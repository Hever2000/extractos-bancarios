from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedRow:
    date: str | None
    description: str
    amount: str | None
    balance: str | None
    metadata: dict[str, str]
