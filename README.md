# Michael's agent skills

Personal skills for Claude Code and other agents. Each skill lives in `skills/<name>/` with
a `SKILL.md`; `~/.claude/skills` is a symlink to `skills/`.

`.gitignore` ignores everything by default, so new skill files must be added with
`git add -f`. Third-party skills are tracked in `skills-lock.json` / `.skill-lock.json`.

## Secrets

Some skills need API tokens. They are read from environment variables first, then from
`.env` at the root of this repository. `.env` is gitignored (explicitly, so even `git add -f`
will not pick it up) and must never be committed or copied into a skill directory.

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
