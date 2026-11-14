# -*- coding: utf-8 -*-
"""review2 表 A 独立复算：四份名单逐项按计划 D2 对照表归属，并做自校。

独立实现说明：不复制第一轮 scripts/ownership.py；名单解析、归属映射、汇总全部重写。
当前值复用仓库既有工具 tools/code_shape/check.py 的 collect()（入库工具，非本轮结论文件）。

从仓库根运行：python -B design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_a_ownership.py
"""
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5] if len(HERE.parents) > 5 and (HERE.parents[5] / ".git").exists() else None
if REPO is None:
    import subprocess
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True)
    REPO = Path(out.stdout.decode().strip())

# D2 对照表（逐字取自计划 decisions D2）
D2 = {
    "步骤 1A": ("local/ui/views/phone.js", "local/ui/views/settings.js"),
    "步骤 1B": ("local/ui/state/login.js", "local/ui/views/login.js",
               "local/ui/views/relogin.js", "local/ui/views/status-cards.js"),
    "步骤 1C": ("local/ui/views/plan-panel.js", "local/ui/controllers/plan.js",
               "local/ui/controllers/plan-events.js", "local/ui/state/plan.js",
               "local/ui/state/task-display.js"),
    "步骤 1 共用": ("local/ui/controllers/refresh.js", "local/ui/app.js", "local/ui/state/store.js"),
    "步骤 2": ("local/app.py",),
    "步骤 3": ("local/grab.py",),
}
F2S = {f: s for s, fs in D2.items() for f in fs}
UNP = "未排进任何一步"


def step_of(path):
    if path.startswith("local/ui/m/"):
        return "手机页"
    return F2S.get(path, UNP)


def file_lines(rel):
    p = REPO / rel
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    return len(t.rstrip("\n").split("\n")) if t.strip() else 0


def legacy_keys():
    src = (REPO / "local/tests/test_layer_boundaries.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "LEGACY_DIRECTION_VIOLATIONS" for t in node.targets):
            for k in node.value.keys:
                f, m = (ast.literal_eval(x) for x in k.elts)
                yield (f if f.startswith(("local/", "server/")) else "local/" + f, m)


def ruff_items():
    text = (REPO / "ruff.toml").read_text(encoding="utf-8")
    body = text.split("[lint.per-file-ignores]", 1)[1]
    return [(m.group(1), c) for m in re.finditer(r'^"([^"]+)"\s*=\s*\[([^\]]*)\]', body, re.M)
            for c in re.findall(r'"([^"]+)"', m.group(2))]


def main():
    sys.path.insert(0, str(REPO / "tools" / "code_shape"))
    import check as shape_check
    cur = shape_check.collect()
    cur_files = dict(cur["files"])
    cur_fn = {(r["file"], r["qual"]): r["lines"] for r in cur["functions"]}
    cur_tf = {(r["file"], r["qual"]): r["lines"] for r in cur["test_functions"]}
    cur_cl = {(r["file"], r["qual"]): r["count"] for r in cur["classes"]}

    base = json.loads((REPO / "tools/code_shape/baseline.json").read_text(encoding="utf-8"))
    allow = json.loads((REPO / "tools/code_shape/ui_layer_allow.json").read_text(encoding="utf-8"))

    items = []  # (来源, 条目, 记录值, 当前值, 归属)
    for tier in ("over800", "over500"):
        for k, v in base["files"][tier].items():
            items.append((f"baseline文件({tier})", k, v["value"],
                          cur_files.get(k, file_lines(k)), step_of(k)))
    for tier in ("over100", "over60"):
        for k, v in base["functions"][tier].items():
            path, qual = k.split("::", 1)
            items.append((f"baseline函数({tier})", k, v["value"],
                          cur_fn.get((path, qual), "缺"), step_of(path)))
    for k, v in base["test_functions"].items():
        path, qual = k.split("::", 1)
        items.append(("baseline测试函数", k, v["value"], cur_tf.get((path, qual), "缺"), step_of(path)))
    for k, v in base["classes"].items():
        path, qual = k.split("::", 1)
        items.append(("baseline类", k, v["value"], cur_cl.get((path, qual), "缺"), step_of(path)))
    n_baseline = len(items)

    allow_items = []
    for group, files in allow.items():
        for relfile, names in files.items():
            reffile = "local/ui/" + relfile
            for name in names:
                allow_items.append((f"{reffile} × {name}", step_of(reffile)))
    n_allow = len(allow_items)

    legacy = [(f"{f} import {m}", step_of(f)) for f, m in legacy_keys()]
    n_legacy = len(legacy)

    ruff = [(f"{f} × {c}", step_of(f)) for f, c in ruff_items()]
    n_ruff = len(ruff)

    total = n_baseline + n_allow + n_legacy + n_ruff
    counts = Counter(it[4] for it in items)
    counts += Counter(s for _, s in allow_items)
    counts += Counter(s for _, s in legacy)
    counts += Counter(s for _, s in ruff)
    scheduled = sum(n for s, n in counts.items() if s != UNP)
    unplaced = counts.get(UNP, 0)

    print("## review2 表 A 独立复算")
    print()
    print("| 归属 | 项数 |")
    print("|---|---|")
    for s in list(D2) + ["手机页", UNP]:
        if counts.get(s):
            print(f"| {s} | {counts[s]} |")
    print(f"| 合计 | {total} |")
    print()
    print(f"名单构成：baseline {n_baseline}（文件 {sum(1 for it in items if it[0].startswith('baseline文件'))}"
          f"+函数 {sum(1 for it in items if it[0].startswith('baseline函数'))}"
          f"+测试函数 {sum(1 for it in items if it[0]=='baseline测试函数')}"
          f"+类 {sum(1 for it in items if it[0]=='baseline类')}）"
          f"+ 白名单 {n_allow} + 分层例外 {n_legacy} + ruff {n_ruff} = {total}")
    print()
    print(f"自校：各步项数 {scheduled} + 未排进项数 {unplaced} = 总项数 {total} -> "
          f"{'成立' if scheduled + unplaced == total else '不成立'}")
    print()
    print("### 未排进清单（独立重算）")
    print()
    print("| 来源 | 条目 | 当前值 |")
    print("|---|---|---|")
    n_unp = 0
    for src, key, rec, curv, st in items:
        if st != UNP:
            continue
        n_unp += 1
        print(f"| {src} | `{key}` | {curv} |")
    for key, _ in allow_items:
        if step_of(key.split(" × ")[0]) == UNP:
            n_unp += 1
            print(f"| 前端白名单 | `{key}` | {file_lines(key.split(' × ')[0])} |")
    for key, _ in legacy:
        n_unp += 1
        print(f"| 分层例外 | `{key}` | {file_lines(key.split(' import ')[0])} |")
    for key, _ in ruff:
        if step_of(key.split(" × ")[0]) == UNP:
            n_unp += 1
            print(f"| ruff | `{key}` | {key.split(' × ')[1]} |")
    print(f"未排进共 {n_unp} 项。")
    print()
    print("### 排进了的项（独立重算，按步分组）")
    print()
    for s in list(D2) + ["手机页"]:
        rows = [it for it in items if it[4] == s]
        rows_a = [(k, file_lines(k.split(" × ")[0])) for k, st in allow_items if st == s]
        if rows or rows_a:
            print(f"**{s}（{len(rows) + len(rows_a)} 项）**")
            for src, key, rec, curv, _ in rows:
                print(f"- {src} `{key}` 记录 {rec} 当前 {curv}")
            for k, ln in rows_a:
                print(f"- 白名单 `{k}` 当前行数 {ln}")
            print()


if __name__ == "__main__":
    main()
