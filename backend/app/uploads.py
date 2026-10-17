"""File upload handling: extract plain text from PDF / TXT / MD / DOCX files."""
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# MIME types (some browsers omit them; filename extension is the fallback).
DOCX_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
DOC_MIMES = {"application/msword"}


def detect_file_type(content_type: str, filename: str = "") -> Optional[str]:
    """Return a canonical label (pdf|txt|md|docx|doc) or None if unsupported."""
    name = (filename or "").lower()
    if content_type == "application/pdf" or name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".md", ".markdown")) or content_type == "text/markdown":
        return "md"
    if content_type == "text/plain" or name.endswith((".txt", ".rtf")):
        return "txt"
    if content_type in DOCX_MIMES or name.endswith(".docx"):
        return "docx"
    if content_type in DOC_MIMES or name.endswith(".doc"):
        return "doc"
    return None


def extract_text(content: bytes, content_type: str, filename: str = "") -> str:
    """Extract text from an uploaded file based on its content type / extension."""
    doc_type = detect_file_type(content_type, filename)
    if doc_type == "pdf":
        return _extract_pdf(content)
    if doc_type == "docx":
        return _extract_docx(content)
    if doc_type in ("txt", "md"):
        return content.decode("utf-8", errors="ignore")
    if doc_type == "doc":
        raise ValueError(
            "Legacy .doc files are not supported. Save the document as .docx or "
            "PDF and upload that instead."
        )
    raise ValueError(f"Unsupported file type: {content_type or filename or 'unknown'}")


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for PDF uploads. pip install pypdf") from exc

    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to extract a PDF page: %s", exc)
    text = "\n".join(p for p in pages if p.strip())
    if not text.strip():
        raise ValueError(
            "No selectable text found in the PDF. It may be a scanned image; "
            "please paste the text manually."
        )
    return text


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx is required for .docx uploads. pip install python-docx"
        ) from exc

    try:
        document = Document(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not parse the Word document: {exc}") from exc

    parts = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(c for c in cells if c))

    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("No readable text found in the Word document.")
    return text