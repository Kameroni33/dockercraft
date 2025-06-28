#!/bin/bash

# Set default value if MAX_FILES is not set
MAX_LOGS=${MAX_LOGS:-10}
MAX_BACKUPS=${MAX_BACKUPS:-10}

# Set backup folder
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR" "$LOG_DIR"

# Notify players backup is starting
echo "say §6[Backup] §fStarting world backup..." > /minecraft/fifo

# Disable world saving to prevent corruption
echo "save-all" > /minecraft/fifo
echo "save-off" > /minecraft/fifo
sleep 5  # Give Minecraft time to flush world data

# Create a compressed backup of all worlds
tar -czf "$BACKUP_FILE" "$SERVER_PATH/world" "$SERVER_PATH/world_nether" "$SERVER_PATH/world_the_end"

# Re-enable world saving
echo "save-on" > /minecraft/fifo

# Notify players backup is complete
echo "say §6[Backup] §fBackup completed successfully!" > /minecraft/fifo

# Keep only the last MAX_BACKUPS backups
ls -tp "$BACKUP_DIR" | grep -v '/$' | tail -n +"$((MAX_BACKUPS + 1))" | xargs -I {} rm -- "$BACKUP_DIR/{}"

# Notify players that restart will occur in 60 seconds
echo "say §6[Backup] §fRestarting server in 60 seconds" > /minecraft/fifo
sleep 30
echo "say §6[Backup] §fRestarting server in 30 seconds" > /minecraft/fifo
sleep 10
echo "say §6[Backup] §fRestarting server in 20 seconds" > /minecraft/fifo
sleep 10
echo "say §6[Backup] §fRestarting server in 10 seconds" > /minecraft/fifo
sleep 5
echo "say §6[Backup] §fRestarting server in 5 seconds" > /minecraft/fifo
sleep 1
echo "say §6[Backup] §fRestarting server in 4 seconds" > /minecraft/fifo
sleep 1
echo "say §6[Backup] §fRestarting server in 3 seconds" > /minecraft/fifo
sleep 1
echo "say §6[Backup] §fRestarting server in 2 seconds" > /minecraft/fifo
sleep 1
echo "say §6[Backup] §fRestarting server in 1 seconds" > /minecraft/fifo
sleep 1
echo "say §6[Backup] §fRestarting server..." > /minecraft/fifo

# Rotate logs (keep last MAX_LOGS logs)
mv "$LOG_DIR/latest.log" "$LOG_DIR/$TIMESTAMP.log" 2>/dev/null
ls -tp "$LOG_DIR" | grep -v '/$' | tail -n +"$((MAX_LOGS + 1))" | xargs -I {} rm -- "$LOG_DIR/{}"

# Stop the server
echo "stop" > "$FIFO_PATH"

echo "Backup created: $BACKUP_FILE"
