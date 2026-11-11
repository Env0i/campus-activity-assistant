# -*- coding: utf-8 -*-
"""application 用例的内存替身测试：端口全注入，零文件/零进程/零网络。

覆盖：更新检查用例（fetch 端口）、check 事件整理（纯分类）、计划项归一化
（domain 纯策略经 application 边界暴露的形状）。

@author Author
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import json
import hashlib
import shutil
import zipfile
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application import login_service, update_service  # noqa: E402
from domain import plan_rules  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from signup_plan import TaskSpec  # noqa: E402


class FakeState:
    """UpdateState 协议的内存替身：只记字段与事件。"""

    def __init__(self, closing: bool = False):
        self._lock = threading.Lock()
        self._closing = closing
        self._updating = True
        self._update_result = {"state": "old"}
        self._update_installer = {"name": "stale.exe"}
        self._update_installer_path = str(Path(tempfile.gettempdir()) / "stale.exe")
        self._update_cancelled = False
        self.events = []

    def _emit(self, kind, payload):
        self.events.append((kind, payload))


class UpdateServiceTests(unittest.TestCase):
    def test_check_success_stores_installer_and_clears_old_download(self):
        state = FakeState()
        expected = {"state": "available", "latest_version": "1.2.0",
                    "installer": {"name": "a.exe"}}

        def fetch(current_version):
            self.assertEqual(current_version, "1.1.0")
            return expected

        update_service.run_check(state, "req-1", fetch=fetch,
                                 current_version="1.1.0", latest_url="https://x")
        self.assertEqual(state._update_result["request_id"], "req-1")
        self.assertEqual(state._update_installer["name"], "a.exe")
        self.assertEqual(state._update_installer_path, "", "旧产物必须作废")
        self.assertFalse(state._updating)
        self.assertEqual(state.events, [("update", state._update_result)])

    def test_check_crash_unlocks_and_reports_error_state(self):
        state = FakeState()

        def fetch(current_version):
            raise RuntimeError("boom")

        update_service.run_check(state, "req-2", fetch=fetch,
                                 current_version="1.1.0", latest_url="https://x")
        self.assertFalse(state._updating)
        self.assertEqual(state._update_result["state"], "error")
        self.assertEqual(state._update_result["error_code"], "unexpected_error")
        self.assertEqual(state._update_result["request_id"], "req-2")

    def test_closing_suppresses_update_event(self):
        state = FakeState(closing=True)
        update_service.run_check(state, "req-3", fetch=lambda v: {"state": "current"},
                                 current_version="1.1.0", latest_url="https://x")
        self.assertEqual(state.events, [], "关闭中不推事件（终态仍留档）")
        self.assertEqual(state._update_result["state"], "current")


class LoginServiceTests(unittest.TestCase):
    def test_build_check_event_carries_frozen_fields(self):
        state = {"session_present": True, "session_expired": False,
                 "hours_left": 12.5, "saved_at": "2026-10-29 08:00:00",
                 "estimated_expires_at": 1793016000.0}
        result, clock, payload = login_service.build_check_event(
            state, 1, "[X] 登录态已失效 code:4001\n请重新登录", "")
        self.assertEqual(result, "expired")
        self.assertEqual(payload["hint"], "login")
        self.assertEqual(payload["hours_left"], 12.5)
        self.assertTrue(payload["session_present"])
        self.assertFalse(payload["session_expired"])
        self.assertEqual(payload["clock"]["state"], "unknown")

    def test_done_result_login_only_needs_exit_code(self):
        self.assertEqual(login_service.done_result("login", 0, ["无关行"]), (True, ""))
        ok, reason = login_service.done_result("login", 3, ["[X] 没登录"])
        self.assertFalse(ok)
        self.assertEqual(reason, "没登录")


class PlanRulesTests(unittest.TestCase):
    def test_normalize_rejects_duplicate_ids(self):
        items = [{"id": "a1"}, {"id": "a1"}]
        normalized, error = plan_rules.normalize_plan_items(items, {"a1": {"id": "a1"}}, 0)
        self.assertIsNone(normalized)
        self.assertEqual(error["errors"][0]["kind"], "duplicate_id")

    def test_merge_keeps_local_confirm_within_window(self):
        prev = {"a1": {"signed": True, "signed_source": "plan_success",
                       "signed_confirmed_at": 100.0}}
        merged = plan_rules.merge_list_activities(
            [{"id": "a1", "signed": False}], prev, now=160.0, window_s=120.0)
        self.assertTrue(merged[0]["signed"])
        self.assertTrue(merged[0]["sync_pending"])

    def test_merge_drops_local_confirm_after_window(self):
        prev = {"a1": {"signed": True, "signed_source": "plan_success",
                       "signed_confirmed_at": 100.0}}
        merged = plan_rules.merge_list_activities(
            [{"id": "a1", "signed": False}], prev, now=300.0, window_s=120.0)
        self.assertFalse(merged[0]["signed"])

    def test_fallback_exit_without_done_line_keeps_attempts_seen(self):
        """worker 无终态行自然退出：进度行已见的提交次数必须保留（不归零）。

        与取消分支、supervised 分支同一口径：发过几次就如实记几次，
        界面的「已提交 N 次」不得在收尾时消失。
        """
        spec = TaskSpec("t1", "a1", "测试活动", "2026-10-25 10:00:00",
                        "2026-10-25 12:00:00", "2026-10-25 13:00:00")
        result = plan_rules.classify_task_stop(
            spec, 2, ["[i] 第 1 次提交：已发起", "[i] 第 2 次提交：已发起",
                      "[X] 没抢到：名额已满"],
            canceled=False, supervised_fired=False, stop={}, attempts_seen=2,
            epoch_of=lambda text: 0.0)
        self.assertEqual(result["attempts"], 2)


class FakePhoneService:
    """手机监听的内存替身：只记「用什么参数开、用什么语义关」。"""

    def __init__(self):
        self.start_calls = []
        self.stop_calls = []
        self.running = False
        self.live = False
        self.paired = 0

    def paired_count(self):
        return self.paired

    def has_live_session(self):
        return self.live

    def start(self, host="127.0.0.1", port=0, public_host="", public_scheme="http",
              persistent_device=False):
        self.start_calls.append({"host": host, "public_host": public_host,
                                 "persistent_device": persistent_device})
        self.running = True
        return {"ok": True, "address": "http://%s:8765/" % host}

    def is_running(self):
        return self.running

    def address(self):
        return "http://100.64.0.9:8765/" if self.running else ""

    def current_pair_code(self):
        return "123456" if self.running else ""

    def pair_code_status(self):
        return {"code": self.current_pair_code(), "expires_in": 300,
                "seq": 1, "reason": "started"}

    def record_event(self, kind, payload):
        self.events = getattr(self, "events", [])
        self.events.append((kind, payload))

    def stop(self, revoke_devices=True):
        self.stop_calls.append({"revoke_devices": revoke_devices})
        self.running = False
        return {"ok": True}

    def shutdown(self, preserve_devices=True):
        self.stop_calls.append({"preserve_devices": preserve_devices})
        self.running = False
        return {"ok": True}

    def set_public_url(self, url=""):
        self.public_url = str(url or "")


class FakeCloudflareTunnel:
    """CloudflareTunnel 的内存替身：exited 只报一次，之后只能读到 stopped。

    真实的 status() 读到已经退出的子进程后就把句柄和地址清掉，下一次只剩 stopped；
    替身照抄这个语义，测试才能证明「退出提示得自己存下来」。
    """

    def __init__(self, executable="C:/pkg/bin/cloudflared.exe", state="stopped",
                 public_url="https://old.trycloudflare.com"):
        self.executable = executable
        self.state = state
        self.public_url = public_url
        self.status_calls = 0
        self.stop_calls = 0
        self.start_calls = []
        self.start_result = {"ok": True, "url": "https://fresh.trycloudflare.com"}
        # H1：非 None 时 stop() 按它返回（模拟进程停不下来），状态与地址保持不变
        self.stop_result = None

    def status(self):
        self.status_calls += 1
        if self.state == "exited":
            self.state = "stopped"
            self.public_url = ""
            return {"running": False, "public_url": "", "state": "exited",
                    "error": "tunnel_exited",
                    "text": "Cloudflare 隧道已退出，重新开启会得到新地址。",
                    "temporary": True, "restart_requires_pairing": True}
        if self.state == "running":
            return {"running": True, "public_url": self.public_url,
                    "state": "running", "temporary": True,
                    "restart_requires_pairing": True}
        return {"running": False, "public_url": "", "state": "stopped",
                "temporary": True, "restart_requires_pairing": True}

    def start(self, local_url, timeout_s=20.0):
        self.start_calls.append(str(local_url))
        if not self.executable:
            return {"ok": False, "error": "cloudflared_missing"}
        self.state = "running"
        self.public_url = str(self.start_result.get("url") or "")
        return dict(self.start_result)

    def stop(self):
        self.stop_calls += 1
        if self.stop_result is not None:
            return dict(self.stop_result)
        self.state = "stopped"
        self.public_url = ""
        return {"ok": True}


class PhoneChannelPreferenceTests(unittest.TestCase):
    """通道偏好 × 探测结果矩阵：只恢复 Tailscale，绝不自动开 Cloudflare。"""

    def setUp(self):
        import json
        import shutil
        import tempfile
        from unittest import mock

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        self.json = json
        tmp = tempfile.mkdtemp(prefix="campus-phone-prefs-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.prefs_path = Path(tmp) / "ui.json"
        for patch in (
            mock.patch.object(local_app, "PREFS", self.prefs_path),
            mock.patch.object(local_app, "DEMO", True),
            mock.patch.object(local_app, "DEVICE_FILE", Path(tmp) / "devices.json"),
            # 功能是否已安装不是本类要测的边界，按已安装处理
            mock.patch.object(local_app._advanced_features, "feature_ready",
                              lambda *a, **k: True),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()

    def _connect_tailscale(self, *, available=True, error="", state="connected"):
        from unittest import mock

        self.api._endpoint = {"available": available, "error": error, "state": state,
                              "bind_host": "100.64.0.9" if available else "",
                              "addresses": ["100.64.0.9"] if available else [],
                              "magicdns": "pc.tail.ts.net" if available else "",
                              "public_host": "pc.tail.ts.net" if available else "",
                              "text": "已找到 Tailscale 远程地址" if available else "没装"}
        patch = mock.patch.object(self.local_app._tunnel_manager, "tailscale_endpoint",
                                  lambda *a, **k: dict(self.api._endpoint))
        patch.start()
        self.addCleanup(patch.stop)

    def _prefs_block(self):
        data = self.json.loads(self.prefs_path.read_text(encoding="utf-8"))
        return data.get("phone_access", {})

    # ---------- 关窗三选 ----------
    def test_close_action_defaults_to_ask(self):
        resolve = self.local_app.resolve_close_action
        self.assertEqual(resolve({}, False), "ask")
        self.assertEqual(resolve({"window": {"close_action": "minimize"}}, False), "minimize")
        self.assertEqual(resolve({"window": {"close_action": "exit"}}, False), "exit")
        self.assertEqual(resolve({"window": {"close_action": "hide"}}, False), "hide")
        # 脏值按 ask，不要照着一个不认识的词去关窗
        self.assertEqual(resolve({"window": {"close_action": "nuke"}}, False), "ask")
        self.assertEqual(resolve({"window": "broken"}, False), "ask")
        # 计划在跑时必须先问，哪怕用户勾过「以后都这样」
        self.assertEqual(resolve({"window": {"close_action": "exit"}}, True), "ask")

    def test_plan_active_for_close_tracks_running_plan(self):
        class _Plan:
            def __init__(self, status):
                self.status = status

            def published_status(self):
                return self.status

        self.assertFalse(self.api.plan_active_for_close())
        self.api._plan = _Plan("running")
        self.assertTrue(self.api.plan_active_for_close())
        self.api._plan = _Plan("ready")
        self.assertTrue(self.api.plan_active_for_close())
        self.api._plan = _Plan("done")
        self.assertFalse(self.api.plan_active_for_close())

    def test_request_close_rejects_unknown_action(self):
        result = self.api.request_window_close("launch_missiles")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bad_action")

    def test_request_close_remembers_choice_and_minimizes(self):
        window = mock.Mock()
        window.minimize = mock.Mock()
        window.destroy = mock.Mock()
        self.api._window = window
        result = self.api.request_window_close("remember_minimize")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["remembered"])
        window.minimize.assert_called_once()
        window.destroy.assert_not_called()
        self.assertEqual(self.json.loads(self.prefs_path.read_text(encoding="utf-8"))
                         ["window"]["close_action"], "minimize")
        # 记住之后：下一次点 X 直接最小化，不再问
        self.assertEqual(self.local_app.resolve_close_action(
            self.local_app.load_prefs(), False), "minimize")

    def test_request_close_remembers_hide_and_keeps_running(self):
        """「隐藏到后台」：窗口 hide 掉、记住偏好、绝不 destroy（进程要继续跑）。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        window.minimize = mock.Mock()
        window.destroy = mock.Mock()
        self.api._window = window
        # 托盘建不起来也不能算保存失败：手机页还连着，照样能从手机叫回界面
        self.api._ensure_tray = lambda: False
        self.api._phone.live = True
        result = self.api.request_window_close("remember_hide")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["remembered"])
        self.assertTrue(result.get("hidden"))
        self.assertFalse(result.get("tray"), "托盘没建起来要如实告诉界面")
        window.hide.assert_called_once()
        window.destroy.assert_not_called()
        window.minimize.assert_not_called()
        self.assertTrue(self.api._close_approved is False,
                        "隐藏不是退出，关闭标记必须保持 False")
        self.assertEqual(self.json.loads(self.prefs_path.read_text(encoding="utf-8"))
                         ["window"]["close_action"], "hide")
        # 记住之后：下一次点 X 直接隐藏，不再问
        self.assertEqual(self.local_app.resolve_close_action(
            self.local_app.load_prefs(), False), "hide")

    def test_hide_is_refused_when_nothing_can_call_the_window_back(self):
        """托盘没有、手机也没连着：藏起来就再也叫不回来，宁可不藏。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: False
        self.api._phone.live = False
        result = self.api.hide_window()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "hide_unavailable")
        window.hide.assert_not_called()
        self.assertNotIn("hidden", result, "没隐藏就不要回一个「已隐藏」的字段")

    def test_remembered_hide_is_refused_the_same_way(self):
        """记住偏好只省一次询问，不改「能不能藏」：门禁照样先过。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: False
        result = self.api.request_window_close("remember_hide")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "hide_unavailable")
        window.hide.assert_not_called()
        self.assertFalse(self.api._close_approved, "拒绝隐藏不是退出")
        self.assertFalse(self.prefs_path.exists(),
                         "隐藏没成功就不能把「以后都隐藏」写进偏好")

    def test_refused_hide_keeps_the_previous_preference(self):
        """用户本来记的是最小化：这次隐藏被拒，不能顺手把偏好改成 hide。"""
        self.prefs_path.write_text(
            self.json.dumps({"window": {"close_action": "minimize"}}),
            encoding="utf-8")
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: False
        result = self.api.request_window_close("remember_hide")
        self.assertFalse(result["ok"], result)
        self.assertEqual(self._prefs_block_window().get("close_action"), "minimize")

    def test_hide_succeeds_even_when_the_preference_cannot_be_saved(self):
        """已经藏起来了就别再翻回来：只是这次没记住，要说清楚。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: True
        with mock.patch.object(self.local_app, "update_prefs", lambda *a, **k: False):
            result = self.api.request_window_close("remember_hide")
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["hidden"])
        self.assertFalse(result["remembered"], "没写成功就不能说记住了")
        self.assertTrue(result["text"], "要告诉用户这次没记住")
        window.hide.assert_called_once()

    def _prefs_block_window(self):
        """只读 window 段；文件不存在时返回空 dict。"""
        if not self.prefs_path.exists():
            return {}
        data = self.json.loads(self.prefs_path.read_text(encoding="utf-8"))
        return data.get("window", {})

    def test_tray_alone_is_enough_to_hide(self):
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: True
        self.api._phone.live = False
        result = self.api.hide_window()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["hidden"])
        window.hide.assert_called_once()

    def test_request_close_exit_marks_approved_before_destroy(self):
        seen = {}
        api = self.api

        class _Window:
            def minimize(self):
                raise AssertionError("exit 不该走最小化")

            def destroy(self):
                seen["approved"] = api._close_approved

        self.api._window = _Window()
        result = self.api.request_window_close("exit")
        self.assertTrue(result["ok"], result)
        self.assertTrue(seen.get("approved"), "必须先把关闭标记置位，closing 才会放行")

    def test_ask_window_close_pushes_the_dialog_event(self):
        events = []
        self.api._emit = lambda kind, payload: events.append((kind, dict(payload)))
        result = self.api.ask_window_close()
        self.assertTrue(result["ok"])
        self.assertEqual(events[0][0], "window_close_ask")
        self.assertEqual(events[0][1]["default_action"], "ask")

    # ---------- 关窗问询的计划负担（BE1）与隐藏通知（BE2，c3-dialogs-gap） ----------
    class _PlanStub:
        """PlanCoordinator 的只读替身：_close_plan_burden 只读 snapshot()，不新造状态。"""

        def __init__(self, tasks):
            self.tasks = tasks

        def snapshot(self):
            return {"plan_id": "p-stub", "status": "running", "tasks": self.tasks}

    def test_close_burden_counts_waiting_and_formats_next_batch(self):
        """BE1：waiting_count 只数 queued/waiting；next_batch_at 是最近一批的北京时间 HH:MM:SS。"""
        self.api._plan = self._PlanStub([
            {"task_id": "t1", "status": "waiting", "sign_start": "2026-11-08 14:30:00"},
            {"task_id": "t2", "status": "queued", "sign_start": "2026-11-09 09:00:00"},
            {"task_id": "t3", "status": "success", "sign_start": "2026-11-08 10:00:00"},
            {"task_id": "t4", "status": "submitting", "sign_start": "2026-11-08 10:00:00"},
        ])
        with mock.patch.object(self.api, "_clock_ready", lambda: True):
            burden = self.api._close_plan_burden()
        self.assertEqual(burden["waiting_count"], 2, "已终态与正在提交的都不算「还没提交」")
        self.assertEqual(burden["next_batch_at"], "14:30:00")

    def test_close_burden_empty_without_clock_or_batch(self):
        """BE1：钟不可用、批次时刻读不到、没有计划——next_batch_at 一律空串。"""
        self.api._plan = self._PlanStub([
            {"task_id": "t1", "status": "waiting", "sign_start": "不是时间"},
        ])
        with mock.patch.object(self.api, "_clock_ready", lambda: False):
            self.assertEqual(self.api._close_plan_burden(),
                             {"waiting_count": 1, "next_batch_at": ""})
        with mock.patch.object(self.api, "_clock_ready", lambda: True):
            self.assertEqual(self.api._close_plan_burden(),
                             {"waiting_count": 1, "next_batch_at": ""})
        self.api._plan = None
        self.assertEqual(self.api._close_plan_burden(),
                         {"waiting_count": 0, "next_batch_at": ""})

    def test_ask_window_close_keeps_old_fields_and_adds_burden(self):
        """BE1 只增不改：旧字段原样在场，waiting_count/next_batch_at 随载荷出去。"""
        events = []
        self.api._emit = lambda kind, payload: events.append((kind, dict(payload)))
        self.api._ensure_tray = lambda: False
        self.api._plan = self._PlanStub([
            {"task_id": "t1", "status": "waiting", "sign_start": "2026-11-08 14:30:00"},
        ])
        with mock.patch.object(self.api, "_clock_ready", lambda: True):
            result = self.api.ask_window_close()
        self.assertTrue(result["ok"])
        self.assertEqual(events[0][0], "window_close_ask")
        payload = events[0][1]
        # 旧字段与旧结论不回归（只补不删）
        self.assertEqual(payload["default_action"], "ask")
        for key in ("plan_running", "tray_ok", "phone_running", "phone_live"):
            self.assertIn(key, payload)
        self.assertEqual(payload["waiting_count"], 1)
        self.assertEqual(payload["next_batch_at"], "14:30:00")

    def test_hide_window_notifies_the_tray_once(self):
        """BE2：隐藏成功恰弹一次托盘通知，标题与正文逐字（CW10）。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: True
        notifies = []

        class _Tray:
            def notify(self, title, text):
                notifies.append((title, text))

        self.api._tray = _Tray()
        result = self.api.hide_window()
        self.assertTrue(result["ok"], result)
        self.assertEqual(notifies, [("窗口已隐藏，工具在后台运行",
                                     "报名计划照常运行。点右下角托盘图标回来，"
                                     "也可以在手机页点“显示电脑窗口”。")])

    def test_hide_window_without_tray_skips_the_notice(self):
        """BE2：托盘没建起来（_tray 为 None）不弹也不抛，隐藏照常成功。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: False
        self.api._phone.live = True
        self.api._tray = None
        result = self.api.hide_window()
        self.assertTrue(result["ok"], result)
        self.assertFalse(result["tray"], "托盘没建起来要如实告诉界面")

    def test_hide_window_survives_a_failing_tray_notify(self):
        """BE2：notify 抛错只吞掉，不影响隐藏结果与返回值。"""
        window = mock.Mock()
        window.hide = mock.Mock()
        self.api._window = window
        self.api._ensure_tray = lambda: True

        class _BadTray:
            def notify(self, title, text):
                raise RuntimeError("tray gone")

        self.api._tray = _BadTray()
        result = self.api.hide_window()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["hidden"])
        window.hide.assert_called_once()

    def test_tailscale_preference_records_autostart(self):
        result = self.api.set_phone_access_preferences("tailscale")
        self.assertTrue(result["ok"])
        self.assertEqual(result["preferred_channel"], "tailscale")
        self.assertTrue(result["tailscale_autostart"])
        self.assertEqual(self._prefs_block()["preferred_channel"], "tailscale")

    def test_tailscale_restore_starts_persistent_entry(self):
        self.api.set_phone_access_preferences("tailscale")
        self._connect_tailscale()
        result = self.api.restore_phone_access()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result.get("restored"))
        self.assertEqual(len(self.api._phone.start_calls), 1)
        call = self.api._phone.start_calls[0]
        self.assertEqual(call["host"], "100.64.0.9", "必须绑 Tailscale 地址而不是回环")
        self.assertEqual(call["public_host"], "pc.tail.ts.net", "优先 MagicDNS 固定名")
        self.assertTrue(call["persistent_device"], "Tailscale 才允许设备信任")

    def test_missing_tailscale_blocks_restore(self):
        self.api.set_phone_access_preferences("tailscale")
        self._connect_tailscale(available=False, error="tailscale_missing", state="missing")
        result = self.api.restore_phone_access()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "tailscale_missing")
        self.assertEqual(self.api._phone.start_calls, [], "没装就不该尝试监听")

    def test_cloudflare_preference_never_autostarts(self):
        result = self.api.set_phone_access_preferences("cloudflare")
        self.assertTrue(result["ok"])
        self.assertFalse(result["tailscale_autostart"])
        self._connect_tailscale()
        restored = self.api.restore_phone_access()
        self.assertFalse(restored["ok"])
        self.assertEqual(restored["error"], "not_configured")
        self.assertEqual(self.api._phone.start_calls, [])

    def test_manual_close_clears_autostart_but_keeps_channel(self):
        self.api.set_phone_access_preferences("tailscale")
        self.api._phone.running = True
        self.api._stop_phone_access()
        block = self._prefs_block()
        self.assertEqual(block["preferred_channel"], "tailscale")
        self.assertFalse(block["tailscale_autostart"], "手动关闭后不再自动恢复")
        self.assertTrue(self.api._phone.stop_calls[-1]["revoke_devices"],
                        "手动关闭必须撤销设备信任")

    def _stuck_cloudflare_phone(self):
        """H1：Cloudflare 通道在跑，但隧道进程停不下来（stop 返回 tunnel_stop_failed）。"""
        tunnel = FakeCloudflareTunnel(state="running")
        tunnel.stop_result = {"ok": False, "error": "tunnel_stop_failed",
                              "text": "Cloudflare 隧道仍在运行，请重试关闭。"}
        self._cloudflare_phone(tunnel)
        events = []
        self.api._emit = lambda kind, payload: events.append((kind, payload))
        return tunnel, events

    def test_stop_phone_access_reports_a_tunnel_that_would_not_stop(self):
        """H1：隧道没停下，不能写「手机访问已关闭」，要把失败结果交给界面并留一条运行记录；手机入口仍照常关掉。"""
        tunnel, events = self._stuck_cloudflare_phone()
        result = self.api.stop_phone_access()
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "tunnel_stop_failed")
        self.assertTrue(result.get("text"), "界面要有一句能显示的原因")
        self.assertEqual(result["text"], "手机入口已停止，但 Cloudflare 隧道没能关闭，请重试关闭。")
        logs = [payload for kind, payload in events if kind == "log"]
        self.assertNotIn("手机访问已关闭", logs, "隧道还在就不能说已关闭")
        self.assertIn("Cloudflare 隧道没能关闭，请重试", logs)
        self.assertIn(result["text"], logs, "运行记录写的是同一句如实说明")
        self.assertEqual(tunnel.stop_calls, 1)
        # 隧道停不下也要关手机入口并撤销会话，隧道后面没有东西可转发
        self.assertTrue(self.api._phone.stop_calls[-1]["revoke_devices"])
        self.assertFalse(self.api._phone.running)
        self.assertEqual(self.api._phone_channel, "")
        # 重试安全：phone.stop 幂等，隧道再停一次成功后照常写已关闭
        tunnel.stop_result = None
        again = self.api.stop_phone_access()
        self.assertTrue(again["ok"], again)
        self.assertEqual(tunnel.stop_calls, 2)
        self.assertIn(("log", "手机访问已关闭"), events)

    def test_stop_phone_access_still_closes_normally_when_the_tunnel_stops(self):
        """H1 守卫：隧道正常停下时仍写「手机访问已关闭」，结果沿用 phone.stop 的返回。"""
        tunnel = FakeCloudflareTunnel(state="running")
        self._cloudflare_phone(tunnel)
        events = []
        self.api._emit = lambda kind, payload: events.append((kind, payload))
        result = self.api.stop_phone_access()
        self.assertTrue(result["ok"], result)
        self.assertIn(("log", "手机访问已关闭"), events)
        self.assertEqual(self.api._phone_channel, "")

    def test_component_swap_is_refused_while_the_tunnel_would_not_stop(self):
        """H1：换包前隧道停不下，抛出组件占用错误且不继续换包（单包与成组两个入口）。"""
        from unittest import mock

        tunnel, _events = self._stuck_cloudflare_phone()
        packages = self.local_app._component_packages
        with mock.patch.object(packages, "install") as install,                 mock.patch.object(packages, "commit_artifact_group") as commit:
            with self.assertRaises(packages.PackageError) as raised:
                self.api._install_downloaded_component("a.zip", "phone_control")
            self.assertEqual(raised.exception.args[0], "component_in_use")
            with self.assertRaises(packages.PackageError) as raised:
                self.api._commit_downloaded_component_group("phone_control", [])
            self.assertEqual(raised.exception.args[0], "component_in_use")
            install.assert_not_called()
            commit.assert_not_called()
        self.assertEqual(tunnel.stop_calls, 2)

    def test_bad_channel_is_rejected_without_writing(self):
        result = self.api.set_phone_access_preferences("lan")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bad_channel")
        self.assertFalse(self.prefs_path.exists(), "非法通道不得落盘")

    # ---------- Cloudflare 生命周期对账 ----------

    def _cloudflare_phone(self, tunnel):
        """把 Api 摆成「Cloudflare 通道正在跑」的样子，隧道换成注入的替身。"""
        self.api._cloudflare = tunnel
        self.api._phone_channel = "cloudflare"
        self.api._phone.running = True
        self.api._phone.live = True
        # Tailscale 探测会真的起子进程：这里固定成不可用
        self._connect_tailscale(available=False, error="tailscale_missing",
                                state="missing")

    def test_cloudflare_exit_is_reconciled_on_the_first_state_read(self):
        tunnel = FakeCloudflareTunnel(state="exited")
        self._cloudflare_phone(tunnel)
        state = self.api.phone_access_state()
        self.assertFalse(state["running"], "隧道没了就不能还说自己开着")
        self.assertEqual(state["address"], "", "旧地址已经不可能连上了")
        self.assertEqual(state["qr"], "", "不能把旧二维码留在界面上")
        self.assertEqual(state["channel"], "")
        self.assertFalse(self.api._phone.running, "手机服务必须停下，不能再占着端口")
        self.assertEqual(len(self.api._phone.stop_calls), 1)
        self.assertTrue(self.api._phone.stop_calls[0]["revoke_devices"],
                        "通道失效要撤销当前会话，不能让旧 cookie 继续可用")
        cloudflare = state["advanced"]["channels"]["cloudflare"]
        self.assertEqual(cloudflare["state"], "exited")
        self.assertEqual(cloudflare["error"], "tunnel_exited")
        self.assertTrue(cloudflare["text"], "至少要说清发生了什么")
        self.assertTrue(cloudflare["available"],
                        "组件还在，通道仍可重新开启；只是这次进程退出了")

    def test_the_exit_notice_is_not_downgraded_to_available(self):
        tunnel = FakeCloudflareTunnel(state="exited")
        self._cloudflare_phone(tunnel)
        first = self.api.phone_access_state()["advanced"]["channels"]["cloudflare"]
        second = self.api.phone_access_state()["advanced"]["channels"]["cloudflare"]
        self.assertEqual(first["state"], "exited")
        self.assertEqual(second["state"], "exited",
                         "第二次读到的 stopped 不能把退出提示降级成可用")
        self.assertEqual(second["error"], "tunnel_exited")
        self.assertGreaterEqual(tunnel.status_calls, 2, "确认真的读了不止一次")
        # 用户手动关掉通道后才收起提示
        self.api.stop_phone_access()
        third = self.api.phone_access_state()["advanced"]["channels"]["cloudflare"]
        self.assertEqual(third["state"], "available")
        self.assertEqual(third["error"], "")

    def test_cloudflare_start_is_refused_without_a_verified_component(self):
        tunnel = FakeCloudflareTunnel(executable="C:/stale/bin/cloudflared.exe")
        self.api._cloudflare = tunnel
        self._connect_tailscale(available=False, error="", state="")
        with mock.patch.object(self.local_app._tunnel_manager, "resolve_cloudflared",
                               lambda **kwargs: ""):
            result = self.api.start_phone_access("cloudflare")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "cloudflared_missing")
        self.assertEqual(tunnel.executable, "",
                         "校验失败必须先清掉启动时缓存的旧路径")
        self.assertEqual(self.api._phone.start_calls, [],
                         "组件不可用时不能先把手机服务开起来")
        self.assertEqual(tunnel.start_calls, [])

    def test_cloudflare_start_uses_the_freshly_verified_path(self):
        tunnel = FakeCloudflareTunnel(executable="")
        self.api._cloudflare = tunnel
        self._connect_tailscale(available=False, error="", state="")
        verified = "D:/app/data/advanced/phone_control/bin/cloudflared.exe"
        with mock.patch.object(self.local_app._tunnel_manager, "resolve_cloudflared",
                               lambda **kwargs: verified):
            result = self.api.start_phone_access("cloudflare")
        self.assertTrue(result["ok"], result)
        self.assertEqual(tunnel.executable, verified,
                         "启动时用的必须是刚刚校验过的路径")
        self.assertEqual(tunnel.start_calls, ["http://100.64.0.9:8765/"])

    def test_a_successful_cloudflare_start_clears_the_exit_notice(self):
        tunnel = FakeCloudflareTunnel(state="exited")
        self._cloudflare_phone(tunnel)
        self.api.phone_access_state()  # 先把退出提示存下来
        self.assertEqual(self.api._cloudflare_exit_notice["state"], "exited")
        with mock.patch.object(self.local_app._tunnel_manager, "resolve_cloudflared",
                               lambda **kwargs: tunnel.executable):
            result = self.api.start_phone_access("cloudflare")
        self.assertTrue(result["ok"], result)
        self.assertIsNone(self.api._cloudflare_exit_notice,
                          "重新开启成功后旧提示必须清掉")
        after = self.api.phone_access_state()["advanced"]["channels"]["cloudflare"]
        self.assertEqual(after["state"], "running")

    def test_state_carries_features_channels_and_active_channel(self):
        """三份状态必须各归各：能力、通道、当前跑的哪条，前端不许自己推导。"""
        tunnel = FakeCloudflareTunnel(state="available")
        self._cloudflare_phone(tunnel)
        self.api._phone.running = False
        state = self.api.phone_access_state()
        self.assertIn("phone_control", state["features"])
        self.assertIn("tailscale", state["channels"])
        self.assertIn("cloudflare", state["channels"])
        self.assertEqual(state["active_channel"], "cloudflare",
                         "当前通道单独给，不能靠 running 猜")
        self.assertFalse(state["running"])

    def test_switching_channel_while_running_is_rejected(self):
        """换通道必须先关旧的：不自动切、不悄悄把旧通道停掉。"""
        tunnel = FakeCloudflareTunnel(state="running")
        self._cloudflare_phone(tunnel)
        self._connect_tailscale(available=True)
        result = self.api.start_phone_access("tailscale")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "other_channel_running")
        self.assertEqual(self.api._phone_channel, "cloudflare", "旧通道不许被顶掉")
        self.assertEqual(len(self.api._phone.stop_calls), 0)

    def test_second_cloudflare_start_says_it_is_starting(self):
        tunnel = FakeCloudflareTunnel(executable="D:/bin/cloudflared.exe")
        self.api._cloudflare = tunnel
        self.api._cloudflare_starting = True
        self._connect_tailscale(available=False, error="", state="")
        result = self.api.start_phone_access("cloudflare")
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["error"], "cloudflare_starting")
        self.assertEqual(tunnel.start_calls, [], "正在启动时不能再叠一条隧道")


class AdvancedComponentDialogTests(unittest.TestCase):
    """对话框的「选文件 → 自检 → 安装」三步：选错要说清是什么，源码版不吞组件包。"""

    def setUp(self):
        import shutil
        import tempfile

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        tmp = tempfile.mkdtemp(prefix="campus-component-dialog-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.dir = Path(tmp)
        for patch in (
            mock.patch.object(local_app, "PREFS", self.dir / "ui.json"),
            mock.patch.object(local_app, "DEVICE_FILE", self.dir / "devices.json"),
            mock.patch.object(local_app, "DEMO", True),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()
        self.addCleanup(self.api.shutdown)

    def _file(self, name, data=b"MZfake"):
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_download_is_refused_in_source_builds(self):
        """源码版没有组件概念：点「下载组件包」应直接说清，而不是悄悄去下载。"""
        result = self.api.download_advanced_feature("phone_control")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_build")

    def test_download_rejects_unknown_feature(self):
        result = self.api.download_advanced_feature("segno")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bad_feature")

    def test_ocr_download_is_a_known_feature(self):
        """验证码识别也能一键下载：源码版同样直说不需要，而不是报「未知功能」。"""
        result = self.api.download_advanced_feature("relogin_ocr")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_build")

    def test_cancel_without_task_says_nothing_to_cancel(self):
        result = self.api.cancel_advanced_feature_download("phone_control")
        self.assertTrue(result["ok"])
        self.assertIn("没有", result["text"])

    def test_state_exposes_download_snapshot_for_both_components(self):
        """两个组件都能一键下载（f9442ad 起验证码识别也有下载事务）。

        旧断言认为 ddddocr 走已装依赖、不需要下载，组件包上线后不再成立；
        新断言改成两行都带 download 快照、状态值取自同一集合。
        """
        state = self.api.advanced_features_state()
        for key in ("phone_control", "relogin_ocr"):
            with self.subTest(feature=key):
                feature = state["features"][key]
                self.assertIn("download", feature)
                self.assertIn(feature["download"]["state"],
                              {"available", "installed", "missing", "cancelled", "failed",
                               "downloading", "verifying", "removing"})

    def _version_text(self, text):
        return mock.patch.object(
            self.local_app._component_packages, "cloudflared_version_text",
            lambda _path: text)

    def test_a_tailscale_exe_is_named_as_tailscale(self):
        exe = self._file("tailscale.exe")
        with self._version_text("tailscale v1.80.0  tailscale is a mesh VPN"):
            info = self.api.inspect_advanced_component("phone_control", str(exe))
        self.assertFalse(info["ok"])
        self.assertEqual(info["kind"], "tailscale")
        self.assertIn("Tailscale", info["text"])

    def test_the_right_cloudflared_passes_the_read_only_check(self):
        exe = self._file("cloudflared.exe")
        with self._version_text("cloudflared version 2026.10.7 (built 2026-10-30T09:43 UTC)"):
            info = self.api.inspect_advanced_component("phone_control", str(exe))
        self.assertTrue(info["ok"])
        self.assertEqual(info["kind"], "cloudflared")

    def test_choosing_a_cloudflared_installs_it_and_refreshes_the_channel(self):
        exe = self._file("cloudflared.exe")
        version = "cloudflared version 2026.10.7 (built 2026-10-30T09:43 UTC)"
        seen = {}

        def fake_install(source, **kwargs):
            seen["source"] = str(source)
            return {"ok": True, "text": "cloudflared 已收好。"}

        def fake_resolve(**kwargs):
            seen["resolve"] = True
            return "D:/store/cloudflared.exe"

        with self._version_text(version),                 mock.patch.object(self.local_app._component_packages,
                                  "install_cloudflared", fake_install),                 mock.patch.object(self.local_app._tunnel_manager,
                                  "resolve_cloudflared", fake_resolve):
            result = self.api.install_advanced_feature("phone_control", str(exe))

        self.assertTrue(result["ok"])
        self.assertEqual(seen["source"], str(exe))
        self.assertTrue(seen.get("resolve"), "装好之后要重新解析通道用的路径")
        self.assertEqual(self.api._cloudflare.executable, "D:/store/cloudflared.exe")
        prefs = self.local_app.load_prefs()
        self.assertTrue((prefs.get("advanced_features") or {}).get("phone_control"))

    def test_a_component_zip_is_refused_in_a_source_build(self):
        # 清单版本要跟当前程序一致：这条用例验的是「源码版不收组件包」，
        # 写死旧版本会先撞上版本不符的分支，验不到本意
        current = self.local_app.APP_VERSION
        archive = self.dir / ("phone_control-%s-windows-x64.zip" % current)
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", json.dumps({
                "schema": 1, "feature": "phone_control", "platform": "windows-x64",
                "entry": "feature-helper.exe", "version": current,
                "files": {"feature-helper.exe": "0" * 64,
                          "bin/cloudflared.exe": "0" * 64},
                "cloudflared": {"version": self.local_app._component_packages.CLOUDFLARED_VERSION,
                                "sha256": "0" * 64},
            }))
        result = self.api.install_advanced_feature("phone_control", str(archive))
        # 源码版走的是已装好的 Python 依赖：组件包对它没用，必须说人话而不是装上去
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_build")
        # 裸 cloudflared.exe 的入口已从界面去掉：提示不能再指向它，也不能指向 PATH 之类走不通的路
        self.assertNotIn("选择 cloudflared.exe", result["text"])
        self.assertIn("发布版", result["text"])

    def test_pick_dialog_offers_only_zip_for_both_features(self):
        """手机控制和验证码识别的选择框一致：只列组件包 ZIP；打不开时不指向只读输入框。"""
        class _Window:
            def __init__(self):
                self.types = []
                self.fail = False

            def create_file_dialog(self, *_args, file_types=(), **_kwargs):
                if self.fail:
                    raise RuntimeError("no dialog")
                self.types.append(tuple(file_types))
                return None

        window = _Window()
        self.api._window = window
        for key in ("phone_control", "relogin_ocr"):
            self.api.pick_advanced_component(key)
        self.assertEqual(window.types, [("组件包 (*.zip)",)] * 2)
        window.fail = True
        result = self.api.pick_advanced_component("phone_control")
        self.assertEqual(result["error"], "dialog_unavailable")
        self.assertNotIn("手动填写", result["text"])
        self.assertIn("导入已下载的组件包", result["text"])

    def test_an_exe_for_the_ocr_feature_is_told_to_pick_a_zip(self):
        exe = self._file("ocr.exe")
        info = self.api.inspect_advanced_component("relogin_ocr", str(exe))
        self.assertFalse(info["ok"])
        self.assertEqual(info["kind"], "not_zip")


class AdvancedBackendFieldsTests(unittest.TestCase):
    """设置抽屉要的四个后端字段（settings-gap B1–B4）：启用、位置、已连接计数、暂存账号。

    全部替身：偏好和数据目录在临时目录，系统打开文件夹的调用被替换，不连学校、
    不碰真实凭据。重点是路径与密码「只走该走的口子」。
    """

    def setUp(self):
        import shutil

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        tmp = tempfile.mkdtemp(prefix="campus-backend-fields-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.dir = Path(tmp)
        self.data = self.dir / "data"
        self.data.mkdir()
        for patch in (
            mock.patch.object(local_app, "PREFS", self.dir / "ui.json"),
            mock.patch.object(local_app, "DEVICE_FILE", self.dir / "devices.json"),
            mock.patch.object(local_app, "DATA_DIR", self.data),
            mock.patch.object(local_app, "DEMO", True),
            # 组件装没装只看依赖能否导入：按需要在各用例里改，默认「没装」
            mock.patch.object(local_app._advanced_features, "module_available",
                              lambda _module: False),
            mock.patch.object(local_app._tunnel_manager, "tailscale_endpoint",
                              lambda *a, **k: {"available": False, "error": "tailscale_missing",
                                               "state": "missing", "text": "没装"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()
        self.addCleanup(self.api.shutdown)

    def _installed(self, installed=True):
        patch = mock.patch.object(self.local_app._advanced_features, "module_available",
                                  lambda _module: installed)
        patch.start()
        self.addCleanup(patch.stop)

    def _enabled_in_prefs(self):
        return dict(self.local_app.load_prefs().get("advanced_features") or {})

    # ---------- B2 enable_advanced_feature ----------
    def test_enable_turns_on_both_known_components_once_installed(self):
        self._installed(True)
        for key in ("phone_control", "relogin_ocr"):
            with self.subTest(feature=key):
                self.assertFalse(self._enabled_in_prefs().get(key, False), "起点是没启用")
                result = self.api.enable_advanced_feature(key)
                self.assertTrue(result["ok"], result)
                self.assertTrue(self._enabled_in_prefs().get(key))
                row = self.api.advanced_features_state()["features"][key]
                self.assertTrue(row["enabled"])
                self.assertTrue(row["ready"])

    def test_enable_refuses_unknown_key_and_changes_nothing(self):
        self._installed(True)
        for key in ("segno", "", "../phone_control"):
            with self.subTest(key=key):
                result = self.api.enable_advanced_feature(key)
                self.assertFalse(result["ok"])
                self.assertEqual(result["reason"], "bad_feature")
        self.assertEqual(self._enabled_in_prefs(), {}, "未知键不得写进偏好")

    def test_enable_refuses_when_component_is_not_installed(self):
        self._installed(False)
        for key in ("phone_control", "relogin_ocr"):
            with self.subTest(feature=key):
                result = self.api.enable_advanced_feature(key)
                self.assertFalse(result["ok"])
                self.assertEqual(result["reason"], "not_available")
        self.assertEqual(self._enabled_in_prefs(), {}, "没装好就不能启用，偏好一个字不改")

    def test_enabling_ocr_resets_auto_relogin_but_phone_control_does_not(self):
        self._installed(True)
        with mock.patch.object(self.api._auto_relogin, "reset") as reset:
            self.api.enable_advanced_feature("phone_control")
            self.assertEqual(reset.call_count, 0)
            self.api.enable_advanced_feature("relogin_ocr")
            self.assertEqual(reset.call_count, 1, "启用识别后自动登录要从头开始")

    # ---------- B3 组件位置：只给电脑端 ----------
    def test_location_points_into_the_data_dir_advanced_folder(self):
        for key in ("phone_control", "relogin_ocr"):
            with self.subTest(feature=key):
                info = self.api.advanced_component_location(key)
                self.assertTrue(info["ok"], info)
                expected = (self.data / "advanced" / key).resolve()
                self.assertEqual(Path(info["path"]), expected)
                self.assertEqual(info["short"], "…\\advanced\\" + key)
                self.assertNotIn(self.dir.name, info["short"], "省略形式不带真实目录")
                self.assertFalse(info["exists"], "还没装时目录不存在")
        (self.data / "advanced" / "relogin_ocr").mkdir(parents=True)
        self.assertTrue(self.api.advanced_component_location("relogin_ocr")["exists"])

    def test_location_refuses_unknown_key(self):
        for key in ("segno", "", "..", "phone_control/.."):
            with self.subTest(key=key):
                result = self.api.advanced_component_location(key)
                self.assertFalse(result["ok"])
                self.assertNotIn("path", result)

    def test_open_dir_prefers_component_then_parent_then_refuses(self):
        advanced = self.data / "advanced"
        opened = []
        with mock.patch.object(self.local_app.os, "startfile",
                               lambda path: opened.append(path), create=True):
            gone = self.api.open_advanced_component_dir("phone_control")
            self.assertFalse(gone["ok"], "两级都不存在要如实说")
            self.assertEqual(opened, [])
            advanced.mkdir()
            parent = self.api.open_advanced_component_dir("phone_control")
            self.assertTrue(parent["ok"])
            self.assertEqual(parent["opened"], "parent")
            (advanced / "phone_control").mkdir()
            own = self.api.open_advanced_component_dir("phone_control")
            self.assertEqual(own["opened"], "component")
            self.assertEqual(Path(opened[-1]), (advanced / "phone_control").resolve())
            self.assertFalse(self.api.open_advanced_component_dir("segno")["ok"])
            self.assertEqual(len(opened), 2, "未知键不得触发打开")
        for reply in (gone, parent, own):
            self.assertNotIn("path", reply, "打开接口的回执也不带路径")

    def test_open_dir_reports_a_system_failure_instead_of_raising(self):
        (self.data / "advanced" / "phone_control").mkdir(parents=True)

        def boom(_path):
            raise OSError("no shell")

        with mock.patch.object(self.local_app.os, "startfile", boom, create=True):
            result = self.api.open_advanced_component_dir("phone_control")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "open_failed")

    def test_no_component_path_leaks_into_state_or_phone_snapshot(self):
        """路径只能走 advanced_component_location：状态快照和手机快照里一个字都不许有。"""
        (self.data / "advanced" / "phone_control").mkdir(parents=True)
        info = self.api.advanced_component_location("phone_control")
        self.assertTrue(info["ok"])
        escaped = json.dumps(info["path"])[1:-1]
        snapshots = {
            "advanced_features_state": self.api.advanced_features_state(),
            "phone_access_state": self.api.phone_access_state(),
            "phone_raw_state": self.api._phone_raw_state(),
        }
        for name, snapshot in snapshots.items():
            with self.subTest(snapshot=name):
                text = json.dumps(snapshot, ensure_ascii=False)
                self.assertNotIn(self.dir.name, text, "临时数据目录的名字出现在快照里了")
                self.assertNotIn(info["path"], text)
                self.assertNotIn(escaped, text)
                self.assertNotIn("…\\advanced", text)

    def test_migration_record_stays_out_of_the_phone_snapshot(self):
        """BE3：迁移结果只给桌面横幅与运行记录，手机快照不得多出 migration 字段。"""
        with mock.patch.object(self.local_app, "migration_record",
                               lambda: {"moved": 3, "login_failed": False}):
            snapshot = self.api._phone_raw_state()
        self.assertNotIn("migration", snapshot,
                         "迁移字段不进手机快照（手机页没有这条横幅）")

    # ---------- B4 staged / staged_hint ----------
    def test_staged_reports_a_masked_hint_and_never_the_password(self):
        credential = self.api.advanced_features_state()["credential"]
        self.assertIs(credential["staged"], False)
        self.assertEqual(credential["staged_hint"], "")
        self.assertTrue(self.api._relay.prepare("demo-user-42", "pw-secret-xyz")["ok"])
        state = self.api.advanced_features_state()
        credential = state["credential"]
        self.assertIs(credential["staged"], True)
        self.assertEqual(credential["staged_hint"], "de****42")
        dump = json.dumps(state, ensure_ascii=False) + json.dumps(
            self.api.phone_access_state(), ensure_ascii=False)
        self.assertNotIn("pw-secret-xyz", dump)
        self.assertNotIn("demo-user-42", dump, "账号只给打码形式")
        self.api._relay.clear_staged()
        credential = self.api.advanced_features_state()["credential"]
        self.assertIs(credential["staged"], False)
        self.assertEqual(credential["staged_hint"], "")

    # ---------- B1 paired_count 透出 ----------
    def test_phone_access_state_carries_the_paired_count(self):
        self.assertEqual(self.api.phone_access_state()["paired_count"], 0)
        self.api._phone.paired = 2
        self.assertEqual(self.api.phone_access_state()["paired_count"], 2)

    # ---------- fe-phone：live_session（审核决定 A4，设备 cookie 恢复的手机也算已连接）----------
    def test_live_session_is_a_bool_and_false_while_phone_access_is_stopped(self):
        phone = self.api._phone
        phone.running = False
        phone.live = True            # 替身故意不清会话：停着时也必须报假
        self.assertIs(self.api.phone_access_state()["live_session"], False,
                      "手机访问停着时不能说有会话")
        phone.running = True
        phone.live = False
        self.assertIs(self.api.phone_access_state()["live_session"], False)
        phone.live = True
        self.assertIs(self.api.phone_access_state()["live_session"], True,
                      "只给布尔，不给 token 或 cookie")
        phone.running = False
        self.assertIs(self.api.phone_access_state()["live_session"], False)


class WindowCloseHandlingTests(unittest.TestCase):
    """closing 回调跑在 UI 主线程：界面动作必须 defer，不能在主线程里 evaluate_js。

    直接在主线程调 evaluate_js 会抢 pywebview 的内部锁，窗口变「未响应」
    （pywebview#1699；真机复现见 2026-10-31 关窗三选卡死）。
    """

    def _app(self):
        """import app 需要把 local/ 插进 sys.path；解析失败按既有惯例 skip。"""
        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 仅在缺依赖的环境触发
            self.skipTest("local/app.py 无法导入：%s" % exc)
        return local_app

    class _Window:
        def __init__(self):
            self.minimized = 0

        def minimize(self):
            self.minimized += 1

    class _Api:
        def __init__(self, plan_running=False):
            self._close_approved = False
            self._plan_running = plan_running
            self.asked = 0

        def plan_active_for_close(self):
            return self._plan_running

        def ask_window_close(self):
            self.asked += 1
            return {"ok": True}

        def hide_window(self):
            self.hidden = getattr(self, "hidden", 0) + 1
            return {"ok": True, "hidden": True}

    def _handle(self, prefs, *, plan_running=False):
        """跑一次判定，返回 (放行?, 被 defer 的动作名列表, api, window)。"""
        local_app = self._app()
        api = self._Api(plan_running=plan_running)
        window = self._Window()
        queued = []

        def _defer(callback, delay=None):
            # 记下「谁被推迟了」，但**不执行**——执行时机属于工作线程，不在本断言范围
            queued.append(getattr(callback, "__name__", "callable"))

        with mock.patch.object(local_app, "load_prefs", lambda: {"window": prefs}):
            allowed = local_app.handle_window_close(api, window, defer=_defer)
        return allowed, queued, api, window

    def test_ask_is_deferred_instead_of_talking_to_the_ui_thread(self):
        allowed, queued, api, window = self._handle({})
        self.assertFalse(allowed, "默认必须取消这次关闭")
        self.assertEqual(queued, ["ask_window_close"], "弹三选必须 defer 出主线程")
        self.assertEqual(api.asked, 0, "主线程里绝不能直接推事件给界面")
        self.assertEqual(window.minimized, 0)

    def test_remembered_exit_passes_through(self):
        allowed, queued, api, _ = self._handle({"close_action": "exit"})
        self.assertTrue(allowed)
        self.assertEqual(queued, [])
        self.assertTrue(api._close_approved, "退出要先置放行标记，否则又会被自己的守卫拦下")

    def test_remembered_minimize_is_deferred_too(self):
        allowed, queued, api, window = self._handle({"close_action": "minimize"})
        self.assertFalse(allowed)
        self.assertEqual(queued, ["minimize"])
        self.assertEqual(window.minimized, 0, "最小化也要挪出主线程")

    def test_plan_running_forces_the_question_even_when_exit_is_remembered(self):
        allowed, queued, _, _ = self._handle({"close_action": "exit"}, plan_running=True)
        self.assertFalse(allowed)
        self.assertEqual(queued, ["ask_window_close"])

    def test_approved_close_lets_the_window_go(self):
        local_app = self._app()
        api = self._Api()
        api._close_approved = True
        queued = []
        allowed = local_app.handle_window_close(api, self._Window(), defer=queued.append)
        self.assertTrue(allowed)
        self.assertEqual(queued, [])

    def test_remembered_hide_is_deferred_instead_of_run_on_the_main_thread(self):
        """「隐藏到后台」和最小化一样要挪出主线程：hide 也是窗口操作。"""
        allowed, queued, _, window = self._handle({"close_action": "hide"})
        self.assertFalse(allowed, "隐藏＝取消这次关闭，进程要继续跑")
        self.assertEqual(queued, ["hide_window"])
        self.assertEqual(window.minimized, 0)


class FakeRelay:
    """LoginRelayService 的替身：只提供状态投影、预备与开始这三件事。"""

    def __init__(self, state=None):
        self.state_value = dict(state or {"ready": False, "state": "idle"})
        self.begin_calls = []
        self.prepared_value = True

    def state(self):
        return dict(self.state_value)

    def prepared(self):
        return self.prepared_value

    def prepare(self, user, secret):
        self.prepared_value = True
        return {"ok": True}

    def begin(self, **kwargs):
        self.begin_calls.append(dict(kwargs))
        return {"ok": True, "flow_id": "f-phone-1", "state": "starting"}


class FakeAutoRelogin:
    """AutoReloginMonitor 的替身：只回一个 snapshot。"""

    def __init__(self, failures=0, inflight=False, retry_in=0):
        self.value = {"state": "idle", "inflight": inflight,
                      "failures": failures, "retry_in": retry_in}

    def snapshot(self):
        return dict(self.value)

    def stop(self):
        self.value["inflight"] = False


class PhoneReloginTakeoverTests(unittest.TestCase):
    """电脑自己认图时，手机不该同时看到验证码；连续失败才把图交出去。"""

    def setUp(self):
        import shutil
        import tempfile

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        tmp = tempfile.mkdtemp(prefix="campus-phone-takeover-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.ocr = True
        self.ocr_patch = mock.patch.object(
            local_app._advanced_features, "feature_ready",
            lambda *a, **k: self.ocr)
        for patch in (
            mock.patch.object(local_app, "PREFS", Path(tmp) / "ui.json"),
            mock.patch.object(local_app, "DEVICE_FILE", Path(tmp) / "devices.json"),
            mock.patch.object(local_app, "DEMO", True),
            self.ocr_patch,
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()
        self.addCleanup(self.api.shutdown)

    def _tunnel_state(self, **over):
        state = {"ready": True, "state": "waiting_code", "flow_id": "f1",
                 "challenge_id": "chg-1",
                 "image": "data:image/png;base64,iVBORw0KGgo=",
                 "expires_in": None, "attempts": 0, "max_attempts": 0,
                 "safe_error": "", "submit_pending": False, "origin": "auto",
                 "live": True}
        state.update(over)
        return state

    def _view(self, relay=None, auto=None):
        self.api._relay = relay or FakeRelay(self._tunnel_state())
        self.api._auto_relogin = auto or FakeAutoRelogin(inflight=True)
        return self.api._phone_relay_view()

    def test_the_captcha_stays_on_the_computer_while_it_is_still_trying(self):
        view = self._view()
        self.assertEqual(view["image"], "", "电脑还在认图，图不该发给手机")
        self.assertEqual(view["challenge_id"], "")
        self.assertEqual(view["mode"], "auto")
        self.assertTrue(view["retrying"])

    def test_three_wrong_reads_hand_the_captcha_to_the_phone(self):
        view = self._view(relay=FakeRelay(self._tunnel_state(attempts=3)))
        self.assertTrue(view["image"].startswith("data:image/png;base64,"))
        self.assertEqual(view["challenge_id"], "chg-1")
        self.assertEqual(view["mode"], "manual")
        self.assertEqual(view["attempts"], 3)

    def test_three_failed_rounds_hand_it_over_even_with_few_attempts(self):
        view = self._view(auto=FakeAutoRelogin(failures=3, retry_in=120))
        self.assertEqual(view["mode"], "manual")
        self.assertEqual(view["auto_failures"], 3)
        self.assertEqual(view["retry_in"], 120)

    def test_without_ocr_the_phone_gets_the_captcha_at_once(self):
        self.ocr = False
        view = self._view()
        self.assertTrue(view["image"].startswith("data:image/png;base64,"))
        self.assertEqual(view["mode"], "manual")

    def test_phone_state_carries_the_projection(self):
        self.api._relay = FakeRelay(self._tunnel_state())
        self.api._auto_relogin = FakeAutoRelogin(inflight=True)
        relay = self.api._phone_raw_state()["login_relay"]
        self.assertEqual(relay["mode"], "auto")
        self.assertEqual(relay["image"], "")

    # ---------- 历史快照不许冒充「这一场」 ----------
    def test_history_attempts_do_not_lock_the_phone_into_manual(self):
        view = self._view(relay=FakeRelay(
            self._tunnel_state(attempts=3, live=False)))
        self.assertEqual(view["mode"], "auto",
                         "上一场剩下的 attempts 不该把手机永久推进人工模式")
        self.assertEqual(view["image"], "")
        self.assertFalse(view["live"])

    def test_a_finished_flow_is_not_live_on_the_phone(self):
        self.api._relay = FakeRelay(self._tunnel_state(state="success", live=False))
        self.api._auto_relogin = FakeAutoRelogin()
        relay = self.api._phone_raw_state()["login_relay"]
        self.assertFalse(relay["live"], "已经结束的那一场不是「这一次还在跑」")

    # ---------- 手机点「重登」不能变成第二场 ----------
    def _allow_begin(self):
        patch = mock.patch.object(self.local_app, "DEMO", False)
        patch.start()
        self.addCleanup(patch.stop)
        self.api._terms_gate = lambda: None

    def test_begin_does_not_open_a_second_flow_while_auto_is_running(self):
        self._allow_begin()
        relay = FakeRelay(self._tunnel_state(state="verifying"))
        self.api._relay = relay
        self.api._auto_relogin = FakeAutoRelogin(inflight=True)
        result = self.api.phone_relogin_begin()
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "auto")
        self.assertEqual(relay.begin_calls, [], "已经在跑就不该再起一个 worker")

    def test_begin_kicks_a_computer_attempt_when_nothing_is_running(self):
        self._allow_begin()
        self.api._relay = FakeRelay({"ready": False, "state": "idle"})
        self.api._auto_relogin = FakeAutoRelogin()
        started = []
        self.api._begin_auto_relogin = lambda: started.append(1) or {"ok": True}
        result = self.api.phone_relogin_begin()
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "auto")
        self.assertEqual(started, [1])

    def test_begin_still_opens_a_phone_flow_when_ocr_is_missing(self):
        self._allow_begin()
        self.ocr = False
        relay = FakeRelay({"ready": False, "state": "idle"})
        self.api._relay = relay
        self.api._auto_relogin = FakeAutoRelogin()
        result = self.api.phone_relogin_begin()
        self.assertTrue(result["ok"])
        self.assertEqual(len(relay.begin_calls), 1)
        self.assertNotIn("origin", relay.begin_calls[0],
                         "手机人工场沿用默认来源 phone")

    def test_begin_ignores_a_leftover_flow_from_the_previous_round(self):
        self._allow_begin()
        relay = FakeRelay(self._tunnel_state(state="waiting_code", live=False))
        self.api._relay = relay
        self.api._auto_relogin = FakeAutoRelogin()
        started = []
        self.api._begin_auto_relogin = lambda: started.append(1) or {"ok": True}
        result = self.api.phone_relogin_begin()
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "auto")
        self.assertEqual(started, [1],
                         "历史快照不算「正在跑」，点重登应该真的开一场")

    # ---------- 重登成功要刷新桌面登录状态 ----------
    def test_a_successful_relogin_refreshes_the_desktop_state(self):
        fired = threading.Event()
        self.api.check = lambda request_id="": fired.set()
        self.api._anchor_login_success("auto_ocr")
        self.assertTrue(fired.wait(2.0), "重登成功后必须触发一次登录检查")

    def test_a_check_that_arrives_mid_flight_runs_once_more(self):
        self.api._terms_gate = lambda *a, **k: None
        calls = []
        gate = threading.Event()

        def inner():
            calls.append(1)
            if len(calls) == 1:
                gate.wait(5.0)   # 第一轮故意占住槽位，制造「在途」

        self.api._do_check_inner = inner
        try:
            self.api.check("r-1")
            for _ in range(500):
                with self.api._lock:
                    running = self.api._checking
                if running:
                    break
                time.sleep(0.01)
            skipped = self.api.check("r-2")
            self.assertEqual(skipped.get("skipped"), "已在检查登录态")
            gate.set()
            for _ in range(500):
                if len(calls) >= 2 and not self.api._checking:
                    break
                time.sleep(0.01)
        finally:
            gate.set()
        self.assertGreaterEqual(len(calls), 2,
                                "被去重吃掉的那次刷新不能就这么丢了")


class AdvancedComponentServiceTests(unittest.TestCase):
    """手机控制组件下载事务：单飞、可取消、校验不过就不装、失败不动旧组件。"""

    ASSET = {"name": "campus-activity-watch-phone-control-v1.2.3-win-x64.zip",
             "url": "https://github.com/x/y/releases/download/v1.2.3/a.zip",
             "bytes": 2048, "sha256": "a" * 64}

    def _service(self, **overrides):
        from application import advanced_component_service as svc
        state = {"installed": False, "installs": [], "hooks": [], "removed": 0,
                 "gate": threading.Event()}
        state["gate"].set()

        def status(feature, root=None):
            return {"available": state["installed"], "source": "imported",
                    "error": "", "version": "1.2.3" if state["installed"] else ""}

        def download(url, *, name, expect_bytes, expect_sha256, root=None,
                     progress=None, cancel=None):
            if progress:
                progress(1024, 2048)
            state["gate"].wait(2)
            if cancel is not None and cancel():
                return {"ok": False, "error_code": "cancelled", "text": "已取消"}
            if state.get("download_result"):
                return state["download_result"]
            return {"ok": True, "path": str(Path(state["tmp"]) / name),
                    "bytes": 2048, "sha256": "a" * 64}

        def inspect(archive, key):
            if state.get("inspect_result"):
                return state["inspect_result"]
            return {"ok": True, "kind": "component", "feature": "phone_control",
                    "version": "1.2.3", "cloudflared": "2026.10.7", "text": "已识别"}

        def install(archive, key, *, root=None):
            state["installs"].append((str(archive), key))
            state["installed"] = True

        def remover(key, *, root=None):
            state["removed"] += 1
            state["installed"] = False

        options = dict(root=None, asset_resolver=lambda v: {"ok": True, "asset": self.ASSET},
                       download=download, inspect=inspect, install=install,
                       status=status, remover=remover,
                       on_installed=lambda v: state["hooks"].append(v))
        options.update(overrides)
        return svc.AdvancedComponentService(**options), state

    def _wait(self, service, expected, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            snap = service.snapshot()
            if snap["state"] == expected:
                return snap
            time.sleep(0.01)
        return service.snapshot()

    def test_start_downloads_verifies_then_installs(self):
        service, state = self._service()
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        started = service.start()
        self.assertTrue(started["ok"])
        snap = self._wait(service, "installed")
        self.assertEqual(snap["state"], "installed")
        self.assertEqual(len(state["installs"]), 1)
        self.assertEqual(state["hooks"], ["1.2.3"])
        self.assertIn("1.2.3", snap["text"])

    def test_split_assets_download_and_install_as_one_feature_transaction(self):
        assets = [dict(self.ASSET, artifact_id="relogin_ocr_runtime",
                       name="runtime.zip"),
                  dict(self.ASSET, artifact_id="relogin_ocr_model",
                       name="model.zip")]
        commits = []
        def cache_artifact(archive, artifact_id, **kwargs):
            state["installs"].append((str(archive), artifact_id))
            return {"artifact_id": artifact_id, "version": "1.2.3"}
        def commit_artifact_group(feature, artifacts, **kwargs):
            commits.append((feature, [item["artifact_id"] for item in artifacts]))
            state["installed"] = True
            return {"ok": True}
        service, state = self._service(
            feature="relogin_ocr",
            asset_resolver=lambda _version: {"ok": True, "assets": assets},
            inspect_artifact=lambda archive, artifact_id: {
                "ok": True, "artifact_id": artifact_id, "version": "1.2.3"},
            find_cached_artifact=lambda asset, **kwargs: None,
            cache_artifact=cache_artifact,
            commit_artifact_group=commit_artifact_group,
        )
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-artifacts-")
        self.assertTrue(service.start()["ok"])
        snap = self._wait(service, "installed")
        self.assertEqual(snap["state"], "installed")
        self.assertEqual([item[1] for item in state["installs"]],
                         ["relogin_ocr_runtime", "relogin_ocr_model"])
        self.assertEqual(commits, [("relogin_ocr", ["relogin_ocr_runtime", "relogin_ocr_model"])])

    def _split_package(self, directory, artifact_id, name, marker):
        from infrastructure import component_packages as packages
        spec = packages.ARTIFACTS[artifact_id]
        if spec["role"] == "model":
            files = {"models/common.onnx": marker, "models/common_old.onnx": marker,
                     "models/charsets-beta.json": b"{}", "models/charsets-old.json": b"{}"}
        else:
            files = {spec["entry"]: marker}
        manifest = {"schema": 2, "artifact_id": artifact_id, "feature": spec["feature"],
                    "role": spec["role"], "protocol": 1, "asset_version": "1.2.2",
                    "compatibility_id": "campus-activity-1", "entry": spec["entry"],
                    "requires": [], "files": {path: hashlib.sha256(raw).hexdigest()
                                               for path, raw in files.items()}}
        archive = directory / (name + ".zip")
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", json.dumps(manifest))
            for path, raw in files.items():
                package.writestr(path, raw)
        metadata = {"artifact_id": artifact_id, "name": archive.name,
                    "url": "https://example.invalid/" + archive.name,
                    "bytes": archive.stat().st_size, "sha256": packages.sha256(archive),
                    "content_sha256": packages.artifact_content_sha256(manifest),
                    "compatibility_id": manifest["compatibility_id"]}
        return archive, metadata

    def test_split_second_download_failure_preserves_current_group(self):
        from application import advanced_component_service as svc
        from infrastructure import component_packages as packages
        temp = tempfile.TemporaryDirectory(prefix="component-group-failure-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        runtime_id, model_id = "relogin_ocr_runtime", "relogin_ocr_model"
        old_runtime, _ = self._split_package(root, runtime_id, "old-runtime", b"old-runtime")
        old_model, _ = self._split_package(root, model_id, "old-model", b"old-model")
        new_runtime, runtime_meta = self._split_package(root, runtime_id, "new-runtime", b"new-runtime")
        _, model_meta = self._split_package(root, model_id, "new-model", b"new-model")
        with mock.patch.object(packages, "_helper", return_value={"ok": True}), \
                mock.patch.object(packages, "supported", return_value=True):
            packages.install_artifact(old_runtime, runtime_id, root=root)
            packages.install_artifact(old_model, model_id, root=root)
            before = packages.feature_status("relogin_ocr", root=root)
            calls = []
            def download(url, *, name, **kwargs):
                calls.append(name)
                if name == model_meta["name"]:
                    return {"ok": False, "error_code": "network_error", "text": "模拟断流"}
                folder = root / "download"
                folder.mkdir()
                path = folder / name
                shutil.copy2(new_runtime, path)
                return {"ok": True, "path": str(path)}
            service = svc.AdvancedComponentService(
                feature="relogin_ocr", root=root, version=lambda: "1.2.2", download=download,
                asset_resolver=lambda version: {"ok": True, "assets": [runtime_meta, model_meta]})
            service._run()
            self.assertEqual(service._state, "failed")
            self.assertTrue(before["available"])
            self.assertEqual((packages.artifact_dir(runtime_id, root=root) /
                              "feature-helper.exe").read_bytes(), b"old-runtime")
            self.assertTrue(packages.feature_status("relogin_ocr", root=root)["available"])

    def test_split_identical_installed_assets_download_zero_bytes(self):
        from application import advanced_component_service as svc
        from infrastructure import component_packages as packages
        temp = tempfile.TemporaryDirectory(prefix="component-group-reuse-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        assets = []
        with mock.patch.object(packages, "_helper", return_value={"ok": True}), \
                mock.patch.object(packages, "supported", return_value=True):
            for artifact_id in ("relogin_ocr_runtime", "relogin_ocr_model"):
                archive, metadata = self._split_package(root, artifact_id, artifact_id, b"same")
                packages.install_artifact(archive, artifact_id, root=root)
                assets.append(metadata)
            download = mock.Mock(side_effect=AssertionError("相同资产不应下载"))
            service = svc.AdvancedComponentService(
                feature="relogin_ocr", root=root, version=lambda: "1.2.2", download=download,
                asset_resolver=lambda version: {"ok": True, "assets": assets})
            service._run()
            download.assert_not_called()
            self.assertEqual(service._state, "installed")
            self.assertEqual(service.snapshot()["total_bytes"], 0)

    def test_split_cancel_after_preparation_never_commits_group(self):
        assets = [dict(self.ASSET, artifact_id="relogin_ocr_runtime", name="runtime.zip"),
                  dict(self.ASSET, artifact_id="relogin_ocr_model", name="model.zip")]
        committed = mock.Mock()
        def cache_artifact(archive, artifact_id, **kwargs):
            self.assertTrue(service.cancel()["ok"])
            return {"artifact_id": artifact_id, "version": "1.2.3"}
        service, state = self._service(
            feature="relogin_ocr", asset_resolver=lambda version: {"ok": True, "assets": assets},
            find_cached_artifact=lambda asset, **kwargs: None,
            inspect_artifact=lambda archive, artifact_id: {"ok": True, "version": "1.2.3"},
            cache_artifact=cache_artifact, commit_artifact_group=committed)
        with tempfile.TemporaryDirectory(prefix="component-group-cancel-") as tmp:
            state["tmp"] = tmp
            service._run()
        self.assertEqual(service._state, "cancelled")
        committed.assert_not_called()
        self.assertEqual(state["hooks"], [])

    def test_split_runtime_change_reuses_installed_model(self):
        from application import advanced_component_service as svc
        from infrastructure import component_packages as packages
        temp = tempfile.TemporaryDirectory(prefix="component-model-reuse-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        runtime_id, model_id = "relogin_ocr_runtime", "relogin_ocr_model"
        old_runtime, _ = self._split_package(root, runtime_id, "old-runtime", b"old-runtime")
        model, model_meta = self._split_package(root, model_id, "model", b"same-model")
        new_runtime, runtime_meta = self._split_package(root, runtime_id, "new-runtime", b"new-runtime")
        with mock.patch.object(packages, "_helper", return_value={"ok": True}), \
                mock.patch.object(packages, "supported", return_value=True):
            packages.install_artifact(old_runtime, runtime_id, root=root)
            packages.install_artifact(model, model_id, root=root)
            downloaded = []
            def download(url, *, name, **kwargs):
                downloaded.append(name)
                folder = root / "download"
                folder.mkdir()
                path = folder / name
                shutil.copy2(new_runtime, path)
                return {"ok": True, "path": str(path)}
            service = svc.AdvancedComponentService(
                feature="relogin_ocr", root=root, version=lambda: "1.2.2", download=download,
                asset_resolver=lambda version: {"ok": True, "assets": [runtime_meta, model_meta]})
            service._run()
            self.assertEqual(service._state, "installed")
            self.assertEqual(downloaded, [new_runtime.name])
            self.assertEqual(service.snapshot()["total_bytes"], runtime_meta["bytes"])

    def test_split_network_failure_does_not_fall_back_to_single_package(self):
        """缺陷 6：拆分资产网络失败时就停在 failed，不许偷偷改下单体包。"""
        assets = [dict(self.ASSET, artifact_id="relogin_ocr_runtime", name="runtime.zip"),
                  dict(self.ASSET, artifact_id="relogin_ocr_model", name="model.zip")]
        downloads = []

        def download(url, *, name, **kwargs):
            downloads.append(name)
            if name == "runtime.zip":
                return {"ok": False, "error_code": "timeout", "text": "下载超时"}
            return {"ok": True, "path": str(Path(state["tmp"]) / name)}

        service, state = self._service(
            feature="relogin_ocr",
            asset_resolver=lambda _version: {"ok": True, "assets": assets,
                                             "asset": dict(self.ASSET, name="legacy.zip")},
            find_cached_artifact=lambda asset, **kwargs: None,
            inspect_artifact=lambda archive, artifact_id: {
                "ok": True, "artifact_id": artifact_id, "version": "1.2.3"},
            cache_artifact=lambda archive, artifact_id, **kwargs: {
                "artifact_id": artifact_id, "version": "1.2.3"},
            commit_artifact_group=lambda *_args, **_kwargs: {"ok": True},
            download=download)
        with tempfile.TemporaryDirectory(prefix="component-split-network-") as tmp:
            state["tmp"] = tmp
            service._run()
        self.assertEqual(downloads, ["runtime.zip"], "网络失败后不得改下单体包")
        self.assertEqual(service._state, "failed")
        self.assertEqual(service.snapshot()["error_code"], "timeout")
        self.assertEqual(state["installs"], [])

    def test_split_integrity_failure_falls_back_to_single_package(self):
        """拆分资产校验不过时仍允许回退，回退前要说清换成了完整组件包。"""
        assets = [dict(self.ASSET, artifact_id="phone_control_runtime", name="runtime.zip"),
                  dict(self.ASSET, artifact_id="phone_control_cloudflared",
                       name="cloudflared.zip")]
        downloads = []
        texts = []

        def download(url, *, name, **kwargs):
            downloads.append(name)
            if name == "legacy.zip":
                texts.append(service.snapshot()["text"])
            return {"ok": True, "path": str(Path(state["tmp"]) / name)}

        service, state = self._service(
            asset_resolver=lambda _version: {"ok": True, "assets": assets,
                                             "asset": dict(self.ASSET, name="legacy.zip")},
            find_cached_artifact=lambda asset, **kwargs: None,
            inspect_artifact=lambda archive, artifact_id: {
                "ok": False, "kind": "content_mismatch", "artifact_id": artifact_id,
                "text": "内容与清单不符"},
            cache_artifact=lambda archive, artifact_id, **kwargs: {
                "artifact_id": artifact_id, "version": "1.2.3"},
            commit_artifact_group=lambda *_args, **_kwargs: {"ok": True},
            download=download)
        with tempfile.TemporaryDirectory(prefix="component-split-integrity-") as tmp:
            state["tmp"] = tmp
            service._run()
        self.assertEqual(downloads, ["runtime.zip", "legacy.zip"])
        self.assertTrue(texts and "拆分资产校验不过" in texts[0])
        self.assertEqual(service._state, "installed")
        self.assertEqual([item[1] for item in state["installs"]], ["phone_control"])

    def test_second_click_while_downloading_is_busy(self):
        service, state = self._service()
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        state["gate"].clear()
        self.assertTrue(service.start()["ok"])
        second = service.start()
        self.assertFalse(second["ok"])
        self.assertEqual(second["error"], "busy")
        state["gate"].set()
        self._wait(service, "installed")

    def test_cancel_reports_cancelled_without_installing(self):
        service, state = self._service()
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        state["gate"].clear()
        service.start()
        service.cancel()
        state["gate"].set()
        snap = self._wait(service, "cancelled")
        self.assertEqual(snap["state"], "cancelled")
        self.assertEqual(state["installs"], [], "取消后绝不能安装")

    def test_bad_component_is_not_installed(self):
        service, state = self._service()
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        state["inspect_result"] = {"ok": False, "kind": "bad_manifest",
                                   "feature": "phone_control", "text": "清单不合法"}
        service.start()
        snap = self._wait(service, "failed")
        self.assertEqual(snap["error_code"], "bad_manifest")
        self.assertEqual(state["installs"], [])

    def test_ocr_service_installs_its_own_feature(self):
        service, state = self._service(feature="relogin_ocr")
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        state["inspect_result"] = {"ok": True, "kind": "component", "feature": "relogin_ocr",
                                   "version": "1.2.3", "text": "已识别"}
        service.start()
        snap = self._wait(service, "installed")
        self.assertEqual(snap["state"], "installed")
        self.assertEqual(state["installs"][0][1], "relogin_ocr", "装的是验证码识别，不是手机控制")

    def test_ocr_service_rejects_phone_package(self):
        service, state = self._service(feature="relogin_ocr")
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        service.start()     # 默认 inspect 回的是 phone_control 包
        snap = self._wait(service, "failed")
        self.assertEqual(snap["error_code"], "wrong_feature")
        self.assertIn("验证码识别", snap["text"])
        self.assertEqual(state["installs"], [])

    def test_cloudflared_version_mismatch_is_rejected(self):
        service, state = self._service()
        import tempfile
        state["tmp"] = tempfile.mkdtemp(prefix="advanced-component-")
        state["inspect_result"] = {"ok": True, "kind": "component",
                                   "feature": "phone_control", "version": "1.2.3",
                                   "cloudflared": "2020.1.1", "text": "已识别"}
        service.start()
        snap = self._wait(service, "failed")
        self.assertEqual(snap["error_code"], "cloudflared_version")

    def test_remove_marks_missing(self):
        service, state = self._service()
        state["installed"] = True
        result = service.remove()
        self.assertTrue(result["ok"])
        self.assertEqual(state["removed"], 1)
        self.assertEqual(service.snapshot()["state"], "available")

    def test_snapshot_reports_available_when_nothing_installed(self):
        service, _state = self._service()
        self.assertEqual(service.snapshot()["state"], "available")

    def test_no_release_asset_means_no_download(self):
        service, state = self._service(
            asset_resolver=lambda v: {"ok": False, "error": "no_component",
                                      "text": "这个版本没有发布组件包。"})
        service.start()
        snap = self._wait(service, "failed")
        self.assertEqual(snap["error_code"], "no_component")
        self.assertEqual(state["installs"], [])

    def test_cancel_during_verification_keeps_existing_component(self):
        entered, release = threading.Event(), threading.Event()
        def inspect(archive, key):
            entered.set()
            release.wait(2)
            return {"ok": True, "feature": "phone_control", "version": "1.2.3"}
        service, state = self._service(inspect=inspect)
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            state["tmp"] = directory
            service.start()
            self.assertTrue(entered.wait(2))
            try:
                self.assertTrue(service.cancel()["ok"])
            finally:
                release.set()
                service._thread.join(3)
        self.assertEqual(state["installs"], [])
        self.assertEqual(service.snapshot()["state"], "cancelled")

    def test_cancel_after_install_commit_is_refused(self):
        entered, release = threading.Event(), threading.Event()
        def install(*args, **kwargs):
            entered.set()
            release.wait(2)
            state["installed"] = True
        service, state = self._service(install=install)
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            state["tmp"] = directory
            service.start()
            self.assertTrue(entered.wait(2))
            try:
                result = service.cancel()
            finally:
                release.set()
                service._thread.join(3)
        self.assertFalse(result["ok"])
        self.assertEqual(service.snapshot()["state"], "installed")

    def test_thread_start_window_cannot_admit_second_transaction(self):
        from application import advanced_component_service as svc
        service, _state = self._service()
        replies = []
        class DelayedThread:
            def __init__(self, **kwargs):
                pass
            def is_alive(self):
                return False
            def start(self):
                if not replies:
                    replies.append(None)
                    replies[0] = service.start()
        with mock.patch.object(svc.threading, "Thread", DelayedThread):
            service.start()
        self.assertFalse(replies[0]["ok"])

    def test_removal_excludes_download_start(self):
        entered, release = threading.Event(), threading.Event()
        def remover(*args, **kwargs):
            entered.set()
            release.wait(2)
        service, state = self._service(remover=remover)
        state["tmp"] = "unused"
        worker = threading.Thread(target=service.remove)
        worker.start()
        self.assertTrue(entered.wait(2))
        try:
            result = service.start()
        finally:
            release.set()
            worker.join(3)
            if service._thread is not None:
                service._thread.join(3)
        self.assertFalse(result["ok"])


class PlanDoneNoticeTests(unittest.TestCase):
    """后台结束的系统通知：计数只写不为 0 的，名额已满、待核对单列。"""

    def test_counts_skip_zero_and_split_full_and_pending(self):
        from application import plan_service

        title, text = plan_service.plan_done_notice([
            {"status": "success"}, {"status": "already_signed"},
            {"status": "failed", "stop_reason": "full"},
            {"status": "failed", "stop_reason": "unconfirmed"},
            {"status": "failed", "stop_reason": "login_invalid"},
        ])
        self.assertEqual(title, "报名计划部分完成")
        self.assertEqual(text, "2 场成功，1 场待核对，1 场名额已满，1 场没成功")

    def test_all_success_says_done(self):
        from application import plan_service

        # 标题改三态（GL02，照原型 toastTitle）：全部成功由「已结束」改为「报名计划完成」
        self.assertEqual(plan_service.plan_done_notice([{"status": "success"}]),
                         ("报名计划完成", "1 场成功"))
        self.assertEqual(plan_service.plan_done_notice(
            [{"status": "success"}, {"status": "already_signed"}])[0], "报名计划完成")

    def test_partial_success_says_partly_done(self):
        from application import plan_service

        title, text = plan_service.plan_done_notice(
            [{"status": "success"}, {"status": "failed", "stop_reason": "full"}])
        self.assertEqual(title, "报名计划部分完成")
        self.assertEqual(text, "1 场成功，1 场名额已满")

    def test_none_success_says_ended(self):
        from application import plan_service

        # 旧标题「报名计划已结束」改为「报名计划结束」（GL02）；没有场次也算一场都没成功
        title, text = plan_service.plan_done_notice([{"status": "failed", "stop_reason": "full"}])
        self.assertEqual(title, "报名计划结束")
        self.assertEqual(text, "1 场名额已满", "为 0 的项不写")
        self.assertEqual(plan_service.plan_done_notice([]), ("报名计划结束", "这次计划没有场次。"))

    def test_tray_notify_without_icon_returns_false(self):
        from infrastructure import tray_icon

        self.assertFalse(tray_icon.TrayIcon().notify("标题", "正文"),
                         "托盘没起来时返回 False，不抛异常")


class LoginExpiredPushTests(unittest.TestCase):
    """登录失效推飞书：本次运行里有效过、之后变成失效才推，同一次失效只推一次。"""

    def _note(self):
        import ast
        import types

        tree = ast.parse((LOCAL / "app.py").read_text(encoding="utf-8"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "_note_login_conclusion")
        module = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace: dict = {}
        exec(compile(module, "<note-login>", "exec"), namespace)  # noqa: S102
        api = types.SimpleNamespace(_lock=threading.RLock(), _login_seen_valid=False,
                                    _expiry_pushed=False, pushes=[])
        api._push_login_expired = lambda: api.pushes.append(1)
        return types.MethodType(namespace["_note_login_conclusion"], api), api

    def test_push_once_after_valid_then_expired(self):
        note, api = self._note()
        note("expired")
        self.assertEqual(api.pushes, [], "启动时就失效（没校验成功过）不推")
        note("valid")
        note("expired")
        note("expired")
        note("unknown")
        self.assertEqual(api.pushes, [1], "同一次失效只推一次")
        note("valid")
        note("expired")
        self.assertEqual(api.pushes, [1, 1], "重新有效后再失效，再推一次")

    def test_push_text_has_no_account_fields(self):
        import ast

        tree = ast.parse((LOCAL / "app.py").read_text(encoding="utf-8"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "_push_login_expired")
        source = ast.unparse(node)
        for banned in ("username", "student", "token", "CREDENTIAL_FILE", "SESSION_FILE"):
            self.assertNotIn(banned, source, "飞书消息不得带账号或登录信息")
        self.assertIn("回电脑或手机上重新登录", source)


class _OnceSink:
    """登录进程 stdin 替身：只在内存里记下发的行，绝不落盘。"""

    def __init__(self):
        self.written = []

    def write(self, text):
        self.written.append(str(text))

    def flush(self):
        pass


class _OncePipe:
    """登录进程 stdout 替身：测试推一行它吐一行，close 才给 EOF。"""

    def __init__(self):
        import queue
        self._q = queue.Queue()

    def __iter__(self):
        return self

    def __next__(self):
        item = self._q.get()
        if item is None:
            raise StopIteration
        return item

    def push(self, line):
        self._q.put(line + "\n")

    def close(self):
        self._q.put(None)


class _OnceWorker:
    def __init__(self):
        self.stdin = _OnceSink()
        self.stdout = _OncePipe()

    def terminate(self):
        self.stdout.close()


class _FakeCredentialStore:
    """本机加密凭据的内存替身：记下有没有写过，绝不碰 DPAPI 和磁盘。"""

    def __init__(self):
        self.doc = None
        self.bad = False
        self.saves = 0

    @staticmethod
    def _protect(raw):
        return raw

    def has_credentials(self, _path):
        return bool(self.doc)

    def load(self, _path):
        if not self.doc:
            raise ValueError("没有保存的账号")
        return dict(self.doc)

    def stored_username(self, path):
        return self.load(path)["username"]

    def is_bad(self, _path):
        return self.bad

    def mark_bad(self, _path):
        self.bad = True

    def clear_bad(self, _path):
        self.bad = False

    def save(self, _path, username, password):
        self.saves += 1
        self.doc = {"username": str(username), "password": str(password)}
        self.bad = False

    def clear(self, _path):
        self.doc = None
        self.bad = False
        return True


class OnceCredentialAutoReloginTests(unittest.TestCase):
    """冲突 5（settings-gap CR20）：只用这一次的账号密码在这次运行里也能自动登录。

    学校、验证码识别、登录进程和本机加密存储全部替身；账号密码都是虚构的。
    """

    ONCE_USER = "once-user-77"
    ONCE_PASS = "once-pw-fictional-9"
    SAVED_USER = "saved-user-01"
    SAVED_PASS = "saved-pw-fictional-3"

    def setUp(self):
        import shutil

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        tmp = tempfile.mkdtemp(prefix="campus-once-autologin-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.dir = Path(tmp)
        self.data = self.dir / "data"
        self.data.mkdir()
        self.store = _FakeCredentialStore()
        self.ocr = True
        self.worker_commands = []
        for patch in (
            mock.patch.object(local_app, "PREFS", self.dir / "ui.json"),
            mock.patch.object(local_app, "DEVICE_FILE", self.dir / "devices.json"),
            mock.patch.object(local_app, "DATA_DIR", self.data),
            mock.patch.object(local_app, "CREDENTIAL_FILE", self.data / "cred.json"),
            mock.patch.object(local_app, "LOG_FILE", self.data / "grab.log"),
            mock.patch.object(local_app, "ensure_data_dir", lambda: self.data),
            mock.patch.object(local_app, "_credential_store", self.store),
            mock.patch.object(local_app, "_CREDENTIAL_STORE_OK", None),
            mock.patch.object(local_app, "worker_command",
                              lambda *args: ["fake-worker"] + list(args)),
            mock.patch.object(local_app, "DEMO", True),
            mock.patch.object(local_app._advanced_features, "feature_ready",
                              lambda *a, **k: self.ocr),
            mock.patch.object(local_app._advanced_features, "module_available",
                              lambda _module: False),
            mock.patch.object(local_app._tunnel_manager, "tailscale_endpoint",
                              lambda *a, **k: {"available": False, "error": "tailscale_missing",
                                               "state": "missing", "text": "没装"}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()
        self.addCleanup(self.api.shutdown)
        # 构造完才放开 DEMO：自动登录在演示模式下一律没资格。这个补丁最后登记、
        # 最先收回，shutdown 时 DEMO 已回到 True，不写任何生命周期记录
        demo = mock.patch.object(local_app, "DEMO", False)
        demo.start()
        self.addCleanup(demo.stop)
        self.api._terms_gate = lambda: None
        self.events = []
        self.api._emit = lambda kind, payload: self.events.append((kind, payload))
        self.workers = []
        self._wire_relay(self.api._relay)

    def _wire_relay(self, relay):
        relay._emit = self.api._emit

        def spawn(_args):
            worker = _OnceWorker()
            self.workers.append(worker)
            return worker
        relay._spawn = spawn

    def _stage_once(self):
        result = self.api.prepare_phone_relogin(self.ONCE_USER, self.ONCE_PASS, save=False)
        self.assertTrue(result["ok"], result)

    def _save(self):
        self.store.doc = {"username": self.SAVED_USER, "password": self.SAVED_PASS}

    def _sent_credentials(self):
        self.assertTrue(self.workers, "应该已经起了一个登录进程")
        first = json.loads(self.workers[-1].stdin.written[0])
        self.assertEqual(first["kind"], "credentials")
        return first

    def _wait(self, predicate, what):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.02)
        self.fail("等不到：%s" % what)

    def _fail_with_bad_password(self, flow_id):
        worker = self.workers[-1]
        worker.stdout.push("[login] " + json.dumps(
            {"kind": "failed", "flow_id": flow_id, "error": "bad_password"}))
        worker.stdout.close()
        self._wait(lambda: not self.api._relay.state()["live"], "这一场结束")
        self._wait(lambda: self.api._once_creds_rejected, "收尾回调记下密码不对")

    # ---------- 资格 ----------
    def test_only_this_run_with_ocr_enabled_is_eligible(self):
        self.assertFalse(self.api._auto_relogin_eligible(), "什么账号都没有时没资格")
        self._stage_once()
        self.assertTrue(self.api._auto_relogin_eligible(),
                        "只用这一次的账号 + 识别已启用，就和保存过一样能自动登录")
        self.assertEqual(self.api._relogin_wait_s(), self.local_app.RELOGIN_WAIT_S,
                         "电脑能自己登录，报名进程就该等它")

    def test_only_this_run_without_ocr_is_not_eligible(self):
        self.ocr = False
        self._stage_once()
        self.assertFalse(self.api._auto_relogin_eligible(), "识别没启用这一条不放宽")
        self.assertEqual(self.api._relogin_wait_s(), 0.0)

    def test_saved_copy_staged_for_the_phone_is_not_a_this_run_credential(self):
        self._save()
        self.assertTrue(self.api.prepare_phone_relogin()["ok"], "不带输入时暂存的是保存的账号")
        self.store.doc = None
        self.assertTrue(self.api._relay.has_staged())
        self.assertFalse(self.api._auto_relogin_eligible(),
                         "暂存区里保存账号的副本不算「只用这一次」（be-fields A3）")

    # ---------- 取哪一份 ----------
    def test_only_this_run_is_used_when_nothing_is_saved(self):
        self._stage_once()
        result = self.api._begin_auto_relogin_once()
        self.assertTrue(result["ok"], result)
        sent = self._sent_credentials()
        self.assertEqual(sent["username"], self.ONCE_USER)
        self.assertEqual(sent["password"], self.ONCE_PASS)
        self.assertEqual(self.api._relay_creds_source, "typed")
        self.assertEqual(self.store.saves, 0, "只用这一次的账号不落盘")
        self.api._relay.cancel()

    def test_saved_credential_wins_when_both_are_present(self):
        self._stage_once()
        self._save()
        self.assertTrue(self.api._auto_relogin_eligible())
        result = self.api._begin_auto_relogin_once()
        self.assertTrue(result["ok"], result)
        sent = self._sent_credentials()
        self.assertEqual(sent["username"], self.SAVED_USER, "两者都有时以保存的为准")
        self.assertEqual(sent["password"], self.SAVED_PASS)
        self.assertEqual(self.api._relay_creds_source, "saved")
        self.api._relay.cancel()

    # ---------- 学校说密码错 ----------
    def test_wrong_password_pauses_and_clears_the_this_run_credential(self):
        self._stage_once()
        result = self.api._begin_auto_relogin_once()
        self.assertTrue(result["ok"], result)
        self._fail_with_bad_password(result["flow_id"])
        self.assertFalse(self.api._relay.has_staged(), "内存里那份被清掉，绝不再试")
        self.assertFalse(self.store.bad, "没有保存的账号，不在磁盘上留暂停标记")
        self.assertTrue(self.api._auto_relogin_paused(), "进入「暂停到更新密码」")
        self.assertFalse(self.api._auto_relogin_eligible())
        self.assertEqual(self.api._relogin_wait_s(), 0.0)
        self.assertEqual(self.api._begin_auto_relogin_once()["error"], "bad_password")
        spawned = len(self.workers)
        self.api._auto_relogin.observe_check("expired")
        self.api._auto_relogin.request_recover()
        self.api._auto_relogin.tick()
        self.assertEqual(self.api._auto_relogin.snapshot()["state"], "paused")
        self.assertEqual(len(self.workers), spawned, "暂停时不再起登录进程")
        # 用户输入新的账号密码才解除
        self._stage_once()
        self.assertFalse(self.api._auto_relogin_paused())
        self.assertTrue(self.api._auto_relogin_eligible())

    def test_saving_a_new_password_also_lifts_the_pause(self):
        self._stage_once()
        result = self.api._begin_auto_relogin_once()
        self._fail_with_bad_password(result["flow_id"])
        self.assertTrue(self.api._auto_relogin_paused())
        with mock.patch.object(self.local_app, "_credential_store_available", lambda: True):
            self.assertTrue(self.api.save_relogin_credentials(
                self.SAVED_USER, self.SAVED_PASS)["ok"])
        self.assertFalse(self.api._auto_relogin_paused())
        self.assertTrue(self.api._auto_relogin_eligible())

    # ---------- 进程退出 / 中继服务重建 ----------
    def test_eligibility_disappears_when_the_relay_goes_away(self):
        from application.login_relay_service import LoginRelayService

        self._stage_once()
        self.assertTrue(self.api._auto_relogin_eligible())
        old = self.api._relay
        rebuilt = LoginRelayService(spawn=lambda _args: _OnceWorker(), now=time.monotonic)
        self.addCleanup(rebuilt.shutdown)
        self.api._relay = rebuilt
        old.shutdown()
        self.assertEqual(self.api._relay_creds_source, "typed", "来源标签还在，账号已经没了")
        self.assertFalse(self.api._auto_relogin_eligible(), "中继服务重建后资格消失")
        self.api._relay = old
        self.assertFalse(old.has_staged(), "关闭收尾清掉了暂存")
        self.assertFalse(self.api._auto_relogin_eligible(), "程序退出（shutdown）后资格消失")

    # ---------- 不落盘、不进日志、不进快照 ----------
    def test_password_never_reaches_logs_snapshots_or_disk(self):
        self._stage_once()
        self.assertTrue(self.api._auto_relogin_eligible())
        result = self.api._begin_auto_relogin()
        self.assertTrue(result["ok"], result)
        live = [self.api.advanced_features_state(), self.api.phone_access_state(),
                self.api._phone_raw_state(), self.api._auto_relogin.snapshot()]
        self._fail_with_bad_password(result["flow_id"])
        after = [self.api.advanced_features_state(), self.api.phone_access_state(),
                 self.api._phone_raw_state(), self.api._auto_relogin.snapshot()]
        dump = json.dumps(live + after + [list(self.events)], ensure_ascii=False, default=str)
        self.assertNotIn(self.ONCE_PASS, dump, "快照与界面事件里出现了密码")
        self.assertNotIn(self.ONCE_USER, dump, "快照与界面事件里只许出现打码账号")
        log = self.data / "grab.log"
        self.assertTrue(log.is_file(), "自动登录的发起与失败应该写了日志行")
        log_text = log.read_text(encoding="utf-8")
        self.assertIn("auto_relogin_started", log_text)
        self.assertNotIn(self.ONCE_PASS, log_text)
        self.assertNotIn(self.ONCE_USER, log_text)
        self.assertEqual(self.store.saves, 0, "只用这一次的账号没有写进加密存储")
        for item in self.dir.rglob("*"):
            if item.is_file():
                self.assertNotIn(self.ONCE_PASS, item.read_text(encoding="utf-8", errors="replace"),
                                 "临时目录里的文件出现了密码")


class PhonePcListErrorTests(unittest.TestCase):
    """BE2/EX05：手机快照的 pc_list_error（电脑侧最近一次拉活动列表失败）。

    正常为 None；失败带固定安全短语与北京 HH:MM（不放堆栈/路径/账号）；
    成功刷新即清空；worker 的原始输出与异常文本不得透传进快照。
    """

    def setUp(self):
        import shutil

        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        self.local_app = local_app
        tmp = tempfile.mkdtemp(prefix="campus-pclist-err-")
        self.addCleanup(shutil.rmtree, tmp, True)
        data = Path(tmp) / "data"
        data.mkdir()
        for patch in (
            mock.patch.object(local_app, "PREFS", Path(tmp) / "ui.json"),
            mock.patch.object(local_app, "DATA_DIR", data),
            mock.patch.object(local_app, "DEMO", True),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.api._phone = FakePhoneService()

    # ---------- 正常态 ----------
    def test_snapshot_has_null_pc_list_error_by_default(self):
        raw = self.api._phone_raw_state()
        self.assertIsNone(raw["pc_list_error"],
                          "没失败过：pc_list_error 必须是 null（纯增量字段，旧字段不动）")

    # ---------- 失败态 ----------
    def test_failure_records_short_reason_and_beijing_hhmm(self):
        self.api._note_pc_list_error("活动列表没能加载")
        raw = self.api._phone_raw_state()
        error = raw["pc_list_error"]
        self.assertIsNotNone(error)
        self.assertEqual(error["reason"], "活动列表没能加载")
        self.assertRegex(error["at"], r"^\d{2}:\d{2}$",
                         "时刻必须是北京 HH:MM（school_time_text 口径）")

    def test_error_at_prefers_the_last_successful_refresh_time(self):
        """R-P3-4：pc_list_error.at 优先取最后一次成功刷新的时刻——原型句
        「现在显示的是 {HH:MM} 更新的列表」说的是手机正在展示的那份列表
        （来自最后一次成功刷新），不是失败发生的时刻；从没成功过才退失败时刻。
        时钟钉在两个相差一小时的时刻上，避免 HH:MM 粒度下两刻同分导致断言失真。"""
        real_clock = self.api._clock_now
        self.addCleanup(setattr, self.api, "_clock_now", real_clock)
        self.api._clock_now = lambda: 1700000000.0          # 北京 2023-11-15 06:13
        self.api._do_list_inner()          # DEMO：走成功分支，记下成功时刻
        ok_at = self.api._pc_list_ok_at
        self.assertRegex(ok_at, r"^\d{2}:\d{2}$", "成功时刻也是北京 HH:MM")
        self.api._clock_now = lambda: 1700000000.0 + 3600   # 一小时后才失败
        self.api._note_pc_list_error("活动列表没能加载")
        error = self.api._phone_raw_state()["pc_list_error"]
        self.assertIsNotNone(error)
        self.assertEqual(error["at"], ok_at,
                         "at 取最后一次成功刷新的时刻，不是失败时刻")
        # 再次成功：错误清空，成功时刻随刷新推进到新的 HH:MM
        self.api._do_list_inner()
        self.assertIsNone(self.api._phone_raw_state()["pc_list_error"])
        self.assertNotEqual(self.api._pc_list_ok_at, ok_at,
                            "成功时刻随刷新推进（不是停在第一次）")

    def test_worker_output_and_exceptions_never_reach_the_field(self):
        """失败原因只许固定短语：带路径/账号样子的字符串即使被调用方塞进来，
        也不该由这里负责透传——钉住「原因来自常量表」这一层。"""
        self.api._note_pc_list_error("活动列表没能加载")
        raw = self.api._phone_raw_state()
        self.assertEqual(raw["pc_list_error"],
                         {"reason": "活动列表没能加载", "at": raw["pc_list_error"]["at"]})
        # 投影后仍只这两个键，值是短语与时刻
        from domain.phone_rules import project_state
        projected = project_state(self.api._phone_raw_state())
        self.assertEqual(set(projected["pc_list_error"].keys()), {"reason", "at"})

    # ---------- 成功清空 ----------
    def test_successful_list_refresh_clears_the_error(self):
        self.api._note_pc_list_error("活动列表没能加载")
        self.assertIsNotNone(self.api._phone_raw_state()["pc_list_error"])
        self.api._do_list_inner()          # DEMO：走成功分支并清空
        self.assertIsNone(self.api._phone_raw_state()["pc_list_error"],
                          "成功刷新后必须清空，手机不再亮「列表没加载」")

    def test_demo_snapshot_keeps_other_fields_unchanged(self):
        """纯增量：pc_list_error 进来后，activities/login/busy 等旧键照旧。"""
        raw = self.api._phone_raw_state()
        self.assertIn("activities", raw)
        self.assertIn("login", raw)
        self.assertIn("busy", raw)
        self.assertIn("business_clock", raw)
        self.assertIn("pc_list_error", raw)


class VersionSwitchLaunchTests(unittest.TestCase):
    """C1：版本目录切换的启动器拉起后，主程序自己走现有退出路径，界面不停在「启动中…」。

    全部替身：不真的起进程、不真的关窗口；Api 经 stop_auto_relogin_on_cleanup 收线程。
    """

    def _app(self):
        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 仅在缺依赖的环境触发
            self.skipTest("local/app.py 无法导入：%s" % exc)
        return local_app

    def _api(self, local_app):
        from fixtures.business_clock import TestWallClock
        api = stop_auto_relogin_on_cleanup(self, local_app.Api(clock=TestWallClock()))
        api._emit = mock.Mock()
        api._update_result = {"state": "ready_to_restart", "latest_version": "1.2.2",
                              "request_id": "rid-update"}
        api._update_staging_path = "D:/versions/.staging-rid-update"
        return api

    def _launch(self, local_app, api, *, popen):
        """在「冻结 + 启动器存在」的替身环境里调一次 update_launch，返回 (结果, 被推迟的动作)。"""
        scheduled = []
        with tempfile.TemporaryDirectory() as name:
            launcher = Path(name) / "update-launcher.exe"
            launcher.write_bytes(b"launcher")
            paths = {"root": Path("D:/versions"), "current_file": Path("D:/current.json"),
                     "base_dir": Path("D:/versions/1.2.1")}
            with mock.patch.object(local_app.sys, "frozen", True, create=True):
                with mock.patch.object(local_app, "resolve_update_launcher_path",
                                       return_value=launcher):
                    with mock.patch.object(local_app, "update_version_paths",
                                           return_value=paths):
                        with mock.patch.object(local_app.subprocess, "Popen", popen):
                            with mock.patch.object(
                                    local_app, "defer_close_action",
                                    lambda callback, delay=0.25: scheduled.append((callback, delay))):
                                result = api.update_launch("rid-update")
        return result, scheduled

    def test_launcher_started_publishes_started_text_and_schedules_exit(self):
        local_app = self._app()
        api = self._api(local_app)
        popen = mock.Mock()
        result, scheduled = self._launch(local_app, api, popen=popen)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["text"].startswith("更新启动器已启动"), result["text"])
        popen.assert_called_once()
        payloads = [call.args[1] for call in api._emit.call_args_list
                    if call.args[0] == "update"]
        self.assertEqual(payloads[-1]["state"], "launching")
        self.assertTrue(payloads[-1]["text"].startswith("更新启动器已启动"), payloads[-1])
        self.assertEqual(len(scheduled), 1, "启动器拉起后必须安排一次退出")
        callback, delay = scheduled[0]
        self.assertTrue(0.5 <= delay <= 3.0, "留约 1 秒让界面先收到文案")
        api.request_window_close = mock.Mock(return_value={"ok": True})
        callback()
        api.request_window_close.assert_called_once_with("exit")

    def test_launcher_failure_does_not_schedule_exit(self):
        local_app = self._app()
        api = self._api(local_app)
        result, scheduled = self._launch(
            local_app, api, popen=mock.Mock(side_effect=OSError("denied")))
        self.assertFalse(result["ok"])
        self.assertEqual(scheduled, [], "启动器没起来时不能关掉主程序")
        payloads = [call.args[1] for call in api._emit.call_args_list
                    if call.args[0] == "update"]
        self.assertEqual(payloads[-1]["state"], "failed")


class VersionSweepWiringTests(unittest.TestCase):
    """D3：冻结态且正从 versions/<当前版本>/ 运行时，启动后后台清理一次版本目录。"""

    def _app(self):
        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 仅在缺依赖的环境触发
            self.skipTest("local/app.py 无法导入：%s" % exc)
        return local_app

    def test_not_frozen_or_not_in_version_dir_does_nothing(self):
        local_app = self._app()
        sweep = mock.Mock()
        for frozen, here in ((False, Path("D:/p/versions/1.2.2")),
                             (True, Path("D:/p/app")),
                             (True, Path("D:/p/versions/9.9.9"))):
            with self.subTest(frozen=frozen, here=str(here)):
                thread = local_app.sweep_versions_in_background(
                    frozen=frozen, here=here, version="1.2.2", sweep=sweep)
                self.assertIsNone(thread)
        sweep.assert_not_called()

    def test_frozen_version_dir_sweeps_once_and_keeps_running_dir(self):
        local_app = self._app()
        calls = []

        def sweep(root, **options):
            calls.append((root, options))
            return {"removed": [], "failed": []}

        thread = local_app.sweep_versions_in_background(
            frozen=True, here=Path("D:/p/versions/1.2.2"), version="1.2.2", sweep=sweep)
        thread.join(5)
        self.assertEqual(len(calls), 1)
        root, options = calls[0]
        self.assertEqual(Path(root), Path("D:/p/versions"))
        self.assertEqual(Path(options["current_file"]), Path("D:/p/current.json"))
        self.assertEqual(Path(options["keep_dir"]), Path("D:/p/versions/1.2.2"))

    def test_sweep_exception_is_logged_not_raised(self):
        local_app = self._app()
        logged = []

        def sweep(root, **options):
            raise RuntimeError("boom")

        thread = local_app.sweep_versions_in_background(
            frozen=True, here=Path("D:/p/versions/1.2.2"), version="1.2.2",
            sweep=sweep, log=lambda **fields: logged.append(fields))
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(logged, [{"error": "RuntimeError"}])

    def test_undeletable_entries_are_logged_as_a_count_only(self):
        """日志只带数量，不带目录名或路径（经 Api._log_event 落 grab.log）。"""
        local_app = self._app()
        logged = []
        thread = local_app.sweep_versions_in_background(
            frozen=True, here=Path("D:/p/versions/1.2.2"), version="1.2.2",
            sweep=lambda root, **options: {"removed": [], "failed": ["0.9.0", ".old-x"]},
            log=lambda **fields: logged.append(fields))
        thread.join(5)
        self.assertEqual(logged, [{"failed": 2}])


class VersionSwitchSelectionTests(unittest.TestCase):
    """C3：只有能走版本目录切换的环境才下载版本目录包，否则直接走完整安装器。

    独立 EXE、源码态、缺 update-launcher、不在 versions/<当前版本>/ 下运行时，
    旧代码仍下载版本目录包并 stage，之后 update_launch 又拒绝切换，用户走进死胡同。
    """

    NAME = "campus-activity-watch-installer-v1.2.2-win-x64.exe"
    BASE = "https://example.invalid/releases/download/v1.2.2/"

    def _app(self):
        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 仅在缺依赖的环境触发
            self.skipTest("local/app.py 无法导入：%s" % exc)
        return local_app

    def _download(self, local_app, *, switch_available, payload_effect=None):
        """跑一次 _do_update_download，返回 (api, 安装器下载替身, 版本包下载替身)。"""
        from fixtures.business_clock import TestWallClock
        api = stop_auto_relogin_on_cleanup(self, local_app.Api(clock=TestWallClock()))
        api._emit = mock.Mock()
        target = {"version": "1.2.2",
                  "files": [{"path": "a.exe", "bytes": 1, "sha256": "aa" * 32}],
                  "target_manifest_sha256": "00" * 32}
        installer = {"name": self.NAME, "url": self.BASE + self.NAME,
                     "bytes": 1024, "sha256": "ab" * 32,
                     "full": {"name": "payload.zip", "url": self.BASE + "payload.zip",
                              "bytes": 4, "sha256": "cd" * 32,
                              "target_version": "1.2.2", "target_manifest": target}}
        api._update_installer = installer
        api._update_result = {"request_id": "check-1", "state": "available",
                              "latest_version": "1.2.2", "installer": installer}
        installer_path = str(Path(tempfile.gettempdir()) / "campus-update-x" / self.NAME)
        with mock.patch.object(local_app, "version_switch_available",
                               return_value=switch_available):
            with mock.patch.object(local_app.updater, "download_installer", return_value={
                    "ok": True, "path": installer_path, "bytes": 1024,
                    "sha256": "ab" * 32}) as installer_download:
                with mock.patch.object(
                        local_app.updater, "download_payload",
                        side_effect=payload_effect
                        or AssertionError("不应下载版本目录包")) as payload_download:
                    api._do_update_download("dl-1", installer)
        return api, installer_download, payload_download

    def test_unavailable_environment_downloads_installer_only(self):
        local_app = self._app()
        api, installer_download, payload_download = self._download(
            local_app, switch_available=False)
        payload_download.assert_not_called()
        installer_download.assert_called_once()
        self.assertEqual(api._update_result["state"], "ready_to_install")

    def test_switch_environment_still_downloads_version_payload(self):
        local_app = self._app()
        # 用「用户取消」结束版本包下载：这条用例只看选路，不走后续 stage
        api, installer_download, payload_download = self._download(
            local_app, switch_available=True,
            payload_effect=lambda *args, **kwargs: {
                "ok": False, "error_code": "cancelled", "text": "已取消"})
        payload_download.assert_called_once()
        installer_download.assert_not_called()

    def _available(self, local_app, *, frozen, here, launcher_exists):
        with tempfile.TemporaryDirectory() as name:
            launcher = Path(name) / "update-launcher.exe"
            if launcher_exists:
                launcher.write_bytes(b"launcher")
            return local_app.version_switch_available(
                frozen=frozen, here=Path(here), version="1.2.2", launcher=launcher)

    def test_source_state_is_unavailable(self):
        local_app = self._app()
        self.assertFalse(self._available(
            local_app, frozen=False, here="D:/p/versions/1.2.2", launcher_exists=True))

    def test_missing_launcher_is_unavailable(self):
        local_app = self._app()
        self.assertFalse(self._available(
            local_app, frozen=True, here="D:/p/versions/1.2.2", launcher_exists=False))

    def test_not_running_from_version_dir_is_unavailable(self):
        local_app = self._app()
        for here in ("D:/p/app", "D:/p/versions/9.9.9"):
            with self.subTest(here=here):
                self.assertFalse(self._available(
                    local_app, frozen=True, here=here, launcher_exists=True))

    def test_frozen_version_dir_with_launcher_is_available(self):
        local_app = self._app()
        self.assertTrue(self._available(
            local_app, frozen=True, here="D:/p/versions/1.2.2", launcher_exists=True))


class WindowVisibilityTests(unittest.TestCase):
    """window_visibility：界面自动刷新列表前问后端「窗口是不是藏到托盘了」。

    pywebview 隐藏窗口时 document.hidden 是否为真无法离线验证，所以界面同时问后端
    的 _window_hidden；这个接口只读、只回一个布尔，不带别的字段。
    """

    def setUp(self):
        try:
            import app as local_app
        except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
            self.skipTest("无法导入 local/app.py：%s" % exc)
        tmp = tempfile.mkdtemp(prefix="campus-window-visibility-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for patch in (
            mock.patch.object(local_app, "PREFS", Path(tmp) / "ui.json"),
            mock.patch.object(local_app, "DEMO", True),
            mock.patch.object(local_app, "DEVICE_FILE", Path(tmp) / "devices.json"),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())

    def test_reports_hidden_true_when_window_is_in_the_tray(self):
        self.api._window_hidden = True
        self.assertEqual(self.api.window_visibility(), {"hidden": True})

    def test_reports_hidden_false_when_window_is_shown(self):
        self.api._window_hidden = False
        self.assertEqual(self.api.window_visibility(), {"hidden": False})

    def test_returns_only_the_hidden_key(self):
        self.api._window_hidden = True
        self.assertEqual(set(self.api.window_visibility()), {"hidden"})


class VersionDownloadFlowTests(unittest.TestCase):
    """U1/U2：版本目录更新的取消口径，以及推给界面的失败文案不带本机路径。"""

    VERSION_BASE = "1.2.1"

    def _installer(self):
        manifest = {"version": "1.2.2", "files": []}
        return {
            "name": "setup.exe", "url": "https://example.invalid/setup.exe",
            "bytes": 10, "sha256": "ab" * 32,
            "full": {"name": "full.zip", "url": "https://example.invalid/full.zip",
                     "bytes": 10, "sha256": "cd" * 32, "target_version": "1.2.2",
                     "target_manifest": manifest},
            "deltas": [{"name": "delta.zip", "url": "https://example.invalid/delta.zip",
                        "bytes": 5, "sha256": "ef" * 32, "target_version": "1.2.2",
                        "base_version": self.VERSION_BASE, "target_manifest": manifest}],
        }

    def _run(self, *, stage_update, download_delta, download_full, fallback=None,
             cleanup=None, installer=None):
        state = FakeState()
        state._update_staging_path = ""
        published = []
        tmp = Path(tempfile.gettempdir()) / "campus-version-flow"
        update_service.run_version_download(
            state, "req-v", installer or self._installer(),
            download=download_full,
            publish=lambda payload, finished: published.append((payload, finished)),
            current_version=self.VERSION_BASE, latest_url="https://example.invalid/latest",
            stage_update=stage_update, base_dir=tmp / "base",
            staging_dir=tmp / ".staging-req-v",
            target_manifest={"version": "1.2.2", "files": []},
            target_version="1.2.2", download_delta=download_delta,
            download_full=download_full, cleanup_download=cleanup,
            download_installer_fallback=fallback)
        return state, published

    def test_cancel_during_full_download_after_delta_failure_is_cancelled(self):
        """增量应用失败改下完整包，用户此时取消：回到 available/cancelled，不改走安装器兜底。"""
        delta_path = str(Path(tempfile.gettempdir()) / "campus-version-flow" / "delta.zip")
        cleaned, fallbacks = [], []

        def fallback(url, **kwargs):
            fallbacks.append(url)
            return {"ok": False, "error_code": "cancelled", "text": "已取消"}

        state, published = self._run(
            stage_update=lambda *a, **k: {"ok": False, "error_code": "apply_failed",
                                          "text": "bad"},
            download_delta=lambda url, **k: {"ok": True, "path": delta_path},
            download_full=lambda url, **k: {"ok": False, "error_code": "cancelled",
                                            "text": "已取消"},
            fallback=fallback, cleanup=cleaned.append)
        final, finished = published[-1]
        self.assertTrue(finished)
        self.assertEqual(final["state"], "available", final)
        self.assertEqual(final["error_code"], "cancelled")
        self.assertEqual(fallbacks, [], "取消之后不能再去下载完整安装器")
        self.assertEqual(cleaned, [delta_path], "半成品增量包要清理")

    def test_stage_failure_text_pushed_to_ui_carries_no_local_path(self):
        """staging 抛出带路径的异常时，界面只拿到固定中文句子，细节只进运行记录。"""
        import updater
        installer = self._installer()
        installer.pop("deltas")
        missing = Path(tempfile.gettempdir()) / "campus-secret-dir" / "full.zip"
        state, published = self._run(
            stage_update=updater.stage_update,
            download_delta=None,
            download_full=lambda url, **k: {"ok": True, "path": str(missing)},
            installer=installer)
        final, _ = published[-1]
        self.assertEqual(final["state"], "failed", final)
        self.assertEqual(final["error_code"], "apply_failed")
        self.assertNotIn("campus-secret-dir", final["text"])
        for separator in ("/", chr(92)):
            self.assertNotIn(separator, final["text"])
        logs = [payload for kind, payload in state.events if kind == "log"]
        self.assertTrue(any("FileNotFoundError" in str(item) for item in logs), logs)


class UpdateCheckLogTests(unittest.TestCase):
    def test_skipped_manifest_entries_are_recorded_in_the_run_log(self):
        """U6：清单里被跳过的未用项写一条运行记录，但不进推给界面的结论。"""
        state = FakeState()
        update_service.run_check(
            state, "req-s", fetch=lambda v: {"state": "current", "latest_version": v,
                                             "manifest_skipped": ["future-tool-notes.txt"]},
            current_version="1.2.2", latest_url="https://example.invalid/latest")
        logs = [payload for kind, payload in state.events if kind == "log"]
        self.assertTrue(any("future-tool-notes.txt" in str(item) for item in logs), state.events)
        updates = [payload for kind, payload in state.events if kind == "update"]
        self.assertNotIn("manifest_skipped", updates[-1])


if __name__ == "__main__":
    unittest.main()
