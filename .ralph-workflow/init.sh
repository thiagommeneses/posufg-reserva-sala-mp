#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

STACK_CONFIGS='{
  "nodejs": {
    "stack": "nodejs",
    "feedback_loops": {
      "typecheck": "npm run typecheck",
      "test": "npm test",
      "lint": "npm run lint"
    }
  },
  "python": {
    "stack": "python",
    "feedback_loops": {
      "typecheck": "mypy src/",
      "test": "pytest",
      "lint": "ruff check src/"
    }
  },
  "php": {
    "stack": "php",
    "feedback_loops": {
      "typecheck": "phpstan analyse",
      "test": "./vendor/bin/pest",
      "lint": "./vendor/bin/pint --test"
    }
  }
}'

SELECTED_STACK=""
FORCE=false
STACK_EXPLICIT=false

show_help() {
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  --stack <stack>   Set stack (nodejs, python, php) and update config.json"
  echo "  --force           Recreate all files (preserves PRD.md, prd.json, progress.txt)"
  echo "  --help            Show this help"
  echo ""
  echo "Examples:"
  echo "  $0                          Interactive setup"
  echo "  $0 --stack python           Setup with Python stack"
  echo "  $0 --stack nodejs --force   Force recreate all files with Node.js stack"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --stack)
      SELECTED_STACK="$2"
      STACK_EXPLICIT=true
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
done

if [ -z "$SELECTED_STACK" ]; then
  echo "Ralph Loop Workflow — Setup"
  echo ""
  echo "Choose your stack:"
  echo "  1) nodejs"
  echo "  2) python"
  echo "  3) php"
  echo ""
  read -p "Enter choice [1-3]: " choice
  case "$choice" in
    1) SELECTED_STACK="nodejs" ;;
    2) SELECTED_STACK="python" ;;
    3) SELECTED_STACK="php" ;;
    *) echo "Invalid choice."; exit 1 ;;
  esac
  STACK_EXPLICIT=true
fi

echo ""
echo "Setting up Ralph Loop Workflow for stack: $SELECTED_STACK"
echo "Target directory: $TARGET_DIR"
if [ "$FORCE" = true ]; then
  echo "Mode: FORCE (recreate all files)"
fi
echo ""

AGENTS_DIR="$TARGET_DIR/.agents"
SKILLS_DIR="$AGENTS_DIR/skills"
RALPH_DIR="$TARGET_DIR/.ralph-workflow"
TOPR_DIR="$SKILLS_DIR/to-prd"

generate_stack_json() {
  echo "$STACK_CONFIGS" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(d)['$1'],null,2)))" 2>/dev/null || echo "$STACK_CONFIGS" | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin)['$1'], indent=2))" 2>/dev/null
}

if [ ! -d "$TOPR_DIR" ] || [ "$FORCE" = true ]; then
  mkdir -p "$TOPR_DIR"
  cat > "$TOPR_DIR/SKILL.md" << 'TOPR_SKILL'
---
name: to-prd
description: Generate a PRD (PRD.md + prd.json) from conversation context and codebase understanding. Use this skill when the user describes a feature or set of requirements and wants a structured PRD for the Ralph Loop workflow.
---

# to-prd — Generate PRD for Ralph Loop Workflow

This skill takes the current conversation context and codebase understanding and produces a PRD for the Ralph Loop workflow. Do NOT interview the user — just synthesize what you already know.

## When to use this skill

- The user describes a feature or set of requirements
- The user asks to "create a PRD", "generate requirements", or "plan work"
- The user wants to prepare tasks before running the Ralph Loop

## Process

1. Explore the repo to understand the current state of the codebase. Use the project's domain glossary throughout the PRD.

2. Sketch out the major modules you will need to build or modify. Actively look for opportunities to extract deep modules that can be tested in isolation. Check with the user that these modules match their expectations.

3. Write the PRD using the format below. Output two files:
   - `PRD.md` — human-readable PRD in markdown (project root)
   - `prd.json` — structured PRD with `passes` field for tracking (project root)

## PRD.md Format

```markdown
# PRD — [Feature Name]

## Problem Statement

The problem the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

1. As a <role>, I want <feature>, so that <benefit>
2. ...

## Implementation Decisions

- Modules that will be built/modified
- Interfaces of those modules
- Technical clarifications
- Architectural decisions

## Testing Decisions

- What makes a good test (test external behavior, not implementation details)
- Which modules will be tested

## Out of Scope

Things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.
```

## prd.json Format

Each user story becomes a JSON item with testable acceptance criteria:

```json
[
  {
    "category": "functional",
    "description": "Description of the task",
    "steps": [
      "Step to verify the task",
      "Another verification step"
    ],
    "passes": false
  }
]
```

Categories:

- `functional` — feature implementation
- `testing` — test coverage
- `refactor` — code quality improvements
- `integration` — cross-module work
- `architectural` — core abstractions and decisions

## Rules

