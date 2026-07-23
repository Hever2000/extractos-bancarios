from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from re import Pattern


class BankId(Enum):
    MACRO = "Banco Macro"
    PROVINCIA = "Banco Provincia"
    NACION = "Banco Nacion"


@dataclass(frozen=True)
class Bank:
    id: BankId
    text_patterns: tuple[Pattern[str], ...]
    filename_patterns: tuple[Pattern[str], ...]
    cbu_prefix: str

    @property
    def name(self) -> str:
        return self.id.value

    def score_text(self, text: str) -> int:
        return sum(30 for p in self.text_patterns if p.search(text))

    def score_filename(self, filename: str) -> int:
        return sum(20 for p in self.filename_patterns if p.search(filename))

    def score_cbu(self, text: str) -> int:
        import re
        m = re.search(r"\b(\d{3})\d{19}\b", text)
        if m and m.group(1) == self.cbu_prefix:
            return 50
        return 0

    def total_score(self, text: str, filename: str) -> int:
        return self.score_text(text) + self.score_filename(filename) + self.score_cbu(text)
