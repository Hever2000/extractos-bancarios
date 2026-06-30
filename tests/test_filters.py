from src.cleaners.filters import FILTERS, split_lines
from src.cleaners.normalizer import normalize_text
from src.models.bank import BankId


def test_split_lines():
    text = "line1\nline2\n\nline3\n  line4  "
    lines = split_lines(text)
    assert lines == ["line1", "line2", "line3", "line4"]


def test_skip_header_patterns():
    filters = FILTERS[BankId.MACRO]
    headers = [
        "Ultimos Movimientos",
        "C.C. ESPECIAL",
        "Caja de Ahorro",
        "PESOS",
        "Fecha Nro. de",
        "Referencia",
        "Causal Concepto Importe Saldo",
        "Fecha de descarga: 09/01/2026",
        "Operador: Silvina Rasetto",
        "Empresa: 30528968461",
        "2 de 2",
    ]
    for h in headers:
        assert any(p.search(h) for p in filters.skip), f"Pattern not matched by SKIP: {h!r}"


def test_skip_pagination():
    filters = FILTERS[BankId.MACRO]
    assert any(p.search("1 de 5") for p in filters.skip)
    assert any(p.search("2 de 2") for p in filters.skip)


def test_keep_transaction_line():
    filters = FILTERS[BankId.MACRO]
    tx_line = "07/01/2026 618724 493 TRANSF BOCCA, AD 27208259550 $ 200.000,00 $ 200.000,00"
    assert not any(p.search(tx_line) for p in filters.skip)


def test_normalize_text():
    raw = "line1\r\nline2\r\n\r\nline3\r"
    result = normalize_text(raw)
    assert result == "line1\nline2\n\nline3"
