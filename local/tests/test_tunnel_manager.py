#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""远程通道与二维码测试：Tailscale 探测、cloudflared 假进程与 QR payload。

全程离线替身：假 which/runner/Popen、假 segno、假 ddddocr 无关；
不启真实隧道、不装真实依赖、不连学校。

@author Author
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import component_packages, phone_qr, tunnel_manager  # noqa: E402


class FakeCompleted:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.returncode = 0


class FakeRunner:
    """tailscale 命令替身：按命令名给输出，可整体抛错。"""

    def __init__(self, ip_output="", status_output="", raises=None):
        self.ip_output = ip_output
        self.status_output = status_output
        self.raises = raises
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        if self.raises is not None:
            raise self.raises
        if "ip" in args:
            return FakeCompleted(self.ip_output)
        return FakeCompleted(self.status_output)


class ParseTailscaleTests(unittest.TestCase):
    def test_only_cgnat_ipv4_is_taken(self):
        text = "100.64.0.5\n100.100.7.8\n192.168.1.9\n10.0.0.2\n1.2.3.4\n::1"
        self.assertEqual(tunnel_manager.parse_tailscale_ips(text),
                         ["100.64.0.5", "100.100.7.8"])

    def test_duplicates_and_out_of_range_octets_dropped(self):
        text = "100.64.0.5 100.64.0.5 100.128.1.1 100.64.999.1 100.200.1.1"
        self.assertEqual(tunnel_manager.parse_tailscale_ips(text), ["100.64.0.5"])

    def test_empty_and_garbage_return_empty(self):
        for text in ("", "none", "100.64.", "999.999.999.999"):
            with self.subTest(text=text):
                self.assertEqual(tunnel_manager.parse_tailscale_ips(text), [])

    def test_magicdns_from_status_json_strips_trailing_dot(self):
        status = '{"Self": {"DNSName": "my-box.tailnet.ts.net."}}'
        self.assertEqual(tunnel_manager.parse_magicdns(status),
                         "my-box.tailnet.ts.net")
        self.assertEqual(
            tunnel_manager.parse_magicdns({"self": {"dnsName": "n."}}), "n")

    def test_backend_state_parsed_from_status_json(self):
        self.assertEqual(
            tunnel_manager.parse_backend_state('{"BackendState": "Running"}'),
            "Running")
        self.assertEqual(
            tunnel_manager.parse_backend_state({"BackendState": " Stopped "}),
            "Stopped")

    def test_backend_state_missing_or_bad_returns_empty(self):
        for value in ("", "{}", "[]", 5, None, "{not json", '{"BackendState": null}'):
            with self.subTest(value=value):
                self.assertEqual(tunnel_manager.parse_backend_state(value), "")

    def test_magicdns_missing_or_bad_returns_empty(self):
        for value in ("", "{}", "[]", 5, None, '{"Self": {}}',
                      "{not json", {"Self": {"DNSName": "  ."}}):
            with self.subTest(value=value):
                self.assertEqual(tunnel_manager.parse_magicdns(value), "")


class ResolveTailscaleTests(unittest.TestCase):
    """PATH 里没有 CLI 时，Windows 默认安装目录必须能找到。"""

    def test_prefers_path_lookup(self):
        self.assertEqual(
            tunnel_manager.resolve_tailscale(which=lambda _n: "C:/x/tailscale.exe"),
            "C:/x/tailscale.exe")

    def test_falls_back_to_program_files(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name) / "Tailscale"
            folder.mkdir()
            exe = folder / "tailscale.exe"
            exe.write_bytes(b"MZ")
            found = tunnel_manager.resolve_tailscale(
                which=lambda _n: None, env={"ProgramFiles": name})
            self.assertEqual(found, str(exe))

    def test_returns_empty_without_any_candidate(self):
        with tempfile.TemporaryDirectory() as name:
            self.assertEqual(
                tunnel_manager.resolve_tailscale(which=lambda _n: None,
                                                 env={"ProgramFiles": name}), "")


