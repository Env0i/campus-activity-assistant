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
        archive = self.dir / "phone_control-1.2.0-windows-x64.zip"
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", json.dumps({
                "schema": 1, "feature": "phone_control", "platform": "windows-x64",
                "entry": "feature-helper.exe", "version": "1.2.0",
                "files": {"feature-helper.exe": "0" * 64,
                          "bin/cloudflared.exe": "0" * 64},
                "cloudflared": {"version": self.local_app._component_packages.CLOUDFLARED_VERSION,
                                "sha256": "0" * 64},
            }))
        result = self.api.install_advanced_feature("phone_control", str(archive))
        # 源码版走的是已装好的 Python 依赖：组件包对它没用，必须说人话而不是装上去
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "source_build")
        self.assertIn("cloudflared.exe", result["text"])

    def test_an_exe_for_the_ocr_feature_is_told_to_pick_a_zip(self):
        exe = self._file("ocr.exe")
        info = self.api.inspect_advanced_component("relogin_ocr", str(exe))
        self.assertFalse(info["ok"])
        self.assertEqual(info["kind"], "not_zip")


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

    def test_all_success_or_none_success_says_ended(self):
        from application import plan_service

        self.assertEqual(plan_service.plan_done_notice([{"status": "success"}]),
                         ("报名计划已结束", "1 场成功"))
        title, text = plan_service.plan_done_notice([{"status": "failed", "stop_reason": "full"}])
        self.assertEqual(title, "报名计划已结束")
        self.assertEqual(text, "1 场名额已满", "为 0 的项不写")

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


if __name__ == "__main__":
    unittest.main()
