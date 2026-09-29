#!/usr/bin/env python3
"""Summarize a live_logger.py drive log.

Usage: analyze_drive_log.py FILE

Bands by vehicle speed and load (stopped / low speed / cruise / moderate /
hard accel): rpm, MAF, trims per bank (STFT and total), front lambda, rear O2
voltage per bank and share of samples below 0.45 V, secondary O2 trims. Also:
closed-loop totals, LTFT drift, misfire counters over time, engine starts
(run_time resets), max speed, coolant range, and a 30 s timeline of cruise
segments. Remember A/C and gear state when comparing idle bands.
"""
import json, sys, statistics as st
recs = [json.loads(l) for l in open(sys.argv[1]) if l.strip() and '"meta"' not in l]
run = [r for r in recs if r.get("rpm", 0) > 300]
print(f"{len(recs)} records, {len(run)} running, span {recs[0]['t']:.0f}-{recs[-1]['t']:.0f}s, no_response {sum(1 for r in recs if r.get('no_response'))}")
# carry forward slow channels (speed is fast; lambda/rear O2 every 5th sweep)
carry = {}; filled = []
for r in run:
    carry.update({k: v for k, v in r.items() if k not in ("t",)})
    filled.append(dict(carry, t=r["t"]))
def m(rs, k, d=2):
    v = [r[k] for r in rs if k in r]; return round(st.mean(v), d) if v else None
def band(r):
    s = r.get("speed_kph", 0); ld = r.get("load_pct", 0)
    if s < 3: return "0 idle (stopped)"
    if ld >= 60: return "5 hard accel (load>=60)"
    if ld >= 40: return "4 moderate load (40-60)"
    if s >= 80: return "3 cruise >=80 kph"
    if s >= 40: return "2 cruise 40-80 kph"
    return "1 low speed <40 kph"
bands = {}
for r in filled: bands.setdefault(band(r), []).append(r)
print("\nband                        n   rpm   maf   load  st1    st2    tot1   tot2   lam1   lam2   b1s2V  b2s2V  b1s2<.45  b2s2<.45  o2tr1  o2tr2")
for b, rs in sorted(bands.items()):
    lo1 = sum(1 for r in rs if r.get("o2_b1s2_v", 1) < 0.45); lo2 = sum(1 for r in rs if r.get("o2_b2s2_v", 1) < 0.45)
    t1 = m(rs, "stft1_pct"); l1 = m(rs, "ltft1_pct"); t2 = m(rs, "stft2_pct"); l2 = m(rs, "ltft2_pct")
    print(f"{b:26s} {len(rs):5d} {m(rs,'rpm',0):5.0f} {m(rs,'maf_gps',1):5.1f} {m(rs,'load_pct',0):5.0f} {t1:6.2f} {t2:6.2f} {t1+l1:6.2f} {t2+l2:6.2f}  {m(rs,'o2_b1s1_lambda',3)}  {m(rs,'o2_b2s1_lambda',3)}  {m(rs,'o2_b1s2_v',2)}  {m(rs,'o2_b2s2_v',2)}  {lo1/len(rs):7.0%}  {lo2/len(rs):7.0%}  {m(rs,'o2trim_lt_b1_pct')}  {m(rs,'o2trim_lt_b2_pct')}")
# decel fuel cut excluded view: closed loop only (fuel_status 2) and load>10
cl = [r for r in filled if r.get("fuel_status_b1") == 2 and r.get("load_pct", 0) > 10]
print(f"\nclosed-loop, load>10: n={len(cl)} tot1 {m(cl,'stft1_pct')+m(cl,'ltft1_pct'):.2f} tot2 {m(cl,'stft2_pct')+m(cl,'ltft2_pct'):.2f}")
# LTFT drift over the drive
l = [(r["t"], r["ltft1_pct"], r["ltft2_pct"]) for r in run if "ltft1_pct" in r]
print("LTFT first/last:", l[0], l[-1]); print("LTFT distinct values b1:", sorted({x[1] for x in l}), "b2:", sorted({x[2] for x in l}))
# misfire timeline: any nonzero
mis = [r for r in run if r.get("misfire_read")]
nz = [(r["t"], {f"c{i}": r.get(f"mis_cnt_c{i}") for i in range(1, 7) if r.get(f"mis_cnt_c{i}")}) for r in mis if any(r.get(f"mis_cnt_c{i}") for i in range(1, 7))]
print(f"misfire reads {len(mis)}; reads with nonzero counts: {len(nz)}; last nonzero: {nz[-1] if nz else None}")
if mis: print("final counters:", {f"c{i}": mis[-1].get(f"mis_cnt_c{i}") for i in range(1, 7)}, "10-cycle avg:", {f"c{i}": mis[-1].get(f"mis_avg_c{i}") for i in range(1, 7)})
# ignition cycles via run_time resets
rt = [(r["t"], r["run_time_s"]) for r in run if "run_time_s" in r]; cycles = [rt[0]] + [b for a, b in zip(rt, rt[1:]) if b[1] < a[1]]
print("engine starts (t, run_time):", cycles)
sp = [r.get("speed_kph", 0) for r in run]; print(f"max speed {max(sp)} kph; coolant range {min(r['coolant_c'] for r in run if 'coolant_c' in r)}-{max(r['coolant_c'] for r in run if 'coolant_c' in r)} C; min voltage {min(r['module_v'] for r in recs if 'module_v' in r)}")
# 30 s timeline for cruise-type segments
print("\n30 s timeline (speed>=40): t  kph  rpm  load  st1   st2   tot1  tot2  b1s2V b2s2V")
bins = {}
for r in filled:
    if r.get("speed_kph", 0) >= 40: bins.setdefault(int(r["t"]//30)*30, []).append(r)
for b, rs in sorted(bins.items()):
    print(f"{b:5d} {m(rs,'speed_kph',0):4.0f} {m(rs,'rpm',0):5.0f} {m(rs,'load_pct',0):4.0f} {m(rs,'stft1_pct'):6.2f} {m(rs,'stft2_pct'):6.2f} {m(rs,'stft1_pct')+m(rs,'ltft1_pct'):6.2f} {m(rs,'stft2_pct')+m(rs,'ltft2_pct'):6.2f}  {m(rs,'o2_b1s2_v',2)}  {m(rs,'o2_b2s2_v',2)}")
