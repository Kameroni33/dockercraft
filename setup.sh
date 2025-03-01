#!/bin/bash

set -e

# Default values
DEFAULT_VERSION="latest"
DEFAULT_NAME="minecraft_server"
MC_DIR="$PWD/minecraft_server"
MCCTL_PATH="/usr/local/bin/mcctl"

JAR_URL="https://api.papermc.io/v2/projects/paper/versions"

echo "Welcome to the Minecraft Server Setup!"

# Install Docker if not installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    sudo apt update
    sudo apt install -y docker.io
    sudo systemctl enable --now docker
    echo "Docker installed successfully."
fi

# Add current user to Docker group
if ! groups $USER | grep -q '\bdocker\b'; then
    echo "Adding $USER to the docker group..."
    sudo usermod -aG docker $USER
    echo "Please log out and back in or run 'newgrp docker' for changes to take effect."
fi

# Install Docker Compose if not installed
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo apt install -y docker-compose
fi

# Prompt for server name
read -p "Enter server name [$DEFAULT_NAME]: " SERVER_NAME
SERVER_NAME=${SERVER_NAME:-$DEFAULT_NAME}

# Prompt for Minecraft version
read -p "Enter Minecraft version (or 'latest' for newest) [$DEFAULT_VERSION]: " MC_VERSION
MC_VERSION=${MC_VERSION:-$DEFAULT_VERSION}

# Create server directory
mkdir -p "$MC_DIR"
cd "$MC_DIR"

# Fetch latest Minecraft version if 'latest' is selected
if [ "$MC_VERSION" == "latest" ]; then
    MC_VERSION=$(curl -s "$JAR_URL" | jq -r '.versions[-1]')
    echo "Latest version detected: $MC_VERSION"
fi

# Download the selected Minecraft server JAR
JAR_NAME="paper-$MC_VERSION.jar"
echo "Downloading Minecraft server version $MC_VERSION..."
curl -o "$MC_DIR/$JAR_NAME" -L "$JAR_URL/$MC_VERSION/builds/latest/downloads/paper-$MC_VERSION.jar"

# Ensure execution permissions
chmod +x "$MC_DIR/$JAR_NAME"

# Install mcctl globally
chmod +x mcctl.sh
sudo mv mcctl.sh "$MCCTL_PATH"

# Build and start the server
echo "Building and starting the Minecraft server..."
docker-compose up -d --build

echo "Setup complete! Use 'mcctl' to manage your server."