- Each prd.json item must be independently verifiable
- Steps must be concrete and testable, not vague
- Set `passes: false` on all items initially — the Ralph Loop will mark them `true`
- Keep items small: one logical change per item
- Prioritize items: architectural first, then integration, then features, then polish
TOPR_SKILL
  echo "  Created .agents/skills/to-prd/SKILL.md"
else
  echo "  .agents/skills/to-prd/SKILL.md already exists, skipping"
fi

if [ ! -d "$RALPH_DIR" ]; then
  mkdir -p "$RALPH_DIR"
fi

if [ ! -f "$RALPH_DIR/SKILL.md" ] || [ "$FORCE" = true ]; then
  cat > "$RALPH_DIR/SKILL.md" << 'RALPH_SKILL'
---
name: ralph-workflow
description: Run the Ralph Loop workflow for autonomous task execution. Loads when the user runs ralph-once.sh or afk-ralph.sh, or asks to execute tasks from the PRD in a loop.
---

# Ralph Loop Workflow

Autonomous task execution loop based on the Ralph Wiggum pattern. The agent reads a PRD, picks the highest-priority task, implements it, runs feedback loops, commits, and updates progress.

## When to use this skill

- The user runs `ralph-once.sh` or `afk-ralph.sh`
- The user asks to "run the Ralph loop", "execute the PRD", or "start Ralph"
- The agent is invoked in a loop context

## How Ralph Works

Each iteration follows this cycle:

1. **Read** — Load `PRD.md`, `prd.json`, `progress.txt`, and `AGENTS.md`
2. **Choose** — Pick the highest-priority task where `passes: false`
3. **Implement** — Make the smallest possible change to complete the task
4. **Verify** — Run ALL feedback loops from `ralph-workflow.config.json`
5. **Commit** — If all feedback loops pass, commit the change
6. **Update** — Mark `passes: true` in `prd.json`, append to `progress.txt`
7. **Check** — If all items pass, emit `<promise>COMPLETE</promise>`

## Task Prioritization

When choosing the next task, prioritize in this order:

1. Architectural decisions and core abstractions
2. Integration points between modules
3. Unknown unknowns and spike work
4. Standard features and implementation
5. Polish, cleanup, and quick wins

Fail fast on risky work. Save easy wins for later.

## Feedback Loops

Before committing, run ALL feedback loops defined in `ralph-workflow.config.json`:

```
Read ralph-workflow.config.json to get the feedback_loops commands.
Run each command in order.
Do NOT commit if any feedback loop fails. Fix issues first.
```

The config.json structure:

```json
{
  "stack": "nodejs",
  "feedback_loops": {
    "typecheck": "npm run typecheck",
    "test": "npm test",
    "lint": "npm run lint"
  }
}
```

## Step Size

Keep changes small and focused:

- One logical change per commit
- If a task feels too large, break it into subtasks
- Prefer multiple small commits over one large commit
- Run feedback loops after each change, not at the end

Quality over speed. Small steps compound into big progress.

## Progress Tracking

After completing each task, append to `.ralph-workflow/progress.txt`:

- Task completed and prd.json item reference
- Key decisions made and reasoning
- Files changed
- Any blockers or notes for next iteration

Keep entries concise. This file helps future iterations skip exploration.

## Completion

When all items in `prd.json` have `passes: true`, output:

```
<promise>COMPLETE</promise>
```

## Software Quality

This codebase will outlive you. Every shortcut you take becomes someone else's burden.
Every hack compounds into technical debt that slows the whole team down.

Fight entropy. Leave the codebase better than you found it.

## Code Conventions

- No `any` types unless absolutely unavoidable (add a comment explaining why)
- Prefer explicit returns on functions
- Use descriptive variable names
- Keep functions small and focused
- Follow the existing patterns in the codebase
RALPH_SKILL
  echo "  Created .ralph-workflow/SKILL.md"
else
  echo "  .ralph-workflow/SKILL.md already exists, skipping"
fi

CONFIG_FILE="$TARGET_DIR/ralph-workflow.config.json"
if [ ! -f "$CONFIG_FILE" ] || [ "$STACK_EXPLICIT" = true ]; then
  STACK_JSON=$(generate_stack_json "$SELECTED_STACK")
  if [ -n "$STACK_JSON" ]; then
    echo "$STACK_JSON" > "$CONFIG_FILE"
    if [ -f "$CONFIG_FILE" ] && [ "$STACK_EXPLICIT" = true ] && [ ! "$FORCE" = true ]; then
      echo "  Updated ralph-workflow.config.json (stack: $SELECTED_STACK)"
    else
      echo "  Created ralph-workflow.config.json (stack: $SELECTED_STACK)"
    fi
  else
    echo "  ERROR: Could not generate ralph-workflow.config.json for stack: $SELECTED_STACK"
    exit 1
  fi
else
  echo "  ralph-workflow.config.json already exists, skipping (use --stack to update)"
fi

PRD_MD="$TARGET_DIR/PRD.md"
if [ ! -f "$PRD_MD" ] || [ "$FORCE" = true ]; then
  cat > "$PRD_MD" << 'PRD_MD_CONTENT'
