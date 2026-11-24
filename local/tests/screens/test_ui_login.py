#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_ui_login.py（来源：test_login_looks.py, test_login_machine.py, test_login_transitions.py, test_ui_login_capsule.py, test_ui_relogin_dialog.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_login_looks.py ====================
"""登录胶囊、详情卡和横幅的样式契约测试。

@author Author
"""

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
ROOT = TESTS.parent.parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402


LOOKS_PRELUDE = r'''
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
S.busy = false; S.demo = false; S.stopping = false; S.autoLogin = false;
S.login = { ok: true, present: true, checking: false, loginPending: false,
  result: "valid", handoff: false, expireAt: null, estimateReason: null,
  hours: null, lastCheckAt: "", lastCheckState: "valid", view: {},
  auto: { state: "idle", block: "", retryInS: null, at: 0 } };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const resetLogin = () => {
  S.busy = false; S.demo = false; S.stopping = false; S.autoLogin = false;
  S.login = { ok: true, present: true, checking: false, loginPending: false,
    result: "valid", handoff: false, expireAt: null, estimateReason: null,
    hours: null, lastCheckAt: "", lastCheckState: "valid", view: {},
    auto: { state: "idle", block: "", retryInS: null, at: 0 } };
  S.terms.acceptedVersion = "v1";
};
'''


