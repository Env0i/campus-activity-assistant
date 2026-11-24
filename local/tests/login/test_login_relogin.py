#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_login_relogin.py（来源：test_auto_login_rules.py, test_auto_relogin.py, test_silent_relogin.py, test_relogin_busy_order.py, test_login_probe.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_auto_login_rules.py ====================
"""自动登录六态的纯规则测试。

Author
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from domain.login.login_rules import AUTO_LOGIN_STATES, auto_login_state


class AutoLoginStateTests(unittest.TestCase):
    def test_states_are_frozen_and_complete(self):
        self.assertEqual(AUTO_LOGIN_STATES,
                         ("idle", "running", "handoff", "backoff", "blocked", "manual"))

    def test_idle_when_session_is_valid_even_if_not_ready(self):
        self.assertEqual(auto_login_state(expired=False, ready=(False, "terms"),
                                          block="terms", relay={}, inflight=False,
                                          handoff=False, failures=0, retry_in_s=0),
                         {"auto_state": "idle", "auto_block": "", "auto_retry_in_s": None})

    def test_manual_live_flow_has_priority_over_expired(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "desktop"},
            inflight=True, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "manual")

    def test_handoff_has_priority_over_inflight(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "auto",
                                                              "mode": "manual"},
            inflight=True, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "handoff")

    def test_live_auto_flow_without_manual_mode_is_running(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": True, "origin": "auto",
                                                              "mode": "auto"},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "running")

    def test_blocked_copies_reason_and_only_exposes_block(self):
        result = auto_login_state(
            expired=True, ready=(False, "ocr_missing"), block="ocr_missing", relay={},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result,
                         {"auto_state": "blocked", "auto_block": "ocr_missing",
                          "auto_retry_in_s": None})

    def test_backoff_needs_positive_retry_and_running_when_due(self):
        backoff = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={}, inflight=False,
            handoff=False, failures=1, retry_in_s=7)
        due = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={}, inflight=False,
            handoff=False, failures=1, retry_in_s=0)
        self.assertEqual(backoff["auto_state"], "backoff")
        self.assertEqual(backoff["auto_retry_in_s"], 7)
        self.assertEqual(due, {"auto_state": "running", "auto_block": "", "auto_retry_in_s": None})


    def test_scheduler_handoff_flag_alone_is_backoff_when_relay_not_live(self):
        # 电脑那一场已结束（中继不在进行），调度器的 handoff 标记可能还没清：不算转人工
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": False}, inflight=False,
            handoff=True, failures=1, retry_in_s=60)
        self.assertEqual(result, {"auto_state": "backoff", "auto_block": "",
                                  "auto_retry_in_s": 60})

    def test_scheduler_handoff_flag_alone_with_inflight_is_running(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="", relay={"live": False}, inflight=True,
            handoff=True, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "running")

    def test_relay_own_handoff_flag_while_live_auto_is_handoff(self):
        result = auto_login_state(
            expired=True, ready=(True, ""), block="",
            relay={"live": True, "origin": "auto", "mode": "auto", "handoff": True},
            inflight=False, handoff=False, failures=0, retry_in_s=0)
        self.assertEqual(result["auto_state"], "handoff")

# ==================== 源自 test_auto_relogin.py ====================
"""自动恢复调度的假时钟与接线回归；不读取本机凭据。

