#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重构前先修的桌面端行为缺陷：修改计划卡在「修改中」、程序自己发起的刷新清空列表，
以及报名成功后有界刷新的守护（计划 20261113-prerefactor-fixes）。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
沙箱的 document.addEventListener 默认只记 keydown；这里换成会记下全部监听的版本，
才能触发 app.js 里的 visibilitychange。

每条用例的断言都以「用户看到的结果」为准：列表有没有被清空、勾选有没有丢、
修改中的标记有没有留下，而不是源码里有没有某个字符串。

@author Author
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import JS_HARNESS, LOCAL  # noqa: E402
from test_ui_reliability import TIMER_HARNESS  # noqa: E402

UI_DIR = LOCAL / "ui"

# 沙箱原来只把 keydown 记下来；visibilitychange 等监听要能被用例触发，所以另存一份全部监听
_HOOKED_HARNESS = JS_HARNESS.replace(
    'addEventListener: (t, fn) => { if (t === "keydown") keydownListeners.push(fn); },',
    'addEventListener: (t, fn) => { if (t === "keydown") keydownListeners.push(fn);'
    ' (sandbox.__docListeners[t] = sandbox.__docListeners[t] || []).push(fn); },',
).replace("out, focused, __els: els,", "out, focused, __els: els, __docListeners: {},")
assert _HOOKED_HARNESS != JS_HARNESS and "__docListeners" in _HOOKED_HARNESS, "沙箱补丁没有生效"


