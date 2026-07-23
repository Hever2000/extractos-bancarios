from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto

from src.models.bank import Bank, BankId

DETECTION_THRESHOLD = 30


class Confidence(Enum):
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    NONE = auto()


@dataclass(frozen=True)
class DetectionResult:
    bank: Bank | None
    score: int
    confidence: Confidence


BANKS: tuple[Bank, ...] = (
    Bank(
        id=BankId.MACRO,
        text_patterns=(
            re.compile(r"BANCO\s+MACRO", re.I),
            re.compile(r"C\.C\.\s*ESPECIAL", re.I),
        ),
        filename_patterns=(re.compile(r"macro", re.I),),
        cbu_prefix="285",
    ),
    Bank(
        id=BankId.PROVINCIA,
        text_patterns=(
            re.compile(r"BANCO\s+(DE LA\s+)?PROVINCIA", re.I),
            re.compile(r"EXTRACTO DE CUENTA INFORMATIVO", re.I),
        ),
        filename_patterns=(re.compile(r"provincia", re.I),),
        cbu_prefix="014",
    ),
    Bank(
        id=BankId.NACION,
        text_patterns=(
            re.compile(r"BANCO\s+(DE LA\s+)?NACION", re.I),
            re.compile(r"Fecha consulta:", re.I),
            re.compile(r"Hora consulta:", re.I),
            re.compile(r"Cuenta: \d+ - CC \$", re.I),
        ),
        filename_patterns=(
            re.compile(r"nacion", re.I),
            re.compile(r"bna", re.I),
        ),
        cbu_prefix="011",
    ),

)


def _confidence(score: int) -> Confidence:
    if score >= 80:
        return Confidence.HIGH
    if score >= 50:
        return Confidence.MEDIUM
    if score >= DETECTION_THRESHOLD:
        return Confidence.LOW
    return Confidence.NONE


def detect_bank(text: str, filename: str = "") -> DetectionResult:
    scored = [(b, b.total_score(text, filename)) for b in BANKS]
    scored.sort(key=lambda x: x[1], reverse=True)
    best_bank, best_score = scored[0]
    if best_score >= DETECTION_THRESHOLD:
        return DetectionResult(bank=best_bank, score=best_score, confidence=_confidence(best_score))
    return DetectionResult(bank=None, score=best_score, confidence=Confidence.NONE)
