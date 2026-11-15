#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新登录对话框的用户可见结果（行为测试）。

在 node 沙箱里按 index.html 的加载序跑真实界面脚本，按「有没有保存账号 × 保存的密码有没有被拒绝」
走不同入口，看用户看得到的东西：标题、副句、当前哪一步、底栏按钮、红字。
不对源码文本做断言，搬文件也不会红。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

PRELUDE = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = false;
S.busy = false;
S.autoLogin = false;
S.login = { ok: false, present: true, checking: false, loginPending: false, result: "expired",
            handoff: false, expireAt: null, estimateReason: null, hours: null,
            lastCheckAt: "", lastCheckState: "unknown", view: {} };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
window.pywebview = { api: {} };
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
const cred = (fields) => {
  S.advanced = { credential: fields };
  if (window.PhonePanel && window.PhonePanel.state) window.PhonePanel.state.advanced = { credential: fields };
};
const title = () => $("#dlg-relogin-title").textContent;
const sub = () => $("#rl-sub").textContent;
const stepOf = () => S.relogin.step;
const shown = (id) => !$("#" + id).hidden;
const logText = () => ($("#log")._children || []).map((row) => row.textContent).join("\n");
"""


class ReloginEntryTests(unittest.TestCase):
    """按保存账号的情况落到第一步。"""

    def test_saved_account_skips_the_form_and_waits_for_the_computer(self):
        """保存过账号时点重新登录直接开登录，不再先让用户填账号密码。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
window.pywebview = { api: { relogin_begin: () => Promise.resolve({ ok: true, flow_id: "f1", mode: "auto" }) } };
openRelogin();
await __flush();
out.push({ title: title(), form: shown("rl-login"), wait: $("#rl-wait-text").textContent,
           step: stepOf(), flow: S.relogin.flowId });
""")[0]
        self.assertEqual(data["title"], "重新登录")
        self.assertFalse(data["form"], "有保存账号不该再显示登录表单")
        self.assertIn("识别验证码", data["wait"])
        self.assertEqual(data["step"], "wait")
        self.assertEqual(data["flow"], "f1")

    def test_rejected_saved_password_opens_the_update_step(self):
        """保存的密码被学校拒绝过时，直接说明「保存的密码不对」并只留更新入口。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: true, username: "20230001" });
openRelogin();
out.push({ title: title(), sub: sub(), bad: shown("rl-bad"), form: shown("rl-login"),
           update: shown("btn-bad-update"), browser: shown("btn-bad-browser"),
           code: shown("btn-rl-code") });
""")[0]
        self.assertEqual(data["title"], "保存的密码不对")
        self.assertEqual(data["sub"], "自动登录已暂停")
        self.assertTrue(data["bad"], "要落在「保存的密码不对」这一步")
        self.assertFalse(data["form"], "不该再显示登录表单")
        self.assertTrue(data["update"], "要能去更新账号密码")
        self.assertTrue(data["browser"], "也能改用浏览器登录")
        self.assertFalse(data["code"], "这一步没有输验证码的按钮")

    def test_without_a_saved_account_starts_at_the_login_form(self):
        """没保存账号时从登录表单开始：宽一屏，账号密码都填了才亮「下一步」。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
out.push({ title: title(), sub: sub(), form: shown("rl-login"), cap: shown("rl-cap"),
           wide: $("#dlg-relogin").classList.contains("wide"), next: shown("btn-lg-next"),
           nextDisabled: $("#btn-lg-next").disabled });
""")[0]
        self.assertEqual(data["title"], "登录学校账号")
        self.assertEqual(data["sub"], "两种方式都可以，选你放心的那种")
        self.assertTrue(data["form"], "没账号要显示登录表单")
        self.assertFalse(data["cap"], "第一步不该显示验证码")
        self.assertTrue(data["wide"], "登录这一屏宽一档")
        self.assertTrue(data["next"], "登录步要有「下一步」按钮")
        self.assertTrue(data["nextDisabled"], "账号密码没填之前不能下一步")

    def test_school_page_step_says_the_browser_is_open(self):
        """改用学校登录页时，标题说明已经打开浏览器，底栏只留取消。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
