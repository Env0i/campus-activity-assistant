# -*- coding: utf-8 -*-
"""代码形状守卫：文件行数、函数行数、测试函数行数、类里多处赋值的实例属性个数。

量法照 design/evidence/2026-11-12/refactor-audit/README.md 的「C1 ③」「C1 ④」：
- 文件行数是物理行；Python 函数/类从 def/class 那一行量到最后一行，不含装饰器；
- JS 函数交给同目录的 jsfuncs.mjs（词法扫描 + 花括号配对）；
- 实例属性只算 self.x 的 `=`、`+=`、带注解赋值，在不少于 3 个方法里赋值的属性才计，
  这样的属性超过 5 个才算这个类超限。嵌套函数里写的 self.x 记在所在方法上。

用法：
  python tools/code_shape/check.py           只读比对：列出违规，有违规时非零退出
  python tools/code_shape/check.py --json    同上，输出机器可读 JSON
  python tools/code_shape/check.py --tighten 把名单记录值收紧到当前值，删掉已不超限的项；
                                             拒绝任何变长或新增
  python tools/code_shape/check.py --init    只在 baseline.json 不存在时生成名单
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASELINE = HERE / "baseline.json"
JSFUNCS = HERE / "jsfuncs.mjs"
EXTS = (".py", ".js", ".mjs")
ROOTS = ("local", "server", "tools")

FILE_LIMIT = 500
FILE_OVER_LIMIT = 800
FUNC_LIMIT = 60
FUNC_OVER_LIMIT = 100
CLASS_ATTR_LIMIT = 5
CLASS_ATTR_METHODS = 3


# ───────────────────────── 取文件 ─────────────────────────

def list_sources() -> list[str]:
    """git 认识的全部源码：已跟踪的加还没跟踪的（新文件也要查）。"""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", *ROOTS],
        cwd=str(ROOT), capture_output=True, check=True).stdout.decode("utf-8")
    files = [p for p in out.split("\0") if p]
    return sorted(f for f in files if f.endswith(EXTS) and not f.startswith(".claude/"))


def is_test(path: str) -> bool:
    parts = path.split("/")
    return "tests" in parts[:-1] or parts[-1].startswith("test_")


def count_lines(text: str) -> int:
    n = text.count("\n")
    return n + 1 if text and not text.endswith("\n") else n


# ───────────────────────── Python 量法 ─────────────────────────

def py_units(path: str, text: str) -> list[dict]:
    """函数与类：def/class 那一行到最后一行，不含装饰器；嵌套的单独算。"""
    tree = ast.parse(text, filename=path)
    units: list[dict] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                qual = prefix + child.name
                units.append({"file": path, "qual": qual, "kind": kind,
                              "start": child.lineno,
                              "lines": child.end_lineno - child.lineno + 1})
                walk(child, qual + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    return units


def _self_attr(target: ast.AST) -> str:
    """只有目标是 self.x 本身才回 "x"。

    self.x[k] = v 是容器内修改、self.x.y = v 改的是别人的属性，按 D5 都不算
    「在这个方法里给 self.x 赋值」；把它们算进来会把容器初始化抬过 3 个方法的门槛。
    """
    if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
            and target.value.id == "self"):
        return target.attr
    return ""


def _assigned_self_attrs(method: ast.AST) -> set[str]:
    """一个方法（含它内部的嵌套函数）里被赋值的 self.x 名字。"""
    names = set()
    for node in ast.walk(method):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                flat = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
                for one in flat:
                    name = _self_attr(one) if not isinstance(one, ast.Name) else ""
                    if name:
                        names.add(name)
    return names


def class_attr_counts(path: str, text: str) -> list[dict]:
    """每个类里「在不少于 3 个方法里赋值」的实例属性个数。"""
    tree = ast.parse(text, filename=path)
    rows: list[dict] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qual = prefix + child.name
                per_attr: dict[str, set[str]] = {}
                for item in child.body:
                    if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    for name in _assigned_self_attrs(item):
                        per_attr.setdefault(name, set()).add(item.name)
                counted = sorted(n for n, ms in per_attr.items() if len(ms) >= CLASS_ATTR_METHODS)
                rows.append({"file": path, "qual": qual, "attrs": counted, "count": len(counted)})
                walk(child, qual + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    return rows


# ───────────────────────── JS 量法 ─────────────────────────

def _normalize_js_name(qualname: str, anonymous: list[str]) -> str:
    """把 A > B 变成 A.B；<anonymous@行号> 换成按出现顺序编号的 #anonN（键里不能有行号）。"""
    parts = []
    for part in qualname.split(" > "):
        if part.startswith("<anonymous@"):
            anonymous.append(part)
            parts.append("#anon%d" % len(anonymous))
        else:
            parts.append(part)
    return ".".join(parts)


