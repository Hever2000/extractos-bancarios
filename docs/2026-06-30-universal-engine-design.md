# Universal Bank Statement Extraction Engine

## Design Document — 2026-06-30

## Status: Historical Reference

> **Note**: This document describes the original design. The implementation has evolved:
> `StageResult` has been removed (no stage returns tracing data), and the pipeline
> returns only the transformed result directly.

---

## 1. Executive Summary

Convert `extractos-bancarios` from a bank-specific parser architecture into a universal
document-structure extraction engine. The engine infers tables, columns, headers, footers,
and rows purely from **positional data** (word coordinates) and **content patterns**,
eliminating all bank-specific parsing code.

**Zero bank knowledge in the engine.** Bank detection remains as a separate concern for
business metadata only — it never conditions how parsing happens.

---

## 2. Philosophy

| Think in... | Not in... |
|---|---|
| Documents | Banks |
| Tables | Text |
| Rows | Lines |
| Columns | Regex |
| Structures | Patterns |

---

## 3. Architecture — Pipes & Filters

### 3.1 Pipeline

```
PDF bytes
  │
  ▼  Stage 1: PDFProcessor.extract()
Document (words with positions)
  │
  ▼  Stage 2: BlockBuilder.build()
Document.blocks (grouped into text lines)
  │
  ▼  Stage 3: TableDetector.detect()
list[Table] (tabular regions, by date-anchoring + lane overlap)
  │
  ▼  Stage 4: HeaderDetector.filter()  ── blocks OUTSIDE table bbox
Document (without header blocks)
  │
  ▼  Stage 5: FooterDetector.filter()  ── blocks OUTSIDE table bbox
Document (without footer blocks)
  │
  ▼  Stage 6: ColumnDetector.detect()  ── per table
Table.columns (lanes from density projection + content classification)
  │
  ▼  Stage 7: RowExtractor.extract()
Table.rows (words assigned to lanes)
  │
  ▼  Stage 8: RowMerger.merge()
MergedTable (multi-line descriptions merged via balance heuristic)
  │
  ▼  Stage 9: ColumnMapper.map()
list[NormalizedRow] (canonical + metadata)
  │
  ▼  Stage 10: TransactionBuilder.build()
list[Transaction] ← existing domain
  │
  ▼  Stage 11: StatementBuilder.build()
Statement ← existing domain
  │
  ▼  Stage 12: Validator (existing) → Serializer (existing)
JSON
```

### 3.2 Stage Contract

Every stage is a **pure function**: `(input, context) → (output, StageResult)`.

```python
@dataclass(frozen=True)
class StageResult:
    stage_name: str
    confidence: float          # 0.0 - 1.0
    metrics: dict[str, int]    # pages, blocks removed, rows, etc.
    warnings: tuple[str, ...]
```

### 3.3 BlockBuilder Algorithm (Stage 2)

Converts flat `Word` lists per page into `TextBlock` objects (visual lines).

1. For each page, sort all words by `(bbox.top, bbox.x0)` — top-to-bottom,
   left-to-right
2. Group words into lines: if two words have `abs(top_a - top_b) < 3px`,
   they are on the same visual line
3. For each line group, create a `TextBlock`:
   - `bbox` = union of all word bboxes
   - `words` = words sorted by `x0`
4. Result: `Document` with populated `Page.blocks`

No side effects. No shared state. All tracing is accumulated externally via
`TracingLogger`.

---

## 4. Domain Model (Rich Intermediate Representations)

### 4.1 Document Layer

```python
@dataclass(frozen=True)
class BBox:
    x0: float
    x1: float
    top: float
    bottom: float

@dataclass(frozen=True)
class Word:
    text: str
    bbox: BBox
    fontname: str | None

@dataclass(frozen=True)
class TextBlock:
    words: tuple[Word, ...]
    bbox: BBox

@dataclass(frozen=True)
class Page:
    number: int
    width: float
    height: float
    words: tuple[Word, ...]
    blocks: tuple[TextBlock, ...]

@dataclass(frozen=True)
class Document:
    pages: tuple[Page, ...]
```

