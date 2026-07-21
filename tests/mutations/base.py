from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from src.models.document import BBox, Document, Page, Word

# ── Shared mutation helpers ──────────────────

def pick_page(doc: Document, rng: random.Random) -> int:
    return rng.randint(0, len(doc.pages) - 1)


def rand_float(rng: random.Random, low: float, high: float) -> float:
    return low + rng.random() * (high - low)


def rebuild_page(page: Page, words: list[Word] | None = None) -> Page:
    return Page(
        number=page.number,
        width=page.width,
        height=page.height,
        words=tuple(words) if words is not None else page.words,
        blocks=(),
    )


def rebuild_doc(doc: Document, page_idx: int, new_page: Page) -> Document:
    pages = list(doc.pages)
    pages[page_idx] = new_page
    return Document(pages=tuple(pages))


def clone_words(words: tuple[Word, ...]) -> list[Word]:
    return [
        Word(
            text=w.text,
            bbox=BBox(x0=w.bbox.x0, x1=w.bbox.x1, top=w.bbox.top, bottom=w.bbox.bottom),
            fontname=w.fontname,
        )
        for w in words
    ]


# ── Core mutation framework ──────────────────

class MutationCategory(Enum):
    HEADERS = auto()
    FOOTERS = auto()
    COLUMN_NAMES = auto()
    COLUMN_ORDER = auto()
    EXTRA_COLUMNS = auto()
    MISSING_COLUMNS = auto()
    ALIGNMENT_H = auto()
    ALIGNMENT_V = auto()
    SPACING = auto()
    MULTIPLE_TABLES = auto()
    MULTILINE_DESC = auto()
    DATES = auto()
    AMOUNTS = auto()
    BALANCES = auto()
    CURRENCY = auto()
    PAGES = auto()
    EMPTY_ROWS = auto()
    DUPLICATE_ROWS = auto()
    EXTREME_VALUES = auto()
    SPECIAL_CHARS = auto()
    UNEXPECTED_TEXT = auto()


@dataclass(frozen=True)
class MutationContext:
    seed: int
    source: Document
    rng: random.Random = field(compare=False, hash=False, repr=False)
    mutations_applied: int = 0

    @classmethod
    def create(cls, seed: int, source: Document) -> MutationContext:
        import random
        return cls(seed=seed, source=source, rng=random.Random(seed))


@dataclass(frozen=True)
class MutationOutcome:
    operator_name: str
    category: MutationCategory
    mutation_index: int
    passed: bool
    properties_results: dict[str, bool]
    stage_confidence: float
    transactions_count: int
    warnings: tuple[str, ...]
    error: str | None = None


@dataclass
class MutationReport:
    total_operators: int = 0
    passed: int = 0
    failed: int = 0
    outcomes: list[MutationOutcome] = field(default_factory=list)
    errors_by_category: dict[str, int] = field(default_factory=dict)
    properties_coverage: dict[str, dict[str, int]] = field(default_factory=dict)


@dataclass(frozen=True)
class MutationOp:
    name: str
    category: MutationCategory
    description: str
    probability: float
    apply: Callable[[Document, MutationContext], Document]
    injection_point: str = "pre_build"

    def __call__(self, doc: Document, ctx: MutationContext) -> Document:
        return self.apply(doc, ctx)
