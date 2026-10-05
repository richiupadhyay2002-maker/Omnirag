"""
Unit tests for the pure scoring logic in tests/eval_rag.py.

These run WITHOUT torch / embeddings / Ollama (all heavy I/O is mocked),
so they validate the harness itself on machines where torch is blocked.
Run: python -m pytest tests/test_eval_harness.py -v (from backend/)
"""
import csv
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stub heavy optional deps so importing eval_rag never touches torch.
for _name in ["torch", "sentence_transformers", "chromadb", "ragas",
              "datasets", "langchain_ollama", "ollama"]:
    if _name not in sys.modules:
        sys.modules[_name] = MagicMock()

import tests.eval_rag as ev


@pytest.fixture()
def golden_path(tmp_path):
    p = tmp_path / "golden.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question", "expected_answer", "source_filename",
                    "keywords", "category", "difficulty"])
        w.writerow(["What is X?", "X is 42", "a.txt", "42|x", "factual", "easy"])
        w.writerow(["Unknown thing?", "I couldn't find this in the uploaded files",
                    "", "", "unanswerable", "medium"])
    return p


class TestLoadQuestions:
    def test_new_schema(self, golden_path):
        qs = ev.load_questions(golden_path)
        assert len(qs) == 2
        assert qs[0]["keywords"] == ["42", "x"]
        assert qs[1]["category"] == "unanswerable"

    def test_old_4col_csv_still_works(self, tmp_path):
        p = tmp_path / "old.csv"
        p.write_text("question,expected_answer,source_filename,keywords\n"
                     '"What is Paris?","Paris","a.txt","paris"\n', encoding="utf-8")
        qs = ev.load_questions(p)
        assert qs[0]["category"] == "factual"
        assert qs[0]["keywords"] == ["paris"]

    def test_bundled_golden_set_loads(self):
        qs = ev.load_questions(ev.DEFAULT_QUESTIONS)
        assert len(qs) >= 10
        assert {"factual", "unanswerable"} <= {q["category"] for q in qs}
class TestKeywordAccuracy:
    def _row(self, **kw):
        base = {"question": "q", "ground_truth": "Paris",
                "answer": "The answer is Paris.", "contexts": ["ctx"],
                "citations": [{}, {}], "category": "factual",
                "keywords": ["paris"], "latency_s": 0.1}
        base.update(kw)
        return base

    def test_keyword_hit(self):
        out = ev.score_keyword_accuracy([self._row()])
        assert out["keyword_accuracy"] == 1.0
        assert out["details"][0]["keyword_pass"] is True

    def test_keyword_miss(self):
        out = ev.score_keyword_accuracy([self._row(answer="No idea.")])
        assert out["keyword_accuracy"] == 0.0

    def test_unanswerable_requires_not_found_reply(self):
        ok = self._row(category="unanswerable", keywords=[], answer=(
            "I couldn't find this in the uploaded files. Try rephrasing."))
        bad = self._row(category="unanswerable", keywords=[],
                        answer="Paris is the capital.")
        out = ev.score_keyword_accuracy([ok, bad])
        assert out["details"][0]["keyword_pass"] is True
        assert out["details"][1]["keyword_pass"] is False
        assert out["keyword_accuracy"] == 0.5


class TestRetrievalScoringMocked:
    def _qs(self):
        return [
            {"question": "q1", "source_filename": "a.txt", "category": "factual"},
            {"question": "q2", "source_filename": "b.txt", "category": "factual"},
            {"question": "q3", "source_filename": "", "category": "unanswerable"},
        ]

    def test_recall_mrr_and_unanswerable_excluded(self):
        fake_vs = types.SimpleNamespace(
            query=MagicMock(side_effect=[
                [{"filename": "a.txt"}, {"filename": "x.txt"}],
                [{"filename": "x.txt"}, {"filename": "b.txt"}],
                [{"filename": "z.txt"}],
            ]))
        with patch.object(ev, "_app_modules",
                          return_value=(None, None, None, fake_vs, None, None)):
            ret = ev.score_retrieval("ws", self._qs(), top_k=8)
        assert ret["recall_at_k"] == 1.0
        assert ret["mrr"] == pytest.approx((1.0 + 0.5) / 2)
        assert ret["num_unanswerable_excluded"] == 1
        assert ret["details"][2]["excluded_from_recall"] is True

    def test_miss_scores_zero(self):
        fake_vs = types.SimpleNamespace(
            query=MagicMock(return_value=[{"filename": "nope.txt"}]))
        with patch.object(ev, "_app_modules",
                          return_value=(None, None, None, fake_vs, None, None)):
            ret = ev.score_retrieval(
                "ws", [{"question": "q", "source_filename": "a.txt",
                        "category": "factual"}], top_k=8)
        assert ret["recall_at_k"] == 0.0
        assert ret["mrr"] == 0.0
class TestLightweightJudge:
    def test_routes_through_app_llm(self):
        with patch("app.llm.generate_stream", return_value=iter([" 4 "])) as gs:
            assert ev.lightweight_judge("q", "ref", "ans") == 4.0
            assert gs.called

    def test_warning_text_returns_none(self):
        with patch("app.llm.generate_stream",
                   return_value=iter(["\u26a0\ufe0f Could not reach Ollama"])):
            assert ev.lightweight_judge("q", "ref", "ans") is None


class TestRagasGuards:
    def test_missing_ragas_raises_helpful_import_error(self):
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name in ("datasets", "ragas"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *a, **k)

        rows = [{"question": "q", "ground_truth": "g", "answer": "a",
                 "contexts": ["c"], "category": "factual"}]
        with patch("builtins.__import__", side_effect=fake_import):
            with pytest.raises(ImportError, match="Ragas not installed"):
                ev.score_ragas(rows)

    def test_no_usable_rows_raises(self):
        # Empty answers/contexts -> RuntimeError raised BEFORE any ragas import
        # is attempted (no usable rows to score).
        with pytest.raises(RuntimeError, match="No usable"):
            ev.score_ragas([{"question": "q", "ground_truth": "g",
                             "answer": "", "contexts": [],
                             "category": "factual"}])