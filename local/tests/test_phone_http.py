#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机受限 HTTP 适配器测试：真实回环 socket + 替身 Api，全程离线。

只开 127.0.0.1 临时端口；不碰 100.x 监听、不改防火墙、不连学校、不读凭据。

@author Author
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from application.phone_service import PhoneAccessService  # noqa: E402
from domain.phone_rules import (  # noqa: E402
    COOKIE_NAME, CSRF_HEADER, DEVICE_COOKIE_NAME, MAX_BODY_BYTES,
    cookie_header_value,
)
from infrastructure.phone_http import PhoneHttpServer  # noqa: E402


class FakeApi:
    def __init__(self):
        self.calls = []

    def list_activities(self, request_id=""):
        self.calls.append(("list_activities", request_id))
        return {"ok": True, "items": [{"id": "a1"}], "request_id": request_id}

    def check(self, request_id=""):
        self.calls.append(("check", request_id))
        return {"ok": True, "result": "valid"}

    def stop_plan(self, plan_id):
        self.calls.append(("stop_plan", plan_id))
        return {"ok": True}

    def save_prefs(self, prefs):
        self.calls.append(("save_prefs", prefs))
        return {"ok": True}


class MemoryDeviceStore:
    """替身设备信任存储：只在内存里记已配对的设备 token。"""

    def __init__(self):
        self.devices = []
        self.revoked = 0

    def add_device(self, token, now=None):
        self.devices.append(token)
        return True

    def validate_device(self, token, now=None):
        return token in self.devices

    def revoke_all(self):
        self.revoked += 1
        self.devices = []
        return True


class PhoneHttpBase(unittest.TestCase):
    # 子类改为 True 即可测试「固定地址通道」的设备恢复；默认与生产 Cloudflare 一致
    persistent_device = False
    device_store = None

    def setUp(self):
        self.api = FakeApi()
        self.clock = {"now": 5000.0}
        self.ui_dir = Path(tempfile.mkdtemp(prefix="campus-phone-ui-"))
        self.addCleanup(shutil.rmtree, str(self.ui_dir), True)
        (self.ui_dir / "index.html").write_text(
            "<!doctype html><html><body>配对</body></html>", encoding="utf-8")
        (self.ui_dir / "styles.css").write_text("body{}", encoding="utf-8")
        (self.ui_dir / "app.js").write_text("console.log(1);", encoding="utf-8")
        self.raw_state = {"activities": [{"id": "a1", "name": "活动"}],
                          "login": {"session_present": True},
                          "plan": None, "busy": False,
                          "terms": {"accepted_version": "1"},
                          "retry_options": {"default": 120}}
        self.service = PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: self.raw_state,
            device_store=self.device_store,
            server_factory=lambda host, port, svc: PhoneHttpServer(
                host, port, svc, ui_dir=self.ui_dir))
        started = self.service.start("127.0.0.1", 0,
                                     persistent_device=self.persistent_device)
        self.assertTrue(started["ok"], started)
        self.base = started["address"].rstrip("/")
        self.origin = self.base
        self.code = started["pair_code"]
        self.addCleanup(self.service.stop)

    def _request(self, method, path, *, body=None, headers=None, cookie=None):
        url = self.base + path
        data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Host", self.base.split("//", 1)[1])
        merged = dict(headers or {})
        if body is not None:
            merged.setdefault("Content-Type", "application/json")
        if cookie:
            merged["Cookie"] = cookie
        for key, value in merged.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()
        except urllib.error.URLError:
            # 服务已下线：连接被拒本身就是「拒绝」，用 0 表达
            return 0, {}, b""

    def _pair(self, code=None):
        status, headers, body = self._request(
            "POST", "/pair", body={"code": code or self.code},
            headers={"Origin": self.origin})
        payload = json.loads(body.decode("utf-8"))
        cookie = ""
        for key, value in headers.items():
            if key.lower() == "set-cookie" and value.startswith("campus_phone_sid="):
                cookie = value.split(";", 1)[0]
        return status, payload, cookie


