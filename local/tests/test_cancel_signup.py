#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取消报名（计划 20261107-conflict-cancel，X1–X4）的后端回归。

三层：
- domain.cancel_rules：学校原话清洗、worker 输出行归一化（纯函数）；
- grab.run_cancel / grab.cmd_cancel：worker 子命令，网络边界（_post / _get / probe_token）
  全部替换，绝不连学校，更不会调真实的取消接口；
- app.Api.cancel_signup：列表缓存门、互斥、结果回写，worker 进程（_run）替换成内存替身。

@author Author
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import threading
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
from domain import cancel_rules  # noqa: E402
from domain import phone_rules  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from fixtures.business_clock import FakeBusinessClock  # noqa: E402

NOW = 1793100000.0     # 假「北京时间」锚点（与真实系统日期无关）
SCHOOL_REPLY_TEXT = "活动已开始，不能取消"


def _t(offset):
    return grab.school_time_text(NOW + offset)


# ------------------------------------------------------------------ 纯规则
class CancelRulesTests(unittest.TestCase):
    def test_sanitize_strips_control_chars_and_truncates_to_80(self):
        dirty = "\u200b第一行\r\n第二行\t\x00尾\u202e巴"
        self.assertEqual(cancel_rules.sanitize_message(dirty), "第一行第二行尾巴")
        long_text = "字" * 200
        self.assertEqual(len(cancel_rules.sanitize_message(long_text)), 80)
        self.assertEqual(cancel_rules.sanitize_message(None), "")
        self.assertEqual(cancel_rules.sanitize_message("   "), "")
        self.assertEqual(cancel_rules.sanitize_message("  中间 空格  "), "中间 空格")

    def test_normalize_takes_the_last_json_line_only(self):
        out = "[i] 一行日志\n{\"ok\": false, \"kind\": \"unknown\"}\n{\"ok\": true, \"kind\": \"cancelled\"}\n"
        self.assertEqual(cancel_rules.normalize_worker_result(out),
                         {"ok": True, "kind": "cancelled"})

    def test_normalize_unreadable_output_is_unknown_never_success(self):
        for out in ("", None, "   \n", "not json", "[1, 2]", "{\"kind\": \"nope\"}",
                    "{\"ok\": true}", "{\"ok\": true, \"kind\": \"cancel\"}"):
            with self.subTest(out=out):
                self.assertEqual(cancel_rules.normalize_worker_result(out),
                                 {"ok": False, "kind": "unknown"})

    def test_ok_is_derived_from_kind_not_trusted(self):
        got = cancel_rules.normalize_worker_result('{"ok": true, "kind": "refused"}')
        self.assertIs(got["ok"], False)
        got = cancel_rules.normalize_worker_result('{"ok": false, "kind": "cancelled"}')
        self.assertIs(got["ok"], True)

    def test_precheck_reason_must_look_like_a_code(self):
        good = cancel_rules.normalize_worker_result(
            '{"ok": false, "kind": "precheck_failed", "reason": "window_closed"}')
        self.assertEqual(good, {"ok": False, "kind": "precheck_failed",
                                "reason": "window_closed"})
        for reason in ("学校原话", "Bad Reason", "", None, 7, "x" * 40):
            with self.subTest(reason=reason):
                bad = cancel_rules.normalize_worker_result(json.dumps(
                    {"ok": False, "kind": "precheck_failed", "reason": reason}))
                self.assertEqual(bad["reason"], "unknown_state")

    def test_message_only_on_refused_and_sanitized_again(self):
        got = cancel_rules.normalize_worker_result(json.dumps(
            {"ok": False, "kind": "refused", "message": "a\nb" + "字" * 100},
            ensure_ascii=False))
        self.assertEqual(got["kind"], "refused")
        self.assertEqual(len(got["message"]), 80)
        self.assertNotIn("\n", got["message"])
        for kind in ("cancelled", "unknown", "precheck_failed"):
            got = cancel_rules.normalize_worker_result(json.dumps(
                {"ok": False, "kind": kind, "message": "不该带"}, ensure_ascii=False))
            self.assertNotIn("message", got, kind)


# --------------------------------------------------------------- worker 子命令
_UNSET = object()


