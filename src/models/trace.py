from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StageResult:
    stage_name: str
    confidence: float
    metrics: dict[str, int]
    warnings: tuple[str, ...]
