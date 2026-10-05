from app.ingestion.detector import detect_file_type
from app.ingestion.text_loader import load_text
from app.ingestion.code_loader import load_code

try:  # optional heavy deps (pdf/docx/pptx/csv/image may be missing locally)
    from app.ingestion.pdf_loader import load_pdf
except ImportError:  # pragma: no cover
    load_pdf = None
try:
    from app.ingestion.docx_loader import load_docx
except ImportError:  # pragma: no cover
    load_docx = None
try:
    from app.ingestion.pptx_loader import load_pptx
except ImportError:  # pragma: no cover
    load_pptx = None
try:
    from app.ingestion.csv_loader import load_csv
except ImportError:  # pragma: no cover
    load_csv = None
try:
    from app.ingestion.image_loader import load_image
except ImportError:  # pragma: no cover
    load_image = None

LOADERS = {}
if load_pdf is not None:
    LOADERS["pdf"] = load_pdf
if load_docx is not None:
    LOADERS["docx"] = load_docx
if load_pptx is not None:
    LOADERS["pptx"] = load_pptx
LOADERS["text"] = load_text
LOADERS["code"] = load_code
if load_csv is not None:
    LOADERS["csv"] = load_csv
if load_image is not None:
    LOADERS["image"] = load_image


def load_file(path: str, file_type: str) -> list[dict]:
    """Dispatches to the correct loader. Returns a list of
    {text, location, page, [image_path]} dicts ready for chunking."""
    loader = LOADERS.get(file_type)
    if loader is None:
        raise ValueError(f"Unsupported file type: {file_type} "
                         f"(missing optional dependency?)")
    return loader(path)
