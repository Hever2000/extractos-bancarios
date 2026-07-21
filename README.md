# 📊 Extractos Bancarios

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

Servicio de extracción de movimientos de extractos bancarios argentinos en PDF a JSON estructurado. Diseñado para **AWS Lambda** con arquitectura de funciones puras y pipeline declarativo.

---

## ¿Por qué existe esto?

En Argentina, cada banco emite extractos en PDF con formatos propietarios. Este servicio unifica la extracción de datos en un modelo JSON único, eliminando la necesidad de escribir parsers específicos por banco.

**Caso de uso principal:** AWS Lambda que recibe un PDF por API Gateway y devuelve el historial de transacciones estructurado para alimentar sistemas de conciliación contable o scoring crediticio.

---

## Flujo de Procesamiento

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

---

## Input / Output Contract

### Input (PDF)

- **Formato:** Cualquier extracto bancario argentino con estructura tabular.
- **Restricciones:**
  - Máximo 50 páginas (configurable vía `MAX_PAGES`).
  - PDF digital con texto seleccionable (no escaneado).

### Output (JSON)

El pipeline devuelve un json con esta estructura:

```json
{
  "banco": "Banco Macro",
  "fecha_desde": "01/12/2025",
  "fecha_hasta": "07/01/2026",
  "detalle": [
    {
      "fecha": "01/12/2025",
      "descripcion": "TRANSF 23132999619 VAR",
      "importe": 542000.0,
      "saldo": 2548968.83
    },
    {
      "fecha": "01/12/2025",
      "descripcion": "TPUSH GRISELDA VILLA",
      "importe": 12000.0,
      "saldo": 2006968.83
    }
  ]
 }

```

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

## Setup

```sh
git clone https://github.com/Hever2000/extractos-bancarios.git
cd extractos-bancarios

pip install -e ".[dev]"

python -m src extracto.pdf
python -m src extracto.pdf --strict

make test
make lint
make typecheck
```

## Requisitos

- Python 3.12+
- Dependencias: solo `pdfplumber` en producción

<<<<<<< HEAD
=======

>>>>>>> 26e950a99d573231b66e583ccae44ae220ee8fbc
