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

### Servicios (src/services/)

Capa de integración con AWS y persistencia, orquestada por `process_upload()`:

```
process_upload(pdf_bytes, filename)
  → calculate_sha256() → check exists_by_hash() (SQL Server)
  → upload_to_s3() (S3)
  → process_statement() (pipeline)
  → save() a SQL Server (UploadRecord con estado OK/ERROR)
  → build_success() / build_duplicate() / build_error()
```

- `orchestrator.py`: `process_upload()` — coordina todo el flujo, maneja errores con saves parciales
- `hash_service.py`: `calculate_sha256()` — hash para detección de duplicados
- `s3_service.py`: `upload_to_s3()` — sube PDF a `extractos/{YYYY}/{MM}/{uuid}.pdf`
- `upload_repository.py`: persistencia en SQL Server (pymssql). Tabla configurable via `DB_TABLE`
- `response_builder.py`: build_success/build_duplicate/build_error — respuestas estructuradas

### Extractors (src/extractors/)

Extracción de metadatos del documento además de las transacciones:
- `metadata.py`: orquesta CBU, account, account_type
- `cbu.py`: extracción de CBU desde header/footer blocks
- `account.py`: número de cuenta por scoring
- `account_type.py`: tipo de cuenta por pattern matching

## Bancos

- **Macro**, **Provincia**, **Nación**: detectables por texto/CBU/filename. Todos usan el **motor universal** (`stages/`), no hay parsers específicos por banco.

Para agregar banco: `BankId` enum → registros en `detectors/bank.py` → (opcional) hints/patrones extra en stages.

Detección por scoring: texto (+30 c/u regex), filename (+20 c/u), prefijo CBU (+50). Umbral mínimo 30.

## Convenciones de código

- `from __future__ import annotations` en todo archivo
- Snake case para funciones/módulos, PascalCase para clases, UPPER_SNAKE para constantes
- Imports: stdlib → third-party → local (separados por línea en blanco)
- Type hints obligatorios (mypy strict)
- `filter()` no devuelve list; no hay walrus operator `:=`

## Lambda Handler

**Archivo:** `src/main.py`

Recibe evento de API Gateway:
- **POST** con PDF en `body` (base64 o raw)
- `Content-Disposition` header opcional para filename
- S3 trigger: `NotImplementedError` (no implementado)

Configuración actual del Lambda (Docker):
- Base: `public.ecr.aws/lambda/python:3.12`
- Dependencias de compilación: `freetds-devel gcc` (pymssql)
- CMD: `src.main.handler`

### Variables de entorno

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `PIPELINE_STRICT` | No | `false` | Modo estricto (falla en lugar de warnings) |
| `DEFAULT_ENCODING` | No | `utf-8` | Codificación de caracteres |
| `S3_BUCKET` | Sí | — | Bucket para almacenar PDFs originales |
| `DB_HOST` | Sí | — | Host de SQL Server |
| `DB_PORT` | No | `1433` | Puerto de SQL Server |
| `DB_NAME` | Sí | — | Base de datos |
| `DB_USER` | Sí | — | Usuario de DB |
| `DB_PASSWORD` | Sí | — | Password de DB |
| `DB_TABLE` | No | `impo_uni_archivos_upload` | Tabla de persistencia |

## Modelo de datos SQL Server

Tabla `impo_uni_archivos_upload` (default):

| Columna | Tipo | Descripción |
|---|---|---|
| `hash_pdf` | varchar(64) PK | SHA-256 del PDF |
| `nombre_original` | varchar(255) | Nombre del archivo original |
| `bucket` | varchar(255) | Bucket S3 donde se almacenó |
| `s3_key` | varchar(512) | Key en S3 |
| `s3_url` | varchar(1024) | URL pública del archivo |
| `json_resultado` | text | JSON de salida del pipeline (nullable, solo OK) |
| `estado` | varchar(20) | OK o ERROR |
| `fecha_upload` | datetime (default GETDATE()) | Fecha de creación |

## Testing

### Unit tests
- `tests/`: unit tests por módulo principal. Datos inline o en `tests/samples/` para PDFs reales.
- `tests/test_stages/`: tests individuales por cada etapa del pipeline (9 archivos, ~40 tests total). Usan `helpers.py` con funciones factory.
- `tests/test_services/`: tests para orchestrator, S3, hash, response builder, upload repository.
- `test_pipeline.py`: tests de integración + **golden tests** (procesan PDF real y comparan contra golden JSON). Si no existe golden, lo crean y fallan con `pytest.skip()`.
- `test_detectors.py`: detección de banco (10 tests: texto, CBU, filename, combinado, no-detección).
- `test_normalizers.py`: normalización de montos (12 tests: cero, positivo, miles, negativo en todos sus formatos).
- `test_validators.py`: validación de Statement (4 tests: válido, vacío, duplicados, date_from > date_to).
- `test_extractors.py`: extracción de metadatos (40+ tests para CBU, account, account_type).

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
- `tests/samples/golden_nacion.json` — output esperado para `09-SEPTIEMBRE 2019 CTA 54 pdf.pdf`

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

## Known Gaps / Technical Debt

### Bugs
- `tests/laboratorio/test_robustez.py` accede a `result.stage_confidence` que no existe en `MutatedResult` (`tests/mutations/runner.py`)
- `README.md` tiene marcadores de merge conflict sin resolver (líneas 107-110)

### No implementado
- S3 trigger en Lambda (`src/main.py:29` — `raise NotImplementedError`)
- `src/models/trace.py` está vacío (eliminar)

### Producción
- No hay Infrastructure as Code (Terraform/CDK/SAM) para API Gateway, Lambda, S3, VPC, IAM
- No hay secret management (credenciales DB en env vars)
- No hay monitoreo (CloudWatch alarms, métricas de negocio)
- No hay DLQ para eventos fallidos
- `pipeline.py` usa `print()` en lugar de logging estructurado
- No hay validación de tamaño/content-type a nivel API Gateway
- No hay graceful degradation: si S3 falla, no procesa
- No hay OpenAPI/Swagger spec
- Documentación de deploy incompleta (ver `docs/roadmap-deploy.md`)

## Gotchas

- `validate_statement()` retorna un **nuevo** `Statement` con warnings agregados (inmutable)
- `serialize_statement()` convierte Decimal a float en JSON. `Amount` serializado como `signed_value`
- `make clean` usa `find` con `-exec rm` — no funciona en Windows nativo
- `tests/mutations/` y `tests/laboratorio/` se excluyen del CI (`--ignore`) por ser lentos
- El processor valida magic bytes `%PDF` y usa `x_tolerance=3` en pdfplumber
- Transformación completa de entrada a salida documentada en `docs/guia-proyecto.md`
- Para deploy en producción, ver `docs/roadmap-deploy.md`
