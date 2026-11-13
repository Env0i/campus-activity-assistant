# -*- coding: utf-8 -*-
"""依赖锁定契约：pywebview 及其依赖必须精确锁版本。

产品靠 pywebview 把本地页面经本机回环地址供出，这个行为随版本变，所以连同
它的依赖一起锁定。本文件核对两处：local/requirements.txt 与
local/build/make_portable.py 的 PIP_PACKAGES 必须给出同样的精确版本。
make_portable.py 用 ast 读取，不 import，避免触发构建脚本的副作用。
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

LOCAL_DIR = Path(__file__).resolve().parents[1]
REQUIREMENTS = LOCAL_DIR / "requirements.txt"
MAKE_PORTABLE = LOCAL_DIR / "build" / "make_portable.py"

# 需要精确锁定的包（包名 → 版本）
PINNED = {
    "pywebview": "6.2.1",
    "bottle": "0.13.4",
    "proxy-tools": "0.1.0",
    "pythonnet": "3.2.1",
    "clr-loader": "0.3.1",
}

_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([^\s;#]+)")


def _parse_requirement(spec: str):
    """把一行依赖写法拆成 (包名, 版本)；不是精确版本写法则返回 None。"""
    m = _LINE_RE.match(spec.split(";", 1)[0])
    if not m:
        return None
    return m.group(1).lower(), m.group(2)


def _requirement_pins() -> dict[str, list[str]]:
    """读 requirements.txt，返回 包名 → 出现过的精确版本列表。"""
    found: dict[str, list[str]] = {}
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parsed = _parse_requirement(line)
        if parsed:
            found.setdefault(parsed[0], []).append(parsed[1])
    return found


def _portable_packages() -> list[str]:
    """用 ast 从 make_portable.py 取出 PIP_PACKAGES 字面量列表。"""
    tree = ast.parse(MAKE_PORTABLE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PIP_PACKAGES" for t in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise AssertionError("make_portable.py 里找不到 PIP_PACKAGES")


class RequirementsPinTests(unittest.TestCase):
    """requirements.txt 对五个包各有且只有一行精确版本。"""

    def test_each_pinned_package_has_exactly_one_exact_line(self):
        pins = _requirement_pins()
        for name, version in PINNED.items():
            with self.subTest(package=name):
                self.assertIn(name, pins, f"{name} 缺少精确版本行")
                self.assertEqual(len(pins[name]), 1, f"{name} 出现多行: {pins[name]}")
                self.assertEqual(pins[name][0], version)

    def test_no_loose_pywebview_requirement_left(self):
        text = REQUIREMENTS.read_text(encoding="utf-8")
        self.assertNotIn("pywebview>=", text)


class PortablePinTests(unittest.TestCase):
    """make_portable.py 的 PIP_PACKAGES 与 requirements.txt 保持一致。"""

    def test_pip_packages_pins_match_requirements(self):
        packages = _portable_packages()
        parsed = {}
        for spec in packages:
            p = _parse_requirement(spec)
            if p:
                parsed[p[0]] = p[1]
        for name, version in PINNED.items():
            with self.subTest(package=name):
                self.assertEqual(parsed.get(name), version,
                                 f"PIP_PACKAGES 里 {name} 的版本与锁定不一致")

    def test_pip_packages_has_no_loose_pywebview(self):
        self.assertNotIn("pywebview>=5.0", _portable_packages())


if __name__ == "__main__":
    unittest.main()
