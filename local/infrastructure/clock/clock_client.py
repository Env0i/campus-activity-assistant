#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""业务时钟只读快照客户端与跨进程单调计时读取。

@author Author
"""
from __future__ import annotations

import json
import os
import sys
import time

__all__ = [
    "ClockUnavailable",
    "ClockClient",
    "READY_UNCERTAINTY_S",
    "HOLDOVER_DRIFT_PPM",
]

READY_UNCERTAINTY_S = 0.5            # 应用策略阈值（非网络精度保证）
HOLDOVER_DRIFT_PPM = 100             # holdover 保守漂移


class ClockUnavailable(Exception):
    """业务时钟不可信：无锚点/快照缺失/过期/损坏。调用方必须显式处理。"""


def _elapsed_tick() -> float:
    """系统级经过毫秒→秒：Windows 用 GetTickCount64（正确声明 restype），
    其余平台用 time.monotonic；两者都是系统级单调时钟，跨进程同源。"""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.GetTickCount64.restype = ctypes.c_ulonglong   # ULONGLONG，不是默认 int
        kernel32.GetTickCount64.argtypes = []
        return float(kernel32.GetTickCount64()) / 1000.0
    return time.monotonic()


def _resolve_elapsed_tick() -> float:
    """调用时解析：若测试替身改写了 business_clock._elapsed_tick，优先走该替身。"""
    pkg = __package__
    if pkg:
        bc = sys.modules.get(f"{pkg}.business_clock")
        if bc is not None:
            fn = getattr(bc, "_elapsed_tick", None)
            if fn is not None and fn is not _elapsed_tick:
                return float(fn())
    return float(_elapsed_tick())


def _require_number(name: str, value, *, minimum: float | None = None) -> float:
    """校验快照数值字段：拒绝 bool/NaN/Inf 与越界值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClockUnavailable("时钟快照字段无效：%s" % name)
    num = float(value)
    if num != num or num in (float("inf"), float("-inf")):
        raise ClockUnavailable("时钟快照字段无效：%s" % name)
    if minimum is not None and num < minimum:
        raise ClockUnavailable("时钟快照字段越界：%s" % name)
    return num


class ClockClient:
    """worker/只读端：按相同 tick 域消费父实例快照；无效一律 ClockUnavailable。

    快照合同（与 BusinessClock.snapshot 同源，一次读取只认一份文档）：
    - ``epoch_s`` 永远对应 ``tick_s``（授时锚点），不是快照生成时刻；
    - ``sampled_tick_s`` 只是该文档生成时刻，用来补采样之后的漂移；
    - 授时年龄按 ``current_tick - tick_s`` 判 900 秒上限，文件被重写不会续命；
    - ``uncertainty_s`` 是采样时的误差，客户端只补采样后漂移，避免重复计入。
    """

    def __init__(self, *, snapshot_path=None, owner_id=None, tick_fn=None,
                 holdover_max_s: float = 900.0,
                 resync_interval_s: float = 300.0) -> None:
        self._path = snapshot_path or os.environ.get("CAMPUS_CLOCK_SNAPSHOT") or ""
        self._owner = owner_id or os.environ.get("CAMPUS_CLOCK_OWNER") or ""
        self._tick = tick_fn or _resolve_elapsed_tick
        self._holdover_max_s = float(holdover_max_s)
        self._resync_interval_s = float(resync_interval_s)

    # ---- 读取与校验 ----
    def _load(self) -> dict:
        """一次读取内完成全部校验并算出同一代的值；字段缺失/矛盾一律拒绝。"""
        if not self._path:
            raise ClockUnavailable("没有配置时钟快照路径")
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                snap = json.load(fh)
        except (OSError, ValueError) as exc:
            raise ClockUnavailable("时钟快照不可读：%s" % exc)
        if not isinstance(snap, dict) or snap.get("schema") != 1:
            raise ClockUnavailable("时钟快照格式不符")
        owner = snap.get("owner_id")
        if not isinstance(owner, str) or not owner:
            raise ClockUnavailable("时钟快照缺少实例归属")
        if self._owner and owner != self._owner:
            raise ClockUnavailable("时钟快照属于其他实例")

        epoch = _require_number("epoch_s", snap.get("epoch_s"))
        anchor_tick = _require_number("tick_s", snap.get("tick_s"))
        sampled_tick = _require_number("sampled_tick_s", snap.get("sampled_tick_s"))
        uncertainty = _require_number("uncertainty_s", snap.get("uncertainty_s"), minimum=0.0)
        state = snap.get("state")
        if state not in ("ready", "holdover"):
            raise ClockUnavailable("时钟快照状态不可用：%s" % state)

        now_tick = self._tick()
        age = now_tick - anchor_tick
        sample_age = now_tick - sampled_tick
        if age < 0 or sample_age < 0:
            raise ClockUnavailable("时钟快照锚点晚于本机经过时长")
        if age > self._holdover_max_s:
            raise ClockUnavailable("时钟快照超过 %g 秒未更新" % self._holdover_max_s)
        drift = HOLDOVER_DRIFT_PPM * 1e-6 * sample_age
        total = uncertainty + drift
        if total > READY_UNCERTAINTY_S:
            raise ClockUnavailable("时钟快照误差超过 %g 秒" % READY_UNCERTAINTY_S)
        effective = "holdover" if (state == "holdover"
                                   or age > self._resync_interval_s) else "ready"
        return {"snap": snap, "epoch": epoch, "anchor_tick": anchor_tick,
                "sampled_tick": sampled_tick, "uncertainty": uncertainty,
                "drift": drift, "total_uncertainty": total, "age": age,
                "now_tick": now_tick, "state": effective,
                "now": epoch + (now_tick - anchor_tick), "owner": owner}

    # ---- 与 BusinessClock 相同的消费接口（RetryBudget 需要）----
    def elapsed_s(self) -> float:
        """应用内经过时长：与父实例同一 tick 域，含睡眠。"""
        return float(self._tick())

    def now(self) -> float:
        """业务 UTC epoch 秒；锚点用 tick_s，不用 sampled_tick_s。"""
        return self._load()["now"]

    def bounds(self) -> tuple[float, float]:
        """业务时刻区间：采样误差 + 采样后保守漂移，同一份快照内取值。"""
        loaded = self._load()
        return (loaded["now"] - loaded["total_uncertainty"],
                loaded["now"] + loaded["total_uncertainty"])

    def state(self) -> str:
        return self._load()["state"]

    @property
    def reason(self) -> str:
        loaded = self._load()
        snap = loaded["snap"]
        return str(snap.get("reason") or ("沿用上次校时" if loaded["state"] == "holdover"
                                          else "北京时间已同步"))

    @property
    def owner_id(self) -> str:
        return self._load()["owner"]

    @property
    def generation(self) -> int:
        value = self._load()["snap"].get("generation")
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0

    def snapshot(self) -> dict:
        """把当前有效读数整理成快照形状（不写文件）。

        ``uncertainty_s`` 保留采样时记录值，另给 ``uncertainty_now_s`` 表示
        含采样后漂移的当前误差——调用方不该再从 sampled 时刻重算一次漂移。
        """
        loaded = self._load()
        snap = dict(loaded["snap"])
        snap["state"] = loaded["state"]
        snap["age_s"] = loaded["age"]
        snap["uncertainty_now_s"] = loaded["total_uncertainty"]
        return snap
