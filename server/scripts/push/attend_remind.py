"""开始与签退提醒：每 5 分钟跑一轮，只在临近的窗口里提醒已报名的场次。

口径（决策 016 这一批）：

- 开始提醒：举办开始前 30 分钟进入窗口，活动一开始就不再补发；
- 签退提醒：需要签退的场次在签退时段开始时发；学校没给签退时段就在结束前
  10 分钟发。要不要签退、时段是什么只有详情接口知道，所以一场活动当天第一次
  进入候选时查一次 getInfo，结果缓存在状态文件里，当天后续轮次不再查；
- 去重按「场次 + 提醒类型」记在 data/attend_remind.json，只有发送成功才落盘；
- 没有临近场次时只取一次活动列表，一次 getInfo 都不调；
- 错过窗口不补发：晚了就晚了，下一条提醒比一条过时的提醒更有用。

用法：
    python3 scripts/push/attend_remind.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _sub in ("lib", "push"):
    _p = str(ROOT / "scripts" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common import (DATA, atomic_write_text, business_now, file_lock,  # noqa: E402
                    load_session)
from fetch import fetch_all, parse_dt  # noqa: E402
from mine_rules import parse_attendance, span_text  # noqa: E402
from notify import send_private  # noqa: E402
from school_detail import SchoolRequestError, get_detail  # noqa: E402

# 测试可以指到临时文件，避免污染真实状态
STATE = Path(os.environ.get("ATTEND_REMIND_STATE") or (DATA / "attend_remind.json"))
LOCK = Path(os.environ.get("ATTEND_REMIND_LOCK") or (DATA / "attend_remind.lock"))
FMT = "%Y-%m-%d %H:%M:%S"
START_LEAD = timedelta(minutes=30)      # 开始前 30 分钟进提醒窗口
CHECKOUT_LEAD = timedelta(minutes=10)   # 没给签退时段时的兜底：结束前 10 分钟
WINDOW = timedelta(minutes=30)          # 一次提醒的有效时长，过了算错过
KEEP_DAYS = 7
KIND_TEXT = {"start": "开始", "checkout": "签退"}


def load_state() -> dict:
    """读状态文件；不存在算空。读坏了抛出——清空它等于把去重记录一起丢掉。"""
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"facts": {}, "sent": {}}
    except Exception as exc:                                  # noqa: BLE001
        raise RuntimeError("提醒状态文件读取失败：%s" % exc) from exc
    if not isinstance(raw, dict):
        raise RuntimeError("提醒状态文件结构不是对象")
    facts = raw.get("facts") if isinstance(raw.get("facts"), dict) else {}
    sent = raw.get("sent") if isinstance(raw.get("sent"), dict) else {}
    return {"facts": facts, "sent": sent}


def save_state(state: dict) -> None:
    """原子写 + 文件锁：5 分钟一轮，可能和手动试跑撞在一起。"""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(state, ensure_ascii=False, indent=2)
    with file_lock(LOCK):
        atomic_write_text(STATE, body, mode=0o600)


def prune(state: dict, now: datetime) -> None:
    """只留当天的详情缓存和最近 7 天的发送记录，状态文件不随时间长胖。"""
    today = now.strftime("%Y-%m-%d")
    state["facts"] = {key: value for key, value in state["facts"].items()
                      if isinstance(value, dict) and value.get("date") == today}
    cutoff = now - timedelta(days=KEEP_DAYS)
    kept = {}
    for key, stamp in state["sent"].items():
        when = parse_dt(stamp)
        if when and when >= cutoff:
            kept[key] = stamp
    state["sent"] = kept


def facts_for(state: dict, activity_id: str, token: str, now: datetime, detail=None):
    """当天第一次进入候选时查一次详情；查不到就跳过这一场，不凭猜测发时段。"""
    cached = state["facts"].get(activity_id)
    today = now.strftime("%Y-%m-%d")
    if isinstance(cached, dict) and cached.get("date") == today:
        return cached
    detail = detail or get_detail
    try:
        raw = detail(activity_id, token)
    except SchoolRequestError as exc:
        print("[!] %s 的详情查不到（%s），这一场本轮不提醒" % (activity_id[:8], exc.kind))
        return None
    facts = parse_attendance(raw)
    facts["date"] = today
    state["facts"][activity_id] = facts
    return facts


def my_items(items: list, now: datetime) -> list:
    """已报名且还没结束的场次。

    不能用 fetch.mine_items：它把已经开始的场次滤掉了，而签退提醒恰恰要发在
    活动进行中。结束时间缺失时保守留下，交给详情与窗口再判。
    """
    mine = []
    for item in items:
        if not item.get("signed"):
            continue
        end = parse_dt(item.get("act_end"))
        if end and end <= now:
            continue
        mine.append(item)
    mine.sort(key=lambda it: it.get("act_start") or "")
    return mine


def start_due(item: dict, now: datetime) -> bool:
    """开始前 30 分钟到开始是提醒窗口；已经开始的场次不补发。"""
    start = parse_dt(item.get("act_start"))
    return bool(start) and start - START_LEAD <= now < start


def need_detail(item: dict, now: datetime) -> bool:
    """要不要看详情：在开始窗口里，或者已经开始还没结束（可能要签退）。"""
    if start_due(item, now):
        return True
    begin, end = parse_dt(item.get("act_start")), parse_dt(item.get("act_end"))
    return bool(begin and end) and begin <= now < end


def checkout_due(item: dict, facts: dict, now: datetime) -> bool:
    """签退提醒：签退时段一开始就发；学校没给时段就结束前 10 分钟。"""
    if not facts.get("checkout_required"):
        return False
    end = parse_dt(item.get("act_end"))
    if not end:
        return False
    begin = parse_dt(facts.get("checkout_start")) or (end - CHECKOUT_LEAD)
    return begin <= now < min(begin + WINDOW, end)


def _time_text(begin: str, end: str) -> str:
    """时段文本：有起有止写区间，只有起点写「X 起」，都没有返回空串。"""
    span = span_text(begin, end)
    if span:
        return span
    moment = parse_dt(begin)
    if not moment:
        return ""
    return "%d月%d日 %02d:%02d 起" % (moment.month, moment.day, moment.hour, moment.minute)


def start_text(item: dict, facts: dict) -> str:
    """开始提醒：活动名、开始时间、地点、签到要求与时段。"""
    begin = parse_dt(item.get("act_start"))
    lines = ["⏰ 30 分钟后开始：%s" % (item.get("name") or "活动"),
             "开始 %s" % ("%d月%d日 %02d:%02d" % (begin.month, begin.day, begin.hour,
                                                 begin.minute) if begin else "待确认")]
    if item.get("place"):
        lines.append("地点 %s" % item["place"])
    required = facts.get("checkin_required")
    if required is None:
        lines.append("签到：未知（以现场要求为准）")
    elif not required:
        lines.append("签到：无需签到")
    else:
        span = _time_text(facts.get("checkin_start"), facts.get("checkin_end"))
        lines.append("签到：需要" + ("，时段 " + span if span else "（学校没给时段）"))
    return "\n".join(lines)


def checkout_text(item: dict, facts: dict) -> str:
    """签退提醒：签退时段与地点；学校没给时段就直说时间到。"""
    span = _time_text(facts.get("checkout_start"), facts.get("checkout_end"))
    lines = ["🏁 可以签退了：%s" % (item.get("name") or "活动"),
             "签退时段 " + span if span else "签退时间到（学校没给时段）"]
    if item.get("place"):
        lines.append("地点 %s" % item["place"])
    return "\n".join(lines)


def deliver(state: dict, activity_id: str, kind: str, text: str, send, now: datetime) -> bool:
    """同一场同一类只发一次；发送成功才记，失败留给下一轮再试。"""
    key = "%s:%s" % (activity_id, kind)
    if state["sent"].get(key):
        return False
    if send(text) is not True:
        print("[!] %s 的%s提醒没发出去，下一轮再试" % (activity_id[:8], KIND_TEXT[kind]))
        return False
    state["sent"][key] = now.strftime(FMT)
    return True


def _token() -> str:
    return str(load_session().get("token") or "").strip()


def run(now=None, token=None, lister=None, detail=None, send=None, state=None) -> int:
    """跑一轮：没有登录态直接退出，没有临近场次不发详情请求。"""
    now = now or business_now()
    lister, send = lister or fetch_all, send or send_private
    token = token if token is not None else _token()
    if not token:
        print("[x] 没有可用登录态（data/session.json 里没有 token），本轮提醒没发出去")
        return 2
    if state is None:
        state = load_state()
    before = json.dumps(state, sort_keys=True)
    prune(state, now)
    try:
        items = lister(token)
    except Exception as exc:                                  # noqa: BLE001
        print("[x] 取活动列表失败：%s，本轮提醒没发出去" % type(exc).__name__)
        return 3
    count = 0
    for item in my_items(items, now):
        activity_id = str(item.get("id") or "")
        if not activity_id or not need_detail(item, now):
            continue
        facts = facts_for(state, activity_id, token, now, detail)
        if facts is None:
            continue
        if start_due(item, now) and deliver(state, activity_id, "start",
                                            start_text(item, facts), send, now):
            count += 1
        if checkout_due(item, facts, now) and deliver(state, activity_id, "checkout",
                                                      checkout_text(item, facts), send, now):
            count += 1
    if json.dumps(state, sort_keys=True) != before:
        save_state(state)
    print("[i] 本轮发出 %d 条提醒" % count)
    return 0


def main() -> int:
    try:
        return run()
    except RuntimeError as exc:
        print("[x] %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
