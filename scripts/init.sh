#!/bin/bash

set -e

echo "Initializing Dockercraft..."

# Create directory structure
mkdir -p data/instances/survival
mkdir -p data/backups/survival
mkdir -p data/logs/survival

# Copy .env.example to .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file - please update RCON_PASSWORD!"
fi

# Generate random RCON password if still default
if grep -q "RCON_PASSWORD=changeme123" .env; then
    NEW_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    sed -i "s/RCON_PASSWORD=changeme123/RCON_PASSWORD=$NEW_PASSWORD/" .env
    echo "Generated secure RCON password"
fi

echo "Checking for server.jar..."
if [ ! -f "data/instances/survival/server.jar" ]; then
    echo "No server.jar found. Please download your preferred server jar and place it in:"
    echo "  data/instances/survival/server.jar"
    echo ""
    echo "Suggested sources:"
    echo "  - Paper: https://papermc.io/downloads"
    echo "  - Vanilla: https://www.minecraft.net/en-us/download/server"
    echo "  - Fabric: https://fabricmc.net/use/server/"
fi

# Build and start services
echo "Building Docker containers..."
docker-compose build

echo ""
echo "Setup complete! Next steps:"
echo "  1. Download server.jar to data/instances/survival/"
echo "  2. Run: docker-compose up -d"
echo "  3. Access web UI at http://localhost:8080"
echo "  4. API docs at http://localhost:8000/docs"