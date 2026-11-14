#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 1 出口变异脚本（计划 20261113-refactor-step1-exit-tests）。

把 D2 表的 47 个桌面端「进行中」状态出口逐条做变异：在 tempfile.gettempdir()
下的仓库副本里，把那一处对该状态的赋值换成空语句，跑 D3 测试集合，
按 D1 认定变红的用例里哪些是行为测试，按 D4 给结论，输出 Markdown 表格。

仓库本体永不改动：所有读写在副本里进行。副本按 git ls-files
（已跟踪 + 未跟踪未忽略）复制，被忽略的文件一个都不带。
每条变异做之前先核对该行仍是对该状态的赋值，对不上就整体停下；
变异后先 node --check，语法不过的作废重做一次，再不过就记异常。

用法（仓库根执行，Python 一律带 -B）：
  基线（未变异，必须零失败）：
    python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py \
        --baseline --save-output <输出目录>
  全部 47 条或指定编号（可开最多四个副本并行，--shard 0..n 配 --shards n）：
    python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py \
        --phase 补之前 --out before.md --json before.json --save-output <目录>

不联网、不构建、不起真实窗口；测试集合固定为 D3（test_ui_*.py、
test_prerefactor_fixes.py、test_phone_ui.py 加本计划新建的四个文件）。

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

