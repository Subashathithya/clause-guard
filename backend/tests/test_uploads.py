"""Text-extraction tests for uploads (PDF/TXT/MD/DOCX). No LLM required."""
import io

import pytest

from app import uploads

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_bytes(
    paragraphs=("Heading text", "Fee payable in advance"),
    table=(("Term", "12 months"),),
) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    if table:
        t = doc.add_table(rows=len(table), cols=len(table[0]))
        for i, row in enumerate(table):
            for j, val in enumerate(row):
                t.cell(i, j).text = val
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_detect_file_type_basics():
    assert uploads.detect_file_type("application/pdf", "a.pdf") == "pdf"
    assert uploads.detect_file_type("", "a.pdf") == "pdf"  # extension fallback
    assert uploads.detect_file_type("text/plain", "a.txt") == "txt"
    assert uploads.detect_file_type("", "a.md") == "md"
    assert uploads.detect_file_type("", "a.docx") == "docx"
    assert uploads.detect_file_type(DOCX_MIME, "a.docx") == "docx"
    assert uploads.detect_file_type("application/msword", "a.doc") == "doc"
    assert uploads.detect_file_type("image/png", "a.png") is None


def test_extract_docx_paragraphs_and_tables():
    text = uploads.extract_text(_docx_bytes(), DOCX_MIME, "agreement.docx")
    assert "Heading text" in text
    assert "Fee payable in advance" in text
    assert "Term | 12 months" in text


def test_extract_txt():
    assert uploads.extract_text(b"hello world", "text/plain", "x.txt") == "hello world"


def test_extract_markdown():
    assert uploads.extract_text(b"# Title\nbody", "text/markdown", "x.md") == "# Title\nbody"


def test_extract_legacy_doc_rejected():
    with pytest.raises(ValueError) as ei:
        uploads.extract_text(b"whatever", "application/msword", "old.doc")
    assert "doc" in str(ei.value).lower()


def test_extract_unsupported_rejected():
    with pytest.raises(ValueError):
        uploads.extract_text(b"\x00\x01\x02", "image/png", "x.png")


def test_extract_empty_docx_rejected():
    with pytest.raises(ValueError):
        uploads.extract_text(_docx_bytes(paragraphs=(), table=()), DOCX_MIME, "empty.docx")