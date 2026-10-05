# OmniRAG Project Notes (eval fixture)

This note supports the evaluation harness cross-file and architecture questions.

## Embeddings
Default embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
Runs locally on CPU via sentence-transformers. No API key required.

## Vector store
OmniRAG uses Chroma (on-disk, persistent) for the vector database.
Data is isolated per workspace: one Chroma collection per workspace,
named `ws_<workspace_id>`. Each chunk stores metadata: file_id,
filename, file_type, location, page, image_path.

## Chunking
`chunk_documents()` in `app/chunking.py` further splits oversized loader
documents with `RecursiveCharacterTextSplitter`, keeping roughly 12%
overlap so context is not lost at boundaries. Code chunks use
function/class-aware separators.

## Grounded answering
The RAG pipeline in `app/rag.py` builds a grounded prompt. If the retrieved
context does not contain the answer, the assistant must reply exactly:
"I couldn't find this in the uploaded files." It must not invent facts.
