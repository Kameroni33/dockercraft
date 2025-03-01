#!/bin/bash

# TODO: make dynamic
MC_FIFO="$HOME/Projects/dockercraft/fifo"
MC_LOG="$HOME/Projects/dockercraft/log/latest.log"
MC_WORLD="$HOME/Projects/dockercraft/world"

function send_command() {
  echo "$1" > "$MC_FIFO"
}

function view_console() {
  local lines=${1:-10}  # Default to 10 if not provided
  tail -n "$lines" -f "$MC_LOG"
}

function attach_console() {
  echo "Attaching to Minecraft server. Press Ctrl+C to exit."

  # Start tailing logs in the background
  tail -f "$MC_LOG" &
  TAIL_PID=$!

  # Read user input and send it to the server
  while true; do
    read -r input
    echo "$input" > "$MC_FIFO"
  done

  # Kill the log tail process if this function exits
  kill $TAIL_PID
}

function restart_server() {
  echo "say §c[Server] Restarting in 10 seconds..." > "$MC_FIFO"
  sleep 10
  echo "stop" > "$MC_FIFO"
  sleep 5
  docker-compose up -d
}

function stop_server() {
  echo "say §c[Server] Stopping..." > "$MC_FIFO"
  sleep 2
  echo "stop" > "$MC_FIFO"
}

function delete_world() {
  echo "WARNING: This will delete the entire Minecraft world folder ($MC_WORLD)!"
  read -rp "Are you sure? (type 'yes' to confirm): " confirmation

  if [[ "$confirmation" == "yes" ]]; then
    stop_server
    sleep 5
    echo "Deleting world data..."
    rm -rf "$MC_WORLD"
    echo "World deleted successfully."
    restart_server
  else
    echo "Operation canceled."
  fi
}

function show_help() {
  echo "Usage: $0 {send <command> | logs | restart | stop | -h}"
  echo ""
  echo "Commands:"
  echo "  run <command>            Run a generic Minecraft command on the server."
  echo "  logs                     Displays the server logs in real-time."
  echo "  attach                   Attach to the Minecraft server console (interactive logs with input)."
  echo "  restart                  Restarts the Minecraft server."
  echo "  stop                     Stops the Minecraft server."
  echo "  delete                   Delete the current Minecraft world."
  echo "  help                     Shows this help message."
}

case "$1" in
  run)
    shift
    send_command "$@"
    ;;
  logs)
    shift
    view_console "$1"
    ;;
  attach)
    attach_console
    ;;
  restart)
    restart_server
    ;;
  stop)
    stop_server
    ;;
  delete)
    delete_world
    ;;
  help)
    show_help
    ;;
  *)
    echo "Invalid option."
    show_help
    ;;
esac
