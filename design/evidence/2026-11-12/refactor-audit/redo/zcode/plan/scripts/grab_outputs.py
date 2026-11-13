#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grab.py 输出协议审计脚本（T4，基线 7e2d31c，只读）。

从仓库根执行：
    python -I design/evidence/2026-11-12/refactor-audit/redo/zcode/plan/scripts/grab_outputs.py

内部执行 `git show 7e2d31c:local/grab.py` 取基线内容，用 ast 模块解析：
  1. 全部 print / sys.stdout.write / sys.stderr.write / logging 输出调用；
     本文件自有日志出口 log() / log_event() / _stderr_note() 单独标注（kind=log_func），
     不与 print/logging 混计——它们既打 stdout 也写 grab.log；
  2. return / sys.exit 的退出码常量，按 argparse 子命令归属。子命令注册方式是
     sub.add_parser("name") + p.set_defaults(func=cmd_x)，main() 顶层分发
     args.func(args) 算一条入口（main 的返回值经 sys.exit(main()) 变进程退出码）；
  3. 嵌套函数（函数体内定义的函数）里的 return 单独归档，标注「非子命令退出码」；
     非子命令的辅助函数返回 int 常量也单独归档，标注「非退出码」。

输出结构化 JSON 清单到 stdout；只读：不改任何文件、不联网、不执行被解析代码。

@author Agent
"""

import ast
import json
import subprocess
import sys

BASELINE_COMMIT = "7e2d31c"
TARGET = "local/grab.py"

# 本文件自有日志出口（不是 print/logging，但最终都会 print 到 stdout）
LOG_FUNCS = {"log", "log_event", "_stderr_note"}
# logging 模块的输出方法
LOGGING_METHODS = {"debug", "info", "warning", "warn", "error",
                   "critical", "exception", "log"}


def show_baseline():
    """git show 基线文件；失败即退出 2。"""
    proc = subprocess.run(
        ["git", "show", "%s:%s" % (BASELINE_COMMIT, TARGET)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write("[X] git show 失败：%s\n"
                         % proc.stderr.decode("utf-8", "replace"))
        raise SystemExit(2)
    return proc.stdout.decode("utf-8", errors="replace")


def call_target(node):
    """Attribute 链摊平成 (根名, ...)，便于匹配 print / sys.stdout.write / log。"""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return tuple(reversed(parts))
    return None


def expr_source(node, source_text):
    """表达式节点的源码文本（压缩空白、截断），用于描述动态 return。"""
    try:
        seg = ast.get_source_segment(source_text, node) or ""
    except Exception:
        seg = ""
    return " ".join(seg.split())[:160]


def snippet_of(call, source_text):
    """输出调用的可读片段：首个常量位置参数（截断），否则整句表达式。"""
    for arg in call.args:
        if isinstance(arg, ast.Constant):
            if isinstance(arg.value, str):
                return "STR " + " ".join(arg.value.split())[:120]
            return "LIT %r" % (arg.value,)
        if isinstance(arg, ast.JoinedStr):
            return "FSTR"
        if isinstance(arg, ast.BinOp):
            return "EXPR " + expr_source(arg, source_text)
        if isinstance(arg, (ast.Name, ast.Attribute)):
            return "EXPR " + expr_source(arg, source_text)
    if call.keywords:
        return "KW " + ",".join(k.arg or "**" for k in call.keywords)
    return "CALL"


def classify_call(call):
    """输出调用分类：print / stream_write / logging / log_func（自有出口）。"""
    target = call_target(call.func)
    if not target:
        return None
    root = target[0]
    if target == ("print",):
        return ("print", "stdout")
    if len(target) == 3 and root == "sys" and target[1] in ("stdout", "stderr") \
            and target[2] == "write":
        return ("stream_write", target[1])
    if root == "logging" and target[-1] in LOGGING_METHODS:
        return ("logging", target[-1])
    if len(target) == 1 and root in LOG_FUNCS:
        return ("log_func", root)
    return None


def own_nodes(func_node):
    """遍历函数自身作用域的节点；不进入嵌套 FunctionDef 子树（它们单独建档）。

    返回 (节点生成器, 嵌套函数定义列表)。装饰器与参数默认值也算本函数。
    """
    stack = list(getattr(func_node, "decorator_list", []))
    args = func_node.args
    stack += [d for d in (args.defaults + args.kw_defaults) if d is not None]
    stack += list(func_node.body)
    nested = []
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if not isinstance(node, ast.Lambda):
                nested.append(node)
            continue  # 嵌套函数体不属于本函数
        stack.extend(ast.iter_child_nodes(node))


class FuncInfo:
    """一个函数定义的收集结果。"""

    def __init__(self, name, node, scope, owner_chain):
        self.name = name
        self.node = node
        self.scope = scope            # subcommand | main | helper | nested
        self.owner_chain = owner_chain
        self.outputs = []             # (line, kind, stream, snippet)
        self.const_returns = []       # (line, int) 常量 int return
        self.dynamic_returns = []     # (line, src) 非常量 return
        self.subcommand = None


def collect(info, source_text):
    """收集一个函数的输出调用与 return；顺带登记本函数体内的嵌套函数定义。

    own_nodes 不进入嵌套函数子树，所以这里看到的 FunctionDef 就是直接嵌套定义；
    它们的输出与 return 由调用方递归建档，绝不混进本函数（嵌套函数的 return
    不是子命令退出码，须分开标注）。
    """
    nested_defs = []
    for node in own_nodes(info.node):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested_defs.append(node)
        elif isinstance(node, ast.Call):
            kind = classify_call(node)
            if kind:
                info.outputs.append(
                    (node.lineno, kind[0], kind[1], snippet_of(node, source_text)))
        elif isinstance(node, ast.Return):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, int)                     and not isinstance(value.value, bool):
                info.const_returns.append((node.lineno, value.value))
            elif value is not None:
                info.dynamic_returns.append((node.lineno, expr_source(value, source_text)))
    return nested_defs


def find_sys_exit(tree, source_text):
    """全文件 sys.exit(...) 调用（模块级出口）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and call_target(node.func) == ("sys", "exit"):
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant):
                out.append((node.lineno, repr(arg.value), True))
            elif arg is None:
                out.append((node.lineno, "None", True))
            else:
                out.append((node.lineno, expr_source(arg, source_text), False))
    return out


