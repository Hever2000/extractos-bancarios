from __future__ import annotations

from typing import Any


def build_success(pipeline_json: dict[str, Any]) -> dict[str, Any]:
    detalle = pipeline_json.get("detalle", [])
    return {
        "exito": True,
        "duplicado": False,
        "mensaje": "Extracto procesado correctamente.",
        "banco": pipeline_json.get("banco"),
        "cantidad_transacciones": len(detalle),
        "fecha_desde": pipeline_json.get("fecha_desde"),
        "fecha_hasta": pipeline_json.get("fecha_hasta"),
    }


def build_duplicate() -> dict[str, Any]:
    return {
        "exito": False,
        "duplicado": True,
        "mensaje": "Este extracto ya fue cargado anteriormente.",
    }


def build_error() -> dict[str, Any]:
    return {
        "exito": False,
        "duplicado": False,
        "mensaje": "Ocurrió un error durante el procesamiento del extracto.",
    }
