#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""高级组件 registry 测试：状态分离、按需安装降级与 OCR 门禁。

全程离线：pip runner 用替身，ddddocr 用假模块，绝不执行真实安装、
不取真实凭据、不加载真实识别模型。

@author Author
"""
from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import advanced_features as af  # noqa: E402


PNG_URI = "data:image/png;base64," + base64.b64encode(b"\x89PNG-fake").decode("ascii")


class FakeCompleted:
    def __init__(self, returncode=0):
        self.returncode = returncode


class RecordingRunner:
    """记录 pip 调用的替身；可配置返回码或直接抛错。"""

    def __init__(self, returncode=0, raises=None):
        self.calls = []
        self.returncode = returncode
        self.raises = raises

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), dict(kwargs)))
        if self.raises is not None:
            raise self.raises
        return FakeCompleted(self.returncode)


class FakeOcr:
    """假 ddddocr：固定识别结果或抛错，不碰真实模型。"""

    result = "Ab12"
    raises = False

    def __init__(self, show_ad=False, beta=False):
        pass

    def classification(self, _raw):
        if FakeOcr.raises:
            raise RuntimeError("engine broken")
        return FakeOcr.result


def install_fake_ddddocr(test: unittest.TestCase) -> None:
    fake = types.ModuleType("ddddocr")
    fake.DdddOcr = FakeOcr
    sys.modules["ddddocr"] = fake
    test.addCleanup(lambda: sys.modules.pop("ddddocr", None))
    af.__dict__.pop("ddddocr", None)


class RegistryContractTests(unittest.TestCase):
    """固定 registry：只认两个组件，用户输入永远成不了包名。"""

    def test_registry_has_exactly_two_fixed_components(self):
        self.assertEqual(set(af.FEATURES), {af.PHONE_CONTROL, af.RELOGIN_OCR})
        self.assertEqual(af.FEATURES[af.PHONE_CONTROL].package, "segno")
        self.assertEqual(af.FEATURES[af.RELOGIN_OCR].package, "ddddocr")
        self.assertTrue(af.allowed_feature(af.PHONE_CONTROL))
        self.assertFalse(af.allowed_feature("segno"))
        self.assertFalse(af.allowed_feature("os"))
        self.assertFalse(af.allowed_feature(""))

    def test_unknown_key_is_rejected_before_any_pip_call(self):
        runner = RecordingRunner()
        for key in ("segno; rm -rf /", "../evil", "RELOGIN_OCR", "relogin_ocr ", ""):
            with self.subTest(key=key):
                result = af.install_feature(key, runner=runner)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"], "unknown_feature")
        self.assertEqual(runner.calls, [], "未知 key 不得触发任何 pip 调用")

    def test_pip_command_uses_fixed_package_not_user_input(self):
        original = af.module_available
        af.module_available = lambda _m: False   # 与本机是否装过 segno 无关
        self.addCleanup(lambda: setattr(af, "module_available", original))
        runner = RecordingRunner(returncode=1)
        af.install_feature(af.PHONE_CONTROL, runner=runner)
        self.assertEqual(len(runner.calls), 1)
        args = runner.calls[0][0]
        self.assertEqual(args[1:], ["-m", "pip", "install", "segno"])
        self.assertEqual(runner.calls[0][1].get("timeout"), 300)


class FeatureStateTests(unittest.TestCase):
    """enabled / available / ready / installable 四态必须互相独立。"""

    def _state(self, prefs, *, available, frozen=False):
        original = af.module_available
        af.module_available = lambda _m: available
        self.addCleanup(lambda: setattr(af, "module_available", original))
        with mock.patch.object(af.component_packages, "feature_status", return_value={
                "available": available, "source": "imported", "error": ""}):
            return af.feature_state(prefs, frozen=frozen)

    def test_states_are_separated(self):
        cases = [
            ({"advanced_features": {"phone_control": True}}, True, False,
             {"enabled": True, "available": True, "ready": True, "installable": True}),
            ({"advanced_features": {"phone_control": True}}, False, False,
             {"enabled": True, "available": False, "ready": False, "installable": True}),
            ({"advanced_features": {"phone_control": False}}, True, False,
             {"enabled": False, "available": True, "ready": False, "installable": True}),
            ({}, False, False,
             {"enabled": False, "available": False, "ready": False, "installable": True}),
            ({"advanced_features": {"phone_control": True}}, True, True,
             {"enabled": True, "available": True, "ready": True, "installable": True}),
        ]
        for prefs, available, frozen, expect in cases:
            with self.subTest(prefs=prefs, available=available, frozen=frozen):
                state = self._state(prefs, available=available, frozen=frozen)
                row = state[af.PHONE_CONTROL]
                for key, value in expect.items():
                    self.assertEqual(row[key], value, key)
                # 两个组件互不影响：phone_control 的偏好不带动 relogin_ocr
                self.assertFalse(state[af.RELOGIN_OCR]["enabled"])

    def test_feature_ready_follows_enabled_and_available(self):
        original = af.module_available
        af.module_available = lambda _m: True
        self.addCleanup(lambda: setattr(af, "module_available", original))
        self.assertTrue(af.feature_ready(
            {"advanced_features": {"relogin_ocr": True}}, af.RELOGIN_OCR))
        self.assertFalse(af.feature_ready(
            {"advanced_features": {"relogin_ocr": False}}, af.RELOGIN_OCR))
        self.assertFalse(af.feature_ready({}, af.RELOGIN_OCR))

    def test_state_payload_has_no_paths_or_secrets(self):
        state = self._state({}, available=True)
        for row in state.values():
            self.assertNotIn("path", row)
            self.assertNotIn("exe", row)
            self.assertEqual(
                set(row), {"key", "title", "description", "enabled",
                           "available", "ready", "installable", "package", "source",
                           "package_version", "error", "status", "install_mode"})


class InstallBehaviourTests(unittest.TestCase):
    """按需安装：pip 失败、模块缺失、冻结版与已安装启用都要有可操作结论。"""

    def setUp(self):
        self._original = af.module_available
        self.available = False
        af.module_available = lambda _m: self.available
        self.addCleanup(lambda: setattr(af, "module_available", self._original))

    def test_pip_failure_is_reported_without_success(self):
        runner = RecordingRunner(returncode=1)
        result = af.install_feature(af.RELOGIN_OCR, runner=runner)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "install_failed")
        self.assertIn("安装失败", result["text"])

    def test_runner_exception_is_reported_as_install_failure(self):
        runner = RecordingRunner(raises=OSError("net down"))
        result = af.install_feature(af.PHONE_CONTROL, runner=runner)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "install_failed")
        self.assertIn("OSError", result["text"])

    def test_module_missing_after_pip_success_is_not_marked_installed(self):
        runner = RecordingRunner(returncode=0)
        result = af.install_feature(af.RELOGIN_OCR, runner=runner)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "install_unavailable")
        self.assertIn("重启", result["text"])

    def test_success_when_module_becomes_available(self):
        runner = RecordingRunner(returncode=0)

        def fake_available(module):
            return bool(runner.calls)

        af.module_available = fake_available
        result = af.install_feature(af.RELOGIN_OCR, runner=runner)
        self.assertTrue(result["ok"])
        self.assertEqual(result["feature"], af.RELOGIN_OCR)

    def test_already_available_enables_without_pip(self):
        self.available = True
        runner = RecordingRunner(returncode=1)
        result = af.install_feature(af.RELOGIN_OCR, runner=runner)
        self.assertTrue(result["ok"], "已安装组件走启用路径，不该再动 pip")
        self.assertEqual(runner.calls, [])
        self.assertIn("启用", result["text"])

    def test_frozen_without_module_requires_offline_installer(self):
        self.available = False
        runner = RecordingRunner()
        result = af.install_feature(af.PHONE_CONTROL, frozen=True, runner=runner)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "package_required")
        self.assertEqual(runner.calls, [], "冻结版不得直接改环境")

    def test_frozen_ignores_bundled_module_and_uses_actual_root(self):
        self.available = True
        runner = RecordingRunner()
        result = af.install_feature(af.PHONE_CONTROL, frozen=True, runner=runner)
        self.assertFalse(result["ok"])
        self.assertEqual(runner.calls, [])
        with mock.patch.object(af.component_packages, "feature_status", return_value={
                "available": True, "source": "imported", "error": ""}) as status:
            self.assertTrue(af.feature_ready({"advanced_features": {af.PHONE_CONTROL: True}},
                                             af.PHONE_CONTROL, frozen=True, root="isolated"))
            status.assert_any_call(af.PHONE_CONTROL, root="isolated")
        with mock.patch.object(af.component_packages, "install", return_value={"ok": True}) as install:
            self.assertTrue(af.install_feature(af.PHONE_CONTROL, frozen=True,
                            archive="trusted.zip", root="isolated")["ok"])
            install.assert_called_once_with("trusted.zip", af.PHONE_CONTROL, root="isolated")

    def test_frozen_ocr_only_sends_image_and_rejects_bad_result(self):
        with mock.patch.object(af.component_packages, "invoke", return_value={"code": "Ab12"}) as invoke:
            self.assertEqual(af.classify_captcha(PNG_URI, frozen=True, root="isolated"), "Ab12")
            invoke.assert_called_once_with(af.RELOGIN_OCR, {"op": "ocr", "image": PNG_URI}, root="isolated")
            invoke.return_value = {"code": "bad value"}
            self.assertEqual(af.classify_captcha(PNG_URI, frozen=True, root="isolated"), "")


class FrozenPackageStateTests(unittest.TestCase):
    """冻结包里「没装」和「装坏」必须分开：空数据根是 missing，不是 failed。"""

    def test_empty_data_root_reports_both_features_as_missing(self):
        """缺陷 1：全新未安装时两个功能都要给「下载并安装」，不能显示加载失败。"""
        with tempfile.TemporaryDirectory(dir=tempfile.gettempdir()) as temporary:
            with mock.patch.object(af.component_packages, "supported", return_value=True):
                state = af.feature_state({}, root=Path(temporary), frozen=True)
            for key in (af.PHONE_CONTROL, af.RELOGIN_OCR):
                with self.subTest(feature=key):
                    row = state[key]
                    self.assertFalse(row["available"])
                    self.assertEqual(row["error"], "")
                    self.assertEqual(row["status"], "missing")
                    self.assertTrue(row["installable"])


class CaptchaGateTests(unittest.TestCase):
    """ddddocr 是可选件：缺组件、坏图、坏结果都必须回退人工输入。"""

    def tearDown(self):
        FakeOcr.result = "Ab12"
        FakeOcr.raises = False

    def test_missing_ddddocr_returns_empty(self):
        # sys.modules 置 None 时 import 必抛 ImportError，与本机是否装过无关
        sys.modules["ddddocr"] = None
        self.addCleanup(lambda: sys.modules.pop("ddddocr", None))
        self.assertEqual(af.classify_captcha(PNG_URI), "")

    def test_bad_payloads_return_empty_without_engine(self):
        install_fake_ddddocr(self)
        for payload in ("", "data:image/jpeg;base64,AAAA", "not-a-uri",
                        PNG_URI[:-4] + "!!!!", "data:image/png;base64,"):
            with self.subTest(payload=payload[:30]):
                self.assertEqual(af.classify_captcha(payload), "")

    def test_engine_result_must_be_four_ascii_alnum(self):
        install_fake_ddddocr(self)
        for bad in ("12", "12345", "ab!d", "ＡＢ１２", "12 4", "    "):
            FakeOcr.result = bad
            with self.subTest(result=bad):
                self.assertEqual(af.classify_captcha(PNG_URI), "")
        FakeOcr.result = "Ab12"
        self.assertEqual(af.classify_captcha(PNG_URI), "Ab12")

    def test_engine_failure_falls_back_to_manual(self):
        install_fake_ddddocr(self)
        FakeOcr.raises = True
        self.assertEqual(af.classify_captcha(PNG_URI), "")

    def test_base_startup_never_imports_ddddocr(self):
        sys.modules.pop("ddddocr", None)
        af.feature_state({})
        af.feature_ready({}, af.RELOGIN_OCR)
        runner = RecordingRunner(returncode=1)
        af.install_feature(af.PHONE_CONTROL, runner=runner)
        self.assertNotIn("ddddocr", sys.modules,
                         "基础探测与安装路径都不得顺手导入 ddddocr")


if __name__ == "__main__":
    unittest.main()