def iter_statements_in_order(stmts):
    """按源码顺序深度优先遍历语句（ast.walk 是广度优先，会把同一层的
    Assign 语句与下一层的 Call 节点分成两批，顺序对不上）。"""
    for stmt in stmts:
        yield stmt
        for _name, value in ast.iter_fields(stmt):
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, ast.stmt):
                    yield from iter_statements_in_order([item])
                elif isinstance(item, ast.ExceptHandler) and item.body:
                    yield from iter_statements_in_order(item.body)


def parse_subcommands(tree):
    """解析 main() 里的 add_parser("name") / set_defaults(func=cmd_x) 注册关系。

    同一个变量名 p 被六个子命令轮流复用，以「最近一次 add_parser 赋值」为准；
    随后的 p.set_defaults / p.add_argument 都归属这个子命令。遍历按语句源码
    顺序进行（见 iter_statements_in_order），赋值与调用不会跨层错序。
    """
    subcommand_func = {}
    subcommand_args = {}
    current_sub = None
    current_var = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            for stmt in iter_statements_in_order(node.body):
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                    target = call_target(stmt.value.func)
                    if target and len(target) >= 2 and target[-1] == "add_parser":
                        name = None
                        if stmt.value.args and isinstance(stmt.value.args[0], ast.Constant):
                            name = str(stmt.value.args[0].value)
                        if name:
                            for t in stmt.targets:
                                if isinstance(t, ast.Name):
                                    current_sub = name
                                    current_var = t.id
                                    subcommand_args.setdefault(name, [])
                elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                    call = stmt.value
                    target = call_target(call.func)
                    if target and len(target) == 2 and target[1] == "set_defaults"                             and current_sub and target[0] == current_var:
                        for kw in call.keywords:
                            if kw.arg == "func" and isinstance(kw.value, ast.Name):
                                subcommand_func[current_sub] = kw.value.id
                                current_sub = None   # 注册完成：后续 add_argument 不再归属
                    if target and len(target) == 2 and target[1] == "add_argument"                             and current_sub and target[0] == current_var:
                        if call.args and isinstance(call.args[0], ast.Constant):
                            subcommand_args.setdefault(current_sub, []).append(
                                "--" + str(call.args[0].value).lstrip("-"))
                        else:
                            subcommand_args.setdefault(current_sub, []).append("<positional>")
    return subcommand_func, subcommand_args


