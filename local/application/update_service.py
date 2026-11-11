# -*- coding: utf-8 -*-
"""更新用例：GitHub 最新版本检查、安装器下载校验、启动安装。

端口（fetch / download / publish / emit）由 interface 注入；本模块不直接
import app，也不读版本文件、不拼文件路径。状态字段挂在调用方传入的
state 上（Api 实例），便于界面重载后按 request_id 对账。

@author Author
"""
from __future__ import annotations

from typing import Protocol


class UpdateState(Protocol):
    """更新用例需要的状态面（由 Api 实例满足；测试可给内存替身）。"""

    _lock: object
    _emit: object
    _updating: bool
    _update_result: "dict | None"
    _update_installer: "dict | None"
    _update_installer_path: str
    _update_cancelled: bool
    _closing: bool
    _update_staging_path: str


def run_check(state, request_id: str, *, fetch, current_version: str,
              latest_url: str) -> None:
    """后台更新检查：结论写入 state 并推 update 事件（单飞由调用方负责）。"""
    result = {"state": "error", "current_version": current_version,
              "latest_version": None, "url": latest_url,
              "text": "检查没能完成，请重试。", "error_code": "unexpected_error",
              "installer": None}
    try:
        checked = fetch(current_version)
        if isinstance(checked, dict):
            result = checked
    except Exception:
        # 最后兜底仍须解锁；普通更新错误不进入组件/登录错误通道。
        pass
    finally:
        result = dict(result, request_id=request_id)
        skipped = result.pop("manifest_skipped", None)
        installer = result.get("installer")
        with state._lock:
            state._update_result = result
            state._update_installer = installer if isinstance(installer, dict) else None
            # 新一轮检查结论取代旧产物：之前校验过的安装器不再对应当前结论
            state._update_installer_path = ""
            state._update_staging_path = ""
            state._update_cancelled = False
            state._updating = False
            closing = state._closing
        if not closing:
            if skipped:
                # 发布清单里新客户端用不到、也不合格的项：只记一笔，不影响更新结论
                state._emit("log", "[i] 发布清单有 %d 个未使用的条目不合格，已跳过：%s"
                            % (len(skipped), "、".join(str(item) for item in skipped[:5])))
            state._emit("update", result)


def run_download(state, request_id: str, installer: dict, *,
                 download, publish, current_version: str,
                 latest_url: str, download_delta=None,
                 download_full=None, cleanup_download=None,
                 download_installer_fallback=None,
                 **version_options) -> None:
    """流式下载安装器并校验（download 端口），进度/结论经 publish 推给界面。"""
    if version_options:
        return run_version_download(
            state, request_id, installer, download=download, publish=publish,
            current_version=current_version, latest_url=latest_url,
            download_delta=download_delta, download_full=download_full,
            cleanup_download=cleanup_download,
            download_installer_fallback=download_installer_fallback,
            **version_options)
    # 下载结论继承最近一次检查的上下文（版本/发布页/安装器），界面不必再拼
    base = dict(state._update_result or {})
    base.update({"request_id": request_id, "current_version": current_version,
                 "url": latest_url, "installer": installer,
                 "error_code": ""})
    total = installer.get("bytes") if isinstance(installer.get("bytes"), int) else 0
    step = 1024 * 1024
    last_sent = [0]

    def progress(done: int, expect: int) -> None:
        # 进度按 1 MiB 步进回推：64 KiB 一块全部回推会把界面打满
        if done == expect or done - last_sent[0] >= step:
            last_sent[0] = done
            publish(dict(base, state="downloading",
                         text="正在下载安装包…",
                         downloaded=done, total_bytes=total), False)

    publish(dict(base, state="downloading", text="正在下载安装包…",
                 downloaded=0, total_bytes=total), False)
    try:
        got = download(
            installer["url"], name=installer["name"],
            expect_bytes=installer.get("bytes") or 0,
            expect_sha256=installer.get("sha256") or "",
            cancel=lambda: state._update_cancelled or state._closing,
            progress=progress)
    except Exception:
        # 只兜未预期异常；可预期失败由下载器分类返回，不在这层吞掉
        got = {"ok": False, "error_code": "unexpected_error",
               "text": "下载没能完成，请重试。"}
    if got.get("ok"):
        path = str(got.get("path") or "")
        with state._lock:
            state._update_installer_path = path
        publish(dict(base, state="ready_to_install",
                     text="安装包已下载并校验通过，可以启动安装程序。",
                     installer_path=path), True)
        return
    code = str(got.get("error_code") or "unexpected_error")
    if code == "cancelled":
        publish(dict(base, state="available", error_code=code,
                     text="已取消下载，可重新下载。"), True)
    else:
        publish(dict(base, state="failed", error_code=code,
                     text=str(got.get("text") or "下载没能完成，请重试。")), True)


