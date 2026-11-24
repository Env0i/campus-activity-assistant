#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记录并逐字段比对 test_grab_signup_retry 中全部 run_submit_loop 调用。

用法：
  python trace_submit_loop.py --repo <repo_dir> --out <trace.json>
  python trace_submit_loop.py --compare <before.json> <after.json>

只做离线替身录制，不写目标仓库，不读写真实 data/ 或配置。
@author Author
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

_SIGNUP_TIME_RE = re.compile(r"报名时间：\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def _normalize_notify_lines(lines):
    out = []
    for line in lines:
        out.append(_SIGNUP_TIME_RE.sub("报名时间：<TS>", str(line)))
    return out


def _load_test_module(repo_dir: Path):
    test_path = repo_dir / "server" / "tests" / "test_grab_signup_retry.py"
    scripts_lib = str(repo_dir / "server" / "scripts" / "lib")
    if scripts_lib not in sys.path:
        sys.path.insert(0, scripts_lib)
    spec = importlib.util.spec_from_file_location("test_grab_signup_retry_trace", test_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def record_traces(repo_dir: Path) -> list[dict]:
    temp_log = Path(tempfile.gettempdir()) / "trace_grab_signup_retry.log"
    old_log_env = os.environ.get("GRAB_LOG_FILE")
    os.environ["GRAB_LOG_FILE"] = str(temp_log)
    traces: list[dict] = []
    try:
        mod = _load_test_module(repo_dir)
        grab = mod.grab
        orig_run = grab.run_submit_loop

        def traced_run_submit_loop(*args, **kwargs):
            call_logs: list[str] = []
            call_notifies: list[dict] = []
            orig_log_fn = kwargs.get("log_fn")
            orig_notify_fn = kwargs.get("notify_fn")
            orig_mod_log = grab.log
            orig_mod_notify = grab.notify

            def wrapped_log(msg):
                call_logs.append(str(msg))
                if orig_log_fn is not None:
                    return orig_log_fn(msg)
                return orig_mod_log(msg)

            def wrapped_notify(title, lines, template="green"):
                call_notifies.append({
                    "title": str(title),
                    "lines": _normalize_notify_lines(lines),
                    "template": str(template),
                })
                if orig_notify_fn is not None:
                    return orig_notify_fn(title, lines, template)
                return orig_mod_notify(title, lines, template)

            new_kwargs = dict(kwargs)
            if orig_log_fn is not None:
                new_kwargs["log_fn"] = wrapped_log
            else:
                grab.log = wrapped_log
            if orig_notify_fn is not None:
                new_kwargs["notify_fn"] = wrapped_notify
            else:
                grab.notify = wrapped_notify

            try:
                stop_reason, state = orig_run(*args, **new_kwargs)
            finally:
                grab.log = orig_mod_log
                grab.notify = orig_mod_notify

            traces.append({
                "call_index": len(traces) + 1,
                "activity_id": kwargs.get("activity_id"),
                "stop_reason": stop_reason,
                "state": copy.deepcopy(state),
                "logs": call_logs,
                "notify": call_notifies,
            })
            return stop_reason, state

        grab.run_submit_loop = traced_run_submit_loop
        try:
            suite = unittest.defaultTestLoader.loadTestsFromModule(mod)
            result = unittest.TextTestRunner(stream=open(os.devnull, "w", encoding="utf-8"), verbosity=0).run(suite)
            if not result.wasSuccessful():
                raise RuntimeError(
                    f"test_grab_signup_retry failed: errors={len(result.errors)} failures={len(result.failures)}"
                )
        finally:
            grab.run_submit_loop = orig_run
    finally:
        if old_log_env is None:
            os.environ.pop("GRAB_LOG_FILE", None)
        else:
            os.environ["GRAB_LOG_FILE"] = old_log_env
        try:
            if temp_log.exists():
                temp_log.unlink()
        except OSError:
            pass
    return traces


def compare_traces(before_path: Path, after_path: Path) -> int:
    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))
    if not before:
        print("[diff] before trace is empty", file=sys.stderr)
        return 1
    if len(before) != len(after):
        print(f"[diff] call count mismatch: before={len(before)} after={len(after)}", file=sys.stderr)
        return 1
    for idx, (a, b) in enumerate(zip(before, after), start=1):
        if a != b:
            for key in ("activity_id", "stop_reason", "state", "logs", "notify"):
                if a.get(key) != b.get(key):
                    print(f"[diff] call #{idx} mismatch in {key}: before={a.get(key)!r} after={b.get(key)!r}",
                          file=sys.stderr)
                    return 1
            print(f"[diff] call #{idx} mismatch: before={a!r} after={b!r}", file=sys.stderr)
            return 1
    print(f"TRACE MATCH: total_calls={len(before)} matched={len(after)}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="Repo root directory to trace")
    ap.add_argument("--out", help="Output JSON path")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"), help="Compare two trace JSON files")
    args = ap.parse_args(argv)
    if args.compare:
        return compare_traces(Path(args.compare[0]), Path(args.compare[1]))
    if not args.repo or not args.out:
        ap.error("--repo and --out are required unless --compare is used")
    traces = record_traces(Path(args.repo).resolve())
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TRACE RECORDED: calls={len(traces)} out={out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
