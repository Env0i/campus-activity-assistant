#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主窗口向原型 1:1 的列表半边（计划 20261108-main-window，fe-list）。

覆盖：更多筛选折叠与计数（LS06）、分组顺序（LS01）、空态与横幅文案（LS08 / LS12 / LS13 / LS16 / LS18 / LS21）、
待公布行禁选（LS14）、列表失败写运行记录（LS11）、工具已经开着（GL01）、顶栏 title（TF02）。

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


if __name__ == "__main__":
    unittest.main()
