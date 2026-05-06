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
