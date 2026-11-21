# -*- coding: utf-8 -*-
"""网络策略：学校接口直连，更新与组件下载跟随系统代理。

只用替身 opener 与源码静态检查，不发任何真实请求。

@author Author
"""
from __future__ import annotations

import io
import sys
import types
import unittest
import urllib.request
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

import grab  # noqa: E402


class DirectOpenerShapeTests(unittest.TestCase):
    """学校请求用「空 ProxyHandler」现建 opener；更新/下载保持默认 opener。"""

    def test_school_open_builds_a_direct_opener(self):
        seen = {}

        class _Response:
            def close(self):
                pass

        class _Opener:
            def open(self, request, timeout=None):
                seen["opened"] = (request, timeout)
                return _Response()

        def _build_opener(handler):
            seen["handler"] = handler
            return _Opener()

        class _ProxyHandler:
            def __init__(self, proxies):
                seen["proxies"] = proxies

        fake = types.SimpleNamespace(
            request=types.SimpleNamespace(Request=object, build_opener=_build_opener,
                                          ProxyHandler=_ProxyHandler))
        with mock.patch.object(grab, "urllib", fake):
            grab._school_open("REQ", timeout=7)
        self.assertEqual(seen["proxies"], {}, "必须显式给空代理表才表示直连")
        self.assertEqual(seen["opened"], ("REQ", 7))

    def test_school_open_falls_back_to_urlopen_for_test_doubles(self):
        """替身 urllib 没有 build_opener 时退回 urlopen——否则所有既有测试替身都会崩。"""
        called = {}

        def _urlopen(request, timeout=None):
            called["hit"] = (request, timeout)
            return "resp"

        fake = types.SimpleNamespace(request=types.SimpleNamespace(Request=object,
                                                                  urlopen=_urlopen))
        with mock.patch.object(grab, "urllib", fake):
            self.assertEqual(grab._school_open("REQ", timeout=3), "resp")
        self.assertEqual(called["hit"], ("REQ", 3))

    def test_installing_global_opener_is_not_used(self):
        """绝不 install_opener：那会把桌面进程里所有 urllib 请求一起改掉。"""
        grab_source = (LOCAL / "grab.py").read_text(encoding="utf-8")
        school_http_source = (LOCAL / "infrastructure" / "school_http.py").read_text(encoding="utf-8")
        self.assertIn("ProxyHandler", school_http_source)
        self.assertNotIn("install_opener", grab_source + "\n" + school_http_source)


class SchoolRequestUsesDirectOpenerTests(unittest.TestCase):
    """学校请求必须走 _SCHOOL_OPENER，而不是模块级 urlopen。"""

    def setUp(self):
        self.calls = []

        class _Response:
            def __init__(self, raw):
                self._raw = raw
                self.headers = {}

            def read(self):
                return self._raw

            def close(self):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def _open(request, timeout=None):
            self.calls.append({"url": request.full_url, "timeout": timeout})
            return _Response(b'{"code":1,"data":{"id":"x"}}')

        patch = mock.patch.object(grab, "_school_open", _open)
        patch.start()
        self.addCleanup(patch.stop)

    def test_get_request_goes_through_direct_opener(self):
        grab._get("/stu/activity/available", tok="t")
        self.assertTrue(self.calls, "学校 GET 必须走直连 opener")
        self.assertIn("/stu/activity/available", self.calls[0]["url"])

    def test_post_request_goes_through_direct_opener(self):
        grab._post("/stu/activity/signup", {"activity_id": "x"}, tok="t")
        self.assertTrue(self.calls, "学校 POST 必须走直连 opener")