reloginStep("lgwait");
out.push({ title: title(), sub: sub(), cancel: shown("btn-rl-cancel"),
           browser: shown("btn-rl-browser"), next: shown("btn-lg-next") });
""")[0]
        self.assertEqual(data["title"], "在学校登录页登录")
        self.assertEqual(data["sub"], "已经用浏览器打开学校登录页")
        self.assertTrue(data["cancel"])
        self.assertFalse(data["browser"])
        self.assertFalse(data["next"])

    def test_confirm_step_offers_the_automatic_login_once(self):
        """确认步说「自动登录一次？」并给出自动登录与取消两个按钮。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
reloginStep("confirm");
out.push({ title: title(), sub: sub(), auto: shown("btn-rl-auto"), cancel: shown("btn-rl-cancel"),
           code: shown("btn-rl-code") });
""")[0]
        self.assertEqual(data["title"], "自动登录一次？")
        self.assertEqual(data["sub"], "验证码由电脑识别")
        self.assertTrue(data["auto"])
        self.assertTrue(data["cancel"])
        self.assertFalse(data["code"])


class ReloginCodeStepTests(unittest.TestCase):
    """验证码步：谁填密码、按钮怎么摆、什么时候亮。"""

    def test_code_step_explains_the_computer_fills_the_password(self):
        """电脑已经开了一场在输码时，标题是「输入验证码」，副句说明账号密码由电脑填。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,xx",
                      flow_id: "f1", attempts: 0 });
out.push({ title: title(), sub: sub(), cap: shown("rl-cap"), wait: shown("rl-wait"),
           codeDisabled: $("#btn-rl-code").disabled,
           browser: shown("btn-rl-browser"), back: shown("btn-lg-back") });
""")[0]
        self.assertEqual(data["title"], "输入验证码")
        self.assertEqual(data["sub"], "账号 20****01 和密码由电脑自动填写")
        self.assertTrue(data["cap"], "要显示验证码这一步")
        self.assertFalse(data["wait"], "验证码步不该同时显示等待")
        self.assertTrue(data["browser"], "验证码步留「改用浏览器登录」")
        self.assertFalse(data["back"], "不是从登录表单进来的，就没有上一步")
        self.assertTrue(data["codeDisabled"], "验证码没填满 4 位时不能提交")

    def test_code_step_after_the_form_says_the_password_is_filled(self):
        """从登录表单点进来的验证码步，副句说密码已填好，第一个按钮变成「上一步」。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
window.pywebview = { api: { relogin_begin: () => Promise.resolve({ ok: true, flow_id: "f2", mode: "auto" }) } };
openLogin();
$("#rl-user").value = "20230001";
$("#rl-pass").value = "secret";
submitReloginForm();
await __flush();
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,yy", flow_id: "f2" });
out.push({ title: title(), sub: sub(), back: shown("btn-lg-back"), browser: shown("btn-rl-browser") });
""")[0]
        self.assertEqual(data["title"], "输入验证码")
        self.assertTrue(data["sub"].startswith("账号 "), data["sub"])
        self.assertTrue(data["sub"].endswith("，密码已填好"), data["sub"])
        self.assertTrue(data["back"], "从表单进来要能退回上一步")
        self.assertFalse(data["browser"], "第一个按钮该是上一步")

    def test_relay_snapshot_reopens_the_code_step_with_its_image(self):
        """中继里已经有一张等着的验证码时，点重新登录直接接上它，不另开一场。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
reloginRelay = { live: true, origin: "manual", flow_id: "f7", mode: "manual",
                 state: "waiting_code", image: "data:image/png;base64,zz", attempts: 1 };
openRelogin();
out.push({ title: title(), flow: S.relogin.flowId,
           tries: $("#rl-cap-tries").textContent });
""")[0]
        self.assertEqual(data["title"], "输入验证码")
        self.assertEqual(data["flow"], "f7")
        self.assertEqual(data["tries"], "已经试过 1 次，换了一张新图。")

    def test_wrong_captcha_keeps_the_code_step_with_a_red_hint(self):
        """验证码认错后仍停在输验证码这一步，换一张图，并用红字说明电脑没认出来。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,aa",
                      flow_id: "f3", attempts: 0 });
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,bb",
                      flow_id: "f3", attempts: 2, handoff: true });
