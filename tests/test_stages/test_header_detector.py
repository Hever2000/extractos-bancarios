from __future__ import annotations

from src.stages.block_builder import build as build_blocks
from src.stages.header_detector import filter_headers

from .helpers import make_document, make_page, make_table, make_word


def _doc_with_header_and_table():
    words = [
        make_word("EXTRACTO DE CUENTA", x0=10, top=10),
        make_word("BANCO MACRO", x0=10, top=30),
        make_word("01/01/2026", x0=10, top=100),
        make_word("DESC", x0=60, top=100),
    ]
    doc = make_document([make_page(words, number=1)])
    doc = build_blocks(doc)
    table = make_table(words[2:], page_number=1)
    return doc, [table]


def test_header_above_table_removed():
    doc, tables = _doc_with_header_and_table()
    result = filter_headers(doc, tables)
    assert result is not None


def test_no_tables_removes_nothing():
    doc, _ = _doc_with_header_and_table()
    result = filter_headers(doc, [])
    assert result is not None
