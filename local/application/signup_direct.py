# -*- coding: utf-8 -*-
"""报名 worker 的直发通道：路径选择与 kind=path 事件、单向退回点击、版本不兼容重取密钥、现算签名发一笔、开放前预检。

从 grab.py 的 cmd_grab 搬出：运行时密钥只绑进签名函数的 functools.partial，
不另存为属性、不写日志、不落盘；预检不占调度账本次数与在途名额。

@author Author
"""
from __future__ import annotations

import functools
import queue

from application.signup_ledger import apply_conclusion, sync_pending
from domain.signup_reply import classify_signup_reply


def new_direct_state(ports) -> dict:
    """直发（主）+ 点击（单向兜底）同一调度账本的直发通道状态字典。"""
    return {
        "enabled": False,
        "downgrade": False,
        "protocol_stop": False,   # 通道/协议异常：停止新发，统一收尾
        "signer": None,
        "build": None,            # 原始签名函数：重取密钥后重新绑定
        "need_rekey": False,      # 收到「版本不兼容」：下一笔前重取一次密钥
        "rekeyed": False,         # 本场已重取过：再不兼容就退回点击
        "transport": None,
        "run_id": ports.os.urandom(8).hex(),
        "seq": 0,
        "ticket_to_bid": {},
        # 本场票据登记表（F03）：request_id -> run_id/attempt_no/生命周期。
        # 预留、started、lost、settled、cancelled 显式记账，不拿整数猜来源。
        "registry": {},
        "reserved": 0,   # 已提交未 started：预留名额与次数配额
        "queue": None,
    }


def downgrade_to_click(ctx, reason):
    """本场单向切到点击兜底；写一行日志并上报路径事件（决策 015：退回点击必须可见）。"""
    if ctx.direct["downgrade"]:
        return
    ctx.direct["downgrade"] = True
    ctx.ports.log("[!] 本场切换为点击兜底（原因：%s）" % reason)
    ctx.ports._retry_event(kind="path", path="click", path_reason=reason)


def rekey_after_version(ctx):
    """收到「版本不兼容」后重取一次运行时密钥（决策 015）；取不到就退回点击。

    预检与正式提交共用。重取过一次就记 rekeyed：之后再不兼容由
    apply_conclusion 直接退回点击。
    """
    direct = ctx.direct
    ports = ctx.ports
    direct["need_rekey"] = False
    new_key, rekey_reason = ports.fetch_runtime_key(ctx.budget)
    if new_key is None:
        downgrade_to_click(ctx, "版本不兼容且重取运行时密钥失败（%s）" % rekey_reason)
    else:
        direct["signer"] = functools.partial(direct["build"], key=new_key)
        direct["rekeyed"] = True
        ports.log("[i] 版本不兼容：已重取运行时密钥，继续直发")
    new_key = None


def rekey_after_relogin(ctx):
    """重新登录后重取运行时密钥；取不到就退回点击。"""
    direct = ctx.direct
    ports = ctx.ports
    if direct["enabled"] and not direct["downgrade"]:
        new_key, rekey_reason = ports.fetch_runtime_key(ctx.budget)
        if new_key is None:
            downgrade_to_click(ctx, "重新登录后取不到运行时密钥（%s）" % rekey_reason)
        else:
            direct["signer"] = functools.partial(direct["build"], key=new_key)
        new_key = None


def setup_direct_path(ctx, runtime_key, key_reason):
    """拿到运行时密钥后延迟加载签名与传输模块、绑定签名函数并上报 kind=path 事件。"""
    ports = ctx.ports
    direct = ctx.direct
    path_reason = ""
    if runtime_key is not None:
        build_signup_hash, direct_transport_cls = ports.load_direct_modules()
        if build_signup_hash is not None and direct_transport_cls is not None:
            # 密钥只绑进签名函数，不另存、不打印
            direct["build"] = build_signup_hash
            direct["signer"] = functools.partial(build_signup_hash, key=runtime_key)
            direct["queue"] = queue.Queue()
            direct["transport"] = direct_transport_cls(direct["queue"])
            direct["enabled"] = True
        else:
            path_reason = "直发模块不可用"
    else:
        path_reason = "取不到运行时密钥（%s）" % key_reason
    runtime_key = None     # 之后只经 direct["signer"] 使用
    if direct["enabled"]:
        ports.log("[i] 报名路径：直发（运行时密钥）")
        ports._retry_event(kind="path", path="direct", path_reason="")
    else:
        ports.log("[i] 报名路径：点击（原因：%s）" % path_reason)
        ports._retry_event(kind="path", path="click", path_reason=path_reason)


