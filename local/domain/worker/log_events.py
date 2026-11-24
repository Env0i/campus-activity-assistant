# -*- coding: utf-8 -*-
"""关键动作的结构化日志行（架构修订设计第 9 节 / S2）。

纯函数：只拼文本、过滤字段，不读时钟、不写文件。时间戳由写日志的一方
（grab.log()、界面进程）在行首补，这里负责「级别 / 来源 / 活动 ID / 事件名」
固定字段和键名黑名单——日志里不得出现 token、密码、验证码、密钥。

行格式：``[event] level=INFO source=cli activity=<活动ID或-> event=login_ok k=v ...``

@author Author
"""
from __future__ import annotations

import json
import re

# 谁写的这一行：命令行 / 桌面界面 / 无人值守自动登录 / 报名子进程
SOURCES = ("cli", "gui", "auto_relogin", "worker")
LEVELS = ("INFO", "WARN", "ERROR")

# 字段名里出现这些片段就整个丢掉（小写后按包含判断）。宁可多挡：事件字段都是
# 开发者起的名字，误挡一个 key_xxx 比漏过一个 token 便宜得多。
FORBIDDEN_KEY_PARTS = (
    "token", "password", "passwd", "pwd", "secret", "captcha", "cookie",
    "authorization", "credential", "key", "username", "student", "account",
    "验证码", "密码", "密钥", "账号", "学号",
)

# 固定字段名，不许被调用方的字段覆盖
_RESERVED = {"level", "source", "activity", "event"}
_MAX_VALUE_CHARS = 200
_UNSAFE = re.compile(r"[\s=\"']")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def is_forbidden_key(name) -> bool:
    lowered = str(name or "").lower()
    return any(part in lowered for part in FORBIDDEN_KEY_PARTS)


def scrub_fields(fields) -> dict:
    """丢掉黑名单键名和保留名，其余原样返回（顺序保持）。"""
    clean = {}
    for name, value in (fields or {}).items():
        if is_forbidden_key(name) or str(name).lower() in _RESERVED:
            continue
        clean[str(name)] = value
    return clean


def _value_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = ("%.2f" % value).rstrip("0").rstrip(".")
        return text or "0"
    text = _CONTROL.sub(" ", str(value))
    if len(text) > _MAX_VALUE_CHARS:
        text = text[:_MAX_VALUE_CHARS] + "…"
    if text == "" or _UNSAFE.search(text):
        return json.dumps(text, ensure_ascii=False)
    return text


def _token(text, fallback) -> str:
    """固定字段只留字母数字下划线连字符，免得一个坏值把整行格式带歪。"""
    cleaned = re.sub(r"[^0-9A-Za-z_\-]", "_", str(text or ""))
    return cleaned or fallback


def format_event_line(event, source, *, level="INFO", activity_id="", fields=None) -> str:
    """拼一行事件日志；字段先过黑名单，值里的空白和引号会被转义。"""
    level_text = str(level or "INFO").upper()
    if level_text not in LEVELS:
        level_text = "INFO"
    parts = ["[event]",
             "level=%s" % level_text,
             "source=%s" % _token(source, "unknown"),
             "activity=%s" % _token(activity_id, "-"),
             "event=%s" % _token(event, "unknown")]
    for name, value in scrub_fields(fields).items():
        parts.append("%s=%s" % (_token(name, "field"), _value_text(value)))
    return " ".join(parts)
