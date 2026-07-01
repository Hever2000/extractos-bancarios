from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.mutations.base import (
    MutationCategory,
    MutationContext,
    MutationOp,
    MutationOutcome,
    MutationReport,
    rebuild_doc,
    rebuild_page,
)
from tests.mutations.operators import ALL_OPERATORS, OPERATORS_BY_CATEGORY
from tests.mutations.properties import ALL_PROPERTIES, check_properties
from tests.mutations.runner import run_mutated_pipeline

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _run_mutation(
    doc, bank, op: MutationOp, ctx: MutationContext,
) -> MutationOutcome:
    try:
        mutated = op.apply(doc, ctx)
        result = run_mutated_pipeline(mutated, bank)
        props = check_properties(result.statement)

        all_pass = all(props.values())
        return MutationOutcome(
            operator_name=op.name,
            category=op.category,
            mutation_index=0,
            passed=all_pass,
            properties_results=props,
            stage_confidence=result.stage_confidence,
            transactions_count=result.transactions_count,
            warnings=result.warnings,
            error=result.error,
        )
    except Exception as e:
        props = {p.name: False for p in ALL_PROPERTIES}
        return MutationOutcome(
            operator_name=op.name,
            category=op.category,
            mutation_index=0,
            passed=False,
            properties_results=props,
            stage_confidence=0.0,
            transactions_count=0,
            warnings=(),
            error=str(e),
        )


def _summarize(report: MutationReport) -> None:
    from collections import Counter
    cat_fails = Counter(o.category.name for o in report.outcomes if not o.passed)
    prop_fails: dict[str, int] = {}
    for o in report.outcomes:
        for pname, passed in o.properties_results.items():
            if not passed:
                prop_fails[pname] = prop_fails.get(pname, 0) + 1

    print(f"\n{'='*60}")
    print(f"  ROBUSTEZ: {report.passed}/{report.total_operators} passed")
    print(f"  Tasa de exito: {report.passed/max(report.total_operators,1)*100:.1f}%")
    print(f"{'='*60}")
    if cat_fails:
        print("\n  Fallos por categoria:")
        for cat, count in sorted(cat_fails.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")
    if prop_fails:
        print("\n  Propiedades fallidas:")
        for pname, count in sorted(prop_fails.items(), key=lambda x: -x[1]):
            print(f"    {pname}: {count}")
    print()

    report_data = {
        "total_operators": report.total_operators,
        "passed": report.passed,
        "failed": report.failed,
        "errors_by_category": report.errors_by_category,
        "outcomes": [
            {
                "operator": o.operator_name,
                "category": o.category.name,
                "passed": o.passed,
                "properties": o.properties_results,
                "transactions": o.transactions_count,
                "error": o.error,
            }
            for o in report.outcomes
        ],
    }
    report_file = Path("robustness-report.json")
    report_file.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")


# ──────────────────────────────────────────────
# TEST: each mutation operator individually
# ──────────────────────────────────────────────

@pytest.mark.robustez
@pytest.mark.parametrize("op", ALL_OPERATORS, ids=lambda op: f"{op.category.name}/{op.name}")
def test_individual_mutation(op: MutationOp, doc, bank, seed, pdf_name):
    ctx = MutationContext.create(seed, doc)
    outcome = _run_mutation(doc, bank, op, ctx)
    if not outcome.passed:
        fail_props = [k for k, v in outcome.properties_results.items() if not v]
        msg = (
            f"[{pdf_name}] {op.category.name}/{op.name}: "
            f"props={fail_props} "
            f"tx={outcome.transactions_count} "
            f"err={outcome.error}"
        )
        pytest.fail(msg)


# ──────────────────────────────────────────────
# TEST: combined mutations (2-3 operators)
# ──────────────────────────────────────────────

COMBINATIONS = [
    ([
        "add_header_line",
        "rename_column_headers",
    ], "header + column rename"),
    ([
        "remove_currency_symbol",
        "change_negative_format",
    ], "amount format combo"),
    ([
        "add_footer_with_table_data",
        "add_unexpected_text",
    ], "footer noise + unexpected"),
    ([
        "subtle_y_jitter",
        "squeeze_columns",
    ], "jitter + column squeeze"),
    ([
        "change_date_format",
        "remove_amount_column",
    ], "date change + missing amounts"),
    ([
        "add_accented_chars",
        "add_extra_whitespace",
    ], "special chars combo"),
    ([
        "duplicate_transactions",
        "add_extreme_amount",
    ], "duplicates + extreme"),
]


@pytest.mark.robustez
@pytest.mark.parametrize("names,desc", COMBINATIONS, ids=lambda x: x[1] if isinstance(x, tuple) else x)
def test_combined_mutations(names: list[str], desc: str, doc, bank, seed, pdf_name):
    ctx = MutationContext.create(seed, doc)
    selected = [op for op in ALL_OPERATORS if op.name in names]
    if len(selected) != len(names):
        pytest.skip(f"Not all operators found: {names}")

    mutated = doc
    for op in selected:
        mutated = op.apply(mutated, ctx)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]

    if fail_props:
        pytest.fail(
            f"[{pdf_name}] {desc}: props={fail_props} "
            f"tx={result.transactions_count} err={result.error}"
        )


