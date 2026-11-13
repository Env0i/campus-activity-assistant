# -*- coding: utf-8 -*-
"""分层边界契约测试：domain/application 不得直接依赖混合具体模块。

被禁的是「实现混杂的具体模块」（signup_plan 含协调器/线程、business_clock 含
SNTP/系统时钟、time_contract 含全局时间源、updater/update_check 含网络/进程）：
所需纯函数、时钟函数与异常类型一律由 composition root（local/app.py）注入。
本文件同时用内存替身验证注入缝真实生效。

@author Author
"""
from __future__ import annotations

import ast
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

LOCAL = Path(__file__).resolve().parents[1]
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

# 混合具体模块：domain/application 只准依赖 stdlib 与 domain 自身
BANNED_MODULES = {
    "signup_plan", "business_clock", "time_contract", "grab", "updater",
    "update_check", "update_delta", "update_launcher", "runtime_paths", "webview", "app",
}


def _module_sources():
    for pkg in ("domain", "application"):
        for path in sorted((LOCAL / pkg).glob("*.py")):
            yield pkg, path


class ImportBoundaryTests(unittest.TestCase):
    def test_domain_and_application_import_no_mixed_concrete_modules(self):
        for pkg, path in _module_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertNotIn(
                        name, BANNED_MODULES,
                        "%s/%s 不得直接依赖混合具体模块 %r（应由 app.py 注入）"
                        % (pkg, path.name, name))

    def test_update_delta_and_launcher_are_banned_for_inner_layers(self):
        """更新增量与启动器带文件和进程副作用：domain/application 直接 import 要被拦。"""
        self.assertLessEqual({"update_delta", "update_launcher"}, BANNED_MODULES)

    def test_domain_reads_no_wall_clock(self):
        """domain 只做纯换算/格式化：不得直接读墙钟，此刻值一律由调用方传入。"""
        banned = ("datetime.now(", "datetime.today(", "datetime.utcnow(",
                  "time.time(", "time.monotonic(", "perf_counter(")
        for pkg, path in _module_sources():
            if pkg != "domain":
                continue
            text = path.read_text(encoding="utf-8")
            for token in banned:
                self.assertNotIn(token, text,
                                 "%s 不得直接读取墙钟：%s" % (path.name, token))


