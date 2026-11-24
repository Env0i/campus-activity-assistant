# -*- coding: utf-8 -*-
"""报名目标选取编排：候选筛选、按序号或名称选取、已开放场次时刻替换与三条查目标路径。

从 grab.py 搬出，外部依赖（活动拉取、时钟、时间换算与筛选）在每次调用时经参数注入；
本模块不 import grab 或任何基础设施/根模块，也不持有全局状态。

@author Author
"""
from __future__ import annotations


def candidates(acts, now=None, *, default_now, still_relevant, parse_ts):
    """可抢的活动：未报名、有报名开始时间、还没截止；未开放的排最前。

    交互选择与 --pick/--name 非交互选择共用这一份顺序，保证序号一致。
    """
    now = now or default_now()
    cand = [a for a in acts
            if not a["signed"] and a["sign_start"] and still_relevant(a, now)]

    def rank(a):
        # 未开放的排最前（这才是要抢的），开放中的其次
        try:
            return 0 if now < parse_ts(a["sign_start"]) else 1
        except Exception:
            return 1

    cand.sort(key=lambda a: (rank(a), a["sign_start"]))
    return cand


def pick_activity(acts, now=None, *, candidates_fn):
    """交互式挑活动：只列未报名的，按报名开始时间排序。"""
    cand = candidates_fn(acts, now)
    if not cand:
        print("[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。")
        return None
    print("%-4s %-19s %-19s %s" % ("序号", "报名开始", "活动开始", "活动名"))
    for i, act in enumerate(cand, 1):
        print("%-4d %-19s %-19s %s" % (i, act["sign_start"], act["act_start"][:16], act["name"]))
    while True:
        raw = input("\n请输入序号（回车选 1，q 退出）：").strip().lower()
        if raw == "q":
            return None
        idx = 1 if raw == "" else (int(raw) if raw.isdigit() else -1)
        if 1 <= idx <= len(cand):
            return cand[idx - 1]
        print("输入的序号不对，请重试。")


def by_index_or_name(cand, args):
    """非交互挑活动：--pick 序号（与 list / 交互列表一致），或 --name 关键词。

    只在这一步命中一个活动才继续；命中多个就列出来让用户改用序号，避免猜错抢错。
    """
    pick = int(getattr(args, "pick", 0) or 0)
    kw = str(getattr(args, "name", "") or "").strip()
    if pick:
        if not 1 <= pick <= len(cand):
            print("[X] --pick %d 超出范围（当前有 %d 个可抢的活动）" % (pick, len(cand)))
            print("    运行 python grab.py list 查看序号。")
            return None
        return cand[pick - 1]
    if not kw:
        return None
    hits = [a for a in cand if kw.lower() in a["name"].lower()]
    if not hits:
        print("[X] 没有名称含「%s」的活动。" % kw)
        print("    运行 python grab.py list 查看当前可抢的活动。")
        return None
    if len(hits) > 1:
        print("[X] 「%s」匹配到 %d 个活动，请改用 --pick 序号：" % (kw, len(hits)))
        for i, a in enumerate(cand, 1):
            if a in hits:
                print("    %-3d %s  %s" % (i, a["sign_start"], a["name"]))
        return None
    return hits[0]


def at_or_now(at_text, *, parse_ts, business_now, school_time_text):
    """已开放的场次把 at 换成现在：重试窗口是「at + 120 秒」，
    开放超过 2 分钟的原时刻会让提交循环一次都不进、直接误报名额已满。"""
    if not at_text:
        return at_text
    try:
        ts = parse_ts(at_text)
    except Exception:
        return at_text
    if ts is not None and ts <= business_now():
        # 回写的「现在」必须按学校时区格式化：随后 parse_ts 会按 UTC+8 读回，
        # 用本机时区写会凭空产生 8 小时偏移；「现在」取业务北京时间
        return school_time_text(now_fn=business_now)
    return at_text


def resolve_target(args, budget=None, *, fetch_activities, candidates_fn,
                   by_index_or_name_fn, pick_activity_fn, at_or_now_fn):
    """确定 activity-id / 报名开始时间 / 活动名。"""
    acts = None
    act = None
    if args.activity_id:
        aid = args.activity_id
        if not args.at:
            act = next((a for a in (fetch_activities(budget) if acts is None else acts)
                        if a["id"] == aid), None)
            if not act or not act["sign_start"]:
                print("[X] 活动 %s 找不到报名开始时间，请显式传 --at" % aid)
                return None
            at = act["sign_start"]
        else:
            at = args.at
        name = args.name or (act["name"] if act else "活动")
        # original_at 保留学校原定开放时刻：已开放场次 at 会被换成现在，
        # 命令行输出要同时给出「原定开放」和「本次执行」两个时间
        return {"id": aid, "at": at_or_now_fn(at), "original_at": at, "name": name}

    try:
        acts = fetch_activities(budget)
    except PermissionError as exc:
        print("[X] 登录态已失效（%s），请先运行 python grab.py login" % exc)
        return None

    cand = candidates_fn(acts)
    if not cand:
        print("[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。")
        return None

    act = by_index_or_name_fn(cand, args)
    if act is None:
        if getattr(args, "pick", 0) or str(getattr(args, "name", "") or "").strip():
            return None            # 非交互模式选不出目标就直接结束，不再弹交互
        act = pick_activity_fn(acts)
    if not act:
        return None
    print("\n已选择：%s" % act["name"])
    print("报名开始：%s   活动时间：%s   地点：%s" %
          (act["sign_start"], act["act_start"], act["place"]))
    # 用 --pick/--name 指定时视为已确认（脚本/快捷方式调用不该再卡在输入上）
    if not (getattr(args, "pick", 0) or str(getattr(args, "name", "") or "").strip()):
        if input("确认到点自动报名？[y/N] ").strip().lower() not in ("y", "yes"):
            print("[i] 已取消。")
            return None
    return {"id": act["id"], "at": at_or_now_fn(act["sign_start"]),
            "original_at": act["sign_start"], "name": act["name"]}