class LoginLooksTests(unittest.TestCase):
    def test_rechecking_capsule_and_card_use_the_confirmed_look(self):
        data = run_js(LOOKS_PRELUDE + r'''
resetLogin();
S.login.checking = true;
paintLogin();
renderLoginCard();
out.push({ capsule: { className: $("#pill").className,
  text: $("#pill-text").textContent, sub: $("#pill-sub").textContent },
  card: { tone: $("#login-pop-chip").dataset.tone,
    big: $("#login-pop-big").textContent } });
''')[0]
        self.assertEqual(data["capsule"], {
            "className": "pill is-ok is-spin",
            "text": "已登录",
            "sub": "正在确认",
        })
        self.assertEqual(data["card"], {"tone": "ok", "big": "登录有效"})

    def test_confirmed_result_removes_the_spin(self):
        data = run_js(LOOKS_PRELUDE + r'''
resetLogin();
S.login.checking = true;
paintLogin();
const checking = $("#pill").className;
S.login.checking = false; S.login.ok = true; S.login.result = "valid";
paintLogin();
out.push([checking, $("#pill").className]);
''')[0]
        self.assertEqual(data, ["pill is-ok is-spin", "pill is-ok"])

    def test_backend_running_spins_and_idle_clears_it(self):
        data = run_js(LOOKS_PRELUDE + r'''
resetLogin(); S.login.ok = false; S.login.result = "expired";
window.onBackend.login_auto({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
const running = $("#pill").className;
S.login.ok = true; S.login.result = "valid";
window.onBackend.login_auto({ auto_state: "idle", auto_block: "", auto_retry_in_s: null });
out.push([running, $("#pill").className]);
''')[0]
        self.assertEqual(data, ["pill is-busy is-spin", "pill is-ok"])

    def test_unconfirmed_capsule_is_amber(self):
        data = run_js(LOOKS_PRELUDE + r'''
resetLogin(); S.login.ok = false; S.login.result = "unknown";
paintLogin();
out.push({ className: $("#pill").className, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"className": "pill is-warn", "text": "登录待确认"})

    def test_code_handoff_card_overrides_both_auto_paths(self):
        data = run_js(LOOKS_PRELUDE + r'''
const rows = [];
for (const payload of [
  { auto_state: "handoff", auto_block: "", auto_retry_in_s: null },
  { auto_state: "blocked", auto_block: "ocr_missing", auto_retry_in_s: null },
]) {
  resetLogin(); S.login.ok = false; S.login.result = "expired";
  window.onBackend.login_auto(payload);
  renderLoginCard();
  rows.push({ tone: $("#login-pop-chip").dataset.tone,
    big: $("#login-pop-big").textContent });
}
out.push(rows);
''')[0]
        self.assertEqual(data, [{"tone": "warn", "big": "要你输验证码"},
                                {"tone": "warn", "big": "要你输验证码"}])

    def test_retry_later_card_keeps_bad_look(self):
        data = run_js(LOOKS_PRELUDE + r'''
resetLogin(); S.login.ok = false; S.login.result = "expired";
applyAutoState({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 60 });
paintLogin(); renderLoginCard();
out.push({ tone: $("#login-pop-chip").dataset.tone,
  big: $("#login-pop-big").textContent, capsule: $("#pill").className });
''')[0]
        self.assertEqual(data, {
            "tone": "bad", "big": "登录已失效", "capsule": "pill is-bad",
        })

    def test_code_banner_uses_the_plan_running_copy(self):
        data = run_js(LOOKS_PRELUDE + r'''
const view = { state: "bad", phase: "needs_code" };
out.push({ busy: loginBannerHtml(view, true), idle: loginBannerHtml(view, false) });
''')[0]
        self.assertIn("报名计划还在等，开放前 100 秒以前输完就照常继续。", data["busy"])
        self.assertIn("电脑需要你输入验证码才能继续登录。", data["idle"])
        self.assertIn('data-act="login"', data["busy"])
        self.assertIn("输入验证码", data["busy"])

    def test_spin_rule_and_pill_markup_are_text_contracts(self):
        styles = (ROOT / "local/ui/styles.css").read_text(encoding="utf-8")
        spin = re.search(r"\.pill\.is-spin i\s*\{([^}]*)\}", styles)
        self.assertIsNotNone(spin)
        self.assertIn("background: transparent", spin.group(1))
        self.assertIn("border: 2px solid currentColor", spin.group(1))
        self.assertIn("border-right-color: transparent", spin.group(1))
        self.assertIn("box-sizing: border-box", spin.group(1))
        self.assertIn("animation: advspin .9s linear infinite", spin.group(1))
        self.assertLess(styles.index(".pill.is-busy i"), styles.index(".pill.is-spin i"))
        html = (ROOT / "local/ui/index.html").read_text(encoding="utf-8")
        pill = re.search(r'<button class="pill" id="pill".*?</button>', html, re.S)
        self.assertIsNotNone(pill)
        self.assertEqual(pill.group(0).count("<i"), 1)


CARD_PRELUDE = r'''
S.terms.version = "v1"; S.terms.acceptedVersion = ""; S.terms.unknown = false;
S.busy = false; S.demo = false; S.stopping = false; S.autoLogin = false;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const setCardLogin = (present) => {
  S.login = { ok: true, present: present, checking: false, loginPending: false,
    result: "valid", handoff: false, expireAt: null, estimateReason: null,
    hours: null, lastCheckAt: "", lastCheckState: "valid", view: {},
    auto: { state: "idle", block: "", retryInS: null, at: 0 } };
};
const readCard = () => ({
  chip: $("#login-pop-chip-text").textContent,
  big: $("#login-pop-big").textContent,
  sub: $("#login-pop-sub").textContent,
  rows: $("#login-pop-rows").textContent,
  note: $("#login-pop-note").textContent,
  check: [$("#btn-login-check").hidden, $("#btn-login-check").disabled],
  login: [$("#btn-login").hidden, $("#btn-login").disabled],
  terms: $("#btn-login-terms").hidden,
});
'''


class LoginCardTermsHoldTests(unittest.TestCase):
    """条款未同意时登录详情卡的样子（原型 Main.dc.html 的 loginCard hold 一路）。

    条款门禁本身不动：两只学校动作按钮仍然禁用（决策 013，另有用例守着），
    这张卡只是把它们收起来，换成一句为什么停着和唯一能走的那一步。
    """

    def test_terms_hold_card_pauses_and_points_at_the_terms(self):
        data = run_js(CARD_PRELUDE + r"""
setCardLogin(true);
paintLogin(); renderLoginCard(); updateControls();
out.push(readCard());
""")[0]
        self.assertEqual(data["chip"], "等同意条款")
        self.assertEqual(data["big"], "暂停检查")
        self.assertEqual(data["sub"], "同意条款后才会检查登录状态")
        self.assertIn("已保存的登录", data["rows"], "登录过的人要知道登录没被删")
        self.assertIn("还在，不会删除", data["rows"])
        self.assertEqual(data["note"], "", "条款门下不报旧结论")
        self.assertEqual(data["check"], [True, True], "检查登录收起来，但仍然禁用")
        self.assertEqual(data["login"], [True, True], "登录同样收起来并保持禁用")
        self.assertFalse(data["terms"], "查看条款是这张卡唯一能点的动作")

    def test_terms_hold_card_hides_the_saved_login_line_for_first_time_users(self):
        data = run_js(CARD_PRELUDE + r"""
setCardLogin(false);
paintLogin(); renderLoginCard();
out.push(readCard());
""")[0]
        self.assertEqual(data["rows"], "",
                         "从没登录过的人看到「已保存的登录还在」就是假话")
        self.assertEqual(data["big"], "暂停检查")

    def test_unknown_terms_state_says_it_is_not_confirmed_yet(self):
        data = run_js(CARD_PRELUDE + r"""
S.terms.version = ""; S.terms.unknown = true;
setCardLogin(true);
paintLogin(); renderLoginCard();
out.push(readCard());
""")[0]
        self.assertEqual(data["chip"], "等确认条款",
                         "条款状态未知时不能写成「等同意条款」——那是另一件事")
        self.assertEqual(data["big"], "暂停检查")

    def test_accepted_terms_restore_the_normal_card(self):
        data = run_js(CARD_PRELUDE + r"""
S.terms.acceptedVersion = "v1";
setCardLogin(true);
paintLogin(); renderLoginCard(); updateControls();
out.push(readCard());
""")[0]
        self.assertEqual(data["big"], "登录有效")
        self.assertTrue(data["terms"], "出了条款门，「查看条款」要收起来")
        self.assertEqual(data["check"], [False, False], "检查登录回到可点")
        self.assertEqual(data["login"], [False, False], "登录按钮回到可见")
        self.assertIn("预计有效", data["rows"], "明细回到原来的两行")
        self.assertIn("别处登录", data["rows"])

# ==================== 源自 test_login_machine.py ====================
"""登录胶囊状态机与重新登录清单的结构测试。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
ROOT = TESTS.parent.parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))



class LoginMachineTests(unittest.TestCase):
    def test_phase_and_view_state_lists_are_frozen(self):
        data = run_js("""
out.push({ phases: LOGIN_PHASES, states: LOGIN_VIEW_STATES,
  frozen: [Object.isFrozen(LOGIN_PHASES), Object.isFrozen(LOGIN_VIEW_STATES)] });
""")[0]
        self.assertEqual(data["phases"], ["plan_running", "demo", "auto", "logging_in",
                                           "checking", "rechecking", "never", "unknown",
                                           "expired", "needs_code", "retry_later", "valid",
                                           "unset", "terms"])
        self.assertEqual(data["states"], ["ok", "none", "demo", "pending", "checking",
                                           "unknown", "bad", "terms"])
        self.assertEqual(data["frozen"], [True, True])

    def test_phase_order_keeps_all_precedence_rules(self):
        data = run_js("""
const base = { busy: false, demo: false, autoLogin: false, loginPending: false,
  checking: false, ok: false, present: true, result: "expired", termsLocked: false,
  stopping: false };
const ask = (extra) => loginPhase(Object.assign({}, base, extra));
out.push([
  ask({ busy: true, result: "expired" }),
  ask({ busy: true, result: "valid", ok: true }),
  ask({ demo: true, autoLogin: true }),
  ask({ autoLogin: true, loginPending: true }),
  ask({ loginPending: true, checking: true }),
  ask({ checking: true, ok: null, result: "none" }),
  ask({ present: false, result: "unknown" }),
  ask({ result: "unknown", ok: false, present: true }),
  ask({ ok: true, result: "valid", termsLocked: true }),
  ask({ demo: true, termsLocked: true }),
  ask({ autoLogin: true, termsLocked: true }),
  ask({ loginPending: true, termsLocked: true }),
  ask({ ok: true, result: "valid" })
]);
""")[0]
        self.assertEqual(data, ["expired", "plan_running", "demo", "auto", "logging_in",
                                "checking", "never", "unknown", "terms", "demo", "auto",
                                "logging_in", "valid"])

    def test_every_phase_maps_to_a_listed_view_state(self):
        data = run_js("""
const facts = [
  { busy: true, present: true, result: "valid" },
  { demo: true }, { autoLogin: true }, { loginPending: true }, { checking: true },
  { checking: true, ok: true, present: true, result: "valid" },
  { present: false }, { result: "unknown", ok: false, present: true },
  { result: "expired", ok: false, present: true }, { result: "valid", ok: true, present: true },
  { result: "expired", ok: false, present: true, auto: { state: "handoff" } },
  { result: "expired", ok: false, present: true, auto: { state: "backoff", retryLeftS: 5 } },
  { result: "none", ok: null, present: null }, { ok: true, result: "valid", termsLocked: true }
];
const phases = facts.map((item) => loginPhase(item));
out.push({ phases: phases, states: phases.map((phase) => loginViewState(phase, true)) });
""")[0]
        self.assertEqual(sorted(set(data["phases"])), sorted([
            "plan_running", "demo", "auto", "logging_in", "checking", "rechecking", "never", "unknown",
            "expired", "needs_code", "retry_later", "valid", "unset", "terms"
        ]))
        self.assertTrue(set(data["states"]).issubset({"ok", "none", "demo", "pending",
                                                        "checking", "unknown", "bad", "terms"}))
        self.assertEqual(dict(zip(data["phases"], data["states"])), {
            "plan_running": "ok", "demo": "demo", "auto": "pending",
            "logging_in": "pending", "checking": "checking", "never": "none",
            "rechecking": "checking", "unknown": "unknown", "expired": "bad", "needs_code": "bad",
            "retry_later": "bad", "valid": "ok", "terms": "terms",
            "unset": "none",
        })

    def test_relogin_steps_and_cases_are_frozen_lists(self):
        data = run_js("""
out.push({ steps: RELOGIN_STEPS, cases: RELOGIN_CASES,
  frozen: [Object.isFrozen(RELOGIN_STEPS), Object.isFrozen(RELOGIN_CASES)] });
""")[0]
        self.assertEqual(data["steps"], ["confirm", "login", "bad", "lgwait", "cap", "wait", "msg"])
        self.assertEqual(data["cases"], ["bad", "captcha", "login"])
        self.assertEqual(data["frozen"], [True, True])

    def test_each_phase_keeps_its_visible_appearance(self):
        data = run_js("""
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
const rows = [
  { busy: true, result: "valid", present: true, ok: true },
  { demo: true }, { autoLogin: true }, { loginPending: true }, { checking: true },
  { result: "none", present: false, ok: null },
  { result: "unknown", present: true, ok: false },
  { result: "expired", present: true, ok: false },
  { result: "valid", present: true, ok: true },
  { result: "none", present: null, ok: null },
  { result: "valid", present: true, ok: true, terms: true }
];
const seen = [];
for (const row of rows) {
  S.busy = !!row.busy; S.demo = !!row.demo; S.autoLogin = !!row.autoLogin;
  S.stopping = false; S.terms.acceptedVersion = row.terms ? "" : "v1";
  S.login = { ok: row.ok, present: row.present, checking: !!row.checking,
    loginPending: !!row.loginPending, result: row.result, expireAt: null,
    estimateReason: null, lastCheckAt: "", view: {} };
  paintLogin();
  seen.push([$("#pill").className, $("#pill-text").textContent, $("#pill-sub").textContent,
             $("#status-detail").textContent]);
}
out.push(seen);
""")[0]
        self.assertEqual(data, [
            ["pill is-busy", "已登录", "", "登录状态保持不变；计划进度见报名区域"],
            ["pill is-warn", "演示模式", "内存样例", "不读取登录信息、不访问学校，只演示界面与流程"],
            ["pill is-busy is-spin", "自动登录中…", "", "学校说登录失效了，电脑正在用保存的账号自动登录"],
            ["pill is-busy", "登录中…", "", "请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态"],
            ["pill is-busy", "检查登录…", "", "正在检查登录状态，马上就好"],
            ["pill is-none", "未登录", "", "打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录"],
            ["pill is-warn", "登录待确认", "", "暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录"],
            ["pill is-bad", "登录已失效", "", "重新登录后可继续使用"],
            ["pill is-ok", "已登录", "", "学校确认登录有效"],
            ["pill", "未登录", "", "打开顶栏的登录状态，点「登录」开始使用"],
            ["pill is-none", "等同意条款", "", "同意使用条款后才会检查登录"],
        ])

    def test_relogin_source_literals_are_in_the_step_list(self):
        view = (ROOT / "local/ui/features/login/view-relogin.js").read_text(encoding="utf-8")
        actions = (ROOT / "local/ui/features/login/actions-relogin.js").read_text(encoding="utf-8")
        steps = set(run_js("out.push(RELOGIN_STEPS);")[0])
        calls = set(re.findall(r'reloginStep\(\s*["\']([^"\']+)', actions))
        heads = set(re.findall(r'step\s*===\s*["\']([^"\']+)', view))
        self.assertTrue(calls.issubset(steps), sorted(calls - steps))
        self.assertTrue(heads.issubset(steps), sorted(heads - steps))

    def test_relogin_case_returns_only_listed_values(self):
        data = run_js("""
const result = [];
const setCred = (value) => {
  S.advanced = { credential: value };
  if (window.PhonePanel && window.PhonePanel.state) window.PhonePanel.state.advanced = S.advanced;
  result.push(reloginCase());
};
setCred({ saved: true, paused: true });
setCred({ saved: true, paused: false });
setCred({ saved: false, paused: false });
out.push(result);
""")[0]
        self.assertEqual(data, ["bad", "captcha", "login"])
        self.assertTrue(set(data).issubset({"bad", "captcha", "login"}))

# ==================== 源自 test_login_transitions.py ====================
"""登录后端状态接线与新转移的用户可见行为测试。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))



LOGIN_TRANS_PRELUDE = r'''
S.terms.version = "v1"; S.terms.acceptedVersion = "v1";
S.demo = false; S.busy = false; S.stopping = false; S.autoLogin = false;
S.login = { ok: true, present: true, checking: false, loginPending: false,
  result: "valid", handoff: false, expireAt: null, estimateReason: null,
  hours: null, lastCheckAt: "", lastCheckState: "valid", view: {} };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const resetLogin = () => {
  S.busy = false; S.demo = false; S.autoLogin = false; S.stopping = false;
  S.login = { ok: true, present: true, checking: false, loginPending: false,
    result: "valid", handoff: false, expireAt: null, estimateReason: null,
    hours: null, lastCheckAt: "", lastCheckState: "valid", view: {} };
  S.login.auto = { state: "idle", block: "", retryInS: null, at: 0 };
  S.terms.acceptedVersion = "v1";
};
'''


class LoginTransitionTests(unittest.TestCase):
    def test_rechecking_keeps_green_capsule_and_blocks_start(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
S.login.checking = true;
paintLogin();
updateControls();
out.push({ text: $("#pill-text").textContent, sub: $("#pill-sub").textContent,
  note: $("#status-detail").textContent, state: S.login.view.state,
  phase: S.login.view.phase, className: $("#pill").className,
  disabled: $("#btn-plan").disabled });
''')[0]
        self.assertEqual(data["text"], "已登录")
        self.assertEqual(data["sub"], "正在确认")
        self.assertEqual(data["state"], "checking")
        self.assertEqual(data["phase"], "rechecking")
        self.assertEqual(data["className"], "pill is-ok is-spin")
        self.assertTrue(data["disabled"])

    def test_rechecking_outcomes_keep_the_right_capsule(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const rows = [];
const check = (payload) => {
  resetLogin(); S.login.checking = true;
  window.onBackend.check(payload);
  rows.push([$("#pill-text").textContent, S.login.view.phase]);
};
check({ ok: true, result: "valid", session_present: true });
check({ ok: null, result: "unknown" });
check({ ok: false, result: "expired", auto_state: "running" });
check({ ok: false, result: "expired", auto_state: "blocked", auto_block: "ocr_missing" });
out.push(rows);
''')[0]
        self.assertEqual(data, [["已登录", "valid"], ["登录待确认", "unknown"],
                                ["自动登录中…", "auto"], ["要你输验证码", "needs_code"]])

    def test_backend_auto_state_drives_running_and_handoff_banner(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
window.onBackend.login_auto({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
const running = { text: $("#pill-text").textContent, phase: S.login.view.phase,
  auto: S.autoLogin };
S.login.result = "expired"; S.login.ok = false;
$("#banners").innerHTML = "";
window.onBackend.login_auto({ auto_state: "handoff", auto_block: "", auto_retry_in_s: null });
const handoff = { text: $("#pill-text").textContent, phase: S.login.view.phase,
  state: S.login.view.state, auto: S.autoLogin, banners: $("#banners").innerHTML };
out.push({ running, handoff });
''')[0]
        self.assertEqual(data["running"], {"text": "自动登录中…", "phase": "auto", "auto": True})
        self.assertEqual(data["handoff"]["text"], "要你输验证码")
        self.assertEqual(data["handoff"]["phase"], "needs_code")
        self.assertEqual(data["handoff"]["state"], "bad")
        self.assertFalse(data["handoff"]["auto"])
        self.assertIn("输入验证码", data["handoff"]["banners"])

    def test_blocked_ocr_missing_and_backoff_use_new_capsules(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin(); S.login.result = "expired"; S.login.ok = false;
window.onBackend.login_auto({ auto_state: "blocked", auto_block: "ocr_missing", auto_retry_in_s: null });
const code = [$("#pill-text").textContent, S.login.view.phase, S.login.view.note, $("#banners").innerHTML];
window.onBackend.login_auto({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 300 });
const first = [$("#pill-text").textContent, $("#pill-sub").textContent, S.login.view.phase,
  S.login.view.state, S.login.view.note];
S.login.auto.at -= 241000; paintLogin();
const later = $("#pill-sub").textContent;
window.onBackend.login_auto({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
out.push({ code, first, later, running: [$("#pill-text").textContent, S.login.view.phase] });
''')[0]
        self.assertEqual(data["code"][0:2], ["要你输验证码", "needs_code"])
        self.assertIn("认不了验证码", data["code"][2])
        self.assertIn("输入验证码", data["code"][3])
        self.assertEqual(data["first"][0:4], ["登录已失效", "5 分钟后再试", "retry_later", "bad"])
        self.assertIn("5 分钟后会再试", data["first"][4])
        self.assertEqual(data["later"], "1 分钟后再试")
        self.assertEqual(data["running"], ["自动登录中…", "auto"])

    def test_invalid_state_defaults_idle_and_backoff_zero_is_not_retry_later(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
const invalid = applyAutoState({ auto_state: "made_up", auto_block: 7, auto_retry_in_s: 99 });
const invalidView = [S.login.auto.state, S.autoLogin];
applyAutoState({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
const missing = applyAutoState({});
const missingView = [S.login.auto.state, S.autoLogin];
S.login.result = "expired"; S.login.ok = false;
applyAutoState({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 0 });
paintLogin();
out.push({ invalid, invalidView, missing, missingView, phase: S.login.view.phase, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data["invalid"], True)
        self.assertEqual(data["invalidView"], ["idle", False])
        self.assertEqual(data["missing"], False)
        self.assertEqual(data["missingView"], ["running", True])
        self.assertEqual(data["phase"], "expired")
        self.assertEqual(data["text"], "登录已失效")

    def test_retry_minutes_round_up(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin(); S.login.result = "expired"; S.login.ok = false;
applyAutoState({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 61 });
paintLogin();
out.push({ sub: $("#pill-sub").textContent });
''')[0]
        self.assertEqual(data["sub"], "2 分钟后再试")

    def test_rechecking_requires_a_valid_answer_and_old_banner_paths_stay_intact(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin(); S.login.checking = true; S.login.ok = false; S.login.result = "valid";
paintLogin();
const checking = [S.login.view.phase, S.login.view.state];
S.login.view = { state: "unknown", phase: "unknown" };
const unknown = loginBannerHtml(S.login.view, false);
S.login.view = { state: "bad", phase: "expired" };
const bad = loginBannerHtml(S.login.view, false);
out.push({ checking, unknown, bad });
''')[0]
        self.assertEqual(data["checking"], ["checking", "checking"])
        self.assertIn("暂时无法确认登录状态", data["unknown"])
        self.assertIn("登录已失效", data["bad"])

    def test_old_relay_snapshot_does_not_set_auto_login(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
receiveReloginState({ state: "waiting_code", mode: "auto", origin: "auto", live: true,
  flow_id: "f1", image: "data:image/png;base64,AAA" });
out.push({ auto: S.autoLogin, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"auto": False, "text": "已登录"})

    def test_valid_without_auto_state_retracts_old_running_mirror(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
applyAutoState({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
setLogin(null, true, true, { result: "valid" });
out.push({ auto: S.autoLogin, state: S.login.auto.state, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"auto": False, "state": "idle", "text": "已登录"})

    def test_switch_to_browser_waits_for_cancel_before_closing(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const calls = [];
window.pywebview = { api: {
  relogin_cancel: (id) => { calls.push(["cancel", id, S.relogin.step]); return Promise.resolve({ ok: true }); },
  login: () => { calls.push(["login"]); return Promise.resolve({ ok: true }); },
} };
S.relogin = { open: true, step: "cap", flowId: "f1", challengeId: "c1" };
$("#dlg-relogin").open = true;
receiveReloginState({ state: "waiting_code", mode: "manual", origin: "desktop", live: true,
  flow_id: "f1", image: "data:image/png;base64,AAA" });
await reloginSwitchToBrowser();
out.push({ calls: calls, open: S.relogin.open, stepAtCancel: calls[0][2] });
''')[0]
        self.assertEqual(data["calls"], [["cancel", "f1", "wait"], ["login"]])
        self.assertFalse(data["open"])

    def test_bad_password_browser_switch_still_closes_immediately(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const calls = [];
window.pywebview = { api: { login: () => { calls.push("login"); return Promise.resolve({ ok: true }); } } };
S.relogin = { open: true, step: "bad", flowId: "", challengeId: "" };
$("#dlg-relogin").open = true;
await reloginSwitchToBrowser();
out.push({ open: S.relogin.open, calls: calls });
''')[0]
        self.assertEqual(data, {"open": False, "calls": ["login"]})


    def test_blocked_for_other_reasons_stays_expired_with_relogin_banner(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const rows = [];
["no_credentials", "paused"].forEach((block) => {
  resetLogin(); $("#banners").innerHTML = "";
  window.onBackend.check({ ok: false, result: "expired", session_present: true,
    auto_state: "blocked", auto_block: block, auto_retry_in_s: null });
  rows.push([block, "check", $("#pill-text").textContent, S.login.view.phase,
    $("#banners").innerHTML]);
  resetLogin(); S.login.result = "expired"; S.login.ok = false; $("#banners").innerHTML = "";
  window.onBackend.login_auto({ auto_state: "blocked", auto_block: block, auto_retry_in_s: null });
  rows.push([block, "push", $("#pill-text").textContent, S.login.view.phase,
    $("#banners").innerHTML]);
});
out.push(rows);
''')[0]
        self.assertEqual(len(data), 4)
        for block, path, text, phase, banners in data:
            with self.subTest(block=block, path=path):
                self.assertEqual(text, "登录已失效")
                self.assertEqual(phase, "expired")
                self.assertIn("重新登录", banners)
                self.assertNotIn("输入验证码", banners)

    def test_switch_to_browser_shows_switching_until_cancel_returns(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const calls = [];
let release = null;
window.pywebview = { api: {
  relogin_cancel: (id) => { calls.push("cancel"); return new Promise((ok) => { release = ok; }); },
  login: () => { calls.push("login"); return Promise.resolve({ ok: true }); },
} };
S.relogin = { open: true, step: "cap", flowId: "f1", challengeId: "c1" };
$("#dlg-relogin").open = true;
receiveReloginState({ state: "waiting_code", mode: "manual", origin: "desktop", live: true,
  flow_id: "f1", image: "data:image/png;base64,AAA" });
const done = reloginSwitchToBrowser();
for (let i = 0; i < 6; i += 1) await Promise.resolve();
const during = { open: S.relogin.open, dlg: !!$("#dlg-relogin").open, step: S.relogin.step,
  words: [$("#dlg-relogin-title").textContent, $("#rl-sub").textContent,
    $("#rl-wait-text").textContent].join("|"),
  logins: calls.filter((c) => c === "login").length };
release({ ok: true });
await done;
out.push({ during, open: S.relogin.open, dlg: !!$("#dlg-relogin").open,
  logins: calls.filter((c) => c === "login").length,
  cancels: calls.filter((c) => c === "cancel").length });
''')[0]
        self.assertTrue(data["during"]["open"])
        self.assertTrue(data["during"]["dlg"])
        self.assertEqual(data["during"]["step"], "wait")
        self.assertIn("正在切换…", data["during"]["words"])
        self.assertEqual(data["during"]["logins"], 0, "取消返回之前不能发登录")
        self.assertFalse(data["open"])
        self.assertFalse(data["dlg"])
        self.assertEqual(data["logins"], 1)
        self.assertEqual(data["cancels"], 1)

    def test_switch_to_browser_still_closes_when_cancel_fails(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const calls = [];
window.pywebview = { api: {
  relogin_cancel: (id) => { calls.push("cancel"); return Promise.reject(new Error("cancel failed")); },
  login: () => { calls.push("login"); return Promise.resolve({ ok: true }); },
} };
S.relogin = { open: true, step: "cap", flowId: "f1", challengeId: "c1" };
$("#dlg-relogin").open = true;
receiveReloginState({ state: "waiting_code", mode: "manual", origin: "desktop", live: true,
  flow_id: "f1", image: "data:image/png;base64,AAA" });
await reloginSwitchToBrowser();
out.push({ open: S.relogin.open, dlg: !!$("#dlg-relogin").open,
  logins: calls.filter((c) => c === "login").length });
''')[0]
        self.assertEqual(data, {"open": False, "dlg": False, "logins": 1})

    def test_demo_set_login_without_auto_state_retracts_running(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
resetLogin();
applyAutoState({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
S.demo = true; S.login.result = "expired"; S.login.ok = false;
setLogin(null, false, true, {});
out.push({ auto: S.autoLogin, state: S.login.auto.state });
''')[0]
        self.assertEqual(data, {"auto": False, "state": "idle"})

    def test_phase_grid_stays_in_listed_phases(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const bad = [];
let count = 0;
const flags = [false, true];
const autos = AUTO_STATES.concat(["made_up"]);
flags.forEach((busy) => flags.forEach((demo) => flags.forEach((autoLogin) =>
  flags.forEach((loginPending) => flags.forEach((checking) => flags.forEach((termsLocked) =>
  [true, false, null].forEach((ok) => [true, false, null].forEach((present) =>
  ["valid", "expired", "unknown", "none"].forEach((result) => autos.forEach((state) =>
  ["", "ocr_missing", "paused"].forEach((block) => [null, 0, 5].forEach((retryLeftS) => {
    const phase = loginPhase({ busy, demo, autoLogin, loginPending, checking, termsLocked,
      ok, present, result, auto: { state, block, retryLeftS } });
    count += 1;
    if (LOGIN_PHASES.indexOf(phase) < 0 && bad.length < 5) bad.push(phase);
  }))))))))))));
out.push({ count, bad });
''')[0]
        self.assertGreater(data["count"], 0)
        self.assertEqual(data["bad"], [])

    def test_apply_auto_state_only_writes_listed_states(self):
        data = run_js(LOGIN_TRANS_PRELUDE + r'''
const bad = [];
const inputs = AUTO_STATES.concat(["made_up", "", "RUNNING", "null"]);
inputs.forEach((value) => {
  resetLogin();
  applyAutoState({ auto_state: value, auto_block: "", auto_retry_in_s: 30 });
  if (AUTO_STATES.indexOf(S.login.auto.state) < 0) bad.push([value, S.login.auto.state]);
  if (S.autoLogin !== (S.login.auto.state === "running")) bad.push([value, "mirror"]);
});
out.push({ count: inputs.length, bad });
''')[0]
        self.assertEqual(data["count"], 10)
        self.assertEqual(data["bad"], [])

# ==================== 源自 test_ui_login_capsule.py ====================
"""登录胶囊的用户可见结论（行为测试）。

在 node 沙箱里按 index.html 的加载序跑真实界面脚本，摆好登录状态后调 paintLogin，
只看用户看得到的东西：胶囊文字、色调、副句、登录按钮文案与实心/描边。
不对源码文本做断言，搬文件也不会红。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))


# 条款已同意、在线、非演示；业务现在 = 北京时间 2026-11-06 14:00
CAPSULE_PRELUDE = r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = false; S.login.result = "none"; S.login.ok = null; S.login.checking = true;
paintLogin();
out.push({ text: read(), state: readState() });
""")[0]
        self.assertEqual(data["text"], "检查登录…", "校验中不能被首次使用盖过去")
        self.assertEqual(data["state"], "checking")

    def test_waiting_terms_says_so(self):
        """没同意使用条款时胶囊说「等同意条款」，即使上次结论是已登录。"""
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.expireAt = Date.UTC(2026, 10, 6, 8, 0, 0);
paintLogin();
out.push({ note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["note"], "学校确认登录有效；预计约到 16:00，以学校为准")

    def test_next_day_estimate_says_tomorrow(self):
        """估算落在明天时写「预计约到明天 10:00」，不写具体日期。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.expireAt = Date.UTC(2026, 10, 7, 2, 0, 0);
paintLogin();
out.push({ note: $("#status-detail").textContent });
""")[0]
        self.assertEqual(data["note"], "学校确认登录有效；预计约到明天 10:00，以学校为准")

    def test_no_estimate_when_school_did_not_give_one(self):
        """没有估算锚点时详情只说学校确认的事实，不编时间。"""
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.autoLogin = true;
S.login.handoff = true; S.login.result = "expired";
window.onBackend.login_auto({ auto_state: "handoff", auto_block: "", auto_retry_in_s: null });
paintLogin();
out.push({ auto: S.autoLogin, text: read() });
""")[0]
        self.assertFalse(data["auto"], "转人工以后自动登录态要收回")
        self.assertNotEqual(data["text"], "自动登录中…")

    def test_login_card_check_button_disabled_while_busy(self):
        """计划跑着时登录详情卡的「检查」按钮不可点，不和计划抢网络。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.busy = true;
renderLoginCard();
out.push({ disabled: $("#btn-login-check").disabled });
""")[0]
        self.assertTrue(data["disabled"], "忙碌时检查按钮要禁用")

    def test_login_card_check_button_disabled_while_checking(self):
        """正在检查登录时详情卡的「检查」按钮不可点，避免重复发请求。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.checking = true;
renderLoginCard();
out.push({ disabled: $("#btn-login-check").disabled });
""")[0]
        self.assertTrue(data["disabled"], "检查中检查按钮要禁用")

    def test_valid_check_dismisses_closed_login_window_result(self):
        """关掉登录窗口留下登录未完成结果条后，check 返回 valid 时自动收起。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.preLoginSnapshot = loginSnapshotState();
window.onBackend.done({ kind: "login", ok: false, reason: "登录窗口被关掉了" });
const before = { hidden: $("#result").hidden, title: $("#result").textContent,
  kind: $("#result").dataset.kind };
window.onBackend.check({ ok: true, result: "valid", hours_left: null });
out.push({ before, after: { hidden: $("#result").hidden, text: $("#result").textContent,
  kind: $("#result").dataset.kind || "" } });
""")[0]
        self.assertFalse(data["before"]["hidden"])
        self.assertIn("登录窗口被关掉了", data["before"]["title"])
        self.assertEqual(data["before"]["kind"], "login_attempt")
        self.assertTrue(data["after"]["hidden"], "check 确认 valid 后应自动收起该结果条")
        self.assertEqual(data["after"]["text"], "")
        self.assertEqual(data["after"]["kind"], "", "收起后应清除结果条类别标记")

    def test_non_valid_check_keeps_login_incomplete_result(self):
        """check 返回 unknown 或 expired 时不得把登录未完成结果条收起。"""
        for check_res in ("unknown", "expired"):
            with self.subTest(result=check_res):
                data = run_js(CAPSULE_PRELUDE + f"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.preLoginSnapshot = loginSnapshotState();
window.onBackend.done({{ kind: "login", ok: false, reason: "窗口被关掉了" }});
window.onBackend.check({{ ok: false, result: "{check_res}", reason: "仍未确认" }});
out.push({{ hidden: $("#result").hidden, text: $("#result").textContent }});
""")[0]
                self.assertFalse(data["hidden"], f"{check_res} 不得收起登录未完成结果条")
                self.assertIn("登录窗口被关掉了", data["text"])

    def test_valid_check_keeps_non_login_result_banner(self):
        """报名结果等其他类别的结果条遇到 valid check 时不得被误收起。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
window.onBackend.done({ kind: "grab", ok: true, label: "心理健康讲座" });
window.onBackend.check({ ok: true, result: "valid", hours_left: null });
out.push({ hidden: $("#result").hidden, text: $("#result").textContent });
""")[0]
        self.assertFalse(data["hidden"], "报名成功结果条遇到 valid check 不得被收起")
        self.assertIn("心理健康讲座", data["text"])

    def test_grab_result_replacing_login_incomplete_clears_kind_and_survives_valid_check(self):
        """登录未完成结果条被无类别的报名结果替换后，必须清掉旧类别标记，后续登录检查有效时不能把报名结果收起。"""
        data = run_js(CAPSULE_PRELUDE + r"""
resetLogin();
S.login.present = true; S.login.result = "valid"; S.login.ok = true;
S.login.preLoginSnapshot = loginSnapshotState();
window.onBackend.done({ kind: "login", ok: false, reason: "登录窗口被关掉了" });
const loginKind = $("#result").dataset.kind || "";
window.onBackend.done({ kind: "grab", ok: true, label: "心理健康讲座" });
const afterGrab = {
  hidden: $("#result").hidden,
  text: $("#result").textContent,
  kind: $("#result").dataset.kind || "",
};
window.onBackend.check({ ok: true, result: "valid", hours_left: null });
const afterCheck = {
  hidden: $("#result").hidden,
  text: $("#result").textContent,
};
out.push({ loginKind, afterGrab, afterCheck });
""")[0]
        self.assertEqual(data["loginKind"], "login_attempt")
        self.assertFalse(data["afterGrab"]["hidden"])
        self.assertIn("心理健康讲座", data["afterGrab"]["text"])
        self.assertEqual(data["afterGrab"]["kind"], "")
        self.assertFalse(data["afterCheck"]["hidden"], "换成报名结果后 valid check 不得将其收起")
        self.assertIn("心理健康讲座", data["afterCheck"]["text"])


    def test_handoff_from_the_backend_does_not_light_auto_login(self):
        """已转人工时后端就算还说 recovering，胶囊也不能报「自动登录中…」。"""
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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
        data = run_js(CAPSULE_PRELUDE + r"""
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

# ==================== 源自 test_ui_relogin_dialog.py ====================
"""重新登录对话框的用户可见结果（行为测试）。

在 node 沙箱里按 index.html 的加载序跑真实界面脚本，按「有没有保存账号 × 保存的密码有没有被拒绝」
走不同入口，看用户看得到的东西：标题、副句、当前哪一步、底栏按钮、红字。
不对源码文本做断言，搬文件也不会红。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS))


