#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机受限访问用例测试：配对/会话/限速、动作白名单、事件缓冲与关闭收尾。

全部替身：假 Api、假时钟、假 server factory；不连学校、不读真实凭据、
不开 100.x 监听、不启真实浏览器。

@author Author
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.phone_service import PhoneAccessService  # noqa: E402
from domain.phone_rules import (  # noqa: E402
    COOKIE_NAME, CSRF_HEADER, DEVICE_COOKIE_NAME, DEVICE_TTL_S,
    EVENT_BUFFER_LIMIT, GLOBAL_FAIL_LIMIT,
    IP_FAIL_LIMIT, IP_LOCK_S, PAIR_TTL_S, SESSION_TTL_S,
    is_allowed_bind, project_state,
)


class FakeApi:
    """替身 Api：只记录调用，任何学校/进程动作都不会真发生。"""

    def __init__(self):
        self.calls = []
        self.plan_snapshot = {"plan_id": "p1", "tasks": []}
        self.saved_prefs = []
        self.fail = False

    def list_activities(self, request_id=""):
        self.calls.append(("list_activities", request_id))
        return {"ok": True, "items": [], "request_id": request_id}

    def check(self, request_id=""):
        self.calls.append(("check", request_id))
        return {"ok": True, "result": "valid", "request_id": request_id}

    def start_plan(self, items, headed=False, retry_policy=None, request_id=""):
        self.calls.append(("start_plan", items, headed, retry_policy, request_id))
        if self.fail:
            raise RuntimeError("boom")
        return {"ok": True, "plan_id": "p1", "request_id": request_id}

    def stop_plan(self, plan_id):
        self.calls.append(("stop_plan", plan_id))
        return {"ok": True}

    def cancel_task(self, plan_id, task_id):
        self.calls.append(("cancel_task", plan_id, task_id))
        return {"ok": True}

    def start_request_state(self, request_id):
        self.calls.append(("start_request_state", request_id))
        return {"ok": True}

    def cancel_start_request(self, request_id):
        self.calls.append(("cancel_start_request", request_id))
        return {"ok": True}

    def show_window(self):
        self.calls.append(("show_window",))
        return {"ok": True, "hidden": False}

    def save_prefs(self, prefs):
        self.calls.append(("save_prefs", prefs))
        self.saved_prefs.append(prefs)
        return {"ok": True}


class FakeServer:
    def __init__(self, host, port, service):
        self.host = host
        self.port = port
        self.service = service
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def address(self):
        return "http://%s:%d" % (self.host, self.port or 8765)


class PhoneServiceBase(unittest.TestCase):
    def setUp(self):
        self.api = FakeApi()
        self.clock = {"now": 1000.0}
        self.servers = []
        self.raw_state = {
            "activities": [{"id": "a1", "name": "活动", "token": "fake-token",
                            "password": "fake-pass", "path": "C:/secret"}],
            "login": {"hours_left": 3, "session_present": True,
                      "token": "fake-login-token"},
            "plan": {"plan_id": "p1"},
            "business_clock": {"state": "ready"},
            "retry_options": {"default": 120},
            "terms": {"version": "1", "accepted_version": "1"},
            "help": {"steps": [{"text": "路径 C:/x"}]},
            "update_check": {"installer_path": "C:/setup.exe"},
            "login_relay": {"ready": False},
        }

        def factory(host, port, service):
            server = FakeServer(host, port, service)
            self.servers.append(server)
            return server

        self.service = PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: self.raw_state, server_factory=factory)

    def tearDown(self):
        self.service.stop()


