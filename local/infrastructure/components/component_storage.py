# -*- coding: utf-8 -*-
"""组件底层存储原语：路径计算、跨进程锁、helper 隔离执行、阶段/缓存回收与解压。

@author Author
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat
import subprocess
import threading
import time
import uuid
import zipfile
from pathlib import Path

_cp = None


def bind(facade) -> None:
    """绑定 component_packages 门面。"""
    global _cp
    _cp = facade


def _root(root):
    if root is None:
        from infrastructure.stores.data_directory import default_data_dir
        root = default_data_dir()
    return Path(root).resolve() / "advanced"


def install_dir(key, *, root=None):
    """组件的安装目录（数据目录下 advanced/<功能>）；只给电脑端的位置接口用，不查磁盘。"""
    return _cp._root(root) / _cp._key(key)


def artifact_dir(artifact_id, *, root=None):
    """拆分资产目录；旧 feature 目录保持独立，作为 legacy 回退。"""
    return _cp._root(root) / _cp.ARTIFACT_ROOT / _cp._artifact_key(artifact_id)


@contextlib.contextmanager
def _file_transaction(root):
    from infrastructure.stores.prefs_store import acquire_file_lock, release_file_lock
    base = _cp._root(root)
    held = getattr(_cp._TRANSACTION_LOCAL, "held", set())
    if str(base) in held:
        yield
        return
    assets = base / _cp.ARTIFACT_ROOT
    if _cp._linked(base) or _cp._linked(assets):
        raise _cp.PackageError("unsafe_path")
    # 锁独立于安装目录，查询尚未安装的组件时不能凭空造出 advanced 目录。
    base.parent.mkdir(parents=True, exist_ok=True)
    lock = base.parent / ".advanced.lock"
    if _cp._linked(lock):
        raise _cp.PackageError("unsafe_path")
    with lock.open("a+b") as handle:
        acquire_file_lock(handle, 30.0)
        try:
            _cp._TRANSACTION_LOCAL.held = held | {str(base)}
            yield
        finally:
            _cp._TRANSACTION_LOCAL.held = held
            release_file_lock(handle)


@contextlib.contextmanager
def _cloudflared_use_lock(root):
    from infrastructure.stores.prefs_store import (
        PrefsLockTimeout, acquire_file_lock, release_file_lock)
    base = _cp._root(root)
    base.parent.mkdir(parents=True, exist_ok=True)
    lock = base.parent / ".advanced-phone-control.use.lock"
    if _cp._linked(lock):
        raise _cp.PackageError("unsafe_path")
    with lock.open("a+b") as handle:
        try:
            acquire_file_lock(handle, 0.0)
        except PrefsLockTimeout as exc:
            raise _cp.PackageError("component_in_use") from exc
        try:
            yield
        finally:
            release_file_lock(handle)


def _assert_unused(feature, root):
    # 写入口已持事务锁；检查后到写入完成之间，新通道必须等待同一把事务锁。
    if feature == "phone_control":
        with _cp._cloudflared_use_lock(root):
            pass


def _pipe_reader(stream, output, overflow, proc, max_output):
    try:
        while True:
            block = stream.read(65536)
            if not block:
                break
            if len(output) + len(block) > max_output:
                overflow.set()
                proc.kill()
                break
            output.extend(block)
    except OSError:
        pass


def _pipe_writer(stream, body):
    try:
        stream.write(body)
        stream.close()
    except OSError:
        pass


def _helper(executable, *, feature, payload=None, timeout=30, probe=False, env=None):
    """用有界 reader 防止 helper stdout/stderr 无限堆进主进程内存。"""
    body = b"" if probe else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    if len(body) > 2 * 1024 * 1024 + 4096:
        raise _cp.PackageError("input_limit")
    args = [str(executable)] + (["--probe"] if probe else [])
    child_env = None
    if env:
        child_env = os.environ.copy()
        child_env.update({str(k): str(v) for k, v in env.items()})
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=child_env,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    output = bytearray()
    overflow = threading.Event()
    reader = threading.Thread(
        target=_pipe_reader, args=(proc.stdout, output, overflow, proc, _cp.MAX_OUTPUT),
        name="advanced-helper-output", daemon=True)
    reader.start()
    # Windows 管道写满会阻塞；主线程必须先能进入整体超时等待。
    writer = threading.Thread(target=_pipe_writer, args=(proc.stdin, body),
                              name="advanced-helper-input", daemon=True)
    writer.start()
    try:
        proc.wait(timeout=timeout)
        writer.join(timeout=2)
        reader.join(timeout=2)
        if writer.is_alive() or reader.is_alive() or overflow.is_set() or proc.returncode != 0:
            raise _cp.PackageError("helper_failed")
        result = json.loads(output.decode("utf-8"))
        if (not isinstance(result, dict) or result.get("ok") is not True
                or result.get("feature") != feature or result.get("protocol") != 1):
            raise _cp.PackageError("helper_protocol")
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise _cp.PackageError("helper_failed") from exc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=2)
        writer.join(timeout=2)
        reader.join(timeout=2)
        proc.stdout.close()
        if not writer.is_alive() and not proc.stdin.closed:
            proc.stdin.close()


def _diagnostic(base, message):
    """组件目录里的自检日志；写不进去也不能影响主流程。"""
    try:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (base / ".diagnostics.log").open("a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (stamp, message))
    except OSError:
        pass


def _discard(path, base):
    """清掉已无用途的旧副本；清不掉只记诊断，不能反过来否定已经完成的换位。"""
    try:
        shutil.rmtree(path)
    except OSError as exc:
        _cp._diagnostic(base, "旧副本清理失败：%s（%s）" % (path.name, type(exc).__name__))


def _discard_stage(path, base):
    try:
        if path.is_dir() and not _cp._linked(path):
            shutil.rmtree(path)
    except OSError as exc:
        _cp._diagnostic(base, "阶段目录清理失败：%s（%s）" % (path.name, type(exc).__name__))


def _reclaim_stages(base, feature=None):
    """回收崩溃留下的阶段目录（可能上百 MB）；只在持事务锁时调用。"""
    names = [".stage-cf-*"]
    if feature:
        names.append(".stage-%s-*" % feature)
    for name in names:
        for path in base.glob(name):
            _cp._discard_stage(path, base)
    assets = base / _cp.ARTIFACT_ROOT
    for path in (assets / ".cache").glob(".stage-*"):
        _cp._discard_stage(path, base)
    if not feature:
        return
    for artifact_id, spec in _cp.ARTIFACTS.items():
        if spec["feature"] != feature:
            continue
        for path in assets.glob(".stage-%s-*" % artifact_id):
            _cp._discard_stage(path, base)
        for path in (assets / ".cache" / artifact_id).glob(".stage-*"):
            _cp._discard_stage(path, base)


def _sync_directory(directory):
    """目录项也尽量落盘；Windows 不允许对目录 fsync 时安静跳过。"""
    try:
        handle = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def _atomic_json(path, data):
    if _cp._linked(path.parent) or _cp._linked(path):
        raise _cp.PackageError("unsafe_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / (".stage-" + uuid.uuid4().hex)
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, sort_keys=True))
            handle.flush()
            # 不 fsync 的话，断电后可能留下空的日志/指针，读取方会当成装坏
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _cp._sync_directory(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


def _reclaim_artifact_cache(base, cache_root, artifact_id, keep):
    try:
        entries = list(cache_root.iterdir())
    except OSError:
        return
    for path in entries:
        if path.name.startswith(".stage-") or (artifact_id, path.name) in keep:
            continue
        if _cp._linked(path) or not path.is_dir():
            continue
        try:
            if time.time() - path.stat().st_mtime < _cp.CACHE_RECLAIM_GRACE_S:
                continue
        except OSError:
            continue
        try:
            shutil.rmtree(path)
        except OSError as exc:
            _cp._diagnostic(base, "缓存清理失败：%s/%s（%s）"
                            % (artifact_id, path.name, type(exc).__name__))
            continue
        for cache_key in [k for k in _cp._ARTIFACT_STATUS_CACHE if k[0] == str(path)]:
            _cp._ARTIFACT_STATUS_CACHE.pop(cache_key, None)


def _reclaim_group_cache(base, feature, keep):
    """回收该功能下不属于「新组」也不属于「切换前那一组」的缓存目录。"""
    if keep is None:
        return
    cache_base = base / _cp.ARTIFACT_ROOT / ".cache"
    if _cp._linked(cache_base):
        return
    for artifact_id, spec in _cp.ARTIFACTS.items():
        if spec["feature"] != feature:
            continue
        cache_root = cache_base / artifact_id
        if _cp._linked(cache_root):
            continue
        _reclaim_artifact_cache(base, cache_root, artifact_id, keep)


def _extract_zip_package(archive, stage, parse_manifest):
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        if len(infos) > _cp.MAX_FILES or sum(i.file_size for i in infos) > _cp.MAX_EXTRACTED:
            raise _cp.PackageError("size_limit")
        files, names = {}, set()
        for info in infos:
            name = _cp._name(info.filename.rstrip("/") if info.is_dir() else info.filename)
            if name.casefold() in names or stat.S_ISLNK(info.external_attr >> 16):
                raise _cp.PackageError("unsafe_path")
            names.add(name.casefold())
            if not info.is_dir():
                files[name] = info
        if "manifest.json" not in files:
            raise _cp.PackageError("bad_manifest")
        if files["manifest.json"].file_size > 2 * 1024 * 1024:
            raise _cp.PackageError("manifest_limit")
        manifest = parse_manifest(package.read(files["manifest.json"]))
        if set(files) != set(manifest["files"]) | {"manifest.json"}:
            raise _cp.PackageError("file_mismatch")
        for name, info in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            with package.open(info) as source, path.open("wb") as dest:
                shutil.copyfileobj(source, dest, 1024 * 1024)
    return manifest
