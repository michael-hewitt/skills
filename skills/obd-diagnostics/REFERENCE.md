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
parameters). `ATSH 7E0` (send to the engine ECU only) and `ATCRA 7E8` (receive
filter) are transient adapter settings, cleared by `ATZ`, and are fine for
standard Mode 01/06/09 queries; do not use custom headers for anything else.

## ELM/ECU protocol notes (learned the hard way)

- **Multi-PID Mode 01 requests** work on CAN: `01 0C 05 06 07 08 09` returns all
  six in one message (max 6 PIDs per request). With `ATH0`, `ATS0`, `ATCAF1` a
  multi-frame reply prints as a 3-hex-digit byte count (`016`), then lines
  `0:410302020F42`, `1:...`, `2:...`; concatenate the segments and truncate to
  the count (trailing `55` padding). Walk the payload with a PID-length table.
- **PID lengths that bite:** PID 44 (commanded lambda) is 2 bytes; 34/38
  (wideband lambda + current) are 4; 15/19 (rear O2) are 2; 23 (DI rail
  pressure) is 2; 43 is 2; 55–58 (secondary O2 trims) are 1 byte on ECUs with
  two banks. A wrong length silently misparses every PID after it.
- **Mode 06 records** (CAN) are 9 bytes each: MID, TID, unit/scaling ID, value
  (2), min (2), max (2). Some ECUs (VW MED17) reject multi-MID requests with
  `7F 06 12` — send one MID per request (~0.13 s each).
- Two ECUs (engine `7E8`, transmission `7E9`) answer generic Mode 01 broadcasts;
  address the engine directly with `ATSH 7E0` + `ATCRA 7E8` for speed and clean
  parsing. `ATAT2` (aggressive adaptive timing) is safe on CAN.
- Expect `NO DATA` for a second or two during cranking; the logger just records
  a `no_response` sample and continues.
- Engine-off, key-on reads are valuable: LTFTs, readiness, warm-ups/distance
  since clear, Mode 06 results (including last-cycle misfire counts) all persist.
- If the cable will be unplugged, stop the logger first; pyserial raises when
  the device vanishes. For a long drive log run under `caffeinate -i -s` with
  the lid open; if a logger must chain into another, wait for the first
  process to exit before opening the port.
- python-OBD (`fast=False`) is fine for one-shot reads (~0.15–0.3 s per PID)
  but too slow for idle-quality work; use the raw logger for that.


## Reading a live log (rough running, misfire, lean/rich)

- **Catalyst heating after a cold start** (VW MED17: ~80 s at ~1200 rpm, timing
  retarded to −15…−18°, MAF 4–5× idle) makes any engine sound and feel lumpy.
  It ends abruptly when idle drops to normal. Compare complaints against this
  window before calling it a fault.
- **Misfire counters** (Mode 06 TID 0C) update live. Zero on every cylinder
  through a cold start, warm-up, and a rev hold means the ECU sees no
  combustion irregularity; a perceived shake is then more likely mounts,
  accessories, or exhaust contact than misfire.
- **Idle quality:** at warm idle an RPM standard deviation under ~10 rpm with no
  dips below (mean − 40) is smooth by the ECU's measure.
- **Trims swinging together on both banks** (correlation ≈ +0.8…+1.0) point to a
  shared cause: purge cycling, warm-up maps, PCV/intake leak into the shared
  plenum, MAF, fuel pressure. Trims that **split by bank** (correlation ≈ 0)
  point to that bank: exhaust leak, injector, sensor.
- **Rear (post-cat) O2 sensors** should sit steady at ~0.6–0.75 V once active
  (they read ~0.45 V bias when cold). Both dropping on decel is fuel cut. One
  bank's rear sensor dropping to 0.1–0.4 V while its front sensor holds λ≈1 and
  the ECU is adding fuel means real oxygen in that bank's exhaust — an air leak
  into the exhaust (manifold gasket, crack, flange, flex joint) or a weak cat —
  rather than an injector problem, which the front-sensor correction would hide
  from the rear sensor.
- **Cranking voltage** below ~9.6 V (ambient ≥ 10 °C) means a weak battery or
  starter draw; note it even though it rarely causes rough running.
- **Warm-ups since clear** of a handful, with monitors incomplete, means the
  code memory was recently cleared (often by a shop) — weight "no codes"
  accordingly and re-check after a drive.
- **A/C on, or stopped in Drive, changes idle:** the ECU adds air and holds a
  torque reserve (ignition retarded several degrees) to absorb compressor and
  converter load steps. Compare idle airflow/timing only like-with-like (Park,
  A/C off) before calling extra idle air a leak.
- **P0507 (idle rpm higher than expected)** on an electronic-throttle engine
  means the idle controller hit its minimum torque with rpm still >100 above
  target for ~10 s (VW conditions: stopped, purge closed, no fuel cut). Causes:
  dirty/mis-adapted throttle body, unmetered air, or a load that dropped away
  faster than the controller could follow (A/C). It needs two drive cycles to
  store; a pending P0507 after a drive is worth a controlled idle test.
- **VVT/cam monitor** values that never change between reads and sit exactly on
  a limit with a 0..0 range are placeholders from a monitor that has not run
  yet; re-read after a drive that completes it.

## Fuel-trim interpretation (lean/rich codes)

Use `scripts/live_logger.py` (or `live_trims.py` for a quick one-off) at cold
idle, warm idle, and steady 2500 rpm. Work from **total trim = STFT avg + LTFT** per bank;
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

- Venv: `~/.cache/obd-diag/venv/`; `serial-baseline.txt` at the top level.
- Per session: `~/.cache/obd-diag/<YYYY-MM-DD>/` with `obd-raw-*.log`,
  `obd-results-*.json`, `keyon-full-*.json`, `<label>-*.jsonl` live logs,
  `*-console.log`, and any session-specific scripts. Never delete.
- Nothing is written to the vehicle or persisted on the adapter.
