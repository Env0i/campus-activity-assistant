#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面可靠性的行为回归：驱动生产 app.js 的事件入口，不调用内部 paint 函数。

覆盖：
    R08 每轮 check 用结构化 clock 替换旧状态（warn → ok → unknown）
    R11 旧轮迟到事件不得覆盖新轮；开始请求超时只对账、不重发
    R12 空闲时标题/快捷选择/LED 用同一个 nextOpen 目标
    R13 次数按「已提交 N/M 次」显示，0 明确「不限次数」
    R20 演示模式必须自己显形，不伪装登录有效

每个用例都在独立的 node vm 上下文里跑完整 app.js，入口是真实事件回调
（window.onBackend.*）与真实按钮动作，不直接改写渲染结果。

@author Author
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402


class ClockRoundTests(unittest.TestCase):
    """R08：时钟结论逐轮替换，告警能清、未知不伪装。"""

    def test_warn_then_ok_then_unknown(self):
        res = run_js(r"""
window.onBackend.check({ ok: true, result: "valid",
  clock: { source: "http_date", state: "warn", offset_s: 8,
           uncertainty_s: 1.1, checked_at: 1793016000 } });
const warn = { state: S.clock.state, offset: S.clock.offset };
window.onBackend.check({ ok: true, result: "valid",
  clock: { source: "http_date", state: "ok", offset_s: 0,
           uncertainty_s: 1.1, checked_at: 1793016100 } });
const ok = { state: S.clock.state, offset: S.clock.offset };
window.onBackend.check({ ok: true, result: "valid" });
const unknown = { state: S.clock.state, detail: S.clock.detail };
/* 打开时间详情：学校粗测与 NTP 状态都只在详情里出现 */
toggleClockPop();
const popText = document.querySelector("#clock-pop").innerHTML;
out.push({ warn, ok, unknown, popText });
""")
        data = res[0]
        self.assertEqual(data["warn"]["state"], "warn")
        self.assertEqual(data["warn"]["offset"], 8)
        self.assertIn("粗测", data["popText"], "学校粗测结论只进时间详情")
        self.assertEqual(data["ok"]["state"], "ok")
        self.assertEqual(data["unknown"]["state"], "unknown",
                         "没有结构化结论时必须落未知，不能保留上一轮 warn")
        self.assertNotIn("可能偏", data["popText"],
                         "时间详情不得把上一轮粗测当成当前结论")


class LoginActionTests(unittest.TestCase):
    """登录窗口未完成前不得把旧会话状态画成登录成功。"""

    def test_relogin_pending_and_cancel_preserve_expired_state(self):
        res = run_js(r'''
S.login.present = true;
S.login.result = "expired";
S.login.ok = false;
window.pywebview = {api: {login: () => Promise.resolve({ok: true, queued: true})}};
doLogin();
const pending = {pending: S.login.loginPending,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state};
window.onBackend.done({kind: "login", ok: false, reason: "窗口被关掉了"});
out.push(pending, {pending: S.login.loginPending,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state,
  result: document.querySelector("#result").innerHTML});
''')
        pending, after = res
        self.assertTrue(pending["pending"])
        self.assertEqual(pending["text"], "登录中…")
        self.assertEqual(pending["state"], "pending")
        self.assertFalse(after["pending"])
        self.assertEqual(after["text"], "登录已失效")
        self.assertEqual(after["state"], "bad")
        self.assertIn("登录窗口被关掉了", after["result"])

    def test_unknown_payload_clears_stale_warn(self):
        res = run_js(r"""
window.onBackend.check({ ok: true, result: "valid",
  clock: { source: "http_date", state: "warn", offset_s: 12,
           uncertainty_s: 1.0, checked_at: 1793016000 } });
window.onBackend.check({ ok: false, result: "unknown" });   // 旧载荷，没有 clock
out.push({ state: S.clock.state, offset: S.clock.offset });
""")
        data = res[0]
        self.assertEqual(data["state"], "unknown")
        self.assertIsNone(data["offset"], "旧结论不能当实时测量继续使用")


class StaleRoundTests(unittest.TestCase):
    """R11：旧轮迟到事件不得覆盖新轮。"""

    def test_stale_check_and_list_events_are_dropped(self):
        res = run_js(r"""
S.round.check = "check-new";
S.round.list = "list-new";
S.login.checking = true;
S.listState = "loading";
window.onBackend.check({ request_id: "check-old", ok: true, result: "valid" });
const afterCheck = { checking: S.login.checking, result: S.login.result };
window.onBackend.activities({ request_id: "list-old", ok: true,
  items: [{ id: "x", name: "旧轮活动", sign_start: "2026-10-26 20:00:00",
            sign_end: "2026-10-26 21:00:00", act_start: "2026-10-27 09:00:00",
            act_end: "2026-10-27 11:00:00", signed: false }] });
const afterList = { state: S.listState, count: S.items.length };
window.onBackend.check({ request_id: "check-new", ok: true, result: "valid" });
window.onBackend.activities({ request_id: "list-new", ok: true,
  items: [{ id: "y", name: "新轮活动", sign_start: "2026-10-26 20:00:00",
            sign_end: "2026-10-26 21:00:00", act_start: "2026-10-27 09:00:00",
            act_end: "2026-10-27 11:00:00", signed: false }] });
const settled = { checking: S.login.checking, state: S.listState,
                  names: S.items.map((item) => item.name) };
out.push({ afterCheck, afterList, settled });
""")
        data = res[0]
        self.assertTrue(data["afterCheck"]["checking"], "旧轮 check 不得结束新轮的检查中")
        self.assertIsNone(data["afterCheck"]["result"])
        self.assertEqual(data["afterList"]["count"], 0, "旧轮列表不得写入")
        self.assertEqual(data["afterList"]["state"], "loading")
        self.assertFalse(data["settled"]["checking"])
        self.assertEqual(data["settled"]["state"], "ready")
        self.assertEqual(data["settled"]["names"], ["新轮活动"])


class NextOpenConsistencyTests(unittest.TestCase):
    """R12：有已开放场次时，空闲板面的目标与 LED 必须指向同一场。"""

    def test_open_target_wins_over_future_countdown(self):
        res = run_js(r"""
/* 样本的开放/截止是固定日期，当前时刻也必须固定，不能过23点就让样本自动截止。 */
setBusinessNow(toTs("2026-10-26 20:00:00") * 1000);
window.LED_UI = { renderLed: (el, text) => { S.__led = text; } };
const openItem = { id: "open", name: "已开放活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 09:00:00",
  act_end: "2026-10-27 11:00:00", signed: false, checkin_required: null,
  checkout_required: null };
const futureItem = { id: "future", name: "未来活动", sign_start: "2026-10-27 20:00:00",
  sign_end: "2026-10-27 21:00:00", act_start: "2026-10-28 09:00:00",
  act_end: "2026-10-28 11:00:00", signed: false, checkin_required: null,
  checkout_required: null };
S.items = [openItem, futureItem];
S.byId = new Map([["open", openItem], ["future", futureItem]]);
/* 计划栏 1:1（draft-panel I）：原型 draft 段 led 在列表没加载时只写「活动未加载」，样本要先标列表已加载 */
S.listState = "ready";
const next = nextOpen();
const target = boardTargetItem();
paintLed();
out.push({ best: next.best, bestId: next.bestId, openId: next.openId,
           target: target && target.id,
           led: S.__led,
           metric: document.querySelector("#led-label b").textContent });
""")
        data = res[0]
        self.assertIsNone(data["best"], "已开放时不得再给未来场倒计时")
        self.assertEqual(data["bestId"], "open")
        self.assertEqual(data["target"], "open", "标题目标与快捷选择必须同源")
        self.assertEqual(data["led"], "00:00:00", "已开放不得显示未来场倒计时")
        self.assertEqual(data["metric"], "现在")


class AttemptsDisplayTests(unittest.TestCase):
    """R13：有限次数显示 N/M，0 明确不限。"""

    def test_limited_and_unlimited_copy(self):
        res = run_js(r"""
const limited = submittingDetail({ status: "submitting", attempts: 1, max_attempts: 3 });
const unlimited = submittingDetail({ status: "submitting", attempts: 2, max_attempts: 0 });
const before = submittingDetail({ status: "submitting", attempts: 0, max_attempts: 5 });
out.push({ limited, unlimited, before });
""")
        data = res[0]
        # 计划栏 1:1（run-panel F）：写法照原型 card「已提交 N 次（上限 M 次）」，不再是「N/M 次」
        self.assertIn("已提交 1 次（上限 3 次）", data["limited"])
        self.assertIn("已提交 2 次（不限次数）", data["unlimited"])
        self.assertIn("上限 5 次", data["before"])
        self.assertNotIn("第 ", data["limited"], "不能只写「第 N 次」，用户看不到上限")


class StartReconcileTests(unittest.TestCase):
    """R11：开始请求失联时只对账，不重发；已接纳要恢复停止入口。"""

    def test_accepted_reconcile_restores_plan(self):
        res = run_js(r"""
window.pywebview = { api: {
  start_request_state: () => Promise.resolve({ ok: true, state: "accepted", plan_id: "p1" }),
  bootstrap: () => Promise.resolve({ plan: { plan_id: "p1", status: "running", tasks: [] } }),
} };
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
S.startRequest = { id: "rid", state: "submitting", timer: null, reconcile: 0 };
S.starting = true;
reconcileStart("rid");
await flush();
out.push({ planId: S.plan.id, busy: S.busy, starting: S.starting,
           state: S.startRequest.state,
           stopDisabled: document.querySelector("#btn-stop").disabled });
""")
        data = res[0]
        self.assertEqual(data["planId"], "p1")
        self.assertTrue(data["busy"], "已接纳必须回到运行态")
        self.assertFalse(data["starting"], "对账成功后释放开始标志")
        self.assertEqual(data["state"], "accepted")
        self.assertFalse(data["stopDisabled"], "必须有停止入口")

    def test_unknown_reconcile_keeps_start_blocked(self):
        res = run_js(r"""
window.pywebview = { api: {
  start_request_state: () => Promise.resolve({ ok: true, state: "unknown" }),
} };
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
S.startRequest = { id: "rid", state: "submitting", timer: null, reconcile: 0 };
S.starting = true;
reconcileStart("rid");
await flush();
out.push({ starting: S.starting, state: S.startRequest.state,
           title: document.querySelector("#result").innerHTML,
           disabled: document.querySelector("#btn-plan").disabled });
""")
        data = res[0]
        self.assertTrue(data["starting"], "没有结论时不得开放第二次开始")
        self.assertEqual(data["state"], "unknown")
        self.assertIn("结果未确认", data["title"])
        self.assertTrue(data["disabled"])


class DemoModeTests(unittest.TestCase):
    """R20：演示模式显式标识，不伪装成登录有效。"""

    def test_demo_pill_is_explicit(self):
        res = run_js(r"""
S.demo = true;
setLogin(null, null, null);
paintLogin();
out.push({ text: document.querySelector("#pill-text").textContent,
           state: document.querySelector("#pill").dataset.state });
""")
        data = res[0]
        self.assertEqual(data["text"], "演示模式")
        self.assertEqual(data["state"], "demo")


class LoginPresentTests(unittest.TestCase):
    """C07 回归：session_present 的 null 不能被 !! 成「首次未登录」。"""

    def test_null_is_unknown_not_false(self):
        res = run_js(r"""
out.push({
  demo: loginPresent({ session_present: null }, true),
  nullPlain: loginPresent({ session_present: null }, false),
  missing: loginPresent({}, false),
  yes: loginPresent({ session_present: true }, false),
  no: loginPresent({ session_present: false }, false),
});
""")
        data = res[0]
        # undefined 经 JSON 序列化会丢键：用「键不存在」表达未知
        self.assertNotIn("demo", data, "演示模式的会话必须是未知，不能判成未登录")
        self.assertNotIn("nullPlain", data)
        self.assertNotIn("missing", data)
        self.assertTrue(data["yes"])
        self.assertFalse(data["no"])


class ReconcileTerminalTests(unittest.TestCase):
    """C05：15 秒内就结束的计划不得被对账复活成运行中。"""

    def test_finished_plan_restores_terminal_not_busy(self):
        res = run_js(BOARD_VIEW_JS + r"""
window.pywebview = { api: {
  start_request_state: () => Promise.resolve({
    ok: true, state: "accepted", plan_id: "p1", running: false, finished: true,
    snapshot: { status: "completed", summary: { total: 1, counts: { success: 1 } },
                tasks: [{ task_id: "t1", activity_id: "a1", name: "活动",
                          status: "success", attempts: 1 }] },
  }),
  bootstrap: () => Promise.resolve({}),
} };
S.startRequest = { id: "rid", state: "submitting", timer: null, reconcile: 0 };
S.starting = true;
reconcileStart("rid");
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push({ busy: S.busy, starting: S.starting, status: S.plan.status,
           tasks: S.plan.tasks.size,
           title: __boardView().title });
""")
        data = res[0]
        self.assertFalse(data["busy"], "已结束的计划不得保持运行态")
        self.assertFalse(data["starting"])
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["tasks"], 1)
        # 结论在计划栏标题（result-panel D：全部报上 → 「报名计划完成」）
        self.assertEqual(data["title"], "报名计划完成")


class SkippedRefreshTests(unittest.TestCase):
    """C06：去重跳过要接续原 ID，并把已完成结果直接落地。"""
    def test_skipped_check_rebinds_original_id(self):
        res = run_js(r"""
S.round.check = "new";
S.login.checking = true;
settleSynchronous({ ok: true, queued: true, skipped: "已在检查登录态",
                    request_id: "orig" }, "check");
out.push({ round: S.round.check, checking: S.login.checking });
""")
        data = res[0]
        self.assertEqual(data["round"], "orig", "必须接续原请求 ID")
        self.assertTrue(data["checking"], "原请求还在途，继续等它")

    def test_skipped_with_finished_result_applies(self):
        res = run_js(r"""
S.round.check = "new";
S.login.checking = true;
settleSynchronous({ ok: true, skipped: "已在检查登录态", request_id: "orig",
  result: { request_id: "orig", ok: true, result: "valid", hours_left: 5,
            session_present: true } }, "check");
out.push({ round: S.round.check, checking: S.login.checking,
           result: S.login.result });
""")
        data = res[0]
        self.assertEqual(data["round"], "orig")
        self.assertFalse(data["checking"], "已完成的终态必须当场落地")
        self.assertEqual(data["result"], "valid")


