from __future__ import annotations

from dataclasses import dataclass

from src.extractors.account import extract_account
from src.extractors.account_type import extract_account_type
from src.extractors.cbu import extract_cbu
from src.models.bank import Bank
from src.models.document import Document, TextBlock
from src.models.table import Table


@dataclass(frozen=True)
class StatementMetadata:
    cbu: str | None
    account: str | None
    account_type: str | None


def _get_header_footer_blocks(
    doc: Document,
    tables: list[Table],
) -> tuple[list[tuple[TextBlock, int]], list[tuple[TextBlock, int]]]:
    header: list[tuple[TextBlock, int]] = []
    footer: list[tuple[TextBlock, int]] = []
    table_by_page: dict[int, Table] = {}
    for t in tables:
        if t.bbox is not None and t.page_number not in table_by_page:
            table_by_page[t.page_number] = t

    for page in doc.pages:
        table = table_by_page.get(page.number)
        if table is None or table.bbox is None:
            continue
        for block in page.blocks:
            if block.bbox.bottom < table.bbox.top:
                header.append((block, page.number))
            elif block.bbox.top > table.bbox.bottom:
                footer.append((block, page.number))

    return header, footer


def extract_statement_metadata(
    doc: Document,
    tables: list[Table],
    bank: Bank | None = None,
) -> StatementMetadata:
    header_blocks, footer_blocks = _get_header_footer_blocks(doc, tables)
    cbu = extract_cbu(header_blocks, footer_blocks, bank)
    account = extract_account(header_blocks, footer_blocks)
    account_type = extract_account_type(header_blocks, footer_blocks)
    return StatementMetadata(cbu=cbu, account=account, account_type=account_type)