def js_units(files: list[str]) -> tuple[list[dict], str]:
    """调 jsfuncs.mjs；返回函数清单和跳过原因（没有 node 时）。"""
    js_files = [f for f in files if f.endswith((".js", ".mjs"))]
    if not js_files:
        return [], ""
    try:
        proc = subprocess.run(["node", str(JSFUNCS), *js_files], cwd=str(ROOT),
                              capture_output=True, check=True)
    except FileNotFoundError:
        return [], "本机没有 node，JS 函数行数没有查"
    except subprocess.CalledProcessError as exc:
        raise SystemExit("jsfuncs.mjs 执行失败：%s" % (exc.stderr or b"").decode("utf-8", "replace"))
    data = json.loads(proc.stdout.decode("utf-8"))
    rows: list[dict] = []
    for entry in data:
        anonymous: list[str] = []
        for fn in entry["functions"]:
            rows.append({"file": entry["file"],
                         "qual": _normalize_js_name(fn["name"], anonymous),
                         "start": fn["start"], "lines": fn["lines"]})
    return rows, ""


# ───────────────────────── 汇总 ─────────────────────────

def collect() -> dict:
    files = list_sources()
    product_files: dict[str, int] = {}
    product_funcs: list[dict] = []
    test_funcs: list[dict] = []
    classes: list[dict] = []
    for path in files:
        text = (ROOT / path).read_text(encoding="utf-8")
        if is_test(path):
            if path.endswith(".py"):
                for u in py_units(path, text):
                    if u["kind"] == "function" and u["qual"].split(".")[-1].startswith("test_"):
                        test_funcs.append(u)
            continue
        product_files[path] = count_lines(text)
        if path.endswith(".py"):
            for u in py_units(path, text):
                if u["kind"] == "function":
                    product_funcs.append(u)
            classes.extend(class_attr_counts(path, text))
    js_funcs, js_skip = js_units(files)
    product_funcs.extend(u for u in js_funcs if not is_test(u["file"]))
    product_funcs = _unique_quals(product_funcs)
    test_funcs = _unique_quals(test_funcs)
    return {"files": product_files, "functions": product_funcs,
            "test_functions": test_funcs, "classes": classes, "js_skipped": js_skip}


def _unique_quals(rows: list[dict]) -> list[dict]:
    """同一个文件里限定名重复时按出现顺序加 #2、#3，键里不能有行号。"""
    seen: dict[tuple, int] = {}
    out = []
    for row in sorted(rows, key=lambda r: (r["file"], r["start"], r["qual"])):
        key = (row["file"], row["qual"])
        seen[key] = seen.get(key, 0) + 1
        item = dict(row)
        if seen[key] > 1:
            item["qual"] = "%s#%d" % (row["qual"], seen[key])
        out.append(item)
    return out


def key_of(row: dict) -> str:
    return "%s::%s" % (row["file"], row["qual"])


def build_entry(row: dict, reason: str) -> dict:
    entry = {"value": row["lines"] if "lines" in row else row["count"]}
    if reason:
        entry["reason"] = reason
    return entry


def init_lists(data: dict) -> dict:
    """按当前代码生成名单：超过上限的项才进名单，甲乙按阈值分。"""
    files_a, files_b = {}, {}
    for path, lines in data["files"].items():
        if lines > FILE_OVER_LIMIT:
            files_a[path] = build_entry({"lines": lines}, "")
        elif lines > FILE_LIMIT:
            files_b[path] = build_entry({"lines": lines}, "")
    funcs_a, funcs_b = {}, {}
    for row in data["functions"]:
        if row["lines"] > FUNC_OVER_LIMIT:
            funcs_a[key_of(row)] = build_entry(row, "")
        elif row["lines"] > FUNC_LIMIT:
            funcs_b[key_of(row)] = build_entry(row, "")
    tests = {key_of(r): build_entry(r, "") for r in data["test_functions"]
             if r["lines"] > FUNC_LIMIT}
    classes = {key_of(r): {"value": r["count"], "attrs": r["attrs"], "reason": ""}
               for r in data["classes"] if r["count"] > CLASS_ATTR_LIMIT}
    return {
        "files": {"over800": dict(sorted(files_a.items())),
                  "over500": dict(sorted(files_b.items()))},
        "functions": {"over100": dict(sorted(funcs_a.items())),
                      "over60": dict(sorted(funcs_b.items()))},
        "test_functions": dict(sorted(tests.items())),
        "classes": dict(sorted(classes.items())),
    }