### 4.2 Table Layer

> **Note on page-relative coordinates:** All `BBox` values are page-relative.
> pdfplumber returns coordinates relative to each page's own coordinate system.
> When a table spans multiple pages, each page has its own `Table` instance.
> The `ColumnMapper` stage handles cross-page merging by sorting all rows
> by (page_number, bbox.top) before building Transaction objects.

```python
class ColumnType(Enum):
    DATE = auto()
    AMOUNT = auto()
    BALANCE = auto()
    DESCRIPTION = auto()
    REFERENCE = auto()
    UNKNOWN = auto()

@dataclass(frozen=True)
class ColumnLane:
    """A geometric interval on the X axis derived from density projection.
    Not a cluster of x0 values — a lane spans the FULL column extent
    regardless of individual word alignment."""
    x0: float
    x1: float
    header_text: str | None
    detected_type: ColumnType
    confidence: float
    alignment: str = "left"  # "left" | "right" | "center"

@dataclass(frozen=True)
class Cell:
    text: str
    lane_index: int       # index into Table.lanes
    bbox: BBox

@dataclass(frozen=True)
class Row:
    cells: tuple[Cell, ...]
    is_continuation: bool   # True if this row has no date column content
    bbox: BBox
    page_number: int

    def has_column_type(self, col_type: ColumnType, lanes: tuple[ColumnLane, ...]) -> bool:
        return any(lanes[c.lane_index].detected_type == col_type for c in self.cells)

@dataclass(frozen=True)
class Table:
    lanes: tuple[ColumnLane, ...]
    rows: tuple[Row, ...]
    raw_words: tuple[Word, ...]  # all words within bbox, for ColumnDetector
    bbox: BBox
    page_number: int

@dataclass(frozen=True)
class MergedRow:
    primary_line: Row
    continuation_lines: tuple[Row, ...]

@dataclass(frozen=True)
class MergedTable:
    lanes: tuple[ColumnLane, ...]
    merged_rows: tuple[MergedRow, ...]
```

### 4.3 Canonical Layer

```python
@dataclass(frozen=True)
class NormalizedRow:
    date: str | None
    description: str
    amount: str | None
    balance: str | None
    metadata: frozendict[str, str]   # all unmapped columns
```

### 4.4 Existing Domain (unchanged)

`Amount`, `Transaction`, `Statement`, `Bank`, `BankId` — remain identical.

---

## 5. Column Detection Algorithm (The Brain)

### 5.1 Phase 1: Horizontal Density Projection (Lane Detection)

Allocate column lanes by projecting character density onto the X axis,
not by clustering individual `x0` values. This is critical because
right-aligned amounts have varying `x0` depending on digit length
(e.g., `$10,00` vs `$1.500.000,00`), which would fragment a single
column into multiple false candidates under naive clustering.

**Algorithm:**

1. Collect ALL `(x0, x1)` intervals from words in the table region
2. Sort intervals by `x0`
3. Merge overlapping/nearby intervals into continuous **lanes**:
   - If `start_i - previous_end > gap_threshold` (8px default) → new lane
   - Otherwise → extend previous lane's `x1` to `max(x1_i, previous_x1)`
4. Result: a list of `ColumnLane` objects, each with `(x0, x1)` spanning
   the full horizontal extent of that column

This captures the **full width** of each column regardless of alignment.
Amount columns produce a single lane even when individual values have
different `x0` positions, because their intervals overlap in X-space.

### 5.2 Phase 2: Alignment Detection

Per lane, collect all words whose `bbox` center falls within `(lane.x0, lane.x1)`.
Determine alignment:

| Pattern | Alignment |
|---|---|
| `x0` varies, `x1` consistent | Right-aligned (amounts, balances) |
| `x0` consistent, `x1` varies | Left-aligned (text, descriptions) |
| Center consistent | Center-aligned |

