#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_ui_plan.py（来源：test_plan_machine.py, test_plan_transitions.py, test_ui_plan_board.py, test_ui_plan_flow.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_plan_machine.py ====================
"""计划栏标题区的状态机：十九个阶段、判断先后、样子表与每个阶段的现状文字。

三件事分开守：`boardPhase` 只看事实、按原分支的先后给出一个阶段；`BOARD_STYLE` 的键与阶段
一一对应；整页沙箱里每个阶段各摆一次，标签、标题、副行都要与改结构之前一字不差。

网格就在本文件里（`GRID`），用的是测试自带的沙箱：不读证据目录、不复制仓库。

@author Author
"""

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

# ==================== 源自 test_plan_transitions.py ====================
"""计划栏新转移的行为测试：要你输验证码、停止没成功、快照对账与窗口恢复。

先断言用户看得到的（运行提示、按钮、说明、记录），再断言内部标记。
沙箱按 index.html 的加载顺序回放真实脚本；学校请求一律用本地桩。

@author Author
"""


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))


TRANSITIONS_PRELUDE = r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.terms.version = "v1"; S.terms.acceptedVersion = "v1"; S.demo = false; S.online = true;
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
const running = (open) => {
  S.busy = true; S.stopping = false; S.editing = null; S.stopNote = null;
  S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
  S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
    status: "waiting", attempts: 0, sign_start: open });
};
const warn = () => ({ text: $("#run-warn").textContent, html: $("#run-warn").innerHTML,
  hidden: $("#run-warn").hidden, tone: $("#run-warn").dataset.tone || "" });
const look = () => ({ warn: warn(), editing: S.editing || null, stopping: S.stopping,
  note: S.stopNote || null, logs: S.recentLogs.join("|"), stop: $("#btn-stop").textContent,
  plan: $("#btn-plan").textContent, board: $("#board-text").textContent,
  busy: S.busy, editNoteHidden: $("#edit-note").hidden });
const needHint = (mode) => {
  if (mode === "blocked") {
    window.onBackend.check({ ok: false, result: "expired", session_present: true,
      auto_state: "idle" });
    window.onBackend.login_auto({ auto_state: "blocked", auto_block: "ocr_missing" });
  } else {
    window.onBackend.check({ ok: false, result: "expired", session_present: true,
      auto_state: "handoff" });
  }
};
'''

TIMELY = "登录失效了，电脑认不出验证码。只要在 14:03:20 前输完验证码，计划照常继续；" \
         "否则 14:05:00 开放的那批会以“登录失效”结束。"


class RunWarnTransitionTests(unittest.TestCase):
    def test_needs_code_prompts_entering_captcha_when_time_allows(self):
        for mode in ("handoff", "blocked"):
            with self.subTest(mode=mode):
                data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:05:00"); needHint(%s); render();
out.push({ pill: $("#pill-text").textContent, warn: warn() });
''' % ('"' + mode + '"'))[0]
                self.assertEqual(data["pill"], "要你输验证码")
                self.assertIn(TIMELY, data["warn"]["text"])
                self.assertIn('data-act="login"', data["warn"]["html"])
                self.assertIn("输入验证码", data["warn"]["html"])

    def test_plain_expiry_keeps_the_original_relogin_sentence(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:05:00");
window.onBackend.check({ ok: false, result: "expired", session_present: true,
  auto_state: "idle" }); render();
out.push(warn());
''')[0]
        self.assertIn("重新登录", data["text"])
        self.assertNotIn("电脑认不出验证码", data["text"])
        self.assertIn('data-act="login"', data["html"])

    def test_too_late_keeps_the_original_sentence_for_both_login_cases(self):
        for mode in ("handoff", "idle"):
            with self.subTest(mode=mode):
                data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:00:30");
window.onBackend.check({ ok: false, result: "expired", session_present: true,
  auto_state: %s }); render();
out.push(warn());
''' % ('"handoff"' if mode == "handoff" else '"idle"'))[0]
                self.assertIn("来不及重新登录", data["text"])
                self.assertIn("这一批", data["text"])
                self.assertNotIn("data-act=", data["html"])


class StopFailureTransitionTests(unittest.TestCase):
    def test_stop_failure_while_editing_says_pausing_failed(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); S.editing = { ids: [], doneN: 0 };
doStopPlan(); await flush(); render(); out.push(look());
''')[0]
        self.assertEqual(data["warn"]["text"], "没能暂停，计划照常进行。")
        self.assertEqual(data["warn"]["tone"], "warn")
        self.assertFalse(data["editing"])
        self.assertTrue(data["editNoteHidden"])
        self.assertIn("停止没成功，计划继续运行", data["logs"])
        self.assertEqual(data["note"], {"planId": "p1", "text": "没能暂停，计划照常进行。"})

    def test_plain_stop_failure_says_stopping_failed(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush(); render(); out.push(look());
''')[0]
        self.assertEqual(data["warn"]["text"], "没能停止，计划照常进行。")
        self.assertEqual(data["warn"]["tone"], "warn")
        self.assertEqual(data["note"], {"planId": "p1", "text": "没能停止，计划照常进行。"})

    def test_login_hint_wins_over_a_stop_note(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
needHint("handoff"); render(); out.push(look());
''')[0]
        self.assertIn(TIMELY.replace("14:03:20", "15:58:20")
                      .replace("14:05:00", "16:00:00"), data["warn"]["text"])
        self.assertIn("输入验证码", data["warn"]["html"])

    def test_another_stop_clears_the_previous_stop_note(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
let first = true;
window.pywebview = { api: { stop_plan: () => first
  ? (first = false, Promise.reject(new Error("桥接断了"))) : new Promise(() => {}) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
const before = look();
doStopPlan(); render(); out.push({ before: before.note, after: look() });
''')[0]
        self.assertEqual(data["before"]["text"], "没能停止，计划照常进行。")
        self.assertIsNone(data["after"]["note"])
        self.assertTrue(data["after"]["warn"]["hidden"])

    def test_stop_note_from_an_earlier_plan_does_not_show_on_a_new_one(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
S.busy = true; S.stopping = false; S.editing = null;
S.plan = { id: "p2", status: "running", tasks: new Map(), source: "" };
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙",
  status: "waiting", attempts: 0, sign_start: "2026-11-06 16:00:00" });
render(); out.push({ view: look(), planId: S.plan.id });
''')[0]
        self.assertNotIn("没能停止，计划照常进行。", data["view"]["warn"]["text"])
        self.assertTrue(data["view"]["busy"])
        self.assertEqual(data["view"]["note"]["planId"], "p1")
        self.assertNotEqual(data["view"]["note"]["planId"], data["planId"])


class StopResyncTransitionTests(unittest.TestCase):
    def test_no_such_plan_resyncs_from_bootstrap_instead_of_lying(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
const calls = [];
window.pywebview = { api: {
  stop_plan: () => { calls.push("stop_plan"); return Promise.resolve({ ok: false,
    text: "当前没有这个计划" }); },
  bootstrap: () => { calls.push("bootstrap"); return Promise.resolve({ busy: false }); },
} };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
out.push({ calls: calls, view: look() });
''')[0]
        self.assertEqual(data["calls"], ["stop_plan", "bootstrap"])
        self.assertNotIn("正在停止", data["view"]["stop"])
        self.assertEqual(data["view"]["plan"], "开始报名计划")
        self.assertIn("可能还没公布报名时间", data["view"]["board"])
        self.assertFalse(data["view"]["busy"])
        self.assertFalse(data["view"]["stopping"])
        self.assertIsNone(data["view"]["note"])
        self.assertNotIn("照常进行", data["view"]["warn"]["text"])

    def test_window_return_drops_a_stale_stopping_flag(self):
        data = run_js(r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.busy = true; S.stopping = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
window.pywebview = { api: { bootstrap: () => Promise.resolve({ busy: false }),
  list_activities: () => Promise.resolve({ ok: true, items: [] }) } };
document.hidden = false;
window.__docListeners.visibilitychange.forEach((fn) => fn());
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push({ stopping: S.stopping, stop: $("#btn-stop").textContent });
''')[0]
        self.assertFalse(data["stopping"])
        self.assertNotIn("正在停止", data["stop"])


class FrameAndStopLogTests(unittest.TestCase):
    """收尾小修：外框随登录、停止记录按快照写。先断言用户看得到的，再断言内部值。"""

    def test_login_pending_draws_idle_frame_but_keeps_login_heading(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: { login: () => new Promise(() => {}) } };
doLogin(); render();
out.push({ frame: $("#board").dataset.planState, tag: $("#board-tag-text").textContent,
  title: $("#selected").textContent, pending: S.login.loginPending, busy: S.busy });
''')[0]
        self.assertEqual(data["frame"], "idle", "浏览器登录窗口开着时外框按没在跑画")
        self.assertEqual(data["tag"], "登录中")
        self.assertEqual(data["title"], "正在打开登录窗口")
        self.assertTrue(data["pending"])
        self.assertTrue(data["busy"])

    def test_waiting_plan_keeps_running_frame(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 16:00:00"); render();
out.push({ frame: $("#board").dataset.planState, pending: S.login.loginPending });
''')[0]
        self.assertEqual(data["frame"], "running", "计划等开放时外框仍是运行色")
        self.assertFalse(data["pending"])

    def test_snapshot_not_busy_writes_plan_already_ended(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {
  stop_plan: () => Promise.resolve({ ok: false, text: "当前没有这个计划" }),
  bootstrap: () => Promise.resolve({ busy: false }) } };
running("2026-11-06 16:00:00"); S.editing = { ids: [], doneN: 0 };
doStopPlan(); await flush(); render(); out.push({ logs: S.recentLogs.join("|"), busy: S.busy });
''')[0]
        self.assertIn("计划已经结束，修改作废", data["logs"])
        self.assertNotIn("计划继续运行", data["logs"])
        self.assertFalse(data["busy"])

    def test_snapshot_busy_writes_stop_failed_as_before(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {
  stop_plan: () => Promise.resolve({ ok: false, text: "当前没有这个计划" }),
  bootstrap: () => Promise.resolve({ busy: true }) } };
