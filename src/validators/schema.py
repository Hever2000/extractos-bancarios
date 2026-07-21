from __future__ import annotations

from src.models.errors import ValidationError
from src.models.statement import Statement


def validate_statement(stmt: Statement) -> Statement:
    if stmt.date_from and stmt.date_to and stmt.date_from > stmt.date_to:
        raise ValidationError(
            "date_from is after date_to", detail=f"{stmt.date_from} > {stmt.date_to}"
        )
    return stmt
