#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件与手机访问安全网度量：认阶段、读进行中标志与使用点的变异结论表。

把 mutate_rows.py 里三组行清单加一组检查中场景探针逐条做变异：认阶段把带条件的分支整行
换成空语句、兜底行换返回字面量；读进行中标志与使用点把那一处读取换成空闲值（同一行有
两个变量就是两条变异）；检查中探针换掉 loading 认 checking 的那一项，单独计数。行按
「文件、函数、那一行的文字」定位（清单在 mutate_rows.py），不按行号——下一批要搬文件，
行号会变，文字不会。定位不到就整体停下报告，不猜。仓库本体永不改动：读写在 tempfile
下的仓库副本里进行，副本按 git ls-files（已跟踪 + 未跟踪未忽略）复制，config.json 与
local/data、server/data 下的文件不进副本。每条变异先 node --check 再跑相关测试（直接
断言这两个视图文件行为或文字的测试，加两个新测试文件；不存在就跳过），按「行为测试
已守 / 只有字面断言守 / 没人守」给结论并记录第一条失败断言原文——「跑 node 的用例」的
认定与 design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py 同一实现；
「等价」与「页面里没有这个元素」由人工复判（OVERRIDES），脚本机械地记「没人守」。
结论表多一列「有没有走整页清单的用例守着」：变红用例的调用链有没有最终调到 import
进来的 run_js（整页脚本清单，而不是按路径加载的辅助函数），有则指名第一条。
用法（仓库根执行，Python 一律带 -B）：--verify 只定位核对；--baseline 未变异基线；全部行或
指定编号可开最多四个副本并行（--shard 0..n 配 --shards n）；分片跑完用 --merge s0.json …合成一张表。
不联网、不构建、不起真实窗口。
@author Author
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from mutate_rows import OVERRIDES, ROWS

# 相关测试文件：直接断言这两个视图文件的行为（跑 node）或文字的测试，加两个新文件
# （存在才跑）。口径与理由写在证据目录的 README.md。
RELEVANT_FILES = (
    "test_phone_ui.py", "test_reason_maps.py", "test_ui_contract_components.py",
    "test_ui_contract_settings.py", "test_ui_contract_shell.py",
    "test_ui_exit_paths_components.py", "test_ui_reliability.py",
    "test_ui_component_rows.py", "test_ui_phone_access_rows.py")
