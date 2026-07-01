# syntax=docker/dockerfile:1

# ── Stage 1: build the Vue/Vite frontend ───────────────────────────────────
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend

# Vite inlines env at build time, so the Google client id is a build arg.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID}

# Install deps first (cached until the lockfile changes).
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build          # → /app/frontend/dist


# ── Stage 2: python runtime that serves the API + the built SPA ─────────────
FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist

# Backend dependencies.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code + the built frontend from stage 1.
COPY backend/ ./backend/
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Writable cache dir for the Parquet cache (mount a volume here in production
# to persist across restarts) and a non-root user.
RUN mkdir -p /app/cache/pricing_data \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Single worker: the app holds data in-memory (DuckDB over Parquet) and runs one
# background-refresh loop — see PRODUCTION.md. Do not add workers here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/startup-status').status==200 else 1)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
