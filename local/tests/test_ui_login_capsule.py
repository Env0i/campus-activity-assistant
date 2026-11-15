#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录胶囊的用户可见结论（行为测试）。

在 node 沙箱里按 index.html 的加载序跑真实界面脚本，摆好登录状态后调 paintLogin，
只看用户看得到的东西：胶囊文字、色调、副句、登录按钮文案与实心/描边。
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

# 条款已同意、在线、非演示；业务现在 = 北京时间 2026-11-06 14:00
PRELUDE = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const resetLogin = () => {
  S.busy = false; S.demo = false; S.autoLogin = false; S.stopping = false;
  S.login = {
    ok: null, present: null, checking: false, loginPending: false, result: "none",
    handoff: false, expireAt: null, estimateReason: null, hours: null,
    lastCheckAt: "", lastCheckState: "unknown", view: {},
  };
};
const read = () => $("#pill-text").textContent;
const readState = () => $("#pill").dataset.state;
const readSub = () => $("#pill-sub").textContent;
const readBtn = () => $("#btn-login-text").textContent;
const readSolid = () => $("#btn-login").classList.contains("btn-solid");
"""


class LoginCapsuleConclusionTests(unittest.TestCase):
    """胶囊按登录结论挑文字与色调。"""

    def test_keeps_saying_logged_in_while_a_plan_runs(self):
        """计划跑着的时候胶囊继续说「已登录」，不拿「正在处理」盖掉登录结论。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.busy = true;
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
paintLogin();
out.push({ text: read(), state: readState(), btn: readBtn() });
""")[0]
        self.assertEqual(data["text"], "已登录", "忙碌时胶囊仍要报登录结论")
        self.assertEqual(data["state"], "ok")
        self.assertEqual(data["btn"], "重新登录", "已登录时按钮叫重新登录")

    def test_still_reports_expiry_while_a_plan_runs(self):
        """计划跑着、学校明确说失效时，胶囊必须报「登录已失效」，不能被忙碌盖成已登录。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.busy = true;
S.login.present = true; S.login.result = "expired"; S.login.ok = false;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "登录已失效", "忙碌时也要把失效说出来")
        self.assertEqual(data["state"], "bad")

    def test_busy_plan_does_not_hide_a_login_in_progress(self):
        """计划跑着但登录窗口还在等用户完成时，胶囊说「登录中…」，不说「已登录」。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.busy = true;
S.login.present = true; S.login.loginPending = true; S.login.ok = false;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "登录中…", "还没登完不能报已登录")
        self.assertEqual(data["state"], "pending")

    def test_busy_plan_says_auto_login(self):
        """电脑正在用保存的账号自动登录时，胶囊说「自动登录中…」，不被忙碌盖成已登录。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.busy = true; S.autoLogin = true;
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "自动登录中…")
        self.assertEqual(data["state"], "pending")

    def test_demo_says_demo_mode(self):
        """演示模式自己说出来，不借「已登录」的外观掩盖没有真实会话。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.demo = true;
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
paintLogin();
out.push({ text: read(), state: readState(), sub: readSub() });
""")[0]
        self.assertEqual(data["text"], "演示模式")
        self.assertEqual(data["state"], "demo")
        self.assertEqual(data["sub"], "内存样例")

    def test_first_use_asks_to_log_in(self):
        """从没登录过时胶囊说「未登录」，按钮叫「登录」并转实心。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = false; S.login.result = "none"; S.login.ok = null;
paintLogin();
out.push({ text: read(), state: readState(), btn: readBtn(), solid: readSolid(),
           note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["text"], "未登录", "首次使用不能报失效")
        self.assertEqual(data["state"], "none")
        self.assertEqual(data["btn"], "登录", "首次使用叫登录，不叫重新登录")
        self.assertTrue(data["solid"], "未登录时按钮转实心")
        self.assertEqual(data["note"],
                         "打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录")

    def test_unconfirmed_check_does_not_say_expired(self):
        """学校没应答时胶囊说「登录待确认」，按钮仍是「登录」，不误报失效。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "unknown"; S.login.ok = false;
