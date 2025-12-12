FROM node:24-slim

WORKDIR /app

# Install system dependencies (only essential)
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy package files first for better caching
COPY package*.json ./

# Install Node.js dependencies (only production)
# Use npm install if package-lock.json is not available (fallback)
RUN if [ -f package-lock.json ]; then \
        npm ci --omit=dev --prefer-offline --no-audit; \
    else \
        npm install --omit=dev --no-audit --prefer-offline; \
    fi

# Copy Python requirements
COPY requirements.txt ./

# Upgrade pip and install Python dependencies (with cache)
RUN pip3 install --upgrade pip setuptools wheel --break-system-packages --root-user-action=ignore && \
    pip3 install --break-system-packages --root-user-action=ignore -r requirements.txt

# Copy only necessary application files
COPY bot_kie.py run_bot.py index.js config.py translations.py kie_models.py kie_client.py knowledge_storage.py ./

# Create directories with empty __init__.py files
# Code has try/except for imports (line 117-123 in bot_kie.py), so it will work without these modules
# If you need these modules, ensure bot_kie_services/ and bot_kie_utils/ are committed to git
RUN mkdir -p ./bot_kie_services ./bot_kie_utils && \
    echo '"""Empty - modules not available in build context"""' > ./bot_kie_services/__init__.py && \
    echo '"""Empty - modules not available in build context"""' > ./bot_kie_utils/__init__.py

# NOTE: bot_kie_services and bot_kie_utils are not copied because they don't exist in build context
# The code will work without them due to try/except in bot_kie.py
# To enable these modules, commit the directories to git:
#   git add bot_kie_services/ bot_kie_utils/
#   git commit -m "Add bot_kie modules"
#   git push
# Then uncomment the COPY commands below:
# COPY bot_kie_services ./bot_kie_services
# COPY bot_kie_utils ./bot_kie_utils

# bot_kie_handlers is empty (handlers are in bot_kie.py), so we skip it

COPY validate_*.py ./

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Ensure proper permissions
RUN chmod +x index.js || true

# Expose port for health check
EXPOSE 10000

# Health check for Render.com
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD node -e "require('http').get('http://localhost:10000/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start the bot
CMD ["npm", "start"]
