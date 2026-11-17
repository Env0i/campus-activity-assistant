#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划栏搬进模块之前的真加载冒烟：宽档、窄档各一次，加上计划快照与结果页。

真加载指的是按 index.html 的普通脚本顺序逐个执行、再用真实的动态 import 加载 main.js，
不走拼接夹具。拼接以后模块里的名字恰好进了全局作用域，普通脚本阶段引用模块名字这类
缺陷只有真加载才暴露；这里守的就是「搬完以后真窗口还能起来、计划栏还画得出来」。

前三条用例不改页面状态以外的东西：普通脚本阶段不抛错 + 计划栏标题、任务卡、停止按钮
画出来；结果页画得出统计与「重新选择」。后四条从界面按钮走一遍：点「开始报名计划」发出
start_plan，点「停止计划」先弹确认、点确认发出 stop_plan，结果页点「完成」回到空草稿，
已失效时点「登录」经重新登录对话框改走浏览器登录、发出 login。每条宽档与 430×820 窄档各跑一次。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_native_smoke  # noqa: E402


# 真加载后的公共开头：条款已同意、非演示、业务时钟可信（重选与门禁都要读它）。
SMOKE_SETUP = r"""
const calls = [];
const flush = async (n) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.demo = false;
S.busy = false;
ingestBusinessClock({ schema: 1, owner_id: "smoke", generation: 1, state: "ready",
  epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0,
  source: "smoke", age_s: 0, reason: "冒烟" });
"""

# 一场还能报的远期活动：开始计划的门禁要时间齐全、未报名、未截止。
SMOKE_ITEM = r"""
S.items = [{ id: "a1", name: "活动甲", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2099-01-02 09:00:00", sign_end: "2099-01-03 09:00:00",
  act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00" }].map(normalize);
S.byId = new Map(S.items.map((i) => [String(i.id), i]));
"""

# 两档各跑一次：宽档不画计划条，窄档画；同一条用例在两档下都要过。
BANDS = ((None, "wide"), ((430, 820), "narrow"))


# 计划快照：两场都在等开放，运行中。时间用远期，避免用例随日历过期。
PLAN_SNAPSHOT = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.demo = false;
S.busy = true;
S.listState = "ready";
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
  sign_start: "2099-01-01 09:00:00" });
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙", status: "waiting",
  sign_start: "2099-01-01 09:00:00" });
"""


class PlanMoveSmokeTests(unittest.TestCase):
    # 宽档真加载：普通脚本阶段不抛错，计划栏标题、两张任务卡和停止按钮都画出来。
    def test_wide_load_draws_the_running_plan_board(self):
        result = run_native_smoke([], after=PLAN_SNAPSHOT + r"""
