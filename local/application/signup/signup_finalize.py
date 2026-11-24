# -*- coding: utf-8 -*-
"""报名 worker 的发射闸门、短事件泵与统一有界收尾。

从 grab.py 的 cmd_grab 搬出：发射闸门（drain→成功→4001→次数/截止→业务时间→名额）、
50ms 切片短事件泵、统一有界收尾（冻结接纳、1 秒尾窗、成功粘性、单次最终核对）
以及收尾异常退路优先级。

@author Author
"""
from __future__ import annotations

from application.signup.signup_direct import downgrade_to_click
from application.signup.signup_ledger import settle_pending
from application.signup.signup_outcome import terminal


def pump_wait(ctx, seconds):
    """短事件泵：按预算截断等待，同时派发并结算在途响应。

    Playwright 同步 API 在等待里派发事件回调；成功/登录失效
    立即返回，让调度循环收成唯一终态。等待按整毫秒推进，
    不让浮点截断把 90ms 间隔悄悄吃短。
    返回 True 表示页面仍可继续；False 表示 page 不存在/已关闭/
    等待抛错（F06：调用方必须有界停泵，不得空转烧满尾窗）。
    """
    ports = ctx.ports
    state = ctx.state
    remain = ctx.budget.remaining_s()
    wait_s = max(0.0, min(float(seconds), remain))
    # 请求了等待就必须有推进：亚毫秒余量取 1ms，否则边界泵会空转
    wait_ms = int(round(wait_s * 1000)) if wait_s > 0 else 0
    if wait_s > 0:
        wait_ms = max(1, wait_ms)
    deadline_ms = int(round(ports.time.monotonic() * 1000)) + wait_ms
    while True:
        left_ms = deadline_ms - int(round(ports.time.monotonic() * 1000))
        if left_ms <= 0:
            break
        try:
            if ctx.page_state["ok"]:
                ctx.page.wait_for_timeout(min(left_ms, 50))  # 50ms 一片
            else:
                # 页面打不开时只剩直发：按时间片等，直发事件照常由
                # settle_pending 结算（直发不依赖页面派发事件）
                ports.time.sleep(min(left_ms, 50) / 1000.0)
        except Exception:
            return False    # 页面不可用：立即停泵
        settle_pending(ctx, downgrade_to_click)
        if (state["resp_ok"] or state["login_invalid"]
                or state["login_suspect"] or state["terminal_reason"]):
            return True
    return True


def may_fire(ctx):
    """统一发射闸门：drain → 成功 → 4001 → 次数/截止 → 业务时间 → 名额。

    返回 "ok" 才允许发下一笔；其余为不发原因（调用方据此收口或原地等）。
    回调路径不读时钟的部分用 current_phase，业务时间用 business_bounds。
    """
    ports = ctx.ports
    state = ctx.state
    direct = ctx.direct
    burst = ctx.burst
    settle_pending(ctx, downgrade_to_click)
    if state["resp_ok"]:
        return "success"
    if state["login_invalid"]:
        return "login_invalid"
    if state["login_suspect"]:
        return "login_check"   # 提交中收到 4001：先复查，确认前不发
    if state["terminal_reason"]:
        return "terminal"      # 学校已明确拒绝（名额满等）：本场不再发
    if direct.get("protocol_stop"):
        return "protocol_stop"
    if not burst.can_attempt():
        return "attempts"
    # 直发已提交未 started 的预留也占次数/名额配额（started 滞后也不允许第二笔）；
    # 预留只是暂时占用，占满时泵等核清，不当作真实 attempts 耗尽漏账终止
    if (ctx.args.max_attempts > 0
            and burst.attempts + direct["reserved"] >= ctx.args.max_attempts):
        if direct["reserved"] > 0:
            return "inflight"
        return "attempts"
    try:
        now_lower, _now_upper = ports.business_bounds()
    except ports.ClockUnavailable:
        return "clock"
    if now_lower < ctx.at_ts:
        return "not_open"
    if burst.inflight_count() + direct["reserved"] >= ports.MAX_INFLIGHT:
        return "inflight"
    return "ok"


def fallback_terminal(ctx, exc):
    """finalize 异常退路统一终态优先级（F06）：已确认成功 >
    有未决 unconfirmed > 无未决的对应异常。不重入、不重建
    尾窗、不因异常再做学校请求；校时/预算异常同样不跳过
    已入账成功或未决事实。"""
    ports = ctx.ports
    state = ctx.state
    if state["resp_ok"]:
        return terminal(ctx, "success")
    if state.get("pending", 0) > 0:
        return terminal(ctx, "unconfirmed")
    if isinstance(exc, ports.ClockUnavailable):
        state["last_reason"] = "北京时间暂不可用"
        return terminal(ctx, "clock_unavailable")
    if isinstance(exc, ports.BudgetExhausted):
        return terminal(
            ctx, "sign_end" if state["binding"] == "sign_end" else "retry_duration")
    return terminal(ctx, "process_error")


