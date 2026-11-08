#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电脑端：冲突原因气泡、跨天时段、报后可退、可取消至、取消报名（计划 20261107-conflict-cancel，fe-desktop）。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
断行与像素以 Edge/WebView2 截图为准，这里不测；定位（翻到行上方）用桩出来的矩形验算。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_ui_contract import LOCAL, read_ui_scripts, run_js  # noqa: E402

WJ = "⁠"

# 业务现在 = 北京时间 2026-11-06 14:00；三场活动，名字用通用名
SETUP = r"""
const WJ = "⁠";
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const base = { place: "学生公寓", checkin_required: false, checkout_required: false };
const signedA = Object.assign({}, base, { id: "s1", name: "宿舍查寝", signed: true, cancel_allowed: true,
  sign_start: "2026-11-05 08:00:00", sign_end: "2026-11-08 14:00:00",
  act_start: "2026-11-08 22:40:00", act_end: "2026-11-10 23:20:00" });
const clashB = Object.assign({}, base, { id: "b1", name: "模拟面试", signed: false, cancel_allowed: null,
  sign_start: "2026-11-07 10:00:00", sign_end: "2026-11-08 10:00:00",
  act_start: "2026-11-09 08:00:00", act_end: "2026-11-09 17:00:00" });
const noRefundC = Object.assign({}, base, { id: "c1", name: "职业规划讲座", signed: false, cancel_allowed: false,
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-07 18:00:00",
  act_start: "2026-11-06 16:00:00", act_end: "2026-11-06 17:30:00" });
const refundD = Object.assign({}, base, { id: "d1", name: "社区志愿服务日", signed: false, cancel_allowed: true,
  sign_start: "2026-11-06 08:00:00", sign_end: "2026-11-07 18:00:00",
  act_start: "2026-11-07 09:00:00", act_end: "2026-11-07 11:30:00" });
function load(items) {
  window.onBackend.activities({ ok: true, items: items.map((it) => Object.assign({}, it)) });
}
const calls = [];
window.pywebview = { api: {
  cancel_signup: (id) => { calls.push(id); return Promise.resolve(globalThis.__cancelReply || { ok: true, kind: "cancelled" }); },
  check: () => Promise.resolve({ ok: true }),
  list_activities: () => Promise.resolve({ ok: true }),
} };
const click = (selector, dataset) => {
  const target = { closest: (sel) => (sel === selector ? { dataset: dataset || {} } : null) };
  $("#rows").listeners.click.forEach((fn) => fn({ target: target, preventDefault() {} }));
};
"""


# 假计时器：run(ms) 把虚拟时间推进 ms，到点的回调按先后触发；clear 过的不触发
HOVER = r"""
const timers = (() => {
  let now = 0, seq = 0;
  const list = [];
  return {
    add: (fn, ms) => { seq += 1; list.push({ id: seq, at: now + (ms || 0), fn, live: true }); return seq; },
    clear: (id) => { list.forEach((t) => { if (t.id === id) t.live = false; }); },
    run: (ms) => {
      const to = now + ms;
      for (;;) {
        const due = list.filter((t) => t.live && t.at <= to).sort((a, b) => a.at - b.at || a.id - b.id)[0];
        if (!due) break;
        due.live = false; now = due.at; due.fn();
      }
      now = to;
    },
    pending: () => list.filter((t) => t.live).length,
  };
})();
setTimeout = (fn, ms) => timers.add(fn, ms);
clearTimeout = (id) => timers.clear(id);
const hoverTag = (id) => {
  const row = { dataset: { id: id } };
  const tag = { closest: (s) => (s === ".row" ? row : null) };
  $("#rows").listeners.mouseover.forEach((fn) => fn({ target: { closest: (s) => (s === ".state-clash" ? tag : null) } }));
};
"""