# ───────────────────────── 比对 ─────────────────────────

def _check_group(kind: str, rows: dict, listed: dict, limit: int,
                 violations: list[dict]) -> None:
    for key, value in rows.items():
        if key in listed:
            recorded = listed[key]["value"]
            if value > recorded:
                violations.append({"kind": kind, "file": key.split("::")[0],
                                   "name": key, "value": value, "recorded": recorded,
                                   "limit": recorded})
        elif value > limit:
            violations.append({"kind": kind, "file": key.split("::")[0],
                               "name": key, "value": value, "recorded": None,
                               "limit": limit})


def compare(baseline: dict, data: dict) -> list[dict]:
    violations: list[dict] = []
    files = data["files"]
    listed_files = dict(baseline["files"]["over800"])
    listed_files.update(baseline["files"]["over500"])
    _check_group("file", files, listed_files, FILE_LIMIT, violations)

    funcs = {key_of(r): r["lines"] for r in data["functions"]}
    listed_funcs = dict(baseline["functions"]["over100"])
    listed_funcs.update(baseline["functions"]["over60"])
    _check_group("function", funcs, listed_funcs, FUNC_LIMIT, violations)

    tests = {key_of(r): r["lines"] for r in data["test_functions"]}
    _check_group("test_function", tests, baseline["test_functions"], FUNC_LIMIT, violations)

    attrs = {key_of(r): r["count"] for r in data["classes"]}
    _check_group("class_attrs", attrs, baseline["classes"], CLASS_ATTR_LIMIT, violations)
    return violations


def _kept_entry(entry: dict, value: int, attrs=None) -> dict:
    """收紧后的名单项：只允许记录值变小；类的属性清单同步更新。"""
    item = dict(entry, value=value)
    if attrs is not None:
        item["attrs"] = attrs
    return item


def _tighten_two_tier(entries: dict, rows: dict, low: int, high: int,
                      label: str, problems: list[str]) -> tuple[dict, dict]:
    """把一组名单按当前值重新分成两档：仍 >high 的留甲（带理由），low<值<=high 的降乙。

    降档不是「新增」：文件从 850 行缩到 700、函数从 150 行缩到 90 时，该项只是从甲挪到乙，
    不能因为收紧后的名单里没有它就报「新超限项」。
    """
    for key, entry in entries.items():
        if key in rows and rows[key] > entry["value"]:
            problems.append("%s变长：%s %d > 名单 %d"
                            % (label, key, rows[key], entry["value"]))
    top: dict = {}
    mid: dict = {}
    for key, entry in entries.items():
        if key not in rows:
            continue
        value = rows[key]
        if value > high:
            top[key] = _kept_entry(entry, value)
        elif value > low:
            mid[key] = {"value": value}
    return top, mid


def _tighten_flat(source: dict, entries: dict, limit: int, label: str,
                  problems: list[str], attrs_of=None) -> dict:
    """按上限收紧一组「键 → 记录值」名单；变长记为问题，已不超限的项删掉。"""
    kept: dict = {}
    for key, entry in entries.items():
        if key not in source:
            continue
        value = source[key]
        if value > entry["value"]:
            problems.append("%s变长：%s %d > 名单 %d" % (label, key, value, entry["value"]))
        if value > limit:
            kept[key] = _kept_entry(entry, value, attrs_of and attrs_of(key))
    return kept


def _assert_no_new(rows: dict, listed: dict, limit: int, kind: str,
                   problems: list[str]) -> None:
    """收紧后不得出现名单外的新超限项。"""
    for key, value in rows.items():
        if key not in listed and value > limit:
            problems.append("新超限项：%s %s=%d" % (kind, key, value))


def _tighten_classes(attrs: dict, entries: dict, data: dict,
                     problems: list[str]) -> dict:
    def attrs_of(key: str):
        return next(r["attrs"] for r in data["classes"] if key_of(r) == key)
    return _tighten_flat(attrs, entries, CLASS_ATTR_LIMIT, "类属性", problems, attrs_of)


