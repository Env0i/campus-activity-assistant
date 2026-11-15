# -*- coding: utf-8 -*-
"""新字段的十一条变异：在临时目录的仓库副本里逐条改一行，看哪条用例红。

量的单位是「这个字段的每一个取值来源」：每条变异按「文件、函数、那一行的
文字」定位（不按行号，定位不到或定位到多处都按失败报告），改完先过语法检查，
再只跑它对应的那个测试文件，记下变红的用例与首条失败断言。副本从 git ls-files
的清单复制（不带 local/data 与任何 config.json），仓库本体不动；每条变异只改
副本里的一个文件，跑完即从仓库本体还原，下一条从原始状态开始。

用法（仓库根）：python -B design/evidence/2026-11-15/backend-fields/scripts/mutate_fields.py
全部十一条都红在自己预期的用例上退出 0，否则退出 1。
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

MUTATIONS = [
    {
        "id": "m01-timeout-threshold-30-31",
        "desc": "组件超时阈值 30 改 31",
        "file": "local/domain/component_rules.py",
        "func": None,
        "find": ["COMPONENT_CHECK_TIMEOUT_S = 30"],
        "sub": ["COMPONENT_CHECK_TIMEOUT_S = 31"],
        "tests": ["test_component_rules.py"],
        "expect": "test_boundary_is_thirty_seconds_inclusive",
    },
    {
        "id": "m02-timeout-gte-to-gt",
        "desc": "check_timed_out 的「大于等于」改成「大于」",
        "file": "local/domain/component_rules.py",
        "func": "check_timed_out",
        "find": ["    return waited >= COMPONENT_CHECK_TIMEOUT_S"],
        "sub": ["    return waited > COMPONENT_CHECK_TIMEOUT_S"],
        "tests": ["test_component_rules.py"],
        "expect": "test_boundary_is_thirty_seconds_inclusive",
    },
    {
        "id": "m03-success-keeps-wait-start",
        "desc": "读成功后不清等锁起点",
        "file": "local/infrastructure/advanced_features.py",
        "func": "_frozen_package",
        "find": ["        _PACKAGE_CACHE[cache_key] = slim",
                 "        _LOCK_WAIT_START.pop(cache_key, None)"],
        "sub": ["        _PACKAGE_CACHE[cache_key] = slim"],
        "tests": ["test_advanced_features.py"],
        "expect": "test_successful_read_resets_the_wait_clock",
    },
    {
        "id": "m04-cached-wait-row-without-fields",
        "desc": "有缓存的等锁分支不带新字段",
        "file": "local/infrastructure/advanced_features.py",
        "func": "_frozen_package",
        "find": ["            payload = dict(cached, busy=True, lock_wait_s=lock_wait_s,",
                 "                           check_timed_out=check_timed_out(lock_wait_s))"],
        "sub": ["            payload = dict(cached, busy=True)"],
        "tests": ["test_advanced_features.py"],
        "expect": "test_cached_busy_row_also_carries_the_wait_fields",
    },
    {
        "id": "m05-drop-read-error-catch",
        "desc": "去掉读状态的读错捕获",
        "file": "local/infrastructure/advanced_features.py",
        "func": "_frozen_package",
        "find": ["    except (component_packages.PackageError, OSError, ValueError):"],
        "sub": ["    except ():"],
        "tests": ["test_advanced_features.py"],
        "expect": "test_read_error_without_cache_reports_checking_and_read_error",
    },
    {
        "id": "m06-error-no-cache-without-read-error",
        "desc": "读错且没缓存时不带 read_error",
        "file": "local/infrastructure/advanced_features.py",
        "func": "_frozen_package",
        "find": ["                \"busy\": True, \"checking\": True, \"read_error\": True}"],
        "sub": ["                \"busy\": True, \"checking\": True}"],
        "tests": ["test_advanced_features.py"],
        "expect": "test_read_error_without_cache_reports_checking_and_read_error",
    },
    {
        "id": "m07-authenticate-no-seen-at",
        "desc": "authenticate 校验通过不写 seen_at",
        "file": "local/application/phone_service.py",
        "func": "authenticate",
        "find": ["            session[\"seen_at\"] = now"],
        "sub": [],
        "tests": ["test_phone_service.py"],
        "expect": "test_a_later_visit_returns_to_connected_with_zero_ago",
    },
    {
        "id": "m08-restore-no-seen-at",
        "desc": "设备信任恢复建会话不写 seen_at",
        "file": "local/application/phone_service.py",
        "func": "authenticate_or_restore",
        "find": ["            self._sessions[token] = {\"csrf\": csrf, \"created_at\": now, \"seen_at\": now}"],
        "sub": ["            self._sessions[token] = {\"csrf\": csrf, \"created_at\": now}"],
        "tests": ["test_phone_service.py"],
        "expect": "test_device_restore_counts_as_a_visit",
    },
    {
        "id": "m09-idle-gte-to-gt",
        "desc": "断开阈值 120 的「大于等于」改成「大于」",
        "file": "local/domain/phone_rules.py",
        "func": "phone_link_state",
        "find": ["    return \"disconnected\" if ago >= PHONE_IDLE_DISCONNECT_S else \"connected\""],
        "sub": ["    return \"disconnected\" if ago > PHONE_IDLE_DISCONNECT_S else \"connected\""],
        "tests": ["test_phone_rules.py"],
        "expect": "test_two_idle_minutes_disconnect",
    },
    {
        "id": "m10-broken-clock-not-unknown",
        "desc": "时钟坏时不返回 unknown（谎报 off）",
        "file": "local/application/phone_service.py",
        "func": "link_status",
        "find": ["            return {\"link\": \"unknown\", \"last_contact_ago_s\": None}"],
        "sub": ["            return {\"link\": \"off\", \"last_contact_ago_s\": None}"],
        "tests": ["test_phone_service.py"],
        "expect": "test_clock_failure_reads_unknown_instead_of_raising",
    },
    {
        "id": "m11-app-drops-link-expansion",
        "desc": "app.py 去掉 link_status 的那一行展开",
        "file": "local/app.py",
        "func": "phone_access_state",
        "find": ["                **service.link_status(),"],
        "sub": [],
        "tests": ["test_application_services.py"],
        "expect": "test_phone_access_state_carries_the_link_fields_from_the_service",
    },
]

_EXC_RE = re.compile(r"^(AssertionError|KeyError|TypeError|AttributeError|OSError|"
                     r"ValueError|RuntimeError|NameError|IndexError|UnboundLocalError)\b")


def tracked_files():
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z"],
                         cwd=str(REPO), capture_output=True, check=True)
    keep = []
    for rel in out.stdout.decode("utf-8").split("\0"):
        if not rel:
            continue
        path = rel.replace("\\", "/")
        if path.endswith("/config.json") or path == "config.json":
            continue
        if path.startswith("local/data/") or path.startswith("server/data/"):
            continue
        keep.append(path)
    return keep


def make_copy(root: Path) -> None:
    for rel in tracked_files():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dst)
    copy_untracked_tests(root)


def copy_untracked_tests(root: Path) -> None:
    """local/tests 下还没入库的测试文件（新规则的单测）也一并带进副本。"""
    base = REPO / "local" / "tests"
    for src in base.rglob("*"):
        if not src.is_file() or "__pycache__" in src.parts or src.suffix == ".pyc":
            continue
        dst = root / src.relative_to(REPO)
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def function_span(lines, func):
    """函数体在文件里的行号范围（按 def 与下一个同级 def/class 之间）。"""
    if func is None:
        return 0, len(lines)
    start = None
    for i, text in enumerate(lines):
        if re.match(r"^\s*def\s+%s\s*\(" % re.escape(func), text):
            start = i
            break
    if start is None:
        raise LookupError("找不到函数 %s" % func)
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        text = lines[j]
        if not text.strip():
            continue
        cur = len(text) - len(text.lstrip())
        head = text.strip()
        if cur <= indent and (head.startswith("def ") or head.startswith("class ")):
            return start, j
    return start, len(lines)


def apply_mutation(root: Path, spec):
    path = root / spec["file"]
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines(keepends=True)
    stripped = [ln.rstrip("\r\n") for ln in lines]
    start, end = function_span(stripped, spec["func"])
    need = len(spec["find"])
    hits = []
    for i in range(start, min(end, len(stripped)) - need + 1):
        if all(stripped[i + k] == spec["find"][k] for k in range(need)):
            hits.append(i)
    if len(hits) != 1:
        raise LookupError("定位到 %d 处（应为 1）" % len(hits))
    i = hits[0]
    if spec["sub"]:
        lines[i:i + need] = [ln + "\n" for ln in spec["sub"]]
    else:
        del lines[i:i + need]
    path.write_text("".join(lines), encoding="utf-8", newline="")
    return i + 1


def syntax_problem(path: Path):
    try:
        compile(path.read_text(encoding="utf-8"), str(path.name), "exec")
    except SyntaxError as exc:
        return "SyntaxError: %s" % exc
    return ""


def first_failure_line(text):
    blocks = re.split(r"={20,}", text)
    for block in blocks[1:]:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        for ln in reversed(lines):
            if _EXC_RE.match(ln):
                return ln
        if lines:
            return lines[-1]
    return ""


def run_tests(root: Path, patterns):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    reds, first, code = [], "", 0
    for pattern in patterns:
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s",
             "local/tests", "-p", pattern],
            cwd=str(root), capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=env)
        code = proc.returncode or code
        text = (proc.stdout or "") + (proc.stderr or "")
        for match in re.finditer(r"^(?:FAIL|ERROR): (.+)$", text, re.M):
            name = match.group(1).split(" (")[0].strip()
            if name not in reds:
                reds.append(name)
        first = first or first_failure_line(text)
    return code, reds, first


def main():
    if not (REPO / "local" / "app.py").is_file():
        raise SystemExit("脚本要放在仓库内 design/evidence/ 下运行")
    root = Path(tempfile.mkdtemp(prefix="cfields-mut-"))
    print("副本：mkdtemp（仓库本体不动，路径不进报告）")
    make_copy(root)
    all_hit = True
    for spec in MUTATIONS:
        shutil.copyfile(REPO / spec["file"], root / spec["file"])
        print("=" * 8, spec["id"], "=" * 8)
        print("变异：%s（%s 的 %s）" % (spec["desc"], spec["file"], spec["func"] or "模块级"))
        try:
            line_no = apply_mutation(root, spec)
        except LookupError as exc:
            print("定位失败：%s" % exc)
            all_hit = False
            continue
        print("改了第 %d 行，语法检查……" % line_no)
        bad = syntax_problem(root / spec["file"])
        if bad:
            print("语法不过：%s" % bad)
            all_hit = False
            continue
        code, reds, first = run_tests(root, spec["tests"])
        hit = any(spec["expect"] in name for name in reds)
        all_hit = all_hit and bool(reds) and hit
        print("跑 %s：退出码 %d，变红 %d 条" % ("、".join(spec["tests"]), code, len(reds)))
        for name in reds:
            print("  红：%s" % name)
        if first:
            print("首条失败断言：%s" % first)
        print("预期用例（%s）红：%s" % (spec["expect"], "是" if hit else "否"))
        shutil.copyfile(REPO / spec["file"], root / spec["file"])
    print("=" * 30)
    print("结论：%s" % ("11/11 全部红在预期用例上" if all_hit else "有变异没红在预期用例上，逐条看上面输出"))
    return 0 if all_hit else 1


if __name__ == "__main__":
    sys.exit(main())
