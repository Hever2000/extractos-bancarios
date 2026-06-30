from __future__ import annotations

import logging
from datetime import date
from typing import Any

from src.cleaners.filters import split_lines
from src.cleaners.normalizer import normalize_text
from src.detectors.bank import detect_bank
from src.extractors.pdf import extract_text_from_pdf
from src.models.statement import Statement, Transaction
from src.normalizers.amount import normalize_amount
from src.parsers.factory import ParserFactory
from src.serializers.json import serialize_statement
from src.validators.schema import validate_statement

log = logging.getLogger(__name__)


def _parse_date(raw: str) -> date:
    d, m, y = raw.split("/")
    return date(int(y), int(m), int(d))


def process_statement(
    pdf_bytes: bytes,
    filename: str = "",
    strict: bool = False,
) -> str:
    raw_text = extract_text_from_pdf(pdf_bytes)
    log.info("extracted_text", extra={"chars": len(raw_text)})

    text = normalize_text(raw_text)
    lines = split_lines(text)
    log.info("normalized_lines", extra={"count": len(lines)})

    detection = detect_bank(text, filename)
    if detection.bank is None:
        result = {
            "banco": None,
            "aviso": "No se pudo detectar el banco.",
            "lineas_extraidas": len(lines),
        }
        if detection.confidence.name:
            result["confidencia"] = detection.confidence.name
        return serialize_statement_custom(result)

    log.info("bank_detected", extra={"bank": detection.bank.name, "score": detection.score})

    parser = ParserFactory.for_bank(detection.bank.id)
    raw_tx_list = parser.parse_lines(lines)
    log.info("parsed_transactions", extra={"count": len(raw_tx_list)})

    transactions: list[Transaction] = []
    for rtx in raw_tx_list:
        tx_date = _parse_date(rtx.fecha)
        amount = normalize_amount(rtx.importe)
        balance = normalize_amount(rtx.saldo) if rtx.saldo is not None else None
        transactions.append(
            Transaction(date=tx_date, description=rtx.descripcion, amount=amount, balance=balance)
        )

    if not transactions:
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
            transactions=tuple(transactions),
            date_from=transactions[0].date,
            date_to=transactions[-1].date,
        )

    stmt = validate_statement(stmt)
    return serialize_statement(stmt, indent=2)


def serialize_statement_custom(data: dict[str, Any]) -> str:
    import json

    class _Encoder(json.JSONEncoder):
        def default(self, o: object) -> str:
            return str(o)

    return json.dumps(data, indent=2, ensure_ascii=False, cls=_Encoder)
