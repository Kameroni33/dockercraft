# dockercraft manager (FastAPI + built Vue UI)

# Stage 1: build the web UI (so hosts don't need node)
FROM node:22-alpine AS web
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

# Stage 2: the manager
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY api ./api
RUN pip install --no-cache-dir .

# MC image build context (ensure_image builds per-Java-major tags on demand)
COPY images ./images
COPY --from=web /build/dist ./web/dist

# Runs with network_mode: host (see compose.yml): reaches host-bound RCON
# ports, detects the real LAN IP, and serves on host port 8080 directly.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
