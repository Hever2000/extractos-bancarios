from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.upload_repository import UploadRecord, exists_by_hash, save

_DB_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "1433",
    "DB_NAME": "test_db",
    "DB_USER": "sa",
    "DB_PASSWORD": "pass",
}


def _mock_cursor(mock_connect: MagicMock, fetchone_result: tuple | None = None) -> MagicMock:
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result

    conn = mock_connect.return_value
    conn.cursor.return_value.__enter__.return_value = mock_cursor

    return mock_cursor


class TestExistsByHash:
    @patch("src.services.upload_repository.pymssql.connect")
    def test_returns_true_when_count_greater_than_zero(self, mock_connect: MagicMock) -> None:
        _mock_cursor(mock_connect, (1,))

        with patch.dict("os.environ", _DB_ENV):
            result = exists_by_hash("abc123")

        assert result is True

    @patch("src.services.upload_repository.pymssql.connect")
    def test_returns_false_when_count_is_zero(self, mock_connect: MagicMock) -> None:
        _mock_cursor(mock_connect, (0,))

        with patch.dict("os.environ", _DB_ENV):
            result = exists_by_hash("nonexistent")

        assert result is False

    @patch("src.services.upload_repository.pymssql.connect")
    def test_returns_false_when_no_rows(self, mock_connect: MagicMock) -> None:
        _mock_cursor(mock_connect, None)

        with patch.dict("os.environ", _DB_ENV):
            result = exists_by_hash("ghost")

        assert result is False

    @patch("src.services.upload_repository.pymssql.connect")
    def test_calls_correct_query(self, mock_connect: MagicMock) -> None:
        mock_cursor = _mock_cursor(mock_connect, (0,))

        with patch.dict("os.environ", _DB_ENV):
            exists_by_hash("abc123")

        mock_cursor.execute.assert_called_once_with(
            "SELECT COUNT(1) FROM impo_uni_archivos_upload WHERE hash_pdf = %s",
            ("abc123",),
        )

    @patch("src.services.upload_repository.pymssql.connect")
    def test_uses_custom_table_from_env(self, mock_connect: MagicMock) -> None:
        mock_cursor = _mock_cursor(mock_connect, (0,))

        with patch.dict("os.environ", {**_DB_ENV, "DB_TABLE": "mi_tabla"}):
            exists_by_hash("xyz")

        sql = mock_cursor.execute.call_args[0][0]
        assert "mi_tabla" in sql


class TestSave:
    @patch("src.services.upload_repository.pymssql.connect")
    def test_inserts_ok_record(self, mock_connect: MagicMock) -> None:
        mock_cursor = _mock_cursor(mock_connect)
        mock_conn = mock_connect.return_value

        record = UploadRecord(
            hash_pdf="hash123",
            nombre_original="test.pdf",
            bucket="bucket",
            s3_key="extractos/2026/07/uuid.pdf",
            s3_url="https://bucket.s3.amazonaws.com/key",
            json_resultado='{"banco": "test"}',
            estado="OK",
        )

        with patch.dict("os.environ", _DB_ENV):
            save(record)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("src.services.upload_repository.pymssql.connect")
    def test_inserts_error_record_with_null_json(self, mock_connect: MagicMock) -> None:
        mock_cursor = _mock_cursor(mock_connect)
        mock_conn = mock_connect.return_value

        record = UploadRecord(
            hash_pdf="hash456",
            nombre_original="error.pdf",
            bucket="bucket",
            s3_key="extractos/2026/07/err.pdf",
            s3_url="https://bucket.s3.amazonaws.com/err",
            json_resultado=None,
            estado="ERROR",
        )

        with patch.dict("os.environ", _DB_ENV):
            save(record)

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    @patch("src.services.upload_repository.pymssql.connect")
    def test_insert_params_match_columns(self, mock_connect: MagicMock) -> None:
        mock_cursor = _mock_cursor(mock_connect)

        record = UploadRecord(
            hash_pdf="h",
            nombre_original="f.pdf",
            bucket="b",
            s3_key="k",
            s3_url="u",
            json_resultado="{}",
            estado="OK",
        )

        with patch.dict("os.environ", _DB_ENV):
            save(record)

        sql = mock_cursor.execute.call_args[0][0]
        for col in ("hash_pdf", "nombre_original", "bucket", "s3_key", "s3_url", "json_resultado", "estado"):
            assert col in sql
        assert "%s" in sql
