"""版本目录切换与当前版本启动桥接。

该模块只处理已准备好的 staging 目录，不下载、不解压，也不触碰数据目录。
切换顺序保证 current.json 写失败时旧版本和 staging 都能保留。
"""
from __future__ import annotations

import json
import os
import re
import argparse
import shutil
import subprocess
import sys
import time
import ctypes
import uuid
from pathlib import Path
from typing import Callable


_VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_EXE_NAME = "campus-activity-watch.exe"
# Win32 常量：OpenProcess 在 PID 不存在时失败，GetLastError 为 87。
_ERROR_INVALID_PARAMETER = 87
# 等主程序退出的默认时限：用户点「重启并切换版本」后可能还要先收尾计划、
# 确认关窗，30 秒经常不够，超时就整轮作废（启动器无窗口，用户看不到原因）。
DEFAULT_WAIT_TIMEOUT_S = 120.0


def _current_path(path: os.PathLike | str) -> Path:
    candidate = Path(path)
    return candidate / "current.json" if candidate.is_dir() else candidate


def read_current(path: os.PathLike | str) -> dict:
    """读取并校验 current.json，缺失或内容不合法时抛出 ValueError。"""
    current = _current_path(path)
    try:
        payload = json.loads(current.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("current.json 无效") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("version"), str):
        raise ValueError("current.json 缺少版本")
    version = payload["version"]
    if not _VERSION_RE.fullmatch(version):
        raise ValueError("current.json 版本无效")
    return payload


