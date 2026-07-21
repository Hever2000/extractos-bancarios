from __future__ import annotations

from src.extractors.account import extract_account
from src.extractors.account_type import extract_account_type
from src.extractors.cbu import extract_cbu
from src.models.bank import Bank, BankId
from src.models.document import BBox, TextBlock

_BANK_MACRO = Bank(
    id=BankId.MACRO,
    text_patterns=(),
    filename_patterns=(),
    cbu_prefix="285",
)

_BANK_NACION = Bank(
    id=BankId.NACION,
    text_patterns=(),
    filename_patterns=(),
    cbu_prefix="011",
)


def _block(words: list[str], top: float = 0.0) -> TextBlock:
    from src.models.document import Word
    ww: list[Word] = []
    x = 0.0
    for w in words:
        ww.append(Word(text=w, bbox=BBox(x0=x, x1=x + 50, top=top, bottom=top + 10)))
        x += 60
    return TextBlock(words=tuple(ww), bbox=BBox(x0=0, x1=x, top=top, bottom=top + 10))


def _hblock(words: list[str], top: float = 0.0) -> tuple[TextBlock, int]:
    return (_block(words, top), 1)


def _fblock(words: list[str], top: float = 0.0) -> tuple[TextBlock, int]:
    return (_block(words, top), 1)


# ── CBU TESTS ────────────────────────────────


def test_cbu_by_label_same_block():
    blocks = [_hblock(["CBU", "2850590940090418135201"])]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_by_label_with_colon():
    blocks = [_hblock(["CBU:", "2850590940090418135201"])]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_by_label_nearby_block():
    label_block = _hblock(["CBU"], top=10.0)
    value_block = _hblock(["2850590940090418135201"], top=30.0)
    blocks = [label_block, value_block]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_by_label_codigo_bancario():
    blocks = [_hblock(["Codigo", "Bancario", "Uniforme", "2850590940090418135201"])]
    result = extract_cbu(blocks, [])
    assert result == "2850590940090418135201"


def test_cbu_no_label_single_candidate():
    blocks = [_hblock(["Datos:", "2850590940090418135201"])]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_no_label_multiple_candidates_prefers_bank_match():
    blocks = [
        _hblock(["0110590940090418135201"], top=0.0),
        _hblock(["2850590940090418135201"], top=20.0),
    ]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_no_label_multiple_candidates_prefers_keyword():
    blocks = [
        _hblock(["2850590940090418135201"], top=0.0),
        _hblock(["Cuenta:", "0110590940090418135201"], top=20.0),
    ]
    result = extract_cbu(blocks, [], _BANK_NACION)
    assert result == "0110590940090418135201"


def test_cbu_invalid_too_short():
    blocks = [_hblock(["CBU:", "2850590940090418135"])]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result is None


def test_cbu_invalid_not_22_digits():
    blocks = [_hblock(["CBU:", "28505909a0090418135201"])]
    result = extract_cbu(blocks, [], _BANK_MACRO)
    assert result is None


def test_cbu_not_found():
    result = extract_cbu([], [])
    assert result is None


def test_cbu_in_footer():
    footer = [_fblock(["CBU:", "2850590940090418135201"])]
    result = extract_cbu([], footer, _BANK_MACRO)
    assert result == "2850590940090418135201"


def test_cbu_label_clave_bancaria():
    blocks = [_hblock(["Clave", "Bancaria", "Uniforme", "2850590940090418135201"])]
    result = extract_cbu(blocks, [])
    assert result == "2850590940090418135201"


# ── ACCOUNT TYPE TESTS ───────────────────────


def test_account_type_cuenta_corriente():
    blocks = [_hblock(["CUENTA", "CORRIENTE", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_cta_cte():
    blocks = [_hblock(["CTA", "CTE:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_cc():
    blocks = [_hblock(["C/C", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_caja_ahorro():
    blocks = [_hblock(["CAJA", "DE", "AHORRO", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Caja de Ahorro"


def test_account_type_caja_ahorro_sin_de():
    blocks = [_hblock(["CAJA", "AHORRO", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Caja de Ahorro"


def test_account_type_cuenta_sueldo():
    blocks = [_hblock(["CUENTA", "SUELDO"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Sueldo"


def test_account_type_cuenta_especial():
    blocks = [_hblock(["CUENTA", "ESPECIAL"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Especial"


def test_account_type_unknown():
    blocks = [_hblock(["ALGO", "INESPERADO"])]
    result = extract_account_type(blocks, [])
    assert result is None


def test_account_type_no_blocks():
    result = extract_account_type([], [])
    assert result is None


def test_account_type_in_footer():
    footer = [_fblock(["CUENTA", "CORRIENTE"])]
    result = extract_account_type([], footer)
    assert result == "Cuenta Corriente"


# ── ACCOUNT TESTS ────────────────────────────


def test_account_returns_none():
    result = extract_account([], [])
    assert result is None


def test_account_returns_none_even_with_blocks():
    blocks = [_hblock(["Cuenta:", "12345"])]
    result = extract_account(blocks, [])
    assert result is None
