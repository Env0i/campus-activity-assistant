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

用法：
    python grab.py login                     # 首次/登录态失效后：弹出浏览器手动登录一次
    python grab.py check                     # 检查登录态是否还有效
    python grab.py list                      # 列出可报名的活动（含活动 id、报名开始时间）
    python grab.py grab                      # 交互式：从列表里挑一个，到点自动报名
    python grab.py grab --activity-id <id> --at "2026-10-22 00:59:59" --name "活动名"
    python grab.py selftest                  # 自检：能否拉起浏览器并打开站点

@author Author
"""

import argparse
import base64
import contextlib
import functools
import hashlib
import hmac
import json
import math
import os
import queue
import secrets
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

# 站点根地址来自 site_target：本机从 config.json 的 site.base 读真实域名，
# 仓库里只留占位值（公开树不含真实域名）
from site_target import BASE_URL as BASE, CONFIGURED as SITE_CONFIGURED
from site_target import CONFIG_MESSAGE as SITE_CONFIG_MESSAGE

API = BASE + "/dr/api"
REFERER = BASE + "/stu/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
# 直发密钥来源（决策 015）：每场向学校取运行时密钥，不再按页面入口脚本文件名判断要不要直发
RUNTIME_PROFILE_PATH = "/upms/security/runtime/profile"

# 官网入口脚本公开的请求安全参数。签名只保护请求完整性，不替代登录态 token；
# 页面脚本更新后若更换 requestSecurityRawKey，必须重新核对并更新这组常量。
REQUEST_SECURITY_RAW_KEY = "7afdca069faa4acb8c0ab09322636245"
REQUEST_SECURITY_CLIENT_KEY = "Pq3Zk2A9xML7"

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
# 登录态/偏好统一走 runtime_paths：开发与绿色版仍是脚本旁 data，
# 冻结 worker 默认 %LOCALAPPDATA%（CAMPUS_DATA_DIR 可覆盖），与主程序同一根
from runtime_paths import DATA_DIR as DATA
from runtime_paths import LOG_FILE, LOG_LOCK_FILE, SESSION_FILE, STATE_FILE, ensure_data_dir
# 登录态写入的跨进程锁：沿用 ui.json.lock 用的同一对加解锁函数（标准库实现，S5）
from infrastructure.prefs_store import (PrefsLockTimeout, acquire_file_lock,
                                        release_file_lock)
# 登录态落盘（S5）：共用写锁、单写、双文件事务、暂存清理与字节回滚都在这个模块，
# 下面的 save_* 只保留旧签名并接线；静态 import 也是冻结分析发现该模块的入口
from infrastructure import login_session_store
# 列表命令的用例编排（20261119 计划）：登录探测、列表查询、时间选择、筛选排序、
# 详情和输出都在 application/worker_activity_list.py；下面的 cmd_list 只做转发
from application import signup_outcome, signup_run, worker_activity_list
# 活动读取实现（决策 005 / 016）：静态 import 也是冻结分析发现该模块的唯一入口，
# 动态替换的请求函数与学校时间解析由下面的薄转发在调用时注入
from infrastructure import activity_queries
# 学校时间与重试预算只有一份实现（time_contract）：这里不再自己 strptime，
# 否则同一串学校时间在 CLI、GUI、JS 三处会解析成不同 epoch
from time_contract import (BudgetExhausted, RetryBudget, parse_school_time,
                           school_epoch, school_time_text, default_now,
                           configure_time_source)
# 独立北京时间（决策 012）：worker 读父进程快照，CLI 有界自校时；
# 任何失败都不回退系统墙钟，也不把校时失败说成登录失效
from business_clock import BusinessClock, ClockClient, ClockUnavailable
# 测试会把 grab.time 换成假时钟：计时段只能用导入时取好的别名，不能现取 grab.time
_perf_counter = time.perf_counter
CONFIG_FILE = HERE / "config.json"

# ---- 独立北京时间（决策 012）-----------------------------------------------
# worker 模式：父进程把 CAMPUS_CLOCK_SNAPSHOT/CAMPUS_CLOCK_OWNER 传进来，只读快照；
# CLI 模式：自带 BusinessClock 做一次有界同步。失败显式处理，绝不回退本机墙钟。
_CLOCK = {"now": None, "bounds": None, "meta": None}


def configure_business_clock(clock_like) -> None:
    _CLOCK["now"] = clock_like.now
    _CLOCK["bounds"] = clock_like.bounds
    _CLOCK["meta"] = clock_like
    configure_time_source(clock_like.now)   # signup_plan 的缺省 now 同源


def business_now() -> float:
    fn = _CLOCK.get("now")
    if fn is None:
        raise ClockUnavailable("业务时钟未配置")
    return float(fn())


def business_bounds():
    fn = _CLOCK.get("bounds")
    if fn is None:
        raise ClockUnavailable("业务时钟未配置")
    return fn()


def clock_meta() -> dict:
    """checkpoint 附带的时钟元数据（无凭证）。"""
    meta = _CLOCK.get("meta")
    if meta is None:
        return {}
    try:
        return {"owner_id": getattr(meta, "owner_id", ""),
                "generation": getattr(meta, "generation", 0),
                "uncertainty_s": round(float(meta.bounds()[1] - meta.bounds()[0]) / 2, 3)}
    except Exception:
        return {}


def setup_business_clock(allow_sync=True, timeout_s=3.0):
    """worker 读父进程快照；CLI 有界自校时。失败返回 None，由调用方显式处理。"""
    if os.environ.get("CAMPUS_CLOCK_SNAPSHOT"):
        try:
            client = ClockClient()
            client.now()                      # 立即验证快照可用
            configure_business_clock(client)
            return client
        except ClockUnavailable:
            return None
    if not allow_sync:
        return None
    clock = BusinessClock(background=False, sync_timeout_s=float(timeout_s))
    try:
        if clock.sync() not in ("ready", "holdover"):
            return None
    except Exception:
        return None
    configure_business_clock(clock)
    return clock

DETAIL_HASH = ("#/secondClassroom/student/activity/studentActivity/"
               "activityDetails?activityId={aid}&from=acList")
LOGIN_HASH = "#/mainPages/login?userType=2"

PAGE_SIZE = 50

# 开放前多少秒开始逐次看按钮：名额放开往往只有几秒窗口，
# 等到开放前一秒再刷新会丢掉首轮点击时机。
POLL_LEAD = 5.0


# ---------------------------------------------------------------- 基础工具
def setup_console():
    """Windows 控制台默认 GBK，中文/特殊符号会抛 UnicodeEncodeError，这里强制 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _school_open(request, timeout=None):
    """学校请求统一走「不走代理」的 opener。

    系统代理（Clash/公司代理）会把校内域名当外网转发或改写请求身份，现象是
    「浏览器能进、脚本 401」。更新检查、组件下载与飞书通知仍用 urllib 默认
    opener（跟随环境变量与 Windows 系统代理）。

    每次都按当前 urllib 现建 opener，而不是模块导入时建一次：测试替换
    grab.urllib 成替身时这条路径同样生效（替身没有 build_opener 就退回 urlopen）。
    """
    build_opener = getattr(urllib.request, "build_opener", None)
    handler = getattr(urllib.request, "ProxyHandler", None)
    if build_opener is None or handler is None:
        return urllib.request.urlopen(request, timeout=timeout)
    return build_opener(handler({})).open(request, timeout=timeout)


LOG_MAX_BYTES = 5 * 1024 * 1024   # grab.log 超过这个大小就轮转（S2）
LOG_KEEP = 5                      # 保留 grab.log.1 … grab.log.5，更老的丢掉
LOG_LOCK_TIMEOUT_S = 2.0          # 拿不到日志锁就走 stderr/控制台降级，不能卡住 worker
_LOG_THREAD_LOCK = threading.Lock()


@contextlib.contextmanager
def _log_file_lock(timeout_s=LOG_LOCK_TIMEOUT_S):
    """grab.log 的轮转与追加共用的跨进程锁。

    界面进程与 worker 打开同一个 grab.log.lock：轮转时不会把对方刚写的行挪走，
    追加也不会落在轮转中间。拿不到锁抛 PrefsLockTimeout，由 log() 降级处理。
    """
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    if not _LOG_THREAD_LOCK.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise PrefsLockTimeout("日志正在被本进程另一线程写入")
    try:
        try:
            Path(LOG_LOCK_FILE).parent.mkdir(parents=True, exist_ok=True)
            handle = open(LOG_LOCK_FILE, "a+b")
        except OSError:
            raise PrefsLockTimeout("日志锁文件不可创建")
        acquired = False
        try:
            acquire_file_lock(handle, max(0.0, deadline - time.monotonic()))
            acquired = True
            yield
        finally:
            if acquired:
                release_file_lock(handle)
            handle.close()
    finally:
        _LOG_THREAD_LOCK.release()


def rotate_log_file(path, max_bytes=None, keep=None):
    """日志超过 max_bytes 就轮转：path → path.1，旧的依次后移，path.keep 之后的丢掉。

    只用标准库的重命名。返回是否轮转了；失败（文件被另一个进程占着等）原样抛出，
    由 log() 兜住——轮转失败不能让这一行日志也丢了。
    """
    path = Path(path)
    limit = LOG_MAX_BYTES if max_bytes is None else max_bytes
    count = LOG_KEEP if keep is None else keep
    try:
        if path.stat().st_size < limit:
            return False
    except FileNotFoundError:
        return False
    oldest = path.with_name("%s.%d" % (path.name, count))
    if oldest.exists():
        oldest.unlink()
    for index in range(count - 1, 0, -1):
        older = path.with_name("%s.%d" % (path.name, index))
        if older.exists():
            os.replace(older, path.with_name("%s.%d" % (path.name, index + 1)))
    os.replace(path, path.with_name(path.name + ".1"))
    return True


def _stderr_note(text):
    """写日志自己出了问题时的出口：至少打到 stderr（无控制台的打包形态里 stderr 可能是 None）。"""
    stream = sys.stderr
    if stream is None:
        return
    try:
        print(text, file=stream, flush=True)
    except Exception:
        pass


@contextlib.contextmanager
def _stdout_to_stderr(enabled):
    """--json 的 stdout 是给主程序 json.loads 的：log() 等辅助函数会往 stdout
    打印，这段时间必须把 stdout 改道到 stderr（无控制台的打包形态里 stderr
    可能是 None，此时丢到系统空设备），否则 JSON 前面多一行，整张列表解析失败。"""
    if not enabled:
        yield
        return
    stream = sys.stderr
    devnull = None
    if stream is None:
        devnull = open(os.devnull, "w", encoding="utf-8")
        stream = devnull
    try:
        with contextlib.redirect_stdout(stream):
            yield
    finally:
        if devnull is not None:
            devnull.close()


