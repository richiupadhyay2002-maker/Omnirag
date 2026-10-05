"""
OmniRAG FastAPI application.

Endpoints:
  POST   /workspaces                          create a workspace
  GET    /workspaces                          list workspaces
  POST   /workspaces/{ws_id}/files             upload a file (background-processed)
  GET    /workspaces/{ws_id}/files             list files + status
  DELETE /files/{file_id}                      remove a file and its vectors
  POST   /workspaces/{ws_id}/conversations     create a conversation
  GET    /workspaces/{ws_id}/conversations     list conversations
  PATCH  /conversations/{id}                   rename
  DELETE /conversations/{id}                   delete
  GET    /conversations/{id}/messages          full history
  POST   /chat/stream                          SSE streaming chat (the core RAG endpoint)
"""
import shutil
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app import memory
from app.models import ChatRequest, WorkspaceCreate
from app.ingestion import detect_file_type, load_file
from app.chunking import chunk_documents
from app import vectorstore
from app.rag import run_chat

app = FastAPI(title="OmniRAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- Workspaces
@app.post("/workspaces")
def create_workspace(body: WorkspaceCreate):
    return memory.create_workspace(body.name)


@app.get("/workspaces")
def get_workspaces():
    return memory.list_workspaces()


# ---------------------------------------------------------------- Files
def _process_file_background(file_id: str, path: str, filename: str, file_type: str, workspace_id: str):
    try:
        raw_docs = load_file(path, file_type)
        chunks = chunk_documents(raw_docs, file_type)
        n = vectorstore.add_chunks(workspace_id, file_id, filename, file_type, chunks)
        memory.update_file_status(file_id, "ready", num_chunks=n)
    except Exception as e:
        memory.update_file_status(file_id, "error", error_message=str(e))


@app.post("/workspaces/{ws_id}/files")
async def upload_file(ws_id: str, background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_type = detect_file_type(file.filename)
    if file_type == "unsupported":
        raise HTTPException(400, f"Unsupported file type: {file.filename}")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File exceeds max size of {settings.MAX_FILE_SIZE_MB}MB")

    rec = memory.add_file(ws_id, file.filename, file_type, len(contents))

    dest_dir = Path(settings.UPLOAD_DIR) / ws_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{rec['file_id']}_{file.filename}"
    with open(dest_path, "wb") as f:
        f.write(contents)

    background_tasks.add_task(
        _process_file_background, rec["file_id"], str(dest_path), file.filename, file_type, ws_id
    )
    return rec


@app.get("/workspaces/{ws_id}/files")
def get_files(ws_id: str):
    return memory.list_files(ws_id)


@app.delete("/files/{file_id}")
def remove_file(file_id: str):
    rec = memory.get_file(file_id)
    if not rec:
        raise HTTPException(404, "File not found")
    vectorstore.delete_file_chunks(rec["workspace_id"], file_id)
    memory.delete_file(file_id)

    dest_dir = Path(settings.UPLOAD_DIR) / rec["workspace_id"]
    for p in dest_dir.glob(f"{file_id}_*"):
        p.unlink(missing_ok=True)
    return {"status": "deleted"}


# ---------------------------------------------------------------- Conversations
@app.post("/workspaces/{ws_id}/conversations")
def create_conversation(ws_id: str):
    return memory.create_conversation(ws_id)


@app.get("/workspaces/{ws_id}/conversations")
def get_conversations(ws_id: str):
    return memory.list_conversations(ws_id)


@app.patch("/conversations/{conv_id}")
def rename(conv_id: str, title: str):
    memory.rename_conversation(conv_id, title)
    return {"status": "ok"}


@app.delete("/conversations/{conv_id}")
def remove_conversation(conv_id: str):
    memory.delete_conversation(conv_id)
    return {"status": "deleted"}


@app.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str):
    return memory.get_messages(conv_id)


# ---------------------------------------------------------------- Chat (RAG)
@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    conv_id = body.conversation_id
    if not conv_id:
        conv = memory.create_conversation(body.workspace_id)
        conv_id = conv["id"]

    def event_generator():
        for token in run_chat(body.workspace_id, conv_id, body.message, body.mode, file_ids=body.file_ids):
            yield {"event": "token", "data": token}
        yield {"event": "done", "data": conv_id}

    return EventSourceResponse(event_generator())


@app.get("/health")
def health():
    return {"status": "ok"}