class TailscaleEndpointTests(unittest.TestCase):
    def test_missing_binary_is_explicit(self):
        result = tunnel_manager.tailscale_endpoint(
            runner=FakeRunner(), which=lambda _n: None, env={})
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "tailscale_missing")
        self.assertIn("Tailscale", result["text"])
        self.assertEqual(result["state"], "missing")

    def test_probe_failure_reports_type_only(self):
        result = tunnel_manager.tailscale_endpoint(
            runner=FakeRunner(raises=OSError("hang")),
            which=lambda _n: "C:/tailscale.exe")
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "tailscale_probe_failed")
        self.assertIn("OSError", result["text"])

    def test_not_logged_in_when_no_cgnat_address(self):
        result = tunnel_manager.tailscale_endpoint(
            runner=FakeRunner(ip_output=""),
            which=lambda _n: "tailscale")
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "tailscale_not_logged_in")

    def test_connected_state_is_explicit(self):
        runner = FakeRunner(
            ip_output="100.64.0.9\n",
            status_output='{"BackendState": "Running", "Self": {"DNSName": "box.ts.net."}}')
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertTrue(result["available"])
        self.assertEqual(result["state"], "connected")
        self.assertEqual(result["public_host"], "box.ts.net")

    def test_backend_needs_login_maps_to_not_logged_in(self):
        runner = FakeRunner(ip_output="", status_output='{"BackendState": "NeedsLogin"}')
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "tailscale_not_logged_in")
        self.assertEqual(result["state"], "not_logged_in")

    def test_backend_stopped_reports_probe_failure_with_state_text(self):
        for backend in ("Stopped", "NoState", "Starting", "NeedsMachineAuth"):
            with self.subTest(backend=backend):
                runner = FakeRunner(
                    ip_output="",
                    status_output='{"BackendState": "%s"}' % backend)
                result = tunnel_manager.tailscale_endpoint(
                    runner=runner, which=lambda _n: "tailscale")
                self.assertFalse(result["available"])
                self.assertEqual(result["error"], "tailscale_probe_failed")
                self.assertEqual(result["state"], "probe_failed")
                self.assertIn(backend, result["text"])

    def test_unknown_backend_state_is_never_available(self):
        # 取值无法识别时宁可报探测失败，也不能让 UI 显示成「已连接」
        runner = FakeRunner(
            ip_output="100.64.0.9\n",
            status_output='{"BackendState": "SomethingNew"}')
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertFalse(result["available"])
        self.assertEqual(result["error"], "tailscale_probe_failed")
        self.assertEqual(result["state"], "probe_failed")
        self.assertIn("SomethingNew", result["text"])

    def test_magicdns_is_preferred_public_host(self):
        runner = FakeRunner(
            ip_output="100.64.0.9\n", status_output='{"Self": {"DNSName": "box.ts.net."}}')
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertTrue(result["available"])
        self.assertEqual(result["bind_host"], "100.64.0.9")
        self.assertEqual(result["public_host"], "box.ts.net")
        self.assertEqual(result["magicdns"], "box.ts.net")

    def test_ip_is_fallback_public_host_without_magicdns(self):
        runner = FakeRunner(ip_output="100.64.0.9\n100.64.0.10\n", status_output="{}")
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertEqual(result["public_host"], "100.64.0.9")
        self.assertEqual(result["addresses"], ["100.64.0.9", "100.64.0.10"])


