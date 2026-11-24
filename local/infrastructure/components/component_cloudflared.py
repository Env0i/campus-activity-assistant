# -*- coding: utf-8 -*-
"""cloudflared 自检、受管目录安装/恢复/查询与使用租约。

@author Author
"""
from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_cp = None


def bind(facade) -> None:
    """绑定 component_packages 门面。"""
    global _cp
    _cp = facade


def probe_cloudflared_version(path) -> str:
    """跑一次 `cloudflared --version`；失败一律返回空串（调用方按不可用处理）。"""
    try:
        done = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    if done.returncode != 0:
        return ""
    return _cp.parse_cloudflared_version((done.stdout or "") + " " + (done.stderr or ""))


def cloudflared_version_text(path) -> str:
    """跑一次 `cloudflared --version` 并返回原始输出；跑不起来返回空串。

    与 probe_cloudflared_version 分开：那个只关心「版本号是多少」，这里要拿原始
    输出判断「这份文件到底是不是 cloudflared」，比如用户误选了 Tailscale 的 exe。
    """
    try:
        done = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return ""
    return ((done.stdout or "") + " " + (done.stderr or "")).strip()


def inspect_cloudflared(source, *, probe_text=None) -> dict:
    """只读自检：这个文件是不是我们要的 cloudflared。不复制、不安装、不改任何状态。

    返回的 text 是给用户看的结论，说明「为什么不行」，而不是只给一个错误码。
    """
    probe_text = probe_text or _cp.cloudflared_version_text
    path = Path(source)
    if not path.is_file():
        return {"ok": False, "kind": "missing", "version": "",
                "text": "没有找到这个文件，可能刚被移动或删除，请重新选择。"}
    if path.suffix.lower() != ".exe":
        return {"ok": False, "kind": "not_executable", "version": "",
                "text": "这里需要 cloudflared 的 Windows 可执行文件（.exe），不是这个文件。"}
    output = probe_text(path)
    found = _cp.parse_cloudflared_version(output)
    if found:
        if found != _cp.CLOUDFLARED_VERSION:
            return {"ok": False, "kind": "version", "version": found,
                    "text": "这份 cloudflared 是 %s，本程序按 %s 校验，版本不一致。"
                            "请换官方发布的 %s。"
                            % (found, _cp.CLOUDFLARED_VERSION, _cp.CLOUDFLARED_VERSION)}
        return {"ok": True, "kind": "cloudflared", "version": found, "path": str(path),
                "text": "已识别为 cloudflared %s，版本与要求一致。" % found}
    lowered = (output or "").lower()
    if "tailscale" in lowered or path.name.lower().startswith("tailscale"):
        return {"ok": False, "kind": "tailscale", "version": "",
                "text": "这是 Tailscale 的程序，不是 cloudflared。Tailscale 请用官方安装包，"
                        "装好之后这里的通道会自动检测到它。"}
    if not output:
        return {"ok": False, "kind": "unreadable", "version": "",
                "text": "没法从这份文件读出 cloudflared 版本（可能不是可执行文件，或被系统拦住了）。"}
    return {"ok": False, "kind": "unknown", "version": "",
            "text": "这份文件不是 cloudflared：它的版本信息里没有 cloudflared 的版本号。"}


def _recover_cloudflared_store(base):
    """进程在受管 cloudflared 换位中断时，把 .bak 恢复成正式目录。

    换位顺序是 store → .bak、stage → store；在两步之间崩溃就只剩 .bak。
    不恢复的话，读取方会把「已经装好」当成没装，用户还得重新选一次文件。
    """
    store = base / _cp.CLOUDFLARED_STORE
    backup = store.with_name(_cp.CLOUDFLARED_STORE + ".bak")
    if _cp._linked(base) or _cp._linked(store) or _cp._linked(backup):
        raise _cp.PackageError("unsafe_path")
    if backup.exists() and not store.exists():
        os.replace(backup, store)
    elif backup.exists() and store.exists():
        if not backup.is_dir():
            raise _cp.PackageError("unsafe_path")
        shutil.rmtree(backup, ignore_errors=True)


