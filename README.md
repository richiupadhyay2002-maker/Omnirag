<div align="center">

# OmniRAG

### Universal Multimodal AI Knowledge Assistant

**Chat with your files — grounded, cited answers from a local LLM.**

Runs locally by default · no paid services required · optional Groq fallback is off by default

[![CI](https://github.com/richiupadhyay2002-maker/OmniRAG/actions/workflows/ci.yml/badge.svg)](https://github.com/richiupadhyay2002-maker/OmniRAG/actions/workflows/ci.yml)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white&style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black&style=flat-square)
![Vite](https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white&style=flat-square)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3-06B6D4?logo=tailwindcss&logoColor=white&style=flat-square)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector_store-F5A623?style=flat-square)
![Ollama](https://img.shields.io/badge/Ollama-local_LLM-ffffff?logo=ollama&logoColor=black&style=flat-square)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white&style=flat-square)

</div>

---

## Overview

**OmniRAG** turns everyday files — PDFs, PowerPoint (.pptx) decks, Word (.docx) documents, source code, CSV/Excel (.xlsx) spreadsheets, text/Markdown, and images — into a conversational knowledge base. Upload documents, ask questions in plain language, and receive **streaming answers with clickable citations** pointing to the exact page, slide, line, or row the answer came from.

The engineering focus of this project is the layer most RAG demos skip: **per-file-type ingestion that preserves provenance**. Every document type gets its own loader and chunking strategy, normalizing heterogeneous files into a common shape that carries source metadata. At query time, that metadata powers document-scoped retrieval, citations computed independently of generation, and a **grounded-only system prompt** that instructs the model to answer only from retrieved context — or state that the answer wasn't found.

Everything runs on your machine by default: local embeddings (sentence-transformers), an on-disk vector database (ChromaDB), and a local LLM served by Ollama. An optional free-tier Groq fallback exists but is **off by default** (`LLM_PROVIDER=ollama`); enabling it sends queries to a third-party API.

## Screenshots

<p align="center">
  <img src="docs/screenshots/chat-ui.png" alt="OmniRAG chat interface with knowledge files and grounded answer" width="860">
  <br>
  <em>Chat interface — knowledge-file cards, conversation history, and streaming grounded answers</em>
</p>

<p align="center">
  <img src="docs/screenshots/landing-hero.png" alt="OmniRAG landing page hero — headline, upload dropzone, and feature highlights" width="860">
  <br>
  <em>Landing page — headline, drag-and-drop upload, and supported file types</em>
</p>

## Key features

### 🧠 Retrieval & grounding

- **Per-type ingestion pipelines** — PyMuPDF (PDF), python-docx (.docx), python-pptx (.pptx), pandas/openpyxl (.csv/.xlsx), plain text/Markdown, source code (19 file extensions), and Tesseract OCR for images — each chunk tagged with page / slide / line / row provenance. Legacy .doc/.ppt/.xls files are not supported.
- **Content-aware chunking** — per-file-type chunk sizes; source code is split on function/class boundaries found with lightweight regexes (tuned for Python, Java/C#, JS/TS, C/C++ and SQL), not a full parser.
- **Local embeddings & vector search** — `all-MiniLM-L6-v2` (384-d) into ChromaDB, organized as per-workspace collections; retrieval can be filtered by `file_id` (the "Ask about" chips).
- **Hybrid retrieval** — dense vector search candidates are combined with BM25 lexical matches and reranked, improving exact-term retrieval without an additional service or package.
- **Grounded-only prompting** — the system prompt instructs the model to answer only from retrieved context and to reply "I couldn't find this in the uploaded files" otherwise. This is prompt-level guidance, not a separate verification step.
- **Citations computed independently of generation** — every answer links file, location, snippet, and relevance score.

### 💬 Chat experience

- **Streaming responses** over Server-Sent Events (read with `fetch` streaming, since the chat request is a POST), with markdown and syntax-highlighted code rendering.
- **Document-scoped chat** — "Ask about" chips filter retrieval to selected files, so answers respect exactly the documents you choose.
- **Six response modes** — Default, Simple, Deep, Exam, Code, Research.
- **Conversation management** — create, rename, delete, persisted history with automatic titles.
- **Shareable links** — a URL (`?w=…&c=…`) restores the workspace and conversation for anyone who can reach the same backend (there is no authentication).
- **Polished React UI** — dark theme, drag-and-drop upload, file cards, and citation cards.

### 🖼️ Multimodal

- **Image files are first-class knowledge** — OCR extracts embedded text, and raw pixels are passed to a local vision model (`llava`) at query time, so diagrams and screenshots are answerable like any document.

### ⚙️ Engineering & operations

- **Local by default** — no paid APIs; optional Groq fallback.
- **Docker Compose** for backend + frontend (Ollama runs on the host).
- **Tests and evaluation harness** — pytest suites (run in CI) plus an evaluation script measuring retrieval (Recall@k, MRR) and, when Ollama is available, answer quality with RAGAS.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18 · Vite 5 · Tailwind CSS 3 · react-markdown · react-syntax-highlighter · lucide-react |
| **Backend / API** | FastAPI 0.115 · Uvicorn · SSE streaming (sse-starlette) · Pydantic v2 |
| **Retrieval** | sentence-transformers (`all-MiniLM-L6-v2`) · BM25 hybrid reranking · ChromaDB (on-disk, per-workspace) |
| **Generation** | Ollama local LLMs (`llama3.1:8b`; vision: `llava:7b`) · optional Groq free tier |
| **File processing** | PyMuPDF · python-docx · python-pptx · pandas · openpyxl · Pillow · Tesseract OCR |
| **Quality** | pytest · RAGAS evaluation harness |
| **Tooling** | Docker & docker-compose · Git |

## Architecture

```
┌──────────────────────────┐        ┌───────────────────────────────────────┐
│  React + Vite + Tailwind │  HTTP  │           FastAPI backend             │
│  (chat UI, upload UI)    │◄──────►│                                       │
└──────────────────────────┘  SSE   │  ingestion/  (per-file-type loaders)  │
                                    │  chunking.py (content-aware splitting)│
                                    │  embeddings.py (sentence-transformers)│
                                    │  vectorstore.py (Chroma, per-workspace│
                                    │  rag.py (retrieval + grounded prompt) │
                                    │  llm.py (Ollama / Groq streaming)     │
                                    │  memory.py (workspaces/files/chats)   │
                                    └───────────────────────────────────────┘
```

**Request flow for a chat message:**

1. The frontend `POST`s the question to `/chat/stream`.
2. The question is embedded and matched against Chroma for the top-k chunks — optionally filtered to the files you selected.
3. Retrieved chunks form a context block, each tagged with its source location (page / slide / line / row).
4. A grounded system prompt instructs the LLM to answer **only** from that context — or state the answer wasn't found.
5. Tokens stream to the UI over SSE, and citations are rendered alongside the answer from the same retrieval results.

## Getting started

### Prerequisites

- **Python 3.11**
- **Node.js 18+** (CI and the Docker image use Node 20)
- **[Ollama](https://ollama.com)** with `llama3.1:8b` (add `llava:7b` for image Q&A)
- *Optional:* [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for scanned documents and images
- *Optional:* Docker, if you prefer containers

### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # defaults work for local Ollama
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                     # → http://localhost:5173
```

### 3. Local LLM

```bash
ollama serve
ollama pull llama3.1:8b
ollama pull llava:7b            # optional — image understanding
```

Configuration lives in `backend/.env` — every key (LLM provider, model names, embedding model, Chroma path, upload limits, CORS origins) is documented in `.env.example`.

### Docker (alternative)

```bash
docker compose up --build       # backend :8000, frontend :5173
```

Compose runs the backend and the Vite **development** server; it does not build a production frontend bundle. Ollama is expected on the host (`ollama serve`, reached via `host.docker.internal:11434`) — uncomment the `ollama` service in `docker-compose.yml` to run it in a container instead.

## Testing & evaluation

```bash
cd backend
pytest                          # unit & integration suites
python -m tests.eval_rag        # RAG quality harness (golden set)
```

The evaluation harness runs a 15-question golden set and reports **Recall@k** and **MRR** for dense-only and hybrid retrieval. Thirteen questions have an expected source filename; two no-source questions are excluded from retrieval metrics. When Ollama is available, generated answers can also be scored with keyword checks, a lightweight judge, and **RAGAS** (faithfulness, answer relevancy, context precision, and context recall).

### Sample retrieval comparison

Measured on the checked-in fixture documents and golden questions (`k=8`):

| Retriever | Recall@8 | MRR |
|---|---:|---:|
| Before: pure-Python TF-IDF fallback | 1.0000 | 0.9423 |
| After: TF-IDF + BM25 reranking | 1.0000 | 0.9487 |

This run used the evaluation harness's explicitly labeled TF-IDF fallback (not the sentence-transformer embeddings); 13 questions with expected source filenames were scored and the 2 no-source questions were excluded from Recall@8 and MRR.

### Sample RAGAS answer-quality check

Measured on the first three factual questions in the golden set, using the local Ollama `llama3:latest` judge and `nomic-embed-text` embeddings:

| RAGAS metric | Score | Questions |
|---|---:|---:|
| Faithfulness | 1.0000 | 3 |
| Answer relevancy | 0.9539 | 3 |
| Context precision | 0.9000 | 3 |
| Context recall | 1.0000 | 3 |

All three generated answers passed the harness's keyword check. These are measured sample results, not a full-set estimate: answer generation used the explicitly labeled TF-IDF + BM25 fallback because sentence-transformer embeddings were unavailable in this environment.

Reproduce the retrieval comparison with:

```bash
cd backend
python -m tests.eval_rag --docs tests/eval_data/docs --questions tests/eval_data/golden_questions.csv
```

To collect answer and RAGAS metrics, install `backend/requirements.txt`, start Ollama, pull the configured chat model and the `nomic-embed-text` embedding model (or set `OLLAMA_EMBEDDING_MODEL` to another Ollama embedding model), and run:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
cd backend
python -m tests.eval_rag --docs tests/eval_data/docs --questions tests/eval_data/golden_questions.csv --with-answers --judge ragas
```

Full per-question output is written to `backend/eval/results.json`, which is intentionally gitignored because evaluation data can contain private document content.

## Project structure

```
OmniRAG/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app & routes
│   │   ├── ingestion/          # per-file-type loaders (pdf, docx, pptx, code, csv, images)
│   │   ├── chunking.py         # content-aware splitting
│   │   ├── embeddings.py       # sentence-transformers
│   │   ├── vectorstore.py      # Chroma, per-workspace collections
│   │   ├── rag.py              # retrieval + grounded prompting
│   │   ├── llm.py              # Ollama / Groq streaming
│   │   └── memory.py           # workspaces, files, conversations
│   ├── tests/                  # pytest suites, eval harness (eval_rag.py) and eval_data/
│   └── requirements.txt
├── frontend/
│   └── src/                    # React app (chat, upload, citations, sidebar)
├── docs/screenshots/           # README imagery
├── docker-compose.yml
└── README.md
```

## Security and privacy

- **Data stays local by default.** Embeddings (sentence-transformers), the
  vector store (ChromaDB, on-disk under `backend/data/`), uploaded files, and
  generation (Ollama) all run on your machine — nothing leaves it unless you
  enable the optional Groq fallback.
- **Never commit `.env` or uploads.** Real API keys, `backend/data/`,
  `*.sqlite3` / `*.db` files, eval outputs (`backend/eval/results.json`), and
  IDE settings are gitignored. Copy `backend/.env.example` to `backend/.env`
  and keep secrets local. See [SECURITY.md](SECURITY.md) for how to report
  vulnerabilities.
- **Groq fallback is optional and off by default** (`LLM_PROVIDER=ollama`).
  Setting `LLM_PROVIDER=groq` sends your queries and retrieved context to
  Groq's third-party API — only enable it deliberately with your own key.

## Roadmap

Hybrid **BM25 + vector** retrieval with lightweight reranking is implemented. Remaining roadmap: cross-encoder reranking, LangGraph multi-agent workflows, tree-sitter AST-level code parsing, legacy Office formats (.doc/.ppt/.xls), authentication & multi-user workspaces, and cloud deployment.

---

<div align="center">

**Richi Upadhyay**

[email](mailto:richiupadhyay2002@gmail.com) · [GitHub @richiupadhyay2002-maker](https://github.com/richiupadhyay2002-maker)

If you find this project valuable, a ⭐ star would be greatly appreciated.

</div>
