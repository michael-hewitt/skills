---
name: orca-open-herd-url
description: Open the local dev URL (Laravel Herd / herd-wake) for the current Orca worktree in an Orca browser tab scoped to that worktree. Use when the user asks to open the app, open the Herd URL, open the dev server, preview the site, or view the local site in a browser. Handles both PHP sites parked by Herd and Node worktrees served on demand by herd-wake — for the latter it defers to the repo's own preview skill so the opened page shows the current code.
---

# Open Laravel Herd URL in Orca Browser

Open the local development URL for the current Orca worktree in a browser tab scoped
to that worktree. Two kinds of site answer at Herd `.test` URLs on this machine, and
they need different handling — decide which one this worktree is first.

## 1. Which kind of site is this worktree?

```bash
herd-wake url "$PWD"        # or: herd-wake url <worktree path>
```

- **Exit 0** — this is a **Node worktree served on demand by herd-wake**. The printed
  URL (e.g. `https://<worktree-dir>.webapp.test`) is the one to open, exactly as
  printed, scheme included. The server wakes on the first request; nothing to start
  by hand. **Go to step 2 before opening anything.**
- **Non-zero** — herd-wake does not serve this directory, so this is an ordinary
  **Herd parked site (PHP)**. The URL is `http://<dirname>.test`, where `<dirname>`
  is the last path component of the worktree path (`orca worktree current --json`,
  field `path`). Use `http://`, not `https://`, unless the site was explicitly
  secured in Herd. There is no client bundle and nothing to rebuild — **skip to
  step 3.**

## 2. Node worktrees: make the app match the code first

In herd-wake-served repos nothing rebuilds the client bundle or restarts the server
automatically — a bare tab would show stale code. Check whether the repo ships its
own preview skill (crescendosw/webapp does: `preview-changes`, in the repo's
`.claude/skills/`, so it is in your skill list when you work in one of its
worktrees).

- **The repo has a preview skill** → **first run the guard below**, then load and
  follow the preview skill. It runs `npm run preview` (regenerates schemas, restarts
  the server *through herd-wake*, rebuilds the bundle only when stale) and already
  knows how to refresh an existing Orca tab or open a new one — if it opened the
  tab, you are done and step 3 does not apply.
- **No preview skill in the repo** → just open the URL from step 1; there is no
  known rebuild step to run.

### Guard: is this branch's preview script herd-wake-aware?

The preview script comes from the worktree's own checkout, and a branch cut before
the herd-wake integration landed (crescendosw/webapp PR #3452) still carries the old
script, which starts its own detached server on the same port herd-wake uses.
herd-wake then crash-loops on `EADDRINUSE`, silently eating memory until the laptop
becomes unusable. Check before running any preview:

```bash
grep -q herdWakeEnsureServer scripts/sypdev.mjs && echo herd-wake-aware || echo OLD-SCRIPT
```

- **herd-wake-aware** → proceed with the preview skill.
- **OLD-SCRIPT** (or no `scripts/sypdev.mjs`) → do **not** run `npm run preview` or
  `npm start`. Tell the user the branch predates the herd-wake integration and offer
  to rebase it onto `main` (`git fetch origin && git rebase origin/main`); after the
  rebase, re-run the guard and continue. If they decline, skip the preview entirely
  and just open the URL in step 3 — herd-wake starts the server on the first request
  and the tab may show stale code, so say so.

If a preview ever prints `starting dev server for <worktree> (port from hash ...)`
it was the old script and a rogue server is now up: run `npm stop` in the worktree
at once, confirm with `herd-wake logs <worktree-dir>` that the `EADDRINUSE` loop has
stopped, then reload the tab.

Never start the dev server by hand (`npm start`, `./start.sh`) in a herd-wake-served
worktree — it fights herd-wake for the port. Opening the URL is what starts it.

## 3. Open the tab

```bash
orca tab create --url "<url>" --worktree current
```

- `--worktree current` scopes the tab to the right workspace even if the user
  switches workspaces before the tab opens.
- If the user asked for a specific path (e.g. `/login`), append it to the URL.

## When to use

- When the user asks to open the app, open the Herd URL, preview the site, open the
  dev server, or view the local site in a browser
- When you need to visually verify UI changes
- NOT automatically — only when requested or when the task requires visual verification
