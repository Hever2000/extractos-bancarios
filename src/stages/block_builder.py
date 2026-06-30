from __future__ import annotations

from src.models.document import BBox, Document, Page, TextBlock, Word


def _group_words_into_lines(
    words: tuple[Word, ...],
    y_tolerance: float = 3.0,
) -> tuple[TextBlock, ...]:
    if not words:
        return ()

    sorted_words = sorted(words, key=lambda w: (w.bbox.top, w.bbox.x0))
    lines: list[list[Word]] = []
    current_line: list[Word] = [sorted_words[0]]

    for word in sorted_words[1:]:
        if abs(word.bbox.top - current_line[0].bbox.top) <= y_tolerance:
            current_line.append(word)
        else:
            lines.append(current_line)
            current_line = [word]

    if current_line:
        lines.append(current_line)

    blocks: list[TextBlock] = []
    for line_words in lines:
        line_words.sort(key=lambda w: w.bbox.x0)
        x0 = min(w.bbox.x0 for w in line_words)
        x1 = max(w.bbox.x1 for w in line_words)
        top = min(w.bbox.top for w in line_words)
        bottom = max(w.bbox.bottom for w in line_words)
        blocks.append(TextBlock(
            words=tuple(line_words),
            bbox=BBox(x0=x0, x1=x1, top=top, bottom=bottom),
        ))

    return tuple(blocks)


def build(doc: Document) -> Document:
    pages: list[Page] = []
    for page in doc.pages:
        blocks = _group_words_into_lines(page.words)
        pages.append(Page(
            number=page.number,
            width=page.width,
            height=page.height,
            words=page.words,
            blocks=blocks,
        ))
    return Document(pages=tuple(pages))
