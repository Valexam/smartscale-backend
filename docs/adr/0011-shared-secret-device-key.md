# ADR 0011 — Shared-secret device key for MVP

**Status:** accepted
**Date:** 2026-04-27

## Context

Real authentication is the named successor MVP F1. MVP 3 introduces the
first non-health endpoints; we need a single bit of "request came from a
known caller" without a DB-backed identity model.

## Decision

A single shared secret `DEVICE_KEY` in env, sent by the phone as the
`X-Device-Key` header. Middleware in `services/api` rejects any request
that lacks the header or has a value not equal (constant-time) to the
configured key. The key is stored as `pydantic.SecretStr` so it stays
out of `repr()` / logs; a `RedactingFilter` strips known auth-header
names from any logged string. Startup refuses to boot when
`DEVICE_KEY` is empty unless `ENV in {dev, test}`.

## Consequences

- Compromise of the key compromises the fleet — accepted for MVP scope.
- Rotation requires a redeploy.
- The phone bakes the key in via `--dart-define=DEVICE_KEY=...`.

## Alternatives considered

- **No auth in MVP** — rejected: even a `tilt up` dev environment is
  network-reachable from the host machine; one bit of gating is cheap.
- **Per-device key in DB** — rejected: a meaningful chunk of F1 done
  early, with the wrong semantics (no rotation, no registration).
  Ship the right shape in F1, not a half-shape now.

## Reverses / supersedes

- Superseded by F1 when real auth lands.
