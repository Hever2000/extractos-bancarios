from __future__ import annotations

from src.models.table import ColumnType
from src.stages.column_detector import _classify_values, detect

from .helpers import make_table, make_word


def test_classify_all_dates():
    values = ["01/01/2026", "02/01/2026", "03/01/2026"]
    col_type, conf = _classify_values(values)
    assert col_type == ColumnType.DATE
    assert conf == 0.95


def test_classify_mixed_dates_not_all():
    values = ["01/01/2026", "02/01/2026", "TEXTO"]
    col_type, _ = _classify_values(values)
    assert col_type != ColumnType.DATE


def test_classify_amounts():
    values = ["1.000,00", "2.500,50", "0,00"]
    col_type, conf = _classify_values(values)
    assert col_type == ColumnType.AMOUNT
    assert conf == 0.85


def test_classify_amounts_with_dollar_prefix():
    values = ["$ 1.000,00", "$ 2.500,50", "$ 0,00"]
    col_type, _ = _classify_values(values)
    assert col_type == ColumnType.AMOUNT


def test_classify_amounts_with_dollar_and_negative():
    values = ["$ -57.640,00", "$ 200.000,00", "$ 0,00"]
    col_type, _ = _classify_values(values)
    assert col_type == ColumnType.AMOUNT


def test_classify_references():
    values = ["123456", "789012", "345678"]
    col_type, _ = _classify_values(values)
    assert col_type == ColumnType.REFERENCE


def test_classify_descriptions():
    values = ["TRANSF BANCO", "PAGO HONORARIOS", "COMPRA TARJETA"]
    col_type, _ = _classify_values(values)
    assert col_type == ColumnType.DESCRIPTION


def test_classify_empty_returns_unknown():
    col_type, conf = _classify_values([])
    assert col_type == ColumnType.UNKNOWN
    assert conf == 0.0


def test_last_amount_becomes_balance():
    words = [
        make_word("01/01/2026", x0=10, top=10),
        make_word("DESC", x0=80, top=10),
        make_word("1.000,00", x0=150, top=10),
        make_word("10.000,00", x0=220, top=10),
        make_word("02/01/2026", x0=10, top=30),
        make_word("DESC2", x0=80, top=30),
        make_word("2.000,00", x0=150, top=30),
        make_word("12.000,00", x0=220, top=30),
    ]
    table = make_table(words)
    updated = detect(table)
    types = [lane.detected_type for lane in updated.lanes]
    assert ColumnType.AMOUNT in types
    assert ColumnType.BALANCE in types


def test_no_raw_words_returns_unknown():
    table = make_table([])
    result = detect(table)
    assert result == table
