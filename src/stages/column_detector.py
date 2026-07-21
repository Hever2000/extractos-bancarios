from __future__ import annotations

import re

from src.models.document import Word
from src.models.table import ColumnLane, ColumnType, Table
from src.stages._utils import detect_lanes

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_SHORT_DATE_RE = re.compile(r"^\d{2}-\d{2}$")
_AMOUNT_RE = re.compile(r"^-?[\d.,]+$|^\$\s*-?[\d.,]+$")
_DIGIT_RE = re.compile(r"^\d+$")
_AMOUNT_SUFFIX_RE = re.compile(r"\.\d{2}$")


def _words_in_lane(lane: ColumnLane, words: list[Word]) -> list[Word]:
    return [
        w for w in words
        if lane.x0 <= (w.bbox.x0 + w.bbox.x1) / 2 <= lane.x1
    ]


def _classify_values(values: list[str]) -> tuple[ColumnType, float]:
    if not values:
        return ColumnType.UNKNOWN, 0.0

    date_matches = sum(1 for v in values if _DATE_RE.match(v))
    amount_matches = sum(
        1 for v in values
        if _AMOUNT_RE.match(v) and ("," in v or _AMOUNT_SUFFIX_RE.search(v))
    )
    digit_matches = sum(1 for v in values if _DIGIT_RE.match(v))
    ref_date_matches = sum(1 for v in values if _SHORT_DATE_RE.match(v))
    total = len(values)

    if date_matches == total:
        return ColumnType.DATE, 0.95
    if amount_matches >= total * 0.7:
        return ColumnType.AMOUNT, 0.85
    if digit_matches >= total * 0.7 or ref_date_matches >= total * 0.7:
        return ColumnType.REFERENCE, 0.75

    text_count = total - date_matches - amount_matches - digit_matches - ref_date_matches
    if text_count >= total * 0.7:
        return ColumnType.DESCRIPTION, 0.7
    if text_count >= total * 0.3:
        return ColumnType.DESCRIPTION, 0.5

    return ColumnType.UNKNOWN, 0.3


def detect(table: Table) -> Table:
    if not table.raw_words:
        return table

    words_list = list(table.raw_words)
    lanes = list(detect_lanes(words_list))

    lane_values: list[list[str]] = [[] for _ in lanes]
    for w in words_list:
        cx = (w.bbox.x0 + w.bbox.x1) / 2
        for i, lane in enumerate(lanes):
            if lane.x0 <= cx <= lane.x1:
                lane_values[i].append(w.text)
                break

    amount_count = 0
    for i, values in enumerate(lane_values):
        col_type, _ = _classify_values(values)
        lanes[i] = ColumnLane(
            x0=lanes[i].x0, x1=lanes[i].x1,
            header_text=lanes[i].header_text,
            detected_type=col_type,
            confidence=0.0,
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

    return Table(
        lanes=tuple(lanes),
        rows=table.rows,
        raw_words=table.raw_words,
        bbox=table.bbox,
        page_number=table.page_number,
    )
