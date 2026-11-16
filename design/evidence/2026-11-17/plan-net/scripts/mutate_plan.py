#!/usr/bin/env python3
"""按计划栏指定函数枚举并执行行为变异：只在临时目录的仓库副本里改产品文件。

定位一律按「文件、函数、那一行的文字、第几次出现」，不按行号；全部候选都跑，
不抽样；一条候选跑五个计划测试文件，第一个变红的文件即停。

用法（从仓库根执行）：
  python -B design/evidence/2026-11-17/plan-net/scripts/mutate_plan.py --list
  python -B design/evidence/2026-11-17/plan-net/scripts/mutate_plan.py --precheck
  python -B design/evidence/2026-11-17/plan-net/scripts/mutate_plan.py [--workers 4] [--out FILE]
  python -B design/evidence/2026-11-17/plan-net/scripts/mutate_plan.py --only M012 [--tests a.py,b.py] [-v]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]

# 五个计划测试文件：按这个顺序跑，第一个变红就停跑这一条
PATTERNS = (
    "test_ui_plan_flow.py",
    "test_ui_plan_board.py",
    "test_ui_exit_paths_plan.py",
    "test_ui_main_window_plan.py",
    "test_ui_contract_plan.py",
)
MUTATED_FILES = (
    "local/ui/views/plan-panel.js",
    "local/ui/state/plan.js",
    "local/ui/state/task-display.js",
    "local/ui/controllers/plan.js",
    "local/ui/controllers/tick.js",
)

# 范围：plan-panel 只取点名的函数；state/plan、state/task-display、controllers/plan 取全部函数；
# controllers/tick 只取读忙态与编辑态的几处读取（不取它的条件与三元，那些不在本轮范围里）。
PLAN_FUNCS = {
    "local/ui/views/plan-panel.js": (
        "paintSelected", "selectionSummary", "boardPlanState", "paintBoardState", "runTagText",
        "runHeadKey", "runCaption", "setBoardTag", "paintBoardActions", "editNoteText",
        "paintEditNote", "resultMode", "boardTargetItem", "startBlocker", "paintWhy", "planLate",
        "paintRunPanel", "verifyTask", "resultCounts", "resultView", "reselectableIds",
        "paintResultPanel", "paintPlan", "stopReasonText", "taskHtml", "updateControls",
    ),
    "local/ui/state/plan.js": None,
    "local/ui/state/task-display.js": None,
    "local/ui/controllers/plan.js": None,
    "local/ui/controllers/tick.js": ("tick",),
}
READ_ONLY_FILES = {"local/ui/controllers/tick.js"}

FLAG_FIELDS = ("busy", "starting", "stopping", "editing", "startRequest", "verifyAsked")
BOOLEAN_FLAGS = ("busy", "starting", "stopping", "editing", "verifyAsked")
START_REQUEST_FIELDS = {
    "id": '"__other__"',
    "state": '"settled"',
    "gen": "-1",
    "reconcile": "8",
    "timer": "0",
    "queryTimer": "0",
}
# 挑文字或按钮的运算符才取：整条候选里至少带引号文案、或读界面上的显隐/计数/状态
SHORT_CIRCUIT_HINTS = ("S.", "'", '"', "disabled", "hidden", "length", "tasks", "items",
                       "selected", "status", "name", "text", "count")


@dataclass
class Candidate:
    path: str
    function: str
    kind: str
    needle: str
    occurrence: int
    replacement: str
    line_text: str
    offset: int = 0
    index: int = 0

    @property
    def cid(self) -> str:
        return f"M{self.index:03d}"

    @property
    def label(self) -> str:
        return f"{self.path}:{self.function}:{self.line_text}（第 {self.occurrence + 1} 次）"

    def as_dict(self) -> dict:
        return {"id": self.cid, "path": self.path, "function": self.function,
                "kind": self.kind, "needle": self.needle, "occurrence": self.occurrence,
                "replacement": self.replacement, "line_text": self.line_text}


class LocatorError(RuntimeError):
    pass


# ---------------------------------------------------------------- 源码定位

def mask_source(text: str) -> str:
    """把注释与字符串内容换成空格（长度与换行不变），用于找结构；取值仍回到原文。"""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif ch == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif ch in "\"'`":
            quote = ch
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            for k in range(i + 1, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        else:
            i += 1
    return "".join(out)


def function_ranges(text: str, masked: str) -> list[tuple[str, int, int]]:
    pattern = re.compile(r"(?m)^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{")
    out = []
    for match in pattern.finditer(masked):
        depth = 0
        end = len(masked)
        i = match.end() - 1
        while i < len(masked):
            char = masked[i]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        out.append((match.group(1), match.start(), end))
    return out


def line_of(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    end = len(text) if end < 0 else end
    return text[start:end].strip()


def depth_span(masked: str, open_at: int) -> int:
    """从 ( 开始找配对的 )，返回 ) 的下标；找不到返回 -1。"""
    depth = 0
    for i in range(open_at, len(masked)):
        if masked[i] == "(":
            depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def left_operand(masked: str, pos: int) -> int:
    depth = 0
    i = pos - 1
    while i >= 0:
        char = masked[i]
        if char in ")]}":
            depth += 1
        elif char in "([{":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and char in ",;=?:&|+*/%<>":
            break
        i -= 1
    return i + 1


def right_operand(masked: str, pos: int) -> int:
    depth = 0
    i = pos
    while i < len(masked):
        char = masked[i]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif depth == 0 and char in ",;?:&|":
            break
        i += 1
    return i


def add_candidate(items: list[Candidate], path: str, function: str, body: str, masked: str,
                  kind: str, needle: str, replacement: str, at: int) -> None:
    if not needle or needle == replacement:
        return
    occurrence = body.count(needle, 0, at)
    items.append(Candidate(path, function, kind, needle, occurrence, replacement, line_of(body, at), at))


def condition_candidates(path: str, function: str, body: str, masked: str,
                         items: list[Candidate]) -> None:
    for match in re.finditer(r"\bif\s*\(", masked):
        start = match.start()
        prefix = masked[:start]
        wider = re.search(r"else\s+$", prefix)
        replacement = "if (false)"
        if wider:
            start = wider.start()
            replacement = "else if (false)"
        open_at = match.end() - 1
        close_at = depth_span(masked, open_at)
        if close_at < 0:
            continue
        add_candidate(items, path, function, body, masked, "条件-恒假",
                      body[start:close_at + 1], replacement, start)


def ternary_candidates(path: str, function: str, body: str, masked: str,
                       items: list[Candidate]) -> None:
    for i, char in enumerate(masked):
        if char != "?":
            continue
        before = masked[i - 1] if i else " "
        after = masked[i + 1] if i + 1 < len(masked) else " "
        if before in "?." or after in "?.":
            continue
        depth = 0
        nested = 0
        colon = -1
        j = i + 1
        while j < len(masked):
            ch = masked[j]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and ch == "?" and masked[j + 1] != "." and masked[j - 1] != "?":
                nested += 1
            elif depth == 0 and ch == ":":
                if nested:
                    nested -= 1
                else:
                    colon = j
                    break
            j += 1
        if colon < 0:
            continue
        end = right_operand(masked, colon + 1)
        a_text = body[i + 1:colon]
        b_text = body[colon + 1:end]
        needle = body[i:end]
        replacement = "?" + b_text + ":" + a_text
        add_candidate(items, path, function, body, masked, "三元-对调", needle, replacement, i)


def short_circuit_candidates(path: str, function: str, body: str, masked: str,
                             items: list[Candidate]) -> None:
    for match in re.finditer(r"&&|\|\|", masked):
        if masked[match.start():match.start() + 3] in ("&&=", "||="):
            continue
        left_at = left_operand(masked, match.start())
        right_at = right_operand(masked, match.end())
        left = body[left_at:match.start()]
        right = body[match.end():right_at]
        if not left.strip() or not right.strip():
            continue
        needle = body[left_at:right_at]
        if not any(hint in needle for hint in SHORT_CIRCUIT_HINTS):
            continue
        add_candidate(items, path, function, body, masked, "短路-去右侧", needle, left, left_at)


def field_candidates(path: str, function: str, body: str, masked: str,
                     items: list[Candidate]) -> None:
    for flag in BOOLEAN_FLAGS:
        token = "S." + flag
        for match in re.finditer(re.escape(token), masked):
            tail = masked[match.end():match.end() + 8]
            if re.match(r"\s*=(?!=)", tail):
                continue
            if re.match(r"[A-Za-z0-9_$]", tail[:1]):
                continue
            add_candidate(items, path, function, body, masked, f"读 {token}",
                          body[match.start():match.end()], "false", match.start())
    token = "S.startRequest"
    for match in re.finditer(re.escape(token), masked):
        rest = masked[match.end():]
        if re.match(r"\s*=(?!=)", rest):
            continue
        if rest.startswith("."):
            name = re.match(r"\.([A-Za-z_$][\w$]*)", rest)
            if not name:
                continue
            field_name = name.group(1)
            if field_name not in START_REQUEST_FIELDS:
                continue
            end = match.end() + name.end()
            add_candidate(items, path, function, body, masked,
                          f"读 {token}.{field_name}", body[match.start():end],
                          START_REQUEST_FIELDS[field_name], match.start())
            continue
        add_candidate(items, path, function, body, masked, f"读 {token}",
                      body[match.start():match.end()], "null", match.start())


def build_candidates() -> tuple[list[Candidate], dict]:
    items: list[Candidate] = []
    stats = {"scanned_functions": {}, "skipped_functions": {}}
    for path, allowed in PLAN_FUNCS.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        masked = mask_source(text)
        ranges = function_ranges(text, masked)
        scoped = [item for item in ranges if allowed is None or item[0] in allowed]
        stats["scanned_functions"][path] = [item[0] for item in scoped]
        stats["skipped_functions"][path] = [item[0] for item in ranges if item not in scoped]
        read_only = path in READ_ONLY_FILES
        for function, start, end in scoped:
            body = text[start:end]
            body_mask = masked[start:end]
            first = len(items)
            if read_only:
                field_candidates(path, function, body, body_mask, items)
            else:
                condition_candidates(path, function, body, body_mask, items)
                ternary_candidates(path, function, body, body_mask, items)
                short_circuit_candidates(path, function, body, body_mask, items)
                field_candidates(path, function, body, body_mask, items)
            for item in items[first:]:
                item.offset += start
                if item.index == 0:
                    item.line_text = line_of(text, item.offset)
    ordered = sorted(items, key=lambda item: (list(PLAN_FUNCS).index(item.path), item.offset,
                                              item.occurrence))
    unique: list[Candidate] = []
    seen = set()
    for item in ordered:
        key = (item.path, item.function, item.kind, item.needle, item.occurrence)
        if key in seen:
            continue
        seen.add(key)
        unique.append(Candidate(item.path, item.function, item.kind, item.needle,
                                item.occurrence, item.replacement, item.line_text,
                                item.offset, index=len(unique) + 1))
    return unique, stats


# ---------------------------------------------------------------- 副本与执行

def copy_base(dest: Path) -> None:
    from importlib.util import module_from_spec, spec_from_file_location
    script = ROOT / "design/evidence/2026-11-16/login-machine/scripts/capsule_grid.py"
    spec = spec_from_file_location("capsule_grid", script)
    grid = module_from_spec(spec)
    spec.loader.exec_module(grid)
    grid.copy_current(dest)
    for rel in ("local/tests/test_ui_plan_board.py", "local/tests/test_ui_plan_flow.py"):
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)


def locate(text: str, candidate: Candidate) -> tuple[int, int, int]:
    masked = mask_source(text)
    ranges = {name: (start, end) for name, start, end in function_ranges(text, masked)}
    if candidate.function not in ranges:
        raise LocatorError(f"函数不存在：{candidate.function}")
    start, end = ranges[candidate.function]
    body = text[start:end]
    at = -1
    cursor = 0
    for _ in range(candidate.occurrence + 1):
        at = body.find(candidate.needle, cursor)
        if at < 0:
            raise LocatorError(f"第 {candidate.occurrence + 1} 次命中不到：{candidate.needle[:60]}")
        cursor = at + len(candidate.needle)
    return start, end, at


def apply_candidate(root: Path, candidate: Candidate) -> None:
    path = root / candidate.path
    text = path.read_text(encoding="utf-8")
    start, end, at = locate(text, candidate)
    body = text[start:end]
    mutated = body[:at] + candidate.replacement + body[at + len(candidate.needle):]
    path.write_text(text[:start] + mutated + text[end:], encoding="utf-8", newline="")


def restore(root: Path, base: Path) -> None:
    for rel in MUTATED_FILES:
        (root / rel).write_bytes((base / rel).read_bytes())


def run_suite(root: Path, patterns: tuple[str, ...], verbose: bool = False) -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    for pattern in patterns:
        try:
            proc = subprocess.run(
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", pattern],
                cwd=root, env=env, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "file": pattern, "test": "", "message": "单个测试文件 120 秒未结束"}
        if proc.returncode == 0:
            continue
        output = proc.stdout + proc.stderr
        head = re.search(r"^(?:FAIL|ERROR):\s+(\S+)", output, re.MULTILINE)
        frames = re.findall(r'File "([^"]+local/tests/[^"]+)", line (\d+), in (\w+)', output)
        assertion = ""
        if frames:
            tail = output.split('File "%s"' % frames[-1][0], 1)[-1]
            lines = [line.strip() for line in tail.splitlines() if line.strip()]
            if len(lines) > 1:
                assertion = lines[1][:160]
        message = ""
        for line in reversed([line.strip() for line in output.splitlines() if line.strip()]):
            if line.startswith(("AssertionError", "TypeError", "ReferenceError", "SyntaxError",
                                "KeyError", "AttributeError", "ValueError", "NameError")):
                message = line[:200]
                break
        result = {"status": "red", "file": pattern,
                  "test": head.group(1) if head else "unknown",
                  "assertion": assertion, "message": message}
        if verbose:
            result["output"] = output[-4000:]
        return result
    return {"status": "green"}


def syntax_ok(root: Path, candidate: Candidate) -> tuple[bool, str]:
    """改完先过 node --check：语法错会让整页起不来，那样变红不算行为被守。"""
    node = shutil.which("node")
    if not node:
        return True, ""
    proc = subprocess.run([node, "--check", str(root / candidate.path)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode == 0:
        return True, ""
    lines = [line for line in (proc.stderr or "").splitlines() if line.strip()]
    return False, (lines[-1][:200] if lines else "语法检查失败")


def worker(index: int, candidates: list[Candidate], base: Path, temp: Path) -> list[dict]:
    root = temp / f"worker-{index}"
    copy_base(root)
    results = []
    for candidate in candidates:
        try:
            apply_candidate(root, candidate)
        except LocatorError as exc:
            results.append({"id": candidate.cid, "status": "locator_error", "message": str(exc)})
            restore(root, base)
            continue
        ok, message = syntax_ok(root, candidate)
        if not ok:
            results.append({"id": candidate.cid, "status": "syntax_error", "message": message})
            print(f"[w{index}] {candidate.cid} syntax_error {candidate.function}", flush=True)
            restore(root, base)
            continue
        outcome = run_suite(root, PATTERNS)
        results.append({"id": candidate.cid, **outcome})
        print(f"[w{index}] {candidate.cid} {outcome['status']} {candidate.kind} "
              f"{candidate.path.split('/')[-1]}:{candidate.function}", flush=True)
        restore(root, base)
    return results


def precheck(candidates: list[Candidate]) -> int:
    failures = 0
    for candidate in candidates:
        text = (ROOT / candidate.path).read_text(encoding="utf-8")
        try:
            start, end, at = locate(text, candidate)
        except LocatorError as exc:
            print(f"{candidate.cid} 定位失败：{exc}")
            failures += 1
            continue
        body = text[start:end]
        if body.count(candidate.needle) <= candidate.occurrence:
            print(f"{candidate.cid} 命中次数不足")
            failures += 1
        hit = body[at:at + len(candidate.needle)] == candidate.needle
        if not hit:
            print(f"{candidate.cid} 命中位置不符")
            failures += 1
    print(f"定位自检：{len(candidates)} 条，失败 {failures} 条")
    return 0 if failures == 0 else 1


def run_all(candidates: list[Candidate], workers: int, out: Path | None) -> int:
    results: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="plan-net-rework2-") as temp_name:
        temp = Path(temp_name)
        base = temp / "base"
        base.mkdir()
        copy_base(base)
        shards: list[list[Candidate]] = [[] for _ in range(workers)]
        for position, candidate in enumerate(candidates):
            shards[position % workers].append(candidate)
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(worker, index, shard, base, temp)
                       for index, shard in enumerate(shards) if shard]
            for future in futures:
                results.extend(future.result())
    retry = [item for item in results if item["status"] == "timeout"]
    if retry:
        by_id = {candidate.cid: candidate for candidate in candidates}
        with tempfile.TemporaryDirectory(prefix="plan-net-rework2-retry-") as temp_name:
            temp = Path(temp_name)
            base = temp / "base"
            base.mkdir()
            copy_base(base)
            root = temp / "retry"
            copy_base(root)
            for item in retry:
                candidate = by_id[item["id"]]
                try:
                    apply_candidate(root, candidate)
                except LocatorError as exc:
                    item.update(status="locator_error", message=str(exc))
                    restore(root, base)
                    continue
                item.update(run_suite(root, PATTERNS))
                restore(root, base)
    counts: dict[str, int] = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    summary = {"candidate_count": len(candidates), "status_counts": counts, "results": results}
    payload = json.dumps(summary, ensure_ascii=False, indent=1)
    if out:
        out.write_text(payload, encoding="utf-8", newline="")
    print(json.dumps({"candidate_count": len(candidates), "status_counts": counts},
                     ensure_ascii=False))
    return 0 if not any(item["status"] in {"timeout", "locator_error"} for item in results) else 1


def run_one(candidates: list[Candidate], cid: str, patterns: tuple[str, ...], verbose: bool) -> int:
    chosen = [candidate for candidate in candidates if candidate.cid == cid]
    if not chosen:
        print(f"没有这个候选：{cid}")
        return 2
    candidate = chosen[0]
    with tempfile.TemporaryDirectory(prefix="plan-net-one-") as temp_name:
        temp = Path(temp_name)
        base = temp / "base"
        base.mkdir()
        copy_base(base)
        root = temp / "one"
        copy_base(root)
        apply_candidate(root, candidate)
        outcome = run_suite(root, patterns, verbose=verbose)
    print(json.dumps({"candidate": candidate.as_dict(), **outcome}, ensure_ascii=False, indent=1))
    return 0 if outcome["status"] == "red" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="只列出候选，不跑")
    parser.add_argument("--precheck", action="store_true", help="只在原仓库自检定位，不跑测试")
    parser.add_argument("--only", default="", help="只跑一条候选，给编号")
    parser.add_argument("--tests", default="", help="配合 --only：逗号分隔的测试文件名")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（试跑用）")
    parser.add_argument("--out", default="")
    parser.add_argument("--json", action="store_true", help="--list 时输出 JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    candidates, stats = build_candidates()
    if args.list:
        if args.json:
            print(json.dumps({"candidate_count": len(candidates), "stats": stats,
                              "candidates": [item.as_dict() for item in candidates]},
                             ensure_ascii=False, indent=1))
        else:
            for item in candidates:
                print(f"{item.cid}\t{item.path}\t{item.function}\t{item.kind}\t"
                      f"第{item.occurrence + 1}次\t{item.line_text[:70]}")
            print(f"共 {len(candidates)} 条")
            for path in PLAN_FUNCS:
                scanned = stats["scanned_functions"][path]
                skipped = stats["skipped_functions"][path]
                print(f"  {path}: 扫 {len(scanned)} 个函数，略过 {len(skipped)} 个"
                      f"（{', '.join(skipped) if skipped else '无'}）")
        return 0
    if args.precheck:
        return precheck(candidates)
    if args.only:
        patterns = tuple(item.strip() for item in args.tests.split(",") if item.strip()) or PATTERNS
        return run_one(candidates, args.only, patterns, args.verbose)
    out = Path(args.out) if args.out else None
    if args.limit:
        candidates = candidates[:args.limit]
    return run_all(candidates, max(1, args.workers), out)


if __name__ == "__main__":
    raise SystemExit(main())
