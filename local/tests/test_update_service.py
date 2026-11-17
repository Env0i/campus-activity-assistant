# -*- coding: utf-8 -*-
"""UpdateService 直测：不经 Api，端口全用内存替身，先断言返回值与事件再断言内部字段。

覆盖单飞（检查在途时再检查、在途时下载）、关闭中拒绝、取消、snapshot 的四个键。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application import update_service  # noqa: E402


class FakeThread:
    """threading.Thread 替身：只记录构造参数，start() 立刻跑目标。"""

    made: list["FakeThread"] = []

    def __init__(self, target=None, args=(), daemon=None, **_):
        self.target, self.args = target, tuple(args or ())
        FakeThread.made.append(self)

    def start(self):
        self.target(*self.args)


class ServiceCase(unittest.TestCase):
    def setUp(self):
        FakeThread.made = []
        self.events: list[tuple[str, dict]] = []
        self.closing = False
        self.service = update_service.UpdateService(
            emit=lambda kind, payload: self.events.append((kind, payload)),
            is_closing=lambda: self.closing)
        self.paths = {"root": Path("versions"), "current_file": Path("current.json"),
                      "base_dir": Path("versions") / "1.0.0"}

    def paths_fn(self):
        return self.paths

    def start_check(self, request_id, job=None):
        return self.service.start_check(
            request_id, thread_factory=FakeThread, job=job or (lambda rid: None),
            cleanup_staging=lambda *a, **k: None,
            update_version_paths=self.paths_fn, current_version="1.0.0")


class StartCheckTests(ServiceCase):
    def test_single_flight_keeps_the_first_request_id(self):
        first = self.start_check("req-1")
        second = self.start_check("req-2")
        self.assertEqual(first, {"ok": True, "queued": True, "request_id": "req-1"})
        self.assertEqual(second, {"ok": True, "queued": True, "skipped": True,
                                  "request_id": "req-1"})
        self.assertEqual(len(FakeThread.made), 1, "在途时不能再起线程")
        self.assertEqual(self.events[0][0], "update")
        self.assertEqual(self.events[0][1]["state"], "checking")
        self.assertTrue(self.service._updating)

    def test_invalid_request_id_is_rejected_before_any_state(self):
        self.assertFalse(self.start_check("bad id")["ok"])
        self.assertFalse(self.service._updating)
        self.assertEqual(FakeThread.made, [])
        self.assertEqual(self.events, [])

    def test_closing_rejects_without_touching_state(self):
        self.closing = True
        result = self.start_check("req-1")
        self.assertEqual(result, {"ok": False, "queued": False, "text": "程序正在关闭。"})
        self.assertFalse(self.service._updating)

    def test_check_job_publishes_result_and_releases_slot(self):
        self.start_check("req-1")
        update_service.run_check(self.service, "req-1",
                                 fetch=lambda version: {"state": "current",
                                                        "latest_version": version},
                                 current_version="1.0.0",
                                 latest_url="https://example.invalid/latest")
        self.assertFalse(self.service._updating)
        self.assertEqual(self.service._update_result["request_id"], "req-1")
        states = [payload.get("state") for _, payload in self.events]
        self.assertEqual(states, ["checking", "current"])


class StartDownloadTests(ServiceCase):
    installer = {"name": "installer.exe", "url": "https://example.invalid/i.exe",
                 "bytes": 4, "sha256": "ab" * 32}

    def start_download(self, request_id, job=None):
        return self.service.start_download(request_id, thread_factory=FakeThread,
                                           job=job or (lambda rid, installer: None))

    def test_download_without_selected_installer_is_refused(self):
        self.service._update_installer = None
        self.assertEqual(self.start_download("dl-1"),
                         {"ok": False, "queued": False,
                          "text": "当前没有可下载的安装包，请前往下载页。"})

    def test_check_in_flight_skips_download(self):
        self.start_check("req-1")
        self.service._update_installer = dict(self.installer)
        self.assertTrue(self.start_download("dl-1")["skipped"])
        self.assertEqual(self.service._update_request_id, "req-1")

    def test_download_single_flight_and_cancel_flag(self):
        self.service._update_installer = dict(self.installer)
        first = self.start_download("dl-1")
        self.assertEqual(first, {"ok": True, "queued": True, "request_id": "dl-1"})
        self.assertTrue(self.start_download("dl-2")["skipped"])
        self.service.cancel()
        self.assertTrue(self.service._update_cancelled)


class SnapshotAndPublishTests(ServiceCase):
    def test_snapshot_has_the_four_keys(self):
        self.assertEqual(set(self.service.snapshot()),
                         {"checking", "request_id", "result", "installer_path"})
        self.assertFalse(self.service.snapshot()["checking"])

    def test_snapshot_reflects_in_flight_and_installer_path(self):
        self.start_check("req-1")
        snapshot = self.service.snapshot()
        self.assertTrue(snapshot["checking"])
        self.assertEqual(snapshot["request_id"], "req-1")
        self.service._update_installer_path = "fake-temp/installer.exe"
        self.assertEqual(self.service.snapshot()["installer_path"], "fake-temp/installer.exe")

    def test_publish_ready_to_restart_adds_version_paths(self):
        self.service.publish({"state": "ready_to_restart", "latest_version": "1.1.0"}, True,
                             update_version_paths=self.paths_fn)
        payload = self.events[-1][1]
        self.assertEqual(payload["state"], "ready_to_restart")
        self.assertEqual(payload["version_root"], str(self.paths["root"]))
        self.assertEqual(payload["current_file"], str(self.paths["current_file"]))
        self.assertEqual(payload["target_version"], "1.1.0")
        self.assertFalse(self.service._updating)

    def test_closing_drops_event_but_keeps_result(self):
        self.closing = True
        self.service.publish({"state": "failed"}, True, update_version_paths=self.paths_fn)
        self.assertEqual(self.events, [])
        self.assertEqual(self.service._update_result, {"state": "failed"})


class LaunchTests(ServiceCase):
    def ports(self, **overrides):
        base = {
            "version_switch_available": lambda: False,
            "update_version_paths": self.paths_fn,
            "launcher_command": lambda *a, **k: ["launcher"],
            "spawn": lambda *a, **k: None,
            "cwd": "fake-temp",
            "env_factory": dict,
            "creationflags": 0,
            "parent_pid": 4321,
            "defer_close": lambda callback, delay=0.25: None,
            "request_close": lambda: None,
            "launch_installer": lambda path: {"ok": True, "path": path},
        }
        base.update(overrides)
        return update_service.LaunchPorts(**base)

    def test_launch_without_artifact_is_refused(self):
        self.assertEqual(self.service.launch("l-1", self.ports()),
                         {"ok": False, "text": "还没有已校验的安装包，请先下载。"})

    def test_launch_installer_publishes_twice(self):
        self.service._update_installer_path = "fake-temp/installer.exe"
        result = self.service.launch("l-1", self.ports())
        self.assertTrue(result["ok"], result)
        self.assertEqual([payload["state"] for _, payload in self.events],
                         ["launching", "launching"])

    def test_launch_refused_when_version_switch_unavailable(self):
        self.service._update_result = {"state": "ready_to_restart", "latest_version": "1.1.0"}
        self.service._update_staging_path = "versions/.staging-l-1"
        result = self.service.launch("l-1", self.ports())
        self.assertEqual(result["state"], "ready_to_restart")
        self.assertFalse(result["ok"])
        self.assertEqual(self.events, [], "拒绝时不推事件，界面按快照处置")


if __name__ == "__main__":
    unittest.main()
