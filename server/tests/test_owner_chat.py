"""私聊自助一批的服务器离线用例：详情请求、个人场次规则、取消、冲突、提醒与变动通知。

全部不联网、不读 data/ 与 config.json：学校请求与飞书发送都换成替身，
临时目录落在 tempfile.gettempdir() 下面，可用 CAMPUS_TEST_ROOT 覆盖。

@author Author
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

try:  # Windows 控制台默认 GBK，打中文断言信息会直接抛 UnicodeEncodeError
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
for _sub in ("lib", "push", "signup"):
    sys.path.insert(0, str(ROOT / "scripts" / _sub))

import cancel_signup as cs     # noqa: E402
import attend_remind as ar     # noqa: E402
import activity_watch as aw    # noqa: E402
import personal_notice as pn  # noqa: E402
import card                    # noqa: E402
import mine_rules as mr        # noqa: E402
import school_detail as sd     # noqa: E402
import watchlist as wl         # noqa: E402


class RuleTableTests(unittest.TestCase):
    """三态、已报名判定、区间与取消前置的表驱动用例。"""

    def test_tri_state_keeps_unknown(self):
        cases = [(1, True), ("1", True), (True, True), (0, False), ("0", False),
                 ("false", False), ("是", True), ("无需", False),
                 ("", None), (None, None), ("看不懂", None), (7, None)]
        for raw, expect in cases:
            self.assertIs(mr.tri_state(raw), expect, "输入 %r" % (raw,))

    def test_parse_attendance_follows_flags_and_times(self):
        cases = [
            ({"sfxyqd": 1, "qdkssj": "2026-11-25 18:30:00",
              "sfxyqt": "0", "qtkssj": "2026-11-25 21:00:00"},
             (True, "2026-11-25 18:30:00", False, "")),
            ({"qdkssj": "2026-11-25 18:30:00"},
             (True, "2026-11-25 18:30:00", None, "")),
            ({"sfxyqd": 0, "qdkssj": "2026-11-25 18:30:00"},
             (False, "", None, "")),
            ({}, (None, "", None, "")),
        ]
        for raw, expect in cases:
            got = mr.parse_attendance(raw)
            self.assertEqual((got["checkin_required"], got["checkin_start"],
                              got["checkout_required"], got["checkout_start"]),
                             expect, "输入 %r" % (raw,))

    def test_parse_attendance_accepts_wrapped_response_and_cancel_flag(self):
        got = mr.parse_attendance({"code": 1, "data": {
            "qxbm": "1", "sfkybm": 0, "bmkssj": "2026-11-20 08:00:00",
            "bmjssj": "2026-11-24 22:00:00"}})
        self.assertIs(got["cancel_allowed"], True)
        self.assertIs(got["can_sign"], False)
        self.assertEqual(got["sign_end"], "2026-11-24 22:00:00")
        self.assertIsNone(mr.parse_attendance({})["cancel_allowed"])

    def test_join_state_table(self):
        cases = [(None, False), ({}, False), ([], False), ({"sfcx": 1}, False),
                 ({"sfbm": 0}, False), ({"sfbm": 1}, True), ({"bmsj": "x"}, True),
                 ("看不懂", True)]
        for payload, expect in cases:
            self.assertIs(mr.join_state(payload), expect, "输入 %r" % (payload,))
        self.assertIsNone(mr.joined_from_response({"code": 4001}))
        self.assertFalse(mr.joined_from_response({"code": 1, "data": None}))
        self.assertTrue(mr.joined_from_response({"code": "1.0", "data": {"sfbm": 1}}))

    def test_overlap_is_half_open(self):
        a = mr.interval("2026-11-25 18:00:00", "2026-11-25 20:00:00")
        self.assertTrue(mr.overlaps(a, mr.interval("2026-11-25 19:00:00",
                                              "2026-11-25 21:00:00")))
        self.assertFalse(mr.overlaps(a, mr.interval("2026-11-25 20:00:00",
                                               "2026-11-25 22:00:00")))
        self.assertTrue(mr.overlaps(a, mr.interval("2026-11-25 18:30:00",
                                              "2026-11-25 19:30:00")))
        self.assertIsNone(mr.overlaps(a, None))
        self.assertIsNone(mr.interval("2026-11-25 20:00:00", "2026-11-25 18:00:00"))

    def test_cancel_precheck_table(self):
        now = datetime(2026, 11, 24, 12, 0)
        window = ("2026-11-20 08:00:00", "2026-11-24 22:00:00")
        ok = dict(now=now, joined=True, allowed=True, sign_start=window[0],
                  sign_end=window[1], clock_ok=True)
        self.assertIsNone(mr.cancel_precheck(**ok))
        cases = [
            (dict(ok, clock_ok=False), "clock_unavailable"),
            (dict(ok, joined=None), "unknown_state"),
            (dict(ok, joined=False), "not_signed"),
            (dict(ok, allowed=False), "not_allowed"),
            (dict(ok, allowed=None), "not_allowed"),
            (dict(ok, now=datetime(2026, 11, 19, 12, 0)), "window_closed"),
            (dict(ok, now=datetime(2026, 11, 25, 12, 0)), "window_closed"),
            (dict(ok, sign_end=""), "unknown_state"),
        ]
        for kwargs, expect in cases:
            self.assertEqual(mr.cancel_precheck(**kwargs), expect, "输入 %r" % (kwargs,))

    def test_span_text_cross_day_and_midnight(self):
        self.assertEqual(mr.span_text("2026-11-25 18:00:00", "2026-11-25 20:30:00"),
                         "11月25日 18:00–20:30")
        self.assertEqual(mr.span_text("2026-11-25 18:00:00", "2026-11-25 00:00:00"),
                         "")
        self.assertEqual(mr.span_text("2026-11-25 18:00:00", "2026-11-26 00:00:00"),
                         "11月25日 18:00–24:00")
        self.assertEqual(mr.span_text("2026-11-08 22:40:00", "2026-11-10 23:20:00"),
                         "11月8日 22:40 – 11月10日 23:20（跨3天）")
        self.assertEqual(mr.span_text("", "2026-11-10 23:20:00"), "")
        self.assertEqual(mr.span_days(datetime(2026, 11, 8, 22, 40),
                                      datetime(2026, 11, 9, 0, 0)), 1)


class DetailRequestTests(unittest.TestCase):
    """请求构造：GET 不带签名，POST 带四个网关头，都走同一个地址前缀。"""

    def setUp(self):
        self.seen = []
        patcher = mock.patch.object(sd, "SITE_CONFIGURED", True)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(sd, "_open", self._fake_open)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fake_open(self, req, timeout):
        self.seen.append((req, timeout))
        return json.dumps({"code": 1, "data": {"sfbm": 1}})

    def test_detail_and_cancel_are_get_without_signature(self):
        self.assertEqual(sd.get_detail("a b", "tok", timeout=3)["code"], 1)
        sd.cancel_signup("a b", "tok", timeout=4)
        for req, timeout in self.seen:
            self.assertEqual(req.get_method(), "GET")
            self.assertIsNone(req.get_header("X-token"))
            self.assertEqual(req.get_header("Token"), "tok")
        self.assertEqual(self.seen[0][1], 3.0)
        self.assertEqual(self.seen[1][1], 4.0)
        self.assertIn("/rjyHd/getInfo/a%20b", self.seen[0][0].full_url)
        self.assertIn("/rjyHdCyr/cancel/a%20b", self.seen[1][0].full_url)

    def test_join_info_posts_empty_json_with_gateway_headers(self):
        body = sd.get_join_info("act-1", "tok")
        self.assertEqual(body["code"], 1)
        req, _timeout = self.seen[0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.data, b"{}")
        self.assertEqual(req.get_header("Content-type"), "application/json")
        for name in ("X-page-ticket", "X-timestamp", "X-nonce", "X-token"):
            self.assertTrue(req.get_header(name), "缺少 %s" % name)

    def test_signature_depends_on_path_body_and_nonce(self):
        fixed = dict(timestamp_ms=1700000000123, nonce="n" * 32)
        base = sd.sign_headers("/rjyHdCyr/getJoinInfo/a", b"{}", **fixed)
        again = sd.sign_headers("/rjyHdCyr/getJoinInfo/a", b"{}", **fixed)
        self.assertEqual(base, again)
        other_path = sd.sign_headers("/rjyHdCyr/getJoinInfo/b", b"{}", **fixed)
        other_body = sd.sign_headers("/rjyHdCyr/getJoinInfo/a", b"{\"x\":1}",
                                     **fixed)
        other_nonce = sd.sign_headers("/rjyHdCyr/getJoinInfo/a", b"{}",
                                      timestamp_ms=1700000000123, nonce="m" * 32)
        self.assertNotEqual(base["X-Token"], other_path["X-Token"])
        self.assertNotEqual(base["X-Token"], other_body["X-Token"])
        self.assertNotEqual(base["X-Token"], other_nonce["X-Token"])
        self.assertEqual(base["X-Timestamp"], "1700000000123")

    def test_missing_token_and_empty_id_raise_before_request(self):
        with self.assertRaises(sd.SchoolConfigError):
            sd.get_detail("act-1", "  ")
        with self.assertRaises(sd.SchoolRequestError):
            sd.get_join_info("", "tok")
        self.assertEqual(self.seen, [])

    def test_http_error_and_bad_payload_are_distinct(self):
        patcher = mock.patch.object(sd, "_open", side_effect=sd.SchoolHTTPError(502, "x"))
        patcher.start()
        self.addCleanup(patcher.stop)
        with self.assertRaises(sd.SchoolHTTPError):
            sd.get_detail("act-1", "tok")
        with self.assertRaises(sd.SchoolPayloadError):
            sd._parse("<html>")


class CancelFlowTests(unittest.TestCase):
    """取消链路：前置不满足就一个请求都不发，取消只发一次，成败只看复查。"""

    NOW = datetime(2026, 11, 24, 12, 0)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cancel-flow-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.object(cs, "LOCK_DIR", Path(self.tmp))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cancelled = []

    def _joins(self, *values):
        """按调用顺序给出「是否已报名」：第一次是前置查询，第二次是取消后复查。"""
        seq = list(values)

        def fake(activity_id, token, timeout=0):
            value = seq.pop(0)
            if isinstance(value, Exception):
                raise value
            if value is None:
                return {"code": 1, "data": {}}   # 查不到是否报名：按未知处理
            return {"code": 1, "data": {"sfbm": 1 if value else 0}}

        return fake

    def _detail(self, allowed=True):
        data = {"qxbm": "1" if allowed else "0",
                "bmkssj": "2026-11-20 08:00:00", "bmjssj": "2026-11-24 22:00:00"}
        return lambda activity_id, token, timeout=0: {"code": 1, "data": data}

    def _cancel(self, message="", boom=False):
        def fake(activity_id, token, timeout=0):
            self.cancelled.append(activity_id)
            if boom:
                raise sd.SchoolNetworkError("boom")
            return {"code": 1, "message": message}

        return fake

    def _run(self, join, allowed=True, cancel=None, remove=None):
        return cs.run_cancel("evt-1", "测试活动", "tok", now=self.NOW, join=join,
                             detail=self._detail(allowed),
                             cancel=cancel or self._cancel(),
                             remove=remove or (lambda activity_id: True))

    def test_success_cancels_once_and_drops_watchlist(self):
        removed = []
        result = self._run(self._joins(True, False),
                           remove=lambda activity_id: removed.append(activity_id) or True)
        self.assertEqual(result["kind"], "cancelled")
        self.assertTrue(result["ok"])
        self.assertTrue(result["removed_from_watchlist"])
        self.assertEqual(removed, ["evt-1"])
        self.assertEqual(self.cancelled, ["evt-1"], "取消接口只发一次")
        self.assertTrue(result["card"]["header"])

    def test_refused_keeps_watchlist_and_sanitizes_school_message(self):
        removed = []
        message = "不在可取消时段\n\x00" + "字" * 120
        result = self._run(self._joins(True, True),
                           cancel=self._cancel(message=message),
                           remove=lambda activity_id: removed.append(activity_id) or True)
        self.assertEqual(result["kind"], "refused")
        self.assertFalse(result["ok"])
        self.assertNotIn("removed_from_watchlist", result)
        self.assertEqual(removed, [], "没取消成不能动预报名清单")
        self.assertLessEqual(len(result["message"]), cs.MESSAGE_MAX)
        self.assertNotIn("\n", result["message"])
        self.assertNotIn("\x00", result["message"])

    def test_unknown_when_recheck_fails_without_retry(self):
        result = self._run(self._joins(True, sd.SchoolNetworkError("boom")))
        self.assertEqual(result["kind"], "unknown")
        self.assertEqual(self.cancelled, ["evt-1"], "复查失败也不能重发取消")

    def test_precheck_failure_sends_nothing(self):
        cases = [
            (self._joins(False), True, "not_signed"),
            (self._joins(True), False, "not_allowed"),
            (self._joins(sd.SchoolNetworkError("boom")), True, "unknown_state"),
        ]
        for join, allowed, reason in cases:
            result = self._run(join, allowed=allowed)
            self.assertEqual(result["kind"], "precheck_failed", "原因 %s" % reason)
            self.assertEqual(result["reason"], reason)
            self.assertFalse(result["ok"])
        self.assertEqual(self.cancelled, [], "前置不满足时零请求")

    def test_empty_id_and_missing_token_short_circuit(self):
        empty = cs.run_cancel("  ", "活动", "tok", now=self.NOW)
        self.assertEqual((empty["kind"], empty["reason"]), ("precheck_failed", "not_in_list"))
        no_token = cs.run_cancel("evt-1", "活动", "  ", now=self.NOW)
        self.assertEqual((no_token["kind"], no_token["reason"]),
                         ("precheck_failed", "login_expired"))
        self.assertEqual(self.cancelled, [])

    def test_busy_when_lock_is_held(self):
        class Held:
            def __enter__(self):
                return False

            def __exit__(self, *exc):
                return False

        patcher = mock.patch.object(cs, "try_file_lock", lambda path: Held())
        patcher.start()
        self.addCleanup(patcher.stop)
        result = cs.run_cancel("evt-1", "活动", "tok", now=self.NOW,
                               join=self._joins(True), detail=self._detail(),
                               cancel=self._cancel())
        self.assertEqual(result["kind"], "busy")
        self.assertEqual(self.cancelled, [])

    def test_confirm_card_survives_detail_failure(self):
        def boom(activity_id, token, timeout=0):
            raise sd.SchoolNetworkError("boom")

        patcher = mock.patch.object(sd, "get_detail", boom)
        patcher.start()
        self.addCleanup(patcher.stop)
        card = cs.confirm_card("evt-1", "测试活动", "tok")
        self.assertTrue(card["header"])

class WatchlistConflictTests(unittest.TestCase):
    """预报名冲突：写清单前比举办时段，撞车或查不清一律拒绝且不动清单。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="watchlist-conflict-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name, value in (("FILE", Path(self.tmp) / "watchlist.json"),
                            ("LOCK", Path(self.tmp) / "watchlist.lock")):
            patcher = mock.patch.object(wl, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _items(self, *extra):
        return [{"id": "evt-new", "name": "新场次", "signed": False,
                 "act_start": "2026-12-01 18:00:00",
                 "act_end": "2026-12-01 20:00:00"}] + list(extra)

    def _open_at(self):
        return (datetime.now() + timedelta(hours=1)).strftime(wl.FMT)

    def _add(self, items=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = wl.main(["add", "--id", "evt-new", "--name", "新场次",
                            "--at", self._open_at()])
        return code, out.getvalue()

    def _add_with_items(self, items):
        with mock.patch.object(wl, "_list_items", lambda: items):
            return self._add()

    def test_overlap_with_joined_activity_is_refused(self):
        joined = {"id": "evt-joined", "name": "已报名的", "signed": True,
                  "act_start": "2026-12-01 19:00:00", "act_end": "2026-12-01 21:00:00"}
        code, out = self._add_with_items(self._items(joined))
        self.assertEqual(code, 1)
        self.assertIn("已报名的", out)
        self.assertEqual(wl.load(), [], "拒绝时清单文件不能变")

    def test_boundary_touching_is_not_a_conflict(self):
        joined = {"id": "evt-joined", "name": "前一场", "signed": True,
                  "act_start": "2026-12-01 16:00:00", "act_end": "2026-12-01 18:00:00"}
        code, _ = self._add_with_items(self._items(joined))
        self.assertEqual(code, 0)
        self.assertEqual([e["id"] for e in wl.load()], ["evt-new"])

    def test_unpublished_time_is_allowed_with_note(self):
        code, out = self._add_with_items([{"id": "evt-new", "name": "新场次"}])
        self.assertEqual(code, 0)
        self.assertIn("未公布", out)
        self.assertEqual([e["id"] for e in wl.load()], ["evt-new"])

    def test_joined_activity_with_unknown_time_is_refused(self):
        code, out = self._add_with_items(self._items(
            {"id": "evt-joined", "name": "已报名的", "signed": True}))
        self.assertEqual(code, 1)
        self.assertIn("举办时间未知", out)
        self.assertEqual(wl.load(), [])

    def test_queued_entry_overlap_is_refused(self):
        queued = {"id": "evt-queued", "name": "排队的", "status": "queued",
                  "open_at": "2026-12-01 08:00:00"}
        wl.FILE.write_text(json.dumps({"entries": [queued]}, ensure_ascii=False),
                           encoding="utf-8")
        code, out = self._add_with_items(self._items(
            {"id": "evt-queued", "name": "排队的",
             "act_start": "2026-12-01 19:30:00", "act_end": "2026-12-01 21:00:00"}))
        self.assertEqual(code, 1)
        self.assertIn("排队", out)
        self.assertEqual([e["id"] for e in wl.load()], ["evt-queued"])

    def test_list_failure_refuses_instead_of_letting_through(self):
        def boom(*args, **kwargs):
            raise RuntimeError("school down")

        patcher = mock.patch.object(wl, "load_session", lambda: {"token": "tok"})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(wl.fetch, "fetch_all", boom)
        patcher.start()
        self.addCleanup(patcher.stop)
        code, out = self._add()
        self.assertEqual(code, 1)
        self.assertIn("取活动列表失败", out)
        self.assertEqual(wl.load(), [])

class PendingCardNoteTests(unittest.TestCase):
    """预报名卡片：举办时间没公布的排队场次要说明「没法检查冲突」。"""

    NOW = datetime(2026, 11, 24, 12, 0)

    def _text(self, item):
        got = card.grab_pending_card([item], self.NOW, {item["id"]})
        return json.dumps(got, ensure_ascii=False)

    def test_queued_without_act_time_is_marked(self):
        item = {"id": "evt-1", "name": "新场次", "sign_start": "2026-12-01 08:00:00"}
        self.assertIn("暂时没法检查", self._text(item))

    def test_queued_with_act_time_has_no_note(self):
        item = {"id": "evt-1", "name": "新场次", "sign_start": "2026-12-01 08:00:00",
                "act_start": "2026-12-05 18:00:00"}
        self.assertNotIn("暂时没法检查", self._text(item))

class AttendRemindTests(unittest.TestCase):
    """开始与签退提醒：窗口、去重、发送失败不记、无临近场次零请求。"""

    NOW = datetime(2026, 11, 24, 17, 40)   # 距 18:00 开始 20 分钟

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="attend-remind-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name, value in (("STATE", Path(self.tmp) / "state.json"),
                            ("LOCK", Path(self.tmp) / "state.lock")):
            patcher = mock.patch.object(ar, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sent = []
        self.details = []

    def _item(self, **extra):
        item = {"id": "evt-1", "name": "讲座", "signed": True, "place": "活动中心",
                "act_start": "2026-11-24 18:00:00", "act_end": "2026-11-24 20:00:00"}
        item.update(extra)
        return item

    def _detail(self, **extra):
        facts = {"sfxyqd": 1, "qdkssj": "2026-11-24 17:45:00",
                 "qdjssj": "2026-11-24 18:10:00", "sfxyqt": 0}
        facts.update(extra)

        def fake(activity_id, token, **kwargs):
            self.details.append(activity_id)
            return facts

        return fake

    def _run(self, items, now=None, detail=None, send=None):
        def collect(text):
            self.sent.append(text)
            return True

        return ar.run(now=now or self.NOW, token="tok", lister=lambda token: items,
                      detail=detail or self._detail(), send=send or collect)

    def test_start_reminder_inside_window(self):
        self.assertEqual(self._run([self._item()]), 0)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("30 分钟后开始", self.sent[0])
        self.assertIn("活动中心", self.sent[0])
        self.assertIn("17:45", self.sent[0])

    def test_far_activity_sends_nothing_and_asks_no_detail(self):
        self.assertEqual(self._run([self._item(act_start="2026-11-24 21:00:00")]), 0)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.details, [], "没有临近场次时不该调详情接口")

    def test_same_reminder_is_sent_only_once(self):
        self._run([self._item()])
        self._run([self._item()])
        self.assertEqual(len(self.sent), 1, "同一场同一类只发一次")
        self.assertEqual(len(self.details), 1, "当天同一场只查一次详情")

    def test_failed_send_is_not_recorded(self):
        def broken(text):
            return False

        self._run([self._item()], send=broken)
        self.assertEqual(ar.load_state()["sent"], {}, "没发出去不能记")
        self._run([self._item()])
        self.assertEqual(len(self.sent), 1, "下一轮补发成功才记")

    def test_checkout_reminder_starts_with_checkout_window(self):
        now = datetime(2026, 11, 24, 20, 20)
        item = self._item(act_start="2026-11-24 18:00:00",
                          act_end="2026-11-24 21:00:00")
        detail = self._detail(sfxyqd=0, qdkssj="", qdjssj="", sfxyqt=1,
                              qtkssj="2026-11-24 20:15:00",
                              qtjssj="2026-11-24 20:40:00")
        self._run([item], now=now, detail=detail)
        self.assertEqual(len(self.sent), 1)
        self.assertIn("签退", self.sent[0])
        self.assertIn("20:15", self.sent[0])

    def test_started_activity_gets_no_start_reminder(self):
        now = datetime(2026, 11, 24, 18, 5)
        self._run([self._item()], now=now)
        self.assertEqual(self.sent, [], "错过了开头的开始提醒不补发")

class PersonalNoticeTests(unittest.TestCase):
    """个人变动私聊：只挑已报名 / 预报名的场次，说清旧值→新值、冲突与下架。"""

    NOW = datetime(2026, 11, 24, 12, 0)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="personal-notice-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patches = (("STATE", Path(self.tmp) / "notice.json"),
                   ("LOCK", Path(self.tmp) / "notice.lock"))
        for name, value in patches:
            patcher = mock.patch.object(pn, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, value in (("FILE", Path(self.tmp) / "watchlist.json"),
                            ("LOCK", Path(self.tmp) / "watchlist.lock")):
            patcher = mock.patch.object(wl, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sent = []

    def _item(self, **extra):
        item = {"id": "evt-1", "name": "讲座", "signed": False,
                "act_start": "2026-11-25 19:00:00", "act_end": "2026-11-25 21:00:00"}
        item.update(extra)
        return item

    def _event(self, **extra):
        event = {"id": "evt-1", "name": "讲座", "kind": "changed", "status": "open",
                 "act_start": "2026-11-25 19:00:00", "act_end": "2026-11-25 21:00:00",
                 "changed_fields": ["act_start"],
                 "previous": {"act_start": "2026-11-25 18:00:00"}}
        event.update(extra)
        return event

    def _send(self, items, events, gone=(), send=None):
        def collect(text):
            self.sent.append(text)
            return True

        return pn.announce(items, events, list(gone), self.NOW, send=send or collect)

    def test_signed_change_is_sent_with_old_and_new(self):
        self.assertTrue(self._send([self._item(signed=True)], [self._event()]))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("已报名", self.sent[0])
        self.assertIn("2026-11-25 18:00 → 2026-11-25 19:00", self.sent[0])

    def test_queued_time_published_says_previous_unknown(self):
        wl.save([{"id": "evt-2", "name": "晚会", "open_at": "2026-11-24 09:00:00"}])
        event = self._event(id="evt-2", name="晚会", act_start="2026-11-26 19:00:00",
                            act_end="2026-11-26 21:00:00",
                            previous={"act_start": ""})
        self._send([self._item(id="evt-2", name="晚会")], [event])
        self.assertIn("预报名", self.sent[0])
        self.assertIn("未公布 → 2026-11-26 19:00", self.sent[0])

    def test_reschedule_conflict_is_warned(self):
        other = self._item(id="evt-9", name="会议", signed=True,
                           act_start="2026-11-25 19:30:00",
                           act_end="2026-11-25 20:30:00")
        items = [self._item(signed=True), other]
        self._send(items, [self._event()])
        self.assertIn("冲突", self.sent[0])
        self.assertIn("会议", self.sent[0])

    def test_unrelated_change_stays_silent(self):
        self.assertTrue(self._send([self._item()], [self._event()]))
        self.assertEqual(self.sent, [])

    def test_missing_activity_is_reported_without_touching_list(self):
        wl.save([{"id": "evt-2", "name": "晚会", "open_at": "2026-11-24 09:00:00"}])
        self._send([self._item(signed=True)], [])
        self._send([], [], gone=[{"id": "evt-1", "name": "讲座"}])
        self.assertIn("下架", self.sent[0])
        self.assertEqual([e["id"] for e in wl.load()], ["evt-2"])

    def test_failed_send_is_retried_and_not_duplicated(self):
        def broken(text):
            return None

        self.assertFalse(self._send([self._item(signed=True)], [self._event()], send=broken))
        self.assertEqual(len(pn.load_state()["pending"]), 1)
        self.assertEqual(self.sent, [])
        self.assertTrue(self._send([self._item(signed=True)], []))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(pn.load_state()["pending"], [])

    def test_field_labels_match_public_events(self):
        self.assertEqual(pn.FIELD_LABELS, aw.FIELD_LABELS, "两处字段说法必须一致")

if __name__ == "__main__":
    unittest.main(verbosity=2)
