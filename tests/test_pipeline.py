import json
from pathlib import Path

import pytest

from src.models.errors import ExtractError
from src.pipeline import process_statement

SAMPLES = Path(__file__).resolve().parent / "samples"

GOLDEN_CASES = [
    ("macro.pdf", "golden_macro.json"),
    ("10005060869_20260202_extractos.pdf", "golden_provincia_nacion.json"),
    ("09-SEPTIEMBRE 2019 CTA 54 pdf.pdf", "golden_nacion.json"),
]


def test_process_invalid_pdf_raises():
    with pytest.raises(Exception, match="does not appear to be a valid PDF"):
        process_statement(b"hello world this is not a pdf")


def test_process_empty_pdf_raises():
    with pytest.raises(Exception, match="does not appear to be a valid PDF"):
        process_statement(b"")


def test_process_oversized_pdf_raises():
    big = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(ExtractError, match="exceeds maximum size"):
        process_statement(big)


@pytest.mark.parametrize("pdf_name,golden_name", GOLDEN_CASES)
def test_golden(pdf_name: str, golden_name: str) -> None:
    pdf_path = SAMPLES / pdf_name
    golden_path = SAMPLES / golden_name

    if not golden_path.exists():
        result = process_statement(pdf_path.read_bytes())
        golden_path.write_text(result, encoding="utf-8")
        pytest.skip(f"Created golden file {golden_name}; verify before running again")

    result = json.loads(process_statement(pdf_path.read_bytes()))
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert result == expected, f"Output mismatch for {pdf_name}"
