#!/usr/bin/env python3
"""比较 HEAD 副本和当前工作区的登录胶囊网格结果。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
TARGETS = (
    "local/ui/features/login/state-machine.js",
    "local/ui/features/login/view.js",
    "local/ui/features/login/state-relogin.js",
)


RUNNER = r'''
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "local" / "tests"))
from fixtures.ui_harness import run_js

script = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const values = (name) => name === "ok" ? [true, false, null, undefined]
  : name === "present" ? [true, false, undefined]
  : name === "result" ? ["valid", "expired", "unknown", "none", null]
  : [false, true];
const output = { total: 0, different: 0, phases: {}, rows: [] };
const estimateValues = (result) => result === "valid" ? [null,
  Date.UTC(2026, 10, 6, 8, 0, 0), Date.UTC(2026, 10, 7, 2, 0, 0),
  Date.UTC(2026, 10, 9, 2, 0, 0)] : [null];
for (const busy of values("busy")) for (const demo of values("demo"))
for (const autoLogin of values("autoLogin")) for (const loginPending of values("loginPending"))
for (const checking of values("checking")) for (const termsLocked of values("termsLocked"))
for (const stopping of values("stopping")) for (const ok of values("ok"))
for (const present of values("present")) for (const result of values("result"))
for (const expireAt of estimateValues(result)) for (const lastCheck of ["", "2026-11-06 14:00:00"]) {
  S.busy = !!busy; S.demo = !!demo; S.autoLogin = !!autoLogin; S.stopping = !!stopping;
  S.terms.acceptedVersion = termsLocked ? "" : "v1";
  S.login = { ok: ok, present: present, checking: !!checking, loginPending: !!loginPending,
    result: result, handoff: false, expireAt: expireAt, estimateReason: expireAt ? "ok" : null,
    hours: null, lastCheckAt: lastCheck, lastCheckState: result || "unknown", view: {} };
  paintLogin();
  output.total += 1;
  const phase = typeof loginPhase === "function" ? loginPhase({
    busy: S.busy, demo: S.demo, autoLogin: S.autoLogin,
    loginPending: S.login.loginPending, checking: S.login.checking, ok: S.login.ok,
    present: S.login.present, result: S.login.result,
    termsLocked: termsLocked, stopping: S.stopping }) : "legacy";
  output.phases[phase] = (output.phases[phase] || 0) + 1;
  output.rows.push({ className: $("#pill").className, state: $("#pill").dataset.state,
    aria: $("#pill").getAttribute("aria-label"), text: $("#pill-text").textContent,
    sub: $("#pill-sub").textContent, note: $("#status-detail").textContent,
    btn: $("#btn-login-text").textContent, btnClass: $("#btn-login").className,
    view: { state: S.login.view.state, text: S.login.view.text,
      sub: S.login.view.sub, note: S.login.view.note } });
}
out.push(output);
"""
print(json.dumps(run_js(script)[0], ensure_ascii=False))
'''


def copy_head(dest: Path) -> None:
    archive = subprocess.run(["git", "archive", "HEAD"], cwd=ROOT,
                             check=True, capture_output=True).stdout
    import tarfile
    import io
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(dest)


def copy_current(dest: Path) -> None:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                            check=True, capture_output=True)
    names = [name for name in result.stdout.decode().split("\0") if name]
    excluded = ("local/data/", "server/data/", "config.json", "local/_site_build.py", ".env")
    for name in names:
        if any(item in name for item in excluded):
            continue
        source = ROOT / name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for name in TARGETS:
        source = ROOT / name
        if source.exists():
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def run_copy(root: Path) -> dict:
    runner = root / "grid_runner.py"
    runner.write_text(RUNNER, encoding="utf-8", newline="")
    result = subprocess.run([sys.executable, "-B", str(runner)], cwd=root,
                            check=True, capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="login-machine-grid-") as name:
        root = Path(name)
        head = root / "head"
        current = root / "current"
        head.mkdir()
        current.mkdir()
        copy_head(head)
        copy_current(current)
        before = run_copy(head)
        after = run_copy(current)
    before_rows = before.pop("rows")
    after_rows = after.pop("rows")
    different = sum(left != right for left, right in zip(before_rows, after_rows))
    print(json.dumps({"different_groups": different, "total_groups": len(before_rows),
                      "head_phases": before["phases"], "current_phases": after["phases"]},
                     ensure_ascii=False, sort_keys=True))
    return 0 if different == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
