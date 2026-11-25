# -*- coding: utf-8 -*-
"""活动查询适配器：列表分页、详情补全、报名状态只读核对。

从 grab.py 的「活动查询」段整体搬出（20261119 计划）：三态归一化、列表字段映射、
分页读取、详情缓存与四路并发补全、getInfo 签到/签退映射、getJoinInfo 判已报名。
规则与异常口径一字未改，本模块只负责实现。

依赖由调用方注入：学校请求函数（post / get）与学校时间解析（school_epoch）都是
参数，本层不 import grab 或 local 根目录模块。冻结 worker 仍从 grab.py 的静态
import 发现本模块。

详情缓存只有这一份 DETAIL_CACHE；grab.DETAIL_CACHE 引用的是同一对象，
所以 grab.DETAIL_CACHE.clear() 清的就是这里正在用的缓存。

@author Author
"""
from __future__ import annotations

import math
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor


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


def activity_flag(raw, names):
    """只读取明确的布尔字段别名；未命中时返回 None，等待真实接口字段确认。"""
    for name in names:
        if name in raw and raw.get(name) not in (None, ""):
            return tri_state(raw.get(name))
    return None


CHECKIN_FLAG_NAMES = (
    "checkin_required", "checkInRequired", "need_checkin", "needCheckIn",
    "isCheckInRequired", "sfdq", "sfqd", "qiandao", "签到",
)
CHECKOUT_FLAG_NAMES = (
    "checkout_required", "checkOutRequired", "need_checkout", "needCheckOut",
    "isCheckOutRequired", "sfqt", "sfqtd", "qiantui", "签退",
)

# 奖励字段：学校 getInfo 同时给参与人（cyr*）与组织者（zzr*）两套，
# 本人是参与者，优先 cyr*；组织者那套只是兜底（有些活动只填一处）。
# 列表接口没有这两项，所以奖励只能是「详情回来之后」才有的字段。
POINTS_NAMES = ("points", "cyrysjfs", "zzrysjfs")
WAGE_NAMES = ("wage", "cyryxngz", "zzryxngz")

# 时间字段别名：列表接口目前全为 null，详情接口才给出真实时间段。
# 名字按「内部字段 → 学校字段」排列，列表若已有同等信息则优先使用。
CHECKIN_START_NAMES = ("checkin_start", "qdkssj", "checkinStart")
CHECKIN_END_NAMES = ("checkin_end", "qdjssj", "checkinEnd")
CHECKOUT_START_NAMES = ("checkout_start", "qtkssj", "checkoutStart")
CHECKOUT_END_NAMES = ("checkout_end", "qtjssj", "checkoutEnd")

# 详情按活动 id 去重缓存：一次列表刷新只查一次，重复刷新直接复用；
# 并发上限 4，避免把学校接口和本机连接数打满。
DETAIL_CACHE: dict[str, dict] = {}
DETAIL_CACHE_LOCK = threading.Lock()
DETAIL_CONCURRENCY = 4
DETAIL_TIMEOUT_S = 12.0


def activity_time(raw, names, school_epoch):
    """读取学校时间文本；非法或缺失返回空串（不猜、不补当前时间）。"""
    for name in names:
        if name in raw and raw.get(name) not in (None, ""):
            text = str(raw.get(name)).strip()
            return text if school_epoch(text) is not None else ""
    return ""


def reward_number(data, names):
    """读奖励数值：缺失、认不出、负数一律 None（界面写「未公布」，不猜成 0）。

    学校给 0 是真实回答（这场没有虚拟工资），必须原样保留，不能当缺失吞掉。
    """
    for name in names:
        if name not in data or data.get(name) in (None, ""):
            continue
        try:
            value = float(data.get(name))
        except (TypeError, ValueError):
            continue
        if math.isnan(value) or math.isinf(value) or value < 0:
            continue
        return value
    return None


def detail_fields(raw):
    """详情响应可能直接是 data，也可能包一层 {code,data}；两种都接受。"""
    if not isinstance(raw, dict):
        return {}
    data = raw.get("data")
    return data if isinstance(data, dict) else raw


