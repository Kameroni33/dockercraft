FROM openjdk:21-jdk-slim

# Install system dependencies
RUN apt-get update
RUN apt-get install -y curl
RUN rm -rf /var/lib/apt/lists/*

# Create minecraft user and directory
RUN useradd -m -u 1000 minecraft
RUN mkdir -p /minecraft
RUN chown -R minecraft:minecraft /minecraft

WORKDIR /minecraft

# Copy startup script
COPY docker/minecraft/start.sh /start.sh
RUN chmod +x /start.sh

USER minecraft

# Expose server ports
EXPOSE 25565 25575

ENTRYPOINT ["/start.sh"]
