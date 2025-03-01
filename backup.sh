#!/bin/bash

# Set backup folder
BACKUP_DIR="/minecraft/backup"
WORLD_DIR="/minecraft/world"
TIMESTAMP=$(date +%F-%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/world-$TIMESTAMP.tar.gz"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Notify players backup is starting
echo "say §6[Backup] §fStarting world backup..." > /minecraft/fifo

# Create a compressed backup
tar -czf "$BACKUP_FILE" "$WORLD_DIR"

# Notify players backup is complete
echo "say §6[Backup] §fBackup completed successfully!" > /minecraft/fifo

# Keep only the last 7 backups
ls -tp "$BACKUP_DIR" | grep -v '/$' | tail -n +8 | xargs -I {} rm -- "$BACKUP_DIR/{}"

echo "Backup created: $BACKUP_FILE"
