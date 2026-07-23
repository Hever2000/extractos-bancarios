from __future__ import annotations

import re

from src.models.document import TextBlock

_LABEL_RE = re.compile(
    r"Cuenta\s*N[°º]|"
    r"N[°º]\s+Cuenta|"
    r"N[uú]mero\s+de\s+Cuenta|"
    r"\bN[uú]mero\b|"
    r"Nro\.?\s*(de\s+)?Cuenta|"
    r"\bCuenta\b",
    re.I,
)

_ACCOUNT_TYPE_EXCLUDE = re.compile(
    r"CUENTA\s+(CORRIENTE|CAJA|AHORRO|SUELDO|ESPECIAL)",
    re.I,
)

_ACCOUNT_TYPE_KEYWORDS = re.compile(
    r"CAJA\s+DE\s+AHORROS?|"
    r"C\.?C\.?\s*ESPECIAL|"
    r"CTA\.?\s*CTE[.\s]|"
    r"C\s*/\s*C",
    re.I,
)

_ACCOUNT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(\d{8}-\d[ \t]+\d{4}-\d)\b"),
    re.compile(r"\b(\d{1,6}-\d{1,10}/\d{1,2})\b"),
    re.compile(r"\b(\d{1,6}/\d)\b"),
    re.compile(r"\b(\d{1,6}-\d{1,10}-\d)\b"),
    re.compile(r"\b(\d{4,6}-\d{4,10})\b"),
    re.compile(r"\b(\d{8,12})\b"),
    re.compile(r"\b(\d{6,7})\b"),
    re.compile(r"\b(\d{13,17})\b"),
    re.compile(r"\b(\d{18,21})\b"),
]

_DISCARD_RE = re.compile(
    r"^\d{22}$|"
    r"^\d{2}-\d{8}-\d$|"
    r"^\d{1,2}/\d{1,2}/\d{2,4}$",
)

_PHONE_RE = re.compile(
    r"^\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{4}[\s\-]?\d{2,4}$|"
    r"^0\d{2,4}\s\d{4}\s\d{4}$|"
    r"^\(\d{2,5}\)\s?\d{4}[\s\-]?\d{4}$",
)

_AMOUNT_RE = re.compile(r"^\d+[.,]\d{2}$")

_NEARBY_DISTANCE = 50.0
_CONFIDENCE_THRESHOLD = 80
_TYPE_BONUS = 40


def _block_text(block: TextBlock) -> str:
    return " ".join(w.text for w in block.words)


def _is_valid_candidate(text: str) -> bool:
    if _DISCARD_RE.match(text):
        return False
    if _PHONE_RE.match(text):
        return False
    if _AMOUNT_RE.match(text):
        return False
    return True


def _find_candidates_in_block(block: TextBlock) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for word in block.words:
        text = word.text
        if not _is_valid_candidate(text):
            continue
        for i, pattern in enumerate(_ACCOUNT_PATTERNS):
            for m in pattern.finditer(text):
                c = m.group(1).strip()
                result.append((c, i))
    return result


def _vertical_distance(a: TextBlock, b: TextBlock) -> float:
    if a is b:
        return 0.0
    return abs(a.bbox.top - b.bbox.top)


def _score(
    pattern_idx: int,
    has_label: bool,
    distance: float,
    page_number: int,
    is_header: bool,
) -> int:
    score = 0
    if page_number == 1:
        score += 30
    if is_header:
        score += 10
    if has_label:
        score += 50
        if distance == 0:
            score += 40
        elif distance <= 10:
            score += 30
        elif distance <= 20:
            score += 20
        elif distance <= 50:
            score += 10
    score += max(15 - pattern_idx * 3, 0)
    return score


def extract_account(
    header_blocks: list[tuple[TextBlock, int]],
    footer_blocks: list[tuple[TextBlock, int]],
) -> str | None:
    all_blocks: list[tuple[TextBlock, int, bool]] = [
        *((b, p, True) for b, p in header_blocks),
        *((b, p, False) for b, p in footer_blocks),
    ]

    label_blocks = [
        b
        for b, _, _ in all_blocks
        if _LABEL_RE.search(_block_text(b))
        and not _ACCOUNT_TYPE_EXCLUDE.search(_block_text(b))
    ]

    block_type_bonus: dict[int, int] = {}
    for i, (block, _, _) in enumerate(all_blocks):
        text = _block_text(block)
        if (
            _ACCOUNT_TYPE_KEYWORDS.search(text)
            and not _ACCOUNT_TYPE_EXCLUDE.search(text)
        ):
            block_type_bonus[i] = _TYPE_BONUS

    scored: list[tuple[int, str]] = []

    for block_idx, (block, page, is_header) in enumerate(all_blocks):
        candidates = _find_candidates_in_block(block)
        if not candidates:
            continue

        nearest = float("inf")
        has_label = False
        for lbl in label_blocks:
            d = _vertical_distance(lbl, block)
            if d < nearest:
                nearest = d
        if nearest <= _NEARBY_DISTANCE:
            has_label = True

        type_bonus = block_type_bonus.get(block_idx, 0)

        for candidate, pidx in candidates:
            s = _score(pidx, has_label, nearest, page, is_header) + type_bonus
            scored.append((s, candidate))

    if not scored:
        return None

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]

    if best_score >= _CONFIDENCE_THRESHOLD:
        return best

    return None
