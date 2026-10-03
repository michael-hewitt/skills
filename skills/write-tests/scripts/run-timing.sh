#!/bin/zsh
# Usage: run-timing.sh <repo-root> <out-dir> — full parallel Pest run (PROCS workers, default 7) with JUnit timings.
set -u
ROOT=${1:A}; OUT=${2:A}; mkdir -p "$OUT"; cd "$ROOT"
/usr/bin/time -l php vendor/bin/pest --parallel --processes=${PROCS:-7} --log-junit "$OUT/junit.xml" > "$OUT/run.log" 2>&1
echo "exit $?" >> "$OUT/run.log"
