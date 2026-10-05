# OmniRAG — Universal Multimodal AI Knowledge Assistant

Chat with almost any file — PDF, DOCX, PPTX, TXT, source code, CSV/Excel, and
images — with grounded, cited answers. Runs entirely on your machine at **$0**
using local embeddings, a local vector database, and a local LLM (Ollama).

---

## 1. What's included in this build

| Layer | What's built | Status |
|---|---|---|
| File upload + type detection | PDF, DOCX, PPTX, TXT/MD, code (13+ languages), CSV/XLSX, images | ✅ Working |
| Ingestion pipelines | Per-type extraction with citation metadata (page/slide/line/row) | ✅ Working |
| Chunking | Content-aware, per-type chunk sizes, boundary-aware for code | ✅ Working |
| Embeddings | Local, free — `sentence-transformers` (all-MiniLM-L6-v2) | ✅ Working |
| Vector store | Chroma, on-disk, per-workspace collections, metadata filtering | ✅ Working |
| Retrieval | Similarity search + metadata filters (cross-file, single-file) | ✅ Working |
| Generation | Ollama local LLM, streaming; optional Groq free-tier fallback | ✅ Working |
| Hallucination guard | System prompt forces "not found" behavior + grounded-only answers | ✅ Working |
| Citations | File + page/slide/line/row, snippet, relevance score, per-answer | ✅ Working |
| Per-document chat scope | "Ask about" chips filter retrieval to selected files (`file_ids` metadata filter) | ✅ Working |
| Shareable links | `?w=…&c=…` URL restores workspace + conversation on load | ✅ Working |
| Conversations | New/rename/delete, persisted history, auto-titling | ✅ Working |
| Modes | Default / Simple / Deep / Exam / Code / Research | ✅ Working |
| Frontend | React + Vite + Tailwind, streaming chat, markdown+code rendering, dark mode, drag-and-drop, file cards, citation cards | ✅ Working |
| Vision (diagrams/screenshots) | OCR text extraction + raw image passed to a local vision model (llava) at query time | ✅ Working |
| Reranking, hybrid (BM25+vector) search, LangGraph multi-agent workflows, tree-sitter AST code parsing, RAG evaluation harness, auth, cloud deploy | Architected for, not implemented in this pass | 🧩 Extend (see §7) |

Everything above the "Extend" line is real, runnable code — not pseudocode.
Section 7 tells you exactly where to plug in the more advanced pieces later
without rewriting anything.

---

## 2. Architecture

```
┌─────────────────────────┐        ┌───────────────────────────────────────┐
│   React + Vite + Tailwind│  HTTP  │              FastAPI backend            │
│   (chat UI, upload UI)   │◄──────►│                                         │
└─────────────────────────┘  SSE    │  ingestion/  (per-file-type loaders)   │
                                     │  chunking.py (content-aware splitting) │
                                     │  embeddings.py (sentence-transformers) │
                                     │  vectorstore.py (Chroma, per-workspace)│
                                     │  rag.py (retrieval + grounded prompt)  │
                                     │  llm.py (Ollama / Groq)                │
                                     │  memory.py (workspaces/files/chats)    │
                                     └───────────────────────────────────────┘
```

**Request flow for a chat message:**
1. Frontend POSTs the question to `/chat/stream`.
2. `rag.py` embeds the question and queries Chroma for the top-k most similar
   chunks in that workspace (optionally filtered to specific files).
3. Retrieved chunks are assembled into a context block, each tagged with its
   source file + location (page/slide/line/row).
4. A system prompt forces the LLM to answer **only** from that context and to
   say "I couldn't find this in the uploaded files" if it's not there.
5. Ollama streams the answer token-by-token over Server-Sent Events; the UI
   renders it live as markdown with syntax-highlighted code.
6. Citations (file, location, snippet, score) are sent back and rendered as
   expandable source cards.

