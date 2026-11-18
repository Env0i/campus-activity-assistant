#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_ui_main_window.py（来源：test_ui_main_window_list.py, test_ui_main_window_plan.py, test_ui_conflict_cancel.py, test_ui_rewards.py, test_terms_consent.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_ui_main_window_list.py ====================
"""主窗口向原型 1:1 的列表半边（计划 20261108-main-window，fe-list）。

覆盖：更多筛选折叠与计数（LS06）、分组顺序（LS01）、空态与横幅文案（LS08 / LS12 / LS13 / LS16 / LS18 / LS21）、
待公布行禁选（LS14）、列表失败写运行记录（LS11）、工具已经开着（GL01）、顶栏 title（TF02）。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
断行与像素以 Edge/WebView2 截图为准，这里不测。

@author Author
"""

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, run_js  # noqa: E402

# 业务现在 = 北京时间 2026-11-06 14:00
SETUP = r"""
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const base = { place: "学生公寓", checkin_required: false, checkout_required: false };
function mk(id, name, extra) {
  return Object.assign({}, base, { id: id, name: name, signed: false,
    sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-08 09:00:00",
    act_start: "2026-11-09 09:00:00", act_end: "2026-11-09 11:00:00" }, extra || {});
}
function load(items) {
  window.onBackend.activities({ ok: true, items: items.map((it) => Object.assign({}, it)) });
}
const logs = () => S.recentLogs.slice();
/* 运行记录真正多出的行数：recentLogs 只是去重窗口，数不出重复；数 #log 上的追加才是用户看到的行数 */
const appended = [];
const logBox = $("#log");
const origAppend = logBox.appendChild;
logBox.appendChild = (child) => { appended.push(child.textContent); return origAppend(child); };
"""


def read(rel: str) -> str:
    return (LOCAL / "ui" / rel).read_text(encoding="utf-8")


class HeaderMarkupTests(unittest.TestCase):
    """TF02：顶栏三个按钮的 title 与品牌副句。"""

    def test_header_titles_follow_the_prototype_and_brand_has_no_subline(self):
        html = read("index.html")
        self.assertNotIn("活动查询与报名计划", html, "品牌副句原型没有，已删")
        self.assertNotIn("brand-desc", html)
        self.assertNotIn("brand-desc", read("styles.css"), "副句删了，样式一并清掉")
        for button_id, title in (("btn-refresh", "刷新（F5）"), ("btn-settings", "设置"), ("btn-help", "帮助")):
            start = html.index('id="%s"' % button_id)
            tag = html[start:html.index(">", start)]
            self.assertIn('title="%s"' % title, tag)
        # 刷新按钮窄档只剩图标：可访问名字保留原来的完整说法
        start = html.index('id="btn-refresh"')
        self.assertIn('aria-label="刷新登录状态和活动列表"', html[start:html.index(">", start)])


class MoreFiltersMarkupTests(unittest.TestCase):
    """LS06：筛选行 = 搜索 + 三段 + 「更多筛选」；四个下拉在展开面板里。"""

    def test_selects_live_in_the_collapsible_panel(self):
        html = read("index.html")
        filters_start = html.index('<div class="filters"')
        more_start = html.index('id="more-filters"')
        row = html[filters_start:more_start]
        panel = html[more_start:html.index("</div>", more_start)]
        self.assertIn('id="q"', row)
        self.assertIn('id="chips"', row)
        self.assertIn('id="btn-more"', row)
        self.assertIn('aria-expanded="false"', row)
        self.assertIn('aria-controls="more-filters"', row)
        for key in ("time", "sort", "checkin", "checkout"):
            self.assertNotIn('id="%s"' % key, row, "%s 下拉不再常驻筛选行" % key)
            self.assertIn('id="%s"' % key, panel, "%s 下拉进了面板" % key)
        self.assertIn("hidden", html[more_start - 40:more_start + 60], "面板默认收起")
        css = read("styles.css")
        for selector in (".fbtn", ".more", ".fsel", '.banner[data-tone="note"]'):
            self.assertIn(selector, css)


class MoreFiltersBehaviorTests(unittest.TestCase):
    """折叠按钮的计数、展开与收起、偏好记忆、清除筛选归零。"""

    def test_count_open_and_clear(self):
        out = run_js(SETUP + r"""
const snap = () => ({
  label: $("#more-label").textContent,
  on: $("#btn-more").classList.contains("on"),
  expanded: $("#btn-more").getAttribute("aria-expanded"),
  hidden: $("#more-filters").hidden,
});
load([mk("a1", "活动甲")]);
const s0 = snap();
setFilter("sort", "name");
const s1 = snap();
setFilter("checkin", "yes");
setFilter("time", "today");
const s3 = snap();
/* 搜索词和状态胶囊常驻筛选行，不算进「更多筛选」的计数 */
setFilter("q", "甲");
setFilter("status", "free");
const sQ = snap();
/* 值改回默认，计数跟着少 */
setFilter("time", "all");
const s2 = snap();
setFilterOpen(true);
const sOpen = snap();
const savedOpen = S.savePending.filter_open;
setFilterOpen(false);
const sClosed = snap();
const savedClosed = S.savePending.filter_open;
setFilterOpen(true);
clearFilters();
const sClear = snap();
out.push({ s0, s1, s3, sQ, s2, sOpen, savedOpen, sClosed, savedClosed, sClear,
  filter: Object.assign({}, S.filter), savedFilter: S.savePending.filter });
""")[0]
        self.assertEqual(out["s0"], {"label": "更多筛选", "on": False, "expanded": "false", "hidden": True})
        self.assertEqual(out["s1"]["label"], "更多筛选（1）")
        self.assertTrue(out["s1"]["on"], "有非默认项时按钮加 on 样式")
        self.assertEqual(out["s3"]["label"], "更多筛选（3）")
        self.assertEqual(out["sQ"]["label"], "更多筛选（3）", "搜索词与状态胶囊不计数")
        self.assertEqual(out["s2"]["label"], "更多筛选（2）")
        self.assertEqual(out["sOpen"]["expanded"], "true", "aria-expanded 跟展开状态")
        self.assertFalse(out["sOpen"]["hidden"])
        self.assertIs(out["savedOpen"], True, "展开状态记进偏好 filter_open")
        self.assertEqual(out["sClosed"]["expanded"], "false")
        self.assertTrue(out["sClosed"]["hidden"])
        self.assertIs(out["savedClosed"], False)
        self.assertEqual(out["sClear"]["label"], "更多筛选", "清除筛选后计数归零")
        self.assertEqual(out["sClear"]["expanded"], "true", "清除筛选不动展开状态")
        self.assertEqual(out["filter"], {"q": "", "status": "all", "time": "all", "sort": "open",
                                         "checkin": "all", "checkout": "all"})
        self.assertEqual(out["savedFilter"]["sort"], "open")

    def test_open_state_and_count_come_back_from_prefs(self):
        out = run_js(SETUP + r"""
applyPrefs({ filter_open: true, filter: { sort: "name", checkout: "no" } });
render();
const open = { label: $("#more-label").textContent, hidden: $("#more-filters").hidden };
applyPrefs({ filter: {} });
render();
out.push({ open, closed: { label: $("#more-label").textContent, hidden: $("#more-filters").hidden } });
""")[0]
        self.assertEqual(out["open"], {"label": "更多筛选（2）", "hidden": False})
        self.assertEqual(out["closed"], {"label": "更多筛选", "hidden": True})

    def test_button_click_toggles_through_the_listener(self):
        out = run_js(SETUP + r"""
const fire = () => $("#btn-more").listeners.click.forEach((fn) => fn({ target: $("#btn-more"), preventDefault() {} }));
fire();
const first = $("#more-filters").hidden;
fire();
out.push({ first, second: $("#more-filters").hidden });
""")[0]
        self.assertFalse(out["first"])
        self.assertTrue(out["second"])


