# -*- coding: utf-8 -*-
"""组件读状态的等锁规则：连续等锁满 30 秒算「检查超时」。

纯函数，不做 IO、不读时钟：等锁时长由调用方（infrastructure 的组件状态探测）
用单调时钟算好传进来，这里只判「是否达到阈值」。放在 domain 是因为「等多久
算超时」是产品规则，不是某个适配器的实现细节。
"""
from __future__ import annotations

# 读组件状态等组件事务锁连续等满 30 秒，界面才改说「另一个窗口正在安装或
# 更新组件，已等 30 秒」并给「重试」；不到 30 秒就等，不打断
COMPONENT_CHECK_TIMEOUT_S = 30


def check_timed_out(wait_s) -> bool:
    """连续等锁达到 30 秒才算「检查超时」；等锁时长拿不到就按没超时。"""
    try:
        waited = float(wait_s)
    except (TypeError, ValueError):
        return False
    return waited >= COMPONENT_CHECK_TIMEOUT_S
