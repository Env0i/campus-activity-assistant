#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划栏标题区的状态机：十九个阶段、判断先后、样子表与每个阶段的现状文字。

三件事分开守：`boardPhase` 只看事实、按原分支的先后给出一个阶段；`BOARD_STYLE` 的键与阶段
一一对应；整页沙箱里每个阶段各摆一次，标签、标题、副行都要与改结构之前一字不差。

网格就在本文件里（`GRID`），用的是测试自带的沙箱：不读证据目录、不复制仓库。

@author Author
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

PHASES = ("first_use", "logging_in", "result", "terms_hold", "broken", "list_error",
          "list_loading", "run_target", "run_settling", "run_preparing", "next_open",
          "next_upcoming", "school_empty", "clock_pending", "none_eligible",
          "none_upcoming", "selected_paused", "editing", "selected")

# 整页网格：把状态摆成各种组合，每个组合都问一次 boardPhase 再画一次标题区。
# 「每个阶段挑一种最有代表性的样子」（NAMED）供逐字对照，其余铺开只为把分支压满。
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


def facts(**kw) -> dict:
    """一条事实：默认是「没在跑、登录过、列表空、没选场」的平静状态。"""
    base = {"busy": False, "present": True, "runtimeError": False, "loginPending": False,
            "resultMode": False, "termsLocked": False, "listState": "idle", "itemsCount": 0,
            "selectedCount": 0, "hasNext": False, "nextOpenNow": False, "clockKnown": True,
            "demo": False, "editing": False, "runPhase": "idle"}
    base.update(kw)
    return base


# 每个阶段各一条，再加「谁压过谁」的八条
CASES = [
    ("first_use", facts(present=False), "first_use"),
    ("logging_in", facts(loginPending=True), "logging_in"),
    ("result", facts(resultMode=True), "result"),
    ("terms_hold", facts(termsLocked=True), "terms_hold"),
    ("broken", facts(runtimeError=True), "broken"),
    ("list_error", facts(listState="error"), "list_error"),
    ("list_loading", facts(listState="loading"), "list_loading"),
    ("run_waiting", facts(busy=True, runPhase="waiting"), "run_target"),
    ("run_arming", facts(busy=True, runPhase="arming"), "run_target"),
    ("run_submitting", facts(busy=True, runPhase="submitting"), "run_target"),
    ("run_settling", facts(busy=True, runPhase="settling"), "run_settling"),
    ("run_preparing", facts(busy=True, runPhase="preparing"), "run_preparing"),
    ("run_idle", facts(busy=True, runPhase="idle"), "run_preparing"),
    ("next_open", facts(hasNext=True, nextOpenNow=True), "next_open"),
    ("next_upcoming", facts(hasNext=True), "next_upcoming"),
    ("school_empty", facts(listState="ready"), "school_empty"),
    ("clock_pending", facts(listState="ready", itemsCount=1, clockKnown=False), "clock_pending"),
    ("clock_pending_demo", facts(listState="ready", itemsCount=1, clockKnown=False,
                                 demo=True), "none_eligible"),
    ("none_eligible", facts(listState="ready", itemsCount=1), "none_eligible"),
    ("none_upcoming", facts(itemsCount=1), "none_upcoming"),
    ("selected_paused", facts(selectedCount=1, termsLocked=True), "selected_paused"),
    ("editing", facts(selectedCount=1, editing=True), "editing"),
    ("selected", facts(selectedCount=1), "selected"),
    ("login_over_result", facts(loginPending=True, resultMode=True), "logging_in"),
    ("result_over_terms", facts(resultMode=True, termsLocked=True), "result"),
    ("busy_over_empty", facts(busy=True, listState="ready"), "run_preparing"),
    ("first_use_needs_idle", facts(present=False, busy=True, runPhase="preparing"),
     "run_preparing"),
    ("first_use_needs_healthy", facts(present=False, runtimeError=True), "broken"),
    ("terms_with_selection", facts(termsLocked=True, selectedCount=2), "selected_paused"),
    ("editing_needs_selection", facts(editing=True, listState="ready", itemsCount=1),
     "none_eligible"),
]

