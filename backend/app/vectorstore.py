"""
Chroma-based vector store, local and free (persists to disk, no server needed).
Each workspace gets its own collection so file-collections/workspaces stay isolated.
Metadata (filename, file_type, location, page) is stored alongside every vector
so retrieval results can be turned directly into citations, and so we can do
metadata-aware / hybrid filtering (e.g. restrict to one file for comparisons).
"""
from dataclasses import dataclass
import uuid

import chromadb

from app.config import settings
from app.embeddings import embed_texts, embed_query
from app.retrieval import bm25_scores_from_tokens, hybrid_rerank_score, tokenize

_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
_bm25_cache: dict[str, "_BM25Corpus"] = {}


@dataclass
class _BM25Corpus:
    ids: list[str]
    documents: list[str]
    metadatas: list[dict]
    tokens: list[list[str]]


def _load_bm25_corpus(workspace_id: str, collection) -> _BM25Corpus:
    corpus = _bm25_cache.get(workspace_id)
    if corpus is None:
        result = collection.get(include=["documents", "metadatas"])
        documents = result["documents"]
        corpus = _BM25Corpus(
            ids=result["ids"],
            documents=documents,
            metadatas=result["metadatas"],
            tokens=[tokenize(document or "") for document in documents],
        )
        _bm25_cache[workspace_id] = corpus
    return corpus


def _invalidate_bm25_cache(workspace_id: str) -> None:
    _bm25_cache.pop(workspace_id, None)


def _collection(workspace_id: str):
    return _client.get_or_create_collection(name=f"ws_{workspace_id}")


def add_chunks(workspace_id: str, file_id: str, filename: str, file_type: str, chunks: list[dict]) -> int:
    if not chunks:
        return 0
    col = _collection(workspace_id)
    texts = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{
        "file_id": file_id,
        "filename": filename,
        "file_type": file_type,
        "location": c.get("location", ""),
        "page": c.get("page") if c.get("page") is not None else -1,
        "image_path": c.get("image_path", ""),
    } for c in chunks]

    col.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
    _invalidate_bm25_cache(workspace_id)
    return len(chunks)


def delete_file_chunks(workspace_id: str, file_id: str):
    col = _collection(workspace_id)
    col.delete(where={"file_id": file_id})
    _invalidate_bm25_cache(workspace_id)


def query(
    workspace_id: str,
    question: str,
    top_k: int = 8,
    file_ids: list[str] | None = None,
    hybrid: bool = True,
) -> list[dict]:
    col = _collection(workspace_id)
    if col.count() == 0:
        return []

    where = {"file_id": {"$in": file_ids}} if file_ids else None
    q_vec = embed_query(question)

    # Fetch extra candidates so the image boost below can promote images that
    # sit just outside the top_k without dropping genuinely relevant text hits.
    fetch_k = min(top_k * 3, col.count())
    result = col.query(
        query_embeddings=[q_vec],
        n_results=fetch_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits_by_id = {
        chunk_id: {
            "text": doc,
            "score": 1 - dist,
            **meta,
        }
        for chunk_id, doc, meta, dist in zip(
            result["ids"][0],
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
    }

    if hybrid:
        corpus = _load_bm25_corpus(workspace_id, col)
        allowed_files = set(file_ids) if file_ids else None
        candidate_indexes = [
            i for i, meta in enumerate(corpus.metadatas)
            if allowed_files is None or meta["file_id"] in allowed_files
        ]
        bm25_scores = bm25_scores_from_tokens(
            tokenize(question),
            [corpus.tokens[i] for i in candidate_indexes],
        )
        max_bm25 = max(bm25_scores, default=0.0)
        lexical_indexes = sorted(
            (
                (candidate_indexes[position], score)
                for position, score in enumerate(bm25_scores)
                if score > 0
            ),
            key=lambda item: item[1],
            reverse=True,
        )[:fetch_k]
        for index, bm25_score in lexical_indexes:
            chunk_id = corpus.ids[index]
            hit = hits_by_id.get(chunk_id)
            if hit is None:
                hit = {
                    "text": corpus.documents[index],
                    "score": 0.0,
                    **corpus.metadatas[index],
                }
                hits_by_id[chunk_id] = hit
            hit["score"] = hybrid_rerank_score(
                hit["score"], bm25_score, max_bm25
            )

    hits = list(hits_by_id.values())

    # Image boost: image chunks often embed weakly (their text is just OCR
    # fragments or a fallback placeholder), so pure similarity undersells
    # diagrams/graphs. Add a small constant bonus so they surface in top_k
    # when the question's embedding puts them anywhere near the top of the
    # candidate pool. The boost is intentionally smaller than a typical
    # text-vs-text similarity gap so irrelevant images still lose to
    # genuinely relevant text.
    IMAGE_BOOST = 0.15
    for h in hits:
        if h.get("image_path"):
            h["score"] += IMAGE_BOOST

        h["score"] = round(h["score"], 4)
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]