# D2 变异表，共 47 行。路径省略前缀 local/ui/；行号以 dddc179 为准，跑之前逐行核对。
EXITS = [
    ("L01", "登录·校验中", "controllers/refresh.js", 182, "refresh", "S.login.checking = false"),
    ("L02", "登录·校验中", "controllers/refresh.js", 217, "refresh", "S.login.checking = false"),
    ("L03", "登录·校验中", "controllers/refresh.js", 260, "settleSynchronous", "S.login.checking = false"),
    ("L04", "登录·校验中", "controllers/refresh.js", 315, "settleSynchronous", "S.login.checking = false"),
    ("L05", "登录·校验中", "controllers/refresh.js", 336, "settleSynchronous", "S.login.checking = false"),
    ("L06", "登录·校验中", "app.js", 107, "check 事件", "S.login.checking = false"),
    ("L07", "登录·浏览器登录窗口开着", "controllers/plan.js", 450, "doLogin", "S.login.loginPending = false"),
    ("L08", "登录·浏览器登录窗口开着", "controllers/plan.js", 457, "doLogin", "S.login.loginPending = false"),
    ("L09", "登录·浏览器登录窗口开着", "controllers/plan.js", 475, "doLogin", "S.login.loginPending = false"),
    ("L10", "登录·浏览器登录窗口开着", "controllers/plan.js", 488, "handleDone", "S.login.loginPending = false"),
    ("L11", "登录·已转人工", "state/login.js", 47, "setLogin", "S.login.handoff = false"),
    ("L12", "登录·已转人工", "views/relogin.js", 465, "receiveReloginState", "S.login.handoff = false"),
    ("L13", "登录·自动登录中", "state/login.js", 27, "reconcileAutoLogin", "S.autoLogin = false"),
    ("L14", "登录·自动登录中", "state/login.js", 29, "reconcileAutoLogin", "S.autoLogin = false"),
    ("L15", "登录·自动登录中", "views/relogin.js", 473, "receiveReloginState", "S.autoLogin = auto"),
    ("L16", "登录·重新登录对话框", "views/relogin.js", 346, "closeRelogin",
     'S.relogin = { open: false, step: "", flowId: "", challengeId: "" }'),
    ("P01", "计划栏·开始请求", "controllers/plan.js", 58, "startPlan", "S.starting = false"),
    ("P02", "计划栏·开始请求", "controllers/plan.js", 180, "reconcileStart", "S.starting = false"),
    ("P03", "计划栏·开始请求", "controllers/plan.js", 187, "reconcileStart", "S.starting = false"),
    ("P04", "计划栏·开始请求", "controllers/plan.js", 211, "adoptPlan", "S.starting = false"),
    ("P05", "计划栏·正在停止", "controllers/plan-events.js", 10, "presentPlanDone", "S.stopping = false"),
    ("P06", "计划栏·正在停止", "controllers/plan-events.js", 52, "handlePlanDone", "S.stopping = false"),
    ("P07", "计划栏·正在停止", "controllers/plan.js", 91, "startPlan", "S.stopping = false"),
    ("P08", "计划栏·正在停止", "controllers/plan.js", 244, "adoptPlan", "S.stopping = false"),
    ("P09", "计划栏·正在停止", "controllers/plan.js", 412, "doStopPlan", "S.stopping = false"),
    ("P10", "计划栏·修改中", "controllers/plan-events.js", 31, "presentPlanDone", "S.editing = null"),
    ("P11", "计划栏·修改中", "controllers/plan.js", 90, "startPlan", "S.editing = null"),
    ("P12", "计划栏·修改中", "controllers/plan.js", 413, "doStopPlan", "S.editing = null"),
    ("P13", "计划栏·修改中", "state/filters.js", 390, "clearSelection", "S.editing = null"),
    ("P14", "计划栏·修改中", "state/plan.js", 60, "handlePlan", "S.editing = null"),
    ("R01", "列表·加载中", "controllers/refresh.js", 197, "refresh", 'S.listState = "error"'),
    ("R02", "列表·加载中", "controllers/refresh.js", 238, "refresh", 'S.listState = "error"'),
    ("R03", "列表·加载中", "controllers/refresh.js", 288, "settleSynchronous", 'S.listState = "error"'),
    ("R04", "列表·加载中", "controllers/refresh.js", 322, "settleSynchronous", 'S.listState = "error"'),
    ("R05", "列表·加载中", "controllers/refresh.js", 350, "settleSynchronous", 'S.listState = "error"'),
    ("R06", "列表·加载中", "controllers/refresh.js", 483, "applyActivities", 'S.listState = "error"'),
    ("R07", "列表·加载中", "controllers/refresh.js", 503, "applyActivities", 'S.listState = "ready"'),
    ("R08", "列表·取消报名", "controllers/cancel.js", 37, "cancelSettle", 'S.cancel.busyId = ""'),
    ("C01", "组件·面板请求在途", "views/phone.js", 856, "enableFeature", "PhonePanel.busy = false"),
    ("C02", "组件·面板请求在途", "views/phone.js", 883, "toggleStart", "PhonePanel.busy = false"),
    ("C03", "组件·面板请求在途", "views/phone.js", 906, "toggleStop", "PhonePanel.busy = false"),
    ("C04", "组件·面板请求在途", "views/phone.js", 1022, "downloadComponent", "PhonePanel.busy = false"),
    ("C05", "组件·面板请求在途", "views/phone.js", 1111, "saveCredentials", "PhonePanel.busy = false"),
    ("C06", "组件·手机访问开启中或停止中", "views/phone.js", 882, "toggleStart", 'PhonePanel.pending = ""'),
    ("C07", "组件·手机访问开启中或停止中", "views/phone.js", 905, "toggleStop", 'PhonePanel.pending = ""'),
    ("C08", "组件·导入安装中", "views/phone.js", 820, "installComponent", "PhonePanel.installing[key] = false"),
    ("C09", "组件·验证码识别面板请求在途", "views/settings.js", 326, "enableOcr", "OcrPanel.busy = false"),
]

# D3 测试集合：test_ui_*.py（含本计划新建的四个）、test_prerefactor_fixes.py、test_phone_ui.py
TEST_PATTERNS = ("test_ui_*.py", "test_prerefactor_fixes.py", "test_phone_ui.py")
TEST_TIMEOUT_S = 900

SUBPROCESS_FNS = ("run", "Popen", "call", "check_output", "check_call")


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def git_commit(repo: Path) -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def copy_repo(repo: Path, dest: Path) -> int:
    """按 git ls-files（已跟踪 + 未跟踪未忽略）复制，被忽略的文件一个都不带。"""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                         cwd=repo, capture_output=True, check=True)
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    count = 0
    for rel in names:
        src = repo / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        count += 1
    return count


