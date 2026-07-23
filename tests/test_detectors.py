from src.detectors.bank import Confidence, detect_bank
from src.models.bank import BankId


def test_detect_macro_by_text():
    text = """
    EXTRACTO DE CUENTA
    BANCO MACRO S.A.
    C.C. ESPECIAL
    """
    result = detect_bank(text)
    assert result.bank is not None
    assert result.bank.id == BankId.MACRO
    assert result.confidence in (Confidence.HIGH, Confidence.MEDIUM, Confidence.LOW)


def test_detect_provincia_by_text():
    text = """
    BANCO PROVINCIA
    EXTRACTO DE CUENTA INFORMATIVO
    """
    result = detect_bank(text)
    assert result.bank is not None
    assert result.bank.id == BankId.PROVINCIA


def test_detect_nacion_by_text():
    text = """
    BANCO NACION
    Fecha consulta: 15/01/2026
    Hora consulta: 10:30
    Cuenta: 12345678 - CC $
    """
    result = detect_bank(text)
    assert result.bank is not None
    assert result.bank.id == BankId.NACION


def test_detect_by_cbu():
    text = "CBU 2851234567890123456789"
    result = detect_bank(text)
    assert result.bank is not None
    assert result.bank.id == BankId.MACRO


def test_detect_nacion_by_cbu():
    text = "CBU 0110123456789012345678"
    result = detect_bank(text)
    assert result.bank is not None
    assert result.bank.id == BankId.NACION


def test_filename_only_below_threshold():
    text = "some random text"
    result = detect_bank(text, filename="extracto_macro_enero.pdf")
    assert result.bank is None
    assert result.score == 20


def test_filename_and_text():
    text = "BANCO MACRO\nC.C. ESPECIAL"
    result = detect_bank(text, filename="extracto_macro_enero.pdf")
    assert result.bank is not None
    assert result.bank.id == BankId.MACRO


def test_no_detection():
    text = "This is just random text with no bank information whatsoever"
    result = detect_bank(text)
    assert result.bank is None
    assert result.confidence == Confidence.NONE


def test_no_detection_low_score():
    text = "maybe macro? or maybe something else"
    result = detect_bank(text)
    assert result.bank is None


def test_nacion_by_text_and_filename():
    text = "BANCO NACION\nFecha consulta:"
    result = detect_bank(text, filename="bna_extracto.pdf")
    assert result.bank is not None
    assert result.bank.id == BankId.NACION
