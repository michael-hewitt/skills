#!/usr/bin/env python3
"""Read-only high-rate live logger over raw ELM/STN commands (pyserial).

Addresses the engine ECU only (ATSH 7E0 / ATCRA 7E8, transient adapter
settings), sends multi-PID Mode 01 requests (up to 6 PIDs each) for speed
(~8 full sweeps/s on CAN), and polls Mode 06 per-cylinder misfire counters
(MIDs A2-A7, one MID per request) every --misfire-every seconds. Writes one
JSON object per line plus a console status line every 2 s. Never sends any
write/clear command.

Usage: live_logger.py --port /dev/cu.usbserial-XXXX --seconds 900 \
           --label coldstart --log-dir ~/.cache/obd-diag/<date> [--misfire-every 5]

Start it BEFORE cranking for a cold start. For a drive log wrap it in
`caffeinate -i -s` and stop it (pkill -f live_logger.py) before the cable is
unplugged. Adjust PID groups / PID_LEN for other vehicles (PID 44 is 2 bytes).
"""
import argparse, datetime, json, re, sys, time
import serial

PID_LEN = {0x03:2,0x04:1,0x05:1,0x06:1,0x07:1,0x08:1,0x09:1,0x0C:2,0x0D:1,0x0E:1,0x0F:1,
           0x10:2,0x11:1,0x15:2,0x19:2,0x1F:2,0x23:2,0x2E:1,0x33:1,0x34:4,0x38:4,0x3C:2,
           0x3D:2,0x42:2,0x43:2,0x44:2,0x45:1,0x46:1,0x4C:1,0x56:1,0x58:1}

def decode(pid, b):
    t = lambda x: (x - 128) * 100 / 128
    if pid == 0x03: return {"fuel_status_b1": b[0], "fuel_status_b2": b[1]}
    if pid == 0x04: return {"load_pct": round(b[0]*100/255, 1)}
    if pid == 0x05: return {"coolant_c": b[0]-40}
    if pid == 0x06: return {"stft1_pct": round(t(b[0]), 2)}
    if pid == 0x07: return {"ltft1_pct": round(t(b[0]), 2)}
    if pid == 0x08: return {"stft2_pct": round(t(b[0]), 2)}
    if pid == 0x09: return {"ltft2_pct": round(t(b[0]), 2)}
    if pid == 0x0C: return {"rpm": (b[0]*256+b[1])/4}
    if pid == 0x0D: return {"speed_kph": b[0]}
    if pid == 0x0E: return {"timing_deg": b[0]/2-64}
    if pid == 0x0F: return {"iat_c": b[0]-40}
    if pid == 0x10: return {"maf_gps": round((b[0]*256+b[1])/100, 2)}
    if pid == 0x11: return {"throttle_pct": round(b[0]*100/255, 1)}
    if pid == 0x15: return {"o2_b1s2_v": b[0]/200}
    if pid == 0x19: return {"o2_b2s2_v": b[0]/200}
    if pid == 0x1F: return {"run_time_s": b[0]*256+b[1]}
    if pid == 0x23: return {"rail_kpa": (b[0]*256+b[1])*10}
    if pid == 0x2E: return {"purge_pct": round(b[0]*100/255, 1)}
    if pid == 0x33: return {"baro_kpa": b[0]}
    if pid in (0x34, 0x38):
        k = "b1s1" if pid == 0x34 else "b2s1"
        return {f"o2_{k}_lambda": round((b[0]*256+b[1])/32768, 4), f"o2_{k}_ma": round((b[2]*256+b[3])/256-128, 3)}
    if pid in (0x3C, 0x3D):
        k = "b1" if pid == 0x3C else "b2"
        return {f"cat_{k}_c": (b[0]*256+b[1])/10-40}
    if pid == 0x42: return {"module_v": (b[0]*256+b[1])/1000}
    if pid == 0x43: return {"abs_load_pct": round((b[0]*256+b[1])*100/255, 1)}
    if pid == 0x44: return {"cmd_lambda": round((b[0]*256+b[1])/32768, 4)}
    if pid == 0x45: return {"rel_throttle_pct": round(b[0]*100/255, 1)}
    if pid == 0x46: return {"ambient_c": b[0]-40}
    if pid == 0x4C: return {"throttle_cmd_pct": round(b[0]*100/255, 1)}
    if pid == 0x56: return {"o2trim_lt_b1_pct": round(t(b[0]), 2)}
    if pid == 0x58: return {"o2trim_lt_b2_pct": round(t(b[0]), 2)}
    return {f"pid_{pid:02X}": b.hex()}

ERR = ("NO DATA", "UNABLE", "ERROR", "BUS ", "STOPPED", "?", "SEARCHING")

def cmd(ser, s, timeout=2.0):
    ser.reset_input_buffer()
    ser.write((s + "\r").encode())
    buf = b""; t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk: buf += chunk
        if buf.endswith(b">"): break
    return buf.decode(errors="replace")

