#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学校请求层与日志层对照录制与逐字段比对脚本（独立工具，不被任何测试 import）。

在给定仓库副本里导入 grab，按固定输入依次录制三类外部可观测行为：
1. HTTP 请求与返回：替换 _school_open、_request_nonce、time、token 后调用 _post / _get，
   记录每个发出请求的 full_url、method、全部请求头、请求体字节与 timeout，以及正常、
   HTTPError（含 JSON 与非 JSON 体）、普通异常与 BudgetExhausted 下的返回值；
2. HTTP Date 粗校时：以与 test_business_clock 相同的方式替换 grab.time 与 grab.urllib，
   按固定偏移、RTT 与错误输入调用 clock_sample，记录返回字典；
3. 日志写入、轮转与降级：将 LOG_FILE / LOG_LOCK_FILE 指到系统临时目录下的新建目录、
   ensure_data_dir 换为空操作、business_now 固定时刻，记录日志文件集合及内容、stdout、stderr。

@author Author
"""
from __future__ import annotations

import argparse
import contextlib
import email.utils
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import urllib.error
from pathlib import Path


def _clear_proxies() -> None:
    for key in ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy"):
        os.environ.pop(key, None)


def _encode_body(data) -> dict | None:
    if data is None:
        return None
    raw = bytes(data)
    return {"utf8": raw.decode("utf-8", "replace"), "hex": raw.hex()}


def _capture_request(req, timeout) -> dict:
    return {
        "full_url": req.full_url,
        "method": req.get_method(),
        "headers": sorted([k, v] for k, v in req.header_items()),
        "body": _encode_body(req.data),
        "timeout": timeout,
    }


def _make_response(raw_bytes: bytes, headers: dict | None = None):
    class _Response:
        def __init__(self):
            self._raw = raw_bytes
            self.headers = dict(headers or {})
            self.closed = False

        def read(self):
            return self._raw

        def close(self):
            self.closed = True

    return _Response()


def _record_http(grab) -> list[dict]:
    """录制 _post 与 _get 的发包细节及各类返回/异常形态。"""
    sent = []
    next_behavior = {"mode": "ok", "raw": b'{"code":1,"data":{"ok":true}}', "headers": {}}

    def fake_open(req, timeout=None):
        sent.append(_capture_request(req, timeout))
        mode = next_behavior["mode"]
        if mode == "http_error":
            raise urllib.error.HTTPError(
                req.full_url, 500, "Server Error", hdrs={}, fp=io.BytesIO(next_behavior["raw"])
            )
        if mode == "exc":
            raise RuntimeError("network boom")
        return _make_response(next_behavior["raw"], next_behavior["headers"])

    fake_time = types.SimpleNamespace(
        time=lambda: 1793100000.123,
        monotonic=lambda: 500.0,
        sleep=lambda _s: None,
    )
    budget_ok = types.SimpleNamespace(timeout_s=lambda base: min(float(base), 2.5))
    budget_done = types.SimpleNamespace(
        timeout_s=lambda _base: (_ for _ in ()).throw(grab.BudgetExhausted("time up"))
    )

    orig = {
        "open": grab._school_open,
        "nonce": grab._request_nonce,
        "time": grab.time,
        "token": grab.token,
    }
    grab._school_open = fake_open
    grab._request_nonce = lambda: "fixed-nonce-0123456789abcdef0123"
    grab.time = fake_time
    grab.token = lambda: "tok-from-fn"
    cases = []
    try:
        grab.clear_school_date()
        scenarios = [
            ("post_empty_default_tok", {"mode": "ok", "raw": b'{"code":1,"msg":"ok"}', "headers": {"Date": "Sat, 21 Nov 2026 02:00:00 GMT"}},
             lambda: grab._post("/stu/activity/listActivity")),
            ("post_payload_with_tok_and_budget", {"mode": "ok", "raw": b'{"code":1,"data":[1,2]}', "headers": {}},
             lambda: grab._post("/stu/activity/signup", {"activityId": "a-1", "note": "中文"}, tok="tok-explicit", timeout=10, budget=budget_ok)),
            ("post_http_error_json", {"mode": "http_error", "raw": b'{"code":4001,"message":"expired"}', "headers": {}},
             lambda: grab._post("/stu/activity/check", {"k": "v"})),
            ("post_http_error_non_json", {"mode": "http_error", "raw": b"<html>bad</html>", "headers": {}},
             lambda: grab._post("/stu/activity/check", {"k": "v"})),
            ("post_runtime_exc", {"mode": "exc", "raw": b"", "headers": {}},
             lambda: grab._post("/stu/activity/check", {"k": "v"})),
            ("get_default_tok", {"mode": "ok", "raw": b'{"code":1,"data":{"id":"x"}}', "headers": {}},
             lambda: grab._get("/stu/activity/getInfo/x")),
            ("get_explicit_tok_timeout", {"mode": "ok", "raw": b'{"code":1}', "headers": {}},
             lambda: grab._get("/stu/activity/cancel/x", tok="tok-cancel", timeout=4)),
            ("get_runtime_exc", {"mode": "exc", "raw": b"", "headers": {}},
             lambda: grab._get("/stu/activity/getInfo/err")),
        ]
        for label, behavior, call in scenarios:
            next_behavior.update(behavior)
            before_idx = len(sent)
            ret = call()
            cases.append({
                "label": label,
                "requests": sent[before_idx:],
                "result": ret,
                "school_date_now": grab.school_date_now(),
            })

        raised = None
        try:
            grab._post("/stu/activity/signup", {"a": 1}, budget=budget_done)
        except grab.BudgetExhausted as exc:
            raised = f"{type(exc).__name__}:{exc}"
        cases.append({"label": "post_budget_exhausted", "requests": [], "raised": raised})
    finally:
        grab._school_open = orig["open"]
        grab._request_nonce = orig["nonce"]
        grab.time = orig["time"]
        grab.token = orig["token"]
        grab.clear_school_date()
    return cases


def _record_clock_sample(grab) -> list[dict]:
    """用与 test_business_clock 相同边界替换方式录制 clock_sample 返回值。"""
    base_epoch = 1793016000
    cases = []

    class _FakeClock:
        def __init__(self, start: float):
            self._t = float(start)

        def time(self) -> float:
            return self._t

        def monotonic(self) -> float:
            return self._t

        def sleep(self, seconds: float) -> None:
            self._t += float(seconds)

    class _FakeReq:
        def __init__(self, *args, **kwargs):
            pass

        def add_header(self, *args, **kwargs):
            pass

    specs = [
        ("ok_zero_offset", 0.0, 0.2, "auto", None),
        ("warn_eight_offset", 8.0, 0.2, "auto", None),
        ("unknown_slow_rtt", 0.0, 4.0, "auto", None),
        ("unknown_straddle", 3.1, 0.1, "auto", None),
        ("unknown_missing_date", 0.0, 0.2, None, None),
        ("unknown_bad_date", 0.0, 0.2, "not-a-date", None),
        ("unknown_network_err", 0.0, 0.2, "auto", OSError("network down")),
    ]
    orig_time, orig_urllib = grab.time, grab.urllib
    try:
        for label, offset_s, rtt_s, date_text, exc in specs:
            clock = _FakeClock(base_epoch)
            header_date = (
                email.utils.formatdate(base_epoch + offset_s, usegmt=True)
                if date_text == "auto"
                else date_text
            )

            def urlopen(_req, timeout=None, _clk=clock, _rtt=rtt_s, _d=header_date, _exc=exc):
                _clk.sleep(_rtt)
                if _exc is not None:
                    raise _exc
                return _make_response(b"", {} if _d is None else {"Date": _d})

            grab.time = types.SimpleNamespace(time=clock.time, monotonic=clock.monotonic, sleep=clock.sleep)
            grab.urllib = types.SimpleNamespace(
                request=types.SimpleNamespace(Request=_FakeReq, urlopen=urlopen)
            )
            cases.append({"label": label, "sample": grab.clock_sample()})
    finally:
        grab.time = orig_time
        grab.urllib = orig_urllib
    return cases


def _snapshot_log_files(root: Path) -> dict[str, str]:
    files = {}
    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if p.name.endswith(".lock") or not p.is_file():
            continue
        files[p.name] = p.read_text(encoding="utf-8")
    return files


def _record_logs(grab) -> dict:
    """录制正常写入、触发轮转、rotate 抛错、写文件失败与 stdout 改道。"""
    with tempfile.TemporaryDirectory(prefix="record-io-log-") as tmp_dir:
        root = Path(tmp_dir)
        log_path = root / "grab.log"
        lock_path = root / "grab.log.lock"
        orig = {
            "log_file": grab.LOG_FILE,
            "lock_file": grab.LOG_LOCK_FILE,
            "ensure": grab.ensure_data_dir,
            "max_bytes": grab.LOG_MAX_BYTES,
            "keep": grab.LOG_KEEP,
            "clock_now": grab._CLOCK.get("now"),
            "rotate": grab.rotate_log_file,
        }
        grab.LOG_FILE = log_path
        grab.LOG_LOCK_FILE = lock_path
        grab.ensure_data_dir = lambda: None
        grab.LOG_MAX_BYTES = 180
        grab.LOG_KEEP = 3
        grab._CLOCK["now"] = lambda: 1793100000.0
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                for idx in range(6):
                    grab.log(f"line-{idx}-" + ("内容" * 8))
                with grab._stdout_to_stderr(True):
                    print("redirected-msg")
                    grab.log("during-redirect")
                files_after_rotate = _snapshot_log_files(root)

                def bad_rotate(*_a, **_kw):
                    raise PermissionError("busy")

                grab.rotate_log_file = bad_rotate
                grab.log("still-logged-on-rotate-error")
                files_after_rotate_err = _snapshot_log_files(root)

                bad_log_path = root / "blocked_dir"
                bad_log_path.mkdir()
                grab.LOG_FILE = bad_log_path
                grab.rotate_log_file = orig["rotate"]
                grab.log("unwritable-line")
        finally:
            grab.LOG_FILE = orig["log_file"]
            grab.LOG_LOCK_FILE = orig["lock_file"]
            grab.ensure_data_dir = orig["ensure"]
            grab.LOG_MAX_BYTES = orig["max_bytes"]
            grab.LOG_KEEP = orig["keep"]
            grab._CLOCK["now"] = orig["clock_now"]
            grab.rotate_log_file = orig["rotate"]

        return {
            "files_after_rotate": files_after_rotate,
            "files_after_rotate_err": files_after_rotate_err,
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
        }


def record_copy(copy_root: Path) -> dict:
    """在当前进程里切进 copy_root 并执行三段录制。"""
    _clear_proxies()
    local_dir = copy_root / "local"
    sys.path.insert(0, str(local_dir))
    os.chdir(copy_root)
    import grab  # type: ignore

    return {
        "http": _record_http(grab),
        "clock_sample": _record_clock_sample(grab),
        "logs": _record_logs(grab),
    }


def run_isolated(copy_root: Path, out_json: Path) -> dict:
    """用干净子进程录制指定副本，避免模块缓存串味。"""
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--worker",
        str(copy_root),
        "--out",
        str(out_json),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"录制子进程失败 ({proc.returncode}): {proc.stderr or proc.stdout}")
    return json.loads(out_json.read_text(encoding="utf-8"))


def compare_records(a: dict, b: dict) -> list[str]:
    """递归逐字段比对两份录制结果，返回差异路径清单。"""
    diffs: list[str] = []

    def _walk(va, vb, path: str) -> None:
        if type(va) is not type(vb):
            diffs.append(f"{path}: type {type(va).__name__} != {type(vb).__name__}")
            return
        if isinstance(va, dict):
            ka, kb = set(va.keys()), set(vb.keys())
            if ka != kb:
                diffs.append(f"{path}: keys {sorted(ka)} != {sorted(kb)}")
                return
            for k in sorted(ka):
                _walk(va[k], vb[k], f"{path}.{k}")
        elif isinstance(va, list):
            if len(va) != len(vb):
                diffs.append(f"{path}: len {len(va)} != {len(vb)}")
                return
            for i, (xa, xb) in enumerate(zip(va, vb)):
                _walk(xa, xb, f"{path}[{i}]")
        elif va != vb:
            diffs.append(f"{path}: {va!r} != {vb!r}")

    _walk(a, b, "$")
    return diffs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="录制并比对学校请求层与日志层行为")
    parser.add_argument("--worker", type=Path, help="内部 worker 模式：指定副本根目录")
    parser.add_argument("--out", type=Path, help="输出录制 JSON 文件路径")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("COPY_A", "COPY_B"),
                        help="在两个独立副本目录里录制并逐字段比对")
    args = parser.parse_args(argv)

    if args.worker is not None:
        if args.out is None:
            parser.error("--worker 需要 --out")
        data = record_copy(args.worker.resolve())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    if args.compare is not None:
        copy_a, copy_b = (p.resolve() for p in args.compare)
        with tempfile.TemporaryDirectory(prefix="record-io-out-") as out_dir:
            out_path = Path(out_dir)
            rec_a = run_isolated(copy_a, out_path / "a.json")
            rec_b = run_isolated(copy_b, out_path / "b.json")
            diffs = compare_records(rec_a, rec_b)
            print(json.dumps({
                "http_cases": len(rec_a["http"]),
                "clock_cases": len(rec_a["clock_sample"]),
                "log_files_rotated": sorted(rec_a["logs"]["files_after_rotate"].keys()),
                "diff_count": len(diffs),
                "diffs": diffs[:20],
            }, ensure_ascii=False, indent=2))
            return 0 if not diffs else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
