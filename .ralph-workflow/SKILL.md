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
