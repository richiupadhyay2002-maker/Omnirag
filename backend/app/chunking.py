"""
Intelligent chunking: the loaders already produce content-aware "documents"
(one per page/slide/function/row-block). Here we further split any that are
too large for the embedding model's context, using different target sizes
per content type, and preserve all citation metadata on every resulting chunk.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

TARGET_CHUNK_CHARS = {
    "pdf": 1200,
    "docx": 1200,
    "pptx": 900,
    "text": 1000,
    "code": 1500,     # keep functions whole where possible
    "csv": 2000,      # summaries/row blocks are already structured
    "image": 2000,    # rarely needs splitting
}

CODE_SEPARATORS = ["\ndef ", "\nclass ", "\nfunction ", "\n\n", "\n", " "]
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


def chunk_documents(raw_docs: list[dict], file_type: str) -> list[dict]:
    target = TARGET_CHUNK_CHARS.get(file_type, 1000)
    separators = CODE_SEPARATORS if file_type == "code" else DEFAULT_SEPARATORS

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=target,
        chunk_overlap=int(target * 0.12),
        separators=separators,
    )

    chunks = []
    for doc in raw_docs:
        text = doc["text"]
        if len(text) <= target:
            pieces = [text]
        else:
            pieces = splitter.split_text(text)

        for piece in pieces:
            chunk = dict(doc)   # copy metadata (location, page, image_path...)
            chunk["text"] = piece
            chunks.append(chunk)

    return chunks
