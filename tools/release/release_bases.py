#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布增量基线管理：历史基线拉取校验、本地基线发现与多基线增量装配。

独立于 release.py 的本地缓存和打包辅助，供 release.py 按文件路径加载。

@author Author
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import re
import shutil
import stat
import time
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_DOWNLOAD_BASE = "https://github.com/Env0i/campus-activity-assistant/releases/download"
FETCH_TIMEOUT_S = 60
MAX_MANIFEST_BYTES = 256 * 1024
MAX_EXTRACT_MEMBERS = 5000
MAX_EXTRACT_BYTES = 1024 * 1024 * 1024
LAUNCHER_FINGERPRINT_FILE = "update-launcher.fingerprint"
LAUNCHER_EXE_NAME = "update-launcher.exe"
_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


def _load_update_delta(root: Path = ROOT):
    """按文件路径加载 local/infrastructure/update/update_delta.py（不污染 sys.path）。"""
    path = Path(root) / "local" / "infrastructure" / "update" / "update_delta.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("release_update_delta", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_version_tuple(value: str) -> tuple[int, int, int]:
    match = _VERSION_RE.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        raise SystemExit("[release] 非法版本号：%r（只允许三段数字版本号）" % (value,))
    return tuple(int(part) for part in match.groups())


def target_manifest(directory: Path, version: str, *, root: Path = ROOT) -> dict:
    """按更新器同一实现生成 onedir 目录清单，避免两边哈希口径漂移。"""
    module = _load_update_delta(root)
    if module is None:
        raise SystemExit("[prepare] 找不到 local/infrastructure/update/update_delta.py：payload 清单无法生成")
    try:
        return module.manifest_from_directory(directory, version=version)
    except Exception as exc:
        raise SystemExit("[prepare] onedir payload 清单生成失败：%s" % exc)


def verify_delta_base(base_dir, base_version: str, base_manifest, *, root: Path = ROOT) -> None:
    """核对 --delta-base 目录就是基线版本当年发布出去的那一份，不符就中止。

    PyInstaller 构建不可复现：自己重建出来的 onedir 与用户机器上装的哈希不同，
    据它生成的增量包对谁都套不上。所以必须拿基线版本已发布的 manifest.json
    （本地副本）当真相，用与更新器同一实现算出基线目录的目标清单哈希来比。
    """
    if not base_manifest:
        raise SystemExit(
            "[prepare] 生成 delta 必须同时提供 --delta-base-manifest：基线版本 %s 已发布的 "
            "manifest.json 本地副本。重建出的基线与用户机器上的不一致，增量包会对谁都不匹配。"
            % base_version)
    path = Path(base_manifest)
    try:
        published = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit("[prepare] 读不出基线清单 %s：%s" % (path.name, exc))
    if not isinstance(published, dict):
        raise SystemExit("[prepare] 基线清单 %s 格式不对" % path.name)
    if published.get("version") != base_version:
        raise SystemExit("[prepare] 基线清单是 %s 的，与 --delta-base-version %s 不一致"
                         % (published.get("version"), base_version))
    full_payload = published.get("full_payload")
    expected = published.get("target_manifest_sha256") or (
        full_payload.get("target_manifest_sha256") if isinstance(full_payload, dict) else None)
    if not isinstance(expected, str) or not _SHA256_RE.fullmatch(expected):
        raise SystemExit("[prepare] 基线清单没有 target_manifest_sha256，无法核对 --delta-base")
    actual = target_manifest(Path(base_dir), base_version, root=root)["target_manifest_sha256"]
    if actual.lower() != expected.lower():
        raise SystemExit(
            "[prepare] --delta-base 目录与基线版本 %s 已发布的清单不符（目标清单哈希不同）："
            "请用当年发布的那份 onedir，而不是重新构建的" % base_version)


