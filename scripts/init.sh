#!/bin/bash

set -e

echo "Initializing Dockercraft..."

# Create directory structure
mkdir -p data/instances
mkdir -p data/backups
mkdir -p data/logs

# Copy .env.example to .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file"
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
docker build -f docker/minecraft/Dockerfile -t dockercraft-minecraft:latest .
docker compose -f compose.yml up --build --detach

echo ""
echo "Setup complete! WEeb UI running at http://localhost:8080"
echo ""
