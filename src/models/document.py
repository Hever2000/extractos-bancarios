from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    x0: float
    x1: float
    top: float
    bottom: float


@dataclass(frozen=True)
class Word:
    text: str
    bbox: BBox
    fontname: str | None = None


@dataclass(frozen=True)
class TextBlock:
    words: tuple[Word, ...]
    bbox: BBox


@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    words: tuple[Word, ...]
    blocks: tuple[TextBlock, ...] = ()


@dataclass(frozen=True)
class Document:
    pages: tuple[Page, ...]
