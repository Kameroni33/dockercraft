#!/bin/sh
# Generic Minecraft server launcher. All provisioning (jar download, mods,
# server.properties) happens on the host via the manager — this only launches.
#
# Env:
#   SERVER_JAR  jar to run, relative to /data        (default: server.jar)
#   MEMORY      heap size for -Xms/-Xmx              (default: 2G)
#   JVM_FLAGS   extra JVM flags (e.g. Aikar's flags) (default: empty)
set -eu

SERVER_JAR="${SERVER_JAR:-server.jar}"
MEMORY="${MEMORY:-2G}"
JVM_FLAGS="${JVM_FLAGS:-}"

if [ ! -f "/data/${SERVER_JAR}" ]; then
    echo "ERROR: /data/${SERVER_JAR} not found — was this instance provisioned?" >&2
    exit 1
fi

# The manager writes eula.txt during provisioning; fail loudly if missing.
if [ ! -f /data/eula.txt ]; then
    echo "ERROR: /data/eula.txt missing — EULA must be accepted at provision time" >&2
    exit 1
fi

# exec so java is PID 1 and receives SIGTERM for graceful world saves on stop.
# shellcheck disable=SC2086
exec java -Xms"${MEMORY}" -Xmx"${MEMORY}" ${JVM_FLAGS} -jar "${SERVER_JAR}" nogui