class ClockUnavailableTests(PhoneServiceBase):

    def test_pair_code_status_degrades_instead_of_raising(self):
        # 校时失败时面板每 5 秒就调一次这里，抛异常会让整个手机面板打不开
        def boom():
            raise RuntimeError("本轮没有可用的时间源响应")

        service = PhoneAccessService(
            api=self.api, now=boom, state_of=lambda: self.raw_state,
            server_factory=lambda host, port, svc: FakeServer(host, port, svc))
        self.addCleanup(service.stop)
        status = service.pair_code_status()
        self.assertEqual(status["reason"], "clock_unavailable")
        self.assertEqual(status["code"], "")
        self.assertEqual(status["expires_in"], 0)

    def test_clock_failure_claims_no_way_back(self):
        """时间源坏了就不能断言手机还连得上：那个判断会决定要不要把窗口藏起来。"""
        def boom():
            raise RuntimeError("本轮没有可用的时间源响应")

        service = PhoneAccessService(
            api=self.api, now=boom, state_of=lambda: self.raw_state,
            server_factory=lambda host, port, svc: FakeServer(host, port, svc))
        self.addCleanup(service.stop)
        self.assertIs(service.has_live_session(), False)


class ProjectionTests(PhoneServiceBase):
    def test_projection_strips_token_password_path(self):
        projected = project_state(self.raw_state)
        text = str(projected)
        self.assertNotIn("fake-token", text)
        self.assertNotIn("fake-pass", text)
        self.assertNotIn("fake-login-token", text)
        self.assertNotIn("C:/secret", text)
        self.assertNotIn("C:/setup.exe", text)
        self.assertIn("session_present", text, "登录结论要保留")
        self.assertEqual(projected["terms"]["accepted_version"], "1")

    def test_projection_drops_help_and_update_blocks(self):
        projected = project_state(self.raw_state)
        self.assertNotIn("help", projected)
        self.assertNotIn("update_check", projected)
        self.assertIn("retry_options", projected)

    def test_state_is_read_from_local_cache_only(self):
        """GET state 只读本机缓存：不调用任何学校/刷新动作。"""
        self.service.safe_state()
        self.assertEqual(self.api.calls, [],
                         "读状态不得触发学校流量或刷新")


