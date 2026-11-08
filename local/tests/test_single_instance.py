#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""防止开两份（对账表 GL01，计划 20261108 be-single-instance）的回归。

三层：
- infrastructure.single_instance：替身 kernel32 / user32（不建真实的产品互斥量、不弹真实
  消息框），临时数据目录在 tempfile.gettempdir() 下，回环连接只在本进程内；
- app.Api._on_second_open：复用 show_window 叫回窗口，发 second_open 与运行记录；
- app.main：第二份唤回后直接退出、不起窗口；守卫出错放行；--demo 不接入。
  main 里的窗口、时钟、生命周期、Api 全换成内存替身，绝不真的起界面。
"""
from __future__ import annotations

import ctypes
import functools
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL = os.path.dirname(HERE)
for p in (LOCAL, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from infrastructure import single_instance as si  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from fixtures.business_clock import FakeBusinessClock  # noqa: E402

NOW = 1793100000.0     # 假「北京时间」锚点（与真实系统日期无关）
WAIT_S = 3.0


class FakeKernel32:
    """进程内互斥量登记表：同名第二次创建返回 ERROR_ALREADY_EXISTS，关句柄才减计数。"""

    def __init__(self, registry=None, fail=None):
        self.registry = registry if registry is not None else {}
        self.fail = fail            # None / "raise" / "null"
        self.handles = {}
        self.closed = []
        self._next = 100

    def create_mutex(self, name):
        if self.fail == "raise":
            raise OSError("CreateMutexW boom")
        if self.fail == "null":
            return 0, 5
        exists = self.registry.get(name, 0) > 0
        self.registry[name] = self.registry.get(name, 0) + 1
        self._next += 1
        self.handles[self._next] = name
        return self._next, (si.ERROR_ALREADY_EXISTS if exists else 0)

    def close_handle(self, handle):
        name = self.handles.pop(handle)
        self.registry[name] -= 1
        self.closed.append(handle)


class FakeUser32:
    def __init__(self):
        self.boxes = []
        self.allowed = []

    def message_box(self, text, title, flags):
        self.boxes.append((text, title, flags))

    def allow_set_foreground(self, pid):
        self.allowed.append(pid)


def _free_port() -> int:
    """拿一个此刻没人在听的回环端口（绑定后立刻关掉）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _TempDirCase(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp(prefix="campus-si-", dir=tempfile.gettempdir())
        self.addCleanup(shutil.rmtree, self.data_dir, True)
        self.registry = {}
        self.logs = []

    def make(self, pid=1111, kernel32=None, user32=None, **kw):
        guard = si.SingleInstance(
            self.data_dir, kernel32=kernel32 or FakeKernel32(self.registry),
            user32=user32 if user32 is not None else FakeUser32(),
            is_windows=True, log=self.logs.append, pid=pid, **kw)
        self.addCleanup(guard.close)
        return guard

    def start_first(self, on_activate=None):
        first = self.make(pid=1111)
        self.assertEqual(first.acquire(), si.FIRST)
        activated = threading.Event()

        def _activate():
            activated.set()
            if on_activate is not None:
                on_activate()

        self.assertTrue(first.start_listener(_activate))
        return first, activated

    def read_port_file(self):
        with open(os.path.join(self.data_dir, si.PORT_FILE_NAME), encoding="utf-8") as fp:
            return json.load(fp)


# ------------------------------------------------------------- 判定与监听
class FirstInstanceTests(_TempDirCase):
    def test_first_acquires_mutex_and_listens_on_loopback_only(self):
        first, _ = self.start_first()
        self.assertEqual(first.role, si.FIRST)
        self.assertEqual(self.registry[si.MUTEX_NAME], 1)
        host, port = first._sock.getsockname()
        self.assertEqual(host, "127.0.0.1")
        info = self.read_port_file()
        self.assertEqual(info["port"], port)
        self.assertEqual(info["pid"], 1111)
        self.assertGreaterEqual(len(info["token"]), 32)
        # 口令只在端口文件里：诊断日志里没有它
        self.assertFalse(any(info["token"] in line for line in self.logs))

    def test_mutex_name_carries_only_the_product_identifier(self):
        self.assertEqual(si.MUTEX_NAME, "Local\\TianSoftActivityPreRegistration.gui")

    def test_non_windows_is_unguarded_and_never_listens(self):
        guard = si.SingleInstance(self.data_dir, is_windows=False, log=self.logs.append)
        self.assertEqual(guard.acquire(), si.UNGUARDED)
        self.assertFalse(guard.start_listener(lambda: None))
        guard.close()
        self.assertFalse(os.path.exists(os.path.join(self.data_dir, si.PORT_FILE_NAME)))


class SecondInstanceTests(_TempDirCase):
    def test_second_detects_existing_signals_first_and_exits_without_ui(self):
        first, activated = self.start_first()
        user32 = FakeUser32()
        k2 = FakeKernel32(self.registry)
        second = self.make(pid=2222, kernel32=k2, user32=user32)
        self.assertEqual(second.acquire(), si.SECOND)
        # 第二份拿到的是第一份那把锁的句柄，必须立刻关掉、不占着
        self.assertEqual(len(k2.closed), 1)
        self.assertEqual(self.registry[si.MUTEX_NAME], 1)
        self.assertEqual(second.hand_over(), 0)
        self.assertTrue(activated.wait(WAIT_S), "第一份没有收到唤回")
        self.assertEqual(user32.boxes, [], "唤回成功时不该再弹消息框")
        # 前台权让给第一份，它的 Activate 才能真把窗口顶上来
        self.assertEqual(user32.allowed, [1111])
        # 第二份不监听、不写端口文件
        self.assertFalse(second.start_listener(lambda: None))
        self.assertEqual(self.read_port_file()["pid"], 1111)

    def test_missing_port_file_shows_message_box_and_exits(self):
        first = self.make(pid=1111)
        self.assertEqual(first.acquire(), si.FIRST)   # 还没开监听：端口文件不存在
        user32 = FakeUser32()
        second = self.make(pid=2222, user32=user32)
        self.assertEqual(second.acquire(), si.SECOND)
        self.assertEqual(second.hand_over(), 0)
        self.assertEqual(len(user32.boxes), 1)
        text, title, _flags = user32.boxes[0]
        self.assertIn("工具已经开着", text)
        self.assertIn("免得同一场被提交两遍", text)
        self.assertEqual(title, "校园活动预报名工具")

    def test_refused_connection_shows_message_box(self):
        with open(os.path.join(self.data_dir, si.PORT_FILE_NAME), "w", encoding="utf-8") as fp:
            json.dump({"pid": 1111, "port": _free_port(), "token": "x" * 64}, fp)
        user32 = FakeUser32()
        second = self.make(pid=2222, user32=user32, timeout_s=0.5)
        self.assertFalse(second.signal_first())
        self.assertEqual(second.hand_over(), 0)
        self.assertEqual(len(user32.boxes), 1)

    def test_silent_peer_times_out_then_message_box(self):
        """端口上的东西收了连接却不回 ok（陈旧文件指到别的程序）：超时后照样提示并退出。"""
        silent = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(silent.close)
        silent.bind(("127.0.0.1", 0))
        silent.listen(1)
        with open(os.path.join(self.data_dir, si.PORT_FILE_NAME), "w", encoding="utf-8") as fp:
            json.dump({"pid": 0, "port": silent.getsockname()[1], "token": "y" * 64}, fp)
        user32 = FakeUser32()
        second = self.make(pid=2222, user32=user32, timeout_s=0.3)
        self.assertEqual(second.hand_over(), 0)
        self.assertEqual(len(user32.boxes), 1)
        self.assertEqual(user32.allowed, [], "pid 缺失时不该让出前台权")

    def test_garbled_port_file_shows_message_box(self):
        with open(os.path.join(self.data_dir, si.PORT_FILE_NAME), "w", encoding="utf-8") as fp:
            fp.write("{not json")
        user32 = FakeUser32()
        second = self.make(pid=2222, user32=user32)
        self.assertEqual(second.hand_over(), 0)
        self.assertEqual(len(user32.boxes), 1)

    def test_message_box_failure_still_exits(self):
        class Broken(FakeUser32):
            def message_box(self, *a):
                raise OSError("no desktop")
        second = self.make(pid=2222, user32=Broken())
        self.assertEqual(second.hand_over(), 0)
        self.assertTrue(any("工具已经开着" in line for line in self.logs))


class ListenerHardeningTests(_TempDirCase):
    def _raw(self, port, payload: bytes) -> bytes:
        """发一段原始字节，返回对方回的全部内容；被对方直接掐断（RST）也算「没回」。"""
        data = b""
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=WAIT_S) as conn:
                conn.settimeout(WAIT_S)
                conn.sendall(payload)
                try:
                    conn.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                while True:
                    chunk = conn.recv(64)
                    if not chunk:
                        return data
                    data += chunk
        except (ConnectionResetError, ConnectionAbortedError):
            return data

    def test_wrong_token_and_bad_messages_are_rejected_listener_survives(self):
        first, activated = self.start_first()
        port = first.port
        bad = [
            json.dumps({"op": "activate", "token": "0" * 64}).encode() + b"\n",
            json.dumps({"op": "exit", "token": self.read_port_file()["token"]}).encode() + b"\n",
            json.dumps(["activate"]).encode() + b"\n",
            b"\xff\xfe garbage\n",
            b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n",
            b"{" + b"a" * (si.MAX_MESSAGE_BYTES * 2),
            b"",
        ]
        for payload in bad:
            self.assertEqual(self._raw(port, payload), b"", "坏消息不该得到任何回复：%r" % payload[:30])
        self.assertFalse(activated.is_set(), "坏消息不该触发唤回")
        # 监听还活着：正确的第二份照样能唤回
        second = self.make(pid=2222)
        self.assertEqual(second.acquire(), si.SECOND)
        self.assertTrue(second.signal_first())
        self.assertTrue(activated.wait(WAIT_S))

    def test_activation_error_does_not_kill_listener(self):
        calls = []

        def boom():
            calls.append(1)
            raise RuntimeError("window gone")

        first, activated = self.start_first(on_activate=boom)
        second = self.make(pid=2222)
        second.acquire()
        self.assertTrue(second.signal_first())
        self.assertTrue(activated.wait(WAIT_S))
        activated.clear()
        self.assertTrue(second.signal_first(), "唤回回调抛错后监听不能死")
        self.assertTrue(activated.wait(WAIT_S))

    def test_listener_bind_failure_fails_open(self):
        guard = self.make()
        self.assertEqual(guard.acquire(), si.FIRST)
        with mock.patch.object(si.socket, "socket", side_effect=OSError("no sockets")):
            self.assertFalse(guard.start_listener(lambda: None))
        self.assertFalse(os.path.exists(os.path.join(self.data_dir, si.PORT_FILE_NAME)))
        self.assertTrue(self.logs, "失败要留一句诊断")

    def test_stop_listener_makes_later_signal_fail(self):
        first, _ = self.start_first()
        first.stop_listener()
        user32 = FakeUser32()
        second = self.make(pid=2222, user32=user32, timeout_s=0.5)
        second.acquire()
        self.assertEqual(second.hand_over(), 0)
        self.assertEqual(len(user32.boxes), 1)


