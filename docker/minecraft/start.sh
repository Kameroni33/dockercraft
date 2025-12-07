#!/bin/bash

set -e

# Default values
MEMORY_MIN=${MEMORY_MIN:-2G}
MEMORY_MAX=${MEMORY_MAX:-4G}
RCON_PASSWORD=${RCON_PASSWORD:-changeme}
RCON_PORT=${RCON_PORT:-25575}

cd /minecraft

# Check for server.jar
if [ ! -f "server.jar" ]; then
    echo "ERROR: server.jar not found in /minecraft"
    echo "Please ensure server.jar is in your instance directory"
    exit 1
fi

# Auto-accept EULA
echo "eula=true" > eula.txt

# Enable RCON in server.properties if not already set
if [ ! -f "server.properties" ]; then
    echo "enable-rcon=true" > server.properties
    echo "rcon.port=${RCON_PORT}" >> server.properties
    echo "rcon.password=${RCON_PASSWORD}" >> server.properties
else
    # Update existing server.properties
    if ! grep -q "enable-rcon=true" server.properties; then
        sed -i 's/enable-rcon=false/enable-rcon=true/' server.properties || echo "enable-rcon=true" >> server.properties
    fi
    if ! grep -q "rcon.port=" server.properties; then
        echo "rcon.port=${RCON_PORT}" >> server.properties
    fi
    if ! grep -q "rcon.password=" server.properties; then
        echo "rcon.password=${RCON_PASSWORD}" >> server.properties
    fi
fi

echo "Starting Minecraft server with ${MEMORY_MIN} to ${MEMORY_MAX} RAM..."
echo "RCON enabled on port ${RCON_PORT}"

# Start server
exec java -Xms${MEMORY_MIN} -Xmx${MEMORY_MAX} \
    -XX:+UseG1GC \
    -XX:+ParallelRefProcEnabled \
    -XX:MaxGCPauseMillis=200 \
    -XX:+UnlockExperimentalVMOptions \
    -XX:+DisableExplicitGC \
    -XX:+AlwaysPreTouch \
    -XX:G1HeapWastePercent=5 \
    -XX:G1MixedGCCountTarget=4 \
    -XX:G1MixedGCLiveThresholdPercent=90 \
    -XX:G1RSetUpdatingPauseTimePercent=5 \
    -XX:SurvivorRatio=32 \
    -XX:+PerfDisableSharedMem \
    -XX:MaxTenuringThreshold=1 \
    -Dusing.aikars.flags=https://mcflags.emc.gs \
    -Daikars.new.flags=true \
    -jar server.jar nogui
