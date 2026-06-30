# Auditoría Técnica — Sistema de Procesamiento de Extractos Bancarios

## Versión Auditada

Workflow n8n: `Extractos bancarios` (`Onk9wdxHWMn0aJbE`)

---

## 1. Comprensión del Flujo Completo

El sistema recibe un PDF de extracto bancario argentino y devuelve un JSON estructurado con todas las transacciones detectadas.

**Flujo de negocio:**

1. **Ingreso del PDF** — Un usuario envía un documento PDF por Telegram. El trigger de Telegram captura el mensaje incluyendo metadatos (tipo MIME, nombre de archivo, ID del chat, ID del usuario).

2. **Validación de formato** — Se verifica que el documento sea efectivamente un PDF. Si no lo es, se responde inmediatamente con un mensaje de error ("Solo se permiten documentos en formato PDF").

3. **Extracción de texto** — El PDF se procesa mediante PyPDF (nodo Extract from File de n8n) para obtener el texto plano.

4. **Normalización inicial** — Se unifican los saltos de línea (`\r\n` → `\n`, `\r` → `\n`) y se divide el texto en líneas no vacías.

5. **Detección del banco** — Mediante un sistema de puntuación que evalúa:
   - Patrones de texto característicos del banco en el contenido del PDF (+30 c/u)
   - Patrones en el nombre del archivo (+20 c/u)
   - Prefijo CBU (primeros 3 dígitos de cualquier número de 22 dígitos, +50)
   - Umbral mínimo: 30 puntos

6. **Enrutamiento por banco** — Según el banco detectado, se selecciona el parser específico.

7. **Parseo de transacciones** — Cada banco tiene su propio parser que:
   - **Macro**: Formato rígido de una línea por transacción. Regex única: `FECHA ref1 ref2 DESCRIPCIÓN $ importe $ saldo`
   - **Provincia**: Formato con descripciones multi-línea. Regex + merge de líneas consecutivas. Formato: `FECHA DESCRIPCIÓN importe referencia saldo`
   - **Nación**: Formato donde descripción y datos numéricos están en líneas separadas. Regex: `FECHA fecha2 importe referencia [saldo]` + descripción en línea aparte.

8. **Normalización de importes** — Todos los parsers convergen a un nodo común que:
   - Convierte formato argentino a número (`.` separador de miles, `,` decimal)
   - Elimina signos `$`
   - Retorna valores numéricos (`float`)

9. **Formateo** — Se construye el JSON final con metadatos (banco, fecha_desde, fecha_hasta) y el array de transacciones.

10. **Respuesta** — Se envía el JSON al usuario por Telegram.

---

## 2. Arquitectura Actual

### Organización

```
Telegram Trigger
    │
    ▼
Switch (PDF? → Sí/No)
    │               │
    ▼               ▼
Extract from File    Advertencia "solo PDF"
    │
    ▼
Banco y separar texto  ←── detección + split de líneas
    │
    ▼
Switch1 (banco?)
    ├──→ Parsear Macro
    ├──→ Parsear Provincia
    ├──→ Parsear Nacion
    └──→ Advertencia "no detectado"
           │
           ▼ (todos convergen)
    importes y saldos  ←── normalización de montos
    │
    ▼
Formatear JSON
    │
    ▼
Telegram: Return
```

### Responsabilidades por bloque

| Bloque | Responsabilidad |
|--------|-----------------|
| Recibir PDF | Trigger de Telegram, descarga del archivo binario |
| Switch | Clasificación por tipo MIME |
| Extract from File | PyPDF: PDF → texto plano |
| Banco y separar texto | Limpieza de texto + detección de banco (scoring) + split en líneas |
| Switch1 | Enrutamiento por banco detectado |
| Parsear Macro | Regex, filtro SKIP, parseo, ordenamiento |
| Parsear Provincia | Regex, merge multi-línea, filtro SKIP, parseo, ordenamiento |
| Parsear Nacion | Regex, split líneas transacción/descripción, filtro SKIP, parseo, ordenamiento |
| importes y saldos | Conversión de formato argentino a número |
| Formatear JSON | Serialización final |
| Return | Telegram: envío de respuesta |
| Error Trigger + Error Notification | Manejo de excepciones no capturadas |

### Decisiones tomadas

- **Scoring para detección de banco**: Mejor que detección secuencial (primer match). Permite que múltiples señales débiles sumen para una detección confiable.
- **Separación de parsers por banco**: Cada banco tiene formato distinto; aislarlos evita condicionales complejos.
- **Nodo compartido de normalización**: Los importes se normalizan igual para todos los bancos — DRY sense.
- **SKIP patterns monolíticos**: Misma lista copiada en cada parser — decisión cuestionable.

---

## 3. Problemas Encontrados

### Código duplicado