running("2026-11-06 16:00:00"); S.editing = { ids: [], doneN: 0 };
doStopPlan(); await flush(); render(); out.push({ logs: S.recentLogs.join("|"), busy: S.busy });
''')[0]
        self.assertIn("停止没成功，计划继续运行", data["logs"])
        self.assertNotIn("计划已经结束，修改作废", data["logs"])
        self.assertTrue(data["busy"])

    def test_bootstrap_failure_writes_stop_failed_conservatively(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {
  stop_plan: () => Promise.resolve({ ok: false, text: "当前没有这个计划" }),
  bootstrap: () => Promise.reject(new Error("快照拿不到")) } };
running("2026-11-06 16:00:00"); S.editing = { ids: [], doneN: 0 };
doStopPlan(); await flush(); render(); out.push({ logs: S.recentLogs.join("|"), busy: S.busy });
''')[0]
        self.assertIn("停止没成功，计划继续运行", data["logs"])
        self.assertNotIn("计划已经结束，修改作废", data["logs"])
        self.assertTrue(data["busy"])

    def test_plain_refusal_writes_neither_editing_sentence(self):
        data = run_js(TRANSITIONS_PRELUDE + r'''
window.pywebview = { api: {
  stop_plan: () => Promise.resolve({ ok: false, text: "当前没有这个计划" }),
  bootstrap: () => Promise.resolve({ busy: false }) } };
running("2026-11-06 16:00:00");
doStopPlan(); await flush(); render(); out.push({ logs: S.recentLogs.join("|"), busy: S.busy });
''')[0]
        self.assertNotIn("停止没成功，计划继续运行", data["logs"])
        self.assertNotIn("计划已经结束，修改作废", data["logs"])
        self.assertIn("当前没有这个计划", data["logs"])
        self.assertFalse(data["busy"])

# ==================== 源自 test_ui_plan_board.py ====================
"""计划栏认状态、认按钮和任务卡的行为测试。

@author Author
"""


TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))



BOARD_PRELUDE = r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
S.terms.acceptedVersion = "v1"; S.demo = true; S.online = true;
S.band = "narrow";
const mk = (id, name, extra) => Object.assign({ id: id, name: name,
  place: "学生公寓", signed: false, checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
const load = (items) => window.onBackend.activities({ ok: true, items: items });
'''


class PlanBoardBehaviorTests(unittest.TestCase):
    # 没选活动但有当前开放场次时，计划栏给出选场入口，选中后才显示可开始的计划。
    def test_empty_board_offers_pick_and_selected_board_offers_start(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "开放活动", { sign_start: "2026-11-06 13:00:00" })]);
render();
const empty = { pickHidden: $("#btn-board-pick").hidden,
  why: $("#plan-why").textContent, startDisabled: $("#btn-plan").disabled };
S.selected.add("a1"); render();
out.push({ empty, selected: { title: $("#selected").textContent,
  startDisabled: $("#btn-plan").disabled } });
''')[0]
        self.assertFalse(data["empty"]["pickHidden"])
        self.assertIn("先在时刻表勾选活动", data["empty"]["why"])
        self.assertTrue(data["empty"]["startDisabled"])
        self.assertEqual(data["selected"]["title"], "已选 1 场")
        self.assertFalse(data["selected"]["startDisabled"])

    # 运行中等待开放时，标题和任务卡都表达等待，用户仍能取消未提交的场次。
    def test_waiting_plan_shows_waiting_target_and_cancel_action(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "未来活动")]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "未来活动",
  status: "waiting", sign_start: "2026-11-07 09:00:00", attempts: 0 });
render();
out.push({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  cancel: $("#plan-tasks").textContent, runActions: $("#run-actions").hidden });
''')[0]
        self.assertEqual(data["tag"], "等开放")
        self.assertEqual(data["title"], "未来活动")
        self.assertIn("取消这一场", data["cancel"])
        self.assertFalse(data["runActions"])

    # 距离开放五秒内，运行标题从等待开放改成即将开放，避免用户错过临界窗口。
    def test_waiting_plan_turns_to_soon_inside_five_seconds(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "临近活动", { sign_start: "2026-11-06 14:00:04" })]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "临近活动",
  status: "waiting", sign_start: "2026-11-06 14:00:04", attempts: 0 });
render(); out.push({ tag: $("#board-tag-text").textContent,
  title: $("#selected").textContent });
''')[0]
        self.assertEqual(data["tag"], "即将开放")
        self.assertEqual(data["title"], "临近活动")

    # 计划在等待开放且登录失效时，来得及时显示重新登录，进入一百秒窗口后修改被禁用。
    def test_login_failure_warning_and_modify_gate_follow_open_window(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "未来活动", { sign_start: "2026-11-06 14:20:00" })]);
S.demo = false; S.login.present = true; S.login.ok = false; S.login.result = "expired";
S.login.view = { state: "bad" }; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "未来活动",
  status: "waiting", sign_start: "2026-11-06 14:20:00", attempts: 0 });
render();
const timely = { warning: $("#run-warn").textContent, modify: $("#btn-modify").disabled };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 19, 0)); render();
out.push({ timely, late: { warning: $("#run-warn").textContent,
  modify: $("#btn-modify").disabled, why: $("#modify-why").textContent } });
''')[0]
        self.assertIn("重新登录", data["timely"]["warning"])
        self.assertFalse(data["timely"]["modify"])
        self.assertIn("来不及重新登录", data["late"]["warning"])
        self.assertTrue(data["late"]["modify"])
        self.assertIn("100 秒内开放", data["late"]["why"])

    # 修改草稿时，详情说明写出已结束场次和最近开放倒计时，运行重新开始后说明消失。
    def test_edit_note_is_visible_only_for_the_editing_draft(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "未来活动", { sign_start: "2026-11-06 14:04:00" })]);
S.selected.add("a1"); S.editing = { ids: ["a1"], doneN: 2 }; render();
const editing = { hidden: $("#edit-note").hidden, text: $("#edit-note").textContent };
S.editing = null; render();
out.push({ editing, after: { hidden: $("#edit-note").hidden,
  text: $("#edit-note").textContent } });
''')[0]
        self.assertFalse(data["editing"]["hidden"])
        self.assertIn("已结束的 2 场不受影响", data["editing"]["text"])
        self.assertIn("离最近一场开放只剩", data["editing"]["text"])
        self.assertTrue(data["after"]["hidden"])
        self.assertEqual(data["after"]["text"], "")

    # 结果页只给可重报的失败场次重新选择，完成按钮回到普通草稿。
    def test_result_actions_reselect_only_eligible_tasks(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "可重报", { sign_start: "2026-11-07 09:00:00" }),
  mk("a2", "已满", { sign_start: "2026-11-07 09:00:00" }),
  mk("a3", "待核对", { sign_start: "2026-11-07 09:00:00" })]);
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "可重报", status: "failed" });
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "已满", status: "failed", stop_reason: "full" });
S.plan.tasks.set("t3", { task_id: "t3", activity_id: "a3", name: "待核对", status: "failed", stop_reason: "unconfirmed" });
S.busy = false; openResultPage(); render();
const result = { actionsHidden: $("#result-actions").hidden, reselectHidden: $("#btn-reselect").hidden,
  stats: $("#plan-stats").textContent };
reselectFailed();
out.push({ result, after: { selected: Array.from(S.selected), editing: S.editing || null,
  resultOpen: S.resultOpen } });
''')[0]
        self.assertFalse(data["result"]["actionsHidden"])
        self.assertFalse(data["result"]["reselectHidden"])
        self.assertIn("报名未成功", data["result"]["stats"])
        self.assertEqual(data["after"]["selected"], ["a1"])
        self.assertIsNone(data["after"]["editing"])
        self.assertFalse(data["after"]["resultOpen"])

    # 计划运行时待核对场次不提供重发，只给刷新核对；草稿态才显示该按钮。
    def test_unconfirmed_task_switches_from_cancel_to_verify(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "活动甲")]);
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "failed", stop_reason: "unconfirmed", attempts: 1 });
S.busy = false; openResultPage(); render();
out.push({ html: $("#plan-tasks").textContent, verify: $("#plan-tasks").textContent.includes("刷新核对") });
''')[0]
        self.assertTrue(data["verify"])
        self.assertIn("刷新核对", data["html"])
        self.assertNotIn("取消这一场", data["html"])

    # 任务卡把自动登录等待、准备提交和已提交次数分别写成用户可读说明。
    def test_task_cards_explain_login_wait_and_submission_phase(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "活动甲", { sign_start: "2026-11-06 13:00:00" })]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "waiting", sign_start: "2026-11-06 13:00:00", login_wait: "waiting", attempts: 0 });
