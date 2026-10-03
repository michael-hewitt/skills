#!/usr/bin/env python3
"""Rank a Vitest JSON report: serial cost, median, slow tail, slowest files and tests.

    vitest run --reporter=default --reporter=json --outputFile.json=report.json
    vitest-stats.py report.json [--top 25] [--markdown]

--markdown prints a table of the slowest tests for $GITHUB_STEP_SUMMARY.
The JSON report has no environment/import/transform times: read those from the
"Duration" line vitest prints at the end of the run.
"""
import argparse
import json
import os
import statistics

parser = argparse.ArgumentParser()
parser.add_argument('report')
parser.add_argument('--top', type=int, default=25)
parser.add_argument('--markdown', action='store_true')
args = parser.parse_args()

report = json.load(open(args.report))
root = os.getcwd()
files, tests = [], []
for result in report['testResults']:
    name = os.path.relpath(result['name'], root)
    durations = [a.get('duration') or 0 for a in result['assertionResults']]
    files.append((result['endTime'] - result['startTime'], len(durations), name))
    for assertion, duration in zip(result['assertionResults'], durations):
        tests.append((duration, name, assertion['fullName'], assertion['status']))
files.sort(reverse=True)
tests.sort(reverse=True)

if args.markdown:
    print(f'### {args.top} slowest tests\n')
    print('| ms | File | Test |')
    print('|---:|---|---|')
    for duration, name, full_name, _ in tests[: args.top]:
        cell = full_name.replace('|', '\\|')
        print(f'| {duration:.0f} | `{name}` | {cell} |')
    raise SystemExit

durations = [t[0] for t in tests]
total = sum(durations)
print(f'{len(files)} files, {len(tests)} tests, {total / 1000:.1f} s summed test time')
print(f'median test {statistics.median(durations):.1f} ms')
for limit in (100, 1000):
    slow = [d for d in durations if d > limit]
    print(f'tests over {limit} ms: {len(slow)}, {sum(slow) / 1000:.1f} s ({100 * sum(slow) / max(total, 1):.0f}% of test time)')
skipped = [t for t in tests if t[3] in ('skipped', 'pending', 'todo')]
if skipped:
    print(f'skipped: {len(skipped)}')

print(f'\nslowest files (ms, tests): the slowest one sets the floor for wall time')
for duration, count, name in files[: args.top]:
    print(f'{duration:8.0f} {count:5d}  {name}')
print('\nslowest tests (ms)')
for duration, name, full_name, _ in tests[: args.top]:
    print(f'{duration:8.0f}  {name} > {full_name}')
