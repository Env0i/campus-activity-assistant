#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐字核对：搬走的每一段能不能在新位置一字不差地找到。

做法——从开工 HEAD 取三个原文件，按「紧挨着的注释 + 顶层声明」切成段；对每一段，
在新文件里按同样的切法取一段，把新段声明行上的 `export ` 去掉后与旧段逐字比较；
再反过来把新文件里不属于原文的行分类，分不进任何一类的必须为零。
最后核对 plan-panel.js 留下的部分与开工 HEAD 相比只少了搬走的段。

@author Author
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BASE = "abd2a6a"
PANEL = "local/ui/views/plan-panel.js"
PLAN = "local/ui/state/plan.js"
TASK = "local/ui/state/task-display.js"
NEW = {
    "state.js": "local/ui/features/plan/state.js",
    "actions.js": "local/ui/features/plan/actions.js",
    "state-task.js": "local/ui/features/plan/state-task.js",
    "state-board.js": "local/ui/features/plan/state-board.js",
    "view.js": "local/ui/features/plan/view.js",
}
PANEL_NAMES = set()
for _names in (["paintSelected", "setBoardTag", "paintBoardState", "boardMetaHtml", "paintBoardActions",
                "paintEditNote", "paintRunPanel", "paintResultPanel", "paintPlan", "taskViaHtml", "taskHtml"],
               ["selectionSummary", "RUN_SOON_S", "runTagText", "runHeadKey", "runCaption", "boardPlanState",
                "editNoteText", "resultMode", "boardTargetItem", "LATE_WINDOW_S", "planLate",
                "earliestWaitingOpen", "resultCounts", "resultView", "reselectableIds",
                "earliestSelectedOpen", "stopReasonText", "retryDeadline"],
               ["verifyTask"]):
    PANEL_NAMES.update(_names)

MOVED = {
    "state.js": ["mergeTask", "PLAN_TERMINAL", "TASK_TERMINAL", "maxPlanGen", "planEventOwns",
                 "admitPlanEvent", "openResultPage", "closeResultPage", "syncResultSelection",
                 "resultPageOpen", "planOutcome", "unknownLabel", "selectionSignature"],
    "actions.js": ["advancePlanStatus", "handlePlan", "handleTask", "verifyTask"],
    "state-task.js": ["RUNNING_STATUSES", "taskDisplayItem", "taskDisplayPhase", "taskDisplayLabel",
                      "taskModePrefix", "taskPrepared", "taskDisplayDetail", "executionView",
                      "verifiedSigned", "telemetryDeadline", "submittingDetail", "effectiveRetryDeadline"],
    "state-board.js": ["selectionSummary", "RUN_SOON_S", "runTagText", "runHeadKey", "runCaption",
                       "boardPlanState", "editNoteText", "resultMode", "boardTargetItem", "LATE_WINDOW_S",
                       "planLate", "earliestWaitingOpen", "resultCounts", "resultView", "reselectableIds",
                       "earliestSelectedOpen", "stopReasonText", "retryDeadline"],
    "view.js": ["paintSelected", "setBoardTag", "paintBoardState", "boardMetaHtml", "paintBoardActions",
                "paintEditNote", "paintRunPanel", "paintResultPanel", "paintPlan", "taskViaHtml", "taskHtml"],
}


def read_head(rel: str) -> list[str]:
    out = subprocess.run(["git", "show", "%s:%s" % (BASE, rel)], cwd=str(ROOT),
                         capture_output=True, check=True).stdout.decode("utf-8")
    return out.split("\n")


def read_now(rel: str) -> list[str]:
    return (ROOT / rel).read_text(encoding="utf-8").split("\n")


def decl_spans(lines: list[str]) -> dict[str, tuple[int, int]]:
    """顶层声明 → (声明首行, 结束行)，1 起。"""
    spans = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^(?:export )?(?:async )?function ([A-Za-z_$][\w$]*)", lines[i])
        m2 = re.match(r"^(?:export )?(?:const|let) ([A-Za-z_$][\w$]*)", lines[i])
        if m or m2:
            name = (m or m2).group(1)
            depth, seen, j = 0, False, i
            while j < len(lines):
                code = re.sub(r"//.*", "", lines[j])
                for ch in code:
                    if ch == "{":
                        depth += 1
                        seen = True
                    elif ch == "}":
                        depth -= 1
                if not m and not seen and code.rstrip().endswith(";"):
                    break
                if seen and depth == 0:
                    break
                j += 1
            spans[name] = (i + 1, j + 1)
            i = j + 1
            continue
        i += 1
    return spans


