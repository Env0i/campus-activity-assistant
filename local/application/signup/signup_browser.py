# -*- coding: utf-8 -*-
"""报名 worker 的浏览器阶段：开页、dry-run、已报名前置核对、等待开放、监听注册与解除、主调度循环与点击兜底、关浏览器。

从 grab.py 的 cmd_grab 搬出：与直发通道、调度账本和统一有界收尾协同工作，
在 finally 中解除页面监听、关闭直发传输与浏览器实例，且绝不在 finally 中 return。

@author Author
"""
from __future__ import annotations

from application.signup.signup_direct import (
    downgrade_to_click,
    new_direct_state,
    precheck_before_open,
    rekey_after_relogin,
    rekey_after_version,
    setup_direct_path,
    try_direct_fire,
)
from application.signup.signup_finalize import finalize, may_fire, pump_wait
from application.signup.signup_ledger import settle_pending
from application.signup.signup_outcome import SubmitAborted, budget_stop, clock_stop, terminal


def _is_signup_url(ports, url_text):
    return url_text.startswith(ports.BASE) and "/rjyHdCyr/signUp/" in url_text


def _make_listeners(ctx):
    """创建页面 request / response / requestfailed 三个只入队回调（F05：回调内零 I/O、零读钟）。"""
    ports = ctx.ports

    def on_request(request):
        # F05：回调只校验监听状态/URL 并入本场队列——不登记、不结算、不刷策略、不读业务钟、不打日志
        if ctx.armed["dead"] or not ctx.armed["on"]:
            return
        # 直发在途（未降级）时，页面自发的同源请求不入账本、不改结论
        if ctx.direct["enabled"] and not ctx.direct["downgrade"]:
            return
        try:
            url_text = str(request.url)
        except Exception:
            return
        if not _is_signup_url(ports, url_text):
            return
        ident = id(request)
        if ident in ctx.seen_ids:
            return          # 同一个 Request 重复通知只计 1
        ctx.seen_ids.add(ident)
        ctx.response_queue.append(("request", request))

    def on_response(response):
        # 回调只入队：结算统一走主循环的事件泵，不在回调里做 I/O
        if ctx.armed["dead"]:
            return
        if ctx.direct["enabled"] and not ctx.direct["downgrade"]:
            return
        try:
            url_text = str(response.url)
        except Exception:
            return
        if not _is_signup_url(ports, url_text):
            return
        ctx.response_queue.append(response)

    def on_requestfailed(request):
        # 回调只入队：导航中止只发 requestfailed，没有 response，交 settle_failed 按既有 request_id 结算为 lost
        if ctx.armed["dead"]:
            return
        if ctx.direct["enabled"] and not ctx.direct["downgrade"]:
            return
        try:
            url_text = str(request.url)
        except Exception:
            return
        if not _is_signup_url(ports, url_text):
            return
        ctx.response_queue.append(("failed", request))

    return on_request, on_response, on_requestfailed


def _open_page_and_fetch_key(ctx, browser):
    """建浏览器上下文与页面，先取运行时密钥再打开详情页（页面失败但有密钥时只关点击兜底）。"""
    ports = ctx.ports
    browser_ctx = ports.new_context(browser)
    ctx.page = browser_ctx.new_page()
    # 直发密钥先于开页面取（决策 015）：直发不依赖页面，开放那一刻页面打不开也照常发；dry-run 只看页面，不取
    runtime_key, key_reason = None, "dry-run 不取"
    if not ctx.args.dry_run:
        runtime_key, key_reason = ports.fetch_runtime_key(ctx.budget)
        ports.log("[i] 运行时密钥：%s" % key_reason)
    ctx.page_state = {"ok": True}
    url = ports.BASE + "/stu/" + ports.DETAIL_HASH.format(aid=ctx.target["id"])
    try:
        ctx.page.goto(url, wait_until="domcontentloaded",
                      timeout=ctx.budget.timeout_ms(60000))
    except (ports.ClockUnavailable, ports.BudgetExhausted):
        raise
    except Exception as exc:  # noqa: BLE001 - 有密钥时页面失败只关掉点击兜底
        if runtime_key is None or ctx.args.dry_run:
            raise
        ctx.page_state["ok"] = False
        ports.log("[!] 详情页打不开（%s）：直发照常，点击兜底不可用" % type(exc).__name__)
    if ctx.page_state["ok"]:
        # 页面渲染稳定最多等 1.5 秒，但绝不把短窗口整个吃掉
        ctx.budget.sleep(min(1.5, max(0.2, ctx.budget.remaining_s() * 0.25)))
        ports._checkpoint_event("page_opened")
        ports.log("[i] 详情页已加载")
    return runtime_key, key_reason


