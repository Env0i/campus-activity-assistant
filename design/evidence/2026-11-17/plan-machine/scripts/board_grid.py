#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""改前改后逐元素对照：计划栏标题区在同一张网格上分别跑开工 HEAD 与当前工作区。

两棵树都按 index.html 的顺序拼页脚本、在同一套 DOM 桩里调 paintSelected，逐个比对
`#board-tag` 的色调与圆点、标签字、`#selected` 的 className 与标题、`#selected-meta`
与 `#board-text` 的 innerHTML。网格按「能落进哪个分支」铺，覆盖标题区的每一种样子。

用法（仓库根执行）：
  python -B design/evidence/<日期>/plan-machine/scripts/board_grid.py --self
      开工 HEAD 与它自己比：证明沙箱本身稳定（必须 0 不同、两组数相等）
  python -B design/evidence/<日期>/plan-machine/scripts/board_grid.py
      开工 HEAD 与当前工作区比：0 不同才算行为没变；同时打印每个阶段命中的组数

@author Author
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
REF = "02c8760"

RUNNER = r'''
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "local" / "tests"))
from fixtures.ui_harness import run_js  # noqa: E402

SCRIPT = open(root / "grid.js", encoding="utf-8").read()
print(json.dumps(run_js(SCRIPT)[0], ensure_ascii=False))
'''

