#!/usr/bin/env python3
"""Read-only: query every Mode 01 / 06 / 09 command the ECU advertises. No writes.

Usage: full_read.py PORT LOG_DIR

Works with the engine off (key on): long-term trims, readiness, warm-ups and
distance since DTC clear, Mode 06 monitor results with the ECU's own limits
(per-cylinder misfire counters, O2/catalyst/VVT/evap tests), VIN, CAL ID, CVN.
Run it again warm/after a drive to see monitors that have completed since.
Saves keyon-full-<stamp>.json and a raw ELM log in LOG_DIR.
"""
import datetime, json, logging, sys
import obd

port, logdir = sys.argv[1], sys.argv[2]
stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
fh = logging.FileHandler(f"{logdir}/keyon-raw-{stamp}.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
obd.logger.setLevel(logging.DEBUG); obd.logger.addHandler(fh)

def ser(v):
    if v is None or isinstance(v, (int, float, str, bool)): return v
    if hasattr(v, "magnitude"): return {"value": float(v.magnitude), "unit": str(v.units)}
    if isinstance(v, (bytes, bytearray)): return v.decode(errors="replace")
    if isinstance(v, (list, tuple, set)): return [ser(x) for x in v]
    if hasattr(v, "tests"):
        return [{"tid": t.tid, "name": t.name, "desc": t.desc, "value": ser(t.value),
                 "min": ser(t.min), "max": ser(t.max), "passed": t.passed} for t in v.tests]
    if hasattr(v, "__dict__"):
        return {k: ser(x) for k, x in vars(v).items() if isinstance(k, str) and not k.startswith("_")}
    return str(v)

conn = obd.OBD(portstr=port, fast=False, timeout=1.0)
if not conn.is_connected(): sys.exit(f"Connection failed: {conn.status()}")
out = {"timestamp": stamp, "protocol": conn.protocol_name(), "modes": {}}
for mode in (1, 9, 6):
    cmds = sorted((c for c in conn.supported_commands if c.mode == mode), key=lambda c: c.pid)
    out["modes"][str(mode)] = {}
    print(f"\n===== MODE {mode:02d} ({len(cmds)} supported) =====")
    for c in cmds:
        if c.name.startswith(("PIDS_", "MIDS_")): continue
        r = conn.query(c)
        val = None if (r is None or r.is_null()) else ser(r.value)
        out["modes"][str(mode)][c.name] = {"pid": c.pid, "desc": c.desc, "value": val}
        if mode == 6 and isinstance(val, list):
            print(f"{c.name} (MID {c.pid:02X}) {c.desc}:")
            for t in val: print(f"    TID {t['tid']:02X} {t['name']:<28} value={t['value']} min={t['min']} max={t['max']} passed={t['passed']}")
        else:
            print(f"{c.name:<32} (PID {c.pid:02X}) = {json.dumps(val, default=str)}")
conn.close()
p = f"{logdir}/keyon-full-{stamp}.json"
json.dump(out, open(p, "w"), indent=2, default=str)
print(f"\nSaved {p}")
