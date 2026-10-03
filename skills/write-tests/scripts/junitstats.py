"""Summarize a JUnit file: serial sum, distribution, top files/tests. Usage: junitstats.py junit.xml [top]"""
import sys, collections, xml.etree.ElementTree as ET
t = ET.parse(sys.argv[1]).getroot(); top = int(sys.argv[2]) if len(sys.argv) > 2 else 25
cases = [((tc.get('class') or ''), tc.get('name'), float(tc.get('time') or 0)) for tc in t.iter('testcase')]
ts = sorted((c[2] for c in cases), reverse=True); tot = sum(ts)
print(f"{len(cases)} cases, serial sum {tot/60:.1f} min, median {ts[len(ts)//2]*1000:.0f} ms")
for th in [0.5, 1, 2, 5]:
    s = sum(x for x in ts if x > th); print(f"  >{th}s: {sum(1 for x in ts if x > th)} cases, {s/60:.1f} min ({100*s/tot:.0f}%)")
byf = collections.defaultdict(lambda: [0, 0.0])
for c, n, tm in cases: byf[c][0] += 1; byf[c][1] += tm
print('top files:')
for k, (n, tm) in sorted(byf.items(), key=lambda kv: -kv[1][1])[:top]: print(f"  {tm:6.1f}s {n:4d} {k.replace('Tests\\\\Feature\\\\','')}")
print('top tests:')
for c, n, tm in sorted(cases, key=lambda c: -c[2])[:top]: print(f"  {tm:5.2f} {c.split(chr(92))[-1]} :: {n[:90]}")
