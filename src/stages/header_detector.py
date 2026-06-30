from __future__ import annotations

import re

from src.models.document import Document, Page, TextBlock
from src.models.table import Table
from src.models.trace import StageResult

_HEADER_PATTERNS = re.compile(
    r"^(Ultimos Movimientos|Extracto de Cuenta|C\.C\.|Caja de Ahorro|"
    r"Cuenta Corriente|Cuenta Sueldo|Pesos?$|Tipo$|Numero$|Moneda$|"
    r"BANCO\s+(MACRO|PROVINCIA|NACION|GALICIA)|"
    r"EXTRACTO DE CUENTA|Fecha consulta:|Hora consulta:|Cuenta: \d+)",
    re.I,
)


def _is_header_block(block: TextBlock) -> bool:
    text = " ".join(w.text for w in block.words)
    return bool(_HEADER_PATTERNS.search(text))


def filter_headers(doc: Document, tables: list[Table]) -> tuple[Document, StageResult]:
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
            if block.bbox.bottom < table_bbox.top and _is_header_block(block):
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
        stage_name="header_detector",
        confidence=1.0 if removed > 0 else 0.5,
        metrics={"headers_removed": removed},
        warnings=(),
    )
