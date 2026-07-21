from __future__ import annotations

from src.services.hash_service import calculate_sha256


def test_returns_hex_string() -> None:
    result = calculate_sha256(b"test data")
    assert isinstance(result, str)
    assert len(result) == 64


def test_deterministic() -> None:
    assert calculate_sha256(b"hello") == calculate_sha256(b"hello")


def test_different_inputs_different_hashes() -> None:
    assert calculate_sha256(b"data1") != calculate_sha256(b"data2")


def test_empty_bytes() -> None:
    result = calculate_sha256(b"")
    assert len(result) == 64
    assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_known_value() -> None:
    assert calculate_sha256(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
