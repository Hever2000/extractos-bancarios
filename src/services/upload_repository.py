from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pymssql

from src.services.secret_service import get_db_config

_VALID_TABLE_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class UploadRecord:
    hash_pdf: str
    nombre_original: str
    bucket: str | None = None
    s3_key: str | None = None
    s3_url: str | None = None
    json_resultado: str | None = None
    estado: str = "OK"


@contextmanager
def _connection() -> Generator[Any, None, None]:
    cfg = get_db_config()
    conn = pymssql.connect(
        server=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )
    try:
        yield conn
    finally:
        conn.close()


def _table_name() -> str:
    name = get_db_config()["table"]
    if not _VALID_TABLE_RE.match(name):
        raise ValueError(f"Invalid table name: {name!r}")
    return name


def exists_by_hash(hash_pdf: str) -> bool:
    with _connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(1) FROM {_table_name()} WHERE hash_pdf = %s",
                (hash_pdf,),
            )
            row = cursor.fetchone()
            if row is None:
                return False
            count: int = row[0]
            return count > 0


def save(record: UploadRecord) -> None:
    with _connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""INSERT INTO {_table_name()}
                    (hash_pdf, nombre_original, bucket, s3_key, s3_url, json_resultado, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    record.hash_pdf,
                    record.nombre_original,
                    record.bucket,
                    record.s3_key,
                    record.s3_url,
                    record.json_resultado,
                    record.estado,
                ),
            )
        conn.commit()
