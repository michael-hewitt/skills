# Michael's agent skills

Personal skills for Claude Code and other agents. Each skill lives in `skills/<name>/` with
a `SKILL.md`; `~/.claude/skills` and `~/.codex/skills` are both symlinks to `skills/`, and Codex also reads
`~/.agents/skills` directly.

New skills are picked up by `git status` like any other file; `.gitignore` excludes only
`.env`, the `skills/synced/` cache and build noise. Third-party skills are committed too, and
their sources are recorded in `skills-lock.json` / `.skill-lock.json`, so updating them
shows up as a normal diff to review.

## Secrets

Some skills need API tokens. They are read from environment variables first, then from
`.env` at the root of this repository. `.env` is gitignored and must never be committed or copied into a skill directory.

Copy this template to `.env` and fill in the values:

```bash
# Superhuman Docs (formerly Coda) API tokens, used by skills/superhuman-docs.
# One per account; create them at https://coda.io/account -> "API settings".
CODA_TOKEN_CRESCENDOSW=   # michael@crescendosw.com  (tried first)
CODA_TOKEN_HEWITTS=       # michael@hewitts.us       (fallback)
```

**Agents: if a required secret is absent, stop and ask the user for it**, then add it to
`.env` and continue. Do not work around a missing token by skipping that account or guessing.
The `superhuman-docs` script exits with code 3 and names the missing variable and account.
