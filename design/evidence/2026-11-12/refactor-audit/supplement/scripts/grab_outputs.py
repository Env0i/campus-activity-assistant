"""清点 grab.py 的输出协议、退出码、环境变量读取和文件写入。

用法（从仓库根运行）：
    py -3.12 design/evidence/2026-11-12/refactor-audit/supplement/scripts/grab_outputs.py local/grab.py

只依赖 ast + pathlib，不 import local/ 下任何模块。
"""
from __future__ import annotations

import ast
import io
import re
import sys
from pathlib import Path


class GrabCallVisitor(ast.NodeVisitor):
    """收集 grab.py 里所有有副作用的调用。"""

    def __init__(self, source_lines: list[str]):
        self.lines = source_lines
        self.prints: list[dict] = []
        self.exits: list[dict] = []
        self.env_reads: list[dict] = []
        self.file_writes: list[dict] = []
        self._scope_stack: list[str] = []
        self.aliases: dict[str, str] = {
            "sys": "sys", "os": "os", "logging": "logging",
            "stderr": "sys.stderr", "stdout": "sys.stdout",
        }

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._scope_stack.append(node.name)
        for child in ast.iter_child_nodes(node):
            self.visit(child)
        self._scope_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def _current_func(self, lineno: int) -> str:
        return self._scope_stack[-1] if self._scope_stack else "<module>"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.name
            asname = alias.asname or name
            self.aliases[asname] = name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            full = f"{module}.{alias.name}" if module else alias.name
            asname = alias.asname or alias.name
            self.aliases[asname] = full
        self.generic_visit(node)

    @staticmethod
    def _eval_str(node: ast.AST | None) -> str | None:
        if node is None:
            return None
        try:
            val = ast.literal_eval(node)
            if isinstance(val, str):
                return val
            if isinstance(val, (bytes, bytearray)):
                return val.decode("utf-8", errors="replace")
        except Exception:
            pass
        return None

    def _targets(self, node: ast.Call) -> list[str]:
        f = node.func
        if isinstance(f, ast.Name):
            return [f.id]
        if isinstance(f, ast.Attribute):
            chain = []
            cur = f
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                chain.append(cur.id)
                chain.reverse()
                return [".".join(chain)]
            chain.reverse()
            return ["(?)." + ".".join(chain)]
        return ["(?)"]

    def visit_Call(self, node: ast.Call):
        targets = self._targets(node)
        full = targets[0]
        lineno = node.lineno
        func = self._current_func(lineno)

        if full == "print":
            self.prints.append({
                "lineno": lineno, "function": func,
                "target": "print-stdout",
                "literal": self._eval_str(node.args[0]) if node.args else None,
                "raw_line": self.lines[lineno - 1].rstrip(),
            })
        elif full in ("sys.exit", "os._exit", "sys.exit") or re.fullmatch(r"sys\.exit\b", full):
            code = self._eval_str(node.args[0]) if node.args else None
            code_expr = ast.unparse(node.args[0]) if node.args else "0"
            self.exits.append({
                "lineno": lineno, "function": func, "full_target": full,
                "code_literal": code, "code_expr": code_expr,
                "raw_line": self.lines[lineno - 1].rstrip(),
            })
        elif full in ("sys.stdout.write", "sys.stderr.write",
                      "sys.stdout.flush", "sys.stderr.flush",
                      "sys.stdout.writelines", "sys.stderr.writelines"):
            target = "stdout" if "stdout" in full else "stderr"
            literal = self._eval_str(node.args[0]) if node.args else None
            self.prints.append({
                "lineno": lineno, "function": func, "target": target + "-write",
                "literal": literal,
                "raw_line": self.lines[lineno - 1].rstrip(),
            })
        elif re.match(r"(logging|logger)\.", full):
            literal = self._eval_str(node.args[0]) if node.args else None
            self.prints.append({
                "lineno": lineno, "function": func, "target": full,
                "literal": literal,
                "raw_line": self.lines[lineno - 1].rstrip(),
            })
        elif full in ("os.getenv", "os.environ.get"):
            key = self._eval_str(node.args[0]) if node.args else None
            self.env_reads.append({
                "lineno": lineno, "function": func,
                "key_literal": key,
                "key_expr": ast.unparse(node.args[0]) if node.args else "?",
                "full_target": full,
                "raw_line": self.lines[lineno - 1].rstrip(),
            })
        elif full == "open":
            path_lit = self._eval_str(node.args[0]) if node.args else None
            mode = self._eval_str(node.args[1]) if len(node.args) > 1 else "r"
            for kw in node.keywords:
                if kw.arg == "mode":
                    mode = self._eval_str(kw.value) or ast.unparse(kw.value)
            path_expr = ast.unparse(node.args[0]) if node.args else "?"
            if isinstance(mode, str) and set(mode) & {"w", "a", "x", "+"} and "r" not in mode:
                self.file_writes.append({
                    "lineno": lineno, "function": func,
                    "path_literal": path_lit, "path_expr": path_expr,
                    "mode": mode,
                    "raw_line": self.lines[lineno - 1].rstrip(),
                })

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
            val_target = self._targets(node.value)
            if val_target and val_target[0].startswith("os.environ"):
                key = self._eval_str(node.slice)
                self.env_reads.append({
                    "lineno": node.lineno,
                    "function": self._current_func(node.lineno),
                    "key_literal": key,
                    "key_expr": ast.unparse(node.slice),
                    "full_target": "os.environ[...]",
                    "raw_line": self.lines[node.lineno - 1].rstrip(),
                })
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                if isinstance(comparator, ast.Attribute) and comparator.attr == "environ":
                    if self._targets(comparator)[0].startswith("os.environ"):
                        key = self._eval_str(node.left)
                        self.env_reads.append({
                            "lineno": node.lineno,
                            "function": self._current_func(node.lineno),
                            "key_literal": key,
                            "key_expr": ast.unparse(node.left),
                            "full_target": "KEY in os.environ",
                            "raw_line": self.lines[node.lineno - 1].rstrip(),
                        })
        self.generic_visit(node)


