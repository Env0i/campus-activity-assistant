#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""到点自动报名（单账号）。

背景：活动名额在开放瞬间被抢光，人工点太慢。本脚本在报名开放前把详情页加载好，
到点自动点「立即报名 → 确定」，成功后私聊发卡片通知。

边界：
- 只操作 session.json 里那一个账号，不代他人报名；
- 只在传入的单个 activity-id 上动作，不批量扫活动；
- 失败不无限重试：默认 120 秒窗口，之后放弃并私聊告知失败原因；
  连续 404 视为接口未就绪，退避重试并把窗口自适应延长（起点起最长 25 分钟），
  传入 --sign-end 时报名截止是硬上限，扩窗绝不越过它；
- 不记录 token、姓名、学号；日志只留结果分类与时间。

提交节奏与本机 local/grab.py 共用同一套阶段/字段契约（独立实现，互不导入）：
开放后 0~1.6 秒黄金风暴（最多 10 轮、间隔 90ms）→ 常规全速（180ms）→
连续 3 次 404 自适应退避（1.6 倍、上限 3 秒）。每笔真实请求唯一记账，
响应按 request 归属结算，乱序合法；未决不伪造成失败，停止时如实报未确认。

用法：
  python3 grab_signup.py --activity-id <id> --at "2026-10-22 00:59:59" \
      --name "活动名" [--lead 100] [--window 120] [--sign-end "2026-10-23 23:59:59"] \
      [--dry-run]

