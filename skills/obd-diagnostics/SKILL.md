---
name: obd-diagnostics
description: Read vehicle diagnostic trouble codes (check-engine codes), Mode 06 monitor results (per-cylinder misfire counters, O2/catalyst/VVT tests), and live sensor data (fuel trims, lambda, MAF, coolant temp) over a USB OBD-II adapter (OBDLink EX or other ELM327/STN-compatible) on macOS, including environment setup, driver/permission checks, port detection, and high-rate logging through a cold start or a drive. Use when the user wants to read or scan car codes, diagnose a check engine light, rough running, a misfire, or a lean/rich code, or mentions OBD, OBD-II, DTCs, fuel trims, OBDLink, or ELM327.
---

# OBD-II Diagnostics (read-only)

Read DTCs, monitor results, and live data from a vehicle through an OBDLink EX
(or other ELM/STN) USB adapter.

## Safety rules — READ ONLY

Every session is read-only unless the user explicitly authorizes a specific write
operation in the current conversation. Never: clear DTCs (Mode 04), reset monitors
or learned values, run actuator tests, do ECU coding/adaptations, security access,
flashing, arbitrary CAN messages, UDS writes, or persistent adapter config changes
(`AT PP`). Harmless adapter init/query commands (reset, echo off, version, voltage,
protocol select, transient header/filter settings like `ATSH 7E0`/`ATCRA 7E8` for
standard Mode 01/06/09 queries) are fine. If a write seems necessary, stop and
explain it first.

## Etiquette

- If the user asks for a **fresh or unbiased** diagnosis, do not open prior reports,
  old logs, or notes that summarize earlier findings until they say so. Say what
  you did and did not look at.
- Keep each session's files in a dated subfolder (`~/.cache/obd-diag/<YYYY-MM-DD>/`).
  Never delete logs.
- The user is usually in the car and cannot read the terminal well: keep messages
  short, say exactly what to do (start, hold 2500 rpm, release), and tell them
  when nothing is needed from them. Send a PushNotification when they must act.

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
   shows an "Allow accessory to connect?" prompt. Ask whether the engine is cold:
   a cold start is the most informative event, so plan the session around it.

3. **Identify the port.** Run `scripts/setup.sh` again — it diffs against the
   baseline and prints the new device (e.g. `/dev/cu.usbserial-223230395038`).
   Verify with `ioreg -p IOUSB -l -w0 | grep -E '\+-o |Product Name'` that an
   OBDLink/FTDI device enumerated. Do not guess a port.

4. **Code scan (engine off).** Run:

   ```bash
   ~/.cache/obd-diag/venv/bin/python \
     ~/.agents/skills/obd-diagnostics/scripts/read_dtcs.py \
     --port /dev/cu.usbserial-XXXX --log-dir ~/.cache/obd-diag/<date>
   ```

   Reads adapter ID + battery voltage, MIL status + DTC count, stored (03),
   pending (07), permanent (0A) DTCs, freeze-frame DTC. Raw ELM log and JSON
   are saved — keep them.

5. **Full key-on read (engine off).** `scripts/full_read.py PORT LOG_DIR`
   queries every Mode 01/06/09 item the ECU advertises. Look at:
   - **warm-ups and distance since DTC clear** (PIDs 30/31): small numbers mean
     the memory was cleared recently and "no codes" proves little;
   - readiness (which monitors have not completed since the clear);
   - **long-term fuel trims per bank** (they persist engine-off);
   - **Mode 06 per-cylinder misfire counters** (MIDs A2+; TID 0B = 10-cycle
     average, TID 0C = last/current drive cycle) and O2/catalyst/VVT results
     against the ECU's own limits;
   - VIN, calibration ID, CVN (python-OBD may drop leading characters; the raw
     log has the exact strings).

6. **Live logging (engine running — get the user's go-ahead).**
   `scripts/live_logger.py --port PORT --seconds N --label LABEL --log-dir DIR`
   samples ~8 sweeps/s (rpm, coolant, STFT/LTFT both banks, MAF, load, timing,
   throttle, voltage, speed; every 5th sweep lambda/O2 currents, rear O2
   voltages, cat temps, rail pressure, IAT, purge, secondary O2 trims) and polls
   per-cylinder misfire counters every `--misfire-every` seconds. It writes a
   JSONL file and a console log with one status line every 2 s.
   - **Cold start:** start the logger in the background *before* cranking, then
     ask the user to start the engine. This captures the cranking voltage dip,
     the catalyst-heating phase, and the first minutes of trims.
   - Watch the console log with a **Monitor** (emit on misfire-count changes plus
     a status line every ~45 s); do not poll with sleeps.
   - Idle to ≥80 °C ECU coolant (dash gauges read "normal" from ~75 °C), then
     ask for a **steady 2500 rpm hold of ~60 s** and note the time window.
   - Run `full_read.py` again warm for Mode 06 monitors, and `read_dtcs.py` for
     pending codes.
   - **Drive log:** wrap the logger in `caffeinate -i -s`, use a long
     `--seconds`, lid open. Stop it (`pkill -f live_logger.py`) before the
     cable is unplugged and start a fresh one after reconnecting. Ask for a few
     minutes of steady cruise plus a couple of moderate accelerations so the
     O2 and VVT monitors can complete.

7. **Analyze.** `scripts/analyze_live_log.py FILE "name:t0:t1" ...` prints
   per-phase statistics, total trim per bank, bank-to-bank STFT correlation, and
   misfire counters; `scripts/analyze_drive_log.py FILE` bins a drive by speed
   and load band. Interpret with the tables in [REFERENCE.md](REFERENCE.md).
   After the drive, run `read_dtcs.py` again: pending codes that set during the
   drive are often the most useful result of the day.

8. **Report and stop.** Give the user: codes with plain-English meanings, MIL
   state, what the ECU measured in each phase, and your interpretation —
   clearly separated. Distinguish designed behavior (catalyst heating, decel
   fuel cut) from faults. Do not clear anything. Write the report where the user
   keeps that vehicle's records, and record vehicle-specific quirks in that
   folder's CLAUDE.md; put generic tooling improvements back into this skill.

## Troubleshooting and background

See [REFERENCE.md](REFERENCE.md) for: no serial device appearing, driver
decision tree, connection failures, multi-ECU responses, ELM/ECU protocol
notes (multi-PID requests, Mode 06 record format, ECU quirks), OBD mode
reference, interpretation tables, and raw ELM access without Python.
