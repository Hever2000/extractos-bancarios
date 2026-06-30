from __future__ import annotations

from src.models.bank import BankId
from src.parsers.base import BankParser
from src.parsers.macro import MacroParser
from src.parsers.nacion import NacionParser
from src.parsers.provincia import ProvinciaParser


class ParserFactory:
    _parsers: dict[BankId, BankParser] = {}

    @classmethod
    def for_bank(cls, bank_id: BankId) -> BankParser:
        if bank_id not in cls._parsers:
            cls._parsers[bank_id] = cls._create(bank_id)
        return cls._parsers[bank_id]

    @classmethod
    def _create(cls, bank_id: BankId) -> BankParser:
        mapping: dict[BankId, type[BankParser]] = {
            BankId.MACRO: MacroParser,
            BankId.PROVINCIA: ProvinciaParser,
            BankId.NACION: NacionParser,
        }
        parser_cls = mapping.get(bank_id)
        if parser_cls is None:
            raise ValueError(f"No parser available for bank: {bank_id.value}")
        return parser_cls()
