# infra/prod

Production deployment for the SmartScale API. Single VM, docker compose,
Caddy auto-TLS, Postgres on a Hetzner Volume. See [spec](../../docs/superpowers/specs/2026-05-14-mvp-infra-1-hetzner-design.md)
for design and tradeoffs; this README is the runbook.

## Stack

| Service  | Image                                         | Role                                  |
|----------|-----------------------------------------------|---------------------------------------|
| postgres | postgres:16-alpine                            | DB. Data on `${POSTGRES_DATA_DIR}`.   |
| migrate  | ghcr.io/valexam/smartscale-api:`${API_IMAGE_TAG}` | One-shot `alembic upgrade head`.  |
| api      | ghcr.io/valexam/smartscale-api:`${API_IMAGE_TAG}` | FastAPI on :8000.                  |
| caddy    | caddy:2-alpine                                | TLS termination + reverse proxy.      |

Compose-level guarantees:

- api waits for migrate to complete successfully.
- migrate waits for postgres to be healthy.
- caddy waits for api to be healthy.
- `docker compose up -d --wait` blocks until every service is healthy → zero-downtime swap on redeploy.

## First-boot bootstrap (one-time)

Skip this if you're just smoke-testing locally — see [Local smoke-test](#local-smoke-test) instead.

### 1. DNS

Buy a domain (or pick a subdomain you control). Create an **A-record** pointing your chosen hostname (e.g. `api.example.tld`) at the VM's public IPv4. Wait for propagation (`dig +short api.example.tld`).

### 2. Hetzner VM

- Project → **+ Add Server**.
- Location: **Falkenstein** (or whichever is closest to you).
- Image: **Ubuntu 24.04**.
- Type: **CX22** (€3.79/mo).
- Volumes: **+ Create Volume**, 10 GB, auto-mount at `/mnt/postgres-data`.
- Networking: IPv4 + IPv6.
- SSH key: add your key.
- Backups: **enable** (+20%, ~€0.76/mo).
- Firewall: allow inbound 22 (SSH), 80, 443.

SSH in as root, then:

```bash
# System hygiene + Docker
apt update && apt upgrade -y
curl -fsSL https://get.docker.com | sh

# Deploy user
adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy
mkdir -p /home/deploy/.ssh
# Paste the CI deploy public key:
nano /home/deploy/.ssh/authorized_keys
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

# Project directory
mkdir -p /opt/smartscale && chown deploy:deploy /opt/smartscale
mkdir -p /mnt/caddy-data && chown deploy:deploy /mnt/caddy-data
chown -R deploy:deploy /mnt/postgres-data
```

### 3. Drop in the compose stack

As the deploy user (or from your laptop via `scp`):

```bash
cd /opt/smartscale
# Three files needed:
#   docker-compose.yml
#   Caddyfile
#   .env
```

Pull them from this repo's `infra/prod/` and create `.env` from `.env.example`. Pin `POSTGRES_DATA_DIR=/mnt/postgres-data` and `CADDY_DATA_DIR=/mnt/caddy-data`. Generate strong values:

```bash
# 32-char random strings for POSTGRES_PASSWORD and DEVICE_KEY:
openssl rand -hex 16
```

Lock down secrets:

```bash
chmod 600 .env
```

### 4. GHCR login (for private images)

The api image will be public on first push (org-owned), so this step is *only* needed if you make the package private:

```bash
echo "<github-pat-with-read:packages>" | docker login ghcr.io -u <username> --password-stdin
```

### 5. First `up`

```bash
docker compose up -d --wait
```

First boot does three things in order:

1. Postgres initdb (creates DB with the password from `.env`).
2. Migrate runs `alembic upgrade head`.
3. Api starts, passes healthcheck.
4. Caddy starts, requests a Let's Encrypt cert via HTTP-01 (this is why port 80 must be open).

Verify:

```bash
curl https://<your-domain>/v1/healthz   # → {"status":"ok"}
docker compose logs --tail 50 caddy     # look for "certificate obtained successfully"
```

### 6. Mobile cutover

Build a release APK pointing at the new endpoint:

```bash
cd apps/mobile
flutter build apk --release \
  --dart-define=API_BASE_URL=https://<your-domain> \
  --dart-define=DEVICE_KEY=<same DEVICE_KEY as .env on VM> \
  --dart-define=DEVICE_ID=scale-abc
```

Install over USB, then **disconnect the cable** and verify pantry + voice work over cellular.

## Local smoke-test

Same compose file works on the dev Mac. Caveats: Caddy will try to obtain a real cert for `${DOMAIN}` via Let's Encrypt — for local testing, skip Caddy:

```bash
cd infra/prod
cp .env.example .env
# Pick any values for POSTGRES_PASSWORD, DEVICE_KEY, OPENAI_API_KEY, DOMAIN, ACME_EMAIL.
# (Caddy won't run, so DOMAIN/ACME_EMAIL don't matter beyond compose's :? check.)

docker compose build api
docker compose up -d --wait postgres migrate api
docker compose port api 8000   # → 0.0.0.0:<random>
curl http://localhost:<random>/v1/healthz   # → {"status":"ok"}

docker compose down
```

`postgres-data/` and `caddy-data/` directories are created in this folder on first run; both are gitignored.

## Redeploys

Handled by `.github/workflows/deploy.yml` on every merge to `main`. Manually:

```bash
ssh deploy@<host>
cd /opt/smartscale
sed -i "s|^API_IMAGE_TAG=.*|API_IMAGE_TAG=<git-sha>|" .env
docker compose pull api migrate
docker compose up -d --wait
docker image prune -f
```

Compose's `--wait` + the api healthcheck guarantee the new container is serving before the old one is torn down.

## Postgres password rotation

`POSTGRES_PASSWORD` in `.env` is only consumed on initdb. To rotate after first boot:

```bash
docker compose exec postgres psql -U smartscale -c "ALTER USER smartscale WITH PASSWORD '<new>';"
# Update .env to match — required so api can reconnect on next restart.
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=<new>|" .env
docker compose up -d --wait api migrate    # picks up the new password
```

## Backups

Hetzner snapshot backups (enabled in step 2) snapshot the entire VM + Volume nightly with a 7-day retention. That covers the Postgres data dir. For belt-and-braces:

```bash
# Cron candidate (not yet automated):
docker compose exec postgres pg_dump -U smartscale -d smartscale | gzip > /mnt/postgres-data/backups/$(date -I).sql.gz
```

## Troubleshooting

**Caddy never gets a cert.** Check the A-record (`dig +short <domain>`), check the firewall (`curl http://<vm-ip>/` from outside must return *something* — even a 404 is fine), check `docker compose logs caddy` for the Let's Encrypt error. The most common cause is DNS pointing at the wrong IP or propagation lag.

**Api restart loop.** `docker compose logs api`. If `assert_safe_to_start` fired, `DEVICE_KEY` is empty in `.env`.

**Migrate fails on first boot.** `docker compose logs migrate`. Usually a Postgres password mismatch — check `.env` matches what was set on initdb. If the data dir is empty and you got the password wrong, easiest fix is `docker compose down -v && rm -rf /mnt/postgres-data/* && docker compose up -d --wait` (LOSES DATA, only do on a fresh deploy).
