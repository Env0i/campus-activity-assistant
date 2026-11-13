#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页重构前先修的两处行为（计划 20261113-prerefactor-fixes）：

- U4 「核对计划」弹层开着时，轮询带回新状态，弹层里的条目与提醒要跟着变；
- U7 顶栏「最近同步」要写北京时间，不能用手机本机时钟和手机时区。

在 node vm 里跑真实的 ui/m/app.js；复用 test_phone_ui 的沙箱，只是为 U7 另起进程时
注入 TZ，让手机时区与北京时间明确不同。

@author Author
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from test_phone_ui import PHONE_DIR, PHONE_JS_HARNESS  # noqa: E402


def run_phone(snippet: str, tz: str | None = None):
    """跑手机页片段；tz 给定时按该时区起 node，用来证明结果不随手机时区漂移。"""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，无法运行 JS 行为测试")
    env = dict(os.environ)
    if tz:
        env["TZ"] = tz
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "harness.js"
        part = Path(name) / "snippet.js"
        harness.write_text(PHONE_JS_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        res = subprocess.run([node, str(harness), str(PHONE_DIR), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30, env=env)
    if res.returncode != 0:
        raise AssertionError("手机 JS 行为测试崩溃：%s" % res.stderr[-800:])
    marker = res.stdout.rfind("__RESULT__")
    if marker < 0:
        raise AssertionError("手机 JS 没有输出结果：%s" % res.stdout[-500:])
    return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


# 业务现在 = 北京时间 2026-11-10 14:00；两场预报名，一场 2 天后、一场 3 天后开放
REVIEW_SETUP = r"""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
const clock = {state: "ready", epoch_s: Date.UTC(2026, 10, 10, 6, 0, 0) / 1000,
               tick_s: 1000000, sampled_tick_s: 1000000, age_s: 0};
const act = (id, name, day) => ({id: id, name: name, seconds_to_open: day * 86400,
  sign_start: "2026-11-" + (10 + day) + " 14:00:00"});
ui.ingest({state: {terms_ok: true, busy: false, business_clock: clock,
  relogin_setup: {saved: false, ocr_ready: false, paused: false},
  activities: [act("a1", "甲活动", 2), act("a2", "乙活动", 3)]}});
ui.model.selected = ["a1", "a2"];
ui.refreshControls();
ui.renderReview();
ui.openSheet("review");
const peek = () => ({ sheet: ui.model.sheetId, nodes: $("review-items").childElementCount,
  warns: $("review-warns").innerHTML, label: $("btn-review-start").textContent });
"""


class ReviewSheetStaysFreshTests(unittest.TestCase):
    """U4：弹层开着时 ingest 也要重画，不能停在打开那一刻的样子。"""

    def test_warnings_follow_a_new_relogin_setup_while_the_sheet_is_open(self):
        """电脑上装好了识别并保存了账号：「没开自动登录」那条提醒应当消失。"""
        res = run_phone(REVIEW_SETUP + r"""
const before = peek();
ui.ingest({state: {relogin_setup: {saved: true, ocr_ready: true, paused: false}}});
out.push({ before, after: peek() });
""")
        data = res[0]
        self.assertEqual(data["before"]["sheet"], "review", "前提：核对弹层是开着的")
        self.assertIn("电脑上没开自动登录", data["before"]["warns"], "前提：打开时有这条提醒")
        self.assertEqual(data["after"]["sheet"], "review", "弹层仍开着")
        self.assertNotIn("电脑上没开自动登录", data["after"]["warns"],
                         "轮询带回新状态后，弹层里的提醒要跟着变：%r" % data["after"]["warns"])
        self.assertIn("24 小时", data["after"]["warns"], "与设置无关的那条提醒照旧在")

    def test_items_follow_the_new_list_while_the_sheet_is_open(self):
        """电脑上那一场刚被报上（列表里变成已报名）：弹层里这一条要从计划里消失。"""
        res = run_phone(REVIEW_SETUP + r"""
/* 沙箱的元素桩清不掉子节点，数节点没有意义：记下每次重画交给批次渲染的场次 */
const seen = [];
const original = PhoneModel.reviewBatches;
PhoneModel.reviewBatches = (items, nowS) => { seen.push(items.map((item) => item.id)); return original(items, nowS); };
const before = peek();
ui.ingest({state: {activities: [act("a1", "甲活动", 2),
  Object.assign(act("a2", "乙活动", 3), {signed: true})]}});
out.push({ before, after: peek(), seen, selected: ui.model.selected.slice() });
""")
        data = res[0]
        self.assertEqual(data["before"]["sheet"], "review", "前提：核对弹层开着")
        self.assertEqual(data["selected"], ["a1"], "已报名的场次移出勾选")
        self.assertEqual(data["seen"], [["a1"]],
                         "轮询之后弹层要按新的勾选重画，只剩一场：%r" % data["seen"])

    def test_sheet_closes_when_the_poll_leaves_nothing_to_review(self):
        """勾选被新状态清空：不留一个空的核对弹层（与手点「移除」到最后一场同样收起）。"""
        res = run_phone(REVIEW_SETUP + r"""
ui.ingest({state: {activities: [
  Object.assign(act("a1", "甲活动", 2), {signed: true}),
  Object.assign(act("a2", "乙活动", 3), {signed: true})]}});
out.push({ sheet: ui.model.sheetId, selected: ui.model.selected.slice() });
""")
        data = res[0]
        self.assertEqual(data["selected"], [])
        self.assertEqual(data["sheet"], "", "没有可核对的场次，弹层要收起")

    def test_other_sheets_are_not_redrawn_or_closed_by_ingest(self):
        """守卫：弹层开的是「更多」时，轮询不去碰核对内容，也不收起「更多」。"""
        res = run_phone(REVIEW_SETUP + r"""
ui.closeSheet(true);
ui.openSheet("more");
const marker = $("review-warns").innerHTML = "占位：不应被改写";
ui.ingest({state: {relogin_setup: {saved: true, ocr_ready: true, paused: false}}});
out.push({ sheet: ui.model.sheetId, warns: $("review-warns").innerHTML, marker });
""")
        data = res[0]
        self.assertEqual(data["sheet"], "more")
        self.assertEqual(data["warns"], data["marker"])


class LastSyncUsesBeijingTimeTests(unittest.TestCase):
    """U7：「最近同步 HH:MM」按北京时间写，手机时区不同也一样。"""

    # 手机时区 UTC-10，与北京时间差 18 小时，任何时刻都不会碰巧相等
    PHONE_TZ = "Pacific/Honolulu"

    def test_tz_override_really_changes_the_phone_local_time(self):
        """前提自检：沙箱里 TZ 生效，手机本机时间和北京时间确实差开。"""
        res = run_phone("""
out.push({ offset: new Date(Date.UTC(2026, 10, 10, 6, 0, 0)).getTimezoneOffset() });
""", tz=self.PHONE_TZ)
        self.assertEqual(res[0]["offset"], 600, "本机时区没有按 TZ 变成 UTC-10，下面的用例就失去意义")

    def test_sync_line_shows_the_beijing_time_of_the_business_clock(self):
        res = run_phone(r"""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {business_clock: {state: "ready",
  epoch_s: Date.UTC(2026, 10, 10, 6, 5, 0) / 1000, tick_s: 1000000, sampled_tick_s: 1000000, age_s: 0},
  activities: []}});
out.push($("last-sync").textContent);
""", tz=self.PHONE_TZ)
        self.assertEqual(res[0], "最近同步 14:05", "北京时间 14:05，而不是手机本机时钟的读数")

    def test_sync_line_does_not_borrow_the_phone_clock_when_the_clock_is_unavailable(self):
        res = run_phone(r"""
const ui = PhoneUI;
ui.model.lastOkAt = Date.now();
ui.ingest({state: {business_clock: {state: "unavailable"}, activities: []}});
const phone = new Date();
const phoneText = String(phone.getHours()).padStart(2, "0") + ":" + String(phone.getMinutes()).padStart(2, "0");
out.push({ text: $("last-sync").textContent, phoneText });
""", tz=self.PHONE_TZ)
        data = res[0]
        self.assertNotIn(data["phoneText"], data["text"], "时钟不可用时不能拿手机本机时钟冒充：%r" % data)
        self.assertEqual(data["text"], "最近同步 --:--")


if __name__ == "__main__":
    unittest.main()
