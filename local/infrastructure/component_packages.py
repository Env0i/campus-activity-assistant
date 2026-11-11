# -*- coding: utf-8 -*-
"""固定高级组件 ZIP 的校验、替换及隔离 helper 调用。

SHA256 只验证完整性，用户必须自行确认组件来源可信。
@author Author
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path, PurePosixPath

FEATURES = {"phone_control", "relogin_ocr"}
ARTIFACTS = {
    "phone_control_runtime": {"feature": "phone_control", "role": "runtime",
                               "entry": "feature-helper.exe"},
    "phone_control_cloudflared": {"feature": "phone_control", "role": "tool",
                                   "entry": "bin/cloudflared.exe"},
    "relogin_ocr_runtime": {"feature": "relogin_ocr", "role": "runtime",
                             "entry": "feature-helper.exe"},
    "relogin_ocr_model": {"feature": "relogin_ocr", "role": "model",
                           "entry": ""},
}
ARTIFACT_ROOT = "assets"
ARTIFACT_SCHEMA = 2
ARTIFACT_PROTOCOL = 1
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXTRACTED = 1024 * 1024 * 1024
MAX_FILES = 5000
MAX_OUTPUT = 2 * 1024 * 1024
# Cloudflare 快速隧道用的可执行文件：版本与路径都写死在这里，组件包必须
# 在 manifest 里声明同一个版本，否则用户跑起来的其实是「随手放进去的任意二进制」。
CLOUDFLARED_NAME = "bin/cloudflared.exe"
CLOUDFLARED_VERSION = "2026.10.7"
# 用户自选的 cloudflared：单独放一个受管目录，manifest 里记版本与哈希。
# 源码版没有组件包，但通道照样要有据可查的二进制——选一次不等于永远信任，
# 每次取用都重新核版本、核哈希，文件被换掉就自动失效。
CLOUDFLARED_STORE = "cloudflared"
CLOUDFLARED_FILE = "cloudflared.exe"
_LOCK = threading.RLock()
_STATUS_CACHE = {}
_ARTIFACT_STATUS_CACHE = {}
_TRANSACTION_LOCAL = threading.local()


class PackageError(ValueError):
    pass


_CLOUDFLARED_VERSION_RE = re.compile(r"(\d{4}\.\d+\.\d+)")


def parse_cloudflared_version(text) -> str:
    """从 `cloudflared --version` 的输出里取语义版本；取不到返回空串。"""
    found = _CLOUDFLARED_VERSION_RE.search(str(text or ""))
    return found.group(1) if found else ""


def supported():
    return sys.platform == "win32" and struct.calcsize("P") == 8 and platform.machine().lower() in (
        "amd64", "x86_64")


def version():
    candidates = [Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])) / "VERSION",
                  Path(__file__).resolve().parents[2] / "VERSION"]
    for path in candidates:
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if re.fullmatch(r"\d+\.\d+\.\d+", value):
                return value
    raise PackageError("version_missing")


def _root(root):
    if root is None:
        from runtime_paths import DATA_DIR
        root = DATA_DIR
    return Path(root).resolve() / "advanced"


@contextlib.contextmanager
def _file_transaction(root):
    from infrastructure.prefs_store import acquire_file_lock, release_file_lock
    base = _root(root)
    held = getattr(_TRANSACTION_LOCAL, "held", set())
    if str(base) in held:
        yield
        return
    assets = base / ARTIFACT_ROOT
    if _linked(base) or _linked(assets):
        raise PackageError("unsafe_path")
    # 锁独立于安装目录，查询尚未安装的组件时不能凭空造出 advanced 目录。
    base.parent.mkdir(parents=True, exist_ok=True)
    lock = base.parent / ".advanced.lock"
    if _linked(lock):
        raise PackageError("unsafe_path")
    with lock.open("a+b") as handle:
        acquire_file_lock(handle, 30.0)
        try:
            _TRANSACTION_LOCAL.held = held | {str(base)}
            yield
        finally:
            _TRANSACTION_LOCAL.held = held
            release_file_lock(handle)


def _transactional(function):
    @functools.wraps(function)
    def guarded(*args, **kwargs):
        with _LOCK, _file_transaction(kwargs.get("root")):
            return function(*args, **kwargs)
    return guarded


@contextlib.contextmanager
def _cloudflared_use_lock(root):
    from infrastructure.prefs_store import (
        PrefsLockTimeout, acquire_file_lock, release_file_lock)
    base = _root(root)
    base.parent.mkdir(parents=True, exist_ok=True)
    lock = base.parent / ".advanced-phone-control.use.lock"
    if _linked(lock):
        raise PackageError("unsafe_path")
    with lock.open("a+b") as handle:
        try:
            acquire_file_lock(handle, 0.0)
        except PrefsLockTimeout as exc:
            raise PackageError("component_in_use") from exc
        try:
            yield
        finally:
            release_file_lock(handle)


def _assert_unused(feature, root):
    # 写入口已持事务锁；检查后到写入完成之间，新通道必须等待同一把事务锁。
    if feature == "phone_control":
        with _cloudflared_use_lock(root):
            pass


@contextlib.contextmanager
def cloudflared_usage(path, *, root=None):
    """从启动前核验到进程退出持有租约，阻止另一进程拆掉正在使用的组件。"""
    with _cloudflared_use_lock(root):
        with _LOCK, _file_transaction(root):
            trusted = cloudflared(root=root)
            if not trusted or Path(trusted).resolve() != Path(path).resolve():
                raise PackageError("cloudflared_untrusted")
        yield trusted


def _key(key):
    if key not in FEATURES:
        raise PackageError("unknown_feature")
    return key


def _artifact_key(artifact_id):
    if artifact_id not in ARTIFACTS:
        raise PackageError("unknown_artifact")
    return artifact_id


def install_dir(key, *, root=None):
    """组件的安装目录（数据目录下 advanced/<功能>）；只给电脑端的位置接口用，不查磁盘。"""
    return _root(root) / _key(key)


def artifact_dir(artifact_id, *, root=None):
    """拆分资产目录；旧 feature 目录保持独立，作为 legacy 回退。"""
    return _root(root) / ARTIFACT_ROOT / _artifact_key(artifact_id)


def _linked(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _name(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or name.startswith("/") or any(ord(c) < 32 for c in name)):
        raise PackageError("unsafe_path")
    parts = name.split("/")
    for part in parts:
        if (part in ("", ".", "..") or part.rstrip(" .") != part
                or any(c in part for c in '<>"|?*')
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)):
            raise PackageError("unsafe_path")
    if PurePosixPath(name).is_absolute():
        raise PackageError("unsafe_path")
    return name


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest(raw, key):
    if len(raw) > 2 * 1024 * 1024:
        raise PackageError("manifest_limit")
    def unique(pairs):
        out = {}
        for name, value in pairs:
            if name in out:
                raise PackageError("duplicate_key")
            out[name] = value
        return out
    try:
        data = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise PackageError("bad_manifest") from exc
    if (not isinstance(data, dict) or type(data.get("schema")) is not int
            or data["schema"] != 1 or data.get("feature") != key
            or data.get("platform") != "windows-x64" or data.get("entry") != "feature-helper.exe"
            or data.get("version") != version() or not isinstance(data.get("files"), dict)):
        raise PackageError("incompatible_manifest")
    files = data["files"]
    if not files or len(files) >= MAX_FILES or "feature-helper.exe" not in files:
        raise PackageError("bad_files")
    # 架构与配套主程序版本：可选字段，但一旦声明就必须自洽——下载流程会把它们
    # 当成「这个包能不能装在当前这台机器/这个版本上」的依据，含糊过去比缺字段更糟。
    target = data.get("target")
    if target is not None and target != "win-x64":
        raise PackageError("bad_target")
    app_version = data.get("app_version")
    if app_version is not None and app_version != data.get("version"):
        raise PackageError("bad_app_version")
    cloudflare = data.get("cloudflared")
    if cloudflare is not None:
        if (not isinstance(cloudflare, dict)
                or not isinstance(cloudflare.get("version"), str)
                or not parse_cloudflared_version(cloudflare.get("version"))
                or not isinstance(cloudflare.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", cloudflare["sha256"])):
            raise PackageError("bad_manifest")
        digest = files.get(CLOUDFLARED_NAME)
        if key != "phone_control" or digest is None or digest != cloudflare["sha256"]:
            raise PackageError("bad_manifest")
        if parse_cloudflared_version(cloudflare["version"]) != CLOUDFLARED_VERSION:
            raise PackageError("cloudflared_version")
    elif key == "phone_control":
        # phone_control 必须内置 cloudflared：缺它就没有远程通道，不能先装上再说
        raise PackageError("cloudflared_required")
    elif CLOUDFLARED_NAME in files:
        # 有二进制却没声明版本：不能假装知道它是什么
        raise PackageError("bad_manifest")
    names = set()
    for name, digest in files.items():
        _name(name)
        folded = name.casefold()
        if (folded in names or folded == "manifest.json" or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise PackageError("bad_files")
        names.add(folded)
    return data


def _artifact_manifest(raw, artifact_id):
    """校验 schema2 拆分资产清单；不把资产版本误当主程序版本。"""
    artifact_id = _artifact_key(artifact_id)
    if len(raw) > 2 * 1024 * 1024:
        raise PackageError("manifest_limit")
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeError) as exc:
        raise PackageError("bad_manifest") from exc
    spec = ARTIFACTS[artifact_id]
    if (not isinstance(data, dict) or data.get("schema") != ARTIFACT_SCHEMA
            or data.get("artifact_id") != artifact_id
            or data.get("feature") != spec["feature"]
            or data.get("role") != spec["role"]
            or data.get("protocol") != ARTIFACT_PROTOCOL
            or not isinstance(data.get("asset_version"), str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", data["asset_version"])
            or not isinstance(data.get("compatibility_id"), str)
            or not data["compatibility_id"]
            or not isinstance(data.get("files"), dict)):
        raise PackageError("incompatible_artifact_manifest")
    entry = data.get("entry")
    if entry != spec["entry"]:
        raise PackageError("bad_entry")
    if not isinstance(data.get("requires", []), list):
        raise PackageError("bad_requires")
    files = data["files"]
    if not files or len(files) >= MAX_FILES:
        raise PackageError("bad_files")
    names = set()
    for name, digest in files.items():
        _name(name)
        folded = name.casefold()
        if (folded in names or folded == "manifest.json"
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise PackageError("bad_files")
        names.add(folded)
    if spec["entry"] and spec["entry"] not in files:
        raise PackageError("entry_missing")
    if spec["role"] == "tool":
        tool = data.get("tool")
        if (not isinstance(tool, dict) or tool.get("name") != "cloudflared"
                or parse_cloudflared_version(tool.get("version")) != CLOUDFLARED_VERSION
                or files.get(spec["entry"]) != tool.get("sha256")):
            raise PackageError("bad_tool")
    declared_content = data.get("content_sha256")
    if declared_content is not None and declared_content != artifact_content_sha256(data):
        raise PackageError("content_mismatch")
    return data


def validate_artifact_directory(directory, artifact_id):
    """校验 schema2 资产目录，不执行 runtime helper。"""
    directory = Path(directory)
    _artifact_key(artifact_id)
    if _linked(directory) or _linked(directory.parent) or not directory.is_dir():
        raise PackageError("missing_artifact")
    manifest_path = directory / "manifest.json"
    if (not manifest_path.is_file() or _linked(manifest_path)
            or manifest_path.stat().st_size > 2 * 1024 * 1024):
        raise PackageError("bad_manifest")
    manifest = _artifact_manifest(manifest_path.read_bytes(), artifact_id)
    actual = {}
    total = 0
    for path in directory.rglob("*"):
        if _linked(path):
            raise PackageError("unsafe_path")
        if path.is_file():
            relative = _name(path.relative_to(directory).as_posix())
            actual[relative.casefold()] = relative
            total += path.stat().st_size
    if len(actual) > MAX_FILES or total > MAX_EXTRACTED:
        raise PackageError("size_limit")
    if set(actual.values()) != set(manifest["files"]) | {"manifest.json"}:
        raise PackageError("file_mismatch")
    for name, digest in manifest["files"].items():
        if sha256(directory / name) != digest:
            raise PackageError("hash_mismatch")
    return manifest


def validate_directory(directory, key):
    directory = Path(directory)
    _key(key)
    if _linked(directory) or _linked(directory.parent) or not directory.is_dir():
        raise PackageError("missing_component")
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file() or _linked(manifest_path) or manifest_path.stat().st_size > 2 * 1024 * 1024:
        raise PackageError("bad_manifest")
    manifest = _manifest(manifest_path.read_bytes(), key)
    actual = {}
    total = 0
    for path in directory.rglob("*"):
        if _linked(path):
            raise PackageError("unsafe_path")
        if path.is_file():
            relative = _name(path.relative_to(directory).as_posix())
            if relative.casefold() in actual:
                raise PackageError("duplicate_file")
            actual[relative.casefold()] = relative
            total += path.stat().st_size
    if len(actual) > MAX_FILES or total > MAX_EXTRACTED:
        raise PackageError("size_limit")
    if set(actual.values()) != set(manifest["files"]) | {"manifest.json"}:
        raise PackageError("file_mismatch")
    for name, digest in manifest["files"].items():
        if sha256(directory / name) != digest:
            raise PackageError("hash_mismatch")
    return manifest


def _helper(executable, *, feature, payload=None, timeout=30, probe=False, env=None):
    """用有界 reader 防止 helper stdout/stderr 无限堆进主进程内存。"""
    body = b"" if probe else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    if len(body) > 2 * 1024 * 1024 + 4096:
        raise PackageError("input_limit")
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
    def read():
        try:
            while True:
                block = proc.stdout.read(65536)
                if not block:
                    break
                if len(output) + len(block) > MAX_OUTPUT:
                    overflow.set()
                    proc.kill()
                    break
                output.extend(block)
        except OSError:
            pass
    reader = threading.Thread(target=read, name="advanced-helper-output", daemon=True)
    reader.start()
    def write():
        try:
            proc.stdin.write(body)
            proc.stdin.close()
        except OSError:
            pass
    # Windows 管道写满会阻塞；主线程必须先能进入整体超时等待。
    writer = threading.Thread(target=write, name="advanced-helper-input", daemon=True)
    writer.start()
    try:
        proc.wait(timeout=timeout)
        writer.join(timeout=2)
        reader.join(timeout=2)
        if writer.is_alive() or reader.is_alive() or overflow.is_set() or proc.returncode != 0:
            raise PackageError("helper_failed")
        result = json.loads(output.decode("utf-8"))
        if (not isinstance(result, dict) or result.get("ok") is not True
                or result.get("feature") != feature or result.get("protocol") != 1):
            raise PackageError("helper_protocol")
        return result
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise PackageError("helper_failed") from exc
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
        _diagnostic(base, "旧副本清理失败：%s（%s）" % (path.name, type(exc).__name__))


def _discard_stage(path, base):
    try:
        if path.is_dir() and not _linked(path):
            shutil.rmtree(path)
    except OSError as exc:
        _diagnostic(base, "阶段目录清理失败：%s（%s）" % (path.name, type(exc).__name__))


def _reclaim_stages(base, feature=None):
    """回收崩溃留下的阶段目录（可能上百 MB）；只在持事务锁时调用。"""
    names = [".stage-cf-*"]
    if feature:
        names.append(".stage-%s-*" % feature)
    for name in names:
        for path in base.glob(name):
            _discard_stage(path, base)
    assets = base / ARTIFACT_ROOT
    for path in (assets / ".cache").glob(".stage-*"):
        _discard_stage(path, base)
    if not feature:
        return
    for artifact_id, spec in ARTIFACTS.items():
        if spec["feature"] != feature:
            continue
        for path in assets.glob(".stage-%s-*" % artifact_id):
            _discard_stage(path, base)
        for path in (assets / ".cache" / artifact_id).glob(".stage-*"):
            _discard_stage(path, base)


def _read_transaction(journal):
    """读事务日志；空文件、断电截断、字段不对都当作「这一步没发生过」。"""
    try:
        data = json.loads(journal.read_text(encoding="utf-8"))
        transaction_id = data["transaction_id"]
        had_target = data["had_target"]
        if (not isinstance(transaction_id, str)
                or not re.fullmatch(r"[0-9a-f]{32}", transaction_id)
                or type(had_target) is not bool):
            return None
        return {"transaction_id": transaction_id, "had_target": had_target}
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _pointer_committed(pointer, key, transaction_id):
    try:
        selection = json.loads(pointer.read_text(encoding="utf-8")) if pointer.exists() else {}
    except (OSError, ValueError):
        return False
    return (isinstance(selection, dict) and selection.get("feature") == key
            and selection.get("selection") == "legacy"
            and selection.get("transaction_id") == transaction_id)


def _target_usable(target, key):
    """换位是否完成以「目标目录是否完整可验证」为准，不看 os.replace 报了什么错。"""
    try:
        if not target.is_dir() or _linked(target):
            return False
        validate_directory(target, key)
        _helper(target / "feature-helper.exe", feature=key, probe=True)
        return True
    except (PackageError, OSError, ValueError, KeyError, TypeError):
        return False


def _recover_replacement(base, key):
    """进程在目录换位中断时，先恢复同一组件的旧目录再判断是否可用。"""
    target = base / key
    backup = base / (".backup-" + key)
    if _linked(base) or _linked(target) or _linked(backup):
        raise PackageError("unsafe_path")
    journal = base / (".transaction-" + key + ".json")
    pointer = base / ARTIFACT_ROOT / ".groups" / (key + ".json")
    if _linked(journal) or _linked(pointer.parent) or _linked(pointer):
        raise PackageError("unsafe_path")
    if journal.exists():
        transaction = _read_transaction(journal)
        if transaction is None:
            # 断电会留下空文件：这一步没发生过，按磁盘上可验证的目录恢复
            _diagnostic(base, "事务日志损坏，按磁盘状态恢复：%s" % journal.name)
            try:
                journal.unlink()
            except OSError:
                pass
        else:
            committed = _pointer_committed(pointer, key, transaction["transaction_id"])
            if committed and _target_usable(target, key):
                # 已提交：残留 backup 只是旧副本，清不掉也不能推翻安装结果
                if backup.exists():
                    _discard(backup, base)
                journal.unlink()
                _STATUS_CACHE.pop(str(target), None)
                return
            if not committed and not transaction["had_target"]:
                # 首次安装且指针没落：这份目录没有被任何选择引用，删掉
                if target.exists():
                    shutil.rmtree(target)
                journal.unlink()
                _STATUS_CACHE.pop(str(target), None)
                return
            if backup.exists():
                # 事务未完成：把旧副本换回来，宁可用旧版也不留下半套
                if target.exists():
                    shutil.rmtree(target)
                os.replace(backup, target)
                journal.unlink()
                _STATUS_CACHE.pop(str(target), None)
                return
            journal.unlink()
            _STATUS_CACHE.pop(str(target), None)
            return
    if backup.exists() and not target.exists():
        os.replace(backup, target)
        _STATUS_CACHE.pop(str(target), None)
    elif backup.exists() and target.exists():
        # 进程死在清理前：target 可验证就以它为准，否则把旧副本换回来
        if not backup.is_dir():
            raise PackageError("unsafe_path")
        if _target_usable(target, key):
            _discard(backup, base)
        else:
            shutil.rmtree(target)
            os.replace(backup, target)
            _STATUS_CACHE.pop(str(target), None)


@_transactional
def status(key, *, root=None):
    with _LOCK:
        if not supported():
            return {"available": False, "source": "imported", "error": "unsupported_platform"}
        base = _root(root)
        key = _key(key)
        try:
            _recover_replacement(base, key)
        except (PackageError, OSError):
            return {"available": False, "source": "imported", "error": "component_invalid"}
        _reclaim_stages(base, key)
        directory = base / key
        if not directory.exists():
            return {"available": False, "source": "imported", "error": "", "version": ""}
        # 版本号给帮助页和下载服务看：装的是哪个版本的组件，界面要说得出来
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            installed_version = str((manifest or {}).get("version") or "")
        except (OSError, ValueError):
            installed_version = ""
        try:
            fingerprint = tuple((p.relative_to(directory).as_posix(), p.stat().st_size,
                                 p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                                for p in sorted(directory.rglob("*")))
            if _STATUS_CACHE.get(str(directory)) == fingerprint:
                return {"available": True, "source": "imported", "error": "",
                        "version": installed_version}
            validate_directory(directory, key)
            _helper(directory / "feature-helper.exe", feature=key, probe=True)
            _STATUS_CACHE[str(directory)] = fingerprint
        except (PackageError, OSError):
            return {"available": False, "source": "imported", "error": "component_invalid",
                    "version": ""}
        return {"available": True, "source": "imported", "error": "",
                "version": installed_version}


@_transactional
def install(archive, key, *, root=None):
    with _LOCK:
        _key(key)
        _assert_unused(key, root)
        if not supported():
            raise PackageError("unsupported_platform")
        archive = Path(archive)
        if archive.stat().st_size > MAX_ARCHIVE:
            raise PackageError("archive_limit")
        base = _root(root)
        if _linked(base):
            raise PackageError("unsafe_path")
        base.mkdir(parents=True, exist_ok=True)
        _recover_replacement(base, key)
        _reclaim_stages(base, key)
        target = base / key
        backup = base / (".backup-" + key)
        if backup.exists():
            # 换位前先清残留 backup：删不掉就中止，别让 os.replace 撞上它
            try:
                shutil.rmtree(backup)
            except OSError as exc:
                raise PackageError("backup_locked") from exc
            if backup.exists():
                raise PackageError("backup_locked")
        stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % key, dir=base))
        try:
            with zipfile.ZipFile(archive) as package:
                infos = package.infolist()
                if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_EXTRACTED:
                    raise PackageError("size_limit")
                names = set()
                files = {}
                for info in infos:
                    name = _name(info.filename.rstrip("/") if info.is_dir() else info.filename)
                    if name.casefold() in names or stat.S_ISLNK(info.external_attr >> 16):
                        raise PackageError("unsafe_path")
                    names.add(name.casefold())
                    if not info.is_dir():
                        files[name] = info
                if "manifest.json" not in files or files["manifest.json"].file_size > 2 * 1024 * 1024:
                    raise PackageError("bad_manifest")
                manifest = _manifest(package.read(files["manifest.json"]), key)
                if set(files) != set(manifest["files"]) | {"manifest.json"}:
                    raise PackageError("file_mismatch")
                for name, info in files.items():
                    path = stage / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with package.open(info) as source, path.open("wb") as dest:
                        shutil.copyfileobj(source, dest, 1024 * 1024)
            validate_directory(stage, key)
            _helper(stage / "feature-helper.exe", feature=key, probe=True)
            transaction_id = uuid.uuid4().hex
            journal = base / (".transaction-" + key + ".json")
            _atomic_json(journal, {"transaction_id": transaction_id, "had_target": target.exists()})
            try:
                if target.exists():
                    if _linked(target):
                        raise PackageError("unsafe_path")
                    os.replace(target, backup)
                os.replace(stage, target)
                _write_group_pointer(key, {"feature": key, "selection": "legacy",
                                           "transaction_id": transaction_id}, root)
            except BaseException:
                _recover_replacement(base, key)
                raise
            _recover_replacement(base, key)
            _STATUS_CACHE.pop(str(target), None)
            return {"ok": True, "feature": key, "text": "组件已导入并启用。"}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def _recover_artifact_replacement(base, artifact_id):
    assets = base / ARTIFACT_ROOT
    target = assets / artifact_id
    backup = assets / (".backup-" + artifact_id)
    if _linked(assets) or _linked(target) or _linked(backup):
        raise PackageError("unsafe_path")
    if backup.exists() and not target.exists():
        os.replace(backup, target)
    elif backup.exists() and target.exists():
        if not backup.is_dir():
            raise PackageError("unsafe_path")
        shutil.rmtree(backup, ignore_errors=True)


@_transactional
def artifact_status(artifact_id, *, root=None):
    """读取单个 schema2 资产状态，不把它当成完整 feature。"""
    artifact_id = _artifact_key(artifact_id)
    if not supported():
        return {"available": False, "artifact_id": artifact_id,
                "source": "imported", "error": "unsupported_platform"}
    base = _root(root)
    feature = ARTIFACTS[artifact_id]["feature"]
    pointer = _group_pointer(feature, root)
    if pointer.exists() or _linked(pointer):
        try:
            return _resolve_group(feature, root=root)[artifact_id]
        except (PackageError, OSError, ValueError, KeyError, TypeError):
            return {"available": False, "artifact_id": artifact_id,
                    "source": "split", "error": "artifact_invalid"}
    try:
        _recover_artifact_replacement(base, artifact_id)
        directory = artifact_dir(artifact_id, root=root)
        manifest = validate_artifact_directory(directory, artifact_id)
        return {"available": True, "artifact_id": artifact_id,
                "feature": manifest["feature"], "role": manifest["role"],
                "source": "split", "error": "",
                "version": manifest["asset_version"],
                "compatibility_id": manifest["compatibility_id"],
                "path": str(directory)}
    except (PackageError, OSError):
        return {"available": False, "artifact_id": artifact_id,
                "source": "split", "error": "artifact_invalid"}


@_transactional
def install_artifact(archive, artifact_id, *, root=None):
    """安装单个 schema2 资产，旧 feature 目录不参与换位。"""
    artifact_id = _artifact_key(artifact_id)
    _assert_unused(ARTIFACTS[artifact_id]["feature"], root)
    if not supported():
        raise PackageError("unsupported_platform")
    archive = Path(archive)
    if archive.stat().st_size > MAX_ARCHIVE:
        raise PackageError("archive_limit")
    base = _root(root)
    assets = base / ARTIFACT_ROOT
    if _linked(base) or _linked(assets):
        raise PackageError("unsafe_path")
    assets.mkdir(parents=True, exist_ok=True)
    _recover_artifact_replacement(base, artifact_id)
    stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % artifact_id, dir=assets))
    target = assets / artifact_id
    backup = assets / (".backup-" + artifact_id)
    try:
        with zipfile.ZipFile(archive) as package:
            infos = package.infolist()
            if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_EXTRACTED:
                raise PackageError("size_limit")
            files = {}
            names = set()
            for info in infos:
                name = _name(info.filename.rstrip("/") if info.is_dir() else info.filename)
                if name.casefold() in names or stat.S_ISLNK(info.external_attr >> 16):
                    raise PackageError("unsafe_path")
                names.add(name.casefold())
                if not info.is_dir():
                    files[name] = info
            if "manifest.json" not in files:
                raise PackageError("bad_manifest")
            if files["manifest.json"].file_size > 2 * 1024 * 1024:
                raise PackageError("manifest_limit")
            manifest = _artifact_manifest(package.read(files["manifest.json"]), artifact_id)
            if set(files) != set(manifest["files"]) | {"manifest.json"}:
                raise PackageError("file_mismatch")
            for name, info in files.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with package.open(info) as source, path.open("wb") as dest:
                    shutil.copyfileobj(source, dest, 1024 * 1024)
        validate_artifact_directory(stage, artifact_id)
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            if _linked(target):
                raise PackageError("unsafe_path")
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except OSError:
            if backup.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        return {"ok": True, "artifact_id": artifact_id,
                "feature": manifest["feature"], "text": "拆分组件资产已安装。"}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def artifact_content_sha256(manifest):
    keys = ("artifact_id", "feature", "role", "protocol", "compatibility_id",
            "entry", "requires", "tool", "files")
    content = {key: manifest[key] for key in keys if key in manifest}
    return hashlib.sha256(json.dumps(content, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact_fingerprint(directory):
    paths = [directory, *sorted(directory.rglob("*"))]
    result = []
    for path in paths:
        if _linked(path):
            raise PackageError("unsafe_path")
        info = path.stat(follow_symlinks=False)
        result.append((str(path.relative_to(directory)), info.st_size, info.st_mtime_ns,
                       info.st_ctime_ns, info.st_ino, info.st_mode,
                       getattr(info, "st_file_attributes", 0),
                       getattr(info, "st_reparse_tag", 0)))
    return tuple(result)


def _handle(directory, artifact_id, digest=None, *, allow_cache=False):
    directory = Path(directory)
    if any(_linked(parent) for parent in list(directory.parents)[:3]):
        raise PackageError("unsafe_path")
    cache_key = (str(directory), artifact_id, digest)
    if not allow_cache:
        # 执行前重新核验时撤销展示缓存，失败后下一次展示也必须反映真实损坏。
        _ARTIFACT_STATUS_CACHE.pop(cache_key, None)
    fingerprint = _artifact_fingerprint(directory) if allow_cache else None
    cached = _ARTIFACT_STATUS_CACHE.get(cache_key) if allow_cache else None
    if cached and cached[0] == fingerprint:
        return dict(cached[1])
    manifest = validate_artifact_directory(directory, artifact_id)
    actual = artifact_content_sha256(manifest)
    if digest is not None and actual != digest:
        raise PackageError("content_mismatch")
    handle = {"available": True, "source": "split", "artifact_id": artifact_id, "content_sha256": actual,
              "path": str(directory), "version": manifest["asset_version"],
              "compatibility_id": manifest["compatibility_id"],
              "feature": manifest["feature"], "role": manifest["role"],
              "requires": tuple(manifest.get("requires", []))}
    if allow_cache:
        if _artifact_fingerprint(directory) != fingerprint:
            raise PackageError("artifact_changed")
        if len(_ARTIFACT_STATUS_CACHE) >= 64:
            _ARTIFACT_STATUS_CACHE.pop(next(iter(_ARTIFACT_STATUS_CACHE)))
        _ARTIFACT_STATUS_CACHE[cache_key] = (fingerprint, handle)
    return dict(handle)


@_transactional
def find_cached_artifact(asset_metadata, *, root=None):
    try:
        artifact_id = _artifact_key(asset_metadata["artifact_id"])
        digest = asset_metadata["content_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return None
        base = _root(root) / ARTIFACT_ROOT
        cache_root = base / ".cache" / artifact_id
        candidates = [cache_root / digest]
        if cache_root.is_dir() and not _linked(cache_root):
            candidates.extend(sorted(cache_root.glob(digest + "-*")))
        candidates.append(base / artifact_id)
        for directory in candidates:
            if directory.parent == cache_root and not _valid_cache_key(directory.name, digest):
                continue
            try:
                result = _handle(directory, artifact_id, digest)
                if result["compatibility_id"] == asset_metadata["compatibility_id"]:
                    return result
            except (PackageError, OSError):
                continue
    except (KeyError, TypeError, PackageError):
        pass
    return None


@_transactional
def cache_artifact(archive, artifact_id, *, root=None, expect_content_sha256=None):
    artifact_id = _artifact_key(artifact_id)
    archive = Path(archive)
    if archive.stat().st_size > MAX_ARCHIVE:
        raise PackageError("archive_limit")
    assets = _root(root) / ARTIFACT_ROOT
    if _linked(_root(root)) or _linked(assets):
        raise PackageError("unsafe_path")
    assets.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % artifact_id, dir=assets))
    try:
        with zipfile.ZipFile(archive) as package:
            infos = package.infolist()
            if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_EXTRACTED:
                raise PackageError("size_limit")
            files, names = {}, set()
            for info in infos:
                name = _name(info.filename.rstrip("/") if info.is_dir() else info.filename)
                if name.casefold() in names or stat.S_ISLNK(info.external_attr >> 16):
                    raise PackageError("unsafe_path")
                names.add(name.casefold())
                if not info.is_dir():
                    files[name] = info
            if "manifest.json" not in files:
                raise PackageError("bad_manifest")
            if files["manifest.json"].file_size > 2 * 1024 * 1024:
                raise PackageError("manifest_limit")
            manifest = _artifact_manifest(package.read(files["manifest.json"]), artifact_id)
            if set(files) != set(manifest["files"]) | {"manifest.json"}:
                raise PackageError("file_mismatch")
            for name, info in files.items():
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                with package.open(info) as source, path.open("wb") as dest:
                    shutil.copyfileobj(source, dest, 1024 * 1024)
        handle = _handle(stage, artifact_id, expect_content_sha256)
        digest = handle["content_sha256"]
        target = assets / ".cache" / artifact_id / digest
        with _LOCK, _file_transaction(root):
            if _linked(assets / ".cache") or _linked(target.parent) or _linked(target):
                raise PackageError("unsafe_path")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                try:
                    return _handle(target, artifact_id, digest)
                except (PackageError, OSError):
                    target = target.with_name(digest + "-" + uuid.uuid4().hex)
            os.replace(stage, target)
            return _handle(target, artifact_id, digest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _valid_cache_key(cache_key, digest):
    return isinstance(cache_key, str) and bool(re.fullmatch(re.escape(digest) + r"(?:-[0-9a-f]{32})?", cache_key))


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
    if _linked(path.parent) or _linked(path):
        raise PackageError("unsafe_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.parent / (".stage-" + uuid.uuid4().hex)
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, sort_keys=True))
            handle.flush()
            # 不 fsync 的话，断电后可能留下空的日志/指针，读取方会当成装坏
            os.fsync(handle.fileno())
        os.replace(temp, path)
        _sync_directory(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


def _write_group_pointer(feature, data, root):
    _atomic_json(_group_pointer(feature, root), data)


def _group_pointer(feature, root):
    return _root(root) / ARTIFACT_ROOT / ".groups" / (_key(feature) + ".json")


def _resolve_group(feature, *, root=None, allow_cache=True):
    pointer = _group_pointer(feature, root)
    if _linked(pointer.parent) or _linked(pointer):
        raise PackageError("unsafe_path")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("feature") != feature or not isinstance(data.get("artifacts"), list):
        raise PackageError("bad_group")
    handles = []
    assets = _root(root) / ARTIFACT_ROOT
    for item in data["artifacts"]:
        artifact_id = _artifact_key(item["artifact_id"])
        digest = item["content_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise PackageError("bad_group")
        if item.get("source") == "fixed":
            path = assets / artifact_id
        elif item.get("source") == "cache":
            cache_key = item.get("cache_key", digest)
            if not _valid_cache_key(cache_key, digest):
                raise PackageError("bad_group")
            path = assets / ".cache" / artifact_id / cache_key
        else:
            raise PackageError("bad_group")
        handles.append(_handle(path, artifact_id, digest, allow_cache=allow_cache))
    return _validate_group(feature, handles)


def _validate_group(feature, handles):
    by_id = {h["artifact_id"]: h for h in handles}
    required = {key for key, spec in ARTIFACTS.items() if spec["feature"] == feature}
    if len(by_id) != len(handles) or set(by_id) != required:
        raise PackageError("artifact_incomplete")
    if len({h["compatibility_id"] for h in handles}) != 1:
        raise PackageError("artifact_incompatible")
    for handle in handles:
        if any(not isinstance(item, str) or item not in by_id for item in handle["requires"]):
            raise PackageError("artifact_incomplete")
    return by_id


@_transactional
def commit_artifact_group(feature, artifacts, *, root=None):
    feature = _key(feature)
    _assert_unused(feature, root)
    assets = _root(root) / ARTIFACT_ROOT
    with _LOCK, _file_transaction(root):
        _reclaim_stages(_root(root), feature)
        checked, refs = [], []
        for handle in artifacts:
            artifact_id = _artifact_key(handle["artifact_id"])
            digest = handle["content_sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise PackageError("content_mismatch")
            path = Path(handle["path"])
            cache_root = assets / ".cache" / artifact_id
            fixed = assets / artifact_id
            if path == fixed:
                _handle(path, artifact_id, digest)
                if _linked(assets / ".cache") or _linked(cache_root):
                    raise PackageError("unsafe_path")
                cache_root.mkdir(parents=True, exist_ok=True)
                cache = cache_root / digest
                if cache.exists():
                    try:
                        _handle(cache, artifact_id, digest)
                    except (PackageError, OSError):
                        cache = cache_root / (digest + "-" + uuid.uuid4().hex)
                if not cache.exists():
                    stage = cache_root / (".stage-" + uuid.uuid4().hex)
                    try:
                        shutil.copytree(path, stage)
                        _handle(stage, artifact_id, digest)
                        os.replace(stage, cache)
                    finally:
                        if stage.exists():
                            shutil.rmtree(stage)
                path = cache
            elif path.parent != cache_root or not _valid_cache_key(path.name, digest):
                raise PackageError("unsafe_path")
            checked.append(_handle(path, artifact_id, digest))
            refs.append({"artifact_id": artifact_id, "content_sha256": digest,
                         "source": "cache", "cache_key": path.name})
        by_id = _validate_group(feature, checked)
        runtime = Path(by_id[feature + "_runtime"]["path"])
        env = None
        if feature == "relogin_ocr":
            env = {"CAMPUS_OCR_MODEL_ROOT": str(Path(by_id["relogin_ocr_model"]["path"]) / "models")}
        _helper(runtime / "feature-helper.exe", feature=feature, probe=True, env=env)
        if feature == "phone_control":
            tool = Path(by_id["phone_control_cloudflared"]["path"]) / CLOUDFLARED_NAME
            if parse_cloudflared_version(probe_cloudflared_version(tool)) != CLOUDFLARED_VERSION:
                raise PackageError("tool_probe_failed")
        _write_group_pointer(feature, {"feature": feature, "artifacts": refs}, root)
        return {"ok": True, "feature": feature, "artifacts": by_id}


@_transactional
def selected_install_dir(feature, *, root=None):
    state = _split_group(feature, root=root)
    if state.get("available"):
        return Path(state["artifacts"][feature + "_runtime"]["path"])
    return install_dir(feature, root=root)


def inspect_artifact(archive, artifact_id):
    """只读识别 schema2 资产，供下载服务在落盘前复核。"""
    path = Path(archive)
    try:
        with zipfile.ZipFile(path) as package:
            info = package.getinfo("manifest.json")
            if info.file_size > 2 * 1024 * 1024:
                raise PackageError("manifest_limit")
            manifest = _artifact_manifest(package.read(info), artifact_id)
    except (OSError, zipfile.BadZipFile, KeyError, PackageError, ValueError) as exc:
        return {"ok": False, "kind": str(exc.args[0] if exc.args else "bad_artifact"),
                "artifact_id": artifact_id, "text": "拆分组件资产清单不合法。"}
    return {"ok": True, "kind": "artifact", "artifact_id": artifact_id,
            "feature": manifest["feature"], "role": manifest["role"],
            "version": manifest["asset_version"],
            "content_sha256": artifact_content_sha256(manifest),
            "compatibility_id": manifest["compatibility_id"],
            "text": "拆分组件资产清单有效。"}


def _has_split_assets(base, feature):
    """磁盘上有没有这个功能的拆分资产：固定目录或缓存里任一份都算。"""
    assets = base / ARTIFACT_ROOT
    for artifact_id, spec in ARTIFACTS.items():
        if spec["feature"] != feature:
            continue
        if (assets / artifact_id).exists():
            return True
        cache = assets / ".cache" / artifact_id
        try:
            if any(cache.iterdir()):
                return True
        except OSError:
            continue
    return False


def _split_group(feature, *, root=None, allow_cache=True):
    feature = _key(feature)
    _recover_replacement(_root(root), feature)
    pointer = _group_pointer(feature, root)
    if pointer.exists() or _linked(pointer):
        try:
            selection = json.loads(pointer.read_text(encoding="utf-8")) if not _linked(pointer) else {}
            if (isinstance(selection, dict) and selection.get("feature") == feature
                    and selection.get("selection") == "legacy"
                    and ("transaction_id" not in selection or
                         (isinstance(selection["transaction_id"], str) and
                          re.fullmatch(r"[0-9a-f]{32}", selection["transaction_id"])) )):
                return {"available": False, "source": "legacy", "feature": feature,
                        "error": "", "artifacts": {}}
            by_id = _resolve_group(feature, root=root, allow_cache=allow_cache)
            runtime = by_id[feature + "_runtime"]
            return {"available": True, "source": "split", "feature": feature,
                    "error": "", "version": runtime["version"],
                    "compatibility_id": runtime["compatibility_id"], "artifacts": by_id}
        except (PackageError, OSError, ValueError, KeyError, TypeError):
            return {"available": False, "source": "split", "feature": feature,
                    "error": "artifact_invalid", "artifacts": {}}
    if not _has_split_assets(_root(root), feature):
        # 全新未安装：既没有旧单体包也没有半套拆分资产，不能报成装坏
        return {"available": False, "source": "none", "feature": feature,
                "error": "", "artifacts": {}}
    ids = [artifact_id for artifact_id, spec in ARTIFACTS.items()
           if spec["feature"] == feature]
    states = [artifact_status(artifact_id, root=root) for artifact_id in ids]
    if feature == "relogin_ocr":
        required = {"relogin_ocr_runtime", "relogin_ocr_model"}
    else:
        required = {"phone_control_runtime"}
    by_id = {state["artifact_id"]: state for state in states}
    if not required.issubset({key for key, state in by_id.items() if state["available"]}):
        return {"available": False, "source": "split", "feature": feature,
                "error": "artifact_incomplete", "artifacts": by_id}
    compatibility = {by_id[key].get("compatibility_id") for key in required}
    if len(compatibility) != 1:
        return {"available": False, "source": "split", "feature": feature,
                "error": "artifact_incompatible", "artifacts": by_id}
    return {"available": True, "source": "split", "feature": feature,
            "error": "", "version": next(iter({by_id[key]["version"] for key in required})),
            "compatibility_id": next(iter(compatibility)), "artifacts": by_id}


@_transactional
def feature_status(key, *, root=None):
    """优先返回完整拆分组，组不完整时退回旧单体 feature 包。"""
    split = _split_group(key, root=root)
    if split["available"]:
        return split
    legacy = status(key, root=root)
    if legacy.get("available"):
        legacy["source"] = "legacy"
        legacy["split"] = split
        return legacy
    if not split.get("error") and legacy.get("error"):
        # 拆分资产没留痕，但旧单体包在且校验不过：那是真实故障，不能报成未安装
        legacy["split"] = split
        return legacy
    return split


@_transactional
def remove(key, *, root=None):
    with _LOCK, _file_transaction(root):
        base = _root(root)
        feature = _key(key)
        _assert_unused(feature, root)
        target = base / feature
        _recover_replacement(base, feature)
        _reclaim_stages(base, feature)
        if _linked(base) or _linked(target):
            raise PackageError("unsafe_path")
        if target.exists():
            shutil.rmtree(target)
        backup = base / (".backup-" + feature)
        if backup.exists():
            shutil.rmtree(backup)
        _STATUS_CACHE.pop(str(target), None)
        assets = base / ARTIFACT_ROOT
        pointer = _group_pointer(feature, root)
        if _linked(pointer) or _linked(pointer.parent):
            raise PackageError("unsafe_path")
        if pointer.exists():
            pointer.unlink()
        for artifact_id, spec in ARTIFACTS.items():
            if spec["feature"] != feature:
                continue
            cache = assets / ".cache" / artifact_id
            if _linked(cache):
                raise PackageError("unsafe_path")
            if cache.exists():
                shutil.rmtree(cache)
            _recover_artifact_replacement(base, artifact_id)
            artifact = assets / artifact_id
            if artifact.exists():
                if _linked(artifact):
                    raise PackageError("unsafe_path")
                shutil.rmtree(artifact)
        return {"ok": True, "text": "组件已移除；本机保存的账号可另行清除。"}


@_transactional
def invoke(key, payload, *, root=None):
    with _LOCK:
        feature = _key(key)
        split = _split_group(feature, root=root, allow_cache=False)
        if split["available"]:
            runtime = Path(split["artifacts"][feature + "_runtime"]["path"])
            env = None
            if feature == "relogin_ocr":
                env = {"CAMPUS_OCR_MODEL_ROOT": str(Path(split["artifacts"]["relogin_ocr_model"]["path"]) / "models")}
            try:
                return _helper(runtime / "feature-helper.exe", feature=feature, payload=payload, env=env)
            except (PackageError, OSError):
                pass
        directory = _root(root) / feature
        validate_directory(directory, feature)
        return _helper(directory / "feature-helper.exe", feature=feature, payload=payload)


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
    return parse_cloudflared_version((done.stdout or "") + " " + (done.stderr or ""))


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
    probe_text = probe_text or cloudflared_version_text
    path = Path(source)
    if not path.is_file():
        return {"ok": False, "kind": "missing", "version": "",
                "text": "没有找到这个文件，可能刚被移动或删除，请重新选择。"}
    if path.suffix.lower() != ".exe":
        return {"ok": False, "kind": "not_executable", "version": "",
                "text": "这里需要 cloudflared 的 Windows 可执行文件（.exe），不是这个文件。"}
    output = probe_text(path)
    found = parse_cloudflared_version(output)
    if found:
        if found != CLOUDFLARED_VERSION:
            return {"ok": False, "kind": "version", "version": found,
                    "text": "这份 cloudflared 是 %s，本程序按 %s 校验，版本不一致。"
                            "请换官方发布的 %s。" % (found, CLOUDFLARED_VERSION, CLOUDFLARED_VERSION)}
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


@_transactional
def install_cloudflared(source, *, root=None, probe=None, probe_text=None) -> dict:
    """把用户选定的 cloudflared 收进受管目录，并记下版本与哈希。

    校验不过一律抛 PackageError，原目录保持不动（不会出现「装了一半」）。
    """
    _assert_unused("phone_control", root)
    info = inspect_cloudflared(source, probe_text=probe_text)
    if not info["ok"]:
        raise PackageError(info["kind"])
    probe = probe or probe_cloudflared_version
    with _LOCK:
        base = _root(root)
        if _linked(base):
            raise PackageError("unsafe_path")
        base.mkdir(parents=True, exist_ok=True)
        # 上一次换位可能停在「store 已挪走、stage 还没落位」：先恢复再开装
        _recover_cloudflared_store(base)
        store = base / CLOUDFLARED_STORE
        stage = Path(tempfile.mkdtemp(prefix=".stage-cf-", dir=base))
        try:
            target = stage / CLOUDFLARED_FILE
            shutil.copy2(source, target)
            version = parse_cloudflared_version(probe(target))
            if version != CLOUDFLARED_VERSION:
                # 复制之后重新跑一次：选文件时的结论不能代表落盘后的这一份
                raise PackageError("cloudflared_version")
            manifest = {"schema": 1, "version": version, "sha256": sha256(target),
                        "filename": CLOUDFLARED_FILE}
            (stage / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            backup = store.with_name(CLOUDFLARED_STORE + ".bak")
            if store.exists():
                if _linked(store):
                    raise PackageError("unsafe_path")
                os.replace(store, backup)
            try:
                os.replace(stage, store)
            except OSError:
                if backup.exists():
                    os.replace(backup, store)
                raise
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            return {"ok": True, "version": version,
                    "text": "cloudflared %s 已收好，Cloudflare 通道现在可用。" % version}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def _recover_cloudflared_store(base):
    """进程在受管 cloudflared 换位中断时，把 .bak 恢复成正式目录。

    换位顺序是 store → .bak、stage → store；在两步之间崩溃就只剩 .bak。
    不恢复的话，读取方会把「已经装好」当成没装，用户还得重新选一次文件。
    """
    store = base / CLOUDFLARED_STORE
    backup = store.with_name(CLOUDFLARED_STORE + ".bak")
    if _linked(base) or _linked(store) or _linked(backup):
        raise PackageError("unsafe_path")
    if backup.exists() and not store.exists():
        os.replace(backup, store)
    elif backup.exists() and store.exists():
        if not backup.is_dir():
            raise PackageError("unsafe_path")
        shutil.rmtree(backup, ignore_errors=True)


@_transactional
def stored_cloudflared(*, root=None, probe=None) -> str:
    """返回受管目录里那份 cloudflared 的路径；版本或哈希对不上就返回空串。"""
    probe = probe or probe_cloudflared_version
    with _LOCK:
        base = _root(root)
        try:
            _recover_cloudflared_store(base)
        except (PackageError, OSError):
            return ""
        _reclaim_stages(base)
        store = base / CLOUDFLARED_STORE
        target = store / CLOUDFLARED_FILE
        try:
            if not target.is_file() or _linked(target):
                return ""
            manifest = json.loads((store / "manifest.json").read_text(encoding="utf-8"))
            if parse_cloudflared_version(manifest.get("version")) != CLOUDFLARED_VERSION:
                return ""
            if str(manifest.get("sha256") or "") != sha256(target):
                return ""
            if parse_cloudflared_version(probe(target)) != CLOUDFLARED_VERSION:
                return ""
            return str(target)
        except (OSError, ValueError):
            return ""


@_transactional
def remove_cloudflared(*, root=None) -> dict:
    with _LOCK:
        _assert_unused("phone_control", root)
        base = _root(root)
        store = base / CLOUDFLARED_STORE
        if _linked(base) or _linked(store):
            raise PackageError("unsafe_path")
        _recover_cloudflared_store(base)
        if store.exists():
            shutil.rmtree(store)
        return {"ok": True, "text": "已移除单独安装的 cloudflared。"}


def inspect_archive(archive, key) -> dict:
    """只读自检：这个 ZIP 是不是该类组件包。不安装、不落盘。

    用户可能拿错包（重登的包当成手机控制、或者根本不是本程序的组件），
    所以先读 manifest 的 feature 字段，给出「这是哪个组件包」这种能对得上话的结论。
    """
    path = Path(archive)
    if not path.is_file():
        return {"ok": False, "kind": "missing", "feature": "",
                "text": "没有找到这个文件，可能刚被移动或删除，请重新选择。"}
    if path.suffix.lower() != ".zip":
        return {"ok": False, "kind": "not_zip", "feature": "",
                "text": "这里需要组件包 ZIP（.zip），不是这个文件。"}
    if path.stat().st_size > MAX_ARCHIVE:
        return {"ok": False, "kind": "archive_limit", "feature": "",
                "text": "这个 ZIP 超过 %d 字节上限，不像是本程序的组件包。" % MAX_ARCHIVE}
    try:
        with zipfile.ZipFile(path) as package:
            names = {name.lower(): name for name in package.namelist()}
            if "manifest.json" not in names:
                return {"ok": False, "kind": "not_component", "feature": "",
                        "text": "这个 ZIP 里没有组件清单（manifest.json），不是本程序的组件包。"}
            info = package.getinfo(names["manifest.json"])
            if info.file_size > 2 * 1024 * 1024:
                return {"ok": False, "kind": "manifest_limit", "feature": "",
                        "text": "组件清单过大，这个 ZIP 不像正常组件包。"}
            blob = package.read(info)
            raw = json.loads(blob.decode("utf-8"))
    except (zipfile.BadZipFile, OSError, ValueError, UnicodeDecodeError):
        return {"ok": False, "kind": "bad_zip", "feature": "",
                "text": "这个 ZIP 打不开或清单损坏，请重新获取组件包。"}
    feature = str((raw or {}).get("feature") or "")
    title = {"phone_control": "手机控制", "relogin_ocr": "验证码识别"}
    if feature not in FEATURES:
        return {"ok": False, "kind": "unknown_feature", "feature": feature,
                "text": "这个 ZIP 的组件类型是「%s」，不是本程序认识的组件。" % (feature or "未声明")}
    if feature != str(key):
        return {"ok": False, "kind": "wrong_feature", "feature": feature,
                "text": "这是「%s」的组件包，不是这里要装的「%s」。"
                        % (title.get(feature, feature), title.get(str(key), str(key)))}
    try:
        manifest = _manifest(blob, str(key))
    except PackageError as exc:
        return {"ok": False, "kind": str(exc.args[0] if exc.args else "bad_manifest"),
                "feature": feature,
                "text": "组件清单不合法（%s），请用与当前版本配套的组件包。"
                        % (exc.args[0] if exc.args else "bad_manifest")}
    return {"ok": True, "kind": "component", "feature": feature,
            "version": str(manifest.get("version") or ""),
            "cloudflared": str((manifest.get("cloudflared") or {}).get("version") or ""),
            "text": "已识别为「%s」组件包。" % title.get(feature, feature)}


@_transactional
def cloudflared(*, root=None, probe=None):
    """返回可用的 cloudflared 路径；版本不符、缺文件、probe 失败都返回空串。"""
    probe = probe or probe_cloudflared_version
    group = _split_group("phone_control", root=root, allow_cache=False)
    split_tool = group.get("artifacts", {}).get("phone_control_cloudflared", {}) if group.get("available") else {}
    if not _group_pointer("phone_control", root).exists() and not split_tool:
        split_tool = artifact_status("phone_control_cloudflared", root=root)
    if split_tool.get("available"):
        target = Path(split_tool["path"]) / CLOUDFLARED_NAME
        if parse_cloudflared_version(probe(target)) == CLOUDFLARED_VERSION:
            return str(target)
    with _LOCK:
        directory = _root(root) / "phone_control"
        try:
            manifest = validate_directory(directory, "phone_control")
            declared = (manifest.get("cloudflared") or {}).get("version") or ""
            if parse_cloudflared_version(declared) != CLOUDFLARED_VERSION:
                return ""
            if CLOUDFLARED_NAME not in manifest["files"]:
                return ""
            target = directory / CLOUDFLARED_NAME
            if parse_cloudflared_version(probe(target)) != CLOUDFLARED_VERSION:
                return ""
            return str(target)
        except (PackageError, OSError):
            pass
    # 组件包之外还有一条合法来源：用户在对话框里亲自选过、且校验通过的那份
    return stored_cloudflared(root=root, probe=probe)
