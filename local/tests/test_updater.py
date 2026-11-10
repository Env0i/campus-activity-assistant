"""安装器流式下载与启动桥接的安全边界；全部替身，不访问网络、不启动正式安装器。

@author Author
"""
from hashlib import sha256
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import uuid
import json
import zipfile
from unittest.mock import patch

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
import updater  # noqa: E402
import update_delta  # noqa: E402
import update_launcher  # noqa: E402

NAME = "campus-activity-watch-installer-v1.1.1-win-x64.exe"
URL = "https://github.com/Env0i/campus-activity-assistant/releases/download/v1.1.1/" + NAME
BODY = b"installer-bytes-0123456789"
DIGEST = sha256(BODY).hexdigest()
TEMP_BASE = Path(tempfile.gettempdir())
OLD_FILES = ("data/session.json", "program/campus-activity-watch.exe")


class FakeStream:
    """替身 HTTP 响应：按脚本吐块，可模拟断流与超量。"""

    def __init__(self, chunks, break_after=None):
        self.chunks = list(chunks)
        self.break_after = break_after
        self.served = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, amt):
        if self.break_after is not None and self.served >= self.break_after:
            raise ConnectionResetError("stream reset")
        if not self.chunks:
            return b""
        self.served += 1
        return self.chunks.pop(0)


class UpdaterDirTests(unittest.TestCase):
    """隔离目录基类：只在 <tmp> 下开目录，不写程序目录和数据目录。"""

    def setUp(self):
        self.root = TEMP_BASE / ("campus-updater-test-" + uuid.uuid4().hex[:12])
        self.root.mkdir(parents=True, exist_ok=True)
        program = self.root / "program"
        data = self.root / "data"
        program.mkdir()
        data.mkdir()
        (program / "campus-activity-watch.exe").write_bytes(b"old-program")
        (data / "session.json").write_bytes(b"old-session")
        self.before = {rel: (self.root / rel).read_bytes() for rel in OLD_FILES}

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def assertOldFilesIntact(self):
        for rel, raw in self.before.items():
            self.assertEqual((self.root / rel).read_bytes(), raw,
                             "旧程序/数据被改动：" + rel)

    def leftovers(self):
        return sorted(p.relative_to(self.root).as_posix()
                      for p in self.root.rglob("*") if p.is_file())

    def assertCleanedUp(self):
        self.assertEqual(self.leftovers(), sorted(OLD_FILES))
        self.assertOldFilesIntact()


