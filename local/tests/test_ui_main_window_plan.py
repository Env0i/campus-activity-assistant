#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主窗口向原型 1:1 的计划半边（计划 20261108-main-window，fe-plan）。

覆盖：窄档 dock 四态的文案（TF05 / PB16）、结果页「错过了」的计数 / 结论 / 任务卡动词（LS22 / PB15）、
修改计划与手机开始计划的两句运行记录（PB03 / PB11）、重试选项标签的空格（GL06）、
超 24 小时提醒里「这段时间」的断行连接符。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
断行与像素以 Edge/WebView2 截图为准，这里不测。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_ui_contract import LOCAL, run_js  # noqa: E402
from test_ui_main_window_list import SETUP  # noqa: E402

# 在 SETUP（业务现在 = 北京时间 2026-11-06 14:00）之上：窄档 dock、演示登录（不挡开始）、任务造数
PLAN_SETUP = SETUP + r"""
S.demo = true;
S.band = "narrow";
S.planOpen = false;
const stamp = (text) => toTs(text);
const task = (id, activity, extra) => S.plan.tasks.set(id, Object.assign(
  { task_id: id, activity_id: activity, status: "waiting", attempts: 0 }, extra || {}));
/* 一份已结束的计划：plan_done 之后的呈现状态（不置 busy，打开结果页） */
function finishPlan(status) {
  S.busy = false;
  S.plan.id = "p1";
  S.plan.status = status || "partial";
  openResultPage();
}
/* 运行记录行带 HH:MM:SS 前缀：断言只看句子本身 */
const bare = (lines) => lines.map((line) => line.replace(/^\d\d:\d\d:\d\d\s+/, ""));
const dock = () => ({ title: $("#dock-title").textContent, sub: $("#dock-sub").textContent,
                      startHidden: $("#btn-dock-start").hidden });
"""

# 睡眠窗口 13:37-14:00 盖住 m1(13:50)、m2(13:55)、ok(13:45)、fl(13:46)；out(12:00) 在窗口之前
SLEEP_AND_PLAN = r"""
load([
  mk("m1", "人工智能与未来职业", { sign_start: "2026-11-06 13:50:00", sign_end: "2026-11-06 18:00:00" }),
  mk("m2", "志愿服务培训", { sign_start: "2026-11-06 13:55:00", sign_end: "2026-11-06 18:00:00" }),
  mk("ok", "睡前已经提交的", { sign_start: "2026-11-06 13:45:00", sign_end: "2026-11-06 18:00:00" }),
  mk("out", "睡眠之前开的", { sign_start: "2026-11-06 12:00:00", sign_end: "2026-11-06 18:00:00" }),
  mk("fl", "名额满了的", { sign_start: "2026-11-06 13:46:00", sign_end: "2026-11-06 18:00:00" }),
]);
S.sleepWindow = { from: stamp("2026-11-06 13:37:00"), to: stamp("2026-11-06 14:00:00") };
"""


def read(rel: str) -> str:
    return (LOCAL / "ui" / rel).read_text(encoding="utf-8")


