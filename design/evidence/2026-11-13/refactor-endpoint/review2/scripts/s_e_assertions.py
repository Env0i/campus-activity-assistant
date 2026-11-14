# -*- coding: utf-8 -*-
"""review2 表 E 独立复算：字面断言三类计数与抽样（计划 D7 口径原文重读后实现）。

口径要点：五种断言调用的直接实参（位置+关键字）里的字符串；先命中先算——
含 aria-/role=/alt=/title= 为无障碍名称；去空白与标点（Unicode P*）后全是汉字、
数字或全角符号（FF 段符号类，＝＋＜＞）为文案；否则源码形状。种子 20261113。

从仓库根运行：python -B design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_e_assertions.py
"""
import ast
import os
import random
import re
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
cand = HERE.parents[5] if len(HERE.parents) > 5 else None
if cand and (cand / ".git").exists():
    REPO = cand
else:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    REPO = Path(out.stdout.decode().strip())

ASSERTS = {"assertIn", "assertNotIn", "assertRegex", "assertNotRegex", "assertEqual"}
BARRIER = ("aria-", "role=", "alt=", "title=")


def is_fullwidth_symbol(ch):
    return 0xFF00 <= ord(ch) <= 0xFFEF and unicodedata.category(ch).startswith("S")


def classify(s):
    if any(w in s for w in BARRIER):
        return "barrier"
    kept = [c for c in s if not c.isspace()
            and not unicodedata.category(c).startswith("P")]
    if kept and all(("\u4e00" <= c <= "\u9fff") or c.isdigit() or is_fullwidth_symbol(c)
                    for c in kept):
        return "copy"
    return "shape"


def main():
    tests = REPO / "local" / "tests"
    paths = sorted(tests.glob("test_ui_*.py")) + [tests / "test_phone_ui.py"]
    per_file, items = [], []
    for p in paths:
        rel = p.relative_to(REPO).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        found, sandbox = [], 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else None)
                if name in ASSERTS:
                    for arg in list(node.args) + list(node.keywords):
                        v = arg.value if isinstance(arg, ast.keyword) else arg
                        if isinstance(v, ast.Constant) and isinstance(v.value, str):
                            found.append((node.lineno, v.value))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                if any(isinstance(c, ast.Call) and (
                        getattr(c.func, "id", None) == "run_js"
                        or getattr(c.func, "attr", None) == "run_js")
                        for c in ast.walk(node)):
                    sandbox += 1
        counts = {"barrier": 0, "copy": 0, "shape": 0}
        for ln, lit in found:
            cls = classify(lit)
            counts[cls] += 1
            items.append((rel, ln, lit, cls))
        per_file.append((rel, counts, len(found), sandbox))
    total = len(items)
    print("## review2 表 E 独立复算")
    print()
    print("| 文件 | 无障碍名称 | 文案 | 源码形状 | 合计 | node 沙箱测试函数 |")
    print("|---|---|---|---|---|---|")
    for rel, c, n, sb in per_file:
        print(f"| `{rel}` | {c['barrier']} | {c['copy']} | {c['shape']} | {n} | {sb} |")
    s = {k: sum(r[1][k] for r in per_file) for k in ("barrier", "copy", "shape")}
    print(f"| 合计 | {s['barrier']} | {s['copy']} | {s['shape']} | {total} | "
          f"{sum(r[3] for r in per_file)} |")
    print()
    print(f"自校：三类之和 {s['barrier'] + s['copy'] + s['shape']} = 收集总数 {total} -> "
          f"{'成立' if s['barrier'] + s['copy'] + s['shape'] == total else '不成立'}")
    print()
    names = {"barrier": "无障碍名称", "copy": "文案", "shape": "源码形状"}
    print("### 三类抽样各 20（random.Random(20261113)，按 文件+行号+字面量 排序后抽）")
    print()
    print("| 类别 | 文件:行号 | 原文 |")
    print("|---|---|---|")
    for cls in ("barrier", "copy", "shape"):
        pool = sorted((i for i in items if i[3] == cls), key=lambda i: (i[0], i[1], i[2]))
        for rel, ln, lit, _ in random.Random(20261113).sample(pool, min(20, len(pool))):
            disp = lit.replace("|", chr(92) + "|").replace("\n", chr(92) + "n")
            print(f"| {names[cls]} | `{rel}:{ln}` | `{disp}` |")


if __name__ == "__main__":
    main()