class SchoolRequestContractTests(unittest.TestCase):
    """学校请求层的请求头与错误回包解析契约。"""

    def setUp(self):
        self.requests = []

        class _Response:
            def __init__(self, raw=b'{"code":1,"data":{}}'):
                self._raw = raw
                self.headers = {}

            def read(self):
                return self._raw

            def close(self):
                pass

        def _open(request, timeout=None):
            self.requests.append(request)
            return _Response()

        patch = mock.patch.object(grab, "_school_open", _open)
        patch.start()
        self.addCleanup(patch.stop)

    def test_get_request_attaches_explicit_or_saved_token_header(self):
        """详情与取消报名 GET 请求必须携带登录 token 头，否则学校接口会当成未登录拒绝。"""
        grab._get("/rjyHd/getInfo/act-1", tok="tok-a")
        with mock.patch.object(grab, "token", lambda: "tok-saved"):
            grab._get("/rjyHd/getInfo/act-2")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0].get_method(), "GET")
        self.assertEqual(self.requests[0].get_header("Token"), "tok-a")
        self.assertEqual(self.requests[1].get_method(), "GET")
        self.assertEqual(self.requests[1].get_header("Token"), "tok-saved")

    def test_post_request_omits_token_header_when_token_is_empty(self):
        """未登录或空 token 发 POST 时不加空 token 头，避免网关把请求当成坏凭据拦截。"""
        grab._post("/rjyHd/listActivity", {}, tok="")
        grab._post("/rjyHd/listActivity", {}, tok="tok-a")
        self.assertEqual(len(self.requests), 2)
        self.assertIsNone(self.requests[0].get_header("Token"))
        self.assertNotIn("Token", self.requests[0].headers)
        self.assertEqual(self.requests[1].get_header("Token"), "tok-a")

    def test_post_request_decodes_json_body_on_http_error_and_falls_back_on_non_json(self):
        """学校以 HTTP 错误状态返回 4001 JSON 时照常解析给调用方识别登录失效，非 JSON 则退回 HTTPError。"""
        bodies = [
            b'{"code":4001,"msg":"login expired"}',
            b"<html>bad gateway</html>",
        ]

        def _open_error(request, timeout=None):
            raw = bodies.pop(0)
            raise HTTPError(
                request.full_url, 401, "Unauthorized", {}, io.BytesIO(raw)
            )

        with mock.patch.object(grab, "_school_open", _open_error):
            expired = grab._post("/rjyHd/listActivity", {}, tok="tok-a")
            fallback = grab._post("/rjyHd/listActivity", {}, tok="tok-a")
        self.assertEqual(expired, {"code": 4001, "msg": "login expired"})
        self.assertEqual(expired["code"], 4001)
        self.assertEqual(fallback, {"code": -1, "message": "HTTPError"})

    def test_post_request_generates_distinct_32_char_lower_hex_nonce_headers(self):
        """每次 POST 生成不同的 32 位小写十六进制 X-Nonce 头，满足学校网关防重放签名校验。"""
        grab._post("/rjyHd/listActivity", {}, tok="tok-a")
        grab._post("/rjyHd/listActivity", {}, tok="tok-a")
        self.assertEqual(len(self.requests), 2)
        first = self.requests[0].get_header("X-nonce")
        second = self.requests[1].get_header("X-nonce")
        self.assertRegex(first or "", r"^[0-9a-f]{32}$")
        self.assertRegex(second or "", r"^[0-9a-f]{32}$")
        self.assertNotEqual(first, second)


class DefaultOpenerKeepsProxyTests(unittest.TestCase):
    """更新与下载仍用 urllib 默认 opener：家用网络下没有代理配置就直连。"""

    def test_update_and_download_do_not_pin_a_proxy(self):
        for name in ("update_check.py", "updater.py"):
            source = (LOCAL / name).read_text(encoding="utf-8")
            self.assertNotIn("ProxyHandler", source, "%s 不应自己决定代理" % name)
            self.assertIn("urlopen(", source, "%s 仍走默认 opener" % name)

    def test_release_tool_does_not_hardcode_a_local_proxy(self):
        source = (LOCAL.parent / "tools" / "release.py").read_text(encoding="utf-8")
        self.assertNotIn("127.0.0.1:7897", source, "发布脚本不能写死别人的代理端口")
        self.assertNotIn("HTTPS_PROXY=PROXY", source)
