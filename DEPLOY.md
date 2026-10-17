# CortexOS Deployment Guide

Two options below. Railway is recommended for quickest setup. Fly.io gives more control.

After deploying with either platform, run `scripts/check_deploy.py` to verify everything works end-to-end.

---

## Option 1: Railway (Recommended)

Railway auto-detects the `docker-compose.yml` but we deploy the engine service directly for more control over the database choice.

### 1. Install Railway CLI

```bash
npm i -g @railway/cli
railway login
```

### 2. Create project

```bash
# From repo root
railway init
# When prompted, name it: cortexos
```

### 3. Add a database

**Option A — Railway Postgres (easiest, but verify pgvector support)**

```bash
railway add --plugin postgresql
```

Then check if pgvector is available:

```bash
railway run psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

If that errors with "extension not found", use Option B.

**Option B — Supabase Postgres (free, pgvector built in)**

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Go to **Settings → Database** and copy the **Connection string (URI)**.
   It looks like: `postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres`

> **Note:** CortexOS does not currently use pgvector index types — it stores embeddings
> as `FLOAT8[]` arrays and computes cosine similarity in Python. The `vector` extension
> is not strictly required right now but will be needed for Phase 2 ANN indexes.
> Railway Postgres without pgvector will work fine today.

### 4. Set environment variables

```bash
# If using Railway Postgres, DATABASE_URL is auto-injected. Extract it:
railway variables

# Set the two URL vars (adjust credentials to match your DB):
railway variables set CORTEX_DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>:5432/<db>"
railway variables set CORTEX_DATABASE_URL_SYNC="postgresql://<user>:<pass>@<host>:5432/<db>"

# Generate and set admin secret:
railway variables set CORTEX_ADMIN_SECRET="$(openssl rand -hex 32)"
```

> The sync URL is the same as the async URL but without `+asyncpg` — alembic uses it
> for migrations (it runs synchronously).

### 5. Deploy

```bash
# From repo root — deploy the cortex-engine directory
railway up --service cortexos --source ./cortex-engine
```

Railway will build from `cortex-engine/Dockerfile`, run alembic migrations via
`entrypoint.sh`, then start uvicorn.

### 6. Get your public URL

```bash
railway open
# Or:
railway status
```

Your URL will be something like `https://cortexos-production.up.railway.app`.

### 7. Seed the admin API key

```bash
railway run --service cortexos python -m cortex.seed_admin
```

Save the printed key — it is shown only once.

### 8. Verify

```bash
curl https://<your-subdomain>.railway.app/healthz
# → {"status": "ok"}

# Full end-to-end check:
CORTEX_ADMIN_SECRET="<your-secret>" python scripts/check_deploy.py https://<your-subdomain>.railway.app
```

---

## Option 2: Fly.io

### fly.toml

Create `cortex-engine/fly.toml`:

```toml
app = "cortexos"
primary_region = "iad"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 0

  [http_service.concurrency]
    type = "requests"
    hard_limit = 200
    soft_limit = 150

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"

[checks]
  [checks.health]
    grace_period = "20s"
    interval = "10s"
    method = "GET"
    path = "/healthz"
    port = 8000
    timeout = "5s"
    type = "http"
```

### Steps

**1. Launch the app** (from `cortex-engine/`)

```bash
cd cortex-engine
fly launch --no-deploy
# Accept the generated fly.toml or use the one above.
# When asked "would you like to set up a PostgreSQL database now?", say No — we do it next.
```

**2. Create a Postgres cluster**

```bash
fly postgres create --name cortexos-db --region iad --vm-size shared-cpu-1x --volume-size 10
```

**3. Attach the database**

```bash
fly postgres attach cortexos-db --app cortexos
# Fly sets DATABASE_URL automatically on the app
```

This injects `DATABASE_URL` as `postgres://...`. We need to create the two env vars
the engine expects:

```bash
# The attached DATABASE_URL uses postgres:// — pull it out:
fly secrets list --app cortexos

# Set Cortex-prefixed vars (replace the URL from above):
fly secrets set \
  CORTEX_DATABASE_URL="postgresql+asyncpg://<user>:<pass>@<host>.flycast:5432/<db>" \
  CORTEX_DATABASE_URL_SYNC="postgresql://<user>:<pass>@<host>.flycast:5432/<db>" \
  CORTEX_ADMIN_SECRET="$(openssl rand -hex 32)" \
  --app cortexos
```

> Fly uses `.flycast` internal DNS for private networking between machines.
> Use `fly postgres connect --app cortexos-db` to get the connection details.

**4. Deploy**

```bash
fly deploy --app cortexos
# Builds from cortex-engine/Dockerfile, runs alembic, starts uvicorn
```

**5. Seed admin key**

```bash
fly ssh console --app cortexos -C "python -m cortex.seed_admin"
```

**6. Verify**

```bash
curl https://cortexos.fly.dev/healthz
# → {"status": "ok"}

CORTEX_ADMIN_SECRET="<your-secret>" python scripts/check_deploy.py https://cortexos.fly.dev
```

---

## Environment Variable Reference

| Variable | Required | Description |
|---|---|---|
| `CORTEX_DATABASE_URL` | Yes | Async DB URL (`postgresql+asyncpg://...`) — used by the app at runtime |
| `CORTEX_DATABASE_URL_SYNC` | Yes | Sync DB URL (`postgresql://...`) — used by alembic during migrations |
| `CORTEX_ADMIN_SECRET` | Yes | Protects `POST /api-keys`. Generate with `openssl rand -hex 32` |
| `CORTEX_EMBEDDING_MODEL` | No | Defaults to `all-MiniLM-L6-v2` (baked into Docker image) |
| `CORTEX_CORS_ORIGINS` | No | Comma-separated allowed origins. Defaults to `localhost:3000,localhost:3001` |

---

## Troubleshooting

**Migrations fail on first deploy**

The engine entrypoint runs `alembic upgrade head` before starting. If the DB is not
reachable yet, the container exits and restarts. This is usually fine — the platform
will retry until Postgres is ready. If it keeps failing, check `CORTEX_DATABASE_URL_SYNC`.

**`detail: Admin secret not configured`**

`CORTEX_ADMIN_SECRET` is not set, or is still the default `changeme-set-CORTEX_ADMIN_SECRET`.
Set it to any random string: `openssl rand -hex 32`.

**`401 Invalid API key`**

The Bearer token is wrong or the key was not seeded. Run `python -m cortex.seed_admin`
(or the platform-specific equivalent above) to generate a fresh key.

**Cold start is slow (Railway free tier)**

The Docker image pre-downloads `all-MiniLM-L6-v2` at build time, so the model is
already on disk. Cold starts should take < 10s. If the platform re-pulls the image
frequently, the model download is cached in the image layer and does not re-run.
