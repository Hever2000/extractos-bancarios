from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.models.bank import Bank
from src.models.document import Document
from src.models.statement import Statement
from src.stages import (
    block_builder,
    column_detector,
    column_mapper,
    footer_detector,
    header_detector,
    row_extractor,
    row_merger,
    table_detector,
    transaction_builder,
)
from src.validators.schema import validate_statement

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MutatedResult:
    statement: Statement
    transactions_count: int
    tables_found: int
    warnings: tuple[str, ...]
    error: str | None = None


def run_mutated_pipeline(doc: Document, bank: Bank) -> MutatedResult:
    try:
        doc = block_builder.build(doc)
        tables = table_detector.detect(doc)

        if not tables:
            stmt = Statement(
                bank=bank,
                transactions=(),
                date_from=None,
                date_to=None,
            )
            stmt = validate_statement(stmt)
            return MutatedResult(
                statement=stmt,
                transactions_count=0,
                tables_found=0,
                warnings=(),
            )

        doc = header_detector.filter_headers(doc, tables)
        doc = footer_detector.filter_footers(doc, tables)

        all_normalized: list[Any] = []
        for table in tables:
            try:
                table = column_detector.detect(table)
                table = row_extractor.extract(table)
                merged = row_merger.merge(table)
                normalized_rows = column_mapper.map_columns(merged)
                all_normalized.extend(normalized_rows)
            except Exception as e:
                log.warning("Table processing failed", exc_info=e)
                continue

        transactions_raw = transaction_builder.build(all_normalized)
        transactions_raw.sort(key=lambda t: t.date)

        if not transactions_raw:
            stmt = Statement(
                bank=bank,
                transactions=(),
                date_from=None,
                date_to=None,
            )
        else:
            stmt = Statement(
                bank=bank,
                transactions=tuple(transactions_raw),
                date_from=transactions_raw[0].date,
                date_to=transactions_raw[-1].date,
            )

        stmt = validate_statement(stmt)
        return MutatedResult(
            statement=stmt,
            transactions_count=len(transactions_raw),
            tables_found=len(tables),
            warnings=(),
        )

    except Exception as e:
        return MutatedResult(
            statement=Statement(
                bank=bank,
                transactions=(),
                date_from=None,
                date_to=None,
            ),
            transactions_count=0,
            tables_found=0,
            warnings=(f"Pipeline error: {e!s}",),
            error=str(e),
        )