def run_ui(snippet: str, ui_dir: Path | None = None):
    """在沙箱里跑片段，返回 out 数组。node 缺失时 skip（跳过要如实报告）。"""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，无法运行 JS 行为测试")
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "harness.js"
        part = Path(name) / "snippet.js"
        harness.write_text(_HOOKED_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        res = subprocess.run([node, str(harness), str(ui_dir or UI_DIR), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60, env=dict(os.environ))
    if res.returncode != 0:
        raise AssertionError("JS 行为测试崩溃：%s" % res.stderr[-800:])
    marker = res.stdout.rfind("__RESULT__")
    if marker < 0:
        raise AssertionError("JS 行为测试没有输出结果：%s" % res.stdout[-500:])
    return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


# 业务现在 = 北京时间 2026-11-06 14:00；条款已同意、在线、非演示
PRELUDE = TIMER_HARNESS + r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = false;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const base = { place: "学生公寓", checkin_required: false, checkout_required: false };
function mk(id, name, extra) {
  return Object.assign({}, base, { id: id, name: name, signed: false,
    sign_start: "2026-11-06 16:00:00", sign_end: "2026-11-08 09:00:00",
    act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
}
function load(items) {
  window.onBackend.activities({ ok: true, items: items.map((it) => Object.assign({}, it)) });
}
/* 运行记录真正多出的行数：数 #log 上的追加才是用户看到的行 */
const appended = [];
const logBox = $("#log");
const origAppend = logBox.appendChild;
logBox.appendChild = (child) => { appended.push(String(child.textContent).replace(/^\d\d:\d\d:\d\d\s+/, "")); return origAppend(child); };
const __calls = { check: [], list: [], start: [], stop: [] };
let __stopImpl = () => new Promise(() => {});
window.pywebview = { api: {
  check: (id) => { __calls.check.push(id); return Promise.resolve({ ok: true, queued: true }); },
  list_activities: (id) => { __calls.list.push(id); return Promise.resolve({ ok: true, queued: true }); },
  bootstrap: () => Promise.resolve({ busy: false }),
  window_visibility: () => Promise.resolve({ hidden: false }),
  start_plan: (items) => { __calls.start.push(items.map((it) => it.id)); return new Promise(() => {}); },
  stop_plan: (id) => { __calls.stop.push(id); return __stopImpl(); },
} };
/* 一份运行中的计划：只有一场还没提交的预报名，离开放 2 小时，修改计划来得及 */
function runningPlan() {
  S.busy = true;
  S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map([
    ["t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
             sign_start: "2026-11-06 16:00:00" }]]) };
}
"""


class PlanEditingExitTests(unittest.TestCase):
    """U1/U9：「修改计划」的各条退出路径，以及「放弃修改」回到原来的场次。"""

    def test_stop_refused_while_editing_returns_to_the_running_plan(self):
        """后端拒绝停止：计划还在跑，不能留着「修改中」，运行记录说清停止没成功。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
runningPlan();
__stopImpl = () => Promise.resolve({ ok: false, text: "当前没有这个计划" });
modifyPlan();
await __flush();
render();
out.push({ editing: S.editing || null, stopping: S.stopping, busy: S.busy,
  stopBtnDisabled: $("#btn-stop").disabled, lines: appended.slice() });
""")
        data = res[0]
        self.assertIsNone(data["editing"], "停止被拒后不能还处在修改中")
        self.assertFalse(data["stopping"])
        self.assertTrue(data["busy"], "计划没停，仍在运行")
        self.assertFalse(data["stopBtnDisabled"], "「停止计划」要能再点")
        self.assertTrue(any("计划继续运行" in line for line in data["lines"]), data["lines"])
        self.assertFalse(any("计划已暂停" in line for line in data["lines"]),
                         "停止没成功就不能说计划已暂停：%r" % data["lines"])

    def test_stop_bridge_error_while_editing_returns_to_the_running_plan(self):
        """桥接异常同理：也要清掉修改中，不写已暂停。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲")]);
runningPlan();
__stopImpl = () => Promise.reject(new Error("桥接断了"));
modifyPlan();
await __flush();
render();
out.push({ editing: S.editing, stopping: S.stopping, lines: appended.slice() });
""")
        data = res[0]
        self.assertIsNone(data["editing"])
        self.assertFalse(data["stopping"])
        self.assertTrue(any("桥接断了" in line for line in data["lines"]), "原有的失败说明保留")
        self.assertTrue(any("计划继续运行" in line for line in data["lines"]), data["lines"])
        self.assertFalse(any("计划已暂停" in line for line in data["lines"]), data["lines"])

    def test_plain_stop_refusal_does_not_invent_the_editing_sentence(self):
        """守卫：用户直接点「停止计划」被拒，没有「修改中」可清，也就不写修改相关的话。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲")]);
runningPlan();
__stopImpl = () => Promise.resolve({ ok: false, text: "当前没有这个计划" });
doStopPlan();
await __flush();
out.push({ editing: S.editing || null, stopping: S.stopping, lines: appended.slice() });
""")
        data = res[0]
        self.assertIsNone(data["editing"])
        self.assertFalse(data["stopping"])
        self.assertFalse(any("计划继续运行" in line for line in data["lines"]), data["lines"])
        self.assertTrue(any("当前没有这个计划" in line for line in data["lines"]), "原有说明保留")

    def test_plan_ending_by_itself_while_editing_clears_editing(self):
        """停止请求发出后计划自己结束（不是 stopped）：走结果页，不留「修改中」。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲")]);
runningPlan();
modifyPlan();                              /* 停止请求悬着，editing 已记下 */
const during = { editing: !!S.editing };
window.onBackend.plan_done({ plan_id: "p1", status: "completed", plan_generation: 1, summary: {} });
render();
out.push({ during, editing: S.editing || null, busy: S.busy, result: resultMode(),
  actionsHidden: $("#route-actions").hidden, stopping: S.stopping });
""")
        data = res[0]
        self.assertTrue(data["during"]["editing"], "前提：停止请求悬着时处于修改中")
        self.assertIsNone(data["editing"], "计划已自然结束，修改中必须清掉")
        self.assertFalse(data["busy"])
        self.assertTrue(data["result"], "清掉以后才能进结果页")

    def test_reselect_after_the_natural_end_is_not_still_editing(self):
        """自然结束后「重新选择未成功的场次」回草稿：计划栏不能还是「修改中」。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲")]);
runningPlan();
modifyPlan();
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "failed", reason: "名额已满", stop_reason: "max_attempts", plan_generation: 1 });
window.onBackend.plan_done({ plan_id: "p1", status: "failed", plan_generation: 1, summary: {} });
reselectFailed();
render();
out.push({ editing: S.editing || null, restoreHidden: $("#btn-edit-restore").hidden,
  noteHidden: $("#edit-note").hidden });