class DockStatesTests(unittest.TestCase):
    """TF05 / PB16：dock 草稿、修改中、结果三态（运行中沿用原来的写法）。"""

    def test_draft_dock_uses_the_summary_sentence_not_the_countdown(self):
        out = run_js(PLAN_SETUP + r"""
load([
  mk("now1", "现在就能报", { sign_start: "2026-11-06 13:00:00", sign_end: "2026-11-06 18:00:00" }),
  mk("pre1", "晚点开放甲", { sign_start: "2026-11-06 14:20:00", sign_end: "2026-11-06 18:00:00",
    act_start: "2026-11-09 13:00:00", act_end: "2026-11-09 15:00:00" }),
  mk("pre2", "晚点开放乙", { sign_start: "2026-11-06 14:40:00", sign_end: "2026-11-06 18:00:00",
    act_start: "2026-11-10 09:00:00", act_end: "2026-11-10 11:00:00" }),
]);
$("#countdown").textContent = "02:00:00 · 下一批开放";
render();
const empty = dock();
["now1", "pre1", "pre2"].forEach((id) => S.selected.add(id));
render();
const three = dock();
S.selected.delete("now1"); S.selected.delete("pre2");
render();
const onlyPre = dock();
out.push({ empty, three, onlyPre, planDisabled: $("#btn-plan").disabled });
""")[0]
        self.assertFalse(out["planDisabled"], "演示登录下开始按钮可用，才轮得到摘要句")
        # 没选：原型副文是「还差一步：」+ blockers[0]（先在时刻表勾选活动），不再是代码独有的提示句
        self.assertEqual(out["empty"]["title"], "还没选活动")
        self.assertEqual(out["empty"]["sub"], "还差一步：先在时刻表勾选活动")
        self.assertEqual(out["three"]["title"], "已选 3 场")
        self.assertEqual(out["three"]["sub"], "1 场立即报名，2 场预报名等开放", "摘要句，不是倒计时文本")
        self.assertFalse(out["three"]["startHidden"])
        self.assertEqual(out["onlyPre"]["title"], "已选 1 场")
        self.assertEqual(out["onlyPre"]["sub"], "1 场预报名等开放", "为 0 的一半不写")

    def test_draft_priority_blocker_then_warnings_then_summary(self):
        out = run_js(PLAN_SETUP + r"""
load([mk("pre1", "晚点开放甲", { sign_start: "2026-11-06 14:20:00", sign_end: "2026-11-06 18:00:00" })]);
S.selected.add("pre1");
render();
const plain = dock();
/* 断网：开始前提醒 1 条，开始按钮不禁用 */
S.online = false;
render();
const warned = dock();
/* 再加登录没了：开始按钮禁用，「还差一步」排在提醒前面（原型 why > pwN > summary） */
S.demo = false;
S.login.present = false;
render();
const blocked = dock();
out.push({ plain, warned, blocked, warnCount: S.preWarnCount });
""")[0]
        self.assertEqual(out["plain"]["sub"], "1 场预报名等开放")
        self.assertFalse(out["plain"]["startHidden"])
        self.assertEqual(out["warned"]["sub"], "有 1 条提醒，开始前先看一眼", "既有的提醒分支保留")
        self.assertTrue(out["warned"]["startHidden"], "有提醒时不给「开始」")
        self.assertTrue(out["blocked"]["sub"].startswith("还差一步："), out["blocked"]["sub"])
        self.assertTrue(out["blocked"]["startHidden"])

    def test_editing_dock_says_paused_and_counts_the_draft(self):
        out = run_js(PLAN_SETUP + r"""
load([
  mk("pre1", "晚点开放甲", { sign_start: "2026-11-06 14:20:00", sign_end: "2026-11-06 18:00:00" }),
  mk("pre2", "晚点开放乙", { sign_start: "2026-11-06 14:40:00", sign_end: "2026-11-06 18:00:00",
    act_start: "2026-11-10 09:00:00", act_end: "2026-11-10 11:00:00" }),
]);
S.selected.add("pre1"); S.selected.add("pre2");
S.editing = { ids: ["pre1", "pre2"], doneN: 0 };
render();
const editing = dock();
S.selected.delete("pre2");
render();
const one = dock();
S.editing = null;
render();
const after = dock();
out.push({ editing, one, after });
""")[0]
        self.assertEqual(out["editing"]["title"], "修改中：已选 2 场")
        self.assertEqual(out["editing"]["sub"], "计划已暂停，改完要重新开始")
        self.assertEqual(out["one"]["title"], "修改中：已选 1 场", "跟着勾选数走")
        self.assertEqual(out["after"]["title"], "已选 1 场", "修改结束回到普通草稿")
        self.assertEqual(out["after"]["sub"], "1 场预报名等开放")

    def test_start_plan_clears_editing_even_when_plan_id_stays(self):
        """修改 → 重新开始后，即使 plan_id 没变，editing 也必须立刻清掉。
        旧实现只等 handlePlan 收到新事件且 plan_id 变了才清，stop+restart 共用 id 时
        修改态说明会一直挂在屏上（2026-11-10 用户复现）。"""
        out = run_js(PLAN_SETUP + r"""
/* 假计时器：保存所有 setTimeout 回调但不触发，让 startPlan 的 15 秒 reconcile
   计时器保持待执行，只验证同 plan_id 接纳后的 editing 清理——不把计时器当成立即执行 */
const __pendingTimers = new Map();
let __nextTimerId = 1;
setTimeout = (fn, ms) => { const id = __nextTimerId++; __pendingTimers.set(id, { fn, ms }); return id; };
setInterval = (fn, ms) => 0;
clearTimeout = (id) => { __pendingTimers.delete(id); };
clearInterval = () => {};
window.pywebview = { api: {
  start_plan: () => Promise.resolve({ ok: true, plan_id: "ph1", plan_generation: 3 }),
  stop_plan: () => Promise.resolve({ ok: true }),
} };
load([mk("pre1", "晚点开放甲", { sign_start: "2026-11-06 16:00:00" })]);
S.selected.add("pre1");
S.plan = { id: "ph1", status: "stopped", gen: 2, tasks: new Map() };
/* 先进入修改态——editPlan 里的 S.editing = {...} + doStopPlan 简化为直接赋值 */
S.editing = { ids: ["pre1"], doneN: 0 };
render();
const before = dock();
startPlan();
/* startPlan 里的 Promise.then 是微任务，flush 一下再看 */
await Promise.resolve();
/* state/plan.js 正常事件没跑（没 emit），所以 S.plan.id 还是 "ph1"，
   但 editing 必须在 startPlan 的 then 分支里被立刻清掉 */
const cleared = S.editing;
render();
const after = dock();
out.push({ before, cleared, after, planStatus: S.plan.status });
""")[0]
        self.assertEqual(out["before"]["title"], "修改中：已选 1 场")
        self.assertIsNone(out["cleared"], "startPlan 成功接纳后 editing 必须立刻清掉")
        self.assertNotEqual(out["after"]["title"], "修改中：已选 1 场", "重新开始后 dock 不应再是修改中")
        self.assertNotIn("计划已暂停", out["after"]["sub"], "修改态子说明必须消失")

    def test_result_dock_shows_the_conclusion_from_the_result_page(self):
        out = run_js(PLAN_SETUP + r"""
load([
  mk("a", "活动甲", { sign_start: "2026-11-06 13:00:00" }),
  mk("b", "活动乙", { sign_start: "2026-11-06 13:00:00" }),
]);
task("t1", "a", { name: "活动甲", status: "success", attempts: 1 });
task("t2", "b", { name: "活动乙", status: "failed", stop_reason: "unconfirmed", attempts: 2 });
finishPlan("partial");
render();
const partial = dock();
const view = resultView();
task("t2", "b", { name: "活动乙", status: "success", attempts: 2 });
render();
const all = dock();
/* 结果页关掉（点「完成」之类）：dock 回到草稿 */
closeResultPage();
render();
const closed = dock();
out.push({ partial, view: { title: view.title, text: view.text }, all, closed });
""")[0]
        self.assertEqual(out["partial"]["title"], "报名计划部分完成")
        self.assertEqual(out["partial"]["sub"], "有 1 场需要到活动页核对，结果以学校为准。")
        self.assertEqual((out["partial"]["title"], out["partial"]["sub"]),
                         (out["view"]["title"], out["view"]["text"]), "dock 与结果页同一来源")
        self.assertTrue(out["partial"]["startHidden"], "结果态不给「开始」")
        self.assertEqual(out["all"]["title"], "报名计划完成")
        self.assertEqual(out["all"]["sub"], "每场结束时都向学校核对过。")
        self.assertNotEqual(out["closed"]["title"], "报名计划完成")

    def test_dock_keeps_the_running_wording_and_hides_on_wide(self):
        out = run_js(PLAN_SETUP + r"""
load([mk("pre1", "晚点开放甲", { sign_start: "2026-11-06 16:00:00", sign_end: "2026-11-06 18:00:00" })]);
S.selected.add("pre1");
S.busy = true;
S.plan.id = "p1"; S.plan.status = "running";
task("t1", "pre1", { name: "晚点开放甲", sign_start: "2026-11-06 16:00:00" });
$("#countdown").textContent = "02:00:00";
render();
const running = dock();
S.band = "wide";
render();
out.push({ running, wideHidden: $("#plan-dock").hidden });
""")[0]
        self.assertEqual(out["running"]["title"], "报名计划运行中", "运行中那一行表里没列，不动")
        self.assertTrue(out["running"]["startHidden"])
        self.assertTrue(out["wideHidden"], "宽档没有 dock")

    def test_long_wait_warning_glues_the_break_inside_this_period(self):
        # 原型在窄档把「这段时间」「电脑」各拆成两行，用 U+2060 连住（时/间、电/脑）；界面同句同样处理
        self.assertIn("这段时⁠间电⁠脑不能关机或睡眠。", read("views/plan-panel.js"))
        self.assertNotIn("这段时间电脑不能关机或睡眠。", read("views/plan-panel.js"))


