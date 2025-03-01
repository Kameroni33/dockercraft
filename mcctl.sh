#!/bin/bash

# TODO: make dynamic
MC_FIFO="$HOME/Projects/dockercraft/fifo"
MC_LOG="$HOME/Projects/dockercraft/log/latest.log"

function send_command() {
  echo "$1" > "$MC_FIFO"
}

function attach_console() {
  local lines=${1:-10}  # Default to 10 if not provided
  tail -n "$lines" -f "$MC_LOG"
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

function show_help() {
  echo "Usage: $0 {send <command> | logs | restart | stop | -h}"
  echo ""
  echo "Commands:"
  echo "  run <command>            Run a generic Minecraft command on the server."
  echo "  logs                     Displays the server logs in real-time."
  echo "  restart                  Restarts the Minecraft server."
  echo "  stop                     Stops the Minecraft server."
  echo "  help                     Shows this help message."
}

case "$1" in
  run)
    shift
    send_command "$@"
    ;;
  logs)
    shift
    attach_console "$1"
    ;;
  restart)
    restart_server
    ;;
  stop)
    stop_server
    ;;
  help)
    show_help
    ;;
  *)
    echo "Invalid option."
    show_help
    ;;
esac