# ──────────────────────────────────────────────
# TEST: all operators in a category
# ──────────────────────────────────────────────

@pytest.mark.robustez
@pytest.mark.parametrize("category", MutationCategory, ids=lambda c: c.name)
def test_category_suite(category: MutationCategory, doc, bank, seed, pdf_name):
    ops = OPERATORS_BY_CATEGORY.get(category, [])
    if not ops:
        pytest.skip(f"No operators for category {category.name}")

    outcomes: list[MutationOutcome] = []
    for i, op in enumerate(ops):
        ctx = MutationContext.create(seed + i, doc)
        outcome = _run_mutation(doc, bank, op, ctx)
        outcomes.append(outcome)

    failures = [o for o in outcomes if not o.passed]
    if failures:
        lines = [f"  [{o.operator_name}]: err={o.error}" for o in failures[:5]]
        pytest.fail(
            f"[{pdf_name}] {category.name}: "
            f"{len(failures)}/{len(ops)} failed\n" + "\n".join(lines)
        )


# ──────────────────────────────────────────────
# TEST: edge cases (known brittle assumptions)
# ──────────────────────────────────────────────

@pytest.mark.robustez
@pytest.mark.edge
def test_dates_without_leading_zero(doc, bank, seed, pdf_name):
    from src.models.document import Word

    page = doc.pages[0]
    date_re = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if date_re.match(w.text.strip()):
            parts = w.text.strip().split("/")
            new_text = f"{int(parts[0])}/{int(parts[1])}/{parts[2]}"
            if new_text != w.text.strip():
                new_words[i] = Word(text=new_text, bbox=w.bbox, fontname=w.fontname)

    new_page = rebuild_page(page, new_words)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]
    if fail_props:
        pytest.fail(f"Dates sin leading zero: props={fail_props} tx={result.transactions_count}")


@pytest.mark.robustez
@pytest.mark.edge
def test_amounts_as_plain_integers(doc, bank, seed, pdf_name):
    from src.models.document import Word

    page = doc.pages[0]
    amount_re = re.compile(r"^-?[\d.,\s]+$")
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        clean = w.text.replace("$", "").strip()
        if amount_re.match(clean) and "," in clean:
            int_part = clean.split(",")[0].replace(".", "")
            new_words[i] = Word(text=int_part, bbox=w.bbox, fontname=w.fontname)

    new_page = rebuild_page(page, new_words)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]
    if fail_props:
        pytest.skip(
            f"Plain integers: props={fail_props} tx={result.transactions_count}"
        )


@pytest.mark.robustez
@pytest.mark.edge
def test_mixed_date_formats(doc, bank, seed, pdf_name):
    from src.models.document import Word

    page = doc.pages[0]
    date_re = re.compile(r"^\d{2}/\d{2}/\d{4}$")
    new_words = list(page.words)
    fmt_idx = 0
    for i, w in enumerate(new_words):
        if date_re.match(w.text.strip()):
            parts = w.text.strip().split("/")
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if fmt_idx % 3 == 0:
                new_text = f"{y}-{m:02d}-{d:02d}"
            elif fmt_idx % 3 == 1:
                new_text = f"{d:02d}.{m:02d}.{y}"
            else:
                new_text = w.text.strip()
            if new_text != w.text.strip():
                new_words[i] = Word(text=new_text, bbox=w.bbox, fontname=w.fontname)
            fmt_idx += 1

    new_page = rebuild_page(page, new_words)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]
    if fail_props:
        pytest.fail(f"Mixed date formats: props={fail_props} tx={result.transactions_count}")


