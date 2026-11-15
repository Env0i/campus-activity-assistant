#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""共用状态机与行绘制的逐条变异（量的单位是用户看得到的每一个结果）。

在临时目录的仓库副本里逐条变异：状态机 componentState 的每一条判断（判断链八条
加派生事实）与行绘制 paintComponentRow 的每一处写元素语句——条件换成相反或
false、兜底行换字面量、写文字的换空串。每条变异只跑组件相关的测试集合，按开销
从小到大跑，遇到第一个变红的文件就停（记下文件与变红用例）。一条都不红时，按
同样口径在开工提交导出的副本里做同型变异（old 字段给出旧代码里的定位与替换）：
改前也不红 = 老缺口（改前就没守这个结果，补行为测试）；改前会红 = 新引入的失守，
立即停下报告。

用法（仓库根）：
  python -B design/evidence/2026-11-15/component-machine/scripts/mutate_machine.py \
      --base-ref <开工提交短哈希> [--ids m01,m02] [--save-output <目录>]
全部变异都红退出 0；有老缺口退出 2；有新引入失守退出 1。定位按「文件、函数、
那一行的文字」，不按行号；副本不带 local/data 与任何 config.json；仓库本体不动。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

TEST_FILES = [
    "test_ui_component_rows.py",
    "test_component_machine.py",
    "test_ui_exit_paths_components.py",
    "test_ui_phone_access_rows.py",
    "test_reason_maps.py",
    "test_ui_contract_components.py",
    "test_ui_contract_settings.py",
    "test_ui_contract_shell.py",
    "test_ui_reliability.py",
    "test_phone_ui.py",
]

SM = "local/ui/features/components/state-machine.js"
VR = "local/ui/features/components/view-row.js"
PHONE_VIEW = "local/ui/features/phone-access/view.js"
OCR_VIEW = "local/ui/features/components/view-ocr.js"

