# -*- coding: utf-8 -*-
"""登录命令编排：交互浏览器登录、手机重登中继与 localStorage 登录态整理。

从 grab.py 的 cmd_login / _cmd_login_relay / page_local_storage / session_from_items 搬出；
Playwright 与 login_relay 的延迟导入及全局名字读取仍留在 grab.py 每次调用时装配后传入，
本模块不 import grab、playwright 或 login_relay。

@author Author
"""
from __future__ import annotations

import json
import secrets
from datetime import datetime


def page_local_storage(page):
    return page.evaluate(
        "() => { const o = {}; for (let i = 0; i < localStorage.length; i++) {"
        " const k = localStorage.key(i); o[k] = localStorage.getItem(k); } return o; }")


def session_from_items(items):
    """localStorage -> session.json（与服务器侧字段保持一致）。"""
    session = {"token": str(items.get("xgUniToken") or "").strip(),
               "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "name": "", "student_no": "", "gender": ""}
    try:
        user = json.loads(items.get("user") or "{}")
    except Exception:
        user = {}
    if isinstance(user, dict):
        session["name"] = str(user.get("xm") or "")
        session["student_no"] = str(user.get("xh") or "")
        session["gender"] = str(user.get("xb") or "")
    session["name"] = session["name"] or str(items.get("xm") or "")
    return session


class _RelayDeps:
    """手机重登中继依赖适配器：按调用时传入的端口访问时钟、浏览器、请求与落盘。"""

    def __init__(self, *, base, login_hash, time_mod, start_playwright,
                 launch_browser, new_context, post, save_verified_files):
        self.login_url = base + "/stu/" + login_hash
        self._pw = None
        self._time = time_mod
        self._start_playwright = start_playwright
        self._launch_browser = launch_browser
        self._new_context = new_context
        self._post = post
        self._save_verified_files = save_verified_files

    def now(self):
        return self._time.monotonic()

    def sleep(self, seconds):
        self._time.sleep(seconds)

    def new_id(self):
        return secrets.token_hex(8)

    def open_page(self):
        self._pw = self._start_playwright()
        browser = self._launch_browser(self._pw, headless=True)
        ctx = self._new_context(browser, with_state=False)
        return ctx.new_page(), ctx, browser

    def post(self, path, payload, tok):
        return self._post(path, payload, tok)

    def save_verified(self, state, session):
        # 两文件的事务端口：一起落位，失败回滚到保存前状态
        session["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_verified_files(state, session)


def run_login_relay(args, *, run_http_relay, ensure_data_dir, base, login_hash,
                    time_mod, start_playwright, launch_browser, new_context,
                    post, save_verified_files, stdin, stdout):
    """手机重登中继模式：HTTP 主路径 + Playwright 一次性兜底。

    默认 cmd_login 行为完全不变；只有显式 --relay 才走这条路径。stdin/
    stdout 仍是同一套 [login] JSON 行协议；HTTP 契约不符时凭据留内存切
    Playwright（页面自己发 captcha/login），网络错误安全失败不切换。
    凭据从 stdin 收一次用完即弃，stdout 只有 [login] 安全 JSON 行（决策 5）。
    """
    ensure_data_dir()
    deps = _RelayDeps(
        base=base, login_hash=login_hash, time_mod=time_mod,
        start_playwright=start_playwright, launch_browser=launch_browser,
        new_context=new_context, post=post, save_verified_files=save_verified_files)
    return run_http_relay(deps=deps, stdin=stdin, stdout=stdout, pw_deps=deps)


def _wait_for_token(page, browser, timeout_s, login_started, *, time_mod, log_event):
    """轮询登录页 localStorage 直到拿到 token、关窗或超时；返回 (tok, err_code)。"""
    deadline = time_mod.time() + timeout_s
    tok = ""
    while time_mod.time() < deadline:
        try:
            if page.is_closed():
                print("[X] 窗口被关掉了，登录未完成。")
                browser.close()
                log_event("login_failed", "cli", level="WARN", reason="window_closed",
                          elapsed_s=time_mod.monotonic() - login_started)
                return "", 1
            tok = page.evaluate(
                "() => (localStorage.getItem('xgUniToken') || '').trim()")
        except Exception:
            tok = ""
        if tok:
            return tok, 0
        time_mod.sleep(1.0)
    print("[X] 等了 %d 秒仍未检测到登录成功，请重试。" % timeout_s)
    browser.close()
    log_event("login_failed", "cli", level="WARN", reason="timeout",
              elapsed_s=time_mod.monotonic() - login_started)
    return "", 1


def _persist_and_verify(items, state, tok, login_started, *,
                        save_verified_files, check_token, log_event, time_mod):
    """事务写入双文件登录态、校验接口可用并返回进程退出码。"""
    session = session_from_items(items)
    session["token"] = tok
    try:
        # 两文件一笔事务：第二份失败时回滚，不留新旧混合的登录态
        save_verified_files(state, session)
    except OSError:
        print("[X] 登录成功，但登录态没能写入（另一个进程正在写），请稍后重新登录。")
        log_event("login_failed", "cli", level="ERROR", reason="session_not_saved",
                  elapsed_s=time_mod.monotonic() - login_started)
        return 2

    ok, msg = check_token()
    if not ok:
        print("[X] 已保存登录态，但接口校验失败：%s" % msg)
        log_event("login_failed", "cli", level="ERROR", reason="verify_failed",
                  elapsed_s=time_mod.monotonic() - login_started)
        return 2
    print("[OK] 登录成功，登录态已保存（失效后重新运行本步即可）。")
    log_event("login_ok", "cli", elapsed_s=time_mod.monotonic() - login_started)
    return 0


def run_login(args, *, sync_playwright, ensure_data_dir, launch_browser,
              new_context, base, login_hash, page_local_storage_fn,
              save_verified_files, check_token, log_event, time_mod):
    """可见浏览器登录全流程：开登录页、等登录成功、写双文件并校验接口。"""
    # login/check/list/grab 共用统一数据根；冻结进程首次会顺带迁移旧 EXE 旁数据
    ensure_data_dir()
    login_started = time_mod.monotonic()
    print("=" * 64)
    print("即将打开浏览器，请在窗口里完成学生登录（账号 + 密码 + 图形验证码）。")
    print("登录成功会自动保存登录态并关闭窗口；最多等待 %d 秒。" % args.timeout)
    print("=" * 64)

    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=False)
        ctx = new_context(browser, with_state=False)
        page = ctx.new_page()
        try:
            page.goto(base + "/stu/" + login_hash, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print("[X] 打不开登录页：%s" % type(exc).__name__)
            browser.close()
            log_event("login_failed", "cli", level="ERROR", reason="login_page_unreachable",
                      elapsed_s=time_mod.monotonic() - login_started)
            return 2

        tok, err_code = _wait_for_token(
            page, browser, args.timeout, login_started,
            time_mod=time_mod, log_event=log_event)
        if err_code:
            return err_code

        page.wait_for_timeout(1500)  # 等页面把 user / xm 写进 localStorage
        items = page_local_storage_fn(page)
        state = ctx.storage_state()
        ctx.close()
        browser.close()

    return _persist_and_verify(
        items, state, tok, login_started,
        save_verified_files=save_verified_files, check_token=check_token,
        log_event=log_event, time_mod=time_mod)
