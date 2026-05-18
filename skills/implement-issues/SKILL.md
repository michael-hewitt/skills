---
name: implement-issues
description: Orchestrate serial implementation of planned vertical slices as sequential PRs using subagents. Use when user wants AFK implementation of a broken-down plan, serial PR pipeline, or to implement slices from a PRD one at a time with fresh-context subagents.
---

# Implement Issues

Sequentially implement vertical slices as individual PRs, each built by a fresh-context subagent. The orchestrator manages git operations, PR lifecycle, CI gating, and branch reuse.

## Prerequisites

- A parent GitHub issue containing the PRD (the spec)
- A list of slices in the conversation context (titles + descriptions + dependency order)
- A current branch to use for all PRs (the skill reuses it across slices)
- The repo uses squash merge on the main branch

## Process

### 1. Gather inputs

From the conversation context, collect:

- **Parent issue number** (contains PRD)
- **Main branch name** (usually `main`)
- **Current branch name** (reused for all PRs)
- **Ordered slice list** — each slice needs: title, description, and acceptance criteria

Read CLAUDE.md to identify the project's local validation commands (linter, static analysis, tests). These vary by project. Common examples:

| Stack | Lint | Static analysis | Tests |
|---|---|---|---|
| Laravel | `vendor/bin/pint --dirty` | `vendor/bin/phpstan analyse` | `php artisan test --compact` |
| Node/TS | `npm run lint -- --fix` | `npx tsc --noEmit` | `npm test` |
| Python | `ruff check --fix .` | `mypy .` | `pytest` |

If unclear, ask the user which commands to run for local validation.

### 2. Confirm the plan

Present the ordered slice list to the user with the branch and parent issue. Ask for final confirmation before starting.

### 3. Execute the slice loop

For each slice, in dependency order:

#### Step 1 — Push branch and open PR

```bash
git push -u origin <branch-name>
gh pr create --title "<slice-title>" --body "<description referencing parent issue>"
```

The PR body should include:
- A `## Parent` section linking to the parent issue
- A `## What to build` section with the slice description
- `## Acceptance criteria` as a checklist
- A note that this PR is being implemented by a subagent

#### Step 2 — Spawn subagent

Spawn an `Agent` (no worktree isolation — it works in the current directory) with a prompt containing:
- The PR number and repo, so it can read the PR with `gh pr view`
- The parent issue number, so it can read the PRD with `gh issue view`
- Instruction to implement the work described in the PR, commit, and push
- Instruction to read CLAUDE.md for project conventions
- Instruction NOT to create new PRs, merge, or modify git config

The subagent has a **fresh context** — it knows nothing about this conversation. The prompt must be self-contained.

#### Step 3 — Validate locally

After the subagent returns, run the project's validation commands. If any fail, fix the issues (or spawn another subagent to fix), commit, and push.

#### Step 4 — Wait for CI and merge

```bash
gh pr checks <pr-number> --watch --fail-fast
gh pr merge <pr-number> --squash --delete-branch
```

If CI fails, diagnose and fix (same as step 3), then re-wait.

#### Step 5 — Reset branch for next slice

```bash
git fetch --prune origin
git reset --hard origin/<main-branch>
```

If there are more slices, re-push the branch:

```bash
git push -u origin <branch-name>
```

### 4. Report completion

After all slices are merged, summarize what was done: list each PR with its number and merge status. Link back to the parent issue.

## Key constraints

- **Serial, never parallel.** Each slice depends on the previous one being merged.
- **Orchestrator owns git.** Subagents commit and push, but the orchestrator creates PRs, waits for CI, merges, and resets the branch.
- **Subagents are disposable.** Each gets a fresh context. They read the PR and parent issue for their instructions. They do not know about other slices.
- **CI is the gate.** Never merge before CI passes. Never use `--no-verify` or `--admin` to bypass checks.
- **Branch is reused.** After squash merge, `git rebase` would conflict — always use `git reset --hard origin/<main>` instead.
