"""完整安装器的流式下载与启动：只写临时目录，不触碰程序目录和数据目录。

下载边界：只走 HTTPS、大小上限、临时 `.part` 半成品、实时 SHA-256，
成功后 `os.replace` 原子保留，失败一律清理半成品。启动只接受临时目录里
已校验的产物，绝不执行任意路径。

@author Author
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import json
import os
import re
import shutil
import socket
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from update_delta import DeltaError, apply_delta, validate_relative_path, verify_directory
except ImportError:  # 源码模块由 app.py 注入 local 到 sys.path；独立测试仍可导入
    from .update_delta import DeltaError, apply_delta, validate_relative_path, verify_directory

CHUNK_BYTES = 64 * 1024
# 与 update_check.MAX_INSTALLER_BYTES 同源口径：安装包下载上限（约 300 MB）
DEFAULT_MAX_BYTES = 300 * 1024 * 1024
DOWNLOAD_TIMEOUT_S = 60
TEMP_PREFIX = "campus-update-"
_NAME_RE = re.compile(r"[A-Za-z0-9._-]{1,120}")
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


def temp_root() -> Path:
    """下载临时根：优先 <tmp>，缺失时退到系统临时目录（用户级 TEMP 已指向同一处）。"""
    preferred = Path("<tmp>")
    if preferred.is_dir():
        return preferred
    return Path(tempfile.gettempdir())


def _require_https(url: str) -> str:
    """只走 HTTPS：非 https 或没有主机名一律拒绝，不给下载机会。"""
    if not isinstance(url, str) or not url or len(url) > 2048:
        raise ValueError("invalid url")
    parts = urlparse(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("https required")
    return url


def download_installer(url, *, name, expect_bytes, expect_sha256, root=None,
                       max_bytes=DEFAULT_MAX_BYTES, timeout_s=DOWNLOAD_TIMEOUT_S,
                       progress=None, cancel=None) -> dict:
    """流式下载安装器到临时目录并实时校验大小与 SHA-256。

    成功返回 {"ok": True, "path", "bytes", "sha256"}，目标文件已从 `.part`
    原子改名保留；可预期失败（断流、超限、大小/哈希不符、取消、写入失败）
    返回 {"ok": False, "error_code", "text"} 并清理半成品。参数非法和未预期
    异常直接抛出——失败路径不吞异常。绝不写程序目录和数据目录。
    """
    _require_https(url)
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError("invalid name")
    if not isinstance(expect_sha256, str) or not _SHA256_RE.fullmatch(expect_sha256):
        raise ValueError("invalid sha256")
    if not isinstance(expect_bytes, int) or isinstance(expect_bytes, bool) or expect_bytes <= 0:
        raise ValueError("invalid expect_bytes")
    limit = max_bytes if isinstance(max_bytes, int) and not isinstance(max_bytes, bool) \
        and max_bytes > 0 else DEFAULT_MAX_BYTES
    if expect_bytes > limit:
        return {"ok": False, "error_code": "size_limit",
                "text": "安装包超过下载大小上限，已放弃下载。"}

    base = Path(root) if root is not None else temp_root()
    workdir = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=str(base)))
    part = workdir / (name + ".part")
    final = workdir / name
    digest = hashlib.sha256()
    done = 0
    kept = False
    try:
        request = Request(url, headers={
            "Accept": "application/octet-stream",
            "User-Agent": "TianSoftActivityPreRegistration-updater",
        })
        with urlopen(request, timeout=timeout_s) as response:
            while True:
                # 每块之间看一次取消标记：用户取消要能立刻停，不留半成品
                if cancel is not None and cancel():
                    return {"ok": False, "error_code": "cancelled",
                            "text": "已取消下载，临时文件已清理。"}
                chunk = response.read(CHUNK_BYTES)
                if not chunk:
                    break
                done += len(chunk)
                if done > limit:
                    return {"ok": False, "error_code": "size_limit",
                            "text": "下载内容超过大小上限，已放弃并清理。"}
                digest.update(chunk)
                try:
                    with part.open("ab") as handle:
                        handle.write(chunk)
                except OSError:
                    return {"ok": False, "error_code": "io_error",
                            "text": "临时目录写入失败，已放弃并清理。"}
                if progress is not None:
                    progress(done, expect_bytes)
        if done != expect_bytes:
            return {"ok": False, "error_code": "size_mismatch",
                    "text": "下载大小与校验信息不一致（%d / %d 字节），已放弃。" % (done, expect_bytes)}
        got = digest.hexdigest().lower()
        if got != expect_sha256.lower():
            return {"ok": False, "error_code": "hash_mismatch",
                    "text": "下载内容哈希校验未通过，已放弃并清理。"}
        os.replace(part, final)
        kept = True
        return {"ok": True, "path": str(final), "bytes": done, "sha256": got}
    except HTTPError:
        return {"ok": False, "error_code": "http_error",
                "text": "下载地址暂时无法响应，请稍后重试。"}
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            return {"ok": False, "error_code": "timeout", "text": "下载超时，请重试。"}
        return {"ok": False, "error_code": "network_error",
                "text": "下载中断，请检查网络后重试。"}
    except TimeoutError:
        return {"ok": False, "error_code": "timeout", "text": "下载超时，请重试。"}
    except OSError:
        # 连接被重置/半途关闭（含 ConnectionError）都归断流；半成品在 finally 清理
        return {"ok": False, "error_code": "network_error",
                "text": "下载中断，请检查网络后重试。"}
    except HTTPException:
        return {"ok": False, "error_code": "network_error",
                "text": "下载中断，请检查网络后重试。"}
    finally:
        if not kept:
            shutil.rmtree(workdir, ignore_errors=True)


def launch_installer(path, *, root=None, launcher=None) -> dict:
    """启动已校验的安装器；只接受临时目录里的现有文件，失败不改会话和偏好。

    关闭主程序由调用方控制：这里只负责拉起安装向导，不退出、不自动重启。
    """
    if not isinstance(path, str) or not path:
        return {"ok": False, "error_code": "launch_failed", "text": "安装包路径无效。"}
    target = Path(path)
    if not target.is_file():
        return {"ok": False, "error_code": "launch_failed",
                "text": "安装包不存在，请重新下载。"}
    base = Path(root) if root is not None else temp_root()
    try:
        target.resolve().relative_to(base.resolve())
    except (ValueError, OSError):
        return {"ok": False, "error_code": "launch_failed",
                "text": "安装包不在更新临时目录，已拒绝启动。"}
    try:
        (launcher or os.startfile)(str(target))   # noqa: S606 - 用户确认后启动安装向导
    except Exception as exc:  # noqa: BLE001 - 启动失败也要给界面一个可读结论
        return {"ok": False, "error_code": "launch_failed",
                "text": "安装程序没能启动（%s）。" % type(exc).__name__}
    return {"ok": True, "path": str(target)}


def download_payload(url, *, name, expect_bytes, expect_sha256, **kwargs) -> dict:
    """通用 payload 下载入口；与完整安装器共用大小、哈希和取消边界。"""
    return download_installer(url, name=name, expect_bytes=expect_bytes,
                              expect_sha256=expect_sha256, **kwargs)


def download_delta(url, *, name, expect_bytes, expect_sha256, **kwargs) -> dict:
    """文件级 delta 包下载入口。"""
    return download_payload(url, name=name, expect_bytes=expect_bytes,
                            expect_sha256=expect_sha256, **kwargs)


def download_full(url, *, name, expect_bytes, expect_sha256, **kwargs) -> dict:
    """完整 onedir payload 下载入口。"""
    return download_payload(url, name=name, expect_bytes=expect_bytes,
                            expect_sha256=expect_sha256, **kwargs)


def cleanup_download(path) -> bool:
    """删除已校验但已用完的 payload，并回收它的临时目录。"""
    target = Path(path) if path else None
    if target is None:
        return False
    removed = False
    try:
        if target.is_file() and not target.is_symlink():
            target.unlink()
            removed = True
        parent = target.parent
        if (parent.is_dir() and parent.name.startswith(TEMP_PREFIX)
                and not any(parent.iterdir())):
            parent.rmdir()
    except OSError:
        return removed
    return removed


def cleanup_staging(path, *, version_root=None) -> bool:
    """回收未再使用的版本 staging；只接受受控版本根下的名称。"""
    target = Path(path) if path else None
    if target is None or not target.name.startswith(".staging-") or target.is_symlink():
        return False
    if version_root is None:
        if target.parent.name != "versions":
            return False
    else:
        try:
            if target.parent.resolve() != Path(version_root).resolve():
                return False
        except OSError:
            return False
    try:
        if target.is_dir():
            shutil.rmtree(target)
            return True
    except OSError:
        return False
    return False


# 版本根下只清理这些前缀的更新残留：下载/应用中断、没点重启、切换被让开的旧目录。
_SWEEP_PREFIXES = (".staging-", ".stage-", ".part-", ".old-")


def _current_and_previous(current_file):
    """读 current.json 里的 (当前版本, 上一版本)；缺失或损坏返回 None。"""
    try:
        raw = json.loads(Path(current_file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    current = raw.get("version")
    if not isinstance(current, str) or not _VERSION_RE.fullmatch(current):
        return None
    previous = raw.get("previous_version")
    if not isinstance(previous, str) or not _VERSION_RE.fullmatch(previous):
        previous = ""
    return current, previous


def _is_link(path: Path) -> bool:
    """符号链接或目录联接：清理时绝不跟进去，也不删链接本身。"""
    if path.is_symlink():
        return True
    isjunction = getattr(os.path, "isjunction", None)
    return bool(isjunction and isjunction(path))


def sweep_version_root(version_root, *, current_file, keep_dir=None) -> dict:
    """清理版本根里的更新残留和多余旧版本；返回 {"removed": [...], "failed": [...]}。

    只删三类名字：.staging-* / .stage-* / .part-* / .old-* 残留，以及版本号目录里
    不是 current.json 的 version / previous_version 的那些。始终保留 keep_dir
    （当前进程正在运行的目录）；链接一律跳过；名字不认识的不碰。current.json
    读不出来时不知道谁是当前版本，只清残留、不删任何版本目录。删不掉的记进
    failed，下次启动再试，绝不抛异常（调用方是启动后的后台线程）。
    数据目录在版本根之外，这里不会也不能碰到。
    """
    result = {"removed": [], "failed": []}
    root = Path(version_root)
    try:
        entries = list(root.iterdir())
    except OSError:
        return result
    versions = _current_and_previous(current_file)
    keep = set()
    if versions is not None:
        keep.update(item for item in versions if item)
    if keep_dir:
        try:
            running = Path(keep_dir).resolve()
            if running.parent == root.resolve():
                keep.add(running.name)
        except OSError:
            pass
    for entry in entries:
        name = entry.name
        if name in keep or _is_link(entry):
            continue
        leftover = name.startswith(_SWEEP_PREFIXES)
        stale_version = (versions is not None and bool(_VERSION_RE.fullmatch(name))
                         and entry.is_dir())
        if not (leftover or stale_version):
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            result["removed"].append(name)
        except OSError:
            result["failed"].append(name)
    return result


def _atomic_write_json(path: Path, payload: dict) -> None:
    """在同一目录内原子写 current.json，切换失败不留下半份状态。"""
    path = Path(path)
    part = path.with_name(path.name + ".part-" + uuid.uuid4().hex)
    try:
        with part.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.flush()
            os.fsync(handle.fileno())   # 断电后不能留下空的 current.json
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def _safe_zip_extract(archive: Path, destination: Path) -> None:
    """解压完整 onedir payload，拒绝绝对路径、目录逃逸和符号链接。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name:
                continue
            relative = name[:-1] if name.endswith("/") else name
            try:
                validate_relative_path(relative)
            except DeltaError as exc:
                raise ValueError("完整包存在越界路径") from exc
            if name.endswith("/"):
                continue
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise ValueError("完整包不允许符号链接")
            target = destination.joinpath(*relative.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                handle.write(zf.read(info))


def _manifest_for_target(target_manifest):
    if isinstance(target_manifest, dict) and isinstance(target_manifest.get("target_manifest"), dict):
        target_manifest = target_manifest["target_manifest"]
    if not isinstance(target_manifest, dict) or not isinstance(target_manifest.get("files"), list):
        raise ValueError("目标 manifest 无效")
    return target_manifest


def stage_update(base_dir, payload, staging_dir, *, mode, base_version=None,
                 target_manifest=None, target_version=None) -> dict:
    """在隔离临时目录应用 delta 或完整 onedir 包，并校验目标 manifest。"""
    staging = Path(staging_dir)
    work = staging.parent / (staging.name + ".stage-" + uuid.uuid4().hex)
    try:
        expected_manifest = _manifest_for_target(target_manifest) if target_manifest is not None else None
        if (target_version and expected_manifest is not None
                and expected_manifest.get("version") != target_version):
            raise ValueError("目标版本与 manifest 不一致")
        if mode == "delta":
            apply_delta(base_dir, payload, work, base_version=base_version)
        elif mode == "full":
            if expected_manifest is None:
                raise ValueError("完整包缺少目标 manifest")
            if not isinstance(payload, (str, Path)):
                raise ValueError("完整包路径无效")
            source = Path(payload)
            if not source.is_file():
                raise FileNotFoundError(str(source))
            _safe_zip_extract(source, work)
            if expected_manifest is not None and not verify_directory(work, expected_manifest):
                raise ValueError("完整包目标 manifest 不一致")
        else:
            raise ValueError("未知更新类型")
        if expected_manifest is not None and mode == "delta":
            if not verify_directory(work, expected_manifest):
                raise ValueError("增量包目标 manifest 不一致")
        if target_version and not _VERSION_RE.fullmatch(str(target_version)):
            raise ValueError("目标版本无效")
        if staging.exists() or staging.is_symlink():
            if staging.is_symlink() or not staging.is_dir():
                raise ValueError("staging 不是目录")
            shutil.rmtree(staging)
        os.replace(work, staging)
        return {"ok": True, "path": str(staging), "mode": mode,
                "version": target_version or ""}
    except Exception as exc:  # noqa: BLE001 - 对外返回可读失败状态并清理隔离目录
        shutil.rmtree(work, ignore_errors=True)
        return {"ok": False, "error_code": "apply_failed",
                "text": str(exc) or "更新包应用失败。", "mode": mode}


def switch_version(version_root, staging_dir, target_version, *, current_file=None) -> dict:
    """把 staging 原子纳入版本目录；旧版本与 current.json 失败时均保留。"""
    if not isinstance(target_version, str) or not _VERSION_RE.fullmatch(target_version):
        return {"ok": False, "error_code": "invalid_version", "text": "目标版本无效。"}
    root = Path(version_root)
    staging = Path(staging_dir)
    current = Path(current_file) if current_file is not None else root.parent / "current.json"
    target = root / target_version
    if not staging.is_dir() or staging.is_symlink() or target.exists():
        return {"ok": False, "error_code": "switch_failed", "text": "版本目录切换前置条件不满足。"}
    previous = ""
    try:
        if current.is_file():
            raw = json.loads(current.read_text(encoding="utf-8"))
            previous = str(raw.get("version") or "") if isinstance(raw, dict) else ""
        root.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
        _atomic_write_json(current, {"version": target_version})
        return {"ok": True, "path": str(target), "version": target_version,
                "previous_version": previous}
    except Exception as exc:  # noqa: BLE001 - 还原目录后保留旧 current.json
        if target.exists() and not staging.exists():
            try:
                os.replace(target, staging)
            except OSError:
                pass
        return {"ok": False, "error_code": "switch_failed",
                "text": str(exc) or "版本目录切换失败。", "previous_version": previous}


def select_payload(installer: dict, current_version: str) -> tuple[str, dict]:
    """从发布清单选择同基础版本的 delta；否则返回完整包作为回退。"""
    if not isinstance(installer, dict):
        raise ValueError("更新资产无效")
    candidates = installer.get("deltas")
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and item.get("base_version") == current_version:
                return "delta", item
    delta = installer.get("delta")
    if isinstance(delta, dict) and delta.get("base_version") == current_version:
        return "delta", delta
    full = installer.get("full")
    if isinstance(full, dict):
        return "full", full
    return "full", installer
