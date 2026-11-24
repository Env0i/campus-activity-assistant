"""个人场次规则：签到签退三态、报名状态、时段重叠、取消前置与跨天时段文本。

纯函数模块：不读墙钟、不联网、不写文件，时间一律由调用方传入。口径照本机
local/infrastructure/school/activity_queries.py 与 local/application/worker/worker_cancel.py，
卡片、冲突检查、提醒脚本共用这一份实现，避免三处各写一套边界。

签到签退只做三态：True 需要、False 明确无需、None 未知。未知绝不写成「无需」——
把「学校没说」说成「不用签」比不写更糟。

@author Author
"""
from datetime import datetime, timedelta

CHECKIN_FLAG_NAMES = ("checkin_required", "sfxyqd", "sfqd", "need_checkin")
CHECKOUT_FLAG_NAMES = ("checkout_required", "sfxyqt", "sfqt", "need_checkout")
CHECKIN_START_NAMES = ("checkin_start", "qdkssj")
CHECKIN_END_NAMES = ("checkin_end", "qdjssj")
CHECKOUT_START_NAMES = ("checkout_start", "qtkssj")
CHECKOUT_END_NAMES = ("checkout_end", "qtjssj")

TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d")


def tri_state(value):
    """把接口里的签到/签退要求归一化；无法确认时保留 None，禁止猜成无需。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "是", "需要", "有"}:
        return True
    if text in {"0", "false", "no", "n", "否", "无需", "无"}:
        return False
    return None


def detail_fields(raw):
    """getInfo 回包可能直接是 data，也可能包一层 {code, data}；两种都接受。"""
    if not isinstance(raw, dict):
        return {}
    data = raw.get("data")
    return data if isinstance(data, dict) else raw


def _flag(raw, names):
    for name in names:
        if name in raw and raw.get(name) not in (None, ""):
            return tri_state(raw.get(name))
    return None


def _time_text(raw, names):
    for name in names:
        if name in raw and raw.get(name) not in (None, ""):
            return str(raw.get(name)).strip()
    return ""


def parse_attendance(raw):
    """getInfo → 签到签退要求与时段、可否取消、学校是否判冲突。

    标记明确时优先；标记缺失但时段存在才推导为需要；两者都缺失保持 None。
    """
    data = detail_fields(raw)
    checkin = _flag(data, CHECKIN_FLAG_NAMES)
    checkout = _flag(data, CHECKOUT_FLAG_NAMES)
    checkin_start = _time_text(data, CHECKIN_START_NAMES)
    checkin_end = _time_text(data, CHECKIN_END_NAMES)
    checkout_start = _time_text(data, CHECKOUT_START_NAMES)
    checkout_end = _time_text(data, CHECKOUT_END_NAMES)
    if checkin is None and (checkin_start or checkin_end):
        checkin = True
    if checkout is None and (checkout_start or checkout_end):
        checkout = True
    if checkin is False:
        checkin_start = checkin_end = ""
    if checkout is False:
        checkout_start = checkout_end = ""
    return {
        "checkin_required": checkin,
        "checkin_start": checkin_start,
        "checkin_end": checkin_end,
        "checkout_required": checkout,
        "checkout_start": checkout_start,
        "checkout_end": checkout_end,
        # qxbm（报名后允许取消）是取消前置条件之一；缺失一律 None。
        "cancel_allowed": tri_state(data.get("qxbm")) if "qxbm" in data else None,
        "can_sign": tri_state(data.get("sfkybm")) if "sfkybm" in data else None,
        "sign_start": str(data.get("bmkssj") or "").strip(),
        "sign_end": str(data.get("bmjssj") or "").strip(),
    }


def join_state(payload):
    """getJoinInfo 的 data → 是否已报名（与学校前端同口径）。

    data 为空、sfcx（已撤销）为 1、sfbm（是否报名）明确为假，都算未报名；
    其余形状（缺字段、认不出）按已报名处理：宁可漏报一次，也不重复提交。
    """
    if payload in (None, {}, []):
        return False
    if not isinstance(payload, dict):
        return True
    if payload.get("sfcx") in (1, "1", True):
        return False
    if payload.get("sfbm") in (0, "0", False):
        return False
    return True


def joined_from_response(response):
    """完整回包 → True / False / None（没查成功），三态不可混用。"""
    if not isinstance(response, dict) or str(response.get("code")) not in {"1", "1.0"}:
        return None
    return join_state(response.get("data"))


def parse_time(value):
    """学校时间文本或 datetime → datetime；空、格式不认、非法日历值一律 None。"""
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def interval(start, end):
    """(开始, 结束) 文本 → 半开区间；结束不晚于开始视为不可用。"""
    begin = parse_time(start)
    finish = parse_time(end)
    if begin is None or finish is None or finish <= begin:
        return None
    return (begin, finish)


def overlaps(first, second):
    """半开区间 [a, b) 与 [c, d) 是否重叠；任一边不可用返回 None（不知道）。"""
    if first is None or second is None:
        return None
    return first[0] < second[1] and second[0] < first[1]


def cancel_precheck(now, joined, allowed, sign_start, sign_end, clock_ok=True):
    """取消报名前置四条；通过返回 None，不通过返回原因码（与界面同一套）。

    1 业务时钟可用；2 确实已报名；3 学校允许取消；4 现在在报名窗口内。
    任一不满足或查不到都不调取消接口。
    """
    if not clock_ok or now is None:
        return "clock_unavailable"
    if joined is None:
        return "unknown_state"
    if joined is False:
        return "not_signed"
    if allowed is not True:
        return "not_allowed"
    begin = parse_time(sign_start)
    finish = parse_time(sign_end)
    if begin is None or finish is None:
        return "unknown_state"
    if not (begin <= now <= finish):
        return "window_closed"
    return None


def _clock_text(moment):
    return "%d月%d日 %02d:%02d" % (moment.month, moment.day,
                                   moment.hour, moment.minute)


def _at_midnight(moment):
    return (moment.hour, moment.minute, moment.second) == (0, 0, 0)


def span_days(start, end):
    """跨 N 天 = 结束日期 − 开始日期 + 1；结束恰为 00:00:00 时按前一天算。"""
    finish = end - timedelta(days=1) if _at_midnight(end) else end
    return (finish.date() - start.date()).days + 1


def span_text(start, end):
    """举办时段的展示文本：同一天写时分，跨天如实展开并注明跨几天。

    返回空串表示时间不可用，由调用方写「待确认」，本函数不替它编一个时刻。
    """
    pair = interval(start, end)
    if pair is None:
        return ""
    begin, finish = pair
    days = span_days(begin, finish)
    if days <= 1:
        tail = "24:00" if _at_midnight(finish) else "%02d:%02d" % (finish.hour,
                                                                  finish.minute)
        return "%s–%s" % (_clock_text(begin), tail)
    return "%s – %s（跨%d天）" % (_clock_text(begin), _clock_text(finish), days)

