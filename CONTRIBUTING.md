# Contributing

## Workflow

1. Open an issue first for anything non-trivial — saves wasted work if the change isn't a fit.
2. Fork or branch from `main`.
3. Make focused commits. One logical change per commit. Tests pass at HEAD.
4. Open a PR against `main`. CI must be green before merge.

## Commit format

Conventional Commits:

```
<type>(<scope>): <subject>
```

Allowed types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `revert`.
Allowed scopes: `api`, `db`, `infra`, `docs`, `ci`, `repo`.

- Imperative subject, lowercase, no trailing period, ≤72 chars.
- Body explains *why*, not *what* — the diff is the *what*. Wrap at 72.
- AI-assisted commits include a `Co-Authored-By: <name> <email>` trailer.

The `conventional-pre-commit` hook enforces type/scope at commit time. Install hooks with:

```bash
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Code style

- `ruff` lint + format.
- `mypy --strict` clean.
- `pytest tests/unit -v` green. Integration tests use testcontainers Postgres.
- File-size soft cap: 300 lines per source file.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) for the dev loop.

## What about the older commit history?

This repo was extracted from a private monorepo via `git filter-repo`. Commits dated before 2026-05 carry footers (`Wave: <name>`, occasionally a stale ADR reference) that referenced an internal MVP roadmap that no longer applies. New commits don't need any of that — the format above is all that's required.

## License

By contributing you agree your contribution is licensed under the MIT License (see [`LICENSE`](LICENSE)).
