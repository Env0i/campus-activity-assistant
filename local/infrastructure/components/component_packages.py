# -*- coding: utf-8 -*-
"""固定高级组件 ZIP 的校验、替换及隔离 helper 调用。

SHA256 只验证完整性，用户必须自行确认组件来源可信。
@author Author
"""
from __future__ import annotations

import functools
import importlib
import importlib.util
import re
import sys
import threading
from pathlib import Path

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
# 本客户端能用的 compatibility_id（发布侧 local/build/build_advanced.py 现在写的值）。
# 资产组整体换成新口径时，旧客户端不能照收：清单格式没变，但 helper 与模型的约定变了。
SUPPORTED_COMPATIBILITY_IDS = frozenset({"campus-activity-1"})
# 切换组后回收旧缓存时的宽限期：刚缓存好、还没来得及提交的资产（下载与提交之间，
# 或者调用方先备好几组再逐个提交）不属于「旧组」，不能被别的提交顺手删掉。
CACHE_RECLAIM_GRACE_S = 3600.0
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
# cloudflared 版本探测结果：键是（路径、大小、mtime_ns），只放进程内存、只存探测成功的结果。
# 探测要起子进程，不能每次状态查询都在全局锁里跑一遍；哈希核对不走这份缓存。
_CLOUDFLARED_PROBE_CACHE = {}
_TRANSACTION_LOCAL = threading.local()


class PackageError(ValueError):
    pass


_CLOUDFLARED_VERSION_RE = re.compile(r"(\d{4}\.\d+\.\d+)")


