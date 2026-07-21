from __future__ import annotations

import re

from src.models.document import BBox, Document, TextBlock, Word
from src.models.table import ColumnLane, Table
from src.stages._utils import detect_lanes

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_AMOUNT_PATTERN_FULL = re.compile(
    r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$"   # 1.000,00 (coma decimal)
    r"|^-?\d+\.\d{2}$"                 # 21000.00 (punto decimal)
    r"|^\$\s*-?[\d.,]+$"              # $ 1.000,00
)


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
    return any(
        _DATE_RE.match(w.text) or _AMOUNT_PATTERN_FULL.match(w.text)
        for w in block.words
    )


def detect(doc: Document) -> list[Table]:
    tables: list[Table] = []

    for page in doc.pages:
        blocks = page.blocks

        anchor_indices: list[int] = []
        for i, block in enumerate(blocks):
            if block.words and _DATE_RE.match(block.words[0].text):
                anchor_indices.append(i)


        if len(anchor_indices) < 3:
            fallback: list[int] = []
            for i, block in enumerate(blocks):
                if any(_AMOUNT_PATTERN_FULL.match(w.text) for w in block.words):
                    fallback.append(i)
            if len(fallback) >= 3:
                anchor_indices = fallback
        if len(anchor_indices) < 3:
            continue

        first_anchor = blocks[anchor_indices[0]]
        last_anchor = blocks[anchor_indices[-1]]
        table_top = first_anchor.bbox.top
        table_bottom = last_anchor.bbox.bottom

        region_words: list[Word] = []
        for block in blocks:
            if table_top <= block.bbox.top <= table_bottom:
                region_words.extend(block.words)

        lanes = detect_lanes(region_words)

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
    return tables
