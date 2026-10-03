#!/usr/bin/env python3
"""Per-test-file line coverage for Vitest, to delete and merge tests without losing coverage.

Vitest cannot attribute coverage to single tests, so this runs each test file alone with
v8 coverage and records the lines it executes. Run from the directory you run vitest in
(the repo root of a workspace); needs @vitest/coverage-v8 matching the vitest version.

    vitest-cov.py run <out.json> --all                 # every test file (the baseline)
    vitest-cov.py run <out.json> <test files...>       # just these files
    vitest-cov.py lost <baseline.json> <before.json> <after.json>
    vitest-cov.py unique <baseline.json> [--timing report.json]
    vitest-cov.py compare <a.json> <b.json>

lost:    lines that <before> covered, <after> no longer covers, and no other file in
         <baseline> covers. Exit 1 if any. Record <before> over the files you are about to
         edit, edit (delete, merge, shrink), then record <after> over the same files (deleted
         files simply drop out). Change only tests between the runs, or line numbers shift.
unique:  per file, the lines no other file covers; files with 0 are coverage-redundant
         candidates (review by hand: line coverage cannot see assertion strength).
compare: whole-suite totals and lines covered only by one side, for a final check.

Environment: PROCS (parallel vitest processes, default half the cores), VITEST_CMD
(default "pnpm exec vitest", "yarn vitest" or "npx vitest" from the lockfile),
TEST_PATTERN (regex for --all, default .test/.spec JS/TS files).
"""
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor


def vitest_cmd():
    if os.environ.get('VITEST_CMD'):
        return shlex.split(os.environ['VITEST_CMD'])
    if os.path.exists('pnpm-lock.yaml'):
        return ['pnpm', 'exec', 'vitest']
    if os.path.exists('yarn.lock'):
        return ['yarn', 'vitest']
    return ['npx', 'vitest']


def covered_lines(coverage_final):
    """{source file: sorted lines} from an istanbul coverage-final.json."""
    root = os.getcwd()
    result = {}
    for path, data in json.load(open(coverage_final)).items():
        lines = set()
        for sid, count in data['s'].items():
            if count > 0:
                lines.add(data['statementMap'][sid]['start']['line'])
        if lines:
            result[os.path.relpath(path, root)] = sorted(lines)
    return result


def run_one(test_file):
    with tempfile.TemporaryDirectory(prefix='vitest-cov-') as out:
        report = os.path.join(out, 'report.json')
        proc = subprocess.run(
            vitest_cmd() + ['run', test_file, '--coverage.enabled', '--coverage.provider=v8',
                            '--coverage.reporter=json', f'--coverage.reportsDirectory={out}',
                            '--reporter=json', f'--outputFile.json={report}'],
            capture_output=True, text=True)
        final = os.path.join(out, 'coverage-final.json')
        tail = '\n'.join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
        if not os.path.exists(final) or not os.path.exists(report):
            sys.exit(f'no coverage for {test_file} (exit {proc.returncode}):\n{tail}')
        # The filter is a substring match, and a path outside the include globs still writes an
        # empty coverage report: make sure vitest ran exactly this file
        ran = {os.path.relpath(r['name']) for r in json.load(open(report))['testResults']}
        if ran != {os.path.normpath(test_file)}:
            sys.exit(f'vitest ran {sorted(ran) or "no files"} for {test_file}; is it outside the include globs?')
        if proc.returncode != 0:
            print(f'warning: {test_file} failed (exit {proc.returncode}); its coverage is partial', file=sys.stderr)
        return test_file, covered_lines(final)


def cmd_run(out, files):
    if files == ['--all']:
        pattern = re.compile(os.environ.get('TEST_PATTERN', r'\.(test|spec)\.[cm]?[jt]sx?$'))
        listed = subprocess.run(['git', 'ls-files'], capture_output=True, text=True, check=True).stdout
        files = [f for f in listed.splitlines() if pattern.search(f)]
    files = [f for f in files if os.path.exists(f)]
    procs = int(os.environ.get('PROCS', max(1, (os.cpu_count() or 2) // 2)))
    result = {}
    with ThreadPoolExecutor(procs) as pool:
        for done, (test_file, lines) in enumerate(pool.map(run_one, files), 1):
            result[test_file] = lines
            print(f'[{done}/{len(files)}] {test_file}: {sum(map(len, lines.values()))} lines', file=sys.stderr)
    json.dump(result, open(out, 'w'))


def union(cov, only=None, exclude=()):
    lines = set()
    for test_file, sources in cov.items():
        if (only is not None and test_file not in only) or test_file in exclude:
            continue
        for source, numbers in sources.items():
            lines.update((source, n) for n in numbers)
    return lines


def print_lines(lines, limit=200):
    by_source = {}
    for source, n in sorted(lines):
        by_source.setdefault(source, []).append(n)
    for source, numbers in list(by_source.items())[:limit]:
        print(f'  {source}: {", ".join(map(str, numbers))}')


def cmd_lost(baseline_path, before_path, after_path):
    baseline, before, after = (json.load(open(p)) for p in (baseline_path, before_path, after_path))
    others = union(baseline, exclude=set(before))
    lost = union(before) - union(after) - others
    stopped = union(before) - union(after)
    print(f'{len(stopped)} lines no longer covered by these files; {len(lost)} LOST from the suite')
    print_lines(lost)
    sys.exit(1 if lost else 0)


def cmd_unique(baseline_path, timing_path=None):
    baseline = json.load(open(baseline_path))
    durations = {}
    if timing_path:
        root = os.getcwd()
        for r in json.load(open(timing_path))['testResults']:
            durations[os.path.relpath(r['name'], root)] = r['endTime'] - r['startTime']
    counts = {}
    for source_lines in baseline.values():
        for source, numbers in source_lines.items():
            for n in numbers:
                counts[(source, n)] = counts.get((source, n), 0) + 1
    rows = []
    for test_file, sources in baseline.items():
        unique = sum(1 for s, ns in sources.items() for n in ns if counts[(s, n)] == 1)
        rows.append((unique, -durations.get(test_file, 0), test_file))
    print('unique lines  ms  file   (0 unique = every line it runs is covered elsewhere)')
    for unique, negative_ms, test_file in sorted(rows):
        print(f'{unique:6d} {-negative_ms:7.0f}  {test_file}')


def cmd_compare(a_path, b_path):
    a, b = union(json.load(open(a_path))), union(json.load(open(b_path)))
    print(f'A covers {len(a)} lines, B covers {len(b)}')
    print(f'only in A: {len(a - b)}')
    print_lines(a - b)
    print(f'only in B: {len(b - a)}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    command, rest = sys.argv[1], sys.argv[2:]
    if command == 'run' and len(rest) >= 2:
        cmd_run(rest[0], rest[1:])
    elif command == 'lost' and len(rest) == 3:
        cmd_lost(*rest)
    elif command == 'unique':
        cmd_unique(rest[0], rest[2] if len(rest) == 3 and rest[1] == '--timing' else None)
    elif command == 'compare' and len(rest) == 2:
        cmd_compare(*rest)
    else:
        sys.exit(__doc__)
