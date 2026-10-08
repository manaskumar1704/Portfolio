# Multi-stage: uv resolves dependencies once in the builder, the runtime image
# carries no compiler and no uv cache. Render free builds from this on every
# push, so build minutes are worth not wasting.

FROM ghcr.io/astral-sh/uv:0.12 AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first. This layer only invalidates when pyproject.toml or
# uv.lock changes, so ordinary source pushes skip the resolve entirely.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Then the source.
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.12-slim

# One worker on purpose. Render free gives 0.1 CPU and 512 MB, and a tool loop
# plus an embedding model in one process is the memory ceiling. Scaling out
# means a per-IP limiter with shared state, which P6 does not need yet.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    OMP_NUM_THREADS=1

WORKDIR /app

COPY --from=builder /app /app

EXPOSE 8000

# Not /health. This endpoint does not touch the database, so Render's health
# check cannot hold Neon out of scale-to-zero.
HEALTHCHECK --interval=5min --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]