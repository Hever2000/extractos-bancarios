from __future__ import annotations

from src.models.document import Word
from src.models.table import ColumnLane


def detect_lanes(words: list[Word], gap_threshold: float = 8.0) -> tuple[ColumnLane, ...]:
    if not words:
        return ()

    intervals = sorted(
        [(w.bbox.x0, w.bbox.x1) for w in words],
        key=lambda i: i[0],
    )

    lanes: list[ColumnLane] = []
    cur_x0, cur_x1 = intervals[0]

    for x0, x1 in intervals[1:]:
        if x0 - cur_x1 > gap_threshold:
            lanes.append(ColumnLane(x0=cur_x0, x1=cur_x1))
            cur_x0, cur_x1 = x0, x1
        else:
            cur_x1 = max(cur_x1, x1)

    lanes.append(ColumnLane(x0=cur_x0, x1=cur_x1))
    return tuple(lanes)