paintLogin();
out.push({ text: read(), state: readState(), btn: readBtn(), solid: readSolid() });
""")[0]
        self.assertEqual(data["text"], "登录待确认")
        self.assertEqual(data["state"], "unknown")
        self.assertEqual(data["btn"], "登录", "待确认时还叫登录")
        self.assertFalse(data["solid"], "待确认时按钮保持描边")

    def test_expired_says_relogin(self):
        """登录过又确认失效时胶囊说「登录已失效」，按钮叫「重新登录」并转实心。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "expired"; S.login.ok = false;
paintLogin();
out.push({ text: read(), state: readState(), btn: readBtn(), solid: readSolid() });
""")[0]
        self.assertEqual(data["text"], "登录已失效")
        self.assertEqual(data["state"], "bad")
        self.assertEqual(data["btn"], "重新登录")
        self.assertTrue(data["solid"], "失效时按钮转实心")

    def test_checking_without_a_saved_session_says_checking(self):
        """本机没有会话、但正在真实校验时，胶囊也要说「检查登录…」而不是「未登录」。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = false; S.login.result = "none"; S.login.ok = null; S.login.checking = true;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "检查登录…", "校验中不能被首次使用盖过去")
        self.assertEqual(data["state"], "checking")

    def test_waiting_terms_says_so(self):
        """没同意使用条款时胶囊说「等同意条款」，即使上次结论是已登录。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.terms.acceptedVersion = "";
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "等同意条款")
        self.assertEqual(data["state"], "terms")

    def test_start_button_waits_for_a_confirmed_login(self):
        """开始按钮只在学校确认登录有效时能点，检查中也不放行。"""
        data = run_js(PRELUDE + r"""
resetLogin();
const item = { id: "a1", name: "活动", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, seconds_to_open: 1,
  state: "未开放", place: "", checkin_required: null, checkout_required: null };
S.items = [item];
S.byId = new Map([["a1", item]]);
S.listState = "ready";
S.selected = new Set(["a1"]);
const gate = () => { paintLogin(); updateControls(); return $("#btn-plan").disabled; };
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
const ready = gate();
S.login.result = "expired"; S.login.ok = false;
const expired = gate();
S.login.result = "valid"; S.login.checking = true;
const checking = gate();
out.push({ ready, expired, checking });
""")[0]
        self.assertFalse(data["ready"], "学校确认有效时开始按钮要能点")
        self.assertTrue(data["expired"], "登录失效时不能开始")
        self.assertTrue(data["checking"], "还没确认的检查期也不能开始")


class LoginCapsuleEstimateTests(unittest.TestCase):
    """已登录时详情里补一句「预计约到…」，只是提示。"""

    def test_same_day_estimate_writes_the_clock_time(self):
        """学校确认有效、估算落在当天时，详情里写「预计约到 16:00，以学校为准」。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.expireAt = Date.UTC(2026, 10, 6, 8, 0, 0);
