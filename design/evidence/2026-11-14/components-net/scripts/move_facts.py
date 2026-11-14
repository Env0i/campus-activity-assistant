#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搬家事实清点（只读）：名字引用表、面板成员表、反向表与按路径加载的测试表，结果打印
到标准输出。

表一「名字引用」——views/phone.js 与 views/settings.js 每个顶层名字被哪些别的脚本引用、
各几处、有没有加载期（文件顶层，任何函数体之外）就引用的。
引用按名字匹配：抹掉字符串、模板串、注释后按词匹配；裸名字与 typeof 判断
（typeof PhonePanel）算引用；经显式挂载点的访问（window.PhonePanel、
globalThis.PhonePanel）也算引用——搬成模块后这些引用要靠挂载点接上，漏了它们就是漏了
最要紧的一组；其余属性访问（前面带点）不算；本文件自己的名字在该文件里不算；import
语句里的具名引用算引用。

表一·面板成员——PhonePanel 与 OcrPanel 按成员列：别的脚本用了它的哪个成员
（refresh、state、feature、installing、busy、downloadComponent、cancelComponent、
openComponents 等），在哪个文件、哪个函数、是不是加载期就用的。

反向表——views/phone.js 与 views/settings.js 各自用到的、定义在别的脚本里的名字
（取元素、发桥接请求、状态仓库、别的视图的重画函数等），各在几处、在哪些函数里用、
有没有加载期就用的。

表三「按路径加载的测试」——哪些测试按文件路径读或加载这两个文件：
方式一读源码（read / read_text / 拼接清单），方式二 run_phone_js 的 files 参数；
对 files 加载的调用再抓片段文本，列出片段里用到这两个文件的哪些顶层名字。

不写任何仓库文件；不联网。用法（仓库根，Python 一律带 -B）：
  python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py

@author Author
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[5]
UI = REPO / "local" / "ui"
TESTS = REPO / "local" / "tests"

TARGETS = ("views/phone.js", "views/settings.js")
PANELS = (("PhonePanel", "views/phone.js"), ("OcrPanel", "views/settings.js"))

