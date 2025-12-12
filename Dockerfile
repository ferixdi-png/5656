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
RUN npm ci --omit=dev --prefer-offline --no-audit

# Copy Python requirements
COPY requirements.txt ./

# Upgrade pip and install Python dependencies (with cache)
RUN pip3 install --upgrade pip setuptools wheel --break-system-packages --root-user-action=ignore && \
    pip3 install --break-system-packages --root-user-action=ignore -r requirements.txt

# Copy only necessary application files
COPY bot_kie.py run_bot.py index.js config.py translations.py kie_models.py kie_client.py knowledge_storage.py ./
COPY bot_kie_services ./bot_kie_services
COPY bot_kie_utils ./bot_kie_utils
# bot_kie_handlers is empty (handlers are in bot_kie.py), so we skip it
# COPY bot_kie_handlers ./bot_kie_handlers
COPY validate_*.py ./

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Ensure proper permissions
RUN chmod +x index.js || true

# Start the bot
CMD ["npm", "start"]