@author Author
"""
import argparse
import os
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

# 按文件路径直接加载或运行时，先把同目录模块加入 sys.path
_SIGNUP_DIR = os.path.dirname(os.path.abspath(__file__))
if _SIGNUP_DIR not in sys.path:
    sys.path.insert(0, _SIGNUP_DIR)

import signup_io as _signup_io  # noqa: E402
import signup_loop as _signup_loop  # noqa: E402
from signup_io import UA, wait_until  # noqa: E402
from signup_policy import (  # noqa: E402
    ADAPTIVE_WINDOW_S,
    BACKOFF_FACTOR,
    BACKOFF_MAX_S,
    BurstPolicy,
    FULL_SPEED_INTERVAL_S,
    GOLDEN_INTERVAL_S,
    GOLDEN_ROUNDS,
    GOLDEN_WINDOW_S,
    NOT_READY_404_LIMIT,
    classify_response as _classify_response,
)

LOGIN_DIR = os.environ.get("LOGIN_DIR", "").strip() or "/root/campus-login"
APP_DIR = os.environ.get("APP_DIR", "").strip() or "/root/campus-activity-watch"
STATE_FILE = os.path.join(LOGIN_DIR, "storage_state.json")
SESSION_FILE = os.path.join(APP_DIR, "data", "session.json")
# 测试用 GRAB_LOG_FILE 重定向日志落点，绝不写真实 /root/campus-login
LOG_FILE = os.path.join(LOGIN_DIR, "grab_signup.log")
sys.path.insert(0, os.path.join(APP_DIR, "scripts", "lib"))
from site_target import BASE_URL as SCHOOL_ORIGIN  # noqa: E402
from site_target import CONFIGURED as SITE_CONFIGURED  # noqa: E402
from site_target import CONFIG_MESSAGE as SITE_CONFIG_MESSAGE  # noqa: E402

API = SCHOOL_ORIGIN + "/dr/api"
REFERER = SCHOOL_ORIGIN + "/stu/"
# 开放前多少秒开始逐次看按钮：名额放开往往只有几秒窗口，
# 等到开放前一秒再刷新会丢掉首轮点击时机。
POLL_LEAD = 5.0


def log(msg):
    _signup_io.write_log(msg, LOG_FILE)


def _token():
    return _signup_io.read_token(SESSION_FILE)


def _post(path, payload=None, token=""):
    return _signup_io.post_json(API, path, payload=payload, token=token,
                                referer=REFERER, ua=UA)


def is_joined(act_id):
    """getJoinInfo：未报名时 data 为 null，报名后 data 是对象。"""
    return _signup_io.check_joined(act_id, post_fn=_post, token_fn=_token)


def ensure_token():
    """报名前确认 token 可用；失效就先跑一次自动登录。"""
    return _signup_io.ensure_valid_token(LOGIN_DIR, log)


def notify(title, lines, template="green"):
    """私聊发交互卡片：优先用 users.json 里登记的 p2p chat_id；
    没登记（owner 还没私聊过机器人）就直接按 open_id 发，避免静默退化到群发。"""
    return _signup_io.send_owner_notify(title, lines, template=template, log_fn=log)


def detail_url(act_id):
    return _signup_io.build_detail_url(SCHOOL_ORIGIN, act_id)


def run_submit_loop(page, *, activity_id, at_ts, window_s, sign_end_ts=None,
                    max_attempts=0, is_joined_fn=None, notify_fn=None,
                    clock=None, log_fn=None, name="活动"):
    return _signup_loop.run_submit_loop(
        page, activity_id=activity_id, at_ts=at_ts, window_s=window_s,
        sign_end_ts=sign_end_ts, max_attempts=max_attempts,
        is_joined_fn=is_joined_fn, notify_fn=notify_fn, clock=clock,
        log_fn=log_fn, name=name,
        default_log_fn=log, default_notify_fn=notify,
        classify_fn=_classify_response,
    )


def _parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity-id", required=True)
    ap.add_argument("--at", required=True, help="报名开始时间，如 2026-10-22 00:59:59")
    ap.add_argument("--name", default="活动")
    ap.add_argument("--lead", type=float, default=100, help="提前多少秒打开页面")
    ap.add_argument("--window", type=float, default=120, help="开放后最多尝试多少秒")
    ap.add_argument("--sign-end", default="", help="报名截止时间（硬上限），如 2026-10-23 23:59:59")
    ap.add_argument("--dry-run", action="store_true", help="只检查页面与按钮，不点击")
    return ap.parse_args()


def _run_browser_signup(args, at, sign_end_ts):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            ctx = browser.new_context(locale="zh-CN",
                                      viewport={"width": 1366, "height": 900},
                                      storage_state=STATE_FILE)
            page = ctx.new_page()
            page.goto(detail_url(args.activity_id), wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            log("[i] 详情页已加载，等待 %s 开放报名" % args.at)

            if args.dry_run:
                btns = page.eval_on_selector_all(
                    "uni-button", "els=>els.map(e=>e.innerText.trim()).filter(Boolean)")
                log("[i] dry-run：joined=%s buttons=%s" % (is_joined(args.activity_id), btns))
                return 0

            if is_joined(args.activity_id):
                log("[i] 该活动已是报名状态，跳过提交")
                notify("已报名", ["**%s**" % args.name, "此前已报名，本次未重复提交"], "blue")
                return 0

            wait_until(at - POLL_LEAD)

            # 终态收口（含 owner 私聊结论）统一在循环内完成，这里只映射退出码
            stop_reason, state = run_submit_loop(
                page, activity_id=args.activity_id, at_ts=at,
                window_s=args.window, sign_end_ts=sign_end_ts,
                is_joined_fn=is_joined, notify_fn=notify, name=args.name)

            if stop_reason in ("success", "already_signed"):
                return 0
            if stop_reason == "login_invalid":
                return 3
            return 2
        finally:
            browser.close()


def main():
    args = _parse_args()
    if not SITE_CONFIGURED:
        print("[x] %s" % SITE_CONFIG_MESSAGE)
        return 2

    at = datetime.strptime(args.at, "%Y-%m-%d %H:%M:%S").timestamp()
    start = at - args.lead
    sign_end_ts = None
    if str(args.sign_end or "").strip():
        sign_end_ts = datetime.strptime(args.sign_end.strip(), "%Y-%m-%d %H:%M:%S").timestamp()
    if args.dry_run:  # 自测不等开放时间，立刻检查页面状态
        start = time.time()

    if not ensure_token():
        log("[x] 登录态不可用，放弃本次报名")
        notify("自动报名未执行", ["**%s**" % args.name, "登录态无法恢复，需要人工检查"], "red")
        return 3

    wait_until(start)
    return _run_browser_signup(args, at, sign_end_ts)


if __name__ == "__main__":
    sys.exit(main())
