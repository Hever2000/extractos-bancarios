from __future__ import annotations

from src.stages.block_builder import build as build_blocks
from src.stages.footer_detector import filter_footers

from .helpers import make_document, make_page, make_table, make_word


def test_footer_below_table_removed():
    words = [
        make_word("01/01/2026", x0=10, top=100),
        make_word("DESC", x0=60, top=100),
        make_word("Fecha de descarga:", x0=10, top=500),
    ]
    doc = make_document([make_page(words, number=1)])
    doc = build_blocks(doc)
    table = make_table(words[:2], page_number=1)
    result = filter_footers(doc, [table])
    assert result is not None


def test_no_tables_removes_nothing():
    words = [make_word("Fecha de descarga:", x0=10, top=10)]
    doc = make_document([make_page(words, number=1)])
    doc = build_blocks(doc)
    result = filter_footers(doc, [])
    assert result is not None
