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
