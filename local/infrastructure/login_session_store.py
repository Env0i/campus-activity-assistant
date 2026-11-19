# -*- coding: utf-8 -*-
"""登录态落盘：session.json / storage_state.json 的唯一写入入口。

界面进程、命令行和 worker 子进程共用 data 下的这两个文件，所以写登录态只有
这一条路：进程内线程锁 + 登录态文件旁的跨进程区域锁（session.json.lock）。
读取不加锁——读到的要么是旧文件要么是新文件，不会是半截。

锁序固定为「线程锁 → 跨进程区域锁」，同一个 timeout 预算在两层之间递减分配，
解锁顺序反过来。单写是「临时文件 + os.replace」；双写先把两份内容都写成临时
文件，再取旧字节，再按 state、session 的顺序替换。第二份替换失败时只回滚已经
落位的文件，没落位的保持原状；回滚本身失败也不能盖掉最初那个异常——调用方要
看到的是真正的失败原因。回滚诊断只写 stderr：stdout 是 worker 协议。
不承诺跨文件断电原子性，也不另写备份文件。

路径与日志端口全部由调用方传入（生产里是 grab 在调用时解析数据根并把 log 传
进来）。本模块不 import grab、runtime_paths 或 local 根模块：测试可以直接换
路径、换日志端口，也可以换掉写文件的 open 原语。

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

# 登录态写锁的加解锁原语沿用 ui.json.lock 那一对（标准库实现，S5）
from infrastructure.prefs_store import (PrefsLockTimeout, acquire_file_lock,
                                        release_file_lock)

SESSION_LOCK_TIMEOUT_S = 5.0
_SESSION_THREAD_LOCK = threading.Lock()


@contextlib.contextmanager
def session_write_lock(session_path, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录态写锁：拿不到抛 PrefsLockTimeout，由调用方决定怎么放弃。

    锁文件放在登录态文件旁（session.json.lock）；state 与 session 两个文件
    共用这一把锁，所以成对落位时不会被另一个写入者插进来。
    """
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    if not _SESSION_THREAD_LOCK.acquire(timeout=max(0.0, deadline - time.monotonic())):
        raise PrefsLockTimeout("登录态正在被本进程另一线程写入")
    try:
        lock_path = Path(str(session_path) + ".lock")
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            handle = open(lock_path, "a+b")
        except OSError:
            raise PrefsLockTimeout("登录态锁文件不可创建")
        try:
            acquire_file_lock(handle, max(0.0, deadline - time.monotonic()))
            try:
                yield
            finally:
                release_file_lock(handle)
        finally:
            handle.close()
    finally:
        _SESSION_THREAD_LOCK.release()


def write_json_atomic(path, obj):
    """临时文件 + os.replace 原子写一份 JSON；非 Windows 仍把权限收成 600。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    if os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass


def _write_login_file(target, obj, session_path, log, timeout_s):
    """在登录态写锁内原子写一份 JSON；超时写日志并放弃，返回是否写成。"""
    try:
        with session_write_lock(session_path, timeout_s):
            write_json_atomic(target, obj)
        return True
    except PrefsLockTimeout:
        log("[X] %s 没写成：%d 秒内没拿到登录态写锁（另一个进程正在写）"
            % (Path(target).name, int(timeout_s)))
        return False


def save_session(session, path, log, timeout_s=SESSION_LOCK_TIMEOUT_S):
    """登录态 session.json 的唯一写入口；拿不到锁最多等 timeout_s 秒，
    超时写日志并放弃这次写入（返回 False，不抛异常）。"""
    target = Path(path)
    return _write_login_file(target, session, target, log, timeout_s)


def save_storage_state(state, path, session_path, log,
                       timeout_s=SESSION_LOCK_TIMEOUT_S):
    """浏览器 cookie 文件（storage_state.json）：和 session.json 共用同一把写锁。"""
    return _write_login_file(Path(path), state, Path(session_path), log, timeout_s)


def save_verified_files(state, session, state_path, session_path, log,
                        timeout_s=SESSION_LOCK_TIMEOUT_S, opener=open):
    """登录成功后 state+session 双文件事务保存（HTTP 路径 save_verified 端口）。

    整笔事务在登录态写锁内进行（见 save_session）；拿不到锁抛 OSError，
    调用方（登录中继）按「持久化失败」处理，不会报告成功。
    opener 只换「写文件用哪个 open」这一个原语，替身测试靠它模拟写失败。
    """
    try:
        with session_write_lock(Path(session_path), timeout_s):
            _save_verified_files_locked(state, session, state_path, session_path, opener)
    except PrefsLockTimeout:
        log("[X] 登录态没写成：%d 秒内没拿到写锁（另一个进程正在写）" % int(timeout_s))
        raise OSError("登录态写入超时")


def _save_verified_files_locked(state, session, state_path, session_path, opener):
    """save_verified_files 的事务本体（调用方已持有写锁）。

    两份内容先写好临时文件再依次替换；第二文件替换失败时把已落位的文件恢复
    到保存前的原始字节或删除回不存在，未落位文件保持原状，两文件最终回到
    保存前状态。只覆盖正常异常下的回滚，不承诺跨文件断电原子性；回滚用的
    存量字节只在运行时读入内存，不另写备份文件。
    """
    targets = [(Path(state_path), state), (Path(session_path), session)]
    prepared = []
    try:
        for path, obj in targets:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with opener(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=2)
            prepared.append((path, tmp))
    except Exception:
        for _path, tmp in prepared:
            _unlink_quiet(tmp)
        raise
    originals = {}
    replaced = []
    try:
        for path, _tmp in prepared:
            originals[path] = _snapshot_bytes(path, opener)
        for path, tmp in prepared:
            os.replace(tmp, path)
            replaced.append(path)
    except Exception:
        for _path, tmp in prepared:
            _unlink_quiet(tmp)
        # 每个已落位的文件各自尽力恢复：一个恢复失败不能让另一个也留成新内容，
        # 更不能让回滚的异常盖掉最初那个异常（调用方要看到的是真正的失败原因）
        for path in replaced:
            _restore_original(path, originals.get(path), opener)
        raise


def _snapshot_bytes(path, opener=open):
    """保存前存量字节；原本不存在回 None，存在但读不出则抛错（先不动盘）。"""
    try:
        with opener(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _unlink_quiet(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


def _restore_original(path, blob, opener=open):
    """把已落位的文件恢复成保存前的字节（None 表示原本不存在）；失败只写 stderr。

    先走临时文件加替换；替换不成再原地覆盖写回。stdout 是 worker 协议，
    回滚诊断不能打到那里，也不记任何登录态内容，只留文件名和异常类型。
    """
    if blob is None:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            _rollback_note(path, exc)
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with opener(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, path)
        return
    except Exception:  # noqa: BLE001 - 换位不成就退到原地覆盖
        _unlink_quiet(tmp)
    try:
        with opener(path, "wb") as f:
            f.write(blob)
    except Exception as exc:  # noqa: BLE001
        _rollback_note(path, exc)


def _rollback_note(path, exc):
    try:
        sys.stderr.write("[X] 登录态回滚没成功：%s 可能还是新内容（%s）\n"
                         % (Path(path).name, type(exc).__name__))
        sys.stderr.flush()
    except Exception:
        pass
