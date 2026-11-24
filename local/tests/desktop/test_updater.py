#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_updater.py（来源：test_update_check.py, test_update_delta.py, test_update_launcher.py, test_update_service.py, test_updater.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_update_check.py ====================
"""手动更新纯逻辑与桥接契约；所有HTTP均为替身，不访问学校或GitHub。

@author Author
"""
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

LOCAL = Path(__file__).resolve().parents[2]
TESTS_DIR = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
from infrastructure.update import update_check as updates
try:
    import app as local_app
except Exception:
    class _DummyApp:
        version_switch_available = staticmethod(lambda *a, **kw: False)
    local_app = _DummyApp()
from fixtures.business_clock import TestWallClock  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402

INSTALLER = "campus-activity-watch-installer-v1.1.1-win-x64.exe"
DOWNLOAD = "https://github.com/Env0i/campus-activity-assistant/releases/download/v1.1.1/"


def release(tag="v1.1.0", **extra):
    return {"tag_name": tag, "draft": False, "prerelease": False, **extra}


def asset(name, url=None, size=1024):
    return {"name": name,
            "browser_download_url": url or (DOWNLOAD + name),
            "size": size}


def manifest(version="1.1.1", name=INSTALLER, sha256="ab" * 32, size=1024, files=None):
    return {"version": version, "tag": "v" + version, "branch": "main",
            "commit": "0" * 40, "commit_short": "0" * 7, "source_dirty": False,
            "built_at": "2026-10-28T00:00:00",
            "files": files if files is not None else {name: {"sha256": sha256, "bytes": size}}}


def stable(tag="v1.1.1", installer=True, manifest_name="manifest.json", size=1024, assets_extra=None):
    """一份“有安装器 + 有清单”的正式 Release 资产集合；assets_extra 用于追加组件资产。"""
    assets = [asset("campus-activity-watch-v1.1.1-win-x64.zip"),
              asset("campus-activity-watch-v1.1.1-win-x64.exe")]
    if installer:
        assets.append(asset(INSTALLER, size=size))
    if manifest_name:
        assets.append(asset(manifest_name))
    if assets_extra:
        assets.extend(assets_extra)
    return release(tag, assets=assets)


class ReleaseComparisonTests(unittest.TestCase):
    def test_numeric_comparison(self):
        self.assertEqual(updates.evaluate_latest_release("1.9.9", release("v1.10.0"))["state"], "available")

    def test_same_version(self):
        self.assertEqual(updates.evaluate_latest_release("1.1.0", release())["state"], "current")

    def test_preview_never_suggests_downgrade(self):
        result = updates.evaluate_latest_release("1.1.0", release("v1.0.2"))
        self.assertEqual(result["state"], "preview")
        self.assertIn("预览", result["text"])

    def test_v_prefix_and_fixed_public_url(self):
        result = updates.evaluate_latest_release("1.0.0", release("1.1.0", html_url="https://invalid.example"))
        self.assertEqual(result["latest_version"], "1.1.0")
        self.assertEqual(result["url"], updates.LATEST_URL)

    def test_result_shape_carries_no_installer_by_default(self):
        self.assertIsNone(updates.evaluate_latest_release("1.1.0", release())["installer"])

    def test_invalid_versions_and_payloads(self):
        for tag in (None, "1.1", "1.1.0-beta", "v01.1.0", "anything", "1.2.3.4", "9" * 100):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                updates.evaluate_latest_release("1.1.0", release(tag))
        for payload in ([], None, {}, release(draft=True), release(prerelease=True)):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                updates.evaluate_latest_release("1.1.0", payload)


class InstallerAssetTests(unittest.TestCase):
    def test_installer_asset_name(self):
        self.assertEqual(updates.installer_asset_name("1.1.1"), INSTALLER)
        with self.assertRaises(ValueError):
            updates.installer_asset_name("1.1.1-beta")

    def test_release_asset_url_gate(self):
        good = DOWNLOAD + INSTALLER
        self.assertTrue(updates.is_release_asset_url(good, INSTALLER))
        self.assertTrue(updates.is_release_asset_url(good + "?download=1", INSTALLER))
        for bad in ("http://github.com/Env0i/campus-activity-assistant/releases/download/v1.1.1/" + INSTALLER,
                    "https://evil.example/releases/download/v1.1.1/" + INSTALLER,
                    "https://github.com/other/repo/releases/download/v1.1.1/" + INSTALLER,
                    "https://github.com/Env0i/campus-activity-assistant/archive/refs/tags/v1.1.1.zip",
                    good.replace(INSTALLER, "other.exe"),
                    "", None, 7):
            with self.subTest(url=bad):
                self.assertFalse(updates.is_release_asset_url(bad, INSTALLER))

    def test_select_release_assets_picks_installer_and_manifest(self):
        picked = updates.select_release_assets(stable(), "1.1.1")
        self.assertEqual(picked["installer"]["name"], INSTALLER)
        self.assertEqual(picked["installer"]["url"], DOWNLOAD + INSTALLER)
        self.assertEqual(picked["installer"]["bytes"], 1024)
        self.assertEqual(picked["manifest_url"], DOWNLOAD + "manifest.json")

    def test_select_release_assets_skips_foreign_and_oversize(self):
        # 非本仓库地址、超大安装器、别名资产都不得被选中
        payload = release("v1.1.1", assets=[
            asset(INSTALLER, url="https://evil.example/" + INSTALLER),
            asset(INSTALLER, size=updates.MAX_INSTALLER_BYTES + 1),
            asset("campus-activity-watch-installer-v1.1.1-win-x64.zip"),
            asset("manifest.json", url="http://github.com/x/manifest.json"),
        ])
        picked = updates.select_release_assets(payload, "1.1.1")
        self.assertIsNone(picked["installer"])
        self.assertEqual(picked["manifest_url"], "")

    def test_select_release_assets_without_assets_key(self):
        # 两个组件包字段都在：空资产时每个键齐全且都为「没有」
        self.assertEqual(updates.select_release_assets(release(), "1.1.1"),
                         {"installer": None, "manifest_url": "", "phone_control": None,
                          "relogin_ocr": None})

    def test_parse_manifest_extracts_entry(self):
        raw = json.dumps(manifest()).encode("utf-8")
        entry = updates.parse_manifest(raw, "1.1.1", INSTALLER)
        self.assertEqual(entry["sha256"], "ab" * 32)
        self.assertEqual(entry["bytes"], 1024)

    def test_parse_manifest_rejects_bad_shapes(self):
        cases = [
            b"not json", b"[]", b"\xff",
            json.dumps(manifest(version="1.1.0")).encode(),          # 版本不匹配
            json.dumps(manifest(files={})).encode(),                 # 缺安装器条目
            json.dumps(manifest(files={INSTALLER: {"sha256": "zz", "bytes": 1}})).encode(),
            json.dumps(manifest(files={INSTALLER: {"sha256": "ab" * 32, "bytes": 0}})).encode(),
            json.dumps(manifest(files={INSTALLER: {"sha256": "ab" * 32,
                                                   "bytes": updates.MAX_INSTALLER_BYTES + 1}})).encode(),
            json.dumps(manifest(files="nope")).encode(),
        ]
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                updates.parse_manifest(raw, "1.1.1", INSTALLER)


