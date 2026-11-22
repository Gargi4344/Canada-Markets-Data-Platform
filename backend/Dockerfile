# Backend image: pipeline (extract -> dbt -> data quality -> publish) + FastAPI.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    CMDP_DATA_DIR=/app/data

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY config ./config
COPY dbt ./dbt
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# Load (or incrementally refresh) the data, then serve the API.
CMD ["sh", "-c", "uv run --no-dev python -m cmdp.pipeline run; uv run --no-dev uvicorn cmdp.api.main:app --host 0.0.0.0 --port 8000"]