render(); const login = $("#plan-tasks").textContent;
S.plan.tasks.get("t1").login_wait = ""; S.plan.tasks.get("t1").status = "submitting";
S.plan.tasks.get("t1").attempts = 2; S.plan.tasks.get("t1").max_attempts = 3; render();
out.push({ login, submitting: $("#plan-tasks").textContent });
''')[0]
        self.assertIn("电脑正在自动登录", data["login"])
        self.assertIn("提交中", data["submitting"])
        self.assertIn("已提交 2 次", data["submitting"])

    # 预报名任务已有页面或监测 checkpoint 时，任务卡写已准备好而不是继续等待。
    def test_prepared_task_uses_checkpoint_in_visible_detail(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "已准备活动", { sign_start: "2026-11-06 14:30:00" })]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "已准备活动",
  status: "waiting", sign_start: "2026-11-06 14:30:00", page_opened_at: bnowS() });
render(); out.push({ detail: $("#plan-tasks").textContent });
''')[0]
        self.assertIn("已准备好", data["detail"])
    # 没登录过的新用户打开时，大屏先说「登录后开始」，不摆空列表的结论。
    def test_first_use_board_invites_login(self):
        data = run_js(BOARD_PRELUDE + r'''
S.demo = false; S.login.present = false; S.login.result = "none";
S.login.view = { state: "none" };
S.items = []; S.byId = new Map(); S.selected = new Set(); S.listState = "ready";
render();
out.push({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent });
''')[0]
        self.assertEqual(data["tag"], "首次使用")
        self.assertEqual(data["title"], "登录后开始")
        self.assertEqual(data["text"], "活动会在登录完成后自动加载。")

    # 登录窗口还开着时大屏说「登录中」；组件缺失、列表失败、正在加载各有自己的短状态。
    def test_board_names_login_component_error_and_loading_states(self):
        data = run_js(BOARD_PRELUDE + r'''
const look = () => ({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent });
S.login.loginPending = true; render(); const loginPending = look();
S.login.loginPending = false; S.runtime.error = "missing"; S.listState = "idle"; render();
const component = look();
S.runtime.error = null; S.listState = "error"; render(); const listError = look();
S.listState = "loading"; render(); const loading = look();
out.push({ loginPending, component, listError, loading });
''')[0]
        self.assertEqual(data["loginPending"]["tag"], "登录中")
        self.assertEqual(data["loginPending"]["title"], "正在打开登录窗口")
        self.assertEqual(data["loginPending"]["text"],
                         "在浏览器里登完再回来；中途关掉窗口会保留原来的登录状态。")
        self.assertEqual(data["component"]["tag"], "不可用")
        self.assertEqual(data["component"]["title"], "暂时不能报名")
        self.assertIn("顶部提示", data["component"]["text"])
        self.assertEqual(data["listError"]["tag"], "需重试")
        self.assertEqual(data["listError"]["title"], "活动暂时没加载")
        self.assertIn("左边列表", data["listError"]["text"])
        self.assertEqual(data["loading"]["tag"], "加载中")
        self.assertEqual(data["loading"]["title"], "活动列表正在加载")
        self.assertIn("先等这一次加载结束", data["loading"]["text"])

    # 没有可报目标时，大屏按「学校没活动 / 没有可报场次 / 列表还没到 / 时间待校准」分开说。
    def test_empty_board_separates_school_empty_from_no_target(self):
        data = run_js(BOARD_PRELUDE + r'''
const look = () => ({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent });
const item = (extra) => Object.assign({ id: "a1", name: "已报场", place: "学生公寓",
  signed: true, checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
S.demo = false; S.listState = "ready"; S.items = []; S.byId = new Map();
S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; render(); const schoolEmpty = look();
S.items = [item()]; S.byId = new Map([["a1", S.items[0]]]); render(); const noTarget = look();
S.listState = "idle"; render(); const notReady = look();
S.listState = "ready"; const realNow = businessNowMs;
businessNowMs = () => null; render(); const noClock = look();
businessNowMs = realNow;
out.push({ schoolEmpty, noTarget, notReady, noClock });
''')[0]
        self.assertEqual(data["schoolEmpty"]["title"], "学校当前没有活动")
        self.assertIn("稍后刷新", data["schoolEmpty"]["text"])
        self.assertEqual(data["noTarget"]["title"], "没有可报名的场次")
        self.assertIn("已报名、已截止或还没公布报名时间", data["noTarget"]["text"])
        self.assertEqual(data["notReady"]["title"], "近期没有要开放的活动")
        self.assertEqual(data["noClock"]["tag"], "时间待校准")
        self.assertEqual(data["noClock"]["text"],
                         "校准北京时间后才能判断哪些场次可以报名。查看时间详情")

    # 条款没同意时大屏先停用报名，未确认与从未同意各说各的。
    def test_terms_hold_board_stops_at_terms_before_selection(self):
        data = run_js(BOARD_PRELUDE + r'''
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" };
S.items = []; S.byId = new Map(); S.selected = new Set(); S.listState = "ready";
S.terms.acceptedVersion = ""; render();
const locked = { tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent };
S.terms.unknown = true; render();
const unknown = { tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent };
out.push({ locked, unknown });
''')[0]
        self.assertEqual(data["locked"]["tag"], "已暂停")
        self.assertEqual(data["locked"]["title"], "同意条款后才能报名")
        self.assertIn("帮助和设置照常可用", data["locked"]["text"])
        self.assertEqual(data["unknown"]["tag"], "已暂停")
        self.assertEqual(data["unknown"]["title"], "重新确认条款后才能报名")
        self.assertIn("暂时停用", data["unknown"]["text"])

    # 空选时大屏先指当前开放场（「开放中」），没有才指下一场（「下一场」）。
    def test_empty_selection_board_points_at_open_then_next_activity(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = (id, name, extra) => Object.assign({ id: id, name: name, place: "学生公寓",
  signed: false, checkin_required: false, checkout_required: false,
  sign_start: "2026-11-06 13:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
S.items = [item("a1", "马上能报")]; S.byId = new Map([["a1", S.items[0]]]); render();
const openNow = { tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  meta: $("#selected-meta").innerHTML };
S.items = [item("a2", "明天开放", { sign_start: "2026-11-07 09:00:00" })];
S.byId = new Map([["a2", S.items[0]]]); render();
const next = { tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  meta: $("#selected-meta").innerHTML };
out.push({ openNow, next });
''')[0]
        self.assertEqual(data["openNow"]["tag"], "开放中")
        self.assertEqual(data["openNow"]["title"], "马上能报")
        self.assertIn("学生公寓", data["openNow"]["meta"])
        self.assertEqual(data["next"]["tag"], "下一场")
        self.assertEqual(data["next"]["title"], "明天开放")
        self.assertIn("学生公寓", data["next"]["meta"])
    # 开始按钮禁用时，「还差一步」逐条说清缺什么，并给一个就地能点的动作。
    def test_start_blocker_names_each_missing_step_with_its_action(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = (id, name) => ({ id: id, name: name, place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" });
const look = () => ({ why: $("#plan-why").textContent, disabled: $("#btn-plan").disabled });
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.items = []; S.byId = new Map(); S.selected = new Set();
S.listState = "ready"; render(); const blank = look();
S.runtime.error = "missing"; render(); const component = look();
S.runtime.error = null; S.cancel.busyId = "a1"; render(); const cancelBusy = look();
S.cancel.busyId = null; S.terms.acceptedVersion = ""; render(); const terms = look();
S.terms.acceptedVersion = "v1"; S.login.present = false; S.login.view = { state: "none" };
S.login.result = "none"; render(); const notLogged = look();
S.login.present = true; S.login.ok = false; S.login.result = "expired";
S.login.view = { state: "bad" }; render(); const expired = look();
S.login.result = "unknown"; S.login.view = { state: "unknown" }; render(); const unknown = look();
S.login.result = "valid"; S.login.view = { state: "checking" }; S.login.checking = true;
render(); const checking = look();
S.login.checking = false; S.login.view = { state: "ok" }; S.login.ok = true;
S.login.result = "valid"; S.items = [item("a1", "活动甲")];
S.byId = new Map([["a1", S.items[0]]]); render(); const noSelection = look();
S.selected = new Set(["a1"]); S.items = [item("a1", "活动甲"), item("a2", "活动乙")];
S.byId = new Map([["a1", S.items[0]], ["a2", S.items[1]]]);
S.selected = new Set(["a1", "a2"]); render(); const conflict = look();
out.push({ blank, component, cancelBusy, terms, notLogged, expired, unknown, checking,
  noSelection, conflict });
''')[0]
        self.assertTrue(data["blank"]["disabled"])
        self.assertIn("学校还没有可选的活动", data["blank"]["why"])
        self.assertIn("刷新", data["blank"]["why"])
        self.assertIn("程序组件缺失", data["component"]["why"])
        self.assertIn("正在取消报名", data["cancelBusy"]["why"])
        self.assertIn("先同意使用条款", data["terms"]["why"])
        self.assertIn("查看条款", data["terms"]["why"])
        self.assertIn("还没有登录", data["notLogged"]["why"])
        self.assertIn("去登录", data["notLogged"]["why"])
        self.assertIn("登录已失效", data["expired"]["why"])
        self.assertIn("重新登录", data["expired"]["why"])
        self.assertIn("登录状态还没确认", data["unknown"]["why"])
        self.assertIn("刷新", data["unknown"]["why"])
        self.assertIn("登录状态还没确认", data["checking"]["why"])
        self.assertNotIn("刷新", data["checking"]["why"])
        self.assertIn("先在时刻表勾选活动", data["noSelection"]["why"])
        self.assertIn("已选场次有问题", data["conflict"]["why"])

    # 开始按钮的字样跟运行阶段走：提交中、运行中、修改中、有时间待校准各说一句。
    def test_start_and_stop_buttons_follow_the_run_phase(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = { id: "a1", name: "活动甲", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-06 14:30:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" };
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.items = [normalize(item)];
S.byId = new Map([["a1", S.items[0]]]); S.selected = new Set(["a1"]);
S.listState = "ready"; render();
const idle = { start: $("#btn-plan").textContent, disabled: $("#btn-plan").disabled,
  stop: $("#btn-stop").textContent, stopDisabled: $("#btn-stop").disabled };
S.starting = true; render(); const starting = { start: $("#btn-plan").textContent,
  disabled: $("#btn-plan").disabled };
S.starting = false; S.editing = { ids: ["a1"], doneN: 0 }; render();
const editing = { start: $("#btn-plan").textContent, tag: $("#board-tag-text").textContent };
S.editing = null; const realNow = businessNowMs; businessNowMs = () => null; render();
const noClock = { start: $("#btn-plan").textContent, disabled: $("#btn-plan").disabled };
businessNowMs = realNow; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "waiting", sign_start: "2026-11-06 14:30:00" });
render(); const running = { start: $("#btn-plan").textContent,
  stopDisabled: $("#btn-stop").disabled, actions: $("#run-actions").hidden };
S.stopping = true; render(); const stopping = { stop: $("#btn-stop").textContent };
out.push({ idle, starting, editing, noClock, running, stopping });
''')[0]
        self.assertEqual(data["idle"]["start"], "开始报名计划")
        self.assertFalse(data["idle"]["disabled"])
        self.assertEqual(data["idle"]["stop"], "停止计划")
        self.assertTrue(data["idle"]["stopDisabled"])
        self.assertEqual(data["starting"]["start"], "正在提交…")
        self.assertTrue(data["starting"]["disabled"])
        self.assertEqual(data["editing"]["start"], "重新开始计划")
        self.assertEqual(data["editing"]["tag"], "修改中")
        self.assertEqual(data["noClock"]["start"], "北京时间未校准")
        self.assertTrue(data["noClock"]["disabled"])
        self.assertEqual(data["running"]["start"], "计划运行中")
        self.assertFalse(data["running"]["stopDisabled"])
        self.assertFalse(data["running"]["actions"])
        self.assertEqual(data["stopping"]["stop"], "正在停止…")

    # 空选且列表已加载时给「选这一场」；有选中才给「清空」，运行中两者都收。
    def test_pick_and_clear_controls_follow_selection_and_run_state(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = { id: "a1", name: "活动甲", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-06 13:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" };
S.items = [normalize(item)]; S.byId = new Map([["a1", S.items[0]]]);
S.selected = new Set(); S.listState = "ready"; render();
const empty = { pick: $("#btn-board-pick").hidden, clear: $("#btn-clear-plan").hidden,
  actions: $("#route-actions").hidden };
S.selected = new Set(["a1"]); render();
const picked = { pick: $("#btn-board-pick").hidden, clear: $("#btn-clear-plan").hidden };
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "waiting", sign_start: "2026-11-06 13:00:00" });
render(); const running = { pick: $("#btn-board-pick").hidden,
  clear: $("#btn-clear-plan").hidden, actions: $("#route-actions").hidden };
out.push({ empty, picked, running });
''')[0]
        self.assertFalse(data["empty"]["pick"])
        self.assertTrue(data["empty"]["clear"])
        self.assertFalse(data["empty"]["actions"])
        self.assertTrue(data["picked"]["pick"])
        self.assertFalse(data["picked"]["clear"])
        self.assertTrue(data["running"]["pick"])
        self.assertTrue(data["running"]["clear"])
        self.assertTrue(data["running"]["actions"])
    # 每场结束时任务卡写人话：名额已满、未提交、待核对、已取消、报名成功各一句。
    def test_task_card_writes_each_outcome_in_plain_words(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "活动甲")]);
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.busy = true;
const card = (extra) => {
  S.plan.tasks.clear();
  S.plan.tasks.set("t1", Object.assign({ task_id: "t1", activity_id: "a1", name: "活动甲",
    status: "failed", attempts: 2 }, extra));
  render();
  return $("#plan-tasks").textContent;
};
const full = card({ stop_reason: "full" });
const loginInvalid = card({ stop_reason: "login_invalid" });
const maxed = card({ stop_reason: "max_attempts" });
const authUnavailable = card({ stop_reason: "auth_unavailable" });
const unconfirmed = card({ stop_reason: "unconfirmed" });
const unknownReply = card({ stop_reason: "unknown_reply" });
const canceled = card({ status: "canceled" });
const success = card({ status: "success", last_reason: "报名成功。" });
S.plan.status = "stopped";
const stoppedCanceled = card({ status: "canceled" });
out.push({ full, loginInvalid, maxed, authUnavailable, unconfirmed, unknownReply,
  canceled, success, stoppedCanceled });
