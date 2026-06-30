from __future__ import annotations

from datetime import date

from src.models.canonical import NormalizedRow
from src.models.statement import Transaction
from src.models.trace import StageResult
from src.normalizers.amount import normalize_amount


def build(rows: list[NormalizedRow]) -> tuple[list[Transaction], StageResult]:
    transactions: list[Transaction] = []
    missing_amounts = 0
    missing_dates = 0

    for row in rows:
        if row.date is None:
            missing_dates += 1
            continue

        parts = row.date.split("/")
        tx_date = date(int(parts[2]), int(parts[1]), int(parts[0]))

        if row.amount:
            amount = normalize_amount(row.amount)
        else:
            amount = normalize_amount(None)
            missing_amounts += 1

        balance = normalize_amount(row.balance) if row.balance else None

        transactions.append(Transaction(
            date=tx_date,
            description=row.description,
            amount=amount,
            balance=balance,
        ))

    warnings: tuple[str, ...] = ()
    if missing_amounts:
        warnings = warnings + (f"{missing_amounts} transacciones sin importe",)
    if missing_dates:
        warnings = warnings + (f"{missing_dates} transacciones sin fecha",)

    return transactions, StageResult(
        stage_name="transaction_builder",
        confidence=1.0 if transactions else 0.0,
        metrics={
            "transactions_built": len(transactions),
            "missing_amounts": missing_amounts,
            "missing_dates": missing_dates,
        },
        warnings=warnings,
    )
