# REST API contract

Living source of truth: the OpenAPI document FastAPI serves at `/openapi.json`. This file is the design intent.

- All paths under `/v1/`. Breaking changes → `/v2/`.
- Auth: every non-health endpoint requires **`X-Device-Key`**, *or* — when
  `ADMIN_KEY` is configured on the server — `X-Admin-Key` as an alternative for
  non-device clients (the scraper worker). Both are checked by
  `DeviceKeyMiddleware`; `X-Admin-Key` is rejected when `ADMIN_KEY` is unset.
- Errors: RFC 7807 `application/problem+json` for **all** errors — auth failures
  (`DeviceKeyMiddleware`) and route/validation failures (exception handlers in
  `app.py`). Every error body carries `type`, `title`, `status`, `code`, `detail`;
  validation errors add an `errors` array, and some carry extra members (e.g. the
  archived-pantry `410` carries `archived_at`).
- **Frozen-once-resolved macros:** see ADR 0007.
- **No public product reads:** see ADR 0009.

## Endpoints

| Method & path | Auth |
|---|---|
| `POST /v1/measurements` | device/admin-key |
| `GET /v1/measurements?device_id=…&limit=…&offset=…` | device/admin-key |
| `GET /v1/products/{barcode}` | device/admin-key |
| `PUT /v1/products/{barcode}` | device/admin-key |
| `POST /v1/products/{barcode}/refresh` | device/admin-key |
| `POST /v1/user-foods` | device/admin-key |
| `GET /v1/pantry?device_id=…&limit=…&offset=…` | device/admin-key |
| `POST /v1/pantry` | device/admin-key |
| `DELETE /v1/pantry/{id}?device_id=…` | device/admin-key |
| `POST /v1/pantry/{id}/log` | device/admin-key |
| `POST /v1/voice/match` (multipart: `audio`, `device_id`) | device/admin-key |
| `GET /v1/healthz` | public |

`/v1/measurements/{id}` is intentionally not implemented — the paginated list
endpoint covers the same use case. Re-add if a single-row fetch is genuinely
needed.

### Pantry & voice (MVP 5a / 5b)

- **`POST /v1/user-foods`** — create a per-device free-form food (name + macros).
- **`GET /v1/pantry`** — list a device's live (non-archived) pantry, most-recently-used first.
- **`POST /v1/pantry`** — add an item by `barcode`, `user_food_id`, or inline `custom` macros (exactly one source). `201`.
- **`DELETE /v1/pantry/{id}`** — soft-archive (idempotent). `204`.
- **`POST /v1/pantry/{id}/log`** — log a weighed amount against a pantry item; computes + freezes macros like `POST /v1/measurements`. `201`; `410` if the item is archived.
- **`POST /v1/voice/match`** — multipart upload (`audio` + `device_id`). Transcribes via Whisper and fuzzy-matches the transcript against the device's pantry; returns `{ transcript, language, candidates[] }` (up to 3, empty if no match). Does **not** log — the phone confirms then calls `POST /v1/pantry/{id}/log`. `503` if `OPENAI_API_KEY` is unset; `502` on a Whisper upstream error.

## `POST /v1/measurements` request

```json
{
  "observed_barcode": "7311070016010",
  "weight_grams": 142.7,
  "measured_at": "2026-04-25T19:14:08Z",
  "device_id": "scale-abc123",
  "note": "half portion"
}
```

## Response (201 if product known, 202 if not yet resolved)

```json
{
  "id": "mea_01jr3y5...",
  "observed_barcode": "7311070016010",
  "product_barcode": "7311070016010",
  "weight_grams": 142.7,
  "measured_at": "2026-04-25T19:14:08Z",
  "device_id": "scale-abc123",
  "note": "half portion",
  "product": { "barcode": "7311070016010", "name": "Havremjölk", "brand": "Oatly",
               "per_100g": { "kcal": 46, "protein_g": 1.0, "carbs_g": 6.7, "fat_g": 1.5 } },
  "computed": { "kcal": 65.6, "protein_g": 1.4, "carbs_g": 9.6, "fat_g": 2.1 },
  "server_received_at": "2026-04-25T19:14:09Z"
}
```

## Error shape (RFC 7807)

A route error (`GET /v1/products/{barcode}` for an unknown barcode):

```json
{
  "type": "https://smartscale.example/errors/not-found",
  "title": "Not Found",
  "status": 404,
  "code": "NOT_FOUND",
  "detail": "product not found"
}
```

A request-validation error carries an `errors` array; the archived-pantry `410`
carries an `archived_at` extension member. `code` is derived from the status
(`NOT_FOUND`, `VALIDATION_ERROR`, `GONE`, `INVALID_DEVICE_KEY`, …).

## Postgres schema

- `products(barcode PK, name, brand, source, source_url, raw_payload jsonb, kcal_per_100g, protein_g_per_100g, carbs_g_per_100g, fat_g_per_100g, fiber_g_per_100g, scraped_at, refreshed_at)`
- `measurements(id PK, device_id, observed_barcode, product_barcode FK→products NULL, weight_grams, measured_at, computed_kcal, computed_protein_g, computed_carbs_g, computed_fat_g, note, server_received_at)`
- `scrape_jobs(barcode PK, status enum, attempts, last_error, scheduled_at, completed_at)`

`measurements.product_barcode` is FK-nullable so a measurement can be logged before the scraper resolves the product.

## PUT /v1/products/{barcode}

User-submitted product data and scraper-submitted product data both write here. Body:

```json
{ "name": "Havremjölk", "brand": "Oatly",
  "per_100g": { "kcal": 46, "protein_g": 1.0, "carbs_g": 6.7, "fat_g": 1.5, "fiber_g": 0.8 } }
```

201 on create, 200 on replace. Body:

```json
{ "product": { ... }, "measurements_backfilled": 3 }
```

Back-fill resolves measurements for this barcode where `product_barcode IS NULL`,
freezing their `computed_*` values. Already-frozen rows are never touched
(ADR 0007).
