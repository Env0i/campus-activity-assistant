"""用 ast 清点 local/app.py 与 local/application 下的锁；只读源码，不 import 产品代码。

用法（仓库根）：lock_graph.py --head <短哈希> [--out-dir <证据目录>]；给 --out-dir 时写 locks.md。

口径：持有只认静态嵌套（`with <锁>:` 的范围，以及同一函数里 `lock = self._lock` 之后 `with lock:`）。
间接只追一层：A 持 L 调同类方法 B，B 直接拿 M，记 L→M（标「间接」）；持 L 调服务方法 S 时同理，
另标「间接·服务」。`with A, B:` 认作先 A 后 B；同一把锁在同一路径出现两次记「重入」。
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

SCOPE_FILES, SCOPE_DIRS = ("local/app.py",), ("local/application",)
LOCK_KINDS = {"Lock": "Lock（不可重入）", "RLock": "RLock（可重入）", "Condition": "Condition"}
FEATURE_ORDER = ("更新", "组件", "手机访问", "登录恢复", "计划",
                 "活动列表", "窗口与托盘", "时钟", "worker 进程", "其他")

# 服务类的方法按类归功能：方法名本身（state、begin、submit）看不出功能
CLASS_FEATURES = {"UpdateService": "更新", "AdvancedComponentService": "组件",
                  "PhoneAccessService": "手机访问", "LoginRelayService": "登录恢复",
                  "AutoReloginMonitor": "登录恢复"}
# 模块级函数按模块归（run_check 这类挂 state 参数的函数名看不出功能）
MODULE_FEATURES = {"update_service": "更新", "phone_service": "手机访问",
                   "advanced_component_service": "组件", "login_relay_service": "登录恢复",
                   "auto_relogin": "登录恢复", "plan_service": "计划"}

# 名字规则判不准的逐个列明依据（判断列，不是数出来的）
FEATURE_OVERRIDES = {
    "shutdown": ("窗口与托盘", "关窗收尾：置关闭屏障并收走全部 worker"),
    "stop": ("窗口与托盘", "停机入口，与 shutdown 同属关闭路径"),
    "open_latest_release": ("更新", "打开发布页，与更新同一入口"),
    "_install_selected_feature": ("组件", "装用户挑的组件包"),
    "_classify_captcha": ("登录恢复", "重登要过的验证码分类"),
    "_commit_pending_save": ("登录恢复", "把「这次手输」的账号落盘"),
    "_confirm_signed": ("计划", "确认已报名，与取消报名同一批缓存写"),
    "worker_command": ("worker 进程", "拼 worker 命令行"),
    "_run": ("worker 进程", "起一次性 worker 进程"),
    "_spawn": ("worker 进程", "起一次性 worker 进程"),
}

# 名字里带这些片段就归给某功能，按顺序先命中先算
FEATURE_RULES = (
    ("更新", ("update", "version")),
    ("组件", ("component", "advanced", "ocr")),
    ("登录恢复", ("relogin", "relay", "login", "check", "auto_log", "credential", "silent_")),
    ("手机访问", ("phone", "cloudflare", "tunnel")),
    ("计划", ("plan", "cancel", "start_request", "protect_start", "remember_start",
              "start_replay", "prune_finished")),
    ("活动列表", ("list", "pc_")),
    ("窗口与托盘", ("window", "tray", "close", "hide", "show_window", "second_open")),
    ("时钟", ("clock",)),
)


def classify(qual: str, module: str = "") -> tuple[str, str]:
    """限定名（`类.方法` 或模块级函数名）→ (功能, 依据)；依据列打进 locks.md。"""
    cls, name = qual.split(".")[0], qual.split(".")[-1]
    if cls in CLASS_FEATURES:
        return CLASS_FEATURES[cls], "按类：%s" % cls
    if "." not in qual and module in MODULE_FEATURES:
        return MODULE_FEATURES[module], "按模块：%s" % module
    bare = name.lstrip("_")
    for key in (bare, name):
        if key in FEATURE_OVERRIDES:
            return FEATURE_OVERRIDES[key]
    for feature, fragments in FEATURE_RULES:
        for frag in fragments:
            if frag in bare:
                return feature, "名字含「%s」" % frag
    return "其他", "名字不落在任何功能的关键词上"


class ModuleInfo:
    def __init__(self, rel: str, tree: ast.Module):
        self.rel = rel
        self.tree = tree
        self.name = Path(rel).stem
        self.locks: dict[str, str] = {}
        self.lock_lines: dict[str, int] = {}
        self.functions: dict[str, ast.AST] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self.module_locks: set[str] = set()


def _lock_ctor(node) -> str | None:
    f = node.func if isinstance(node, ast.Call) else None
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
    return name if name in LOCK_KINDS else None


def load_modules(root: Path) -> dict[str, ModuleInfo]:
    rels = list(SCOPE_FILES)
    for d in SCOPE_DIRS:
        rels.extend(p.relative_to(root).as_posix() for p in sorted((root / d).glob("*.py")))
    return {rel: ModuleInfo(rel, ast.parse((root / rel).read_text(encoding="utf-8"), filename=rel))
            for rel in rels}


def scan_declarations(mod: ModuleInfo) -> None:
    for node in mod.tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            kind = _lock_ctor(node.value)
            if kind and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                mod.locks[name] = kind
                mod.lock_lines[name] = node.lineno
                mod.module_locks.add(name)
        elif isinstance(node, ast.ClassDef):
            mod.classes[node.name] = node
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
                    kind, tgt = _lock_ctor(sub.value), sub.targets[0]
                    if kind and isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) \
                            and tgt.value.id == "self":
                        key = node.name + "." + tgt.attr
                        mod.locks[key] = kind
                        mod.lock_lines[key] = sub.lineno
                elif isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    mod.functions[node.name + "." + sub.name] = sub
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mod.functions[node.name] = node


class LockCtx:
    """一个函数里的锁上下文：当前类、局部别名、参数锁。"""

    def __init__(self, mod, cls, fname, fn, param_locks):
        self.mod, self.cls, self.fname = mod, cls, fname
        self.param_locks = param_locks
        self.env: dict[str, str] = {}
        a = fn.args
        self.params = {x.arg for x in list(a.args) + list(a.kwonlyargs)}

    def resolve(self, node) -> str | None:
        if isinstance(node, ast.Name):
            if node.id in self.env:
                return self.env[node.id]
            if node.id in self.mod.module_locks:
                return node.id
            pl = self.param_locks.get((self.mod.name, self.fname, node.id))
            return pl[1] if pl and pl[0] == "lock" else None
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            base = node.value.id
            if base == "self":
                key = (self.cls or "") + "." + node.attr
                return key if key in self.mod.locks else None
            if base in self.params:
                pl = self.param_locks.get((self.mod.name, self.fname, base))
                if pl and pl[0] == "class":
                    return pl[1] + "." + node.attr
            if base in self.env:
                return self.env[base]
        return None


class FnWalk(ast.NodeVisitor):
    """走一个函数体：记锁的区间、嵌套边、持锁时的调用，以及认不出的 with。"""

    def __init__(self, ctx: LockCtx):
        self.ctx = ctx
        self.local_locks: list[tuple[str, str, int]] = []
        self.stack: list[str] = []
        self.intervals: list[tuple[str, int, int]] = []
        self.edges: list[tuple[str, str, int]] = []
        self.calls: list[tuple[str, str, int]] = []
        self.unknown_with: list[tuple[int, str]] = []

    def visit_Assign(self, node) -> None:
        tgt = node.targets[0] if len(node.targets) == 1 else None
        if isinstance(tgt, ast.Name):
            key = self.ctx.resolve(node.value)
            if key:
                self.ctx.env[tgt.id] = key
            elif (kind := _lock_ctor(node.value)):  # 函数里现建的锁，如 Condition()
                key = "%s:%s:%s" % (self.ctx.mod.name, self.ctx.fname, tgt.id)
                self.ctx.env[tgt.id] = key
                self.local_locks.append((key, kind, node.lineno))
        self.generic_visit(node)

    def visit_With(self, node) -> None:
        pushed = []
        for item in node.items:
            self.visit(item.context_expr)
            key = self.ctx.resolve(item.context_expr)
            if key:
                self.edges.extend((outer, key, node.lineno) for outer in self.stack)
                self.stack.append(key)
                pushed.append(key)
            elif not isinstance(item.context_expr, ast.Call):
                self.unknown_with.append((node.lineno, ast.unparse(item.context_expr)))
        for stmt in node.body:
            self.visit(stmt)
        for key in reversed(pushed):
            self.stack.remove(key)
            self.intervals.append((key, node.lineno, node.end_lineno or node.lineno))

    def visit_Call(self, node) -> None:
        desc = self._describe(node)
        if desc:
            self.calls.extend((key, desc, node.lineno) for key in self.stack)
        self.generic_visit(node)

    def _describe(self, node) -> str | None:
        f = node.func
        if isinstance(f, ast.Name):
            return f.id + "()"
        if not isinstance(f, ast.Attribute):
            return None
        base = f.value
        if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                and base.value.id == "self":
            return base.attr + "." + f.attr + "()"   # self._svc.method()
        if isinstance(base, ast.Name) and (base.id == "self" or base.id in self.ctx.params):
            return base.id + "." + f.attr + "()"     # self.method() / 参数上的方法
        return None


def collect_services(mods) -> tuple[dict[str, str], dict[str, str]]:
    """Api.__init__ 里的服务字段 → 类名；类名 → 所在模块。"""
    class_rel = {cls: m.rel for m in mods.values() for cls in m.classes}
    attrs, fn = {}, mods["local/app.py"].functions.get("Api.__init__")
    for node in ast.walk(fn) if fn else []:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        tgt, val = node.targets[0], node.value
        if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
                and tgt.value.id == "self" and isinstance(val, ast.Call)):
            continue
        name = val.func.attr if isinstance(val.func, ast.Attribute) else getattr(val.func, "id", "")
        if name in class_rel:
            attrs[tgt.attr] = name
    return attrs, class_rel


def _owner(mod: ModuleInfo, line: int) -> str:
    """行号落在哪个方法/函数体里（取最内层）。"""
    hits = [q for q, fn in mod.functions.items()
            if fn.lineno <= line <= (getattr(fn, "end_lineno", None) or fn.lineno)]
    return max(hits, key=len) if hits else ""


def collect_param_locks(mods, services) -> dict:
    """模块级函数的锁参数：靠调用点反推是哪个对象的锁，迭代到不再变。"""
    param_locks: dict[tuple[str, str, str], tuple[str, str]] = {}
    funcs = {(m.name, n): fn for m in mods.values()
             for n, fn in m.functions.items() if "." not in n}
    class_locks = {m.name: {k for k in m.locks if "." in k} for m in mods.values()}
    alias = {}
    for m in mods.values():
        for node in ast.walk(m.tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for a in node.names:
                    # from application import plan_service as _plan：名字就是模块
                    # from application.plan_service import f：模块是 node.module 的末段
                    alias[(m.name, a.asname or a.name)] = (a.name if a.asname
                                                           else node.module.split(".")[-1])

    def resolve_arg(expr, mod, cls, fname):
        if isinstance(expr, ast.Name):
            return ("class", cls) if expr.id == "self" and cls \
                else param_locks.get((mod, fname, expr.id))
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) \
                and expr.value.id == "self":
            if cls and (cls + "." + expr.attr) in class_locks.get(mod, set()):
                return ("lock", cls + "." + expr.attr)
            if expr.attr in services:
                return ("class", services[expr.attr])
        return None

    for _ in range(4):
        changed = False
        for m in mods.values():
            for node in ast.walk(m.tree):
                if not isinstance(node, ast.Call):
                    continue
                f, target = node.func, None
                if isinstance(f, ast.Name) and (m.name, f.id) in funcs:
                    target = (m.name, f.id)
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    mod_name = alias.get((m.name, f.value.id))
                    if mod_name and (mod_name, f.attr) in funcs:
                        target = (mod_name, f.attr)
                if not target:
                    continue
                a = funcs[target].args
                params = [x.arg for x in a.args + a.kwonlyargs]
                qual = _owner(m, node.lineno)
                cls = qual.split(".")[0] if "." in qual else None
                fname = qual.split(".")[-1] if qual else ""
                for pname, arg in list(zip(params, node.args)) + [
                        (kw.arg, kw.value) for kw in node.keywords if kw.arg in params]:
                    val = resolve_arg(arg, m.name, cls, fname)
                    key = (target[0], target[1], pname)
                    if val and param_locks.get(key) != val:
                        param_locks[key] = val
                        changed = True
        if not changed:
            break
    return param_locks


def walk_all(mods, param_locks):
    out = {}
    for m in mods.values():
        for qual, fn in m.functions.items():
            cls = qual.split(".")[0] if "." in qual else None
            walk = FnWalk(LockCtx(m, cls if cls in m.classes else None,
                                  qual.split(".")[-1], fn, param_locks))
            for stmt in fn.body:
                walk.visit(stmt)
            out[(m.rel, qual)] = walk
    return out


def build(mods, walks, services, class_rel):
    """汇总成：锁 → 声明、持有者、直接边、间接边、持锁调用、认不出的 with。"""
    rep = {"decls": {}, "users": {}, "direct": [], "indirect": [], "unknown": [], "calls": {}}
    for m in mods.values():
        for key, kind in m.locks.items():
            rep["decls"][key] = (kind, m.rel, m.lock_lines[key])
    for (rel, qual), walk in walks.items():
        for key, kind, line in walk.local_locks:
            rep["decls"].setdefault(key, (kind, rel, line))
        for key, line, _end in walk.intervals:
            rep["users"].setdefault(key, {}).setdefault((rel, qual), []).append(line)
        for outer, inner, line in walk.edges:
            rep["direct"].append((outer, inner, rel, qual, line,
                                  "重入" if outer == inner else "直接"))
        for key, desc, _line in walk.calls:
            rep["calls"].setdefault(key, {})
            rep["calls"][key][desc] = rep["calls"][key].get(desc, 0) + 1
        rep["unknown"].extend((rel, qual, line, expr) for line, expr in walk.unknown_with)
    # 一层间接：持锁时调同类方法 / 调服务方法，把被调方法直接拿的锁记到外层名下
    for (rel, qual), walk in walks.items():
        cls = qual.split(".")[0] if "." in qual else None
        for key, desc, line in walk.calls:
            if desc.startswith("self.") and cls:
                callee = (rel, cls + "." + desc[5:-2])
            elif "." in desc:
                svc, method = desc[:-2].split(".", 1)
                callee = (class_rel.get(services.get(svc, ""), ""),
                          (services.get(svc) or "") + "." + method)
            else:
                continue
            for inner, _s, _e in walks[callee].intervals if callee in walks else []:
                rep["indirect"].append((key, inner, rel, qual, line,
                                        desc + ("（重入）" if inner == key else "")))
    return rep


def _table(add, head, rows) -> None:
    add("| " + " | ".join(head) + " |")
    add("|" + "---|" * len(head))
    for row in rows:
        add("| " + " | ".join(row) + " |")


def render(rep, mods, head, cmd) -> list[str]:
    L: list[str] = []
    add = L.append
    decls, users = rep["decls"], rep["users"]
    keys = sorted(decls, key=lambda k: (-len(users.get(k, {})), k))

    def feat(rel, qual):
        return classify(qual, Path(rel).stem)[0]

    add("# 锁图")
    add("")
    add("- 生成脚本：`scripts/lock_graph.py`（ast 只读源码，不 import 产品代码）")
    add("- 命令：`%s --head %s`" % (cmd, head))
    add("- 基线：`%s`；范围：local/app.py 与 local/application 下 %d 个模块；锁 %d 把"
        % (head, len(mods), len(decls)))
    add("- 「获取处」是 `with` 出现的次数而非执行次数；间接只追一层；服务自己线程里拿自己锁的"
        "路径（HTTP 处理线程等）不经过 Api，只按静态源码计。")
    add("- 认不出的 `with`：%d 处%s" % (len(rep["unknown"]), "" if not rep["unknown"] else
                                     "：" + "；".join("%s:%s 的 `%s`" % (r, n, e)
                                                      for r, _q, n, e in rep["unknown"])))
    add("")

    add("## 一览")
    add("")
    rows = []
    for key in keys:
        kind, rel, line = decls[key]
        feats: dict[str, int] = {}
        for _mrel, qual in users.get(key, {}):
            feats[feat(_mrel, qual)] = feats.get(feat(_mrel, qual), 0) + 1
        rows.append(["`%s`" % key, LOCK_KINDS.get(kind, kind), "`%s:%d`" % (rel, line),
                     str(sum(len(v) for v in users.get(key, {}).values())),
                     str(len(users.get(key, {}))),
                     "、".join("%s %d" % (f, feats[f]) for f in FEATURE_ORDER if f in feats) or "—"])
    _table(add, ("锁", "种类", "声明", "获取处", "持有方法数", "功能分布"), rows)
    add("")

    add("## 每把锁")
    add("")
    for key in keys:
        kind, rel, line = decls[key]
        held = users.get(key, {})
        add("### `%s`（%s，`%s:%d`）" % (key, LOCK_KINDS.get(kind, kind), rel, line))
        add("")
        add("持有它的方法 %d 个、`with` %d 处：" % (len(held), sum(len(v) for v in held.values())))
        add("")
        _table(add, ("模块", "方法", "功能", "获取处", "行"),
               [["`%s`" % r, "`%s`" % q, feat(r, q), str(len(ls)),
                 "、".join(str(x) for x in sorted(ls))]
                for (r, q), ls in sorted(held.items(), key=lambda kv: kv[0])])
        add("")
        outs = [e for e in rep["direct"] if e[0] == key]
        ins = [e for e in rep["direct"] if e[1] == key]
        ind = [e for e in rep["indirect"] if e[0] == key]
        if outs:
            add("- 持它时直接拿别的锁 %d 处：%s"
                % (len(outs), "、".join(sorted({"`%s`" % e[1] for e in outs}))))
        if ins:
            add("- 拿别的锁时又被拿 %d 处（这些地方它是内层）：%s"
                % (len(ins), "、".join(sorted({"`%s`" % e[0] for e in ins}))))
        if ind:
            add("- 间接（经同类或服务方法一层）%d 处：%s"
                % (len(ind), "、".join(sorted({"`%s` 经 %s" % (e[1], e[5]) for e in ind}))))
        skip = ("str()", "int()", "dict()", "list()", "tuple()", "set()", "len()", "repr()",
                "getattr()", "setattr()", "hasattr()", "isinstance()", "sorted()", "any()",
                "all()", "max()", "min()", "RuntimeError()", "ValueError()", "KeyError()")
        calls = {d: n for d, n in rep["calls"].get(key, {}).items() if d not in skip}
        if calls:
            add("- 持它期间发起的调用（按次数取前 12）：")
            add("")
            _table(add, ("调用", "次数"), [["`%s`" % d, str(n)] for d, n in
                                          sorted(calls.items(), key=lambda kv: (-kv[1], kv[0]))[:12]])
        add("")

    add("## 先后表")
    add("")
    pairs: dict[tuple[str, str, str], list[str]] = {}
    for outer, inner, _rel, qual, line, kind in rep["direct"]:
        pairs.setdefault((outer, inner, kind), []).append("%s:%s" % (qual, line))
    for outer, inner, _rel, qual, line, desc in rep["indirect"]:
        kind = "间接·重入" if desc.endswith("（重入）") else "间接"
        pairs.setdefault((outer, inner, kind), []).append("%s:%s 经 %s" % (qual, line, desc))
    _table(add, ("外层", "内层", "种类", "处数", "出处"),
           [["`%s`" % o, "`%s`" % i, k, str(len(w)),
             "；".join(w[:3]) + ("…" if len(w) > 3 else "")]
            for (o, i, k), w in sorted(pairs.items())])
    add("")

    add("## 互锁与重入")
    add("")
    seen = {(o, i) for o, i, *_ in rep["direct"]} | {(o, i) for o, i, *_ in rep["indirect"]}
    both = sorted({(a, b) for a, b in seen if a < b and (b, a) in seen})
    add("A→B 与 B→A 同时存在（潜在死锁）的组合：%s"
        % ("；".join("`%s` ↔ `%s`" % ab for ab in both) if both else "无"))
    add("")
    reentry = [(e[0], e[3], e[4], "直接嵌套") for e in rep["direct"] if e[5] == "重入"]
    reentry += [(e[0], e[3], e[4], "经 `%s`" % e[5]) for e in rep["indirect"]
                if e[5].endswith("（重入）")]
    add("同一把锁在同一条静态路径上被拿两次（RLock 的必要性就在这些点上）：")
    add("")
    _table(add, ("锁", "位置", "行", "种类"),
           [["`%s`" % k, "`%s`" % q, str(n), how] for k, q, n, how in reentry]
           or [["—", "—", "—", "没有观察到"]])
    add("")
    bad = [r for r in reentry if decls.get(r[0], ("",))[0] == "Lock"]
    add("其中落在不可重入 Lock 上的：%s"
        % ("；".join("`%s` @ `%s`" % (b[0], b[1]) for b in bad) if bad else "无"))
    add("")

    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="锁图清点（ast，只读源码）")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--head", default="（未记录）", help="基线短哈希，写进表头")
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[5]
    if not (root / "local/app.py").exists():
        print("找不到 local/app.py；用 --repo 指定仓库根。")
        return 2
    mods = load_modules(root)
    for m in mods.values():
        scan_declarations(m)
    services, class_rel = collect_services(mods)
    rep = build(mods, walk_all(mods, collect_param_locks(mods, services)), services, class_rel)
    text = "\n".join(render(rep, mods, args.head,
                            "python -B design/evidence/<日期>/api-coordination/scripts/lock_graph.py"))
    if args.out_dir:
        out = Path(args.out_dir) / "locks.md"
        out.write_text(text + "\n", encoding="utf-8", newline="\n")
        print("已写 %s（%d 行）" % (out, text.count("\n") + 1))
    else:
        print(text)
    print("未认出的 with：%d 处" % len(rep["unknown"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
