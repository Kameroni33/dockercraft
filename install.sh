#!/bin/bash

set -e

# === CONFIG ===

CACHE=".cache"
BIN="/usr/local/bin"
JAR="server.jar"

MCUTILS_URL="https://mcutils.com"

SERVER_NAME="dockercraft"
SERVER_PATH="./server"

CLEAN_ITEMS=(
  "logs"
  "cache"
  "debug"
  "config"
  "libraries"
  "supervisord.log"
  "supervisord.pid"
  "usercache.json"
  "version_history.json"
  "help.yml"
  "commands.yml"
  "permissions.yml"
  "bukkit.yml"
  "spigot.yml"
  ".cache"
  ".fabric"
)


echo "Welcome to the Minecraft Server Installer!"

# === CHECK DEPENDENCIES ===

for cmd in curl jq docker docker-compose; do
  if ! command -v $cmd &> /dev/null; then
    echo "Missing dependency: $cmd"
    exit 1
  fi
done

# === CHECK OVERWRITE ===

if docker ps --format '{{.Names}}' | grep -q "^${SERVER_NAME}$"; then
  echo "Warning: A minecraft server '$SERVER_NAME' already exists ."
  read -p "Do you want to delete it and continue? [y/N] " stopit
  if [[ "$stopit" =~ ^[Yy]$ ]]; then
    echo "Stopping container $SERVER_NAME..."
    docker stop "$SERVER_NAME"
    echo "Removing container $SERVER_NAME..."
    docker rm "$SERVER_NAME"

    for item in "${CLEAN_ITEMS[@]}"; do
      path="$SERVER_PATH/$item"
      if [ -e "$path" ]; then
        echo "Removing $path..."
        rm -rf "$path"
      fi
    done

  else
    echo "Aborting installation."
    exit 0
  fi
fi

if [ -d "$SERVER_PATH/world" ] || [ -d "$SERVER_PATH/world_nether" ] || [ -d "$SERVER_PATH/world_the_end" ]; then
  echo "Warning: Existing Minecraft world data was found."
  read -p "Do you want to overwrite it? [y/N] " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing existing world directory..."
    rm -rf "$SERVER_PATH/world" "$SERVER_PATH/world_nether" "$SERVER_PATH/world_the_end"
  else
    echo "Preserving existing world data."
  fi
fi

if [ -d "$SERVER_PATH/world" ] || [ -d "$SERVER_PATH/world_nether" ] || [ -d "$SERVER_PATH/world_the_end" ]; then
  echo "Warning: Existing plugins/mods were found."
  read -p "Do you want to delete them? [y/N] " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "Removing existing plugins/mods..."
    rm -rf "$SERVER_PATH/plugins" "$SERVER_PATH/mods" "$SERVER_PATH/world_the_end"
  else
    echo "Preserving existing plugins/mods."
  fi
fi

# === FETCH LOADER & VERSIONS ===

echo "Fetching supported loaders from mcutils..."
LOADERS=$(curl -s "$MCUTILS_URL/api/server-jars" | jq -r '.[].key')

echo "Available loaders:"
select LOADER in $LOADERS; do
  if [ -n "$LOADER" ]; then break; fi
done

echo "Fetching supported versions of $LOADER..."
VERSIONS=$(curl -s "$MCUTILS_URL/api/server-jars/$LOADER" | jq -r '.[].version')

echo "Available versions:"
select VERSION in $VERSIONS; do
  if [ -n "$VERSION" ]; then break; fi
done

mkdir -p "$CACHE/$LOADER/$VERSION"

echo "Downloading $LOADER $VERSION..."
JAR_URL=$(curl -s "$MCUTILS_URL/api/server-jars/$LOADER/$VERSION" | jq -r '.downloadUrl')
curl -L "$JAR_URL" -o "$CACHE/$LOADER/$VERSION/$JAR"

cp "$CACHE/$LOADER/$VERSION/$JAR" "$JAR"

# === SERVER SETUP ===

chmod +x "$JAR"
chmod +x mcctl.sh

echo "Installing utility 'mcctl'..."
cp mcctl.sh "$BIN/mcctl"

if [ ! -p fifo ]; then
  echo "Creating FIFO pipe..."
  mkfifo fifo
  chmod 666 fifo
else
  echo "FIFO pipe already exists."
fi


# === START SERVER ===

echo "Building and starting the Minecraft server..."
docker-compose up --build -d

echo "Setup complete! Use 'mcctl' utility to manage your server."
