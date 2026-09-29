---
name: schedule-follow-up-agent
description: Schedule an agent to run once at a future date (days or weeks out) on this Mac, using Orca automations. Use when the user wants a follow-up check, verification, soak test or reminder that an agent should carry out later ("check again in 7 days", "schedule an agent for next month", "follow up after a week", "remind an agent to verify this"), especially when the check needs local credentials (SSH keys, .env, AWS CLI) or must outlive the current session or worktree.
---

# Schedule a Follow-Up Agent

Use **Orca automations** (`orca automations create`). An automation runs an agent (Claude by
default) on this Mac at a scheduled time, in an existing Orca workspace, with everything the
Mac has: SSH keys, the repo's `.env`, the AWS CLI, `gh`. It survives the current session,
worktree deletion and app restarts, and catches up if the Mac was asleep.

## What not to use

- **Claude Code's `CronCreate`**: session-only. The job dies when the session ends or the
  worktree is deleted. Fine for "in an hour", useless for days.
- **claude.ai routines (`RemoteTrigger`)**: run in the cloud with no SSH keys, no `.env`, no
  cloud credentials. Only fit for checks that need nothing but GitHub and the web.
- **A GitHub Actions dated workflow**: runs on a CI runner that cannot reach laptop-only
  credentials or private hosts, and needs a PR to schedule.
- **launchd/cron with a hand-rolled `claude -p`**: works, but Orca already does this with run
  history, missed-run handling and a UI.

## Steps

1. **Load the version-matched reference** (flags change between Orca releases):

   ```bash
   orca status --json                                              # runtime must be ready
   orca skills get orca-cli --reference references/automations.md
   orca automations create --help
   orca automations list --json                                    # see existing ones as examples
   ```

2. **Capture baselines now.** The run agent cannot see this session. Anything it must compare
   against (metric values, counters, timestamps, what "normal" looks like) goes into the prompt
   as numbers with their UTC timestamps. Metric history may have aged out by the run date.

3. **Write a self-contained prompt** to a file. Include: the issue or PR number and a one-line
   summary of what shipped; the exact window in UTC; the exact commands (hosts, keys, database
   names, env var names, skills to use); the baselines; explicit pass/fail thresholds; what to
   post and where (one comment, with `gh issue comment`); when to reopen an issue; "read only,
   change nothing" if that applies; and a final step to disable the automation. Read issues with
   `gh api repos/<owner>/<repo>/issues/<n>` rather than `gh issue view`, which has failed on
   token scopes in automation runs.

4. **Create it as a one-shot:**

   ```bash
   orca automations create \
     --name "#<issue> <what> check" \
     --trigger "7 9 <day> <month> *" \
     --timezone America/Boise \
     --precheck 'test "$(date +%Y)" = <year>' \
     --provider claude \
     --workspace path:<primary checkout, e.g. /Users/michael/dev/crescendo/webapp> \
     --workspace-mode existing --fresh-session \
     --missed-run-grace-minutes 4320 \
     --enabled \
     --prompt "$(cat /path/to/prompt.txt)" --json
   ```

   - **One-shot**: there is no one-shot flag. A 5-field cron pinned to a day and month fires
     every year on that date, so the year `--precheck` skips later years (a non-zero exit
     records a skipped run), and the prompt's last step disables the automation.
   - **Workspace**: point at the repo's **primary checkout**, never the current worktree, which
     is usually deleted before the run date. The primary checkout holds the `.env`.
   - **Grace**: 4320 minutes (3 days) makes a run missed while the Mac slept or Orca was closed
     happen once on the next opportunity.
   - **Time**: avoid :00 and :30; give `--timezone` explicitly.

   - **Make the verdict visible.** Orca records every run as `completed` whatever the agent
     concluded, and the Automations view shows the automation's name. So end the prompt with:
     "run `orca automations edit <id> --name '<name>: PASS' --disabled` (or `: FAIL - <reason>`)"
     and "your final reply must start with `VERDICT: PASS` or `VERDICT: FAIL - <reason>`". The
     id is only known after creation: create first, then `orca automations edit <id> --prompt`
     with the id filled in. Do not tell the agent to `exit` its shell: the run's output snapshot
     then captures only the startup banner.

5. **Verify** with `orca automations show <id> --json`: convert `nextRunAt` (epoch ms) to local
   time and confirm the date, the workspace path and the precheck. Do **not** `orca automations
   run` a one-shot whose prompt posts to GitHub or reopens issues: that performs the real check
   now. A manual run also **skips the precheck**, so it proves nothing about the year guard. To
   prove the plumbing, create a separate `--disabled` test automation with a harmless
   prompt, `run` it, check `orca automations runs --id <id> --json`, then remove it.

6. **Tell the user** the automation name and id, the local run time, what it will check, the
   pass/fail thresholds, and where the result will appear.

## Facts about this Mac's Orca

- Orca launches Claude as `claude --dangerously-skip-permissions --model fable`
  (`settings.agentCmdOverrides.claude` in
  `~/Library/Application Support/orca/profiles/local-default/orca-data.json`), so an unattended
  run does not stall on permission prompts. Check that setting if runs hang.
- Managing later: `orca automations list|show|edit|runs|remove`. `edit <id> --disabled` keeps
  the run history; `remove` deletes it.