def _freeze_and_pump_tail(ctx):
    """先冻结新接纳、收齐已提交 started，并运行一次性 1 秒尾窗（受预算/sign_end 截断）。"""
    ports = ctx.ports
    state = ctx.state
    direct = ctx.direct
    finalize_state = ctx.finalize_state
    # 先冻结新接纳（F04）：close 与 started 提交同锁原子，close 返回后不再产生新的 started
    if direct.get("transport") is not None:
        try:
            direct["transport"].close()
        except Exception:
            pass
    # 再 drain 提交点已入队的 started/completed，然后取消未跨点预留
    settle_pending(ctx, downgrade_to_click)
    for reg in direct["registry"].values():
        if reg["state"] == "reserved":
            reg["state"] = "cancelled"
    direct["reserved"] = 0
    # 1 秒尾窗（main 语义，取消 not login_invalid：4001 后同窗内成功仍可结算）
    try:
        tail_gate = state["pending"] > 0 and not ctx.budget.expired()
    except ports.ClockUnavailable:
        tail_gate = False
    if tail_gate and finalize_state["tail_deadline"] is None:
        try:
            finalize_state["tail_deadline"] = (
                ports.time.monotonic()
                + min(1.0, max(0.0, ctx.budget.remaining_s())))
        except ports.ClockUnavailable:
            pass
    tail_deadline = finalize_state["tail_deadline"]
    if tail_gate and tail_deadline is not None:
        try:
            while (ports.time.monotonic() < tail_deadline
                   and not ctx.budget.expired()
                   and state["pending"] > 0
                   and not state["resp_ok"]):
                tail_left = tail_deadline - ports.time.monotonic()
                if tail_left <= 0 or not pump_wait(ctx, min(0.05, tail_left)):
                    break
        except ports.ClockUnavailable:
            pass    # 时钟失效：收尾泵停；可读队列已由 settle_pending 结算
    # 尾窗结束冻结响应接纳（F06）：核对期间不再 drain 迟到完成事件
    finalize_state["frozen"] = True


def finalize_once(ctx, stop_reason, fallback=None):
    """执行一次完整的冻结、1 秒尾窗、成功粘性判定与单次 getJoinInfo 最终核对。"""
    ports = ctx.ports
    state = ctx.state
    _freeze_and_pump_tail(ctx)
    # 成功粘性最优先：已到 code=1 就是成功，不被 False/异常覆盖（F01）
    if state["resp_ok"]:
        return terminal(ctx, "success")
    if state["login_invalid"] or state["login_suspect"]:
        # 4001 待确认但预算已到、来不及复查：按登录失效收口（与原行为一致）
        stop_reason = "login_invalid"
    elif state["terminal_reason"]:
        stop_reason = state["terminal_reason"]
    # 单次最终核对（F07 / 决策 015）：只要发过提交就查一次学校的报名状态，
    # 原预算用完、报名截止之后也查；用单独的 FINAL_CHECK_S 小预算，
    # 只查这一次、不循环，不引入 not_joined。没有可信北京时间就不查。
    check_budget = None
    if state["attempts"]:
        try:
            check_budget = ports.RetryBudget(
                ports.business_now() + ports.FINAL_CHECK_S, business_clock=ctx.clock)
        except ports.ClockUnavailable:
            check_budget = None
    if check_budget is not None:
        # 最终核对失败走统一退路优先级（F06）：不重入、不因异常再做学校请求
        try:
            joined_now = ports.is_joined(ctx.target["id"], budget=check_budget)
        except Exception as exc:
            return fallback_terminal(ctx, exc)
        if joined_now is True:
            return terminal(ctx, "success")
    # pending 且无成功＝未确认（F02）
    if state["pending"] > 0:
        return terminal(ctx, "unconfirmed")
    if stop_reason:
        return terminal(ctx, stop_reason)
    if fallback:
        return terminal(ctx, fallback)
    return terminal(
        ctx, "sign_end" if state["binding"] == "sign_end" else "retry_duration")


def finalize(ctx, stop_reason, fallback=None):
    """统一有界收尾（F04/F06）：先冻结新接纳、收齐已提交 started，
    一次性 1 秒尾窗（受预算/sign_end 截断），再按「成功粘性最优先」
    解析唯一终态。page/时钟不可用不忙转；反复进入不重建尾窗。
    """
    finalize_state = ctx.finalize_state
    if finalize_state.get("result") is not None:
        return finalize_state["result"]   # 不重入、不重建尾窗
    try:
        result = finalize_once(ctx, stop_reason, fallback)
    except Exception as exc:
        # 所有异常退路（普通/校时/预算）共用同一终态优先级
        result = fallback_terminal(ctx, exc)
    finalize_state["result"] = result
    return result