Amount/balance columns are almost always right-aligned. Description columns
are always left-aligned. This correlation serves as a classification signal.

### 5.3 Phase 3: Content Classification

Sample first N rows (3-5) and classify each cluster by content:

```python
def classify_column(values: list[str]) -> tuple[ColumnType, float]:
    # ALL match DD/MM/YYYY → DATE (high confidence)
    # ALL match ARS amount format → AMOUNT
    # Mixture of text, no numeric pattern → DESCRIPTION
    # ALL pure digits → REFERENCE
    # No clear match → UNKNOWN
```

### 5.4 Phase 4: Ambiguity Resolution

| Rule | Action |
|---|---|
| Multiple AMOUNT columns | Last → BALANCE, penultimate → AMOUNT |
| Multiple REFERENCE columns | All → metadata keys |
| UNKNOWN column with header text | header text → metadata key |
| UNKNOWN column without header | `columna_{index}` → metadata key |

### 5.5 Canonical Mapping Rules (deterministic)

When multiple columns share the same `ColumnType`, the mapping is
deterministic:

| Type | If single | If multiple |
|---|---|---|
| `DATE` | → `NormalizedRow.date` | First → date, rest → metadata keys `fecha_valor`, `fecha_original` |
| `DESCRIPTION` | → `NormalizedRow.description` | Concatenate with single space in column order (left to right) |
| `AMOUNT` | → `NormalizedRow.amount` | Penultimate → amount, last → balance |
| `BALANCE` | → `NormalizedRow.balance` | First → balance, rest → metadata |
| `REFERENCE` | → metadata | All → metadata keys `referencia_0`, `referencia_1`, etc. |
| `UNKNOWN` | → metadata | All → metadata keys inferred from position/header text |

### 5.6 Phase 5: Header Matching (optional, non-critical)

If text at the column's x-position exists in lines above the table start,
match against known header synonyms to reinforce classification.
This is a confidence boost, not a requirement.

---

## 6. Header/Footer Detection Strategy

> **Execution order:** Runs AFTER `TableDetector` (Stage 3). The table's `bbox`
> boundaries are already known, so header/footer detection is applied ONLY to
> blocks OUTSIDE the table region. Blocks INSIDE the table are never removed.

### Headers

Detected by a combination of position and content on blocks **outside** the table bbox:

| Signal | Weight |
|---|---|
| Block is above `table.bbox.top` | +0.3 |
| Matches known header patterns (bank names, "Últimos Movimientos", account types) | +0.5 |
| Single short line with no numeric content | +0.1 |
| Total ≥ 0.5 → classified as header | |

The detector emits how many headers were removed per page.

### Footers

| Signal | Weight |
|---|---|
| Block is below `table.bbox.bottom` | +0.3 |
| Matches known footer patterns ("Fecha de descarga:", "N de N", "Operador:", "Empresa:") | +0.5 |
| No date/amount patterns in content | +0.1 |
| Total ≥ 0.5 → classified as footer | |

Footers are removed per page from blocks below the table region.

### Known Pattern Dictionary

Patterns are grouped by function, not by bank:

```python
# Headers
HEADER_PATTERNS = re.compile(
    r"^(Últimos Movimientos|Extracto de Cuenta|C\.C\.|Caja de Ahorro|"
    r"Cuenta Corriente|Cuenta Sueldo|Pesos?|Tipo$|Número$|Moneda$|"
    r"BANCO\s+(MACRO|PROVINCIA|NACION|GALICIA)|"
    r"EXTRACTO DE CUENTA|Fecha consulta:|Hora consulta:|Cuenta: \d+)",
    re.I,
)

# Footers
FOOTER_PATTERNS = re.compile(
    r"^(Fecha de descarga:|Operador:|Empresa:|"
    r"\d+ de \d+$|CBU|DNI$|CIUDAD AUTONOMA|OLAVARRIA|"
    r"1000 - REGION|parámetros de búsqueda|búsqueda:)",
    re.I,
)
```

