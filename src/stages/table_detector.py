from __future__ import annotations

import re

from src.models.document import BBox, Document, TextBlock, Word
from src.models.table import ColumnLane, Table
from src.models.trace import StageResult

_DATE_PATTERN = re.compile(r"\d{2}/\d{2}/\d{4}")
_AMOUNT_PATTERN = re.compile(r"\$\s*-?[\d.,]+")
_REF_PATTERN = re.compile(r"\b\d{6,22}\b")


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


def _word_in_lanes(word: Word, lanes: tuple[ColumnLane, ...]) -> bool:
    cx = (word.bbox.x0 + word.bbox.x1) / 2
    return any(lane.x0 <= cx <= lane.x1 for lane in lanes)


def _block_lane_overlap(
    block: TextBlock,
    lanes: tuple[ColumnLane, ...],
    threshold: float = 0.8,
) -> bool:
    if not block.words:
        return False
    hits = sum(1 for w in block.words if _word_in_lanes(w, lanes))
    return hits / len(block.words) >= threshold


def _has_key_pattern(block: TextBlock) -> bool:
    text = " ".join(w.text for w in block.words)
    return bool(_DATE_PATTERN.search(text) or _AMOUNT_PATTERN.search(text))


def detect(doc: Document) -> tuple[list[Table], StageResult]:
    tables: list[Table] = []
    total_blocks = 0
    date_anchors = 0

    for page in doc.pages:
        blocks = page.blocks
        total_blocks += len(blocks)

        anchor_indices: list[int] = []
        for i, block in enumerate(blocks):
            text = " ".join(w.text for w in block.words)
            if _DATE_PATTERN.search(text):
                anchor_indices.append(i)

        if len(anchor_indices) < 3:
            fallback: list[int] = []
            for i, block in enumerate(blocks):
                text = " ".join(w.text for w in block.words)
                if _AMOUNT_PATTERN.search(text):
                    fallback.append(i)
            if len(fallback) >= 3:
                anchor_indices = fallback

        if len(anchor_indices) < 3:
            continue

        date_anchors += len(anchor_indices)
        first_anchor = blocks[anchor_indices[0]]
        last_anchor = blocks[anchor_indices[-1]]
        table_top = first_anchor.bbox.top
        table_bottom = last_anchor.bbox.bottom

        region_words: list[Word] = []
        for block in blocks:
            if table_top <= block.bbox.top <= table_bottom:
                region_words.extend(block.words)

        lanes = _detect_lanes(region_words)
        if not lanes:
            continue

        table_words: list[Word] = []
        table_blocks: list[TextBlock] = []
        consecutive_misses = 0

        for block in blocks:
            if block.bbox.bottom < table_top or block.bbox.top > table_bottom:
                continue

            has_key = _has_key_pattern(block)

            if _block_lane_overlap(block, lanes):
                table_blocks.append(block)
                table_words.extend(block.words)
                consecutive_misses = 0
            elif has_key:
                table_blocks.append(block)
                table_words.extend(block.words)
                consecutive_misses = 0
            else:
                consecutive_misses += 1
                if consecutive_misses > 2:
                    break

        if not table_blocks:
            continue

        x0 = min(b.bbox.x0 for b in table_blocks)
        x1 = max(b.bbox.x1 for b in table_blocks)
        top = min(b.bbox.top for b in table_blocks)
        bottom = max(b.bbox.bottom for b in table_blocks)

        tables.append(Table(
            lanes=lanes,
            raw_words=tuple(table_words),
            bbox=BBox(x0=x0, x1=x1, top=top, bottom=bottom),
            page_number=page.number,
        ))

    confidence = min(1.0, date_anchors / 9.0) if tables else 0.0
    warnings = () if tables else ("No se detectaron tablas en ninguna pagina",)

    return tables, StageResult(
        stage_name="table_detector",
        confidence=confidence,
        metrics={
            "tables_found": len(tables),
            "total_blocks": total_blocks,
            "date_anchors": date_anchors,
        },
        warnings=warnings,
    )
