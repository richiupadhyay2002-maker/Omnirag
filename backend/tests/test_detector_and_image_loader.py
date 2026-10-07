"""
Unit tests for app.ingestion.detector and app.ingestion.image_loader.

Run with: python -m pytest tests/test_detector_and_image_loader.py -v
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _load_module(name: str):
    """Load a module file directly, bypassing the heavy app.ingestion.__init__
    (which imports pdf/docx/pptx loaders and their optional dependencies)."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[1] / "app" / "ingestion" / f"{name.split('.')[-1]}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Stub the app package so 'from app.ingestion.detector import ...'
# does not trigger the real app.ingestion.__init__ (heavy optional deps),
# while app.config still resolves for image_loader's settings import.
_app = types.ModuleType("app")
_app.__path__ = [str(Path(__file__).resolve().parents[1] / "app")]
sys.modules["app"] = _app
_stub_pkg = types.ModuleType("app.ingestion")
_stub_pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "app" / "ingestion")]
sys.modules["app.ingestion"] = _stub_pkg

detector = _load_module("app.ingestion.detector")

TYPE_MAP = detector.TYPE_MAP
CODE_EXTENSIONS = detector.CODE_EXTENSIONS
detect_file_type = detector.detect_file_type


# ---------------------------------------------------------------------------
# detect_file_type — positive cases
# ---------------------------------------------------------------------------
class TestDetectFileTypePositive:
    @pytest.mark.parametrize("filename,expected", [
        ("report.pdf", "pdf"),
        ("thesis.docx", "docx"),
        ("old.doc", "unsupported"),
        ("slides.pptx", "pptx"),
        ("deck.ppt", "unsupported"),
        ("notes.txt", "text"),
        ("readme.md", "text"),
        ("data.csv", "csv"),
        ("sheet.xlsx", "csv"),
        ("table.xls", "unsupported"),
        ("diagram.png", "image"),
        ("photo.jpg", "image"),
        ("scan.jpeg", "image"),
        ("banner.webp", "image"),
        ("logo.bmp", "image"),
    ])
    def test_document_extensions(self, filename, expected):
        assert detect_file_type(filename) == expected

    @pytest.mark.parametrize("filename,expected", [
        ("main.py", "code"),
        ("App.java", "code"),
        ("kernel.c", "code"),
        ("math.cpp", "code"),
        ("header.h", "code"),
        ("header.hpp", "code"),
        ("index.js", "code"),
        ("Component.jsx", "code"),
        ("app.ts", "code"),
        ("Component.tsx", "code"),
        ("query.sql", "code"),
        ("server.go", "code"),
        ("lib.rs", "code"),
        ("script.rb", "code"),
        ("page.php", "code"),
        ("Program.cs", "code"),
        ("App.swift", "code"),
        ("Main.kt", "code"),
        ("run.sh", "code"),
    ])
    def test_code_extensions(self, filename, expected):
        assert detect_file_type(filename) == "code"

    def test_uppercase_extension_is_lowered(self):
        assert detect_file_type("REPORT.PDF") == "pdf"
        assert detect_file_type("MAIN.PY") == "code"

    def test_mixed_case_extension(self):
        assert detect_file_type("Photo.JpEg") == "image"

    def test_full_path_filename(self):
        assert detect_file_type("/some/dir/report.pdf") == "pdf"
        assert detect_file_type("C:\\data\\main.py") == "code"


# ---------------------------------------------------------------------------
# detect_file_type — negative / edge cases
# ---------------------------------------------------------------------------
class TestDetectFileTypeNegativeEdge:
    @pytest.mark.parametrize("filename", [
        "file.unknown",
        "file.xyz",
        "archive.zip",
        "archive.tar.gz",
        "data.json",
        "song.mp3",
        "video.mp4",
        "doc.pdf.exe",
        "no_extension",
        "",
        ".",
        "..",
        ".hidden",           # dotfile with no real suffix
    ])
    def test_unsupported_types(self, filename):
        assert detect_file_type(filename) == "unsupported"

    def test_dotfile_with_suffix_maps_normally(self):
        # pathlib treats '.hidden.txt' as name='.hidden.txt', suffix='.txt'
        assert detect_file_type(".hidden.txt") == "text"

    def test_empty_extension_dot_only(self):
        # "file." -> suffix is "." -> not in maps
        assert detect_file_type("file.") == "unsupported"

    def test_type_map_consistency(self):
        # every mapped type must be one of the known categories
        allowed = {"pdf", "docx", "pptx", "text", "csv", "image"}
        assert set(TYPE_MAP.values()) <= allowed

    def test_code_extensions_do_not_overlap_type_map(self):
        assert not (CODE_EXTENSIONS & set(TYPE_MAP.keys()))

    def test_returns_str(self):
        assert isinstance(detect_file_type("x.pdf"), str)


