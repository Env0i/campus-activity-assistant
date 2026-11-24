# -*- coding: utf-8 -*-
"""取消报名用例编排：前置核对四条、单次取消请求、getJoinInfo 复查。

从 grab.py 的 run_cancel 搬出（决策 016）：所有外部依赖均由 grab.run_cancel
在每次调用时从模块当前全局组装后传入，本模块不 import grab，也不持有全局状态。

@author Author
"""
from __future__ import annotations

import json
import urllib.parse


def _refuse(log, reason):
    log("[cancel] 前置核对未通过：%s（未调取消接口）" % reason)
    return {"ok": False, "kind": "precheck_failed", "reason": reason}


def _check_auth_and_clock(act_id, *, site_configured, probe_token, business_now,
                          has_clock_meta, clock_unavailable, log):
    """核对站点、参数、登录态与业务北京时间；不通过返回拒绝结果，通过返回 None。"""
    if not site_configured:
        return _refuse(log, "site_unconfigured")
    if not act_id:
        return _refuse(log, "not_in_list")
    # 1 登录：只有学校明确说失效才算 login_expired；网络不通是「查不到」，不能诱导重登
    state, _detail = probe_token()
    if state in ("expired", "none"):
        return _refuse(log, "login_expired")
    if state != "valid":
        return _refuse(log, "unknown_state")
    # 2 业务北京时间
    try:
        business_now()
        if not has_clock_meta():
            raise clock_unavailable("业务时钟未配置")
    except clock_unavailable:
        return _refuse(log, "clock_unavailable")
    return None


def _check_join_and_window(act_id, *, cancel_joined, cancel_facts,
                           precheck_budget_s, business_now, clock_unavailable, log):
    """核对确实已报名与详情取消窗口；不通过返回拒绝结果，通过返回 None。"""
    # 3 确实已报名（三态，只有 True 往下走）
    joined = cancel_joined(act_id, precheck_budget_s)
    if joined is None:
        # 分不清是校时失效还是查询没成功：再看一眼时钟，给更准的原因
        try:
            business_now()
        except clock_unavailable:
            return _refuse(log, "clock_unavailable")
        return _refuse(log, "unknown_state")
    if joined is False:
        return _refuse(log, "not_signed")
    # 4 详情：允许取消，且业务北京时间在 [报名开始, 报名截止] 内
    facts = cancel_facts(act_id)
    if facts is None:
        return _refuse(log, "unknown_state")
    allowed, sign_start, sign_end = facts
    if allowed is not True:
        return _refuse(log, "not_allowed")
    if sign_start is None or sign_end is None:
        return _refuse(log, "unknown_state")
    try:
        now = business_now()
    except clock_unavailable:
        return _refuse(log, "clock_unavailable")
    if not (sign_start <= now <= sign_end):
        return _refuse(log, "window_closed")
    return None


def _send_and_recheck(act_id, progress, *, get, cancel_path, cancel_joined,
                      recheck_budget_s, sanitize_message, log):
    """调用一次取消接口并按 getJoinInfo 复查结果返回最终字典。"""
    # 5 调取消接口：只调一次、不重试；从这一行起「结果未知」都算 unknown
    log("[cancel] 前置核对通过，调用取消接口一次")
    if progress is not None:
        progress["sent"] = True
    reply = get(cancel_path + urllib.parse.quote(act_id, safe=""))
    # 6 以复查为准：回包只拿来给「没取消成」配一句学校原话
    after = cancel_joined(act_id, recheck_budget_s)
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
        message = sanitize_message(reply.get("message")) if from_school else ""
        if message:
            result["message"] = message
        return result
    log("[cancel] 复查没查到结果")
    return {"ok": False, "kind": "unknown"}


def run_cancel(act_id, progress=None, *, site_configured, probe_token,
               business_now, has_clock_meta, cancel_joined, cancel_facts,
               get, log, cancel_path, precheck_budget_s, recheck_budget_s,
               clock_unavailable, sanitize_message):
    """取消报名的全部流程，返回 {ok, kind, reason?, message?}；不打印、不读 args。

    progress 是调用方给的字典：调取消接口之前把 sent 置真，供异常兜底区分阶段。
    """
    act_id = str(act_id or "").strip()
    denied = _check_auth_and_clock(
        act_id, site_configured=site_configured, probe_token=probe_token,
        business_now=business_now, has_clock_meta=has_clock_meta,
        clock_unavailable=clock_unavailable, log=log)
    if denied is not None:
        return denied
    denied = _check_join_and_window(
        act_id, cancel_joined=cancel_joined, cancel_facts=cancel_facts,
        precheck_budget_s=precheck_budget_s, business_now=business_now,
        clock_unavailable=clock_unavailable, log=log)
    if denied is not None:
        return denied
    return _send_and_recheck(
        act_id, progress, get=get, cancel_path=cancel_path,
        cancel_joined=cancel_joined, recheck_budget_s=recheck_budget_s,
        sanitize_message=sanitize_message, log=log)


def cancel_facts(act_id, *, get_fn, detail_timeout_s, detail_fields_fn,
                 tri_state_fn, school_epoch_fn):
    """取消前要看的详情：(cancel_allowed, sign_start, sign_end) 或 None（详情没拿到）。"""
    data = get_fn("/rjyHd/getInfo/" + urllib.parse.quote(act_id, safe=""),
                  timeout=detail_timeout_s)
    if not isinstance(data, dict) or str(data.get("code")) not in {"1", "1.0"}:
        return None
    fields = detail_fields_fn(data)
    allowed = tri_state_fn(fields.get("qxbm")) if "qxbm" in fields else None
    return (allowed, school_epoch_fn(str(fields.get("bmkssj") or "").strip()),
            school_epoch_fn(str(fields.get("bmjssj") or "").strip()))


def cancel_joined(act_id, budget_s, *, business_now_fn, make_budget_fn,
                  is_joined_fn, budget_exhausted_cls, clock_unavailable):
    """取消前后用的三态查询：True / False / None（含预算用尽、校时失效）。"""
    try:
        budget = make_budget_fn(business_now_fn() + budget_s)
        return is_joined_fn(act_id, budget=budget)
    except (budget_exhausted_cls, clock_unavailable):
        return None


def run_cmd_cancel(args, *, stdout_to_stderr_fn, run_cancel_fn, log_fn):
    """worker 子命令：取消一场已报名活动。stdout 恰好一行 JSON，日志与其他输出走 stderr。"""
    progress = {"sent": False}
    with stdout_to_stderr_fn(True):
        try:
            result = run_cancel_fn(getattr(args, "id", ""), progress)
        except Exception as exc:  # noqa: BLE001 - 兜底：worker 不能不给结论
            # 异常要分清「接口还没调」与「已经调了」：前者是前置失败，后者结果未知
            log_fn("[cancel] 异常 %s" % type(exc).__name__)
            result = ({"ok": False, "kind": "unknown"} if progress["sent"]
                      else {"ok": False, "kind": "precheck_failed",
                            "reason": "unknown_state"})
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result.get("kind") == "cancelled" else 2