# 字符串 / 模板串 / 注释的抹除（与 mutate_reads.py 同一做法：抹成等长空白保行号）
_LEX_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`'
    r'|//[^\n]*|/\*.*?\*/', re.S)

# 控制语句与函数声明的关键字：这些词后面的「名字(…) {」不是对象方法
_CTRL_WORDS = {"if", "for", "while", "switch", "catch", "return", "typeof", "new",
               "await", "do", "else", "case", "function", "async", "delete", "void"}


def scrub(text: str) -> str:
    return _LEX_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def top_level_names(rel: str) -> list:
    """一个视图文件的顶层声明名（function / const / let / var，深度 0；模块的 export 声明也算）。"""
    path = UI / rel
    text = scrub(path.read_text(encoding="utf-8"))
    names = []
    depth = 0
    decl = re.compile(
        r"^\s*(?:export\s+)?(?:async\s+)?(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)")
    for line in text.splitlines():
        for m in decl.finditer(line):
            if depth == 0:
                names.append(m.group(1))
        depth += line.count("{") + line.count("(") - line.count("}") - line.count(")")
    return names


def referenced(name: str, body: str) -> list:
    """body 里对该名字的引用位置（0 起始偏移）。裸名字与 typeof 判断算引用；经显式
    挂载点的访问（window.X、globalThis.X）也算；其余属性访问（前面带点）不算。"""
    esc = re.escape(name)
    pat = re.compile(
        r"(?<![\w$.])" + esc + r"(?![\w$])"
        r"|(?<=" + re.escape("window.") + r")" + esc + r"(?![\w$])"
        r"|(?<=" + re.escape("globalThis.") + r")" + esc + r"(?![\w$])")
    return [m.start() for m in pat.finditer(body)]


def local_declared(name: str, body: str) -> bool:
    """引用文件里有没有该名字自己的声明（function / const / let / var / 形参）。"""
    return bool(re.search(
        r"(?<![\w$.])(?:function\s+" + re.escape(name) + r"\s*\(|"
        r"(?:const|let|var)\s+" + re.escape(name) + r"\s*[=\n]|"
        r"\(\s*(?:async\s+)?" + re.escape(name) + r"[\s,)])", body))


def depth_at(text: str, pos: int) -> int:
    """pos 之前的花括号深度（scrub 后的文本）。"""
    return text[:pos].count("{") - text[:pos].count("}")


def other_ui_files() -> list:
    out = []
    for path in sorted(UI.rglob("*.js")):
        rel = path.relative_to(UI).as_posix()
        if rel == "led.js" or rel.startswith("m/"):
            continue
        out.append(rel)
    return out


def _match_brace(text: str, open_pos: int) -> int:
    """open_pos 是「{」的位置，返回配对「}」的位置；配不上返回文末。"""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def _preceding_word(text: str, pos: int) -> str:
    """pos 之前的最后一个词（跳过空白），没有则空串。"""
    j = pos
    while j > 0 and text[j - 1] in " \t\r\n":
        j -= 1
    end = j
    while j > 0 and (text[j - 1].isalnum() or text[j - 1] in "_$"):
        j -= 1
    return text[j:end]


def function_scopes(text: str) -> list:
    """文件里所有有名字的函数体 [(start, end, 名字, 名字偏移)]，start/end 指函数体花括号区间。

    覆盖四种写法：plain function 声明（function NAME(...) {）、对象成员的方法简写
    （NAME(...) {）、对象成员的箭头函数（NAME: (…) => {）与 const 赋值的箭头函数
    （NAME = (…) => {）。控制语句的括号头（if / for / while / switch / catch 等后面
    跟的「(…) {」）与别对象的方法（前面带点）不算；除 plain function 外，候选头已经
    落在更早记录的函数体里的也不再记。名字偏移是「NAME」的位置，供引用计数排除声明
    本身——方法声明也长得很像引用。"""
    scopes = []

    def record(pat, skip_nested: bool) -> None:
        for m in pat.finditer(text):
            word = _preceding_word(text, m.start())
            before_word = _preceding_word(text, m.start() - len(word)) if word else ""
            if m.group(1) in _CTRL_WORDS \
                    or (word in _CTRL_WORDS and word != "async") \
                    or (word == "async" and before_word == "function") \
                    or text[max(m.start() - 1, 0):m.start()].rstrip().endswith("."):
                continue
            if skip_nested and any(s[0] <= m.start() < s[1] for s in scopes):
                continue
            open_pos = m.end() - 1
            scopes.append([open_pos, _match_brace(text, open_pos), m.group(1), m.start(1)])

    record(re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{"), False)
    record(re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\([^()]{0,200}\)\s*\{"), True)
    record(re.compile(
        r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*:\s*(?:async\s+)?"
        r"(?:\([^()]{0,200}\)|[A-Za-z_$][\w$]*)\s*=>\s*\{"), True)
    record(re.compile(
        r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\([^()]{0,200}\)\s*=>\s*\{"), True)
    scopes.sort(key=lambda s: s[0])
    return [tuple(s) for s in scopes]


def declared_positions(scopes: list) -> set:
    """所有函数名自己的偏移：引用计数里要排除的「声明长得像引用」的位置。"""
    return {item[3] for item in scopes}


def enclosing_label(scopes: list, pos: int) -> str:
    """pos 所在的最内层函数名；不在任何函数体里就是顶层（文件级作用域）。"""
    best = None
    for start, end, name, _npos in scopes:
        if start <= pos < end and (best is None or start > best[0]):
            best = (start, end, name)
    return best[2] if best else "顶层"


def table_one() -> None:
    print("=" * 72)
    print("表一 名字引用：这两个文件的顶层名字被哪些别的脚本引用")
    print("量法：抹掉字符串与注释后按词匹配；裸名字与 typeof 判断算引用；经显式挂载点")
    print("      的访问（window.PhonePanel、globalThis.PhonePanel）也算引用；其余前面带点")
    print("      （属性访问）不算；本文件有同名声明的名字在该文件里不算；import { 名字 }")
    print("      算引用；「加载期」= 引用出现在任何函数体之外的顶层。两个目标文件互为")
    print("      「别的脚本」——phone.js 与 settings.js 之间的引用也算。")
    print("复跑命令：python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py")
    print("=" * 72)
    every = other_ui_files()
    for rel in TARGETS:
        print("\n--- %s 的顶层名字 ---" % rel)
        others = [(orel, scrub((UI / orel).read_text(encoding="utf-8")))
                  for orel in every if orel != rel]
        for name in top_level_names(rel):
            rows = []
            for orel, body in others:
                hits = referenced(name, body)
                if not hits or local_declared(name, body):
                    continue
                top_hits = sum(1 for h in hits if depth_at(body, h) == 0)
                rows.append((orel, len(hits), top_hits))
            if not rows:
                print("  %-22s 无别的脚本引用" % name)
                continue
            mark = "  ←有加载期引用" if any(t for _, _, t in rows) else ""
            print("  %-22s %s%s" % (name, mark, ""))
            for orel, n, t in sorted(rows):
                print("      %-46s 引用 %2d 处，其中顶层 %d 处" % (orel, n, t))


def table_members() -> None:
    print("\n" + "=" * 72)
    print("表一·面板成员：PhonePanel 与 OcrPanel 的成员被哪些别的脚本用")
    print("量法：在别的脚本里找「(window.)面板名.成员」的引用；每个引用归属到它所在的")
    print("      函数（最内层有名字的函数体；plain function 与对象方法简写都算，控制语句")
    print("      的括号头不算），不在任何函数体里记「顶层（加载期）」。本文件用自己面板的")
    print("      成员不在此表——那是 move-facts.md 表二的事。")
    print("复跑命令：python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py")
    print("=" * 72)
    every = other_ui_files()
    for panel, home in PANELS:
        print("\n--- %s（定义于 %s）的成员被谁用 ---" % (panel, home))
        member_map = {}
        for orel in every:
            if orel == home:
                continue
            text = scrub((UI / orel).read_text(encoding="utf-8"))
            scopes = function_scopes(text)
            for m in re.finditer(r"(?:window\.)?" + panel + r"\.([A-Za-z_$][\w$]*)", text):
                member = m.group(1)
                load = depth_at(text, m.start()) == 0
                member_map.setdefault(member, []).append(
                    (orel, enclosing_label(scopes, m.start()), load))
        if not member_map:
            print("  无别的脚本引用")
            continue
        for member in sorted(member_map):
            entries = sorted(member_map[member])
            by_file = {}
            for orel, label, load in entries:
                by_file.setdefault(orel, []).append((label, load))
            print("  %-18s 共 %d 处" % (member, len(entries)))
            for orel, items in sorted(by_file.items()):
                labels = []
                load_n = 0
                for label, load in items:
                    load_n += 1 if load else 0
                    if label not in labels:
                        labels.append(label)
                mark = "，其中加载期 %d 处" % load_n if load_n else ""
                print("      %-46s %d 处（%s%s）" % (orel, len(items), "、".join(labels), mark))


def table_reverse() -> None:
    print("\n" + "=" * 72)
    print("反向表：这两个文件各自用到的、定义在别的脚本里的名字")
    print("量法：把其余界面脚本（led.js 与手机页 m/ 不算）的顶层声明名取并集，逐个在这两个")
    print("      文件里按词找引用（挂载点访问也算，前面带点不算）；本文件自己声明过的名字")
    print("      不算。每个名字列出引用几处、在哪些函数里用（最内层函数）、有没有加载期就用的。")
    print("复跑命令：python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py")
    print("=" * 72)
    every = other_ui_files()
    decls = {orel: set(top_level_names(orel)) for orel in every}
    for rel in TARGETS:
        print("\n--- %s 用到的外部名字 ---" % rel)
        text = scrub((UI / rel).read_text(encoding="utf-8"))
        scopes = function_scopes(text)
        declared = declared_positions(scopes)
        found = {}
        for orel in every:
            if orel == rel:
                continue
            for name in decls[orel]:
                hits = [h for h in referenced(name, text) if h not in declared]
                if not hits or local_declared(name, text):
                    continue
                item = found.setdefault(name, {"count": 0, "load": 0, "files": [], "labels": []})
                item["count"] += len(hits)
                item["load"] += sum(1 for h in hits if depth_at(text, h) == 0)
                if orel not in item["files"]:
                    item["files"].append(orel)
                for h in hits:
                    label = enclosing_label(scopes, h)
                    if label not in item["labels"]:
                        item["labels"].append(label)
        if not found:
            print("  无")
            continue
        for name in sorted(found, key=lambda n: -found[n]["count"]):
            item = found[name]
            mark = "，加载期 %d 处" % item["load"] if item["load"] else ""
            print("  %-24s %3d 处（定义于 %s；%s%s）" % (
                name, item["count"], "、".join(sorted(item["files"])),
                "、".join(item["labels"][:8]) + ("…" if len(item["labels"]) > 8 else ""), mark))


# ---------------------------------------------------------------- 表三
_READ_PAT = re.compile(
    r'read\(\s*"ui/(views/(?:phone|settings)\.js)"\s*\)'
    r'|(?:LOCAL\s*/\s*"ui"\s*/\s*"views"\s*/\s*"(?:phone|settings)\.js")'
    r'|(?:read_text\([^)]*"(?:phone|settings)\.js"\))'
    r'|(?:_read\(\s*"ui"\s*,\s*"views"\s*,\s*"(?:phone|settings)\.js"\s*\))')


def _string_consts_in_assign(tree) -> dict:
    """模块级与类级「名字 = 字符串」赋值，供片段变量名回查原文。"""
    out = {}

    def walk_body(body):
        for node in body:
            if isinstance(node, ast.Assign):
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            out[t.id] = value.value
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.If)):
                walk_body(getattr(node, "body", []))

    walk_body(tree.body)
    return out


def _snippet_text(node, consts) -> str:
    """run_phone_js 的第一个实参还原成片段文本：字符串字面量直接取，变量名回查赋值。"""
    if not node.args:
        return ""
    arg = node.args[0]
    if isinstance(arg, ast.BinOp):   # SETUP + r"""...""" 的拼接
        parts = []
        for piece in ast.walk(arg):
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                parts.append(piece.value)
            elif isinstance(piece, ast.Name) and piece.id in consts:
                parts.append(consts[piece.id])
        return "\n".join(parts)
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.Name) and arg.id in consts:
        return consts[arg.id]
    return ""


def collect_test_usage() -> None:
    print("\n" + "=" * 72)
    print("表三 按路径加载的测试：哪些测试按文件路径读或加载这两个文件")
    print("量法：逐个测试文件找两种方式——读源码（read / read_text 指到这两个文件），")
    print("      run_phone_js(..., files=[...]) 的 files 参数（ast 解析；片段还原后列出")
    print("      片段里用到的这两个文件的顶层名字）。行号按当前文件。")
    print("复跑命令：python -B design/evidence/2026-11-14/components-net/scripts/move_facts.py")
    print("=" * 72)
    names = {rel: set(top_level_names(rel)) for rel in TARGETS}
    for path in sorted(TESTS.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        found = []
        for i, line in enumerate(lines, start=1):
            if _READ_PAT.search(line):
                found.append((i, "读源码", line.strip()[:110]))
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        consts = _string_consts_in_assign(tree) if tree else {}
        if tree:
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "run_phone_js"):
                    continue
                files_kw = next((k for k in node.keywords if k.arg == "files"), None)
                if files_kw is None or not isinstance(files_kw.value, ast.List):
                    continue
                loaded = [e.value for e in files_kw.value.elts
                          if isinstance(e, ast.Constant)]
                if not any(t in loaded for t in TARGETS):
                    continue
                snippet = _snippet_text(node, consts)
                used = []
                for rel in TARGETS:
                    if rel not in loaded:
                        continue
                    hits = sorted(n for n in names[rel] if referenced(n, snippet))
                    used.append("%s → %s" % (rel, "、".join(hits) or "（片段未直接用到）"))
                found.append((node.lineno, "files 加载", "；".join(used)))
        if found:
            print("\n--- %s ---" % path.name)
            for lineno, how, detail in sorted(found):
                print("  行 %-4d %-14s %s" % (lineno, how, detail))


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    table_one()
    table_members()
    table_reverse()
    collect_test_usage()


if __name__ == "__main__":
    main()
