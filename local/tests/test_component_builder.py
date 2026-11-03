# -*- coding: utf-8 -*-
"""构建入口与 helper 的固定协议；不执行依赖安装或真实构建。

@author Author
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
sys.path.insert(0, str(LOCAL / "build"))   # 打包脚本在 local/build/
import advanced_helper
import build_advanced as builder


class BuilderTests(unittest.TestCase):
    def test_output_is_restricted_to_explicit_temp_subdirectory(self):
        for path in ("relative", "<tmp>", "<tmp>/../elsewhere", "C:/bad"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder.output_root(path)

    def test_phone_control_without_cloudflared_is_refused(self):
        """不给 --cloudflared 就直接失败：不许产出没有远程通道的组件包。"""
        with tempfile.TemporaryDirectory(dir="<tmp>") as tmp:
            with mock.patch.object(builder.importlib.util, "find_spec", return_value=object()), \
                    mock.patch.object(builder.subprocess, "run") as run:
                with self.assertRaises(ValueError) as refused:
                    builder.build("phone_control", Path(tmp))
            self.assertIn("cloudflared_required", str(refused.exception))
            run.assert_not_called()

    def test_manifest_and_separate_dependencies(self):
        with tempfile.TemporaryDirectory(dir="<tmp>") as tmp:
            root = Path(tmp)
            binary = root / "cloudflared.exe"
            binary.write_bytes(b"MZcloudflared")
            def fake_run(command, **kwargs):
                if "--version" in command:
                    return mock.Mock(stdout="cloudflared version %s (built x)"
                                            % builder.cp.CLOUDFLARED_VERSION)
                folder = Path(command[command.index("--distpath") + 1]) / "feature-helper"
                folder.mkdir(parents=True)
                (folder / "feature-helper.exe").write_bytes(b"MZfake")
            with mock.patch.object(builder.importlib.util, "find_spec", return_value=object()), \
                    mock.patch.object(builder.subprocess, "run", side_effect=fake_run) as run, \
                    mock.patch.object(builder.cp, "_helper", return_value={"ok": True}):
                result = builder.build("phone_control", root, str(binary))
            self.assertTrue(Path(result["archive"]).is_file())
            command = run.call_args_list[0].args[0]
            self.assertIn("--onedir", command)
            self.assertIn("segno", command)
            self.assertEqual(command[command.index("--exclude-module") + 1], "ddddocr")
            manifest = json.loads((root / "phone_control/dist/feature-helper/manifest.json").read_text())
            self.assertEqual(manifest["version"], builder.cp.version())
            # 下载与安装流程要看的两项：组件包架构、它配套的主程序版本
            self.assertEqual(manifest["target"], "win-x64")
            self.assertEqual(manifest["app_version"], builder.cp.version())
            self.assertEqual(set(manifest["files"]),
                             {"feature-helper.exe", builder.cp.CLOUDFLARED_NAME})
            self.assertEqual(manifest["cloudflared"]["version"], builder.cp.CLOUDFLARED_VERSION)

    def test_helper_rejects_credentials_and_wrong_operation(self):
        with mock.patch.dict(sys.modules, {"segno": mock.Mock()}):
            for payload in ({"op": "ocr", "image": "x"},
                            {"op": "qr", "url": "https://x", "password": "fake"}):
                result = advanced_helper.run("phone_control", stream=io.BytesIO(json.dumps(payload).encode()))
                self.assertFalse(result["ok"])
                self.assertNotIn("fake", json.dumps(result))
            self.assertTrue(advanced_helper.run("phone_control", probe=True)["ok"])


if __name__ == "__main__":
    unittest.main()
