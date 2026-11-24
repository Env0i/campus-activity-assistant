# -*- coding: utf-8 -*-
"""报名 worker 的主入口 run_signup 与准备阶段编排。

从 grab.py 的 cmd_grab 搬出：入口业务时钟校验、冻结起点与重试窗口、预算建立、
鉴权与等待自动登录、粗校时、查目标、窗口事件、进浏览器前的预算检查，
以及最外层三类异常到唯一终态的映射。

所有外部边界均通过每次调用时组装的 ports 对象传入，本模块不持有任何模块级可变状态。

@author Author
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from application.signup.signup_browser import run_browser_phase
from application.signup.signup_ledger import new_signup_state
from application.signup.signup_outcome import budget_stop, clock_stop, terminal


def wait_for_relogin(ctx, where):
    """确认登录失效后等界面自动登录：最多 relogin_wait_s 秒，期间不提交。

    发 login_wait 事件让界面做一次自动登录；这里只读登录态文件，
    换成新 token 且复查有效才返回 True。不等、窗口不够或等不到都返回 False。
    """
    ports = ctx.ports
    if ctx.relogin_wait_s <= 0:
        return False
    try:
        remain = ctx.budget.remaining_s()
    except ports.ClockUnavailable:
        return False
    wait_s = min(ctx.relogin_wait_s, remain - 1.0)
    if wait_s <= 0:
        return False
    old = ports.token()
    ports.log("[!] 登录失效（%s）：等自动登录，最多 %d 秒，期间不提交" % (where, int(wait_s)))
    ports._retry_event(kind="login_wait", wait_s=int(wait_s))
    until = ports.time.monotonic() + wait_s
    while ports.time.monotonic() < until:
        ports.time.sleep(min(0.5, max(0.0, until - ports.time.monotonic())))
        fresh = ports.token()
        if not fresh or fresh == old:
            continue
        try:
            again, _detail = ports.probe_token(ctx.budget)
        except (ports.BudgetExhausted, ports.ClockUnavailable):
            return False
        if again == "valid":
            ports.log("[i] 自动登录完成：换上新的登录态，继续")
            ports._retry_event(kind="login_resumed")
            return True
        old = fresh     # 新登录态也不行：继续等下一次写入
    ports.log("[X] 等自动登录超时（%s）" % where)
    return False


def _init_entry_clock(ports):
    """入口即建立独立北京时间并记录 worker_started 节点；不可用时返回 (None, None, 3)。"""
    clock = ports.setup_business_clock(allow_sync=True)
    if clock is None:
        ports.log("[X] 北京时间未校准，本次自动报名不启动")
        print("\n[X] 暂时无法获取可信北京时间，自动报名没有开始。")
        print("    登录态与活动列表不受影响；稍后重试。")
        return None, None, 3
    try:
        entry_epoch = ports.business_now()
    except ports.ClockUnavailable:
        ports.log("[X] 北京时间在入口处不可用，本次自动报名不启动")
        print("\n[X] 暂时无法获取可信北京时间，自动报名没有开始。")
        return None, None, 3
    ports._checkpoint_event("worker_started", entry_epoch)
    return clock, entry_epoch, None


def _parse_entry_times(args, ports):
    """解析命令行的 sign_end 与 at；格式错误时打印提示并返回 (None, None, 2)。"""
    try:
        sign_end_ts = ports.parse_ts(args.sign_end) if args.sign_end else None
    except ValueError:
        print("[X] 报名截止时间格式不对：%r" % (args.sign_end,))
        return None, None, 2
    try:
        at_ts = ports.parse_ts(args.at) if args.at else None
    except ValueError:
        print("[X] 报名开始时间格式不对：%r" % (args.at,))
        return None, None, 2
    return sign_end_ts, at_ts, None


def _build_initial_budget(ctx):
    """在任何阻塞前建立初始预算；窗口已过或时钟失效时直接返回终态退出码。"""
    ports = ctx.ports
    try:
        if ctx.preflight_only:
            # CLI 没给开放时间：只给“查目标”一段有界前置预算，绝不无限查询
            ctx.budget = ports.RetryBudget(
                ctx.entry_epoch + ports.PREFLIGHT_BUDGET_S, business_clock=ctx.clock)
        else:
            deadline, binding = ports._policy_window(
                ctx.frozen, ctx.sign_end_ts, ctx.retry_for)
            ctx.state["deadline"], ctx.state["binding"] = deadline, binding
            ctx.budget = ports.RetryBudget(deadline, business_clock=ctx.clock)
            if ctx.budget.expired():
                ctx.state["last_reason"] = "重试窗口在启动前已结束"
                return terminal(
                    ctx, "sign_end" if binding == "sign_end" else "retry_duration")
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    return None


def _check_auth_and_clock_sample(ctx):
    """执行受预算约束的入场鉴权（含等待自动重登）与粗校时采样；提前结束返回退出码。"""
    ports = ctx.ports
    try:
        token_state, token_detail = ports.probe_token(ctx.budget)
    except ports.BudgetExhausted:
        return budget_stop(ctx, "鉴权")
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    if token_state == "none":
        print("[X] %s" % token_detail)
        print("    请先运行：python grab.py login")
        return 3
    if token_state == "expired":
        ctx.state["last_reason"] = token_detail
        try:
            relogged = wait_for_relogin(ctx, "开抢前检查")
        except ports.BudgetExhausted:
            return budget_stop(ctx, "鉴权")
        except ports.ClockUnavailable:
            return clock_stop(ctx)
        if not relogged:
            return terminal(ctx, "login_invalid")
        ctx.state["last_reason"] = ""
    if token_state == "unknown":
        ctx.state["last_reason"] = token_detail
        return terminal(ctx, "auth_unavailable")
    return _maybe_run_clock_sample(ctx)


def _maybe_run_clock_sample(ctx):
    """剩余预算大于 1.5 秒时做一次 HTTP Date 粗校时采样。"""
    ports = ctx.ports
    try:
        remaining_before_sample = ctx.budget.remaining_s()
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    if remaining_before_sample > 1.5:
        try:
            sample = ports.clock_sample(timeout_s=ctx.budget.timeout_s(6))
        except ports.BudgetExhausted:
            return budget_stop(ctx, "粗校时")
        except ports.ClockUnavailable:
            return clock_stop(ctx)
        ports.log("[clock] " + json.dumps(sample, ensure_ascii=False, separators=(",", ":")))
        if sample.get("state") == "warn":
            print("[!] 学校 HTTP Date 粗测与本机有偏差（含网络误差约 ±%.1f 秒）；"
                  "该粗测只作诊断参考，报名调度按工具的独立北京时间执行。"
                  % (sample.get("uncertainty_s") or 1.0))
    return None


def _resolve_and_announce_window(ctx):
    """查询目标活动、必要时重建正式预算、打印窗口提示并发出 kind=window 事件。"""
    ports = ctx.ports
    try:
        target = ports.resolve_target(ctx.args, budget=ctx.budget)
    except ports.BudgetExhausted:
        return budget_stop(ctx, "查目标")
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    if not target:
        return 0
    ctx.target = target
    ctx.display = target["name"]
    ports._EVENT_CONTEXT["activity_id"] = str(target.get("id") or "")
    try:
        ctx.at_ts = ports.parse_ts(target["at"])
    except ValueError:
        print("[X] 报名开始时间格式不对：%r" % (target["at"],))
        return 2
    if ctx.preflight_only:
        ctx.frozen = ports.retry_anchor(ctx.at_ts, ctx.entry_epoch)
        deadline, binding = ports._policy_window(
            ctx.frozen, ctx.sign_end_ts, ctx.retry_for)
        ctx.state["deadline"], ctx.state["binding"] = deadline, binding
        try:
            ctx.budget = ports.RetryBudget(deadline, business_clock=ctx.clock)
            if ctx.budget.expired():
                ctx.state["last_reason"] = "重试窗口在查目标时已结束"
                return terminal(
                    ctx, "sign_end" if binding == "sign_end" else "retry_duration")
        except ports.ClockUnavailable:
            return clock_stop(ctx)
    _announce_target_window(ctx)
    try:
        if not ctx.args.dry_run and ctx.budget.expired():
            return budget_stop(ctx, "前置检查")
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    return None


def _announce_target_window(ctx):
    """输出目标、模式与截止提示，并广播 [retry] kind=window 事件。"""
    ports = ctx.ports
    target = ctx.target
    ctx.start = (ctx.entry_epoch if ctx.args.dry_run
                 else ctx.at_ts - max(0.0, float(ctx.args.lead or 0.0)))
    print("[i] 目标：%s" % ctx.display)
    original_at = target.get("original_at") or ""
    ctx.instant_mode = bool(original_at and original_at != target["at"])
    if ctx.instant_mode:
        print("[i] 活动已开放，本次立即报名/抢名额（原定开放 %s）" % original_at)
        print("[i] 本次执行：%s；失败重试窗口 %.0f 秒" % (target["at"], ctx.args.window))
    else:
        print("[i] 报名开始：%s；提前 %.0f 秒打开页面；失败重试窗口 %.0f 秒"
              % (target["at"], ctx.args.lead, ctx.args.window))
    if ctx.sign_end_ts:
        ports.log("[i] 报名截止：%s；重试到 %s 截止"
                  % (ports._ts_text(ctx.sign_end_ts), ports._ts_text(ctx.state["deadline"])))
    ports._retry_event(kind="window", retry_deadline=int(ctx.state["deadline"]),
                       sign_end=int(ctx.sign_end_ts or 0))


def run_signup(args, ports):
    """跑完单场自动报名全流程并返回进程退出码（0 成功/已报，2 失败/未确认，3 时钟/登录）。"""
    clock, entry_epoch, err_code = _init_entry_clock(ports)
    if err_code is not None:
        return err_code
    retry_for = args.retry_for if args.retry_for is not None else args.window
    sign_end_ts, at_ts, err_code = _parse_entry_times(args, ports)
    if err_code is not None:
        return err_code
    frozen = ports._known_policy_start(args)
    if frozen is None and at_ts is not None:
        frozen = ports.retry_anchor(at_ts, entry_epoch)
    ctx = SimpleNamespace(
        args=args,
        ports=ports,
        clock=clock,
        entry_epoch=entry_epoch,
        retry_for=retry_for,
        sign_end_ts=sign_end_ts,
        at_ts=at_ts,
        frozen=frozen,
        preflight_only=(frozen is None),
        display=getattr(args, "name", "") or "这一场活动",
        state=new_signup_state(),
        done={"value": False},
        stop_reason_logged="",
        budget=None,
        relogin_wait_s=max(0.0, float(getattr(args, "relogin_wait", 0) or 0)),
        target=None,
        start=0.0,
        instant_mode=False,
    )
    ctx.wait_for_relogin = lambda where: wait_for_relogin(ctx, where)
    for step in (_build_initial_budget, _check_auth_and_clock_sample, _resolve_and_announce_window):
        code = step(ctx)
        if code is not None:
            return code
    try:
        return run_browser_phase(ctx)
    except ports.ClockUnavailable:
        return clock_stop(ctx)
    except ports.BudgetExhausted:
        return terminal(
            ctx, "sign_end" if ctx.state["binding"] == "sign_end" else "retry_duration")
    except Exception as exc:  # noqa: BLE001 - 浏览器/管道异常也要有唯一终态
        ctx.state["last_reason"] = "运行异常：%s" % type(exc).__name__
        return terminal(ctx, "process_error")
