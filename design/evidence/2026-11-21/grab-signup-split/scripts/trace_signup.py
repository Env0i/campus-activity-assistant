#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cmd_grab 对照录制与逐调用比对脚本（独立工具，不被任何测试 import）。

在给定的仓库副本目录里运行 test_worker_boundaries.py 与 test_retry_policy.py，
对副本里的 grab.cmd_grab 包一层，逐次调用记录：
- case_id：所属 unittest 用例 id
- call_index：该用例内第几次调用（从 1 开始）
- exit_code：cmd_grab 返回值
- stdout：调用期间写到 sys.stdout 的全部文字
- logs：调用期间经 grab.log 写出的每一行
- posts：调用期间经 grab._post 发出的每次请求 {"path": ..., "at": ...}
- elapsed_s：调用前后 grab.time.monotonic() 之差（四舍五入到 6 位小数）

16 位十六进制运行标识（如 a1b2c3d4e5f60718-1 或 a1b2c3d4e5f60718-pre1）
在标准化时替换为固定占位 <RUN_ID>，避免 os.urandom(8).hex() 造成假差异。

@author Author
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SUITE_FILES = ("test_worker_boundaries.py", "test_retry_policy.py")
# 匹配 direct["run_id"] 生成的 16 位小写 hex 票据前缀（<16hex>-<digits> 或 <16hex>-pre<digits>）
_RUN_ID_RE = re.compile(r"\b[0-9a-f]{16}(?=-(?:pre)?\d+\b)")


class _TeeStdout(io.TextIOBase):
    """在转发给原 stdout（如 run_worker 的 redirect_stdout 缓冲）的同时录下一份副本。"""

    def __init__(self, target, capture: io.StringIO):
        self._target = target
        self._capture = capture

    def write(self, s):
        text = str(s)
        self._capture.write(text)
        if self._target is not None:
            return self._target.write(text)
        return len(text)

    def flush(self):
        if self._target is not None and hasattr(self._target, "flush"):
            self._target.flush()


def normalize_text(text: str) -> str:
    return _RUN_ID_RE.sub("<RUN_ID>", str(text))


def normalize_record(rec: dict) -> dict:
    return {
        "case_id": rec["case_id"],
        "call_index": rec["call_index"],
        "exit_code": rec["exit_code"],
        "stdout": normalize_text(rec["stdout"]),
        "logs": [normalize_text(line) for line in rec["logs"]],
        "posts": [
            {
                "path": normalize_text(p["path"]),
                "at": round(float(p["at"]), 6) if isinstance(p.get("at"), (int, float)) else p.get("at"),
            }
            for p in rec["posts"]
        ],
        "elapsed_s": round(float(rec["elapsed_s"]), 6),
    }


def _clock_now(grab_mod):
    try:
        return round(float(grab_mod.time.time()), 6)
    except Exception:
        return None


