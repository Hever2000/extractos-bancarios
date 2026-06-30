from __future__ import annotations

import re

from src.cleaners.filters import FILTERS
from src.models.bank import BankId
from src.parsers.base import RawTransaction
from src.parsers.macro import _sort_key

_RE_TRANSACTION = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(-?[\d.,]+)\s+(\d+)(?:\s+(-?[\d.,]+))?$"
)


class NacionParser:
    def parse_lines(self, lines: list[str]) -> list[RawTransaction]:
        filters = FILTERS[BankId.NACION]
        clean = [line for line in lines if not any(p.search(line) for p in filters.skip)]
        tx_matches: list[re.Match[str]] = []
        desc_lines: list[str] = []
        for line in clean:
            m = _RE_TRANSACTION.match(line)
            if m:
                tx_matches.append(m)
            else:
                desc_lines.append(line)
        result: list[RawTransaction] = []
        for i, m in enumerate(tx_matches):
            desc = (desc_lines[i] if i < len(desc_lines) else "").strip() or "S/N"
            result.append(
                RawTransaction(
                    fecha=m.group(1),
                    descripcion=desc,
                    importe=m.group(3),
                    saldo=m.group(5),
                )
            )
        result.sort(key=_sort_key)
        return result
