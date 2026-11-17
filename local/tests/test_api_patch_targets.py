# -*- coding: utf-8 -*-
"""补丁落点守卫：测试打在 app 模块上的补丁、写到 Api 实例上的字段，必须真有人接。

拆分 Api 时最大的风险是补丁悄悄落空：`patch.object(app, "名字")` 打在了一个已经被搬走
的名字上、`api._字段 = ...` 写进了一个 Api 再也不会读的字段——两边都不报错，用例照常绿，
行为却已经没被守住。本文件只读源码，不 import 产品代码：

1. 打在 app 模块上的补丁（`patch.object(<app 模块别名>, "名字")`、`patch("<app 别名>.名字")`、
   对 app 模块别名的属性赋值与 `setattr`），名字必须是 `local/app.py` 模块级真有的属性；
2. 写到 Api 实例上的字段（对 Api 实例变量的属性赋值、`setattr`、`patch.object`），
   名字必须在 `class Api` 里被 `self.名字` 读到，或者本身就是 Api 的方法；
3. 认不出的写法（动态名字、`__dict__` 下标赋值）必须为零：出现了先补清点，不许放过。

开工 HEAD 上就存在、但不在这一批修的存量违规记在 FROZEN_LEGACY：实际违规必须**恰好**
等于它——多一条说明这一批改坏了，少一条说明存量已经消失，要把对应条目删掉（清单只许变短）。

@author Author
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
LOCAL_DIR = TESTS_DIR.parent
APP_FILE = LOCAL_DIR / "app.py"


# 开工 HEAD 上就存在、不在这一批修的存量违规：(相对路径, 所在函数, 名字)。只许变短。
# 三条都不构成真缺陷：产品侧是用 getattr(self, "名字") 或 self.__dict__.setdefault 读的，
# 只是不满足「被 self.名字 直接读到」这一条口径；清单已逐条写进证据 README 交裁决。
FROZEN_LEGACY: tuple[tuple[str, str, str], ...] = (
    ("tests/test_application_services.py", "_connect_tailscale", "_endpoint"),
    ("tests/test_application_services.py", "test_approved_close_lets_the_window_go", "_close_approved"),
    ("tests/test_release_audit.py",
     "test_cancellation_survives_normal_start_history_eviction", "_canceled_start_ids"),
)


def _iter_sources() -> list[Path]:
    """local/tests 下所有测试与夹具源码，按路径排序。"""
    return sorted(TESTS_DIR.rglob("*.py"))


def _bind_names(stmts) -> set[str]:
    """一组语句里的绑定名（含 try/if/with 里的延迟 import）。"""
    names: set[str] = set()
    for node in stmts:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets
                         if isinstance(target, ast.Name))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, (ast.Try, ast.If, ast.With, ast.For, ast.While)):
            names |= _bind_names(getattr(node, "body", []))
            names |= _bind_names(getattr(node, "orelse", []))
            names |= _bind_names(getattr(node, "finalbody", []))
            for handler in getattr(node, "handlers", []):
                names |= _bind_names(handler.body)
    return names


def _module_attrs(tree: ast.Module) -> set[str]:
    """app 模块级真有的属性名。"""
    return _bind_names(tree.body)


def _api_members(tree: ast.Module) -> set[str]:
    """Api 的成员名：方法、类体赋值，以及被 `self.名字` 读到或 += 过的字段。"""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Api":
            break
    else:
        raise AssertionError("local/app.py 里没有 class Api")
    names = _bind_names(node.body)
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute) and isinstance(item.ctx, ast.Load) \
                and isinstance(item.value, ast.Name) and item.value.id == "self":
            names.add(item.attr)
        elif isinstance(item, ast.AugAssign) and isinstance(item.target, ast.Attribute) \
                and isinstance(item.target.value, ast.Name) and item.target.value.id == "self":
            names.add(item.target.attr)
    return names


def _app_aliases(tree: ast.Module) -> set[str]:
    """本文件里指向 app 模块的本地名字。"""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases.update(alias.asname or alias.name.split(".")[0] for alias in node.names
                           if alias.name in ("app", "local.app"))
        elif isinstance(node, ast.ImportFrom):
            if node.module in ("local", None):
                aliases.update(alias.asname or alias.name for alias in node.names
                               if alias.name == "app")
    return aliases


def _mentions_api(node: ast.AST) -> bool:
    """表达式里出现 `Api` 这个名字或 `.Api` 属性，就当成 Api 实例的构造。"""
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and item.id == "Api":
            return True
        if isinstance(item, ast.Attribute) and item.attr == "Api":
            return True
    return False


def _dotted(node: ast.AST) -> str:
    """`self.api` 这类属性链拼成点号串；拼不出来返回空串。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _api_vars(tree: ast.Module) -> set[str]:
    """被赋成 Api 实例的变量（含 self.api 这种属性链）。"""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value, targets = node.value, node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, (node.target,)
        else:
            continue
        if not _mentions_api(value):
            continue
        found.update(name for name in (_dotted(target) for target in targets) if name)
    return found