class FailOpenTests(_TempDirCase):
    def test_create_mutex_raising_is_unguarded(self):
        guard = self.make(kernel32=FakeKernel32(self.registry, fail="raise"))
        self.assertEqual(guard.acquire(), si.UNGUARDED)
        self.assertFalse(guard.start_listener(lambda: None))
        guard.close()
        self.assertTrue(any("照常启动" in line for line in self.logs))

    def test_create_mutex_null_handle_is_unguarded(self):
        guard = self.make(kernel32=FakeKernel32(self.registry, fail="null"))
        self.assertEqual(guard.acquire(), si.UNGUARDED)

    def test_kernel32_load_failure_is_unguarded(self):
        guard = si.SingleInstance(self.data_dir, is_windows=True, log=self.logs.append)
        with mock.patch.object(si, "_Kernel32", side_effect=OSError("no kernel32")):
            self.assertEqual(guard.acquire(), si.UNGUARDED)
        guard.close()


class CleanupTests(_TempDirCase):
    def test_close_removes_own_port_file_and_releases_mutex(self):
        first, _ = self.start_first()
        path = os.path.join(self.data_dir, si.PORT_FILE_NAME)
        self.assertTrue(os.path.exists(path))
        first.close()
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.registry[si.MUTEX_NAME], 0)
        first.close()   # 可重复调用
        # 放掉之后新的一份是第一份
        again = self.make(pid=3333)
        self.assertEqual(again.acquire(), si.FIRST)

    def test_close_keeps_a_foreign_port_file(self):
        first, _ = self.start_first()
        path = os.path.join(self.data_dir, si.PORT_FILE_NAME)
        foreign = {"pid": 9999, "port": 1, "token": "f" * 64}
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(foreign, fp)
        first.close()
        self.assertEqual(self.read_port_file(), foreign, "别人的端口文件不能删")
        self.assertEqual(self.registry[si.MUTEX_NAME], 0)