def _precheck_and_wait_start(ctx):
    """处理 dry-run、已报名前置核对（F07）与等到提前开页时刻；提前结束时返回退出码，否则返回 None。"""
    ports = ctx.ports
    if ctx.args.dry_run:
        btns = ctx.page.eval_on_selector_all(
            "uni-button", "els => els.map(e => e.innerText.trim()).filter(Boolean)")
        ports.log("[i] dry-run：joined=%s buttons=%s"
                  % (ports.is_joined(ctx.target["id"], budget=ctx.budget), btns))
        return 0
    # 前置核对与最终核对分开（F07）：这里查询失败不等于没报名，吞掉非时钟异常后照常进入盯按钮
    try:
        joined = ports.is_joined(ctx.target["id"], budget=ctx.budget)
    except ports.ClockUnavailable:
        raise
    except Exception:
        joined = None
    if joined is True:
        return terminal(ctx, "already_signed")
    if joined is None:
        ctx.state["last_reason"] = "已有报名查询未确认"
    if not ctx.args.headed:
        print("[i] 后台等待中，到点自动提交；想看着它点就加 --headed。")
    ports.wait_until(ctx.start, ctx.budget)
    return None


def _init_watch_state(ctx, runtime_key, key_reason, now_entry):
    """初始化 BurstPolicy、受控提交集合、直发通道、开放前预检并挂载页面监听。"""
    ports = ctx.ports
    if now_entry >= ctx.at_ts:
        ports.log("[i] 活动已开放，立即报名/抢名额")
    else:
        ports.log("[i] 开始等待开放")
    ctx.reload_gap = 2.0
    ctx.last_reload = 0.0
    ctx.confirm_open = False   # F07：确认框重入状态（超时保留弹窗）
    ctx.stop_reason = ""
    base_dl = (ctx.state["deadline"]
               or ports._policy_window(ctx.frozen, ctx.sign_end_ts, ctx.retry_for)[0])
    ctx.burst = ports.BurstPolicy(
        open_ts=ctx.at_ts,
        base_deadline=base_dl,
        sign_end_ts=ctx.sign_end_ts,
        max_attempts=ctx.args.max_attempts,
        clock=ctx.clock,
        retry_start=ctx.frozen or ctx.at_ts,
        allow_extend=ctx.args.retry_for is None or ctx.retry_for == ports.ADAPTIVE_RETRY,
    )
    ctx.admitted_ids = set()
    ctx.seen_ids = set()
    ctx.admitted_all = []
    ctx.request_to_bid = {}
    ctx.response_queue = []
    ctx.direct = new_direct_state(ports)
    ctx.finalize_state = {"tail_deadline": None, "frozen": False}
    setup_direct_path(ctx, runtime_key, key_reason)
    ctx.finalize_fn = lambda sr, fallback=None: finalize(ctx, sr, fallback=fallback)
    # 未来场次：开放前约 45 秒预检一次，再等到开放前 POLL_LEAD 秒开始盯
    if now_entry < ctx.at_ts:
        precheck_before_open(ctx, now_entry)
        if not (ctx.state["resp_ok"] or ctx.state["terminal_reason"]
                or ctx.state["login_suspect"] or ctx.direct.get("protocol_stop")):
            ports.wait_until(ctx.at_ts - ports.POLL_LEAD, ctx.budget)
    if ctx.page_state["ok"]:
        on_req, on_resp, on_fail = _make_listeners(ctx)
        for name, fn in (("request", on_req), ("response", on_resp), ("requestfailed", on_fail)):
            ctx.listeners.append((name, fn))
            ctx.page.on(name, fn)
    ctx.armed["on"] = True    # 整个提交阶段受控：在途响应按 request_id 结算
    ports._checkpoint_event("watch_started")
    ports.log("[i] 开始盯按钮")


def _handle_login_check(ctx):
    """提交中收到 4001 后的在途等待、登录复查与自动重登交接；返回 'continue' 或 'break'。"""
    ports = ctx.ports
    state = ctx.state
    if state["pending"] > 0 or ctx.direct["reserved"] > 0:
        pump_wait(ctx, ports.INFLIGHT_WAIT_S)
        return "continue"
    recheck, _detail = ports.probe_token(ctx.budget)
    if recheck == "expired":
        if not ctx.wait_for_relogin("提交中"):
            state["login_invalid"] = True
            ctx.stop_reason = "login_invalid"
            return "break"
        rekey_after_relogin(ctx)
        state["login_suspect"] = False
        return "continue"
    state["login_suspect"] = False
    ports.log("[i] 复查登录结论 %s：不判失效，继续发送" % recheck)
    return "continue"