# PRD — [Feature Name]

## Problem Statement

_Descreva o problema que o usuário enfrenta, da perspectiva do usuário._

## Solution

_Descreva a solução, da perspectiva do usuário._

## User Stories

1. As a _[role]_, I want _[feature]_, so that _[benefit]_
2. ...

## Implementation Decisions

- _Módulos que serão construídos/modificados_
- _Interfaces daqueles módulos_
- _Decisões arquiteturais_

## Testing Decisions

- _O que constitui um bom teste para esta feature_
- _Quais módulos serão testados_

## Out of Scope

- _Itens fora do escopo deste PRD_

## Further Notes

- _Notas adicionais sobre a feature_
PRD_MD_CONTENT
  echo "  Created PRD.md"
else
  echo "  PRD.md already exists, skipping"
fi

PRD_JSON="$TARGET_DIR/prd.json"
if [ ! -f "$PRD_JSON" ] || [ "$FORCE" = true ]; then
  cat > "$PRD_JSON" << 'PRD_JSON_CONTENT'
[
  {
    "category": "functional",
    "description": "Descrição da tarefa 1",
    "steps": [
      "Passo para verificar a tarefa 1"
    ],
    "passes": false
  }
]
PRD_JSON_CONTENT
  echo "  Created prd.json"
else
  echo "  prd.json already exists, skipping"
fi

PROGRESS_FILE="$RALPH_DIR/progress.txt"
if [ ! -f "$PROGRESS_FILE" ] || [ "$FORCE" = true ]; then
  > "$PROGRESS_FILE"
  echo "  Created .ralph-workflow/progress.txt"
else
  echo "  .ralph-workflow/progress.txt already exists, skipping"
fi

if [ "$SCRIPT_DIR" != "$RALPH_DIR" ]; then
  if [ ! -f "$RALPH_DIR/ralph-once.sh" ] || [ "$FORCE" = true ]; then
    cp "$SCRIPT_DIR/ralph-once.sh" "$RALPH_DIR/ralph-once.sh" && chmod +x "$RALPH_DIR/ralph-once.sh"
    echo "  Created .ralph-workflow/ralph-once.sh"
  else
    echo "  .ralph-workflow/ralph-once.sh already exists, skipping"
  fi

  if [ ! -f "$RALPH_DIR/afk-ralph.sh" ] || [ "$FORCE" = true ]; then
    cp "$SCRIPT_DIR/afk-ralph.sh" "$RALPH_DIR/afk-ralph.sh" && chmod +x "$RALPH_DIR/afk-ralph.sh"
    echo "  Created .ralph-workflow/afk-ralph.sh"
  else
    echo "  .ralph-workflow/afk-ralph.sh already exists, skipping"
  fi
else
  echo "  .ralph-workflow/ralph-once.sh already exists, skipping"
  echo "  .ralph-workflow/afk-ralph.sh already exists, skipping"
fi

AGENTS_MD="$TARGET_DIR/AGENTS.md"
if [ ! -f "$AGENTS_MD" ] || [ "$FORCE" = true ]; then
  cat > "$AGENTS_MD" << 'AGENTS_MD_CONTENT'
# AGENTS.md

## Software Quality

This codebase will outlive you. Every shortcut you take becomes someone else's burden.
Every hack compounds into technical debt that slows the whole team down.

You are not just writing code. You are shaping the future of this project.
The patterns you establish will be copied. The corners you cut will be cut again.

Fight entropy. Leave the codebase better than you found it.

## Feedback Loops

Before committing, run ALL feedback loops defined in `ralph-workflow.config.json`.
Do NOT commit if any feedback loop fails. Fix issues first.

## Task Prioritization

When choosing the next task, prioritize in this order:

1. Architectural decisions and core abstractions
2. Integration points between modules
3. Unknown unknowns and spike work
4. Standard features and implementation
5. Polish, cleanup, and quick wins

Fail fast on risky work. Save easy wins for later.

## Step Size

Keep changes small and focused:

- One logical change per commit
- If a task feels too large, break it into subtasks
- Prefer multiple small commits over one large commit
- Run feedback loops after each change, not at the end

Quality over speed. Small steps compound into big progress.

## Code Conventions

- No `any` types unless absolutely unavoidable (add a comment explaining why)
- Prefer explicit returns on functions
- Use descriptive variable names
- Keep functions small and focused
AGENTS_MD_CONTENT
  echo "  Created AGENTS.md"
else
  echo "  AGENTS.md already exists, skipping"
fi

echo ""
echo "Ralph Loop Workflow setup complete!"
echo ""
echo "Next steps:"
echo "  1. Fill in PRD.md and prd.json with your tasks"
echo "     (or use the to-prd skill: describe your feature and ask to generate a PRD)"
echo "  2. Run HITL mode:  .ralph-workflow/ralph-once.sh"
echo "  3. Run AFK mode:   .ralph-workflow/afk-ralph.sh <iterations>"
