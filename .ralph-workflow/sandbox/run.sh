#!/usr/bin/env bash
# Run a command inside the ralph-workflow sandbox container.
#
# The host project directory is mounted at /workspace. Host opencode
# auth/config and git identity are bind-mounted read-only where possible.
#
# Usage:
#   ./.ralph-workflow/sandbox/run.sh opencode run --help
#   ./.ralph-workflow/sandbox/run.sh bash
#
# Environment:
#   RALPH_SANDBOX_IMAGE  image name (default: ralph-workflow-sandbox)
#   RALPH_SANDBOX_TAG    image tag  (default: latest)
#   RALPH_SANDBOX_NO_TTY set to 1 to disable -it (for non-interactive use)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

IMAGE_NAME="${RALPH_SANDBOX_IMAGE:-ralph-workflow-sandbox}"
IMAGE_TAG="${RALPH_SANDBOX_TAG:-latest}"
IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

if ! docker image inspect "${IMAGE}" >/dev/null 2>&1; then
  echo ">> Sandbox image ${IMAGE} not found. Building..."
  "${SCRIPT_DIR}/build.sh"
fi

# Required host paths for opencode.
HOST_OPENCODE_DATA="${HOME}/.local/share/opencode"
HOST_OPENCODE_CACHE="${HOME}/.cache/opencode"

# Build docker run args.
docker_args=(
  run
  --rm
  --init
  --security-opt no-new-privileges
  --cap-drop ALL
  --cap-add CHOWN
  --cap-add SETUID
  --cap-add SETGID
  --cap-add DAC_OVERRIDE
  --workdir /workspace
  -v "${PROJECT_DIR}:/workspace"
  -e HOME=/home/ralph
  -e TERM="${TERM:-xterm-256color}"
  -e OPENCODE_SERVER_PASSWORD
  -e OPENCODE_SERVER_USERNAME
  -e OPENROUTER_API_KEY
  -e ANTHROPIC_API_KEY
  -e OPENAI_API_KEY
  -e GEMINI_API_KEY
  -e GITHUB_TOKEN
)

# Mount opencode credentials if present on host.
if [ -d "${HOST_OPENCODE_DATA}" ]; then
  docker_args+=( -v "${HOST_OPENCODE_DATA}:/home/ralph/.local/share/opencode" )
fi
if [ -d "${HOST_OPENCODE_CACHE}" ]; then
  docker_args+=( -v "${HOST_OPENCODE_CACHE}:/home/ralph/.cache/opencode" )
fi

# Mount git identity (read-only) so commits inside the sandbox use the
# same author as the host.
if [ -f "${HOME}/.gitconfig" ]; then
  docker_args+=( -v "${HOME}/.gitconfig:/home/ralph/.gitconfig:ro" )
fi

# Attach TTY only when stdin is a terminal (unless explicitly disabled).
if [ -t 0 ] && [ -t 1 ] && [ "${RALPH_SANDBOX_NO_TTY:-0}" != "1" ]; then
  docker_args+=( -it )
fi

docker_args+=( "${IMAGE}" )

# Default command: bash. Otherwise pass user-supplied args.
if [ "$#" -eq 0 ]; then
  docker_args+=( bash )
else
  docker_args+=( "$@" )
fi

exec docker "${docker_args[@]}"
