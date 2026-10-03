#!/bin/zsh
# Usage: profile.sh <out-prefix> <test-file-or-dir>...   (run from the repo root)
# Samples wall-clock stacks of a serial Pest run with Excimer (PROFILE_PERIOD seconds, default 0.002)
# and writes collapsed stacks to <out-prefix>.<pid>. Rank frames with topframes.py.
set -u
OUT=${1:A}; shift
TOOLS=${0:A:h}
ROOT=$(pwd)
EXCIMER_SO=${EXCIMER_SO:-/opt/homebrew/opt/excimer@8.4/excimer.so}
if [[ ! -f "$EXCIMER_SO" ]]; then
    echo "Excimer not found at $EXCIMER_SO. Install it (brew install shivammathur/extensions/excimer@8.4) or set EXCIMER_SO." >&2
    exit 1
fi
TMP=$(mktemp -d)
"$TOOLS/phpunit-config.sh" "$ROOT" "$TMP/phpunit.xml" 'TestSuiteTools\ProfileExtension'
PROFILE_OUT="$OUT" PROFILE_PERIOD=${PROFILE_PERIOD:-0.002} php -d extension="$EXCIMER_SO" vendor/bin/pest -c "$TMP/phpunit.xml" "$@" --compact
