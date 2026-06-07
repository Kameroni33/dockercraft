#!/bin/bash

set -euo pipefail

# ─── CONSTANTS ───────────────────────────────────────────────────────────────

SCRIPT_NAME="dockercraft Installation Script"
SCRIPT_VERSION="1.0.0"

AUTO_INSTALL=false
UNINSTALL=false
VERBOSE=false

ROOT_PATH="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# Default manager UI/API port. Deliberately uncommon; the installer walks up
# from here if it happens to be taken. Kept clear of the MC instance port
# ranges (game 25565-25664, RCON 25665-25764).
DEFAULT_PORT=25800

# ─── ENVIRONMENT ─────────────────────────────────────────────────────────────

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ─── LOGGING ─────────────────────────────────────────────────────────────────

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR |${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARN  |${NC} $1"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO  |${NC} $1"
}

debug() {
    [ "${VERBOSE:-false}" = false ] && return
    echo -e "${CYAN}[$(date +'%Y-%m-%d %H:%M:%S')] DEBUG |${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] INFO  |${NC} $1"
}

# ─── HELP ────────────────────────────────────────────────────────────────────

help() {
    cat << EOF
TITLE
    ${SCRIPT_NAME} (${SCRIPT_VERSION})

DESCRIPTION
    One-shot setup of the dockercraft manager on a Linux host.  Checks for
    Docker, generates .env (data dir, LAN IP, port, docker GID), then builds
    and starts the manager via docker compose.  Idempotent — re-run after a
    'git pull' to update.

USAGE
    $(basename "${BASH_SOURCE[0]}") [OPTIONS]

OPTIONS
    -h, --help              Show this help message and exit
    -v, --version           Show script version and exit
        --verbose           Detailed output for debugging
        --auto-install      Allow the script to automatically install Docker
                            (via get.docker.com) if it is missing
        --uninstall         Remove everything dockercraft created: MC instance
                            containers, the manager, built images, and .env.
                            Prompts separately before deleting the data dir
                            (worlds, backups, manager DB).

EOF
}

# ─── FUNCTIONS ───────────────────────────────────────────────────────────────

check_command() {
    command -v "$1" > /dev/null 2>&1
}

install_docker() {
    debug "Installing Docker via get.docker.com convenience script..."
    curl -fsSL https://get.docker.com | sh
    success "Installed docker"
    warn "To use docker as non-root: sudo usermod -aG docker \${USER}, then re-login."
}

find_free_port() {
    local port="$1"
    while ss -tln 2>/dev/null | grep -q ":${port} "; do
        debug "Port ${port} is taken — trying $((port + 1))"
        port=$((port + 1))
    done
    echo "${port}"
}

detect_lan_ip() {
    ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || echo ""
}

uninstall() {
    info "STEP 1: Removing MC instance containers"

    local containers
    containers="$(docker ps -aq --filter "label=dockercraft.instance" 2>/dev/null || true)"
    if [[ -n "${containers}" ]]; then
        debug "Removing containers: $(echo "${containers}" | tr '\n' ' ')"
        # shellcheck disable=SC2086
        docker rm -f ${containers} > /dev/null
        success "Removed $(echo "${containers}" | wc -l) instance container(s)"
    else
        debug "No instance containers found"
    fi

    info "STEP 2: Stopping the manager"

    if [[ -f .env ]]; then
        docker compose --env-file .env down --remove-orphans 2> /dev/null || true
    fi
    docker rm -f dockercraft-api > /dev/null 2>&1 || true
    success "Manager stopped"

    info "STEP 3: Removing built images"

    local images
    images="$(docker images -q "dockercraft/minecraft" 2>/dev/null || true)"
    if [[ -n "${images}" ]]; then
        # shellcheck disable=SC2086
        docker rmi -f ${images} > /dev/null 2>&1 || true
    fi
    docker rmi -f dockercraft-api > /dev/null 2>&1 || true
    success "Images removed"

    info "STEP 4: Removing data and configuration"

    local data_dir="${ROOT_PATH}/data"
    if [[ -f .env ]]; then
        # shellcheck disable=SC1091
        source .env
        data_dir="${DOCKERCRAFT_HOST_DATA_DIR:-${data_dir}}"
    fi

    if [[ -d "${data_dir}" ]]; then
        warn "Data dir contains ALL worlds, backups, and the manager DB: ${data_dir}"
        read -rp "Delete it permanently? [y/N] " answer
        if [[ "${answer,,}" == y* ]]; then
            rm -rf "${data_dir}" 2> /dev/null \
                || sudo rm -rf "${data_dir}"
            success "Deleted ${data_dir}"
        else
            info "Keeping ${data_dir} — a future install will pick it back up."
        fi
    else
        debug "No data dir at ${data_dir}"
    fi

    rm -f .env
    success "Uninstall complete"
}

