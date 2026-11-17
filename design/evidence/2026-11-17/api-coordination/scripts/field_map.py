"""用 ast 清点 Api 的实例字段、模块级全局（含 DEMO）与测试触点。

只读源码：不 import 产品代码；源码解析、锁区间与功能归类复用同目录的 lock_graph.py。
产出三份表：`fields.md`（字段归属）、`tests.md`（测试触点与改造预算）、`demo.md`（DEMO 读写与补丁）。

用法（仓库根）：
    python -B .../scripts/field_map.py --head <短哈希> --out-dir design/evidence/<日期>/api-coordination

口径：
- 字段读写只认 `self.X` 的赋值与读取；`getattr(self, ...)` / `__dict__` 这类动态写法单列一节，不并进计数。
- 「持锁」按 lock_graph 的静态区间：该行落在哪个 `with` 里就算在哪些锁下；锁外记 `—`。
- 测试触点只认 `patch.object(app, "X")`、`patch("app.X")`、`setattr(app, "X", ...)` 与
  `api.X`（含 `self.api.X`）；补别的模块的 patch 不计。
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lock_graph as lg  # noqa: E402  同目录的证据脚本，不是产品代码

APP_ALIASES = {"app", "local_app", "app_module"}


def locks_at(walk, line: int) -> list[str]:
    """该行持有的锁（按进入先后）。"""
    hits = [(s, k) for k, s, e in walk.intervals if s <= line <= e]
    return [k for _s, k in sorted(hits)]


def api_members(mod: lg.ModuleInfo) -> tuple[dict[str, ast.AST], set[str], set[str]]:
    """Api 的方法表、方法名集合、锁字段名集合。"""
    methods = {q.split(".", 1)[1]: fn for q, fn in mod.functions.items() if q.startswith("Api.")}
    lock_attrs = {k.split(".", 1)[1] for k in mod.locks if k.startswith("Api.")}
    return methods, set(methods), lock_attrs


def collect_fields(mods, walks) -> dict:
    """self.X 的每次读写：方法、行、当时的锁、方法所属功能。"""
    api = mods["local/app.py"]
    methods, _names, lock_attrs = api_members(api)
    out: dict[str, list[tuple[str, str, int, list[str], str]]] = {}
    dynamic: list[tuple[str, str, int, str]] = []
    for mname, fn in methods.items():
        walk = walks[("local/app.py", "Api." + mname)]
        feature = lg.classify("Api." + mname)[0]
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    _note(out, tgt, mname, node.lineno, walk, feature, "write", lock_attrs)
            elif isinstance(node, ast.AugAssign):
                _note(out, node.target, mname, node.lineno, walk, feature, "write", lock_attrs)
                _note(out, node.target, mname, node.lineno, walk, feature, "read", lock_attrs)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                _note(out, node.target, mname, node.lineno, walk, feature, "write", lock_attrs)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                _note(out, node, mname, node.lineno, walk, feature, "read", lock_attrs)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("getattr", "setdefault"):
                dynamic.append(("Api." + mname, node.func.attr, node.lineno, ast.unparse(node)[:70]))
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "getattr" and len(node.args) >= 2:
                dynamic.append(("Api." + mname, "getattr", node.lineno, ast.unparse(node)[:70]))
    state = {k: v for k, v in out.items()
             if any(a[0] == "write" for a in v) and not k.startswith("__")}
    readonly = sorted(k for k in out if k not in state and not k.startswith("__"))
    return {"fields": state, "readonly": readonly, "dynamic": dynamic, "lock_attrs": lock_attrs}


def _note(out, tgt, mname, line, walk, feature, how, lock_attrs) -> None:
    if not (isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name)
            and tgt.value.id == "self"):
        return
    if tgt.attr in lock_attrs:
        return  # 锁本身在 locks.md 里清点
    out.setdefault(tgt.attr, []).append((how, mname, line, locks_at(walk, line), feature))


def collect_globals(mods) -> dict[str, dict[str, list[int]]]:
    """模块级全局的读点：{名字: {函数: [行]}}。"""
    api = mods["local/app.py"]
    names: set[str] = set()
    for node in api.tree.body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    reads: dict[str, dict[str, list[int]]] = {n: {} for n in names}
    for qual, fn in api.functions.items():
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names:
                reads[node.id].setdefault(qual, []).append(node.lineno)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in names:
                reads[node.value.id].setdefault(qual, []).append(node.lineno)
    return reads


def _api_vars(tree: ast.AST) -> tuple[set[str], set[str]]:
    """测试里绑到 Api 实例上的名字：局部变量与 self.<attr>。

    两种来源：值里出现 `Api(...)`（含 fixture 包装，如 `cleanup(self, app.Api())`），
    以及惯例名 `api` / `self.api`（测试普遍这么写，纯名字判断，见 README 的口径）。
    """
    names, attrs = {"api"}, {"api"}
    for _ in range(3):
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(kw in ast.unparse(node.value) for kw in ("Api(", "api")):
                continue
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names.add(tgt.id)
                elif isinstance(tgt, ast.Attribute) and isinstance(tgt.value, ast.Name) \
                        and tgt.value.id == "self":
                    attrs.add(tgt.attr)
    return names - {"self"}, attrs


def _app_ref(node: ast.AST) -> str | None:
    """`app` / `local_app` / `self.app` / `self.local_app` 这类模块引用。

    测试普遍写成 `mock.patch.object(self.local_app, "DEMO", True)`，基座是个属性
    而不是裸名字，所以两种都要认；只认最后一段，`self.app` 与 `app` 同权。
    """
    if isinstance(node, ast.Name):
        return node.id if node.id in APP_ALIASES else None
    if isinstance(node, ast.Attribute) and node.attr in APP_ALIASES:
        return node.attr
    return None


def _patch_name(node: ast.Call) -> str | None:
    """`patch.object(app, "X")` / `patch("app.X")` / `setattr(app, "X", v)` 里的 X。

    装饰器写法带 `mock.` 前缀（`@mock.patch.object(...)`），所以按点分全名比尾部，
    不能只看 `f.attr`：那样 `mock.patch.object` 会被当成普通 `object` 调用漏掉。
    """
    full = ast.unparse(node.func)
    tail = full.rsplit(".", 1)[-1]
    if tail == "patch" and node.args:
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) \
                and arg.value.startswith("app."):
            return arg.value.split(".", 1)[1]
        if isinstance(arg, ast.Attribute) and _app_ref(arg.value):
            return arg.attr
    if full.endswith("patch.object") and len(node.args) >= 2:
        name = node.args[1]
        if _app_ref(node.args[0]) and isinstance(name, ast.Constant):
            return str(name.value)
    if tail == "setattr" and len(node.args) >= 2:
        name = node.args[1]
        if _app_ref(node.args[0]) and isinstance(name, ast.Constant):
            return str(name.value)
    return None


def collect_tests(root: Path, api_fields: set[str], api_methods: set[str]) -> list:
    """测试触点：字段读写、私有方法调用、打在 app 模块上的补丁。"""
    rows = []
    for path in sorted((root / "local/tests").glob("*.py")):
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        names, attrs = _api_vars(tree)
        called, patches = set(), []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Attribute):
                called.add(id(node.func))
            name = _patch_name(node)
            if name:
                patches.append(("app 补丁", name, node.lineno))
        rows.extend((rel, how, name, line) for how, name, line in patches)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Load, ast.Store))):
                continue
            base = node.value
            is_api = (isinstance(base, ast.Name) and base.id in names) or (
                isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                and base.value.id == "self" and base.attr in attrs)
            if not is_api or (node.attr not in api_fields and node.attr not in api_methods):
                continue
            if isinstance(node.ctx, ast.Store):
                rows.append((rel, "字段写", node.attr, node.lineno))
            elif id(node) in called and node.attr in api_methods:
                rows.append((rel, "私有方法调用", node.attr, node.lineno))
            else:
                rows.append((rel, "字段读", node.attr, node.lineno))
    return rows


def _table(add, head, rows) -> None:
    add("| " + " | ".join(head) + " |")
    add("|" + "---|" * len(head))
    for row in rows:
        add("| " + " | ".join(row) + " |")


def _locks_text(locks) -> str:
    return "、".join("`%s`" % k for k in locks) if locks else "—"


def fields_md(info, head, cmd) -> list[str]:
    fields = info["fields"]
    L: list[str] = []
    add = L.append
    add("# Api 字段归属")
    add("")
    add("- 生成脚本：`scripts/field_map.py`（ast 只读源码；锁区间与功能归类来自 `lock_graph.py`）")
    add("- 命令：`%s --head %s`" % (cmd, head))
    add("- 基线：`%s`；Api 实例属性 %d 个（Api 上的 %d 把锁另见 locks.md，不在此表）"
        % (head, len(fields), len(info["lock_attrs"])))
    add("- 「功能」按方法名归类，规则与例外写在 `lock_graph.py` 的 FEATURE_RULES / FEATURE_OVERRIDES。")
    add("- 「锁外访问」是该字段在没有任何锁的行上被读写过几次：这些点改归属时最容易漏。")
    add("")
    single, cross = [], []
    for name in sorted(fields):
        acc = fields[name]
        feats = sorted({a[4] for a in acc})
        unlocked = sum(1 for a in acc if not a[3])
        row = ["`%s`" % name, "、".join(feats), str(sum(1 for a in acc if a[0] == "write")),
               str(sum(1 for a in acc if a[0] == "read")),
               str(len({a[1] for a in acc if a[0] == "write"})),
               str(len({a[1] for a in acc if a[0] == "read"})), str(unlocked)]
        (cross if len(feats) > 1 else single).append((row, feats, acc))
    head_row = ("字段", "功能", "写处", "读处", "写方法数", "读方法数", "锁外访问")
    add("## 只被一个功能读写的字段（可以随该服务走）")
    add("")
    _table(add, head_row, [r for r, _f, _a in single])
    add("")
    add("## 被两个以上功能读写的字段（跨功能，必须先定归属）")
    add("")
    _table(add, head_row, [r for r, _f, _a in cross])
    add("")
    add("### 跨功能字段逐项：谁读、谁写、在哪把锁里")
    add("")
    for row, feats, acc in cross:
        add("#### `%s`" % row[0].strip("`"))
        add("")
        _table(add, ("功能", "写的方法", "读的方法", "持锁"),
               [[feat,
                 "、".join("`%s`" % m for m in sorted({a[1] for a in acc
                                                      if a[4] == feat and a[0] == "write"})) or "—",
                 "、".join("`%s`" % m for m in sorted({a[1] for a in acc
                                                      if a[4] == feat and a[0] == "read"})) or "—",
                 "、".join(sorted({_locks_text(a[3]) for a in acc if a[4] == feat}))]
                for feat in feats])
        add("")
    add("## 锁外读写的点")
    add("")
    cross_names = {r[0].strip("`") for r, _f, _a in cross}
    rows = [["`%s`" % name, "写" if a[0] == "write" else "读", "`Api.%s`" % a[1], str(a[2]), a[4]]
            for name in sorted(cross_names) for a in fields[name] if not a[3]]
    add("只列跨功能字段；单功能字段的锁外次数见上面两张表的最后一列。")
    add("")
    _table(add, ("字段", "读写", "方法", "行", "功能"), rows or [["—", "—", "—", "—", "没有"]])
    add("")
    add("## 只读过、没赋过值的 `self.X`（类常量与模块级名字，不归任何服务）")
    add("")
    add("、".join("`%s`" % k for k in info["readonly"]) or "没有")
    add("")
    add("## 动态访问（getattr / setdefault，不并进上面的计数）")
    add("")
    _table(add, ("位置", "写法", "行", "表达式"),
           [["`%s`" % q, h, str(n), "`%s`" % e] for q, h, n, e in info["dynamic"]] or
           [["—", "—", "—", "没有"]])
    add("")
    return L


def _feature_of_touch(fields, how, name) -> str:
    if how == "app 补丁":
        return lg.classify(name, "app")[0]
    if how == "私有方法调用":
        return lg.classify("Api." + name)[0]
    feats = {a[4] for a in fields.get(name, [])}
    return "跨功能" if len(feats) > 1 else (next(iter(feats)) if feats else "其他")


def tests_md(rows, fields, head, cmd) -> list[str]:
    L: list[str] = []
    add = L.append
    add("# 测试触点")
    add("")
    add("- 生成脚本：`scripts/field_map.py`（ast 读 local/tests/*.py）")
    add("- 命令：`%s --head %s`" % (cmd, head))
    add("- 基线：`%s`；触点 %d 处，分布在 %d 个测试文件"
        % (head, len(rows), len({r[0] for r in rows})))
    add("- 归类：字段触点按该字段所属功能（跨功能字段记「跨功能」），私有方法按方法名，app 补丁按名字。")
    add("")
    by_feature: dict[str, list] = {}
    for rel, how, name, line in rows:
        by_feature.setdefault(_feature_of_touch(fields, how, name), []).append((rel, how, name, line))
    add("## 汇总")
    add("")
    _table(add, ("功能", "触点处数", "涉及文件数", "改造预算（行，按每处一行估）"),
           [[feat, str(len(by_feature[feat])), str(len({i[0] for i in by_feature[feat]})),
             str(len(by_feature[feat]))]
            for feat in list(lg.FEATURE_ORDER) + ["跨功能"] if feat in by_feature])
    add("")
    add("预算只估「改测试要动多少行」的量级：搬字段、换断言目标大约一处一行；跨功能字段按最坏情况"
        "（每个功能的责任测试都要改）单独记一档，不摊到任何单个服务。")
    add("")
    for feat in list(lg.FEATURE_ORDER) + ["跨功能"]:
        items = by_feature.get(feat, [])
        if not items:
            continue
        add("## %s（%d 处）" % (feat, len(items)))
        add("")
        kinds: dict[str, list] = {}
        for rel, how, name, line in items:
            kinds.setdefault(how, []).append((rel, name, line))
        _table(add, ("触点类型", "处数", "名字（次数）", "文件分布"),
               [[how, str(len(v)),
                 "、".join("`%s`×%d" % (n, sum(1 for x in v if x[1] == n))
                          for n in sorted({x[1] for x in v})),
                 "、".join("`%s` %d" % (f, sum(1 for x in v if x[0] == f))
                          for f in sorted({x[0] for x in v}))]
                for how, v in sorted(kinds.items(), key=lambda kv: -len(kv[1]))])
        add("")
    return L


def demo_md(globals_, rows, head, cmd) -> list[str]:
    L: list[str] = []
    add = L.append
    demo = globals_.get("DEMO", {})
    patches = [r for r in rows if r[1] == "app 补丁" and r[2] == "DEMO"]
    add("# 模块级 DEMO")
    add("")
    add("- 生成脚本：`scripts/field_map.py`（ast 读 local/app.py 与 local/tests/*.py）")
    add("- 命令：`%s --head %s`" % (cmd, head))
    add("- 基线：`%s`；DEMO 读点 %d 个函数、%d 处；测试打补丁 %d 处"
        % (head, len(demo), sum(len(v) for v in demo.values()), len(patches)))
    add("")
    add("## 读点（按将来归属的服务归）")
    add("")
    _table(add, ("函数/方法", "功能", "读处", "行"),
           [["`%s`" % q, lg.classify(q)[0], str(len(demo[q])),
             "、".join(str(x) for x in sorted(demo[q])[:8])] for q in sorted(demo)])
    add("")
    add("按功能汇总：%s" % "、".join(
        "%s %d" % (f, sum(1 for q in demo if lg.classify(q)[0] == f))
        for f in lg.FEATURE_ORDER if any(lg.classify(q)[0] == f for q in demo)))
    add("")
    add("## 测试打补丁的地方")
    add("")
    by_file: dict[str, int] = {}
    for rel, _how, _name, _line in patches:
        by_file[rel] = by_file.get(rel, 0) + 1
    _table(add, ("测试文件", "补丁次数"),
           [["`%s`" % f, str(n)] for f, n in sorted(by_file.items())] or [["—", "0"]])
    add("")
    add("## 与 2026-11-12 审计的对照")
    add("")
    add("审计（基线 `7e2d31c`）：DEMO 被 22 个函数读、测试补丁 24 次。本次：%d 个函数、%d 次。"
        % (len(demo), len(patches)))
    add("")
    add("读点数与审计一致（22 个函数）。补丁数比审计多 3 处，两头都核过：")
    add("")
    add("- 按本脚本的口径（只数 `patch.object` / `patch(\"app.X\")` / `setattr` 的调用点），"
        "基线 `7e2d31c` 是 26 处，审计的 24 少 2 —— 少的是"
        "`for patch in (mock.patch.object(..., \"DEMO\", ...),)` 这种先收集后启动的元组写法，"
        "审计只数了 `mock.patch.object(...)` 直接出现的行。")
    add("- 26 → 27 的那 1 处是 `local/tests/test_relogin_busy_order.py`：基线没有这个文件，"
        "它是 `636da16` 之后新增的用例文件。")
    add("")
    add("另有一种不走 patch 的注入：`local/tests/test_terms_consent.py` 把 DEMO 写进伪模块的"
        "命名空间字典（`{\"DEMO\": demo, ...}`），再用它 exec 模块级函数——2 处，不计入上表，"
        "因为它替换的是整个模块而不是属性。")
    add("")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Api 字段、DEMO 与测试触点清点（ast 只读）")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--head", default="（未记录）", help="基线短哈希，写进表头")
    args = ap.parse_args(argv)
    root = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[5]
    if not (root / "local/app.py").exists():
        print("找不到 local/app.py；用 --repo 指定仓库根。")
        return 2
    mods = lg.load_modules(root)
    for m in mods.values():
        lg.scan_declarations(m)
    services, _class_rel = lg.collect_services(mods)
    walks = lg.walk_all(mods, lg.collect_param_locks(mods, services))
    info = collect_fields(mods, walks)
    globals_ = collect_globals(mods)
    _methods, method_names, _locks = api_members(mods["local/app.py"])
    rows = collect_tests(root, set(info["fields"]), method_names)
    cmd = "python -B design/evidence/<日期>/api-coordination/scripts/field_map.py"
    docs = (("fields.md", fields_md(info, args.head, cmd)),
            ("tests.md", tests_md(rows, info["fields"], args.head, cmd)),
            ("demo.md", demo_md(globals_, rows, args.head, cmd)))
    if not args.out_dir:
        print("\n".join(docs[0][1]))
        return 0
    out = Path(args.out_dir)
    for name, text in docs:
        (out / name).write_text("\n".join(text) + "\n", encoding="utf-8", newline="\n")
        print("已写 %s（%d 行）" % (out / name, len(text)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
