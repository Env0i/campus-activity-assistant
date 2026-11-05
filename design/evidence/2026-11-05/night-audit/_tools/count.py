# -*- coding: utf-8 -*-
"""Coverage denominator counter: reads tracked files from git ls-files -z,
categorizes them and counts lines. Output is plain text, consumed by
the auditor; no data leaves the machine.

Usage: git -c core.quotepath=false ls-files -z | python -I reports/_tools/count.py
"""
import sys
from collections import defaultdict


def line_count(path):
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return -1


def category(path):
    p = path.replace("\\", "/")
    if p.endswith(".md"):
        return "doc"
    if p.startswith("design/prototype/"):
        return "proto"
    if p.startswith(("local/", "server/", "tools/", "contracts/")) or p == "VERSION":
        return "code"
    return "misc"


def main():
    raw = sys.stdin.buffer.read().decode("utf-8")
    files = [f for f in raw.split("\0") if f]
    agg = defaultdict(lambda: [0, 0])
    det = defaultdict(lambda: [0, 0])
    for f in files:
        n = line_count(f)
        c = category(f)
        agg[c][0] += 1
        agg[c][1] += max(n, 0)
        top = f.split("/")[0] if "/" in f else f
        det[(c, top)][0] += 1
        det[(c, top)][1] += max(n, 0)
    print("TOTAL", len(files))
    for c in ("code", "doc", "proto", "misc"):
        print("CAT", c, agg[c][0], agg[c][1])
    print("--- detail ---")
    for k in sorted(det):
        print("DET", k[0], k[1], det[k][0], det[k][1])


if __name__ == "__main__":
    main()