TEST_TIMEOUT_S = 600
SUBPROCESS_FNS = ("run", "Popen", "call", "check_output", "check_call")
_DEF_RE = r"^\s*(?:async\s+)?(?:function\s+)?%s\s*\([^)]*\)\s*\{"
_CODE_LINE_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`|//[^\n]*|/\*.*?\*/', re.S)

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)

def git_commit(repo: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()

def copy_repo(repo: Path, dest: Path) -> int:
    """按 git ls-files（已跟踪 + 未跟踪未忽略）复制；config.json 与两个 data 目录不进副本。"""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                         cwd=repo, capture_output=True, check=True)
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    count = 0
    for rel in names:
        if "config.json" in rel or rel.startswith(("local/data/", "server/data/")):
            continue
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            count += 1
    return count

def _strip_strings_and_comments(line: str) -> str:
    """把字符串字面量、行注释与块注释抹成等长空白，供括号配对只看结构。"""
    return _CODE_LINE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), line)

def locate_function(text: str, name: str) -> tuple[int, int]:
    """函数名 -> (起始行号, 结束行号)，闭区间、1 起始。找不到或括号不闭合就报错。"""
    lines = text.splitlines()
    pat = re.compile(_DEF_RE % re.escape(name), re.M)
    start = None
    open_line = None
    depth = 0
    for idx, line in enumerate(lines):
        if start is None:
            m = pat.match(line)
            if m:
                start = open_line = idx
                stripped = _strip_strings_and_comments(line)
                depth = stripped.count("{") - stripped.count("}")
                if depth <= 0 and "{" in stripped:
                    return (idx + 1, idx + 1)
                if depth > 0:
                    continue
                continue
        else:
            stripped = _strip_strings_and_comments(line)
            depth += stripped.count("{") - stripped.count("}")
            if depth <= 0:
                return (open_line + 1, idx + 1)
    raise SystemExit("定位不到函数 %r（或括号不闭合），停下报告" % name)

def locate_row(root: Path, row) -> tuple[Path, int]:
    """按「文件、函数、那一行的文字」定位，返回（文件路径, 行下标 0 起始）。定位不到就停下。"""
    rel, func, line_text = row[2], row[3], row[4]
    path = root / "local" / "ui" / rel
    text = path.read_text(encoding="utf-8")
    start, end = locate_function(text, func)
    lines = text.splitlines()
    hits = [i for i in range(start - 1, end)
            if i < len(lines) and lines[i].strip() == line_text]
    if len(hits) != 1:
        got = "；".join(lines[i].strip() for i in hits[:3]) or "<没有这一行>"
        raise SystemExit("定位不到唯一一行：函数 %s（第 %d–%d 行）里与 %r 逐字相等的行有 %d 处（%s），停下报告"
                         % (func, start, end, line_text, len(hits), got))
    return path, hits[0]

def node_check(path: Path) -> bool:
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node，无法做语法检查")
    return subprocess.run([node, "--check", str(path)], capture_output=True,
                          text=True).returncode == 0

def mutate_text(text: str, idx: int, row) -> str | None:
    """在原文的第 idx 行上做这一条变异，返回新文本；做不了返回 None。"""
    kind, old, new = row[5], row[6], row[7]
    lines = text.splitlines(keepends=True)
    line = lines[idx]
    if line.strip() != row[4]:
        return None
    if kind == "blank":
        lines[idx] = ";" + line[len(line.rstrip("\r\n")):]
    elif line.count(old) == 1:
        lines[idx] = line.replace(old, new, 1)
    else:
        return None
    return "".join(lines)

def first_failure_detail(text: str, first_red_id: str) -> dict:
    """第一个变红用例的第一条失败断言：断言源码行与 AssertionError 原文。"""
    pat = re.compile(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", re.M)
    for m in pat.finditer(text):
        if first_red_id not in (m.group(1), m.group(2)):
            continue
        rest = text[m.end():]
        nxt = pat.search(rest)
        lines = (rest[:nxt.start()] if nxt else rest).splitlines()
        assert_src = ""
        assert_msg = ""
        for i, line in enumerate(lines):
            if "AssertionError" in line or ("Error" in line and ":" in line
                                            and re.match(r"^\w+(Error|Exception)", line.strip())):
                assert_msg = line.strip()
                for back in range(i - 1, max(i - 5, -1), -1):
                    cand = lines[back].strip()
                    if cand.startswith(("self.assert", "assert ")):
                        assert_src = cand
                        break
                break
        return {"test": first_red_id, "assert_src": assert_src, "assert_msg": assert_msg}
    return {"test": first_red_id, "assert_src": "", "assert_msg": ""}

def run_tests(copy_root: Path) -> dict:
    """跑相关测试文件，返回 {total, failures, errors, skipped, ok, output, red, first_fail}。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    stat = {"total": 0, "failures": 0, "errors": 0, "skipped": 0}
    red, chunks, ok, first_fail = [], [], True, None
    tests_dir = copy_root / "local" / "tests"
    for name in RELEVANT_FILES:
        if not (tests_dir / name).exists():
            chunks.append("[%s] 不存在，跳过" % name)
            continue
        cmd = [sys.executable, "-B", "-m", "unittest", "discover",
               "-s", "local/tests", "-p", name, "-v"]
        try:
            res = subprocess.run(cmd, cwd=copy_root, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=TEST_TIMEOUT_S, env=env)
        except subprocess.TimeoutExpired:
            ok = False
            chunks.append("[%s] 超时（>%ds）" % (name, TEST_TIMEOUT_S))
            continue
        text = (res.stdout or "") + "\n" + (res.stderr or "")
        chunks.append("[%s]\n%s" % (name, text))
        m = re.search(r"^Ran (\d+) tests? in", text, re.M)
        stat["total"] += int(m.group(1)) if m else 0
        if res.returncode != 0:
            ok = False
        sm = re.search(r"^FAILED \((.*)\)\s*$", text, re.M)
        for key, val in (re.findall(r"(failures|errors|skipped)=(\d+)", sm.group(1)) if sm else []):
            stat[key] += int(val)
        for line in text.splitlines():
            mm = re.match(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", line)
            if mm:
                red.append(mm.group(2) or mm.group(1))
        if red and first_fail is None:
            first_fail = first_failure_detail(text, red[0])
    return dict(stat, ok=ok, output="\n".join(chunks), red=sorted(set(red)),
                first_fail=first_fail)

# 行为测试认定与 design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py 同一
# 实现：test_ 函数体内（含经同类方法与同文件辅助函数传递）最终调到 fixtures/ui_harness.py
# 的 run_js，或同文件里最终用 subprocess 起 node 的辅助函数，才算行为测试。整页清单一列
# 在此基础上再分：能力集合里 "page" = 调用链最终调到 import 进来的 run_js（整页脚本清单），
# "sub" = 子进程起 node；行为测试 = 有 page 或 sub，整页清单 = 有 page。
class ModuleInfo:
    def __init__(self, tests_dir: Path, name: str, loader):
        self.loader = loader
        self.path = tests_dir / (name + ".py")
        self.funcs: dict = {}
        self.classes: dict = {}
        self.imported: dict = {}
        self._caps: dict = {}
        tree = ast.parse(self.path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
            elif isinstance(node, ast.ImportFrom):
                self._note_import(node)
        for name in self.funcs:
            self.func_caps(name)

    def _note_import(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            if mod == "fixtures.ui_harness" and alias.name == "run_js":
                self.imported[local] = ("node", None)
            elif mod.startswith("test_"):
                self.imported[local] = ("mod", mod)

    def _collect(self, fn, class_name, seen) -> set:
        """这个函数（含调用链）的执行能力：page=走整页清单的 run_js；sub=子进程起 node。"""
        if id(fn) in seen:
            return set()
        seen = seen | {id(fn)}
        caps = set()
        local = {n.name: n for n in ast.walk(fn)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        sub = node_ok = False
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Name):
                name = f.id
                if name in local:
                    caps |= self._collect(local[name], class_name, seen)
                elif name in self.imported:
                    kind, mod = self.imported[name]
                    if kind == "node":
                        caps.add("page")
                    else:
                        other = self.loader(mod)
                        if other and name in other.funcs:
                            caps |= other.func_caps(name)
                elif name in self.funcs:
                    caps |= self.func_caps(name)
            elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)):
                owner, attr = f.value.id, f.attr
                if owner in ("self", "cls") and class_name in self.classes:
                    methods = {n.name: n for n in self.classes[class_name].body
                               if isinstance(n, ast.FunctionDef)}
                    if attr in methods:
                        caps |= self._collect(methods[attr], class_name, seen)
                    elif attr in self.funcs:
                        caps |= self.func_caps(attr)
                elif owner == "subprocess" and attr in SUBPROCESS_FNS:
                    sub = True
                elif owner == "shutil" and attr == "which" and any(
                        isinstance(a, ast.Constant) and a.value == "node" for a in node.args):
                    node_ok = True
        if sub and node_ok:
            caps.add("sub")
        return caps

    def func_caps(self, name: str, seen=None) -> set:
        if name in self._caps:
            return self._caps[name]
        self._caps[name] = set()          # 先占位防环，真有环时按无能力算
        result = self._collect(self.funcs[name], None, seen or frozenset())
        self._caps[name] = result
        return result

    def _pick(self, class_name: str, method_name: str):
        if class_name and class_name in self.classes:
            methods = {n.name: n for n in self.classes[class_name].body
                       if isinstance(n, ast.FunctionDef)}
            return methods.get(method_name)
        return self.funcs.get(method_name)

    def _caps_of(self, class_name: str, method_name: str) -> set | None:
        fn = self._pick(class_name, method_name)
        if fn is None:
            return None
        return self._collect(fn, class_name, frozenset()) if class_name \
            else self.func_caps(method_name)

    def test_behavioral(self, class_name: str, method_name: str) -> bool:
        caps = self._caps_of(class_name, method_name)
        return bool(caps) and bool(caps & {"page", "sub"})

    def test_page(self, class_name: str, method_name: str) -> bool:
        caps = self._caps_of(class_name, method_name)
        return bool(caps) and "page" in caps

def load_test_module(tests_dir: Path, cache: dict, name: str):
    if name in cache:
        return cache[name]
    if not (tests_dir / (name + ".py")).exists():
        cache[name] = None
        return None
    info = ModuleInfo(tests_dir, name, lambda n: load_test_module(tests_dir, cache, n))
    cache[name] = info
    return info

def classify_red(red_ids, tests_dir: Path, cache: dict) -> tuple:
    behavioral, literal, page = [], [], []
    for rid in red_ids:
        parts = rid.split(".")
        mod, rest = parts[0], parts[1:]
        info = load_test_module(tests_dir, cache, mod)
        if info is None:
            literal.append(rid)
            continue
        if not rest:
            literal.append(rid)
            continue
        cls, method = (rest[-2], rest[-1]) if len(rest) >= 2 else ("", rest[0])
        if info.test_behavioral(cls, method):
            behavioral.append(rid)
            if info.test_page(cls, method):
                page.append(rid)
        else:
            literal.append(rid)
    return behavioral, literal, page

def conclusions_for(rows, copy_root: Path, tests_dir: Path, save_dir) -> list:
    cache: dict = {}
    results = []
    # 每条变异各自定位（同一文件有多行要变异）；原样文本按文件缓存：变异从原文做，
    # 做完按原文还原，下一条不受上一条影响，也不会把已变异的文本误当原样备份。
    located: dict = {}
    originals: dict = {}
    for row in rows:
        path, idx = locate_row(copy_root, row)
        located[row[0]] = (path, idx)
        originals.setdefault(row[2], path.read_text(encoding="utf-8"))
    for row in rows:
        rid, rel = row[0], row[2]
        path, idx = located[rid]
        original = originals[rel]
        mutated = mutate_text(original, idx, row)
        syntax_ok = False
        if mutated is not None:
            path.write_text(mutated, encoding="utf-8")
            syntax_ok = node_check(path)
        if not syntax_ok:
            path.write_text(original, encoding="utf-8")
            results.append({"id": rid, "desc": row[1], "group": row[8],
                            "where": "%s %s" % (rel, row[3]), "conclusion": "运行异常",
                            "red": [], "page": [], "first_fail": None})
            log("[%s] 变异失败或语法不过，记运行异常" % rid)
            continue
        run = run_tests(copy_root)
        if save_dir is not None:
            (save_dir / ("mut-%s-output.txt" % rid)).write_text(run["output"], encoding="utf-8")
        behavioral, literal, page = classify_red(run["red"], tests_dir, cache)
        conclusion = ("没人守" if not run["red"]
                      else "行为测试已守" if behavioral else "只有字面断言守")
        results.append({"id": rid, "desc": row[1], "group": row[8],
                        "where": "%s %s" % (rel, row[3]), "conclusion": conclusion,
                        "red": run["red"], "behavioral": behavioral, "literal": literal,
                        "page": page, "first_fail": run["first_fail"], "suite_ok": run["ok"],
                        "total": run["total"], "failures": run["failures"],
                        "errors": run["errors"], "skipped": run["skipped"]})
        ff = run["first_fail"] or {}
        log("[%s] %s 红=%d 行为=%d 字面=%d 整页=%s 先红=%s" %
            (rid, conclusion, len(run["red"]), len(behavioral), len(literal),
             page[0] if page else "否", ff.get("test", "")))
        path.write_text(original, encoding="utf-8")   # 副本内按原文还原，下一条不受影响
    return results

def write_markdown(out_path: Path, results, commit: str, phase: str, title: str) -> None:
    counts = {}
    groups = {}
    for item in results:
        name = OVERRIDES.get(item["id"], item["conclusion"])
        counts[name] = counts.get(name, 0) + 1
        groups[item["group"]] = groups.get(item["group"], 0) + 1
    lines = [
        "# %s（%s）" % (title, phase),
        "",
        "- 基线提交：`%s`（行按「文件、函数、那一行的文字」定位，清单在 scripts/mutate_rows.py）" % commit,
        "- 执行命令（仓库根，临时目录用占位符）：`python -B"
        " design/evidence/2026-11-14/components-net/scripts/mutate_reads.py"
        " --phase %s --title %s --out <表名>.md`" % (phase, title),
        "- 测试集合：直接断言这两个视图文件行为或文字的相关测试文件（清单见 README.md），加两个新测试文件",
        "- 结论口径：变红用例里至少一条跑 node 的用例即「行为测试已守」，全是字面断言即「只有"
        "字面断言守」，没有用例变红即「没人守」；「等价」与「页面里没有这个元素」由人工复判"
        "（mutate_rows.py 的 OVERRIDES）；整页清单一列看变红用例里有没有走整页脚本清单的，有则指名",
        "",
        "| 编号 | 一行是什么 | 文件与函数 | 结论 | 有没有走整页清单的用例守着 | 变红的用例名（最多三条） | 先红用例的第一条失败断言 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in results:
        reds = item.get("behavioral") or item.get("literal") or item.get("red") or []
        shown = "、".join(reds[:3]) if reds else "（无）"
        page_red = item.get("page") or []
        page_cell = ("是（%s）" % page_red[0]) if page_red else "否"
        ff = item.get("first_fail") or {}
        src = ff.get("assert_src", "")
        detail = ("`%s` → %s" % (src, ff.get("assert_msg", ""))) if src else (
            ff.get("assert_msg", "") or "（无）")
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            item["id"], item["desc"], item["where"],
            OVERRIDES.get(item["id"], item["conclusion"]), page_cell, shown, detail))
    lines.append("")
    four = ["没人守", "只有字面断言守", "行为测试已守", "等价"]
    ordered = four + sorted(k for k in counts if k not in four)
    summary = "、".join("%s %d" % (k, counts[k]) for k in ordered if counts.get(k))
    gsum = "、".join("%s %d" % (k, v) for k, v in groups.items())
    lines.append("汇总：%s（共 %d 行，其中 %s）" % (summary, len(results), gsum))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

