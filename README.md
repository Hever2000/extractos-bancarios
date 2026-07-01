# extractos-bancarios

Extrae movimientos de extractos bancarios argentinos en PDF y los convierte a JSON estructurado.

Diseñado para AWS Lambda. Procesa cualquier extracto con estructura tabular sin importar el banco.

## Flujo

```
PDF → PdfplumberProcessor → Document (words con coordenadas)
  → block_builder (agrupa words en líneas)
  → table_detector (detecta regiones tabulares por fechas)
  → header_detector / footer_detector (limpia encabezados/pies)
  → column_detector (clasifica columnas: fecha, importe, descripción, saldo)
  → row_extractor (asigna words a celdas)
  → row_merger (fusiona descripciones multi-línea)
  → column_mapper (mapea a modelo canónico)
  → transaction_builder (construye Transaction objects)
  → validate → serialize → JSON
```

Cada etapa es una función pura. Datos inmutables en todo el pipeline.

## Estructura

```
src/
├── models/           # Modelos de dominio (Amount, Transaction, Statement, Document, Table)
├── processors/       # Backend de PDF (abstraído via Protocol, implementado con pdfplumber)
├── detectors/        # Detección de banco por texto/CBU/filename (scoring)
├── stages/           # Pipeline de extracción universal (9 etapas)
├── normalizers/      # Normalización de montos (formato argentino → Decimal)
├── serializers/      # Serialización a JSON
├── validators/       # Validación de Statement con warnings
├── pipeline.py       # Orquestador del pipeline completo
├── main.py           # Lambda handler (API Gateway)
└── __main__.py       # CLI
```

## Uso

```sh
pip install -e ".[dev]"

# CLI
python -m src extracto.pdf
python -m src extracto.pdf --strict

# Tests
make test
make lint
make typecheck
```

## Comandos

| Comando | Descripción |
|---------|-------------|
| `make install` | Instalar dependencias |
| `make test` | Ejecutar tests |
| `make lint` | Ruff (linter + formateo) |
| `make typecheck` | MyPy strict |
| `make test-coverage` | Pytest con cobertura |
| `make clean` | Limpiar cachés |

## Requisitos

- Python 3.12+
- Dependencias: solo `pdfplumber` en producción

## CI/CD

GitHub Actions corre lint, typecheck y tests en cada PR/push a main.

## Despliegue (AWS Lambda)

El proyecto está preparado para Lambda mediante Docker. Ver `Dockerfile` y `docker-compose.yml`.

```sh
make docker-build
make docker-test
```
