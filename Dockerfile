# syntax=docker/dockerfile:1.6
#
# Single-image build for Seelenruh: React+Vite client + FastAPI server.
# The client is built once and served as static assets by FastAPI from
# /static. Default port is 5000.
#
# Build:
#   docker build -t seelenruh .
# Run:
#   docker run -p 5000:5000 --env-file server/.env seelenruh

# ----- Stage 1: build the React client -----
FROM node:20-alpine AS client-build
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# ----- Stage 2: server runtime -----
FROM python:3.10-slim AS runtime

# Sentence-transformers + faiss need a C toolchain at install time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libgomp1 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/server

COPY server/requirements.txt ./
# Install torch first from the CPU-only PyTorch wheel index to avoid
# pulling the ~1.2 GB of NVIDIA CUDA libraries that the default torch
# wheel ships with. The container runs CPU-only so those libs are dead
# weight. This drops the final image from ~4 GB to ~1.5 GB.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
       torch==2.5.1 \
 && pip install --no-cache-dir -r requirements.txt

# Server source + the pre-built client bundle.
COPY server/ ./
COPY --from=client-build /app/client/dist /app/client/dist

# Hugging Face Spaces runs containers as UID 1000, not root. Create that
# user, point HF caches at a writable path under /app, and chown everything.
# This change is harmless when running locally as root.
ENV HF_HOME=/app/server/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/server/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/server/.cache/huggingface \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN useradd -m -u 1000 user \
 && mkdir -p /app/server/.cache/huggingface /app/server/rag/.cache \
 && chown -R user:user /app
USER user

VOLUME ["/app/server/.cache/huggingface", "/app/server/rag/.cache"]

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=5 \
  CMD curl -fsS http://localhost:${PORT:-7860}/api/health || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --log-level warning"]
