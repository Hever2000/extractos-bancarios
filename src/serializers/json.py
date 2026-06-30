from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from src.models.statement import Amount, Statement, Transaction


class StatementEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, date):
            return o.strftime("%d/%m/%Y")
        if isinstance(o, Amount):
            return o.signed_value
        return super().default(o)


def _tx_to_dict(tx: Transaction) -> dict[str, Any]:
    d: dict[str, Any] = {
        "fecha": tx.date.strftime("%d/%m/%Y"),
        "descripcion": tx.description,
        "importe": float(tx.amount.signed_value),
    }
    if tx.balance is not None:
        d["saldo"] = float(tx.balance.signed_value)
    else:
        d["saldo"] = None
    return d


def serialize_statement(stmt: Statement, indent: int | None = None) -> str:
    data: dict[str, Any] = {
        "banco": stmt.bank.name,
        "fecha_desde": stmt.date_from.strftime("%d/%m/%Y") if stmt.date_from else None,
        "fecha_hasta": stmt.date_to.strftime("%d/%m/%Y") if stmt.date_to else None,
        "detalle": [_tx_to_dict(tx) for tx in stmt.transactions],
    }
    if stmt.metadata:
        data["metadata"] = stmt.metadata
    if stmt.warnings:
        data["warnings"] = list(stmt.warnings)
    return json.dumps(data, indent=indent, ensure_ascii=False)