def stage_delta_payload(base_version: str, target_version: str,
                        stage_dir: Path, base_dir: Path,
                        target_dir: Path, *, delta_name_fn, sha256_fn,
                        root: Path = ROOT) -> tuple[Path, dict]:
    """从显式历史 onedir 基线生成 delta 资产和发布清单条目。"""
    module = _load_update_delta(root)
    if module is None:
        raise SystemExit("[prepare] 找不到 local/infrastructure/update/update_delta.py：delta 无法生成")
    base_dir = Path(base_dir)
    target_dir = Path(target_dir)
    if not base_dir.is_dir() or not target_dir.is_dir():
        raise SystemExit("[prepare] delta 基线或目标目录不存在")
    target = Path(stage_dir) / delta_name_fn(base_version, target_version)
    try:
        delta = module.build_delta(base_dir, target_dir, base_version, target_version)
        module.write_delta_zip(delta, target, target_dir=target_dir)
    except Exception as exc:
        raise SystemExit("[prepare] delta 生成失败：%s" % exc)
    metadata = {
        "name": target.name,
        "bytes": target.stat().st_size,
        "sha256": sha256_fn(target),
        "base_version": base_version,
        "target_version": target_version,
        "target_manifest_sha256": delta["target_manifest_sha256"],
        "target_manifest": delta["target_manifest"],
    }
    return target, metadata


def _read_limited_bytes(url: str, opener, limit: int) -> bytes:
    try:
        with opener(url) as resp:
            chunks: list[bytes] = []
            total = 0
            while True:
                block = resp.read(64 * 1024)
                if not block:
                    break
                total += len(block)
                if total > limit:
                    raise SystemExit("[fetch-base] 清单超过大小上限 %d 字节：%s" % (limit, url))
                chunks.append(block)
            return b"".join(chunks)
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit("[fetch-base] 下载清单失败 %s：%s" % (url, exc))


def _parse_base_manifest(raw: bytes, version: str) -> tuple[str, int, str, str]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SystemExit("[fetch-base] manifest 解析失败：%s" % exc)
    if not isinstance(data, dict) or data.get("version") != version:
        raise SystemExit("[fetch-base] manifest 版本与 %s 不一致" % version)
    full = data.get("full_payload")
    files = data.get("files")
    if not isinstance(full, dict) or not isinstance(files, dict):
        raise SystemExit("[fetch-base] manifest 缺少 full_payload 或 files")
    name = full.get("name")
    if not isinstance(name, str) or not _SAFE_NAME_RE.fullmatch(name):
        raise SystemExit("[fetch-base] full_payload.name 非法：%r" % (name,))
    entry = files.get(name)
    if not isinstance(entry, dict):
        raise SystemExit("[fetch-base] files 缺少 %s 记录" % name)
    size, sha = entry.get("bytes"), entry.get("sha256")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise SystemExit("[fetch-base] files[%s].bytes 非法" % name)
    if not isinstance(sha, str) or not _SHA256_RE.fullmatch(sha):
        raise SystemExit("[fetch-base] files[%s].sha256 非法" % name)
    if ("bytes" in full and full["bytes"] != size) or (
            "sha256" in full and str(full["sha256"]).lower() != sha.lower()):
        raise SystemExit("[fetch-base] full_payload 与 files 校验字段不一致")
    target_sha = data.get("target_manifest_sha256") or full.get("target_manifest_sha256")
    if not isinstance(target_sha, str) or not _SHA256_RE.fullmatch(target_sha):
        raise SystemExit("[fetch-base] manifest 缺少合法的 target_manifest_sha256")
    return name, size, sha.lower(), target_sha.lower()


