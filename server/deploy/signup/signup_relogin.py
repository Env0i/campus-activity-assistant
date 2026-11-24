#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器自动报名的登录失效复查、限时重登与锁冲突等待。

@author Author
"""
from __future__ import annotations

import os
import subprocess
import time

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows 离线测试走替身
    fcntl = None

PRE_OPEN_RECHECK_DELAY_S = 1.5
IN_SUBMIT_RELOGIN_TIMEOUT_S = 60.0
IN_SUBMIT_MAX_ATTEMPTS = 2
RELOGIN_POLL_INTERVAL_S = 0.5


def is_lock_busy(lock_file) -> bool:
    """非阻塞探测 auto_login 文件锁是否正被别的重登进程持有。"""
    if fcntl is None:
        return False
    try:
        with open(lock_file, "a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                return True
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            return False
    except OSError:
        return False


def wait_token_change(old_token, *, token_fn, timeout_s=IN_SUBMIT_RELOGIN_TIMEOUT_S,
                      clock=None, sleep_fn=time.sleep, poll_s=RELOGIN_POLL_INTERVAL_S) -> bool:
    """锁被占用时不另起重登，限时等待 session.json 里的 token 变化。"""
    mono = (clock.monotonic if clock is not None and hasattr(clock, "monotonic")
            else time.monotonic)
    deadline = mono() + float(timeout_s)
    prev = str(old_token or "").strip()
    while mono() < deadline:
        cur = str(token_fn() or "").strip()
        if cur and cur != prev:
            return True
        remain = deadline - mono()
        if remain <= 0:
            break
        sleep_fn(min(float(poll_s), remain))
    cur = str(token_fn() or "").strip()
    return bool(cur and cur != prev)


def run_auto_login_force(*, login_dir, timeout_s=IN_SUBMIT_RELOGIN_TIMEOUT_S,
                         max_attempts=IN_SUBMIT_MAX_ATTEMPTS,
                         runner_fn=subprocess.run) -> bool:
    """限时子进程执行 auto_login.py --force，限制本次最大重试次数。"""
    env = dict(os.environ)
    env["AUTO_LOGIN_MAX_ATTEMPTS"] = str(int(max_attempts))
    cmd = ["/usr/bin/python3", os.path.join(login_dir, "auto_login.py"), "--force"]
    try:
        proc = runner_fn(cmd, env=env, capture_output=True, text=True,
                         timeout=float(timeout_s))
        return getattr(proc, "returncode", 1) == 0
    except Exception:
        return False


def recover_session(*, old_token, login_dir, lock_file, token_fn,
                    timeout_s=IN_SUBMIT_RELOGIN_TIMEOUT_S,
                    max_attempts=IN_SUBMIT_MAX_ATTEMPTS, log_fn=None,
                    lock_busy_fn=None, runner_fn=subprocess.run,
                    clock=None, sleep_fn=time.sleep) -> bool:
    """锁空闲时拉重登子进程；锁忙时改为等 token 变化，总时长均受 timeout_s 约束。"""
    log = log_fn or (lambda _m: None)
    busy = (lock_busy_fn or is_lock_busy)(lock_file)
    if busy:
        log("[i] auto_login 锁已被占用，等待登录态 token 更新（限时 %ds）" % int(timeout_s))
        return wait_token_change(old_token, token_fn=token_fn, timeout_s=timeout_s,
                                 clock=clock, sleep_fn=sleep_fn)
    log("[i] 执行限时自动重登（上限 %ds）" % int(timeout_s))
    return run_auto_login_force(login_dir=login_dir, timeout_s=timeout_s,
                                max_attempts=max_attempts, runner_fn=runner_fn)


def handle_pre_open_4001(*, check_fn, recover_fn, fetch_key_fn, log_fn,
                         sleep_fn=time.sleep, delay_s=PRE_OPEN_RECHECK_DELAY_S):
    """等开放期间收到 4001：先隔 1.5 秒复查，仍失效才重登并重取运行时密钥。"""
    log_fn("[i] 等开放期间收到 4001，等待 %.1f 秒后复查" % float(delay_s))
    sleep_fn(float(delay_s))
    if check_fn():
        key, reason = fetch_key_fn()
        return ("recovered", key, reason)
    if not recover_fn():
        log_fn("[x] 等开放期间复查仍失效且自动重登失败")
        return ("login_invalid", None, "自动重登失败")
    new_key, reason = fetch_key_fn()
    log_fn("[i] 等开放期间自动重登成功，已重取运行时密钥")
    return ("relogged", new_key, reason)


def handle_in_submit_4001(*, already_tried, recover_fn, fetch_key_fn, log_fn):
    """提交中确认 4001：本场最多限时重登一次，成功后重取密钥继续。"""
    if already_tried:
        return ("login_invalid", None, "本场已重登过")
    if not recover_fn():
        log_fn("[x] 提交中重登超时或失败，本场以登录失效结束")
        return ("login_invalid", None, "提交中重登超时或失败")
    new_key, reason = fetch_key_fn()
    return ("relogged", new_key, reason)
