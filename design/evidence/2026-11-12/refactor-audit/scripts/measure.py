# -*- coding: utf-8 -*-
"""量文件行数和函数行数的分布（README「C1 ③」）。

从仓库根运行：
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/measure.py
    py -3.12 design/evidence/2026-11-12/refactor-audit/scripts/measure.py --out <tempfile.mkdtemp() 建的空目录>

只读，不联网，只用标准库；JS 部分调同目录的 jsfuncs.mjs（需要 node）。
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 只看这三个目录下受版本管理的源码；数据目录、配置和构建产物不在 git 里，自然不会进来。
ROOTS = ("local", "server", "tools")
EXTS = (".py", ".js", ".mjs")


def tracked_files() -> list[str]:
    """git ls-files 给出的源码文件，路径用正斜杠。"""
    out = subprocess.run(["git", "ls-files", *ROOTS], capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return sorted(f for f in files if f.endswith(EXTS))


def is_test(path: str) -> bool:
    """测试：在 tests/ 目录里，或者文件名以 test_ 开头。"""
    parts = path.split("/")
    return "tests" in parts[:-1] or parts[-1].startswith("test_")


def group_of(path: str) -> str:
    lang = "py" if path.endswith(".py") else "js"
    return f"{lang}-{'test' if is_test(path) else 'product'}"


def count_lines(text: str) -> int:
    """物理行数，和 wc -l 一致；末行没有换行时补一行。"""
    n = text.count("\n")
    return n + 1 if text and not text.endswith("\n") else n


def python_units(path: str, text: str) -> list[dict]:
    """用 ast 量每个函数和类：def/class 那一行到最后一行，不含装饰器。嵌套的单独算。"""
    tree = ast.parse(text, filename=path)
    units: list[dict] = []

    def walk(node: ast.AST, prefix: str, depth: int) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                qual = f"{prefix}{child.name}"
                units.append({"file": path, "name": qual, "kind": kind,
                              "start": child.lineno, "end": child.end_lineno,
                              "lines": child.end_lineno - child.lineno + 1, "depth": depth})
                walk(child, qual + ".", depth + 1)
            else:
                walk(child, prefix, depth)

    walk(tree, "", 0)
    return units


def js_units(paths: list[str]) -> tuple[list[dict], list[str]]:
    """调 jsfuncs.mjs 量 JS 函数；返回函数清单和括号没配平的文件。"""
    if not paths:
        return [], []
    proc = subprocess.run(["node", str(HERE / "jsfuncs.mjs"), *paths], capture_output=True,
                          text=True, encoding="utf-8", check=True)
    units, unbalanced = [], []
    for entry in json.loads(proc.stdout):
        if not entry["balanced"]:
            unbalanced.append(entry["file"])
        for fn in entry["functions"]:
            units.append({"file": entry["file"], "name": fn["name"], "kind": fn["kind"],
                          "start": fn["start"], "end": fn["end"], "lines": fn["lines"],
                          "depth": fn["depth"]})
    return units, unbalanced


def percentile(values: list[int], p: float) -> int:
    """最近秩法：排序后第 ceil(p × n) 个。"""
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, math.ceil(p * len(ordered)))
    return ordered[rank - 1]


def dist(values: list[int]) -> dict:
    return {"n": len(values), "sum": sum(values), "p50": percentile(values, 0.50),
            "p90": percentile(values, 0.90), "p99": percentile(values, 0.99),
            "max": max(values) if values else 0}


BUCKETS = [(0, 99), (100, 199), (200, 399), (400, 799), (800, 1499), (1500, 10 ** 9)]
FUNC_BUCKETS = [(1, 10), (11, 20), (21, 40), (41, 60), (61, 100), (101, 10 ** 9)]


def bucket_counts(values: list[int], buckets) -> list[int]:
    return [sum(1 for v in values if lo <= v <= hi) for lo, hi in buckets]


def bucket_label(lo: int, hi: int) -> str:
    return f"≥{lo}" if hi >= 10 ** 9 else f"{lo}–{hi}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="另存 JSON 的目录（用 tempfile.mkdtemp() 新建的空目录）")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    files = tracked_files()
    file_rows: list[dict] = []
    units: list[dict] = []
    js_paths: list[str] = []
    for path in files:
        text = Path(path).read_text(encoding="utf-8")
        file_rows.append({"file": path, "lines": count_lines(text), "group": group_of(path)})
        if path.endswith(".py"):
            units.extend(python_units(path, text))
        else:
            js_paths.append(path)
    js, unbalanced = js_units(js_paths)
    units.extend(js)
    for unit in units:
        unit["group"] = group_of(unit["file"])

    groups = ["py-product", "js-product", "py-test", "js-test"]
    titles = {"py-product": "产品 Python", "js-product": "产品 JS",
              "py-test": "测试 Python", "js-test": "测试 JS"}
    # 另出两个子集，定参考值时主要看它们：本机版的产品代码。
    subsets = {
        "py-local": ("本机版 Python（local/，不含测试）",
                     lambda f: f.startswith("local/") and f.endswith(".py") and not is_test(f)),
        "js-local-ui": ("本机版前端（local/ui/）",
                        lambda f: f.startswith("local/ui/") and not is_test(f)),
    }

    print(f"# 大小分布（{len(files)} 个文件）\n")
    if unbalanced:
        print("**括号没配平的 JS 文件（函数行数不可信）**：" + "、".join(unbalanced) + "\n")
    else:
        print("JS 文件括号全部配平。\n")

    print("## 文件行数\n")
    print("| 组 | 文件数 | 总行数 | P50 | P90 | P99 | 最大 | "
          + " | ".join(bucket_label(*b) for b in BUCKETS) + " |")
    print("|---|---|---|---|---|---|---|" + "---|" * len(BUCKETS))
    summary: dict = {"files": {}, "functions": {}, "classes": {}}

    def file_line(title: str, rows: list[dict]) -> dict:
        values = [r["lines"] for r in rows]
        d = dist(values)
        print(f"| {title} | {d['n']} | {d['sum']} | {d['p50']} | {d['p90']} | {d['p99']} | "
              f"{d['max']} | " + " | ".join(str(c) for c in bucket_counts(values, BUCKETS)) + " |")
        return d

    for g in groups:
        summary["files"][g] = file_line(titles[g], [r for r in file_rows if r["group"] == g])
    for key, (title, pred) in subsets.items():
        summary["files"][key] = file_line(title, [r for r in file_rows if pred(r["file"])])

    print("\n### 400 行以上的文件\n")
    print("| 行数 | 文件 | 组 |")
    print("|---|---|---|")
    for row in sorted(file_rows, key=lambda r: -r["lines"]):
        if row["lines"] >= 400:
            print(f"| {row['lines']} | `{row['file']}` | {titles[row['group']]} |")

    print("\n## 函数行数（类单独列在后面）\n")
    print("| 组 | 函数数 | P50 | P90 | P99 | 最大 | "
          + " | ".join(bucket_label(*b) for b in FUNC_BUCKETS) + " |")
    print("|---|---|---|---|---|---|" + "---|" * len(FUNC_BUCKETS))

    def func_line(title: str, rows: list[dict]) -> dict:
        values = [u["lines"] for u in rows]
        d = dist(values)
        print(f"| {title} | {d['n']} | {d['p50']} | {d['p90']} | {d['p99']} | {d['max']} | "
              + " | ".join(str(c) for c in bucket_counts(values, FUNC_BUCKETS)) + " |")
        return d

    funcs = [u for u in units if u["kind"] != "class"]
    classes = [u for u in units if u["kind"] == "class"]
    for g in groups:
        summary["functions"][g] = func_line(titles[g], [u for u in funcs if u["group"] == g])
    for key, (title, pred) in subsets.items():
        summary["functions"][key] = func_line(title, [u for u in funcs if pred(u["file"])])

    for g in groups:
        rows = [u for u in funcs if u["group"] == g]
        p99 = summary["functions"][g]["p99"]
        over = sorted((u for u in rows if u["lines"] > p99), key=lambda u: -u["lines"])
        print(f"\n### {titles[g]}：超过本组 P99（{p99} 行）的函数，共 {len(over)} 个\n")
        print("| 行数 | 位置 | 名字 |")
        print("|---|---|---|")
        for u in over:
            print(f"| {u['lines']} | `{u['file']}:{u['start']}-{u['end']}` | `{u['name']}` |")

    print("\n## 产品代码里 60 行以上的函数（按文件汇总）\n")
    print("| 文件 | 60 行以上 | 100 行以上 | 最长 |")
    print("|---|---|---|---|")
    per_file: dict[str, list[dict]] = {}
    for u in funcs:
        if u["group"].endswith("product") and u["lines"] > 60:
            per_file.setdefault(u["file"], []).append(u)
    for path, rows in sorted(per_file.items(), key=lambda kv: -len(kv[1])):
        longest = max(rows, key=lambda u: u["lines"])
        print(f"| `{path}` | {len(rows)} | {sum(1 for u in rows if u['lines'] > 100)} | "
              f"`{longest['name']}` {longest['lines']} 行 |")

    print("\n## Python 类行数\n")
    print("| 组 | 类数 | P50 | P90 | P99 | 最大 |")
    print("|---|---|---|---|---|---|")
    for g in ("py-product", "py-test"):
        values = [u["lines"] for u in classes if u["group"] == g]
        d = dist(values)
        summary["classes"][g] = d
        print(f"| {titles[g]} | {d['n']} | {d['p50']} | {d['p90']} | {d['p99']} | {d['max']} |")
    print("\n### 产品 Python 里 200 行以上的类\n")
    print("| 行数 | 位置 | 类 | 方法数 |")
    print("|---|---|---|---|")
    for u in sorted(classes, key=lambda u: -u["lines"]):
        if u["group"] == "py-product" and u["lines"] >= 200:
            methods = sum(1 for f in funcs if f["file"] == u["file"] and f["depth"] == u["depth"] + 1
                          and f["name"].startswith(u["name"] + ".")
                          and "." not in f["name"][len(u["name"]) + 1:])
            print(f"| {u['lines']} | `{u['file']}:{u['start']}-{u['end']}` | `{u['name']}` | {methods} |")

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "measure.json").write_text(
            json.dumps({"files": file_rows, "units": units, "summary": summary},
                       ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
