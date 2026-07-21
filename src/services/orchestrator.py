from __future__ import annotations

import json
import logging
from typing import Any

from src.pipeline import process_statement
from src.services.hash_service import calculate_sha256
from src.services.response_builder import build_duplicate, build_error, build_success
from src.services.s3_service import upload_to_s3
from src.services.upload_repository import UploadRecord, exists_by_hash, save

log = logging.getLogger(__name__)


def process_upload(
    pdf_bytes: bytes,
    filename: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    pdf_hash = calculate_sha256(pdf_bytes)

    if exists_by_hash(pdf_hash):
        response = build_duplicate()
        print(json.dumps(response, ensure_ascii=False))
        return response

    try:
        s3_result = upload_to_s3(pdf_bytes, filename)
    except Exception:
        log.exception("Failed to upload to S3")
        response = build_error()
        print(json.dumps(response, ensure_ascii=False))
        return response

    try:
        json_str = process_statement(pdf_bytes, filename=filename, strict=strict)
    except Exception:
        log.exception("Pipeline failed")
        _save_error(pdf_hash, filename, s3_result)
        response = build_error()
        print(json.dumps(response, ensure_ascii=False))
        return response

    try:
        _save_ok(pdf_hash, filename, s3_result, json_str)
    except Exception:
        log.exception("Failed to save OK record, attempting ERROR fallback")
        try:
            _save_error(pdf_hash, filename, s3_result)
        except Exception:
            log.exception("Failed to save ERROR record as well")
        response = build_error()
        print(json.dumps(response, ensure_ascii=False))
        return response

    json_data = json.loads(json_str)
    response = build_success(json_data)

    print(json.dumps(response, ensure_ascii=False))
    print(json_str)

    return response


def _save_error(
    pdf_hash: str,
    filename: str,
    s3_result: Any,
) -> None:
    record = UploadRecord(
        hash_pdf=pdf_hash,
        nombre_original=filename,
        bucket=s3_result.bucket,
        s3_key=s3_result.s3_key,
        s3_url=s3_result.s3_url,
        json_resultado=None,
        estado="ERROR",
    )
    save(record)


def _save_ok(
    pdf_hash: str,
    filename: str,
    s3_result: Any,
    json_str: str,
) -> None:
    record = UploadRecord(
        hash_pdf=pdf_hash,
        nombre_original=filename,
        bucket=s3_result.bucket,
        s3_key=s3_result.s3_key,
        s3_url=s3_result.s3_url,
        json_resultado=json_str,
        estado="OK",
    )
    save(record)
