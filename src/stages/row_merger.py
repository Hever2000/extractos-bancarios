from __future__ import annotations

from src.models.table import ColumnType, MergedRow, MergedTable, Row, Table
from src.models.trace import StageResult


def merge(table: Table) -> tuple[MergedTable, StageResult]:
    if not table.rows:
        return MergedTable(lanes=table.lanes), StageResult(
            stage_name="row_merger",
            confidence=1.0,
            metrics={"merged_rows": 0, "orphan_continuations": 0},
            warnings=(),
        )

    merged: list[MergedRow] = []
    pending: list[Row] = []
    orphans = 0

    for row in table.rows:
        if row.is_continuation:
            has_amount = row.has_column_type(ColumnType.AMOUNT, table.lanes)
            if has_amount:
                if merged:
                    merged.append(MergedRow(primary_line=row))
                else:
                    orphans += 1
            elif merged:
                pending.append(row)
            else:
                orphans += 1
        else:
            if pending and merged:
                last = merged.pop()
                merged.append(MergedRow(
                    primary_line=last.primary_line,
                    continuation_lines=last.continuation_lines + tuple(pending),
                ))
                pending = []
            merged.append(MergedRow(primary_line=row))

    if pending and merged:
        last = merged.pop()
        merged.append(MergedRow(
            primary_line=last.primary_line,
            continuation_lines=last.continuation_lines + tuple(pending),
        ))

    warnings: tuple[str, ...] = ()
    if orphans:
        warnings = (f"{orphans} filas huerfanas descartadas (continuacion sin fila primaria)",)

    return MergedTable(
        lanes=table.lanes,
        merged_rows=tuple(merged),
    ), StageResult(
        stage_name="row_merger",
        confidence=1.0 if not orphans else 0.5,
        metrics={
            "merged_rows": sum(
                len(mr.continuation_lines) for mr in merged
            ),
            "orphan_continuations": orphans,
        },
        warnings=warnings,
    )