''')[0]
        self.assertIn("名额已满", data["full"])
        self.assertIn("不是工具出错", data["full"])
        self.assertIn("已提交 2 次", data["full"])
        self.assertIn("报名未成功", data["loginInvalid"])
        self.assertIn("登录失效，先重新登录", data["loginInvalid"])
        self.assertIn("达到最大提交次数", data["maxed"])
        self.assertIn("未提交", data["authUnavailable"])
        self.assertIn("登录状态无法确认", data["authUnavailable"])
        self.assertIn("待核对", data["unconfirmed"])
        self.assertIn("没拿到确定回应", data["unconfirmed"])
        self.assertIn("不会再自动重发", data["unconfirmed"])
        self.assertIn("学校回了无法识别的结果", data["unknownReply"])
        self.assertIn("已取消", data["canceled"])
        self.assertIn("你取消了这一场", data["canceled"])
        self.assertIn("报名成功", data["success"])
        self.assertIn("学校回“报名成功”", data["success"])
        self.assertIn("计划已停止，这一场没有提交", data["stoppedCanceled"])

    # 结果页与整屏外框按结论分开：只有待核对说「需确认」，全失败说「没有成功」。
    def test_result_page_distinguishes_pending_from_total_failure(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "活动甲")]);
const page = (tasks, status) => {
  S.plan = { id: "p1", status: status, tasks: new Map() };
  tasks.forEach((task) => S.plan.tasks.set(task.task_id, task));
  S.busy = false; openResultPage(); render();
  return { tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
    text: $("#board-text").textContent, frame: $("#board").dataset.planState,
    stats: $("#plan-stats").textContent };
};
const pending = page([{ task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "failed", stop_reason: "unconfirmed" }], "completed");
const failed = page([{ task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "failed", stop_reason: "max_attempts" }], "failed");
const partial = page([{ task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" },
  { task_id: "t2", activity_id: "a1", name: "活动甲", status: "failed" }], "partial");
out.push({ pending, failed, partial });
''')[0]
        self.assertEqual(data["pending"]["tag"], "需确认")
        self.assertIn("需确认", data["pending"]["title"])
        self.assertIn("到学校活动页核对", data["pending"]["text"])
        self.assertEqual(data["pending"]["frame"], "attention")
        self.assertIn("待核对", data["pending"]["stats"])
        self.assertEqual(data["failed"]["tag"], "未成功")
        self.assertEqual(data["failed"]["title"], "报名计划没有成功")
        self.assertEqual(data["failed"]["frame"], "failed")
        self.assertIn("报名未成功", data["failed"]["stats"])
        self.assertEqual(data["partial"]["tag"], "部分完成")
        self.assertEqual(data["partial"]["frame"], "partial")
        self.assertIn("已报名", data["partial"]["stats"])
        self.assertIn("报名未成功", data["partial"]["stats"])
    # 忙态、条款、缓存列表三件事同时成立时，大屏只报最该报的那一条。
    def test_board_keeps_busy_terms_and_cached_list_apart(self):
        data = run_js(BOARD_PRELUDE + r'''
const put = (items) => { S.items = items.map((x) => normalize(x));
  S.byId = new Map(S.items.map((i) => [String(i.id), i])); };
const look = () => ({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  text: $("#board-text").textContent });
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.items = []; S.byId = new Map(); S.selected = new Set();
S.listState = "ready"; S.runtime.error = null;
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.login.present = false; S.login.view = { state: "none" }; render(); const busyFirstUse = look();
S.busy = false; S.plan = { id: null, status: "idle", tasks: new Map() };
S.terms.acceptedVersion = ""; S.runtime.error = "missing"; S.listState = "idle";
render(); const termsVsComponent = look();
S.runtime.error = null; S.listState = "ready"; S.login.present = true;
S.login.view = { state: "ok" }; put([mk("a1", "活动甲")]);
S.selected = new Set(["a1"]); render(); const termsWithSelection = look();
S.terms.acceptedVersion = "v1"; S.runtime.error = "missing"; put([]); S.selected = new Set();
render(); const componentReadyList = look();
S.runtime.error = null; put([mk("a1", "活动甲")]); S.listState = "error"; render();
const errorWithCache = look();
S.listState = "loading"; render(); const loadingWithSelection = look();
S.listState = "ready"; S.selected = new Set(["a1"]); render();
S.listState = "loading"; render(); const loadingAndSelected = look();
S.listState = "ready"; S.selected = new Set();
out.push({ busyFirstUse, termsVsComponent, termsWithSelection, componentReadyList,
  errorWithCache, loadingWithSelection, loadingAndSelected });
''')[0]
        self.assertEqual(data["busyFirstUse"]["tag"], "准备中")
        self.assertEqual(data["busyFirstUse"]["title"], "正在准备报名")
        self.assertEqual(data["termsVsComponent"]["tag"], "不可用")
        self.assertEqual(data["termsVsComponent"]["title"], "暂时不能报名")
        self.assertEqual(data["termsWithSelection"]["tag"], "已暂停")
        self.assertEqual(data["termsWithSelection"]["title"], "已选 1 场")
        self.assertIn("预报名等开放", data["termsWithSelection"]["text"])
        self.assertEqual(data["componentReadyList"]["title"], "学校当前没有活动")
        self.assertEqual(data["errorWithCache"]["tag"], "下一场")
        self.assertEqual(data["errorWithCache"]["title"], "活动甲")
        self.assertEqual(data["loadingWithSelection"]["tag"], "加载中")
        self.assertEqual(data["loadingAndSelected"]["tag"], "报名计划")
        self.assertEqual(data["loadingAndSelected"]["title"], "已选 1 场")

    # 运行中按阶段换标签颜色与副行：提交中是红的，汇总与准备各说一句。
    def test_running_board_uses_tone_and_caption_for_each_phase(self):
        data = run_js(BOARD_PRELUDE + r'''
const look = () => ({ tag: $("#board-tag-text").textContent, tone: $("#board-tag").dataset.tone,
  title: $("#selected").textContent, text: $("#board-text").textContent });
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "提交场",
  status: "submitting", attempts: 1, sign_start: "2026-11-06 13:00:00", run_started_at: 1 });
render(); const submitting = look();
S.plan.tasks.clear();
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "结束场",
  status: "success", sign_start: "2026-11-06 13:00:00" }); render(); const settling = look();
S.plan.tasks.clear(); render(); const preparing = look();
out.push({ submitting, settling, preparing });
''')[0]
        self.assertEqual(data["submitting"]["tag"], "正在提交")
        self.assertEqual(data["submitting"]["tone"], "red")
        self.assertEqual(data["submitting"]["title"], "提交场")
        self.assertIn("已提交 1 次", data["submitting"]["text"])
        self.assertEqual(data["settling"]["tag"], "汇总中")
        self.assertEqual(data["settling"]["title"], "正在汇总结果")
        self.assertEqual(data["settling"]["text"], "每一场都结束了，正在汇总这一轮的结果。")
        self.assertEqual(data["preparing"]["tag"], "准备中")
        self.assertEqual(data["preparing"]["title"], "正在准备报名")
        self.assertEqual(data["preparing"]["text"], "计划已经接管，正在核对每一场的开放时间。")
    # 计划跑起来以后，大屏不再退回条款、组件、列表这些草稿态的说法。
    def test_running_board_never_falls_back_to_draft_states(self):
        data = run_js(BOARD_PRELUDE + r'''
const put = (items) => { S.items = items.map((x) => normalize(x));
  S.byId = new Map(S.items.map((i) => [String(i.id), i])); };
const look = () => ({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent });
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.items = []; S.byId = new Map(); S.selected = new Set();
S.listState = "ready"; S.runtime.error = null; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.terms.acceptedVersion = ""; render(); const termsLocked = look();
S.terms.acceptedVersion = "v1"; S.runtime.error = "missing"; S.listState = "idle";
render(); const component = look();
S.runtime.error = null; S.listState = "error"; render(); const listError = look();
S.listState = "loading"; render(); const loading = look();
S.busy = false; S.plan = { id: null, status: "idle", tasks: new Map() };
S.demo = true; S.listState = "ready"; put([mk("a1", "已报", { signed: true })]);
const realNow = businessNowMs; businessNowMs = () => null; render();
const demoNoClock = look(); businessNowMs = realNow;
out.push({ termsLocked, component, listError, loading, demoNoClock });
''')[0]
        self.assertEqual(data["termsLocked"]["tag"], "准备中")
        self.assertNotIn("已暂停", data["termsLocked"]["tag"])
        self.assertEqual(data["component"]["tag"], "准备中")
        self.assertNotIn("不可用", data["component"]["tag"])
        self.assertEqual(data["listError"]["tag"], "准备中")
        self.assertNotIn("需重试", data["listError"]["tag"])
        self.assertEqual(data["loading"]["tag"], "准备中")
        self.assertNotIn("加载中", data["loading"]["tag"])
        self.assertEqual(data["demoNoClock"]["title"], "没有可报名的场次")
        self.assertNotIn("时间待校准", data["demoNoClock"]["tag"])
    # 登录、刷新、清空三个按钮各自的门禁：忙、缺组件、条款、加载、取消中。
    def test_controls_disable_login_refresh_and_clear_at_their_own_gates(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = { id: "a1", name: "活动甲", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" };
const put = () => { S.items = [normalize(item)]; S.byId = new Map([["a1", S.items[0]]]); };
const look = () => ({ login: $("#btn-login").disabled, refresh: $("#btn-refresh").disabled,
  clear: $("#btn-clear-plan").disabled });
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.runtime.error = null; S.listState = "ready";
S.busy = false; S.starting = false; S.cancel = { busyId: null };
S.plan = { id: null, status: "idle", tasks: new Map() }; S.selected = new Set(); put();
updateControls(); const ready = look();
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
updateControls(); const busy = look();
S.busy = false; S.plan = { id: null, status: "idle", tasks: new Map() };
S.runtime.error = "missing"; updateControls(); const component = look();
S.runtime.error = null; S.terms.acceptedVersion = ""; updateControls(); const terms = look();
S.terms.acceptedVersion = "v1"; S.listState = "loading"; updateControls(); const loading = look();
S.listState = "ready"; S.cancel.busyId = "a1"; updateControls(); const canceling = look();
S.cancel.busyId = null; S.selected = new Set(["a1"]); S.starting = true; updateControls();
const starting = look();
S.starting = false; updateControls(); const selected = look();
out.push({ ready, busy, component, terms, loading, canceling, starting, selected });
''')[0]
        self.assertFalse(data["ready"]["login"])
        self.assertFalse(data["ready"]["refresh"])
        self.assertTrue(data["ready"]["clear"], "没选活动时清空按钮不该出现")
        self.assertTrue(data["busy"]["login"], "计划运行中不允许再开登录窗口")
        self.assertTrue(data["busy"]["clear"])
        self.assertTrue(data["component"]["login"], "缺组件时登录按钮应禁用")
        self.assertTrue(data["terms"]["login"])
        self.assertTrue(data["terms"]["refresh"])
        self.assertTrue(data["loading"]["refresh"])
        self.assertTrue(data["canceling"]["refresh"], "正在取消报名时刷新要让开")
        self.assertTrue(data["starting"]["clear"], "正在提交时不许清空选择")
        self.assertFalse(data["selected"]["clear"])

    # 停止按钮与停止确认弹层：没计划时禁用，停止中写「正在停止」，计划结束后弹层收起并把焦点交出去。
    def test_stop_button_and_stop_ask_follow_the_plan(self):
        data = run_js(BOARD_PRELUDE + r'''
const look = () => ({ stop: $("#btn-stop").textContent, disabled: $("#btn-stop").disabled,
  ask: $("#plan-stop-ask").hidden });
S.busy = false; S.stopping = false; S.plan = { id: null, status: "idle", tasks: new Map() };
updateControls(); const noPlan = look();
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
updateControls(); const running = look();
S.stopping = true; updateControls(); const stopping = look();
S.stopping = false;
$("#plan-stop-ask").hidden = false;
$("#btn-stop-yes").id = "btn-stop-yes";
document.activeElement = $("#btn-stop-yes");
S.busy = false; S.plan = { id: "p1", status: "stopped", tasks: new Map() };
focused.length = 0; updateControls();
out.push({ noPlan, running, stopping,
  after: { ask: $("#plan-stop-ask").hidden, focused: focused.slice() } });
''')[0]
        self.assertEqual(data["noPlan"]["stop"], "停止计划")
        self.assertTrue(data["noPlan"]["disabled"])
        self.assertFalse(data["running"]["disabled"])
        self.assertEqual(data["stopping"]["stop"], "正在停止…")
        self.assertTrue(data["stopping"]["disabled"])
        self.assertTrue(data["after"]["ask"], "计划结束后停止确认弹层要收起")
        self.assertEqual(data["after"]["focused"], ["#board"],
                         "结果页没开时焦点落回大屏，而不是看不见的「完成」")
    # 运行中登录失效：电脑自动登录时只说明，来不及才说这一批会结束，来得及给重新登录。
    def test_run_warning_explains_auto_login_and_both_relogin_windows(self):
        data = run_js(BOARD_PRELUDE + r'''
S.demo = false; S.login.present = true; S.login.ok = false; S.login.result = "expired";
S.login.view = { state: "bad" }; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
const put = (task) => { S.plan.tasks.clear(); S.plan.tasks.set("t1", Object.assign(
  { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting" }, task));
  render(); return { warn: $("#run-warn").textContent, hidden: $("#run-warn").hidden,
    hint: $("#plan-hint").textContent, modify: $("#btn-modify").disabled,
    why: $("#modify-why").textContent }; };
const autoSubmitting = put({ status: "submitting", attempts: 1,
  login_wait: "waiting", sign_start: "2026-11-06 13:00:00" });
S.busy = true; S.plan.tasks.clear();
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
  login_wait: "waiting", sign_start: "2026-11-07 09:00:00" }); render();
const autoWaiting = { warn: $("#run-warn").textContent };
S.plan.tasks.clear();
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
  sign_start: "2026-11-07 09:00:00" }); render();
const timely = { warn: $("#run-warn").textContent, modify: $("#btn-modify").disabled };
S.plan.tasks.clear();
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "submitting",
  attempts: 1, sign_start: "2026-11-06 13:00:00" }); render();