class FakeSchool:
    """学校接口替身：getJoinInfo 按次序给回包，getInfo / cancel 各一个回包，全程记账。"""

    def __init__(self, joins, detail=None, cancel=_UNSET):
        self.joins = list(joins)
        self.detail = detail if detail is not None else self.detail_reply()
        self.cancel = {"code": 1, "message": "操作成功！"} if cancel is _UNSET else cancel
        self.calls = []          # [(method, path)]
        self.join_timeouts = []
        self.on_cancel = None

    @staticmethod
    def detail_reply(qxbm=1, start=-86400, end=3600, **extra):
        data = {"qxbm": qxbm, "bmkssj": _t(start), "bmjssj": _t(end)}
        data.update(extra)
        return {"code": 1, "message": "操作成功！", "data": data}

    @staticmethod
    def joined():
        return {"code": 1, "message": "操作成功！", "data": {"sfbm": 1, "sfcx": 0}}

    @staticmethod
    def not_joined():
        return {"code": 1, "message": "操作成功！", "data": None}

    @staticmethod
    def failed():
        return {"code": -1, "message": "URLError"}

    def post(self, path, payload=None, tok=None, timeout=None, budget=None):
        self.calls.append(("POST", path))
        if path.startswith("/rjyHdCyr/getJoinInfo/"):
            # is_joined 只把预算折成 timeout 传下来：带预算时它是个数，不带是 None
            self.join_timeouts.append(timeout)
            return self.joins.pop(0) if len(self.joins) > 1 else self.joins[0]
        raise AssertionError("测试里不该出现的 POST：%s" % path)

    def get(self, path, tok=None, timeout=None):
        self.calls.append(("GET", path))
        if path.startswith("/rjyHd/getInfo/"):
            return self.detail
        if path.startswith("/rjyHdCyr/cancel/"):
            if self.on_cancel is not None:
                self.on_cancel()
            return self.cancel
        raise AssertionError("测试里不该出现的 GET：%s" % path)

    def cancel_calls(self):
        return [c for c in self.calls if c[1].startswith("/rjyHdCyr/cancel/")]


