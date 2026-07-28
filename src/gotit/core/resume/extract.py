"""Resume text extraction (framework-free).

Given raw file bytes + content type, return plain text. Deterministic IO only
(no LLM). Used as stage 1 of the two-stage resume parse.
"""

from __future__ import annotations

from typing import Literal

ContentType = Literal[
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
]


class ResumeExtractError(Exception):
    """Raised when a resume file yields no extractable text."""


def extract_text(content: bytes, content_type: str) -> str:
    """Extract plain text from a resume file by content type.

    Raises ResumeExtractError when the file yields no text (e.g. scanned PDF).
    """
    if content_type == "application/pdf":
        text = _extract_pdf(content)
    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = _extract_docx(content)
    elif content_type in ("text/plain", "text/markdown"):
        text = content.decode("utf-8", errors="replace")
    else:
        raise ResumeExtractError(f"unsupported content type: {content_type}")

    text = text.strip()
    if not text:
        raise ResumeExtractError("no extractable text (scanned PDF or empty file?)")
    return text


def _extract_pdf(content: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(content))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_docx(content: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs)
