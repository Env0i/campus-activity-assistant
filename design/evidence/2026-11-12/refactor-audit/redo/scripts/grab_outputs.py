#!/usr/bin/env python3
"""用 ast 列出基线（7e2d31c）local/grab.py 里所有会写到 stdout/stderr 的调用和各函数的返回、退出码。

从仓库任意位置运行，只读，不联网，不执行 grab.py：
    py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/grab_outputs.py            # 汇总
    py -3.12 -X utf8 .../grab_outputs.py --detail                                                      # 逐条明细
    py -3.12 -X utf8 .../grab_outputs.py --json                                                        # 机器可读

口径（每一步在数什么）：
1. 输出调用 = `print(...)`、`sys.stdout.write(...)`、`sys.stderr.write(...)`、以及本文件里自己封装的输出函数
   （脚本先找出「函数体里直接 print 或 write 到标准流」的函数，再把对这些函数的调用也记为输出调用，一层封装）。
   `log(...)` 先写日志文件，再 print 到 stdout，所以 `log` 调用都算 stdout 行，行首带时间戳。
   `log_event(...)` 内部调用 log()，所以事件行也带时间戳打到 stdout；脚本把它的调用点单列，不重复计入 log 的 62 处（审计 AA2-02）。
2. 前缀 = 第一个实参里能静态取到的开头常量文本（f 字符串取开头常量，`"..." % x` 与 `"..." + x` 取左边常量）；
   取不到写「<动态>」。
3. 所在函数 = 最内层函数；嵌套函数用「外层>内层」。归属子命令：先看顶层函数名是不是 cmd_<子命令>；
   不是的，按静态调用图（函数体里出现的同文件函数名）从各 cmd_* 往下找，能到达的子命令都记（标「静态可达」，
   是近似，动态分派和回调到不了）。
4. 退出码：只看函数自己的 `return`（不含嵌套函数里的 return）和 `sys.exit` / `raise SystemExit`。
   cmd_* 的返回值经 main() 的 `return args.func(args)` 和文件末尾的 `sys.exit(main())` 变成进程退出码。
5. 环境变量与写文件：只列 grab.py 本文件里直接出现的 os.environ / os.getenv，以及 open(..., "w"/"a"/"wb"...)、
   write_text、write_bytes、os.replace、shutil.move 等；它们调用的别的模块里的读写不在本脚本范围。
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

BASE = "7e2d31c"
FILE = "local/grab.py"


def load():
    here = Path(__file__).resolve().parent
    root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True, check=True).stdout.strip()
    raw = subprocess.run(["git", "show", "%s:%s" % (BASE, FILE)], cwd=root, capture_output=True, check=True).stdout
    return raw.decode("utf-8").replace("\r\n", "\n")


def const_prefix(node):
    """第一个实参里静态可知的开头文本。"""
    if node is None:
        return "<无参数>"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = ""
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                out += part.value
            else:
                break
        return out + ("" if out and len(out) == len("".join(p.value for p in node.values if isinstance(p, ast.Constant))) and all(isinstance(p, ast.Constant) for p in node.values) else "<…>")
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
        left = const_prefix(node.left)
        return left + ("<…>" if not left.endswith("<…>") else "")
    return "<动态>"


def dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


class Walker(ast.NodeVisitor):
    def __init__(self):
        self.stack = []
        self.calls = []        # (line, func_chain, kind, callee, args_node)
        self.returns = []      # (line, func_chain, repr)
        self.exits = []        # (line, func_chain, repr)
        self.defs = {}         # name -> (line, end_line, chain)
        self.names_called = {}  # chain(top-level name) -> set of called simple names
        self.envs = []
        self.writes = []

    def chain(self):
        return ">".join(self.stack) if self.stack else "<模块级>"

    def visit_FunctionDef(self, node):
        self.stack.append(node.name)
        self.defs[">".join(self.stack)] = (node.lineno, node.end_lineno)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, node):
        val = ast.unparse(node.value) if node.value is not None else "None"
        self.returns.append((node.lineno, self.chain(), val))
        self.generic_visit(node)

    def visit_Raise(self, node):
        text = ast.unparse(node.exc) if node.exc is not None else ""
        if text.startswith("SystemExit"):
            self.exits.append((node.lineno, self.chain(), "raise " + text))
        self.generic_visit(node)

    def visit_Call(self, node):
        name = dotted(node.func)
        top = self.stack[0] if self.stack else "<模块级>"
        simple = node.func.id if isinstance(node.func, ast.Name) else None
        if simple:
            self.names_called.setdefault(top, set()).add(simple)
        first = node.args[0] if node.args else None
        if name == "print":
            to_err = any(k.arg == "file" and "stdout" not in ast.unparse(k.value) for k in node.keywords)   # file=stream（stream 取自 sys.stderr）一类也算 stderr
            self.calls.append((node.lineno, self.chain(), "print→stderr" if to_err else "print→stdout", name, first))
        elif name in ("sys.stdout.write", "sys.stderr.write"):
            self.calls.append((node.lineno, self.chain(), name.replace("sys.", "") , name, first))
        elif name in ("sys.exit", "exit"):
            self.exits.append((node.lineno, self.chain(), "sys.exit(%s)" % (ast.unparse(first) if first is not None else "")))
        elif name in ("os.environ.get", "os.getenv", "os.environ.setdefault", "os.environ.pop"):
            self.envs.append((node.lineno, self.chain(), "%s(%s)" % (name, ", ".join(ast.unparse(a) for a in node.args))))
        elif name == "open":
            mode = ""
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for k in node.keywords:
                if k.arg == "mode" and isinstance(k.value, ast.Constant):
                    mode = str(k.value.value)
            if any(c in mode for c in "wax+"):
                self.writes.append((node.lineno, self.chain(), "open(%s, %r)" % (ast.unparse(node.args[0]) if node.args else "?", mode)))
        elif name.split(".")[-1] in ("write_text", "write_bytes", "replace", "rename", "move", "unlink", "remove") and name not in ("str.replace",):
            if name.split(".")[-1] in ("replace",) and not name.startswith(("os.", "Path")) and "path" not in name.lower():
                pass
            else:
                self.writes.append((node.lineno, self.chain(), "%s(%s)" % (name, ", ".join(ast.unparse(a)[:40] for a in node.args))))
        elif name == "log_event":
            self.calls.append((node.lineno, self.chain(), "log_event(经 log 写 stdout)", name, first))
        else:
            self.calls.append((node.lineno, self.chain(), "?", name, first))
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if dotted(node.value) == "os.environ":
            self.envs.append((node.lineno, self.chain(), "os.environ[%s]" % ast.unparse(node.slice)))
        self.generic_visit(node)


def main():
    src = load()
    tree = ast.parse(src)
    w = Walker()
    w.visit(tree)
    lines = src.split("\n")
    # 找出直接写标准流的函数（一层封装）
    direct_funcs = {}
    for line, chain, kind, callee, first in w.calls:
        if kind in ("print→stdout", "print→stderr", "stdout.write", "stderr.write"):
            direct_funcs.setdefault(chain.split(">")[-1], set()).add(kind)
    out_calls = []
    for line, chain, kind, callee, first in w.calls:
        if kind in ("print→stdout", "print→stderr", "stdout.write", "stderr.write"):
            out_calls.append(dict(line=line, func=chain, kind=kind, callee=callee, prefix=const_prefix(first), via=""))
        elif kind == "log_event(经 log 写 stdout)":
            out_calls.append(dict(line=line, func=chain, kind=kind, callee=callee, prefix=const_prefix(node_arg(first, w, line)) if False else const_prefix(first), via=""))
        elif callee in direct_funcs and callee not in ("print",) and not callee.startswith("cmd_") and callee != "main":
            k = "log→stdout(带时间戳)" if callee == "log" else ("封装(%s)→" % callee + "/".join(sorted(direct_funcs[callee])))
            out_calls.append(dict(line=line, func=chain, kind=k, callee=callee, prefix=const_prefix(first), via=callee))
    # 子命令归属（静态可达）
    cmds = {n[4:]: n for n in w.names_called if n.startswith("cmd_")}
    for n in list(w.defs):
        pass
    top_defs = [d for d in w.defs if ">" not in d]
    reach = {}
    for sub, top in cmds.items():
        seen, todo = set([top]), [top]
        while todo:
            cur = todo.pop()
            for callee in w.names_called.get(cur, ()):
                if callee in top_defs and callee not in seen:
                    seen.add(callee)
                    todo.append(callee)
        reach[sub] = seen
    def owners(chain):
        top = chain.split(">")[0]
        res = [s for s, seen in reach.items() if top in seen]
        if top.startswith("cmd_"):
            return [top[4:]], "直属"
        if top == "main":
            return ["(main)"], "直属"
        return res or ["(无静态可达)"], "静态可达"
    for c in out_calls:
        c["subcmds"], c["attr"] = owners(c["func"])
    # cmd_* 自己的返回
    cmd_returns = {}
    for line, chain, val in w.returns:
        parts = chain.split(">")
        if len(parts) == 1 and (parts[0].startswith("cmd_") or parts[0] == "main"):
            cmd_returns.setdefault(parts[0], []).append((line, val))
    nested_returns = sum(1 for l, c, v in w.returns if c.count(">") >= 1 and c.split(">")[0].startswith("cmd_"))
    res = dict(base=BASE, file=FILE, lines=len(lines), out_calls=out_calls, cmd_returns=cmd_returns, exits=[dict(line=l, func=c, what=v) for l, c, v in w.exits],
               envs=[dict(line=l, func=c, what=v) for l, c, v in w.envs], writes=[dict(line=l, func=c, what=v) for l, c, v in w.writes],
               direct_funcs={k: sorted(v) for k, v in direct_funcs.items()}, nested_returns_in_cmd=nested_returns,
               reach={k: sorted(v) for k, v in reach.items()})
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    stdout_like = [c for c in out_calls if "stdout" in c["kind"] or c["kind"].startswith("log→") or "封装" in c["kind"]]
    print("基线 %s  %s  共 %d 行" % (BASE, FILE, len(lines)))
    print("直接写标准流的函数：" + "、".join("%s(%s)" % (k, "/".join(v)) for k, v in sorted(direct_funcs.items())))
    kinds = {}
    for c in out_calls:
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
    print("输出调用共 %d 处：" % len(out_calls) + "，".join("%s %d" % kv for kv in sorted(kinds.items())))
    by_cmd = {}
    for c in out_calls:
        for s in c["subcmds"]:
            by_cmd[s] = by_cmd.get(s, 0) + 1
    print("按子命令归属（一处可属多个子命令）：" + "，".join("%s %d" % kv for kv in sorted(by_cmd.items())))
    print("cmd_* 与 main 自己的 return（不含嵌套函数）：")
    for k, v in sorted(cmd_returns.items()):
        print("  %s: %s" % (k, "；".join("%d行→%s" % (l, val[:50]) for l, val in v)))
    print("cmd_* 内嵌套函数里的 return 数（不算子命令退出码）：%d" % nested_returns)
    print("sys.exit / SystemExit：" + "；".join("%d行 %s %s" % (e["line"], e["func"], e["what"]) for e in res["exits"]))
    print("环境变量访问 %d 处；写文件类调用 %d 处" % (len(res["envs"]), len(res["writes"])))
    if "--detail" in sys.argv:
        print("\n## 输出调用明细（行 / 所在函数 / 类别 / 前缀 / 归属）")
        for c in sorted(out_calls, key=lambda x: x["line"]):
            print("%d\t%s\t%s\t%r\t%s(%s)" % (c["line"], c["func"], c["kind"], c["prefix"][:60], "/".join(c["subcmds"]), c["attr"]))
        print("\n## 环境变量")
        for e in res["envs"]:
            print("%d\t%s\t%s" % (e["line"], e["func"], e["what"]))
        print("\n## 写文件类")
        for e in res["writes"]:
            print("%d\t%s\t%s" % (e["line"], e["func"], e["what"]))
        print("\n## 各子命令静态可达的顶层函数数")
        for k, v in sorted(res["reach"].items()):
            print("%s\t%d" % (k, len(v)))


def node_arg(first, w, line):
    return first


if __name__ == "__main__":
    main()