def payload(text):
    """Reassemble ELM (ATH0, ATS0, CAF1) single/multi-frame response into bytes."""
    if any(e in text for e in ERR): return None
    lines = [l.strip() for l in text.replace(">", "").split("\r") if l.strip()]
    total = None; hexstr = ""
    for l in lines:
        if re.fullmatch(r"[0-9A-F]{3}", l): total = int(l, 16); continue
        m = re.fullmatch(r"[0-9A-F]:([0-9A-F]+)", l)
        if m: hexstr += m.group(1); continue
        if re.fullmatch(r"[0-9A-F]+", l) and len(l) % 2 == 0: hexstr += l
    if not hexstr: return None
    data = bytes.fromhex(hexstr)
    return data[:total] if total else data

def read_pids(ser, pids):
    data = payload(cmd(ser, "01" + "".join(f"{p:02X}" for p in pids)))
    if not data or data[0] != 0x41: return None
    out, i = {}, 1
    while i < len(data):
        pid = data[i]; n = PID_LEN.get(pid)
        if n is None or i + 1 + n > len(data): break
        out.update(decode(pid, data[i+1:i+1+n])); i += 1 + n
    return out

def read_misfire(ser):
    """One MID per request: this ECU answers 7F 06 12 to multi-MID Mode 06 requests."""
    out = {}
    for mid in range(0xA2, 0xA8):
        data = payload(cmd(ser, f"06{mid:02X}", timeout=2.0))
        if not data or data[0] != 0x46: continue
        for i in range(1, len(data) - 8, 9):
            m, tid = data[i], data[i+1]
            val = data[i+3]*256 + data[i+4]
            cyl = m - 0xA1
            key = {0x0B: f"mis_avg_c{cyl}", 0x0C: f"mis_cnt_c{cyl}"}.get(tid, f"mid{m:02X}_tid{tid:02X}")
            out[key] = val
    return out or None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True); ap.add_argument("--seconds", type=float, default=900)
    ap.add_argument("--label", default="live"); ap.add_argument("--log-dir", default=".")
    ap.add_argument("--misfire-every", type=float, default=10.0)
    a = ap.parse_args()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = f"{a.log_dir}/{a.label}-{stamp}.jsonl"
    ser = serial.Serial(a.port, 115200, timeout=0.05)
    init = {}
    for c in ("ATZ", "ATE0", "ATL0", "ATS0", "ATH0", "ATSP6", "ATSH7E0", "ATCRA7E8", "ATAT2", "ATRV"):
        init[c] = cmd(ser, c, timeout=3.0).replace("\r", " ").strip()
    print("init:", init, flush=True)
    f = open(path, "w"); t0 = time.time(); last_mis = -1e9; n = 0; last_print = 0
    f.write(json.dumps({"type": "meta", "stamp": stamp, "init": init, "label": a.label}) + "\n")
    print(f"logging to {path}", flush=True)
    latest = {}
    while time.time() - t0 < a.seconds:
        rec = {"t": round(time.time() - t0, 2)}
        for group in ([0x0C,0x05,0x06,0x07,0x08,0x09], [0x10,0x04,0x0E,0x11,0x42,0x0D]):
            r = read_pids(ser, group)
            if r: rec.update(r)
        if n % 5 == 0:
            for group in ([0x03,0x0F,0x34,0x38,0x44,0x23], [0x15,0x19,0x3C,0x3D,0x43,0x1F], [0x2E,0x46,0x33,0x4C,0x56,0x58]):
                r = read_pids(ser, group)
                if r: rec.update(r)
        if time.time() - last_mis >= a.misfire_every:
            r = read_misfire(ser)
            if r: rec.update(r); rec["misfire_read"] = True
            last_mis = time.time()
        if len(rec) == 1: rec["no_response"] = True
        f.write(json.dumps(rec) + "\n"); f.flush(); latest.update(rec); n += 1
        if time.time() - last_print >= 2.0:
            last_print = time.time()
            mis = " ".join(f"c{i}:{latest.get(f'mis_cnt_c{i}','-')}" for i in range(1, 7))
            print(f"t={rec['t']:6.1f} rpm={latest.get('rpm','-'):>6} ect={latest.get('coolant_c','-'):>3} "
                  f"st1={latest.get('stft1_pct','-'):>6} lt1={latest.get('ltft1_pct','-'):>6} "
                  f"st2={latest.get('stft2_pct','-'):>6} lt2={latest.get('ltft2_pct','-'):>6} "
                  f"maf={latest.get('maf_gps','-'):>5} adv={latest.get('timing_deg','-'):>5} "
                  f"V={latest.get('module_v','-'):>6} rail={latest.get('rail_kpa','-'):>5} mis[{mis}]", flush=True)
    f.close(); ser.close()
    print(f"done: {n} sweeps in {time.time()-t0:.0f}s -> {path}", flush=True)

if __name__ == "__main__":
    main()
