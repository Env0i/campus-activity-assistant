#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用无头 Edge 截取手机页登录四态、首次登录面板与对应原型画板。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-21/phone-login-phases/scripts/shots.py

@author Author
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
EVIDENCE_DIR = Path(__file__).resolve().parents[1]
SHOTS_DIR = EVIDENCE_DIR / "shots"
PROTO_DIR = REPO / "design" / "prototype" / "workbench-2026-11"
UI_M = REPO / "local" / "ui" / "m"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")

LOGIN_SNAPSHOTS = {
    "never": {"session_present": False, "session_expired": False, "last_check_state": "unknown"},
    "unknown": {"session_present": True, "session_expired": False, "last_check_state": "unknown"},
    "expired": {"session_present": True, "session_expired": True, "last_check_state": "expired"},
    "valid": {"session_present": True, "session_expired": False, "last_check_state": "valid"},
}

SERVER_RUNNER = r"""
import json, sys
from pathlib import Path

local_dir, ui_dir, login_json = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, local_dir)

from application.phone_service import PhoneAccessService
from domain.phone_rules import ACTION_PARAMS
from infrastructure.phone_http import PhoneHttpServer

class FakeApi:
    def check(self, request_id=""):
        return {"ok": True, "result": "valid"}
    def list_activities(self, request_id=""):
        return {"ok": True, "items": [], "request_id": request_id}

api = FakeApi()
actions = {name: (lambda _n=name, **kw: getattr(api, _n)(**kw))
           for name in ACTION_PARAMS if hasattr(api, name)}
raw_state = {
    "activities": [
        {
            "id": "a1", "name": "青年志愿者校园导览", "place": "图书馆门前",
            "sign_start": "2026-11-22 09:00:00", "sign_end": "2026-11-22 18:00:00",
            "act_start": "2026-11-23 14:00:00", "act_end": "2026-11-23 16:00:00",
            "signed": False, "cancel_allowed": True,
            "reward_state": "ready", "points": 2, "wage": 0,
        },
        {
            "id": "a2", "name": "实验室安全规范讲座", "place": "学术报告厅",
            "sign_start": "2026-11-22 14:00:00", "sign_end": "2026-11-22 20:00:00",
            "act_start": "2026-11-24 19:00:00", "act_end": "2026-11-24 21:00:00",
            "signed": False, "cancel_allowed": False,
            "reward_state": "ready", "points": 1, "wage": 0,
        },
        {
            "id": "a3", "name": "校园秋日健步行", "place": "南操场",
            "sign_start": "2026-11-20 08:00:00", "sign_end": "2026-11-23 12:00:00",
            "act_start": "2026-11-25 09:00:00", "act_end": "2026-11-25 11:30:00",
            "signed": True, "cancel_allowed": True,
            "reward_state": "ready", "points": 2, "wage": 0,
        },
    ],
    "login": json.loads(login_json),
    "plan": None,
    "busy": False,
    "terms": {"accepted_version": "1"},
    "terms_ok": True,
    "business_clock": {
        "state": "ready", "epoch_s": 1795312800.0,
        "tick_s": 1000.0, "sampled_tick_s": 1000.0, "age_s": 0.0,
    },
    "retry_options": {"default": 120, "choices": [{"value": 120, "label": "2 分钟"}]},
    "retry_policy": {"retry_for_s": 120, "max_attempts": 0},
    "relogin_setup": {"saved": False, "account_hint": "", "ocr_ready": False, "paused": False},
    "login_relay": {"state": "idle", "live": False},
}
svc = PhoneAccessService(
    actions=actions, now=lambda: 1000.0, state_of=lambda: raw_state,
    server_factory=lambda host, port, s: PhoneHttpServer(host, port, s, ui_dir=Path(ui_dir)),
)
started = svc.start("127.0.0.1", 0)
print(json.dumps({"address": started["address"], "pair_code": started["pair_code"]}), flush=True)
try:
    sys.stdin.readline()
finally:
    svc.stop()
"""


