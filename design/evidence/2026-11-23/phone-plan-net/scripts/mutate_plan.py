#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页第三组（计划操作）13 个函数的五类单点变异与行为测试判定。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py --list
  python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py --baseline
  python design/evidence/2026-11-23/phone-plan-net/scripts/mutate_plan.py --workers 4 --out design/evidence/2026-11-23/phone-plan-net/before.md

@author Author
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
TARGET_FILES = ("local/ui/m/ui-plan.js",)
ALL_FUNCTIONS = (
    "startPlan",
    "reconcile",
    "cancelPendingStart",
    "stopPlan",
    "showComputerWindow",
    "cancelTask",
    "reselectFailed",
    "finishPlanView",
    "saveRetry",
    "fillRetryOptions",
    "renderReview",
    "removeFromReview",
    "openReview",
)
TEST_REL = Path("local/tests/test_phone_ui.py")
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

MUTATIONS: tuple[tuple[str, str, str, str, int, str, str], ...] = (
    # startPlan
    ("M001", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (!canWrite())", "if (!(!canWrite()))"),
    ("M002", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (!items.length)", "if (!(!items.length))"),
    ("M003", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (model.pending && PhoneModel.startPending(model.pending, Date.now()))",
     "if (!(model.pending && PhoneModel.startPending(model.pending, Date.now())))"),
    ("M004", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (model.pending && !model.pending.done)",
     "if (!(model.pending && !model.pending.done))"),
    ("M005", "甲", "local/ui/m/ui-plan.js", "startPlan", 1,
     "model.pending = { request_id: requestId, at: Date.now(), done: false };", "void 0;"),
    ("M006", "甲", "local/ui/m/ui-plan.js", "startPlan", 1,
     'model.notice = "";', "void 0;"),
    ("M007", "甲", "local/ui/m/ui-plan.js", "startPlan", 1,
     "model.listOpen = false;", "void 0;"),
    ("M008", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     'action: "start_plan",', "action: undefined,"),
    ("M009", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "args: {\n"
     "    items, headed: false,\n"
     "    retry_policy: { retry_for_s: Number(model.retry.retry_for_s),\n"
     "                    max_attempts: Number(model.retry.max_attempts || 0) },\n"
     "    request_id: requestId }",
     "args: undefined"),
    ("M010", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "items, headed: false,", "items: undefined, headed: false,"),
    ("M011", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "headed: false,", "headed: undefined,"),
    ("M012", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "retry_policy: { retry_for_s: Number(model.retry.retry_for_s),\n"
     "                    max_attempts: Number(model.retry.max_attempts || 0) },",
     "retry_policy: undefined,"),
    ("M013", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "retry_for_s: Number(model.retry.retry_for_s),", "retry_for_s: undefined,"),
    ("M014", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "max_attempts: Number(model.retry.max_attempts || 0)", "max_attempts: undefined"),
    ("M015", "丁", "local/ui/m/ui-plan.js", "startPlan", 1,
     "request_id: requestId } });", "request_id: undefined } });"),
    ("M016", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (status === 401)", "if (!(status === 401))"),
    ("M017", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "if (body && body.ok && !body.pending)", "if (!(body && body.ok && !body.pending))"),
    ("M018", "甲", "local/ui/m/ui-plan.js", "startPlan", 1,
     "model.pending.done = true;", "void 0;"),
    ("M019", "甲", "local/ui/m/ui-plan.js", "startPlan", 1,
     'model.pending.outcome = "accepted";', "void 0;"),
    ("M020", "乙", "local/ui/m/ui-plan.js", "startPlan", 1,
     "else if (body && body.error)", "else if (!(body && body.error))"),
    # reconcile
    ("M021", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     "if (model.reconciling)", "if (!(model.reconciling))"),
    ("M022", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     "if (!requestId)", "if (!(!requestId))"),
    ("M023", "甲", "local/ui/m/ui-plan.js", "reconcile", 1,
     "model.reconciling = true;", "void 0;"),
    ("M024", "丁", "local/ui/m/ui-plan.js", "reconcile", 1,
     'action: "start_request_state",', "action: undefined,"),
    ("M025", "丁", "local/ui/m/ui-plan.js", "reconcile", 1,
     "args: { request_id: requestId }", "args: undefined"),
    ("M026", "丁", "local/ui/m/ui-plan.js", "reconcile", 1,
     "request_id: requestId", "request_id: undefined"),
    ("M027", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     "if (model.pending !== pending || pending.request_id !== requestId || pending.done || pending.canceling)",
     "if (!(model.pending !== pending || pending.request_id !== requestId || pending.done || pending.canceling))"),
    ("M028", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     'if (body && (body.state === "accepted" || body.state === "rejected"\n               || body.state === "canceled"))',
     'if (!(body && (body.state === "accepted" || body.state === "rejected"\n               || body.state === "canceled")))'),
    ("M029", "甲", "local/ui/m/ui-plan.js", "reconcile", 1,
     "pending.done = true;", "void 0;"),
    ("M030", "甲", "local/ui/m/ui-plan.js", "reconcile", 1,
     "pending.outcome = body.state;", "void 0;"),
    ("M031", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     'if (body.state === "accepted")', 'if (!(body.state === "accepted"))'),
    ("M032", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     'body.state === "canceled"\n      ?', '!(body.state === "canceled")\n      ?'),
    ("M033", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     'body.state === "canceled" ? "info"', '!(body.state === "canceled") ? "info"'),
    ("M034", "乙", "local/ui/m/ui-plan.js", "reconcile", 1,
     'if (body && body.state === "unknown")', 'if (!(body && body.state === "unknown"))'),
    ("M035", "甲", "local/ui/m/ui-plan.js", "reconcile", 1,
     "model.reconciling = false;", "void 0;"),
    # cancelPendingStart
    ("M036", "乙", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "if (!model.pending || model.pending.done || model.cancelingStart)",
     "if (!(!model.pending || model.pending.done || model.cancelingStart))"),
    ("M037", "戊", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "if (!model.pending || model.pending.done || model.cancelingStart) return false;",
     "if (!model.pending || model.pending.done || model.cancelingStart) return true;"),
    ("M038", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "pending.canceling = true;", "void 0;"),
    ("M039", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "model.cancelingStart = true;", "void 0;"),
    ("M040", "丁", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     'action:"cancel_start_request",', "action:undefined,"),
    ("M041", "丁", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "args:{request_id:pending.request_id}", "args:undefined"),
    ("M042", "丁", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "request_id:pending.request_id", "request_id:undefined"),
    ("M043", "乙", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     'if (body && body.ok && body.state === "canceled")',
     'if (!(body && body.ok && body.state === "canceled"))'),
    ("M044", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "pending.done = true;", "void 0;"),
    ("M045", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     'pending.outcome = "canceled";', "void 0;"),
    ("M046", "戊", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     '|| "取消结果尚未确认，请刷新核对"));\n      return false;',
     '|| "取消结果尚未确认，请刷新核对"));\n      return true;'),
    ("M047", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "pending.canceling = false;", "void 0;"),
    ("M048", "甲", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "model.cancelingStart = false;", "void 0;"),
    ("M049", "乙", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "if (model.paired)", "if (!(model.paired))"),
    ("M050", "戊", "local/ui/m/ui-plan.js", "cancelPendingStart", 1,
     "  return true;\n}", "  return false;\n}"),
    # stopPlan
    ("M051", "乙", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "if (!planId)", "if (!(!planId))"),
    ("M052", "戊", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "if (!planId) return false;", "if (!planId) return true;"),
    ("M053", "丁", "local/ui/m/ui-plan.js", "stopPlan", 1,
     'action: "stop_plan",', "action: undefined,"),
    ("M054", "丁", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "args: { plan_id: planId }", "args: undefined"),
    ("M055", "丁", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "plan_id: planId", "plan_id: undefined"),
    ("M056", "乙", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "if (body && body.error)", "if (!(body && body.error))"),
    ("M057", "戊", "local/ui/m/ui-plan.js", "stopPlan", 1,
     'showSheetError("没能停止计划：" + String(body.text || body.error));\n    return false;',
     'showSheetError("没能停止计划：" + String(body.text || body.error));\n    return true;'),
    ("M058", "戊", "local/ui/m/ui-plan.js", "stopPlan", 1,
     "  return true;\n}", "  return false;\n}"),
    # showComputerWindow
    ("M059", "丁", "local/ui/m/ui-plan.js", "showComputerWindow", 1,
     'action: "show_window",', "action: undefined,"),
    ("M060", "丁", "local/ui/m/ui-plan.js", "showComputerWindow", 1,
     "args: {}", "args: undefined"),
    ("M061", "乙", "local/ui/m/ui-plan.js", "showComputerWindow", 1,
     "if (status !== 200 || (body && body.ok === false))",
     "if (!(status !== 200 || (body && body.ok === false)))"),
    # cancelTask
    ("M062", "乙", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "if (!planId || !task)", "if (!(!planId || !task))"),
    ("M063", "戊", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "if (!planId || !task) return false;", "if (!planId || !task) return true;"),
    ("M064", "丁", "local/ui/m/ui-plan.js", "cancelTask", 1,
     'action: "cancel_task",', "action: undefined,"),
    ("M065", "丁", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "args: { plan_id: planId, task_id: task.task_id }", "args: undefined"),
    ("M066", "丁", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "plan_id: planId,", "plan_id: undefined,"),
    ("M067", "丁", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "task_id: task.task_id", "task_id: undefined"),
    ("M068", "乙", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "if (body && body.error)", "if (!(body && body.error))"),
    ("M069", "戊", "local/ui/m/ui-plan.js", "cancelTask", 1,
     'showSheetError("没能取消这一场：" + String(body.text || body.error));\n    return false;',
     'showSheetError("没能取消这一场：" + String(body.text || body.error));\n    return true;'),
    ("M070", "戊", "local/ui/m/ui-plan.js", "cancelTask", 1,
     "  return true;\n}", "  return false;\n}"),
    # reselectFailed
    ("M071", "甲", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     'model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");', "void 0;"),
    ("M072", "甲", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     "model.plan = null;", "void 0;"),
    ("M073", "乙", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     'if (st !== "failed" && st !== "canceled")',
     'if (!(st !== "failed" && st !== "canceled"))'),
    ("M074", "乙", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     "if (item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model)))",
     "if (!(item && PhoneModel.actionable(item, model.items, PhoneModel.businessNowS(model))))"),
    ("M075", "甲", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     "model.selected = picked;", "void 0;"),
    ("M076", "甲", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     "model.listOpen = false;", "void 0;"),
    ("M077", "甲", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     'model.notice = "";', "void 0;"),
    ("M078", "乙", "local/ui/m/ui-plan.js", "reselectFailed", 1,
     "if (skipped > 0)", "if (!(skipped > 0))"),
    # finishPlanView
    ("M079", "甲", "local/ui/m/ui-plan.js", "finishPlanView", 1,
     'model.dismissedPlanId = String((model.plan && model.plan.plan_id) || "");', "void 0;"),
    ("M080", "甲", "local/ui/m/ui-plan.js", "finishPlanView", 1,
     "model.plan = null;", "void 0;"),
    ("M081", "甲", "local/ui/m/ui-plan.js", "finishPlanView", 1,
     "model.selected = [];", "void 0;"),
    ("M082", "甲", "local/ui/m/ui-plan.js", "finishPlanView", 1,
     "model.listOpen = false;", "void 0;"),
    ("M083", "甲", "local/ui/m/ui-plan.js", "finishPlanView", 1,
     'model.notice = "";', "void 0;"),
    # saveRetry
    ("M084", "丁", "local/ui/m/ui-plan.js", "saveRetry", 1,
     'action: "save_retry_policy",', "action: undefined,"),
    ("M085", "丁", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "args: {\n"
     "    retry_policy: {\n"
     "      retry_for_s: Number(model.retry.retry_for_s),\n"
     "      max_attempts: Number(model.retry.max_attempts || 0) } }",
     "args: undefined"),
    ("M086", "丁", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "retry_policy: {\n"
     "      retry_for_s: Number(model.retry.retry_for_s),\n"
     "      max_attempts: Number(model.retry.max_attempts || 0) }",
     "retry_policy: undefined"),
    ("M087", "丁", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "retry_for_s: Number(model.retry.retry_for_s),", "retry_for_s: undefined,"),
    ("M088", "丁", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "max_attempts: Number(model.retry.max_attempts || 0)", "max_attempts: undefined"),
    ("M089", "乙", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "if (body && body.error)", "if (!(body && body.error))"),
    ("M090", "甲", "local/ui/m/ui-plan.js", "saveRetry", 1,
     "model.retryDirty = false;", "void 0;"),
    # renderReview
    ("M091", "乙", "local/ui/m/ui-plan.js", "renderReview", 1,
     "if (tk.act)", "if (!(tk.act))"),
    ("M092", "丙", "local/ui/m/ui-plan.js", "renderReview", 1,
     '$("review-warns").hidden = !warns.length;', "void 0;"),
    ("M093", "乙", "local/ui/m/ui-plan.js", "renderReview", 1,
     "warns.length ?", "!(warns.length) ?"),
    # removeFromReview
    ("M094", "甲", "local/ui/m/ui-plan.js", "removeFromReview", 1,
     "model.selected = res.selected;", "void 0;"),
    ("M095", "甲", "local/ui/m/ui-plan.js", "removeFromReview", 1,
     'model.notice = "";', "void 0;"),
    ("M096", "乙", "local/ui/m/ui-plan.js", "removeFromReview", 1,
     "if (!model.selected.length)", "if (!(!model.selected.length))"),
    # openReview
    ("M097", "乙", "local/ui/m/ui-plan.js", "openReview", 1,
     'if ($("btn-start").disabled)', 'if (!($("btn-start").disabled))'),
)


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for k in PROXY_VARS:
        env.pop(k, None)
    return env


def func_ranges() -> dict[tuple[str, str], tuple[int, int]]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    code = (
        'import { readFileSync } from "node:fs";\n'
        'import { pathToFileURL } from "node:url";\n'
        'const [scan, ...files] = process.argv.slice(2);\n'
        'const { findFunctions } = await import(pathToFileURL(scan).href);\n'
        'const out = {};\n'
        'for (const fpath of files) {\n'
        '  const { funcs } = findFunctions(readFileSync(fpath, "utf8"));\n'
        '  const m = {};\n'
        '  for (const f of funcs) if (f.depth === 0 && f.kind === "function" && f.name) m[f.name] = [f.start, f.end];\n'
        '  out[fpath] = m;\n'
        '}\n'
        'process.stdout.write(JSON.stringify(out));\n'
    )
    abs_files = [str(REPO / rel) for rel in TARGET_FILES]
    res = subprocess.run(
        [node, "--input-type=module", "-", str(JSSCAN_MJS), *abs_files],
        input=code, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    raw = json.loads(res.stdout)
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for rel, abs_path in zip(TARGET_FILES, abs_files):
        for fn, rng in raw.get(abs_path, {}).items():
            out[(rel, fn)] = (int(rng[0]), int(rng[1]))
    return out


def test_behavior_map() -> dict[str, bool]:
    tree = ast.parse((REPO / TEST_REL).read_text(encoding="utf-8"))
    out: dict[str, bool] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        helpers: dict[str, ast.FunctionDef] = {
            item.name: item
            for item in node.body
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("test_")
        }
        behav_helpers: set[str] = {
            name for name, item in helpers.items()
            if any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "run_phone_js"
                for c in ast.walk(item)
            )
        }
        changed = True
        while changed:
            changed = False
            for name, item in helpers.items():
                if name in behav_helpers:
                    continue
                if any(
                    isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == "self"
                    and c.func.attr in behav_helpers
                    for c in ast.walk(item)
                ):
                    behav_helpers.add(name)
                    changed = True
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                uses_node = any(
                    isinstance(c, ast.Call) and (
                        (isinstance(c.func, ast.Name) and c.func.id == "run_phone_js")
                        or (isinstance(c.func, ast.Attribute)
                            and isinstance(c.func.value, ast.Name)
                            and c.func.value.id == "self"
                            and c.func.attr in behav_helpers)
                    )
                    for c in ast.walk(item)
                )
                out[f"{node.name}.{item.name}"] = uses_node
    return out


def apply_in_func(text: str, start: int, end: int, locate: str, repl: str) -> str | None:
    lines = text.splitlines(keepends=False)
    head = "\n".join(lines[:start - 1])
    body = "\n".join(lines[start - 1:end])
    tail = "\n".join(lines[end:])
    if locate.startswith("^"):
        pat = re.compile(locate, re.M)
        hits = list(pat.finditer(body))
        if len(hits) != 1:
            return None
        new_body = pat.sub(lambda _m: repl, body, count=1)
    else:
        if body.count(locate) != 1:
            return None
        new_body = body.replace(locate, repl, 1)
    parts = [p for p in (head, new_body, tail) if p]
    return "\n".join(parts) + ("\n" if text.endswith("\n") else "")


def create_archive_zip(zip_path: Path) -> None:
    subprocess.run(
        ["git", "archive", "--format=zip", "--output", str(zip_path), "HEAD"],
        cwd=REPO, check=True, capture_output=True,
    )


def open_replica(zip_path: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="phone_plan_mut_"))
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(root)
    dst_test = root / TEST_REL
    dst_test.parent.mkdir(parents=True, exist_ok=True)
    dst_test.write_bytes((REPO / TEST_REL).read_bytes())
    return root


def _parse_running_test(out_text: str) -> list[str]:
    m = re.findall(r"^([A-Za-z0-9_]+)\s+\(([^)]+)\)\s+\.\.\.", out_text, flags=re.M)
    if not m:
        return []
    meth, qual = m[-1]
    parts = qual.split(".")
    cls = parts[-2] if len(parts) >= 2 else ""
    return [f"{cls}.{meth}" if cls else meth]


def run_unittest(root: Path) -> tuple[int, list[str], int]:
    try:
        res = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", "test_phone_ui.py", "-v"],
            cwd=root, env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        out_text = (exc.stdout or b"" if isinstance(exc.stdout, bytes) else exc.stdout or "")
        err_text = (exc.stderr or b"" if isinstance(exc.stderr, bytes) else exc.stderr or "")
        if isinstance(out_text, bytes):
            out_text = out_text.decode("utf-8", "replace")
        if isinstance(err_text, bytes):
            err_text = err_text.decode("utf-8", "replace")
        return 124, _parse_running_test(out_text + "\n" + err_text), 0
    out_text = (res.stdout or "") + "\n" + (res.stderr or "")
    fails = re.findall(r"^(?:FAIL|ERROR):\s+([A-Za-z0-9_]+)\s+\(([^)]+)\)", out_text, flags=re.M)
    names = []
    for meth, qual in fails:
        parts = qual.split(".")
        cls = parts[-2] if len(parts) >= 2 else ""
        names.append(f"{cls}.{meth}" if cls else meth)
    skipped = 0
    m = re.search(r"skipped=(\d+)", out_text)
    if m:
        skipped = int(m.group(1))
    return res.returncode, names, skipped


def run_one_in_replica(
    root: Path, orig_texts: dict[str, str], ranges: dict[tuple[str, str], tuple[int, int]],
    bmap: dict[str, bool], mut: tuple,
) -> dict:
    mid, kind, rel, fn, occur, locate, repl = mut
    target = root / rel
    orig_lf = orig_texts[rel]
    rng = ranges.get((rel, fn))
    if not rng:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "未找到目标函数", "timeout": False}
    mutated = apply_in_func(orig_lf, rng[0], rng[1], locate, repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "定位不唯一或未命中", "timeout": False}
    target.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        node = shutil.which("node")
        chk = subprocess.run([node, "--check", str(target)], capture_output=True, text=True, check=False)
        if chk.returncode != 0:
            return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                    "replace": repl, "status": "无效", "first_fail": "", "note": "node --check 失败", "timeout": False}
        code, fails, _ = run_unittest(root)
    finally:
        target.write_text(orig_lf, encoding="utf-8", newline="\n")
    if code == 0:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无人守", "first_fail": "", "note": "", "timeout": False}
    if code == 124:
        first = fails[0] if fails else "(timeout)"
        behav = [f for f in fails if bmap.get(f, False)]
        status = "行为守" if (behav or not fails) else "字面守"
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": status, "first_fail": f"{first}（超时）", "note": "超时", "timeout": True}
    if not fails:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "字面守", "first_fail": "(unknown)", "note": "非零退出但未解析出用例名", "timeout": False}
    behav = [f for f in fails if bmap.get(f, False)]
    status = "行为守" if behav else "字面守"
    return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
            "replace": repl, "status": status, "first_fail": fails[0], "note": "", "timeout": False}