class PairAndSessionTests(PhoneServiceBase):
    def test_default_not_running_and_no_socket(self):
        self.assertFalse(self.service.is_running())
        self.assertEqual(self.servers, [], "默认不得创建任何监听")
        self.assertEqual(self.service.current_pair_code(), "")

    def test_start_issues_pair_code_and_stop_revokes(self):
        result = self.service.start("127.0.0.1", 0)
        self.assertTrue(result["ok"])
        code = result["pair_code"]
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        redeemed = self.service.pair(code, ip="127.0.0.1")
        self.assertTrue(redeemed["ok"])
        self.assertIn("HttpOnly", redeemed["cookie"])
        self.assertIn("SameSite=Strict", redeemed["cookie"])
        self.assertNotIn("Secure", redeemed["cookie"])
        self.assertTrue(self.service.authenticate(redeemed["cookie"]))
        self.service.stop()
        self.assertIsNone(self.service.authenticate(redeemed["cookie"]),
                          "停服务必须撤销全部会话")
        self.assertTrue(self.servers[0].stopped)

    def test_pair_code_is_one_time(self):
        self.service.start("127.0.0.1", 0)
        code = self.service.current_pair_code()
        first = self.service.pair(code, ip="127.0.0.1")
        second = self.service.pair(code, ip="127.0.0.1")
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"], "一码一次：第二次兑换必须失败")

    def test_pair_code_status_reports_leftover_time_and_change_reason(self):
        """面板要能说清「码还剩多久」「为什么换了一张」，而不是只给一串数字。"""
        self.service.start("127.0.0.1", 0)
        first = self.service.pair_code_status()
        self.assertEqual(len(first["code"]), 6)
        self.assertEqual(first["reason"], "started")
        self.assertGreater(first["expires_in"], 0)
        self.assertLessEqual(first["expires_in"], int(PAIR_TTL_S))
        self.clock["now"] += PAIR_TTL_S + 1
        expired = self.service.pair_code_status()
        self.assertNotEqual(expired["code"], first["code"], "过期必须换新码")
        self.assertEqual(expired["seq"], first["seq"] + 1)
        self.assertEqual(expired["reason"], "expired")
        self.assertTrue(self.service.pair(expired["code"], ip="127.0.0.1")["ok"])
        paired = self.service.pair_code_status()
        self.assertEqual(paired["seq"], expired["seq"] + 1)
        self.assertEqual(paired["reason"], "paired")
        self.assertNotEqual(paired["code"], expired["code"], "兑换过就不能再用")


        self.service.start("127.0.0.1", 0)
        code = self.service.current_pair_code()
        results = []
        barrier = threading.Barrier(2)

        def redeem():
            barrier.wait()
            results.append(self.service.pair(code, ip="127.0.0.1")["ok"])

        threads = [threading.Thread(target=redeem) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(results.count(True), 1, "并发双兑换只能有一赢")

    def test_pair_code_expires_after_five_minutes(self):
        self.service.start("127.0.0.1", 0)
        code = self.service.current_pair_code()
        self.clock["now"] += PAIR_TTL_S + 1
        self.assertFalse(self.service.pair(code, ip="127.0.0.1")["ok"],
                         "5 分钟后配对码必须作废")
        fresh = self.service.current_pair_code()
        self.assertNotEqual(fresh, code, "过期后面板换一张新的一码一次")

    def test_three_failures_lock_ip_and_global_locks_across_ips(self):
        self.service.start("127.0.0.1", 0)
        for _ in range(IP_FAIL_LIMIT):
            result = self.service.pair("000000", ip="127.0.0.1")
        self.assertEqual(result["error"], "bad_code")
        locked = self.service.pair(self.service.current_pair_code(), ip="127.0.0.1")
        self.assertEqual(locked["error"], "locked", "单 IP 连错 3 次锁 60 秒")
        # 换 IP 也逃不过全局限速
        self.clock["now"] += IP_LOCK_S + 1
        for _ in range(GLOBAL_FAIL_LIMIT):
            self.service.pair("000000", ip="100.64.0.2")
        blocked = self.service.pair(self.service.current_pair_code(), ip="100.64.0.9")
        self.assertEqual(blocked["error"], "locked", "换 IP 也要被全局限速拦下")

    def test_session_expires_in_eight_hours_and_check_does_not_refresh(self):
        self.service.start("127.0.0.1", 0)
        redeemed = self.service.pair(self.service.current_pair_code(), ip="127.0.0.1")
        cookie = redeemed["cookie"]
        first = self.service.authenticate(cookie)
        self.assertIsNotNone(first)
        created = first["created_at"]
        self.clock["now"] += 60
        again = self.service.authenticate(cookie)
        self.assertIsNotNone(again)
        self.assertEqual(again["created_at"], created,
                         "校验不得刷新会话寿命")
        self.clock["now"] += SESSION_TTL_S
        self.assertIsNone(self.service.authenticate(cookie), "8 小时后必须失效")


class LiveSessionTests(PhoneServiceBase):
    """「还叫得回来吗」：隐藏窗口前唯一的凭据，只回答有没有，不给 token。"""

    def _pair(self):
        self.service.start("127.0.0.1", 0)
        return self.service.pair(self.service.current_pair_code(), ip="127.0.0.1")

    def test_fresh_service_has_no_live_session(self):
        self.assertIs(self.service.has_live_session(), False)

    def test_pairing_gives_a_way_back_until_it_expires(self):
        self._pair()
        self.assertIs(self.service.has_live_session(), True)
        # 边界是「<= 8 小时」，所以过期要往后多走一秒
        self.clock["now"] += SESSION_TTL_S + 1
        self.assertIs(self.service.has_live_session(), False,
                      "过期的会话不能当成「手机还连得上」")

    def test_stopping_the_service_revokes_the_way_back(self):
        self._pair()
        self.service.stop(revoke_devices=True)
        self.assertIs(self.service.has_live_session(), False)

    def test_answer_is_a_bare_boolean_never_a_token(self):
        self._pair()
        answer = self.service.has_live_session()
        self.assertIsInstance(answer, bool)
        self.assertNotIn("token", str(answer))


class DispatchWhitelistTests(PhoneServiceBase):
    def test_forbidden_actions_are_rejected(self):
        for action in ("shutdown", "open_data", "update", "check_update",
                       "save_prefs", "accept_terms", "bootstrap", "login",
                       "eval", "__class__"):
            with self.subTest(action=action):
                result = self.service.dispatch(action, {})
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], "action_not_allowed")
        self.assertEqual(self.api.calls, [], "禁止动作不得触达 Api")

    def test_extra_args_are_rejected(self):
        result = self.service.dispatch("check", {"request_id": "r1", "evil": "x"})
        self.assertEqual(result["error"], "args_not_allowed")
        self.assertEqual(self.api.calls, [])

    def test_show_window_is_allowed_without_arguments(self):
        """手机页「显示电脑窗口」：无参数动作，允许；带参数一律拒。"""
        ok = self.service.dispatch("show_window", {})
        self.assertTrue(ok["ok"], ok)
        self.assertEqual(self.api.calls[-1], ("show_window",))
        bad = self.service.dispatch("show_window", {"request_id": "r1"})
        self.assertEqual(bad["error"], "args_not_allowed")

    def test_save_retry_policy_only_allows_policy_keys(self):
        ok = self.service.dispatch(
            "save_retry_policy", {"retry_policy": {"retry_for_s": -1, "max_attempts": 3}})
        self.assertTrue(ok["ok"])
        self.assertEqual(self.api.saved_prefs,
                         [{"retry_policy": {"retry_for_s": -1, "max_attempts": 3}}])
        bad = self.service.dispatch(
            "save_retry_policy", {"retry_policy": {"terms_version": "9"}})
        self.assertEqual(bad["error"], "args_not_allowed")
        self.assertEqual(len(self.api.saved_prefs), 1)

    def test_start_plan_carries_only_whitelisted_shape(self):
        result = self.service.dispatch("start_plan", {
            "items": [{"id": "a1", "signed": True, "sign_end": "2026-01-01 00:00:00"}],
            "headed": True, "retry_policy": {"retry_for_s": 120},
            "request_id": "req-1"})
        self.assertTrue(result["ok"])
        name, items, headed, policy, rid = self.api.calls[0]
        self.assertEqual(name, "start_plan")
        self.assertEqual(items, [{"id": "a1"}], "客户端自报的 signed/时间不得带进计划")
        self.assertTrue(headed)
        self.assertEqual(policy, {"retry_for_s": 120})
        self.assertEqual(rid, "req-1")

    def test_internal_exception_returns_type_only(self):
        self.api.fail = True
        result = self.service.dispatch("start_plan", {"items": [{"id": "a1"}]})
        self.assertEqual(result["error"], "internal")
        self.assertNotIn("Traceback", str(result))
        self.assertIn("RuntimeError", result["text"])