class GroupOrderAndEmptyStateTests(unittest.TestCase):
    """LS01 分组顺序、LS08 / LS12 / LS16 空态文案。"""

    def test_groups_run_unknown_then_signed_then_closed(self):
        out = run_js(SETUP + r"""
load([
  mk("o1", "开放中的", { sign_start: "2026-11-06 09:00:00", sign_end: "2026-11-06 18:00:00" }),
  mk("w1", "明天开的"),
  mk("u1", "时间待公布的", { sign_start: "" }),
  mk("c1", "已经截止的", { sign_start: "2026-11-01 09:00:00", sign_end: "2026-11-05 09:00:00" }),
  mk("s1", "已经报名的", { signed: true }),
]);
const html = groupTimetable(filtered());
const at = (label) => html.indexOf("<b>" + label + "</b>");
out.push({ open: at("正在开放"), unknown: at("报名时间待公布"), signed: at("已报名"), closed: at("已截止"),
  days: html.indexOf('data-g="day"') });
""")[0]
        self.assertTrue(0 <= out["open"] < out["days"] < out["unknown"] < out["signed"] < out["closed"],
                        "正在开放 → 按天 → 待公布 → 已报名 → 已截止：%s" % out)

    def test_no_result_body_uses_a_full_stop(self):
        out = run_js(SETUP + r"""
load([mk("a1", "活动甲"), mk("a2", "活动乙")]);
setFilter("q", "不存在的关键词");
out.push({ title: $("#empty-title").textContent, text: $("#empty-text").textContent,
  action: $("#empty-action").textContent, intent: $("#empty-action").dataset.action });
""")[0]
        self.assertEqual(out["title"], "没有符合筛选的活动")
        self.assertEqual(out["text"], "一共 2 场。换个关键词，或清除筛选看完整列表。")
        self.assertEqual(out["action"], "清除筛选")
        self.assertEqual(out["intent"], "clear-filters")

    def test_list_error_body_and_button(self):
        out = run_js(SETUP + r"""
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.listState = "error"; S.listError = "连不上";
render();
out.push({ title: $("#empty-title").textContent, text: $("#empty-text").textContent,
  action: $("#empty-action").textContent, intent: $("#empty-action").dataset.action });
""")[0]
        self.assertEqual(out["title"], "活动暂时没加载")
        # 评审修正：原型在这句里把「刷」「新」用 U+2060 连住，免得按钮名在 Edge 里被断成两行；句子本身没变。
        self.assertEqual(out["text"], "连不上学校站点，已保存的登录不受影响。检查网络后点“刷⁠新”。")
        self.assertEqual(out["action"], "刷新")
        self.assertEqual(out["intent"], "refresh")

    def test_broken_empty_title_keeps_the_three_runtime_error_banners(self):
        out = run_js(SETUP + r"""
const res = {};
["worker_missing", "worker_permission", "spawn_failed"].forEach((code) => {
  S.runtime.error = code;
  render();
  res[code] = { title: $("#empty-title").textContent, banner: $("#banners").innerHTML.replace(/<[^>]*>/g, "") };
});
out.push(res);
""")[0]
        titles = {key: value["title"] for key, value in out.items()}
        self.assertEqual(set(titles.values()), {"活动列表没加载"})
        banners = [value["banner"] for value in out.values()]
        self.assertIn("程序组件缺失", banners[0])
        self.assertIn("程序组件无法读取", banners[1])
        self.assertIn("程序组件启动失败", banners[2])


class UnpublishedRowTests(unittest.TestCase):
    """LS14：报名时间待公布的行复选框禁用；时钟不可用（待校准）的行照原型不禁。"""

    def test_unpublished_row_is_disabled_but_others_are_not(self):
        out = run_js(SETUP + r"""
load([
  mk("u1", "时间待公布的", { sign_start: "" }),
  mk("w1", "明天开的"),
  mk("o1", "开放中的", { sign_start: "2026-11-06 09:00:00", sign_end: "2026-11-06 18:00:00" }),
]);
const dis = (id) => /<input class="row-check"[^>]*disabled/.test(rowHtml(findItem(id)));
const before = { u1: dis("u1"), w1: dis("w1"), o1: dis("o1") };
/* 业务时钟不可用：开放时刻已知的行是「待校准」，原型 ClockDown 里照常可勾；没公布时刻的行仍禁 */
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 99, state: "unavailable",
  epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0, source: "qa", age_s: 0, reason: "测试注入" });
render();
const down = { u1: dis("u1"), w1: dis("w1"), unavailable: businessNowMs() === null,
  w1State: rowHtml(findItem("w1")).indexOf("待校准") >= 0, u1Text: rowHtml(findItem("u1")).indexOf("待公布") >= 0 };
out.push({ before, down });
""")[0]
        self.assertEqual(out["before"], {"u1": True, "w1": False, "o1": False})
        self.assertTrue(out["down"]["unavailable"], "前置：业务时钟确实不可用")
        self.assertTrue(out["down"]["u1"], "没公布开放时间的行在时钟不可用时仍禁勾")
        self.assertFalse(out["down"]["w1"], "开放时刻已知、只是待校准的行不禁，和原型 ClockDown 一致")
        self.assertTrue(out["down"]["w1State"])
        self.assertTrue(out["down"]["u1Text"])


class ListFailureLogTests(unittest.TestCase):
    """LS11：列表加载失败的三条路（错误回包、Promise 失败、130 秒超时）各写一条运行记录。"""

    def test_error_reply_logs_one_line(self):
        out = run_js(SETUP + r"""
window.onBackend.activities({ ok: false, text: "连不上学校站点" });
out.push({ logs: logs(), last: $("#log-last").textContent, state: S.listState });
""")[0]
        self.assertEqual(out["state"], "error")
        self.assertEqual(out["logs"], ["活动列表没加载：连不上学校站点"])
        self.assertTrue(out["last"].endswith("活动列表没加载：连不上学校站点"))

    def test_promise_rejection_logs_one_line(self):
        out = run_js(SETUP + r"""
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: true }),
  list_activities: () => Promise.reject(new Error("桥接断了")),
} };
refresh(false);
for (let i = 0; i < 6; i += 1) await Promise.resolve();
out.push({ logs: logs().filter((line) => line.indexOf("活动列表没加载") >= 0), state: S.listState });
""")[0]
        self.assertEqual(out["state"], "error")
        # 评审修正：运行记录只写用户看得懂的原因（与空态同一套归因），不回显原始异常文本
        self.assertEqual(out["logs"], ["活动列表没加载：连不上学校站点"])

    def test_timeout_logs_one_line(self):
        out = run_js(SETUP + r"""
const timers = [];
setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: true }),
  list_activities: () => new Promise(() => {}),
} };
refresh(false);
const slow = timers.filter((t) => t.ms === 130000);
slow.forEach((t) => t.fn());
out.push({ count: slow.length, logs: logs().filter((line) => line.indexOf("活动列表没加载") >= 0), state: S.listState });
""")[0]
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["state"], "error")
        # 评审修正：超时也按空态同一套归因写成用户看得懂的原因，不把内部秒数当原因
        self.assertEqual(out["logs"], ["活动列表没加载：连不上学校站点"])

    def test_raw_exception_names_never_reach_the_log_line(self):
        # 评审修正：接口回包的原始原因（如 URLError）不进运行记录，只写与空态同一套归因的第一个分句
        out = run_js(SETUP + r"""
window.onBackend.activities({ ok: false, text: "接口异常：URLError" });
out.push({ logs: logs(), last: $("#log-last").textContent, empty: $("#empty-text").textContent });
""")[0]
        self.assertEqual(out["logs"], ["活动列表没加载：连不上学校站点"])
        self.assertNotIn("URLError", out["last"])
        self.assertNotIn("接口异常", out["last"])

    def test_second_failure_is_visible_but_back_to_back_repeats_are_not(self):
        out = run_js(SETUP + r"""
window.onBackend.activities({ ok: false, text: "连不上学校站点" });
window.onBackend.activities({ ok: false, text: "连不上学校站点" });
const afterTwo = logs().length;
addLog("中间有别的记录");
window.onBackend.activities({ ok: false, text: "连不上学校站点" });
out.push({ afterTwo, shown: appended.map((line) => line.replace(/^\S+\s+/, "")) });
""")[0]
        self.assertEqual(out["afterTwo"], 1, "紧挨着的同一句不重复写")
        self.assertEqual(out["shown"], ["活动列表没加载：连不上学校站点", "中间有别的记录", "活动列表没加载：连不上学校站点"],
                         "隔了别的记录再失败，要让用户看见新的一行")


