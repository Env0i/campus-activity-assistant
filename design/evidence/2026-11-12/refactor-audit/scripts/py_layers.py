# -*- coding: utf-8 -*-
"""数 local/ 后端的跨层 import（README「C1 ② 后端」）。

从仓库根运行：
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/py_layers.py

口径：
- 层按目录定：domain / application / infrastructure；local/ 下其余模块记为「顶层」。
- 允许：domain → domain；application → domain、application；
        infrastructure → domain、infrastructure；顶层 → 都可以。
- 函数体里的延迟 import 也算；标准库和第三方包不算。
- importlib.import_module("…")、__import__("…") 这类字符串 import 单独列出，供人工看。
只读，只用标准库。
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

LAYERS = ("domain", "application", "infrastructure")
ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "infrastructure"},
    "top": {"domain", "application", "infrastructure", "top"},
}


def tracked_local_py() -> list[str]:
    out = subprocess.run(["git", "ls-files", "local"], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    return sorted(f for f in out.splitlines()
                  if f.endswith(".py") and "/tests/" not in f and "/build/" not in f)


def layer_of_path(path: str) -> str:
    parts = path.split("/")
    return parts[1] if len(parts) > 2 and parts[1] in LAYERS else "top"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    files = tracked_local_py()
    # 本仓库自己的模块名 → 层。顶层模块按文件名记（app、grab、signup_plan …）。
    local_modules: dict[str, str] = {}
    for path in files:
        parts = path.split("/")
        if layer_of_path(path) == "top" and len(parts) == 2:
            local_modules[parts[1][:-3]] = "top"
    for layer in LAYERS:
        local_modules[layer] = layer

    # test_layer_boundaries 的黑名单：直接从测试文件里读出来，免得两边抄错。
    banned: set[str] = set()
    test_tree = ast.parse(Path("local/tests/test_layer_boundaries.py").read_text(encoding="utf-8"))
    for node in ast.walk(test_tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "BANNED_MODULES" for t in node.targets):
            banned = {elt.value for elt in node.value.elts if isinstance(elt, ast.Constant)}

    edges: list[dict] = []
    dynamic: list[dict] = []
    for path in files:
        src_layer = layer_of_path(path)
        tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
        # 记下每个节点是不是在函数体里（延迟 import）
        lazy_lines: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for inner in ast.walk(node):
                    if isinstance(inner, (ast.Import, ast.ImportFrom)):
                        lazy_lines.add(inner.lineno)
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:      # 相对 import：按所在包算
                    base = path.split("/")[1:-1]
                    base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                    module = ".".join([*base, node.module] if node.module else base)
                    if not module:      # from . import x → 顶层模块 x
                        targets = [alias.name for alias in node.names]
                    else:
                        targets = [module]
                else:
                    targets = [node.module or ""]
                    # from local import app / from local.domain import x
                    if node.module in ("local",):
                        targets = [alias.name for alias in node.names]
                    # from domain import a, b → 展开成 domain.a、domain.b，一个名字算一条
                    elif node.module in LAYERS or node.module in tuple("local." + x for x in LAYERS):
                        targets = [f"{node.module}.{alias.name}" for alias in node.names]
            elif isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name in ("import_module", "__import__") and node.args:
                    arg = node.args[0]
                    dynamic.append({"file": path, "line": node.lineno, "call": name,
                                    "arg": arg.value if isinstance(arg, ast.Constant) else "<表达式>"})
                continue
            else:
                continue
            for target in targets:
                parts = [p for p in target.split(".") if p]
                if parts and parts[0] == "local":
                    parts = parts[1:]
                if not parts or parts[0] not in local_modules:
                    continue        # 标准库或第三方
                dst_layer = local_modules[parts[0]]
                edges.append({
                    "file": path, "line": node.lineno, "from_layer": src_layer,
                    "module": ".".join(parts), "to_layer": dst_layer,
                    "lazy": node.lineno in lazy_lines,
                    "allowed": dst_layer in ALLOWED[src_layer],
                    # 这一条会不会被 test_layer_boundaries 拦住：它只看 domain / application
                    # 的 import，并且只拦黑名单里的第一段模块名。
                    "guarded": src_layer in ("domain", "application") and parts[0] in banned,
                })

    print("# 后端跨层 import\n")
    print(f"扫了 {len(files)} 个文件（local/ 下非测试、非 build）。"
          f"`test_layer_boundaries` 的黑名单：{', '.join(sorted(banned))}。\n")

    print("## 各层之间的 import 条数\n")
    order = ["domain", "application", "infrastructure", "top"]
    print("| 从 ＼ 到 | " + " | ".join(order) + " |")
    print("|---|" + "---|" * len(order))
    for src in order:
        cells = []
        for dst in order:
            n = sum(1 for e in edges if e["from_layer"] == src and e["to_layer"] == dst)
            mark = "" if dst in ALLOWED[src] else "（越界）"
            cells.append(f"{n}{mark if n else ''}")
        print(f"| {src} | " + " | ".join(cells) + " |")

    bad = [e for e in edges if not e["allowed"]]
    print(f"\n## 越界的 import，共 {len(bad)} 条\n")
    print("| 位置 | 从 | import 了 | 到 | 延迟 import | 现有测试拦不拦 |")
    print("|---|---|---|---|---|---|")
    for e in sorted(bad, key=lambda e: (e["file"], e["line"])):
        print(f"| `{e['file']}:{e['line']}` | {e['from_layer']} | `{e['module']}` | {e['to_layer']} | "
              f"{'是' if e['lazy'] else '否'} | {'拦' if e['guarded'] else '不拦'} |")

    print("\n## 现有测试没覆盖到的方向\n")
    print("`test_layer_boundaries` 只检查 `domain/`、`application/` 两个包，只拦黑名单里的模块名。"
          "下面这些 import 即使出现也不会让它变红：\n")
    uncovered = [
        ("domain → application", "domain", "application"),
        ("domain → infrastructure", "domain", "infrastructure"),
        ("application → infrastructure", "application", "infrastructure"),
        ("infrastructure → application", "infrastructure", "application"),
        ("infrastructure → 顶层", "infrastructure", "top"),
    ]
    print("| 方向 | 现在有几条 | 位置 |")
    print("|---|---|---|")
    for title, src, dst in uncovered:
        rows = [e for e in edges if e["from_layer"] == src and e["to_layer"] == dst]
        where = "、".join(f"`{e['file']}:{e['line']}`（`{e['module']}`）" for e in rows) or "—"
        print(f"| {title} | {len(rows)} | {where} |")

    print(f"\n## 字符串 import（{len(dynamic)} 处，人工看）\n")
    print("| 位置 | 调用 | 参数 |")
    print("|---|---|---|")
    for d in dynamic:
        print(f"| `{d['file']}:{d['line']}` | `{d['call']}` | `{d['arg']}` |")

    print("\n## 顶层模块对三层的依赖（事实，不算越界）\n")
    print("| 顶层模块 | domain | application | infrastructure | 其他顶层模块 |")
    print("|---|---|---|---|---|")
    tops = sorted({e["file"] for e in edges if e["from_layer"] == "top"})
    for path in tops:
        row = [e for e in edges if e["file"] == path]
        def names(layer: str) -> str:
            mods = sorted({e["module"].split(".")[-1] if layer != "top" else e["module"]
                           for e in row if e["to_layer"] == layer})
            return f"{len(mods)}：" + "、".join(mods) if mods else "—"
        print(f"| `{path}` | {names('domain')} | {names('application')} | "
              f"{names('infrastructure')} | {names('top')} |")

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "py_layers.json").write_text(
            json.dumps({"edges": edges, "dynamic": dynamic, "banned": sorted(banned)},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
