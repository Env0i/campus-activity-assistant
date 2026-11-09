"""手动更新纯逻辑与桥接契约；所有HTTP均为替身，不访问学校或GitHub。

@author Author
"""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

LOCAL = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
import update_check as updates
import app as local_app
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
        self.api._updating = True
        self.api._update_request_id = "request"
        expected = updates.evaluate_latest_release("1.1.0", release())
        with patch.object(local_app, "check_latest_release", return_value=expected):
            self.api._do_check_update("request")
        self.assertFalse(self.api._updating)
        self.assertEqual(self.api._update_result["request_id"], "request")
        self.api._emit.assert_called_once_with("update", self.api._update_result)

    def test_check_stores_installer_and_clears_old_download(self):
        self.api._updating = True
        self.api._update_request_id = "request"
        self.api._update_installer_path = str(Path(tempfile.gettempdir()) / "stale.exe")
        picked = updates.evaluate_latest_release("1.0.0", stable())
        picked = dict(picked, installer={"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                                         "bytes": 1024, "sha256": "ab" * 32})
        with patch.object(local_app, "check_latest_release", return_value=picked):
            self.api._do_check_update("request")
        self.assertEqual(self.api._update_installer["name"], INSTALLER)
        self.assertEqual(self.api._update_installer_path, "")

    def test_unexpected_error_or_bad_checker_return_unlocks(self):
        for options in ({"side_effect": RuntimeError()}, {"return_value": None}):
            with self.subTest(options=options):
                self.api._updating = True
                with patch.object(local_app, "check_latest_release", **options):
                    self.api._do_check_update("request")
                self.assertFalse(self.api._updating)
                self.assertEqual(self.api._update_result["state"], "error")

    def test_thread_start_failure_unlocks(self):
        with patch.object(local_app.threading, "Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError()
            result = self.api.check_update("request")
        self.assertFalse(result["ok"])
        self.assertFalse(self.api._updating)

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
        self.assertFalse(self.api._updating)

    def test_download_requires_selected_installer(self):
        self.api._update_installer = None
        result = self.api.update_download("dl-1")
        self.assertFalse(result["ok"])
        self.assertIn("下载页", result["text"])

    def test_download_single_flight_and_thread_failure(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 1024, "sha256": "ab" * 32}
        self.api._update_installer = installer
        with patch.object(local_app.threading, "Thread") as thread:
            first = self.api.update_download("dl-1")
            self.assertTrue(first["queued"])
            skipped = self.api.update_download("dl-2")
            self.assertTrue(skipped["skipped"])
            thread.assert_called_once()
        self.api._updating = False
        with patch.object(local_app.threading, "Thread") as thread:
            thread.return_value.start.side_effect = RuntimeError()
            result = self.api.update_download("dl-3")
        self.assertFalse(result["ok"])
        self.assertFalse(self.api._updating)

    def test_download_progress_and_ready_state(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._update_installer = installer
        self.api._update_request_id = "dl-1"
        self.api._update_result = {"request_id": "check-1", "state": "available",
                                   "latest_version": "1.1.1", "installer": installer}

        def fake_download(url, **kwargs):
            kwargs["progress"](2, 4)
            kwargs["progress"](4, 4)
            return {"ok": True, "path": str(Path(tempfile.gettempdir()) / "campus-update-x" / INSTALLER),
                    "bytes": 4, "sha256": "ab" * 32}
        with patch.object(local_app.updater, "download_installer", side_effect=fake_download):
            self.api._do_update_download("dl-1", installer)
        self.assertFalse(self.api._updating)
        self.assertEqual(self.api._update_result["state"], "ready_to_install")
        self.assertTrue(self.api._update_installer_path.endswith(INSTALLER))
        states = [call.args[1]["state"] for call in self.api._emit.call_args_list]
        self.assertEqual(states, ["downloading", "downloading", "ready_to_install"])

    def test_download_hash_failure_goes_to_failed(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._update_installer = installer
        with patch.object(local_app.updater, "download_installer",
                          return_value={"ok": False, "error_code": "hash_mismatch", "text": "哈希不符"}):
            self.api._do_update_download("dl-1", installer)
        self.assertFalse(self.api._updating)
        self.assertEqual(self.api._update_result["state"], "failed")
        self.assertEqual(self.api._update_result["error_code"], "hash_mismatch")
        self.assertEqual(self.api._update_installer_path, "")

    def test_download_cancel_returns_to_available(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._update_installer = installer
        with patch.object(local_app.updater, "download_installer",
                          return_value={"ok": False, "error_code": "cancelled", "text": "已取消"}):
            self.api._do_update_download("dl-1", installer)
        self.assertEqual(self.api._update_result["state"], "available")
        self.assertEqual(self.api._update_result["error_code"], "cancelled")

    def test_update_cancel_sets_flag_only(self):
        self.assertFalse(self.api._update_cancelled)
        self.assertTrue(self.api.update_cancel()["ok"])
        self.assertTrue(self.api._update_cancelled)

    def test_launch_requires_verified_path(self):
        result = self.api.update_launch("launch-1")
        self.assertFalse(result["ok"])
        self.assertIn("安装包", result["text"])

    def test_launch_publishes_launching_then_success(self):
        installer = {"name": INSTALLER, "url": DOWNLOAD + INSTALLER,
                     "bytes": 4, "sha256": "ab" * 32}
        self.api._update_installer = installer
        self.api._update_installer_path = str(Path(tempfile.gettempdir()) / "campus-update-x" / INSTALLER)
        self.api._update_result = {"request_id": "dl-1", "state": "ready_to_install",
                                   "installer": installer}
        with patch.object(local_app.updater, "launch_installer",
                          return_value={"ok": True, "path": self.api._update_installer_path}):
            result = self.api.update_launch("launch-1")
        self.assertTrue(result["ok"])
        states = [call.args[1]["state"] for call in self.api._emit.call_args_list]
        self.assertEqual(states, ["launching", "launching"])
        self.assertIn("关闭本工具", result["text"])

    def test_launch_failure_goes_to_failed(self):
        self.api._update_installer_path = str(Path(tempfile.gettempdir()) / "campus-update-x" / INSTALLER)
        with patch.object(local_app.updater, "launch_installer",
                          return_value={"ok": False, "error_code": "launch_failed", "text": "没能启动"}):
            result = self.api.update_launch("launch-1")
        self.assertFalse(result["ok"])
        self.assertEqual(self.api._update_result["state"], "failed")
        self.assertEqual(self.api._update_result["error_code"], "launch_failed")


class DirectManifestReproTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
