#!/bin/bash

cd "$SERVER_PATH" || exit

# Ensure required files exist
if [ ! -f "server.jar" ]; then
  echo "Error: server.jar not found!"
  exit 1
fi

# Create a backups folder if it doesn't exist
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# Rotate logs (keep last 5 logs)
mv "$LOG_DIR"/latest.log "$LOG_DIR"/latest-"$(date +%F-%T)".log 2>/dev/null
ls -tp "$LOG_DIR" | grep -v '/$' | tail -n +6 | xargs -I {} rm -- "logs/{}"

# Start the Minecraft server and listen for commands
echo "Starting Minecraft server..."
tail -f "$FIFO_PATH" | java -Xms"$MEMORY_MIN" -Xmx"$MEMORY_MAX" -jar server.jar nogui > >(tee -a "$LOG_DIR/latest.log") 2>&1 & wait
