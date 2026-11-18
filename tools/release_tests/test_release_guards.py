#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发版守卫的用例：tools/release_guards.py 的步骤顺序、失败点名、ruff 缺失提示，
以及 tools/release.py 的 --prepare/--publish 在守卫失败时不进入构建、--check 不触发守卫。

先红后绿：本文件在没有 tools/release_guards.py、release.py 还没接守卫时先跑出红。
run_guards 的子进程一律用替身替换 run_command（模块级名字），不真跑全量、不真构建；
release.py 的入口测试也用替身 RUN_GUARDS / stage_local_assets，不发真实子进程。
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = (Path(__file__).resolve().parents[2] / "local" / "tests")
ROOT = TESTS.parent.parent
sys.path.insert(0, str(TESTS))


def _load_module(name: str, path: Path):
    """按路径加载仓库里的脚本当模块（与 test_lifecycle_release.load_release 同款）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_guards():
    """加载 tools/release_guards.py；实现缺失时在这里抛错，就是先红的那批。"""
    return _load_module("release_guards_for_test", ROOT / "tools" / "release_guards.py")


def load_release():
    """加载 tools/release.py（当模块导入，不执行 main）。"""
    return _load_module("campus_release_for_guards_test", ROOT / "tools" / "release.py")


def fake_run(fail_when: str = "", missing_ruff: bool = False):
    """造一个替身 run_command：命中 fail_when 片段的命令返回 1，ruff 缺席按缺模块报错。

    返回 (替身函数, 调用顺序记录)；命令按空格拼起来记进列表，方便断言步骤顺序。
    """
    calls: list[str] = []

    def run(command, timeout, cwd):
        joined = " ".join(command)
        calls.append(joined)
        if fail_when and fail_when in joined:
            return 1, "out:" + joined
        if missing_ruff and "ruff" in joined:
            return 1, "error: No module named ruff"
        return 0, "out:" + joined

    return run, calls


class GuardSequenceTests(unittest.TestCase):
    """run_guards：全绿返回成功且步骤按口径顺序；失败即停、点名失败的那一步。"""

    def test_all_pass_runs_steps_in_order(self):
        """全过：返回 (True, None)，顺序是形状 → 三道守卫测试 → ruff → 本机版全量。"""
        guards = load_guards()
        run, calls = fake_run()
        with mock.patch.object(guards, "run_command", run):
            ok, failed = guards.run_guards(ROOT)
        self.assertTrue(ok)
        self.assertIsNone(failed)
        self.assertEqual(6, len(calls), calls)
        self.assertIn("check.py", calls[0], "第一步必须是代码形状大小比对")
        self.assertIn("test_code_shape.py", calls[1])
        self.assertIn("test_layer_boundaries.py", calls[2])
        self.assertIn("test_ui_layers.py", calls[3])
        self.assertIn("ruff", calls[4])
        self.assertIn("test_*.py", calls[5], "最后一步是本机版全量")

    def test_failure_names_step_and_stops(self):
        """某一步失败：返回 (False, 那一步的名字)，后面的步骤不再跑。"""
        guards = load_guards()
        run, calls = fake_run(fail_when="test_layer_boundaries.py")
        with mock.patch.object(guards, "run_command", run):
            ok, failed = guards.run_guards(ROOT)
        self.assertFalse(ok)
        self.assertEqual("守卫测试 test_layer_boundaries", failed)
        self.assertEqual(3, len(calls), "失败后面的步骤不再跑：%r" % (calls,))
        self.assertNotIn("ruff", " ".join(calls))
        self.assertNotIn("test_*.py", " ".join(calls))

    def test_missing_ruff_fails_with_install_hint(self):
        """没装 ruff 也算失败，并提示先装开发依赖；全量不再往下跑。"""
        guards = load_guards()
        run, calls = fake_run(missing_ruff=True)
        buf = io.StringIO()
        with mock.patch.object(guards, "run_command", run):
            with contextlib.redirect_stdout(buf):
                ok, failed = guards.run_guards(ROOT)
        self.assertFalse(ok)
        self.assertEqual("ruff 静态检查", failed)
        self.assertNotIn("test_*.py", " ".join(calls), "ruff 失败后不再跑全量")
        self.assertIn("pip install -r requirements-dev.txt", buf.getvalue())


class ReleaseGuardWiringTests(unittest.TestCase):
    """release.py 接线：守卫失败挡住 --prepare；全过才放行；只读检查不触发守卫。"""

    def _cli_patches(self, rel, guards_result, argv):
        """把 release.py 摆成真命令行场景：CLI 模式开、守卫换替身、入口换替身。"""
        stage = mock.Mock()
        return stage, [
            mock.patch.object(rel, "__name__", "__main__"),
            mock.patch.object(rel, "RUN_GUARDS", mock.Mock(return_value=guards_result)),
            mock.patch.object(rel, "stage_local_assets", stage),
            mock.patch.object(sys, "argv", argv),
        ]

    def test_prepare_blocked_when_guards_fail(self):
        """--prepare 在守卫失败时不进入构建：非零退出并说明守卫没过，构建函数没被调。"""
        rel = load_release()
        stage, patches = self._cli_patches(rel, (False, "本机版全量"),
                                           ["release.py", "--prepare"])
        with contextlib.redirect_stdout(io.StringIO()):
            for p in patches:
                p.start()
            try:
                with self.assertRaises(SystemExit) as stopped:
                    rel.main()
            finally:
                mock.patch.stopall()
        self.assertIn("守卫没过，没有开始构建", str(stopped.exception))
        stage.assert_not_called()

    def test_prepare_proceeds_when_guards_pass(self):
        """守卫全过：--prepare 照常进入构建，构建函数恰好被调一次。"""
        rel = load_release()
        stage, patches = self._cli_patches(rel, (True, None),
                                           ["release.py", "--prepare"])
        with contextlib.redirect_stdout(io.StringIO()):
            for p in patches:
                p.start()
            try:
                self.assertEqual(0, rel.main())
            finally:
                mock.patch.stopall()
        self.assertEqual(1, stage.call_count)

    def test_check_mode_never_runs_guards(self):
        """不带参数的只读检查不触发守卫——哪怕处在真命令行模式。"""
        rel = load_release()
        guards_run = mock.Mock(return_value=(True, None))
        with contextlib.redirect_stdout(io.StringIO()):
            for p in (
                mock.patch.object(rel, "__name__", "__main__"),
                mock.patch.object(rel, "RUN_GUARDS", guards_run),
                mock.patch.object(rel, "check_only", lambda v: None),
                mock.patch.object(sys, "argv", ["release.py"]),
            ):
                p.start()
            try:
                self.assertEqual(0, rel.main())
            finally:
                mock.patch.stopall()
        guards_run.assert_not_called()


class WorkflowCommandTests(unittest.TestCase):
    """持续集成工作流：能解析成两个 job，每条 run 命令都能在 AGENTS.md「命令」一节找到。"""

    def test_ci_workflow_runs_come_from_agents_commands(self):
        """ci.yml 存在、恰有两个 job；工作流不得出现 AGENTS.md 之外的命令（逐行取 run 值）。"""
        path = ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(path.is_file(), "缺少 .github/workflows/ci.yml")
        lines = path.read_text(encoding="utf-8").splitlines()
        job_ids = [lines[i].strip().rstrip(":") for i in range(len(lines) - 1)
                   if re.fullmatch(r"  [A-Za-z][\w-]*:", lines[i])
                   and re.fullmatch(r"    runs-on: \S+", lines[i + 1])]
        self.assertEqual(2, len(job_ids), "应解析出两个 job，实际：%r" % job_ids)
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        begin = agents_text.index("## 命令")
        section = agents_text[begin:agents_text.index("\n## ", begin)]
        commands = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- run: "):
                commands.append(stripped[len("- run: "):])
            elif stripped.startswith("run: "):
                commands.append(stripped[len("run: "):])
        self.assertTrue(commands, "工作流里没有解析到任何 run 命令")
        missing = [cmd for cmd in commands if cmd not in section]
        self.assertEqual([], missing, "run 命令在 AGENTS.md「命令」一节找不到原文：%r" % missing)


    def _syntax_check_command(self) -> str:
        """从 ci.yml 取出语法检查那一步的 run 值；找不到就让当前用例失败。"""
        lines = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            for prefix in ("- run: ", "run: "):
                if stripped.startswith(prefix) and "node --check" in stripped:
                    return stripped[len(prefix):]
        self.fail("ci.yml 里没有语法检查那一步")

    def test_no_break_in_syntax_check_command(self):
        """挡：「|| break」让语法检查在出错时退出码为 0——工作流与 AGENTS.md 都不许再有这种写法。"""
        for name, path in ((".github/workflows/ci.yml", ROOT / ".github" / "workflows" / "ci.yml"),
                           ("AGENTS.md", ROOT / "AGENTS.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            hits = [str(i + 1) for i, line in enumerate(lines) if "|| break" in line]
            self.assertEqual([], hits, "%s 里还有出错也算通过的语法检查写法，行号：%r" % (name, hits))

    def test_syntax_check_command_fails_on_bad_script(self):
        """行为挡板：工作流里那条语法检查命令，遇到语法错误的脚本必须退出码非零，只有正确脚本时为零。"""
        bash = shutil.which("bash")
        if bash is None or shutil.which("node") is None:
            self.skipTest("本机没有 bash 或 node：跳过语法检查命令的行为核对")
        command = self._syntax_check_command()
        root = Path(tempfile.mkdtemp(prefix="ci-syntax-check-")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        (root / "good.js").write_text("const answer = 42;\n", encoding="utf-8")
        (root / "bad.js").write_text("const answer = ;\n", encoding="utf-8")
        globbed = (root / "*.js").as_posix()
        command = command.replace("local/ui/*.js", globbed).replace("local/ui/*/*.js", globbed).replace("local/ui/*/*/*.js", globbed)
        with_bad = subprocess.run([bash, "-c", command], capture_output=True, text=True)
        self.assertNotEqual(0, with_bad.returncode,
                            "有语法错误的脚本时命令仍返回 0：%r" % (with_bad.stdout + with_bad.stderr))
        (root / "bad.js").unlink()
        good_only = subprocess.run([bash, "-c", command], capture_output=True, text=True)
        self.assertEqual(0, good_only.returncode,
                         "只有正确脚本时命令不该失败：%r" % (good_only.stdout + good_only.stderr))


if __name__ == "__main__":
    unittest.main()
