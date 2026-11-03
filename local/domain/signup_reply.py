"""学校报名回包分类（决策 015；架构修订设计文档 3.3 节）。

纯函数：不做网络、不读时钟、不 import grab.py。把一笔 HTTP 200 的业务回包按
code 和 message 里的关键短语归成一种 kind，worker 据此决定继续发、本场结束，
还是退回点击。学校出现新文案时，往 PHRASE_TABLE 加一行即可。

判定顺序：code=1 成功 → code=4001 登录失效 → 关键短语 → 其余一律 unknown。
登录失效只认 code=4001：「请登录后完成身份验证」这类业务文案里的字眼不算
（与 worker 既有的子串误判守卫一致）。
关键短语按「包含」判断、不看 code：实测里这些文案都带固定 code（500 或 0），
但同一句话换了 code 时，按话的意思处理比按 code 猜更稳。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignupReply:
    """一笔回包的分类结论。

    kind  ：success / not_open / full / conflict / closed / version /
            stale_ts / no_activity / login_invalid / unknown
    label ：给界面和终态的短中文结论，不含学校原文
    raw   ：「code:<code> <message>」原文，不截断，只进日志
    """
    kind: str
    label: str
    raw: str


# (kind, 关键短语, label)；每行后面的注释是证据来源（日期 + 实测节号）
PHRASE_TABLE = (
    ("not_open", "报名未开始", "报名还没开始"),       # 实测 §28：开放前 1 秒回 code=500「报名未开始！」
    ("full", "报名人数已满", "名额已满"),             # 实测 §14、§35、§40：code=500「报名人数已满」
    ("conflict", "时间冲突", "时间冲突"),             # 实测 §28：报上后再发回 code=500「活动时间与已参与活动时间冲突」
    ("closed", "报名已结束", "报名已截止"),           # 签名材料 §5：已截止活动回 code=500「报名已结束！」
    ("version", "版本不兼容", "版本不兼容"),          # 签名材料 §5：hash 解不开回 code=0「版本不兼容……」
    ("stale_ts", "请求已超时", "请求已超时，本机时钟可能不准"),  # 签名材料 §5：时间戳超出约 60 秒回 code=0
    # 签名材料 §5：活动 ID 查不到回 code=0「Cache 'hd-info' ……」；成因未完全证实，
    # worker 在直发时先退回点击核实，点击上也这样才按「活动不存在」结束
    ("no_activity", "hd-info", "活动不存在"),
)

SUCCESS_LABEL = "报名成功"
LOGIN_INVALID_LABEL = "登录失效"
UNKNOWN_LABEL = "学校回了无法识别的结果"

# 这些 kind 一出现本场就结束；值是写进终态行的 stop_reason
TERMINAL_STOP_REASONS = {
    "full": "full",
    "closed": "closed",
    "conflict": "conflict",
    "no_activity": "no_activity",
}

# 同一条未识别回包连续出现几次就处理：直发先退回点击，点击时再出现就结束本场
UNKNOWN_REPLY_LIMIT = 3
# 「请求已超时」连续几次就判本机时钟有问题、结束本场
STALE_TS_LIMIT = 2

# 新增终态的界面短结论；不在表里的 stop_reason 返回空串，由调用方沿用旧文案
STOP_REASON_LABELS = {
    "full": "名额已满",
    "closed": "报名已截止",
    "conflict": "时间冲突",
    "no_activity": "活动不存在",
    "clock_skew": "本机时钟不准",
    "unknown_reply": "学校回了无法识别的结果",
    # 不是学校回包，而是退回点击时详情页打不开（决策 015）
    "page_unavailable": "学校页面打不开",
}


def _code_text(code) -> str:
    return str(code).strip() if code is not None else ""


def classify_signup_reply(code, message) -> SignupReply:
    """按分类表给一笔回包定性；任何输入都不抛异常。"""
    text = str(message or "").strip()
    code_text = _code_text(code)
    raw = "code:%s %s" % (code_text or "?", text)
    if code_text == "1":
        return SignupReply("success", SUCCESS_LABEL, raw)
    if code_text == "4001":
        return SignupReply("login_invalid", LOGIN_INVALID_LABEL, raw)
    for kind, phrase, label in PHRASE_TABLE:
        if phrase in text:
            return SignupReply(kind, label, raw)
    return SignupReply("unknown", UNKNOWN_LABEL, raw)


def stop_reason_label(stop_reason) -> str:
    """新增终态的短结论；旧终态（success、max_attempts 等）返回空串。"""
    return STOP_REASON_LABELS.get(str(stop_reason or ""), "")
