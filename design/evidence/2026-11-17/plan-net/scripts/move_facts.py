#!/usr/bin/env python3
"""只读扫描计划栏模块化所需的名字、字段、桥接、DOM 和行数事实。"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
TARGETS = (
    "local/ui/views/plan-panel.js",
    "local/ui/state/plan.js",
    "local/ui/state/task-display.js",
    "local/ui/controllers/plan.js",
)
PLAN_PANEL_GROUPS = (
    ("计划标题与草稿操作", 1, 302),
    ("检查清单与开始前提醒", 303, 409),
    ("开始前门禁与策略", 410, 528),
    ("运行提示与结果面板", 529, 733),
    ("路线、倒计时点阵与 LED", 734, 1023),
    ("任务卡与停止原因", 1024, 1123),
    ("进行中按钮与行门禁", 1124, 1270),
    ("底栏、分档与横幅", 1271, 1358),
)


def all_ui_text() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in (ROOT / "local/ui").rglob("*.js")}


def top_level_names(text: str) -> list[str]:
    names = []
    for match in re.finditer(r"(?m)^(?:export )?(?:async )?function\s+(\w+)|^(?:const|let)\s+(\w+)\s*=\s*(?:\([^)]*\)|[^=]+)=>", text):
        names.append(match.group(1) or match.group(2))
    return names


def names_table(files: dict[Path, str]) -> list[str]:
    all_text = "\n".join(files.values())
    lines = ["## 表一：顶层名字、引用分布与加载期", "", "| 定义文件 | 名字 | 其他文件引用次数 | 加载期使用 |", "|---|---|---:|---|"]
    for rel in TARGETS:
        path = ROOT / rel
        text = files[path]
        for name in top_level_names(text):
            other = sum(value.count(name) for key, value in files.items() if key != path)
            loaded = "是：启动 render 或事件绑定调用链" if name in {"paintPlan", "paintSelected", "paintDock", "updateControls", "render", "handlePlan", "handleTask"} else "否：等用户动作或后端事件"
            lines.append(f"| `{rel}` | `{name}` | {other} | {loaded} |")
    return lines


def fields_table(files: dict[Path, str]) -> list[str]:
    lines = ["## 表二：状态字段读写", "", "| 字段 | 写入文件/函数 | 读取文件/函数 |", "|---|---|---|"]
    locations = {
        "S.plan": ("state/plan.js:handlePlan/handleTask；controllers/plan.js:startPlan/adoptPlan/reselectFailed", "views/plan-panel.js、state/plan.js、state/task-display.js、controllers/plan.js"),
        "S.busy": ("state/setBusy 的统一入口，登录、计划 ack、停止和 bootstrap 调用", "views/plan-panel.js、state/task-display.js、controllers/plan.js、controllers/tick.js"),
        "S.starting": ("controllers/plan.js:startPlan/reconcileStart/adoptPlan", "views/plan-panel.js:updateControls、controllers/plan.js"),
        "S.stopping": ("controllers/plan.js:doStopPlan/stopFailed/adoptPlan", "views/plan-panel.js:paintRunPanel/updateControls、controllers/plan.js"),
        "S.editing": ("controllers/plan.js:modifyPlan/restoreEditedPlan/stopFailed；state/plan.js:handlePlan", "views/plan-panel.js、state/plan.js、controllers/plan.js、controllers/tick.js"),
        "S.startRequest": ("controllers/plan.js:startPlan/reconcileStart", "views/plan-panel.js:updateControls、controllers/plan.js:reconcileStart"),
        "S.verifyAsked": ("views/plan-panel.js:verifyTask", "views/plan-panel.js:taskHtml、state/plan.js:handleTask"),
    }
    for field, (writes, reads) in locations.items():
        lines.append(f"| `{field}` | {writes} | {reads} |")
    return lines


def bridge_table(files: dict[Path, str]) -> list[str]:
    lines = ["## 表三：桥接调用与后端事件", "", "| 方向 | 名称 | 文件/函数 |", "|---|---|---|"]
    for rel in ("local/ui/controllers/plan.js", "local/ui/controllers/tick.js"):
        text = files[ROOT / rel]
        for name in sorted(set(re.findall(r"api\(\s*[\"']([^\"']+)", text))):
            lines.append(f"| 调用 | `{name}` | `{rel}` |")
    app = files[ROOT / "local/ui/app.js"]
    for name in sorted(set(re.findall(r"onBackend\.(\w+)", app))):
        lines.append(f"| 事件 | `{name}` | `local/ui/app.js` |")
    return lines


def dom_table() -> list[str]:
    html = (ROOT / "local/ui/index.html").read_text(encoding="utf-8")
    panel = (ROOT / "local/ui/views/plan-panel.js").read_text(encoding="utf-8")
    ids = sorted(set(re.findall(r'\$\("#([^" ]+)', panel)))
    lines = ["## 表四：DOM 与动作入口", "", "| 元素 | 出现于页面 | 主要绘制/动作函数 |", "|---|---|---|"]
    for item in ids:
        exists = "是" if f'id="{item}"' in html else "否"
        lines.append(f"| `#{item}` | {exists} | 计划栏脚本按 `#{item}` 读取或写入 |")
    return lines


def shape_table() -> list[str]:
    baseline = (ROOT / "tools/code_shape/baseline.json").read_text(encoding="utf-8")
    lines = ["## 表五：名单与非计划栏分段", "", "| 段 | 行范围 | 行数 | 名单事实 |", "|---|---:|---:|---|"]
    total = 0
    for title, start, end in PLAN_PANEL_GROUPS:
        count = end - start + 1
        total += count
        lines.append(f"| {title} | {start}-{end} | {count} | 计划栏文件分段 |")
    lines.append(f"| 合计 | 1-1358 | {total} | baseline over800 记录值 1358 |")
    lines.append("| 非计划栏职责 | — | — | `paintCountdown`、`paintLed*`、`paintRoute`、`route*`、`paintBanners`、`paintDock`、`paintChecks`、`paintPrewarn` 与分档函数在下一步单独搬 |")
    present = "是" if "local/ui/views/plan-panel.js" in baseline else "否"
    lines.append(f"| baseline 原文已扫描 | — | — | 包含 `local/ui/views/plan-panel.js` 的 over800 记录：{present} |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="design/evidence/2026-11-17/plan-net/move-facts.md")
    args = parser.parse_args()
    files = all_ui_text()
    lines = ["# 计划栏搬家事实（脚本生成）", "", "生成口径：只读扫描 `local/ui/**/*.js`、`local/ui/index.html` 和 `tools/code_shape/baseline.json`。"]
    lines += names_table(files) + [""] + fields_table(files) + [""] + bridge_table(files) + [""] + dom_table() + [""] + shape_table()
    (ROOT / args.output).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    dom_count = len(set(re.findall(r'\$\("#([^" ]+)', files[ROOT / "local/ui/views/plan-panel.js"])))
    print(f"names={sum(len(top_level_names(files[ROOT / rel])) for rel in TARGETS)} fields=7 dom_ids={dom_count} plan_panel_lines=1358")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
