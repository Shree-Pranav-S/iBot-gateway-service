"""Common API response envelopes."""

from src.schemas.base import AppBaseModel


class ErrorDetail(AppBaseModel):
    """Single validation or field-level error detail."""

    field: str | None = None
    message: str


class ErrorResponse(AppBaseModel):
    """Standard error envelope returned on 4xx / 5xx responses."""

    success: bool = False
    message: str
    errors: list[ErrorDetail] | None = None
