# extractos-bancarios

Procesamiento de extractos bancarios argentinos en PDF. Pipeline Python 3.12+ → AWS Lambda.

## Arquitectura

Pipeline lineal (Pipes & Filters):

```
PDF bytes → extract → normalize → filter → detect_bank → parse → normalize_amounts → validate → serialize → JSON
```

Cada etapa es una función pura. Los modelos son dataclasses inmutables (`frozen=True`). Montos con `Decimal` (nunca `float`).

## Uso

```sh
# CLI
python -m src extracto.pdf

# Modo estricto (falla rápido en errores de parseo)
python -m src extracto.pdf --strict
```

## Setup

```sh
pip install -e ".[dev]"
```

## Comandos

| Comando | Descripción |
|---------|-------------|
| `make lint` | ruff check |
| `make typecheck` | mypy strict |
| `make test` | pytest |
| `make test-coverage` | pytest con coverage |
| `make clean` | Limpiar cachés |

Orden: `make lint && make typecheck && make test`.

## Bancos soportados

| Banco | Estado |
|-------|--------|
| Macro | ✅ Parseado |
| Provincia | ✅ Parseado (multi-línea) |
| Nación | ✅ Parseado |
| Galicia | 🔍 Detectable, sin parser |

Las fechas se manejan en formato `DD/MM/AAAA`. Los montos usan formato argentino (`.` miles, `,` decimal).

## Infraestructura

Lambda handler en `src/main.py`. API Gateway (body base64) o S3 events (pendiente).
