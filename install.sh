#!/usr/bin/env bash
# dockercraft one-shot installer for a Linux host.
# Idempotent: safe to re-run for updates (rebuilds + restarts the manager).
set -euo pipefail

cd "$(dirname "$0")"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- docker ---------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    say "Docker not found."
    read -rp "Install Docker via get.docker.com? [y/N] " answer
    if [[ ${answer,,} == y* ]]; then
        curl -fsSL https://get.docker.com | sh
    else
        fail "install Docker first: https://docs.docker.com/engine/install/"
    fi
fi
docker info >/dev/null 2>&1 || fail "cannot talk to the Docker daemon (try: sudo usermod -aG docker \$USER, then re-login)"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin missing (docker-compose-plugin package)"

# --- .env -----------------------------------------------------------------
if [[ ! -f .env ]]; then
    say "Writing .env"
    data_dir="$(pwd)/data"
    lan_ip="$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || echo "")"
    port=8080
    while ss -tln 2>/dev/null | grep -q ":${port} "; do port=$((port + 1)); done
    docker_gid="$(stat -c %g /var/run/docker.sock 2>/dev/null || echo 0)"
    cat > .env <<EOF
# Absolute host path for all instance data, backups, and the manager DB.
DOCKERCRAFT_HOST_DATA_DIR=${data_dir}
# LAN IP shown to players / used for port-forward hints (auto-detected).
DOCKERCRAFT_LAN_IP=${lan_ip}
# Manager UI/API port (first free port >= 8080 at install time).
DOCKERCRAFT_PORT=${port}
# Group owning /var/run/docker.sock (manager container joins it).
DOCKER_GID=${docker_gid}
EOF
else
    say ".env exists — keeping it"
fi
# shellcheck disable=SC1091
source .env
mkdir -p "${DOCKERCRAFT_HOST_DATA_DIR}"
# The manager container and MC containers both run as uid 1000 — the data dir
# must be writable by that uid.
owner="$(stat -c %u "${DOCKERCRAFT_HOST_DATA_DIR}")"
if [[ "${owner}" != "1000" ]]; then
    say "Setting data dir ownership to uid 1000 (needs sudo)"
    sudo chown -R 1000:1000 "${DOCKERCRAFT_HOST_DATA_DIR}"
fi

# --- build + start ----------------------------------------------------------
say "Building and starting the manager (first build takes a few minutes)"
docker compose up -d --build

port="${DOCKERCRAFT_PORT:-8080}"
say "Waiting for the manager to come up"
for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:${port}/api/health" >/dev/null 2>&1; then
        ip_hint="${DOCKERCRAFT_LAN_IP:-$(hostname -I | awk '{print $1}')}"
        say "dockercraft is running!"
        echo
        echo "  Open:   http://${ip_hint}:${port}"
        echo "  First visit creates the admin account."
        echo
        echo "  Manage: docker compose logs -f   |   docker compose down"
        exit 0
    fi
    sleep 2
done
fail "manager did not become healthy — check: docker compose logs"
