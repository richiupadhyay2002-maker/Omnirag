"""
OmniRAG evaluation harness — real accuracy number for YOUR documents.

Metrics
-------
Retrieval (no LLM needed, fast, objective):
  - Recall@k : was the expected source file in the top-k?
  - MRR      : mean reciprocal rank of first relevant hit (0..1)
Answer (needs Ollama running):
  - Keyword accuracy : expected keywords / expected_answer in generated answer
  - Ragas (full)     : faithfulness, answer_relevancy, context_precision,
                       context_recall — via local Ollama judge (no OpenAI key)

Usage (pytest — recommended)
----------------------------
  cd backend
  # fast CI gate: retrieval only, no LLM
  python -m pytest tests/eval_rag.py -v
  # full run with answers + lightweight judge
  python -m pytest tests/eval_rag.py -v -s --eval-with-answers --eval-judge lightweight
  # full run with standard Ragas metrics (needs: pip install -r requirements.txt + ollama serve)
  python -m pytest tests/eval_rag.py -v -s --eval-with-answers --eval-judge ragas

Usage (standalone CLI)
----------------------
  python -m tests.eval_rag --docs tests/eval_data/docs --questions tests/eval_data/golden_questions.csv
  python -m tests.eval_rag --docs path/to/my/docs --questions my_golden.csv --with-answers --judge ragas --fail-under 0.7

Golden CSV schema (new cols optional, backward-compat with old 4-col file):
  question,expected_answer,source_filename,keywords,category,difficulty
  keywords use "|" as OR separator, e.g. "paris|france". category in
  {factual,cross-file,unanswerable,code,image}. Empty source_filename means
  "no specific source required" (unanswerable Qs expect the not-found reply).

Results are printed as a table and written to eval/results.json.
"""
import argparse
import csv
import json
import re
import sys
import time
import uuid
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
EVAL_DIR = BACKEND / "eval"
DEFAULT_DOCS = HERE / "eval_data" / "docs"
DEFAULT_QUESTIONS = HERE / "eval_data" / "golden_questions.csv"
RESULTS_PATH = EVAL_DIR / "results.json"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