class SilentReloginUiTests(unittest.TestCase):
    """静默自动登录（计划 20261111）：电脑能自己登录时，用户不该看见「登录已失效」。"""

    def test_expired_check_stays_silent_until_the_relogin_finishes(self):
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: true, result: "valid" });
window.onBackend.check({ ok: false, result: "expired", reason: "4001", recovering: true });
const silent = { text: document.querySelector("#pill-text").textContent,
                 state: document.querySelector("#pill").dataset.state,
                 banners: document.querySelector("#banners").innerHTML };
window.onBackend.phone_relogin({ state: "waiting_code", mode: "auto", live: true,
  origin: "auto", flow_id: "f1", challenge_id: "c1", attempts: 1, image: "" });
const running = { text: document.querySelector("#pill-text").textContent,
                  state: document.querySelector("#pill").dataset.state,
                  banners: document.querySelector("#banners").innerHTML };
window.onBackend.check({ ok: true, result: "valid" });
const done = { text: document.querySelector("#pill-text").textContent,
               state: document.querySelector("#pill").dataset.state };
out.push({ silent, running, done });
""")
        data = res[0]
        self.assertEqual(data["silent"]["text"], "自动登录中…")
        self.assertEqual(data["silent"]["state"], "pending")
        self.assertNotIn("登录已失效", data["silent"]["banners"],
                         "静默恢复期间不该出现失效横幅")
        self.assertEqual(data["running"]["state"], "pending", "自动登录期间保持自动登录中")
        self.assertNotIn("登录已失效", data["running"]["banners"])
        self.assertNotEqual(data["done"]["state"], "bad")
        self.assertNotEqual(data["done"]["text"], "登录已失效")

    def test_first_silent_failure_puts_the_reminder_back(self):
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
const silent = document.querySelector("#pill-text").textContent;
window.onBackend.check({ ok: false, result: "expired", recovering: false,
  recover_block: "retry_pending" });
out.push({ silent,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state,
  banners: document.querySelector("#banners").innerHTML,
  auto: !!S.autoLogin });
""")
        data = res[0]
        self.assertEqual(data["silent"], "自动登录中…")
        self.assertEqual(data["text"], "登录已失效", "第一次静默失败后要回到失效提醒")
        self.assertEqual(data["state"], "bad")
        self.assertIn("登录已失效", data["banners"])
        self.assertFalse(data["auto"])

    def test_handoff_restores_the_reminder_and_asks_for_the_captcha(self):
        res = run_js(r"""
S.login.present = true;
S.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
if (window.PhonePanel && window.PhonePanel.state) {
  window.PhonePanel.state.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
}
let beginCalls = 0;
window.pywebview = { api: { relogin_begin: () => { beginCalls += 1;
  return Promise.resolve({ ok: true, flow_id: "f2" }); } } };
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "auto", flow_id: "f1", challenge_id: "c1", attempts: 3, handoff: true,
  image: "data:image/png;base64,AAA" });
const handoff = { text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state,
  banners: document.querySelector("#banners").innerHTML,
  auto: !!S.autoLogin, mark: !!S.login.handoff };
document.querySelector("#btn-login").click();
out.push({ handoff, beginCalls, step: S.relogin.step, flow: S.relogin.flowId,
  prompt: document.querySelector("#rl-err").textContent,
  img: document.querySelector("#rl-cap-img").src });
""")
        data = res[0]
        self.assertEqual(data["handoff"]["text"], "登录已失效")
        self.assertEqual(data["handoff"]["state"], "bad")
        self.assertIn("登录已失效", data["handoff"]["banners"])
        self.assertFalse(data["handoff"]["auto"], "转人工后不能还显示自动登录中")
        self.assertTrue(data["handoff"]["mark"])
        self.assertEqual(data["beginCalls"], 0, "已有进行中的一场，不能另开一场")
        self.assertEqual(data["step"], "cap")
        self.assertEqual(data["flow"], "f1")
        self.assertEqual(data["prompt"], "自动识别 3 次没认对，请输入验证码。")
        self.assertTrue(data["img"].endswith("AAA"))

    def test_saved_account_goes_straight_to_the_captcha_without_confirming(self):
        res = run_js(r"""
S.login.present = true;
S.login.result = "expired";
S.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
if (window.PhonePanel && window.PhonePanel.state) {
  window.PhonePanel.state.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
}
let beginCalls = 0;
const asked = [];
window.pywebview = { api: {
  relogin_begin: () => { beginCalls += 1; return Promise.resolve({ ok: true, flow_id: "f-new" }); },
  relogin_auto_once: () => { asked.push("auto"); return Promise.resolve({ ok: true }); } } };
document.querySelector("#btn-login").click();
const opened = { step: S.relogin.step, open: S.relogin.open,
                 confirmHidden: document.querySelector("#rl-confirm").hidden };
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "manual", flow_id: "f-new", challenge_id: "c1", attempts: 1,
  image: "data:image/png;base64,AAA" });
out.push({ opened, beginCalls, asked, step: S.relogin.step,
  capHidden: document.querySelector("#rl-cap").hidden });
""")
        data = res[0]
        self.assertTrue(data["opened"]["open"])
        self.assertTrue(data["opened"]["confirmHidden"], "不再先问「自动登录一次？」")
        self.assertEqual(data["opened"]["step"], "wait")
        self.assertEqual(data["beginCalls"], 1, "保存过账号就直接开一场")
        self.assertEqual(data["asked"], [], "不再调用relogin_auto_once")
        self.assertEqual(data["step"], "cap")
        self.assertFalse(data["capHidden"])

    def test_wrong_code_only_swaps_the_image(self):
        res = run_js(r"""
S.login.present = true;
S.login.result = "expired";
S.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
if (window.PhonePanel && window.PhonePanel.state) {
  window.PhonePanel.state.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
}
window.pywebview = { api: { relogin_begin: () => Promise.resolve({ ok: true, flow_id: "f1" }) } };
document.querySelector("#btn-login").click();
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "manual", flow_id: "f1", challenge_id: "c1", attempts: 1,
  image: "data:image/png;base64,AAA" });
document.querySelector("#rl-code").value = "ZZZZ";
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "manual", flow_id: "f1", challenge_id: "c2", attempts: 2,
  image: "data:image/png;base64,BBB" });
out.push({ step: S.relogin.step, img: document.querySelector("#rl-cap-img").src,
  code: document.querySelector("#rl-code").value,
  userHidden: document.querySelector("#rl-login").hidden,
  err: document.querySelector("#rl-err").textContent });
""")
        data = res[0]
        self.assertEqual(data["step"], "cap", "验证码错只换图，不退出这一屏")
        self.assertTrue(data["img"].endswith("BBB"))
        self.assertEqual(data["code"], "", "换图后要把上一张的输入清掉")
        self.assertTrue(data["userHidden"], "不回到账号密码表单")
        self.assertFalse(data["err"], "验证码错是平常事，不显示成错误")

    def test_network_error_can_be_retried_with_a_new_captcha(self):
        res = run_js(r"""
S.login.present = true;
S.login.result = "expired";
S.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
if (window.PhonePanel && window.PhonePanel.state) {
  window.PhonePanel.state.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
}
let beginCalls = 0;
window.pywebview = { api: { relogin_begin: () => { beginCalls += 1;
  return Promise.resolve({ ok: true, flow_id: "f" + beginCalls }); } } };
document.querySelector("#btn-login").click();
window.onBackend.phone_relogin({ state: "failed", live: false, origin: "manual",
  flow_id: "f1", safe_error: "timeout" });
const failed = { step: S.relogin.step, text: document.querySelector("#rl-msg-text").textContent };
document.querySelector("#btn-rl-done").click();
document.querySelector("#btn-login").click();
out.push({ failed, again: { step: S.relogin.step, beginCalls,
  userHidden: document.querySelector("#rl-login").hidden } });
""")
        data = res[0]
        self.assertEqual(data["failed"]["step"], "msg")
        self.assertIn("可以再试一次", data["failed"]["text"])
        self.assertEqual(data["again"]["step"], "wait")
        self.assertEqual(data["again"]["beginCalls"], 2, "再试一次要真开新的一场")
        self.assertTrue(data["again"]["userHidden"], "不回到账号密码表单")

    def test_bad_password_goes_to_the_bad_step_not_a_generic_message(self):
        res = run_js(r"""
S.login.present = true;
S.login.result = "expired";
S.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
if (window.PhonePanel && window.PhonePanel.state) {
  window.PhonePanel.state.advanced = { credential: { saved: true, ocr_ready: true, paused: false } };
}
window.pywebview = { api: { relogin_begin: () => Promise.resolve({ ok: true, flow_id: "f1" }) } };
document.querySelector("#btn-login").click();
window.onBackend.phone_relogin({ state: "failed", live: false, origin: "manual",
  flow_id: "f1", safe_error: "bad_password" });
out.push({ step: S.relogin.step, badHidden: document.querySelector("#rl-bad").hidden });
""")
        data = res[0]
        self.assertEqual(data["step"], "bad", "学校说密码不对要进「保存的密码不对」那一步")
        self.assertFalse(data["badHidden"])

    def test_handoff_log_matches_the_attempt_count(self):
        def handoff_log(attempts):
            res = run_js(r"""
S.login.present = true;
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "auto", flow_id: "f1", challenge_id: "c1", attempts: __N__, handoff: true,
  image: "data:image/png;base64,AAA" });
out.push({ log: S.recentLogs.join("\n") });
""".replace("__N__", str(attempts)))
            return res[0]["log"]

        once = handoff_log(1)
        self.assertNotIn("3 次", once, "只认错一次就转人工，运行记录不能说「3 次」")
        self.assertIn("电脑没认出验证码", once)
        third = handoff_log(3)
        self.assertIn("自动识别 3 次没认对", third)


# 计划栏结果页（计划 20261106-plan-panel 的 result-panel，P1 / P8）：计划结论不再写进 #result 条，
# 改由计划栏的标签、标题、副行和五类大数字承担（原型 Main.dc.html 渲染函数 res 段）。
# 用例从这里读同一份结论；#result 只剩登录、开始请求这类非计划提示。
BOARD_VIEW_JS = r"""
const __boardView = () => ({
  tag: document.querySelector("#board-tag-text").textContent,
  title: document.querySelector("#selected").textContent,
  text: document.querySelector("#board-text").textContent,
  stats: document.querySelector("#plan-stats").hidden ? "" : document.querySelector("#plan-stats").innerHTML,
  ledHidden: !!document.querySelector("#led-box").hidden,
  resultHidden: !!document.querySelector("#result").hidden,
});
"""


def _stats(view):
    """结果页大数字 → {标签: 数}（只含显示出来的格子）。"""
    return {label: int(n) for n, label in
            re.findall(r"<strong>(\d+)</strong><span>([^<]+)</span>", view["stats"])}


def _said(view):
    """结果页标签、标题、副行连成一句，便于查用词。"""
    return " | ".join([view["tag"], view["title"], view["text"]])


SELECTED_SNIPPET = r"""
window.LED_UI = { renderLed: (el, text, tone) => { S.__led = [String(text), String(tone)]; } };
const __labels = [];
const __realLabel = paintLedLabel;
paintLedLabel = (prefix, value) => { __labels.push(String(prefix)); return __realLabel(prefix, value); };
window.onBackend.plan({ plan_id: "p1", status: "ready", tasks: [] });
"""


