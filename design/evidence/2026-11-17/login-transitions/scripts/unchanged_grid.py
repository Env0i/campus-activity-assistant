#!/usr/bin/env python3
"""比较不进入新阶段的登录胶囊网格。

维度与上一批网格相同（含估算到期时刻四个取值、上次校验时刻两个取值），
跳过会进入「有效·确认中」的组。默认比较开工 HEAD 与当前工作区；
加 --self 时比较开工 HEAD 的两份独立副本，用来确认网格本身稳定。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "design/evidence/2026-11-16/login-machine/scripts"))
from capsule_grid import copy_current, copy_head  # noqa: E402
RUNNER = r'''
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "local" / "tests"))
from fixtures.ui_harness import run_js

script = r"""
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
S.online = true;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const values = (name) => name === "ok" ? [true, false, null, undefined]
  : name === "present" ? [true, false, undefined]
  : name === "result" ? ["valid", "expired", "unknown", "none", null]
  : [false, true];
const estimateValues = (result) => result === "valid" ? [null,
  Date.UTC(2026, 10, 6, 8, 0, 0), Date.UTC(2026, 10, 7, 2, 0, 0),
  Date.UTC(2026, 10, 9, 2, 0, 0)] : [null];
const result = { rows: [], skipped: 0 };
for (const busy of values("busy")) for (const demo of values("demo"))
for (const autoLogin of values("autoLogin")) for (const loginPending of values("loginPending"))
for (const checking of values("checking")) for (const termsLocked of values("termsLocked"))
for (const stopping of values("stopping")) for (const ok of values("ok"))
for (const present of values("present")) for (const loginResult of values("result"))
for (const expireAt of estimateValues(loginResult)) for (const lastCheck of ["", "2026-11-06 14:00:00"]) {
  const unchanged = !(checking && ok === true && present === true && loginResult === "valid");
  if (!unchanged) { result.skipped += 1; continue; }
  S.busy = !!busy; S.demo = !!demo; S.autoLogin = !!autoLogin; S.stopping = !!stopping;
  S.terms.acceptedVersion = termsLocked ? "" : "v1";
  S.login = { ok: ok, present: present, checking: !!checking, loginPending: !!loginPending,
    result: loginResult, handoff: false, expireAt: expireAt,
    estimateReason: expireAt ? "ok" : null, hours: null, lastCheckAt: lastCheck,
    lastCheckState: loginResult || "unknown", view: {} };
  paintLogin();
  result.rows.push({ className: $("#pill").className, state: $("#pill").dataset.state,
    aria: $("#pill").getAttribute("aria-label"), text: $("#pill-text").textContent,
    sub: $("#pill-sub").textContent, note: $("#status-detail").textContent,
    btn: $("#btn-login-text").textContent, btnClass: $("#btn-login").className,
    view: { state: S.login.view.state, text: S.login.view.text,
      sub: S.login.view.sub, note: S.login.view.note } });
}
out.push(result);
"""
print(json.dumps(run_js(script)[0], ensure_ascii=False))
'''


def run_copy(root: Path) -> dict:
    runner = root / "unchanged_runner.py"
    runner.write_text(RUNNER, encoding="utf-8", newline="")
    proc = subprocess.run([sys.executable, "-B", str(runner)], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          check=True)
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self", dest="self_check", action="store_true",
                        help="开工 HEAD 对开工 HEAD，确认网格本身稳定")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="login-transitions-grid-") as temp:
        root = Path(temp); left = root / "head"; right = root / "other"
        left.mkdir(); right.mkdir(); copy_head(left)
        if args.self_check:
            copy_head(right)
        else:
            copy_current(right)
        before = run_copy(left); after = run_copy(right)
    assert len(before["rows"]) == len(after["rows"]), (len(before["rows"]), len(after["rows"]))
    assert before["skipped"] == after["skipped"], (before["skipped"], after["skipped"])
    different = sum(a != b for a, b in zip(before["rows"], after["rows"]))
    print(json.dumps({"mode": "head-vs-head" if args.self_check else "head-vs-current",
                      "different_groups": different, "compared_groups": len(before["rows"]),
                      "skipped_groups": before["skipped"]}, ensure_ascii=False))
    return 0 if different == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