def _load_sibling(name: str):
    """按包内相对导入或独立路径加载同级模块，兼容 release.py 的无 sys.path 挂载。"""
    if __package__:
        return importlib.import_module(f".{name}", __package__)
    module_name = f"{__name__}__{name}"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _FacadeProxy:
    """当模块由 spec_from_file_location 独立挂载且未进 sys.modules 时代理其命名空间。"""

    def __init__(self, namespace: dict) -> None:
        self._ns = namespace

    def __getattr__(self, name: str):
        try:
            return self._ns[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


_manifest_mod = _load_sibling("component_manifest")
_storage_mod = _load_sibling("component_storage")
_tx_mod = _load_sibling("component_transactions")
_artifacts_mod = _load_sibling("component_artifacts")
_cloudflared_mod = _load_sibling("component_cloudflared")

_FACADE = sys.modules.get(__name__) or _FacadeProxy(globals())
for _mod in (_manifest_mod, _storage_mod, _tx_mod, _artifacts_mod, _cloudflared_mod):
    _mod.bind(_FACADE)

# 保持对测试 patch cp.os / cp.shutil / cp.subprocess 等模块属性的兼容
os = _storage_mod.os
shutil = _storage_mod.shutil
subprocess = _storage_mod.subprocess
json = _storage_mod.json
zipfile = _storage_mod.zipfile
tempfile = _tx_mod.tempfile
time = _storage_mod.time
uuid = _storage_mod.uuid
stat = _storage_mod.stat
contextlib = _storage_mod.contextlib
hashlib = _manifest_mod.hashlib
platform = _manifest_mod.platform
struct = _manifest_mod.struct
PurePosixPath = _manifest_mod.PurePosixPath


def _transactional(function):
    @functools.wraps(function)
    def guarded(*args, **kwargs):
        with _LOCK, _file_transaction(kwargs.get("root")):
            return function(*args, **kwargs)
    return guarded


# ---------- 清单、路径与只读自检 -------------------------------------------
parse_cloudflared_version = _manifest_mod.parse_cloudflared_version
supported = _manifest_mod.supported
version = _manifest_mod.version
_key = _manifest_mod._key
_artifact_key = _manifest_mod._artifact_key
_linked = _manifest_mod._linked
_name = _manifest_mod._name
sha256 = _manifest_mod.sha256
_manifest = _manifest_mod._manifest
_artifact_manifest = _manifest_mod._artifact_manifest
validate_artifact_directory = _manifest_mod.validate_artifact_directory
validate_directory = _manifest_mod.validate_directory
_outdated_version = _manifest_mod._outdated_version
artifact_content_sha256 = _manifest_mod.artifact_content_sha256
inspect_artifact = _manifest_mod.inspect_artifact
inspect_archive = _manifest_mod.inspect_archive

# ---------- 底层存储、锁与恢复 ---------------------------------------------
_root = _storage_mod._root
install_dir = _storage_mod.install_dir
artifact_dir = _storage_mod.artifact_dir
_file_transaction = _storage_mod._file_transaction
_cloudflared_use_lock = _storage_mod._cloudflared_use_lock
_assert_unused = _storage_mod._assert_unused
_helper = _storage_mod._helper
_diagnostic = _storage_mod._diagnostic
_discard = _storage_mod._discard
_discard_stage = _storage_mod._discard_stage
_reclaim_stages = _storage_mod._reclaim_stages
_reclaim_group_cache = _storage_mod._reclaim_group_cache
_sync_directory = _storage_mod._sync_directory
_atomic_json = _storage_mod._atomic_json
_extract_zip_package = _storage_mod._extract_zip_package

_read_transaction = _tx_mod._read_transaction
_pointer_committed = _tx_mod._pointer_committed
_target_usable = _tx_mod._target_usable
_recover_replacement = _tx_mod._recover_replacement
_recover_artifact_replacement = _tx_mod._recover_artifact_replacement

# ---------- 拆分资产与组路由 -----------------------------------------------
_group_pointer = _artifacts_mod._group_pointer
_write_group_pointer = _artifacts_mod._write_group_pointer
_valid_cache_key = _artifacts_mod._valid_cache_key
_artifact_fingerprint = _artifacts_mod._artifact_fingerprint
_handle = _artifacts_mod._handle
_validate_group = _artifacts_mod._validate_group
_resolve_group = _artifacts_mod._resolve_group
_group_cache_refs = _artifacts_mod._group_cache_refs
_has_split_assets = _artifacts_mod._has_split_assets
_split_group = _artifacts_mod._split_group

# ---------- cloudflared 探测与存储 -----------------------------------------
probe_cloudflared_version = _cloudflared_mod.probe_cloudflared_version
cloudflared_version_text = _cloudflared_mod.cloudflared_version_text
inspect_cloudflared = _cloudflared_mod.inspect_cloudflared
_recover_cloudflared_store = _cloudflared_mod._recover_cloudflared_store
cloudflared_usage = _cloudflared_mod.cloudflared_usage


# ---------- 事务化对外入口 -------------------------------------------------
@_transactional
def status(key, *, root=None):
    return _tx_mod.status(key, root=root)


@_transactional
def install(archive, key, *, root=None):
    return _tx_mod.install(archive, key, root=root)


@_transactional
def remove(key, *, root=None):
    return _tx_mod.remove(key, root=root)


@_transactional
def artifact_status(artifact_id, *, root=None):
    """读取单个 schema2 资产状态，不把它当成完整 feature。"""
    return _artifacts_mod.artifact_status(artifact_id, root=root)


@_transactional
def install_artifact(archive, artifact_id, *, root=None):
    """安装单个 schema2 资产，旧 feature 目录不参与换位。"""
    return _artifacts_mod.install_artifact(archive, artifact_id, root=root)


@_transactional
def find_cached_artifact(asset_metadata, *, root=None):
    return _artifacts_mod.find_cached_artifact(asset_metadata, root=root)


@_transactional
def cache_artifact(archive, artifact_id, *, root=None, expect_content_sha256=None):
    return _artifacts_mod.cache_artifact(
        archive, artifact_id, root=root, expect_content_sha256=expect_content_sha256)


@_transactional
def commit_artifact_group(feature, artifacts, *, root=None):
    return _artifacts_mod.commit_artifact_group(feature, artifacts, root=root)


@_transactional
def selected_install_dir(feature, *, root=None):
    return _artifacts_mod.selected_install_dir(feature, root=root)


@_transactional
def feature_status(key, *, root=None):
    """优先返回完整拆分组，组不完整时退回旧单体 feature 包。"""
    return _artifacts_mod.feature_status(key, root=root)


@_transactional
def invoke(key, payload, *, root=None):
    return _artifacts_mod.invoke(key, payload, root=root)


@_transactional
def install_cloudflared(source, *, root=None, probe=None, probe_text=None) -> dict:
    """把用户选定的 cloudflared 收进受管目录，并记下版本与哈希。"""
    return _cloudflared_mod.install_cloudflared(
        source, root=root, probe=probe, probe_text=probe_text)


@_transactional
def stored_cloudflared(*, root=None, probe=None) -> str:
    """返回受管目录里那份 cloudflared 的路径；版本或哈希对不上就返回空串。"""
    return _cloudflared_mod.stored_cloudflared(root=root, probe=probe)


@_transactional
def remove_cloudflared(*, root=None) -> dict:
    return _cloudflared_mod.remove_cloudflared(root=root)


@_transactional
def cloudflared(*, root=None, probe=None):
    """返回可用的 cloudflared 路径；版本不符、缺文件、probe 失败都返回空串。"""
    return _cloudflared_mod.cloudflared(root=root, probe=probe)
