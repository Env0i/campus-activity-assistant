"""个人变动私聊：公开变动里，只挑「我报了名 / 我排了队」的场次单独告诉 owner。

与公共链路的分工：activity_watch.py 照旧只发群里的公开事件，群消息口径一点不变；
这里在同一轮的抓取结果上再筛一遍，只对已报名和预报名清单里的场次私聊说明：
改了什么、旧值到新值、改完有没有和别的场次撞时间；连续三轮没抓到的场次也在
这里提一句，但不动清单本身。

边界：

- 私聊发不出去就留在 data/personal_notice.json 里等下一轮，不丢也不重复；
- 没配 owner 私聊会话时只留一行日志，不抛错、不影响公共推送；
- 只在内存里比对：不回写预报名清单，也不触发任何报名动作；
- 只处理「字段变化」与「连续缺失下架」，报名开放提醒仍归预报名 runner。

@author Author
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _sub in ("lib", "signup"):
    _p = str(ROOT / "scripts" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import watchlist                                        # noqa: E402
from common import DATA, atomic_write_text, file_lock    # noqa: E402
from fetch import parse_dt                              # noqa: E402
from mine_rules import interval, overlaps               # noqa: E402
from notify import send_private                         # noqa: E402

STATE = Path(os.environ.get("PERSONAL_NOTICE_STATE") or (DATA / "personal_notice.json"))
LOCK = Path(os.environ.get("PERSONAL_NOTICE_LOCK") or (DATA / "personal_notice.lock"))
FMT = "%Y-%m-%d %H:%M:%S"
KEEP_DAYS = 7
MAX_PENDING = 20

RELATION = {"signed": "已报名", "queued": "预报名"}

# 字段标签与公共事件保持同一套说法；test_owner_chat 会核对两边一致
FIELD_LABELS = {
    "name": "活动名称",
    "type": "类型",
    "place": "地点",
    "sign_start": "报名开放时间",
    "sign_end": "报名截止时间",
    "act_start": "活动开始时间",
    "act_end": "活动结束时间",
    "checkin": "签到时间",
}


def load_state() -> dict:
    """读状态；不存在算空。读坏了抛出，免得把待发条目当没有。"""
    try:
        raw = json.loads(STATE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"sent": {}, "pending": [], "known": {}}
    except Exception as exc:                             # noqa: BLE001
        raise RuntimeError("个人变动状态读取失败：%s" % exc) from exc
    if not isinstance(raw, dict):
        raise RuntimeError("个人变动状态结构不是对象")
    return {
        "sent": raw.get("sent") if isinstance(raw.get("sent"), dict) else {},
        "pending": raw.get("pending") if isinstance(raw.get("pending"), list) else [],
        "known": raw.get("known") if isinstance(raw.get("known"), dict) else {},
    }


def save_state(state: dict) -> None:
    """原子写（0600）+ 文件锁：动态监测与手动试跑可能撞在一起。"""
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(LOCK):
        atomic_write_text(STATE, json.dumps(state, ensure_ascii=False, indent=2),
                          mode=0o600)


def _entries() -> list:
    """预报名清单只读：读不到就当没有排队场次，不让私聊提醒挡住公共链路。"""
    try:
        return watchlist.load()
    except Exception as exc:                             # noqa: BLE001
        print("[!] 预报名清单读取失败，本轮只按已报名判断：%s" % exc)
        return []


def _relations(items: list, known: dict, now: datetime) -> dict:
    """这一轮「和我有关」的场次：已报名看接口，预报名看清单。

    关系表跨轮保留：活动连续三轮没抓到时它已经不在列表里了，只能靠这张表
    认出「那是我报过名的场次」。超过 KEEP_DAYS 没再出现的关系自动丢掉。
    """
    table = {key: dict(value) for key, value in (known or {}).items()
             if isinstance(value, dict)}
    stamp = now.strftime(FMT)
    for item in items or []:
        aid = str(item.get("id") or "")
        if aid and item.get("signed"):
            table[aid] = {"relation": "signed", "last_seen": stamp}
    for entry in _entries():
        aid = str(entry.get("id") or "")
        if aid and aid not in table:
            table[aid] = {"relation": "queued", "last_seen": stamp}
    cutoff = now - timedelta(days=KEEP_DAYS)
    return {aid: rec for aid, rec in table.items()
            if (parse_dt(rec.get("last_seen")) or cutoff) >= cutoff}


def _value(text) -> str:
    """旧值 / 新值的展示：空值写「未公布」，时间去掉秒，其余原样。"""
    raw = str(text or "").strip()
    if not raw:
        return "未公布"
    return raw[:16]


def _event_key(event: dict) -> str:
    """去重键：同一场同一组新值只提醒一次，改第二次是新的一条。"""
    fields = event.get("changed_fields") or []
    payload = json.dumps({key: event.get(key) for key in fields},
                         ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return "%s:changed:%s" % (event.get("id"), digest)


def _change_text(event: dict, relation: str) -> str:
    """一条变动：活动名 + 身份 + 每个字段的「旧值 → 新值」。"""
    previous = event.get("previous") or {}
    parts = []
    for field in event.get("changed_fields") or []:
        parts.append("%s %s → %s" % (FIELD_LABELS.get(field, field),
                                    _value(previous.get(field)), _value(event.get(field))))
    name = event.get("name") or str(event.get("id") or "")[:8]
    return "▸ 「%s」（%s）%s" % (name, RELATION.get(relation, relation), "；".join(parts))


def _conflict_text(event: dict, items: list, known: dict) -> str:
    """改期后重新比一遍冲突：只提醒，不改清单，也不拦任何动作。"""
    mine = interval(event.get("act_start"), event.get("act_end"))
    if mine is None:
        return ""
    names = []
    for item in items or []:
        aid = str(item.get("id") or "")
        if not aid or aid == str(event.get("id") or ""):
            continue
        if not (known.get(aid) or {}).get("relation"):
            continue
        if overlaps(mine, interval(item.get("act_start"), item.get("act_end"))):
            names.append(item.get("name") or aid[:8])
    if not names:
        return ""
    return "\n  ⚠️ 和 %s 举办时间冲突，请自行确认" % "、".join(
        "「%s」" % name for name in names[:3])


def _collect(items: list, events: list, gone: list, known: dict) -> list:
    """把这一轮公开变动筛成私聊条目；和我无关的一律不出现。"""
    notices = []
    for event in events or []:
        if not event.get("changed_fields"):
            continue
        relation = (known.get(str(event.get("id") or "")) or {}).get("relation")
        if not relation:
            continue
        notices.append({"key": _event_key(event),
                        "text": _change_text(event, relation)
                                + _conflict_text(event, items, known)})
    for row in gone or []:
        aid = str(row.get("id") or "")
        relation = (known.get(aid) or {}).get("relation")
        if not relation:
            continue
        notices.append({"key": "%s:gone" % aid,
                        "text": "▸ 「%s」（%s）连续三轮没抓到，可能已下架（清单未改动）"
                                % (row.get("name") or aid[:8], RELATION[relation])})
    return notices


def _merge(existing: list, fresh: list) -> list:
    """上一轮没发出去的和这一轮新发现的一起发：按 key 合并，不重不漏。"""
    merged = {str(n.get("key")): n for n in (existing or [])
              if isinstance(n, dict) and n.get("key")}
    for notice in fresh or []:
        merged.setdefault(notice["key"], notice)
    return list(merged.values())[-MAX_PENDING:]


def _digest(pending: list) -> str:
    """多条合成一条私聊：改动多的日子也只占一条消息。"""
    return "\n".join(["📌 你关注的活动有变动"] + [n["text"] for n in pending])


def announce(items: list, events: list, gone: list, now: datetime,
             dry: bool = False, send=None) -> bool:
    """一轮入口：个人提醒出错只留一行日志，绝不拖垮公共推送链路。"""
    try:
        return _announce(items, events, gone, now, dry, send)
    except Exception as exc:                              # noqa: BLE001
        print("[!] 个人变动提醒失败（%s：%s），本轮跳过" % (type(exc).__name__, exc))
        return False


def _announce(items: list, events: list, gone: list, now: datetime,
              dry: bool, send=None) -> bool:
    """算变动、合并待发、私聊 owner；没配私聊时只留一行日志。"""
    if dry:
        return True
    send = send or send_private
    state = load_state()
    known = _relations(items, state.get("known") or {}, now)
    fresh = [notice for notice in _collect(items, events, gone, known)
             if notice["key"] not in (state.get("sent") or {})]
    pending = _merge(state.get("pending"), fresh)
    state["known"] = known
    if not pending:
        save_state(state)
        return True
    if send(_digest(pending)) is not True:
        state["pending"] = pending
        save_state(state)
        print("[!] 个人变动提醒没发出去，留到下一轮再试")
        return False
    for notice in pending:
        state["sent"][notice["key"]] = now.strftime(FMT)
    cutoff = now - timedelta(days=KEEP_DAYS)
    state["sent"] = {key: stamp for key, stamp in state["sent"].items()
                     if (parse_dt(stamp) or cutoff) >= cutoff}
    state["pending"] = []
    save_state(state)
    return True

