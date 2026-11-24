"""owner 私聊的「我的报名」与取消报名卡片。

和公共卡片共用同一个外壳与按钮编码，但内容口径不同：

- 签到签退只写「需要 / 无需 / 未知」三种说法。学校没说的一律写未知，
  不能替它说成「无需」，否则用户会按错误的时间去现场；
- 取消条件查不到就写未知，不写「可取消」，也不给按钮；
- 可取消的场次带「取消报名」按钮，点了先出确认卡，确认卡里再提交。

取消结果按四类展示：cancelled / refused / unknown / precheck_failed；
busy 只是「上一单还没跑完」，不是结果。

@author Author
"""
import mine_rules
from card import _btn_value, _card
from common import MAX_LIST_ITEMS, business_now, fmt_when


def _hm(text):
    """只取时分：签到签退与活动同一天，写全日期反而挤掉了时段。"""
    raw = str(text or "").strip()
    return raw[11:16] if len(raw) >= 16 else raw


def _sign_text(label, required, start, end):
    """一条签到或签退说明：要求未知不猜，有要求就带上时段。"""
    if required is False:
        return "无需" + label
    if required is None:
        return label + "要求未知"
    begin, finish = _hm(start), _hm(end)
    if begin and finish:
        window = "%s–%s" % (begin, finish)
    elif begin:
        window = "%s 起" % begin
    elif finish:
        window = "至 %s" % finish
    else:
        window = ""
    return (label + " " + window) if window else ("需要" + label)


def cancel_available(it, now):
    """这场现在点取消能不能通过前置核对。只决定按钮显不显示，不做权威判定。

    权威判定在取消脚本里重做一遍：卡片是几分钟前的快照，不能当放行凭据。
    """
    return mine_rules.cancel_precheck(
        now, True, it.get("cancel_allowed"), it.get("sign_start"),
        it.get("sign_end")) is None


def _cancel_text(it, now, can_cancel):
    if it.get("cancel_allowed") is False:
        return "报后不可退"
    if it.get("cancel_allowed") is None:
        return "取消条件未知"
    if can_cancel:
        return "可取消，%s 截止" % fmt_when(it.get("sign_end") or "", now)
    end = it.get("sign_end") or ""
    return ("已过取消截止 %s" % fmt_when(end, now)) if end else "取消条件未知"


def mine_detail_text(it, now, can_cancel):
    """卡片与纯文本兜底共用的一行细节：签到、签退、取消三件事。"""
    return "｜".join([
        _sign_text("签到", it.get("checkin_required"),
                   it.get("checkin_start"), it.get("checkin_end")),
        _sign_text("签退", it.get("checkout_required"),
                   it.get("checkout_start"), it.get("checkout_end")),
        _cancel_text(it, now, can_cancel),
    ])


def _mine_detail_md(it, now, can_cancel):
    span = mine_rules.span_text(it.get("act_start"), it.get("act_end")) or "时间待确认"
    lines = ["**▸ %s**" % span, it.get("name") or "活动"]
    meta = [it.get("type") or "其他"]
    if it.get("place"):
        meta.append(str(it["place"]))
    lines.append("｜".join(meta))
    lines.append(mine_detail_text(it, now, can_cancel))
    return "\n".join(lines)


def mine_card(items, now):
    """我的报名：每场展开时段、地点、签到签退，可取消的带取消按钮。

    查不到详情的场次照常列出并写「未知」，整张卡片不会因为一次查询失败而不发。
    """
    items = list(items or [])
    elements = []
    for idx, it in enumerate(items[:MAX_LIST_ITEMS]):
        if idx:
            elements.append({"tag": "hr"})
        can_cancel = cancel_available(it, now)
        elements.append({"tag": "div", "text": {"tag": "lark_md",
                        "content": _mine_detail_md(it, now, can_cancel)}})
        vid = str(it.get("id") or "")
        if not (vid and can_cancel):
            continue
        elements.append({"tag": "action", "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "取消报名"},
            "type": "danger",
            "value": "c:" + _btn_value({
                "i": vid,
                "n": it.get("name") or "",
                "s": it.get("act_start") or "",
                "e": it.get("act_end") or "",
                "p": it.get("place") or "",
            }),
        }]})
    if not items:
        elements = [{"tag": "div", "text": {"tag": "lark_md",
                     "content": "你还没有报名任何活动。"}}]
    footer = ["只列还没结束的场次"]
    if len(items) > MAX_LIST_ITEMS:
        footer.insert(0, "还有 %d 场没展开" % (len(items) - MAX_LIST_ITEMS))
    return _card("我的报名 %d 项" % len(items),
                 "更新于 %s" % now.strftime("%H:%M"), "green",
                 elements, footer)


