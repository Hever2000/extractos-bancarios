from __future__ import annotations

from src.models.document import BBox, Document, Page, Word
from src.models.table import ColumnLane, ColumnType, MergedRow, MergedTable, Row, Table


def make_word(
    text: str, x0: float, top: float,
    x1: float | None = None, bottom: float | None = None,
) -> Word:
    width = x1 if x1 is not None else x0 + len(text) * 5
    height = bottom if bottom is not None else top + 10
    return Word(text=text, bbox=BBox(x0=x0, x1=width, top=top, bottom=height))


def make_page(words: list[Word], number: int = 1, width: float = 600, height: float = 800) -> Page:
    return Page(number=number, width=width, height=height, words=tuple(words))


def make_document(pages: list[Page]) -> Document:
    return Document(pages=tuple(pages))


def make_table(
    words: list[Word],
    lanes: tuple[ColumnLane, ...] = (),
    rows: tuple[Row, ...] = (),
    page_number: int = 1,
) -> Table:
    xs = [w.bbox.x0 for w in words]
    ys = [w.bbox.top for w in words]
    xe = [w.bbox.x1 for w in words]
    ye = [w.bbox.bottom for w in words]
    bbox = BBox(x0=min(xs), x1=max(xe), top=min(ys), bottom=max(ye)) if words else None
    return Table(
        lanes=lanes,
        rows=rows,
        raw_words=tuple(words),
        bbox=bbox,
        page_number=page_number,
    )


def make_lane(
    x0: float, x1: float,
    col_type: ColumnType = ColumnType.UNKNOWN,
    confidence: float = 0.0,
) -> ColumnLane:
    return ColumnLane(x0=x0, x1=x1, detected_type=col_type, confidence=confidence)


def make_row(
    cells: list[tuple[int, str]], is_continuation: bool = False, top: float = 0.0,
) -> Row:
    from src.models.table import Cell

    cell_bbox = BBox(x0=0, x1=10, top=top, bottom=top + 10)
    row_cells = [Cell(text=text, lane_index=lane_idx, bbox=cell_bbox) for lane_idx, text in cells]
    row_bbox = BBox(x0=0, x1=100, top=top, bottom=top + 10)
    return Row(
        cells=tuple(row_cells), is_continuation=is_continuation,
        bbox=row_bbox, page_number=1,
    )


def make_merged_row(primary: Row, continuations: list[Row] | None = None) -> MergedRow:
    return MergedRow(primary_line=primary, continuation_lines=tuple(continuations or []))


def make_merged_table(rows: list[MergedRow], lanes: tuple[ColumnLane, ...] = ()) -> MergedTable:
    return MergedTable(lanes=lanes, merged_rows=tuple(rows))
