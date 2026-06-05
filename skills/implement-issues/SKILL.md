---
name: implement-issues
description: Orchestrate serial implementation of planned vertical slices on the current branch using fresh-context subagents and issue-suffixed conventional commits. Use when user wants AFK implementation of GitHub issues from a PRD one at a time without creating pull requests.
---

# Implement Issues

Sequentially implement GitHub issues on the current branch, each built by a fresh-context subagent. The orchestrator manages issue ordering, local validation, and commit hygiene. Issues are typically created upstream by `/to-issues`.

## Prerequisites

- A set of GitHub issues describing vertical slices (typically created by `/to-issues`)
- A parent GitHub issue containing the PRD (the spec) — each slice issue should reference it
- A current branch to use for all implementation commits
- The repo's accepted conventional commit prefixes (from CI/workflows or project convention)

## Process

### 1. Gather inputs

From the conversation context and GitHub, collect:

- **Issue numbers** — the ordered list of slice issues to implement. Read each with `gh issue view` to confirm titles, descriptions, acceptance criteria, and blocked-by relationships.
- **Parent issue number** — contains the PRD. The subagent reads this for broader context.
- **Main branch name** (usually `main`)
- **Current branch name** (all work stays here)
- **Valid commit prefixes** from CI/project convention. Common examples: `feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`, `ci:`.

Read CLAUDE.md to identify the project's local validation commands (linter, static analysis, tests). These vary by project. Common examples:

| Stack | Lint | Static analysis | Tests |
|---|---|---|---|
| Laravel | `vendor/bin/pint --dirty` | `vendor/bin/phpstan analyse` | `php artisan test --compact` |
| Node/TS | `npm run lint -- --fix` | `npx tsc --noEmit` | `npm test` |
| Python | `ruff check --fix .` | `mypy .` | `pytest` |

If unclear, ask the user which commands to run for local validation.

### 2. Confirm the plan

Present the ordered issue list (number, title, blocked-by) to the user with the branch and parent issue unless the user already explicitly asked to proceed without further approval. The user may ask to skip, reorder, or stop after a specific issue.

### 3. Execute the issue loop

For each issue, in dependency order:

#### Step 1 — Spawn subagent

Spawn an `Agent` (no worktree isolation — it works in the current directory) with a prompt containing:
- The **issue number**, so it can read the issue with `gh issue view` — this is its primary instruction
- The **parent issue number**, so it can read the PRD with `gh issue view` for broader context
- Instruction to implement the work described in the issue and commit on the current branch
- Instruction to read CLAUDE.md for project conventions
- Instruction NOT to create PRs, push, merge, reset the branch, or modify git config
- Instruction that the commit message must use a valid conventional prefix and end with the child issue reference, e.g. `fix: Tighten organization-person purge scope (#301)`
- Any additional context from the orchestrator that would help (e.g., "the previous slice added X, which you can build on")

The subagent has a **fresh context** — it knows nothing about this conversation. The prompt must be self-contained. The issue is the single source of truth for what to build.

#### Step 2 — Validate locally

After the subagent returns, inspect the commit and run the project's focused validation commands. If any fail, fix the issues (or spawn another subagent to fix) and commit the fix with the same message rules.

#### Step 3 — Continue serially

Do not create a PR. Do not push unless the user explicitly asks. Leave the branch as-is and start the next issue on top of the previous issue's committed work.

### 4. Report completion

After all issues are implemented (or the user asked to stop), summarize what was done: list each issue with its commit hash and validation status. Link back to the parent issue.

## Key constraints

- **Serial, never parallel.** Each issue is implemented only after the previous one is committed and validated, even if dependency graphs would allow parallelism.
- **Issues are the contract.** The subagent's primary instruction is the GitHub issue. The orchestrator should not paraphrase or reinterpret the issue — let the subagent read it directly.
- **No PR lifecycle.** Do not create PRs, wait for PR CI, merge, delete branches, or reset to main as part of this skill.
- **Current branch only.** Work accumulates as serial commits on the current branch.
- **Commit format matters.** Every implementation commit must use one of the repo's accepted conventional prefixes and must be suffixed with the corresponding child issue, e.g. `fix: Add role slug resolver (#301)`.
- **Subagents are disposable.** Each gets a fresh context. They read the issue and parent PRD for their instructions. They do not know about other issues or slices.
- **Validation is the gate.** Run focused local validation after each issue. Never use `--no-verify` to bypass hooks.