def log(msg):
    try:
        ensure_data_dir()
    except Exception as exc:  # noqa: BLE001 - 数据目录建不出来也要把这一行打出去
        _stderr_note("[log] 数据目录不可用（%s）" % type(exc).__name__)
    try:
        # 日志时间按北京时间（业务时钟）；时钟未配置时保留旧本机戳以免崩溃
        stamp = school_time_text(now_fn=business_now)
    except Exception:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "%s %s" % (stamp, msg)
    try:
        with _log_file_lock():
            # 轮转与追加在同一临界区：另一个进程不会读到挪到一半的日志
            try:
                rotate_log_file(LOG_FILE)
            except Exception as exc:  # noqa: BLE001 - 轮转失败下次写入再试，不丢这一行
                _stderr_note("[log] 日志轮转失败（%s）" % type(exc).__name__)
            _append_log_line_unlocked(line)
    except PrefsLockTimeout:
        # 另一个进程正占着日志锁：不能无锁追加，当前行只走 stderr/控制台降级。
        _stderr_note("[log] 没拿到日志文件锁，本次跳过轮转")
        _stderr_note("[log] 当前行未写入 grab.log：%s" % line)
    print(line, flush=True)


def _append_log_line_unlocked(line):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - 不再静默：至少让控制台看到这一行没落盘
        _stderr_note("[log] 写日志文件失败（%s）：%s" % (type(exc).__name__, line))


# 事件日志里的活动 ID：cmd_grab 查到目标后设置一次，之后本进程的事件都带上它
_EVENT_CONTEXT = {"activity_id": ""}


def log_event(event, source, level="INFO", activity_id="", **fields):
    """关键动作写一行结构化日志：北京时间（log() 补）、级别、来源、活动 ID、事件名。

    source 取 cli / gui / auto_relogin / worker。字段名含 token、密码、验证码、
    密钥等字样的一律丢掉（domain.log_events 里的黑名单），调用方不用自己记着过滤。
    """
    log(format_event_line(event, source, level=level,
                          activity_id=activity_id or _EVENT_CONTEXT["activity_id"],
                          fields=fields))


def read_json(path, default=None):
    """读 JSON：文件不存在是常态（还没登录、没配置），静默回 default；
    存在却读不出（被占用、半截内容、编码坏）写一行日志再回 default，只记异常类别，
    不记内容（登录态里有 token）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except Exception as exc:  # noqa: BLE001 - 读失败不抛，但不能装成「文件不存在」
        log("[!] 读取 %s 失败（%s）" % (Path(path).name, type(exc).__name__))
        return default


# ---- 登录态写入（S5）---------------------------------------------------------
# 界面进程和命令行/子进程共用 data 下的登录态文件。单文件写入、双文件事务、
# 线程锁 + 跨进程区域锁（session.json.lock）、暂存清理和字节回滚都归
# infrastructure.login_session_store 一处持有；下面只保留旧入口与旧签名，
# 调用时把数据根解析出来的路径和 log 端口传进去（测试仍按名字替换 grab.log）。
# 读取 token() 不加锁：读到的要么是旧文件要么是新文件，不会是半截。
SESSION_LOCK_TIMEOUT_S = login_session_store.SESSION_LOCK_TIMEOUT_S
_session_write_lock = login_session_store.session_write_lock


def save_session(session, path=None, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录态 session.json 的唯一写入口；拿不到锁最多等 timeout_s 秒，
    超时写日志并放弃这次写入（返回 False，不抛异常）。"""
    target = SESSION_FILE if path is None else Path(path)
    return login_session_store.save_session(session, target, log, timeout_s)