GRID = r"""
const OUT = { total: 0, rows: [], phases: {}, named: {}, machine: typeof boardPhase === "function" };
const realClock = businessNowMs;
const mk = (id, name, signed, start, end) => normalize({ id: id, name: name, place: "学生公寓",
  signed: signed, checkin_required: false, checkout_required: false,
  sign_start: start, sign_end: end,
  act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00" });
const SETS = {
  empty: [],
  signed: [mk("s1", "已报场", true, "2026-11-06 09:00:00", "2026-11-06 20:00:00")],
  open: [mk("o1", "开放场", false, "2026-11-06 13:00:00", "2026-11-06 20:00:00"),
         mk("o2", "第二场", false, "2026-11-06 13:30:00", "2026-11-06 21:00:00")],
  future: [mk("f1", "未来场", false, "2026-11-07 09:00:00", "2026-11-08 09:00:00"),
           mk("f2", "再一场", false, "2026-11-09 09:00:00", "2026-11-10 09:00:00")],
};
const terminal = () => ({
  id: "p1", status: "partial", gen: 1,
  tasks: new Map([["t1", { task_id: "t1", activity_id: "o1", name: "开放场", status: "success" }]]),
});
const RUNS = {
  submitting: () => ({
    id: "p1", status: "running", gen: 1,
    tasks: new Map([["t1", { task_id: "t1", activity_id: "o1", name: "开放场", status: "submitting",
      attempts: 2, signup_mode: "instant_signup", sign_start: "2026-11-06 13:00:00" }]]),
  }),
  arming: () => ({
    id: "p1", status: "running", gen: 1,
    tasks: new Map([["t1", { task_id: "t1", activity_id: "o1", name: "开放场", status: "waiting",
      attempts: 0, signup_mode: "instant_signup", sign_start: "2026-11-06 13:00:00" }]]),
  }),
  waiting: () => ({
    id: "p1", status: "running", gen: 1,
    tasks: new Map([["t1", { task_id: "t1", activity_id: "f1", name: "未来场", status: "waiting",
      attempts: 0, signup_mode: "pre_register", sign_start: "2026-11-07 09:00:00" }]]),
  }),
  settling: () => ({
    id: "p1", status: "running", gen: 1,
    tasks: new Map([["t1", { task_id: "t1", activity_id: "o1", name: "开放场", status: "success" }]]),
  }),
  preparing: () => ({ id: "p1", status: "running", gen: 1, tasks: new Map() }),
};
const blank = () => {
  const tag = $("#board-tag");
  tag.dataset = {};
  $("#board-tag-text").textContent = "";
  const box = $("#selected");
  box.className = "";
  box.textContent = "";
  $("#selected-meta").innerHTML = "";
  $("#board-text").innerHTML = "";
};
const reset = (d) => {
  S.demo = d.demo;
  S.busy = d.busy;
  S.listState = d.listState;
  S.online = true;
  S.terms = { version: "v1", acceptedVersion: d.terms === "accepted" ? "v1" : "",
    acceptedAt: "", declined: d.terms === "declined", prompted: true,
    unknown: d.terms === "unknown" };
  S.login = { present: d.present, ok: true, result: "valid", checking: false,
    loginPending: d.loginPending, view: { state: "ok" }, preLoginSnapshot: null };
  S.runtime = { error: d.broken ? "missing" : null, checkPending: false, listPending: false,
    roundError: null };
  S.items = SETS[d.items];
  S.byId = new Map(S.items.map((i) => [String(i.id), i]));
  S.selected = new Set(S.items.slice(0, d.sel).map((i) => String(i.id)));
  S.editing = d.editing ? { ids: [], doneN: 0 } : null;
  S.plan = { id: null, status: "idle", tasks: new Map(), gen: 1 };
  S.resultOpen = false;
  S.resultSel = null;
  S.cancel = { busyId: null };
  S.starting = false;
  S.stopping = false;
  setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
  businessNowMs = d.clock ? realClock : () => null;
  if (d.result) {
    S.plan = terminal();
    S.resultOpen = true;
    S.resultSel = selectionSignature();
  }
  if (d.run) S.plan = RUNS[d.run]();
};
const read = () => ({
  tone: $("#board-tag").dataset.tone,
  dot: $("#board-tag").dataset.dot,
  tag: $("#board-tag-text").textContent,
  cls: $("#selected").className,
  title: $("#selected").textContent,
  meta: $("#selected-meta").innerHTML,
  /* 副行有两支写 innerHTML、其余写 textContent：桩里两者不联动，两个都读才比得全 */
  text: $("#board-text").textContent,
  html: $("#board-text").innerHTML,
});
const factsOf = () => {
  const next = boardTargetItem();
  return { busy: S.busy, present: S.login.present, runtimeError: !!S.runtime.error,
    loginPending: !!S.login.loginPending, resultMode: resultMode(), termsLocked: termsLocked(),
    listState: S.listState, itemsCount: S.items.length, selectedCount: selectedItems().length,
    hasNext: !!next, nextOpenNow: !!next && stateOf(next) === "open",
    clockKnown: bnowS() !== null, demo: S.demo, editing: !!S.editing,
    runPhase: executionView().phase };
};
const push = (d, name) => {
  reset(d);
  const facts = factsOf();
  const phase = OUT.machine ? boardPhase(facts) : null;
  blank();
  paintSelected();
  const row = read();
  OUT.total += 1;
  OUT.rows.push(row);
  if (phase) OUT.phases[phase] = (OUT.phases[phase] || 0) + 1;
  if (name) OUT.named[name] = row;
};
/* 每个阶段挑一种最有代表性的样子，供新测试逐字对照；另加两个表里会分叉的写法 */
const BASE_IDLE = { busy: false, run: null, present: true, loginPending: false, broken: false,
  listState: "ready", terms: "accepted", items: "empty", sel: 0, result: false,
  editing: false, clock: true, demo: false };
const NAMED = [
  ["first_use", { present: false }],
  ["logging_in", { loginPending: true }],
  ["result", { result: true }],
  ["terms_hold", { terms: "locked" }],
  ["terms_hold_unknown", { terms: "unknown" }],
  ["broken", { broken: true, listState: "idle" }],
  ["list_error", { listState: "error", items: "empty" }],
  ["list_loading", { listState: "loading", items: "open" }],
  ["run_target", { busy: true, run: "submitting" }],
  ["run_settling", { busy: true, run: "settling" }],
  ["run_preparing", { busy: true, run: "preparing" }],
  ["next_open", { items: "open" }],
  ["next_upcoming", { items: "future" }],
  ["school_empty", { items: "empty" }],
  ["clock_pending", { items: "signed", clock: false }],
  ["none_eligible", { items: "signed" }],
  ["none_upcoming", { items: "signed", listState: "idle" }],
  ["selected_paused", { items: "open", sel: 1, terms: "locked" }],
  ["editing", { items: "open", sel: 1, editing: true }],
  ["selected", { items: "open", sel: 1 }],
  ["selected_two", { items: "open", sel: 2 }],
];
for (const item of NAMED) push(Object.assign({}, BASE_IDLE, item[1]), item[0]);
const IDLE = [];
for (const present of [true, false, undefined])
for (const loginPending of [false, true])
for (const broken of [false, true])
for (const listState of ["ready", "loading", "error", "idle"])
for (const terms of ["accepted", "locked", "unknown"])
for (const items of ["empty", "signed", "open", "future"])
for (const result of [false, true])
for (const editing of [false, true])
for (const clock of [true, false])
for (const demo of [false, true]) {
  const top = items === "empty" ? 1 : 3;
  for (let sel = 0; sel < top; sel += 1) {
    IDLE.push({ busy: false, run: null, present: present, loginPending: loginPending,
      broken: broken, listState: listState, terms: terms, items: items, sel: sel,
      result: result, editing: editing, clock: clock, demo: demo });
  }
}
for (const d of IDLE) push(d);
for (const loginPending of [false, true])
for (const run of ["submitting", "arming", "waiting", "settling", "preparing"])
for (const items of ["empty", "open"])
for (const terms of ["accepted", "locked"])
for (const present of [true, false])
for (const sel of [0, 1]) {
  push({ busy: true, run: run, present: present, loginPending: loginPending, broken: false,
    listState: "ready", terms: terms, items: items, sel: sel, result: false,
    editing: false, clock: true, demo: false });
}
out.push(OUT);
"""


