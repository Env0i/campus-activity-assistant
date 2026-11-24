# -*- coding: utf-8 -*-
"""报名 worker 的同一调度账本：状态初值、回包结论、页面与直发结算、事件泵、在途同步与扩窗。

从 grab.py 的 cmd_grab 搬出：click 与直发两条通道共用同一份 state 与 BurstPolicy，
按回包分类表下结论、结算页面 Request/Response/requestfailed 与直发传输事件，
以及在自适应扩窗时同步重建 RetryBudget 并发出 window_extended 事件。

@author Author
"""
from __future__ import annotations

import queue

from domain.signup.signup_reply import (
    STALE_TS_LIMIT,
    TERMINAL_STOP_REASONS,
    UNKNOWN_REPLY_LIMIT,
    classify_signup_reply,
)


def new_signup_state() -> dict:
    """单场报名的已观察事实初值。"""
    return {
        "attempts": 0,
        "pending": 0,
        "last_reason": "",
        "resp_ok": False,
        "login_invalid": False,
        "deadline": 0.0,
        "binding": "",
        # 回包分类（决策 015）：一出现就结束本场的原因、未识别回包与超时回包的连续计数
        "terminal_reason": "",
        "unknown_raw": "",
        "unknown_count": 0,
        "stale_count": 0,
        # 过了预期开放 OPEN_GRACE_S 秒学校仍说「报名未开始」：整场只写一行日志
        "not_open_logged": False,
        # 提交中收到 4001：先停发、等在途落定再复查，确认失效才记 login_invalid
        "login_suspect": False,
    }


def sync_pending(ctx):
    """把 BurstPolicy 的在途、次数、连击与阶段同步到 state。"""
    state = ctx.state
    burst = ctx.burst
    state["pending"] = burst.pending_count()
    state["attempts"] = burst.attempts
    state["streak_404"] = burst.streak_404
    state["phase"] = burst.phase


def sync_budget_window(ctx):
    """扩窗同步（F05）：policy 截止变大时重建 RetryBudget 并广播事件。

    纯 404 与 429 连击都会经 burst.settle→_maybe_extend_window 拉长
    effective_deadline；这里统一把预算与事件对齐，sign_end 仍硬截。
    """
    ports = ctx.ports
    burst = ctx.burst
    if (burst is not None
            and burst.effective_deadline > getattr(ctx.budget, "deadline_epoch", 0)):
        ctx.budget = ports.RetryBudget(burst.effective_deadline, business_clock=ctx.clock)
        ctx.state["deadline"] = burst.effective_deadline
        ports._retry_event(kind="window_extended",
                           retry_deadline=int(burst.effective_deadline),
                           sign_end=int(ctx.sign_end_ts or 0))


def _handle_reply_kind(ctx, reply, downgrade_fn):
    """按回包分类更新 state / direct 状态（从 _apply_conclusion 拆出以保持函数短小）。"""
    ports = ctx.ports
    state = ctx.state
    direct = ctx.direct
    kind = reply.kind
    if kind == "success":
        # 成功结论粘性：只要有一笔 code=1 就是成功，后续失败响应不改写
        state["resp_ok"] = True
    elif kind == "login_invalid":
        # 只认 code=4001：业务文案里的「登录/身份验证」字眼不作数（避免误判）。
        # 先记待确认：停发、等在途落定后由主循环复查一次（决策 015）
        if not state["login_invalid"]:
            state["login_suspect"] = True
            ports.log("[!] 提交中收到 4001（%s），停发并复查登录" % reply.raw)
    elif kind == "no_activity" and direct["enabled"] and not direct["downgrade"]:
        # hd-info 空值成因未证实（活动不存在 / 少了页面自己的前置请求等）：
        # 直发时先退回点击，让学校页面自己走一遍核实；点击上也这样才判活动不存在
        downgrade_fn(ctx, "学校查不到活动信息（hd-info 空值），改走点击核实")
    elif kind in TERMINAL_STOP_REASONS:
        # 时间冲突也先记成终态：收尾的 getJoinInfo 核对确认已报名时改判成功
        if not state["terminal_reason"]:
            state["terminal_reason"] = TERMINAL_STOP_REASONS[kind]
    elif kind == "version":
        # 直发时先重取一次运行时密钥（下一笔前由主循环做）；重取过还不兼容就退回点击
        if direct["enabled"] and not direct["downgrade"]:
            if direct["rekeyed"]:
                downgrade_fn(ctx, "重取运行时密钥后仍版本不兼容")
            else:
                direct["need_rekey"] = True
    elif kind == "stale_ts":
        state["stale_count"] += 1
        if state["stale_count"] >= STALE_TS_LIMIT and not state["terminal_reason"]:
            state["terminal_reason"] = "clock_skew"
    elif kind == "unknown":
        _handle_unknown_reply(ctx, reply, downgrade_fn)
    elif kind == "not_open":
        _handle_not_open_reply(ctx, reply)


