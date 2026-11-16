#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划栏搬进模块之前的真加载冒烟：宽档、窄档各一次，加上计划快照与结果页。

真加载指的是按 index.html 的普通脚本顺序逐个执行、再用真实的动态 import 加载 main.js，
不走拼接夹具。拼接以后模块里的名字恰好进了全局作用域，普通脚本阶段引用模块名字这类
缺陷只有真加载才暴露；这里守的就是「搬完以后真窗口还能起来、计划栏还画得出来」。

三条用例都不改页面状态以外的东西：普通脚本阶段不抛错 + 计划栏标题、任务卡、停止按钮
画出来；结果页画得出统计与「重新选择」。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_native_smoke  # noqa: E402


# 计划快照：两场都在等开放，运行中。时间用远期，避免用例随日历过期。
PLAN_SNAPSHOT = r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.demo = false;
S.busy = true;
S.listState = "ready";
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "waiting",
  sign_start: "2099-01-01 09:00:00" });
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙", status: "waiting",
  sign_start: "2099-01-01 09:00:00" });
"""


class PlanMoveSmokeTests(unittest.TestCase):
    # 宽档真加载：普通脚本阶段不抛错，计划栏标题、两张任务卡和停止按钮都画出来。
    def test_wide_load_draws_the_running_plan_board(self):
        result = run_native_smoke([], after=PLAN_SNAPSHOT + r"""
render();
out.push({ tag: $("#board-tag-text").textContent, title: $("#selected").textContent,
  tasks: $("#plan-tasks").textContent, stopText: $("#btn-stop").textContent,
  stopDisabled: $("#btn-stop").disabled, band: S.band });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertEqual(case["band"], "wide")
        self.assertEqual(case["tag"], "等开放")
        self.assertEqual(case["title"], "活动甲")
        self.assertIn("活动甲", case["tasks"])
        self.assertIn("活动乙", case["tasks"])
        self.assertEqual(case["stopText"], "停止计划")
        self.assertFalse(case["stopDisabled"], "运行中停止按钮必须可点")

    # 窄档真加载：430 宽下计划条与计划栏照样画出来，普通脚本阶段不抛错。
    def test_narrow_load_draws_the_plan_dock_and_board(self):
        result = run_native_smoke([], size=(430, 820), after=PLAN_SNAPSHOT + r"""
S.selected = new Set();
render();
out.push({ band: S.band, title: $("#selected").textContent,
  dockHidden: $("#plan-dock").hidden, dockTitle: $("#dock-title").textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertEqual(case["band"], "narrow")
        self.assertEqual(case["title"], "活动甲")
        self.assertFalse(case["dockHidden"], "窄档要摆计划条")
        self.assertIn("运行中", case["dockTitle"])

    # 结果页真加载：一场成功一场失败时，统计与「重新选择」都画出来。
    def test_result_page_draws_stats_and_reselect(self):
        result = run_native_smoke([], after=r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.demo = false;
S.busy = false;
S.listState = "ready";
S.plan = { id: "p1", status: "partial", tasks: new Map() };
S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲", status: "success" });
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙", status: "failed",
  stop_reason: "max_attempts", attempts: 2 });
/* 一场还能重报的活动留在列表里，并给一个可信现在：重选判据要读业务时钟 */
ingestBusinessClock({ schema: 1, owner_id: "smoke", generation: 1, state: "ready",
  epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0,
  source: "smoke", age_s: 0, reason: "冒烟" });
S.items = [{ id: "a2", name: "活动乙", place: "学生公寓", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2099-01-02 09:00:00", sign_end: "2099-01-03 09:00:00",
  act_start: "2099-01-04 09:00:00", act_end: "2099-01-04 11:00:00" }].map(normalize);
S.byId = new Map(S.items.map((i) => [String(i.id), i]));
openResultPage();
render();
out.push({ stats: $("#plan-stats").textContent, statsHidden: $("#plan-stats").hidden,
  reselectHidden: $("#btn-reselect").hidden, actionsHidden: $("#result-actions").hidden,
  tag: $("#board-tag-text").textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        case = result["after"][0]
        self.assertFalse(case["statsHidden"], "结果页要摆统计")
        self.assertIn("已报名", case["stats"])
        self.assertIn("报名未成功", case["stats"])
        self.assertFalse(case["actionsHidden"], "结果页要摆页脚按钮")
        self.assertFalse(case["reselectHidden"], "有可重报场次时要给「重新选择」")
        self.assertEqual(case["tag"], "部分完成")


if __name__ == "__main__":
    unittest.main()
