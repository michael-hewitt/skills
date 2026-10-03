"""Usage: cov-compare.py <before-covdir> <after-covdir> — union line coverage before vs after, lost lines by file."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from covdb import load
import numpy as np
def union(d):
    db = load(d)
    s = set()
    for arr in db.test_lines:
        s.update(arr.tolist())
    return {db.lines[i] for i in s}, db
a, dba = union(sys.argv[1]); b, dbb = union(sys.argv[2])
print(f"before: {len(dba.tests)} tests, {len(a)} lines | after: {len(dbb.tests)} tests, {len(b)} lines")
lost = sorted(a - b); gained = sorted(b - a)
print(f"lost {len(lost)}, gained {len(gained)}")
by = collections.defaultdict(list)
for f, l in lost: by[f].append(l)
for f, ls in sorted(by.items(), key=lambda kv: -len(kv[1])):
    print(f"  LOST {f}: {len(ls)} {sorted(ls)[:30]}")
gb = collections.Counter(f for f, _ in gained)
print('gained by file (top):', gb.most_common(8))
