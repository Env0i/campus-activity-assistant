#!/usr/bin/env python3
"""比较登录样子改动的完整胶囊网格和详情卡样子。"""
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
const output = { rows: [], skipped: 0, phases: {} };
for (const busy of values("busy")) for (const demo of values("demo"))
for (const autoLogin of values("autoLogin")) for (const loginPending of values("loginPending"))
for (const checking of values("checking")) for (const termsLocked of values("termsLocked"))
for (const stopping of values("stopping")) for (const ok of values("ok"))
for (const present of values("present")) for (const loginResult of values("result"))
for (const expireAt of estimateValues(loginResult)) for (const lastCheck of ["", "2026-11-06 14:00:00"]) {
  const unchanged = !(checking && ok === true && present === true && loginResult === "valid");
  if (!unchanged) { output.skipped += 1; continue; }
  S.busy = !!busy; S.demo = !!demo; S.autoLogin = !!autoLogin; S.stopping = !!stopping;
  S.terms.acceptedVersion = termsLocked ? "" : "v1";
  S.login = { ok: ok, present: present, checking: !!checking, loginPending: !!loginPending,
    result: loginResult, handoff: false, expireAt: expireAt, estimateReason: expireAt ? "ok" : null,
    hours: null, lastCheckAt: lastCheck, lastCheckState: loginResult || "unknown", view: {},
    auto: { state: "idle", block: "", retryInS: null, at: 0 } };
  paintLogin();
  renderLoginCard();
  const phase = S.login.view.phase;
  output.phases[phase] = (output.phases[phase] || 0) + 1;
  output.rows.push({ phase: phase, className: $("#pill").className,
    state: $("#pill").dataset.state, aria: $("#pill").getAttribute("aria-label"),
    text: $("#pill-text").textContent, sub: $("#pill-sub").textContent,
    note: $("#status-detail").textContent, btn: $("#btn-login-text").textContent,
    cardTone: $("#login-pop-chip").dataset.tone,
    cardText: $("#login-pop-chip-text").textContent,
    cardBig: $("#login-pop-big").textContent });
}
const special = (name, setup) => {
  S.busy = false; S.demo = false; S.stopping = false; S.autoLogin = false;
  S.terms.acceptedVersion = "v1";
  S.login = { ok: true, present: true, checking: false, loginPending: false,
    result: "valid", handoff: false, expireAt: null, estimateReason: null,
    hours: null, lastCheckAt: "", lastCheckState: "valid", view: {},
    auto: { state: "idle", block: "", retryInS: null, at: 0 } };
  setup(); paintLogin(); renderLoginCard();
  return { name: name, phase: S.login.view.phase,
    capsule: { className: $("#pill").className, text: $("#pill-text").textContent,
      sub: $("#pill-sub").textContent },
    card: { tone: $("#login-pop-chip").dataset.tone,
      text: $("#login-pop-chip-text").textContent, big: $("#login-pop-big").textContent } };
};
output.special = [
  special("rechecking", () => { S.login.checking = true; }),
  special("needs_code_handoff", () => {
    S.login.ok = false; S.login.result = "expired";
    applyAutoState({ auto_state: "handoff", auto_block: "", auto_retry_in_s: null });
  }),
  special("needs_code_ocr_missing", () => {
    S.login.ok = false; S.login.result = "expired";
    applyAutoState({ auto_state: "blocked", auto_block: "ocr_missing", auto_retry_in_s: null });
  }),
  special("retry_later", () => {
    S.login.ok = false; S.login.result = "expired";
    applyAutoState({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 300 });
  }),
];
out.push(output);
"""
print(json.dumps(run_js(script)[0], ensure_ascii=False))
'''


def run_copy(root: Path) -> dict:
    runner = root / "looks_runner.py"
    runner.write_text(RUNNER, encoding="utf-8", newline="")
    proc = subprocess.run([sys.executable, "-B", str(runner)], cwd=root,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True)
    return json.loads(proc.stdout)


def compare_rows(before: dict, after: dict) -> dict:
    assert len(before["rows"]) == len(after["rows"])
    assert before["skipped"] == after["skipped"]
    allowed = {"auto": 0, "unknown": 0}
    other = 0
    by_phase = {}
    fields = ("phase", "className", "state", "aria", "text", "sub", "note",
              "btn", "cardTone", "cardText", "cardBig")
    for left, right in zip(before["rows"], after["rows"]):
        phase = left["phase"]
        differences = [field for field in fields if left[field] != right[field]]
        by_phase[phase] = by_phase.get(phase, 0) + 1
        is_auto = (phase == "auto" and differences == ["className"]
                   and right["className"] == left["className"] + " is-spin")
        is_unknown = (phase == "unknown" and differences == ["className"]
                      and left["className"] == "pill is-none"
                      and right["className"] == "pill is-warn")
        if is_auto:
            allowed["auto"] += 1
        elif is_unknown:
            allowed["unknown"] += 1
        elif differences:
            other += 1
    return {"allowed_differences": allowed, "other_differences": other,
            "phase_groups": by_phase, "compared_groups": len(before["rows"]),
            "skipped_groups": before["skipped"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self", dest="self_check", action="store_true",
                        help="开工 HEAD 的两份副本互比")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="login-looks-grid-") as temp:
        root = Path(temp); left = root / "head"; right = root / "other"
        left.mkdir(); right.mkdir(); copy_head(left)
        if args.self_check:
            copy_head(right)
        else:
            copy_current(right)
        before = run_copy(left); after = run_copy(right)
    comparison = compare_rows(before, after)
    result = {"mode": "head-vs-head" if args.self_check else "head-vs-current",
              **comparison, "special": []}
    for left, right in zip(before["special"], after["special"]):
        result["special"].append({"name": left["name"], "before": left, "after": right})
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if comparison["other_differences"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
