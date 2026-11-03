# -*- coding: utf-8 -*-
"""站点地址来源优先级：环境变量 → 程序旁 config.json → 构建时内置的 _site_build。

隔离做法：把 local/site_target.py 复制到临时目录再导入，`_here()` 落在临时目录，
真实 local/config.json 既不读也不碰；`_site_build` 用内存 stub 注入。
假地址一律用 example.invalid，不写死盘符、不写真实域名。
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
ENV_BASE = "https://env.example.invalid"
CONFIG_BASE = "https://config.example.invalid"
BUILD_BASE = "https://build.example.invalid"


def _load(env_origin=None, config_base=None, build_base=None):
    """复制 site_target.py 到临时目录后导入，返回隔离模块（常量已按来源算好）。"""
    directory = tempfile.TemporaryDirectory(prefix="campus-site-target-")
    here = Path(directory.name)
    (here / "site_target.py").write_text(
        (LOCAL / "site_target.py").read_text(encoding="utf-8"), encoding="utf-8")
    if config_base is not None:
        (here / "config.json").write_text(
            json.dumps({"site": {"base": config_base}}, ensure_ascii=False),
            encoding="utf-8")
    env = dict(os.environ)
    env.pop("SCHOOL_ORIGIN", None)
    if env_origin is not None:
        env["SCHOOL_ORIGIN"] = env_origin
    saved_build = sys.modules.pop("_site_build", None)
    if build_base is not None:
        stub = types.ModuleType("_site_build")
        stub.BUILD_BASE = build_base
        sys.modules["_site_build"] = stub
    try:
        with mock.patch.dict(os.environ, env, clear=True):
            spec = importlib.util.spec_from_file_location(
                "site_target_isolated", here / "site_target.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    finally:
        sys.modules.pop("_site_build", None)
        if saved_build is not None:
            sys.modules["_site_build"] = saved_build
        directory.cleanup()
    return module


class SiteTargetSourceTests(unittest.TestCase):
    def test_env_wins_over_config_and_build(self):
        """SCHOOL_ORIGIN 优先级最高：同时有配置文件和构建内置值时也取环境变量。"""
        module = _load(env_origin=ENV_BASE, config_base=CONFIG_BASE, build_base=BUILD_BASE)
        self.assertEqual(module.BASE_URL, ENV_BASE)
        self.assertTrue(module.CONFIGURED, "环境变量配好即视为已配置")

    def test_config_wins_over_build(self):
        """没有环境变量时，程序旁 config.json 优先于构建时内置值。"""
        module = _load(config_base=CONFIG_BASE, build_base=BUILD_BASE)
        self.assertEqual(module.BASE_URL, CONFIG_BASE)
        self.assertTrue(module.CONFIGURED)

    def test_build_value_used_when_env_and_config_absent(self):
        """发布版：环境变量与 config.json 都没有时用打包内置的 BUILD_BASE。"""
        module = _load(build_base=BUILD_BASE)
        self.assertEqual(module.BASE_URL, BUILD_BASE)
        self.assertTrue(module.CONFIGURED)

    def test_nothing_configured_falls_back_to_placeholder(self):
        """三种来源都缺失：占位地址 + CONFIGURED=False（学校动作会被拒绝）。"""
        module = _load()
        self.assertEqual(module.BASE_URL, module.PLACEHOLDER)
        self.assertFalse(module.CONFIGURED)

    def test_trailing_slash_is_trimmed(self):
        """站点根地址去掉结尾斜杠，拼接端点路径时不会出现双斜杠。"""
        module = _load(env_origin=ENV_BASE + "/")
        self.assertEqual(module.BASE_URL, ENV_BASE)


if __name__ == "__main__":
    unittest.main()