class EventBufferTests(PhoneServiceBase):
    def test_state_projection_cannot_advance_cursor_past_unreturned_event(self):
        self.service.record_event("log", {"text": "first"})
        def state_with_new_event():
            self.service.record_event("log", {"text": "second"})
            return {}
        self.service._state_of = state_with_new_event
        first = self.service.safe_state(cursor=0)
        self.service._state_of = lambda: {}
        second = self.service.safe_state(cursor=first["seq"])
        self.assertEqual([event["payload"]["text"] for event in second["events"]], ["second"])

    def test_events_survive_without_window(self):
        """窗口为空也要能发布：_emit 只进缓冲，不回调任何客户端。"""
        self.service.record_event("log", {"text": "hello", "token": "fake"})
        payload = self.service.safe_state()
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0]["kind"], "log")
        self.assertNotIn("fake", str(payload["events"][0]))

    def test_event_buffer_is_bounded_to_400(self):
        for index in range(EVENT_BUFFER_LIMIT + 50):
            self.service.record_event("log", {"text": "line %d" % index})
        events = self.service.safe_state()["events"]
        self.assertEqual(len(events), EVENT_BUFFER_LIMIT)
        self.assertEqual(events[0]["payload"]["text"],
                         "line %d" % 50, "旧事件按序号淘汰，只留最近 400 条")

    def test_old_cursor_returns_reset_snapshot(self):
        for index in range(EVENT_BUFFER_LIMIT + 50):
            self.service.record_event("log", {"text": "line %d" % index})
        fresh = self.service.safe_state(cursor=EVENT_BUFFER_LIMIT + 50)
        self.assertFalse(fresh["reset"])
        self.assertEqual(fresh["events"], [], "cursor 等于最新序号时没有新事件")
        stale = self.service.safe_state(cursor=0)
        self.assertTrue(stale["reset"], "cursor 太旧必须整体重置，不漏中间状态")
        self.assertEqual(len(stale["events"]), EVENT_BUFFER_LIMIT)

    def test_incremental_cursor_returns_only_new(self):
        self.service.record_event("log", {"text": "one"})
        self.service.record_event("log", {"text": "two"})
        seen = self.service.safe_state(cursor=1)
        self.assertFalse(seen["reset"])
        self.assertEqual([e["payload"]["text"] for e in seen["events"]], ["two"])


