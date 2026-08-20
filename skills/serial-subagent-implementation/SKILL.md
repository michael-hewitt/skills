---
name: serial-subagent-implementation
description: "Implement multi-step work as a series of sub-agents, one step per sub-agent, one commit per step, all on the current worktree branch. Use whenever an approved implementation plan or PRD requires more than one step or commit — e.g. a feature touching several modules (migration + service + UI + admin), implementing a GitHub issue with a PRD, or any task where the work naturally decomposes into ordered slices. Covers step decomposition, the test-independence dependency analysis, sub-agent prompt contents, per-step quality gates, and orchestrator verification between steps. Do not use for single-commit changes, and do not create pull requests with it — the user reviews the branch first."
---

# Serial Sub-Agent Implementation

Implement a planned, multi-step change as a series of fresh-context sub-agents run **serially** — never in parallel. Each sub-agent performs exactly one step and produces exactly one commit on the **current worktree branch**.

## Prerequisites

- An approved plan or PRD exists, normally as a GitHub issue (with the PRD attached as a comment).
- You are on the feature branch/worktree for the issue. Do **not** create new worktrees or branches — all sub-agents work in the current directory on the current branch.

## Step 1 — Decompose into serial steps

Break the implementation into ordered steps, each small enough for one focused sub-agent and one commit. Typical shape for this codebase: schema/migration → domain logic (enums, services, resolution) → UI (Livewire/Filament) → mailables/notifications → wiring it together.

## Step 2 — Dependency analysis (critical, do not skip)

For **each** step, verify that its tests can pass **without any subsequent step existing**. Sometimes a step's natural tests depend on later work — a sub-agent given such tests will get stuck trying to make tests pass that can never pass.

For every step ask: "If the repo froze after this step's commit, would this step's full test list be green?" If not:

- **Reorder** the steps so the dependency comes first, or
- **Merge** the two interdependent steps into one sub-agent/commit, or
- **Move the test** to the later step that completes the behavior.

Also confirm each step is *designed* to leave the whole suite green — a step may not knowingly break existing tests "to be fixed by the next step." (Verification of this is targeted per step; the full suite runs once at the end — see the final gate.)

## Step 3 — Run one sub-agent per step, serially

Launch each sub-agent only after the previous one's commit is verified. Each sub-agent's prompt must contain:

1. **The issue context**: instruct it to run `gh issue view <N> --comments` to read the issue and its PRD before writing code.
2. **Its step instructions**: precisely what to build in this step, with known file pointers, and what is explicitly out of scope (later steps).
3. **Prior-step summary**: one line per already-landed commit so it doesn't redo or undo earlier work.
4. **The quality gates** (below) and the single-commit requirement.

## Step 4 — Per-step quality gates

Every sub-agent must, before committing:

1. Write or update tests for its step's externally observable behavior (Pest, feature tests preferred).
2. Run its targeted tests: `php artisan test --compact --filter=...` (plus any suites its change touches). Do **not** run the full Pest suite per step — it is far too slow to sit between commits. Pick the test files/filters most relevant to the step's changes; the full suite runs exactly once, after the final step (see the final gate).
3. Run `vendor/bin/pint --dirty --format agent`.
4. Run `vendor/bin/phpstan analyse --memory-limit=512M` and fix all errors.
5. Make **exactly one commit** on the current branch. Message style matches repo history — `Area: what changed (#<issue>)` — with the standard Co-Authored-By footer. No push.

## Step 5 — Orchestrator verification between steps

After each sub-agent reports done:

- Confirm exactly one new commit exists and the working tree is clean (`git status`, `git log`).
- Spot-check the diff against the step instructions.
- If something is wrong, continue **the same sub-agent** (SendMessage) to fix and amend — do not start the next step on a broken base.

## Final gate — full suite once, after the last step

After the last sub-agent's commit lands, run the full Pest suite once (`composer test` — parallel, capped per CLAUDE.md). Fix any regressions (fixes may be their own commit) before reporting the branch done. This is the only point in the workflow where the full suite runs.

## Boundaries

- **No pull request** for the issue unless the user explicitly asks — they review the branch first.
- **No pushes** by sub-agents.
- **No parallelism** — later steps assume earlier commits exist.