def save_storage_state(state, path=None, session_path=None, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """浏览器 cookie 文件（storage_state.json）：和 session.json 共用同一把写锁。"""
    target = STATE_FILE if path is None else Path(path)
    lock_for = SESSION_FILE if session_path is None else Path(session_path)
    return login_session_store.save_storage_state(state, target, lock_for, log, timeout_s)


def save_verified_files(state, session, state_path=None, session_path=None,
                        timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录成功后 state+session 双文件事务保存（HTTP 路径 save_verified 端口）。

    整笔事务在登录态写锁内进行（见 save_session）；拿不到锁抛 OSError，
    调用方（登录中继）按「持久化失败」处理，不会报告成功。
    """
    target = STATE_FILE if state_path is None else Path(state_path)
    lock_for = SESSION_FILE if session_path is None else Path(session_path)
    # opener 传当前命名空间的 open：替身测试按模块名替换 grab.open 来模拟回滚写失败，
    # 显式把同一个原语交给事务，接缝才不会被新的模块边界切断
    login_session_store.save_verified_files(state, session, target, lock_for,
                                            log, timeout_s, opener=open)


def token():
    sess = read_json(SESSION_FILE, {}) or {}
    return str(sess.get("token") or "").strip()


def _hmac_sha256_hex(message: bytes, key: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _xor_base64(value: str, key: str) -> str:
    """复现官网 K0：按字符异或后按 Latin1 字节做 Base64。"""
    mixed = "".join(chr(ord(value[i]) ^ ord(key[i % len(key)]))
                    for i in range(len(value)))
    return base64.b64encode(mixed.encode("latin-1")).decode("ascii")


def _encode_x_token(signature_hex: str, path: str, nonce: str) -> str:
    encoded = base64.b64encode(signature_hex.encode("utf-8")).decode("ascii")
    mask = _hmac_sha256_hex(
        (path + "|" + nonce).encode("utf-8"),
        REQUEST_SECURITY_CLIENT_KEY.encode("utf-8"),
    )[:16]
    return _xor_base64(encoded, mask)[::-1]


# 注意：这套网关签名的 canonical 里方法写死为 POST，只能给 _post 用；
# 直发 signUp 是 GET、本来就不带这四个头，不能把它原样挪给 GET，否则会静默算错。
def sign_request_headers(path: str, body: bytes, timestamp_ms: int,
                         nonce: str) -> dict:
    """按官网登录页 Z0 算法生成四个网关请求头。"""
    page_ticket = _hmac_sha256_hex(
        REQUEST_SECURITY_RAW_KEY.encode("utf-8"),
        REQUEST_SECURITY_CLIENT_KEY.encode("utf-8"),
    )
    body_hash = hashlib.sha256(body or b"").hexdigest()
    canonical = "\n".join(("POST", str(path), str(timestamp_ms), str(nonce),
                            body_hash, page_ticket))
    derived_key = _hmac_sha256_hex(
        (page_ticket + "|" + str(int(timestamp_ms) // 1000) + "|"
         + str(path) + "|" + str(nonce)).encode("utf-8"),
        REQUEST_SECURITY_CLIENT_KEY.encode("utf-8"),
    )
    signature = _hmac_sha256_hex(canonical.encode("utf-8"),
                                 derived_key.encode("utf-8"))
    return {
        "X-Page-Ticket": page_ticket,
        "X-Timestamp": str(timestamp_ms),
        "X-Nonce": str(nonce),
        "X-Token": _encode_x_token(signature, str(path), str(nonce)),
    }


def _request_nonce() -> str:
    seed = "%d-%s-%s" % (int(time.time() * 1000),
                          secrets.token_hex(8), secrets.token_hex(8))
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


# L2（计划 20261109-list-time-and-estimate）：学校列表回包的 HTTP Date 头。
# 这是学校服务器的时刻，只许用于「列表筛选与排序」，不是业务时钟——报名开放
# 判定、计划启动、倒计时仍只认 business_clock（决策 012 修订 2026-11-09）。
_SCHOOL_DATE = {"raw": "", "epoch": None}


def _remember_school_date(value) -> None:
    """记下最近一次学校回包的 Date 头；解析失败也留原文，epoch 置空。"""
    from email.utils import parsedate_to_datetime

    text = str(value or "").strip()
    if not text:
        return
    epoch = None
    try:
        parsed = parsedate_to_datetime(text)
        # RFC 7231 的 Date 必须带时区；不带时无法换算成唯一 epoch
        if parsed is not None and parsed.tzinfo is not None:
            epoch = parsed.timestamp()
    except Exception:
        epoch = None
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
    """POST/GET 共用入口；传 budget 时超时被压进剩余预算。

    预算耗尽抛 BudgetExhausted，且不被本函数的通用 except 吞掉——
    否则「窗口到点」会被伪装成一次接口异常。
    """
    if budget is not None:
        timeout = budget.timeout_s(15 if timeout is None else timeout)
    # JSON.stringify 的紧凑格式是签名 bodyHash 的输入；先定字节，再签名和发送。
    body = json.dumps(payload if payload is not None else {}, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(API + path, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/plain, */*")
    tok_value = tok if tok is not None else token()
    if tok_value:
        req.add_header("token", tok_value)
    req.add_header("Referer", REFERER)
    req.add_header("User-Agent", UA)
    req_headers = sign_request_headers(path, body, int(time.time() * 1000),
                                       _request_nonce())
    for name, value in req_headers.items():
        req.add_header(name, value)
    try:
        # timeout 可由调用方按剩余预算收紧：固定 15 秒会在 2 秒窗口里
        # 一次查询就把流程拖出截止（R03）
        resp = _school_open(req, timeout=15 if timeout is None else float(timeout))
        try:
            # L2：列表分页回包的 Date 头只侧带出来给列表筛选用，不改返回结构
            headers = getattr(resp, "headers", None)
            if headers is not None:
                _remember_school_date(headers.get("Date"))
            raw = resp.read().decode("utf-8", "replace")
        finally:
            resp.close()
        return json.loads(raw)
    except BudgetExhausted:
        raise
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read().decode("utf-8", "replace")
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else {
                "code": -1, "message": "HTTPError"
            }
        except Exception:
            return {"code": -1, "message": "HTTPError"}
    except Exception as exc:
        return {"code": -1, "message": type(exc).__name__}


def _get(path, tok=None, timeout=None):
    """GET：详情接口（只读）与取消报名（run_cancel，唯一的写用途）共用；
    失败返回 code=-1 由调用方降级。取消接口不重试，成败以随后的复查为准。

    不打印 URL 之外的任何请求头；token 只在内存里使用，绝不进日志。
    """
    req = urllib.request.Request(API + path, method="GET")
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("token", tok if tok is not None else token())
    req.add_header("Referer", REFERER)
    req.add_header("User-Agent", UA)
    try:
        resp = _school_open(req, timeout=15 if timeout is None else float(timeout))
        try:
            raw = resp.read().decode("utf-8", "replace")
        finally:
            resp.close()
        return json.loads(raw)
    except Exception as exc:
        return {"code": -1, "message": type(exc).__name__}


def clock_sample(timeout_s=6.0):
    """用 HTTP Date 做一次粗校时，返回结构化结论（不调整任何本地时间）。

    HTTP Date 只有整秒分辨率，且响应里的时刻对应「服务器生成响应」，
    本机只能观测到发出请求和收到响应两个时刻。因此：

    * 偏移估计取区间中点，误差至少包含往返耗时的一半与整秒截断的 1 秒；
    * 差值的可信区间跨过告警阈值时，只能说「不确定」，不能断言本机慢 N 秒；
    * 没有 Date、解析失败、请求失败或往返太慢，一律 unknown。

    这不是精确对时，也绝不自动把差值加到报名时刻上。
    """
    started_wall = time.time()
    started_mono = time.monotonic()
    result = {
        "source": "http_date",
        "checked_at": started_wall,
        "rtt_s": None,
        "offset_s": None,
        "uncertainty_s": None,
        "state": "unknown",
        "detail": "",
    }
    try:
        req = urllib.request.Request(BASE + "/stu/", method="HEAD")
        req.add_header("User-Agent", UA)
        resp = _school_open(req, timeout=max(0.5, float(timeout_s)))
        try:
            raw = resp.headers.get("Date")
        finally:
            resp.close()
        received_wall = time.time()
        rtt = time.monotonic() - started_mono
        result["rtt_s"] = round(rtt, 3)
        if not raw:
            result["detail"] = "服务器没有返回 Date"
            return result
        from email.utils import parsedate_to_datetime
        remote = parsedate_to_datetime(raw).timestamp()
        offset = remote - (started_wall + received_wall) / 2.0
        # 整秒分辨率最多丢 1 秒；往返延迟按一半计入不确定区间
        uncertainty = rtt / 2.0 + 1.0
        result["offset_s"] = round(offset, 3)
        result["uncertainty_s"] = round(uncertainty, 3)
        # 往返太慢时，中点估计已经不能支撑「慢几秒」这种结论
        if rtt > 2.0:
            result["detail"] = "往返耗时过长，只能算粗校验"
            return result
        low = abs(offset) - uncertainty
        high = abs(offset) + uncertainty
        if low > 3.0:
            result["state"] = "warn"
            result["detail"] = "差值区间整体超过 3 秒"
        elif high <= 3.0:
            result["state"] = "ok"
        else:
            result["detail"] = "差值区间跨过 3 秒阈值，无法断定"
        return result
    except Exception as exc:  # noqa: BLE001 - 校时失败只影响提示，不影响报名
        result["detail"] = type(exc).__name__
        return result


def clock_skew():
    """兼容旧调用：只取偏移估计；没有可信样本返回 None。"""
    sample = clock_sample()
    return sample.get("offset_s") if sample.get("state") != "unknown" else None


# ---------------------------------------------------------------- 活动查询
# 实现已整体迁到 infrastructure/activity_queries.py（20261119 计划）：字段常量、
# 三态与时间解析、列表映射与分页、详情缓存与并发补全、getJoinInfo 只读核对。
# 这里只保留原入口名称与签名，经薄转发注入 grab 的请求函数、学校时间解析和当前
# 详情读取函数——测试替换 grab._post / grab._get / grab.fetch_activity_detail 仍生效。
CHECKIN_FLAG_NAMES = activity_queries.CHECKIN_FLAG_NAMES
CHECKOUT_FLAG_NAMES = activity_queries.CHECKOUT_FLAG_NAMES
POINTS_NAMES = activity_queries.POINTS_NAMES
WAGE_NAMES = activity_queries.WAGE_NAMES
CHECKIN_START_NAMES = activity_queries.CHECKIN_START_NAMES
CHECKIN_END_NAMES = activity_queries.CHECKIN_END_NAMES
CHECKOUT_START_NAMES = activity_queries.CHECKOUT_START_NAMES
CHECKOUT_END_NAMES = activity_queries.CHECKOUT_END_NAMES

# 详情缓存只有一份：这几个名字引用的是 activity_queries 里的同一批对象，
# grab.DETAIL_CACHE.clear() 清的就是实现正在用的缓存。
DETAIL_CACHE = activity_queries.DETAIL_CACHE
DETAIL_CACHE_LOCK = activity_queries.DETAIL_CACHE_LOCK
DETAIL_CONCURRENCY = activity_queries.DETAIL_CONCURRENCY
DETAIL_TIMEOUT_S = activity_queries.DETAIL_TIMEOUT_S

_tri_state = activity_queries.tri_state
_detail_fields = activity_queries.detail_fields
_join_state = activity_queries.join_state
_apply_attendance = activity_queries.apply_attendance
# 三态归一化只有一份实现：空值跳过、未知保持 None 的规则只在 activity_queries 里写，
# 这里保留原入口名，界面契约测试改为驱动 _map_activity 的字段级行为。
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
    rows = activity_queries.fetch_activities(_post, PAGE_SIZE, school_epoch,
                                             budget=budget)
    if with_details and rows:
        return enrich_attendance_items(rows)
    return rows


def is_joined(act_id, budget=None):
    """getJoinInfo 三态查询；判定口径与出处见 activity_queries.join_state。"""
    return activity_queries.is_joined(act_id, _post, budget=budget)


def parse_ts(text):
    """学校时间文本 → epoch 秒；非法时抛 ValueError（调用方按「时间未知」处理）。

    必须显式按东八区解释：学校给的是不带时区的墙上时间，交给
    `datetime.strptime(...).timestamp()` 会按本机时区折算，UTC 机器上会差 8 小时。
    """
    epoch = school_epoch(text)
    if epoch is None:
        raise ValueError("学校时间格式不正确：%r" % (text,))
    return epoch


def still_relevant(act, now=None):
    """报名还没截止（或没给截止时间）的活动才算「还值得看」；实现见 worker_activity_list。"""
    return worker_activity_list.still_relevant(
        act, now, parse_ts=parse_ts, default_now=default_now)


def keep_in_list(act, now):
    """列表默认保留谁（R1，计划 20261107-conflict-cancel）；实现见 worker_activity_list。

    still_relevant 为真照旧保留；另外「已报名、举办还没结束」的活动即使报名早已截止
    也保留——否则它在列表里消失，界面的冲突与禁选基线、后端 signed_baseline 都看不见
    这场已占用的举办时段，用户只能等学校拒绝才发现冲突。
    act_end 缺失或解析不了的已报名活动仍按原规则筛：补回它们会让界面「已报名活动
    时间待确认」的保守规则挡住所有勾选。举办恰在 now 结束算没结束（不早于 now）。
    """
    return worker_activity_list.keep_in_list(act, now, parse_ts=parse_ts)


def sign_state(act, now=None):
    """开放状态文案；实现见 worker_activity_list。"""
    return worker_activity_list.sign_state(
        act, now, parse_ts=parse_ts, default_now=default_now)


# ---------------------------------------------------------------- 浏览器
def launch_browser(pw, headless):
    """按「Chrome → Edge → 自带内核」的顺序找浏览器。

    前两个用本机已装的，免下载几百 MB；Windows 10/11 一定带 Edge，
    所以绿色版（不打包 chromium）在没装 Chrome 的机器上也能跑。
    """
    for channel in ("chrome", "msedge"):
        try:
            return pw.chromium.launch(channel=channel, headless=headless)
        except Exception:
            continue
    try:
        return pw.chromium.launch(headless=headless)
    except Exception as exc:
        raise RuntimeError(
            "没找到可用的浏览器：请先装 Chrome 或 Edge，"
            "或执行 python -m playwright install chromium 下载自带内核。") from exc


def new_context(browser, with_state=True):
    kwargs = {"locale": "zh-CN", "viewport": {"width": 1366, "height": 900}}
    if with_state and STATE_FILE.exists():
        kwargs["storage_state"] = str(STATE_FILE)
    return browser.new_context(**kwargs)


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


# ---------------------------------------------------------------- 子命令
def _cmd_login_relay(args):
    """手机重登中继模式：HTTP 主路径 + Playwright 一次性兜底。

    默认 cmd_login 行为完全不变；只有显式 --relay 才走这条路径。stdin/
    stdout 仍是同一套 [login] JSON 行协议；HTTP 契约不符时凭据留内存切
    Playwright（页面自己发 captcha/login），网络错误安全失败不切换。
    凭据从 stdin 收一次用完即弃，stdout 只有 [login] 安全 JSON 行（决策 5）。
    """
    import secrets as _secrets

    import login_relay

    ensure_data_dir()

    class _Deps:
        login_url = BASE + "/stu/" + LOGIN_HASH

        def __init__(self):
            self._pw = None

        def now(self):
            return time.monotonic()

        def sleep(self, seconds):
            time.sleep(seconds)

        def new_id(self):
            return _secrets.token_hex(8)

        def open_page(self):
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            browser = launch_browser(self._pw, headless=True)
            ctx = new_context(browser, with_state=False)
            return ctx.new_page(), ctx, browser

        def post(self, path, payload, tok):
            return _post(path, payload, tok)

        def save_verified(self, state, session):
            # 两文件的事务端口：一起落位，失败回滚到保存前状态
            session["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_verified_files(state, session)

    deps = _Deps()
    return login_relay.run_http_relay(deps=deps, stdin=sys.stdin,
                                      stdout=sys.stdout, pw_deps=deps)


def cmd_login(args):
    if getattr(args, "relay", False):
        return _cmd_login_relay(args)
    from playwright.sync_api import sync_playwright

    # login/check/list/grab 共用统一数据根；冻结进程首次会顺带迁移旧 EXE 旁数据
    ensure_data_dir()
    login_started = time.monotonic()
    print("=" * 64)
    print("即将打开浏览器，请在窗口里完成学生登录（账号 + 密码 + 图形验证码）。")
    print("登录成功会自动保存登录态并关闭窗口；最多等待 %d 秒。" % args.timeout)
    print("=" * 64)

    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=False)
        ctx = new_context(browser, with_state=False)
        page = ctx.new_page()
        try:
            page.goto(BASE + "/stu/" + LOGIN_HASH, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:
            print("[X] 打不开登录页：%s" % type(exc).__name__)
            browser.close()
            log_event("login_failed", "cli", level="ERROR", reason="login_page_unreachable",
                      elapsed_s=time.monotonic() - login_started)
            return 2

        deadline = time.time() + args.timeout
        tok = ""
        while time.time() < deadline:
            try:
                if page.is_closed():
                    print("[X] 窗口被关掉了，登录未完成。")
                    browser.close()
                    log_event("login_failed", "cli", level="WARN", reason="window_closed",
                              elapsed_s=time.monotonic() - login_started)
                    return 1
                tok = page.evaluate(
                    "() => (localStorage.getItem('xgUniToken') || '').trim()")
            except Exception:
                tok = ""
            if tok:
                break
            time.sleep(1.0)

        if not tok:
            print("[X] 等了 %d 秒仍未检测到登录成功，请重试。" % args.timeout)
            browser.close()
            log_event("login_failed", "cli", level="WARN", reason="timeout",
                      elapsed_s=time.monotonic() - login_started)
            return 1

        page.wait_for_timeout(1500)  # 等页面把 user / xm 写进 localStorage
        items = page_local_storage(page)
        state = ctx.storage_state()
        ctx.close()
        browser.close()

    session = session_from_items(items)
    session["token"] = tok
    try:
        # 两文件一笔事务：第二份失败时回滚，不留新旧混合的登录态
        save_verified_files(state, session)
    except OSError:
        print("[X] 登录成功，但登录态没能写入（另一个进程正在写），请稍后重新登录。")
        log_event("login_failed", "cli", level="ERROR", reason="session_not_saved",
                  elapsed_s=time.monotonic() - login_started)
        return 2

    ok, msg = check_token()
    if not ok:
        print("[X] 已保存登录态，但接口校验失败：%s" % msg)
        log_event("login_failed", "cli", level="ERROR", reason="verify_failed",
                  elapsed_s=time.monotonic() - login_started)
        return 2
    print("[OK] 登录成功，登录态已保存（失效后重新运行本步即可）。")
    log_event("login_ok", "cli", elapsed_s=time.monotonic() - login_started)
    return 0


def cmd_check(args):
    ok, msg = check_token()
    if ok:
        print("[OK] 登录态有效。")
        # 每轮都给结构化粗校时结论：正常/未知也要有，界面才能替换旧告警
        sample = clock_sample()
        log("[clock] " + json.dumps(sample, ensure_ascii=False, separators=(",", ":")))
        if sample.get("state") == "warn":
            print("[!] 学校 HTTP Date 与本机时间有偏差（粗测含网络误差约 ±%.1f 秒）。"
                  "该粗测只作诊断，报名调度按工具自己的北京时间执行。" %
                  (sample.get("uncertainty_s") or 1.0))
        return 0
    print("[X] %s" % msg)
    print("    请运行：python grab.py login   （或双击 1-登录.bat）")
    return 2


def cmd_list(args):
    """列表命令的薄转发：编排在 application/worker_activity_list。

    下面每个实参都在本次调用时取当前函数，测试替换 grab._post / check_token /
    fetch_activity_detail / log 仍然生效。
    """
    return worker_activity_list.run_list(
        args,
        check_token=check_token,
        fetch_activities=fetch_activities,
        enrich=enrich_attendance_items,
        business_now=business_now,
        clear_school_date=clear_school_date,
        school_date_now=school_date_now,
        clock_unavailable=ClockUnavailable,
        log=log,
        stdout_to_stderr=_stdout_to_stderr,
        note=_stderr_note,
        perf_counter=_perf_counter,
        page_size=PAGE_SIZE,
        parse_ts=parse_ts,
        keep_in_list=keep_in_list,
        sign_state=sign_state,
    )


# ---------------------------------------------------------------- 取消报名（X2/X4）
# 计划 20261107-conflict-cancel。取消不可撤回，所以：前置条件四条都在本进程里重核，
# 任何一条不满足或查不到都不调接口；接口只调一次、不重试；成败一律以随后的 getJoinInfo
# 复查为准（学校回包没有实测样例，只作参考）。依据：学校前端分析 11.1 / 9.2 / 9.3。
CANCEL_PATH = "/rjyHdCyr/cancel/"
CANCEL_PRECHECK_BUDGET_S = 20.0    # 前置核对（登录、是否已报名）共用的预算
CANCEL_RECHECK_BUDGET_S = 10.0     # 取消之后复查单独给一份：前面再慢也要查得到
# 学校原话回给界面前的清洗与截断（≤80 字、去控制字符）与界面进程共用一份实现
from domain.cancel_rules import sanitize_message as sanitize_school_message  # noqa: E402


def _cancel_facts(act_id):
    """取消前要看的详情：(cancel_allowed, sign_start, sign_end) 或 None（详情没拿到）。

    直接读 getInfo，不走 fetch_activity_detail：那条路的归一化结果不带报名起止时间。
    本进程是新起的，缓存里也不会有东西，没有复用旧结论的风险。
    """
    data = _get("/rjyHd/getInfo/" + urllib.parse.quote(act_id, safe=""),
                timeout=DETAIL_TIMEOUT_S)
    if not isinstance(data, dict) or str(data.get("code")) not in {"1", "1.0"}:
        return None
    fields = _detail_fields(data)
    allowed = _tri_state(fields.get("qxbm")) if "qxbm" in fields else None
    return (allowed, school_epoch(str(fields.get("bmkssj") or "").strip()),
            school_epoch(str(fields.get("bmjssj") or "").strip()))


def _cancel_joined(act_id, budget_s):
    """取消前后用的三态查询：True / False / None（含预算用尽、校时失效）。"""
    try:
        budget = RetryBudget(business_now() + budget_s, business_clock=_CLOCK["meta"])
        return is_joined(act_id, budget=budget)
    except (BudgetExhausted, ClockUnavailable):
        return None


def run_cancel(act_id, progress=None):
    """取消报名的全部流程，返回 {ok, kind, reason?, message?}；不打印、不读 args。

    progress 是调用方给的字典：调取消接口之前把 sent 置真，供异常兜底区分阶段。
    """
    def refuse(reason):
        log("[cancel] 前置核对未通过：%s（未调取消接口）" % reason)
        return {"ok": False, "kind": "precheck_failed", "reason": reason}

    act_id = str(act_id or "").strip()
    if not SITE_CONFIGURED:
        return refuse("site_unconfigured")
    if not act_id:
        return refuse("not_in_list")
    # 1 登录：只有学校明确说失效才算 login_expired；网络不通是「查不到」，不能诱导重登
    state, _detail = probe_token()
    if state in ("expired", "none"):
        return refuse("login_expired")
    if state != "valid":
        return refuse("unknown_state")
    # 2 业务北京时间
    try:
        business_now()
        if _CLOCK.get("meta") is None:
            raise ClockUnavailable("业务时钟未配置")
    except ClockUnavailable:
        return refuse("clock_unavailable")
    # 3 确实已报名（三态，只有 True 往下走）
    joined = _cancel_joined(act_id, CANCEL_PRECHECK_BUDGET_S)
    if joined is None:
        # 分不清是校时失效还是查询没成功：再看一眼时钟，给更准的原因
        try:
            business_now()
        except ClockUnavailable:
            return refuse("clock_unavailable")
        return refuse("unknown_state")
    if joined is False:
        return refuse("not_signed")
    # 4 详情：允许取消，且业务北京时间在 [报名开始, 报名截止] 内
    facts = _cancel_facts(act_id)
    if facts is None:
        return refuse("unknown_state")
    allowed, sign_start, sign_end = facts
    if allowed is not True:
        return refuse("not_allowed")
    if sign_start is None or sign_end is None:
        return refuse("unknown_state")
    try:
        now = business_now()
    except ClockUnavailable:
        return refuse("clock_unavailable")
    if not (sign_start <= now <= sign_end):
        return refuse("window_closed")
    # 5 调取消接口：只调一次、不重试；从这一行起「结果未知」都算 unknown
    log("[cancel] 前置核对通过，调用取消接口一次")
    if progress is not None:
        progress["sent"] = True
    reply = _get(CANCEL_PATH + urllib.parse.quote(act_id, safe=""))
    # 6 以复查为准：回包只拿来给「没取消成」配一句学校原话
    after = _cancel_joined(act_id, CANCEL_RECHECK_BUDGET_S)
    if after is False:
        log("[cancel] 复查：学校记录里已没有这场报名")
        return {"ok": True, "kind": "cancelled"}
    if after is True:
        log("[cancel] 复查：仍是已报名")
        result = {"ok": False, "kind": "refused"}
        # _get / _post 传输失败时回 {"code": -1, "message": "<异常类名>"}（B8）：
        # 那不是学校的话，不能当学校原话显示；这种情况只回 refused，不带 message
        from_school = (isinstance(reply, dict)
                       and str(reply.get("code")) not in {"-1", "-1.0"})
        message = sanitize_school_message(reply.get("message")) if from_school else ""
        if message:
            result["message"] = message
        return result
    log("[cancel] 复查没查到结果")
    return {"ok": False, "kind": "unknown"}


def cmd_cancel(args):
    """worker 子命令：取消一场已报名活动。stdout 恰好一行 JSON，日志与其他输出走 stderr。"""
    progress = {"sent": False}
    with _stdout_to_stderr(True):
        try:
            result = run_cancel(getattr(args, "id", ""), progress)
        except Exception as exc:  # noqa: BLE001 - 兜底：worker 不能不给结论
            # 异常要分清「接口还没调」与「已经调了」：前者是前置失败，后者结果未知
            log("[cancel] 异常 %s" % type(exc).__name__)
            result = ({"ok": False, "kind": "unknown"} if progress["sent"]
                      else {"ok": False, "kind": "precheck_failed",
                            "reason": "unknown_state"})
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("kind") == "cancelled" else 2


def candidates(acts, now=None):
    """可抢的活动：未报名、有报名开始时间、还没截止；未开放的排最前。

    交互选择与 --pick/--name 非交互选择共用这一份顺序，保证序号一致。
    """
    now = now or default_now()
    cand = [a for a in acts
            if not a["signed"] and a["sign_start"] and still_relevant(a, now)]
    def rank(a):
        # 未开放的排最前（这才是要抢的），开放中的其次
        try:
            return 0 if now < parse_ts(a["sign_start"]) else 1
        except Exception:
            return 1

    cand.sort(key=lambda a: (rank(a), a["sign_start"]))
    return cand


def pick_activity(acts, now=None):
    """交互式挑活动：只列未报名的，按报名开始时间排序。"""
    cand = candidates(acts, now)
    if not cand:
        print("[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。")
        return None
    print("%-4s %-19s %-19s %s" % ("序号", "报名开始", "活动开始", "活动名"))
    for i, act in enumerate(cand, 1):
        print("%-4d %-19s %-19s %s" % (i, act["sign_start"], act["act_start"][:16], act["name"]))
    while True:
        raw = input("\n请输入序号（回车选 1，q 退出）：").strip().lower()
        if raw == "q":
            return None
        idx = 1 if raw == "" else (int(raw) if raw.isdigit() else -1)
        if 1 <= idx <= len(cand):
            return cand[idx - 1]
        print("输入的序号不对，请重试。")


def notify(title, lines, template="green"):
    """可选飞书群机器人通知：config.json 里配了 webhook 才会发，没配就只在控制台打印。"""
    cfg = read_json(CONFIG_FILE, {}) or {}
    hook = str(cfg.get("feishu_webhook") or "").strip()
    if not hook:
        return False
    card = {
        "config": {"wide_screen_mode": True},
        "header": {"template": template,
                   "title": {"tag": "plain_text", "content": title}},
        "elements": [{"tag": "div", "text": {"tag": "lark_md",
                                             "content": "\n".join(lines)}}],
    }
    body = json.dumps({"msg_type": "interactive", "card": card},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(hook, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
        ok = payload.get("code") == 0 or payload.get("StatusCode") == 0
        log("[i] 飞书通知%s" % ("已发送" if ok else "失败：%s" % str(payload)[:80]))
        return ok
    except Exception as exc:
        log("[i] 飞书通知失败：%s" % type(exc).__name__)
        return False


def wait_until(ts, budget=None):
    """等到指定墙钟时刻；给了预算时，预算一到就放弃等待。

    等待开放用的是学校绝对时刻（墙钟语义），但用户设的持续时长是单调预算：
    系统时钟被回拨时，墙钟的「还差 10 秒」会凭空变长，这时必须由预算把
    这段时间截住，不能靠墙钟自己走回来（R06）。
    """
    while True:
        left = ts - business_now()      # 业务北京时间：不随系统墙钟跳变
        if left <= 0:
            return
        step = min(0.2, left)
        if budget is not None:
            remain = budget.remaining_s()
            if remain <= 0:
                raise BudgetExhausted("等待开放时重试窗口已到点")
            step = min(step, remain)
        time.sleep(step)


def _by_index_or_name(cand, args):
    """非交互挑活动：--pick 序号（与 list / 交互列表一致），或 --name 关键词。

    只在这一步命中一个活动才继续；命中多个就列出来让用户改用序号，避免猜错抢错。
    """
    pick = int(getattr(args, "pick", 0) or 0)
    kw = str(getattr(args, "name", "") or "").strip()
    if pick:
        if not 1 <= pick <= len(cand):
            print("[X] --pick %d 超出范围（当前有 %d 个可抢的活动）" % (pick, len(cand)))
            print("    运行 python grab.py list 查看序号。")
            return None
        return cand[pick - 1]
    if not kw:
        return None
    hits = [a for a in cand if kw.lower() in a["name"].lower()]
    if not hits:
        print("[X] 没有名称含「%s」的活动。" % kw)
        print("    运行 python grab.py list 查看当前可抢的活动。")
        return None
    if len(hits) > 1:
        print("[X] 「%s」匹配到 %d 个活动，请改用 --pick 序号：" % (kw, len(hits)))
        for i, a in enumerate(cand, 1):
            if a in hits:
                print("    %-3d %s  %s" % (i, a["sign_start"], a["name"]))
        return None
    return hits[0]


def _at_or_now(at_text):
    """已开放的场次把 at 换成现在：重试窗口是「at + 120 秒」，
    开放超过 2 分钟的原时刻会让提交循环一次都不进、直接误报名额已满。"""
    if not at_text:
        return at_text
    try:
        ts = parse_ts(at_text)
    except Exception:
        return at_text
    if ts is not None and ts <= business_now():
        # 回写的「现在」必须按学校时区格式化：随后 parse_ts 会按 UTC+8 读回，
        # 用本机时区写会凭空产生 8 小时偏移；「现在」取业务北京时间
        return school_time_text(now_fn=business_now)
    return at_text


def resolve_target(args, budget=None):
    """确定 activity-id / 报名开始时间 / 活动名。"""
    acts = None
    act = None
    if args.activity_id:
        aid = args.activity_id
        if not args.at:
            act = next((a for a in (fetch_activities(budget) if acts is None else acts)
                        if a["id"] == aid), None)
            if not act or not act["sign_start"]:
                print("[X] 活动 %s 找不到报名开始时间，请显式传 --at" % aid)
                return None
            at = act["sign_start"]
        else:
            at = args.at
        name = args.name or (act["name"] if act else "活动")
        # original_at 保留学校原定开放时刻：已开放场次 at 会被换成现在，
        # 命令行输出要同时给出「原定开放」和「本次执行」两个时间
        return {"id": aid, "at": _at_or_now(at), "original_at": at, "name": name}

    try:
        acts = fetch_activities(budget)
    except PermissionError as exc:
        print("[X] 登录态已失效（%s），请先运行 python grab.py login" % exc)
        return None

    cand = candidates(acts)
    if not cand:
        print("[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。")
        return None

    act = _by_index_or_name(cand, args)
    if act is None:
        if getattr(args, "pick", 0) or str(getattr(args, "name", "") or "").strip():
            return None            # 非交互模式选不出目标就直接结束，不再弹交互
        act = pick_activity(acts)
    if not act:
        return None
    print("\n已选择：%s" % act["name"])
    print("报名开始：%s   活动时间：%s   地点：%s" %
          (act["sign_start"], act["act_start"], act["place"]))
    # 用 --pick/--name 指定时视为已确认（脚本/快捷方式调用不该再卡在输入上）
    if not (getattr(args, "pick", 0) or str(getattr(args, "name", "") or "").strip()):
        if input("确认到点自动报名？[y/N] ").strip().lower() not in ("y", "yes"):
            print("[i] 已取消。")
            return None
    return {"id": act["id"], "at": _at_or_now(act["sign_start"]),
            "original_at": act["sign_start"], "name": act["name"]}



def retry_anchor(at_ts, now=None):
    """重试窗口起算点；必须在 page.goto 之前取值，之后不再移动。

    未来场次归一到原定 sign_start（等待开放后起算）；已开放场次固定为
    worker 启动时刻——页面加载慢不得把用户配置的重试窗口整体后移。
    配套用法：compute_retry_window(anchor, ..., now=anchor) 把 retry_start
    钉在 anchor 上，等待和首次刷新都不改变 deadline。
    """
    now = default_now() if now is None else now
    return at_ts if at_ts and at_ts > now else now


# 「直到报名截止」缺 sign_end 时的兜底窗口：绝不无限运行。
# 数值口径统一在 domain.retry_window（父监督/桌面投影同源），此处保留旧名。
from domain.retry_window import (  # noqa: E402
    ADAPTIVE_SECONDS, ADAPTIVE_RETRY, DEFAULT_RETRY_SECONDS,
    initial_deadline, resolve_window,
)
# 关键动作的结构化日志行（S2）：格式与黑名单字段是纯函数，界面进程写同一份日志时共用
from domain.log_events import format_event_line  # noqa: E402
# 报名回包分类表（决策 015）：click 与直发共用同一套判据
from domain.signup_reply import (  # noqa: E402
    STALE_TS_LIMIT, TERMINAL_STOP_REASONS, UNKNOWN_REPLY_LIMIT,
    classify_signup_reply, stop_reason_label,
)

DEFAULT_RETRY_WINDOW_S = DEFAULT_RETRY_SECONDS


def compute_retry_window(at_ts, sign_end_ts, retry_for_s, now=None):
    """计算重试起算点与有效截止（纯函数，跨层单测共用同一口径）。

    未来活动从 sign_start 起算；已开放活动从本进程启动（≈用户启动计划）起算。
    - retry_for_s > 0：用户选的持续时长，sign_end 更早时被截断；
    - retry_for_s == 0：持续到 sign_end；sign_end 缺失回退默认 120 秒；
    - retry_for_s == ADAPTIVE_RETRY(-1)：自动延长模式，初始 120 秒，
      后续由合法 window_extended 事件扩窗（上限起点 + 25 分钟、sign_end 硬截）。
    返回 (retry_start, deadline, binding)，binding 是最终起约束的边界
    （duration / sign_end / fallback），终态归因用它。
    """
    now = default_now() if now is None else now
    retry_start = at_ts if at_ts and at_ts > now else now
    deadline, binding = resolve_window(retry_start, retry_for_s, sign_end_ts)
    return retry_start, deadline, binding


def attempts_allowed(attempts: int, max_attempts: int) -> bool:
    """max_attempts=0 表示不限；否则已发起的 signUp 次数必须小于上限才能再点。"""
    return max_attempts <= 0 or attempts < max_attempts


# 提交失败后的下一轮节奏（RC-05）：学校回「人数已满」时，固定 2 秒连打
# 只会在几秒内把次数烧光。2 秒起、1.5 倍退避、8 秒封顶，既给名额释放留时间，
# 又不至于整段窗口只试一两次。等待仍受 RetryBudget（含 sign_end）钳制。
SUBMIT_BACKOFF_START_S = 2.0
SUBMIT_BACKOFF_MAX_S = 8.0
SUBMIT_BACKOFF_FACTOR = 1.5


def next_submit_gap(current: float) -> float:
    """返回下一次提交前的等待秒数；输入非法时从起点重新起算。"""
    try:
        value = float(current)
    except (TypeError, ValueError):
        value = SUBMIT_BACKOFF_START_S
    if value < SUBMIT_BACKOFF_START_S:
        value = SUBMIT_BACKOFF_START_S
    return min(SUBMIT_BACKOFF_MAX_S, value * SUBMIT_BACKOFF_FACTOR)


def wait_before_next_submit(budget, gap: float) -> float:
    """按剩余预算截断等待，返回下一轮间隔（不越过 sign_end / 时长上限）。"""
    try:
        remain = budget.remaining_s()
    except ClockUnavailable:
        raise
    budget.sleep(min(max(0.0, float(gap)), max(0.0, remain)))
    return next_submit_gap(gap)


# ---------------------------------------------------------------------------
# 黄金风暴 / 常规全速 / 404 自适应（2026-10-28 用户确认方案）
#
# 开放瞬间 0~1.6 秒内最多 10 轮、最小间隔 90ms；随后 180ms 常规全速；
# 连续 3 次 404 视为接口未就绪/限流，1.6 倍指数退避、上限 3 秒，并把有效
# 窗口自动扩到起点起 25 分钟；收到非 404 真实响应立即切回全速。
# sign_end 永远是硬截止，扩窗不得越过它。
#
# 旧 RC-05（2 秒起、1.5 倍、8 秒封顶）纯函数保留在上方不动：test_retry_policy
# 直接锁定它们的数值契约，本文件外的测试不可在本轮改动范围内。
# ---------------------------------------------------------------------------

GOLDEN_WINDOW_S = 1.6            # 开放后黄金窗口
GOLDEN_INTERVAL_S = 0.09         # 黄金阶段最小间隔（90ms）
GOLDEN_ROUNDS = 10               # 黄金阶段最多轮次
FULL_SPEED_INTERVAL_S = 0.18     # 常规全速最小间隔（180ms）
NOT_READY_404_LIMIT = 3          # 连续 404 视为接口未就绪
BACKOFF_FACTOR = 1.6             # 自适应退避倍率
BACKOFF_MAX_S = 3.0              # 自适应退避上限
ADAPTIVE_WINDOW_S = ADAPTIVE_SECONDS   # 自适应扩窗上限（25 分钟）
# --- v4 直发核心：调度账本与降级地板（§3/§5/§12）---
SERVER_ERROR_MIN_GAP_S = 0.5     # 5xx 之后的最小间隔地板
ADAPTIVE_IN_GOLDEN = False       # golden 内默认不进 adaptive（真实 200 才退黄金）
MAX_INFLIGHT = 2                 # 物理在途请求上限（直发与 click 共用）
FINAL_CHECK_S = 3.0              # 收尾核对 getJoinInfo 的单独预算：预算用完、截止之后也查这一次
LOGIN_RECHECK_S = 1.5            # 单次 4001 后隔多久复查一次登录（决策 015）
PRECHECK_AHEAD_S = 45.0          # 开抢前预检：原定开放前多久发这一次 signUp（设计 3.1 / S1）
PRECHECK_MIN_LEAD_S = 30.0       # 进场时距开放不足这么久就不预检：来不及改道，反倒挤占开抢
PRECHECK_WAIT_S = 9.0            # 预检回包最多等多久（传输层单笔硬上限 8 秒，多留 1 秒收事件）
OPEN_GRACE_S = 3.0               # 过了预期开放这么久学校仍回「报名未开始」，写一行日志（设计 3.4）
INFLIGHT_TTL_S = 8.0             # 非 lost pending 超过此时长不再占发射名额
INFLIGHT_WAIT_S = 0.05           # 名额满时原地泵的步长
CONFIRM_INFLIGHT_WAIT_S = 1.0    # 确认点击前名额满时最多原地等待的秒数
NOT_READY_SLOWDOWN_AFTER_S = 20.0  # 纯 404 段持续超过此时长开始降速
NOT_READY_SLOW_GAP_S = 0.8         # 纯 404 慢未就绪的最小间隔地板


class BurstPolicy:
    """黄金风暴/常规全速/404 自适应的显式状态机与真实请求记账。

    纯调度与记账，不做任何 I/O：时间读数全部走注入的 clock（单测里是虚拟
    时钟，绝不真实 sleep 1.6 秒）。四个阶段 golden / full_speed /
    adaptive_backoff / terminal 的转移规则见类常量上方注释。

    不变量：
    * attempts 只数真正发出过的 signUp 请求，单调递增；
    * pending 里每笔都有唯一 request_id，响应按归属结算，乱序合法；
    * 同一 request 重复结算只算一次；别家响应不改本场结论；
    * effective_deadline 只会因自适应扩窗变大，且永不越过 sign_end；
    * hard_deadline 一旦冻结就不再改写，sign_end 截止永远优先于扩窗；
    * 进入 terminal 后拒绝再发起任何动作（用户停止同此）；
    * 登记序 == 发送序（attempt_no 严格递增），倒扫 _order 即倒序扫发送序
      ——这是乱序结算安全（F06 5xx 地板、连击重算）的前提。
    """

    PHASE_GOLDEN = "golden"
    PHASE_FULL_SPEED = "full_speed"
    PHASE_ADAPTIVE = "adaptive_backoff"
    PHASE_TERMINAL = "terminal"

    def __init__(self, open_ts, base_deadline, sign_end_ts=None,
                 max_attempts=0, clock=None, retry_start=None,
                 allow_extend=True):
        self._clock = clock
        self.open_ts = float(open_ts)
        self.retry_start = float(retry_start if retry_start is not None else open_ts)
        self.sign_end_ts = float(sign_end_ts) if sign_end_ts else None
        self.max_attempts = int(max_attempts or 0)
        self.hard_deadline = float(base_deadline)
        if self.sign_end_ts:
            self.hard_deadline = min(self.hard_deadline, self.sign_end_ts)
        self.effective_deadline = self.hard_deadline
        self.attempts = 0
        self.streak_404 = 0
        self.golden_rounds = 0
        self._phase = self.PHASE_GOLDEN
        self._backoff_s = FULL_SPEED_INTERVAL_S
        self._requests = {}
        self._seq = 0
        self._stopped = False
        # 显式 --retry-for 时禁扩窗（用户给的秒数是硬承诺，不被自适应拉长）
        self._allow_extend = bool(allow_extend)
        # §5 5xx 降速地板（倒扫派生，见 _derive_min_gap）
        self._min_gap = 0.0
        # 发送序（只追加，绝不重排/删除）与相关缓存
        self._order = []
        self._last_attempt_no = 0
        self._level_prev = False            # 上一次 _apply_level 的 ungated 电平
        self._seg_has_throttled = False     # 缓存：最新连击段内是否出现 429
        self._seg_oldest_issued = None      # 缓存：最新连击段最旧 issued_at

    # -- 时间读数 ---------------------------------------------------------
    def _now(self):
        if self._clock is None:
            import time as _time
            return _time.monotonic()
        return float(self._clock.monotonic() if hasattr(self._clock, "monotonic")
                     else self._clock())

    def _wall_now(self):
        """业务墙上时钟读数：只认 clock.now()（业务 epoch），不回退墙钟。

        clock 不可用或读数无效（None/NaN/±inf/无法转换）时抛 ClockUnavailable
        （由上层统一转 unconfirmed），绝不静默回退 time.time()——那会让扩窗/截止
        在时钟失效时偷偷按真实墙钟走，破坏「时钟不可用即停止发射」的契约。
        """
        if self._clock is None:
            import time as _time
            return _time.time()
        if hasattr(self._clock, "now"):
            raw = self._clock.now()
        else:
            raw = self._clock()
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ClockUnavailable("业务时钟读数无效")
        if not math.isfinite(value):
            raise ClockUnavailable("业务时钟读数无效")
        return value

    def _elapsed(self):
        """单调时钟读数（issued_at/TTL/慢地板用），永不抛 ClockUnavailable。"""
        return float(self._clock.elapsed_s()) if self._clock is not None else self._now()

    # -- 发送序倒扫（乱序安全的核心） ---------------------------------------
    def _recompute_streak(self):
        """按发送序（新→旧）倒扫 _order，返回最新连击段的 (长度, 含429, 最旧issued_at)。

        与登记序同口径：首个已结算的非 404/throttled（更新的 real/server_error）
        断连击——止步于此，更旧的段不看。pending/lost 跳过（不参与判定）。
        """
        n = 0
        has_throttled = False
        oldest_issued = None
        for rid in reversed(self._order):
            rec = self._requests[rid]
            if rec["status"] != "settled":
                continue                     # pending / lost：不看
            if rec["kind"] not in ("404", "throttled"):
                break                        # 更新的 real/5xx：段已断
            n += 1
            if rec["kind"] == "throttled":
                has_throttled = True
            issued = rec.get("issued_at")
            if issued is not None and (oldest_issued is None or issued < oldest_issued):
                oldest_issued = issued
        return n, has_throttled, oldest_issued

    def _derive_min_gap(self):
        """5xx 降速地板：按发送序倒扫，最新「有定论」的记录说了算（§5/F06）。

        倒扫取最新有定论者，天然乱序安全：
        - server_error（5xx）→ 0.5；
        - 404 且状态码==404（未就绪）或 real 且状态码==200（干净成功）→ 0；
        - throttled(429) / 非200 real / 无状态码 bare404 → 跳过（看更旧）；
        - 全部跳过（从未有定论）→ 0。
        替代 feature 的事件式 _note_min_gap/_clear_min_gap（旧 5xx 晚到会在新
        200 之后错误置 0.5 的 F06 缺陷）。
        """
        for rid in reversed(self._order):
            rec = self._requests[rid]
            if rec["status"] != "settled":
                continue                     # pending/lost：跳过
            kind = rec["kind"]
            status = rec.get("http_status")
            if kind == "server_error":
                return SERVER_ERROR_MIN_GAP_S
            if kind == "404" and status == 404:
                return 0.0
            if kind == "real" and status == 200:
                return 0.0
            # throttled / non-200 real / bare 404 → 跳过，看更旧
            continue
        return 0.0

    # -- 阶段与调度 -------------------------------------------------------
    @property
    def phase(self):
        self._apply_level()
        return self._phase

    def current_phase(self):
        """只读返回当前 phase，不触发 _apply_level（回调路径不读时钟）。"""
        return self._phase

    def _golden_time_up(self):
        """黄金墙钟是否已到点；clock 不可用时返回 False（保守留在 golden）。"""
        try:
            return self._wall_now() >= self.open_ts + GOLDEN_WINDOW_S
        except Exception:
            return False

    def _apply_level(self):
        """电平/边沿两层重算：streak、5xx 地板、种子边沿、golden 退出、phase。

        电平：当前事实直接决定 level（ungated = streak>=3 且段内含 429）。
        边沿：level 从 false→true 才给退避种子，true→false 且非 ADAPTIVE 才清——
        否则单个 429 每次重算都重置退避/清种子，把种子语义打碎。
        """
        if self._stopped or self._phase == self.PHASE_TERMINAL:
            return
        n, has_throttled, oldest_issued = self._recompute_streak()
        self.streak_404 = n
        self._seg_has_throttled = has_throttled
        self._seg_oldest_issued = oldest_issued
        self._min_gap = self._derive_min_gap()
        ungated = n >= NOT_READY_404_LIMIT and has_throttled
        # 边沿：false→true 给种子；true→false 且非 ADAPTIVE 清种子
        if ungated and not self._level_prev:
            self._backoff_s = self._seed_backoff()
        elif (not ungated and self._level_prev
              and self._phase != self.PHASE_ADAPTIVE):
            self._backoff_s = FULL_SPEED_INTERVAL_S
        self._level_prev = ungated
        # golden：默认不进 adaptive（ADAPTIVE_IN_GOLDEN=False）；轮数/墙钟到点退位
        if self._phase == self.PHASE_GOLDEN:
            if self.golden_rounds >= GOLDEN_ROUNDS or self._golden_time_up():
                self._exit_golden()
            return
        self._refresh_phase(ungated)

    def _exit_golden(self):
        """golden 的唯一出口：退到 FULL_SPEED，按当前事实决定是否带种子进 adaptive。

        统一从这里退出，避免路径分叉把 golden 内累积的种子清掉。
        """
        if self._phase != self.PHASE_GOLDEN:
            return
        self._phase = self.PHASE_FULL_SPEED
        n, has_throttled, _ = self._recompute_streak()
        ungated = n >= NOT_READY_404_LIMIT and has_throttled
        self._refresh_phase(ungated)
        if ungated and self._backoff_s == FULL_SPEED_INTERVAL_S:
            self._backoff_s = self._seed_backoff()

    def _refresh_phase(self, ungated):
        """按已重算的 ungated 电平刷 phase。gated 必须在退出 golden 之后判定。

        ADAPTIVE_IN_GOLDEN=False（§3 常量开关）⇒ gated 的第二项恒假，即 golden
        内永不进 ADAPTIVE；改成 True 才会让 golden 内的段也切 phase（死分支，
        留着是为了让开关真的能切，不是遗留代码）。
        """
        in_golden_ok = ADAPTIVE_IN_GOLDEN if self._phase == self.PHASE_GOLDEN else True
        if ungated and in_golden_ok:
            if self._phase != self.PHASE_ADAPTIVE:
                self._phase = self.PHASE_ADAPTIVE
        else:
            if self._phase == self.PHASE_ADAPTIVE:
                self._phase = self.PHASE_FULL_SPEED
                self._backoff_s = FULL_SPEED_INTERVAL_S

    def _seed_backoff(self):
        """退避种子值：一段含 throttled 的连击降速后从这里起步。"""
        return min(BACKOFF_MAX_S, FULL_SPEED_INTERVAL_S * BACKOFF_FACTOR)

    def interval_s(self):
        """下一次尝试前必须等待的最小间隔（base / 5xx 地板 / 纯404慢地板 取 max）。"""
        self._apply_level()
        if self._phase == self.PHASE_GOLDEN:
            base = GOLDEN_INTERVAL_S
        elif self._phase == self.PHASE_ADAPTIVE:
            base = min(BACKOFF_MAX_S, max(FULL_SPEED_INTERVAL_S, self._backoff_s))
        else:
            base = FULL_SPEED_INTERVAL_S
        # §12：纯 404 段一直未就绪（服务器晚开几分钟）时降速到 0.8s 地板——
        # 段内一旦混进 throttled 就交给退避，出现 real 立即随连击清零而解除。
        slow_floor = 0.0
        if (self.streak_404 > 0 and not self._seg_has_throttled
                and self._seg_oldest_issued is not None):
            age_s = self._elapsed() - self._seg_oldest_issued
            if age_s > NOT_READY_SLOWDOWN_AFTER_S:
                slow_floor = NOT_READY_SLOW_GAP_S
        # §5：5xx 后的最小间隔地板，与退避/黄金/慢未就绪取 max
        return max(base, self._min_gap, slow_floor)

    def next_interval_after_wait(self):
        """等待完本次间隔后推进退避计数，返回下一轮间隔。"""
        if self._phase == self.PHASE_ADAPTIVE:
            if self._level_prev and self._backoff_s == FULL_SPEED_INTERVAL_S:
                # 段内种子边沿已消耗（_backoff_s 已是 seed），此处只兜底
                # 进 ADAPTIVE 时按 level 重放种子，否则从全速起步被错算成「无退避」
                self._backoff_s = self._seed_backoff()
            self._backoff_s = min(BACKOFF_MAX_S,
                                  max(FULL_SPEED_INTERVAL_S, self._backoff_s) * BACKOFF_FACTOR)
        return self.interval_s()

    def can_attempt(self):
        """是否还允许发起新的一次提交（次数/截止/停止都算）。"""
        if self._stopped or self._phase == self.PHASE_TERMINAL:
            return False
        if self.attempts >= self.max_attempts > 0:
            return False
        if self._wall_now() >= self.effective_deadline:
            return False
        return True

    def extend_deadline_for_adaptive(self):
        """404 连击触发自适应扩窗：有效截止拉到起点起 25 分钟，sign_end 仍硬截。

        显式 --retry-for 时（allow_extend=False）整条扩窗路径不生效：
        用户给的秒数是硬承诺，不能被自适应偷偷拉长。
        """
        if not self._allow_extend:
            return self.effective_deadline
        target = self.retry_start + ADAPTIVE_WINDOW_S
        if self.sign_end_ts:
            target = min(target, self.sign_end_ts)
        if target > self.effective_deadline:
            self.effective_deadline = target
        return self.effective_deadline

    # -- 请求记账 ---------------------------------------------------------
    def register_request(self):
        """为一笔真实发出的 signUp 请求分配唯一 ID 并入账。"""
        self._seq += 1
        request_id = "req-%d" % self._seq
        attempt_no = self.attempts + 1
        # 不变量：attempt_no 严格递增 ⇒ 登记序 == 发送序，倒扫 _order 才等价
        # 按发送顺序从新到旧（乱序结算的安全前提）。本方法跑在回调里，
        # assert 被 -O 剥掉或异常被吞都会漏账，所以只记日志不抛。
        if attempt_no <= self._last_attempt_no:
            log("attempt_no 未递增（%s → %s）：倒序重算不再等于发送序"
                % (self._last_attempt_no, attempt_no))
        self._last_attempt_no = attempt_no
        # issued_at 只在登记时读一次单调时钟（永不抛 ClockUnavailable），
        # 供纯 404 慢地板（段起点 = 段最旧 issued_at）与 inflight TTL 复用。
        self._requests[request_id] = {"status": "pending", "kind": None,
                                      "attempt_no": attempt_no,
                                      "issued_at": self._elapsed()}
        self._order.append(request_id)   # 只追加，绝不重排/删除
        self.attempts += 1
        if self._phase == self.PHASE_GOLDEN:
            self.golden_rounds += 1
        return request_id

    def settle(self, request_id, kind, http_status=None):
        """结算一笔请求的响应归属；kind ∈ {404, throttled, server_error, real, lost}。

        乱序合法：响应可按任意顺序回来；重复结算同一笔只认第一次。
        - 404：计入连击段；连击达阈值只扩窗，不切 phase（§4）；
        - throttled：计入连击段、连击达阈值给退避种子（含 throttled 才给），
          但不结束 golden（§4）；单个 429 只结算，不单独触发退避；
        - server_error：断开连击、设 5xx 地板（§5），永不切 phase；
        - real：断开连击；http_status==200 时结束 golden 并回 FULL_SPEED（§11），
          非 200 real 只断连击、不结束 golden；
        - lost：不结算，请求保持未决，终态如实报「未确认」。
        http_status 记原始 HTTP 状态码，供 §5/§11 判定。
        """
        record = self._requests.get(request_id)
        if record is None or record["status"] == "settled":
            return None
        if http_status is not None:
            record["http_status"] = http_status
        if kind == "lost":
            record["kind"] = "lost"
            return record          # 不改 status，仍是 pending
        record["status"] = "settled"
        record["kind"] = kind
        # prev 必须在 _apply_level 之前取：_apply_level 会把重算结果写回 streak_404
        prev_len = self.streak_404
        # 连击/地板/种子/phase 全部交给 _apply_level：按发送顺序倒序重算（乱序安全），
        # 不再在 settle 里做 +=1 / =0——旧 404 后到不得重建连击，非 200 real 断连击但不退黄金（§11）。
        self._apply_level()
        if kind == "real" and http_status == 200 and self._phase == self.PHASE_GOLDEN:
            # §11：200-real 事件驱动结束 golden（接口已就绪，与它是否清连击无关）。
            self._exit_golden()
        # 扩窗边沿只看长度（§4「纯 404 段不切 phase，只扩窗」）；种子边沿在 _apply_level
        self._maybe_extend_window(prev_len, self.streak_404)
        return record

    def _maybe_extend_window(self, prev_len, new_len):
        """扩窗边沿：只看连击长度（404 与 throttled 同等计入），new>prev 每增长一次就扩一次。

        判据刻意不含 has_throttled——纯 404 也照常扩窗（§4），纯 404 的 20s→0.8s
        慢地板依赖这个能力。extend_deadline_for_adaptive 幂等且被 sign_end 硬截；
        显式 --retry-for 时整条路径不生效。
        """
        if new_len >= NOT_READY_404_LIMIT and new_len > prev_len:
            self.extend_deadline_for_adaptive()

    def pending_ids(self):
        return [rid for rid, rec in self._requests.items()
                if rec["status"] == "pending"]

    def pending_count(self):
        return len(self.pending_ids())

    def inflight_count(self):
        """占发射名额的在途请求数（§2）：pending、非 lost、且未超 INFLIGHT_TTL_S。

        lost 不占名额——页面重载/导航中止只发 requestfailed，若继续占名额，
        名额会一点点占满直到永久不发。pending 超过 INFLIGHT_TTL_S 也不占名额
        （等不回来的请求不该堵死发射），但它仍是 pending：终态如实报「未确认」，
        迟到响应照常结算。
        """
        now = self._elapsed()
        count = 0
        for rec in self._requests.values():
            if rec["status"] != "pending" or rec["kind"] == "lost":
                continue
            issued = rec.get("issued_at")
            if issued is not None and now - issued >= INFLIGHT_TTL_S:
                continue
            count += 1
        return count

    def settled_kind(self, request_id):
        rec = self._requests.get(request_id)
        return rec["kind"] if rec and rec["status"] == "settled" else None

    # -- 终态 -------------------------------------------------------------
    def stop(self, reason):
        """进入终态；之后 can_attempt() 恒 False，不再发起本场任何动作。"""
        self._stopped = True
        self._phase = self.PHASE_TERMINAL
        self.stop_reason = reason
        return reason

    @property
    def stopped(self):
        return self._stopped


def _classify_response(response):
    """把一次 signUp 响应归类为五档：404 / throttled / server_error / real / lost。

    - 404：接口未就绪（还没开放报名）；
    - 429→throttled：限流信号，据此进退避种子；
    - >=500→server_error：服务端异常（网关/超载），当 real 断 404 连击但需 5xx 地板降速；
    - 其余（200+JSON、400 等业务响应）→real：必须结束黄金阶段；
    - 无响应→lost：请求保持未决，终态如实报「未确认」。
    5xx 常是 HTML 错误页，不能按「读不出就 lost」处理（会永久挂 pending）。
    """
    if response is None:
        return "lost"
    status = getattr(response, "status", 200)
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        status_code = 200
    if status_code == 404:
        return "404"
    if status_code == 429:
        return "throttled"
    if status_code >= 500:
        return "server_error"
    return "real"


def _decode_body(raw):
    """字节响应体 → dict。先严格 utf-8，失败再 gb18030（学校接口多为 GBK 系）。

    解不出时返回 {}（等价 code=None），绝不抛异常——否则 HTML 错误页会把
    结算路径炸掉、请求永久 pending。
    """
    if not raw:
        return {}
    for encoding in ("utf-8", "gb18030"):
        try:
            text = raw.decode(encoding) if isinstance(raw, (bytes, bytearray)) else str(raw)
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, ValueError):
            continue
    return {}


def _recognizable_code(value):
    """direct 响应业务 code 可识别性（A2 裁决）：仅接受非 bool 的有限整数
    数值或去空白后严格的十进制整数字符串。bool（True==1 陷阱）、容器、
    非数值字符串、非有限/非整数浮点一律视为无可识别业务 code（协议异常停发）。
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer()
    if isinstance(value, str):
        text = value.strip()
        body = text[1:] if text[:1] in "+-" else text
        return bool(body) and all("0" <= ch <= "9" for ch in body)
    return False


def _ts_text(ts) -> str:
    """秒级时间戳 → 学校时区的完整时间文本；None 显示 '-'（结构化日志用）。"""
    if not ts:
        return "-"
    return school_time_text(ts)


def _checkpoint_event(kind, at=None):
    """结构化 checkpoint 行：kind 只取 worker_started/page_opened/watch_started。

    父层必须用这里记录的源事件时间，不能用读到这一行的接收时刻——
    日志转发慢 2 秒时，父层接收时刻会把「页面已打开」整体推后 2 秒（R10）。
    """
    if at is None:
        try:
            at = business_now()       # 源事件时间按业务北京时间记录
        except ClockUnavailable:
            return                    # 没有可信时钟就不写时间节点，不用本机时间补
    at = float(at)
    payload = {"kind": kind, "at": round(at, 3)}
    meta = clock_meta()
    if meta:
        payload["clock"] = meta
    log("[checkpoint] " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _retry_event(**fields):
    """进度型 [retry] 行：只带进度字段，绝不带 stop_reason（终态才有一条）。

    解析方按空格切字段：值里的空格换成不换行空格，原因文案不会把一行切碎。
    """
    body = " ".join("%s=%s" % (key, str(value).replace(" ", "\u00a0"))
                    for key, value in fields.items())
    log("[retry] " + body)


PREFLIGHT_BUDGET_S = 30.0
_SubmitAborted = signup_outcome.SubmitAborted


def _probe_list(tok, budget=None):
    """登录探测用的最小列表请求（1 条），只看 code。"""
    return _post("/rjyHd/listActivity",
                 {"pageSize": 1, "pageNum": 1, "hdmc": "", "hdzt": None,
                  "kssj": "", "jssj": ""}, tok, budget=budget)


def _direct_headers(tok):
    """直发 signUp 的请求头：只带这四项（决策 015）；正式提交与预检共用，免得两处漂移。"""
    return {"Accept": "application/json, text/plain, */*",
            "token": tok, "Referer": REFERER, "User-Agent": UA}


def fetch_runtime_key(budget=None):
    """向学校取本场的运行时密钥（决策 015）：返回 (密钥字节或 None, 给日志的原因)。

    和页面点击前一样调 runtime/profile，走 _post（带网关签名头）。密钥只在内存：
    不写盘、不写日志、不进事件；原因里只有 code/message，不含 data。
    预算耗尽与校时失效照常上抛，交给统一收尾。
    """
    from signup_signing import parse_runtime_key
    try:
        data = _post(RUNTIME_PROFILE_PATH, {}, token(), budget=budget)
    except (BudgetExhausted, ClockUnavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - 取不到就退回点击，不让异常打断本场
        return None, "请求异常 %s" % type(exc).__name__
    key = parse_runtime_key(data)
    if key is None:
        code = data.get("code") if isinstance(data, dict) else None
        message = str(data.get("message") or "") if isinstance(data, dict) else ""
        return None, "返回里没有可用密钥（code=%s %s）" % (code, message[:40])
    return key, "已取到"


def probe_token(budget=None):
    """登录探测四态：valid / expired / none / unknown。

    只有学校明确回 4001 才是 expired；网络不通、超时、5xx、认不出的返回码
    都归 unknown——把接口异常说成“登录失效”会诱导用户重登，而重登解决不了网络。
    单次 4001 先隔 LOGIN_RECHECK_S 复查一次（决策 015）：实测 13 枚失效 token 里
    有 1 枚之后又恢复；复查时重读 token，别处刚重新登录写入的新 token 也能接上。
    预算不够等这一次时按单次结果判。
    """
    tok = token()
    if not tok:
        return "none", "本机还没有登录过（data/session.json 不存在）"
    data = _probe_list(tok, budget)
    code = data.get("code")
    if code == 1:
        return "valid", "ok"
    if str(code) != "4001":
        return "unknown", "接口异常：%s" % (data.get("message") or code)
    expired_detail = "登录态已过期（%s）" % (data.get("message") or "身份验证失败")
    if budget is not None and budget.remaining_s() <= LOGIN_RECHECK_S:
        return "expired", expired_detail
    if budget is not None:
        budget.sleep(LOGIN_RECHECK_S)
    else:
        time.sleep(LOGIN_RECHECK_S)
    again = _probe_list(token() or tok, budget)
    again_code = again.get("code")
    if str(again_code) == "4001":
        return "expired", expired_detail
    log("[i] 登录探测：4001 后复查恢复（复查 code=%s）" % (again_code,))
    if again_code == 1:
        return "valid", "ok"
    return "unknown", "接口异常：%s" % (again.get("message") or again_code)


def check_token(budget=None):
    """用活动列表接口判定登录态：code=1 有效，4001 表示 token 失效。"""
    state, detail = probe_token(budget)
    return state == "valid", detail


def _known_policy_start(args):
    """GUI 传入的冻结起点；没有则 None（CLI 需要先查目标）。"""
    raw = getattr(args, "retry_start", 0) or 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _policy_window(start, sign_end_ts, retry_for):
    _, deadline, binding = compute_retry_window(start, sign_end_ts, retry_for, now=start)
    return deadline, binding


# 学校明确拒绝类终态的第二行提示（决策 015）；指向 signup_outcome 里的同一个字典对象
REPLY_STOP_HINTS = signup_outcome.REPLY_STOP_HINTS

# cmd_grab 每次调用时从本模块当前全局取出的 47 个名字：测试在调用前替换 grab.X 替身仍生效
_SIGNUP_PORT_NAMES = (
    "ADAPTIVE_RETRY", "API", "BASE", "BudgetExhausted", "BurstPolicy",
    "CONFIRM_INFLIGHT_WAIT_S", "ClockUnavailable", "DETAIL_HASH",
    "FINAL_CHECK_S", "INFLIGHT_WAIT_S", "MAX_INFLIGHT", "OPEN_GRACE_S",
    "POLL_LEAD", "PRECHECK_AHEAD_S", "PRECHECK_MIN_LEAD_S",
    "PRECHECK_WAIT_S", "PREFLIGHT_BUDGET_S", "RetryBudget",
    "_EVENT_CONTEXT", "_checkpoint_event", "_classify_response",
    "_decode_body", "_direct_headers", "_known_policy_start",
    "_policy_window", "_recognizable_code", "_retry_event", "_ts_text",
    "business_bounds", "business_now", "clock_sample", "fetch_runtime_key",
    "is_joined", "launch_browser", "log", "new_context", "notify", "os",
    "parse_ts", "probe_token", "resolve_target", "retry_anchor",
    "school_time_text", "setup_business_clock", "time", "token",
    "wait_until",
)


def _load_direct_modules():
    """拿到运行时密钥后才延迟导入签名与传输模块；导入失败退回点击兜底。"""
    try:
        from signup_signing import build_signup_hash
        from signup_transport import DirectTransport
    except Exception:  # noqa: BLE001 - 模块缺失只影响直发，点击照常
        return None, None
    return build_signup_hash, DirectTransport


def cmd_grab(args):
    """报名命令的薄转发：在调用时导入 Playwright 并从当前模块全局装配端口，交由 application.signup_run 执行。"""
    from playwright.sync_api import sync_playwright
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    g = globals()
    ports = SimpleNamespace(**{name: g[name] for name in _SIGNUP_PORT_NAMES})
    ports.sync_playwright = sync_playwright
    ports.PlaywrightTimeoutError = PlaywrightTimeoutError
    ports.load_direct_modules = _load_direct_modules
    return signup_run.run_signup(args, ports)

def cmd_selftest(args):
    from playwright.sync_api import sync_playwright

    print("[i] 自检：拉起浏览器并打开站点首页 ...")
    with sync_playwright() as pw:
        browser = launch_browser(pw, headless=True)
        try:
            ctx = new_context(browser, with_state=False)
            page = ctx.new_page()
            page.goto(BASE + "/stu/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            title = page.title()
            body = page.inner_text("body")[:120].replace("\n", " ")
            print("[OK] 打开成功：title=%s" % title)
            print("[i] 页面片段：%s" % body)
            if "学生" not in body and "校园助手" not in title:
                print("[!] 页面内容看起来不对，可能被网络/代理拦截。")
                return 2
            return 0
        except Exception as exc:
            print("[X] 自检失败：%s" % type(exc).__name__)
            print("    请确认已安装：pip install playwright && playwright install chromium")
            return 2
        finally:
            browser.close()


def main():
    setup_console()
    # 子命令统一入口先初始化数据根：直接运行冻结 worker 执行 check/list/grab
    # 时，也要先把旧 EXE 旁 data 迁到统一目录——与 GUI 起的 worker 同一套初始化
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

    p = sub.add_parser("grab", help="到点自动报名（不传 --pick/--name/--activity-id 则交互选择）")
    p.add_argument("--pick", type=int, default=0, metavar="N",
                   help="按 list 里的序号直接选（与交互列表顺序一致）")
    p.add_argument("--name", default="",
                   help="活动名关键词，或配合 --activity-id 作为通知里的名字")
    p.add_argument("--activity-id", default="", help="活动 id（一般不用手抄，用 --pick 即可）")
    p.add_argument("--at", default="", help="报名开始时间；不给则自动从活动列表读取")
    p.add_argument("--lead", type=float, default=100, help="提前多少秒打开页面，默认 100")
    p.add_argument("--window", type=float, default=120, help="开放后重试窗口秒数，默认 120（--retry-for 缺省时沿用）")
    p.add_argument("--sign-end", default="", help="报名截止时间；是自动重试的绝对硬上限")
    p.add_argument("--retry-for", type=float, default=None,
                   help="重试持续秒数，默认沿用 --window；0 表示持续到 --sign-end（缺截止则回退 120 秒）")
    p.add_argument("--max-attempts", type=int, default=0,
                   help="最大提交次数，只数真正点 signUp 的次数；0 表示不限")
    p.add_argument("--relogin-wait", type=float, default=0,
                   help="内部：登录失效后等图形界面自动登录的秒数（决策 015）；0 表示不等，直接按登录失效结束")
    p.add_argument("--retry-start", type=float, default=0,
                   help="内部：计划接纳时固定的重试起点（epoch 秒），由图形界面传入；"
                        "CLI 独跑留空则用本进程入口时刻")
    p.add_argument("--headed", action="store_true", help="显示浏览器窗口（默认后台运行）")
    p.add_argument("--dry-run", action="store_true", help="只检查页面/按钮，不提交")
    p.set_defaults(func=cmd_grab)

    p = sub.add_parser("selftest", help="自检浏览器与网络")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args()
    # cancel 的 stdout 是给主程序 json.loads 的：站点未配置也由它自己回一行 JSON 拒绝
    if not SITE_CONFIGURED and args.cmd != "cancel":
        print("[X] %s" % SITE_CONFIG_MESSAGE)
        return 2
    # CLI check/list（以及 cancel）也按需建立同一业务时钟：授时失败不阻断鉴权与原始数据读取，
    # 由各子命令显式降级（列表状态未知、不做本机时钟筛选）
    if args.cmd in ("check", "list", "cancel"):
        setup_business_clock(allow_sync=True)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[i] 已手动中断。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
