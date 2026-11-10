"""登录态写入口（S5）：save_session 带跨进程锁、读失败有日志、读取 token 不加锁。

全部用系统临时目录，不碰真实 data；grab.log 换成收集器，免得测试往真实日志里写。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LOCAL))
import grab  # noqa: E402
from infrastructure import prefs_store  # noqa: E402


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.session = self.root / "session.json"
        self.logs = []
        patcher = mock.patch.object(grab, "log", side_effect=self.logs.append)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _read(self):
        return json.loads(self.session.read_text(encoding="utf-8"))


class SaveSessionTests(_Base):
    def test_threads_saving_together_lose_nothing(self):
        # 8 个线程各写 25 次：全部写成功，最后留下的是完整的一份，没有残留临时文件
        results = []
        guard = threading.Lock()

        def worker(index):
            for step in range(25):
                ok = grab.save_session({"token": "t-%d-%d" % (index, step)}, path=self.session)
                with guard:
                    results.append(ok)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        self.assertEqual(len(results), 200)
        self.assertTrue(all(results), "没有一次写入被丢掉")
        self.assertTrue(self._read()["token"].startswith("t-"), "文件是完整可解析的")
        self.assertEqual(list(self.root.glob("*.tmp")), [], "不留临时文件")
        self.assertEqual(self.logs, [], "正常写入不产生日志")

    def test_two_processes_saving_together_lose_nothing(self):
        # 跨进程：界面进程和命令行进程同时落盘，靠 session.json.lock 排队
        code = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import grab\n"
            "from pathlib import Path\n"
            "target, tag = Path(sys.argv[2]), sys.argv[3]\n"
            "ok = 0\n"
            "for step in range(40):\n"
            "    ok += bool(grab.save_session({'token': '%s-%d' % (tag, step)}, path=target))\n"
            "print(ok)\n"
        )
        procs = [subprocess.Popen([sys.executable, "-X", "utf8", "-c", code, str(LOCAL),
                                   str(self.session), tag],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for tag in ("a", "b")]
        outputs = [proc.communicate(timeout=120) for proc in procs]
        for proc, (out, err) in zip(procs, outputs):
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(out.strip(), "40", "每次写入都成功")
        self.assertEqual(self._read()["token"].split("-")[0] in ("a", "b"), True)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_lock_timeout_gives_up_without_raising(self):
        # 另一个进程占着文件锁：最多等 timeout_s，写日志放弃，不抛异常，也不动原文件
        self.session.write_text(json.dumps({"token": "old"}), encoding="utf-8")
        holder = open(str(self.session) + ".lock", "a+b")
        self.addCleanup(holder.close)
        prefs_store.acquire_file_lock(holder, 1.0)
        try:
            started = time.monotonic()
            ok = grab.save_session({"token": "new"}, path=self.session, timeout_s=0.3)
            waited = time.monotonic() - started
        finally:
            prefs_store.release_file_lock(holder)
        self.assertFalse(ok)
        self.assertLess(waited, 3.0, "只等到超时，不无限卡住")
        self.assertEqual(self._read()["token"], "old", "放弃的这次写入不动原文件")
        self.assertTrue(any("没拿到登录态写锁" in line for line in self.logs))

    def test_thread_contention_also_times_out_quietly(self):
        # 同进程里另一个线程正占着写锁：同样超时放弃
        entered, release = threading.Event(), threading.Event()

        def hold():
            with grab._session_write_lock(self.session):
                entered.set()
                release.wait(5)

        thread = threading.Thread(target=hold)
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            ok = grab.save_session({"token": "new"}, path=self.session, timeout_s=0.2)
        finally:
            release.set()
            thread.join(5)
        self.assertFalse(ok)
        self.assertFalse(self.session.exists())
        self.assertTrue(any("没拿到登录态写锁" in line for line in self.logs))

    def test_default_timeout_is_five_seconds(self):
        self.assertEqual(grab.SESSION_LOCK_TIMEOUT_S, 5.0)

    def test_reading_token_never_waits_for_the_write_lock(self):
        self.session.write_text(json.dumps({"token": " tok-1 "}), encoding="utf-8")
        with mock.patch.object(grab, "SESSION_FILE", self.session):
            with grab._session_write_lock(self.session):
                self.assertEqual(grab.token(), "tok-1")

    def test_state_file_shares_the_session_lock(self):
        state = self.root / "storage_state.json"
        self.assertTrue(grab.save_storage_state({"cookies": []}, path=state,
                                                session_path=self.session))
        self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"cookies": []})
        holder = open(str(self.session) + ".lock", "a+b")
        self.addCleanup(holder.close)
        prefs_store.acquire_file_lock(holder, 1.0)
        try:
            ok = grab.save_storage_state({"cookies": [1]}, path=state,
                                         session_path=self.session, timeout_s=0.2)
        finally:
            prefs_store.release_file_lock(holder)
        self.assertFalse(ok, "state 与 session 共用一把锁")


class SaveVerifiedUnderLockTests(_Base):
    def test_pair_is_written_inside_the_lock(self):
        state = self.root / "storage_state.json"
        grab.save_verified_files({"s": 1}, {"token": "t"}, state, self.session)
        self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"s": 1})
        self.assertEqual(self._read(), {"token": "t"})

    def test_lock_timeout_raises_oserror_and_touches_nothing(self):
        state = self.root / "storage_state.json"
        holder = open(str(self.session) + ".lock", "a+b")
        self.addCleanup(holder.close)
        prefs_store.acquire_file_lock(holder, 1.0)
        try:
            with self.assertRaises(OSError):
                grab.save_verified_files({"s": 1}, {"token": "t"}, state, self.session,
                                         timeout_s=0.2)
        finally:
            prefs_store.release_file_lock(holder)
        self.assertTrue(any("没拿到" in line or "没写成" in line for line in self.logs))
        self.assertFalse(state.exists())
        self.assertFalse(self.session.exists())


class _FakePage:
    """命令行登录的最小页面替身：只回答 token 轮询与 localStorage 快照。"""

    def __init__(self, token="tok-new", items=None):
        self.token = token
        self.items = dict(items or {"xgUniToken": token, "xm": "张三"})
        self.closed = False

    def goto(self, url, wait_until=None, timeout=None):
        self.url = url

    def is_closed(self):
        return self.closed

    def evaluate(self, js):
        if "xgUniToken" in js:
            return self.token
        return dict(self.items)

    def wait_for_timeout(self, ms):
        pass


class _FakeCtx:
    def __init__(self):
        self.closed = False
        self.new_state = {"cookies": [{"name": "new"}]}

    def new_page(self):
        return _FakePage()

    def storage_state(self):
        return dict(self.new_state)

    def close(self):
        self.closed = True


class _FakeBrowser:
    def close(self):
        pass


class _FakePlaywright:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _fake_playwright_modules():
    """cmd_login 在函数里导入 playwright：没有真依赖时用替身模块顶上。"""
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = lambda: _FakePlaywright()
    package = types.ModuleType("playwright")
    package.sync_api = module
    return {"playwright": package, "playwright.sync_api": module}


class CmdLoginTransactionTests(_Base):
    """命令行登录成功必须把 state+session 当一笔事务落盘，失败不报成功。"""

    def setUp(self):
        super().setUp()
        self.state = self.root / "storage_state.json"
        self.session_path = self.root / "session.json"
        self.state.write_bytes(b'{"old": "state"}')
        self.session_path.write_bytes(b'{"old": "session"}')
        self.browser = _FakeBrowser()
        self.ctx = _FakeCtx()
        for patcher in (
            mock.patch.object(grab, "STATE_FILE", self.state),
            mock.patch.object(grab, "SESSION_FILE", self.session_path),
            mock.patch.object(grab, "ensure_data_dir", lambda: None),
            mock.patch.object(grab, "launch_browser", lambda pw, headless: self.browser),
            mock.patch.object(grab, "new_context", lambda browser, with_state=True: self.ctx),
            mock.patch.object(grab, "check_token", lambda: (True, "ok")),
            mock.patch.dict(sys.modules, _fake_playwright_modules()),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _login(self):
        out = io.StringIO()
        args = types.SimpleNamespace(relay=False, timeout=5)
        with contextlib.redirect_stdout(out):
            code = grab.cmd_login(args)
        return code, out.getvalue()

    def test_success_writes_both_files_in_one_transaction(self):
        code, output = self._login()
        self.assertEqual(code, 0, output)
        self.assertIn("[OK] 登录成功", output)
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8")),
                         {"cookies": [{"name": "new"}]})
        saved = json.loads(self.session_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["token"], "tok-new")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_second_file_failure_keeps_old_pair_and_reports_failure(self):
        originals = {self.state: self.state.read_bytes(),
                     self.session_path: self.session_path.read_bytes()}
        real_replace = os.replace
        calls = []

        def fail_second(src, dst):
            calls.append(dst)
            if len(calls) == 2:
                raise OSError("second replace failed")
            return real_replace(src, dst)

        with mock.patch("grab.os.replace", side_effect=fail_second):
            code, output = self._login()
        self.assertEqual(code, 2, output)
        self.assertNotIn("[OK] 登录成功", output)
        for path, blob in originals.items():
            self.assertEqual(path.read_bytes(), blob, "旧的两份登录态组合必须保持不变")
        self.assertEqual(list(self.root.glob("*.tmp")), [], "回滚后不留临时文件")


class ReadJsonTests(_Base):
    def test_missing_file_is_silent(self):
        self.assertEqual(grab.read_json(self.root / "nope.json", {"d": 1}), {"d": 1})
        self.assertEqual(self.logs, [], "文件不存在是常态，不写日志")

    def test_unreadable_content_logs_once_without_the_content(self):
        self.session.write_text('{"token": "secret-value"', encoding="utf-8")   # 半截 JSON
        self.assertEqual(grab.read_json(self.session, {}), {})
        self.assertEqual(len(self.logs), 1)
        self.assertIn("session.json", self.logs[0])
        self.assertIn("读取", self.logs[0])
        self.assertNotIn("secret-value", self.logs[0], "日志不带文件内容")

    def test_directory_in_place_of_file_is_a_read_failure(self):
        folder = self.root / "session.json.d"
        folder.mkdir()
        self.assertIsNone(grab.read_json(folder, None))
        self.assertEqual(len(self.logs), 1)


if __name__ == "__main__":
    unittest.main()