@unittest.skipUnless(os.name == "nt", "真实 kernel32 只在 Windows 上有")
class RealKernel32SmokeTests(unittest.TestCase):
    """ctypes 签名冒烟：用一次性随机名字，不碰产品互斥量。"""

    def test_real_create_mutex_reports_already_exists(self):
        name = "Local\\campus-si-test-%s" % uuid.uuid4().hex
        k1, k2 = si._Kernel32(), si._Kernel32()
        h1, e1 = k1.create_mutex(name)
        try:
            self.assertTrue(h1)
            self.assertNotEqual(e1, si.ERROR_ALREADY_EXISTS)
            h2, e2 = k2.create_mutex(name)
            self.assertTrue(h2)
            self.assertEqual(e2, si.ERROR_ALREADY_EXISTS)
            k2.close_handle(h2)
        finally:
            k1.close_handle(h1)


# ------------------------------------------------------------------ Api 层
try:
    import app as local_app
    _IMPORT_ERROR = None
except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时如实跳过并报告
    local_app = None
    _IMPORT_ERROR = exc


class _FakeWindow:
    def __init__(self, fail_show=False):
        self.calls = []
        self.fail_show = fail_show

    def show(self):
        self.calls.append("show")
        if self.fail_show:
            raise RuntimeError("window closed")

    def restore(self):
        self.calls.append("restore")

    def evaluate_js(self, js):
        self.calls.append(("js", js))


