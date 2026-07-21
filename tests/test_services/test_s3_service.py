from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.services.s3_service import S3UploadResult, upload_to_s3


@patch("src.services.s3_service.boto3.client")
def test_upload_to_s3_returns_upload_result(mock_client: MagicMock) -> None:
    mock_s3 = MagicMock()
    mock_s3.meta.region_name = "us-east-1"
    mock_client.return_value = mock_s3

    with patch.dict("os.environ", {"S3_BUCKET": "test-bucket"}):
        result = upload_to_s3(b"pdf content", "test.pdf")

    assert isinstance(result, S3UploadResult)
    assert result.bucket == "test-bucket"
    assert result.s3_key.startswith("extractos/")
    assert result.s3_key.endswith(".pdf")
    assert result.s3_url == f"https://test-bucket.s3.us-east-1.amazonaws.com/{result.s3_key}"

    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key=result.s3_key,
        Body=b"pdf content",
    )


@patch("src.services.s3_service.boto3.client")
def test_upload_to_s3_url_includes_region(mock_client: MagicMock) -> None:
    mock_s3 = MagicMock()
    mock_s3.meta.region_name = "sa-east-1"
    mock_client.return_value = mock_s3

    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}):
        result = upload_to_s3(b"data", "f.pdf")

    assert "s3.sa-east-1.amazonaws.com" in result.s3_url


@patch("src.services.s3_service.boto3.client")
def test_upload_to_s3_url_no_region_fallback(mock_client: MagicMock) -> None:
    mock_s3 = MagicMock()
    mock_s3.meta.region_name = None
    mock_client.return_value = mock_s3

    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}):
        result = upload_to_s3(b"data", "f.pdf")

    assert "s3.amazonaws.com" in result.s3_url


@patch("src.services.s3_service.boto3.client")
def test_upload_to_s3_key_includes_year_month_uuid(mock_client: MagicMock) -> None:
    mock_s3 = MagicMock()
    mock_s3.meta.region_name = "us-east-1"
    mock_client.return_value = mock_s3

    with patch.dict("os.environ", {"S3_BUCKET": "b"}):
        result = upload_to_s3(b"data", "test.pdf")

    parts = result.s3_key.split("/")
    assert len(parts) == 4
    assert parts[0] == "extractos"
    assert parts[1].isdigit()
    assert parts[2].isdigit()
    assert parts[3].endswith(".pdf")