def _handle_gate_verdict(ctx, verdict):
    """处理发射闸门非 'ok' 的返回值；返回 'continue' 或 'break'。"""
    ports = ctx.ports
    state = ctx.state
    if verdict == "success":
        return "break"
    if verdict == "login_invalid":
        ctx.stop_reason = "login_invalid"
        return "break"
    if verdict == "terminal":
        ctx.stop_reason = state["terminal_reason"]
        return "break"
    if verdict == "login_check":
        return _handle_login_check(ctx)
    if verdict == "protocol_stop":
        ctx.stop_reason = "process_error"
        return "break"
    if verdict == "attempts":
        if state["attempts"] >= ctx.args.max_attempts > 0:
            ctx.stop_reason = "max_attempts"
        else:
            ctx.stop_reason = ("sign_end" if (ctx.sign_end_ts and
                               ctx.burst.effective_deadline >= ctx.sign_end_ts)
                               else "retry_duration")
        return "break"
    if verdict == "clock":
        ctx.stop_reason = "unconfirmed" if state["pending"] > 0 else "clock_unavailable"
        if ctx.stop_reason == "clock_unavailable":
            state["last_reason"] = "北京时间暂不可用"
        return "break"
    if verdict == "not_open":
        try:
            _now_lower, _now_upper = ports.business_bounds()
        except ports.ClockUnavailable:
            ctx.stop_reason = "unconfirmed" if state["pending"] > 0 else "clock_unavailable"
            return "break"
        pump_wait(ctx, min(0.25, max(0.0, ctx.at_ts - _now_lower)))
        return "continue"
    # verdict == "inflight"
    pump_wait(ctx, ports.INFLIGHT_WAIT_S)
    return "continue"


def _click_confirm_box(ctx, btn, round_start):
    """执行点开确认框、二次闸门检查与点「确定」，返回是否因本地闸门主动中止 (aborted)。"""
    ports = ctx.ports
    state = ctx.state
    aborted = False
    try:
        if not ctx.confirm_open:
            btn.first.click(timeout=ctx.budget.timeout_ms(3000))
            ctx.confirm_open = True
        # 打开确认框后、点「确定」前再过一次闸门（含名额满原地等≤1s）
        gate2 = may_fire(ctx)
        if gate2 == "inflight":
            waited = 0.0
            while gate2 == "inflight" and waited < ports.CONFIRM_INFLIGHT_WAIT_S:
                pump_wait(ctx, ports.INFLIGHT_WAIT_S)
                waited += ports.INFLIGHT_WAIT_S
                gate2 = may_fire(ctx)
        if gate2 in ("success", "login_invalid", "terminal"):
            aborted = True
            state["last_reason"] = "确认前已出结论，取消本次确认"
        elif gate2 != "ok":
            aborted = True
            state["last_reason"] = "确认前闸门未过（%s）" % gate2
            raise SubmitAborted(state["last_reason"])
        else:
            if ctx.budget.expired():
                raise SubmitAborted("确认前重试窗口已到点")
            if ports.business_now() < ctx.at_ts:
                raise SubmitAborted("确认前还没到开放时间")
            ctx.page.get_by_text("确定", exact=True).first.click(
                timeout=ctx.budget.timeout_ms(3000))
    except ports.ClockUnavailable:
        raise           # 校时失效不是点击失败：交统一收尾
    except SubmitAborted as exc:
        aborted = True
        state["last_reason"] = str(exc)
    except ports.PlaywrightTimeoutError:
        state["last_reason"] = ("点击确认超时" if ctx.admitted_all[round_start:]
                                else "点击后没发出提交请求")
    except Exception as exc:
        state["last_reason"] = ("点击确认失败：%s" % type(exc).__name__
                                if ctx.admitted_all[round_start:]
                                else type(exc).__name__)
    return aborted