class ClashRowTests(unittest.TestCase):
    """重叠行：勾选框置灰，状态格只剩「不可加入」，行内没有「不能加入」，也没有倒计时。"""

    def test_clash_row_is_disabled_with_a_bare_tag(self):
        out = run_js(SETUP + r"""
load([signedA, clashB, noRefundC]);
const html = rowHtml(findItem("b1"));
const other = rowHtml(findItem("c1"));
out.push({
  html: html, other: other,
  checkDisabled: /<input class="row-check"[^>]*disabled/.test(html),
  otherDisabled: /<input class="row-check"[^>]*disabled/.test(other),
});
""")[0]
        html = out["html"]
        self.assertIn("不可加入", html)
        self.assertIn('class="state-tag state-clash"', html)
        self.assertIn('tabindex="0"', html, "标签可键盘聚焦")
        self.assertIn('aria-describedby="cx-tip"', html)
        self.assertNotIn("不能加入", html, "行内不再写「与已报名的…不能加入」")
        self.assertNotIn("时间重叠，", html)
        self.assertNotIn('class="left', html, "不可加入的行不显示距开放倒计时")
        self.assertTrue(out["checkDisabled"], "重叠行复选框禁用")
        self.assertFalse(out["otherDisabled"], "不重叠的行照常可勾选")
        self.assertNotIn("不可加入", out["other"])

    def test_signed_and_closed_rows_never_show_the_tag(self):
        out = run_js(SETUP + r"""
const closedX = Object.assign({}, clashB, { id: "x1", name: "已截止的面试", sign_end: "2026-11-05 10:00:00" });
load([signedA, closedX]);
out.push({ signed: rowHtml(findItem("s1")), closed: rowHtml(findItem("x1")) });
""")[0]
        self.assertNotIn("不可加入", out["signed"])
        self.assertNotIn("不可加入", out["closed"], "已截止的行本来就只能查看，不再写不可加入")

    def test_list_script_has_no_inline_clash_text(self):
        text = (LOCAL / "ui" / "views" / "list.js").read_text(encoding="utf-8")
        self.assertNotIn("不能加入", text)


