"""给飞书机器人用的查询入口：只输出文字，不发消息。

用法：
    python3 scripts/push/query.py                # 待开放报名（默认）
    python3 scripts/push/query.py open           # 报名已开放
    python3 scripts/push/query.py all            # 两种都列
    python3 scripts/push/query.py types          # 有哪些活动类型
    python3 scripts/push/query.py pending --type 实践学习
"""
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))

import mine_rules                                              # noqa: E402
import school_detail                                           # noqa: E402
from card import all_card, menu_card, open_card, pending_card   # noqa: E402
from common import MAX_LIST_ITEMS, load_config, load_session   # noqa: E402
from mine_cards import cancel_available, mine_card, mine_detail_text  # noqa: E402
from fetch import classify, fetch_all                           # noqa: E402
from render import open_lines, pending_lines, trim              # noqa: E402

# 和卡片共用同一个上限：同一条活动在卡片里被截掉、在文字里还露出来，
# 两条通道就会对不上，用户会以为某一端漏了。
MAX_ITEMS = MAX_LIST_ITEMS

# 我的报名要逐场查详情（签到签退、能否取消）。一次查询的总预算与单场超时：
# 学校慢的时候宁可几场写「未知」，也不能让整张卡片等到超时。
MINE_DETAIL_BUDGET_S = 20.0
MINE_DETAIL_TIMEOUT_S = 8.0


def apply_detail(item, response):
    """把 getInfo 回包并进列表条目；查不到的部分保持 None，卡片会写未知。"""
    facts = mine_rules.parse_attendance(response)
    for key in ("checkin_required", "checkin_start", "checkin_end",
                "checkout_required", "checkout_start", "checkout_end",
                "cancel_allowed"):
        item[key] = facts[key]
    for key in ("sign_start", "sign_end"):
        if not item.get(key) and facts[key]:
            item[key] = facts[key]
    data = mine_rules.detail_fields(response)
    for key, school_key in (("act_start", "hdkssj"), ("act_end", "hdjssj")):
        if not item.get(key) and data.get(school_key):
            item[key] = str(data[school_key]).strip()


def enrich_mine(items, token, now, budget_s=MINE_DETAIL_BUDGET_S,
                clock=time.monotonic, fetch=school_detail.get_detail):
    """逐场补详情：总预算内能查几场查几场，失败只标记，不抛给调用方。"""
    deadline = clock() + budget_s
    for it in items:
        remaining = deadline - clock()
        if remaining <= 0:
            it["detail_unknown"] = True
            continue
        timeout = min(MINE_DETAIL_TIMEOUT_S, remaining)
        try:
            apply_detail(it, fetch(str(it.get("id") or ""), token, timeout))
        except school_detail.SchoolRequestError:
            it["detail_unknown"] = True
    return items


def not_ended(item, now):
    """结束时间已知就按结束判；未知时不隐藏——藏掉一场还在进行的活动更糟。"""
    end = mine_rules.parse_time(item.get("act_end"))
    return end is None or end > now


def prepare_mine(items, token, now, **kwargs):
    """我的报名：已报名、未结束、按举办时间排序，并尽量补上详情。"""
    signed = [it for it in items if it.get("signed")]
    enrich_mine(signed, token, now, **kwargs)
    alive = [it for it in signed if not_ended(it, now)]
    alive.sort(key=lambda it: mine_rules.parse_time(it.get("act_start")) or datetime.max)
    return alive


def render_pending(items, now, type_filter=""):
    title = "📋 待开放报名 %d 项" % len(items)
    if type_filter:
        title += "（%s）" % type_filter
    if not items:
        return title + "\n\n暂时没有这一类待开放的活动。"
    lines = [title, ""] + pending_lines(items, now, MAX_ITEMS)
    return trim(lines)


