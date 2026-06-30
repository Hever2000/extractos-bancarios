from src.parsers.nacion import NacionParser

NACION_SAMPLE = [
    "BANCO NACION",
    "Fecha consulta: 15/01/2026",
    "Hora consulta: 10:30",
    "Cuenta: 12345678 - CC $",
    "PESOS",
    "01/12/2025 01/12/2025 1.500,00 123456 100.000,00",
    "TRANSF RECIBIDA",
    "05/12/2025 05/12/2025 50.000,00 789012",
    "PAGO HONORARIOS",
    "10/12/2025 10/12/2025 3.200,50 345678 46.800,00",
    "COMPRA TARJETA",
    "Fecha de descarga: 15/01/2026",
]


def test_nacion_parser_count():
    parser = NacionParser()
    result = parser.parse_lines(NACION_SAMPLE)
    assert len(result) == 3


def test_nacion_parser_first():
    parser = NacionParser()
    result = parser.parse_lines(NACION_SAMPLE)
    first = result[0]
    assert first.fecha == "01/12/2025"
    assert first.descripcion == "BANCO NACION"
    assert first.importe == "1.500,00"
    assert first.saldo == "100.000,00"


def test_nacion_parser_second_no_balance():
    parser = NacionParser()
    result = parser.parse_lines(NACION_SAMPLE)
    second = result[1]
    assert second.fecha == "05/12/2025"
    assert second.descripcion == "TRANSF RECIBIDA"
    assert second.importe == "50.000,00"
    assert second.saldo is None


def test_nacion_parser_sorted():
    parser = NacionParser()
    result = parser.parse_lines(NACION_SAMPLE)
    dates = [r.fecha for r in result]
    expected = ["01/12/2025", "05/12/2025", "10/12/2025"]
    assert dates == expected


def test_nacion_parser_fallback_description():
    parser = NacionParser()
    result = parser.parse_lines(NACION_SAMPLE)
    third = result[2]
    assert third.descripcion == "PAGO HONORARIOS"


def test_nacion_missing_description_uses_sn():
    lines = [
        "01/12/2025 01/12/2025 1.500,00 123456 100.000,00",
    ]
    parser = NacionParser()
    result = parser.parse_lines(lines)
    assert result[0].descripcion == "S/N"


def test_nacion_parser_empty():
    parser = NacionParser()
    result = parser.parse_lines([])
    assert result == []
