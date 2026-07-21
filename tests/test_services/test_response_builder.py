from __future__ import annotations

from src.services.response_builder import build_duplicate, build_error, build_success


def test_build_success() -> None:
    pipeline_json = {
        "banco": "Banco Macro",
        "detalle": [{"fecha": "2026-01-01"}, {"fecha": "2026-01-02"}],
        "fecha_desde": "2026-01-01",
        "fecha_hasta": "2026-01-31",
    }
    result = build_success(pipeline_json)

    assert result["exito"] is True
    assert result["duplicado"] is False
    assert result["mensaje"] == "Extracto procesado correctamente."
    assert result["banco"] == "Banco Macro"
    assert result["cantidad_transacciones"] == 2
    assert result["fecha_desde"] == "2026-01-01"
    assert result["fecha_hasta"] == "2026-01-31"


def test_build_success_empty_detail() -> None:
    result = build_success({"banco": None, "detalle": []})

    assert result["exito"] is True
    assert result["cantidad_transacciones"] == 0
    assert result["banco"] is None
    assert result["fecha_desde"] is None


def test_build_success_no_banco() -> None:
    result = build_success({})

    assert result["banco"] is None
    assert result["cantidad_transacciones"] == 0


def test_build_duplicate() -> None:
    result = build_duplicate()

    assert result["exito"] is False
    assert result["duplicado"] is True
    assert result["mensaje"] == "Este extracto ya fue cargado anteriormente."


def test_build_error() -> None:
    result = build_error()

    assert result["exito"] is False
    assert result["duplicado"] is False
    assert result["mensaje"] == "Ocurrió un error durante el procesamiento del extracto."
