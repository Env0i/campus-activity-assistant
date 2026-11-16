#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录胶囊状态机与重新登录清单的结构测试。

@author Author
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent.parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402


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
            ["pill is-busy", "自动登录中…", "", "学校说登录失效了，电脑正在用保存的账号自动登录"],
            ["pill is-busy", "登录中…", "", "请在弹出的浏览器中完成登录；取消或关闭窗口后会保留原状态"],
            ["pill is-busy", "检查登录…", "", "正在检查登录状态，马上就好"],
            ["pill is-none", "未登录", "", "打开顶栏的登录状态，点「登录」，在打开的浏览器中完成登录"],
            ["pill is-none", "登录待确认", "", "暂时无法确认登录状态；检查网络后点「刷新」，先不用重新登录"],
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


if __name__ == "__main__":
    unittest.main()
