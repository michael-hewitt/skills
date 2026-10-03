#!/bin/zsh
# Usage: run-cov.sh <repo-root> <out-dir> [pest path]
# Full parallel Pest run (PROCS workers, default 7) recording, per test, the app/, routes/ and
# compiled-view lines it executed plus wall and CPU time: <out-dir>/cov/*.jsonl, <out-dir>/junit.xml.
set -u
ROOT=${1:A}; OUT=${2:A}; shift 2
TOOLS=${0:A:h}
mkdir -p "$OUT/cov"
find "$OUT/cov" -name '*.jsonl' -delete
"$TOOLS/pcov.sh" "$ROOT" "$OUT/pcov.ini" || exit 1
"$TOOLS/phpunit-config.sh" "$ROOT" "$OUT/phpunit.xml" 'TestSuiteTools\LineCoverageExtension'
cd "$ROOT"
PHPRC="$OUT/pcov.ini" LINECOV_DIR="$OUT/cov" LINECOV_ROOT="$ROOT" \
    /usr/bin/time -l php vendor/bin/pest -c "$OUT/phpunit.xml" --parallel --processes=${PROCS:-7} --log-junit "$OUT/junit.xml" "$@" > "$OUT/run.log" 2>&1
echo "exit $?" >> "$OUT/run.log"
