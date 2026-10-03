"""Coverage-preserving removal analysis over a CovDB.

Key idea: a set R of tests can be removed without losing coverage iff every line
covered by R is also covered by some test outside R. Lines executed only while a
worker's first test ran migrate:fresh (covered solely by 2+ "first" tests) are
treated as always covered.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict

import numpy as np

from covdb import CovDB, load


def method_of(test_id: str) -> str:
    m = test_id.split('::', 1)[1]
    return m.split('#', 1)[0].split(' with data set', 1)[0]


class Analysis:
    def __init__(self, db: CovDB):
        self.db = db
        n = len(db.lines)
        self.count = np.zeros(n, dtype=np.int32)  # covering (non-free) tests per line
        first_count = np.zeros(n, dtype=np.int32)
        for t, arr in zip(db.tests, db.test_lines):
            self.count[arr] += 1
            if t['first']:
                first_count[arr] += 1
        # Lines only first-tests reach, reached by 2+ of them: migrate:fresh / bootstrap.
        self.free = (first_count == self.count) & (first_count >= 2)
        self.key_index = defaultdict(list)  # (file, method) -> test indexes
        for i, t in enumerate(db.tests):
            self.key_index[(t['file'], method_of(t['id']))].append(i)
        self.by_file = defaultdict(list)
        for i, t in enumerate(db.tests):
            self.by_file[t['file']].append(i)

    def lines_of(self, idxs) -> np.ndarray:
        if not idxs:
            return np.zeros(0, dtype=np.int32)
        return np.unique(np.concatenate([self.db.test_lines[i] for i in idxs]))

    def lost_if_removed(self, idxs) -> np.ndarray:
        """Line ids that would lose all coverage if these tests were removed together."""
        idxs = list(idxs)
        if not idxs:
            return np.zeros(0, dtype=np.int32)
        sub = np.zeros_like(self.count)
        for i in idxs:
            sub[self.db.test_lines[i]] += 1
        touched = np.nonzero(sub)[0]
        lost = touched[(self.count[touched] - sub[touched] == 0) & ~self.free[touched]]
        return lost

    def remove(self, idxs) -> None:
        for i in idxs:
            self.count[self.db.test_lines[i]] -= 1

    def time_of(self, idxs) -> float:
        return float(sum(self.db.tests[i]['time'] for i in idxs))

    def describe_lines(self, line_ids, limit=30) -> list[str]:
        by = defaultdict(list)
        for l in line_ids:
            f, ln = self.db.lines[l]
            by[f].append(ln)
        out = []
        for f, ls in sorted(by.items(), key=lambda kv: -len(kv[1])):
            ls.sort()
            out.append(f"{f}: {len(ls)} lines {compress(ls)}")
        return out[:limit]


def compress(ls, maxparts=8):
    parts = []
    start = prev = ls[0]
    for x in ls[1:]:
        if x == prev + 1:
            prev = x
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = x
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    s = ','.join(parts[:maxparts])
    return s + (',…' if len(parts) > maxparts else '')


def load_tags(path: str) -> dict:
    tags = {}
    for line in open(path):
        t = json.loads(line)
        tags[(t['file'], t['name'])] = t
    return tags
