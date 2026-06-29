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

## Required environment variables (frontend)

| Variable | Required | Notes |
|---|---|---|
| `VITE_GOOGLE_CLIENT_ID` | **yes** | Same client id as the backend's `GOOGLE_CLIENT_ID`. Set at build time. |

The frontend calls the API at the relative path `/api`, so serve it behind a reverse proxy that routes `/api/*` to the backend (same origin), or add a rewrite.

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

## Build

```bash
# frontend
cd frontend && npm ci && npm run build      # outputs dist/

# backend
pip install -r backend/requirements.txt
```
