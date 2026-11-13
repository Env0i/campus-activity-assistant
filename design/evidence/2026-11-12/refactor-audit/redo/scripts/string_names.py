#!/usr/bin/env python3
"""列出基线（7e2d31c）里经字符串访问的名字，并与实际定义逐个比对（T5 第 4 项）。只读，不联网。

    py -3.12 -X utf8 design/evidence/2026-11-12/refactor-audit/redo/scripts/string_names.py

口径：
1. 桌面桥接方法名：桌面前端 `api("名字"` 的字面量（local/ui 下不含 m/），与 class Api 的方法（含下划线开头）比对；
   同时列出「公开方法里桌面前端静态看不到引用」的方法（它们可能被手机动作白名单、后端自己或窗口回调使用）。
   `api(name, …)` 的第一个实参不是字面量的调用点单列（本仓库只有 bridge.js 里的定义那一处）。
2. 后端往前端推的事件名：app.py 里 `_emit("名字"` 的字面量，与 ui/app.js 里 `window.onBackend = {…}` 的键比对；
   `_emit(kind, …)` 这种 kind 是变量的调用点单列，由人工去确认变量取值。
3. 手机动作：domain/phone_rules.py 的 ACTION_PARAMS 键，与 Api 方法比对；phone_service.dispatch 里按名字特判的动作单列。
4. `window[…]` 形式的全局访问：local/ui 下全文搜索 `window[`。
"""
import ast
import re
import subprocess
from pathlib import Path

BASE = "7e2d31c"
here = Path(__file__).resolve().parent
root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True, check=True).stdout.strip()


def sh(*a):
    return subprocess.run(["git"] + list(a), cwd=root, capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


files = [f for f in sh("ls-tree", "-r", "--name-only", BASE, "local/ui").split("\n") if f.endswith(".js")]
desktop = [f for f in files if not f.startswith("local/ui/m/")]
tree = ast.parse(sh("show", BASE + ":local/app.py"))
api = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Api")
allm = {f.name for f in api.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
pub = {n for n in allm if not n.startswith("_")}

names, dynamic = {}, []
for f in desktop:
    t = sh("show", BASE + ":" + f)
    for m in re.finditer(r'(?<![\w$.])api\(\s*"([A-Za-z_]+)"', t):
        names.setdefault(m.group(1), set()).add(f)
    for m in re.finditer(r"(?<![\w$.])api\(\s*([A-Za-z_$][\w$]*)", t):
        dynamic.append("%s:%d" % (f, t[:m.start()].count("\n") + 1))
print("1) 桌面前端 api(\"…\") 静态名 %d 个；其中不是 Api 方法的 %d 个：%s" % (len(names), len([n for n in names if n not in allm]), sorted(n for n in names if n not in allm) or "无"))
print("   经 api(变量, …) 调用的点：%s" % (dynamic or "无"))
print("   公开方法 %d 个，桌面静态看不到引用的 %d 个：%s" % (len(pub), len(pub - set(names)), sorted(pub - set(names))))

app_src = sh("show", BASE + ":local/app.py")
kinds = set(re.findall(r'_emit\(\s*"([a-z_]+)"', app_src))
dyn_emit = [("local/app.py:%d" % (app_src[:m.start()].count("\n") + 1), m.group(1)) for m in re.finditer(r"_emit\(\s*([a-z_]+)\s*,", app_src)]
js = sh("show", BASE + ":local/ui/app.js")
i = js.index("window.onBackend = {")
keys = set(re.findall(r"^\s{2}([a-z_]+):\s", js[i:i + 6000], re.M))
print("2) 后端 _emit 字面量事件名 %d 个：%s" % (len(kinds), sorted(kinds)))
print("   前端 onBackend 键 %d 个：%s" % (len(keys), sorted(keys)))
print("   后端有、前端没有：%s；前端有、后端字面量里没有：%s" % (sorted(kinds - keys) or "无", sorted(keys - kinds) or "无"))
print("   _emit(变量, …) 的调用点（变量取值要人工确认）：%s" % (dyn_emit or "无"))

rules = sh("show", BASE + ":local/domain/phone_rules.py")
blk = rules[rules.index("ACTION_PARAMS = {"):]
blk = blk[:blk.index("\n}\n")]
actions = re.findall(r'^\s{4}"([a-z_]+)":', blk, re.M)
svc = sh("show", BASE + ":local/application/phone_service.py")
special = re.findall(r'if name == "([a-z_]+)":', svc)
print("3) 手机动作白名单 %d 个：%s" % (len(actions), actions))
print("   其中在 Api 里没有同名方法的：%s；dispatch 里按名字特判的：%s" % ([a for a in actions if a not in allm] or "无", special))

hits = []
for f in files:
    t = sh("show", BASE + ":" + f)
    for m in re.finditer(r"window\[", t):
        hits.append("%s:%d" % (f, t[:m.start()].count("\n") + 1))
print("4) window[…] 形式访问：%s" % (hits or "无"))
