#!/usr/bin/env python3
"""Summarize a live_logger.py JSONL by phase.

Usage: analyze_live_log.py FILE "phase name:t_start:t_end" [...]

Per phase: n, mean, sd, min, max for every logged channel; total trim
(STFT+LTFT) per bank; bank-1-vs-bank-2 STFT correlation (near +1 = a cause
shared by both banks, near 0 = bank-specific); misfire counters at the end of
the phase and the max seen. Pick phase windows from the console log
(cranking, cat heating, idle by coolant band, 2500 rpm hold, cruise...).
"""
import json, sys, statistics as st
path = sys.argv[1]
recs = [json.loads(l) for l in open(path) if l.strip() and '"meta"' not in l]
def stats(rs, k, d=2):
    v = [r[k] for r in rs if k in r and r[k] is not None]
    if not v: return None
    return {"n": len(v), "mean": round(st.mean(v), d), "sd": round(st.pstdev(v), d), "min": round(min(v), d), "max": round(max(v), d)}
def phase(name, t0, t1):
    rs = [r for r in recs if t0 <= r["t"] <= t1 and r.get("rpm", 0) > 300]
    if not rs: print(f"\n## {name}: no running samples"); return
    print(f"\n## {name}  (t {t0}-{t1}, {len(rs)} samples, coolant {stats(rs,'coolant_c',0)['min']}-{stats(rs,'coolant_c',0)['max']} C)")
    keys = ["rpm","maf_gps","load_pct","abs_load_pct","timing_deg","stft1_pct","stft2_pct","ltft1_pct","ltft2_pct",
            "o2_b1s1_lambda","o2_b2s1_lambda","o2_b1s1_ma","o2_b2s1_ma","cmd_lambda","o2_b1s2_v","o2_b2s2_v",
            "cat_b1_c","cat_b2_c","rail_kpa","module_v","throttle_pct","iat_c"]
    print(f"{'key':18s} {'n':>5s} {'mean':>9s} {'sd':>7s} {'min':>9s} {'max':>9s}")
    for k in keys:
        s = stats(rs, k)
        if s: print(f"{k:18s} {s['n']:5d} {s['mean']:9.2f} {s['sd']:7.2f} {s['min']:9.2f} {s['max']:9.2f}")
    s1 = [r for r in rs if "stft1_pct" in r and "ltft1_pct" in r]
    tot1 = [r["stft1_pct"] + r["ltft1_pct"] for r in s1]; tot2 = [r["stft2_pct"] + r["ltft2_pct"] for r in rs if "stft2_pct" in r and "ltft2_pct" in r]
    if tot1: print(f"TOTAL trim  bank1 mean {st.mean(tot1):+.1f}%  bank2 mean {st.mean(tot2):+.1f}%")
    a = [r["stft1_pct"] for r in rs if "stft1_pct" in r and "stft2_pct" in r]; b = [r["stft2_pct"] for r in rs if "stft1_pct" in r and "stft2_pct" in r]
    if len(a) > 10 and st.pstdev(a) and st.pstdev(b):
        ma, mb = st.mean(a), st.mean(b); cov = sum((x-ma)*(y-mb) for x, y in zip(a, b)) / len(a)
        print(f"STFT bank1-vs-bank2 correlation: {cov/(st.pstdev(a)*st.pstdev(b)):+.2f}")
    mis = [r for r in rs if r.get("misfire_read")]
    if mis:
        last = mis[-1]; print("misfire counts (current cycle) at end of phase:", {f"c{i}": last.get(f"mis_cnt_c{i}") for i in range(1, 7)})
        mx = {i: max(r.get(f"mis_cnt_c{i}", 0) for r in mis) for i in range(1, 7)}; print("max misfire count seen in phase:", mx)
for spec in sys.argv[2:]:
    n, a, b = spec.split(":"); phase(n, float(a), float(b))
