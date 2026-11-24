# -*- coding: utf-8 -*-
"""飞书提醒设置：地址校验、config.json 合并写回、发一条测试消息。

只改 config.json 的 feishu_webhook 一个键：站点地址和其他键原样保留。现有配置
读不出来时拒绝保存——宁可这一次没存上，也不能把用户的其它配置覆盖掉。测试消息
沿用现有 webhook 适配器，成功与失败原因都交给设置里就地显示。

@author Author
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

WEBHOOK_KEY = "feishu_webhook"
TEST_TEXT = "这是一条测试消息：设置里的飞书提醒已经能用了。"
BAD_URL_TEXT = "地址要以 https:// 开头，从群机器人的设置里整条复制过来。"


class ConfigUnreadable(RuntimeError):
    """现有 config.json 读不出来：这时保存会把别人的配置一起覆盖掉。"""


def normalize_url(raw) -> str:
    """只接受 https 地址；空串表示关掉提醒。"""
    url = str(raw or "").strip()
    if not url:
        return ""
    parts = urlsplit(url)
    if (parts.scheme.lower() != "https" or not parts.netloc
            or any(ch.isspace() for ch in url)):
        raise ValueError(BAD_URL_TEXT)
    return url


def _load_existing(path, read) -> dict:
    """读现有配置：文件不存在算空（首次保存），读不出或结构不对就拒绝。"""
    try:
        text = read(path)
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ConfigUnreadable("读不出现有的 config.json，这次没有保存，其它设置原样保留。") from exc
    if not str(text or "").strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ConfigUnreadable("现有的 config.json 不是有效的 JSON，这次没有保存。") from exc
    if not isinstance(data, dict):
        raise ConfigUnreadable("现有的 config.json 结构不是对象，这次没有保存。")
    return data


def save(path, raw_url, *, read, write) -> dict:
    """把地址合并写回 config.json：只动 feishu_webhook，读不出就拒绝保存。"""
    try:
        url = normalize_url(raw_url)
    except ValueError as exc:
        return {"ok": False, "error": "bad_url", "text": str(exc)}
    try:
        data = _load_existing(path, read)
    except ConfigUnreadable as exc:
        return {"ok": False, "error": "config_unreadable", "text": str(exc)}
    if url:
        data[WEBHOOK_KEY] = url
    else:
        data.pop(WEBHOOK_KEY, None)
    try:
        write(path, data)
    except OSError:
        return {"ok": False, "error": "write_failed",
                "text": "地址没有保存：写不进 config.json，看看文件是不是被占用了。"}
    text = "已保存，飞书提醒会发到这个群。" if url else "地址已清空，不再发飞书提醒。"
    return {"ok": True, "url": url, "text": text}


def test_message(raw_url, *, post) -> dict:
    """发一条测试消息：失败只说异常类别，不回显地址。"""
    try:
        url = normalize_url(raw_url)
    except ValueError as exc:
        return {"ok": False, "error": "bad_url", "text": str(exc)}
    if not url:
        return {"ok": False, "error": "empty_url", "text": "先填上机器人地址，再发测试消息。"}
    body = json.dumps({"msg_type": "text", "content": {"text": TEST_TEXT}},
                      ensure_ascii=False).encode("utf-8")
    try:
        post(url, body)
    except Exception as exc:                       # noqa: BLE001 - 网络失败种类多，只报类别
        return {"ok": False, "error": "send_failed",
                "text": "测试消息没发出去（%s）：检查网络，或确认地址是从群里复制的。"
                        % type(exc).__name__}
    return {"ok": True, "text": "测试消息已发出，去群里看看。"}

