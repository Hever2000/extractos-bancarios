from __future__ import annotations

import json
import logging
import os
from typing import cast

log = logging.getLogger(__name__)


def _fetch_secret(secret_arn: str) -> dict[str, str] | None:
    try:
        import boto3

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_arn)
        secret_str = response.get("SecretString")
        if secret_str:
            return cast(dict[str, str], json.loads(secret_str))
    except Exception:
        log.exception("Failed to fetch secret from AWS Secrets Manager")
    return None


def get_db_config() -> dict[str, str]:
    secret_arn = os.getenv("DB_SECRET_ARN")
    if secret_arn:
        secret = _fetch_secret(secret_arn)
        if secret is not None:
            return {
                "host": secret.get("DB_HOST", ""),
                "port": secret.get("DB_PORT", "1433"),
                "database": secret.get("DB_NAME", ""),
                "user": secret.get("DB_USER", ""),
                "password": secret.get("DB_PASSWORD", ""),
                "table": secret.get("DB_TABLE", "impo_uni_archivos_upload"),
            }

    return {
        "host": os.environ["DB_HOST"],
        "port": os.getenv("DB_PORT", "1433"),
        "database": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
        "table": os.getenv("DB_TABLE", "impo_uni_archivos_upload"),
    }