class BindAndLifecycleTests(PhoneServiceBase):
    def test_only_loopback_or_tailscale_addresses_allowed(self):
        self.assertTrue(is_allowed_bind("127.0.0.1"))
        self.assertTrue(is_allowed_bind("localhost"))
        self.assertTrue(is_allowed_bind("100.64.1.2"))
        self.assertFalse(is_allowed_bind("0.0.0.0"))
        self.assertFalse(is_allowed_bind("192.168.1.5"))
        self.assertFalse(is_allowed_bind("10.1.2.3"))
        self.assertFalse(is_allowed_bind("8.8.8.8"))
        self.assertFalse(is_allowed_bind("::1"))
        self.assertFalse(is_allowed_bind(""))

    def test_start_rejects_public_bind(self):
        result = self.service.start("0.0.0.0", 0)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bind_not_allowed")
        self.assertEqual(self.servers, [])

    def test_stop_is_bounded_and_touches_only_own_server(self):
        self.service.start("127.0.0.1", 0)
        other = FakeServer("127.0.0.1", 1, self.service)
        result = self.service.stop()
        self.assertTrue(result["ok"])
        self.assertTrue(self.servers[0].stopped)
        self.assertFalse(other.stopped, "关闭不得影响别的进程/服务")
        self.assertFalse(self.service.is_running())


class PublicUrlServer(FakeServer):
    """带公网展示地址的假 server：行为对齐 PhoneHttpServer.address()。"""

    def __init__(self, host, port, service, public_host="", public_scheme="http"):
        super().__init__(host, port, service)
        self.public_host = str(public_host or host)
        self.public_scheme = "https" if str(public_scheme).lower() == "https" else "http"

    def set_public_host(self, public_host, scheme="http"):
        self.public_host = str(public_host)
        self.public_scheme = "https" if str(scheme).lower() == "https" else "http"

    def address(self):
        suffix = "" if self.public_scheme == "https" else ":%d" % (self.port or 8765)
        return "%s://%s%s" % (self.public_scheme, self.public_host, suffix)


class PublicUrlTests(unittest.TestCase):
    """远程通道展示地址：Tailscale 域名直用，Cloudflare 建隧道后切换。"""

    def setUp(self):
        self.api = FakeApi()
        self.clock = {"now": 1000.0}
        self.servers = []

        def factory(host, port, service, public_host="", public_scheme="http"):
            server = PublicUrlServer(host, port, service,
                                     public_host=public_host,
                                     public_scheme=public_scheme)
            self.servers.append(server)
            return server

        self.service = PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: {"activities": [], "busy": False},
            server_factory=factory)
        self.addCleanup(self.service.stop)

    def test_tailscale_public_host_is_used_in_address(self):
        result = self.service.start("100.64.0.9", 0,
                                    public_host="box.tailnet.ts.net")
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["address"], "http://box.tailnet.ts.net:8765")

    def test_set_public_url_switches_to_https_tunnel_host(self):
        self.service.start("127.0.0.1", 0)
        result = self.service.set_public_url(
            "https://neat-words.trycloudflare.com/some/path?q=1")
        self.assertTrue(result["ok"])
        self.assertEqual(result["address"], "https://neat-words.trycloudflare.com")
        self.assertEqual(self.servers[0].public_scheme, "https")

    def test_bad_public_url_and_host_are_rejected(self):
        self.service.start("127.0.0.1", 0)
        for bad in ("", "ftp://x.example", "https://", "not a url",
                    "javascript:alert(1)"):
            with self.subTest(bad=bad):
                self.assertFalse(self.service.set_public_url(bad)["ok"])
        self.assertFalse(self.service.set_public_host("")["ok"])

    def test_stop_clears_public_host(self):
        self.service.start("127.0.0.1", 0)
        self.service.set_public_url("https://x.trycloudflare.com")
        self.service.stop()
        self.assertEqual(self.service.address(), "")