class InjectionBoundaryTests(unittest.TestCase):
    """注入缝的内存替身：证明纯函数/异常类型确经参数进入，不走模块直连。"""

    def test_plan_rules_classify_and_validate_are_injected(self):
        from domain import plan_rules

        seen = []

        def classify_mode(sign_start, sign_end, now):
            seen.append(("classify", sign_start, sign_end, now))
            return "closed"

        error = plan_rules.closed_items_error(
            [{"id": "a1", "name": "甲", "sign_end": "2026-01-01 09:00:00"}],
            123.0, classify_mode)
        self.assertIsNotNone(error, "注入的分类函数判 closed 时必须拒绝")
        self.assertEqual(error["errors"][0]["kind"], "sign_end_passed")
        self.assertTrue(seen, "必须调用注入的分类函数而不是模块直连")

        def validate_fn(items, now=None, signed_activities=None):
            seen.append(("validate", tuple(items), now))
            return {"ok": False, "conflicts": ["c1"], "errors": ["e1"]}

        out = plan_rules.check_conflicts([{"id": "a1"}], 1.0, [], validate_fn)
        self.assertEqual(out["conflicts"], ["c1"])
        self.assertEqual(out["errors"], ["e1"])

    def test_plan_rules_no_error_when_injected_classifier_passes(self):
        from domain import plan_rules

        error = plan_rules.closed_items_error(
            [{"id": "a1", "name": "甲", "sign_end": ""}], 1.0,
            lambda s, e, n: "instant_signup")
        self.assertIsNone(error, "注入分类函数不判 closed 时不得拒绝")

    def test_task_stop_binding_uses_injected_epoch_fn(self):
        from domain import plan_rules

        spec = SimpleNamespace(sign_end="2026-01-01 09:00:00",
                               retry_started_at=100.0, retry_for_s=50)
        # epoch_of(sign_end)=50；task_deadline=min(100+50, 50)=50 → 绑 sign_end
        binding = plan_rules.task_stop_reason_binding(
            spec, True, lambda ts: 50.0)
        self.assertEqual(binding, "sign_end")
        self.assertEqual(
            plan_rules.task_stop_reason_binding(spec, False, lambda ts: 50.0), "")

    def test_plan_service_catches_only_injected_clock_unavailable(self):
        """业务时钟读不到 → 保持原定开放时刻：异常类型经参数注入。"""
        from application import plan_service

        class FakeClockErr(Exception):
            pass

        captured = {}

        def worker_command(*args):
            captured["args"] = list(args)
            return ["fake-worker"]

        def spawn(args, cwd=None, env=None):
            raise RuntimeError("stop-before-threads")

        spec = SimpleNamespace(
            task_id="t1", activity_id="a1", name="活动",
            sign_start="2026-01-01 09:00:00", sign_end="",
            lead_s=0, retry_for_s=5, max_attempts=0,
            headed=False, signup_mode="", retry_started_at=0)

        def boom():
            raise FakeClockErr("no clock")

        with self.assertRaises(RuntimeError):
            plan_service.run_plan_task(
                spec, threading.Event(), None,
                emit=lambda *a: None, lock=threading.Lock(), plan_procs={},
                clock_now=boom, is_closing=lambda: False,
                worker_command=worker_command, env=lambda: {},
                spawn=spawn, cwd=".", grace_s=0.1,
                epoch_of=lambda ts: None, time_text_of=lambda epoch=None: "",
                clock_unavailable=FakeClockErr)
        self.assertEqual(captured["args"][0], "grab", "worker 命令已装配")
        self.assertIn("--at", captured["args"])
        at_index = captured["args"].index("--at")
        self.assertEqual(captured["args"][at_index + 1], "2026-01-01 09:00:00",
                         "注入的时钟异常被识别为「时钟不可用」：保持原定开放时刻")

    def test_plan_service_closing_refusal_uses_domain_error(self):
        from application import plan_service
        from domain.errors import ClosingError

        called = []

        with self.assertRaises(ClosingError):
            plan_service.run_plan_task(
                SimpleNamespace(
                    task_id="t1", activity_id="a1", name="活动",
                    sign_start="", sign_end="", lead_s=0, retry_for_s=5,
                    max_attempts=0, headed=False, signup_mode="",
                    retry_started_at=0),
                threading.Event(), None,
                emit=lambda *a: None, lock=threading.Lock(), plan_procs={},
                clock_now=lambda: 1.0, is_closing=lambda: True,
                worker_command=lambda *a: ["fake"], env=lambda: {},
                spawn=lambda *a, **k: called.append("spawn"),
                cwd=".", grace_s=0.1,
                epoch_of=lambda ts: None, time_text_of=lambda epoch=None: "",
                clock_unavailable=Exception)
        self.assertEqual(called, [], "关闭拒绝必须发生在创建之前（零 spawn）")

    def test_demo_items_uses_injected_time_text(self):
        from domain import demo_data

        items = demo_data.demo_items(1000.0, lambda epoch=None: "T%s" % epoch)
        self.assertEqual(items[0]["sign_start"], "T997.0",
                         "演示时间必须走注入的格式化函数")

    def test_format_local_text_is_pure_formatting(self):
        """ui.json 时间文本格式冻结：只接受 datetime 值并格式化，不取时。"""
        from datetime import datetime

        from domain.time_text import format_local_text

        self.assertEqual(format_local_text(datetime(2026, 1, 2, 3, 4, 5)),
                         "2026-01-02 03:04:05")


# 三个内层包各自允许依赖的类别。顶层模块（local/ 根下的 .py）任何内层包都不许 import。
# infrastructure 是接第三方包的适配器层；domain 与 application 里 import 第三方即算越界。
_ALLOWED_KINDS = {
    "domain": {"domain", "stdlib"},
    "application": {"domain", "application", "stdlib"},
    "infrastructure": {"domain", "infrastructure", "stdlib", "third_party"},
}
_LAYERS = frozenset(_ALLOWED_KINDS)
_TOP_LEVEL = {p.stem for p in LOCAL.glob("*.py")}

# 存量越界：每条都要写清去处，消掉时从这里删。函数体里的延迟 import 也算越界。
# 键是「文件、完整模块名」：按模块锁，不按包锁，同包再加一个模块照样报。
LEGACY_DIRECTION_VIOLATIONS = {
    ("application/advanced_component_service.py", "infrastructure.component_packages"):
        "步骤 2 拆组件服务时消：组件包扫描归 infrastructure，服务经端口拿清单",
    ("infrastructure/component_packages.py", "runtime_paths"):
        "步骤 2 拆组件服务时消：数据目录改由调用方传进来，不直接取顶层模块",
}


def _strip_local(module):
    """去掉项目根包前缀 local：写 local.domain 与写 domain 是同一件事。"""
    if module == "local":
        return ""
    if module.startswith("local."):
        return module[len("local."):]
    return module


def _kind_of(module):
    """模块名 → domain/application/infrastructure/top_level/stdlib/third_party。"""
    head = _strip_local(module).split(".")[0]
    if not head or head == "__future__":
        return "stdlib"
    if head in _LAYERS:
        return head
    if head in _TOP_LEVEL:
        return "top_level"
    if head in sys.stdlib_module_names:
        return "stdlib"
    return "third_party"


def _imported_modules(node, layer):
    """一条 import/from 语句指向的完整模块名；相对 import 按所在层解析成实际包名。"""
    if isinstance(node, ast.Import):
        return [_strip_local(alias.name) for alias in node.names]
    module = node.module or ""
    if node.level:
        # level 1 是同一个包；level 2 起逐级上溯到 local 根
        parts = layer.split(".")
        keep = parts[:max(0, len(parts) - (node.level - 1))]
        module = ".".join(keep + ([module] if module else []))
    module = _strip_local(module)
    if not module:
        return [alias.name for alias in node.names]
    # from 内层包 import 名：名是子模块时按「包.名」记，白名单才能锁住具体模块
    if _kind_of(module) in _LAYERS:
        return ["%s.%s" % (module, alias.name) for alias in node.names]
    return [module]


