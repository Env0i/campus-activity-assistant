# -*- coding: utf-8 -*-
"""表 D：类型标注覆盖（计划 decisions D6）。

口径：
- 用 ast 数 local 与 server 下每个 Python 文件里的函数（FunctionDef / AsyncFunctionDef，
  含方法与嵌套函数，嵌套函数单独算一条）；不含测试目录（local/tests、server/tests），
  不读 local/data、server/data、local/_site_build.py。
- 分三类：参数与返回值都标了 / 标了一部分 / 完全没标。self 与 cls 不算参数；
  *args、**kwargs 各算一个参数位；零参函数没有返回标注算「完全没标」。
- 分组按 D6 的五组；local/build 与 local 其他子目录的文件不在五组里，单列两行并记入口径疑点。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/annotations.py
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root():
    """先按「脚本位置上推四级」定位仓库根；脚本被复制到别处时改问 git。"""
    cand = HERE.parents[4] if len(HERE.parents) > 4 else None
    if cand is not None and (cand / ".git").exists():
        return cand
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    if out.returncode == 0:
        return Path(out.stdout.decode("utf-8", "replace").strip())
    raise SystemExit("定位不到仓库根：请从仓库根运行本脚本")


REPO = _repo_root()

GROUPS = (
    "local/domain",
    "local/application",
    "local/infrastructure",
    "local 根目录",
    "server",
)
BUILD_GROUP = "local/build"
OTHER_GROUP = "local 其他子目录"


def group_of(rel):
    parts = rel.split("/")
    if parts[0] == "server":
        return "server"
    if len(parts) == 2:  # local/<file>.py
        return "local 根目录"
    if parts[1] == "build":
        return BUILD_GROUP
    if parts[1] in ("domain", "application", "infrastructure"):
        return "local/" + parts[1]
    return OTHER_GROUP


def iter_files():
    for top in ("local", "server"):
        for p in sorted((REPO / top).rglob("*.py")):
            rel = p.relative_to(REPO).as_posix()
            if rel.startswith(("local/tests/", "server/tests/")):
                continue
            if rel == "local/_site_build.py":
                continue
            if "__pycache__" in rel:
                continue
            yield rel, p


def classify(fn):
    a = fn.args
    params = list(a.posonlyargs) + list(a.args)
    if params and params[0].arg in ("self", "cls"):
        params = params[1:]
    slots = params + list(a.kwonlyargs)
    if a.vararg:
        slots.append(a.vararg)
    if a.kwarg:
        slots.append(a.kwarg)
    ann = sum(1 for s in slots if s.annotation is not None)
    ret = fn.returns is not None
    if ann == 0 and not ret:
        return "none"
    if ann == len(slots) and ret:
        return "full"
    return "partial"


def main():
    files = []  # (rel, group, {none, partial, full})
    for rel, p in iter_files():
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        kinds = {"full": 0, "partial": 0, "none": 0}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kinds[classify(node)] += 1
        files.append((rel, group_of(rel), kinds))

    groups = list(GROUPS) + [BUILD_GROUP, OTHER_GROUP]
    print("## 表 D：类型标注覆盖")
    print()
    print("量什么：local 与 server 下的 Python 函数（含方法与嵌套函数；不含测试目录），"
          "按参数与返回值标注分三类；self、cls 不算参数。分组：五组照计划 D6，"
          "local/build 与 local 其他子目录的文件不在五组内，单列。")
    print()
    print("### D1 分组汇总")
    print()
    print("| 组 | 文件数 | 函数数 | 参数与返回值都标了 | 标了一部分 | 完全没标 |")
    print("|---|---|---|---|---|---|")
    for g in groups:
        rows = [r for r in files if r[1] == g]
        total = sum(sum(r[2].values()) for r in rows)
        print(f"| {g} | {len(rows)} | {total} | {sum(r[2]['full'] for r in rows)} | "
              f"{sum(r[2]['partial'] for r in rows)} | {sum(r[2]['none'] for r in rows)} |")
    rows = [r for r in files if r[1] == OTHER_GROUP]
    if rows:
        print()
        print(f"{OTHER_GROUP} 里的文件：{'、'.join(r[0] for r in rows)}。")
    print()
    print("### D2 每组函数最多的十个文件")
    print()
    print("| 组 | 文件 | 函数数 | 都标了 | 一部分 | 完全没标 |")
    print("|---|---|---|---|---|---|")
    for g in groups:
        rows = [r for r in files if r[1] == g]
        rows.sort(key=lambda r: (-sum(r[2].values()), r[0]))
        for rel, _, kinds in rows[:10]:
            n = sum(kinds.values())
            print(f"| {g} | `{rel}` | {n} | {kinds['full']} | {kinds['partial']} | {kinds['none']} |")
    print()
    print(f"全部函数合计：{sum(sum(r[2].values()) for r in files)}；"
          f"都标了 {sum(r[2]['full'] for r in files)}、一部分 {sum(r[2]['partial'] for r in files)}、"
          f"完全没标 {sum(r[2]['none'] for r in files)}。")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/annotations.py`")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
