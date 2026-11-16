#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划开始、对账、停止、修改和结果出口的行为测试。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402


PRELUDE = r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
const running = await run({ status: "running", tasks: [
  { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
    sign_start: "2026-11-07 09:00:00" }] }, false);
const finished = await run({ status: "completed", tasks: [
  { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" }] }, true);
out.push({ running, finished });
''')[0]
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
