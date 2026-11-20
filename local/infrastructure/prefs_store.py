# -*- coding: utf-8 -*-
"""ui.json 偏好存储适配器：跨进程短时锁 + 原子读-合并-写。

路径全部显式传入（调用方持有 PREFS 绑定），锁与写入原语可整体替换成测试桩。
「读-核验-写」必须串行，否则生命周期心跳的整份快照会覆盖用户刚存的筛选
（反之亦然）；拿不到跨进程锁宁可放弃本次写入，也不写回未核验的旧快照。

Windows 上还有第三种意外：替换目标文件时，只要别的句柄正以不带
FILE_SHARE_DELETE 的方式开着它（本进程无锁的 load_from、杀毒或索引服务都
可能），os.replace 会报拒绝访问。这类失败一律按「这次没写成」有界重试；
读当前偏好失败时更要放弃整次事务——拿空字典合并再写回，会把条款同意、
筛选、关窗偏好一次全冲掉。

@author Author
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import threading
import time
from pathlib import Path

# 进程内锁：同一进程里的生命周期线程与界面调用互斥
PREFS_LOCK = threading.Lock()
LOCK_TIMEOUT_S = 1.0      # 生命周期元数据：拿不到就放弃本次写入
SAVE_TIMEOUT_S = 3.0      # 用户偏好：给正在收尾的另一个进程留出时间

# 文件被占用时的重试节奏：首次立即，随后 5 次逐次加长，总等待约 0.5 秒。
# 只覆盖「刚被放开就成功」的短窗口；占用更久说明确实有别的东西在读，
# 让调用方按失败处理比把界面卡住更合适。
RETRY_DELAYS_S = (0.02, 0.05, 0.10, 0.15, 0.18)


class PrefsLockTimeout(RuntimeError):
    """同一偏好文件的跨进程短时锁在期限内没有拿到。"""


class PrefsReadError(RuntimeError):
    """读当前偏好失败（文件被占用或不可读）：本次事务必须放弃，不得写盘。"""


def load_from(path: Path) -> dict:
    """无锁读（界面与 bootstrap 用）：被占用时短暂重试，仍失败按空偏好显示。

    无锁读不写盘，返回空只影响这一次显示，不会覆盖任何东西；诊断只写
    异常类型，不带路径与内容。
    """
    last = None
    for delay in (0,) + RETRY_DELAYS_S:
        if delay:
            time.sleep(delay)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except PermissionError as exc:   # 文件被别的句柄占着：隔一会儿再试
            last = exc
            continue
        except Exception:
            return {}
    print("[prefs] 偏好文件被占用，本次按空偏好显示：%s" % type(last).__name__,
          file=sys.stderr)
    return {}


def load_for_update(path: Path, *, sleep=time.sleep) -> dict:
    """事务内读当前偏好：读不到就抛 PrefsReadError，绝不返回空字典冒充「没配过」。

    文件不存在返回空字典（首次保存）；坏 JSON 返回空字典（存量口径：由下一次
    写入覆盖）。其余 OSError（含文件被占用的 PermissionError）按与写入相同的
    节奏有界重试，仍失败就抛——调用方据此放弃整次事务。
    """
    last = None
    for delay in (0,) + RETRY_DELAYS_S:
        if delay:
            sleep(delay)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            return {}
        except OSError as exc:
            last = exc
            continue
    raise PrefsReadError("读不到当前偏好：%s" % type(last).__name__)


def atomic_write(path: Path, prefs: dict, *, sleep=time.sleep) -> None:
    """临时文件 + os.replace 原子落盘：断电/崩溃不留半个 ui.json。

    目录随写入确保（测试里 path 指向临时目录，不会碰到真实数据根）。
    os.replace 撞上文件占用（PermissionError）时有界重试：临时文件只写一次，
    重试只是再换一次名；全部失败先删临时文件再抛最后一次异常，不留半成品。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    last = None
    for delay in (0,) + RETRY_DELAYS_S:
        if delay:
            sleep(delay)
        try:
            os.replace(tmp, path)
            return
        except PermissionError as exc:      # 目标正被别的句柄开着：隔一会儿再换
            last = exc
            continue
    try:
        tmp.unlink()
    except OSError:
        pass
    raise last


def acquire_file_lock(handle, timeout_s: float) -> None:
    """给已打开的锁文件加排他锁（标准库：Windows msvcrt / POSIX fcntl）。

    只用 1 字节区域锁表达「正在读-核验-写」；不写入业务内容，也不依赖锁文件
    内容本身。轮询而非阻塞，才能在窗口关闭路径上有界放弃。
    """
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    if sys.platform == "win32":
        import msvcrt
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")        # 区域锁需要文件里至少有一个字节
            handle.flush()
        while True:
            try:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise PrefsLockTimeout("偏好文件正被另一个进程写入")
                time.sleep(0.005)
    else:
        import fcntl
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise PrefsLockTimeout("偏好文件正被另一个进程写入")
                time.sleep(0.005)


def release_file_lock(handle) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextlib.contextmanager
def prefs_transaction(path: Path, *, timeout_s: float = LOCK_TIMEOUT_S):
    """同一 prefs 路径的进程内 + 跨进程短时排他事务。

    进程内沿用 PREFS_LOCK；跨进程用与 ui.json 同目录的 ``ui.json.lock`` 区域锁。
    事务只覆盖「读-核验-合并-原子写」，调用方不得持锁联网或等待子进程。
    拿不到跨进程锁时抛 PrefsLockTimeout：宁可放弃这次元数据写入，也不写回
    一份未核验归属的旧快照。
    """
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    if not PREFS_LOCK.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise PrefsLockTimeout("偏好文件正在写入")
    try:
        lock_path = Path(str(path) + ".lock")
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, "a+b")
        except OSError:
            raise PrefsLockTimeout("偏好锁文件不可创建")
        try:
            acquire_file_lock(handle, max(0.0, deadline - time.monotonic()))
            try:
                yield
            finally:
                release_file_lock(handle)
        finally:
            handle.close()
    finally:
        PREFS_LOCK.release()


def update(path: Path, patch: dict, *, load=None, write=None, transaction=None) -> bool:
    """统一的原子读-合并-写；任何失败都返回 False，绝不把异常抛给调用方。

    绕过文件锁写入会覆盖另一个实例刚保存的周期。调用方可重试用户偏好；
    可选登录估算落盘失败也不影响真实登录成功。

    读用严格读：读不到当前偏好就放弃整次事务（返回 False、一个字节都不写），
    免得拿空字典合并再写回、把用户的条款同意与筛选一次冲掉。

    load / write / transaction 可由组合根注入：`app.update_prefs` 把它们换成
    app 模块上的同名封装，测试按 app.X 打的补丁才照样生效。load 不带参数。
    """
    load = load or (lambda: load_for_update(path))
    write = write or atomic_write
    transaction = transaction or prefs_transaction
    try:
        with transaction(path, timeout_s=SAVE_TIMEOUT_S):
            prefs = load()
            prefs.update(patch or {})
            write(path, prefs)
        return True
    except (PrefsLockTimeout, PrefsReadError, OSError):
        return False
