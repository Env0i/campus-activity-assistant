#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_component_domain.py（来源：test_component_rules.py, test_advanced_features.py, test_reason_maps.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_component_rules.py ====================
"""组件读状态等锁规则测试：连续等锁满 30 秒才算「检查超时」。

纯函数测试：不读文件、不读墙钟、不起线程。
"""

import sys
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from domain.component_rules import COMPONENT_CHECK_TIMEOUT_S, check_timed_out  # noqa: E402


class ComponentCheckTimeoutTests(unittest.TestCase):
    """「检查超时」边界：29 秒没到、30 秒整到；非数字按没超时。"""

    def test_boundary_is_thirty_seconds_inclusive(self):
        self.assertFalse(check_timed_out(29))
        self.assertTrue(check_timed_out(30))
        self.assertTrue(check_timed_out(31))

    def test_zero_and_fractional_waits_do_not_time_out(self):
        self.assertFalse(check_timed_out(0))
        self.assertFalse(check_timed_out(29.9))

    def test_non_numeric_wait_counts_as_not_timed_out(self):
        for bad in (None, "", "abc", [], {}):
            with self.subTest(value=repr(bad)):
                self.assertFalse(check_timed_out(bad))

    def test_threshold_is_thirty_seconds(self):
        self.assertEqual(COMPONENT_CHECK_TIMEOUT_S, 30)

# ==================== 源自 test_advanced_features.py ====================
"""高级组件 registry 测试：状态分离、按需安装降级与 OCR 门禁。

全程离线：pip runner 用替身，ddddocr 用假模块，绝不执行真实安装、
不取真实凭据、不加载真实识别模型。

@author Author
"""

import base64
import tempfile
import types
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import advanced_features as af  # noqa: E402
from infrastructure.prefs_store import PrefsLockTimeout  # noqa: E402


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

    def test_outdated_component_is_not_reported_as_failed(self):
        original = af.module_available
        af.module_available = lambda _m: False
        self.addCleanup(lambda: setattr(af, "module_available", original))
        with mock.patch.object(af.component_packages, "feature_status", return_value={
                "available": False, "source": "imported", "error": "component_outdated",
                "version": "0.9.0"}):
            row = af.feature_state(
                {"advanced_features": {"phone_control": True}}, frozen=True)[af.PHONE_CONTROL]
        self.assertEqual(row["status"], "outdated")
        self.assertFalse(row["ready"])
        self.assertTrue(row["installable"], "旧组件要能一键换新")
        self.assertEqual(row["package_version"], "0.9.0")

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


