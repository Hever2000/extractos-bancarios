from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawTransaction:
    fecha: str
    descripcion: str
    importe: str
    saldo: str | None


class BankParser(Protocol):
    def parse_lines(self, lines: list[str]) -> list[RawTransaction]:
        ...