def _clean_text(value):
    """纯文本字段清洗：非字符串或缺省一律归一化为空串。"""
    return value.strip() if isinstance(value, str) else ""


def _non_negative_int(value):
    """面向范围代码：仅接受非负整数（或纯整数数字串），其余返回 None。"""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def parse_attendance_detail(raw, school_epoch):
    """把 getInfo 的签到/签退、退报与简介字段归一化；未知保持 None。

    真实字段：sfxyqd/qdkssj/qdjssj（签到）、sfxyqt/qtkssj/qtjssj（签退）、
    hdms（简介）、mxfw（面向范围文字）、hdmxfw（面向范围代码）。
    标记明确时优先；标记缺失但时间段存在才推导 true；两者都缺失 → None。
    """
    data = detail_fields(raw)
    flag_in = tri_state(data.get("sfxyqd")) if "sfxyqd" in data else None
    flag_out = tri_state(data.get("sfxyqt")) if "sfxyqt" in data else None
    in_start = activity_time(data, CHECKIN_START_NAMES, school_epoch)
    in_end = activity_time(data, CHECKIN_END_NAMES, school_epoch)
    out_start = activity_time(data, CHECKOUT_START_NAMES, school_epoch)
    out_end = activity_time(data, CHECKOUT_END_NAMES, school_epoch)
    if flag_in is None and (in_start or in_end):
        flag_in = True
    if flag_out is None and (out_start or out_end):
        flag_out = True
    if flag_in is False:
        # 明确无需签到：时间段一并清空，避免界面出现「无需签到 19:00」
        in_start = in_end = ""
    if flag_out is False:
        out_start = out_end = ""
    return {
        "checkin_required": flag_in,
        "checkin_start": in_start,
        "checkin_end": in_end,
        "checkout_required": flag_out,
        "checkout_start": out_start,
        "checkout_end": out_end,
        # R2（计划 20261107-conflict-cancel）：qxbm（报名后允许取消）与 sfkybm
        # （学校前端判「时间冲突」的开关）逐键映射成三态；缺失或认不出一律 None，
        # 绝不猜成允许 / 不允许。can_sign 只映射不展示（学校前端分析 9.4：学校
        # 不写冲突原因）；cancel_allowed 是取消报名的前置条件之一（分析 11.1）。
        "cancel_allowed": tri_state(data.get("qxbm")) if "qxbm" in data else None,
        "can_sign": tri_state(data.get("sfkybm")) if "sfkybm" in data else None,
        # 奖励（实践分 / 虚拟工资）：与签到信息同一次 getInfo 请求，参与人字段优先。
        # 给 0 就存 0（真实回答），给不出就 None（界面写「未公布」）。
        "points": reward_number(data, POINTS_NAMES),
        "wage": reward_number(data, WAGE_NAMES),
        "description": _clean_text(data.get("hdms")),
        "audience": _clean_text(data.get("mxfw")),
        "audience_code": _non_negative_int(data.get("hdmxfw")),
    }


def fetch_activity_detail(activity_id, get, school_epoch, timeout=DETAIL_TIMEOUT_S):
    """只读详情；失败返回 None（调用方显示「同步中」，不把失败当成无需）。

    详情成功才写缓存；缓存命中返回副本，调用方改结果不会污染缓存。
    get 与 school_epoch 由调用方注入，测试替换 grab._get 仍然生效。
    """
    aid = str(activity_id or "").strip()
    if not aid:
        return None
    with DETAIL_CACHE_LOCK:
        cached = DETAIL_CACHE.get(aid)
    if cached is not None:
        return dict(cached)
    data = get("/rjyHd/getInfo/" + urllib.parse.quote(aid, safe=""), timeout=timeout)
    if not isinstance(data, dict) or str(data.get("code")) not in {"1", "1.0"}:
        return None
    parsed = parse_attendance_detail(data, school_epoch)
    with DETAIL_CACHE_LOCK:
        DETAIL_CACHE[aid] = parsed
    return dict(parsed)


