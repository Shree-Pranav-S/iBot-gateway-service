"""Base Pydantic schema configuration for gateway-service."""

from pydantic import BaseModel, ConfigDict


class AppBaseModel(BaseModel):
    """Base for request and response schemas."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )
