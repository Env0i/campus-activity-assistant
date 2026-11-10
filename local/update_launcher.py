"""版本目录切换与当前版本启动桥接。

该模块只处理已准备好的 staging 目录，不下载、不解压，也不触碰数据目录。
切换顺序保证 current.json 写失败时旧版本和 staging 都能保留。
"""
from __future__ import annotations

import json
import os
import re
import argparse
import subprocess
import sys
import time
import ctypes
from pathlib import Path
from typing import Callable


_VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\Z")
_EXE_NAME = "campus-activity-watch.exe"


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
    exe = target / _EXE_NAME
    if not _contained(target, exe) or exe.is_symlink() or not exe.is_file():
        raise ValueError("版本目录缺少固定程序")
    return target


def launch_current(version_root: os.PathLike | str, *, current_file=None,
                   launcher: Callable[[str], object] | None = None) -> dict:
    """按 current.json 启动当前版本的固定 exe。"""
    current_path = _current_path(current_file or Path(version_root).parent / "current.json")
    if not _contained(Path(version_root).parent, current_path):
        raise ValueError("current.json 路径越界")
    payload = read_current(current_path)
    target = validate_version_dir(version_root, payload["version"])
    exe = target / _EXE_NAME
    (launcher or os.startfile)(str(exe))
    return {"ok": True, "version": payload["version"], "path": str(exe)}


def _atomic_current(path: Path, payload: dict) -> None:
    """优先复用 updater 的原子写实现，便于旧调用方注入失败；否则本地完成。"""
    try:
        from . import updater
    except ImportError:
        updater = None
    writer = getattr(updater, "_atomic_write_json", None)
    if writer is not None:
        writer(path, payload)
        return
    part = path.with_name(path.name + ".part")
    try:
        part.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


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
    if target.exists() or not _contained(root, target):
        return {"ok": False, "error_code": "switch_failed", "text": "目标版本目录已存在。"}
    waiter = wait_fn or wait_parent
    if parent_pid is not None and waiter is not None:
        waited = waiter(parent_pid, wait_timeout_s)
        if isinstance(waited, dict) and not waited.get("ok"):
            return waited
    previous = None
    try:
        if current.is_file():
            previous = read_current(current).get("version")
        root.mkdir(parents=True, exist_ok=True)
        os.replace(source, target)
        _atomic_current(current, {"version": target_version})
    except Exception as exc:  # noqa: BLE001 - 切换失败必须恢复 staging
        if target.exists() and not source.exists():
            try:
                os.replace(target, source)
            except OSError:
                pass
        return {"ok": False, "error_code": "switch_failed", "text": str(exc) or "版本切换失败。"}
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
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        WAIT_OBJECT_0 = 0
        WAIT_TIMEOUT = 0x102
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
                                      False, pid)
        if not handle:
            return {"ok": False, "error_code": "parent_wait_failed",
                    "text": "无法等待父进程退出。"}
        try:
            result = kernel32.WaitForSingleObject(handle, int(timeout_s * 1000))
        finally:
            kernel32.CloseHandle(handle)
        if result == WAIT_OBJECT_0:
            return {"ok": True}
        if result == WAIT_TIMEOUT:
            return {"ok": False, "error_code": "parent_timeout",
                    "text": "等待主程序退出超时。"}
        return {"ok": False, "error_code": "parent_wait_failed",
                "text": "等待父进程退出失败。"}
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
    parser.add_argument("--wait-timeout", type=float, default=30.0)
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
