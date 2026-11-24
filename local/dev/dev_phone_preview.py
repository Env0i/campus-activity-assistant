#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发期离线手机页预览服务。

只监听 127.0.0.1，强制把 CAMPUS_DATA_DIR 指到系统临时目录下的空文件夹，
复用 demo_items 与真实 local/ui/m 静态资源起一个无需连网的替身手机服务。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
LOGIN_PRESETS = {
    "never": {"session_present": False, "session_expired": False, "last_check_state": "unknown"},
    "unknown": {"session_present": True, "session_expired": False, "last_check_state": "unknown"},
    "expired": {"session_present": True, "session_expired": True, "last_check_state": "expired"},
    "valid": {"session_present": True, "session_expired": False, "last_check_state": "valid"},
    "recovering": {"session_present": True, "session_expired": True,
                   "last_check_state": "expired", "recovering": True},
}


def _clear_proxies() -> None:
    """清除环境变量里的代理，避免本机回环请求走错通道。"""
    for key in PROXY_VARS:
        os.environ.pop(key, None)


class _DemoApi:
    """只做离线应答，不触发真实登录或学校请求。"""

    def __init__(self, state_name: str):
        self._state_name = state_name

    def check(self, request_id: str = "") -> dict:
        return {"ok": True, "result": self._state_name, "request_id": request_id}

    def list_activities(self, request_id: str = "") -> dict:
        return {"ok": True, "items": [], "request_id": request_id}


def build_demo_state(args: argparse.Namespace) -> dict:
    """构造离线手机页快照；数据与时间戳完全脱离 local/data 与真实登录态。"""
    from domain.common import demo_data
    from infrastructure.clock.time_contract import school_time_text

    now_s = time.time()
    tick_s = time.monotonic()
    return {
        "activities": demo_data.demo_items(now_s, school_time_text),
        "login": dict(LOGIN_PRESETS[args.state]),
        "plan": None,
        "busy": False,
        "terms": {"accepted_version": "1"},
        "terms_ok": True,
        "business_clock": {
            "state": "ready",
            "epoch_s": now_s,
            "tick_s": tick_s,
            "sampled_tick_s": tick_s,
            "age_s": 0.0,
        },
        "retry_options": {
            "default": 120,
            "choices": [
                {"value": 120, "label": "2 分钟"},
                {"value": 0, "label": "直到报名截止"},
            ],
        },
        "retry_policy": {"retry_for_s": 120, "max_attempts": 0},
        "relogin_setup": {
            "saved": bool(args.saved),
            "account_hint": "26****01" if args.saved else "",
            "ocr_ready": bool(args.ocr),
            "paused": bool(args.paused),
        },
        "login_relay": {"state": "idle", "live": False},
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动离线手机页预览服务（127.0.0.1）")
    parser.add_argument("--state", choices=tuple(LOGIN_PRESETS), default="never",
                        help="模拟电脑登录态（默认 never）")
    parser.add_argument("--port", type=int, default=8791, help="监听端口（0 为随机端口）")
    parser.add_argument("--saved", action="store_true", help="模拟电脑已保存账号")
    parser.add_argument("--ocr", action="store_true", help="模拟电脑已启用验证码识别")
    parser.add_argument("--paused", action="store_true", help="模拟自动登录因密码不对暂停")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开系统浏览器")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _clear_proxies()
    local_dir = Path(__file__).resolve().parent.parent
    if str(local_dir) not in sys.path:
        sys.path.insert(0, str(local_dir))

    data_root = Path(tempfile.mkdtemp(prefix="campus_phone_preview_"))
    os.environ["CAMPUS_DATA_DIR"] = str(data_root)
    try:
        from application.phone.phone_service import PhoneAccessService
        from domain.phone.phone_rules import ACTION_PARAMS
        from infrastructure.phone.phone_http import PhoneHttpServer

        api = _DemoApi(args.state)
        actions = {name: (lambda _n=name, **kw: getattr(api, _n)(**kw))
                   for name in ACTION_PARAMS if hasattr(api, name)}
        state = build_demo_state(args)
        svc = PhoneAccessService(
            actions=actions,
            now=lambda: 1000.0,
            state_of=lambda: state,
            server_factory=lambda host, port, s: PhoneHttpServer(
                host, port, s, ui_dir=local_dir / "ui" / "m"),
        )
        started = svc.start("127.0.0.1", args.port)
        address = str(started["address"]).rstrip("/")
        print(f"[手机预览] 状态={args.state}  地址={address}/  配对码={started['pair_code']}",
              flush=True)
        print("[手机预览] 可用 --state never|unknown|expired|valid|recovering 切换；按 Ctrl+C 停止",
              flush=True)
        if not args.no_browser:
            webbrowser.open(f"{address}/")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        finally:
            svc.stop()
    finally:
        shutil.rmtree(data_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
