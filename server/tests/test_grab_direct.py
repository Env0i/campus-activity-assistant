#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器直发签名报名、登录失效重登、主动换新避让与跨端对照（离线测试）。

全部用替身：假网络 / 假时钟 / 假 systemctl / 假重登子进程，绝不联网、
不读取真实 server/data 或 config.json、不起 systemd。
@author Author
"""
from __future__ import annotations

import importlib.util
import json
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.request
from datetime import datetime
from pathlib import Path
from unittest import mock

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
SCRIPTS = ROOT / "scripts"
for extra in (str(SCRIPTS / "lib"), str(DEPLOY / "signup"), str(DEPLOY / "login")):
    if extra not in sys.path:
        sys.path.insert(0, extra)


def _load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_auto_login(app_dir: str, login_dir: str):
    fake_fcntl = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=lambda *a: None)
    with mock.patch.dict(os.environ, {"APP_DIR": app_dir, "LOGIN_DIR": login_dir}), \
         mock.patch.dict(sys.modules, {"fcntl": fake_fcntl}):
        return _load_module("server_auto_login_under_test", DEPLOY / "login" / "auto_login.py")


import preempt_guard
import school_detail
import signup_direct
import signup_io
import signup_policy
import signup_relogin
import signup_reply
import signup_signing
import signup_transport


class FakeClock:
    def __init__(self, now_s=1000.0):
        self.wall = float(now_s)
        self.mono = float(now_s)

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def sleep(self, dt):
        self.wall += float(dt)
        self.mono += float(dt)
        time.sleep(0.005)


class _FakeResponse:
    def __init__(self, payload_obj, status=200):
        self.status = status
        self.code = status
        if isinstance(payload_obj, (bytes, bytearray)):
            self._body = bytes(payload_obj)
        else:
            self._body = json.dumps(payload_obj, ensure_ascii=False).encode("utf-8")

    def read(self):
        return self._body

    def close(self):
        return None


class _SequenceOpener:
    def __init__(self, handler):
        self._handler = handler
        self.requests = []
        self._lock = threading.Lock()

    def open(self, req, timeout=15.0):
        with self._lock:
            self.requests.append({
                "url": req.full_url,
                "method": req.get_method(),
                "headers": dict(req.header_items()),
                "data": req.data,
                "timeout": timeout,
            })
            idx = len(self.requests)
        return self._handler(idx, req)


class SigningTests(unittest.TestCase):
    def test_two_cng_parity_vectors(self):
        key = b"Abcdefgh12345678"
        h1 = signup_signing.build_signup_hash("test-activity-1", 1767225600000, key)
        self.assertEqual(
            h1,
            "e32414cb4f3634022e6adfbb42f1e32ea6b79ae9d39d650ec973ab4ef9753413",
        )
        h2 = signup_signing.build_signup_hash("a" * 40, 1767225600123, key)
        self.assertEqual(
            h2,
            "f06538985c008b061470062a5ccc92d1"
            "f06538985c008b061470062a5ccc92d1"
            "fee87e80cd50a7100899d759036b33c9"
            "d7cf30c16f023d2df3d50225b40ab818",
        )

    def test_fips_197_aes128_vector(self):
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        plain = bytes.fromhex("3243f6a8885a308d313198a2e0370734")
        expected = bytes.fromhex("3925841d02dc09fbdc118597196a0b32")
        self.assertEqual(signup_signing.encrypt_aes_ecb(plain, key), expected)

    def test_full_block_32_byte_cng_parity_vector(self):
        key = b"Abcdefgh12345678"
        # 明文 "abcdefghijklmnopqr,1767225600000" 恰好 32 字节（两整块），PKCS7 必须额外补满 16 字节
        got = signup_signing.build_signup_hash("abcdefghijklmnopqr", 1767225600000, key)
        self.assertEqual(
            got,
            "fb492d0431de8ae69e0ebd7a4f2a0658"
            "f70c6d87ccedad072c90366fa28724e9"
            "fd9bc72a0d101f61b4580230619e6962",
        )

    def test_parse_runtime_key_valid_and_invalid(self):
        self.assertEqual(
            signup_signing.parse_runtime_key({"code": 1, "data": "Abcdefgh12345678"}),
            b"Abcdefgh12345678",
        )
        bad_payloads = [
            None,
            "Abcdefgh12345678",
            {},
            {"data": None},
            {"data": 1234567890123456},
            {"data": "short"},
            {"data": "too_long_12345678"},
            {"data": "Abcdefgh1234567_"},
            {"data": "Abcdefgh1234567中"},
        ]
        for payload in bad_payloads:
            self.assertIsNone(signup_signing.parse_runtime_key(payload))

    def test_signer_unavailable_when_backend_missing_or_fails(self):
        key = b"Abcdefgh12345678"
        with mock.patch.object(
            signup_signing,
            "_load_cipher_backend",
            side_effect=signup_signing.SignerUnavailable("cryptography 不可用"),
        ):
            with self.assertRaises(signup_signing.SignerUnavailable):
                signup_signing.build_signup_hash("act-1", 1767225600000, key)

    def test_build_signup_hash_input_validation(self):
        key = b"Abcdefgh12345678"
        for bad_id in ("", "a,b", "a\nb", "a\rb", None):
            with self.assertRaises(ValueError):
                signup_signing.build_signup_hash(bad_id, 1767225600000, key)
        for bad_ms in (0, -1, True, "1767225600000"):
            with self.assertRaises(ValueError):
                signup_signing.build_signup_hash("act-1", bad_ms, key)
        for bad_key in (b"short", b"x" * 17, "Abcdefgh12345678"):
            with self.assertRaises(ValueError):
                signup_signing.build_signup_hash("act-1", 1767225600000, bad_key)


class DirectSignupTests(unittest.TestCase):
    def _run_direct(self, *, clock, opener, key=b"Abcdefgh12345678", key_reason="ok",
                    token_fn=None, max_attempts=10, click_cb=None, relogin_fn=None,
                    is_joined_fn=None):
        logs, cards = [], []
        res = signup_direct.run_direct_submit_loop(
            activity_id="act-1", at_ts=1000.0, window_s=60.0, max_attempts=max_attempts,
            api_base="https://portal.school.example.edu/dr/api",
            referer="https://portal.school.example.edu/stu/", ua="UA",
            token_fn=token_fn or (lambda: "tok-1"),
            sign_headers_fn=lambda path, body: {"X-Test": "1"},
            initial_key=key, initial_key_reason=key_reason,
            is_joined_fn=is_joined_fn,
            notify_fn=lambda t, l, tpl="green": cards.append((t, l, tpl)) or True,
            log_fn=logs.append, clock=clock, name="音乐节",
            click_fallback_fn=click_cb, opener=opener,
            relogin_fn=relogin_fn, sleep_fn=clock.sleep,
        )
        return res, logs, cards

    def test_direct_success_and_path_line_in_card(self):
        clock = FakeClock(1000.0)
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 1, "message": "ok"}))
        (reason, state), logs, cards = self._run_direct(clock=clock, opener=opener)
        self.assertEqual(reason, "success")
        self.assertEqual(state["path"], "direct")
        self.assertIn("/rjyHdCyr/signUp/", opener.requests[0]["url"])
        self.assertTrue(any("报名路径：直发" in line for line in cards[-1][1]))

    def test_full_stops_immediately_without_burning_attempts(self):
        clock = FakeClock(1000.0)
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 500, "message": "报名人数已满"}))
        (reason, state), _, cards = self._run_direct(clock=clock, opener=opener, max_attempts=20)
        self.assertEqual(reason, "full")
        self.assertLessEqual(state["attempts"], 2)
        self.assertIn("名额已满", "\n".join(cards[-1][1]))

    def test_downgrade_missing_key_and_signer_unavailable(self):
        clock = FakeClock(1000.0)
        called = []
        res1, _, _ = self._run_direct(
            clock=clock, opener=_SequenceOpener(lambda i, r: _FakeResponse({"code": 1})),
            key=None, key_reason="http_500",
            click_cb=lambda burst, state: (called.append((burst, state)), ("fallback", state))[1],
        )
        self.assertEqual(res1[0], "fallback")
        self.assertEqual(called[0][1]["path"], "click")
        with mock.patch.object(
            signup_direct, "build_signup_hash",
            side_effect=signup_signing.SignerUnavailable("cryptography 不可用"),
        ):
            res2, _, _ = self._run_direct(
                clock=clock, opener=_SequenceOpener(lambda i, r: _FakeResponse({"code": 1})),
                click_cb=lambda burst, state: ("fallback2", state),
            )
            self.assertEqual(res2[0], "fallback2")
            self.assertEqual(res2[1]["path"], "click")

    def test_downgrade_version_rekey_once_then_click(self):
        clock = FakeClock(1000.0)

        def handle(idx, req):
            if "/upms/security/runtime/profile" in req.full_url:
                return _FakeResponse({"code": 1, "data": "NewKey1234567890"})
            return _FakeResponse({"code": 0, "message": "版本不兼容"})

        opener = _SequenceOpener(handle)
        (reason, state), _, _ = self._run_direct(
            clock=clock, opener=opener,
            click_cb=lambda burst, st: ("click_after_rekey", st),
        )
        self.assertEqual(reason, "click_after_rekey")
        self.assertEqual(state["path"], "click")
        profile_hits = [r for r in opener.requests if "runtime/profile" in r["url"]]
        self.assertEqual(len(profile_hits), 1)

    def test_downgrade_three_consecutive_unknown_and_shared_budget(self):
        clock = FakeClock(1000.0)
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 500, "message": "未知提示XYZ"}))
        seen, click_cards = {}, []

        def on_click(burst, st):
            seen["attempts"] = burst.attempts
            seen["deadline"] = burst.effective_deadline
            return signup_direct.finish_submit_loop(
                "retry_duration", burst=burst, state=st, name="音乐节",
                log_fn=lambda m: None,
                notify_owner=lambda t, l, tpl="green": click_cards.append((t, l, tpl)) or True,
            )

        (reason, state), _, _ = self._run_direct(
            clock=clock, opener=opener, max_attempts=6, click_cb=on_click,
        )
        self.assertEqual(reason, "retry_duration")
        self.assertEqual(state["path"], "click")
        self.assertIn("未知回包连续 3 次", state["path_reason"])
        self.assertGreaterEqual(seen["attempts"], 3)
        self.assertEqual(seen["deadline"], 1060.0)
        self.assertTrue(
            any("报名路径：点击（原因：未知回包连续 3 次）" in ln for ln in click_cards[-1][1])
        )

    def test_physical_concurrency_max_two_and_no_redirect(self):
        barrier = threading.Event()
        entered = threading.Event()

        def open_fn(req, timeout=8.0):
            if "1" in req.full_url:
                entered.set()
                barrier.wait(timeout=2.0)
            elif "2" in req.full_url:
                barrier.wait(timeout=2.0)
            return _FakeResponse({"code": 1}, status=302)

        q = queue.Queue()
        tr = signup_transport.DirectTransport(q, opener=mock.Mock(open=open_fn))
        try:
            self.assertTrue(tr.try_submit({"request_id": "r1", "url": "https://x/1", "request_deadline": time.monotonic() + 5}))
            entered.wait(timeout=1.0)
            self.assertTrue(tr.try_submit({"request_id": "r2", "url": "https://x/2", "request_deadline": time.monotonic() + 5}))
            self.assertFalse(tr.try_submit({"request_id": "r3", "url": "https://x/3", "request_deadline": time.monotonic() + 5}))
        finally:
            barrier.set()
            tr.close()
        default_opener = signup_transport.build_no_redirect_opener()
        self.assertTrue(any(isinstance(h, urllib.request.HTTPRedirectHandler) for h in default_opener.handlers))

    def test_per_request_token_read_across_attempts(self):
        clock = FakeClock(1000.0)
        tokens = iter(["tok-A", "tok-B", "tok-B", "tok-B"])
        seen_tokens = []

        def handle(idx, req):
            seen_tokens.append(dict(req.header_items()).get("Token"))
            if len(seen_tokens) >= 2:
                return _FakeResponse({"code": 1, "message": "ok"})
            return _FakeResponse({"code": 500, "message": "报名未开始"})

        (reason, _), _, _ = self._run_direct(
            clock=clock, opener=_SequenceOpener(handle), token_fn=lambda: next(tokens, "tok-B"),
        )
        self.assertEqual(reason, "success")
        self.assertEqual(seen_tokens[:2], ["tok-A", "tok-B"])

    def test_rehearse_fetches_key_signs_without_signup_or_notify(self):
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 1, "data": "Abcdefgh12345678"}))
        logs = []
        with mock.patch("builtins.open", side_effect=AssertionError("should not write files")):
            info = signup_direct.rehearse_direct(
                activity_id="act-1", api_base="https://portal.school.example.edu/dr/api",
                referer="https://portal.school.example.edu/stu/", ua="UA",
                token_fn=lambda: "tok-1", sign_headers_fn=lambda p, b: {"X-Test": "1"},
                now_fn=lambda: 1767225600.0, log_fn=logs.append, opener=opener,
            )
        self.assertEqual(info["path"], "direct")
        self.assertTrue(info["signed"])
        self.assertEqual(len(opener.requests), 1)
        self.assertIn("runtime/profile", opener.requests[0]["url"])
        self.assertFalse(any("signUp" in r["url"] for r in opener.requests))


class ReloginTests(unittest.TestCase):
    def test_pre_open_4001_recovers_after_1_5s_without_relogin(self):
        slept, recovered_calls, logs = [], [], []
        res = signup_relogin.handle_pre_open_4001(
            check_fn=lambda: True,
            recover_fn=lambda: (recovered_calls.append(1), True)[1],
            fetch_key_fn=lambda: (b"KeyAfterCheck123", "ok"),
            log_fn=logs.append,
            sleep_fn=slept.append,
        )
        self.assertEqual(slept, [1.5])
        self.assertEqual(recovered_calls, [])
        self.assertEqual(res, ("recovered", b"KeyAfterCheck123", "ok"))

    def test_pre_open_4001_relogins_and_rekeys_when_recheck_fails(self):
        slept, logs = [], []
        ok_res = signup_relogin.handle_pre_open_4001(
            check_fn=lambda: False,
            recover_fn=lambda: True,
            fetch_key_fn=lambda: (b"NewKey1234567890", "ok"),
            log_fn=logs.append,
            sleep_fn=slept.append,
        )
        self.assertEqual(slept, [1.5])
        self.assertEqual(ok_res, ("relogged", b"NewKey1234567890", "ok"))
        fail_res = signup_relogin.handle_pre_open_4001(
            check_fn=lambda: False, recover_fn=lambda: False,
            fetch_key_fn=lambda: (b"Unused1234567890", "ok"),
            log_fn=logs.append, sleep_fn=slept.append,
        )
        self.assertEqual(fail_res[0], "login_invalid")

    def test_in_submit_4001_relogins_rekeys_and_continues_to_success(self):
        clock = FakeClock(1000.0)
        tok_box = {"tok": "old-tok"}
        calls, rekey_calls, second_hashes = {"signup": 0}, {"n": 0}, []

        def handle(idx, req):
            calls["signup"] += 1
            if dict(req.header_items()).get("Token") == "old-tok":
                return _FakeResponse({"code": 4001, "message": "登录失效"})
            second_hashes.append(req.full_url.rsplit("/", 1)[-1])
            return _FakeResponse({"code": 1, "message": "ok"})

        def relogin_cb(ctx):
            out = signup_relogin.handle_in_submit_4001(
                already_tried=ctx.get("relogin_tried", False),
                recover_fn=lambda: (tok_box.update(tok="new-tok"), True)[1],
                fetch_key_fn=lambda: (rekey_calls.update(n=rekey_calls["n"] + 1), (b"ReKeyed123456789", "ok"))[1],
                log_fn=ctx["log"],
            )
            self.assertEqual(out[1], b"ReKeyed123456789")
            return out

        opener = _SequenceOpener(handle)
        (reason, _), _, _ = DirectSignupTests._run_direct(
            DirectSignupTests(), clock=clock, opener=opener,
            token_fn=lambda: tok_box["tok"], relogin_fn=relogin_cb,
        )
        self.assertEqual(reason, "success")
        self.assertEqual(rekey_calls["n"], 1)
        expected_hash = signup_signing.build_signup_hash("act-1", int(clock.wall * 1000), b"ReKeyed123456789")
        self.assertIn(expected_hash, second_hashes)

    def test_in_submit_4001_timeout_or_second_failure_ends_login_invalid(self):
        clock = FakeClock(1000.0)
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 4001, "message": "失效"}))
        (reason1, _), _, _ = DirectSignupTests._run_direct(
            DirectSignupTests(), clock=clock, opener=opener,
            relogin_fn=lambda ctx: signup_relogin.handle_in_submit_4001(
                already_tried=ctx.get("relogin_tried", False),
                recover_fn=lambda: False, fetch_key_fn=lambda: (None, "err"),
                log_fn=ctx["log"],
            ),
        )
        self.assertEqual(reason1, "login_invalid")
        relogin_cnt = {"n": 0}
        (reason2, _), _, _ = DirectSignupTests._run_direct(
            DirectSignupTests(), clock=clock, opener=opener,
            relogin_fn=lambda ctx: (
                relogin_cnt.update(n=relogin_cnt["n"] + 1),
                signup_relogin.handle_in_submit_4001(
                    already_tried=ctx.get("relogin_tried", False),
                    recover_fn=lambda: True,
                    fetch_key_fn=lambda: (b"NewKey1234567890", "ok"),
                    log_fn=ctx["log"],
                ),
            )[1],
        )
        self.assertEqual(reason2, "login_invalid")
        self.assertEqual(relogin_cnt["n"], 2)

    def test_lock_busy_waits_for_token_change_without_spawning(self):
        clock = FakeClock(2000.0)
        spawned, polls, logs = [], {"n": 0}, []

        def token_poll():
            polls["n"] += 1
            return "fresh-tok" if polls["n"] >= 3 else "old-tok"

        ok = signup_relogin.recover_session(
            old_token="old-tok", login_dir="/tmp/login", lock_file="/tmp/lock",
            token_fn=token_poll, timeout_s=60.0, log_fn=logs.append,
            lock_busy_fn=lambda _p: True,
            runner_fn=lambda *a, **kw: spawned.append(1),
            clock=clock, sleep_fn=clock.sleep,
        )
        self.assertTrue(ok)
        self.assertEqual(spawned, [])
        timeout_ok = signup_relogin.recover_session(
            old_token="old-tok", login_dir="/tmp/login", lock_file="/tmp/lock",
            token_fn=lambda: "old-tok", timeout_s=2.0, log_fn=logs.append,
            lock_busy_fn=lambda _p: True, runner_fn=lambda *a, **kw: spawned.append(1),
            clock=clock, sleep_fn=clock.sleep,
        )
        self.assertFalse(timeout_ok)
        self.assertEqual(spawned, [])


class PreemptGuardTests(unittest.TestCase):
    def _write_watchlist(self, root: Path, entries):
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        fp = data_dir / "watchlist.json"
        fp.write_text(json.dumps({"entries": entries}, ensure_ascii=False), encoding="utf-8")
        return fp

    def test_active_grab_unit_skips_preempt_with_custom_prefix(self):
        proc = types.SimpleNamespace(returncode=0, stdout="custom-grab-act1.service loaded active running\n")
        with mock.patch.dict(os.environ, {"GRAB_UNIT_PREFIX": "custom-grab-"}):
            skip, reason = preempt_guard.should_skip_preempt(
                app_dir=tempfile.gettempdir(),
                runner_fn=lambda cmd, **kw: proc,
            )
        self.assertTrue(skip)
        self.assertIn("custom-grab-act1.service", reason)

    def test_watchlist_20min_boundaries_and_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            now = datetime(2026, 11, 24, 12, 0, 0)
            ok_runner = lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout="")
            # 非排队状态 + 20分01秒外 + 已过去 不拦截
            self._write_watchlist(app_dir, [
                {"id": "a", "status": "done", "open_at": "2026-11-24 12:05:00"},
                {"id": "b", "status": "failed", "open_at": "2026-11-24 12:05:00"},
                {"id": "c", "status": "cancelled", "open_at": "2026-11-24 12:05:00"},
                {"id": "d", "status": "queued", "open_at": "2026-11-24 12:20:01"},
                {"id": "e", "status": "queued", "open_at": "2026-11-24 11:59:59"},
            ])
            skip, _ = preempt_guard.should_skip_preempt(
                app_dir=str(app_dir), now_dt=now, runner_fn=ok_runner,
            )
            self.assertFalse(skip)
            # 恰好 20 分钟边界应跳过
            self._write_watchlist(app_dir, [
                {"id": "f", "status": "queued", "open_at": "2026-11-24 12:20:00"},
            ])
            skip_at_20, reason = preempt_guard.should_skip_preempt(
                app_dir=str(app_dir), now_dt=now, runner_fn=ok_runner,
            )
            self.assertTrue(skip_at_20)
            self.assertIn("20 分钟", reason)

    def test_corrupt_or_missing_watchlist_behavior(self):
        ok_runner = lambda cmd, **kw: types.SimpleNamespace(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as tmp:
            app_dir = Path(tmp)
            skip_missing, _ = preempt_guard.should_skip_preempt(app_dir=str(app_dir), runner_fn=ok_runner)
            self.assertFalse(skip_missing)
            data_dir = app_dir / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "watchlist.json").write_text("{bad json", encoding="utf-8")
            skip_bad, reason = preempt_guard.should_skip_preempt(app_dir=str(app_dir), runner_fn=ok_runner)
            self.assertTrue(skip_bad)
            self.assertIn("无法读取", reason)

    def test_passive_relogin_and_force_bypass_preempt_guard_and_max_attempts_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            app_dir, login_dir = Path(tmp) / "app", Path(tmp) / "login"
            (app_dir / "data").mkdir(parents=True)
            login_dir.mkdir(parents=True)
            (app_dir / "data" / "session.json").write_text(json.dumps({"token": "tok-old"}), encoding="utf-8")
            al = _load_auto_login(str(app_dir), str(login_dir))
            with mock.patch.dict(os.environ, {"AUTO_LOGIN_MAX_ATTEMPTS": "2"}):
                self.assertEqual(al._max_attempts(), 2)
            with mock.patch.object(al, "_fp_age_hours", return_value=9.0), \
                 mock.patch.object(al, "_probe_fail_streak", return_value=2), \
                 mock.patch.object(al, "_session_fresh", return_value=False), \
                 mock.patch.object(al, "_load_credentials", return_value=None), \
                 mock.patch.object(al.preempt_guard, "should_skip_preempt", return_value=(True, "忙")):
                with mock.patch.object(sys, "argv", ["auto_login.py", "--preempt"]):
                    # 被动失效（probe 连续失败 2 次）不被避让拦住，继续走到加载凭据（返回 3）
                    self.assertEqual(al.main(), 3)
                with mock.patch.object(sys, "argv", ["auto_login.py", "--force"]):
                    self.assertEqual(al.main(), 3)
            with mock.patch.object(al, "_fp_age_hours", return_value=9.0), \
                 mock.patch.object(al, "_probe_fail_streak", return_value=0), \
                 mock.patch.object(al, "_load_credentials", side_effect=AssertionError("should skip")), \
                 mock.patch.object(al.preempt_guard, "should_skip_preempt", return_value=(True, "忙")):
                with mock.patch.object(sys, "argv", ["auto_login.py", "--preempt"]):
                    self.assertEqual(al.main(), 0)


class CrossSideParityTests(unittest.TestCase):
    def _load_local_module(self, unique_name: str, rel_path: Path):
        local_root = ROOT.parent / "local"
        old_sys_path = list(sys.path)
        sys.path.insert(0, str(local_root))
        try:
            return _load_module(unique_name, local_root / rel_path)
        finally:
            sys.path[:] = old_sys_path

    def test_reply_classification_parity_with_local(self):
        local_reply = self._load_local_module(
            "local_signup_reply_ref", Path("domain/signup/signup_reply.py"),
        )
        samples = [
            (1, "ok"),
            ("1", "报名成功"),
            (4001, "未登录"),
            ("4001", "登录过期"),
            (500, "请登录后完成身份验证"),
            (500, "报名未开始！"),
            (500, "报名人数已满"),
            (500, "活动时间与已参与活动时间冲突"),
            (500, "报名已结束！"),
            (0, "版本不兼容，请升级"),
            (0, "请求已超时"),
            (0, "Cache 'hd-info' not found"),
            (500, "一条未见过的新文案"),
            (None, None),
        ]
        for code, msg in samples:
            srv = signup_reply.classify_signup_reply(code, msg)
            loc = local_reply.classify_signup_reply(code, msg)
            self.assertEqual((srv.kind, srv.label, srv.raw), (loc.kind, loc.label, loc.raw))
        self.assertEqual(signup_reply.UNKNOWN_REPLY_LIMIT, local_reply.UNKNOWN_REPLY_LIMIT)
        self.assertEqual(signup_reply.STALE_TS_LIMIT, local_reply.STALE_TS_LIMIT)
        self.assertEqual(signup_reply.TERMINAL_STOP_REASONS, local_reply.TERMINAL_STOP_REASONS)
        self.assertEqual(signup_reply.STOP_REASON_LABELS, local_reply.STOP_REASON_LABELS)

    def test_burst_policy_constants_parity_with_local(self):
        local_policy = self._load_local_module(
            "local_signup_policy_ref", Path("application/signup/signup_policy.py"),
        )
        names = (
            "GOLDEN_WINDOW_S",
            "GOLDEN_INTERVAL_S",
            "GOLDEN_ROUNDS",
            "FULL_SPEED_INTERVAL_S",
            "NOT_READY_404_LIMIT",
            "BACKOFF_FACTOR",
            "BACKOFF_MAX_S",
            "ADAPTIVE_WINDOW_S",
        )
        for attr in names:
            self.assertEqual(getattr(signup_policy, attr), getattr(local_policy, attr), attr)


class PageOpenFallbackTests(unittest.TestCase):
    def _fake_playwright(self, *, page_error=None):
        fake_page = mock.MagicMock()
        if page_error is not None:
            fake_page.goto.side_effect = page_error
        fake_ctx = mock.MagicMock()
        fake_ctx.new_page.return_value = fake_page
        fake_browser = mock.MagicMock()
        fake_browser.new_context.return_value = fake_ctx
        fake_pw = mock.MagicMock()
        fake_pw.chromium.launch.return_value = fake_browser
        cm = mock.MagicMock()
        cm.__enter__.return_value = fake_pw
        cm.__exit__.return_value = False
        return (lambda: cm), fake_page

    def _run_grab_browser(self, *, page_error, key_result, direct_result=("success", {})):
        grab = _load_module("server_grab_signup_r1", DEPLOY / "signup" / "grab_signup.py")
        pw_factory, fake_page = self._fake_playwright(page_error=page_error)
        args = types.SimpleNamespace(
            activity_id="act-1", at="2026-11-24 12:00:00", name="音乐节",
            lead=100.0, window=60.0, sign_end="", dry_run=False, rehearse=False,
        )
        cards, logs, click_calls = [], [], []

        def fake_direct(**kwargs):
            if direct_result == "call_fallback":
                st = {"attempts": 0, "pending": 0, "last_reason": "", "resp_ok": False,
                      "login_invalid": False, "retry_deadline": 1060.0, "streak_404": 0,
                      "backoff_s": 0.18, "phase": "golden", "round": 0,
                      "path": "click", "path_reason": "取不到运行时密钥"}
                burst = signup_policy.BurstPolicy(1000.0, 1060.0, clock=FakeClock(1000.0))
                return kwargs["click_fallback_fn"](burst, st)
            return direct_result

        with mock.patch.object(grab, "sync_playwright", pw_factory), \
             mock.patch.object(grab, "wait_until"), \
             mock.patch.object(grab, "is_joined", return_value=False), \
             mock.patch.object(grab, "log", side_effect=logs.append), \
             mock.patch.object(grab, "notify", side_effect=lambda t, l, tpl="green": cards.append((t, l, tpl)) or True), \
             mock.patch.object(grab, "_prepare_runtime_key", return_value=key_result), \
             mock.patch.object(grab._signup_direct, "run_direct_submit_loop", side_effect=fake_direct), \
             mock.patch.object(grab, "run_submit_loop", side_effect=lambda pg, **kw: (click_calls.append(pg), ("click_ok", kw["state"]))[1]):
            rc = grab._run_browser_signup(args, 1000.0, None)
        return rc, cards, logs, click_calls, fake_page

    def test_page_goto_timeout_still_runs_direct_and_succeeds(self):
        rc, _, logs, click_calls, _ = self._run_grab_browser(
            page_error=TimeoutError("page timeout"),
            key_result=(b"Abcdefgh12345678", "ok", False),
            direct_result=("success", {"path": "direct"}),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(click_calls, [])
        self.assertTrue(any("详情页加载失败" in line for line in logs))

    def test_page_not_open_when_downgrade_needed_ends_with_reason_without_click_loop(self):
        rc, cards, _, click_calls, _ = self._run_grab_browser(
            page_error=TimeoutError("page timeout"),
            key_result=(None, "http_500", False),
            direct_result="call_fallback",
        )
        self.assertEqual(rc, 2)
        self.assertEqual(click_calls, [])
        self.assertIn("页面没打开，没法点击兜底", "\n".join(cards[-1][1]))

    def test_page_open_normally_still_falls_back_to_click_loop(self):
        rc, _, _, click_calls, fake_page = self._run_grab_browser(
            page_error=None,
            key_result=(None, "http_500", False),
            direct_result="call_fallback",
        )
        self.assertEqual(rc, 2)
        self.assertEqual(click_calls, [fake_page])


class ReloginProcessGroupTests(unittest.TestCase):
    def test_relogin_passes_max_attempts_one_and_new_session(self):
        captured = {}

        class FakeProc:
            pid = 43210
            returncode = 0

            def communicate(self, timeout=None):
                captured["timeout"] = timeout
                return ("ok", "")

        def fake_popen(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env")
            captured["start_new_session"] = kwargs.get("start_new_session")
            return FakeProc()

        ok = signup_relogin.recover_session(
            old_token="tok-old", login_dir="/tmp/login", lock_file="/tmp/lock",
            token_fn=lambda: "tok-old", timeout_s=60.0,
            lock_busy_fn=lambda _p: False, popen_fn=fake_popen,
        )
        self.assertTrue(ok)
        self.assertEqual(captured["env"]["AUTO_LOGIN_MAX_ATTEMPTS"], "1")
        self.assertTrue(captured["start_new_session"])
        self.assertEqual(captured["timeout"], 60.0)

    def test_relogin_timeout_kills_process_group_and_returns_false(self):
        killed_pg, child_kills = [], []

        class SlowProc:
            pid = 54321
            returncode = None
            calls = 0

            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired("auto_login.py", timeout)
                return ("", "")

            def kill(self):
                child_kills.append(self.pid)

        ok = signup_relogin.recover_session(
            old_token="tok-old", login_dir="/tmp/login", lock_file="/tmp/lock",
            token_fn=lambda: "tok-old", timeout_s=60.0,
            lock_busy_fn=lambda _p: False,
            popen_fn=lambda *a, **kw: SlowProc(),
            getpgid_fn=lambda pid: pid + 100,
            killpg_fn=lambda pgid, sig: killed_pg.append((pgid, sig)),
        )
        self.assertFalse(ok)
        expected_sig = getattr(signal, "SIGKILL", signal.SIGTERM)
        self.assertEqual(killed_pg, [(54421, expected_sig)])
        self.assertEqual(child_kills, [])


class SignedJoinInfoTests(unittest.TestCase):
    def test_all_four_join_info_call_sites_send_gateway_sign_headers(self):
        grab = _load_module("server_grab_signup_r3", DEPLOY / "signup" / "grab_signup.py")
        captured_headers, sign_req_urls = [], []
        open_replies = iter([
            json.dumps({"code": 1, "data": None}),              # 1) pre-open is_joined -> False
            json.dumps({"code": 1, "data": None}),              # 2) pre-open 4001 recheck -> ok (not 4001)
            json.dumps({"code": 1, "data": {"id": "joined"}}),  # 3) conflict核对 -> True
            json.dumps({"code": 1, "data": {"id": "joined"}}),  # 4) closeout核对 -> True
        ])

        def fake_open(req, timeout):
            sign_req_urls.append(req.full_url)
            captured_headers.append({k.lower(): v for k, v in req.header_items()})
            return next(open_replies)

        clock = FakeClock(1000.0)
        with mock.patch.object(school_detail, "SITE_CONFIGURED", True), \
             mock.patch.object(school_detail, "_open", side_effect=fake_open), \
             mock.patch.object(grab, "_token", return_value="tok-r3"), \
             mock.patch.object(grab, "_fetch_key", side_effect=[(None, "4001"), (b"Abcdefgh12345678", "ok")]), \
             mock.patch.object(grab, "log"):
            self.assertFalse(grab.is_joined("act-1"))
            key, reason, aborted = grab._prepare_runtime_key("act-1", "音乐节")
            self.assertFalse(aborted)
            self.assertEqual(key, b"Abcdefgh12345678")
            opener_conflict = _SequenceOpener(lambda i, r: _FakeResponse({"code": 500, "message": "时间冲突"}))
            r_conf, _ = signup_direct.run_direct_submit_loop(
                activity_id="act-1", at_ts=1000.0, window_s=5.0, max_attempts=3,
                api_base="https://portal.school.example.edu/dr/api",
                referer="https://portal.school.example.edu/stu/", ua="UA",
                token_fn=lambda: "tok-r3", sign_headers_fn=lambda p, b: {},
                initial_key=key, is_joined_fn=grab.is_joined, log_fn=lambda m: None,
                clock=clock, opener=opener_conflict, sleep_fn=clock.sleep,
            )
            self.assertEqual(r_conf, "success")
            opener_closeout = _SequenceOpener(lambda i, r: _FakeResponse({"code": 500, "message": "报名未开始"}))
            r_close, _ = signup_direct.run_direct_submit_loop(
                activity_id="act-1", at_ts=1000.0, window_s=5.0, max_attempts=1,
                api_base="https://portal.school.example.edu/dr/api",
                referer="https://portal.school.example.edu/stu/", ua="UA",
                token_fn=lambda: "tok-r3", sign_headers_fn=lambda p, b: {},
                initial_key=key, is_joined_fn=grab.is_joined, log_fn=lambda m: None,
                clock=clock, opener=opener_closeout, sleep_fn=clock.sleep,
            )
            self.assertEqual(r_close, "success")

        self.assertEqual(len(captured_headers), 4)
        for url, hdrs in zip(sign_req_urls, captured_headers):
            self.assertIn("/rjyHdCyr/getJoinInfo/act-1", url)
            for key_name in ("x-page-ticket", "x-timestamp", "x-nonce", "x-token"):
                self.assertIn(key_name, hdrs)

    def test_recheck_only_explicit_4001_triggers_relogin_network_and_http_continue(self):
        logs, relogin_calls = [], []
        out_4001 = signup_relogin.handle_pre_open_4001(
            check_fn=lambda: signup_io.recheck_not_4001(
                "act-1", join_info_fn=lambda a, t: {"code": 4001},
                token_fn=lambda: "tok", log_fn=logs.append,
            ),
            recover_fn=lambda: (relogin_calls.append(1), True)[1],
            fetch_key_fn=lambda: (b"NewKey1234567890", "ok"),
            log_fn=logs.append, sleep_fn=lambda _s: None,
        )
        self.assertEqual(out_4001[0], "relogged")
        self.assertEqual(len(relogin_calls), 1)
        for err in (
            school_detail.SchoolNetworkError("Timeout"),
            school_detail.SchoolHTTPError(502, "bad gateway"),
            school_detail.SchoolPayloadError("not json"),
        ):
            out = signup_relogin.handle_pre_open_4001(
                check_fn=lambda e=err: signup_io.recheck_not_4001(
                    "act-1", join_info_fn=mock.Mock(side_effect=e),
                    token_fn=lambda: "tok", log_fn=logs.append,
                ),
                recover_fn=lambda: (relogin_calls.append(99), True)[1],
                fetch_key_fn=lambda: (b"Abcdefgh12345678", "ok"),
                log_fn=logs.append, sleep_fn=lambda _s: None,
            )
            self.assertEqual(out[0], "recovered")
        self.assertEqual(len(relogin_calls), 1)

    def test_is_joined_semantics_unchanged(self):
        self.assertTrue(signup_io.check_joined(
            "act-1", join_info_fn=lambda a, t: {"code": 1, "data": {"id": 1}}, token_fn=lambda: "t",
        ))
        for bad in (
            {"code": 1, "data": None},
            {"code": 1, "data": {}},
            {"code": 1, "data": []},
            {"code": 500, "data": {"id": 1}},
        ):
            self.assertFalse(signup_io.check_joined(
                "act-1", join_info_fn=lambda a, t, p=bad: p, token_fn=lambda: "t",
            ))
        self.assertFalse(signup_io.check_joined(
            "act-1", join_info_fn=mock.Mock(side_effect=RuntimeError("boom")), token_fn=lambda: "t",
        ))

    def test_rehearse_logs_signed_join_info_code_without_data(self):
        opener = _SequenceOpener(lambda i, r: _FakeResponse({"code": 1, "data": "Abcdefgh12345678"}))
        logs = []
        with mock.patch.object(school_detail, "SITE_CONFIGURED", True), \
             mock.patch.object(school_detail, "_open", return_value=json.dumps({
                 "code": 1, "data": {"secret_name": "SHOULD_NOT_APPEAR"},
             })):
            info = signup_direct.rehearse_direct(
                activity_id="act-1", api_base="https://portal.school.example.edu/dr/api",
                referer="https://portal.school.example.edu/stu/", ua="UA",
                token_fn=lambda: "tok-1", sign_headers_fn=lambda p, b: {"X-Test": "1"},
                join_info_fn=school_detail.get_join_info,
                now_fn=lambda: 1767225600.0, log_fn=logs.append, opener=opener,
            )
        joined_text = "\n".join(logs)
        self.assertEqual(info["join_info_code"], 1)
        self.assertIn("已报名查询：code=1", joined_text)
        self.assertNotIn("SHOULD_NOT_APPEAR", joined_text)
        self.assertFalse(any("signUp" in r["url"] for r in opener.requests))


if __name__ == "__main__":
    unittest.main()
