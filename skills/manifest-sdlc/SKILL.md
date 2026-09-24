---
name: manifest-sdlc
description: Hand a Linear project to Manifest Automation's Agent SDLC (design, issue breakdown, build, one PR, gatekeeper review) and check on its progress. Use when the user wants Manifest, the Manifest Automation agent, or "the SDLC" to start on, pick up, or kick off a Linear project, asks how to trigger it, or asks what the agent is doing on a project.
---

# Manifest Agent SDLC

Manifest Agents (https://agents.manifestautomation.com, team slug `crescendo`) runs an
`agent-sdlc` task that drives one Linear project from engineering design to a merged PR:
design study, gatekeeper approval of the design, issues created under the project, a build
on one shared branch (`preview/ai-project-<first 8 chars of the project id>`), one PR, an
automated review, gatekeeper approval, then a QA handoff to the PM. It posts a live status
thread in Slack and replies in the Linear agent session.

Tools: the `linear` MCP server (issues, comments) and the `manifest` MCP server (task runs),
both registered at user scope with OAuth tokens in the macOS Keychain. The Linear team is
**Crescendosw** (`CRE`); the Linear user is **Manifest Automation Agent**
(`218ae536-cc3c-4358-a7f1-5d1c14a34352`).

## Starting a project

Linear no longer lets an agent be a project lead or member (since about 2026-09-24; the API
returns "Agents cannot be project leads or members" and the app no longer offers it). The
trigger is now a **kickoff issue delegated to the agent**.

1. Make sure the project exists and its description carries the whole brief: problem, goal,
   definition of done, where to look, decisions already made, out of scope. The agent works
   from the project description.
2. Create the kickoff issue in the project with `save_issue`:
   - `team`: `Crescendosw`, `project`: the project, a label that fits (`Bug`/`Feature`/`Improvement`)
   - `delegate`: `Manifest Automation Agent`. Use `delegate`, not `assignee`; Linear keeps the
     human creator as assignee automatically.
   - `title`: `Get started on <project name>`
   - `description`: the template below, filled in. **Write the full description in the
     create call.** The run starts about two seconds after creation, so editing later races it.
3. Confirm the run started (see "Checking progress") and give the user the issue link.

### Kickoff description template

Without this wording the agent treats the issue as an issue-scoped engagement ("THIS ISSUE
ONLY") and may fast-lane it as a single fix.

```markdown
This issue is the trigger for the **<Project name>** project. Linear no longer allows an agent to be set as project lead, so the project is handed to you through this issue instead. Treat it as the whole project, not a single fix: do not fast-lane it. Run the full engineering design, break it into issues under this project, build on one shared branch in `<owner/repo>`, open one PR, and take the design and the PR to the gatekeepers as usual.

Everything you need is in the project description: <list what it covers, plus any Linear documents or issues with assets>.

Repository is `<owner/repo>`. Read its `<CLAUDE.md or AGENTS.md>` first. PM for QA handoff: <name>. Gatekeepers: <names>.
```

- Repository: the team's repos are `crescendosw/webapp` (default; read `CLAUDE.md`) and
  `crescendosw/website` (read `AGENTS.md`). Name the repo explicitly when it isn't webapp.
- PM and gatekeepers: ask the user if they haven't said. Past projects used Isaiah Holt as PM
  and Isaiah Holt plus Michael Hewitt as gatekeepers. The agent cannot open Linear documents
  from its build sandbox, so paste anything word-for-word critical into the project
  description or attach it as a file.

## Steering a run

Reply in the agent session thread on the kickoff issue: `list_comments` on the issue, find the
comment "This thread is for an agent session with manifestautomationagent.", and `save_comment`
with `parentId` set to it. Linear forwards the reply to the agent as a new prompt. Gate
approvals and answers to its questions go the same way (or in the Slack thread it opens).

## Checking progress

- `list_task_runs` (team `crescendo`, task `agent-sdlc`): the newest run's `created_at` should
  be seconds after the kickoff issue.
- `get_task_run_events`: the first event is the Linear trigger; later `model_response` events
  carry the agent's own summaries and `session_status` (`awaiting_input` means it is waiting on
  a person); `channel_outbound` events show the Slack status posts.
- The run's first reply names the branch and phase. Nothing is built before the design gate.
