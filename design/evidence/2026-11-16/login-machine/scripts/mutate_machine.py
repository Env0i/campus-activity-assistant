#!/usr/bin/env python3
"""在临时副本中逐条变异登录状态机和样子表。"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from capsule_grid import copy_current


ROOT = Path(__file__).resolve().parents[5]
TEST_EXTRA = "local/tests/test_login_machine.py"


def mutation(mutation_id, path, scope, needle, replacement, pattern):
    return {"id": mutation_id, "path": path, "scope": scope, "needle": needle,
            "replacement": replacement, "pattern": pattern}


MUTATIONS = [
    mutation("phase-plan-running", "local/ui/features/login/state-machine.js", "function loginPhase",
             "if (data.busy && !data.loginPending && !busyExpired && !data.autoLogin)",
             "if (false)", "phase_order"),
    mutation("phase-demo", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.demo) phase = \"demo\";", "else if (false) phase = \"demo\";", "phase_order"),
    mutation("phase-auto", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.autoLogin) phase = \"auto\";", "else if (false) phase = \"auto\";", "phase_order"),
    mutation("phase-login", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.loginPending) phase = \"logging_in\";", "else if (false) phase = \"logging_in\";", "phase_order"),
    mutation("phase-checking", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.checking || (data.ok === null && data.present === true)) phase = \"checking\";",
             "else if (false) phase = \"checking\";", "phase_order"),
    mutation("phase-never", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.present === false) phase = \"never\";", "else if (false) phase = \"never\";", "phase_order"),
    mutation("phase-unknown", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.result === \"unknown\" && data.ok === false) phase = \"unknown\";",
             "else if (false) phase = \"unknown\";", "phase_order"),
    mutation("phase-expired", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.ok === false && data.present !== false) phase = \"expired\";",
             "else if (false) phase = \"expired\";", "phase_order"),
    mutation("phase-valid", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else if (data.ok === true) phase = \"valid\";", "else if (false) phase = \"valid\";", "phase_order"),
    mutation("phase-unset", "local/ui/features/login/state-machine.js", "function loginPhase",
             "else phase = \"unset\";", "else phase = \"demo\";", "every_phase_maps"),
    mutation("terms-demo-exception", "local/ui/features/login/state-machine.js", "function loginPhase",
             'phase !== "demo"', 'phase === "demo"', "phase_order"),
    mutation("terms-auto-exception", "local/ui/features/login/state-machine.js", "function loginPhase",
             'phase !== "auto"', 'phase === "auto"', "phase_order"),
    mutation("terms-login-exception", "local/ui/features/login/state-machine.js", "function loginPhase",
             'phase !== "logging_in"', 'phase === "logging_in"', "phase_order"),
]


for phase, expected in {
    "plan_running": ("is-busy", 'text: () => S.login.present === false ? "未登录" : "已登录"',
                     'sub: () => ""', "登录状态保持不变；计划进度见报名区域"),
    "demo": ("is-warn", 'text: () => "演示模式"', 'sub: () => "内存样例"',
             "不读取登录信息、不访问学校，只演示界面与流程"),
    "auto": ("is-busy", 'text: () => "自动登录中…"', 'sub: () => ""',
             "学校说登录失效了，电脑正在用保存的账号自动登录"),
    "logging_in": ("is-busy", 'text: () => "登录中…"', 'sub: () => ""',
                   "请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态"),
    "checking": ("is-busy", 'text: () => "检查登录…"', 'sub: () => ""',
                 "正在检查登录状态，马上就好"),
    "never": ("is-none", 'text: () => "未登录"', 'sub: () => ""',
              "打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录"),
    "unknown": ("is-none", 'text: () => "登录待确认"', 'sub: () => ""',
                "暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录"),
    "expired": ("is-bad", 'text: () => "登录已失效"', 'sub: () => ""',
                "重新登录后可继续使用"),
    "valid": ("is-ok", 'text: () => "已登录"',
              'sub: () => lastCheckText() ? lastCheckText() + " 校验" : ""',
              ': "学校确认登录有效"'),
    "unset": ("", 'text: () => "未登录"', 'sub: () => ""',
              "打开顶栏的登录状态，点「登录」开始使用"),
    "terms": ("is-none", 'text: () => "等同意条款"', 'sub: () => ""',
              "同意使用条款后才会检查登录"),
}.items():
    class_name, text_line, sub_line, note_text = expected
    MUTATIONS.extend([
        mutation(f"appearance-{phase}-class", "local/ui/features/login/view.js", f"{phase}: {{",
                 f'className: "{class_name}"', 'className: "mutated"', "each_phase_keeps"),
        mutation(f"appearance-{phase}-text", "local/ui/features/login/view.js", f"{phase}: {{",
                 text_line, 'text: () => "mutated"', "each_phase_keeps"),
        mutation(f"appearance-{phase}-sub", "local/ui/features/login/view.js", f"{phase}: {{",
                 sub_line, 'sub: () => "mutated"', "each_phase_keeps"),
        mutation(f"appearance-{phase}-note", "local/ui/features/login/view.js", f"{phase}: {{",
                 note_text, "mutated", "each_phase_keeps"),
    ])


for phase, value in {
    "demo": "demo", "auto": "pending", "logging_in": "pending", "checking": "checking",
    "never": "none", "unknown": "unknown", "expired": "bad", "valid": "ok",
    "unset": "none", "terms": "terms",
}.items():
    MUTATIONS.append(mutation(f"view-state-{phase}", "local/ui/features/login/state-machine.js",
                              "function loginViewState", f'{phase}: "{value}"',
                              f'{phase}: "mutated"', "every_phase_maps"))


def replace_after_scope(root: Path, item: dict) -> None:
    path = root / item["path"]
    text = path.read_text(encoding="utf-8")
    scope_at = text.find(item["scope"])
    if scope_at < 0:
        raise AssertionError(f"scope not found: {item['path']}::{item['scope']}")
    position = text.find(item["needle"], scope_at)
    if position < 0:
        raise AssertionError(f"line not found: {item['path']}::{item['scope']}")
    path.write_text(text[:position] + item["replacement"]
                    + text[position + len(item["needle"]):], encoding="utf-8", newline="")


def make_copy() -> Path:
    root = Path(tempfile.mkdtemp(prefix="login-machine-mutation-"))
    copy_current(root)
    source = ROOT / TEST_EXTRA
    target = root / TEST_EXTRA
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return root


def run_test(root: Path, pattern: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
         "-p", "test_login_machine.py", "-k", pattern],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    match = re.search(r"(?:FAIL|ERROR): ([^\r\n]+)", output)
    return result.returncode, match.group(1) if match else "no failure detail"


def main() -> int:
    green = []
    for item in MUTATIONS:
        root = make_copy()
        try:
            replace_after_scope(root, item)
            code, first_failure = run_test(root, item["pattern"])
            status = "red" if code else "green"
            print(f"{item['id']}\t{status}\t{first_failure}")
            if code == 0:
                green.append(item["id"])
        finally:
            shutil.rmtree(root, ignore_errors=True)
    if green:
        print("mutations unexpectedly green: " + ", ".join(green))
        return 1
    print(f"all {len(MUTATIONS)} mutations were detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