def build_inventory(text):
    """全量清点：返回 (行数, AST, 函数清单, 名字索引, 注册表, 输出调用清单)。"""
    lines = text.splitlines(keepends=True)
    tree = ast.parse(text)
    subcommand_func, subcommand_args = parse_subcommands(tree)

    funcs = []
    info_by_name = {}

    def register(name, node, scope, chain):
        info = FuncInfo(name, node, scope, chain)
        funcs.append(info)
        info_by_name[chain_key(chain, name)] = info
        nested = collect(info, text)
        for sub_node in nested:
            register(sub_node.name, sub_node, "nested", chain + [name])

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "main":
                scope = "main"
            elif node.name in subcommand_func.values():
                scope = "subcommand"
            else:
                scope = "helper"
            register(node.name, node, scope, [])
            info = info_by_name[node.name]
            if scope == "subcommand":
                info.subcommand = [s for s, f in subcommand_func.items()
                                   if f == node.name][0]
            elif scope == "main":
                info.subcommand = "(dispatch main)"

    sub_of_func = {fn: sub for sub, fn in subcommand_func.items()}

    def callers_of(name):
        found = set()
        for info in funcs:
            for node in own_nodes(info.node):
                if isinstance(node, ast.Call):
                    t = call_target(node.func)
                    if t and len(t) == 1 and t[0] == name:
                        found.add(info.name)
        return found

    output_calls = []
    for info in funcs:
        if info.scope == "subcommand":
            attr = {"subcommand": info.subcommand, "function": info.name,
                    "scope": "subcommand"}
        elif info.scope == "main":
            attr = {"subcommand": "(dispatch main)", "function": info.name,
                    "scope": "main"}
        elif info.scope == "nested":
            attr = {"subcommand": "(nested)", "function": info.name,
                    "scope": "nested", "host": info.owner_chain}
        else:
            callers = sorted(callers_of(info.name))
            subs = sorted({sub_of_func[c] for c in callers if c in sub_of_func})
            attr = {"subcommand": ("via:" + ",".join(subs)) if subs else "(helper)",
                    "function": info.name, "scope": "helper", "callers": callers}
        for line, kind, stream, snip in info.outputs:
            output_calls.append({"line": line, "kind": kind, "stream": stream,
                                 "snippet": snip, **attr})
    return lines, tree, funcs, info_by_name, subcommand_func, subcommand_args,         sub_of_func, output_calls, callers_of


