#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R1/R2（计划 20261107-conflict-cancel）：已报名活动补回列表，详情追加取消/可报三态。

只替换网络边界（_post 列表、_get 详情、check_token），cmd_list、fetch_activities、
enrich_attendance_items、fetch_activity_detail、parse_attendance_detail 全走生产代码。

@author Author
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.dirname(HERE)
for p in (LOCAL, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import grab  # noqa: E402
import time_contract  # noqa: E402
from fixtures.business_clock import FakeBusinessClock  # noqa: E402

NOW = 1793100000.0     # 假「北京时间」锚点（与真实系统日期无关）


def _t(offset):
    return grab.school_time_text(NOW + offset)


def raw_row(aid, *, signed=False, sign_end=-9000.0, act_start=3600.0, act_end=7200.0,
            sign_start=-86400.0):
    """学校 /rjyHd/listActivity 的原始行（拼音缩写字段）。偏移为 None 表示学校没给。"""
    def text(offset):
        return "" if offset is None else _t(offset)
    return {"id": aid, "hdmc": "活动" + aid, "hdlx": "讲座", "hddd": "A101",
            "bmkssj": text(sign_start), "bmjssj": text(sign_end),
            "hdkssj": text(act_start), "hdjssj": text(act_end),
            "bmzt": 1 if signed else 0}


def detail_reply(**fields):
    """getInfo 回包：只放签到相关与本计划关心的键。"""
    data = {"sfxyqd": 0, "sfxyqt": 0}
    data.update(fields)
    return {"code": 1, "message": "操作成功！", "data": data}


class _ListHarness(unittest.TestCase):
    """cmd_list 的网络边界替身与业务时钟注入、现场还原。"""

    def run_list(self, rows, details=None, *, all_rows=False, clock=True):
        """details：id → getInfo 回包；缺省回 detail_reply()；值为 None 表示详情失败。"""
        details = details or {}
        detail_calls = []

        def fake_post(path, payload=None, tok=None, timeout=None, budget=None):
            return {"code": 1, "data": {"count": len(rows), "list": rows}}

        def fake_get(path, tok=None, timeout=None):
            aid = path.rsplit("/", 1)[-1]
            detail_calls.append(aid)
            reply = details.get(aid, detail_reply())
            return {"code": -1, "message": "URLError"} if reply is None else reply

        original_clock = dict(grab._CLOCK)
        original_now = time_contract._BUSINESS_NOW
        if clock:
            grab.configure_business_clock(FakeBusinessClock(epoch=NOW))
        else:
            grab._CLOCK.update({"now": None, "bounds": None, "meta": None})
        out = io.StringIO()
        try:
            grab.DETAIL_CACHE.clear()
            with mock.patch.object(grab, "_post", fake_post), \
                    mock.patch.object(grab, "_get", fake_get), \
                    mock.patch.object(grab, "check_token", lambda budget=None: (True, "ok")), \
                    mock.patch.object(grab, "log", lambda msg: None), \
                    contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = grab.cmd_list(SimpleNamespace(all=all_rows, json=True))
        finally:
            grab._CLOCK.update(original_clock)
            time_contract.configure_time_source(original_now)
            grab.DETAIL_CACHE.clear()
        self.assertEqual(code, 0, out.getvalue())
        return json.loads(out.getvalue().strip()), detail_calls


class KeepInListTests(unittest.TestCase):
    """R1：keep_in_list 纯函数。"""

    def act(self, **kw):
        base = {"signed": True, "sign_end": _t(-9000), "act_end": _t(3600)}
        base.update(kw)
        return base

    def test_signed_deadline_passed_but_activity_not_over_is_kept(self):
        self.assertTrue(grab.keep_in_list(self.act(), NOW))
        self.assertFalse(grab.still_relevant(self.act(), NOW),
                         "前提：这场按旧规则（截止超过 1 小时）会被筛掉")

    def test_signed_activity_already_over_is_dropped(self):
        self.assertFalse(grab.keep_in_list(self.act(act_end=_t(-1)), NOW))

    def test_activity_ending_exactly_now_counts_as_not_over(self):
        self.assertTrue(grab.keep_in_list(self.act(act_end=_t(0)), NOW))

    def test_signed_without_parsable_act_end_follows_the_old_rule(self):
        for act_end in ("", None, "待定", "2026-13-45 99:00:00"):
            with self.subTest(act_end=act_end):
                self.assertFalse(grab.keep_in_list(self.act(act_end=act_end), NOW))
        self.assertTrue(grab.keep_in_list(self.act(act_end="", sign_end=_t(600)), NOW),
                        "报名还没截止的照旧保留，与 act_end 无关")

    def test_unsigned_deadline_passed_is_dropped_even_if_activity_not_over(self):
        self.assertFalse(grab.keep_in_list(self.act(signed=False), NOW))

    def test_still_relevant_rows_are_kept_regardless_of_signed(self):
        self.assertTrue(grab.keep_in_list(
            {"signed": False, "sign_end": _t(600), "act_end": ""}, NOW))
        self.assertTrue(grab.keep_in_list(
            {"signed": False, "sign_end": "", "act_end": ""}, NOW))


class ListSignedFilterTests(_ListHarness):
    """R1：cmd_list 默认筛选补回已报名且举办没结束的活动。"""

    def test_signed_deadline_passed_activity_not_over_stays_in_list(self):
        rows = [
            raw_row("signed-late", signed=True, sign_end=-9000, act_end=3600),
            raw_row("open", sign_end=7200),
        ]
        data, details = self.run_list(rows)
        self.assertEqual([r["id"] for r in data], ["open", "signed-late"],
                         "报名截止超过 1 小时但举办没结束的已报名活动留在列表，且垫底")
        self.assertTrue(data[-1]["signed"])
        self.assertEqual(data[-1]["state"], "已报名")
        self.assertIn("signed-late", details, "补回的行也要补详情（要取 cancel_allowed）")

    def test_signed_activity_already_over_is_filtered_out(self):
        rows = [raw_row("signed-over", signed=True, sign_end=-90000, act_start=-7200,
                        act_end=-3600),
                raw_row("open", sign_end=7200)]
        data, details = self.run_list(rows)
        self.assertEqual([r["id"] for r in data], ["open"])
        self.assertNotIn("signed-over", details, "筛掉的行不发详情请求")

    def test_signed_without_act_end_follows_the_old_rule(self):
        rows = [raw_row("no-end", signed=True, sign_end=-9000, act_end=None),
                raw_row("no-end-open", signed=True, sign_end=600, act_end=None),
                raw_row("open", sign_end=7200)]
        data, _ = self.run_list(rows)
        self.assertEqual(sorted(r["id"] for r in data), ["no-end-open", "open"],
                         "act_end 缺失的已报名活动：报名截止超过 1 小时仍被筛掉")

    def test_unsigned_deadline_passed_still_filtered_even_if_activity_not_over(self):
        rows = [raw_row("unsigned-late", signed=False, sign_end=-9000, act_end=3600),
                raw_row("open", sign_end=7200)]
        data, _ = self.run_list(rows)
        self.assertEqual([r["id"] for r in data], ["open"])

    def test_all_flag_is_unchanged(self):
        rows = [raw_row("signed-late", signed=True, sign_end=-9000, act_end=3600),
                raw_row("signed-over", signed=True, sign_end=-90000, act_start=-7200,
                        act_end=-3600),
                raw_row("unsigned-late", signed=False, sign_end=-9000, act_end=3600),
                raw_row("open", sign_end=7200)]
        data, _ = self.run_list(rows, all_rows=True)
        self.assertEqual(len(data), 4, "--all 保留全部")

    def test_without_clock_every_row_is_kept(self):
        rows = [raw_row("signed-over", signed=True, sign_end=-90000, act_start=-7200,
                        act_end=-3600),
                raw_row("open", sign_end=7200)]
        data, _ = self.run_list(rows, clock=False)
        self.assertEqual(len(data), 2, "北京时间不可用：不筛选，行为不变")


class DetailCancelFlagsTests(_ListHarness):
    """R2：qxbm / sfkybm → cancel_allowed / can_sign 三态，list --json 带这两个键。"""

    def one(self, reply):
        data, _ = self.run_list([raw_row("a1", sign_end=7200)], {"a1": reply})
        return data[0]

    def test_qxbm_and_sfkybm_map_to_tri_state(self):
        cases = [
            ({"qxbm": 1, "sfkybm": 1}, True, True),
            ({"qxbm": 0, "sfkybm": 0}, False, False),
            ({"qxbm": "1", "sfkybm": "0"}, True, False),
            ({"qxbm": True, "sfkybm": False}, True, False),
        ]
        for fields, cancel, sign in cases:
            with self.subTest(fields=fields):
                row = self.one(detail_reply(**fields))
                self.assertIs(row["cancel_allowed"], cancel)
                self.assertIs(row["can_sign"], sign)

    def test_missing_or_unrecognised_values_are_none(self):
        for fields in ({}, {"qxbm": None, "sfkybm": None}, {"qxbm": "", "sfkybm": ""},
                       {"qxbm": "abc", "sfkybm": 2}, {"qxbm": 7}):
            with self.subTest(fields=fields):
                row = self.one(detail_reply(**fields))
                self.assertIsNone(row["cancel_allowed"], "认不出就是不知道，不猜")
                self.assertIsNone(row["can_sign"])

    def test_keys_map_independently(self):
        row = self.one(detail_reply(qxbm=1))
        self.assertIs(row["cancel_allowed"], True)
        self.assertIsNone(row["can_sign"])

    def test_detail_failure_gives_none_for_both_keys(self):
        row = self.one(None)
        self.assertIsNone(row["cancel_allowed"])
        self.assertIsNone(row["can_sign"])
        self.assertIn("cancel_allowed", row)
        self.assertIn("can_sign", row)
        self.assertEqual(row["attendance_state"], "pending", "详情失败仍是同步中")

    def test_failure_of_one_detail_does_not_blank_the_others(self):
        rows = [raw_row("a1", sign_end=7200), raw_row("a2", sign_end=7200)]
        data, _ = self.run_list(rows, {"a1": None, "a2": detail_reply(qxbm=1, sfkybm=0)})
        by_id = {r["id"]: r for r in data}
        self.assertIsNone(by_id["a1"]["cancel_allowed"])
        self.assertIs(by_id["a2"]["cancel_allowed"], True)
        self.assertIs(by_id["a2"]["can_sign"], False)

    def test_every_listed_row_carries_both_keys(self):
        rows = [raw_row("a1", sign_end=7200),
                raw_row("a2", signed=True, sign_end=-9000, act_end=3600)]
        data, _ = self.run_list(rows)
        for row in data:
            self.assertIn("cancel_allowed", row)
            self.assertIn("can_sign", row)

    def test_false_from_detail_is_not_swallowed_by_truthiness_merge(self):
        # _apply_attendance 对普通键用「没有才补」；False 必须被当成明确回答写进去
        item = {"id": "x"}
        grab._apply_attendance(item, {"checkin_required": None, "checkout_required": None,
                                      "cancel_allowed": False, "can_sign": False})
        self.assertIs(item["cancel_allowed"], False)
        self.assertIs(item["can_sign"], False)

    def test_detail_with_missing_keys_still_gets_none(self):
        item = {"id": "x"}
        grab._apply_attendance(item, {"checkin_required": False, "checkout_required": False})
        self.assertIsNone(item["cancel_allowed"])
        self.assertIsNone(item["can_sign"])

    def test_concurrency_and_timeout_constants_are_untouched(self):
        self.assertEqual(grab.DETAIL_CONCURRENCY, 4)
        self.assertEqual(grab.DETAIL_TIMEOUT_S, 12.0)


class DemoDataTests(unittest.TestCase):
    """演示数据补的冲突与取消样本（截图与取消流程用）：时间相对演示时钟，形状同 list --json。"""

    def items(self):
        from domain import demo_data
        rows = demo_data.demo_items(NOW, grab.school_time_text)
        return {row["id"]: row for row in rows}

    def test_every_demo_row_carries_both_tri_state_keys(self):
        for row in self.items().values():
            self.assertIn("cancel_allowed", row, row["id"])
            self.assertIn("can_sign", row, row["id"])
            self.assertIn(row["cancel_allowed"], (True, False, None))

    def test_signed_cross_day_dorm_check_is_still_inside_its_cancel_window(self):
        dorm = self.items()["demo-dorm"]
        self.assertEqual(dorm["name"], "宿舍查寝")
        self.assertTrue(dorm["signed"])
        self.assertIs(dorm["cancel_allowed"], True)
        sign_start = grab.parse_ts(dorm["sign_start"])
        sign_end = grab.parse_ts(dorm["sign_end"])
        self.assertLessEqual(sign_start, NOW)
        self.assertGreater(sign_end, NOW, "报名窗口还没关：可取消")
        start_day = dorm["act_start"][:10]
        end_day = dorm["act_end"][:10]
        from datetime import date
        span = (date.fromisoformat(end_day) - date.fromisoformat(start_day)).days + 1
        self.assertGreaterEqual(span, 3, "举办时段跨三个日历日以上")
        self.assertGreater(grab.parse_ts(dorm["act_end"]), NOW, "举办还没结束（R1 会保留它）")

    def test_unsigned_interview_overlaps_the_dorm_check(self):
        rows = self.items()
        dorm, mock_interview = rows["demo-dorm"], rows["demo-interview"]
        self.assertEqual(mock_interview["name"], "模拟面试")
        self.assertFalse(mock_interview["signed"])
        self.assertLess(grab.parse_ts(mock_interview["act_start"]),
                        grab.parse_ts(dorm["act_end"]))
        self.assertGreater(grab.parse_ts(mock_interview["act_end"]),
                           grab.parse_ts(dorm["act_start"]))

    def test_has_unsigned_samples_for_both_cancel_answers(self):
        rows = self.items().values()
        self.assertTrue([r for r in rows if not r["signed"] and r["cancel_allowed"] is False],
                        "缺「报后不可退」的未报名样本")
        self.assertTrue([r for r in rows if not r["signed"] and r["cancel_allowed"] is True],
                        "缺「报后可退」的未报名样本")

    def test_has_a_signed_cancellable_sample_inside_the_sign_window(self):
        found = [r for r in self.items().values()
                 if r["signed"] and r["cancel_allowed"] is True
                 and grab.parse_ts(r["sign_start"]) <= NOW <= grab.parse_ts(r["sign_end"])]
        self.assertTrue(found, "缺「窗口内、可取消、已报名」样本")

    def test_non_overlap_samples_do_not_touch_the_signed_dorm(self):
        rows = self.items()
        dorm = rows["demo-dorm"]
        for aid in ("demo-nocancel", "demo-community"):
            row = rows[aid]
            apart = (grab.parse_ts(row["act_end"]) <= grab.parse_ts(dorm["act_start"])
                     or grab.parse_ts(row["act_start"]) >= grab.parse_ts(dorm["act_end"]))
            self.assertTrue(apart, aid)


if __name__ == "__main__":
    unittest.main()
