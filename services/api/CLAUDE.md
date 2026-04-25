# services/api/CLAUDE.md

FastAPI public service. Read first: `.claude/skills/backend-api/SKILL.md`.

## Layout

- `routes/` — thin FastAPI routers.
- `domain/` — pure functions. No I/O. Fully unit-testable.
- `repos/` — Postgres access (SQLAlchemy/asyncpg). Lands in MVP 3.
- `schemas/` — Pydantic models for requests/responses + ORM mappers.
- `app.py` — composition root: `create_app() -> FastAPI`.
- `main.py` — uvicorn entry point.

## Dev loop

```bash
cd services/api
uv venv
uv pip install -e ".[dev]"
uv run pytest tests/unit -v
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Adding an endpoint

1. Add a router under `routes/`.
2. Add request/response Pydantic models under `schemas/`.
3. Pure logic goes in `domain/`. Repo calls go in `repos/`.
4. Write unit tests under `tests/unit/`.
5. Write integration tests under `tests/integration/` (testcontainers Postgres).
6. Re-run schemathesis locally: `uv run schemathesis run --checks all http://127.0.0.1:8000/v1/openapi.json`.
7. Update `docs/API.md` if the contract changed.

## Migrations

Alembic config arrives in MVP 3. Until then, no DB code lives in this service.

## Auth (MVP)

`X-Device-Key` (writes + product reads) or `X-Admin-Key` (admin) on all non-health endpoints. See ADR 0009.