def _literal(node: ast.AST | None) -> str | None:
    """字符串字面量的值；不是字面量返回 None（= 动态名字）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str:
    return _dotted(node.func) if isinstance(node, ast.Call) else ""


def _literals_of(node: ast.AST) -> set[str] | None:
    """一个字面量或一组字面量；掺了非字面量就返回 None。"""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [_literal(item) for item in node.elts]
        return None if any(item is None for item in values) else set(values)
    value = _literal(node)
    return None if value is None else {value}


def _string_candidates(tree: ast.Module) -> dict[str, set[str]]:
    """变量名 → 它可能取到的字符串字面量（只认一次赋值与 for 的字面量序列）。"""
    found: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            values = _literals_of(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name) and values is not None:
                    found.setdefault(target.id, set()).update(values)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            values = _literals_of(node.iter)
            if values is not None:
                found.setdefault(node.target.id, set()).update(values)
    return found


def _owner(dotted: str, aliases: set[str], api_vars: set[str]) -> str:
    """点号串归属：app 模块 / Api 实例 / 都不是。"""
    if dotted in aliases:
        return "app"
    if dotted in api_vars:
        return "api"
    return ""


def _walk_scoped(node: ast.AST, scope: tuple[str, ...] = ()):
    """按作用域遍历：产出 (节点, 外层函数/类名字元组)。"""
    yield node, scope
    inner = scope + (getattr(node, "name", ""),) \
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) else scope
    for child in ast.iter_child_nodes(node):
        yield from _walk_scoped(child, inner)


def _write_targets(node: ast.AST) -> list[ast.Attribute]:
    """赋值语句里写在属性上的目标（含 for 的循环变量）。"""
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.For, ast.AsyncFor)):
        targets = [node.target]
    else:
        return []
    return [item for item in targets if isinstance(item, ast.Attribute)]


class _Scanner:
    """一次扫描：把违规与认不出的写法按类别攒起来。"""

    def __init__(self, app_attrs: set[str], api_members: set[str]):
        self.app_attrs = app_attrs
        self.api_members = api_members
        self.problems: dict[str, list[tuple[str, str, str]]] = {}
        self.unknown: list[str] = []
        self.candidates: dict[str, set[str]] = {}

    def scan_file(self, path: Path) -> None:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(LOCAL_DIR).as_posix()
        aliases = _app_aliases(tree)
        api_vars = _api_vars(tree)
        self.candidates = _string_candidates(tree)
        for node, scope in _walk_scoped(tree):
            self.judge(node, rel, scope[-1] if scope else "<module>", aliases, api_vars)

    def judge(self, node, rel, where, aliases, api_vars) -> None:  # noqa: PLR0913
        call = _call_name(node)
        if call.endswith("patch.object") and len(node.args) >= 2:
            self._judge_patch_object(node, rel, where, aliases, api_vars)
        elif call == "setattr" and len(node.args) >= 2:
            self._judge_setattr(node, rel, where, aliases, api_vars)
        elif call in ("patch", "mock.patch") and node.args:
            self._judge_patch_string(node, rel, where, aliases)
        for target in _write_targets(node):
            self._judge_write(target, rel, where, aliases, api_vars)
        self._judge_dict_write(node, rel, aliases, api_vars)

    def _judge_patch_object(self, node, rel, where, aliases, api_vars) -> None:
        dotted = _dotted(node.args[0])
        name = _literal(node.args[1])
        owner = _owner(dotted, aliases, api_vars)
        if not owner:
            return
        if name is None:
            self.unknown.append("%s: patch.object(%s, <动态名字>) 第 %d 行"
                                % (rel, dotted, node.lineno))
            return
        self._record(owner, rel, where, name)

    def _judge_setattr(self, node, rel, where, aliases, api_vars) -> None:
        dotted = _dotted(node.args[0])
        owner = _owner(dotted, aliases, api_vars)
        if not owner:
            return
        name = _literal(node.args[1])
        if name is None:
            self.unknown.append("%s: setattr(%s, <动态名字>) 第 %d 行" % (rel, dotted, node.lineno))
            return
        self._record(owner, rel, where, name)

    def _judge_patch_string(self, node, rel, where, aliases) -> None:
        raw = _literal(node.args[0])
        targets = {raw} if raw is not None else self._resolved_patch_target(node, rel)
        for item in targets or ():
            if "." in item:
                head, name = item.rsplit(".", 1)
                if head in aliases or head.split(".")[-1] == "app":
                    self._record("app", rel, where, name)

    def _resolved_patch_target(self, node, rel) -> set[str] | None:
        """动态 patch 目标：能追到字面量的就追，追不到记进「认不出」。"""
        argument = node.args[0]
        if isinstance(argument, ast.Name) and argument.id in self.candidates:
            return self.candidates[argument.id]
        self.unknown.append("%s: patch(<动态目标>) 第 %d 行" % (rel, node.lineno))
        return None

    def _judge_write(self, target, rel, where, aliases, api_vars) -> None:
        owner = _owner(_dotted(target.value), aliases, api_vars)
        if owner:
            self._record(owner, rel, where, target.attr)

    def _judge_dict_write(self, node, rel, aliases, api_vars) -> None:
        """`api.__dict__["名字"] = ...` 这类写法认不出，一律记下。"""
        for item in ast.walk(node):
            if not isinstance(item, ast.Subscript) or not isinstance(item.ctx, ast.Store):
                continue
            value = item.value
            dotted = _dotted(value.value) if isinstance(value, ast.Attribute) \
                and value.attr == "__dict__" else ""
            if dotted and _owner(dotted, aliases, api_vars):
                self.unknown.append("%s: %s.__dict__[...] 下标赋值第 %d 行"
                                    % (rel, dotted, item.lineno))

    def _record(self, owner: str, rel: str, where: str, name: str) -> None:
        allowed = self.app_attrs if owner == "app" else self.api_members
        if name not in allowed:
            self.problems.setdefault(owner, []).append((rel, where, name))


def _app_names() -> tuple[set[str], set[str]]:
    """(app 模块级属性, Api 成员)。"""
    app_tree = ast.parse(APP_FILE.read_text(encoding="utf-8"), filename=str(APP_FILE))
    return _module_attrs(app_tree), _api_members(app_tree)


def scan() -> tuple[dict[str, list], list[str]]:
    """读 local/app.py 与 local/tests 下全部源码，返回 (违规, 认不出的写法)。"""
    app_attrs, api_members = _app_names()
    scanner = _Scanner(app_attrs, api_members)
    for path in _iter_sources():
        scanner.scan_file(path)
    return scanner.problems, scanner.unknown


class PatchTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.problems, cls.unknown = scan()

    def test_app_module_patches_hit_real_names(self):
        """打在 app 模块上的补丁，名字必须是 app.py 模块级真有的属性。"""
        misses = self.problems.get("app", [])
        self.assertEqual(misses, [], "补丁打在了 app 模块没有的名字上：%s" % (misses,))

    def test_violations_equal_the_frozen_legacy_list(self):
        """写到 Api 实例上的字段必须有人读；实际违规恰好等于冻结的存量清单。"""
        actual = sorted(set(self.problems.get("api", [])))
        frozen = sorted(set(FROZEN_LEGACY))
        self.assertEqual([item for item in actual if item not in frozen], [],
                         "这些写入落在 Api 没有的成员上（拆分后补丁已悄悄落空）：%s"
                         % ([item for item in actual if item not in frozen],))
        self.assertEqual([item for item in frozen if item not in actual], [],
                         "存量清单里这些条目已经不违规了，请删掉（清单只许变短）：%s"
                         % ([item for item in frozen if item not in actual],))

    def test_no_unrecognized_forms(self):
        """认不出的写法必须为零：出现了先补清点，不许当没看见。"""
        self.assertEqual(self.unknown, [], "认不出的补丁/写入写法：%s" % (self.unknown,))

    def test_scanner_flags_a_synthetic_violation(self):
        """守卫自己也要被守住：合成一段写得出的违规，必须被抓到。"""
        source = "\n".join([
            "import app as local_app",
            "api = local_app.Api()",
            "api._gone_field = 1",
            "api._emit = 2",
            "local_app.missing_name = 3",
            "patch.object(local_app, 'also_missing')",
            "setattr(local_app, 'third_missing', 4)",
            "setattr(api, some_dynamic, 5)",
        ])
        app_attrs, api_members = _app_names()
        scanner = _Scanner(app_attrs, api_members)
        tree = ast.parse(source)
        scanner.candidates = _string_candidates(tree)
        for node, scope in _walk_scoped(tree):
            scanner.judge(node, "synthetic.py", scope[-1] if scope else "<module>",
                          _app_aliases(tree), _api_vars(tree))
        self.assertEqual(scanner.problems.get("api"), [("synthetic.py", "<module>", "_gone_field")])
        app_misses = [name for _, _, name in scanner.problems.get("app", [])]
        self.assertEqual(app_misses, ["missing_name", "also_missing", "third_missing"])
        self.assertEqual(len(scanner.unknown), 1, scanner.unknown)
        self.assertIn("动态名字", scanner.unknown[0])


if __name__ == "__main__":
    unittest.main()
