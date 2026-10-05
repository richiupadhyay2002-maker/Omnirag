"""
Unit tests for the image boost logic in app.vectorstore.query.

Run with: python -m pytest -v (from backend/)
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Stub the app package before importing vectorstore, so app.config's
# side-effect (creating dirs) is bypassed and we can patch chromadb cleanly.
_app = types.ModuleType("app")
_app.__path__ = [str(Path(__file__).resolve().parents[1] / "app")]
sys.modules["app"] = _app

# Stub heavy/unavailable deps before vectorstore (via embeddings) imports them.
# torch is blocked by a Windows Application Control policy on this machine, so
# sentence_transformers must be faked rather than imported.
_sent_st = types.ModuleType("sentence_transformers")
_sent_st.SentenceTransformer = MagicMock
torch = types.ModuleType("torch")
sys.modules["sentence_transformers"] = _sent_st
sys.modules["torch"] = torch

_spec = importlib.util.spec_from_file_location(
    "app.config", Path(__file__).resolve().parents[1] / "app" / "config.py"
)
config = importlib.util.module_from_spec(_spec)
sys.modules["app.config"] = config
_spec.loader.exec_module(config)

_spec_vs = importlib.util.spec_from_file_location(
    "app.vectorstore", Path(__file__).resolve().parents[1] / "app" / "vectorstore.py"
)
# Load vectorstore with chromadb + embeddings mocked at import time.
with patch("chromadb.PersistentClient") as _pc, \
     patch("app.embeddings.embed_texts"), \
     patch("app.embeddings.embed_query"):
    vectorstore = importlib.util.module_from_spec(_spec_vs)
    sys.modules["app.vectorstore"] = vectorstore
    _spec_vs.loader.exec_module(vectorstore)

IMAGE_BOOST = 0.15


def _make_col_result(docs, metas, dists):
    return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def _make_col(n_total, query_result):
    col = MagicMock()
    col.count.return_value = n_total
    col.query.return_value = query_result
    return col


class TestImageBoost:
    def _run_query(self, col, top_k=8):
        with patch.object(vectorstore, "_collection", return_value=col), \
             patch.object(vectorstore, "embed_query", return_value=[0.0]):
            return vectorstore.query("ws", "explain the diagram", top_k=top_k)

    def test_image_chunk_gets_boosted_score(self):
        col = _make_col(2, _make_col_result(
            ["some text", "chart labels"],
            [{"file_id": "a", "filename": "doc.pdf", "file_type": "pdf"},
             {"file_id": "b", "filename": "graph.png", "file_type": "image",
              "image_path": "uploads/graph.png"}],
            [0.1, 0.2],
        ))
        hits = self._run_query(col)
        scores = {h["filename"]: h["score"] for h in hits}
        # image score = (1 - 0.2) + 0.15 = 0.95
        assert scores["graph.png"] == round((1 - 0.2) + IMAGE_BOOST, 4)

    def test_text_chunk_score_unchanged(self):
        col = _make_col(1, _make_col_result(
            ["plain paragraph"],
            [{"file_id": "a", "filename": "doc.pdf", "file_type": "pdf"}],
            [0.3],
        ))
        hits = self._run_query(col)
        assert hits[0]["score"] == 0.7  # no boost applied

    def test_boost_promotes_image_above_weaker_text(self):
        # image at dist 0.45 (score 0.55) vs text at dist 0.42 (score 0.58)
        col = _make_col(2, _make_col_result(
            ["text chunk", "image chunk"],
            [{"file_id": "a", "filename": "doc.pdf", "file_type": "pdf"},
             {"file_id": "b", "filename": "graph.png", "file_type": "image",
              "image_path": "uploads/graph.png"}],
            [0.42, 0.45],
        ))
        hits = self._run_query(col)
        assert hits[0]["filename"] == "graph.png"  # 0.70 > 0.58

    def test_very_relevant_text_still_beats_weak_image(self):
        # text at dist 0.05 (score 0.95) vs image at dist 0.5 (score 0.65 after boost)
        col = _make_col(2, _make_col_result(
            ["highly relevant text", "irrelevant image"],
            [{"file_id": "a", "filename": "doc.pdf", "file_type": "pdf"},
             {"file_id": "b", "filename": "graph.png", "file_type": "image",
              "image_path": "uploads/graph.png"}],
            [0.05, 0.5],
        ))
        hits = self._run_query(col)
        assert hits[0]["filename"] == "doc.pdf"

    def test_top_k_limit_still_respected(self):
        n = 10
        col = _make_col(n, _make_col_result(
            [f"doc {i}" for i in range(n)],
            [{"file_id": str(i), "filename": f"f{i}.txt", "file_type": "text"} for i in range(n)],
            [0.1 * i for i in range(n)],
        ))
        hits = self._run_query(col, top_k=3)
        assert len(hits) == 3

    def test_boosted_image_inside_top_k_window(self):
        # image sits just outside plain top_k (rank 4 of 4 with top_k=2),
        # boost should promote it into the returned 2.
        col = _make_col(4, _make_col_result(
            ["t1", "t2", "t3", "img"],
            [{"file_id": str(i), "filename": f"f{i}.txt", "file_type": "text"} for i in range(3)]
            + [{"file_id": "x", "filename": "diagram.png", "file_type": "image",
                "image_path": "uploads/diagram.png"}],
            [0.10, 0.12, 0.14, 0.16],
        ))
        hits = self._run_query(col, top_k=2)
        names = [h["filename"] for h in hits]
        assert "diagram.png" in names  # 0.84 + 0.15 = 0.99 beats 0.90

    def test_empty_collection_returns_no_hits(self):
        col = MagicMock()
        col.count.return_value = 0
        with patch.object(vectorstore, "_collection", return_value=col):
            assert vectorstore.query("ws", "q") == []

    def test_file_ids_filter_passed_to_chroma(self):
        col = _make_col(1, _make_col_result(
            ["x"], [{"file_id": "only-this", "filename": "a.pdf", "file_type": "pdf"}], [0.1]))
        with patch.object(vectorstore, "_collection", return_value=col), \
             patch.object(vectorstore, "embed_query", return_value=[0.0]):
            vectorstore.query("ws", "q", file_ids=["only-this"])
        assert col.query.call_args.kwargs["where"] == {"file_id": {"$in": ["only-this"]}}
