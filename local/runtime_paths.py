#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""登录态与偏好文件的统一数据根：开发/绿色版与冻结 EXE 共用同一套口径。

- 开发与绿色版：沿用脚本旁边的 data/（local/data、便携目录 data），语义不变；
- 冻结主程序与 grab-worker.exe：默认 %LOCALAPPDATA%/TianSoftActivityPreRegistration/data，
  同一台机器上关闭重开、替换 EXE 或重建 EXE 后仍复用同一份登录态；
- 环境变量 CAMPUS_DATA_DIR 可覆盖（相对路径先 resolve），便于测试与高级用户迁移；
- 冻结进程首次使用新数据根时，把旧 EXE 旁 data 里的会话/偏好文件原子搬过来：
  只补缺失、绝不覆盖目标已有文件，也不读取或改写 token 内容。

@author Author
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

from infrastructure.prefs_store import (PrefsLockTimeout, acquire_file_lock,
                                        release_file_lock)

# 统一数据根的应用目录名（%LOCALAPPDATA% 下）
APP_DIR_NAME = "TianSoftActivityPreRegistration"
# 迁移白名单：登录态与偏好；grab.log 只在缺失时一并带走，方便排查
MIGRATE_FILES = ("session.json", "storage_state.json", "ui.json", "grab.log")
# 失败时归入「登录信息」一类的文件；其余归入「设置或运行记录」
LOGIN_FILES = ("session.json", "storage_state.json")

# 本次进程启动时的迁移结果（BE3；MG01 原型 Main:2146 / MG02 原型 Main:2147）：
# None=没发生迁移；{"moved": int, "login_failed": bool, "other_failed": bool} 由 _migrate_legacy_data
# 只写一次。界面 bootstrap 只读它，不另存状态、不再读 stderr 去猜。
_MIGRATION_RECORD: dict | None = None
# 本进程的旧数据迁移是否已有结论（G1）：grab.log() 每写一行都会走 ensure_data_dir，
# 冻结态下若每次都重新迁移，报名开放那一刻每行日志都要排队拿迁移锁和日志锁。
# 只在「完整跑完一次」或「确定无需迁移」后置位；等锁超时（对方正在迁移）不置位，下次再试。
_MIGRATION_DONE = False


def migration_record() -> dict | None:
    """只读取值：本次进程的旧数据迁移结果；没发生迁移返回 None。

    返回副本，调用方改不动模块里的记录（记录只写一次，迁移不再重跑）。
    """
    record = _MIGRATION_RECORD
    return dict(record) if record else None


def _base_dir() -> Path:
    """解析本进程的数据根（只算路径，不创建目录）。"""
    override = os.environ.get("CAMPUS_DATA_DIR", "").strip()
    if override:
        # 相对路径锚定当前工作目录，避免冻结进程拿到一个随启动目录漂移的根
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA", "").strip()
        # LOCALAPPDATA 缺失（精简系统/服务账户）时回退 home/AppData/Local
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_DIR_NAME / "data"
    return Path(__file__).resolve().parent / "data"


DATA_DIR = _base_dir()
SESSION_FILE = DATA_DIR / "session.json"
STATE_FILE = DATA_DIR / "storage_state.json"
UI_STATE_FILE = DATA_DIR / "ui.json"
LOG_FILE = DATA_DIR / "grab.log"
# 日志轮转与追加共用的跨进程锁；与 session.json.lock 分开，日志不占登录态写锁
LOG_LOCK_FILE = DATA_DIR / "grab.log.lock"
# 旧数据迁移的跨进程锁：两个 GUI 同时首次启动时只能有一个在搬文件
MIGRATION_LOCK_FILE = DATA_DIR / "migration.lock"
MIGRATION_LOCK_TIMEOUT_S = 5.0


