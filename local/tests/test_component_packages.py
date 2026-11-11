# -*- coding: utf-8 -*-
"""独立 ZIP 的真实文件校验与替换失败回滚；helper 仅用替身。

@author Author
"""
import contextlib
import hashlib
import json
import os
import shutil
import stat
import sys
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from infrastructure import component_packages as cp

# phone_control 组件必须内置 cloudflared，所以默认夹具自带一份；
# AUTO 表示「按 names 里的二进制自动算出声明」，None 才是「刻意不声明」。
TMP_ROOT = tempfile.gettempdir()
AUTO = object()
BINARY = b"MZcloudflared"


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TMP_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = "phone_control"
        self.target = self.root / "advanced" / self.key
        patch = mock.patch.object(cp, "_helper", return_value={"ok": True})
        self.helper = patch.start()
        self.addCleanup(patch.stop)

    def archive(self, *, extra=None, feature=None, platform="windows-x64", data=b"MZtest",
                names=None, cloudflare=AUTO, target="win-x64", app_version=None):
        key = feature or self.key
        if names is None:
            names = {"feature-helper.exe": data, "_internal/test.dll": b"library"}
            if key == "phone_control":
                names[cp.CLOUDFLARED_NAME] = BINARY
        if cloudflare is AUTO:
            cloudflare = ({"version": cp.CLOUDFLARED_VERSION,
                           "sha256": hashlib.sha256(names[cp.CLOUDFLARED_NAME]).hexdigest()}
                          if cp.CLOUDFLARED_NAME in names else None)
        files = names
        manifest = {"schema": 1, "feature": key,
                    "version": cp.version(), "platform": platform, "entry": "feature-helper.exe",
                    "files": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
        if cloudflare is not None:
            manifest["cloudflared"] = cloudflare
        if target is not None:
            manifest["target"] = target
        if app_version is not None:
            manifest["app_version"] = app_version
        archive = self.root / "package.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("manifest.json", json.dumps(manifest))
            for name, raw in files.items():
                z.writestr(name, raw)
            for name, raw in (extra or {}).items():
                z.writestr(name, raw)
        return archive

    def artifact_archive(self, artifact_id, files=None):
        spec = cp.ARTIFACTS[artifact_id]
        files = files or ({spec["entry"]: b"MZruntime"} if spec["entry"]
                          else {"models/common.onnx": b"model",
                                "models/charset.json": b"{}"})
        manifest = {
            "schema": cp.ARTIFACT_SCHEMA,
            "artifact_id": artifact_id,
            "feature": spec["feature"],
            "role": spec["role"],
            "protocol": cp.ARTIFACT_PROTOCOL,
            "asset_version": cp.version(),
            "compatibility_id": "campus-activity-1",
            "entry": spec["entry"],
            "requires": [],
            "files": {name: hashlib.sha256(raw).hexdigest()
                      for name, raw in files.items()},
        }
        if spec["role"] == "tool":
            manifest["tool"] = {"name": "cloudflared",
                                 "version": cp.CLOUDFLARED_VERSION,
                                 "sha256": manifest["files"][spec["entry"]]}
        archive = self.root / (artifact_id + ".zip")
        with zipfile.ZipFile(archive, "w") as package:
            package.writestr("manifest.json", json.dumps(manifest))
            for name, raw in files.items():
                package.writestr(name, raw)
        return archive

    def test_legacy_install_selects_new_component_over_split(self):
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        cp.install(self.archive(feature="relogin_ocr"), "relogin_ocr", root=self.root)
        self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "legacy")
        self.assertEqual(cp.selected_install_dir("relogin_ocr", root=self.root), self.root / "advanced" / "relogin_ocr")
        cp.invoke("relogin_ocr", {}, root=self.root)
        self.assertEqual(Path(self.helper.call_args.args[0]).parent, self.root / "advanced" / "relogin_ocr")

    def test_damaged_referenced_cache_is_never_moved(self):
        archive = self.artifact_archive("relogin_ocr_model")
        old = cp.cache_artifact(archive, "relogin_ocr_model", root=self.root)
        old_path = Path(old["path"])
        (old_path / "models" / "common.onnx").write_bytes(b"damaged")
        new = cp.cache_artifact(archive, "relogin_ocr_model", root=self.root)
        self.assertTrue(old_path.exists())
        self.assertNotEqual(old["path"], new["path"])
        self.assertEqual((old_path / "models" / "common.onnx").read_bytes(), b"damaged")
        metadata = {k: new[k] for k in ("artifact_id", "content_sha256", "compatibility_id")}
        self.assertEqual(cp.find_cached_artifact(metadata, root=self.root)["path"], new["path"])

    def test_legacy_install_overrides_automatic_fixed_group(self):
        for artifact in ("relogin_ocr_runtime", "relogin_ocr_model"):
            cp.install_artifact(self.artifact_archive(artifact), artifact, root=self.root)
        self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "split")
        cp.install(self.archive(feature="relogin_ocr"), "relogin_ocr", root=self.root)
        self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "legacy")
        self.assertTrue(cp.artifact_dir("relogin_ocr_runtime", root=self.root).exists())

    def test_legacy_install_process_exit_recovery_boundaries(self):
        script = """import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from infrastructure import component_packages as cp
cp.supported = lambda: True
cp._helper = lambda *args, **kwargs: {'ok': True}
original = cp._write_group_pointer
def stop(feature, data, root):
    if sys.argv[4] == 'before': os._exit(71)
    original(feature, data, root)
    os._exit(72)
cp._write_group_pointer = stop
cp.install(sys.argv[3], 'relogin_ocr', root=Path(sys.argv[2]))
"""
        local = str(Path(__file__).resolve().parents[1])
        for had_target, boundary, selection in ((True, "before", "split"), (True, "after", "split"),
                                                (False, "before", "split"), (True, "before", "legacy")):
            with self.subTest(had_target=had_target, boundary=boundary, selection=selection), tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
                root = Path(tmp)
                if had_target:
                    cp.install(self.archive(feature="relogin_ocr", data=b"old"), "relogin_ocr", root=root)
                runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=root)
                model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=root)
                if selection == "split":
                    cp.commit_artifact_group("relogin_ocr", [runtime, model], root=root)
                pointer = cp._group_pointer("relogin_ocr", root)
                old_pointer = pointer.read_bytes()
                archive = self.archive(feature="relogin_ocr", data=b"new")
                proc = subprocess.run([sys.executable, "-c", script, local, str(root), str(archive), boundary], timeout=15)
                self.assertEqual(proc.returncode, 71 if boundary == "before" else 72)
                self.assertTrue(cp.invoke("relogin_ocr", {}, root=root)["ok"])
                state = cp.feature_status("relogin_ocr", root=root)
                target = root / "advanced" / "relogin_ocr"
                if boundary == "before":
                    self.assertEqual(pointer.read_bytes(), old_pointer)
                    self.assertEqual(state["source"], selection)
                    if had_target:
                        self.assertEqual((target / "feature-helper.exe").read_bytes(), b"old")
                    else:
                        self.assertFalse(target.exists())
                else:
                    self.assertEqual(state["source"], "legacy")
                    self.assertEqual((target / "feature-helper.exe").read_bytes(), b"new")
                self.assertTrue(cp.invoke("relogin_ocr", {}, root=root)["ok"])

    def test_legacy_pointer_failure_restores_previous_selection_and_bytes(self):
        cp.install(self.archive(feature="relogin_ocr", data=b"old"), "relogin_ocr", root=self.root)
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        pointer = cp._group_pointer("relogin_ocr", self.root)
        old_pointer = pointer.read_bytes()
        with mock.patch.object(cp, "_write_group_pointer", side_effect=OSError("denied")):
            with self.assertRaises(OSError):
                cp.install(self.archive(feature="relogin_ocr", data=b"new"), "relogin_ocr", root=self.root)
        self.assertEqual(pointer.read_bytes(), old_pointer)
        self.assertEqual((self.root / "advanced" / "relogin_ocr" / "feature-helper.exe").read_bytes(), b"old")
        self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "split")

    def test_fixed_asset_commit_copies_to_immutable_cache(self):
        handles = []
        for artifact in ("relogin_ocr_runtime", "relogin_ocr_model"):
            cp.install_artifact(self.artifact_archive(artifact), artifact, root=self.root)
            state = cp.artifact_status(artifact, root=self.root)
            handles.append(cp._handle(state["path"], artifact))
        cp.commit_artifact_group("relogin_ocr", handles, root=self.root)
        cp.install_artifact(self.artifact_archive("relogin_ocr_runtime", {"feature-helper.exe": b"changed"}), "relogin_ocr_runtime", root=self.root)
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])
        self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["artifacts"]["relogin_ocr_runtime"]["content_sha256"], handles[0]["content_sha256"])

    def test_other_process_remove_waits_for_active_invoke(self):
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        script = """import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from infrastructure import component_packages as cp
root, entered, release, finished = map(Path, sys.argv[2:6])
cp.supported = lambda: True
if sys.argv[6] == 'invoke':
    def helper(*args, **kwargs):
        entered.touch()
        while not release.exists(): time.sleep(.02)
        return {'ok': True}
    cp._helper = helper
    cp.invoke('relogin_ocr', {}, root=root)
else:
    entered.touch()
    cp.remove('relogin_ocr', root=root)
finished.touch()
"""
        local = str(Path(__file__).resolve().parents[1])
        entered, release, done, started, removed = (self.root / x for x in ("entered", "release", "done", "started", "removed"))
        processes = []
        try:
            processes.append(subprocess.Popen([sys.executable, "-c", script, local, str(self.root), str(entered), str(release), str(done), "invoke"]))
            import time
            deadline = time.monotonic() + 10
            while not entered.exists() and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue(entered.exists())
            processes.append(subprocess.Popen([sys.executable, "-c", script, local, str(self.root), str(started), str(release), str(removed), "remove"]))
            deadline = time.monotonic() + 10
            while not started.exists() and time.monotonic() < deadline: time.sleep(.02)
            self.assertTrue(started.exists())
            time.sleep(.4)
            self.assertFalse(removed.exists())
            self.assertTrue(Path(runtime["path"]).exists())
            release.touch()
            for proc in processes: self.assertEqual(proc.wait(timeout=10), 0)
            self.assertTrue(done.exists())
            self.assertTrue(removed.exists())
        finally:
            release.touch()
            for proc in processes:
                if proc.poll() is None: proc.kill(); proc.wait()

    def test_two_processes_serialize_component_transactions(self):
        script = """import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from infrastructure import component_packages as cp
root = Path(sys.argv[2])
Path(sys.argv[5]).write_text('ready')
with cp._LOCK, cp._file_transaction(root):
    Path(sys.argv[3]).write_text('entered')
    while not Path(sys.argv[4]).exists(): time.sleep(.02)
"""
        local = str(Path(__file__).resolve().parents[1])
        first, second, release1, release2, first_ready, second_ready = (
            self.root / x for x in ("one", "two", "release1", "release2", "one.ready", "two.ready"))
        processes = []
        try:
            processes.append(subprocess.Popen([sys.executable, "-c", script, local, str(self.root), str(first), str(release1), str(first_ready)]))
            import time
            deadline = time.monotonic() + 10
            while not first.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(first.exists())
            processes.append(subprocess.Popen([sys.executable, "-c", script, local, str(self.root), str(second), str(release2), str(second_ready)]))
            # 等第二个进程写完就绪文件再计时：这时它已导入完模块，只差取锁
            deadline = time.monotonic() + 10
            while not second_ready.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(second_ready.exists())
            time.sleep(.4)
            self.assertFalse(second.exists())
            release1.touch()
            deadline = time.monotonic() + 10
            while not second.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(second.exists())
            release2.touch()
            for proc in processes:
                self.assertEqual(proc.wait(timeout=10), 0)
        finally:
            release1.touch()
            release2.touch()
            for proc in processes:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()

    def test_invoke_revalidates_even_if_status_fingerprint_is_unchanged(self):
        cp.install(self.archive(feature="relogin_ocr"), "relogin_ocr", root=self.root)
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        with mock.patch.object(cp, "_artifact_fingerprint", return_value=("unchanged",)):
            self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "split")
            (Path(runtime["path"]) / "feature-helper.exe").write_bytes(b"X" * len(b"MZruntime"))
            self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "split")
            self.helper.reset_mock()
            self.assertTrue(cp.invoke("relogin_ocr", {}, root=self.root)["ok"])
            self.assertEqual(Path(self.helper.call_args.args[0]), self.root / "advanced" / "relogin_ocr" / "feature-helper.exe")
            self.assertEqual(self.helper.call_count, 1)
            self.assertEqual(cp.feature_status("relogin_ocr", root=self.root)["source"], "legacy")

    def test_cloudflared_revalidates_even_if_status_fingerprint_is_unchanged(self):
        cp.install(self.archive(), "phone_control", root=self.root)
        runtime = cp.cache_artifact(self.artifact_archive("phone_control_runtime"), "phone_control_runtime", root=self.root)
        tool = cp.cache_artifact(self.artifact_archive("phone_control_cloudflared"), "phone_control_cloudflared", root=self.root)
        with mock.patch.object(cp, "probe_cloudflared_version", return_value=cp.CLOUDFLARED_VERSION):
            cp.commit_artifact_group("phone_control", [runtime, tool], root=self.root)
            with mock.patch.object(cp, "_artifact_fingerprint", return_value=("unchanged",)):
                self.assertEqual(cp.feature_status("phone_control", root=self.root)["source"], "split")
                (Path(tool["path"]) / cp.CLOUDFLARED_NAME).write_bytes(b"X" * len(b"MZruntime"))
                self.assertEqual(cp.feature_status("phone_control", root=self.root)["source"], "split")
                trusted = cp.cloudflared(root=self.root)
                self.assertEqual(Path(trusted), self.root / "advanced" / "phone_control" / cp.CLOUDFLARED_NAME)
                self.assertEqual(cp.feature_status("phone_control", root=self.root)["source"], "legacy")

    def test_group_status_reuses_validation_and_invalidates_changed_files(self):
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        with mock.patch.object(cp, "sha256", wraps=cp.sha256) as hashing:
            self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])
            self.assertEqual(hashing.call_count, 3)
            hashing.reset_mock()
            self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])
            self.assertEqual(hashing.call_count, 0)
            metadata = {k: model[k] for k in ("artifact_id", "content_sha256", "compatibility_id")}
            self.assertIsNotNone(cp.find_cached_artifact(metadata, root=self.root))
            self.assertGreater(hashing.call_count, 0)
            hashing.reset_mock()
            cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
            self.assertGreater(hashing.call_count, 0)
            (Path(model["path"]) / "models" / "common.onnx").write_bytes(b"broken")
            self.assertFalse(cp.feature_status("relogin_ocr", root=self.root)["available"])

    def test_cached_group_commit_preserves_old_group_on_probe_failure(self):
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        pointer = self.root / "advanced" / "assets" / ".groups" / "relogin_ocr.json"
        old = pointer.read_bytes()
        replacement = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime", {"feature-helper.exe": b"new"}), "relogin_ocr_runtime", root=self.root)
        self.helper.side_effect = cp.PackageError("helper_failed")
        with self.assertRaises(cp.PackageError):
            cp.commit_artifact_group("relogin_ocr", [replacement, model], root=self.root)
        self.assertEqual(pointer.read_bytes(), old)
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])

    def test_cache_reuses_verified_content_and_does_not_remove_other_stage(self):
        archive = self.artifact_archive("relogin_ocr_model")
        handle = cp.cache_artifact(archive, "relogin_ocr_model", root=self.root)
        other = self.root / "advanced" / "assets" / ".stage-relogin_ocr_model-other"
        other.mkdir()
        metadata = {k: handle[k] for k in ("artifact_id", "content_sha256", "compatibility_id")}
        self.assertEqual(cp.find_cached_artifact(metadata, root=self.root)["path"], handle["path"])
        self.assertTrue(other.exists())
        (Path(handle["path"]) / "models" / "common.onnx").write_bytes(b"bad")
        self.assertIsNone(cp.find_cached_artifact(metadata, root=self.root))

    def test_group_pointer_failure_and_incomplete_group_preserve_selection(self):
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        pointer = self.root / "advanced" / "assets" / ".groups" / "relogin_ocr.json"
        before = pointer.read_bytes()
        with self.assertRaises(cp.PackageError):
            cp.commit_artifact_group("relogin_ocr", [runtime], root=self.root)
        with mock.patch.object(cp.os, "replace", side_effect=OSError("denied")):
            with self.assertRaises(OSError):
                cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        self.assertEqual(pointer.read_bytes(), before)
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])

    def test_selected_group_invoke_uses_model_and_falls_back_to_legacy(self):
        cp.install(self.archive(feature="relogin_ocr"), "relogin_ocr", root=self.root)
        runtime = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        self.assertEqual(cp.selected_install_dir("relogin_ocr", root=self.root), Path(runtime["path"]))
        self.helper.side_effect = [cp.PackageError("failed"), {"ok": True}]
        self.assertTrue(cp.invoke("relogin_ocr", {}, root=self.root)["ok"])
        self.assertEqual(Path(self.helper.call_args.args[0]), self.root / "advanced" / "relogin_ocr" / "feature-helper.exe")

    def test_readers_observe_complete_group_during_switch(self):
        old = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime"), "relogin_ocr_runtime", root=self.root)
        model = cp.cache_artifact(self.artifact_archive("relogin_ocr_model"), "relogin_ocr_model", root=self.root)
        new = cp.cache_artifact(self.artifact_archive("relogin_ocr_runtime", {"feature-helper.exe": b"new"}), "relogin_ocr_runtime", root=self.root)
        cp.commit_artifact_group("relogin_ocr", [old, model], root=self.root)
        failures = []
        def reader():
            for _ in range(30):
                state = cp.feature_status("relogin_ocr", root=self.root)
                if not state["available"] or state["artifacts"]["relogin_ocr_runtime"]["content_sha256"] not in (old["content_sha256"], new["content_sha256"]):
                    failures.append(state)
        thread = threading.Thread(target=reader)
        thread.start()
        for _ in range(5):
            cp.commit_artifact_group("relogin_ocr", [new, model], root=self.root)
            cp.commit_artifact_group("relogin_ocr", [old, model], root=self.root)
        thread.join()
        self.assertEqual(failures, [])

    def _aged(self, handle, aged=True):
        """把缓存目录的修改时间拨到宽限期之外，模拟「早就缓存好、早已退役」的旧组。"""
        if aged:
            old = time.time() - getattr(cp, "CACHE_RECLAIM_GRACE_S", 3600.0) - 600
            os.utime(handle["path"], (old, old))
        return handle

    def _runtime_version(self, index, aged=True):
        """第 index 份内容互不相同的 runtime 缓存。"""
        return self._aged(cp.cache_artifact(
            self.artifact_archive("relogin_ocr_runtime", {"feature-helper.exe": b"MZv%d" % index}),
            "relogin_ocr_runtime", root=self.root), aged)

    def _model(self):
        return self._aged(cp.cache_artifact(self.artifact_archive("relogin_ocr_model"),
                                            "relogin_ocr_model", root=self.root))

    def _cache_names(self, artifact_id):
        cache = self.root / "advanced" / "assets" / ".cache" / artifact_id
        return {path.name for path in cache.iterdir()} if cache.is_dir() else set()

    def test_group_switch_keeps_only_new_and_previous_cache(self):
        """K2：切换两次以上后，更早的组不再占着缓存目录。"""
        model = self._model()
        other = cp.cache_artifact(self.artifact_archive("phone_control_runtime"),
                                  "phone_control_runtime", root=self.root)
        digests = []
        for index in range(3):
            runtime = self._runtime_version(index)
            digests.append(runtime["content_sha256"])
            cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
            if index == 1:
                self.assertEqual(self._cache_names("relogin_ocr_runtime"),
                                 {digests[0], digests[1]}, "第二次切换：新组与上一组")
        self.assertEqual(self._cache_names("relogin_ocr_runtime"), {digests[1], digests[2]},
                         "第三次切换后只剩新组与切换前那一组")
        self.assertEqual(self._cache_names("relogin_ocr_model"), {model["content_sha256"]})
        self.assertEqual(self._cache_names("phone_control_runtime"), {other["content_sha256"]},
                         "别的功能的缓存不归这次回收管")
        state = cp.feature_status("relogin_ocr", root=self.root)
        self.assertTrue(state["available"])
        self.assertEqual(state["artifacts"]["relogin_ocr_runtime"]["content_sha256"], digests[2])

    def test_fresh_uncommitted_cache_survives_group_switch(self):
        """K2：刚备好、还没提交的下一组不在「旧组」之列，别的提交不能顺手删掉它。"""
        model = self._model()
        first = self._runtime_version(0)
        cp.commit_artifact_group("relogin_ocr", [first, model], root=self.root)
        second = self._runtime_version(1)
        cp.commit_artifact_group("relogin_ocr", [second, model], root=self.root)
        fresh = self._runtime_version(2, aged=False)
        cp.commit_artifact_group("relogin_ocr", [first, model], root=self.root)
        self.assertIn(fresh["content_sha256"], self._cache_names("relogin_ocr_runtime"))
        cp.commit_artifact_group("relogin_ocr", [fresh, model], root=self.root)
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])

    def test_cache_reclaim_failure_is_only_a_diagnostic(self):
        """K2：回收删不掉不能推翻已经完成的指针切换。"""
        model = self._model()
        for index in range(2):
            cp.commit_artifact_group("relogin_ocr", [self._runtime_version(index), model],
                                     root=self.root)
        third = self._runtime_version(2)
        with mock.patch.object(cp.shutil, "rmtree", side_effect=OSError("locked")):
            result = cp.commit_artifact_group("relogin_ocr", [third, model], root=self.root)
        self.assertTrue(result["ok"])
        log = self.root / "advanced" / ".diagnostics.log"
        self.assertIn("缓存清理失败", log.read_text(encoding="utf-8"))
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])

    def test_unsupported_compatibility_id_is_reported_incompatible(self):
        """K3：客户端只认自己支持的 compatibility_id，组整体换口径也不照收。"""
        runtime, model = self._runtime_version(0), self._model()
        cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
        self.assertTrue(cp.feature_status("relogin_ocr", root=self.root)["available"])
        newer = frozenset({"campus-activity-2"})
        with mock.patch.object(cp, "SUPPORTED_COMPATIBILITY_IDS", newer, create=True):
            state = cp._split_group("relogin_ocr", root=self.root)
            self.assertFalse(state["available"])
            self.assertEqual(state["error"], "artifact_incompatible")
            with self.assertRaises(cp.PackageError) as caught:
                cp.commit_artifact_group("relogin_ocr", [runtime, model], root=self.root)
            self.assertEqual(caught.exception.args[0], "artifact_incompatible")

    def test_unsupported_compatibility_id_in_fixed_assets_is_incompatible(self):
        for artifact in ("relogin_ocr_runtime", "relogin_ocr_model"):
            cp.install_artifact(self.artifact_archive(artifact), artifact, root=self.root)
        self.assertTrue(cp._split_group("relogin_ocr", root=self.root)["available"])
        with mock.patch.object(cp, "SUPPORTED_COMPATIBILITY_IDS",
                               frozenset({"campus-activity-2"}), create=True):
            state = cp._split_group("relogin_ocr", root=self.root)
        self.assertFalse(state["available"])
        self.assertEqual(state["error"], "artifact_incompatible")

    def _stored_cloudflared_fixture(self):
        source = self.root / "cloudflared.exe"
        source.write_bytes(BINARY)
        text = "cloudflared version %s" % cp.CLOUDFLARED_VERSION
        cp.install_cloudflared(source, root=self.root, probe=lambda _p: text,
                               probe_text=lambda _p: text)
        return cp._root(self.root) / cp.CLOUDFLARED_STORE

    def test_stored_cloudflared_skips_probe_while_file_is_unchanged(self):
        """P3：文件没变就不再起子进程探测版本；换了文件必须重新探测。"""
        store = self._stored_cloudflared_fixture()
        target = store / cp.CLOUDFLARED_FILE
        with mock.patch.object(cp, "probe_cloudflared_version",
                               return_value=cp.CLOUDFLARED_VERSION) as probe:
            first = cp.stored_cloudflared(root=self.root)
            second = cp.stored_cloudflared(root=self.root)
            self.assertEqual(first, str(target))
            self.assertEqual(second, str(target))
            self.assertEqual(probe.call_count, 1, "第二次不应再探测")
            target.write_bytes(BINARY + b"-new")
            manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
            manifest["sha256"] = cp.sha256(target)
            (store / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(cp.stored_cloudflared(root=self.root), str(target))
            self.assertEqual(probe.call_count, 2, "文件变了（大小或时间戳）要重新探测")

    def test_stored_cloudflared_cache_does_not_hide_tampering(self):
        store = self._stored_cloudflared_fixture()
        target = store / cp.CLOUDFLARED_FILE
        with mock.patch.object(cp, "probe_cloudflared_version",
                               return_value=cp.CLOUDFLARED_VERSION):
            self.assertTrue(cp.stored_cloudflared(root=self.root))
            target.write_bytes(b"MZtampered")
            self.assertEqual(cp.stored_cloudflared(root=self.root), "",
                             "哈希对不上必须拒绝，探测缓存不能放行")

    def test_injected_probe_is_never_cached(self):
        self._stored_cloudflared_fixture()
        text = "cloudflared version %s" % cp.CLOUDFLARED_VERSION
        self.assertTrue(cp.stored_cloudflared(root=self.root, probe=lambda _p: text))
        self.assertEqual(cp.stored_cloudflared(root=self.root, probe=lambda _p: ""), "")

    _CROSS_PROCESS_READER = """
import contextlib, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from infrastructure import component_packages as cp
if sys.argv[4] == "unlocked":
    cp._file_transaction = lambda root: contextlib.nullcontext()
root, ready = sys.argv[2], Path(sys.argv[3])
allowed, model = set(sys.argv[5].split(",")), sys.argv[6]
stop = Path(sys.argv[3] + ".stop")
bad, count = [], 0
ready.write_text("ready")
while not stop.exists() and count < 200000:
    count += 1
    time.sleep(0.003 if sys.argv[4] == "locked" else 0)
    try:
        state = cp.feature_status("relogin_ocr", root=root)
        arts = state.get("artifacts") or {}
        runtime = arts.get("relogin_ocr_runtime", {}).get("content_sha256")
        mdl = arts.get("relogin_ocr_model", {}).get("content_sha256")
        if not (state.get("available") and runtime in allowed and mdl == model):
            bad.append([state.get("source"), state.get("error"), runtime, mdl])
    except Exception as exc:
        bad.append(["exception", type(exc).__name__])
    if len(bad) >= 5:
        break
print(json.dumps({"count": count, "bad": bad}))
"""

    def _cross_process_switch(self, mode):
        """另一个进程反复读组状态，本进程反复在三份 runtime 之间切换。"""
        model = self._model()
        runtimes = [self._runtime_version(index) for index in range(3)]
        digests = [item["content_sha256"] for item in runtimes]
        cp.commit_artifact_group("relogin_ocr", [runtimes[0], model], root=self.root)
        ready = self.root / "reader.ready"
        local = str(Path(cp.__file__).resolve().parents[1])
        child = subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", self._CROSS_PROCESS_READER, local,
             str(self.root), str(ready), mode, ",".join(digests), model["content_sha256"]],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            deadline = time.monotonic() + 30
            while not ready.exists() and time.monotonic() < deadline and child.poll() is None:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "读进程没有起来")
            with contextlib.ExitStack() as stack:
                if mode == "unlocked":
                    # 证明用的空锁替身：读写两边都不拿跨进程锁
                    stack.enter_context(mock.patch.object(
                        cp, "_file_transaction", lambda root: contextlib.nullcontext()))
                for _ in range(12):
                    for index in range(3):
                        # 每轮重新备好这一组：被回收掉的旧目录会按内容寻址重建
                        item = self._runtime_version(index)
                        cp.commit_artifact_group("relogin_ocr", [item, model], root=self.root)
            Path(str(ready) + ".stop").write_text("stop")
            out, err = child.communicate(timeout=60)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0, err)
        return json.loads(out.strip().splitlines()[-1])

    def test_cross_process_reader_never_sees_a_half_switched_group(self):
        """K6：读写分属两个进程，读到的组必须完整（runtime 与 model 配套、版本在已提交集合内）。"""
        result = self._cross_process_switch("locked")
        self.assertGreater(result["count"], 0)
        self.assertEqual(result["bad"], [])

    def test_split_artifacts_install_as_a_complete_legacy_safe_group(self):
        runtime = self.artifact_archive("relogin_ocr_runtime")
        model = self.artifact_archive("relogin_ocr_model")
        cp.install_artifact(runtime, "relogin_ocr_runtime", root=self.root)
        self.assertFalse(cp.feature_status("relogin_ocr", root=self.root)["available"])
        cp.install_artifact(model, "relogin_ocr_model", root=self.root)
        state = cp.feature_status("relogin_ocr", root=self.root)
        self.assertTrue(state["available"])
        self.assertEqual(state["source"], "split")
        self.assertTrue((self.root / "advanced" / "assets" /
                         "relogin_ocr_model" / "models" / "common.onnx").is_file())

    def test_split_artifact_mismatch_does_not_replace_existing_asset(self):
        good = self.artifact_archive("relogin_ocr_model")
        cp.install_artifact(good, "relogin_ocr_model", root=self.root)
        bad = self.artifact_archive("relogin_ocr_runtime")
        with self.assertRaises(cp.PackageError):
            cp.install_artifact(bad, "relogin_ocr_model", root=self.root)
        self.assertTrue(cp.artifact_status("relogin_ocr_model", root=self.root)["available"])

    def test_split_invoke_prefers_complete_group_and_passes_model_root(self):
        cp.install_artifact(self.artifact_archive("relogin_ocr_runtime"),
                            "relogin_ocr_runtime", root=self.root)
        cp.install_artifact(self.artifact_archive("relogin_ocr_model"),
                            "relogin_ocr_model", root=self.root)
        result = cp.invoke("relogin_ocr", {"op": "ocr", "image": "data:image/png;base64,AA=="},
                           root=self.root)
        self.assertTrue(result["ok"])
        args = self.helper.call_args.kwargs
        self.assertIn("CAMPUS_OCR_MODEL_ROOT", args["env"])
        self.assertIn("relogin_ocr_model", args["env"]["CAMPUS_OCR_MODEL_ROOT"])

    def test_split_cloudflared_precedes_legacy_sources(self):
        cp.install_artifact(self.artifact_archive("phone_control_cloudflared",
                                                   {cp.CLOUDFLARED_NAME: BINARY}),
                            "phone_control_cloudflared", root=self.root)
        found = cp.cloudflared(root=self.root,
                               probe=lambda _path: cp.CLOUDFLARED_VERSION)
        self.assertTrue(found.replace("\\", "/").endswith(cp.CLOUDFLARED_NAME))

    def test_remove_feature_also_removes_split_artifacts(self):
        cp.install_artifact(self.artifact_archive("phone_control_runtime"),
                            "phone_control_runtime", root=self.root)
        cp.install_artifact(self.artifact_archive(
            "phone_control_cloudflared", {cp.CLOUDFLARED_NAME: BINARY}),
            "phone_control_cloudflared", root=self.root)
        cp.remove("phone_control", root=self.root)
        self.assertFalse((self.root / "advanced" / "assets" /
                          "phone_control_runtime").exists())
        self.assertFalse((self.root / "advanced" / "assets" /
                          "phone_control_cloudflared").exists())

    def test_valid_install_tamper_and_independent_remove(self):
        cp.install(self.archive(), self.key, root=self.root)
        self.assertTrue(cp.status(self.key, root=self.root)["available"])
        self.assertFalse(cp.status("relogin_ocr", root=self.root)["available"])
        (self.target / "feature-helper.exe").write_bytes(b"tampered")
        self.assertEqual(cp.status(self.key, root=self.root)["error"], "component_invalid")
        with self.assertRaises(cp.PackageError):
            cp.invoke(self.key, {"op": "qr", "url": "http://localhost/"}, root=self.root)
        sibling = self.root / "advanced" / "relogin_ocr"
        sibling.mkdir()
        (sibling / "keep").write_bytes(b"keep")
        cp.remove(self.key, root=self.root)
        self.assertTrue((sibling / "keep").is_file())

    def test_replacement_failure_restores_original_bytes(self):
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        archive = self.archive(data=b"new")
        original = os.replace
        def fail_stage(source, destination):
            if Path(source).name.startswith(".stage-"):
                raise OSError("replacement denied")
            return original(source, destination)
        with mock.patch.object(cp.os, "replace", side_effect=fail_stage):
            with self.assertRaises(OSError):
                cp.install(archive, self.key, root=self.root)
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"old")
        self.assertEqual({p.name for p in self.target.parent.iterdir()}, {self.key, "assets"})

    def test_probe_failure_preserves_old_component(self):
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        self.helper.side_effect = cp.PackageError("helper_failed")
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(data=b"new"), self.key, root=self.root)
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"old")

    def test_interrupted_replacement_restores_backup_on_first_status(self):
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        backup = self.target.parent / (".backup-" + self.key)
        os.replace(self.target, backup)
        self.assertTrue(cp.status(self.key, root=self.root)["available"])
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"old")
        self.assertFalse(backup.exists())

    def test_recovery_discards_backup_after_new_target_is_in_place(self):
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        backup = self.target.parent / (".backup-" + self.key)
        shutil.copytree(self.target, backup)
        self.assertTrue(cp.status(self.key, root=self.root)["available"])
        self.assertTrue(self.target.is_dir())
        self.assertFalse(backup.exists(), "新目录已落位后不应留下旧 backup")

    def test_recovery_reclaims_orphan_component_stage(self):
        """缺陷 5：持事务锁的操作应回收崩溃留下的同功能阶段目录（可能上百 MB）。"""
        stage = self.target.parent / (".stage-%s-orphan" % self.key)
        stage.mkdir(parents=True)
        (stage / "partial").write_bytes(b"partial")
        self.assertFalse(cp.status(self.key, root=self.root)["available"])
        self.assertFalse(stage.exists(), "崩溃留下的阶段目录应在下次持锁操作时回收")

    def test_lock_free_split_query_keeps_stage_directories(self):
        """不持事务锁的只读查询不回收任何目录。"""
        stage = self.target.parent / (".stage-%s-orphan" % self.key)
        stage.mkdir(parents=True)
        (stage / "partial").write_bytes(b"partial")
        state = cp._split_group(self.key, root=self.root)
        self.assertFalse(state["available"])
        self.assertTrue(stage.exists(), "不持锁的读路径不能删阶段目录")

    def test_leftover_backup_that_cannot_be_removed_aborts_without_losing_target(self):
        """缺陷 2：残留 backup 删不掉时中止安装，正在用的 target 不许被删或被旧副本顶替。"""
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        backup = self.target.parent / (".backup-" + self.key)
        shutil.copytree(self.target, backup)
        (backup / "feature-helper.exe").write_bytes(b"stale")
        real_rmtree = shutil.rmtree

        def busy_rmtree(path, *args, **kwargs):
            if Path(path) == backup:
                return                      # 杀软占用：删不动，也不抛
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(cp.shutil, "rmtree", side_effect=busy_rmtree):
            with self.assertRaises(cp.PackageError):
                cp.install(self.archive(data=b"new"), self.key, root=self.root)
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"old")
        self.assertTrue(cp.status(self.key, root=self.root)["available"])

    def test_cleanup_failure_after_commit_still_reports_success(self):
        """缺陷 4：新目录已落位后清不掉旧 backup，不能反过来报安装失败。"""
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        backup = self.target.parent / (".backup-" + self.key)
        real_rmtree = shutil.rmtree

        def locked_rmtree(path, *args, **kwargs):
            if Path(path) == backup:
                raise PermissionError("locked")
            return real_rmtree(path, *args, **kwargs)

        with mock.patch.object(cp.shutil, "rmtree", side_effect=locked_rmtree):
            result = cp.install(self.archive(data=b"new"), self.key, root=self.root)
        self.assertTrue(result["ok"])
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"new")
        self.assertTrue(cp.feature_status(self.key, root=self.root)["available"])

    def test_empty_transaction_journal_keeps_component_usable(self):
        """缺陷 3：日志断电留空文件，读状态、取 cloudflared、移除都不能抛。"""
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        journal = self.target.parent / (".transaction-" + self.key + ".json")
        journal.write_text("", encoding="utf-8")
        self.assertTrue(cp.status(self.key, root=self.root)["available"])
        self.assertTrue(cp.feature_status(self.key, root=self.root)["available"])
        found = cp.cloudflared(root=self.root, probe=lambda _p: cp.CLOUDFLARED_VERSION)
        self.assertTrue(found.replace("\\", "/").endswith(cp.CLOUDFLARED_NAME))
        self.assertEqual((self.target / "feature-helper.exe").read_bytes(), b"old")
        cp.remove(self.key, root=self.root)
        self.assertFalse(self.target.exists())

    def test_bad_json_journal_and_pointer_do_not_raise(self):
        """缺陷 3：日志/指针内容损坏只算这一步没发生过，不能把程序拖垮。"""
        cp.install(self.archive(data=b"old"), self.key, root=self.root)
        journal = self.target.parent / (".transaction-" + self.key + ".json")
        journal.write_text("{not json", encoding="utf-8")
        self.assertTrue(cp.feature_status(self.key, root=self.root)["available"])
        self.assertTrue(cp.cloudflared(root=self.root, probe=lambda _p: cp.CLOUDFLARED_VERSION))

        group = cp._root(self.root) / cp.ARTIFACT_ROOT / ".groups"
        pointer = group / "relogin_ocr.json"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text("{not json", encoding="utf-8")
        state = cp.feature_status("relogin_ocr", root=self.root)
        self.assertFalse(state["available"])
        self.assertEqual(cp.cloudflared(root=self.root, probe=lambda _p: ""), "")
        cp.remove("relogin_ocr", root=self.root)
        self.assertFalse(pointer.exists())

    def test_atomic_json_syncs_file_and_directory(self):
        """缺陷 3：指针落盘要 fsync 文件和目录，否则断电后指针可能是空的。"""
        pointer = cp._root(self.root) / cp.ARTIFACT_ROOT / ".groups" / "relogin_ocr.json"
        with mock.patch.object(cp.os, "fsync", wraps=cp.os.fsync) as synced:
            cp._write_group_pointer("relogin_ocr", {"feature": "relogin_ocr"}, self.root)
        self.assertGreaterEqual(synced.call_count, 1)
        self.assertEqual(json.loads(pointer.read_text(encoding="utf-8"))["feature"],
                         "relogin_ocr")

    def test_untrusted_paths_extras_duplicates_platform_and_feature(self):
        for name in ("../evil", "/evil", "C:/evil", "a\\evil", "nul.exe", "file:stream", "x./y"):
            with self.subTest(name=name), self.assertRaises(cp.PackageError):
                cp.install(self.archive(extra={name: b"bad"}), self.key, root=self.root)
        for kwargs in ({"extra": {"extra": b"bad"}}, {"platform": "linux-x64"},
                       {"feature": "relogin_ocr"}, {"extra": {"FEATURE-HELPER.EXE": b"bad"}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(cp.PackageError):
                cp.install(self.archive(**kwargs), self.key, root=self.root)
        self.assertFalse(self.target.exists())

    def test_symlink_size_limits_and_hash_mismatch(self):
        archive = self.archive()
        with zipfile.ZipFile(archive, "a") as z:
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(link, "outside")
        with self.assertRaises(cp.PackageError):
            cp.install(archive, self.key, root=self.root)
        for constant in ("MAX_ARCHIVE", "MAX_EXTRACTED", "MAX_FILES"):
            archive = self.archive()
            with mock.patch.object(cp, constant, 1), self.assertRaises(cp.PackageError):
                cp.install(archive, self.key, root=self.root)
        archive = self.archive()
        with zipfile.ZipFile(archive) as z:
            contents = {n: z.read(n) for n in z.namelist()}
        contents["feature-helper.exe"] = b"tampered"
        with zipfile.ZipFile(archive, "w") as z:
            for name, raw in contents.items():
                z.writestr(name, raw)
        with self.assertRaises(cp.PackageError):
            cp.install(archive, self.key, root=self.root)



    def test_phone_control_must_declare_cloudflared(self):
        """phone_control 缺声明直接拒绝；relogin_ocr 反过来不许携带。"""
        bare = {"feature-helper.exe": b"MZtest", "_internal/test.dll": b"library"}
        with self.assertRaises(cp.PackageError) as missing:
            cp.install(self.archive(names=bare, cloudflare=None), self.key, root=self.root)
        self.assertEqual(missing.exception.args[0], "cloudflared_required")
        self.assertFalse(self.target.exists())
        cp.install(self.archive(feature="relogin_ocr", names=bare, cloudflare=None),
                   "relogin_ocr", root=self.root)
        carried = dict(bare)
        carried[cp.CLOUDFLARED_NAME] = BINARY
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(feature="relogin_ocr", names=carried, cloudflare=None),
                       "relogin_ocr", root=self.root)

    def test_cloudflared_metadata_must_match_bundled_binary(self):
        binary = BINARY
        bare = {"feature-helper.exe": b"MZtest", "_internal/test.dll": b"library"}
        good = {"version": cp.CLOUDFLARED_VERSION,
                "sha256": hashlib.sha256(binary).hexdigest()}
        names = dict(bare)
        names[cp.CLOUDFLARED_NAME] = binary
        # 声明了版本却没放二进制：拒绝
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(names=bare, cloudflare=good), self.key, root=self.root)
        # 放了二进制却没声明版本：拒绝（不能假装知道它是什么）
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(names=names, cloudflare=None), self.key, root=self.root)
        # 哈希对不上：拒绝
        wrong = dict(good, sha256="0" * 64)
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(names=names, cloudflare=wrong), self.key, root=self.root)
        # 版本不是写死的那个：拒绝
        drift = dict(good, version="2026.1.1")
        with self.assertRaises(cp.PackageError):
            cp.install(self.archive(names=names, cloudflare=drift), self.key, root=self.root)
        cp.install(self.archive(names=names, cloudflare=good), self.key, root=self.root)
        self.assertTrue((self.target / cp.CLOUDFLARED_NAME).is_file())

    def test_cloudflared_probe_gates_availability(self):
        binary = b"MZcloudflared"
        names = {"feature-helper.exe": b"MZtest", "_internal/test.dll": b"library",
                 cp.CLOUDFLARED_NAME: binary}
        meta = {"version": cp.CLOUDFLARED_VERSION,
                "sha256": hashlib.sha256(binary).hexdigest()}
        cp.install(self.archive(names=names, cloudflare=meta), self.key, root=self.root)
        ok = cp.cloudflared(root=self.root,
                            probe=lambda _p: "cloudflared version %s (built x)" % cp.CLOUDFLARED_VERSION)
        self.assertTrue(ok.endswith(cp.CLOUDFLARED_NAME.replace("/", os.sep))
                        or ok.endswith("cloudflared.exe"))
        # probe 报错/版本不符/根本没跑起来：一律不可用，绝不把没验证的二进制交出去
        self.assertEqual(cp.cloudflared(root=self.root, probe=lambda _p: ""), "")
        self.assertEqual(cp.cloudflared(root=self.root, probe=lambda _p: "cloudflared version 2026.1.1"), "")
        self.assertEqual(cp.cloudflared(root=self.root, probe=lambda _p: "boom"), "")

    def test_inspect_cloudflared_says_what_the_file_really_is(self):
        """自检必须能说「这到底是什么」，不能只回一个「不行」。"""
        missing = self.root / "nope.exe"
        self.assertEqual(cp.inspect_cloudflared(missing)["kind"], "missing")

        not_exe = self.root / "README.md"
        not_exe.write_text("说明", encoding="utf-8")
        self.assertEqual(cp.inspect_cloudflared(not_exe)["kind"], "not_executable")

        good = self.root / "cloudflared.exe"
        good.write_bytes(BINARY)
        version_text = lambda _p: "cloudflared version 2026.10.7 (built 2026-10-30T09:43 UTC)"
        info = cp.inspect_cloudflared(good, probe_text=version_text)
        self.assertTrue(info["ok"])
        self.assertEqual(info["version"], cp.CLOUDFLARED_VERSION)

        stale = cp.inspect_cloudflared(
            good, probe_text=lambda _p: "cloudflared version 2025.1.1 (built 2025-01-01)")
        self.assertFalse(stale["ok"])
        self.assertEqual(stale["kind"], "version")
        self.assertIn(cp.CLOUDFLARED_VERSION, stale["text"])

        tailscale = self.root / "tailscale.exe"
        tailscale.write_bytes(BINARY)
        picked = cp.inspect_cloudflared(
            tailscale, probe_text=lambda _p: "tailscale v1.80.0 tailscale is a mesh VPN")
        self.assertFalse(picked["ok"])
        self.assertEqual(picked["kind"], "tailscale")
        self.assertIn("Tailscale", picked["text"])

        mute = cp.inspect_cloudflared(good, probe_text=lambda _p: "")
        self.assertEqual(mute["kind"], "unreadable")

    def test_install_cloudflared_stores_a_verified_copy(self):
        source = self.root / "cloudflared.exe"
        source.write_bytes(BINARY)
        text = "cloudflared version 2026.10.7 (built 2026-10-30T09:43 UTC)"
        result = cp.install_cloudflared(
            source, root=self.root, probe=lambda _p: text, probe_text=lambda _p: text)
        self.assertTrue(result["ok"])

        stored = cp._root(self.root) / cp.CLOUDFLARED_STORE
        self.assertTrue((stored / cp.CLOUDFLARED_FILE).is_file())
        manifest = json.loads((stored / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], cp.CLOUDFLARED_VERSION)
        self.assertEqual(manifest["sha256"], cp.sha256(stored / cp.CLOUDFLARED_FILE))

        self.assertEqual(cp.stored_cloudflared(root=self.root, probe=lambda _p: text),
                         str(stored / cp.CLOUDFLARED_FILE))
        # 复制之后重新 probe：落盘这份和选文件时那份不一样，就不算装成功
        self.assertEqual(cp.stored_cloudflared(root=self.root, probe=lambda _p: ""), "")

    def test_install_cloudflared_refuses_the_wrong_file(self):
        decoy = self.root / "tailscale.exe"
        decoy.write_bytes(BINARY)
        with self.assertRaises(cp.PackageError) as caught:
            cp.install_cloudflared(
                decoy, root=self.root, probe_text=lambda _p: "tailscale v1.80.0")
        self.assertEqual(caught.exception.args[0], "tailscale")
        self.assertFalse((cp._root(self.root) / cp.CLOUDFLARED_STORE).exists())

    def test_stored_cloudflared_rejects_tampering(self):
        source = self.root / "cloudflared.exe"
        source.write_bytes(BINARY)
        text = "cloudflared version 2026.10.7"
        cp.install_cloudflared(source, root=self.root, probe=lambda _p: text,
                               probe_text=lambda _p: text)
        target = cp._root(self.root) / cp.CLOUDFLARED_STORE / cp.CLOUDFLARED_FILE
        target.write_bytes(b"MZtampered")
        self.assertEqual(cp.stored_cloudflared(root=self.root, probe=lambda _p: text), "")

    def test_stored_cloudflared_recovers_interrupted_swap(self):
        """换位中断后只剩 cloudflared.bak：读取前先恢复，不能当成没装。"""
        source = self.root / "cloudflared.exe"
        source.write_bytes(BINARY)
        text = "cloudflared version 2026.10.7"
        cp.install_cloudflared(source, root=self.root, probe=lambda _p: text,
                               probe_text=lambda _p: text)
        store = cp._root(self.root) / cp.CLOUDFLARED_STORE
        backup = store.with_name(cp.CLOUDFLARED_STORE + ".bak")
        os.replace(store, backup)       # 模拟 store → .bak 之后、stage → store 之前崩溃
        path = cp.stored_cloudflared(root=self.root, probe=lambda _p: text)
        self.assertEqual(path, str(store / cp.CLOUDFLARED_FILE))
        self.assertTrue(store.is_dir(), "读取时应把 .bak 恢复成正式目录")
        self.assertFalse(backup.exists(), "恢复后不应残留 .bak")

    def test_stored_cloudflared_discards_backup_and_orphan_stage(self):
        source = self.root / "cloudflared.exe"
        source.write_bytes(BINARY)
        text = "cloudflared version 2026.10.7"
        cp.install_cloudflared(source, root=self.root, probe=lambda _p: text,
                               probe_text=lambda _p: text)
        store = cp._root(self.root) / cp.CLOUDFLARED_STORE
        backup = store.with_name(cp.CLOUDFLARED_STORE + ".bak")
        shutil.copytree(store, backup)
        stage = cp._root(self.root) / ".stage-cf-orphan"
        stage.mkdir()
        (stage / "partial").write_bytes(b"partial")
        self.assertTrue(cp.stored_cloudflared(root=self.root, probe=lambda _p: text))
        self.assertFalse(backup.exists(), "新目录已落位后不应留下 cloudflared backup")
        self.assertFalse(stage.exists(), "持锁读取时应回收崩溃留下的阶段目录")

    def test_inspect_archive_names_the_component_it_found(self):
        good = self.archive()
        info = cp.inspect_archive(good, "phone_control")
        self.assertTrue(info["ok"])
        self.assertEqual(info["feature"], "phone_control")

        plain = self.root / "notes.zip"
        with zipfile.ZipFile(plain, "w") as package:
            package.writestr("readme.txt", "nothing")
        self.assertEqual(cp.inspect_archive(plain, "phone_control")["kind"], "not_component")

        other = self.archive(feature="relogin_ocr")
        wrong = cp.inspect_archive(other, "phone_control")
        self.assertFalse(wrong["ok"])
        self.assertEqual(wrong["kind"], "wrong_feature")
        self.assertIn("验证码识别", wrong["text"])

    def test_parse_cloudflared_version(self):
        self.assertEqual(cp.parse_cloudflared_version(
            "cloudflared version 2026.10.7 (built 2026-10-30T09:43 UTC)"), "2026.10.7")
        self.assertEqual(cp.parse_cloudflared_version(""), "")
        self.assertEqual(cp.parse_cloudflared_version("no version here"), "")

    def test_target_and_app_version_are_checked_when_declared(self):
        """新加的声明字段只做严格校验：写错要拒，不写仍兼容老包。"""
        cp.install(self.archive(), self.key, root=self.root)
        self.assertTrue(cp.status(self.key, root=self.root)["available"])

        with self.assertRaises(cp.PackageError) as target:
            cp.install(self.archive(target="win-arm64"), self.key, root=self.root)
        self.assertIn("bad_target", str(target.exception))

        with self.assertRaises(cp.PackageError) as version:
            cp.install(self.archive(app_version="0.0.1"), self.key, root=self.root)
        self.assertIn("bad_app_version", str(version.exception))

    def test_install_dir_is_root_advanced_key_and_touches_nothing(self):
        """B3 的位置只靠这一个函数算出来：落在 <根>/advanced/<功能>，不建目录、不认未知键。"""
        for key in ("phone_control", "relogin_ocr"):
            with self.subTest(feature=key):
                self.assertEqual(cp.install_dir(key, root=self.root),
                                 (self.root / "advanced" / key).resolve())
        self.assertFalse((self.root / "advanced").exists(), "只算位置，不创建目录")
        for bad in ("segno", "", "..", "phone_control/.."):
            with self.subTest(key=bad):
                with self.assertRaises(cp.PackageError):
                    cp.install_dir(bad, root=self.root)

    def test_status_reports_installed_version(self):
        self.assertEqual(cp.status(self.key, root=self.root).get("version"), "")
        cp.install(self.archive(app_version=cp.version()), self.key, root=self.root)
        state = cp.status(self.key, root=self.root)
        self.assertTrue(state["available"])
        self.assertEqual(state["version"], cp.version())


