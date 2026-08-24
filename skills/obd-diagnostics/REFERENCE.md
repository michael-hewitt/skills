# OBD-II Diagnostics — Reference

## macOS driver & permission decision tree

1. `ls /dev/cu.usbserial*` shows a device → **no driver needed**. Apple's
   built-in `AppleUSBFTDI` driver (macOS 14+) handles FTDI-based adapters like
   the OBDLink EX (VID 0x0403 / PID 0x6015, "ScanTool.net LLC").
2. No serial device, and `ioreg -p IOUSB -l -w0` does NOT show the adapter →
   it's a USB-level problem, not a driver problem. Check in order:
   - macOS "Allow accessory to connect?" prompt (System Settings → Privacy &
     Security → "Allow accessories to connect"). This is the only macOS
     permission normally involved — `/dev/cu.*` nodes are already `crw-rw-rw-`,
     so no group/ownership changes are ever needed (unlike Linux dialout).
   - Cable/adapter seating (USB-A→C adapters are a common failure point).
   - Try another USB port.
3. Adapter visible in `ioreg` but no `/dev/cu.usbserial*` after ~10 s →
   the built-in driver didn't claim it. Only then consider the **official FTDI
   VCP driver** from https://ftdichip.com/drivers/vcp-drivers/ (never
   third-party download sites). It installs a system extension the user must
   approve in System Settings → Privacy & Security. Explain and get approval
   before installing. Verify afterward that `/dev/cu.usbserial*` appears.

Note: `system_profiler SPUSBDataType` prints nothing on some machines/sandboxes
— use `ioreg -p IOUSB -l -w0` for enumeration.

## Connection troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Connection failed` / `UNABLE TO CONNECT` | Ignition not ON; adapter not fully seated in OBD port; wrong port chosen |
| Adapter responds but `NO DATA` to mode queries | Ignition on but ECU asleep — cycle ignition; or protocol mismatch, let auto-detect run (`ATSP0`) |
| Multiple `/dev/cu.usbserial*` candidates | Unplug other serial devices or pass `--port` explicitly; match the USB serial number from `ioreg` to the device suffix |
| Very low adapter voltage reading (<11 V) | Weak car battery or poor OBD-port contact; readings are still valid |
| Port opens but garbage output | Baud mismatch — OBDLink EX defaults to 115200; python-OBD auto-negotiates, raw `screen` needs the right baud |

## Interpreting multi-ECU responses

On CAN (ISO 15765-4, 11-bit), each responding module answers with its own
header: `7E8` = engine ECU, `7E9` = usually transmission, `7EA`+ = others.
A response like `7E8 04 43 01 21 89` decodes as: Mode 03 response (`43`),
1 DTC (`01`), DTC bytes `21 89` → P2189. `7E9 02 43 00` = second module,
zero codes. python-OBD merges these; check the raw log when counts look odd.

## OBD mode reference (read-only modes used here)

| Mode | Purpose |
|---|---|
| 01 PID 01 | MIL status, DTC count, monitor readiness |
| 02 PID 02 | DTC that triggered the freeze frame |
| 03 | Stored (confirmed) DTCs |
| 07 | Pending DTCs (current/last drive cycle) |
| 0A | Permanent DTCs (unclearable until ECU self-clears) |
| **04** | **CLEARS DTCs — never send without explicit user authorization** |

## Raw ELM access without Python (fallback)

```bash
screen /dev/cu.usbserial-XXXX 115200
# ATZ   → reset/identify;  ATE0 → echo off;  ATRV → battery voltage
# ATSP0 → auto protocol;   0101 → MIL/status;  03 → stored DTCs
# Exit screen: Ctrl-A then k, then y
```

All of these are read/init commands. Avoid `AT PP` (persistent programmable
parameters) and any `ATSH`/raw-header writes beyond standard queries.

## Fuel-trim interpretation (lean/rich codes)

Use `scripts/live_trims.py` at cold idle, warm idle (after `wait_warm.py`),
and steady 2500 rpm. Work from **total trim = STFT avg + LTFT** per bank;
STFT near zero just means LTFT has already absorbed the error. Trims are only
trustworthy in closed loop on a warm engine (~80 °C+); expect the biggest
lean excursions cold.

| Pattern | Points to |
|---|---|
| High + at idle, normalizes at 2500 rpm | Vacuum leak (fixed air leak matters most at low airflow): PCV valve/hoses (classic VW), intake gaskets, booster lines |
| High + at all speeds, roughly constant | Underreporting MAF, fuel supply (pump/filter/regulator), exhaust leak upstream of O2 |
| Moderate + everywhere, one bank worse, worst when cold | Small leak biased to that bank (PCV feed, purge/N80 valve, injector falloff) — smoke test, prioritize the worse bank |
| Negative (rich) trims | Leaking injector, fuel in purge vapor, overreporting MAF |

Sanity checks: MAF at warm idle ≈ 1 g/s per liter of displacement (3.6L →
~3.5 g/s; ~11 g/s at 2500 rpm unloaded is normal). `FUEL_STATUS` must report
closed loop on both banks. Generic LTFT thresholds for setting a code are
~±25%, so a stored lean code alongside modest current trims usually means the
fault is intermittent or condition-dependent (cold, high load) — sample those
conditions. Other useful PIDs: `INTAKE_PRESSURE`, `O2_SENSORS`,
`FUEL_RAIL_PRESSURE_DIRECT`. A load test (someone else driving) or pinching
candidate vacuum lines while watching STFT are still read-only follow-ups.

## Storage layout

- Venv + logs: `~/.cache/obd-diag/` (`venv/`, `obd-raw-*.log`,
  `obd-results-*.json`, `serial-baseline.txt`)
- Nothing is written to the vehicle or persisted on the adapter.