1. **SKIP patterns duplicados en TODOS los parsers** (~35 regex cada uno, copia exacta con mínimas variaciones). Si se agrega un patrón de skip, hay que actualizar 3+ nodos.

2. **Lógica de ordenamiento por fecha duplicada** en los 3 parsers — exactamente el mismo código de sort.

3. **Lógica de armado de `result`** duplicada: `{ banco, fecha_desde, fecha_hasta, detalle, aviso }` se construye idénticamente en cada parser.

4. **Validación de líneas vacías** duplicada: `if (!lines?.length) { return ... }` en cada parser.

### Acoplamiento

1. **Banco y separar texto** hace DEMASIADO: normaliza texto, detecta banco Y separa líneas. Tres responsabilidades distintas.

2. **Formato de salida acoplado entre nodos** — `importes y saldos` espera `{ fecha, descripcion, importe, saldo }` pero no hay contrato explícito. Si un parser cambia el formato, el error es silencioso.

3. **Acoplamiento a la estructura de Telegram** — El ID del chat se obtiene como `$("Recibir PDF").item.json.message.from.id`. Si la estructura del trigger cambia, todo el workflow se rompe.

4. **Conocimiento implícito de versiones de nodos** — Los números de version (`typeVersion`) están hardcodeados y son frágiles.

### Mantenibilidad

1. **Sin tipos ni esquemas** — Todo es `json` genérico. No hay validación de estructura en ningún punto.

2. **JS embebido en strings** — El código vive dentro del nodo Code de n8n. No se puede versionar, testear, ni formatear con linter.

3. **Sin documentación de formatos** — No existe documentación de qué formato espera cada banco. El conocimiento está en las regex.

4. **Sin documentación de formatos** — No existe documentación de qué formato espera cada banco. El conocimiento está en las regex.

5. **Constantes mágicas** — `30`, `20`, `50` (puntajes), `2` (límite de caracteres en descriptión), `3999` (límite de Telegram). Sin nombres ni justificación.

### Escalabilidad

1. **Agregar un banco requiere**:
   - Editar la definición en "Banco y separar texto"
   - Agregar ruta en Switch1
   - Crear nodo Code NUEVO con SKIP patterns copiados
   - Conectar nodo al flujo
   - Sin test automatizado

2. **No hay independencia entre bancos** — Todos comparten el mismo flujo. Un error en un parser no detectado puede propagarse.

### Diseño

1. **SKIP list es un cajón de sastre** — Headers, footers, metadatos, páginas, todo mezclado. Sin organización ni agrupación lógica.

2. **Parser de Nación usa algoritmo frágil** — Las líneas de descripción se guardan en un array paralelo indexado por posición. Si una línea de transacción no tiene descripción correspondiente, TODO se desfasa.

3. **Provincia mergea líneas pero Macro no** — Inconsistencia de diseño. O todos deberían soportar multi-línea, o la responsabilidad debería ser explícita.

4. **Galicia se detecta pero no se parsea** — Siempre cae en fallback. Es medio banco soportado.

### Legibilidad

1. **Regex largas sin comentarios** — `RE = /^(\d{2}\/\d{2}\/\d{4})\s+(.+?)\s+(-?[\d.,]+)\s+(\d{2}-\d{2})\s+(-?[\d.,]+)\s*$/` es críptico.

2. **Nombres de nodos inconsistentes** — "Banco y separar texto", "Switch1", "importes y saldos" (minúscula).

3. **Magic numbers en scoring**.

### Posibles bugs

1. **Galicia no tiene parser** — Cae siempre al fallback. El usuario recibe "No se encontró el banco".

2. **Parser de Nación: desfasaje de índices** — `desc[i]` asume que el array `desc` tiene los mismos índices que `tx`. Si hay una línea de descripción sin transacción, o viceversa, los datos se corrompen.

3. **Provincia merge multi-línea frágil** — Cualquier línea que NO empiece con fecha se considera continuación. Si una descripción comienza con dígitos (ej. "1er HONORARIO"), se mergea incorrectamente.

4. **Múltiples CBU en el texto** — El primer CBU encontrado puede no ser de la cuenta del extracto (ej. extracto de una cuenta pero menciona CBU de transferencia).

5. **Sin escape en regex** — Patrones como `C.C. ESPECIAL` usan `.` que en regex significa "cualquier caracter". Algunos SKIP tienen `.` sin escapar.

6. **`sort` con `new Date()` puede dar NaN** — Si una fecha está malformada, `new Date("undefined-undefined-undefined")` produce NaN y el sort se comporta impredeciblemente.

7. **Balance en Nación puede ser `null` y cause problemas downstream** — `m[5] || null` produce null, y si downstream hace operaciones aritméticas, cascada.

### Casos límite

1. **PDF sin texto** — PyPDF devuelve string vacío. Se maneja en Banco y separar texto, pero sin test.

2. **Extracto sin movimientos** — Se reporta "No se encontraron movimientos", pero en algunos casos podría ser un extracto válido.