@author Author
"""
import threading
import json
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from application.login.auto_relogin import AutoReloginMonitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.allowed = True
        self.checks = []
        self.starts = []
        self.flow = {"state": "idle"}
        self.monitor = AutoReloginMonitor(
            now=lambda: self.now, check=lambda: self.checks.append(self.now),
            start=self.begin, eligible=lambda: self.allowed, state=lambda: self.flow)
        self.addCleanup(self.monitor.stop)

    def begin(self):
        self.starts.append(self.now)
        self.flow = {"state": "starting", "flow_id": str(len(self.starts))}
        return {"ok": True, "flow_id": self.flow["flow_id"]}

    def test_worker_request_starts_relogin_right_away_even_in_backoff(self):
        # 决策 015：报名进程发来 login_wait，下一拍就自动登录，不等退避
        self.monitor.observe_check("expired")
        self.flow = {"state": "idle"}
        self.monitor._failures = 2
        self.monitor._retry_at = self.now + 900
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_worker_request_does_not_double_start_while_inflight(self):
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        self.monitor.request_recover()   # 第一轮还在跑
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_worker_request_respects_eligibility_gate(self):
        self.allowed = False
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(self.starts, [])

    def test_initial_wait_period_and_disabled_gate(self):
        self.monitor.tick()
        self.assertEqual(self.checks, [])
        self.now = 60
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.now = 120
        self.allowed = False
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.allowed = True
        self.monitor.tick()
        self.assertEqual(self.checks, [60, 120])

    def test_only_expired_starts_and_waiting_code_stays_inflight(self):
        for result in ("unknown", "network", "bad_clock", "none", "valid"):
            self.monitor.observe_check(result)
            self.monitor.tick()
        self.assertEqual(self.starts, [])
        self.monitor.observe_check("expired")
        self.monitor.tick()
        for phase in ("starting", "waiting_code", "verifying"):
            self.flow["state"] = phase
            self.now += 1000
            self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_a_takeover_by_another_source_is_not_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 手机端另开一场人工重登：中继换成了一条新的、还在跑的流程
        self.flow = {"state": "waiting_code", "flow_id": "phone-1", "live": True}
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["failures"], 0,
                         "人主动接手不是自动重登失败，不能累加失败次数")
        self.assertFalse(snapshot["inflight"], "槽位要放回去，别一直占着")

    def test_our_own_flow_vanishing_still_counts_as_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 中继里什么都没有了：这一轮确实没跑成
        self.flow = {"state": "idle", "flow_id": "", "live": False}
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 1)

    def test_backoff_cap_success_reset_and_clear_suppress(self):
        self.monitor.observe_check("expired")
        for wait in (60, 120, 300, 900, 900):
            self.monitor.tick()
            self.flow["state"] = "failed"
            self.monitor.tick()
            started = len(self.starts)
            self.now += wait - 1
            self.monitor.tick()
            self.assertEqual(len(self.starts), started)
            self.now += 1
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 0)
        started = len(self.starts)
        self.monitor.observe_check("expired")
        self.monitor.reset()
        self.allowed = False
        self.now += 5000
        self.monitor.tick()
        self.assertEqual(len(self.starts), started)

    def test_success_records_recent_use_without_sensitive_fields(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["last_used_method"], "auto_ocr")
        self.assertEqual(snapshot["last_used_ago_s"], 0)
        text = json.dumps(snapshot, ensure_ascii=False)
        for leaked in ("secret", "password", "token", "code"):
            self.assertNotIn(leaked, text)
        # 历史事实不被 reset 擦掉：界面要能解释「上次是谁完成的」
        self.now += 125
        self.monitor.reset()
        later = self.monitor.snapshot()
        self.assertEqual(later["last_used_method"], "auto_ocr")
        self.assertEqual(later["last_used_ago_s"], 125)

    def test_callbacks_can_reenter_and_concurrent_tick_is_singleflight(self):
        entered, release = threading.Event(), threading.Event()
        def begin():
            self.monitor.snapshot()
            entered.set()
            release.wait(2)
            return self.begin()
        self.monitor._start_relogin = begin
        self.monitor.observe_check("expired")
        thread = threading.Thread(target=self.monitor.tick)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.monitor.tick()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.starts), 1)

    def test_busy_start_is_not_a_failure_and_retries_next_beat(self):
        # R3：拉列表这类瞬时忙碌时发起会被拒，不能算一次失败，也不能进退避
        self.monitor._start_relogin = lambda: {"ok": False, "error": "busy"}
        self.monitor.observe_check("expired")
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["failures"], 0, "busy 不该累加失败次数")
        self.assertNotEqual(snapshot["state"], "backoff", "busy 不该进退避")
        self.assertEqual(snapshot["retry_in"], 0)
        started = []
        self.monitor._start_relogin = lambda: started.append(1) or {
            "ok": True, "flow_id": "f"}
        self.monitor.tick()
        self.assertEqual(started, [1], "下一拍就要重试，不白等 60 秒")

    def test_handoff_when_our_flow_turns_manual(self):
        # R4：自动发起的一场转人工后，界面要能读出来（不只是日志）
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertFalse(self.monitor.snapshot()["handoff"])
        self.flow = {"state": "waiting_code", "flow_id": "1", "live": True,
                     "mode": "manual"}
        self.monitor.tick()
        self.assertTrue(self.monitor.snapshot()["handoff"],
                        "转人工要给界面一个可读的信号")

    def test_stop_wakes_wait_and_prevents_more_work(self):
        self.monitor.start()
        self.monitor.stop()
        self.assertFalse(self.monitor._thread.is_alive())
        self.now = 1000
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(self.starts + self.checks, [])


class AutoLoginViewTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.flow = {"state": "idle"}
        self.ready_calls = []
        self.changes = []
        self.monitor = AutoReloginMonitor(
            now=lambda: self.now, check=lambda: None,
            start=self._start, eligible=lambda: True, state=self._state,
            ready=self._ready, on_change=self.changes.append)
        self.addCleanup(self.monitor.stop)

    def _state(self):
        with self.monitor._lock:
            return dict(self.flow)

    def _ready(self):
        with self.monitor._lock:
            self.ready_calls.append(self.now)
        return True, ""

    def _start(self):
        self.flow = {"state": "starting", "flow_id": "f"}
        return {"ok": True, "flow_id": "f"}

    def test_view_reports_backoff_and_decrements_remaining_seconds(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow = {"state": "failed", "flow_id": "f"}
        self.monitor.tick()
        self.assertEqual(self.monitor.view()["auto_state"], "backoff")
        self.assertEqual(self.monitor.view()["auto_retry_in_s"], 60)
        self.now = 10
        self.assertEqual(self.monitor.view()["auto_retry_in_s"], 50)

    def test_due_backoff_is_running(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow = {"state": "failed", "flow_id": "f"}
        self.monitor.tick()
        self.now = 60
        self.assertEqual(self.monitor.view()["auto_state"], "running")

    def test_handoff_is_reported(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow = {"state": "waiting_code", "flow_id": "f", "live": True,
                     "mode": "manual", "origin": "auto"}
        self.monitor.tick()
        self.assertEqual(self.monitor.view()["auto_state"], "handoff")

    def test_handoff_turns_into_backoff_once_the_relay_flow_ended(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow = {"state": "waiting_code", "flow_id": "f", "live": True,
                     "mode": "manual", "origin": "auto"}
        self.monitor.tick()
        self.assertEqual(self.monitor.view()["auto_state"], "handoff")
        self.flow = {"state": "failed", "flow_id": "f", "live": False}
        self.monitor.tick()
        view = self.monitor.view()
        self.assertEqual(view["auto_state"], "backoff")
        self.assertGreater(view["auto_retry_in_s"], 0)

    def test_ready_is_only_called_for_expired_view(self):
        self.assertEqual(self.monitor.view(expired=False)["auto_state"], "idle")
        self.assertEqual(self.ready_calls, [])
        self.monitor.view(expired=True)
        self.assertEqual(self.ready_calls, [0])

    def test_ready_error_becomes_blocked_unknown(self):
        self.monitor._ready = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        self.assertEqual(self.monitor.view(expired=True),
                         {"auto_state": "blocked", "auto_block": "unknown",
                          "auto_retry_in_s": None})

    def test_expired_argument_overrides_internal_flag(self):
        self.monitor.observe_check("expired")
        self.assertEqual(self.monitor.view(expired=False)["auto_state"], "idle")

    def test_notify_changes_once_per_state_not_per_countdown(self):
        self.monitor.observe_check("expired")
        self.monitor.notify_if_changed()
        self.monitor.notify_if_changed()
        self.assertEqual([item["auto_state"] for item in self.changes], ["running"])
        self.monitor.tick()
        self.flow = {"state": "failed", "flow_id": "f"}
        self.monitor.tick()
        self.monitor.notify_if_changed()
        self.now = 1
        self.monitor.notify_if_changed()
        self.now = 60
        self.monitor.notify_if_changed()
        self.assertEqual([item["auto_state"] for item in self.changes],
                         ["running", "backoff", "running"])

    def test_second_backoff_deadline_is_a_new_change(self):
        self.monitor.observe_check("expired")
        self.monitor.notify_if_changed()
        self.monitor.tick()
        self.flow = {"state": "failed", "flow_id": "f"}
        self.monitor.tick()
        self.monitor.notify_if_changed()
        self.monitor._retry_at = 120
        self.monitor.notify_if_changed()
        self.assertEqual([item["auto_state"] for item in self.changes], ["running", "backoff", "backoff"])

    def test_change_callback_errors_are_swallowed(self):
        self.monitor._on_change = lambda _view: (_ for _ in ()).throw(RuntimeError("boom"))
        self.monitor.observe_check("expired")
        self.monitor.notify_if_changed()

    def test_view_callbacks_can_take_monitor_lock_without_deadlock(self):
        result = []

        def run():
            result.append(self.monitor.view(expired=True))

        thread = threading.Thread(target=run)
        thread.start()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result[0]["auto_state"], "running")

    def test_run_notifies_after_each_tick(self):
        calls = []

        class StopAfterOneWait:
            def __init__(self):
                self.count = 0

            def wait(self, _seconds):
                self.count += 1
                return self.count > 1

            def set(self):
                pass

        self.monitor._stop = StopAfterOneWait()
        self.monitor.tick = lambda: calls.append("tick")
        self.monitor.notify_if_changed = lambda: calls.append("notify")
        self.monitor._run()
        self.assertEqual(calls, ["tick", "notify"])


class RelayRaceTests(unittest.TestCase):
    def test_spawn_reservation_and_old_finish_cannot_replace_new_flow(self):
        from application.login.login_relay_service import LoginRelayService
        from login.test_login_relay import FakeWorker
        entered, release = threading.Event(), threading.Event()
        workers = []
        def spawn(_args):
            worker = FakeWorker()
            workers.append(worker)
            entered.set()
            release.wait(2)
            return worker
        service = LoginRelayService(spawn=spawn, now=lambda: 0)
        self.addCleanup(service.shutdown)
        service.prepare("fictional", "fictional")
        answers = []
        thread = threading.Thread(target=lambda: answers.append(
            service.begin(worker_command=["fake"], origin="auto")))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(service.begin(worker_command=["fake"])["error"], "busy")
        finally:
            release.set()
            thread.join(3)
        old = service._flow
        self.assertEqual(service.cancel(origin="phone").get("skipped"), "foreign_origin")
        service.cancel()
        service.begin(worker_command=["fake"])
        current = service.state()["flow_id"]
        service._finish(old)
        service._handle_line(old, '[login] {"kind":"success","flow_id":"%s"}' % old["flow_id"])
        self.assertEqual(service.state()["flow_id"], current)


class PausedMonitorTests(unittest.TestCase):
    """保存的密码被学校拒绝过：自动登录暂停，不再拿同一份密码去试。"""

    def test_paused_monitor_never_starts(self):
        starts = []
        paused = {"value": True}
        monitor = AutoReloginMonitor(
            now=lambda: 0, check=lambda: None,
            start=lambda: starts.append(1) or {"ok": True, "flow_id": "f"},
            eligible=lambda: True, state=lambda: {"state": "idle"},
            paused=lambda: paused["value"])
        monitor.observe_check("expired")
        monitor.request_recover()
        monitor.tick()
        self.assertEqual(starts, [], "暂停时报名进程请求自动登录也不发起")
        self.assertEqual(monitor.snapshot()["state"], "paused")
        paused["value"] = False
        monitor.tick()
        self.assertEqual(starts, [1], "写入新密码解除暂停后恢复")


class LateWindowRuleTests(unittest.TestCase):
    """计划运行中「来不及重新登录」：提交中，或离开放不到 100 秒。"""

    def setUp(self):
        from domain.login import login_rules
        self.rules = login_rules
        self.opens = {"a": 1000.0, "b": 2000.0}

    def _late(self, tasks, now):
        return self.rules.relogin_too_late(tasks, now, lambda t: self.opens.get(t.get("id")))

    def test_window_is_100_seconds(self):
        self.assertEqual(self.rules.LATE_WINDOW_S, 100)
        waiting = [{"id": "a", "status": "waiting"}]
        self.assertFalse(self._late(waiting, 899), "离开放 101 秒还来得及")
        self.assertTrue(self._late(waiting, 900), "离开放正好 100 秒就来不及")
        self.assertTrue(self._late(waiting, 1005), "过了开放还在排队也来不及")

    def test_submitting_is_always_late(self):
        self.assertTrue(self._late([{"id": "b", "status": "submitting"}], 0))

    def test_finished_and_unknown_open_do_not_block(self):
        self.assertFalse(self._late([{"id": "a", "status": "success"},
                                     {"id": "x", "status": "waiting"}], 999))

    def test_mask_account_keeps_two_and_two(self):
        self.assertEqual(self.rules.mask_account("stu20990001"), "st****01")
        self.assertEqual(self.rules.mask_account("ab"), "a****")
        self.assertEqual(self.rules.mask_account(""), "")

# ==================== 源自 test_silent_relogin.py ====================
"""登录失效时的静默自动登录：立即发起、busy 不算失败、转人工提醒与事件日志。