NOT_FOUND_RE = re.compile(r"couldn.?t find.*uploaded files", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Lazy imports (keep pytest collection light; heavy deps load only when used)
# ---------------------------------------------------------------------------
def _app_modules():
    from app.ingestion import detect_file_type, load_file
    from app.chunking import chunk_documents
    from app import vectorstore, memory
    from app.rag import answer_question
    return detect_file_type, load_file, chunk_documents, vectorstore, memory, answer_question


# ---------------------------------------------------------------------------
# Golden-set loading (backward-compat: old 4-col CSV still works)
# ---------------------------------------------------------------------------
def load_questions(csv_path: str | Path) -> list[dict]:
    qs: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qs.append({
                "question": (row.get("question") or "").strip(),
                "expected_answer": (row.get("expected_answer") or "").strip(),
                "source_filename": (row.get("source_filename") or "").strip(),
                "keywords": [k.strip().lower()
                             for k in (row.get("keywords") or "").split("|") if k.strip()],
                "category": (row.get("category") or "factual").strip().lower() or "factual",
                "difficulty": (row.get("difficulty") or "").strip().lower(),
            })
    qs = [q for q in qs if q["question"]]
    if not qs:
        raise SystemExit(f"No questions found in {csv_path}")
    return qs


# ---------------------------------------------------------------------------
# Isolated ingestion fixture helper
# ---------------------------------------------------------------------------
def ingest_docs(docs_dir: str | Path, workspace_name: str | None = None) -> str:
    detect_file_type, load_file, chunk_documents, vectorstore, memory, _ = _app_modules()
    docs_dir = Path(docs_dir)
    if not docs_dir.is_dir():
        raise SystemExit(f"--docs not found: {docs_dir}")
    ws = memory.create_workspace(workspace_name or f"eval-{uuid.uuid4().hex[:8]}")
    ws_id = ws["id"]
    files = sorted(p for p in docs_dir.iterdir() if p.is_file())
    if not files:
        raise SystemExit(f"No files found in {docs_dir}")
    total_chunks = 0
    for path in files:
        ftype = detect_file_type(path.name)
        if ftype == "unsupported":
            print(f"  skip (unsupported): {path.name}")
            continue
        try:
            size = path.stat().st_size
            raw = load_file(str(path), ftype)
        except (ValueError, ImportError) as e:
            print(f"  skip ({ftype} loader unavailable): {path.name} [{e}]")
            continue
        chunks = chunk_documents(raw, ftype)
        rec = memory.add_file(ws_id, path.name, ftype, size)
        n = vectorstore.add_chunks(ws_id, rec["file_id"], path.name, ftype, chunks)
        memory.update_file_status(rec["file_id"], "ready", num_chunks=n)
        total_chunks += n
        print(f"  ingested: {path.name} ({ftype}, {n} chunks)")
    print(f"Total chunks embedded: {total_chunks}")
    if total_chunks == 0:
        raise SystemExit("Nothing was embedded — check document formats.")
    return ws_id


def cleanup_workspace(ws_id: str) -> None:
    """Remove eval workspace: Chroma collection + memory file records."""
    try:
        _, _, _, vectorstore, memory, _ = _app_modules()
        try:
            col = vectorstore._collection(ws_id)  # internal but correct cleanup
            try:
                vectorstore._client.delete_collection(name=f"ws_{ws_id}")
            except Exception:
                # fallback: delete docs one-by-one if client API differs
                try:
                    ids = col.get().get("ids", [])
                    if ids:
                        col.delete(ids=ids)
                except Exception:
                    pass
        except Exception as e:
            print(f"  [cleanup: chroma: {e}]")
        try:
            for f in memory.list_files(ws_id):
                try:
                    memory.delete_file(f["file_id"])
                except Exception:
                    pass
            # remove workspace record itself
            try:
                import json as _json
                from app.memory import _load as _mload, _save as _msave
                db = _mload()
                db.get("workspaces", {}).pop(ws_id, None)
                _msave(db)
            except Exception:
                pass
        except Exception as e:
            print(f"  [cleanup: memory: {e}]")
    except Exception as e:
        print(f"  [cleanup failed: {e}]")
def _torch_usable() -> bool:
    """True if torch imports OK (blocked by WDAC/AppLocker on some machines)."""
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def score_retrieval_tfidf(docs_dir: str | Path, questions: list[dict],
                          top_k: int = 8, hybrid: bool = False) -> dict:
    """Pure-Python TF-IDF baseline, optionally reranked with BM25.

    Used ONLY when torch/sentence-transformers AND sklearn are unusable on
    this machine (both ship compiled DLLs blocked by WDAC/AppLocker here).
    Ingests via the real loaders + chunker, scores with hand-rolled TF-IDF
    cosine similarity and the same BM25 reranker as production (stdlib only).
    Results are labeled as a fallback and are not semantic-embedding scores.
    Real semantic numbers require torch working (see eval_workspace skip).
    """
    from math import log
    from app.ingestion import detect_file_type, load_file
    from app.chunking import chunk_documents
    from app.retrieval import bm25_scores_from_tokens, hybrid_rerank_score, tokenize

    docs_dir = Path(docs_dir)
    chunks: list[dict] = []  # {text, filename, tf: Counter}
    df: dict[str, int] = {}
    for path in sorted(p for p in docs_dir.iterdir() if p.is_file()):
        ftype = detect_file_type(path.name)
        if ftype == "unsupported":
            continue
        try:
            raw = load_file(str(path), ftype)
        except (ValueError, ImportError):
            continue
        for c in chunk_documents(raw, ftype):
            toks = _tokenize(c["text"])
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            for t in tf:
                df[t] = df.get(t, 0) + 1
            chunks.append({"text": c["text"], "filename": path.name, "tf": tf})
    if not chunks:
        raise SystemExit("Nothing chunked for TF-IDF fallback.")
    n = len(chunks)
    idf = {t: log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}

    def vec_norm(tf: dict[str, int]) -> tuple[dict[str, float], float]:
        w = {t: (f * idf.get(t, log(1 + n) + 1.0)) for t, f in tf.items()}
        norm = sum(v * v for v in w.values()) ** 0.5
        return w, norm

    chunk_vecs = [vec_norm(c["tf"]) for c in chunks]
    chunk_tokens = [tokenize(c["text"]) for c in chunks]
    per_q: list[dict] = []
    rrs: list[float] = []
    hits = scored = 0
    for q in questions:
        if not q["source_filename"]:
            per_q.append({"question": q["question"], "category": q["category"],
                          "expected_source": "", "retrieved_rank": None,
                          "top_file": None, "reciprocal_rank": None,
                          "excluded_from_recall": True})
            continue
        qtf: dict[str, int] = {}
        for t in _tokenize(q["question"]):
            qtf[t] = qtf.get(t, 0) + 1
        qw, qn = vec_norm(qtf)
        sims = []
        for (cw, cn) in chunk_vecs:
            dot = sum(qw.get(t, 0.0) * cw.get(t, 0.0) for t in qw)
            sims.append(dot / (qn * cn) if qn and cn else 0.0)
        if hybrid:
            bm25 = bm25_scores_from_tokens(tokenize(q["question"]), chunk_tokens)
            max_bm25 = max(bm25, default=0.0)
            scores = [
                hybrid_rerank_score(dense, lexical, max_bm25)
                for dense, lexical in zip(sims, bm25)
            ]
        else:
            scores = sims
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        expected = q["source_filename"].lower()
        rank = next((i + 1 for i, idx in enumerate(order)
                     if chunks[idx]["filename"].lower() == expected), None)
        rr = 1.0 / rank if rank else 0.0
        rrs.append(rr)
        scored += 1
        hits += 1 if rank else 0
        per_q.append({"question": q["question"], "category": q["category"],
                      "expected_source": q["source_filename"],
                      "retrieved_rank": rank,
                      "top_file": chunks[order[0]]["filename"] if order else None,
                      "reciprocal_rank": round(rr, 4)})
    return {"backend": "tfidf+bm25-fallback-pure" if hybrid else "tfidf-fallback-pure",
            "recall_at_k": round(hits / scored, 4) if scored else 0.0,
            "mrr": round(sum(rrs) / len(rrs), 4) if rrs else 0.0,
            "top_k": top_k, "num_scored": scored,
            "num_unanswerable_excluded": len(questions) - scored,
            "details": per_q}


# ---------------------------------------------------------------------------
# Retrieval scoring (no LLM) + answer collection for Ragas
# ---------------------------------------------------------------------------
def score_retrieval(ws_id: str, questions: list[dict], top_k: int = 8,
                    hybrid: bool = True) -> dict:
    """Recall@k + MRR: is the expected source file in the top-k, at what rank?

    Unanswerable Qs (empty source_filename) pass retrieval iff the answer
    stage says the not-found sentence (checked in score_answers); here they
    are reported with retrieved_rank=None and excluded from recall/MRR so a
    deliberately-unanswerable Q can't inflate retrieval scores.
    """
    _, _, _, vectorstore, _, _ = _app_modules()
    per_q: list[dict] = []
    rrs: list[float] = []
    hits = 0
    scored = 0
    for q in questions:
        result = vectorstore.query(
            ws_id, q["question"], top_k=top_k, hybrid=hybrid
        )
        expected_src = q["source_filename"].lower()
        if not expected_src:
            per_q.append({"question": q["question"], "category": q["category"],
                          "expected_source": "", "retrieved_rank": None,
                          "top_file": result[0]["filename"] if result else None,
                          "reciprocal_rank": None, "excluded_from_recall": True})
            continue
        rank = next((i for i, h in enumerate(result, start=1)
                     if h["filename"].lower() == expected_src), None)
        rr = 1.0 / rank if rank else 0.0
        rrs.append(rr)
        scored += 1
        hits += 1 if rank else 0
        per_q.append({"question": q["question"], "category": q["category"],
                      "expected_source": q["source_filename"], "retrieved_rank": rank,
                      "top_file": result[0]["filename"] if result else None,
                      "reciprocal_rank": round(rr, 4)})
    return {"recall_at_k": round(hits / scored, 4) if scored else 0.0,
            "mrr": round(sum(rrs) / len(rrs), 4) if rrs else 0.0,
            "top_k": top_k, "num_scored": scored,
            "num_unanswerable_excluded": len(questions) - scored,
            "details": per_q}


def collect_answers(ws_id: str, questions: list[dict], top_k: int = 8) -> list[dict]:
    """Run the full RAG pipeline per question; capture answer + contexts.

    Returns rows ready for keyword scoring AND for ragas Dataset creation:
    {question, ground_truth, answer, contexts, citations, latency_s}.
    """
    _, _, _, vectorstore, _, answer_question = _app_modules()
    rows: list[dict] = []
    for q in questions:
        t0 = time.time()
        hits = vectorstore.query(ws_id, q["question"], top_k=top_k)
        contexts = [h["text"] for h in hits]
        stream, citations = answer_question(ws_id, q["question"], top_k=top_k)
        answer = "".join(stream).strip()
        rows.append({"question": q["question"],
                     "ground_truth": q["expected_answer"],
                     "answer": answer,
                     "contexts": contexts,
                     "citations": citations,
                     "category": q["category"],
                     "keywords": q["keywords"],
                     "latency_s": round(time.time() - t0, 2)})
    return rows


def score_keyword_accuracy(rows: list[dict]) -> dict:
    per_q: list[dict] = []
    passes = 0
    for r in rows:
        ans_low = r["answer"].lower()
        if r["category"] == "unanswerable":
            ok = bool(NOT_FOUND_RE.search(r["answer"]))
            found = ["<not-found-reply>"] if ok else []
        elif r["keywords"]:
            found = [k for k in r["keywords"] if k in ans_low]
            ok = bool(found)
        else:
            ok = bool(r["ground_truth"]) and r["ground_truth"].lower() in ans_low
            found = [r["ground_truth"]] if ok else []
        passes += 1 if ok else 0
        per_q.append({"question": r["question"], "answer_excerpt": r["answer"][:300],
                      "expected_answer": r["ground_truth"], "keywords_found": found,
                      "keyword_pass": ok, "latency_s": r["latency_s"],
                      "num_citations": len(r["citations"]),
                      "num_contexts": len(r["contexts"])})
    n = len(rows)
    return {"keyword_accuracy": round(passes / n, 4) if n else 0.0,
            "num_passed": passes, "num_total": n, "details": per_q}


def _ollama_http_generate(user_prompt: str, system_prompt: str,
                          timeout: int = 180) -> str:
    """Generate via Ollama HTTP API with stdlib only (no `ollama` pkg needed).

    Honors OLLAMA_BASE_URL / OLLAMA_MODEL env vars (same as app/config.py
    defaults). Returns a ⚠️ warning string if unreachable, mirroring
    app/llm.py behaviour so callers can skip cleanly.
    """
    import json as _json
    import os as _os
    import urllib.request as _url
    base = _os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = _os.environ.get("OLLAMA_MODEL", "llama3:latest")
    body = _json.dumps({"model": model, "stream": False,
                        "messages": [{"role": "system", "content": system_prompt},
                                     {"role": "user", "content": user_prompt}],
                        "options": {"temperature": 0}}).encode()
    try:
        req = _url.Request(base + "/api/chat", data=body,
                           headers={"Content-Type": "application/json"})
        with _url.urlopen(req, timeout=timeout) as resp:
            data = _json.loads(resp.read().decode())
        return data.get("message", {}).get("content", "")
    except Exception as e:
        return (f"⚠️ Could not reach the local Ollama model ('{model}'). "
                f"Details: {e}")


def _chunk_docs_for_tfidf(docs_dir: str | Path) -> list[dict]:
    """Chunk docs via real loaders; shared by TF-IDF retrieval + answer gen."""
    from app.ingestion import detect_file_type, load_file
    from app.chunking import chunk_documents

    docs_dir = Path(docs_dir)
    chunks: list[dict] = []
    for path in sorted(p for p in docs_dir.iterdir() if p.is_file()):
        ftype = detect_file_type(path.name)
        if ftype == "unsupported":
            continue
        try:
            raw = load_file(str(path), ftype)
        except (ValueError, ImportError):
            continue
        for c in chunk_documents(raw, ftype):
            chunks.append({"text": c["text"], "filename": path.name,
                           "location": c.get("location", "")})
    return chunks


def collect_answers_tfidf(docs_dir: str | Path, questions: list[dict],
                          top_k: int = 8, max_ctx_chars: int = 6000,
                          hybrid: bool = True) -> list[dict]:
    """Full RAG pipeline WITHOUT torch: TF-IDF + optional BM25 and Ollama.

    Uses the same grounded SYSTEM_PROMPT as app/rag.py so the answer
    accuracy reflects the real prompt/pipeline (only the retriever differs).
    NOTE: prompt text is inlined (not imported from app.rag) because
    importing app.rag pulls app.vectorstore -> torch, which is blocked
    on this machine.
    """
    from math import log
    from app.retrieval import bm25_scores_from_tokens, hybrid_rerank_score, tokenize

    try:
        from app.llm import generate_stream  # needs `ollama` pkg
        _have_app_llm = True
    except ImportError:
        _have_app_llm = False

    # Keep in sync with app/rag.py SYSTEM_PROMPT / MODE_INSTRUCTIONS.
    _SYSTEM_PROMPT = """You are OmniRAG, an assistant that answers questions strictly using the CONTEXT
provided from the user's uploaded files. Rules:

1. Only use information present in the CONTEXT below. Do not use outside/general knowledge to state facts
   about the files' content.
2. If the answer is not present in the CONTEXT, clearly say: "I couldn't find this in the uploaded files."
   Do not invent or guess.
3. When you use information from the context, be precise about which file and location it came from
   (this is shown separately as citations, but stay faithful to the source).
4. When multiple files are involved, distinguish clearly which source supports which part of your answer.
5. Format your answer in clean Markdown: use headings, bullet points, tables, and fenced code blocks
   (with language tags) where appropriate.
"""

    chunks = _chunk_docs_for_tfidf(docs_dir)
    if not chunks:
        raise SystemExit("Nothing chunked for answer generation.")
    df: dict[str, int] = {}
    tf_list: list[dict[str, int]] = []
    for c in chunks:
        tf: dict[str, int] = {}
        for t in _tokenize(c["text"]):
            tf[t] = tf.get(t, 0) + 1
        tf_list.append(tf)
        for t in tf:
            df[t] = df.get(t, 0) + 1
    n = len(chunks)
    idf = {t: log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
    chunk_tokens = [tokenize(c["text"]) for c in chunks]

    def score(q: str) -> list[int]:
        qtf: dict[str, int] = {}
        for t in _tokenize(q):
            qtf[t] = qtf.get(t, 0) + 1
        qw = {t: f * idf.get(t, log(1 + n) + 1.0) for t, f in qtf.items()}
        qnorm = sum(v * v for v in qw.values()) ** 0.5
        sims = []
        for tf in tf_list:
            cw = {t: f * idf.get(t, log(1 + n) + 1.0) for t, f in tf.items()}
            cnorm = sum(v * v for v in cw.values()) ** 0.5
            dot = sum(qw.get(t, 0.0) * cw.get(t, 0.0) for t in qw)
            sims.append(dot / (qnorm * cnorm) if qnorm and cnorm else 0.0)
        if hybrid:
            bm25 = bm25_scores_from_tokens(tokenize(q), chunk_tokens)
            max_bm25 = max(bm25, default=0.0)
            scores = [
                hybrid_rerank_score(dense, lexical, max_bm25)
                for dense, lexical in zip(sims, bm25)
            ]
        else:
            scores = sims
        return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    rows: list[dict] = []
    for quest in questions:
        t0 = time.time()
        order = score(quest["question"])
        hits = [chunks[i] for i in order]
        contexts = [h["text"] for h in hits]
        blocks = [f"[Source {i + 1}: {h['filename']} — {h['location']}]\n{h['text']}"
                  for i, h in enumerate(hits)]
        context_block = "\n\n---\n\n".join(blocks)[:max_ctx_chars]
        user_prompt = ("MODE INSTRUCTION: Answer clearly and directly using only "
                       "the provided context.\n\n"
                       f"CONTEXT:\n{context_block}\n\n"
                       f"QUESTION:\n{quest['question']}\n")
        if _have_app_llm:
            answer = "".join(generate_stream(_SYSTEM_PROMPT, user_prompt)).strip()
        else:
            # No `ollama` pip pkg here — talk to Ollama's HTTP API directly
            # (stdlib urllib, no new deps).
            answer = _ollama_http_generate(user_prompt, _SYSTEM_PROMPT).strip()
        rows.append({"question": quest["question"],
                     "ground_truth": quest["expected_answer"],
                     "answer": answer,
                     "contexts": contexts,
                     "citations": [{"filename": h["filename"],
                                    "location": h["location"]} for h in hits],
                     "category": quest["category"],
                     "keywords": quest["keywords"],
                     "latency_s": round(time.time() - t0, 2)})
    return rows
# ---------------------------------------------------------------------------
# Judges: lightweight (zero new deps) + full Ragas
# ---------------------------------------------------------------------------
def lightweight_judge(question: str, expected: str, answer: str) -> float | None:
    """1-5 faithfulness rating via the app's own LLM abstraction.

    Routes through app.llm.generate_stream so OLLAMA_MODEL / GROQ_MODEL in
    .env are honoured (unlike calling ollama.chat with a hardcoded model).
    Falls back to direct Ollama HTTP (stdlib) when the `ollama` pip package
    is missing. Returns None if the LLM is unreachable.
    """
    prompt = ("You are grading a RAG system. Rate 1-5 how well the ANSWER "
              "addresses the QUESTION using the REFERENCE as ground truth.\n\n"
              f"QUESTION: {question}\n\nREFERENCE: {expected}\n\nANSWER: {answer}\n\n"
              "Reply with only a single digit 1-5.")
    try:
        try:
            from app.llm import generate_stream
            text = "".join(generate_stream(
                "You are a strict evaluator. Reply with only a single digit 1-5.",
                prompt)).strip()
        except ImportError:
            text = _ollama_http_generate(
                prompt,
                "You are a strict evaluator. Reply with only a single digit 1-5.").strip()
        if text.startswith("⚠️"):
            print(f"  [judge unavailable: {text[:120]}]")
            return None
        m = re.search(r"[1-5]", text)
        return float(m.group()) if m else None
    except Exception as e:
        print(f"  [judge unavailable: {e}]")
        return None


def score_ragas(rows: list[dict]) -> dict:
    """Standard Ragas metrics with a LOCAL Ollama judge (no OpenAI key).

    Requires: pip install ragas datasets langchain-ollama + `ollama serve`
    with settings.OLLAMA_MODEL pulled. Raises ImportError/RuntimeError with a
    clear message when requirements are missing so pytest can skip cleanly.
    """
    usable = [r for r in rows if r["answer"] and r["contexts"]]
    if not usable:
        raise RuntimeError("No usable answer/context rows for Ragas scoring.")
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.run_config import RunConfig
    except ImportError as e:
        raise ImportError(
            "Ragas not installed or an evaluation dependency is missing. "
            "Run: pip install -r backend/requirements.txt. "
            f"Import detail: {e}") from e
    try:
        from langchain_ollama import ChatOllama, OllamaEmbeddings
        from app.config import settings
    except ImportError as e:
        raise ImportError(
            "langchain-ollama not installed. Run: pip install langchain-ollama."
        ) from e
    # Import metric objects version-agnostically (ragas 0.1.x vs 0.2.x layouts).
    try:
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    except ImportError:
        from ragas.metrics.faithfulness import faithfulness  # type: ignore
        from ragas.metrics.answer_relevance import answer_relevancy  # type: ignore
        from ragas.metrics.context_precision import context_precision  # type: ignore
        from ragas.metrics.context_recall import context_recall  # type: ignore

    unanswerable = [r for r in rows if r["category"] == "unanswerable"]
    if unanswerable:
        print(f"  note: {len(unanswerable)} unanswerable Q(s) included in Ragas; "
              "faithfulness on correct refusals may score low — interpret separately.")

    llm = ChatOllama(model=settings.OLLAMA_MODEL,
                     base_url=settings.OLLAMA_BASE_URL, temperature=0)
    embeddings = OllamaEmbeddings(model=settings.OLLAMA_EMBEDDING_MODEL,
                                  base_url=settings.OLLAMA_BASE_URL)
    # Preflight: fail fast with a clear message if Ollama is down.
    try:
        llm.invoke("Reply with: ok")
    except Exception as e:
        raise RuntimeError(
            f"Ollama judge unreachable at {settings.OLLAMA_BASE_URL} "
            f"(model={settings.OLLAMA_MODEL}). Run `ollama serve` + "
            f"`ollama pull {settings.OLLAMA_MODEL}`. Details: {e}") from e

    dataset = Dataset.from_dict({
        "question": [r["question"] for r in usable],
        "ground_truth": [r["ground_truth"] or r["question"] for r in usable],
        "answer": [r["answer"] for r in usable],
        "contexts": [r["contexts"] for r in usable],
    })
    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm, embeddings=embeddings, raise_exceptions=False,
        run_config=RunConfig(timeout=600, max_retries=1, max_workers=1))
    scores = result.to_pandas()
    numeric_scores = scores.select_dtypes(include="number")
    means = {}
    metric_counts = {}
    for metric in numeric_scores.columns:
        valid_scores = numeric_scores[metric].dropna()
        metric_counts[metric] = len(valid_scores)
        if not valid_scores.empty:
            means[metric] = round(float(valid_scores.mean()), 4)
    return {"means": means, "metric_counts": metric_counts,
            "num_scored": len(usable),
            "model": settings.OLLAMA_MODEL}
# ---------------------------------------------------------------------------
# Orchestration + report
# ---------------------------------------------------------------------------
def run_eval(docs_dir, questions_path, top_k=8, with_answers=False, judge="none"):
    questions = load_questions(questions_path)
    print(f"Loaded {len(questions)} golden questions.\n")
    if _torch_usable():
        print("Ingesting documents (Chroma backend)...")
        ws_id = ingest_docs(docs_dir)
        try:
            print("Scoring dense baseline and hybrid retrieval...")
            retrieval_baseline = score_retrieval(
                ws_id, questions, top_k=top_k, hybrid=False
            )
            retrieval = score_retrieval(
                ws_id, questions, top_k=top_k, hybrid=True
            )
            answers = None
            rows = []
            if with_answers:
                print("Generating answers (can take a while on local models)...")
                rows = collect_answers(ws_id, questions, top_k=top_k)
                answers = score_keyword_accuracy(rows)
                if judge == "lightweight":
                    js = [lightweight_judge(r["question"], r["ground_truth"], r["answer"])
                          for r in rows if r["ground_truth"]]
                    js = [j for j in js if j is not None]
                    answers["judge_mean"] = round(sum(js) / len(js), 2) if js else None
                    answers["judge_n"] = len(js)
                elif judge == "ragas":
                    answers["ragas"] = score_ragas(rows)
            preview = [{"question": r["question"], "answer": r["answer"][:500],
                        "contexts_n": len(r["contexts"])} for r in rows]
            return {"retrieval": retrieval, "retrieval_baseline": retrieval_baseline,
                    "answers": answers, "answer_rows": preview}
        finally:
            cleanup_workspace(ws_id)
    # Torch-free path: TF-IDF retrieval (+ Ollama answers if requested).
    print("torch unavailable — using TF-IDF fallback retriever...")
    print("Scoring TF-IDF baseline and hybrid retrieval...")
    retrieval_baseline = score_retrieval_tfidf(
        docs_dir, questions, top_k=top_k, hybrid=False
    )
    retrieval = score_retrieval_tfidf(
        docs_dir, questions, top_k=top_k, hybrid=True
    )
    answers = None
    rows = []
    if with_answers:
        print("Generating answers with Ollama (TF-IDF contexts)...")
        rows = collect_answers_tfidf(docs_dir, questions, top_k=top_k)
        if rows and rows[0]["answer"].startswith("⚠️"):
            print(f"Ollama unreachable, keyword scoring only: {rows[0]['answer'][:150]}")
        answers = score_keyword_accuracy(rows)
        if judge == "lightweight":
            js = [lightweight_judge(r["question"], r["ground_truth"], r["answer"])
                  for r in rows if r["ground_truth"]]
            js = [j for j in js if j is not None]
            answers["judge_mean"] = round(sum(js) / len(js), 2) if js else None
            answers["judge_n"] = len(js)
        elif judge == "ragas":
            try:
                answers["ragas"] = score_ragas(rows)
            except (ImportError, RuntimeError) as e:
                answers["ragas_skipped"] = str(e)
    preview = [{"question": r["question"], "answer": r["answer"][:500],
                "contexts_n": len(r["contexts"])} for r in rows]
    return {"retrieval": retrieval, "retrieval_baseline": retrieval_baseline,
            "answers": answers, "answer_rows": preview}


def print_report(retrieval, answers, retrieval_baseline=None) -> None:
    print("\n" + "=" * 64)
    print("OMNIRAG EVALUATION RESULTS")
    print("=" * 64)
    if retrieval_baseline:
        print(f"Before (dense baseline) Recall@{retrieval_baseline['top_k']}: "
              f"{retrieval_baseline['recall_at_k']*100:.1f}%  "
              f"MRR: {retrieval_baseline['mrr']:.4f}")
    print(f"After (hybrid rerank)  Recall@{retrieval['top_k']}: "
          f"{retrieval['recall_at_k']*100:.1f}%  MRR: {retrieval['mrr']:.4f}")
    print(f"Recall@{retrieval['top_k']} (right source) : "
          f"{retrieval['recall_at_k']*100:.1f}%  (n={retrieval['num_scored']})")
    print(f"MRR (mean reciprocal rank)          : {retrieval['mrr']:.3f}")
    if retrieval.get("num_unanswerable_excluded"):
        print(f"Unanswerable excluded from recall   : "
              f"{retrieval['num_unanswerable_excluded']}")
    if answers:
        print(f"Keyword answer accuracy             : "
              f"{answers['keyword_accuracy']*100:.1f}% "
              f"({answers['num_passed']}/{answers['num_total']})")
        if answers.get("judge_mean") is not None:
            print(f"Lightweight LLM-judge (1-5)         : "
                  f"{answers['judge_mean']} (n={answers.get('judge_n', 0)})")
        if answers.get("ragas"):
            print("Ragas (local Ollama judge):")
            for k, v in answers["ragas"]["means"].items():
                print(f"  - {k:<18}: {v}")
        elif answers.get("ragas_skipped"):
            print(f"Ragas not run: {answers['ragas_skipped']}")
    print("-" * 64)
    print(f"{'Q':<48} {'rank':>5}")
    for d in retrieval["details"]:
        rank = d["retrieved_rank"] if d["retrieved_rank"] else "-"
        print(f"{d['question'][:47]:<48} {rank:>5}")
    print("=" * 64)


def write_results(payload: dict) -> Path:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Full details written to {RESULTS_PATH}")
    return RESULTS_PATH
def _opt(request, name, default=None):
    try:
        return request.config.getoption(name)
    except (ValueError, AttributeError):
        return default


@pytest.fixture()
def eval_workspace(request):
    if not _torch_usable():
        pytest.skip(
            "torch blocked by Windows Application Control on this machine "
            "(shm.dll, WinError 4551) — live Chroma eval skipped. "
            "TF-IDF fallback numbers are reported by "
            "test_retrieval_tfidf_fallback below. Fix: allow-list "
            "Python/torch in WDAC/AppLocker, or run eval where torch works.")
    try:
        ws_id = ingest_docs(_opt(request, "eval_docs", str(DEFAULT_DOCS)))
    except OSError as e:
        if "Application Control" in str(e) or "shm.dll" in str(e) or "WinError 4551" in str(e):
            pytest.skip(
                "torch blocked by Windows Application Control on this machine "
                "(shm.dll). Fix: allow-list Python/torch in WDAC/AppLocker, "
                "or run eval on a machine with working torch. Details: "
                f"{e}")
        raise
    except ModuleNotFoundError as e:
        pytest.skip(f"Missing backend dependency for eval ingestion: {e} "
                    "(pip install -r requirements.txt)")
    yield ws_id
    cleanup_workspace(ws_id)


def test_rag_retrieval_accuracy(request, eval_workspace):
    """Fast CI gate: Recall@k / MRR. No LLM needed."""
    questions = load_questions(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))
    top_k = _opt(request, "eval_top_k", 8)
    retrieval = score_retrieval(eval_workspace, questions, top_k=top_k)
    print_report(retrieval, None)
    write_results({"retrieval": retrieval, "answers": None,
                   "docs": str(_opt(request, "eval_docs", str(DEFAULT_DOCS))),
                   "questions": str(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))})
    fail_under = _opt(request, "eval_fail_under", 0.0)
    assert retrieval["recall_at_k"] >= fail_under, (
        f"Recall@{top_k} {retrieval['recall_at_k']} < --eval-fail-under {fail_under}")
    assert retrieval["recall_at_k"] > 0, "No golden Q retrieved its source."


