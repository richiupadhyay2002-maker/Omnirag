"""
Lightweight persistence layer for workspaces, files, and conversations.

Uses a local JSON file as a zero-dependency, zero-cost "database". This keeps
the project runnable with $0 and no external services. Swap this module for
a real SQLite/Postgres layer later without touching the rest of the app —
every function here is the only place that touches storage.
"""
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

_LOCK = threading.Lock()
_DB_PATH = Path("./data/db.json")
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not _DB_PATH.exists():
        return {"workspaces": {}, "files": {}, "conversations": {}, "messages": {}}
    with open(_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(db: dict) -> None:
    with open(_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, default=str)


def create_workspace(name: str) -> dict:
    with _LOCK:
        db = _load()
        ws_id = str(uuid.uuid4())
        ws = {"id": ws_id, "name": name, "created_at": _now()}
        db["workspaces"][ws_id] = ws
        _save(db)
        return ws


def list_workspaces() -> list[dict]:
    return list(_load()["workspaces"].values())


def add_file(workspace_id: str, filename: str, file_type: str, size_bytes: int) -> dict:
    with _LOCK:
        db = _load()
        file_id = str(uuid.uuid4())
        rec = {
            "file_id": file_id,
            "workspace_id": workspace_id,
            "filename": filename,
            "file_type": file_type,
            "size_bytes": size_bytes,
            "status": "processing",
            "error_message": None,
            "num_chunks": 0,
            "uploaded_at": _now(),
        }
        db["files"][file_id] = rec
        _save(db)
        return rec


def update_file_status(file_id: str, status: str, num_chunks: int = 0, error_message: Optional[str] = None):
    with _LOCK:
        db = _load()
        if file_id in db["files"]:
            db["files"][file_id]["status"] = status
            db["files"][file_id]["num_chunks"] = num_chunks
            db["files"][file_id]["error_message"] = error_message
            _save(db)


def list_files(workspace_id: str) -> list[dict]:
    db = _load()
    return [f for f in db["files"].values() if f["workspace_id"] == workspace_id]


def delete_file(file_id: str):
    with _LOCK:
        db = _load()
        db["files"].pop(file_id, None)
        _save(db)


def get_file(file_id: str) -> Optional[dict]:
    return _load()["files"].get(file_id)


def create_conversation(workspace_id: str, title: str = "New chat") -> dict:
    with _LOCK:
        db = _load()
        conv_id = str(uuid.uuid4())
        conv = {"id": conv_id, "workspace_id": workspace_id, "title": title, "updated_at": _now()}
        db["conversations"][conv_id] = conv
        db["messages"][conv_id] = []
        _save(db)
        return conv


def list_conversations(workspace_id: str) -> list[dict]:
    db = _load()
    convs = [c for c in db["conversations"].values() if c["workspace_id"] == workspace_id]
    return sorted(convs, key=lambda c: c["updated_at"], reverse=True)


def rename_conversation(conversation_id: str, title: str):
    with _LOCK:
        db = _load()
        if conversation_id in db["conversations"]:
            db["conversations"][conversation_id]["title"] = title
            _save(db)


def delete_conversation(conversation_id: str):
    with _LOCK:
        db = _load()
        db["conversations"].pop(conversation_id, None)
        db["messages"].pop(conversation_id, None)
        _save(db)


def add_message(conversation_id: str, role: str, content: str, citations: list[dict] | None = None):
    with _LOCK:
        db = _load()
        msg = {"role": role, "content": content, "citations": citations or [], "created_at": _now()}
        db["messages"].setdefault(conversation_id, []).append(msg)
        if conversation_id in db["conversations"]:
            db["conversations"][conversation_id]["updated_at"] = _now()
            # Auto-title from first user message
            if role == "user" and db["conversations"][conversation_id]["title"] == "New chat":
                db["conversations"][conversation_id]["title"] = content[:48] + ("..." if len(content) > 48 else "")
        _save(db)
        return msg


def get_messages(conversation_id: str) -> list[dict]:
    return _load()["messages"].get(conversation_id, [])