def _handle_unknown_reply(ctx, reply, downgrade_fn):
    """同一未识别回包连续达上限时：直发先退回点击，点击上再出现才结束。"""
    state = ctx.state
    direct = ctx.direct
    if reply.raw == state["unknown_raw"]:
        state["unknown_count"] += 1
    else:
        state["unknown_raw"], state["unknown_count"] = reply.raw, 1
    if state["unknown_count"] >= UNKNOWN_REPLY_LIMIT:
        if direct["enabled"] and not direct["downgrade"]:
            # 降级后重新计数：点击路径上同一文案再连续出现才结束
            state["unknown_count"] = 0
            downgrade_fn(ctx, "同一未识别回包连续 %d 次：%s"
                         % (UNKNOWN_REPLY_LIMIT, reply.raw))
        elif not state["terminal_reason"]:
            state["terminal_reason"] = "unknown_reply"


def _handle_not_open_reply(ctx, reply):
    """学校还没开放，照常按节奏继续；过了预期开放 OPEN_GRACE_S 秒仍这样，只提示一次。"""
    ports = ctx.ports
    state = ctx.state
    if not state["not_open_logged"]:
        try:
            late_s = ports.business_now() - ctx.at_ts
        except ports.ClockUnavailable:
            late_s = 0.0
        if late_s >= ports.OPEN_GRACE_S:
            state["not_open_logged"] = True
            ports.log("[i] 学校还没开门：已过预期开放 %d 秒仍回「报名未开始」，"
                      "按全速节奏继续（%s）" % (int(late_s), reply.raw))


def apply_conclusion(ctx, payload, downgrade_fn):
    """对一笔 real 应答的 body 按回包分类表下结论（决策 015），返回学校原文。

    click 与直发共用同一套分类，避免两条通道判据漂移。
    last_reason 只存给界面的短结论，学校原文由调用方写进日志，不截断。
    """
    state = ctx.state
    code = payload.get("code") if isinstance(payload, dict) else None
    message = ""
    if isinstance(payload, dict):
        message = str(payload.get("message") or "")
    reply = classify_signup_reply(code, message)
    state["last_reason"] = reply.label
    if reply.kind != "stale_ts":
        state["stale_count"] = 0
    if reply.kind != "unknown":
        state["unknown_raw"], state["unknown_count"] = "", 0
    _handle_reply_kind(ctx, reply, downgrade_fn)
    return reply.raw


def reason_with_raw(ctx, reply_raw):
    """日志用：短结论后面附学校原文（完整、不截断）；没有业务回包时只给短结论。"""
    if reply_raw:
        return "%s｜%s" % (ctx.state["last_reason"], reply_raw)
    return ctx.state["last_reason"]


