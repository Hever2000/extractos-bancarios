from __future__ import annotations

from src.models.document import BBox, Word
from src.models.table import Cell, ColumnType, Row, Table
from src.models.trace import StageResult


def extract(table: Table) -> tuple[Table, StageResult]:
    if not table.lanes or not table.raw_words:
        return table, StageResult(
            stage_name="row_extractor",
            confidence=0.0,
            metrics={"total_rows": 0, "discarded_rows": 0},
            warnings=("No lanes or words to extract rows from",),
        )

    sorted_words = sorted(table.raw_words, key=lambda w: (w.bbox.top, w.bbox.x0))
    lines: list[list[Word]] = []

    current_line: list[Word] = [sorted_words[0]]
    for word in sorted_words[1:]:
        if abs(word.bbox.top - current_line[0].bbox.top) <= 3.0:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]
    if current_line:
        lines.append(current_line)

    rows: list[Row] = []
    discarded = 0

    for line_words in lines:
        lane_map: dict[int, list[Word]] = {}
        for w in line_words:
            cx = (w.bbox.x0 + w.bbox.x1) / 2
            for i, lane in enumerate(table.lanes):
                if lane.x0 <= cx <= lane.x1:
                    lane_map.setdefault(i, []).append(w)
                    break

        if not lane_map:
            discarded += 1
            continue

        cells: list[Cell] = []
        for lane_idx, words_in_lane in sorted(lane_map.items()):
            text = " ".join(w.text for w in words_in_lane)
            bbox = BBox(
                x0=min(w.bbox.x0 for w in words_in_lane),
                x1=max(w.bbox.x1 for w in words_in_lane),
                top=min(w.bbox.top for w in words_in_lane),
                bottom=max(w.bbox.bottom for w in words_in_lane),
            )
            cells.append(Cell(text=text, lane_index=lane_idx, bbox=bbox))

        first_lane_type = table.lanes[0].detected_type
        has_first_lane_content = any(c.lane_index == 0 for c in cells)
        is_cont = (
            first_lane_type == ColumnType.DATE
            and not has_first_lane_content
        )

        row_bbox = BBox(
            x0=min(c.bbox.x0 for c in cells),
            x1=max(c.bbox.x1 for c in cells),
            top=min(c.bbox.top for c in cells),
            bottom=max(c.bbox.bottom for c in cells),
        )

        rows.append(Row(
            cells=tuple(cells),
            is_continuation=is_cont,
            bbox=row_bbox,
            page_number=table.page_number,
        ))

    updated = Table(
        lanes=table.lanes,
        rows=tuple(rows),
        raw_words=table.raw_words,
        bbox=table.bbox,
        page_number=table.page_number,
    )

    return updated, StageResult(
        stage_name="row_extractor",
        confidence=1.0 if rows else 0.0,
        metrics={
            "total_rows": len(rows),
            "valid_rows": len(rows),
            "discarded_rows": discarded,
        },
        warnings=("No rows extracted",) if not rows else (),
    )