class RoundTripTests(PhoneHttpBase):
    def test_pair_state_action_roundtrip(self):
        status, payload, cookie = self._pair()
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(cookie)

        status, _, body = self._request("GET", "/api/state?after=0", cookie=cookie)
        self.assertEqual(status, 200)
        state = json.loads(body.decode("utf-8"))
        self.assertEqual(state["state"]["activities"][0]["id"], "a1")
        self.assertNotIn("help", state["state"])

        status, _, body = self._request(
            "POST", "/api/action",
            body={"action": "check", "args": {"request_id": "r1"}},
            headers={"Origin": self.origin, CSRF_HEADER: payload["csrf"]},
            cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body.decode("utf-8"))["ok"])
        self.assertEqual(self.api.calls, [("check", "r1")])

    def test_static_pages_are_served_from_fixed_table(self):
        status, _, body = self._request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("配对", body.decode("utf-8"))
        status, _, _ = self._request("GET", "/app.js")
        self.assertEqual(status, 200)

    def test_static_brand_icons_are_served(self):
        """PHONE_STATIC 白名单里新增的 favicon.ico 和 apple-touch-icon.png
        必须能取到、Content-Type 正确。"""
        # setUp 只写了 html/css/js 假文件；这里补写假图标再请求，
        # 避免测试依赖真实 design/brand/ 资源（测试应该在任何机器上都能跑）
        (self.ui_dir / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
        (self.ui_dir / "apple-touch-icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        status, headers, body = self._request("GET", "/favicon.ico")
        self.assertEqual(status, 200, "favicon.ico 必须在白名单里")
        ctype = headers.get("Content-Type", headers.get("content-type", ""))
        self.assertIn("image/x-icon", ctype,
                      "favicon Content-Type 应为 image/x-icon，实际 %s" % ctype)
        self.assertEqual(body, b"\x00\x00\x01\x00")

        status, headers, body = self._request("GET", "/apple-touch-icon.png")
        self.assertEqual(status, 200, "apple-touch-icon.png 必须在白名单里")
        ctype = headers.get("Content-Type", headers.get("content-type", ""))
        self.assertIn("image/png", ctype,
                      "apple-touch-icon Content-Type 应为 image/png，实际 %s" % ctype)
        self.assertEqual(body, b"\x89PNG\r\n\x1a\n")

    def test_static_icon_paths_still_block_traversal(self):
        """白名单只放开 /favicon.ico 和 /apple-touch-icon.png 两个精确路径，
        目录穿越或变体路径仍应拒绝（不因为多了两个条目就放松安全边界）。"""
        for path in ("/favicon.ico/secret", "/../favicon.ico",
                     "/apple-touch-icon.png%00.png", "/FAVICON.ICO"):
            with self.subTest(path=path):
                status, _, _ = self._request("GET", path)
                self.assertIn(status, (403, 404),
                              "白名单变体路径 %s 必须被拒（got %d）" % (path, status))

    def test_state_carries_no_school_traffic(self):
        _, _, cookie = self._pair()
        self.api.calls.clear()
        self._request("GET", "/api/state?after=0", cookie=cookie)
        self.assertEqual(self.api.calls, [], "GET state 不得触发任何 Api 动作")


class RejectionTests(PhoneHttpBase):
    def test_state_without_cookie_is_401(self):
        status, _, _ = self._request("GET", "/api/state")
        self.assertEqual(status, 401)

    def test_bad_host_is_rejected(self):
        url = self.base + "/api/state"
        req = urllib.request.Request(url)
        req.add_header("Host", "evil.example")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        self.assertIn(status, (400, 403), "伪 Host 必须被拒，不得回 200")

    def test_post_without_origin_is_rejected(self):
        status, _, body = self._request("POST", "/pair", body={"code": self.code})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body.decode("utf-8"))["error"], "bad_origin")

    def test_post_with_foreign_origin_is_rejected(self):
        status, _, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body.decode("utf-8"))["error"], "bad_origin")

    def test_action_without_csrf_is_rejected(self):
        _, payload, cookie = self._pair()
        status, _, body = self._request(
            "POST", "/api/action", body={"action": "check", "args": {}},
            headers={"Origin": self.origin}, cookie=cookie)
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body.decode("utf-8"))["error"], "bad_csrf")

    def test_action_with_wrong_csrf_is_rejected(self):
        _, _, cookie = self._pair()
        status, _, body = self._request(
            "POST", "/api/action", body={"action": "check", "args": {}},
            headers={"Origin": self.origin, CSRF_HEADER: "wrong"}, cookie=cookie)
        self.assertEqual(status, 403)

    def test_illegal_methods_are_rejected(self):
        for method in ("PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            with self.subTest(method=method):
                status, _, _ = self._request(method, "/api/action",
                                             body={"action": "check", "args": {}})
                self.assertIn(status, (400, 403, 405))

    def test_directory_traversal_and_unknown_routes_404(self):
        for path in ("/../app.py", "/..%2f..%2fapp.py", "/secret.txt",
                     "/api/../session.json", "/ui/index.html"):
            with self.subTest(path=path):
                status, _, _ = self._request("GET", path)
                self.assertIn(status, (400, 403, 404))

    def test_oversized_body_is_rejected(self):
        huge = b'{"action":"check","args":{"request_id":"' + b"a" * (MAX_BODY_BYTES + 100) + b'"}}'
        _, payload, cookie = self._pair()
        status, _, body = self._request(
            "POST", "/api/action", body=huge,
            headers={"Origin": self.origin, CSRF_HEADER: payload["csrf"]},
            cookie=cookie)
        self.assertIn(status, (400, 403))
        self.assertIn(json.loads(body.decode("utf-8"))["error"],
                      ("body_too_large", "bad_json"))

    def test_bad_json_and_bad_utf8_are_rejected(self):
        _, payload, cookie = self._pair()
        for raw in (b"\xff\xfe\x00", b"not-json", b"[1,2,3]", b'{"a":NaN}'):
            with self.subTest(raw=raw):
                status, _, _ = self._request(
                    "POST", "/api/action", body=raw,
                    headers={"Origin": self.origin, CSRF_HEADER: payload["csrf"]},
                    cookie=cookie)
                self.assertIn(status, (400, 403))

    def test_forbidden_actions_are_not_reflected(self):
        _, payload, cookie = self._pair()
        for action in ("shutdown", "open_data", "update", "check_update",
                       "save_prefs", "bootstrap", "login"):
            with self.subTest(action=action):
                status, _, body = self._request(
                    "POST", "/api/action",
                    body={"action": action, "args": {}},
                    headers={"Origin": self.origin, CSRF_HEADER: payload["csrf"]},
                    cookie=cookie)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body.decode("utf-8"))["error"],
                                 "action_not_allowed")
        self.assertEqual(self.api.calls, [], "禁止动作不得触达 Api")

    def test_cookies_after_stop_are_rejected(self):
        _, _, cookie = self._pair()
        self.service.stop()
        status, _, _ = self._request("GET", "/api/state", cookie=cookie)
        # 0 = 连接被拒（服务已下线）；即便端口还在也必须 401/403
        self.assertIn(status, (0, 401, 403))


