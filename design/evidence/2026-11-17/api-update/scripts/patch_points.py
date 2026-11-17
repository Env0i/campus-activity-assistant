# -*- coding: utf-8 -*-
"""P4 注入点核对：列出更新相关测试打的每一个补丁在新代码里的调用点，
再对每个补丁做两条变异，两条都必须让打这个补丁的用例变红。

两条变异只差「替身绑在哪一刻」：
- A 调用点：把 Api 转发方法传给服务的那个端口换成抛错替身；
  用例变红说明补丁确实要经过这个调用点才生效。
- B 构造时：同一个抛错替身改成在 Api 构造时就绑死（`self._mut_x`），
  转发方法读 `self._mut_x`；用例变红说明端口现在必须是调用时取——
  若真在构造时绑死，用例在构造之后打的补丁就再也顶不上去。

基线（不改任何东西时这 12 个用例全绿）证明补丁被认；A 全红证明补丁经过调用点；
B 全红证明端口不能提前绑。三条合起来就是「端口在调用时取」的证据。

变异在 app.py 的临时副本上做：跑完立刻按原字节写回并核对 SHA-256，工作区不留改动。

用法：
  python design/evidence/<日期>/api-update/scripts/patch_points.py           全部点
  python ... --list                                                        只列清单
  python ... --only updater.stage_update                                   只跑一个点
  python ... --out points-report.txt                                       同时写报告
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

APP_REL = Path("local/app.py")
TESTS_REL = Path("local") / "tests"

# 变异用的端口替身；A 插在调用点前，B 插在 class Api 前
HELPER = '''def _mutant_port(name):
    """变异用端口替身：一被调用就抛错。"""

    def boom(*args, **kwargs):
        raise RuntimeError("mutant port " + name)

    return boom


'''

# UpdateService 在 Api.__init__ 里的构造结尾；B 在它后面插绑死那一行
ANCHOR = "            is_closing=self._update_is_closing)\n"

# 表里每一项：补丁打在谁身上、测试里怎么打、转发方法的哪个参数是它的落点
POINTS = [
    {
        "key": "app.check_latest_release",
        "expr": "fetch=check_latest_release",
        "attr": "fetch",
        "patched_by": 'patch.object(local_app, "check_latest_release")',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_check_stores_installer_and_clears_old_download"],
    },
    {
        "key": "app.threading.Thread",
        "expr": "thread_factory=threading.Thread",
        "attr": "thread",
        "patched_by": 'patch.object(local_app.threading, "Thread")',
        "tests": ["test_update_check.UpdateBridgeTests.test_immediate_ack_single_flight"],
    },
    {
        "key": "app.updater.cleanup_staging",
        "expr": "cleanup_staging=updater.cleanup_staging",
        "attr": "cleanup_staging",
        "patched_by": 'patch.object(local_app.updater, "cleanup_staging")',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_new_check_reclaims_stale_version_staging"],
    },
    {
        "key": "app.version_switch_available",
        "expr": "version_switch_available=version_switch_available",
        "attr": "switch",
        "patched_by": 'patch.object(local_app, "version_switch_available", new=...)',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_version_payload_cleans_archive_after_staging"],
    },
    {
        "key": "app.update_version_paths",
        "expr": "update_version_paths=update_version_paths",
        "attr": "paths",
        "patched_by": 'patch.object(local_app, "update_version_paths", return_value=paths)',
        "tests": ["test_application_services.VersionSwitchLaunchTests"
                  ".test_launcher_started_publishes_started_text_and_schedules_exit"],
    },
    {
        "key": "app.updater.stage_update",
        "expr": "stage_update=updater.stage_update",
        "attr": "stage",
        "patched_by": 'patch.object(local_app.updater, "stage_update", return_value=...)',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_version_payload_cleans_archive_after_staging"],
    },
    {
        "key": "app.updater.download_payload",
        "expr": "download_payload=updater.download_payload",
        "attr": "payload",
        "patched_by": 'patch.object(local_app.updater, "download_payload", return_value=...)',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_version_payload_cleans_archive_after_staging"],
    },
    {
        "key": "app.updater.download_installer",
        "expr": "download_installer=updater.download_installer",
        "attr": "installer",
        "patched_by": 'patch.object(local_app.updater, "download_installer", ...)',
        "tests": ["test_update_check.UpdateBridgeTests.test_download_progress_and_ready_state"],
    },
    {
        "key": "app.updater.cleanup_download",
        "expr": "cleanup_download=updater.cleanup_download",
        "attr": "cleanup_download",
        "patched_by": 'patch.object(local_app.updater, "cleanup_download")',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_version_payload_cleans_archive_after_staging"],
    },
    {
        "key": "app.updater.launch_installer",
        "expr": "launch_installer=updater.launch_installer",
        "attr": "launch_installer",
        "patched_by": 'patch.object(local_app.updater, "launch_installer", return_value=...)',
        "tests": ["test_update_check.UpdateBridgeTests"
                  ".test_launch_publishes_launching_then_success"],
    },
    {
        "key": "app.subprocess.Popen",
        "expr": "spawn=subprocess.Popen",
        "attr": "spawn",
        "patched_by": 'patch.object(local_app.subprocess, "Popen", popen)',
        "tests": ["test_application_services.VersionSwitchLaunchTests"
                  ".test_launcher_started_publishes_started_text_and_schedules_exit"],
    },
    {
        "key": "app.defer_close_action",
        "expr": "defer_close=defer_close_action",
        "attr": "defer_close",
        "patched_by": 'patch.object(local_app, "defer_close_action", lambda ...)',
        "tests": ["test_application_services.VersionSwitchLaunchTests"
                  ".test_launcher_started_publishes_started_text_and_schedules_exit"],
    },
]


# ───────────────────────── 清单 ─────────────────────────

def _enclosing(text: str):
    """行号 → (类, 函数)：拿每行所属的最内层定义，用来写「哪个函数里取的端口」。"""
    tree = ast.parse(text)
    spans: list[tuple[int, int, str, str]] = []

    def walk(node, cls: str, fn: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                spans.append((child.lineno, child.end_lineno, child.name, ""))
                walk(child, child.name, "")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                spans.append((child.lineno, child.end_lineno, cls, child.name))
                walk(child, cls, child.name)
            else:
                walk(child, cls, fn)

    walk(tree, "", "")
    return spans


def call_sites(text: str, expr: str) -> list[tuple[int, str]]:
    """表达式在 app.py 里出现的每一处：(行号, 类.函数)。"""
    spans = _enclosing(text)
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if expr not in line:
            continue
        best = ("", "")
        best_span = 10 ** 9
        for start, end, cls, fn in spans:
            if start <= number <= end and (end - start) < best_span:
                best, best_span = (cls, fn), end - start
        name = ".".join(part for part in best if part) or "<module>"
        rows.append((number, name))
    return rows


def print_inventory(text: str, points: list[dict]) -> None:
    print("更新相关补丁 → 新代码里的调用点")
    print("=" * 78)
    for point in points:
        sites = call_sites(text, point["expr"])
        print("\n%s" % point["key"])
        print("  测试里怎么打：%s" % point["patched_by"])
        print("  用来验的用例：%s" % "、".join(point["tests"]))
        if not sites:
            print("  !! 调用点没找到：%r 不在 app.py 里" % point["expr"])
            continue
        for number, where in sites:
            print("  调用点：local/app.py:%d  %s  →  %s" % (number, where, point["expr"]))


# ───────────────────────── 变异 ─────────────────────────

def _compile(text: str, label: str) -> str:
    try:
        compile(text, label, "exec")
    except SyntaxError as exc:  # 变异写坏了要当场停，不能拿坏文件去跑用例
        raise SystemExit("变异后语法错误（%s）：%s" % (label, exc))
    return text


def mutate(text: str, point: dict, kind: str) -> str:
    """返回变异后的 app.py 全文；kind 为 A（调用点）或 B（构造时）。"""
    expr, key = point["expr"], point["key"]
    param = expr.split("=", 1)[0]
    if text.count(expr) < 1:
        raise SystemExit("变异打空：%r 不在 app.py 里" % expr)
    out = text.replace("class Api:", HELPER + "class Api:", 1)
    if kind == "A":
        stub = '%s=_mutant_port("%s")' % (param, key)
        return _compile(out.replace(expr, stub), "A %s" % key)
    bind = '        self._mut_%s = _mutant_port("%s")\n' % (point["attr"], key)
    if out.count(ANCHOR) != 1:
        raise SystemExit("绑死插入点不唯一：%r" % ANCHOR)
    out = out.replace(ANCHOR, ANCHOR + bind)
    stub = "%s=self._mut_%s" % (param, point["attr"])
    return _compile(out.replace(expr, stub), "B %s" % key)


def run_tests(repo: Path, tests: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-B", "-m", "unittest", "-q", *tests]
    try:
        proc = subprocess.run(cmd, cwd=str(repo / TESTS_REL), capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        return 124, "用例超过 600 秒没跑完"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def verdict(output: str) -> str:
    """从 unittest 输出里挑一行说明为什么红。"""
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if stripped.startswith(("AssertionError", "RuntimeError", "TypeError", "NameError",
                                "AttributeError", "KeyError", "ValueError")):
            return stripped[:160]
        if stripped.startswith("FAILED (") or stripped.startswith("Ran "):
            continue
    return ""


def run_point(repo: Path, text: str, point: dict) -> list[tuple[str, int, str]]:
    """一个补丁跑两条变异；返回 [(变异, 退出码, 说明)]。"""
    results = []
    for kind in ("A", "B"):
        mutated = mutate(text, point, kind)
        target = repo / APP_REL
        before = target.read_bytes()
        try:
            target.write_bytes(mutated.encode("utf-8"))
            code, output = run_tests(repo, point["tests"])
        finally:
            target.write_bytes(before)
        results.append((kind, code, verdict(output) if code else ""))
        print("  变异 %s（%s）：退出码 %d  %s"
              % (kind, "调用点换抛错替身" if kind == "A" else "构造时绑死",
                 code, "变红 ✓" if code else "仍然全绿 ✗"))
        if code:
            print("    %s" % verdict(output))
    return results


# ───────────────────────── 主流程 ─────────────────────────

class _Tee:
    """一份输出写两处：屏幕与 --out 指定的文件。"""

    def __init__(self, screen, stream):
        self._screen, self._stream = screen, stream

    def write(self, text):
        self._screen.write(text)
        self._stream.write(text)

    def flush(self):
        self._screen.flush()
        self._stream.flush()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="P4 注入点核对与两条变异")
    parser.add_argument("--repo", default=None, help="仓库根（默认按脚本位置推）")
    parser.add_argument("--only", default=None, help="只跑一个补丁，取 POINTS 的 key")
    parser.add_argument("--list", action="store_true", help="只列清单，不做变异")
    parser.add_argument("--out", default=None, help="报告另存一份到这个路径")
    args = parser.parse_args(argv)
    if args.out:
        # 报告同时进文件：屏幕上的输出与文件内容一致，不用事后手抄
        stream = open(args.out, "w", encoding="utf-8", newline="\n")
        sys.stdout = _Tee(sys.stdout, stream)

    # 脚本在 design/evidence/<日期>/api-update/scripts/ 下：往上 5 层是仓库根
    repo = Path(args.repo).resolve() if args.repo else Path(__file__).resolve().parents[5]
    app = repo / APP_REL
    if not app.exists():
        print("找不到 %s；用 --repo 指定仓库根。" % app, file=sys.stderr)
        return 2
    text = app.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # 只报目录名，不把本机绝对路径写进证据
    print("仓库：%s（工作副本根，下面路径都相对它）" % repo.name)
    print("app.py SHA-256（改前）：%s" % digest)
    print()

    points = [p for p in POINTS if args.only in (None, p["key"])]
    if not points:
        print("--only 没匹配到任何补丁：%s" % args.only, file=sys.stderr)
        return 2
    print_inventory(text, points)
    if args.list:
        return _done(0)

    print()
    print("两条变异（A 调用点换抛错替身 / B 构造时绑死）；每条都必须让用例变红")
    print("=" * 78)
    survived = []
    for point in points:
        print("\n%s  ← %s" % (point["key"], point["patched_by"]))
        for kind, code, why in run_point(repo, text, point):
            if not code:
                survived.append((point["key"], kind))

    after = hashlib.sha256(app.read_bytes()).hexdigest()
    print()
    print("app.py SHA-256（改后）：%s" % after)
    print("工作区复原：%s" % ("一致 ✓" if after == digest else "不一致 ✗"))
    print()
    if survived:
        print("有 %d 条变异没让用例变红，注入点核对不通过：" % len(survived))
        for key, kind in survived:
            print("  - %s 的变异 %s" % (key, kind))
        return _done(1)
    print("全部 %d 个补丁 × 2 条变异都让对应用例变红（共 %d 条）。"
          % (len(points), 2 * len(points)))
    return _done(0 if after == digest else 1)


def _done(code: int) -> int:
    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
