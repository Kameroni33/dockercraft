#!/bin/bash

# Set memory limits (adjust as needed)
MEMORY_MAX="2G"
MEMORY_MIN="1G"

# Ensure required files exist
if [ ! -f "server.jar" ]; then
  echo "Error: server.jar not found!"
  exit 1
fi

# Create a backups folder if it doesn't exist
mkdir -p backups logs

# Rotate logs (keep last 5 logs)
mv logs/latest.log logs/latest-$(date +%F-%T).log 2>/dev/null
ls -tp logs | grep -v '/$' | tail -n +6 | xargs -I {} rm -- "logs/{}"

# Start the Minecraft server and listen for commands
echo "Starting Minecraft server..."
java -Xms$MEMORY_MIN -Xmx$MEMORY_MAX -jar server.jar nogui < /minecraft/fifo &
wait
