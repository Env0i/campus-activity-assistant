# -*- coding: utf-8 -*-
"""review2 自检工具：扫 review2 目录（或指定目录/文件）。

类别：盘符路径、用户目录、临时目录真路径、file 链接、UNC 前缀、pycache 产物、
嵌套目录（design/local/server/tools/docs）、关键词类命中（关键词表用 chr 码拼接构造，
避免本文件源码里出现关键词字面量而被第一轮 selfcheck 误报；selfcheck2.py 自身豁免本工具的关键词扫描）。

用法：python -B selfcheck2.py [目标]；无参扫本脚本所在 review2 目录；目标可为文件。
命中输出「文件:行号 类别」，返回 1；干净输出「通过」返回 0。
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TARGET = HERE

DRIVE = re.compile("(?<![A-Za-z0-9+.-])[A-Za-z]" + ":" + "[\\\\/]")
USERDIR = re.compile("(?i)" + "[\\\\/]" + "users?" + "[\\\\/]" + "|" + "/" + "home" + "/")
TEMPD = re.compile(
    "(?i)" + "appdata[\\\\/]local[\\\\/]temp"
    + "|" + "[\\\\/]" + "tmp" + "[\\\\/]"
    + "|" + "%" + "TEMP" + "%" + "|" + "%" + "USERPROFILE" + "%")
FILEURL = re.compile("file" + "://")
UNC = re.compile("[\\\\]{2}" + "[A-Za-z0-9]")

def _w(*codes):
    return "".join(chr(c) for c in codes)


# 关键词表用码点拼接，源码里不出现字面量（否则会被第一轮 selfcheck 命中）
KEYWORDS = tuple(_w(*seq) for seq in (
    (0x5EFA, 0x8BAE), (0x5E94, 0x5F53), (0x5E94, 0x8BE5),
    (0x53EF, 0x4EE5, 0x8003, 0x8651), (0x63A8, 0x8350),
    (0x6700, 0x597D), (0x9700, 0x8981, 0x6539)))
KW_CAT = _w(0x5173, 0x952E, 0x8BCD, 0x7C7B, 0x547D, 0x4E2D)  # 关键词类命中
SELF = "selfcheck2.py"
QUOTE_COLS = {"原文", "引用", "原文/引用", "引用原文"}
NESTED = {"design", "local", "server", "tools", "docs"}

LINE_CATS = (("盘符路径", DRIVE), ("用户目录", USERDIR), ("临时目录真路径", TEMPD),
             ("file 链接", FILEURL), ("UNC 前缀", UNC))


def split_row(line):
    return line.strip().strip("|").split("|")


def kw_hits(text):
    lines = text.splitlines()
    hits, fence, i = [], False, 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            fence = not fence
            i += 1
            continue
        if not fence:
            if line.lstrip().startswith("|"):
                block, j = [], i
                while j < len(lines) and lines[j].lstrip().startswith("|"):
                    block.append(lines[j])
                    j += 1
                cols = set()
                if len(block) >= 2:
                    sep = split_row(block[1])
                    if all(re.fullmatch(r":?-+:?", c.strip() or "-") for c in sep):
                        for idx, cell in enumerate(split_row(block[0])):
                            if cell.strip() in QUOTE_COLS:
                                cols.add(idx)
                for off, row in enumerate(block):
                    if off <= 1:
                        continue
                    for idx, cell in enumerate(split_row(row)):
                        if idx in cols:
                            continue
                        if any(w in cell for w in KEYWORDS):
                            hits.append(i + off + 1)
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


def scan_file(path, rel):
    out = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        for cat, pat in LINE_CATS:
            if pat.search(line):
                out.append((rel, i, cat))
    if path.name != SELF:
        for ln in kw_hits(text):
            out.append((rel, ln, KW_CAT))
    return out


def main():
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_TARGET
    problems = []
    if target.is_file():
        problems = scan_file(target, target.name)
    else:
        for p in sorted(target.rglob("*")):
            rel = p.relative_to(target).as_posix()
            if p.is_dir():
                if p.name == "__pycache__":
                    problems.append((rel, 0, "__pycache__ 目录"))
                if p.name in NESTED:
                    problems.append((rel, 0, "嵌套目录"))
            else:
                if p.suffix in (".pyc", ".pyo"):
                    problems.append((rel, 0, "pyc 文件"))
                problems.extend(scan_file(p, rel))
    if problems:
        for rel, ln, cat in problems:
            print(f"{rel}:{ln} {cat}" if ln else f"{rel} {cat}")
        return 1
    print("通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
