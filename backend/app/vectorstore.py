"""
Chroma-based vector store, local and free (persists to disk, no server needed).
Each workspace gets its own collection so file-collections/workspaces stay isolated.
Metadata (filename, file_type, location, page) is stored alongside every vector
so retrieval results can be turned directly into citations, and so we can do
metadata-aware / hybrid filtering (e.g. restrict to one file for comparisons).
"""
import chromadb
import uuid
from app.config import settings
from app.embeddings import embed_texts, embed_query

_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)


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
    return len(chunks)


def delete_file_chunks(workspace_id: str, file_id: str):
    col = _collection(workspace_id)
    col.delete(where={"file_id": file_id})


def query(workspace_id: str, question: str, top_k: int = 8, file_ids: list[str] | None = None) -> list[dict]:
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

    hits = []
    for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        hits.append({
            "text": doc,
            "score": round(1 - dist, 4),  # cosine distance -> similarity-ish score
            **meta,
        })

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
            h["score"] = round(h["score"] + IMAGE_BOOST, 4)

    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:top_k]