def _clean_env(data_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in PROXY_VARS:
        env.pop(key, None)
    env["CAMPUS_DATA_DIR"] = str(data_dir)
    return env


def _start_fake_server(login_payload: dict, data_dir: Path):
    proc = subprocess.Popen(
        [sys.executable, "-B", "-c", SERVER_RUNNER,
         str(REPO / "local"), str(UI_M), json.dumps(login_payload)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=_clean_env(data_dir),
    )
    line = proc.stdout.readline().strip()
    if not line:
        err = proc.stderr.read() if proc.stderr else ""
        proc.kill()
        raise RuntimeError(f"替身手机服务启动失败：{err}")
    info = json.loads(line)
    return proc, str(info["address"]).rstrip("/"), str(info["pair_code"])


def _stop_fake_server(proc) -> None:
    try:
        if proc.stdin:
            proc.stdin.write("\n")
            proc.stdin.flush()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def _attach_error_listeners(page) -> tuple[list[str], list[str], list[str]]:
    console_errs: list[str] = []
    page_errs: list[str] = []
    req_fails: list[str] = []
    page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))
    page.on("requestfailed", lambda req: req_fails.append(f"{req.url}: {req.failure}"))
    return console_errs, page_errs, req_fails


def _capture_phone_state(browser, state_name: str, login_payload: dict) -> dict:
    data_dir = Path(tempfile.mkdtemp(prefix=f"phone_shot_{state_name}_"))
    proc, base_url, pair_code = _start_fake_server(login_payload, data_dir)
    try:
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        page = ctx.new_page()
        c_errs, p_errs, r_fails = _attach_error_listeners(page)
        page.goto(base_url + "/", wait_until="networkidle")
        page.fill("#pair-code", pair_code)
        page.click("#btn-pair")
        page.wait_for_selector("#app:not([hidden])", timeout=10000)
        page.wait_for_selector("#today-items .row", timeout=10000)
        shot_path = SHOTS_DIR / f"phone-{state_name}.png"
        page.screenshot(path=str(shot_path), full_page=True)
        extra: dict[str, str] = {}
        if state_name == "never":
            page.click("#btn-banner-relogin")
            page.wait_for_selector("#relogin-panel:not([hidden])", timeout=10000)
            page.wait_for_timeout(300)
            extra["sheet_title"] = page.text_content("#sheet-title") or ""
            page.screenshot(path=str(SHOTS_DIR / "phone-never-relogin.png"), full_page=True)
        summary = {
            "state": state_name,
            "banner_hidden": page.is_hidden("#login-expired-banner"),
            "banner_title": page.text_content("#login-expired-title") or "",
            "bar_sub": page.text_content("#bar-sub") or "",
            "start_text": page.text_content("#btn-start") or "",
            "console_errors": c_errs, "page_errors": p_errs, "request_failures": r_fails,
            **extra,
        }
        ctx.close()
        return summary
    finally:
        _stop_fake_server(proc)
        shutil.rmtree(data_dir, ignore_errors=True)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/favicon.ico" and not (PROTO_DIR / "favicon.ico").exists():
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format, *args):
        return


def _capture_prototype_boards(browser) -> list[dict]:
    if not (PROTO_DIR / "support.js").exists():
        return []
    handler = functools.partial(_QuietHandler, directory=str(PROTO_DIR))
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            boards = [
                ("PhoneNever.dc.html", "proto-phone-never.png"),
                ("PhoneLoginUnknown.dc.html", "proto-phone-login-unknown.png"),
                ("PhoneExpired.dc.html", "proto-phone-expired.png"),
            ]
            results: list[dict] = []
            for html_name, out_name in boards:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                page = ctx.new_page()
                c_errs, p_errs, r_fails = _attach_error_listeners(page)
                page.goto(f"http://127.0.0.1:{port}/{html_name}", wait_until="networkidle")
                page.wait_for_selector(".m .top", timeout=10000)
                page.screenshot(path=str(SHOTS_DIR / out_name), full_page=True)
                results.append({
                    "board": html_name, "shot": out_name,
                    "console_errors": c_errs, "page_errors": p_errs, "request_failures": r_fails,
                })
                ctx.close()
            return results
        finally:
            httpd.shutdown()


def main() -> int:
    from playwright.sync_api import sync_playwright

    for key in PROXY_VARS:
        os.environ.pop(key, None)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True)
        try:
            phone_res = [
                _capture_phone_state(browser, name, payload)
                for name, payload in LOGIN_SNAPSHOTS.items()
            ]
            proto_res = _capture_prototype_boards(browser)
        finally:
            browser.close()

    all_errs = [
        item for item in (phone_res + proto_res)
        if item["console_errors"] or item["page_errors"] or item["request_failures"]
    ]
    print(json.dumps({"phone": phone_res, "prototype": proto_res}, ensure_ascii=False, indent=2))
    return 1 if all_errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