def verify_rows(repo: Path, rows) -> None:
    """每条变异做之前，核对该行在当前提交上仍是对该状态的赋值；对不上就停下。"""
    problems = []
    for (eid, _state, rel, line_no, _func, assign) in rows:
        text = (repo / "local" / "ui" / rel).read_text(encoding="utf-8")
        lines = text.splitlines()
        if line_no > len(lines) or assign not in lines[line_no - 1]:
            got = lines[line_no - 1] if line_no <= len(lines) else "<超出文件>"
            problems.append("%s %s:%d 期望含 %r，实际 %r" % (eid, rel, line_no, assign, got))
    if problems:
        raise SystemExit("D2 行核对不过，停下报告（不另找一处）：\n" + "\n".join(problems))


def node_check(path: Path) -> bool:
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node，无法做语法检查")
    res = subprocess.run([node, "--check", str(path)], capture_output=True, text=True)
    return res.returncode == 0


def run_tests(copy_root: Path) -> dict:
    """跑 D3 测试集合，返回 {total, failures, errors, skipped, ok, output, red}。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    total = fails = errs = skips = 0
    red = []
    chunks = []
    ok = True
    for pattern in TEST_PATTERNS:
        cmd = [sys.executable, "-B", "-m", "unittest", "discover",
               "-s", "local/tests", "-p", pattern, "-v"]
        try:
            res = subprocess.run(cmd, cwd=copy_root, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace",
                                 timeout=TEST_TIMEOUT_S, env=env)
        except subprocess.TimeoutExpired:
            ok = False
            chunks.append("[%s] 超时（>%ds）" % (pattern, TEST_TIMEOUT_S))
            continue
        text = (res.stdout or "") + "\n" + (res.stderr or "")
        chunks.append("[%s]\n%s" % (pattern, text))
        m = re.search(r"^Ran (\d+) tests? in", text, re.M)
        if m:
            total += int(m.group(1))
        sm = re.search(r"^FAILED \((.*)\)\s*$", text, re.M)
        if res.returncode != 0:
            ok = False
        if sm:
            for key, val in re.findall(r"(failures|errors|skipped)=(\d+)", sm.group(1)):
                if key == "failures":
                    fails += int(val)
                elif key == "errors":
                    errs += int(val)
                else:
                    skips += int(val)
        for line in text.splitlines():
            mm = re.match(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", line)
            if mm:
                red.append(mm.group(2) or mm.group(1))
    return {"total": total, "failures": fails, "errors": errs, "skipped": skips,
            "ok": ok, "output": "\n".join(chunks), "red": sorted(set(red))}


# ---------------------------------------------------------------- D1 行为测试认定
class ModuleInfo:
    """一个测试文件的 D1 认定：test_ 函数体里（ast）最终调到 run_js 或 subprocess 跑 node。"""

    def __init__(self, tests_dir: Path, name: str, loader):
        self.loader = loader
        self.path = tests_dir / (name + ".py")
        self.funcs: dict = {}
        self.classes: dict = {}
        self.imported: dict = {}
        self.behavioral: set = set()
        self._memo: set = set()
        tree = ast.parse(self.path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                self.funcs[node.name] = node
            elif isinstance(node, ast.ClassDef):
                self.classes[node.name] = node
            elif isinstance(node, ast.ImportFrom):
                self._note_import(node)
        for name in self.funcs:
            self.func_behavioral(name)

    def _note_import(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            local = alias.asname or alias.name
            if mod == "fixtures.ui_harness" and alias.name == "run_js":
                self.imported[local] = ("node", None)
            elif mod.startswith("test_"):
                self.imported[local] = ("mod", mod)

    def _calls_behavioral(self, fn, class_name, seen):
        """fn 体内（含嵌套函数）的调用是否最终落到 run_js / subprocess 跑 node。"""
        if id(fn) in seen:
            return False
        seen = seen | {id(fn)}
        local = {n.name: n for n in ast.walk(fn)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        has_subprocess = has_node = False
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if isinstance(f, ast.Name):
                name = f.id
                if name in local and self._calls_behavioral(local[name], class_name, seen):
                    return True
                if name in self.imported:
                    kind, mod = self.imported[name]
                    if kind == "node":
                        return True
                    other = self.loader(mod)
                    if other and name in other.funcs and other.func_behavioral(name):
                        return True
                if name in self.funcs and name not in local and self.func_behavioral(name):
                    return True
            elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                  and f.value.id in ("self", "cls") and class_name in self.classes):
                methods = {n.name: n for n in self.classes[class_name].body
                           if isinstance(n, ast.FunctionDef)}
                if f.attr in methods and self._calls_behavioral(methods[f.attr], class_name, seen):
                    return True
                if f.attr in self.funcs and self.func_behavioral(f.attr):
                    return True
            elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                  and f.value.id == "subprocess" and f.attr in SUBPROCESS_FNS):
                has_subprocess = True
            elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                  and f.value.id == "shutil" and f.attr == "which"
                  and any(isinstance(a, ast.Constant) and a.value == "node" for a in node.args)):
                has_node = True
        return has_subprocess and has_node

    def func_behavioral(self, name: str, seen=None) -> bool:
        if name in self.behavioral:
            return True
        if name in self._memo:
            return False
        self._memo.add(name)
        result = self._calls_behavioral(self.funcs[name], None, seen or frozenset())
        if result:
            self.behavioral.add(name)
        return result

    def test_behavioral(self, class_name: str, method_name: str) -> bool:
        if class_name and class_name in self.classes:
            methods = {n.name: n for n in self.classes[class_name].body
                       if isinstance(n, ast.FunctionDef)}
            if method_name in methods:
                return self._calls_behavioral(methods[method_name], class_name, frozenset())
            return False
        return method_name in self.funcs and self.func_behavioral(method_name)


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
    """按 D1 分：behavioral / literal。id 形如 module.Class.test 或 module.test。"""
    behavioral, literal = [], []
    for rid in red_ids:
        parts = rid.split(".")
        mod, rest = parts[0], parts[1:]
        info = load_test_module(tests_dir, cache, mod)
        if info is None:
            literal.append(rid)
            continue
        if len(rest) >= 2:
            cls, method = rest[-2], rest[-1]
        elif len(rest) == 1:
            cls, method = "", rest[0]
        else:
            literal.append(rid)
            continue
        (behavioral if info.test_behavioral(cls, method) else literal).append(rid)
    return behavioral, literal


# ---------------------------------------------------------------- 每条变异
def apply_mutation(copy_root: Path, rel: str, line_no: int, assign: str) -> tuple:
    """把那一处赋值换成空语句（同一行的其他语句和条件原样保留），返回 (原文本, 是否成功)。"""
    target = copy_root / "local" / "ui" / rel
    text = target.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    line = lines[line_no - 1]
    if assign not in line:
        return text, False
    lines[line_no - 1] = line.replace(assign, "", 1)
    target.write_text("".join(lines), encoding="utf-8")
    return text, node_check(target)


def conclusions_for(rows, copy_root: Path, tests_dir: Path, save_dir) -> list:
    cache: dict = {}
    results = []
    for (eid, state, rel, line_no, func, assign) in rows:
        target = copy_root / "local" / "ui" / rel
        original, syntax_ok = apply_mutation(copy_root, rel, line_no, assign)
        if not syntax_ok:
            log("[%s] 变异后语法不过或找不到赋值，作废重做一次" % eid)
            target.write_text(original, encoding="utf-8")
            original, syntax_ok = apply_mutation(copy_root, rel, line_no, assign)
        if not syntax_ok:
            results.append({"id": eid, "state": state, "where": "%s %s" % (rel, func),
                            "conclusion": "运行异常", "red": []})
            continue
        run = run_tests(copy_root)
        if save_dir is not None:
            (save_dir / ("mut-%s-output.txt" % eid)).write_text(run["output"], encoding="utf-8")
        behavioral, literal = classify_red(run["red"], tests_dir, cache)
        if not run["red"]:
            conclusion = "没人守"
        elif behavioral:
            conclusion = "行为测试已守"
        else:
            conclusion = "只有字面断言守"
        results.append({"id": eid, "state": state, "where": "%s %s" % (rel, func),
                        "conclusion": conclusion, "red": run["red"],
                        "behavioral": behavioral, "literal": literal,
                        "total": run["total"], "failures": run["failures"],
                        "errors": run["errors"], "skipped": run["skipped"],
                        "suite_ok": run["ok"]})
        log("[%s] %s 红=%d 行为=%d 字面=%d" % (eid, conclusion, len(run["red"]),
                                              len(behavioral), len(literal)))
        target.write_text(original, encoding="utf-8")   # 副本内还原，下一条不受影响
    return results


# ---------------------------------------------------------------- 输出
def write_markdown(out_path: Path, results, commit: str, phase: str) -> None:
    counts = {}
    for item in results:
        counts[item["conclusion"]] = counts.get(item["conclusion"], 0) + 1
    lines = [
        "# 步骤 1 出口变异结论表（%s）" % phase,
        "",
        "- 基线提交：`%s`（D2 行号以 dddc179 为准，脚本逐行核对通过）" % commit,
        "- 执行命令（仓库根，临时目录用占位符）：%s" % (
            "`python -B design/evidence/2026-11-13/exit-path-tests/scripts/mutate_exits.py"
            " --phase %s --out <表名>.md`" % phase),
        "- 测试集合（D3）：`test_ui_*.py`、`test_prerefactor_fixes.py`、`test_phone_ui.py`（含本计划新建文件）",
        "- 结论口径（D4）：变红用例按 D1 认定；「等价」由人工复判（D6），脚本只出前三类",
        "",
        "| 编号 | 状态 | 文件与函数 | 结论 | 变红的用例名 |",
        "|---|---|---|---|---|",
    ]
    for item in results:
        reds = item.get("behavioral") or item.get("literal") or item.get("red") or []
        shown = "、".join(reds[:3]) if item["conclusion"] == "行为测试已守" else "、".join(reds)
        if not reds:
            shown = "（无）"
        lines.append("| %s | %s | %s | %s | %s |" % (
            item["id"], item["state"], item["where"], item["conclusion"], shown))
    lines.append("")
    four = ["没人守", "只有字面断言守", "行为测试已守", "等价"]
    summary = "、".join("%s %d" % (k, counts.get(k, 0)) for k in four)
    extra = "、".join("%s %d" % (k, v) for k, v in sorted(counts.items()) if k not in four)
    if extra:
        summary += "、" + extra
    lines.append("汇总：%s（共 %d 行）" % (summary, len(results)))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    here = Path(__file__).resolve()
    repo_default = here.parents[5]
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(repo_default))
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--phase", default="补之前")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--save-output", default="")
    ap.add_argument("--keep-copy", action="store_true")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    copy_root = Path(tempfile.mkdtemp(prefix="exit-mut-"))
    n_files = copy_repo(repo, copy_root)
    log("副本 %s：%d 个文件" % (copy_root, n_files))
    rows = EXITS
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        rows = [r for r in EXITS if r[0] in wanted]
    if args.shards > 1:
        rows = [r for i, r in enumerate(EXITS) if i % args.shards == args.shard]
    verify_rows(repo, rows)
    tests_dir = copy_root / "local" / "tests"
    save_dir = Path(args.save_output) if args.save_output else None
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
    if args.baseline:
        run = run_tests(copy_root)
        if save_dir is not None:
            (save_dir / "baseline-output.txt").write_text(run["output"], encoding="utf-8")
        log("基线：%d 例，失败 %d，报错 %d，跳过 %d，ok=%s"
            % (run["total"], run["failures"], run["errors"], run["skipped"], run["ok"]))
        print(json.dumps(run, ensure_ascii=False))
        if not args.keep_copy:
            shutil.rmtree(copy_root, ignore_errors=True)
        return
    commit = git_commit(repo)
    results = conclusions_for(rows, copy_root, tests_dir, save_dir)
    if args.out:
        write_markdown(Path(args.out), results, commit, args.phase)
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    log("完成 %d 条" % len(results))
    if not args.keep_copy:
        shutil.rmtree(copy_root, ignore_errors=True)


if __name__ == "__main__":
    main()
