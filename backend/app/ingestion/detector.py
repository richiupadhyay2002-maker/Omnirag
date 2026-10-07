"""Detects a file's category from its extension so the right loader is used."""
from pathlib import Path

CODE_EXTENSIONS = {
    ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx",
    ".sql", ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".kt", ".sh",
}

TYPE_MAP = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".txt": "text",
    ".md": "text",
    ".csv": "csv",
    ".xlsx": "csv",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".bmp": "image",
}


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in CODE_EXTENSIONS:
        return "code"
    return TYPE_MAP.get(ext, "unsupported")
