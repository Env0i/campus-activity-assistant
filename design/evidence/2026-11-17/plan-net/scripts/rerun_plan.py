#!/usr/bin/env python3
"""补测试后的针对性复跑：只跑指定文件/函数/编号的候选。

与 mutate_plan.py 同一份候选生成与同一条执行路径，只是范围可筛；用于补完一条
用例后，立刻看这一组候选是否变红，不必重跑全部六百多条。

用法（从仓库根执行）：
  python -B design/evidence/2026-11-17/plan-net/scripts/rerun_plan.py --function paintSelected
  python -B ... --path plan-panel.js --function paintSelected --function startBlocker
  python -B ... --ids M001,M005 --tests test_ui_plan_board.py
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import mutate_plan as mutate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", action="append", default=[], help="路径片段，可重复")
    parser.add_argument("--function", action="append", default=[], help="函数名，可重复")
    parser.add_argument("--kind", action="append", default=[], help="种类片段，可重复")
    parser.add_argument("--ids", default="", help="逗号分隔的候选编号")
    parser.add_argument("--tests", default="", help="逗号分隔的测试文件名")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    candidates, _ = mutate.build_candidates()
    chosen = candidates
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        chosen = [item for item in chosen if item.cid in wanted]
    if args.path:
        chosen = [item for item in chosen if any(part in item.path for part in args.path)]
    if args.function:
        chosen = [item for item in chosen if item.function in set(args.function)]
    if args.kind:
        chosen = [item for item in chosen if any(part in item.kind for part in args.kind)]
    if not chosen:
        print("没有匹配的候选")
        return 2
    patterns = tuple(item.strip() for item in args.tests.split(",") if item.strip()) or mutate.PATTERNS

    results = []
    with tempfile.TemporaryDirectory(prefix="plan-rerun-") as name:
        temp = Path(name)
        base = temp / "base"
        base.mkdir()
        mutate.copy_base(base)
        root = temp / "root"
        mutate.copy_base(root)
        for candidate in chosen:
            try:
                mutate.apply_candidate(root, candidate)
            except mutate.LocatorError as exc:
                results.append({"id": candidate.cid, "status": "locator_error", "message": str(exc)})
                mutate.restore(root, base)
                continue
            ok, message = mutate.syntax_ok(root, candidate)
            if not ok:
                results.append({"id": candidate.cid, "status": "syntax_error", "message": message})
                mutate.restore(root, base)
                continue
            outcome = mutate.run_suite(root, patterns)
            results.append({"id": candidate.cid, **outcome})
            mark = "红" if outcome["status"] == "red" else outcome["status"]
            print(f"{candidate.cid} {mark}\t{candidate.function}\t{candidate.kind}\t"
                  f"{candidate.line_text[:60]}\t{outcome.get('test', '')}", flush=True)
            mutate.restore(root, base)
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print(json.dumps({"count": len(results), "status_counts": counts}, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps({"results": results}, ensure_ascii=False, indent=1),
                                  encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
