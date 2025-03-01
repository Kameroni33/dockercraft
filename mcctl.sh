#!/bin/bash

MC_FIFO="/minecraft/fifo"
MC_LOG="/minecraft/logs/latest.log"

function send_command() {
  echo "$1" > "$MC_FIFO"
}

function attach_console() {
  tail -f "$MC_LOG"
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
    attach_console
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