class MissedResultTests(unittest.TestCase):
    """LS22 / PB15：结果页「错过了」计数、结论、任务卡动词；与时刻表行级同一判据，不重复计数。"""

    def test_missed_is_counted_apart_and_never_double_counted(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
task("t1", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
task("t2", "m2", { name: "志愿服务培训", status: "failed", stop_reason: "auth_unavailable" });
task("t3", "ok", { name: "睡前已经提交的", status: "success", attempts: 1 });
task("t4", "out", { name: "睡眠之前开的", status: "failed", stop_reason: "deadline" });
task("t5", "fl", { name: "名额满了的", status: "failed", stop_reason: "full", attempts: 3 });
finishPlan("partial");
render();
const counts = resultCounts();
const statsHtml = $("#plan-stats").innerHTML;
const cells = statsHtml.replace(/<\/div>/g, "|").replace(/<[^>]*>/g, "");
const total = Object.keys(counts).reduce((sum, key) => sum + counts[key], 0);
const rowTag = (id) => /state-missed/.test(rowHtml(findItem(id)));
out.push({ counts, cells, statsHtml, total, tasks: S.plan.tasks.size,
           rowMissed: { m1: rowTag("m1"), m2: rowTag("m2"), ok: rowTag("ok"), out: rowTag("out"), fl: rowTag("fl") } });
""")[0]
        self.assertEqual(out["counts"], {"ok": 1, "full": 1, "bad": 1, "missed": 2, "pending": 0, "canceled": 0})
        self.assertEqual(out["total"], out["tasks"], "每一场只落进一类，合计等于场数")
        # 原型顺序：已报名 / 名额已满 / 报名未成功 / 错过了 / 待核对 / 已取消
        self.assertEqual(out["cells"], "1已报名|1名额已满|1报名未成功|2错过了|")
        self.assertIn('<div data-tone="bad"><strong>2</strong><span>错过了</span></div>', out["statsHtml"],
                      "错过了是红色（原型 tone bad）")
        # 时刻表行级与结果页是同一批：m1、m2 在睡眠窗口里没提交；睡眠之前的 out 不算
        self.assertEqual(out["rowMissed"], {"m1": True, "m2": True, "ok": False, "out": False, "fl": False})

    def test_task_cards_use_the_missed_verb_and_the_prototype_reason(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
task("t1", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
task("t2", "m2", { name: "志愿服务培训", status: "failed", stop_reason: "auth_unavailable" });
task("t4", "out", { name: "睡眠之前开的", status: "failed", stop_reason: "deadline" });
task("t6", "ok", { name: "睡前已经提交的", status: "success", attempts: 1 });
finishPlan("failed");
render();
const card = (id) => {
  const html = taskHtml(S.plan.tasks.get(id), bnowS());
  return { label: (html.match(/class="task-state ([^"]*)">([^<]*)</) || []).slice(1), detail: (html.match(/task-detail">([^<]*)</) || [])[1] };
};
out.push({ t1: card("t1"), t2: card("t2"), t4: card("t4"), t6: card("t6"),
           label: taskLabel("missed"), cls: taskClass("missed", null),
           tagged: $("#plan-tasks").innerHTML.split("错过了").length - 1 });
""")[0]
        self.assertEqual(out["label"], "错过了")
        self.assertEqual(out["cls"], "is-bad")
        self.assertEqual(out["t1"]["label"], ["is-bad", "错过了"])
        self.assertEqual(out["t1"]["detail"], "电脑睡眠期间到了开放时间，没有提交。")
        # 「没提交」的泛说法（未提交 / is-warn）被睡眠错过盖过
        self.assertEqual(out["t2"]["label"], ["is-bad", "错过了"])
        self.assertEqual(out["t2"]["detail"], "电脑睡眠期间到了开放时间，没有提交。")
        # 睡眠窗口之外的失败仍然是原来的写法
        self.assertEqual(out["t4"]["label"][1], "报名未成功")
        self.assertEqual(out["t6"]["label"], ["is-ok", "报名成功"])
        # 任务卡里「错过了」出现两次：m1、m2 各一个动词（说明句里是「没有提交」，不含这三个字）
        self.assertEqual(out["tagged"], 2)

    def test_all_missed_conclusion_title_body_and_red_frame(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
task("t1", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
task("t2", "m2", { name: "志愿服务培训", status: "failed", stop_reason: "deadline" });
finishPlan("failed");
render();
const view = resultView();
out.push({ tag: view.tag, tone: view.tone, title: view.title, text: view.text, frame: view.frame, led: view.led,
           board: $("#selected").textContent, boardText: $("#board-text").textContent,
           state: $("#board").dataset.planState, dock: dock(),
           reselect: reselectableIds() });
""")[0]
        self.assertEqual(out["title"], "电脑睡眠，错过了开放")
        self.assertEqual(out["text"], "运行计划时别让电脑睡眠：在 Windows 电源设置里把睡眠改成“从不”，并保持插电。")
        self.assertEqual((out["tag"], out["tone"]), ("错过了", "red"))
        self.assertIsNone(out["led"], "原型这一支没有 LED")
        self.assertEqual(out["frame"], "bad")
        self.assertEqual(out["state"], "failed", "红框：确定没提交，FR06 的「失败」外框")
        self.assertEqual(out["board"], out["title"])
        self.assertEqual(out["boardText"], out["text"])
        self.assertEqual((out["dock"]["title"], out["dock"]["sub"]), (out["title"], out["text"]))
        self.assertEqual(sorted(out["reselect"]), ["m1", "m2"], "错过了的还开着就能重新选（原型 canRetry 含 missed）")

    def test_missed_next_to_other_outcomes_follows_the_prototype_chain(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
const run = (setup) => {
  S.plan.tasks.clear();
  setup();
  finishPlan("partial");
  render();
  const v = resultView();
  return { title: v.title, frame: v.frame, state: $("#board").dataset.planState, tag: v.tag };
};
const missedTask = () => task("tm", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
const withOk = run(() => { missedTask(); task("to", "ok", { name: "睡前已经提交的", status: "success", attempts: 1 }); });
const withPending = run(() => { missedTask(); task("tp", "fl", { name: "名额满了的", status: "failed", stop_reason: "unconfirmed", attempts: 2 }); });
const withFull = run(() => { missedTask(); task("tf", "fl", { name: "名额满了的", status: "failed", stop_reason: "full", attempts: 2 }); });
const withBad = run(() => { missedTask(); task("tb", "out", { name: "睡眠之前开的", status: "failed", stop_reason: "deadline" }); });
const cancelled = run(() => { task("tc", "m1", { name: "人工智能与未来职业", status: "canceled" }); });
out.push({ withOk, withPending, withFull, withBad, cancelled });
""")[0]
        # 有成功的：部分完成（黄框），不因为有一场错过了就画成红
        self.assertEqual(out["withOk"]["title"], "报名计划部分完成")
        self.assertEqual(out["withOk"]["frame"], "warn")
        # 有待核对：待核对优先，仍是黄框（FR06：含待核对的计划不画成确定失败）
        self.assertEqual(out["withPending"]["title"], "计划已结束，有 1 场需确认")
        self.assertEqual(out["withPending"]["frame"], "warn")
        # 名额已满 + 错过了：错过了的结论排在名额已满之前
        self.assertEqual(out["withFull"]["title"], "电脑睡眠，错过了开放")
        # 另有普通失败：不用「电脑睡眠」下结论，落到原型最后一支
        self.assertEqual(out["withBad"]["title"], "报名计划没有成功")
        self.assertEqual(out["withBad"]["frame"], "bad")
        # 用户取消的场次即使开放时刻落在睡眠窗口里，也只是「已取消」，不翻成错过了
        self.assertNotEqual(out["cancelled"]["title"], "电脑睡眠，错过了开放")
        self.assertEqual(out["cancelled"]["tag"], "未成功")

    def test_missed_never_makes_a_plan_look_fully_successful(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
task("tm", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
task("to", "ok", { name: "睡前已经提交的", status: "success", attempts: 1 });
finishPlan("partial");
const view = resultView();
const counts = resultCounts();
out.push({ title: view.title, ok: counts.ok, missed: counts.missed, bad: counts.bad });
""")[0]
        self.assertEqual((out["ok"], out["missed"], out["bad"]), (1, 1, 0))
        self.assertNotEqual(out["title"], "报名计划完成")

    def test_without_a_sleep_window_nothing_is_missed(self):
        out = run_js(PLAN_SETUP + SLEEP_AND_PLAN + r"""
S.sleepWindow = null;
task("t1", "m1", { name: "人工智能与未来职业", status: "failed", stop_reason: "deadline" });
finishPlan("failed");
render();
out.push({ counts: resultCounts(), label: taskDisplayLabel(S.plan.tasks.get("t1")) });
""")[0]
        self.assertEqual(out["counts"]["missed"], 0)
        self.assertEqual(out["counts"]["bad"], 1)
        self.assertEqual(out["label"], "报名未成功")


class RunLogLineTests(unittest.TestCase):
    """PB03 / PB11：两句运行记录。"""

    def test_modify_plan_logs_the_paused_line_with_the_draft_count(self):
        out = run_js(PLAN_SETUP + r"""
load([
  mk("w1", "晚点开放甲", { sign_start: "2026-11-06 16:00:00" }),
  mk("w2", "晚点开放乙", { sign_start: "2026-11-06 16:30:00" }),
  mk("d1", "已经结束的", { sign_start: "2026-11-06 13:00:00" }),
]);
S.busy = true;
S.plan.id = "p1"; S.plan.status = "running";
task("t1", "w1", { name: "晚点开放甲", sign_start: "2026-11-06 16:00:00" });
task("t2", "w2", { name: "晚点开放乙", sign_start: "2026-11-06 16:30:00", status: "queued" });
task("t3", "d1", { name: "已经结束的", status: "success", attempts: 1 });
window.pywebview = { api: { stop_plan: () => new Promise(() => {}) } };
const before = appended.length;
modifyPlan();
const first = bare(appended.slice(before));
/* 同一句再来一次（改了又停了又改）：不被整句去重吞掉 */
S.busy = true; S.stopping = false; S.editing = null;
addLog("中间有别的记录");
modifyPlan();
out.push({ first, all: bare(appended.slice(before)), editing: S.editing });
""")[0]
        self.assertIn("计划已暂停：2 场放回草稿修改", out["first"])
        self.assertNotIn("修改计划：先停下，改完要重新开始", "".join(out["all"]), "旧句已换掉")
        self.assertEqual(sum(1 for line in out["all"] if line == "计划已暂停：2 场放回草稿修改"), 2)

    def test_phone_started_plan_logs_one_start_line(self):
        out = run_js(PLAN_SETUP + r"""
const plan = (source, status, tasks) => window.onBackend.plan({ plan_id: "ph1", plan_generation: 5, source: source, status: status,
  tasks: tasks });
const mkTask = (id, mode) => ({ task_id: id, activity_id: id, name: id, status: "waiting", signup_mode: mode });
const before = appended.length;
plan("phone", "running", [mkTask("a", "pre_register"), mkTask("b", "pre_register")]);
const first = bare(appended.slice(before));
/* 同一个计划的后续 plan 事件：不再写 */
plan("phone", "running", [mkTask("a", "pre_register"), mkTask("b", "pre_register")]);
const second = bare(appended.slice(before));
/* 另一份由电脑自己开始的计划：没有这一句 */
const mark = appended.length;
window.onBackend.plan({ plan_id: "dk1", plan_generation: 6, source: "desktop", status: "running", tasks: [mkTask("c", "pre_register")] });
const desktop = bare(appended.slice(mark));
/* 两种模式都有 */
const mark2 = appended.length;
window.onBackend.plan({ plan_id: "ph2", plan_generation: 7, source: "phone", status: "running",
  tasks: [mkTask("d", "instant_signup"), mkTask("e", "pre_register"), mkTask("f", "pre_register")] });
const mixed = bare(appended.slice(mark2));
out.push({ first, second, desktop, mixed });
""")[0]
        self.assertEqual(out["first"], ["从手机开始了报名计划：2 场预报名等开放"])
        self.assertEqual(out["second"], out["first"], "同计划的后续事件不重复写")
        self.assertEqual(out["desktop"], [], "电脑自己开始的计划不写这一句")
        self.assertEqual(out["mixed"], ["从手机开始了报名计划：1 场立即报名，2 场预报名等开放"])

    def test_phone_plan_restored_after_reload_does_not_log_again(self):
        out = run_js(PLAN_SETUP + r"""
const before = appended.length;
ingestBootstrapPlan({ plan: { plan_id: "ph1", plan_generation: 5, status: "running", source: "phone",
  tasks: [{ task_id: "a", activity_id: "a", name: "a", status: "waiting", signup_mode: "pre_register" }] } });
window.onBackend.plan({ plan_id: "ph1", plan_generation: 5, source: "phone", status: "running",
  tasks: [{ task_id: "a", activity_id: "a", name: "a", status: "waiting", signup_mode: "pre_register" }] });
out.push({ lines: bare(appended.slice(before)) });
""")[0]
        self.assertEqual(out["lines"], [], "页面重载后恢复的计划，开始记录早写过了")

    def test_old_log_sentences_are_gone_from_the_sources(self):
        controller = read("controllers/plan.js")
        self.assertNotIn("修改计划：先停下，改完要重新开始", controller)
        self.assertIn("计划已暂停：", controller)
        self.assertIn("从手机开始了报名计划", controller)


class RetryLabelTests(unittest.TestCase):
    """GL06：重试选项标签与输入框标签的空格。"""

    def test_labels_have_the_prototype_spaces_everywhere(self):
        html = read("index.html")
        store = read("state/store.js")
        for source in (html, store):
            self.assertIn("自动延长（最多 25 分钟）", source)
            self.assertNotIn("最多25分钟", source)
        self.assertIn("最多提交次数（0 = 不限）", html)
        self.assertNotIn("最多提交次数（0=不限）", html)

    def test_summary_line_says_just_auto_extend(self):
        out = run_js(PLAN_SETUP + r"""
S.retryPolicy = { retry_for_s: -1, max_attempts: 0 };
paintPolicyLine();
const auto = $("#policy-text").innerHTML;
S.retryPolicy = { retry_for_s: 600, max_attempts: 3 };
paintPolicyLine();
out.push({ auto, ten: $("#policy-text").innerHTML });
""")[0]
        self.assertEqual(out["auto"], "尝试 <b>自动延长</b>，<b>不限次数</b>", "概括行照原型 retryText，不带括号")
        self.assertEqual(out["ten"], "尝试 <b>10 分钟</b>，<b>最多 3 次</b>")


if __name__ == "__main__":
    unittest.main()
