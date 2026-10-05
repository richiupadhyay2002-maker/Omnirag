"""Tests for the optional per-document chat scope (ChatRequest.file_ids).

Covers the additive `file_ids` field end-to-end: schema default (backward
compatibility with clients that never send it) and forwarding into run_chat().

Importing the FastAPI app pulls the full backend stack (sse_starlette, ollama,
...), so the module is imported here — before other test modules run — and the
whole module skips cleanly if a lean environment is missing those deps.
"""
from unittest.mock import patch

import pytest

from app.models import ChatRequest

main_module = pytest.importorskip(
    "app.main", reason="full backend stack (sse_starlette, ollama, ...) not installed"
)
fastapi_app = main_module.app


@pytest.fixture(autouse=True)
def _reset_sse_exit_event():
    """sse_starlette caches an anyio.Event bound to the first event loop.

    TestClient uses a fresh loop per request, so reset the cache around every
    test to avoid "bound to a different event loop" RuntimeErrors.
    """
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


class TestChatRequestSchema:
    def test_omitted_file_ids_defaults_to_none(self):
        """Old clients that never send file_ids must keep working unchanged."""
        req = ChatRequest(workspace_id="ws-1", message="hello")
        assert req.file_ids is None

    def test_file_ids_accepts_list(self):
        req = ChatRequest(workspace_id="ws-1", message="hello", file_ids=["f-1", "f-2"])
        assert req.file_ids == ["f-1", "f-2"]

    def test_default_payload_keeps_existing_fields(self):
        req = ChatRequest(workspace_id="ws-1", message="hi", mode="simple")
        payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
        assert payload["file_ids"] is None
        assert payload["mode"] == "simple"
        assert payload["message"] == "hi"


class TestChatStreamForwarding:
    """POST /chat/stream must forward body.file_ids into run_chat()."""

    def _post(self, payload):
        from fastapi.testclient import TestClient

        captured = {}

        def fake_run_chat(workspace_id, conversation_id, question, mode, file_ids=None):
            captured["file_ids"] = file_ids
            yield "ok"

        with patch.object(main_module, "run_chat", fake_run_chat):
            resp = TestClient(fastapi_app).post("/chat/stream", json=payload)
        return resp, captured

    def test_forwards_file_ids_when_provided(self):
        resp, captured = self._post(
            {
                "workspace_id": "ws-1",
                "conversation_id": "conv-1",
                "message": "what does the paper say?",
                "file_ids": ["file-a"],
            }
        )
        assert resp.status_code == 200
        assert captured["file_ids"] == ["file-a"]

    def test_passes_none_when_omitted(self):
        resp, captured = self._post(
            {"workspace_id": "ws-1", "conversation_id": "conv-1", "message": "hi"}
        )
        assert resp.status_code == 200
        assert captured["file_ids"] is None