const late = { warn: $("#run-warn").textContent, modify: $("#btn-modify").disabled,
  why: $("#modify-why").textContent };
S.plan.source = "phone"; S.plan.tasks.clear();
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
  sign_start: "2026-11-07 09:00:00" }); render();
const phone = { hint: $("#plan-hint").textContent };
out.push({ autoSubmitting, autoWaiting, timely, late, phone });
''')[0]
        self.assertIn("电脑正在自动登录（最多约 20 秒）", data["autoSubmitting"]["warn"])
        self.assertIn("成功后接着提交", data["autoSubmitting"]["warn"])
        self.assertIn("计划照常等开放，不用你管", data["autoWaiting"]["warn"])
        self.assertIn("只要在", data["timely"]["warn"])
        self.assertIn("重新登录", data["timely"]["warn"])
        self.assertFalse(data["timely"]["modify"])
        self.assertIn("来不及重新登录", data["late"]["warn"])
        self.assertIn("正在提交的场次", data["late"]["warn"])
        self.assertTrue(data["late"]["modify"])
        self.assertIn("正在提交，现在不能修改", data["late"]["why"])
        self.assertIn("可以最小化窗口", data["phone"]["hint"])
        self.assertIn("从手机开始的", data["phone"]["hint"])

    # 运行中只留「修改计划/停止计划」；草稿才摆检查条与开始按钮，修改中才给「放弃修改」。
    def test_board_actions_show_only_what_the_phase_allows(self):
        data = run_js(BOARD_PRELUDE + r'''
