# -*- coding: utf-8 -*-
"""表 A：四份名单的每一项按计划 D2 的固定对照表标归属。

口径出处：.claude/plans/plan-20261113-refactor-endpoint-evidence.yaml decisions D2、D3。
- 归属按文件：名单项取「::」前的文件部分查 D2 对照表；对照表没有这个文件的，
  一律记「未排进任何一步」（D3：对不上的不许自己判断）。
- baseline.json 的 reason 字段不参与归属（D3 只认 D2 对照表）。
- 前端白名单项按「引用方文件」归属，另列「被引用名字的定义文件」的归属（D3）。
- 当前值取自 tools/code_shape/check.py 的同一套量法（import 后调 collect()）。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ownership.py
只用标准库；node 仅经 ui_coupling.mjs --defs 取前端名字的定义文件。
"""
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root():
    """先按「脚本位置上推四级」定位仓库根；脚本被复制到别处时改问 git。"""
    cand = HERE.parents[4] if len(HERE.parents) > 4 else None
    if cand is not None and (cand / ".git").exists():
        return cand
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    if out.returncode == 0:
        return Path(out.stdout.decode("utf-8", "replace").strip())
    raise SystemExit("定位不到仓库根：请从仓库根运行本脚本")


REPO = _repo_root()

# D2 的固定对照表，逐字来自计划 decisions D2；出处就是本计划，未做任何增删。
D2_STEPS = {
    "步骤 1A 组件与手机访问": (
        "local/ui/views/phone.js",
        "local/ui/views/settings.js",
    ),
    "步骤 1B 登录": (
        "local/ui/state/login.js",
        "local/ui/views/login.js",
        "local/ui/views/relogin.js",
        "local/ui/views/status-cards.js",
    ),
    "步骤 1C 计划栏": (
        "local/ui/views/plan-panel.js",
        "local/ui/controllers/plan.js",
        "local/ui/controllers/plan-events.js",
        "local/ui/state/plan.js",
        "local/ui/state/task-display.js",
    ),
    "步骤 1 共用": (
        "local/ui/controllers/refresh.js",
        "local/ui/app.js",
        "local/ui/state/store.js",
    ),
    "步骤 2": ("local/app.py",),
    "步骤 3": ("local/grab.py",),
}
M_PREFIX = "local/ui/m/"
FILE2STEP = {f: s for s, fs in D2_STEPS.items() for f in fs}
UNPLACED = "未排进任何一步"


def step_of(path):
    if path.startswith(M_PREFIX):
        return "手机页"
    return FILE2STEP.get(path, UNPLACED)


def count_file_lines(rel):
    p = REPO / rel
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="replace")
    return len(text.replace("\r\n", "\n").rstrip("\n").split("\n"))


def load_check_data():
    """复用 tools/code_shape/check.py 的量法取当前值；不落任何盘。"""
    sys.path.insert(0, str(REPO / "tools" / "code_shape"))
    import check as shape_check  # noqa: PLC0415（与仓库同名风格一致，顶层一次性导入）

    data = shape_check.collect()
    return {
        "files": dict(data["files"]),
        "funcs": {(r["file"], r["qual"]): r["lines"] for r in data["functions"]},
        "tests": {(r["file"], r["qual"]): r["lines"] for r in data["test_functions"]},
        "classes": {(r["file"], r["qual"]): r["count"] for r in data["classes"]},
        "js_skipped": data["js_skipped"],
    }


def load_legacy_violations():
    """从 local/tests/test_layer_boundaries.py 用 ast 取 LEGACY_DIRECTION_VIOLATIONS 的键。"""
    src = (REPO / "local" / "tests" / "test_layer_boundaries.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "LEGACY_DIRECTION_VIOLATIONS" for t in node.targets
        ):
            if isinstance(node.value, ast.Dict):
                for k in node.value.keys:
                    if isinstance(k, ast.Tuple) and len(k.elts) == 2:
                        file_part = ast.literal_eval(k.elts[0])
                        module = ast.literal_eval(k.elts[1])
                        if not (file_part.startswith("local/") or file_part.startswith("server/")):
                            file_part = "local/" + file_part
                        keys.append((file_part, module))
    return keys


def load_ruff_items():
    """ruff.toml 里 per-file-ignores 的每个「文件×规则码」。"""
    text = (REPO / "ruff.toml").read_text(encoding="utf-8")
    body = text.split("[lint.per-file-ignores]", 1)[1]
    items = []
    for m in re.finditer(r'^"([^"]+)"\s*=\s*\[([^\]]*)\]', body, re.M):
        for code in re.findall(r'"([^"]+)"', m.group(2)):
            items.append((m.group(1), code))
    return items


def load_allow_defs():
    """调 ui_coupling.mjs --defs 取「前端顶层名字 → 定义文件」；取同目录的脚本，复制体也成立。"""
    out = subprocess.run(
        ["node", str(HERE / "ui_coupling.mjs"), "--defs"],
        cwd=str(REPO), capture_output=True, check=True,
    )
    return json.loads(out.stdout.decode("utf-8"))


