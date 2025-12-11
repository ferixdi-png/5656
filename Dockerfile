FROM node:24-slim

WORKDIR /app

# Install system dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    curl \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libtiff5-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tesseract-ocr \
    tesseract-ocr-rus \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy package files first for better caching
COPY package*.json ./

# Install Node.js dependencies
RUN npm ci --omit=dev

# Copy Python requirements
COPY requirements.txt ./

# Upgrade pip and install Python dependencies
# Using --break-system-packages is safe in Docker containers (isolated environment)
RUN pip3 install --upgrade pip setuptools wheel --break-system-packages --root-user-action=ignore && \
    pip3 install --no-cache-dir --break-system-packages --root-user-action=ignore -r requirements.txt

# Copy Python files explicitly to ensure critical modules are included
COPY bot_kie.py run_bot.py translations.py kie_client.py kie_models.py knowledge_storage.py ./

# Copy all other application files
COPY . .

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Ensure proper permissions
RUN chmod +x index.js || true

# Start the bot
CMD ["npm", "start"]
