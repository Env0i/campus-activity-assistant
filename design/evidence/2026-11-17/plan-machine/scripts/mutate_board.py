#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐条变异计划栏标题区的状态机判断与样子表每一项，看现有测试能不能逐条抓住。

每条变异都在自己那份工作区副本里做：先改一处，再按顺序跑
test_plan_machine.py → test_ui_plan_board.py → test_ui_plan_flow.py，首红即停；
三条都绿才跑 test_ui_main_window_plan.py → test_ui_contract_plan.py → test_ui_exit_paths_plan.py。
改完立刻还原，副本复用。四个进程并行。

用法（仓库根执行）：
  python -B design/evidence/<日期>/plan-machine/scripts/mutate_board.py [--workers 4]

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from board_grid import copy_current  # noqa: E402

ROOT = Path(__file__).resolve().parents[5]
STATE = "local/ui/features/plan/state-machine.js"
VIEW = "local/ui/features/plan/view.js"
FIRST = ["test_plan_machine.py", "test_ui_plan_board.py", "test_ui_plan_flow.py"]
SECOND = ["test_ui_main_window_plan.py", "test_ui_contract_plan.py", "test_ui_exit_paths_plan.py"]


def mut(mid, path, scope, needle, replacement):
    return {"id": mid, "path": path, "scope": scope, "needle": needle,
            "replacement": replacement}


# 状态机：十九条判断逐条挡掉，外加条款坑的三个条件与阶段清单本身
PHASE = [
    ("first_use", "if (!f.busy && f.present === false && !f.runtimeError) return \"first_use\";",
     "if (false) return \"first_use\";"),
    ("logging_in", "if (f.loginPending) return \"logging_in\";",
     "if (false) return \"logging_in\";"),
    ("result", "if (f.resultMode) return \"result\";", "if (false) return \"result\";"),
    ("terms_hold", "if (termsHold && !f.selectedCount) return \"terms_hold\";",
     "if (false) return \"terms_hold\";"),
    ("broken", "if (!f.busy && f.runtimeError && f.listState !== \"ready\") return \"broken\";",
     "if (false) return \"broken\";"),
    ("list_error", "if (!f.busy && f.listState === \"error\" && !f.itemsCount) return \"list_error\";",
     "if (false) return \"list_error\";"),
    ("list_loading",
     "if (!f.busy && f.listState === \"loading\" && !f.selectedCount) return \"list_loading\";",
     "if (false) return \"list_loading\";"),
    ("run_target",
     "if (phase === \"submitting\" || phase === \"arming\" || phase === \"waiting\") return \"run_target\";",
     "if (false) return \"run_target\";"),
    ("run_settling", "return phase === \"settling\" ? \"run_settling\" : \"run_preparing\";",
     "return \"run_preparing\";"),
    ("has_next", "if (f.hasNext) return f.nextOpenNow ? \"next_open\" : \"next_upcoming\";",
     "if (false) return f.nextOpenNow ? \"next_open\" : \"next_upcoming\";"),
    ("next_open_now", "\"next_open\" : \"next_upcoming\"", "\"next_upcoming\" : \"next_upcoming\""),
    ("none_upcoming", "if (f.listState !== \"ready\") return \"none_upcoming\";",
     "if (false) return \"none_upcoming\";"),
    ("school_empty", "if (!f.itemsCount) return \"school_empty\";",
     "if (false) return \"school_empty\";"),
    ("clock_pending", "if (!f.clockKnown && !f.demo) return \"clock_pending\";",
     "if (false) return \"clock_pending\";"),
    ("none_eligible", "return \"none_eligible\";", "return \"none_upcoming\";"),
    ("selected_paused", "if (termsHold) return \"selected_paused\";",
     "if (false) return \"selected_paused\";"),
    ("editing", "return f.editing ? \"editing\" : \"selected\";", "return \"selected\";"),
    ("terms_not_busy",
     "const termsHold = !f.busy && f.termsLocked && f.present !== false;",
     "const termsHold = f.termsLocked && f.present !== false;"),
    ("terms_present",
     "const termsHold = !f.busy && f.termsLocked && f.present !== false;",
     "const termsHold = !f.busy && f.termsLocked;"),
    ("phase_list_last", "\"none_upcoming\", \"selected_paused\", \"editing\", \"selected\",",
     "\"none_upcoming\", \"selected_paused\", \"editing\","),
]

MUTATIONS = [mut("phase-" + mid, STATE, "function boardPhase", needle, repl)
             for mid, needle, repl in PHASE if mid != "phase_list_last"]
MUTATIONS.append(mut("phase_list_last", STATE, "", PHASE[-1][1], PHASE[-1][2]))

