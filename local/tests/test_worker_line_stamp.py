#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""worker 输出行带北京时间前缀时，结构行必须仍能被识别（W6）。

约定：worker 的 log() 把每行写成「YYYY-MM-DD HH:MM:SS 消息」，
而 [retry]、「第 N 次提交」、[X] 这类结构行的识别点都要求行首就是标记。
去前缀的唯一入口是 domain.worker_lines.worker_message；这里用真实格式的
时间戳回放：时间戳由 time_contract.school_time_text 生成，另覆盖 grab.log
时钟不可用时的回退格式。全部离线：假 worker 脚本，不调用 grab.log
（它会写数据目录），不联网，不读真实配置。

@author Author
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from time_contract import configure_time_source, school_time_text  # noqa: E402
configure_time_source(time.time)

from domain import plan_rules  # noqa: E402
from domain.retry_window import ADAPTIVE_RETRY, DEFAULT_RETRY_SECONDS  # noqa: E402
from application import login_service  # noqa: E402
from signup_plan import TaskSpec  # noqa: E402
from fixtures.business_clock import TestWallClock  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402

# 固定的业务时刻（epoch 秒）：时间戳文本由真实换算函数生成，不手写字符串
FIXED_EPOCH = 1792000000.0
REAL_STAMP = school_time_text(FIXED_EPOCH)
# grab.log 在业务时钟不可用时的回退格式（本机墙钟，格式相同）
FALLBACK_STAMP = datetime.fromtimestamp(FIXED_EPOCH).strftime("%Y-%m-%d %H:%M:%S")


def stamped(message: str, stamp: str = REAL_STAMP) -> str:
    """和 grab.log 的 "%s %s" % (stamp, msg) 同一形状。"""
    return "%s %s" % (stamp, message)


# ---- 假 worker：每一行都加时间戳前缀后再 print，和真实 log() 的输出一致 ----
WORKER_FIXTURE = r'''
import os
import sys
import time

scenario = sys.argv[1] if len(sys.argv) > 1 else "silent"
stamp = os.environ.get("CAMPUS_TEST_STAMP", "")
deadline = os.environ.get("CAMPUS_TEST_DEADLINE", "0")


def log(msg):
    print((stamp + " " if stamp else "") + msg, flush=True)


if scenario == "attempts":
    log("[i] 第 1 次提交：已发起")
    log("[i] 第 3 次提交：直发已发起")
    sys.exit(2)
elif scenario == "extend_then_wait":
    log("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline)
    time.sleep(60)
elif scenario == "done_unconfirmed":
    log("[retry] kind=done attempts=2 stop_reason=unconfirmed retry_deadline=0 "
        "sign_end=0 last_reason=")
    sys.exit(2)
elif scenario == "reason":
    log("[X] 报名失败（尝试 2 次，最近原因 名额已满）")
    sys.exit(2)
else:
    raise SystemExit("unknown scenario: %s" % scenario)
'''


class WorkerMessageTests(unittest.TestCase):
    """worker_message：只认「YYYY-MM-DD HH:MM:SS 」这一种行首格式。"""

    def _fn(self):
        from domain.worker_lines import worker_message
        return worker_message

    def test_strips_real_school_time_stamp(self):
        fn = self._fn()
        self.assertEqual(fn(stamped("[retry] kind=done attempts=1")),
                         "[retry] kind=done attempts=1")

    def test_strips_grab_log_fallback_stamp(self):
        fn = self._fn()
        self.assertEqual(fn(stamped("[i] 第 2 次提交：已发起", FALLBACK_STAMP)),
                         "[i] 第 2 次提交：已发起")

    def test_unstamped_line_is_returned_as_is(self):
        fn = self._fn()
        for line in ("[retry] kind=done attempts=1", "[X] 没登录", "", "普通文字"):
            with self.subTest(line=line):
                self.assertEqual(fn(line), line)

    def test_digit_leading_messages_are_not_swallowed(self):
        """消息本身以数字开头、但不是完整时间戳 + 空格，不得被吞。"""
        fn = self._fn()
        for line in ("2026 年报名开始", "2026-11-13 活动明天开始",
                     "2026-11-13 10:00 开始", "10:00:00 开始",
                     "2026-11-13 10:00:00开始", "2026-11-13T10:00:00 开始",
                     " 2026-11-13 10:00:00 前面多一个空格"):
            with self.subTest(line=line):
                self.assertEqual(fn(line), line)

    def test_only_one_leading_stamp_is_removed(self):
        fn = self._fn()
        inner = stamped("消息里又带了一个时间戳")
        self.assertEqual(fn(stamped(inner)), inner)

    def test_stamp_with_empty_message_and_non_text_input(self):
        fn = self._fn()
        self.assertEqual(fn(REAL_STAMP + " "), "")
        self.assertEqual(fn(None), "")


