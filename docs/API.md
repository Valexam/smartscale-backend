# REST API contract

Living source of truth: the OpenAPI document FastAPI serves at `/openapi.json`. This file is the design intent.

- All paths under `/v1/`. Breaking changes → `/v2/`.
- Auth: `X-Device-Key` (writes + product reads) or `X-Admin-Key` (admin) on all non-health endpoints.
- Errors: RFC 7807 `application/problem+json`.
- **Frozen-once-resolved macros:** see ADR 0007.
- **No public product reads in MVP:** see ADR 0009.

## Endpoints (MVP scope)

| Method & path | Auth | First MVP |
|---|---|---|
| `POST /v1/measurements` | device-key | 3 |
| `GET /v1/measurements?device_id=…&limit=…` | device-key | 4 |
| `GET /v1/measurements/{id}` | device-key | 4 |
| `GET /v1/products/{barcode}` | device-key | 4 |
| `POST /v1/products/{barcode}/refresh` | admin-key | scraper-MVP |
| `GET /v1/healthz` | public | 0 |

## `POST /v1/measurements` request

```json
{
  "barcode": "7311070016010",
  "weight_grams": 142.7,
  "measured_at": "2026-04-25T19:14:08Z",
  "device_id": "scale-abc123",
  "note": "half portion"
}
```

## Response (200 if product known, 202 if scrape was enqueued)

```json
{
  "id": "mea_01HXYZ...",
  "barcode": "7311070016010",
  "weight_grams": 142.7,
  "measured_at": "2026-04-25T19:14:08Z",
  "product": {
    "barcode": "7311070016010",
    "name": "Havremjölk",
    "brand": "Oatly",
    "per_100g": { "kcal": 46, "protein_g": 1.0, "carbs_g": 6.7, "fat_g": 1.5 }
  },
  "computed": { "kcal": 65.6, "protein_g": 1.4, "carbs_g": 9.6, "fat_g": 2.1 },
  "server_received_at": "2026-04-25T19:14:09Z"
}
```

## Error shape (RFC 7807)

```json
{
  "type": "https://smartscale.example/errors/product-not-found",
  "title": "Product not found",
  "status": 404,
  "code": "PRODUCT_NOT_FOUND",
  "barcode": "7311070016010"
}
```

## Postgres schema (target — created by Alembic in MVP 3)

- `products(barcode PK, name, brand, source, source_url, raw_payload jsonb, kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g, fiber_g_per_100g, scraped_at, refreshed_at)`
- `measurements(id PK, device_id, barcode FK→products NULL, weight_grams, measured_at, computed_kcal, computed_protein_g, computed_carbs_g, computed_fat_g, note, server_received_at)`
- `scrape_jobs(barcode PK, status enum, attempts, last_error, scheduled_at, completed_at)`

`measurements.barcode` is FK-nullable so a measurement can be logged before the scraper resolves the product.
