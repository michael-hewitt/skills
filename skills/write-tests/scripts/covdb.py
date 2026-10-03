"""Load per-test line coverage JSONL (from LineCoverageExtension) into compact numpy form.

Usage as a library:
    from covdb import load
    db = load('/path/to/covdir')

db.tests: list of dicts {id, file, time, first}
db.lines: list of (app_file, line) for each line id
db.test_lines: list of np.ndarray[int32] line ids per test
db.boot_lines: set of line ids executed by every worker's first test (migrate:fresh / bootstrap)
"""

from __future__ import annotations

import glob
import json
import os
import pickle
import re
from dataclasses import dataclass, field

import numpy as np


def test_file_for(test_id: str) -> str:
    cls = test_id.split('::', 1)[0]
    if cls.startswith('P\\'):
        cls = cls[2:]
    parts = cls.split('\\')
    if parts and parts[0] == 'Tests':
        parts[0] = 'tests'
    return '/'.join(parts) + '.php'


@dataclass
class CovDB:
    tests: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    test_lines: list = field(default_factory=list)
    boot_lines: set = field(default_factory=set)

    def files(self) -> dict:
        out: dict[str, list[int]] = {}
        for i, t in enumerate(self.tests):
            out.setdefault(t['file'], []).append(i)
        return out


def load(covdir: str, use_cache: bool = True) -> CovDB:
    cache = os.path.join(covdir, '_covdb.pickle')
    sources = sorted(glob.glob(os.path.join(covdir, '*.jsonl')))
    if use_cache and os.path.exists(cache) and all(os.path.getmtime(cache) >= os.path.getmtime(s) for s in sources):
        with open(cache, 'rb') as fh:
            return pickle.load(fh)

    db = CovDB()
    index: dict[tuple[str, int], int] = {}
    first_sets = []
    for src in sources:
        with open(src) as fh:
            for raw in fh:
                rec = json.loads(raw)
                ids = []
                cov = rec['cov'] if isinstance(rec['cov'], dict) else {}
                for f, ls in cov.items():
                    if not f.startswith(('app/', 'routes/', 'resources/views/')):
                        continue
                    for ln in ls:
                        key = (f, ln)
                        lid = index.get(key)
                        if lid is None:
                            lid = len(db.lines)
                            index[key] = lid
                            db.lines.append(key)
                        ids.append(lid)
                arr = np.array(sorted(ids), dtype=np.int32)
                db.tests.append({
                    'id': rec['id'],
                    'file': test_file_for(rec['id']),
                    'time': rec['time'],
                    'cpu': rec.get('cpu', 0.0),
                    'first': rec.get('first', False),
                })
                db.test_lines.append(arr)
                if rec.get('first'):
                    first_sets.append(set(arr.tolist()))
    if first_sets:
        boot = set.intersection(*first_sets) if len(first_sets) > 1 else set()
        # Lines every first test hit that almost no ordinary test hits are migrate:fresh/bootstrap lines.
        counts = np.zeros(len(db.lines), dtype=np.int32)
        for t, arr in zip(db.tests, db.test_lines):
            if not t['first']:
                counts[arr] += 1
        db.boot_lines = {l for l in boot if counts[l] == 0}
    with open(cache, 'wb') as fh:
        pickle.dump(db, fh)
    return db