""")
        data = res[0]
        self.assertIsNone(data["editing"])
        self.assertTrue(data["restoreHidden"])
        self.assertTrue(data["noteHidden"])

    def test_confirmed_stop_still_puts_unsubmitted_tasks_back_into_the_draft(self):
        """守卫：正常停止（stopped）仍然放回勾选并保留修改中，直到用户重新开始。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
S.selected.add("a2");
runningPlan();
__stopImpl = () => Promise.resolve({ ok: true });
modifyPlan();
await __flush();
window.onBackend.plan_done({ plan_id: "p1", status: "stopped", plan_generation: 1, summary: {} });
render();
out.push({ editing: S.editing, selected: Array.from(S.selected).sort(), busy: S.busy,
  noteHidden: $("#edit-note").hidden, restoreHidden: $("#btn-edit-restore").hidden });
""")
        data = res[0]
        self.assertEqual(data["editing"], {"ids": ["a1"], "doneN": 0})
        self.assertEqual(data["selected"], ["a1"], "放回的是计划里没提交的场次，不是停之前的勾选")
        self.assertFalse(data["busy"])
        self.assertFalse(data["noteHidden"])
        self.assertFalse(data["restoreHidden"])

    def test_paused_line_is_written_when_the_stop_is_confirmed_not_before(self):
        """U9：「计划已暂停」要等计划真的以 stopped 结束才写，一次，场次数照放回草稿的数。"""
        res = run_ui(PRELUDE + r"""
load([mk("a1", "活动甲")]);
runningPlan();
modifyPlan();                              /* 停止请求还没有结论 */
const pending = appended.filter((line) => line.indexOf("计划已暂停") >= 0);
window.onBackend.plan_done({ plan_id: "p1", status: "stopped", plan_generation: 1, summary: {} });
const done = appended.filter((line) => line.indexOf("计划已暂停") >= 0);
out.push({ pending, done });
""")
        data = res[0]
        self.assertEqual(data["pending"], [], "停止还没成功，不能先写计划已暂停：%r" % data["pending"])
        self.assertEqual(data["done"], ["计划已暂停：1 场放回草稿修改"])

    def test_restore_button_restarts_the_original_tasks_not_the_current_ticks(self):
        """U1：「放弃修改，按原计划继续」按原来的场次重新开始，不按用户改过的勾选。"""
        res = run_ui(PRELUDE + r"""
S.demo = true;                             /* 开始前的检查在演示登录下不挡，与既有修改态用例一致 */
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
S.editing = { ids: ["a1"], doneN: 0 };
S.plan = { id: "p1", gen: 1, status: "stopped", tasks: new Map() };
S.selected.clear();
S.selected.add("a2");                      /* 用户在修改中把勾选改成了另一场 */
render();
$("#btn-edit-restore").click();
await __flush();
out.push({ started: __calls.start, selected: Array.from(S.selected) });
""")
        data = res[0]
        self.assertEqual(data["started"], [["a1"]], "要按原计划的场次开始，而不是当前勾选")
        self.assertEqual(data["selected"], ["a1"])

    def test_restore_button_skips_tasks_that_can_no_longer_be_signed(self):
        """原场次里已经不在列表（或不能报）的，不跟着重新开始。"""
        res = run_ui(PRELUDE + r"""
