# -*- coding: utf-8 -*-
"""review2 表 D 独立复算：类型标注三类计数，五组 + build 单列（计划 D6 口径原文重读后实现）。

从仓库根运行：python -B design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_d_annotations.py
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
cand = HERE.parents[5] if len(HERE.parents) > 5 else None
if cand and (cand / ".git").exists():
    REPO = cand
else:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    REPO = Path(out.stdout.decode().strip())

GROUPS = ("local/domain", "local/application", "local/infrastructure",
          "local 根目录", "server", "local/build", "local 其他子目录")


def group_of(rel):
    parts = rel.split("/")
    if parts[0] == "server":
        return "server"
    if len(parts) == 2:
        return "local 根目录"
    if parts[1] == "build":
        return "local/build"
    if parts[1] in ("domain", "application", "infrastructure"):
        return "local/" + parts[1]
    return "local 其他子目录"


def kind(fn):
    a = fn.args
    params = list(a.posonlyargs) + list(a.args)
    if params and params[0].arg in ("self", "cls"):
        params = params[1:]
    slots = params + list(a.kwonlyargs) + ([a.vararg] if a.vararg else []) + \
        ([a.kwarg] if a.kwarg else [])
    ann = sum(1 for s in slots if s.annotation is not None)
    ret = fn.returns is not None
    if ann == 0 and not ret:
        return "none"
    return "full" if (ann == len(slots) and ret) else "partial"


def main():
    files = []
    for top in ("local", "server"):
        for p in sorted((REPO / top).rglob("*.py")):
            rel = p.relative_to(REPO).as_posix()
            if rel.startswith(("local/tests/", "server/tests/")) or "__pycache__" in rel \
                    or rel == "local/_site_build.py":
                continue
            tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
            ks = {"full": 0, "partial": 0, "none": 0}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    ks[kind(node)] += 1
            files.append((rel, group_of(rel), ks))
    print("## review2 表 D 独立复算")
    print()
    print("| 组 | 文件数 | 函数数 | 都标了 | 一部分 | 完全没标 |")
    print("|---|---|---|---|---|---|")
    for g in GROUPS:
        rows = [r for r in files if r[1] == g]
        n = sum(sum(r[2].values()) for r in rows)
        print(f"| {g} | {len(rows)} | {n} | {sum(r[2]['full'] for r in rows)} | "
              f"{sum(r[2]['partial'] for r in rows)} | {sum(r[2]['none'] for r in rows)} |")
    tot = sum(sum(r[2].values()) for r in files)
    print()
    print(f"全部函数合计：{tot}；都标了 {sum(r[2]['full'] for r in files)}、"
          f"一部分 {sum(r[2]['partial'] for r in files)}、完全没标 {sum(r[2]['none'] for r in files)}。")
    print()
    print("### 每组函数最多的十个文件")
    print()
    print("| 组 | 文件 | 函数数 | 都标 | 部分 | 没标 |")
    print("|---|---|---|---|---|---|")
    for g in GROUPS:
        rows = sorted((r for r in files if r[1] == g),
                      key=lambda r: (-sum(r[2].values()), r[0]))[:10]
        for rel, _, k in rows:
            print(f"| {g} | `{rel}` | {sum(k.values())} | {k['full']} | {k['partial']} | {k['none']} |")


if __name__ == "__main__":
    main()