def _cached_zip_valid(dest: Path, expect_bytes: int, expect_sha: str) -> bool:
    if not dest.is_file() or dest.stat().st_size != expect_bytes:
        return False
    digest = hashlib.sha256()
    with dest.open("rb") as fh:
        for chunk in iter(lambda: fh.read(256 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expect_sha.lower()


def _stream_download_verified(url: str, dest: Path, expect_bytes: int,
                              expect_sha: str, opener) -> Path:
    if _cached_zip_valid(dest, expect_bytes, expect_sha):
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    part.unlink(missing_ok=True)
    digest = hashlib.sha256()
    read_bytes = 0
    try:
        with opener(url) as resp, part.open("wb") as fh:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                read_bytes += len(chunk)
                if read_bytes > expect_bytes:
                    raise SystemExit("[fetch-base] 下载大小超出声明上限：%s" % dest.name)
                digest.update(chunk)
                fh.write(chunk)
    except SystemExit:
        part.unlink(missing_ok=True)
        raise
    except Exception as exc:
        part.unlink(missing_ok=True)
        raise SystemExit("[fetch-base] 下载完整版本包失败：%s" % exc)
    if read_bytes != expect_bytes or digest.hexdigest().lower() != expect_sha.lower():
        part.unlink(missing_ok=True)
        raise SystemExit("[fetch-base] %s 大小或 SHA-256 校验失败，已删除半成品" % dest.name)
    os.replace(part, dest)
    return dest


def _extract_member(zf: zipfile.ZipFile, info: zipfile.ZipInfo, extract_dir: Path,
                    root_resolved: Path, delta_mod, written_total: int) -> int:
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        raise SystemExit("[fetch-base] 归档包含符号链接：%s" % info.filename)
    is_dir = info.is_dir() or info.filename.endswith("/")
    rel = info.filename.rstrip("/") if is_dir else info.filename
    if rel or not is_dir:
        delta_mod.validate_relative_path(rel)
    if not rel:
        return written_total
    dest = (extract_dir / Path(*rel.split("/"))).resolve()
    if not dest.is_relative_to(root_resolved):
        raise SystemExit("[fetch-base] 归档路径越界：%s" % info.filename)
    if is_dir:
        dest.mkdir(parents=True, exist_ok=True)
        return written_total
    if written_total + info.file_size > MAX_EXTRACT_BYTES:
        raise SystemExit("[fetch-base] 归档解压总大小超过 1 GiB 上限")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(info, "r") as src, dest.open("wb") as dst:
        while True:
            buf = src.read(256 * 1024)
            if not buf:
                break
            written_total += len(buf)
            if written_total > MAX_EXTRACT_BYTES:
                raise SystemExit("[fetch-base] 归档解压总大小超过 1 GiB 上限")
            dst.write(buf)
    return written_total


def _extract_and_verify(zip_path: Path, extract_dir: Path, version: str,
                        expect_target_sha: str, root: Path) -> None:
    delta_mod = _load_update_delta(root)
    if delta_mod is None:
        raise SystemExit("[fetch-base] 找不到 local/infrastructure/update/update_delta.py")
    extract_dir.mkdir(parents=True, exist_ok=True)
    root_resolved = extract_dir.resolve()
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_EXTRACT_MEMBERS:
                raise SystemExit("[fetch-base] 归档成员数超过 %d 上限" % MAX_EXTRACT_MEMBERS)
            written_total = 0
            for info in infos:
                written_total = _extract_member(
                    zf, info, extract_dir, root_resolved, delta_mod, written_total)
        actual_sha = delta_mod.manifest_from_directory(
            extract_dir, version=version)["target_manifest_sha256"]
        if actual_sha.lower() != expect_target_sha.lower():
            raise SystemExit("[fetch-base] 解包后目标清单哈希不匹配，已删除临时目录")
    except SystemExit:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise SystemExit("[fetch-base] 解包校验失败：%s" % exc)


def _replace_dir_with_retry(src: Path, dst: Path, *,
                            attempts: int = 15, delay: float = 0.4) -> None:
    """落盘解包目录：Windows 杀毒扫描可能短暂占用新解出的 exe/dll，做有界重试。"""
    try:
        if dst.exists():
            shutil.rmtree(dst)
        for attempt in range(attempts):
            try:
                os.replace(src, dst)
                return
            except PermissionError:
                if attempt + 1 >= attempts:
                    raise
                time.sleep(delay)
    except OSError as exc:
        shutil.rmtree(src, ignore_errors=True)
        raise SystemExit("[fetch-base] 无法落盘基线目录 %s：%s" % (dst, exc))


def fetch_base(version: str, cache_root, *, open_url=None, root: Path = ROOT) -> Path:
    """下载指定历史版本的 manifest 与完整包并核验解包到本地基线缓存目录。"""
    _parse_version_tuple(version)
    opener = open_url or (lambda url: urllib.request.urlopen(url, timeout=FETCH_TIMEOUT_S))
    base_url = "%s/v%s" % (RELEASE_DOWNLOAD_BASE, version)
    manifest_bytes = _read_limited_bytes(
        base_url + "/manifest.json", opener, MAX_MANIFEST_BYTES)
    name, expect_bytes, expect_sha, expect_target_sha = _parse_base_manifest(
        manifest_bytes, version)
    base_root = Path(cache_root) / version
    zip_path = _stream_download_verified(
        "%s/%s" % (base_url, name), base_root / name, expect_bytes, expect_sha, opener)
    extract_dir = base_root / (".extract-" + uuid.uuid4().hex)
    _extract_and_verify(zip_path, extract_dir, version, expect_target_sha, root)
    _replace_dir_with_retry(extract_dir, base_root / "onedir")
    manifest_part = base_root / "manifest.json.part"
    manifest_part.write_bytes(manifest_bytes)
    os.replace(manifest_part, base_root / "manifest.json")
    return base_root / "onedir"


def discover_bases(cache_root, target_version: str,
                   limit: int = 2) -> list[tuple[Path, str, Path]]:
    """从本地基线缓存挑选比目标版本旧、且同时含 manifest.json 与 onedir 的最新几个版本。"""
    target_tuple = _parse_version_tuple(target_version)
    root = Path(cache_root)
    if not root.is_dir():
        return []
    candidates: list[tuple[tuple[int, int, int], Path, str, Path]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = _VERSION_RE.fullmatch(child.name)
        if not match:
            continue
        parsed = tuple(int(part) for part in match.groups())
        if parsed >= target_tuple:
            continue
        manifest_path = child / "manifest.json"
        onedir = child / "onedir"
        if manifest_path.is_file() and onedir.is_dir():
            candidates.append((parsed, onedir, child.name, manifest_path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [(onedir, ver, manifest) for _, onedir, ver, manifest in candidates[:limit]]


def resolve_delta_bases(dist_dir: Path, version: str, delta_base,
                        delta_base_version, delta_base_manifest, *,
                        auto_delta: bool, verify_fn) -> list[tuple[Path, str, object]]:
    """确定本次构建要生成增量的基线列表并在构建前逐个校验。"""
    # 基线核对放在构建之前：基线不对时不值得再等几十分钟的构建
    if delta_base is not None or delta_base_version is not None:
        if delta_base is None or not delta_base_version:
            raise SystemExit("[prepare] 生成 delta 需要同时提供 --delta-base 和 --delta-base-version")
        verify_fn(delta_base, delta_base_version, delta_base_manifest)
        return [(Path(delta_base), str(delta_base_version), delta_base_manifest)]
    if not auto_delta:
        return []
    bases = discover_bases(Path(dist_dir) / "delta-bases", version)
    if not bases:
        raise SystemExit("[prepare] 找不到本地增量基线缓存：请先运行 --fetch-base <上一版本号>，或显式 --no-delta")
    for base_dir, base_ver, base_man in bases:
        verify_fn(base_dir, base_ver, base_man)
    return bases


def _read_hex_fingerprint(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return None
    return text if _SHA256_RE.fullmatch(text) else None


def reuse_launcher(onedir_dir: Path, bases) -> str | None:
    """按从新到旧选首个启动器指纹一致的基线，复制其已发布 update-launcher.exe 覆盖新版本目录。"""
    target_dir = Path(onedir_dir)
    current_fp = _read_hex_fingerprint(target_dir / LAUNCHER_FINGERPRINT_FILE)
    if not current_fp:
        return None
    for base_dir, base_ver, _ in bases:
        src_dir = Path(base_dir)
        base_fp = _read_hex_fingerprint(src_dir / LAUNCHER_FINGERPRINT_FILE)
        base_exe = src_dir / LAUNCHER_EXE_NAME
        if base_fp == current_fp and base_exe.is_file():
            shutil.copy2(base_exe, target_dir / LAUNCHER_EXE_NAME)
            return base_ver
    return None


def stage_deltas(bases, target_version: str, stage_dir: Path, target_dir: Path,
                 *, stage_delta_fn) -> tuple[list[Path], list[dict]]:
    """为已核对的基线列表生成增量包并按从新到旧返回路径与清单摘要。"""
    paths: list[Path] = []
    infos: list[dict] = []
    for base_dir, base_ver, _ in bases:
        d_path, d_info = stage_delta_fn(base_ver, target_version, stage_dir, Path(base_dir), target_dir)
        paths.append(d_path)
        infos.append(d_info)
        print("[prepare] delta 资产：%s  %.1f MB（基线 %s）"
              % (d_path.name, d_path.stat().st_size / 1024 / 1024, base_ver))
    return paths, infos
