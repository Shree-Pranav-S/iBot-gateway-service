FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8002

WORKDIR /app
ENV UV_PROJECT_ENVIRONMENT="/opt/venv"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

ENV PATH="/opt/venv/bin:$PATH"
USER appuser

EXPOSE 8002

ENTRYPOINT ["sh", "-c", "uvicorn src.api.rest.app:app --host 0.0.0.0 --port ${PORT} --timeout-graceful-shutdown 10"]