def _submit_direct_ticket(ctx, captured_token, sig, remaining):
    """构造直发票据、登记预留并交由 transport.try_submit 发送。"""
    ports = ctx.ports
    direct = ctx.direct
    mono_now = ports.time.monotonic()
    direct["seq"] += 1
    req_id = "%s-%d" % (direct["run_id"], direct["seq"])
    url = ports.API + "/rjyHdCyr/signUp/" + sig
    ticket = {
        "run_id": direct["run_id"],
        "request_id": req_id,
        "attempt_no": ctx.burst.attempts + direct["reserved"] + 1,
        "url": url,
        "headers": ports._direct_headers(captured_token),
        # dispatch 只管最晚启动；request_deadline 是网络预算截止，
        # timeout_s 为本笔捕获的预算，线程不得延长它们。
        "dispatch_deadline": mono_now + min(ports.INFLIGHT_WAIT_S, remaining),
        "request_deadline": mono_now + remaining,
        "timeout_s": min(8.0, remaining),
    }
    # try_submit 之前登记 reservation；拒绝时释放该条（F03/F04）
    direct["registry"][req_id] = {
        "run_id": direct["run_id"],
        "attempt_no": ticket["attempt_no"],
        "state": "reserved",
        "bid": None,
    }
    direct["reserved"] += 1
    if not direct["transport"].try_submit(ticket):
        direct["reserved"] -= 1
        direct["registry"].pop(req_id, None)
        return "busy"
    return "fired"


def try_direct_fire(ctx):
    """现算签名并直发一笔：时间取自 business clock（ClockUnavailable 停发射，不用 time.time）。

    签名失败/try_submit 拒绝不计次数；返回 "fired"/"busy"/"downgrade"/"stop"。
    token 只取本场内存：缺失不建 ticket、不转 click，安全停发（F01）。
    """
    ports = ctx.ports
    direct = ctx.direct
    if direct["transport"] is None or direct["signer"] is None:
        downgrade_to_click(ctx, "直发模块不可用")
        return "downgrade"
    try:
        captured_token = ports.token()
    except Exception:
        captured_token = ""
    if not captured_token:
        direct["protocol_stop"] = True
        ctx.state["last_reason"] = "token 缺失，停止发送"
        ports.log("[!] token 缺失：停止发送")
        return "stop"
    epoch_ms = int(ports.business_now() * 1000)
    try:
        sig = direct["signer"](str(ctx.target["id"]), epoch_ms)
    except Exception as exc:  # noqa: BLE001 - 签名失败不提交，改走点击
        downgrade_to_click(ctx, "签名失败：%s" % type(exc).__name__)
        return "downgrade"
    # 签名耗时后重新过预算闸门（F02）：remaining 已含 sign_end 硬截
    remaining = ctx.budget.remaining_s()
    if remaining <= 0:
        return "busy"
    return _submit_direct_ticket(ctx, captured_token, sig, remaining)


def _wait_precheck_reply(ctx, req_id):
    """在 PRECHECK_WAIT_S 内等待预检票据的完成事件并解码回包。"""
    ports = ctx.ports
    direct = ctx.direct
    give_up = ports.time.monotonic() + ports.PRECHECK_WAIT_S
    while ports.time.monotonic() < give_up:
        try:
            ev = direct["queue"].get_nowait()
        except queue.Empty:
            ports.time.sleep(0.02)
            continue
        if ev.get("request_id") != req_id:
            continue
        kind = ev.get("kind")
        if kind == "completed":
            if ev.get("http_status") != 200:
                ports.log("[!] 预检回了 HTTP %s，没有业务回包" % (ev.get("http_status"),))
                return None
            return ports._decode_body(ev.get("body_bytes"))
        if kind in ("failed", "not_started"):
            return None
    return None


