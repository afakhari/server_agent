# Staging-only, single-operator image. No credentials or sources of target apps baked in.
FROM node:22-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 --home /nonexistent --shell /usr/sbin/nologin sentinel \
    && mkdir /data && chown 10001:10001 /data
COPY app.py ./
COPY sentinel/ ./sentinel/
COPY static/ ./static/
COPY examples/ ./examples/
COPY --from=frontend-build /build/frontend/dist/ ./frontend/dist/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8000","--workers","1","--no-proxy-headers","--no-access-log"]