def run_version_download(state, request_id: str, installer: dict, *,
                         download, publish, current_version: str,
                         latest_url: str, stage_update, base_dir,
                         staging_dir, target_manifest=None,
                         target_version=None, download_delta=None,
                         download_full=None, cleanup_download=None,
                         download_installer_fallback=None) -> None:
    """下载并准备版本目录更新；切换动作留给主程序退出后的启动器。"""
    base = dict(state._update_result or {})
    base.update({"request_id": request_id, "current_version": current_version,
                 "url": latest_url, "installer": installer, "error_code": ""})
    delta = installer.get("delta")
    deltas = installer.get("deltas")
    selected = None
    if isinstance(deltas, list):
        selected = next((item for item in deltas
                         if isinstance(item, dict)
                         and item.get("base_version") == current_version), None)
    if selected is None and isinstance(delta, dict) and delta.get("base_version") == current_version:
        selected = delta
    mode = "delta" if selected is not None else "full"
    full = installer.get("full") if isinstance(installer.get("full"), dict) else installer
    selected = selected or full

    def do_download(asset, asset_mode):
        total = asset.get("bytes") if isinstance(asset.get("bytes"), int) else 0
        last = [0]
        def progress(done, expect):
            if done == expect or done - last[0] >= 1024 * 1024:
                last[0] = done
                publish(dict(base, state="downloading_delta" if asset_mode == "delta" else "downloading_full",
                             payload_kind=asset_mode,
                             text="正在下载增量包…" if asset_mode == "delta" else "正在下载安装包…",
                             downloaded=done, total_bytes=total), False)
        publish(dict(base, state="downloading_delta" if asset_mode == "delta" else "downloading_full",
                     payload_kind=asset_mode,
                     text="正在下载增量包…" if asset_mode == "delta" else "正在下载安装包…",
                     downloaded=0, total_bytes=total), False)
        try:
            fetch = download_delta if asset_mode == "delta" and download_delta is not None else (
                download_full if asset_mode == "full" and download_full is not None else download)
            return fetch(asset["url"], name=asset["name"],
                            expect_bytes=asset.get("bytes") or 0,
                            expect_sha256=asset.get("sha256") or "",
                            cancel=lambda: state._update_cancelled or state._closing,
                            progress=progress)
        except Exception:
            return {"ok": False, "error_code": "unexpected_error",
                    "text": "下载没能完成，请重试。"}

    def fallback_to_installer(reason):
        """版本目录链路失败时回到用户已有的完整 Inno 安装器。"""
        if download_installer_fallback is None or not installer.get("url"):
            return False
        total = installer.get("bytes") if isinstance(installer.get("bytes"), int) else 0
        last = [0]
        def progress(done, expect):
            if done != expect and done - last[0] < 1024 * 1024:
                return
            last[0] = done
            publish(dict(base, state="downloading_full", payload_kind="installer_fallback",
                         text="正在下载完整安装器…", fallback_reason=reason,
                         downloaded=done, total_bytes=total), False)
        publish(dict(base, state="downloading_full", payload_kind="installer_fallback",
                     text="增量更新未能应用，正在下载完整安装器…",
                     fallback_reason=reason, downloaded=0, total_bytes=total), False)
        try:
            got = download_installer_fallback(
                installer["url"], name=installer["name"],
                expect_bytes=installer.get("bytes") or 0,
                expect_sha256=installer.get("sha256") or "",
                cancel=lambda: state._update_cancelled or state._closing,
                progress=progress)
        except Exception:
            got = {"ok": False, "error_code": "unexpected_error",
                   "text": "完整安装器下载没能完成，请重试。"}
        if not got.get("ok"):
            return False
        path = str(got.get("path") or "")
        with state._lock:
            state._update_installer_path = path
        publish(dict(base, state="ready_to_install", payload_kind="installer_fallback",
                     text="完整安装器已下载并校验通过，可以启动安装程序。",
                     installer_path=path, fallback_reason=reason), True)
        return True

    got = do_download(selected, mode) if isinstance(selected, dict) and selected.get("url") else {
        "ok": False, "error_code": "no_payload", "text": "没有可下载的更新包。"}
    if (not got.get("ok") and mode == "delta"
            and got.get("error_code") != "cancelled"
            and full is not selected and full.get("url")):
        mode, selected = "full", full
        got = do_download(selected, mode)
    if not got.get("ok"):
        code = str(got.get("error_code") or "unexpected_error")
        if code != "cancelled" and fallback_to_installer("download_failed"):
            return
        publish(dict(base, state="available" if code == "cancelled" else "failed",
                     error_code=code, text=str(got.get("text") or "下载没能完成，请重试。")), True)
        return

    publish(dict(base, state="applying", payload_kind=mode,
                 text="正在校验并准备更新目录…"), False)
    downloaded_path = str(got.get("path") or "")
    result = stage_update(
        base_dir, str(got.get("path") or ""), staging_dir, mode=mode,
        base_version=current_version,
        target_manifest=selected.get("target_manifest") or target_manifest,
        target_version=selected.get("target_version") or target_version)
    if cleanup_download is not None and downloaded_path:
        try:
            cleanup_download(downloaded_path)
        except Exception:
            pass
    if not result.get("ok") and mode == "delta" and full is not selected and full.get("url"):
        mode, selected = "full", full
        got = do_download(selected, mode)
        if not got.get("ok") and got.get("error_code") == "cancelled":
            # 增量应用失败后改下完整包，用户此时取消：口径与首段下载一致，回到可重新下载；
            # 不能落到 apply_failed，更不能再去拉完整安装器（用户明明已经喊停）。
            publish(dict(base, state="available", error_code="cancelled",
                         text="已取消下载，可重新下载。"), True)
            return
        if got.get("ok"):
            downloaded_path = str(got.get("path") or "")
            result = stage_update(
                base_dir, str(got.get("path") or ""), staging_dir, mode="full",
                base_version=current_version,
                target_manifest=selected.get("target_manifest") or target_manifest,
                target_version=selected.get("target_version") or target_version)
            if cleanup_download is not None and downloaded_path:
                try:
                    cleanup_download(downloaded_path)
                except Exception:
                    pass
    if result.get("ok"):
        path = str(result.get("path") or staging_dir)
        with state._lock:
            state._update_staging_path = path
        publish(dict(base, state="ready_to_restart", payload_kind=mode,
                     text="更新目录已准备好，关闭程序后完成切换。",
                     staging_path=path), True)
    else:
        if fallback_to_installer("apply_failed"):
            return
        # staging 的异常文本常带本机绝对路径，不能原样推给界面；细节只写运行记录。
        detail = str(result.get("detail") or "").strip()
        if detail:
            state._emit("log", "[X] 更新包应用失败：%s" % detail)
        publish(dict(base, state="failed", error_code="apply_failed",
                     text="更新包应用失败，已保留当前版本。"), True)
