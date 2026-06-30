from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from src.models.document import BBox, Word


class ColumnType(Enum):
    DATE = auto()
    AMOUNT = auto()
    BALANCE = auto()
    DESCRIPTION = auto()
    REFERENCE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class ColumnLane:
    x0: float
    x1: float
    header_text: str | None = None
    detected_type: ColumnType = ColumnType.UNKNOWN
    confidence: float = 0.0
    alignment: str = "left"


@dataclass(frozen=True)
class Cell:
    text: str
    lane_index: int
    bbox: BBox


@dataclass(frozen=True)
class Row:
    cells: tuple[Cell, ...]
    is_continuation: bool
    bbox: BBox
    page_number: int

    def has_column_type(self, col_type: ColumnType, lanes: tuple[ColumnLane, ...]) -> bool:
        return any(lanes[c.lane_index].detected_type == col_type for c in self.cells)


@dataclass(frozen=True)
class Table:
    lanes: tuple[ColumnLane, ...] = ()
    rows: tuple[Row, ...] = ()
    raw_words: tuple[Word, ...] = ()
    bbox: BBox | None = None
    page_number: int = 0


@dataclass(frozen=True)
class MergedRow:
    primary_line: Row
    continuation_lines: tuple[Row, ...] = ()


@dataclass(frozen=True)
class MergedTable:
    lanes: tuple[ColumnLane, ...] = ()
    merged_rows: tuple[MergedRow, ...] = ()
