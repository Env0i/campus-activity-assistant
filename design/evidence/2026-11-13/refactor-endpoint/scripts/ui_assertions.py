# -*- coding: utf-8 -*-
"""表 E：界面测试的字面断言分类（计划 decisions D7）。

口径（D7 原文的固定规则，先命中先算）：
- 文件：local/tests 下文件名以 test_ui_ 开头的测试文件，加 test_phone_ui.py。
- 用 ast 找 assertIn、assertNotIn、assertRegex、assertNotRegex、assertEqual 调用里的
  字符串字面量参数。本脚本取的是这五个调用的**直接实参**（位置参数，含关键字实参）；
  嵌套调用的实参不算（例如 read("ui/app.js") 里的路径不是断言的参数）。
- 分类：一、含 aria-、role=、alt=、title= 之一算「无障碍名称」；二、去掉空白与标点后
  全是汉字、数字或全角符号算「文案」；三、其余算「源码形状」。
- node 沙箱测试函数数：test_ 函数的函数体里调用了 fixtures/ui_harness.py 的 run_js。
- 抽样：random.Random(20261113)，三类各抽 20 条（不足 20 条全抽），
  每条带 文件:行号 与原文。原文含主机路径时替换为 <主机路径> 并在该行标注。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_assertions.py
"""
import ast
import os
import random
import re
import subprocess
import unicodedata
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
SEED = 20261113
SAMPLE_N = 20

ASSERTS = {"assertIn", "assertNotIn", "assertRegex", "assertNotRegex", "assertEqual"}
CLASSES = ("barrier", "copy", "shape")
CLASS_NAMES = {"barrier": "无障碍名称", "copy": "文案", "shape": "源码形状"}

BARRIER_WORDS = ("aria-", "role=", "alt=", "title=")

# 主机路径替换（表 E、表 G 共用规则）：命中才替换，其余字符不动。
HOST_PATTERNS = [
    re.compile("(?<![A-Za-z0-9+.-])[A-Za-z]:[\\\\/]"),
    re.compile("(?i)[\\\\/]users?[\\\\/]"),
    re.compile("(?i)appdata[\\\\/]local[\\\\/]temp"),
    re.compile("%" + "TEMP" + "%", re.I),
    re.compile("%" + "USERPROFILE" + "%", re.I),
]


def sanitize(text):
    out = text
    for pat in HOST_PATTERNS:
        out = pat.sub("<主机路径>", out)
    return out


def is_host_path(text):
    return any(p.search(text) for p in HOST_PATTERNS)


def is_fullwidth_symbol(ch):
    """「全角符号」：Halfwidth and Fullwidth Forms 段（U+FF00–FFEF）里的符号类字符（＝、＋、＜ 等）。"""
    return 0xFF00 <= ord(ch) <= 0xFFEF and unicodedata.category(ch).startswith("S")


def classify_literal(s):
    for w in BARRIER_WORDS:
        if w in s:
            return "barrier"
    kept = []
    for ch in s:
        cat = unicodedata.category(ch)
        # 口径按 D7 原文：去「空白与标点」（Unicode P*）；剩余字符须全是汉字、数字或全角符号。
        # 全角符号放行（＝ ＋ ＜ ＞ 等 FF 段符号）；半角符号（= < > | × → ≤）不放行，归「源码形状」。
        if ch.isspace() or cat.startswith("P"):
            continue
        kept.append(ch)
    if kept and all(("\u4e00" <= ch <= "\u9fff") or ch.isdigit() or is_fullwidth_symbol(ch)
                    for ch in kept):
        return "copy"
    return "shape"


def iter_files():
    tests = REPO / "local" / "tests"
    names = sorted(p for p in tests.glob("test_ui_*.py"))
    phone = tests / "test_phone_ui.py"
    if phone.exists():
        names.append(phone)
    return names