out.push({ title: title(), cap: shown("rl-cap"), tries: $("#rl-cap-tries").textContent,
           err: $("#rl-err").hidden, errText: $("#rl-err").textContent });
""")[0]
        self.assertEqual(data["title"], "输入验证码")
        self.assertTrue(data["cap"], "认错以后还要能接着输这一张")
        self.assertEqual(data["tries"], "已经试过 2 次，换了一张新图。")
        self.assertFalse(data["err"], "要给出红字说明")
        self.assertEqual(data["errText"], "电脑没认出这张验证码，请输入验证码。")

    def test_typed_wrong_code_stays_on_code_step_with_grey_tries_note(self):
        """用户自己输错验证码（后端换了一张图、不带转人工）：仍停在输验证码那一步，清空输入，次数只给灰字说明。
        现码手输认错不出红字，与 D6 原文「给出红字」不一致，留给状态机那一步处理。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,aa",
                      flow_id: "f4", attempts: 0 });
$("#rl-code").value = "ab12";
receiveReloginState({ state: "waiting_code", mode: "manual", image: "data:image/png;base64,bb",
                      flow_id: "f4", attempts: 1 });
out.push({ title: title(), cap: shown("rl-cap"), tries: $("#rl-cap-tries").textContent,
           errHidden: $("#rl-err").hidden, code: $("#rl-code").value });
""")[0]
        self.assertEqual(data["title"], "输入验证码")
        self.assertTrue(data["cap"], "认错以后还要能接着输这一张")
        self.assertEqual(data["tries"], "已经试过 1 次，换了一张新图。")
        self.assertTrue(data["errHidden"], "现码手输认错不出红字")
        self.assertEqual(data["code"], "", "换了新图，输入框要清空")

    def test_result_step_reports_success_with_one_button(self):
        """登录成功后对话框停在结果步，只留「知道了」。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "success", live: false, flow_id: "f5" });
out.push({ title: title(), msg: $("#rl-msg-text").textContent, done: shown("btn-rl-done"),
           cap: shown("rl-cap"), foot: shown("rl-foot") });
""")[0]
        self.assertEqual(data["msg"], "重新登录成功。")
        self.assertTrue(data["done"], "结果步要留「知道了」")
        self.assertFalse(data["cap"], "成功以后不该还停在验证码步")
        self.assertTrue(data["foot"], "结果步要有底栏")


class ReloginFeedbackTests(unittest.TestCase):
    """红字、来不及、关掉时的收尾。"""

    def test_error_line_only_shows_when_it_has_text(self):
        """红字条有内容才出现，传空串就收起。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
const before = $("#rl-err").hidden;
reloginError("账号和密码都要填。");
const text = $("#rl-err").textContent;
const after = $("#rl-err").hidden;
reloginError("");
out.push({ before, text, after, cleared: $("#rl-err").hidden });
""")[0]
        self.assertTrue(data["before"], "没有错误时红字条不该出现")
        self.assertEqual(data["text"], "账号和密码都要填。")
        self.assertFalse(data["after"], "有错误时要露出来")
        self.assertTrue(data["cleared"], "错误清空后红字条要收回去")

    def test_busy_step_hides_the_whole_foot_bar(self):
        """等待步没有按钮，整条底栏收起，不留一条空边。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
reloginStep("wait", "正在登录…");
out.push({ title: title(), foot: shown("rl-foot"), cancel: shown("btn-rl-cancel"),
           code: shown("btn-rl-code"), wait: $("#rl-wait-text").textContent });
""")[0]
        self.assertEqual(data["wait"], "正在登录…")
        self.assertFalse(data["foot"], "等待步整条底栏收起")
        self.assertFalse(data["cancel"], "等待步不该留取消按钮")
        self.assertFalse(data["code"])

    def test_plan_too_late_is_explained_with_a_reason(self):
        """计划来不及时说清楚「现在来不及重新登录」，并带上后端的原因。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
