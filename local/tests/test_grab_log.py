"""grab.log 的轮转、写失败出口和关键动作的结构化日志行（S2）。

全部用系统临时目录；ensure_data_dir 换成空操作，免得测试在真实 data 目录里建东西。
"""
from __future__ import annotations

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
        self.root = Path(self._tmp.name)
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
        source = (LOCAL / "grab.py").read_text(encoding="utf-8")
        self.assertNotIn("有效期约 17 小时", source)


if __name__ == "__main__":
    unittest.main()
