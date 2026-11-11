"""文件级增量包的离线契约测试。"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

import update_delta  # noqa: E402


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="campus-delta-test-"))
        self.base = self.root / "base"
        self.target = self.root / "target"
        self.staging = self.root / "staging"
        self.base.mkdir()
        self.target.mkdir()
        (self.base / "keep.txt").write_text("same", encoding="utf-8")
        (self.base / "replace.txt").write_text("old", encoding="utf-8")
        (self.base / "remove.txt").write_text("gone", encoding="utf-8")
        shutil.copytree(self.base, self.target, dirs_exist_ok=True)
        (self.target / "replace.txt").write_text("new", encoding="utf-8")
        (self.target / "remove.txt").unlink()
        (self.target / "add.txt").write_text("added", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_build_apply_and_manifest_match(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        changed = {item["path"] for item in delta["files"]}
        self.assertEqual(changed, {"add.txt", "replace.txt"})
        self.assertEqual(delta["deletions"], ["remove.txt"])
        update_delta.apply_delta(self.base, delta, self.staging, base_version="1.0.0")
        self.assertEqual(update_delta.manifest_from_directory(self.staging, version="1.2.2"),
                         delta["target_manifest"])
        self.assertEqual(update_delta.verify_directory(self.staging, delta["target_manifest"]), True)

    def test_same_file_is_reused(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        self.assertNotIn("keep.txt", {item["path"] for item in delta["files"]})

    def test_manifest_hash_uses_global_path_order(self):
        """跨目录遍历顺序不能影响目标清单哈希。"""
        (self.base / "z-dir").mkdir()
        (self.base / "z-dir" / "b.txt").write_bytes(b"b")
        (self.base / "a-dir").mkdir()
        (self.base / "a-dir" / "a.txt").write_bytes(b"a")
        manifest = update_delta.manifest_from_directory(self.base, version="1.0.0")
        paths = [entry["path"] for entry in manifest["files"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(manifest["target_manifest_sha256"],
                         update_delta._manifest_hash(manifest))

    def test_hash_error_does_not_pollute_staging(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        delta["files"][0]["sha256"] = "0" * 64
        self.staging.mkdir()
        (self.staging / "sentinel.txt").write_text("untouched", encoding="utf-8")
        with self.assertRaises(update_delta.DeltaError):
            update_delta.apply_delta(self.base, delta, self.staging, base_version="1.0.0")
        self.assertEqual((self.staging / "sentinel.txt").read_text(encoding="utf-8"), "untouched")

    def test_base_version_mismatch(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        with self.assertRaises(update_delta.DeltaError):
            update_delta.apply_delta(self.base, delta, self.staging, base_version="9.9.9")
        self.assertFalse(self.staging.exists())

    def test_path_escape_is_rejected(self):
        with self.assertRaises(update_delta.DeltaError):
            update_delta.validate_relative_path("../outside.txt")
        with self.assertRaises(update_delta.DeltaError):
            update_delta.validate_relative_path("C:/outside.txt")
        try:
            (self.base / "link.txt").symlink_to(self.base / "keep.txt")
        except OSError:
            self.skipTest("当前 Windows 运行环境未授予创建符号链接的权限")
        with self.assertRaises(update_delta.DeltaError):
            update_delta.manifest_from_directory(self.base, version="1.0.0")

    def test_corrupt_zip_is_rejected_without_staging_change(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        archive = self.root / "delta.zip"
        update_delta.write_delta_zip(delta, archive)
        archive.write_bytes(b"not-a-zip")
        self.staging.mkdir()
        (self.staging / "sentinel.txt").write_text("untouched", encoding="utf-8")
        with self.assertRaises(update_delta.DeltaError):
            update_delta.apply_delta(self.base, archive, self.staging, base_version="1.0.0")
        self.assertTrue((self.staging / "sentinel.txt").exists())

    def test_zip_round_trip(self):
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        archive = self.root / "delta.zip"
        update_delta.write_delta_zip(delta, archive)
        update_delta.apply_delta(self.base, archive, self.staging, base_version="1.0.0")
        self.assertTrue((self.staging / "add.txt").is_file())
        self.assertFalse((self.staging / "remove.txt").exists())

    def test_path_segment_with_colon_is_rejected(self):
        """NTFS 备用数据流写法 name:stream 会把内容藏进别的文件，含冒号的路径一律拒绝。"""
        for bad in ("lib/app.dll:evil", "a:b", "dir:s/file.txt", "file.txt::$DATA"):
            with self.subTest(path=bad), self.assertRaises(update_delta.DeltaError):
                update_delta.validate_relative_path(bad)
        self.assertEqual(update_delta.validate_relative_path("lib/app.dll"), "lib/app.dll")

    def test_archive_member_larger_than_declared_size_is_rejected(self):
        """ZIP 里某文件实际大小超过清单声明时，解出之前就拒绝（防压缩炸弹撑满磁盘）。"""
        import json
        import zipfile
        delta = update_delta.build_delta(self.base, self.target, "1.0.0", "1.2.2")
        manifest = {key: value for key, value in delta.items() if not key.startswith("_")}
        manifest["files"] = [dict(item, bytes=1) if item["path"] == "add.txt" else item
                             for item in manifest["files"]]
        archive = self.root / "lying.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
            for item in manifest["files"]:
                zf.write(self.target / item["path"], "files/" + item["path"])
        extraction = None
        try:
            with self.assertRaises(update_delta.DeltaError):
                _manifest, extraction, _ = update_delta._load_archive(archive)
        finally:
            if extraction is not None:
                shutil.rmtree(extraction, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
