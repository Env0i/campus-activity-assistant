# -*- coding: utf-8 -*-
"""证据目录自检（补充规则 6.2-6.6）。

扫描目标：默认本脚本所在的证据目录（scripts/ 的上一级），也可以传另一个目录做反向验证。

行级类别（逐行扫，命中只输出「文件:行号 类别」，不回显原文）：
- 盘符路径、用户目录、临时目录真路径、file 链接（file scheme 加三斜杠）、UNC 前缀
- 建议类关键词（关键词表见 KEYWORDS；只扫散文行：> 引用行、代码围栏内、
  表格的「原文」「引用」列豁免；selfcheck.py 自身豁免，否则会被自己的词表命中）
目录级类别：
- __pycache__ 目录或 .pyc/.pyo 文件
- 证据目录下出现名为 design、local、server、tools、docs 的子目录（任意层级）

无问题输出一行「通过」并返回 0；有问题逐行输出并返回 1。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/selfcheck.py
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TARGET = HERE.parent

# 所有敏感字面量都用拼接构造，避免 selfcheck 扫描自己时被自己的模式串命中。
DRIVE = re.compile("(?<![A-Za-z0-9+.-])[A-Za-z]" + ":" + "[\\\\/]")
USERDIR = re.compile("(?i)" + "[\\\\/]" + "users?" + "[\\\\/]" + "|" + "/" + "home" + "/")
TEMPDIR = re.compile(
    "(?i)" + "appdata[\\\\/]local[\\\\/]temp"
    + "|" + "[\\\\/]" + "tmp" + "[\\\\/]"
    + "|" + "/var/" + "folders"
    + "|" + "%" + "TEMP" + "%"
    + "|" + "%" + "USERPROFILE" + "%")
FILEURL = re.compile("file" + "://")
UNC = re.compile("[\\\\]{2}" + "[A-Za-z0-9]")

KEYWORDS = ("建议", "应当", "应该", "可以考虑", "推荐", "最好", "需要改")
KEYWORD_EXEMPT_SELF = "selfcheck.py"
QUOTE_COLS = {"原文", "引用", "原文/引用", "引用原文", "原文引用"}
NESTED_DIRS = {"design", "local", "server", "tools", "docs"}

LINE_CATS = (
    ("盘符路径", DRIVE),
    ("用户目录", USERDIR),
    ("临时目录真路径", TEMPDIR),
    ("file 链接", FILEURL),
    ("UNC 前缀", UNC),
)


def split_row(line):
    return line.strip().strip("|").split("|")


def exempt_cols_of(block):
    """表头的「原文/引用」列下标；第二行不是分隔行时不豁免。"""
    if len(block) < 2:
        return set()
    sep = split_row(block[1])
    if not all(re.fullmatch(r":?-+:?", c.strip() or "-") for c in sep):
        return set()
    cols = set()
    for idx, cell in enumerate(split_row(block[0])):
        t = cell.strip()
        if t in QUOTE_COLS:
            cols.add(idx)
    return cols


def keyword_hit_lines(text):
    """返回命中的行号列表（1 起）。豁免：> 行、代码围栏、表格原文/引用列。"""
    lines = text.splitlines()
    hits = []
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            if line.lstrip().startswith("|"):
                block = []
                j = i
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    block.append(lines[j])
                    j += 1
                cols = exempt_cols_of(block)
                for k2, row in enumerate(block):
                    if k2 <= 1:  # 表头与分隔行不扫
                        continue
                    for idx, cell in enumerate(split_row(row)):
                        if idx in cols:
                            continue
                        if any(w in cell for w in KEYWORDS):
                            hits.append(i + k2 + 1)
                            break
                i = j
                continue
            if line.lstrip().startswith(">"):
                i += 1
                continue
            if any(w in line for w in KEYWORDS):
                hits.append(i + 1)
        i += 1
    return hits


def scan_file(path, rel, do_keywords):
    out = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        out.append((rel, 0, f"读不了（{type(exc).__name__}）"))
        return out
    for i, line in enumerate(text.splitlines(), 1):
        for cat, pat in LINE_CATS:
            if pat.search(line):
                out.append((rel, i, cat))
    if do_keywords:
        for ln in keyword_hit_lines(text):
            out.append((rel, ln, "建议类关键词"))
    return out


def scan_tree(target):
    out = []
    for p in sorted(target.rglob("*")):
        rel = p.relative_to(target).as_posix()
        if p.is_dir():
            if p.name == "__pycache__":
                out.append((rel, 0, "__pycache__ 目录"))
            if p.name in NESTED_DIRS:
                out.append((rel, 0, "嵌套目录"))
        else:
            if p.suffix in (".pyc", ".pyo"):
                out.append((rel, 0, "pyc 文件"))
    return out


def main():
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_TARGET
    if target.is_file():
        # 反向验证用法：直接传单个文件，只扫这一个文件
        problems = scan_file(target, target.name, do_keywords=target.name != KEYWORD_EXEMPT_SELF)
        if problems:
            for rel, ln, cat in problems:
                print(f"{rel}:{ln} {cat}")
            return 1
        print("通过")
        return 0
    if len(sys.argv) <= 1 and not (target / "README.md").exists() and not (target / "tables.md").exists():
        # 默认目标是脚本所在证据目录；脚本被复制走后默认目标不再成立
        print(f"默认目标 {DEFAULT_TARGET} 不像证据目录（无 README.md 与 tables.md）；请把目标目录作为参数传入")
        return 2
    problems = scan_tree(target)
    for p in sorted(target.rglob("*")):
        if p.is_file():
            rel = p.relative_to(target).as_posix()
            do_kw = p.name != KEYWORD_EXEMPT_SELF
            problems.extend(scan_file(p, rel, do_kw))
    if problems:
        for rel, ln, cat in problems:
            if ln:
                print(f"{rel}:{ln} {cat}")
            else:
                print(f"{rel} {cat}")
        return 1
    print("通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