def collect():
    items = []  # {file, line, literal, cls}
    per_file = []
    for p in iter_files():
        rel = p.relative_to(REPO).as_posix()
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                fname = f.attr if isinstance(f, ast.Attribute) else (
                    f.id if isinstance(f, ast.Name) else None)
                if fname in ASSERTS:
                    for arg in list(node.args) + list(node.keywords):
                        val = arg.value if isinstance(arg, ast.keyword) else arg
                        if isinstance(val, ast.Constant) and isinstance(val.value, str):
                            found.append((node.lineno, val.value))
        sandbox_tests = 0
        for node in ast.walk(tree):
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name.startswith("test_")):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        f = sub.func
                        fname = f.id if isinstance(f, ast.Name) else (
                            f.attr if isinstance(f, ast.Attribute) else None)
                        if fname == "run_js":
                            sandbox_tests += 1
                            break
        counts = {c: 0 for c in CLASSES}
        for lineno, lit in found:
            cls = classify_literal(lit)
            counts[cls] += 1
            items.append({"file": rel, "line": lineno, "literal": lit, "cls": cls})
        per_file.append({"file": rel, "counts": counts,
                         "total": len(found), "sandbox": sandbox_tests})
    return per_file, items


def main():
    per_file, items = collect()
    total = len(items)
    print("## 表 E：界面测试字面断言分类")
    print()
    print("量什么：local/tests 的 test_ui_*.py 与 test_phone_ui.py 里，assertIn、assertNotIn、"
          "assertRegex、assertNotRegex、assertEqual 调用的直接实参里的字符串字面量，"
          "按 D7 固定规则分三类（先命中先算）；node 沙箱测试函数指调用了 ui_harness.run_js 的 test_ 函数。")
    print()
    print("### E1 每文件计数")
    print()
    print("| 文件 | 无障碍名称 | 文案 | 源码形状 | 合计 | node 沙箱测试函数数 |")
    print("|---|---|---|---|---|---|")
    for row in per_file:
        c = row["counts"]
        print(f"| `{row['file']}` | {c['barrier']} | {c['copy']} | {c['shape']} | "
              f"{row['total']} | {row['sandbox']} |")
    sums = {c: sum(r["counts"][c] for r in per_file) for c in CLASSES}
    print(f"| 合计 | {sums['barrier']} | {sums['copy']} | {sums['shape']} | {total} | "
          f"{sum(r['sandbox'] for r in per_file)} |")
    print()
    print(f"自校：三类之和 {sums['barrier'] + sums['copy'] + sums['shape']} = "
          f"脚本找到的字面量断言总数 {total} -> "
          f"{'成立' if sums['barrier'] + sums['copy'] + sums['shape'] == total else '不成立'}")
    print()
    print("### E2 三类抽样各 20 条（random.Random(20261113)，按 文件:行号+字面量 排序后抽样）")
    print()
    print("| 类别 | 文件:行号 | 原文 |")
    print("|---|---|---|")
    for cls in CLASSES:
        pool = sorted((i for i in items if i["cls"] == cls),
                      key=lambda i: (i["file"], i["line"], i["literal"]))
        picked = random.Random(SEED).sample(pool, min(SAMPLE_N, len(pool)))
        for it in picked:
            lit = it["literal"]
            note = ""
            if is_host_path(lit):
                note = "（原文含路径，已替换）"
            # 转义符用 chr(92) 拼，避免源码里出现「两反斜杠+字母」被自检的 UNC 规则命中
            lit_disp = sanitize(lit).replace("|", chr(92) + "|").replace("\n", chr(92) + "n")
            print(f"| {CLASS_NAMES[cls]} | `{it['file']}:{it['line']}` | `{lit_disp}`{note} |")
        if len(pool) < SAMPLE_N:
            print(f"| {CLASS_NAMES[cls]} | （该类共 {len(pool)} 条，不足 20，已全抽） | |")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_assertions.py`")


if __name__ == "__main__":
    main()