def main():
    if len(sys.argv) < 2:
        print("用法: grab_outputs.py <grab.py 路径>", file=sys.stderr)
        sys.exit(2)

    src_path = Path(sys.argv[1])
    if not src_path.is_file():
        print(f"文件不存在: {src_path}", file=sys.stderr)
        sys.exit(2)

    source = src_path.read_text(encoding="utf-8-sig")
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(src_path))

    visitor = GrabCallVisitor(lines)
    visitor.visit(tree)

    out = io.StringIO()
    def hdr(title):
        out.write("\n" + "=" * 78 + "\n")
        out.write(f"  {title}\n")
        out.write("=" * 78 + "\n")

    hdr(f"清点 grab.py  —— 共 {len(lines)} 行")
    out.write(f"源文件: {src_path}\n")

    hdr("1) print / sys.stdout.write / sys.stderr.write / logging 调用")
    for item in visitor.prints:
        lit_preview = item["literal"]
        if lit_preview is not None and len(lit_preview) > 160:
            lit_preview = lit_preview[:157] + "..."
        out.write(f"L{item['lineno']:>5}  [{item['function']:<40}]  {item['target']}\n")
        out.write(f"       literal: {lit_preview!r}\n")
        out.write(f"       code   : {item['raw_line'].strip()}\n")
        out.write("\n")

    hdr("2) sys.exit / os._exit 调用")
    for item in visitor.exits:
        out.write(f"L{item['lineno']:>5}  [{item['function']:<40}]  {item['full_target']}\n")
        out.write(f"       code_literal: {item['code_literal']}\n")
        out.write(f"       code_expr   : {item['code_expr']}\n")
        out.write(f"       code        : {item['raw_line'].strip()}\n")
        out.write("\n")

    hdr("3) os.environ 读取")
    seen_keys = set()
    for item in visitor.env_reads:
        key = item["key_literal"] or item["key_expr"]
        mark = "" if key not in seen_keys else "  (重复)"
        seen_keys.add(key)
        out.write(f"L{item['lineno']:>5}  [{item['function']:<40}]  {item['full_target']}  key={key!r}{mark}\n")
        if item["key_literal"] is None:
            out.write(f"       key 表达式: {item['key_expr']}\n")
        out.write(f"       code     : {item['raw_line'].strip()}\n")
        out.write("\n")
    out.write(f"---- 唯 env key 统计: {len(seen_keys)} 个 ----\n")

    hdr("4) open() 写入 (mode 含 w/a/x)")
    for item in visitor.file_writes:
        out.write(f"L{item['lineno']:>5}  [{item['function']:<40}]  mode={item['mode']}\n")
        out.write(f"       path_literal: {item['path_literal']!r}\n")
        out.write(f"       path_expr   : {item['path_expr']}\n")
        out.write(f"       code        : {item['raw_line'].strip()}\n")
        out.write("\n")

    hdr("5) 概览统计")
    out.write(f"  print/stdout/stderr/logging 调用 : {len(visitor.prints)}\n")
    out.write(f"  sys.exit / os._exit 调用         : {len(visitor.exits)}\n")
    out.write(f"  os.environ 读取                  : {len(visitor.env_reads)}  唯键 {len(seen_keys)}\n")
    out.write(f"  open() 写入                      : {len(visitor.file_writes)}\n")

    sys.stdout.write(out.getvalue())


if __name__ == "__main__":
    main()
