#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录后端状态接线与新转移的用户可见行为测试。

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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
resetLogin(); S.login.result = "expired"; S.login.ok = false;
applyAutoState({ auto_state: "backoff", auto_block: "", auto_retry_in_s: 61 });
paintLogin();
out.push({ sub: $("#pill-sub").textContent });
''')[0]
        self.assertEqual(data["sub"], "2 分钟后再试")

    def test_rechecking_requires_a_valid_answer_and_old_banner_paths_stay_intact(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
resetLogin();
receiveReloginState({ state: "waiting_code", mode: "auto", origin: "auto", live: true,
  flow_id: "f1", image: "data:image/png;base64,AAA" });
out.push({ auto: S.autoLogin, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"auto": False, "text": "已登录"})

    def test_valid_without_auto_state_retracts_old_running_mirror(self):
        data = run_js(PRELUDE + r'''
resetLogin();
applyAutoState({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
setLogin(null, true, true, { result: "valid" });
out.push({ auto: S.autoLogin, state: S.login.auto.state, text: $("#pill-text").textContent });
''')[0]
        self.assertEqual(data, {"auto": False, "state": "idle", "text": "已登录"})

    def test_switch_to_browser_waits_for_cancel_before_closing(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
const calls = [];
window.pywebview = { api: { login: () => { calls.push("login"); return Promise.resolve({ ok: true }); } } };
S.relogin = { open: true, step: "bad", flowId: "", challengeId: "" };
$("#dlg-relogin").open = true;
await reloginSwitchToBrowser();
out.push({ open: S.relogin.open, calls: calls });
''')[0]
        self.assertEqual(data, {"open": False, "calls": ["login"]})


    def test_blocked_for_other_reasons_stays_expired_with_relogin_banner(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
resetLogin();
applyAutoState({ auto_state: "running", auto_block: "", auto_retry_in_s: null });
S.demo = true; S.login.result = "expired"; S.login.ok = false;
setLogin(null, false, true, {});
out.push({ auto: S.autoLogin, state: S.login.auto.state });
''')[0]
        self.assertEqual(data, {"auto": False, "state": "idle"})

    def test_phase_grid_stays_in_listed_phases(self):
        data = run_js(PRELUDE + r'''
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
        data = run_js(PRELUDE + r'''
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


if __name__ == "__main__":
    unittest.main()
