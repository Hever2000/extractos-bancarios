from __future__ import annotations

import re

from src.models.bank import Bank
from src.models.document import TextBlock

_CBU_LABEL_RE = re.compile(
    r"\bCBU\b|CBU\s*N[°º]|"
    r"Código\s+Bancario\s+Uniforme|"
    r"Clave\s+Bancaria\s+Uniforme",
    re.I,
)
_22_DIGIT_RE = re.compile(r"\b(\d{22})\b")
_NEARBY_KEYWORDS_RE = re.compile(r"\b(CBU|Cuenta|Sucursal|Alias)\b", re.I)
_NEARBY_DISTANCE = 50.0


def _find_22_digit(text: str) -> str | None:
    m = _22_DIGIT_RE.search(text)
    return m.group(1) if m else None


def _is_nearby(a: TextBlock, b: TextBlock) -> bool:
    return abs(a.bbox.top - b.bbox.top) <= _NEARBY_DISTANCE


def _block_text(block: TextBlock) -> str:
    return " ".join(w.text for w in block.words)


def _score_cbu(cbu: str, context: str, page_number: int, bank: Bank | None) -> int:
    score = 0
    if bank is not None and cbu.startswith(bank.cbu_prefix):
        score += 50
    if _NEARBY_KEYWORDS_RE.search(context):
        score += 30
    if page_number == 1:
        score += 20
    return score


def extract_cbu(
    header_blocks: list[tuple[TextBlock, int]],
    footer_blocks: list[tuple[TextBlock, int]],
    bank: Bank | None = None,
) -> str | None:
    all_blocks: list[tuple[TextBlock, int]] = header_blocks + footer_blocks

    for block, _page in all_blocks:
        text = _block_text(block)
        if _CBU_LABEL_RE.search(text):
            cbu = _find_22_digit(text)
            if cbu is not None:
                return cbu
            for other, _ in all_blocks:
                if other is not block and _is_nearby(block, other):
                    cbu = _find_22_digit(_block_text(other))
                    if cbu is not None:
                        return cbu

    candidates: list[tuple[str, str, int]] = []
    for block, page in all_blocks:
        text = _block_text(block)
        for m in _22_DIGIT_RE.finditer(text):
            candidates.append((m.group(1), text, page))

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    scored = [
        (cbu, _score_cbu(cbu, ctx, page, bank))
        for cbu, ctx, page in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]