def chain_key(chain, name):
    return ".".join(chain + [name]) if chain else name


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    text = show_baseline()
    (lines, tree, funcs, info_by_name, subcommand_func, subcommand_args,
     sub_of_func, output_calls, callers_of) = build_inventory(text)

    exit_code_returns = []
    for info in funcs:
        if info.scope in ("subcommand", "main"):
            for line, value in info.const_returns:
                exit_code_returns.append({
                    "line": line, "value": value, "function": info.name,
                    "subcommand": info.subcommand or "(dispatch main)",
                    "note": ("子命令退出码（%s 函数体自身的 return 常量）" % info.name)
                            if info.scope == "subcommand"
                            else "main() 返回值，经 sys.exit(main()) 变进程退出码"})
            for line, src in info.dynamic_returns:
                exit_code_returns.append({
                    "line": line, "value": None, "dynamic": src,
                    "function": info.name,
                    "subcommand": info.subcommand or "(dispatch main)",
                    "note": "动态返回（非常量表达式），不是字面退出码常量"})

    nested_returns = []
    for info in funcs:
        if info.scope == "nested":
            for line, value in info.const_returns:
                nested_returns.append({
                    "line": line, "value": value, "dynamic": None,
                    "function": info.name, "host": info.owner_chain,
                    "note": "非子命令退出码：嵌套函数返回值（经宿主函数 return 间接生效）"})
            for line, src in info.dynamic_returns:
                nested_returns.append({
                    "line": line, "value": None, "dynamic": src,
                    "function": info.name, "host": info.owner_chain,
                    "note": "非子命令退出码：嵌套函数动态返回值"})

    helper_returns = []
    for info in funcs:
        if info.scope == "helper":
            for line, value in info.const_returns:
                helper_returns.append({
                    "line": line, "value": value, "function": info.name,
                    "note": "非退出码：辅助函数返回的 int 常量"})

    sys_exit_calls = [
        {"line": line, "arg": arg, "is_const": is_const,
         "note": "进程退出码出口" if is_const else "动态（值来自表达式）"}
        for line, arg, is_const in find_sys_exit(tree, text)]

    by_sub = {}
    for sub, fn in sorted(subcommand_func.items()):
        codes = sorted({r["value"] for r in exit_code_returns
                        if r["function"] == fn and r.get("value") is not None})
        dyn = sorted({r["dynamic"] for r in exit_code_returns
                      if r["function"] == fn and r.get("dynamic")})
        nested_codes = sorted({n["value"] for n in nested_returns
                               if n["host"] and n["host"][0] == fn
                               and n.get("value") is not None})
        by_sub[sub] = {
            "handler": fn,
            "args": subcommand_args.get(sub, []),
            "exit_code_constants": codes,
            "dynamic_returns": dyn,
            "nested_return_values_not_exit_codes": nested_codes,
            "output_call_count": sum(1 for o in output_calls
                                     if o.get("subcommand") == sub),
        }

    kind_counts, stream_counts = {}, {}
    for o in output_calls:
        key = o["kind"] if o["kind"] != "log_func" else "log_func(%s)" % o["stream"]
        kind_counts[key] = kind_counts.get(key, 0) + 1
        stream_counts[o["stream"]] = stream_counts.get(o["stream"], 0) + 1

    result = {
        "baseline": BASELINE_COMMIT,
        "target": TARGET,
        "line_count": len(lines),
        "summary": {
            "output_calls_total": len(output_calls),
            "output_calls_by_kind": kind_counts,
            "output_calls_by_stream": stream_counts,
            "subcommands": sorted(by_sub),
            "exit_code_return_entries": len(exit_code_returns),
            "nested_return_entries": len(nested_returns),
            "helper_return_entries": len(helper_returns),
            "sys_exit_calls": len(sys_exit_calls),
        },
        "subcommands": by_sub,
        "dispatch": {
            "entry": "main() -> sys.exit(main())（if __name__ == '__main__'）",
            "site_gate": "站点未配置时除 cancel 外一律 print [X] 并 return 2",
            "interrupt": "KeyboardInterrupt -> print [i] 已手动中断 -> return 130",
            "note": "main 的 return 经 sys.exit 成为进程退出码；"
                    "顶层分发 args.func(args) 是动态返回，不归入常量退出码",
        },
        "output_calls": sorted(output_calls, key=lambda o: o["line"]),
        "exit_code_returns": sorted(exit_code_returns, key=lambda r: r["line"]),
        "nested_returns": sorted(nested_returns, key=lambda r: r["line"]),
        "helper_returns": sorted(helper_returns, key=lambda r: r["line"]),
        "sys_exit_calls": sorted(sys_exit_calls, key=lambda r: r["line"]),
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