class TipBubbleTests(unittest.TestCase):
    """气泡：标题、两个时段、时间条、四种解除路径；悬停 / 聚焦打开，Esc 收起。"""

    def test_four_resolution_sentences(self):
        out = run_js(SETUP + r"""
const nm = "「宿舍查寝」";
const cases = {
  a: signedA,                                                        // 能取消：14:00 前窗口还开着
  b: Object.assign({}, signedA, { cancel_allowed: false }),
  c: Object.assign({}, signedA, { sign_end: "2026-11-06 10:00:00" }), // 窗口已关
  d: Object.assign({}, signedA, { cancel_allowed: null }),
};
const res = {};
Object.keys(cases).forEach((k) => {
  load([cases[k], clashB]);
  const model = conflictTipModel(findItem("b1"), findItem("s1"));
  res[k] = { way: model.way, hasGo: model.hasGo, kind: model.wayKind, html: tipHtml(model) };
});
out.push(res);
""")[0]
        self.assertEqual(out["a"]["way"], "想报这一场，要先取消「宿舍查寝」的报名，11月8日 14:00 前可以取消。")
        self.assertTrue(out["a"]["hasGo"])
        self.assertIn("去已报名那场", out["a"]["html"])
        self.assertEqual(out["b"]["way"], "「宿舍查寝」报名后不能取消，" + WJ.join("这一场报不了。"))
        self.assertEqual(out["c"]["way"], "「宿舍查寝」的取消时间已过（截至 11月6日 10:00），" + WJ.join("这一场报不了。"))
        self.assertEqual(out["d"]["way"], "「宿舍查寝」能不能取消还没查到，刷新后再看。")
        for key in "bcd":
            self.assertFalse(out[key]["hasGo"], key + " 句没有链接")
            self.assertNotIn("去已报名那场", out[key]["html"])
        self.assertEqual([out[k]["kind"] for k in "abcd"], list("abcd"))

    def test_bubble_content_and_timeline(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
const model = conflictTipModel(findItem("b1"), findItem("s1"));
out.push({ model: model, html: tipHtml(model) });
""")[0]
        model, html = out["model"], out["html"]
        self.assertIn("和已报名的活动时间重叠", html)
        self.assertEqual(model["rows"][0], {
            "label": "已报名", "name": "宿舍查寝",
            "span": "11月8日 22:40 – 11月10日 23:20（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ)})
        self.assertEqual(model["rows"][1], {"label": "这一场", "name": "模拟面试", "span": "11月9日 08:00–17:00"})
        self.assertEqual([d["text"] for d in model["days"]], ["11月8日", "11月9日", "11月10日"])
        self.assertEqual(len(model["cuts"]), 2)
        # 重叠段 = 11-09 整个模拟面试；三天各占三分之一
        self.assertAlmostEqual(model["ovL"], 33.33 + (8 / 24) / 3 * 100, delta=0.05)
        self.assertGreater(model["ovW"], 0)
        for legend in ("已报名", "这一场", "重叠"):
            self.assertIn(">" + legend + "<", html)
        self.assertIn('class="tl-ov"', html)

    def test_hover_opens_and_escape_closes_without_clearing_selection(self):
        # f81959e 有意把触发点从「整行」改到「不可加入」标签，并加了 140ms 的停留：
        # 这里悬停标签、让计时走完，其余断言（打开、Esc 收起、不清已选）不变。
        out = run_js(SETUP + HOVER + r"""
load([signedA, clashB, noRefundC]);
S.selected.add("c1");
hoverTag("b1");
timers.run(140);
const opened = { id: S.tip.id, hidden: $("#cx-tip").hidden, text: $("#cx-tip").innerHTML };
__dispatchKey({ key: "Escape" });
out.push({ opened, closed: { id: S.tip.id, hidden: $("#cx-tip").hidden }, selected: Array.from(S.selected) });
""")[0]
        self.assertEqual(out["opened"]["id"], "b1")
        self.assertFalse(out["opened"]["hidden"])
        self.assertIn("和已报名的活动时间重叠", out["opened"]["text"])
        self.assertEqual(out["closed"], {"id": "", "hidden": True})
        self.assertEqual(out["selected"], ["c1"], "Esc 先收气泡，不顺手清空已选")

    def test_hovering_the_row_but_not_the_tag_never_opens(self):
        out = run_js(SETUP + HOVER + r"""
load([signedA, clashB]);
const row = { classList: { contains: (c) => c === "is-clash" }, dataset: { id: "b1" } };
$("#rows").listeners.mouseover.forEach((fn) => fn({ target: { closest: (s) => (s === ".row" ? row : null) } }));
const early = S.tip.id;
timers.run(1000);
out.push({ early, id: S.tip.id, hidden: $("#cx-tip").hidden, pending: timers.pending() });
""")[0]
        self.assertEqual(out["early"], "")
        self.assertEqual(out["id"], "", "只扫过行的其它部位，计时走完也不弹")
        self.assertEqual(out["pending"], 0)

    def test_leaving_the_tag_within_140ms_cancels_the_pending_open(self):
        out = run_js(SETUP + HOVER + r"""
load([signedA, clashB]);
hoverTag("b1");
timers.run(60);
const mid = S.tip.id;
$("#rows").listeners.mouseout.forEach((fn) => fn({ target: { closest: (s) => (s === ".state-clash" ? {} : null) } }));
timers.run(1000);
const afterOut = S.tip.id;
// 再来一次：这回是整个列表的 mouseleave
hoverTag("b1");
timers.run(60);
$("#rows").listeners.mouseleave.forEach((fn) => fn({}));
timers.run(1000);
out.push({ mid, afterOut, afterLeave: S.tip.id, hidden: $("#cx-tip").hidden, pending: timers.pending() });
""")[0]
        self.assertEqual(out["mid"], "", "还不到 140ms，不开")
        self.assertEqual(out["afterOut"], "", "140ms 内移开标签：待开的计时被取消，气泡不能自己冒出来")
        self.assertEqual(out["afterLeave"], "", "140ms 内离开整个列表同理")
        self.assertTrue(out["hidden"])
        self.assertEqual(out["pending"], 0)

    def test_moving_from_tag_text_to_its_icon_keeps_an_open_bubble(self):
        out = run_js(SETUP + HOVER + r"""
load([signedA, clashB]);
hoverTag("b1");
timers.run(140);
const opened = S.tip.id;
$("#rows").listeners.mouseout.forEach((fn) => fn({ target: { closest: (s) => (s === ".state-clash" ? {} : null) } }));
hoverTag("b1");                       // 子元素（图标）的 mouseover：closest 仍是同一个标签
timers.run(300);
out.push({ opened, after: S.tip.id, hidden: $("#cx-tip").hidden });
""")[0]
        self.assertEqual(out["opened"], "b1")
        self.assertEqual(out["after"], "b1", "指针还在标签内，tipLater 设的关闭计时必须被取消")
        self.assertFalse(out["hidden"])

    def test_resting_on_the_tag_for_140ms_opens(self):
        out = run_js(SETUP + HOVER + r"""
load([signedA, clashB]);
hoverTag("b1");
timers.run(139);
const before = S.tip.id;
timers.run(1);
out.push({ before, after: S.tip.id, hidden: $("#cx-tip").hidden });
""")[0]
        self.assertEqual(out["before"], "")
        self.assertEqual(out["after"], "b1")
        self.assertFalse(out["hidden"])

    def test_keyboard_focus_opens_and_enter_moves_into_the_link(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
const row = { dataset: { id: "b1" } };
const tag = { closest: (s) => (s === ".row" ? row : null) };
$("#rows").listeners.focusin.forEach((fn) => fn({ target: { closest: (s) => (s === ".state-clash" ? tag : null) } }));
const opened = S.tip.id;
const key = { key: "Enter", preventDefault() { key.prevented = true; }, stopPropagation() {} };
tipKey(key);
const focusedLink = focused.indexOf("#cx-tip-go") >= 0;
const esc = { key: "Escape", preventDefault() {}, stopPropagation() {} };
tipKey(esc);
out.push({ opened, prevented: !!key.prevented, focusedLink, closed: S.tip.id });
""")[0]
        self.assertEqual(out["opened"], "b1")
        self.assertTrue(out["prevented"])
        self.assertTrue(out["focusedLink"], "Enter 把焦点移进气泡里的「去已报名那场」")
        self.assertEqual(out["closed"], "")

    def test_bubble_flips_above_when_there_is_no_room_below(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
const rect = (o) => Object.assign({ left: 700, right: 1000, width: 300, height: 56 }, o);
const mkRow = (top) => ({
  getBoundingClientRect: () => rect({ top: top, bottom: top + 56 }),
  querySelector: () => ({ getBoundingClientRect: () => rect({ top: top + 18, bottom: top + 38, left: 900, right: 960, width: 60 }) }),
});
function place(top) {
  const el = mkRow(top);
  S.rowEls.set("b1", { row: el, state: { getBoundingClientRect: () => rect({ top: top, bottom: top + 56 }) } });
  S.tip.id = "";
  tipOpen("b1");
  S.rowEls.set("b1", { row: el, state: { getBoundingClientRect: () => rect({ top: top, bottom: top + 56 }) } });
  placeTip();
  const box = $("#cx-tip");
  return { top: box.style.top, up: box.dataset.placed, vis: box.style.visibility };
}
out.push({ low: place(200), high: place(700) });
""")[0]
        self.assertEqual(out["low"]["up"], "down")
        self.assertEqual(out["low"]["top"], "264px", "放得下：行下沿 + 8")
        self.assertEqual(out["high"]["up"], "up", "下面放不下才翻到行上方")
        self.assertEqual(out["high"]["vis"], "visible")

    def test_go_to_signed_row_clears_a_hiding_filter_and_flashes_it(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
S.filter.status = "free";                       // 「可报名」筛选把已报名那场藏起来了
tipOpen("b1");
const hiddenBefore = !filtered().some((i) => i.id === "s1");
tipGoSigned();
out.push({ hiddenBefore, status: S.filter.status, shown: filtered().some((i) => i.id === "s1"),
           flash: S.flashId, tip: S.tip.id, rowCls: rowHtml(findItem("s1")).indexOf("is-flash") >= 0 });
""")[0]
        self.assertTrue(out["hiddenBefore"])
        self.assertEqual(out["status"], "all")
        self.assertTrue(out["shown"])
        self.assertEqual(out["flash"], "s1")
        self.assertEqual(out["tip"], "", "跳转后气泡收起")
        self.assertTrue(out["rowCls"], "那一行带高亮样式")