def verify_rows(repo: Path, rows) -> None:
    for row in rows:
        path, idx = locate_row(repo, row)
        line = path.read_text(encoding="utf-8").splitlines()[idx]
        log("定位 %s → %s:%d %s" % (row[0], row[2], idx + 1, line.strip()))

def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(here.parents[5]))
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--phase", default="补测试之前")
    ap.add_argument("--title", default="认阶段与读进行中标志的变异结论表")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--save-output", default="")
    ap.add_argument("--merge", nargs="+", default=[])
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    if args.merge:
        order = {row[0]: i for i, row in enumerate(ROWS)}
        results = [r for name in args.merge
                   for r in json.loads(Path(name).read_text(encoding="utf-8"))]
        results.sort(key=lambda item: order.get(item["id"], len(order)))
        write_markdown(Path(args.out), results, git_commit(repo), args.phase, args.title)
        log("合并 %d 条 → %s" % (len(results), args.out))
        return
    rows = ROWS
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        rows = [r for r in ROWS if r[0] in wanted]
        if len(rows) != len(wanted):
            raise SystemExit("编号对不上表，停下报告：缺 %s"
                             % sorted(wanted - {r[0] for r in rows}))
    if args.shards > 1:
        rows = [r for i, r in enumerate(rows) if i % args.shards == args.shard]
    if args.verify:
        verify_rows(repo, rows)
        return
    copy_root = Path(tempfile.mkdtemp(prefix="read-mut-"))
    log("副本 %s：%d 个文件" % (copy_root, copy_repo(repo, copy_root)))
    if args.baseline:
        run = run_tests(copy_root)
        log("基线：%d 例，失败 %d，报错 %d，跳过 %d，ok=%s"
            % (run["total"], run["failures"], run["errors"], run["skipped"], run["ok"]))
        print(json.dumps({k: v for k, v in run.items() if k != "output"}, ensure_ascii=False))
        shutil.rmtree(copy_root, ignore_errors=True)
        return
    verify_rows(repo, rows)          # 变异之前逐行核对定位
    commit = git_commit(repo)
    save_dir = Path(args.save_output) if args.save_output else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
    results = conclusions_for(rows, copy_root, copy_root / "local" / "tests", save_dir)
    if args.out:
        write_markdown(Path(args.out), results, commit, args.phase, args.title)
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    log("完成 %d 条" % len(results))
    shutil.rmtree(copy_root, ignore_errors=True)

if __name__ == "__main__":
    main()
