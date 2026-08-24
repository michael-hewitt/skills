#!/usr/bin/env python3
"""Poll coolant temp (read-only) until it reaches a target, then exit 0.

Run in the background while the engine idles; take warm measurements when it
exits. Exits 1 on timeout. Usage: wait_warm.py [--port PORT] [--target 80]
[--timeout-min 15]
"""
import argparse
import glob
import sys
import time

import obd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--target", type=float, default=80, help="target coolant temp, deg C")
    ap.add_argument("--timeout-min", type=float, default=15)
    args = ap.parse_args()

    port = args.port or (sorted(glob.glob("/dev/cu.usbserial*")) or [None])[0]
    if not port:
        sys.exit("No /dev/cu.usbserial* device found")

    conn = obd.OBD(portstr=port, fast=False, timeout=1.0)
    if not conn.is_connected():
        sys.exit(f"Connection failed: {conn.status()}")

    start = time.time()
    while time.time() - start < args.timeout_min * 60:
        r = conn.query(obd.commands.COOLANT_TEMP)
        if r and not r.is_null():
            t = float(r.value.magnitude)
            print(f"{time.strftime('%H:%M:%S')} coolant {t:.0f}C", flush=True)
            if t >= args.target:
                print("WARM: target reached")
                conn.close()
                sys.exit(0)
        time.sleep(20)

    conn.close()
    print(f"TIMEOUT: did not reach {args.target:.0f}C in {args.timeout_min:.0f} min")
    sys.exit(1)


if __name__ == "__main__":
    main()
