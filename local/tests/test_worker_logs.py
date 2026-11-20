#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_worker_logs.py（来源：test_grab_log.py, test_worker_line_stamp.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_grab_log.py ====================
"""grab.log 的轮转、写失败出口和关键动作的结构化日志行（S2）。

全部用系统临时目录；ensure_data_dir 换成空操作，免得测试在真实 data 目录里建东西。
"""

import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
import grab  # noqa: E402
from domain import log_events  # noqa: E402
from infrastructure import prefs_store  # noqa: E402


class _LogBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        self.log_file = self.root / "grab.log"
        self.lock_file = self.root / "grab.log.lock"
        for patcher in (mock.patch.object(grab, "LOG_FILE", self.log_file),
                        mock.patch.object(grab, "LOG_LOCK_FILE", self.lock_file,
                                          create=True),
                        mock.patch.object(grab, "ensure_data_dir", lambda: None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _log(self, text):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            grab.log(text)
        return out.getvalue(), err.getvalue()


class RotationTests(_LogBase):
    def test_small_file_is_left_alone(self):
        self.log_file.write_text("x" * 10, encoding="utf-8")
        self.assertFalse(grab.rotate_log_file(self.log_file, max_bytes=100, keep=5))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["grab.log"])

    def test_missing_file_is_not_an_error(self):
        self.assertFalse(grab.rotate_log_file(self.log_file, max_bytes=1, keep=5))

    def test_rotation_keeps_at_most_five_copies_newest_first(self):
        for round_no in range(1, 9):
            self.log_file.write_text("round-%d" % round_no, encoding="utf-8")
            self.assertTrue(grab.rotate_log_file(self.log_file, max_bytes=1, keep=5))
        names = sorted(p.name for p in self.root.iterdir())
        self.assertEqual(names, ["grab.log.1", "grab.log.2", "grab.log.3",
                                 "grab.log.4", "grab.log.5"], "最多 5 份，没有 .6")
        self.assertEqual((self.root / "grab.log.1").read_text(encoding="utf-8"), "round-8")
        self.assertEqual((self.root / "grab.log.5").read_text(encoding="utf-8"), "round-4",
                         "最老的几份被丢掉")

    def test_log_rotates_when_the_file_gets_big(self):
        with mock.patch.object(grab, "LOG_MAX_BYTES", 200):
            for index in range(60):
                self._log("第 %d 行 " % index + "内容" * 10)
        names = sorted(p.name for p in self.root.iterdir()
                       if not p.name.endswith(".lock"))
        self.assertIn("grab.log", names)
        self.assertIn("grab.log.1", names)
        self.assertLessEqual(len([n for n in names if n != "grab.log"]), 5)
        self.assertNotIn("grab.log.6", names)
        newest = self.log_file.read_text(encoding="utf-8")
        self.assertIn("第 59 行", newest, "最新的一行落在当前文件里")

    def test_rotation_failure_does_not_lose_the_line(self):
        with mock.patch.object(grab, "rotate_log_file", side_effect=PermissionError("占用")):
            out, err = self._log("照常写")
        self.assertIn("照常写", self.log_file.read_text(encoding="utf-8"))
        self.assertIn("日志轮转失败", err)
        self.assertIn("照常写", out)


class LogLockTests(_LogBase):
    """轮转与追加必须在同一把跨进程锁内，拿不到锁时降级但不丢当前行。"""

    def _hold_lock(self):
        holder = open(str(self.lock_file), "a+b")
        self.addCleanup(holder.close)
        prefs_store.acquire_file_lock(holder, 1.0)
        self.addCleanup(prefs_store.release_file_lock, holder)
        return holder

    def test_lock_timeout_does_not_append_without_the_lock(self):
        self._hold_lock()
        with mock.patch.object(grab, "LOG_LOCK_TIMEOUT_S", 0.2, create=True):
            out, err = self._log("锁住时也要写")
        self.assertIn("锁", err, "拿不到日志锁要留一条降级提示")
        self.assertFalse(self.log_file.exists(), "没拿到日志锁时不得无锁追加")
        self.assertIn("锁住时也要写", err, "当前行要落到 stderr/console 降级出口")
        self.assertIn("锁住时也要写", out)

    def test_rotation_waits_until_the_lock_is_released(self):
        self.log_file.write_text("x" * 100, encoding="utf-8")
        holder = open(str(self.lock_file), "a+b")
        self.addCleanup(holder.close)
        prefs_store.acquire_file_lock(holder, 1.0)
        with mock.patch.object(grab, "LOG_MAX_BYTES", 10), \
                mock.patch.object(grab, "LOG_LOCK_TIMEOUT_S", 0.2, create=True):
            try:
                self._log("锁内不轮转")
                self.assertFalse((self.root / "grab.log.1").exists(),
                                 "另一个进程持锁时不得轮转")
            finally:
                prefs_store.release_file_lock(holder)
            self._log("放锁后轮转")
        self.assertTrue((self.root / "grab.log.1").exists())

    def test_two_processes_append_and_rotate_without_losing_lines(self):
        code = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from pathlib import Path\n"
            "import grab\n"
            "grab.LOG_FILE = Path(sys.argv[2])\n"
            "grab.LOG_LOCK_FILE = Path(sys.argv[3])\n"
            "grab.ensure_data_dir = lambda: None\n"
            "grab.LOG_MAX_BYTES = 512\n"
            "grab.LOG_KEEP = 20\n"
            "tag = sys.argv[4]\n"
            "for i in range(80):\n"
            "    grab.log('%s-%03d' % (tag, i))\n"
        )
        procs = [subprocess.Popen(
            [sys.executable, "-X", "utf8", "-c", code, str(LOCAL),
             str(self.log_file), str(self.lock_file), tag],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8") for tag in ("a", "b")]
        outputs = [proc.communicate(timeout=180) for proc in procs]
        for proc, (out, err) in zip(procs, outputs):
            self.assertEqual(proc.returncode, 0, err)
        files = [path for path in self.root.glob("grab.log*")
                 if not path.name.endswith(".lock")]
        lines = []
        for path in files:
            lines.extend(path.read_text(encoding="utf-8").splitlines())
        self.assertEqual(len(lines), 160, "两个进程各 80 行，一行都不能丢")
        for line in lines:
            self.assertRegex(line, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [ab]-\d{3}$",
                             "轮转与追加交错时不得留下半截行")
        for tag in ("a", "b"):
            self.assertEqual(
                len([line for line in lines if line.split()[-1].startswith(tag + "-")]),
                80)


class WriteFailureTests(_LogBase):
    def test_unwritable_log_goes_to_stderr_and_does_not_raise(self):
        self.log_file.mkdir()          # 日志路径被一个目录占着：open 必然失败
        out, err = self._log("这行写不进文件")
        self.assertIn("写日志文件失败", err)
        self.assertIn("这行写不进文件", err, "stderr 里至少能看到没落盘的那一行")
        self.assertIn("这行写不进文件", out, "控制台输出照旧")

    def test_no_stderr_stream_is_tolerated(self):
        self.log_file.mkdir()
        with mock.patch.object(sys, "stderr", None), contextlib.redirect_stdout(io.StringIO()):
            grab.log("无控制台形态")       # 不抛就算过

    def test_data_dir_failure_still_writes_the_line(self):
        with mock.patch.object(grab, "ensure_data_dir", side_effect=OSError("没有权限")):
            out, err = self._log("数据目录不可用也要打出来")
        self.assertIn("数据目录不可用", err)
        self.assertIn("数据目录不可用也要打出来", out)


class EventLineTests(_LogBase):
    def _event(self, *args, **kwargs):
        lines = []
        with mock.patch.object(grab, "log", side_effect=lines.append):
            grab.log_event(*args, **kwargs)
        self.assertEqual(len(lines), 1)
        return lines[0]

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(grab._EVENT_CONTEXT, {"activity_id": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_fixed_fields_come_first_in_one_line(self):
        line = self._event("login_ok", "cli", elapsed_s=12.3456)
        self.assertEqual(line, "[event] level=INFO source=cli activity=- "
                               "event=login_ok elapsed_s=12.35")
        self.assertNotIn("\n", line)

    def test_activity_id_comes_from_argument_or_context(self):
        self.assertIn("activity=act-7", self._event("x", "worker", activity_id="act-7"))
        grab._EVENT_CONTEXT["activity_id"] = "act-9"
        self.assertIn("activity=act-9", self._event("x", "worker"))

    def test_secret_looking_fields_are_dropped(self):
        line = self._event("login_ok", "auto_relogin",
                           token="abc123SECRET", password="p@ss", captcha_text="ab12",
                           runtime_key="KEYVALUE", 验证码="1234", Authorization="Bearer x",
                           reason="verify_failed")
        for forbidden in ("abc123SECRET", "p@ss", "ab12", "KEYVALUE", "1234", "Bearer",
                          "token=", "password=", "captcha", "runtime_key"):
            self.assertNotIn(forbidden, line)
        self.assertIn("reason=verify_failed", line, "正常字段照留")

    def test_values_with_spaces_or_quotes_are_escaped(self):
        line = self._event("x", "cli", note='两个 词="引号"')
        self.assertIn('note="两个 词=\\"引号\\""', line)

    def test_fixed_names_cannot_be_overridden_by_fields(self):
        line = log_events.format_event_line(
            "x", "cli", level="ERROR",
            fields={"source": "evil", "event": "evil", "activity": "evil", "level": "evil"})
        self.assertIn("level=ERROR", line)
        self.assertEqual(line.count("source="), 1)
        self.assertEqual(line.count("event="), 1)
        self.assertNotIn("evil", line)

    def test_unknown_level_falls_back_to_info(self):
        self.assertIn("level=INFO", self._event("x", "cli", level="LOUD"))

    def test_event_reaches_the_file_with_a_timestamp_prefix(self):
        out, _err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(_err):
            grab.log_event("login_failed", "cli", level="WARN", reason="timeout")
        written = self.log_file.read_text(encoding="utf-8").strip()
        stamp, _, rest = written.partition(" [event] ")
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.assertEqual(rest, "level=WARN source=cli activity=- event=login_failed reason=timeout")

    def test_after_cmd_grab_log_event_carries_activity_id(self):
        """报名进程查到目标活动后，同进程后续写出的结构化事件必须自动带上该活动 id。

        保证排查单场报名记录时每条事件日志都关联到对应活动，不出现上下文丢失。
        """
        tests_dir = str(Path(__file__).resolve().parent)
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)
        from test_worker_boundaries import run_worker

        with mock.patch.dict(grab._EVENT_CONTEXT, dict(grab._EVENT_CONTEXT)):
            res = run_worker(behavior="success", max_attempts=1)
            line = self._event("after_grab", "worker")
        self.assertEqual(res.stop_reason, "success")
        self.assertIn("activity=act-1", line)


class PureFormatterTests(unittest.TestCase):
    def test_scrub_fields_keeps_order_and_drops_reserved_and_secret(self):
        clean = log_events.scrub_fields({"b": 1, "token": "x", "a": 2, "level": "X"})
        self.assertEqual(list(clean), ["b", "a"])

    def test_bool_and_none_values(self):
        line = log_events.format_event_line("e", "cli", fields={"ok": True, "gone": None})
        self.assertIn("ok=true", line)
        self.assertIn("gone=None", line)

    def test_very_long_value_is_cut(self):
        line = log_events.format_event_line("e", "cli", fields={"blob": "x" * 5000})
        self.assertLess(len(line), 400)

    def test_login_success_message_no_longer_promises_a_lifetime(self):
        source = ((LOCAL / "grab.py").read_text(encoding="utf-8")
                  + "\n"
                  + (LOCAL / "application" / "worker_login.py").read_text(encoding="utf-8"))
        self.assertIn("登录成功，登录态已保存", source)
        self.assertNotIn("有效期约 17 小时", source)


class FrozenLogDoesNotMigratePerLineTests(_LogBase):
    """G1：冻结态下每写一行日志都走 ensure_data_dir，迁移（含两把锁）不能每行重来。"""

    def test_many_log_lines_migrate_at_most_once(self):
        import runtime_paths
        data_dir = self.root / "data-root"
        data_dir.mkdir()

        def finished():
            # 替身模拟「完整跑完一次」：真实实现跑完会置位 _MIGRATION_DONE
            runtime_paths._MIGRATION_DONE = True

        with mock.patch.object(runtime_paths, "DATA_DIR", data_dir), \
                mock.patch.object(runtime_paths, "_MIGRATION_DONE", False, create=True), \
                mock.patch.object(runtime_paths, "_MIGRATION_RECORD", None), \
                mock.patch.object(runtime_paths, "_migrate_legacy_data",
                                  side_effect=finished) as migrate, \
                mock.patch.object(sys, "frozen", True, create=True), \
                mock.patch.object(grab, "ensure_data_dir", runtime_paths.ensure_data_dir):
            for index in range(5):
                self._log("第 %d 行" % index)
        self.assertEqual(migrate.call_count, 1, "五行日志只允许迁移一次")
        text = self.log_file.read_text(encoding="utf-8")
        self.assertEqual(text.count("第 "), 5, "五行日志都要写进 grab.log")

# ==================== 源自 test_worker_line_stamp.py ====================
"""worker 输出行带北京时间前缀时，结构行必须仍能被识别（W6）。

约定：worker 的 log() 把每行写成「YYYY-MM-DD HH:MM:SS 消息」，
而 [retry]、「第 N 次提交」、[X] 这类结构行的识别点都要求行首就是标记。
去前缀的唯一入口是 domain.worker_lines.worker_message；这里用真实格式的
时间戳回放：时间戳由 time_contract.school_time_text 生成，另覆盖 grab.log
时钟不可用时的回退格式。全部离线：假 worker 脚本，不调用 grab.log
（它会写数据目录），不联网，不读真实配置。

@author Author
"""

import shutil
import threading
import time
from datetime import datetime

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
        self.root = Path(tempfile.mkdtemp(prefix="campus-worker-stamp-")).resolve()
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
