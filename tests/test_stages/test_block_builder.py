from __future__ import annotations

from src.stages.block_builder import _group_words_into_lines, build

from .helpers import make_document, make_page, make_word


def test_empty_words_returns_empty():
    result = _group_words_into_lines(())
    assert result == ()


def test_single_word_is_one_block():
    words = (make_word("HOLA", x0=10, top=10),)
    blocks = _group_words_into_lines(words)
    assert len(blocks) == 1
    assert blocks[0].words[0].text == "HOLA"


def test_words_on_same_line_grouped():
    words = (
        make_word("HOLA", x0=10, top=10),
        make_word("MUNDO", x0=60, top=10),
    )
    blocks = _group_words_into_lines(words)
    assert len(blocks) == 1
    texts = [w.text for w in blocks[0].words]
    assert texts == ["HOLA", "MUNDO"]


def test_words_on_different_lines_separated():
    words = (
        make_word("LINEA1", x0=10, top=10),
        make_word("LINEA2", x0=10, top=30),
    )
    blocks = _group_words_into_lines(words)
    assert len(blocks) == 2


def test_words_sorted_by_x0_within_line():
    words = (
        make_word("B", x0=60, top=10),
        make_word("A", x0=10, top=10),
    )
    blocks = _group_words_into_lines(words)
    assert len(blocks) == 1
    texts = [w.text for w in blocks[0].words]
    assert texts == ["A", "B"]


def test_build_populates_blocks():
    doc = make_document([
        make_page([make_word("A", x0=10, top=10), make_word("B", x0=60, top=30)], number=1),
    ])
    result = build(doc)
    assert len(result.pages) == 1
    assert len(result.pages[0].blocks) == 2


def test_build_preserves_words():
    doc = make_document([
        make_page([make_word("TEST", x0=10, top=10)], number=1),
    ])
    result = build(doc)
    assert len(result.pages[0].words) == 1
    assert result.pages[0].words[0].text == "TEST"