COMPONENT = "campus-activity-watch-phone-control-v1.1.1-win-x64.zip"


def component_manifest(version="1.1.1", name=COMPONENT, sha256="cd" * 32, size=2048, files=None):
    return manifest(version=version, files=files if files is not None else
                    {name: {"sha256": sha256, "bytes": size}})


class PhoneControlAssetTests(unittest.TestCase):
    """手机控制组件是独立 Release 资产：命名固定、地址限定本仓库、清单必须对得上。"""

    def test_phone_control_asset_name_is_stable(self):
        self.assertEqual(
            updates.phone_control_asset_name("1.2.3"),
            "campus-activity-watch-phone-control-v1.2.3-win-x64.zip",
        )
        with self.assertRaises(ValueError):
            updates.phone_control_asset_name("1.2.3-beta")

    def test_release_selection_rejects_phone_asset_outside_repository(self):
        payload = {"assets": [{
            "name": "campus-activity-watch-phone-control-v1.2.3-win-x64.zip",
            "browser_download_url": "https://example.com/component.zip",
            "size": 10,
        }]}
        picked = updates.select_release_assets(payload, "1.2.3")
        self.assertIsNone(picked["phone_control"])

    def test_selection_picks_component_with_repo_url_and_bounded_size(self):
        payload = stable("v1.1.1", assets_extra=[asset(COMPONENT, size=2048)])
        picked = updates.select_release_assets(payload, "1.1.1")
        self.assertEqual(picked["phone_control"]["name"], COMPONENT)
        self.assertEqual(picked["phone_control"]["url"], DOWNLOAD + COMPONENT)
        self.assertEqual(picked["phone_control"]["bytes"], 2048)
        # 安装器与组件的选择互不影响
        self.assertEqual(picked["installer"]["name"], INSTALLER)

    def test_component_selection_skips_oversize_and_alias(self):
        payload = release("v1.1.1", assets=[
            asset(COMPONENT, size=updates.MAX_INSTALLER_BYTES + 1),
            asset("campus-activity-watch-phone-control-v1.1.1-win-x86.zip"),
        ])
        self.assertIsNone(updates.select_release_assets(payload, "1.1.1")["phone_control"])

    def test_ocr_component_asset_name_follows_same_rule(self):
        self.assertEqual(
            updates.component_asset_name("relogin_ocr", "1.2.3"),
            "campus-activity-watch-relogin-ocr-v1.2.3-win-x64.zip",
        )
        with self.assertRaises(ValueError):
            updates.component_asset_name("segno", "1.2.3")

    def test_split_artifact_asset_names_and_group_resolution(self):
        version = "1.1.1"
        runtime = updates.artifact_asset_name("relogin_ocr_runtime", version)
        model = updates.artifact_asset_name("relogin_ocr_model", version)
        self.assertTrue(runtime.endswith("relogin-ocr-runtime-v1.1.1-win-x64.zip"))
        self.assertTrue(model.endswith("relogin-ocr-model-v1.1.1-win-x64.zip"))
        data = manifest(version=version, files={
            runtime: {"sha256": "aa" * 32, "bytes": 1024},
            model: {"sha256": "bb" * 32, "bytes": 2048},
        })
        data["split_assets"] = {
            "relogin_ocr_runtime": {"name": runtime, "target_version": version,
                                    "compatibility_id": "campus-activity-1", "content_sha256": "cc" * 32},
            "relogin_ocr_model": {"name": model, "target_version": version,
                                  "compatibility_id": "campus-activity-1", "content_sha256": "dd" * 32},
        }
        payload = updates.payload_from_manifest(json.dumps(data).encode())
        resolved = updates.resolve_component_assets(
            payload, version, json.dumps(data).encode(), "relogin_ocr")
        self.assertEqual(resolved["state"], "available")
        self.assertEqual([item["artifact_id"] for item in resolved["assets"]],
                         ["relogin_ocr_runtime", "relogin_ocr_model"])
        self.assertEqual(resolved["assets"][1]["content_sha256"], "dd" * 32)
        for bad in ("bad-hash", ["not-a-hash"]):
            data["split_assets"]["relogin_ocr_model"]["content_sha256"] = bad
            checked = updates.resolve_component_assets(payload, version, json.dumps(data).encode(), "relogin_ocr")
            self.assertEqual(checked["state"], "legacy")

    def test_ocr_component_is_selected_and_resolved_separately(self):
        ocr = "campus-activity-watch-relogin-ocr-v1.1.1-win-x64.zip"
        payload = stable("v1.1.1", assets_extra=[asset(COMPONENT, size=2048), asset(ocr, size=4096)])
        picked = updates.select_release_assets(payload, "1.1.1")
        self.assertEqual(picked["relogin_ocr"]["name"], ocr)
        self.assertEqual(picked["phone_control"]["name"], COMPONENT, "两个组件互不影响")
        raw = json.dumps(manifest(version="1.1.1", files={
            COMPONENT: {"sha256": "cd" * 32, "bytes": 2048},
            ocr: {"sha256": "ef" * 32, "bytes": 4096}})).encode("utf-8")
        resolved = updates.resolve_component_asset(payload, "1.1.1", raw, "relogin_ocr")
        self.assertEqual(resolved["state"], "available")
        self.assertEqual(resolved["asset"]["sha256"], "ef" * 32)
        missing = updates.resolve_component_asset(
            stable("v1.1.1", assets_extra=[asset(COMPONENT, size=2048)]), "1.1.1", raw, "relogin_ocr")
        self.assertEqual(missing["state"], "no_component")
        self.assertIn("验证码识别", missing["text"])

    def test_resolve_component_asset_returns_verified_entry(self):
        payload = stable("v1.1.1", assets_extra=[asset(COMPONENT, size=2048)])
        resolved = updates.resolve_phone_control_asset(
            payload, "1.1.1", json.dumps(component_manifest()).encode("utf-8"))
        self.assertEqual(resolved["state"], "available")
        self.assertEqual(resolved["asset"]["sha256"], "cd" * 32)
        self.assertEqual(resolved["asset"]["bytes"], 2048)

    def test_resolve_component_asset_reports_no_component(self):
        resolved = updates.resolve_phone_control_asset(
            stable("v1.1.1"), "1.1.1", json.dumps(component_manifest()).encode("utf-8"))
        self.assertEqual(resolved["state"], "no_component")
        self.assertEqual(resolved["error_code"], "no_component")
        self.assertIsNone(resolved["asset"])

    def test_resolve_component_asset_rejects_bad_manifest(self):
        payload = stable("v1.1.1", assets_extra=[asset(COMPONENT, size=2048)])
        cases = [
            b"not json",
            json.dumps(component_manifest(version="1.1.0")).encode(),     # 版本不符
            json.dumps(component_manifest(files={})).encode(),            # 缺组件条目
            json.dumps(component_manifest(size=4096)).encode(),           # 大小与资产不符
            json.dumps(component_manifest(files={COMPONENT: {"sha256": "zz", "bytes": 2048}})).encode(),
        ]
        for raw in cases:
            with self.subTest(size=len(raw)):
                resolved = updates.resolve_phone_control_asset(payload, "1.1.1", raw)
                self.assertEqual(resolved["state"], "manifest_invalid")
                self.assertEqual(resolved["error_code"], "manifest_invalid")

    def test_resolve_component_asset_requires_manifest_url(self):
        payload = release("v1.1.1", assets=[asset(COMPONENT, size=2048)])
        resolved = updates.resolve_phone_control_asset(
            payload, "1.1.1", json.dumps(component_manifest()).encode("utf-8"))
        self.assertEqual(resolved["state"], "manifest_invalid")