class DownloadTests(UpdaterDirTests):
    def download(self, chunks, expect_bytes=len(BODY), expect_sha256=DIGEST,
                 max_bytes=updater.DEFAULT_MAX_BYTES, break_after=None,
                 cancel=None, progress=None):
        stream = FakeStream(chunks, break_after=break_after)
        with patch.object(updater, "urlopen", return_value=stream) as fetch:
            result = updater.download_installer(
                URL, name=NAME, expect_bytes=expect_bytes, expect_sha256=expect_sha256,
                root=self.root, max_bytes=max_bytes, cancel=cancel, progress=progress)
        return result, fetch

    def test_success_keeps_atomically_named_file(self):
        result, fetch = self.download([BODY[i:i + 8] for i in range(0, len(BODY), 8)])
        self.assertTrue(result["ok"])
        self.assertEqual(result["bytes"], len(BODY))
        self.assertEqual(result["sha256"], DIGEST)
        path = Path(result["path"])
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, NAME)
        self.assertEqual(path.read_bytes(), BODY)
        self.assertNotIn(NAME + ".part", self.leftovers())
        self.assertOldFilesIntact()
        self.assertEqual(fetch.call_count, 1)

    def test_https_only(self):
        for bad in ("http://github.com/x/" + NAME, "ftp://github.com/x/" + NAME, "", None, 5):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                updater.download_installer(bad, name=NAME, expect_bytes=len(BODY),
                                           expect_sha256=DIGEST, root=self.root)
        self.assertOldFilesIntact()

    def test_bad_arguments_raise_not_swallow(self):
        base = {"name": NAME, "expect_bytes": len(BODY), "expect_sha256": DIGEST}
        for bad in ({"name": "a/b.exe"}, {"name": ""},
                    {"expect_sha256": "zz"}, {"expect_bytes": 0},
                    {"expect_bytes": "9"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                updater.download_installer(URL, root=self.root, **dict(base, **bad))

    def test_stream_break_cleans_up(self):
        result, _ = self.download([BODY[:8], BODY[8:16], BODY[16:]], break_after=2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "network_error")
        self.assertCleanedUp()

    def test_declared_oversize_rejected_without_fetch(self):
        result, fetch = self.download([], expect_bytes=updater.DEFAULT_MAX_BYTES + 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "size_limit")
        fetch.assert_not_called()

    def test_stream_oversize_rejected(self):
        # 声明大小在上限内，但服务端发来更多字节：必须中途放弃并清理
        result, _ = self.download([BODY[:8], BODY[8:16], BODY[16:]],
                                  expect_bytes=8, max_bytes=12)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "size_limit")
        self.assertCleanedUp()

    def test_short_stream_rejected(self):
        result, _ = self.download([BODY[:4]])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "size_mismatch")
        self.assertCleanedUp()

    def test_hash_mismatch_cleans_up(self):
        result, _ = self.download([b"evil" + BODY[4:]])
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "hash_mismatch")
        self.assertCleanedUp()

    def test_user_cancel_cleans_up(self):
        calls = []
        result, _ = self.download([BODY[:8], BODY[8:16], BODY[16:]],
                                  cancel=lambda: calls.append(1) or len(calls) > 1)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "cancelled")
        self.assertCleanedUp()

    def test_progress_reports_each_chunk(self):
        steps = []
        result, _ = self.download([BODY[:8], BODY[8:16], BODY[16:]],
                                  progress=lambda done, total: steps.append((done, total)))
        self.assertTrue(result["ok"])
        self.assertEqual(steps, [(8, len(BODY)), (16, len(BODY)), (len(BODY), len(BODY))])

    def test_cleanup_download_removes_payload_and_temp_parent(self):
        work = self.root / (updater.TEMP_PREFIX + "payload")
        work.mkdir()
        payload = work / "payload.zip"
        payload.write_bytes(b"payload")
        self.assertTrue(updater.cleanup_download(payload))
        self.assertFalse(work.exists())


class LaunchTests(UpdaterDirTests):
    def test_launch_success_returns_path(self):
        target = self.root / NAME
        target.write_bytes(BODY)
        launched = []
        got = updater.launch_installer(str(target), root=self.root,
                                       launcher=lambda p: launched.append(p))
        self.assertTrue(got["ok"])
        self.assertEqual(launched, [str(target)])

    def test_launcher_failure_is_reported(self):
        def boom(path):
            raise RuntimeError("uac denied")
        target = self.root / NAME
        target.write_bytes(BODY)
        got = updater.launch_installer(str(target), root=self.root, launcher=boom)
        self.assertFalse(got["ok"])
        self.assertEqual(got["error_code"], "launch_failed")
        self.assertIn("RuntimeError", got["text"])
        self.assertOldFilesIntact()

    def test_launch_refuses_paths_outside_temp_root(self):
        outside = self.root.parent / ("outside-" + uuid.uuid4().hex[:8] + ".exe")
        outside.write_bytes(BODY)
        try:
            got = updater.launch_installer(str(outside), root=self.root,
                                           launcher=lambda p: self.fail("不该启动"))
            self.assertFalse(got["ok"])
            self.assertEqual(got["error_code"], "launch_failed")
        finally:
            outside.unlink(missing_ok=True)

    def test_launch_refuses_missing_file(self):
        got = updater.launch_installer(str(self.root / "ghost.exe"), root=self.root,
                                       launcher=lambda p: self.fail("不该启动"))
        self.assertFalse(got["ok"])
        self.assertEqual(got["error_code"], "launch_failed")