class HeaderSafetyTests(PhoneHttpBase):
    def test_security_headers_on_static_and_api(self):
        for path in ("/", "/api/state"):
            with self.subTest(path=path):
                status, headers, _ = self._request("GET", path)
                lowered = {k.lower(): v for k, v in headers.items()}
                self.assertIn("content-security-policy", lowered)
                self.assertEqual(lowered.get("x-content-type-options"), "nosniff")
                self.assertEqual(lowered.get("cache-control"), "no-store")

    def test_pair_sets_httponly_strict_cookie_without_secure(self):
        status, headers, _ = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": self.origin})
        self.assertEqual(status, 200)
        cookies = [v for k, v in headers.items()
                   if k.lower() == "set-cookie"]
        session_cookie = next(v for v in cookies if v.startswith("campus_phone_sid="))
        self.assertIn("HttpOnly", session_cookie)
        self.assertIn("SameSite=Strict", session_cookie)
        self.assertIn("Path=/", session_cookie)
        self.assertNotIn("Secure", session_cookie)


class PublicHostSwitchTests(unittest.TestCase):
    """Cloudflare 场景：socket 在回环，Host/Origin 必须切到隧道公网域名。"""

    PUBLIC_HOST = "neat-words.trycloudflare.com"
    PUBLIC = "https://neat-words.trycloudflare.com"

    def setUp(self):
        self.api = FakeApi()
        self.clock = {"now": 5000.0}
        self.ui_dir = Path(tempfile.mkdtemp(prefix="campus-phone-ui-"))
        self.addCleanup(shutil.rmtree, str(self.ui_dir), True)
        for name, text in (("index.html", "<html>配对</html>"),
                           ("styles.css", "body{}"), ("app.js", ";")):
            (self.ui_dir / name).write_text(text, encoding="utf-8")
        self.raw_state = {"activities": [], "login": {"session_present": True},
                          "plan": None, "busy": False,
                          "terms": {"accepted_version": "1"},
                          "retry_options": {"default": 120}}
        self.servers = []

        def factory(host, port, svc, public_host="", public_scheme="http"):
            server = PhoneHttpServer(
                host, port, svc, ui_dir=self.ui_dir,
                public_host=public_host, public_scheme=public_scheme)
            self.servers.append(server)
            return server

        self.service = PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: self.raw_state, server_factory=factory)
        started = self.service.start(
            "127.0.0.1", 0, public_host=self.PUBLIC_HOST,
            public_scheme="https")
        self.assertTrue(started["ok"], started)
        self.code = started["pair_code"]
        port = self.servers[0]._httpd.server_address[1]
        self.local_base = "http://127.0.0.1:%d" % port
        self.addCleanup(self.service.stop)

    def _request(self, method, path, *, body=None, headers=None, cookie=None,
                 host=None):
        req = urllib.request.Request(self.local_base + path,
                                     data=json.dumps(body).encode("utf-8")
                                     if body is not None else None,
                                     method=method)
        req.add_header("Host", host or self.PUBLIC_HOST)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        if cookie:
            req.add_header("Cookie", cookie)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_pair_over_public_host_requires_https_origin(self):
        status, _, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": self.PUBLIC})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        status, _, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": "http://" + self.PUBLIC_HOST})
        self.assertEqual(status, 403, "https 隧道必须拒 http Origin")
        self.assertEqual(json.loads(body)["error"], "bad_origin")

    def test_stale_local_host_is_rejected_after_switch(self):
        status, _, _ = self._request("GET", "/", host="127.0.0.1")
        self.assertIn(status, (400, 403),
                      "切到公网域名后不得再认本机 Host")

    def test_bare_host_without_port_is_accepted(self):
        status, _, _ = self._request("GET", "/")
        self.assertEqual(status, 200)

    def test_state_action_roundtrip_with_public_origin(self):
        status, headers, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": self.PUBLIC})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        cookie = next(v for k, v in headers.items()
                      if k.lower() == "set-cookie"
                      and v.startswith("campus_phone_sid=")).split(";", 1)[0]
        status, _, body = self._request("GET", "/api/state?after=0", cookie=cookie)
        self.assertEqual(status, 200)
        status, _, _ = self._request(
            "POST", "/api/action",
            body={"action": "check", "args": {"request_id": "r1"}},
            headers={"Origin": self.PUBLIC, CSRF_HEADER: payload["csrf"]},
            cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual([c[0] for c in self.api.calls], ["check"])

class DeviceRestoreHttpTests(PhoneHttpBase):
    """固定地址通道（Tailscale）：重新打开工具后靠设备 cookie 直接恢复。"""

    persistent_device = True

    def setUp(self):
        self.device_store = MemoryDeviceStore()
        super().setUp()

    def _pair_with_cookies(self):
        url = self.base + "/pair"
        body = json.dumps({"code": self.code}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Host", self.base.split("//", 1)[1])
        req.add_header("Origin", self.origin)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            cookies = list(resp.headers.get_all("Set-Cookie") or [])
            payload = json.loads(resp.read().decode("utf-8"))
        return payload, cookies

    def test_pair_writes_device_cookie(self):
        _payload, cookies = self._pair_with_cookies()
        names = [cookie.split("=", 1)[0] for cookie in cookies]
        self.assertIn(DEVICE_COOKIE_NAME, names)
        self.assertIn(COOKIE_NAME, names)
        self.assertEqual(len(self.device_store.devices), 1, "配对成功登记一条设备令牌")

    def test_state_restores_session_from_device_cookie_only(self):
        _payload, cookies = self._pair_with_cookies()
        device = next(cookie for cookie in cookies
                      if cookie.startswith(DEVICE_COOKIE_NAME + "="))
        status, _headers, body = self._request(
            "GET", "/api/state?after=0", cookie=device.split(";", 1)[0])
        self.assertEqual(status, 200, "配对过的设备重启服务后应直接读到状态")
        state = json.loads(body.decode("utf-8"))
        self.assertEqual(state["state"]["activities"][0]["id"], "a1")

    def test_forged_device_cookie_is_401(self):
        self._pair_with_cookies()
        status, _headers, _body = self._request(
            "GET", "/api/state", cookie="%s=deadbeefdeadbeef" % DEVICE_COOKIE_NAME)
        self.assertEqual(status, 401)


class DeviceRestoreOffHttpTests(PhoneHttpBase):
    """Cloudflare 通道：没有设备 cookie，永远回配对页。"""

    def test_pair_writes_no_device_cookie(self):
        status, headers, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": self.origin})
        self.assertEqual(status, 200)
        self.assertIn("ok", json.loads(body.decode("utf-8")))
        self.assertNotIn(DEVICE_COOKIE_NAME, "".join(headers.values()),
                         "Cloudflare 通道不得签发设备 cookie")

    def test_device_cookie_alone_cannot_restore(self):
        status, _headers, _body = self._request(
            "GET", "/api/state", cookie="%s=anything" % DEVICE_COOKIE_NAME)
        self.assertEqual(status, 401, "域名会变，设备 cookie 一律不认")


class BackupHostTests(unittest.TestCase):
    """Tailscale 直连：MagicDNS 名与 100.x 备用地址都要能过 Host/Origin 校验。"""

    PUBLIC_HOST = "pc.tail1234.ts.net"

    def setUp(self):
        self.api = FakeApi()
        self.clock = {"now": 9000.0}
        self.ui_dir = Path(tempfile.mkdtemp(prefix="campus-phone-ui-"))
        self.addCleanup(shutil.rmtree, str(self.ui_dir), True)
        for name, text in (("index.html", "<html>配对</html>"),
                           ("styles.css", "body{}"), ("app.js", ";")):
            (self.ui_dir / name).write_text(text, encoding="utf-8")
        self.raw_state = {"activities": [], "login": {"session_present": True},
                          "plan": None, "busy": False,
                          "terms": {"accepted_version": "1"},
                          "retry_options": {"default": 120}}
        self.servers = []

        def factory(host, port, svc, public_host="", public_scheme="http"):
            server = PhoneHttpServer(
                host, port, svc, ui_dir=self.ui_dir,
                public_host=public_host, public_scheme=public_scheme)
            self.servers.append(server)
            return server

        self.service = PhoneAccessService(
            api=self.api, now=lambda: self.clock["now"],
            state_of=lambda: self.raw_state, server_factory=factory)
        started = self.service.start("127.0.0.1", 0, public_host=self.PUBLIC_HOST)
        self.assertTrue(started["ok"], started)
        self.code = started["pair_code"]
        port = self.servers[0]._httpd.server_address[1]
        self.local_base = "http://127.0.0.1:%d" % port
        self.backup_host = "127.0.0.1:%d" % port
        self.addCleanup(self.service.stop)

    def _request(self, method, path, *, body=None, headers=None, host=None):
        req = urllib.request.Request(
            self.local_base + path,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            method=method)
        req.add_header("Host", host or self.PUBLIC_HOST)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        for key, value in (headers or {}).items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def test_bind_address_is_accepted_as_host(self):
        status, _, body = self._request(
            "GET", "/api/state", host=self.backup_host)
        self.assertEqual(status, 401, "备用地址要走到会话校验，而不是被判成 bad_host")
        self.assertEqual(json.loads(body)["error"], "need_pair")

    def test_backup_origin_can_pair(self):
        status, _, body = self._request(
            "POST", "/pair", body={"code": self.code},
            headers={"Origin": "http://" + self.backup_host})
        self.assertEqual(status, 200, body[:120])
        self.assertTrue(json.loads(body)["ok"])

    def test_foreign_host_still_rejected(self):
        status, _, _ = self._request(
            "GET", "/api/state", host="evil.example")
        self.assertIn(status, (400, 403), "白名单之外的主机名仍必须拒绝")
