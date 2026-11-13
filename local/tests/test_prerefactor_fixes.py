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

from test_ui_contract import JS_HARNESS, LOCAL  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