@unittest.skipIf(local_app is None, "无法导入 local/app.py：%s" % (_IMPORT_ERROR,))
class ApiSecondOpenTests(unittest.TestCase):
    def _api(self, clock=None):
        api = stop_auto_relogin_on_cleanup(self, local_app.Api(clock=clock))
        self.events = []
        api._emit = lambda kind, payload: self.events.append((kind, payload))
        # show_window 会写 phone.log：测试里不落真实数据目录
        patcher = mock.patch.object(local_app, "phone_log", lambda *_a, **_k: None)
        patcher.start()
        self.addCleanup(patcher.stop)
        return api

    def test_second_open_restores_window_and_emits_banner_and_log(self):
        api = self._api(FakeBusinessClock(epoch=NOW))
        window = _FakeWindow()
        api._window = window
        api._window_hidden = True
        api._window_minimized = True
        api._on_second_open()
        # 复用 show_window：藏到后台和最小化都叫回来
        self.assertEqual(window.calls[:2], ["show", "restore"])
        self.assertFalse(api._window_hidden)
        self.assertFalse(api._window_minimized)
        self.assertEqual(self.events, [
            ("second_open", {"at": NOW}),
            ("log", "又打开了一次，已切回这个窗口"),
        ])

    def test_second_open_without_clock_sends_null_at(self):
        api = self._api()          # 未注入时钟：显式不可用，不回退墙钟
        api._window = _FakeWindow()
        with mock.patch.object(local_app, "DEMO", False):
            api._on_second_open()
        self.assertEqual(self.events[0], ("second_open", {"at": None}))

    def test_second_open_still_emits_when_window_fails(self):
        api = self._api(FakeBusinessClock(epoch=NOW))
        api._window = _FakeWindow(fail_show=True)
        api._on_second_open()
        self.assertEqual([kind for kind, _ in self.events], ["second_open", "log"])

    def test_real_emit_pushes_second_open_to_on_backend(self):
        api = stop_auto_relogin_on_cleanup(self, local_app.Api(clock=FakeBusinessClock(epoch=NOW)))
        window = _FakeWindow()
        api._window = window
        with mock.patch.object(local_app, "phone_log", lambda *_a, **_k: None):
            api._on_second_open()
        scripts = [c[1] for c in window.calls if isinstance(c, tuple)]
        self.assertIn("window.onBackend && window.onBackend.second_open(%s)"
                      % json.dumps({"at": NOW}), scripts)
        self.assertIn("window.onBackend && window.onBackend.log(%s)"
                      % json.dumps("又打开了一次，已切回这个窗口", ensure_ascii=False), scripts)


