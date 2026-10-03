"""Are lines a rewrite stopped covering still covered by other tests in the suite?

Usage: COV_BASELINE=<full-run cov dir> [REMOVED_PLANS=plan1.json:plan2.json] \
       cov-global.py before.json after.json <edited test file>...

Compares the two cov-files.sh outputs; for every line covered before but not after,
counts tests in the full-suite baseline (run-cov.sh output) outside the edited files,
and not removed by any remove_tests.php plan listed in REMOVED_PLANS, that cover it.
Lines with zero such tests are real coverage losses: fix them.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analysis import Analysis, load, method_of  # noqa: E402

before, after, edited = sys.argv[1], sys.argv[2], set(sys.argv[3:])
a = set(json.load(open(before))['lines'])
b = set(json.load(open(after))['lines'])
lost = sorted(a - b)
if not lost:
    print('no lines lost')
    sys.exit(0)

db = load(os.environ['COV_BASELINE'])
removed = set()
for p in filter(None, os.environ.get('REMOVED_PLANS', '').split(':')):
    if os.path.exists(p):
        for f, ms in json.load(open(p)).items():
            removed.update((f, m) for m in ms)

index = {line: i for i, line in enumerate(db.lines)}
counts = {}
wanted = {}
for x in lost:
    f, l = x.rsplit(':', 1)
    lid = index.get((f, int(l)))
    if lid is not None:
        wanted[lid] = x
        counts[x] = 0
    else:
        counts[x] = None  # not in baseline (should not happen)

for t, arr in zip(db.tests, db.test_lines):
    if t['file'] in edited or (t['file'], method_of(t['id'])) in removed:
        continue
    for lid in set(arr.tolist()) & wanted.keys():
        counts[wanted[lid]] += 1

uncovered = [x for x, c in counts.items() if not c]
print(f"{len(lost)} lines no longer covered by the edited files; {len(lost) - len(uncovered)} still covered elsewhere; {len(uncovered)} LOST from the suite")
for x in uncovered:
    print('  LOST', x)
