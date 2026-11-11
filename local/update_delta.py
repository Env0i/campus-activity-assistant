"""纯标准库的版本目录文件级增量包。

增量包只描述 onedir 文件，不修改运行中的程序和独立数据目录。应用过程先在
临时 staging 中复制、校验目标 manifest，最后才一次切换 staging；任何失败都
保留调用方原有目录。
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import stat
import tempfile
import uuid
import zipfile


FORMAT = "campus-activity-delta-v1"
MANIFEST_NAME = "manifest.json"
FILES_PREFIX = "files/"
_SHA256_LENGTH = 64


class DeltaError(ValueError):
    """增量包格式、路径或校验失败。"""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def validate_relative_path(value: str) -> str:
    """校验归档和 manifest 使用的 POSIX 相对路径。"""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise DeltaError("非法相对路径")
    if "\\" in value:
        raise DeltaError("路径不能包含反斜杠")
    if value.startswith("/") or PurePosixPath(value).is_absolute():
        raise DeltaError("路径不能是绝对路径")
    if PureWindowsPath(value).drive or PureWindowsPath(value).root:
        raise DeltaError("路径不能包含盘符")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise DeltaError("路径包含目录逃逸或空段")
    if any(":" in part for part in parts):
        # NTFS 备用数据流（文件名:流名）会把内容写进别的文件的隐藏流，正常文件名不含冒号
        raise DeltaError("路径不能包含冒号")
    return value


def _ensure_directory(root: Path) -> Path:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise DeltaError("目录不存在或是符号链接：%s" % root)
    return root


def _iter_files(root: Path):
    root = _ensure_directory(root)
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(dirs)
        names = sorted(names)
        for name in dirs:
            child = current_path / name
            if child.is_symlink():
                raise DeltaError("目录不能包含符号链接：%s" % child)
        for name in names:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                raise DeltaError("文件必须是普通文件：%s" % child)
            relative = child.relative_to(root).as_posix()
            yield validate_relative_path(relative), child


def _file_entry(relative: str, path: Path) -> dict:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            digest.update(block)
    return {"path": relative, "bytes": size, "sha256": digest.hexdigest()}


def _manifest_core(manifest: dict) -> dict:
    return {"version": manifest["version"], "files": manifest["files"]}


def _manifest_hash(manifest: dict) -> str:
    return _digest(_manifest_core(manifest))


def manifest_from_directory(directory, *, version: str | None = None,
                            base_version: str | None = None) -> dict:
    """生成目录文件清单；文件条目按稳定的 POSIX 路径排序。"""
    root = _ensure_directory(Path(directory))
    entries = sorted((_file_entry(relative, path) for relative, path in _iter_files(root)),
                     key=lambda item: item["path"])
    result = {"version": version or "", "files": entries}
    if base_version is not None:
        result["base_version"] = base_version
    result["target_manifest_sha256"] = _manifest_hash(result)
    return result


def _strip_internal(value: dict) -> dict:
    return {key: item for key, item in value.items() if not key.startswith("_")}


def _validate_file_entries(entries, *, field: str) -> list[dict]:
    if not isinstance(entries, list):
        raise DeltaError("%s 必须是列表" % field)
    result = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise DeltaError("%s 条目不是对象" % field)
        path = validate_relative_path(entry.get("path"))
        if path in seen:
            raise DeltaError("%s 包含重复路径" % field)
        seen.add(path)
        size = entry.get("bytes")
        digest = entry.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise DeltaError("%s 的 bytes 无效" % field)
        if not isinstance(digest, str) or len(digest) != _SHA256_LENGTH:
            raise DeltaError("%s 的 sha256 无效" % field)
        try:
            int(digest, 16)
        except ValueError as exc:
            raise DeltaError("%s 的 sha256 无效" % field) from exc
        result.append({"path": path, "bytes": size, "sha256": digest.lower()})
    return sorted(result, key=lambda item: item["path"])


def _validate_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("format") not in (None, FORMAT):
        raise DeltaError("未知增量包格式")
    for key in ("version", "base_version"):
        if not isinstance(manifest.get(key), str) or not manifest[key]:
            raise DeltaError("manifest.%s 无效" % key)
    files = _validate_file_entries(manifest.get("files"), field="files")
    deletions = manifest.get("deletions")
    if not isinstance(deletions, list):
        raise DeltaError("deletions 必须是列表")
    deletions = sorted({validate_relative_path(path) for path in deletions})
    if set(deletions) & {entry["path"] for entry in files}:
        raise DeltaError("同一路径不能同时替换和删除")
    target = manifest.get("target_manifest")
    if not isinstance(target, dict):
        raise DeltaError("缺少 target_manifest")
    if not isinstance(target.get("version"), str) or target["version"] != manifest["version"]:
        raise DeltaError("target_manifest 版本不一致")
    target_files = _validate_file_entries(target.get("files"), field="target_manifest.files")
    target = {"version": target["version"], "files": target_files}
    target_hash = manifest.get("target_manifest_sha256")
    if not isinstance(target_hash, str) or target_hash.lower() != _manifest_hash(target):
        raise DeltaError("target_manifest_sha256 校验失败")
    result = dict(manifest)
    result["format"] = FORMAT
    result["files"] = files
    result["deletions"] = deletions
    result["target_manifest"] = target
    result["target_manifest_sha256"] = target_hash.lower()
    return result


def build_delta(base_dir, target_dir, base_version: str, target_version: str,
                *, output=None) -> dict:
    """比较两个版本目录，返回可序列化的增量 manifest。"""
    if not isinstance(base_version, str) or not base_version:
        raise DeltaError("base_version 无效")
    if not isinstance(target_version, str) or not target_version:
        raise DeltaError("target_version 无效")
    base = manifest_from_directory(base_dir, version=base_version)
    target = manifest_from_directory(target_dir, version=target_version)
    old = {item["path"]: item for item in base["files"]}
    new = {item["path"]: item for item in target["files"]}
    changed = [new[path] for path in sorted(new)
               if path not in old or old[path]["sha256"] != new[path]["sha256"]
               or old[path]["bytes"] != new[path]["bytes"]]
    deletions = sorted(set(old) - set(new))
    result = {
        "format": FORMAT,
        "version": target_version,
        "base_version": base_version,
        "files": changed,
        "deletions": deletions,
        "target_manifest": _strip_internal(target),
        "target_manifest_sha256": target["target_manifest_sha256"],
        "base_manifest_sha256": base["target_manifest_sha256"],
        "_target_dir": str(Path(target_dir).resolve()),
    }
    if output is not None:
        write_delta_zip(result, output, target_dir=target_dir)
    return result


def _load_archive(archive: Path):
    extraction = Path(tempfile.mkdtemp(prefix="campus-delta-"))
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            infos = zf.infolist()
            names = {info.filename for info in infos}
            if MANIFEST_NAME not in names:
                raise DeltaError("增量 ZIP 缺少 manifest.json")
            for info in infos:
                name = info.filename
                if name.endswith("/"):
                    raise DeltaError("增量 ZIP 不允许目录条目")
                if name != MANIFEST_NAME:
                    if not name.startswith(FILES_PREFIX):
                        raise DeltaError("增量 ZIP 存在未知条目")
                    validate_relative_path(name[len(FILES_PREFIX):])
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise DeltaError("增量 ZIP 不允许符号链接")
            try:
                manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
                raise DeltaError("增量 ZIP 的 manifest 损坏") from exc
            manifest = _validate_manifest(manifest)
            expected = {MANIFEST_NAME} | {
                FILES_PREFIX + item["path"] for item in manifest["files"]
            }
            if names != expected:
                raise DeltaError("增量 ZIP 文件条目与 manifest 不一致")
            declared = {FILES_PREFIX + item["path"]: item["bytes"]
                        for item in manifest["files"]}
            for info in infos:
                if info.filename == MANIFEST_NAME:
                    continue
                # 解出之前先比大小：条目实际大小超过清单声明就拒绝，防压缩炸弹撑满磁盘
                if info.file_size > declared[info.filename]:
                    raise DeltaError("增量 ZIP 条目超过清单声明的大小")
                target = extraction / info.filename[len(FILES_PREFIX):]
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as handle:
                    handle.write(zf.read(info))
        return manifest, extraction, True
    except zipfile.BadZipFile as exc:
        shutil.rmtree(extraction, ignore_errors=True)
        raise DeltaError("增量 ZIP 损坏") from exc
    except Exception:
        shutil.rmtree(extraction, ignore_errors=True)
        raise


def _delta_parts(delta, payload_dir=None):
    if isinstance(delta, (str, Path)):
        return _load_archive(Path(delta))
    if isinstance(delta, dict) and isinstance(delta.get("manifest"), dict):
        delta = delta["manifest"]
    if not isinstance(delta, dict):
        raise DeltaError("delta 必须是 manifest 或 ZIP 路径")
    manifest = _validate_manifest(delta)
    payload = payload_dir or manifest.get("_target_dir")
    if not payload:
        raise DeltaError("内存 delta 缺少目标 payload")
    return manifest, Path(payload), False


def verify_directory(directory, manifest: dict) -> bool:
    """按 manifest 比较目录；不一致返回 False，格式错误抛 DeltaError。"""
    if not isinstance(manifest, dict):
        raise DeltaError("目标 manifest 无效")
    expected = _validate_file_entries(manifest.get("files"), field="target_manifest.files")
    actual = manifest_from_directory(directory, version=manifest.get("version", ""))
    return actual["files"] == expected


def apply_delta(base_dir, delta, staging_dir, *, base_version: str | None = None,
                payload_dir=None) -> bool:
    """在临时目录构造目标版本，成功后替换 staging_dir。"""
    base = _ensure_directory(Path(base_dir))
    staging = Path(staging_dir)
    manifest, payload_root, cleanup_payload = _delta_parts(delta, payload_dir=payload_dir)
    work = staging.parent / (staging.name + ".part-" + uuid.uuid4().hex)
    backup = staging.parent / (staging.name + ".backup-" + uuid.uuid4().hex)
    try:
        expected_base_version = base_version if base_version is not None else manifest["base_version"]
        if expected_base_version != manifest["base_version"]:
            raise DeltaError("基础版本不匹配")
        if "base_manifest_sha256" in manifest:
            current = manifest_from_directory(base, version=manifest["base_version"])
            if current["target_manifest_sha256"] != manifest["base_manifest_sha256"]:
                raise DeltaError("基础目录 manifest 不匹配")
        target_manifest = manifest["target_manifest"]
        _validate_manifest({
            "format": FORMAT,
            "version": target_manifest["version"],
            "base_version": manifest["base_version"],
            "files": [],
            "deletions": [],
            "target_manifest": target_manifest,
            "target_manifest_sha256": manifest["target_manifest_sha256"],
        })
        shutil.copytree(base, work, symlinks=False)
        for relative in manifest["deletions"]:
            path = work / relative
            if path.is_symlink() or (path.exists() and not path.is_file()):
                raise DeltaError("删除目标不是普通文件")
            if path.exists():
                path.unlink()
        for entry in manifest["files"]:
            source = payload_root / entry["path"]
            if source.is_symlink() or not source.is_file():
                raise DeltaError("delta payload 缺少普通文件：%s" % entry["path"])
            actual = _file_entry(entry["path"], source)
            if actual != entry:
                raise DeltaError("delta payload 哈希或大小错误：%s" % entry["path"])
            destination = work / entry["path"]
            if destination.exists() and not destination.is_file():
                raise DeltaError("替换目标不是普通文件")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        if not verify_directory(work, target_manifest):
            raise DeltaError("应用后目标 manifest 不一致")
        if staging.exists() or staging.is_symlink():
            if staging.is_symlink() or not staging.is_dir():
                raise DeltaError("staging 不是目录")
            os.replace(staging, backup)
        try:
            os.replace(work, staging)
        except Exception:
            if backup.exists() and not staging.exists():
                os.replace(backup, staging)
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        return True
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        if backup.exists() and not staging.exists():
            os.replace(backup, staging)
        elif backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        raise
    finally:
        if cleanup_payload:
            shutil.rmtree(payload_root, ignore_errors=True)


def write_delta_zip(delta: dict, output, *, target_dir=None) -> Path:
    """把 build_delta 结果写成 ZIP；只写 output 指定的文件及其父目录。"""
    manifest = _validate_manifest(delta)
    source = Path(target_dir or delta.get("_target_dir", ""))
    _ensure_directory(source)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    part = output_path.with_name(output_path.name + ".part")
    try:
        with zipfile.ZipFile(part, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_NAME, _canonical_json(_strip_internal(manifest)))
            for entry in manifest["files"]:
                path = source / entry["path"]
                if path.is_symlink() or not path.is_file():
                    raise DeltaError("目标 payload 缺少普通文件：%s" % entry["path"])
                zf.write(path, FILES_PREFIX + entry["path"])
        os.replace(part, output_path)
        return output_path
    except Exception:
        part.unlink(missing_ok=True)
        raise


__all__ = [
    "DeltaError", "apply_delta", "build_delta", "manifest_from_directory",
    "validate_relative_path", "verify_directory", "write_delta_zip",
]
