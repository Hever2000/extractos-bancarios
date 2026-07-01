from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from src.pipeline import process_statement

log = logging.getLogger(__name__)


def _get_pdf_bytes(event: dict[str, Any]) -> bytes | None:
    if "body" in event:
        raw = event["body"]
        is_base64 = event.get("isBase64Encoded", False)
        if is_base64:
            return base64.b64decode(raw)
        if isinstance(raw, str):
            return raw.encode("latin-1")
        if isinstance(raw, bytes):
            return raw
        return None

    if "Records" in event:
        record = event["Records"][0]
        if "s3" in record:
            raise NotImplementedError("S3 trigger not yet implemented")

    return None


def _get_filename(event: dict[str, Any]) -> str:
    if "body" in event:
        headers = event.get("headers", {})
        cd = headers.get("Content-Disposition") or headers.get("content-disposition") or ""
        if "filename=" in cd:
            return cd.split("filename=")[-1].strip('" ')
    if "Records" in event:
        key = event["Records"][0].get("s3", {}).get("object", {}).get("key", "")
        return key.split("/")[-1] if key else ""
    return ""


def handler(event: dict[str, Any], context: object | None = None) -> dict[str, Any]:
    try:
        pdf_bytes = _get_pdf_bytes(event)
        if pdf_bytes is None:
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {"error": "Unsupported event source. Provide PDF in body or S3 event."}
                ),
                "headers": {"Content-Type": "application/json"},
            }

        filename = _get_filename(event)
        strict = os.getenv("PIPELINE_STRICT", "false").lower() == "true"

        result = process_statement(pdf_bytes, filename=filename, strict=strict)

        return {
            "statusCode": 200,
            "body": result,
            "headers": {"Content-Type": "application/json"},
        }

    except NotImplementedError:
        raise
    except Exception:
        log.exception("Pipeline failed")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal_error"}),
            "headers": {"Content-Type": "application/json"},
        }