def copy_head(dest: Path) -> None:
    archive = subprocess.run(["git", "archive", REF], cwd=ROOT, check=True,
                             capture_output=True).stdout
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        tar.extractall(dest)


SKIP = ("local/data/", "server/data/", "config.json", "local/_site_build.py")


def _skip(name: str) -> bool:
    """不抄的：数据根、站点构建脚本、隐藏目录与隐藏文件（运行时目录与环境变量文件都在里面）。"""
    if any(part in name for part in SKIP):
        return True
    return any(seg.startswith(".") for seg in name.split("/"))


def _names(root: Path) -> list:
    """仓库里该抄的文件。副本里没有 .git（变异与测试都在副本里跑），这时按目录走一遍。"""
    try:
        out = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=root, check=True, capture_output=True).stdout
        return out.decode().split("\0")
    except (subprocess.CalledProcessError, FileNotFoundError):
        names = []
        for path in root.rglob("*"):
            if path.is_file():
                names.append(path.relative_to(root).as_posix())
        return names


def copy_current(dest: Path, root: Path = None) -> None:
    root = root or ROOT
    for name in dict.fromkeys(_names(root)):
        if not name or _skip(name):
            continue
        source = root / name
        if not source.exists():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def run_side(root: Path) -> dict:
    (root / "grid.js").write_text(GRID, encoding="utf-8", newline="")
    runner = root / "grid_runner.py"
    runner.write_text(RUNNER, encoding="utf-8", newline="")
    result = subprocess.run([sys.executable, "-B", str(runner)], cwd=root, check=True,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(result.stdout)


def compare(left: dict, right: dict) -> int:
    if len(left["rows"]) != len(right["rows"]):
        print(json.dumps({"error": "两组组数不同", "left": len(left["rows"]),
                          "right": len(right["rows"])}, ensure_ascii=False))
        return 2
    different = [(i, a, b) for i, (a, b) in enumerate(zip(left["rows"], right["rows"])) if a != b]
    print(json.dumps({"total": left["total"], "different": len(different),
                      "phases": right.get("phases") or left.get("phases") or {},
                      "first_diffs": different[:3]}, ensure_ascii=False))
    return 0 if not different else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self", action="store_true", dest="self_check")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="plan-machine-grid-") as name:
        base = Path(name)
        left = base / "head"
        right = base / "current"
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
