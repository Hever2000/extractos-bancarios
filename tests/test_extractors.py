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


def test_account_type_cc_abbrev():
    blocks = [_hblock(["CC", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_cc_dotted():
    blocks = [_hblock(["C.C.", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_cc_with_dash():
    blocks = [_hblock(["03", "-", "CC", "$", "00850005400123"])]
    result = extract_account_type(blocks, [])
    assert result == "Cuenta Corriente"


def test_account_type_cc_especial_not_confused():
    blocks = [_hblock(["C.C.", "ESPECIAL"])]
    result = extract_account_type(blocks, [])
    assert result is None  # "C.C. ESPECIAL" ambiguo, no forzar Cte. Cte.


def test_account_type_ca_abbrev():
    blocks = [_hblock(["CA", "Nro:", "506086/9"])]
    result = extract_account_type(blocks, [])
    assert result == "Caja de Ahorro"


def test_account_type_ca_caja_ahorro_alias():
    blocks = [_hblock(["CA", "AHORRO", "Nro:", "12345"])]
    result = extract_account_type(blocks, [])
    assert result == "Caja de Ahorro"


# ── ACCOUNT TESTS ────────────────────────────


def test_account_empty():
    result = extract_account([], [])
    assert result is None


def test_account_label_same_block():
    blocks = [_hblock(["Cuenta:", "506086/9"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_label_with_colon_same_block():
    blocks = [_hblock(["Cuenta", "N°:", "506086/9"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_label_nro_cuenta():
    blocks = [_hblock(["Nro", "Cuenta:", "175-12345/01"])]
    result = extract_account(blocks, [])
    assert result == "175-12345/01"


def test_account_label_numero_de_cuenta():
    blocks = [_hblock(["Número", "de", "Cuenta:", "506086/9"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_label_nro_abbrev():
    blocks = [_hblock(["Nro.", "Cuenta:", "506086/9"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_label_nearby_block():
    label = _hblock(["Cuenta", "N°"], top=10.0)
    value = _hblock(["506086/9"], top=30.0)
    result = extract_account([label, value], [])
    assert result == "506086/9"


def test_account_slash_format():
    blocks = [_hblock(["Cuenta:", "506086/9"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_dash_slash_format():
    blocks = [_hblock(["Cuenta:", "175-12345/01"])]
    result = extract_account(blocks, [])
    assert result == "175-12345/01"


def test_account_dash_dash_format():
    blocks = [_hblock(["Cuenta:", "123-456789-0"])]
    result = extract_account(blocks, [])
    assert result == "123-456789-0"


def test_account_plain_9_digits():
    blocks = [_hblock(["Cuenta:", "123456789"])]
    result = extract_account(blocks, [])
    assert result == "123456789"


def test_account_plain_12_digits_leading_zeros():
    blocks = [_hblock(["Cuenta:", "000123456789"])]
    result = extract_account(blocks, [])
    assert result == "000123456789"


def test_account_discard_cbu_22_digits():
    blocks = [_hblock(["Cuenta:", "2850590940090418135201"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_discard_cuit():
    blocks = [_hblock(["Cuenta:", "20-12345678-9"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_discard_date():
    blocks = [_hblock(["Cuenta:", "15/01/2024"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_discard_amount():
    blocks = [_hblock(["Cuenta:", "1234,56"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_discard_phone():
    blocks = [_hblock(["Cuenta:", "+54-11-5555-1234"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_no_label_not_confident():
    blocks = [_hblock(["123456789"], top=0.0)]
    result = extract_account(blocks, [])
    assert result is None


def test_account_multiple_candidates_best_wins():
    label = _hblock(["Cuenta:"], top=0.0)
    value = _hblock(["506086/9"], top=20.0)
    other = _hblock(["999999999"], top=100.0)
    result = extract_account([label, value, other], [])
    assert result == "506086/9"


def test_account_in_footer():
    footer = [_fblock(["Cuenta:", "506086/9"])]
    result = extract_account([], footer)
    assert result == "506086/9"


def test_account_account_type_excluded():
    blocks = [_hblock(["CUENTA", "CORRIENTE", "Nro:", "123456"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_too_short_digits():
    blocks = [_hblock(["Cuenta:", "12345"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_not_found():
    result = extract_account([], [])
    assert result is None


def test_account_label_numero_alone():
    blocks = [_hblock(["Número", "470309538602872"])]
    result = extract_account(blocks, [])
    assert result == "470309538602872"


def test_account_label_numero_same_block():
    blocks = [_hblock(["Número", "470309538602872"])]
    result = extract_account(blocks, [])
    assert result == "470309538602872"


def test_account_label_numero_nearby():
    label = _hblock(["Número:"], top=10.0)
    value = _hblock(["470309538602872"], top=25.0)
    result = extract_account([label, value], [])
    assert result == "470309538602872"


def test_account_long_14_digits():
    blocks = [_hblock(["Cuenta:", "00850005400123"])]
    result = extract_account(blocks, [])
    assert result == "00850005400123"


def test_account_long_15_digits():
    blocks = [_hblock(["Cuenta:", "470309538602872"])]
    result = extract_account(blocks, [])
    assert result == "470309538602872"


def test_account_long_18_digits():
    blocks = [_hblock(["Cuenta:", "123456789012345678"])]
    result = extract_account(blocks, [])
    assert result == "123456789012345678"


def test_account_long_21_digits():
    blocks = [_hblock(["Cuenta:", "123456789012345678901"])]
    result = extract_account(blocks, [])
    assert result == "123456789012345678901"


def test_account_discard_22_digits_cbu():
    blocks = [_hblock(["Número:", "2850590940090418135201"])]
    result = extract_account(blocks, [])
    assert result is None


def test_account_type_keyword_bonus_caja_ahorro():
    blocks = [_hblock(["506086/9", "CAJA", "DE", "AHORROS", "EN", "PESOS"])]
    result = extract_account(blocks, [])
    assert result == "506086/9"


def test_account_type_keyword_bonus_cc_especial():
    blocks = [_hblock(["470309538602872", "C.C.", "ESPECIAL"])]
    result = extract_account(blocks, [])
    assert result == "470309538602872"


def test_account_type_keyword_excluded_still_not_confident():
    blocks = [_hblock(["CUENTA", "CORRIENTE", "Nro:", "123456"])]
    result = extract_account(blocks, [])
    assert result is None