**Request flow for a file upload:**
1. File is saved to disk, a DB record is created with `status: processing`.
2. A background task detects file type → runs the matching loader → chunks →
   embeds → stores vectors in that workspace's Chroma collection → marks
   `status: ready` (or `error` with a message).
3. The frontend polls file status every 2s while anything is processing.

---

## 3. Windows + VS Code setup (step by step)

### 3.1 Prerequisites
- **Python 3.11** (https://python.org — check "Add to PATH" during install)
- **Node.js 20 LTS** (https://nodejs.org)
- **Ollama** (https://ollama.com/download) — this is your free, local LLM engine
- **Tesseract OCR** (only needed for text-in-images):
  https://github.com/UB-Mannheim/tesseract-ocr/wiki → install → note the path
  (usually `C:\Program Files\Tesseract-OCR\tesseract.exe`)
- **VS Code** with the Python and ES7+ React extensions (optional but nice)

### 3.2 Pull the local models (one-time, free)
Open a terminal:
```bash
ollama pull llama3.1:8b
ollama pull llava:7b
```
> If your machine is low-spec, swap `llama3.1:8b` for `llama3.2:3b` or
> `phi3:mini` in `.env` — smaller, faster, still free.

Make sure Ollama is running (it usually starts automatically; otherwise run
`ollama serve` in a terminal and leave it open).

### 3.3 Backend setup
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env
```
Open `.env` and, if Tesseract isn't on your PATH, set:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```
Run the backend:
```bash
uvicorn app.main:app --reload --port 8000
```
You should see: `Uvicorn running on http://127.0.0.1:8000`.
Visit `http://localhost:8000/health` → should return `{"status":"ok"}`.

### 3.4 Frontend setup
Open a **second** terminal:
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```
Visit `http://localhost:5173` — you should see the OmniRAG landing page.

### 3.5 Try it
1. Drag a PDF onto the upload area.
2. Wait for its card to show a green checkmark ("ready").
3. Ask: *"Summarize this document"* — you should see a streaming answer with
   an expandable "Sources" section showing the page number(s) used.
4. The URL always carries `?w=<workspace>&c=<conversation>` — copy it to
   bookmark or share the exact chat; reopening it restores that workspace and
   its full conversation history (same backend/data only).
5. With 2+ files ready, use the **Ask about** chips above the composer to scope
   a question to a single document ("All files" is the default).

---

## 4. Project tree

```
omnirag/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes
│   │   ├── config.py          # env-driven settings
│   │   ├── models.py          # pydantic schemas
│   │   ├── memory.py          # workspaces/files/conversations storage
│   │   ├── chunking.py        # content-aware text splitting
│   │   ├── embeddings.py      # local sentence-transformers wrapper
│   │   ├── vectorstore.py     # Chroma wrapper
│   │   ├── llm.py             # Ollama/Groq client
│   │   ├── rag.py             # retrieval + grounded generation
│   │   └── ingestion/
│   │       ├── detector.py    # extension → file_type
│   │       ├── pdf_loader.py
│   │       ├── docx_loader.py
│   │       ├── pptx_loader.py
│   │       ├── text_loader.py
│   │       ├── code_loader.py
│   │       ├── csv_loader.py
│   │       └── image_loader.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── lib/api.js
│   │   └── components/
│   │       ├── Landing.jsx
│   │       ├── UploadArea.jsx
│   │       ├── FileCard.jsx
│   │       ├── Sidebar.jsx
│   │       ├── ChatWindow.jsx
│   │       ├── MessageBubble.jsx
│   │       ├── Citation.jsx
│   │       ├── FileScopeSelector.jsx   # per-document chat scope chips
│   │       ├── SuggestedQuestions.jsx  # starter + follow-up prompt chips
│   │       └── ConnectionStatus.jsx    # backend health dot (GET /health)
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── .env.example
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 5. What's completely free vs. optional vs. potentially costly

**1. Completely free/local (default, $0 forever):**
- Embeddings: `sentence-transformers` (runs on your CPU/GPU, no API)
- Vector DB: Chroma (on-disk file, no server, no account)
- LLM: Ollama running `llama3.1:8b` / `llava:7b` locally
- Storage: local disk (`./data`)
- Frontend/backend hosting: your own machine

**2. Optional free-tier APIs (only if you choose them):**
- Groq (`LLM_PROVIDER=groq` in `.env`) — has a free tier as of this writing,
  but **verify current limits yourself** at https://console.groq.com before
  relying on it; free tiers change over time.

**3. Only costs money if you choose to add them later:**
- Cloud hosting (Render, Railway, AWS, etc.) for the backend/frontend
- A managed vector DB (Pinecone, Qdrant Cloud, etc.) instead of local Chroma
- A paid LLM API (OpenAI/Anthropic/Gemini) instead of Ollama
- A domain name / SSL for public deployment

---

## 6. Git / GitHub

```bash
cd omnirag
git init
echo "backend/venv/
backend/data/
backend/.env
frontend/node_modules/
frontend/.env
__pycache__/
*.pyc" > .gitignore
git add .
git commit -m "Initial commit: OmniRAG v1"
git branch -M main
git remote add origin https://github.com/<your-username>/omnirag.git
git push -u origin main
```
Never commit `.env` — only `.env.example`. `data/` holds your local uploads
and vector DB; keep it out of version control too.

---

## 7. How to extend (per your 38-step spec)

This build gives you a working vertical slice of the whole system end-to-end.
Here's exactly where to add the remaining advanced pieces:

- **Reranking**: after `vectorstore.query()` in `rag.py`, add a cross-encoder
  rerank step (e.g. `sentence-transformers` CrossEncoder `ms-marco-MiniLM-L-6-v2`,
  also free/local) and sort hits by rerank score before building the context.
- **Hybrid search (BM25 + vectors)**: add a BM25 index (e.g. `rank_bm25`) per
  workspace alongside Chroma, merge/re-rank both result sets in `vectorstore.py`.
- **Tree-sitter AST code parsing**: swap the regex boundaries in
  `ingestion/code_loader.py` for `tree-sitter-languages` grammars for exact
  function/class node boundaries.
- **LangGraph agent workflow**: wrap `rag.py`'s retrieve → generate steps as
  nodes in a `StateGraph`, adding conditional nodes for "needs clarification",
  "cross-file comparison", or "no-context found" branches.
- **RAG evaluation**: ✅ IMPLEMENTED — see §8 (`backend/tests/eval_rag.py`,
  15-question golden set, Full Ragas with local Ollama judge). To extend:
  add rerank-aware metrics or per-category thresholds in `score_retrieval()`.
- **Auth**: add FastAPI's `OAuth2PasswordBearer` + a `users` table in
  `memory.py` (or swap it for real SQLite/Postgres — it's already isolated
  behind one module).
- **Cloud deployment**: the Dockerfiles are ready — push images to any
  container host; just point `OLLAMA_BASE_URL` at a hosted Ollama instance
  or switch `LLM_PROVIDER=groq`.

---

## 8. Measuring accuracy (evaluation harness)

Run a real accuracy measurement against your own documents:

```bash
cd backend

# 1. Retrieval-only gate (fast, no Ollama needed) — use in CI
python -m pytest tests/eval_rag.py -v
python -m pytest tests/eval_rag.py -v --eval-fail-under 0.7

# 2. Full run: retrieval + answers + lightweight judge (needs Ollama)
python -m pytest tests/eval_rag.py -v -s --eval-with-answers --eval-judge lightweight

# 3. Full Ragas: standard faithfulness/answer_relevancy/context_precision/context_recall
pip install -r requirements.txt   # adds ragas datasets langchain-ollama
ollama serve & ollama pull llama3.1:8b
python -m pytest tests/eval_rag.py -v -s --eval-with-answers --eval-judge ragas

# 4. Standalone CLI (same engine, no pytest)
python -m tests.eval_rag --docs tests/eval_data/docs --questions tests/eval_data/golden_questions.csv
python -m tests.eval_rag --docs path/to/my/docs --questions my_golden.csv --with-answers --judge ragas --fail-under 0.7
```

- `--docs` — folder of documents to ingest (bundled: `tests/eval_data/docs/` with
  `sample_facts.txt`, `project_notes.md`, `sample_api.py`; point it at your own PDFs/DOCX/etc.).
- `--questions` — CSV with `question,expected_answer,source_filename,keywords[,category,difficulty]`
  (see `tests/eval_data/golden_questions.csv`, 15 Qs: factual, cross-file, code, unanswerable).
  - `keywords` are `|`-separated strings checked (case-insensitively) in the generated answer.
  - `category=unanswerable` rows have empty `source_filename` and pass iff the answer
    contains "I couldn't find this in the uploaded files" (excluded from Recall@k).
- Results: `Recall@k`, `MRR` (retrieval), keyword answer accuracy, lightweight judge (1–5),
  and Ragas means (faithfulness, answer_relevancy, context_precision, context_recall).
  Full per-question detail is written to `backend/eval/results.json`.
- Legacy starter still at `backend/eval/eval_rag.py` (4-col CSV); the canonical harness is
  `backend/tests/eval_rag.py` (backward-compat: reads old CSVs too).

**Interpreting numbers:** Recall@k ≥ 0.8 means retrieval is solid; answer accuracy depends on the local model's ability. Low Recall + high judge score → questions too easy; high Recall + low answers → model/prompt issue. Unanswerable-Q accuracy measures hallucination guard quality.

---

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| "Could not reach the local Ollama model" | Run `ollama serve`, confirm `ollama list` shows the model, check `OLLAMA_BASE_URL` in `.env` |
| File stuck on "processing" | Check the backend terminal for a stack trace; likely a missing system dependency (e.g. Tesseract not installed/found) |
| OCR returns empty text | Set `TESSERACT_CMD` in `.env` to the full path of `tesseract.exe` |
| CORS errors in browser console | Ensure `CORS_ORIGINS` in backend `.env` includes your frontend's URL (default `http://localhost:5173`) |
| Slow first response | The first Ollama call loads the model into memory — subsequent calls are faster |
| Out of memory on a small machine | Use a smaller model: `ollama pull llama3.2:3b` and set `OLLAMA_MODEL=llama3.2:3b` |
| `pip install` fails on `torch` | Install a CPU-only wheel: `pip install torch --index-url https://download.pytorch.org/whl/cpu` |

---

## 9. Portfolio / resume description

> **OmniRAG — Universal Multimodal RAG Assistant.** Designed and built a
> full-stack, multimodal Retrieval-Augmented Generation system supporting
> PDF, DOCX, PPTX, source code, spreadsheets, and images, with per-file-type
> ingestion pipelines, content-aware chunking, local embeddings, a metadata-
> aware Chroma vector store, and a citation-tracked, hallucination-guarded
> generation layer served through streaming FastAPI endpoints and a custom
> React/Tailwind chat interface. Engineered to run entirely offline/local at
> zero infrastructure cost using Ollama.

## 10. Interview explanation (short version)

*"OmniRAG is a RAG system where the hard part isn't the LLM call, it's
everything before it: normalizing wildly different file types into a common
'chunk + citation metadata' shape. Each file type gets its own loader that
preserves exactly where information came from — page number for PDFs, slide
number for decks, line ranges for code, row ranges for spreadsheets — so
every chunk stored in the vector DB carries provenance. At query time I embed
the question, retrieve top-k chunks from a per-workspace Chroma collection,
and build a prompt that explicitly instructs the model to answer only from
that context and say so if the answer isn't there — that's the hallucination
guard. Citations are computed independently of generation, from the same
retrieved hits, so the UI can show exactly what supported the answer. The
whole stack runs locally — sentence-transformers for embeddings, Chroma
on-disk, Ollama for the LLM — so there's no per-token cost and no dependency
on an external API being up."*