class FakeDeviceStore:
    """替身设备信任存储：只记内存，不落盘、不碰 DPAPI。"""

    def __init__(self, valid=True):
        self.valid = valid
        self.devices = []
        self.validated = []
        self.revoked = 0
        self.fail = False

    def add_device(self, token, now=None):
        if self.fail:
            raise RuntimeError("boom")
        self.devices.append(token)
        return True

    def validate_device(self, token, now=None):
        self.validated.append(token)
        return self.valid and token in self.devices

    def revoke_all(self):
        self.revoked += 1
        self.devices = []
        return True


def _device_token(cookie_header) -> str:
    """从 Set-Cookie 文本里取设备 token（测试用，不认识别的键）。"""
    for part in str(cookie_header or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key == DEVICE_COOKIE_NAME:
            return value.strip()
    return ""


class DeviceTrustBase(PhoneServiceBase):
    def setUp(self):
        super().setUp()
        self.store = FakeDeviceStore()
        self.service = self._build(self.store)

    def _build(self, store):
        self.servers = []

        def factory(host, port, service):
            server = FakeServer(host, port, service)
            self.servers.append(server)
            return server

        return PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: self.raw_state, server_factory=factory,
            device_store=store)

    def _pair_persistent(self):
        started = self.service.start("100.64.0.9", 0, persistent_device=True)
        self.assertTrue(started["ok"], started)
        self.assertTrue(started["persistent_device"])
        redeemed = self.service.pair(self.service.current_pair_code(), ip="127.0.0.1")
        self.assertTrue(redeemed["ok"], redeemed)
        return redeemed


