from __future__ import annotations

import re

from src.models.document import BBox, Document, Page, TextBlock, Word

_DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_AMOUNT_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$|^-?\d+\.\d{2}$")
_HEADER_LIKE = re.compile(
    r"^(Fecha|Nro\.|Causal|Concepto|Importe|Saldo|Monto|Referencia|"
    r"Valor|Moneda|Pesos|Tipo|N[uú]mero|Documento|Detalle)",
    re.I,
)
_DESC_MERGE_GAP = 5.0


def _is_pure_description(block: TextBlock) -> bool:
    text = " ".join(w.text for w in block.words).strip()
    if not text:
        return False
    if _HEADER_LIKE.match(block.words[0].text):
        return False
    return not any(
        _DATE_RE.match(w.text) or _AMOUNT_RE.match(w.text) for w in block.words
    )


def _is_data_block(block: TextBlock) -> bool:
    return bool(block.words and _DATE_RE.match(block.words[0].text))


def _merge_description_data_blocks(blocks: tuple[TextBlock, ...]) -> tuple[TextBlock, ...]:
    if not blocks:
        return ()

    merged: list[TextBlock] = []
    pending_desc: list[TextBlock] = []

    for block in blocks:
        if _is_data_block(block):
            if pending_desc:
                last_gap = block.bbox.top - pending_desc[-1].bbox.bottom
                if last_gap <= _DESC_MERGE_GAP:
                    all_words: list[Word] = []
                    for desc_block in pending_desc:
                        all_words.extend(desc_block.words)
                    all_words.extend(block.words)

                    data_top = block.bbox.top
                    data_bottom = block.bbox.bottom
                    adjusted: list[Word] = []
                    for w in all_words:
                        if abs(w.bbox.top - data_top) <= 1.0:
                            adjusted.append(w)
                        else:
                            adjusted.append(Word(
                                text=w.text,
                                bbox=BBox(
                                    x0=w.bbox.x0, x1=w.bbox.x1,
                                    top=data_top, bottom=data_bottom,
                                ),
                                fontname=w.fontname,
                            ))

                    x0 = min(w.bbox.x0 for w in adjusted)
                    x1 = max(w.bbox.x1 for w in adjusted)
                    merged.append(TextBlock(
                        words=tuple(adjusted),
                        bbox=BBox(x0=x0, x1=x1, top=data_top, bottom=data_bottom),
                    ))
                else:
                    merged.extend(pending_desc)
                    merged.append(block)
                pending_desc = []
            else:
                merged.append(block)
        elif _is_pure_description(block):
            if pending_desc:
                gap = block.bbox.top - pending_desc[-1].bbox.bottom
                if gap <= _DESC_MERGE_GAP:
                    pending_desc.append(block)
                else:
                    merged.extend(pending_desc)
                    pending_desc = [block]
            else:
                pending_desc.append(block)
        else:
            merged.extend(pending_desc)
            pending_desc = []
            merged.append(block)

    merged.extend(pending_desc)
    return tuple(merged)


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
        blocks = _merge_description_data_blocks(blocks)
        pages.append(Page(
            number=page.number,
            width=page.width,
            height=page.height,
            words=page.words,
            blocks=blocks,
        ))
    return Document(pages=tuple(pages))