class _PlanRunCase(unittest.TestCase):
    """api._run_plan_task + 假 worker：时间戳由测试进程真实生成后经环境变量交给它。"""

    GRACE = 0.4

    def setUp(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        self.app = local_app
        self.root = Path(tempfile.mkdtemp(prefix="campus-worker-stamp-"))
        self.addCleanup(shutil.rmtree, str(self.root), True)
        self._old_grace = local_app.SUPERVISE_GRACE_S
        local_app.SUPERVISE_GRACE_S = self.GRACE
        self.addCleanup(setattr, local_app, "SUPERVISE_GRACE_S", self._old_grace)
        self.script = self.root / "worker_fixture.py"
        self.script.write_text(WORKER_FIXTURE, encoding="utf-8")

    def _spec(self, retry_for, anchor_offset=1.0):
        return TaskSpec(task_id="t1", activity_id="a1", name="时间戳实验",
                        sign_start="2026-10-30 09:00:00", act_start="", act_end="",
                        sign_end="", retry_for_s=retry_for, max_attempts=0,
                        signup_mode="instant_signup", lead_s=0,
                        retry_started_at=time.time() - anchor_offset)

    def _run(self, scenario, *, stamp=REAL_STAMP, retry_for=120,
             anchor_offset=1.0, deadline=None):
        """返回 (result, elapsed, events, status_calls)。"""
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload: events.append((kind, payload))
        status_calls = []
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_TEST_STAMP"] = stamp
            if deadline is not None:
                env["CAMPUS_TEST_DEADLINE"] = "%.3f" % float(deadline)
            return env

        def fake_command(*args):
            return [sys.executable, str(self.script), scenario]

        started = time.time()
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            result = api._run_plan_task(
                self._spec(retry_for, anchor_offset), threading.Event(),
                lambda *a: status_calls.append(a))
        return result, time.time() - started, events, status_calls


class StampedAttemptLineTests(_PlanRunCase):
    """① 带时间戳的「[i] 第 N 次提交」行要计入提交次数。"""

    def test_stamped_attempt_lines_update_attempts(self):
        for name, stamp in (("真实格式", REAL_STAMP), ("回退格式", FALLBACK_STAMP)):
            with self.subTest(stamp=name):
                result, _, events, status_calls = self._run("attempts", stamp=stamp)
                seen = [a[1].get("attempts") for a in status_calls
                        if len(a) > 1 and isinstance(a[1], dict) and "attempts" in a[1]]
                self.assertIn(3, seen, "进度回调里应出现第 3 次提交")
                self.assertEqual(result.get("attempts"), 3)
                # 运行记录仍存带时间戳的原行
                logs = [p for k, p in events if k == "log"]
                self.assertTrue(any(stamped("[i] 第 3 次提交：直发已发起", stamp) in p
                                    for p in logs), logs)

    def test_unstamped_attempt_lines_still_count(self):
        result, _, _, _ = self._run("attempts", stamp="")
        self.assertEqual(result.get("attempts"), 3)


class StampedWindowExtensionTests(_PlanRunCase):
    """② 带时间戳的 [retry] kind=window_extended 要被接受并平移单调截止。"""

    def test_stamped_window_extended_moves_hard_stop(self):
        now = time.time()
        anchor_offset = DEFAULT_RETRY_SECONDS - 1.0       # 初始截止约 1 秒后
        candidate = now - anchor_offset + DEFAULT_RETRY_SECONDS + 4.0
        result, elapsed, _, _ = self._run(
            "extend_then_wait", retry_for=ADAPTIVE_RETRY,
            anchor_offset=anchor_offset, deadline=candidate)
        self.assertEqual(result["stop_reason"], "retry_duration")
        self.assertGreaterEqual(elapsed, 2.5,
                                "旧截止（约 %.1f 秒）不得杀树，带时间戳的扩窗要被接受"
                                % (0.5 + self.GRACE))


class StampedTerminalLineTests(_PlanRunCase):
    """③ 带时间戳的 [retry] kind=done 终态行要被结束分类读到 stop_reason。"""

    def test_stamped_done_line_gives_stop_reason(self):
        for name, stamp in (("真实格式", REAL_STAMP), ("回退格式", FALLBACK_STAMP)):
            with self.subTest(stamp=name):
                result, _, _, _ = self._run("done_unconfirmed", stamp=stamp)
                self.assertEqual(result["stop_reason"], "unconfirmed")
                self.assertEqual(result.get("attempts"), 2)

    def test_unstamped_done_line_still_gives_stop_reason(self):
        result, _, _, _ = self._run("done_unconfirmed", stamp="")
        self.assertEqual(result["stop_reason"], "unconfirmed")


class StampedFailureReasonTests(_PlanRunCase):
    """④ 带时间戳的 [X] 原因行要进入失败原因（plan_rules 与 login_service）。"""

    def test_plan_run_takes_reason_from_stamped_x_line(self):
        result, _, _, _ = self._run("reason")
        self.assertEqual(result["reason"], "报名失败（尝试 2 次，最近原因 名额已满）")

    def test_classify_task_stop_reads_stamped_x_line(self):
        spec = TaskSpec("t1", "a1", "测试活动", "2026-10-25 10:00:00",
                        "2026-10-25 12:00:00", "2026-10-25 13:00:00")
        tail = [stamped("[i] 第 1 次提交：已发起"),
                stamped("[X] 报名失败（尝试 1 次，最近原因 名额已满）")]
        result = plan_rules.classify_task_stop(
            spec, 2, tail, canceled=False, supervised_fired=False, stop={},
            attempts_seen=1, epoch_of=lambda text: 0.0)
        self.assertEqual(result["reason"], "报名失败（尝试 1 次，最近原因 名额已满）")

    def test_done_result_reads_stamped_x_line(self):
        for kind in ("grab", "login"):
            with self.subTest(kind=kind):
                ok, reason = login_service.done_result(
                    kind, 2, [stamped("[X] 登录失效（尝试 3 次）", FALLBACK_STAMP)])
                self.assertFalse(ok)
                self.assertEqual(reason, "登录失效（尝试 3 次）")


class StampedCheckReasonTests(unittest.TestCase):
    """⑤ check 输出里经 log() 写的 [X] 行带时间戳，check_reason_line 也要认得。"""

    def test_check_reason_line_reads_stamped_x_line(self):
        from domain import login_rules
        for name, stamp in (("真实格式", REAL_STAMP), ("回退格式", FALLBACK_STAMP)):
            with self.subTest(stamp=name):
                out = chr(10).join([
                    stamped('[clock] {"source": "http_date"}', stamp),
                    stamped("[X] 登录态没写成：5 秒内没拿到写锁（另一个进程正在写）", stamp),
                    "请重新登录",
                ])
                reason, last = login_rules.check_reason_line(out)
                self.assertEqual(reason, "[X] 登录态没写成：5 秒内没拿到写锁（另一个进程正在写）")
                self.assertEqual(last, "请重新登录")

    def test_check_reason_line_unstamped_still_works(self):
        from domain import login_rules
        reason, last = login_rules.check_reason_line(chr(10).join(["[X] 没登录", "请重新登录"]))
        self.assertEqual((reason, last), ("[X] 没登录", "请重新登录"))


if __name__ == "__main__":
    unittest.main()
