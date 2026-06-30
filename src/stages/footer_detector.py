from __future__ import annotations

import re

from src.models.document import Document, Page, TextBlock
from src.models.table import Table
from src.models.trace import StageResult

_FOOTER_PATTERNS = re.compile(
    r"^(Fecha de descarga:|Operador:|Empresa:|"
    r"\d+ de \d+$|CBU|DNI$|CIUDAD AUTONOMA|OLAVARRIA|"
    r"1000 - REGION|parametros de busqueda|busqueda:)",
    re.I,
)


def _is_footer_block(block: TextBlock) -> bool:
    text = " ".join(w.text for w in block.words)
    return bool(_FOOTER_PATTERNS.search(text))


def filter_footers(doc: Document, tables: list[Table]) -> tuple[Document, StageResult]:
    table_boxes = {t.page_number: t.bbox for t in tables if t.bbox is not None}
    removed = 0
    pages: list[Page] = []

    for page in doc.pages:
        table_bbox = table_boxes.get(page.number)
        if table_bbox is None:
            pages.append(page)
            continue

        kept: list[TextBlock] = []
        for block in page.blocks:
            if block.bbox.top > table_bbox.bottom and _is_footer_block(block):
                removed += 1
            else:
                kept.append(block)

        pages.append(Page(
            number=page.number,
            width=page.width,
            height=page.height,
            words=page.words,
            blocks=tuple(kept),
        ))

    return Document(pages=tuple(pages)), StageResult(
        stage_name="footer_detector",
        confidence=1.0 if removed > 0 else 0.5,
        metrics={"footers_removed": removed},
        warnings=(),
    )
