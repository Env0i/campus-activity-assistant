#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搬完重跑安全网：只对「已守」的 354 条与「等价」的 10 条在新位置各做一次同样的变异。

行清单来自计划栏安全网那一批的候选（文件名、函数名、那一行的文字、第几次出现都不改），
只把文件路径换成搬完的新位置；执行方式与那批一致：先在记录的那个测试文件上跑，
没变红再跑其余四个。另把出口那一批的 P14（handlePlan 里删掉 `S.editing = null`）在新位置做一次。

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
PLAN_NET = ROOT / "design/evidence/2026-11-17/plan-net/scripts"
sys.path.insert(0, str(PLAN_NET))

import mutate_plan as mutate  # noqa: E402

FIVE = list(mutate.PATTERNS)

MOVED_TO = {}
for _name in ("paintSelected", "setBoardTag", "paintBoardState", "boardMetaHtml", "paintBoardActions",
              "paintEditNote", "paintRunPanel", "paintResultPanel", "paintPlan", "taskViaHtml", "taskHtml"):
    MOVED_TO[("local/ui/views/plan-panel.js", _name)] = "local/ui/features/plan/view.js"
for _name in ("selectionSummary", "runTagText", "runHeadKey", "runCaption", "boardPlanState", "editNoteText",
              "resultMode", "boardTargetItem", "planLate", "earliestWaitingOpen", "resultCounts", "resultView",
              "reselectableIds", "earliestSelectedOpen", "stopReasonText", "retryDeadline"):
    MOVED_TO[("local/ui/views/plan-panel.js", _name)] = "local/ui/features/plan/state-board.js"
MOVED_TO[("local/ui/views/plan-panel.js", "verifyTask")] = "local/ui/features/plan/actions.js"
for _name in ("mergeTask", "maxPlanGen", "planEventOwns", "admitPlanEvent", "openResultPage",
              "closeResultPage", "syncResultSelection", "resultPageOpen", "planOutcome", "unknownLabel",
              "selectionSignature"):
    MOVED_TO[("local/ui/state/plan.js", _name)] = "local/ui/features/plan/state.js"
for _name in ("advancePlanStatus", "handlePlan", "handleTask"):
    MOVED_TO[("local/ui/state/plan.js", _name)] = "local/ui/features/plan/actions.js"


def build_rows() -> list[dict]:
    """行清单直接读同目录的 rows.json：文件路径已换成新位置，函数名与变异写法与那一批一字不差。"""
    path = Path(__file__).resolve().parents[1] / "rows.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    if any(item["id"] == "P14" for item in rows):
        return rows
    rows.append({"id": "P14", "verdict": "已守",
                 "test_file": "test_ui_exit_paths_plan.py",
                 "path": "local/ui/features/plan/actions.js", "function": "handlePlan",
                 "kind": "删行", "needle": "S.editing = null;", "occurrence": 0,
                 "replacement": "", "line_text": "S.editing = null;"})
    return rows


def restore(root: Path, base: Path) -> None:
    """把这一批可能改过的文件从基线副本还原：一条变异只改一处，跑完必须回到原样。

    还原清单取自行清单里出现过的文件——写死成旧文件名的话，搬家换了路径就漏还原。
    基线副本里没有的文件跳过：那一批之后文件被搬走或删掉时，这些行只会记定位失败，不必还原。
    """
    for rel in sorted({row["path"] for row in build_rows()}):
        if (base / rel).exists():
            (root / rel).write_bytes((base / rel).read_bytes())


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
        shutil.copy2(src, target)


def apply_masked(root: Path, row: dict) -> None:
    """只在代码区定位：注释与字符串先掩掉，避免命中注释里的同名字样。"""
    path = root / row["path"]
    text = path.read_text(encoding="utf-8")
    masked = mutate.mask_source(text)
    ranges = {name: (start, end) for name, start, end in mutate.function_ranges(text, masked)}
    if row["function"] not in ranges:
        raise mutate.LocatorError("函数不存在：%s" % row["function"])
    start, end = ranges[row["function"]]
    body = masked[start:end]
    at = -1
    cursor = 0
    for _ in range(row["occurrence"] + 1):
        at = body.find(row["needle"], cursor)
        if at < 0:
            raise mutate.LocatorError("第 %d 次命中不到：%s" % (row["occurrence"] + 1, row["needle"][:40]))
        cursor = at + len(row["needle"])
    mutated = text[:start + at] + row["replacement"] + text[start + at + len(row["needle"]):]
    path.write_text(mutated, encoding="utf-8", newline="")


def run_rows(index: int, rows: list[dict], base: Path, temp: Path) -> list[dict]:
    root = temp / f"w{index}"
    copy_tree(root)
    out = []
    for row in rows:
        if not (root / row["path"]).exists():
            # 那一批之后文件被搬走或删掉：这一行在新树上无处可改，如实记定位失败
            out.append({"id": row["id"], "status": "locator_error",
                        "detail": "文件不在这次的树里：%s" % row["path"]})
            continue
        cand = mutate.Candidate(row["path"], row["function"], row["kind"], row["needle"],
                                row["occurrence"], row["replacement"], row["line_text"])
        try:
            mutate.apply_candidate(root, cand)
        except mutate.LocatorError as exc:
            out.append({"id": row["id"], "status": "locator_error", "detail": str(exc)})
            restore(root, base)
            continue
        ok, message = mutate.syntax_ok(root, cand)
        if not ok:
            out.append({"id": row["id"], "status": "syntax_error", "detail": message})
            restore(root, base)
            continue
        first = (row["test_file"],) if row["test_file"] else ()
        outcome = mutate.run_suite(root, first) if first else {"status": "green"}
        if outcome["status"] == "green":
            rest = tuple(p for p in FIVE if p not in first)
            outcome = mutate.run_suite(root, rest)
        out.append({"id": row["id"], "verdict": row["verdict"], **outcome})
        print(f"[w{index}] {row['id']} {outcome['status']} {row['path'].split('/')[-1]}:{row['function']}",
              flush=True)
        restore(root, base)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    rows = build_rows()
    verdicts = {}
    for row in rows:
        verdicts[row["verdict"]] = verdicts.get(row["verdict"], 0) + 1
    print("行清单", len(rows), verdicts, flush=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="plan-move-net-") as name:
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
    counts = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"rows": len(rows), "status_counts": counts}, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"results": results}, ensure_ascii=False, indent=1),
                                  encoding="utf-8", newline="")
    return 0 if not any(item["status"] in {"locator_error", "syntax_error"} for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