class VersionUpdateTests(unittest.TestCase):
    """版本目录更新只操作程序目录，失败时保留 current.json 与旧版本。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="campus-version-test-"))
        self.versions = self.root / "versions"
        self.versions.mkdir()
        self.data = self.root / "data"
        self.data.mkdir()
        self.old = self.versions / "1.0.0"
        self.old.mkdir()
        (self.old / "app.exe").write_bytes(b"old")
        (self.data / "session.json").write_bytes(b"session")
        (self.root / "current.json").write_text(
            json.dumps({"version": "1.0.0"}), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _target(self):
        target = self.root / "target"
        target.mkdir()
        (target / "app.exe").write_bytes(b"new")
        (target / "new.dll").write_bytes(b"dll")
        return target

    def test_delta_is_preferred_and_switch_keeps_previous_version(self):
        target = self._target()
        delta = update_delta.build_delta(self.old, target, "1.0.0", "1.2.2")
        archive = self.root / "delta.zip"
        update_delta.write_delta_zip(delta, archive)
        staging = self.root / "staging"
        result = updater.stage_update(
            self.old, archive, staging, mode="delta", base_version="1.0.0")
        self.assertTrue(result["ok"])
        switched = updater.switch_version(
            self.versions, staging, "1.2.2", current_file=self.root / "current.json")
        self.assertTrue(switched["ok"])
        self.assertTrue((self.versions / "1.0.0" / "app.exe").is_file())
        self.assertEqual((self.versions / "1.2.2" / "app.exe").read_bytes(), b"new")
        self.assertEqual(json.loads((self.root / "current.json").read_text())["version"], "1.2.2")
        self.assertEqual((self.data / "session.json").read_bytes(), b"session")

    def test_corrupt_delta_falls_back_to_full_payload(self):
        target = self._target()
        manifest = update_delta.manifest_from_directory(target, version="1.2.2")
        full = self.root / "full.zip"
        with zipfile.ZipFile(full, "w") as archive:
            for path in target.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(target).as_posix())
        staging = self.root / "staging"
        bad = updater.stage_update(
            self.old, self.root / "missing.delta.zip", staging,
            mode="delta", base_version="1.0.0")
        self.assertFalse(bad["ok"])
        good = updater.stage_update(
            self.old, full, staging, mode="full", target_manifest=manifest,
            target_version="1.2.2")
        self.assertTrue(good["ok"])
        self.assertEqual((staging / "app.exe").read_bytes(), b"new")

    def test_switch_failure_does_not_change_current(self):
        staging = self.root / "staging"
        staging.mkdir()
        (staging / "app.exe").write_bytes(b"new")
        with patch.object(updater, "_atomic_write_json", side_effect=OSError("disk")):
            result = updater.switch_version(
                self.versions, staging, "1.2.2", current_file=self.root / "current.json")
        self.assertFalse(result["ok"])
        self.assertEqual(json.loads((self.root / "current.json").read_text())["version"], "1.0.0")
        self.assertTrue((self.old / "app.exe").is_file())

    def test_cleanup_staging_accepts_only_versions_staging(self):
        staging = self.versions / ".staging-request"
        staging.mkdir()
        (staging / "partial").write_bytes(b"partial")
        self.assertTrue(updater.cleanup_staging(staging))
        self.assertFalse(staging.exists())
        foreign = self.root / ".staging-foreign"
        foreign.mkdir()
        self.assertFalse(updater.cleanup_staging(foreign))
        self.assertTrue(foreign.exists())
        custom_root = self.root / "program-releases"
        custom_root.mkdir()
        custom = custom_root / ".staging-custom"
        custom.mkdir()
        self.assertTrue(updater.cleanup_staging(custom, version_root=custom_root))
        self.assertFalse(custom.exists())

    def test_launcher_starts_current_fixed_exe(self):
        exe = self.old / "campus-activity-watch.exe"
        exe.write_bytes(b"old-exe")
        launched = []
        result = update_launcher.launch_current(
            self.versions, current_file=self.root / "current.json",
            launcher=lambda path: launched.append(path))
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "1.0.0")
        self.assertEqual(launched, [str(exe)])

    def test_launcher_rejects_version_path_escape_and_wrong_exe(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "campus-activity-watch.exe").write_bytes(b"outside")
        with self.assertRaises(ValueError):
            update_launcher.validate_version_dir(self.versions, "..")
        (self.old / "campus-activity-watch.exe").write_bytes(b"old-exe")
        (self.old / "campus-activity-watch.exe").unlink()
        with self.assertRaises(ValueError):
            update_launcher.validate_version_dir(self.versions, "1.0.0")

    def test_cli_uses_explicit_start_flag(self):
        with patch.object(update_launcher, "launch_current",
                          return_value={"ok": True}), \
                patch.object(update_launcher, "_default_launcher"):
            self.assertEqual(update_launcher.main([
                "--start", "--version-root", str(self.versions),
                "--current-file", str(self.root / "current.json")]), 0)

    def test_cli_uses_explicit_apply_flag(self):
        staging = self.root / "staging"
        with patch.object(update_launcher, "apply_staged",
                          return_value={"ok": True}), \
                patch.object(update_launcher, "_default_launcher"):
            self.assertEqual(update_launcher.main([
                "--apply", "--version-root", str(self.versions),
                "--current-file", str(self.root / "current.json"),
                "--staging", str(staging), "--target-version", "1.2.2",
                "--parent-pid", "123"]), 0)

    def test_cli_requires_start_or_apply_flag(self):
        with self.assertRaises(SystemExit):
            update_launcher.main(["--version-root", str(self.versions)])

    def test_apply_waits_parent_switches_and_starts_target(self):
        staging = self.root / "staging"
        staging.mkdir()
        (staging / "campus-activity-watch.exe").write_bytes(b"new-exe")
        waited = []
        launched = []
        result = update_launcher.apply_and_launch(
            self.versions, staging, "1.2.2",
            current_file=self.root / "current.json", parent_pid=123,
            wait_parent=lambda pid, timeout_s: waited.append((pid, timeout_s)) or {"ok": True},
            launcher=lambda path: launched.append(path), wait_timeout_s=4)
        self.assertTrue(result["ok"])
        self.assertEqual(waited, [(123, 4)])
        self.assertEqual(launched, [str(self.versions / "1.2.2" / "campus-activity-watch.exe")])
        self.assertTrue((self.versions / "1.0.0" / "app.exe").is_file())
        self.assertEqual(json.loads((self.root / "current.json").read_text())["version"], "1.2.2")

    def test_apply_parent_timeout_keeps_staging_and_current(self):
        staging = self.root / "staging"
        staging.mkdir()
        (staging / "campus-activity-watch.exe").write_bytes(b"new-exe")
        result = update_launcher.apply_and_launch(
            self.versions, staging, "1.2.2",
            current_file=self.root / "current.json", parent_pid=123,
            wait_parent=lambda pid, timeout_s: {"ok": False, "error_code": "parent_timeout",
                                                "text": "timeout"},
            launcher=lambda path: self.fail("不应启动"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "parent_timeout")
        self.assertTrue(staging.is_dir())
        self.assertEqual(json.loads((self.root / "current.json").read_text())["version"], "1.0.0")

    def test_apply_current_write_failure_restores_staging_and_old_version(self):
        staging = self.root / "staging"
        staging.mkdir()
        (staging / "campus-activity-watch.exe").write_bytes(b"new-exe")
        with patch.object(update_launcher, "_atomic_current", side_effect=OSError("disk")):
            result = update_launcher.apply_and_launch(
                self.versions, staging, "1.2.2",
                current_file=self.root / "current.json", parent_pid=None,
                launcher=lambda path: self.fail("不应启动"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "switch_failed")
        self.assertTrue(staging.is_dir())
        self.assertTrue((self.versions / "1.0.0" / "app.exe").is_file())
        self.assertEqual(json.loads((self.root / "current.json").read_text())["version"], "1.0.0")


if __name__ == "__main__":
    unittest.main()
