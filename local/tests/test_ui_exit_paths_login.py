#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 1 出口行为测试·登录一组（计划 20261113-refactor-step1-exit-tests）。

每个 test_ 守 D2 变异表里的一个出口（编号见用例名）：在 node 沙箱里按
index.html 的加载序跑真实界面脚本、触发动作、看用户看得到的结果（胶囊文字、
结果框、运行记录），再断言状态值；不对源码文本做断言。
变异验证（未变异通过 / 对应变异变红）见 design/evidence/2026-11-13/exit-path-tests/。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 定时器桩：记下所有 setTimeout，用 __fire(ms) 精确触发超时出口；__flush 推进微任务
TIMERS = r"""
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

# 业务现在 = 北京时间 2026-11-06 14:00；条款已同意、在线、非演示；运行记录逐行记账
PRELUDE = TIMERS + r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = false;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const appended = [];
const logBox = $("#log");
const origAppend = logBox.appendChild;
logBox.appendChild = (child) => {
  appended.push(String(child.textContent).replace(/^\d\d:\d\d:\d\d\s+/, ""));
  return origAppend(child);
};
const pill = () => $("#pill-text").textContent;
"""


class LoginCheckingExitTests(unittest.TestCase):
    """登录·校验中（S.login.checking）的四条前台出口与接续超时出口。"""

    def test_L01_check_timeout_after_100s_leaves_checking(self):
        """登录·校验中：前台轮 100 秒没等到校验回包——胶囊离开「检查登录…」落「登录待确认」，
        运行记录说明按暂时无法确认处理、可点刷新重试。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: { check: () => new Promise(() => {}),
                            list_activities: () => new Promise(() => {}) } };
S.login.present = true;
refresh(false);
await __flush();
const during = { checking: S.login.checking, pill: pill() };
__fire(100000);
await __flush();
out.push({ during, after: { checking: S.login.checking, pill: pill(),
                            lines: appended.slice() } });
""")
        data = res[0]
        self.assertTrue(data["during"]["checking"], "前提：刷新后应处在检查中")
        self.assertEqual(data["during"]["pill"], "检查登录…")
        self.assertFalse(data["after"]["checking"], "超时后不能停在检查中")
        self.assertEqual(data["after"]["pill"], "登录待确认", "结论按暂时无法确认画")
        self.assertTrue(any("检查登录状态超过 100 秒没有回应" in line for line in data["after"]["lines"]),
                        data["after"]["lines"])

    def test_L03_checking_ends_when_the_adopted_old_round_times_out(self):
        """登录·校验中：接续旧请求（skipped）后 100 秒仍没结论——胶囊同样要离开「检查登录…」。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => Promise.resolve({ skipped: true, request_id: "check-old-1" }),
  list_activities: () => new Promise(() => {}),
} };
S.login.present = true;
refresh(false);
await __flush();
const adopted = S.round.check;
__fire(100000);
await __flush();
out.push({ adopted, after: { checking: S.login.checking, pill: pill() } });
""")
        data = res[0]
        self.assertEqual(data["adopted"], "check-old-1", "前提：请求号已接续回旧 owner")
        self.assertFalse(data["after"]["checking"], "接续后的超时也要离开检查中")
        self.assertEqual(data["after"]["pill"], "登录待确认")

    def test_L04_check_rejected_by_terms_leaves_checking_and_reopens_terms(self):
        """登录·校验中：后端条款回绝——胶囊离开「检查登录…」，条款门禁重新弹到用户面前。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: false, error: "terms_required", text: "请先同意使用条款" }),
  list_activities: () => new Promise(() => {}),
} };
S.login.present = true;
refresh(false);
await __flush();
out.push({ checking: S.login.checking, pill: pill(),
           termsOpen: $("#dlg-terms").open === true });
""")
        data = res[0]
        self.assertFalse(data["checking"], "条款回绝也是一条出口，不能停在检查中")
        self.assertEqual(data["pill"], "登录待确认")
        self.assertTrue(data["termsOpen"], "条款回绝要把条款面弹出来")

    def test_L05_check_could_not_start_leaves_checking_with_the_reason(self):
        """登录·校验中：后端说这次检查没能开始——胶囊离开「检查登录…」，运行记录带后端原话。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: false, text: "正在关闭，稍后再试" }),
  list_activities: () => new Promise(() => {}),
} };
S.login.present = true;
refresh(false);
await __flush();
out.push({ checking: S.login.checking, pill: pill(), lines: appended.slice() });
""")
        data = res[0]
        self.assertFalse(data["checking"])
        self.assertEqual(data["pill"], "登录待确认")
        self.assertTrue(any("正在关闭，稍后再试" in line for line in data["lines"]), data["lines"])


