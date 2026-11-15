# 1) Build the Svelte frontend
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# 2) Python server that also serves web/dist
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ src/
RUN uv sync --frozen --no-dev
COPY --from=web /web/dist web/dist
ENV PORT=8000 CUNO_STATIC_DIR=/app/web/dist
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "cuno"]
