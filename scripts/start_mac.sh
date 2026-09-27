#!/usr/bin/env bash
# Build the Blokus Arena image and run it in Docker at http://127.0.0.1:7870.
# A running Blokus Arena container is stopped first. Set BLOKUS_PORT to use another port.
# 7870 leaves Gradio's usual 7860 free for other apps and for `uv run blokus`.
# API keys are read from .env, and game history is kept in data/, both in the repository root.
# Usage: scripts/start_mac.sh
set -euo pipefail

cd "$(dirname "$0")/.."
image=blokus-arena
container=blokus-arena
port="${BLOKUS_PORT:-7870}"
url="http://127.0.0.1:${port}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop or Colima, then try again." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop or Colima, then try again." >&2
  exit 1
fi

scripts/stop_mac.sh

# Some Docker setups (Colima, for one) don't report a port that is already taken, and the app
# would then be unreachable while another program answers on its port. So check first.
if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $port is already in use by another program. Close it, or pick another port:" >&2
  echo "  BLOKUS_PORT=7871 scripts/start_mac.sh" >&2
  exit 1
fi

echo "Building the $image image..."
docker build --tag "$image" .
# Each build leaves the previous image untagged, so remove those leftovers.
docker image prune --force --filter "label=org.opencontainers.image.title=$image" >/dev/null

mkdir -p data
run_args=(
  --detach
  --name "$container"
  --publish "127.0.0.1:${port}:7860"
  --mount "type=bind,source=$PWD/data,target=/data"
  # LLM players can use an Ollama server running on this computer.
  --add-host host.docker.internal:host-gateway
  --env OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
)
if [ -f .env ]; then
  run_args+=(--mount "type=bind,source=$PWD/.env,target=/app/.env,readonly")
else
  echo "No .env file, so LLM players can only use Ollama (see README.md)."
fi
docker run "${run_args[@]}" "$image" >/dev/null

echo "Starting $container..."
for _ in $(seq 1 60); do
  if curl --silent --fail --output /dev/null "$url"; then
    echo "Blokus Arena is running at $url"
    echo "Logs: docker logs --follow $container"
    echo "Stop: scripts/stop_mac.sh"
    exit 0
  fi
  if [ "$(docker inspect --format '{{.State.Running}}' "$container")" != "true" ]; then
    echo "The container stopped while starting. Its log:" >&2
    docker logs "$container" >&2
    exit 1
  fi
  sleep 1
done
echo "Blokus Arena did not answer at $url within 60 seconds. See: docker logs $container" >&2
exit 1