3. **Descripciones extremadamente largas** (>500 chars) — Podrían romper líneas de manera impredecible.

4. **Importes con paréntesis** `(1.234,56)` para negativos — No se maneja actualmente.

5. **Multi-página** — Los headers/footers se repiten en cada página. SKIP list intenta filtrarlos, pero un header como "PESOS" también podría ser una transacción válida.

6. **Codificaciones no UTF-8** — ISO-8859-1, CP1252 — no se detecta explícitamente.

7. **Diferentes formatos de CBU** — A veces aparece como `xxxx-xxxx-xxxxxxxxxxxx` con guiones.

### Performance

1. **SKIP list itera COMPLETO por cada línea** — O(N×M) donde N = líneas, M = ~35 regex. Para un extracto de 200 líneas y 3 parsers, es aceptable pero ineficiente.

2. **Regex compiladas cada ejecución** — JS reinterpreta los literales `/pattern/` en cada invocación del Code node.

### Testeo

1. **CERO tests** — No hay unit tests, integration tests, ni golden tests.

2. **Solo se puede testear enviando PDF real por Telegram** — Sin mocking posible.

3. **No hay fixtures ni datos de muestra** — Imposible verificar comportamiento sin datos de prueba.

4. **Imposible verificar regresión** — Un cambio en las regex no tiene validación automática.

### Extensibilidad

1. **Agregar banco = tocar 4 archivos/nodos** — Alto costo cognitivo.

2. **No hay plugin/discovery de parsers** — Todo está hardcodeado en los nodos.

3. **No hay versión de formato** — Si un banco cambia su formato, no hay manera de versionar.

---

## 4. Riesgos

| Riesgo | Impacto | Probabilidad |
|--------|---------|--------------|
| Banco cambia formato de extracto → parser produce datos incorrectos silenciosamente | Alto | Media |
| PyPDF cambia comportamiento en nueva versión → extracción de texto diferente | Alto | Baja |
| Un CBU de transferencia dentro del extracto hace match como CBU de la cuenta | Medio | Alta |
| Línea de descripción comienza con fecha → parser de Provincia la trata como transacción nueva | Alto | Media |
| Galicia eventualmente implementado → requiere replicar todo el patrón actual con bugs | Medio | Seguro |
| Desfase en parser de Nación por línea extra (ej. salto de página) → transacciones con descripción incorrecta | Alto | Media |
| No hay validación de salida → JSON mal formado pero enviado igual | Alto | Alta |
| Sin monitoreo → no se detectan fallos hasta que el usuario lo reporta | Medio | Alta |
| No hay validación de salida → JSON mal formado pero enviado igual | Alto | Alta |

---

## 5. Propuesta de Nueva Arquitectura

### Patrón: Pipeline Arquitectónico (Pipes and Filters)

**¿Por qué?** El procesamiento de extractos es inherentemente un pipeline lineal de transformaciones. Cada etapa recibe un input, lo transforma, y pasa el resultado a la siguiente. No hay estado compartido, no hay interacciones complejas entre etapas.

**Alternativas descartadas:**

- **Clean Architecture con 5+ capas**: Overkill. El dominio NO es complejo — es una transformación de datos lineal. Agregar capas de abstracción solo añade indirección sin beneficio.
- **Event-Driven / CQRS**: Sin sentido para un proceso batch de un solo PDF.
- **Microservicios**: Un solo PDF por invocación, no hay razón para distribuir.

### Arquitectura propuesta

```
┌─────────────────────────────────────────────────────────────┐
│                     PIPELINE ORCHESTRATOR                    │
│                                                             │
│  PDF bytes → extract → normalize → filter → detect →       │
│  parse → normalize_amounts → validate → serialize → JSON    │
│                                                             │
│  Cada etapa es una función pura (input → output)            │
└─────────────────────────────────────────────────────────────┘
```

### Patrones adicionales

| Patrón | Dónde | Por qué |
|--------|-------|---------|
| **Strategy** | Parsers por banco | Cada banco tiene formato distinto. `Parser` es un protocolo/interface común. |
| **Factory** | Selección de parser | `ParserFactory.for_bank(bank_name)` devuelve el parser correcto. |
| **Value Object** | `Amount`, `Transaction` | Tipado fuerte sin ambigüedad. `Amount` encapsula validación y formato. |
| **Composition Root** | Handler de Lambda | Un solo punto donde se ensambla el pipeline. |
| **Result Object** | Pipeline stages | Cada etapa retorna `Result[T, Error]` en lugar de lanzar excepciones. |

### ¿Por qué NO clases pesadas?

- La lógica de negocio es **transformación de datos**, no comportamiento con estado.
- Las funciones puras son más fáciles de testear, componer y razonar.
- Los **dataclasses** y **Protocol** de Python dan el tipado necesario sin jerarquías complejas.
- Si en el futuro se necesita comportamiento más rico, se puede migrar gradualmente.

