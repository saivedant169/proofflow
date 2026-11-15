FROM node:24-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY evidence/benchmark_summary.json /build/evidence/benchmark_summary.json
COPY evidence/agent_composition.json /build/evidence/agent_composition.json
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PROOFFLOW_STATIC_DIR=/app/frontend/dist \
    PROOFFLOW_STATE_DIR=/data/sessions
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.1@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY proofflow/ ./proofflow/
RUN uv sync --frozen --no-dev --no-editable && \
    groupadd --gid 10001 proofflow && useradd --uid 10001 --gid 10001 --no-create-home proofflow && \
    mkdir -p /data/sessions && chown -R 10001:10001 /data
COPY --from=frontend /build/frontend/dist /app/frontend/dist
COPY video/proofflow-walkthrough.mp4 /app/frontend/dist/walkthrough.mp4
COPY video/poster.jpg /app/frontend/dist/walkthrough-poster.jpg
COPY evidence/benchmark_summary.json /app/evidence/benchmark_summary.json
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["/app/.venv/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=8)"]
CMD ["/app/.venv/bin/uvicorn", "proofflow.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