class _CancelHarness(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.clock = FakeBusinessClock(epoch=NOW)
        self._saved_clock = dict(grab._CLOCK)
        self._saved_now = time_contract._BUSINESS_NOW
        grab.configure_business_clock(self.clock)
        self.addCleanup(self._restore)

    def _restore(self):
        grab._CLOCK.update(self._saved_clock)
        time_contract.configure_time_source(self._saved_now)

    def run_cancel(self, school, act_id="act1", *, probe=("valid", "ok"), configured=True,
                   progress=None):
        with mock.patch.object(grab, "_post", school.post), \
                mock.patch.object(grab, "_get", school.get), \
                mock.patch.object(grab, "probe_token", lambda budget=None: probe), \
                mock.patch.object(grab, "SITE_CONFIGURED", configured), \
                mock.patch.object(grab, "log", self.logs.append):
            return grab.run_cancel(act_id, progress)

    def assertRefused(self, result, reason, school):
        self.assertEqual(result, {"ok": False, "kind": "precheck_failed", "reason": reason})
        self.assertEqual(school.cancel_calls(), [], "前置条件不满足：不得调取消接口")


class RunCancelPrecheckTests(_CancelHarness):
    def test_not_signed_does_not_call_cancel(self):
        school = FakeSchool([FakeSchool.not_joined()])
        self.assertRefused(self.run_cancel(school), "not_signed", school)

    def test_cancelled_registration_counts_as_not_signed(self):
        # sfcx=1（已撤销）按 _join_state 是未报名：不能再「取消」一次
        school = FakeSchool([{"code": 1, "data": {"sfbm": 1, "sfcx": 1}}])
        self.assertRefused(self.run_cancel(school), "not_signed", school)

    def test_join_state_unknown_does_not_call_cancel(self):
        school = FakeSchool([FakeSchool.failed()])
        self.assertRefused(self.run_cancel(school), "unknown_state", school)

    def test_detail_not_available_does_not_call_cancel(self):
        school = FakeSchool([FakeSchool.joined()], detail=FakeSchool.failed())
        self.assertRefused(self.run_cancel(school), "unknown_state", school)

    def test_cancel_not_allowed_does_not_call_cancel(self):
        for qxbm in (0, "0", None, "abc", 2):
            with self.subTest(qxbm=qxbm):
                school = FakeSchool([FakeSchool.joined()],
                                    detail=FakeSchool.detail_reply(qxbm=qxbm))
                self.assertRefused(self.run_cancel(school), "not_allowed", school)

    def test_missing_qxbm_key_is_not_allowed(self):
        reply = FakeSchool.detail_reply()
        del reply["data"]["qxbm"]
        school = FakeSchool([FakeSchool.joined()], detail=reply)
        self.assertRefused(self.run_cancel(school), "not_allowed", school)

    def test_outside_sign_window_does_not_call_cancel(self):
        for start, end in ((600, 7200), (-86400, -1)):   # 还没开始 / 已经截止
            with self.subTest(start=start, end=end):
                school = FakeSchool([FakeSchool.joined()],
                                    detail=FakeSchool.detail_reply(start=start, end=end))
                self.assertRefused(self.run_cancel(school), "window_closed", school)

    def test_window_bounds_are_inclusive(self):
        for start, end in ((0, 3600), (-3600, 0)):
            with self.subTest(start=start, end=end):
                school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()],
                                    detail=FakeSchool.detail_reply(start=start, end=end))
                got = self.run_cancel(school)
                self.assertEqual(got["kind"], "cancelled")
                self.assertEqual(len(school.cancel_calls()), 1)

    def test_missing_window_times_do_not_call_cancel(self):
        for fields in ({"bmkssj": ""}, {"bmjssj": None}, {"bmjssj": "待定"}):
            with self.subTest(fields=fields):
                reply = FakeSchool.detail_reply()
                reply["data"].update(fields)
                school = FakeSchool([FakeSchool.joined()], detail=reply)
                self.assertRefused(self.run_cancel(school), "unknown_state", school)

    def test_clock_unavailable_does_not_call_cancel(self):
        grab._CLOCK.update({"now": None, "bounds": None, "meta": None})
        school = FakeSchool([FakeSchool.joined()])
        self.assertRefused(self.run_cancel(school), "clock_unavailable", school)
        self.assertEqual(school.calls, [], "时钟不可用：连查询都不发")

    def test_clock_lost_midway_does_not_call_cancel(self):
        # 查询期间校时失效（业务读数抛 ClockUnavailable）：不能拿旧时间去判窗口
        school = FakeSchool([FakeSchool.joined()])
        self.clock.expire()
        self.assertRefused(self.run_cancel(school), "clock_unavailable", school)

    def test_login_expired_does_not_call_cancel(self):
        for state in ("expired", "none"):
            with self.subTest(state=state):
                school = FakeSchool([FakeSchool.joined()])
                self.assertRefused(self.run_cancel(school, probe=(state, "x")),
                                   "login_expired", school)
                self.assertEqual(school.calls, [])

    def test_network_trouble_is_not_reported_as_expired_login(self):
        school = FakeSchool([FakeSchool.joined()])
        self.assertRefused(self.run_cancel(school, probe=("unknown", "接口异常")),
                           "unknown_state", school)

    def test_unconfigured_site_refuses_before_any_request(self):
        school = FakeSchool([FakeSchool.joined()])
        got = self.run_cancel(school, configured=False)
        self.assertRefused(got, "site_unconfigured", school)
        self.assertEqual(school.calls, [])

    def test_empty_id_is_refused(self):
        school = FakeSchool([FakeSchool.joined()])
        self.assertRefused(self.run_cancel(school, act_id="  "), "not_in_list", school)
        self.assertEqual(school.calls, [])

    def test_state_queries_use_a_budget_so_none_stays_three_state(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        self.run_cancel(school)
        self.assertEqual(len(school.join_timeouts), 2)
        for timeout in school.join_timeouts:
            self.assertIsNotNone(timeout, "不带 budget 查不到会回 False，被当成「已取消」")


class RunCancelOutcomeTests(_CancelHarness):
    def test_recheck_not_joined_is_cancelled(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        got = self.run_cancel(school)
        self.assertEqual(got, {"ok": True, "kind": "cancelled"})
        self.assertEqual(len(school.cancel_calls()), 1, "取消接口只调一次")
        self.assertEqual(
            [(m, p.rsplit("/", 1)[0]) for m, p in school.calls],
            [("POST", "/rjyHdCyr/getJoinInfo"), ("GET", "/rjyHd/getInfo"),
             ("GET", "/rjyHdCyr/cancel"), ("POST", "/rjyHdCyr/getJoinInfo")],
            "顺序：查报名 → 查详情 → 取消（一次）→ 复查报名")

    def test_recheck_still_joined_is_refused_with_truncated_message(self):
        # 回包的 code 学校没给样例：不管它长得像成功（1）还是失败（500），
        # 复查仍是已报名就是 refused，原话清洗后截到 80 字
        for code in (500, 1):
            with self.subTest(reply_code=code):
                reply = {"code": code,
                         "message": "\u200b" + "活动已开始\n，不能取消" + "。" * 200}
                school = FakeSchool([FakeSchool.joined(), FakeSchool.joined()], cancel=reply)
                got = self.run_cancel(school)
                self.assertEqual(got["kind"], "refused")
                self.assertIs(got["ok"], False)
                self.assertLessEqual(len(got["message"]), 80)
                self.assertTrue(got["message"].startswith("活动已开始，不能取消"))
                self.assertFalse(any(ch in got["message"] for ch in "\n\r\t\u200b"))
                self.assertEqual(len(school.cancel_calls()), 1)

    def test_success_looking_reply_is_not_trusted_when_recheck_says_joined(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.joined()],
                            cancel={"code": 1, "message": "取消成功"})
        self.assertEqual(self.run_cancel(school)["kind"], "refused")

    def test_failure_looking_reply_is_not_trusted_when_recheck_says_not_joined(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()],
                            cancel={"code": 500, "message": "系统繁忙"})
        self.assertEqual(self.run_cancel(school)["kind"], "cancelled")

    def test_refused_without_usable_message_has_no_message_key(self):
        for reply in ({"code": 500}, {"code": 500, "message": "\n\t"}, None, "boom"):
            with self.subTest(reply=reply):
                school = FakeSchool([FakeSchool.joined(), FakeSchool.joined()], cancel=reply)
                got = self.run_cancel(school)
                self.assertEqual(got, {"ok": False, "kind": "refused"})

    def test_transport_failure_reply_is_not_shown_as_school_words(self):
        # _get 传输失败回 {"code": -1, "message": "URLError"}：复查仍是已报名时是 refused，
        # 但异常类名不能冒充学校原话（B8）
        for reply in ({"code": -1, "message": "URLError"},
                      {"code": -1, "message": "HTTPError"}):
            with self.subTest(reply=reply):
                school = FakeSchool([FakeSchool.joined(), FakeSchool.joined()], cancel=reply)
                got = self.run_cancel(school)
                self.assertEqual(got, {"ok": False, "kind": "refused"})
                self.assertNotIn("message", got)

    def test_recheck_unavailable_is_unknown(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.failed()])
        self.assertEqual(self.run_cancel(school), {"ok": False, "kind": "unknown"})
        self.assertEqual(len(school.cancel_calls()), 1)

    def test_recheck_gets_a_fresh_budget_after_a_slow_cancel(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        school.on_cancel = lambda: self.clock.advance(grab.CANCEL_PRECHECK_BUDGET_S + 5)
        self.assertEqual(self.run_cancel(school)["kind"], "cancelled")

    def test_clock_lost_after_cancel_is_unknown(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        school.on_cancel = self.clock.expire
        self.assertEqual(self.run_cancel(school), {"ok": False, "kind": "unknown"})

    def test_activity_id_is_url_escaped(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        self.run_cancel(school, act_id="a/b c?x=1#y")
        self.assertEqual(school.cancel_calls(), [("GET", "/rjyHdCyr/cancel/a%2Fb%20c%3Fx%3D1%23y")])

    def test_progress_marks_sent_only_when_cancel_is_called(self):
        progress = {"sent": False}
        school = FakeSchool([FakeSchool.not_joined()])
        self.run_cancel(school, progress=progress)
        self.assertFalse(progress["sent"])
        progress = {"sent": False}
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        self.run_cancel(school, progress=progress)
        self.assertTrue(progress["sent"])

    def test_school_message_never_reaches_the_log(self):
        secret = "学校原话-不该进日志"
        school = FakeSchool([FakeSchool.joined(), FakeSchool.joined()],
                            cancel={"code": 500, "message": secret})
        got = self.run_cancel(school)
        self.assertEqual(got["message"], secret)
        self.assertTrue(self.logs, "worker 应写几行不含原话的诊断")
        self.assertFalse([line for line in self.logs if secret in line])


class CmdCancelTests(_CancelHarness):
    def run_cmd(self, school, act_id="act1", *, log_to_stdout=True):
        out, err = io.StringIO(), io.StringIO()

        def noisy_log(msg):
            self.logs.append(msg)
            if log_to_stdout:
                print("LOGGER:%s" % msg)       # 真实 log() 会往 stdout 打印

        with mock.patch.object(grab, "_post", school.post), \
                mock.patch.object(grab, "_get", school.get), \
                mock.patch.object(grab, "probe_token", lambda budget=None: ("valid", "ok")), \
                mock.patch.object(grab, "SITE_CONFIGURED", True), \
                mock.patch.object(grab, "log", noisy_log), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = grab.cmd_cancel(SimpleNamespace(id=act_id, json=True))
        return code, out.getvalue(), err.getvalue()

    def test_stdout_is_exactly_one_json_line_and_logs_go_to_stderr(self):
        school = FakeSchool([FakeSchool.joined(), FakeSchool.not_joined()])
        code, out, err = self.run_cmd(school)
        self.assertEqual(code, 0)
        lines = [line for line in out.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "stdout 只能有一行：%r" % out)
        self.assertEqual(json.loads(lines[0]), {"ok": True, "kind": "cancelled"})
        self.assertIn("LOGGER:", err, "辅助日志应改道到 stderr")

    def test_non_cancelled_results_exit_nonzero_with_one_json_line(self):
        school = FakeSchool([FakeSchool.not_joined()])
        code, out, _err = self.run_cmd(school)
        self.assertNotEqual(code, 0)
        self.assertEqual(json.loads(out.strip()),
                         {"ok": False, "kind": "precheck_failed", "reason": "not_signed"})

    def test_unexpected_exception_before_sending_is_a_precheck_failure(self):
        school = FakeSchool([FakeSchool.joined()])
        with mock.patch.object(grab, "_cancel_facts", side_effect=RuntimeError("boom")):
            code, out, _ = self.run_cmd(school)
        self.assertEqual(json.loads(out.strip()),
                         {"ok": False, "kind": "precheck_failed", "reason": "unknown_state"})
        self.assertEqual(school.cancel_calls(), [])

    def test_unexpected_exception_after_sending_is_unknown(self):
        school = FakeSchool([FakeSchool.joined()])
        with mock.patch.object(grab, "_cancel_joined", side_effect=[True, RuntimeError("boom")]):
            code, out, _ = self.run_cmd(school)
        self.assertEqual(json.loads(out.strip()), {"ok": False, "kind": "unknown"})
        self.assertEqual(len(school.cancel_calls()), 1)

    def test_main_registers_the_cancel_subcommand(self):
        import inspect
        source = inspect.getsource(grab.main)
        self.assertIn('sub.add_parser("cancel"', source)
        self.assertIn('"--id", required=True', source)
        self.assertIn("cmd_cancel", source)


# ------------------------------------------------------------------- Api 层
try:
    import app as local_app
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时如实跳过并报告
    local_app = None
    _IMPORT_ERROR = exc


class _FakePlan:
    def __init__(self, status="running"):
        self.status = status

    def published_status(self):
        return self.status


class _FakeProc:
    def __init__(self, alive=True):
        self.alive = alive

    def poll(self):
        return None if self.alive else 0


@unittest.skipIf(local_app is None, "无法导入 local/app.py：%s" % (_IMPORT_ERROR,))
class ApiCancelSignupTests(unittest.TestCase):
    ACTIVITY = {"id": "act-signed", "name": "宿舍查寝", "signed": True,
                "sign_start": _t(-86400), "sign_end": _t(3600),
                "act_start": _t(86400), "act_end": _t(2 * 86400), "cancel_allowed": True}
    OTHER = {"id": "act-open", "name": "模拟面试", "signed": False,
             "sign_start": _t(-3600), "sign_end": _t(3600)}

    def setUp(self):
        self.api = stop_auto_relogin_on_cleanup(self, local_app.Api())
        self.events = []
        self.api._emit = lambda kind, payload: self.events.append((kind, payload))
        self.api._activities = {"act-signed": dict(self.ACTIVITY), "act-open": dict(self.OTHER)}
        self.run_calls = []
        self.worker_reply = {"code": 0, "out": "", "stderr": "",
                             "stdout": '{"ok": true, "kind": "cancelled"}\n'}
        patches = [
            mock.patch.object(local_app, "DEMO", False),
            mock.patch.object(local_app, "worker_problem", lambda: ""),
            mock.patch.object(local_app, "worker_command", lambda *a: ["W"] + list(a)),
            mock.patch.object(self.api, "_terms_gate", lambda request_id="": None),
            mock.patch.object(self.api, "_run", self._fake_run),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _fake_run(self, args, timeout):
        self.run_calls.append((list(args), timeout))
        reply = self.worker_reply
        if isinstance(reply, BaseException):
            raise reply
        if callable(reply):
            return reply()
        return dict(reply)

    def logs(self):
        return [payload for kind, payload in self.events if kind == "log"]

    # ---- 列表缓存门
    def test_ids_outside_the_list_cache_are_refused_without_a_worker(self):
        for bad in ("nope", "", None, 5, {"id": "act-signed"}, ["act-signed"], "act-signed ' or 1"):
            with self.subTest(bad=bad):
                got = self.api.cancel_signup(bad)
                self.assertEqual(got, {"ok": False, "kind": "precheck_failed",
                                       "reason": "not_in_list"})
        self.assertEqual(self.run_calls, [])

    def test_unsigned_activity_is_refused_without_a_worker(self):
        got = self.api.cancel_signup("act-open")
        self.assertEqual(got, {"ok": False, "kind": "precheck_failed", "reason": "not_in_list"})
        self.assertEqual(self.run_calls, [])

    def test_terms_gate_blocks_before_anything(self):
        gate = {"ok": False, "error": "terms_required", "text": "还没确认条款"}
        with mock.patch.object(self.api, "_terms_gate", lambda request_id="": dict(gate)):
            got = self.api.cancel_signup("act-signed")
        self.assertFalse(got["ok"])
        self.assertEqual(got["kind"], "precheck_failed")
        self.assertEqual(got["reason"], "terms_required")
        self.assertEqual(self.run_calls, [])

    def test_worker_problem_is_a_precheck_failure(self):
        with mock.patch.object(local_app, "worker_problem", lambda: "worker_missing"):
            got = self.api.cancel_signup("act-signed")
        self.assertEqual(got, {"ok": False, "kind": "precheck_failed",
                               "reason": "worker_unavailable"})
        self.assertEqual(self.run_calls, [])

    # ---- 互斥（X3）
    def test_busy_when_plan_running_refreshing_or_other_work(self):
        cases = [
            ("plan_running", lambda: setattr(self.api, "_plan", _FakePlan("running"))),
            ("plan_running", lambda: setattr(self.api, "_plan", _FakePlan("ready"))),
            ("plan_running", lambda: self.api._plan_procs.update({"t": _FakeProc()})),
            ("refreshing", lambda: setattr(self.api, "_listing", True)),
            ("refreshing", lambda: setattr(self.api, "_checking", True)),
            ("task_running", lambda: setattr(self.api, "_proc", _FakeProc())),
            ("cancelling", lambda: setattr(self.api, "_cancelling", True)),
        ]
        for reason, arm in cases:
            with self.subTest(reason=reason):
                api = stop_auto_relogin_on_cleanup(self, local_app.Api())
                api._emit = lambda kind, payload: None
                api._activities = {"act-signed": dict(self.ACTIVITY)}
                with mock.patch.object(api, "_terms_gate", lambda request_id="": None), \
                        mock.patch.object(api, "_run", self._fake_run):
                    self.api = api
                    arm()
                    got = api.cancel_signup("act-signed")
                self.assertEqual((got["ok"], got["kind"], got["reason"]), (False, "busy", reason))
                self.assertTrue(got["message"])
        self.assertEqual(self.run_calls, [], "忙碌时不起 worker")

    def test_finished_plan_does_not_block(self):
        self.api._plan = _FakePlan("completed")
        self.api._plan_procs["t"] = _FakeProc(alive=False)
        self.assertTrue(self.api.cancel_signup("act-signed")["ok"])

    def test_cancelling_blocks_refresh_login_and_start_plan(self):
        seen = {}

        def during():
            with self.api._lock:
                seen["busy"] = self.api._is_busy_locked()
            seen["list"] = self.api.list_activities("r-list")
            seen["check"] = self.api.check("r-check")
            seen["login"] = self.api.login()
            seen["second_cancel"] = self.api.cancel_signup("act-signed")
            with mock.patch.object(self.api, "_clock_ready", lambda: True), \
                    mock.patch.object(self.api, "_clock_now", lambda: NOW):
                seen["start"] = self.api.start_plan([{"id": "act-open"}])
            return {"code": 0, "out": "", "stderr": "",
                    "stdout": '{"ok": true, "kind": "cancelled"}'}

        self.worker_reply = during
        self.assertTrue(self.api.cancel_signup("act-signed")["ok"])
        self.assertTrue(seen["busy"])
        self.assertFalse(seen["list"]["ok"])
        self.assertIn("取消", seen["list"]["text"])
        self.assertFalse(seen["check"]["ok"])
        self.assertFalse(seen["login"]["ok"])
        self.assertEqual(seen["second_cancel"]["reason"], "cancelling")
        self.assertFalse(seen["start"]["ok"])
        self.assertIn("在运行", seen["start"]["text"])
        # 取消结束后忙碌标记放开
        self.assertFalse(self.api._cancelling)
        self.assertFalse(self.api._is_busy())

    def test_busy_flag_is_released_when_the_worker_blows_up(self):
        self.worker_reply = RuntimeError("boom")
        self.assertEqual(self.api.cancel_signup("act-signed"), {"ok": False, "kind": "unknown"})
        self.assertFalse(self.api._cancelling)
        self.assertFalse(self.api._is_busy())

    # ---- 起 worker
    def test_worker_is_started_once_with_the_exact_command(self):
        self.api.cancel_signup("act-signed")
        self.assertEqual(len(self.run_calls), 1)
        args, timeout = self.run_calls[0]
        self.assertEqual(args, ["W", "cancel", "--id", "act-signed", "--json"])
        self.assertEqual(timeout, local_app.Api.CANCEL_WORKER_TIMEOUT_S)

    # ---- 结果
    def test_cancelled_marks_cache_unsigned_and_emits_activities(self):
        got = self.api.cancel_signup("act-signed")
        self.assertEqual(got, {"ok": True, "kind": "cancelled"})
        self.assertIs(self.api._activities["act-signed"]["signed"], False)
        self.assertEqual(self.api._activities["act-signed"]["signed_source"], "cancelled")
        self.assertIs(self.api._activities["act-open"]["signed"], False)
        kinds = [kind for kind, _ in self.events]
        self.assertIn("activities", kinds)
        payload = dict(self.events)["activities"]
        self.assertIs(payload["ok"], True)
        self.assertEqual(payload["request_id"], "", "不占用任何一轮刷新的 request_id")
        by_id = {it["id"]: it for it in payload["items"]}
        self.assertIs(by_id["act-signed"]["signed"], False)
        self.assertEqual(set(by_id), {"act-signed", "act-open"})
        self.assertGreater(kinds.index("activities"), kinds.index("log"),
                           "先记一行运行记录，再让界面刷新")

    def test_cancelled_does_not_pollute_the_last_list_snapshot(self):
        before = {"request_id": "r-old", "payload": {"ok": True, "items": []}}
        self.api._list_last = before
        self.api.cancel_signup("act-signed")
        self.assertIs(self.api._list_last, before)

    def test_refused_and_unknown_leave_the_cache_alone_and_emit_no_refresh(self):
        replies = {
            "refused": '{"ok": false, "kind": "refused", "message": "不能取消"}',
            "unknown": '{"ok": false, "kind": "unknown"}',
            "precheck_failed": '{"ok": false, "kind": "precheck_failed", "reason": "window_closed"}',
        }
        for kind, line in replies.items():
            with self.subTest(kind=kind):
                self.events.clear()
                self.worker_reply = {"code": 2, "out": "", "stderr": "", "stdout": line}
                got = self.api.cancel_signup("act-signed")
                self.assertEqual(got["kind"], kind)
                self.assertIs(got["ok"], False)
                self.assertIs(self.api._activities["act-signed"]["signed"], True)
                self.assertNotIn("activities", [k for k, _ in self.events])

    def test_precheck_reason_passes_through(self):
        self.worker_reply = {"code": 2, "out": "", "stderr": "", "stdout":
                             '{"ok": false, "kind": "precheck_failed", "reason": "not_allowed"}'}
        self.assertEqual(self.api.cancel_signup("act-signed"),
                         {"ok": False, "kind": "precheck_failed", "reason": "not_allowed"})

    def test_unreadable_or_timed_out_worker_is_unknown(self):
        replies = [
            {"code": -1, "out": "[X] 执行超时（90 秒）", "stdout": "", "stderr": ""},   # 超时
            {"code": 0, "out": "", "stdout": "", "stderr": ""},
            {"code": 0, "out": "", "stdout": "Traceback...\nboom", "stderr": ""},
            {"code": 0, "out": "", "stdout": '{"ok": true}', "stderr": ""},
        ]
        for reply in replies:
            with self.subTest(reply=reply):
                self.worker_reply = reply
                got = self.api.cancel_signup("act-signed")
                self.assertEqual(got, {"ok": False, "kind": "unknown"})
                self.assertIs(self.api._activities["act-signed"]["signed"], True)

    def test_spawn_failure_is_a_precheck_failure_and_closing_is_busy(self):
        self.worker_reply = FileNotFoundError("grab.py")
        self.assertEqual(self.api.cancel_signup("act-signed"),
                         {"ok": False, "kind": "precheck_failed", "reason": "worker_unavailable"})
        self.worker_reply = local_app._ClosingError("closing")
        got = self.api.cancel_signup("act-signed")
        self.assertEqual((got["kind"], got["reason"]), ("busy", "closing"))

    def test_run_log_records_kind_and_reason_but_never_the_school_message(self):
        secret = "学校原话-不该进运行记录"
        self.worker_reply = {"code": 2, "out": "", "stderr": "", "stdout": json.dumps(
            {"ok": False, "kind": "refused", "message": secret}, ensure_ascii=False)}
        got = self.api.cancel_signup("act-signed")
        self.assertEqual(got["message"], secret, "原话只回给界面")
        logs = self.logs()
        self.assertEqual(len(logs), 1)
        self.assertIn("refused", logs[0])
        self.assertNotIn(secret, json.dumps(self.events, ensure_ascii=False))
        self.worker_reply = {"code": 2, "out": "", "stderr": "", "stdout":
                             '{"ok": false, "kind": "precheck_failed", "reason": "window_closed"}'}
        self.api.cancel_signup("act-signed")
        self.assertIn("window_closed", self.logs()[-1])

    # ---- 演示模式
    def test_demo_returns_a_fixed_result_without_a_worker(self):
        from domain import demo_data
        rows = demo_data.demo_items(NOW, grab.school_time_text)
        self.api._activities = {row["id"]: row for row in rows}
        with mock.patch.object(local_app, "DEMO", True), \
                mock.patch.object(local_app, "worker_problem", side_effect=AssertionError("demo 不查组件")):
            got = self.api.cancel_signup("demo-dorm")
        self.assertEqual(got, {"ok": True, "kind": "cancelled", "demo": True})
        self.assertEqual(self.run_calls, [])
        self.assertIs(self.api._activities["demo-dorm"]["signed"], False)
        self.assertIn("activities", [kind for kind, _ in self.events])

    def test_demo_still_rejects_ids_outside_the_cache(self):
        with mock.patch.object(local_app, "DEMO", True):
            got = self.api.cancel_signup("demo-not-there")
        self.assertEqual(got["reason"], "not_in_list")

    # ---- X1：手机不做取消
    def test_phone_whitelist_does_not_contain_cancel_signup(self):
        self.assertNotIn("cancel_signup", phone_rules.ACTION_PARAMS)
        self.assertEqual(phone_rules.normalize_action("cancel_signup", {"activity_id": "a"}),
                         (None, "action_not_allowed"))
        self.assertEqual(phone_rules.normalize_action("cancel_signup", {}),
                         (None, "action_not_allowed"))

    def test_phone_module_source_never_names_cancel_signup(self):
        from pathlib import Path
        for name in ("domain/phone_rules.py", "application/phone_service.py",
                     "infrastructure/phone_http.py"):
            text = (Path(LOCAL) / name).read_text(encoding="utf-8")
            self.assertNotIn("cancel_signup", text, name)


if __name__ == "__main__":
    unittest.main()
