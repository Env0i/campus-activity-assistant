#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搬完重跑安全网：本批 28 个函数里「已守」与「等价」的行在新位置各变异一次。

行清单见同目录 rows.json：文件路径已是新位置，函数名、那一行的文字、第几次出现、
变异写法都与 plan-net 那一批一字不差，只换路径。先跑记录的那个测试文件，没变红
再跑其余四个；每条在 tempfile 下的仓库副本里改一处，改完先过 node --check。
等价行照旧应不改变可见结果；已守行必须仍红。

用法（仓库根执行）：
  python -B design/evidence/<日期>/plan-panel-rest-move/scripts/net_after_move.py --workers 4 --out <file>

@author Author
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "design/evidence/2026-11-17/plan-net/scripts"))

import mutate_plan as mutate  # noqa: E402

FIVE = list(mutate.PATTERNS)


def build_rows() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "rows.json"
    return json.loads(path.read_text(encoding="utf-8"))


def skip(name: str) -> bool:
    return ("local/data/" in name or "server/data/" in name or "config.json" in name
            or ".env" in name or name.split("/")[0].startswith("."))


def copy_tree(dest: Path) -> None:
    names = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                           check=True).stdout.decode().split("\0")
    names += subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                            cwd=str(ROOT), capture_output=True, check=True).stdout.decode().split("\0")
    for name in dict.fromkeys(names):
        if not name or skip(name):
            continue
        src = ROOT / name
        if not src.is_file():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())


def restore_files(rows: list[dict]) -> tuple[str, ...]:
    return tuple(sorted({row["path"] for row in rows}))


def run_rows(index: int, rows: list[dict], base: Path, temp: Path) -> list[dict]:
    root = temp / f"w{index}"
    copy_tree(root)
    restore = restore_files(rows)
    out = []
    for row in rows:
        cand = mutate.Candidate(row["path"], row["function"], row["kind"], row["needle"],
                                row["occurrence"], row["replacement"], row["line_text"])
        try:
            mutate.apply_candidate(root, cand)
        except mutate.LocatorError as exc:
            out.append({"id": row["id"], "verdict": row["verdict"], "status": "locator_error", "detail": str(exc)})
            for rel in restore:
                (root / rel).write_bytes((base / rel).read_bytes())
            continue
        ok, message = mutate.syntax_ok(root, cand)
        if not ok:
            out.append({"id": row["id"], "verdict": row["verdict"], "status": "syntax_error", "detail": message})
            for rel in restore:
                (root / rel).write_bytes((base / rel).read_bytes())
            continue
        first = (row["test_file"],) if row["test_file"] else ()
        outcome = mutate.run_suite(root, first) if first else {"status": "green"}
        if outcome["status"] == "green":
            outcome = mutate.run_suite(root, tuple(p for p in FIVE if p not in first))
        out.append({"id": row["id"], "verdict": row["verdict"], **outcome})
        print(f"[w{index}] {row['id']} {row['verdict']} {outcome['status']} "
              f"{row['path'].split('/')[-1]}:{row['function']}", flush=True)
        for rel in restore:
            (root / rel).write_bytes((base / rel).read_bytes())
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    rows = build_rows()
    print("行清单", len(rows), flush=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="plan-panel-rest-net-") as name:
        temp = Path(name); base = temp / "base"; base.mkdir()
        copy_tree(base)
        shards = [[] for _ in range(args.workers)]
        for i, row in enumerate(rows):
            shards[i % args.workers].append(row)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_rows, i, shard, base, temp)
                       for i, shard in enumerate(shards) if shard]
            for future in futures:
                results.extend(future.result())
    counts: dict = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    # 核对：已守行必须仍红；等价行应仍绿
    guarded_not_red = [r["id"] for r in results if r["verdict"] == "已守" and r["status"] != "red"]
    equivalent_red = [r["id"] for r in results if r["verdict"] == "等价" and r["status"] == "red"]
    print(json.dumps({"rows": len(rows), "status_counts": counts,
                      "guarded_not_red": guarded_not_red, "equivalent_red": equivalent_red},
                     ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"results": results}, ensure_ascii=False, indent=1),
                                  encoding="utf-8", newline="")
    return 0 if not guarded_not_red and not equivalent_red and not any(
        r["status"] in {"locator_error", "syntax_error"} for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
