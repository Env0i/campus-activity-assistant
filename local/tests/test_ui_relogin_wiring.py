#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新登录对话框的接线测试：wireRelogin 里的每一处事件绑定，加上顶栏「登录」那一个入口。

每一处绑定一条用例：在整页沙箱（真实页面脚本清单）里触发控件的事件，先断言用户看得到
的结果（对话框开没开、落到哪一步、按钮可不可点、密码框是不是明文）或发出的桥接请求
（接口名与关键参数），再断言内部值；不读源码文字，搬文件也不会红。变异验证（把那一处
绑定的动作行换成空语句后红在它自己那句断言上）见 design/evidence 下这一批的 wiring.md。

另有三条真加载冒烟：登录结论为已失效时点「登录」能打开对话框、点「取消」能关上、430 宽
窄窗口下普通脚本阶段不抛错且「登录」按钮照样能打开对话框。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js, run_native_smoke  # noqa: E402

# 公共桩：桥接替身把每次请求记成 [接口名, ...参数]；__flush 推进微任务；
# __fire 按选择器触发某个类型的事件（按键事件带上 key）。
PRELUDE = r"""
window.__calls = [];
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.terms.declined = false;
S.terms.unknown = false;
S.online = true;
S.demo = false;
S.busy = false;
S.autoLogin = false;
S.login = { ok: false, present: true, checking: false, loginPending: false, result: "expired",
            handoff: false, expireAt: null, estimateReason: null, hours: null,
            lastCheckAt: "", lastCheckState: "unknown", view: {} };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const __flush = async (n = 12) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
const __fire = (sel, type, extra) => {
  const el = $("#" + sel);
  (el.listeners[type] || []).forEach((fn) => fn(Object.assign({ target: el, preventDefault() {} }, extra || {})));
};
const __names = () => window.__calls.map((call) => call[0]);
const __open = (step, extra) => {
  S.advanced = { credential: { saved: false, paused: false } };
  if (window.PhonePanel && window.PhonePanel.state) {
    window.PhonePanel.state.advanced = { credential: { saved: false, paused: false } };
  }
  S.relogin = Object.assign({ open: true, step: "", flowId: "f1", challengeId: "ch1",
                              way: "here", fromLogin: false }, extra || {});
  const dlg = $("#dlg-relogin");
  if (dlg.showModal) dlg.showModal();
  reloginStep(step);
};
"""


class LoginEntryTests(unittest.TestCase):
    """顶栏「登录」这一个入口（app.js 里绑的那一行）。"""

    def test_expired_login_button_opens_the_relogin_dialog(self):
        """登录已失效时点顶栏「登录」：打开重新登录对话框，从登录表单开始。"""
        data = run_js(PRELUDE + r"""
$("#btn-login").click();
out.push({ open: $("#dlg-relogin").open, step: S.relogin ? S.relogin.step : null,
           title: $("#dlg-relogin-title").textContent });
""")[0]
        self.assertTrue(data["open"], "点「登录」要把重新登录对话框打开")
        self.assertEqual(data["step"], "login", "没有保存账号时从登录表单开始")
        self.assertEqual(data["title"], "登录学校账号")

    def test_first_login_button_opens_the_login_form(self):
        """从没登录过时点顶栏「登录」：同样打开对话框，仍从登录表单开始。"""
        data = run_js(PRELUDE + r"""
S.login.result = "none";
S.login.present = false;
$("#btn-login").click();
out.push({ open: $("#dlg-relogin").open, step: S.relogin ? S.relogin.step : null });
""")[0]
        self.assertTrue(data["open"])
        self.assertEqual(data["step"], "login")


class ConfirmStepWireTests(unittest.TestCase):
    """确认步与「自动登录一次」。"""

    def test_auto_login_button_asks_the_backend_once(self):
        """确认步点「自动登录」：发出一次自动登录请求，画面进入等待。"""
        data = run_js(PRELUDE + r"""
__open("confirm");
$("#btn-rl-auto").click();
await __flush();
out.push({ names: __names(), step: S.relogin.step, wait: $("#rl-wait-text").textContent });
""")[0]
        self.assertEqual(data["names"][:1], ["relogin_auto_once"], "要发出自动登录请求")
        self.assertEqual(data["step"], "wait", "发出请求后停在等待那一屏")
        self.assertIn("自动登录", data["wait"])