S.demo = true;
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
S.editing = { ids: ["a1", "gone"], doneN: 0 };
S.plan = { id: "p1", gen: 1, status: "stopped", tasks: new Map() };
S.selected.clear();
render();
$("#btn-edit-restore").click();
await __flush();
out.push({ started: __calls.start });
""")
        self.assertEqual(res[0]["started"], [["a1"]])


# 非后台刷新用例的公共骨架：先加载两场、勾一场，再触发程序自己发起的刷新；
# 校验刷新确实发出了，当时没有骨架，学校回包失败后列表和勾选都还在
PROGRAM_REFRESH = PRELUDE + r"""
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
S.selected.add("a1");
const __look = () => ({ state: S.listState, bg: !!S.round.background, items: S.items.length,
  selected: Array.from(S.selected), listCalls: __calls.list.length });
const __failList = () => window.onBackend.activities({ request_id: S.round.list, ok: false, text: "连不上学校站点" });
"""

PROGRAM_TAIL = r"""
await __flush(20);
const sent = __look();
__failList();
const after = __look();
out.push({ sent, after });
"""


class ProgramRefreshTests(unittest.TestCase):
    """U2/U3：程序自己发起的刷新走后台轮——不画骨架，失败不清列表也不清勾选。"""

    def check_background(self, trigger, label):
        data = run_ui(PROGRAM_REFRESH + trigger + PROGRAM_TAIL)[0]
        self.assertEqual(data["sent"]["listCalls"], 1, "%s：刷新确实要发出一轮" % label)
        self.assertEqual(data["sent"]["state"], "ready",
                         "%s：发出刷新时列表不能退回骨架（loading）：%r" % (label, data["sent"]))
        self.assertTrue(data["sent"]["bg"], "%s：应是后台轮" % label)
        self.assertEqual(data["after"]["items"], 2, "%s：学校回包失败后列表不能被清空" % label)
        self.assertEqual(data["after"]["selected"], ["a1"], "%s：勾选不能丢" % label)
        self.assertEqual(data["after"]["state"], "ready", "%s：不能切到错误空态" % label)

    def test_window_becoming_visible_refreshes_in_the_background(self):
        self.check_background(r"""
document.hidden = false;
window.__docListeners.visibilitychange.forEach((fn) => fn());
""", "窗口重新可见 app.js:641")

    def test_cancel_success_refreshes_in_the_background(self):
        self.check_background(r"""
S.cancel.busyId = "a1";
cancelSettle("a1", { ok: true, kind: "cancelled" });
""", "取消报名成功 cancel.js:52")

    def test_failed_task_recheck_refreshes_in_the_background(self):
        self.check_background(r"""
showTaskResult({ task_id: "t1", activity_id: "a1", name: "活动甲", status: "failed",
  reason: "名额已满", stop_reason: "max_attempts" });
__fire(400);
""", "报名失败后复查 plan-events.js:123")

    def test_signed_bounded_refresh_runs_in_the_background(self):
        self.check_background(r"""
scheduleSignedRefresh();
__fire(800);
""", "报名成功后的有界刷新 refresh.js:456")

    def test_relogin_success_refreshes_in_the_background(self):
        self.check_background(r"""
reloginSucceeded("f1");
""", "重新登录成功且列表已有内容 relogin.js")

    def test_relogin_success_with_an_empty_list_keeps_the_skeleton(self):
        """重新登录成功时列表空着（常常正是因为登录失效才拉不到列表）：走前台轮，才有骨架与错误空态。"""
        res = run_ui(PRELUDE + r"""
reloginSucceeded("f1");
await __flush();
out.push({ state: S.listState, bg: !!S.round.background, listCalls: __calls.list.length });
""")
        data = res[0]
        self.assertEqual(data["listCalls"], 1, "重新登录成功后要加载一次列表")
        self.assertEqual(data["state"], "loading", "列表为空时前台轮才有骨架")
        self.assertFalse(data["bg"])

    def test_browser_login_success_with_a_list_refreshes_in_the_background(self):
        self.check_background(r"""
S.login.loginPending = true;
handleDone({ kind: "login", ok: true });
""", "浏览器登录成功且列表已有内容 plan.js:471")

    def test_browser_login_success_with_an_empty_list_keeps_the_skeleton(self):
        """列表为空时前台轮才有骨架和错误空态可看：这一支保持原行为。"""
        res = run_ui(PRELUDE + r"""
