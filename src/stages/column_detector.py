from __future__ import annotations

import re

from src.models.document import Word
from src.models.table import ColumnLane, ColumnType, Table
from src.models.trace import StageResult

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_AMOUNT_RE = re.compile(r"^-?[\d.,]+$")
_DIGIT_RE = re.compile(r"^\d+$")


def _detect_lanes(words: list[Word], gap_threshold: float = 8.0) -> tuple[ColumnLane, ...]:
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


def _words_in_lane(lane: ColumnLane, words: list[Word]) -> list[Word]:
    return [
        w for w in words
        if lane.x0 <= (w.bbox.x0 + w.bbox.x1) / 2 <= lane.x1
    ]


def _classify_values(values: list[str]) -> tuple[ColumnType, float]:
    if not values:
        return ColumnType.UNKNOWN, 0.0

    date_matches = sum(1 for v in values if _DATE_RE.match(v))
    amount_matches = sum(1 for v in values if _AMOUNT_RE.match(v) and "," in v)
    digit_matches = sum(1 for v in values if _DIGIT_RE.match(v))
    total = len(values)

    if date_matches == total:
        return ColumnType.DATE, 0.95
    if amount_matches >= total * 0.7:
        return ColumnType.AMOUNT, 0.85
    if digit_matches >= total * 0.7:
        return ColumnType.REFERENCE, 0.75

    text_count = total - date_matches - amount_matches - digit_matches
    if text_count >= total * 0.7:
        return ColumnType.DESCRIPTION, 0.7

    return ColumnType.UNKNOWN, 0.3


def detect(table: Table) -> tuple[Table, StageResult]:
    if not table.raw_words:
        return table, StageResult(
            stage_name="column_detector",
            confidence=0.0,
            metrics={"columns_detected": 0, "unknown_columns": 0},
            warnings=("No raw words in table region",),
        )

    words_list = list(table.raw_words)
    lanes = list(_detect_lanes(words_list))

    lane_values: list[list[str]] = [[] for _ in lanes]
    for w in words_list:
        cx = (w.bbox.x0 + w.bbox.x1) / 2
        for i, lane in enumerate(lanes):
            if lane.x0 <= cx <= lane.x1:
                lane_values[i].append(w.text)
                break

    amount_count = 0
    for i, values in enumerate(lane_values):
        col_type, confidence = _classify_values(values)
        lanes[i] = ColumnLane(
            x0=lanes[i].x0, x1=lanes[i].x1,
            header_text=lanes[i].header_text,
            detected_type=col_type,
            confidence=confidence,
            alignment=lanes[i].alignment,
        )
        if col_type == ColumnType.AMOUNT:
            amount_count += 1

    if amount_count >= 2:
        amount_indices = [
            i for i, lane in enumerate(lanes)
            if lane.detected_type == ColumnType.AMOUNT
        ]
        last_amount = amount_indices[-1]
        lanes[last_amount] = ColumnLane(
            x0=lanes[last_amount].x0, x1=lanes[last_amount].x1,
            detected_type=ColumnType.BALANCE,
            confidence=lanes[last_amount].confidence,
            alignment=lanes[last_amount].alignment,
        )

    unknown_count = sum(1 for lane in lanes if lane.detected_type == ColumnType.UNKNOWN)
    date_found = any(lane.detected_type == ColumnType.DATE for lane in lanes)
    amount_found = any(
        lane.detected_type in (ColumnType.AMOUNT, ColumnType.BALANCE) for lane in lanes
    )

    global_confidence = min(
        1.0,
        (len(lanes) - unknown_count) / max(len(lanes), 1) * 0.8
        + (0.1 if date_found else 0)
        + (0.1 if amount_found else 0),
    )

    updated = Table(
        lanes=tuple(lanes),
        rows=table.rows,
        raw_words=table.raw_words,
        bbox=table.bbox,
        page_number=table.page_number,
    )

    return updated, StageResult(
        stage_name="column_detector",
        confidence=global_confidence,
        metrics={
            "columns_detected": len(lanes),
            "unknown_columns": unknown_count,
            "date_found": 1 if date_found else 0,
            "amount_found": 1 if amount_found else 0,
        },
        warnings=(),
    )
