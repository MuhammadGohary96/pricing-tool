import math
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from pathlib import Path

from backend.config import settings
from backend.services import (
    create_data_service,
    create_data_service_from_cache,
    create_data_service_from_parquet,
    save_parquet_cache,
)
from backend.services import parquet_cache as pc
from backend.services.cache_service import DataCache
from backend.services.background_loader import BackgroundDataLoader
from backend.auth import google_auth_middleware
from backend.routers import health, filters, commercial, master_data, executive, competitor_products
import logging

logger = logging.getLogger(__name__)


def _sanitize_nan(obj):
    """Recursively replace NaN/Inf floats with None for JSON compliance."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_nan(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    def render(self, content):
        return super().render(_sanitize_nan(content))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifecycle with zero-downtime cache-first loading.

    Flow:
    1. Try to load from cache (5 seconds) → app ready immediately
    2. If cache stale, start background refresh (non-blocking)
    3. If no cache, must load from BigQuery (first-time only)
    """
    app.state.data_source = settings.DATA_SOURCE
    app.state.startup_status = {
        "ready": False,
        "stage": "Checking cache...",
        "progress": 0,
        "total": 0,
    }
    app.state.enrichment_status = {
        "done": False,
        "progress": 0,
        "total": 0,
        "error": None,
        "in_progress": False,
    }
    app.state.data_service = None
    app.state.background_loader = BackgroundDataLoader(app.state)

    def _background_load_func(progress_callback=None):
        """Fetch fresh data from BigQuery and persist the Parquet cache."""
        svc = create_data_service(startup_status={
            "ready": False,
            "stage": "Background refresh...",
            "progress": 0,
            "total": 0,
            "progress_callback": progress_callback,
        })
        # Rewrite the fp-grain Parquet so DuckDB queries the refreshed data,
        # then persist the full Parquet cache. Done BEFORE returning so the
        # hot-swap is consistent.
        if hasattr(svc, "refresh_parquet"):
            try:
                svc.refresh_parquet()
            except Exception as exc:
                logger.error(f"[Background] refresh_parquet failed: {exc}")
        try:
            save_parquet_cache(svc)
            logger.info("[Background] Parquet cache saved")
        except Exception as exc:
            logger.error(f"[Background] save_parquet_cache failed: {exc}")
        return svc

    def _start_background_refresh():
        app.state.background_loader.start_background_load(
            _background_load_func,
            on_complete=lambda svc: logger.info("[Background] Refresh complete, data updated"),
            on_error=lambda err: logger.error(f"[Background] Refresh failed: {err}"),
        )

    # Expose for the manual non-blocking trigger endpoint.
    app.state.start_background_refresh = _start_background_refresh

    def _aware(iso):
        from datetime import datetime
        if not iso:
            return None
        try:
            dt = datetime.fromisoformat(iso)
            return dt.astimezone() if dt.tzinfo is None else dt
        except Exception:
            return None

    def _check_and_refresh():
        """Smart freshness check (shared by the ↻ button and the hourly loop):
        compare the latest last-modified across BOTH source tables (pricing +
        competitor) to our baseline and pull ONLY when either changed. On
        no-change, just record that we verified (last_checked_at). Never
        downloads unless something changed. Returns an outcome dict."""
        from datetime import datetime
        loader = app.state.background_loader
        if loader.is_loading():
            return {"ok": True, "status": "refreshing", "changed": None}
        svc = app.state.data_service
        if svc is None or getattr(svc, "_client", None) is None:
            return {"ok": False, "status": "not_ready"}
        fp_path = Path(settings.DUCKDB_PARQUET_PATH)
        # Latest modified across BOTH source tables (pricing + competitor); a
        # change in either must trigger a pull.
        from backend.services import latest_bq_modified
        modified = latest_bq_modified(svc._client)
        if modified is None:
            logger.error("[Check] Could not read BQ table metadata for either source table")
            return {"ok": False, "status": "error", "message": "Could not read BQ table metadata"}

        state = pc.read_sync_state(fp_path.parent)
        baseline = _aware(state.get("bq_table_modified")) if state else None
        if baseline is None:
            meta = pc.get_metadata(fp_path)
            baseline = _aware(meta.get("written_at")) if meta else None

        changed = baseline is None or (modified is not None and modified > baseline)
        if changed:
            logger.info("[Check] BQ table changed → starting background pull")
            _start_background_refresh()
            return {"ok": True, "status": "refreshing", "changed": True}
        # No change — record the verification (advances last_checked_at only).
        pc.touch_last_checked(fp_path.parent, datetime.now().isoformat())
        logger.info("[Check] BQ table unchanged → data confirmed current")
        return {"ok": True, "status": "up_to_date", "changed": False}

    app.state.check_and_refresh = _check_and_refresh

    def _load_data():
        """Load data: Parquet cache → legacy pickle → fresh BigQuery."""
        try:
            fp_path = Path(settings.DUCKDB_PARQUET_PATH)

            # 1) Preferred: Parquet-only cache (no multi-GB pickle).
            if settings.USE_PARQUET_CACHE and pc.exists(fp_path):
                logger.info("[Startup] Loading from Parquet cache...")
                app.state.startup_status["stage"] = "Loading from cache..."
                svc = create_data_service_from_parquet()
                if svc is not None:
                    app.state.data_service = svc
                    app.state.startup_status = {
                        "ready": True, "stage": "Ready (from cache)", "progress": 1, "total": 1,
                    }
                    logger.info("[Startup] App ready from Parquet cache ✓")
                    age = pc.data_age_hours(fp_path)
                    if age is None or age > 24:
                        logger.info(
                            f"[Startup] Data is {age:.1f}h old (>24h), starting background refresh..."
                            if age is not None else "[Startup] Data age unknown, starting background refresh..."
                        )
                        _start_background_refresh()
                    else:
                        logger.info(f"[Startup] Data is {age:.1f}h old (fresh), no background refresh needed")
                    logger.info(f"[Pricing API] Data source: {settings.DATA_SOURCE}")
                    return

            # 2) Legacy fallback: pickle cache (one-time, until next refresh
            #    writes the Parquet cache).
            cache = DataCache()
            cached_data = cache.load("pricing_data")
            if cached_data:
                logger.info("[Startup] Loading from legacy pickle cache...")
                app.state.startup_status["stage"] = "Loading from cache..."
                svc = create_data_service_from_cache(cached_data)
                app.state.data_service = svc
                app.state.startup_status = {
                    "ready": True, "stage": "Ready (from cache)", "progress": 1, "total": 1,
                }
                logger.info("[Startup] App ready from pickle cache ✓")
                # Always refresh in background to materialize the Parquet cache.
                logger.info("[Startup] Starting background refresh to build Parquet cache...")
                _start_background_refresh()
                logger.info(f"[Pricing API] Data source: {settings.DATA_SOURCE}")
                return

            # 3) Cold start: load from BigQuery and write the Parquet cache.
            logger.info("[Startup] No cache found, loading from BigQuery (first time)...")
            app.state.startup_status["stage"] = "Loading from BigQuery..."
            svc = create_data_service(startup_status=app.state.startup_status)
            app.state.data_service = svc
            app.state.startup_status = {
                "ready": True, "stage": "Ready", "progress": 1, "total": 1,
            }
            logger.info("[Startup] App ready after initial load")
            try:
                save_parquet_cache(svc)
                logger.info("[Startup] Parquet cache saved")
            except Exception as e:
                logger.error(f"[Startup] Failed to save Parquet cache: {e}")
            logger.info(f"[Pricing API] Data source: {settings.DATA_SOURCE}")

        except Exception as e:
            app.state.startup_status["stage"] = f"Error: {e}"
            logger.error(f"[Pricing API] Startup error: {e}")
            import traceback
            traceback.print_exc()

    # Start data loading in background thread
    thread = threading.Thread(target=_load_data, daemon=True, name="startup-loader")
    thread.start()

    def _auto_refresh_loop():
        """Run one smart check as soon as the data service is ready (so the
        "last checked" badge is current right after a deploy/restart), then
        re-check every REFRESH_INTERVAL_SECONDS. Smart = pull only when the BQ
        table changed; otherwise just record the no-change verification."""
        import time as _time
        # Data loads in a separate background thread; wait until the service
        # (with its BQ client) is up before the first check, else it no-ops.
        waited = 0
        while waited < 600:
            svc = app.state.data_service
            if svc is not None and getattr(svc, "_client", None) is not None:
                break
            _time.sleep(5)
            waited += 5
        while True:
            if settings.AUTO_REFRESH_ENABLED:
                try:
                    _check_and_refresh()
                except Exception as e:
                    logger.error(f"[AutoRefresh] loop error: {e}")
            _time.sleep(settings.REFRESH_INTERVAL_SECONDS)

    if settings.AUTO_REFRESH_ENABLED:
        threading.Thread(target=_auto_refresh_loop, daemon=True, name="auto-refresh").start()
        logger.info(
            f"[AutoRefresh] Enabled — checking every {settings.REFRESH_INTERVAL_SECONDS}s (smart: pull only on change)"
        )

    yield  # App is running

    # Cleanup (if needed)
    logger.info("[Shutdown] Pricing API shutting down")


