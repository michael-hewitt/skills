#!/bin/zsh
# Usage: pcov.sh <repo-root> <out.ini> — an ini loading pcov for app/, routes/ and compiled views.
# PHPRC=<out.ini> reaches ParaTest workers even under Laravel Herd, which overrides PHP_INI_SCAN_DIR.
set -eu
ROOT=${1:A}; OUT=$2
PCOV_SO=${PCOV_SO:-/opt/homebrew/opt/pcov@8.4/pcov.so}
if [[ ! -f "$PCOV_SO" ]]; then
    echo "pcov not found at $PCOV_SO. Install it (macOS/Homebrew: brew tap shivammathur/extensions && brew install shivammathur/extensions/pcov@8.4) or set PCOV_SO=/path/to/pcov.so." >&2
    exit 1
fi
cat > "$OUT" <<INI
extension=$PCOV_SO
pcov.enabled=1
pcov.directory=$ROOT
pcov.exclude="~/(vendor|node_modules|tests|database|config|bootstrap|public|lang)/~"
INI
