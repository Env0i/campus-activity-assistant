# -*- coding: utf-8 -*-
"""汇总手机页连接复用对照测速的上报与请求日志（只读 results/，不写任何文件）。

两种连接设置：
  - close：HTTP/1.0，每个请求回复后断开连接
  - keepalive：HTTP/1.1，带 Content-Length 保持并复用同一条 TCP 连接

按「通道 × 组别 × 形态」分别输出真机（iOS Safari）与本机自测（desktop-webview2）的
有效/总次数、done_ms 中位数与最大值、10 秒内未完成次数；再按请求日志输出每轮的
总请求数、TCP 连接数，以及未完成那几次中 40 个模块请求实际到达服务器的个数。

用法：
  python design/evidence/2026-11-21/keepalive-probe/scripts/summarize.py

@author Author
"""
from __future__ import annotations

import json
import statistics
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS_DIR = HERE.parent / "results"
CHANNELS = ("tailscale", "cloudflare")
ARMS = ("close", "keepalive")
FORMS = ("legacy", "flat", "chain", "preload-chain")


def _fmt(value) -> str:
    return "-" if value is None else "%g" % round(float(value), 1)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if text:
            rows.append(json.loads(text))
    return rows


def _is_module_path(path: str, form: str) -> bool:
    clean = urllib.parse.urlsplit(str(path or "")).path
    prefix = "/h9/%s/" % form
    common_prefix = "/h9/%s/common/" % form
    return (
        clean.startswith(prefix)
        and not clean.startswith(common_prefix)
        and (clean.endswith(".js") or clean.endswith(".mjs"))
    )


def _collect_reports(results_dir: Path) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    if not results_dir.is_dir():
        return out
    for path in sorted(results_dir.glob("phone-*.json")):
        out.append((path, _load_json(path)))
    return out


def _print_form_table(title: str, reports: list[tuple[Path, dict]],
                      browser_filter: str) -> dict[tuple[str, str, str], dict]:
    print("## %s" % title)
    print("| 通道 | 组别 | 形态 | 有效 / 总次 | done_ms 中位数（ms） | done_ms 最大值（ms） | 未完成（10 秒内） |")
    print("|---|---|---|---|---:|---:|---:|")
    stats_map: dict[tuple[str, str, str], dict] = {}
    for channel in CHANNELS:
        for arm in ARMS:
            for form in FORMS:
                vals: list[float] = []
                total = 0
                unfinished = 0
                for _path, rec in reports:
                    if rec.get("channel") != channel or rec.get("arm") != arm:
                        continue
                    client = rec.get("client") or {}
                    if client.get("browser") != browser_filter:
                        continue
                    payload = rec.get("payload") or {}
                    if payload.get("page") != "h9" or payload.get("form") != form:
                        continue
                    total += 1
                    done_ms = payload.get("done_ms")
                    if done_ms is None:
                        unfinished += 1
                    else:
                        vals.append(float(done_ms))
                median_val = statistics.median(vals) if vals else None
                max_val = max(vals) if vals else None
                stats_map[(channel, arm, form)] = {
                    "valid": len(vals),
                    "total": total,
                    "median": median_val,
                    "max": max_val,
                    "unfinished": unfinished,
                }
                print("| %s | %s | %s | %d/%d | %s | %s | %d |" % (
                    channel, arm, form, len(vals), total,
                    _fmt(median_val), _fmt(max_val), unfinished,
                ))
    print()
    return stats_map


def _index_session_browsers(reports: list[tuple[Path, dict]]) -> dict[str, set[str]]:
    by_log: dict[str, set[str]] = {}
    for _path, rec in reports:
        server = rec.get("server") or {}
        req_log = str(server.get("request_log") or "")
        browser = str((rec.get("client") or {}).get("browser") or "unknown")
        if req_log:
            by_log.setdefault(req_log, set()).add(browser)
    return by_log


