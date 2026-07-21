from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.orchestrator import process_upload
from src.services.s3_service import S3UploadResult
from src.services.upload_repository import UploadRecord

_SUCCESS_PIPELINE_JSON = {
    "banco": "Banco Macro",
    "detalle": [{"fecha": "2026-01-01"}, {"fecha": "2026-01-02"}],
    "fecha_desde": "2026-01-01",
    "fecha_hasta": "2026-01-31",
}


@patch("src.services.orchestrator.save")
@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.process_statement")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_new_file_processed_successfully(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_pipeline: MagicMock,
    mock_s3: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_hash.return_value = "abc123"
    mock_exists.return_value = False
    mock_s3.return_value = S3UploadResult(bucket="b", s3_key="k", s3_url="u")
    mock_pipeline.return_value = '{"banco":"Macro","detalle":[],"fecha_desde":null,"fecha_hasta":null}'

    result = process_upload(b"pdf data", "test.pdf")

    assert result["exito"] is True
    assert result["duplicado"] is False
    assert result["mensaje"] == "Extracto procesado correctamente."
    assert result["banco"] == "Macro"
    assert result["cantidad_transacciones"] == 0


@patch("src.services.orchestrator.save")
@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.process_statement")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_new_file_stores_ok_record(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_pipeline: MagicMock,
    mock_s3: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_hash.return_value = "abc123"
    mock_exists.return_value = False
    mock_s3.return_value = S3UploadResult(bucket="b", s3_key="k", s3_url="u")
    mock_pipeline.return_value = '{"banco":"test","detalle":[]}'

    process_upload(b"data", "f.pdf")

    mock_save.assert_called_once()
    record: UploadRecord = mock_save.call_args[0][0]
    assert record.hash_pdf == "abc123"
    assert record.nombre_original == "f.pdf"
    assert record.estado == "OK"
    assert record.json_resultado == '{"banco":"test","detalle":[]}'


@patch("src.services.orchestrator.calculate_sha256")
@patch("src.services.orchestrator.exists_by_hash")
def test_duplicate_file_returns_duplicate_response(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
) -> None:
    mock_hash.return_value = "dup123"
    mock_exists.return_value = True

    result = process_upload(b"pdf data", "dup.pdf")

    assert result["exito"] is False
    assert result["duplicado"] is True
    assert "ya fue cargado" in result["mensaje"]


@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_duplicate_file_does_not_upload_or_parse(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_s3: MagicMock,
) -> None:
    mock_hash.return_value = "dup123"
    mock_exists.return_value = True

    with patch("src.services.orchestrator.process_statement") as mock_pipeline:
        process_upload(b"data", "f.pdf")

    mock_s3.assert_not_called()
    mock_pipeline.assert_not_called()


@patch("src.services.orchestrator.save")
@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.process_statement")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_pipeline_error_saves_error_record(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_pipeline: MagicMock,
    mock_s3: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_hash.return_value = "err123"
    mock_exists.return_value = False
    mock_s3.return_value = S3UploadResult(bucket="b", s3_key="k", s3_url="u")
    mock_pipeline.side_effect = Exception("Pipeline error")

    result = process_upload(b"data", "err.pdf")

    assert result["exito"] is False
    assert result["duplicado"] is False
    mock_save.assert_called_once()
    record: UploadRecord = mock_save.call_args[0][0]
    assert record.estado == "ERROR"
    assert record.json_resultado is None
    assert record.hash_pdf == "err123"


@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_s3_error_returns_error_without_db_record(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
) -> None:
    mock_hash.return_value = "s3err"
    mock_exists.return_value = False

    with (
        patch("src.services.orchestrator.upload_to_s3") as mock_s3,
        patch("src.services.orchestrator.save") as mock_save,
    ):
        mock_s3.side_effect = Exception("S3 upload failed")
        result = process_upload(b"data", "f.pdf")

    assert result["exito"] is False
    assert result["duplicado"] is False
    mock_save.assert_not_called()


@patch("src.services.orchestrator.save")
@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.process_statement")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_save_ok_failure_falls_back_to_error(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_pipeline: MagicMock,
    mock_s3: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_hash.return_value = "savefail"
    mock_exists.return_value = False
    mock_s3.return_value = S3UploadResult(bucket="b", s3_key="k", s3_url="u")
    mock_pipeline.return_value = '{"banco":"test","detalle":[]}'

    mock_save.side_effect = [Exception("DB down"), None]

    result = process_upload(b"data", "f.pdf")

    assert result["exito"] is False
    assert result["duplicado"] is False
    assert mock_save.call_count == 2

    first_record: UploadRecord = mock_save.call_args_list[0][0][0]
    assert first_record.estado == "OK"

    second_record: UploadRecord = mock_save.call_args_list[1][0][0]
    assert second_record.estado == "ERROR"
    assert second_record.json_resultado is None


@patch("src.services.orchestrator.save")
@patch("src.services.orchestrator.upload_to_s3")
@patch("src.services.orchestrator.process_statement")
@patch("src.services.orchestrator.exists_by_hash")
@patch("src.services.orchestrator.calculate_sha256")
def test_save_ok_and_save_error_both_fail(
    mock_hash: MagicMock,
    mock_exists: MagicMock,
    mock_pipeline: MagicMock,
    mock_s3: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_hash.return_value = "totalfail"
    mock_exists.return_value = False
    mock_s3.return_value = S3UploadResult(bucket="b", s3_key="k", s3_url="u")
    mock_pipeline.return_value = '{"banco":"test"}'
    mock_save.side_effect = [Exception("DB down"), Exception("DB still down")]

    result = process_upload(b"data", "f.pdf")

    assert result["exito"] is False
    assert mock_save.call_count == 2
