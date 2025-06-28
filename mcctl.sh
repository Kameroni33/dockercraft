#!/bin/bash

# === VARIABLES ===

# TODO: make dynamic
MC_BACKUPS="$HOME/Projects/dockercraft/backups"
MC_SERVER="$HOME/Projects/dockercraft/server"
MC_FIFO="$HOME/Projects/dockercraft/fifo"
MC_LOG="$HOME/Projects/dockercraft/logs"

RESTART_DELAY=10
CONTAINER_NAME="dockercraft"

# === FUNCTIONS ===

function show_help() {
  cat << EOF
Usage: $(basename "$0") [COMMAND] [ARGS...]

Manage the Minecraft server via fifo commands and logs.

Commands:
  status              Check the status of the Minecraft server docker container.
  start               Start the Minecraft server docker container.
  stop                Stop the Minecraft server docker container.
  restart             Restart the Minecraft server gracefully.
  run <command>       Run a Minecraft command on the server.
  logs [NUM]          Show the last NUM lines of server logs and follow. Defaults to 10 lines.
  attach              Attach interactively to the Minecraft server console.
  backup              Run an immediate backup of the server.
  addmod              Interactive setup for adding a mod to the server (via Modrinth).
  help                Display this help message.

Options:
  -h, --help          Show this help and exit.
EOF
  exit 0
}

function run_if_container_active() {
  local func="$1"
  shift

  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Call the function passed as argument with any additional parameters
    "$func" "$@"
  else
    echo "Container '$container_name' is not running. Aborting."
    return 1
  fi
}

function check_status() {
  if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Minecraft server is running."
    docker ps --filter "name=$CONTAINER_NAME" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"
  else
    # Check if container exists but stopped
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
      echo "Minecraft server is NOT running."
      docker ps -a --filter "name=$CONTAINER_NAME" --format "table {{.ID}}\t{{.Names}}\t{{.Status}}"
    else
      echo "Minecraft server container '$CONTAINER_NAME' does not exist."
    fi
  fi
}

function start_server() {
  docker-compose up -d
}

function stop_server() {
  docker-compose down
}

function restart_server() {
  # TODO: Check docker first

  echo "Notifying server and waiting $RESTART_DELAY seconds..."
  echo "say §c[Server] Restarting in $RESTART_DELAY seconds..." > "$MC_FIFO"
  sleep "$RESTART_DELAY"
  echo "stop" > "$MC_FIFO"
  # sleep "$RESTART_DELAY"
  # docker-compose up -d
}

function send_command() {
  echo "$1" > "$MC_FIFO"
}

function view_console() {
  local lines=${1:-10}  # Default to 10 if not provided
  tail -n "$lines" -f "$MC_LOG/latest.log"
}

function attach_console() {
  echo "Attaching to Minecraft server. Press Ctrl+C to exit."

  # Start tailing logs in the background
  tail -f "$MC_LOG/latest.log" &
  TAIL_PID=$!

  # Define a cleanup function to kill tail on exit or interrupt
  cleanup() {
    kill "$TAIL_PID" 2>/dev/null
    wait "$TAIL_PID" 2>/dev/null
    echo "Detached from Minecraft server."
    exit 0
  }

  # Trap SIGINT (Ctrl+C) and SIGTERM signals to cleanup properly
  trap cleanup SIGINT SIGTERM

  # Read user input and send it to the server
  while true; do
    if ! read -r input; then
      # EOF or error on stdin
      break
    fi
    echo "$input" > "$MC_FIFO"
  done

  # Cleanup when input loop ends
  cleanup
}

function run_backup() {
  echo "Initiating immediate backup..."
  docker exec dockercraft /backup.sh
}

function addmod() {
  if [ -z "$1" ]; then
    echo "Usage: $0 addmod <mod-name>"
    exit 1
  fi

  local MOD_NAME="$*"
  local SEARCH_URL="https://api.modrinth.com/v2/search?query=$(echo "$MOD_NAME" | jq -sRr @uri)&facets=%5B%5B%22project_type%3Amod%22%5D%5D&limit=5"

  echo "Searching for mods matching '$MOD_NAME'..."

  # Fetch top 5 results
  local results_json=$(curl -s "$SEARCH_URL")
  local mods_count=$(echo "$results_json" | jq '.hits | length')

  if [ "$mods_count" -eq 0 ]; then
    echo "No mods found matching '$MOD_NAME'."
    exit 1
  fi

  echo "Select a mod:"
  local i=1
  echo "$results_json" | jq -r '.hits[] | "\(.title) (slug: \(.slug))"' | while read -r modline; do
    echo "  $i) $modline"
    i=$((i+1))
  done

  read -p "Enter choice [1-$mods_count]: " choice
  if ! [[ "$choice" =~ ^[1-9][0-9]*$ ]] || [ "$choice" -gt "$mods_count" ] || [ "$choice" -lt 1 ]; then
    echo "Invalid choice."
    exit 1
  fi

  local selected_slug=$(echo "$results_json" | jq -r ".hits[$((choice-1))].slug")

  echo "Fetching versions for mod '$selected_slug'..."

  local versions_json=$(curl -s "https://api.modrinth.com/v2/project/$selected_slug/version")
  local versions_count=$(echo "$versions_json" | jq 'length')

  echo "Available versions:"
  i=1
  echo "$versions_json" | jq -r '.[] | "\(.version_number) - \(.name)"' | while read -r versionline; do
    echo "  $i) $versionline"
    i=$((i+1))
  done

  read -p "Enter version choice [1-$versions_count]: " vchoice
  if ! [[ "$vchoice" =~ ^[1-9][0-9]*$ ]] || [ "$vchoice" -gt "$versions_count" ] || [ "$vchoice" -lt 1 ]; then
    echo "Invalid choice."
    exit 1
  fi

  local download_url=$(echo "$versions_json" | jq -r ".[$((vchoice-1))].files[0].url")
  local mod_filename=$(basename "$download_url")

  echo "Downloading $mod_filename ..."
  curl -L "$download_url" -o "$MC_SERVER/mods/$mod_filename"

  echo "Mod installed to $MC_SERVER/mods/$mod_filename"

  read -p "Restart server now? [y/N] " restart
  if [[ "$restart" =~ ^[Yy]$ ]]; then
    restart_server
  else
    echo "Remember to restart the server later for the mod to load."
  fi
}

# === ENTRYPOINT ===

# argument parser
case "$1" in
  status) check_status ;;
  start) start_server ;;
  stop) stop_server ;;
  restart) run_if_container_active restart_server ;;
  run) shift; run_if_container_active send_command "$@" ;;
  logs) shift; view_console "$1" ;;
  attach) run_if_container_active attach_console ;;
  backup) run_backup ;;
  addmod) shift; addmod "$@" ;;
  help|-h|--help) show_help ;;
  *) echo "Invalid option: $1" >&2; show_help ;;
esac