class UnknownOutcomeUITests(unittest.TestCase):
    """F04：未确认/鉴权未知贯穿任务卡、计划总结与大屏（与 stopReasonText 同源）。"""

    def _run(self, tasks, status, counts):
        body = BOARD_VIEW_JS + SELECTED_SNIPPET
        for task in tasks:
            body += "window.onBackend.task(%s);\n" % _js(task)
        body += ("window.onBackend.plan_done({ plan_id: \"p1\", status: %s, "
                 "summary: { total: %d, counts: %s } });\n"
                 % (_js(status), len(tasks), _js(counts)))
        body += r"""
out.push({
  cards: document.querySelector("#plan-tasks").innerHTML,
  result: document.querySelector("#result").innerHTML,
  board: __boardView(),
  led: S.__led,
  labels: __labels,
});
"""
        return run_js(body)[0]

    def test_unconfirmed_is_pending_not_failure(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "讲座",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "unconfirmed", "attempts": 3,
              "reason": "本机监督到期，已收走本场进程"}],
            "failed", {"failed": 1})
        self.assertIn("待核对", data["cards"])
        self.assertIn("3 次", data["cards"])
        self.assertNotIn("没抢到", data["cards"])
        # 结论从 #result 条搬到计划栏（result-panel D「没报上、有待核对」），说明原话在任务卡（G）
        board = data["board"]
        self.assertTrue(board["resultHidden"], "计划结束不再往 #result 条写结论")
        self.assertEqual(_stats(board), {"待核对": 1}, "大数字与任务卡同一分类")
        self.assertEqual(board["tag"], "需确认")
        self.assertEqual(board["title"], "计划已结束，有 1 场需确认")
        self.assertIn("不会自动重发", board["text"])
        self.assertIn("没拿到确定回应", data["cards"])
        self.assertNotIn("没抢到", _said(board))
        self.assertNotIn("都没抢到", _said(board))
        # 原型 res.hasLed 只在全成功 / 全失败时为真：待核对不亮 LED，更不亮失败叉
        self.assertTrue(board["ledHidden"], "待核对不显示结论 LED")
        self.assertNotEqual(data["led"], ["✕", "red"], "待核对不得亮失败叉")

    def test_auth_unavailable_does_not_push_relogin(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "讲座",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "auth_unavailable", "attempts": 0,
              "reason": "接口异常：URLError"}],
            "failed", {"failed": 1})
        self.assertIn("本场没有提交", data["cards"])
        self.assertNotIn("没抢到", data["cards"])
        # 计划 20261106-plan-panel decisions：auth_unavailable 在结果页计入「报名未成功」，卡片标签保留「未提交」；
        # 原因原话只在任务卡（结果页副行是原型的「每场的原因都列在下面。」）
        board = data["board"]
        self.assertIn("未提交", data["cards"], "卡片标签保留「未提交」（代码独有）")
        self.assertEqual(_stats(board), {"报名未成功": 1}, "没提交的场次不得算成待核对")
        self.assertIn("登录状态无法确认", data["cards"])
        self.assertIn("检查网络", data["cards"])
        for said in (_said(board), data["cards"]):
            self.assertNotIn("登录失效", said)
            self.assertNotIn("请重新登录", said)
        # 只有这一场且确定没提交：结果页走原型 res 的「其余」分支（未成功、小 LED ✕），见 plan_amendments
        self.assertEqual(board["title"], "报名计划没有成功")
        self.assertEqual(data["led"], ["✕", "red"])

    def test_mixed_success_and_unknown_is_partial(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "成功场",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "success", "stop_reason": "success", "attempts": 1, "reason": "报名成功"},
             {"plan_id": "p1", "task_id": "t2", "activity_id": "a2", "name": "待核对场",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "unconfirmed", "attempts": 2,
              "reason": "响应丢失"}],
            "partial", {"success": 1, "failed": 1})
        # 结论在计划栏（result-panel D「有报上的、也有别的」）
        board = data["board"]
        self.assertEqual(_stats(board), {"已报名": 1, "待核对": 1})
        self.assertEqual(board["title"], "报名计划部分完成")
        self.assertEqual(board["text"], "有 1 场需要到活动页核对，结果以学校为准。")
        self.assertNotIn("都没抢到", _said(board))

    def test_confirmed_failure_and_unknown_are_counted_separately(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "名额满",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "max_attempts", "attempts": 5,
              "reason": "报名人数已满"},
             {"plan_id": "p1", "task_id": "t2", "activity_id": "a2", "name": "待核对场",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "unconfirmed", "attempts": 1,
              "reason": "响应丢失"}],
            "failed", {"failed": 2})
        # 结论在计划栏（result-panel C / D）：两类分开计数，有待核对就走「需确认」，不画确定失败
        board = data["board"]
        self.assertEqual(_stats(board), {"报名未成功": 1, "待核对": 1})
        self.assertEqual(board["tag"], "需确认")
        self.assertIn("待核对", data["cards"])
        self.assertTrue(board["ledHidden"], "有待核对就不亮结论 LED")
        self.assertNotEqual(data["led"], ["✕", "red"])

    def test_all_confirmed_failures_keep_definite_copy(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "场一",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "retry_duration", "attempts": 2,
              "reason": "名额已满"},
             {"plan_id": "p1", "task_id": "t2", "activity_id": "a2", "name": "场二",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "failed", "stop_reason": "sign_end", "attempts": 1,
              "reason": "报名已截止"}],
            "failed", {"failed": 2})
        board = data["board"]
        self.assertEqual(board["title"], "报名计划没有成功")
        self.assertEqual(board["text"], "每场的原因都列在下面。")
        self.assertEqual(_stats(board), {"报名未成功": 2})
        self.assertNotIn("待核对", _said(board) + board["stats"])
        self.assertFalse(board["ledHidden"], "全部确认失败显示小 LED（原型 res.hasLed）")
        self.assertEqual(data["led"], ["✕", "red"], "全部确认失败才允许亮失败结论")

    def test_stopped_plan_keeps_its_own_copy(self):
        data = self._run(
            [{"plan_id": "p1", "task_id": "t1", "activity_id": "a1", "name": "场一",
              "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
              "status": "canceled", "stop_reason": "user_stopped", "attempts": 0,
              "reason": "你取消了这一场"}],
            "stopped", {"canceled": 1})
        board = data["board"]
        self.assertEqual(board["tag"], "已停止")
        self.assertEqual(board["title"], "报名计划已停止")
        self.assertNotIn("待核对", _said(board) + board["stats"])
        self.assertIn("保留原状态", board["text"])
        self.assertEqual(_stats(board), {"已取消": 1})
        self.assertTrue(board["ledHidden"], "停止不显示结论 LED（原型 res.hasLed）")
        self.assertNotEqual(data["led"], ["✕", "red"])

    def test_f5_restore_keeps_same_conclusion_and_attempts(self):
        res = run_js(r"""
window.LED_UI = { renderLed: (el, text, tone) => { S.__led = [String(text), String(tone)]; } };
ingestBootstrapPlan({ plan: { plan_id: "p9", status: "failed", tasks: [
  { task_id: "t1", activity_id: "a1", name: "待核对场",
    sign_start: "2026-10-26 09:00:00", sign_end: "2026-10-26 23:00:00",
    status: "failed", stop_reason: "unconfirmed", attempts: 4,
    reason: "响应丢失" } ] } });
const task = S.plan.tasks.get("t1");
out.push({ attempts: task.attempts, stop: task.stop_reason,
           cards: document.querySelector("#plan-tasks").innerHTML });
""")
        data = res[0]
        self.assertEqual(data["attempts"], 4, "恢复后次数不能归零")
        self.assertEqual(data["stop"], "unconfirmed")
        self.assertIn("4 次", data["cards"])
        self.assertIn("待核对", data["cards"])


def _js(value):
    import json
    return json.dumps(value, ensure_ascii=False)


TIMER_HARNESS = r"""
const __timers = [];
let __seq = 1;
setTimeout = (fn, ms) => { __timers.push({ id: __seq, fn: fn, ms: ms }); return __seq++; };
clearTimeout = (id) => {
  const at = __timers.findIndex((t) => t.id === id);
  if (at >= 0) __timers.splice(at, 1);
};
const __fire = (ms) => {
  const hit = __timers.find((t) => t.ms === ms);
  if (hit) { clearTimeout(hit.id); hit.fn(); }
  return !!hit;
};
const __flush = async (n = 6) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
"""


class StartReconcileQueryTests(unittest.TestCase):
    """F05：对账自身有 5 秒期限；旧代次与旧请求的迟到回复不得落地。"""

    def test_never_settled_query_times_out_at_5s(self):
        res = run_js(TIMER_HARNESS + r"""
window.pywebview = { api: {
  start_request_state: () => new Promise(() => {}),
  bootstrap: () => Promise.resolve({}),
} };
S.startRequest = { id: "rid", state: "submitting", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
S.starting = true;
reconcileStart("rid");
const fired = __fire(5000);
out.push({ fired: fired, state: S.startRequest.state, starting: S.starting,
           html: document.querySelector("#result").innerHTML });
""")
        data = res[0]
        self.assertTrue(data["fired"], "5 秒期限必须真的挂上计时器")
        self.assertEqual(data["state"], "unknown")
        self.assertTrue(data["starting"], "对账超时也必须锁住重复启动")
        self.assertIn("结果未确认", data["html"])
        self.assertIn("5 秒", data["html"])
        self.assertIn("重新确认", data["html"])

    def test_reconfirm_is_read_only(self):
        res = run_js(TIMER_HARNESS + r"""
const calls = { start_plan: 0, query: 0 };
window.pywebview = { api: {
  start_request_state: () => { calls.query += 1; return new Promise(() => {}); },
  start_plan: () => { calls.start_plan += 1; return Promise.resolve({ ok: true }); },
  bootstrap: () => Promise.resolve({}),
} };
S.startRequest = { id: "rid", state: "submitting", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
S.starting = true;
reconcileStart("rid");
__fire(5000);
const btn = document.querySelector("#result").querySelector("#result-action");
btn.click();
out.push({ calls: calls, gen: S.startRequest.gen, starting: S.starting });
""")
        data = res[0]
        self.assertEqual(data["calls"]["query"], 2, "重新确认只做只读查询")
        self.assertEqual(data["calls"]["start_plan"], 0, "绝不重发 start_plan")
        self.assertEqual(data["gen"], 2)
        self.assertTrue(data["starting"])

    def test_old_generation_reply_is_ignored(self):
        res = run_js(TIMER_HARNESS + r"""
const pending = [];
window.pywebview = { api: {
  start_request_state: () => new Promise((resolve) => pending.push(resolve)),
  bootstrap: () => Promise.resolve({}),
} };
S.startRequest = { id: "rid", state: "submitting", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
S.starting = true;
reconcileStart("rid");            // 第 1 代
__fire(5000);                     // 超时 -> unknown
reconcileStart("rid");            // 第 2 代
pending[0]({ ok: true, state: "accepted", plan_id: "p-old", running: true });
await __flush();
const afterOld = { plan: S.plan.id, state: S.startRequest.state };
pending[1]({ ok: false, state: "rejected", text: "本机拒绝" });
await __flush();
out.push({ afterOld: afterOld, plan: S.plan.id, state: S.startRequest.state,
           starting: S.starting, html: document.querySelector("#result").innerHTML });
""")
        data = res[0]
        self.assertFalse(data["afterOld"]["plan"], "旧代次的 accepted 不得建计划")
        self.assertEqual(data["afterOld"]["state"], "reconciling")
        self.assertEqual(data["state"], "rejected", "当前代次的结论必须落地")
        self.assertFalse(data["starting"])

    def test_late_accept_does_not_replace_later_plan(self):
        res = run_js(TIMER_HARNESS + r"""
const pending = [];
window.pywebview = { api: {
  start_request_state: () => new Promise((resolve) => pending.push(resolve)),
  bootstrap: () => Promise.resolve({}),
} };
S.plan = { id: "p-later", status: "running", tasks: new Map(), armedAt: 0 };
S.startRequest = { id: "rid", state: "submitting", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
S.starting = true;
reconcileStart("rid");            // 第 1 代
__fire(5000);                     // 超时 -> unknown
reconcileStart("rid");            // 第 2 代（当前查询）
pending[0]({ ok: true, state: "accepted", plan_id: "p-old", running: true });
await __flush();
out.push({ plan: S.plan.id, state: S.startRequest.state, pending: pending.length });
""")
        data = res[0]
        self.assertEqual(data["plan"], "p-later", "迟到的旧 plan 不得替换当前计划")


class RefreshRoundRaceTests(unittest.TestCase):
    """F05：check/list 终态先于 skipped ack 时必须暂存重放，不能干等 100/130 秒。"""

    def test_check_terminal_before_skipped_ack_replays(self):
        res = run_js(TIMER_HARNESS + r"""
S.round.check = "new";
S.login.checking = true;
window.onBackend.check({ request_id: "old", ok: true, result: "valid",
  session_present: true, hours_left: 5, request_id2: "" });
const cachedSize = S.round.cache.length;
/* 去重 ack 后到：接续回旧 owner，必须立刻重放暂存终态 */
settleSynchronous({ ok: true, skipped: "已在检查登录态", request_id: "old" }, "check");
await __flush();
out.push({ cachedSize: cachedSize, round: S.round.check, checking: S.login.checking,
           result: S.login.result, left: S.round.cache.length });
""")
        data = res[0]
        self.assertEqual(data["cachedSize"], 1, "终态先到必须先暂存")
        self.assertEqual(data["round"], "old")
        self.assertFalse(data["checking"], "重放后必须离开检查中")
        self.assertEqual(data["result"], "valid")
        self.assertEqual(data["left"], 0, "重放后缓存清空")

    def test_check_ack_before_terminal_still_applies(self):
        res = run_js(TIMER_HARNESS + r"""
window.pywebview = { api: {} };
S.login.checking = true;
settleSynchronous({ ok: true, skipped: "已在检查登录态", request_id: "old" }, "check");
window.onBackend.check({ request_id: "old", ok: true, result: "valid",
  session_present: true, hours_left: 7 });
await __flush();
out.push({ round: S.round.check, checking: S.login.checking,
           result: S.login.result });
""")
        data = res[0]
        self.assertEqual(data["round"], "old")
        self.assertFalse(data["checking"])
        self.assertEqual(data["result"], "valid")

    def test_skipped_ack_with_result_applies_without_cache(self):
        res = run_js(TIMER_HARNESS + r"""
S.login.checking = true;
settleSynchronous({ ok: true, skipped: "已在检查登录态", request_id: "old",
  result: { request_id: "old", ok: true, result: "valid", session_present: true } }, "check");
await __flush();
out.push({ checking: S.login.checking, result: S.login.result,
           cached: S.round.cache.length });
""")
        data = res[0]
        self.assertFalse(data["checking"])
        self.assertEqual(data["result"], "valid")
        self.assertEqual(data["cached"], 0)

    def test_list_terminal_before_skipped_ack_replays(self):
        res = run_js(TIMER_HARNESS + r"""
S.round.list = "new-list";
S.listState = "loading";
window.onBackend.activities({ ok: true, request_id: "old-list", items: [
  { id: "a1", name: "活动一", sign_start: "2026-10-27 09:00:00",
    sign_end: "2026-10-27 23:00:00", act_start: "2026-10-28 09:00:00",
    act_end: "2026-10-28 11:00:00", signed: false } ] });
const cached = S.round.cache.length;
settleSynchronous({ ok: true, skipped: "已经在拉活动列表", request_id: "old-list" }, "list");
await __flush();
out.push({ cached: cached, round: S.round.list, state: S.listState,
           items: S.items.length });
""")
        data = res[0]
        self.assertEqual(data["cached"], 1)
        self.assertEqual(data["round"], "old-list")
        self.assertEqual(data["state"], "ready")
        self.assertEqual(data["items"], 1, "列表终态必须当场重放")

    def test_old_terminal_does_not_clear_current_timer(self):
        res = run_js(TIMER_HARNESS + r"""
S.round.check = "new";
S.login.checking = true;
S.round.checkTimer = setTimeout(() => { S.login.checking = false; }, 100000);
window.onBackend.check({ request_id: "old", ok: true, result: "valid" });
const armed = __timers.filter((t) => t.ms === 100000).length;
__fire(100000);
out.push({ armed: armed, checking: S.login.checking });
""")
        data = res[0]
        self.assertEqual(data["armed"], 1, "旧轮终态不得清掉新一轮的兜底计时器")
        self.assertFalse(data["checking"])

    def test_duplicate_terminal_is_idempotent(self):
        res = run_js(TIMER_HARNESS + r"""
S.round.check = "rid";
window.onBackend.check({ request_id: "rid", ok: true, result: "valid" });
window.onBackend.check({ request_id: "rid", ok: false, result: "expired" });
out.push({ result: S.login.result, ok: S.login.ok });
""")
        data = res[0]
        self.assertEqual(data["result"], "valid", "同一终态重复到达只生效一次")
        self.assertTrue(data["ok"])

    def test_cache_bound_and_expiry(self):
        res = run_js(TIMER_HARNESS + r"""
for (let i = 0; i < 20; i += 1) cacheRoundPayload("check", "id" + i, { n: i });
const size = S.round.cache.length;
const first = S.round.cache[0];
first.at = Date.now() - 200000;      // 超过 130 秒
const expired = takeRoundPayload("check", first.id);
const alive = takeRoundPayload("check", "id19");
out.push({ size: size, expired: expired === null, alive: alive });
""")
        data = res[0]
        self.assertEqual(data["size"], 16, "缓存最多 16 项")
        self.assertTrue(data["expired"], "超过 130 秒的终态不得重放")
        self.assertIsNotNone(data["alive"])