四条回归（计划 20261111-silent-relogin）：
    R2 检查结论 expired 且电脑能自己登录时，check 事件带 recovering 并立即发起
    R3 发起时遇到「正在拉列表」这类瞬时忙碌不算失败，也不进 60 秒退避
    R4 自动发起的一场 OCR 连续认错到上限时转人工，并推出提醒状态
    R5 grab.log 的关键事件逐条落盘，且行里不含账号、密码、验证码

全部离线：学校请求、时钟、OCR、中继都用替身。创建 app.Api 的用例一律经
stop_auto_relogin_on_cleanup 收掉自动重登线程。

@author Author
"""
import tempfile
import time

TESTS = Path(__file__).resolve().parents[1]
LOCAL = TESTS.parent
for _path in (str(LOCAL), str(TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from fixtures.business_clock import TestWallClock  # noqa: E402
from infrastructure.clock.time_contract import configure_time_source  # noqa: E402

configure_time_source(time.time)

_FAKE_USER = "stu20990001"
_FAKE_PASSWORD = "P@ss-secret-value"
_FAKE_CODE = "AB12"


def _import_app():
    sys.path.insert(0, str(LOCAL))
    try:
        import app as local_app
    except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
        raise unittest.SkipTest("无法导入 local/app.py：%s" % exc)
    finally:
        sys.path.pop(0)
    return local_app


class _ApiCase(unittest.TestCase):
    """Api + 临时数据目录 + 可控的凭据/识别/条款替身。"""

    def setUp(self):
        self.local_app = _import_app()
        tmp = tempfile.TemporaryDirectory(prefix="campus-silent-relogin-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        self.root = root
        self.ocr = True
        self.creds = True
        self.bad = False
        for patcher in (
            mock.patch.object(self.local_app, "DEMO", False),
            mock.patch.object(self.local_app, "PREFS", root / "ui.json"),
            mock.patch.object(self.local_app, "DEVICE_FILE", root / "devices.json"),
            mock.patch.object(self.local_app, "DATA_DIR", root),
            mock.patch.object(self.local_app, "LOG_FILE", root / "grab.log"),
            mock.patch.object(self.local_app, "LOG_LOCK_FILE", root / "grab.log.lock"),
            mock.patch.object(self.local_app._advanced_features, "feature_ready",
                              lambda *a, **k: self.ocr),
            mock.patch.object(self.local_app._credential_store, "has_credentials",
                              lambda *a, **k: self.creds),
            mock.patch.object(self.local_app._credential_store, "is_bad",
                              lambda *a, **k: self.bad),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.api = stop_auto_relogin_on_cleanup(
            self, self.local_app.Api(clock=TestWallClock()))
        self.addCleanup(self.api.shutdown)
        self.api._terms_gate = lambda: None
        self.events = []
        self.api._emit = lambda kind, payload=None: self.events.append((kind, payload))
        self.api._push_login_expired = mock.Mock()

    # ---------- 辅助 ----------
    def _log_text(self):
        path = self.local_app.LOG_FILE
        return path.read_text(encoding="utf-8") if Path(path).exists() else ""

    def _payload(self, kind):
        found = [payload for name, payload in self.events if name == kind]
        self.assertTrue(found, "没有 %s 事件" % kind)
        return found[-1]

    def _expired_check(self):
        state = {"session_present": True, "session_expired": False,
                 "hours_left": 1.0, "saved_at": "2026-11-11 09:00:00",
                 "estimated_expires_at": None, "estimate_reason": "ok"}
        out = "[X] 4001 登录状态已失效\n请重新登录"
        with mock.patch.object(self.local_app, "login_state", lambda clock: state), \
                mock.patch.object(self.api, "_run",
                                  lambda *a, **k: {"code": 1, "out": out}):
            self.api._do_check()
        return self._payload("check")

    def _fake_relay(self, begin=None):
        relay = mock.Mock()
        relay.prepare.return_value = {"ok": True, "ready": True}
        relay.begin.return_value = dict(begin or {"ok": True, "flow_id": "f-auto"})
        if "flow_id" not in relay.begin.return_value:
            relay.begin.return_value["flow_id"] = "f-auto"
        relay.state.return_value = {"state": "starting", "flow_id": "f-auto",
                                    "live": True, "mode": "auto", "origin": "auto"}
        self.api._relay = relay
        return relay


class SilentCheckTests(_ApiCase):
    """R2：能自己登录时不再让用户看见「登录已失效」。"""

    def test_expired_check_is_silent_and_starts_recovery_right_away(self):
        recover = mock.Mock()
        self.api._auto_relogin.request_recover = recover
        payload = self._expired_check()
        self.assertEqual(payload["result"], "expired")
        self.assertTrue(payload.get("recovering"),
                        "判据为真时 check 载荷必须标成静默恢复")
        recover.assert_called_once()
        self.assertIn("login_expired_detected", self._log_text())
        self.assertIn("silent=true", self._log_text())

    def test_without_ocr_the_reminder_stays_and_recovery_is_not_requested(self):
        self.ocr = False
        recover = mock.Mock()
        self.api._auto_relogin.request_recover = recover
        payload = self._expired_check()
        self.assertFalse(payload.get("recovering"))
        self.assertEqual(payload.get("recover_block"), "ocr_missing",
                         "界面的失效提醒要能解释为什么没静默登录")
        recover.assert_not_called()
        self.assertIn("silent=false", self._log_text())

    def test_paused_password_blocks_silent_recovery(self):
        self.bad = True
        payload = self._expired_check()
        self.assertFalse(payload.get("recovering"))
        self.assertEqual(payload.get("recover_block"), "paused")

    def test_no_credentials_blocks_silent_recovery(self):
        self.creds = False
        payload = self._expired_check()
        self.assertFalse(payload.get("recovering"))
        self.assertEqual(payload.get("recover_block"), "no_credentials")

    def test_expired_after_silent_failure_restores_the_reminder(self):
        # 静默发起后失败：后台仍会退避重试，但界面要回到「登录已失效」
        self._fake_relay()
        self._expired_check()
        self.api._relay.state.return_value = {"state": "failed", "flow_id": "f-auto",
                                              "live": False, "mode": "auto",
                                              "origin": "auto", "safe_error": "timeout"}
        self.api._relay_finished()
        self.api._auto_relogin._failures = 1     # 调度线程已经把这次算成一次失败
        payload = self._expired_check()
        self.assertFalse(payload.get("recovering"),
                         "静默登录失败以后必须回到「登录已失效」")
        self.assertIn("auto_relogin_failed", self._log_text())


class AutoLoginFieldsTests(_ApiCase):
    def test_check_exposes_running_fields_and_keeps_legacy_recovering(self):
        self.api._auto_relogin._ready = lambda: (True, "")
        payload = self._expired_check()
        self.assertEqual(payload["auto_state"], "running")
        self.assertTrue(payload["recovering"])

    def test_check_exposes_block_reason(self):
        self.ocr = False
        payload = self._expired_check()
        self.assertEqual(payload["auto_state"], "blocked")
        self.assertEqual(payload["auto_block"], "ocr_missing")

    def test_valid_check_is_idle(self):
        state = {"session_present": True, "session_expired": False, "hours_left": 1.0,
                 "saved_at": "2026-11-11 09:00:00", "estimated_expires_at": None,
                 "estimate_reason": "ok"}
        with mock.patch.object(self.local_app, "login_state", lambda clock: state), \
                mock.patch.object(self.api, "_run", lambda *a, **k: {"code": 0, "out": ""}):
            self.api._do_check()
        self.assertEqual(self._payload("check")["auto_state"], "idle")

    def test_bootstrap_login_exposes_auto_fields(self):
        with mock.patch.object(self.local_app, "login_state", lambda clock: {
                "session_present": True, "session_expired": False, "hours_left": 1.0,
                "saved_at": None, "estimated_expires_at": None, "estimate_reason": "ok"}), \
                mock.patch.object(self.api, "_last_check", {"result": "valid"}):
            payload = self.api.bootstrap()
        self.assertEqual(payload["login"]["auto_state"], "idle")
        self.assertIn("auto_block", payload["login"])
        self.assertIn("auto_retry_in_s", payload["login"])

    def test_monitor_constructor_receives_callbacks_and_event_is_emitted(self):
        self.assertIsNotNone(self.api._auto_relogin._ready)
        self.assertIsNotNone(self.api._auto_relogin._on_change)
        self.api._auto_relogin.observe_check("expired")
        self.api._auto_relogin.notify_if_changed()
        self.assertEqual(self._payload("login_auto")["auto_state"], "running")


class BusyStartTests(_ApiCase):
    """R3：拉列表这类瞬时忙碌不算一次失败。"""

    def test_listing_neither_counts_a_failure_nor_backs_off(self):
        relay = self._fake_relay()
        with mock.patch.object(self.local_app._credential_store, "load",
                               lambda *a, **k: {"username": _FAKE_USER,
                                                "password": _FAKE_PASSWORD}):
            self.api._listing = True
            self.api._auto_relogin.observe_check("expired")
            self.api._auto_relogin.tick()
            snapshot = self.api._auto_relogin.snapshot()
            self.assertEqual(snapshot["failures"], 0, "busy 不该累加失败次数")
            self.assertNotEqual(snapshot["state"], "backoff", "busy 不该进退避")
            self.assertEqual(snapshot["retry_in"], 0)
            self.assertEqual(relay.begin.call_args_list, [])
            self.api._listing = False
            self.api._auto_relogin.tick()
            self.assertEqual(len(relay.begin.call_args_list), 1,
                             "拉列表一结束就该重试，不白等 60 秒")
        self.assertIn("auto_relogin_started", self._log_text())

    def test_start_answering_busy_is_logged_once_and_retried(self):
        # 资格判过之后才撞上忙碌（并发窗口）：发起返回 busy，同样不算失败
        self.api._auto_relogin._start_relogin = lambda: {"ok": False, "error": "busy"}
        self.api._auto_relogin.observe_check("expired")
        self.api._auto_relogin.tick()
        snapshot = self.api._auto_relogin.snapshot()
        self.assertEqual(snapshot["failures"], 0)
        self.assertEqual(snapshot["state"], "deferred")
        self.assertEqual(snapshot["retry_in"], 0)
        self.assertIn("auto_relogin_deferred", self._log_text())
        self.assertIn("cause=busy", self._log_text())
        started = []
        self.api._auto_relogin._start_relogin = lambda: started.append(1) or {
            "ok": True, "flow_id": "f"}
        self.api._auto_relogin.tick()
        self.assertEqual(started, [1], "下一拍必须重试")


class HandoffTests(unittest.TestCase):
    """R4：自动发起的一场 OCR 连认 3 次不对就转人工并推出提醒状态。"""

    def setUp(self):
        self.local_app = _import_app()
        from application.login.login_relay_service import LoginRelayService
        from login.test_login_relay import FakeWorker
        self.worker = FakeWorker()
        self.events = []
        self.logs = []
        # 认得对：让 OCR 一直提交，直到手动上限才转人工（认错那条路径单独测）
        self.service = LoginRelayService(
            spawn=lambda _args: self.worker, now=lambda: 0.0,
            emit=lambda kind, payload: self.events.append((kind, payload)),
            log=lambda event, **fields: self.logs.append((event, fields)),
            classify_captcha=lambda _image: "34AB", manual_after=3)
        self.addCleanup(self.service.shutdown)
        self.service.prepare("fictional", "fictional")
        self.started = self.service.begin(worker_command=["fake"], origin="auto")
        self.flow = self.service._flow

    def _challenge(self, number):
        line = "[login] " + json.dumps({
            "kind": "challenge", "flow_id": self.started["flow_id"],
            "challenge_id": "c%d" % number,
            "image": "data:image/png;base64,AAAA", "attempts": number})
        self.service._handle_line(self.flow, line)

    def test_three_wrong_reads_hand_over_and_push_the_state(self):
        for number in (1, 2, 3):
            self._challenge(number)
        snapshot = self.service.state()
        self.assertEqual(snapshot["mode"], "manual", "认满 3 次必须转人工")
        self.assertTrue(snapshot.get("handoff"), "转人工要能被界面认出来")
        self.assertIn(("auto_relogin_handoff", {"attempts": 3}), self.logs)
        self.assertTrue(any(payload.get("handoff") for kind, payload in self.events
                            if kind == "phone_relogin"),
                        "转人工时必须推一次状态")

    def test_each_ocr_attempt_is_logged_without_the_code(self):
        self.service._classify_captcha = lambda _image: ""
        self._challenge(1)
        self.assertEqual([event for event, _ in self.logs][:1],
                         ["auto_relogin_ocr_attempt"])
        self.assertEqual(self.logs[0][1].get("attempt"), 1)
        text = json.dumps(self.logs, ensure_ascii=False)
        self.assertNotIn(_FAKE_CODE, text)
        self.assertNotIn("fictional", text)


class AutoStartFailureEmitTests(_ApiCase):
    """F3：自动发起失败（非 busy）时要推一次中继状态，顶栏才会收起「自动登录中」。"""

    def test_failed_start_pushes_a_state_so_the_banner_can_clear(self):
        # 落点在 application.login.relogin_entry：Api 上只剩转发，替身要打在服务上
        with mock.patch.object(self.api._relogin_entry, "_begin_auto_relogin_once",
                               lambda: {"ok": False, "error": "needs_local_setup"}):
            result = self.api._begin_auto_relogin()
        self.assertFalse(result.get("ok"))
        pushed = [payload for name, payload in self.events if name == "phone_relogin"]
        self.assertEqual(len(pushed), 1, "发起失败要推且只推一次状态")
        self.assertIs(pushed[0].get("live"), False, "界面要据此收起「自动登录中」")
        self.assertIn("auto_relogin_start_failed", self._log_text())

    def test_busy_start_pushes_nothing(self):
        with mock.patch.object(self.api._relogin_entry, "_begin_auto_relogin_once",
                               lambda: {"ok": False, "error": "busy"}):
            self.api._begin_auto_relogin()
        pushed = [payload for name, payload in self.events if name == "phone_relogin"]
        self.assertEqual(pushed, [], "busy 不落盘、也不推状态")


class LogEventTests(_ApiCase):
    """R5：事件表逐项落盘，且不含账号、密码、验证码。"""

    def test_manual_relogin_events_are_written_without_credentials(self):
        relay = self._fake_relay(begin={"ok": True, "flow_id": "f-manual"})
        result = self.api.relogin_begin(_FAKE_USER, _FAKE_PASSWORD, False)
        self.assertTrue(result.get("ok"))
        relay.state.return_value = {"state": "failed", "flow_id": "f-manual",
                                    "live": False, "mode": "manual",
                                    "origin": "desktop", "safe_error": "bad_password"}
        self.api._relay_finished()
        text = self._log_text()
        self.assertIn("relogin_manual_started", text)
        self.assertIn("relogin_manual_result", text)
        self.assertIn("case=login", text)
        self.assertNotIn(_FAKE_USER, text)
        self.assertNotIn(_FAKE_PASSWORD, text)
        self.assertNotIn(_FAKE_CODE, text)

    def test_auto_success_and_backoff_are_written(self):
        self.api._auto_relogin_started_at = 0.0
        with mock.patch.object(self.api, "check", lambda *a, **k: None):
            self.api._anchor_login_success("auto_ocr")
        text = self._log_text()
        self.assertIn("auto_relogin_ok", text)
        self.assertIn("elapsed_s=", text)
        self.assertNotIn(_FAKE_USER, text)

    def test_monitor_backoff_is_written(self):
        logs = []
        self.api._auto_relogin._log = lambda event, **fields: logs.append(
            (event, fields))
        self.api._auto_relogin._paused = lambda: True
        self.api._auto_relogin.observe_check("expired")
        self.api._auto_relogin.tick()
        self.api._auto_relogin._paused = lambda: False
        self.api._auto_relogin._start_relogin = lambda: {"ok": False, "error": "timeout"}
        self.api._auto_relogin.tick()
        self.assertIn("auto_relogin_backoff", [event for event, _ in logs])
        fields = dict(logs)["auto_relogin_backoff"]
        self.assertEqual(fields.get("retry_in_s"), 60)

# ==================== 源自 test_relogin_busy_order.py ====================
"""U6 定性：验证码页点「改用浏览器登录」时，先等 relogin_cancel 返回再发 login。

