# -*- coding: utf-8 -*-
"""登录状态分类：三态快照构造、check 四态结论与来源行归因。

纯函数：token / 会话文本 / 剩余小时数由调用方（app 外观）读好传入；
本模块不读 session.json、不读 ui.json、不调用任何时钟对象。

@author Author
"""
from __future__ import annotations

import hashlib

from domain.time_text import parse_local_time


# 计划运行中「来不及重新登录」的窗口：有场次在提交、或离开放不到这么多秒。
# 界面「修改计划」的禁用条件用的是同一个数（local/ui 里有同名常量和契约测试盯着）。
LATE_WINDOW_S = 100

# E1（计划 20261109-list-time-and-estimate，决策 006 修订 2026-11-09）：
# 登录预计有效时长取实测下限 10 小时，宁可提前提醒；只作提示，
# 绝不参与放行、拦截、过期判定或清理会话。
LOGIN_ESTIMATE_H = 10.0


def relogin_too_late(tasks, now, open_epoch) -> bool:
    """计划里还有没有时间让用户重新登录（架构方案 4.3）。

    有场次在提交，或者还没提交的场次离开放不到 LATE_WINDOW_S 秒（含已经过了开放
    时刻还在排队的立即报名场次），就是来不及：这时只有电脑能自动登录。
    open_epoch(task) 返回该场开放时刻的 epoch 秒，读不出来返回 None（这一场不参与判断）。
    """
    for task in tasks or []:
        task = task if isinstance(task, dict) else {}
        status = str(task.get("status") or "")
        if status == "submitting":
            return True
        if status not in ("queued", "waiting"):
            continue
        opens = open_epoch(task)
        if opens is not None and float(opens) - float(now) <= LATE_WINDOW_S:
            return True
    return False


def mask_account(name) -> str:
    """账号打码：前两位加后两位，中间四个星号；太短的只留第一位。"""
    text = str(name or "").strip()
    if not text:
        return ""
    if len(text) >= 5:
        return text[:2] + "****" + text[-2:]
    return text[:1] + "****"


def credential_id(token: str) -> str:
    """本机内部凭证摘要：只用于把 v2 锚点和具体凭证绑定，不输出到日志。"""
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()[:16]


def component_error(exc: Exception) -> str:
    """把**进程创建**抛出的异常归类为结构化组件错误码（check/list/login 收尾共用）。

    只对进程启动阶段的 OSError 调用：文件/权限/其他 OS 层失败才有资格归组件码。
    数据/解析等普通异常不进这里——数据坏了不是组件坏了，不得诱导重新下载。
    """
    if isinstance(exc, FileNotFoundError):
        return "worker_missing"
    if isinstance(exc, PermissionError):
        return "worker_permission"
    return "spawn_failed"


def session_estimated_expires_at(save_epoch, lifetime_h: float = LOGIN_ESTIMATE_H):
    """按登录锚点 + 预计寿命给出的预计失效时刻（epoch 秒）；锚点不可用返回 None。

    E1：这只是提醒，与学校真实校验无关——估算到点不代表会话失效。
    """
    if isinstance(save_epoch, bool) or not isinstance(save_epoch, (int, float)):
        return None
    try:
        value = float(save_epoch)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value + float(lifetime_h) * 3600.0


def session_estimate_from_anchor(timing, token: str, now):
    """从 v2 锚点估算剩余小时与预计失效时刻（E1，纯函数）。

    返回 {hours_left, estimated_expires_at, estimate_reason}：
    - ok：锚点与当前凭证匹配，且有可信北京时间
    - no_anchor：没有锚点，或锚点属于别的凭证（换登录/在别处登录后复用）
    - clock_unavailable：锚点匹配但业务时钟不可用，估算不出来
    """
    saved_epoch = None
    if isinstance(timing, dict) and timing.get("credential_id") == credential_id(token):
        raw = timing.get("saved_epoch")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            saved_epoch = float(raw)
    if saved_epoch is None:
        return {"hours_left": None, "estimated_expires_at": None,
                "estimate_reason": "no_anchor"}
    if now is None:
        return {"hours_left": None, "estimated_expires_at": None,
                "estimate_reason": "clock_unavailable"}
    return {
        "hours_left": hours_left_from_anchor(timing, token, now, LOGIN_ESTIMATE_H),
        "estimated_expires_at": session_estimated_expires_at(saved_epoch),
        "estimate_reason": "ok",
    }