class CloudflaredUsageTests(unittest.TestCase):
    def test_other_process_cannot_remove_active_component_or_tool(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
            root = Path(temporary)
            target = root / "advanced" / "phone_control"
            target.mkdir(parents=True)
            sentinel = target / "sentinel"
            sentinel.write_bytes(b"current-group")
            ready = root / "ready"
            child = r'''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from infrastructure import component_packages as cp
root = Path(sys.argv[2])
path = str(root / "advanced/phone_control/cloudflared.exe")
cp.cloudflared = lambda **kwargs: path
with cp.cloudflared_usage(path, root=root):
    (root / "ready").write_text("ready", encoding="utf-8")
    sys.stdin.readline()
'''
            proc = subprocess.Popen(
                [sys.executable, "-X", "utf8", "-c", child,
                 str(Path(__file__).resolve().parents[1]), str(root)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                deadline = time.monotonic() + 10
                while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready.exists(), "子进程必须先拿到使用锁")
                for operation in (
                        lambda: cp.remove("phone_control", root=root),
                        lambda: cp.remove_cloudflared(root=root),
                        lambda: cp.install(root / "missing.zip", "phone_control", root=root),
                        lambda: cp.install_artifact(root / "missing.zip", "phone_control_runtime", root=root),
                        lambda: cp.commit_artifact_group("phone_control", [], root=root),
                        lambda: cp.install_cloudflared(root / "missing.exe", root=root)):
                    with self.assertRaisesRegex(cp.PackageError, "component_in_use"):
                        operation()
                    self.assertEqual(sentinel.read_bytes(), b"current-group")
                proc.communicate(b"stop\n", timeout=10)
                self.assertEqual(proc.returncode, 0)
                cp.remove("phone_control", root=root)
                self.assertFalse(target.exists())
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate(timeout=10)

    def test_failed_path_verification_releases_usage_lock(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
            with mock.patch.object(cp, "cloudflared", return_value=""):
                with self.assertRaisesRegex(cp.PackageError, "cloudflared_untrusted"):
                    with cp.cloudflared_usage("missing.exe", root=temporary):
                        self.fail("校验失败不能进入运行期")
            self.assertTrue(cp.remove_cloudflared(root=temporary)["ok"])

    def test_usage_can_be_released_by_stop_on_another_thread(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as temporary:
            executable = str(Path(temporary) / "cloudflared.exe")
            with mock.patch.object(cp, "cloudflared", return_value=executable):
                usage = cp.cloudflared_usage(executable, root=temporary)
                usage.__enter__()
            stopped = threading.Thread(target=lambda: usage.__exit__(None, None, None))
            stopped.start()
            stopped.join(timeout=5)
            self.assertFalse(stopped.is_alive())
            self.assertTrue(cp.remove_cloudflared(root=temporary)["ok"])


if __name__ == "__main__":
    unittest.main()
