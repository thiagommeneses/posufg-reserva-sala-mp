#!/usr/bin/env bash
# Build the ralph-workflow sandbox image.
#
# Usage: ./.ralph-workflow/sandbox/build.sh [--no-cache]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

IMAGE_NAME="${RALPH_SANDBOX_IMAGE:-ralph-workflow-sandbox}"
IMAGE_TAG="${RALPH_SANDBOX_TAG:-latest}"
UID_ARG="$(id -u)"
GID_ARG="$(id -g)"

echo ">> Building ${IMAGE_NAME}:${IMAGE_TAG} (UID=${UID_ARG} GID=${GID_ARG})"

docker build \
  "$@" \
  --build-arg "UID=${UID_ARG}" \
  --build-arg "GID=${GID_ARG}" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" \
  "${SCRIPT_DIR}"

echo ">> Image ${IMAGE_NAME}:${IMAGE_TAG} ready."