def _contained(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_version_dir(version_root: os.PathLike | str, version: str) -> Path:
    """返回安全的版本目录，并确认其中存在固定名称的可执行文件。"""
    if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
        raise ValueError("版本无效")
    root = Path(version_root)
    target = root / version
    if not _contained(root, target) or target.is_symlink() or not target.is_dir():
        raise ValueError("版本目录无效")
    return _check_exe(target)


def _check_exe(target: Path) -> Path:
    """目录里必须有固定名称的可执行文件（不是链接、不越界）。"""
    exe = target / _EXE_NAME
    if not _contained(target, exe) or exe.is_symlink() or not exe.is_file():
        raise ValueError("版本目录缺少固定程序")
    return target


def _version_key(version: str) -> tuple:
    return tuple(int(part) for part in version.split("."))


def _greatest_valid_version(version_root: Path, skip=()) -> str:
    """版本目录下版本号最大的有效目录；没有返回空串。"""
    try:
        names = [item.name for item in version_root.iterdir()]
    except OSError:
        return ""
    for name in sorted((n for n in names if _VERSION_RE.fullmatch(n) and n not in skip),
                       key=_version_key, reverse=True):
        try:
            validate_version_dir(version_root, name)
        except ValueError:
            continue
        return name
    return ""


def launch_current(version_root: os.PathLike | str, *, current_file=None,
                   launcher: Callable[[str], object] | None = None) -> dict:
    """按 current.json 启动当前版本的固定 exe；当前版本不可用时自动回退。

    回退顺序：current.json 的 version → 它记的 previous_version → 版本号最大的
    有效目录。只读磁盘，不改写 current.json：回退只是这一次能启动，下次切换
    成功时 current.json 会被重写成合法内容。三者都不可用才抛 ValueError，
    磁盘上的版本目录一概不动。
    """
    root = Path(version_root)
    current_path = _current_path(current_file or root.parent / "current.json")
    if not _contained(root.parent, current_path):
        raise ValueError("current.json 路径越界")
    try:
        payload = read_current(current_path)
    except ValueError:
        payload = {}   # current.json 缺失或损坏：直接找最大的有效版本
    tried = []
    chosen, how = "", ""
    previous = payload.get("previous_version")
    for version, source in ((payload.get("version"), ""),
                            (previous if isinstance(previous, str) else "",
                             "previous_version")):
        if not isinstance(version, str) or not _VERSION_RE.fullmatch(version):
            continue
        tried.append(version)
        try:
            validate_version_dir(root, version)
        except ValueError:
            continue
        chosen, how = version, source
        break
    if not chosen:
        chosen, how = _greatest_valid_version(root, skip=tried), "latest_valid"
    if not chosen:
        raise ValueError("当前版本不可用，也没有可回退的有效版本。")
    exe = root / chosen / _EXE_NAME
    (launcher or os.startfile)(str(exe))
    result = {"ok": True, "version": chosen, "path": str(exe)}
    if how:
        result["fallback"] = how
    return result


def _atomic_current(path: Path, payload: dict) -> None:
    """优先复用 updater 的原子写实现，便于旧调用方注入失败；否则本地完成。

    本地实现：同目录临时文件写完 flush + fsync 再 os.replace。任何一步失败，
    磁盘上只可能是旧 current.json 加一个会被清掉的临时文件，不会出现半份内容。
    """
    try:
        from . import updater
    except ImportError:
        updater = None
    writer = getattr(updater, "_atomic_write_json", None)
    if writer is not None:
        writer(path, payload)
        return
    part = path.with_name(path.name + ".part-" + uuid.uuid4().hex)
    try:
        with part.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.flush()
            os.fsync(handle.fileno())   # 断电后不能留下空的 current.json
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def _discard(path: Path) -> None:
    """删掉被换下来的旧目录；删不掉不报错（残留由主程序启动后的清理收走）。"""
    try:
        if path.is_symlink() or path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def apply_staged(staging: os.PathLike | str, version_root: os.PathLike | str,
                 target_version: str, current_file=None, *, parent_pid=None,
                 wait_fn: Callable[[int, float], dict] | None = None,
                 wait_parent: Callable[[int, float], dict] | None = None,
                 wait_timeout_s: float = 10, launcher=None) -> dict:
    """等待父进程退出后，将 staging 原子切换为版本并启动；失败保留旧状态。"""
    if not isinstance(target_version, str) or not _VERSION_RE.fullmatch(target_version):
        return {"ok": False, "error_code": "invalid_version", "text": "目标版本无效。"}
    root = Path(version_root)
    source = Path(staging)
    current = _current_path(current_file or root.parent / "current.json")
    if not _contained(root.parent, current):
        return {"ok": False, "error_code": "switch_failed", "text": "current.json 路径越界。"}
    if not source.is_dir() or source.is_symlink() or not _contained(root.parent, source):
        return {"ok": False, "error_code": "switch_failed", "text": "staging 目录无效。"}
    target = root / target_version
    if not _contained(root, target):
        return {"ok": False, "error_code": "switch_failed", "text": "目标版本目录无效。"}
    # staging 缺固定程序时不切换：磁盘上 current.json 与所有版本目录原样不动，
    # staging 也留着，用户看到的是旧版本照常可用。
    try:
        _check_exe(source)
    except ValueError:
        return {"ok": False, "error_code": "switch_failed",
                "text": "更新包缺少程序文件，已保留当前版本。"}
    waiter = wait_fn or wait_parent
    if parent_pid is not None and waiter is not None:
        waited = waiter(parent_pid, wait_timeout_s)
        if isinstance(waited, dict) and not waited.get("ok"):
            return waited
    previous = ""
    backup = None
    try:
        if current.is_file():
            try:
                prior = read_current(current)
            except ValueError:
                prior = {}   # current.json 已损坏：本次切换会把它重写成合法内容
            previous = prior.get("version") or ""
            if previous == target_version:
                # 重装同一版本：上一版仍是更早的那个，不能把自己记成上一版
                previous = prior.get("previous_version") or ""
        root.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(target):
            # 崩溃残留或重装旧版后再升级：目标目录已存在。先让到 .old-* 旁边，
            # 切换成功再删；失败就改回来，不让每次重试都静默失败。
            backup = root / (".old-%s-%s" % (target_version, uuid.uuid4().hex[:8]))
            os.replace(target, backup)
        os.replace(source, target)
        payload = {"version": target_version}
        if previous and _VERSION_RE.fullmatch(previous):
            payload["previous_version"] = previous
        _atomic_current(current, payload)
    except Exception as exc:  # noqa: BLE001 - 切换失败必须恢复 staging 和被让开的旧目录
        # 失败后的磁盘状态：staging 回到原处；原来的目标目录（若有）回到原名；
        # current.json 还是旧内容。用户下次启动仍是切换前的版本。
        if os.path.lexists(target) and not source.exists():
            try:
                os.replace(target, source)
            except OSError:
                pass
        if backup is not None and os.path.lexists(backup) and not os.path.lexists(target):
            try:
                os.replace(backup, target)
            except OSError:
                pass
        return {"ok": False, "error_code": "switch_failed", "text": str(exc) or "版本切换失败。"}
    if backup is not None:
        _discard(backup)
    launched = validate_version_dir(root, target_version)
    if launcher is not None:
        launcher(str(launched / _EXE_NAME))
    return {"ok": True, "version": target_version,
            "previous_version": previous or "", "path": str(launched)}


def apply_and_launch(*args, **kwargs):
    """兼容旧调用名。"""
    if len(args) >= 2:
        args = (args[1], args[0], *args[2:])
    else:
        # 旧调用方通常使用关键字；关键字名称本身无需调整。
        version_root = kwargs.pop("version_root")
        staging = kwargs.pop("staging")
        return apply_staged(staging, version_root, **kwargs)
    return apply_staged(*args, **kwargs)


def _load_kernel32():
    """加载带完整函数原型的 kernel32：句柄在 64 位下是指针宽度，缺原型会被截断。

    GetLastError 用 ctypes.get_last_error（配合 use_last_error=True），
    否则两次调用之间错误码可能已被别的调用覆盖。
    """
    import types
    from ctypes import wintypes
    lib = ctypes.WinDLL("kernel32", use_last_error=True)
    lib.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    lib.OpenProcess.restype = wintypes.HANDLE
    lib.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    lib.WaitForSingleObject.restype = wintypes.DWORD
    lib.CloseHandle.argtypes = [wintypes.HANDLE]
    lib.CloseHandle.restype = wintypes.BOOL
    return types.SimpleNamespace(
        OpenProcess=lib.OpenProcess, WaitForSingleObject=lib.WaitForSingleObject,
        CloseHandle=lib.CloseHandle, GetLastError=ctypes.get_last_error)


def _wait_parent_windows(pid: int, timeout_s: float, kernel32) -> dict:
    """Windows 句柄等待；kernel32 由调用方注入，测试用替身，不碰真实进程。

    OpenProcess 失败且 GetLastError 为 87（参数无效）说明这个 PID 已经不存在，
    也就是主程序已经退出，可以切换；其他原因（如拒绝访问）无法确认主程序已退出，
    仍然报失败，不误切换。
    """
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0
    WAIT_TIMEOUT = 0x102
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                                  False, pid)
    if not handle:
        if kernel32.GetLastError() == _ERROR_INVALID_PARAMETER:
            return {"ok": True}
        return {"ok": False, "error_code": "parent_wait_failed",
                "text": "无法等待父进程退出。"}
    try:
        # DWORD 毫秒数，0xFFFFFFFF 是无限等待，留一格不用
        result = kernel32.WaitForSingleObject(handle, min(int(timeout_s * 1000), 0xFFFFFFFE))
    finally:
        kernel32.CloseHandle(handle)
    if result == WAIT_OBJECT_0:
        return {"ok": True}
    if result == WAIT_TIMEOUT:
        return {"ok": False, "error_code": "parent_timeout",
                "text": "等待主程序退出超时，已保留当前版本，请关闭本工具后重试。"}
    return {"ok": False, "error_code": "parent_wait_failed",
            "text": "等待父进程退出失败。"}


