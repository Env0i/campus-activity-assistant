# -*- coding: utf-8 -*-
"""报名 worker 的唯一终态、停止原因结论、通知、退出码与收口辅助。

从 grab.py 的 cmd_grab 搬出：done 结构化行、每种停止原因给人读的结论、
飞书通知、退出码映射，以及校时中途失效与预算到点两个收口函数。
REPLY_STOP_HINTS 与 SubmitAborted 也在此定义，由 grab.py 保留同名引用。

@author Author
"""
from __future__ import annotations

from domain.signup_reply import stop_reason_label

# 学校明确拒绝类终态的第二行提示（决策 015）；短结论统一来自 domain.signup_reply
REPLY_STOP_HINTS = {
    "full": "学校说名额已满，再提交也不会变，本场已停止。",
    "closed": "报名窗口已经关闭。",
    "conflict": "这场和你已报名的活动时间冲突，核对后确认没报上。",
    "no_activity": "学校查不到这个活动，可能已删除或改期；刷新活动列表后再看。",
    "clock_skew": "学校连续说请求已超时，本机北京时间可能不准；校时后再试。",
    "unknown_reply": "学校连续回了同一条无法识别的结果，已停止；完整原文见运行记录。",
    "page_unavailable": "直发不可用、学校详情页又打不开，本场没法提交；稍后手动打开活动页再试。",
}


class SubmitAborted(RuntimeError):
    """确认前的本地拦截：条件已不满足，绝不点「确定」。"""


def _emit_done_line(ctx):
    """写唯一一条 [retry] kind=done 结构化终态行，last_reason 恒在行末。"""
    ports = ctx.ports
    state = ctx.state
    ports.log("[retry] kind=done attempts=%d stop_reason=%s retry_deadline=%d sign_end=%d "
              "pending=%d streak_404=%d phase=%s last_reason=%s"
              % (state["attempts"], ctx.stop_reason_logged, int(state["deadline"]),
                 int(ctx.sign_end_ts or 0),
                 state.get("pending", 0), state.get("streak_404", 0),
                 state.get("phase", ""), (state["last_reason"] or "")[:40]))


def _report_success_or_auth(ctx, stop_reason):
    """处理成功、已报名、登录失效与鉴权无法确认四类终态；未命中返回 None。"""
    ports = ctx.ports
    state = ctx.state
    attempts, last = state["attempts"], state["last_reason"]
    if stop_reason == "success":
        ports.log("[OK] 报名成功（尝试 %d 次）" % attempts)
        print("\n[OK] 报名成功：%s" % ctx.display)
        print("     不想去请尽快在活动页取消，别占名额。")
        ports.notify("报名成功", [
            "**%s**" % ctx.display,
            "报名时间：%s" % ports.school_time_text(now_fn=ports.business_now),
            "如不想参加，请尽快在活动页取消。",
        ])
        return 0
    if stop_reason == "already_signed":
        print("[i] 你已经报过这个活动了。")
        return 0
    if stop_reason == "login_invalid":
        ports.log("[X] 登录失效（尝试 %d 次）" % attempts)
        print("\n[X] 登录失效：%s" % (last or "学校要求重新登录"))
        print("    重试没有意义，请先重新登录再跑。")
        return 3
    if stop_reason == "auth_unavailable":
        # 网络/接口无法确认 ≠ 登录失效：不指导用户重登
        ports.log("[X] 登录状态暂时无法确认（%s）" % (last or "接口没有应答"))
        print("\n[X] 登录状态暂时无法确认：%s" % (last or "接口没有应答"))
        print("    先检查网络或校园网，再点「刷新」重试；不要急着重新登录。")
        return 3
    return None