class BannerTests(unittest.TestCase):
    """LS13 / LS18 / LS21 横幅文案，GL01 工具已经开着。"""

    def test_unknown_and_expired_login_banners(self):
        out = run_js(SETUP + r"""
const text = () => $("#banners").innerHTML.replace(/<[^>]*>/g, "");
S.login.view = { state: "unknown" };
paintBanners();
const unknown = { text: text(), html: $("#banners").innerHTML };
S.login.view = { state: "bad" };
paintBanners();
const draft = text();
S.busy = true;
paintBanners();
const running = text();
out.push({ unknown, draft, running });
""")[0]
        self.assertIn("检查网络后点“刷新”，先不用重新登录。", out["unknown"]["text"])
        self.assertNotIn("「刷新」，先不用", out["unknown"]["text"])
        self.assertIn('data-act="runtime-refresh">刷新</button>', out["unknown"]["html"])
        self.assertEqual(out["draft"], "登录已失效。重新登录后可以继续。重新登录")
        self.assertIn("报名计划还在等，开放前 100 秒以前重新登录就照常继续。", out["running"])

    def test_sleep_banner_names_the_missed_activities(self):
        out = run_js(SETUP + r"""
const stamp = (text) => toTs(text);
load([
  mk("m1", "人工智能与未来职业", { sign_start: "2026-11-06 13:50:00", sign_end: "2026-11-06 18:00:00" }),
  mk("m2", "志愿服务培训", { sign_start: "2026-11-06 13:55:00", sign_end: "2026-11-06 18:00:00" }),
  mk("ok", "睡前已经提交的", { sign_start: "2026-11-06 13:45:00", sign_end: "2026-11-06 18:00:00" }),
  mk("out", "睡眠之前开的", { sign_start: "2026-11-06 12:00:00", sign_end: "2026-11-06 18:00:00" }),
]);
const task = (id, activity, extra) => S.plan.tasks.set(id, Object.assign({ task_id: id, activity_id: activity, status: "waiting", attempts: 0 }, extra || {}));
task("t1", "m1", { name: "人工智能与未来职业" });
task("t2", "m2", { name: "志愿服务培训" });
task("t3", "ok", { name: "睡前已经提交的", status: "success", attempts: 1 });
task("t4", "out", { name: "睡眠之前开的" });
S.sleepGap = 23 * 60000 + 20000;
S.sleepWindow = { from: stamp("2026-11-06 13:37:00"), to: stamp("2026-11-06 14:00:00") };
paintBanners();
const html = $("#banners").innerHTML;
const named = html.replace(/<[^>]*>/g, "");
const rows = { m1: rowHtml(findItem("m1")), ok: rowHtml(findItem("ok")), out: rowHtml(findItem("out")) };
/* 点名的场次一场都没有 */
S.plan.tasks.clear();
paintBanners();
const none = $("#banners").innerHTML.replace(/<[^>]*>/g, "");
/* 睡眠窗口没记下来（当时业务时钟不可用）：不断言「没有场次」 */
S.sleepWindow = null;
paintBanners();
const unknownWindow = $("#banners").innerHTML.replace(/<[^>]*>/g, "");
out.push({ html, named, none, unknownWindow, rows });
""")[0]
        self.assertEqual(out["named"], "电脑刚才睡眠了约 23 分钟。"
                         "期间「人工智能与未来职业」「志愿服务培训」到了开放时间，没有提交。知道了")
        self.assertIn('data-tone="warn"', out["html"])
        self.assertIn('data-act="sleep-ok">知道了</button>', out["html"])
        self.assertEqual(out["none"], "电脑刚才睡眠了约 23 分钟。期间没有场次到开放时间。知道了")
        self.assertIn("要是睡过了开放时间", out["unknownWindow"])
        self.assertNotIn("期间没有场次", out["unknownWindow"])
        # 横幅点名的和时刻表行上标「错过了」的是同一批（同一条 missedBySleep 判据）
        self.assertIn("state-missed", out["rows"]["m1"])
        self.assertNotIn("state-missed", out["rows"]["ok"])
        self.assertNotIn("state-missed", out["rows"]["out"])

    def test_second_open_shows_a_note_banner_and_a_log_line(self):
        out = run_js(SETUP + r"""
const html0 = $("#banners").innerHTML;
window.onBackend.second_open({ at: null });
const html1 = $("#banners").innerHTML;
const lines1 = appended.length;
/* 再来一次：横幅还在，记录是新的一行（中间隔了别的记录）而不是被吞 */
addLog("中间有别的记录");
window.onBackend.second_open({ at: 1790000000 });
const shown = appended.map((line) => line.replace(/^\S+\s+/, ""));
$("#banners").listeners.click.forEach((fn) => fn({ target: { closest: (sel) => (sel === '[data-act="second-ok"]' ? {} : null) } }));
out.push({ html0, html1, lines1, shown, after: $("#banners").innerHTML, flag: S.secondOpen });
""")[0]
        self.assertEqual(out["html0"], "")
        html = out["html1"]
        self.assertIn('data-tone="note"', html)
        self.assertIn("<b>工具已经开着。</b>", html)
        self.assertIn("刚才又打开了一次，已切回这个窗口。同一台电脑只运行一份，免得同一场被提交两遍。", html)
        self.assertIn('data-act="second-ok">知道了</button>', html)
        self.assertEqual(out["lines1"], 1)
        self.assertEqual(out["shown"], ["又打开了一次，已切回这个窗口", "中间有别的记录", "又打开了一次，已切回这个窗口"])
        self.assertEqual(out["after"], "", "点「知道了」收起")
        self.assertFalse(out["flag"])

    def test_note_banner_sits_after_the_clock_banner(self):
        out = run_js(SETUP + r"""
const realClock = clockUiState;
const title = () => ($("#banners").innerHTML.match(/<b>([^<]*)<\/b>/) || [])[1] || "";
S.secondOpen = true;
S.sleepGap = 300000;
S.sleepWindow = { from: 0, to: 1 };
const withSleep = (paintBanners(), title());
S.sleepGap = 0;
clockUiState = () => "unavailable";
const withClock = (paintBanners(), title());
clockUiState = realClock;
const alone = (paintBanners(), title());
out.push({ withSleep, withClock, alone });
""")[0]
        self.assertTrue(out["withSleep"].startswith("电脑刚才睡眠了约"))
        self.assertEqual(out["withClock"], "北京时间还没校准。")
        self.assertEqual(out["alone"], "工具已经开着。")

