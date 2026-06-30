from __future__ import annotations

from typing import Protocol

from src.models.document import Document


class PDFProcessor(Protocol):
    def extract(self, pdf_bytes: bytes) -> Document:
        ...
