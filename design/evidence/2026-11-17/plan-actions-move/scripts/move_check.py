#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐字核对：两个控制器的每一段是否原样落到 features/plan/ 与 features/login/ 的新文件里。

口径：
- 段 = 一个顶层函数或常量，连同紧挨着它上方的注释；文件末尾没有归属的注释跟着最后一个函数走。
- 每段去掉 `export ` 前缀后，必须在四个新文件里找到一字不差的一段。
- 反过来列四个新文件里不属于原文的每一行，归类为文件头注释 / import / export 关键字；
  不属于这几类的必须为零。
- app.js 与开工 HEAD 相比只许少那 8 行；main.js 多出来的行只能是 import、那句注释与这 8 行。

@author Author
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HEAD = "35229af"

ORIGINALS = ("local/ui/controllers/plan.js", "local/ui/controllers/plan-events.js")
MOVED = ("local/ui/features/plan/actions-start.js", "local/ui/features/plan/actions-run.js",
         "local/ui/features/plan/actions-events.js", "local/ui/features/login/actions-browser.js")
APP_JS = "local/ui/app.js"
MAIN_JS = "local/ui/main.js"


def head_text(rel: str) -> str:
    return subprocess.run(["git", "show", "%s:%s" % (HEAD, rel)], cwd=str(ROOT),
                          capture_output=True, check=True).stdout.decode("utf-8")


def decls(lines: list[str]) -> list[tuple[str, str, int, int]]:
    """顶层声明：名字、种类、起止行（1 起）。"""
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(?:function|const|let)\s+([A-Za-z_$][\w$]*)", lines[i])
        if not m:
            i += 1
            continue
        name, kind = m.group(1), lines[i].split()[0]
        depth, seen, j = 0, False, i
        while j < len(lines):
            code = re.sub(r"//.*", "", lines[j])
            for ch in code:
                if ch == "{":
                    depth += 1
                    seen = True
                elif ch == "}":
                    depth -= 1
            if kind == "function" and seen and depth == 0:
                break
            if kind != "function" and code.rstrip().endswith(";"):
                break
            j += 1
        out.append((name, kind, i + 1, j + 1))
        i = j + 1
    return out


def block_start(lines: list[str], first: int) -> int:
    s = first
    while s - 1 >= 2:
        prev = lines[s - 2].strip()
        if prev.startswith(("//", "/*", "*")) or prev.endswith("*/"):
            s -= 1
            if prev.startswith("/*"):
                break
            continue
        break
    return s


def strip_export(lines: list[str]) -> list[str]:
    return [re.sub(r"^export\s+", "", line, count=1) for line in lines]


def find_block(haystack: list[str], block: list[str]) -> bool:
    n = len(block)
    for i in range(len(haystack) - n + 1):
        if strip_export(haystack[i:i + n]) == block:
            return True
    return False


def main() -> int:
    report = {"segments": 0, "found": 0, "missing": [], "different": [], "extra": {}, "app_removed": [], "main_added": []}
    new_lines: dict[str, list[str]] = {}
    for rel in MOVED:
        new_lines[rel] = (ROOT / rel).read_text(encoding="utf-8").split("\n")
    original_lines: set[str] = set()

    for rel in ORIGINALS:
        text = head_text(rel)
        lines = text.split("\n")
        original_lines.update(line for line in lines if line.strip())
        items = decls(lines)
        for name, kind, first, last in items:
            report["segments"] += 1
            block = lines[block_start(lines, first) - 1:last]
            while block and block[0].strip() == "":
                block.pop(0)
            while block and block[-1].strip() == "":
                block.pop()
            if any(find_block(new_lines[x], block) for x in MOVED):
                report["found"] += 1
            else:
                decl_only = block[-_decl_len(block):]
                if any(find_block(new_lines[x], decl_only) for x in MOVED):
                    report["different"].append([rel, name, "注释不同"])
                else:
                    report["different"].append([rel, name, "正文不同"])
        tail = lines[items[-1][3]:]
        tail = [line for line in tail if line.strip()]
        if tail and not any(find_block(new_lines[x], tail) for x in MOVED):
            report["missing"].append([rel, "文件末尾的注释", len(tail)])

    # 新文件里不属于原文的行
    for rel in MOVED:
        extra = []
        for line in new_lines[rel]:
            if line.strip() == "" or line in original_lines:
                continue
            if line.startswith("/* 计划栏的编排层") or line.startswith("/* 登录的编排层"):
                continue
            if line.startswith("import {") and line.endswith(";"):
                continue
            if line.startswith("export ") and line[len("export "):] in original_lines:
                continue
            extra.append(line[:90])
        report["extra"][rel] = extra

    # app.js 只许少那 8 行
    old_app = head_text(APP_JS).split("\n")
    new_app = (ROOT / APP_JS).read_text(encoding="utf-8").split("\n")
    removed = [line for line in old_app if line and line not in new_app]
    report["app_removed"] = removed

    # main.js 多出来的行：import、那句注释、这 8 行
    old_main = head_text(MAIN_JS).split("\n")
    added = [line for line in new_app[:0]]  # 占位，避免误用
    added = [line for line in (ROOT / MAIN_JS).read_text(encoding="utf-8").split("\n")
             if line.strip() and line not in old_main]
    report["main_added"] = added

    print(json.dumps(report, ensure_ascii=False, indent=1))
    bad = (len(report["missing"]) + len(report["different"])
           + sum(len(v) for v in report["extra"].values()) + len(report["app_removed"]) - 8)
    return 0 if bad == 0 else 1


def _decl_len(block: list[str]) -> int:
    for i, line in enumerate(block):
        if re.match(r"^(?:function|const|let)\s+", re.sub(r"^export\s+", "", line)):
            return len(block) - i
    return len(block)


if __name__ == "__main__":
    sys.exit(main())
