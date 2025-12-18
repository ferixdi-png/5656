# Используем Python образ вместо Node.js
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (essential + OCR support)
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements first for better caching
COPY requirements.txt ./

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy only necessary application files
COPY bot_kie.py run_bot.py config.py translations.py kie_models.py kie_client.py kie_gateway.py knowledge_storage.py config_runtime.py helpers.py ./

# Copy validation files if they exist
COPY validate_*.py ./

# Create directories with empty __init__.py files
# Code has try/except for imports, so it will work without these modules
RUN mkdir -p ./bot_kie_services ./bot_kie_utils && \
    echo '"""Empty - modules not available in build context"""' > ./bot_kie_services/__init__.py && \
    echo '"""Empty - modules not available in build context"""' > ./bot_kie_utils/__init__.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV DATA_DIR=/app/data
ENV PYTHONPATH=/app

# Create data directory for persistent storage
RUN mkdir -p /app/data && chmod 755 /app/data

# Expose port for health check
EXPOSE 10000

# Health check for Render.com (using Python instead of Node.js)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:10000/health').read()" || exit 1

# Start the bot using Python (NOT npm!)
CMD ["python3", "bot_kie.py"]