# 每个阶段在整页沙箱里画出来的现状（照改结构之前的实际输出抄）
EXPECTED = {
    "first_use": {"tone": "off", "dot": "true", "tag": "首次使用", "title": "登录后开始",
                  "text": "活动会在登录完成后自动加载。"},
    "logging_in": {"tone": "amber", "dot": "true", "tag": "登录中", "title": "正在打开登录窗口",
                   "text": "在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。"},
    "result": {"tone": "green", "dot": "true", "tag": "报名成功", "title": "报名计划完成",
               "text": "每场结束时都向学校核对过。"},
    "terms_hold": {"tone": "off", "dot": "true", "tag": "已暂停", "title": "同意条款后才能报名",
                   "text": "登录、活动列表和报名计划都停用了。帮助和设置照常可用。"},
    "broken": {"tone": "red", "dot": "true", "tag": "不可用", "title": "暂时不能报名",
               "text": "程序组件缺失，处理办法在顶部提示里。"},
    "list_error": {"tone": "red", "dot": "true", "tag": "需重试", "title": "活动暂时没加载",
                   "text": "具体原因看左边列表的提示。"},
    "list_loading": {"tone": "off", "dot": "true", "tag": "加载中", "title": "活动列表正在加载",
                     "text": "先等这一次加载结束。"},
    "run_target": {"tone": "red", "dot": "true", "tag": "正在提交", "title": "开放场",
                   "text": "已提交 2 次"},
    "run_settling": {"tone": "amber", "dot": "true", "tag": "汇总中", "title": "正在汇总结果",
                     "text": "每一场都结束了，正在汇总这一轮的结果。"},
    "run_preparing": {"tone": "amber", "dot": "true", "tag": "准备中", "title": "正在准备报名",
                      "text": "计划已经接管，正在核对每一场的开放时间。"},
    "next_open": {"tone": "amber", "dot": "false", "tag": "开放中", "title": "开放场",
                  "text": "", "meta_has": "学生公寓"},
    "next_upcoming": {"tone": "amber", "dot": "true", "tag": "下一场", "title": "未来场",
                      "text": "", "meta_has": "学生公寓"},
    "school_empty": {"tone": "off", "dot": "true", "tag": "暂时没有", "title": "学校当前没有活动",
                     "text": "稍后刷新再看。"},
    "clock_pending": {"tone": "amber", "dot": "true", "tag": "时间待校准", "title": "时间待校准",
                      "text": "校准北京时间后才能判断哪些场次可以报名。查看时间详情",
                      "html_has": "data-open-clock"},
    "none_eligible": {"tone": "off", "dot": "true", "tag": "暂时没有", "title": "没有可报名的场次",
                      "text": "列表里的活动已报名、已截止或还没公布报名时间。"},
    "none_upcoming": {"tone": "off", "dot": "true", "tag": "暂时没有",
                      "title": "近期没有要开放的活动",
                      "text": "可能还没公布报名时间，也可能都报过了。过一会儿点「刷新」看看。"},
    "selected_paused": {"tone": "off", "dot": "true", "tag": "已暂停", "title": "已选 1 场",
                        "text": "1 场立即报名"},
    "editing": {"tone": "amber", "dot": "true", "tag": "修改中", "title": "已选 1 场",
                "text": "1 场立即报名"},
    "selected": {"tone": "amber", "dot": "true", "tag": "报名计划", "title": "已选 1 场",
                 "text": "1 场立即报名"},
}

_GRID_CACHE: dict = {}


def grid() -> dict:
    """跑一次整张网格：总组数、阶段命中数、每阶段一条现状。"""
    if not _GRID_CACHE:
        _GRID_CACHE.update(run_js(GRID)[0])
    return _GRID_CACHE


class PhaseTableTests(unittest.TestCase):
    def test_phases_are_frozen_and_in_order(self):
        got = run_js(r"""
out.push({ frozen: Object.isFrozen(BOARD_PHASES), phases: BOARD_PHASES.slice(),
  table: typeof BOARD_STYLE === "object" && BOARD_STYLE ? Object.keys(BOARD_STYLE) : null });
""")[0]
        self.assertTrue(got["frozen"], "BOARD_PHASES 必须冻结")
        self.assertEqual(tuple(got["phases"]), PHASES)
        self.assertIsNotNone(got["table"], "view.js 要导出按阶段取的样子表")
        self.assertEqual(sorted(got["table"]), sorted(PHASES), "样子表的键要与阶段一一对应")

    def test_phase_choices_and_their_order(self):
        cases = [c[1] for c in CASES]
        got = run_js("const cases = %s;\nout.push(cases.map((c) => boardPhase(c)));"
                     % json.dumps(cases, ensure_ascii=False))[0]
        for (name, _, want), got_phase in zip(CASES, got):
            self.assertEqual(got_phase, want, "%s 应落到 %s" % (name, want))

    def test_grid_runs_every_phase_at_least_once(self):
        data = grid()
        self.assertTrue(data["machine"], "网格里应当能调到 boardPhase")
        for phase in PHASES:
            self.assertGreater(data["phases"].get(phase, 0), 0, "网格没覆盖到 %s" % phase)
        self.assertEqual(data["total"], len(data["rows"]))
        self.assertGreater(data["total"], 1000, "网格太小，覆盖不住分支")


class BoardTextTests(unittest.TestCase):
    def test_every_phase_draws_its_current_text(self):
        named = grid()["named"]
        for phase in PHASES:
            want = EXPECTED[phase]
            got = named[phase]
            self.assertEqual(got["tag"], want["tag"], "%s 的标签字" % phase)
            self.assertEqual(got["tone"], want["tone"], "%s 的标签色调" % phase)
            self.assertEqual(got["dot"], want["dot"], "%s 的圆点" % phase)
            self.assertEqual(got["title"], want["title"], "%s 的标题" % phase)
            self.assertEqual(got["cls"], "b-title", "%s 的标题 class" % phase)
            if "text" in want:
                self.assertEqual(got["text"], want["text"], "%s 的副行" % phase)
            if "meta_has" in want:
                self.assertIn(want["meta_has"], got["meta"], "%s 的地点时间" % phase)
            if "html_has" in want:
                self.assertIn(want["html_has"], got["html"], "%s 的副行 HTML" % phase)

    def test_terms_unknown_and_two_selected_keep_their_wording(self):
        named = grid()["named"]
        self.assertEqual(named["terms_hold_unknown"]["title"], "重新确认条款后才能报名")
        self.assertEqual(named["terms_hold_unknown"]["text"],
                         "登录、活动列表和报名计划暂时停用。帮助和设置照常可用。")
        self.assertEqual(named["selected_two"]["title"], "已选 2 场")
        self.assertEqual(named["selected_two"]["text"], "2 场立即报名")


if __name__ == "__main__":
    unittest.main()