# 样子表：每个阶段六件事各算一处（写文字、写 HTML、写地点时间的三支分开算）
ENTRIES = [
    ("first_use", 'tag: "首次使用"', 'tone: "off"', "dot: true", 'title: "登录后开始"',
     'text: "活动会在登录完成后自动加载。"', None),
    ("logging_in", 'tag: "登录中"', 'tone: "amber"', "dot: true",
     'title: "正在打开登录窗口"',
     'text: "在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。"', None),
    ("result", "tag: () => resultView().tag", "tone: () => resultView().tone", "dot: true",
     "title: () => resultView().title", "text: () => resultView().text", None),
    ("terms_hold", 'tag: "已暂停"', 'tone: "off"', "dot: true",
     'title: () => S.terms.unknown ? "重新确认条款后才能报名" : "同意条款后才能报名"',
     'text: () => S.terms.unknown ? "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。"\n'
     '      : "登录、活动列表和报名计划都停用了。帮助和设置照常可用。"', None),
    ("broken", 'tag: "不可用"', 'tone: "red"', "dot: true", 'title: "暂时不能报名"',
     'text: "程序组件缺失，处理办法在顶部提示里。"', None),
    ("list_error", 'tag: "需重试"', 'tone: "red"', "dot: true", 'title: "活动暂时没加载"',
     'text: "具体原因看左边列表的提示。"', None),
    ("list_loading", 'tag: "加载中"', 'tone: "off"', "dot: true", 'title: "活动列表正在加载"',
     'text: "先等这一次加载结束。"', None),
    ("run_target", "tag: (view) => runTagText(view)",
     'tone: (view) => view.phase === "submitting" ? "red" : "amber"', "dot: true",
     'title: (view) => view.item ? view.item.name : "这一场活动"',
     "text: (view) => runCaption(view)", None),
    ("run_settling", 'tag: "汇总中"', 'tone: "amber"', "dot: true", 'title: "正在汇总结果"',
     'text: "每一场都结束了，正在汇总这一轮的结果。"', None),
    ("run_preparing", 'tag: "准备中"', 'tone: "amber"', "dot: true", 'title: "正在准备报名"',
     'text: "计划已经接管，正在核对每一场的开放时间。"', None),
    ("next_open", 'tag: "开放中"', 'tone: "amber"', "dot: false",
     "title: (view, next) => next.name", None, "meta: (view, next) => boardMetaHtml(next)"),
    ("next_upcoming", 'tag: "下一场"', 'tone: "amber"', "dot: true",
     "title: (view, next) => next.name", None, "meta: (view, next) => boardMetaHtml(next)"),
    ("school_empty", 'tag: "暂时没有"', 'tone: "off"', "dot: true",
     'title: "学校当前没有活动"', 'text: "稍后刷新再看。"', None),
    ("clock_pending", 'tag: "时间待校准"', 'tone: "amber"', "dot: true",
     'title: "时间待校准"', None,
     'html: "校准北京时间后才能判断哪些场次可以报名。"\n'
     "      + '<button type=\"button\" class=\"btn btn-line btn-mini\" data-open-clock>查看时间详情</button>'"),
    ("none_eligible", 'tag: "暂时没有"', 'tone: "off"', "dot: true",
     'title: "没有可报名的场次"', 'text: "列表里的活动已报名、已截止或还没公布报名时间。"', None),
    ("none_upcoming", 'tag: "暂时没有"', 'tone: "off"', "dot: true",
     'title: "近期没有要开放的活动"',
     'text: "可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。"', None),
    ("selected_paused", 'tag: "已暂停"', 'tone: "off"', "dot: true",
     'title: (view, next, items) => "已选 " + items.length + " 场"',
     "text: (view, next, items) => selectionSummary(items)", None),
    ("editing", 'tag: "修改中"', 'tone: "amber"', "dot: true",
     'title: (view, next, items) => "已选 " + items.length + " 场"',
     "text: (view, next, items) => selectionSummary(items)", None),
    ("selected", 'tag: "报名计划"', 'tone: "amber"', "dot: true",
     'title: (view, next, items) => "已选 " + items.length + " 场"',
     "text: (view, next, items) => selectionSummary(items)", None),
]

for phase, tag, tone, dot, title, text, other in ENTRIES:
    scope = "  " + phase + ": {"
    MUTATIONS.append(mut("style-%s-tag" % phase, VIEW, scope, tag, 'tag: "mutated"'))
    MUTATIONS.append(mut("style-%s-tone" % phase, VIEW, scope, tone, 'tone: "mutated"'))
    MUTATIONS.append(mut("style-%s-dot" % phase, VIEW, scope, dot,
                         "dot: false" if dot == "dot: true" else "dot: true"))
    MUTATIONS.append(mut("style-%s-title" % phase, VIEW, scope, title, 'title: "mutated"'))
    if text:
        MUTATIONS.append(mut("style-%s-text" % phase, VIEW, scope, text, 'text: "mutated"'))
    if other:
        MUTATIONS.append(mut("style-%s-extra" % phase, VIEW, scope, other,
                             'meta: () => "mutated"' if other.startswith("meta") else 'html: "mutated"'))


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
    """变异后的那份源码还得是能解析的 JS，否则红得没意义。"""
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
        for name in FIRST + SECOND:
            code, detail = run_test(root, name)
            if code:
                return {"id": item["id"], "status": "red", "detail": detail}
        return {"id": item["id"], "status": "green", "detail": "六个文件都过"}
    finally:
        path.write_text(original, encoding="utf-8", newline="")


def worker(items: list[dict], index: int) -> list[dict]:
    root = Path(tempfile.mkdtemp(prefix="plan-machine-mut-%d-" % index))
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