def install_cloudflared(source, *, root=None, probe=None, probe_text=None) -> dict:
    """把用户选定的 cloudflared 收进受管目录，并记下版本与哈希。

    校验不过一律抛 PackageError，原目录保持不动（不会出现「装了一半」）。
    """
    _cp._assert_unused("phone_control", root)
    info = _cp.inspect_cloudflared(source, probe_text=probe_text)
    if not info["ok"]:
        raise _cp.PackageError(info["kind"])
    probe = probe or _cp.probe_cloudflared_version
    with _cp._LOCK:
        base = _cp._root(root)
        if _cp._linked(base):
            raise _cp.PackageError("unsafe_path")
        base.mkdir(parents=True, exist_ok=True)
        # 上一次换位可能停在「store 已挪走、stage 还没落位」：先恢复再开装
        _cp._recover_cloudflared_store(base)
        store = base / _cp.CLOUDFLARED_STORE
        stage = Path(tempfile.mkdtemp(prefix=".stage-cf-", dir=base))
        try:
            target = stage / _cp.CLOUDFLARED_FILE
            shutil.copy2(source, target)
            found = _cp.parse_cloudflared_version(probe(target))
            if found != _cp.CLOUDFLARED_VERSION:
                # 复制之后重新跑一次：选文件时的结论不能代表落盘后的这一份
                raise _cp.PackageError("cloudflared_version")
            manifest = {"schema": 1, "version": found, "sha256": _cp.sha256(target),
                        "filename": _cp.CLOUDFLARED_FILE}
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            backup = store.with_name(_cp.CLOUDFLARED_STORE + ".bak")
            if store.exists():
                if _cp._linked(store):
                    raise _cp.PackageError("unsafe_path")
                os.replace(store, backup)
            try:
                os.replace(stage, store)
            except OSError:
                if backup.exists():
                    os.replace(backup, store)
                raise
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            return {"ok": True, "version": found,
                    "text": "cloudflared %s 已收好，Cloudflare 通道现在可用。" % found}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def stored_cloudflared(*, root=None, probe=None) -> str:
    """返回受管目录里那份 cloudflared 的路径；版本或哈希对不上就返回空串。

    版本探测要起子进程，所以按（路径、大小、mtime_ns）缓存成功结果，文件没变就不再探；
    哈希仍每次核对，换了文件（含同名同大小）一定走重新探测。调用方自带的 probe 不进缓存。
    """
    real_probe = _cp.probe_cloudflared_version
    probe = probe or real_probe
    cacheable = probe is real_probe
    with _cp._LOCK:
        base = _cp._root(root)
        try:
            _cp._recover_cloudflared_store(base)
        except (_cp.PackageError, OSError):
            return ""
        _cp._reclaim_stages(base)
        store = base / _cp.CLOUDFLARED_STORE
        target = store / _cp.CLOUDFLARED_FILE
        try:
            if not target.is_file() or _cp._linked(target):
                return ""
            manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
            if _cp.parse_cloudflared_version(manifest.get("version")) != _cp.CLOUDFLARED_VERSION:
                return ""
            if str(manifest.get("sha256") or "") != _cp.sha256(target):
                return ""
            info = target.stat()
            fingerprint = (str(target), info.st_size, info.st_mtime_ns)
            if cacheable and _cp._CLOUDFLARED_PROBE_CACHE.get(fingerprint) == _cp.CLOUDFLARED_VERSION:
                return str(target)
            if _cp.parse_cloudflared_version(probe(target)) != _cp.CLOUDFLARED_VERSION:
                return ""
            if cacheable:
                if len(_cp._CLOUDFLARED_PROBE_CACHE) >= 16:
                    _cp._CLOUDFLARED_PROBE_CACHE.clear()
                _cp._CLOUDFLARED_PROBE_CACHE[fingerprint] = _cp.CLOUDFLARED_VERSION
            return str(target)
        except (OSError, ValueError):
            return ""


def remove_cloudflared(*, root=None) -> dict:
    with _cp._LOCK:
        _cp._assert_unused("phone_control", root)
        base = _cp._root(root)
        store = base / _cp.CLOUDFLARED_STORE
        if _cp._linked(base) or _cp._linked(store):
            raise _cp.PackageError("unsafe_path")
        _cp._recover_cloudflared_store(base)
        if store.exists():
            shutil.rmtree(store)
        return {"ok": True, "text": "已移除单独安装的 cloudflared。"}


def cloudflared(*, root=None, probe=None):
    """返回可用的 cloudflared 路径；版本不符、缺文件、probe 失败都返回空串。"""
    probe = probe or _cp.probe_cloudflared_version
    group = _cp._split_group("phone_control", root=root, allow_cache=False)
    split_tool = group.get("artifacts", {}).get("phone_control_cloudflared", {}) if group.get("available") else {}
    if not _cp._group_pointer("phone_control", root).exists() and not split_tool:
        split_tool = _cp.artifact_status("phone_control_cloudflared", root=root)
    if split_tool.get("available"):
        target = Path(split_tool["path"]) / _cp.CLOUDFLARED_NAME
        if _cp.parse_cloudflared_version(probe(target)) == _cp.CLOUDFLARED_VERSION:
            return str(target)
    with _cp._LOCK:
        directory = _cp._root(root) / "phone_control"
        try:
            manifest = _cp.validate_directory(directory, "phone_control")
            declared = (manifest.get("cloudflared") or {}).get("version") or ""
            if _cp.parse_cloudflared_version(declared) != _cp.CLOUDFLARED_VERSION:
                return ""
            if _cp.CLOUDFLARED_NAME not in manifest["files"]:
                return ""
            target = directory / _cp.CLOUDFLARED_NAME
            if _cp.parse_cloudflared_version(probe(target)) != _cp.CLOUDFLARED_VERSION:
                return ""
            return str(target)
        except (_cp.PackageError, OSError):
            pass
    # 组件包之外还有一条合法来源：用户在对话框里亲自选过、且校验通过的那份
    return _cp.stored_cloudflared(root=root, probe=probe)


@contextlib.contextmanager
def cloudflared_usage(path, *, root=None):
    """从启动前核验到进程退出持有租约，阻止另一进程拆掉正在使用的组件。"""
    with _cp._cloudflared_use_lock(root):
        with _cp._LOCK, _cp._file_transaction(root):
            trusted = _cp.cloudflared(root=root)
            if not trusted or Path(trusted).resolve() != Path(path).resolve():
                raise _cp.PackageError("cloudflared_untrusted")
        yield trusted