def _run_worker_in_copy(copy_root: Path, out_json: Path) -> int:
    """在子进程中切到副本目录跑两份测试并写录制 JSON。"""
    for k in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy"):
        os.environ.pop(k, None)
    local_dir = copy_root / "local"
    tests_dir = local_dir / "tests"
    sys.path.insert(0, str(tests_dir))
    sys.path.insert(0, str(local_dir))
    os.chdir(copy_root)

    import grab  # type: ignore

    records = []
    current_case = {"id": "<unknown>", "seq": 0}
    orig_cmd_grab = grab.cmd_grab

    def traced_cmd_grab(args):
        current_case["seq"] += 1
        call_idx = current_case["seq"]
        case_id = current_case["id"]
        call_logs = []
        call_posts = []
        stdout_buf = io.StringIO()

        prev_log = grab.log
        prev_post = grab._post

        def wrapped_log(msg):
            call_logs.append(str(msg))
            return prev_log(msg)

        def wrapped_post(path, payload=None, tok=None, timeout=None, budget=None):
            call_posts.append({"path": str(path), "at": _clock_now(grab)})
            return prev_post(path, payload=payload, tok=tok, timeout=timeout, budget=budget)

        grab.log = wrapped_log
        grab._post = wrapped_post
        prev_stdout = sys.stdout
        sys.stdout = _TeeStdout(prev_stdout, stdout_buf)
        t0 = float(grab.time.monotonic())
        try:
            code = orig_cmd_grab(args)
        finally:
            t1 = float(grab.time.monotonic())
            sys.stdout = prev_stdout
            grab.log = prev_log
            grab._post = prev_post

        records.append(normalize_record({
            "case_id": case_id,
            "call_index": call_idx,
            "exit_code": code,
            "stdout": stdout_buf.getvalue(),
            "logs": call_logs,
            "posts": call_posts,
            "elapsed_s": round(t1 - t0, 6),
        }))
        return code

    grab.cmd_grab = traced_cmd_grab

    class TracingResult(unittest.TextTestResult):
        def startTest(self, test):
            current_case["id"] = test.id()
            current_case["seq"] = 0
            super().startTest(test)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for fname in SUITE_FILES:
        suite.addTests(loader.discover(start_dir=str(tests_dir), pattern=fname))

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=TracingResult)
    result = runner.run(suite)

    payload = {
        "copy_root": str(copy_root.name),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "total_calls": len(records),
        "records": records,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not result.wasSuccessful():
        sys.stderr.write(stream.getvalue()[-4000:])
        return 1
    return 0


def record_in_subprocess(copy_root: Path, out_json: Path) -> dict:
    cmd = [
        sys.executable, "-B", str(Path(__file__).resolve()),
        "--worker-copy", str(copy_root.resolve()),
        "--out", str(out_json.resolve()),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("录制失败 (exit=%d):\n%s\n%s" % (proc.returncode, proc.stdout, proc.stderr))
    return json.loads(out_json.read_text(encoding="utf-8"))


def _diff_fields(a: dict, b: dict) -> list[str]:
    diffs = []
    for key in ("exit_code", "stdout", "logs", "posts", "elapsed_s"):
        if a.get(key) != b.get(key):
            diffs.append(key)
    return diffs


def _multiset_equal(a: dict, b: dict) -> bool:
    if a.get("exit_code") != b.get("exit_code"):
        return False
    if collections.Counter(a.get("logs", [])) != collections.Counter(b.get("logs", [])):
        return False
    if collections.Counter(a.get("stdout", "").splitlines()) != collections.Counter(b.get("stdout", "").splitlines()):
        return False
    posts_a = collections.Counter((p["path"], p["at"]) for p in a.get("posts", []))
    posts_b = collections.Counter((p["path"], p["at"]) for p in b.get("posts", []))
    return posts_a == posts_b


def compare_traces(trace_a: dict, trace_b: dict, nondeterministic_keys: set[str] | None = None) -> dict:
    recs_a = {"%s#%d" % (r["case_id"], r["call_index"]): r for r in trace_a["records"]}
    recs_b = {"%s#%d" % (r["case_id"], r["call_index"]): r for r in trace_b["records"]}
    keys_a = list(recs_a.keys())
    keys_b = list(recs_b.keys())
    nondet = nondeterministic_keys or set()

    only_a = [k for k in keys_a if k not in recs_b]
    only_b = [k for k in keys_b if k not in recs_a]
    exact_equal = 0
    multiset_equal_nondet = 0
    mismatches = []

    for key in keys_a:
        if key not in recs_b:
            continue
        ra, rb = recs_a[key], recs_b[key]
        fields = _diff_fields(ra, rb)
        if not fields:
            exact_equal += 1
        elif key in nondet and _multiset_equal(ra, rb):
            multiset_equal_nondet += 1
        else:
            mismatches.append({
                "call_key": key,
                "diff_fields": fields,
                "in_nondet": key in nondet,
                "multiset_equal": _multiset_equal(ra, rb),
            })

    return {
        "total_a": len(keys_a),
        "total_b": len(keys_b),
        "only_in_a": only_a,
        "only_in_b": only_b,
        "exact_equal": exact_equal,
        "multiset_equal_nondet": multiset_equal_nondet,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="cmd_grab 对照录制与逐调用比对")
    ap.add_argument("--worker-copy", help="内部子进程入口：在指定副本目录内执行录制")
    ap.add_argument("--out", help="输出 JSON 文件路径")
    ap.add_argument("--self-compare-copy", help="对同一副本录两遍并输出自比报告")
    ap.add_argument("--compare", nargs=2, metavar=("HEAD_JSON", "NEW_JSON"), help="比对两份录制 JSON")
    ap.add_argument("--nondet-json", help="自比报告 JSON（读取其中的不确定调用名单）")
    args = ap.parse_args()

    if args.worker_copy:
        if not args.out:
            ap.error("--worker-copy 需要配合 --out")
        return _run_worker_in_copy(Path(args.worker_copy), Path(args.out))

    if args.self_compare_copy:
        copy_dir = Path(args.self_compare_copy)
        out_dir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="trace-head-"))
        out_dir.mkdir(parents=True, exist_ok=True)
        r1_path = out_dir / "head-run1.json"
        r2_path = out_dir / "head-run2.json"
        t1 = record_in_subprocess(copy_dir, r1_path)
        t2 = record_in_subprocess(copy_dir, r2_path)
        cmp_res = compare_traces(t1, t2)
        nondet_calls = [m for m in cmp_res["mismatches"]]
        report = {
            "total_calls_run1": t1["total_calls"],
            "total_calls_run2": t2["total_calls"],
            "exact_equal": cmp_res["exact_equal"],
            "nondeterministic_count": len(nondet_calls),
            "nondeterministic_calls": nondet_calls,
        }
        report_path = out_dir / "head-self-compare.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.compare:
        t_head = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        t_new = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        nondet = set()
        if args.nondet_json:
            nd_data = json.loads(Path(args.nondet_json).read_text(encoding="utf-8"))
            nondet = {item["call_key"] for item in nd_data.get("nondeterministic_calls", [])}
        res = compare_traces(t_head, t_new, nondet)
        if args.out:
            Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if (res["mismatch_count"] == 0 and not res["only_in_a"] and not res["only_in_b"]) else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