app = FastAPI(
    title="Breadfast Pricing Tool API",
    version="0.1.0",
    lifespan=lifespan,
    default_response_class=SafeJSONResponse,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def startup_guard(request: Request, call_next):
    """Return 503 for data endpoints while startup is in progress."""
    path = request.url.path
    if not request.app.state.startup_status["ready"] and path.startswith("/api/") and path not in ("/api/startup-status", "/api/config", "/api/reload", "/api/data-status", "/api/background-status"):
        return JSONResponse(
            status_code=503,
            content=request.app.state.startup_status,
        )
    return await call_next(request)


# Google OAuth middleware — runs after startup guard, before route handlers
app.middleware("http")(google_auth_middleware)


@app.get("/api/startup-status")
def get_startup_status(request: Request):
    status = dict(request.app.state.startup_status)
    status["enrichment"] = request.app.state.enrichment_status
    return status


@app.get("/api/config")
def get_config():
    """Public runtime config for the SPA. The frontend reads GOOGLE_CLIENT_ID
    from here at load time, so it's driven by the server env the production
    engineer sets — no build-time bake, no CI secret. The OAuth client id is
    public by design (it ships in the OAuth flow either way)."""
    return {"google_client_id": settings.GOOGLE_CLIENT_ID}


@app.get("/api/background-status")
def get_background_status(request: Request):
    """Get background data loading status."""
    if hasattr(request.app.state, "background_loader"):
        return request.app.state.background_loader.get_progress()
    return {"loading": False, "stage": "No background loader"}


@app.get("/api/data-status")
def get_data_status(request: Request):
    """Data freshness for the UI.

    - last_checked_at: last time freshness was verified (a pull OR a no-change
      check). This is what the header badge counts from ("Synced N ago").
    - data_synced_at:  when the data itself was last pulled/changed (tooltip;
      also the trigger the UI uses to refetch the view in place).
    """
    from datetime import datetime
    from backend.services import parquet_cache as pc

    fp_path = Path(settings.DUCKDB_PARQUET_PATH)
    state = pc.read_sync_state(fp_path.parent) or {}
    data_synced_at = state.get("synced_at")
    if not data_synced_at:
        meta = pc.get_metadata(fp_path)  # pre-marker fallback
        data_synced_at = meta.get("written_at") if meta else None
    last_checked_at = state.get("last_checked_at") or data_synced_at

    age_minutes = None
    if last_checked_at:
        try:
            age_minutes = round((datetime.now() - datetime.fromisoformat(last_checked_at)).total_seconds() / 60, 1)
        except Exception:
            age_minutes = None

    loader = getattr(request.app.state, "background_loader", None)
    progress = loader.get_progress() if loader else {}
    refreshing = bool(progress.get("loading"))
    return {
        "last_checked_at": last_checked_at,
        "data_synced_at": data_synced_at,
        "age_minutes": age_minutes,
        "refreshing": refreshing,
        "refresh_stage": progress.get("stage") if refreshing else None,
        "refresh_percent": progress.get("percent") if refreshing else None,
        "auto_refresh_enabled": settings.AUTO_REFRESH_ENABLED,
        "refresh_interval_seconds": settings.REFRESH_INTERVAL_SECONDS,
    }


@app.post("/api/refresh-now")
def refresh_now(request: Request):
    """Smart "check for new data" (the ↻ button). Pulls in the background ONLY
    if the BQ table changed since our last sync; otherwise records a no-change
    verification. Never does an unconditional/blocking reload."""
    checker = getattr(request.app.state, "check_and_refresh", None)
    if checker is None:
        return {"ok": False, "status": "not_ready"}
    return checker()


@app.post("/api/reload")
def reload_data(request: Request):
    """Trigger a full data reload from BigQuery."""
    if not request.app.state.startup_status["ready"]:
        return {"ok": False, "message": "Already reloading"}

    request.app.state.startup_status.update({
        "ready": False,
        "stage": "Reloading data...",
        "progress": 0,
        "total": 0,
    })
    request.app.state.enrichment_status.update({
        "done": False,
        "progress": 0,
        "total": 0,
        "error": None,
        "in_progress": False,
    })

    def _reload():
        try:
            svc = create_data_service(startup_status=request.app.state.startup_status)
            request.app.state.data_service = svc
            request.app.state.startup_status["ready"] = True
            request.app.state.startup_status["stage"] = "Ready"
            try:
                save_parquet_cache(svc)
                logger.info("[Reload] Parquet cache saved")
            except Exception as exc:
                logger.error(f"[Reload] save_parquet_cache failed: {exc}")
            print(f"[Pricing API] Data reloaded: {settings.DATA_SOURCE}")
        except Exception as e:
            request.app.state.startup_status["stage"] = f"Error: {e}"
            print(f"[Pricing API] Reload error: {e}")

    thread = threading.Thread(target=_reload, daemon=True)
    thread.start()
    return {"ok": True, "reloading": True}


app.include_router(health.router)
app.include_router(filters.router)
app.include_router(commercial.router)
app.include_router(master_data.router)
app.include_router(executive.router)
app.include_router(competitor_products.router)


# ── Serve the built frontend (single-image deploy) ─────────────────────────
# When a Vite build is present (the Docker image copies it here), FastAPI serves
# the SPA at "/" and the API stays at "/api". Registered AFTER the routers so
# "/api/*" always wins; skipped entirely in local dev (no dist → `npm run dev`
# + Vite proxy handles the frontend). SPA uses history routing, so unknown
# non-API paths fall back to index.html.
_DIST_DIR = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parent.parent / "frontend" / "dist"))

if (_DIST_DIR / "index.html").is_file():
    _INDEX = _DIST_DIR / "index.html"
    if (_DIST_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def _serve_spa(full_path: str):
        # Known /api/* routes matched above; an UNKNOWN /api path is a real 404,
        # not the SPA shell.
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse(status_code=404, content={"error": "Not found"})
        candidate = (_DIST_DIR / full_path)
        if full_path and candidate.is_file() and _DIST_DIR in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(_INDEX)  # SPA deep-link fallback (history routing)

    logger.info(f"[Startup] Serving frontend from {_DIST_DIR}")
else:
    logger.info("[Startup] No frontend build found — API only (dev mode uses Vite)")
