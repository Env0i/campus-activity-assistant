# -*- coding: utf-8 -*-
"""防止开两份（对账表 GL01，计划 20261108 NEEDS-HUMAN 3）。

为什么要有：没有单实例时，用户双击两次就有两个窗口，两边可能各跑一份报名计划，
同一场被提交两遍。这里只用标准库（ctypes + socket + secrets + hmac + json），不新增依赖。

做法：
1. 判定：Windows 用 kernel32.CreateMutexW 建一个固定名字的具名互斥量（名字只含产品标识，
   Local\\ 命名空间 = 只管当前登录会话）。GetLastError == ERROR_ALREADY_EXISTS 就是第二份。
   句柄留到进程退出；进程崩了系统会自动收回，不会把下一次启动锁死。
2. 第一份：在 127.0.0.1 的随机端口开一个只收「唤回」的监听，端口、进程号和随机口令写进
   数据目录下的 instance.json。口令只在这个文件里，不进日志、不进异常文本。
3. 第二份：读文件、连回环、发「唤回」，收到 ok 就安静退出；文件缺失、连不上、超时（约 2 秒）
   或口令被拒，就弹一个原生消息框「工具已经开着」再退出。无论哪条路都不起第二个界面。

失败一律放行第一份（fail-open）：建互斥量出错、监听起不来，都只记一句诊断、照常启动——
守卫本身绝不能让唯一的那一份打不开。

非 Windows：直接放行（返回 UNGUARDED）。产品只发 Windows 版，非 Windows 只有测试和开发
会走到这里；文件锁在网络盘和容器里语义不稳，换来的保护又用不上，不值得多一条分支。
"""
from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import sys
import threading
from pathlib import Path

# 互斥量名字固定，只含产品标识（与数据目录名同源），不含账号、路径或机器信息
MUTEX_NAME = "Local\\TianSoftActivityPreRegistration.gui"
PORT_FILE_NAME = "instance.json"
ERROR_ALREADY_EXISTS = 183
# 只绑本机回环：唤回信号不对外监听（计划 must_not）
LOOPBACK = "127.0.0.1"
SIGNAL_TIMEOUT_S = 2.0
ACCEPT_POLL_S = 0.5
MAX_MESSAGE_BYTES = 512
ACTIVATE = "activate"

FIRST = "first"          # 拿到了互斥量：照常启动
SECOND = "second"        # 已经有一份在跑：唤回它后退出，不起界面
UNGUARDED = "unguarded"  # 守卫不可用（非 Windows 或建互斥量出错）：放行

# 第二份唤回失败时的消息框（文案取原型 Main SecondRun 横幅 Main:2145；
# 没能切回去，所以不说「已切回」，改成告诉用户去哪找已开着的窗口）
MESSAGE_TITLE = "校园活动预报名工具"
MESSAGE_TEXT = ("工具已经开着。\n\n"
                "同一台电脑只运行一份，免得同一场被提交两遍。"
                "请从任务栏或托盘图标打开已经开着的窗口。")
MB_OK = 0x0
MB_ICONINFORMATION = 0x40
MB_SETFOREGROUND = 0x10000


def _stderr_log(message: str) -> None:
    """默认诊断输出：冻结的窗口版没有 stderr，写不出去就算了，绝不抛。"""
    try:
        stream = sys.stderr
        if stream is not None:
            stream.write("[single-instance] %s\n" % message)
    except Exception:
        pass


class _Kernel32:
    """kernel32 的最小包装：只暴露建互斥量和关句柄，便于测试换替身。"""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        lib = ctypes.WinDLL("kernel32", use_last_error=True)
        lib.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        lib.CreateMutexW.restype = wintypes.HANDLE
        lib.CloseHandle.argtypes = (wintypes.HANDLE,)
        lib.CloseHandle.restype = wintypes.BOOL
        self._lib = lib

    def create_mutex(self, name: str):
        """返回 (句柄, 建完后的 last error)；句柄为空表示建失败。"""
        handle = self._lib.CreateMutexW(None, False, name)
        return handle, self._ctypes.get_last_error()

    def close_handle(self, handle) -> None:
        self._lib.CloseHandle(handle)


