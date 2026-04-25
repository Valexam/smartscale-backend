# ADR 0004 — FastAPI + Postgres for backend

**Status:** accepted
**Date:** 2026-04-25

## Context

The backend needs typed request/response validation, an auto-generated OpenAPI document (consumed by mobile + later by direct-ESP32 mode), async-friendliness, and a relational store for products + measurements + scrape jobs.

## Decision

Python 3.12, FastAPI for HTTP, Pydantic for validation, SQLAlchemy/asyncpg for DB, Postgres for storage, Alembic for migrations, uv for dependencies, ruff + mypy (strict) for hygiene, pytest + testcontainers for tests.

## Consequences

- OpenAPI spec is a build artifact, not a side document — mobile + direct-ESP32 mode can codegen against it.
- Strong typing end-to-end (Pydantic ↔ SQLAlchemy ↔ TypedDict where useful).
- Alternative would be Node/NestJS (TS end-to-end) or Go — both rejected for solo-dev velocity reasons.

## Alternatives considered

- **NestJS + TypeScript:** rejected — more boilerplate; mobile is deferred so TS-everywhere isn't a payoff yet.
- **Go + chi/Echo:** rejected — slower to scaffold; OpenAPI codegen is more painful.

## Reverses / supersedes

none