def test_retrieval_tfidf_fallback(request):
    """Zero-torch retrieval comparison — runs with the standard library.

    Reports the TF-IDF baseline and TF-IDF + BM25 reranking on the same
    bundled corpus and golden questions.
    """
    questions = load_questions(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))
    top_k = _opt(request, "eval_top_k", 8)
    docs = _opt(request, "eval_docs", str(DEFAULT_DOCS))
    retrieval_baseline = score_retrieval_tfidf(
        docs, questions, top_k=top_k, hybrid=False
    )
    retrieval = score_retrieval_tfidf(
        docs, questions, top_k=top_k, hybrid=True
    )
    print_report(retrieval, None, retrieval_baseline)
    write_results({"retrieval": retrieval,
                   "retrieval_baseline": retrieval_baseline, "answers": None,
                   "docs": str(docs),
                   "questions": str(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))})
    fail_under = _opt(request, "eval_fail_under", 0.0)
    assert retrieval["recall_at_k"] >= fail_under
    assert retrieval["recall_at_k"] > 0, "No golden Q retrieved its source."


def test_answer_tfidf(request):
    """Torch-free answer accuracy: TF-IDF retrieval + Ollama generation.

    Runs whenever --eval-with-answers is passed, even when torch/Chroma is
    blocked. Uses the real loaders + chunker + grounded SYSTEM_PROMPT, so
    the keyword accuracy reflects the true prompt/pipeline quality.
    Skips cleanly only if Ollama is unreachable.
    """
    if not _opt(request, "eval_with_answers", False):
        pytest.skip("Pass --eval-with-answers to score answers (needs Ollama).")
    questions = load_questions(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))
    top_k = _opt(request, "eval_top_k", 8)
    judge = _opt(request, "eval_judge", "none")
    docs = _opt(request, "eval_docs", str(DEFAULT_DOCS))
    rows = collect_answers_tfidf(docs, questions, top_k=top_k)
    if rows and rows[0]["answer"].startswith("⚠️"):
        pytest.skip(f"Ollama unreachable: {rows[0]['answer'][:150]}")
    answers = score_keyword_accuracy(rows)
    if judge == "lightweight":
        js = [lightweight_judge(r["question"], r["ground_truth"], r["answer"])
              for r in rows if r["ground_truth"]]
        js = [j for j in js if j is not None]
        if js:
            answers["judge_mean"] = round(sum(js) / len(js), 2)
            answers["judge_n"] = len(js)
    elif judge == "ragas":
        try:
            answers["ragas"] = score_ragas(rows)
        except (ImportError, RuntimeError) as e:
            answers["ragas_skipped"] = str(e)
    retrieval_baseline = score_retrieval_tfidf(
        docs, questions, top_k=top_k, hybrid=False
    )
    retrieval = score_retrieval_tfidf(
        docs, questions, top_k=top_k, hybrid=True
    )
    retrieval["note"] = ("TF-IDF retriever (torch blocked); answers from "
                         + answers.get("model", "Ollama"))
    print_report(retrieval, answers, retrieval_baseline)
    write_results({"retrieval": retrieval,
                   "retrieval_baseline": retrieval_baseline, "answers": answers,
                   "docs": str(docs),
                   "questions": str(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))})
    assert answers["keyword_accuracy"] > 0, "No answer passed keyword check."