class CrossRoundConsumptionTests(unittest.TestCase):
    """FR04：请求幂等与刷新轮次分成两层——同 owner 可以收口新轮次，副作用仍幂等。"""

    LOG_COUNT = ("() => document.querySelector('#log').childElementCount")

    def test_same_owner_terminal_replays_in_new_round(self):
        res = run_js(TIMER_HARNESS + r"""
const logs = () => document.querySelector('#log').childElementCount;
S.round.check = "owner-1";
bumpRoundGeneration("check");
window.onBackend.check({ request_id: "owner-1", ok: true, result: "valid",
  session_present: true, hours_left: 5 });
const first = logs();
/* 新一轮：代次递增、本轮 id 换新，但后端回的还是同一个 owner */
bumpRoundGeneration("check");
S.round.check = "check-new";
S.login.checking = true;
settleSynchronous({ ok: true, queued: true, skipped: "已在检查登录态",
  request_id: "owner-1",
  result: { request_id: "owner-1", ok: true, result: "valid",
            session_present: true, hours_left: 5 } }, "check");
await __flush();
out.push({ first: first, after: logs(), checking: S.login.checking,
           round: S.round.check, result: S.login.result });
""")
        data = res[0]
        self.assertFalse(data["checking"], "新一轮必须立刻用同一 owner 的既有结果收口")
        self.assertEqual(data["round"], "owner-1")
        self.assertEqual(data["result"], "valid")
        self.assertEqual(data["after"], data["first"],
                         "状态要恢复，但同一句日志不能写两遍")

    def test_list_owner_replays_in_new_round(self):
        res = run_js(TIMER_HARNESS + r"""
const row = { id: "a1", name: "活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "", act_end: "", place: "报告厅",
  signed: false };
S.round.list = "L1";
bumpRoundGeneration("list");
applyActivities({ request_id: "L1", ok: true, items: [row] }, false);
const first = S.items.length;
bumpRoundGeneration("list");
S.round.list = "L2";
S.listState = "loading";
settleSynchronous({ ok: true, queued: true, skipped: "已经在拉活动列表",
  request_id: "L1", result: { request_id: "L1", ok: true, items: [row] } }, "list");
await __flush();
out.push({ first: first, items: S.items.length, state: S.listState,
           round: S.round.list });
""")
        data = res[0]
        self.assertEqual(data["first"], 1)
        self.assertEqual(data["state"], "ready", "新一轮不能停在加载中干等 130 秒")
        self.assertEqual(data["round"], "L1")
        self.assertEqual(data["items"], 1)

    def test_duplicate_terminal_in_same_round_applies_once(self):
        res = run_js(TIMER_HARNESS + r"""
const logs = () => document.querySelector('#log').childElementCount;
S.round.check = "dup";
bumpRoundGeneration("check");
const emit = () => window.onBackend.check({ request_id: "dup", ok: true,
  result: "valid", session_present: true, hours_left: 5 });
emit();
const first = logs();
emit();
out.push({ first: first, after: logs(), cache: S.round.cache.length });
""")
        data = res[0]
        self.assertEqual(data["first"], 1)
        self.assertEqual(data["after"], 1, "同一轮同一终态只能生效一次")
        self.assertEqual(data["cache"], 0, "本轮事件不该被当成旧轮暂存")

    def test_old_ack_does_not_settle_new_round(self):
        res = run_js(TIMER_HARNESS + r"""
const pending = [];
window.pywebview = { api: {
  check: (rid) => new Promise((resolve) => pending.push([rid, resolve])),
  list_activities: () => new Promise(() => {}),
  bootstrap: () => Promise.resolve({}),
} };
refresh(false);                 // 第 1 轮
refresh(false);                 // 第 2 轮
pending[0][1]({ ok: true, queued: true, request_id: pending[0][0] });
await __flush();
out.push({ pending: S.runtime.checkPending, checking: S.login.checking,
           gen: S.round.gen.check });
""")
        data = res[0]
        self.assertTrue(data["pending"], "旧轮 ack 不得清掉新一轮的 pending")
        self.assertTrue(data["checking"], "新一轮仍在检查中")
        self.assertGreaterEqual(data["gen"], 2)


class BootstrapTerminalViewTests(unittest.TestCase):
    """FR05：F5 只恢复 data 不够，必须恢复结果框/LED/边框/次数/动作。"""

    def _snapshot(self, status, tasks):
        return {"plan_id": "p9", "status": status, "summary": {"total": len(tasks)},
                "tasks": tasks}

    def test_terminal_snapshot_restores_result_box_and_led(self):
        snap = self._snapshot("stopped", [
            {"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "failed",
             "stop_reason": "unconfirmed", "attempts": 3,
             "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00",
             "reason": "响应丢失"},
            {"task_id": "t2", "activity_id": "a2", "name": "场二", "status": "canceled",
             "stop_reason": "user_stopped", "attempts": 0,
             "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00"},
        ])
        res = run_js(BOARD_VIEW_JS + "const snap = " + _js(snap) + ";" + r"""
window.LED_UI = { renderLed: (el, text, tone) => { S.__led = [String(text), String(tone)]; } };
const __labels = [];
const __realLabel = paintLedLabel;
paintLedLabel = (prefix, value) => { __labels.push(String(prefix)); return __realLabel(prefix, value); };
ingestBootstrapPlan({ plan: snap });
out.push({
  busy: S.busy, status: S.plan.status,
  doneSel: S.plan.doneSelection === selectionSignature(),
  board: boardPlanState(),
  html: document.querySelector("#result").innerHTML,
  view: __boardView(),
  labels: __labels,
  cards: document.querySelector("#plan-tasks").innerHTML,
});
""")
        data = res[0]
        self.assertFalse(data["busy"], "已结束的计划不得恢复成运行中")
        self.assertEqual(data["status"], "stopped")
        self.assertTrue(data["doneSel"], "恢复时必须设好选择签名，否则 LED/边框回落预览")
        self.assertEqual(data["board"], "attention", "含未知的停止不能画确定失败红框")
        # 结论在计划栏（result-panel D「用户停止的」）：标签同时说清「已停止」和要确认；
        # 原型 res.hasLed 在停止时为假，所以这句从 LED 下方搬到了标签
        view = data["view"]
        self.assertEqual(view["title"], "报名计划已停止")
        self.assertEqual(view["tag"], "已停止，需确认", "必须同时说清「已停止」和待核对场次")
        self.assertEqual(_stats(view), {"待核对": 1, "已取消": 1})
        self.assertTrue(view["ledHidden"], "停止的结果页不显示 LED")
        self.assertIn("3 次", data["cards"], "恢复后已提交次数不能归零")

    def test_running_snapshot_restores_busy_and_progress(self):
        snap = self._snapshot("running", [
            {"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "waiting",
             "sign_start": "2099-01-01 09:00:00", "sign_end": "2099-01-01 10:00:00"},
        ])
        res = run_js(BOARD_VIEW_JS + "const snap = " + _js(snap) + ";" + r"""
ingestBootstrapPlan({ plan: snap });
out.push({ busy: S.busy, status: S.plan.status, tasks: S.plan.tasks.size,
           result: document.querySelector("#result").innerHTML, view: __boardView() });
""")
        data = res[0]
        self.assertTrue(data["busy"], "运行态快照必须恢复进度与停止入口")
        self.assertEqual(data["tasks"], 1)
        self.assertNotIn("报名计划", data["result"], "运行态不该冒出终态结论")
        # 计划结论现在在计划栏：运行态不显示结果大数字，标题也不是结论
        self.assertEqual(data["view"]["stats"], "", "运行态不该冒出结果大数字")
        self.assertNotIn("报名计划", data["view"]["title"])

    def test_same_plan_id_advances_to_terminal(self):
        running = self._snapshot("running", [])
        done = self._snapshot("completed", [
            {"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "success",
             "stop_reason": "success", "attempts": 1,
             "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-26 23:00:00"},
        ])
        res = run_js(BOARD_VIEW_JS + "const running = " + _js(running) + "; const done = " + _js(done) + ";" + r"""
ingestBootstrapPlan({ plan: running });
const busyFirst = S.busy;
ingestBootstrapPlan({ plan: done });
out.push({ busyFirst: busyFirst, busy: S.busy, status: S.plan.status,
           html: __boardView().title });
""")
        data = res[0]
        self.assertTrue(data["busyFirst"])
        self.assertFalse(data["busy"], "同一 plan_id 推进到终态不能因为「已存在」被跳过")
        self.assertEqual(data["status"], "completed")
        # 结论在计划栏标题（result-panel D）
        self.assertEqual(data["html"], "报名计划完成")

    def test_restore_never_starts_a_plan(self):
        snap = self._snapshot("failed", [])
        res = run_js("const snap = " + _js(snap) + ";" + r"""
const calls = [];
window.pywebview = { api: {
  start_plan: (...args) => { calls.push(args); return Promise.resolve({ ok: true }); },
  bootstrap: () => Promise.resolve({}),
} };
ingestBootstrapPlan({ plan: snap });
out.push({ calls: calls.length, status: S.plan.status });
""")
        data = res[0]
        self.assertEqual(data["calls"], 0, "恢复显示不得重发 start_plan")
        self.assertEqual(data["status"], "failed")


class BoardStateSemanticsTests(unittest.TestCase):
    """FR06：整屏视觉与卡片/总结/LED 同一分类，确认失败才用失败色。"""

    def _run_plan(self, tasks, status):
        body = [BOARD_VIEW_JS,
                "window.onBackend.plan({ plan_id: \"p1\", status: \"running\", tasks: [] });"]
        for task in tasks:
            # plan_id 必须随任务一起带：handleTask 用它对账，缺了会被当成别的计划
            body.append("window.onBackend.task(%s);" % _js(dict(task, plan_id="p1")))
        body.append("window.onBackend.plan_done(%s);" % _js(
            {"plan_id": "p1", "status": status, "summary": {"total": len(tasks)}}))
        body.append(r"""out.push({ board: document.querySelector("#board").dataset.planState,
  html: document.querySelector("#result").innerHTML,
  view: __boardView(),
  led: document.querySelector("#led-label").textContent });""")
        return run_js(chr(10).join(body))[0]

    def test_unconfirmed_only_is_neutral(self):
        data = self._run_plan(
            [{"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "failed",
              "stop_reason": "unconfirmed", "attempts": 2, "reason": "响应丢失"}],
            "failed")
        self.assertEqual(data["board"], "attention")
        # 结论在计划栏（result-panel C / D「没报上、有待核对」）
        self.assertEqual(_stats(data["view"]), {"待核对": 1}, "按场数计，不按提交次数")
        self.assertEqual(data["view"]["title"], "计划已结束，有 1 场需确认")

    def test_auth_unavailable_is_counted_separately(self):
        data = self._run_plan(
            [{"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "failed",
              "stop_reason": "unconfirmed", "attempts": 2, "reason": "响应丢失"},
             {"task_id": "t2", "activity_id": "a2", "name": "场二", "status": "failed",
              "stop_reason": "auth_unavailable", "attempts": 0, "reason": "URLError"}],
            "failed")
        # 计划 decisions：auth_unavailable 在结果页计入「报名未成功」，与待核对分开
        self.assertEqual(_stats(data["view"]), {"报名未成功": 1, "待核对": 1},
                         "未提交的场次不能算成待核对")
        self.assertEqual(data["board"], "attention")

    def test_confirmed_failure_keeps_red(self):
        data = self._run_plan(
            [{"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "failed",
              "stop_reason": "max_attempts", "attempts": 5, "reason": "名额已满"}],
            "failed")
        self.assertEqual(data["board"], "failed", "确认失败仍用确定失败视觉")
        self.assertEqual(_stats(data["view"]), {"报名未成功": 1})
        self.assertEqual(data["view"]["title"], "报名计划没有成功")

    def test_stopped_with_unknown_keeps_stopped_title(self):
        data = self._run_plan(
            [{"task_id": "t1", "activity_id": "a1", "name": "场一", "status": "success",
              "stop_reason": "success", "attempts": 1, "reason": "报名成功"},
             {"task_id": "t2", "activity_id": "a2", "name": "场二", "status": "failed",
              "stop_reason": "unconfirmed", "attempts": 3, "reason": "停止前没拿到回应"}],
            "stopped")
        view = data["view"]
        self.assertEqual(view["title"], "报名计划已停止", "停止是主结论，不能被未知覆盖")
        self.assertEqual(view["tag"], "已停止，需确认", "停止前的未知场次要并列说清")
        self.assertEqual(_stats(view), {"已报名": 1, "待核对": 1})
        self.assertEqual(data["board"], "attention")


