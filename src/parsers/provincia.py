from __future__ import annotations

import re

from src.cleaners.filters import FILTERS
from src.models.bank import BankId
from src.parsers.base import RawTransaction
from src.parsers.macro import _sort_key

_RE_TRANSACTION = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(-?[\d.,]+)\s+(\d{2}-\d{2})\s+(-?[\d.,]+)\s*$"
)
_RE_DATE_START = re.compile(r"^\d{2}/\d{2}/\d{4}")
_RE_HAS_ENDING = re.compile(r"-?[\d.,]+\s+\d{2}-\d{2}\s+-?[\d.,]+\s*$")


def _merge_multiline(raw_lines: list[str]) -> list[str]:
    merged: list[str] = []
    buf: list[str] = []
    for line in raw_lines:
        is_new = bool(_RE_DATE_START.match(line))
        has_ending = bool(_RE_HAS_ENDING.search(line))
        if is_new:
            if buf:
                merged.append(" ".join(buf))
            buf = [line]
            if has_ending:
                merged.append(" ".join(buf))
                buf = []
        elif buf:
            buf.append(line)
            if has_ending:
                merged.append(" ".join(buf))
                buf = []
    if buf:
        merged.append(" ".join(buf))
    return merged


class ProvinciaParser:
    def parse_lines(self, lines: list[str]) -> list[RawTransaction]:
        filters = FILTERS[BankId.PROVINCIA]
        clean = [line for line in lines if not any(p.search(line) for p in filters.skip)]
        merged = _merge_multiline(clean)
        result: list[RawTransaction] = []
        for line in merged:
            m = _RE_TRANSACTION.match(line)
            if m:
                result.append(
                    RawTransaction(
                        fecha=m.group(1),
                        descripcion=m.group(2).strip(),
                        importe=m.group(3),
                        saldo=m.group(5),
                    )
                )
        result.sort(key=_sort_key)
        return result
