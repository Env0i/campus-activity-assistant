# -*- coding: utf-8 -*-
"""worker 列表命令：登录探测、列表查询、时间选择、筛选排序、详情与输出。

从 grab.py 的 cmd_list 整条用例搬出（20261119 计划）：计时起点、先判登录态、
校时不可用时只认本次回包的 Date 头、先筛后补详情、JSON 键顺序、纯文本表头和
[timing] 诊断都保持原样，文案与退出码一字未改。

依赖全部由调用方在调用时注入（登录探测、列表与详情读取、业务时钟与学校 Date、
时间解析与原异常类型、输出改道与计时日志边界）；本模块不 import grab 或 local
根目录模块，也不持有任何全局状态。

@author Author
"""
from __future__ import annotations

import json
import math


def _still_relevant(act, now, parse_ts):
    """报名还没截止（或没给截止时间）的活动才算「还值得看」。"""
    if not act.get("sign_end"):
        return True
    try:
        return parse_ts(act["sign_end"]) >= now - 3600
    except Exception:
        return True


def still_relevant(act, now=None, *, parse_ts, default_now):
    """报名还没截止（或没给截止时间）的活动才算「还值得看」。"""
    return _still_relevant(act, now or default_now(), parse_ts)


def keep_in_list(act, now, *, parse_ts):
    """列表默认保留谁（R1，计划 20261107-conflict-cancel）。

    still_relevant 为真照旧保留；另外「已报名、举办还没结束」的活动即使报名早已截止
    也保留——否则它在列表里消失，界面的冲突与禁选基线、后端 signed_baseline 都看不见
    这场已占用的举办时段，用户只能等学校拒绝才发现冲突。
    act_end 缺失或解析不了的已报名活动仍按原规则筛：补回它们会让界面「已报名活动
    时间待确认」的保守规则挡住所有勾选。举办恰在 now 结束算没结束（不早于 now）。
    """
    if _still_relevant(act, now, parse_ts):
        return True
    if not act.get("signed"):
        return False
    try:
        return parse_ts(act.get("act_end")) >= now
    except Exception:
        return False


