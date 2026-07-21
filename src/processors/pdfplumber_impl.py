from __future__ import annotations

from io import BytesIO

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from src.models.document import BBox, Document, Page, Word
from src.models.errors import ExtractError
from src.processors.base import PDFProcessor


class PdfplumberProcessor(PDFProcessor):
    def extract(self, pdf_bytes: bytes) -> Document:
        if not pdf_bytes[:4] == b"%PDF":
            raise ExtractError(
                "does not appear to be a valid PDF",
                detail="missing PDF magic bytes",
            )

        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages: list[Page] = []
                for i, plumber_page in enumerate(pdf.pages, start=1):
                    words_data = plumber_page.extract_words(
                        extra_attrs=["fontname", "size"],
                        keep_blank_chars=True,
                        x_tolerance=3,
                    )
                    page_words = tuple(
                        Word(
                            text=w["text"],
                            bbox=BBox(
                                x0=w["x0"], x1=w["x1"],
                                top=w["top"], bottom=w["bottom"],
                            ),
                            fontname=w.get("fontname"),
                        )
                        for w in words_data
                    )
                    pages.append(Page(
                        number=i,
                        width=plumber_page.width,
                        height=plumber_page.height,
                        words=page_words,
                    ))
                return Document(pages=tuple(pages))
        except PdfminerException as e:
            raise ExtractError(
                "does not appear to be a valid PDF",
                detail=str(e),
            )