# ==================== 源自 test_ui_main_window_plan.py ====================
"""主窗口向原型 1:1 的计划半边（计划 20261108-main-window，fe-plan）。

覆盖：窄档 dock 四态的文案（TF05 / PB16）、结果页「错过了」的计数 / 结论 / 任务卡动词（LS22 / PB15）、
修改计划与手机开始计划的两句运行记录（PB03 / PB11）、重试选项标签的空格（GL06）、
超 24 小时提醒里「这段时间」的断行连接符。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
断行与像素以 Edge/WebView2 截图为准，这里不测。

@author Author
"""


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))



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
/* features/plan/actions.js 正常事件没跑（没 emit），所以 S.plan.id 还是 "ph1"，
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
        self.assertIn("这段时⁠间电⁠脑不能关机或睡眠。", read("features/plan/state-draft.js"))
        self.assertNotIn("这段时间电脑不能关机或睡眠。", read("features/plan/state-draft.js"))


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
        """PB03 / U9：停止真的成功、计划以 stopped 结束时才给一句；
        改了又停、停了又改的两轮各一句，不被整句去重吞掉。"""
        out = run_js(PLAN_SETUP + r"""
load([
  mk("w1", "晚点开放甲", { sign_start: "2026-11-06 16:00:00" }),
  mk("w2", "晚点开放乙", { sign_start: "2026-11-06 16:30:00" }),
  mk("d1", "已经结束的", { sign_start: "2026-11-06 13:00:00" }),
]);
/* 每一轮：一份运行中的计划（两场还没提交、一场已成功），停止请求悬着 */
const beginRound = (planId) => {
  S.busy = true; S.stopping = false;
  S.plan = { id: planId, status: "running", tasks: new Map() };
  task(planId + "t1", "w1", { name: "晚点开放甲", sign_start: "2026-11-06 16:00:00" });
  task(planId + "t2", "w2", { name: "晚点开放乙", sign_start: "2026-11-06 16:30:00", status: "queued" });
  task(planId + "t3", "d1", { name: "已经结束的", status: "success", attempts: 1 });
};
window.pywebview = { api: { stop_plan: () => new Promise(() => {}) } };
const before = appended.length;
/* 第一轮：改了，停止请求发出去还没回；此刻运行记录里不能有「计划已暂停」 */
beginRound("p1");
modifyPlan();
const pending = bare(appended.slice(before)).filter((line) => line.indexOf("计划已暂停") >= 0);
window.onBackend.plan_done({ plan_id: "p1", status: "stopped", plan_generation: 1, summary: {} });
const first = bare(appended.slice(before));
/* 第二轮：改了又停、停了又改。中间隔了别的记录，同一句要再出现一次（不被整句去重吞掉） */
addLog("中间有别的记录");
const mark = appended.length;
beginRound("p2");
modifyPlan();
window.onBackend.plan_done({ plan_id: "p2", status: "stopped", plan_generation: 2, summary: {} });
const second = bare(appended.slice(mark));
out.push({ pending, first, second, all: bare(appended.slice(before)), editing: S.editing });
""")[0]
        self.assertEqual(out["pending"], [], "停止还没成功，不能先写「计划已暂停」：%r" % out["pending"])
        self.assertEqual(out["first"].count("计划已暂停：2 场放回草稿修改"), 1,
                         "停止成功后才写，且只写一句：%r" % out["first"])
        self.assertEqual(out["second"].count("计划已暂停：2 场放回草稿修改"), 1,
                         "第二轮再停再写一句：%r" % out["second"])
        self.assertEqual(sum(1 for line in out["all"] if line == "计划已暂停：2 场放回草稿修改"), 2,
                         "两轮各一句，不被整句去重吞掉")
        self.assertNotIn("修改计划：先停下，改完要重新开始", "".join(out["all"]), "旧句已换掉")

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
        controller = read("features/plan/actions-run.js") + read("features/plan/actions-start.js")
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

# ==================== 源自 test_ui_conflict_cancel.py ====================
"""电脑端：冲突原因气泡、跨天时段、报后可退、可取消至、取消报名（计划 20261107-conflict-cancel，fe-desktop）。

全部在 node 沙箱里跑真实的界面脚本（按 index.html 加载序），学校接口一律用本地桩，不连网。
断行与像素以 Edge/WebView2 截图为准，这里不测；定位（翻到行上方）用桩出来的矩形验算。