class LoginFormWireTests(unittest.TestCase):
    """登录表单这一屏：下一步、方式切换、密码明文、按键与勾选。"""

    def test_next_button_starts_relogin_with_the_typed_account(self):
        """填好账号密码点「下一步」：把账号密码交给后端开始登录。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-user").value = "20230001";
$("#rl-pass").value = "pw-1";
$("#btn-lg-next").click();
await __flush();
out.push({ call: window.__calls.find((c) => c[0] === "relogin_begin"), step: S.relogin.step });
""")[0]
        self.assertEqual(data["call"], ["relogin_begin", "20230001", "pw-1", False],
                         "要带着填进去的账号密码请求开始登录（没勾保存传 false）")
        self.assertEqual(data["step"], "wait")

    def test_way_card_here_shows_the_form_again(self):
        """从「用学校登录页」切回「在这里输入」：表单重新出现。"""
        data = run_js(PRELUDE + r"""
__open("login", { way: "browser" });
$("#lg-here").click();
out.push({ way: S.relogin.way, form: $("#lg-form").hidden, trade: $("#lg-trade").hidden });
""")[0]
        self.assertEqual(data["way"], "here")
        self.assertFalse(data["form"], "切回「在这里输入」要露出表单")
        self.assertTrue(data["trade"], "「在这里输入」时收起去浏览器登录的说明")

    def test_way_card_browser_hides_the_form(self):
        """切到「用学校登录页」：表单收起，换成去浏览器登录的说明。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#lg-web").click();
out.push({ way: S.relogin.way, form: $("#lg-form").hidden, trade: $("#lg-trade").hidden });
""")[0]
        self.assertEqual(data["way"], "browser")
        self.assertTrue(data["form"], "切到浏览器登录时表单要收起")
        self.assertFalse(data["trade"])

    def test_eye_button_shows_the_password_as_plain_text(self):
        """点密码框旁的眼睛：密码变明文（再点回圆点）。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-pass").type = "password";
$("#lg-eye").click();
out.push({ first: $("#rl-pass").type, label: $("#lg-eye").getAttribute("aria-label") });
""")[0]
        self.assertEqual(data["first"], "text", "点眼睛要把密码显示成明文")
        self.assertEqual(data["label"], "隐藏密码")

    def test_typing_the_account_enables_next(self):
        """只填账号还不够、「下一步」本来不能点：账号一输入，按钮跟着变可点。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-pass").value = "pw-1";
$("#btn-lg-next").disabled = true;
$("#rl-user").value = "20230001";
__fire("rl-user", "input");
out.push({ disabled: $("#btn-lg-next").disabled });
""")[0]
        self.assertFalse(data["disabled"], "账号输入后「下一步」要变可点")

    def test_typing_the_password_enables_next(self):
        """账号已填、密码一输入，「下一步」变可点。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-user").value = "20230001";
$("#btn-lg-next").disabled = true;
$("#rl-pass").value = "pw-1";
__fire("rl-pass", "input");
out.push({ disabled: $("#btn-lg-next").disabled });
""")[0]
        self.assertFalse(data["disabled"], "密码输入后「下一步」要变可点")

    def test_enter_in_the_password_field_submits_the_form(self):
        """在密码框里按回车：等同点「下一步」，直接开始登录。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-user").value = "20230001";
$("#rl-pass").value = "pw-1";
__fire("rl-pass", "keydown", { key: "Enter" });
await __flush();
out.push({ call: window.__calls.find((c) => c[0] === "relogin_begin"), step: S.relogin.step });
""")[0]
        self.assertIsNotNone(data["call"], "密码框回车要开始登录")
        self.assertEqual(data["call"][1], "20230001")
        self.assertEqual(data["step"], "wait")

    def test_ticking_save_rewrites_the_explanation(self):
        """勾上「保存到这台电脑」：第 2 条说明当场换成「勾了保存」。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#rl-save").checked = true;
__fire("rl-save", "change");
out.push({ fact: $("#lg-fact-save").textContent });
""")[0]
        self.assertIn("勾了保存", data["fact"], "勾选后要说明密码会被加密保存")

    def test_school_page_button_waits_for_the_browser(self):
        """点「打开学校登录页」：对话框停在等待那一屏，同时发起浏览器登录。"""
        data = run_js(PRELUDE + r"""
__open("login");
$("#btn-lg-webopen").click();
await __flush();
out.push({ step: S.relogin.step, names: __names() });
""")[0]
        self.assertEqual(data["step"], "lgwait", "用浏览器登录时停在「在学校登录页登录」")
        self.assertIn("login", data["names"], "同时要发起浏览器登录")

    def test_back_button_returns_from_the_captcha_step(self):
        """从登录表单点进验证码步后点「上一步」：回到登录表单。"""
        data = run_js(PRELUDE + r"""
__open("cap", { fromLogin: true });
$("#btn-lg-back").click();
out.push({ step: S.relogin.step, fromLogin: S.relogin.fromLogin,
           title: $("#dlg-relogin-title").textContent });
""")[0]
        self.assertEqual(data["step"], "login")
        self.assertFalse(data["fromLogin"])
        self.assertEqual(data["title"], "登录学校账号")


