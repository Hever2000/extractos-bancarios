from __future__ import annotations

from src.stages.table_detector import detect

from .helpers import make_document, make_page, make_word


def _doc_with_blocks(words: list) -> object:
    from src.stages.block_builder import build
    doc = make_document([make_page(words, number=1)])
    return build(doc)


def test_no_date_anchors_returns_empty():
    doc = _doc_with_blocks([make_word("SIN", x0=10, top=10), make_word("FECHAS", x0=50, top=30)])
    tables = detect(doc)
    assert len(tables) == 0


def test_fewer_than_3_date_anchors_returns_empty():
    doc = _doc_with_blocks([
        make_word("01/01/2026", x0=10, top=10),
        make_word("OTRO", x0=50, top=30),
        make_word("02/01/2026", x0=10, top=50),
        make_word("TEXTO", x0=50, top=70),
    ])
    tables = detect(doc)
    assert len(tables) == 0


def test_3_date_anchors_detects_table():
    doc = _doc_with_blocks([
        make_word("01/01/2026", x0=10, top=10),
        make_word("DESC A", x0=60, top=10),
        make_word("02/01/2026", x0=10, top=30),
        make_word("DESC B", x0=60, top=30),
        make_word("03/01/2026", x0=10, top=50),
        make_word("DESC C", x0=60, top=50),
    ])
    tables = detect(doc)
    assert len(tables) >= 1


def test_table_bbox_contains_all_anchors():
    doc = _doc_with_blocks([
        make_word("01/01/2026", x0=10, top=10),
        make_word("100,00", x0=60, top=10),
        make_word("02/01/2026", x0=10, top=30),
        make_word("200,00", x0=60, top=30),
        make_word("03/01/2026", x0=10, top=50),
        make_word("300,00", x0=60, top=50),
    ])
    tables = detect(doc)
    assert len(tables) == 1
    t = tables[0]
    assert t.bbox is not None
    assert t.bbox.top <= 10
    assert t.bbox.bottom >= 50


def test_amount_fallback_when_no_dates():
    doc = _doc_with_blocks([
        make_word("$ 100,00", x0=10, top=10),
        make_word("DESC A", x0=60, top=10),
        make_word("$ 200,00", x0=10, top=30),
        make_word("DESC B", x0=60, top=30),
        make_word("$ 300,00", x0=10, top=50),
        make_word("DESC C", x0=60, top=50),
    ])
    tables = detect(doc)
    assert len(tables) >= 1
