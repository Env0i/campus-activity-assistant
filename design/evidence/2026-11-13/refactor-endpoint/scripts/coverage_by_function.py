# -*- coding: utf-8 -*-
"""H3 的函数级覆盖：把 coverage 导出的 JSON 报告对上 local/app.py 与 local/grab.py 的函数。

口径（计划 decisions D10 H3）：
- 输入：coverage json 报告路径（命令行第一个参数，报告放在 tempfile.mkdtemp() 的临时目录）。
- 用 ast 取每个函数（含方法与嵌套函数）的行范围：从 def 行到 end_lineno（不含装饰器行）。
- 「已执行行数」不含 def 行本身（模块导入就执行 def 行，会把每个函数都算成执行过）；
  单行 def 的函数以 def 行是否执行计。
- 「一行都没执行到」= 函数体一行都没执行。经子进程启动的 worker 不在统计内（局限）。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/coverage_by_function.py <coverage.json>
"""
import ast
import json
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
TARGETS = ("local/app.py", "local/grab.py")


def function_rows(rel):
    src = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    rows = []

    def qual_of(node, parents):
        parts = []
        for p in parents:
            if isinstance(p, ast.ClassDef):
                parts.append(p.name)
            elif isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parts.append(p.name)
        return ".".join(parts + [node.name])

    def visit(node, parents):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rows.append({
                    "qual": qual_of(child, parents),
                    "def_line": child.lineno,
                    "end": child.end_lineno,
                })
                visit(child, parents + [child])
            else:
                visit(child, parents)
    visit(tree, [])
    return rows


def main():
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    # coverage 的键在 Windows 上带反斜杠；归一成正斜杠再查
    fdata = {k.replace("\\", "/"): v for k, v in report["files"].items()}

    def executed_set(rel):
        entry = fdata.get(rel)
        if entry is None:
            return None
        return set(entry["executed_lines"])

    for rel in TARGETS:
        ex = executed_set(rel)
        print(f"## {rel}")
        print()
        if ex is None:
            print("coverage 报告里没有这个文件（模块未被导入）。")
            print()
            continue
        rows = function_rows(rel)
        zero = []
        print("| 限定名 | 起止行 | 总行数（不含 def 行）| 已执行行数 |")
        print("|---|---|---|---|")
        for r in rows:
            lo, hi = r["def_line"], r["end"]
            if hi == lo:  # 单行 def
                total, done = 1, (1 if lo in ex else 0)
            else:
                total = hi - lo  # 不含 def 行
                done = sum(1 for ln in range(lo + 1, hi + 1) if ln in ex)
            if done == 0:
                zero.append(r)
            print(f"| `{r['qual']}` | {lo}-{hi} | {total} | {done} |")
        print()
        print(f"一行都没执行到的函数，共 {len(zero)} 个：")
        for r in zero:
            total = (1 if r["end"] == r["def_line"] else r["end"] - r["def_line"])
            print(f"- `{r['qual']}`（{r['def_line']}-{r['end']}，{total} 行）")
        print()


if __name__ == "__main__":
    main()
