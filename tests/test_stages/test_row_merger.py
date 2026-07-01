from __future__ import annotations

from src.models.table import ColumnType
from src.stages.row_merger import merge

from .helpers import make_lane, make_row, make_table


def test_empty_rows_returns_empty():
    table = make_table([], lanes=(make_lane(0, 50, ColumnType.DATE),))
    merged = merge(table)
    assert len(merged.merged_rows) == 0


def test_primary_rows_remain_primary():
    lanes = (make_lane(0, 50, ColumnType.DATE), make_lane(60, 120, ColumnType.DESCRIPTION))
    rows = (
        make_row([(0, "01/01/2026"), (1, "DESC A")], top=10),
        make_row([(0, "02/01/2026"), (1, "DESC B")], top=30),
    )
    table = make_table([], lanes=lanes, rows=rows)
    merged = merge(table)
    assert len(merged.merged_rows) == 2


def test_continuation_merged_with_previous():
    lanes = (make_lane(0, 50, ColumnType.DATE), make_lane(60, 120, ColumnType.DESCRIPTION))
    rows = (
        make_row([(0, "01/01/2026"), (1, "DESC A")], top=10),
        make_row([(1, "CONTINUA")], is_continuation=True, top=30),
    )
    table = make_table([], lanes=lanes, rows=rows)
    merged = merge(table)
    assert len(merged.merged_rows) == 1
    assert len(merged.merged_rows[0].continuation_lines) == 1


def test_continuation_with_amount_becomes_new_row():
    lanes = (
        make_lane(0, 50, ColumnType.DATE),
        make_lane(60, 120, ColumnType.DESCRIPTION),
        make_lane(130, 180, ColumnType.AMOUNT),
    )
    rows = (
        make_row([(0, "01/01/2026"), (1, "PRIMERA"), (2, "1.000,00")], top=10),
        make_row([(1, "SIN FECHA"), (2, "2.000,00")], is_continuation=True, top=30),
    )
    table = make_table([], lanes=lanes, rows=rows)
    merged = merge(table)
    assert len(merged.merged_rows) == 2