def ensure_data_dir() -> Path:
    """确保数据根存在；冻结进程首次使用新根时顺带完成旧数据迁移。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # 迁移以进程为单位只做一次：有结论后日志热路径只剩一次 mkdir(exist_ok)
    if getattr(sys, "frozen", False) and not _MIGRATION_DONE:
        _migrate_legacy_data()
    return DATA_DIR


def _legacy_data_dir() -> Path:
    """统一数据根之前的老位置：EXE 旁边的 data/。"""
    return Path(sys.executable).resolve().parent / "data"


def _migrate_legacy_data() -> None:
    """旧 EXE 旁 data → 统一数据根：只补缺失文件，临时文件 + os.replace 原子落位。

    任何失败都不阻断启动（打印一句可读提示）——迁移丢了还能手动拷贝，
    启动失败才是真问题。绝不覆盖目标已有文件，避免旧数据倒灌新数据。
    结果同时记进 _MIGRATION_RECORD（BE3），供界面横幅与运行记录读取。
    G1：拿到锁并完整跑完、或确定无需迁移（旧目录就是数据根）、或失败已有定论时置位
    _MIGRATION_DONE，本进程不再重复；等锁超时是「对方正在搬」，既不置位也不写记录。
    """
    global _MIGRATION_RECORD, _MIGRATION_DONE
    legacy = _legacy_data_dir()
    moved = 0
    login_failed = False
    other_failed = False
    try:
        if legacy.resolve() == DATA_DIR.resolve():
            # 旧目录就是数据根：没有需要搬的东西，这个结论本进程内不会变
            _MIGRATION_DONE = True
            return
    except Exception as exc:  # noqa: BLE001 - 迁移是尽力而为，不让它挡住启动
        print("[!] 旧数据迁移失败（不影响启动，可手动拷贝）：%s" % exc, file=sys.stderr)
        _MIGRATION_RECORD = {"moved": 0, "login_failed": True, "other_failed": True}
        # 路径都算不出来：再试也是同一个结果，别让每行日志都重复打这句提示
        _MIGRATION_DONE = True
        return
    # 迁移是跨进程的一次性动作：两个 GUI 同时首次启动时，后到者必须等前者
    # 收工后再检查目标，否则会把对方刚写入的新登录态当成缺失、再拿旧文件覆盖。
    try:
        lock_handle = open(MIGRATION_LOCK_FILE, "a+b")
    except OSError as exc:
        print("[!] 旧数据迁移失败（不影响启动，可手动拷贝）：%s" % exc, file=sys.stderr)
        _MIGRATION_RECORD = {"moved": 0, "login_failed": True, "other_failed": True}
        # 迁移锁文件都建不出来（权限/只读）：这是本机环境的定论，不逐行重试
        _MIGRATION_DONE = True
        return
    acquired = False
    try:
        try:
            acquire_file_lock(lock_handle, MIGRATION_LOCK_TIMEOUT_S)
            acquired = True
        except (PrefsLockTimeout, OSError) as exc:
            # G3：等锁超时说明另一个实例正在搬（多半已经搬完），本次没有迁移结论。
            # 不写 _MIGRATION_RECORD：写成 login_failed 会让界面横幅误报「旧登录信息
            # 没搬过来」；也不置位 _MIGRATION_DONE，下次 ensure_data_dir 拿到锁再检查。
            print("[!] 旧数据迁移暂缓（不影响启动）：另一个进程正在迁移（%s）"
                  % type(exc).__name__, file=sys.stderr)
            return
        for name in MIGRATE_FILES:
            # 每个文件单独 try：一个失败不影响其余文件继续搬
            try:
                source = legacy / name
                target = DATA_DIR / name
                if not source.is_file() or target.exists():
                    continue
                # 先拷成数据根同盘的临时文件再原子替换：中途断电不会留下半个文件
                handle, temp_name = tempfile.mkstemp(dir=str(DATA_DIR),
                                                     prefix=name + ".", suffix=".tmp")
                os.close(handle)
                try:
                    shutil.copy2(source, temp_name)
                    os.replace(temp_name, target)
                    moved += 1
                finally:
                    Path(temp_name).unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001 - 迁移是尽力而为，不让它挡住启动
                is_login = name in LOGIN_FILES
                print("[!] 旧%s没能搬过来（不影响启动，可手动拷贝）：%s"
                      % ("登录信息" if is_login else "设置或运行记录", exc), file=sys.stderr)
                if is_login:
                    login_failed = True
                else:
                    other_failed = True
        if moved:
            print("[i] 已把 %d 个旧数据文件搬到统一数据目录：%s" % (moved, DATA_DIR),
                  file=sys.stderr)
        if moved or login_failed or other_failed:
            # MG02（原型 Main:2147）：失败原因不给界面看原文（可能带本机路径），
            # 只给「哪一类没搬过来」
            _MIGRATION_RECORD = {"moved": moved, "login_failed": login_failed,
                                 "other_failed": other_failed}
        # 完整跑完一次（含部分文件失败）：结论已记进 _MIGRATION_RECORD，本进程不再重复
        _MIGRATION_DONE = True
    finally:
        if acquired:
            release_file_lock(lock_handle)
        lock_handle.close()
