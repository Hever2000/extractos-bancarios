from __future__ import annotations


class PipelineError(Exception):
    """Base error for all pipeline errors."""

    def __init__(self, message: str, stage: str, detail: str | None = None) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(message)


class ExtractError(PipelineError):
    """PDF extraction failed."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, stage="extract", detail=detail)


class DetectionError(PipelineError):
    """Bank detection failed."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, stage="detect", detail=detail)


class ParseError(PipelineError):
    """Transaction parsing failed."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, stage="parse", detail=detail)


class ValidationError(PipelineError):
    """Output validation failed."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message, stage="validate", detail=detail)