relogin_cancel 与 login 两个桥接调用并发时，后端仍可能以忙碌拒绝：中继 worker 占着 Api._proc，
_is_busy_locked 看它；relogin_cancel 里 terminate 最多等 1 秒再按需强杀；pywebview 每次 js_api
调用各起一个线程，两次调用没有先后保证。前端已改为先等取消返回再登录
（local/ui/features/login/actions-relogin.js 的 closeRelogin().then(doLogin)），绕开了这个窗口。

后端 relogin_cancel 与 login 的并发竞态记为已知残留，留给重构步骤 2 的登录恢复一块；
并发顺序的修前失败原文见 .claude/results/20261113-prerefactor-fixes-red-output.txt。
本文件只保留「先取消后登录」一条：进程树用假的，terminate 期间进程还活着，terminate 返回时
才退，与 process_tree.ProcessTree 一致。不起真实进程、不联网、不读真实数据目录；
Api 经 stop_auto_relogin_on_cleanup 构造。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
LOCAL = TESTS.parent
for _path in (str(LOCAL), str(TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


configure_time_source(time.time)




class _Pipe:
    """中继 worker 的 stdin 替身：只收写入。"""

    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)

    def flush(self):
        pass


class _BlockingStdout:
    """stdout 替身：迭代时一直等到收尾，不产出任何行，中继的读线程就不会提前把这一场收掉。"""

    def __init__(self, stop: threading.Event):
        self._stop = stop

    def __iter__(self):
        self._stop.wait(10)
        return iter(())


class _FakeProc:
    """worker 进程替身：dead 置位之前 poll() 一直是 None。"""

    def __init__(self, stop: threading.Event):
        self.dead = threading.Event()
        self.stdin = _Pipe()
        self.stdout = _BlockingStdout(stop)
        self.pid = 4242
        self.returncode = None

    def poll(self):
        return 0 if self.dead.is_set() else None

    def wait(self, timeout=None):
        self.dead.wait(timeout)
        return 0


class _SlowDyingTree:
    """受管进程树替身。terminate() 期间进程还活着，等 exit_delay 之后才退并返回 True；
    ProcessTree.terminate 同样是「发出终止后等进程退（最多 1 秒），仍没退再强杀」，返回时进程已死。"""

    def __init__(self, stop: threading.Event, exit_delay: float):
        self.proc = _FakeProc(stop)
        self.exit_delay = exit_delay
        self.entered = threading.Event()
        self.closed = False

    def terminate(self):
        self.entered.set()
        time.sleep(self.exit_delay)
        self.proc.dead.set()
        return True

    def close(self):
        self.closed = True


class _PlainTree:
    """登录 worker 的替身：不用终止，只要能被登记为 _proc。"""

    def __init__(self, stop: threading.Event):
        self.proc = _FakeProc(stop)

    def terminate(self):
        self.proc.dead.set()
        return True

    def close(self):
        pass


class ReloginCancelThenBrowserLoginTests(unittest.TestCase):
    """从验证码页（中继 worker 在跑）切到浏览器登录。"""

    EXIT_DELAY = 0.6      # 假进程在 terminate 里多久才退

    def setUp(self):
        self.local_app = _import_app()
        tmp = tempfile.TemporaryDirectory(prefix="campus-relogin-busy-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        for patcher in (
            mock.patch.object(self.local_app, "DEMO", False),
            mock.patch.object(self.local_app, "PREFS", root / "ui.json"),
            mock.patch.object(self.local_app, "DEVICE_FILE", root / "devices.json"),
            mock.patch.object(self.local_app, "DATA_DIR", root),
            mock.patch.object(self.local_app, "LOG_FILE", root / "grab.log"),
            mock.patch.object(self.local_app, "LOG_LOCK_FILE", root / "grab.log.lock"),
            mock.patch.object(self.local_app, "worker_problem", lambda: ""),
            mock.patch.object(self.local_app, "worker_command", lambda *a: ["fake-worker"] + list(a)),
            mock.patch.object(self.local_app, "_env", lambda: {}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.api = stop_auto_relogin_on_cleanup(
            self, self.local_app.Api(clock=TestWallClock()))
        self.addCleanup(self.api.shutdown)
        self.api._terms_gate = lambda: None          # 条款门禁用替身：本用例只看忙碌判定
        self.api._emit = lambda *a, **k: None
        self.api._push_login_expired = mock.Mock()
        self.api._pump = lambda *a, **k: None        # 登录 worker 的输出泵用替身：不读真实管道
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.relay_tree = _SlowDyingTree(self.stop, self.EXIT_DELAY)
        self.login_tree = _PlainTree(self.stop)
        trees = iter([self.relay_tree, self.login_tree])
        patch = mock.patch.object(self.local_app, "spawn_owned", lambda *a, **k: next(trees))
        patch.start()
        self.addCleanup(patch.stop)

    def start_verification_page(self):
        """让中继 worker 活着：验证码页开着时的真实状态（_proc 被它占住）。"""
        self.api._relay.prepare("test-user", "test-pass")
        started = self.api._relay.begin(plan_active=False, worker_command=["fake-worker", "login"],
                                        manual=True, origin="desktop")
        self.assertTrue(started.get("ok"), started)
        self.assertTrue(self.api._is_busy(), "前提：中继 worker 占着忙碌位")
        return started["flow_id"]

    def test_cancel_returns_then_login_is_not_refused(self):
        """顺序 A：先取消，等 relogin_cancel 返回，再登录。返回时进程已退，login 必须放行。"""
        flow_id = self.start_verification_page()
        cancelled = self.api.relogin_cancel(flow_id)
        self.assertTrue(cancelled.get("ok"), cancelled)
        self.assertTrue(self.relay_tree.proc.dead.is_set(), "前提：terminate 返回时进程已退")
        result = self.api.login()
        self.assertTrue(result.get("ok"), "取消已返回，login 不该被忙碌拒绝：%r" % result)

# ==================== 源自 test_login_probe.py ====================
"""登录探测复查（决策 015）：单次 4001 先隔 LOGIN_RECHECK_S 复查一次，两次都是 4001 才判失效。"""

from unittest.mock import patch

LOCAL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LOCAL))
import grab  # noqa: E402


class _Budget:
    """够用的假预算：记录 sleep，不真的等。"""

    def __init__(self, remaining):
        self.remaining = remaining
        self.slept = []

    def remaining_s(self):
        return self.remaining

    def sleep(self, seconds, monotonic_now=None):
        self.slept.append(seconds)


class ProbeRecheckTests(unittest.TestCase):
    def _run(self, replies, budget=None, tokens=("tok-1",)):
        calls = []
        replies = list(replies)
        token_seq = list(tokens)

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            calls.append(tok)
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        def fake_token():
            return token_seq.pop(0) if len(token_seq) > 1 else token_seq[0]

        with patch.object(grab, "_post", fake_post), \
                patch.object(grab, "token", fake_token), \
                patch.object(grab, "log", lambda msg: None), \
                patch.object(grab.time, "sleep", lambda s: None):
            result = grab.probe_token(budget)
        return result, calls

    def test_two_4001_is_expired(self):
        (state, _), calls = self._run([{"code": 4001}, {"code": 4001}])
        self.assertEqual(state, "expired")
        self.assertEqual(len(calls), 2)

    def test_4001_then_ok_is_valid(self):
        (state, _), calls = self._run([{"code": 4001}, {"code": 1}])
        self.assertEqual(state, "valid")
        self.assertEqual(len(calls), 2)

    def test_4001_then_other_error_is_unknown(self):
        (state, _), _ = self._run([{"code": 4001}, {"code": -1, "message": "TimeoutError"}])
        self.assertEqual(state, "unknown", "复查不是 4001 就不能判失效")

    def test_recheck_reads_fresh_token(self):
        # 复查前别处刚重新登录：用新 token 复查
        (state, _), calls = self._run([{"code": 4001}, {"code": 1}], tokens=("old", "new"))
        self.assertEqual(state, "valid")
        self.assertEqual(calls, ["old", "new"])

    def test_tight_budget_judges_on_single_reply(self):
        budget = _Budget(remaining=grab.LOGIN_RECHECK_S)
        (state, _), calls = self._run([{"code": 4001}], budget=budget)
        self.assertEqual(state, "expired")
        self.assertEqual(len(calls), 1, "预算不够复查时只查一次")
        self.assertEqual(budget.slept, [])

    def test_budget_sleep_used_when_budget_given(self):
        budget = _Budget(remaining=30.0)
        (state, _), _ = self._run([{"code": 4001}, {"code": 1}], budget=budget)
        self.assertEqual(state, "valid")
        self.assertEqual(budget.slept, [grab.LOGIN_RECHECK_S])

    def test_first_ok_needs_no_recheck(self):
        (state, _), calls = self._run([{"code": 1}])
        self.assertEqual(state, "valid")
        self.assertEqual(len(calls), 1)

# ==================== 重登入口的纯规则（application.login.relogin_entry 的判断落点） ====================
"""搬进 application.login.relogin_entry 的四类判断：每条都在 domain/login/login_rules 上逐分支钉住。

入口服务只做端口调用，结论一律来自这些纯函数；纯函数不读墙钟、不拿锁、参数全显式。
"""

from domain.login.login_rules import (auto_relogin_blocked, late_relogin_answer,
                                manual_relogin_wanted, relogin_manual_case,
                                silent_relogin_state)


class AutoReloginBlockedTests(unittest.TestCase):
    """自动重登资格的第一段：忙碌位与进程占用，login_wait 只放行进程那一条。"""

    def test_each_busy_slot_blocks(self):
        for slot in ("closing", "advanced_busy", "checking", "listing", "cancelling"):
            with self.subTest(slot=slot):
                self.assertTrue(auto_relogin_blocked(**{slot: True}), slot)
        self.assertFalse(auto_relogin_blocked())

    def test_running_worker_or_plan_task_blocks(self):
        self.assertTrue(auto_relogin_blocked(proc_running=True))
        self.assertTrue(auto_relogin_blocked(plan_procs_running=True))
        self.assertFalse(auto_relogin_blocked(proc_running=False, plan_procs_running=False))

    def test_login_wait_lifts_only_the_running_process_block(self):
        self.assertFalse(auto_relogin_blocked(login_wait_pending=True, proc_running=True,
                                              plan_procs_running=True))
        self.assertTrue(auto_relogin_blocked(login_wait_pending=True, checking=True),
                        "login_wait 只放行「报名进程在跑」，其余忙碌位照旧挡")


class SilentReloginStateTests(unittest.TestCase):
    """静默恢复态：不能登录 / 转人工 / 失败过 / 正常。"""

    def test_not_ready_returns_the_reason(self):
        self.assertEqual(silent_relogin_state(ready=False, ready_reason="ocr_missing",
                                              relay={}, auto_failures=0),
                         (False, "ocr_missing"))
        self.assertEqual(silent_relogin_state(ready=False, ready_reason="",
                                              relay={}, auto_failures=0), (False, ""),
                         "没有原因时只回空串，不编一个词")

    def test_manual_flow_is_handoff(self):
        self.assertEqual(silent_relogin_state(ready=True, ready_reason="",
                                              relay={"live": True, "mode": "manual"},
                                              auto_failures=0), (False, "handoff"))

    def test_failures_mean_retry_pending(self):
        self.assertEqual(silent_relogin_state(ready=True, ready_reason="", relay={},
                                              auto_failures=2), (False, "retry_pending"))

    def test_ready_when_auto_flow_is_live_and_no_failures(self):
        self.assertEqual(silent_relogin_state(ready=True, ready_reason="",
                                              relay={"live": True, "mode": "auto"},
                                              auto_failures=0), (True, ""))


class ManualReloginWantedTests(unittest.TestCase):
    """验证码交给谁：没有识别、本场模式、本场认错次数、整轮失败次数。"""

    def test_no_ocr_always_goes_manual(self):
        self.assertTrue(manual_relogin_wanted(ocr_ready=False, relay={}, auto_failures=0,
                                              manual_after=3))

    def test_live_flow_mode_decides(self):
        self.assertFalse(manual_relogin_wanted(ocr_ready=True,
                                               relay={"live": True, "mode": "auto"},
                                               auto_failures=0, manual_after=3))
        self.assertTrue(manual_relogin_wanted(ocr_ready=True,
                                              relay={"live": True, "mode": "manual"},
                                              auto_failures=0, manual_after=3))

    def test_live_attempts_reach_the_threshold(self):
        self.assertTrue(manual_relogin_wanted(ocr_ready=True,
                                              relay={"live": True, "attempts": 3},
                                              auto_failures=0, manual_after=3))
        self.assertFalse(manual_relogin_wanted(ocr_ready=True,
                                               relay={"live": True, "attempts": 2},
                                               auto_failures=0, manual_after=3))

    def test_history_attempts_do_not_count(self):
        self.assertFalse(manual_relogin_wanted(ocr_ready=True,
                                               relay={"live": False, "attempts": 9},
                                               auto_failures=0, manual_after=3),
                         "上一场剩下的 attempts 不能把手机永久推进人工模式")

    def test_auto_failures_reach_the_threshold(self):
        self.assertTrue(manual_relogin_wanted(ocr_ready=True, relay={"live": False},
                                              auto_failures=3, manual_after=3))
        self.assertFalse(manual_relogin_wanted(ocr_ready=True, relay={"live": False},
                                               auto_failures=2, manual_after=3))


class ReloginManualCaseTests(unittest.TestCase):
    """日志与文案里的入口分类：没有账号 / 密码被拒 / 只是要输验证码。"""

    def test_three_cases(self):
        self.assertEqual(relogin_manual_case(has_credentials=False,
                                             credentials_bad=False), "login")
        self.assertEqual(relogin_manual_case(has_credentials=True,
                                             credentials_bad=True), "bad")
        self.assertEqual(relogin_manual_case(has_credentials=True,
                                             credentials_bad=False), "captcha")


class LateReloginAnswerTests(unittest.TestCase):
    """计划运行中「来得及吗」：没有计划、提交中、窗口内、窗口外、时钟不可用。"""

    NOW = 1_000_000.0

    def _epoch(self, task):
        """与生产同口径的开放时刻换算：入参是任务 dict，读不到返回 None。"""
        return {"2026-11-07 09:00:00": self.NOW + 30,
                "2026-11-08 09:00:00": self.NOW + 600}.get(str(task.get("sign_start") or ""))

    def test_no_plan_is_not_late(self):
        self.assertIsNone(late_relogin_answer(
            has_plan=False, tasks=[{"status": "submitting"}],
            now=self.NOW, open_epoch=self._epoch))

    def test_submitting_task_is_late(self):
        answer = late_relogin_answer(has_plan=True, tasks=[{"status": "submitting"}],
                                     now=self.NOW, open_epoch=self._epoch)
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["error"], "plan_late")
        self.assertIn("电脑能自动登录", answer["text"])

    def test_queued_task_inside_the_window_is_late(self):
        answer = late_relogin_answer(
            has_plan=True,
            tasks=[{"status": "queued", "sign_start": "2026-11-07 09:00:00"}],
            now=self.NOW, open_epoch=self._epoch)
        self.assertEqual(answer["error"], "plan_late")

    def test_queued_task_outside_the_window_is_fine(self):
        self.assertIsNone(late_relogin_answer(
            has_plan=True,
            tasks=[{"status": "queued", "sign_start": "2026-11-08 09:00:00"}],
            now=self.NOW, open_epoch=self._epoch))

    def test_missing_clock_is_late(self):
        answer = late_relogin_answer(has_plan=True, tasks=[], now=self.NOW,
                                     open_epoch=self._epoch, clock_unavailable=True)
        self.assertEqual(answer["error"], "plan_late",
                         "时钟读不出来按来不及处理，宁可等电脑自己登录")


if __name__ == "__main__":
    unittest.main()