def wait_parent_process(pid: int, timeout_s: float) -> dict:
    """有界等待主程序退出；Windows 句柄失败返回可读错误，不误切换。"""
    try:
        pid = int(pid)
        timeout_s = max(0.0, float(timeout_s))
    except (TypeError, ValueError):
        return {"ok": False, "error_code": "parent_invalid", "text": "父进程参数无效。"}
    if pid <= 0:
        return {"ok": False, "error_code": "parent_invalid", "text": "父进程参数无效。"}
    if os.name == "nt":
        return _wait_parent_windows(pid, timeout_s, _load_kernel32())
    # 开发环境没有 Windows 句柄，使用 kill(0) 轮询保持同一有界语义。
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return {"ok": True}
        except PermissionError:
            return {"ok": False, "error_code": "parent_wait_failed",
                    "text": "没有权限等待父进程退出。"}
        if time.monotonic() >= deadline:
            return {"ok": False, "error_code": "parent_timeout",
                    "text": "等待主程序退出超时。"}
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


def _default_launcher(path: str) -> object:
    """启动固定版本 EXE；保留 os.startfile 以兼容 Windows 资源关联。"""
    if hasattr(os, "startfile"):
        return os.startfile(path)
    return subprocess.Popen([path], close_fds=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="校园活动预报名工具版本启动器")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--start", action="store_true",
                       help="按 current.json 启动当前版本")
    modes.add_argument("--apply", action="store_true",
                       help="等待父进程退出，切换 staging 并启动目标版本")
    parser.add_argument("--version-root", required=True)
    parser.add_argument("--current-file")
    parser.add_argument("--staging")
    parser.add_argument("--target-version")
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--wait-timeout", type=float, default=DEFAULT_WAIT_TIMEOUT_S)
    args = parser.parse_args(argv)
    mode = "start" if args.start else "apply"
    current_file = args.current_file or str(Path(args.version_root).parent / "current.json")
    try:
        if mode == "start":
            result = launch_current(args.version_root, current_file=current_file,
                                    launcher=_default_launcher)
        else:
            if not args.staging or not args.target_version or args.parent_pid is None:
                parser.error("apply 模式需要 --staging、--target-version、--parent-pid")
            result = apply_staged(
                args.staging, args.version_root, args.target_version,
                current_file=current_file, parent_pid=args.parent_pid,
                wait_parent=wait_parent_process, wait_timeout_s=args.wait_timeout,
                launcher=_default_launcher)
    except (OSError, ValueError) as exc:
        result = {"ok": False, "error_code": "launcher_failed", "text": str(exc)}
    if result.get("ok"):
        return 0
    print(result.get("text") or "版本启动失败。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
