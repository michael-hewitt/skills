#!/usr/bin/env python3
"""Read-only live fuel-trim sampler for lean-code diagnosis.

Samples Mode 01 PIDs for a period and prints per-PID min/avg/max.
Usage: live_trims.py [--port PORT] [--seconds 20] [--label idle]
"""
import argparse
import datetime
import glob
import json
import statistics
import sys
import time

import obd

PIDS = [
    ("RPM", obd.commands.RPM),
    ("COOLANT_TEMP", obd.commands.COOLANT_TEMP),
    ("SHORT_FUEL_TRIM_1", obd.commands.SHORT_FUEL_TRIM_1),
    ("LONG_FUEL_TRIM_1", obd.commands.LONG_FUEL_TRIM_1),
    ("SHORT_FUEL_TRIM_2", obd.commands.SHORT_FUEL_TRIM_2),
    ("LONG_FUEL_TRIM_2", obd.commands.LONG_FUEL_TRIM_2),
    ("MAF", obd.commands.MAF),
    ("INTAKE_PRESSURE", obd.commands.INTAKE_PRESSURE),
    ("FUEL_STATUS", obd.commands.FUEL_STATUS),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--label", default="sample")
    ap.add_argument("--log-dir", default=".")
    args = ap.parse_args()

    port = args.port or (sorted(glob.glob("/dev/cu.usbserial*")) or [None])[0]
    if not port:
        sys.exit("No /dev/cu.usbserial* device found")

    conn = obd.OBD(portstr=port, fast=False, timeout=1.0)
    if not conn.is_connected():
        sys.exit(f"Connection failed: {conn.status()}")

    samples = {name: [] for name, _ in PIDS}
    fuel_status = set()
    end = time.time() + args.seconds
    n = 0
    while time.time() < end:
        for name, cmd in PIDS:
            r = conn.query(cmd)
            if r is None or r.is_null():
                continue
            if name == "FUEL_STATUS":
                fuel_status.add(str(r.value))
            else:
                v = r.value
                samples[name].append(float(v.magnitude if hasattr(v, "magnitude") else v))
        n += 1
    conn.close()

    print(f"\n== {args.label}: {n} sweeps over {args.seconds:.0f}s ==")
    out = {"label": args.label, "sweeps": n, "fuel_status": sorted(fuel_status)}
    for name, vals in samples.items():
        if name == "FUEL_STATUS" or not vals:
            continue
        lo, avg, hi = min(vals), statistics.mean(vals), max(vals)
        out[name] = {"min": lo, "avg": round(avg, 2), "max": hi}
        print(f"{name:20s} min {lo:8.2f}  avg {avg:8.2f}  max {hi:8.2f}")
    print(f"FUEL_STATUS values seen: {sorted(fuel_status)}")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"{args.log_dir}/trims-{args.label}-{stamp}.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
