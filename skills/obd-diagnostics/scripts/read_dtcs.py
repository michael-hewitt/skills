#!/usr/bin/env python3
"""Read-only OBD-II diagnostic scan via an OBDLink/ELM/STN USB adapter.

Reads MIL status, stored (Mode 03), pending (Mode 07), and permanent (Mode 0A)
DTCs plus the freeze-frame DTC (Mode 02 PID 02). Never clears or writes anything.

Usage: read_dtcs.py [--port /dev/cu.usbserial-XXXX] [--log-dir DIR]
"""
import argparse
import datetime
import glob
import json
import logging
import sys

import obd
from obd import OBDCommand
from obd.decoders import dtc
from obd.protocols import ECU


def find_port(explicit=None):
    if explicit:
        return explicit
    candidates = sorted(
        glob.glob("/dev/cu.usbserial*")
        + glob.glob("/dev/cu.usbmodem*")
        + glob.glob("/dev/cu.OBDLink*")
    )
    if not candidates:
        sys.exit("No USB serial device found under /dev/cu.* — is the adapter plugged in?")
    if len(candidates) > 1:
        print(f"Multiple candidate ports found, using first: {candidates}", file=sys.stderr)
    return candidates[0]


def fmt(response):
    if response is None or response.is_null():
        return None
    return response.value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--log-dir", default=".")
    args = ap.parse_args()

    port = find_port(args.port)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_log = f"{args.log_dir}/obd-raw-{stamp}.log"

    # Capture the full raw ELM conversation for later reference.
    fh = logging.FileHandler(raw_log)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    obd.logger.setLevel(logging.DEBUG)
    obd.logger.addHandler(fh)

    print(f"Connecting on {port} (raw log: {raw_log}) ...")
    conn = obd.OBD(portstr=port, fast=False, timeout=1.0)

    if not conn.is_connected():
        sys.exit(
            f"Connection failed (status: {conn.status()}). "
            "Check ignition is ON and adapter is seated in the OBD port."
        )

    print(f"Adapter port: {conn.port_name()}")
    print(f"Protocol: {conn.protocol_name()} (id {conn.protocol_id()})")

    results = {"port": port, "protocol": conn.protocol_name(), "timestamp": stamp}

    # Adapter identification and battery voltage (harmless adapter-level queries).
    for name, cmd in [("adapter_id", obd.commands.ELM_VERSION),
                      ("adapter_voltage", obd.commands.ELM_VOLTAGE)]:
        r = conn.query(cmd)
        results[name] = str(fmt(r))
        print(f"{name}: {results[name]}")

    # MIL / DTC count / monitor status (Mode 01 PID 01)
    r = conn.query(obd.commands.STATUS)
    if r and not r.is_null():
        results["mil_on"] = bool(r.value.MIL)
        results["dtc_count"] = int(r.value.DTC_count)
        print(f"MIL (check engine light) commanded on: {results['mil_on']}")
        print(f"DTC count reported: {results['dtc_count']}")
    else:
        results["mil_on"] = None
        print("STATUS query returned no data")

    # Stored DTCs — Mode 03
    r = conn.query(obd.commands.GET_DTC)
    results["stored_dtcs"] = fmt(r) or []
    print(f"Stored DTCs (Mode 03): {results['stored_dtcs']}")

    # Pending DTCs — Mode 07
    r = conn.query(obd.commands.GET_CURRENT_DTC)
    results["pending_dtcs"] = fmt(r) or []
    print(f"Pending DTCs (Mode 07): {results['pending_dtcs']}")

    # Permanent DTCs — Mode 0A (not built into python-OBD; read-only custom query)
    perm_cmd = OBDCommand("GET_PERMANENT_DTC", "Permanent DTCs", b"0A", 0, dtc, ECU.ALL, False)
    r = conn.query(perm_cmd, force=True)
    results["permanent_dtcs"] = fmt(r) or []
    print(f"Permanent DTCs (Mode 0A): {results['permanent_dtcs']}")

    # Freeze frame DTC — Mode 02 PID 02 (force: some ECUs answer even when
    # they don't advertise support for the PID)
    r = conn.query(obd.commands.DTC_FREEZE_DTC, force=True)
    results["freeze_frame_dtc"] = str(fmt(r))
    print(f"Freeze-frame DTC (Mode 02 PID 02): {results['freeze_frame_dtc']}")

    conn.close()

    out = f"{args.log_dir}/obd-results-{stamp}.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    main()
