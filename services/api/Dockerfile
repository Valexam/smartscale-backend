# services/api/Dockerfile
# Build context: repo root (so we can bundle services/db/migrations alongside the app).

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

# Install runtime deps from the locked closure (no dev tools).
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY services/api/src ./src
COPY services/db/migrations ./migrations
COPY services/db/alembic.ini .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["python", "-m", "smartscale_api.main"]
