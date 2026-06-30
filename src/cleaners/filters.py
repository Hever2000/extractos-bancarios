from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from src.models.bank import BankId


class LineCategory(Enum):
    HEADER = auto()
    FOOTER = auto()
    METADATA = auto()
    PAGE_NUMBER = auto()
    TRANSACTION = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class Filters:
    skip: tuple[re.Pattern[str], ...]


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.split("\n") if line.strip()]


def _build_skip_patterns(extra: list[re.Pattern[str]] | None = None) -> Filters:
    base: list[re.Pattern[str]] = [
        re.compile(r"^ultimos movimientos", re.I),
        re.compile(r"^c\.c\.", re.I),
        re.compile(r"^caja de ahorro", re.I),
        re.compile(r"^cuenta corriente", re.I),
        re.compile(r"^cuenta sueldo", re.I),
        re.compile(r"^pesos?$", re.I),
        re.compile(r"^\d{12,22}$"),
        re.compile(r"^tipo$", re.I),
        re.compile(r"^n\.mero$", re.I),
        re.compile(r"^moneda$", re.I),
        re.compile(r"^fecha nro\.", re.I),
        re.compile(r"^fecha mvto", re.I),
        re.compile(r"^referencia$", re.I),
        re.compile(r"^causal concepto", re.I),
        re.compile(r"^fecha$", re.I),
        re.compile(r"^detalle$", re.I),
        re.compile(r"^concepto$", re.I),
        re.compile(r"^\d+ de \d+$"),
        re.compile(r"^fecha de descarga", re.I),
        re.compile(r"^operador:", re.I),
        re.compile(r"^empresa:", re.I),
        re.compile(r"^importe saldo$", re.I),
        re.compile(r"^saldoimporte$", re.I),
        re.compile(r"^emitido el", re.I),
        re.compile(r"^extracto de cuenta", re.I),
        re.compile(r"^p.gina", re.I),
        re.compile(r"^\d+$"),
        re.compile(r"^CAJA DE AHORROS", re.I),
        re.compile(r"^Lcda\.?\s", re.I),
        re.compile(r"^Cantidad de Titulares", re.I),
        re.compile(r"^CBU", re.I),
        re.compile(r"^DNI$", re.I),
        re.compile(r"^CIUDAD AUTONOMA", re.I),
        re.compile(r"^OLAVARRIA", re.I),
        re.compile(r"^1000 - REGION", re.I),
        re.compile(r"^\d+-\w+", re.I),
        re.compile(r"^TRIMESTRAL", re.I),
        re.compile(r"^Fecha Concepto Fecha Valor", re.I),
        re.compile(r"^par.metros de b.squeda", re.I),
        re.compile(r"^b.squeda:", re.I),
        re.compile(r"^Cuenta:", re.I),
        re.compile(r"^Monto:", re.I),
        re.compile(r"^Usuario:", re.I),
        re.compile(r"^Fecha consulta:", re.I),
        re.compile(r"^Hora consulta:", re.I),
    ]
    if extra:
        base.extend(extra)
    return Filters(skip=tuple(base))


FILTERS: dict[BankId, Filters] = {
    BankId.MACRO: _build_skip_patterns(),
    BankId.PROVINCIA: _build_skip_patterns(),
    BankId.NACION: _build_skip_patterns(),
}
