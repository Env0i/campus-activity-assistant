# -*- coding: utf-8 -*-
"""构建入口与 helper 的固定协议；不执行依赖安装或真实构建。

@author Author
"""
import io
import json
import os
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

TMP_ROOT = tempfile.gettempdir()


class BuilderTests(unittest.TestCase):
    def test_artifact_identity_is_stable_across_app_versions(self):
        files = {"models/common.onnx": "a" * 64}
        with mock.patch.object(builder.cp, "version", return_value="1.2.2"):
            first = builder._artifact_manifest("relogin_ocr_model", files)
        with mock.patch.object(builder.cp, "version", return_value="1.2.3"):
            second = builder._artifact_manifest("relogin_ocr_model", files)
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertEqual(first["content_sha256"], builder.cp.artifact_content_sha256(first))
        runtime = builder._artifact_manifest("relogin_ocr_runtime", {"feature-helper.exe": "b" * 64}, entry="feature-helper.exe")
        self.assertEqual(runtime["requires"], ["relogin_ocr_model"])

    def test_external_ocr_failures_are_not_empty_success(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp, \
                mock.patch.dict(os.environ, {"CAMPUS_OCR_MODEL_ROOT": tmp}), \
                mock.patch.dict(sys.modules, {"ddddocr": mock.Mock(), "onnxruntime": mock.Mock()}) as modules:
            for name in ("common.onnx", "common_old.onnx", "charsets-beta.json", "charsets-old.json"):
                (Path(tmp) / name).write_bytes(b"present")
            payload = json.dumps({"op": "ocr", "image": "data:image/png;base64,eA=="}).encode()
            modules["ddddocr"].DdddOcr.side_effect = ValueError("failed")
            self.assertFalse(advanced_helper.run("relogin_ocr", stream=io.BytesIO(payload))["ok"])
            modules["ddddocr"].DdddOcr.side_effect = None
            modules["ddddocr"].DdddOcr.return_value.classification.return_value = ""
            result = advanced_helper.run("relogin_ocr", stream=io.BytesIO(payload))
            self.assertTrue(result["ok"])
            self.assertEqual(result["code"], "")

    def test_model_metadata_preserves_default_aspect_ratio(self):
        _, metadata = builder._model_source_files()
        for value in metadata.values():
            self.assertEqual(value["image"], [-1, 64])
            self.assertFalse(value["word"])
            self.assertEqual(value["channel"], 1)

    def test_controlled_model_root_requires_both_usable_models(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp, \
                mock.patch.dict(os.environ, {"CAMPUS_OCR_MODEL_ROOT": tmp}), \
                mock.patch.dict(sys.modules, {"ddddocr": mock.Mock(), "onnxruntime": mock.Mock()}) as modules:
            self.assertFalse(advanced_helper.run("relogin_ocr", probe=True)["ok"])
            for name in ("common.onnx", "common_old.onnx", "charsets-beta.json", "charsets-old.json"):
                (Path(tmp) / name).write_bytes(b"present")
            modules["ddddocr"].DdddOcr.side_effect = [object(), ValueError("damaged")]
            self.assertFalse(advanced_helper.run("relogin_ocr", probe=True)["ok"])
            modules["ddddocr"].DdddOcr.side_effect = None
            self.assertTrue(advanced_helper.run("relogin_ocr", probe=True)["ok"])

    def test_controlled_model_rejects_non_png_prefix_before_inference(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp, \
                mock.patch.dict(os.environ, {"CAMPUS_OCR_MODEL_ROOT": tmp}), \
                mock.patch.object(advanced_helper, "_classify_with_external_model") as classify, \
                mock.patch.dict(sys.modules, {"ddddocr": mock.Mock(), "onnxruntime": mock.Mock()}):
            result = advanced_helper.run("relogin_ocr", stream=io.BytesIO(json.dumps({"op": "ocr", "image": "x"}).encode()))
            self.assertEqual(result.get("code"), "")
            classify.assert_not_called()

    def test_output_is_restricted_to_explicit_temp_subdirectory(self):
        for path in ("relative", "<tmp>", "<tmp>/../elsewhere", "C:/bad"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                builder.output_root(path)

    def test_phone_control_without_cloudflared_is_refused(self):
        """不给 --cloudflared 就直接失败：不许产出没有远程通道的组件包。"""
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            with mock.patch.object(builder.importlib.util, "find_spec", return_value=object()), \
                    mock.patch.object(builder.subprocess, "run") as run:
                with self.assertRaises(ValueError) as refused:
                    builder.build("phone_control", Path(tmp))
            self.assertIn("cloudflared_required", str(refused.exception))
            run.assert_not_called()

    def test_manifest_and_separate_dependencies(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
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

    def test_artifact_registry_has_four_fixed_entries(self):
        self.assertEqual(set(builder.ARTIFACTS), {
            "phone_control_runtime", "phone_control_cloudflared",
            "relogin_ocr_runtime", "relogin_ocr_model",
        })
        self.assertEqual(builder.ARTIFACTS["relogin_ocr_model"]["role"], "model")

    def test_phone_runtime_artifact_does_not_require_cloudflared(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            run_root = root / "phone_control_runtime"

            def fake_pyinstaller(feature, location, dependencies):
                folder = location / "dist" / "feature-helper"
                folder.mkdir(parents=True)
                (folder / "feature-helper.exe").write_bytes(b"MZfake")
                return folder

            with mock.patch.object(builder.importlib.util, "find_spec", return_value=object()), \
                    mock.patch.object(builder, "_pyinstaller_directory", side_effect=fake_pyinstaller), \
                    mock.patch.object(builder.cp, "_helper", return_value={"ok": True}):
                result = builder.build("phone_control_runtime", root)
            manifest = json.loads((run_root / "dist/feature-helper/manifest.json").read_text())
            self.assertEqual(manifest["schema"], 2)
            self.assertEqual(manifest["artifact_id"], "phone_control_runtime")
            self.assertEqual(manifest["role"], "runtime")
            self.assertNotIn("cloudflared", manifest)
            self.assertTrue(Path(result["archive"]).is_file())

    def test_phone_cloudflared_artifact_is_standalone_tool(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            binary = root / "cloudflared.exe"
            binary.write_bytes(b"MZcloudflared")

            def fake_run(command, **kwargs):
                self.assertIn("--version", command)
                return mock.Mock(stdout="cloudflared version %s (built x)" %
                                 builder.cp.CLOUDFLARED_VERSION, stderr="")

            with mock.patch.object(builder.subprocess, "run", side_effect=fake_run):
                result = builder.build("phone_control_cloudflared", root, str(binary))
            folder = root / "phone_control_cloudflared/dist/phone_control_cloudflared"
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["role"], "tool")
            self.assertEqual(manifest["tool"]["name"], "cloudflared")
            self.assertEqual(manifest["tool"]["version"], builder.cp.CLOUDFLARED_VERSION)
            self.assertEqual(manifest["tool"]["sha256"],
                             builder.cp.sha256(folder / builder.cp.CLOUDFLARED_NAME))
            self.assertEqual(set(manifest["files"]), {builder.cp.CLOUDFLARED_NAME})
            self.assertTrue(Path(result["archive"]).is_file())

    def test_ocr_runtime_artifact_removes_common_onnx(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            root = Path(tmp)

            def fake_pyinstaller(feature, location, dependencies):
                folder = location / "dist" / "feature-helper"
                folder.mkdir(parents=True)
                (folder / "feature-helper.exe").write_bytes(b"MZfake")
                (folder / "common.onnx").write_bytes(b"model")
                (folder / "common_old.onnx").write_bytes(b"old-model")
                (folder / "onnxruntime.dll").write_bytes(b"runtime")
                return folder

            with mock.patch.object(builder.importlib.util, "find_spec", return_value=object()), \
                    mock.patch.object(builder, "_pyinstaller_directory", side_effect=fake_pyinstaller), \
                    mock.patch.object(builder.cp, "_helper", return_value={"ok": True}):
                result = builder.build("relogin_ocr_runtime", root)
            folder = root / "relogin_ocr_runtime/dist/feature-helper"
            self.assertFalse((folder / "common.onnx").exists())
            self.assertFalse((folder / "common_old.onnx").exists())
            self.assertTrue((folder / "onnxruntime.dll").is_file())
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["feature"], "relogin_ocr")
            self.assertNotIn("common.onnx", manifest["files"])
            self.assertTrue(Path(result["archive"]).is_file())

    def test_ocr_model_artifact_contains_models_and_charsets(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            beta = source / "common.onnx"
            old = source / "common_old.onnx"
            beta.write_bytes(b"beta")
            old.write_bytes(b"old")
            sources = {"common.onnx": beta, "common_old.onnx": old}
            metadata = {
                "charsets-beta.json": {"charset": ["", "A"], "word": False,
                                       "image": [64, 64], "channel": 1},
                "charsets-old.json": {"charset": ["", "B"], "word": False,
                                      "image": [64, 64], "channel": 1},
            }
            with mock.patch.object(builder, "_model_source_files", return_value=(sources, metadata)):
                result = builder.build("relogin_ocr_model", root)
            folder = root / "relogin_ocr_model/dist/relogin_ocr_model"
            self.assertEqual(set(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()), {
                "models/common.onnx", "models/common_old.onnx",
                "models/charsets-beta.json", "models/charsets-old.json", "manifest.json",
            })
            manifest = json.loads((folder / "manifest.json").read_text())
            self.assertEqual(manifest["role"], "model")
            self.assertEqual(manifest["entry"], "")
            self.assertTrue(Path(result["archive"]).is_file())

    def test_external_ocr_model_is_passed_to_ddddocr(self):
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmp:
            model_root = Path(tmp)
            (model_root / "common.onnx").write_bytes(b"model")
            (model_root / "charsets-beta.json").write_text("{}", encoding="utf-8")
            captured = {}

            class FakeEngine:
                def __init__(self, **kwargs):
                    captured.update(kwargs)

                def classification(self, raw):
                    self.raw = raw
                    return "Ab12"

            fake_ddddocr = mock.Mock(DdddOcr=FakeEngine)
            payload = {"op": "ocr", "image": "data:image/png;base64,WA=="}
            with mock.patch.dict(os.environ, {"CAMPUS_OCR_MODEL_ROOT": str(model_root)}), \
                    mock.patch.dict(sys.modules, {"ddddocr": fake_ddddocr, "onnxruntime": mock.Mock()}):
                result = advanced_helper.run("relogin_ocr",
                                            stream=io.BytesIO(json.dumps(payload).encode()))
            self.assertTrue(result["ok"])
            self.assertEqual(result["code"], "Ab12")
            self.assertEqual(captured["import_onnx_path"], str(model_root / "common.onnx"))
            self.assertEqual(captured["charsets_path"], str(model_root / "charsets-beta.json"))

    def test_external_ocr_model_missing_uses_legacy_classifier(self):
        payload = {"op": "ocr", "image": "data:image/png;base64,WA=="}
        with mock.patch.object(advanced_helper, "_external_model_candidates", return_value=()), \
                mock.patch.dict(sys.modules, {"ddddocr": mock.Mock(), "onnxruntime": mock.Mock()}), \
                mock.patch("infrastructure.advanced_features.classify_captcha", return_value="Cd34") as legacy:
            result = advanced_helper.run("relogin_ocr",
                                        stream=io.BytesIO(json.dumps(payload).encode()))
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "Cd34")
        legacy.assert_called_once_with(payload["image"], frozen=False)


if __name__ == "__main__":
    unittest.main()
