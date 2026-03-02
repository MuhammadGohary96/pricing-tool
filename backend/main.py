import math
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.services import create_data_service
from backend.auth import google_auth_middleware
from backend.routers import health, filters, commercial, master_data, executive


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
    app.state.data_source = settings.DATA_SOURCE
    app.state.startup_status = {
        "ready": False,
        "stage": "Initializing...",
        "progress": 0,
        "total": 0,
    }
    app.state.enrichment_status = {
        "done": False,
        "progress": 0,
        "total": 0,
        "error": None,
    }
    app.state.data_service = None

    def _load_data():
        try:
            # Skip catalog enrichment — BQ data only (fast ~10s)
            svc = create_data_service(startup_status=app.state.startup_status)
            app.state.data_service = svc
            app.state.startup_status["ready"] = True
            app.state.startup_status["stage"] = "Ready"
            print(f"[Pricing API] Data source: {settings.DATA_SOURCE}")
        except Exception as e:
            app.state.startup_status["stage"] = f"Error: {e}"
            print(f"[Pricing API] Startup error: {e}")

    thread = threading.Thread(target=_load_data, daemon=True)
    thread.start()
    yield


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
