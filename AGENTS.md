# extractos-bancarios

Procesamiento de extractos bancarios argentinos en PDF. Pipeline Python 3.12+ → AWS Lambda.

## Comandos

```sh
make install        # pip install -e ".[dev]"
make test           # pytest tests/ -v
make lint           # ruff check src/ tests/
make typecheck      # mypy src/
make test-coverage  # pytest tests/ --cov=src --cov-report=term-missing
make test-benchmark # pytest tests/ --benchmark-only
make clean          # rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
```

Orden: `make lint && make typecheck && make test`.

## Arquitectura

Pipeline lineal (Pipes & Filters). Cada etapa es función pura:

```
PDF bytes → extract → normalize → filter → detect_bank → parse → normalize_amounts → validate → serialize
```

Entrypoint: `src/pipeline.py:process_statement()`. Lambda handler en `src/main.py:handler()`.
CLI: `python -m src <pdf> [--strict]` (lee PDF del disco, imprime JSON por stdout).

Modelos `frozen=True` (dataclasses inmutables). `Decimal` para montos (nunca `float`).

## Bancos

- **Macro**: formato rígido 1 línea por tx. Regex: `FECHA ref1 ref2 DESCRIPCIÓN $ importe $ saldo`
- **Provincia**: descripciones multi-línea mergeadas con state machine. Regex: `FECHA DESCRIPCIÓN importe referencia saldo`
- **Nación**: descripción en línea separada de la numérica. **Algoritmo frágil**: array indexado paralelo (`desc_lines[i]`).
- **Galicia**: detectable pero **sin parser**. `ParserFactory` lanza `ValueError`.

Para agregar banco: `BankId` enum → registros en `detectors/bank.py` → parser implementando `BankParser` Protocol → `filters.py` (si extra) → `ParserFactory._create()`. Ver `docs/adding-new-banks.md`.

Detección por scoring: texto (+30 c/u), filename (+20), prefijo CBU (+50). Umbral mínimo 30.

## Convenciones de código

- `from __future__ import annotations` en todo archivo
- Snake case para funciones/módulos, PascalCase para clases, UPPER_SNAKE para constantes
- Imports: stdlib → third-party → local (separados por línea en blanco)
- Type hints obligatorios (mypy strict)
- `filter()` no devuelve list; no hay walrus operator `:=`

## Testing

- Unit tests por módulo en `tests/`. Fixtures compartidos en `conftest.py` (`FIXTURES` path).
- Datos de prueba por banco en `tests/fixtures/{banco}/sample.txt` + `sample.json` (golden).
- **Golden tests**: si no existe golden file, lo crean del output actual y hacen `pytest.skip()`. Revisar antes de dar por bueno.
- `test_pipeline.py` usa PDF real con `pytest.raises` (no hay fixture PDF sample).

## Edge cases conocidos

- `Amount.zero()` usa sign=0 (único caso). `signed_value = value * sign`
- Negativos aceptan `-prefijo`, `sufijo-`, y `(parentheses)`
- Importe sin `$` se acepta
- `normalize_amount(None)` y `normalize_amount("")` retornan `Amount.zero()`
- Nación: si falta línea descripción, usa `"S/N"` como fallback
- Si no detecta banco o no hay transacciones, igual retorna JSON 200 con `aviso`

## Infraestructura

Lambda handler vía API Gateway (body base64) o S3 events (no implementado).
Env vars: `LOG_LEVEL`, `PIPELINE_STRICT`, `DEFAULT_ENCODING`.
`infra/` vacío (pendiente template SAM o Dockerfile).

## Gotchas

- `_sort_key` se importa de `src.parsers.macro` y lo usan todos los parsers
- `validate_statement()` retorna un **nuevo** `Statement` con warnings agregados (inmutable)
- `serialize_statement()` convierte Decimal a float en JSON. `Amount` serializado como `signed_value`
- `make clean` usa `find` con `-exec rm` — no funciona en Windows nativo
