# Multi-stage: uv resolves dependencies once in the builder, the runtime image
# carries no compiler and no uv cache. Render free builds from this on every
# push, so build minutes are worth not wasting.

# The `-python3.12-bookworm-slim` variant, not the default. The default uv
# image is distroless and has no /bin/sh, so every RUN line fails at container
# init. The slim variant is the same Debian base as the runtime stage, so the
# wheels resolve and link identically.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

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

# Bake the embedding model into the image. Without this, the first request after a
# cold start downloads ~67 MB from Hugging Face while the visitor watches a
# spinner — and Render free spins down after 15 idle minutes, so that is most
# first requests. The download happens here instead, once, on the builder's clock.
#
# It sits before the COPY on purpose. After the COPY, a one-line source edit
# invalidated the layer and re-downloaded 67 MB on every push.
#
# Run through the project venv: `python` on the builder's PATH is the system
# interpreter, so a bare `python -c` fails with ModuleNotFoundError for every
# dependency in the project.
#
# FASTEMBED_CACHE_PATH is the mechanism, not a TextEmbedding argument. fastembed
# 0.9 takes `cache_dir`; the env var is read by the library itself, so the
# download lands where the runtime stage will look for it. Setting it in the
# builder is what makes the cache portable across the two stages.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
RUN --mount=type=cache,target=/root/.cache/uv \
    /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"

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
    OMP_NUM_THREADS=1 \
    FASTEMBED_CACHE_PATH=/app/.fastembed_cache

WORKDIR /app

COPY --from=builder /app /app

# The baked model cache, readable by the unprivileged user the app runs as. Done
# after the COPY because the cache is created by the layer above.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app/.fastembed_cache
USER appuser

EXPOSE 8000

# Not /health. This endpoint does not touch the database, so Render's health
# check cannot hold Neon out of scale-to-zero.
HEALTHCHECK --interval=300s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# Shell-wrapped the CMD. Render free has no preDeployCommand, so migrations
# must run in the container's entrypoint before the server — through a shell,
# because the `&&` is shell syntax: Render's dockerCommand override invoked the
# string directly without one, and alembic choked on `&& uvicorn ...` as its
# own arguments. `exec` hands the PID to uvicorn once migrations are done.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]