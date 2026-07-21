from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pymssql


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
    conn = pymssql.connect(
        server=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "1433"),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    try:
        yield conn
    finally:
        conn.close()


def _table_name() -> str:
    return os.getenv("DB_TABLE", "impo_uni_archivos_upload")


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
