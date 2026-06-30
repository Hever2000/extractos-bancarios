from __future__ import annotations

from src.models.errors import ValidationError
from src.models.statement import Statement


def validate_statement(stmt: Statement) -> Statement:
    warnings: list[str] = []

    if not stmt.transactions:
        warnings.append("No transactions found in statement")

    seen = set()
    for tx in stmt.transactions:
        key = (tx.date.isoformat(), tx.description, str(tx.amount.signed_value))
        if key in seen:
            warnings.append(
                f"Possible duplicate: {tx.date} {tx.description} {tx.amount.signed_value}"
            )
        seen.add(key)

    if stmt.date_from and stmt.date_to and stmt.date_from > stmt.date_to:
        raise ValidationError(
            "date_from is after date_to", detail=f"{stmt.date_from} > {stmt.date_to}"
        )

    return Statement(
        bank=stmt.bank,
        transactions=stmt.transactions,
        date_from=stmt.date_from,
        date_to=stmt.date_to,
        metadata=stmt.metadata,
        warnings=stmt.warnings + tuple(warnings),
    )
