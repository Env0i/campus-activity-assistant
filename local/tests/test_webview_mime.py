#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚本类型头登记的守卫：pywebview 本地服务的脚本类型头来自标准库 mimetypes，而
mimetypes 在 Windows 上会读注册表——有的电脑把 .js 记成 text/plain（装过某些软件之后
会出现）。普通脚本不在乎类型头，模块脚本严格要求 JavaScript 类型，类型不对时整张
模块图都不加载，界面停在兜底提示上，重装也没用；宿主机的注册表是正常的，验不出这个
问题，只能靠这里的模拟加断言守住。三条用例都用 add_type 把 .js 模拟成 text/plain，
断言登记函数（与 infrastructure 包导入时的登记）把它压回 text/javascript；
每条用例收尾在 addCleanup 里把 mimetypes 重新初始化，模拟不外溢。"""
from __future__ import annotations

import importlib
import mimetypes
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL  # noqa: E402

SIMULATED = ("text/plain", None)
REGISTERED = ("text/javascript", None)


def _restore_mimetypes():
    """把 mimetypes 的映射恢复到本进程初始状态，模拟不带到别的测试。"""
    mimetypes.init()


class WebViewMimeTests(unittest.TestCase):
    """模拟注册表把 .js 记成 text/plain 之后，登记给出的仍是 text/javascript。"""

    def setUp(self):
        self.addCleanup(_restore_mimetypes)

    def test_register_script_types_overrides_simulated_registry(self):
        """模拟注册表生效后，register_script_types() 把 .js 压回 text/javascript。"""
        from local.infrastructure.webview_mime import register_script_types
        mimetypes.add_type("text/plain", ".js")
        self.assertEqual(mimetypes.guess_type("main.js"), SIMULATED,
                         "模拟没有生效（guess_type 仍是原值），这条测试没有牙")
        register_script_types()
        self.assertEqual(mimetypes.guess_type("main.js"), REGISTERED,
                         "登记之后 .js 必须是 text/javascript")

    def test_package_import_registers_script_types(self):
        """infrastructure 包导入时的那次登记同样压得过模拟的注册表。"""
        mimetypes.add_type("text/plain", ".js")
        import local.infrastructure as infra
        importlib.reload(infra)          # 重新执行包初始化，导入处的登记再跑一遍
        self.assertEqual(mimetypes.guess_type("main.js"), REGISTERED,
                         "infrastructure 包导入时必须登记 .js 的脚本类型")

    def test_bottle_static_file_serves_javascript_type(self):
        """pywebview 自带服务用 bottle.static_file 供脚本：模拟注册表后类型头仍以
        text/javascript 开头。没装 bottle 时跳过并说明，其余两条照常跑。"""
        try:
            import bottle
        except ImportError:
            self.skipTest("本机没装 bottle：静态文件类型头这条跳过，其余两条照常跑")
        mimetypes.add_type("text/plain", ".js")
        from local.infrastructure.webview_mime import register_script_types
        register_script_types()
        response = bottle.static_file("main.js", root=str(LOCAL / "ui"))
        content_type = response.headers.get("Content-Type") or response.content_type
        self.assertTrue(content_type.startswith("text/javascript"),
                        "bottle.static_file 给 main.js 的类型头必须以 text/javascript 开头，"
                        "实际是 %r" % (content_type,))


if __name__ == "__main__":
    unittest.main()
