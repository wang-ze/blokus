# Blokus Arena in one container: the web app (frontend/) and the game engine (backend/).
# scripts/start_mac.sh and scripts/start_pc.ps1 build and run it locally, and a Hugging Face
# Docker Space builds it from this file as well.

ARG PYTHON_VERSION=3.13

# Build: install the locked dependencies into /app/.venv. The environment holds no project code,
# so its layer is reused until the dependencies change, and a code change only recopies the source.
FROM python:${PYTHON_VERSION}-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.2 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
COPY frontend/pyproject.toml frontend/
RUN uv sync --locked --no-dev --no-install-workspace

# Run: Python, the environment and the source, without uv.
FROM python:${PYTHON_VERSION}-slim
LABEL org.opencontainers.image.title="blokus-arena"
# Hugging Face Spaces run containers as user 1000. Game history goes to /data, where the start
# scripts mount the repository's data/ folder and a Space mounts a Storage Bucket.
RUN useradd --create-home --uid 1000 user \
    && mkdir /data \
    && chown user /data
COPY --from=build /app/.venv /app/.venv
COPY backend/src /app/backend/src
COPY frontend/src /app/frontend/src
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend/src:/app/frontend/src \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    BLOKUS_DATA_DIR=/data
USER user
# API keys come from the environment, or from a .env file mounted at /app/.env.
WORKDIR /app
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=4)"]
# Python ignores SIGTERM when it runs as process 1, so `docker stop` sends SIGINT instead.
STOPSIGNAL SIGINT
CMD ["python", "-m", "blokus_ui"]
