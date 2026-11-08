# -*- coding: utf-8 -*-
"""取消报名的纯规则（计划 20261107-conflict-cancel，X2/X4）。

worker（grab.py cancel）与界面进程（app.Api.cancel_signup）共用：学校回包原话的清洗、
worker 输出行的解析与归一化。纯函数：不做 IO、不读墙钟、不联网。

结果四类外加忙碌：
- cancelled        复查确认学校记录里已没有这场报名；
- refused          复查仍是已报名，带学校原话（已清洗、截断）；
- unknown          没能确认（复查没查到、worker 超时或输出读不出）；
- precheck_failed  前置条件不满足或查不到，没有调取消接口，带 reason；
- busy             界面进程这边与别的学校动作互斥（X3），没有起 worker。

@author Author
"""
from __future__ import annotations

import json
import re
import unicodedata

WORKER_KINDS = ("cancelled", "refused", "unknown", "precheck_failed")
MESSAGE_MAX = 80
_REASON_RE = re.compile(r"[a-z_]{1,32}")


def sanitize_message(value, limit: int = MESSAGE_MAX) -> str:
    """学校回包里的 message → 能直接给界面显示的一句话。

    去掉全部控制类字符（Unicode 类别 C*：换行、制表、零宽、方向控制符等），
    首尾空白去掉，截到 limit 个字符。只用于回给界面，永远不写文件、不进运行记录。
    """
    text = "".join(ch for ch in str(value if value is not None else "")
                   if unicodedata.category(ch)[0] != "C")
    return text.strip()[:limit]


def unknown_result() -> dict:
    return {"ok": False, "kind": "unknown"}


def normalize_worker_result(stdout) -> dict:
    """worker stdout → 界面要的结果；读不出一律 unknown（结果未知，绝不猜成功）。

    只认最后一个非空行。ok 由 kind 推出，不信 worker 自报；precheck_failed 的 reason
    只放行小写字母和下划线（不让原话从这里混进去）；message 只给 refused，再清洗一遍。
    """
    lines = [line.strip() for line in str(stdout or "").splitlines() if line.strip()]
    if not lines:
        return unknown_result()
    try:
        data = json.loads(lines[-1])
    except (ValueError, TypeError):
        return unknown_result()
    if not isinstance(data, dict) or data.get("kind") not in WORKER_KINDS:
        return unknown_result()
    kind = data["kind"]
    out = {"ok": kind == "cancelled", "kind": kind}
    if kind == "precheck_failed":
        reason = data.get("reason")
        out["reason"] = (reason if isinstance(reason, str) and _REASON_RE.fullmatch(reason)
                         else "unknown_state")
    elif kind == "refused":
        message = sanitize_message(data.get("message"))
        if message:
            out["message"] = message
    return out
