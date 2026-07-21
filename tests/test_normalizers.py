from decimal import Decimal

from src.normalizers.amount import normalize_amount


def test_zero_amount():
    a = normalize_amount("")
    assert a.signed_value == Decimal("0")

    a = normalize_amount(None)
    assert a.signed_value == Decimal("0")


def test_positive_integer():
    a = normalize_amount("$ 1.000")
    assert a.signed_value == Decimal("1")


def test_positive_with_thousands_and_decimal():
    a = normalize_amount("$ 200.000,00")
    assert a.signed_value == Decimal("200000.00")


def test_positive_no_symbol():
    a = normalize_amount("1.234,56")
    assert a.signed_value == Decimal("1234.56")


def test_negative_leading_minus():
    a = normalize_amount("$-57.640,00")
    assert a.signed_value == Decimal("-57640.00")


def test_negative_trailing_minus():
    a = normalize_amount("1.234,56-")
    assert a.signed_value == Decimal("-1234.56")


def test_negative_parentheses():
    a = normalize_amount("(1.234,56)")
    assert a.signed_value == Decimal("-1234.56")


def test_no_decimal_separator():
    a = normalize_amount("500")
    assert a.signed_value == Decimal("500")


def test_small_amount():
    a = normalize_amount("0,50")
    assert a.signed_value == Decimal("0.50")


def test_negative_zero():
    a = normalize_amount("-0")
    assert a.signed_value == Decimal("0")


def test_amount_with_spaces():
    a = normalize_amount("  $  1.000,50  ")
    assert a.signed_value == Decimal("1000.50")


def test_large_amount():
    a = normalize_amount("$ 1.234.567,89")
    assert a.signed_value == Decimal("1234567.89")


def test_importes_from_macro_sample():
    assert normalize_amount("200.000,00").signed_value == Decimal("200000.00")
    assert normalize_amount("-57.640,00").signed_value == Decimal("-57640.00")
    assert normalize_amount("-205.360,00").signed_value == Decimal("-205360.00")
    assert normalize_amount("5.500,00").signed_value == Decimal("5500.00")
    assert normalize_amount("542.000,00").signed_value == Decimal("542000.00")
