from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from src.detectors.bank import detect_bank
from src.models.document import Document
from src.models.statement import Statement, Transaction
from src.normalizers.amount import normalize_amount
from src.parsers.factory import ParserFactory
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


def _parse_date(raw: str) -> date:
    d, m, y = raw.split("/")
    return date(int(y), int(m), int(d))


def _reconstruct_lines(doc: Document) -> list[str]:
    lines: list[str] = []
    for page in doc.pages:
        if not page.words:
            continue
        sorted_words = sorted(page.words, key=lambda w: (w.bbox.top, w.bbox.x0))
        page_lines: list[list[tuple[float, str]]] = []
        current_line: list[tuple[float, str]] = [
            (sorted_words[0].bbox.x0, sorted_words[0].text)
        ]
        current_top = sorted_words[0].bbox.top

        for w in sorted_words[1:]:
            if abs(w.bbox.top - current_top) <= 3.0:
                current_line.append((w.bbox.x0, w.text))
            else:
                page_lines.append(current_line)
                current_line = [(w.bbox.x0, w.text)]
                current_top = w.bbox.top

        if current_line:
            page_lines.append(current_line)

        for line_words in page_lines:
            sorted_by_x = sorted(line_words, key=lambda x: x[0])
            lines.append(" ".join(text for _, text in sorted_by_x))

    return lines


def process_statement(
    pdf_bytes: bytes,
    filename: str = "",
    strict: bool = False,
) -> str:
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

    try:
        parser = ParserFactory.for_bank(detection.bank.id)
        raw_lines = _reconstruct_lines(doc)
        raw_tx = parser.parse_lines(raw_lines)
    except ValueError:
        raw_tx = []

    if raw_tx:
        transactions = tuple(
            Transaction(
                date=_parse_date(t.fecha),
                description=t.descripcion,
                amount=normalize_amount(t.importe),
                balance=normalize_amount(t.saldo) if t.saldo else None,
            )
            for t in raw_tx
        )
        stmt = Statement(
            bank=detection.bank,
            transactions=transactions,
            date_from=transactions[0].date,
            date_to=transactions[-1].date,
        )
        stmt = validate_statement(stmt)
        return serialize_statement(stmt, indent=2)

    doc = block_builder.build(doc)
    tables, _ = table_detector.detect(doc)

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

    doc, _ = header_detector.filter_headers(doc, tables)
    doc, _ = footer_detector.filter_footers(doc, tables)

    all_normalized: list[Any] = []
    for table in tables:
        table, _ = column_detector.detect(table)
        table, _ = row_extractor.extract(table)
        merged, _ = row_merger.merge(table)
        normalized_rows, _ = column_mapper.map_columns(merged)
        all_normalized.extend(normalized_rows)

    transactions_raw, _ = transaction_builder.build(all_normalized)
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
