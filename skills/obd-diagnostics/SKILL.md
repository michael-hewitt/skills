---
name: obd-diagnostics
description: Read vehicle diagnostic trouble codes (check-engine codes) over a USB OBD-II adapter (OBDLink EX or other ELM327/STN-compatible) on macOS, including environment setup, driver/permission checks, and port detection. Use when the user wants to read or scan car codes, diagnose a check engine light, or mentions OBD, OBD-II, DTCs, OBDLink, or ELM327.
---

# OBD-II Diagnostics (read-only)

Read DTCs from a vehicle through an OBDLink EX (or other ELM/STN) USB adapter.

## Safety rules — READ ONLY

Every session is read-only unless the user explicitly authorizes a specific write
operation in the current conversation. Never: clear DTCs (Mode 04), reset monitors
or learned values, run actuator tests, do ECU coding/adaptations, security access,
flashing, arbitrary CAN messages, UDS writes, or persistent adapter config changes.
Harmless adapter init/query commands (reset, echo off, version, voltage, protocol
detect) are fine. If a write seems necessary, stop and explain it first.

## Workflow

1. **Baseline (before hardware is connected)** — run `scripts/setup.sh`.
   It records existing `/dev/cu.*` devices, creates a Python venv at
   `~/.cache/obd-diag/venv`, and installs `obd` + `pyserial`. No driver is
   installed: macOS 14+ ships Apple's built-in FTDI driver which handles the
   OBDLink EX (FTDI VID 0x0403, PID 0x6015). Only consider the official FTDI VCP
   driver if the USB device enumerates but no `/dev/cu.usbserial*` appears —
   and ask the user before installing anything (see REFERENCE.md).

2. **Have the user connect hardware.** Ask them to: plug the adapter into the
   car's OBD-II port, connect USB to the Mac, put the car in Park with parking
   brake set, turn ignition ON with engine OFF, and click **Allow** if macOS
   shows an "Allow accessory to connect?" prompt (that prompt is the only
   macOS "permission" normally involved; serial devices are already 0666).

3. **Identify the port.** Run `scripts/setup.sh` again — it diffs against the
   baseline and prints the new device (e.g. `/dev/cu.usbserial-223230395038`).
   Verify with `ioreg -p IOUSB -l -w0 | grep -E '\+-o |Product Name'` that an
   OBDLink/FTDI device enumerated. Note: `system_profiler SPUSBDataType` can
   print nothing on some machines — use `ioreg`. Do not guess a port.

4. **Scan.** Run:

   ```bash
   ~/.cache/obd-diag/venv/bin/python \
     ~/.agents/skills/obd-diagnostics/scripts/read_dtcs.py \
     --port /dev/cu.usbserial-XXXX --log-dir ~/.cache/obd-diag
   ```

   It connects, auto-detects protocol, and reads: adapter ID + battery voltage,
   MIL status + DTC count (Mode 01 PID 01), stored DTCs (Mode 03), pending
   DTCs (Mode 07), permanent DTCs (Mode 0A), freeze-frame DTC (Mode 02 PID 02).
   Raw ELM log and parsed JSON are saved in `--log-dir` — keep them.

5. **Report and stop.** Give the user: stored/pending/permanent codes with
   plain-English meanings, whether the MIL is commanded on, protocol and
   adapter info, and any errors. Distinguish clearly between what the vehicle
   literally reported and your interpretation of likely causes — a DTC does
   not prove a component is bad. Do not clear anything; wait for the user to
   choose next steps.

## Troubleshooting and background

See [REFERENCE.md](REFERENCE.md) for: no serial device appearing, driver
decision tree, connection failures, multi-ECU responses, OBD mode reference,
and raw ELM access without Python.
