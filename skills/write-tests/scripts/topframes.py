"""Inclusive-time ranking of frames in Excimer collapsed stacks.
Usage: topframes.py <collapsed-file>... [--match REGEX] [--top N]"""
import collections, re, sys, argparse
ap = argparse.ArgumentParser(); ap.add_argument('files', nargs='+'); ap.add_argument('--match', default='.'); ap.add_argument('--top', type=int, default=40)
a = ap.parse_args()
incl = collections.Counter(); total = 0
for f in a.files:
    for line in open(f):
        stack, n = line.rstrip('\n').rsplit(' ', 1); n = int(n); total += n
        for fr in set(stack.split(';')):
            incl[fr] += n
print('total samples', total)
rx = re.compile(a.match)
shown = 0
for k, v in incl.most_common():
    if rx.search(k):
        print(f"{100*v/total:5.1f}% {k[:160]}"); shown += 1
        if shown >= a.top: break
