# -*- coding: utf-8 -*-
"""独立 ZIP 的真实文件校验与替换失败回滚；helper 仅用替身。

@author Author
"""
import hashlib
import json
import os
import stat
import sys
import subprocess
import tempfile
import threading
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
        self.assertEqual([p.name for p in self.target.parent.iterdir()], [self.key])

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


if __name__ == "__main__":
    unittest.main()