const item = { id: "a1", name: "活动甲", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" };
S.items = [normalize(item)]; S.byId = new Map([["a1", S.items[0]]]); S.selected = new Set();
const look = () => ({ actions: $("#route-actions").hidden, checks: $("#plan-checks").hidden,
  start: $("#btn-plan").hidden, restore: $("#btn-edit-restore").hidden,
  clear: $("#btn-clear-plan").hidden, pick: $("#btn-board-pick").hidden });
S.busy = false; S.plan = { id: null, status: "idle", tasks: new Map() };
$("#plan-checks").hidden = true; $("#btn-plan").hidden = true;
render(); const draft = look();
S.editing = { ids: [], doneN: 0 }; render(); const editing = look();
S.editing = null; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
render(); const running = look();
S.busy = false; S.plan = { id: "p1", status: "completed", tasks: new Map([
  ["t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" }]]) };
openResultPage(); render(); const result = look();
out.push({ draft, editing, running, result });
''')[0]
        self.assertFalse(data["draft"]["actions"], "草稿要看得到主按钮")
        self.assertFalse(data["draft"]["checks"], "草稿要把检查条放出来")
        self.assertFalse(data["draft"]["start"], "草稿要把开始按钮放出来")
        self.assertTrue(data["draft"]["restore"], "没在修改时不显示「放弃修改」")
        self.assertTrue(data["draft"]["pick"], "已选活动时不显示「选这一场」")
        self.assertFalse(data["editing"]["restore"], "修改中要显示「放弃修改」")
        self.assertTrue(data["running"]["actions"], "运行中收起草稿那排按钮")
        self.assertTrue(data["running"]["pick"])
        self.assertTrue(data["result"]["actions"], "结果页不摆开始按钮")
        self.assertTrue(data["result"]["clear"])
    # 刷新核对前后任务卡换说法；学校列表显示已报名就把标签改成「报名成功」。
    def test_verify_task_switches_the_card_wording(self):
        data = run_js(BOARD_PRELUDE + r'''
load([mk("a1", "活动甲")]);
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "failed", stop_reason: "unconfirmed", attempts: 1 });
S.busy = true; render(); const before = $("#plan-tasks").textContent;
S.busy = false; S.listState = "ready"; openResultPage();
verifyTask("t1"); render(); const after = $("#plan-tasks").textContent;
const asked = Array.from(S.verifyAsked);
S.items[0].signed = true; S.byId.set("a1", S.items[0]); render();
const verified = $("#plan-tasks").textContent;
S.plan.tasks.clear();
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a1", name: "活动甲" });
render(); const noStatus = $("#plan-tasks").textContent;
out.push({ before, after, asked, verified, noStatus });
''')[0]
        self.assertIn("待核对", data["before"])
        self.assertIn("刷新核对", data["after"])
        self.assertIn("学校列表还没显示已报名", data["after"])
        self.assertIn("刷新核对", data["before"] + data["after"])
        self.assertEqual(data["asked"], ["t1"], "点过刷新核对要把这一场记下来")
        self.assertIn("报名成功", data["verified"])
        self.assertIn("学校显示已报名", data["verified"])
        self.assertIn("排队", data["noStatus"], "缺状态字段的旧载荷按「排队」显示")
    # 列表被刷新掉或还没到时，大屏与任务卡用任务自带字段显示，不回退到别的活动。
    def test_board_falls_back_to_the_task_fields_without_a_list_item(self):
        data = run_js(BOARD_PRELUDE + r'''
load([]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
const look = (task) => { S.plan.tasks.clear(); S.plan.tasks.set("t1", Object.assign(
  { task_id: "t1", status: "waiting", sign_start: "2026-11-07 09:00:00" }, task));
  render(); return { title: $("#selected").textContent, card: $("#plan-tasks").textContent }; };
const named = look({ activity_id: "gone", name: "已不在列表的活动" });
const unnamed = look({ activity_id: "gone" });
const empty = look({});
out.push({ named, unnamed, empty });
''')[0]
        self.assertEqual(data["named"]["title"], "已不在列表的活动")
        self.assertIn("已不在列表的活动", data["named"]["card"])
        self.assertEqual(data["unnamed"]["title"], "这一场活动")
        self.assertEqual(data["empty"]["title"], "这一场活动")
    # 修改计划的门禁：没有可信时间、有场次在提交、离开放不到一百秒都改不了。
    def test_modify_gate_closes_on_each_late_condition(self):
        data = run_js(BOARD_PRELUDE + r'''
S.demo = false; S.login.present = true; S.login.ok = true; S.login.result = "valid";
S.login.view = { state: "ok" }; S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
const look = (task) => { S.plan.tasks.clear(); S.plan.tasks.set("t1", Object.assign(
  { task_id: "t1", activity_id: "a1", name: "活动甲" }, task));
  render(); return { modify: $("#btn-modify").disabled, why: $("#modify-why").textContent }; };
const far = look({ status: "waiting", sign_start: "2026-11-07 09:00:00" });
const near = look({ status: "waiting", sign_start: "2026-11-06 14:01:00" });
const submitting = look({ status: "submitting", attempts: 1, sign_start: "2026-11-06 13:00:00" });
const realNow = businessNowMs; businessNowMs = () => null;
const noClock = look({ status: "waiting", sign_start: "2026-11-07 09:00:00" });
businessNowMs = realNow;
out.push({ far, near, submitting, noClock });
''')[0]
        self.assertFalse(data["far"]["modify"], "离开放还早时可以修改")
        self.assertIn("可以放回草稿", data["far"]["why"])
        self.assertTrue(data["near"]["modify"], "离开放不到 100 秒时不能再改")
        self.assertIn("100 秒内开放", data["near"]["why"])
        self.assertTrue(data["submitting"]["modify"])
        self.assertIn("有场次正在提交", data["submitting"]["why"])
        self.assertTrue(data["noClock"]["modify"], "没有可信现在时不能修改")
        self.assertIn("100 秒内开放", data["noClock"]["why"])

# ==================== 源自 test_ui_plan_flow.py ====================
"""计划开始、对账、停止、修改和结果出口的行为测试。

@author Author
"""


TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))



FLOW_PRELUDE = r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
S.terms.acceptedVersion = "v1"; S.demo = true; S.online = true;
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
const mk = (id, name, extra) => Object.assign({ id: id, name: name,
  place: "学生公寓", signed: false, checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
  act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
const load = (items) => window.onBackend.activities({ ok: true, items: items });
'''


class PlanFlowBehaviorTests(unittest.TestCase):
    # 计划已经运行时焦点在页面上按回车，用户看不到失败结果，也不会再次发开始请求。
    def test_enter_during_running_plan_does_not_start_again(self):
        data = run_js(FLOW_PRELUDE + r'''
let starts = 0;
window.pywebview = { api: { start_plan: () => { starts += 1; return Promise.resolve({ ok: true }); } } };
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
render(); __dispatchKey({ key: "Enter" });
out.push({ result: $("#result").textContent, starts: starts,
  button: $("#btn-plan").textContent });
''')[0]
        self.assertEqual(data["button"], "计划运行中")
        self.assertEqual(data["result"], "")
        self.assertEqual(data["starts"], 0)

    # 已完成计划收到同计划迟到的运行事件时，用户仍看到结果态，忙标志不会复活。
    def test_late_same_plan_events_do_not_revive_terminal_plan(self):
        data = run_js(FLOW_PRELUDE + r'''
S.busy = false;
S.plan = { id: "p1", gen: 3, status: "completed", tasks: new Map([
  ["t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" }],
]) };
openResultPage(); render();
window.onBackend.plan({ plan_id: "p1", plan_generation: 3, status: "running", tasks: [] });
window.onBackend.task({ plan_id: "p1", plan_generation: 3, task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "waiting" });
render();
out.push({ title: $("#selected").textContent, button: $("#btn-plan").textContent,
  busy: S.busy, status: S.plan.status, resultOpen: S.resultOpen });
''')[0]
        self.assertIn("报名计划", data["title"])
        self.assertNotEqual(data["button"], "计划运行中")
        self.assertFalse(data["busy"])
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data["resultOpen"])

    # 开始桥接没有及时回话时，用户先看到提交中，再看到正在确认且不能重复开始。
    def test_start_timeout_enters_reconciliation_without_restarting(self):
        data = run_js(FLOW_PRELUDE + r'''
let starts = 0;
window.pywebview = { api: {
  start_plan: () => { starts += 1; return Promise.reject(new Error("没有回话")); },
  start_request_state: () => new Promise(() => {}),
} };
load([mk("a1", "活动甲")]); S.selected.add("a1");
startPlan(); const submitting = { text: $("#btn-plan").textContent, disabled: $("#btn-plan").disabled };
await flush();
out.push({ submitting, reconciling: { text: $("#result").textContent,
  button: $("#btn-plan").textContent, disabled: $("#btn-plan").disabled,
  starts: starts, state: S.startRequest.state } });
''')[0]
        self.assertEqual(data["submitting"]["text"], "正在提交…")
        self.assertTrue(data["submitting"]["disabled"])
        self.assertIn("正在确认是否启动", data["reconciling"]["button"] + data["reconciling"]["text"])
        self.assertTrue(data["reconciling"]["disabled"])
        self.assertEqual(data["reconciling"]["starts"], 1)
        self.assertEqual(data["reconciling"]["state"], "reconciling")

    # 对账失败时写结果未确认和重新确认入口，不能把启动按钮放回可点状态。
    def test_reconciliation_failure_leaves_visible_unknown_result(self):
        data = run_js(FLOW_PRELUDE + r'''
window.pywebview = { api: { start_request_state: () => Promise.reject(new Error("对账失败")) } };
S.startRequest = { id: "r1", state: "reconciling", timer: null, queryTimer: null, reconcile: 0, gen: 0 };
reconcileStart("r1"); await flush();
out.push({ result: $("#result").textContent, button: $("#btn-plan").textContent,
  disabled: $("#btn-plan").disabled, state: S.startRequest.state });
''')[0]
        self.assertIn("结果未确认，请勿重复启动", data["result"])
        self.assertIn("重新确认", data["result"])
        self.assertTrue(data["disabled"])
        self.assertEqual(data["state"], "unknown")

    # 停止被后端拒绝时，正在停止会收回，修改态也结束，运行记录说明计划仍在运行。
    def test_stop_rejection_clears_stopping_and_editing(self):
        data = run_js(FLOW_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.resolve({ ok: false, text: "暂时不能停" }) } };
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.editing = { ids: [], doneN: 0 }; doStopPlan();
const during = { text: $("#btn-stop").textContent, stopping: S.stopping };
await flush(); render();
out.push({ during, after: { text: $("#btn-stop").textContent, stopping: S.stopping,
  editing: S.editing, log: S.recentLogs.join("|") } });
