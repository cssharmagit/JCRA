from __future__ import annotations

import io
from pathlib import Path

ALLOWED = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
    "text/plain",
}

EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


def sniff(filename: str, content_type: str) -> str | None:
    media = (content_type or "").split(";")[0].strip().lower()
    if media == "image/jpg":
        media = "image/jpeg"
    if media in ALLOWED:
        return media
    guessed = EXT.get(Path(filename or "").suffix.lower())
    if guessed:
        return guessed
    return None


def extract_text(media_type: str, data: bytes) -> str:
    if media_type == "text/plain":
        return data.decode("utf-8", errors="replace")
    if media_type == "application/pdf":
        return _pdf_text(data)
    return ""


def needs_vision(media_type: str, text: str) -> bool:
    if media_type.startswith("image/"):
        return True
    # always send PDFs: extracted text misses scanned pages and embedded
    # screenshots, which are common in receipt bundles
    return media_type == "application/pdf"


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""