def main():
    cur = load_check_data()
    base = json.loads((REPO / "tools" / "code_shape" / "baseline.json").read_text(encoding="utf-8"))

    # items: (来源, 条目, 记录值, 当前值, 规则码, 归属)
    items = []

    def add(src, key, record, current, code, path):
        items.append({
            "src": src, "key": key, "record": record, "current": current,
            "code": code, "step": step_of(path),
        })

    for tier in ("over800", "over500"):
        for k, v in base["files"][tier].items():
            add(f"baseline 文件名单（{tier}）", k, v["value"],
                cur["files"].get(k) or count_file_lines(k), "", k)
    for tier in ("over100", "over60"):
        for k, v in base["functions"][tier].items():
            path = k.split("::")[0]
            add(f"baseline 函数名单（{tier}）", k, v["value"],
                cur["funcs"].get((path, k.split("::", 1)[1]), "不在当前清点里"), "", path)
    for k, v in base["test_functions"].items():
        path = k.split("::")[0]
        add("baseline 测试函数名单", k, v["value"],
            cur["tests"].get((path, k.split("::", 1)[1]), "不在当前清点里"), "", path)
    for k, v in base["classes"].items():
        path = k.split("::")[0]
        add("baseline 类名单", k, v["value"],
            cur["classes"].get((path, k.split("::", 1)[1]), "不在当前清点里"), "", path)

    defs = load_allow_defs()["defs"]
    allow = json.loads((REPO / "tools" / "code_shape" / "ui_layer_allow.json").read_text(encoding="utf-8"))
    for group, files in allow.items():
        for relfile, names in files.items():
            reffile = "local/ui/" + relfile
            for name in names:
                deffile = defs.get(name)
                if deffile is None:
                    defdisp, defstep = "定义未找到", UNPLACED
                else:
                    defdisp = "local/ui/" + deffile
                    defstep = step_of(defdisp)
                items.append({
                    "src": "前端分层白名单 ui_layer_allow.json",
                    "key": f"{reffile} × {name}",
                    "record": "", "current": count_file_lines(reffile), "code": "",
                    "step": step_of(reffile),
                    "def_file": defdisp, "def_step": defstep,
                })

    for file_part, module in load_legacy_violations():
        items.append({
            "src": "分层测试存量例外 LEGACY_DIRECTION_VIOLATIONS",
            "key": f"{file_part} import {module}",
            "record": "", "current": count_file_lines(file_part), "code": "",
            "step": step_of(file_part),
        })

    for file_part, code in load_ruff_items():
        items.append({
            "src": "ruff.toml per-file-ignores",
            "key": f"{file_part} × {code}",
            "record": "", "current": "", "code": code,
            "step": step_of(file_part),
        })

    total = len(items)
    counts = Counter(it["step"] for it in items)
    scheduled = sum(n for s, n in counts.items() if s != UNPLACED)
    unplaced = counts.get(UNPLACED, 0)

    print("## 表 A：四份名单的每项归属（按计划 D2 对照表）")
    print()
    print("量什么：baseline.json 的四份名单（文件两档、函数两档、测试函数、类）、ui_layer_allow.json 的每一项、"
          "LEGACY_DIRECTION_VIOLATIONS 的每一项、ruff.toml per-file-ignores 的每个「文件×规则码」，"
          "按 D2 的固定对照表标归属；对照表没有的文件记「未排进任何一步」。")
    print()
    print("### A1 归属汇总与自校")
    print()
    print("| 归属 | 项数 |")
    print("|---|---|")
    for s in list(D2_STEPS) + ["手机页", UNPLACED]:
        if counts.get(s):
            print(f"| {s} | {counts[s]} |")
    print(f"| 合计 | {total} |")
    print()
    print(f"表 A 自校：各步项数 {scheduled} + 未排进项数 {unplaced} = 四份名单总项数 {total} -> "
          f"{'成立' if scheduled + unplaced == total else '不成立'}")
    print()
    print("### A2 未排进任何一步的完整清单")
    print()
    print("| 来源 | 条目 | 当前行数 | 规则码 |")
    print("|---|---|---|---|")
    for it in items:
        if it["step"] != UNPLACED:
            continue
        cur_disp = it["code"] if it["code"] else (it["current"] if it["current"] != "" else "—")
        print(f"| {it['src']} | `{it['key']}` | {cur_disp} | {it['code'] or '—'} |")
    print(f"未排进共 {unplaced} 项。")
    print()
    print("### A3 明细")
    print()
    by_src = {}
    for it in items:
        by_src.setdefault(it["src"], []).append(it)
    for src, rows in by_src.items():
        allow_like = "def_file" in rows[0]
        if allow_like:
            print(f"#### {src}（归属按「引用方文件」；另列「被引用名字的定义文件」的归属）")
            print()
            print("| 条目（引用方文件 × 名字）| 引用方归属 | 当前行数 | 定义文件 | 定义文件归属 |")
            print("|---|---|---|---|---|")
            for it in rows:
                print(f"| `{it['key']}` | {it['step']} | {it['current']} | `{it['def_file']}` | {it['def_step']} |")
        else:
            print(f"#### {src}")
            print()
            print("| 条目 | 记录值 | 当前值 | 归属 |")
            print("|---|---|---|---|")
            for it in rows:
                record = it["record"] if it["record"] != "" else "—"
                current = it["current"] if it["current"] != "" else it["code"]
                print(f"| `{it['key']}` | {record} | {current} | {it['step']} |")
        print()
    if cur["js_skipped"]:
        print(f"注：{cur['js_skipped']}。")


if __name__ == "__main__":
    main()