''')[0]
        self.assertEqual(data["during"]["text"], "正在停止…")
        self.assertTrue(data["during"]["stopping"])
        self.assertEqual(data["after"]["text"], "停止计划")
        self.assertFalse(data["after"]["stopping"])
        self.assertIsNone(data["after"]["editing"])
        self.assertIn("停止没成功，计划继续运行", data["after"]["log"])

    # 停止成功后收到结束事件，按钮回到停止计划，结果页打开且不再保留忙态。
    def test_stop_success_waits_for_plan_done_before_result(self):
        data = run_js(FLOW_PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.resolve({ ok: true }) } };
S.busy = true; S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map() };
doStopPlan(); const during = { text: $("#btn-stop").textContent, busy: S.busy };
window.onBackend.plan_done({ plan_id: "p1", plan_generation: 1, status: "stopped", summary: {} });
render();
out.push({ during, after: { text: $("#btn-stop").textContent, busy: S.busy,
  resultOpen: S.resultOpen === true } });
''')[0]
        self.assertEqual(data["during"]["text"], "正在停止…")
        self.assertTrue(data["during"]["busy"])
        self.assertEqual(data["after"]["text"], "停止计划")
        self.assertFalse(data["after"]["busy"])
        self.assertTrue(data["after"]["resultOpen"])

    # 放弃修改前先恢复进入修改时的原计划场次，再发起新的开始请求。
    def test_restore_edited_plan_sends_original_selection(self):
        data = run_js(FLOW_PRELUDE + r'''
const calls = [];
window.pywebview = { api: { start_plan: (...args) => { calls.push(args); return Promise.resolve({ ok: false, text: "停在提交" }); } } };
load([mk("a1", "原计划"), mk("a2", "后来勾选")]);
S.selected.add("a2"); S.editing = { ids: ["a1"], doneN: 0 };
restoreEditedPlan(); await flush();
out.push({ selected: Array.from(S.selected), sent: calls.length ? calls[0][0].map((x) => x.id) : [],
  board: $("#selected").textContent });
''')[0]
        self.assertEqual(data["sent"], ["a1"])
        self.assertEqual(data["selected"], ["a1"])
        self.assertNotIn("修改中", data["board"])

    # 新代次计划事件可以接管旧计划，旧代次事件不能清掉当前运行态。
    def test_old_plan_event_cannot_replace_current_running_plan(self):
        data = run_js(FLOW_PRELUDE + r'''
S.busy = true; S.plan = { id: "new", gen: 5, status: "running", tasks: new Map() };
S.plan.tasks.set("new-task", { task_id: "new-task", name: "当前活动", status: "waiting" });
window.onBackend.plan({ plan_id: "old", plan_generation: 4, status: "stopped", tasks: [] });
render();
out.push({ id: S.plan.id, status: S.plan.status, busy: S.busy,
  task: S.plan.tasks.has("new-task"), title: $("#selected").textContent });
''')[0]
        self.assertEqual(data["id"], "new")
        self.assertEqual(data["status"], "running")
        self.assertTrue(data["busy"])
        self.assertTrue(data["task"])
        self.assertNotIn("报名计划已停止", data["title"])

    # 修改中计划自然结束时，修改作废，结果页显示新计划结论，不把旧场次放回选择。
    def test_natural_end_cancels_editing_and_opens_result(self):
        data = run_js(FLOW_PRELUDE + r'''
load([mk("a1", "活动甲")]); S.editing = { ids: ["a1"], doneN: 0 };
window.onBackend.plan({ plan_id: "p1", plan_generation: 2, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "活动甲", status: "failed" }] });
window.onBackend.plan_done({ plan_id: "p1", plan_generation: 2, status: "stopped", summary: {} });
render();
out.push({ editing: S.editing, selected: Array.from(S.selected), resultOpen: S.resultOpen === true,
  title: $("#selected").textContent });
''')[0]
        self.assertIsNone(data["editing"])
        self.assertEqual(data["selected"], [])
        self.assertTrue(data["resultOpen"])
        self.assertIn("报名计划已停止", data["title"])

    # 完成结果页清空选择并回到普通草稿，计划栏不再显示上一轮任务卡。
    def test_finish_result_returns_to_empty_draft(self):
        data = run_js(FLOW_PRELUDE + r'''
load([mk("a1", "活动甲")]); S.selected.add("a1");
S.plan = { id: "p1", status: "completed", tasks: new Map([
  ["t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" }],
]) };
openResultPage(); render(); finishResult(); render();
out.push({ resultOpen: S.resultOpen, selected: Array.from(S.selected),
  tasks: $("#plan-tasks").textContent, title: $("#selected").textContent });
''')[0]
        self.assertFalse(data["resultOpen"])
        self.assertEqual(data["selected"], [])
        self.assertEqual(data["tasks"], "")
        self.assertNotEqual(data["title"], "报名计划完成")
    # 登录窗口没能打开时把原因说出来并回滚，演示模式与组件缺失各走各的出口。
    def test_login_start_reports_failure_and_keeps_previous_session(self):
        data = run_js(FLOW_PRELUDE + r'''
const reset = () => { S.demo = false; S.busy = false; S.login.present = true;
  S.login.ok = true; S.login.result = "valid"; S.login.checking = false;
  S.login.loginPending = false; S.login.view = { state: "ok" };
  S.login.preLoginSnapshot = null; setResult(null); };
reset();
window.pywebview = { api: { login: () => Promise.resolve({ ok: false, text: "窗口没起来" }) } };
doLogin();
const pending = { board: $("#selected").textContent, pending: S.login.loginPending,
  busy: S.busy };
await flush();
const refused = { text: $("#result").textContent, pending: S.login.loginPending, busy: S.busy,
  result: S.login.result, present: S.login.present };
reset();
window.pywebview = { api: { login: () => Promise.reject(new Error("桥接断了")) } };
doLogin(); await flush();
const crashed = { text: $("#result").textContent, busy: S.busy };
reset(); S.demo = true;
window.pywebview = { api: { login: () => Promise.resolve({ demo: true, text: "演示模式不联网。" }) } };
doLogin(); await flush();
const demo = { text: $("#result").textContent, busy: S.busy };
reset();
window.pywebview = { api: { login: () => Promise.resolve({ ok: false, text: "x",
  error: "worker_missing" }) } };
doLogin(); await flush();
const component = { text: $("#result").textContent, banner: $("#banners").textContent,
  busy: S.busy };
out.push({ pending, refused, crashed, demo, component });
''')[0]
        self.assertEqual(data["pending"]["board"], "正在打开登录窗口")
        self.assertTrue(data["pending"]["pending"])
        self.assertTrue(data["pending"]["busy"])
        self.assertIn("登录没能开始", data["refused"]["text"])
        self.assertIn("窗口没起来", data["refused"]["text"])
        self.assertFalse(data["refused"]["pending"])
        self.assertFalse(data["refused"]["busy"])
        self.assertEqual(data["refused"]["result"], "valid", "登录没开始时旧结论要原样留着")
        self.assertTrue(data["refused"]["present"])
        self.assertIn("登录没能开始", data["crashed"]["text"])
        self.assertIn("桥接断了", data["crashed"]["text"])
        self.assertFalse(data["crashed"]["busy"])
        self.assertIn("演示模式不登录", data["demo"]["text"])
        self.assertIn("演示模式不联网", data["demo"]["text"])
        self.assertFalse(data["demo"]["busy"])
        self.assertNotIn("登录没能开始", data["component"]["text"])
        self.assertIn("程序组件缺失", data["component"]["banner"])
        self.assertFalse(data["component"]["busy"])
    # 开始报名计划前逐个挡住：忙、条款、没选、场次有问题；挡住时一个请求都不发。
    def test_start_plan_refuses_before_sending_anything(self):
        data = run_js(FLOW_PRELUDE + r'''
let starts = 0;
window.pywebview = { api: { start_plan: () => { starts += 1; return Promise.resolve({ ok: true }); } } };
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
S.selected.add("a1"); S.listState = "ready";
S.busy = true; startPlan(); const busy = { starts: starts, result: $("#result").textContent };
S.busy = false; S.demo = false; S.terms.acceptedVersion = ""; startPlan();
const terms = { starts: starts, result: $("#result").textContent };
S.demo = true; S.terms.acceptedVersion = "v1"; S.selected = new Set(); startPlan();
const empty = { starts: starts, result: $("#result").textContent };
S.selected = new Set(["a1", "a2"]); startPlan();
const conflict = { starts: starts, result: $("#result").textContent,
  board: $("#plan-conflicts").textContent };
out.push({ busy, terms, empty, conflict });
''')[0]
        self.assertEqual(data["busy"]["starts"], 0, "计划运行中不能再发一次开始请求")
        self.assertEqual(data["busy"]["result"], "")
        self.assertEqual(data["terms"]["starts"], 0, "条款没同意不能发开始请求")
        self.assertIn("还没选活动", data["empty"]["result"])
        self.assertEqual(data["empty"]["starts"], 0)
        self.assertIn("计划还不能开始", data["conflict"]["result"])
        self.assertIn("活动时间重叠", data["conflict"]["board"])
        self.assertEqual(data["conflict"]["starts"], 0)

    # 后端接纳后排好场次并写运行记录；接纳回来的计划已经结束就不再置忙。
    def test_start_plan_reports_the_ack_and_respects_a_terminal_ack(self):
        data = run_js(FLOW_PRELUDE + r'''
window.pywebview = { api: { start_plan: () => Promise.resolve({ ok: true, plan_id: "p1" }) } };
load([mk("a1", "活动甲")]); S.selected.add("a1"); S.listState = "ready";
startPlan(); await flush(); render();
const accepted = { busy: S.busy, planId: S.plan.id, log: S.recentLogs.join("|"),
  title: $("#selected").textContent, button: $("#btn-plan").textContent };
S.busy = false; S.plan = { id: null, status: "idle", tasks: new Map() }; setResult(null);
window.pywebview = { api: { start_plan: () => Promise.resolve({ ok: true, plan_id: "p2" }) } };
startPlan(); await flush();
S.plan.status = "completed"; S.busy = false;
window.pywebview = { api: { start_plan: () => Promise.resolve({ ok: true, plan_id: "p2" }) } };
startPlan(); await flush(); render();
const terminal = { busy: S.busy, status: S.plan.status };
out.push({ accepted, terminal });
''')[0]
        self.assertTrue(data["accepted"]["busy"])
        self.assertEqual(data["accepted"]["planId"], "p1")
        self.assertIn("已安排 1 场活动：1 场预报名等开放。", data["accepted"]["log"])
        self.assertEqual(data["accepted"]["title"], "正在准备报名")
        self.assertEqual(data["accepted"]["button"], "计划运行中")
        self.assertFalse(data["terminal"]["busy"])
        self.assertEqual(data["terminal"]["status"], "completed")

    # 后端拒绝开始的三种情况：条款回绝回到门禁、组件失败只挂横幅、其余给结果框。
    def test_start_plan_rejection_branches_show_their_own_exit(self):
        data = run_js(FLOW_PRELUDE + r'''
const run = async (reply) => {
  window.pywebview = { api: { start_plan: () => Promise.resolve(reply) } };
  S.busy = false; S.starting = false;
  S.startRequest = { id: "", state: "idle", timer: null, queryTimer: null, reconcile: 0, gen: 0 };
  S.terms.acceptedVersion = "v1"; S.terms.unknown = false;
  S.runtime = { error: null, checkPending: false, listPending: false, roundError: null };
  setResult(null); load([mk("a1", "活动甲")]); S.selected = new Set(["a1"]);
  S.listState = "ready"; S.plan = { id: null, status: "idle", tasks: new Map() };
  startPlan(); await flush(); render();
  return { result: $("#result").textContent, banner: $("#banners").textContent,
    busy: S.busy, accepted: S.terms.acceptedVersion, unknown: S.terms.unknown };
};
const terms = await run({ ok: false, error: "terms_required",
  terms: { version: "v2", accepted_version: "" } });
const component = await run({ ok: false, error: "worker_missing", text: "组件缺失" });
const plain = await run({ ok: false, text: "场次已截止", errors: [], conflicts: [] });
out.push({ terms, component, plain });
''')[0]
        self.assertEqual(data["terms"]["accepted"], "")
        self.assertFalse(data["terms"]["unknown"])
        self.assertFalse(data["terms"]["busy"])
        self.assertIn("程序组件缺失", data["component"]["banner"])
        self.assertEqual(data["component"]["result"], "")
        self.assertFalse(data["component"]["busy"])
        self.assertIn("场次已截止", data["plain"]["result"])
        self.assertFalse(data["plain"]["busy"])

    # 同一场的进度事件先到、终态后到、又来了迟到的进度：标签只按终态走，不退回运行态。
    def test_task_events_keep_the_terminal_fact_and_update_the_card(self):
        data = run_js(FLOW_PRELUDE + r'''
load([mk("a1", "活动甲")]);
S.busy = true; S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map() };
window.onBackend.task({ plan_id: "p1", plan_generation: 1, task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "waiting", sign_start: "2026-11-07 09:00:00" });
render(); const waiting = { card: $("#plan-tasks").textContent, status: S.plan.tasks.get("t1").status };
window.onBackend.task({ plan_id: "p1", plan_generation: 1, task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "success", last_reason: "报名成功。" });
render(); const done = { card: $("#plan-tasks").textContent, status: S.plan.tasks.get("t1").status,
  log: S.recentLogs.join("|") };
window.onBackend.task({ plan_id: "p1", plan_generation: 1, task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "waiting", attempts: 0 });
render(); const late = { status: S.plan.tasks.get("t1").status,
  card: $("#plan-tasks").textContent };
out.push({ waiting, done, late });
''')[0]
        self.assertIn("等待开放", data["waiting"]["card"])
        self.assertEqual(data["waiting"]["status"], "waiting")
        self.assertIn("报名成功", data["done"]["card"])
        self.assertEqual(data["done"]["status"], "success")
        self.assertIn("报名成功：活动甲", data["done"]["log"])
        self.assertEqual(data["late"]["status"], "success", "终态不能被迟到的进度拖回去")
        self.assertIn("报名成功", data["late"]["card"])
    # 开始请求把每场的时间和模式一起交上去；后端说「还在处理」时不重发，改为对账。
    def test_start_plan_sends_full_items_and_waits_on_pending(self):
        data = run_js(FLOW_PRELUDE + r'''
const calls = [];
window.pywebview = { api: {
  start_plan: (...args) => { calls.push(args); return Promise.resolve({ pending: true }); },
  start_request_state: () => new Promise(() => {}),
} };
load([mk("a1", "活动甲"), mk("a2", "活动乙", { sign_start: "2026-11-06 13:00:00",
  act_start: "2026-11-10 09:00:00", act_end: "2026-11-10 11:00:00" })]);
S.selected = new Set(["a1", "a2"]); S.listState = "ready"; S.busy = false;
startPlan(); await flush();
const sent = calls.length ? calls[0][0] : [];
out.push({ calls: calls.length, items: sent, state: S.startRequest.state,
  starting: S.starting, button: $("#btn-plan").textContent });
''')[0]
        self.assertEqual(data["calls"], 1, "回「还在处理」不能再发第二次开始请求")
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["sign_start"], "2026-11-07 09:00:00")
        self.assertEqual(data["items"][0]["sign_end"], "2026-11-08 09:00:00")
        self.assertEqual(data["items"][0]["act_start"], "2026-11-09 09:00:00")
        self.assertEqual(data["items"][0]["signup_mode"], "pre_register")
        self.assertEqual(data["items"][1]["signup_mode"], "instant_signup")
        self.assertEqual(data["state"], "reconciling")
        self.assertTrue(data["starting"])
        self.assertEqual(data["button"], "正在确认是否启动…")
    # 对账确认已接纳时按快照恢复任务与停止按钮；快照已经结束就不再置忙。
    def test_reconcile_accepted_restores_tasks_or_keeps_the_terminal_state(self):
        script = FLOW_PRELUDE + r'''
const run = async (snapshot, finished) => {
  S.busy = false; S.starting = true;
  S.plan = { id: null, status: "idle", tasks: new Map() };
  S.startRequest = { id: "r1", state: "submitting", timer: null, queryTimer: null, reconcile: 0, gen: 0 };
  window.pywebview = { api: { start_request_state: () => Promise.resolve({
    state: "accepted", plan_id: "p1", running: !finished, finished: finished, snapshot: snapshot,
    plan_generation: 2 }) } };
  reconcileStart("r1"); await flush(); render();
  return { busy: S.busy, planId: S.plan.id, status: S.plan.status,
    tasks: Array.from(S.plan.tasks.keys()), stop: $("#btn-stop").disabled,
    resultOpen: S.resultOpen === true, result: $("#result").textContent,
    title: $("#selected").textContent };
};
'''
        running = run_js(script + r'''
const running = await run({ status: "running", tasks: [
  { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
    sign_start: "2026-11-07 09:00:00" }] }, false);
out.push(running);
''')[0]
        finished = run_js(script + r'''
const finished = await run({ status: "completed", tasks: [
  { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" }] }, true);
out.push(finished);
''')[0]
        data = {"running": running, "finished": finished}
        self.assertTrue(data["running"]["busy"])
        self.assertEqual(data["running"]["planId"], "p1")
        self.assertEqual(data["running"]["tasks"], ["t1"])
        self.assertFalse(data["running"]["stop"])
        self.assertEqual(data["running"]["title"], "活动甲")
        self.assertFalse(data["finished"]["busy"], "接纳回来的快照已经结束，不能置忙")
        self.assertEqual(data["finished"]["status"], "completed")
        self.assertTrue(data["finished"]["resultOpen"])
        self.assertIn("报名计划完成", data["finished"]["title"])

if __name__ == "__main__":
    unittest.main()
