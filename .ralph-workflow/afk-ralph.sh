#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

for ((i=1; i<=$1; i++)); do
  echo "=== Ralph iteration $i of $1 ==="

  result=$(docker sandbox run opencode run \
    --dangerously-skip-permissions \
    -f "$PROJECT_DIR/PRD.md" \
    -f "$PROJECT_DIR/prd.json" \
    -f "$SCRIPT_DIR/progress.txt" \
    -f "$PROJECT_DIR/ralph-workflow.config.json" \
    -f "$PROJECT_DIR/AGENTS.md" \
    "1. Read the PRD, prd.json, progress.txt, config.json, and AGENTS.md.
2. Load the ralph-workflow skill for instructions on how to operate.
3. Find the highest-priority incomplete task and implement it.
4. Run ALL feedback loops defined in config.json.
5. If any feedback loop fails, fix the issues before proceeding.
6. Commit your changes.
7. Update prd.json: set passes to true for completed items.
8. Append your progress to progress.txt with: task completed, decisions made, files changed.
ONLY WORK ON A SINGLE TASK.
If all PRD items are complete, output <promise>COMPLETE</promise>.")

  echo "$result"

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "PRD complete after $i iterations."
    exit 0
  fi
done

echo "Reached max iterations ($1). Review progress and re-run if needed."
