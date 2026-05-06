---
name: release-generator
description: >-
  Automates the full release workflow using commitizen and conventional commits.
  Handles final releases, release candidates (RC), and hotfix patches. Use this
  skill whenever the user says "gere uma release", "create a release", "bump version",
  "release candidate", "RC", "hotfix release", "gere um patch", or anything related
  to versioning, tagging, or publishing a new version of the project. Also use when
  the user asks about "next version", "what version will be next", or "deploy to production".
metadata:
  author: André Teles
  version: '1.0.0'
---

# Release Generator

Automates the full release workflow using commitizen and conventional commits. Handles final releases, release candidates (RC), and hotfix patches.

## Overview

This skill orchestrates the release process for projects using:
- **commitizen** for version management (reads conventional commits to determine bump type)
- **uv** as the Python package manager
- **git tags** in `vX.Y.Z` format to mark releases
- **CHANGELOG.md** auto-generated from commit history

The skill handles three release types:
- **Final release**: bumps to next stable version (e.g., 0.2.0 -> 0.3.0)
- **Release candidate (RC)**: creates a pre-release tag (e.g., 0.3.0rc1)
- **Hotfix**: forces a PATCH bump regardless of commit types (e.g., 0.2.0 -> 0.2.1)

## Prerequisites

Before running the release workflow, verify these are in place:
- `[tool.commitizen]` section in `pyproject.toml` with `version`, `tag_format`, and `version_files`
- `commitizen` in dev dependencies
- At least one conventional commit since the last tag (otherwise commitizen has nothing to bump)

## How Commitizen Determines the Version

Commitizen reads the **current version from `pyproject.toml`** (not from git tags). It then:
1. Finds the git tag matching the current version (`v<version>`)
2. Reads all conventional commits since that tag
3. Determines the bump type based on commit prefixes (`feat` → MINOR, `fix` → PATCH)
4. Updates `version` in all files listed in `version_files`

This means `pyproject.toml` is the source of truth for the current version, and tags are used to delimit commit ranges.

## Environment Workaround

In some environments, the shebang in `.venv/bin/cz` points to a wrong Python path (e.g., `/workspace/.venv/bin/python3` from a Docker build). Always use `uv run python -m commitizen` instead of `uv run cz` to avoid this issue.

Similarly, `.venv/bin/pre-commit` may have the same problem. Use `--no-verify` on bump commits — this is safe because quality checks (lint, format, test) are already executed in Step 2 before any version changes. The `--no-verify` flag only bypasses hooks that cannot execute due to broken shebangs, not to skip quality validation.

## Workflow

### Step 1: Verify clean working tree

```bash
git status
```

If there are uncommitted changes:
- Ask the user if they want to commit them first, stash them, or abort.
- A release should NEVER be generated on a dirty working tree.

### Step 2: Run feedback loops (unless user asked to skip)

Read `ralph-workflow.config.json` and execute each feedback loop:

```bash
uv run ruff check .        # lint
uv run ruff format --check . # format
uv run pytest              # test (includes coverage)
```

If ANY feedback loop fails, STOP and inform the user. Do NOT proceed with the release. The user must fix the issues first.

If the user explicitly said "skip tests", "sem rodar testes", "pula os checks", or similar, you may skip this step.

### Step 3: Check for existing baseline tag

```bash
git tag --list | sort -V | tail -5
uv run python -m commitizen version --project
```

If no tag exists matching the current version in `pyproject.toml`:
- This is the first release. Create a baseline tag on the commit where commitizen was configured (or on the current HEAD if it's appropriate):

```bash
git log --oneline -- pyproject.toml | grep -i "commitizen"
# Find the commit that configured commitizen, then:
git tag -a v<current_version> <commit_hash> -m "Initial version <current_version>"
```

If the current version already has a tag, commitizen can proceed normally.

### Step 4: Determine release type

Based on user request:

| User says | Command | Bump type |
|-----------|---------|-----------|
| "release", "gere uma release", "bump" | `cz bump --yes --no-verify` | Auto (MINOR for feat, PATCH for fix) |
| "release candidate", "RC", "gere um RC" | `cz bump --yes --no-verify --prerelease rc` | Auto + RC suffix |
| "hotfix", "patch", "gere um patch" | `cz bump --yes --no-verify --increment PATCH` | Forced PATCH |

### Step 5: Execute the bump

```bash
uv run python -m commitizen bump --yes --no-verify [options]
```

The `--yes` flag prevents interactive prompts. The `--no-verify` flag bypasses pre-commit hooks that may fail due to shebang issues.

Verify the bump succeeded:
```bash
git log --oneline -2
git tag --list | sort -V | tail -3
uv run python -m commitizen version --project
```

### Step 6: Generate CHANGELOG

```bash
uv run python -m commitizen changelog
```

This regenerates `CHANGELOG.md` from the full commit history grouped by version tags.

### Step 7: Commit CHANGELOG and lockfile updates

After the bump, `CHANGELOG.md` and possibly `uv.lock` will be modified but not committed (since commitizen only commits the version bump itself).

```bash
git add CHANGELOG.md uv.lock
git commit --no-verify -m "chore(release): update CHANGELOG and uv.lock for v<new_version>"
```

### Step 8: Move the tag to include the final commit

The tag created by commitizen points to the bump commit, but we want it to also include the CHANGELOG commit. This is only safe if the tag has NOT been pushed to a remote yet.

```bash
git tag -d v<new_version>
git tag -a v<new_version> -m "Version <new_version>"
```

> **Warning**: If the tag was already pushed to a remote (unlikely in normal flow since push happens in Step 9), moving it requires `git push origin :refs/tags/v<new_version>` followed by `git push origin v<new_version>`. Warn the user before doing this.

Verify:
```bash
git log --oneline --decorate -3
```

The tag should appear on the latest commit (the one with CHANGELOG).

### Step 9: Report and ask about push

Present a summary to the user:

```
Release v<new_version> generated successfully.

- Previous version: v<old_version>
- New version: v<new_version>
- Bump type: MINOR/PATCH/RC
- Commits included: <count> commits since v<old_version>
- Tag: v<new_version> on commit <hash>
```

Then ask:
> "Quer que eu faça o push para o remote? (`git push origin <branch> --tags`)"

Only push if the user confirms.

### Push command (if confirmed):
```bash
git push origin <current_branch> --tags
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "No tag matching configuration" | No baseline tag exists | Create initial tag (Step 3) |
| "No commits found to generate a bump" | No conventional commits since last tag | Inform user there's nothing to release |
| "pre-commit not found" / shebang errors | Broken .venv binaries | Use `--no-verify` (already handled) |
| "is not a terminal" / EOFError | Interactive prompt in non-TTY | Use `--yes` (already handled) |
| Coverage below threshold | Tests pass but coverage fails | Inform user to add tests before releasing |

## Notes

- Tags trigger CI/CD production deploy (as documented in AGENTS.md)
- After `make release-rc` or `make release`, always push tags to remote
- The commitizen configuration in `pyproject.toml` defines `version_files` to keep versions in sync
- Release commits follow conventional format: `bump: version X.Y.Z -> A.B.C`
- If `uv.lock` was not modified after the bump (no version field in lockfile), skip adding it in Step 7
- The `--no-verify` flag is used exclusively because pre-commit hooks may have broken shebangs — quality validation happens in Step 2 before any version changes are made
