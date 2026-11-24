#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主动换新（--preempt）避让守卫：有报名在跑或 20 分钟内将开放时跳过。

只影响主动换新；token 已失效的被动重登与 --force 不受本守卫限制。
@author Author
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

DEFAULT_GRAB_UNIT_PREFIX = "campus-grab-"
PREEMPT_LOOKAHEAD_SEC = 20 * 60
_AT_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")


def resolve_unit_prefix(unit_prefix=None) -> str:
    val = str(unit_prefix if unit_prefix is not None
              else os.environ.get("GRAB_UNIT_PREFIX", "")).strip()
    return val or DEFAULT_GRAB_UNIT_PREFIX


def has_active_grab_unit(unit_prefix=None, runner_fn=subprocess.run) -> tuple[bool, str]:
    """检测是否有前缀匹配的报名 systemd unit 正在运行。"""
    prefix = resolve_unit_prefix(unit_prefix)
    cmd = [
        "systemctl", "list-units", "--type=service",
        "--state=running,activating", "--no-legend", "--no-pager", f"{prefix}*",
    ]
    try:
        proc = runner_fn(cmd, capture_output=True, text=True, timeout=10)
    except Exception as exc:
        return True, "systemctl 查询异常（%s），安全跳过主动换新" % type(exc).__name__
    if getattr(proc, "returncode", 1) != 0:
        return True, "systemctl 返回非零退出码（%s），安全跳过主动换新" % getattr(proc, "returncode", 1)
    for line in (getattr(proc, "stdout", "") or "").splitlines():
        token = line.strip().split(None, 1)[0] if line.strip() else ""
        if token.startswith(prefix):
            return True, "存在运行中的报名单元（%s）" % token
    return False, ""


def _parse_open_at(raw_text) -> datetime | None:
    raw = str(raw_text or "").strip()
    for fmt in _AT_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def check_upcoming_watchlist(watchlist_path, now_dt=None,
                             window_sec=PREEMPT_LOOKAHEAD_SEC) -> tuple[bool, str]:
    """检查 watchlist.json 是否有 queued 场次在接下来 window_sec 内开放。"""
    try:
        with open(watchlist_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return False, ""
    except Exception as exc:
        return True, "watchlist.json 无法读取（%s），跳过主动换新" % type(exc).__name__

    if isinstance(data, dict):
        entries = data.get("entries")
    elif isinstance(data, list):
        entries = data
    else:
        entries = None
    if not isinstance(entries, list):
        return True, "watchlist.json 结构非法，跳过主动换新"

    now = now_dt if now_dt is not None else datetime.now()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") != "queued":
            continue
        open_at = _parse_open_at(entry.get("open_at"))
        if open_at is None:
            return True, "watchlist 排队条目开放时间无法解析，跳过主动换新"
        delta_s = (open_at - now).total_seconds()
        if 0 <= delta_s <= float(window_sec):
            return True, "预报名场次将在 20 分钟内开放（%s）" % str(entry.get("open_at") or "")
    return False, ""


def should_skip_preempt(*, app_dir, unit_prefix=None, now_dt=None,
                        window_sec=PREEMPT_LOOKAHEAD_SEC,
                        runner_fn=subprocess.run) -> tuple[bool, str]:
    """综合判断是否跳过本轮主动换新。"""
    active, reason = has_active_grab_unit(unit_prefix=unit_prefix, runner_fn=runner_fn)
    if active:
        return True, reason
    watchlist_path = os.path.join(app_dir, "data", "watchlist.json")
    return check_upcoming_watchlist(watchlist_path, now_dt=now_dt, window_sec=window_sec)