DIALOG_PRELUDE = r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
reloginStep("wait", "正在核对验证码…");
out.push({ title: title(), step: stepOf() });
""")[0]
        self.assertEqual(data["title"], "输入验证码")

    def test_auto_login_wait_step_says_so(self):
        """电脑正在自动登录时，等待步标题是「正在自动登录」并带上保存的账号。"""
        data = run_js(DIALOG_PRELUDE + r"""
cred({ saved: true, paused: false, username: "20230001" });
openRelogin();
reloginStep("wait", "电脑正在自动登录…");
out.push({ title: title(), sub: sub() });
""")[0]
        self.assertEqual(data["title"], "正在自动登录")
        self.assertEqual(data["sub"], "用保存的账号 20****01")

    def test_browser_way_offers_the_school_page_button(self):
        """选「用学校登录页」后，登录步的按钮换成「打开学校登录页」，没有下一步。"""
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
S.busy = true;
S.relogin = { open: false };
receiveReloginState({ state: "success", flow_id: "f6" });
out.push({ log: logText() });
""")[0]
        self.assertIn("重新登录成功，报名计划照常继续", data["log"])

    def test_open_dialog_busy_success_log_mentions_the_plan(self):
        """计划跑着、对话框开着时成功，运行记录要提一句报名计划照常继续。"""
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
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
        data = run_js(DIALOG_PRELUDE + r"""
cred({ saved: false });
S.relogin = { open: false, step: "cap", flowId: "f1", way: "" };
reloginPickWay("browser");
out.push({ step: stepOf(), way: S.relogin.way });
""")[0]
        self.assertEqual(data["step"], "cap", "关着时不该换步")
        self.assertEqual(data["way"], "", "关着时不该记登录方式")

    def test_a_failed_code_answer_after_closing_does_not_show_a_message_step(self):
        """验证码提交失败回来时对话框已关，就不该再跳到提示步。"""
        data = run_js(DIALOG_PRELUDE + r"""
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
