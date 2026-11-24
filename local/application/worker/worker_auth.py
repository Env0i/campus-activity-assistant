# -*- coding: utf-8 -*-
"""worker 鉴权探测、运行时密钥读取与 check 命令编排。

从 grab.py 搬出：全部外部依赖（HTTP 请求、token 读取、密钥解析、时钟采样、
睡眠与日志）都在每次调用时由调用方注入，本模块不 import grab 或 infrastructure。

@author Author
"""
from __future__ import annotations

import json


def probe_list(tok, budget=None, *, post_fn):
    """登录探测用的最小列表请求（1 条），只看 code。"""
    return post_fn("/rjyHd/listActivity",
                   {"pageSize": 1, "pageNum": 1, "hdmc": "", "hdzt": None,
                    "kssj": "", "jssj": ""}, tok, budget=budget)


def fetch_runtime_key(budget=None, *, post_fn, token_fn, runtime_profile_path,
                      parse_runtime_key_fn, budget_exhausted_cls, clock_unavailable):
    """向学校取本场的运行时密钥（决策 015）：返回 (密钥字节或 None, 给日志的原因)。"""
    try:
        data = post_fn(runtime_profile_path, {}, token_fn(), budget=budget)
    except (budget_exhausted_cls, clock_unavailable):
        raise
    except Exception as exc:  # noqa: BLE001 - 取不到就退回点击，不让异常打断本场
        return None, "请求异常 %s" % type(exc).__name__
    key = parse_runtime_key_fn(data)
    if key is None:
        code = data.get("code") if isinstance(data, dict) else None
        message = str(data.get("message") or "") if isinstance(data, dict) else ""
        return None, "返回里没有可用密钥（code=%s %s）" % (code, message[:40])
    return key, "已取到"


def probe_token(budget=None, *, token_fn, probe_list_fn, login_recheck_s,
                time_mod, log_fn):
    """登录探测四态：valid / expired / none / unknown。"""
    tok = token_fn()
    if not tok:
        return "none", "本机还没有登录过（data/session.json 不存在）"
    data = probe_list_fn(tok, budget)
    code = data.get("code")
    if code == 1:
        return "valid", "ok"
    if str(code) != "4001":
        return "unknown", "接口异常：%s" % (data.get("message") or code)
    expired_detail = "登录态已过期（%s）" % (data.get("message") or "身份验证失败")
    if budget is not None and budget.remaining_s() <= login_recheck_s:
        return "expired", expired_detail
    if budget is not None:
        budget.sleep(login_recheck_s)
    else:
        time_mod.sleep(login_recheck_s)
    again = probe_list_fn(token_fn() or tok, budget)
    again_code = again.get("code")
    if str(again_code) == "4001":
        return "expired", expired_detail
    log_fn("[i] 登录探测：4001 后复查恢复（复查 code=%s）" % (again_code,))
    if again_code == 1:
        return "valid", "ok"
    return "unknown", "接口异常：%s" % (again.get("message") or again_code)


def check_token(budget=None, *, probe_token_fn):
    """用活动列表接口判定登录态：code=1 有效，4001 表示 token 失效。"""
    state, detail = probe_token_fn(budget)
    return state == "valid", detail


def run_check(args, *, check_token_fn, clock_sample_fn, log_fn):
    """check 子命令：校验登录态并输出结构化粗校时结论。"""
    ok, msg = check_token_fn()
    if ok:
        print("[OK] 登录态有效。")
        # 每轮都给结构化粗校时结论：正常/未知也要有，界面才能替换旧告警
        sample = clock_sample_fn()
        log_fn("[clock] " + json.dumps(sample, ensure_ascii=False, separators=(",", ":")))
        if sample.get("state") == "warn":
            print("[!] 学校 HTTP Date 与本机时间有偏差（粗测含网络误差约 ±%.1f 秒）。"
                  "该粗测只作诊断，报名调度按工具自己的北京时间执行。" %
                  (sample.get("uncertainty_s") or 1.0))
        return 0
    print("[X] %s" % msg)
    print("    请运行：python grab.py login   （或双击 1-登录.bat）")
    return 2
