from __future__ import annotations

from src.models.canonical import NormalizedRow
from src.stages.transaction_builder import build


def test_empty_rows_returns_empty():
    tx_list = build([])
    assert len(tx_list) == 0


def test_single_transaction():
    rows = [
        NormalizedRow(
            date="01/01/2026", description="TEST",
            amount="1.000,00", balance="10.000,00", metadata={},
        ),
    ]
    tx_list = build(rows)
    assert len(tx_list) == 1
    assert tx_list[0].description == "TEST"
    assert float(tx_list[0].amount.signed_value) == 1000.00
    assert float(tx_list[0].balance.signed_value) == 10000.00


def test_null_date_skips_row():
    rows = [
        NormalizedRow(
            date="01/01/2026", description="VALID",
            amount="100,00", balance=None, metadata={},
        ),
        NormalizedRow(
            date=None, description="SKIPPED",
            amount="200,00", balance=None, metadata={},
        ),
    ]
    tx_list = build(rows)
    assert len(tx_list) == 1


def test_null_amount_uses_zero():
    rows = [
        NormalizedRow(
            date="01/01/2026", description="TEST",
            amount=None, balance=None, metadata={},
        ),
    ]
    tx_list = build(rows)
    assert len(tx_list) == 1
    assert float(tx_list[0].amount.signed_value) == 0.0


def test_multiple_transactions():
    a = NormalizedRow(date="01/01/2026", description="A", amount="100,00", balance=None, metadata={})
    b = NormalizedRow(date="02/01/2026", description="B", amount="200,00", balance=None, metadata={})
    tx_list = build([a, b])
    assert len(tx_list) == 2
