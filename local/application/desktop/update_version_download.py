# -*- coding: utf-8 -*-
"""版本目录更新的纯下载与暂存辅助函数（不持有服务锁）。

从 update_service.run_version_download 拆出，隔离进度节流、增量/完整包选择、
暂存清理与完整安装器兜底下载；UpdateService._lock 的读写仍留在 update_service。

@author Author
"""
from __future__ import annotations


def can_use_version_dir(installer, switch_available: bool) -> bool:
    """与下载选路共用的版本目录切换前提：环境支持且携带完整 target_manifest。"""
    full = installer.get("full") if isinstance(installer, dict) else None
    return (bool(switch_available) and isinstance(full, dict)
            and isinstance(full.get("target_manifest"), dict))


def _positive_bytes(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def download_plan(installer, current_version: str, switch_available: bool) -> dict | None:
    """算出本次检查实际要下载的资产类型与字节数，供界面确认前展示。"""
    if not isinstance(installer, dict) or not installer.get("url"):
        return None
    if can_use_version_dir(installer, switch_available):
        mode, selected, _ = select_version_payload(installer, current_version)
        raw_bytes = selected.get("bytes") if isinstance(selected, dict) else 0
        return {"kind": mode, "bytes": _positive_bytes(raw_bytes)}
    return {"kind": "installer", "bytes": _positive_bytes(installer.get("bytes"))}


def select_version_payload(installer: dict, current_version: str) -> tuple[str, dict | None, dict]:
    """按当前版本选匹配的增量包；没有匹配项时回退到完整更新包。"""
    delta = installer.get("delta")
    deltas = installer.get("deltas")
    selected = None
    if isinstance(deltas, list):
        selected = next(
            (item for item in deltas
             if isinstance(item, dict) and item.get("base_version") == current_version),
            None)
    if selected is None and isinstance(delta, dict) and delta.get("base_version") == current_version:
        selected = delta
    mode = "delta" if selected is not None else "full"
    full = installer.get("full") if isinstance(installer.get("full"), dict) else installer
    return mode, (selected or full), full


def download_with_progress(asset: dict, *, fetch, cancel, emit_progress,
                           error_text: str) -> dict:
    """按 1 MiB 步进节流回调进度并执行下载，兜住未预期异常。"""
    total = asset.get("bytes") if isinstance(asset.get("bytes"), int) else 0
    last = [0]

    def progress(done: int, expect: int) -> None:
        if done == expect or done - last[0] >= 1024 * 1024:
            last[0] = done
            emit_progress(done, total, False)

    emit_progress(0, total, True)
    try:
        return fetch(
            asset["url"], name=asset["name"],
            expect_bytes=asset.get("bytes") or 0,
            expect_sha256=asset.get("sha256") or "",
            cancel=cancel, progress=progress)
    except Exception:
        return {"ok": False, "error_code": "unexpected_error", "text": error_text}


def download_version_asset(asset: dict | None, asset_mode: str, *, base: dict,
                           publish, download, download_delta, download_full,
                           cancel) -> dict:
    """下载增量包或完整版本目录包，并按包类型回推进度。"""
    if not isinstance(asset, dict) or not asset.get("url"):
        return {"ok": False, "error_code": "no_payload", "text": "没有可下载的更新包。"}
    state = "downloading_delta" if asset_mode == "delta" else "downloading_full"
    text = "正在下载增量包…" if asset_mode == "delta" else "正在下载安装包…"
    fetch = (
        download_delta if asset_mode == "delta" and download_delta is not None
        else (download_full if asset_mode == "full" and download_full is not None else download)
    )

    def emit_progress(done: int, total: int, _initial: bool) -> None:
        publish(dict(base, state=state, payload_kind=asset_mode, text=text,
                     downloaded=done, total_bytes=total), False)

    return download_with_progress(
        asset, fetch=fetch, cancel=cancel, emit_progress=emit_progress,
        error_text="下载没能完成，请重试。")


def stage_and_cleanup(stage_update, base_dir, got: dict, staging_dir, *,
                      mode: str, current_version: str, selected: dict,
                      target_manifest, target_version, cleanup_download) -> dict:
    """校验并准备暂存更新目录，完成后尽力清理已下载的压缩包。"""
    downloaded_path = str(got.get("path") or "")
    result = stage_update(
        base_dir, downloaded_path, staging_dir, mode=mode,
        base_version=current_version,
        target_manifest=selected.get("target_manifest") or target_manifest,
        target_version=selected.get("target_version") or target_version)
    if cleanup_download is not None and downloaded_path:
        try:
            cleanup_download(downloaded_path)
        except Exception:
            pass
    return result


def download_fallback_asset(base: dict, installer: dict, *, publish, cancel,
                            download_installer_fallback, reason: str) -> dict | None:
    """版本目录链路失败时下载完整 Inno 安装器（不改锁内状态）。"""
    if download_installer_fallback is None or not installer.get("url"):
        return None

    def emit_progress(done: int, total: int, initial: bool) -> None:
        text = "增量更新未能应用，正在下载完整安装器…" if initial else "正在下载完整安装器…"
        publish(dict(base, state="downloading_full", payload_kind="installer_fallback",
                     text=text, fallback_reason=reason,
                     downloaded=done, total_bytes=total), False)

    return download_with_progress(
        installer, fetch=download_installer_fallback, cancel=cancel,
        emit_progress=emit_progress, error_text="完整安装器下载没能完成，请重试。")
