"""PDF ingestion using PyMuPDF. Returns one 'document' dict per page so that
page numbers survive all the way to citations."""
import fitz  # PyMuPDF


def load_pdf(path: str) -> list[dict]:
    docs = []
    with fitz.open(path) as pdf:
        for page_num, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if text:
                docs.append({
                    "text": text,
                    "location": f"page {page_num}",
                    "page": page_num,
                })
    return docs
