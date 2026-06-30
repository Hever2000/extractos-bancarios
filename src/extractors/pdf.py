from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from src.models.errors import ExtractError


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    if not pdf_bytes[:4] == b"%PDF":
        raise ExtractError(
            "File does not appear to be a valid PDF", detail="missing PDF magic bytes"
        )

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as e:
        raise ExtractError(f"Failed to open PDF: {e}")

    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text()
            if text:
                pages.append(text)
        except Exception as e:
            raise ExtractError(f"Failed to extract text from page {i + 1}", detail=str(e))

    result = "\n".join(pages).strip()
    if not result:
        raise ExtractError(
            "No text could be extracted from PDF", detail="PDF may be scanned or image-based"
        )

    return result
