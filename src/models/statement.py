from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import NewType

from src.models.bank import Bank

Sign = NewType("Sign", int)


@dataclass(frozen=True)
class Amount:
    value: Decimal
    sign: Sign

    @property
    def signed_value(self) -> Decimal:
        return self.value * self.sign

    @classmethod
    def zero(cls) -> Amount:
        return cls(value=Decimal("0"), sign=Sign(1))

    @classmethod
    def positive(cls, value: Decimal) -> Amount:
        return cls(value=value, sign=Sign(1))

    @classmethod
    def negative(cls, value: Decimal) -> Amount:
        return cls(value=value, sign=Sign(-1))


@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    amount: Amount
    balance: Amount | None


@dataclass(frozen=True)
class Statement:
    bank: Bank
    transactions: tuple[Transaction, ...]
    date_from: date | None
    date_to: date | None
    metadata: dict[str, str] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
