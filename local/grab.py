#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校园活动「到点自动报名」—— 本机 Windows 版（单账号，不依赖服务器）。

用途：
    在报名开放瞬间自动点「立即报名 → 确定」，避免手速不够被抢光。

安全边界：
    - 只操作本机 data/session.json 里那一个账号，不代他人报名；
    - 密码不落盘：登录是在弹出的真实浏览器窗口里由你手动输入（含验证码），
      脚本只在登录成功后保存 cookie + localStorage（等价于浏览器"保持登录"）；
    - 日志不记录 token、姓名、学号、密码、验证码；
    - 只对传入的单个 activity-id 动作，不批量扫活动、不做任何超出报名的操作。

@author Author
"""

import argparse
import contextlib
import json  # noqa: F401 - 供测试替换/保持模块命名空间
import os
import sys
import time
import urllib.parse  # noqa: F401 - 保留 urllib.parse 子模块给测试与请求层
import urllib.request  # noqa: F401 - 保留 urllib.request 子模块给测试与通知层
from pathlib import Path
from types import SimpleNamespace

# 站点根地址来自 site_target：本机从 config.json 的 site.base 读真实域名，
# 仓库里只留占位值（公开树不含真实域名）
from infrastructure.school.site_target import BASE_URL as BASE, CONFIGURED as SITE_CONFIGURED
from infrastructure.school.site_target import CONFIG_MESSAGE as SITE_CONFIG_MESSAGE

API = BASE + "/dr/api"
REFERER = BASE + "/stu/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
RUNTIME_PROFILE_PATH = "/upms/security/runtime/profile"
REQUEST_SECURITY_RAW_KEY = "7afdca069faa4acb8c0ab09322636245"
REQUEST_SECURITY_CLIENT_KEY = "Pq3Zk2A9xML7"

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
from infrastructure.stores.runtime_paths import DATA_DIR as DATA  # noqa: F401
from infrastructure.stores.runtime_paths import LOG_FILE, LOG_LOCK_FILE, SESSION_FILE, STATE_FILE, ensure_data_dir
from infrastructure.stores.prefs_store import PrefsLockTimeout, acquire_file_lock, release_file_lock  # noqa: F401
from infrastructure.stores import login_session_store
from application.signup import signup_outcome, signup_policy, signup_run, signup_target
from application.worker import (worker_activity_list, worker_auth, worker_cancel,
                                worker_clock, worker_login, worker_runtime)
from domain.signup import retry_window, signup_reply
from domain.signup.cancel_rules import sanitize_message as sanitize_school_message
from domain.signup.retry_window import (
    ADAPTIVE_RETRY, ADAPTIVE_SECONDS, DEFAULT_RETRY_SECONDS,
    SUBMIT_BACKOFF_FACTOR, SUBMIT_BACKOFF_MAX_S, SUBMIT_BACKOFF_START_S, initial_deadline)
from domain.signup.signup_reply import (
    STALE_TS_LIMIT, TERMINAL_STOP_REASONS, UNKNOWN_REPLY_LIMIT,
    classify_signup_reply, stop_reason_label)
from domain.worker import worker_lines
from domain.worker.log_events import format_event_line
from infrastructure.school import activity_queries, school_http
from infrastructure.worker import worker_log
from infrastructure.clock.time_contract import (
    BudgetExhausted, RetryBudget, configure_time_source, default_now,
    parse_school_time, school_epoch, school_time_text)
from infrastructure.clock.business_clock import BusinessClock, ClockClient, ClockUnavailable

# 测试会把 grab.time 换成假时钟：计时段只能用导入时取好的别名，不能现取 grab.time
_perf_counter = time.perf_counter
CONFIG_FILE = HERE / "config.json"

# ---- 独立北京时间（决策 012）-----------------------------------------------
_CLOCK = {"now": None, "bounds": None, "meta": None}


def configure_business_clock(clock_like) -> None:
    worker_clock.configure_business_clock(
        _CLOCK, clock_like, configure_time_source=configure_time_source)


def business_now() -> float:
    return worker_clock.business_now(_CLOCK, clock_unavailable=ClockUnavailable)


def business_bounds():
    return worker_clock.business_bounds(_CLOCK, clock_unavailable=ClockUnavailable)


def clock_meta() -> dict:
    """checkpoint 附带的时钟元数据（无凭证）。"""
    return worker_clock.clock_meta(_CLOCK)


def setup_business_clock(allow_sync=True, timeout_s=3.0):
    """worker 读父进程快照；CLI 有界自校时。失败返回 None，由调用方显式处理。"""
    return worker_clock.setup_business_clock(
        env=os.environ, clock_client_cls=ClockClient,
        business_clock_cls=BusinessClock, clock_unavailable=ClockUnavailable,
        configure_fn=configure_business_clock,
        allow_sync=allow_sync, timeout_s=timeout_s)


DETAIL_HASH = ("#/secondClassroom/student/activity/studentActivity/"
               "activityDetails?activityId={aid}&from=acList")
LOGIN_HASH = "#/mainPages/login?userType=2"
PAGE_SIZE = 50
POLL_LEAD = 5.0


# ---------------------------------------------------------------- 基础工具
def setup_console():
    """Windows 控制台默认 GBK，中文/特殊符号会抛 UnicodeEncodeError，这里强制 UTF-8。"""
    worker_runtime.setup_console()


def _school_open(request, timeout=None):
    """学校请求统一走「不走代理」的 opener；调用时传入 grab.urllib 保留测试接缝。"""
    return school_http.school_open(request, urllib_mod=urllib, timeout=timeout)


LOG_MAX_BYTES = 5 * 1024 * 1024   # grab.log 超过这个大小就轮转（S2）
LOG_KEEP = 5                      # 保留 grab.log.1 … grab.log.5，更老的丢掉
LOG_LOCK_TIMEOUT_S = 2.0          # 拿不到日志锁就走 stderr/控制台降级，不能卡住 worker
_LOG_THREAD_LOCK = worker_log._LOG_THREAD_LOCK


@contextlib.contextmanager
def _log_file_lock(timeout_s=LOG_LOCK_TIMEOUT_S):
    """grab.log 的轮转与追加共用的跨进程锁（实现在 infrastructure.worker.worker_log）。"""
    with worker_log.log_file_lock(
        timeout_s=timeout_s, log_lock_file=LOG_LOCK_FILE,
        time_mod=time, thread_lock=_LOG_THREAD_LOCK,
    ):
        yield


def rotate_log_file(path, max_bytes=None, keep=None):
    """日志超过 max_bytes 就轮转；在调用时取当前 LOG_MAX_BYTES 与 LOG_KEEP。"""
    return worker_log.rotate_log_file(
        path, max_bytes=max_bytes, keep=keep,
        default_max_bytes=LOG_MAX_BYTES, default_keep=LOG_KEEP,
    )


def _stderr_note(text):
    """写日志自己出了问题时的出口：至少打到 stderr。"""
    worker_log.stderr_note(text)


@contextlib.contextmanager
def _stdout_to_stderr(enabled):
    """--json 的 stdout 是给主程序 json.loads 的：期间把 stdout 改道到 stderr。"""
    with worker_log.stdout_to_stderr(enabled):
        yield


def log(msg):
    """写一行运行日志；目录、业务时钟、锁、轮转与写入端口均在调用时取 grab 全局。"""
    worker_log.write_log(
        msg, ensure_dir_fn=ensure_data_dir, school_time_text_fn=school_time_text,
        business_now_fn=business_now, lock_ctx_fn=_log_file_lock,
        rotate_fn=rotate_log_file, log_file=LOG_FILE,
        append_fn=_append_log_line_unlocked, note_fn=_stderr_note,
    )


def _append_log_line_unlocked(line):
    worker_log.append_log_line_unlocked(line, log_file=LOG_FILE, note_fn=_stderr_note)


_EVENT_CONTEXT = {"activity_id": ""}


def log_event(event, source, level="INFO", activity_id="", **fields):
    """关键动作写一行结构化日志：北京时间（log() 补）、级别、来源、活动 ID、事件名。"""
    log(format_event_line(event, source, level=level,
                          activity_id=activity_id or _EVENT_CONTEXT["activity_id"],
                          fields=fields))


def read_json(path, default=None):
    """读 JSON：文件不存在静默回 default；读不出写一行日志再回 default。"""
    return worker_runtime.read_json(path, default, log_fn=log, opener=open)


# ---- 登录态写入（S5）---------------------------------------------------------
SESSION_LOCK_TIMEOUT_S = login_session_store.SESSION_LOCK_TIMEOUT_S
_session_write_lock = login_session_store.session_write_lock


def save_session(session, path=None, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录态 session.json 的唯一写入口；超时写日志并放弃（返回 False）。"""
    target = SESSION_FILE if path is None else Path(path)
    return login_session_store.save_session(session, target, log, timeout_s)


