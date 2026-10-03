#!/bin/zsh
# Usage: run-serial.sh <repo-root> <out-dir> [pest paths...]
# The suite in ONE process (no --parallel) with JUnit timings — the honest "serial wall clock" number.
# A single process accumulates memory over thousands of tests, so the generated config lifts the memory cap.
set -u
ROOT=${1:A}; OUT=${2:A}; shift 2
TOOLS=${0:A:h}
mkdir -p "$OUT"
"$TOOLS/phpunit-config.sh" "$ROOT" "$OUT/phpunit.xml"
cd "$ROOT"
/usr/bin/time -l php vendor/bin/pest -c "$OUT/phpunit.xml" --log-junit "$OUT/junit.xml" "$@" > "$OUT/run.log" 2>&1
echo "exit $?" >> "$OUT/run.log"