# ----------------------------------------------------------------- main 接线
class _FakeClock:
    def __init__(self, background=True):
        self.closed = False

    def now(self):
        return NOW

    def snapshot(self):
        return {}

    def close(self):
        self.closed = True


class _FakeMainApi:
    instances = []

    def __init__(self, clock=None):
        self.clock = clock
        self._window = None
        self.second_open = threading.Event()
        self.shutdown_called = False
        _FakeMainApi.instances.append(self)

    def _start_clock_monitor(self):
        pass

    def schedule_phone_restore(self, window):
        pass

    def _on_window_minimized(self):
        pass

    def _on_window_restored(self):
        pass

    def _on_second_open(self):
        self.second_open.set()

    def shutdown(self):
        self.shutdown_called = True


@unittest.skipIf(local_app is None, "无法导入 local/app.py：%s" % (_IMPORT_ERROR,))
class MainWiringTests(_TempDirCase):
    def setUp(self):
        super().setUp()
        _FakeMainApi.instances = []
        self.created = []
        self.started = []
        self.on_start = None
        self.k_main = FakeKernel32(self.registry)
        self.u_main = FakeUser32()
        self.atexit_calls = []
        lifecycle = SimpleNamespace(finalize=lambda: None)
        real_cls = si.SingleInstance
        self.guard_cls = functools.partial(real_cls, kernel32=self.k_main, user32=self.u_main,
                                           is_windows=True, log=self.logs.append, pid=1111)

        def create_window(*args, **kwargs):
            window = SimpleNamespace()
            self.created.append((args, kwargs))
            return window

        def start(debug=False):
            self.started.append(debug)
            if self.on_start is not None:
                self.on_start()

        patches = [
            mock.patch.object(sys, "argv", ["app.py"]),
            mock.patch.object(local_app, "DEMO", False),
            mock.patch.object(local_app, "DATA_DIR", local_app.Path(self.data_dir)),
            mock.patch.object(local_app, "ensure_data_dir", lambda: None),
            mock.patch.object(local_app, "BusinessClock", _FakeClock),
            mock.patch.object(local_app, "configure_time_source", lambda fn: None),
            mock.patch.object(local_app, "get_lifecycle", lambda now_fn=None: lifecycle),
            mock.patch.object(local_app, "Api", _FakeMainApi),
            mock.patch.object(local_app, "_screen_size", lambda: None),
            mock.patch.object(local_app.webview, "create_window", create_window),
            mock.patch.object(local_app.webview, "start", start),
            mock.patch.object(local_app.atexit, "register", self.atexit_calls.append),
            mock.patch.object(local_app._single_instance, "SingleInstance", self.guard_cls),
        ]
        if os.name == "nt":
            # main 会设一次进程级 DPI 感知：测试进程里换成替身，不留副作用
            patches.append(mock.patch.object(ctypes, "windll", mock.MagicMock()))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.real_cls = real_cls

    def _hold_mutex_elsewhere(self):
        other = self.real_cls(self.data_dir, kernel32=FakeKernel32(self.registry),
                              user32=FakeUser32(), is_windows=True,
                              log=self.logs.append, pid=4444)
        self.addCleanup(other.close)
        self.assertEqual(other.acquire(), si.FIRST)
        return other

    def test_second_instance_exits_before_any_window_clock_or_api(self):
        self._hold_mutex_elsewhere()          # 另一份已在跑，但没开监听
        rc = local_app.main()
        self.assertEqual(rc, 0)
        self.assertEqual(self.created, [], "第二份不得创建窗口")
        self.assertEqual(self.started, [], "第二份不得进入界面循环")
        self.assertEqual(_FakeMainApi.instances, [], "第二份不得构造 Api")
        self.assertEqual(len(self.u_main.boxes), 1, "唤回不成要弹「工具已经开着」")
        self.assertEqual(self.registry[si.MUTEX_NAME], 1, "第二份不得占着互斥量")

    def test_first_instance_listens_handles_activation_and_cleans_up(self):
        port_file = os.path.join(self.data_dir, si.PORT_FILE_NAME)
        seen = {}

        def during_gui_loop():
            # 界面循环期间：端口文件在、监听绑回环；模拟用户再双击一次
            seen["port_file"] = os.path.exists(port_file)
            second = self.real_cls(self.data_dir, kernel32=FakeKernel32(self.registry),
                                   user32=FakeUser32(), is_windows=True,
                                   log=self.logs.append, pid=2222)
            seen["role"] = second.acquire()
            seen["rc"] = second.hand_over()
            seen["activated"] = _FakeMainApi.instances[0].second_open.wait(WAIT_S)

        self.on_start = during_gui_loop
        rc = local_app.main()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.created), 1)
        self.assertEqual(seen, {"port_file": True, "role": si.SECOND, "rc": 0,
                                "activated": True})
        api = _FakeMainApi.instances[0]
        self.assertTrue(api.shutdown_called)
        # 退出：端口文件删掉、互斥量放掉
        self.assertFalse(os.path.exists(port_file))
        self.assertEqual(self.registry[si.MUTEX_NAME], 0)
        self.assertEqual(len(self.atexit_calls), 1, "异常退出兜底要登记 atexit")

    def test_guard_construction_error_fails_open(self):
        with mock.patch.object(local_app._single_instance, "SingleInstance",
                               side_effect=RuntimeError("boom")):
            rc = local_app.main()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.created), 1, "守卫出错也必须照常起窗口")
        self.assertEqual(len(self.started), 1)

    def test_create_mutex_error_fails_open(self):
        self.k_main.fail = "raise"
        rc = local_app.main()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.created), 1)
        self.assertFalse(os.path.exists(os.path.join(self.data_dir, si.PORT_FILE_NAME)))

    def test_demo_is_not_guarded(self):
        self._hold_mutex_elsewhere()
        built = []
        with mock.patch.object(sys, "argv", ["app.py", "--demo"]), \
                mock.patch.object(local_app._single_instance, "SingleInstance",
                                  side_effect=lambda *a, **k: built.append(1)):
            rc = local_app.main()
        self.assertEqual(rc, 0)
        self.assertEqual(built, [], "--demo 不接入单实例守卫")
        self.assertEqual(len(self.created), 1)


