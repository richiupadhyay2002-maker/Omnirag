"""Shared pytest options for the OmniRAG eval harness (tests/eval_rag.py).

pytest only calls pytest_addoption in conftest.py / plugins, so the
--eval-* flags live here. Defaults point at the bundled golden set so
`pytest tests/eval_rag.py` works with zero flags.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DOCS = str(HERE / "eval_data" / "docs")
DEFAULT_QUESTIONS = str(HERE / "eval_data" / "golden_questions.csv")


def pytest_addoption(parser):
    g = parser.getgroup("eval", "OmniRAG RAG evaluation harness")
    g.addoption("--eval-docs", action="store", default=DEFAULT_DOCS)
    g.addoption("--eval-questions", action="store", default=DEFAULT_QUESTIONS)
    g.addoption("--eval-top-k", action="store", type=int, default=8)
    g.addoption("--eval-with-answers", action="store_true", default=False,
                help="Also generate answers (needs Ollama running).")
    g.addoption("--eval-judge", action="store", default="none",
                choices=["none", "lightweight", "ragas"])
    g.addoption("--eval-fail-under", action="store", type=float, default=0.0,
                help="Fail if recall@k below this threshold (e.g. 0.7).")
