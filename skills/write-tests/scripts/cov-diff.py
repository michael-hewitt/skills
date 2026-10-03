"""Usage: cov-diff.py before.json after.json — lists lines covered before but not after, grouped by file."""
import json, sys, collections
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
lost = sorted(set(a['lines']) - set(b['lines'])); gained = len(set(b['lines']) - set(a['lines']))
print(f"before: {a['tests']} tests {a['time']}s {len(a['lines'])} lines | after: {b['tests']} tests {b['time']}s {len(b['lines'])} lines | lost {len(lost)} gained {gained}")
by = collections.defaultdict(list)
for x in lost:
    f, l = x.rsplit(':', 1); by[f].append(int(l))
for f, ls in sorted(by.items()):
    print(f"  LOST {f}: {sorted(ls)}")
