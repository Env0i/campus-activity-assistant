# -*- coding: utf-8 -*-
"""worker 业务时钟装配、等待与结构化事件输出。

从 grab.py 搬出：_CLOCK 状态存取由 grab 保留并传入，ClockClient/BusinessClock/
ClockUnavailable/BudgetExhausted/time/log 等外部边界都在调用时经参数注入；
本模块不 import grab、business_clock 或 time_contract。

@author Author
"""
from __future__ import annotations

import json

from domain.worker.worker_lines import format_retry_event


def configure_business_clock(clock_state, clock_like, *, configure_time_source) -> None:
    """装配业务时钟并同步时间源。"""
    clock_state["now"] = clock_like.now
    clock_state["bounds"] = clock_like.bounds
    clock_state["meta"] = clock_like
    configure_time_source(clock_like.now)   # signup_plan 的缺省 now 同源


def business_now(clock_state, *, clock_unavailable) -> float:
    fn = clock_state.get("now")
    if fn is None:
        raise clock_unavailable("业务时钟未配置")
    return float(fn())


def business_bounds(clock_state, *, clock_unavailable):
    fn = clock_state.get("bounds")
    if fn is None:
        raise clock_unavailable("业务时钟未配置")
    return fn()


def clock_meta(clock_state) -> dict:
    """checkpoint 附带的时钟元数据（无凭证）。"""
    meta = clock_state.get("meta")
    if meta is None:
        return {}
    try:
        return {"owner_id": getattr(meta, "owner_id", ""),
                "generation": getattr(meta, "generation", 0),
                "uncertainty_s": round(float(meta.bounds()[1] - meta.bounds()[0]) / 2, 3)}
    except Exception:
        return {}


def setup_business_clock(*, env, clock_client_cls, business_clock_cls,
                         clock_unavailable, configure_fn, allow_sync=True,
                         timeout_s=3.0):
    """worker 读父进程快照；CLI 有界自校时。失败返回 None，由调用方显式处理。"""
    if env.get("CAMPUS_CLOCK_SNAPSHOT"):
        try:
            client = clock_client_cls()
            client.now()                      # 立即验证快照可用
            configure_fn(client)
            return client
        except clock_unavailable:
            return None
    if not allow_sync:
        return None
    clock = business_clock_cls(background=False, sync_timeout_s=float(timeout_s))
    try:
        if clock.sync() not in ("ready", "holdover"):
            return None
    except Exception:
        return None
    configure_fn(clock)
    return clock


def wait_until(ts, budget=None, *, business_now_fn, budget_exhausted_cls, time_mod):
    """等到指定墙钟时刻；给了预算时，预算一到就放弃等待。"""
    while True:
        left = ts - business_now_fn()      # 业务北京时间：不随系统墙钟跳变
        if left <= 0:
            return
        step = min(0.2, left)
        if budget is not None:
            remain = budget.remaining_s()
            if remain <= 0:
                raise budget_exhausted_cls("等待开放时重试窗口已到点")
            step = min(step, remain)
        time_mod.sleep(step)


def checkpoint_event(kind, at=None, *, business_now_fn, clock_meta_fn,
                     clock_unavailable, log_fn):
    """结构化 checkpoint 行：kind 只取 worker_started/page_opened/watch_started。"""
    if at is None:
        try:
            at = business_now_fn()       # 源事件时间按业务北京时间记录
        except clock_unavailable:
            return                       # 没有可信时钟就不写时间节点，不用本机时间补
    at = float(at)
    payload = {"kind": kind, "at": round(at, 3)}
    meta = clock_meta_fn()
    if meta:
        payload["clock"] = meta
    log_fn("[checkpoint] " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def retry_event(*, log_fn, **fields):
    """写一行进度型 [retry] 事件。"""
    log_fn(format_retry_event(**fields))