class CaptchaStepWireTests(unittest.TestCase):
    """验证码这一屏：登录、回车、满四位才亮。"""

    def test_code_button_submits_the_typed_code(self):
        """填满四位验证码点「登录」：带着这一场的号和验证码提交。"""
        data = run_js(PRELUDE + r"""
__open("cap");
$("#rl-code").value = "AB12";
$("#btn-rl-code").click();
await __flush();
out.push({ call: window.__calls.find((c) => c[0] === "relogin_submit"), step: S.relogin.step });
""")[0]
        self.assertEqual(data["call"], ["relogin_submit", "f1", "ch1", "AB12"],
                         "要带这一场的 flow_id、challenge_id 和输入的验证码")
        self.assertEqual(data["step"], "wait")

    def test_four_digit_code_enables_the_login_button(self):
        """验证码满四位，「登录」按钮才从禁用变可点。"""
        data = run_js(PRELUDE + r"""
__open("cap");
$("#rl-code").value = "AB12";
$("#btn-rl-code").disabled = true;
__fire("rl-code", "input");
out.push({ disabled: $("#btn-rl-code").disabled });
""")[0]
        self.assertFalse(data["disabled"], "四位验证码要能点「登录」")

    def test_enter_in_the_code_field_submits_it(self):
        """在验证码框里按回车：等同点「登录」。"""
        data = run_js(PRELUDE + r"""
__open("cap");
$("#rl-code").value = "AB12";
__fire("rl-code", "keydown", { key: "Enter" });
await __flush();
out.push({ call: window.__calls.find((c) => c[0] === "relogin_submit") });
""")[0]
        self.assertEqual(data["call"][3], "AB12", "回车要把验证码提交出去")