class TimeTextTests(unittest.TestCase):
    """跨天时段如实显示：绝对日期、跨 N 天，结束恰为 00:00 算前一天；一律用业务时钟。"""

    def test_cross_day_and_same_day(self):
        out = run_js(SETUP + r"""
const mk = (s, e) => Object.assign({}, clashB, { act_start: s, act_end: e });
out.push({
  cross: activityTimeText(mk("2026-11-08 22:40:00", "2026-11-10 23:20:00")),
  same: activityTimeText(mk("2026-11-07 09:00:00", "2026-11-07 11:30:00")),
  midnight1: activityTimeText(mk("2026-11-08 22:00:00", "2026-11-09 00:00:00")),
  midnight3: activityTimeText(mk("2026-11-08 22:40:00", "2026-11-11 00:00:00")),
  two: activityTimeText(mk("2026-11-08 22:00:00", "2026-11-09 02:00:00")),
  days: [spanDays(mk("2026-11-08 22:40:00", "2026-11-10 23:20:00")), spanDays(mk("2026-11-08 22:40:00", "2026-11-11 00:00:00")),
         spanDays(mk("2026-11-08 22:00:00", "2026-11-09 00:00:00")), spanDays(mk("2026-11-08 09:00:00", "2026-11-08 10:00:00"))],
  bad: activityTimeText(mk("", "")),
});
""")[0]
        self.assertEqual(out["cross"], "活动 11月8日 22:40 – 11月10日 23:20（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ))
        self.assertEqual(out["same"], "活动 11月7日 09:00 – 11:30".replace("11月7日", "明天"), "同一天仍是原来的写法")
        self.assertEqual(out["midnight1"], "活动 11月8日 22:00 – 24:00".replace("11月8日", "后天"),
                         "结束恰为 00:00 且只跨一天：算前一天，写 24:00")
        self.assertEqual(out["midnight3"], "活动 11月8日 22:40 – 11月11日 00:00（%s跨%s3%s天%s）" % (WJ, WJ, WJ, WJ),
                         "结束恰为 00:00：按前一天算，8、9、10 日共三天")
        self.assertEqual(out["two"], "活动 11月8日 22:00 – 11月9日 02:00（%s跨%s2%s天%s）" % (WJ, WJ, WJ, WJ))
        self.assertEqual(out["days"], [3, 3, 1, 1])
        self.assertEqual(out["bad"], "活动时间待确认")

    def test_not_read_from_the_wall_clock(self):
        text = (LOCAL / "ui" / "state" / "conflict.js").read_text(encoding="utf-8")
        self.assertNotIn("Date.now", text)
        self.assertNotIn("new Date()", text)


class RefundAndUntilTests(unittest.TestCase):
    def test_refund_flag_only_on_waiting_or_open_rows(self):
        out = run_js(SETUP + r"""
load([signedA, clashB, noRefundC, refundD]);
const nullRow = Object.assign({}, refundD, { id: "n1", name: "空白退改", cancel_allowed: null });
load([signedA, clashB, noRefundC, refundD, nullRow]);
out.push({ no: rowHtml(findItem("c1")), yes: rowHtml(findItem("d1")), nul: rowHtml(findItem("n1")), signed: rowHtml(findItem("s1")),
           states: [stateOf(findItem("c1")), stateOf(findItem("d1"))] });
""")[0]
        self.assertEqual(out["states"], ["waiting", "open"])
        self.assertIn('<span class="rf no">报后不可退</span>', out["no"])
        self.assertIn('<span class="rf">报后可退</span>', out["yes"])
        self.assertNotIn("报后", out["nul"], "cancel_allowed 为 null 时什么都不写")
        self.assertNotIn("报后", out["signed"])

    def test_until_and_button_only_when_allowed_and_inside_the_window(self):
        out = run_js(SETUP + r"""
const variants = {
  ok: signedA,
  no: Object.assign({}, signedA, { cancel_allowed: false }),
  nul: Object.assign({}, signedA, { cancel_allowed: null }),
  late: Object.assign({}, signedA, { sign_end: "2026-11-06 10:00:00" }),       // 报名截止已过
  early: Object.assign({}, signedA, { sign_start: "2026-11-07 08:00:00" }),    // 窗口还没开
};
const res = {};
Object.keys(variants).forEach((k) => { load([variants[k]]); res[k] = rowHtml(findItem("s1")); });
out.push(res);
""")[0]
        self.assertIn("可取消至 11月8日 14:00", out["ok"])
        self.assertIn('data-cancel="s1"', out["ok"])
        self.assertIn(">取消报名</button>", out["ok"])
        for key in ("no", "nul", "late", "early"):
            self.assertNotIn("可取消至", out[key], key)
            self.assertNotIn("data-cancel=", out[key], key)

    def test_clock_unavailable_hides_the_cancel_affordance(self):
        out = run_js(SETUP + r"""
load([signedA]);
S.businessClock.state = "unavailable";
out.push({ now: businessNowMs(), html: rowHtml(findItem("s1")) });
""")[0]
        self.assertIsNone(out["now"])
        self.assertNotIn("可取消至", out["html"])

    def test_plan_ticket_says_no_refund_only_for_false(self):
        out = run_js(SETUP + r"""
load([signedA, clashB, noRefundC, refundD]);
S.selected.add("c1"); S.selected.add("d1");
paintTickets();
out.push($("#plan-tickets").innerHTML);
""")[0]
        self.assertEqual(out.count("报后不可退"), 1)
        self.assertIn("职业规划讲座", out)


class CancelFlowTests(unittest.TestCase):
    """点「取消报名」只展开确认块；「不取消」不调接口；只有「确认取消报名」才调 cancel_signup。"""

    def test_ask_then_dismiss_never_calls_the_api(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
click("[data-cancel]", { cancel: "s1" });
const asked = { ask: S.cancel.askId, html: rowHtml(findItem("s1")), calls: calls.length };
click("[data-cancel-no]", { cancelNo: "s1" });
out.push({ asked, ask: S.cancel.askId, busy: S.cancel.busyId, calls: calls.length, html: rowHtml(findItem("s1")) });
""")[0]
        self.assertEqual(out["asked"]["ask"], "s1")
        self.assertIn("取消「宿舍查寝」的报名？取消后名额可能被别人报走，不能撤回。", out["asked"]["html"])
        self.assertIn(">不取消</button>", out["asked"]["html"])
        self.assertIn(">确认取消报名</button>", out["asked"]["html"])
        self.assertEqual(out["asked"]["calls"], 0, "只展开确认块，不调接口")
        self.assertEqual(out["ask"], "")
        self.assertEqual(out["busy"], "")
        self.assertEqual(out["calls"], 0, "点「不取消」不调 cancel_signup")
        self.assertNotIn("确认取消报名", out["html"])

    def test_confirm_calls_cancel_signup_once_and_marks_busy(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
click("[data-cancel]", { cancel: "s1" });
click("[data-cancel-yes]", { cancelYes: "s1" });
click("[data-cancel-yes]", { cancelYes: "s1" });        // 连点第二下不能再发
const during = { calls: calls.slice(), busy: S.cancel.busyId, html: rowHtml(findItem("s1")),
  refreshOff: $("#btn-refresh").disabled, planOff: $("#btn-plan").disabled, why: $("#plan-why").innerHTML };
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ during, after: { busy: S.cancel.busyId, res: S.cancel.res, signed: findItem("s1").signed } });
""")[0]
        self.assertEqual(out["during"]["calls"], ["s1"], "确认只调一次，参数是活动 id")
        self.assertEqual(out["during"]["busy"], "s1")
        self.assertIn("正在取消…", out["during"]["html"])
        self.assertRegex(out["during"]["html"], r'data-cancel="s1" disabled')
        self.assertTrue(out["during"]["refreshOff"], "取消进行中刷新置灰")
        self.assertTrue(out["during"]["planOff"], "取消进行中开始计划置灰")
        self.assertIn("正在取消报名，等它结束再开始", out["during"]["why"])
        self.assertEqual(out["after"]["busy"], "")
        self.assertEqual(out["after"]["res"], {"id": "s1", "kind": "cancelled"})
        self.assertFalse(out["after"]["signed"], "cancelled 之后这一场回到未报名")

    def test_result_sentences_are_verbatim(self):
        out = run_js(SETUP + r"""
load([signedA]);
const res = {};
function settle(key, reply) { S.cancel.busyId = "s1"; cancelSettle("s1", reply); res[key] = (rowHtml(findItem("s1")).match(/<p class="cx-res[^>]*>([^<]*)<\/p>/) || [])[0] || ""; }
settle("refused", { ok: false, kind: "refused", message: "活动已开始，不能取消" });
settle("unknown", { ok: false, kind: "unknown" });
const reasons = {};
["window_closed", "not_allowed", "not_signed", "not_in_list", "clock_unavailable", "login_expired", "unknown_state"].forEach((r) => {
  settle(r, { ok: false, kind: "precheck_failed", reason: r });
});
settle("busy", { ok: false, kind: "busy" });
// 已取消：回到未报名后行不再是已报名，结果句挂在它自己的行下面
S.cancel.busyId = "s1"; cancelSettle("s1", { ok: true, kind: "cancelled" });
res.cancelled = (rowHtml(findItem("s1")).match(/<p class="cx-res[^>]*>([^<]*)<\/p>/) || [])[0] || "";
out.push(res);
""")[0]
        self.assertIn('class="cx-res ok"', out["cancelled"])
        self.assertIn("已取消「宿舍查寝」的报名，学校记录已核对。", out["cancelled"])
        self.assertIn('class="cx-res bad"', out["refused"])
        self.assertIn("学校没有取消这场报名：活动已开始，不能取消", out["refused"])
        self.assertIn('class="cx-res warn"', out["unknown"])
        self.assertIn("没能确认是否已取消，请到学校网站的活动详情里核对。", out["unknown"])
        for code, text in (("window_closed", "取消时间已过"), ("not_allowed", "这个活动报名后不能取消"),
                           ("not_signed", "学校记录里没有这场报名"), ("not_in_list", "学校记录里没有这场报名"),
                           ("clock_unavailable", "北京时间暂不可用")):
            self.assertIn("现在不能取消：" + text + "</p>", out[code], code)
        self.assertIn("现在不能取消：登录已失效</p>", out["login_expired"])
        self.assertIn("现在不能取消：暂时无法确认这场的报名状态</p>", out["unknown_state"])
        self.assertIn("现在不能取消：", out["busy"])

    def test_buttons_are_disabled_with_a_reason_while_other_work_runs(self):
        out = run_js(SETUP + r"""
load([signedA, clashB]);
const html = () => rowHtml(findItem("s1"));
const free = html();
S.busy = true; const planRuns = html(); S.busy = false;
S.listState = "loading"; const refreshing = html(); S.listState = "ready";
S.login.checking = true; const checking = html(); S.login.checking = false;
S.login.loginPending = true; const loggingIn = html(); S.login.loginPending = false;
S.cancel.busyId = "other"; const anotherCancel = html(); S.cancel.busyId = "";
// 计划运行中点取消：什么都不发生
S.busy = true; cancelAsk("s1"); const askedWhileBusy = S.cancel.askId; S.busy = false;
out.push({ free, planRuns, refreshing, checking, loggingIn, anotherCancel, askedWhileBusy });
""")[0]
        self.assertNotRegex(out["free"], r'data-cancel="s1" disabled')
        self.assertRegex(out["planRuns"], r'data-cancel="s1" disabled title="计划在运行，先停下来再取消"')
        self.assertIn('title="正在刷新，等它结束再取消"', out["refreshing"])
        self.assertIn('title="正在刷新，等它结束再取消"', out["checking"])
        self.assertIn('title="正在登录，等它结束再取消"', out["loggingIn"])
        self.assertIn('title="正在取消另一场"', out["anotherCancel"])
        self.assertEqual(out["askedWhileBusy"], "")

    def test_refresh_and_start_are_blocked_while_cancelling(self):
        out = run_js(SETUP + r"""
load([signedA, clashB, noRefundC]);
S.selected.add("c1");
let refreshCalls = 0;
window.pywebview.api.check = () => { refreshCalls += 1; return Promise.resolve({ ok: true }); };
S.cancel.busyId = "s1";
refresh(false);
startPlan();
out.push({ refreshCalls, starting: S.starting, blocker: startBlocker() });
""")[0]
        self.assertEqual(out["refreshCalls"], 0, "取消期间 F5 与自动刷新都不放行")
        self.assertFalse(out["starting"])
        self.assertEqual(out["blocker"], {"text": "正在取消报名，等它结束再开始"})

    def test_manual_refresh_clears_the_result_but_the_auto_one_keeps_it(self):
        out = run_js(SETUP + r"""
load([signedA]);
S.cancel.res = { id: "s1", kind: "unknown" };
refresh(true);
const afterQuiet = S.cancel.res;
refresh(false);
out.push({ afterQuiet, afterManual: S.cancel.res });
""")[0]
        self.assertEqual(out["afterQuiet"], {"id": "s1", "kind": "unknown"})
        self.assertIsNone(out["afterManual"])

    def test_window_closing_while_the_confirm_is_open_is_caught_without_calling(self):
        out = run_js(SETUP + r"""
load([signedA]);
cancelAsk("s1");
setBusinessNow(Date.UTC(2026, 10, 8, 7, 0, 0));      // 11-08 15:00：报名截止（14:00）已过
cancelConfirm("s1");
out.push({ calls: calls.length, res: S.cancel.res, busy: S.cancel.busyId });
""")[0]
        self.assertEqual(out["calls"], 0)
        self.assertEqual(out["res"], {"id": "s1", "kind": "precheck", "reason": "window_closed"})
        self.assertEqual(out["busy"], "")

    def test_bridge_failure_is_reported_as_unknown_not_success(self):
        out = run_js(SETUP + r"""
load([signedA]);
window.pywebview.api.cancel_signup = () => Promise.reject(new Error("桥断了"));
cancelAsk("s1"); cancelConfirm("s1");
for (let i = 0; i < 20; i += 1) await Promise.resolve();
out.push({ res: S.cancel.res, signed: findItem("s1").signed, busy: S.cancel.busyId });
""")[0]
        self.assertEqual(out["res"], {"id": "s1", "kind": "unknown"})
        self.assertTrue(out["signed"], "没拿到回执就不能把这一场画成已取消")
        self.assertEqual(out["busy"], "")

    def test_cancelled_reply_does_not_touch_the_run_log_with_school_text(self):
        out = run_js(SETUP + r"""
load([signedA]);
const logged = [];
const origAdd = addLog;
addLog = (line) => { logged.push(String(line)); };
S.cancel.busyId = "s1";
cancelSettle("s1", { ok: false, kind: "refused", message: "学校原话XYZ" });
addLog = origAdd;
out.push({ logged, say: S.cancel.res.say });
""")[0]
        self.assertEqual(out["say"], "学校原话XYZ", "学校原话只给界面显示")
        self.assertTrue(out["logged"])
        self.assertFalse([line for line in out["logged"] if "学校原话XYZ" in line], "运行记录只记结果类别")


class CancelWiringContractTests(unittest.TestCase):
    def test_only_the_confirm_path_calls_cancel_signup(self):
        scripts = read_ui_scripts()
        self.assertEqual(scripts.count('api("cancel_signup"'), 1)
        text = (LOCAL / "ui" / "controllers" / "cancel.js").read_text(encoding="utf-8")
        dismiss = text[text.index("function cancelAskDismiss"):text.index("function cancelSettle")]
        self.assertNotIn("cancel_signup", dismiss)
        ask = text[text.index("function cancelAsk("):text.index("function cancelAskDismiss")]
        self.assertNotIn("cancel_signup", ask)

    def test_new_scripts_are_loaded_in_index_html(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        for src in ("state/conflict.js", "views/conflict-tip.js", "controllers/cancel.js"):
            self.assertIn('<script src="%s"></script>' % src, html)
        self.assertIn('id="cx-tip"', html)


if __name__ == "__main__":
    unittest.main()
