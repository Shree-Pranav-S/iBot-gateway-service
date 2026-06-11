"""Gateway health endpoint."""

from fastapi import APIRouter

from src.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="Gateway health")
async def health_check() -> dict[str, str]:
    """Return gateway liveness metadata."""

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }
