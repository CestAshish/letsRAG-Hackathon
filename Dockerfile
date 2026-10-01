# ---- Backend (Python / FastAPI) ----
FROM python:3.12-slim AS backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 1. CPU-only torch first (skips ~5GB of NVIDIA/CUDA junk)
# 2. Then sync the rest of the deps
COPY pyproject.toml uv.lock ./
RUN uv venv && \
    uv pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    uv sync --no-dev

# Playwright Chromium + all its system deps
RUN uv run playwright install --with-deps chromium

COPY app/ ./app/

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]


# ---- Frontend (React / Vite) ----
FROM node:20-slim AS frontend

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
