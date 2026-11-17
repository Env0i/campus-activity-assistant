#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搬完重跑安全网：两个控制器里「已守」的 68 行在新位置各做一次同样的变异，另加六个出口。

行清单见同目录 rows.json：函数名、那一行的文字、第几次出现、变异写法都与计划栏安全网那一批一字不差，
只把文件路径换成搬完的新位置。执行方式与那批一致——先跑记录的那个测试文件，没变红再跑其余四个；
每条都在 tempfile.gettempdir() 下的仓库副本里改一处，改完先过 node --check。

@author Author
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "design/evidence/2026-11-17/plan-net/scripts"))

import mutate_plan as mutate  # noqa: E402

FIVE = list(mutate.PATTERNS)


def build_rows() -> list[dict]:
    """行清单直接读同目录的 rows.json：文件路径已是新位置，其它与那一批一致。"""
    path = Path(__file__).resolve().parents[1] / "rows.json"
    return json.loads(path.read_text(encoding="utf-8"))


def restore_files(rows: list[dict]) -> tuple[str, ...]:
    """要还原的文件：行清单里出现过的，加这次变异可能波及的同文件。"""
    names = {row["path"] for row in rows}
    return tuple(sorted(names))


def copy_tree(dest: Path) -> None:
    names = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                           check=True).stdout.decode().split("\0")
    names += subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=str(ROOT),
                            capture_output=True, check=True).stdout.decode().split("\0")
    skip = ("local/data/", "server/data/", "config.json", "local/_site_build.py", ".env")
    for name in names:
        if not name or name.split("/")[0].startswith(".") or any(part in name for part in skip):
            continue
        src = ROOT / name
        if not src.exists():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(src.read_bytes())


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
            out.append({"id": row["id"], "status": "locator_error", "detail": str(exc)})
            for rel in restore:
                (root / rel).write_bytes((base / rel).read_bytes())
            continue
        ok, message = mutate.syntax_ok(root, cand)
        if not ok:
            out.append({"id": row["id"], "status": "syntax_error", "detail": message})
            for rel in restore:
                (root / rel).write_bytes((base / rel).read_bytes())
            continue
        first = (row["test_file"],) if row["test_file"] else ()
        outcome = mutate.run_suite(root, first) if first else {"status": "green"}
        if outcome["status"] == "green":
            outcome = mutate.run_suite(root, tuple(p for p in FIVE if p not in first))
        out.append({"id": row["id"], "verdict": row["verdict"], **outcome})
        print(f"[w{index}] {row['id']} {outcome['status']} {row['path'].split('/')[-1]}:{row['function']}",
              flush=True)
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
    with tempfile.TemporaryDirectory(prefix="plan-actions-net-") as name:
        temp = Path(name)
        base = temp / "base"
        base.mkdir()
        copy_tree(base)
        shards = [[] for _ in range(args.workers)]
        for i, row in enumerate(rows):
            shards[i % args.workers].append(row)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_rows, i, shard, base, temp) for i, shard in enumerate(shards) if shard]
            for future in futures:
                results.extend(future.result())
    counts: dict = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"rows": len(rows), "status_counts": counts}, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"results": results}, ensure_ascii=False, indent=1),
                                  encoding="utf-8", newline="")
    return 0 if not any(item["status"] in {"locator_error", "syntax_error"} for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
