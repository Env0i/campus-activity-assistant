#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录胶囊、详情卡和横幅的样式契约测试。

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


PRELUDE = r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
resetLogin(); S.login.ok = false; S.login.result = "expired";
window.onBackend.login_auto({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
const running = $("#pill").className;
S.login.ok = true; S.login.result = "valid";
window.onBackend.login_auto({ auto_state: "idle", auto_block: "", auto_retry_in_s: null });
out.push([running, $("#pill").className]);
''')[0]
        self.assertEqual(data, ["pill is-busy is-spin", "pill is-ok"])

    def test_unconfirmed_capsule_is_amber(self):
        data = run_js(PRELUDE + r'''
resetLogin(); S.login.ok = false; S.login.result = "unknown";
paintLogin();
out.push({ className: $("#pill").className, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"className": "pill is-warn", "text": "登录待确认"})

    def test_code_handoff_card_overrides_both_auto_paths(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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


if __name__ == "__main__":
    unittest.main()
