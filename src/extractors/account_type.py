from __future__ import annotations

import re

from src.models.document import TextBlock

_ACCOUNT_TYPE_MAP: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"CUENTA\s+CORRIENTE|"
            r"CTA\.?\s*CTE\.?|"
            r"C\s*/\s*C\b|"
            r"\bCC(?!\s+(?:ESPECIAL|AHORRO|SUELDO))|"
            r"C\.\s*C\.(?!\s*(?:ESPECIAL|AHORRO|SUELDO))",
            re.I,
        ),
        "Cuenta Corriente",
    ),
    (
        re.compile(
            r"CAJA\s+(DE\s+)?AHORRO|"
            r"CUENTA\s+AHORRO|"
            r"\bCA\b",
            re.I,
        ),
        "Caja de Ahorro",
    ),
    (re.compile(r"CUENTA\s+SUELDO", re.I), "Cuenta Sueldo"),
    (re.compile(r"CUENTA\s+ESPECIAL", re.I), "Cuenta Especial"),
]


def _block_text(block: TextBlock) -> str:
    return " ".join(w.text for w in block.words)


def extract_account_type(
    header_blocks: list[tuple[TextBlock, int]],
    footer_blocks: list[tuple[TextBlock, int]],
) -> str | None:
    all_blocks: list[tuple[TextBlock, int]] = header_blocks + footer_blocks
    for block, _ in all_blocks:
        text = _block_text(block)
        for pattern, normalized in _ACCOUNT_TYPE_MAP:
            if pattern.search(text):
                return normalized
    return None
