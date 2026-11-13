#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主执行方抽查助手：从 .cites.jsonl 按固定种子抽 N 条，
打印条目与基线原文（start..end 行），供人工判断 claim 语义是否成立。
用法: python spot_sample.py <cites.jsonl> --n 12 --seed 20261112
只读。基线用 git show 7e2d31c:<file>。"""

import argparse
import json
import random
import subprocess
import sys


def norm(t):
    return t.replace("\r\n", "\n").replace("\r", "\n")


def baseline(rel):
    proc = subprocess.run(["git", "show", "7e2d31c:%s" % rel],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    return norm(proc.stdout.decode("utf-8", errors="replace"))


def main(argv):
    if getattr(sys.stdout, "reconfigure", None):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("cites")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20261112)
    args = ap.parse_args(argv)
    entries = []
    with open(args.cites, "rb") as handle:
        for line in handle.read().decode("utf-8").splitlines():
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    rnd = random.Random(args.seed)
    picks = rnd.sample(entries, min(args.n, len(entries)))
    for e in picks:
        text = baseline(e["file"])
        print("=" * 8, e["id"], e["file"], e["start"], e["end"], e["kind"])
        print("claim:", e["claim"])
        print("excerpt:", e["excerpt"].replace("\n", "\\n")[:120])
        if text is None:
            print("!! 基线读取失败")
            continue
        lines = text.split("\n")
        for no in range(e["start"], min(e["end"], len(lines)) + 1):
            print("%5d| %s" % (no, lines[no - 1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
