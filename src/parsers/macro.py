from __future__ import annotations

import re

from src.cleaners.filters import FILTERS
from src.models.bank import BankId
from src.parsers.base import RawTransaction

_RE_TRANSACTION = re.compile(
    r"^(\d{2}/\d{2}/\d{4})\s+(\d+)\s+(\d+)\s+(.+?)\s+\$\s*(-?[\d.,]+)\s+\$\s*(-?[\d.,]+)$"
)


class MacroParser:
    def parse_lines(self, lines: list[str]) -> list[RawTransaction]:
        filters = FILTERS[BankId.MACRO]
        clean = [line for line in lines if not any(p.search(line) for p in filters.skip)]
        result: list[RawTransaction] = []
        for line in clean:
            m = _RE_TRANSACTION.match(line)
            if m:
                result.append(
                    RawTransaction(
                        fecha=m.group(1),
                        descripcion=m.group(4).strip(),
                        importe=m.group(5),
                        saldo=m.group(6),
                    )
                )
        result.sort(key=_sort_key)
        return result


def _sort_key(tx: RawTransaction) -> tuple[int, int, int]:
    d, m, y = tx.fecha.split("/")
    return int(y), int(m), int(d)