---

## 6. Estructura del Proyecto

```
extractos-bancarios/
├── pyproject.toml              # Dependencias y metadata del proyecto
├── Makefile                    # Comandos comunes (test, lint, build, deploy)
├── .env.example                # Variables de entorno de ejemplo
├── .gitignore
│
├── src/
│   ├── __init__.py
│   │
│   ├── main.py                 # Lambda handler (Composition Root)
│   ├── pipeline.py             # Orquestador del pipeline
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── statement.py        # Statement, Transaction
│   │   ├── bank.py             # Bank (enum con metadatos)
│   │   └── errors.py           # Errores tipados del dominio
│   │
│   ├── extractors/
│   │   ├── __init__.py
│   │   └── pdf.py              # PDF → texto plano (pypdf/pymupdf)
│   │
│   ├── cleaners/
│   │   ├── __init__.py
│   │   ├── normalizer.py       # Normalización de texto (encodings, line endings)
│   │   └── filters.py          # Eliminación de headers/footers/metadata
│   │
│   ├── detectors/
│   │   ├── __init__.py
│   │   └── bank.py             # Detección de banco (scoring configurable)
│   │
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py             # Protocol/ABC para parsers de banco
│   │   ├── macro.py            # Parser Banco Macro
│   │   ├── provincia.py        # Parser Banco Provincia
│   │   ├── nacion.py           # Parser Banco Nación
│   │   ├── galicia.py          # Placeholder para Galicia
│   │   └── factory.py          # ParserFactory
│   │
│   ├── normalizers/
│   │   ├── __init__.py
│   │   └── amount.py           # Normalización de importes (AR$ → Decimal)
│   │
│   ├── validators/
│   │   ├── __init__.py
│   │   └── schema.py           # Validación de Statement completo
│   │
│   └── serializers/
│       ├── __init__.py
│       └── json.py             # JSON serialization con Decimal handling
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Fixtures compartidos
│   ├── fixtures/               # Datos de prueba
│   │   ├── macro/
│   │   │   ├── sample.txt      # Texto extraído real
│   │   │   └── sample.json     # Golden output esperado
│   │   ├── provincia/
│   │   ├── nacion/
│   │   └── galicia/
│   │
│   ├── test_pipeline.py        # Integration: pipeline completo
│   ├── test_detectors.py       # Detección de banco
│   ├── test_parsers/
│   │   ├── test_macro.py
│   │   ├── test_provincia.py
│   │   ├── test_nacion.py
│   │   └── test_factory.py
│   ├── test_normalizers.py     # Normalización de importes
│   ├── test_filters.py         # Limpieza de headers/footers
│   └── golden/                 # Golden tests (snapshot)
│       ├── test_macro_golden.py
│       ├── test_provincia_golden.py
│       └── test_nacion_golden.py
│
├── infra/
│   ├── template.yaml           # SAM template
│   └── Dockerfile              # Lambda container (alternativa)
│
└── docs/
    └── adding-new-banks.md     # Guía para agregar bancos
```

### Convenciones

- **Módulos**: `snake_case`
- **Clases**: `PascalCase`
- **Funciones**: `snake_case`
- **Constantes**: `UPPER_SNAKE_CASE`
- **Tipos**: Siempre type hints
- **Imports**: stdlib → third-party → local (separados por línea en blanco)
- **Tests**: Un archivo por módulo, fixtures en directorio separado

---

## 7. Modelado del Dominio

```python
@dataclass(frozen=True)
class Amount:
    """Value Object: Representa un monto monetario."""
    value: Decimal
    sign: int  # -1, 0, 1

    @property
    def signed_value(self) -> Decimal:
        return self.value * self.sign

@dataclass(frozen=True)
class Transaction:
    """Transacción individual del extracto."""
    date: date
    description: str
    amount: Amount
    balance: Amount | None

@dataclass(frozen=True)
class Statement:
    """Extracto bancario completo."""
    bank: Bank
    transactions: tuple[Transaction, ...]
    date_from: date | None
    date_to: date | None
    metadata: dict[str, str]       # CBU, CUIT, cuenta, etc.
    warnings: tuple[str, ...]
```

**¿Por qué `frozen=True`?** Inmutabilidad evita mutaciones accidentales en el pipeline. Cada etapa produce nuevos objetos.

**¿Por qué `Decimal` y no `float`?** `0.1 + 0.2 != 0.3` en float. `Decimal` es correcto para dinero.

**¿Por qué `tuple` en lugar de `list`?** Las transacciones ordenadas no deberían mutarse. `tuple` es inmutable por defecto.

**¿Por qué `date` y no `str`?** Validación temprana. Si una fecha no se puede parsear, falla rápido.

**¿Por qué `Amount.sign` separado?** Los negativos en extractos bancarios tienen semántica distinta (débito vs crédito). Separar signo de magnitud permite conservar la semántica original.

