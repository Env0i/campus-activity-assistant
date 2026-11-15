# -*- coding: utf-8 -*-
"""把登录块搬成模块之后，在同一份行清单上再跑一遍量具，逐行对照搬之前的结论。

做法：不复制任何行清单，直接导入登录-net 那一份脚本，把每行的「文件」按函数名换成新位置
（函数名与那一行的文字一个字不改），再调它的 main()。这样两边量的永远是同一批行。

三种用法（都从仓库根执行）：
  python -B design/evidence/<日期>/login-move/scripts/net_after_move.py --verify
  python -B design/evidence/<日期>/login-move/scripts/net_after_move.py --shard-index 0 --shard-count 8 --out 结果目录/shard-0.json
  python -B design/evidence/<日期>/login-move/scripts/net_after_move.py --compare 结果目录

--compare 读该目录下所有 shard-*.json，与 login-net/after.md 的结论逐行比对：变了红的行，
变红的用例名也要相同。有任何不同退出 1。

@author Author
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
NET_SCRIPT = REPO / "design/evidence/2026-11-15/login-net/scripts/mutate_login.py"
AFTER_MD = REPO / "design/evidence/2026-11-15/login-net/after.md"

# 搬家后登录块的全部归属文件（函数名 → 文件，靠扫这些文件建表）
NEW_FILES = [
    "local/ui/features/login/state.js",
    "local/ui/features/login/view.js",
    "local/ui/features/login/actions.js",
    "local/ui/features/login/state-relogin.js",
    "local/ui/features/login/view-relogin.js",
    "local/ui/features/login/actions-relogin.js",
    "local/ui/views/result.js",
    "local/ui/views/log.js",
]

FUNC_RE = re.compile(r"^(?:export )?(?:async )?function ([A-Za-z0-9_]+)\(", re.M)
CONCLUSIONS = ("行为测试已守", "只有字面断言守", "没人守", "等价")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def name_to_file() -> dict[str, str]:
    """每个函数名在新的哪个文件里；同名出现在两个文件就报错，不猜。"""
    table: dict[str, str] = {}
    clash: list[str] = []
    for rel in NEW_FILES:
        text = (REPO / rel).read_bytes().decode("utf-8")
        for name in FUNC_RE.findall(text):
            if name in table and table[name] != rel:
                clash.append("%s：%s / %s" % (name, table[name], rel))
            table[name] = rel
    if clash:
        raise SystemExit("同名函数出现在两个新文件里：\n  " + "\n  ".join(clash))
    return table


def remapped_rows(mutate):
    """把 ROWS 里每行的文件换成函数所在的新文件，别的字段一个不动。"""
    table = name_to_file()
    rows = []
    missing = []
    for raw in mutate.ROWS:
        rid, table_name, rel, fn, old, new, nth, reuse, what = raw
        # 没搬的文件（顶栏登录卡、活动列表的刷新编排）保持原路径，原样再量一遍
        target = table.get(fn, rel)
        if not (REPO / target).exists():
            missing.append("%s %s::%s" % (rid, rel, fn))
            continue
        rows.append((rid, table_name, target, fn, old, new, nth, reuse, what))
    if missing:
        raise SystemExit("这些行在新位置找不到同名函数：\n  " + "\n  ".join(missing))
    return rows


def parse_after(path: Path) -> dict[str, dict]:
    """从 after.md 的表格里读每一行的结论与出处。定位列里有转义竖线，所以只按结论词切。"""
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*([JY]\d+)\s*\|", line)
        if not m:
            continue
        rid = m.group(1)
        hits = [c for c in CONCLUSIONS if c in line]
        if not hits:
            continue
        word = min(hits, key=lambda c: line.index(c))
        tail = line.split(word, 1)[1].lstrip(" |")
        out[rid] = {"conclusion": word, "source": tail.strip()}
    return out


def first_test_name(row: dict) -> str:
    failures = row.get("failures") or []
    if not failures:
        return ""
    return str(failures[0].get("test", ""))


def collect(folder: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for path in sorted(folder.glob("shard-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("rows", []):
            rows[row["id"]] = row
    return rows


def compare(folder: Path) -> int:
    after = parse_after(AFTER_MD)
    measured = collect(folder)
    problems: list[str] = []
    checked = 0
    for rid, want in sorted(after.items()):
        got = measured.get(rid)
        if got is None:
            problems.append("%s：没跑（结果里没有这一行）" % rid)
            continue
        checked += 1
        status = got.get("status", "")
        if status == "invalid":
            problems.append("%s：定位失败 %s" % (rid, got.get("detail", "")))
            continue
        want_killed = want["conclusion"] != "等价"
        got_killed = status == "killed"
        if want_killed != got_killed:
            problems.append("%s：搬之前「%s」，搬之后 %s"
                            % (rid, want["conclusion"], "变红" if got_killed else "没红"))
            continue
        if want_killed:
            name = first_test_name(got)
            if name and name not in want["source"]:
                problems.append("%s：变红的用例换了（搬之后 %s，after.md 写的是 %s）"
                                % (rid, name, want["source"][:60]))
    extra = sorted(set(measured) - set(after))
    if extra:
        problems.append("多出来的行：%s" % "、".join(extra))
    print("对照 %d 行，不同 %d 条" % (checked, len(problems)))
    for item in problems:
        print("  ", item)
    return 1 if problems else 0


def walk_tree(root: Path) -> list[str]:
    """导出树不是 git 仓库，make_copy 的清单改成遍历文件；口径（跳过哪些）与量具一致。"""
    skip = ("local/data/", "server/data/", "local/config.json", "server/config.json",
            "local/_site_build.py", "local/bin/")
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
        for name in filenames:
            rel = Path(dirpath, name).relative_to(root).as_posix()
            if rel.startswith(skip):
                continue
            out.append(rel)
    return out


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--compare":
        return compare(Path(argv[1]))
    tree = ""
    if "--tree" in argv:
        i = argv.index("--tree")
        tree = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    mutate = load_module(NET_SCRIPT, "mutate_login_for_move")
    if tree:
        # 拿开工 HEAD 的导出树当「搬之前」重跑同一批行：路径照旧，不换新位置
        mutate.REPO = Path(tree)
        mutate.git_files = walk_tree
    else:
        mutate.ROWS = remapped_rows(mutate)
    # 模块里的声明前面多了 export，量具的两个正则各放开一处，函数体的定位口径不变
    mutate.FUNC_RE = r"(?m)^(?:export )?(?:async )?function %s\("
    mutate.NEXT_FUNC_RE = r"(?m)^(?:export )?(?:async )?function "
    return mutate.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