S.login.loginPending = true;
handleDone({ kind: "login", ok: true });
await __flush();
out.push({ state: S.listState, bg: !!S.round.background, listCalls: __calls.list.length });
""")
        data = res[0]
        self.assertEqual(data["listCalls"], 1)
        self.assertEqual(data["state"], "loading")
        self.assertFalse(data["bg"])

    def accept_terms_js(self):
        return r"""
window.pywebview.api.accept_terms = () => Promise.resolve({ ok: true, terms: { version: "2026-10-27",
  accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } });
window.pywebview.api.save_prefs = () => Promise.resolve({ ok: true });
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro");
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true;
document.querySelector("#btn-terms-accept").click();
"""

    def test_accepting_terms_with_a_list_refreshes_in_the_background(self):
        self.check_background(self.accept_terms_js(), "同意条款后补加载（列表已有内容）terms.js:354")

    def test_accepting_terms_with_an_empty_list_keeps_the_skeleton(self):
        res = run_ui(PRELUDE + self.accept_terms_js() + r"""
await __flush(12);
out.push({ state: S.listState, bg: !!S.round.background, listCalls: __calls.list.length });
""")
        data = res[0]
        self.assertEqual(data["listCalls"], 1, "同意后要补加载一次")
        self.assertEqual(data["state"], "loading")
        self.assertFalse(data["bg"])

    def recheck_terms_js(self):
        return r"""
window.pywebview.api.accept_terms = () => new Promise(() => {});
window.pywebview.api.bootstrap = () => Promise.resolve({ terms: { version: "2026-10-27",
  accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } });
window.pywebview.api.save_prefs = () => Promise.resolve({ ok: true });
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro");
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true;
document.querySelector("#btn-terms-accept").click();
__fire(10000);                              /* 10 秒没有回执：转「保存结果未确认」 */
document.querySelector("#btn-terms-recheck").click();
"""

    def test_terms_recheck_success_with_a_list_refreshes_in_the_background(self):
        self.check_background(self.recheck_terms_js(), "重新确认条款后补加载（列表已有内容）terms.js:414")

    def test_terms_recheck_success_with_an_empty_list_keeps_the_skeleton(self):
        res = run_ui(PRELUDE + self.recheck_terms_js() + r"""
await __flush(12);
out.push({ state: S.listState, bg: !!S.round.background, listCalls: __calls.list.length });
""")
        data = res[0]
        self.assertEqual(data["listCalls"], 1)
        self.assertEqual(data["state"], "loading")
        self.assertFalse(data["bg"])

    def test_user_clicked_refresh_and_startup_stay_foreground(self):
        """守卫：用户点的刷新照旧出骨架、失败清空；启动那一处源码里仍是前台调用。"""
        data = run_ui(PROGRAM_REFRESH + r"""
refresh(false);
await __flush();
const sent = __look();
__failList();
out.push({ sent, after: __look() });
""")[0]
        self.assertEqual(data["sent"]["state"], "loading")
        self.assertFalse(data["sent"]["bg"])
        self.assertEqual(data["after"]["items"], 0, "用户点的刷新失败仍清空列表")
        boot = (UI_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("    refresh(true);\n    startAutoRefresh();", boot,
                      "启动流程里的首轮刷新要保持前台")


# AA3-03：报名成功后的有界刷新。原先 local/tests 里零引用，重构挪动 state 层时可能「绿着坏」
AA3_SNIPPET = PRELUDE + r"""
load([mk("a1", "活动甲", { sign_start: "2026-11-06 13:00:00" }),
      mk("a2", "活动乙", { sign_start: "2026-11-06 13:00:00" })]);
