# -*- coding: utf-8 -*-
"""固定高级组件 ZIP 的校验、替换及隔离 helper 调用。

SHA256 只验证完整性，用户必须自行确认组件来源可信。
@author Author
"""
from __future__ import annotations

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
import uuid
import zipfile
from pathlib import Path, PurePosixPath

FEATURES = {"phone_control", "relogin_ocr"}
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


def _key(key):
    if key not in FEATURES:
        raise PackageError("unknown_feature")
    return key


def install_dir(key, *, root=None):
    """组件的安装目录（数据目录下 advanced/<功能>）；只给电脑端的位置接口用，不查磁盘。"""
    return _root(root) / _key(key)


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


def _helper(executable, *, feature, payload=None, timeout=30, probe=False):
    """用有界 reader 防止 helper stdout/stderr 无限堆进主进程内存。"""
    body = b"" if probe else json.dumps(payload, ensure_ascii=True).encode("utf-8")
    if len(body) > 2 * 1024 * 1024 + 4096:
        raise PackageError("input_limit")
    args = [str(executable)] + (["--probe"] if probe else [])
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
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


def _recover_replacement(base, key):
    """进程在目录换位中断时，先恢复同一组件的旧目录再判断是否可用。"""
    target = base / key
    backup = base / (".backup-" + key)
    if _linked(base) or _linked(target) or _linked(backup):
        raise PackageError("unsafe_path")
    if backup.exists() and not target.exists():
        os.replace(backup, target)
        _STATUS_CACHE.pop(str(target), None)


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


def install(archive, key, *, root=None):
    with _LOCK:
        _key(key)
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
        stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=base))
        target = base / key
        backup = base / (".backup-" + key)
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
            _STATUS_CACHE.pop(str(target), None)
            return {"ok": True, "feature": key, "text": "组件已导入并启用。"}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def remove(key, *, root=None):
    with _LOCK:
        base = _root(root)
        target = base / _key(key)
        _recover_replacement(base, key)
        if _linked(base) or _linked(target):
            raise PackageError("unsafe_path")
        if target.exists():
            shutil.rmtree(target)
        backup = base / (".backup-" + key)
        if backup.exists():
            shutil.rmtree(backup)
        _STATUS_CACHE.pop(str(target), None)
        return {"ok": True, "text": "组件已移除；本机保存的账号可另行清除。"}


def invoke(key, payload, *, root=None):
    with _LOCK:
        directory = _root(root) / _key(key)
        validate_directory(directory, key)
        return _helper(directory / "feature-helper.exe", feature=key, payload=payload)


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


def install_cloudflared(source, *, root=None, probe=None, probe_text=None) -> dict:
    """把用户选定的 cloudflared 收进受管目录，并记下版本与哈希。

    校验不过一律抛 PackageError，原目录保持不动（不会出现「装了一半」）。
    """
    info = inspect_cloudflared(source, probe_text=probe_text)
    if not info["ok"]:
        raise PackageError(info["kind"])
    probe = probe or probe_cloudflared_version
    with _LOCK:
        base = _root(root)
        if _linked(base):
            raise PackageError("unsafe_path")
        base.mkdir(parents=True, exist_ok=True)
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


def stored_cloudflared(*, root=None, probe=None) -> str:
    """返回受管目录里那份 cloudflared 的路径；版本或哈希对不上就返回空串。"""
    probe = probe or probe_cloudflared_version
    store = _root(root) / CLOUDFLARED_STORE
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


def remove_cloudflared(*, root=None) -> dict:
    with _LOCK:
        base = _root(root)
        store = base / CLOUDFLARED_STORE
        if _linked(base) or _linked(store):
            raise PackageError("unsafe_path")
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


def cloudflared(*, root=None, probe=None):
    """返回可用的 cloudflared 路径；版本不符、缺文件、probe 失败都返回空串。"""
    probe = probe or probe_cloudflared_version
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
