# ADR 0007 — Frozen-once-resolved macros

**Status:** accepted
**Date:** 2026-04-25

## Context

Product macro data (kcal, protein, etc., per 100g) is owned by the scraper and changes over time as sources update or we re-scrape. A measurement logged today is a record of what the user ate; if we recompute its macros tomorrow against the latest product data, the log silently mutates.

## Decision

Macros stored on the `measurements` row are frozen once written. They're written either:
1. **At insert time**, if the product is already in the DB (synchronous compute on `POST /v1/measurements`).
2. **Exactly once by a worker**, if the product is missing at insert time and a scrape later resolves it.

After they are written, they are never silently recomputed. `measurements.barcode` is a nullable FK so the row can exist before the product does.

## Consequences

- Logs are auditable: "what was eaten" is fixed at the moment of measurement.
- Schema needs `computed_kcal`, `computed_protein_g`, `computed_carbs_g`, `computed_fat_g` columns on `measurements`.
- A separate workflow (admin endpoint or DB migration) is needed if we ever want to deliberately re-freeze a measurement against new product data.

## Alternatives considered

- **Compute on read from product table:** rejected — silent mutation.
- **Snapshot the entire product row on each measurement:** rejected — wasteful storage; the four computed fields are enough.

## Reverses / supersedes

none
