#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学校报名回包分类与直发请求头（与本机决策 015 同口径，独立实现）。

纯函数：不做网络、不读时钟、不写状态。
@author Author
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SignupReply:
    """一笔回包的分类结论。"""

    kind: str
    label: str
    raw: str


PHRASE_TABLE = (
    ("not_open", "报名未开始", "报名还没开始"),
    ("full", "报名人数已满", "名额已满"),
    ("conflict", "时间冲突", "时间冲突"),
    ("closed", "报名已结束", "报名已截止"),
    ("version", "版本不兼容", "版本不兼容"),
    ("stale_ts", "请求已超时", "请求已超时，本机时钟可能不准"),
    ("no_activity", "hd-info", "活动不存在"),
)

SUCCESS_LABEL = "报名成功"
LOGIN_INVALID_LABEL = "登录失效"
UNKNOWN_LABEL = "学校回了无法识别的结果"

TERMINAL_STOP_REASONS = {
    "full": "full",
    "closed": "closed",
    "conflict": "conflict",
    "no_activity": "no_activity",
}

UNKNOWN_REPLY_LIMIT = 3
STALE_TS_LIMIT = 2

STOP_REASON_LABELS = {
    "full": "名额已满",
    "closed": "报名已截止",
    "conflict": "时间冲突",
    "no_activity": "活动不存在",
    "clock_skew": "本机时钟不准",
    "unknown_reply": "学校回了无法识别的结果",
    "page_unavailable": "学校页面打不开",
}


def _code_text(code) -> str:
    return str(code).strip() if code is not None else ""


def classify_signup_reply(code, message) -> SignupReply:
    """按分类表给一笔回包定性；任何输入都不抛异常。

    判定顺序：code=1 成功 → code=4001 登录失效 → 关键短语 → unknown。
    """
    text = str(message or "").strip()
    code_text = _code_text(code)
    raw = "code:%s %s" % (code_text or "?", text)
    if code_text == "1":
        return SignupReply("success", SUCCESS_LABEL, raw)
    if code_text == "4001":
        return SignupReply("login_invalid", LOGIN_INVALID_LABEL, raw)
    for kind, phrase, label in PHRASE_TABLE:
        if phrase in text:
            return SignupReply(kind, label, raw)
    return SignupReply("unknown", UNKNOWN_LABEL, raw)


def stop_reason_label(stop_reason) -> str:
    """新增终态的短结论；旧终态返回空串。"""
    return STOP_REASON_LABELS.get(str(stop_reason or ""), "")


def decode_reply_body(raw) -> dict:
    """字节响应体 → dict。先严格 utf-8，失败再 gb18030；解不出返回 {}。"""
    if not raw:
        return {}
    for encoding in ("utf-8", "gb18030"):
        try:
            text = raw.decode(encoding) if isinstance(raw, (bytes, bytearray)) else str(raw)
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, ValueError):
            continue
    return {}


def direct_headers(tok: str, referer: str, ua: str) -> dict:
    """直发 signUp 的请求头（决策 015）。"""
    return {
        "Accept": "application/json, text/plain, */*",
        "token": tok,
        "Referer": referer,
        "User-Agent": ua,
    }