class PlanEventOwnershipTests(unittest.TestCase):
    """P1：旧计划事件不得改写当前计划；合法新计划事件可早于 ack。

    全部通过 window.onBackend.plan/task/plan_done 驱动生产 handler，
    载荷带后端接纳时附加的 plan_generation（生产桥接事件都有该字段）。
    """

    def test_stale_plan_events_cannot_hijack_running_plan(self):
        """B 运行中注入旧 A 的 plan/task/plan_done：B 的忙态/任务/停止入口不变。"""
        res = run_js(r"""
window.onBackend.plan({ plan_id: "pb", plan_generation: 2, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "B场一", status: "running" }] });
const calls = [];
window.pywebview = { api: {
  stop_plan: (pid) => { calls.push(pid); return Promise.resolve({ ok: true }); } } };
window.onBackend.plan({ plan_id: "pa", plan_generation: 1, status: "ready", tasks: [] });
window.onBackend.task({ plan_id: "pa", plan_generation: 1, task_id: "tA",
                        activity_id: "aA", name: "A场一", status: "success" });
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "completed", summary: {} });
out.push({ id: S.plan.id, status: S.plan.status, busy: S.busy,
           tasks: Array.from(S.plan.tasks.keys()) });
doStopPlan();
out.push({ calls: calls });
""")
        data = res[0]
        self.assertEqual(data["id"], "pb", "旧计划事件不得替换当前计划")
        self.assertEqual(data["status"], "running", "旧计划事件不得结束运行中的 B")
        self.assertTrue(data["busy"], "B 仍在运行：忙态不得被旧事件解除")
        self.assertEqual(data["tasks"], ["t1"], "旧计划任务不得混入 B 的任务表")
        self.assertEqual(res[1]["calls"], ["pb"],
                         "停止按钮实际调用必须仍指向 B 的 plan_id")

    def test_stale_done_cannot_replace_finished_plan_conclusion(self):
        """B 已完成后再注入 A 的完成：结果框/LED/边框/忙态保持 B 的结论。"""
        res = run_js(BOARD_VIEW_JS + r"""
window.onBackend.plan({ plan_id: "pb", plan_generation: 2, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "B场一", status: "success" }] });
window.onBackend.plan_done({ plan_id: "pb", plan_generation: 2,
                             status: "completed", summary: { total: 1 } });
const doneHtml = JSON.stringify(__boardView());
const doneBoard = document.querySelector("#board").dataset.planState;
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "failed", summary: {} });
out.push({ id: S.plan.id, busy: S.busy, board: document.querySelector("#board").dataset.planState,
           html: JSON.stringify(__boardView()), doneTitle: JSON.parse(doneHtml).title,
           unchanged: JSON.stringify(__boardView()) === doneHtml,
           doneBoard: doneBoard });
""")
        data = res[0]
        self.assertEqual(data["id"], "pb", "旧完成事件不得把屏上计划换成 A")
        self.assertEqual(data["doneTitle"], "报名计划完成", "对照：B 的结论在计划栏")
        self.assertTrue(data["unchanged"], "B 的结果框结论不得被 A 改写")
        self.assertFalse(data["busy"], "B 已结束：忙态应保持解除")
        self.assertEqual(data["board"], data["doneBoard"], "整屏状态保持 B 的终态")

    def test_duplicate_done_keeps_first_conclusion(self):
        """同计划重复终态：不把已定结论改成后来重复包的另一状态。"""
        res = run_js(BOARD_VIEW_JS + r"""
window.onBackend.plan({ plan_id: "p1", plan_generation: 1, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "场一", status: "failed" }] });
window.onBackend.plan_done({ plan_id: "p1", plan_generation: 1,
                             status: "failed", summary: {} });
const firstHtml = JSON.stringify(__boardView());
window.onBackend.plan_done({ plan_id: "p1", plan_generation: 1,
                             status: "completed", summary: {} });
out.push({ status: S.plan.status, busy: S.busy, firstTitle: JSON.parse(firstHtml).title,
           unchanged: JSON.stringify(__boardView()) === firstHtml });
""")
        data = res[0]
        self.assertEqual(data["firstTitle"], "报名计划没有成功", "对照：第一次终态的结论在计划栏")
        self.assertTrue(data["unchanged"], "重复终态不得改写已定结论")
        self.assertFalse(data["busy"], "重复终态不得重新拉起忙态")

    def test_stale_progress_cannot_regress_terminal_plan(self):
        """同计划终态后收到旧进度事件：不回退终态、不复活忙态（含被拒的开始）。"""
        res = run_js(r"""
window.onBackend.plan({ plan_id: "pa", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "failed", summary: {} });
S.startRequest = { id: "rid-x", state: "rejected", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
window.onBackend.plan({ plan_id: "pa", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "completed", summary: {} });
out.push({ id: S.plan.id, status: S.plan.status, busy: S.busy });
""")
        data = res[0]
        self.assertEqual(data["status"], "failed", "旧进度/重复终态不得回退已定结论")
        self.assertFalse(data["busy"], "被拒的开始请求不得被旧事件复活成运行态")

    def test_new_plan_events_before_ack_are_adopted_and_ack_keeps_telemetry(self):
        """B 事件早于 ack：按代次接纳；后到 ack 不清任务、不抹已收次数。"""
        res = run_js(r"""
window.onBackend.plan({ plan_id: "pa", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "stopped", summary: {} });
/* 新 B：事件先于 start_plan ack 到达 */
window.onBackend.plan({ plan_id: "pb", plan_generation: 2, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "B场一", status: "running",
            attempts: 3 }] });
/* ack 后到：不得清掉已收任务，也不得把已收到的提交次数抹回 0 */
adoptPlan("rid-b", "pb",
          { status: "running", tasks: [{ task_id: "t1", activity_id: "a1", attempts: 0 }] },
          false, 2);
const task = S.plan.tasks.get("t1") || {};
out.push({ id: S.plan.id, busy: S.busy, tasks: S.plan.tasks.size, attempts: task.attempts });
""")
        data = res[0]
        self.assertEqual(data["id"], "pb", "更新代次的事件应被接纳为新计划")
        self.assertTrue(data["busy"], "B 运行中：忙态保持")
        self.assertEqual(data["tasks"], 1, "后到 ack 不得清掉已收任务")
        self.assertEqual(data["attempts"], 3, "后到 ack 不得抹掉已收到的提交次数")

    def test_f5_restore_survives_stale_events(self):
        """F5 以 bootstrap 权威快照建立归属后，旧计划事件不得覆盖。"""
        res = run_js(BOARD_VIEW_JS + r"""
ingestBootstrapPlan({ plan: { plan_id: "pb", plan_generation: 2, status: "completed",
  summary: { total: 1 },
  tasks: [{ task_id: "t1", activity_id: "a1", name: "B场一", status: "success" }] } });
const html = JSON.stringify(__boardView());
window.onBackend.plan_done({ plan_id: "pa", plan_generation: 1,
                             status: "failed", summary: {} });
window.onBackend.plan({ plan_id: "pa", plan_generation: 1, status: "running", tasks: [] });
out.push({ id: S.plan.id, busy: S.busy, status: S.plan.status, title: JSON.parse(html).title,
           unchanged: JSON.stringify(__boardView()) === html });
""")
        data = res[0]
        self.assertEqual(data["id"], "pb", "F5 恢复的计划不得被旧事件替换")
        self.assertEqual(data["title"], "报名计划完成", "对照：F5 恢复的结论在计划栏")
        self.assertTrue(data["unchanged"], "F5 恢复的结论不得被旧事件改写")
        self.assertFalse(data["busy"])
        self.assertEqual(data["status"], "completed")


class StoppingEarlyReturnTests(unittest.TestCase):
    """S.stopping：同计划终态已定时，重复终态事件通过早返回分支到达，
    presentPlanDone 不会被调。doStopPlan 曾置 S.stopping=true，早返回必须自己收口。"""

    def test_duplicate_done_clears_stopping_flag(self):
        """doStopPlan 后收到同 plan_id 的重复 plan_done(stopped)：S.stopping 必须归 false。"""
        res = run_js(r"""
/* 先把计划推到 running，再模拟用户点停止留下的停止标记 */
window.onBackend.plan({ plan_id: "p1", plan_generation: 1, status: "running",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "场一", status: "running" }] });
S.stopping = true;
/* 先到 plan 终态：plan 事件应解除 busy 并保留 stopped 结论 */
window.onBackend.plan({ plan_id: "p1", plan_generation: 1, status: "stopped",
  tasks: [{ task_id: "t1", activity_id: "a1", name: "场一", status: "canceled" }] });
const afterPlan = { stopping: S.stopping, busy: S.busy, status: S.plan.status };
/* 随后的同 plan_id plan_done 走早返回，补齐任务详情并收口 stopping */
window.onBackend.plan_done({ plan_id: "p1", plan_generation: 1,
                             status: "stopped", summary: {}, tasks: [{ task_id: "t1",
                             activity_id: "a1", name: "场一", status: "canceled" }] });
out.push({ afterPlan, stopping: S.stopping, busy: S.busy, status: S.plan.status,
           taskCount: S.plan.tasks.size, taskCanceled: (S.plan.tasks.get("t1") || {}).status });
""")
        data = res[0]
        self.assertTrue(data["afterPlan"]["stopping"],
                        "plan 事件只推进终态，保留等待 plan_done 的停止标记")
        self.assertFalse(data["afterPlan"]["busy"], "plan 终态后 busy 必须解除")
        self.assertEqual(data["afterPlan"]["status"], "stopped", "plan 事件保持 stopped 结论")
        self.assertFalse(data["stopping"],
                         "早返回分支必须自己清 S.stopping，不能让停止标记残留")
        self.assertFalse(data["busy"], "终态后 busy 必须解除")
        self.assertEqual(data["status"], "stopped", "计划保持 stopped 结论不变")
        self.assertEqual(data["taskCount"], 1, "重复终态仍能合并任务详情")
        self.assertEqual(data["taskCanceled"], "canceled", "后端推来的 canceled 状态应覆盖旧 task")


class StartingSelectionRaceTests(unittest.TestCase):
    """S.starting 期间选择入口锁定：toggleSelection / clearSelection 都要早退，
    防止 startPlan 到 ack 之间用户乱改选择导致 stale selection 被 adoptPlan 恢复。"""

    def test_toggle_selection_refuses_when_starting(self):
        """S.starting=true + busy=false 时，toggleSelection(id,true/false) 都不得改动 selected 集合。"""
        res = run_js(r"""
window.onBackend.activities({ ok: true, items: [
  { id: "a1", name: "活动甲", signed: false,
    sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00",
    act_start: "2099-01-03 09:00:00", act_end: "2099-01-03 11:00:00" },
  { id: "a2", name: "活动乙", signed: false,
    sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00",
    act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00" },
] });
S.busy = false; S.starting = true;
S.selected.add("a1");
const before = S.selected.size;
toggleSelection("a1", false);   /* 取消已选中的 */
toggleSelection("a2", true);    /* 勾选新的 */
out.push({ before, after: S.selected.size, ids: Array.from(S.selected).sort() });
""")
        data = res[0]
        self.assertEqual(data["before"], 1)
        self.assertEqual(data["after"], 1, "starting 期间选择集合不得被改动")
        self.assertEqual(data["ids"], ["a1"], "a1 保留、a2 不得被勾上")

    def test_clear_selection_refuses_when_starting(self):
        """S.starting=true 时 clearSelection 不得清空 selected 或重置 plan。"""
        res = run_js(r"""
window.onBackend.activities({ ok: true, items: [
  { id: "a1", name: "活动甲", signed: false,
    sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00",
    act_start: "2099-01-03 09:00:00", act_end: "2099-01-03 11:00:00" },
] });
S.busy = false; S.starting = true;
S.selected.add("a1");
S.plan = { id: "ph1", status: "running", gen: 1, tasks: new Map() };
clearSelection();
out.push({ selectedSize: S.selected.size, planId: S.plan.id, planStatus: S.plan.status });
""")
        data = res[0]
        self.assertEqual(data["selectedSize"], 1, "starting 期间 clearSelection 不得清选择")
        self.assertEqual(data["planId"], "ph1", "starting 期间 clearSelection 不得重置 plan")
        self.assertEqual(data["planStatus"], "running")


class RowCheckGateConsistencyTests(unittest.TestCase):
    """H2：行渲染与 updateControls 对复选框用同一份禁用判据。

    此前行渲染缺 S.starting，updateControls 缺 signStartPending：开放时间待公布的行
    在 updateControls 之后会被重新启用，提交中重画列表时勾选框又能点。
    """

    LIST = r"""
const rows = [
  { id: "a1", name: "正常活动", sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00",
    act_start: "2099-01-03 09:00:00", act_end: "2099-01-03 11:00:00", signed: false },
  { id: "a2", name: "待公布活动", sign_start: "", sign_end: "2099-01-02 09:00:00",
    act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00", signed: false },
];
window.onBackend.activities({ ok: true, items: rows });
S.busy = false; S.starting = false;
"""

    def test_update_controls_keeps_pending_sign_start_row_disabled(self):
        """开放时间待公布的行：updateControls 之后仍禁用（此前被重新启用）。"""
        res = run_js(self.LIST + r"""
const pending = findItem("a2");
const check = document.querySelector(".row-check");
check.dataset.id = "a2";
updateControls();
const pendingDisabled = check.disabled;
check.dataset.id = "a1";
updateControls();
out.push({ precondition: signStartPending(pending), pendingDisabled,
           normalDisabled: check.disabled });
""")
        data = res[0]
        self.assertTrue(data["precondition"], "夹具里 a2 必须是开放时间待公布的行")
        self.assertTrue(data["pendingDisabled"], "待公布的行勾选框必须保持禁用")
        self.assertFalse(data["normalDisabled"], "正常的行不受影响")

    def test_starting_disables_row_checkbox_on_rerender(self):
        """提交中（S.starting）重画列表：行勾选框必须是禁用的。"""
        res = run_js(self.LIST + r"""
const item = findItem("a1");
const idle = rowHtml(item);
S.starting = true;
const starting = rowHtml(item);
const re = /<input class="row-check"[^>]*disabled/;
out.push({ idleDisabled: re.test(idle), startingDisabled: re.test(starting) });
""")
        data = res[0]
        self.assertFalse(data["idleDisabled"], "空闲时正常行可勾")
        self.assertTrue(data["startingDisabled"], "提交中重画列表，勾选框必须禁用")


