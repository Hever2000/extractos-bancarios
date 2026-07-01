from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.detectors.bank import detect_bank
from src.models.bank import Bank, BankId
from src.models.document import Document
from src.processors.pdfplumber_impl import PdfplumberProcessor

SAMPLES_DIR = Path(__file__).parent.parent / "samples"

SAMPLE_PDFS: dict[str, str] = {
    "macro": str(SAMPLES_DIR / "macro.pdf"),
    "provincia": str(SAMPLES_DIR / "10005060869_20260202_extractos.pdf"),
}

SAMPLE_BANKS: dict[str, BankId] = {
    "macro": BankId.MACRO,
    "provincia": BankId.PROVINCIA,
}

_doc_cache: dict[str, Document] = {}


def load_document(pdf_name: str) -> Document:
    if pdf_name not in _doc_cache:
        path = SAMPLE_PDFS[pdf_name]
        proc = PdfplumberProcessor()
        with open(path, "rb") as f:
            data = f.read()
        _doc_cache[pdf_name] = proc.extract(data)
    return _doc_cache[pdf_name]


def get_bank(pdf_name: str) -> Bank:
    bank_id = SAMPLE_BANKS.get(pdf_name)
    if bank_id is None:
        path = SAMPLE_PDFS[pdf_name]
        with open(path, "rb") as f:
            raw_text = f.read().decode("latin-1", errors="replace")
        det = detect_bank(raw_text, pdf_name)
        assert det.bank is not None, f"No se pudo detectar banco para {pdf_name}"
        return det.bank

    from src.detectors.bank import BANKS
    for b in BANKS:
        if b.id == bank_id:
            return b
    msg = f"Bank {bank_id} not found in registry"
    raise ValueError(msg)


@pytest.fixture(scope="session")
def macro_doc() -> Document:
    return load_document("macro")


@pytest.fixture(scope="session")
def provincia_doc() -> Document:
    return load_document("provincia")


@pytest.fixture(scope="session")
def macro_bank() -> Bank:
    return get_bank("macro")


@pytest.fixture(scope="session")
def provincia_bank() -> Bank:
    return get_bank("provincia")


@pytest.fixture(params=["macro", "provincia"])
def pdf_name(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def doc(pdf_name: str) -> Document:
    return load_document(pdf_name)


@pytest.fixture
def bank(pdf_name: str) -> Bank:
    return get_bank(pdf_name)


@pytest.fixture
def seed() -> int:
    return 42


@pytest.fixture(scope="session")
def golden_macro() -> list[dict]:
    path = SAMPLES_DIR / "golden_macro.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["detalle"]


@pytest.fixture(scope="session")
def golden_provincia() -> list[dict]:
    path = SAMPLES_DIR / "golden_provincia_nacion.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["detalle"]