The heuristics also work for UNKNOWN patterns — any block that is
positionally at the top/bottom of the page and has no tabular structure
is a candidate for removal.

---

## 7. Table Detection Algorithm

### 7.1 Core Insight

Bank statements display tabular data where **words align vertically across
consecutive rows**. This vertical alignment is the universal signal that a
table exists — regardless of bank, layout, or column naming.

### 7.2 Algorithm: `TableDetector.detect()`

**Approach:** Date-anchored detection + geometric lane overlap.
No x0-cluster matching. No requirement that all rows share identical
column structure.

**Phase A — Date anchoring (find the table)**

```
For each page:
  1. Collect all TextBlocks sorted by top (y-position, top-to-bottom)
  2. Scan for anchor blocks containing DD/MM/YYYY patterns:
       - If found in ≥3 blocks → table EXISTS
       - Table vertical bounds: first_anchor.top → last_anchor.bottom
  3. If <3 date anchors found, fall back to amount-pattern anchors
     (blocks containing ARS number format with $, ., ,)
  4. If <3 amount anchors, fall back to REFERENCE digit anchors
     (blocks containing 6-22 digit sequences)
  5. If no anchor type reaches threshold → no table detected on this page
```

**Phase B — Lane detection (verify and extend)**

Once the anchor-defined region is established:

```
  6. Within anchor bounds, run Horizontal Density Projection on ALL words:
       - Collect (x0, x1) intervals, merge with gap_threshold=8px
       - Result: global lane intervals for this page's table
  7. Verify each block (anchor or between anchors) against global lanes:
       - Block belongs to table if ≥80% of its word centers fall within
         any global lane interval
       - Blocks that fail the test but contain date/amount patterns
         are still kept (conservative inclusion)
  8. Extend region upward: include blocks above first anchor if
     they overlap with global lanes (column header rows)
  9. Extend region downward: include blocks below last anchor if
     they keep the sliding window alive (≤2 consecutive blocks without
     date or amount patterns → close the table)
```

**Phase C — Build Table objects**

```
 10. Build Table:
       - BBox = union of all verified block bboxes
       - raw_words = all Word objects within BBox
       - lanes = result of density projection on raw_words
       - rows = empty (populated by RowExtractor in Stage 7)
       - page_number for cross-page tracking
```

### 7.3 Edge Cases

| Situation | Handling |
|---|---|
| Page has 2 separate tables (e.g., summary + detail) | Each anchor cluster produces its own Table if separated by ≥3 non-anchor blocks. Processed independently. |
| Table has blank rows (spacer rows) | Skipped if block has no word centers in any global lane |
| Table headers (column names) as first rows | Passed to ColumnDetector as potential header hints via `header_text` field, not discarded |
| Table continues across page break | Each page has its own Table; ColumnMapper sorts by (page, y) globally |
| Row missing reference/empty cell | Still captured — single columns missing don't break ≥80% overlap rule |
| Alternating debit/credit columns | Stage 6 ColumnDetector resolves via lane classification, not strict cluster matching |

### 7.4 Failure Mode

If no table region is found on any page, the stage returns:
- empty `tables` list
- `confidence: 0.0`
- `warnings: ("No tabular structure detected")`
- The pipeline continues gracefully → empty Statement with warning

---

## 8. Multi-Line Detection

Three modes detected automatically:

| Mode | Signal | Example |
|---|---|---|
| Single-line | Every row has content in all canonical columns | Banco Macro |
| Wrapped description | Row lacks date-column content, has description content | Banco Provincia |
| Separate description | Line has no canonical column content at all | Banco Nación |

### 8.1 Merge Algorithm

Not every row that lacks a date is a continuation. A row could be a
**new transaction that omitted the date** (common in Galicia, BBVA,
and other banks where date repeats from the row above).

**Balance heuristic** — the key differentiator:

| Condition | Classification | Action |
|---|---|---|
| No date + HAS amount/balance | New transaction (date omitted) | Inherit date from previous row. EMIT WARNING. |
| No date + NO amount/balance + HAS description text | Continuation | Merge description with previous row. |

Algorithm:

1. Compute a **column presence mask** per row (which lanes have content)
2. If mask lacks first-lane (DATE) content:
   a. If row `has_column_type(AMOUNT, lanes)` → **new transaction**
      → copy date from previous row, create new `MergedRow`, emit warning
   b. Else → **continuation** → add to previous `MergedRow.continuation_lines`
3. If mask HAS date content → new primary `MergedRow`
4. Description cells are concatenated across primary + continuation lines

---

## 9. PDF Backend (Abstracted)

### 9.1 Protocol

```python
class PDFProcessor(Protocol):
    def extract(self, pdf_bytes: bytes) -> Document:
        """PDF bytes → Document with positioned words."""
        ...
```

### 9.2 Default Implementation: pdfplumber

```python
class PdfplumberProcessor:
    def extract(self, pdf_bytes: bytes) -> Document:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(
                    extra_attrs=["fontname", "size"],
                    keep_blank_chars=True,
                    x_tolerance=3,
                )
                ...
```

### 9.3 Future Implementations (engine unchanged)

- `PyMuPDFProcessor` — C-based, faster
- `TextractProcessor` — AWS Textract OCR for scanned PDFs

---

## 10. Confidence Scoring

### 10.1 Per-Stage

| Stage | Base | Penalization |
|---|---|---|
| PDF Extract | 1.0 | Empty pages |
| Header Detect | 1.0 | No known headers found |
| Footer Detect | 1.0 | No known footers found |
| Table Detect | 1.0 | Many orphan lines outside tables |
| **Column Detect** | **1.0** | **Per UNKNOWN column** |
| **Column Map** | **1.0** | **No DATE or AMOUNT column found** |
| Row Extract | 1.0 | High discard rate |
| Row Merge | 1.0 | Orphan continuations |

### 10.2 Global

Weighted average. Column detection and mapping have 3x weight.

```python
def compute_global_confidence(results: list[StageResult]) -> float:
    weights = {
        "column_detector": 3.0,
        "column_mapper": 3.0,
        "table_detector": 2.0,
        "row_merger": 1.5,
    }
    ...
```

---

## 11. Tracing (Observability)

Internal-only. Never exposed to client.

```python
@dataclass(frozen=True)
class PipelineTracing:
    stages: tuple[StageResult, ...]
    global_confidence: float
    duration_ms: int
```

Each stage records:

| Stage | Metrics |
|---|---|
| `extractor` | page_count, chars_extracted |
| `header_detector` | headers_removed, total_blocks |
| `footer_detector` | footers_removed, total_blocks |
| `table_detector` | tables_found, lines_in_table, lines_outside_table |
| `column_detector` | columns_detected, unknown_columns, date_found, amount_found |
| `column_mapper` | mapped_columns, unmapped_columns |
| `row_extractor` | total_rows, valid_rows, discarded_rows |
| `row_merger` | merged_rows, orphan_continuations |
| `transaction_builder` | transactions_built, missing_amounts, missing_dates |

---

## 12. Robustness (Partial Failure)

| Scenario | Behavior |
|---|---|
| Column detection low confidence | Continue with UNKNOWN columns in metadata |
| No date column found | NormalizedRow.date = None (warning) |
| No amount column found | NormalizedRow.amount = None (warning) |
| Multi-line merge fails | Keep orphan rows as-is (warning) |
| No tables detected | Return empty Statement with warning |
| Page fails to extract | Skip page, continue with rest (warning) |

Never abort processing for recoverable failures.

---

## 13. What Changes vs What Stays

### Unchanged (observable behavior identical)