def render_open(items, now, type_filter=""):
    """公共查询的「报名已开放」列表（纯文本兜底）。

    只陈述学校事实：报名已经开放、可以自己去学校页面看。不承诺名额、
    不暗示机器人替你报名——名额与能否提交都由活动详情页说了算，
    这条文案唯一该做的是把开放与截止时间摊开。
    """
    title = "📋 报名已开放 %d 项" % len(items)
    if type_filter:
        title += "（%s）" % type_filter
    if not items:
        return title + "\n\n现在没有报名已开放的活动。"
    lines = [title, "", "报名已开放，可前往学校页面查看并报名：", ""]
    lines += open_lines(items, now, MAX_ITEMS)
    return trim(lines)


def render_mine(items, now):
    """纯文本兜底：与卡片同一套细节，取消按钮没有替代物，只能写清条件。"""
    title = "🎟 我的报名 %d 项" % len(items)
    if not items:
        return title + "\n\n你还没有报名任何活动。"
    lines = [title, "", "只列还没结束的场次：", ""]
    for it in items[:MAX_ITEMS]:
        span = mine_rules.span_text(it.get("act_start"), it.get("act_end")) or "时间待确认"
        lines.append("▸ " + span)
        lines.append("　" + it["name"])
        meta = [it.get("type") or "其他"]
        if it.get("place"):
            meta.append(str(it["place"]))
        lines.append("　" + "｜".join(meta))
        lines.append("　" + mine_detail_text(it, now, cancel_available(it, now)))
        lines.append("")
    return trim(lines)


def render_types(pending, open_now):
    counter = Counter([i["type"] for i in pending])
    counter_open = Counter([i["type"] for i in open_now])
    types = sorted(set(counter) | set(counter_open))
    lines = ["📚 现有活动类型", ""]
    for t in types:
        lines.append(f"· {t}　待开放 {counter.get(t, 0)} 项／报名中 {counter_open.get(t, 0)} 项")
    lines += ["", "想看某一类，就 @我 说类型名，比如「实践学习」。"]
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    view = "pending"
    type_filter = ""
    fmt = "text"
    if args and not args[0].startswith("--"):
        view = args[0]
    if "--type" in args:
        idx = args.index("--type")
        if idx + 1 < len(args):
            type_filter = args[idx + 1].strip()
    if "--format" in args:
        idx = args.index("--format")
        if idx + 1 < len(args):
            fmt = args[idx + 1].strip()

    session = load_session()
    token = (session.get("token") or "").strip()
    if not token:
        print("登录态失效了，需要重新登录。")
        return 2

    try:
        items = fetch_all(token)
    except PermissionError:
        print("登录态失效了，需要重新登录。")
        return 2
    except Exception as exc:
        print(f"抓取失败：{type(exc).__name__}")
        return 3

    cfg = load_config()["filter"]
    now = datetime.now()
    pending, open_now = classify(
        items, session.get("gender", ""),
        [w for w in cfg.get("keyword_blocklist", []) if w], now)
    mine = prepare_mine(items, token, now) if view in ("mine", "我的") else []

    if type_filter:
        pending = [i for i in pending
                   if type_filter in i["type"] or type_filter in i["name"]]
        open_now = [i for i in open_now
                    if type_filter in i["type"] or type_filter in i["name"]]

    if fmt == "card" and view not in ("types", "类型"):
        if view == "open":
            payload = open_card(open_now, now, type_filter)
        elif view == "all":
            payload = all_card(pending, open_now, now, type_filter)
        elif view in ("mine", "我的"):
            payload = mine_card(mine, now)
        elif view in ("menu", "菜单", "menu_p2p"):
            payload = menu_card(now, with_mine=(view == "menu_p2p"))
        else:
            payload = pending_card(pending, now, type_filter)
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    if view in ("types", "类型"):
        print(render_types(pending, open_now))
    elif view == "open":
        print(render_open(open_now, now, type_filter))
    elif view == "all":
        print(render_pending(pending, now, type_filter))
        print()
        print(render_open(open_now, now, type_filter))
    elif view in ("mine", "我的"):
        print(render_mine(mine, now))
    else:
        print(render_pending(pending, now, type_filter))
    return 0


if __name__ == "__main__":
    sys.exit(main())
