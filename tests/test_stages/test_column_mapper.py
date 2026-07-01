from __future__ import annotations

from src.models.table import ColumnType
from src.stages.column_mapper import map_columns

from .helpers import make_lane, make_merged_row, make_merged_table, make_row


def test_empty_rows_returns_empty():
    merged = make_merged_table([])
    rows = map_columns(merged)
    assert len(rows) == 0


def test_maps_date_description_amount():
    lanes = (
        make_lane(0, 50, ColumnType.DATE, 0.95),
        make_lane(60, 120, ColumnType.DESCRIPTION, 0.7),
        make_lane(130, 180, ColumnType.AMOUNT, 0.85),
    )
    row = make_merged_row(make_row([(0, "01/01/2026"), (1, "DESC A"), (2, "1.000,00")], top=10))
    merged = make_merged_table([row], lanes)
    rows = map_columns(merged)
    assert len(rows) == 1
    assert rows[0].date == "01/01/2026"
    assert rows[0].description == "DESC A"
    assert rows[0].amount == "1.000,00"


def test_maps_balance_column():
    lanes = (
        make_lane(0, 50, ColumnType.DATE, 0.95),
        make_lane(60, 120, ColumnType.DESCRIPTION, 0.7),
        make_lane(130, 180, ColumnType.AMOUNT, 0.85),
        make_lane(190, 250, ColumnType.BALANCE, 0.85),
    )
    cells = [(0, "01/01/2026"), (1, "DESC"), (2, "100,00"), (3, "1.000,00")]
    row = make_merged_row(make_row(cells, top=10))
    merged = make_merged_table([row], lanes)
    rows = map_columns(merged)
    assert rows[0].balance == "1.000,00"


def test_unknown_columns_become_metadata():
    lanes = (
        make_lane(0, 50, ColumnType.DATE, 0.95),
        make_lane(60, 120, ColumnType.UNKNOWN, 0.3),
        make_lane(130, 180, ColumnType.AMOUNT, 0.85),
    )
    row = make_merged_row(make_row([(0, "01/01/2026"), (1, "REF123"), (2, "100,00")], top=10))
    merged = make_merged_table([row], lanes)
    rows = map_columns(merged)
    assert len(rows[0].metadata) > 0


def test_continuation_appends_to_description():
    lanes = (
        make_lane(0, 50, ColumnType.DATE, 0.95),
        make_lane(60, 120, ColumnType.DESCRIPTION, 0.7),
        make_lane(130, 180, ColumnType.AMOUNT, 0.85),
    )
    primary = make_row([(0, "01/01/2026"), (1, "TRANSF"), (2, "100,00")], top=10)
    cont = make_row([(1, "BANCO DESTINO")], is_continuation=True, top=30)
    row = make_merged_row(primary, [cont])
    merged = make_merged_table([row], lanes)
    rows = map_columns(merged)
    assert rows[0].description == "TRANSF BANCO DESTINO"
