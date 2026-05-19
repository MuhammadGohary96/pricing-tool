import math
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.services import create_data_service, create_data_service_from_cache
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

    def _load_data():
        """Load data from cache or BigQuery."""
        try:
            cache = DataCache()
            cached_data = cache.load("pricing_data")

            if cached_data:
                # Cache hit! Load from cache (fast)
                logger.info("[Startup] Loading from cache...")
                app.state.startup_status["stage"] = "Loading from cache..."

                svc = create_data_service_from_cache(cached_data)
                app.state.data_service = svc
                app.state.startup_status = {
                    "ready": True,
                    "stage": "Ready (from cache)",
                    "progress": 1,
                    "total": 1,
                }
                logger.info("[Startup] App ready from cache in <5 seconds ✓")

                # Check if cache is stale → start background refresh
                if cache.is_stale("pricing_data"):
                    logger.info("[Startup] Cache is stale, starting background refresh...")

                    def _background_load_func(progress_callback=None):
                        """Background load function with progress callback."""
                        return create_data_service(startup_status={
                            "ready": False,
                            "stage": "Background refresh...",
                            "progress": 0,
                            "total": 0,
                            "progress_callback": progress_callback,
                        })

                    # Start background refresh (non-blocking)
                    app.state.background_loader.start_background_load(
                        _background_load_func,
                        on_complete=lambda svc: logger.info("[Background] Refresh complete, data updated"),
                        on_error=lambda err: logger.error(f"[Background] Refresh failed: {err}"),
                    )
                else:
                    logger.info("[Startup] Cache is fresh, no background refresh needed")

            else:
                # No cache, must load from BigQuery (first-time only)
                logger.info("[Startup] No cache found, loading from BigQuery (first time)...")
                app.state.startup_status["stage"] = "Loading from BigQuery..."

                svc = create_data_service(startup_status=app.state.startup_status)
                app.state.data_service = svc
                app.state.startup_status = {
                    "ready": True,
                    "stage": "Ready",
                    "progress": 1,
                    "total": 1,
                }
                logger.info("[Startup] App ready after initial load")

                # Save to cache for next time
                try:
                    cache_data = {
                        "_df": svc._df,
                        "_global_df": svc._global_df,
                    }
                    if hasattr(svc, "_competitor_df"):
                        cache_data["_competitor_df"] = svc._competitor_df

                    cache.save("pricing_data", cache_data)
                    logger.info("[Startup] Data cached successfully")
                except Exception as e:
                    logger.error(f"[Startup] Failed to cache data: {e}")

            logger.info(f"[Pricing API] Data source: {settings.DATA_SOURCE}")

        except Exception as e:
            app.state.startup_status["stage"] = f"Error: {e}"
            logger.error(f"[Pricing API] Startup error: {e}")
            import traceback
            traceback.print_exc()

    # Start data loading in background thread
    thread = threading.Thread(target=_load_data, daemon=True, name="startup-loader")
    thread.start()

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
    if not request.app.state.startup_status["ready"] and path.startswith("/api/") and path not in ("/api/startup-status", "/api/reload"):
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


@app.get("/api/background-status")
def get_background_status(request: Request):
    """Get background data loading status."""
    if hasattr(request.app.state, "background_loader"):
        return request.app.state.background_loader.get_progress()
    return {"loading": False, "stage": "No background loader"}


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