def settle_one(ctx, response, downgrade_fn):
    """按 request_id 结算一笔在途响应；乱序合法，别家响应不改本场结论。

    不以「唯一 pending」认领未知响应（F05）：身份关联只走
    已接纳 Request 引用，避免把 direct 未决记到别人头上。
    """
    ports = ctx.ports
    state = ctx.state
    burst = ctx.burst
    if burst is None:
        return
    resp_request = getattr(response, "request", None)
    bid = ctx.request_to_bid.get(id(resp_request)) if resp_request is not None else None
    if bid is None:
        state["last_reason"] = "收到其他请求的响应，本场结论未变"
        return
    raw_kind = ports._classify_response(response)
    http_status = getattr(response, "status", None)
    try:
        http_status = int(http_status) if http_status is not None else None
    except (TypeError, ValueError):
        http_status = None
    payload = None
    reply_raw = ""
    if raw_kind == "real":
        # 已得 HTTP 应答按 real 结算：200+HTML（学校错误页）不伪装
        # lost；仅响应体完全读不出才降为 lost（保持未决，不假造结论）。
        try:
            raw = response.body()
        except Exception:
            raw_kind = "lost"
        else:
            payload = ports._decode_body(raw)
    burst.settle(bid, raw_kind, http_status=http_status)
    sync_budget_window(ctx)
    if raw_kind == "lost":
        state["last_reason"] = "响应读取失败，请求仍未决"
    elif raw_kind == "404":
        state["last_reason"] = "404 接口未就绪/限流"
        ports._retry_event(kind="not_ready", request_id=bid,
                           streak_404=burst.streak_404, phase=burst.phase,
                           retry_deadline=int(burst.effective_deadline))
    elif raw_kind == "throttled":
        state["last_reason"] = "429 限流"
        ports._retry_event(kind="throttled", request_id=bid,
                           streak_404=burst.streak_404, phase=burst.phase,
                           retry_deadline=int(burst.effective_deadline))
    elif raw_kind == "server_error":
        state["last_reason"] = "5xx 服务端异常"
        ports._retry_event(kind="server_error", request_id=bid,
                           http_status=http_status, phase=burst.phase)
    else:
        reply_raw = apply_conclusion(ctx, payload, downgrade_fn)
    sync_pending(ctx)
    ports.log("[i] 第 %d 次提交：%s" % (state["attempts"], reason_with_raw(ctx, reply_raw)))


def settle_failed(ctx, request):
    """requestfailed：按既有 request_id 结算为 lost，立即释放名额。

    不以「唯一 pending」认领未登记 Request（F05）。
    """
    if ctx.burst is None:
        return
    bid = ctx.request_to_bid.get(id(request))
    if bid is None:
        return
    ctx.burst.settle(bid, "lost")
    ctx.state["last_reason"] = "请求中止（requestfailed），仍未决"
    sync_pending(ctx)


def register_request(ctx, request):
    """主循环一次登记实际 Request 身份（F05 回调只入队）。"""
    ports = ctx.ports
    ident = id(request)
    if ident in ctx.admitted_ids:
        return
    ctx.admitted_ids.add(ident)
    ctx.admitted_all.append(request)
    bid = ctx.burst.register_request()
    ctx.request_to_bid[ident] = bid
    sync_pending(ctx)
    ctx.state["last_reason"] = "已发起，等响应"
    # 请求发起即上报，不等响应回来才让界面知道已提交
    ports.log("[i] 第 %d 次提交：已发起" % ctx.state["attempts"])
    ports._retry_event(kind="submit", attempts=ctx.state["attempts"],
                       request_id=bid, phase=ctx.burst.phase)


def _settle_direct_started(ctx, req_id, reg):
    """直发 started 事件：仅一次登记进调度账本。"""
    ports = ctx.ports
    direct = ctx.direct
    if reg["state"] != "reserved":
        return
    reg["state"] = "started"
    if direct["reserved"] > 0:
        direct["reserved"] -= 1
    bid = ctx.burst.register_request()
    reg["bid"] = bid
    direct["ticket_to_bid"][req_id] = bid
    sync_pending(ctx)
    ctx.state["last_reason"] = "直发已发起"
    ports.log("[i] 第 %d 次提交：直发已发起" % ctx.state["attempts"])
    ports._retry_event(kind="submit", attempts=ctx.state["attempts"],
                       request_id=bid, phase=ctx.burst.phase)


