# Guía del Proyecto: Extractos Bancarios

## ¿Qué hace este proyecto?

Cada banco imprime sus extractos con su propio formato, sus columnas en distinto orden, sus propios encabezados y pies de página.

Este proyecto **toma cualquier extracto bancario argentino en PDF y lo convierte automáticamente a un JSON estructurado**.

El resultado final es un archivo JSON con esta pinta:

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
  ],
}
```

---

## Requisitos de entrada

### ¿Qué bancos soporta?

| Banco | Cómo lo detecta |
|---|---|
| **Banco Macro** | Por palabras como "BANCO MACRO" en el texto, por "macro" en el nombre del archivo, o por CBU que empiece con 285 |
| **Banco Provincia** | Por "BANCO PROVINCIA" o "EXTRACTO DE CUENTA INFORMATIVO", o CBU que empiece con 014 |
| **Banco Nación** | Por "BANCO NACION", "Fecha consulta:", o CBU que empiece con 011. También si el archivo se llama "nacion..." o "bna..." |

Si el sistema **no logra identificar el banco**, igual intenta procesar el extracto. No se rompe, simplemente devuelve el resultado con un aviso.

### ¿Cómo detecta el banco?

Usa un sistema de **puntajes** (scoring):

- Si encuentra palabras clave del banco en el texto del PDF: **+30 puntos** por cada una
- Si el nombre del archivo coincide: **+20 puntos**
- Si el CBU (Código Bancario Uniforme) empieza con el prefijo del banco: **+50 puntos**

Si el puntaje total es menor a 30, asume que no pudo identificar el banco.

---

## El Proceso (El Pipeline)

### Paso 1: Extraer el texto del PDF

**Archivo:** `src/processors/pdfplumber_impl.py`

Abre el pdf con `pdfplumber` que extrae cada palabra con sus coordenadas en la página: dónde está ubicada (posición X e Y), su tamaño, y la fuente tipográfica.

**Importante**: si el PDF es una imagen escaneada (no tiene texto seleccionable), este paso falla porque no hay palabras que extraer.

### Paso 2: Identificar el banco

**Archivo:** `src/detectors/bank.py`

Toma todo el texto extraído y el nombre del archivo, y aplica el sistema de puntajes para determinar de qué banco es el extracto.

### Paso 3: Agrupar palabras en líneas

**Archivo:** `src/stages/block_builder.py`

Las palabras extraídas están "sueltas". Este paso las **agrupa en líneas de texto**, juntando las que están cerca verticalmente (en el mismo renglón) y ordenándolas de izquierda a derecha.

### Paso 4: Encontrar la tabla de movimientos

**Archivo:** `src/stages/table_detector.py`

El extracto tiene encabezados, pies de página, y mucha información que no son movimientos. Este paso **encuentra dónde está la tabla** que contiene las transacciones.

¿Cómo hace? Busca **patrones de fecha** en formato DD/MM/AAAA. Si encuentra al menos 3 fechas cerca unas de otras, deduce que ahí empieza una tabla. Usa esas fechas como "anclas" para determinar los bordes superior e inferior de la tabla.

Si no encuentra fechas, busca montos con formato argentino (signo $ y números con punto de miles y coma decimal).

Una vez que encuentra la tabla, también detecta automáticamente **cuántas columnas tiene** y en qué posición están, midiendo los espacios entre palabras.

### Paso 5: Limpiar encabezados

**Archivo:** `src/stages/header_detector.py`

Saca del medio cualquier cosa que esté **arriba** de la tabla y que parezca un encabezado (fechas de consulta, CBU, nombre del banco, etc.).

### Paso 6: Limpiar pies de página

**Archivo:** `src/stages/footer_detector.py`

Saca del medio cualquier cosa que esté **debajo** de la tabla y que parezca un pie de página (totales, resúmenes, "SUMAS IGUALES", "SALDO ANTERIOR", "No. de registro", "PÁGINA", etc.).

### Paso 7: Clasificar las columnas

**Archivo:** `src/stages/column_detector.py`

Ahora que tenemos la tabla limpia, hay que entender **qué es cada columna**. El sistema analiza y clasifica:

| Tipo de columna | ¿Qué contiene? |
|---|---|
| **DATE (Fecha)** | Fechas en formato DD/MM/AAAA, DD/MM/AA, o nombres de mes |
| **AMOUNT (Importe)** | Números con signo $, formato argentino con puntos y comas |
| **BALANCE (Saldo)** | Lo mismo que importe, pero es la última columna numérica |
| **DESCRIPTION (Descripción)** | Texto libre que describe el movimiento |
| **REFERENCE (Referencia)** | Números de referencia, CBUs, códigos |
| **UNKNOWN (Desconocido)** | Lo que no entra en ninguna categoría |

Si detecta **dos o más columnas de importe (AMOUNT)**, automáticamente la última pasa a ser SALDO (BALANCE). Así maneja extractos que muestran "Debe" y "Haber" en columnas separadas.

### Paso 8: Extraer las filas

**Archivo:** `src/stages/row_extractor.py`

Con las columnas clasificadas, asigna cada palabra a la celda que le corresponde en cada fila. También detecta **filas de continuación**: son descripciones largas que ocupan dos o más renglones (por ejemplo, un movimiento que dice "TRANSFERENCIA DE" en una línea y "CUENTA CORRIENTE" en la siguiente). La segunda línea **no tiene fecha**, y eso es lo que permite identificarla como continuación.

### Paso 9: Fusionar descripciones multi-línea

**Archivo:** `src/stages/row_merger.py`

Junta las filas que son continuación de la anterior, **fusionando sus descripciones** en una sola. Hay una regla especial: si una línea de continuación tiene un importe, se convierte en un movimiento nuevo (no se fusiona).

### Paso 10: Mapear al formato estándar

**Archivo:** `src/stages/column_mapper.py`

Traduce las columnas del formato original de cada banco al **formato SOS** (fecha, descripción, importe, saldo). Las columnas que el sistema no pudo clasificar van a un campo "metadata" para no perder información. Las fechas que faltan (por herencia de filas de continuación) se completan automáticamente con la fecha de la fila anterior.

### Paso 11: Construir las transacciones

**Archivo:** `src/stages/transaction_builder.py`

Convierte cada fila ya mapeada en una **transacción** propiamente dicha.

### Paso 12: Normalizar montos

**Archivo:** `src/normalizers/amount.py`

Acá es donde los importes y saldos se normalizan: el formato argentino ($ 1.234,56) se convierte a un número estándar (1234.56). Los negativos se detectan si tienen **signo menos adelante** (-$100), **signo menos atrás** (100-), o están **entre paréntesis** (($100)).

### Paso 13: Validar y ordenar

**Archivo:** `src/validators/schema.py`

1. **Ordena** todas las transacciones por fecha (de más antigua a más reciente)
2. Calcula la **fecha desde** (primera transacción) y **fecha hasta** (última transacción)
3. **Valida** que todo tenga sentido:
   - Si no hay transacciones, agrega un aviso
   - Si hay transacciones duplicadas exactas, agrega un aviso
   - Si la fecha "desde" es posterior a la fecha "hasta", lanza un error (esto no debería pasar)

### Paso 14: Serializar a JSON

**Archivo:** `src/serializers/json.py`

Como paso final, convierte todo a JSON y lo devuelve.

Todos estos pasos están coordinados desde un único archivo **`src/pipeline.py`**, que es el que los encadena en orden, maneja los errores, y se asegura de que cada paso reciba lo que necesita del anterior.

### Metadatos adicionales

Además de las transacciones, el pipeline extrae metadatos del extracto:

| Archivo | Qué extrae |
|---|---|
| `src/extractors/cbu.py` | CBU de la cuenta (desde bloques de header/footer) |
| `src/extractors/account.py` | Número de cuenta (por sistema de scoring) |
| `src/extractors/account_type.py` | Tipo de cuenta (caja de ahorro, cuenta corriente, etc.) |

---

## Los Modelos (Cómo se representan los datos)

**Carpeta:** `src/models/`

Acá se definen los modelos para guardar la información en cada etapa:

### Word (Palabra)
Es la unidad más chiquita: una palabra con su texto, posición en la página (x0, x1, top, bottom), y la fuente tipográfica.

### TextBlock (Línea de texto)
Un conjunto de palabras que están en el mismo renglón.

### Page (Página)
Tiene un número de página y una lista de líneas de texto (TextBlocks).

### Document (Documento)
El PDF completo: un conjunto de páginas.

### Table (Tabla)
Representa la tabla de movimientos ya detectada. Tiene:
- **Lanes**: las columnas detectadas con su tipo (fecha, importe, etc.) y posición
- **Rows**: las filas con celdas
- **Raw words**: las palabras originales que caen dentro de la tabla

### ColumnLane (Carril de columna)
Una columna ya clasificada. Guarda el tipo (DATE, AMOUNT, DESCRIPTION, etc.) y el rango horizontal (de X a X) donde está.

### Cell (Celda)
Intersección de una fila y una columna. Contiene las palabras que caen en esa celda.

### Row (Fila) y MergedRow (Fila fusionada)
Row es una fila individual. MergedRow es el resultado de fusionar filas de continuación (tiene fecha, descripción combinada, importe, y saldo adicional si existe).

### NormalizedRow (Fila normalizada)
Es el formato estándar al que se convierten TODOS los extractos, sin importar de qué banco vengan: fecha, descripción, importe, saldo, y metadata adicional.

### Amount (Importe)
Un importe no es solo un número: tiene un **valor** (ej: 1500.50) y un **signo** (+1 para ingresos, -1 para egresos). El caso especial es "cero" donde el signo también es 0.

### Transaction (Transacción)
Es un movimiento ya listo para salir: fecha, descripción, importe (Amount), y saldo (Amount opcional).

### Statement (Extracto)
El resultado final del proceso: banco, fecha_desde, fecha_hasta, lista de transacciones, y warnings (avisos).

### UploadRecord (Registro de subida)
**Archivo:** `src/services/upload_repository.py`

Representa la persistencia del resultado en SQL Server: hash del PDF, metadatos de S3, JSON resultado, y estado (OK/ERROR).

### Tipos de errores
**Archivo:** `src/models/errors.py`

El proyecto define sus propios errores para distintas etapas:
- **ExtractError**: algo salió mal al leer el PDF
- **DetectionError**: no se pudo identificar el banco
- **ParseError**: no se pudieron interpretar los datos extraídos
- **ValidationError**: los datos no pasaron las validaciones finales

---

## Capa de Servicios (Integración AWS)

**Carpeta:** `src/services/`

Además del pipeline, el proyecto tiene una capa de servicios que orquesta toda la operación en AWS.

### Orchestrator (Orquestador)
**Archivo:** `src/services/orchestrator.py`

Coordina el flujo completo:
1. Calcula el SHA-256 del PDF
2. Verifica si ya existe (duplicado) consultando SQL Server
3. Si es nuevo, sube el PDF a S3
4. Ejecuta el pipeline de extracción
5. Guarda el resultado en SQL Server (con estado OK o ERROR)
6. Devuelve una respuesta estructurada

Si alguna etapa falla, intenta guardar un registro con estado ERROR para no perder el rastro del archivo.

### Hash Service
**Archivo:** `src/services/hash_service.py`

Calcula el SHA-256 del PDF para detección de duplicados.

### S3 Service
**Archivo:** `src/services/s3_service.py`

Sube el PDF original a S3 en la ruta `extractos/{YYYY}/{MM}/{uuid}.pdf`. Construye la URL pública del objeto.

### Response Builder
**Archivo:** `src/services/response_builder.py`

Construye respuestas estructuradas para tres escenarios:
- **success**: `{exito: true, banco, cantidad_transacciones, fecha_desde, fecha_hasta}`
- **duplicate**: `{exito: false, duplicado: true, mensaje}`
- **error**: `{exito: false, duplicado: false, mensaje}`

### Upload Repository
**Archivo:** `src/services/upload_repository.py`

Persistencia en SQL Server usando pymssql. Las operaciones son:
- `exists_by_hash(hash)`: consulta si un PDF ya fue procesado
- `save(record)`: inserta un registro con el resultado

---

## Cómo se usa

### Desde la línea de comandos
**Archivo:** `src/__main__.py` (punto de entrada), `src/pipeline.py` (procesamiento interno)

```bash
python -m src extracto.pdf          # Procesa el PDF y muestra el JSON
python -m src extracto.pdf --strict # Modo estricto (falla en lugar de dar avisos)
```

### Como servicio en la nube (AWS Lambda)
**Archivo:** `src/main.py`

El proyecto está preparado para correr en AWS Lambda como una **container image**. El Lambda handler recibe el PDF a través de API Gateway (en el body del POST como base64) y devuelve el JSON procesado.

Flujo completo en AWS:

```
WhatsApp Bot (otra Lambda)
    │ POST /process (PDF en body)
    ▼
