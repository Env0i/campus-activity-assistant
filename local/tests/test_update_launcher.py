"""版本启动器（update_launcher）的返修回归：等待父进程、目标目录残留、坏 staging、current 回退。

全部使用 tempfile.gettempdir() 下的临时目录和替身：不真的启动进程、不杀进程，
Windows 句柄接口（OpenProcess / WaitForSingleObject / GetLastError）用替身注入，
不调用真实的 kernel32。

@author Author
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
import update_launcher  # noqa: E402

EXE = "campus-activity-watch.exe"
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87
WAIT_TIMEOUT = 0x102


class FakeKernel32:
    """替身 kernel32：只记调用，不碰任何真实句柄。"""

    def __init__(self, *, handle=0, last_error=0, wait_result=0):
        self.handle = handle
        self.last_error = last_error
        self.wait_result = wait_result
        self.opened = []
        self.waited = []
        self.closed = []

    def OpenProcess(self, access, inherit, pid):  # noqa: N802 - 与 Win32 同名
        self.opened.append(pid)
        return self.handle

    def GetLastError(self):  # noqa: N802
        return self.last_error

    def WaitForSingleObject(self, handle, milliseconds):  # noqa: N802
        self.waited.append((handle, milliseconds))
        return self.wait_result

    def CloseHandle(self, handle):  # noqa: N802
        self.closed.append(handle)
        return 1


class WaitParentTests(unittest.TestCase):
    """C2：父进程已经退出时必须放行，等待时限要给用户足够时间关窗。"""

    def test_missing_pid_means_parent_already_exited(self):
        # 主程序已退出：PID 不存在，OpenProcess 返回 0 且 GetLastError 为 87
        fake = FakeKernel32(handle=0, last_error=ERROR_INVALID_PARAMETER)
        result = update_launcher._wait_parent_windows(4321, 5, fake)
        self.assertTrue(result["ok"], result)
        self.assertEqual(fake.waited, [])

    def test_other_open_failure_is_still_reported(self):
        # 拒绝访问等其他原因拿不到句柄时无法确认父进程已退出，不能切换
        fake = FakeKernel32(handle=0, last_error=ERROR_ACCESS_DENIED)
        result = update_launcher._wait_parent_windows(4321, 5, fake)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "parent_wait_failed")
        self.assertTrue(result["text"])

    def test_live_parent_is_waited_and_handle_closed(self):
        fake = FakeKernel32(handle=77, wait_result=0)
        result = update_launcher._wait_parent_windows(4321, 5, fake)
        self.assertTrue(result["ok"], result)
        self.assertEqual(fake.waited, [(77, 5000)])
        self.assertEqual(fake.closed, [77])

    def test_wait_timeout_closes_handle_and_reports_timeout(self):
        fake = FakeKernel32(handle=77, wait_result=WAIT_TIMEOUT)
        result = update_launcher._wait_parent_windows(4321, 1, fake)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "parent_timeout")
        self.assertEqual(fake.closed, [77])

    def test_cli_default_wait_timeout_is_120_seconds(self):
        with mock.patch.object(update_launcher, "apply_staged",
                               return_value={"ok": True}) as applied, \
                mock.patch.object(update_launcher, "_default_launcher"):
            code = update_launcher.main([
                "--apply", "--version-root", "versions", "--staging", "versions/.staging-x",
                "--target-version", "1.2.2", "--parent-pid", "123"])
        self.assertEqual(code, 0)
        self.assertEqual(applied.call_args.kwargs["wait_timeout_s"], 120)


class VersionRootCase(unittest.TestCase):
    """隔离的安装根：versions/1.0.0 为当前版本，data 是不许被触碰的用户数据。"""

    def setUp(self):
        self.root = Path(tempfile.gettempdir()) / ("campus-launcher-test-" + uuid.uuid4().hex[:12])
        self.versions = self.root / "versions"
        self.versions.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.data = self.root / "data"
        self.data.mkdir()
        (self.data / "session.json").write_bytes(b"session")
        self.current = self.root / "current.json"
        self.make_version("1.0.0", b"old-exe")
        self.write_current({"version": "1.0.0"})

    def make_version(self, version, exe_bytes=b"exe", with_exe=True):
        path = self.versions / version
        path.mkdir(parents=True, exist_ok=True)
        if with_exe:
            (path / EXE).write_bytes(exe_bytes)
        return path

    def write_current(self, payload):
        self.current.write_text(json.dumps(payload), encoding="utf-8")

    def current_payload(self):
        return json.loads(self.current.read_text(encoding="utf-8"))

    def make_staging(self, with_exe=True):
        staging = self.versions / ".staging-req"
        staging.mkdir()
        if with_exe:
            (staging / EXE).write_bytes(b"new-exe")
        return staging

    def apply(self, staging, **overrides):
        options = dict(current_file=self.current, parent_pid=None,
                       launcher=lambda path: None)
        options.update(overrides)
        return update_launcher.apply_staged(staging, self.versions, "1.2.2", **options)

    def leftovers(self):
        return sorted(item.name for item in self.versions.iterdir()
                      if item.name.startswith(".old-"))


class ApplyStagedTests(VersionRootCase):
    def test_existing_target_dir_is_replaced_and_old_copy_removed(self):
        # D1：崩溃残留或重装旧版后再升级，目标目录已存在，不能每次都静默失败
        stale = self.make_version("1.2.2", b"stale-exe")
        (stale / "stale.txt").write_bytes(b"stale")
        launched = []
        result = self.apply(self.make_staging(), launcher=launched.append)
        self.assertTrue(result["ok"], result)
        self.assertEqual((self.versions / "1.2.2" / EXE).read_bytes(), b"new-exe")
        self.assertFalse((self.versions / "1.2.2" / "stale.txt").exists())
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.current_payload()["version"], "1.2.2")
        self.assertEqual(launched, [str(self.versions / "1.2.2" / EXE)])

    def test_existing_target_dir_is_restored_when_switch_fails(self):
        stale = self.make_version("1.2.2", b"stale-exe")
        (stale / "stale.txt").write_bytes(b"stale")
        staging = self.make_staging()
        with mock.patch.object(update_launcher, "_atomic_current", side_effect=OSError("disk")):
            result = self.apply(staging, launcher=lambda path: self.fail("不应启动"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "switch_failed")
        self.assertEqual((self.versions / "1.2.2" / EXE).read_bytes(), b"stale-exe")
        self.assertEqual((self.versions / "1.2.2" / "stale.txt").read_bytes(), b"stale")
        self.assertEqual((staging / EXE).read_bytes(), b"new-exe")
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.current_payload(), {"version": "1.0.0"})

    def test_staging_without_exe_is_rejected_before_switch(self):
        # D2：缺固定程序的 staging 不能先变成 current 再校验
        staging = self.make_staging(with_exe=False)
        result = self.apply(staging, launcher=lambda path: self.fail("不应启动"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "switch_failed")
        self.assertTrue(result["text"])
        self.assertTrue(staging.is_dir())
        self.assertFalse((self.versions / "1.2.2").exists())
        self.assertEqual(self.current_payload(), {"version": "1.0.0"})
        self.assertEqual((self.versions / "1.0.0" / EXE).read_bytes(), b"old-exe")

    def test_current_json_records_previous_version(self):
        result = self.apply(self.make_staging())
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.current_payload(),
                         {"version": "1.2.2", "previous_version": "1.0.0"})
        self.assertEqual(update_launcher.read_current(self.current)["previous_version"], "1.0.0")

    def test_user_data_is_never_touched(self):
        stale = self.make_version("1.2.2", b"stale-exe")
        (stale / "stale.txt").write_bytes(b"stale")
        self.assertTrue(self.apply(self.make_staging())["ok"])
        self.assertEqual((self.data / "session.json").read_bytes(), b"session")

    def test_atomic_current_syncs_file_to_disk(self):
        # D2：断电后 current.json 不能是空文件，写完必须 fsync
        with mock.patch.object(update_launcher.os, "fsync") as fsync:
            update_launcher._atomic_current(self.current, {"version": "1.2.2"})
        fsync.assert_called()
        self.assertEqual(self.current_payload(), {"version": "1.2.2"})

    def test_switch_failure_text_carries_no_local_path(self):
        """U2：切换失败的文案是固定中文句子，异常类型放 detail，本机路径不外泄。"""
        secret = str(self.root / "secret-dir" / "current.json")
        with mock.patch.object(update_launcher, "_atomic_current", side_effect=OSError(secret)):
            result = self.apply(self.make_staging(), launcher=lambda path: self.fail("不应启动"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "switch_failed")
        self.assertNotIn("secret-dir", result["text"])
        self.assertNotIn(str(self.root), result["text"])
        self.assertEqual(result.get("detail"), "OSError")

    def test_main_prints_exception_type_but_not_the_path_on_stderr(self):
        import contextlib
        import io
        secret = str(self.root / "secret-dir" / "x")
        buffer = io.StringIO()
        with mock.patch.object(update_launcher, "launch_current", side_effect=OSError(secret)), \
                contextlib.redirect_stderr(buffer):
            code = update_launcher.main(["--start", "--version-root", str(self.versions)])
        self.assertEqual(code, 1)
        self.assertIn("OSError", buffer.getvalue())
        self.assertNotIn("secret-dir", buffer.getvalue())


class LaunchCurrentFallbackTests(VersionRootCase):
    """D2：current.json 指向的版本不可用时，依次回退 previous_version、最大有效版本。"""

    def setUp(self):
        super().setUp()
        self.make_version("1.1.0", b"mid-exe")
        self.make_version("1.2.0", with_exe=False)   # 半成品：没有固定程序

    def launch(self):
        launched = []
        result = update_launcher.launch_current(
            self.versions, current_file=self.current, launcher=launched.append)
        return result, launched

    def test_healthy_current_is_used_without_fallback(self):
        self.write_current({"version": "1.0.0", "previous_version": "1.1.0"})
        result, launched = self.launch()
        self.assertEqual(result["version"], "1.0.0")
        self.assertFalse(result.get("fallback"))
        self.assertEqual(launched, [str(self.versions / "1.0.0" / EXE)])

    def test_broken_current_falls_back_to_previous_version(self):
        self.write_current({"version": "1.2.0", "previous_version": "1.0.0"})
        result, launched = self.launch()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(result["fallback"], "previous_version")
        self.assertEqual(launched, [str(self.versions / "1.0.0" / EXE)])

    def test_without_previous_falls_back_to_greatest_valid_version(self):
        self.write_current({"version": "1.2.0"})
        result, launched = self.launch()
        self.assertEqual(result["version"], "1.1.0")
        self.assertEqual(result["fallback"], "latest_valid")
        self.assertEqual(launched, [str(self.versions / "1.1.0" / EXE)])

    def test_corrupt_current_json_still_starts_greatest_valid_version(self):
        self.current.write_text("{not json", encoding="utf-8")
        result, launched = self.launch()
        self.assertEqual(result["version"], "1.1.0")
        self.assertEqual(launched, [str(self.versions / "1.1.0" / EXE)])

    def test_previous_missing_too_falls_back_to_greatest_valid_version(self):
        self.write_current({"version": "1.2.0", "previous_version": "0.9.0"})
        result, _ = self.launch()
        self.assertEqual(result["version"], "1.1.0")

    def test_no_valid_version_raises_readable_error(self):
        shutil.rmtree(self.versions / "1.0.0")
        shutil.rmtree(self.versions / "1.1.0")
        self.write_current({"version": "1.2.0"})
        with self.assertRaises(ValueError):
            update_launcher.launch_current(self.versions, current_file=self.current,
                                           launcher=lambda path: self.fail("不应启动"))


if __name__ == "__main__":
    unittest.main()
