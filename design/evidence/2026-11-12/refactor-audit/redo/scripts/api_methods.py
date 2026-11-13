#!/usr/bin/env python3
"""用 ast 列出基线（7e2d31c）local/app.py 里 class Api 的方法，以及每个方法写到的 self 实例字段、用到的锁。

从仓库任意位置运行，只读，不联网，不执行 app.py：
    py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/api_methods.py            # 汇总
    py -3.12 -X utf8 .../api_methods.py --public                                                      # 公开方法清单（名字不以下划线开头）
    py -3.12 -X utf8 .../api_methods.py --json                                                        # 机器可读
    py -3.12 -X utf8 .../api_methods.py --tests                                                       # 测试里打补丁的 app 模块名字、被改写的 Api 成员

口径：
1. 公开方法 = class Api 体内直接定义的、名字不以下划线开头的方法（含 async）。pywebview 会把这些都暴露给前端。
   类体里的嵌套类、常量不算方法。
2. 写入字段 = 方法体内（含嵌套函数）`self.X = …`、`self.X += …`、带注解赋值、`self.X[k] = …`、
   `self.X.append/add/update/pop/clear/setdefault/discard/remove/extend/insert(...)`（后一类记为「容器内改」）。
3. 锁 = 方法体里 `with self.<名字>:` 的 <名字>，名字里含 lock 或叫 _lock 的；另记 `with self._a, self._b:` 的多个。
4. --tests：在 local/tests 下用 ast 找 `patch.object(app, "X", …)`、`patch("app.X", …)`、`patch("local.app.X", …)`、
   `setattr(app, "X", …)`、`app.X = …` 里被打补丁的模块级名字，以及对 Api 实例（变量名叫 api 或以 api 结尾）`api._X = …` 的改写成员。
"""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

BASE = "7e2d31c"


def git_show(rel, root):
    return subprocess.run(["git", "show", "%s:%s" % (BASE, rel)], cwd=root, capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


def repo_root():
    here = Path(__file__).resolve().parent
    return subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True, check=True).stdout.strip()


MUTATORS = {"append", "add", "update", "pop", "clear", "setdefault", "discard", "remove", "extend", "insert", "popitem"}


def self_attr(node):
    """node 是 self.X 时返回 X。"""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return node.attr
    return None


def analyse(root):
    src = git_show("local/app.py", root)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
    methods = []
    for fn in cls.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        writes, mutates, locks, reads = set(), set(), [], set()
        for node in ast.walk(fn):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for t in targets:
                for sub in ast.walk(t):
                    a = self_attr(sub)
                    if a and isinstance(sub, ast.Attribute) and sub is t:
                        writes.add(a)
                if isinstance(t, ast.Subscript):
                    a = self_attr(t.value)
                    if a:
                        mutates.add(a)
                if isinstance(t, (ast.Tuple, ast.List)):
                    for e in t.elts:
                        a = self_attr(e)
                        if a:
                            writes.add(a)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in MUTATORS:
                a = self_attr(node.func.value)
                if a:
                    mutates.add(a)
            if isinstance(node, ast.With):
                for item in node.items:
                    a = self_attr(item.context_expr)
                    if a and ("lock" in a.lower()):
                        locks.append(a)
            a = self_attr(node)
            if a and isinstance(getattr(node, "ctx", None), ast.Load):
                reads.add(a)
        methods.append(dict(name=fn.name, line=fn.lineno, end=fn.end_lineno, public=not fn.name.startswith("_"),
                            writes=sorted(writes), mutates=sorted(mutates - writes), locks=sorted(set(locks)), reads=sorted(reads)))
    return dict(cls_line=cls.lineno, cls_end=cls.end_lineno, methods=methods)


def is_api_var(name):
    """变量名叫 api，或以 api 结尾（self.api 的末段另算不到，口径写在文件头）。"""
    return name == "api" or name.endswith("api") or name.endswith("_api")


def test_patches(root):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", BASE, "local/tests", "tools"], cwd=root, capture_output=True, text=True, check=True).stdout.split()
    files = [f for f in out if f.endswith(".py")]
    mod_patch, api_set = {}, {}
    app_names = {"app"}
    for f in files:
        try:
            tree = ast.parse(git_show(f, root))
        except SyntaxError:
            continue
        local_app = set(app_names)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name in ("app", "local.app"):
                        local_app.add(a.asname or a.name.split(".")[-1])
            if isinstance(node, ast.ImportFrom) and node.module in ("local", ".") :
                for a in node.names:
                    if a.name == "app":
                        local_app.add(a.asname or "app")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name.endswith("patch.object") or name == "patch.object":
                    if len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and node.args[0].id in local_app and isinstance(node.args[1], ast.Constant):
                        mod_patch.setdefault(str(node.args[1].value), set()).add(f)
                    elif len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and is_api_var(node.args[0].id) and isinstance(node.args[1], ast.Constant):
                        api_set.setdefault(str(node.args[1].value), set()).add(f)
                elif name.endswith("patch") and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    m = re.match(r"^(?:local\.)?app\.([A-Za-z_]\w*)$", node.args[0].value)
                    if m:
                        mod_patch.setdefault(m.group(1), set()).add(f)
                elif name == "setattr" and len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and node.args[0].id in local_app and isinstance(node.args[1], ast.Constant):
                    mod_patch.setdefault(str(node.args[1].value), set()).add(f)
                elif name == "setattr" and len(node.args) >= 2 and isinstance(node.args[0], ast.Name) and is_api_var(node.args[0].id) and isinstance(node.args[1], ast.Constant):
                    api_set.setdefault(str(node.args[1].value), set()).add(f)
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name):
                        if t.value.id in local_app:
                            mod_patch.setdefault(t.attr, set()).add(f)
                        elif is_api_var(t.value.id):
                            api_set.setdefault(t.attr, set()).add(f)
    return {k: sorted(v) for k, v in mod_patch.items()}, {k: sorted(v) for k, v in api_set.items()}


def main():
    root = repo_root()
    info = analyse(root)
    ms = info["methods"]
    if "--tests" in sys.argv:
        mp, ap = test_patches(root)
        if "--json" in sys.argv:
            print(json.dumps(dict(module_patches=mp, api_member_writes=ap), ensure_ascii=False, indent=1))
            return
        print("测试里打补丁的 app 模块级名字 %d 个；被改写的 Api 成员 %d 个" % (len(mp), len(ap)))
        for k in sorted(mp):
            print("模块名\t%s\t%d 个文件" % (k, len(mp[k])))
        for k in sorted(ap):
            print("Api成员\t%s\t%d 个文件" % (k, len(ap[k])))
        return
    if "--json" in sys.argv:
        print(json.dumps(info, ensure_ascii=False, indent=1))
        return
    pub = [m for m in ms if m["public"]]
    print("基线 %s  local/app.py  class Api 第 %d-%d 行，方法共 %d 个，其中公开 %d 个、下划线开头 %d 个" % (
        BASE, info["cls_line"], info["cls_end"], len(ms), len(pub), len(ms) - len(pub)))
    fields = sorted({w for m in ms for w in m["writes"]})
    print("被赋值的 self 字段 %d 个（含 __init__）" % len(fields))
    if "--public" in sys.argv:
        for m in pub:
            print("%s\t%d-%d\t写:%s\t容器改:%s\t锁:%s" % (m["name"], m["line"], m["end"], ",".join(m["writes"]) or "-", ",".join(m["mutates"]) or "-", ",".join(m["locks"]) or "-"))


if __name__ == "__main__":
    main()
