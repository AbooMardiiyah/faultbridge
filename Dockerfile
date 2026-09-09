FROM ghcr.io/astral-sh/uv:0.9.9-python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY migrations ./migrations
COPY scripts ./scripts
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["sh", "-c", "uv run python3 scripts/migrate.py && exec uv run uvicorn faultbridge.api:app --host 0.0.0.0 --port 8000"]
