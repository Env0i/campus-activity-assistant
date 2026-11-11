# -*- coding: utf-8 -*-
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
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
LOCAL = TESTS.parent
for _path in (str(LOCAL), str(TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from fixtures.business_clock import TestWallClock  # noqa: E402
from time_contract import configure_time_source  # noqa: E402

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
        root = Path(tmp.name)
        self.root = root
        self.ocr = True
        self.creds = True
        self.bad = False
        for patch in (
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
            patch.start()
            self.addCleanup(patch.stop)
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
        from application.login_relay_service import LoginRelayService
        from test_login_relay import FakeWorker
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
        with mock.patch.object(self.api, "_begin_auto_relogin_once",
                               lambda: {"ok": False, "error": "needs_local_setup"}):
            result = self.api._begin_auto_relogin()
        self.assertFalse(result.get("ok"))
        pushed = [payload for name, payload in self.events if name == "phone_relogin"]
        self.assertEqual(len(pushed), 1, "发起失败要推且只推一次状态")
        self.assertIs(pushed[0].get("live"), False, "界面要据此收起「自动登录中」")
        self.assertIn("auto_relogin_start_failed", self._log_text())

    def test_busy_start_pushes_nothing(self):
        with mock.patch.object(self.api, "_begin_auto_relogin_once",
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


if __name__ == "__main__":
    unittest.main()
