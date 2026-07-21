from __future__ import annotations

import hashlib


def calculate_sha256(pdf_bytes: bytes) -> str:
    return hashlib.sha256(pdf_bytes).hexdigest()
