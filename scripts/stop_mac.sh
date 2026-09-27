#!/usr/bin/env bash
# Stop the Blokus Arena container and remove it. Game history stays in data/.
# Usage: scripts/stop_mac.sh
set -euo pipefail

container=blokus-arena

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "Docker is not running, so there is no container to stop."
  exit 0
fi

if [ -n "$(docker ps --all --quiet --filter "name=^${container}\$")" ]; then
  echo "Stopping $container..."
  docker stop "$container" >/dev/null
  docker rm "$container" >/dev/null
  echo "Stopped $container."
else
  echo "$container is not running."
fi
