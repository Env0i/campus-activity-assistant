# -*- coding: utf-8 -*-
"""网络策略：学校接口直连，更新与组件下载跟随系统代理。

只用替身 opener 与源码静态检查，不发任何真实请求。

@author Author
"""
from __future__ import annotations

import sys
import types
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

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
        source = (LOCAL / "grab.py").read_text(encoding="utf-8")
        self.assertNotIn("install_opener", source)


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