class TerminalBeforeAckTests(unittest.TestCase):
    """终态早于开始 ack：ack 只证明「已接纳」，不得把已结束计划重新置忙。

    全部驱动生产 startPlan/adoptPlan 与真实 onBackend 事件；start_plan 回执用
    受控 Promise 挂起，终态事件先落地、最后才 resolve ack。
    """

    ITEM = {"id": "a1", "name": "活动一", "sign_start": "2026-10-27 09:00:00",
            "sign_end": "2099-01-01 23:00:00",
            "act_start": "2099-01-02 09:00:00", "act_end": "2099-01-02 11:00:00",
            "signed": False}

    def _harness(self):
        return r"""
window.onBackend.activities({ ok: true, request_id: "l1", items: [
  { id: "a1", name: "活动一", sign_start: "2026-10-27 09:00:00",
    sign_end: "2099-01-01 23:00:00", act_start: "2099-01-02 09:00:00",
    act_end: "2099-01-02 11:00:00", signed: false } ] });
S.selected.add("a1");
"""

    def test_ack_does_not_revive_finished_plan(self):
        """start → 终态事件 → 原 ack：busy 不得复活，结论/次数/任务保持。"""
        cases = [
            ("completed", "success", "success", 1),
            ("failed", "failed", "max_attempts", 5),
            ("failed", "failed", "unconfirmed", 3),
            ("stopped", "canceled", "unconfirmed", 2),
        ]
        for plan_status, task_status, stop, attempts in cases:
            with self.subTest(plan=plan_status, stop=stop):
                res = run_js(self._harness() + r"""
let resolveAck = null;
let startCalls = 0;
window.pywebview = { api: {
  start_plan: () => { startCalls += 1;
    return new Promise((res) => { resolveAck = res; }); } } };
startPlan();
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
await flush();
const submitting = { busy: S.busy, starting: S.starting };
window.onBackend.plan({ plan_id: "p9", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.task({ plan_id: "p9", plan_generation: 1, task_id: "t1",
                        activity_id: "a1", name: "活动一", status: %s,
                        stop_reason: %s, attempts: %d });
window.onBackend.plan_done({ plan_id: "p9", plan_generation: 1, status: %s,
                             summary: { total: 1 } });
const afterDone = { busy: S.busy, status: S.plan.status,
                    result: document.querySelector("#result").innerHTML };
resolveAck({ ok: true, queued: true, plan_id: "p9", plan_generation: 1 });
await flush();
out.push({ submitting: submitting, afterDone: afterDone,
           after: { busy: S.busy, starting: S.starting, status: S.plan.status,
                    id: S.plan.id, attempts: (S.plan.tasks.get("t1")||{}).attempts },
           startCalls: startCalls });
""" % (json_str(task_status), json_str(stop), attempts, json_str(plan_status)))
                data = res[0]
                self.assertFalse(data["submitting"]["busy"],
                                 "ack 未回、事件未到：此时还不忙（对照）")
                self.assertTrue(data["submitting"]["starting"],
                                "提交中开始标志保持，不放行第二次开始")
                self.assertFalse(data["afterDone"]["busy"], "plan_done 后必须解锁")
                self.assertFalse(data["after"]["busy"],
                                 "迟到的 ack 不得把已结束计划重新置忙")
                self.assertFalse(data["after"]["starting"])
                self.assertEqual(data["after"]["status"], plan_status,
                                 "ack 不得改写终态结论")
                self.assertEqual(data["after"]["id"], "p9")
                self.assertEqual(data["after"]["attempts"], attempts,
                                 "ack 不得抹掉已收次数")
                self.assertEqual(data["startCalls"], 1, "start_plan 恰好调用一次")

    def test_ack_while_still_submitting_keeps_busy(self):
        """对照：事件仍处提交中时 ack 到达，busy 必须为 true（既有路径不回退）。"""
        res = run_js(self._harness() + r"""
let resolveAck = null;
window.pywebview = { api: {
  start_plan: () => new Promise((res) => { resolveAck = res; }) } };
startPlan();
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
await flush();
window.onBackend.plan({ plan_id: "p9", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.task({ plan_id: "p9", plan_generation: 1, task_id: "t1",
                        activity_id: "a1", name: "活动一", status: "submitting",
                        attempts: 1 });
resolveAck({ ok: true, queued: true, plan_id: "p9", plan_generation: 1 });
await flush();
out.push({ busy: S.busy, status: S.plan.status, tasks: S.plan.tasks.size,
           attempts: (S.plan.tasks.get("t1")||{}).attempts });
""")
        data = res[0]
        self.assertTrue(data["busy"], "计划仍在提交中：ack 后忙态成立")
        self.assertEqual(data["tasks"], 1, "ack 不清已收任务")
        self.assertEqual(data["attempts"], 1, "ack 不抹已收次数")

    def test_reconcile_old_running_snapshot_cannot_revive_terminal(self):
        """adoptPlan 收到同 plan_id 旧 running 快照：终态/忙态/次数不回退。"""
        res = run_js(BOARD_VIEW_JS + self._harness() + r"""
window.onBackend.plan({ plan_id: "p9", plan_generation: 1, status: "running", tasks: [] });
window.onBackend.task({ plan_id: "p9", plan_generation: 1, task_id: "t1",
                        activity_id: "a1", name: "活动一", status: "success",
                        stop_reason: "success", attempts: 2 });
window.onBackend.plan_done({ plan_id: "p9", plan_generation: 1,
                             status: "completed", summary: { total: 1 } });
const before = { busy: S.busy, status: S.plan.status,
                 result: JSON.stringify(__boardView()), title: __boardView().title };
S.startRequest = { id: "rid", state: "reconciling", timer: null,
                   queryTimer: null, reconcile: 0, gen: 0 };
adoptPlan("rid", "p9",
          { status: "running",
            tasks: [{ task_id: "t1", activity_id: "a1", name: "活动一",
                      status: "queued", attempts: 0 }] },
          false, 1);
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
await flush();
out.push({ before: before, after: { busy: S.busy, status: S.plan.status,
           taskStatus: (S.plan.tasks.get("t1")||{}).status,
           attempts: (S.plan.tasks.get("t1")||{}).attempts,
           unchanged: JSON.stringify(__boardView()) === before.result } });
""")
        data = res[0]
        self.assertFalse(data["before"]["busy"], "plan_done 后已解锁（对照）")
        self.assertEqual(data["before"]["title"], "报名计划完成", "对照：终态结论在计划栏")
        self.assertFalse(data["after"]["busy"],
                         "旧 running 快照不得复活已终态的计划")
        self.assertEqual(data["after"]["status"], "completed",
                         "旧 running 快照不得改写终态结论")
        self.assertEqual(data["after"]["taskStatus"], "success",
                         "旧 queued 快照不得把已成功场次拖回排队")
        self.assertEqual(data["after"]["attempts"], 2, "次数只增不减")
        self.assertTrue(data["after"]["unchanged"], "终态呈现保持")


def json_str(value):
    import json
    return json.dumps(value, ensure_ascii=False)


class SignedResultUiTests(unittest.TestCase):
    """真实数据 P0-1/P0-2：报名成功后列表、计数、门禁与冲突基线立即一致。"""

    LIST = r"""
const rows = [
  { id: "a1", name: "已确认活动", sign_start: "2026-10-26 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 09:00:00",
    act_end: "2026-10-27 11:00:00", signed: false, checkin_required: null,
    checkout_required: null },
  { id: "a2", name: "重叠活动", sign_start: "2026-10-26 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 10:00:00",
    act_end: "2026-10-27 12:00:00", signed: false, checkin_required: null,
    checkout_required: null },
  { id: "a3", name: "已报名活动", sign_start: "2026-10-20 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 11:00:00",
    act_end: "2026-10-27 12:30:00", signed: true, checkin_required: null,
    checkout_required: null }
];
setBusinessNow(toTs("2026-10-26 20:00:00") * 1000);
window.onBackend.activities({ ok: true, items: rows });
"""

    def test_success_updates_rows_counts_and_removes_from_selection(self):
        res = run_js(self.LIST + r"""
S.selected.add("a1");
const before = { signed: S.items.filter((i) => i.signed).length,
                 eligible: isEligibleForPlan(findItem("a1")),
                 selected: S.selected.has("a1") };
window.onBackend.plan({ plan_id: "p1", status: "running", plan_generation: 1, tasks: [] });
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1",
  name: "已确认活动", status: "success", attempts: 1, plan_generation: 1 });
window.onBackend.plan_done({ plan_id: "p1", status: "completed",
  plan_generation: 1, summary: {} });
const item = findItem("a1");
out.push({ before: before,
  after: { signed: S.items.filter((i) => i.signed).length,
           itemSigned: !!item.signed, source: item.signed_source,
           eligible: isEligibleForPlan(item), selected: S.selected.has("a1"),
           conflicts: conflictIds().has("a1"),
           taskStatus: (S.plan.tasks.get("t1") || {}).status },
  html: rowHtml(item) });
""")
        data = res[0]
        self.assertEqual(data["before"]["signed"], 1)
        self.assertTrue(data["before"]["eligible"])
        self.assertTrue(data["before"]["selected"])
        self.assertEqual(data["after"]["signed"], 2,
                         "success 是已确认事实：已报名计数必须立即 +1")
        self.assertTrue(data["after"]["itemSigned"])
        self.assertEqual(data["after"]["source"], "plan_success")
        self.assertFalse(data["after"]["eligible"])
        self.assertFalse(data["after"]["selected"], "成功场次从下一次选择集合移除")
        self.assertFalse(data["after"]["conflicts"])
        self.assertEqual(data["after"]["taskStatus"], "success", "任务卡保留")
        self.assertIn("已报名", data["html"])

    def test_success_blocks_overlapping_second_activity(self):
        res = run_js(self.LIST + r"""
window.onBackend.plan({ plan_id: "p1", status: "running", plan_generation: 1, tasks: [] });
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1",
  name: "已确认活动", status: "success", attempts: 1, plan_generation: 1 });
window.onBackend.plan_done({ plan_id: "p1", status: "completed",
  plan_generation: 1, summary: {} });
toggleSelection("a2", true);
const validation = validateSelection();
out.push({ notice: S.selectionNotice, selected: Array.from(S.selected),
           errors: validation.errors.map((e) => e.title) });
""")
        data = res[0]
        self.assertIn("与已报名活动", data["notice"])
        self.assertIn("举办时间重叠", data["notice"])
        self.assertNotIn("a2", data["selected"])
        self.assertEqual(data["errors"], [])

    def test_validation_rejects_selection_conflicting_with_signed_item(self):
        res = run_js(self.LIST + r"""
S.selected.add("a2");
const check = validateSelection();
out.push({ errors: check.errors.map((e) => e.title) });
""")
        data = res[0]
        self.assertIn("与已报名活动重叠", data["errors"])

    def test_list_refresh_false_keeps_confirmed_success_with_sync_note(self):
        res = run_js(self.LIST + r"""
window.onBackend.plan({ plan_id: "p1", status: "running", plan_generation: 1, tasks: [] });
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1",
  name: "已确认活动", status: "success", attempts: 1, plan_generation: 1 });
window.onBackend.plan_done({ plan_id: "p1", status: "completed",
  plan_generation: 1, summary: {} });
/* 学校列表还没同步：同一条 a1 仍是 signed=false */
const stale = [{ id: "a1", name: "已确认活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 09:00:00",
  act_end: "2026-10-27 11:00:00", signed: false, checkin_required: null,
  checkout_required: null }];
window.onBackend.activities({ ok: true, items: stale });
const item = findItem("a1");
out.push({ signed: !!item.signed, pending: !!item.sync_pending,
           state: stateOf(item), html: rowHtml(item),
           count: S.items.filter((i) => i.signed).length });
""")
        data = res[0]
        self.assertTrue(data["signed"], "同步窗口内不得撤销已确认成功")
        self.assertTrue(data["pending"])
        self.assertEqual(data["state"], "signed")
        self.assertIn("学校列表正在同步", data["html"])
        self.assertEqual(data["count"], 1)


class InstantModeCopyTests(unittest.TestCase):
    """RC-04/RC-06：立即模式不显示等待开放，成功结论只留一条。"""

    def test_instant_task_card_never_says_waiting_open(self):
        res = run_js(r"""
setBusinessNow(toTs("2026-10-26 20:00:00") * 1000);
const past = { task_id: "t1", activity_id: "a1", name: "活动",
  signup_mode: "instant_signup", status: "submitting", attempts: 0,
  sign_start: "2026-10-26 09:00:00" };
const unknownTime = Object.assign({}, past, { sign_start: "" });
out.push({ pastLabel: taskDisplayLabel(past),
           pastDetail: taskDisplayDetail(past),
           unknownLabel: taskDisplayLabel(unknownTime),
           unknownDetail: taskDisplayDetail(unknownTime) });
""")
        data = res[0]
        self.assertEqual(data["pastLabel"], "准备报名")
        self.assertEqual(data["pastDetail"], "已开放，正在准备提交")
        self.assertEqual(data["unknownLabel"], "准备报名",
                         "立即模式时间不可读也不能说成等待开放")
        self.assertNotIn("等待开放", data["unknownDetail"])

    def test_worker_success_is_logged_once(self):
        res = run_js(r"""
window.onBackend.log("[活动甲] 2026-10-26 20:00:00 [OK] 报名成功（尝试 1 次）");
window.onBackend.plan({ plan_id: "p1", status: "running", plan_generation: 1, tasks: [] });
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "success", attempts: 1, plan_generation: 1 });
window.onBackend.plan_done({ plan_id: "p1", status: "completed",
  plan_generation: 1, summary: {} });
/* 重复终态：同一条成功不得再写一遍 */
window.onBackend.task({ plan_id: "p1", task_id: "t1", activity_id: "a1",
  name: "活动甲", status: "success", attempts: 1, plan_generation: 1 });
const rows = document.querySelector("#log")._children
  .map((node) => String(node.textContent || ""))
  .filter((text) => text.indexOf("报名成功") >= 0);
out.push({ rows: rows });
""")
        rows = res[0]["rows"]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("活动甲", rows[0])


