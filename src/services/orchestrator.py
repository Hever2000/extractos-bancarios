from __future__ import annotations

import json
import logging
from typing import Any

from src.pipeline import process_statement
from src.services.hash_service import calculate_sha256
from src.services.response_builder import build_duplicate, build_error
from src.services.s3_service import S3UploadResult, upload_to_s3
from src.services.upload_repository import UploadRecord, exists_by_hash, save

log = logging.getLogger(__name__)


def process_upload(
    pdf_bytes: bytes,
    filename: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    pdf_hash = calculate_sha256(pdf_bytes)

    if exists_by_hash(pdf_hash):
        log.info("duplicate_detected", extra={"hash": pdf_hash})
        return build_duplicate()

    s3_result: S3UploadResult | None = None
    try:
        s3_result = upload_to_s3(pdf_bytes, filename)
    except Exception:
        log.warning("S3 upload failed, continuing without S3 storage")

    try:
        json_str = process_statement(pdf_bytes, filename=filename, strict=strict)
    except Exception:
        log.exception("Pipeline failed")
        _save_error(pdf_hash, filename, s3_result)
        return build_error()

    try:
        _save_ok(pdf_hash, filename, s3_result, json_str)
    except Exception:
        log.exception("Failed to save OK record, attempting ERROR fallback")
        try:
            _save_error(pdf_hash, filename, s3_result)
        except Exception:
            log.exception("Failed to save ERROR record as well")
        return build_error()

    json_data: dict[str, Any] = json.loads(json_str)

    log.info(
        "upload_success",
        extra={"hash": pdf_hash, "filename": filename, "s3_stored": s3_result is not None},
    )

    return json_data


def _save_error(
    pdf_hash: str,
    filename: str,
    s3_result: S3UploadResult | None,
) -> None:
    record = UploadRecord(
        hash_pdf=pdf_hash,
        nombre_original=filename,
        bucket=s3_result.bucket if s3_result else None,
        s3_key=s3_result.s3_key if s3_result else None,
        s3_url=s3_result.s3_url if s3_result else None,
        json_resultado=None,
        estado="ERROR",
    )
    save(record)


def _save_ok(
    pdf_hash: str,
    filename: str,
    s3_result: S3UploadResult | None,
    json_str: str,
) -> None:
    record = UploadRecord(
        hash_pdf=pdf_hash,
        nombre_original=filename,
        bucket=s3_result.bucket if s3_result else None,
        s3_key=s3_result.s3_key if s3_result else None,
        s3_url=s3_result.s3_url if s3_result else None,
        json_resultado=json_str,
        estado="OK",
    )
    save(record)
