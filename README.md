# smartscale-backend

FastAPI backend for the SmartScale food scale. Stores measurements, looks up products by barcode, matches voice transcripts against a per-user pantry, and serves it all over HTTPS with `X-Device-Key` auth.

The hardware (ESP32 firmware) and the phone app that talks to this backend live in a separate private repo. This repo is the half that's open-source.

## Stack

- **Python 3.12** + **FastAPI** + **SQLAlchemy async**
- **Postgres 16** for measurements, products, pantry, scrape jobs
- **Alembic** migrations
- **OpenAI Whisper** for voice transcription (via API)
- **uv** for dependency management
- **Docker Compose** + **Caddy** for deployment

## Quick start

```bash
git clone https://github.com/Valexam/smartscale-backend.git
cd smartscale-backend/infra/prod
cp .env.example .env       # edit values
docker compose up -d postgres
docker compose run --rm migrate
docker compose up -d api
curl http://localhost:8000/v1/healthz
```

For local development (without Caddy): see [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md).
For production deploy: see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).
For the wire contract: see [`docs/API.md`](docs/API.md) and [`services/api/openapi.json`](services/api/openapi.json).

## Repo layout

```
services/api/        FastAPI service (routes, domain, repos, schemas)
services/db/         Alembic config + migrations
infra/prod/          docker-compose + Caddyfile + .env.example
docs/                API contract, architecture, dev + deploy runbooks
docs/adr/            Architecture decision records
.github/workflows/   CI: tests, contract checks, image push, deploy
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). PRs welcome.

## License

MIT — see [`LICENSE`](LICENSE).