---

## 8. Pipeline de Procesamiento

```
                    ┌──────────────┐
  PDF bytes ───────▶│  extractor   │
                    └──────┬───────┘
                           ▼ raw_text: str
                    ┌──────────────┐
                    │  normalizer  │
                    └──────┬───────┘
                           ▼ normalized: str
                    ┌──────────────┐
                    │   filters    │
                    └──────┬───────┘
                           ▼ clean_lines: list[str]
                    ┌──────────────┐
                    │   detector   │
                    └──────┬───────┘
                           ▼ bank: Bank
                    ┌──────────────┐
                    │    parser    │
                    │  (factory)   │
                    └──────┬───────┘
                           ▼ raw_tx: list[RawTx]
                    ┌──────────────┐
                    │  normalizer  │
                    │   (amount)   │
                    └──────┬───────┘
                           ▼ tx: list[Transaction]
                    ┌──────────────┐
                    │  validator   │
                    └──────┬───────┘
                           ▼ Statement
                    ┌──────────────┐
                    │ serializer   │
                    └──────┬───────┘
                           ▼ JSON string
```

**Diferencias clave con el actual:**

1. **Parser separado en dos fases**: Primero se detecta el banco, luego se selecciona el parser. No más Switch de n8n.
2. **Filters como etapa explícita**: La SKIP list sale de los parsers y se vuelve configuración independiente.
3. **Validación como etapa final**: Se verifica que el Statement sea coherente antes de serializar.
4. **Metadata extraída**: CBU, CUIT, tipo de cuenta se capturan durante el parseo (no existen actualmente).

---

## 9. Detección del Banco

### Análisis del mecanismo actual

El scoring actual es bueno conceptualmente:

```
score = sum(text_matches × 30) + sum(filename_matches × 20) + (CBU_prefix_match × 50)
threshold = 30
```

**Fortalezas:**
- Múltiples fuentes de evidencia combinadas
- CBU es muy confiable (+50)
- Fácil de extender: solo agregar patterns

**Debilidades:**
- Threshold arbitrario sin justificación estadística
- Filename es señal débil (depende del usuario)
- El scoring no es probabilístico ni normalizado
- Text patterns pueden ser demasiado específicos o demasiado genéricos
- Banco Provincia y Nación pueden compartir palabras ("Banco", "EXTRACTO DE CUENTA")

### Propuesta de mejora

1. **Mantener scoring pero con pesos configurables desde un archivo YAML/JSON** — No hardcodeados.
2. **Agregar nivel de confianza**: `HIGH` (≥80), `MEDIUM` (≥50), `LOW` (≥30), `NONE` (<30).
3. **Agregar detección por formato de transacción**: Si el banco no se pudo detectar por contenido, intentar inferir por el formato de las líneas de transacción (fallback).
4. **Emitir warning si confianza es LOW**: El JSON final incluye `confidence: "low"` para que el consumidor decida.
5. **CBU parsing más robusto**: Aceptar formato con/sin guiones: `\b(\d{3})\d{19}\b` o `\b(\d{3})-\d{4}-\d{15}\b`.

---

## 10. Parsing — Análisis Profundo

### Evaluación de estrategias

| Estrategia | Pros | Contras | Recomendada para |
|------------|------|---------|------------------|
| **Regex gigante** | Simple, rápida | Frágil, sin recuperación, no multi-línea | Macro (formato rígido) |
| **Tokenizer + State Machine** | Robusta, maneja multi-línea, recuperable | Más código, overhead | Provincia (multi-línea) |
| **Parser incremental (line-by-line)** | Clara, fácil de debuggear | Verbosa | Todos (como base) |
| **Híbrida (clasificación + buffer)** | Flexible, reutilizable | Curva de aprendizaje | **RECOMENDADA** |

### Estrategia recomendada: Híbrida con clasificación de líneas

Cada parser implementa:

```python
class BankParser(Protocol):
    """Protocolo que todo parser de banco debe implementar."""

    bank: ClassVar[Bank]

    def classify_line(self, line: str) -> LineType:
        """Clasifica una línea: HEADER, TRANSACTION_START, CONTINUATION, FOOTER, UNKNOWN."""
        ...

    def parse_transaction(self, lines: list[str]) -> RawTransaction:
        """Convierte una o más líneas (transacción + continuaciones) en RawTransaction."""
        ...
```

El pipeline de parseo:

```
clean_lines
    → classify_line() cada línea
    → agrupar: TRANSACTION_START + CONTINUATION* → bloque de transacción
    → parse_transaction() cada bloque
    → RawTransaction list
```

**¿Por qué esta estrategia?**

