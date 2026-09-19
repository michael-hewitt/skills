---
name: accs-weekly-summary
description: Generate Michael's weekly ACCS billable-hours summary from the Timesheet Superhuman doc and copy it to the clipboard as rich text. Use when the user asks for the ACCS weekly summary, weekly status report, billable-hours summary, or to report hours to ACCS leadership.
---

# ACCS Weekly Billable-Hours Summary

Builds the weekly report ACCS leadership receives: a Helvetica rich-text bulleted
list of Michael Hewitt's billable entries for the current week (Sunday through
Saturday) with a weekly total and month total(s), copied to the macOS clipboard.

## Step 1: Pull the week's entries

```bash
python3 ~/.agents/skills/accs-weekly-summary/scripts/weekly_hours.py
# --date 2026-09-16   any date inside a different target week
# --person "..."      someone other than Michael Hewitt
```

The script fetches the Timesheet table (doc `Sgv9itPXHL`) through the
superhuman-docs skill's `coda.py`, so its token rules apply: if it exits with
code 3, ask the user for the missing Coda API token — never skip or guess.

It prints one line per entry (date, pre-formatted duration, category, notes),
then the exact totals lines to use, and on stderr the latest entry date in the
sheet. **If the latest entry is earlier than the report day, warn the user the
week may be incomplete before copying.**

## Step 2: Compose the bullets

One bullet per entry, in the script's order:

```
* **Title** (duration) - Description
```

- **Title**: 1-3 words you write from the entry's notes (e.g. "Revenue Projection").
- **Duration**: exactly as the script printed it ("5m", "30m", "1h", "3h 45m").
  Do not recompute.
- **Description**: brief rewrite of the notes; keep names in parentheses
  ("(Lendy)") when the notes credit someone.

After the bullets, the totals, bolded labels, exactly as the script printed
them and in the script's order:

- `**Total this week:** 3h 45m`
- then `**<Month> running total:** ...` — and, only when the week spans a month
  boundary, `**<OldMonth> final total:** ...` last.

## Step 3: Copy as rich text

Follow the copy-to-clipboard skill (`~/.claude/skills/copy-to-clipboard/SKILL.md`)
for the mechanics. Summary of what matters here: wrap the fragment in
`<div style="font-family: Helvetica, sans-serif; font-size: 12px;">`, use `<ul>`
and `<b>`, ASCII punctuation only (`-` not em dashes, straight quotes, `&amp;`
for &), then:

```bash
textutil -format html -inputencoding UTF-8 -convert rtf -stdout summary.html | pbcopy -Prefer rtf
osascript -e 'the clipboard as «class RTF »' >/dev/null && echo OK
```

Finally, show the user the summary as markdown so they can check it before
pasting, and remind them the clipboard holds only the RTF flavor (plain-text
paste targets get nothing).
