# -*- coding: utf-8 -*-
"""发布审核发现的并发与故障边界；全程离线、数据只在临时目录。"""
import subprocess
import sys
import threading
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure import component_packages as cp
from domain import phone_rules


class PersistentDiscoveryTests(unittest.TestCase):
    def test_csrf_discovery_survives_browser_session_end(self):
        self.assertIn("Max-Age=", phone_rules.csrf_cookie_header_value("non-authorizing-test"))


class ApiComponentCoordinationTests(unittest.TestCase):
    def setUp(self):
        import app
        self.app = app
        self.api = app.Api.__new__(app.Api)
        self.api._lock = threading.Lock()
        self.api._phone_access_lock = threading.RLock()
        self.api._credential_lock = threading.RLock()
        self.api._closing = False
        self.api._advanced_busy = False
        self.api._is_busy_locked = lambda: False
        self.api._emit = mock.Mock()
        self.api._component_service = mock.Mock()
        self.api._component_service.start.return_value = {"ok": True}

    def test_online_download_reserves_existing_advanced_operation_guard(self):
        with mock.patch.object(sys, "frozen", True, create=True):
            first = self.api.download_advanced_feature("phone_control")
            second = self.api.download_advanced_feature("phone_control")
        self.assertTrue(first["ok"])
        self.assertFalse(second["ok"])
        self.assertTrue(self.api._advanced_busy)
        self.assertEqual(self.api._component_service.start.call_count, 1)

    def test_component_query_uses_installed_version_manifest_direct_link(self):
        # G1：按标签拼 Release 资产直链，不请求 api.github.com（未登录接口按出口 IP 限流）
        with mock.patch.object(self.app._update_check, "_fetch_bytes", side_effect=ValueError) as fetch:
            self.api._resolve_component_asset("1.2.0")
        self.assertTrue(fetch.call_args.args[0].endswith("/releases/download/v1.2.0/manifest.json"))

    def test_component_failure_writes_reason_to_run_log(self):
        # G2：界面红条只显示当前 tab 的那一条，运行记录里也要留下同一句原因
        self.api._advanced_busy = True
        self.api._ocr_component_service = mock.Mock()
        self.api._ocr_component_service.snapshot.return_value = {
            "state": "failed", "error_code": "rate_limited",
            "text": "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载。"}
        self.api._component_finished(self.app._advanced_features.RELOGIN_OCR)
        self.assertFalse(self.api._advanced_busy)
        self.api._emit.assert_called_once()
        kind, line = self.api._emit.call_args.args
        self.assertEqual(kind, "log")
        self.assertEqual(line, "下载没有完成：GitHub 暂时限制了查询次数，"
                               "过一会再试，或到发布页手动下载后导入。")

    def test_component_success_and_cancel_write_no_failure_line(self):
        for state in ("installed", "cancelled", "available", "missing"):
            with self.subTest(state=state):
                self.api._emit.reset_mock()
                self.api._ocr_component_service = mock.Mock()
                self.api._ocr_component_service.snapshot.return_value = {
                    "state": state, "error_code": "", "text": "组件包已安装。"}
                self.api._component_finished(self.app._advanced_features.RELOGIN_OCR)
                self.api._emit.assert_not_called()

    def test_component_finish_without_feature_stays_silent(self):
        self.api._component_finished()
        self.api._emit.assert_not_called()

    def test_cancel_unknown_start_prevents_late_original_from_creating_plan(self):
        self.api._start_requests = {}
        self.api._start_order = []
        canceled = self.api.cancel_start_request("delayed-request")
        self.assertTrue(canceled["ok"])
        self.api._terms_gate = mock.Mock(side_effect=AssertionError("late request passed cancel"))
        replay = self.api.start_plan([{"id": "test-only"}], request_id="delayed-request")
        self.assertTrue(replay["canceled"])

    def test_cancellation_survives_normal_start_history_eviction(self):
        self.api._start_requests = {}
        self.api._start_order = []
        self.api._canceled_start_ids = set()
        self.assertTrue(self.api.cancel_start_request("delayed-request")["ok"])
        with self.api._lock:
            for index in range(40):
                self.api._remember_start("other-%d" % index, "rejected", result={"ok":False})
        self.api._terms_gate = mock.Mock(return_value={"ok":False})
        replay = self.api.start_plan([{"id":"test-only"}], request_id="delayed-request")
        self.assertTrue(replay.get("canceled"))

    def test_component_maintenance_preserves_trust_and_channel_preferences(self):
        self.api._phone = mock.Mock()
        self.api._cloudflare = mock.Mock()
        self.api.stop_phone_access = mock.Mock()
        with mock.patch.object(self.app._component_packages, "install", return_value={"ok":True}):
            self.api._install_downloaded_component("unused", "phone_control")
        self.api.stop_phone_access.assert_not_called()
        self.api._phone.shutdown.assert_called_once_with(preserve_devices=True)



class HelperTimeoutTests(unittest.TestCase):
    def test_stalled_stdin_is_covered_by_helper_timeout(self):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        failures = []
        def invoke():
            try:
                cp._helper("unused.exe", feature="phone_control",
                           payload={"data": "a" * (512 * 1024)}, timeout=0.1)
            except cp.PackageError as exc:
                failures.append(str(exc))
        worker = threading.Thread(target=invoke, daemon=True)
        with mock.patch.object(cp.subprocess, "Popen", return_value=child):
            worker.start()
            worker.join(1.5)
            bounded = not worker.is_alive()
            if child.poll() is None:
                child.kill()
            worker.join(3)
        self.assertTrue(bounded, "stdin 写满也必须触发整体超时")
        self.assertEqual(failures, ["helper_failed"])
