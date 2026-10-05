"""Shared pydantic schemas for API requests/responses."""
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class FileMeta(BaseModel):
    file_id: str
    filename: str
    file_type: str            # pdf | docx | pptx | txt | code | csv | xlsx | image
    size_bytes: int
    status: Literal["processing", "ready", "error"]
    error_message: Optional[str] = None
    num_chunks: int = 0
    uploaded_at: datetime
    workspace_id: str


class Citation(BaseModel):
    file_id: str
    filename: str
    file_type: str
    location: str              # e.g. "page 4", "slide 12", "line 45-60", "image"
    snippet: str
    score: float


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation] = []
    created_at: datetime


class ChatRequest(BaseModel):
    workspace_id: str
    conversation_id: Optional[str] = None
    message: str
    mode: Literal["default", "simple", "deep", "exam", "code", "research"] = "default"
    # Optional per-document retrieval scope: when provided, only these files are
    # searched. None (omitted) = search the whole workspace — exactly what
    # pre-file_ids clients send, so the default behavior is unchanged.
    file_ids: Optional[list[str]] = None


class ConversationSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: datetime
    workspace_id: str


class WorkspaceCreate(BaseModel):
    name: str
