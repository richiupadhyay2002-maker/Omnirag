"""
OmniRAG evaluation harness — measures real accuracy on YOUR documents.

What it measures
----------------
1. Retrieval quality (no LLM needed, fast, objective):
   - Recall@k   : was the correct file's chunk found in the top-k results?
   - MRR        : mean reciprocal rank of the first relevant hit (0..1)

2. Answer quality (needs a working LLM — Ollama running):
   - Keyword hit: do expected keywords appear in the generated answer?
   - Optional   : LLM-as-judge faithfulness score (1-5) if Ollama is up

Usage
-----
    cd backend

    # retrieval-only evaluation (fast, no Ollama needed)
    python -m eval.eval_rag --docs eval --questions eval/golden_questions.csv

    # full evaluation including generated answers
    python -m eval.eval_rag --docs eval --questions eval/golden_questions.csv --with-answers

    # point at your own documents and question file
    python -m eval.eval_rag --docs path/to/my/docs --questions my_golden.csv --with-answers

Results are printed as a table and written to eval/results.json.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

from app.ingestion import detect_file_type, load_file          # noqa: E402
from app.chunking import chunk_documents                       # noqa: E402
from app import vectorstore, memory                            # noqa: E402
from app.rag import answer_question                            # noqa: E402


# ---------------------------------------------------------------- ingestion
def ingest_docs(docs_dir: str, workspace_name: str = "eval") -> str:
    """Load + chunk + embed every supported file in docs_dir into a fresh eval
    workspace. Returns the workspace_id."""
    ws = memory.create_workspace(workspace_name)
    ws_id = ws["id"]
    files = [p for p in Path(docs_dir).iterdir() if p.is_file()]
    if not files:
        raise SystemExit(f"No files found in {docs_dir}")

    total_chunks = 0
    for path in files:
        ftype = detect_file_type(path.name)
        if ftype == "unsupported":
            print(f"  skip (unsupported): {path.name}")
            continue
        raw = load_file(str(path), ftype)
        chunks = chunk_documents(raw, ftype)
        n = vectorstore.add_chunks(ws_id, "eval-" + path.name, path.name, ftype, chunks)
        total_chunks += n
        print(f"  ingested: {path.name} ({ftype}, {n} chunks)")
    print(f"Total chunks embedded: {total_chunks}")
    if total_chunks == 0:
        raise SystemExit("Nothing was embedded — check document formats.")
    return ws_id


# ---------------------------------------------------------------- retrieval scoring
def load_questions(csv_path: str) -> list[dict]:
    import csv
    qs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qs.append({
                "question": row["question"].strip(),
                "expected_answer": row.get("expected_answer", "").strip(),
                "source_filename": row.get("source_filename", "").strip(),
                "keywords": [k.strip().lower() for k in row.get("keywords", "").split("|") if k.strip()],
            })
    return qs


def score_retrieval(ws_id: str, questions: list[dict], top_k: int = 8) -> dict:
    """For each question, check whether the expected source file appears in the
    retrieved top-k, and at what rank."""
    per_q = []
    reciprocal_ranks = []
    hits = 0
    for q in questions:
        result = vectorstore.query(ws_id, q["question"], top_k=top_k)
        # If no specific source file expected, any non-empty retrieval counts as a hit.
        expected_src = q["source_filename"].lower()
        rank = None
        for i, h in enumerate(result, start=1):
            if not expected_src or h["filename"].lower() == expected_src:
                rank = i
                break
        rr = 1.0 / rank if rank else 0.0
        reciprocal_ranks.append(rr)
        hits += 1 if rank else 0
        per_q.append({
            "question": q["question"],
            "expected_source": q["source_filename"],
            "retrieved_rank": rank,
            "top_file": result[0]["filename"] if result else None,
            "reciprocal_rank": round(rr, 4),
        })

    return {
        "recall_at_k": round(hits / len(questions), 4) if questions else 0.0,
        "mrr": round(sum(reciprocal_ranks) / len(questions), 4) if questions else 0.0,
        "top_k": top_k,
        "details": per_q,
    }


# ---------------------------------------------------------------- answer scoring
def score_answers(ws_id: str, questions: list[dict], use_ollama_judge: bool = False) -> dict:
    """Run the full RAG pipeline per question and check keyword coverage in the
    generated answer. Optionally ask the LLM to judge faithfulness 1-5."""
    per_q = []
    keyword_hits = 0
    judge_scores = []
    for q in questions:
        t0 = time.time()
        stream, citations = answer_question(ws_id, q["question"])
        answer = "".join(stream).strip()
        elapsed = round(time.time() - t0, 2)

        kws = q["keywords"]
        found = [k for k in kws if k in answer.lower()]
        ok = bool(found) if kws else (q["expected_answer"].lower() in answer.lower())
        keyword_hits += 1 if ok else 0

        judge = None
        if use_ollama_judge and q["expected_answer"]:
            judge = _ollama_judge(q["question"], q["expected_answer"], answer)
            if judge is not None:
                judge_scores.append(judge)

        per_q.append({
            "question": q["question"],
            "answer_excerpt": answer[:300],
            "expected_answer": q["expected_answer"],
            "keywords_found": found,
            "keyword_pass": ok,
            "judge_score": judge,
            "latency_s": elapsed,
            "num_citations": len(citations),
        })

    n = len(questions)
    return {
        "keyword_accuracy": round(keyword_hits / n, 4) if n else 0.0,
        "judge_mean": round(sum(judge_scores) / len(judge_scores), 2) if judge_scores else None,
        "details": per_q,
    }


def _ollama_judge(question: str, expected: str, answer: str) -> float | None:
    """Ask the local LLM to rate 1-5 whether the answer correctly addresses the
    question given the expected reference answer. Returns None if Ollama is down."""
    try:
        import ollama
        prompt = (
            "You are grading a RAG system. Rate from 1 to 5 how well the ANSWER "
            "addresses the QUESTION, using the REFERENCE as ground truth.\n\n"
            f"QUESTION: {question}\n\nREFERENCE: {expected}\n\nANSWER: {answer}\n\n"
            "Reply with only a single digit 1-5."
        )
        resp = ollama.chat(model="llama3.1:8b", messages=[{"role": "user", "content": prompt}])
        m = re.search(r"[1-5]", resp["message"]["content"])
        return float(m.group()) if m else None
    except Exception as e:
        print(f"  [judge unavailable: {e}]")
        return None


# ---------------------------------------------------------------- report
def print_report(retrieval: dict, answers: dict | None) -> None:
    print("\n" + "=" * 60)
    print("OMNIRAG EVALUATION RESULTS")
    print("=" * 60)
    print(f"Recall@{retrieval['top_k']} (right source retrieved) : {retrieval['recall_at_k']*100:.1f}%")
    print(f"MRR (mean reciprocal rank)      : {retrieval['mrr']:.3f}")
    if answers:
        print(f"Keyword answer accuracy         : {answers['keyword_accuracy']*100:.1f}%")
        if answers["judge_mean"] is not None:
            print(f"LLM-judge faithfulness (1-5)    : {answers['judge_mean']}")
    print("-" * 60)
    print(f"{'Q':<44} {'rank':>5}")
    for d in retrieval["details"]:
        rank = d["retrieved_rank"] if d["retrieved_rank"] else "-"
        print(f"{d['question'][:43]:<44} {rank:>5}")
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser(description="Evaluate OmniRAG accuracy on your documents")
    ap.add_argument("--docs", required=True, help="Folder with documents to ingest")
    ap.add_argument("--questions", required=True, help="CSV with question,expected_answer,source_filename,keywords")
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--with-answers", action="store_true", help="Also generate and score answers (needs Ollama)")
    ap.add_argument("--judge", action="store_true", help="Use LLM-as-judge for answer quality (needs Ollama)")
    args = ap.parse_args()

    print("Ingesting documents...")
    ws_id = ingest_docs(args.docs)
    questions = load_questions(args.questions)
    print(f"Loaded {len(questions)} golden questions.\n")

    print("Scoring retrieval...")
    retrieval = score_retrieval(ws_id, questions, top_k=args.top_k)

    answers = None
    if args.with_answers:
        print("Generating answers (this can take a while on local models)...")
        answers = score_answers(ws_id, questions, use_ollama_judge=args.judge)

    print_report(retrieval, answers)

    out = HERE / "results.json"
    out.write_text(json.dumps({"retrieval": retrieval, "answers": answers}, indent=2), encoding="utf-8")
    print(f"Full details written to {out}")

    # Clean up the eval workspace so results aren't polluted next run.
    for f in memory.list_files(ws_id):
        vectorstore.delete_file_chunks(ws_id, f["file_id"])
        memory.delete_file(f["file_id"])


if __name__ == "__main__":
    main()
