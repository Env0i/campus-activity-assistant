# -*- coding: utf-8 -*-
"""U6 定性：验证码页点「改用浏览器登录」时，先等 relogin_cancel 返回再发 login。

relogin_cancel 与 login 两个桥接调用并发时，后端仍可能以忙碌拒绝：中继 worker 占着 Api._proc，
_is_busy_locked 看它；relogin_cancel 里 terminate 最多等 1 秒再按需强杀；pywebview 每次 js_api
调用各起一个线程，两次调用没有先后保证。前端已改为先等取消返回再登录
（local/ui/views/relogin.js 的 closeRelogin().then(doLogin)），绕开了这个窗口。

后端 relogin_cancel 与 login 的并发竞态记为已知残留，留给重构步骤 2 的登录恢复一块；
并发顺序的修前失败原文见 .claude/results/20261113-prerefactor-fixes-red-output.txt。
本文件只保留「先取消后登录」一条：进程树用假的，terminate 期间进程还活着，terminate 返回时
才退，与 process_tree.ProcessTree 一致。不起真实进程、不联网、不读真实数据目录；
Api 经 stop_auto_relogin_on_cleanup 构造。

@author Author
"""
from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
LOCAL = TESTS.parent
for _path in (str(LOCAL), str(TESTS)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from fixtures.business_clock import TestWallClock  # noqa: E402
from time_contract import configure_time_source  # noqa: E402

configure_time_source(time.time)


def _import_app():
    sys.path.insert(0, str(LOCAL))
    try:
        import app as local_app
    except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
        raise unittest.SkipTest("无法导入 local/app.py：%s" % exc)
    finally:
        sys.path.pop(0)
    return local_app


class _Pipe:
    """中继 worker 的 stdin 替身：只收写入。"""

    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)

    def flush(self):
        pass


class _BlockingStdout:
    """stdout 替身：迭代时一直等到收尾，不产出任何行，中继的读线程就不会提前把这一场收掉。"""

    def __init__(self, stop: threading.Event):
        self._stop = stop

    def __iter__(self):
        self._stop.wait(10)
        return iter(())


class _FakeProc:
    """worker 进程替身：dead 置位之前 poll() 一直是 None。"""

    def __init__(self, stop: threading.Event):
        self.dead = threading.Event()
        self.stdin = _Pipe()
        self.stdout = _BlockingStdout(stop)
        self.pid = 4242
        self.returncode = None

    def poll(self):
        return 0 if self.dead.is_set() else None

    def wait(self, timeout=None):
        self.dead.wait(timeout)
        return 0


class _SlowDyingTree:
    """受管进程树替身。terminate() 期间进程还活着，等 exit_delay 之后才退并返回 True；
    ProcessTree.terminate 同样是「发出终止后等进程退（最多 1 秒），仍没退再强杀」，返回时进程已死。"""

    def __init__(self, stop: threading.Event, exit_delay: float):
        self.proc = _FakeProc(stop)
        self.exit_delay = exit_delay
        self.entered = threading.Event()
        self.closed = False

    def terminate(self):
        self.entered.set()
        time.sleep(self.exit_delay)
        self.proc.dead.set()
        return True

    def close(self):
        self.closed = True


class _PlainTree:
    """登录 worker 的替身：不用终止，只要能被登记为 _proc。"""

    def __init__(self, stop: threading.Event):
        self.proc = _FakeProc(stop)

    def terminate(self):
        self.proc.dead.set()
        return True

    def close(self):
        pass


class ReloginCancelThenBrowserLoginTests(unittest.TestCase):
    """从验证码页（中继 worker 在跑）切到浏览器登录。"""

    EXIT_DELAY = 0.6      # 假进程在 terminate 里多久才退

    def setUp(self):
        self.local_app = _import_app()
        tmp = tempfile.TemporaryDirectory(prefix="campus-relogin-busy-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for patch in (
            mock.patch.object(self.local_app, "DEMO", False),
            mock.patch.object(self.local_app, "PREFS", root / "ui.json"),
            mock.patch.object(self.local_app, "DEVICE_FILE", root / "devices.json"),
            mock.patch.object(self.local_app, "DATA_DIR", root),
            mock.patch.object(self.local_app, "LOG_FILE", root / "grab.log"),
            mock.patch.object(self.local_app, "LOG_LOCK_FILE", root / "grab.log.lock"),
            mock.patch.object(self.local_app, "worker_problem", lambda: ""),
            mock.patch.object(self.local_app, "worker_command", lambda *a: ["fake-worker"] + list(a)),
            mock.patch.object(self.local_app, "_env", lambda: {}),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(
            self, self.local_app.Api(clock=TestWallClock()))
        self.addCleanup(self.api.shutdown)
        self.api._terms_gate = lambda: None          # 条款门禁用替身：本用例只看忙碌判定
        self.api._emit = lambda *a, **k: None
        self.api._push_login_expired = mock.Mock()
        self.api._pump = lambda *a, **k: None        # 登录 worker 的输出泵用替身：不读真实管道
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.relay_tree = _SlowDyingTree(self.stop, self.EXIT_DELAY)
        self.login_tree = _PlainTree(self.stop)
        trees = iter([self.relay_tree, self.login_tree])
        patch = mock.patch.object(self.local_app, "spawn_owned", lambda *a, **k: next(trees))
        patch.start()
        self.addCleanup(patch.stop)

    def start_verification_page(self):
        """让中继 worker 活着：验证码页开着时的真实状态（_proc 被它占住）。"""
        self.api._relay.prepare("test-user", "test-pass")
        started = self.api._relay.begin(plan_active=False, worker_command=["fake-worker", "login"],
                                        manual=True, origin="desktop")
        self.assertTrue(started.get("ok"), started)
        self.assertTrue(self.api._is_busy(), "前提：中继 worker 占着忙碌位")
        return started["flow_id"]

    def test_cancel_returns_then_login_is_not_refused(self):
        """顺序 A：先取消，等 relogin_cancel 返回，再登录。返回时进程已退，login 必须放行。"""
        flow_id = self.start_verification_page()
        cancelled = self.api.relogin_cancel(flow_id)
        self.assertTrue(cancelled.get("ok"), cancelled)
        self.assertTrue(self.relay_tree.proc.dead.is_set(), "前提：terminate 返回时进程已退")
        result = self.api.login()
        self.assertTrue(result.get("ok"), "取消已返回，login 不该被忙碌拒绝：%r" % result)


if __name__ == "__main__":
    unittest.main()