# ─── ARGUMENT PARSING ────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            help; exit 0 ;;
        --version|-v)
            echo "${SCRIPT_NAME} - ${SCRIPT_VERSION}"; exit 0 ;;
        --auto-install)
            AUTO_INSTALL=true; shift ;;
        --uninstall)
            UNINSTALL=true; shift ;;
        --verbose)
            VERBOSE=true; shift ;;
        *)
            error "Unknown option '$1'"
            error "Run '${BASH_SOURCE[0]} --help' for usage information"
            exit 1 ;;
    esac
done

# ─── ENTRYPOINT ──────────────────────────────────────────────────────────────

cd "${ROOT_PATH}"

if [[ "${UNINSTALL}" == true ]]; then
    uninstall
    exit 0
fi

info "STEP 1: Checking requirements"

if ! check_command docker; then
    if [[ "${AUTO_INSTALL}" == true ]]; then
        install_docker
    else
        error "Docker is missing.  Re-run with --auto-install, or install it manually:"
        error "    https://docs.docker.com/engine/install/"
        exit 1
    fi
fi

if ! docker info > /dev/null 2>&1; then
    error "Cannot talk to the Docker daemon."
    error "Try: sudo usermod -aG docker \${USER}  (then log out and back in)"
    exit 1
fi

if ! docker compose version > /dev/null 2>&1; then
    error "The docker compose plugin is missing (docker-compose-plugin package)."
    exit 1
fi

success "All requirements met"

info "STEP 2: Setting up environment variables"

if [[ ! -f .env ]]; then
    debug "Detecting LAN IP, free port, and docker socket GID"
    DATA_DIR="${ROOT_PATH}/data"
    LAN_IP="$(detect_lan_ip)"
    PORT="$(find_free_port "${DEFAULT_PORT}")"
    DOCKER_GID="$(stat -c %g /var/run/docker.sock 2>/dev/null || echo 0)"

    cat > .env << EOF
# Absolute host path for all instance data, backups, and the manager DB.
DOCKERCRAFT_HOST_DATA_DIR=${DATA_DIR}
# LAN IP shown to players / used for port-forward hints (auto-detected).
DOCKERCRAFT_LAN_IP=${LAN_IP}
# Manager UI/API port (first free port >= ${DEFAULT_PORT} at install time).
DOCKERCRAFT_PORT=${PORT}
# Group owning /var/run/docker.sock (manager container joins it).
DOCKER_GID=${DOCKER_GID}
EOF
    success "Created .env"
else
    debug ".env already exists — skipping."
fi

# shellcheck disable=SC1091
source .env

info "STEP 3: Preparing data directory"

mkdir -p "${DOCKERCRAFT_HOST_DATA_DIR}"

# The manager container and MC containers both run as uid 1000 — the data dir
# must be writable by that uid.
OWNER="$(stat -c %u "${DOCKERCRAFT_HOST_DATA_DIR}")"
if [[ "${OWNER}" != "1000" ]]; then
    warn "Data dir is owned by uid ${OWNER} — changing to uid 1000 (needs sudo)"
    sudo chown -R 1000:1000 "${DOCKERCRAFT_HOST_DATA_DIR}"
fi

success "Data directory ready: ${DOCKERCRAFT_HOST_DATA_DIR}"

info "STEP 4: Building and starting the manager"

debug "docker compose up -d --build (first build takes a few minutes)"
docker compose up -d --build

info "STEP 5: Waiting for the manager to come up"

PORT="${DOCKERCRAFT_PORT:-${DEFAULT_PORT}}"
for _ in $(seq 1 30); do
    if curl -fsS "http://localhost:${PORT}/api/health" > /dev/null 2>&1; then
        IP_HINT="${DOCKERCRAFT_LAN_IP:-$(hostname -I | awk '{print $1}')}"
        success "dockercraft is running!"
        echo
        echo "    Open:   http://${IP_HINT}:${PORT}"
        echo "    First visit creates the admin account."
        echo
        echo "    Manage: docker compose logs -f   |   docker compose down"
        exit 0
    fi
    sleep 2
done

error "Manager did not become healthy — check: docker compose logs"
exit 1
