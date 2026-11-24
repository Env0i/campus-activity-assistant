# -*- coding: utf-8 -*-
"""组件清单、路径校验与只读自检。

@author Author
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath

_cp = None


def bind(facade) -> None:
    """绑定 component_packages 门面，确保运行时走门面读取常量与替身。"""
    global _cp
    _cp = facade


def parse_cloudflared_version(text) -> str:
    """从 `cloudflared --version` 的输出里取语义版本；取不到返回空串。"""
    found = _cp._CLOUDFLARED_VERSION_RE.search(str(text or ""))
    return found.group(1) if found else ""


def supported():
    return sys.platform == "win32" and struct.calcsize("P") == 8 and platform.machine().lower() in (
        "amd64", "x86_64")


def version():
    candidates = [Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "VERSION",
                  Path(__file__).resolve().parents[3] / "VERSION"]
    for path in candidates:
        if path.is_file():
            value = path.read_text(encoding="utf-8").strip()
            if re.fullmatch(r"\d+\.\d+\.\d+", value):
                return value
    raise _cp.PackageError("version_missing")


def _key(key):
    if key not in _cp.FEATURES:
        raise _cp.PackageError("unknown_feature")
    return key


def _artifact_key(artifact_id):
    if artifact_id not in _cp.ARTIFACTS:
        raise _cp.PackageError("unknown_artifact")
    return artifact_id


def _linked(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def _name(name):
    if (not isinstance(name, str) or not name or "\\" in name or ":" in name
            or name.startswith("/") or any(ord(c) < 32 for c in name)):
        raise _cp.PackageError("unsafe_path")
    parts = name.split("/")
    for part in parts:
        if (part in ("", ".", "..") or part.rstrip(" .") != part
                or any(c in part for c in '<>"|?*')
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)):
            raise _cp.PackageError("unsafe_path")
    if PurePosixPath(name).is_absolute():
        raise _cp.PackageError("unsafe_path")
    return name


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_unique_json(raw):
    if len(raw) > 2 * 1024 * 1024:
        raise _cp.PackageError("manifest_limit")

    def unique(pairs):
        out = {}
        for name, value in pairs:
            if name in out:
                raise _cp.PackageError("duplicate_key")
            out[name] = value
        return out

    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        raise _cp.PackageError("bad_manifest") from exc


def _validate_manifest_files(files):
    names = set()
    for name, digest in files.items():
        _name(name)
        folded = name.casefold()
        if (folded in names or folded == "manifest.json" or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise _cp.PackageError("bad_files")
        names.add(folded)


def _validate_manifest_cloudflared(data, key, files):
    cloudflare = data.get("cloudflared")
    if cloudflare is not None:
        if (not isinstance(cloudflare, dict)
                or not isinstance(cloudflare.get("version"), str)
                or not _cp.parse_cloudflared_version(cloudflare.get("version"))
                or not isinstance(cloudflare.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", cloudflare["sha256"])):
            raise _cp.PackageError("bad_manifest")
        digest = files.get(_cp.CLOUDFLARED_NAME)
        if key != "phone_control" or digest is None or digest != cloudflare["sha256"]:
            raise _cp.PackageError("bad_manifest")
        if _cp.parse_cloudflared_version(cloudflare["version"]) != _cp.CLOUDFLARED_VERSION:
            raise _cp.PackageError("cloudflared_version")
    elif key == "phone_control":
        # phone_control 必须内置 cloudflared：缺它就没有远程通道，不能先装上再说
        raise _cp.PackageError("cloudflared_required")
    elif _cp.CLOUDFLARED_NAME in files:
        # 有二进制却没声明版本：不能假装知道它是什么
        raise _cp.PackageError("bad_manifest")


def _manifest(raw, key, *, expect_version=None):
    data = _parse_unique_json(raw)
    want = _cp.version() if expect_version is None else expect_version
    if (not isinstance(data, dict) or type(data.get("schema")) is not int
            or data["schema"] != 1 or data.get("feature") != key
            or data.get("platform") != "windows-x64" or data.get("entry") != "feature-helper.exe"
            or data.get("version") != want or not isinstance(data.get("files"), dict)):
        raise _cp.PackageError("incompatible_manifest")
    files = data["files"]
    if not files or len(files) >= _cp.MAX_FILES or "feature-helper.exe" not in files:
        raise _cp.PackageError("bad_files")
    # 架构与配套主程序版本：可选字段，但一旦声明就必须自洽——下载流程会把它们
    # 当成「这个包能不能装在当前这台机器/这个版本上」的依据，含糊过去比缺字段更糟。
    target = data.get("target")
    if target is not None and target != "win-x64":
        raise _cp.PackageError("bad_target")
    app_version = data.get("app_version")
    if app_version is not None and app_version != data.get("version"):
        raise _cp.PackageError("bad_app_version")
    _validate_manifest_cloudflared(data, key, files)
    _validate_manifest_files(files)
    return data


def _artifact_manifest(raw, artifact_id):
    """校验 schema2 拆分资产清单；不把资产版本误当主程序版本。"""
    artifact_id = _artifact_key(artifact_id)
    if len(raw) > 2 * 1024 * 1024:
        raise _cp.PackageError("manifest_limit")
    try:
        data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    except (ValueError, UnicodeError) as exc:
        raise _cp.PackageError("bad_manifest") from exc
    spec = _cp.ARTIFACTS[artifact_id]
    if (not isinstance(data, dict) or data.get("schema") != _cp.ARTIFACT_SCHEMA
            or data.get("artifact_id") != artifact_id
            or data.get("feature") != spec["feature"]
            or data.get("role") != spec["role"]
            or data.get("protocol") != _cp.ARTIFACT_PROTOCOL
            or not isinstance(data.get("asset_version"), str)
            or not re.fullmatch(r"\d+\.\d+\.\d+", data["asset_version"])
            or not isinstance(data.get("compatibility_id"), str)
            or not data["compatibility_id"]
            or not isinstance(data.get("files"), dict)):
        raise _cp.PackageError("incompatible_artifact_manifest")
    if data.get("entry") != spec["entry"]:
        raise _cp.PackageError("bad_entry")
    if not isinstance(data.get("requires", []), list):
        raise _cp.PackageError("bad_requires")
    files = data["files"]
    if not files or len(files) >= _cp.MAX_FILES:
        raise _cp.PackageError("bad_files")
    _validate_manifest_files(files)
    if spec["entry"] and spec["entry"] not in files:
        raise _cp.PackageError("entry_missing")
    if spec["role"] == "tool":
        tool = data.get("tool")
        if (not isinstance(tool, dict) or tool.get("name") != "cloudflared"
                or _cp.parse_cloudflared_version(tool.get("version")) != _cp.CLOUDFLARED_VERSION
                or files.get(spec["entry"]) != tool.get("sha256")):
            raise _cp.PackageError("bad_tool")
    declared_content = data.get("content_sha256")
    if declared_content is not None and declared_content != _cp.artifact_content_sha256(data):
        raise _cp.PackageError("content_mismatch")
    return data


def _verify_directory_files(directory, manifest):
    actual = {}
    total = 0
    for path in directory.rglob("*"):
        if _linked(path):
            raise _cp.PackageError("unsafe_path")
        if path.is_file():
            relative = _name(path.relative_to(directory).as_posix())
            if relative.casefold() in actual:
                raise _cp.PackageError("duplicate_file")
            actual[relative.casefold()] = relative
            total += path.stat().st_size
    if len(actual) > _cp.MAX_FILES or total > _cp.MAX_EXTRACTED:
        raise _cp.PackageError("size_limit")
    if set(actual.values()) != set(manifest["files"]) | {"manifest.json"}:
        raise _cp.PackageError("file_mismatch")
    for name, digest in manifest["files"].items():
        if _cp.sha256(directory / name) != digest:
            raise _cp.PackageError("hash_mismatch")


def _read_dir_manifest_bytes(directory, missing_error):
    if _linked(directory) or _linked(directory.parent) or not directory.is_dir():
        raise _cp.PackageError(missing_error)
    manifest_path = directory / "manifest.json"
    if (not manifest_path.is_file() or _linked(manifest_path)
            or manifest_path.stat().st_size > 2 * 1024 * 1024):
        raise _cp.PackageError("bad_manifest")
    return manifest_path.read_bytes()


def validate_artifact_directory(directory, artifact_id):
    """校验 schema2 资产目录，不执行 runtime helper。"""
    directory = Path(directory)
    _artifact_key(artifact_id)
    raw = _read_dir_manifest_bytes(directory, "missing_artifact")
    manifest = _artifact_manifest(raw, artifact_id)
    _verify_directory_files(directory, manifest)
    return manifest


def validate_directory(directory, key, *, expect_version=None):
    directory = Path(directory)
    _key(key)
    raw = _read_dir_manifest_bytes(directory, "missing_component")
    manifest = _manifest(raw, key, expect_version=expect_version)
    _verify_directory_files(directory, manifest)
    return manifest


def _outdated_version(directory, key):
    """只差主程序版本的单体包返回已装版本，其余情况返回空串。

    主程序升级会把装好的单体包判成 incompatible_manifest，但用户看到的是
    「没装」——分不清是版本旧还是文件坏了，就会以为功能被卸载。这里把版本
    这一项放宽后重跑全部校验：文件、cloudflared、大小任何一处不对都仍返回
    空串，让调用方继续报 component_invalid，不能把坏包说成「旧包」。
    """
    try:
        raw = (directory / "manifest.json").read_bytes()
        declared = json.loads(raw.decode("utf-8"))
        installed = (declared or {}).get("version") if isinstance(declared, dict) else None
        if (not isinstance(installed, str) or installed == _cp.version()
                or not re.fullmatch(r"\d+\.\d+\.\d+", installed)):
            return ""
        _cp.validate_directory(directory, key, expect_version=installed)
        _cp._helper(directory / "feature-helper.exe", feature=key, probe=True)
    except (_cp.PackageError, OSError, ValueError, UnicodeError):
        return ""
    return installed


def artifact_content_sha256(manifest):
    keys = ("artifact_id", "feature", "role", "protocol", "compatibility_id",
            "entry", "requires", "tool", "files")
    content = {key: manifest[key] for key in keys if key in manifest}
    return hashlib.sha256(json.dumps(content, ensure_ascii=True, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def inspect_artifact(archive, artifact_id):
    """只读识别 schema2 资产，供下载服务在落盘前复核。"""
    path = Path(archive)
    try:
        with zipfile.ZipFile(path) as package:
            info = package.getinfo("manifest.json")
            if info.file_size > 2 * 1024 * 1024:
                raise _cp.PackageError("manifest_limit")
            manifest = _cp._artifact_manifest(package.read(info), artifact_id)
    except (OSError, zipfile.BadZipFile, KeyError, _cp.PackageError, ValueError) as exc:
        return {"ok": False, "kind": str(exc.args[0] if exc.args else "bad_artifact"),
                "artifact_id": artifact_id, "text": "拆分组件资产清单不合法。"}
    return {"ok": True, "kind": "artifact", "artifact_id": artifact_id,
            "feature": manifest["feature"], "role": manifest["role"],
            "version": manifest["asset_version"],
            "content_sha256": _cp.artifact_content_sha256(manifest),
            "compatibility_id": manifest["compatibility_id"],
            "text": "拆分组件资产清单有效。"}


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
    if path.stat().st_size > _cp.MAX_ARCHIVE:
        return {"ok": False, "kind": "archive_limit", "feature": "",
                "text": "这个 ZIP 超过 %d 字节上限，不像是本程序的组件包。" % _cp.MAX_ARCHIVE}
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
    if feature not in _cp.FEATURES:
        return {"ok": False, "kind": "unknown_feature", "feature": feature,
                "text": "这个 ZIP 的组件类型是「%s」，不是本程序认识的组件。" % (feature or "未声明")}
    if feature != str(key):
        return {"ok": False, "kind": "wrong_feature", "feature": feature,
                "text": "这是「%s」的组件包，不是这里要装的「%s」。"
                        % (title.get(feature, feature), title.get(str(key), str(key)))}
    try:
        manifest = _cp._manifest(blob, str(key))
    except _cp.PackageError as exc:
        return {"ok": False, "kind": str(exc.args[0] if exc.args else "bad_manifest"),
                "feature": feature,
                "text": "组件清单不合法（%s），请用与当前版本配套的组件包。"
                        % (exc.args[0] if exc.args else "bad_manifest")}
    return {"ok": True, "kind": "component", "feature": feature,
            "version": str(manifest.get("version") or ""),
            "cloudflared": str((manifest.get("cloudflared") or {}).get("version") or ""),
            "text": "已识别为「%s」组件包。" % title.get(feature, feature)}
