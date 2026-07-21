# extractos-bancarios

Procesamiento de extractos bancarios argentinos en PDF. Pipeline Python 3.12+ → AWS Lambda.

## Comandos

```sh
make install              # pip install -e ".[dev]"
make test                 # pytest tests/ -v
make lint                 # ruff check src/ tests/
make typecheck            # mypy src/
make test-coverage        # pytest tests/ --cov=src --cov-report=term-missing
make test-benchmark       # pytest tests/ --benchmark-only
make clean                # find __pycache__, *.pyc, .pytest_cache, .mypy_cache, .ruff_cache
make robustness           # pytest tests/laboratorio/ -v --tb=short -m robustez -x
make robustness-full      # pytest tests/laboratorio/ -v --tb=long --maxfail=5
make robustness-edge      # pytest tests/laboratorio/ -v --tb=short -m edge
make robustness-report    # pytest tests/laboratorio/test_robustez.py::test_consolidated_report
make docker-build         # docker compose build lambda
make docker-test          # docker compose run --rm test
make docker-lint          # docker compose run --rm lint
make docker-typecheck     # docker compose run --rm typecheck
make docker-all           # build + lint + typecheck + test (todo en Docker)
make docker-shell         # bash en el contenedor lambda
make docker-local         # docker compose up lambda (puerto 9000:8080)
make docker-deploy        # login ECR + tag + push (requiere AWS_ACCOUNT_ID, AWS_REGION)
```

Orden estándar: `make lint && make typecheck && make test`.
Orden full: `make docker-all`.

## Arquitectura

Pipeline lineal (Pipes & Filters). Cada etapa es función pura:

```
PDF bytes → extract → detect_bank → stages/ (universal engine) → normalize_amounts → validate → serialize
```

Entrypoint: `src/pipeline.py:process_statement()`. Lambda handler en `src/main.py:handler()`.
CLI: `python -m src <pdf> [--strict]` (lee PDF del disco, imprime JSON por stdout).

Modelos `frozen=True` (dataclasses inmutables). `Decimal` para montos (nunca `float`).

### Pipeline detallado (stages/)

9 etapas en `src/stages/`:

```
Document → block_builder → table_detector → header_detector → footer_detector
  → column_detector → row_extractor → row_merger → column_mapper → transaction_builder
```

- `block_builder`: agrupa words en TextBlocks (líneas) por proximidad vertical (y_tolerance=3)
- `table_detector`: detecta regiones tabulares por anclas de fecha DD/MM/YYYY (≥3) o fallback por montos
- `header_detector`: remueve bloques sobre la tabla que matchean patrones de encabezado
- `footer_detector`: remueve bloques bajo la tabla que matchean patrones de footer
- `column_detector`: clasifica columnas (DATE, AMOUNT, BALANCE, DESCRIPTION, REFERENCE, UNKNOWN)
- `row_extractor`: asigna words a celdas por columna, detecta continuaciones
- `row_merger`: fusiona filas de continuación en MergedRow
- `column_mapper`: mapea a NormalizedRow (formato canónico)
- `transaction_builder`: construye Transaction objects con Amount normalizados

`_utils.py`: `detect_lanes()` — detecta columnas agrupando intervalos de words por gap > 8px.

## Bancos

- **Macro**, **Provincia**, **Nación**, **Galicia**: detectables por texto/CBU/filename. Todos usan el **motor universal** (`stages/`), no hay parsers específicos por banco.

Para agregar banco: `BankId` enum → registros en `detectors/bank.py` → (opcional) hints/patrones extra en stages.

Detección por scoring: texto (+30 c/u regex), filename (+20 c/u), prefijo CBU (+50). Umbral mínimo 30.

## Convenciones de código

- `from __future__ import annotations` en todo archivo
- Snake case para funciones/módulos, PascalCase para clases, UPPER_SNAKE para constantes
- Imports: stdlib → third-party → local (separados por línea en blanco)
- Type hints obligatorios (mypy strict)
- `filter()` no devuelve list; no hay walrus operator `:=`

## Testing

### Unit tests
- `tests/`: unit tests por módulo principal. Datos inline o en `tests/samples/` para PDFs reales.
- `tests/test_stages/`: tests individuales por cada etapa del pipeline (9 archivos, ~40 tests total). Usan `helpers.py` con funciones factory.
- `test_pipeline.py`: tests de integración + **golden tests** (procesan PDF real y comparan contra golden JSON). Si no existe golden, lo crean y fallan con `pytest.skip()`.
- `test_detectors.py`: detección de banco (10 tests: texto, CBU, filename, combinado, no-detección).
- `test_normalizers.py`: normalización de montos (12 tests: cero, positivo, miles, negativo en todos sus formatos).
- `test_validators.py`: validación de Statement (4 tests: válido, vacío, duplicados, date_from > date_to).