API Gateway
    │
    ▼
Lambda (esta imagen Docker)
    ├── SHA-256 → check SQL Server (duplicado?)
    ├── Upload PDF a S3
    ├── Pipeline de extracción
    ├── Save resultado a SQL Server
    └── Response: {exito, duplicado, mensaje, resumen}
```

**Nota:** El trigger por S3 (cuando se sube un PDF a un bucket) no está implementado aún.

### Variables de entorno configurables

| Variable | Requerida | Default | Descripción |
|---|---|---|---|
| `LOG_LEVEL` | No | `INFO` | Nivel de log (DEBUG, INFO, WARNING, ERROR) |
| `PIPELINE_STRICT` | No | `false` | Modo estricto (falla en lugar de warnings) |
| `DEFAULT_ENCODING` | No | `utf-8` | Codificación de caracteres |
| `S3_BUCKET` | Sí | — | Bucket S3 para almacenar PDFs originales |
| `DB_HOST` | Sí | — | Host del SQL Server |
| `DB_PORT` | No | `1433` | Puerto del SQL Server |
| `DB_NAME` | Sí | — | Nombre de la base de datos |
| `DB_USER` | Sí | — | Usuario de base de datos |
| `DB_PASSWORD` | Sí | — | Password de base de datos |
| `DB_TABLE` | No | `impo_uni_archivos_upload` | Nombre de la tabla de persistencia |

---

## Los tests (Cómo se verifica que funciona)

Para asegurarse de que todo funcione correctamente, el proyecto tiene varias capas de pruebas:

### Tests unitarios (por pieza)
**Carpeta:** `tests/test_stages/` (cada etapa del pipeline) y archivos sueltos como `tests/test_detectors.py`, `tests/test_normalizers.py`, `tests/test_validators.py`

Cada componente del pipeline tiene su propio conjunto de pruebas. Por ejemplo, hay tests específicos para:

- **Detectores**: que identifiquen bien cada banco, que no confundan uno con otro, que respeten el puntaje mínimo
- **Normalizadores**: que conviertan correctamente los distintos formatos de importe
- **Cada etapa del pipeline**: que el detector de tablas encuentre la tabla, que el fusionador de filas junte bien las descripciones multi-línea, que el clasificador de columnas asigne bien los tipos, etc.
- **Validadores**: que detecten transacciones duplicadas, extractos vacíos, fechas inconsistentes
- **Servicios**: tests para orchestrator, S3, hash, response builder, upload repository

### Tests de integración (Golden Tests)
**Archivo:** `tests/test_pipeline.py` | **PDFs de muestra:** `tests/samples/` | **Resultados de referencia:** `tests/samples/golden_*.json`

Toman un **PDF real** (como un extracto del Banco Macro con ~64 movimientos, o uno del Banco Provincia con ~800 movimientos), lo procesan de principio a fin, y comparan el resultado contra un JSON "de referencia" (golden) que se guardó la primera vez que se ejecutó. Si el resultado cambia, el test falla. Esto asegura que cualquier modificación no rompa el resultado final.

### Laboratorio de robustez (Mutation Testing)
**Carpetas:** `tests/mutations/` (el motor de mutaciones) y `tests/laboratorio/` (las pruebas que lo usan)

Es un sistema más avanzado. Básicamente, el proyecto **se prueba a sí mismo al extremo**:

1. Toma un extracto real y lo procesa normalmente
2. **Introduce errores deliberados** en el PDF: mueve palabras de lugar, cambia fechas, borra columnas, agrega caracteres raros, desordena filas, etc.
3. Vuelve a procesar el PDF "mutado" y verifica que el sistema **siga funcionando sin romperse** y que los resultados sigan siendo razonables

Son más de 30 tipos de mutaciones diferentes, agrupadas en 16 categorías:

| Categoría | ¿Qué prueba? |
|---|---|
| Encabezados | Si aparecen encabezados raros o extra, ¿los ignora correctamente? |
| Pies de página | ¿Sabe ignorar textos al final de la página? |
| Nombres de columna | ¿Y si los nombres de las columnas cambian? |
| Orden de columnas | ¿Y si las columnas están en otro orden? |
| Columnas extras | ¿Maneja columnas que no esperaba? |
| Columnas faltantes | ¿Y si falta alguna columna importante? |
| Espaciado horizontal | ¿Y si las columnas están más juntas o más separadas? |
| Espaciado vertical | ¿Y si los renglones tienen distinto espacio entre sí? |
| Fechas | ¿Y si las fechas tienen formatos raros? |
| Importes | ¿Y si los montos tienen formatos extraños? |
| Caracteres especiales | ¿Y si aparecen símbolos raros o tildes? |
| Filas vacías | ¿Y si hay filas sin datos? |
| Filas duplicadas | ¿Y si hay filas repetidas? |
| Valores extremos | ¿Y si un monto es descomunalmente grande? |
| Texto inesperado | ¿Y si hay texto basura en medio de la tabla? |

Al final, genera un **reporte consolidado** que dice qué tan robusto es el sistema frente a cada tipo de problema.

---

## Infraestructura

### Docker

El proyecto corre en AWS Lambda usando una **container image**:

- **Base image:** `public.ecr.aws/lambda/python:3.12`
- **Dependencias de sistema:** `freetds-devel gcc` (necesario para compilar pymssql)
- **Entrypoint:** `src.main.handler`

### CI/CD (GitHub Actions)

El archivo `.github/workflows/ci.yml` define dos pipelines:

1. **verify** (push a main + PRs): corre lint (ruff), typecheck (mypy), y tests (pytest) en Python 3.12 y 3.13
2. **deploy** (tags v*): asume rol de AWS, buildea la imagen, la pushea a ECR, y actualiza la función Lambda

### Modelo de datos SQL Server

Tabla `impo_uni_archivos_upload` (configurable via `DB_TABLE`):

| Columna | Tipo | Descripción |
|---|---|---|
| `hash_pdf` | varchar(64) PK | SHA-256 del PDF |
| `nombre_original` | varchar(255) | Nombre original del archivo |
| `bucket` | varchar(255) | Bucket S3 |
| `s3_key` | varchar(512) | Key en S3 |
| `s3_url` | varchar(1024) | URL pública del archivo |
| `json_resultado` | text | JSON de salida (nullable, solo OK) |
| `estado` | varchar(20) | OK o ERROR |
| `fecha_upload` | datetime (default GETDATE()) | Fecha de creación |

---

## Limitaciones Conocidas

- **PDF escaneado**: si el PDF es una imagen (no tiene texto seleccionable), no se puede procesar
- **S3 trigger**: no implementado (solo se aceptan PDFs por API Gateway)
- **Tamaño máximo**: 10MB (configurable en `pipeline.py`)
- **Bancos soportados**: Macro, Provincia, Nación. Para agregar más, ver `src/detectors/bank.py`

Para más detalle sobre lo que falta para producción, ver `docs/roadmap-deploy.md`.
