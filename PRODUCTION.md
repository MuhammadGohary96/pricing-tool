# Production deployment

Checklist and configuration for running the Pricing Tool in production.

## Required environment variables (backend)

Set these via your secret manager / environment — do **not** bake them into the image.

| Variable | Required | Notes |
|---|---|---|
| `DATA_SOURCE` | **yes** | Must be `bigquery` (default is `mock`). |
| `GOOGLE_CLIENT_ID` | **yes** | OAuth client id. **If unset, authentication is disabled (dev mode).** Must match the value the frontend signs in with. |
| `CORS_ORIGINS` | **yes** | JSON list of the production frontend origin(s), e.g. `["https://pricing.breadfast.com"]` (default is `http://localhost:5174`). |
| `GOOGLE_APPLICATION_CREDENTIALS` | **yes** | Path to the BigQuery service-account key (or use workload identity). The SA needs **read + `tables.get`** on both source tables. |
| `BQ_PROJECT_ID` / `BQ_DATASET` | yes | Source project/dataset. |
| `BQ_TABLE` | yes | Pricing table (`pricing_index_analysis`). |
| `BQ_COMPETITOR_TABLE` | yes | Competitor table (`competitor_products_analysis`). |
| `BQ_LOCATION` | yes | e.g. `EU`. |
| `DUCKDB_PARQUET_PATH` / `COMPETITOR_PARQUET_PATH` | recommended | Cache file paths — point at a **writable, persistent volume** so cache survives restarts. |
| `AUTO_REFRESH_ENABLED` / `REFRESH_INTERVAL_SECONDS` | optional | Default on, hourly. |

`BF_CATALOG_TOKEN` / `BF_CATALOG_URL` are **removed** — the app no longer fetches or writes live Catalog prices (now-prices come from BigQuery), and a static token must never be a way past auth.

## Frontend config (no separate variable needed)

The SPA fetches the Google client id from the backend at runtime (`GET /api/config`,
public), so **setting `GOOGLE_CLIENT_ID` in the server env configures both API auth
and frontend sign-in** — one value, no build-time bake, no CI secret. Build the image
once; configure it per environment via env vars.

`VITE_GOOGLE_CLIENT_ID` remains only an **optional** build-time fallback for running
the frontend without a backend (pure `npm run dev`); leave it unset in production.

The single image serves the built SPA at `/` and the API at `/api` from the **same origin**, so no reverse proxy or `/api` rewrite is needed. (If you ever serve the frontend separately, you'd proxy `/api/*` to the backend instead.)

## Authentication

- Every `/api/*` request requires a Google Bearer token, validated against Google `tokeninfo`. Access is restricted to **@breadfast.com** accounts **and** to tokens whose `aud` equals `GOOGLE_CLIENT_ID` (tokens minted for other apps are rejected).
- There is **no static-token bypass**. With `GOOGLE_CLIENT_ID` unset the API runs open (dev only) — never deploy without it.

## Run topology (important)

The backend keeps data **in-memory** (DuckDB over a Parquet cache) and runs a **single background refresh loop** with one DuckDB connection. Run it as a **single process / single worker**:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000   # one worker
```

Do **not** run multiple workers (`gunicorn -w N`) on one machine: each worker would load its own copy of the data (multiplying RAM) and refresh independently (drifting). To scale horizontally you'd need a shared cache/refresh service — out of scope today.

First boot with no Parquet cache pulls from BigQuery (a few minutes); subsequent boots rehydrate from the cache in seconds.

## Data freshness

The smart refresh checks the latest `modified` time across **both** source tables (pricing **and** competitor) and pulls only when **either** changed — so a competitor-only update is no longer missed. The "Synced X ago" badge reflects that combined timestamp.

## Docker image (recommended)

The app ships as a **single image** (multi-stage `Dockerfile`): the Vite SPA is
built and served by FastAPI alongside the API. CI (`.github/workflows/docker-image.yml`)
builds and pushes to **GHCR** on every push to `main` and on `v*` tags:

- `ghcr.io/muhammadgohary96/pricing-tool:latest` (main)
- `ghcr.io/muhammadgohary96/pricing-tool:<version>` (on `vX.Y.Z` tags) and `:sha-<commit>`

**CI needs no extra secrets** — `GITHUB_TOKEN` handles GHCR auth, and the frontend's
Google client id is supplied at runtime via `GOOGLE_CLIENT_ID` (see below), not baked
into the image.

### Run the container

```bash
docker run -p 8000:8000 \
  --env-file .env \                                   # backend env (DATA_SOURCE, BQ_*, GOOGLE_CLIENT_ID, CORS_ORIGINS…)
  -v /srv/pricing-cache:/app/cache \                  # persistent Parquet cache (survives restarts)
  -v /secrets/bq-sa.json:/keys/bq-sa.json:ro \        # BigQuery service-account key
  -e GOOGLE_APPLICATION_CREDENTIALS=/keys/bq-sa.json \
  ghcr.io/muhammadgohary96/pricing-tool:latest
```

App is then at `http://<host>:8000` (SPA + API). The container already runs a
**single uvicorn worker** — don't override the command to add workers (see Run
topology above). Mount the cache volume so the first-boot BigQuery pull isn't
repeated on every restart.

### Build locally

```bash
docker build --build-arg VITE_GOOGLE_CLIENT_ID=<client-id> -t pricing-tool .
```

## Manual (no Docker)

```bash
cd frontend && npm ci && npm run build      # outputs frontend/dist (FastAPI serves it)
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000   # one worker
```
