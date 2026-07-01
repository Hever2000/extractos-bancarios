from __future__ import annotations

from datetime import date

from src.models.canonical import NormalizedRow
from src.models.statement import Transaction
from src.normalizers.amount import normalize_amount


def build(rows: list[NormalizedRow]) -> list[Transaction]:
    transactions: list[Transaction] = []

    for row in rows:
        if row.date is None:
            continue

        parts = row.date.split("/")
        tx_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
        amount = normalize_amount(row.amount) if row.amount else normalize_amount(None)
        balance = normalize_amount(row.balance) if row.balance else None

        transactions.append(Transaction(
            date=tx_date,
            description=row.description,
            amount=amount,
            balance=balance,
        ))

    return transactions
