# -*- coding: utf-8 -*-
"""schema2 拆分资产缓存、指针组切换与功能级路由。

@author Author
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

_cp = None


def bind(facade) -> None:
    """绑定 component_packages 门面。"""
    global _cp
    _cp = facade


def _group_pointer(feature, root):
    return _cp._root(root) / _cp.ARTIFACT_ROOT / ".groups" / (_cp._key(feature) + ".json")


def _write_group_pointer(feature, data, root):
    _cp._atomic_json(_cp._group_pointer(feature, root), data)


def _valid_cache_key(cache_key, digest):
    return isinstance(cache_key, str) and bool(
        re.fullmatch(re.escape(digest) + r"(?:-[0-9a-f]{32})?", cache_key))


def _artifact_fingerprint(directory):
    paths = [directory, *sorted(directory.rglob("*"))]
    result = []
    for path in paths:
        if _cp._linked(path):
            raise _cp.PackageError("unsafe_path")
        info = path.stat(follow_symlinks=False)
        result.append((str(path.relative_to(directory)), info.st_size, info.st_mtime_ns,
                       info.st_ctime_ns, info.st_ino, info.st_mode,
                       getattr(info, "st_file_attributes", 0),
                       getattr(info, "st_reparse_tag", 0)))
    return tuple(result)


def _handle(directory, artifact_id, digest=None, *, allow_cache=False):
    directory = Path(directory)
    if any(_cp._linked(parent) for parent in list(directory.parents)[:3]):
        raise _cp.PackageError("unsafe_path")
    cache_key = (str(directory), artifact_id, digest)
    if not allow_cache:
        # 执行前重新核验时撤销展示缓存，失败后下一次展示也必须反映真实损坏。
        _cp._ARTIFACT_STATUS_CACHE.pop(cache_key, None)
    fingerprint = _cp._artifact_fingerprint(directory) if allow_cache else None
    cached = _cp._ARTIFACT_STATUS_CACHE.get(cache_key) if allow_cache else None
    if cached and cached[0] == fingerprint:
        return dict(cached[1])
    manifest = _cp.validate_artifact_directory(directory, artifact_id)
    actual = _cp.artifact_content_sha256(manifest)
    if digest is not None and actual != digest:
        raise _cp.PackageError("content_mismatch")
    handle = {"available": True, "source": "split", "artifact_id": artifact_id, "content_sha256": actual,
              "path": str(directory), "version": manifest["asset_version"],
              "compatibility_id": manifest["compatibility_id"],
              "feature": manifest["feature"], "role": manifest["role"],
              "requires": tuple(manifest.get("requires", []))}
    if allow_cache:
        if _cp._artifact_fingerprint(directory) != fingerprint:
            raise _cp.PackageError("artifact_changed")
        if len(_cp._ARTIFACT_STATUS_CACHE) >= 64:
            _cp._ARTIFACT_STATUS_CACHE.pop(next(iter(_cp._ARTIFACT_STATUS_CACHE)))
        _cp._ARTIFACT_STATUS_CACHE[cache_key] = (fingerprint, handle)
    return dict(handle)


def find_cached_artifact(asset_metadata, *, root=None):
    try:
        artifact_id = _cp._artifact_key(asset_metadata["artifact_id"])
        digest = asset_metadata["content_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return None
        base = _cp._root(root) / _cp.ARTIFACT_ROOT
        cache_root = base / ".cache" / artifact_id
        candidates = [cache_root / digest]
        if cache_root.is_dir() and not _cp._linked(cache_root):
            candidates.extend(sorted(cache_root.glob(digest + "-*")))
        candidates.append(base / artifact_id)
        for directory in candidates:
            if directory.parent == cache_root and not _valid_cache_key(directory.name, digest):
                continue
            try:
                result = _cp._handle(directory, artifact_id, digest)
                if result["compatibility_id"] == asset_metadata["compatibility_id"]:
                    return result
            except (_cp.PackageError, OSError):
                continue
    except (KeyError, TypeError, _cp.PackageError):
        pass
    return None


def cache_artifact(archive, artifact_id, *, root=None, expect_content_sha256=None):
    artifact_id = _cp._artifact_key(artifact_id)
    archive = Path(archive)
    if archive.stat().st_size > _cp.MAX_ARCHIVE:
        raise _cp.PackageError("archive_limit")
    assets = _cp._root(root) / _cp.ARTIFACT_ROOT
    if _cp._linked(_cp._root(root)) or _cp._linked(assets):
        raise _cp.PackageError("unsafe_path")
    assets.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % artifact_id, dir=assets))
    try:
        _cp._extract_zip_package(
            archive, stage, lambda raw: _cp._artifact_manifest(raw, artifact_id))
        handle = _cp._handle(stage, artifact_id, expect_content_sha256)
        digest = handle["content_sha256"]
        target = assets / ".cache" / artifact_id / digest
        with _cp._LOCK, _cp._file_transaction(root):
            if _cp._linked(assets / ".cache") or _cp._linked(target.parent) or _cp._linked(target):
                raise _cp.PackageError("unsafe_path")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                try:
                    return _cp._handle(target, artifact_id, digest)
                except (_cp.PackageError, OSError):
                    target = target.with_name(digest + "-" + uuid.uuid4().hex)
            os.replace(stage, target)
            return _cp._handle(target, artifact_id, digest)
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def artifact_status(artifact_id, *, root=None):
    """读取单个 schema2 资产状态，不把它当成完整 feature。"""
    artifact_id = _cp._artifact_key(artifact_id)
    if not _cp.supported():
        return {"available": False, "artifact_id": artifact_id,
                "source": "imported", "error": "unsupported_platform"}
    base = _cp._root(root)
    feature = _cp.ARTIFACTS[artifact_id]["feature"]
    pointer = _cp._group_pointer(feature, root)
    if pointer.exists() or _cp._linked(pointer):
        try:
            return _cp._resolve_group(feature, root=root)[artifact_id]
        except (_cp.PackageError, OSError, ValueError, KeyError, TypeError):
            return {"available": False, "artifact_id": artifact_id,
                    "source": "split", "error": "artifact_invalid"}
    try:
        _cp._recover_artifact_replacement(base, artifact_id)
        directory = _cp.artifact_dir(artifact_id, root=root)
        manifest = _cp.validate_artifact_directory(directory, artifact_id)
        return {"available": True, "artifact_id": artifact_id,
                "feature": manifest["feature"], "role": manifest["role"],
                "source": "split", "error": "",
                "version": manifest["asset_version"],
                "compatibility_id": manifest["compatibility_id"],
                "path": str(directory)}
    except (_cp.PackageError, OSError):
        return {"available": False, "artifact_id": artifact_id,
                "source": "split", "error": "artifact_invalid"}


def install_artifact(archive, artifact_id, *, root=None):
    """安装单个 schema2 资产，旧 feature 目录不参与换位。"""
    artifact_id = _cp._artifact_key(artifact_id)
    _cp._assert_unused(_cp.ARTIFACTS[artifact_id]["feature"], root)
    if not _cp.supported():
        raise _cp.PackageError("unsupported_platform")
    archive = Path(archive)
    if archive.stat().st_size > _cp.MAX_ARCHIVE:
        raise _cp.PackageError("archive_limit")
    base = _cp._root(root)
    assets = base / _cp.ARTIFACT_ROOT
    if _cp._linked(base) or _cp._linked(assets):
        raise _cp.PackageError("unsafe_path")
    assets.mkdir(parents=True, exist_ok=True)
    _cp._recover_artifact_replacement(base, artifact_id)
    stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % artifact_id, dir=assets))
    target, backup = assets / artifact_id, assets / (".backup-" + artifact_id)
    try:
        manifest = _cp._extract_zip_package(
            archive, stage, lambda raw: _cp._artifact_manifest(raw, artifact_id))
        _cp.validate_artifact_directory(stage, artifact_id)
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            if _cp._linked(target):
                raise _cp.PackageError("unsafe_path")
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


def _validate_group(feature, handles):
    by_id = {h["artifact_id"]: h for h in handles}
    required = {key for key, spec in _cp.ARTIFACTS.items() if spec["feature"] == feature}
    if len(by_id) != len(handles) or set(by_id) != required:
        raise _cp.PackageError("artifact_incomplete")
    if len({h["compatibility_id"] for h in handles}) != 1:
        raise _cp.PackageError("artifact_incompatible")
    for handle in handles:
        if any(not isinstance(item, str) or item not in by_id for item in handle["requires"]):
            raise _cp.PackageError("artifact_incomplete")
    return by_id


def _resolve_group(feature, *, root=None, allow_cache=True):
    pointer = _cp._group_pointer(feature, root)
    if _cp._linked(pointer.parent) or _cp._linked(pointer):
        raise _cp.PackageError("unsafe_path")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("feature") != feature
            or not isinstance(data.get("artifacts"), list)):
        raise _cp.PackageError("bad_group")
    handles, assets = [], _cp._root(root) / _cp.ARTIFACT_ROOT
    for item in data["artifacts"]:
        artifact_id = _cp._artifact_key(item["artifact_id"])
        digest = item["content_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise _cp.PackageError("bad_group")
        if item.get("source") == "fixed":
            path = assets / artifact_id
        elif item.get("source") == "cache":
            cache_key = item.get("cache_key", digest)
            if not _valid_cache_key(cache_key, digest):
                raise _cp.PackageError("bad_group")
            path = assets / ".cache" / artifact_id / cache_key
        else:
            raise _cp.PackageError("bad_group")
        handles.append(_cp._handle(path, artifact_id, digest, allow_cache=allow_cache))
    return _validate_group(feature, handles)


def _group_cache_refs(feature, root):
    """切换前指针引用的缓存目录集合：{(资产, 缓存目录名)}。"""
    pointer = _cp._group_pointer(feature, root)
    if _cp._linked(pointer) or _cp._linked(pointer.parent):
        return None
    if not pointer.exists():
        return set()
    try:
        data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    refs = set()
    for item in data.get("artifacts") or ():
        if (isinstance(item, dict) and item.get("source") == "cache"
                and isinstance(item.get("artifact_id"), str)
                and isinstance(item.get("cache_key"), str)):
            refs.add((item["artifact_id"], item["cache_key"]))
    return refs


def _stage_artifact_for_commit(handle, assets):
    artifact_id = _cp._artifact_key(handle["artifact_id"])
    digest = handle["content_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise _cp.PackageError("content_mismatch")
    path = Path(handle["path"])
    cache_root, fixed = assets / ".cache" / artifact_id, assets / artifact_id
    if path == fixed:
        _cp._handle(path, artifact_id, digest)
        if _cp._linked(assets / ".cache") or _cp._linked(cache_root):
            raise _cp.PackageError("unsafe_path")
        cache_root.mkdir(parents=True, exist_ok=True)
        cache = cache_root / digest
        if cache.exists():
            try:
                _cp._handle(cache, artifact_id, digest)
            except (_cp.PackageError, OSError):
                cache = cache_root / (digest + "-" + uuid.uuid4().hex)
        if not cache.exists():
            stage = cache_root / (".stage-" + uuid.uuid4().hex)
            try:
                shutil.copytree(path, stage)
                _cp._handle(stage, artifact_id, digest)
                os.replace(stage, cache)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        path = cache
    elif path.parent != cache_root or not _valid_cache_key(path.name, digest):
        raise _cp.PackageError("unsafe_path")
    checked = _cp._handle(path, artifact_id, digest)
    ref = {"artifact_id": artifact_id, "content_sha256": digest,
           "source": "cache", "cache_key": path.name}
    return checked, ref


def _probe_group_runtime(feature, by_id):
    runtime = Path(by_id[feature + "_runtime"]["path"])
    env = None
    if feature == "relogin_ocr":
        env = {"CAMPUS_OCR_MODEL_ROOT": str(Path(by_id["relogin_ocr_model"]["path"]) / "models")}
    _cp._helper(runtime / "feature-helper.exe", feature=feature, probe=True, env=env)
    if feature == "phone_control":
        tool = Path(by_id["phone_control_cloudflared"]["path"]) / _cp.CLOUDFLARED_NAME
        if _cp.parse_cloudflared_version(_cp.probe_cloudflared_version(tool)) != _cp.CLOUDFLARED_VERSION:
            raise _cp.PackageError("tool_probe_failed")


def commit_artifact_group(feature, artifacts, *, root=None):
    feature = _cp._key(feature)
    _cp._assert_unused(feature, root)
    assets = _cp._root(root) / _cp.ARTIFACT_ROOT
    with _cp._LOCK, _cp._file_transaction(root):
        _cp._reclaim_stages(_cp._root(root), feature)
        checked, refs = [], []
        for handle in artifacts:
            verified, ref = _stage_artifact_for_commit(handle, assets)
            checked.append(verified)
            refs.append(ref)
        by_id = _validate_group(feature, checked)
        if any(item["compatibility_id"] not in _cp.SUPPORTED_COMPATIBILITY_IDS for item in checked):
            # 指针切过去之后本客户端会读不了：宁可拒绝，也别丢掉现在能用的那一组
            raise _cp.PackageError("artifact_incompatible")
        _probe_group_runtime(feature, by_id)
        previous = _cp._group_cache_refs(feature, root)
        _cp._write_group_pointer(feature, {"feature": feature, "artifacts": refs}, root)
        keep = None if previous is None else previous | {
            (ref["artifact_id"], ref["cache_key"]) for ref in refs}
        _cp._reclaim_group_cache(_cp._root(root), feature, keep)
        return {"ok": True, "feature": feature, "artifacts": by_id}


def selected_install_dir(feature, *, root=None):
    state = _cp._split_group(feature, root=root)
    if state.get("available"):
        return Path(state["artifacts"][feature + "_runtime"]["path"])
    return _cp.install_dir(feature, root=root)


def _has_split_assets(base, feature):
    """磁盘上有没有这个功能的拆分资产：固定目录或缓存里任一份都算。"""
    assets = base / _cp.ARTIFACT_ROOT
    for artifact_id, spec in _cp.ARTIFACTS.items():
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


def _resolve_pointer_selection(feature, pointer, root, allow_cache):
    try:
        selection = json.loads(pointer.read_text(encoding="utf-8")) if not _cp._linked(pointer) else {}
        if (isinstance(selection, dict) and selection.get("feature") == feature
                and selection.get("selection") == "legacy"
                and ("transaction_id" not in selection or
                     (isinstance(selection["transaction_id"], str) and
                      re.fullmatch(r"[0-9a-f]{32}", selection["transaction_id"])))):
            return {"available": False, "source": "legacy", "feature": feature,
                    "error": "", "artifacts": {}}
        by_id = _cp._resolve_group(feature, root=root, allow_cache=allow_cache)
        runtime = by_id[feature + "_runtime"]
        if runtime["compatibility_id"] not in _cp.SUPPORTED_COMPATIBILITY_IDS:
            return {"available": False, "source": "split", "feature": feature,
                    "error": "artifact_incompatible", "artifacts": {}}
        return {"available": True, "source": "split", "feature": feature,
                "error": "", "version": runtime["version"],
                "compatibility_id": runtime["compatibility_id"], "artifacts": by_id}
    except (_cp.PackageError, OSError, ValueError, KeyError, TypeError):
        return {"available": False, "source": "split", "feature": feature,
                "error": "artifact_invalid", "artifacts": {}}


def _split_group(feature, *, root=None, allow_cache=True):
    feature = _cp._key(feature)
    _cp._recover_replacement(_cp._root(root), feature)
    pointer = _cp._group_pointer(feature, root)
    if pointer.exists() or _cp._linked(pointer):
        return _resolve_pointer_selection(feature, pointer, root, allow_cache)
    if not _has_split_assets(_cp._root(root), feature):
        # 全新未安装：既没有旧单体包也没有半套拆分资产，不能报成装坏
        return {"available": False, "source": "none", "feature": feature,
                "error": "", "artifacts": {}}
    ids = [artifact_id for artifact_id, spec in _cp.ARTIFACTS.items()
           if spec["feature"] == feature]
    states = [_cp.artifact_status(artifact_id, root=root) for artifact_id in ids]
    required = ({"relogin_ocr_runtime", "relogin_ocr_model"}
                if feature == "relogin_ocr" else {"phone_control_runtime"})
    by_id = {state["artifact_id"]: state for state in states}
    if not required.issubset({key for key, state in by_id.items() if state["available"]}):
        return {"available": False, "source": "split", "feature": feature,
                "error": "artifact_incomplete", "artifacts": by_id}
    compatibility = {by_id[key].get("compatibility_id") for key in required}
    if len(compatibility) != 1 or not compatibility <= _cp.SUPPORTED_COMPATIBILITY_IDS:
        return {"available": False, "source": "split", "feature": feature,
                "error": "artifact_incompatible", "artifacts": by_id}
    return {"available": True, "source": "split", "feature": feature,
            "error": "", "version": next(iter({by_id[key]["version"] for key in required})),
            "compatibility_id": next(iter(compatibility)), "artifacts": by_id}


def feature_status(key, *, root=None):
    """优先返回完整拆分组，组不完整时退回旧单体 feature 包。"""
    split = _cp._split_group(key, root=root)
    if split["available"]:
        return split
    legacy = _cp.status(key, root=root)
    if legacy.get("available"):
        legacy["source"] = "legacy"
        legacy["split"] = split
        return legacy
    if legacy.get("error") == "component_outdated":
        # 拆分组不可用（或半装）时也要说出「旧组件还占着位置」，否则界面把
        # 升级后的旧包装成没装，用户会以为功能被卸载了
        legacy["split"] = split
        return legacy
    if not split.get("error") and legacy.get("error"):
        # 拆分资产没留痕，但旧单体包在且校验不过：那是真实故障，不能报成未安装
        legacy["split"] = split
        return legacy
    return split


def invoke(key, payload, *, root=None):
    with _cp._LOCK:
        feature = _cp._key(key)
        split = _cp._split_group(feature, root=root, allow_cache=False)
        if split["available"]:
            runtime = Path(split["artifacts"][feature + "_runtime"]["path"])
            env = None
            if feature == "relogin_ocr":
                env = {"CAMPUS_OCR_MODEL_ROOT": str(
                    Path(split["artifacts"]["relogin_ocr_model"]["path"]) / "models")}
            try:
                return _cp._helper(runtime / "feature-helper.exe",
                                   feature=feature, payload=payload, env=env)
            except (_cp.PackageError, OSError):
                pass
        directory = _cp._root(root) / feature
        _cp.validate_directory(directory, feature)
        return _cp._helper(directory / "feature-helper.exe", feature=feature, payload=payload)
