from __future__ import annotations

from src.models.table import ColumnType
from src.stages.row_extractor import extract

from .helpers import make_lane, make_table, make_word


def test_empty_lanes_returns_empty():
    table = make_table([make_word("A", x0=10, top=10)])
    result = extract(table)
    assert len(result.rows) == 0


def test_single_row_extracted():
    lanes = (make_lane(0, 50, ColumnType.DATE), make_lane(60, 120, ColumnType.DESCRIPTION))
    words = [
        make_word("01/01/2026", x0=10, top=10),
        make_word("DESCRIPCION", x0=70, top=10),
    ]
    table = make_table(words, lanes=lanes)
    updated = extract(table)
    assert len(updated.rows) == 1


def test_row_without_date_is_continuation():
    lanes = (make_lane(0, 50, ColumnType.DATE), make_lane(60, 120, ColumnType.DESCRIPTION))
    words = [
        make_word("01/01/2026", x0=10, top=10),
        make_word("PRIMERA", x0=70, top=10),
        make_word("CONTINUA", x0=70, top=30),
    ]
    table = make_table(words, lanes=lanes)
    updated = extract(table)
    assert len(updated.rows) == 2
    assert not updated.rows[0].is_continuation
    assert updated.rows[1].is_continuation


def test_discarded_row_no_lane_match():
    lanes = (make_lane(100, 150, ColumnType.DATE),)
    words = [
        make_word("TEXTO_FUERA", x0=0, top=10),
    ]
    table = make_table(words, lanes=lanes)
    updated = extract(table)
    assert len(updated.rows) == 0