class DeviceTrustTests(DeviceTrustBase):
    def test_pair_persistence_cannot_restore_revoked_trust_after_stop(self):
        self.service.start("100.64.0.9", 0, persistent_device=True)
        code = self.service.current_pair_code()
        entered, release = threading.Event(), threading.Event()
        original = self.store.add_device
        def add(*args):
            entered.set()
            release.wait(2)
            return original(*args)
        with mock.patch.object(self.store, "add_device", side_effect=add):
            worker = threading.Thread(target=lambda: self.service.pair(code, ip="127.0.0.1"))
            worker.start()
            self.assertTrue(entered.wait(2))
            stopper = threading.Thread(target=self.service.stop)
            stopper.start()
            stopper.join(0.1)
            release.set()
            worker.join(3)
            stopper.join(3)
        self.assertEqual(self.store.devices, [])

    def test_inflight_restore_cannot_recreate_sessions_after_stop(self):
        redeemed = self._pair_persistent()
        device_cookie = redeemed["device_cookie"]
        entered, release = threading.Event(), threading.Event()
        def validate(*args):
            entered.set()
            release.wait(2)
            return True
        with mock.patch.object(self.store, "validate_device", side_effect=validate):
            worker = threading.Thread(target=lambda: self.service.authenticate_or_restore("", device_cookie))
            worker.start()
            self.assertTrue(entered.wait(2))
            stopper = threading.Thread(target=self.service.stop)
            stopper.start()
            stopper.join(0.1)
            release.set()
            worker.join(3)
            stopper.join(3)
        self.assertEqual(self.service._sessions, {})

    def test_tailscale_pair_issues_device_cookie(self):
        redeemed = self._pair_persistent()
        cookie = redeemed["device_cookie"]
        self.assertIn("%s=" % DEVICE_COOKIE_NAME, cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=%d" % DEVICE_TTL_S, cookie)
        self.assertEqual(self.store.devices, [_device_token(cookie)],
                         "存储里只该有 hash 由存储自己算，服务只交原始 token 一次")

    def test_cloudflare_pair_has_no_device_cookie(self):
        started = self.service.start("127.0.0.1", 0)
        self.assertTrue(started["ok"], started)
        self.assertFalse(started["persistent_device"], "非固定地址通道不得承诺免配对")
        redeemed = self.service.pair(self.service.current_pair_code(), ip="127.0.0.1")
        self.assertTrue(redeemed["ok"], redeemed)
        self.assertEqual(redeemed["device_cookie"], "")
        self.assertEqual(self.store.devices, [])

    def test_shutdown_preserves_device_trust_and_restores(self):
        redeemed = self._pair_persistent()
        token = _device_token(redeemed["device_cookie"])
        self.service.shutdown(preserve_devices=True)
        self.assertEqual(self.store.revoked, 0, "程序退出不得撤销设备信任")
        restarted = self._build(self.store)
        started = restarted.start("100.64.0.9", 0, persistent_device=True)
        self.assertTrue(started["ok"], started)
        try:
            session, headers = restarted.authenticate_or_restore("", redeemed["device_cookie"])
            self.assertIsNotNone(session, "配对过的手机重开工具后应直接可用")
            self.assertTrue(session["restored"])
            self.assertEqual(len(headers), 3, "会话 + CSRF + 设备续期三条 Set-Cookie")
            self.assertTrue(any(value.startswith("%s=" % COOKIE_NAME)
                                for _key, value in headers),
                            "恢复时必须回写新的会话 cookie")
            self.assertEqual([value for _key, value in headers
                              if value.startswith("%s=" % DEVICE_COOKIE_NAME)],
                             [redeemed["device_cookie"]],
                             "恢复时顺带给设备 cookie 续期")
        finally:
            restarted.shutdown(preserve_devices=True)

    def test_manual_stop_revokes_device_trust(self):
        redeemed = self._pair_persistent()
        self.service.stop()
        self.assertEqual(self.store.revoked, 1, "手动关闭手机访问必须撤销设备信任")
        restarted = self._build(self.store)
        restarted.start("100.64.0.9", 0, persistent_device=True)
        try:
            session, headers = restarted.authenticate_or_restore(
                "", redeemed["device_cookie"])
            self.assertIsNone(session)
            self.assertEqual(headers, [])
        finally:
            restarted.shutdown(preserve_devices=True)

    def test_restore_requires_persistent_channel(self):
        self.service.start("127.0.0.1", 0)
        session, headers = self.service.authenticate_or_restore(
            "", "%s=whatever; Path=/" % DEVICE_COOKIE_NAME)
        self.assertIsNone(session, "非 Tailscale 通道永不进恢复分支")
        self.assertEqual(headers, [])
        self.assertEqual(self.store.validated, [], "不该白读存储")

    def test_active_session_wins_without_new_cookies(self):
        redeemed = self._pair_persistent()
        session, headers = self.service.authenticate_or_restore(
            redeemed["cookie"], redeemed["device_cookie"])
        self.assertIsNotNone(session)
        self.assertNotIn("restored", session)
        self.assertEqual(headers, [], "活动会话有效时不得再签发新 cookie")

    def test_unknown_device_token_is_rejected(self):
        self._pair_persistent()
        session, headers = self.service.authenticate_or_restore(
            "", "%s=deadbeef; Path=/" % DEVICE_COOKIE_NAME)
        self.assertIsNone(session, "没登记过的设备不得换会话")

    def test_store_failure_does_not_break_pairing(self):
        self.store.fail = True
        redeemed = self._pair_persistent()
        self.assertEqual(redeemed["device_cookie"], "",
                         "落盘失败只影响免配对，配对本身必须成功")

    def test_restored_session_is_usable(self):
        redeemed = self._pair_persistent()
        self.service.shutdown(preserve_devices=True)
        restarted = self._build(self.store)
        restarted.start("100.64.0.9", 0, persistent_device=True)
        try:
            session, _headers = restarted.authenticate_or_restore(
                "", redeemed["device_cookie"])
            again = restarted.authenticate("%s=%s" % (COOKIE_NAME, session["token"]))
            self.assertIsNotNone(again, "恢复出来的会话必须是真会话")
            self.assertEqual(again["csrf"], session["csrf"])
        finally:
            restarted.shutdown(preserve_devices=True)
