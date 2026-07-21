from datetime import date
from decimal import Decimal

import pytest

from src.models.bank import Bank, BankId
from src.models.errors import ValidationError
from src.models.statement import Amount, Sign, Statement, Transaction
from src.validators.schema import validate_statement


def _make_bank() -> Bank:
    return Bank(
        id=BankId.MACRO,
        text_patterns=[],
        filename_patterns=[],
        cbu_prefix="285",
    )


def _make_tx(day: int) -> Transaction:
    return Transaction(
        date=date(2025, 12, day),
        description="TEST",
        amount=Amount(value=Decimal("100"), sign=Sign(1)),
        balance=Amount(value=Decimal("1000"), sign=Sign(1)),
    )


def test_valid_statement():
    stmt = Statement(
        bank=_make_bank(),
        transactions=(_make_tx(1), _make_tx(15)),
        date_from=date(2025, 12, 1),
        date_to=date(2025, 12, 15),
    )
    result = validate_statement(stmt)
    assert result == stmt


def test_empty_transactions():
    stmt = Statement(
        bank=_make_bank(),
        transactions=(),
        date_from=None,
        date_to=None,
    )
    result = validate_statement(stmt)
    assert result == stmt


def test_duplicate_transactions():
    tx = _make_tx(1)
    stmt = Statement(
        bank=_make_bank(),
        transactions=(tx, tx),
        date_from=date(2025, 12, 1),
        date_to=date(2025, 12, 1),
    )
    result = validate_statement(stmt)
    assert result == stmt


def test_date_mismatch_raises():
    stmt = Statement(
        bank=_make_bank(),
        transactions=(_make_tx(15),),
        date_from=date(2025, 12, 31),
        date_to=date(2025, 12, 1),
    )
    with pytest.raises(ValidationError, match="date_from is after date_to"):
        validate_statement(stmt)