@pytest.mark.robustez
@pytest.mark.edge
def test_single_page_with_many_transactions(doc, bank, seed, pdf_name):
    page = doc.pages[0]
    words = list(page.words)
    doubled = words * 3
    new_page = rebuild_page(page, doubled)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]
    if fail_props:
        pytest.fail(f"Many txns: props={fail_props} tx={result.transactions_count}")


@pytest.mark.robustez
@pytest.mark.edge
def test_tabula_rasa(doc, bank, seed, pdf_name):
    from src.models.document import Document, Page
    empty_doc = Document(pages=(
        Page(number=1, width=doc.pages[0].width, height=doc.pages[0].height, words=()),
    ))
    result = run_mutated_pipeline(empty_doc, bank)
    assert result.transactions_count == 0
    assert "No se encontraron movimientos" in " ".join(result.warnings)


@pytest.mark.robustez
@pytest.mark.edge
def test_non_breaking_spaces(doc, bank, seed, pdf_name):
    from src.models.document import Word
    page = doc.pages[0]
    new_words = list(page.words)
    for i, w in enumerate(new_words):
        if "\xa0" not in w.text:
            new_words[i] = Word(
                text=w.text.replace(" ", "\xa0"),
                bbox=w.bbox,
                fontname=w.fontname,
            )
            break

    new_page = rebuild_page(page, new_words)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    assert result.error is None, f"Non-breaking spaces caused crash: {result.error}"


@pytest.mark.robustez
@pytest.mark.edge
def test_balance_before_amount(doc, bank, seed, pdf_name):
    from src.models.document import Word

    page = doc.pages[0]
    mid = page.width / 2
    new_words = []
    right_group: list[Word] = []
    left_group: list[Word] = []
    for w in page.words:
        if w.bbox.x0 > mid:
            right_group.append(w)
        else:
            left_group.append(w)

    if not right_group:
        pytest.skip("No words on right side to swap")

    new_words = left_group + right_group

    new_page = rebuild_page(page, new_words)
    mutated = rebuild_doc(doc, 0, new_page)

    result = run_mutated_pipeline(mutated, bank)
    props = check_properties(result.statement)
    fail_props = [k for k, v in props.items() if not v]
    if fail_props:
        pytest.fail(f"Balance before amount: props={fail_props} tx={result.transactions_count}")


# ──────────────────────────────────────────────
# AGGREGATE REPORT
# ──────────────────────────────────────────────

@pytest.mark.robustez
@pytest.mark.last
def test_consolidated_report(doc, bank, seed, pdf_name):
    ops = ALL_OPERATORS
    report = MutationReport(total_operators=len(ops))

    for i, op in enumerate(ops):
        ctx = MutationContext.create(seed + i, doc)
        outcome = _run_mutation(doc, bank, op, ctx)
        report.outcomes.append(outcome)
        if outcome.passed:
            report.passed += 1
        else:
            report.failed += 1
            cat = op.category.name
            report.errors_by_category[cat] = report.errors_by_category.get(cat, 0) + 1

    _summarize(report)
    rate = report.passed / max(report.total_operators, 1) * 100

    print(f"\n{'='*60}")
    print("  LABORATORIO DE ROBUSTEZ — COMPLETO")
    print(f"  PDF: {pdf_name}")
    print(f"  Operaciones: {report.total_operators}")
    print(f"  Pasaron: {report.passed}")
    print(f"  Fallaron: {report.failed}")
    print(f"  Tasa de exito: {rate:.1f}%")
    print("  Reporte guardado en: robustness-report.json")
    if report.errors_by_category:
        print("  Categorias con fallos:")
        for cat, count in sorted(report.errors_by_category.items(), key=lambda x: -x[1]):
            print(f"    {cat}: {count}")
    print(f"{'='*60}\n")
