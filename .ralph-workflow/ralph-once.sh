#!/usr/bin/env bash
# Run a single Ralph iteration.
#
# Usage:
#   ./ralph-once.sh                              # sandbox + default model
#   ./ralph-once.sh --sandbox                    # sandbox (explicit)
#   ./ralph-once.sh --no-sandbox                 # host, no sandbox
#   ./ralph-once.sh --model <provider/model>     # override model
#   ./ralph-once.sh -m anthropic/claude-sonnet-4-5
#
# Env vars (CLI flags always win):
#   RALPH_NO_SANDBOX=1            Same as --no-sandbox
#   RALPH_MODEL=<provider/model>  Same as --model
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_MODEL="opencode/kimi-k2.6"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--sandbox|--no-sandbox] [--model <provider/model>] [-h|--help]

Options:
  --sandbox                 Run opencode inside the Docker sandbox (default).
  --no-sandbox              Run opencode directly on the host.
  -m, --model <id>          Model to use (default: ${DEFAULT_MODEL}).
  -h, --help                Show this help.

Env:
  RALPH_NO_SANDBOX=1            Same as --no-sandbox.
  RALPH_MODEL=<provider/model>  Same as --model.

CLI flags always override environment variables.
EOF
}

# Defaults.
use_sandbox=1
if [ "${RALPH_NO_SANDBOX:-0}" = "1" ]; then
  use_sandbox=0
fi

model="${RALPH_MODEL:-${DEFAULT_MODEL}}"

while [ $# -gt 0 ]; do
  case "$1" in
    --sandbox)     use_sandbox=1; shift ;;
    --no-sandbox)  use_sandbox=0; shift ;;
    -m|--model)
      if [ $# -lt 2 ]; then
        echo "Missing value for $1" >&2; usage >&2; exit 2
      fi
      model="$2"; shift 2 ;;
    --model=*)     model="${1#--model=}"; shift ;;
    -h|--help)     usage; exit 0 ;;
    *)             echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

PROMPT="1. Read the PRD, prd.json, progress.txt, config.json, and AGENTS.md.
2. Load the ralph-workflow skill for instructions on how to operate.
3. Find the highest-priority incomplete task and implement it.
4. Run ALL feedback loops defined in config.json.
5. If any feedback loop fails, fix the issues before proceeding.
6. Commit your changes.
7. Update prd.json: set passes to true for completed items.
8. Append your progress to progress.txt with: task completed, decisions made, files changed.
ONLY WORK ON A SINGLE TASK.
If all PRD items are complete, output <promise>COMPLETE</promise>."

opencode_args=(
  run
  --dangerously-skip-permissions
  -m "${model}"
  "${PROMPT}"
  -f "PRD.md"
  -f "prd.json"
  -f ".ralph-workflow/progress.txt"
  -f "ralph-workflow.config.json"
  -f "AGENTS.md"
)

if [ "${use_sandbox}" = "1" ]; then
  echo ">> Running in sandbox (model: ${model})"
  exec "${SCRIPT_DIR}/sandbox/run.sh" opencode "${opencode_args[@]}"
else
  echo ">> Running on host, no sandbox (model: ${model})"
  cd "${PROJECT_DIR}"
  exec opencode "${opencode_args[@]}"
fi

