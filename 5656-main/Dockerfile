# Production Dockerfile for Render (MAXIMUM OPTIMIZATION)
# Uses multi-stage build, BuildKit cache mounts, and layer optimization

# ============================================================================
# STAGE 1: Builder - Install dependencies and compile native extensions
# ============================================================================
FROM python:3.11-slim as builder

# Suppress debconf warnings and apt-get output
ENV DEBIAN_FRONTEND=noninteractive
ENV APT_LISTCHANGES_FRONTEND=none
ENV APT_OPTIONS="-o Dpkg::Options::=--force-confold -o Dpkg::Options::=--force-confdef"
# Disable pip version check and warnings (saves time, cleaner logs)
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install build dependencies (only for compilation)
# Suppress warnings: DEBIAN_FRONTEND=noninteractive, apt-get -qq (quiet)
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean -qq

# Copy only requirements first (for better caching)
COPY requirements-prod.txt ./requirements.txt

# Install Python dependencies with BuildKit cache mount
# Cache mount persists pip cache between builds (HUGE speedup!)
# Suppress all warnings: --quiet, --root-user-action=ignore, redirect to /dev/null
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade --no-cache-dir --quiet --root-user-action=ignore pip setuptools wheel >/dev/null 2>&1 && \
    pip install --no-cache-dir --no-warn-script-location --quiet --root-user-action=ignore -r requirements.txt >/dev/null 2>&1

# ============================================================================
# STAGE 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.11-slim as runtime

# Suppress debconf warnings
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV DATA_DIR=/app/data
ENV PYTHONPATH=/app

WORKDIR /app

# Install ONLY runtime dependencies (no build tools!)
# This significantly reduces image size
# Suppress warnings: -qq (quiet), DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
    # Runtime libraries for PostgreSQL (psycopg2, asyncpg)
    libpq5 \
    # OCR support (if needed)
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    # Cleanup in same layer to reduce image size
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean -qq \
    && apt-get autoremove -y -qq

# Copy ONLY installed packages from builder (not build tools!)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files (after dependencies for better caching)
COPY . /app

# Safety: remove vendored packages and create missing directories (combined)
RUN rm -rf /app/aiogram || true && \
    mkdir -p ./bot_kie_services ./bot_kie_utils /app/data && \
    (test -f ./bot_kie_services/__init__.py || echo '"""Empty - modules not available in build context"""' > ./bot_kie_services/__init__.py) && \
    (test -f ./bot_kie_utils/__init__.py || echo '"""Empty - modules not available in build context"""' > ./bot_kie_utils/__init__.py) && \
    chmod 755 /app/data

# Verify critical files and imports (optimized single command)
RUN test -f /app/models/kie_models.yaml && \
    test -f /app/app/config.py && \
    python3 -c "import yaml, aiogram; from app.config import get_settings" && \
    echo "✅ Critical files verified"

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import os, urllib.request; port = os.environ.get('PORT', '10000'); urllib.request.urlopen(f'http://localhost:{port}/health').read()" || exit 1

# Start command
CMD ["python3", "main_render.py"]
