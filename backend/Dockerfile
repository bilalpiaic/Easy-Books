FROM python:3.12-slim

# Install uv from its official image (no pip download, no PATH hacks)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# WeasyPrint needs Pango/Cairo (and friends) at runtime — without these,
# Save PDF returns HTTP 503 "PDF engine unavailable… (import failed: OSError)".
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (own layer → cache-friendly on code changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --frozen

# Application code
COPY . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Health-check via the unauthenticated /api/version endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
  CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/version')" \
  || exit 1

EXPOSE 8000
ENTRYPOINT ["/docker-entrypoint.sh"]
