#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条变异收尾小修的两处改动，看测试能不能逐条抓住。

每条变异在自己的临时工作区副本里做：按文件、函数、那一行的文字与第几次出现定位一处，
先 node --check，再按 test_plan_transitions.py → test_ui_plan_flow.py → test_ui_plan_board.py
→ test_ui_contract_plan.py → test_prerefactor_fixes.py 首红即停；五条全绿才记 green。
改完立刻还原，副本复用，四个进程并行。不写临时目录的具体路径。

用法（仓库根执行）：
  python -B design/evidence/<日期>/plan-finish/scripts/mutate_finish.py [--workers 4]

@author Author
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
STATE = "local/ui/features/plan/state-board.js"
RUN = "local/ui/features/plan/actions-run.js"
FIRST = "test_plan_transitions.py"
REST = ["test_ui_plan_flow.py", "test_ui_plan_board.py",
        "test_ui_contract_plan.py", "test_prerefactor_fixes.py"]

FRAME_SCOPE = "export function boardPlanState() {"
SYNC_SCOPE = "function resyncPlanFromBootstrap(wasEditing) {"
STOP_SCOPE = "const stopFailed = (line, noteText) => {"
BRANCH_SCOPE = 'api("stop_plan", planId).then((res) => {'


def mut(mid, path, scope, needle, replacement, nth=1, why=""):
    return {"id": mid, "path": path, "scope": scope, "needle": needle,
            "replacement": replacement, "nth": nth, "why": why}


MUTATIONS = [
    # 外框随登录：条件去掉、取反
    mut("frame_drop_login", STATE, FRAME_SCOPE,
        'if (S.busy && !S.login.loginPending) return "running";',
        'if (S.busy) return "running";', why="登录窗口开着时又按运行中画"),
    mut("frame_invert_login", STATE, FRAME_SCOPE,
        'if (S.busy && !S.login.loginPending) return "running";',
        'if (S.busy && S.login.loginPending) return "running";',
        why="只有登录时才按运行中画，等开放反而按没在跑"),

    # 停止记录按快照写：句子对调、wasEditing 判断去掉、catch 那句去掉
    mut("swap_busy_text", RUN, SYNC_SCOPE,
        'info.busy ? "停止没成功，计划继续运行" : "计划已经结束，修改作废"',
        'info.busy ? "计划已经结束，修改作废" : "停止没成功，计划继续运行"',
        why="快照说在跑却写结束，说不在却写继续运行"),
    mut("drop_was_editing", RUN, SYNC_SCOPE,
        'if (wasEditing) addLog(info.busy ?',
        'addLog(info.busy ?', why="非修改时停也写修改相关的两句"),
    mut("drop_catch_line", RUN, SYNC_SCOPE,
        'if (wasEditing) addLog("停止没成功，计划继续运行");\n  });',
        '\n  });', why="拿快照失败时不再保守写停止没成功"),

    # 改由 stopFailed 继续写那一句、桥接异常那支不变、原有第一条记录
    mut("stop_failed_writes_again", RUN, STOP_SCOPE,
        "if (noteText && wasEditing) addLog(", "if (wasEditing) addLog(",
        why="后端拒答那一支又写了停止没成功"),
    mut("drop_bridge_line", RUN, STOP_SCOPE,
        "if (noteText && wasEditing) addLog(", "if (false && noteText && wasEditing) addLog(",
        why="桥接异常那一支不再写停止没成功"),
    mut("drop_first_failure_line", RUN, STOP_SCOPE,
        "    addLog(line);\n", "", why="后端给的原因那句不见了"),

    # wasEditing 没带进对账分支
    mut("pass_no_was_editing", RUN, BRANCH_SCOPE,
        "resyncPlanFromBootstrap(wasEditing);", "resyncPlanFromBootstrap();",
        why="对账分支拿不到修改标记，按快照的两句都不写"),
]


def skip(name: str) -> bool:
    parts = Path(name).parts
    return (parts[0] in ("local/data", "server/data", ".workbuddy")
            or ".workbuddy" in parts or "config.json" in parts[-1]
            or parts[-1] == ".env")


def copy_current(dest: Path) -> None:
    """复制仓库里跟踪与未跟踪的业务文件；磁盘上已不存在的文件跳过。"""
    names = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
    for name in dict.fromkeys(names):
        if not name or skip(name):
            continue
        source = ROOT / name
        if not source.is_file():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def apply_mutation(root: Path, item: dict) -> None:
    path = root / item["path"]
    text = path.read_text(encoding="utf-8")
    start = text.find(item["scope"]) if item["scope"] else 0
    if start < 0:
        raise AssertionError("scope not found: %s::%s" % (item["path"], item["scope"]))
    at = -1
    for _ in range(item["nth"]):
        at = text.find(item["needle"], at + 1)
        if at < 0:
            raise AssertionError("needle not found: %s::%s#%d"
                                 % (item["path"], item["needle"], item["nth"]))
    path.write_text(text[:at] + item["replacement"] + text[at + len(item["needle"]):],
                    encoding="utf-8", newline="")


def parses(root: Path, item: dict) -> bool:
    target = root / item["path"]
    probe = root / "mutant.mjs"
    shutil.copyfile(target, probe)
    try:
        return subprocess.run(["node", "--check", str(probe)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace").returncode == 0
    finally:
        probe.unlink()


def run_test(root: Path, name: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", name],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    output = result.stdout + result.stderr
    match = re.search(r"(?:FAIL|ERROR): ([^\r\n]+)", output)
    return result.returncode, (name + ": " + match.group(1)) if match else name


def check(root: Path, item: dict) -> dict:
    path = root / item["path"]
    original = path.read_text(encoding="utf-8")
    try:
        apply_mutation(root, item)
    except AssertionError as error:
        return {"id": item["id"], "status": "invalid", "detail": str(error), "why": item["why"]}
    try:
        if not parses(root, item):
            return {"id": item["id"], "status": "invalid", "detail": "node --check 没过", "why": item["why"]}
        for name in [FIRST] + REST:
            code, detail = run_test(root, name)
            if code:
                return {"id": item["id"], "status": "red", "detail": detail, "why": item["why"]}
        return {"id": item["id"], "status": "green", "detail": "五个文件都过", "why": item["why"]}
    finally:
        path.write_text(original, encoding="utf-8", newline="")


def worker(items: list[dict], index: int) -> list[dict]:
    root = Path(tempfile.mkdtemp(prefix="plan-finish-mut-%d-" % index))
    try:
        copy_current(root)
        return [check(root, item) for item in items]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    buckets = [[] for _ in range(args.workers)]
    for i, item in enumerate(MUTATIONS):
        buckets[i % args.workers].append(item)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for chunk in pool.map(lambda pair: worker(pair[1], pair[0]), enumerate(buckets)):
            results.extend(chunk)
    order = {item["id"]: i for i, item in enumerate(MUTATIONS)}
    results.sort(key=lambda r: order[r["id"]])
    for row in results:
        print("%s\t%s\t%s" % (row["id"], row["status"], row["detail"]))
    green = [r["id"] for r in results if r["status"] == "green"]
    invalid = [r["id"] for r in results if r["status"] == "invalid"]
    print(json.dumps({"total": len(results), "green": green, "invalid": invalid},
                     ensure_ascii=False))
    return 0 if not green and not invalid else 1


if __name__ == "__main__":
    raise SystemExit(main())