reloginStep("msg", reloginRefusal({ error: "plan_late", text: "有场次正在提交" }));
out.push({ text: $("#rl-msg-text").textContent, done: shown("btn-rl-done") });
""")[0]
        self.assertIn("现在来不及重新登录", data["text"])
        self.assertIn("有场次正在提交", data["text"])
        self.assertIn("电脑能自动登录就会自动登录", data["text"])
        self.assertTrue(data["done"], "说明完留一个「知道了」")

    def test_bad_password_event_switches_to_the_update_step(self):
        """学校说密码不对时，不重试，直接进「保存的密码不对」让用户更新。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "failed", safe_error: "bad_password", flow_id: "f6" });
out.push({ title: title(), sub: sub(), update: shown("btn-bad-update") });
""")[0]
        self.assertEqual(data["title"], "保存的密码不对")
        self.assertEqual(data["sub"], "自动登录已暂停")
        self.assertTrue(data["update"])

    def test_closing_cancels_the_live_login(self):
        """用户中途关掉对话框时，要取消还挂着的那一场登录。"""
        data = run_js(PRELUDE + r"""
const calls = [];
window.pywebview = { api: { relogin_cancel: (id) => { calls.push(id); return Promise.resolve({ ok: true }); } } };
$("#dlg-relogin").removeAttribute = () => {};
S.relogin = { open: true, step: "cap", flowId: "f3", challengeId: "c1" };
reloginRelay = null;
await closeRelogin();
out.push({ calls, open: S.relogin.open, step: stepOf() });
""")[0]
        self.assertFalse(data["open"], "关掉后对话框是关着的")
        self.assertEqual(data["calls"], ["f3"], "关掉时要取消这一场")

    def test_closing_keeps_the_computers_own_auto_login(self):
        """关掉的若是电脑自己在做的自动登录，就不取消——那只是不看了。"""
        data = run_js(PRELUDE + r"""
const calls = [];
window.pywebview = { api: { relogin_cancel: (id) => { calls.push(id); return Promise.resolve({ ok: true }); } } };
$("#dlg-relogin").removeAttribute = () => {};
S.relogin = { open: true, step: "cap", flowId: "f4", challengeId: "c2" };
reloginRelay = { live: true, origin: "auto", flow_id: "f4" };
await closeRelogin();
out.push({ calls, open: S.relogin.open });
""")[0]
        self.assertFalse(data["open"], "关掉后对话框是关着的")
        self.assertEqual(data["calls"], [], "电脑自己的自动登录不该被关对话框打断")


class ReloginEdgeCasesTests(unittest.TestCase):
    """等待步标题、接上中继、关掉时取消、成功收尾这些边角分支。"""

    def test_checking_captcha_keeps_the_code_title(self):
        """正在核对验证码时标题仍是「输入验证码」，不换成等待说法。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
reloginStep("wait", "正在核对验证码…");
out.push({ title: title(), step: stepOf() });
""")[0]
        self.assertEqual(data["title"], "输入验证码")

    def test_auto_login_wait_step_says_so(self):
        """电脑正在自动登录时，等待步标题是「正在自动登录」并带上保存的账号。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
reloginStep("wait", "电脑正在自动登录…");
out.push({ title: title(), sub: sub() });
""")[0]
        self.assertEqual(data["title"], "正在自动登录")
        self.assertEqual(data["sub"], "用保存的账号 20****01")

    def test_browser_way_offers_the_school_page_button(self):
        """选「用学校登录页」后，登录步的按钮换成「打开学校登录页」，没有下一步。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
S.relogin.way = "browser";
reloginStep("login");
out.push({ webopen: shown("btn-lg-webopen"), next: shown("btn-lg-next") });
""")[0]
        self.assertTrue(data["webopen"], "浏览器方式要给「打开学校登录页」")
        self.assertFalse(data["next"], "浏览器方式没有下一步")

    def test_relay_auto_mode_says_the_computer_is_recognizing(self):
        """接上电脑正在自动识别的那场时，等待行说「电脑正在识别验证码…」。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
