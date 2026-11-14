# -*- coding: utf-8 -*-
"""review2 表 G 独立复算：文档数字对账（计划 D9 口径，四类句子 + 实测）。

四类正则独立重写（与第一轮实现无参照）；实测用独立量法函数。

从仓库根运行：python -B design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_g_doccheck.py
"""
import ast
import os
import re
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

# 四类句子正则（本轮独立写法）
RE_TEST = re.compile(r"\d{3,}\s*(?:个)?\s*(?:例|用例)")
RE_API = re.compile(r"\d+\s*个?\s*(?:公开)?方法")
RE_DEC = re.compile(r"\d+\s*篇")
RE_LINES = re.compile(r"\d{3,}\s*行")
RE_FILE = re.compile(r"[\w\-./]+\.(?:py|js|mjs)\b")
RE_LINEREF = re.compile(r"第\s*\d|[:：]\s*\d{2,}")

HOST = [re.compile("(?<![A-Za-z0-9+.-])[A-Za-z]:[\\\\/]"),
        re.compile("(?i)[\\\\/]users?[\\\\/]"),
        re.compile("(?i)appdata[\\\\/]local[\\\\/]temp")]


def m_tests():
    out = []
    for top in ("local/tests", "server/tests"):
        n = 0
        for p in (REPO / top).rglob("*.py"):
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8", errors="replace"))):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    n += 1
        out.append((top, n))
    return out


def m_api():
    tree = ast.parse((REPO / "local/app.py").read_text(encoding="utf-8", errors="replace"))
    total = public = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Api":
            for it in node.body:
                if isinstance(it, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total += 1
                    public += 0 if it.name.startswith("_") else 1
    return total, public


def m_decisions():
    d = REPO / "design" / "decisions"
    return len([p for p in d.glob("*.md") if not p.name.startswith("README")])


def m_lines(rel):
    p = REPO / rel
    if not p.exists():
        return "文件当前不存在"
    t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return len(t.rstrip("\n").split("\n")) if t.strip() else 0


def main():
    files = [n for n in ("AGENTS.md", "README.md", "local/README.md")
             if (REPO / n).exists()]
    docs = REPO / "docs"
    if docs.exists():
        files += sorted(p.relative_to(REPO).as_posix() for p in docs.rglob("*.md"))
    tests = m_tests()
    api = m_api()
    dec = m_decisions()
    test_disp = "；".join(f"{k} {v}" for k, v in tests) + f"；合计 {sum(v for _, v in tests)}"
    print("## review2 表 G 独立复算")
    print()
    print(f"量法基准：api 总数 {api[0]} / 非下划线 {api[1]}；决策记录 {dec} 篇；测试 test_ 函数 {test_disp}。")
    print()
    print("| 文件:行号 | 类别 | 原文 | 实测值 |")
    print("|---|---|---|---|")
    for rel in files:
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        for i, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line:
                continue
            hits = []
            if RE_TEST.search(line):
                hits.append(("测试用例个数", test_disp))
            if "Api" in line and RE_API.search(line):
                hits.append(("Api 方法个数", f"总数 {api[0]}；非下划线 {api[1]}"))
            if RE_DEC.search(line):
                hits.append(("决策记录篇数", f"{dec} 篇"))
            if RE_LINES.search(line) and RE_FILE.search(line) and not RE_LINEREF.search(line):
                toks = sorted(set(RE_FILE.findall(line)))
                vals = "；".join(f"`{t}` = {m_lines(t)}" for t in toks)
                hits.append(("源文件行数", vals or "未量"))
            for cat, val in hits:
                disp = line
                for pat in HOST:
                    disp = pat.sub("<主机路径>", disp)
                disp = disp.replace("|", chr(92) + "|")
                print(f"| `{rel}:{i}` | {cat} | {disp} | {val} |")


if __name__ == "__main__":
    main()
