#!/usr/bin/env python3
"""Pull this week's ACCS billable hours from the Timesheet Superhuman doc.

Fetches the Timesheet table via the superhuman-docs coda.py script, filters to
one person's entries for the Sunday-Saturday week containing --date (default
today), and prints each entry plus the weekly total and month total(s). Month
totals follow the ACCS report convention: normally one running total for the
current month; when the week spans a month boundary, the new month's running
total first, then the old month's final total.

Durations are formatted as "Hh Mm" with minutes rounded to the nearest integer;
the hour part is omitted under one hour and the minutes part is omitted on
exact hours.
"""

import argparse
import csv
import io
import subprocess
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

CODA = Path.home() / ".agents/skills/superhuman-docs/scripts/coda.py"
DOC = "Sgv9itPXHL"  # "Timesheet Reloaded"
TABLE = "Timesheet"


def fmt_duration(hours: float) -> str:
    minutes = round(hours * 60)
    h, m = divmod(minutes, 60)
    if h == 0:
        return f"{m}m"
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="any date inside the target week, YYYY-MM-DD (default today)")
    ap.add_argument("--person", default="Michael Hewitt")
    ap.add_argument("--doc", default=DOC)
    args = ap.parse_args()

    anchor = date.fromisoformat(args.date) if args.date else date.today()
    sunday = anchor - timedelta(days=(anchor.weekday() + 1) % 7)
    saturday = sunday + timedelta(days=6)

    proc = subprocess.run(
        [sys.executable, str(CODA), "rows", args.doc, TABLE, "--all", "--csv"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode
    rows = list(csv.DictReader(io.StringIO(proc.stdout)))
    mine = [r for r in rows if r["Created By"] == args.person and r["Date"]]

    week = [r for r in mine if sunday.isoformat() <= r["Date"][:10] <= saturday.isoformat()]
    week.sort(key=lambda r: (r["Date"][:10], r["Start"]))

    print(f"Week of {sunday} to {saturday} for {args.person}")
    if not week:
        print("No entries this week.")
    for r in week:
        h = float(r["Hours"] or 0)
        print(f"{r['Date'][:10]} | {fmt_duration(h)} | {r['Category']} | {r['Notes']}")

    weekly = sum(float(r["Hours"] or 0) for r in week)
    by_month = defaultdict(float)
    for r in mine:
        by_month[r["Date"][:7]] += float(r["Hours"] or 0)

    print()
    print(f"Weekly total: {fmt_duration(weekly)}")
    old_key, new_key = sunday.strftime("%Y-%m"), saturday.strftime("%Y-%m")
    if old_key == new_key:
        month_name = sunday.strftime("%B")
        print(f"{month_name} running total: {fmt_duration(by_month[new_key])}")
    else:
        print(f"{saturday.strftime('%B')} running total: {fmt_duration(by_month[new_key])}")
        print(f"{sunday.strftime('%B')} final total: {fmt_duration(by_month[old_key])}")

    latest = max((r["Date"][:10] for r in mine), default="none")
    print(f"\nLatest entry in sheet: {latest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