class UpdateNetworkTests(unittest.TestCase):
    def response(self, body):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = body
        return response

    def run_check(self, bodies, current="1.1.0", error=None):
        """用替身响应跑一次 check_latest_release；bodies 按 GET 顺序供给。"""
        queue = list(bodies)

        def fake_open(*args, **kwargs):
            if error is not None:
                raise error
            return self.response(queue.pop(0) if queue else b"")
        with patch.object(updates, "urlopen", side_effect=fake_open) as fetch:
            result = updates.check_latest_release(current)
        return result, fetch

    def test_one_request_fixed_endpoint_and_bounded_read(self):
        response = self.response(json.dumps(manifest(version="1.1.0")).encode())
        with patch.object(updates, "urlopen", return_value=response) as fetch:
            result = updates.check_latest_release("1.1.0")
        fetch.assert_called_once()
        request = fetch.call_args.args[0]
        self.assertEqual(request.full_url, updates.LATEST_MANIFEST_URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(fetch.call_args.kwargs["timeout"], 8)
        self.assertNotIn("Authorization", request.headers)
        response.read.assert_called_once_with(updates.MAX_MANIFEST_BYTES + 1)
        self.assertEqual(result["state"], "current")

    def test_available_with_installer_carries_bytes_and_sha256(self):
        # 清单只取一次：检查更新拿到后直接复用，不再请求 api.github.com
        result, fetch = self.run_check([json.dumps(manifest()).encode()])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["latest_version"], "1.1.1")
        self.assertEqual(result["installer"]["name"], INSTALLER)
        self.assertEqual(result["installer"]["url"], DOWNLOAD + INSTALLER)
        self.assertEqual(result["installer"]["bytes"], 1024)
        self.assertEqual(result["installer"]["sha256"], "ab" * 32)

    def test_available_with_payload_and_delta_metadata(self):
        target_files = [{"path": "campus-activity-watch.exe", "bytes": 3,
                         "sha256": "aa" * 32}]
        canonical = json.dumps({"version": "1.1.1", "files": target_files},
                               ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        target = {"version": "1.1.1", "files": target_files,
                  "target_manifest_sha256": hashlib.sha256(canonical).hexdigest()}
        payload_name = "campus-activity-watch-payload-v1.1.1-win-x64.zip"
        delta_name = "campus-activity-watch-delta-v1.1.0-to-v1.1.1-win-x64.zip"
        files = {
            INSTALLER: {"sha256": "ab" * 32, "bytes": 1024},
            payload_name: {"sha256": "cd" * 32, "bytes": 2048},
            delta_name: {"sha256": "ef" * 32, "bytes": 512},
        }
        data = manifest(files=files)
        data["full_payload"] = {
            "name": payload_name, "bytes": 2048, "sha256": "cd" * 32,
            "target_version": "1.1.1", "target_manifest": target,
            "target_manifest_sha256": target["target_manifest_sha256"],
        }
        data["deltas"] = [{
            "name": delta_name, "bytes": 512, "sha256": "ef" * 32,
            "base_version": "1.1.0", "target_version": "1.1.1",
            "target_manifest": target,
            "target_manifest_sha256": target["target_manifest_sha256"],
        }]
        result, _ = self.run_check([json.dumps(data).encode()])
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["installer"]["full"]["name"], payload_name)
        self.assertEqual(result["installer"]["full"]["target_manifest"], target)
        self.assertEqual(result["installer"]["deltas"][0]["base_version"], "1.1.0")
        self.assertEqual(result["installer"]["deltas"][0]["sha256"], "ef" * 32)
        data["target_manifest"] = target
        data["target_manifest_sha256"] = target["target_manifest_sha256"]
        del data["full_payload"]["target_manifest"]
        del data["deltas"][0]["target_manifest"]
        result, _ = self.run_check([json.dumps(data).encode()])
        self.assertEqual(result["installer"]["full"]["target_manifest"], target)
        self.assertEqual(result["installer"]["deltas"][0]["target_manifest"], target)
        for field, bad in (("target_manifest_sha256", "00" * 32), ("bytes", 1),
                           ("sha256", "00" * 32)):
            with self.subTest(field=field):
                original = data["full_payload"][field]
                data["full_payload"][field] = bad
                result, _ = self.run_check([json.dumps(data).encode()])
                self.assertNotIn("full", result["installer"])
                data["full_payload"][field] = original
        data["target_manifest"]["files"][0]["path"] = "../bad"
        result, _ = self.run_check([json.dumps(data).encode()])
        self.assertNotIn("full", result["installer"])
        self.assertNotIn("deltas", result["installer"])

    def test_bad_payload_metadata_keeps_verified_installer_fallback(self):
        payload_name = "campus-activity-watch-payload-v1.1.1-win-x64.zip"
        data = manifest(files={
            INSTALLER: {"sha256": "ab" * 32, "bytes": 1024},
            payload_name: {"sha256": "cd" * 32, "bytes": 2048},
        })
        data["full_payload"] = {
            "name": payload_name, "bytes": 2048, "sha256": "cd" * 32,
            "target_version": "1.1.1",
            "target_manifest": {"version": "1.1.1", "files": []},
        }
        result, _ = self.run_check([json.dumps(data).encode()])
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["installer"]["name"], INSTALLER)
        self.assertNotIn("full", result["installer"])

    def test_no_installer_asset_returns_release_page_state(self):
        result, fetch = self.run_check([json.dumps(manifest(files={COMPONENT: {
            "sha256": "cd" * 32, "bytes": 2048}})).encode()])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(result["state"], "no_installer")
        self.assertEqual(result["error_code"], "no_installer")
        self.assertIsNone(result["installer"])
        self.assertIn("下载页", result["text"])

    def test_payload_from_manifest_rejects_version_mismatch(self):
        raw = json.dumps(manifest(version="1.1.0")).encode()
        with self.assertRaises(ValueError):
            updates.payload_from_manifest(raw, "1.1.1")

    def test_payload_from_manifest_rejects_missing_or_wrong_tag(self):
        # 标签是必填：不能靠默认值补出 v<版本>，否则没写 tag 的清单也会被当成对得上
        for bad in (None, "", "v1.1.0", 111):
            data = manifest()
            if bad is None:
                data.pop("tag")
            else:
                data["tag"] = bad
            with self.subTest(tag=bad), self.assertRaises(ValueError):
                updates.payload_from_manifest(json.dumps(data).encode())

    def test_manifest_bytes_mismatch_is_not_downloadable(self):
        # payload 由清单自身生成时大小天然一致；_attach_installer 仍守住这道防御
        payload = stable(size=2048)
        result = updates.evaluate_latest_release("1.1.0", payload)
        attached = updates._attach_installer(
            result, payload, raw_manifest=json.dumps(manifest(size=1024)).encode())
        self.assertEqual(attached["state"], "no_installer")
        self.assertEqual(attached["error_code"], "manifest_invalid")

    def test_invalid_manifest_returns_invalid_response(self):
        for raw in (b"not json", b"[]",
                    json.dumps(manifest(files={})).encode(),
                    json.dumps(manifest(files={INSTALLER: {"sha256": "zz", "bytes": 1}})).encode()):
            with self.subTest(size=len(raw)):
                result, _ = self.run_check([raw])
                self.assertEqual(result["state"], "error")
                self.assertEqual(result["error_code"], "invalid_response")

    def test_payload_from_manifest_builds_release_download_urls(self):
        payload = updates.payload_from_manifest(json.dumps(manifest()).encode())
        urls = {item["name"]: item["browser_download_url"] for item in payload["assets"]}
        self.assertEqual(urls[INSTALLER], DOWNLOAD + INSTALLER)
        self.assertEqual(urls["manifest.json"], updates.tag_manifest_url("1.1.1"))
        self.assertEqual(payload["tag_name"], "v1.1.1")
        self.assertIs(payload["draft"], False)
        self.assertIs(payload["prerelease"], False)

    def test_tag_manifest_url_rejects_bad_version(self):
        for version in ("1.1.1-beta", "v01.1.0", "", None):
            with self.subTest(version=version), self.assertRaises(ValueError):
                updates.tag_manifest_url(version)

    def test_oversized_manifest_rejected(self):
        result, _ = self.run_check([b"x" * (updates.MAX_MANIFEST_BYTES + 1)])
        self.assertEqual(result["state"], "error")
        self.assertEqual(result["error_code"], "invalid_response")

    def test_no_release(self):
        result, _ = self.run_check([], error=HTTPError(updates.LATEST_MANIFEST_URL, 404, "", {}, io.BytesIO()))
        self.assertEqual(result["state"], "unavailable")

    def test_rate_limit(self):
        for code in (403, 429):
            result, _ = self.run_check([], error=HTTPError(updates.LATEST_MANIFEST_URL, code, "", {}, io.BytesIO()))
            self.assertEqual(result["error_code"], "rate_limited")

    def test_other_http_error(self):
        result, _ = self.run_check([], error=HTTPError(updates.LATEST_MANIFEST_URL, 500, "", {}, io.BytesIO()))
        self.assertEqual(result["error_code"], "http_error")

    def test_timeout_and_network(self):
        for error, code in ((TimeoutError(), "timeout"), (URLError(TimeoutError()), "timeout"),
                            (URLError("offline"), "network_error"), (OSError(), "network_error")):
            with self.subTest(error=error):
                result, fetch = self.run_check([], error=error)
                self.assertEqual(result["state"], "error")
                self.assertEqual(result["error_code"], code)
                fetch.assert_called_once()

    def test_invalid_json_and_oversize(self):
        for body in (b"not json", b"[]", b"\xff", b"x" * (updates.MAX_MANIFEST_BYTES + 1)):
            with self.subTest(size=len(body)):
                result, _ = self.run_check([body])
                self.assertEqual(result["error_code"], "invalid_response")