class CloseWireTests(unittest.TestCase):
    """取消、知道了、Esc：三种关上对话框的方式各自的后果。"""

    def test_cancel_closes_the_dialog_and_cancels_the_flow(self):
        """验证码步点「取消」：对话框关上，同时把这一场登录取消掉。"""
        data = run_js(PRELUDE + r"""
__open("cap");
$("#btn-rl-cancel").click();
await __flush();
out.push({ open: $("#dlg-relogin").open, call: window.__calls.find((c) => c[0] === "relogin_cancel") });
""")[0]
        self.assertFalse(data["open"], "点「取消」要把对话框关上")
        self.assertEqual(data["call"], ["relogin_cancel", "f1"], "要取消这一场登录")

    def test_done_closes_the_dialog_without_touching_the_backend(self):
        """结果步点「知道了」：只关对话框，不再发任何请求。"""
        data = run_js(PRELUDE + r"""
__open("msg");
$("#btn-rl-done").click();
await __flush();
out.push({ open: $("#dlg-relogin").open, names: __names() });
""")[0]
        self.assertFalse(data["open"])
        self.assertEqual([n for n in data["names"] if n.startswith("relogin")], [],
                         "已经结束的这一场不该再发重新登录类的请求")

    def test_escape_on_the_dialog_closes_it(self):
        """在对话框上按 Esc（浏览器的 cancel 事件）：对话框关上。"""
        data = run_js(PRELUDE + r"""
__open("cap");
__fire("dlg-relogin", "cancel");
await __flush();
out.push({ open: $("#dlg-relogin").open });
""")[0]
        self.assertFalse(data["open"], "Esc 要能把对话框关上")

    def test_browser_button_closes_then_opens_the_school_page(self):
        """验证码步点「改用浏览器登录」：先关上这一场，再打开学校登录页。"""
        data = run_js(PRELUDE + r"""
__open("cap");
$("#btn-rl-browser").click();
await __flush();
out.push({ open: $("#dlg-relogin").open, names: __names() });
""")[0]
        self.assertFalse(data["open"], "改用浏览器登录要先关掉对话框")
        self.assertIn("relogin_cancel", data["names"])
        self.assertIn("login", data["names"], "关掉之后要发起浏览器登录")

    def test_bad_password_browser_button_also_opens_the_school_page(self):
        """保存的密码不对时点「在浏览器里登录」：同样关掉对话框并发起浏览器登录。"""
        data = run_js(PRELUDE + r"""
__open("bad");
$("#btn-bad-browser").click();
await __flush();
out.push({ open: $("#dlg-relogin").open, names: __names() });
""")[0]
        self.assertFalse(data["open"])
        self.assertIn("login", data["names"])

    def test_update_password_button_returns_to_the_form(self):
        """保存的密码不对时点「更新账号密码」：回到登录表单。"""
        data = run_js(PRELUDE + r"""
__open("bad");
$("#btn-bad-update").click();
out.push({ step: S.relogin.step, title: $("#dlg-relogin-title").textContent });
""")[0]
        self.assertEqual(data["step"], "login")
        self.assertEqual(data["title"], "登录学校账号")


NATIVE_AFTER = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.terms.declined = false;
S.terms.unknown = false;
S.demo = false;
S.busy = false;
S.login = { ok: false, present: true, checking: false, loginPending: false, result: "expired",
            handoff: false, expireAt: null, estimateReason: null, hours: null,
            lastCheckAt: "", lastCheckState: "unknown", view: {} };
$("#btn-login").click();
const opened = { open: $("#dlg-relogin").open, step: S.relogin ? S.relogin.step : null,
                 title: $("#dlg-relogin-title").textContent };
$("#btn-rl-cancel").click();
out.push({ opened: opened, closed: !$("#dlg-relogin").open });
"""


class NativeLoadWireTests(unittest.TestCase):
    """真加载：模块与普通脚本按真实次序加载，名字挂回之后这几处接线仍可用。"""

    def test_native_login_button_opens_and_cancel_closes_the_dialog(self):
        """真加载后点「登录」能打开重新登录对话框，点「取消」能关上。"""
        result = run_native_smoke([], after=NATIVE_AFTER)
        data = result["after"][0]
        self.assertTrue(result["modulesReady"], "模块入口要跑完")
        self.assertTrue(data["opened"]["open"], "真加载下点「登录」要打开对话框")
        self.assertEqual(data["opened"]["title"], "登录学校账号")
        self.assertTrue(data["closed"], "真加载下点「取消」要关上对话框")

    def test_native_narrow_window_keeps_the_login_button_working(self):
        """430 宽窄窗口真加载：普通脚本阶段不抛错，登录按钮照样能打开对话框。"""
        result = run_native_smoke([], after=NATIVE_AFTER, size=(430, 820))
        data = result["after"][0]
        self.assertTrue(result["modulesReady"], "窄窗口下模块入口也要跑完")
        self.assertTrue(data["opened"]["open"], "窄窗口下点「登录」仍要打开对话框")
        self.assertTrue(data["closed"])


if __name__ == "__main__":
    unittest.main()
