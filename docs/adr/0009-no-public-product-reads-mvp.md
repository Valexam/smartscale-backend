# ADR 0009 — No public product reads in MVP

**Status:** accepted
**Date:** 2026-04-25

## Context

The original sketch had `GET /v1/products/{barcode}` as a public endpoint. Public read of our scraped product DB is effectively a free proxy: any third party can re-scrape our scrape, with us paying the source-side rate limit and bandwidth.

## Decision

In MVP, all non-health endpoints (including `GET /v1/products/{barcode}`) require `X-Device-Key` or `X-Admin-Key`. A future ADR may open up a separate, rate-limited public route under `/public/v1/products/{barcode}` if there's demand.

## Consequences

- Scraper costs are proportional to scale-device traffic, not to internet traffic.
- Reverting an "internal" endpoint to public is cheap; the reverse is not — so the more-restrictive default is safer.
- Anyone wanting public-read access has to make a case for it (and a new ADR).

## Alternatives considered

- **Public read with per-IP rate limit:** rejected for MVP — adds a rate-limit infra dep (Redis or reverse-proxy module) that isn't worth it yet.
- **Public read of a curated subset:** rejected — premature curation.

## Reverses / supersedes

none
