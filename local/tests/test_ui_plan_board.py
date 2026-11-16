#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划栏认状态、认按钮和任务卡的行为测试。

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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
load([mk("a1", "已准备活动", { sign_start: "2026-11-06 14:30:00" })]);
S.busy = true; S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "已准备活动",
  status: "waiting", sign_start: "2026-11-06 14:30:00", page_opened_at: bnowS() });
render(); out.push({ detail: $("#plan-tasks").textContent });
''')[0]
        self.assertIn("已准备好", data["detail"])
    # 没登录过的新用户打开时，大屏先说「登录后开始」，不摆空列表的结论。
    def test_first_use_board_invites_login(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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


if __name__ == "__main__":
    unittest.main()
