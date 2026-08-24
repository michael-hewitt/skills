#!/bin/bash
# Idempotent environment setup + serial-port detection for OBD-II diagnostics.
# Run once BEFORE the adapter is connected (records a baseline), and again
# AFTER connecting (prints the newly appeared serial device).
set -euo pipefail

DIAG_DIR="$HOME/.cache/obd-diag"
VENV="$DIAG_DIR/venv"
BASELINE="$DIAG_DIR/serial-baseline.txt"

mkdir -p "$DIAG_DIR"

echo "== Python environment =="
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  echo "Created venv at $VENV"
fi
"$VENV/bin/pip" install --quiet obd pyserial
"$VENV/bin/python" -c 'import obd, serial; print("python-OBD", getattr(obd, "__version__", "ok"), "/ pyserial", serial.__version__)'

echo
echo "== Serial devices (/dev/cu.*) =="
CURRENT="$(ls /dev/cu.* 2>/dev/null || true)"
echo "$CURRENT"

if [ -f "$BASELINE" ]; then
  NEW="$(comm -13 <(sort "$BASELINE") <(echo "$CURRENT" | sort) || true)"
  echo
  if [ -n "$NEW" ]; then
    echo "== NEW device(s) since baseline =="
    echo "$NEW"
  else
    echo "No new serial devices since baseline ($BASELINE)."
    echo "If the adapter is plugged in, check: ioreg -p IOUSB -l -w0 | grep -E '\\+-o |Product Name'"
    echo "and the macOS 'Allow accessory to connect?' prompt (System Settings > Privacy & Security)."
  fi
else
  echo "$CURRENT" > "$BASELINE"
  echo
  echo "Baseline saved to $BASELINE — connect the adapter, then run this script again."
fi
