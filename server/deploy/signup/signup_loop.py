#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务器自动报名的事件驱动提交循环、响应结算与终态收口。

只做「盯按钮 → 点击 → 记账 → 收口」，不做登录和浏览器生命周期。
@author Author
"""
import time
from datetime import datetime

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from signup_policy import BurstPolicy, FULL_SPEED_INTERVAL_S, classify_response
from signup_reply import stop_reason_label


def _is_signup_url(url_text):
    return "/rjyHdCyr/signUp/" in url_text


def _sync_state(burst, state):
    state["attempts"] = burst.attempts
    state["pending"] = burst.pending_count()
    state["streak_404"] = burst.streak_404
    state["backoff_s"] = burst.backoff_s
    state["phase"] = burst.phase
    state["round"] = burst.round
    state["retry_deadline"] = burst.effective_deadline


def _format_log_fields(burst, state):
    _sync_state(burst, state)
    return ("phase=%s round=%d 404_streak=%d backoff_s=%.2f attempts=%d "
            "pending=%d retry_deadline=%d"
            % (state["phase"], state["round"], state["streak_404"],
               state["backoff_s"], state["attempts"], state["pending"],
               int(state["retry_deadline"])))


def _now_ms(burst, clock):
    if clock is None:
        return time.monotonic() * 1000
    return burst._now() * 1000


def _exhausted_reason(burst):
    if burst.attempts >= burst.max_attempts > 0:
        return "max_attempts"
    if burst.sign_end_ts and burst.effective_deadline >= burst.sign_end_ts:
        return "sign_end"
    return "retry_duration"


def _settle_response(response, *, burst, state, request_to_bid, classify_fn, log_fn):
    """按 request_id 结算一笔在途响应；乱序合法，别家响应不改本场结论。"""
    resp_request = getattr(response, "request", None)
    bid = None
    if resp_request is not None:
        bid = request_to_bid.get(id(resp_request))
    elif burst.pending_count() == 1:
        # 替身/旧驱动可能不给 response.request：只在唯一未决时认领
        bid = burst.pending_ids()[0]
    if bid is None:
        state["last_reason"] = "收到其他请求的响应，本场结论未变"
        return
    raw_kind = classify_fn(response)
    payload = None
    if raw_kind == "real":
        try:
            payload = response.json()
        except Exception:
            raw_kind = "lost"   # 响应体读不出：保持未决，不假造结论
    burst.settle(bid, raw_kind)
    if raw_kind == "lost":
        state["last_reason"] = "响应读取失败，请求仍未决"
    elif raw_kind == "404":
        state["last_reason"] = "404 接口未就绪/限流"
    else:
        code = payload.get("code") if isinstance(payload, dict) else None
        message = ""
        if isinstance(payload, dict):
            message = str(payload.get("message") or "")
        state["last_reason"] = "code:%s %s" % (code, message[:30])
        # 成功结论粘性：只要有一笔 code=1 就是成功，后续失败响应不改写
        if code == 1:
            state["resp_ok"] = True
        code_text = "" if code is None else str(code)
        # 只认 4001（决策 015）；业务回包里出现「登录」字样不算失效，交给原有重试逻辑
        if code_text == "4001":
            state["login_invalid"] = True
    _sync_state(burst, state)
    log_fn("[retry] kind=settle request_id=%s status=%s %s last_reason=%s"
           % (bid, raw_kind, _format_log_fields(burst, state),
              (state["last_reason"] or "")[:40]))


def _drain_responses(response_queue, *, burst, state, request_to_bid, classify_fn, log_fn):
    while response_queue:
        _settle_response(response_queue.pop(0), burst=burst, state=state,
                         request_to_bid=request_to_bid, classify_fn=classify_fn,
                         log_fn=log_fn)
    _sync_state(burst, state)


def _pump_wait(page, seconds, *, burst, state, clock, drain_fn):
    """短事件泵：按预算截断等待，同时派发并结算在途响应。

    Playwright 同步 API 在等待里派发事件回调；成功/登录失效立即返回，
    让调度循环收成唯一终态。等待按整毫秒推进，不让浮点截断把 90ms
    间隔悄悄吃短。
    """
    remain = max(0.0, burst.effective_deadline - burst._wall_now())
    wait_s = max(0.0, min(float(seconds), remain))
    wait_ms = int(round(wait_s * 1000)) if wait_s > 0 else 0
    if wait_s > 0:
        wait_ms = max(1, wait_ms)
    deadline_ms = int(round(_now_ms(burst, clock))) + wait_ms
    while True:
        left_ms = deadline_ms - int(round(_now_ms(burst, clock)))
        if left_ms <= 0:
            break
        try:
            page.wait_for_timeout(min(left_ms, 50))  # 50ms 一片
        except Exception:
            break
        drain_fn()
        if state["resp_ok"] or state["login_invalid"]:
            return


def _path_card_line(state):
    path = state.get("path")
    if path == "direct":
        return "报名路径：直发"
    if path == "click":
        reason = state.get("path_reason") or "退回兜底"
        return "报名路径：点击（原因：%s）" % reason
    return ""


def _build_finish_card(stop_reason, name, attempts, pending, state):
    extra = _path_card_line(state)
    if stop_reason == "success":
        lines = ["**%s**" % name,
                 "报名时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "如不想参加，请尽快在活动页取消，别占着名额。"]
        out = ("🎟 报名成功", lines, "green")
    elif stop_reason == "already_signed":
        out = ("已报名", ["**%s**" % name, "此前已报名，本次未重复提交"], "blue")
    elif stop_reason == "login_invalid":
        out = ("⚠️ 自动报名失败",
               ["**%s**" % name, "登录已失效，重试没有意义，请重新登录后再试。"], "red")
    elif stop_reason == "unconfirmed":
        out = ("⚠️ 自动报名结果未确认",
               ["**%s**" % name,
                "已提交 %d 次（未决 %d 笔），没有拿到确定回应。" % (attempts, pending),
                "结果未确认，请到活动页核对。"], "orange")
    else:
        label = stop_reason_label(stop_reason)
        detail = label or ("可能名额已满或页面未放开")
        out = ("⚠️ 自动报名失败",
               ["**%s**" % name,
                "窗口内未成功（尝试 %d 次，stop_reason=%s，%s）。" % (attempts, stop_reason, detail),
                "建议手动打开活动页确认。"], "orange")
    if extra:
        out[1].append(extra)
    return out


def finish_submit_loop(stop_reason, *, burst, state, name, log_fn, notify_owner):
    """唯一结构化终态：一条 [retry] kind=done + 一条 owner 私聊结论。"""
    _sync_state(burst, state)
    log_fn("[retry] kind=done stop_reason=%s %s last_reason=%s"
           % (stop_reason, _format_log_fields(burst, state),
              (state["last_reason"] or "")[:40]))
    attempts, pending = state["attempts"], state["pending"]
    if stop_reason == "success":
        log_fn("[OK] 报名成功（尝试 %d 次）" % attempts)
    elif stop_reason == "login_invalid":
        log_fn("[x] 登录失效（尝试 %d 次）" % attempts)
    elif stop_reason == "unconfirmed":
        log_fn("[x] 结果未确认（尝试 %d 次，未决 %d 笔）" % (attempts, pending))
    elif stop_reason != "already_signed":
        log_fn("[x] 报名失败（尝试 %d 次，stop_reason=%s，最近异常 %s）"
               % (attempts, stop_reason, (state["last_reason"] or "名额已满/未开放")))
    title, lines, template = _build_finish_card(stop_reason, name, attempts, pending, state)
    notify_owner(title, lines, template)
    return stop_reason, state


def _try_click_confirm(page, btn, *, burst, state, at_ts):
    # 非阻塞提交：点完「确定」立刻回调度循环，不逐笔等响应
    try:
        btn.first.click(timeout=3000)
        # 打开确认框之后、点「确定」之前再核一次：
        # 到期/次数到/还没开放都绝不确认
        if burst._wall_now() >= burst.effective_deadline:
            state["last_reason"] = "确认前重试窗口已到点"
            return False
        if not burst.can_attempt():
            state["last_reason"] = "确认前已达最大提交次数或窗口关闭"
            return False
        if burst._wall_now() < at_ts:
            state["last_reason"] = "确认前还没到开放时间"
            return False
        page.get_by_text("确定", exact=True).first.click(timeout=3000)
    except PlaywrightTimeoutError:
        state["last_reason"] = "点击确认超时"
    except Exception as exc:
        state["last_reason"] = "点击确认失败：%s" % type(exc).__name__
    return True


def _reload_or_wait(page, reload_state, *, burst, clock, pump_fn):
    # 按钮迟迟不出现通常是「名额已满」：间隔逐次放大（2 秒起、
    # 1.5 倍、8 秒封顶），满员场景不刷爆接口
    if _now_ms(burst, clock) / 1000.0 - reload_state["last_reload"] >= reload_state["reload_gap"]:
        page.reload(wait_until="domcontentloaded", timeout=45000)
        pump_fn(0.25)
        reload_state["last_reload"] = _now_ms(burst, clock) / 1000.0
        reload_state["reload_gap"] = min(8.0, reload_state["reload_gap"] * 1.5)
    else:
        pump_fn(0.3)


def _attach_listeners(page, *, burst, state, request_to_bid, response_queue, armed, log_fn):
    # 受控提交窗口：只承认本场盯按钮期间发出的 signUp 请求。请求事件的派发
    # 可能晚于网络发起，窗口覆盖整个提交阶段才不会漏计真实请求；页面加载
    # 阶段的别家请求在监听注册之前，天然不入账。
    # admitted_all 必须持有 Request 引用：只记 id() 的话对象一被回收，
    # 下一笔请求可能拿到复用的地址而被误判成重复（真实请求会被吞掉）。
    admitted_ids = set()
    admitted_all = []

    def on_request(request):
        if armed["dead"] or not armed["on"]:
            return
        try:
            url_text = str(request.url)
        except Exception:
            return
        if not _is_signup_url(url_text):
            return
        ident = id(request)
        if ident in admitted_ids:
            return          # 同一个 Request 重复通知只计 1
        admitted_ids.add(ident)
        admitted_all.append(request)   # 钉住引用，防 id() 复用误判重复
        bid = burst.register_request()
        request_to_bid[ident] = bid
        _sync_state(burst, state)
        state["last_reason"] = "已发起，等响应"
        # 请求发起即记账：发出就计次，不等响应回来
        log_fn("[retry] kind=submit request_id=%s status=pending %s"
               % (bid, _format_log_fields(burst, state)))

    def on_response(response):
        # 回调只入队：结算统一走主循环的事件泵，不在回调里做 I/O
        if armed["dead"]:
            return
        try:
            url_text = str(response.url)
        except Exception:
            return
        if not _is_signup_url(url_text):
            return
        response_queue.append(response)

    page.on("request", on_request)
    page.on("response", on_response)
    return [("request", on_request), ("response", on_response)]


def _drive_click_loop(page, *, burst, state, at_ts, clock, drain_fn, pump_fn):
    reload_state = {"reload_gap": 2.0, "last_reload": 0.0}
    stop_reason = ""
    while burst._wall_now() < burst.effective_deadline:
        # 先结算在途响应：成功/登录失效立即收口，绝不为下一笔再等
        drain_fn()
        if state["resp_ok"]:
            break
        if state["login_invalid"]:
            stop_reason = "login_invalid"
            break

        btn = page.locator("uni-button").filter(has_text="立即报名")
        if not btn.count():
            _reload_or_wait(page, reload_state, burst=burst, clock=clock, pump_fn=pump_fn)
            continue

        # 多笔未决合法：黄金风暴允许并发在途请求，不因 pending 停手
        if not burst.can_attempt():
            stop_reason = _exhausted_reason(burst)
            break

        # 按钮提前可见也不能提前发请求：到开放时刻才动手
        if burst._wall_now() < at_ts:
            pump_fn(min(0.25, at_ts - burst._wall_now()))
            continue

        if not _try_click_confirm(page, btn, burst=burst, state=state, at_ts=at_ts):
            continue

        # 已到响应立即结算；迟到的由下一片事件泵接管
        drain_fn()
        if state["resp_ok"]:
            break
        if state["login_invalid"]:
            stop_reason = "login_invalid"
            break
        if not burst.can_attempt():
            stop_reason = _exhausted_reason(burst)
            break
        # 下一轮节奏由状态机统一提供：黄金 90ms / 全速 180ms /
        # 404 自适应退避 1.6 倍上限 3 秒
        gap = burst.interval_s()
        pump_fn(min(max(0.0, gap), max(0.0, burst.effective_deadline - burst._wall_now())))
        burst.next_interval_after_wait()
    return stop_reason


def _closeout_submit_loop(page, *, activity_id, burst, state, stop_reason, clock,
                          is_joined_fn, drain_fn, pump_fn, finish_fn):
    # 有界收尾：给在途响应一个短暂结算窗口（最长 1 秒且不越截止）
    if burst.pending_count() > 0 and burst._wall_now() < burst.effective_deadline:
        tail_deadline = _now_ms(burst, clock) / 1000.0 + min(
            1.0, max(0.0, burst.effective_deadline - burst._wall_now()))
        while (_now_ms(burst, clock) / 1000.0 < tail_deadline
               and burst.pending_count() > 0
               and not state["resp_ok"] and not state["login_invalid"]):
            pump_fn(0.05)

    if state["login_invalid"]:
        return finish_fn("login_invalid")
    if state["resp_ok"]:
        return finish_fn("success")

    # 收尾查询：查询不到不等于没报名
    if burst.attempts and is_joined_fn is not None:
        try:
            if is_joined_fn(activity_id) is True:
                return finish_fn("success")
        except Exception:
            pass    # 查询失败不改写已记账事实
    if burst.pending_count() > 0:
        return finish_fn("unconfirmed")
    if stop_reason:
        return finish_fn(stop_reason)
    return finish_fn("sign_end" if (burst.sign_end_ts and
                                    burst.effective_deadline >= burst.sign_end_ts)
                     else "retry_duration")


def _initial_loop_state(burst):
    return {"attempts": 0, "pending": 0, "last_reason": "", "resp_ok": False,
            "login_invalid": False, "retry_deadline": burst.effective_deadline,
            "streak_404": 0, "backoff_s": FULL_SPEED_INTERVAL_S,
            "phase": burst.phase, "round": 0}


def _detach_listeners(page, armed, listeners):
    # 停止/异常路径统一解除监听并失活回调：不留跨计划的残留监听
    armed["on"] = False
    armed["dead"] = True
    for event_name, handler in listeners:
        try:
            page.remove_listener(event_name, handler)
        except Exception:
            pass


def _ensure_loop_context(burst, state, at_ts, window_s, sign_end_ts, max_attempts, clock):
    if burst is None:
        burst = BurstPolicy(open_ts=at_ts, base_deadline=float(at_ts) + float(window_s),
                            sign_end_ts=sign_end_ts, max_attempts=max_attempts,
                            clock=clock, retry_start=at_ts)
    if state is None:
        state = _initial_loop_state(burst)
    return burst, state


def run_submit_loop(page, *, activity_id, at_ts, window_s, sign_end_ts=None,
                    max_attempts=0, is_joined_fn=None, notify_fn=None,
                    clock=None, log_fn=None, name="活动",
                    default_log_fn=None, default_notify_fn=None, classify_fn=None,
                    burst=None, state=None):
    """事件驱动非阻塞提交循环（黄金风暴/全速/404 自适应）。

    只做「盯按钮 → 点击 → 记账 → 收口」，不做登录和浏览器生命周期：
    页面、查询、通知、时钟全部注入，单测用替身即可覆盖全部阶段转移。
    返回 (stop_reason, state)；state 含 attempts/pending/404_streak/backoff_s
    等日志字段。未决不伪造成失败：停止时仍有 pending 就报 unconfirmed。
    """
    log = log_fn or default_log_fn
    notify_owner = notify_fn or default_notify_fn
    classify = classify_fn or classify_response
    burst, state = _ensure_loop_context(burst, state, at_ts, window_s,
                                        sign_end_ts, max_attempts, clock)
    request_to_bid, response_queue = {}, []
    armed = {"on": False, "dead": False}

    def _drain():
        _drain_responses(response_queue, burst=burst, state=state,
                         request_to_bid=request_to_bid, classify_fn=classify, log_fn=log)

    def _pump(seconds):
        _pump_wait(page, seconds, burst=burst, state=state, clock=clock, drain_fn=_drain)

    def _finish(reason):
        return finish_submit_loop(reason, burst=burst, state=state, name=name,
                                  log_fn=log, notify_owner=notify_owner)

    listeners = _attach_listeners(
        page, burst=burst, state=state, request_to_bid=request_to_bid,
        response_queue=response_queue, armed=armed, log_fn=log)
    armed["on"] = True
    log("[i] 开始盯按钮 %s" % _format_log_fields(burst, state))

    try:
        stop_reason = _drive_click_loop(
            page, burst=burst, state=state, at_ts=at_ts, clock=clock,
            drain_fn=_drain, pump_fn=_pump)
        return _closeout_submit_loop(
            page, activity_id=activity_id, burst=burst, state=state,
            stop_reason=stop_reason, clock=clock, is_joined_fn=is_joined_fn,
            drain_fn=_drain, pump_fn=_pump, finish_fn=_finish)
    except KeyboardInterrupt:
        # 用户停止（Ctrl-C / 终止信号）立即收口；已发出的请求如实保留未决
        burst.stop("user_stopped")
        state["last_reason"] = "收到中断"
        return _finish("user_stopped")
    except Exception as exc:  # noqa: BLE001 - 浏览器/管道异常也要有唯一终态
        burst.stop("process_error")
        state["last_reason"] = "运行异常：%s" % type(exc).__name__
        return _finish("process_error")
    finally:
        _detach_listeners(page, armed, listeners)
