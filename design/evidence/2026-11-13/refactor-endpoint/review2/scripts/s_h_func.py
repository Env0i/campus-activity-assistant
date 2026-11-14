# -*- coding: utf-8 -*-
"""review2 H3 函数级复算：coverage JSON 对上 local/app.py 与 local/grab.py（计划 D10 H3）。

从仓库根运行：python -B <本文件> <coverage.json>
已执行行数不含 def 行；单行 def 以 def 行计；零执行 = 函数体一行未执行。
"""
import ast
import json
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


def rows_of(rel):
    src = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    rows = []

    def qual(node, stack):
        return ".".join([p.name for p in stack
                         if isinstance(p, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
                        + [node.name])

    def visit(node, stack):
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                rows.append({"qual": qual(ch, stack), "lo": ch.lineno, "hi": ch.end_lineno})
                visit(ch, stack + [ch])
            else:
                visit(ch, stack)
    visit(ast.parse(src), [])
    return rows


def main():
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["files"]
    norm = {k.replace("\\", "/"): v for k, v in data.items()}
    for rel in ("local/app.py", "local/grab.py"):
        ex = set(norm[rel]["executed_lines"]) if rel in norm else set()
        rows = rows_of(rel)
        zero = []
        print(f"## {rel}（coverage 文件数 {len(data)}，该文件 {'在' if rel in norm else '不在'}报告内）")
        print()
        print("| 限定名 | 起止 | 总行数(不含def) | 已执行 |")
        print("|---|---|---|---|")
        for r in rows:
            lo, hi = r["lo"], r["hi"]
            if hi == lo:
                total, done = 1, (1 if lo in ex else 0)
            else:
                total, done = hi - lo, sum(1 for x in range(lo + 1, hi + 1) if x in ex)
            if done == 0:
                zero.append((r, total))
            print(f"| `{r['qual']}` | {lo}-{hi} | {total} | {done} |")
        print()
        print(f"一行未执行函数：{len(zero)} 个")
        for r, t in zero:
            print(f"- `{r['qual']}`（{r['lo']}-{r['hi']}，{t} 行）")
        print()


if __name__ == "__main__":
    main()
