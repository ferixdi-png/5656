FROM node:24-slim

WORKDIR /app

# Install system dependencies
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for python command
RUN ln -s /usr/bin/python3 /usr/bin/python

# Copy package files first for better caching
COPY package*.json ./

# Install Node.js dependencies
RUN npm install --omit=dev

# Copy Python requirements
COPY requirements.txt ./

# Install Python dependencies
     RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy all application files
COPY . .

# Set environment variables
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

# Ensure proper permissions
RUN chmod +x index.js || true

# Start the bot
CMD ["npm", "start"]
