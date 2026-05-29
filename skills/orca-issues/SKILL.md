---
name: orca-issues
description: File and track GitHub issues for Orca, the Stably AI desktop ADE/editor (the "next-gen IDE for working with a fleet of parallel agents" — the app this user edits code in, NOT the project being worked on). Use whenever the user wants to file a feature request or bug report against Orca itself; check the status of Orca issues they have filed; find which Orca release a fix shipped in; or report something about the Orca app's UI/behavior (Tasks page, worktrees, terminals, browser automation, computer-use, keyboard shortcuts, tabs, etc.). The canonical repo is `stablyai/orca`. Do NOT use for issues about the project codebase the user is developing (those go to that project's own repo) — this skill is only for the Orca editor application.
---

# Orca Issues

Orca is the desktop ADE (IDE) made by **Stably AI** that this user runs to edit code and drive parallel agents. Bugs and feature requests *about the Orca app itself* are tracked on GitHub.

## Canonical facts

- **Repo:** `stablyai/orca`
- **Bundle id:** `com.stablyai.orca` (app at `/Applications/Orca.app`)
- **Installed version:** read it from the app bundle —
  `defaults read /Applications/Orca.app/Contents/Info.plist CFBundleShortVersionString`
- The user's GitHub login is whatever `gh api user --jq .login` returns (currently `michael-hewitt`).
- Releases are tagged `vMAJOR.MINOR.PATCH` (e.g. `v1.4.35`), with `-rc.N` pre-releases between stable tags.

> Do not confuse `stablyai/orca` with the many unrelated GitHub repos named "orca" (spinnaker/orca, hundredrabbits/Orca, OrcaSlicer, GNOME/orca, etc.). The Stably AI desktop editor is always `stablyai/orca`.

## File a new issue

Use `gh` against the repo. Write a clear title and a body with context + the concrete request. Do **not** add labels unless the user asks.

```bash
gh issue create --repo stablyai/orca \
  --title "<concise title>" \
  --body "<what you observe / where in the UI>

**Request:** <the concrete change>

**Benefit:** <why it helps>"
```

Confirm the wording with the user before filing if there's any ambiguity, then report back the issue URL `gh` prints.

## Check issues the user has filed

```bash
# All issues this user authored in the Orca repo (open + closed)
gh issue list --repo stablyai/orca --author "@me" --state all \
  --json number,title,state,createdAt --jq \
  '.[] | "#\(.number) [\(.state)] \(.title)"'
```

For one issue's full status, including how it was resolved:

```bash
gh issue view <N> --repo stablyai/orca \
  --json number,title,state,stateReason,createdAt,closedAt,comments \
  --jq '"#\(.number) [\(.state)/\(.stateReason)] \(.title)\nclosed: \(.closedAt // "—")\ncomments: \(.comments|length)"'
gh issue view <N> --repo stablyai/orca --comments   # read the discussion / fix notes
```

Maintainers usually leave a closing comment naming the fix PR (e.g. "Merged #2977 for this. Coming in the next release").

## Find which release a fix shipped in

The closing comment names the PR. Get the PR's merge timestamp, then compare against the release tag timeline — the fix ships in the first stable tag created *after* its merge.

```bash
# 1. merge time of the fix PR
gh pr view <PR> --repo stablyai/orca --json number,mergedAt,mergeCommit \
  --jq '"#\(.number) merged=\(.mergedAt) commit=\(.mergeCommit.oid[0:12])"'

# 2. release tags with timestamps (stable tags have no -rc suffix)
gh release list --repo stablyai/orca --limit 25
```

The first stable `vX.Y.Z` tagged after the PR's `mergedAt` is the release containing it. Then compare to the installed version (`CFBundleShortVersionString`) to tell the user whether they already have it or need to update.

## Pitfalls (learned the hard way)

- **Confirm the repo from real data before probing.** The correct slug is `stablyai/orca`; don't guess alternative org names — a `gh` call against a non-existent repo returns empty/errors.
- **Run dependent `gh` calls sequentially, not as one big parallel batch.** If the first call in a parallel batch errors, every dependent call in that batch gets auto-cancelled, producing a wall of identical "Cancelled: parallel tool call" errors. One real failure, many noisy duplicates.
- **`status` is a read-only variable in zsh** — don't assign to it in shell loops; pick another name like `cmp_status`.