MUTATIONS = [
    # ---- 状态机：判断链八条 ----
    {"id": "sm-01-downloading-cond", "file": SM, "func": "componentState",
     "find": ['  if (dl === "downloading") state = "downloading";'],
     "sub": ['  if (false) state = "downloading";']},
    {"id": "sm-02-verifying-cond", "file": SM, "func": "componentState",
     "find": ['  else if (dl === "verifying") state = "verifying";'],
     "sub": ['  else if (false) state = "verifying";']},
    {"id": "sm-03-checking-cond", "file": SM, "func": "componentState",
     "find": ['  else if (String(source.status || "") === "checking") state = "checking";'],
     "sub": ['  else if (false) state = "checking";']},
    {"id": "sm-04-outdated-cond", "file": SM, "func": "componentState",
     "find": ['  else if (String(source.status || "") === "outdated") state = "outdated";'],
     "sub": ['  else if (false) state = "outdated";']},
    {"id": "sm-05-broken-cond", "file": SM, "func": "componentState",
     "find": ['  else if (String(source.status || "") === "failed") state = "broken";'],
     "sub": ['  else if (false) state = "broken";']},
    {"id": "sm-06-ready-cond", "file": SM, "func": "componentState",
     "find": ['  else if (source.ready) state = "enabled";'],
     "sub": ['  else if (false) state = "enabled";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      install.hidden = phase !== "missing" && phase !== "outdated";'],
             "sub": ['      install.hidden = false;']}},
    {"id": "sm-07-available-cond", "file": SM, "func": "componentState",
     "find": ['  else if (source.available) state = "disabled";'],
     "sub": ['  else if (false) state = "disabled";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      install.hidden = phase !== "missing" && phase !== "outdated";'],
             "sub": ['      install.hidden = false;']}},
    {"id": "sm-08-missing-fallback", "file": SM, "func": "componentState",
     "find": ['  else state = "missing";'],
     "sub": ['  else state = "disabled";'],
     "old": {"file": OCR_VIEW, "func": "paintOcrDownload",
             "find": ['  const downloadBtn = $("#btn-ocr-download");'],
             "sub": ['  const downloadBtn = null;']}},
    # ---- 状态机：派生事实 ----
    {"id": "sm-09-downloading-fact", "file": SM, "func": "componentState",
     "find": ['  const downloading = state === "downloading" || state === "verifying";'],
     "sub": ['  const downloading = false;']},
    {"id": "sm-10-loading-fact", "file": SM, "func": "componentState",
     "find": ['    loading: downloading || state === "checking" || installing,'],
     "sub": ['    loading: false,']},
    {"id": "sm-11-failed-fact", "file": SM, "func": "componentState",
     "find": ['    failed: dl === "failed",'],
     "sub": ['    failed: false,'],
     "old": {"file": OCR_VIEW, "func": "paintOcrDownload",
             "find": ['  const failed = dlState === "failed";'],
             "sub": ['  const failed = false;']}},
    {"id": "sm-12-cancelled-fact", "file": SM, "func": "componentState",
     "find": ['    cancelled: dl === "cancelled",'],
     "sub": ['    cancelled: false,'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneText("#phone-component-state", phase === "missing" && !missingErr && dl === "cancelled"',
                      '      ? "下载已取消，没有装任何东西。" : "");'],
             "sub": ['    phoneText("#phone-component-state", phase === "missing" && !missingErr && false',
                     '      ? "下载已取消，没有装任何东西。" : "");']}},
    {"id": "sm-13-installing-fact", "file": SM, "func": "componentState",
     "find": ['    installing: installing,'],
     "sub": ['    installing: false,'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    const installing = !!(PhonePanel.installing && PhonePanel.installing.phone_control);'],
             "sub": ['    const installing = false;']}},
    {"id": "sm-14-busy-fact", "file": SM, "func": "componentState",
     "find": ['    busy: !!env.busy,'],
     "sub": ['    busy: false,'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    const busy = !!PhonePanel.busy;'],
             "sub": ['    const busy = false;']}},
    {"id": "sm-15-location-fact", "file": SM, "func": "componentState",
     "find": ['    location: env.location || null,'],
     "sub": ['    location: null,'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    const loc = PhonePanel.location;'],
             "sub": ['    const loc = null;']}},
    {"id": "sm-16-download-fact", "file": SM, "func": "componentState",
     "find": ['    download: download,'],
     "sub": ['    download: {},'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    const total = Number(download.total_bytes || 0);',
                      '    const done = Number(download.downloaded || 0);'],
             "sub": ['    const total = 0;',
                     '    const done = 0;']}},
    # ---- 行绘制：写元素语句 ----
    {"id": "vr-01-install-hidden", "file": VR, "func": "paintComponentRow",
     "find": ['    install.hidden = state !== "missing" && state !== "outdated";'],
     "sub": ['    install.hidden = !(state !== "missing" && state !== "outdated");'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      install.hidden = phase !== "missing" && phase !== "outdated";'],
             "sub": ['      install.hidden = !(phase !== "missing" && phase !== "outdated");']}},
    {"id": "vr-02-install-disabled", "file": VR, "func": "paintComponentRow",
     "find": ['    install.disabled = facts.busy || facts.installing;'],
     "sub": ['    install.disabled = false;'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      install.disabled = busy || installing;'],
             "sub": ['      install.disabled = false;']}},
    {"id": "vr-03-install-text", "file": VR, "func": "paintComponentRow",
     "find": ['    install.textContent = state === "outdated" ? INSTALL_TEXT_OUTDATED',
              '      : (facts.failed ? INSTALL_TEXT_FAILED : INSTALL_TEXT_DEFAULT);'],
     "sub": ['    install.textContent = "";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      install.textContent = phase === "outdated" ? "更新组件"',
                      '        : (failed ? "重新下载" : "下载并安装");'],
             "sub": ['      install.textContent = "";']}},
    {"id": "vr-04-cancel-hidden", "file": VR, "func": "paintComponentRow",
     "find": ['    cancel.hidden = !facts.downloading;'],
     "sub": ['    cancel.hidden = facts.downloading;'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      cancel.hidden = !downloading;'],
             "sub": ['      cancel.hidden = downloading;']}},
    {"id": "vr-05-cancel-disabled", "file": VR, "func": "paintComponentRow",
     "find": ['    cancel.disabled = facts.busy || state === "verifying";'],
     "sub": ['    cancel.disabled = false;'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      cancel.disabled = busy || phase === "verifying";'],
             "sub": ['      cancel.disabled = false;']}},
    {"id": "vr-06-cancel-text", "file": VR, "func": "paintComponentRow",
     "find": ['    cancel.textContent = state === "verifying" ? CANCEL_TEXT_VERIFYING : CANCEL_TEXT;'],
     "sub": ['    cancel.textContent = "";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      cancel.textContent = phase === "verifying" ? "校验中…" : "取消下载";'],
             "sub": ['      cancel.textContent = "";']}},
    {"id": "vr-07-missing-show", "file": VR, "func": "paintComponentRow",
     "find": ['  rowShow(spec.missingId, state === "missing" && !facts.installing);'],
     "sub": ['  rowShow(spec.missingId, !(state === "missing" && !facts.installing));'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneShow("#phone-missing", phase === "missing" && !installing);'],
             "sub": ['    phoneShow("#phone-missing", !(phase === "missing" && !installing));']}},
    {"id": "vr-08-import-show", "file": VR, "func": "paintComponentRow",
     "find": ['  rowShow(spec.importLineId, (state === "missing" || state === "outdated")',
              '    && facts.failed && !facts.installing);'],
     "sub": ['  rowShow(spec.importLineId, false);'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneShow("#phone-import-line", (phase === "missing" || phase === "outdated") && failed && !installing);'],
             "sub": ['    phoneShow("#phone-import-line", false);']}},
    {"id": "vr-09-loading-show", "file": VR, "func": "paintComponentRow",
     "find": ['  rowShow(spec.loadingId, facts.loading);'],
     "sub": ['  rowShow(spec.loadingId, !facts.loading);'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneShow("#phone-loading", loading);'],
             "sub": ['    phoneShow("#phone-loading", !loading);']}},
    {"id": "vr-10-prog-text", "file": VR, "func": "paintComponentRow",
     "find": ['  rowText(spec.progTextId, facts.installing ? PROG_TEXT_INSTALLING',
              '    : (state === "checking" ? PROG_TEXT_CHECKING',
              '      : (state === "verifying" ? PROG_TEXT_VERIFYING : spec.downloadText)));'],
     "sub": ['  rowText(spec.progTextId, "");'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneText("#phone-prog-text", installing ? "正在安装组件…"',
                      '      : (phase === "checking" ? "正在检查组件…"',
                      '      : (phase === "verifying" ? "下载完成，正在校验组件…" : "正在下载手机控制组件")));'],
             "sub": ['    phoneText("#phone-prog-text", "");']}},
    {"id": "vr-11-prog-num", "file": VR, "func": "paintComponentRow",
     "find": ['    num.textContent = state === "downloading" && total > 0',
              '      ? (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB" : "";'],
     "sub": ['    num.textContent = "";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      num.textContent = phase === "downloading" && total > 0',
                      '        ? (done / 1048576).toFixed(1) + " / " + (total / 1048576).toFixed(1) + " MB" : "";'],
             "sub": ['      num.textContent = "";']}},
    {"id": "vr-12-progress-aria", "file": VR, "func": "paintComponentRow",
     "find": ['  if (bar) bar.setAttribute("aria-valuenow", String(pct));'],
     "sub": ['  if (bar) bar.setAttribute("aria-valuenow", "0");'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    if (bar) bar.setAttribute("aria-valuenow", String(pct));'],
             "sub": ['    if (bar) bar.setAttribute("aria-valuenow", "0");']}},
    {"id": "vr-13-progress-fill", "file": VR, "func": "paintComponentRow",
     "find": ['  if (fill && fill.style) fill.style.width = pct + "%";'],
     "sub": ['  if (fill && fill.style) fill.style.width = "0%";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    if (fill && fill.style) fill.style.width = pct + "%";'],
             "sub": ['    if (fill && fill.style) fill.style.width = "0%";']}},
    {"id": "vr-14-error-bar", "file": VR, "func": "paintComponentRow",
     "find": ['  rowText(spec.errorId, texts.componentError || "");'],
     "sub": ['  rowText(spec.errorId, "");'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneText("#phone-component-error", missingErr);'],
             "sub": ['    phoneText("#phone-component-error", "");']}},
    {"id": "vr-15-cancelled-note", "file": VR, "func": "paintComponentRow",
     "find": ['  rowText(spec.cancelledNoteId, texts.cancelledNote || "");'],
     "sub": ['  rowText(spec.cancelledNoteId, "");'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneText("#phone-component-state", phase === "missing" && !missingErr && dl === "cancelled"',
                      '      ? "下载已取消，没有装任何东西。" : "");'],
             "sub": ['    phoneText("#phone-component-state", "");']}},
    {"id": "vr-16-loc-before-show", "file": VR, "func": "paintComponentRow",
     "find": ['      ? state === "missing" && !!facts.location'],
     "sub": ['      ? false'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    phoneShow("#phone-loc-before", phase === "missing" && !!loc);'],
             "sub": ['    phoneShow("#phone-loc-before", false);']}},
    {"id": "vr-17-loc-after-show", "file": VR, "func": "paintComponentRow",
     "find": ['      : state !== "missing" && !facts.loading && !!facts.location;'],
     "sub": ['      : false;'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['    const after = phoneShow("#phone-loc-after", phase !== "missing" && !loading && !!loc);'],
             "sub": ['    const after = phoneShow("#phone-loc-after", false);']}},
    {"id": "vr-18-loc-title", "file": VR, "func": "paintComponentRow",
     "find": ['    if (box && facts.location) box.title = facts.location.path || facts.location.short;'],
     "sub": ['    if (box && facts.location) box.title = "";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      if (box && loc) box.title = loc.path || loc.short;'],
             "sub": ['      if (box && loc) box.title = "";']}},
    {"id": "vr-19-loc-path-text", "file": VR, "func": "paintComponentRow",
     "find": ['    if (code) code.textContent = facts.location ? facts.location.short : "";'],
     "sub": ['    if (code) code.textContent = "";'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      if (code) code.textContent = loc ? loc.short : "";'],
             "sub": ['      if (code) code.textContent = "";']}},
    {"id": "vr-20-open-disabled", "file": VR, "func": "paintComponentRow",
     "find": ['  if (open) open.disabled = facts.busy;'],
     "sub": ['  if (open) open.disabled = false;'],
     "old": {"file": PHONE_VIEW, "func": "paintPhoneAccess",
             "find": ['      if (open) open.disabled = busy;'],
             "sub": ['      if (open) open.disabled = false;']}},
]


