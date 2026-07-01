from __future__ import annotations

import json
import logging
from typing import Any

from src.detectors.bank import detect_bank
from src.models.errors import ExtractError
from src.models.statement import Statement
from src.processors.pdfplumber_impl import PdfplumberProcessor
from src.serializers.json import serialize_statement
from src.stages import (
    block_builder,
    column_detector,
    column_mapper,
    footer_detector,
    header_detector,
    row_extractor,
    row_merger,
    table_detector,
    transaction_builder,
)
from src.validators.schema import validate_statement

log = logging.getLogger(__name__)

_processor = PdfplumberProcessor()
_MAX_PDF_SIZE = 10 * 1024 * 1024


def process_statement(
    pdf_bytes: bytes,
    filename: str = "",
    strict: bool = False,
) -> str:
    if len(pdf_bytes) > _MAX_PDF_SIZE:
        raise ExtractError(
            f"PDF exceeds maximum size of {_MAX_PDF_SIZE // (1024 * 1024)}MB",
            detail=f"got {len(pdf_bytes)} bytes",
        )

    doc = _processor.extract(pdf_bytes)

    raw_text = " ".join(w.text for page in doc.pages for w in page.words)
    detection = detect_bank(raw_text, filename)
    if detection.bank is None:
        result: dict[str, Any] = {
            "banco": None,
            "aviso": "No se pudo detectar el banco.",
            "lineas_extraidas": len(raw_text.splitlines()),
        }
        if detection.confidence.name:
            result["confidencia"] = detection.confidence.name
        return _serialize_custom(result)

    log.info("bank_detected", extra={"bank": detection.bank.name, "score": detection.score})

    doc = block_builder.build(doc)
    tables = table_detector.detect(doc)

    if not tables:
        stmt = Statement(
            bank=detection.bank,
            transactions=(),
            date_from=None,
            date_to=None,
            warnings=("No se encontraron movimientos.",),
        )
        stmt = validate_statement(stmt)
        return serialize_statement(stmt, indent=2)

    doc = header_detector.filter_headers(doc, tables)
    doc = footer_detector.filter_footers(doc, tables)

    all_normalized: list[Any] = []
    for table in tables:
        table = column_detector.detect(table)
        table = row_extractor.extract(table)
        merged = row_merger.merge(table)
        normalized_rows = column_mapper.map_columns(merged)
        all_normalized.extend(normalized_rows)

    transactions_raw = transaction_builder.build(all_normalized)
    transactions_raw.sort(key=lambda t: t.date)

    if not transactions_raw:
        stmt = Statement(
            bank=detection.bank,
            transactions=(),
            date_from=None,
            date_to=None,
            warnings=("No se encontraron movimientos.",),
        )
    else:
        stmt = Statement(
            bank=detection.bank,
            transactions=tuple(transactions_raw),
            date_from=transactions_raw[0].date,
            date_to=transactions_raw[-1].date,
        )

    stmt = validate_statement(stmt)
    return serialize_statement(stmt, indent=2)


def _serialize_custom(data: dict[str, Any]) -> str:
    class _Encoder(json.JSONEncoder):
        def default(self, o: object) -> str:
            return str(o)

    return json.dumps(data, indent=2, ensure_ascii=False, cls=_Encoder)