# ------------------------------------------------------------ 源码与 QA 桥契约
class SourceContractTests(unittest.TestCase):
    def _read(self, *parts):
        with open(os.path.join(LOCAL, *parts), encoding="utf-8") as fp:
            return fp.read()

    def test_module_never_binds_all_interfaces(self):
        src = self._read("infrastructure", "single_instance.py")
        self.assertNotIn("0.0.0.0", src)
        # 唯一的 bind 只用回环常量：空主机名等于所有网卡
        self.assertEqual(src.count(".bind("), 1)
        self.assertIn("sock.bind((LOOPBACK, 0))", src)
        self.assertIn('LOOPBACK = "127.0.0.1"', src)

    def test_infrastructure_module_imports_no_upper_layers(self):
        import ast
        tree = ast.parse(self._read("infrastructure", "single_instance.py"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertFalse(names & {"app", "application", "webview", "grab", "runtime_paths"},
                         names)

    def test_guard_runs_before_clock_api_and_window_in_main(self):
        src = self._read("app.py")
        main_src = src[src.index("def main("):]
        guard_at = main_src.index("instance_guard.acquire()")
        self.assertLess(main_src.index("--runtime-check"), guard_at)
        for later in ("BusinessClock(", "api = Api(", "webview.create_window"):
            self.assertLess(guard_at, main_src.index(later), later)

    def test_qa_bridge_can_trigger_second_open(self):
        bridge = self._read("tests", "fixtures", "runtime_bridge.js")
        self.assertIn("window.__QA_SECOND_OPEN", bridge)
        self.assertIn("second_open(payload)", bridge)
        self.assertIn("又打开了一次，已切回这个窗口", bridge)


if __name__ == "__main__":
    unittest.main()
