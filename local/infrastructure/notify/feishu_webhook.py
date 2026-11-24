# -*- coding: utf-8 -*-
"""飞书 webhook 的最小发送适配器：发一次 POST，读掉有限响应，失败就抛。

放在 infrastructure，是因为这是唯一需要联网的副作用；application 层的
「什么时候推、推什么」不该自己 import urllib。这里不记日志、不重试：
调用方拿异常类型自己决定怎么记，重试会把一次失效通知变成一串重复消息。

@author Author
"""
from __future__ import annotations

import urllib.request

# 只读掉响应开头：webhook 的回包很小，读满 4 KiB 足以读出错误码又不会把
# 一段异常的长响应整个拖进内存。
MAX_RESPONSE_BYTES = 4096
DEFAULT_TIMEOUT_S = 10.0


def post_json(url: str, body: bytes, timeout: float = DEFAULT_TIMEOUT_S) -> str:
    """向 url POST 一段已编码的 JSON；返回读到的回包文本，失败抛异常。"""
    request = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read(MAX_RESPONSE_BYTES).decode("utf-8", errors="replace")
