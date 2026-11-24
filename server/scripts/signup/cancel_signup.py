"""私聊取消报名：前置四条、单次请求、复查为准，一行 JSON 交给机器人。

取消不可撤回，所以每次点击都在服务器上重新核对，卡片只是入口不是凭据：

- 前置四条（确实已报名、学校允许取消、业务北京时间在报名窗口内、业务时钟可用）
  任一不满足或查不到，**一个请求都不发**；
- 学校的 cancel 接口只调一次，绝不重试；
- 成败只看随后 getJoinInfo 的复查：没报名了才是已取消，仍是已报名就是学校拒绝；
- 同一场用文件锁单飞，正在处理时再点只回「正在处理」；
- 取消成功且这场在预报名清单里，一并移出，免得 runner 到点又去报名。

子命令（stdout 都只有一行 JSON）：
    python3 scripts/signup/cancel_signup.py confirm --id <活动id> --name <名称>
    python3 scripts/signup/cancel_signup.py run --id <活动id> --name <名称>

@author Author
"""
import argparse
import hashlib
import json
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
for _sub in ("lib", "signup"):
    _p = str(ROOT / "scripts" / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mine_rules as rules                                     # noqa: E402
import school_detail                                           # noqa: E402
import watchlist                                               # noqa: E402
from mine_cards import (cancel_busy_card, cancel_confirm_card,  # noqa: E402
                         cancel_result_card)
from common import DATA, business_now, try_file_lock            # noqa: E402

JOIN_TIMEOUT_S = 15.0
DETAIL_TIMEOUT_S = 12.0
CANCEL_TIMEOUT_S = 15.0
RECHECK_TIMEOUT_S = 10.0      # 取消之后复查单独给一份：前面再慢也要查得到
MESSAGE_MAX = 80
LOCK_DIR = DATA


def school_message(value):
    """学校原话 → 能直接给界面看的一句话：去控制字符、首尾空白、截 80 字。"""
    text = "".join(ch for ch in str(value if value is not None else "")
                   if unicodedata.category(ch)[0] != "C")
    return text.strip()[:MESSAGE_MAX]


def lock_path(activity_id):
    """同一场一把锁：按活动 id 取哈希，避免 id 里的字符跑进文件名。"""
    digest = hashlib.sha1(str(activity_id or "").encode("utf-8")).hexdigest()[:12]
    return Path(LOCK_DIR) / (".cancel-%s.lock" % digest)


def _result(kind, name, message="", reason="", removed=False):
    """结果字典：卡片随回调返回，客户端当场替换确认卡。"""
    if kind == "busy":
        card = cancel_busy_card(name)
    else:
        card = cancel_result_card(kind, name, message=message, reason=reason)
    out = {"kind": kind, "ok": kind == "cancelled", "card": card}
    if message:
        out["message"] = message
    if reason:
        out["reason"] = reason
    if removed:
        out["removed_from_watchlist"] = True
    return out


def _load_state(activity_id, token, join=school_detail.get_join_info,
                detail=school_detail.get_detail):
    """查「是否已报名」与详情；两者互不拖累，各失败各的按未知处理。"""
    joined, expired = None, False
    try:
        response = join(activity_id, token, JOIN_TIMEOUT_S)
        expired = str(response.get("code")) in {"4001", "4001.0"}
        joined = rules.joined_from_response(response)
    except school_detail.SchoolRequestError:
        joined = None
    facts = None
    try:
        response = detail(activity_id, token, DETAIL_TIMEOUT_S)
        if str(response.get("code")) in {"1", "1.0"}:
            facts = rules.parse_attendance(response)
    except school_detail.SchoolRequestError:
        facts = None
    return joined, facts, expired


def precheck_reason(now, joined, facts, expired=False):
    """前置四条的原因码；None 表示可以调取消接口。"""
    if expired and facts is None:
        return "login_expired"
    if facts is None:
        return "unknown_state"
    return rules.cancel_precheck(now, joined, facts.get("cancel_allowed"),
                                 facts.get("sign_start"), facts.get("sign_end"))


def _drop_from_watchlist(activity_id, remove):
    """取消成功后同步移出预报名清单；清单读坏不拖累取消结果。"""
    try:
        return bool(remove(activity_id))
    except (ValueError, RuntimeError):
        return False


def _send_and_recheck(activity_id, name, token, join=school_detail.get_join_info,
                      cancel=school_detail.cancel_signup,
                      remove=watchlist.remove):
    """取消接口只调一次；成败只看复查，学校回包只给「拒绝」配一句原话。"""
    reply = None
    try:
        reply = cancel(activity_id, token, CANCEL_TIMEOUT_S)
    except school_detail.SchoolRequestError:
        reply = None
    after = None
    try:
        after = rules.joined_from_response(join(activity_id, token, RECHECK_TIMEOUT_S))
    except school_detail.SchoolRequestError:
        after = None
    if after is False:
        return _result("cancelled", name,
                       removed=_drop_from_watchlist(activity_id, remove))
    if after is True:
        message = school_message(reply.get("message")) if isinstance(reply, dict) else ""
        return _result("refused", name, message=message)
    return _result("unknown", name)


def run_cancel(activity_id, name, token, now=None, join=school_detail.get_join_info,
               detail=school_detail.get_detail,
               cancel=school_detail.cancel_signup, remove=watchlist.remove):
    """一次完整的私聊取消；不打印、不读 argv，返回给机器人一行结果的字典。"""
    activity_id = str(activity_id or "").strip()
    name = str(name or "").strip() or "活动"
    if not activity_id:
        return _result("precheck_failed", name, reason="not_in_list")
    if not str(token or "").strip():
        return _result("precheck_failed", name, reason="login_expired")
    now = now or business_now()
    with try_file_lock(lock_path(activity_id)) as acquired:
        if not acquired:
            return _result("busy", name)
        joined, facts, expired = _load_state(activity_id, token, join, detail)
        reason = precheck_reason(now, joined, facts, expired)
        if reason:
            return _result("precheck_failed", name, reason=reason)
        return _send_and_recheck(activity_id, name, token, join, cancel, remove)


def confirm_card(activity_id, name, token):
    """确认卡要场次时段：详情查不到就给「时间待确认」，不阻止用户确认。"""
    activity = {"id": activity_id, "name": str(name or "").strip() or "活动"}
    try:
        response = school_detail.get_detail(activity_id, token, DETAIL_TIMEOUT_S)
        data = rules.detail_fields(response)
        if str(response.get("code")) in {"1", "1.0"} and data:
            activity["act_start"] = str(data.get("hdkssj") or "")
            activity["act_end"] = str(data.get("hdjssj") or "")
            activity["place"] = str(data.get("hddd") or "")
    except school_detail.SchoolRequestError:
        pass
    return cancel_confirm_card(activity, int(time.time() * 1000))


def main(argv=None):
    parser = argparse.ArgumentParser(description="私聊取消报名")
    parser.add_argument("cmd", choices=("confirm", "run"))
    parser.add_argument("--id", default="")
    parser.add_argument("--name", default="")
    args = parser.parse_args(argv)
    token = school_detail.session_token()
    if args.cmd == "confirm":
        print(json.dumps(confirm_card(args.id, args.name, token), ensure_ascii=False))
        return 0
    result = run_cancel(args.id, args.name, token)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