class FeatureStateLockBusyTests(unittest.TestCase):
    """K1：组件事务锁被别的进程占着时，界面状态查询不能冒异常，也不能报成装坏。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
        self.addCleanup(self._tmp.cleanup)
        # 每个用例用独立 root，进程内缓存互不串
        self.root = self._tmp.name

    def _installed(self):
        return {"available": True, "source": "imported", "error": "", "version": "1.2.3"}

    def test_busy_returns_cached_copy_marked_busy(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            first = af.feature_state(prefs, root=self.root, frozen=True)
        self.assertFalse(first[af.PHONE_CONTROL].get("busy"))
        busy = PrefsLockTimeout("组件锁被占用")
        with mock.patch.object(af.component_packages, "feature_status", side_effect=busy):
            second = af.feature_state(prefs, root=self.root, frozen=True)
        row = second[af.PHONE_CONTROL]
        self.assertTrue(row["busy"])
        self.assertTrue(row["available"])
        self.assertTrue(row["ready"])
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["package_version"], "1.2.3")
        self.assertEqual(row["error"], "")

    def test_cached_package_does_not_freeze_user_preferences(self):
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            af.feature_state({}, root=self.root, frozen=True)
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            row = af.feature_state({"advanced_features": {af.PHONE_CONTROL: True}},
                                   root=self.root, frozen=True)[af.PHONE_CONTROL]
        self.assertTrue(row["enabled"], "缓存只存组件状态，启用开关要按本次偏好算")
        self.assertTrue(row["ready"])

    def test_busy_without_cache_reports_checking_not_failed(self):
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            state = af.feature_state({"advanced_features": {af.RELOGIN_OCR: True}},
                                     root=self.root, frozen=True)
        for key in (af.PHONE_CONTROL, af.RELOGIN_OCR):
            row = state[key]
            self.assertEqual(row["status"], "checking")
            self.assertEqual(row["error"], "")
            self.assertTrue(row["busy"])
            self.assertFalse(row["available"])
            self.assertFalse(row["ready"])
            self.assertTrue(row["installable"])


class FeatureStateWaitFieldsTests(unittest.TestCase):
    """等锁要给出「等了多久、是否超时」，读错要退回缓存或检查中——界面据此画「检查超时」。

    时钟用可推进的假单调钟；每个用例独立 root，进程内缓存互不串。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.t = [1000.0]

    def _clock(self):
        return self.t[0]

    def _installed(self):
        return {"available": True, "source": "imported", "error": "", "version": "1.2.3"}

    def test_first_lock_timeout_reports_zero_wait_and_not_timed_out(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
        self.assertEqual(row["lock_wait_s"], 0)
        self.assertFalse(row["check_timed_out"])

    def test_wait_accumulates_across_calls_and_times_out_at_thirty(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
            self.t[0] += 29
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
            self.assertEqual(row["lock_wait_s"], 29)
            self.assertFalse(row["check_timed_out"])
            self.t[0] += 1
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
            self.assertEqual(row["lock_wait_s"], 30)
            self.assertTrue(row["check_timed_out"], "连续等锁满 30 秒要给「检查超时」")

    def test_cached_busy_row_also_carries_the_wait_fields(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            first = af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
        self.assertFalse(first[af.PHONE_CONTROL].get("busy"))
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            # 第一拍记等锁起点（读成功那一拍不算在等），推 10 秒后的下一拍带出时长
            af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
            self.t[0] += 10
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
        self.assertEqual(row["lock_wait_s"], 10)
        self.assertFalse(row["check_timed_out"])
        self.assertTrue(row["busy"])
        self.assertTrue(row["available"])
        self.assertEqual(row["status"], "ready")
        self.assertEqual(row["package_version"], "1.2.3")

    def test_successful_read_resets_the_wait_clock(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
            self.t[0] += 30
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            ok = af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
        self.assertNotIn("lock_wait_s", ok[af.PHONE_CONTROL])
        self.t[0] += 5
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=PrefsLockTimeout("busy")):
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
        self.assertEqual(row["lock_wait_s"], 0)
        self.assertFalse(row["check_timed_out"])

    def test_wait_fields_absent_when_not_waiting(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
        self.assertNotIn("lock_wait_s", row)
        self.assertNotIn("check_timed_out", row)
        self.assertNotIn("read_error", row)

    def test_read_error_with_cache_returns_cache_and_read_error(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
        errors = (OSError("disk gone"),
                  af.component_packages.PackageError("artifact_invalid"),
                  ValueError("junk"))
        for exc in errors:
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(af.component_packages, "feature_status",
                                       side_effect=exc):
                    row = af.feature_state(prefs, root=self.root, frozen=True,
                                           clock=self._clock)[af.PHONE_CONTROL]
                self.assertTrue(row["read_error"])
                self.assertTrue(row["available"], "读错时退回上一次成功的结果")
                self.assertEqual(row["status"], "ready")
                self.assertEqual(row["package_version"], "1.2.3")

    def test_read_error_without_cache_reports_checking_and_read_error(self):
        prefs = {"advanced_features": {af.RELOGIN_OCR: True}}
        errors = (OSError("disk gone"),
                  af.component_packages.PackageError("artifact_invalid"),
                  ValueError("junk"))
        for exc in errors:
            with self.subTest(exc=type(exc).__name__):
                with mock.patch.object(af.component_packages, "feature_status",
                                       side_effect=exc):
                    row = af.feature_state(prefs, root=self.root, frozen=True,
                                           clock=self._clock)[af.RELOGIN_OCR]
                self.assertTrue(row["read_error"])
                self.assertEqual(row["status"], "checking", "不知道状态时说检查中，不说没装")
                self.assertFalse(row["available"])
                self.assertTrue(row["busy"])

    def test_read_error_clears_and_success_drops_read_error(self):
        prefs = {"advanced_features": {af.PHONE_CONTROL: True}}
        with mock.patch.object(af.component_packages, "feature_status",
                               side_effect=OSError("disk gone")):
            af.feature_state(prefs, root=self.root, frozen=True, clock=self._clock)
        with mock.patch.object(af.component_packages, "feature_status",
                               return_value=self._installed()):
            row = af.feature_state(prefs, root=self.root, frozen=True,
                                   clock=self._clock)[af.PHONE_CONTROL]
        self.assertNotIn("read_error", row)

# ==================== 源自 test_reason_maps.py ====================
"""下载失败原因映射的一致性守卫。

local/app.py 的 _DOWNLOAD_FAIL_REASONS（写日志用）与 local/ui/views/phone.js 的
PHONE_DOWNLOAD_REASON（手机页高级功能区用）注释说同源，两边只要有一边多了或少了
error_code，用户在日志和界面里就会看到不同的原因说法，甚至一边回落后端原话。
这里只读源码、用正则抽键，不 import app（它会拉起一堆运行时依赖）。
"""
import re

LOCAL = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import module_group_raw_src  # noqa: E402

# 手机面板搬成模块后的装配文件（模块入口）：读源码改读这组模块的原文拼接
PANEL_ENTRY = "features/phone-access/actions-panel.js"


def _keys(source: str, anchor: str, quoted: bool) -> set:
    """取 anchor 之后第一个 {...} 块里的键。"""
    start = source.index(anchor)
    block = source[source.index("{", start):]
    block = block[:block.index("}")]
    pattern = r'"(\w+)"\s*:' if quoted else r'^\s*(\w+)\s*:'
    return set(re.findall(pattern, block, re.M))


class DownloadReasonMapTests(unittest.TestCase):
    def test_python_and_js_reason_maps_share_keys(self):
        py = (LOCAL / "app.py").read_text(encoding="utf-8")
        js = module_group_raw_src(PANEL_ENTRY)
        py_keys = _keys(py, "_DOWNLOAD_FAIL_REASONS = {", True)
        js_keys = _keys(js, "const PHONE_DOWNLOAD_REASON = {", False)
        self.assertTrue(py_keys, "没抽到 app.py 的键，正则需要跟着源码改")
        self.assertEqual(py_keys, js_keys)

    def test_not_published_reason_is_in_both_maps(self):
        """I3：发布页上没有组件资产时，日志与手机页都要有「未发布」原因，不能回落到网络类文案。"""
        py = (LOCAL / "app.py").read_text(encoding="utf-8")
        js = module_group_raw_src(PANEL_ENTRY)
        self.assertIn("not_published", _keys(py, "_DOWNLOAD_FAIL_REASONS = {", True))
        self.assertIn("not_published", _keys(js, "const PHONE_DOWNLOAD_REASON = {", False))

if __name__ == "__main__":
    unittest.main()