class UpdateBridgeTests(unittest.TestCase):
    def setUp(self):
        if not hasattr(local_app, 'Api'):
            self.skipTest('无法导入 local/app.py（缺少 webview）')
        self.api = stop_auto_relogin_on_cleanup(
            self, local_app.Api(clock=TestWallClock()))
        self.api._emit = Mock()

    def test_constructor_and_bootstrap_do_not_query(self):
        with patch.object(local_app, "check_latest_release") as fetch, \
             patch.object(local_app, "load_prefs", return_value={}), \
             patch.object(local_app, "login_state", return_value={}), \
             patch.object(local_app, "get_lifecycle") as lifecycle:
            lifecycle.return_value.snapshot.return_value = {}
            info = self.api.bootstrap()
        fetch.assert_not_called()
        self.assertFalse(info["update_check"]["checking"])
        self.assertEqual(info["update_check"]["installer_path"], "")

    def test_immediate_ack_single_flight(self):
        with patch.object(local_app.threading, "Thread") as thread, patch.object(local_app, "check_latest_release") as fetch:
            first = self.api.check_update("first")
            second = self.api.check_update("second")
        self.assertTrue(first["queued"])
        self.assertEqual(second["request_id"], "first")
        self.assertTrue(second["skipped"])
        thread.assert_called_once()
        fetch.assert_not_called()

    def test_result_correlation_and_finished_snapshot(self):
        self.api._updates._updating = True
        self.api._updates._update_request_id = "request"
        expected = updates.evaluate_latest_release("1.1.0", release())
        with patch.object(local_app, "check_latest_release", return_value=expected):
            self.api._do_check_update("request")
        self.assertFalse(self.api._updates._updating)
        self.assertEqual(self.api._updates._update_result["request_id"], "request")
        self.api._emit.assert_called_once_with("update", self.api._updates._update_result)

    def test_check_stores_installer_and_clears_old_download(self):
        self.api._updates._updating = True
        self.api._updates._update_request_id = "request"
        self.api._updates._update_installer_path = str(Path(tempfile.gettempdir()).resolve() / "stale.exe")
        picked = updates.evaluate_latest_release("1.0.0", stable())
        picked = dict(picked, installer={"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                                         "bytes": 1024, "sha256": "ab" * 32})
        with patch.object(local_app, "check_latest_release", return_value=picked):
            self.api._do_check_update("request")
        self.assertEqual(self.api._updates._update_installer["name"], INSTALLER)
        self.assertEqual(self.api._updates._update_installer_path, "")

    def test_new_check_reclaims_stale_version_staging(self):
        stale = str(Path("D:/program/versions/.staging-old"))
        self.api._updates._update_staging_path = stale
        with patch.object(local_app.threading, "Thread") as thread, \
                patch.object(local_app.updater, "cleanup_staging") as cleanup:
            self.api.check_update("request")
            thread.assert_called_once()
        cleanup.assert_called_once_with(stale,
                                        version_root=local_app.update_version_paths()["root"])
        self.assertEqual(self.api._updates._update_staging_path, "")

    def test_unexpected_error_or_bad_checker_return_unlocks(self):
        for options in ({"side_effect": RuntimeError()}, {"return_value": None}):
            with self.subTest(options=options):
                self.api._updates._updating = True
                with patch.object(local_app, "check_latest_release", **options):
                    self.api._do_check_update("request")
                self.assertFalse(self.api._updates._updating)
                self.assertEqual(self.api._updates._update_result["state"], "error")

    def test_thread_start_failure_unlocks(self):
        with patch.object(local_app.threading, "Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError()
            result = self.api.check_update("request")
        self.assertFalse(result["ok"])
        self.assertFalse(self.api._updates._updating)

    def test_close_and_invalid_id_reject_without_thread(self):
        with patch.object(local_app.threading, "Thread") as thread:
            self.assertFalse(self.api.check_update("bad id")["ok"])
            self.assertFalse(self.api.update_download("bad id")["ok"])
            self.assertFalse(self.api.update_launch("bad id")["ok"])
            self.api._closing = True
            self.assertFalse(self.api.check_update("request")["ok"])
            self.assertFalse(self.api.update_download("request")["ok"])
            self.assertFalse(self.api.update_launch("request")["ok"])
        thread.assert_not_called()

    def test_closing_drops_result_event(self):
        self.api._closing = True
        with patch.object(local_app, "check_latest_release", return_value={"state": "current"}):
            self.api._do_check_update("request")
        self.api._emit.assert_not_called()
        self.assertFalse(self.api._updates._updating)

    def test_download_requires_selected_installer(self):
        self.api._updates._update_installer = None
        result = self.api.update_download("dl-1")
        self.assertFalse(result["ok"])
        self.assertIn("下载页", result["text"])

    def test_download_single_flight_and_thread_failure(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 1024, "sha256": "ab" * 32}
        self.api._updates._update_installer = installer
        with patch.object(local_app.threading, "Thread") as thread:
            first = self.api.update_download("dl-1")
            self.assertTrue(first["queued"])
            skipped = self.api.update_download("dl-2")
            self.assertTrue(skipped["skipped"])
            thread.assert_called_once()
        self.api._updates._updating = False
        with patch.object(local_app.threading, "Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError()
            result = self.api.update_download("dl-3")
        self.assertFalse(result["ok"])
        self.assertFalse(self.api._updates._updating)

    def test_download_progress_and_ready_state(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._updates._update_installer = installer
        self.api._updates._update_request_id = "dl-1"
        self.api._updates._update_result = {"request_id": "check-1", "state": "available",
                                   "latest_version": "1.1.1", "installer": installer}

        def fake_download(url, **kwargs):
            kwargs["progress"](2, 4)
            kwargs["progress"](4, 4)
            return {"ok": True, "path": str(Path(tempfile.gettempdir()).resolve() / "campus-update-x" / INSTALLER),
                    "bytes": 4, "sha256": "ab" * 32}
        with patch.object(local_app.updater, "download_installer", side_effect=fake_download):
            self.api._do_update_download("dl-1", installer)
        self.assertFalse(self.api._updates._updating)
        self.assertEqual(self.api._updates._update_result["state"], "ready_to_install")
        self.assertTrue(self.api._updates._update_installer_path.endswith(INSTALLER))
        states = [call.args[1]["state"] for call in self.api._emit.call_args_list]
        self.assertEqual(states, ["downloading", "downloading", "ready_to_install"])

    @patch.object(local_app, "version_switch_available", new=lambda *args, **kwargs: True)
    def test_version_payload_cleans_archive_after_staging(self):
        target_files = [{"path": "campus-activity-watch.exe", "bytes": 3,
                         "sha256": "aa" * 32}]
        target = {"version": "1.1.1", "files": target_files,
                  "target_manifest_sha256": "00" * 32}
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 1024, "sha256": "ab" * 32,
                     "full": {"name": "payload.zip", "url": DOWNLOAD + "payload.zip",
                              "bytes": 4, "sha256": "cd" * 32,
                              "target_version": "1.1.1", "target_manifest": target}}
        self.api._updates._update_installer = installer
        self.api._updates._update_result = {"request_id": "check-1", "state": "available",
                                   "latest_version": "1.1.1", "installer": installer}
        downloaded = str(Path(tempfile.gettempdir()).resolve() / "campus-update-payload" / "payload.zip")
        cleanup = Mock()
        with patch.object(local_app.updater, "download_payload", return_value={
                "ok": True, "path": downloaded, "bytes": 4, "sha256": "cd" * 32}), \
                patch.object(local_app.updater, "stage_update", return_value={
                    "ok": True, "path": "D:/versions/.staging-dl-1"}), \
                patch.object(local_app.updater, "cleanup_download", cleanup):
            self.api._do_update_download("dl-1", installer)
        self.assertEqual(self.api._updates._update_result["state"], "ready_to_restart")
        cleanup.assert_called_once_with(downloaded)

    @patch.object(local_app, "version_switch_available", new=lambda *args, **kwargs: True)
    def test_version_payload_failure_falls_back_to_inno_installer(self):
        target = {"version": "1.1.1", "files": [{"path": "app.exe", "bytes": 1,
                                                     "sha256": "aa" * 32}],
                  "target_manifest_sha256": "00" * 32}
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 1024, "sha256": "ab" * 32,
                     "full": {"name": "payload.zip", "url": DOWNLOAD + "payload.zip",
                              "bytes": 4, "sha256": "cd" * 32,
                              "target_version": "1.1.1", "target_manifest": target}}
        self.api._updates._update_installer = installer
        self.api._updates._update_result = {"request_id": "check-1", "state": "available",
                                   "latest_version": "1.1.1", "installer": installer}
        payload_path = str(Path(tempfile.gettempdir()).resolve() / "campus-update-payload" / "payload.zip")
        installer_path = str(Path(tempfile.gettempdir()).resolve() / "campus-update-installer" / INSTALLER)
        with patch.object(local_app.updater, "download_payload", return_value={
                "ok": True, "path": payload_path, "bytes": 4, "sha256": "cd" * 32}), \
                patch.object(local_app.updater, "stage_update", return_value={
                    "ok": False, "text": "目标清单不一致"}), \
                patch.object(local_app.updater, "cleanup_download") as cleanup, \
                patch.object(local_app.updater, "download_installer", return_value={
                    "ok": True, "path": installer_path, "bytes": 1024, "sha256": "ab" * 32}):
            self.api._do_update_download("dl-1", installer)
        self.assertEqual(self.api._updates._update_result["state"], "ready_to_install")
        self.assertEqual(self.api._updates._update_installer_path, installer_path)
        cleanup.assert_called_once_with(payload_path)

    def test_download_hash_failure_goes_to_failed(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._updates._update_installer = installer
        with patch.object(local_app.updater, "download_installer",
                          return_value={"ok": False, "error_code": "hash_mismatch", "text": "哈希不符"}):
            self.api._do_update_download("dl-1", installer)
        self.assertFalse(self.api._updates._updating)
        self.assertEqual(self.api._updates._update_result["state"], "failed")
        self.assertEqual(self.api._updates._update_result["error_code"], "hash_mismatch")
        self.assertEqual(self.api._updates._update_installer_path, "")

    def test_download_cancel_returns_to_available(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._updates._update_installer = installer
        with patch.object(local_app.updater, "download_installer",
                          return_value={"ok": False, "error_code": "cancelled", "text": "已取消"}):
            self.api._do_update_download("dl-1", installer)
        self.assertEqual(self.api._updates._update_result["state"], "available")
        self.assertEqual(self.api._updates._update_result["error_code"], "cancelled")

    def test_update_cancel_sets_flag_only(self):
        self.assertFalse(self.api._updates._update_cancelled)
        self.assertTrue(self.api.update_cancel()["ok"])
        self.assertTrue(self.api._updates._update_cancelled)

    def test_launch_requires_verified_path(self):
        result = self.api.update_launch("launch-1")
        self.assertFalse(result["ok"])
        self.assertIn("安装包", result["text"])

    def test_launch_publishes_launching_then_success(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._updates._update_installer = installer
        self.api._updates._update_installer_path = str(Path(tempfile.gettempdir()).resolve() / "campus-update-x" / INSTALLER)
        self.api._updates._update_result = {"request_id": "dl-1", "state": "ready_to_install",
                                   "installer": installer}
        with patch.object(local_app.updater, "launch_installer",
                          return_value={"ok": True, "path": self.api._updates._update_installer_path}):
            result = self.api.update_launch("launch-1")
        self.assertTrue(result["ok"])
        states = [call.args[1]["state"] for call in self.api._emit.call_args_list]
        self.assertEqual(states, ["launching", "launching"])
        self.assertIn("关闭本工具", result["text"])

    def test_launch_failure_goes_to_failed(self):
        self.api._updates._update_installer_path = str(Path(tempfile.gettempdir()).resolve() / "campus-update-x" / INSTALLER)
        with patch.object(local_app.updater, "launch_installer",
                          return_value={"ok": False, "error_code": "launch_failed", "text": "没能启动"}):
            result = self.api.update_launch("launch-1")
        self.assertFalse(result["ok"])
        self.assertEqual(self.api._updates._update_result["state"], "failed")
        self.assertEqual(self.api._updates._update_result["error_code"], "launch_failed")


class DirectManifestReproTests(unittest.TestCase):
    def setUp(self):
        if not hasattr(local_app, 'Api'):
            self.skipTest('无法导入 local/app.py（缺少 webview）')
    """G1 复现：api.github.com 对未登录请求按出口 IP 限 60 次/小时，共享代理出口打到 403。

    期望行为：检查更新与组件解析都不再碰这个接口，改走 Release 资产直链
    （releases/latest/download/manifest.json 与 releases/download/v<版本>/manifest.json），
    清单里的 name/bytes/sha256 已经够用，校验一点不少。修复前这两条用例应当是红的。
    """

    def response(self, body):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = body
        return response

    def fake_open(self, bodies):
        queue = list(bodies)

        def opener(request, *args, **kwargs):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            if "api.github.com" in url:
                raise HTTPError(url, 403, "", {}, io.BytesIO())
            return self.response(queue.pop(0) if queue else b"")
        return opener

    def update_manifest(self, version="1.1.1"):
        return manifest(version=version, files={
            INSTALLER: {"sha256": "ab" * 32, "bytes": 1024},
            COMPONENT: {"sha256": "cd" * 32, "bytes": 2048},
        })

    def test_api_rate_limit_does_not_block_update_check(self):
        body = json.dumps(self.update_manifest()).encode()
        with patch.object(updates, "urlopen", side_effect=self.fake_open([body])) as fetch:
            result = updates.check_latest_release("1.1.0")
        self.assertEqual(result["state"], "available")
        urls = [call.args[0].full_url for call in fetch.call_args_list]
        self.assertTrue(all("api.github.com" not in url for url in urls), urls)

    def test_api_rate_limit_does_not_block_component_resolve(self):
        api = local_app.Api.__new__(local_app.Api)
        body = json.dumps(self.update_manifest()).encode()

        def fake_fetch(url, limit, user_agent):
            if "api.github.com" in url:
                raise HTTPError(url, 403, "", {}, io.BytesIO())
            return body
        with patch.object(local_app._update_check, "_fetch_bytes", side_effect=fake_fetch) as fetch:
            verdict = api._resolve_component_asset("1.1.1", "phone_control")
        self.assertTrue(verdict["ok"], verdict)
        self.assertEqual(verdict["asset"]["sha256"], "cd" * 32)
        urls = [call.args[0] for call in fetch.call_args_list]
        self.assertTrue(all("api.github.com" not in url for url in urls), urls)

    def test_release_without_manifest_says_no_component_not_network(self):
        """I3 调查：发布页上还没有这个版本（清单 404）时，组件解析落成 no_component 与「没有发布」文案，
        不落成网络或超时文案。"""
        api = local_app.Api.__new__(local_app.Api)

        def fake_fetch(url, limit, user_agent):
            raise HTTPError(url, 404, "", {}, io.BytesIO())
        with patch.object(local_app._update_check, "_fetch_bytes", side_effect=fake_fetch):
            verdict = api._resolve_component_asset("1.1.1", "phone_control")
        self.assertFalse(verdict["ok"], verdict)
        self.assertEqual(verdict["error"], "no_component")
        self.assertIn("没有发布手机控制组件包", verdict["text"])


class UnusedManifestEntryTests(unittest.TestCase):
    """U6：发布清单里新客户端用不到的文件项不合格，不能让整份清单作废。"""

    EXTRA = "future-tool-notes.txt"

    def raw(self, extra_entry, **overrides):
        files = {INSTALLER: {"sha256": "ab" * 32, "bytes": 1024},
                 self.EXTRA: extra_entry}
        data = manifest(files=files)
        data.update(overrides)
        return json.dumps(data).encode()

    def test_unused_entry_with_oversize_bytes_is_skipped_not_fatal(self):
        raw = self.raw({"sha256": "ab" * 32, "bytes": 10 ** 12})
        payload = updates.payload_from_manifest(raw)
        names = {item["name"] for item in payload["assets"]}
        self.assertIn(INSTALLER, names)
        self.assertNotIn(self.EXTRA, names)
        self.assertEqual(payload["skipped"], [self.EXTRA])

    def test_installer_still_resolves_when_an_unused_entry_is_bad(self):
        raw = self.raw({"sha256": "zz", "bytes": 5})
        with patch.object(updates, "_fetch_bytes", return_value=raw):
            result = updates.check_latest_release("1.1.0")
        self.assertEqual(result["state"], "available", result)
        self.assertEqual(result["installer"]["name"], INSTALLER)
        self.assertEqual(result["manifest_skipped"], [self.EXTRA])

    def test_used_installer_entry_is_still_strict(self):
        for bad in ({"sha256": "zz", "bytes": 1024},
                    {"sha256": "ab" * 32, "bytes": 10 ** 12}):
            data = manifest(files={INSTALLER: bad})
            with self.subTest(entry=bad), self.assertRaises(ValueError):
                updates.payload_from_manifest(json.dumps(data).encode())

    def test_used_full_payload_and_split_entries_are_still_strict(self):
        good = {"sha256": "ab" * 32, "bytes": 1024}
        bad = {"sha256": "ab" * 32, "bytes": 0}
        for field, holder in (("full_payload", {"name": "payload.zip"}),
                              ("deltas", [{"name": "delta.zip", "base_version": "1.1.0"}]),
                              ("split_assets", {"relogin_ocr_model": {"name": "model.zip"}})):
            name = ("payload.zip" if field == "full_payload"
                    else "delta.zip" if field == "deltas" else "model.zip")
            data = manifest(files={INSTALLER: good, name: bad})
            data[field] = holder
            with self.subTest(field=field), self.assertRaises(ValueError):
                updates.payload_from_manifest(json.dumps(data).encode())

# ==================== 源自 test_update_delta.py ====================
"""文件级增量包的离线契约测试。"""

import shutil

LOCAL = Path(__file__).resolve().parents[2]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure.update import update_delta  # noqa: E402


class DeltaTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="campus-delta-test-")).resolve()
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

# ==================== 源自 test_update_launcher.py ====================
"""版本启动器（update_launcher）的返修回归：等待父进程、目标目录残留、坏 staging、current 回退。

全部使用 tempfile.gettempdir() 下的临时目录和替身：不真的启动进程、不杀进程，
Windows 句柄接口（OpenProcess / WaitForSingleObject / GetLastError）用替身注入，
不调用真实的 kernel32。

@author Author
"""

import uuid
from unittest import mock

LOCAL = Path(__file__).resolve().parents[2]
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
        self.root = Path(tempfile.gettempdir()).resolve() / ("campus-launcher-test-" + uuid.uuid4().hex[:12])
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

# ==================== 源自 test_update_service.py ====================
"""UpdateService 直测：不经 Api，端口全用内存替身，先断言返回值与事件再断言内部字段。

覆盖单飞（检查在途时再检查、在途时下载）、关闭中拒绝、取消、snapshot 的四个键。

@author Author
"""


LOCAL = Path(__file__).resolve().parents[2]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.desktop import update_service  # noqa: E402


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


class UpdateServiceLaunchTests(ServiceCase):
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

# ==================== 源自 test_updater.py ====================
"""安装器流式下载与启动桥接的安全边界；全部替身，不访问网络、不启动正式安装器。

@author Author
"""
from hashlib import sha256
import os
import zipfile

LOCAL = Path(__file__).resolve().parents[2]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
from infrastructure.update import updater  # noqa: E402

NAME = "campus-activity-watch-installer-v1.1.1-win-x64.exe"
URL = "https://github.com/Env0i/campus-activity-assistant/releases/download/v1.1.1/" + NAME
BODY = b"installer-bytes-0123456789"
DIGEST = sha256(BODY).hexdigest()
TEMP_BASE = Path(tempfile.gettempdir()).resolve()
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

    def test_http_error_reports_status_for_callers(self):
        """I3：HTTP 错误仍是 http_error（主程序更新路径不变），但多带 http_status，
        让组件下载能分出「资产没传（404）」与其他 HTTP 错误。"""
        for status in (404, 500):
            with self.subTest(status=status), patch.object(
                    updater, "urlopen",
                    side_effect=HTTPError(URL, status, "x", {}, io.BytesIO(b""))):
                result = updater.download_installer(
                    URL, name=NAME, expect_bytes=len(BODY), expect_sha256=DIGEST, root=self.root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_code"], "http_error")
            self.assertEqual(result["http_status"], status)
        self.assertCleanedUp()

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
        self.root = Path(tempfile.mkdtemp(prefix="campus-version-test-")).resolve()
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

    def test_stage_failure_text_has_no_local_path_and_detail_keeps_the_reason(self):
        """U2：staging 失败给界面固定句子；带路径的异常细节只放 detail 供运行记录。"""
        missing = self.root / "secret-dir" / "full.zip"
        manifest = update_delta.manifest_from_directory(self._target(), version="1.2.2")
        result = updater.stage_update(
            self.old, missing, self.root / "staging", mode="full",
            target_manifest=manifest, target_version="1.2.2")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "apply_failed")
        self.assertNotIn("secret-dir", result["text"])
        self.assertNotIn(str(self.root), result["text"])
        self.assertIn("FileNotFoundError", result["detail"])

    def test_switch_failure_text_has_no_local_path(self):
        staging = self.root / "staging"
        staging.mkdir()
        (staging / "app.exe").write_bytes(b"new")
        secret = str(self.root / "secret-dir" / "current.json")
        with patch.object(updater, "_atomic_write_json", side_effect=OSError(secret)):
            result = updater.switch_version(
                self.versions, staging, "1.2.2", current_file=self.root / "current.json")
        self.assertFalse(result["ok"])
        self.assertNotIn("secret-dir", result["text"])
        self.assertIn("OSError", result["detail"])


class SweepVersionRootTests(unittest.TestCase):
    """D3：版本目录清理只删受控残留与多余旧版本，不碰 current/previous、运行目录和数据。"""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="campus-sweep-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.versions = self.root / "versions"
        self.versions.mkdir()
        self.data = self.root / "data"
        self.data.mkdir()
        (self.data / "session.json").write_bytes(b"session")
        self.current = self.root / "current.json"
        self.current.write_text(json.dumps(
            {"version": "1.1.0", "previous_version": "1.0.0"}), encoding="utf-8")
        for name in ("0.8.0", "0.9.0", "1.0.0", "1.1.0", "1.3.0",
                     ".staging-a", ".staging-a.stage-1f2e", ".stage-b", ".old-1.1.0-abcd"):
            folder = self.versions / name
            folder.mkdir()
            (folder / "campus-activity-watch.exe").write_bytes(b"x")
        (self.versions / ".part-c").write_bytes(b"partial")

    def names(self):
        return sorted(item.name for item in self.versions.iterdir())

    def test_removes_leftovers_and_versions_beyond_current_and_previous(self):
        result = updater.sweep_version_root(
            self.versions, current_file=self.current, keep_dir=self.versions / "1.3.0")
        self.assertEqual(self.names(), ["1.0.0", "1.1.0", "1.3.0"])
        for name in ("0.8.0", "0.9.0", ".staging-a", ".staging-a.stage-1f2e",
                     ".stage-b", ".old-1.1.0-abcd", ".part-c"):
            self.assertIn(name, result["removed"])
        self.assertEqual(result["failed"], [])
        self.assertEqual((self.data / "session.json").read_bytes(), b"session")
        self.assertEqual(json.loads(self.current.read_text(encoding="utf-8"))["version"], "1.1.0")

    def test_without_keep_dir_unreferenced_version_is_removed_too(self):
        updater.sweep_version_root(self.versions, current_file=self.current)
        self.assertEqual(self.names(), ["1.0.0", "1.1.0"])

    def test_unreadable_current_removes_only_temp_leftovers(self):
        # 不知道谁是当前版本时，宁可多留旧版本，也不能删错
        self.current.write_text("{not json", encoding="utf-8")
        updater.sweep_version_root(self.versions, current_file=self.current)
        self.assertEqual(self.names(), ["0.8.0", "0.9.0", "1.0.0", "1.1.0", "1.3.0"])

    def test_unknown_names_are_left_alone(self):
        (self.versions / "notes.txt").write_bytes(b"keep")
        (self.versions / "1.2").mkdir()
        updater.sweep_version_root(self.versions, current_file=self.current)
        self.assertIn("notes.txt", self.names())
        self.assertIn("1.2", self.names())

    def test_links_are_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"keep")
        link = self.versions / ".staging-link"
        patches = []
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            # 本机没有创建符号链接的权限：造一个真实目录，再让 is_symlink 对它返回真
            link.mkdir()
            (link / "keep.txt").write_bytes(b"keep")
            real = Path.is_symlink
            patches.append(patch.object(
                Path, "is_symlink", lambda self: self.name == ".staging-link" or real(self)))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        updater.sweep_version_root(self.versions, current_file=self.current)
        self.assertTrue((outside / "keep.txt").is_file())
        self.assertTrue(os.path.lexists(link))

    def test_failures_are_reported_not_raised(self):
        with patch.object(updater.shutil, "rmtree", side_effect=OSError("busy")):
            result = updater.sweep_version_root(
                self.versions, current_file=self.current, keep_dir=self.versions / "1.3.0")
        self.assertIn("0.8.0", result["failed"])
        self.assertTrue((self.versions / "0.8.0").is_dir())

    def test_missing_root_is_a_noop(self):
        result = updater.sweep_version_root(self.root / "nope", current_file=self.current)
        self.assertEqual(result["removed"], [])
        self.assertEqual(result["failed"], [])

if __name__ == "__main__":
    unittest.main()