class HiddenConsoleTests(unittest.TestCase):
    """探测 Tailscale 不许闪黑框：面板几秒探一次，闪一下比慢更烦人。"""

    def test_fake_runner_never_receives_spawn_flags(self):
        # 替身如果收到 creationflags，说明参数喂给了错误的 runner
        self.assertEqual(tunnel_manager._hidden_window_kwargs(FakeRunner()), {})

    def test_windows_hides_the_console_window(self):
        if os.name != "nt":
            self.skipTest("黑框只在 Windows 上出现")
        kwargs = tunnel_manager._hidden_window_kwargs(subprocess.run)
        self.assertEqual(kwargs["creationflags"],
                         getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.assertIn("startupinfo", kwargs)

    def test_probe_still_reports_connected_with_flags(self):
        runner = FakeRunner(ip_output="100.64.0.9\n",
                            status_output='{"BackendState": "Running"}')
        result = tunnel_manager.tailscale_endpoint(
            runner=runner, which=lambda _n: "tailscale")
        self.assertTrue(result["available"])
        self.assertEqual(result["bind_host"], "100.64.0.9")


class ResolveCloudflaredTests(unittest.TestCase):
    """cloudflared 只认组件包校验过的路径。

    PATH 上的、解释器旁边的、resource_root/bin 下的二进制都无法证明版本与哈希，
    一律不采信：装个旧版 cloudflared 就能绕过组件包校验，等于没有校验。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="campus-cf-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"

    def test_returns_the_verified_component_path(self):
        verified = str(self.data / "advanced" / "phone_control" / "bin" / "cloudflared.exe")
        with mock.patch.object(component_packages, "cloudflared",
                               return_value=verified) as component:
            found = tunnel_manager.resolve_cloudflared(
                resource_root=self.root, here=self.root, root=self.data)
        self.assertEqual(found, verified)
        component.assert_called_once_with(root=self.data)

    def test_rejects_bin_directories_and_path_lookalikes(self):
        for folder in (self.root / "bin", self.root / "here" / "bin"):
            folder.mkdir(parents=True)
            (folder / "cloudflared.exe").write_bytes(b"stub")
        original = tunnel_manager.shutil.which
        tunnel_manager.shutil.which = lambda _n: "C:/bin/cloudflared.exe"
        self.addCleanup(
            lambda: setattr(tunnel_manager.shutil, "which", original))
        with mock.patch.object(component_packages, "cloudflared", return_value=""):
            found = tunnel_manager.resolve_cloudflared(
                resource_root=self.root, here=self.root / "here", root=self.data)
        self.assertEqual(found, "")


class FakeProc:
    def __init__(self, lines, *, hang=False):
        self.stdout = list(lines)
        self.hang = hang
        self.terminated = False
        self.killed = False
        self.waits = []
        self.exit = None

    def poll(self):
        return self.exit

    def terminate(self):
        self.terminated = True
        self.exit = -15

    def kill(self):
        self.killed = True
        self.exit = -9

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.hang:
            raise subprocess.TimeoutError("hang")
        return self.exit


class FakePopen:
    def __init__(self, lines=(), raises=None, hang=False):
        self.proc = FakeProc(lines, hang=hang)
        self.raises = raises
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), dict(kwargs)))
        if self.raises is not None:
            raise self.raises
        return self.proc


class CloudflareTunnelTests(unittest.TestCase):
    def test_missing_executable_is_explicit(self):
        tunnel = tunnel_manager.CloudflareTunnel("", popen=FakePopen())
        result = tunnel.start("http://127.0.0.1:8765")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cloudflared_missing")

    def test_start_failure_reports_type_only(self):
        popen = FakePopen(raises=OSError("no exe"))
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        result = tunnel.start("http://127.0.0.1:8765")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "tunnel_start_failed")
        self.assertIn("OSError", result["text"])

    def test_quick_tunnel_url_is_parsed_and_kept(self):
        popen = FakePopen(lines=[
            "INF +--------------------------------------------------------------------+\n",
            "INF |  Your quick Tunnel has been created! Visit it:                    |\n",
            "INF |  https://neat-random-words.trycloudflare.com                      |\n",
        ])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        result = tunnel.start("http://127.0.0.1:8765")
        self.assertTrue(result["ok"])
        self.assertEqual(result["url"], "https://neat-random-words.trycloudflare.com")
        self.assertEqual(tunnel.public_url, result["url"])
        args = popen.calls[0][0]
        self.assertEqual(args[:2], ["cf.exe", "tunnel"])
        self.assertIn("http://127.0.0.1:8765", args)

    def test_url_without_trycloudflare_host_is_ignored(self):
        popen = FakePopen(lines=["INF visit https://evil.example.com now\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        result = tunnel.start("http://127.0.0.1:8765", timeout_s=0.5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "tunnel_url_timeout")
        self.assertEqual(tunnel.public_url, "", "失败后不得留残留地址")

    def test_no_url_stops_child_and_clears(self):
        popen = FakePopen(lines=["INF starting\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        result = tunnel.start("http://127.0.0.1:8765", timeout_s=0.5)
        self.assertFalse(result["ok"])
        self.assertTrue(popen.proc.terminated, "超时必须收掉子进程")
    def test_status_reports_stopped_tunnel_as_temporary(self):
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=FakePopen())
        state = tunnel.status()
        self.assertFalse(state["running"])
        self.assertEqual(state["state"], "stopped")
        self.assertTrue(state["temporary"], "快速隧道永远是临时的")
        self.assertTrue(state["restart_requires_pairing"])

    def test_status_reports_running_tunnel_with_public_url(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        state = tunnel.status()
        self.assertTrue(state["running"])
        self.assertEqual(state["state"], "running")
        self.assertEqual(state["public_url"], "https://x.trycloudflare.com")

    def test_status_clears_url_after_child_exit(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        popen.proc.exit = 0
        state = tunnel.status()
        self.assertFalse(state["running"])
        self.assertEqual(state["state"], "exited")
        self.assertEqual(state["error"], "tunnel_exited")
        self.assertEqual(state["public_url"], "", "退出的隧道不能继续对外宣称地址")
        self.assertTrue(state["restart_requires_pairing"])

    def test_exited_status_is_reported_once_then_stopped(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        popen.proc.exit = 0
        first = tunnel.status()
        again = tunnel.status()
        self.assertEqual(first["state"], "exited", "第一次读到退出必须如实报")
        self.assertEqual(again["state"], "stopped",
                         "退出只报一次，之后就是没在运行")
        self.assertNotIn("error", again, "第二次不该再带退出错误")

    def test_stop_after_exit_clears_the_address_and_reports_stopped(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        popen.proc.exit = 0
        self.assertEqual(tunnel.status()["state"], "exited")
        self.assertTrue(tunnel.stop()["ok"])
        state = tunnel.status()
        self.assertEqual(state["state"], "stopped")
        self.assertEqual(state["public_url"], "")
        self.assertNotIn("error", state)

    def test_start_rechecks_the_managed_component_first(self):
        """启动前必须再验一次组件：缓存路径被换掉就不能拿它去跑。"""
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel(
            "cf.exe", popen=popen, verify=lambda _path: "")
        result = tunnel.start("http://127.0.0.1:8765")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "cloudflared_untrusted")
        self.assertEqual(tunnel.executable, "", "不可信路径要从缓存里清掉")
        self.assertEqual(popen.calls, [], "校验没过就不能起子进程")

    def test_start_uses_the_reverified_path(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        trusted = "D:/data/advanced/phone_control/bin/cloudflared.exe"
        tunnel = tunnel_manager.CloudflareTunnel(
            "stale.exe", popen=popen, verify=lambda _path: trusted)
        result = tunnel.start("http://127.0.0.1:8765")
        self.assertTrue(result["ok"], result)
        self.assertEqual(tunnel.executable, trusted)
        self.assertEqual(popen.calls[0][0][0], trusted)

    def test_verify_managed_cloudflared_rejects_foreign_paths(self):
        trusted = "D:/data/advanced/phone_control/bin/cloudflared.exe"
        with mock.patch.object(component_packages, "cloudflared",
                               lambda root=None: trusted):
            self.assertEqual(
                tunnel_manager.verify_managed_cloudflared(trusted, root="D:/data"), trusted)
            self.assertEqual(
                tunnel_manager.verify_managed_cloudflared(
                    "C:/Program Files/cloudflared/cloudflared.exe", root="D:/data"), "")
        with mock.patch.object(component_packages, "cloudflared",
                               lambda root=None: ""):
            self.assertEqual(
                tunnel_manager.verify_managed_cloudflared(trusted, root="D:/data"), "")


    def test_stop_terminates_waits_and_clears_url(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        result = tunnel.stop()
        self.assertTrue(result["ok"])
        self.assertTrue(popen.proc.terminated)
        self.assertIn(3, popen.proc.waits, "terminate 后必须等待子进程退出")
        self.assertEqual(tunnel.public_url, "")
        self.assertTrue(tunnel.stop()["ok"], "重复关闭应无害")

    def test_hung_child_is_killed_after_terminate_timeout(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"], hang=True)
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        tunnel.stop()
        self.assertTrue(popen.proc.terminated)
        self.assertTrue(popen.proc.killed, "等待超时必须升级到杀进程")

    def test_second_start_while_running_is_rejected(self):
        popen = FakePopen(lines=["INF https://x.trycloudflare.com\n"])
        tunnel = tunnel_manager.CloudflareTunnel("cf.exe", popen=popen)
        self.assertTrue(tunnel.start("http://127.0.0.1:8765")["ok"])
        again = tunnel.start("http://127.0.0.1:8765")
        self.assertFalse(again["ok"])
        self.assertEqual(again["error"], "already_running")

    def test_url_re_matches_only_trycloudflare(self):
        line = "x https://a-b-c.trycloudflare.com y https://a-b-c.trycloudflare.com"
        matches = tunnel_manager.URL_RE.findall(line)
        self.assertEqual(matches, ["https://a-b-c.trycloudflare.com"] * 2)
        self.assertIsNone(tunnel_manager.URL_RE.search(
            "visit https://evil.example.com now"))
        # 伪后缀只会截出真正的 trycloudflare 主机，不把外域当隧道地址
        self.assertEqual(
            tunnel_manager.URL_RE.findall(
                "https://a-b-c.trycloudflare.com.evil.example"),
            ["https://a-b-c.trycloudflare.com"])


class QrPayloadTests(unittest.TestCase):
    """QR 只编码当前公开地址；配对码与任何查询参数都不得进图。"""

    def setUp(self):
        self.captured = []
        outer = self

        class FakeQr:
            def save(self, out, kind="png", scale=5, border=4):
                out.write(b"\x89PNG-fake")

        def fake_make(text, error="m"):
            outer.captured.append(str(text))
            return FakeQr()

        segno = types.ModuleType("segno")
        segno.make = fake_make
        sys.modules["segno"] = segno
        self.addCleanup(lambda: sys.modules.pop("segno", None))

    def test_png_data_uri_encodes_exact_address(self):
        address = "https://neat-random-words.trycloudflare.com"
        uri = phone_qr.png_data_uri(address)
        self.assertTrue(uri.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(uri.split(",", 1)[1]), b"\x89PNG-fake")
        self.assertEqual(self.captured, [address])

    def test_qr_never_carries_pair_code_or_query(self):
        address = "https://neat-random-words.trycloudflare.com"
        phone_qr.png_data_uri(address)
        encoded = self.captured[0]
        self.assertNotIn("?", encoded)
        self.assertNotIn("pair", encoded.lower())
        self.assertNotIn("code", encoded.lower())

    def test_empty_address_short_circuits_without_engine(self):
        self.assertEqual(phone_qr.png_data_uri(""), "")
        self.assertEqual(phone_qr.png_data_uri("   "), "")
        self.assertEqual(self.captured, [])

    def test_missing_segno_degrades_to_empty(self):
        sys.modules["segno"] = None      # import 必抛，与本机安装无关
        self.assertEqual(phone_qr.png_data_uri("https://x.trycloudflare.com"), "")


if __name__ == "__main__":
    unittest.main()