const rc = [];
refresh = (quiet, options) => { rc.push({ quiet: quiet, background: !!(options && options.background) }); };
const armed = () => __timers.filter((t) => t.ms === 800).length;
const success = (task, activity) => window.onBackend.task({ plan_id: "p1", task_id: task,
  activity_id: activity, name: "活动", status: "success", attempts: 1, plan_generation: 1 });
window.onBackend.plan({ plan_id: "p1", status: "running", plan_generation: 1, tasks: [] });

/* 1) 一次成功：安排一个约 800ms 的定时器；计划结束后到点发一轮刷新 */
success("t1", "a1");
const armedAfterOne = armed();
window.onBackend.plan_done({ plan_id: "p1", status: "completed", plan_generation: 1, summary: {} });
__fire(800);
const sentOnce = rc.length;

/* 2) 连续两次成功：定时器顶掉前一个，只发一次 */
rc.length = 0;
window.onBackend.plan({ plan_id: "p2", status: "running", plan_generation: 2, tasks: [] });
load([mk("a3", "活动丙", { sign_start: "2026-11-06 13:00:00" }),
      mk("a4", "活动丁", { sign_start: "2026-11-06 13:00:00" })]);
const success2 = (task, activity) => window.onBackend.task({ plan_id: "p2", task_id: task,
  activity_id: activity, name: "活动", status: "success", attempts: 1, plan_generation: 2 });
success2("t3", "a3");
success2("t4", "a4");
const armedAfterTwo = armed();
window.onBackend.plan_done({ plan_id: "p2", status: "completed", plan_generation: 2, summary: {} });
__fire(800);
const fired = rc.length;
const none = __fire(800);                   /* 已经触发过，不会再有第二个 */

/* 3) 三种拦截：忙碌、启动中、演示模式，到点也不发 */
const blocked = {};
const blockedRun = (name, apply, revert, planId, gen, activity) => {
  rc.length = 0;
  load([mk(activity, "活动", { sign_start: "2026-11-06 13:00:00" })]);
  window.onBackend.plan({ plan_id: planId, status: "running", plan_generation: gen, tasks: [] });
  window.onBackend.task({ plan_id: planId, task_id: "tb", activity_id: activity, name: "活动",
    status: "success", attempts: 1, plan_generation: gen });
  window.onBackend.plan_done({ plan_id: planId, status: "completed", plan_generation: gen, summary: {} });
  apply();
  const armedNow = armed();               /* 先确认定时器真的安排了，下面的 0 才不是空转 */
  __fire(800);
  blocked[name] = { armed: armedNow, sent: rc.length };
  revert();
};
blockedRun("busy", () => { S.busy = true; }, () => { S.busy = false; }, "p3", 3, "b1");
blockedRun("starting", () => { S.starting = true; }, () => { S.starting = false; }, "p4", 4, "b2");
blockedRun("demo", () => { S.demo = true; }, () => { S.demo = false; }, "p5", 5, "b3");
out.push({ armedAfterOne, sentOnce, armedAfterTwo, fired, none, blocked });
"""


class SignedRefreshTests(unittest.TestCase):
    """AA3-03：报名成功后的有界刷新（state/plan.js 的调用 → refresh.js scheduleSignedRefresh）。"""

    @staticmethod
    def assert_aa3(case, data):
        case.assertEqual(data["armedAfterOne"], 1, "报名成功后要安排一次有界刷新（约 800ms）")
        case.assertEqual(data["sentOnce"], 1, "到点要发出一轮刷新")
        case.assertEqual(data["armedAfterTwo"], 1, "连续成功只留一个定时器")
        case.assertEqual(data["fired"], 1, "连续成功只发一次")
        case.assertFalse(data["none"], "触发过的定时器不会再有第二个")
        case.assertEqual(data["blocked"], {name: {"armed": 1, "sent": 0}
                                           for name in ("busy", "starting", "demo")},
                         "忙碌、启动中、演示模式：定时器照常安排，到点不发刷新")

    def test_success_event_schedules_one_bounded_refresh(self):
        self.assert_aa3(self, run_ui(AA3_SNIPPET)[0])

    def test_removing_the_call_in_state_layer_is_caught(self):
        """变异：在 mkdtemp 副本里删掉 state/plan.js 的调用，上面的断言必须红。
        仓库里的文件不动；这条用例让「用例能抓到删调用」一直有据可查。"""
        with tempfile.TemporaryDirectory() as name:
            copy = Path(name) / "ui"
            shutil.copytree(UI_DIR, copy)
            target = copy / "state" / "plan.js"
            text = target.read_text(encoding="utf-8")
            old = "if (noteSignedTasks([task])) scheduleSignedRefresh();"
            self.assertEqual(text.count(old), 1, "变异点必须唯一存在")
            target.write_text(text.replace(old, "noteSignedTasks([task]);"), encoding="utf-8")
            mutated = run_ui(AA3_SNIPPET, ui_dir=copy)[0]
        with self.assertRaises(AssertionError) as caught:
            self.assert_aa3(self, mutated)
        self.assertIn("有界刷新", str(caught.exception))


class ReloginBrowserSwitchTests(unittest.TestCase):
    """U6：验证码页「改用浏览器登录」要等 relogin_cancel 返回再发 login。
    后端定性见 test_relogin_busy_order.py：取消还在终止中继 worker 时到达的 login 会被忙碌拒绝。"""

    CAP_PAGE = PRELUDE + r"""
