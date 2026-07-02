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

**Carpeta:** `src/processors`

Abre el pdf con `pdfplumber` que extrae cada palabra con sus coordenadas en la página: dónde está ubicada (posición X e Y), su tamaño, y la fuente tipográfica.

**Importante**: si el PDF es una imagen escaneada (no tiene texto seleccionable), este paso falla porque no hay palabras que extraer.

### Paso 2: Identificar el banco

**Carpeta:** `src/detectors`

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

Saca del medio cualquier cosa que esté **arriba** de la tabla y que parezca un encabezado 

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

**Archivos:** `src/stages/transaction_builder.py` 

Convierte cada fila ya mapeada en una **transacción** propiamente dicha. 

### Paso 12: Validar y ordenar

**Carpeta:** `src/normalizers`

Acá es donde los importes y saldos se normalizan: el formato argentino ($ 1.234,56) se convierte a un número estándar (1234.56). Los negativos se detectan si tienen **signo menos adelante** (-$100), **signo menos atrás** (100-), o están **entre paréntesis** (($100)).

### Paso 13: Validar y ordenar

**Carpeta:** `src/validators`

1. **Ordena** todas las transacciones por fecha (de más antigua a más reciente)
2. Calcula la **fecha desde** (primera transacción) y **fecha hasta** (última transacción)
3. **Valida** que todo tenga sentido:
   - Si no hay transacciones, agrega un aviso
   - Si hay transacciones duplicadas exactas, agrega un aviso
   - Si la fecha "desde" es posterior a la fecha "hasta", lanza un error (esto no debería pasar)

### Paso 14 

**Carpeta:** `src/serializers`

Como paso final, convierte todo a JSON y lo devuelve.

Todos estos pasos están coordinados desde un único archivo **`src/pipeline.py`**, que es el que los encadena en orden, maneja los errores, y se asegura de que cada paso reciba lo que necesita del anterior.

---

## Los Modelos (Cómo se representan los datos)

**Carpeta:** `src/models/`

Aca se definen los modelos para guardar la información en cada etapa:

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

### Tipos de errores
**Archivo:** `src/models/errors.py`

El proyecto define sus propios errores para distintas etapas:
- **ExtractError**: algo salió mal al leer el PDF
- **DetectionError**: no se pudo identificar el banco
- **ParseError**: no se pudieron interpretar los datos extraídos
- **ValidationError**: los datos no pasaron las validaciones finales

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

El proyecto está preparado para correr en AWS Lambda. Recibe el PDF a través de una API (API Gateway), lo procesa en el servidor, y devuelve el JSON. También está preparado para recibir archivos desde S3 (el servicio de almacenamiento de Amazon), aunque esa funcionalidad aún no está implementada.

### Variables de entorno configurables

| Variable | Qué hace |
|---|---|
| `LOG_LEVEL` | Nivel de detalle de los mensajes de registro (DEBUG, INFO, WARNING, ERROR) |
| `PIPELINE_STRICT` | Si es "true", el modo estricto está activado por defecto |
| `DEFAULT_ENCODING` | Codificación de caracteres (utf-8 por defecto) |

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
| Fechas | ¿Y si las fechas tienenformatos raros? |
| Importes | ¿Y si los montos tienen formatos extraños? |
| Caracteres especiales | ¿Y si aparecen símbolos raros o tildes? |
| Filas vacías | ¿Y si hay filas sin datos? |
| Filas duplicadas | ¿Y si hay filas repetidas? |
| Valores extremos | ¿Y si un monto es descomunalmente grande? |
| Texto inesperado | ¿Y si hay texto basura en medio de la tabla? |

Al final, genera un **reporte consolidado** que dice qué tan robusto es el sistema frente a cada tipo de problema.



