# ShiftLoop backend: the API, the WebSocket and the ML models. The dashboard is hosted separately
# (build it with VITE_API_URL pointing at this service).
# Build context is the repository root:  docker build -t shiftloop .
# Run locally:                           docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... shiftloop

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

ENV PATH="/app/backend/.venv/bin:$PATH"

# run as a non-root user; the app only reads /app, so the files can stay owned by root
RUN useradd --create-home --uid 1000 shiftloop
USER shiftloop

EXPOSE 8000
# Render sets $PORT; locally it defaults to 8000
CMD ["sh", "-c", "exec uvicorn shiftloop.api.app:make_default --factory --host 0.0.0.0 --port ${PORT:-8000}"]