def build_session_state(token, saved_text, hours_left=None, now=None, timing=None) -> dict:
    """登录三态快照（纯函数）：区分「从没登录过」和「登录过期」。

    「没有登录」= 缺 token；只有 token 还在但已过期才叫登录态失效。
    缺 token 时 hours_left 必须是 None——按 saved_at 报一个假的小时数会把
    空壳会话显示成有效。saved_at / estimated_expires_at 只是估算提醒，
    登录有效性永远以学校真实校验为准，二者绝不参与放行或拦截。

    E1（2026-11-09）：估算改为「v2 锚点 + LOGIN_ESTIMATE_H」，
    session_expired 与估算彻底脱钩——估算到点也不算失效，是否失效只由
    学校真实校验（check 事件）决定。
    """
    state = {"session_present": False, "session_expired": False, "hours_left": None,
             "saved_at": None, "estimated_expires_at": None,
             "estimate_reason": "no_anchor"}
    token = str(token or "").strip()
    saved_text = str(saved_text or "").strip()
    if not token:
        return state
    state["session_present"] = True
    saved = parse_local_time(saved_text)
    if saved is not None:
        state["saved_at"] = saved_text
    if timing is not None:
        state.update(session_estimate_from_anchor(timing, token, now))
    else:
        # 兼容旧调用方：没有锚点时只回传调用方给的静态值，不据此算失效
        state["hours_left"] = hours_left
    return state


def hours_left_from_anchor(timing: "dict | None", token: str, now: "float | None",
                           lifetime_h: float) -> "float | None":
    """登录剩余估算（纯函数）：只认与当前凭证匹配的 v2 锚点 + 可信业务时刻。

    旧 saved_at 是本机墙钟文本，无法反推真实 UTC，绝不拿系统当前时间减它
    冒充准确小时数。now=None（无业务时钟）一律返回 None = 「暂无法估算」。
    """
    if not isinstance(timing, dict) or timing.get("credential_id") != credential_id(token):
        return None
    saved_epoch = timing.get("saved_epoch")
    if not isinstance(saved_epoch, (int, float)):
        return None
    if now is None:
        return None
    used = (float(now) - float(saved_epoch)) / 3600.0
    return max(0.0, float(lifetime_h) - used)


def check_reason_line(out: str) -> tuple[str, str]:
    """从 check 的完整输出提取 (来源行, 末行)。

    归因只信第一条 [X] 来源行——失败输出的末尾固定是「请重新登录」指引，
    拿末行分类会把网络错误误判成登录失效；末行仍返回给界面做时钟偏差展示。
    结构化 [clock]/[checkpoint] 行不是人话，既不当来源也不当末行。
    空输出返回 ("", "")，调用方按「认不出的失败」落 unknown。
    """
    lines = [ln.strip() for ln in str(out or "").strip().splitlines() if ln.strip()]
    lines = [ln for ln in lines if "[clock] " not in ln and "[checkpoint] " not in ln]
    reason = next((ln for ln in lines if ln.startswith("[X] ")), "")
    return reason, (lines[-1] if lines else "")


def check_hint(text: str, code: int) -> str:
    """把 check 的来源行粗分类：network / login / error（成功返回空）。

    成功输出本来就常含「登录」字样（如「登录态还有 17 小时」），
    必须先按退出码认成功。归因顺序网络词优先：身份验证服务的超时、
    连接失败是网络问题而不是登录失效（「身份验证服务超时」不得误归
    login）；网络词都不命中时，4001/「登录」/「身份验证失败」才算登录类；
    其余含糊文本落 error（上游统一归 unknown，宁可暂不确认也不误导重登）。
    """
    raw = str(text or "")
    if code == 0:
        return ""
    if any(word in raw for word in ("网络", "连接", "超时", "URLError", "HTTPError", "timed out", "Timeout")):
        return "network"
    if "4001" in raw or "登录" in raw or "身份验证失败" in raw:
        return "login"
    return "error"


def check_result(state: dict, code: int, text: str) -> str:
    """check 的四态结论：valid / expired / unknown / none（附加字段，旧 UI 可忽略）。

    只有学校接口真实成功才是 valid；本机没有会话是 none；能认出的登录失效
    （4001/登录类字样，且不含网络词）是 expired；网络类与认不出的失败一律
    unknown——网络异常不能被误报成「必须重新登录」。
    """
    if code == 0:
        return "valid"
    if not state.get("session_present"):
        return "none"
    hint = check_hint(text, code)
    if hint == "network":
        return "unknown"
    if hint == "login":
        return "expired"
    return "unknown"