def tracked_files():
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z"],
                         cwd=str(REPO), capture_output=True, check=True)
    keep = []
    for rel in out.stdout.decode("utf-8").split("\0"):
        if not rel:
            continue
        path = rel.replace("\\", "/")
        if path.endswith("/config.json") or path == "config.json":
            continue
        if path.startswith("local/data/") or path.startswith("server/data/"):
            continue
        keep.append(path)
    return keep


def make_workspace_copy(root: Path) -> None:
    """镜像当前工作区：git ls-files 清单 + local/ui 与 local/tests 下未入库的文件。"""
    for rel in tracked_files():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dst)
    for subdir in ("local/ui", "local/tests"):
        for src in (REPO / subdir).rglob("*"):
            if not src.is_file() or "__pycache__" in src.parts or src.suffix == ".pyc":
                continue
            dst = root / src.relative_to(REPO)
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)


def make_head_copy(ref: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix="component-machine-mut-head-"))
    data = subprocess.run(["git", "archive", ref], cwd=str(REPO), check=True,
                          capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(root, filter="data")
    return root


def function_span(lines, func):
    """JS 函数体在文件里的行号范围（function/async function 定义到下一个同级定义）。"""
    if func is None:
        return 0, len(lines)
    start = None
    pat = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+%s\s*\(" % re.escape(func))
    for i, text_line in enumerate(lines):
        if pat.match(text_line):
            start = i
            break
    if start is None:
        raise LookupError("找不到函数 %s" % func)
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        text_line = lines[j]
        if not text_line.strip():
            continue
        cur = len(text_line) - len(text_line.lstrip())
        head = text_line.strip()
        if cur <= indent and (head.startswith("function ")
                              or head.startswith("export ")
                              or head.startswith("async ")
                              or head.startswith("const ")):
            return start, j
    return start, len(lines)


def apply_mutation(root: Path, spec) -> int:
    path = root / spec["file"]
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines(keepends=True)
    stripped = [ln.rstrip("\r\n") for ln in lines]
    start, end = function_span(stripped, spec.get("func"))
    need = len(spec["find"])
    hits = []
    for i in range(start, min(end, len(stripped)) - need + 1):
        if all(stripped[i + k] == spec["find"][k] for k in range(need)):
            hits.append(i)
    if len(hits) != 1:
        raise LookupError("定位到 %d 处（应为 1）" % len(hits))
    i = hits[0]
    if spec["sub"]:
        lines[i:i + need] = [ln + "\n" for ln in spec["sub"]]
    else:
        del lines[i:i + need]
    path.write_text("".join(lines), encoding="utf-8", newline="")
    return i + 1


def syntax_problem(path: Path):
    """JS 文件用 node --check（与既有变异脚本同一口径）；不过时返回错误摘要。"""
    proc = subprocess.run(["node", "--check", str(path)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout or "")[-300:]
    return ""


def run_test_files(root: Path):
    """按开销从小到大跑组件相关的测试集合，遇到第一个变红的文件就停。

    node 沙箱偶发崩溃（JS 行为测试崩溃）不算数：崩溃样子的失败重跑一次该文件，
    重跑绿了就继续看下一个文件。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for pattern in TEST_FILES:
        if not (root / "local" / "tests" / pattern).is_file():
            continue
        for attempt in (1, 2):
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s",
                 "local/tests", "-p", pattern],
                cwd=str(root), capture_output=True, text=True, encoding="utf-8",
                errors="replace", env=env, timeout=600)
            if proc.returncode == 0:
                break
            text = (proc.stdout or "") + (proc.stderr or "")
            reds = []
            for match in re.finditer(r"^(?:FAIL|ERROR): (.+)$", text, re.M):
                name = match.group(1).split(" (")[0].strip()
                if name not in reds:
                    reds.append(name)
            first = ""
            blocks = re.split(r"={20,}", text)
            for block in blocks[1:]:
                lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
                for ln in reversed(lines):
                    if re.match(r"^(AssertionError|KeyError|TypeError|AttributeError|"
                                r"OSError|ValueError|RuntimeError|NameError|IndexError)\b", ln):
                        first = ln
                        break
                if first:
                    break
            crashed = ("JS 行为测试崩溃" in text or "JS 没有输出结果" in text
                       or not reds)
            if crashed and attempt == 1:
                continue
            return {"file": pattern, "exit": proc.returncode, "red": reds,
                    "first": first, "raw": text[-1800:]}
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="开工提交短哈希")
    parser.add_argument("--ids", default="", help="只跑这些编号（逗号分隔）")
    parser.add_argument("--save-output", default="", help="把每条的结论 JSON 另存到这个目录")
    args = parser.parse_args()
    todo = MUTATIONS
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        todo = [m for m in MUTATIONS if m["id"] in wanted]
    ws_copy = Path(tempfile.mkdtemp(prefix="component-machine-mut-ws-"))
    head_copy = make_head_copy(args.base_ref)
    make_workspace_copy(ws_copy)
    head_pristine = {}
    for spec in todo:
        old = spec.get("old")
        if old and old["file"] not in head_pristine:
            head_pristine[old["file"]] = (head_copy / old["file"]).read_text(encoding="utf-8")
    gaps, defects, reds_count = [], [], 0
    summary = []
    dirty_ws = set()
    for spec in todo:
        for f in sorted(dirty_ws):
            shutil.copyfile(REPO / f, ws_copy / f)
        shutil.copyfile(REPO / spec["file"], ws_copy / spec["file"])
        print("=" * 8, spec["id"], "=" * 8)
        entry = {"id": spec["id"], "verdict": "", "red": None, "old_red": None}
        result = None
        try:
            apply_mutation(ws_copy, spec)
            bad = syntax_problem(ws_copy / spec["file"])
            if bad:
                raise LookupError("变异后语法不过：%s" % bad)
            result = run_test_files(ws_copy)
        except LookupError as exc:
            print("定位或语法失败：%s" % exc)
            entry["verdict"] = "定位失败"
            defects.append(spec["id"])
            summary.append(entry)
            continue
        if result:
            reds_count += 1
            entry["verdict"] = "红"
            entry["red"] = result
            print("红：%s 退出码 %d，变红 %d 条，第一条：%s"
                  % (result["file"], result["exit"], len(result["red"]),
                     (result["red"] or [""])[0] if result["red"] else result["first"]))
        else:
            old = spec.get("old")
            if not old:
                print("不红，且没有给出改前同型变异的定位——按老缺口处理，需补行为测试")
                entry["verdict"] = "老缺口（改前无从同型变异，按没人守处理）"
                gaps.append(spec["id"])
            else:
                (head_copy / old["file"]).write_text(head_pristine[old["file"]], encoding="utf-8")
                try:
                    apply_mutation(head_copy, old)
                    result_old = run_test_files(head_copy)
                except LookupError as exc:
                    print("改前同型变异定位失败：%s" % exc)
                    entry["verdict"] = "老缺口（改前定位失败，按没人守处理）"
                    gaps.append(spec["id"])
                    result_old = None
                if result_old is not None and result_old:
                    print("新引入的失守：改前同型变异会红（%s），现在不红——停下报告"
                          % result_old["file"])
                    entry["verdict"] = "新引入失守"
                    entry["old_red"] = result_old
                    defects.append(spec["id"])
                elif result_old is not None:
                    print("改前同型变异也不红——老缺口（改前就没守这个结果），需补行为测试")
                    entry["verdict"] = "老缺口（改前同型变异也不红）"
                    gaps.append(spec["id"])
        summary.append(entry)
        dirty_ws.add(spec["file"])
        for f in sorted(dirty_ws):
            shutil.copyfile(REPO / f, ws_copy / f)
        old = spec.get("old")
        if old:
            (head_copy / old["file"]).write_text(head_pristine[old["file"]],
                                                 encoding="utf-8")
        if args.save_output:
            out_dir = Path(args.save_output)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / (spec["id"] + ".json")).write_text(
                json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 30)
    print("结论：变异 %d 条，红 %d 条，老缺口 %d（%s），新引入失守 %d（%s）"
          % (len(todo), reds_count, len(gaps), "、".join(gaps) or "无",
             len(defects), "、".join(defects) or "无"))
    if args.save_output:
        out_dir = Path(args.save_output)
        (out_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.rmtree(ws_copy, ignore_errors=True)
    shutil.rmtree(head_copy, ignore_errors=True)
    if defects:
        return 1
    if gaps:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