def precheck_send(ctx, round_no):
    """发一笔预检 signUp：返回学校回包的 dict，没拿到业务回包返回 None。

    不登记进调度账本（不占 attempts、不占在途名额）。此时本场还没有别的
    直发票据，事件队列里只会有这一笔的事件，直接在这里收。
    """
    ports = ctx.ports
    direct = ctx.direct
    if direct["transport"] is None or direct["signer"] is None:
        return None
    try:
        tok = ports.token()
    except Exception:  # noqa: BLE001 - 读不到登录态只跳过预检
        tok = ""
    if not tok:
        ports.log("[!] 预检跳过：登录态里没有 token")
        return None
    epoch_ms = int(ports.business_now() * 1000)
    try:
        sig = direct["signer"](str(ctx.target["id"]), epoch_ms)
    except Exception as exc:  # noqa: BLE001 - 签名失败不提交，改走点击
        downgrade_to_click(ctx, "签名失败：%s" % type(exc).__name__)
        return None
    remaining = ctx.budget.remaining_s()
    if remaining <= 0:
        return None
    mono_now = ports.time.monotonic()
    req_id = "%s-pre%d" % (direct["run_id"], round_no)
    ticket = {
        "run_id": direct["run_id"],
        "request_id": req_id,
        "attempt_no": 0,          # 不占正式提交的序号
        "url": ports.API + "/rjyHdCyr/signUp/" + sig,
        "headers": ports._direct_headers(tok),
        "dispatch_deadline": mono_now + min(ports.INFLIGHT_WAIT_S, remaining),
        "request_deadline": mono_now + remaining,
        "timeout_s": min(8.0, remaining),
    }
    if not direct["transport"].try_submit(ticket):
        return None
    return _wait_precheck_reply(ctx, req_id)


def precheck_before_open(ctx, now_entry):
    """开抢前预检（设计 3.1 / S1）：开放前约 45 秒直发一次 signUp，最多 2 次请求。

    只为提前发现密钥或格式不对：学校回「报名未开始」说明两样都对，这一笔
    不会写入。预检不进调度账本，所以开抢前的「报名未开始」天然不计次。
    只对未来场次做：已开放、直发没启用或已降级、进场时距开放不足
    PRECHECK_MIN_LEAD_S 秒的都跳过。
    """
    ports = ctx.ports
    direct = ctx.direct
    if (not direct["enabled"] or direct["downgrade"] or ctx.instant_mode
            or ctx.at_ts - now_entry < ports.PRECHECK_MIN_LEAD_S):
        return
    ports.wait_until(ctx.at_ts - ports.PRECHECK_AHEAD_S, ctx.budget)
    for round_no in (1, 2):
        payload = precheck_send(ctx, round_no)
        if payload is None:
            if not direct["downgrade"]:
                ports.log("[!] 预检没有拿到学校回包：不影响正式提交，到点照常发")
            return
        reply = classify_signup_reply(payload.get("code"),
                                      str(payload.get("message") or ""))
        if reply.kind == "not_open":
            ports.log("[i] 预检通过：学校回「报名未开始」，密钥和格式都对（%s）" % reply.raw)
            return
        ports.log("[i] 预检回包：%s｜%s" % (reply.label, reply.raw))
        apply_conclusion(ctx, payload, downgrade_to_click)
        if reply.kind == "success":
            # 学校提前开放而真的报上：记成一笔真实提交，主循环一进来就收口
            bid = ctx.burst.register_request()
            ctx.burst.settle(bid, "real", http_status=200)
            sync_pending(ctx)
            ports._retry_event(kind="submit", attempts=ctx.state["attempts"],
                               request_id=bid, phase=ctx.burst.phase)
            return
        if reply.kind == "version" and direct["need_rekey"] and round_no == 1:
            rekey_after_version(ctx)
            if direct["downgrade"]:
                return
            continue        # 重取密钥成功：再预检一次
        return