# ---------------------------------------------------------------------------
# load_image — positive cases (mocked OCR)
# ---------------------------------------------------------------------------
image_loader = _load_module("app.ingestion.image_loader")
load_image = image_loader.load_image


class TestLoadImagePositive:
    def test_ocr_extracts_text(self):
        with patch("app.ingestion.image_loader.Image.open") as mock_open, \
             patch("app.ingestion.image_loader.pytesseract.image_to_string",
                   return_value="  Architecture diagram: client -> server  "):
            docs = load_image("fake/path.png")

        assert len(docs) == 1
        doc = docs[0]
        assert doc["text"] == "Architecture diagram: client -> server"  # stripped
        assert doc["location"] == "image"
        assert doc["page"] is None
        assert doc["image_path"] == "fake/path.png"
        mock_open.assert_called_once_with("fake/path.png")

    def test_all_expected_keys_present(self):
        with patch("app.ingestion.image_loader.Image.open"), \
             patch("app.ingestion.image_loader.pytesseract.image_to_string",
                   return_value="hello"):
            doc = load_image("x.jpg")[0]
        assert set(doc.keys()) == {"text", "location", "page", "image_path"}

    def test_multiline_ocr_text_preserved(self):
        with patch("app.ingestion.image_loader.Image.open"), \
             patch("app.ingestion.image_loader.pytesseract.image_to_string",
                   return_value="line one\nline two\n"):
            doc = load_image("x.png")[0]
        assert doc["text"] == "line one\nline two"


# ---------------------------------------------------------------------------
# load_image — fallback / negative / edge cases
# ---------------------------------------------------------------------------
class TestLoadImageFallbackAndEdge:
    def test_no_ocr_text_yields_fallback_message(self):
        with patch("app.ingestion.image_loader.Image.open"), \
             patch("app.ingestion.image_loader.pytesseract.image_to_string",
                   return_value="   "):
            docs = load_image("x.png")
        assert "[No machine-readable text detected" in docs[0]["text"]
        assert docs[0]["image_path"] == "x.png"

    def test_corrupt_image_falls_back_gracefully(self):
        with patch("app.ingestion.image_loader.Image.open",
                   side_effect=Exception("cannot identify image file")):
            docs = load_image("corrupt.png")
        assert len(docs) == 1
        assert "[No machine-readable text detected" in docs[0]["text"]

    def test_missing_file_falls_back_gracefully(self):
        with patch("app.ingestion.image_loader.Image.open",
                   side_effect=FileNotFoundError()):
            docs = load_image("ghost.png")
        assert "[No machine-readable text detected" in docs[0]["text"]

    def test_ocr_failure_falls_back_gracefully(self):
        with patch("app.ingestion.image_loader.Image.open"), \
             patch("app.ingestion.image_loader.pytesseract.image_to_string",
                   side_effect=RuntimeError("tesseract not found")):
            docs = load_image("x.png")
        assert "[No machine-readable text detected" in docs[0]["text"]

    def test_fallback_doc_still_has_image_path(self):
        with patch("app.ingestion.image_loader.Image.open",
                   side_effect=Exception("boom")):
            doc = load_image("img/bmp diag.bmp")[0]
        assert doc["image_path"] == "img/bmp diag.bmp"
        assert doc["location"] == "image"
        assert doc["page"] is None

    def test_ocr_called_with_opened_image(self):
        img_mock = MagicMock()
        with patch("app.ingestion.image_loader.Image.open", return_value=img_mock) as mo, \
             patch("app.ingestion.image_loader.pytesseract.image_to_string") as ocr:
            load_image("x.png")
        ocr.assert_called_once_with(img_mock)
        mo.assert_called_once_with("x.png")