1. **Macro** se simplifica: `classify_line` detecta líneas que empiezan con fecha + 2 números → TRANSACTION_START
2. **Provincia** se beneficia: las continuaciones son `classify_line → CONTINUATION`
3. **Nación** se modela naturalmente: transacción y descripción en líneas alternas se agrupan en un bloque
4. **Nuevos bancos** solo implementan dos métodos: `classify_line` y `parse_transaction`
5. **Separación de concerns**: clasificación ≠ parseo ≠ normalización

### Análisis de regex actuales

**Macro:**
```
/^(\d{2}\/\d{2}\/\d{4})\s+(\d+)\s+(\d+)\s+(.+?)\s+\$\s*(-?[\d.,]+)\s+\$\s*(-?[\d.,]+)$/
```
- Grupos: fecha, ref1, ref2, descripción, importe, saldo
- Asume que SIEMPRE hay dos referencias numéricas después de la fecha
- Las referencias (618724, 493) son números de transacción internos del banco
- No captura si no hay signo `$` (formato regional inconsistente)

**Provincia:**
```
/^(\d{2}\/\d{2}\/\d{4})\s+(.+?)\s+(-?[\d.,]+)\s+(\d{2}-\d{2})\s+(-?[\d.,]+)\s*$/
```
- Grupos: fecha, descripción, importe, referencia (dd-dd?), saldo
- El `.+?` (lazy) en descripción significa que el regex "regala" lo mínimo a descripción y el resto a los grupos siguientes
- El grupo `\d{2}-\d{2}` probablemente sea código de sucursal o tipo de operación
- No maneja multi-línea nativamente — por eso existe `mergeMultiLine` aparte

**Nación:**
```
/^(\d{2}\/\d{2}\/\d{4})\s+(\d{2}\/\d{2}\/\d{4})\s+(-?[\d.,]+)\s+(\d+)(?:\s+(-?[\d.,]+))?$/
```
- Grupos: fecha, fecha_valor, importe, código_referencia, saldo (opcional)
- Dos fechas: fecha de operación y fecha valor
- Saldo es opcional (Nación a veces no lo incluye por línea)
- Descripción está en LÍNEA SEPARADA — esto es frágil si hay desfasaje

### Mejoras propuestas para cada banco

**Macro:**
```python
# En lugar de 3 grupos: ref1 + ref2 + descripción
# Mejor: (fecha) (resto) donde resto se analiza:
#   - Primeros 1-2 tokens numéricos = referencias
#   - Resto hasta $ importe $ saldo = descripción
```

**Provincia:**
```python
# Formalizar el merge multi-línea como un state machine simple:
# - Línea con fecha inicio → START
# - Líneas sin fecha → CONTINUATION (acumular en buffer de descripción)
# - Cuando se completa el patrón → emitir transacción
```

**Nación:**
```python
# Eliminar dependencia de índices paralelos.
# Agrupar (línea_transacción, línea_descripción) como bloque.
# Si falta descripción → warning + descripción genérica "S/N"
```

---

## 11. Normalización

### Fechas

| Formato actual | Estrategia |
|----------------|------------|
| `DD/MM/YYYY` | `datetime.strptime(fecha, "%d/%m/%Y").date()` |
| `DD/MM/YYYY` (segunda fecha Nación) | Mismo parser |

- **Error**: Lanzar excepción con contexto: `línea X: fecha inválida "{raw}"`
- **Output**: ISO `YYYY-MM-DD` (o configurable)

### Importes

Pipeline de normalización:

```
raw: str
    → strip("$ ", "$\t", "$")  # eliminar símbolo moneda
    → detectar negativo: trailing "-", leading "-", paréntesis "(1.234,56)"
    → strip("(" , ")") si aplica
    → separar miles/decimales:
        - último "," es decimal
        - "." son separadores de miles
        - eliminar todos los "." antes del último ","
        - reemplazar "," por "."
    → Decimal(resultado)
    → aplicar signo
    → Amount(value, sign)
```

Edge cases:

| Input | Output |
|-------|--------|
| `$ 1.234,56` | `1234.56` |
| `$-1.234,56` | `-1234.56` |
| `1.234,56-` | `-1234.56` |
| `(1.234,56)` | `-1234.56` |
| `$ 1.000` | `1000` |
| `0,50` | `0.50` |
| `-0` | `0` |
| `""` | `0` |
| `null` | `None` → warning |

---

## 12. Testing

### Pirámide de testing

```
         ╱╲
        ╱  ╲
       ╱Golden╲       ← 1-2 por banco (snapshot test)
      ╱────────╲
     ╱Integration╲     ← Pipeline completo por banco
    ╱──────────────╲
   ╱   Unit tests    ╲  ← Cada función/módulo individual
  ╱────────────────────╲
```

### Unit tests