def block_start(lines: list[str], decl_start: int) -> int:
    s = decl_start
    while s - 1 >= 1 and lines[s - 2].strip().startswith(("//", "/*", "*")):
        s -= 1
        if lines[s - 1].strip().startswith("/*"):
            break
    if s < decl_start and lines[s - 1].strip().startswith("/*") and s == 1:
        return decl_start          # 这一块是文件头，不算函数的注释
    while s - 1 >= 1 and lines[s - 2].strip() == "":
        s -= 1
    return s


def take_block(lines: list[str], start: int, end: int) -> list[str]:
    text = lines[start - 1:end]
    while text and text[0].strip() == "":
        text.pop(0)
    while text and text[-1].strip() == "":
        text.pop()
    return text


def find_block(new_lines: list[str], block: list[str]) -> bool:
    n = len(block)
    for i in range(len(new_lines) - n + 1):
        if strip_export(new_lines[i:i + n]) == block:
            return True
    return False


def _decl_len(block: list[str]) -> int:
    for i, line in enumerate(block):
        if re.match(r"^(?:function|const|let) ", strip_export([line])[0]):
            return len(block) - i
    return len(block)


def strip_export(text: list[str]) -> list[str]:
    out = []
    for line in text:
        out.append(re.sub(r"^export (function|const|let) ", r"\1 ", line, count=1))
    return out


def main() -> int:
    report = {"segments": 0, "found": 0, "missing": [], "different": [],
              "extra_lines": {}, "panel_ok": False, "panel_extra": []}
    for target, names in MOVED.items():
        new_lines = read_now(NEW[target])
        spans = decl_spans(new_lines)
        for name in names:
            report["segments"] += 1
            src_file = PANEL if name in PANEL_NAMES else (
                PLAN if name in MOVED["state.js"] + MOVED["actions.js"] else TASK)
            old_lines = read_head(src_file)
            old_span = decl_spans(old_lines).get(name)
            if not old_span:
                report["missing"].append([name, "旧文件里没找到声明"])
                continue
            old_block = take_block(old_lines, block_start(old_lines, old_span[0]), old_span[1])
            if name not in spans:
                report["missing"].append([name, "新文件里没找到声明"])
                continue
            if find_block(new_lines, old_block):
                report["found"] += 1
            else:
                decl_only = old_block[-_decl_len(old_block):]
                if find_block(new_lines, decl_only):
                    report["different"].append([name, "注释不同"])
                else:
                    report["different"].append([name, "正文不同"])
    # 反向：新文件里不属于原文的行
    original = set()
    for rel in (PANEL, PLAN, TASK):
        original.update(read_head(rel))
    for target in NEW.values():
        extra = []
        for line in read_now(target):
            if line in original or line.strip() == "":
                continue
            if re.match(r"^export (function|const|let) ", line) and strip_export([line])[0] in original:
                continue
            if line.startswith("import {") or line.startswith("/* 计划栏的") or line.startswith("/* 计划栏（"):
                continue
            extra.append(line[:80])
        report["extra_lines"][target] = extra
    # plan-panel.js：原文减掉搬走的段
    panel_old = read_head(PANEL)
    cut = set()
    spans = decl_spans(panel_old)
    for name in MOVED["view.js"] + MOVED["state-board.js"] + MOVED["actions.js"] + MOVED["state.js"]:
        if name in spans:
            a, b = spans[name]
            start = 4 if name == "paintSelected" else block_start(panel_old, a)
            for i in range(start, b + 1):
                cut.add(i)
    expect = [line for i, line in enumerate(panel_old, start=1) if i not in cut]
    panel_now = read_now(PANEL)
    if expect == panel_now:
        report["panel_ok"] = True
    else:
        for i, (a, b) in enumerate(zip(expect, panel_now)):
            if a != b:
                report["panel_extra"].append([i + 1, a[:60], b[:60]])
                break
        report["panel_extra"].append(["行数", len(expect), len(panel_now)])
    print(json.dumps(report, ensure_ascii=False, indent=1))
    bad = report["missing"] or report["different"] or any(report["extra_lines"].values()) \
        or not report["panel_ok"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
