from src.parsers.macro import MacroParser

MACRO_SAMPLE = [
    "Últimos Movimientos",
    "C.C. ESPECIAL",
    "Caja de Ahorro",
    "PESOS",
    "470309538602872",
    "Tipo",
    "Número",
    "Moneda",
    "Fecha Nro. de",
    "Referencia",
    "Causal Concepto Importe Saldo",
    "07/01/2026 618724 493 TRANSF BOCCA, AD 27208259550 $ 200.000,00 $ 200.000,00",
    "29/12/2025 76450031 3861 TRF MO CCDO MISMO - 30528968461 $ -57.640,00 $ 0,00",
    "29/12/2025 360802 4085 TRANSF:2512290000785383360802- $ -205.360,00 $ 57.640,00",
    "26/12/2025 111526 4544 ING TRANSF:ELIANA SOLEDAD $ 5.500,00 $ 263.000,00",
    "01/12/2025 595645331 4397 TRANSF 23132999619 VAR $ 542.000,00 $ 2.548.968,83",
    "Fecha de descarga: 09/01/2026 13:32:40",
    "2 de 2",
    "Operador: Silvina Rasetto",
    "Empresa: 30528968461 - ASOCIACION CULTURAL VIRGEN NIÑA",
]


def test_macro_parser_count():
    parser = MacroParser()
    result = parser.parse_lines(MACRO_SAMPLE)
    assert len(result) == 5


def test_macro_parser_first_transaction():
    parser = MacroParser()
    result = parser.parse_lines(MACRO_SAMPLE)
    first = result[0]
    assert first.fecha == "01/12/2025"
    assert first.descripcion == "TRANSF 23132999619 VAR"
    assert first.importe == "542.000,00"
    assert first.saldo == "2.548.968,83"


def test_macro_parser_last_transaction():
    parser = MacroParser()
    result = parser.parse_lines(MACRO_SAMPLE)
    last = result[-1]
    assert last.fecha == "07/01/2026"
    assert "TRANSF BOCCA" in last.descripcion
    assert last.importe == "200.000,00"
    assert last.saldo == "200.000,00"


def test_macro_parser_sorted():
    parser = MacroParser()
    result = parser.parse_lines(MACRO_SAMPLE)
    dates = [r.fecha for r in result]
    expected = ["01/12/2025", "26/12/2025", "29/12/2025", "29/12/2025", "07/01/2026"]
    assert dates == expected


def test_macro_parser_descripcion_preserves_commas():
    parser = MacroParser()
    result = parser.parse_lines(MACRO_SAMPLE)
    assert "AD 27208259550" in result[-1].descripcion


def test_macro_parser_empty_lines():
    parser = MacroParser()
    result = parser.parse_lines([])
    assert result == []
