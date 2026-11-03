# -*- coding: utf-8 -*-
"""重试策略纯规则：worker 结构化行解析、次数归并、telemetry 载荷、截止计算。

只处理文本/数值：不读管道、不起进程。解析失败一律返回 None/0 兜底，
调用方按「无策略信息」处理，绝不影响既有退出码语义。

@author Author
"""
from __future__ import annotations

import re

from domain.time_text import task_deadline, seconds_until  # noqa: F401  (对外统一出口)
# 三种重试模式的常量出口：Api/worker/父监督都从这里取同一套数值口径
from domain.retry_window import (  # noqa: F401
    ADAPTIVE_RETRY,
    ADAPTIVE_SECONDS,
    DEFAULT_RETRY_SECONDS,
    initial_deadline,
)
from domain.signup_reply import stop_reason_label

# worker 每次真正发起 signUp 时打印的行（带 [i] 前缀落日志）；
# 只匹配这个形状，刷新 / is_joined 查询不会撞上
ATTEMPT_RE = re.compile(r"^(?:\[i\]\s*)?第 (\d+) 次提交[：:]\s*(.*)$")


def parse_retry_line(line: str) -> "dict | None":
    """解析 worker 的结构化终态行：[retry] attempts=N stop_reason=X retry_deadline=<epoch> sign_end=<epoch> last_reason=<原文>。

    时间字段是 epoch 秒（无空格）；last_reason 恒为最后一个字段（可含空格）。
    解析失败返回 None，调用方按「无策略信息」处理，不影响既有退出码语义。
    """
    text = str(line or "").strip()
    prefix = "[retry] "
    if not text.startswith(prefix):
        return None
    head, _, reason = text[len(prefix):].partition(" last_reason=")
    fields: dict = {}
    for pair in head.split(" "):
        key, _, value = pair.partition("=")
        if key:
            fields[key] = value
    if reason:
        fields["last_reason"] = reason
    return fields or None


def attempts_of(stop: dict) -> int:
    """从结构化终态行里读「已承认的提交次数」；非法值按 0。"""
    try:
        return max(0, int((stop or {}).get("attempts", 0) or 0))
    except (TypeError, ValueError):
        return 0


def progress_event_status(parsed: dict, now_epoch=None) -> dict:
    """把报名进程的进度事件转成任务快照字段（决策 015）；其余事件返回空字典。

    path：这一场走直发还是点击，以及退回点击的原因；
    login_wait：在等自动登录，login_wait_until 是预计等到的时刻（epoch 秒，读不到时钟时留空）；
    login_resumed：自动登录完成、继续提交，清掉等待字段。
    """
    kind = (parsed or {}).get("kind")
    if kind == "path":
        return {"path": str(parsed.get("path") or ""),
                "path_reason": str(parsed.get("path_reason") or "").replace("\u00a0", " ")}
    if kind == "login_wait":
        try:
            wait_s = max(0, int(float(parsed.get("wait_s") or 0)))
        except (TypeError, ValueError):
            wait_s = 0
        until = int(now_epoch + wait_s) if (now_epoch is not None and wait_s) else ""
        return {"login_wait": "waiting", "login_wait_until": until}
    if kind == "login_resumed":
        return {"login_wait": "", "login_wait_until": ""}
    return {}


def with_attempts(stop: dict, attempts: int) -> dict:
    """终态载荷统一写「两路归并后的次数」，不让某一路缺失把次数清零。"""
    merged = dict(stop or {})
    merged["attempts"] = max(attempts, attempts_of(stop))
    return merged


def retry_payload(stop: dict, spec, stop_reason: str) -> dict:
    """把 [retry] 行整理成任务终态附带的 telemetry 字段（缺省值兜底）。"""

    def epoch_or_blank(value) -> str:
        """epoch 秒文本；0/非法表示学校没给，落空串交给活动自身字段兜底。"""
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            return ""
        return str(number) if number > 0 else ""

    try:
        attempts = int((stop or {}).get("attempts", 0) or 0)
    except (TypeError, ValueError):
        attempts = 0
    payload = {
        "stop_reason": (stop or {}).get("stop_reason") or stop_reason,
        "attempts": attempts,
        "retry_deadline": epoch_or_blank((stop or {}).get("retry_deadline")),
        "sign_end": epoch_or_blank((stop or {}).get("sign_end")) or spec.sign_end,
    }
    if (stop or {}).get("last_reason"):
        payload["last_reason"] = stop["last_reason"]
    # 学校明确拒绝类终态（名额已满、报名已截止等，决策 015）附短结论，界面直接用，
    # 不再拿 last_reason 原文拼文案；旧终态不加这个键
    label = stop_reason_label(payload["stop_reason"])
    if label:
        payload["outcome_label"] = label
    if (stop or {}).get("phase"):
        # 终态行的提交阶段原样转发（golden/full_speed/adaptive_backoff）；
        # 缺失/未知不编造，界面按缺失处理
        payload["phase"] = stop["phase"]
    return payload


def policy_int(value, fallback: int, minimum: int = 0) -> int:
    """重试策略字段的整数归一：非法/低于下限回退默认值（不猜）。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number >= minimum else fallback
