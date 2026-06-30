import pytest

from src.pipeline import process_statement


def test_process_invalid_pdf_raises():
    with pytest.raises(Exception, match="does not appear to be a valid PDF"):
        process_statement(b"hello world this is not a pdf")


def test_process_empty_pdf_raises():
    with pytest.raises(Exception, match="does not appear to be a valid PDF"):
        process_statement(b"")
