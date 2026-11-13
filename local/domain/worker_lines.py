# -*- coding: utf-8 -*-
"""worker 输出行的纯解析：[checkpoint] / [clock] 结构化行。

只解析文本：坏 JSON、未知 kind 一律返回 None，调用方保持已有状态不变，
绝不用接收时刻补一个假节点。

@author Author
"""
from __future__ import annotations

import json
import re

# worker 的 grab.log() 把每行写成「YYYY-MM-DD HH:MM:SS 消息」再 print；
# 回退格式（业务时钟不可用时）长得一样。只认这一种，别的开头一律不动。
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ")


def worker_message(line: str) -> str:
    """去掉 worker 输出行首的北京时间前缀，返回消息本身；没有前缀则原样返回。

    约定：经 log() 输出的行都带时间戳，而 [retry]、「第 N 次提交」、[X] 这类
    结构行的识别点都要求行首就是标记，所以识别前必须先过这里。这是去前缀的
    唯一入口：调用方不要自己切时间戳，也不要放宽各解析函数自己的前缀规则。
    只用于识别；运行记录与 tail 仍存原行（界面按时间戳前缀着色）。
    """
    text = str(line or "")
    stamp = _STAMP_RE.match(text)
    return text[stamp.end():] if stamp else text


def parse_checkpoint_line(line: str) -> "tuple[str, float] | None":
    """解析 worker 的 [checkpoint] JSON 行，返回 (kind, 源事件 epoch 秒)。

    kind 只认三个真实发生过的事件；坏 JSON、未知 kind 都返回 None，
    调用方保持已有 checkpoint 不变，绝不用接收时刻补一个假节点。
    """
    text = str(line or "")
    marker = "[checkpoint] "
    index = text.find(marker)
    if index < 0:
        return None
    try:
        data = json.loads(text[index + len(marker):].strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    kind = str(data.get("kind") or "")
    if kind not in {"worker_started", "page_opened", "watch_started"}:
        return None
    try:
        at = float(data.get("at"))
    except (TypeError, ValueError):
        return None
    return (kind, at) if at > 0 else None


def parse_clock_line(out: str) -> "dict | None":
    """取输出里最后一条 [clock] 结构化粗校时结论；没有则 None。

    每轮 check 都要带结论（ok/warn/unknown），界面才能用新状态替换旧告警；
    只取最后一行会让「本轮没有采样」被误当成「上一轮仍然有效」。
    """
    found = None
    for line in str(out or "").splitlines():
        marker = "[clock] "
        index = line.find(marker)
        if index < 0:
            continue
        try:
            data = json.loads(line[index + len(marker):].strip())
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict) and data.get("source") == "http_date":
            found = data
    return found
