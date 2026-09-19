---
name: superhuman-docs
description: Read Superhuman Docs (formerly Coda) documents, pages and tables through the Coda REST API using Michael's two accounts, trying michael@crescendosw.com first and falling back to michael@hewitts.us. Use when the user shares a docs.superhuman.com or coda.io link, mentions a Coda doc, Superhuman doc, Timesheet doc, or asks to read, list, or export rows, tables or pages from one of their docs.
---

# Superhuman Docs (Coda) access

Superhuman Docs is the renamed Coda. Doc links look like
`https://docs.superhuman.com/d/<Name>_d<docId>/<Page>_su<pageId>#_lu<section>`
(old `https://coda.io/d/...` links work the same). The web page needs a browser login, so
never `WebFetch` it: use the bundled script, which calls the REST API at `coda.io/apis/v1`.

## Quick start

```bash
S=~/.agents/skills/superhuman-docs/scripts/coda.py
python3 $S doc    "<url>"                 # name, owner, workspace, which account opened it
python3 $S pages  "<url>"                 # pages with ids and browser links
python3 $S page   "<url>"                 # page canvas as markdown (page taken from the URL)
python3 $S tables "<url>"                 # tables and views, with the page they sit on
python3 $S rows   "<url>" "Timesheet" --limit 20   # rows with column names, markdown table
python3 $S rows   "<url>" grid-HY42dpY0HN --all --csv > rows.csv
python3 $S rows   "<url>" "Timesheet" --query 'Category:"Renewal Support"'
python3 $S columns "<url>" "Timesheet"    # column names and types
python3 $S whoami                          # which accounts have a working token
```

Add `--json` for raw API JSON. `<url>` may also be a bare doc id (`Sgv9itPXHL`).

## Accounts and fallback

Two accounts own docs. The script tries **michael@crescendosw.com** first and falls back to
**michael@hewitts.us** when the doc returns 401, 403 or 404 (Coda answers 404 for docs the
account cannot see). It prints which account opened the doc on stderr. Force one with
`--account crescendosw` or `--account hewitts`.

Tokens are read from `CODA_TOKEN_CRESCENDOSW` and `CODA_TOKEN_HEWITTS`, first from the
environment, then from the gitignored `~/.agents/.env` (the skills repo root; see its
README "Secrets" section).

**If a token is missing the script exits with code 3 and names the account.** Do not guess
or skip that account: ask the user for the API token for that email address (created at
https://coda.io/account under "API settings"), append `CODA_TOKEN_<ACCOUNT>=<token>` to
`~/.agents/.env`, and rerun. Exit code 2 means both accounts were tried and neither can see
the doc; tell the user which accounts were tried and ask them to share the doc.

## Reading a doc: what to use for what

1. `doc` confirms the link resolves and shows the owning workspace.
2. `pages` shows structure. The `_su...` suffix in a URL is a page; `#_lu...` is a section
   anchor inside it and can be ignored.
3. `page` exports the canvas text (headings, paragraphs, lists). **Tables inside a page
   export as empty headers** with no rows, so for the data run `tables` and then `rows`.
4. `rows` defaults to 50 rows and says when more exist; use `--all` for everything or
   `--query` to filter server-side. Row values use column names and the "simple" format
   (dates as ISO strings, people as names, lookups as display text).
5. `get` and `request` cover anything else in the API, e.g.
   `get "<url>" tables/grid-XXXX/rows --param sortBy=natural`.

The API is read-only in this skill. Do not create, update or delete rows or pages unless
the user explicitly asks, and then use `request` with the method they approved.

See [REFERENCE.md](REFERENCE.md) for API details, ids, rate limits and known quirks.
