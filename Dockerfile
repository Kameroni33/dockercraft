FROM openjdk:21-jdk-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /minecraft

# Accept EULA automatically
RUN echo "eula=true" > eula.txt

# Expose Minecraft server port
EXPOSE 25565

# Create Minecraft working directory
RUN mkdir -p /minecraft

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Copy backup script
COPY backup.sh /backup.sh
RUN chmod +x /backup.sh

# Create a named pipe for server commands
RUN mkfifo /minecraft/fifo

# Add cron job for daily backups
RUN (echo "0 0 * * * /backup.sh") | crontab -

# Set entrypoint
ENTRYPOINT ["/start.sh"]
