"""Smoke tests for gateway custom exception JSON responses."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.error_handler import register_exception_handlers
from src.core.exceptions import (
    DownstreamUnavailableException,
    MissingAccessTokenException,
)


def test_unauthorized_exception_envelope() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    def protected() -> None:
        raise MissingAccessTokenException()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/protected")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Missing access token."


def test_downstream_unavailable_exception() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/proxy")
    def proxy() -> None:
        raise DownstreamUnavailableException()

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/proxy")

    assert response.status_code == 502
    assert response.json()["success"] is False