- `src/pipeline.py` — function signature and JSON output
- `src/main.py` — Lambda handler
- `src/__main__.py` — CLI entrypoint
- `src/models/statement.py` — `Amount`, `Transaction`, `Statement`
- `src/models/bank.py` — `Bank`, `BankId`
- `src/models/errors.py` — error hierarchy
- `src/normalizers/amount.py` — `normalize_amount()`
- `src/serializers/json.py` — `serialize_statement()`
- `src/validators/schema.py` — `validate_statement()`
- `tests/test_golden_macro.py` — must produce identical JSON
- `tests/fixtures/*/sample.json` — golden files remain unmodified

### Removed (replaced by universal engine)

- `src/extractors/pdf.py` → `src/processors/pdfplumber_impl.py`
- `src/cleaners/filters.py` → `src/stages/header_detector.py` + `footer_detector.py`
- `src/cleaners/normalizer.py` → migrated to `block_builder.py`
- `src/parsers/macro.py` — deleted
- `src/parsers/provincia.py` — deleted
- `src/parsers/nacion.py` — deleted
- `src/parsers/factory.py` — deleted
- `src/parsers/base.py` — deleted
- `src/parsers/__init__.py` — deleted
- `src/detectors/` → stays as separate concern

### Created

```
src/processors/
  __init__.py
  base.py                # PDFProcessor Protocol
  pdfplumber_impl.py     # pdfplumber implementation

src/stages/
  __init__.py
  block_builder.py       # Words → TextBlocks
  header_detector.py     # Header block removal
  footer_detector.py     # Footer block removal
  table_detector.py      # Table region detection
  column_detector.py     # Column clustering + classification
  column_mapper.py       # Columns → NormalizedRow
  row_extractor.py       # Words → Rows
  row_merger.py          # Multi-line merge
  transaction_builder.py # NormalizedRow → Transaction

src/models/
  document.py            # Document, Page, BBox, Word, TextBlock
  table.py               # Table, Column, Row, Cell, ColumnType
  canonical.py           # NormalizedRow
  trace.py               # StageResult, PipelineTracing, TracingLogger
```

---

## 14. Testing Strategy

| Test type | What | Covers |
|---|---|---|
| Golden tests | Macro, Provincia, Nación fixtures | Exact JSON match (existing, unchanged) |
| Column detection | Known column arrangements | Clustering + classification |
| Multi-line merge | Provincia-style + Nación-style | Row merging logic |
| Confidence scoring | Various quality inputs | Score reflects detection quality |
| PDFProcessor mock | Mock backend returns known words | Engine works with any backend |
| Empty/no-table PDF | No tabular structure | Graceful degradation |
| Partial failure | Missing columns, bad positions | Robustness |

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| pdfplumber positional extraction fails | `extract_words(x_tolerance=3, keep_blank_chars=True)` handles most digital PDFs. `extract_text()` fallback per page. |
| Column detection fails for unusual layouts | All UNKNOWN columns go to metadata. Transaction builder still gets description + whatever was detected. |
| Multi-line merge creates wrong descriptions | Conservative merging: require strong signal (missing date column) before merging. Orphan rows emit warnings. |
| Performance: positional extraction slower than pypdf | Process only pages with tabular structure. Lazy extraction per page. |
| Golden test Macro breaks | The engine must produce identical output. Column detection tuned specifically to match exact description formatting. |

---

## 16. Future-Proofing

- Adding a new bank = **zero engine changes**. The engine infers structure from the PDF.
- If auto-detection fails for a specific layout, a `LayoutHint` protocol can provide
  column position hints without modifying the engine. (To be implemented only if needed.)
- New PDF backends implement `PDFProcessor` protocol.
- Confidence scores enable automatic regression detection in CI.

---

## 17. Glossary

| Term | Definition |
|---|---|
| BBox | Bounding box (x0, x1, top, bottom) |
| TextBlock | Group of words on the same visual line |
| Continuation | Row without date-column content (multi-line description) |
| Canonical | Mapped to the standard model (date, description, amount, balance) |
| Tracing | Internal observability, not exposed to client |