def _direction_violations_in(layer, rel, source):
    """纯函数：一段源码加所在层，返回 (文件, 完整模块名, 行号) 的越界清单。"""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        for module in _imported_modules(node, layer):
            if _kind_of(module) not in _ALLOWED_KINDS[layer]:
                found.append((rel, module, node.lineno))
    return found


def _direction_violations():
    """扫三个内层包，返回 (文件, 完整模块名, 行号)，函数体里的延迟 import 也在内。"""
    found = set()
    for pkg in sorted(_ALLOWED_KINDS):
        for path in sorted((LOCAL / pkg).glob("*.py")):
            rel = "%s/%s" % (pkg, path.name)
            found.update(_direction_violations_in(
                pkg, rel, path.read_text(encoding="utf-8")))
    return found


class LayerDirectionTests(unittest.TestCase):
    """三条内层包只许向下依赖：domain → application → infrastructure 不许反向或跨层。"""

    def test_inner_layers_import_only_allowed_directions(self):
        found = _direction_violations()
        extra = sorted(
            (rel, module, line) for rel, module, line in found
            if (rel, module) not in LEGACY_DIRECTION_VIOLATIONS)
        self.assertEqual(
            [], extra,
            "内层包出现新的跨层依赖（文件、被 import 的项目内模块、行）：%r" % (extra,))

    def test_direction_whitelist_is_still_needed(self):
        """白名单里的越界在代码里已经没有了也要红：提示把它删掉。"""
        found = {(rel, module) for rel, module, _ in _direction_violations()}
        stale = sorted(set(LEGACY_DIRECTION_VIOLATIONS) - found)
        self.assertEqual([], stale, "白名单里的越界已经不存在，请删掉这些项：%r" % (stale,))

    def test_direction_whitelist_entries_carry_reason(self):
        for key, reason in LEGACY_DIRECTION_VIOLATIONS.items():
            self.assertTrue(reason.strip(), "%r 必须写理由是哪个步骤消掉" % (key,))

    def test_direction_guard_sees_every_alias_in_multi_import(self):
        """import a, b 的每个 alias 都要看：只看第一个会漏掉跨层 import。"""
        found = _direction_violations_in(
            "domain", "domain/sample.py", "import os, infrastructure\n")
        self.assertEqual([("domain/sample.py", "infrastructure", 1)], found)

    def test_direction_guard_sees_from_local_import_package(self):
        """from local import 包：去掉 local 前缀后仍要能认出项目内包。"""
        found = _direction_violations_in(
            "domain", "domain/sample.py", "from local import infrastructure\n")
        self.assertEqual([("domain/sample.py", "infrastructure", 1)], found)

    def test_direction_whitelist_is_locked_to_module_not_package(self):
        """白名单锁到具体模块：同一个包里再加一个模块仍要红。"""
        rel = "application/advanced_component_service.py"
        found = {(r, m) for r, m, _ in _direction_violations_in(
            "application", rel, "from infrastructure import tunnel_manager\n")}
        extra = sorted(found - set(LEGACY_DIRECTION_VIOLATIONS))
        self.assertEqual([(rel, "infrastructure.tunnel_manager")], extra)

    def test_direction_guard_treats_third_party_as_cross_layer(self):
        """domain 与 application 里 import 第三方包也算跨层，infrastructure 里放行。"""
        self.assertEqual(
            [("domain/sample.py", "requests", 1)],
            _direction_violations_in("domain", "domain/sample.py", "import requests\n"))
        self.assertEqual(
            [("application/sample.py", "requests", 1)],
            _direction_violations_in("application", "application/sample.py", "import requests\n"))
        self.assertEqual(
            [], _direction_violations_in("infrastructure", "infrastructure/sample.py", "import requests\n"))

    def test_direction_guard_resolves_parent_relative_import(self):
        """from ..infrastructure import x：level 大于 1 要按实际包名判。"""
        found = _direction_violations_in(
            "domain", "domain/sample.py", "from ..infrastructure import helper\n")
        self.assertEqual([("domain/sample.py", "infrastructure.helper", 1)], found)

    def test_direction_guard_allows_same_layer_and_stdlib(self):
        """反向用例：标准库与同包相对 import 都不算越界。"""
        self.assertEqual(
            [], _direction_violations_in("domain", "domain/sample.py", "import json\n"))
        self.assertEqual(
            [], _direction_violations_in("domain", "domain/sample.py", "from . import helper\n"))
        self.assertEqual(
            [], _direction_violations_in("infrastructure", "infrastructure/sample.py", "import ddddocr\n"))


if __name__ == "__main__":
    unittest.main()
