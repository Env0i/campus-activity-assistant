# -*- coding: utf-8 -*-
"""搬家逐字核对：把开工 HEAD 上那三个文件切成顶层声明段，逐段到新位置找一字不差的一段；
再反过来把新文件里不属于原文的行分类，分不进任何一类的必须为零。

用法（从仓库根执行）：
  python -B design/evidence/<日期>/login-move/scripts/move_check.py
  python -B design/evidence/<日期>/login-move/scripts/move_check.py --base-ref <开工 HEAD>

判定：每一段都在新位置找到且完全相同，且新文件里每一行都能归类（文件头注释 / import /
export 关键字已经并进声明行 / 迁移时新写的分隔注释 / main.js 的接线）。
有任何一段找不到、或不相同的行分不进这几类，退出 1。

@author Author
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# 开工 HEAD 上还没有的模块，要从 HEAD 里取原文的三个旧文件
ORIGINALS = (
    "local/ui/state/login.js",
    "local/ui/views/login.js",
    "local/ui/views/relogin.js",
)

# 搬完之后这些地方应当含有原文的段
TARGETS = (
    "local/ui/features/login/state.js",
    "local/ui/features/login/view.js",
    "local/ui/features/login/actions.js",
    "local/ui/features/login/state-relogin.js",
    "local/ui/features/login/view-relogin.js",
    "local/ui/features/login/actions-relogin.js",
    "local/ui/views/result.js",
    "local/ui/views/log.js",
    "local/ui/main.js",
)

DECL = re.compile(r"^(?:export )?(?:async )?(?:function|const|let|var) ([A-Za-z_$][\w$]*)")
EXPORT_PREFIX = re.compile(r"^export ")


def split_blocks(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """按顶层声明切段，紧挨着声明的那几行注释跟着段走。"""
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        match = DECL.match(line)
        if not match:
            continue
        j = i
        while j > 0 and lines[j - 1].lstrip().startswith(("/*", "*", "*/", "//")):
            j -= 1
        starts.append((j, match.group(1)))
    header = lines[: starts[0][0]] if starts else lines
    blocks: list[tuple[str, list[str]]] = []
    for n, (j, name) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        chunk = lines[j:end]
        while chunk and not chunk[-1].strip():
            chunk.pop()
        blocks.append((name, chunk))
    return header, blocks


def strip_export(lines: list[str]) -> list[str]:
    """模块里只在声明行前面多了 export；核对时把这一处去掉再比。"""
    out = []
    for line in lines:
        out.append(EXPORT_PREFIX.sub("", line))
    return out


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def git_show(ref: str, rel: str) -> str:
    out = subprocess.run(["git", "show", "%s:%s" % (ref, rel)], cwd=str(REPO),
                         capture_output=True, check=True).stdout
    return out.decode("utf-8").replace("\r\n", "\n")


def classify(line: str, rel: str) -> str:
    """不属于原文的行只能落进这几类，否则返回空串。"""
    stripped = line.strip()
    if not stripped:
        return "空行"
    if stripped.startswith(("/*", "*", "*/", "//")):
        return "注释"
    if stripped.startswith("import "):
        return "import"
    if stripped.startswith("{") and stripped.endswith("};"):
        return "export 列表续行"
    if rel == "local/ui/main.js":
        return "main.js 接线"
    return ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-ref", default="fb3e035", help="开工 HEAD，默认取计划开工时那个提交")
    args = ap.parse_args(argv)

    originals = {rel: git_show(args.base_ref, rel) for rel in ORIGINALS}
    targets = {rel: read_text(REPO / rel) for rel in TARGETS}

    # 每一段的原文（去掉 export）与新文件全文（同样去掉 export 后按行比对）
    target_lines = {rel: strip_export(text.split("\n")) for rel, text in targets.items()}

    total = 0
    found: list[tuple[str, str, str]] = []      # (原文件, 名字, 新文件)
    missing: list[tuple[str, str]] = []
    covered: dict[str, set[int]] = {rel: set() for rel in TARGETS}

    for rel, text in originals.items():
        _, blocks = split_blocks(text.split("\n"))
        for name, chunk in blocks:
            total += 1
            want = strip_export(chunk)
            # 原文的文件头注释贴在第一个声明上；搬的时候它被挪到编排层文件顶部，
            # 所以这一段要按「去掉前导注释」的两种形态各试一次
            bare = list(want)
            while bare and bare[0].lstrip().startswith(("/*", "*", "*/", "//")):
                bare.pop(0)
            candidates = [want] if bare == want else [want, bare]
            hit = None
            for form in candidates:
                for target_rel, lines in target_lines.items():
                    for start in range(len(lines) - len(form) + 1):
                        if lines[start:start + len(form)] == form:
                            hit = (target_rel, start, len(form))
                            break
                    if hit:
                        break
                if hit:
                    break
            if hit is None:
                missing.append((rel, name))
                continue
            found.append((rel, name, hit[0]))
            covered[hit[0]].update(range(hit[1], hit[1] + hit[2]))

    # 反查：新文件里没被任何原文段落覆盖的行
    unclassified: list[tuple[str, int, str]] = []
    extra: dict[str, int] = {}
    # 开工 HEAD 上本来就有的文件（log.js、main.js），它们原有的行不算搬家新写的
    own = {}
    for rel in TARGETS:
        try:
            own[rel] = set(line.rstrip() for line in git_show(args.base_ref, rel).split("\n"))
        except subprocess.CalledProcessError:
            own[rel] = set()
    for rel in TARGETS:
        for i, line in enumerate(target_lines[rel]):
            if i in covered[rel]:
                continue
            if line.rstrip() in own[rel]:
                extra["原有行"] = extra.get("原有行", 0) + 1
                continue
            kind = classify(line, rel)
            if not kind:
                unclassified.append((rel, i + 1, line.rstrip()))
                continue
            extra[kind] = extra.get(kind, 0) + 1

    print("原文文件：%s（开工 HEAD %s）" % ("、".join(ORIGINALS), args.base_ref))
    print("顶层声明段：%d 段" % total)
    print("一字不差找到：%d 段" % len(found))
    print("找不到：%d 段" % len(missing))
    for rel, name in missing:
        print("   %s :: %s" % (rel, name))
    print("新文件里不属于原文的行，按类：")
    for kind in sorted(extra):
        print("   %-12s %d 行" % (kind, extra[kind]))
    print("分不进任何一类：%d 行" % len(unclassified))
    for rel, line_no, text in unclassified[:40]:
        print("   %s:%d  %s" % (rel, line_no, text))

    bad = bool(missing) or bool(unclassified)
    print("\n结论：%s" % ("有段找不到或有行分不进任何一类" if bad else "全部找到且相同，多出来的行全部可归类"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