def _report_stop_or_failure(ctx, stop_reason):
    """处理次数上限、未确认、时钟不可用、学校明确拒绝、流程异常与默认超时终态。"""
    ports = ctx.ports
    state = ctx.state
    attempts, last = state["attempts"], state["last_reason"]
    if stop_reason == "max_attempts":
        ports.log("[X] 达到最大提交次数 %d（最近原因 %s）" % (attempts, last))
        print("\n[X] 已提交 %d 次仍没成功：%s" % (attempts, last or "名额已满"))
        print("    到达你设置的最大提交次数，停止重试。")
        return 2
    if stop_reason == "unconfirmed":
        # 已发出的请求撤不回来：不能声称没抢到，也不能声称成功
        ports.log("[X] 结果未确认（已发起 %d 次提交，仍有 %d 次没有确定结果）"
                  % (attempts, state["pending"]))
        print("\n[?] 结果未确认：提交已经发出，但没有拿到学校的确定结果。")
        print("    请打开活动页核对是否已报名；不要直接重复提交。")
        ports.notify("报名结果未确认", [
            "**%s**" % ctx.display,
            "提交已发出但结果未确认，请到活动页核对。",
        ], "orange")
        return 2
    if stop_reason == "clock_unavailable":
        ports.log("[X] 北京时间暂不可用，已停止自动动作（尝试 %d 次）" % attempts)
        print("\n[X] 暂时无法获取可信北京时间，已停止自动报名动作。")
        print("    已发出的提交不受影响，请到活动页核对；不要直接重复提交。")
        return 3
    if stop_reason in REPLY_STOP_HINTS:
        # 学校已明确拒绝或回包无法识别：再提交也不会变，本场结束（决策 015）
        label = stop_reason_label(stop_reason)
        ports.log("[X] 本场结束：%s（尝试 %d 次）" % (label, attempts))
        print("\n[X] 没报上：%s" % label)
        print("    " + REPLY_STOP_HINTS[stop_reason])
        ports.notify("自动报名结束", ["**%s**" % ctx.display, "原因：%s" % label], "orange")
        return 2
    if stop_reason == "process_error":
        ports.log("[X] 本机流程异常结束（%s）" % (last or "未知异常"))
        print("\n[X] 本机流程异常结束：%s" % (last or "未知异常"))
        print("    这不代表学校拒绝了报名；请到活动页核对后再决定。")
        return 2
    ports.log("[X] 报名失败（尝试 %d 次，最近原因 %s）"
              % (attempts, last or "名额已满/未开放"))
    tail_note = "报名已截止" if stop_reason == "sign_end" else "重试时长到了"
    print("\n[X] 没抢到：%s（%s）" % (last or "名额已满／页面未放开", tail_note))
    print("    建议手动打开活动页确认，必要时再试一次。")
    ports.notify("自动报名失败", [
        "**%s**" % ctx.display,
        "原因：%s（%s）" % (last or "名额已满/未开放", tail_note),
        "建议手动确认。",
    ], "orange")
    return 2


def terminal(ctx, stop_reason):
    """唯一结构化终态：恰一条 [retry] kind=done，随后给人读结论与退出码。"""
    if ctx.done["value"]:
        return 2
    ctx.done["value"] = True
    ctx.stop_reason_logged = stop_reason
    _emit_done_line(ctx)
    code = _report_success_or_auth(ctx, stop_reason)
    if code is not None:
        return code
    return _report_stop_or_failure(ctx, stop_reason)


def clock_stop(ctx):
    """校时在流程中途失效：已发出的未决请求保留为「未确认」。

    零提交才是 clock_unavailable；有 pending 时不能声称没抢到，
    也不能把校时失败说成学校拒绝。
    """
    ctx.state["last_reason"] = "北京时间暂不可用"
    if ctx.state["pending"] > 0:
        return terminal(ctx, "unconfirmed")
    return terminal(ctx, "clock_unavailable")


def budget_stop(ctx, phase):
    """阶段耗时撞上重试窗口截止时，按起约束的边界收口。"""
    ctx.state["last_reason"] = "%s时重试窗口已到点" % phase
    return terminal(
        ctx, "sign_end" if ctx.state["binding"] == "sign_end" else "retry_duration")
