#!/usr/bin/env bash
# Run Ralph in a loop up to N iterations, or until the PRD is complete.
#
# Usage:
#   ./afk-ralph.sh <iterations>                              # sandbox + default model
#   ./afk-ralph.sh --sandbox <iterations>                    # sandbox (explicit)
#   ./afk-ralph.sh --no-sandbox <iterations>                 # host, no sandbox
#   ./afk-ralph.sh --model <provider/model> <iterations>     # override model
#   ./afk-ralph.sh -m anthropic/claude-sonnet-4-5 5
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
Usage: $(basename "$0") [--sandbox|--no-sandbox] [--model <provider/model>] <iterations>

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
iterations=""

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
    --)            shift; break ;;
    -*)            echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -z "${iterations}" ]; then
        iterations="$1"; shift
      else
        echo "Unexpected positional argument: $1" >&2; usage >&2; exit 2
      fi
      ;;
  esac
done

if [ -z "${iterations}" ]; then
  usage >&2
  exit 1
fi

if ! [[ "${iterations}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Iterations must be a positive integer, got: ${iterations}" >&2
  exit 2
fi

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

run_ralph() {
  if [ "${use_sandbox}" = "1" ]; then
    RALPH_SANDBOX_NO_TTY=1 "${SCRIPT_DIR}/sandbox/run.sh" opencode "${opencode_args[@]}"
  else
    ( cd "${PROJECT_DIR}" && opencode "${opencode_args[@]}" )
  fi
}

if [ "${use_sandbox}" = "1" ]; then
  echo ">> Running in sandbox (model: ${model})"
else
  echo ">> Running on host, no sandbox (model: ${model})"
fi

for ((i=1; i<=iterations; i++)); do
  echo "=== Ralph iteration $i of ${iterations} ==="

  result="$(run_ralph)"
  echo "$result"

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "PRD complete after $i iterations."
    exit 0
  fi
done

echo "Reached max iterations (${iterations}). Review progress and re-run if needed."