AUTO_REFRESH_PRELUDE = TIMER_HARNESS + r"""
/* 自动刷新用例的公共前置：条款已同意、在线、登录有效、列表已成功加载一次（10:00 的）。
 * 后端桥接全是桩：window_visibility 可由用例切换，check / list_activities 只记调用。 */
let __backendHidden = false;
const __calls = { check: [], list: [], visibility: 0 };
window.pywebview = { api: {
  window_visibility: () => { __calls.visibility += 1; return Promise.resolve({ hidden: __backendHidden }); },
  check: (id) => { __calls.check.push(id); return Promise.resolve({ ok: true, queued: true }); },
  list_activities: (id) => { __calls.list.push(id); return Promise.resolve({ ok: true, queued: true }); },
} };
const __ITEMS = [
  { id: "a1", name: "活动一", sign_start: "2026-11-12 20:00:00", sign_end: "2026-11-12 22:00:00",
    act_start: "2026-11-13 09:00:00", act_end: "2026-11-13 11:00:00", signed: false },
  { id: "a2", name: "活动二", sign_start: "2026-11-13 20:00:00", sign_end: "2026-11-13 22:00:00",
    act_start: "2026-11-14 09:00:00", act_end: "2026-11-14 11:00:00", signed: false },
];
/* 把当前这一轮的 check 与 list 终态按真实事件入口送回来 */
const __checkOk = () => window.onBackend.check({ request_id: S.round.check, ok: true,
  result: "valid", session_present: true, hours_left: 5 });
const __finish = (items) => {
  __checkOk();
  window.onBackend.activities({ request_id: S.round.list, ok: true, items: items || __ITEMS });
};
const __failList = (text) => {
  __checkOk();
  window.onBackend.activities({ request_id: S.round.list, ok: false, text: text || "连不上学校站点" });
};
/* 单调钟与业务钟一起走：业务锚点每次推进后重新注入，长时间推进也不会因锚点过期变成「待校准」 */
let __bizEpochMs = toTs("2026-11-12 10:00:00") * 1000;
const __advance = (minutes) => {
  __advanceMono(minutes * 60000);
  __bizEpochMs += minutes * 60000;
  setBusinessNow(__bizEpochMs);
};
const __schoolText = (epochSec) => new Date((Math.floor(epochSec) + 8 * 3600) * 1000)
  .toISOString().slice(0, 19).replace("T", " ");
const __tick = async () => { const fired = await autoRefreshTick(); await __flush(); return fired; };
const __autoLogs = () => S.recentLogs.filter((line) => /活动列表/.test(line));
const __ids = () => S.items.map((item) => item.id);

S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = false;
setBusinessNow(__bizEpochMs);
refresh(true);
__finish();
"""

# 只记录调用的 refresh 桩：验证「触发了什么」，不真的发请求
STUB_REFRESH = r"""
const __rc = [];
refresh = (quiet, options) => { __rc.push({ quiet: quiet, background: !!(options && options.background) }); };
"""

# 跳过条件的统一骨架：先满 10 分钟，套上条件后不触发；撤掉条件后同一时刻立即触发。
# 这样每条跳过条件都是「唯一原因」，不会被别的条件顶替。
SKIP_TEMPLATE = AUTO_REFRESH_PRELUDE + STUB_REFRESH + r"""
__advance(10.5);
const __at = (sec) => __schoolText(bnowS() + sec);
const __row = {};
__APPLY__
__row.skipped = await __tick();
__row.callsWhileSkipped = __rc.length;
__REVERT__
__row.fired = await __tick();
__row.callsAfter = __rc.length;
out.push(__row);
"""

_PLAN_WITH_TASK = (
    'S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map([["t1", '
    '{ task_id: "t1", activity_id: "a1", name: "活动一", status: "%s", sign_start: %s }]]) }; '
    'S.busy = true;')

SKIP_CASES = [
    ("条款未同意", 'S.terms.acceptedVersion = "";', 'S.terms.acceptedVersion = "v1";'),
    ("断网", 'S.online = false;', 'S.online = true;'),
    ("登录结论不是 valid", 'S.login.result = "expired"; S.login.ok = false;',
     'S.login.result = "valid"; S.login.ok = true;'),
    ("刷新按钮当前不可用", '$("#btn-refresh").disabled = true;', '$("#btn-refresh").disabled = false;'),
    ("取消报名进行中", 'S.cancel.busyId = "a1";', 'S.cancel.busyId = "";'),
    ("正在提交开始请求", 'S.starting = true;', 'S.starting = false;'),
    ("正在检查登录", 'S.login.checking = true;', 'S.login.checking = false;'),
    ("正在拉列表", 'S.listState = "loading";', 'S.listState = "ready";'),
    ("演示模式", 'S.demo = true;', 'S.demo = false;'),
    ("页面不可见 document.hidden", 'document.hidden = true;', 'document.hidden = false;'),
    ("后端报告窗口已隐藏", '__backendHidden = true;', '__backendHidden = false;'),
    ("计划场次离开放不到 5 分钟",
     _PLAN_WITH_TASK % ("waiting", "__at(240)"),
     'S.plan.tasks.get("t1").sign_start = __at(360);'),
    ("计划场次离开放 299 秒（边界内）",
     _PLAN_WITH_TASK % ("waiting", "__at(299)"),
     'S.plan.tasks.get("t1").sign_start = __at(301);'),
    ("计划场次已过开放时刻但没有终态",
     _PLAN_WITH_TASK % ("submitting", "__at(-30)"),
     'S.plan.tasks.get("t1").status = "success";'),
    ("计划场次开放时间读不出来",
     _PLAN_WITH_TASK % ("waiting", '""'),
     'S.plan.tasks.get("t1").sign_start = __at(900);'),
]


class AutoListRefreshTests(unittest.TestCase):
    """活动列表每 10 分钟后台自动刷新（计划 20261112-auto-list-refresh）。

    每个用例都在 node 沙箱里驱动生产 refresh.js / app.js：时间用 __advanceMono 推单调钟，
    业务时刻用 setBusinessNow 注入，不读墙钟。"""

    # ---- 周期 ----

    def test_fires_one_background_refresh_after_ten_minutes(self):
        res = run_js(AUTO_REFRESH_PRELUDE + STUB_REFRESH + r"""
__advance(9.9);
const early = await __tick();
__advance(0.2);
const due = await __tick();
const again = await __tick();     /* 刚尝试过：同一刻不能再触发第二次 */
out.push({ early: early, due: due, again: again, calls: __rc });
""")
        data = res[0]
        self.assertFalse(data["early"], "未满 10 分钟不触发")
        self.assertTrue(data["due"], "满 10 分钟触发")
        self.assertFalse(data["again"], "触发后重新计时，不连发")
        self.assertEqual(data["calls"], [{"quiet": True, "background": True}],
                         "只触发一次，且是 quiet 加 background 的 refresh")

    def test_manual_login_and_cancel_refreshes_restart_the_clock(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
const legs = [];
/* 手动刷新（点按钮）与登录成功 / 取消报名后的 quiet 刷新都走 refresh()，都要重新计时 */
for (const quiet of [false, true]) {
  __advance(9);
  refresh(quiet);
  __finish();
  __advance(2);                         /* 距开机超过 10 分钟，距刚才的刷新只有 2 分钟 */
  const early = await __tick();
  const callsEarly = __calls.list.length;
  __advance(8.1);
  const due = await __tick();
  legs.push({ quiet: quiet, early: early, due: due, callsEarly: callsEarly,
              callsDue: __calls.list.length });
  __finish();
}
out.push(legs);
""")
        for leg in res[0]:
            self.assertFalse(leg["early"], "刚刷新过 2 分钟，不能因为开机早就满 10 分钟而触发: %r" % leg)
            self.assertTrue(leg["due"], "距上次刷新满 10 分钟才触发: %r" % leg)
            self.assertEqual(leg["callsDue"], leg["callsEarly"] + 1)

    # ---- 跳过条件 ----

    def test_each_skip_condition_blocks_the_tick_on_its_own(self):
        for name, apply_js, revert_js in SKIP_CASES:
            with self.subTest(skip=name):
                code = SKIP_TEMPLATE.replace("__APPLY__", apply_js).replace("__REVERT__", revert_js)
                row = run_js(code)[0]
                self.assertFalse(row["skipped"], "「%s」成立时这一拍不能刷新" % name)
                self.assertEqual(row["callsWhileSkipped"], 0)
                self.assertTrue(row["fired"], "「%s」撤掉后同一时刻就该刷新（说明跳过的唯一原因是它）" % name)
                self.assertEqual(row["callsAfter"], 1)

    def test_terminal_and_far_plan_tasks_do_not_block(self):
        res = run_js(AUTO_REFRESH_PRELUDE + STUB_REFRESH + r"""
__advance(10.5);
const at = (sec) => __schoolText(bnowS() + sec);
S.busy = true;
S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map([
  ["t1", { task_id: "t1", activity_id: "a1", name: "活动一", status: "success", sign_start: at(-3600) }],
  ["t2", { task_id: "t2", activity_id: "a2", name: "活动二", status: "waiting", sign_start: at(7200) }],
]) };
out.push({ fired: await __tick(), calls: __rc.length });
""")
        self.assertTrue(res[0]["fired"], "已结束的场次和远未开放的场次都不该拦住自动刷新")

    # ---- 窗口不可见与恢复 ----

    def test_hidden_window_never_refreshes_and_catches_up_on_return(self):
        res = run_js(AUTO_REFRESH_PRELUDE + STUB_REFRESH + r"""
__advance(12);
document.hidden = true;
const hiddenDoc = await __tick();
__advance(1);
const hiddenDoc2 = await __tick();
document.hidden = false;
__backendHidden = true;                /* 藏到托盘：document.hidden 不一定为真，后端说了算 */
const hiddenBackend = await __tick();
const callsWhileHidden = __rc.length;
__backendHidden = false;               /* 回到可见：已满 10 分钟，立即补刷一次 */
const back = await __tick();
const again = await __tick();
out.push({ hiddenDoc, hiddenDoc2, hiddenBackend, callsWhileHidden, back, again, calls: __rc });
""")
        data = res[0]
        self.assertFalse(data["hiddenDoc"])
        self.assertFalse(data["hiddenDoc2"])
        self.assertFalse(data["hiddenBackend"])
        self.assertEqual(data["callsWhileHidden"], 0, "不可见期间一次都不刷新")
        self.assertTrue(data["back"], "恢复可见且已满 10 分钟：立即补刷")
        self.assertFalse(data["again"], "补刷只补一次")
        self.assertEqual(data["calls"], [{"quiet": True, "background": True}])

    def test_backend_without_window_visibility_counts_as_visible(self):
        res = run_js(AUTO_REFRESH_PRELUDE + STUB_REFRESH + r"""
