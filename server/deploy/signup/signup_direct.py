#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器直发签名报名主控、运行时密钥读取与只读演练。

直发为主、三种条件单向退回点击兜底，与点击路径共用同一份 BurstPolicy。
@author Author
"""
from __future__ import annotations

import queue
import time
import urllib.error
import urllib.request

from signup_loop import _format_log_fields, _initial_loop_state, _sync_state, finish_submit_loop
from signup_policy import BurstPolicy
from signup_reply import (
    STALE_TS_LIMIT,
    TERMINAL_STOP_REASONS,
    UNKNOWN_REPLY_LIMIT,
    classify_signup_reply,
    decode_reply_body,
    direct_headers,
)
from signup_signing import SignerUnavailable, build_signup_hash, parse_runtime_key
from signup_transport import DirectTransport, MAX_PHYSICAL_INFLIGHT, MAX_TIMEOUT_S, build_no_redirect_opener

RUNTIME_PROFILE_PATH = "/upms/security/runtime/profile"


def fetch_runtime_key(*, api_base, referer, ua, token_fn, sign_headers_fn,
                      opener=None, timeout=15.0):
    """POST runtime/profile 取运行时密钥，只存内存；失败返回 (None, reason)。"""
    tok = str(token_fn() or "").strip()
    if not tok:
        return None, "missing_token"
    body = b"{}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "token": tok,
        "Referer": referer,
        "User-Agent": ua,
    }
    headers.update(sign_headers_fn(RUNTIME_PROFILE_PATH, body))
    req = urllib.request.Request(api_base + RUNTIME_PROFILE_PATH, data=body, headers=headers, method="POST")
    client = opener if opener is not None else build_no_redirect_opener()
    try:
        resp = client.open(req, timeout=float(timeout))
        try:
            raw = resp.read()
        finally:
            resp.close()
    except urllib.error.HTTPError as exc:
        return None, "http_%s" % exc.code
    except Exception as exc:
        return None, type(exc).__name__

    payload = decode_reply_body(raw)
    if str(payload.get("code") or "").strip() == "4001":
        return None, "4001"
    key = parse_runtime_key(payload)
    if key is None:
        return None, "bad_key_shape"
    return key, "ok"


def rehearse_direct(*, activity_id, api_base, referer, ua, token_fn,
                    sign_headers_fn, now_fn=None, log_fn=print, opener=None):
    """只读直发演练（--rehearse）：取密钥并试算签名，不发 signUp、不发私聊。"""
    key, reason = fetch_runtime_key(
        api_base=api_base, referer=referer, ua=ua,
        token_fn=token_fn, sign_headers_fn=sign_headers_fn, opener=opener,
    )
    if key is None:
        msg = "取不到运行时密钥（%s）" % reason
        log_fn("[rehearse] 路径：点击（原因：%s）" % msg)
        return {"path": "click", "reason": msg, "signed": False}
    now_s = (now_fn or time.time)()
    try:
        build_signup_hash(str(activity_id), int(now_s * 1000), key)
    except SignerUnavailable as exc:
        msg = str(exc) or "签名不可用"
        log_fn("[rehearse] 路径：点击（原因：%s）" % msg)
        return {"path": "click", "reason": msg, "signed": False}
    log_fn("[rehearse] 路径：直发（运行时密钥可用，签名自检通过）")
    return {"path": "direct", "reason": "运行时密钥与签名可用", "signed": True}


def _rekey_on_version(ctx):
    if ctx["rekeyed"]:
        ctx["downgrade_reason"] = "重取密钥后仍版本不兼容"
        return
    new_key, reason = fetch_runtime_key(
        api_base=ctx["api_base"], referer=ctx["referer"], ua=ctx["ua"],
        token_fn=ctx["token_fn"], sign_headers_fn=ctx["sign_headers_fn"],
        opener=ctx["opener"],
    )
    if new_key is None:
        ctx["downgrade_reason"] = "版本不兼容且重取密钥失败（%s）" % reason
        return
    ctx["key"] = new_key
    ctx["rekeyed"] = True
    ctx["log"]("[i] 版本不兼容：已重取运行时密钥，继续直发")


def _handle_real_reply(ctx, payload):
    reply = classify_signup_reply(payload.get("code"), payload.get("message"))
    ctx["state"]["last_reason"] = reply.raw[:40]
    if reply.kind != "unknown":
        ctx["unknown_raw"], ctx["unknown_streak"] = "", 0
    if reply.kind == "success":
        ctx["state"]["resp_ok"] = True
        ctx["stop_reason"] = "success"
    elif reply.kind == "conflict":
        if ctx["is_joined_fn"] is not None and ctx["is_joined_fn"](ctx["activity_id"]) is True:
            ctx["state"]["resp_ok"] = True
            ctx["stop_reason"] = "success"
        else:
            ctx["stop_reason"] = "conflict"
    elif reply.kind in TERMINAL_STOP_REASONS:
        ctx["stop_reason"] = TERMINAL_STOP_REASONS[reply.kind]
    elif reply.kind == "version":
        _rekey_on_version(ctx)
    elif reply.kind == "unknown":
        if reply.raw == ctx["unknown_raw"]:
            ctx["unknown_streak"] += 1
        else:
            ctx["unknown_raw"], ctx["unknown_streak"] = reply.raw, 1
        if ctx["unknown_streak"] >= UNKNOWN_REPLY_LIMIT:
            ctx["downgrade_reason"] = "未知回包连续 %d 次" % UNKNOWN_REPLY_LIMIT
    elif reply.kind == "stale_ts":
        ctx["stale_ts_count"] += 1
        if ctx["stale_ts_count"] >= STALE_TS_LIMIT:
            ctx["stop_reason"] = "clock_skew"
    elif reply.kind == "login_invalid":
        _handle_login_invalid(ctx)


def _handle_login_invalid(ctx):
    if ctx["relogin_fn"] is None:
        ctx["state"]["login_invalid"] = True
        ctx["stop_reason"] = "login_invalid"
        return
    outcome, new_key, reason = ctx["relogin_fn"](ctx)
    ctx["relogin_tried"] = True
    if outcome == "relogged":
        if new_key is None:
            ctx["downgrade_reason"] = reason or "重登后取不到运行时密钥"
        else:
            ctx["key"] = new_key
            ctx["rekeyed"] = False
            ctx["log"]("[i] 提交中重登成功并重取运行时密钥，继续直发")
        return
    ctx["state"]["login_invalid"] = True
    ctx["stop_reason"] = "login_invalid"


def _settle_event(ctx, ev):
    kind = ev.get("kind")
    if kind == "started" or kind is None:
        return
    req_id = ev.get("request_id")
    bid = ctx["req_to_bid"].get(req_id)
    if bid is None:
        return
    burst, state = ctx["burst"], ctx["state"]
    if kind == "not_started":
        burst.settle(bid, "lost")
        return
    if kind == "failed":
        burst.settle(bid, "lost")
        state["last_reason"] = "网络异常：%s" % ev.get("error_class", "error")
        _sync_state(burst, state)
        return
    status = int(ev.get("http_status") or 0)
    if status == 404:
        burst.settle(bid, "404")
        state["last_reason"] = "404 接口未就绪/限流"
    else:
        payload = decode_reply_body(ev.get("body_bytes"))
        if not payload:
            burst.settle(bid, "lost")
            state["last_reason"] = "响应读取失败，请求仍未决"
        else:
            burst.settle(bid, "real")
            _handle_real_reply(ctx, payload)
    ctx["log"]("[retry] kind=settle request_id=%s %s last_reason=%s"
               % (bid, _format_log_fields(burst, state), (state["last_reason"] or "")[:40]))


def _drain_events(ctx):
    q = ctx["queue"]
    while True:
        try:
            ev = q.get_nowait()
        except queue.Empty:
            break
        _settle_event(ctx, ev)
        if _should_halt(ctx):
            break
    _sync_state(ctx["burst"], ctx["state"])


def _should_halt(ctx):
    state = ctx["state"]
    return bool(
        state["resp_ok"] or state["login_invalid"]
        or ctx["stop_reason"] or ctx["downgrade_reason"]
    )


def _fire_one(ctx):
    burst, transport = ctx["burst"], ctx["transport"]
    if transport.active_count() >= MAX_PHYSICAL_INFLIGHT or not burst.can_attempt():
        return
    tok = str(ctx["token_fn"]() or "").strip()
    if not tok:
        _handle_login_invalid(ctx)
        return
    remain = max(0.0, burst.effective_deadline - burst._wall_now())
    if remain <= 0:
        return
    epoch_ms = int(burst._wall_now() * 1000)
    try:
        sig = build_signup_hash(str(ctx["activity_id"]), epoch_ms, ctx["key"])
    except SignerUnavailable as exc:
        ctx["downgrade_reason"] = str(exc) or "签名不可用"
        return
    ctx["seq"] += 1
    req_id = "dir-%d" % ctx["seq"]
    mono_now = ctx["mono"]()
    ticket = {
        "request_id": req_id,
        "attempt_no": burst.attempts + 1,
        "url": ctx["api_base"] + "/rjyHdCyr/signUp/" + sig,
        "headers": direct_headers(tok, ctx["referer"], ctx["ua"]),
        "request_deadline": mono_now + remain,
        "timeout_s": min(MAX_TIMEOUT_S, remain),
    }
    if not transport.try_submit(ticket):
        return
    bid = burst.register_request()
    ctx["req_to_bid"][req_id] = bid
    ctx["state"]["last_reason"] = "已发起，等响应"
    ctx["log"]("[retry] kind=submit request_id=%s status=pending %s"
               % (bid, _format_log_fields(burst, ctx["state"])))


def _sleep_and_drain(ctx, total_s):
    left = max(0.0, float(total_s))
    if left == 0.0:
        _drain_events(ctx)
        return
    while left > 0 and not _should_halt(ctx):
        slice_s = min(0.05, left)
        ctx["sleep"](slice_s)
        left -= slice_s
        _drain_events(ctx)


def _tail_drain(ctx):
    burst = ctx["burst"]
    if burst.pending_count() <= 0 or burst._wall_now() >= burst.effective_deadline:
        return
    end = ctx["mono"]() + min(1.0, max(0.0, burst.effective_deadline - burst._wall_now()))
    while (ctx["mono"]() < end and burst.pending_count() > 0
           and not _should_halt(ctx)):
        ctx["sleep"](0.05)
        _drain_events(ctx)


def _closeout_direct(ctx, notify_owner):
    burst, state = ctx["burst"], ctx["state"]
    if state["login_invalid"]:
        return finish_submit_loop("login_invalid", burst=burst, state=state,
                                  name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)
    if state["resp_ok"]:
        return finish_submit_loop("success", burst=burst, state=state,
                                  name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)
    if not ctx["stop_reason"] and burst.attempts and ctx["is_joined_fn"] is not None:
        try:
            if ctx["is_joined_fn"](ctx["activity_id"]) is True:
                return finish_submit_loop("success", burst=burst, state=state,
                                          name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)
        except Exception:
            pass
    if ctx["stop_reason"]:
        return finish_submit_loop(ctx["stop_reason"], burst=burst, state=state,
                                  name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)
    if burst.pending_count() > 0:
        return finish_submit_loop("unconfirmed", burst=burst, state=state,
                                  name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)
    reason = "sign_end" if (burst.sign_end_ts and burst.effective_deadline >= burst.sign_end_ts) else "retry_duration"
    return finish_submit_loop(reason, burst=burst, state=state,
                              name=ctx["name"], log_fn=ctx["log"], notify_owner=notify_owner)


def _drive_direct_loop(ctx, at_ts):
    burst = ctx["burst"]
    while burst._wall_now() < burst.effective_deadline:
        _drain_events(ctx)
        if _should_halt(ctx):
            break
        if burst._wall_now() < at_ts:
            ctx["sleep"](min(0.2, at_ts - burst._wall_now()))
            continue
        if not burst.can_attempt():
            ctx["stop_reason"] = (
                "max_attempts" if burst.attempts >= burst.max_attempts > 0 else
                ("sign_end" if burst.sign_end_ts and burst.effective_deadline >= burst.sign_end_ts else "retry_duration")
            )
            break
        _fire_one(ctx)
        _drain_events(ctx)
        if _should_halt(ctx) or not burst.can_attempt():
            continue
        gap = burst.interval_s()
        _sleep_and_drain(ctx, min(max(0.0, gap), max(0.0, burst.effective_deadline - burst._wall_now())))
        burst.next_interval_after_wait()


def run_direct_submit_loop(*, activity_id, at_ts, window_s, sign_end_ts=None,
                           max_attempts=0, api_base, referer, ua, token_fn,
                           sign_headers_fn, initial_key=None, initial_key_reason="",
                           is_joined_fn=None, notify_fn=None, log_fn=None,
                           clock=None, name="活动", click_fallback_fn=None,
                           transport_cls=None, opener=None, relogin_fn=None,
                           sleep_fn=time.sleep):
    """直发为主、三种条件下退回点击的提交主控（共用同一份 BurstPolicy）。"""
    log = log_fn or print
    notify_owner = notify_fn or (lambda *a, **kw: False)
    burst = BurstPolicy(open_ts=at_ts, base_deadline=float(at_ts) + float(window_s),
                        sign_end_ts=sign_end_ts, max_attempts=max_attempts,
                        clock=clock, retry_start=at_ts)
    state = _initial_loop_state(burst)
    state["path"], state["path_reason"] = "direct", ""

    if initial_key is None:
        reason = initial_key_reason or "取不到运行时密钥"
        state["path"], state["path_reason"] = "click", reason
        log("[i] 报名路径：点击（原因：%s）" % reason)
        if click_fallback_fn is not None:
            return click_fallback_fn(burst, state)
        return finish_submit_loop("process_error", burst=burst, state=state,
                                  name=name, log_fn=log, notify_owner=notify_owner)

    log("[i] 报名路径：直发（运行时密钥）")
    ev_q = queue.Queue()
    mono_fn = (lambda: burst._now()) if clock is not None else time.monotonic
    transport = (transport_cls or DirectTransport)(ev_q, opener=opener, monotonic_fn=mono_fn)
    ctx = {
        "activity_id": activity_id, "api_base": api_base, "referer": referer, "ua": ua,
        "token_fn": token_fn, "sign_headers_fn": sign_headers_fn, "opener": opener,
        "key": initial_key, "rekeyed": False, "unknown_raw": "", "unknown_streak": 0,
        "stale_ts_count": 0, "stop_reason": "", "downgrade_reason": "",
        "burst": burst, "state": state, "queue": ev_q, "transport": transport,
        "req_to_bid": {}, "seq": 0, "log": log, "is_joined_fn": is_joined_fn,
        "relogin_fn": relogin_fn, "relogin_tried": False,
        "sleep": sleep_fn, "name": name, "mono": mono_fn,
    }
    try:
        _drive_direct_loop(ctx, at_ts)
    finally:
        transport.close()

    if not ctx["downgrade_reason"] and not ctx["state"]["resp_ok"] and not ctx["state"]["login_invalid"]:
        _tail_drain(ctx)
    if ctx["downgrade_reason"]:
        state["path"], state["path_reason"] = "click", ctx["downgrade_reason"]
        log("[!] 本场切换为点击兜底（原因：%s）" % ctx["downgrade_reason"])
        if click_fallback_fn is not None:
            return click_fallback_fn(burst, state)
    return _closeout_direct(ctx, notify_owner)
