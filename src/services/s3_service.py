from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3


@dataclass(frozen=True)
class S3UploadResult:
    bucket: str
    s3_key: str
    s3_url: str


def _sanitize_filename(filename: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._\-]", "_", filename)
    safe = safe.replace("..", "_")
    safe = safe.strip("._-")
    return safe if safe else "unnamed"


def _build_s3_url(bucket: str, s3_key: str, s3: Any) -> str:
    region = s3.meta.region_name
    domain = f"s3.{region}.amazonaws.com" if region else "s3.amazonaws.com"
    return f"https://{bucket}.{domain}/{s3_key}"


def upload_to_s3(pdf_bytes: bytes, filename: str) -> S3UploadResult:
    bucket = os.environ["S3_BUCKET"]
    now = datetime.now()
    safe_name = _sanitize_filename(filename)
    name_no_ext = safe_name.rsplit(".", 1)[0] if "." in safe_name else safe_name
    s3_key = f"extractos/{now.year}/{now.month:02d}/{name_no_ext}.pdf"

    s3 = boto3.client("s3")
    s3.put_object(Bucket=bucket, Key=s3_key, Body=pdf_bytes)

    s3_url = _build_s3_url(bucket, s3_key, s3)

    return S3UploadResult(bucket=bucket, s3_key=s3_key, s3_url=s3_url)