delete window.pywebview.api.window_visibility;     /* 老后端没有这个接口 */
__advance(10.5);
out.push({ fired: await __tick(), calls: __rc.length });
""")
        self.assertTrue(res[0]["fired"], "问不到后端时只看 document.hidden，不能永远不刷新")

    # ---- 后台不闪 ----

    def test_background_round_has_no_skeleton_checking_capsule_or_result_box(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
S.selected.add("a1");
S.selected.add("a2");
__advance(10.5);
const seen = [];
const realRender = render;
render = () => { seen.push(S.listState); realRender(); };
let loginPaints = 0;
const realPaintLogin = paintLogin;
paintLogin = () => { loginPaints += 1; realPaintLogin(); };
const resultBefore = document.querySelector("#result").innerHTML;
const calls0 = { check: __calls.check.length, list: __calls.list.length };
const fired = await __tick();
paintFreshness();
const during = {
  fired: fired, listState: S.listState, checking: S.login.checking,
  renders: seen.length, loginPaints: loginPaints,
  pill: document.querySelector("#pill").dataset.state,
  isLoading: document.querySelector("#list").classList.contains("is-loading"),
  result: document.querySelector("#result").innerHTML === resultBefore,
  freshHidden: document.querySelector("#fresh").hidden,
  items: S.items.length, selected: Array.from(S.selected),
  newCheck: __calls.check.length - calls0.check, newList: __calls.list.length - calls0.list,
};
const a3 = Object.assign({}, __ITEMS[0], { id: "a3", name: "活动三" });
const monoBefore = S.listAtMono;
__advance(0.5);
__finish([__ITEMS[0], a3]);            /* a2 下线、a3 新增 */
out.push({ during: during, seen: seen, after: {
  listState: S.listState, ids: __ids(), selected: Array.from(S.selected),
  advancedMono: S.listAtMono > monoBefore, checking: S.login.checking,
  result: document.querySelector("#result").innerHTML === resultBefore } });
""")
        data = res[0]
        during = data["during"]
        self.assertTrue(during["fired"])
        self.assertEqual(during["newCheck"], 1, "后台轮照常查登录并拉列表，各发一次")
        self.assertEqual(during["newList"], 1)
        self.assertEqual(during["listState"], "ready", "后台刷新不进 loading，不出骨架")
        self.assertFalse(during["isLoading"])
        self.assertFalse(during["checking"], "后台刷新不进「检查中」")
        self.assertNotEqual(during["pill"], "checking")
        self.assertEqual(during["renders"], 0, "发起后台轮不重画")
        self.assertEqual(during["loginPaints"], 0, "发起后台轮不重画登录胶囊")
        self.assertTrue(during["result"], "不弹结果框")
        self.assertFalse(during["freshHidden"], "「N 分钟前更新」照常显示上次成功时刻")
        self.assertEqual(during["items"], 2, "等待期间原列表原样在")
        self.assertEqual(sorted(during["selected"]), ["a1", "a2"])
        after = data["after"]
        self.assertNotIn("loading", data["seen"], "整个后台轮里没有任何一帧是加载态")
        self.assertEqual(after["listState"], "ready")
        self.assertEqual(after["ids"], ["a1", "a3"])
        self.assertEqual(after["selected"], ["a1"], "勾选保留仍在列表里的场次，下线的移出")
        self.assertTrue(after["advancedMono"], "成功后「N 分钟前更新」重新计时")
        self.assertFalse(after["checking"])
        self.assertTrue(after["result"])

    # ---- 后台失败 ----

    def test_background_failure_keeps_list_and_selection_without_noise(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
S.selected.add("a1");
S.selected.add("a2");
__advance(10.5);
const resultBefore = document.querySelector("#result").innerHTML;
const logsBefore = S.recentLogs.length;
const fired = await __tick();
__failList("连不上学校站点");
await __flush();
out.push({ fired: fired, listState: S.listState, listError: S.listError, ids: __ids(),
  selected: Array.from(S.selected), newLogs: S.recentLogs.slice(logsBefore),
  runtimeError: S.runtime.error, listPending: S.runtime.listPending,
  result: document.querySelector("#result").innerHTML === resultBefore,
  isLoading: document.querySelector("#list").classList.contains("is-loading") });
""")
        data = res[0]
        self.assertTrue(data["fired"])
        self.assertEqual(data["ids"], ["a1", "a2"], "后台失败不清列表")
        self.assertEqual(sorted(data["selected"]), ["a1", "a2"], "后台失败不清勾选")
        self.assertEqual(data["listState"], "ready", "不切到错误空态")
        self.assertEqual(data["listError"], "")
        self.assertEqual([line for line in data["newLogs"] if "活动列表" in line], [],
                         "单次后台失败不写失败日志")
        self.assertIsNone(data["runtimeError"], "不挂横幅")
        self.assertTrue(data["result"], "不弹结果框")
        self.assertFalse(data["listPending"], "这一轮要收口，不能一直挂着")
        self.assertFalse(data["isLoading"])

    def test_manual_refresh_failure_still_clears_the_list(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
S.selected.add("a1");
refresh(false);
const during = S.listState;
__failList("连不上学校站点");
out.push({ during: during, listState: S.listState, ids: __ids(), selected: Array.from(S.selected) });
""")
        data = res[0]
        self.assertEqual(data["during"], "loading", "手动刷新仍然出骨架")
        self.assertEqual(data["listState"], "error", "手动刷新失败的老行为不变")
        self.assertEqual(data["ids"], [])
        self.assertEqual(data["selected"], [])

    def test_every_failure_channel_keeps_the_list_and_counts_toward_three(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
S.selected.add("a1");
const channels = [
  /* 桥接抛错 */
  async () => {
    window.pywebview.api.list_activities = () => Promise.reject(new Error("桥接断了"));
    return await __tick();
  },
  /* 入队被同步拒绝 */
  async () => {
    window.pywebview.api.list_activities = () => Promise.resolve({ ok: false, text: "正在关闭" });
    return await __tick();
  },
  /* 130 秒没有回应 */
  async () => {
    window.pywebview.api.list_activities = () => Promise.resolve({ ok: true, queued: true });
    const fired = await __tick();
    return { fired: fired, timer: __fire(130000) };
  },
];
const rows = [];
for (const channel of channels) {
  __advance(10.5);
  const got = await channel();
  await __flush();
  __checkOk();
  rows.push({ got: got, listState: S.listState, ids: __ids(), selected: Array.from(S.selected),
    logs: __autoLogs(), listPending: S.runtime.listPending, checkPending: S.runtime.checkPending });
}
out.push(rows);
""")
        rows = res[0]
        self.assertEqual(len(rows), 3)
        for index, row in enumerate(rows):
            self.assertEqual(row["listState"], "ready", row)
            self.assertEqual(row["ids"], ["a1", "a2"], row)
            self.assertEqual(row["selected"], ["a1"], row)
            self.assertFalse(row["listPending"], "每条失败路径都要把本轮列表分支收口: %r" % row)
            self.assertFalse(row["checkPending"])
            self.assertEqual(len(row["logs"]), 1 if index == 2 else 0,
                             "三条不同路径的失败合起来算连续 3 次，只在第 3 次写一条: %r" % row)
        self.assertTrue(rows[2]["got"]["timer"], "超时兜底必须真的挂着计时器")

    def test_three_consecutive_failures_write_exactly_one_record(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
const counts = [];
for (let i = 0; i < 5; i += 1) {
  __advance(10.5);
  const fired = await __tick();
  __failList();
  await __flush();
  counts.push({ fired: fired, logs: __autoLogs() });
}
out.push(counts);
""")
        rows = res[0]
        self.assertTrue(all(row["fired"] for row in rows))
        self.assertEqual([len(row["logs"]) for row in rows], [0, 0, 1, 1, 1],
                         "第 3 次失败写一条，之后继续失败也不刷屏")
        self.assertEqual(rows[2]["logs"][0],
                         "活动列表自动刷新连续 3 次没成功，列表还是 10:00 的；可以点「刷新」重试")

    def test_a_success_resets_the_failure_count(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
const round = async (ok) => {
  __advance(10.5);
  const fired = await __tick();
  if (ok) __finish(); else __failList();
  await __flush();
  return { fired: fired, logs: __autoLogs().length };
};
const rows = [];
for (const ok of [false, false, true, false, false, false]) rows.push(await round(ok));
out.push(rows);
""")
        rows = res[0]
        self.assertTrue(all(row["fired"] for row in rows))
        self.assertEqual([row["logs"] for row in rows], [0, 0, 0, 0, 0, 1],
                         "失败、失败、成功之后重新数：再连续失败 3 次才写")

    # ---- 接线 ----

    def test_start_auto_refresh_installs_a_single_30_second_check(self):
        res = run_js(AUTO_REFRESH_PRELUDE + r"""
const made = [];
setInterval = (fn, ms) => { made.push(ms); return made.length; };
autoRefreshTimer = null;
startAutoRefresh();
startAutoRefresh();
out.push({ made: made });
""")
        self.assertEqual(res[0]["made"], [30000], "只起一个 30 秒检查，重复调用不叠加")

    def test_app_js_starts_the_loop_and_ticks_when_the_window_returns(self):
        source = (TESTS.parent / "ui" / "app.js").read_text(encoding="utf-8")
        boot = source[source.index("async function boot()"):source.index("window.onBackend = {")]
        self.assertIn("startAutoRefresh()", boot, "启动流程里要起一次自动刷新检查")
        listener = source[source.index('document.addEventListener("visibilitychange"'):
                          source.index("setInterval(tick, 1000)")]
        self.assertIn("autoRefreshTick()", listener, "窗口变为可见时要立即看一次是否该补刷")


class SilentReloginResidualTests(unittest.TestCase):
    """静默自动登录的界面残留（计划 20261112）：关对话框不打断电脑的自动登录，
    胶囊不停在「自动登录中…」。"""

    AUTO_LIVE = ('{ state: "waiting_code", mode: "auto", live: true, origin: "auto", '
                 'flow_id: "f1", challenge_id: "c1", attempts: 1, image: "" }')

    def test_closing_the_dialog_keeps_the_computers_own_auto_login(self):
        """R1：对话框接上的是电脑自己发起的那一场，关掉只收对话框，不取消这一场。"""
        res = run_js(r"""
const cancels = [];
window.pywebview = { api: { relogin_cancel: (id) => { cancels.push(id); return Promise.resolve({ ok: true }); } } };
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin(""" + self.AUTO_LIVE + r""");
openRelogin();
const opened = { open: S.relogin.open, step: S.relogin.step, flow: S.relogin.flowId };
closeRelogin();
out.push({ opened, cancels, open: S.relogin.open, auto: !!S.autoLogin,
  pill: document.querySelector("#pill-text").textContent });
""")
        data = res[0]
        self.assertEqual(data["opened"]["step"], "wait")
        self.assertEqual(data["opened"]["flow"], "f1", "对话框接上的是电脑正在跑的这一场")
        self.assertEqual(data["cancels"], [], "关掉对话框不能把电脑的自动登录取消")
        self.assertFalse(data["open"])
        self.assertTrue(data["auto"])
        self.assertEqual(data["pill"], "自动登录中…")

    def test_closing_a_user_started_flow_still_cancels_it(self):
        """R1 守卫：用户自己发起的登录（origin 不是 auto），关掉对话框仍然取消。"""
        res = run_js(r"""
const cancels = [];
window.pywebview = { api: { relogin_cancel: (id) => { cancels.push(id); return Promise.resolve({ ok: true }); } } };
S.login.present = true;
S.login.result = "expired";
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "desktop", flow_id: "f2", challenge_id: "c1", attempts: 1,
  image: "data:image/png;base64,AAA" });
openRelogin();
const step = S.relogin.step;
closeRelogin();
out.push({ step, cancels });
""")
        data = res[0]
        self.assertEqual(data["step"], "cap")
        self.assertEqual(data["cancels"], ["f2"])

    def test_closing_after_the_auto_flow_handed_off_still_cancels(self):
        """R1 守卫：电脑那一场已转人工（等用户输验证码）时，关掉对话框照旧取消。"""
        res = run_js(r"""
const cancels = [];
window.pywebview = { api: { relogin_cancel: (id) => { cancels.push(id); return Promise.resolve({ ok: true }); } } };
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "auto", flow_id: "f1", challenge_id: "c1", attempts: 3, handoff: true,
  image: "data:image/png;base64,AAA" });
openRelogin();
const step = S.relogin.step;
closeRelogin();
out.push({ step, cancels });
""")
        data = res[0]
        self.assertEqual(data["step"], "cap")
        self.assertEqual(data["cancels"], ["f1"])

    def test_pill_leaves_auto_login_when_a_valid_check_arrives(self):
        """R2：没等到中继的收尾事件，学校校验已经确认有效，胶囊要变「已登录」。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
const during = document.querySelector("#pill-text").textContent;
window.onBackend.check({ ok: true, result: "valid", hours_left: 9, session_present: true });
out.push({ during, auto: !!S.autoLogin,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state });
""")
        data = res[0]
        self.assertEqual(data["during"], "自动登录中…")
        self.assertFalse(data["auto"])
        self.assertEqual(data["text"], "已登录")
        self.assertEqual(data["state"], "ok")

    def test_pill_leaves_auto_login_when_the_check_cannot_reach_the_school(self):
        """R2：自动登录中来了一次「暂时无法确认」，没有自动中继在跑就不能还写自动登录中。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.check({ ok: false, result: "unknown", session_present: true });
out.push({ auto: !!S.autoLogin,
  text: document.querySelector("#pill-text").textContent });
""")
        data = res[0]
        self.assertFalse(data["auto"])
        self.assertNotEqual(data["text"], "自动登录中…")

    def test_a_live_auto_flow_survives_an_unknown_check(self):
        """R2 守卫：电脑确实还在自动登录时，一次「暂时无法确认」不能把胶囊提前改掉。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin(""" + self.AUTO_LIVE + r""");
window.onBackend.check({ ok: false, result: "unknown", session_present: true });
out.push({ auto: !!S.autoLogin });
""")
        self.assertTrue(res[0]["auto"])

    def test_relay_replay_after_a_valid_check_does_not_bring_auto_login_back(self):
        """R2：校验已确认有效，中继重放一条旧的「电脑自动登录中」快照，不能再亮自动登录中。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: true, result: "valid", hours_left: 9, session_present: true });
window.onBackend.phone_relogin(""" + self.AUTO_LIVE + r""");
out.push({ auto: !!S.autoLogin,
  text: document.querySelector("#pill-text").textContent });
""")
        data = res[0]
        self.assertFalse(data["auto"])
        self.assertEqual(data["text"], "已登录")

    def test_pill_leaves_auto_login_when_the_refresh_check_fails_outright(self):
        """R2：手动刷新里 check 请求本身失败（桥接异常、没能开始），结论落 unknown，
        没有自动中继在跑就不能还停在自动登录中。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
const before = document.querySelector("#pill-text").textContent;
window.pywebview = { api: {
  check: () => Promise.reject(new Error("bridge down")),
  list_activities: () => Promise.resolve({ ok: true, queued: true }),
} };
refresh(false);
for (let i = 0; i < 12; i += 1) await Promise.resolve();
const thrown = { auto: !!S.autoLogin, text: document.querySelector("#pill-text").textContent,
                 result: S.login.result };
S.login.result = "expired";
S.autoLogin = true;
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: false, error: "busy", text: "这次检查没能开始" }),
  list_activities: () => Promise.resolve({ ok: true, queued: true }),
} };
refresh(false);
for (let i = 0; i < 12; i += 1) await Promise.resolve();
const refused = { auto: !!S.autoLogin, text: document.querySelector("#pill-text").textContent,
                  result: S.login.result };
out.push({ before, thrown, refused });
""")
        data = res[0]
        self.assertEqual(data["before"], "自动登录中…")
        self.assertEqual(data["thrown"]["result"], "unknown")
        self.assertFalse(data["thrown"]["auto"])
        self.assertNotEqual(data["thrown"]["text"], "自动登录中…")
        self.assertEqual(data["refused"]["result"], "unknown")
        self.assertFalse(data["refused"]["auto"])
        self.assertNotEqual(data["refused"]["text"], "自动登录中…")

    def test_pill_leaves_auto_login_when_the_check_times_out(self):
        """R2：check 超过 100 秒没回应，落 unknown，不能一直停在自动登录中。"""
        res = run_js(r"""
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
const timers = [];
const realSetTimeout = setTimeout;
setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
window.pywebview = { api: {
  check: () => new Promise(() => {}),
  list_activities: () => new Promise(() => {}),
} };
refresh(false);
setTimeout = realSetTimeout;
const hit = timers.filter((t) => t.ms === 100000);
hit.forEach((t) => t.fn());
out.push({ timers: hit.length, auto: !!S.autoLogin, result: S.login.result,
  text: document.querySelector("#pill-text").textContent });
""")
        data = res[0]
        self.assertEqual(data["timers"], 1)
        self.assertEqual(data["result"], "unknown")
        self.assertFalse(data["auto"])
        self.assertNotEqual(data["text"], "自动登录中…")

    def test_pill_leaves_auto_login_when_the_relay_finishes_or_hands_off(self):
        """R2 守卫：原有的收回路径（中继结束、转人工、静默失败）继续有效。"""
        res = run_js(r"""
const text = () => document.querySelector("#pill-text").textContent;
S.login.present = true;
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin(""" + self.AUTO_LIVE + r""");
const live = text();
window.onBackend.phone_relogin({ state: "failed", mode: "auto", live: false, origin: "auto",
  flow_id: "f1", safe_error: "timeout" });
const failed = { auto: !!S.autoLogin, text: text() };
window.onBackend.check({ ok: false, result: "expired", recovering: true });
window.onBackend.phone_relogin({ state: "waiting_code", mode: "manual", live: true,
  origin: "auto", flow_id: "f3", challenge_id: "c1", attempts: 3, handoff: true,
  image: "data:image/png;base64,AAA" });
const handoff = { auto: !!S.autoLogin, text: text() };
out.push({ live, failed, handoff });
""")
        data = res[0]
        self.assertEqual(data["live"], "自动登录中…")
        self.assertFalse(data["failed"]["auto"])
        self.assertEqual(data["failed"]["text"], "登录已失效")
        self.assertFalse(data["handoff"]["auto"])
        self.assertEqual(data["handoff"]["text"], "登录已失效")


if __name__ == "__main__":
    unittest.main()
