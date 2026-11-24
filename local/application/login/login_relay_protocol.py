# -*- coding: utf-8 -*-
"""手机重登中继协议解析与 flow 状态转移（纯逻辑，不持服务锁）。

从 login_relay_service 拆出，封装 [login] 结构行解析、challenge/rejected/
verifying/success/failed 状态转移、安全错误码收敛与回调签名探测。

@author Author
"""
from __future__ import annotations

import inspect
import json
import queue
import re
import threading

# OCR 自动提交前的形状门禁：与 worker 的 valid_code 一致，四位 ASCII 字母数字
VALID_CODE_RE = re.compile(r"^[0-9A-Za-z]{4}$")

STATE_STARTING = "starting"
STATE_WAITING_CODE = "waiting_code"
STATE_VERIFYING = "verifying"
STATE_SUCCESS = "success"
STATE_FAILED = "failed"
STATE_CANCELED = "canceled"

_SAFE_ERRORS = {
    "needs_local_setup", "plan_active", "terms_required", "busy",
    "spawn_failed", "bad_page", "bad_response", "token_unverified",
    "expired", "canceled", "eof", "timeout", "internal", "demo",
    "max_tries",
    # 学校明确说账号或密码不对：登录进程报出这个码时，界面停下并暂停自动登录
    "bad_password",
}


def safe_error(value) -> str:
    text = str(value or "")
    return text if text in _SAFE_ERRORS else "internal"


def accepts_origin(callback) -> bool:
    """判断成功回调是否收一个来源标签。

    旧调用方传的是零参 lambda；用签名判断比「先传参、失败再退回零参」干净，
    也不必让异常参与正常流程。取不到签名（如某些 Mock）时按零参处理。
    """
    try:
        params = inspect.signature(callback).parameters
    except (TypeError, ValueError):
        return False
    for param in params.values():
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            return True
        if param.kind is param.VAR_POSITIONAL:
            return True
    return False


def new_flow_record(flow_id: str, origin: str, auto_ocr_ready: bool) -> dict:
    """构造单次中继会话的内存状态字典。"""
    return {
        "flow_id": flow_id, "state": STATE_STARTING, "challenge_id": "",
        "image": "", "expires_in": None, "deadline": None,
        "attempts": 0, "max_attempts": 0,
        "safe_error": "", "tree": None, "success_fired": False,
        "submit_pending": False, "handoff": False,
        "mode": "auto" if auto_ocr_ready else "manual",
        "origin": str(origin or "phone"), "stdin": None,
        "lines": queue.Queue(), "reader_done": threading.Event(),
    }


def parse_relay_line(line: str, expected_flow_id: str) -> tuple[str, dict] | None:
    """解析 worker 输出的 [login] JSON 行，过滤非当前 flow 的旧消息。"""
    prefix = "[login] "
    if not line.startswith(prefix):
        return None
    try:
        data = json.loads(line[len(prefix):])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if str(data.get("flow_id") or "") != str(expected_flow_id or ""):
        return None
    return str(data.get("kind") or ""), data


def _apply_challenge_event(flow: dict, data: dict, manual_after: int) -> dict:
    """处理 challenge 事件；重复 challenge 只非破坏性同步计数并要求忽略广播。"""
    challenge_id = str(data.get("challenge_id") or "")
    if challenge_id and challenge_id == str(flow.get("challenge_id") or ""):
        # 同一 challenge 的事件更新（重复投递）：不清空输入状态、
        # 不清空已输入状态，只非破坏性同步计数，也不补发事件
        # ——新事件会被手机当成新验证码，清掉正在输入的码。
        flow["attempts"] = max(int(flow.get("attempts") or 0),
                               max(0, int(data.get("attempts") or 0)))
        flow["max_attempts"] = 0
        return {"ignore": True, "success": False,
                "handoff_attempts": None, "rejected_reason": None}
    flow["submit_pending"] = False
    flow["state"] = STATE_WAITING_CODE
    flow["challenge_id"] = challenge_id
    image = str(data.get("image") or "")
    flow["image"] = image if image.startswith("data:image/png;base64,") else ""
    flow["expires_in"] = None
    flow["deadline"] = None
    flow["attempts"] = max(0, int(data.get("attempts") or 0))
    handoff_attempts = None
    if manual_after and flow["attempts"] >= manual_after:
        # 自动识别连续认错到上限：这一场转人工，记下交接事实
        if flow.get("mode") == "auto":
            handoff_attempts = flow["attempts"]
            flow["handoff"] = True
        flow["mode"] = "manual"
    flow["max_attempts"] = 0
    return {"ignore": False, "success": False,
            "handoff_attempts": handoff_attempts, "rejected_reason": None}


def apply_relay_event(flow: dict, kind: str, data: dict, manual_after: int) -> dict:
    """把一条合法结构行应用到 flow（调用方已持锁）；返回锁外副作用摘要。"""
    outcome = {"ignore": False, "success": False,
               "handoff_attempts": None, "rejected_reason": None}
    try:
        if kind == "challenge":
            return _apply_challenge_event(flow, data, manual_after)
        if kind == "rejected":
            flow["submit_pending"] = False
            flow["attempts"] = max(0, int(data.get("attempts") or 0))
            flow["safe_error"] = safe_error(data.get("reason"))
            outcome["rejected_reason"] = flow["safe_error"]
        elif kind == "verifying":
            flow["state"] = STATE_VERIFYING
        elif kind == "success":
            # worker 若自己声明了完成方（它跑过 OCR），以它为准；没声明就沿用开局时的来源
            declared = str(data.get("origin") or "")
            if declared in ("auto", "phone"):
                flow["origin"] = declared
            flow["state"] = STATE_SUCCESS
            flow["safe_error"] = ""
            outcome["success"] = not flow.get("success_fired")
            flow["success_fired"] = True
        elif kind in ("failed", "canceled"):
            flow["state"] = STATE_FAILED if kind == "failed" else STATE_CANCELED
            flow["safe_error"] = safe_error(data.get("error"))
    except (TypeError, ValueError, OverflowError):
        outcome["ignore"] = True
    return outcome
