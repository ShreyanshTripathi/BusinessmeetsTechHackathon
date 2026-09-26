# ShiftLoop: one container serving the API, the WebSocket and the built dashboard.
# Build context is the repository root:  docker build -t shiftloop .
# Run locally:                           docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... shiftloop

# ---------------------------------------------------------------- 1. build the dashboard
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------- 2. backend, ML models, dashboard
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# dependencies first, so code changes don't reinstall them
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

# trained random forests + the code that loads and explains them (ml_bridge looks in /app/ml)
COPY ml/*.py /app/ml/
COPY ml/models /app/ml/models

COPY --from=frontend /app/frontend/dist /app/frontend/dist

ENV PATH="/app/backend/.venv/bin:$PATH" \
    SHIFTLOOP_STATIC_DIR=/app/frontend/dist

# run as a non-root user; the app only reads /app, so the files can stay owned by root
RUN useradd --create-home --uid 1000 shiftloop
USER shiftloop

EXPOSE 8000
# Render sets $PORT; locally it defaults to 8000
CMD ["sh", "-c", "exec uvicorn shiftloop.api.app:make_default --factory --host 0.0.0.0 --port ${PORT:-8000}"]
