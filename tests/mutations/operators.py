from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from src.models.document import BBox, Document, Word
from tests.mutations.base import (
    MutationCategory,
    MutationContext,
    MutationOp,
    pick_page,
    rand_float,
    rebuild_doc,
    rebuild_page,
)


@dataclass(frozen=True)
class _Mutator:
    name: str
    category: MutationCategory
    description: str
    probability: float
    fn: Callable[[Document, MutationContext], Document]
    injection_point: str = "pre_build"

    def build(self) -> MutationOp:
        return MutationOp(
            name=self.name,
            category=self.category,
            description=self.description,
            probability=self.probability,
            apply=self.fn,
            injection_point=self.injection_point,
        )


def _build_ops(mutators: list[_Mutator]) -> list[MutationOp]:
    return [m.build() for m in mutators]


# ═══════════════════════════════════════════════
# 1. HEADERS
# ═══════════════════════════════════════════════

def _add_header_line(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    top_y = 10.0 + rand_float(ctx.rng, 0, 30)
    texts = [
        "RESUMEN DE CUENTA",
        "Estado de Cuenta",
        "Movimientos del Mes",
        "DETALLE DE OPERACIONES",
        "EXTRACTO DE MOVIMIENTOS",
        "INFORME DE TRANSACCIONES",
    ]
    t = ctx.rng.choice(texts)
    fake = Word(
        text=t,
        bbox=BBox(x0=50.0, x1=50.0 + len(t) * 6, top=top_y, bottom=top_y + 12),
    )
    new_words = (fake,) + page.words
    return rebuild_doc(doc, page_idx, rebuild_page(page, list(new_words)))


def _add_subheader_line(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    top_y = 25.0 + rand_float(ctx.rng, 0, 20)
    texts = [
        "Cuenta Corriente Nro: 12345/6",
        "Caja de Ahorro Nro: 67890/1",
        "Cliente: EMPRESA S.A.",
        "CUIT: 30-12345678-9",
        "Periodo: Enero 2026",
        "Tipo de Moneda: Pesos Argentinos",
    ]
    t = ctx.rng.choice(texts)
    fake = Word(
        text=t,
        bbox=BBox(x0=50.0, x1=50.0 + len(t) * 5, top=top_y, bottom=top_y + 10),
    )
    new_words = (fake,) + page.words
    return rebuild_doc(doc, page_idx, rebuild_page(page, list(new_words)))


def _add_line_with_date_like_header(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    top_y = 15.0
    t = f"Extraido al {ctx.rng.randint(1,31):02d}/{ctx.rng.randint(1,12):02d}/2026"
    fake = Word(
        text=t,
        bbox=BBox(x0=200.0, x1=200.0 + len(t) * 5, top=top_y, bottom=top_y + 10),
    )
    new_words = (fake,) + page.words
    return rebuild_doc(doc, page_idx, rebuild_page(page, list(new_words)))


HEADER_OPS = _build_ops([
    _Mutator("add_header_line", MutationCategory.HEADERS,
             "Agrega linea de encabezado desconocida arriba de la tabla", 0.8,
             _add_header_line),
    _Mutator("add_subheader_line", MutationCategory.HEADERS,
             "Agrega info de cuenta/cliente arriba de la tabla", 0.7,
             _add_subheader_line),
    _Mutator("add_date_like_header", MutationCategory.HEADERS,
             "Agrega encabezado con patron de fecha (puede confundir al detector)", 0.5,
             _add_line_with_date_like_header),
])


# ═══════════════════════════════════════════════
# 2. FOOTERS
# ═══════════════════════════════════════════════

def _add_footer_line(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    page_height = page.height
    bottom_y = page_height - 30.0 + rand_float(ctx.rng, -10, 10)
    texts = [
        f"Pagina {page_idx + 1} de {len(doc.pages)}",
        "Usuario: ADMINISTRADOR",
        "Impreso: 01/01/2026 15:30 hs",
        "CUIT: 30-12345678-9",
        "Email: notificaciones@banco.com.ar",
        "Solicite su comprobante en www.banco.com",
        "Codigo de verificacion: ABC123DEF456",
    ]
    t = ctx.rng.choice(texts)
    fake = Word(
        text=t,
        bbox=BBox(x0=100.0, x1=100.0 + len(t) * 5, top=bottom_y, bottom=bottom_y + 10),
    )
    new_words = tuple(list(page.words) + [fake])
    return rebuild_doc(doc, page_idx, rebuild_page(page, list(new_words)))


def _add_footer_with_table_data(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    page_height = page.height
    bottom_y = page_height - 50.0
    d = ctx.rng.randint(1, 28)
    m = ctx.rng.randint(1, 12)
    amounts = [f"${ctx.rng.randint(100,9999):,}.{ctx.rng.randint(0,99):02d}" for _ in range(3)]
    t = f"{d:02d}/{m:02d}/2026 TOTAL {amounts[0]} {amounts[1]} {amounts[2]}"
    fake = Word(
        text=t,
        bbox=BBox(x0=50.0, x1=50.0 + len(t) * 5, top=bottom_y, bottom=bottom_y + 10),
    )
    new_words = tuple(list(page.words) + [fake])
    return rebuild_doc(doc, page_idx, rebuild_page(page, list(new_words)))


FOOTER_OPS = _build_ops([
    _Mutator("add_footer_line", MutationCategory.FOOTERS,
             "Agrega footer generico debajo de la tabla", 0.8, _add_footer_line),
    _Mutator("add_footer_with_table_data", MutationCategory.FOOTERS,
             "Agrega footer con patrones de tabla (fecha+importes) que puede confundir", 0.4,
             _add_footer_with_table_data),
])


# ═══════════════════════════════════════════════
# 3. COLUMN NAMES
# ═══════════════════════════════════════════════

COLUMN_HEADER_SWAPS: dict[str, list[str]] = {
    "Fecha": ["F. Valor", "Fch.", "Date", "Fec.", "Fecha Operacion"],
    "Descripcion": ["Detalle", "Concepto", "Leyenda", "Operacion", "Movimiento"],
    "Importe": ["Debe", "Haber", "Monto", "Valor", "Credito", "Debito"],
    "Saldo": ["Saldo Final", "Disponible", "Saldo Parcial"],
}


def _rename_column_word(word: Word, ctx: MutationContext) -> Word | None:
    for original, alternatives in COLUMN_HEADER_SWAPS.items():
        if original.lower() in word.text.lower():
            new_text = ctx.rng.choice(alternatives)
            return Word(
                text=new_text,
                bbox=word.bbox,
                fontname=word.fontname,
            )
    return None


def _rename_headers(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    changes = 0
    for i, w in enumerate(new_words):
        renamed = _rename_column_word(w, ctx)
        if renamed is not None:
            new_words[i] = renamed
            changes += 1
            if changes >= 2:
                break
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


COLUMN_NAME_OPS = _build_ops([
    _Mutator("rename_column_headers", MutationCategory.COLUMN_NAMES,
             "Renombra encabezados de columnas con sinonimos reales", 0.9,
             _rename_headers),
])


# ═══════════════════════════════════════════════
# 4. COLUMN ORDER — swap or reorder lanes
# ═══════════════════════════════════════════════

def _swap_date_description(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    w50 = page.width / 2
    for i, w in enumerate(words):
        shift = w50 if w.bbox.x0 < w50 else -w50
        words[i] = Word(
            text=w.text,
            bbox=BBox(x0=w.bbox.x0 + shift, x1=w.bbox.x1 + shift,
                      top=w.bbox.top, bottom=w.bbox.bottom),
            fontname=w.fontname,
        )
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


COLUMN_ORDER_OPS = _build_ops([
    _Mutator("swap_date_description", MutationCategory.COLUMN_ORDER,
             "Intercambia posiciones de columna fecha y descripcion", 0.3,
             _swap_date_description),
])


# ═══════════════════════════════════════════════
# 5. EXTRA COLUMNS
# ═══════════════════════════════════════════════

def _add_reference_column(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    if len(words) < 5:
        return doc
    anchor = words[len(words) // 2]
    refs = [f"NRO{ctx.rng.randint(100000,999999)}",
            f"LOTE{ctx.rng.randint(100,999)}",
            f"COMP{ctx.rng.randint(10000000,99999999)}"]
    ref = ctx.rng.choice(refs)
    fake = Word(
        text=ref,
        bbox=BBox(x0=anchor.bbox.x0 - 60, x1=anchor.bbox.x0 - 10,
                  top=anchor.bbox.top, bottom=anchor.bbox.bottom),
    )
    words.insert(0, fake)
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


EXTRA_COL_OPS = _build_ops([
    _Mutator("add_reference_column", MutationCategory.EXTRA_COLUMNS,
             "Agrega columna extra de referencia/comprobante", 0.6,
             _add_reference_column),
])


# ═══════════════════════════════════════════════
# 6. MISSING COLUMNS
# ═══════════════════════════════════════════════

_AMOUNT_PATTERN = re.compile(
    r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$"
    r"|^-?\d+\.\d{2}$"
    r"|^\$\s*-?[\d.,]+$"
    r"|^-?[\d.,]+$"
)

_DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")


def _remove_column(doc: Document, remove_type: str) -> Document:
    page_idx = 0
    page = doc.pages[page_idx]

    if remove_type == "amounts":
        kept: list[Word] = []
        for w in page.words:
            clean = w.text.replace("$", "").strip()
            if _DATE_PATTERN.match(w.text.strip()):
                kept.append(w)
            elif _AMOUNT_PATTERN.match(clean):
                pass
            else:
                kept.append(w)
        new_words = kept
    elif remove_type == "balances":
        new_words = [w for w in page.words
                     if not re.search(r"^\d+\.?\d*,\d{2}$", w.text)]
    elif remove_type == "dates":
        new_words = [w for w in page.words
                     if not re.search(r"^\d{2}/\d{2}/\d{4}$", w.text)]
    else:
        return doc
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


MISSING_COL_OPS = _build_ops([
    _Mutator("remove_amount_column", MutationCategory.MISSING_COLUMNS,
             "Elimina palabras que parecen importes (columna faltante)", 0.4,
             lambda d, c: _remove_column(d, "amounts")),
    _Mutator("remove_balance_column", MutationCategory.MISSING_COLUMNS,
             "Elimina palabras que parecen saldos (columna faltante)", 0.4,
             lambda d, c: _remove_column(d, "balances")),
    _Mutator("remove_date_column", MutationCategory.MISSING_COLUMNS,
             "Elimina fechas del documento (sin columna de fecha)", 0.2,
             lambda d, c: _remove_column(d, "dates")),
])


# ═══════════════════════════════════════════════
# 7. HORIZONTAL ALIGNMENT
# ═══════════════════════════════════════════════

def _shift_amounts_right(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if re.search(r"[\d.,]{4,}", w.text) and not re.search(r"^\d{2}/\d{2}/\d{4}$", w.text):
            shift = rand_float(ctx.rng, 5, 20)
            new_words[i] = Word(
                text=w.text,
                bbox=BBox(x0=w.bbox.x0 + shift, x1=w.bbox.x1 + shift,
                          top=w.bbox.top, bottom=w.bbox.bottom),
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


ALIGNMENT_H_OPS = _build_ops([
    _Mutator("shift_amounts_right", MutationCategory.ALIGNMENT_H,
             "Desplaza importes a la derecha desalineandolos", 0.5,
             _shift_amounts_right),
])


# ═══════════════════════════════════════════════
# 8. VERTICAL ALIGNMENT (y-jitter)
# ═══════════════════════════════════════════════

def _apply_y_jitter(doc: Document, ctx: MutationContext, max_jitter: float) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = []
    for w in page.words:
        jitter = rand_float(ctx.rng, -max_jitter, max_jitter)
        new_words.append(Word(
            text=w.text,
            bbox=BBox(x0=w.bbox.x0, x1=w.bbox.x1,
                      top=w.bbox.top + jitter, bottom=w.bbox.bottom + jitter),
            fontname=w.fontname,
        ))
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


ALIGNMENT_V_OPS = _build_ops([
    _Mutator("subtle_y_jitter", MutationCategory.ALIGNMENT_V,
             "Jitter vertical sutil 0-2px en posiciones de palabras", 0.7,
             lambda d, c: _apply_y_jitter(d, c, 2.0)),
    _Mutator("aggressive_y_jitter", MutationCategory.ALIGNMENT_V,
             "Jitter vertical agresivo 3-6px (rompe agrupacion por lineas)", 0.4,
             lambda d, c: _apply_y_jitter(d, c, 6.0)),
])


# ═══════════════════════════════════════════════
# 9. SPACING (column gap manipulation)
# ═══════════════════════════════════════════════

def _squeeze_columns(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = []
    mid = page.width / 2
    squeeze = rand_float(ctx.rng, 3, 6)
    for w in page.words:
        if w.bbox.x0 > mid:
            new_words.append(Word(
                text=w.text,
                bbox=BBox(x0=w.bbox.x0 - squeeze, x1=w.bbox.x1 - squeeze,
                          top=w.bbox.top, bottom=w.bbox.bottom),
                fontname=w.fontname,
            ))
        else:
            new_words.append(w)
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


def _expand_columns(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = []
    mid = page.width / 2
    expand = rand_float(ctx.rng, 3, 8)
    for w in page.words:
        if w.bbox.x0 > mid:
            new_words.append(Word(
                text=w.text,
                bbox=BBox(x0=w.bbox.x0 + expand, x1=w.bbox.x1 + expand,
                          top=w.bbox.top, bottom=w.bbox.bottom),
                fontname=w.fontname,
            ))
        else:
            new_words.append(w)
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


SPACING_OPS = _build_ops([
    _Mutator("squeeze_columns", MutationCategory.SPACING,
             "Acerca columnas (puede fusionar lanes si gap < 8px)", 0.5,
             _squeeze_columns),
    _Mutator("expand_columns", MutationCategory.SPACING,
             "Separa columnas (puede crear lanes extras)", 0.5,
             _expand_columns),
])


# ═══════════════════════════════════════════════
# 10. DATE FORMATS
# ═══════════════════════════════════════════════

_MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
           "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

DATE_FORMATS: list[tuple[str, Callable[[int, int, int], str]]] = [
    ("DD-MM-YYYY", lambda d, m, y: f"{d:02d}-{m:02d}-{y}"),
    ("YYYY-MM-DD", lambda d, m, y: f"{y}-{m:02d}-{d:02d}"),
    ("DD/MM/YY", lambda d, m, y: f"{d:02d}/{m:02d}/{y % 100:02d}"),
    ("DD.MM.YYYY", lambda d, m, y: f"{d:02d}.{m:02d}.{y}"),
    ("YYYY/MM/DD", lambda d, m, y: f"{y}/{m:02d}/{d:02d}"),
    ("DD-Mon-YYYY", lambda d, m, y: f"{d:02d}-{_MONTHS[m-1]}-{y}"),
]


def _change_date_format(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    fmt_name, fmt_fn = ctx.rng.choice(DATE_FORMATS)
    date_re = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        m = date_re.match(w.text.strip())
        if m:
            parts = w.text.strip().split("/")
            d, mo, y = int(parts[0]), int(parts[1]), int(parts[2])
            new_text = fmt_fn(d, mo, y)
            new_words[i] = Word(
                text=new_text,
                bbox=w.bbox,
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


DATE_OPS = _build_ops([
    _Mutator("change_date_format", MutationCategory.DATES,
             "Cambia formato DD/MM/YYYY a formatos alternativos reales", 0.9,
             _change_date_format),
])


# ═══════════════════════════════════════════════
# 11. AMOUNT FORMATS
# ═══════════════════════════════════════════════

def _remove_currency_symbol(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        stripped = w.text.strip()
        if stripped.startswith("$"):
            new_words[i] = Word(
                text=stripped.replace("$", "").strip(),
                bbox=w.bbox,
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


def _add_currency_code(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    codes = ["ARS ", "U$S ", "USD ", "$ "]
    code = ctx.rng.choice(codes)
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if re.search(r"^\d{1,3}(?:\.\d{3})*,\d{2}$", w.text.strip()):
            new_words[i] = Word(
                text=code + w.text.strip(),
                bbox=w.bbox,
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


def _remove_thousands_separator(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        clean = w.text.replace(".", "")
        if clean != w.text and re.search(r"^\d+,\d{2}$", clean):
            new_words[i] = Word(
                text=clean,
                bbox=w.bbox,
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


def _change_negative_format(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        t = w.text.strip()
        if t.startswith("-") and re.search(r"\d", t):
            new_text = t[1:]
            if ctx.rng.random() < 0.5:
                new_text = f"({new_text})"
            else:
                new_text = f"{new_text}-"
            new_words[i] = Word(
                text=new_text, bbox=w.bbox, fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


AMOUNT_OPS = _build_ops([
    _Mutator("remove_currency_symbol", MutationCategory.AMOUNTS,
             "Saca simbolo $ de los importes", 0.7, _remove_currency_symbol),
    _Mutator("add_currency_code", MutationCategory.AMOUNTS,
             "Agrega codigo de moneda (ARS, U$S) antes del importe", 0.5,
             _add_currency_code),
    _Mutator("remove_thousands_separator", MutationCategory.AMOUNTS,
             "Elimina separador de miles (.) de los importes", 0.4,
             _remove_thousands_separator),
    _Mutator("change_negative_format", MutationCategory.AMOUNTS,
             "Cambia formato de negativos: -X → (X) o X-", 0.6,
             _change_negative_format),
])


# ═══════════════════════════════════════════════
# 12. SPECIAL CHARS
# ═══════════════════════════════════════════════

ACCENT_MAP = {
    "a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú",
    "A": "Á", "E": "É", "I": "Í", "O": "Ó", "U": "Ú",
    "n": "ñ", "N": "Ñ",
}


def _add_accented_chars(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if len(w.text) > 3 and ctx.rng.random() < 0.3:
            new_text = "".join(
                ACCENT_MAP.get(c, c) if ctx.rng.random() < 0.5 else c
                for c in w.text
            )
            if new_text != w.text:
                new_words[i] = Word(
                    text=new_text, bbox=w.bbox, fontname=w.fontname,
                )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


def _add_extra_whitespace(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if ctx.rng.random() < 0.2:
            new_words[i] = Word(
                text=w.text + " ",
                bbox=w.bbox,
                fontname=w.fontname,
            )
    return rebuild_doc(doc, page_idx, rebuild_page(page, new_words))


SPECIAL_CHARS_OPS = _build_ops([
    _Mutator("add_accented_chars", MutationCategory.SPECIAL_CHARS,
             "Agrega acentos y enies a descripciones", 0.8, _add_accented_chars),
    _Mutator("add_extra_whitespace", MutationCategory.SPECIAL_CHARS,
             "Agrega espacios extras en palabras", 0.5, _add_extra_whitespace),
])


# ═══════════════════════════════════════════════
# 13. EMPTY ROWS
# ═══════════════════════════════════════════════

def _add_empty_rows(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    if len(words) < 10:
        return doc
    insert_at = ctx.rng.randint(len(words) // 3, 2 * len(words) // 3)
    spacer = Word(
        text="",
        bbox=BBox(x0=50, x1=550, top=words[insert_at].bbox.top + 1,
                  bottom=words[insert_at].bbox.bottom + 5),
    )
    words.insert(insert_at, spacer)
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


EMPTY_ROWS_OPS = _build_ops([
    _Mutator("add_empty_row", MutationCategory.EMPTY_ROWS,
             "Inserta fila vacia en medio de la tabla", 0.5, _add_empty_rows),
])


# ═══════════════════════════════════════════════
# 14. DUPLICATE ROWS
# ═══════════════════════════════════════════════

def _duplicate_transactions(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    if len(words) < 10:
        return doc
    chunk_size = ctx.rng.randint(3, 6)
    start = ctx.rng.randint(0, max(0, len(words) - chunk_size * 2))
    dup = words[start:start + chunk_size]
    insert_at = ctx.rng.randint(0, len(words))
    words[insert_at:insert_at] = dup
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


DUPLICATE_ROWS_OPS = _build_ops([
    _Mutator("duplicate_transactions", MutationCategory.DUPLICATE_ROWS,
             "Duplica un grupo de transacciones (genera duplicados exactos)", 0.4,
             _duplicate_transactions),
])


# ═══════════════════════════════════════════════
# 15. EXTREME VALUES
# ═══════════════════════════════════════════════

def _add_extreme_amount(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    if not words:
        return doc
    anchor = words[len(words) // 2]
    extreme_value = ctx.rng.choice([
        f"${ctx.rng.randint(10_000_000, 999_999_999):,}.00",
        "$0.01",
        "$-0.01",
        "$0,00",
        f"${ctx.rng.randint(1, 99):,}.{ctx.rng.randint(0, 99):02d}",
    ])
    extreme = Word(
        text=extreme_value,
        bbox=BBox(x0=anchor.bbox.x0, x1=anchor.bbox.x1,
                  top=anchor.bbox.top - 12, bottom=anchor.bbox.bottom - 12),
    )
    words.append(extreme)
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


EXTREME_OPS = _build_ops([
    _Mutator("add_extreme_amount", MutationCategory.EXTREME_VALUES,
             "Agrega transaccion con valores extremos (muy grandes, muy chicos, cero)", 0.5,
             _add_extreme_amount),
])


# ═══════════════════════════════════════════════
# 16. UNEXPECTED TEXT
# ═══════════════════════════════════════════════

UNEXPECTED_TEXTS = [
    "SALDO ANTERIOR $1.234,56",
    "SUBTOTAL $5.678,90",
    "TOTAL DEBITOS $10.000,00",
    "TOTAL CREDITOS $15.000,00",
    "SALDO A LA FECHA $20.000,00",
    "*** FIN DEL EXTRACTO ***",
    "NO REGISTRA MOVIMIENTOS",
    "CONTINUA EN PROXIMA PAGINA",
    "RESUMEN DE IMPUESTOS: $500,00",
    "IIBB PERCEPCIONES $200,00",
]


def _add_unexpected_text(doc: Document, ctx: MutationContext) -> Document:
    page_idx = pick_page(doc, ctx.rng)
    page = doc.pages[page_idx]
    words = list(page.words)
    if not words:
        return doc
    anchor = words[len(words) // 2]
    txt = ctx.rng.choice(UNEXPECTED_TEXTS)
    fake = Word(
        text=txt,
        bbox=BBox(x0=anchor.bbox.x0, x1=anchor.bbox.x0 + len(txt) * 5,
                  top=anchor.bbox.top - 14, bottom=anchor.bbox.bottom - 14),
    )
    words.append(fake)
    return rebuild_doc(doc, page_idx, rebuild_page(page, words))


UNEXPECTED_TEXT_OPS = _build_ops([
    _Mutator("add_unexpected_text", MutationCategory.UNEXPECTED_TEXT,
             "Agrega textos inesperados dentro de la tabla (total, subtotal, resumen)", 0.6,
             _add_unexpected_text),
])


# ═══════════════════════════════════════════════
# AGGREGATE: ALL OPERATORS
# ═══════════════════════════════════════════════

ALL_OPERATORS: list[MutationOp] = (
    HEADER_OPS
    + FOOTER_OPS
    + COLUMN_NAME_OPS
    + COLUMN_ORDER_OPS
    + EXTRA_COL_OPS
    + MISSING_COL_OPS
    + ALIGNMENT_H_OPS
    + ALIGNMENT_V_OPS
    + SPACING_OPS
    + DATE_OPS
    + AMOUNT_OPS
    + SPECIAL_CHARS_OPS
    + EMPTY_ROWS_OPS
    + DUPLICATE_ROWS_OPS
    + EXTREME_OPS
    + UNEXPECTED_TEXT_OPS
)

OPERATORS_BY_CATEGORY: dict[MutationCategory, list[MutationOp]] = {}
for op in ALL_OPERATORS:
    OPERATORS_BY_CATEGORY.setdefault(op.category, []).append(op)