def _run_click_step(ctx):
    """单轮点击兜底：找「立即报名」或刷新页面、点确认框、结算本轮请求并推进退避节奏。"""
    ports = ctx.ports
    state = ctx.state
    if ctx.confirm_open and ctx.page.get_by_text("确定", exact=True).count() == 0:
        ctx.confirm_open = False
    btn = None
    if not ctx.confirm_open:
        btn = ctx.page.locator("uni-button").filter(has_text="立即报名")
        if not btn.count():
            if ports.time.monotonic() - ctx.last_reload >= ctx.reload_gap:
                ctx.page.reload(wait_until="domcontentloaded",
                                timeout=ctx.budget.timeout_ms(60000))
                pump_wait(ctx, 0.25)
                ctx.last_reload = ports.time.monotonic()
                ctx.reload_gap = min(8.0, ctx.reload_gap * 1.5)
            else:
                pump_wait(ctx, 0.3)
            return "continue"
    round_start = len(ctx.admitted_all)
    aborted = _click_confirm_box(ctx, btn, round_start)
    round_requests = ctx.admitted_all[round_start:]
    settle_pending(ctx, downgrade_to_click)
    if not round_requests and not aborted:
        ports.log("[i] 本次点击没有发出提交：%s"
                  % (state["last_reason"] or "未点开确认框"))
    if state["resp_ok"]:
        return "break"
    if len(round_requests) > 1:
        state["last_reason"] = "一次动作发出 %d 次提交" % len(round_requests)
    if state["login_invalid"]:
        ctx.stop_reason = "login_invalid"
        return "break"
    if state["terminal_reason"]:
        ctx.stop_reason = state["terminal_reason"]
        return "break"
    if not ctx.burst.can_attempt():
        if state["attempts"] >= ctx.args.max_attempts > 0:
            ctx.stop_reason = "max_attempts"
        else:
            ctx.stop_reason = ("sign_end" if (ctx.sign_end_ts and
                               ctx.burst.effective_deadline >= ctx.sign_end_ts)
                               else "retry_duration")
        return "break"
    gap = ctx.burst.interval_s()
    pump_wait(ctx, min(max(0.0, gap), max(0.0, ctx.budget.remaining_s())))
    ctx.burst.next_interval_after_wait()
    return "continue"


def _run_dispatch_loop(ctx):
    """主调度循环：统一发射闸门 → 直发为主 → 点击兜底。"""
    ports = ctx.ports
    direct = ctx.direct
    while not ctx.budget.expired():
        verdict = may_fire(ctx)
        if verdict != "ok":
            if _handle_gate_verdict(ctx, verdict) == "break":
                break
            continue
        if direct["enabled"] and not direct["downgrade"] and direct["need_rekey"]:
            rekey_after_version(ctx)
        if direct["enabled"] and not direct["downgrade"]:
            res = try_direct_fire(ctx)
            if res == "fired":
                gap = ctx.burst.interval_s()
                pump_wait(ctx, min(max(0.0, gap), max(0.0, ctx.budget.remaining_s())))
                ctx.burst.next_interval_after_wait()
                continue
            if res == "busy":
                pump_wait(ctx, ports.INFLIGHT_WAIT_S)
                continue
            if res == "stop":
                ctx.stop_reason = "process_error"
                break
            # res == "downgrade"：本场单向切到下方点击兜底
        if not ctx.page_state["ok"]:
            ctx.stop_reason = "page_unavailable"
            break
        if _run_click_step(ctx) == "break":
            break


def _cleanup_browser_resources(ctx, browser):
    """停止/异常路径统一解除监听、关直发通道与浏览器（finally 专用，绝不 return）。"""
    ctx.armed["on"] = False
    ctx.armed["dead"] = True
    for event_name, handler in ctx.listeners:
        try:
            ctx.page.remove_listener(event_name, handler)
        except Exception:
            pass
    if ctx.direct is not None and ctx.direct.get("transport") is not None:
        try:
            ctx.direct["transport"].close()
        except Exception:
            pass
    try:
        browser.close()
    except Exception:
        pass


def run_browser_phase(ctx):
    """在 sync_playwright 上下文内运行整段浏览器与直发调度，并在关浏览器前完成有界收尾。"""
    ports = ctx.ports
    with ports.sync_playwright() as pw:
        browser = ports.launch_browser(pw, headless=not ctx.args.headed)
        ctx.armed = {"on": False, "dead": False}
        ctx.listeners = []
        ctx.burst = None
        ctx.direct = None
        ctx.finalize_fn = None
        try:
            runtime_key, key_reason = _open_page_and_fetch_key(ctx, browser)
            early_code = _precheck_and_wait_start(ctx)
            if early_code is not None:
                return early_code
            try:
                now_entry = ports.business_now()
            except ports.ClockUnavailable:
                return clock_stop(ctx)
            _init_watch_state(ctx, runtime_key, key_reason, now_entry)
            _run_dispatch_loop(ctx)
            return ctx.finalize_fn(ctx.stop_reason)
        except ports.ClockUnavailable:
            if ctx.finalize_fn is None:
                return clock_stop(ctx)
            return ctx.finalize_fn("clock_unavailable")
        except ports.BudgetExhausted:
            fallback = ("sign_end" if ctx.state["binding"] == "sign_end"
                        else "retry_duration")
            if ctx.finalize_fn is None:
                return budget_stop(ctx, "页面")
            return ctx.finalize_fn(fallback, fallback=fallback)
        except Exception as exc:  # noqa: BLE001 - 流程异常也要在关浏览器前收口
            ctx.state["last_reason"] = "运行异常：%s" % type(exc).__name__
            if ctx.finalize_fn is None:
                return terminal(ctx, "process_error")
            return ctx.finalize_fn("process_error", fallback="process_error")
        finally:
            _cleanup_browser_resources(ctx, browser)