def save_storage_state(state, path=None, session_path=None, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """浏览器 cookie 文件（storage_state.json）：和 session.json 共用同一把写锁。"""
    target = STATE_FILE if path is None else Path(path)
    lock_for = SESSION_FILE if session_path is None else Path(session_path)
    return login_session_store.save_storage_state(state, target, lock_for, log, timeout_s)


def save_verified_files(state, session, state_path=None, session_path=None,
                        timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录成功后 state+session 双文件事务保存（HTTP 路径 save_verified 端口）。"""
    target = STATE_FILE if state_path is None else Path(state_path)
    lock_for = SESSION_FILE if session_path is None else Path(session_path)
    login_session_store.save_verified_files(
        state, session, target, lock_for, log, timeout_s, opener=open)


def token():
    sess = read_json(SESSION_FILE, {}) or {}
    return str(sess.get("token") or "").strip()


def _hmac_sha256_hex(message: bytes, key: bytes) -> str:
    return school_http.hmac_sha256_hex(message, key)


def _xor_base64(value: str, key: str) -> str:
    return school_http.xor_base64(value, key)


def _encode_x_token(signature_hex: str, path: str, nonce: str) -> str:
    return school_http.encode_x_token(
        signature_hex, path, nonce, client_key=REQUEST_SECURITY_CLIENT_KEY,
        hmac_fn=_hmac_sha256_hex, xor_fn=_xor_base64)


def sign_request_headers(path: str, body: bytes, timestamp_ms: int, nonce: str) -> dict:
    """按官网登录页 Z0 算法生成四个网关请求头（实现在 infrastructure.school.school_http）。"""
    return school_http.sign_request_headers(
        path, body, timestamp_ms, nonce,
        raw_key=REQUEST_SECURITY_RAW_KEY, client_key=REQUEST_SECURITY_CLIENT_KEY,
        hmac_fn=_hmac_sha256_hex, encode_fn=_encode_x_token)


def _request_nonce() -> str:
    return school_http.request_nonce(time_mod=time)


_SCHOOL_DATE = {"raw": "", "epoch": None}


def _remember_school_date(value) -> None:
    """记下最近一次学校回包的 Date 头；解析失败也留原文，epoch 置空。"""
    text, epoch = worker_lines.parse_http_date_epoch(value)
    if not text:
        return
    _SCHOOL_DATE["raw"] = text
    _SCHOOL_DATE["epoch"] = epoch


def school_date_now():
    """最近一次列表回包 Date 头的 epoch 秒；没有或解析不了返回 None。"""
    value = _SCHOOL_DATE.get("epoch")
    return float(value) if isinstance(value, (int, float)) else None


def clear_school_date() -> None:
    """清空 Date 记录：每轮列表开始前调用，避免拿上一轮的旧头凑数。"""
    _SCHOOL_DATE.update({"raw": "", "epoch": None})


def _post(path, payload=None, tok=None, timeout=None, budget=None):
    """POST/GET 共用入口；调用时从 grab 装配请求与签名端口以保留测试替身接缝。"""
    return school_http.school_post(
        path, payload=payload, tok=tok, timeout=timeout, budget=budget,
        api=API, referer=REFERER, ua=UA, get_token=token,
        sign_headers_fn=sign_request_headers, nonce_fn=_request_nonce,
        open_fn=_school_open, remember_date_fn=_remember_school_date,
        budget_exhausted_cls=BudgetExhausted, time_mod=time, urllib_mod=urllib)


def _get(path, tok=None, timeout=None):
    """GET 请求薄转发；每次调用从 grab 全局读取 token、_school_open 与 urllib。"""
    return school_http.school_get(
        path, tok=tok, timeout=timeout, api=API, referer=REFERER, ua=UA,
        get_token=token, open_fn=_school_open, urllib_mod=urllib)


def clock_sample(timeout_s=6.0):
    """HTTP Date 粗校时薄转发；调用时从 grab 传入 time 与 urllib。"""
    return school_http.clock_sample(
        timeout_s=timeout_s, base=BASE, ua=UA,
        open_fn=_school_open, time_mod=time, urllib_mod=urllib)


def clock_skew():
    """兼容旧调用：只取偏移估计；没有可信样本返回 None。"""
    return school_http.clock_skew(sample_fn=clock_sample)


# ---------------------------------------------------------------- 活动查询
CHECKIN_FLAG_NAMES = activity_queries.CHECKIN_FLAG_NAMES
CHECKOUT_FLAG_NAMES = activity_queries.CHECKOUT_FLAG_NAMES
POINTS_NAMES = activity_queries.POINTS_NAMES
WAGE_NAMES = activity_queries.WAGE_NAMES
CHECKIN_START_NAMES = activity_queries.CHECKIN_START_NAMES
CHECKIN_END_NAMES = activity_queries.CHECKIN_END_NAMES
CHECKOUT_START_NAMES = activity_queries.CHECKOUT_START_NAMES
CHECKOUT_END_NAMES = activity_queries.CHECKOUT_END_NAMES

DETAIL_CACHE = activity_queries.DETAIL_CACHE
DETAIL_CACHE_LOCK = activity_queries.DETAIL_CACHE_LOCK
DETAIL_CONCURRENCY = activity_queries.DETAIL_CONCURRENCY
DETAIL_TIMEOUT_S = activity_queries.DETAIL_TIMEOUT_S

_tri_state = activity_queries.tri_state
_detail_fields = activity_queries.detail_fields
_join_state = activity_queries.join_state
_apply_attendance = activity_queries.apply_attendance
_activity_flag = activity_queries.activity_flag


def _map_activity(raw):
    """学校列表接口的一条活动 → 本地字段结构；实现见 activity_queries。"""
    return activity_queries.map_activity(raw, school_epoch)


def parse_attendance_detail(raw):
    """把 getInfo 的签到/签退字段归一化；实现见 activity_queries。"""
    return activity_queries.parse_attendance_detail(raw, school_epoch)


def fetch_activity_detail(activity_id, timeout=DETAIL_TIMEOUT_S):
    """只读详情；失败返回 None（调用方显示「同步中」，不把失败当成无需）。"""
    return activity_queries.fetch_activity_detail(
        activity_id, _get, school_epoch, timeout=timeout)


def enrich_attendance_items(items, max_workers=DETAIL_CONCURRENCY):
    """按活动 id 去重并发补详情；单场失败不影响整张列表。"""
    return activity_queries.enrich_attendance_items(
        items, fetch_activity_detail, max_workers=max_workers)


def fetch_activities(budget=None, with_details=False):
    """分页拉活动列表；with_details=True 时按活动 id 去重并发补详情。"""
    rows = activity_queries.fetch_activities(_post, PAGE_SIZE, school_epoch, budget=budget)
    if with_details and rows:
        return enrich_attendance_items(rows)
    return rows


def is_joined(act_id, budget=None):
    """getJoinInfo 三态查询；判定口径与出处见 activity_queries.join_state。"""
    return activity_queries.is_joined(act_id, _post, budget=budget)


def parse_ts(text):
    """学校时间文本 → epoch 秒；非法时抛 ValueError。"""
    epoch = school_epoch(text)
    if epoch is None:
        raise ValueError("学校时间格式不正确：%r" % (text,))
    return epoch


def still_relevant(act, now=None):
    """报名还没截止（或没给截止时间）的活动才算「还值得看」；实现见 worker_activity_list。"""
    return worker_activity_list.still_relevant(act, now, parse_ts=parse_ts, default_now=default_now)


def keep_in_list(act, now):
    """列表默认保留谁；实现见 worker_activity_list。"""
    return worker_activity_list.keep_in_list(act, now, parse_ts=parse_ts)


def sign_state(act, now=None):
    """开放状态文案；实现见 worker_activity_list。"""
    return worker_activity_list.sign_state(act, now, parse_ts=parse_ts, default_now=default_now)


# ---------------------------------------------------------------- 浏览器
def launch_browser(pw, headless):
    """按「Chrome → Edge → 自带内核」的顺序找浏览器；实现见 worker_runtime。"""
    return worker_runtime.launch_browser(pw, headless)


def new_context(browser, with_state=True):
    """创建浏览器上下文；在调用时读取 STATE_FILE。"""
    return worker_runtime.new_context(browser, with_state=with_state, state_file=STATE_FILE)


def page_local_storage(page):
    """读取登录页 localStorage 键值；实现见 worker_login。"""
    return worker_login.page_local_storage(page)


def session_from_items(items):
    """localStorage -> session.json（与服务器侧字段保持一致）；实现见 worker_login。"""
    return worker_login.session_from_items(items)


# ---------------------------------------------------------------- 子命令
def _start_login_playwright():
    from playwright.sync_api import sync_playwright

    return sync_playwright().start()


def _cmd_login_relay(args):
    """手机重登中继模式转发：调用时导入 login_relay 并取本模块最新边界。"""
    from infrastructure.login import login_relay

    return worker_login.run_login_relay(
        args, run_http_relay=login_relay.run_http_relay,
        ensure_data_dir=ensure_data_dir, base=BASE, login_hash=LOGIN_HASH,
        time_mod=time, start_playwright=_start_login_playwright,
        launch_browser=launch_browser, new_context=new_context, post=_post,
        save_verified_files=save_verified_files, stdin=sys.stdin, stdout=sys.stdout)


def cmd_login(args):
    """登录子命令转发：在调用时导入 Playwright 并装配模块最新边界。"""
    if getattr(args, "relay", False):
        return _cmd_login_relay(args)
    from playwright.sync_api import sync_playwright

    return worker_login.run_login(
        args, sync_playwright=sync_playwright, ensure_data_dir=ensure_data_dir,
        launch_browser=launch_browser, new_context=new_context, base=BASE,
        login_hash=LOGIN_HASH, page_local_storage_fn=page_local_storage,
        save_verified_files=save_verified_files, check_token=check_token,
        log_event=log_event, time_mod=time)


def cmd_check(args):
    """登录态检查子命令转发；编排在 worker_auth。"""
    return worker_auth.run_check(
        args, check_token_fn=check_token, clock_sample_fn=clock_sample, log_fn=log)


def cmd_list(args):
    """列表命令的薄转发：编排在 application/worker/worker_activity_list。"""
    return worker_activity_list.run_list(
        args, check_token=check_token, fetch_activities=fetch_activities,
        enrich=enrich_attendance_items, business_now=business_now,
        clear_school_date=clear_school_date, school_date_now=school_date_now,
        clock_unavailable=ClockUnavailable, log=log,
        stdout_to_stderr=_stdout_to_stderr, note=_stderr_note,
        perf_counter=_perf_counter, page_size=PAGE_SIZE, parse_ts=parse_ts,
        keep_in_list=keep_in_list, sign_state=sign_state)


# ---------------------------------------------------------------- 取消报名（X2/X4）
CANCEL_PATH = "/rjyHdCyr/cancel/"
CANCEL_PRECHECK_BUDGET_S = 20.0
CANCEL_RECHECK_BUDGET_S = 10.0


def _cancel_facts(act_id):
    """取消前要看的详情：(cancel_allowed, sign_start, sign_end) 或 None。"""
    return worker_cancel.cancel_facts(
        act_id, get_fn=_get, detail_timeout_s=DETAIL_TIMEOUT_S,
        detail_fields_fn=_detail_fields, tri_state_fn=_tri_state,
        school_epoch_fn=school_epoch)


def _cancel_joined(act_id, budget_s):
    """取消前后用的三态查询：True / False / None（含预算用尽、校时失效）。"""
    return worker_cancel.cancel_joined(
        act_id, budget_s, business_now_fn=business_now,
        make_budget_fn=lambda deadline: RetryBudget(deadline, business_clock=_CLOCK["meta"]),
        is_joined_fn=is_joined, budget_exhausted_cls=BudgetExhausted,
        clock_unavailable=ClockUnavailable)


def run_cancel(act_id, progress=None):
    """取消报名转发：在调用时从本模块全局取最新边界并交给 worker_cancel 执行。"""
    return worker_cancel.run_cancel(
        act_id, progress, site_configured=SITE_CONFIGURED,
        probe_token=probe_token, business_now=business_now,
        has_clock_meta=lambda: _CLOCK.get("meta") is not None,
        cancel_joined=_cancel_joined, cancel_facts=_cancel_facts,
        get=_get, log=log, cancel_path=CANCEL_PATH,
        precheck_budget_s=CANCEL_PRECHECK_BUDGET_S,
        recheck_budget_s=CANCEL_RECHECK_BUDGET_S,
        clock_unavailable=ClockUnavailable,
        sanitize_message=sanitize_school_message)


def cmd_cancel(args):
    """取消子命令转发；编排在 worker_cancel。"""
    return worker_cancel.run_cmd_cancel(
        args, stdout_to_stderr_fn=_stdout_to_stderr,
        run_cancel_fn=run_cancel, log_fn=log)


def candidates(acts, now=None):
    """可抢的活动筛选转发；编排在 signup_target。"""
    return signup_target.candidates(
        acts, now, default_now=default_now, still_relevant=still_relevant, parse_ts=parse_ts)


def pick_activity(acts, now=None):
    """交互式挑活动转发；编排在 signup_target。"""
    return signup_target.pick_activity(acts, now, candidates_fn=candidates)


def notify(title, lines, template="green"):
    """可选飞书群机器人通知转发；在调用时读取 CONFIG_FILE、urllib 与 log。"""
    return worker_runtime.notify(
        title, lines, template=template, read_json_fn=read_json,
        config_file=CONFIG_FILE, urllib_mod=urllib, log_fn=log)


def wait_until(ts, budget=None):
    """等到指定墙钟时刻转发；在调用时取 business_now、BudgetExhausted 与 time。"""
    return worker_clock.wait_until(
        ts, budget=budget, business_now_fn=business_now,
        budget_exhausted_cls=BudgetExhausted, time_mod=time)


def _by_index_or_name(cand, args):
    return signup_target.by_index_or_name(cand, args)


def _at_or_now(at_text):
    return signup_target.at_or_now(
        at_text, parse_ts=parse_ts, business_now=business_now,
        school_time_text=school_time_text)


def resolve_target(args, budget=None):
    """确定目标活动转发；编排在 signup_target。"""
    return signup_target.resolve_target(
        args, budget, fetch_activities=fetch_activities,
        candidates_fn=candidates, by_index_or_name_fn=_by_index_or_name,
        pick_activity_fn=pick_activity, at_or_now_fn=_at_or_now)


def retry_anchor(at_ts, now=None):
    """重试窗口起算点转发；实现在 domain.signup.retry_window。"""
    return retry_window.retry_anchor(at_ts, default_now() if now is None else now)


DEFAULT_RETRY_WINDOW_S = DEFAULT_RETRY_SECONDS


def compute_retry_window(at_ts, sign_end_ts, retry_for_s, now=None):
    """计算重试起算点与有效截止转发；实现在 domain.signup.retry_window。"""
    return retry_window.compute_retry_window(
        at_ts, sign_end_ts, retry_for_s, default_now() if now is None else now)


def attempts_allowed(attempts: int, max_attempts: int) -> bool:
    """max_attempts=0 表示不限；实现在 domain.signup.retry_window。"""
    return retry_window.attempts_allowed(attempts, max_attempts)


def next_submit_gap(current: float) -> float:
    """返回下一次提交前的等待秒数；实现在 domain.signup.retry_window。"""
    return retry_window.next_submit_gap(current)


def wait_before_next_submit(budget, gap: float) -> float:
    """按剩余预算截断等待转发；实现在 application.signup.signup_policy。"""
    return signup_policy.wait_before_next_submit(
        budget, gap, clock_unavailable=ClockUnavailable, next_gap_fn=next_submit_gap)


from application.signup.signup_policy import (  # noqa: E402
    ADAPTIVE_IN_GOLDEN, ADAPTIVE_WINDOW_S, BACKOFF_FACTOR, BACKOFF_MAX_S,
    FULL_SPEED_INTERVAL_S, GOLDEN_INTERVAL_S, GOLDEN_ROUNDS, GOLDEN_WINDOW_S,
    INFLIGHT_TTL_S, NOT_READY_404_LIMIT, NOT_READY_SLOWDOWN_AFTER_S,
    NOT_READY_SLOW_GAP_S, SERVER_ERROR_MIN_GAP_S)
MAX_INFLIGHT = 2
FINAL_CHECK_S = 3.0
LOGIN_RECHECK_S = 1.5
PRECHECK_AHEAD_S = 45.0
PRECHECK_MIN_LEAD_S = 30.0
PRECHECK_WAIT_S = 9.0
OPEN_GRACE_S = 3.0
INFLIGHT_WAIT_S = 0.05
CONFIRM_INFLIGHT_WAIT_S = 1.0


class BurstPolicy(signup_policy.BurstPolicy):
    """绑定 grab 当前日志函数与 ClockUnavailable 异常的提交节奏状态机。"""

    _clock_error = ClockUnavailable

    def _log(self, msg):
        log(msg)


def _classify_response(response):
    return signup_reply.classify_http_response(response)


def _decode_body(raw):
    return signup_reply.decode_reply_body(raw)


def _recognizable_code(value):
    return signup_reply.recognizable_code(value)


def _ts_text(ts) -> str:
    return worker_lines.format_ts_text(ts, school_time_text)


def _checkpoint_event(kind, at=None):
    return worker_clock.checkpoint_event(
        kind, at=at, business_now_fn=business_now, clock_meta_fn=clock_meta,
        clock_unavailable=ClockUnavailable, log_fn=log)


def _retry_event(**fields):
    return worker_clock.retry_event(log_fn=log, **fields)


PREFLIGHT_BUDGET_S = 30.0
_SubmitAborted = signup_outcome.SubmitAborted


def _probe_list(tok, budget=None):
    return worker_auth.probe_list(tok, budget=budget, post_fn=_post)


def _direct_headers(tok):
    return signup_reply.direct_headers(tok, REFERER, UA)


def fetch_runtime_key(budget=None):
    """运行时密钥读取转发；在调用时导入 parse_runtime_key 并取 grab._post/token。"""
    from infrastructure.signup.signup_signing import parse_runtime_key

    return worker_auth.fetch_runtime_key(
        budget=budget, post_fn=_post, token_fn=token,
        runtime_profile_path=RUNTIME_PROFILE_PATH,
        parse_runtime_key_fn=parse_runtime_key,
        budget_exhausted_cls=BudgetExhausted, clock_unavailable=ClockUnavailable)


def probe_token(budget=None):
    """登录探测四态转发；在调用时取 grab.token/_probe_list/time/log。"""
    return worker_auth.probe_token(
        budget=budget, token_fn=token, probe_list_fn=_probe_list,
        login_recheck_s=LOGIN_RECHECK_S, time_mod=time, log_fn=log)


def check_token(budget=None):
    """登录态有效判定转发；调用 grab.probe_token。"""
    return worker_auth.check_token(budget=budget, probe_token_fn=probe_token)


def _known_policy_start(args):
    return retry_window.known_policy_start(args)


def _policy_window(start, sign_end_ts, retry_for):
    _, deadline, binding = compute_retry_window(start, sign_end_ts, retry_for, now=start)
    return deadline, binding


REPLY_STOP_HINTS = signup_outcome.REPLY_STOP_HINTS

_SIGNUP_PORT_NAMES = (
    "ADAPTIVE_RETRY", "API", "BASE", "BudgetExhausted", "BurstPolicy",
    "CONFIRM_INFLIGHT_WAIT_S", "ClockUnavailable", "DETAIL_HASH", "FINAL_CHECK_S",
    "INFLIGHT_WAIT_S", "MAX_INFLIGHT", "OPEN_GRACE_S", "POLL_LEAD",
    "PRECHECK_AHEAD_S", "PRECHECK_MIN_LEAD_S", "PRECHECK_WAIT_S",
    "PREFLIGHT_BUDGET_S", "RetryBudget", "_EVENT_CONTEXT", "_checkpoint_event",
    "_classify_response", "_decode_body", "_direct_headers",
    "_known_policy_start", "_policy_window", "_recognizable_code", "_retry_event",
    "_ts_text", "business_bounds", "business_now", "clock_sample",
    "fetch_runtime_key", "is_joined", "launch_browser", "log", "new_context",
    "notify", "os", "parse_ts", "probe_token", "resolve_target", "retry_anchor",
    "school_time_text", "setup_business_clock", "time", "token", "wait_until",
)


def _load_direct_modules():
    """拿到运行时密钥后才延迟导入签名与传输模块；导入失败退回点击兜底。"""
    try:
        from infrastructure.signup.signup_signing import build_signup_hash
        from infrastructure.signup.signup_transport import DirectTransport
    except Exception:  # noqa: BLE001
        return None, None
    return build_signup_hash, DirectTransport


def cmd_grab(args):
    """报名命令的薄转发：在调用时导入 Playwright 并从当前模块全局装配端口。"""
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    g = globals()
    ports = SimpleNamespace(**{name: g[name] for name in _SIGNUP_PORT_NAMES})
    ports.sync_playwright = sync_playwright
    ports.PlaywrightTimeoutError = PlaywrightTimeoutError
    ports.load_direct_modules = _load_direct_modules
    return signup_run.run_signup(args, ports)


def cmd_selftest(args):
    """自检命令转发；在调用时导入 Playwright 并取 grab.launch_browser/new_context/BASE。"""
    from playwright.sync_api import sync_playwright

    return worker_runtime.run_selftest(
        args, sync_playwright=sync_playwright, launch_browser_fn=launch_browser,
        new_context_fn=new_context, base=BASE)


def main():
    setup_console()
    ensure_data_dir()
    ap = argparse.ArgumentParser(
        description="校园活动到点自动报名（本机版，单账号）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python grab.py login\n"
               "  python grab.py list\n"
               "  python grab.py grab\n"
               "  python grab.py grab --activity-id 2ae75dd103654543b1a8b97053adf4a6 "
               "--at \"2026-10-22 00:59:59\" --name \"网络安全·数字时代大长城\"")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("login", help="打开浏览器手动登录一次，保存登录态")
    p.add_argument("--timeout", type=int, default=600, help="等待登录的秒数，默认 600")
    p.add_argument("--relay", action="store_true",
                   help="内部：手机重登中继模式（headless + stdin/stdout JSON 行）")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("check", help="检查登录态是否有效")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("list", help="列出活动与报名开始时间")
    p.add_argument("--all", action="store_true", help="连已报名的也列出来")
    p.add_argument("--json", action="store_true", help="输出 JSON（给图形界面调用）")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("cancel", help="取消一场已报名的活动（复查为准；stdout 只有一行 JSON）")
    p.add_argument("--id", required=True, help="活动 id（只取消这一场）")
    p.add_argument("--json", action="store_true",
                   help="输出 JSON（本子命令恒只输出一行 JSON，给图形界面调用）")
    p.set_defaults(func=cmd_cancel)

    worker_runtime.add_grab_parser(sub, cmd_grab)

    p = sub.add_parser("selftest", help="自检浏览器与网络")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args()
    if not SITE_CONFIGURED and args.cmd != "cancel":
        print("[X] %s" % SITE_CONFIG_MESSAGE)
        return 2
    if args.cmd in ("check", "list", "cancel"):
        setup_business_clock(allow_sync=True)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[i] 已手动中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