class _User32:
    """user32 的最小包装：消息框与「允许对方抢前台」。"""

    def __init__(self):
        import ctypes
        from ctypes import wintypes

        lib = ctypes.WinDLL("user32", use_last_error=True)
        lib.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR,
                                    wintypes.LPCWSTR, wintypes.UINT)
        lib.MessageBoxW.restype = ctypes.c_int
        lib.AllowSetForegroundWindow.argtypes = (wintypes.DWORD,)
        lib.AllowSetForegroundWindow.restype = wintypes.BOOL
        self._lib = lib

    def message_box(self, text: str, title: str, flags: int) -> None:
        self._lib.MessageBoxW(None, text, title, flags)

    def allow_set_foreground(self, pid: int) -> None:
        self._lib.AllowSetForegroundWindow(int(pid))


class SingleInstance:
    """一份进程的单实例守卫。用法见 local/app.py main()：

        guard = SingleInstance(DATA_DIR)
        if guard.acquire() == SECOND:
            return guard.hand_over()          # 不起界面，退出码 0
        ...建窗口...
        guard.start_listener(on_activate)     # 收到唤回就调 on_activate()
        ...窗口关了...
        guard.close()                         # 停监听、删自己的端口文件、放互斥量
    """

    def __init__(self, data_dir, *, kernel32=None, user32=None, is_windows=None,
                 log=None, pid=None, mutex_name: str = MUTEX_NAME,
                 timeout_s: float = SIGNAL_TIMEOUT_S):
        self.port_file = Path(data_dir) / PORT_FILE_NAME
        self._kernel32 = kernel32
        self._user32 = user32
        self._is_windows = (os.name == "nt") if is_windows is None else bool(is_windows)
        self._log = log or _stderr_log
        self._pid = int(pid if pid is not None else os.getpid())
        self._mutex_name = mutex_name
        self._timeout_s = float(timeout_s)
        self._handle = None
        self._token = ""
        self._sock = None
        self._thread = None
        self._stop = threading.Event()
        self._closed = False
        self.role = None
        self.port = None

    # ---------- 判定 ----------
    def acquire(self) -> str:
        """FIRST / SECOND / UNGUARDED。任何异常都当 UNGUARDED（放行），绝不抛。"""
        if not self._is_windows:
            self.role = UNGUARDED
            return self.role
        try:
            if self._kernel32 is None:
                self._kernel32 = _Kernel32()
            handle, last_error = self._kernel32.create_mutex(self._mutex_name)
        except Exception as exc:  # noqa: BLE001 - 守卫出错不挡唯一一份启动
            self._log("建互斥量出错，照常启动：%s" % type(exc).__name__)
            self.role = UNGUARDED
            return self.role
        if not handle:
            self._log("建互斥量失败（错误码 %s），照常启动" % last_error)
            self.role = UNGUARDED
            return self.role
        if last_error == ERROR_ALREADY_EXISTS:
            # 拿到的是别人那把锁的句柄：立刻关掉，不占着
            self._close_handle(handle)
            self.role = SECOND
            return self.role
        self._handle = handle
        self.role = FIRST
        return self.role

    # ---------- 第一份：监听唤回 ----------
    def start_listener(self, on_activate) -> bool:
        """在 127.0.0.1 随机端口起监听并写端口文件；失败只记诊断、返回 False。"""
        if self.role != FIRST or self._sock is not None:
            return False
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((LOOPBACK, 0))
            sock.listen(4)
            sock.settimeout(ACCEPT_POLL_S)
            self.port = int(sock.getsockname()[1])
            self._token = secrets.token_hex(32)
            self._write_port_file()
        except Exception as exc:  # noqa: BLE001 - 起不来就当没有唤回，照常运行
            self._log("唤回监听没起来，照常运行：%s" % type(exc).__name__)
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
            self.port = None
            self._token = ""
            return False
        self._sock = sock
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, args=(sock, on_activate),
                                        name="single-instance", daemon=True)
        self._thread.start()
        return True

    def _write_port_file(self) -> None:
        payload = {"pid": self._pid, "port": self.port, "token": self._token}
        self.port_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.port_file.with_name(self.port_file.name + ".%d.tmp" % self._pid)
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        os.replace(tmp, self.port_file)

    def _serve(self, sock, on_activate) -> None:
        while not self._stop.is_set():
            try:
                conn, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break  # 监听已关
            try:
                accepted = self._handle_conn(conn)
            except Exception:  # noqa: BLE001 - 坏连接只丢掉，监听不能死
                accepted = False
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            if accepted and on_activate is not None:
                # 唤回放进单独线程：窗口还没显示时 show() 会等，不能卡住监听
                threading.Thread(target=self._run_activate, args=(on_activate,),
                                 name="single-instance-activate", daemon=True).start()

    def _run_activate(self, on_activate) -> None:
        try:
            on_activate()
        except Exception as exc:  # noqa: BLE001
            self._log("唤回窗口出错：%s" % type(exc).__name__)

    def _handle_conn(self, conn) -> bool:
        """读一行 JSON；op 与口令都对才回 ok。不对就直接关，不回任何内容。"""
        conn.settimeout(self._timeout_s)
        data = b""
        while b"\n" not in data and len(data) <= MAX_MESSAGE_BYTES:
            chunk = conn.recv(MAX_MESSAGE_BYTES)
            if not chunk:
                break
            data += chunk
        if len(data) > MAX_MESSAGE_BYTES:
            return False
        try:
            message = json.loads(data.split(b"\n", 1)[0].decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return False
        if not isinstance(message, dict) or message.get("op") != ACTIVATE:
            return False
        token = message.get("token")
        if not isinstance(token, str) or not self._token:
            return False
        if not hmac.compare_digest(token.encode("utf-8"), self._token.encode("utf-8")):
            return False
        conn.sendall(b"ok\n")
        return True

    def stop_listener(self) -> None:
        """窗口关了就先停监听：之后再开的那份连不上，会弹「工具已经开着」而不是白等。"""
        self._stop.set()
        sock, self._sock = self._sock, None
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=ACCEPT_POLL_S * 4)

    # ---------- 第二份：唤回第一份 ----------
    def signal_first(self) -> bool:
        """把「唤回」交给第一份；收到 ok 才算成功。任何失败返回 False，绝不抛。"""
        try:
            info = json.loads(self.port_file.read_text(encoding="utf-8"))
            port = int(info.get("port"))
            token = str(info.get("token") or "")
            pid = int(info.get("pid") or 0)
        except Exception:
            return False
        if not (0 < port < 65536) or not token:
            return False
        if pid > 0:
            # 第二份是用户刚双击起来的，手里有前台权；先让给第一份，它的 Activate 才能真把窗口顶到前面
            try:
                if self._user32 is None and self._is_windows:
                    self._user32 = _User32()
                if self._user32 is not None:
                    self._user32.allow_set_foreground(pid)
            except Exception:
                pass
        message = json.dumps({"op": ACTIVATE, "token": token}).encode("utf-8") + b"\n"
        try:
            with socket.create_connection((LOOPBACK, port), timeout=self._timeout_s) as conn:
                conn.settimeout(self._timeout_s)
                conn.sendall(message)
                reply = b""
                while b"\n" not in reply and len(reply) < 16:
                    chunk = conn.recv(16)
                    if not chunk:
                        break
                    reply += chunk
        except Exception:
            return False
        return reply.strip() == b"ok"

    def notify_already_running(self) -> None:
        """唤回不成：弹原生消息框告诉用户工具已经开着。弹不出来就写一句诊断。"""
        try:
            if self._user32 is None and self._is_windows:
                self._user32 = _User32()
            if self._user32 is not None:
                self._user32.message_box(MESSAGE_TEXT, MESSAGE_TITLE,
                                         MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND)
                return
        except Exception:
            pass
        self._log(MESSAGE_TEXT.replace("\n", " "))

    def hand_over(self) -> int:
        """第二份的全部动作：唤回成功就安静退出，不成就弹消息框再退出。恒返回 0。"""
        try:
            if not self.signal_first():
                self.notify_already_running()
        except Exception:  # noqa: BLE001 - 第二份无论如何都不起界面
            pass
        return 0

    # ---------- 收尾 ----------
    def close(self) -> None:
        """停监听、只删自己写的端口文件、放互斥量。可重复调用。"""
        if self._closed:
            return
        self._closed = True
        try:
            self.stop_listener()
        except Exception:
            pass
        if self._token:
            try:
                info = json.loads(self.port_file.read_text(encoding="utf-8"))
                mine = (isinstance(info, dict)
                        and hmac.compare_digest(str(info.get("token") or "").encode("utf-8"),
                                                self._token.encode("utf-8"))
                        and int(info.get("pid") or 0) == self._pid)
                if mine:
                    self.port_file.unlink()
            except Exception:
                pass
            self._token = ""
        handle, self._handle = self._handle, None
        if handle:
            self._close_handle(handle)

    def _close_handle(self, handle) -> None:
        try:
            if self._kernel32 is not None:
                self._kernel32.close_handle(handle)
        except Exception:
            pass