def apply_attendance(item, detail):
    """列表字段优先、详情补充；详情失败保留 pending 状态供下次刷新重试。"""
    list_has = any(item.get(key) not in (None, "")
                   for key in ("checkin_required", "checkout_required",
                               "checkin_start", "checkout_start"))
    if detail is None:
        # R2：详情没拿到就是「不知道」，两键置 None（界面据此不写「报后可退」）
        item["cancel_allowed"] = None
        item["can_sign"] = None
        item.setdefault("checkin_start", "")
        item.setdefault("checkin_end", "")
        item.setdefault("checkout_start", "")
        item.setdefault("checkout_end", "")
        item["attendance_source"] = "list" if list_has else "none"
        item["attendance_state"] = "pending"
        item["attendance_error"] = "detail_unavailable"
        # 奖励只在详情里：没拿到详情就是「同步中」，不能写「分未公布」
        item["points"] = None
        item["wage"] = None
        item["reward_state"] = "pending"
        item["description"] = None
        item["audience"] = None
        item["audience_code"] = None
        return item
    for key, value in detail.items():
        if key in ("description", "audience", "audience_code", "points", "wage"):
            continue
        if key in ("checkin_required", "checkout_required",
                   "cancel_allowed", "can_sign"):
            # 三态键：只有 None 才让位给详情；False 是明确回答，不能被「真值判断」吞掉
            if item.get(key) is None:
                item[key] = value
        elif not item.get(key):
            item[key] = value
    # R2：列表没有这两个键，详情（或测试替身）也可能没给——补成 None，输出形状固定
    item.setdefault("cancel_allowed", None)
    item.setdefault("can_sign", None)
    item["attendance_source"] = "list" if list_has else "detail"
    item["attendance_state"] = "ready"
    # 奖励以这次详情为准：详情里没有这两项，就是学校尚未公布（None），
    # 不能沿用上一轮的值——活动可能改了奖励（简介/面向范围同理，保留 0 与空串不被假值吞掉）。
    item["points"] = detail.get("points")
    item["wage"] = detail.get("wage")
    item["reward_state"] = "ready"
    item["description"] = detail.get("description")
    item["audience"] = detail.get("audience")
    item["audience_code"] = detail.get("audience_code")
    item.pop("attendance_error", None)
    return item


def enrich_attendance_items(items, read_detail, max_workers=DETAIL_CONCURRENCY):
    """按活动 id 去重并发补详情；单场失败不影响整张列表。

    read_detail 由调用方传入当前的详情读取函数（grab 传自己的
    fetch_activity_detail），测试替换它仍然生效。
    """
    rows = list(items or [])
    ids = []
    seen = set()
    for item in rows:
        aid = str(item.get("id") or "")
        if aid and aid not in seen:
            seen.add(aid)
            ids.append(aid)
    if not ids:
        return rows
    results: dict[str, dict | None] = {}
    try:
        with ThreadPoolExecutor(max_workers=max(1, int(max_workers))) as pool:
            for aid, detail in zip(ids, pool.map(read_detail, ids)):
                results[aid] = detail
    except Exception:
        # 线程池不可用：全部按「同步中」处理，列表本身仍然可用
        results = {}
    for item in rows:
        apply_attendance(item, results.get(str(item.get("id") or "")))
    return rows