def _print_request_logs(results_dir: Path,
                        reports: list[tuple[Path, dict]]) -> dict[str, list[dict]]:
    print("## 请求日志连接数与请求数")
    print("| 请求日志文件 | 通道 | 组别 | 客户端标签 | 总请求数 | TCP 连接数 | 单连接最大请求数 |")
    print("|---|---|---|---|---:|---:|---:|")
    by_log = _index_session_browsers(reports)
    logs_cache: dict[str, list[dict]] = {}
    if not results_dir.is_dir():
        print()
        return logs_cache
    for path in sorted(results_dir.glob("requests-*.jsonl")):
        rows = _load_jsonl(path)
        logs_cache[path.name] = rows
        if not rows:
            continue
        channel = str(rows[0].get("channel") or "-")
        arm = str(rows[0].get("arm") or "-")
        conn_ids = {int(r.get("conn_id") or 0) for r in rows}
        max_seq = max((int(r.get("conn_req_seq") or 0) for r in rows), default=0)
        browsers = ",".join(sorted(by_log.get(path.name, {"unknown"})))
        print("| `%s` | %s | %s | %s | %d | %d | %d |" % (
            path.name, channel, arm, browsers, len(rows), len(conn_ids), max_seq,
        ))
    print()
    return logs_cache


def _slice_run_requests(rows: list[dict], start_idx: int, end_idx: int,
                        form: str) -> tuple[int, int]:
    window = rows[max(0, start_idx):min(len(rows), end_idx)]
    # 若窗口内含多次导航，只取最后一次进入该 form 页面之后的请求
    nav_pos = 0
    nav_prefix = "/h9/%s/" % form
    for idx, row in enumerate(window):
        clean = urllib.parse.urlsplit(str(row.get("path") or "")).path
        if clean in (nav_prefix, nav_prefix + "index.html"):
            nav_pos = idx
    sub = window[nav_pos:]
    mod_reqs = [r for r in sub if _is_module_path(str(r.get("path") or ""), form)]
    distinct_mods = {urllib.parse.urlsplit(str(r.get("path") or "")).path for r in mod_reqs}
    return len(mod_reqs), len(distinct_mods)


def _print_unfinished_details(reports: list[tuple[Path, dict]],
                              logs_cache: dict[str, list[dict]]) -> None:
    print("## 未完成轮次（10 秒内 done_ms 为空）的模块请求到达情况")
    grouped: dict[str, list[tuple[Path, dict]]] = {}
    for path, rec in reports:
        req_log = str((rec.get("server") or {}).get("request_log") or "")
        grouped.setdefault(req_log, []).append((path, rec))

    found_any = False
    print("| 上报文件 | 通道 | 组别 | 形态 | run | 页面已执行模块数 | 到达服务器的模块请求数（共 40） | 不同模块文件数 |")
    print("|---|---|---|---|---:|---:|---:|---:|")
    for req_log, items in sorted(grouped.items()):
        rows = logs_cache.get(req_log, [])
        prev_idx = 0
        for path, rec in items:
            server = rec.get("server") or {}
            end_idx = int(server.get("request_count_so_far") or len(rows))
            payload = rec.get("payload") or {}
            form = str(payload.get("form") or "")
            if payload.get("page") == "h9" and form:
                if payload.get("done_ms") is None:
                    found_any = True
                    req_cnt, distinct_cnt = _slice_run_requests(rows, prev_idx, end_idx, form)
                    print("| `%s` | %s | %s | %s | %s | %s | %d | %d |" % (
                        path.name, rec.get("channel"), rec.get("arm"), form,
                        payload.get("run"), payload.get("module_count", 0),
                        req_cnt, distinct_cnt,
                    ))
                prev_idx = end_idx
    if not found_any:
        print("| （无未完成记录） | - | - | - | - | - | - | - |")
    print()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    reports = _collect_reports(RESULTS_DIR)
    _print_form_table("真机测速汇总（iOS Safari）", reports, "ios-safari")
    _print_form_table("本机 WebView2 自测汇总（desktop-webview2，仅验证工具可用）",
                      reports, "desktop-webview2")
    logs_cache = _print_request_logs(RESULTS_DIR, reports)
    _print_unfinished_details(reports, logs_cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
