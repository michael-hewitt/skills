---
name: implement-issues
description: Orchestrate serial implementation of planned vertical slices as sequential PRs using subagents. Use when user wants AFK implementation of a broken-down plan, serial PR pipeline, or to implement slices from a PRD one at a time with fresh-context subagents.
---

# Implement Issues

Sequentially implement GitHub issues as individual PRs, each built by a fresh-context subagent. The orchestrator manages git operations, PR lifecycle, CI gating, and branch reuse. Issues are typically created upstream by `/to-issues`.

## Prerequisites

- A set of GitHub issues describing vertical slices (typically created by `/to-issues`)
- A parent GitHub issue containing the PRD (the spec) — each slice issue should reference it
- A current branch to use for all PRs (the skill reuses it across slices)
- The repo uses squash merge on the main branch

## Process

### 1. Gather inputs

From the conversation context and GitHub, collect:

- **Issue numbers** — the ordered list of slice issues to implement. Read each with `gh issue view` to confirm titles, descriptions, acceptance criteria, and blocked-by relationships.
- **Parent issue number** — contains the PRD. The subagent reads this for broader context.
- **Main branch name** (usually `main`)
- **Current branch name** (reused for all PRs)

Read CLAUDE.md to identify the project's local validation commands (linter, static analysis, tests). These vary by project. Common examples:

| Stack | Lint | Static analysis | Tests |
|---|---|---|---|
| Laravel | `vendor/bin/pint --dirty` | `vendor/bin/phpstan analyse` | `php artisan test --compact` |
| Node/TS | `npm run lint -- --fix` | `npx tsc --noEmit` | `npm test` |
| Python | `ruff check --fix .` | `mypy .` | `pytest` |

If unclear, ask the user which commands to run for local validation.

### 2. Confirm the plan

Present the ordered issue list (number, title, blocked-by) to the user with the branch and parent issue. Ask for final confirmation before starting. The user may ask to skip, reorder, or stop after a specific issue.

### 3. Execute the issue loop

For each issue, in dependency order:

#### Step 1 — Spawn subagent

Spawn an `Agent` (no worktree isolation — it works in the current directory) with a prompt containing:
- The **issue number**, so it can read the issue with `gh issue view` — this is its primary instruction
- The **parent issue number**, so it can read the PRD with `gh issue view` for broader context
- Instruction to implement the work described in the issue, commit, and push
- Instruction to read CLAUDE.md for project conventions
- Instruction NOT to create new PRs, merge, or modify git config
- Any additional context from the orchestrator that would help (e.g., "the previous slice added X, which you can build on")

The subagent has a **fresh context** — it knows nothing about this conversation. The prompt must be self-contained. The issue is the single source of truth for what to build.

#### Step 2 — Validate locally

After the subagent returns, run the project's validation commands. If any fail, fix the issues (or spawn another subagent to fix), commit, and push.

#### Step 3 — Push branch and open PR

Push the branch with the subagent's commits, then create the PR:

```bash
git push -u origin <branch-name>
gh pr create --title "<issue-title>" --body "<body>"
```

The PR body should include:
- `Closes #<issue-number>` so the issue auto-closes on merge
- A `## Parent` section linking to the parent issue
- The issue's `## What to build` and `## Acceptance criteria` sections (copied from the issue)

#### Step 4 — Wait for CI and merge

```bash
gh pr checks <pr-number> --watch --fail-fast
gh pr merge <pr-number> --squash --delete-branch
```

If CI fails, diagnose and fix (same as step 2), then re-wait.

#### Step 5 — Reset branch for next issue

```bash
git fetch --prune origin
git reset --hard origin/<main-branch>
```

### 4. Report completion

After all issues are merged (or the user asked to stop), summarize what was done: list each issue with its PR number and merge status. Link back to the parent issue.

## Key constraints

- **Serial, never parallel.** Each issue is implemented only after the previous one is merged, even if dependency graphs would allow parallelism. This keeps the subagent context clean — it always works on a branch that matches the current tip of main.
- **Issues are the contract.** The subagent's primary instruction is the GitHub issue. The orchestrator should not paraphrase or reinterpret the issue — let the subagent read it directly.
- **Orchestrator owns git.** Subagents commit and push, but the orchestrator creates PRs, waits for CI, merges, and resets the branch.
- **Subagents are disposable.** Each gets a fresh context. They read the issue and parent PRD for their instructions. They do not know about other issues or slices.
- **CI is the gate.** Never merge before CI passes. Never use `--no-verify` or `--admin` to bypass checks.
- **Branch is reused.** After squash merge, `git rebase` would conflict — always use `git reset --hard origin/<main>` instead.
