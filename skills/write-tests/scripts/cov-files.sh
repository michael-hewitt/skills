#!/bin/zsh
# Usage: cov-files.sh <out.json> <test-file-or-dir>...   (run from the repo root)
# Runs the given tests serially with per-test line coverage and writes the union:
# {lines: ["file:line", ...], tests: N, time: seconds}. Compare two with cov-diff.py / cov-global.py.
set -u
OUT=$1; shift
TOOLS=${0:A:h}
ROOT=$(pwd)
TMP=$(mktemp -d)
"$TOOLS/pcov.sh" "$ROOT" "$TMP/pcov.ini" || exit 1
"$TOOLS/phpunit-config.sh" "$ROOT" "$TMP/phpunit.xml" 'TestSuiteTools\LineCoverageExtension'
PHPRC="$TMP/pcov.ini" LINECOV_DIR="$TMP/cov" LINECOV_ROOT="$ROOT" php vendor/bin/pest -c "$TMP/phpunit.xml" "$@" > "$TMP/run.log" 2>&1
rc=$?
python3 - "$TMP/cov" "$OUT" <<'PY'
import glob, json, sys
lines = set(); n = 0; t = 0.0
for f in glob.glob(sys.argv[1] + '/*.jsonl'):
    for raw in open(f):
        r = json.loads(raw); n += 1; t += r['time']
        cov = r['cov'] if isinstance(r['cov'], dict) else {}
        for file, ls in cov.items():
            if file.startswith(('app/', 'routes/', 'resources/views/')):
                lines.update(f"{file}:{l}" for l in ls)
json.dump({'lines': sorted(lines), 'tests': n, 'time': round(t, 2)}, open(sys.argv[2], 'w'))
print(f"{n} tests, {t:.1f}s, {len(lines)} covered lines -> {sys.argv[2]}")
PY
grep -a -E "Tests:|FAILED" "$TMP/run.log" | sed 's/\x1b\[[0-9;]*m//g'
exit $rc
