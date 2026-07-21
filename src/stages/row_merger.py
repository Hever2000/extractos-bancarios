from __future__ import annotations

from src.models.table import ColumnType, MergedRow, MergedTable, Row, Table


def merge(table: Table) -> MergedTable:
    if not table.rows:
        return MergedTable(lanes=table.lanes)

    merged: list[MergedRow] = []
    pending: list[Row] = []
    merge_count = 0

    for row in table.rows:
        if row.is_continuation:
            has_amount = row.has_column_type(ColumnType.AMOUNT, table.lanes)
            if has_amount:
                if merged:
                    merged.append(MergedRow(primary_line=row))
            elif merged:
                pending.append(row)
        else:
            if pending and merged:
                last = merged.pop()
                merged.append(MergedRow(
                    primary_line=last.primary_line,
                    continuation_lines=last.continuation_lines + tuple(pending),
                ))
                merge_count += 1
                pending = []
            merged.append(MergedRow(primary_line=row))

    if pending and merged:
        last = merged.pop()
        merged.append(MergedRow(
            primary_line=last.primary_line,
            continuation_lines=last.continuation_lines + tuple(pending),
        ))
        merge_count += 1

    return MergedTable(
        lanes=table.lanes,
        merged_rows=tuple(merged),
    )
