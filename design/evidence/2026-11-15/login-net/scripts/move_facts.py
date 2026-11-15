# -*- coding: utf-8 -*-
"""清点搬文件要用的事实：五张表全部由本脚本算出（只读源码，不改任何文件）。

用法（仓库根）：
  python -B design/evidence/<日期>/login-net/scripts/move_facts.py [输出 json]

表一 名字引用（含加载期用到）；表二 状态字段的写点/读点；表三 反向调用；
表四 refresh.js 每个函数属于登录检查 / 活动列表 / 两者都有；表五通用名字的使用方。

扫描范围：local/ui/**/*.js 去掉 local/ui/m/（手机页单独一份）。表一的「加载期」按顶层语句判定，见 name_refs。

@author Author
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
UI = REPO / "local" / "ui"
BLOCK_FILES = ["state/login.js", "views/login.js", "views/relogin.js"]
VIEW_FILES = ["views/login.js", "views/relogin.js"]
REFRESH = "controllers/refresh.js"
FUNC_RE = re.compile(r"(?m)^(?:async )?function ([A-Za-z_$][\w$]*)\s*\(")
STR_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')

LOGIN_TOKENS = ("S.login", "loginPending", "checking", "paintLogin", "autoLogin",
                "relogin", "S.autoLogin", "session_present")
LIST_TOKENS = ("S.items", "activities", "applyActivities", "S.listState", "render(",
               "S.filter", "signed", "list_activities", "S.runtime.listPending")

GENERIC = ("addLog", "setBusy", "setResult")


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def js_sources() -> dict[str, str]:
    """本机界面的脚本；不含 local/ui/m/（手机页自己在闭包里定义同名函数，不是桌面版的使用方）。"""
    out = {}
    for p in sorted(UI.rglob("*.js")):
        if not p.is_file():
            continue
        rel = p.relative_to(UI).as_posix()
        if not rel.startswith("m/"):
            out[rel] = read(p)
    return out


def function_ranges(text: str) -> list[tuple[str, int, int]]:
    """顶层函数的 (名字, 起始行, 结束行)，按下一个顶层 function 或文件尾定界。"""
    starts = [(m.group(1), text.count("\n", 0, m.start()) + 1) for m in FUNC_RE.finditer(text)]
    lines = text.count("\n") + 1
    out = []
    for i, (name, line) in enumerate(starts):
        end = starts[i + 1][1] - 1 if i + 1 < len(starts) else lines
        out.append((name, line, end))
    return out


def owner(ranges: list[tuple[str, int, int]], line: int) -> str:
    for name, start, end in ranges:
        if start <= line <= end:
            return name
    return "<顶层>"


def mask(text: str) -> str:
    """把注释与字符串内容换成空格（换行保留，长度不变）。只用来数名字，不用来读文本。"""
    out = []
    i, n, mode = 0, len(text), None
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if mode is None:
            if ch in "'\"`":
                mode = ch
                out.append(ch)
            elif ch == "/" and nxt == "/":
                mode = "//"
                out.append("  ")
                i += 2
                continue
            elif ch == "/" and nxt == "*":
                mode = "/*"
                out.append("  ")
                i += 2
                continue
            else:
                out.append(ch)
        elif mode in "'\"`":
            if ch == "\\" and nxt:
                out.append(" " + ("\n" if nxt == "\n" else " "))
                i += 2
                continue
            if ch == mode:
                mode = None
                out.append(ch)
            else:
                out.append("\n" if ch == "\n" else " ")
        elif mode == "//":
            if ch == "\n":
                mode = None
                out.append("\n")
            else:
                out.append(" ")
        else:
            if ch == "*" and nxt == "/":
                mode = None
                out.append("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
        i += 1
    return "".join(out)


def depth_at(masked: str) -> list[int]:
    """掩码后文本里每个字符位置的花括号深度；0 就是文件顶层语句（不在任何 {} 里）。"""
    out = []
    depth = 0
    for ch in masked:
        out.append(depth)
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
    return out


def name_refs(masked: str, depths: list[int], name: str) -> list[dict]:
    """名字在一份脚本里的每一处引用（调用或取值；不算声明与对象键）。

    load 为真：落在文件顶层语句上（不在任何 {} 里、同一行也没有 => 箭头），即加载期就执行或取值。
    口径的局限：顶层的 if (x) loginEntry(); 这类无花括号语句也算加载期。
    """
    out = []
    for m in re.finditer(r"(?<![\w$.])%s(?![\w$])" % re.escape(name), masked):
        before = masked[:m.start()]
        after = masked[m.end():]
        if re.search(r"function\s+$", before[-40:]):
            continue
        if re.match(r"\s*:", after) and before.rstrip()[-1:] in ("{", ","):
            continue
        line = before.count("\n") + 1
        line_head = before[before.rfind("\n") + 1:]
        kind = "调用" if re.match(r"\s*\(", after) else "取值"
        load = depths[m.start()] == 0 and "=>" not in line_head
        out.append({"line": line, "kind": kind, "load": load})
    return out


def table_names(sources: dict[str, str], masks: dict[str, str], depths: dict[str, list[int]]) -> list[dict]:
    """表一：块内每个顶层函数名被别的脚本引用几处；落在顶层语句上的（加载期）单独列出。"""
    rows = []
    for rel in BLOCK_FILES:
        for name, start, _end in function_ranges(sources[rel]):
            refs = []
            for other in sources:
                if other == rel:
                    continue
                hits = name_refs(masks[other], depths[other], name)
                if hits:
                    refs.append({"file": other, "count": len(hits),
                                 "load": [dict(h, file=other) for h in hits if h["load"]]})
            if refs:
                rows.append({"file": rel, "fn": name, "line": start, "refs": refs})
    return rows


def field_key(m: re.Match) -> str:
    if m.group(3):
        return "S.autoLogin"
    if m.group(1):
        return "S.%s.%s" % (m.group(1), m.group(2))
    return "reloginRelay" + ("." + m.group(4) if m.group(4) else "")


def table_fields(sources: dict[str, str]) -> list[dict]:
    """表二：S.login.* / S.relogin.* / S.autoLogin / reloginRelay 的写点与读点。

    口径：单字段赋值算写；整体替换（S.login = {…} / S.relogin = {…} / reloginRelay = {…}）
    单独记为「整体替换」，它同时写掉该对象的全部字段。
    """
    pat = re.compile(r"S\.(login|relogin)\.([A-Za-z_$][\w$]*)"
                     r"|S\.(autoLogin)\b|\breloginRelay(?:\.([A-Za-z_$][\w$]*))?\b")
    write = re.compile(r"S\.(?:login|relogin)\.[A-Za-z_$][\w$]*\s*=(?!=)"
                       r"|S\.autoLogin\s*=(?!=)|\breloginRelay\s*=(?!=)")
    whole = re.compile(r"\bS\.(login|relogin)\s*=(?!=)|\breloginRelay\s*=(?!=)")
    data = defaultdict(lambda: {"writers": set(), "readers": set()})
    for rel, text in sources.items():
        ranges = function_ranges(text)
        for m in whole.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            key = "S.%s(整体)" % m.group(1) if m.group(1) else "reloginRelay(整体)"
            data[key]["writers"].add("%s:%s" % (rel, owner(ranges, line)))
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            key = field_key(m)
            after = text[m.end():m.end() + 4]
            head = text[m.start():m.end()]
            tail = after.lstrip()
            is_write = bool(write.match(head)) or (tail.startswith("=") and not tail.startswith("=="))
            bucket = "writers" if is_write else "readers"
            data[key][bucket].add("%s:%s" % (rel, owner(ranges, line)))
    rows = []
    for key in sorted(data):
        w = sorted(data[key]["writers"])
        r = sorted(data[key]["readers"])
        if w or r:
            rows.append({"field": key, "writers": w, "readers": r})
    return rows


def table_reverse(sources: dict[str, str]) -> list[dict]:
    """表三：状态层调视图层、视图层发桥接请求的每一处。"""
    rows = []
    view_names = set()
    for rel in VIEW_FILES:
        view_names.update(FUNC_RE.findall(sources[rel]))
    state_text = sources["state/login.js"]
    ranges = function_ranges(state_text)
    for name in sorted(view_names):
        pattern = re.compile(r"(?<![\w$.])%s\s*\(" % re.escape(name))
        for m in pattern.finditer(state_text):
            line = state_text.count("\n", 0, m.start()) + 1
            rows.append({"kind": "状态层调视图层", "in": "state/login.js",
                         "line": line, "target": name, "from": owner(ranges, line)})
    for rel in VIEW_FILES:
        text = sources[rel]
        ranges = function_ranges(text)
        for m in re.finditer(r"\bapi\s*\(\s*\"([^\"]+)\"", text):
            line = text.count("\n", 0, m.start()) + 1
            rows.append({"kind": "视图层发桥接请求", "in": rel, "line": line,
                         "target": "api(\"%s\")" % m.group(1), "from": owner(ranges, line)})
        for pat, label in ((re.compile(r"window\.pywebview"), "直接读 window.pywebview"),
                           (re.compile(r"\bPhonePanel\."), "读手机页对象 PhonePanel")):
            for m in pat.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                rows.append({"kind": "视图层发桥接请求", "in": rel, "line": line,
                             "target": label, "from": owner(ranges, line)})
    return rows


def table_refresh(sources: dict[str, str]) -> list[dict]:
    """表四：refresh.js 每个函数归哪一类，并给两者都有时的交织行。"""
    text = sources[REFRESH]
    ranges = function_ranges(text)
    lines = text.split("\n")
    rows = []
    for name, start, end in ranges:
        body = "\n".join(lines[start - 1:end])
        login_lines = [start + i for i, ln in enumerate(lines[start - 1:end])
                       if any(t in ln for t in LOGIN_TOKENS)]
        list_lines = [start + i for i, ln in enumerate(lines[start - 1:end])
                      if any(t in ln for t in LIST_TOKENS)]
        if login_lines and list_lines:
            kind = "两者都有"
        elif login_lines:
            kind = "登录检查"
        elif list_lines:
            kind = "活动列表"
        else:
            kind = "都不是（计划/通用）"
        rows.append({"fn": name, "line": start, "kind": kind,
                     "login_lines": login_lines, "list_lines": list_lines})
    return rows


def table_generic(sources: dict[str, str], masks: dict[str, str], depths: dict[str, list[int]]) -> list[dict]:
    """表五：addLog / setBusy / setResult 的全部使用方（只列，不搬；声明不算）。"""
    rows = []
    for name in GENERIC:
        users = []
        for rel in sources:
            n = len(name_refs(masks[rel], depths[rel], name))
            if n:
                users.append({"file": rel, "count": n})
        rows.append({"fn": name, "users": users})
    return rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sources = js_sources()
    masks = {rel: mask(text) for rel, text in sources.items()}
    for rel, text in sources.items():
        assert len(masks[rel]) == len(text), rel
    depths = {rel: depth_at(text) for rel, text in masks.items()}
    out = {"names": table_names(sources, masks, depths), "fields": table_fields(sources),
           "reverse": table_reverse(sources), "refresh": table_refresh(sources),
           "generic": table_generic(sources, masks, depths)}

    print("== 表一：名字引用（外部脚本 -> 块内函数）；加载期 = 落在该脚本顶层语句上 ==")
    for row in out["names"]:
        refs = []
        for r in row["refs"]:
            text = "%s×%d" % (r["file"], r["count"])
            if r["load"]:
                text += "（加载期：" + "，".join("L%d %s" % (h["line"], h["kind"]) for h in r["load"]) + "）"
            refs.append(text)
        print("%-20s %-26s %s" % (row["file"], row["fn"], ", ".join(refs)))

    print("\n== 表一附：加载期引用逐条 ==")
    for row in out["names"]:
        for r in row["refs"]:
            for h in r["load"]:
                print("%s:L%d %s（%s）用于 %s" % (r["file"], h["line"], row["fn"], h["kind"], row["file"]))

    print("\n== 表二：状态字段的写点 / 读点（文件:函数） ==")
    for row in out["fields"]:
        print("%-24s 写[%s] 读[%s]" % (row["field"], "; ".join(row["writers"]),
                                      "; ".join(row["readers"])))

    print("\n== 表三：反向调用 ==")
    for row in out["reverse"]:
        print("%-12s %-18s L%-4d %-22s %s" % (row["kind"], row["in"], row["line"],
                                              row["target"], row["from"]))

    print("\n== 表四：refresh.js 函数分类 ==")
    for row in out["refresh"]:
        marks = ""
        if row["kind"] == "两者都有":
            marks = " 交织行 %s" % row["login_lines"]
        print("%-28s L%-4d %-14s%s" % (row["fn"], row["line"], row["kind"], marks))

    print("\n== 表五：通用名字的使用方 ==")
    for row in out["generic"]:
        print("%-10s %s" % (row["fn"], ", ".join("%s×%d" % (u["file"], u["count"])
                                                for u in row["users"])))

    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
