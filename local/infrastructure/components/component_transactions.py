# -*- coding: utf-8 -*-
"""单体组件包的替换恢复、状态查询、安装与移除。

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
        if not target.is_dir() or _cp._linked(target):
            return False
        _cp.validate_directory(target, key)
        _cp._helper(target / "feature-helper.exe", feature=key, probe=True)
        return True
    except (_cp.PackageError, OSError, ValueError, KeyError, TypeError):
        return False


def _recover_journal_entry(base, key, target, backup, journal, pointer):
    transaction = _read_transaction(journal)
    if transaction is None:
        # 断电会留下空文件：这一步没发生过，按磁盘上可验证的目录恢复
        _cp._diagnostic(base, "事务日志损坏，按磁盘状态恢复：%s" % journal.name)
        try:
            journal.unlink()
        except OSError:
            pass
        return False
    committed = _pointer_committed(pointer, key, transaction["transaction_id"])
    if committed and _target_usable(target, key):
        # 已提交：残留 backup 只是旧副本，清不掉也不能推翻安装结果
        if backup.exists():
            _cp._discard(backup, base)
        journal.unlink()
        _cp._STATUS_CACHE.pop(str(target), None)
        return True
    if not committed and not transaction["had_target"]:
        # 首次安装且指针没落：这份目录没有被任何选择引用，删掉
        if target.exists():
            shutil.rmtree(target)
        journal.unlink()
        _cp._STATUS_CACHE.pop(str(target), None)
        return True
    if backup.exists():
        # 事务未完成：把旧副本换回来，宁可用旧版也不留下半套
        if target.exists():
            shutil.rmtree(target)
        os.replace(backup, target)
    journal.unlink()
    _cp._STATUS_CACHE.pop(str(target), None)
    return True


def _recover_replacement(base, key):
    """进程在目录换位中断时，先恢复同一组件的旧目录再判断是否可用。"""
    target = base / key
    backup = base / (".backup-" + key)
    if _cp._linked(base) or _cp._linked(target) or _cp._linked(backup):
        raise _cp.PackageError("unsafe_path")
    journal = base / (".transaction-" + key + ".json")
    pointer = base / _cp.ARTIFACT_ROOT / ".groups" / (key + ".json")
    if _cp._linked(journal) or _cp._linked(pointer.parent) or _cp._linked(pointer):
        raise _cp.PackageError("unsafe_path")
    if journal.exists() and _recover_journal_entry(base, key, target, backup, journal, pointer):
        return
    if backup.exists() and not target.exists():
        os.replace(backup, target)
        _cp._STATUS_CACHE.pop(str(target), None)
    elif backup.exists() and target.exists():
        # 进程死在清理前：target 可验证就以它为准，否则把旧副本换回来
        if not backup.is_dir():
            raise _cp.PackageError("unsafe_path")
        if _target_usable(target, key):
            _cp._discard(backup, base)
        else:
            shutil.rmtree(target)
            os.replace(backup, target)
            _cp._STATUS_CACHE.pop(str(target), None)


def _recover_artifact_replacement(base, artifact_id):
    assets = base / _cp.ARTIFACT_ROOT
    target = assets / artifact_id
    backup = assets / (".backup-" + artifact_id)
    if _cp._linked(assets) or _cp._linked(target) or _cp._linked(backup):
        raise _cp.PackageError("unsafe_path")
    if backup.exists() and not target.exists():
        os.replace(backup, target)
    elif backup.exists() and target.exists():
        if not backup.is_dir():
            raise _cp.PackageError("unsafe_path")
        shutil.rmtree(backup, ignore_errors=True)


def _read_installed_version(directory):
    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        return str((manifest or {}).get("version") or "")
    except (OSError, ValueError):
        return ""


def _dir_fingerprint(directory):
    return tuple((p.relative_to(directory).as_posix(), p.stat().st_size,
                  p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                 for p in sorted(directory.rglob("*")))


def status(key, *, root=None):
    with _cp._LOCK:
        if not _cp.supported():
            return {"available": False, "source": "imported", "error": "unsupported_platform"}
        base, key = _cp._root(root), _cp._key(key)
        try:
            _cp._recover_replacement(base, key)
        except (_cp.PackageError, OSError):
            return {"available": False, "source": "imported", "error": "component_invalid"}
        _cp._reclaim_stages(base, key)
        directory = base / key
        if not directory.exists():
            return {"available": False, "source": "imported", "error": "", "version": ""}
        # 版本号给帮助页和下载服务看：装的是哪个版本的组件，界面要说得出来
        installed_version = _read_installed_version(directory)
        cache_key, fingerprint = str(directory), None
        try:
            fingerprint = _dir_fingerprint(directory)
            cached = _cp._STATUS_CACHE.get(cache_key)
            if cached and cached[0] == fingerprint:
                if cached[1]:
                    return {"available": False, "source": "imported",
                            "error": "component_outdated", "version": cached[1]}
                return {"available": True, "source": "imported", "error": "",
                        "version": installed_version}
            _cp.validate_directory(directory, key)
            _cp._helper(directory / "feature-helper.exe", feature=key, probe=True)
            _cp._STATUS_CACHE[cache_key] = (fingerprint, "")
        except (_cp.PackageError, OSError):
            # 升级主程序后旧组件包只差 version：不能说成没装，也不能说成损坏。
            # 结论也按指纹缓存：设置抽屉和自动登录资格判断都高频查状态，
            # 旧包带着几十 MB 的模型，不能每次都重算全部哈希、再起一次 helper。
            outdated = _cp._outdated_version(directory, key)
            if outdated:
                if fingerprint is not None:
                    _cp._STATUS_CACHE[cache_key] = (fingerprint, outdated)
                return {"available": False, "source": "imported",
                        "error": "component_outdated", "version": outdated}
            _cp._STATUS_CACHE.pop(cache_key, None)
            return {"available": False, "source": "imported", "error": "component_invalid",
                    "version": ""}
        return {"available": True, "source": "imported", "error": "", "version": installed_version}


def _prepare_legacy_install_base(archive, key, root):
    _cp._key(key)
    _cp._assert_unused(key, root)
    if not _cp.supported():
        raise _cp.PackageError("unsupported_platform")
    archive = Path(archive)
    if archive.stat().st_size > _cp.MAX_ARCHIVE:
        raise _cp.PackageError("archive_limit")
    base = _cp._root(root)
    if _cp._linked(base):
        raise _cp.PackageError("unsafe_path")
    base.mkdir(parents=True, exist_ok=True)
    _cp._recover_replacement(base, key)
    _cp._reclaim_stages(base, key)
    backup = base / (".backup-" + key)
    if backup.exists():
        # 换位前先清残留 backup：删不掉就中止，别让 os.replace 撞上它
        try:
            shutil.rmtree(backup)
        except OSError as exc:
            raise _cp.PackageError("backup_locked") from exc
        if backup.exists():
            raise _cp.PackageError("backup_locked")
    return archive, base, base / key, backup


def install(archive, key, *, root=None):
    with _cp._LOCK:
        archive, base, target, backup = _prepare_legacy_install_base(archive, key, root)
        stage = Path(tempfile.mkdtemp(prefix=".stage-%s-" % key, dir=base))
        try:
            _cp._extract_zip_package(archive, stage, lambda raw: _cp._manifest(raw, key))
            _cp.validate_directory(stage, key)
            _cp._helper(stage / "feature-helper.exe", feature=key, probe=True)
            transaction_id = uuid.uuid4().hex
            journal = base / (".transaction-" + key + ".json")
            _cp._atomic_json(journal, {"transaction_id": transaction_id, "had_target": target.exists()})
            try:
                if target.exists():
                    if _cp._linked(target):
                        raise _cp.PackageError("unsafe_path")
                    os.replace(target, backup)
                os.replace(stage, target)
                _cp._write_group_pointer(key, {"feature": key, "selection": "legacy",
                                               "transaction_id": transaction_id}, root)
            except BaseException:
                _cp._recover_replacement(base, key)
                raise
            _cp._recover_replacement(base, key)
            _cp._STATUS_CACHE.pop(str(target), None)
            return {"ok": True, "feature": key, "text": "组件已导入并启用。"}
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def remove(key, *, root=None):
    with _cp._LOCK, _cp._file_transaction(root):
        base = _cp._root(root)
        feature = _cp._key(key)
        _cp._assert_unused(feature, root)
        target = base / feature
        _cp._recover_replacement(base, feature)
        _cp._reclaim_stages(base, feature)
        if _cp._linked(base) or _cp._linked(target):
            raise _cp.PackageError("unsafe_path")
        if target.exists():
            shutil.rmtree(target)
        backup = base / (".backup-" + feature)
        if backup.exists():
            shutil.rmtree(backup)
        _cp._STATUS_CACHE.pop(str(target), None)
        assets = base / _cp.ARTIFACT_ROOT
        pointer = _cp._group_pointer(feature, root)
        if _cp._linked(pointer) or _cp._linked(pointer.parent):
            raise _cp.PackageError("unsafe_path")
        if pointer.exists():
            pointer.unlink()
        for artifact_id, spec in _cp.ARTIFACTS.items():
            if spec["feature"] != feature:
                continue
            cache = assets / ".cache" / artifact_id
            if _cp._linked(cache):
                raise _cp.PackageError("unsafe_path")
            if cache.exists():
                shutil.rmtree(cache)
            _cp._recover_artifact_replacement(base, artifact_id)
            artifact = assets / artifact_id
            if artifact.exists():
                if _cp._linked(artifact):
                    raise _cp.PackageError("unsafe_path")
                shutil.rmtree(artifact)
        return {"ok": True, "text": "组件已移除；本机保存的账号可另行清除。"}