const order = [];
let releaseCancel = null;
window.pywebview = { api: {
  relogin_cancel: (id) => { order.push("cancel:" + id); return new Promise((resolve) => { releaseCancel = resolve; }); },
  login: () => { order.push("login"); return Promise.resolve({ ok: true }); },
} };
S.login.present = true;
S.login.result = "expired";
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "desktop", flow_id: "f2", challenge_id: "c1", attempts: 1,
  image: "data:image/png;base64,AAA" });
openRelogin();
const step = S.relogin.step;
"""

    def test_browser_login_waits_for_the_cancel_to_return(self):
        res = run_ui(self.CAP_PAGE + r"""
$("#btn-rl-browser").click();
await __flush();
const before = order.slice();
releaseCancel({ ok: true });
await __flush();
out.push({ step, before, after: order.slice() });
""")
        data = res[0]
        self.assertEqual(data["step"], "cap", "前提：验证码页开着，中继 worker 在跑")
        self.assertEqual(data["before"], ["cancel:f2"],
                         "取消还没返回就发了 login，会撞上还没退出的中继 worker：%r" % data["before"])
        self.assertEqual(data["after"], ["cancel:f2", "login"])

    def test_browser_login_still_goes_ahead_if_the_cancel_call_fails(self):
        """取消调用本身失败也不能卡住用户：照样往下登录。"""
        res = run_ui(self.CAP_PAGE + r"""
window.pywebview.api.relogin_cancel = (id) => { order.push("cancel:" + id); return Promise.reject(new Error("桥接断了")); };
$("#btn-rl-browser").click();
await __flush();
out.push({ order: order.slice() });
""")
        self.assertEqual(res[0]["order"], ["cancel:f2", "login"])

    def test_bad_password_page_browser_login_goes_straight_to_login(self):
        """守卫：密码不对那一页没有在跑的中继，没有取消要等，直接登录。"""
        res = run_ui(PRELUDE + r"""
const order = [];
window.pywebview = { api: {
  relogin_cancel: (id) => { order.push("cancel:" + id); return Promise.resolve({ ok: true }); },
  login: () => { order.push("login"); return Promise.resolve({ ok: true }); },
} };
S.login.present = true;
S.login.result = "expired";
S.relogin = { open: true, step: "", flowId: "", challengeId: "" };
reloginStep("bad");
reloginDialog().open = true;                 /* 沙箱的弹层桩没有 removeAttribute，开着才走 close() */
$("#btn-bad-browser").click();
await __flush();
out.push({ order: order.slice() });
""")
        self.assertEqual(res[0]["order"], ["login"])


if __name__ == "__main__":
    unittest.main()
