# -*- coding: utf-8 -*-
"""数 Python 里的隐式状态（README「C1 ④」的前两种）。

从仓库根运行：
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/py_state.py

三部分：
A. 模块级可变全局（local/ 与 server/，不含测试和 build）：
   (a) 函数里 global X 之后赋值的；(b) 模块级名字被原地修改的（下标赋值、del、变更方法）。
B. local/app.py 的 class Api：每个 self.xxx 在哪些方法里赋值、原地修改、读取。
   门槛：赋值的方法数 ≥ 3（__init__ 算一个；嵌套函数算在所在方法头上）。
C. 测试直接改写 Api 实例私有属性的位置（api._x = …、patch.object(api, "_x")）：
   这些属性名是测试的注入缝，拆 Api 时要么保留，要么同步改测试。
只读，只用标准库。按名字匹配，不做别名分析：把容器赋给别的名字再改的数不到。
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

MUTATORS = {"append", "extend", "insert", "remove", "pop", "clear", "update", "setdefault",
            "add", "discard", "popitem", "sort", "reverse", "appendleft", "popleft"}
APP = "local/app.py"


def tracked(roots: list[str]) -> list[str]:
    out = subprocess.run(["git", "ls-files", *roots], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return sorted(f for f in out.splitlines() if f.endswith(".py"))


def is_test(path: str) -> bool:
    parts = path.split("/")
    return "tests" in parts[:-1] or parts[-1].startswith("test_")


def func_spans(tree: ast.AST) -> list[tuple[int, int, str]]:
    """所有函数的（起，止，限定名），用来回答「这一行在哪个函数里」。"""
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = prefix + child.name
                if not isinstance(child, ast.ClassDef):
                    spans.append((child.lineno, child.end_lineno, qual))
                walk(child, qual + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    return spans


def where(spans: list[tuple[int, int, str]], line: int) -> str:
    """最内层函数名；不在函数里就是「模块级」。"""
    best = None
    for start, end, name in spans:
        if start <= line <= end and (best is None or start >= best[0]):
            best = (start, name)
    return best[1] if best else "<模块级>"


def value_kind(node: ast.AST | None) -> str:
    if node is None:
        return "（只有注解）"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Set):
        return "set"
    if isinstance(node, ast.Constant):
        return repr(node.value) if not isinstance(node.value, str) else "str"
    if isinstance(node, ast.Call):
        fn = node.func
        return (fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "call")) + "()"
    return type(node).__name__


def module_globals(path: str) -> list[dict]:
    """A 部分：一个模块里的可变全局。"""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    spans = func_spans(tree)
    # 模块级绑定：名字 → (行号, 初值种类)
    bound: dict[str, tuple[int, str]] = {}

    def collect(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id not in bound:
                        bound[target.id] = (node.lineno, value_kind(node.value))
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                collect(node.body)
                collect(getattr(node, "orelse", []) or [])
                collect(getattr(node, "finalbody", []) or [])
                for handler in getattr(node, "handlers", []) or []:
                    collect(handler.body)

    collect(tree.body)

    writes: dict[str, list[tuple[int, str, str]]] = defaultdict(list)   # 名字 → (行, 函数, 方式)
    reads: dict[str, set[str]] = defaultdict(set)                        # 名字 → 读它的函数

    # (a) global 声明 + 赋值
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        declared: set[str] = set()
        for inner in ast.walk(node):
            if isinstance(inner, ast.Global):
                declared.update(inner.names)
        if not declared:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = inner.targets if isinstance(inner, ast.Assign) else [inner.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id in declared:
                        writes[target.id].append((inner.lineno, where(spans, inner.lineno),
                                                  "global 赋值"))

    # (b) 原地修改：X[k] = …、del X[k]、X.append(…) 等
    def base_name(node: ast.AST) -> str:
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            node = node.value
        return node.id if isinstance(node, ast.Name) else ""

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, (ast.Subscript, ast.Attribute)):
                    name = base_name(target)
                    if name in bound:
                        how = "下标赋值" if isinstance(target, ast.Subscript) else "属性赋值"
                        writes[name].append((node.lineno, where(spans, node.lineno), how))
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    name = base_name(target)
                    if name in bound:
                        writes[name].append((node.lineno, where(spans, node.lineno), "del"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in MUTATORS and isinstance(node.func.value, ast.Name):
            name = node.func.value.id
            if name in bound:
                writes[name].append((node.lineno, where(spans, node.lineno),
                                     f".{node.func.attr}()"))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in bound:
            reads[node.id].add(where(spans, node.lineno))

    rows = []
    for name, sites in writes.items():
        if name not in bound:
            # global 声明了却没有模块级初值：也算，行号取第一次写
            bound[name] = (sites[0][0], "（函数里首次赋值）")
        # 属性赋值里，接收者是模块（例如 time.x = …）的不算状态；这里只留容器和 global
        kinds = {how for _, _, how in sites}
        if kinds == {"属性赋值"} and bound[name][1] not in ("dict", "list", "set"):
            # 模块级对象的属性被改：仍然列出，但标明
            pass
        rows.append({"file": path, "name": name, "line": bound[name][0], "init": bound[name][1],
                     "writes": sorted(set(sites)), "readers": sorted(reads.get(name, set()))})
    return rows


def api_attributes() -> tuple[list[dict], int]:
    """B 部分：class Api 的 self 属性。"""
    tree = ast.parse(Path(APP).read_text(encoding="utf-8"), filename=APP)
    api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
    attrs: dict[str, dict] = defaultdict(lambda: {"assign": defaultdict(list),
                                                  "mutate": defaultdict(list),
                                                  "read": defaultdict(list)})
    methods = [n for n in api.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    def self_attr(node: ast.AST) -> str:
        """self.x → "x"；self.x[k]、self.x.y → 也回 "x"（取紧挨 self 的那一段）。"""
        while isinstance(node, (ast.Subscript, ast.Attribute)):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "self":
                return node.attr
            node = node.value
        return ""

    for method in methods:
        stored: set[int] = set()
        for node in ast.walk(method):
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                flat = []
                for target in targets:
                    flat.extend(target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target])
                for target in flat:
                    direct = isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) \
                        and target.value.id == "self"
                    if direct:
                        attrs[target.attr]["assign"][method.name].append(node.lineno)
                        stored.add(id(target))
                    else:
                        name = self_attr(target)
                        if name:
                            attrs[name]["mutate"][method.name].append(node.lineno)
            elif isinstance(node, ast.Delete):
                for target in node.targets:
                    name = self_attr(target)
                    if name:
                        attrs[name]["mutate"][method.name].append(node.lineno)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in MUTATORS:
                recv = node.func.value
                if isinstance(recv, ast.Attribute) and isinstance(recv.value, ast.Name) \
                        and recv.value.id == "self":
                    attrs[recv.attr]["mutate"][method.name].append(node.lineno)
        for node in ast.walk(method):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "self" and isinstance(node.ctx, ast.Load):
                attrs[node.attr]["read"][method.name].append(node.lineno)

    method_names = {m.name for m in methods}
    rows = []
    for name, info in attrs.items():
        if name in method_names and not info["assign"]:
            continue        # self.方法() 的调用，不是状态
        rows.append({"name": name,
                     "assign": {k: sorted(set(v)) for k, v in info["assign"].items()},
                     "mutate": {k: sorted(set(v)) for k, v in info["mutate"].items()},
                     "read": {k: sorted(set(v)) for k, v in info["read"].items()}})
    return rows, len(methods)


def test_writes_to_api() -> dict[str, list[tuple[str, int]]]:
    """C 部分：测试里改写 Api 实例属性的位置。接收者按名字认：api、self.api、self._api。"""
    found: dict[str, list[tuple[str, int]]] = defaultdict(list)

    def is_api(node: ast.AST) -> bool:
        if isinstance(node, ast.Name):
            return node.id in ("api", "_api")
        return isinstance(node, ast.Attribute) and node.attr in ("api", "_api") \
            and isinstance(node.value, ast.Name) and node.value.id in ("self", "cls")

    for path in tracked(["local/tests", "tools"]):
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Attribute) and is_api(target.value):
                        found[target.attr].append((path, node.lineno))
            elif isinstance(node, ast.Call):
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                a = node.args
                if fname in ("object", "setattr") and len(a) >= 2 and is_api(a[0]) \
                        and isinstance(a[1], ast.Constant) and isinstance(a[1].value, str):
                    found[a[1].value].append((path, node.lineno))
    return found


def external_writes(api_attr_names: set[str]) -> list[dict]:
    """B 的补充：application/、infrastructure/ 里，对「不是 self 的对象」的属性赋值，
    并且属性名和 Api 的某个下划线属性同名。这些是服务从外面改写 Api 的状态
    （Api 把自己当参数传了进去）。按名字认，接收者一并列出供人工判断。"""
    rows: list[dict] = []
    files = [f for f in tracked(["local/application", "local/infrastructure", "local/domain"])]
    for path in files:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
        spans = func_spans(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) \
                        and target.value.id != "self" and target.attr.startswith("_") \
                        and target.attr in api_attr_names:
                    rows.append({"file": path, "line": node.lineno, "receiver": target.value.id,
                                 "attr": target.attr, "fn": where(spans, node.lineno)})
    return rows


def fmt_methods(mapping: dict[str, list[int]], limit: int = 12) -> str:
    items = sorted(mapping.items(), key=lambda kv: kv[1][0])
    text = "、".join(f"`{name}`:{','.join(str(n) for n in lines[:3])}{'…' if len(lines) > 3 else ''}"
                    for name, lines in items[:limit])
    return text + (f" 等 {len(items)} 个" if len(items) > limit else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # ---- A ----
    files = [f for f in tracked(["local", "server"]) if not is_test(f) and "/build/" not in f]
    all_rows: list[dict] = []
    for path in files:
        all_rows.extend(module_globals(path))
    print("# Python 隐式状态\n")
    print(f"## A. 模块级可变全局（扫了 {len(files)} 个文件，共 {len(all_rows)} 个）\n")
    print("| 定义位置 | 名字 | 初值 | 写的位置（函数:行 方式）| 读它的函数数 |")
    print("|---|---|---|---|---|")
    for row in sorted(all_rows, key=lambda r: (r["file"], r["line"])):
        sites = "；".join(f"`{fn}`:{line} {how}" for line, fn, how in row["writes"][:8])
        if len(row["writes"]) > 8:
            sites += f" 等 {len(row['writes'])} 处"
        print(f"| `{row['file']}:{row['line']}` | `{row['name']}` | {row['init']} | {sites} | "
              f"{len(row['readers'])} |")

    # ---- B ----
    api_rows, n_methods = api_attributes()
    flagged = [r for r in api_rows if len(r["assign"]) >= 3]
    print(f"\n## B. `Api` 实例属性（`{APP}`，{n_methods} 个方法，{len(api_rows)} 个属性）\n")
    by_count = defaultdict(int)
    for r in api_rows:
        by_count[min(len(r["assign"]), 5)] += 1
    print("赋值方法数的分布："
          + "、".join(f"{'≥5' if k == 5 else k} 个方法：{by_count[k]} 个属性" for k in sorted(by_count))
          + "。\n")
    print(f"### 在 3 个及以上方法里赋值的属性，共 {len(flagged)} 个\n")
    print("| 属性 | 赋值的方法数 | 赋值的位置（方法:行）| 原地修改的方法数 | 读的方法数 |")
    print("|---|---|---|---|---|")
    for r in sorted(flagged, key=lambda r: (-len(r["assign"]), r["name"])):
        print(f"| `self.{r['name']}` | {len(r['assign'])} | {fmt_methods(r['assign'])} | "
              f"{len(r['mutate'])} | {len(r['read'])} |")

    two = [r for r in api_rows if len(r["assign"]) == 2]
    print(f"\n### 在 2 个方法里赋值的属性，共 {len(two)} 个\n")
    print("| 属性 | 赋值的位置（方法:行）| 原地修改的方法数 | 读的方法数 |")
    print("|---|---|---|---|")
    for r in sorted(two, key=lambda r: r["name"]):
        print(f"| `self.{r['name']}` | {fmt_methods(r['assign'])} | {len(r['mutate'])} | "
              f"{len(r['read'])} |")

    containers = [r for r in api_rows if len(r["assign"]) < 3 and len(r["mutate"]) >= 3]
    print(f"\n### 只在一两处赋值、但在 3 个及以上方法里原地修改的容器，共 {len(containers)} 个\n")
    print("| 属性 | 原地修改的位置（方法:行）| 读的方法数 |")
    print("|---|---|---|")
    for r in sorted(containers, key=lambda r: (-len(r["mutate"]), r["name"])):
        print(f"| `self.{r['name']}` | {fmt_methods(r['mutate'])} | {len(r['read'])} |")

    readers = sorted(api_rows, key=lambda r: -len(r["read"]))[:15]
    print("\n### 被最多方法读取的 15 个属性\n")
    print("| 属性 | 读的方法数 | 赋值的方法数 |")
    print("|---|---|---|")
    for r in readers:
        print(f"| `self.{r['name']}` | {len(r['read'])} | {len(r['assign'])} |")

    ext = external_writes({r["name"] for r in api_rows})
    print(f"\n### 别的模块从外面改写 `Api` 属性的位置，共 {len(ext)} 处\n")
    print("`Api` 把自己当参数传给服务，服务直接给它的下划线属性赋值。上面几张表只数了 `Api` 自己的方法，"
          "这些要加上才是全部写入点。\n")
    print("| 位置 | 所在函数 | 接收者 | 属性 |")
    print("|---|---|---|---|")
    for row in sorted(ext, key=lambda r: (r["file"], r["line"])):
        print(f"| `{row['file']}:{row['line']}` | `{row['fn']}` | `{row['receiver']}` | `{row['attr']}` |")

    # ---- C ----
    test_writes = test_writes_to_api()
    known = {r["name"] for r in api_rows}
    tree = ast.parse(Path(APP).read_text(encoding="utf-8"))
    api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
    method_names = {n.name for n in api.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    print(f"\n## C. 测试改写 `Api` 实例成员的位置（{len(test_writes)} 个名字）\n")
    print("接收者按名字认（`api`、`self.api`、`self._api`）。「是什么」一列对照 `Api` 的方法名和属性名。\n")
    print("| 名字 | 是什么 | 次数 | 文件数 | 位置（每个文件第一处）|")
    print("|---|---|---|---|---|")
    for name, sites in sorted(test_writes.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        kind = "方法" if name in method_names else ("属性" if name in known else "Api 里没有")
        first: dict[str, int] = {}
        for path, line in sites:
            first.setdefault(path, line)
        print(f"| `{name}` | {kind} | {len(sites)} | {len(first)} | "
              + "、".join(f"`{p}:{ln}`" for p, ln in sorted(first.items())[:6])
              + (" 等" if len(first) > 6 else "") + " |")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "py_state.json").write_text(json.dumps(
            {"module_globals": all_rows, "api_attrs": api_rows, "external_writes": ext,
             "test_writes": test_writes},
            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
