#!/usr/bin/env python3
"""在临时仓库副本中验证登录字段的回归用例能识别关键变异。"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
COPY_EXTRA = ("local/tests/test_auto_login_rules.py",)


MUTATIONS = (
    {
        "id": "manual-priority",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": 'if relay.get("live") and relay.get("origin") != "auto":',
        "replacement": "if False:",
        "test": ("local/tests/test_auto_login_rules.py", "manual_live_flow"),
    },
    {
        "id": "handoff-mode-guard",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": 'and (relay.get("mode") == "manual"',
        "replacement": "and (False",
        "test": ("local/tests/test_auto_login_rules.py", "handoff"),
    },
    {
        "id": "handoff-needs-live",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": 'and (relay.get("mode") == "manual" or relay.get("handoff") or handoff)):',
        "replacement": 'and relay.get("mode") == "manual") or handoff:',
        "test": ("local/tests/test_auto_login_rules.py", "scheduler_handoff_flag_alone_is_backoff"),
    },
    {
        "id": "valid-not-idle",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": "elif not expired:",
        "replacement": "elif False:",
        "test": ("local/tests/test_auto_login_rules.py", "idle_when_session"),
    },
    {
        "id": "blocked-reason",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": 'block = block or ready_reason or "unknown"',
        "replacement": 'block = "wrong"',
        "test": ("local/tests/test_auto_login_rules.py", "blocked_copies"),
    },
    {
        "id": "backoff-zero",
        "path": "local/domain/login_rules.py",
        "function": "def auto_login_state",
        "needle": "failures > 0 and retry_in_s > 0",
        "replacement": "failures > 0 and retry_in_s >= 0",
        "test": ("local/tests/test_auto_login_rules.py", "backoff_needs"),
    },
    {
        "id": "countdown-fixed",
        "path": "local/application/auto_relogin.py",
        "function": "def view",
        "needle": "retry_in_s = max(0, int(self._retry_at - self._now()))",
        "replacement": "retry_in_s = max(0, int(self._retry_at))",
        "test": ("local/tests/test_auto_relogin.py", "view_reports_backoff"),
    },
    {
        "id": "expired-override",
        "path": "local/application/auto_relogin.py",
        "function": "def view",
        "needle": "expired = state_expired if expired is None else bool(expired)",
        "replacement": "expired = state_expired",
        "test": ("local/tests/test_auto_relogin.py", "expired_argument"),
    },
    {
        "id": "ready-on-valid",
        "path": "local/application/auto_relogin.py",
        "function": "def view",
        "needle": "if expired and self._ready is not None:",
        "replacement": "if False and self._ready is not None:",
        "test": ("local/tests/test_auto_relogin.py", "ready_is_only"),
    },
    {
        "id": "countdown-signature",
        "path": "local/application/auto_relogin.py",
        "function": "def notify_if_changed",
        "needle": 'retry_at = self._retry_at if view["auto_state"] == "backoff" else None',
        "replacement": 'retry_at = view["auto_retry_in_s"] if view["auto_state"] == "backoff" else None',
        "test": ("local/tests/test_auto_relogin.py", "notify_changes_once"),
    },
    {
        "id": "deadline-signature",
        "path": "local/application/auto_relogin.py",
        "function": "def notify_if_changed",
        "needle": 'signature = (view["auto_state"], view["auto_block"], retry_at)',
        "replacement": 'signature = (view["auto_state"], view["auto_block"])',
        "test": ("local/tests/test_auto_relogin.py", "second_backoff"),
    },
    {
        "id": "run-notify",
        "path": "local/application/auto_relogin.py",
        "function": "def _run",
        "needle": "            self.notify_if_changed()\n",
        "replacement": "",
        "test": ("local/tests/test_auto_relogin.py", "run_notifies"),
    },
    {
        "id": "check-field",
        "path": "local/app.py",
        "function": "def _do_check_inner",
        "needle": '        payload.update(self._auto_relogin.view(expired=result == "expired"))\n',
        "replacement": "",
        "test": ("local/tests/test_silent_relogin.py", "check_exposes_running"),
    },
    {
        "id": "bootstrap-field",
        "path": "local/app.py",
        "function": "def bootstrap",
        "needle": '            login_info.update(self._auto_relogin.view(expired=last_check.get("result") == "expired"))\n',
        "replacement": "",
        "test": ("local/tests/test_silent_relogin.py", "bootstrap_login"),
    },
    {
        "id": "change-callback",
        "path": "local/app.py",
        "function": "def __init__(self, clock=None)",
        "needle": ', on_change=lambda view: self._emit("login_auto", view)',
        "replacement": "",
        "test": ("local/tests/test_silent_relogin.py", "monitor_constructor"),
    },
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    names = result.stdout.decode().split("\0")
    forbidden = ("local/data/", "server/data/", "config.json", "local/_site_build.py", ".env")
    return [name for name in names if name and not any(item in name for item in forbidden)]


def make_copy() -> Path:
    temp_root = Path(tempfile.mkdtemp(prefix="login-fields-mutation-"))
    for name in tracked_files():
        source = ROOT / name
        target = temp_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in COPY_EXTRA:
        source = ROOT / name
        target = temp_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return temp_root


def replace_once(root: Path, mutation: dict) -> None:
    path = root / mutation["path"]
    text = path.read_text(encoding="utf-8")
    start = text.find(mutation["function"])
    if start < 0:
        raise AssertionError(f"function not found: {mutation['function']}")
    position = text.find(mutation["needle"], start)
    if position < 0:
        raise AssertionError(f"line not found: {mutation['path']}:{mutation['function']}")
    before = text[:position]
    after = text[position + len(mutation["needle"]):]
    path.write_text(before + mutation["replacement"] + after, encoding="utf-8", newline="")


def run_test(root: Path, test_file: str, pattern: str) -> tuple[int, str]:
    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
               "-p", Path(test_file).name, "-k", pattern]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True,
                            encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    match = re.search(r"(?:FAIL|ERROR): ([^\r\n]+)", output)
    first_failure = match.group(1) if match else "no failure detail"
    return result.returncode, first_failure


def main() -> int:
    failures = []
    for mutation in MUTATIONS:
        copy_root = make_copy()
        try:
            replace_once(copy_root, mutation)
            code, first_failure = run_test(copy_root, *mutation["test"])
            status = "red" if code != 0 else "green"
            print(f"{mutation['id']}\t{status}\t{first_failure}")
            if code == 0:
                failures.append(mutation["id"])
        finally:
            shutil.rmtree(copy_root, ignore_errors=True)
    if failures:
        print("mutations unexpectedly green: " + ", ".join(failures))
        return 1
    print(f"all {len(MUTATIONS)} mutations were detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