| Módulo | Qué testear | Cantidad estimada |
|--------|-------------|-------------------|
| `normalizers/amount.py` | Edge cases de formato AR$ | 15-20 |
| `cleaners/filters.py` | Cada patrón SKIP individual | 10-15 |
| `cleaners/normalizer.py` | Encodings, line endings | 5-10 |
| `detectors/bank.py` | Cada banco con texto conocido | 8-12 |
| `parsers/*.py` | Líneas individuales, multi-línea, errores | 20-30 por parser |
| `validators/schema.py` | Statement válido, inválido | 5-10 |

### Integration tests

- Pipeline completo con texto real de PDF de cada banco
- Verificar que `Statement` tiene la cantidad correcta de transacciones
- Verificar que los montos suman correctamente
- Verificar errores en pipeline para datos inválidos

### Golden tests (Critical)

Para CADA banco:

1. **Input**: Archivo `.txt` con el texto extraído de un PDF real
2. **Output esperado**: Archivo `.json` con el resultado exacto esperado
3. **Test**: `assert pipeline(text) == expected_json`

Esto garantiza que:
- Refactors no alteran el output
- Nuevos bancos no rompen existentes
- El comportamiento observable es idéntico

**Mecanismo**: `pytest` + `json` diff. Si el output cambia deliberadamente, se actualiza el golden file.

---

## 13. AWS Lambda

### Handler

```python
# src/main.py
import json
from src.pipeline import process_statement

def handler(event, context):
    try:
        # API Gateway: body en base64
        if "body" in event:
            pdf_bytes = base64.b64decode(event["body"])

        # S3 Event: buscar objeto en S3
        elif "Records" in event and event["Records"][0].get("s3"):
            pdf_bytes = download_from_s3(event["Records"][0]["s3"])

        else:
            return {"statusCode": 400, "body": json.dumps({"error": "Unsupported event source"})}

        result = process_statement(pdf_bytes)
        return {
            "statusCode": 200,
            "body": json.dumps(result, cls=StatementEncoder),
            "headers": {"Content-Type": "application/json"},
        }

    except Exception as e:
        logger.exception("Pipeline failed")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
```

### Empaquetado

| Opción | Pros | Contras |
|--------|------|---------|
| **ZIP + Layer** | Simple, rápido | Límite 250MB descomprimido |
| **Container Image (ECR)** | Mayor tamaño permitido, entornos reproducibles | Más lento build/deploy |
| **SAM + Layer** | Infraestructura declarativa | Curva de aprendizaje |

**Recomendación**: SAM con Lambda Layers:
- **Layer**: `pypdf` (o `pymupdf-light`) — dependencia pesada
- **Código app**: Deploy separado (rápido)
- **Lambda Web Adapter** si se quiere interfaz HTTP completa

### Variables de entorno

```env
LOG_LEVEL=INFO
PIPELINE_STRICT=true           # Fail fast en errores de parseo
DEFAULT_ENCODING=iso-8859-1    # Encoding por defecto de PDFs bancarios
S3_OUTPUT_BUCKET=              # Opcional: bucket para guardar resultados
```

### Observabilidad

- **Logging estructurado**: `{"level": "INFO", "stage": "extract", "duration_ms": 45, "chars": 12345}`
- **AWS X-Ray**: Tracing por etapa del pipeline (si la latencia lo justifica)
- **CloudWatch Metrics**: `ProcessingTime`, `PdfSize`, `TransactionsCount`, `ErrorCount`
- **Lambda Powertools**: Logger, Metrics, Tracer listos para usar

### Manejo de errores

| Error | HTTP Status | Payload |
|-------|-------------|---------|
| PDF inválido | 400 | `{"error": "invalid_pdf", "detail": "..."}` |
| Banco no detectado | 200 | `{"banco": null, "aviso": "...", "warnings": [...]}` |
| Parseo parcial | 200 | `{"banco": "...", "aviso": "...", "detalle": [...], "warnings": [...]}` |
| Error interno | 500 | `{"error": "internal_error"}` |

--- 

## 14. Performance

### Memoria

| Componente | Consumo estimado |
|------------|------------------|
| Python runtime | ~15 MB |
| pypdf/pymupdf | ~20-30 MB |
| PDF en memoria | ~1-10 MB (típico) |
| Texto extraído | ~0.1-1 MB |
| Procesamiento | ~5-10 MB |
| **Total** | **~50-80 MB** |

**Configuración Lambda recomendada**: 256 MB (suficiente, con margen).

### Velocidad

| Etapa | Tiempo estimado |
|-------|-----------------|
| Lectura del PDF | < 5ms |
| Extracción de texto (pypdf) | 50-200ms |
| Normalización | < 5ms |
| Filtrado | < 5ms |
| Detección de banco | < 10ms |
| Parseo | < 20ms |
| Normalización de importes | < 10ms |
| Validación | < 5ms |
| Serialización | < 5ms |
| **Total** | **~100-250ms** |

### Cold start

**Estrategias:**

