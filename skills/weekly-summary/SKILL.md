---
name: weekly-summary
description: Generate the weekly status report in docs/weekly-summaries/ covering Michael's pull requests merged to main since Sunday, plus the rendered PDF. Use when the user asks for a weekly summary, weekly status report, or "my PRs since Sunday".
---

# Weekly Summary

Produces `docs/weekly-summaries/week-of-<Sunday>.md` and a matching PDF for the window Sunday through Saturday.

## Scope

- Include every pull request authored by Michael (`michael-hewitt`) merged to `main` in the window, plus any merged after the previous report was written (say so in the preamble).
- Include Renovate dependency PRs in their own table.
- Exclude PRs authored by Graham; say so in the preamble.
- **Do not include billable hours.** Michael records hours in Coda, out of band. Earlier reports (through week-of-2026-08-09) carried a Billable Hours table; that practice ended with the week of 2026-08-23 and must not return.

## Gathering

```bash
gh pr list --repo accsTechnology/classicalchristian-platform --state merged --search "merged:>=<Sunday>" --limit 200 --json number,title,author,mergedAt,closingIssuesReferences
gh issue list --repo accsTechnology/classicalchristian-platform --state closed --search "closed:>=<Sunday>" --json number,title,closedAt,stateReason
gh run list --repo accsTechnology/classicalchristian-platform --workflow deploy-production.yml --json createdAt,headSha,conclusion
```

Read each of Michael's PR bodies (`gh pr view N --json body`) for the narratives. Merged dates in tables use the `mergedAt` date.

## Format (follow the most recent report)

1. `# Weekly Summary - Week of <Sunday>` and an italic preamble: window, PR counts (feature vs. dependency), exclusions.
2. `## Highlights` — bold-led bullets, one per theme, with issue/PR numbers.
3. `---` then `## Merged Pull Requests` with one `###` section per theme: a `| PR | Title | Closes | Merged |` table followed by narrative paragraphs led by the PR number. Dependencies get a `| PR | Title | Merged |` table and a one-sentence note.
4. `## Issues Closed` — count, linked list, and notes on anything not closed as completed or closed without a PR; list notable issues opened in the window.
5. `## Deployed` — production/staging promotion counts and dates, the SHA both environments sit at, anything on `main` awaiting promotion, and documented post-deploy steps (state them as the PRs' documented steps, not as verified-open work).

Use `--` for dashes in prose, en dashes in school-year spans ("2026–27"), and full GitHub URLs for every PR/issue link.

## Render

```bash
cd docs/weekly-summaries
pandoc week-of-<Sunday>.md --pdf-engine=weasyprint -H ~/.agents/skills/weekly-summary/assets/pdf-tables.html -o week-of-<Sunday>.pdf
```

The PDF is gitignored (`docs/weekly-summaries/*.pdf`) and stays local; check page 1 and a narrative page with `pdftoppm`.

## Deliver

Commit the markdown only, on a `weekly-summary-<Sunday>` branch, open a PR ("Weekly summary for the week of <Sunday>", documentation only) with auto-merge, and monitor CI per the `pull-request` skill.