class LoginPendingExitTests(unittest.TestCase):
    """登录·浏览器登录窗口开着（S.login.loginPending）的三条同步出口。"""

    def setUpPreLogin(self):
        """尝试前的状态：登录过但已失效，才看得出「回滚到尝试前」。"""
        return r"""
S.login.present = true;
S.login.result = "expired";
S.login.ok = false;
"""

    def test_L07_demo_login_releases_the_pending_pill(self):
        """登录·浏览器登录窗口开着：演示模式不打开学校登录页——胶囊离开「登录中…」，
        结果框如实说明，忙态解除。"""
        res = run_js(PRELUDE + self.setUpPreLogin() + r"""
window.pywebview = { api: { login: () => Promise.resolve({ demo: true, text: "演示模式不联网。" }) } };
doLogin();
const during = { pending: S.login.loginPending, pill: pill() };
await __flush();
out.push({ during, after: { pending: S.login.loginPending, busy: S.busy, pill: pill(),
                            result: $("#result").innerHTML } });
""")
        data = res[0]
        self.assertTrue(data["during"]["pending"], "前提：尝试期间窗口算开着")
        self.assertEqual(data["during"]["pill"], "登录中…")
        self.assertFalse(data["after"]["pending"], "演示模式不当成登录失败挂住")
        self.assertFalse(data["after"]["busy"])
        self.assertNotEqual(data["after"]["pill"], "登录中…", "胶囊不能停在登录中")
        self.assertIn("演示模式不登录", data["after"]["result"])

    def test_L08_failed_start_releases_the_pending_pill_and_rolls_back(self):
        """登录·浏览器登录窗口开着：后端拒绝开始——胶囊离开「登录中…」，结论整份回滚到尝试前，
        结果框说明登录没能开始。"""
        res = run_js(PRELUDE + self.setUpPreLogin() + r"""
window.pywebview = { api: { login: () => Promise.resolve({ ok: false, text: "已经有一个任务在跑" }) } };
doLogin();
await __flush();
out.push({ pending: S.login.loginPending, busy: S.busy, pill: pill(),
           resultState: S.login.result, ok: S.login.ok,
           result: $("#result").innerHTML });
""")
        data = res[0]
        self.assertFalse(data["pending"], "没能开始也要放开胶囊")
        self.assertFalse(data["busy"])
        self.assertEqual(data["pill"], "登录已失效", "回滚到尝试前的结论，不把旧凭证画没")
        self.assertEqual(data["resultState"], "expired")
        self.assertIn("登录没能开始", data["result"])
        self.assertIn("已经有一个任务在跑", data["result"])

    def test_L09_bridge_error_releases_the_pending_pill(self):
        """登录·浏览器登录窗口开着：桥接异常——胶囊离开「登录中…」，旧结论保留，错误进结果框。"""
        res = run_js(PRELUDE + self.setUpPreLogin() + r"""
window.pywebview = { api: { login: () => Promise.reject(new Error("桥接断了")) } };
doLogin();
await __flush();
out.push({ pending: S.login.loginPending, busy: S.busy, pill: pill(),
           resultState: S.login.result, result: $("#result").innerHTML });
""")
        data = res[0]
        self.assertFalse(data["pending"])
        self.assertFalse(data["busy"])
        self.assertEqual(data["pill"], "登录已失效")
        self.assertIn("登录没能开始", data["result"])
        self.assertIn("桥接断了", data["result"])


class LoginHandoffExitTests(unittest.TestCase):
    """登录·已转人工（S.login.handoff）的两条出口：清掉之后自动登录才可能再亮。"""

    def test_L11_valid_check_clears_handoff_so_auto_login_can_return(self):
        """登录·已转人工：学校说登录有效——转人工结束；之后再失效且电脑能自己恢复时，
        胶囊要能回到「自动登录中…」而不是永远「登录已失效」。"""
        res = run_js(PRELUDE + r"""
S.login.handoff = true;
S.login.result = "expired";
S.login.present = true;
window.onBackend.check({ ok: true, result: "valid" });
const afterValid = { handoff: S.login.handoff, pill: pill() };
window.onBackend.check({ ok: false, result: "expired", auto_state: "running" });
await __flush();
out.push({ afterValid, again: { handoff: S.login.handoff, autoLogin: S.autoLogin,
                                pill: pill() } });
""")
        data = res[0]
        self.assertEqual(data["afterValid"]["pill"], "已登录")
        self.assertFalse(data["afterValid"]["handoff"], "学校确认有效就不再是等验证码")
        self.assertTrue(data["again"]["autoLogin"], "新一轮失效且能恢复：自动登录该亮回来")
        self.assertEqual(data["again"]["pill"], "自动登录中…")

    def test_L12_finished_relay_clears_handoff_so_auto_login_can_return(self):
        """登录·已转人工：中继说这一场结束了（live=false）——不再等用户输码；
        之后再失效且电脑能自己恢复时，胶囊要回到「自动登录中…」。"""
        res = run_js(PRELUDE + r"""
S.login.handoff = true;
S.login.result = "expired";
S.login.present = true;
window.onBackend.phone_relogin({ state: "idle", live: false, origin: "auto", flow_id: "f1" });
const afterRelay = { handoff: S.login.handoff };
window.onBackend.check({ ok: false, result: "expired", auto_state: "running" });
await __flush();
out.push({ afterRelay, again: { handoff: S.login.handoff, autoLogin: S.autoLogin,
                                pill: pill() } });
""")
        data = res[0]
        self.assertFalse(data["afterRelay"]["handoff"], "这一场走完就不再等验证码")
        self.assertTrue(data["again"]["autoLogin"])
        self.assertEqual(data["again"]["pill"], "自动登录中…")


if __name__ == "__main__":
    unittest.main()