### Mutation testing
Framework completo inline en `tests/mutations/` (sin librería externa):

- `base.py`: `MutationCategory` (20 categorías), `MutationContext`, `MutationOp`, helpers (pick_page, clone_words, rebuild_doc).
- `operators.py`: 30+ operadores en 16 categorías — HEADERS, FOOTERS, COLUMN_NAMES, COLUMN_ORDER, EXTRA_COLUMNS, MISSING_COLUMNS, ALIGNMENT_H, ALIGNMENT_V, SPACING, DATES, AMOUNTS, SPECIAL_CHARS, EMPTY_ROWS, DUPLICATE_ROWS, EXTREME_VALUES, UNEXPECTED_TEXT.
- `properties.py`: 12 propiedades de robustez (fecha valida, descripcion no vacía, Amount con sign/Decimal, date range consistente, sorted, serializable, etc.).
- `runner.py`: ejecuta el pipeline completo sobre un documento mutado.

### Laboratorio de robustez (`tests/laboratorio/`)
- `test_robustez.py`: 4 categorías de tests marcados `@pytest.mark.robustez`:
  - `test_individual_mutation`: cada operador individualmente (38 tests paramétricos)
  - `test_combined_mutations`: combinaciones de 2-3 operadores (7 combos)
  - `test_category_suite`: todos los operadores de una categoría (16 categorías)
  - Edge cases: fechas sin leading zero, montos como enteros, formatos mixtos, muchas transacciones, documento vacío, non-breaking spaces, balance antes que amount
  - `test_consolidated_report`: genera `robustness-report.json`

### Golden tests
- `tests/samples/golden_macro.json` — output esperado para `macro.pdf`
- `tests/samples/golden_provincia_nacion.json` — output esperado para `10005060869_20260202_extractos.pdf`

## Edge cases conocidos

- `Amount.zero()` usa sign=0 (único caso). `signed_value = value * sign`
- Negativos aceptan `-prefijo`, `sufijo-`, y `(parentheses)`
- Importe sin `$` se acepta
- `normalize_amount(None)` y `normalize_amount("")` retornan `Amount.zero()`
- Si no detecta banco o no hay transacciones, igual retorna JSON 200 con `aviso`
- `table_detector`: filtro por tolerancia de 3 misses consecutivos sin fecha
- `row_merger`: si una continuación tiene AMOUNT se convierte en nueva fila (no se fusiona)
- `column_mapper`: fechas faltantes se heredan de fila anterior
- `column_detector`: si hay ≥2 columnas AMOUNT, la última pasa a BALANCE

## Infraestructura

### Docker
- **Dockerfile**: imagen oficial AWS Lambda Python 3.12 (`public.ecr.aws/lambda/python:3.12`), copia `pyproject.toml` y `src/`, `pip install -e "."`, CMD `src.main.handler`
- **docker-compose.yml**: servicios lambda (puerto 9000:8080, samples montados en /samples), test, lint, typecheck

### CI/CD (`.github/workflows/ci.yml`)
- **verify** (push a main, PRs): matrix Python 3.12 + 3.13. `uv` → setup-python → `uv pip install -e ".[dev]"` → `ruff` → `mypy` → `pytest` (excluyendo laboratorio y mutations)
- **deploy** (solo tags `v*`): asume AWS role, login ECR, build/push image, `aws lambda update-function-code`

### Env vars
`LOG_LEVEL`, `PIPELINE_STRICT`, `DEFAULT_ENCODING`.

## Gotchas

- `validate_statement()` retorna un **nuevo** `Statement` con warnings agregados (inmutable)
- `serialize_statement()` convierte Decimal a float en JSON. `Amount` serializado como `signed_value`
- `make clean` usa `find` con `-exec rm` — no funciona en Windows nativo
- `tests/mutations/` y `tests/laboratorio/` se excluyen del CI (`--ignore`) por ser lentos
- El processor valida magic bytes `%PDF` y usa `x_tolerance=3` en pdfplumber
- Transformación completa de entrada a salida documentada en `docs/guia-proyecto.md`
