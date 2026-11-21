# -*- coding: utf-8 -*-
"""worker 日志层：文件锁、轮转、stderr 降级出口、stdout 改道与追加写入。

日志路径、上限参数、业务时钟和跨进程锁文件均在每次调用时经端口传入，
保证测试对 `grab.LOG_FILE`、`grab.rotate_log_file` 等替身仍照旧生效；
进程内日志线程锁 `_LOG_THREAD_LOCK` 在本模块与 `grab` 之间只保有一份实例。

@author Author
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

from infrastructure.prefs_store import (
    PrefsLockTimeout,
    acquire_file_lock,
    release_file_lock,
)

# 唯一一把进程内日志线程锁；grab.py 以原名引用同一对象，禁止两处各建一把。
_LOG_THREAD_LOCK = threading.Lock()


@contextlib.contextmanager
def log_file_lock(*, timeout_s: float, log_lock_file, time_mod,
                  thread_lock=_LOG_THREAD_LOCK):
    """grab.log 的轮转与追加共用的跨进程锁。

    界面进程与 worker 打开同一个 grab.log.lock：轮转时不会把对方刚写的行挪走，
    追加也不会落在轮转中间。拿不到锁抛 PrefsLockTimeout，由 log() 降级处理。
    """
    deadline = time_mod.monotonic() + max(0.0, float(timeout_s))
    if not thread_lock.acquire(timeout=max(0.0, deadline - time_mod.monotonic())):
        raise PrefsLockTimeout("日志正在被本进程另一线程写入")
    try:
        try:
            Path(log_lock_file).parent.mkdir(parents=True, exist_ok=True)
            handle = open(log_lock_file, "a+b")
        except OSError:
            raise PrefsLockTimeout("日志锁文件不可创建")
        acquired = False
        try:
            acquire_file_lock(handle, max(0.0, deadline - time_mod.monotonic()))
            acquired = True
            yield
        finally:
            if acquired:
                release_file_lock(handle)
            handle.close()
    finally:
        thread_lock.release()


def rotate_log_file(path, max_bytes=None, keep=None, *,
                    default_max_bytes: int, default_keep: int) -> bool:
    """日志超过 max_bytes 就轮转：path → path.1，旧的依次后移，path.keep 之后的丢掉。

    只用标准库的重命名。返回是否轮转了；失败（文件被另一个进程占着等）原样抛出，
    由 log() 兜住——轮转失败不能让这一行日志也丢了。
    """
    path = Path(path)
    limit = default_max_bytes if max_bytes is None else max_bytes
    count = default_keep if keep is None else keep
    try:
        if path.stat().st_size < limit:
            return False
    except FileNotFoundError:
        return False
    oldest = path.with_name("%s.%d" % (path.name, count))
    if oldest.exists():
        oldest.unlink()
    for index in range(count - 1, 0, -1):
        older = path.with_name("%s.%d" % (path.name, index))
        if older.exists():
            os.replace(older, path.with_name("%s.%d" % (path.name, index + 1)))
    os.replace(path, path.with_name(path.name + ".1"))
    return True


def stderr_note(text) -> None:
    """写日志自己出了问题时的出口：至少打到 stderr（无控制台的打包形态里 stderr 可能是 None）。"""
    stream = sys.stderr
    if stream is None:
        return
    try:
        print(text, file=stream, flush=True)
    except Exception:
        pass


@contextlib.contextmanager
def stdout_to_stderr(enabled):
    """--json 的 stdout 是给主程序 json.loads 的：log() 等辅助函数会往 stdout
    打印，这段时间必须把 stdout 改道到 stderr（无控制台的打包形态里 stderr
    可能是 None，此时丢到系统空设备），否则 JSON 前面多一行，整张列表解析失败。"""
    if not enabled:
        yield
        return
    stream = sys.stderr
    devnull = None
    if stream is None:
        devnull = open(os.devnull, "w", encoding="utf-8")
        stream = devnull
    try:
        with contextlib.redirect_stdout(stream):
            yield
    finally:
        if devnull is not None:
            devnull.close()


def append_log_line_unlocked(line, *, log_file, note_fn) -> None:
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as exc:  # noqa: BLE001 - 不再静默：至少让控制台看到这一行没落盘
        note_fn("[log] 写日志文件失败（%s）：%s" % (type(exc).__name__, line))


def write_log(msg, *, ensure_dir_fn, school_time_text_fn, business_now_fn,
              lock_ctx_fn, rotate_fn, log_file, append_fn, note_fn) -> None:
    """写一行带北京时间戳的运行日志：按临界区先后确保目录、持锁轮转并追加、打印标准输出。"""
    try:
        ensure_dir_fn()
    except Exception as exc:  # noqa: BLE001 - 数据目录建不出来也要把这一行打出去
        note_fn("[log] 数据目录不可用（%s）" % type(exc).__name__)
    try:
        # 日志时间按北京时间（业务时钟）；时钟未配置时保留旧本机戳以免崩溃
        stamp = school_time_text_fn(now_fn=business_now_fn)
    except Exception:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = "%s %s" % (stamp, msg)
    try:
        with lock_ctx_fn():
            # 轮转与追加在同一临界区：另一个进程不会读到挪到一半的日志
            try:
                rotate_fn(log_file)
            except Exception as exc:  # noqa: BLE001 - 轮转失败下次写入再试，不丢这一行
                note_fn("[log] 日志轮转失败（%s）" % type(exc).__name__)
            append_fn(line)
    except PrefsLockTimeout:
        # 另一个进程正占着日志锁：不能无锁追加，当前行只走 stderr/控制台降级。
        note_fn("[log] 没拿到日志文件锁，本次跳过轮转")
        note_fn("[log] 当前行未写入 grab.log：%s" % line)
    print(line, flush=True)