def map_activity(raw, school_epoch):
    """学校列表接口的一条活动 → 本地字段结构（纯映射，不发请求、不读全局状态）。

    字段名换成好读的名字；规则与顺序跟原来写在 fetch_activities 循环里的一字不差，
    契约测试用 contracts/school-api/list-activity.*.json 逐键比对。
    """
    return {
        "id": raw.get("id", ""),
        "name": (raw.get("hdmc") or "").strip(),
        "type": raw.get("hdlx") or "其他",
        "place": raw.get("hddd") or "",
        "sign_start": raw.get("bmkssj") or "",
        "sign_end": raw.get("bmjssj") or "",
        "act_start": raw.get("hdkssj") or "",
        "act_end": raw.get("hdjssj") or "",
        "signed": raw.get("bmzt") == 1,
        "checkin_required": activity_flag(raw, CHECKIN_FLAG_NAMES),
        "checkout_required": activity_flag(raw, CHECKOUT_FLAG_NAMES),
        # 列表若已带回时间段就直接用；没有则留空，等详情补充
        "checkin_start": activity_time(raw, CHECKIN_START_NAMES, school_epoch),
        "checkin_end": activity_time(raw, CHECKIN_END_NAMES, school_epoch),
        "checkout_start": activity_time(raw, CHECKOUT_START_NAMES, school_epoch),
        "checkout_end": activity_time(raw, CHECKOUT_END_NAMES, school_epoch),
        "attendance_source": "list",
        "attendance_state": "unknown",
    }


def fetch_activities(post, page_size, school_epoch, budget=None):
    """分页拉活动列表；返回本地字段结构（字段名已换成好读的名字）。

    post、page_size 与 school_epoch 由调用方注入（grab 传 grab._post、PAGE_SIZE
    与 grab.school_epoch）；页数上限 30，登录失效抛 PermissionError，
    业务失败抛 RuntimeError。
    """
    out, page, total = [], 1, None
    while page <= 30:
        data = post("/rjyHd/listActivity",
                    {"pageSize": page_size, "pageNum": page, "hdmc": "",
                     "hdzt": None, "kssj": "", "jssj": ""}, budget=budget)
        if data.get("code") == 4001:
            raise PermissionError(data.get("message") or "身份验证失败")
        if data.get("code") != 1:
            raise RuntimeError("接口异常：%s" % (data.get("message") or data.get("code")))
        block = data.get("data") or {}
        total = int(block.get("count") or 0)
        chunk = block.get("list") or []
        for raw in chunk:
            if not raw.get("hdmc"):
                continue
            out.append(map_activity(raw, school_epoch))
        if not chunk or len(out) >= total:
            break
        page += 1
    return out


def join_state(payload):
    """getJoinInfo 的 data → 是否已报名（与学校前端同口径）。

    出处：school-frontend-analysis.md 9.2/9.3/9.8（学校前端静态分析）：
    - data 为 null（顺带容忍空对象/空数组）：从没报过 → 未报名；
    - sfcx（是否撤销）为 1：学校把「已撤销」当成可以再报，列表里也退回可报名 →
      未报名。只判 data 非空会把撤销过的活动永远钉在「已报名」；
    - sfbm（是否报名）明确为假：学校自己说没报上 → 未报名；
    - 其余（含缺 sfbm 字段、形状认不出）：按已报名处理。宁可漏报一次，
      也不要因为读不懂回包就再提交一遍，把「结果未知」变成重复报名。
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


def is_joined(act_id, post, budget=None):
    """getJoinInfo：未报名时 data 为 null，报名后 data 是对象。

    实测形状（2026-11-03）：未报名 {"code": 1, "message": "操作成功！", "data": null}；
    已报名 data 带 sfbm=1（是否报名）、bmsj（报名时间）、qdzt/qtzt（签到/签退状态）等。
    报名后又撤销的 data 不回到 null，而是留在对象里并带 sfcx=1，所以判据交给
    join_state()（见那里的三条口径与出处）。

    传入 budget 时返回三态：True 已报名 / False 确认未报名 / None 查询没成功。
    最后一种绝不能被当成「未报名」——把它当未报名会再发一次提交，
    把「结果未知」变成真正的重复报名。
    """
    if budget is not None and budget.expired():
        return None
    data = post("/rjyHdCyr/getJoinInfo/" + act_id, {},
                timeout=None if budget is None else budget.timeout_s(15))
    if not isinstance(data, dict) or data.get("code") != 1:
        return False if budget is None else None
    return join_state(data.get("data"))
