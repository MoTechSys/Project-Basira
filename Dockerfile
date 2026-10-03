# syntax=docker/dockerfile:1.7
# Basira — single image: FastAPI backend + built React frontend + prebuilt index snapshot.
# Cold start ≈ 2 s, RSS ≈ 300 MB. Runs offline by default (LLM_PROVIDER=mock).

# ---------- 1) frontend ----------
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# brand assets already live in frontend/public/brand (copied with frontend/ above)
RUN npm run build

# ---------- 2) backend deps ----------
FROM python:3.12-slim AS py
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY backend/pyproject.toml backend/
RUN pip install --no-cache-dir "./backend[mcp]"

# ---------- 3) corpus + index + snapshot (cached layer; re-runs only if manifest changes) ----------
FROM py AS index
COPY corpus/ corpus/
COPY backend/app/ backend/app/
RUN python corpus/fetch.py && python corpus/build_index.py \
 && PYTHONPATH=backend python -c "from pathlib import Path; from app.snapshot import load_or_build; load_or_build(Path('corpus/index'))" \
 && rm -rf corpus/data

# ---------- 4) runtime ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    BASIRA_INDEX_DIR=/app/corpus/index BASIRA_MANIFEST=/app/corpus/manifest.json \
    BASIRA_MESSAGES_DIR=/app/messages BASIRA_STATIC_DIR=/app/frontend/dist \
    BASIRA_SNAPSHOT_WRITE=0 LLM_PROVIDER=mock VISION_PROVIDER=mock PORT=8000 \
    BASIRA_MCP=1 BASIRA_MODEL_CONFIG=/data/model.json
RUN useradd -r -u 10001 basira && mkdir -p /data && chown basira:basira /data
VOLUME ["/data"]
WORKDIR /app
COPY --from=py /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=py /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=index /app/corpus/index corpus/index
COPY --from=index /app/corpus/manifest.json /app/corpus/surah_names.json corpus/
COPY --from=web /web/dist frontend/dist
COPY backend/app backend/app
COPY messages messages
COPY LICENSE SOURCES.md THIRD_PARTY_NOTICES.md AI_USAGE.md SAFETY.md ./
# /data holds the operator's model configuration written once from /settings (E-051); the rest of the FS is read-only.
USER basira
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4).status==200 else 1)"
WORKDIR /app/backend
# B12: X-Forwarded-For is trusted only from known proxies. uvicorn reads FORWARDED_ALLOW_IPS (default 127.0.0.1);
# set it AND BASIRA_TRUSTED_PROXIES to the load balancer's address/CIDR at deploy time — never '*'.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level warning --proxy-headers"]