@author Author
"""


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import read_ui_scripts  # noqa: E402

WJ = "⁠"

# 业务现在 = 北京时间 2026-11-06 14:00；三场活动，名字用通用名
CONFLICT_SETUP = r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + HOVER + r"""
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
        out = run_js(CONFLICT_SETUP + HOVER + r"""
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
        out = run_js(CONFLICT_SETUP + HOVER + r"""
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
        out = run_js(CONFLICT_SETUP + HOVER + r"""
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
        out = run_js(CONFLICT_SETUP + HOVER + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
load([signedA]);
S.businessClock.state = "unavailable";
out.push({ now: businessNowMs(), html: rowHtml(findItem("s1")) });
""")[0]
        self.assertIsNone(out["now"])
        self.assertNotIn("可取消至", out["html"])

    def test_plan_ticket_says_no_refund_only_for_false(self):
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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
        out = run_js(CONFLICT_SETUP + r"""
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

# ==================== 源自 test_ui_rewards.py ====================
"""电脑端奖励徽标（实践分 · 虚拟工资）：宽档侧边两枚标签、窄档 .sub 内联块、演示数据形态。

脚本按 index.html 加载序在 node 沙箱里回放；原型真源是 Main.dc.html 的 rwOf / .rw* 规则。
断行与像素以 Edge/WebView2 截图为准，这里只测文本、类名与 CSS 规则是否存在。

@author Author
"""

import re

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))


REWARDS_SETUP = r"""
const mk = (extra) => Object.assign({ id: "r1", name: "测试活动", place: "教室", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 10:00:00", sign_end: "2026-11-08 10:00:00",
  act_start: "2026-11-09 08:00:00", act_end: "2026-11-09 17:00:00" }, extra);
const both = (item) => ({ side: rewardChips(item), inline: rewardInline(item) });
"""


class RewardTextTests(unittest.TestCase):
    def test_pending_ready_zero_and_missing(self):
        out = run_js(REWARDS_SETUP + r"""
out.push({
  pending: both(mk({ reward_state: "pending", points: null, wage: null })),
  absent: both(mk({})),
  full: both(mk({ reward_state: "ready", points: 2, wage: 20 })),
  half: both(mk({ reward_state: "ready", points: 0.5, wage: "5" })),
  zero: both(mk({ reward_state: "ready", points: 0, wage: 0 })),
  zeroWage: both(mk({ reward_state: "ready", points: 1, wage: 0 })),
  noPts: both(mk({ reward_state: "ready", points: null, wage: 20 })),
  noWage: both(mk({ reward_state: "ready", points: 3, wage: "" })),
  none: both(mk({ reward_state: "ready", points: null, wage: undefined })),
  pendingWithValues: both(mk({ reward_state: "pending", points: 9, wage: 9 })),
  evil: both(mk({ reward_state: "ready", points: "<b>x</b>", wage: 1 })),
  nothing: rewardChips(null),
});
""")[0]
        # 详情没回来：只写同步中，侧边带 title，内联用 .rw-i.p
        for key in ("pending", "absent", "pendingWithValues"):
            self.assertIn('<span class="rw-p">奖励同步中</span>', out[key]["side"], key)
            self.assertIn('title="奖励信息同步中"', out[key]["side"], key)
            self.assertNotIn("rw-c", out[key]["side"], key)
            self.assertIn('class="rw-i p"', out[key]["inline"], key)
            self.assertIn(">奖励同步中</span>", out[key]["inline"], key)
        self.assertNotIn("9", out["pendingWithValues"]["side"], "pending 时不显示可能残留的数值")
        # 有值
        side = out["full"]["side"]
        self.assertIn('<span class="rw-c pt"><b>2</b>分</span>', side)
        self.assertIn('<span class="rw-c wg">工资<b>20</b></span>', side)
        self.assertIn('title="实践分 2，虚拟工资 20"', side)
        self.assertIn('<span class="rw-i" title="实践分 2，虚拟工资 20">2 分 · 工资 20</span>', out["full"]["inline"])
        self.assertIn("0.5</b>分", out["half"]["side"])
        self.assertIn(">0.5 分 · 工资 5<", out["half"]["inline"])
        # 0 是真实回答，照实写
        self.assertIn("<b>0</b>分", out["zero"]["side"])
        self.assertIn("工资<b>0</b>", out["zero"]["side"])
        self.assertNotIn("未公布", out["zero"]["side"])
        self.assertIn(">0 分 · 工资 0<", out["zero"]["inline"])
        self.assertIn(">1 分 · 工资 0<", out["zeroWage"]["inline"])
        # 缺失：ready 才写未公布，类名带 na
        self.assertIn('<span class="rw-c pt na">分未公布</span>', out["noPts"]["side"])
        self.assertIn('<span class="rw-c wg">', out["noPts"]["side"])
        self.assertIn(">分未公布 · 工资 20<", out["noPts"]["inline"])
        self.assertIn('<span class="rw-c wg na">工资未公布</span>', out["noWage"]["side"])
        self.assertIn(">3 分 · 工资未公布<", out["noWage"]["inline"])
        self.assertIn('title="实践分 未公布，虚拟工资 未公布"', out["none"]["side"])
        self.assertIn(">分未公布 · 工资未公布<", out["none"]["inline"])
        self.assertNotIn("<b></b>", out["none"]["side"], "没有数值时不画空的 <b>")
        self.assertNotIn('class="rw-i p"', out["none"]["inline"], "ready 的缺失不是同步中")
        # 转义
        self.assertNotIn("<b>x</b>", out["evil"]["side"] + out["evil"]["inline"])
        self.assertEqual(out["nothing"], "")

    def test_row_outputs_both_variants_and_inline_sits_between_refund_and_requirements(self):
        out = run_js(REWARDS_SETUP + r"""
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const item = mk({ reward_state: "ready", points: 2, wage: 20, cancel_allowed: true });
window.onBackend.activities({ ok: true, items: [item] });
out.push(rowHtml(findItem("r1")));
""")[0]
        self.assertEqual(out.count('class="rw" '), 1, "侧边块带 title，类名后面还有属性")
        self.assertEqual(out.count('class="rw-i"'), 1)
        self.assertLess(out.index('class="rw" '), out.index('class="sub"'), "侧边标签在名字行")
        self.assertGreater(out.index('class="rw-i"'), out.index('class="sub"'), "内联块在 .sub 行")
        self.assertGreater(out.index('class="rw-i"'), out.index('class="rf"'), "在报后可退之后")
        self.assertGreater(out.index("无需签到"), out.index('class="rw-i"'), "在签到说明之前")


class RewardCssTests(unittest.TestCase):
    css = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")

    def rule(self, selector: str) -> str:
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_chip_rules_follow_the_prototype(self):
        self.assertIn("min-width: 3.125rem", self.rule(".c-main .rw-c.pt"))
        self.assertIn("min-width: 3.75rem", self.rule(".c-main .rw-c.wg"))
        self.assertIn("text-align: center", self.rule(".c-main .rw-c.pt"))
        self.assertIn("box-shadow: none", self.rule(".c-main .rw-c.na"))
        self.assertIn("margin-left: 0", self.rule(".c-main .rw-c b:first-child"))
        self.assertIn("display: none", self.rule(".c-main .rw-c b:empty"))

    def test_narrow_tier_swaps_side_chips_for_the_inline_block(self):
        self.assertIn("display: none", self.rule(".c-main .rw-i"), "宽档不显示内联块")
        m = re.search(r"@media \(max-width: 719px\)\s*\{\s*\.c-main \.rw \{ display: none; \}\s*"
                      r"\.c-main \.rw-i \{ display: inline; \}\s*\}", self.css)
        self.assertIsNotNone(m, "窄档（< 720px）隐藏侧边、显示内联")
        self.assertIn("color: var(--warn)", self.rule(".c-main .rw-i.p"))

    def test_selected_and_dim_rows(self):
        self.assertIn(".row.is-selected .rw-c, .row.is-selected .rw-i:not(.p)", self.css)
        self.assertIn(".row.is-signed .rw-c, .row.is-closed .rw-c", self.css)


class DemoRewardTests(unittest.TestCase):
    def test_every_demo_row_carries_reward_keys(self):
        sys.path.insert(0, str(LOCAL))
        try:
            from domain import demo_data
        finally:
            sys.path.pop(0)
        rows = demo_data.demo_items(1_700_000_000.0, lambda epoch=None: "T%s" % epoch)
        for row in rows:
            for key in ("points", "wage", "reward_state"):
                self.assertIn(key, row, row["id"])
            self.assertIn(row["reward_state"], ("ready", "pending"), row["id"])
            for key in ("points", "wage"):
                self.assertTrue(row[key] is None or isinstance(row[key], (int, float)), row["id"])
            if row["reward_state"] == "pending":
                self.assertIsNone(row["points"], row["id"])
                self.assertIsNone(row["wage"], row["id"])
        states = {r["id"]: r for r in rows}
        self.assertEqual(states["demo-volunteer"]["reward_state"], "pending")
        self.assertTrue(any(r["reward_state"] == "ready" and r["points"] is None and r["wage"] is None for r in rows))
        self.assertTrue(any(r["reward_state"] == "ready" and r["wage"] == 0 for r in rows))
        self.assertTrue(any(r["points"] == 0.5 for r in rows))

# ==================== 源自 test_terms_consent.py ====================
"""后端条款门禁的隔离测试（plan-20261027-distribution-contract-repair）。

不 `import app.py`：它的顶层会 import webview 并经 runtime_paths 触碰数据根，
与「不读真实登录文件、不起真实 worker」的边界冲突。这里用 ast 抽出 Api 的
相关方法，注入 DEMO / TERMS_VERSION / load_prefs / threading 等假件后单独
求值，拿到的是**真实方法的返回值**，不是源码子串的推测。

覆盖：授权 helper、terms_required 返回、学校动作（check / list_activities /
login / grab / start_plan）在未授权与已授权两种状态下的行为、start_plan 的
幂等重放优先于门禁、demo grab 不启动真实 worker，以及非学校动作不被门禁误伤；
另有 accept_terms 的版本绑定——不匹配输入在写前拒绝、零副作用。
"""

import ast
import threading
import time
import types

LOCAL = Path(__file__).resolve().parents[1]

# 与 local/app.py 的 TERMS_VERSION 同源的测试常量：任何一处漂移都会让
# 「已同意版本 == 当前版本」的判定失效，测试就是要盯住这一点。
# r6：只补披露（手机访问通道、GitHub 下载、手机配对记录），仍要求重新同意，
# 旧 r1–r5 的同意记录不再放行。
TEST_TERMS = "2026-11-09-r6"

SCHOOL_METHODS = ("check", "list_activities", "login", "grab", "start_plan")
# 手机能发起的学校动作：都经同一组 Api 方法，门禁必须在方法里而不是在手机页
PHONE_SCHOOL_METHODS = ("check", "list_activities", "start_plan", "phone_relogin_begin")
HELPER_METHODS = ("_terms_gate", "_remember_start", "_start_replay")
# 明确不在门禁范围内的公开桥接：停止/取消、帮助、数据目录、更新检查、偏好与同意
NON_SCHOOL_METHODS = ("stop_plan", "cancel_task", "cancel_start_request",
                      "help", "open_data", "check_update", "save_prefs",
                      "accept_terms", "start_request_state")


def _read(rel: str) -> str:
    return (LOCAL / rel).read_text(encoding="utf-8")


def _function_node(name: str):
    tree = ast.parse(_read("app.py"))
    node = next(item for item in ast.walk(tree)
                if isinstance(item, ast.FunctionDef) and item.name == name)
    return node


def _school_action_node(name: str):
    paths = {"check": "application/login_recovery.py",
             "list_activities": "application/activity_list_service.py",
             "start_plan": "application/plan_admission.py"}
    if name not in paths:
        return _function_node(name)
    tree = ast.parse(_read(paths[name]))
    return next(item for item in ast.walk(tree)
                if isinstance(item, ast.FunctionDef) and item.name == name)


def _module_source(*names: str) -> str:
    """把若干方法拼成一个可执行的模块源码（保持真实实现，不改写）。"""
    parts = []
    for name in names:
        parts.append(ast.unparse(_function_node(name)))
    return "\n\n".join(parts)


class _FakeThread:
    """只登记、不起真实线程：测试要断言的是「有没有被排上」。"""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self.target = target
        self.args = args or ()

    def start(self):
        STARTED_TARGETS.append(self.target)


class _FakeThreading:
    Thread = _FakeThread


STARTED_TARGETS: list = []


class _FakeApi:
    """Api 的最小替身：只提供被抽出方法真正会用到的属性。"""

    # 与生产 Api.START_KEEP 同值：真实 _remember_start 会按它裁剪 start_plan
    # 登记队列，替身缺这个类属性会让每次登记都抛 AttributeError（假报错）
    START_KEEP = 32

    @property
    def closing(self): return self._closing
    @property
    def cancelling(self): return self._cancelling
    @property
    def checking(self): return self._checking
    @checking.setter
    def checking(self, value): self._checking = value
    @property
    def listing(self): return self._listing
    @listing.setter
    def listing(self, value): self._listing = value

    def __init__(self):
        self._lock = threading.RLock()
        self._closing = False
        self._checking = False
        self._listing = False
        # 取消报名在途标记（计划 20261107-conflict-cancel X3）：被抽出的 check /
        # list_activities / _auto_relogin_eligible 现在会读它，替身要有这个属性
        # （只补属性，断言一字未动）
        self._cancelling = False
        self._check_request_id = ""
        self._list_request_id = ""
        self._check_last = {}
        self._list_last = {}
        self._start_requests = {}
        self._start_order = []
        self._plan = None
        self.spawned = []
        self.inner_calls = 0
        self.inner_result = {"ok": True, "plan_id": "p-test"}

    def _do_check(self):
        self._checking = False

    def _do_list(self):
        self._listing = False

    def _spawn(self, args, label, kind="grab"):
        self.spawned.append({"args": list(args), "label": label, "kind": kind})
        return {"ok": True}

    def _start_plan_inner(self, items, headed, retry_policy, request_id=""):
        self.inner_calls += 1
        return dict(self.inner_result)


def build_api(prefs: dict, demo: bool = False) -> _FakeApi:
    """按给定 ui.json 偏好构造一个装好真实方法的 Api 替身。"""
    namespace = {
        "DEMO": demo,
        "TERMS_VERSION": TEST_TERMS,
        "load_prefs": lambda: dict(prefs or {}),
        "re": re,
        "time": time,
        "threading": _FakeThreading,
        "worker_command": lambda *args: ["worker"] + list(args),
    }
    # terms_state / terms_unknown_payload 是模块级纯函数：直接取真实实现
    helpers = ast.Module(body=[_function_node("terms_state"),
                               _function_node("terms_unknown_payload")],
                         type_ignores=[])
    ast.fix_missing_locations(helpers)
    exec(compile(helpers, "<terms-helpers>", "exec"), namespace)  # noqa: S102

    methods = ast.Module(body=[_function_node(name)
                               for name in HELPER_METHODS + SCHOOL_METHODS],
                         type_ignores=[])
    ast.fix_missing_locations(methods)
    exec(compile(methods, "<terms-gate>", "exec"), namespace)  # noqa: S102

    api = _FakeApi()
    for name in HELPER_METHODS + SCHOOL_METHODS:
        setattr(api, name, types.MethodType(namespace[name], api))
    services = ast.Module(body=[_school_action_node("check"), _school_action_node("list_activities")],
                          type_ignores=[])
    ast.fix_missing_locations(services)
    exec(compile(services, "<terms-services>", "exec"), namespace)  # noqa: S102
    login = types.SimpleNamespace(_coordination=api, _lock=api._lock,
                                  _ports={"terms_gate": api._terms_gate, "do_check": api._do_check},
                                  check_again=False, check_request_id="", check_last={})
    listing = types.SimpleNamespace(_coordination=api, _lock=api._lock,
                                    _ports={"terms_gate": api._terms_gate, "do_list": api._do_list},
                                    request_id="", last={})
    login.check = types.MethodType(namespace["check"], login)
    listing.list_activities = types.MethodType(namespace["list_activities"], listing)
    api._login_recovery, api._activity_list = login, listing
    tree = ast.parse(_read("application/plan_admission.py"))
    plan_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PlanAdmission")
    plan_module = ast.fix_missing_locations(ast.Module(body=[plan_class], type_ignores=[]))
    exec(compile(plan_module, "<terms-plan>", "exec"), namespace)  # noqa: S102
    api._plan_manager = namespace["PlanAdmission"](
        lock=api._lock, coordination=api, activity_list=listing, login=login,
        ports={"terms_gate": api._terms_gate, "start_inner": api._start_plan_inner})
    api._start_requests = api._plan_manager.start_requests
    return api


class TermsGateHelperTests(unittest.TestCase):
    """授权 helper：只有「已同意当前版本」才放行。"""

    def test_gate_passes_only_for_current_version(self):
        accepted = build_api({"terms_version": TEST_TERMS,
                              "terms_accepted_at": "2026-10-27 19:00:00"})
        self.assertIsNone(accepted._terms_gate(), "已同意当前版本必须放行")

        # 旧 r1 的同意记录在 r3 下必须被拒：版本变化要求重新点击同意
        old = build_api({"terms_version": "2026-10-27-r1"})
        gate = old._terms_gate()
        self.assertIsNotNone(gate)
        self.assertEqual(gate["error"], "terms_required")
        self.assertEqual(gate["terms"]["accepted_version"], "2026-10-27-r1")
        self.assertEqual(gate["terms"]["version"], TEST_TERMS)
        self.assertIn("查看条款", gate["text"])

        empty = build_api({})
        self.assertIsNotNone(empty._terms_gate(), "没同意过必须拦住")

    def test_gate_carries_request_id_for_reconciliation(self):
        api = build_api({})
        gate = api._terms_gate("start-1")
        self.assertEqual(gate["request_id"], "start-1",
                         "拒绝也要带原 request_id，界面按 ID 对账而不是当新一轮")
        self.assertNotIn("request_id", api._terms_gate(), "没有 ID 时不伪造")

    def test_demo_bypasses_gate(self):
        self.assertIsNone(build_api({}, demo=True)._terms_gate(),
                          "演示模式完全离线，不受条款门禁限制")

    def test_gate_never_touches_login_files_or_logs(self):
        source = ast.unparse(_function_node("_terms_gate"))
        self.assertIn("load_prefs", source)
        for banned in ("SESSION_FILE", "STORAGE_STATE", "storage_state",
                       "session_path", "addLog", "_trace", "grab.log"):
            self.assertNotIn(banned, source, "门禁不得读写登录文件或写运行日志")


class SchoolActionGateTests(unittest.TestCase):
    """五个学校动作：未授权一律不起线程、worker、学校请求或计划。"""

    def setUp(self):
        STARTED_TARGETS.clear()

    def test_unauthorized_check_and_list_do_not_start_threads(self):
        api = build_api({})
        for rid in ("check-1", "list-1"):
            got = api.check(rid)
            self.assertEqual(got["error"], "terms_required")
            self.assertEqual(got["queued"], False)
            self.assertEqual(got["request_id"], rid)
        got = api.list_activities("list-9")
        self.assertEqual(got["error"], "terms_required")
        self.assertEqual(STARTED_TARGETS, [], "未获授权不得排上任何后台线程")
        self.assertFalse(api._checking)
        self.assertFalse(api._listing)

    def test_unauthorized_login_and_grab_do_not_spawn_worker(self):
        api = build_api({})
        self.assertEqual(api.login()["error"], "terms_required")
        self.assertEqual(api.grab("a1", "活动")["error"], "terms_required")
        self.assertEqual(api.spawned, [], "未获授权不得起真实 worker")

    def test_unauthorized_start_plan_leaves_no_pending_and_no_plan(self):
        api = build_api({})
        got = api.start_plan([{"id": "a1"}], False, None, "start-7")
        self.assertEqual(got["error"], "terms_required")
        self.assertEqual(got["request_id"], "start-7")
        self.assertEqual(api.inner_calls, 0, "未获授权不得进入计划构建")
        self.assertEqual(api._start_requests["start-7"]["state"], "rejected",
                         "本次登记必须收成 rejected，不能留下悬空 pending")

    def test_accepted_version_releases_school_actions(self):
        api = build_api({"terms_version": TEST_TERMS})
        self.assertTrue(api.check("c1")["queued"])
        self.assertTrue(api.list_activities("l1")["queued"])
        self.assertTrue(api._checking, "放行后要真的进入检查态")
        self.assertTrue(api._listing)
        self.assertEqual(len(STARTED_TARGETS), 2, "放行后两个后台线程都要排上")
        self.assertEqual(api.login(), {"ok": True})
        self.assertEqual(len(api.spawned), 1, "放行后登录才起 worker")
        got = api.start_plan([{"id": "a1"}], False, None, "start-8")
        self.assertTrue(got["ok"])
        self.assertEqual(api.inner_calls, 1)

    def test_start_plan_replay_precedes_gate(self):
        """同一 request_id 的既有结论先重放：门禁不得改写已接纳/已拒绝的结论。"""
        api = build_api({})
        api._remember_start("rid-accepted", "accepted",
                            plan_id="p-old", result={"ok": True, "plan_id": "p-old"})
        api._remember_start("rid-rejected", "rejected",
                            result={"ok": False, "text": "上次被拒绝"})
        accepted = api.start_plan([{"id": "a1"}], False, None, "rid-accepted")
        self.assertTrue(accepted.get("duplicate"), "已接纳请求必须重放原结论")
        self.assertEqual(accepted["plan_id"], "p-old")
        rejected = api.start_plan([{"id": "a1"}], False, None, "rid-rejected")
        self.assertTrue(rejected.get("duplicate"))
        self.assertEqual(api.inner_calls, 0, "重放不得重复建计划")

    def test_start_plan_without_request_id_still_gated(self):
        api = build_api({})
        got = api.start_plan([{"id": "a1"}])
        self.assertEqual(got["error"], "terms_required")
        self.assertEqual(api.inner_calls, 0)


class DemoOfflineTests(unittest.TestCase):
    """demo 语义：不联网、不起真实 worker。"""

    def test_demo_grab_returns_offline_result_without_worker(self):
        api = build_api({}, demo=True)
        got = api.grab("a1", "活动")
        self.assertFalse(got["ok"])
        self.assertTrue(got["demo"])
        self.assertIn("演示模式", got["text"])
        self.assertEqual(api.spawned, [], "demo 的 grab 绝不能起真实 worker")

    def test_demo_login_keeps_offline_answer(self):
        api = build_api({}, demo=True)
        got = api.login()
        self.assertTrue(got.get("demo"))
        self.assertEqual(api.spawned, [])


class NonSchoolActionContractTests(unittest.TestCase):
    """门禁范围之外：停止、取消、帮助、数据目录、更新检查、偏好与同意本身。"""

    def test_non_school_methods_have_no_terms_gate(self):
        for name in NON_SCHOOL_METHODS:
            source = ast.unparse(_function_node(name))
            self.assertNotIn("_terms_gate", source,
                             "%s 不是学校网络动作，不得被条款门禁误伤" % name)

    def test_school_methods_all_call_the_gate(self):
        for name in SCHOOL_METHODS:
            source = ast.unparse(_school_action_node(name))
            self.assertIn("terms_gate", source,
                          "%s 是学校网络动作，必须有后端授权兜底" % name)
        for factory in ("_make_login_recovery", "_make_activity_list"):
            self.assertIn("'terms_gate': lambda request_id: self._terms_gate(request_id)",
                          ast.unparse(_function_node(factory)))
        self.assertIn("'terms_gate': lambda: self._terms_gate()",
                      ast.unparse(_function_node("_make_plan_manager")))

    def test_phone_school_actions_go_through_the_gate(self):
        for name in PHONE_SCHOOL_METHODS:
            source = ast.unparse(_school_action_node(name))
            self.assertIn("terms_gate", source,
                          "手机动作 %s 访问学校，门禁必须在后端方法里" % name)
        tree = ast.parse(_read("application/phone_service.py"))
        state = ast.unparse(next(n for n in ast.walk(tree)
                                 if isinstance(n, ast.FunctionDef) and n.name == "raw_state"))
        self.assertIn("'terms_ok': self._ports['terms_gate']() is None", state,
                      "手机快照的 terms_ok 必须和电脑门禁同源")
        self.assertIn("'terms_gate': lambda: self._terms_gate()", ast.unparse(_function_node("_make_phone_controller")))


def build_accept_api(prefs: dict, *, update_ok: bool = True):
    """抽出真实 accept_terms：注入内存偏好与 update_prefs spy。

    返回 (api, store, writes, terms_state_fn)：store 是内存偏好（可乱改来模拟
    旧 HTML/混合资源），writes 记录每次真实落盘的补丁，terms_state_fn 用于在
    拒绝后重读快照、确认没有伪造出当前版本的同意。
    """
    store = dict(prefs or {})
    writes: list = []

    def update_prefs(patch):
        # 与生产同语义：拿不到锁返回 False 且一个键都不写
        if not update_ok:
            return False
        writes.append(dict(patch))
        store.update(patch)
        return True

    namespace = {
        "TERMS_VERSION": TEST_TERMS,
        "load_prefs": lambda: dict(store),
        "update_prefs": update_prefs,
        "time": time,
    }
    helpers = ast.Module(body=[_function_node("terms_state")], type_ignores=[])
    ast.fix_missing_locations(helpers)
    exec(compile(helpers, "<terms-helpers>", "exec"), namespace)  # noqa: S102

    method = ast.Module(body=[_function_node("accept_terms")], type_ignores=[])
    ast.fix_missing_locations(method)
    exec(compile(method, "<accept-terms>", "exec"), namespace)  # noqa: S102

    api = _FakeApi()
    api.accept_terms = types.MethodType(namespace["accept_terms"], api)
    return api, store, writes, namespace["terms_state"]


class AcceptTermsWriteTests(unittest.TestCase):
    """同意提交必须绑定实际阅读版本：一切不匹配输入在写前被拒、零副作用。"""

    OLD = {"terms_version": "2026-10-27-r1", "terms_accepted_at": "2026-10-27 10:00:00"}

    def setUp(self):
        STARTED_TARGETS.clear()

    def test_current_version_writes_only_two_keys(self):
        api, store, writes, _ = build_accept_api(dict(self.OLD))
        got = api.accept_terms(TEST_TERMS)
        self.assertTrue(got["ok"], "提交当前版必须成功")
        self.assertEqual(len(writes), 1, "成功只发一次原子写")
        self.assertEqual(set(writes[0]), {"terms_version", "terms_accepted_at"},
                         "只允许写这两个键：不碰登录文件、不写日志")
        self.assertEqual(store["terms_version"], TEST_TERMS)
        self.assertTrue(store["terms_accepted_at"], "同意时间必须落盘")
        self.assertEqual(got["terms"]["accepted_version"], TEST_TERMS,
                         "成功回执与 terms_state 同源")
        self.assertEqual(got["terms"]["version"], TEST_TERMS)

    def test_mismatched_inputs_write_nothing_and_gate_stays_closed(self):
        # 缺参（默认空串）、空串、旧版、未知新版、None、数字、对象、列表
        for bad in ("", "2026-10-27-r1", "2026-10-28-r3", None, 2026,
                    [TEST_TERMS], {"version": TEST_TERMS}):
            api, store, writes, terms_state = build_accept_api(dict(self.OLD))
            got = api.accept_terms(bad)
            self.assertEqual(got["ok"], False, "输入 %r 必须拒绝" % (bad,))
            self.assertEqual(got["error"], "terms_version_mismatch")
            self.assertEqual(writes, [], "输入 %r 不得触发 update_prefs" % (bad,))
            self.assertEqual(store, self.OLD, "内存偏好与原同意时间必须原样")
            self.assertEqual(terms_state(store)["accepted_version"], "2026-10-27-r1",
                             "快照如实反映旧状态，不得伪造当前版同意")
            gate = build_api(dict(store))._terms_gate()
            self.assertIsNotNone(gate, "拒绝后 _terms_gate 仍须拒绝")
            self.assertEqual(gate["error"], "terms_required")
            self.assertEqual(STARTED_TARGETS, [], "拒绝路径不得排任何线程")

    def test_old_html_cannot_forge_current_acceptance(self):
        """旧 HTML（只认识 r1）向当前后端提交：重读 terms_state 不出现 r4。"""
        api, store, writes, terms_state = build_accept_api(dict(self.OLD))
        got = api.accept_terms("2026-10-27-r1")   # 旧副本提交旧版
        self.assertEqual(got["ok"], False)
        self.assertEqual(got["error"], "terms_version_mismatch")
        self.assertEqual(writes, [], "旧副本提交不得留下任何写入")
        snapshot = terms_state(store)
        self.assertNotEqual(snapshot["accepted_version"], TEST_TERMS,
                            "拒绝后不得出现伪造的 r4 同意")
        self.assertEqual(snapshot["accepted_at"], "2026-10-27 10:00:00",
                         "原同意时间不得被改写")

    def test_prefs_busy_keeps_failure_semantics(self):
        api, store, writes, _ = build_accept_api(dict(self.OLD), update_ok=False)
        got = api.accept_terms(TEST_TERMS)
        self.assertEqual(got["ok"], False)
        self.assertEqual(got["error"], "prefs_busy")
        self.assertEqual(writes, [], "拿不到锁时一个键都不写")
        self.assertEqual(store, self.OLD, "偏好保持原样，界面留在弹窗重试")

    def test_rejection_path_has_no_side_effect_calls(self):
        source = ast.unparse(_function_node("accept_terms"))
        # 版本判定先于时间戳与原子写（顺序即证据）
        self.assertLess(source.index("document_version == TERMS_VERSION"),
                        source.index("strftime"), "判定必须先于时间戳生成")
        self.assertLess(source.index("document_version == TERMS_VERSION"),
                        source.index("update_prefs"), "判定必须先于原子写")
        for banned in ("SESSION_FILE", "STORAGE_STATE", "storage_state",
                       "read_text", "_trace", "addLog", "threading", "log"):
            self.assertNotIn(banned, source,
                             "同意不得读写登录文件、写日志或起线程")


def build_withdraw_api(prefs: dict, *, plan_running: bool = False, update_ok: bool = True):
    """抽出真实 withdraw_terms / accept_terms：内存偏好 + update_prefs spy。"""
    store = dict(prefs or {})
    writes: list = []

    def update_prefs(patch):
        if not update_ok:
            return False
        writes.append(dict(patch))
        store.update(patch)
        return True

    namespace = {
        "TERMS_VERSION": TEST_TERMS,
        "load_prefs": lambda: dict(store),
        "update_prefs": update_prefs,
        "time": time,
    }
    helpers = ast.Module(body=[_function_node("terms_state")], type_ignores=[])
    ast.fix_missing_locations(helpers)
    exec(compile(helpers, "<terms-helpers>", "exec"), namespace)  # noqa: S102
    methods = ast.Module(body=[_function_node("withdraw_terms"), _function_node("accept_terms")],
                         type_ignores=[])
    ast.fix_missing_locations(methods)
    exec(compile(methods, "<withdraw-terms>", "exec"), namespace)  # noqa: S102

    api = _FakeApi()
    api.plan_active_for_close = lambda: plan_running
    api.withdraw_terms = types.MethodType(namespace["withdraw_terms"], api)
    api.accept_terms = types.MethodType(namespace["accept_terms"], api)
    return api, store, writes, namespace["terms_state"]


class WithdrawTermsTests(unittest.TestCase):
    """撤回同意：学校动作重新被拦；计划运行中拒绝；不删账号密码和登录信息。"""

    ACCEPTED = {"terms_version": TEST_TERMS, "terms_accepted_at": "2026-11-03 09:12:00",
                "relogin": {"keep": True}}

    def setUp(self):
        STARTED_TARGETS.clear()

    def test_withdraw_closes_the_gate_for_school_actions(self):
        api, store, writes, terms_state = build_withdraw_api(dict(self.ACCEPTED))
        got = api.withdraw_terms()
        self.assertTrue(got["ok"])
        self.assertEqual(got["terms"]["accepted_version"], "")
        self.assertEqual(got["terms"]["accepted_at"], "")
        self.assertTrue(got["terms"]["withdrawn_at"], "撤回时刻要回给界面显示")
        self.assertEqual(set(writes[0]), {"terms_version", "terms_accepted_at", "terms_withdrawn_at"},
                         "只写三个条款键")
        gated = build_api(dict(store))
        self.assertEqual(gated.check("c-1")["error"], "terms_required", "撤回后检查登录被拦")
        self.assertEqual(gated.list_activities("l-1")["error"], "terms_required")
        self.assertEqual(gated.start_plan([{"id": "a1"}], False, None, "s-1")["error"],
                         "terms_required")
        self.assertEqual(STARTED_TARGETS, [], "撤回后不得排上任何学校线程")

    def test_withdraw_refused_while_plan_running_writes_nothing(self):
        api, store, writes, _ = build_withdraw_api(dict(self.ACCEPTED), plan_running=True)
        got = api.withdraw_terms()
        self.assertFalse(got["ok"])
        self.assertEqual(got["error"], "plan_running")
        self.assertIn("先停止计划", got["text"])
        self.assertEqual(writes, [], "计划运行中撤回零写入")
        self.assertEqual(store, self.ACCEPTED)

    def test_withdraw_keeps_credentials_and_login_files(self):
        api, store, _, _ = build_withdraw_api(dict(self.ACCEPTED))
        api.withdraw_terms()
        self.assertEqual(store["relogin"], {"keep": True}, "其他偏好原样保留")
        source = ast.unparse(_function_node("withdraw_terms"))
        for banned in ("_credential_store", "CREDENTIAL_FILE", "SESSION_FILE", "clear_relogin",
                       "unlink", "threading", "_log_event", "_trace"):
            self.assertNotIn(banned, source, "撤回不得碰账号密码、登录文件、线程或日志")

    def test_withdraw_prefs_busy_keeps_acceptance(self):
        api, store, writes, _ = build_withdraw_api(dict(self.ACCEPTED), update_ok=False)
        got = api.withdraw_terms()
        self.assertEqual(got["error"], "prefs_busy")
        self.assertEqual(store, self.ACCEPTED, "没保存成功就仍是已同意")

    def test_accept_again_restores_terms_snapshot(self):
        api, store, _, terms_state = build_withdraw_api(dict(self.ACCEPTED))
        api.withdraw_terms()
        self.assertTrue(api.accept_terms(TEST_TERMS)["ok"])
        snap = terms_state(store)
        self.assertEqual(snap["accepted_version"], TEST_TERMS, "重新同意后 bootstrap.terms 恢复")
        self.assertNotIn("withdrawn_at", snap, "terms_state 仍只回报三个键")
        self.assertIsNone(build_api(dict(store))._terms_gate())


class AutoReloginTermsGateTests(unittest.TestCase):
    """未同意条款时自动登录不触发：执行真实 _auto_relogin_eligible。"""

    def _eligible(self, prefs):
        namespace = {
            "DEMO": False,
            "TERMS_VERSION": TEST_TERMS,
            "load_prefs": lambda: dict(prefs),
            "_advanced_features": types.SimpleNamespace(
                feature_ready=lambda *args, **kwargs: True, RELOGIN_OCR="relogin_ocr"),
            "DATA_DIR": None,
            "_credential_store": types.SimpleNamespace(has_credentials=lambda path: True),
            "CREDENTIAL_FILE": None,
        }
        helpers = ast.Module(body=[_function_node("terms_state"),
                                   _function_node("terms_unknown_payload")], type_ignores=[])
        ast.fix_missing_locations(helpers)
        exec(compile(helpers, "<terms-helpers>", "exec"), namespace)  # noqa: S102
        methods = ast.Module(body=[_function_node("_terms_gate"),
                                   _function_node("_silent_relogin_ready"),
                                   _function_node("_auto_relogin_eligible")], type_ignores=[])
        ast.fix_missing_locations(methods)
        exec(compile(methods, "<auto-eligible>", "exec"), namespace)  # noqa: S102
        api = _FakeApi()
        api._advanced_busy = False
        api._relogin_blocked_locked = lambda: False
        api._terms_gate = types.MethodType(namespace["_terms_gate"], api)
        # 2026-11-11 起资格判据与 _silent_relogin_ready 共用一份口径，
        # 两个只影响「这次手输的账号」「密码被拒过」的旁支在替身里按「没有」处理
        api._once_credentials_staged = lambda: False
        api._auto_relogin_paused = lambda: False
        api._silent_relogin_ready = types.MethodType(
            namespace["_silent_relogin_ready"], api)
        return types.MethodType(namespace["_auto_relogin_eligible"], api)()

    def test_auto_relogin_blocked_without_current_terms(self):
        self.assertFalse(self._eligible({}), "没同意过不能自动登录")
        self.assertFalse(self._eligible({"terms_version": "2026-10-27-r3"}), "旧版同意不能自动登录")
        self.assertFalse(self._eligible({"terms_version": "", "terms_withdrawn_at": "x"}),
                         "撤回后不能自动登录")
        self.assertTrue(self._eligible({"terms_version": TEST_TERMS}),
                        "同意当前版且账号、识别都就绪才放行")

if __name__ == "__main__":
    unittest.main()
