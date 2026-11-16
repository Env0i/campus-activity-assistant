#!/usr/bin/env python3
"""在临时副本中逐条变异登录新转移和后端状态接线。"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "design/evidence/2026-11-16/login-machine/scripts"))
from capsule_grid import copy_current  # noqa: E402

TRANSITION_TARGETS = (
    "local/ui/features/login/actions.js",
    "local/ui/features/login/actions-relogin.js",
    "local/ui/views/plan-panel.js",
    "local/ui/app.js",
    "local/ui/legacy-globals.js",
)


def m(mid, path, scope, needle, replacement, pattern):
    return {"id": mid, "path": path, "scope": scope, "needle": needle,
            "replacement": replacement, "pattern": pattern}


MUTATIONS = [
    m("auto-invalid-idle", "local/ui/features/login/actions.js", "function applyAutoState",
      'const state = AUTO_STATES.indexOf(fields.auto_state) >= 0 ? fields.auto_state : "idle";',
      'const state = fields.auto_state;', "invalid_state"),
    m("auto-noop-missing", "local/ui/features/login/actions.js", "function applyAutoState",
      'if (!fields || typeof fields.auto_state !== "string") return false;',
      'if (!fields) return false;', "valid_without_auto"),
    m("auto-mirror-running", "local/ui/features/login/actions.js", "function applyAutoState",
      'S.autoLogin = state === "running";', 'S.autoLogin = true;', "backend_auto_state"),
    m("auto-no-redraw", "local/ui/features/login/actions.js", "function receiveAutoState",
      'syncLoginDependentView();', 'return true;', "backend_auto_state"),
    m("setlogin-no-valid-retract", "local/ui/features/login/actions.js", "function setLogin",
      'applyAutoState({ auto_state: "idle" });', 'applyAutoState({ auto_state: "running" });', "valid_without_auto"),
    m("phase-recheck-ok", "local/ui/features/login/state-machine.js", "function loginPhase",
      'data.checking && data.ok === true && data.present === true && data.result === "valid"',
      'data.checking && data.present === true && data.result === "valid"', "rechecking"),
    m("phase-needs-handoff", "local/ui/features/login/state-machine.js", "function loginPhase",
      'auto.state === "handoff"', 'false', "backend_auto_state"),
    m("phase-needs-ocr", "local/ui/features/login/state-machine.js", "function loginPhase",
      'auto.state === "blocked" && auto.block === "ocr_missing"', 'false', "blocked_ocr"),
    m("phase-retry-positive", "local/ui/features/login/state-machine.js", "function loginPhase",
      'auto.state === "backoff" && auto.retryLeftS > 0',
      'auto.state === "backoff" && auto.retryLeftS >= 0', "invalid_state"),
    m("view-state-rechecking", "local/ui/features/login/state-machine.js", "function loginViewState",
      'rechecking: "checking"', 'rechecking: "bad"', "rechecking"),
    m("view-state-needs-code", "local/ui/features/login/state-machine.js", "function loginViewState",
      'needs_code: "bad"', 'needs_code: "checking"', "backend_auto_state"),
    m("view-state-retry-later", "local/ui/features/login/state-machine.js", "function loginViewState",
      'retry_later: "bad"', 'retry_later: "checking"', "backoff"),
    m("retry-no-elapsed", "local/ui/features/login/view.js", "function retryLeftS",
      'const elapsed = Math.max(0, Math.floor((performance.now() - Number(auto.at || 0)) / 1000));',
      'const elapsed = 0;', "blocked_ocr"),
    m("retry-floor-minutes", "local/ui/features/login/view.js", "function retryMinutes",
      'Math.ceil(Number(auto.retryLeftS || 0) / 60)', 'Math.floor(Number(auto.retryLeftS || 0) / 60)', "retry_minutes"),
    m("appearance-rechecking-text", "local/ui/features/login/view.js", "rechecking: {",
      'text: () => "已登录"', 'text: () => "登录已失效"', "rechecking"),
    m("appearance-rechecking-sub", "local/ui/features/login/view.js", "rechecking: {",
      'sub: () => "正在确认"', 'sub: () => ""', "rechecking"),
    m("appearance-needs-code-text", "local/ui/features/login/view.js", "needs_code: {",
      'text: () => "要你输验证码"', 'text: () => "登录已失效"', "backend_auto_state"),
    m("appearance-needs-code-note", "local/ui/features/login/view.js", "needs_code: {",
      '"电脑这边认不了验证码，输入验证码就能重新登录"', '"登录已失效"', "blocked_ocr"),
    m("appearance-retry-text", "local/ui/features/login/view.js", "retry_later: {",
      'text: () => "登录已失效"', 'text: () => "自动登录中…"', "backoff"),
    m("appearance-retry-sub", "local/ui/features/login/view.js", "retry_later: {",
      'retryMinutes(facts.auto) + " 分钟后再试"', '""', "backoff"),
    m("appearance-retry-note", "local/ui/features/login/view.js", "retry_later: {",
      '" 分钟后会再试；也可以现在重新登录"', '""', "backoff"),
    m("banner-unknown", "local/ui/features/login/view.js", "function loginBannerHtml",
      'if (data.state === "unknown")', 'if (false)', "backend_auto_state"),
    m("banner-needs-code", "local/ui/features/login/view.js", "function loginBannerHtml",
      'if (data.phase === "needs_code")', 'if (false)', "backend_auto_state"),
    m("banner-bad", "local/ui/features/login/view.js", "function loginBannerHtml",
      'if (data.state === "bad")', 'if (false)', "backoff"),
    m("app-login-auto-event", "local/ui/app.js", "window.onBackend",
      'login_auto: (payload) => receiveAutoState(payload),', 'login_auto: (payload) => {},', "backend_auto_state"),
    m("legacy-auto-mount", "local/ui/legacy-globals.js", "function installLegacyGlobals",
      'window.receiveAutoState = receiveAutoState;', 'window.receiveAutoState = () => {};', "backend_auto_state"),
    m("switch-no-wait", "local/ui/features/login/actions-relogin.js", "async function reloginSwitchToBrowser",
      'reloginStep("wait", "正在切换…");', 'reloginStep("login");', "switch_to_browser"),
    m("switch-no-cancel", "local/ui/features/login/actions-relogin.js", "async function reloginSwitchToBrowser",
      'await api("relogin_cancel", flowId);', 'await Promise.resolve();', "switch_to_browser"),
    m("switch-duplicate-cancel", "local/ui/features/login/actions-relogin.js", "async function reloginSwitchToBrowser",
      'if (S.relogin) S.relogin.flowId = "";', 'if (S.relogin) S.relogin.flowId = flowId;', "switch_to_browser"),
    m("plan-banner-call", "local/ui/views/plan-panel.js", "function paintBanners",
      'parts.push(...[loginBannerHtml(S.login.view || {}, S.busy)].filter(Boolean));', 'void 0;',
      "backend_auto_state"),
    m("phase-blocked-any-reason", "local/ui/features/login/state-machine.js", "function loginPhase",
      'auto.state === "blocked" && auto.block === "ocr_missing"', 'auto.state === "blocked"',
      "blocked_other_reasons"),
    m("switch-text-changed", "local/ui/features/login/actions-relogin.js", "async function reloginSwitchToBrowser",
      'reloginStep("wait", "正在切换…");', 'reloginStep("wait", "正在登录…");', "switch_to_browser"),
    m("switch-close-before-cancel-returns", "local/ui/features/login/actions-relogin.js",
      "async function reloginSwitchToBrowser",
      'await api("relogin_cancel", flowId);', 'void api("relogin_cancel", flowId).catch(() => {});',
      "switch_to_browser"),
    m("demo-no-retract", "local/ui/features/login/actions.js", "function setLogin",
      '} else if (S.login.result === "valid" || S.demo) {', '} else if (S.login.result === "valid") {',
      "demo_retract"),
]

# 等价变异：改了也不该有用户可见差别，单独跑、不计入结论条数，期望不红。
EQUIVALENT = [
    # 只有剩余秒数大于 0 才进稍后重试（loginPhase），剩余秒数是整数，向上取整后本来就至少为 1。
    m("retry-minutes-no-floor-of-one", "local/ui/features/login/view.js", "function retryMinutes",
      'Math.max(1, Math.ceil(Number(auto.retryLeftS || 0) / 60))',
      'Math.ceil(Number(auto.retryLeftS || 0) / 60)', "retry_minutes"),
    # receiveAutoState 先走 syncLoginDependentView，其中的 render 已经重画横幅。
    m("receive-no-explicit-banner", "local/ui/features/login/actions.js", "function receiveAutoState",
      'paintBanners();', '', "backend_auto_state"),
]


def apply_mutation(root: Path, item: dict) -> None:
    path = root / item["path"]
    text = path.read_text(encoding="utf-8")
    start = text.find(item["scope"])
    if start < 0:
        raise AssertionError(f"scope not found: {item['path']}::{item['scope']}")
    pos = text.find(item["needle"], start)
    if pos < 0:
        raise AssertionError(f"line not found: {item['path']}::{item['scope']}")
    path.write_text(text[:pos] + item["replacement"]
                    + text[pos + len(item["needle"]):], encoding="utf-8", newline="")


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="login-transition-mutation-"))
    copy_current(root)
    for name in TRANSITION_TARGETS:
        source = ROOT / name; target = root / name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    for name in ("local/tests/test_login_transitions.py", "local/tests/test_login_machine.py"):
        source = ROOT / name; target = root / name
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
    return root


def run_test(root: Path, pattern: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
                           "-p", "test_login_transitions.py"],
                          cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    output = proc.stdout + proc.stderr
    match = re.search(r"(?:FAIL|ERROR): ([^\r\n]+)", output)
    return proc.returncode, match.group(1) if match else "no failure detail"


def run_one(item: dict) -> tuple[int, str]:
    root = make_copy()
    try:
        apply_mutation(root, item)
        return run_test(root, item["pattern"])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    green = []
    for item in MUTATIONS:
        code, failure = run_one(item)
        print(f"{item['id']}\t{'red' if code else 'green'}\t{failure}")
        if code == 0: green.append(item["id"])
    red_equivalent = []
    for item in EQUIVALENT:
        code, failure = run_one(item)
        print(f"equivalent:{item['id']}\t{'red' if code else 'green'}\t{failure if code else ''}")
        if code: red_equivalent.append(item["id"])
    if green:
        print("mutations unexpectedly green: " + ", ".join(green))
    if red_equivalent:
        print("equivalent mutations turned red (not equivalent): " + ", ".join(red_equivalent))
    if green or red_equivalent:
        return 1
    print(f"all {len(MUTATIONS)} mutations were detected; {len(EQUIVALENT)} equivalent stayed green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