# 取消结果四类；busy 是「上一单还没跑完」，不是结果。
CANCEL_KIND_TEXT = {
    "cancelled": ("已取消报名", "green", "学校记录里已经没有这场报名。"),
    "refused": ("学校没让取消", "red", ""),
    "unknown": ("取消结果待确认", "grey",
                "没能确认是否取消成功，稍后在「我的报名」里再看一眼。"),
    "precheck_failed": ("没有取消", "grey", ""),
}
CANCEL_REASON_TEXT = {
    "not_signed": "学校记录里这场已经不是已报名状态，不用再取消。",
    "not_allowed": "这场不允许取消报名。",
    "not_in_list": "没找到这场活动，先去「我的报名」里看一眼。",
    "window_closed": "已经过了报名截止时间，不能取消。",
    "clock_unavailable": "业务时间不可用，先不取消。",
    "login_expired": "登录态失效了，重新登录后再试。",
    "site_unconfigured": "还没配置学校站点，先不取消。",
    "unknown_state": "没查到这场的最新状态，先不取消。",
}


def cancel_confirm_card(activity, issued_ms, now=None):
    """取消确认卡：场次、时段、不可撤回提醒，外加签发时刻。

    签发时刻随按钮值回到机器人，超过 10 分钟的点击按过期处理。
    """
    now = now or business_now()
    it = activity or {}
    span = mine_rules.span_text(it.get("act_start"), it.get("act_end")) or "时间待确认"
    body = ["**%s**" % (it.get("name") or "活动"), span]
    if it.get("place"):
        body.append(str(it["place"]))
    warn = ("取消后名额可能马上被别人报走，**不能撤回**。\n"
            "确定要取消，就点下面的按钮；这张确认卡 10 分钟内有效。")
    elements = [
        {"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(body)}},
        {"tag": "hr"},
        {"tag": "div", "text": {"tag": "lark_md", "content": warn}},
        {"tag": "action", "actions": [
            {"tag": "button", "text": {"tag": "plain_text", "content": "确认取消报名"},
             "type": "danger",
             "value": "x:" + _btn_value({"i": str(it.get("id") or ""),
                                         "n": it.get("name") or "",
                                         "t": int(issued_ms)})},
            {"tag": "button", "text": {"tag": "plain_text", "content": "先不取消"},
             "type": "default", "value": "v:mine"},
        ]},
    ]
    return _card("确认取消报名？", "点确认后立即提交", "red", elements,
                 ["只对本人生效"])


def cancel_result_card(kind, name, message="", reason="", now=None):
    """取消结果卡：原地替换确认卡，四类结果各自一句人话。"""
    now = now or business_now()
    title, template, default = CANCEL_KIND_TEXT.get(
        kind, ("取消结果待确认", "grey", ""))
    body = ["**%s**" % (name or "活动")]
    text = CANCEL_REASON_TEXT.get(reason, "") if kind == "precheck_failed" else default
    if text:
        body.append(text)
    if kind == "refused" and message:
        body.append("学校原话：%s" % str(message)[:80])
    if kind == "unknown":
        body.append("要重新取消，就再点一次「取消报名」。")
    elements = [{"tag": "div", "text": {"tag": "lark_md",
                                        "content": "\n".join(body)}}]
    return _card(title, "更新于 %s" % now.strftime("%H:%M"), template, elements,
                 ["只对本人生效"])


def cancel_busy_card(name):
    """同一场正在取消时再点：不是失败，也不是结果，只是让用户等一下。"""
    return _card("正在处理", "上一单还没结束", "grey",
                 [{"tag": "div", "text": {"tag": "lark_md", "content":
                   "**%s**\n这场正在取消，稍等几秒再看「我的报名」。" % (name or "活动")}}],
                 ["只对本人生效"])
