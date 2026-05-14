# Deployment

The backend ships as four containers via docker compose: `postgres`, a one-shot `migrate`, the `api`, and `caddy` for TLS termination. Single VM is plenty for one device + one user; the stack scales horizontally later if needed.

The full runbook — VM provisioning, DNS, secrets, redeploys, postgres password rotation, backups, troubleshooting — lives in [`../infra/prod/README.md`](../infra/prod/README.md).

## TL;DR

1. Buy a domain, point `api.<your-domain>` at a fresh Linux VM.
2. SSH in, install Docker, create a `deploy` user, drop in `docker-compose.yml` + `Caddyfile` + `.env` from this repo's `infra/prod/`.
3. `docker compose up -d --wait`. Caddy auto-issues a Let's Encrypt cert on first request.
4. `curl https://api.<your-domain>/v1/healthz` → `{"status":"ok"}`.

## What runs where

- `infra/prod/docker-compose.yml` — service definitions.
- `infra/prod/Caddyfile` — TLS + reverse proxy.
- `infra/prod/.env` — secrets and per-deploy config (gitignored).
- `.github/workflows/backend.yml` — builds and pushes `ghcr.io/valexam/smartscale-api:<sha>` on every merge to `main`.
- `.github/workflows/deploy.yml` — SSHes to the VM and rolls the stack with `docker compose pull && up -d --wait`. Gated on the `SSH_HOST` secret; skips cleanly if not configured.

## Cost

The reference deployment runs on a Hetzner CX22 (~€3.79/mo) + 10 GB Volume (€0.44/mo) + 20 % backups surcharge. Roughly €4.50/mo total. Any VPS that runs Docker works — Hetzner just happens to be cheap and reliable.

## What the public Docker image is not

The image `ghcr.io/valexam/smartscale-api` is publicly pullable, but a running instance does *not* serve public traffic — the API requires `X-Device-Key` on every non-health endpoint. You can run your own copy by setting your own `DEVICE_KEY` in `.env`.
