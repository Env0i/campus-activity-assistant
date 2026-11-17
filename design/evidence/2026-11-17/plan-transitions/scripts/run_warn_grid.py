#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行提示的不变区对照：开工 HEAD 与当前工作区各画一遍同一张网格。

网格按登录胶囊的状态与相位、有没有在等的场次、有没有在提交的场次、有没有
login_wait、最早一场离开放三十秒/三百秒/不可知铺开；只比用户看得到的
`#run-warn` 的 hidden/tone/innerHTML、修改按钮的 disabled 与修改说明的文字。
允许的差异只有「要你输验证码且来得及」那些格子——那正是这一批按用户定稿改的。
自身对照开关拿开工 HEAD 比它自己，必须 0 不同。

用法（仓库根执行）：
  python -B design/evidence/2026-11-17/plan-transitions/scripts/run_warn_grid.py --self
  python -B design/evidence/2026-11-17/plan-transitions/scripts/run_warn_grid.py

@author Author
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
REF = "c3eb9d0"

RUNNER = r'''
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "local" / "tests"))
from fixtures.ui_harness import run_js  # noqa: E402
print(json.dumps(run_js(Path(root / "grid.js").read_text(encoding="utf-8"))[0], ensure_ascii=False))
'''

GRID = r"""
const OUT = { total: 0, rows: [], machine: typeof boardPhase === "function" };
const stampAt = (ms) => new Date(ms + 28800000).toISOString().replace("T", " ").slice(0, 19);
const STUDY = { ok: ["valid"], bad: ["expired", "needs_code", "retry_later", "auto"],
  unknown: ["valid"], pending: ["valid"] };
const put = (state, phase, waiting, submitting, autoWait, openIn) => {
  setBusinessNow(now);
  S.demo = false; S.busy = true;
  S.login.present = true; S.login.ok = state === "ok" || state === "pending";
  S.login.result = state === "ok" ? "valid" : (state === "pending" ? "unknown" : "expired");
  S.login.view = { state: state, phase: phase };
  S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
  S.stopping = false; S.editing = null; S.stopNote = null;
  const add = (id, st, extra) => S.plan.tasks.set(id, Object.assign({ task_id: id,
    activity_id: "a1", name: "活动甲", status: st, attempts: 0, sign_start: null }, extra || {}));
  if (waiting) add("t1", "waiting", { sign_start: openIn === null ? null : stampAt(now + openIn * 1000) });
  if (submitting) add("t2", "submitting", { sign_start: stampAt(now - 30 * 1000) });
  if (autoWait) add("t3", "waiting", { sign_start: stampAt(now + 300 * 1000), login_wait: "waiting" });
  paintRunPanel();
  const warn = $("#run-warn");
  return { state: state, phase: phase, waiting: waiting, submitting: submitting,
    autoWait: autoWait, openIn: openIn, hidden: !!warn.hidden, tone: warn.dataset.tone || "",
    html: warn.innerHTML || "", disabled: !!$("#btn-modify").disabled,
    why: $("#modify-why").textContent || "" };
};
const now = Date.UTC(2026, 10, 6, 6, 0, 0);
for (const state of Object.keys(STUDY))
for (const phase of STUDY[state])
for (const waiting of [false, true])
for (const submitting of [false, true])
for (const autoWait of [false, true])
for (const openIn of [30, 300, null]) {
  OUT.rows.push(put(state, phase, waiting, submitting, autoWait, openIn));
  OUT.total += 1;
}
out.push(OUT);
"""


SKIP = ("local/data/", "server/data/", "config.json", "local/_site_build.py")


def _skip(name: str) -> bool:
    if any(part in name for part in SKIP):
        return True
    return any(seg.startswith(".") for seg in name.split("/"))


def copy_head(dest: Path) -> None:
    archive = subprocess.run(["git", "archive", REF], cwd=ROOT, check=True,
                             capture_output=True).stdout
    import io
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar.getmembers():
            if member.isfile() and not _skip(member.name):
                data = tar.extractfile(member)
                target = dest / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data.read())


def copy_current(dest: Path) -> None:
    names = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                           cwd=ROOT, check=True, capture_output=True).stdout.decode().split("\0")
    for name in dict.fromkeys(names):
        if not name or _skip(name):
            continue
        source = ROOT / name
        if not source.is_file():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def run_side(root: Path) -> dict:
    (root / "grid.js").write_text(GRID, encoding="utf-8", newline="")
    (root / "grid_runner.py").write_text(RUNNER, encoding="utf-8", newline="")
    result = subprocess.run([sys.executable, "-B", str(root / "grid_runner.py")], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError(result.stderr[-1200:])
    return json.loads(result.stdout)


def compare(left: dict, right: dict) -> int:
    if len(left["rows"]) != len(right["rows"]):
        print(json.dumps({"error": "两组组数不同", "left": len(left["rows"]),
                          "right": len(right["rows"])}, ensure_ascii=False))
        return 2
    allowed = ["hidden", "tone", "html", "disabled", "why"]
    diffs = []
    for i, (a, b) in enumerate(zip(left["rows"], right["rows"])):
        fields = [k for k in allowed if a[k] != b[k]]
        if fields:
            expected = a["phase"] == "needs_code" and a["openIn"] == 300 and not a["submitting"]
            diffs.append({"row": i, "fields": fields, "expected": bool(expected),
                          "sample": {k: [a[k], b[k]] for k in fields[:2]}})
    other = [d for d in diffs if not d["expected"]]
    print(json.dumps({"total": len(left["rows"]), "allowed_diffs": len(diffs) - len(other),
                      "other_diffs": len(other), "first_diffs": diffs[:4]}, ensure_ascii=False))
    return 1 if other else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self", action="store_true", dest="self_check")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="run-warn-grid-") as name:
        base = Path(name)
        left = base / "head"
        right = base / "self" if args.self_check else base / "current"
        left.mkdir()
        right.mkdir()
        copy_head(left)
        if args.self_check:
            copy_head(right)
        else:
            copy_current(right)
        before = run_side(left)
        after = run_side(right)
    return compare(before, after)


if __name__ == "__main__":
    raise SystemExit(main())
