# -*- coding: utf-8 -*-
"""演示数据（--demo）：固定样例集，时间按给定 now 偏移，供离线视觉演示。

纯函数：now（此刻值）由调用方传入（app 外观取本机时刻后传入），样例时间格式化
函数（time_text_of）由 composition root 注入——domain 不直接依赖 time_contract。
样例字段与 grab.py list --json 的缺失形态一致。

@author Author
"""
from __future__ import annotations


def demo_items(now: float, time_text_of) -> list[dict]:
    """time_text_of：epoch 秒 → 学校时间文本（app.py 注入 school_time_text）。"""
    raw = [
        # lab 与 career 报名同时开放，但举办时段重叠；workshop 同批开放却不重叠。
        ("demo-security", "网络安全·数字时代大长城", "实践学习", "教学 A301", -3, 3600, 7200, 10800, False),
        ("demo-face", "我与学生面对面（校园信息化发展之路）", "讲座", "报告厅", -7200, 7200, -3600, 1800, True),
        ("demo-lab", "程序设计实验室开放日", "实践学习", "实训楼 B204", 1800, 5400, 7200, 10800, False),
        ("demo-career", "简历门诊：一对一改简历", "就业指导", "线上", 1800, 5400, 9000, 12600, False),
        ("demo-workshop", "创新作品夜场导览", "创新实践", "创新中心展厅", 1800, 5400, 14400, 16200, False),
        ("demo-volunteer", "图书馆志愿服务（第 12 期）", "志愿服务", "图书馆一层", 86400, 90000, 172800, 176400, False),
        # 活动举办时间缺失：演示「不能静默加入计划」的校验边界（act 两项传 None）
        ("demo-exhibit", "宿舍文化节摄影征集", "文化活动", "线上", 90000, 93600, None, None, False),
        # 冲突与取消（计划 20261107-conflict-cancel，R1/R2）。偏移以天计，跨天靠时长保证：
        # 宿舍查寝已报名、跨三个日历日（举办 +3d8h20m 起，持续 2d0h40m），报名窗口还没关
        # （截止在 +2d23h40m，cancel_allowed=true，可取消）；模拟面试未报名，举办时段落在
        # 它里面，演示「与已报名重叠 → 不可加入」；职业规划讲座报后不可退；
        # 社区志愿服务日报后可退，两者都不与已报名的重叠。
        ("demo-dorm", "宿舍查寝", "生活服务", "学生公寓", -432000, 258000, 289200, 464400, True),
        ("demo-interview", "模拟面试", "就业指导", "就业指导中心", -3600, 172800, 322800, 344400, False),
        ("demo-nocancel", "职业规划讲座", "讲座", "报告厅", -1800, 10800, 18000, 21600, False),
        ("demo-community", "社区志愿服务日", "志愿服务", "社区服务站", -900, 43200, 108000, 115200, False),
    ]
    flags = {
        "demo-security": (True, False),
        "demo-face": (False, False),
        "demo-lab": (True, True),
        "demo-career": (False, True),
        "demo-workshop": (True, False),
        "demo-volunteer": (None, None),
        "demo-exhibit": (None, True),
    }
    # R2：报后能不能取消（qxbm）与能不能报（sfkybm）的三态；没列出的活动两项都是 None，
    # 和详情没拿到时 list --json 的形态一致。demo-face 是窗口内已报名、可取消的一场。
    cancel_flags = {
        "demo-face": (True, None),
        "demo-dorm": (True, True),
        "demo-interview": (True, True),
        "demo-nocancel": (False, True),
        "demo-community": (True, True),
    }
    out = []
    for i, (aid, name, kind, place, s_off, e_off, act_s_off, act_e_off, signed) in enumerate(raw):
        # 样例时间也按学校东八区格式化：界面按 UTC+8 解析，用本机时区写会错位
        start = time_text_of(now + s_off)
        end = time_text_of(now + e_off)
        # 举办时间未公布时保持空串，和 grab.py list --json 的缺失形态一致
        act_start = "" if act_s_off is None else time_text_of(now + act_s_off)
        act_end = "" if act_e_off is None else time_text_of(now + act_e_off)
        checkin_required, checkout_required = flags.get(aid, (None, None))
        cancel_allowed, can_sign = cancel_flags.get(aid, (None, None))
        out.append({"index": i + 1, "id": aid, "name": name, "type": kind,
                    "place": place, "sign_start": start, "sign_end": end,
                    "act_start": act_start, "act_end": act_end, "signed": signed,
                    "checkin_required": checkin_required, "checkout_required": checkout_required,
                    "cancel_allowed": cancel_allowed, "can_sign": can_sign,
                    # 状态文案与 grab.py list --json 同一套中文口径，避免演示与真实契约不一致
                    "state": "已报名" if signed else (
                        "开放中" if s_off <= 0 else "未开放"),
                    "seconds_to_open": s_off})
    return out