render();
out.push({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  tasks: $("#plan-tasks").textContent, stopText: $("#btn-stop").textContent,
  stopDisabled: $("#btn-stop").disabled, band: S.band });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertEqual(case["band"], "wide")
        self.assertEqual(case["tag"], "等开放")
        self.assertEqual(case["title"], "活动甲")
        self.assertIn("活动甲", case["tasks"])
        self.assertIn("活动乙", case["tasks"])
        self.assertEqual(case["stopText"], "停止计划")
        self.assertFalse(case["stopDisabled"], "运行中停止按钮必须可点")

    # 窄档真加载：430 宽下计划条与计划栏照样画出来，普通脚本阶段不抛错。
    def test_narrow_load_draws_the_plan_dock_and_board(self):
        result = run_native_smoke([], size=(430, 820), after=PLAN_SNAPSHOT + r"""
S.selected = new Set();
render();
out.push({ band: S.band, title: $("#selected").textContent,
  dockHidden: $("#plan-dock").hidden, dockTitle: $("#dock-title").textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertEqual(case["band"], "narrow")
        self.assertEqual(case["title"], "活动甲")
        self.assertFalse(case["dockHidden"], "窄档要摆计划条")
        self.assertIn("运行中", case["dockTitle"])

    # 结果页真加载：一场成功一场失败时，统计与「重新选择」都画出来。
    def test_result_page_draws_stats_and_reselect(self):
        result = run_native_smoke([], after=r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.demo = false;
S.busy = false;
S.listState = "ready";
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" });
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙", status: "failed",
  stop_reason: "max_attempts", attempts: 2 });
/* 一场还能重报的活动留在列表里，并给一个可信现在：重选判据要读业务时钟 */
ingestBusinessClock({ schema: 1, owner_id: "smoke", generation: 1, state: "ready",
  epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0,
  source: "smoke", age_s: 0, reason: "冒烟" });
S.items = [{ id: "a2", name: "活动乙", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2099-01-02 09:00:00", sign_end: "2099-01-03 09:00:00",
  act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00" }].map(normalize);
S.byId = new Map(S.items.map((i) => [String(i.id), i]));
/* 结果页标记直接摆：模块里的 openResultPage 没人挂回 window（普通脚本都不用它），
 * 选择签名用挂回的那一个补齐，否则 resultPageOpen 会把刚打开的结果页又关上 */
S.resultOpen = true;
syncResultSelection();
render();
out.push({ stats: $("#plan-stats").textContent, statsHidden: $("#plan-stats").hidden,
  reselectHidden: $("#btn-reselect").hidden, actionsHidden: $("#result-actions").hidden,
  tag: $("#board-tag-text").textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertFalse(case["statsHidden"], "结果页要摆统计")
        self.assertIn("已报名", case["stats"])
        self.assertIn("报名未成功", case["stats"])
        self.assertFalse(case["actionsHidden"], "结果页要摆页脚按钮")
        self.assertFalse(case["reselectHidden"], "有可重报场次时要给「重新选择」")
        self.assertEqual(case["tag"], "部分完成")


    # 宽窄两档：点「开始报名计划」走真实按钮，必须向本机发出 start_plan 并带上选中的场次。
    def test_start_button_issues_start_plan(self):
        after = SMOKE_SETUP + SMOKE_ITEM + r"""
S.selected = new Set(["a1"]);
window.pywebview = { api: {
  start_plan: (...args) => { calls.push(["start_plan", args[0]]); return Promise.resolve(
    { ok: true, plan_id: "p9", plan_generation: 1 }); },
} };
render();
$("#btn-plan").click();
await flush(6);
out.push({ calls: calls.map((c) => c[0]), ids: (calls[0] && calls[0][1] || []).map((x) => x.id),
  planId: S.plan.id, busy: S.busy, band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertEqual(case["calls"], ["start_plan"], "开始按钮必须发出 start_plan")
                self.assertEqual(case["ids"], ["a1"])
                self.assertEqual(case["planId"], "p9")
                self.assertTrue(case["busy"], "计划被接纳后要置忙")

    # 宽窄两档：点「停止计划」先弹确认，点确认才发出 stop_plan，弹层随即收起。
    def test_stop_button_asks_before_stopping(self):
        after = SMOKE_SETUP + r"""
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
  status: "waiting", sign_start: "2099-01-02 09:00:00" });
window.pywebview = { api: { stop_plan: (...args) => { calls.push(["stop_plan", args[0]]);
  return Promise.resolve({ ok: true }); } } };
$("#plan-stop-ask").hidden = true;
$("#btn-stop").click();
const askOpen = !$("#plan-stop-ask").hidden;
const focusKeep = document.activeElement === $("#btn-stop-keep");
$("#btn-stop-yes").click();
await flush(4);
out.push({ askOpen, focusKeep, calls: calls.map((c) => c[0]), planId: (calls[0] || [])[1],
  askHidden: $("#plan-stop-ask").hidden, band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertTrue(case["askOpen"], "点停止要先弹确认，不能直接停")
                self.assertTrue(case["focusKeep"], "确认弹层的焦点落在「继续计划」")
                self.assertEqual(case["calls"], ["stop_plan"], "确认后才发 stop_plan")
                self.assertEqual(case["planId"], "p1")
                self.assertTrue(case["askHidden"], "确认后弹层要收起")

    # 宽窄两档：结果页点「完成，回到活动列表」收起结果页、清空选择，回到空草稿。
    def test_finish_button_returns_to_empty_draft(self):
        after = SMOKE_SETUP + r"""
S.resultOpen = true;
S.resultSel = null;
S.selected = new Set(["a1", "a2"]);
S.plan = { id: "p1", status: "partial", tasks: new Map() };
$("#btn-finish").click();
await flush(3);
out.push({ resultOpen: S.resultOpen, selected: S.selected.size, planId: S.plan.id,
  planOpen: S.planOpen, band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertFalse(case["resultOpen"], "点完成要收起结果页")
                self.assertEqual(case["selected"], 0, "点完成要清空选择")
                self.assertIsNone(case["planId"])
                self.assertFalse(case["planOpen"])

    # 宽窄两档：已失效时点「登录」进重新登录对话框，改走浏览器登录后发出 login。
    def test_login_button_falls_back_to_browser_login(self):
        after = SMOKE_SETUP + r"""
S.login = { present: true, ok: false, result: "expired", checking: false,
  loginPending: false, view: { state: "bad" }, preLoginSnapshot: null };
window.pywebview = { api: { login: () => { calls.push(["login"]);
  return Promise.resolve({ ok: false, text: "冒烟不真登录" }); } } };
$("#btn-login").click();
await flush(4);
const step = S.relogin && S.relogin.step;
const dialogOpen = !!(S.relogin && S.relogin.open);
$("#btn-rl-browser").click();
await flush(8);
out.push({ step, dialogOpen, calls: calls.map((c) => c[0]), band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertTrue(case["dialogOpen"], "已失效时点登录要先开重新登录对话框")
                self.assertEqual(case["step"], "login")
                self.assertEqual(case["calls"], ["login"], "改用浏览器登录要发出 login")


    # 宽窄两档：真加载后点草稿区地点开关，会翻转它的 aria-expanded。
    # 桩的 click() 不冒泡、closest() 恒 null，故直接调 #selected-meta 的委托并给一个
    # 会命中 [data-place-toggle] 的 target。这条依赖 main.js 里挪进来的 bindPlaceToggle();
    # —— 删掉那行就没有这个委托，翻转不会发生。
    def test_place_toggle_flips_expanded_after_native_load(self):
        after = SMOKE_SETUP + r"""
const handlers = $("#selected-meta").listeners.click || [];
const attrs = { "aria-expanded": "false" };
const placeBtn = {
  getAttribute: (k) => attrs[k] === undefined ? null : attrs[k],
  setAttribute: (k, v) => { attrs[k] = String(v); },
};
const event = { target: { closest: (sel) => sel === "[data-place-toggle]" ? placeBtn : null } };
handlers.forEach((fn) => fn(event));
const first = attrs["aria-expanded"];
handlers.forEach((fn) => fn(event));
out.push({ wired: handlers.length, first: first, second: attrs["aria-expanded"], band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertGreater(case["wired"], 0, "真加载后地点开关的委托必须接上")
                self.assertEqual(case["first"], "true", "点地点开关要展开")
                self.assertEqual(case["second"], "false", "再点一次要收起")

    # 中档真加载：点「查看计划」收起计划条、露出「返回列表」，点返回再收起计划栏、露出计划条。
    def test_medium_dock_opens_and_returns(self):
        after = SMOKE_SETUP + SMOKE_ITEM + r"""
S.selected = new Set(["a1"]);
render();
const before = { band: S.band, dockHidden: $("#plan-dock").hidden };
$("#btn-dock-open").click();
const opened = { backHidden: $("#btn-plan-back").hidden, dockHidden: $("#plan-dock").hidden,
  flag: document.querySelector("#zd").dataset.planOpen };
$("#btn-plan-back").click();
const closed = { backHidden: $("#btn-plan-back").hidden, dockHidden: $("#plan-dock").hidden };
out.push({ before, opened, closed });
"""
        case = run_native_smoke([], after=after, size=(900, 820))["after"][0]
        self.assertEqual(case["before"]["band"], "medium")
        self.assertFalse(case["before"]["dockHidden"], "中档要摆计划条")
        self.assertFalse(case["opened"]["backHidden"], "查看计划后要露出返回列表")
        self.assertTrue(case["opened"]["dockHidden"], "查看计划后计划条收起")
        self.assertEqual(case["opened"]["flag"], "1")
        self.assertTrue(case["closed"]["backHidden"], "返回列表后收起返回按钮")
        self.assertFalse(case["closed"]["dockHidden"], "返回列表后计划条回来")

    # 宽窄两档：组件错误时顶部横幅写出组件错误说明与重新检查入口。
    def test_runtime_error_shows_component_banner(self):
        after = SMOKE_SETUP + r"""
S.runtime.error = "worker_missing";
render();
out.push({ banner: $("#banners").innerHTML, band: S.band });
"""
        for size, band in BANDS:
            with self.subTest(band=band):
                case = run_native_smoke([], after=after, size=size)["after"][0]
                self.assertEqual(case["band"], band)
                self.assertIn("程序组件缺失", case["banner"])
                self.assertIn("重新检查", case["banner"])

if __name__ == "__main__":
    unittest.main()
