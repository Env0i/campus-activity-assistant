#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 1 出口行为测试·计划栏一组（计划 20261113-refactor-step1-exit-tests）。

每个 test_ 守 D2 变异表里的一个出口（编号见用例名）：在 node 沙箱里按
index.html 的加载序跑真实界面脚本、触发动作、看用户看得到的结果（计划栏按钮、
结果框、运行记录），再断言状态值；不对源码文本做断言。
变异验证（未变异通过 / 对应变异变红）见 design/evidence/2026-11-13/exit-path-tests/。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 定时器桩与微任务推进；业务现在 = 北京时间 2026-11-06 14:00；演示登录不挡开始
PRELUDE = r"""
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = true;
S.band = "narrow";
function mk(id, name, extra) {
  return Object.assign({}, { id: id, name: name, place: "学生公寓", signed: false,
    checkin_required: false, checkout_required: false,
    sign_start: "2026-11-06 16:00:00", sign_end: "2026-11-08 09:00:00",
    act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
}
function load(items) {
  window.onBackend.activities({ ok: true, items: items.map((it) => Object.assign({}, it)) });
}
"""


class StartRequestExitTests(unittest.TestCase):
    """计划栏·开始请求的对账出口（S.starting）。"""

    def test_P03_canceled_reconciliation_releases_the_start_button(self):
        """计划栏·开始请求：对账说这次开始已取消——按钮离开「正在提交…」，
        结果框说明可以重新选了再开始。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  start_plan: () => Promise.reject(new Error("桥接断了")),
  start_request_state: () => Promise.resolve({ state: "canceled" }),
} };
load([mk("a1", "活动甲")]);
S.selected.add("a1");
startPlan();
const during = { starting: S.starting };
await __flush();
out.push({ during, after: { starting: S.starting, btn: $("#btn-plan").textContent,
                            result: $("#result").innerHTML } });
""")
        data = res[0]
        self.assertTrue(data["during"]["starting"], "前提：开始请求已发出、在等结论")
        self.assertFalse(data["after"]["starting"], "取消是结论，不能一直锁着开始")
        self.assertEqual(data["after"]["btn"], "开始报名计划", "按钮要回到可再次开始的样子")
        self.assertIn("这次开始已取消", data["after"]["result"])


class StoppingExitTests(unittest.TestCase):
    """计划栏·正在停止（S.stopping）的三条出口。"""

    def test_P05_plan_done_by_itself_releases_the_stopping_mark(self):
        """计划栏·正在停止：停止请求悬着时计划自己跑完——「停止计划」按钮要回到
        「停止计划」（不能停在「正在停止…」），忙态解除、结果页照常出。"""
        res = run_js(PRELUDE + r"""
S.busy = true;
S.stopping = true;
S.plan = { id: "p1", gen: 1, status: "running", tasks: new Map() };
window.onBackend.plan_done({ plan_id: "p1", status: "completed", plan_generation: 1, summary: {} });
render();
out.push({ stopText: $("#btn-stop").textContent, stopping: S.stopping, busy: S.busy,
           resultOpen: S.resultOpen === true });
""")
        data = res[0]
        self.assertEqual(data["stopText"], "停止计划", "计划已结束，停止按钮不能停在「正在停止…」")
        self.assertFalse(data["stopping"], "计划已结束，不能停在正在停止")
        self.assertFalse(data["busy"])
        self.assertTrue(data["resultOpen"], "终态要进结果页")

    def test_P07_new_start_ack_releases_a_stale_stopping_mark(self):
        """计划栏·正在停止：上一场停止请求悬着、用户重新开始并被接纳——
        停止按钮要回到「停止计划」，不能带着旧停止态进新计划。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: { start_plan: () => Promise.resolve({ ok: true, plan_id: "p1",
  plan_generation: 2 }) } };
load([mk("a1", "活动甲")]);
S.selected.add("a1");
S.stopping = true;
S.busy = false;
S.plan = { id: "p0", status: "stopped", tasks: new Map() };
startPlan();
await __flush();
out.push({ stopping: S.stopping, busy: S.busy, stopText: $("#btn-stop").textContent });
""")
        data = res[0]
        self.assertFalse(data["stopping"], "新计划已接纳，旧的停止标记要清")
        self.assertTrue(data["busy"], "新计划在跑")
        self.assertEqual(data["stopText"], "停止计划", "按钮不能停在「正在停止…」")

    def test_P08_adopted_reconciliation_releases_a_stale_stopping_mark(self):
        """计划栏·正在停止：对账确认接纳（accepted）——停止标记同样要清，
        停止按钮回到「停止计划」。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  start_plan: () => Promise.reject(new Error("桥接断了")),
  start_request_state: () => Promise.resolve({ state: "accepted", plan_id: "p1",
    plan_generation: 2, snapshot: { status: "running", tasks: [] } }),
} };
load([mk("a1", "活动甲")]);
S.selected.add("a1");
S.stopping = true;
S.busy = false;
S.plan = { id: "p0", status: "stopped", tasks: new Map() };
startPlan();
await __flush();
out.push({ stopping: S.stopping, busy: S.busy, stopText: $("#btn-stop").textContent });
""")
        data = res[0]
        self.assertFalse(data["stopping"], "对账接纳也要清停止标记")
        self.assertTrue(data["busy"])
        self.assertEqual(data["stopText"], "停止计划")


class EditingExitTests(unittest.TestCase):
    """计划栏·修改中（S.editing）的两条出口。"""

    def test_P13_clearing_the_selection_leaves_editing(self):
        """计划栏·修改中：用户清空选择——「修改中」标签要摘掉，计划栏回到普通草稿。"""
        res = run_js(PRELUDE + r"""
S.editing = { ids: ["a1"], doneN: 0 };
render();
const before = $("#dock-title").textContent;
clearSelection();
render();
out.push({ before, after: { title: $("#dock-title").textContent, editing: S.editing || null } });
""")
        data = res[0]
        self.assertTrue(data["before"].startswith("修改中"), "前提：计划栏挂在修改中")
        self.assertIsNone(data["after"]["editing"], "清空选择就是放弃修改")
        self.assertFalse(data["after"]["title"].startswith("修改中"), data["after"]["title"])

    def test_P14_a_new_plan_event_leaves_editing(self):
        """计划栏·修改中：后端推来一份计划号不同的新计划（运行中），随后这份新计划以
        stopped 结束——旧修改流程到此结束：计划栏回到「还没选活动」，修改里的场次
        不被放回勾选，结果页照常打开。"""
        res = run_js(PRELUDE + r"""
load([mk("a1", "活动甲")]);
S.editing = { ids: ["a1"], doneN: 0 };
window.onBackend.plan({ plan_id: "p5", plan_generation: 9, status: "running", tasks: [] });
window.onBackend.plan_done({ plan_id: "p5", status: "stopped", plan_generation: 9, summary: {} });
render();
out.push({ dock: $("#dock-title").textContent, selected: Array.from(S.selected),
           resultOpen: S.resultOpen === true, editing: S.editing || null });
""")
        data = res[0]
        self.assertEqual(data["dock"], "还没选活动", "新计划已结束，计划栏不能还挂着旧的修改中")
        self.assertEqual(data["selected"], [], "旧修改流程里的场次不能被放回勾选")
        self.assertTrue(data["resultOpen"], "新计划的终态要进结果页")
        self.assertIsNone(data["editing"], "新计划已接纳：修改流程结束")


if __name__ == "__main__":
    unittest.main()
