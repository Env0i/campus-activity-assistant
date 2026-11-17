#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条变异这一批新转移，看测试能不能逐条抓住。

每条变异都在自己的临时工作区副本里做：先按文件、函数、原文与出现次序定位一处，
再按顺序跑 test_plan_transitions.py → test_ui_plan_flow.py → test_ui_plan_board.py →
test_ui_contract_plan.py，首红即停；全绿才记 green。改完立刻还原，副本复用，四个进程并行。

用法（仓库根执行）：
  python -B design/evidence/<日期>/plan-transitions/scripts/mutate_transitions.py [--workers 4]

@author Author
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from run_warn_grid import copy_current  # noqa: E402

ROOT = HERE.parents[4]
STATE = "local/ui/features/plan/state-board.js"
RUN = "local/ui/features/plan/actions-run.js"
APP = "local/ui/app.js"
FIRST = "test_plan_transitions.py"
REST = ["test_ui_plan_flow.py", "test_ui_plan_board.py", "test_ui_contract_plan.py"]

CODE_SCOPE = '} else if ((S.login.view || {}).phase === "needs_code") {'
LATE_SCOPE = "      const first = earliestWaitingOpen();"
PLAIN_SCOPE = "      } else {\n        text = \"登录失效了，计划还在等。"
NOTE_SCOPE = "  if (!text && S.stopNote && S.stopNote.planId === S.plan.id) {"
STOP_SCOPE = "export function doStopPlan() {"
SYNC_SCOPE = "function resyncPlanFromBootstrap() {"
WINDOW_SCOPE = "      ingestBootstrapPlan(info);"


def mut(mid, path, scope, needle, replacement):
    return {"id": mid, "path": path, "scope": scope, "needle": needle,
            "replacement": replacement}


MUTATIONS = [
    # 要你输验证码那一支：判断、两个时刻、按钮动作与按钮字
    mut("code_phase", STATE, CODE_SCOPE, '=== "needs_code"', '=== "expired"'),
    mut("code_first_stamp", STATE, CODE_SCOPE, "first - LATE_WINDOW_S", "first"),
    mut("code_second_stamp", STATE, CODE_SCOPE,
        '+ " 前输完验证码，计划照常继续；否则 " + hmsDay(first) + " 开放的那批会以“登录失效”结束。"',
        '+ " 前输完验证码，计划照常继续；否则 " + hmsDay(first - LATE_WINDOW_S)'
        ' + " 开放的那批会以“登录失效”结束。"'),
    mut("code_action", STATE, CODE_SCOPE,
        'act = { act: "login", label: "输入验证码" };',
        'act = { act: "code", label: "输入验证码" };'),
    mut("code_label", STATE, CODE_SCOPE,
        'act = { act: "login", label: "输入验证码" };',
        'act = { act: "login", label: "重新登录" };'),
    mut("plain_text", STATE, PLAIN_SCOPE,
        '+ " 前重新登录，计划照常继续；否则 "',
        '+ " 前输完验证码，计划照常继续；否则 "'),
    mut("late_condition", STATE, LATE_SCOPE, "if (late || first === null) {",
        "if (late && first === null) {"),

    # 停止没成功写在计划栏上：两种文案、计划号相同才显示、登录提示优先、色调、清与置
    mut("note_pause_text", RUN, STOP_SCOPE, '"没能暂停，计划照常进行。"',
        '"没能停止，计划照常进行。"'),
    mut("note_stop_text", RUN, STOP_SCOPE, '"没能停止，计划照常进行。"',
        '"没能暂停，计划照常进行。"'),
    mut("note_plan_id", STATE, NOTE_SCOPE, "S.stopNote.planId === S.plan.id",
        "S.stopNote.planId !== S.plan.id"),
    mut("note_priority", STATE, NOTE_SCOPE,
        "if (!text && S.stopNote && S.stopNote.planId === S.plan.id) {",
        "if (S.stopNote && S.stopNote.planId === S.plan.id) {"),
    mut("note_tone", STATE, NOTE_SCOPE, 'tone = "warn";', 'tone = "info";'),
    mut("note_clear", RUN, STOP_SCOPE, "  S.stopNote = null;\n  if (!S.plan.id) return;",
        "  if (!S.plan.id) return;"),
    mut("note_assignment", RUN, STOP_SCOPE,
        "if (noteText) S.stopNote = { planId: planId, text: noteText };",
        "if (false && noteText) S.stopNote = { planId: planId, text: noteText };"),

    # 后端说没有这个计划时按快照对账，不写「照常进行」
    mut("sync_ok_false", RUN, STOP_SCOPE, "if (res && res.ok === false) {",
        "if (false && res && res.ok === false) {"),
    mut("sync_call", RUN, STOP_SCOPE, "      resyncPlanFromBootstrap();\n", ""),
    mut("sync_no_note", RUN, STOP_SCOPE, 'stopFailed(res.text || "当前没有这个计划");',
        'stopFailed(res.text || "当前没有这个计划", '
        'S.editing ? "没能暂停，计划照常进行。" : "没能停止，计划照常进行。");'),
    mut("sync_busy_clear", RUN, SYNC_SCOPE, "if (!info.busy) S.stopping = false;",
        "if (info.busy) S.stopping = false;"),
    mut("sync_set_busy", RUN, SYNC_SCOPE,
        "if (!!info.busy !== S.busy) setBusy(!!info.busy);", "if (false) setBusy(!!info.busy);"),
    mut("sync_render", RUN, SYNC_SCOPE, "    render();\n", ""),

    # 窗口重新可见时收掉残留的正在停止
    mut("window_stopping", APP, WINDOW_SCOPE, "if (!info.busy) S.stopping = false;",
        "if (info.busy) S.stopping = false;"),
]


def apply_mutation(root: Path, item: dict) -> None:
    path = root / item["path"]
    text = path.read_text(encoding="utf-8")
    start = text.find(item["scope"]) if item["scope"] else 0
    if start < 0:
        raise AssertionError("scope not found: %s::%s" % (item["path"], item["scope"]))
    at = text.find(item["needle"], start)
    if at < 0:
        raise AssertionError("line not found: %s::%s" % (item["path"], item["needle"]))
    path.write_text(text[:at] + item["replacement"] + text[at + len(item["needle"]):],
                    encoding="utf-8", newline="")


def parses(root: Path, item: dict) -> bool:
    target = root / item["path"]
    probe = root / "mutant.mjs"
    shutil.copyfile(target, probe)
    result = subprocess.run(["node", "--check", str(probe)], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    probe.unlink()
    return result.returncode == 0


def run_test(root: Path, name: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", name],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    match = re.search(r"(?:FAIL|ERROR): ([^\r\n]+)", output)
    return result.returncode, (name + ": " + match.group(1)) if match else name


def check(root: Path, item: dict) -> dict:
    path = root / item["path"]
    original = path.read_text(encoding="utf-8")
    try:
        apply_mutation(root, item)
    except AssertionError as error:
        return {"id": item["id"], "status": "invalid", "detail": str(error)}
    try:
        if not parses(root, item):
            return {"id": item["id"], "status": "invalid", "detail": "node --check 没过"}
        for name in [FIRST] + REST:
            code, detail = run_test(root, name)
            if code:
                return {"id": item["id"], "status": "red", "detail": detail}
        return {"id": item["id"], "status": "green", "detail": "四个文件都过"}
    finally:
        path.write_text(original, encoding="utf-8", newline="")


def worker(items: list[dict], index: int) -> list[dict]:
    root = Path(tempfile.mkdtemp(prefix="plan-transitions-mut-%d-" % index))
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