paintLogin();
out.push({ note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["note"], "学校确认登录有效；预计约到 16:00，以学校为准")

    def test_next_day_estimate_says_tomorrow(self):
        """估算落在明天时写「预计约到明天 10:00」，不写具体日期。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.expireAt = Date.UTC(2026, 10, 7, 2, 0, 0);
paintLogin();
out.push({ note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["note"], "学校确认登录有效；预计约到明天 10:00，以学校为准")

    def test_no_estimate_when_school_did_not_give_one(self):
        """没有估算锚点时详情只说学校确认的事实，不编时间。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
paintLogin();
out.push({ note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["note"], "学校确认登录有效")


class LoginCapsuleEdgeTests(unittest.TestCase):
    """结果条自动收起、自动登录态收回、详情卡检查按钮这些边角行为。"""

    def test_auto_close_result_stays_while_a_plan_runs(self):
        """计划跑着时结果条不自动收起，免得把成功结论从用户眼前抢走。"""
        data = run_js(PRELUDE + r"""
resetLogin();
let cb = null;
window.setTimeout = (fn) => { cb = fn; return 1; };
S.busy = true;
setResult({ ok: true, title: "报好了", text: "已提交", autoClose: Date.now() + 5000 });
cb();
out.push({ hidden: $("#result").hidden, text: $("#result").textContent });
""")[0]
        self.assertFalse(data["hidden"], "忙碌时结果条要留着")
        self.assertIn("报好了", data["text"])

    def test_handoff_retracts_the_auto_login_state(self):
        """学校说已转人工后，「自动登录中…」必须收回，否则用户一直以为电脑还在登。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.autoLogin = true;
S.login.handoff = true; S.login.result = "expired";
reconcileAutoLogin();
paintLogin();
out.push({ auto: S.autoLogin, text: read() });
""")[0]
        self.assertFalse(data["auto"], "转人工以后自动登录态要收回")
        self.assertNotEqual(data["text"], "自动登录中…")

    def test_login_card_check_button_disabled_while_busy(self):
        """计划跑着时登录详情卡的「检查」按钮不可点，不和计划抢网络。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.busy = true;
renderLoginCard();
out.push({ disabled: $("#btn-login-check").disabled });
""")[0]
        self.assertTrue(data["disabled"], "忙碌时检查按钮要禁用")

    def test_login_card_check_button_disabled_while_checking(self):
        """正在检查登录时详情卡的「检查」按钮不可点，避免重复发请求。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.checking = true;
renderLoginCard();
out.push({ disabled: $("#btn-login-check").disabled });
""")[0]
        self.assertTrue(data["disabled"], "检查中检查按钮要禁用")


    def test_handoff_from_the_backend_does_not_light_auto_login(self):
        """已转人工时后端就算还说 recovering，胶囊也不能报「自动登录中…」。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true;
S.login.result = "expired"; S.login.ok = false;
S.login.handoff = true;
setLogin(6, false, true, { recovering: true });
paintLogin();
out.push({ auto: S.autoLogin, text: read() });
""")[0]
        self.assertNotEqual(data["text"], "自动登录中…", "转人工后不该再报自动登录")
        self.assertFalse(data["auto"], "转人工时 autoLogin 不该被置位")


    def test_anchor_with_a_future_time_says_roughly_when(self):
        """有锚点时胶囊副句写明「预计约到 …」，长句同样带日期，不写成未知。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.expireAt = Date.UTC(2026, 10, 6, 16, 0, 0);
paintLogin();
renderLoginCard();
out.push({ note: $("#status-detail").textContent, long: expiryText() });
""")[0]
        self.assertIn("预计约到", data["note"], "有锚点时胶囊要说清预计到什么时候")
        self.assertTrue(data["long"].startswith("约到 "), "长句要带具体日期")
        self.assertNotIn("未知", data["long"])

    def test_a_pending_login_window_blocks_the_auto_refresh(self):
        """登录窗口开着时不自动刷新列表，别和它抢网络；关掉后恢复。"""
        data = run_js(PRELUDE + r"""
resetLogin();
S.online = true;
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
window.pywebview = { api: { refresh: () => Promise.resolve({}) } };
$("#btn-refresh").disabled = false;
S.listState = "idle"; S.starting = false;
S.listAtMono = _monoMs() - 11 * 60 * 1000;
S.login.loginPending = true;
const blocked = autoRefreshDue();
S.login.loginPending = false;
const allowed = autoRefreshDue();
out.push({ blocked, allowed });
""")[0]
        self.assertFalse(data["blocked"], "登录窗口开着时不该自动刷新")
        self.assertTrue(data["allowed"], "窗口关掉后自动刷新照旧")


if __name__ == "__main__":
    unittest.main()
