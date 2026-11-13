#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T5②：清点基线 7e2d31c 中 local/app.py 的 Api 方法（ast 提取，不手抄）。

从仓库根运行（只读，不写任何文件）：
    python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/api_methods.py

输出：
  [summary]  方法总数 / 公开 / 私有
  [public]   每个公开方法：行号、修饰器、docstring 首行、所属分节注释
  [detail]   每个公开方法：读/写的 self 实例字段、调用的模块级函数
  [fields]   全部实例字段（含私有），标注哪些方法读写
  [locks]    模块级与实例上的锁对象（threading.Lock/RLock/Event）来源行
"""
import ast
import re
import subprocess
import sys

COMMIT = "7e2d31c"
REL = "local/app.py"
SECTION_RE = re.compile(r"#\s*-{3,}\s*(.+?)\s*-{3,}\s*$")
LOCK_RE = re.compile(
    r"^\s*(?:self\.([A-Za-z_0-9]+)|([A-Z_a-z][A-Za-z_0-9]*)\s*=\s*threading\.(?:Lock|RLock|Event|Condition)\(\))")


def git_show(rel: str) -> str:
    proc = subprocess.run(["git", "show", "%s:%s" % (COMMIT, rel)],
                          capture_output=True)
    if proc.returncode != 0:
        raise SystemExit("git show %s 失败：%s" % (
            rel, proc.stderr.decode("utf-8", "replace")))
    return proc.stdout.decode("utf-8")


def attr_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return attr_name(node.value) + "." + node.attr
    return "?"


def method_info(node: ast.FunctionDef, sections, class_fields):
    doc = ast.get_docstring(node) or ""
    first_doc = doc.splitlines()[0].strip() if doc else ""
    section = ""
    for lineno, text in sections:
        if lineno < node.lineno:
            section = text
    assigned, read = set(), set()
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) \
                and n.value.id == "self":
            if isinstance(n.ctx, ast.Store):
                assigned.add(n.attr)
            else:
                read.add(n.attr)
    # 调用的模块级名字（Call 的 func 是裸 Name，且不是内置/局部变量）
    local_names = {a.arg for a in node.args.args}
    local_names |= {n.id for n in ast.walk(node) if isinstance(n, ast.Name)
                    and isinstance(n.ctx, ast.Store)}
    local_names |= {n.name for n in ast.walk(node) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    calls = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                and n.func.id not in local_names:
            calls.add(n.func.id)
    decorators = []
    for d in node.decorator_list:
        decorators.append(attr_name(d))
    class_fields.update(assigned | read)
    return {
        "name": node.name,
        "lineno": node.lineno,
        "end": node.end_lineno,
        "decorators": decorators,
        "doc": first_doc,
        "section": section,
        "assigned": sorted(assigned),
        "read": sorted(read),
        "calls": sorted(calls),
    }


def main() -> int:
    src = git_show(REL)
    lines = src.splitlines()
    tree = ast.parse(src)
    sections = []
    for idx, line in enumerate(lines, start=1):
        m = SECTION_RE.match(line)
        if m:
            sections.append((idx, m.group(1)))
    api_cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Api":
            api_cls = node
    if api_cls is None:
        raise SystemExit("基线 %s 中找不到 class Api" % REL)
    methods = []
    class_fields = set()
    for node in ast.iter_child_nodes(api_cls):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(method_info(node, sections, class_fields))
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    class_fields.add(tgt.id)
    methods.sort(key=lambda m: m["lineno"])
    public = [m for m in methods if not m["name"].startswith("_")]
    private = [m for m in methods if m["name"].startswith("_")]

    print("[summary]")
    print("class Api 定义于 %s:%d（基线 %s）" % (REL, api_cls.lineno, COMMIT))
    print("方法总数=%d 公开=%d 私有=%d" % (
        len(methods), len(public), len(private)))

    print("[public] name | line | decorators | section | doc-first-line")
    for m in public:
        print("%s | L%d | %s | %s | %s" % (
            m["name"], m["lineno"], ",".join(m["decorators"]) or "-",
            m["section"] or "-", m["doc"] or "-"))

    print("[detail] name | assigned | read | calls")
    for m in public:
        print("%s | %s | %s | %s" % (
            m["name"], ",".join(m["assigned"]) or "-",
            ",".join(m["read"]) or "-", ",".join(m["calls"]) or "-"))

    # 全部实例字段（含私有），来源=方法内 self.X 赋值或读 + 类体类属性
    field_users = {}
    for m in methods:
        for f in m["assigned"]:
            field_users.setdefault(f, {"w": [], "r": []})["w"].append(m["name"])
        for f in m["read"]:
            field_users.setdefault(f, {"w": [], "r": []})["r"].append(m["name"])
    print("[fields] field | writers | readers")
    for f in sorted(field_users):
        info = field_users[f]
        print("%s | %s | %s" % (f, ",".join(info["w"]) or "-",
                                ",".join(info["r"]) or "-"))

    print("[locks] 模块级/实例锁来源（threading.Lock/RLock/Event/Condition 赋值行）")
    for idx, line in enumerate(lines, start=1):
        if re.search(r"threading\.(Lock|RLock|Event|Condition)\(", line):
            print("L%d: %s" % (idx, line.strip()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
