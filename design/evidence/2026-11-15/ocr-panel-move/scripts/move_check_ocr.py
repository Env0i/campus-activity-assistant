#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证码识别一节搬家的逐字核对（只读，结果打印到标准输出）。

全部文件版本都从提交里经 git show 取，不读工作区——仓库里就能复跑：
一、以「整理之后、搬家之前」的提交（--tidy-ref）里的 views/settings.js 为基准，
    按名字切出六段（连同前面紧挨着的注释），逐段到「搬家之后」的提交（--move-ref）
    的两个新模块文件里找一字不差的一段——声明行只多一个 export；OcrPanel 前那段
    注释只差「本文件的动作」改成「views/settings.js 的动作」这一处。
二、--move-ref 里的 views/settings.js 必须等于基准减去两整块（两处连续删除，各含
    块后的一个分隔空行，别的一个字不变）。
三、反向列出两个新文件里不属于基准原文的每个非空行并分类（文件头注释、import），
    分不出类的必须为零。
四、上一批搬出的三个模块文件，--tidy-ref 与 --move-ref 两个版本的 diff 必须只有
    加的 import 行与路径注释的替换——整理那一笔已经先落库，整理挪注释不再混进来。

用法（仓库根执行，Python 一律带 -B）：
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/move_check_ocr.py \
      --tidy-ref <整理那一笔的短哈希> --move-ref <搬家那一笔的短哈希> [--json <文件>]

