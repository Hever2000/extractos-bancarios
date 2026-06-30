from __future__ import annotations

from src.models.canonical import NormalizedRow
from src.models.table import ColumnType, MergedTable
from src.models.trace import StageResult


def map_columns(merged: MergedTable) -> tuple[list[NormalizedRow], StageResult]:
    if not merged.merged_rows:
        return [], StageResult(
            stage_name="column_mapper",
            confidence=0.0,
            metrics={"mapped_rows": 0, "unmapped_columns": 0},
            warnings=("No merged rows to map",),
        )

    rows: list[NormalizedRow] = []
    prev_date: str | None = None
    unmapped = sum(
        1 for lane in merged.lanes if lane.detected_type == ColumnType.UNKNOWN
    )

    for mrow in merged.merged_rows:
        cells_by_lane: dict[int, str] = {}
        for c in mrow.primary_line.cells:
            cells_by_lane[c.lane_index] = c.text

        for crow in mrow.continuation_lines:
            for c in crow.cells:
                lane = merged.lanes[c.lane_index]
                if lane.detected_type == ColumnType.DESCRIPTION:
                    existing = cells_by_lane.get(c.lane_index, "")
                    cells_by_lane[c.lane_index] = (existing + " " + c.text).strip()

        date_val: str | None = None
        desc_parts: list[str] = []
        amount_val: str | None = None
        balance_val: str | None = None
        metadata: dict[str, str] = {}

        for i, lane in enumerate(merged.lanes):
            text = cells_by_lane.get(i, "")
            if lane.detected_type == ColumnType.DATE:
                date_val = text
            elif lane.detected_type == ColumnType.DESCRIPTION:
                if text:
                    desc_parts.append(text)
            elif lane.detected_type == ColumnType.AMOUNT:
                amount_val = text
            elif lane.detected_type == ColumnType.BALANCE:
                balance_val = text
            else:
                if text.strip():
                    key = lane.header_text or f"columna_{i}"
                    metadata[key] = text.strip()

        if date_val is None and amount_val is not None:
            date_val = prev_date

        prev_date = date_val

        rows.append(NormalizedRow(
            date=date_val,
            description=" ".join(desc_parts).strip(),
            amount=amount_val,
            balance=balance_val,
            metadata=metadata,
        ))

    return rows, StageResult(
        stage_name="column_mapper",
        confidence=min(1.0, len(rows) / max(len(merged.merged_rows), 1)),
        metrics={
            "mapped_rows": len(rows),
            "unmapped_columns": unmapped,
        },
        warnings=(),
    )
