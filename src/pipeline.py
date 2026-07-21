from __future__ import annotations

import json
import logging
from typing import Any

from src.detectors.bank import detect_bank
from src.extractors.metadata import extract_statement_metadata
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
    total_words = sum(len(p.words) for p in doc.pages)

    # === SECCION 1: EXTRACCION ===
    print("=== EXTRACCION ===")
    print(f"PDF: {len(doc.pages)} pagina(s), {total_words} palabra(s) extraidas")
    print()

    raw_text = " ".join(w.text for page in doc.pages for w in page.words)
    detection = detect_bank(raw_text, filename)
    if detection.bank is None:
        print("=== BANCO ===")
        print("No se pudo detectar el banco")
        print()
        result: dict[str, Any] = {
            "banco": None,
            "aviso": "No se pudo detectar el banco.",
            "lineas_extraidas": len(raw_text.splitlines()),
        }
        if detection.confidence.name:
            result["confidencia"] = detection.confidence.name
        json_result = _serialize_custom(result)
        return json_result

    # === SECCION 2: BANCO ===
    print("=== BANCO ===")
    print(f"Banco: {detection.bank.name} (score: {detection.score})")
    print()
    log.info("bank_detected", extra={"bank": detection.bank.name, "score": detection.score})

    doc = block_builder.build(doc)
    tables = table_detector.detect(doc)

    stmt_metadata = extract_statement_metadata(doc, tables, detection.bank)

    if not tables:
        print("Sin tablas detectadas - sin movimientos")
        print()
        stmt = Statement(
            bank=detection.bank,
            cbu=stmt_metadata.cbu,
            account=stmt_metadata.account,
            account_type=stmt_metadata.account_type,
            transactions=(),
            date_from=None,
            date_to=None,
        )
        stmt = validate_statement(stmt)
        json_result = serialize_statement(stmt, indent=2)
        return json_result

    doc = header_detector.filter_headers(doc, tables)
    doc = footer_detector.filter_footers(doc, tables)

    all_normalized: list[Any] = []
    for table in tables:
        # === SECCION 3 y 4: COLUMNAS, FILAS, FILAS FUSIONADAS ===
        print(f"--- Pagina {table.page_number} ---")

        table = column_detector.detect(table)
        n_cols = len(table.lanes)
        print(f"  Columnas: {n_cols} detectadas")

        table = row_extractor.extract(table)
        n_rows = len(table.rows)
        n_cont = sum(1 for r in table.rows if r.is_continuation)
        print(f"  Filas: {n_rows} extraidas ({n_cont} continuacion(es))")

        merged = row_merger.merge(table)

        normalized_rows = column_mapper.map_columns(merged)
        all_normalized.extend(normalized_rows)
        print()

    transactions_raw = transaction_builder.build(all_normalized)
    transactions_raw.sort(key=lambda t: t.date)

    if not transactions_raw:
        stmt = Statement(
            bank=detection.bank,
            cbu=stmt_metadata.cbu,
            account=stmt_metadata.account,
            account_type=stmt_metadata.account_type,
            transactions=(),
            date_from=None,
            date_to=None,
        )
    else:
        stmt = Statement(
            bank=detection.bank,
            cbu=stmt_metadata.cbu,
            account=stmt_metadata.account,
            account_type=stmt_metadata.account_type,
            transactions=tuple(transactions_raw),
            date_from=transactions_raw[0].date,
            date_to=transactions_raw[-1].date,
        )

    stmt = validate_statement(stmt)
    json_result = serialize_statement(stmt, indent=2)

    return json_result


def _serialize_custom(data: dict[str, Any]) -> str:
    class _Encoder(json.JSONEncoder):
        def default(self, o: object) -> str:
            return str(o)

    return json.dumps(data, indent=2, ensure_ascii=False, cls=_Encoder)
