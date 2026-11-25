# -*- coding: utf-8 -*-
"""演示数据（--demo）：固定样例集，时间按给定 now 偏移，供离线视觉演示。

纯函数：now（此刻值）由调用方传入（app 外观取本机时刻后传入），样例时间格式化
函数（time_text_of）由 composition root 注入——domain 不直接依赖 time_contract。
样例字段与 grab.py list --json 的缺失形态一致。

@author Author
"""
from __future__ import annotations


# lab 与 career 报名同时开放，但举办时段重叠；workshop 同批开放却不重叠。
_DEMO_RAW = [
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

_DEMO_FLAGS = {
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
_DEMO_CANCEL_FLAGS = {
    "demo-face": (True, None),
    "demo-dorm": (True, True),
    "demo-interview": (True, True),
    "demo-nocancel": (False, True),
    "demo-community": (True, True),
}

# 奖励（实践分 / 虚拟工资），形态同 grab.py list --json：points / wage 为数字或 None，
# reward_state 为 "ready"（详情已回来）或 "pending"（还没回来）。多数有值；
# demo-volunteer 是详情未回的 pending；demo-exhibit 详情回来了但学校没公布；
# demo-career 工资是真实的 0。
_DEMO_REWARDS = {
    "demo-security": (2, 20, "ready"),
    "demo-face": (1, 10, "ready"),
    "demo-lab": (4, 40, "ready"),
    "demo-career": (1, 0, "ready"),
    "demo-workshop": (0.5, 5, "ready"),
    "demo-volunteer": (None, None, "pending"),
    "demo-exhibit": (None, None, "ready"),
    "demo-dorm": (2, 20, "ready"),
    "demo-interview": (8, 80, "ready"),
    "demo-nocancel": (1, 10, "ready"),
    "demo-community": (2, 20, "ready"),
}

# 简介与面向范围假值：覆盖代码 0、1（4+ 分支）、2、3、0..3 之外、空简介、详情未同步 None
_DEMO_DETAILS = {
    "demo-security": (
        "面向全校同学的网络安全科普与实操演练。\n"
        "第一部分：识别常见网络钓鱼与账号盗用手法，讲解日常防骗要点；"
        "第二部分：现场演示校园网络防护工具的基本配置，帮助大家建立良好的账号口令习惯。"
        "全程需按时完成入场与离场确认，现场座位先到先得，请提前十五分钟到场并保持安静。"
        "如临时不能参加且允许退报，请在截止前操作。",
        "全校同学",
        0,
    ),
    "demo-face": ("面对面交流校园数字化日常使用体验。\n欢迎提前准备要反馈的建议。", "示例甲级", 2),
    "demo-lab": (
        "参观实验台位并完成上机小测验，现场安排高年级同学分组带看。",
        "示例一分部、示例二分部、示例三分部、示例四分部、示例五分部",
        1,
    ),
    "demo-career": (
        "一对一简历诊断与修改建议，请携带电子或纸质草稿到场。",
        "年级：示例甲级、示例乙级; 分公司：示例一分部、示例二分部、示例三分部、示例四分部;",
        3,
    ),
    "demo-workshop": ("", "示例一分部、示例二分部", 1),
    "demo-volunteer": (None, None, None),
    "demo-exhibit": ("线上征集活动作品示例说明，支持多行纯文本展示。\n提交截止后统一评比。", "示例扩展范围标签（测试未知代码）", 5),
    "demo-dorm": ("例行宿舍安全与卫生检查记录场次，已报名后可查看基础详情。", "全校", 0),
    "demo-interview": ("分组开展结构化面试模拟与现场点评。", "示例一分部、示例二分部", 1),
    "demo-nocancel": ("邀请行业导师分享求职路径与岗位准备要点，本场报后不可退。", "示例乙级", 2),
    "demo-community": ("协助社区服务站整理图书与引导访客。", "", None),
}


def demo_items(now: float, time_text_of) -> list[dict]:
    """time_text_of：epoch 秒 → 学校时间文本（app.py 注入 school_time_text）。"""
    out = []
    for i, (aid, name, kind, place, s_off, e_off, act_s_off, act_e_off, signed) in enumerate(_DEMO_RAW):
        # 样例时间也按学校东八区格式化：界面按 UTC+8 解析，用本机时区写会错位
        start = time_text_of(now + s_off)
        end = time_text_of(now + e_off)
        # 举办时间未公布时保持空串，和 grab.py list --json 的缺失形态一致
        act_start = "" if act_s_off is None else time_text_of(now + act_s_off)
        act_end = "" if act_e_off is None else time_text_of(now + act_e_off)
        checkin_required, checkout_required = _DEMO_FLAGS.get(aid, (None, None))
        cancel_allowed, can_sign = _DEMO_CANCEL_FLAGS.get(aid, (None, None))
        points, wage, reward_state = _DEMO_REWARDS.get(aid, (None, None, "pending"))
        description, audience, audience_code = _DEMO_DETAILS.get(aid, ("", "", None))
        out.append({"index": i + 1, "id": aid, "name": name, "type": kind,
                    "place": place, "sign_start": start, "sign_end": end,
                    "act_start": act_start, "act_end": act_end, "signed": signed,
                    "checkin_required": checkin_required, "checkout_required": checkout_required,
                    "cancel_allowed": cancel_allowed, "can_sign": can_sign,
                    "points": points, "wage": wage, "reward_state": reward_state,
                    "description": description, "audience": audience,
                    "audience_code": audience_code,
                    # 状态文案与 grab.py list --json 同一套中文口径，避免演示与真实契约不一致
                    "state": "已报名" if signed else (
                        "开放中" if s_off <= 0 else "未开放"),
                    "seconds_to_open": s_off})
    return out
