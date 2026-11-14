#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板搬家的逐字核对（只读，结果打印到标准输出）。

从基线提交取出原来的 views/phone.js，机械地切成段：文件头注释、"use strict"、每个
顶层函数与顶层常量（连同前面紧挨着的注释块）、PhonePanel 的每个字段块与每个方法
（同样连同紧挨着的注释）、文件尾两段。逐段到十个新位置（九个功能模块文件加
legacy-globals.js）里找一字不差的一段；声明行允许在前面多一个 export 关键字（导出
的包装），其余行必须逐字相同且连续。再反过来列出新文件（九个功能文件）里不属于
原文的每个非空行并分类（文件头注释、import、导出的包装、方法包与导出的包装、装配、
启动函数），分不进这几类的行必须为零。文件尾两段的去向单独写明。

用法（仓库根执行，Python 一律带 -B）：
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/move_check.py [--json <文件>]

不写主机路径；--json 把逐段落点写到给定文件（相对路径），供搬家对照表引用。
@author Author
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

BASELINE_COMMIT = "15dde9b"
ORIGIN_REL = "local/ui/views/phone.js"
NEW_FILES = [
    "features/phone-access/state.js",
    "features/phone-access/view.js",
    "features/phone-access/actions.js",
    "features/phone-access/actions-panel.js",
    "features/components/state.js",
    "features/components/view.js",
    "features/components/actions.js",
    "features/login/state-recovery.js",
    "features/login/view-recovery.js",
    "features/login/actions-recovery.js",
]
LEGACY = "legacy-globals.js"
SEARCH_FILES = NEW_FILES + [LEGACY]

