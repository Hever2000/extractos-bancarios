import pytest

from src.models.bank import BankId
from src.parsers.factory import ParserFactory
from src.parsers.macro import MacroParser
from src.parsers.nacion import NacionParser
from src.parsers.provincia import ProvinciaParser


def test_factory_returns_macro():
    parser = ParserFactory.for_bank(BankId.MACRO)
    assert isinstance(parser, MacroParser)


def test_factory_returns_provincia():
    parser = ParserFactory.for_bank(BankId.PROVINCIA)
    assert isinstance(parser, ProvinciaParser)


def test_factory_returns_nacion():
    parser = ParserFactory.for_bank(BankId.NACION)
    assert isinstance(parser, NacionParser)


def test_factory_caches_parsers():
    p1 = ParserFactory.for_bank(BankId.MACRO)
    p2 = ParserFactory.for_bank(BankId.MACRO)
    assert p1 is p2


def test_factory_raises_for_galicia():
    with pytest.raises(ValueError, match="No parser available"):
        ParserFactory.for_bank(BankId.GALICIA)