def tighten(baseline: dict, data: dict) -> tuple[dict, list[str]]:
    """收紧记录值并删掉已不超限的项；任何变长或新增都拒绝。"""
    problems: list[str] = []
    files = data["files"]
    funcs = {key_of(r): r["lines"] for r in data["functions"]}
    tests = {key_of(r): r["lines"] for r in data["test_functions"]}
    attrs = {key_of(r): r["count"] for r in data["classes"]}
    out = {"files": {}, "functions": {}, "test_functions": {}, "classes": {}}
    base_files, base_funcs = baseline["files"], baseline["functions"]
    out["files"]["over800"], out["files"]["over500"] = _tighten_two_tier(
        {**base_files["over800"], **base_files["over500"]}, files,
        FILE_LIMIT, FILE_OVER_LIMIT, "文件", problems)
    out["functions"]["over100"], out["functions"]["over60"] = _tighten_two_tier(
        {**base_funcs["over100"], **base_funcs["over60"]}, funcs,
        FUNC_LIMIT, FUNC_OVER_LIMIT, "函数", problems)
    out["test_functions"] = _tighten_flat(tests, baseline["test_functions"],
                                          FUNC_LIMIT, "测试函数", problems)
    out["classes"] = _tighten_classes(attrs, baseline["classes"], data, problems)
    listed_files = dict(out["files"]["over800"])
    listed_files.update(out["files"]["over500"])
    listed_funcs = dict(out["functions"]["over100"])
    listed_funcs.update(out["functions"]["over60"])
    _assert_no_new(files, listed_files, FILE_LIMIT, "file", problems)
    _assert_no_new(funcs, listed_funcs, FUNC_LIMIT, "function", problems)
    _assert_no_new(tests, out["test_functions"], FUNC_LIMIT, "test_function", problems)
    _assert_no_new(attrs, out["classes"], CLASS_ATTR_LIMIT, "class_attrs", problems)
    return out, problems


def load_baseline() -> dict:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    data = collect()
    if data["js_skipped"] and ("--init" in argv or "--tighten" in argv):
        # JS 名单靠 jsfuncs 现算：查不到时写名单会把整段 JS 记录删掉或生成空名单
        print("JS 函数没查成（%s）；--init 与 --tighten 拒绝执行，避免删掉 JS 名单。"
              % data["js_skipped"], file=sys.stderr)
        return 2
    if "--init" in argv:
        if BASELINE.exists():
            print("baseline.json 已存在；--init 只在它不存在时可用。", file=sys.stderr)
            return 2
        baseline = init_lists(data)
        BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        print("已生成 %s" % BASELINE.name)
        return 0
    if not BASELINE.exists():
        print("baseline.json 不存在；先跑 --init。", file=sys.stderr)
        return 2
    baseline = load_baseline()
    if "--tighten" in argv:
        tightened, problems = tighten(baseline, data)
        if problems:
            for problem in problems:
                print("拒绝收紧：" + problem, file=sys.stderr)
            return 1
        BASELINE.write_text(json.dumps(tightened, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
        print("名单已收紧")
        return 0
    violations = compare(baseline, data)
    if "--json" in argv:
        print(json.dumps({"violations": violations, "counts": counts_of(data),
                          "js_skipped": data["js_skipped"]}, ensure_ascii=False, indent=2))
        return 1 if violations else 0
    for item in violations:
        print("%s %s = %d（上限 %d）" % (item["kind"], item["name"], item["value"],
                                        item["limit"]))
    if data["js_skipped"]:
        print("跳过：" + data["js_skipped"])
    if violations:
        print("\n共 %d 项超限。" % len(violations), file=sys.stderr)
        return 1
    print("代码形状检查通过：" + _counts_text(data))
    return 0


def counts_of(data: dict) -> dict:
    files = data["files"]
    funcs = data["functions"]
    return {
        "files_over800": sum(1 for v in files.values() if v > FILE_OVER_LIMIT),
        "files_over500": sum(1 for v in files.values()
                             if FILE_LIMIT < v <= FILE_OVER_LIMIT),
        "functions_over100": sum(1 for r in funcs if r["lines"] > FUNC_OVER_LIMIT),
        "functions_over60": sum(1 for r in funcs
                                if FUNC_LIMIT < r["lines"] <= FUNC_OVER_LIMIT),
        "test_functions_over60": sum(1 for r in data["test_functions"] if r["lines"] > FUNC_LIMIT),
        "classes": sum(1 for r in data["classes"] if r["count"] > CLASS_ATTR_LIMIT),
    }


def _counts_text(data: dict) -> str:
    c = counts_of(data)
    return ("文件 >800 行 %d 个、501–800 行 %d 个；函数 >100 行 %d 个、61–100 行 %d 个；"
            "测试函数 >60 行 %d 个；属性超标的类 %d 个"
            % (c["files_over800"], c["files_over500"], c["functions_over100"],
               c["functions_over60"], c["test_functions_over60"], c["classes"]))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
