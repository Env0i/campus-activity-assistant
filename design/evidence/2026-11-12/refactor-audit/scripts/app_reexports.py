# -*- coding: utf-8 -*-
"""app.py 的模块级名字，以及测试按 app.X 打补丁、读取的位置（README「C3」）。

从仓库根运行：
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/app_reexports.py

口径：
- app.py 模块级名字分四种：def / class（自己定义）、别名（X = 模块.名字 或 X = 导入的名字）、
  import 进来的名字、其余赋值（常量或变量）。
- 测试文件（local/tests/、tools/）里，先找出绑到 app 模块的名字：
  import app、import app as X、from local import app、X = importlib.import_module("app")；
  测试还常用夹具把模块转一手（app = self._app()、app = self.app、local_app = self._app_module），
  所以名字叫 app / local_app 的变量、self.app / self._app / self._app_module、_app() 的返回值
  也按 app 模块算。同一个函数里 app = read(…) / ….read_text(…) 这种读源码文本的除外。
- 误差：这是按名字认的。夹具换了别的名字就数不到；别的对象恰好叫 app 会被多数。
  结果里「app.py 模块级找不到的名字」一节就是用来人工排查多数的。
- 打补丁：patch.object(X, "名字")、patch("app.名字")、setattr(X, "名字", …)、X.名字 = …
- 读取：其余 X.名字。
- X.Api.名字、X.某模块.名字（例如 app.subprocess.Popen）单独统计。
只读，只用标准库。
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

APP = "local/app.py"


def app_module_names() -> dict[str, dict]:
    """app.py 模块级的每个名字 → {kind, line, target}。同名多次赋值时保留全部行号。"""
    tree = ast.parse(Path(APP).read_text(encoding="utf-8"), filename=APP)
    names: dict[str, dict] = {}
    imported: set[str] = set()

    def record(name: str, kind: str, line: int, target: str = "") -> None:
        entry = names.setdefault(name, {"kind": kind, "line": line, "target": target, "lines": []})
        entry["lines"].append(line)
        # 后面的定义覆盖前面的：以最后一次为准（例如 _task_deadline 先 def 后被别名覆盖）
        entry["kind"], entry["target"], entry["line"] = kind, target, line

    def dotted(node: ast.AST) -> str:
        parts = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
            return ".".join(reversed(parts))
        return ""

    def visit(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                record(node.name, "def", node.lineno)
            elif isinstance(node, ast.ClassDef):
                record(node.name, "class", node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    imported.add(bound)
                    record(bound, "import", node.lineno, alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    bound = alias.asname or alias.name
                    imported.add(bound)
                    record(bound, "import", node.lineno, f"{node.module}.{alias.name}")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for target in targets:
                    if not isinstance(target, ast.Name):
                        continue
                    ref = dotted(value) if value is not None else ""
                    base = ref.split(".")[0] if ref else ""
                    if ref and (base in imported or base in names):
                        record(target.id, "alias", node.lineno, ref)
                    else:
                        record(target.id, "value", node.lineno)
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                visit(node.body)
                for extra in ("orelse", "finalbody"):
                    visit(getattr(node, extra, []) or [])
                for handler in getattr(node, "handlers", []) or []:
                    visit(handler.body)

    visit(tree.body)
    return names


def test_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "local/tests", "tools"], capture_output=True,
                         text=True, encoding="utf-8", check=True).stdout
    return sorted(f for f in out.splitlines() if f.endswith(".py"))


def app_aliases(tree: ast.AST) -> set[str]:
    """这个文件里哪些名字绑到了 app 模块。"""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in ("app", "local.app"):
                    found.add(alias.asname or alias.name.split(".")[0] if alias.name == "app"
                              else (alias.asname or "local"))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "local":
                for alias in node.names:
                    if alias.name == "app":
                        found.add(alias.asname or "app")
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            args = node.value.args
            if fname in ("import_module", "__import__") and args \
                    and isinstance(args[0], ast.Constant) and args[0].value in ("app", "local.app"):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.add(target.id)
    found.discard("local")
    return found


ALIAS_NAMES = {"app", "local_app"}
ALIAS_ATTRS = {"app", "_app", "_app_module"}
ALIAS_CALLS = {"_app"}
TEXT_CALLS = {"read", "read_text", "read_ui_scripts", "open"}


def scope_map(tree: ast.AST) -> dict[int, int]:
    """每个节点 → 它所在的最内层函数（用 id 表示；模块级是 0）。"""
    out: dict[int, int] = {}

    def walk(node: ast.AST, scope: int) -> None:
        for child in ast.iter_child_nodes(node):
            out[id(child)] = scope
            inner = id(child) if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else scope
            walk(child, inner)

    walk(tree, 0)
    return out


def text_bound_names(tree: ast.AST) -> set[tuple[int, str]]:
    """哪些（函数，名字）是从读文本的调用赋来的：这些 app 是源码字符串，不是模块。"""
    scopes = scope_map(tree)
    found: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            fn = node.value.func
            fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
            if fname in TEXT_CALLS:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        found.add((scopes.get(id(target)), target.id))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    names = app_module_names()
    # uses[名字] = {"patch": [(文件, 行)], "read": [...]}
    uses: dict[str, dict[str, list]] = defaultdict(lambda: {"patch": [], "read": []})
    api_uses: dict[str, dict[str, list]] = defaultdict(lambda: {"patch": [], "read": []})
    via_module: dict[str, list] = defaultdict(list)      # app.subprocess.Popen 一类
    files_with_app = 0

    for path in test_files():
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
        aliases = app_aliases(tree)
        # patch("app.X") 这种字符串写法不需要别名
        handled: set[int] = set()      # 已经记为打补丁的 Attribute 节点，不再记读取

        text_bound = text_bound_names(tree)
        scope_of = scope_map(tree)

        def is_app(node: ast.AST) -> bool:
            if isinstance(node, ast.Name):
                if node.id not in aliases and node.id not in ALIAS_NAMES:
                    return False
                return (scope_of.get(id(node)), node.id) not in text_bound
            if isinstance(node, ast.Attribute) and node.attr in ALIAS_ATTRS                     and isinstance(node.value, ast.Name) and node.value.id in ("self", "cls"):
                return True
            if isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                return fname in ALIAS_CALLS
            return False

        def is_app_api(node: ast.AST) -> bool:
            return isinstance(node, ast.Attribute) and node.attr == "Api" and is_app(node.value)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                a = node.args
                # patch.object(app, "X", …) / setattr(app, "X", …)
                if fname in ("object", "setattr") and len(a) >= 2 \
                        and isinstance(a[1], ast.Constant) and isinstance(a[1].value, str):
                    if is_app(a[0]):
                        uses[a[1].value]["patch"].append((path, node.lineno))
                    elif is_app_api(a[0]):
                        api_uses[a[1].value]["patch"].append((path, node.lineno))
                        handled.add(id(a[0]))
                    elif isinstance(a[0], ast.Attribute) and is_app(a[0].value):
                        via_module[f"{a[0].attr}.{a[1].value}"].append((path, node.lineno))
                        handled.add(id(a[0]))
                # patch("app.X") / patch("app.Api.X")
                if fname == "patch" and a and isinstance(a[0], ast.Constant) \
                        and isinstance(a[0].value, str):
                    parts = a[0].value.split(".")
                    if parts[0] == "local":
                        parts = parts[1:]
                    if len(parts) >= 2 and parts[0] == "app":
                        if parts[1] == "Api" and len(parts) >= 3:
                            api_uses[parts[2]]["patch"].append((path, node.lineno))
                        else:
                            uses[parts[1]]["patch"].append((path, node.lineno))
            elif isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute):
                        if is_app(target.value):
                            uses[target.attr]["patch"].append((path, node.lineno))
                            handled.add(id(target))
                        elif is_app_api(target.value):
                            api_uses[target.attr]["patch"].append((path, node.lineno))
                            handled.add(id(target))
                            handled.add(id(target.value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and id(node) not in handled:
                if is_app(node.value):
                    uses[node.attr]["read"].append((path, node.lineno))
                elif is_app_api(node.value):
                    api_uses[node.attr]["read"].append((path, node.lineno))
        if aliases or any(isinstance(n, ast.Name) and is_app(n) for n in ast.walk(tree)):
            files_with_app += 1

    kinds = {"def": "自己定义（def）", "class": "自己定义（class）", "alias": "别名",
             "import": "import 进来", "value": "赋值（常量或变量）"}

    print("# app.py 模块级名字与测试的用法\n")
    counts = defaultdict(int)
    for info in names.values():
        counts[info["kind"]] += 1
    print(f"`{APP}` 模块级共 {len(names)} 个名字："
          + "、".join(f"{kinds[k]} {counts[k]} 个" for k in kinds) + "。")
    print(f"`local/tests/` 和 `tools/` 里有 {files_with_app} 个文件用到了 app 模块。\n")

    patched = {n: u for n, u in uses.items() if u["patch"]}
    print(f"## 被测试打补丁的模块级名字，共 {len(patched)} 个\n")
    print("拆 `Api` 时这些名字必须留在 `app` 模块上，并且 `Api` 的代码必须仍然经 `app` 模块的全局名字去取它们，"
          "否则补丁打不到。\n")
    print("| 名字 | 种类 | app.py 行号 | 指向 | 打补丁次数 | 文件数 | 读取次数 | 打补丁的位置（每个文件第一处）|")
    print("|---|---|---|---|---|---|---|---|")
    for name, u in sorted(patched.items(), key=lambda kv: (-len(kv[1]["patch"]), kv[0])):
        info = names.get(name)
        kind = kinds[info["kind"]] if info else "**app.py 里没有这个模块级名字**"
        line = info["line"] if info else "—"
        target = f"`{info['target']}`" if info and info["target"] else "—"
        first: dict[str, int] = {}
        for path, lineno in u["patch"]:
            first.setdefault(path, lineno)
        where = "、".join(f"`{p}:{ln}`" for p, ln in sorted(first.items()))
        print(f"| `{name}` | {kind} | {line} | {target} | {len(u['patch'])} | {len(first)} | "
              f"{len(u['read'])} | {where} |")

    read_only = {n: u for n, u in uses.items() if not u["patch"] and n in names
                 and names[n]["kind"] in ("alias", "import")}
    print(f"\n## 只被读取、没被打补丁的别名和 import 名，共 {len(read_only)} 个\n")
    print("测试经 `app.X` 取这些名字；拆分后要么留再导出，要么改测试的 import。\n")
    print("| 名字 | 种类 | app.py 行号 | 指向 | 读取次数 | 文件数 |")
    print("|---|---|---|---|---|---|")
    for name, u in sorted(read_only.items(), key=lambda kv: (-len(kv[1]["read"]), kv[0])):
        info = names[name]
        files = {p for p, _ in u["read"]}
        print(f"| `{name}` | {kinds[info['kind']]} | {info['line']} | `{info['target']}` | "
              f"{len(u['read'])} | {len(files)} |")

    unused_alias = sorted(n for n, info in names.items()
                          if info["kind"] == "alias" and n not in uses)
    print(f"\n## 测试没碰过的别名，共 {len(unused_alias)} 个\n")
    print("只统计了 `local/tests/` 和 `tools/`；`app.py` 自己内部可能在用。\n")
    print("、".join(f"`{n}`（{names[n]['line']}）" for n in unused_alias) or "—")

    own_read = {n: u for n, u in uses.items() if not u["patch"] and n in names
                and names[n]["kind"] in ("def", "class", "value")}
    print(f"\n## 只被读取的自己定义的名字，共 {len(own_read)} 个（前 40 个）\n")
    print("| 名字 | 种类 | app.py 行号 | 读取次数 | 文件数 |")
    print("|---|---|---|---|---|")
    for name, u in sorted(own_read.items(), key=lambda kv: (-len(kv[1]["read"]), kv[0]))[:40]:
        info = names[name]
        files = {p for p, _ in u["read"]}
        print(f"| `{name}` | {kinds[info['kind']]} | {info['line']} | {len(u['read'])} | {len(files)} |")

    missing = sorted(n for n in uses if n not in names)
    print(f"\n## 测试用到、但 app.py 模块级找不到的名字，共 {len(missing)} 个\n")
    print("多半是测试自己往 `app` 上挂的，或者在函数里才绑定的；逐个人工看。\n")
    print("、".join(f"`{n}`（补丁 {len(uses[n]['patch'])}，读 {len(uses[n]['read'])}）" for n in missing) or "—")

    api_patched = {n: u for n, u in api_uses.items() if u["patch"]}
    print(f"\n## 测试直接在 `app.Api` 类上打补丁的属性，共 {len(api_patched)} 个\n")
    print("| 属性 | 打补丁次数 | 位置（每个文件第一处）|")
    print("|---|---|---|")
    for name, u in sorted(api_patched.items(), key=lambda kv: (-len(kv[1]["patch"]), kv[0])):
        first = {}
        for path, lineno in u["patch"]:
            first.setdefault(path, lineno)
        print(f"| `Api.{name}` | {len(u['patch'])} | "
              + "、".join(f"`{p}:{ln}`" for p, ln in sorted(first.items())) + " |")

    print(f"\n## 测试经 app 去补别的模块（`app.模块.名字`），共 {len(via_module)} 种\n")
    print("这些补丁依赖 `app.py` 里 import 了那个模块、并且被测代码在 `app.py` 里调用它。"
          "代码搬到别的模块后，补丁仍然生效（补的是模块对象本身），但读起来会误导。\n")
    print("| 目标 | 次数 | 位置（每个文件第一处）|")
    print("|---|---|---|")
    for name, rows in sorted(via_module.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        first = {}
        for path, lineno in rows:
            first.setdefault(path, lineno)
        print(f"| `app.{name}` | {len(rows)} | "
              + "、".join(f"`{p}:{ln}`" for p, ln in sorted(first.items())) + " |")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "app_reexports.json").write_text(json.dumps(
            {"names": names, "uses": uses, "api_uses": api_uses, "via_module": via_module},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