不写主机路径；--json 把逐段落点写到给定文件（相对路径），供搬家对照表引用。
"""
from __future__ import annotations

import argparse
import collections
import difflib
import json
import subprocess
import sys
from pathlib import Path

NEW_FILES = {
    "state": "features/components/state-ocr.js",
    "view": "features/components/view-ocr.js",
}
THREE_FILES = [
    "features/components/actions.js",
    "features/phone-access/view.js",
    "features/phone-access/state.js",
]

# 段的定义：名字、基准里 1 起始的起止行（含段前紧挨着的注释）、声明行的行号与原文、
# 声明行加 export 后的原文；OcrPanel 段多一条「注释里允许的那一处替换」。
SEGMENTS = [
    ("ocrFeature", 130, 137, 1, "function ocrFeature() {", [], None),
    ("OcrPanel", 139, 148, 4, "const OcrPanel = {", [],
     (" * note / error 由本文件的动作和 features/components/actions.js 里 relogin_ocr 的下载、取消、导入三处写入。 */",
      " * note / error 由 views/settings.js 的动作和 features/components/actions.js 里 relogin_ocr 的下载、取消、导入三处写入。 */")),
    ("ocrPhase", 150, 162, 3, "function ocrPhase(feature) {", [], None),
    ("ocrShow", 164, 168, 1, "function ocrShow(selector, visible) {", [], None),
    ("ocrText", 170, 177, 1, "function ocrText(selector, text) {", [], None),
    ("paintOcrDownload", 191, 311, 3, "function paintOcrDownload() {", [], None),
]
# 两整块（内容加块后的一个分隔空行）：130-178 与 191-312
BLOCKS = [(130, 178), (191, 312)]

# 三个模块文件在整理之后与搬家之后两个提交之间允许出现的行变化
#（added / removed 的原文多重集，用元组防并重）
ALLOWED_THREE = {
    "features/components/actions.js": {
        "added": (
            'import { OcrPanel } from "./state-ocr.js";',
            "      // OC11 / OC15：反馈就地写在验证码识别那一节（features/components/state-ocr.js OcrPanel），不再走抽屉底部；开始下载不另说，进度块会出现",
            "      // OC13：成功后回到没装态，取消的那句话由快照的 cancelled 派生（写在 features/components/view-ocr.js）；失败才在本节红条里说",
        ),
        "removed": (
            "      // OC11 / OC15：反馈就地写在验证码识别那一节（views/settings.js OcrPanel），不再走抽屉底部；开始下载不另说，进度块会出现",
            "      // OC13：成功后回到没装态，取消的那句话由快照的 cancelled 派生（写在 views/settings.js）；失败才在本节红条里说",
        ),
    },
    "features/phone-access/view.js": {
        "added": (
            'import { paintOcrDownload } from "../components/view-ocr.js";',
            "    /* 验证码识别一节的状态、按钮和文案由设置抽屉按组件快照与下载事务统一决定（features/components/view-ocr.js） */",
        ),
        "removed": (
            "    /* 验证码识别一节的状态、按钮和文案由设置抽屉按组件快照与下载事务统一决定（views/settings.js） */",
        ),
    },
    "features/phone-access/state.js": {
        "added": (
            "/* 验证码识别一节的状态、按钮和文案在 features/components/view-ocr.js（paintOcrDownload）；这里管手机访问、登录恢复和导入弹窗。 */",
        ),
        "removed": (
            "/* 验证码识别一节的状态、按钮和文案在 views/settings.js（paintOcrDownload）；这里管手机访问、登录恢复和导入弹窗。 */",
        ),
    },
}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def load_version(ref: str, rel: str) -> list[str]:
    out = subprocess.run(["git", "show", "%s:local/ui/%s" % (ref, rel)],
                         cwd=".", capture_output=True, check=True)
    return [l.rstrip("\r\n") for l in out.stdout.decode("utf-8").splitlines()]


def line_matches(seg_name: str, want: str, got: str, decl_line_no: int,
                 line_pos: int, exported: str, comment_swap) -> bool:
    if got == want:
        return True
    if line_pos == decl_line_no - 1 and got == "export " + want.lstrip():
        return True
    if comment_swap and want == comment_swap[0] and got == comment_swap[1]:
        return True
    return False


def find_segment(seg_name: str, seg_text: list[str], decl_line_no: int, exported: str,
                 comment_swap, file_lines: list[str]) -> int | None:
    m = len(seg_text)
    for i in range(len(file_lines) - m + 1):
        if all(line_matches(seg_name, seg_text[k], file_lines[i + k].rstrip("\r\n"),
                            decl_line_no, k, exported, comment_swap)
               for k in range(m)):
            return i
    return None


def classify_extra(extra: collections.Counter, heads: set) -> list[str]:
    report = []
    for line, count in sorted(extra.items()):
        s = line.strip()
        if s in heads:
            kind = "文件头注释"
        elif s.startswith("import {"):
            kind = "import"
        else:
            kind = "【分不出类】"
        report.append("%s x%d → %s" % (line, count, kind))
    return report


def normalize_for_reverse(file_lines: dict, segs: list[tuple]) -> tuple[list[str], list[str]]:
    """按允许规则归一新文件的行再拿去与基准相减，返回（归一后的行序列，允许项说明）。

    允许规则只有三条：声明行多一个 export、面板字段那段注释的那一处路径改写、
    以及文件头注释与 import 本身（这两类在归一后仍会多出来，交给分类归档）。"""
    export_decl = {("export " + s[4]) for s in segs}
    swap_old, swap_new = next(s[6] for s in segs if s[6])
    allowed_notes: list[str] = []
    out: list[str] = []
    for rel in NEW_FILES.values():
        for l in file_lines[rel]:
            line = l.rstrip("\r\n")
            if line in export_decl:
                allowed_notes.append("%s → 声明行加 export" % line)
                line = line[len("export "):]
            elif line == swap_new:
                allowed_notes.append("%s → 点名的那一处注释改写" % line)
                line = swap_old
            out.append(line)
    return out, allowed_notes


def check_three_files(rows: list[dict], tidy_ref: str, move_ref: str) -> int:
    bad = 0
    for rel in THREE_FILES:
        before = load_version(tidy_ref, rel)
        after = load_version(move_ref, rel)
        sm = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
        added: list[str] = []
        removed: list[str] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("insert", "replace"):
                added.extend(l.rstrip("\r\n") for l in after[j1:j2])
            if tag in ("delete", "replace"):
                removed.extend(l.rstrip("\r\n") for l in before[i1:i2])
        allowed = ALLOWED_THREE[rel]
        extra_add = collections.Counter(added) - collections.Counter(allowed["added"])
        extra_rem = collections.Counter(removed) - collections.Counter(allowed["removed"])
        ok = not extra_add and not extra_rem
        rows.append({"check": "三文件 diff", "file": rel, "status": "通过" if ok else "不通过",
                     "added": len(added), "removed": len(removed)})
        if ok:
            log("diff %s → 只有允许的变化（加 %d 行、删 %d 行）" % (rel, len(added), len(removed)))
        else:
            bad += 1
            for l, n in extra_add.items():
                log("diff %s 多出不在允许清单的行 x%d：%r" % (rel, n, l))
            for l, n in extra_rem.items():
                log("diff %s 少了不在允许清单的行 x%d：%r" % (rel, n, l))
    return bad


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tidy-ref", required=True,
                    help="整理之后、搬家之前的提交（逐字核对基准的来源）")
    ap.add_argument("--move-ref", required=True,
                    help="搬家之后的提交（新文件与搬完后的 settings.js 的来源）")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    base = load_version(args.tidy_ref, "views/settings.js")
    file_lines = {rel: load_version(args.move_ref, rel) for rel in NEW_FILES.values()}

    rows: list[dict] = []
    not_found = 0
    for name, start, end, decl_no, decl, _flags, comment_swap in SEGMENTS:
        seg_text = base[start - 1:end]
        hits = []
        for rel in NEW_FILES.values():
            at = find_segment(name, seg_text, decl_no, decl, comment_swap, file_lines[rel])
            if at is not None:
                hits.append((rel, at + 1, at + len(seg_text)))
        if len(hits) == 1:
            rel, lo, hi = hits[0]
            rows.append({"check": "逐段", "name": name, "origin": "%d-%d" % (start, end),
                         "status": "找到且相同（声明行可多 export；注释只差点名那一处）",
                         "file": rel, "lines": "%d-%d" % (lo, hi)})
            log("段 %-18s 基准 %4d-%4d → %-44s %d-%d" % (name, start, end, rel, lo, hi))
        else:
            not_found += 1
            rows.append({"check": "逐段", "name": name, "origin": "%d-%d" % (start, end),
                         "status": "没找到或不止一处（%d）" % len(hits), "file": "", "lines": ""})
            log("段 %-18s 基准 %4d-%4d → 没找到或不止一处（%d）" % (name, start, end, len(hits)))

    # settings.js = 基准减两整块
    keep: list[str] = []
    cut = sorted(BLOCKS)
    pos = 1
    for lo, hi in cut:
        keep.extend(base[pos - 1:lo - 1])
        pos = hi + 1
    keep.extend(base[pos - 1:])
    actual = load_version(args.move_ref, "views/settings.js")
    settings_ok = keep == actual
    rows.append({"check": "settings 只剩两处连续删除", "file": "views/settings.js",
                 "status": "通过（%d 行 = 基准 403 − %d − %d）" % (len(actual), BLOCKS[0][1] - BLOCKS[0][0] + 1, BLOCKS[1][1] - BLOCKS[1][0] + 1),
                 "added": 0, "removed": 0})
    log("settings.js 与「基准减两整块」逐行相等：%s（%d 行）" % ("是" if settings_ok else "否", len(actual)))
    if not settings_ok:
        not_found += 1
        diff = list(difflib.unified_diff(keep, actual, "基准减两整块", "搬完后的 settings.js", lineterm=""))
        for l in diff[:40]:
            log(l)

    # 反向核对：两个新文件里不属于基准原文的非空行（声明行先按允许规则去掉 export、
    # 点名的那处注释改写按规则还原，再与基准相减）
    normalized, allowed_notes = normalize_for_reverse(file_lines, SEGMENTS)
    orig_counter = collections.Counter(l for l in base if l.strip())
    for l in normalized:
        if l.strip():
            orig_counter[l] -= 1
    extra = collections.Counter({k: -v for k, v in orig_counter.items() if v < 0})
    heads = set()
    for rel in NEW_FILES.values():
        for l in file_lines[rel]:
            s = l.strip()
            if not s or s.startswith("import "):
                break
            heads.add(s)
    report = classify_extra(extra, heads)
    unclassified = [r for r in report if "【分不出类】" in r]
    log("")
    log("== 按允许规则归掉的行（声明行加 export 与点名的那处注释改写）==")
    for line in allowed_notes:
        log("  " + line)
    log("== 新文件里多出来的非空行（反向核对，已归掉允许项）==")
    for line in report:
        log("  " + line)

    bad_three = check_three_files(rows, args.tidy_ref, args.move_ref)

    print()
    print("== 逐段核对 ==")
    print("六段全部找到且逐字相同：%d/6；没找到 %d 段。声明行只多一个 export；"
          "面板字段那段注释只差点名的那一处路径改写。出现没找到即不通过。"
          % (6 - sum(1 for r in rows if r["check"] == "逐段" and not r["status"].startswith("找到")),
             not_found - (0 if settings_ok else 1)))
    print()
    print("== settings.js ==")
    print("搬完后的 settings.js 与「基准减两整块」逐行相等：%s；行数 %d（基准 403）。"
          % ("是" if settings_ok else "否", len(actual)))
    print()
    print("== 新文件里多出来的非空行 ==")
    print("多出的非空行共 %d 行；分不进「文件头注释、import」两类的行 %d 行（必须为零）。"
          % (sum(extra.values()), len(unclassified)))
    print()
    print("== 上一批三个模块文件的 diff ==")
    print("三个文件在整理之后与搬家之后两个提交之间只有加的 import 行与路径注释替换：%s"
          % ("通过" if bad_three == 0 else "不通过"))
    ok = (not_found == 0 and settings_ok and not unclassified and bad_three == 0)
    print()
    print("核对结论：%s" % ("全部通过" if ok else "不通过"))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        log("逐段落点已写 %s" % args.json)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
