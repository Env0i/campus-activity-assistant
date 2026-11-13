#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""代码形状守卫的薄测试：跑 tools/code_shape/check.py 的只读比对，四类对象各一条用例。

测试只读，不生成也不收紧名单；名单由命令行显式 `--init` / `--tighten` 维护。
上限与量法见 tools/code_shape/README.md。

"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL  # noqa: E402

CHECK = LOCAL.parent / "tools" / "code_shape" / "check.py"


def load_check_module():
    """把 check.py 当模块加载，用以单测量法本身（不读 git、不写名单）。"""
    spec = importlib.util.spec_from_file_location("code_shape_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_check() -> tuple[int, dict]:
    """跑只读比对并返回退出码与 --json 解析结果；stdout 为空视为检查没跑起来。"""
    proc = subprocess.run([sys.executable, "-B", "-X", "utf8", str(CHECK), "--json"],
                          cwd=str(LOCAL.parent), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if not proc.stdout.strip():
        raise AssertionError("check.py 没有输出 JSON；stderr：%s" % proc.stderr)
    return proc.returncode, json.loads(proc.stdout)


class ShapeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rc, cls.data = run_check()
        cls.violations = cls.data.get("violations", [])

    def test_check_reports_counts(self):
        """检查本身要正常结束：退出码 0、带 counts，不能静默崩掉后靠空列表过关。"""
        self.assertEqual(0, self.rc, "check.py 退出码非 0")
        self.assertIn("counts", self.data)
        self.assertIn("files_over800", self.data["counts"])

    def _kinds(self, kind: str) -> list[dict]:
        return [v for v in self.violations if v["kind"] == kind]

    def _assert_kind(self, kind: str) -> list[dict]:
        bad = self._kinds(kind)
        self.assertEqual(bad, [], "%s 类超限：\n%s" % (
            kind, "\n".join("%s = %d（上限 %d）" % (v["name"], v["value"], v["limit"])
                            for v in bad)))
        return bad

    def test_product_files_stay_within_limit(self):
        """不在名单里的产品文件不超过 500 行。"""
        self._assert_kind("file")

    def test_product_functions_stay_within_limit(self):
        """产品函数不超过 60 行；没有 node 时先查 Python 部分，再跳过 JS 部分并说明。"""
        py_only = [v for v in self._kinds("function")
                   if not v["file"].endswith((".js", ".mjs"))]
        self.assertEqual(py_only, [], "Python 函数超限：\n%s" % "\n".join(
            "%s = %d（上限 %d）" % (v["name"], v["value"], v["limit"]) for v in py_only))
        if shutil.which("node") is None or self.data.get("js_skipped"):
            self.skipTest("没有 node：跳过 JS 函数行数检查，Python 部分已在本用例里查过")
        self._assert_kind("function")

    def test_test_functions_stay_within_limit(self):
        """测试文件里 test_ 开头的函数不超过 60 行。"""
        self._assert_kind("test_function")

    def test_class_attributes_stay_within_limit(self):
        """在三个以上方法里赋值的实例属性不超过 5 个。"""
        self._assert_kind("class_attrs")


class ClassAttrMeasurementTests(unittest.TestCase):
    """D5 的量法：只算 self.x 的 =、+=、带注解赋值；容器内修改与 self.x.y 都不算。"""

    @staticmethod
    def _attrs(source: str) -> list[str]:
        rows = load_check_module().class_attr_counts("x.py", source)
        return rows[0]["attrs"]

    def test_container_mutation_is_not_an_attribute_assignment(self):
        src = """
class Box:
    def a(self):
        self.hits = {}
        self.hits['k'] = 1
    def b(self):
        self.hits['k'] = 2
    def c(self):
        self.hits['k'] = 3
"""
        self.assertEqual([], self._attrs(src))

    def test_attribute_on_other_object_is_not_an_assignment(self):
        src = """
class Box:
    def a(self):
        self.dep.value = 1
    def b(self):
        self.dep.value = 2
    def c(self):
        self.dep.value = 3
"""
        self.assertEqual([], self._attrs(src))

    def test_plain_attribute_in_three_methods_counts(self):
        src = """
class Box:
    def a(self):
        self.state = 1
    def b(self):
        self.state += 1
    def c(self):
        self.state: int = 3
"""
        self.assertEqual(["state"], self._attrs(src))


class TightenRuleTests(unittest.TestCase):
    """--tighten 的判定：变长与新增拒绝，变小与换档放行。"""

    @staticmethod
    def _tighten(baseline: dict, data: dict) -> tuple[dict, list[str]]:
        return load_check_module().tighten(baseline, data)

    def _baseline(self) -> dict:
        return {"files": {"over800": {"big.py": {"value": 850, "reason": "拆"}},
                          "over500": {"mid.py": {"value": 600}}},
                "functions": {"over100": {"big.py::f": {"value": 150, "reason": "拆"}},
                              "over60": {}},
                "test_functions": {}, "classes": {}}

    @staticmethod
    def _data(files: dict, functions: list) -> dict:
        return {"files": files, "functions": functions, "test_functions": [],
                "classes": [], "js_skipped": ""}

    def test_shrink_across_tier_moves_entry_instead_of_rejecting(self):
        """850→700、150→90 只是从甲档降到乙档，不能被判成新超限项。"""
        rows = [{"file": "big.py", "name": "f", "qual": "f",
                 "lines": 90, "kind": "function", "start": 1}]
        out, problems = self._tighten(self._baseline(), self._data({"big.py": 700}, rows))
        self.assertEqual([], problems)
        self.assertEqual({}, out["files"]["over800"])
        self.assertEqual({"big.py": {"value": 700}}, out["files"]["over500"])
        self.assertEqual({"big.py::f": {"value": 90}}, out["functions"]["over60"])

    def test_growth_is_rejected(self):
        rows = [{"file": "big.py", "name": "f", "qual": "f",
                 "lines": 160, "kind": "function", "start": 1}]
        _, problems = self._tighten(self._baseline(), self._data({"big.py": 900}, rows))
        self.assertTrue(any("变长" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()


def _run_main(module, argv):
    """直接调 main，返回退出码与标准错误文本（不落盘、不读真实名单）。"""
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        rc = module.main(list(argv))
    return rc, err.getvalue()


class NoNodeRefusalTests(unittest.TestCase):
    """JS 函数没查成时，--init 与 --tighten 必须拒绝，不能把 JS 名单删掉。"""

    def _module(self):
        module = load_check_module()
        real = module.collect()
        real["js_skipped"] = "no node（测试替身）"
        module.collect = lambda: real
        return module

    def _baseline_copy(self, module):
        tmp = Path(tempfile.mkdtemp(prefix="code-shape-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        baseline = tmp / "baseline.json"
        shutil.copy2(CHECK.parent / "baseline.json", baseline)
        module.BASELINE = baseline
        return baseline

    def test_tighten_refuses_without_js_data(self):
        """没有 JS 数据时收紧会把 JS 名单整段删掉，必须先拒绝。"""
        module = self._module()
        baseline = self._baseline_copy(module)
        before = baseline.read_bytes()
        rc, err = _run_main(module, ["--tighten"])
        self.assertNotEqual(0, rc, "--tighten 在没有 JS 数据时必须非零退出")
        self.assertIn("node", err, "被拒绝的原因要打到标准错误")
        self.assertEqual(before, baseline.read_bytes(), "被拒绝时不能改 baseline.json")

    def test_init_refuses_without_js_data(self):
        """没有 JS 数据时 --init 会生成一份没有 JS 的名单，必须先拒绝。"""
        module = self._module()
        tmp = Path(tempfile.mkdtemp(prefix="code-shape-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        module.BASELINE = tmp / "baseline.json"
        rc, err = _run_main(module, ["--init"])
        self.assertNotEqual(0, rc, "--init 在没有 JS 数据时必须非零退出")
        self.assertIn("node", err, "被拒绝的原因要打到标准错误")
        self.assertFalse(module.BASELINE.exists(), "被拒绝时不能生成 baseline.json")