reloginRelay = { live: true, origin: "auto", flow_id: "f9", mode: "auto",
                 state: "starting", image: "" };
openRelogin();
out.push({ step: stepOf(), wait: $("#rl-wait-text").textContent });
""")[0]
        self.assertEqual(data["step"], "wait")
        self.assertEqual(data["wait"], "电脑正在识别验证码…")

    def test_generic_refusal_shows_the_backend_text(self):
        """后端拒绝但不是 plan_late 时，结果步原样显示后端给的说明。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
openRelogin();
reloginStep("msg", reloginRefusal({ ok: false, text: "服务器忙，请稍后再试" }));
out.push({ text: $("#rl-msg-text").textContent });
""")[0]
        self.assertEqual(data["text"], "服务器忙，请稍后再试")

    def test_handoff_reminder_resets_after_a_non_handoff_event(self):
        """转人工的提醒只说一次；中间来过正常事件后，再转人工要重新提醒。

        两次的验证码输错次数不同，提醒文字本来就不同；第二次还能写出来，说明「已经提醒过」
        这个记忆被正常事件清掉了。同一句话写两次会被运行记录去重，所以不能拿同一句比。
        """
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
receiveReloginState({ state: "waiting_code", mode: "manual", image: "a",
                      flow_id: "f1", attempts: 1, handoff: true });
const first = logText();
receiveReloginState({ state: "verifying", flow_id: "f1" });
receiveReloginState({ state: "waiting_code", mode: "manual", image: "b",
                      flow_id: "f1", attempts: 3, handoff: true });
out.push({ first, second: logText() });
""")[0]
        self.assertIn("电脑没认出验证码", data["first"])
        self.assertIn("3 次没认对", data["second"], "第二次转人工要再提醒一次")

    def test_verifying_state_draws_the_wait_step(self):
        """后端说正在校验/启动时，对话框停在等待步，不闪回验证码。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
S.relogin.flowId = "f1";
receiveReloginState({ state: "verifying", flow_id: "f1" });
out.push({ step: stepOf(), wait: $("#rl-wait-text").textContent });
""")[0]
        self.assertEqual(data["step"], "wait")
        self.assertEqual(data["wait"], "正在登录…")

    def test_closing_cancels_a_finished_auto_relay(self):
        """接上的那场已经停下（live=false）时，关掉对话框要照常取消，不把它当活的。"""
        data = run_js(PRELUDE + r"""
const calls = [];
window.pywebview = { api: { relogin_cancel: (id) => { calls.push(id); return Promise.resolve({ ok: true }); } } };
$("#dlg-relogin").removeAttribute = () => {};
S.relogin = { open: true, step: "wait", flowId: "f8", challengeId: "c8" };
reloginRelay = { live: false, origin: "auto", flow_id: "f8" };
await closeRelogin();
out.push({ calls });
""")[0]
        self.assertEqual(data["calls"], ["f8"])

    def test_browser_watch_stops_when_the_dialog_closes(self):
        """对话框关掉后，浏览器登录的轮询要停掉，不再盯着登录结论。"""
        data = run_js(PRELUDE + r"""
let tick = null;
window.setInterval = (fn) => { tick = fn; return 1; };
S.relogin = { open: true, step: "lgwait" };
S.login = { result: "none", ok: null };
watchBrowserLogin();
S.relogin.open = false;
S.login.result = "valid"; S.login.ok = true;
tick();
out.push({ log: logText(), open: S.relogin.open });
""")[0]
        self.assertNotIn("登录成功", data["log"], "关掉后不该再写成功记录")

    def test_browser_watch_closes_on_a_valid_login(self):
        """浏览器登录成功后，轮询自己关掉对话框并写一条成功记录。"""
        data = run_js(PRELUDE + r"""
let tick = null;
window.setInterval = (fn) => { tick = fn; return 1; };
window.clearInterval = () => {};
$("#dlg-relogin").removeAttribute = () => {};
S.relogin = { open: true, step: "lgwait" };
S.login = { result: "none", ok: null };
watchBrowserLogin();
S.login.result = "valid"; S.login.ok = true;
tick();
out.push({ log: logText(), open: S.relogin.open });
""")[0]
        self.assertIn("登录成功", data["log"])
        self.assertFalse(data["open"], "登录成功后对话框要自己关掉")

    def test_relay_without_a_challenge_does_not_open_the_code_step(self):
        """中继里不是「等验证码」的状态时，接上它只画等待步，不弹验证码。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
reloginRelay = { live: true, origin: "manual", flow_id: "f2", mode: "manual",
                 state: "verifying", image: "data:image/png;base64,x" };
openRelogin();
out.push({ step: stepOf(), cap: shown("rl-cap") });
""")[0]
        self.assertEqual(data["step"], "wait")
        self.assertFalse(data["cap"], "没有验证码图不该弹验证码步")

    def test_relay_auto_mode_waits_instead_of_showing_code(self):
        """中继是电脑自动识别时，接上它画等待步，不让用户输验证码。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
reloginRelay = { live: true, origin: "auto", flow_id: "f3", mode: "auto",
                 state: "waiting_code", image: "data:image/png;base64,y" };
openRelogin();
out.push({ step: stepOf(), cap: shown("rl-cap") });
""")[0]
        self.assertEqual(data["step"], "wait")
        self.assertFalse(data["cap"], "自动识别时不该让用户输验证码")

    def test_relay_without_an_image_waits_instead_of_showing_code(self):
        """中继说等验证码但还没给图时，先画等待步，不弹一张空验证码。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
reloginRelay = { live: true, origin: "manual", flow_id: "f4", mode: "manual",
                 state: "waiting_code", image: "" };
openRelogin();
out.push({ step: stepOf(), cap: shown("rl-cap") });
""")[0]
        self.assertEqual(data["step"], "wait")
        self.assertFalse(data["cap"], "没图不该弹验证码步")

    def test_success_during_a_plan_does_not_refresh_the_list(self):
        """计划跑着时重新登录成功，只说明一句，不另起一轮列表刷新打扰计划。"""
        data = run_js(PRELUDE + r"""
const calls = [];
window.doCheck = () => calls.push("check");
window.refresh = () => calls.push("refresh");
S.busy = true;
S.relogin = { open: false };
S.items = [];
reloginSucceeded("f1");
out.push({ calls });
""")[0]
        self.assertEqual(data["calls"], [], "忙碌时成功不该触发刷新")

    def test_closed_dialog_success_does_not_log_the_done_line(self):
        """对话框没开时收到成功，不写「重新登录成功」那一条运行记录。"""
        data = run_js(PRELUDE + r"""
S.busy = false;
S.relogin = { open: false };
S.login = { result: "none", ok: null };
S.items = [];
window.doCheck = () => {};
window.refresh = () => {};
receiveReloginState({ state: "success", flow_id: "f5" });
out.push({ log: logText() });
""")[0]
        self.assertNotIn("重新登录成功", data["log"])

    def test_closed_dialog_busy_success_logs_the_plan_line(self):
        """计划跑着、对话框没开时收到成功，运行记录写「报名计划照常继续」。"""
        data = run_js(PRELUDE + r"""
S.busy = true;
S.relogin = { open: false };
receiveReloginState({ state: "success", flow_id: "f6" });
out.push({ log: logText() });
""")[0]
        self.assertIn("重新登录成功，报名计划照常继续", data["log"])

    def test_open_dialog_busy_success_log_mentions_the_plan(self):
        """计划跑着、对话框开着时成功，运行记录要提一句报名计划照常继续。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
S.relogin.flowId = "f7";
S.busy = true;
receiveReloginState({ state: "success", flow_id: "f7" });
out.push({ log: logText() });
""")[0]
        self.assertIn("重新登录成功，报名计划照常继续", data["log"])

    def test_open_dialog_busy_success_message_mentions_the_plan(self):
        """计划跑着时成功，结果步的文字也要说明报名计划照常继续。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
S.relogin.flowId = "f8";
S.busy = true;
receiveReloginState({ state: "success", flow_id: "f8" });
out.push({ msg: $("#rl-msg-text").textContent });
""")[0]
        self.assertEqual(data["msg"], "重新登录成功，报名计划照常继续。")

    def test_stale_progress_from_another_flow_is_ignored(self):
        """不是当前这一场的进度事件直接忽略，对话框不被别的 flow 带跑。"""
        data = run_js(PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
S.relogin.flowId = "f9";
receiveReloginState({ state: "failed", safe_error: "timeout", flow_id: "other" });
out.push({ step: stepOf(), msg: $("#rl-msg-text").textContent });
""")[0]
        self.assertNotEqual(data["step"], "msg", "别的 flow 的失败不该改当前步骤")
        self.assertEqual(data["msg"], "")

    def test_login_pending_blocks_auto_refresh(self):
        """登录窗口还开着时，自动刷新列表要让路，不跟登录抢网络。"""
        data = run_js(PRELUDE + r"""
S.demo = false; S.online = true; S.busy = false; S.starting = false;
S.login = { result: "valid", loginPending: true, checking: false };
S.listState = "ready"; S.listAtMono = 0; S.cancel = { busyId: null };
S.round = { background: false }; S.runtime = { checkPending: false, listPending: false, error: null };
S.plan = { tasks: new Set() };
$("#btn-refresh").disabled = false;
out.push({ due: autoRefreshDue() });
""")[0]
        self.assertFalse(data["due"], "登录进行中不该自动刷新")


class ClosedDialogTests(unittest.TestCase):
    """对话框关着的时候，后台回来的结果不该把状态改到一半。"""

    def test_begin_result_after_closing_does_not_move_the_step(self):
        """开始登录的请求回来时对话框已经关了，就不该把流程推进到等待步。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
window.pywebview = { api: { relogin_begin: () => Promise.resolve({ ok: true, flow_id: "f9", mode: "auto" }) } };
S.relogin = { open: false, step: "login", flowId: "" };
await beginRelogin("20230001", "pw", false);
await __flush();
out.push({ flow: S.relogin.flowId, step: stepOf() });
""")[0]
        self.assertEqual(data["flow"], "", "对话框关着时不该记下流程号")
        self.assertEqual(data["step"], "login", "对话框关着时不该推进到等待步")

    def test_auto_once_result_after_closing_does_not_move_the_step(self):
        """自动登录那一次回来时对话框已关，流程号同样不该被记下。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
window.pywebview = { api: { relogin_auto_once: () => Promise.resolve({ ok: true, flow_id: "f8" }) } };
S.relogin = { open: false, step: "login", flowId: "" };
await autoReloginOnce();
await __flush();
out.push({ flow: S.relogin.flowId });
""")[0]
        # 这一支进来就先写了「电脑正在自动登录…」，所以这里只看流程号有没有被记下
        self.assertEqual(data["flow"], "", "对话框关着时不该记下流程号")


    def test_pick_way_after_closing_does_not_move_the_step(self):
        """对话框关着时选登录方式不该把流程推进到填写步。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
S.relogin = { open: false, step: "cap", flowId: "f1", way: "" };
reloginPickWay("browser");
out.push({ step: stepOf(), way: S.relogin.way });
""")[0]
        self.assertEqual(data["step"], "cap", "关着时不该换步")
        self.assertEqual(data["way"], "", "关着时不该记登录方式")

    def test_a_failed_code_answer_after_closing_does_not_show_a_message_step(self):
        """验证码提交失败回来时对话框已关，就不该再跳到提示步。"""
        data = run_js(PRELUDE + r"""
cred({ saved: false });
window.pywebview = { api: { relogin_submit: () => Promise.resolve({ ok: false, error: "bad_code", text: "验证码不对" }) } };
S.relogin = { open: true, step: "cap", flowId: "f1", challengeId: "c1" };
$("#rl-code").value = "ab12";
S.relogin.open = false;
await submitReloginCode();
await __flush();
out.push({ step: stepOf() });
""")[0]
        # 提交这一支进来就先写了「正在核对验证码…」，所以看它有没有被推到提示步
        self.assertEqual(data["step"], "wait", "关着时不该跳到提示步")


if __name__ == "__main__":
    unittest.main()