STRING_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`|//[^\n]*|/\*.*?\*/', re.S)
MEMBER_RE = re.compile(r"^  (?:async\s+)?([A-Za-z_$][\w$]*)\s*(\(|:)")
DECL_RE = re.compile(r"^\s*(?:async\s+)?(?:function\s+|const\s+)")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_origin(repo: Path) -> list[str]:
    out = subprocess.run(["git", "show", "%s:%s" % (BASELINE_COMMIT, ORIGIN_REL)],
                         cwd=repo, capture_output=True, check=True)
    return out.stdout.decode("utf-8").splitlines()


def stripped(line: str) -> str:
    return STRING_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), line)


def depth_of(line: str) -> int:
    s = stripped(line)
    return s.count("{") - s.count("}")


def eat_block(lines: list[str], i: int) -> int:
    """从第 i 行（0 起始）的语句块吃到括号回到 0，返回末行下标（0 起始）；无括号只算一行。"""
    if "{" not in stripped(lines[i]):
        return i
    total = depth_of(lines[i])
    j = i
    while total > 0 and j + 1 < len(lines):
        j += 1
        total += depth_of(lines[j])
    return j


def segment_origin(lines: list[str]) -> list[dict]:
    """把原文件机械切段：[{kind, start, end}]（1 起始闭区间，含段前紧挨着的注释）。"""
    segments: list[dict] = []
    n = len(lines)
    i = 0
    pend = 0                      # 段前注释的起始行（1 起始）；0 表示没有
    while i < n:
        s = lines[i].strip()
        if not s or s.startswith("//"):
            pend = 0
            i += 1
            continue
        if s.startswith("/*"):
            if not pend:
                pend = i + 1
            j = i
            while "*/" not in lines[j] and j + 1 < n:
                j += 1
            i = j + 1
            continue
        j = eat_block(lines, i)
        segments.append({"kind": "top", "start": pend or i + 1, "end": j + 1})
        pend = 0
        i = j + 1
    # PhonePanel 对象字面量内部：字段块与方法逐个成段
    out: list[dict] = []
    for seg in segments:
        body = lines[seg["start"] - 1:seg["end"]]
        decl_at = next((k for k, l in enumerate(body)
                        if "const PhonePanel = {" in l), None)
        if decl_at is None:
            out.append(seg)
            continue
        if decl_at > 0:
            out.append({"kind": "top", "start": seg["start"], "end": seg["start"] + decl_at})
        open_line = seg["start"] + decl_at          # const PhonePanel = { 这一行
        inner_start = open_line + 1
        inner = lines[inner_start - 1:seg["end"] - 1]
        k = 0
        pend = 0
        while k < len(inner):
            s = inner[k].strip()
            if not s:
                pend = 0
                k += 1
                continue
            if s.startswith("//"):
                if not pend:
                    pend = inner_start + k
                k += 1
                continue
            if s.startswith("/*"):
                if not pend:
                    pend = inner_start + k
                while "*/" not in inner[k] and k + 1 < len(inner):
                    k += 1
                k += 1
                continue
            m = MEMBER_RE.match(inner[k])
            if not m:
                raise SystemExit("PhonePanel 内出现认不出的成员行 %d：%s"
                                 % (inner_start + k, s))
            j = eat_block(inner, k)
            out.append({"kind": "member:" + m.group(1),
                        "start": pend or inner_start + k, "end": inner_start + j})
            pend = 0
            k = j + 1
    return out


def find_segment(seg_text: list[str], file_lines: list[str]) -> int | None:
    """在文件里找逐字相同（声明行可带 export 前缀）的连续段，返回起始下标（0 起始）。"""
    m = len(seg_text)
    for i in range(len(file_lines) - m + 1):
        ok = True
        for k in range(m):
            want = seg_text[k].rstrip("\r\n")
            got = file_lines[i + k].rstrip("\r\n")
            # 声明行允许在前面多一个 export 关键字（导出的包装），其余必须逐字相同
            if got == want or got == "export " + want.lstrip():
                continue
            ok = False
            break
        if ok:
            return i
    return None


def header_lines() -> set:
    """九个新文件开头（第一个空行或 import 之前）的注释行集合。"""
    heads = set()
    for rel in NEW_FILES:
        for line in (Path("local/ui") / rel).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("import ") or s.startswith('"use strict"'):
                break
            heads.add(s)
    return heads


def classify_extra(extra: collections.Counter, heads: set) -> list[str]:
    """把新文件里多出来的非空行分类，返回逐行说明；分不类的在前面加标记。"""
    report = []
    for line, count in sorted(extra.items()):
        s = line.strip()
        if s in heads:
            kind = "文件头注释"
        elif s.startswith("import {"):
            kind = "import"
        elif s.startswith("Object.assign(") or re.match(r"^  \w+Pack", line) \
                or line.endswith("Pack);"):
            kind = "装配"
        elif s.startswith("export function startPhonePanel") or s == "}":
            kind = "启动函数"
        elif re.match(r"^export const \w+Pack = \{$", s) or s == "const panelWirePack = {" \
                or s == "};":
            kind = "方法包与导出的包装"
        elif s.startswith("export ") and DECL_RE.match(s[len("export "):]):
            kind = "导出的包装"
        else:
            kind = "【分不出类】"
        report.append("%s x%d → %s" % (line, count, kind))
    return report


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    origin = load_origin(Path("."))
    file_lines = {rel: (Path("local/ui") / rel).read_text(encoding="utf-8").splitlines()
                  for rel in SEARCH_FILES}
    segments = segment_origin(origin)

    rows = []
    not_found = 0
    for seg in segments:
        text = [l.rstrip("\r\n") for l in origin[seg["start"] - 1:seg["end"]]]
        if not any(t.strip() for t in text):
            continue
        hit = None
        for rel in SEARCH_FILES:
            at = find_segment(text, file_lines[rel])
            if at is not None:
                hit = (rel, at + 1, at + len(text))
                break
        head = next((t.strip() for t in text if t.strip()), "")[:56]
        if hit is None:
            not_found += 1
            rows.append({"kind": seg["kind"], "origin": "%d-%d" % (seg["start"], seg["end"]),
                         "head": head, "status": "没找到", "file": "", "lines": ""})
            log("段 %-16s 原文 %4d-%4d → 没找到  %s" % (seg["kind"][:16], seg["start"],
                                                       seg["end"], head[:40]))
        else:
            rows.append({"kind": seg["kind"], "origin": "%d-%d" % (seg["start"], seg["end"]),
                         "head": head, "status": "找到且相同", "file": hit[0],
                         "lines": "%d-%d" % (hit[1], hit[2])})
            log("段 %-16s 原文 %4d-%4d → %-44s %d-%d" %
                (seg["kind"][:16], seg["start"], seg["end"], hit[0], hit[1], hit[2]))

    tail_doc = next((r for r in rows if r["origin"] == "1245-1248"), None)
    tail_mount = next((r for r in rows if r["origin"] == "1250-1252"), None)

    orig_counter = collections.Counter(l.rstrip() for l in origin if l.strip())
    for rel in NEW_FILES:
        for l in (Path("local/ui") / rel).read_text(encoding="utf-8").splitlines():
            if l.strip():
                orig_counter[l.rstrip()] -= 1
    extra = collections.Counter({k: -v for k, v in orig_counter.items() if v < 0})
    report = classify_extra(extra, header_lines())
    unclassified = [r for r in report if "【分不出类】" in r]

    total = len(rows)
    print()
    print("== 逐段核对 ==")
    print("原文共切成 %d 段（含段前紧挨着的注释）；找到且逐字相同 %d 段；没找到 %d 段。"
          "本脚本只有「找到且相同（声明行可多一个 export）」与「没找到」两种结果，"
          "出现没找到即不通过。" % (total, total - not_found, not_found))
    print()
    print("== 文件尾两段的去向 ==")
    print("判断 readyState 后调用 wire 的那段（原文 1245-1248）→ %s" %
          ("%s:%s（包在导出的启动函数 startPhonePanel 里）"
           % (tail_doc["file"], tail_doc["lines"])
           if tail_doc and tail_doc["status"] == "找到且相同" else "没找到"))
    print("挂回 window 的那段（原文 1250-1252，两行注释加一行挂载）→ %s" %
          ("%s:%s（搬进过渡名单 installLegacyGlobals 里）"
           % (tail_mount["file"], tail_mount["lines"])
           if tail_mount and tail_mount["status"] == "找到且相同" else "没找到"))
    print()
    print("== 新文件里多出来的非空行（反向核对）==")
    for line in report:
        print("  " + line)
    print("多出的非空行共 %d 行；分不进六类的行 %d 行（必须为零）。"
          % (sum(extra.values()), len(unclassified)))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        log("逐段落点已写 %s" % args.json)
    raise SystemExit(1 if (not_found or unclassified) else 0)


if __name__ == "__main__":
    main()
