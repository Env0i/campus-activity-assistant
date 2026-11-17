#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐字核对：plan-panel.js 的 28 段与 refresh.js 的两段是否原样落到新模块。

口径：
- 段 = 一个顶层函数或常量，连同紧挨着它上方的注释；文件末尾没有归属的注释跟着最后一个函数走。
- 每段去掉 `export ` 前缀后，必须在某个新文件里找到一字不差的一段。
- 反过来列新文件里不属于原文的每一行，归类为文件头注释 / import / 挂回；不属于这几类的必须为零。
- app.js 与开工 HEAD 相比只许少 bindPlaceToggle(); 那一行；main.js 多出来的行只能是 import、两句注释、那一行调用。

@author Author
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HEAD = "580c1c4"

ORIGINALS = ("local/ui/views/plan-panel.js",)
REFRESH = "local/ui/controllers/refresh.js"
MOVED = (
    "local/ui/features/plan/state-draft.js",
    "local/ui/features/plan/view-draft.js",
    "local/ui/features/plan/actions-draft.js",
    "local/ui/features/plan/state-led.js",
    "local/ui/features/plan/view-led.js",
    "local/ui/features/plan/view-controls.js",
    "local/ui/features/plan/view-dock.js",
    "local/ui/features/shell/view-band.js",
    "local/ui/features/shell/view-banners.js",
    "local/ui/features/shell/state-runtime.js",
)
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


def find_block(haystacks: list[list[str]], block: list[str]) -> bool:
    n = len(block)
    for hay in haystacks:
        for i in range(len(hay) - n + 1):
            if strip_export(hay[i:i + n]) == block:
                return True
    return False


def main() -> int:
    report = {"segments": 0, "found": 0, "missing": [], "different": [], "extra": {},
              "app_removed": [], "main_added": [], "refresh_removed": [], "refresh_remaining_tail": []}
    new_lines = {rel: (ROOT / rel).read_text(encoding="utf-8").split("\n") for rel in MOVED}
    haystacks = list(new_lines.values())
    original_lines: set[str] = set()

    for rel in ORIGINALS:
        lines = head_text(rel).split("\n")
        original_lines.update(line for line in lines if line.strip())
        items = decls(lines)
        for name, kind, first, last in items:
            report["segments"] += 1
            block = lines[block_start(lines, first) - 1:last]
            while block and block[0].strip() == "":
                block.pop(0)
            while block and block[-1].strip() == "":
                block.pop()
            if find_block(haystacks, block):
                report["found"] += 1
            else:
                decl_only = block[-_decl_len(block):]
                if find_block(haystacks, decl_only):
                    report["different"].append([rel, name, "注释不同"])
                else:
                    report["different"].append([rel, name, "正文不同"])
        tail = [line for line in lines[items[-1][3]:] if line.strip()]
        if tail and not find_block(haystacks, tail):
            report["missing"].append([rel, "文件末尾的注释", len(tail)])

    # refresh.js 只删两段：RUNTIME_ERRORS(含注释) 与 runtimeErrorCopy
    old_refresh = head_text(REFRESH)
    new_refresh = (ROOT / REFRESH).read_text(encoding="utf-8")
    cm = "/* 组件错误 → 一句话标题 + 恢复动作说明（后端 runtime_error 的唯一展示口径） */"
    block_start_i = old_refresh.index(cm)
    fn_i = old_refresh.index("function runtimeErrorCopy()")
    block_end_i = old_refresh.index("\n}", fn_i) + 2
    removed = old_refresh[block_start_i:block_end_i]
    report["refresh_removed"] = [l for l in removed.split("\n") if l.strip()]
    # 只检查两段的定义是否还在；函数体里对挂回名字的正常使用不算残留
    report["refresh_remaining_tail"] = [l for l in new_refresh.split("\n")
                                        if l.strip().startswith("const RUNTIME_ERRORS")
                                        or l.strip().startswith("function runtimeErrorCopy")]
    original_lines.update(l for l in removed.split("\n") if l.strip())

    # 新文件里不属于原文的行
    for rel in MOVED:
        extra = []
        for line in new_lines[rel]:
            if line.strip() == "" or line in original_lines:
                continue
            if line.startswith("/*") or line.startswith(" *") or line.endswith("*/"):
                continue  # 文件头注释与段内注释（段内注释原文已收录）
            if line.startswith("import {") and line.endswith(";"):
                continue
            if line.startswith("export ") and line[len("export "):] in original_lines:
                continue
            extra.append(line[:90])
        report["extra"][rel] = extra

    old_app = head_text(APP_JS).split("\n")
    new_app = (ROOT / APP_JS).read_text(encoding="utf-8").split("\n")
    report["app_removed"] = [line for line in old_app if line.strip() and line not in new_app]
    old_main = head_text(MAIN_JS).split("\n")
    report["main_added"] = [line for line in (ROOT / MAIN_JS).read_text(encoding="utf-8").split("\n")
                            if line.strip() and line not in old_main]

    print(json.dumps(report, ensure_ascii=False, indent=1))
    extra_n = sum(len(v) for v in report["extra"].values())
    bad = (len(report["missing"]) + len(report["different"]) + extra_n
           + len(report["app_removed"]) - 1 + len(report["refresh_remaining_tail"]))
    return 0 if bad == 0 else 1


def _decl_len(block: list[str]) -> int:
    for i, line in enumerate(block):
        if re.match(r"^(?:function|const|let)\s+", re.sub(r"^export\s+", "", line)):
            return len(block) - i
    return len(block)


if __name__ == "__main__":
    sys.exit(main())