def worker_chunk(
    zip_path: Path, orig_texts: dict[str, str], ranges: dict[tuple[str, str], tuple[int, int]],
    bmap: dict[str, bool], chunk: list[tuple],
) -> list[dict]:
    root = open_replica(zip_path)
    results = []
    try:
        for mut in chunk:
            results.append(run_one_in_replica(root, orig_texts, ranges, bmap, mut))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return results


def list_mutations(ranges: dict[tuple[str, str], tuple[int, int]], orig_texts: dict[str, str]) -> int:
    bad = 0
    for mid, kind, rel, fn, occur, locate, repl in MUTATIONS:
        rng = ranges.get((rel, fn))
        ok = bool(rng and apply_in_func(orig_texts[rel], rng[0], rng[1], locate, repl) is not None)
        if not ok:
            bad += 1
        loc_one = locate.replace("\n", "\\n")
        rep_one = repl.replace("\n", "\\n")
        print(f"{mid}\t{kind}\t{Path(rel).name}:{fn}\t#{occur}\t{'OK' if ok else 'MISS'}\t{loc_one} => {rep_one}")
    print(f"Total: {len(MUTATIONS)} (locate miss: {bad})")
    return 1 if bad else 0


def format_report(results: list[dict], phase: str, equiv: dict) -> str:
    cats = ("行为守", "字面守", "无人守", "无效", "等价")
    kinds = ("甲", "乙", "丙", "丁", "戊")
    counts = {k: 0 for k in cats}
    by_kind = {knd: {k: 0 for k in cats} for knd in kinds}
    by_func = {fn: {"kinds": {knd: 0 for knd in kinds}, "cats": {k: 0 for k in cats}, "total": 0} for fn in ALL_FUNCTIONS}
    lines = [
        f"# 第三组（计划操作）变异结论（{phase}）",
        "",
        (
            f"- 范围：`local/ui/m/ui-plan.js` 的 13 个顶层函数（`fillRetryOptions` 不含五类节点，其余 12 个函数共 {len(results)} 条）："
            f"甲类（模型及 `pending` 字段写换 `void 0`）{sum(1 for r in results if r['kind']=='甲')} 条、"
            f"乙类（条件 `C` 换 `!(C)`）{sum(1 for r in results if r['kind']=='乙')} 条、"
            f"丙类（`.hidden = X` 写换 `void 0`）{sum(1 for r in results if r['kind']=='丙')} 条、"
            f"丁类（`postAction` 载荷属性换 `undefined`）{sum(1 for r in results if r['kind']=='丁')} 条、"
            f"戊类（`return true`/`false` 互换）{sum(1 for r in results if r['kind']=='戊')} 条。"
        ),
        "",
        "| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    equiv_notes = []
    for r in results:
        st = r["status"]
        if st == "无人守" and r["id"] in equiv:
            st = "等价"
            info = equiv[r["id"]]
            reason = info.get("reason", "") if isinstance(info, dict) else str(info)
            callers = info.get("callers", "") if isinstance(info, dict) else ""
            equiv_notes.append((r["id"], r["file"], r["func"], reason, callers))
        counts[st] = counts.get(st, 0) + 1
        by_kind[r["kind"]][st] = by_kind[r["kind"]].get(st, 0) + 1
        fn_stat = by_func[r["func"]]
        fn_stat["total"] += 1
        fn_stat["kinds"][r["kind"]] += 1
        fn_stat["cats"][st] += 1
        loc = r["locate"].replace("\n", " ↵ ").replace("|", "\\|")
        rep = r["replace"].replace("\n", " ↵ ").replace("|", "\\|")
        ff = f"`{r['first_fail']}`" if r["first_fail"] else "—"
        f_short = Path(r["file"]).name
        lines.append(f"| {r['id']} | {r['kind']} | `{f_short}` | `{r['func']}` | `{loc}` | `{rep}` | {st} | {ff} |")
    lines.extend(["", "## 各类合计", ""])
    for k in cats:
        lines.append(f"- {k}：{counts[k]}")
    lines.append(f"- 总计：{len(results)}")
    lines.extend([
        "",
        "## 按变异口径统计",
        "",
        "| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    kind_labels = {
        "甲": "甲类（模型及 `pending` 字段写换 `void 0`）",
        "乙": "乙类（条件 `C` 换 `!(C)`）",
        "丙": "丙类（`.hidden = X` 写换 `void 0`）",
        "丁": "丁类（`postAction` 载荷属性换 `undefined`）",
        "戊": "戊类（`return true`/`false` 互换）",
    }
    for knd in kinds:
        row_c = by_kind[knd]
        sub_total = sum(row_c.values())
        lines.append(
            f"| {kind_labels[knd]} | {row_c['行为守']} | {row_c['字面守']} | {row_c['无人守']} | "
            f"{row_c['无效']} | {row_c['等价']} | {sub_total} |"
        )
    lines.extend([
        "",
        "## 按函数统计",
        "",
        "| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for fn in ALL_FUNCTIONS:
        fs = by_func[fn]
        ks = " / ".join(str(fs["kinds"][knd]) for knd in kinds)
        cs = fs["cats"]
        lines.append(
            f"| `{fn}` | {ks} | {cs['行为守']} | {cs['字面守']} | {cs['无人守']} | "
            f"{cs['无效']} | {cs['等价']} | {fs['total']} |"
        )
    if equiv_notes:
        lines.extend(["", "## 等价判定理由与调用方证明", ""])
        for mid, rel, fn, reason, callers in equiv_notes:
            tail = f" 调用方证明：{callers}" if callers else ""
            lines.append(f"- **{mid}**（`{Path(rel).name}:{fn}`）：{reason}{tail}")
    return "\n".join(lines) + "\n"


def run_parallel(selected: list[tuple], workers: int) -> list[dict]:
    orig_texts = {
        rel: (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        for rel in TARGET_FILES
    }
    ranges = func_ranges()
    bmap = test_behavior_map()
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_plan_zip_"))
    zip_path = tmp_zip_dir / "repo.zip"
    try:
        create_archive_zip(zip_path)
        w = max(1, min(4, workers, len(selected)))
        chunks = [selected[i::w] for i in range(w)]
        merged = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(worker_chunk, zip_path, orig_texts, ranges, bmap, ch) for ch in chunks if ch]
            for fut in concurrent.futures.as_completed(futs):
                merged.extend(fut.result())
        order = {m[0]: idx for idx, m in enumerate(MUTATIONS)}
        merged.sort(key=lambda r: order[r["id"]])
        return merged
    finally:
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def run_baseline() -> int:
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_plan_base_"))
    zip_path = tmp_zip_dir / "repo.zip"
    root = None
    try:
        create_archive_zip(zip_path)
        root = open_replica(zip_path)
        code, fails, skipped = run_unittest(root)
        print(f"Baseline: exit={code}, fails={len(fails)}, skipped={skipped}")
        return 0 if (code == 0 and skipped == 0) else 1
    finally:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="手机页第三组变异测试")
    ap.add_argument("--list", action="store_true", help="只列清单并核对定位")
    ap.add_argument("--baseline", action="store_true", help="跑未变异副本基线")
    ap.add_argument("--ids", default="", help="只跑指定编号（逗号分隔）")
    ap.add_argument("--workers", type=int, default=4, help="并行副本数（最大 4）")
    ap.add_argument("--phase", default="补测之前", help="报告阶段标题")
    ap.add_argument("--equiv-json", default="", help="等价判定 JSON 文件路径")
    ap.add_argument("--out", default="", help="输出 Markdown 路径")
    args = ap.parse_args(argv)
    orig_texts = {
        rel: (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        for rel in TARGET_FILES
    }
    if args.list:
        return list_mutations(func_ranges(), orig_texts)
    if args.baseline:
        return run_baseline()
    wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
    selected = [m for m in MUTATIONS if not wanted or m[0] in wanted]
    if not selected:
        print("没有匹配的编号", file=sys.stderr)
        return 1
    equiv = json.loads(Path(args.equiv_json).read_text(encoding="utf-8")) if args.equiv_json else {}
    results = run_parallel(selected, args.workers)
    md = format_report(results, args.phase, equiv)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8", newline="\n")
        print(f"Wrote {args.out} ({len(results)} mutations)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