def _settle_direct_completed(ctx, ev, reg, bid, downgrade_fn):
    """直发 completed 事件：五档分类、协议异常检查与业务结论结算。"""
    ports = ctx.ports
    state = ctx.state
    direct = ctx.direct
    burst = ctx.burst
    if reg["state"] == "settled":
        return  # 已决不改写
    http_status = ev.get("http_status")
    body = ev.get("body_bytes")
    raw_kind = "real"
    if http_status == 404:
        raw_kind = "404"
    elif http_status == 429:
        raw_kind = "throttled"
    elif isinstance(http_status, int) and http_status >= 500:
        raw_kind = "server_error"
    payload = ports._decode_body(body) if raw_kind == "real" else None
    reply_raw = ""
    if burst.settle(bid, raw_kind, http_status=http_status) is None:
        return  # 重复结算被拒：结论/扩窗/降级副作用一并拒绝
    sync_budget_window(ctx)
    # 通道/协议异常（F01 返修）：非 200/404/429/5xx 的 HTTP，或 200 解码后无可识别业务 code
    anomaly = None
    if raw_kind == "real":
        has_code = isinstance(payload, dict) and ports._recognizable_code(payload.get("code"))
        if http_status != 200:
            anomaly = "通道/协议异常 HTTP %s，停止新发" % (http_status,)
        elif not has_code:
            anomaly = "通道/协议异常：200 无业务 code，停止新发"
    reg["state"] = "settled"
    if anomaly is not None:
        direct["protocol_stop"] = True
        state["last_reason"] = anomaly
        ports.log("[!] " + anomaly)
    elif raw_kind == "404":
        state["last_reason"] = "404 接口未就绪/限流"
        ports._retry_event(kind="not_ready", request_id=bid,
                           streak_404=burst.streak_404, phase=burst.phase,
                           retry_deadline=int(burst.effective_deadline))
    elif raw_kind == "throttled":
        state["last_reason"] = "429 限流"
        ports._retry_event(kind="throttled", request_id=bid,
                           streak_404=burst.streak_404, phase=burst.phase,
                           retry_deadline=int(burst.effective_deadline))
    elif raw_kind == "server_error":
        state["last_reason"] = "5xx 服务端异常"
        ports._retry_event(kind="server_error", request_id=bid,
                           http_status=http_status, phase=burst.phase)
    else:
        reply_raw = apply_conclusion(ctx, payload, downgrade_fn)
    sync_pending(ctx)
    ports.log("[i] 第 %d 次提交：%s" % (state["attempts"], reason_with_raw(ctx, reply_raw)))


def settle_direct_event(ctx, ev, downgrade_fn):
    """把一笔直发传输事件并入同一调度账本（started 登记 / completed 五档 / failed 保持未决）。

    F03：先核对本场 run_id、已登记 request_id 与票据 attempt_no；
    任何未知/跨场/不匹配事件无副作用——不释放他人预留、不改 policy/last_reason、不套业务结论。
    """
    direct = ctx.direct
    kind = ev.get("kind")
    req_id = ev.get("request_id")
    reg = direct["registry"].get(req_id)
    if (reg is None or ev.get("run_id") != direct["run_id"]
            or ev.get("attempt_no") != reg["attempt_no"]):
        return      # 跨场 / 未知 / 身份不匹配：无副作用
    if kind == "started":
        _settle_direct_started(ctx, req_id, reg)
        return
    if kind == "not_started":
        # 只释放仍预留的本条；重复、started 后的 not_started 无副作用
        if reg["state"] == "reserved":
            reg["state"] = "cancelled"
            if direct["reserved"] > 0:
                direct["reserved"] -= 1
        return
    bid = reg["bid"]
    if bid is None:
        return      # 未跨接纳点的票据没有可结算身份
    if kind == "failed":
        if reg["state"] != "started":
            return  # 已决 / lost 后重复 failed：无副作用
        # lost 保持 pending（不假造结论），同一合法请求仍可在尾窗内被迟到的确定应答结算
        if ctx.burst.settle(bid, "lost") is None:
            return
        reg["state"] = "lost"
        sync_budget_window(ctx)
        ctx.state["last_reason"] = "直发网络失败，仍未决"
        sync_pending(ctx)
        return
    if kind == "completed":
        _settle_direct_completed(ctx, ev, reg, bid, downgrade_fn)


def drain_direct(ctx, downgrade_fn):
    """抽干直发队列里的事件并逐笔结算。"""
    if ctx.burst is None or ctx.direct["queue"] is None:
        return
    q = ctx.direct["queue"]
    while True:
        try:
            ev = q.get_nowait()
        except queue.Empty:
            break
        settle_direct_event(ctx, ev, downgrade_fn)


def settle_pending(ctx, downgrade_fn):
    """直发通道与页面通道共用的事件泵；尾窗冻结后不再接纳新事件。"""
    if ctx.finalize_state["frozen"]:
        return        # 尾窗后冻结响应接纳：不再 drain 新事件
    drain_direct(ctx, downgrade_fn)     # 直发通道与页面通道同一事件泵
    while ctx.response_queue:
        item = ctx.response_queue.pop(0)
        if isinstance(item, tuple) and item and item[0] == "request":
            register_request(ctx, item[1])
        elif isinstance(item, tuple) and item and item[0] == "failed":
            settle_failed(ctx, item[1])
        else:
            settle_one(ctx, item, downgrade_fn)
    sync_pending(ctx)