def test_rag_answer_accuracy(request, eval_workspace):
    """Full answer accuracy. Skipped unless --eval-with-answers is passed."""
    if not _opt(request, "eval_with_answers", False):
        pytest.skip("Pass --eval-with-answers to score answers (needs Ollama).")
    questions = load_questions(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))
    top_k = _opt(request, "eval_top_k", 8)
    judge = _opt(request, "eval_judge", "none")
    if judge == "ragas":
        try:
            import ragas  # noqa: F401
            import datasets  # noqa: F401
            import langchain_ollama  # noqa: F401
        except ImportError:
            pytest.skip("Ragas not installed: pip install ragas datasets langchain-ollama")
    rows = collect_answers(eval_workspace, questions, top_k=top_k)
    answers = score_keyword_accuracy(rows)
    if judge == "lightweight":
        js = [lightweight_judge(r["question"], r["ground_truth"], r["answer"])
              for r in rows if r["ground_truth"]]
        js = [j for j in js if j is not None]
        if not js:
            pytest.skip("LLM judge unreachable (is Ollama running?).")
        answers["judge_mean"] = round(sum(js) / len(js), 2)
        answers["judge_n"] = len(js)
    elif judge == "ragas":
        try:
            answers["ragas"] = score_ragas(rows)
        except (ImportError, RuntimeError) as e:
            pytest.skip(f"Ragas unavailable: {e}")
    retrieval_baseline = score_retrieval(
        eval_workspace, questions, top_k=top_k, hybrid=False
    )
    retrieval = score_retrieval(
        eval_workspace, questions, top_k=top_k, hybrid=True
    )
    print_report(retrieval, answers, retrieval_baseline)
    write_results({"retrieval": retrieval,
                   "retrieval_baseline": retrieval_baseline, "answers": answers,
                   "docs": str(_opt(request, "eval_docs", str(DEFAULT_DOCS))),
                   "questions": str(_opt(request, "eval_questions", str(DEFAULT_QUESTIONS)))})
    assert answers["keyword_accuracy"] > 0, "No answer passed keyword check."


# ---------------------------------------------------------------------------
# Standalone CLI: python -m tests.eval_rag ...
# ---------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluate OmniRAG accuracy")
    ap.add_argument("--docs", default=str(DEFAULT_DOCS))
    ap.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--with-answers", action="store_true")
    ap.add_argument("--judge", default="none",
                    choices=["none", "lightweight", "ragas"])
    ap.add_argument("--fail-under", type=float, default=0.0)
    args = ap.parse_args(argv)
    payload = run_eval(args.docs, args.questions, top_k=args.top_k,
                       with_answers=args.with_answers, judge=args.judge)
    print_report(payload["retrieval"], payload["answers"],
                 payload["retrieval_baseline"])
    write_results({"retrieval": payload["retrieval"],
                   "retrieval_baseline": payload["retrieval_baseline"],
                   "answers": payload["answers"],
                   "docs": str(args.docs), "questions": str(args.questions),
                   "answer_rows": payload["answer_rows"]})
    if payload["retrieval"]["recall_at_k"] < args.fail_under:
        raise SystemExit(
            f"FAIL: recall {payload['retrieval']['recall_at_k']} < {args.fail_under}")


if __name__ == "__main__":
    main()