1. **Lazy imports**: No importar todos los parsers en cold start. Solo importar el detector y el parser necesario después de la detección.
2. **Lambda Layers**: pypdf en Layer, app code separado (más rápido de descargar y cachear).
3. **Provisioned Concurrency**: Si la latencia de cold start es crítica (agrega ~1-2s).
4. **SnapStart** (Java/Python): Si el cold start es problema, SnapStart puede reducirlo drásticamente.

**Cold start esperado**:
- Sin optimización: ~2-3s
- Con lazy imports y layer: ~1-1.5s
- Con SnapStart: ~200-500ms

### Optimizaciones adicionales

1. **Regex compiladas una vez**: `re.compile()` a nivel de módulo, no por invocación.
2. **Parser cache**: `ParserFactory` cachea instancias de parser (singleton por banco).
3. **Streaming**: Si el PDF es enorme, procesar página por página. No aplica a extractos típicos.
4. **Early exit**: Si la extracción de texto falla, no ejecutar resto del pipeline.

---

## 15. Mejoras Adicionales

### 15.1 Validación de PDF

Antes de extraer texto, verificar:
- Magic bytes `%PDF` al inicio
- Que no sea PDF protegido por contraseña
- Que no sea imagen escaneada (sin texto extraíble)
- Que tenga al menos una página

### 15.2 Metadata extraction

Además de transacciones, extraer:
- **CBU / Alias** de la cuenta
- **CUIT / CUIL** del titular
- **Tipo de cuenta** (CC, CA, CS)
- **Moneda** (ARS, USD)
- **Período del extracto**
- **Sucursal**
- **Número de cuenta** (enmascarado)

Esto enriquece el output y permite validaciones cruzadas.

### 15.3 Detección de encoding automática

Los bancos argentinos suelen usar ISO-8859-1 o CP1252, pero algunos ya usan UTF-8.

```python
def detect_encoding(pdf_bytes: bytes) -> str:
    """Detecta encoding del texto del PDF."""
    # Estrategia: intentar UTF-8 primero, fallback a ISO-8859-1
    # Si hay caracteres como ñ, á, é con bytes correctos → UTF-8
    # Si hay caracteres Ã±, Ã¡ → era UTF-8 mal interpretado como latin1
```

### 15.4 Configuración externa de bancos

```yaml
# bancos.yaml
banks:
  - name: "Banco Macro"
    aliases: ["Macro"]
    detection:
      text_patterns:
        - "BANCO\\s+MACRO"
        - "C\\.C\\.\\s*ESPECIAL"
      filename_patterns:
        - "macro"
      cbu_prefix: "285"
    parser: "macro"
```

Ventajas:
- Agregar banco = agregar entrada YAML + parser Python
- No tocar código de detección
- Noel balance conocimiento de dominio en config, no en código

### 15.5 Clasificador de transacciones

Categorizar cada transacción:
- Débito / Crédito
- Transferencia / Depósito / Extracción / Impuesto / Honorario
- Tipo de operación

### 15.6 Detección de duplicados

Misma fecha + mismo importe + misma descripción = potencial duplicado. Emitir warning.

### 15.7 Checksum validation

Algunos extractos incluyen totales al final. Validar que la suma de transacciones coincida con el saldo final.

### 15.8 Modo CLI

```bash
python -m extractos_bancarios extract --input extracto.pdf --output resultado.json
```

Para testing local y debugging sin Lambda.

### 15.9 Health check

```python
# GET /health
def health_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "ok",
            "version": "1.0.0",
            "supported_banks": ["Macro", "Provincia", "Nacion"]
        })
    }
```

### 15.10 Dead letter queue

PDFs que fallaron el procesamiento → guardar en S3 para revisión manual. Incluir el error, timestamp y metadata.

---

## Resumen de Decisiones Arquitectónicas

| Decisión | Opción elegida | Alternativa descartada | Justificación |
|----------|---------------|----------------------|---------------|
| Arquitectura | Pipeline (Pipes & Filters) | Clean Architecture 5 capas | El dominio es transformación lineal, no necesitamos 5 capas |
| Parsers | Strategy Pattern (Protocol) | Herencia de clase base | Composición > Herencia. Protocol es duck typing seguro |
| Modelos | Dataclasses frozen | Pydantic | Sin dependencia extra, suficiente para el caso |
| Detección | Scoring configurable | ML / reglas fijas | Sin datos para ML, scoring da control explícito |
| Normalización | Decimal exacto | float | Dinero NO se representa con float |
| Serialización | JSON custom encoder | Pydantic | Sin dependencia extra |
| Testing | Golden tests + unit + integration | Solo unit tests | Golden tests garantizan que output observable no cambia |
| Lambda packaging | SAM + Layers | Container | Menor complexity para el caso de uso |
| Config bancos | YAML externo (futuro) | Hardcodeado | Primera iteración hardcodeada, migrar a YAML después |

---

**Fin del informe de auditoría.**

Próximo paso: esperar aprobación para comenzar implementación.
