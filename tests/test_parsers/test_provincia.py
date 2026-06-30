from src.parsers.provincia import ProvinciaParser

PROVINCIA_SAMPLE_SINGLE = [
    "BANCO PROVINCIA",
    "EXTRACTO DE CUENTA INFORMATIVO",
    "C.C.",
    "PESOS",
    "01/12/2025 TRANSF BANCO PROV NCIA 123.456,78 15-01 1.000.000,00",
    "15/12/2025 PAGO HONORARIOS 50.000,00 12-34 950.000,00",
    "20/12/2025 COMPRA CON TARJETA 15.000,50 56-78 935.000,00",
    "Fecha de descarga: 10/01/2026",
]


def test_provincia_parser_count():
    parser = ProvinciaParser()
    result = parser.parse_lines(PROVINCIA_SAMPLE_SINGLE)
    assert len(result) == 3


def test_provincia_parser_first():
    parser = ProvinciaParser()
    result = parser.parse_lines(PROVINCIA_SAMPLE_SINGLE)
    first = result[0]
    assert first.fecha == "01/12/2025"
    assert "TRANSF BANCO PROV NCIA" in first.descripcion
    assert first.importe == "123.456,78"
    assert first.saldo == "1.000.000,00"


def test_provincia_parser_sorted():
    parser = ProvinciaParser()
    result = parser.parse_lines(PROVINCIA_SAMPLE_SINGLE)
    dates = [r.fecha for r in result]
    assert dates == sorted(dates)


PROVINCIA_SAMPLE_MULTILINE = [
    "BANCO PROVINCIA",
    "EXTRACTO DE CUENTA INFORMATIVO",
    "C.C.",
    "PESOS",
    "01/12/2025 TRANSF BANCO PROV",
    "NCIA DESTINO VARIOS",
    " 123.456,78 15-01 1.000.000,00",
    "15/12/2025 PAGO HONORARIOS PROFESIONALES 50.000,00 12-34 950.000,00",
    "Fecha de descarga: 10/01/2026",
]


def test_provincia_merge_multiline():
    parser = ProvinciaParser()
    result = parser.parse_lines(PROVINCIA_SAMPLE_MULTILINE)
    assert len(result) == 2
    first = result[0]
    assert first.fecha == "01/12/2025"
    assert "TRANSF BANCO PROV NCIA DESTINO VARIOS" in first.descripcion


def test_provincia_parser_empty():
    parser = ProvinciaParser()
    result = parser.parse_lines([])
    assert result == []