def sign_state(act, now=None, *, parse_ts, default_now):
    """开放状态文案：未开放给剩余时长，截止后写明已截止；时间缺失按未知处理。"""
    now = now or default_now()
    try:
        start = parse_ts(act["sign_start"])
    except Exception:
        return "时间未知"
    try:
        end = parse_ts(act["sign_end"])
    except Exception:
        end = None
    if now < start:
        left = int(start - now)
        return "未开放（%d 小时 %d 分后）" % (left // 3600, left % 3600 // 60)
    if end and now > end:
        return "报名已截止"
    return "开放中"


def _probe_login(check_token, stdout_to_stderr, json_mode, perf_counter):
    """先判登录态：直接拉列表失败只会得到一句「接口异常：HTTPError」，
    图形界面里的用户看不出是没登录还是网络问题。"""
    with stdout_to_stderr(json_mode):
        t0 = perf_counter()
        ok, msg = check_token()
        token_s = perf_counter() - t0
    return ok, msg, token_s


def _load_activities(fetch_activities, clear_school_date, stdout_to_stderr,
                     json_mode, perf_counter):
    """只拉列表不发详情：学校返回全部历史活动，详情等筛完再补（见 enrich 处）。"""
    with stdout_to_stderr(json_mode):
        t0 = perf_counter()
        # L2：先清上一轮的 Date 记录，只认本次列表回包的 Date 头
        clear_school_date()
        acts = fetch_activities()
        pages_s = perf_counter() - t0
    return acts, pages_s


def _filter_time(business_now, school_date_now, clock_unavailable, log,
                 stdout_to_stderr, json_mode):
    """筛选时刻：业务北京时间优先；不可用时只用本次回包的学校 Date 头。

    返回 (now, filter_now, filter_time_source)：now 只供开放状态文案，filter_now
    只供筛选与排序，两者不得混用——Date 头不冒充业务时钟，也不进报名开放判定。
    """
    try:
        now = business_now()          # 列表筛选按业务北京时间
        return now, now, "clock"
    except clock_unavailable:
        # 校时不可用仍可完成原始数据读取：不按系统时钟筛选/排行，
        # 状态与距开放一律显示未知，绝不把本机日期当北京时间。
        now = None
        # L2：退而使用本次列表回包的 HTTP Date 头（学校服务器时刻），
        # 只用于筛选与排序，不冒充业务时钟，也不进报名开放判定。
        filter_now = school_date_now()
        source = "school_date" if filter_now is not None else "none"
        with stdout_to_stderr(json_mode):
            if filter_now is None:
                log("[!] 北京时间暂不可用，回包也没有可用的 Date 头："
                    "本次保留全部活动，开放状态显示未知。")
            else:
                log("[!] 北京时间暂不可用：已按学校服务器时间筛选要显示的活动。")
        return now, filter_now, source


def _select_rows(acts, all_rows, filter_now, *, keep_in_list, parse_ts):
    """默认只看报名还没截止的；R1 补回已报名且举办没结束的；--all 与时间全缺时保留全部。"""
    if all_rows or filter_now is None:
        rows = list(acts)
    else:
        rows = [a for a in acts if keep_in_list(a, filter_now)]

    def rank(a):
        # 未开放的排最前，其次开放中，已报名的垫底；时间未知时全部同档
        if a["signed"]:
            return 2
        if filter_now is None:
            return 1
        try:
            return 0 if filter_now < parse_ts(a["sign_start"]) else 1
        except Exception:
            return 1

    rows.sort(key=lambda a: (rank(a), a["sign_start"] or "9999", a["name"]))
    return rows


def _emit_timing(note, perf_counter, page_size, t_start, token_s, pages_s,
                 acts, details_n, details_s, filter_time_source):
    """运行记录里的列表用时分段只作诊断：任何异常都不能影响列表输出与退出码。"""
    try:
        total_s = perf_counter() - t_start
        pages = max(1, math.ceil(len(acts) / page_size))
        note("[timing] list token_s=%.2f pages=%d pages_s=%.2f "
             "details=%d details_s=%.2f total_s=%.2f "
             "filter_time_source=%s"
             % (token_s, pages, pages_s, details_n, details_s,
                total_s, filter_time_source))
    except Exception:
        pass


def _json_rows(rows, now, sign_state):
    """给图形界面用：字段固定，界面拿 id 直接把目标钉死，不靠序号对齐。"""
    out = []
    for i, act in enumerate(rows, 1):
        out.append({
            "index": i,
            "id": act["id"],
            "name": act["name"],
            "sign_start": act["sign_start"],
            "sign_end": act["sign_end"],
            "act_start": act["act_start"],
            "act_end": act["act_end"],
            "place": act["place"],
            "signed": bool(act["signed"]),
            "checkin_required": act.get("checkin_required"),
            "checkout_required": act.get("checkout_required"),
            # 真实时间段与来源：界面据此显示「签到 19:00–19:40」或「同步中」
            "checkin_start": act.get("checkin_start") or "",
            "checkin_end": act.get("checkin_end") or "",
            "checkout_start": act.get("checkout_start") or "",
            "checkout_end": act.get("checkout_end") or "",
            "attendance_source": act.get("attendance_source") or "none",
            "attendance_state": act.get("attendance_state") or "unknown",
            # R2：三态，详情失败或字段缺失为 None；can_sign 只透传不展示
            "cancel_allowed": act.get("cancel_allowed"),
            "can_sign": act.get("can_sign"),
            # 奖励（决策口径见 design/prototype/workbench-2026-11 Main/Phone 的 rw）：
            # pending 是「详情还没回来」，ready 时 points/wage 为 None 才是「未公布」
            "points": act.get("points"),
            "wage": act.get("wage"),
            "reward_state": act.get("reward_state") or "pending",
            "state": "已报名" if act["signed"]
                     else ("待确认" if now is None else sign_state(act, now)),
        })
    return out


def _print_text_rows(rows, now, sign_state):
    """纯文本列表只给人看活动名与状态，照旧不为每场发详情请求。"""
    print("%3s  %s  %s  %s" % ("#", "报名开始", "状态", "活动名"))
    for i, act in enumerate(rows, 1):
        flag = "已报名" if act["signed"] else (
            "待确认" if now is None else sign_state(act, now))
        print("%3d  %s  %s  %s" % (i, act["sign_start"] or "-", flag, act["name"]))
    print("\n提示：双击 2-抢活动.bat 可直接选择并到点抢；也可以双击 4-图形界面.bat 用鼠标点。")


def run_list(args, *, check_token, fetch_activities, enrich, business_now,
             clear_school_date, school_date_now, clock_unavailable, log,
             stdout_to_stderr, note, perf_counter, page_size, parse_ts,
             keep_in_list, sign_state):
    """跑一条 list 命令，返回进程退出码（登录或拉取失败为 2，其余为 0）。

    args 只读 all 与 json 两项，其余边界全是调用时注入的当前函数。
    """
    json_mode = bool(getattr(args, "json", False))
    # 计时起点放函数最前：[timing] 的 total_s 要覆盖登录探测到打印 JSON 全程
    t_start = perf_counter() if json_mode else 0.0

    ok, msg, token_s = _probe_login(check_token, stdout_to_stderr, json_mode,
                                    perf_counter)
    if not ok:
        print("[X] %s" % msg)
        print("    请先运行：python grab.py login（或点界面上的「登录」）")
        return 2
    try:
        acts, pages_s = _load_activities(fetch_activities, clear_school_date,
                                         stdout_to_stderr, json_mode, perf_counter)
    except PermissionError as exc:
        print("[X] 登录态已失效（%s），请先运行 python grab.py login" % exc)
        return 2
    except Exception as exc:
        print("[X] 拉取活动失败：%s" % exc)
        return 2

    now, filter_now, filter_time_source = _filter_time(
        business_now, school_date_now, clock_unavailable, log,
        stdout_to_stderr, json_mode)
    rows = _select_rows(acts, args.all, filter_now,
                        keep_in_list=keep_in_list, parse_ts=parse_ts)

    def emit_timing(details_n, details_s):
        _emit_timing(note, perf_counter, page_size, t_start, token_s, pages_s,
                     acts, details_n, details_s, filter_time_source)

    if not rows:
        if json_mode:
            print("[]")
            emit_timing(0, 0.0)
            return 0
        print("[i] 近期没有可报名的活动（还没公布报名时间，或都已截止/已报名）。")
        print("    想连历史活动一起看：python grab.py list --all")
        return 0

    if json_mode:
        # 详情只补要显示的这些：--all 或三种时间都拿不到时 rows 就是全部活动，
        # 仍全补——分不出谁已截止，宁可慢也不按本机时钟猜。
        t0 = perf_counter()
        with stdout_to_stderr(json_mode):
            rows = enrich(rows)
        details_s = perf_counter() - t0
        print(json.dumps(_json_rows(rows, now, sign_state), ensure_ascii=False))
        emit_timing(len(rows), details_s)
        return 0

    _print_text_rows(rows, now, sign_state)
    return 0
