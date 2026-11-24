# -*- coding: utf-8 -*-
"""更新用例：GitHub 最新版本检查、安装器下载校验、启动安装。

状态与单飞槽位在 UpdateService（一把自己的锁）；构造时只注入 emit 与 is_closing，
其余端口每次调用时由 interface 传入，测试打在界面层模块与 updater 上的补丁才在
调用时刻生效。本模块不反向依赖界面层，也不读版本文件、不拼文件路径。

@author Author
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass

from application.desktop.update_version_download import (
    download_fallback_asset,
    download_version_asset,
    select_version_payload,
    stage_and_cleanup,
)

_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


@dataclass(frozen=True)
class LaunchPorts:
    """启动安装程序或更新启动器需要的外部动作，由 interface 在调用时装配。"""

    version_switch_available: object
    update_version_paths: object
    launcher_command: object
    spawn: object
    cwd: str
    env_factory: object
    creationflags: int
    parent_pid: int
    defer_close: object
    request_close: object
    launch_installer: object


class UpdateService:
    """更新的状态与用例：检查、下载校验、启动安装，单飞共用一个槽位。

    字段沿用原来挂在 Api 上的名字（run_check / run_download 直接读写）：`_updating` 表示
    「任一更新动作在途」，`_update_installer` 是检查阶段选好的安装器资产，下载只信它、
    不收界面传来的地址，`_update_installer_path` 是校验通过后的本地产物。
    """

    def __init__(self, *, emit, is_closing):
        self._lock = threading.Lock()
        self._emit = emit
        self._is_closing = is_closing
        self._updating = False
        self._update_request_id = ""
        self._update_result: dict | None = None
        self._update_installer: dict | None = None
        self._update_installer_path = ""
        self._update_staging_path = ""
        self._update_cancelled = False

    def is_closing(self) -> bool:
        return bool(self._is_closing())

    def snapshot(self) -> dict:
        """界面重载时接管在途请求：四个键与原来 bootstrap 里的 update_check 一致。"""
        with self._lock:
            return {"checking": self._updating, "request_id": self._update_request_id,
                    "result": self._update_result, "installer_path": self._update_installer_path}

    def publish(self, payload: dict, finished: bool, *, update_version_paths=None) -> None:
        """把更新状态推给界面并留档；finished 才释放单飞槽位。"""
        if isinstance(payload, dict) and payload.get("state") == "ready_to_restart":
            # ready_to_restart 只公布版本端口的受控路径；真正切换必须等主程序
            # 退出后由独立 launcher 完成，避免运行中的 EXE 覆盖自身文件。
            paths = update_version_paths()
            payload = dict(payload)
            payload.setdefault("version_root", str(paths["root"]))
            payload.setdefault("current_file", str(paths["current_file"]))
            payload.setdefault("target_version", str(payload.get("latest_version") or ""))
        with self._lock:
            self._update_result = payload
            if finished:
                self._updating = False
            closing = self.is_closing()
        if not closing:
            self._emit("update", payload)

    def _refuse(self, request_id) -> dict | None:
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return {"ok": False, "queued": False, "text": "更新请求无效，请重试。"}
        if self.is_closing():
            return {"ok": False, "queued": False, "text": "程序正在关闭。"}
        if self._updating:
            return {"ok": True, "queued": True, "skipped": True,
                    "request_id": self._update_request_id}
        return None

    def _spawn(self, thread_factory, job, args, failure: str) -> dict:
        try:
            thread_factory(target=job, args=args, daemon=True).start()
        except Exception:
            with self._lock:
                self._updating = False
            return {"ok": False, "queued": False, "text": failure}
        return {"ok": True, "queued": True, "request_id": args[0]}

    def start_check(self, request_id: str, *, thread_factory, job,
                    cleanup_staging, update_version_paths, current_version: str) -> dict:
        """只登记轻量后台查询，不在桥接线程等待网络，也不改变报名门禁。"""
        with self._lock:
            if (refusal := self._refuse(request_id)) is not None:
                return refusal
            current = self._update_result if isinstance(self._update_result, dict) else {}
            if current.get("state") == "launching":
                # 更新启动器已拉起、正等本进程退出：_update_staging_path 就是它要切换的
                # 目录，这时再检查更新不能把它当旧暂存清掉。直接回当前状态，界面按
                # 同一 request_id 接管快照。
                return {"ok": True, "queued": True, "skipped": True,
                        "request_id": str(current.get("request_id") or self._update_request_id)}
            stale_staging = self._update_staging_path
            self._update_staging_path = ""
            self._updating = True
            self._update_request_id = request_id
        if stale_staging:
            cleanup_staging(stale_staging, version_root=update_version_paths()["root"])
        self.publish({"request_id": request_id, "current_version": current_version,
                      "state": "checking", "text": "正在检查更新…", "error_code": ""}, False)
        return self._spawn(thread_factory, job, (request_id,), "检查没能启动，请重试。")

    def start_download(self, request_id: str, *, thread_factory, job) -> dict:
        """用户确认后启动安装器下载：单飞后台流式下载并校验，事件回推进度与结论。"""
        with self._lock:
            if (refusal := self._refuse(request_id)) is not None:
                return refusal
            installer = self._update_installer
            if not isinstance(installer, dict) or not installer.get("url"):
                return {"ok": False, "queued": False,
                        "text": "当前没有可下载的安装包，请前往下载页。"}
            self._updating = True
            self._update_request_id = request_id
            self._update_cancelled = False
        return self._spawn(thread_factory, job, (request_id, installer),
                           "下载没能启动，请重试。")

    def download_job(self, request_id: str, installer: dict, *, version_switch_available,
                     update_version_paths, stage_update, download_payload, download_installer,
                     cleanup_download, current_version: str, latest_url: str) -> None:
        version_options = {}
        full_payload = installer.get("full")
        # 只有真能走版本目录切换的环境才下载版本目录包；独立 EXE、源码态直接下完整
        # 安装器，磁盘上不留 .staging-*，用户也不会在 update_launch 处被拒绝。
        if (version_switch_available() and isinstance(full_payload, dict)
                and isinstance(full_payload.get("target_manifest"), dict)):
            paths = update_version_paths()
            target_version = str(full_payload.get("target_version")
                                 or (self._update_result or {}).get("latest_version") or "")
            version_options = {
                "stage_update": stage_update,
                "base_dir": paths["base_dir"],
                "staging_dir": paths["root"] / (".staging-" + request_id),
                "target_manifest": full_payload["target_manifest"],
                "target_version": target_version,
            }
        run_download(
            self, request_id, installer,
            download=(download_payload if version_options else download_installer),
            publish=lambda payload, finished: self.publish(
                payload, finished, update_version_paths=update_version_paths),
            current_version=current_version, latest_url=latest_url,
            cleanup_download=(cleanup_download if version_options else None),
            download_installer_fallback=(download_installer if version_options else None),
            **version_options)

    def cancel(self) -> dict:
        """用户取消下载：只置取消标记，下载线程在下一块之间停下并清理半成品。"""
        with self._lock:
            self._update_cancelled = True
        return {"ok": True}

    def launch(self, request_id: str, ports: LaunchPorts) -> dict:
        """用户确认后启动已校验的安装器；启动前先回推 launching 状态。

        安装器路径：关闭主程序由调用方控制，这里不退出、不自动重启。
        版本目录切换路径：启动器拉起后主程序约 1 秒自己走「退出」关窗，切换才能继续。
        两条路径失败都不改会话和偏好。
        """
        if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
            return {"ok": False, "text": "更新请求无效，请重试。"}
        with self._lock:
            if self.is_closing():
                return {"ok": False, "text": "程序正在关闭。"}
            path = self._update_installer_path
            base = dict(self._update_result or {})
            staging = self._update_staging_path
        if staging and base.get("state") == "ready_to_restart":
            return self._launch_switch(request_id, staging, base, ports)
        if not path:
            return {"ok": False, "text": "还没有已校验的安装包，请先下载。"}

        def push(text):
            self.publish(dict(base, request_id=request_id, state="launching", text=text,
                              installer_path=path, error_code=""), False)

        # 安装器启动前先回推状态：界面能看到「正在启动安装程序…」
        push("正在启动安装程序…")
        got = ports.launch_installer(path)
        if not got.get("ok"):
            text = str(got.get("text") or "安装程序没能启动，请重试。")
            self.publish(dict(base, request_id=request_id, state="failed", text=text,
                              installer_path=path, error_code=str(
                                  got.get("error_code") or "launch_failed")), False)
            return {"ok": False, "text": text}
        push(text := "安装程序已启动。请先关闭本工具，再按向导完成安装。")
        return {"ok": True, "path": path, "text": text}

    def _launch_switch(self, request_id: str, staging: str, base: dict,
                       ports: LaunchPorts) -> dict:
        """版本目录切换：起启动器并在约 1 秒后让主程序走现有的退出动作。"""
        if not ports.version_switch_available():
            # 防御分支：与 download_job 用同一判据（冻结态、启动器文件在、
            # 正从 versions/<当前版本>/ 运行），下载和启动不会各说各话。
            # 源码态与 onefile 没有独立旁路入口，只保留 ready 状态，
            # 避免在运行中的主程序里直接切换版本目录。
            return {"ok": False, "state": "ready_to_restart", "request_id": request_id,
                    "text": "更新目录已准备好，请使用完整版本重启后完成切换。"}
        paths = ports.update_version_paths()
        target_version = str(base.get("target_version") or base.get("latest_version") or "")
        if not target_version:
            return {"ok": False, "text": "更新版本信息不完整，请重新检查。"}

        def launch_ready(text):
            self.publish(dict(base, request_id=request_id, state="launching", text=text,
                              staging_path=staging, version_root=str(paths["root"]),
                              target_version=target_version, error_code=""), False)

        command = ports.launcher_command(
            "apply", staging=staging, version_root=paths["root"], parent_pid=ports.parent_pid,
            current_file=paths["current_file"], target_version=target_version)
        launch_ready("正在准备重启…")
        try:
            ports.spawn(command, cwd=ports.cwd, close_fds=True,
                        env=ports.env_factory(), creationflags=ports.creationflags)
        except (OSError, ValueError) as exc:
            text = "更新启动器没能启动，请重试。"
            self.publish(dict(base, request_id=request_id, state="failed", text=text,
                              staging_path=staging, error_code="launcher_failed"), False)
            self._emit("log", "[X] 更新启动器启动失败：%s" % type(exc).__name__)
            return {"ok": False, "text": text, "error_code": "launcher_failed"}
        # 启动器已拉起并在等本进程退出（最长 120 秒）。先把第二段文案推给界面，
        # 再约 1 秒后走现有的关窗口「退出」动作：不另写退出逻辑，也让界面来得及
        # 收到文案。启动器没拉起（上面的 except 分支）时不会走到这里，不会误关主程序。
        text = "更新启动器已启动，正在关闭本工具完成切换…"
        launch_ready(text)
        ports.defer_close(ports.request_close, delay=1.0)
        return {"ok": True, "path": staging, "text": text}


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
            closing = state.is_closing()
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
            cancel=lambda: state._update_cancelled or state.is_closing(),
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


def _try_installer_fallback(state, base: dict, installer: dict, publish,
                            download_installer_fallback, reason: str) -> bool:
    """版本目录链路失败时回到用户已有的完整 Inno 安装器。"""
    got = download_fallback_asset(
        base, installer, publish=publish,
        cancel=lambda: state._update_cancelled or state.is_closing(),
        download_installer_fallback=download_installer_fallback, reason=reason)
    if not got or not got.get("ok"):
        return False
    path = str(got.get("path") or "")
    with state._lock:
        state._update_installer_path = path
    publish(dict(base, state="ready_to_install", payload_kind="installer_fallback",
                 text="完整安装器已下载并校验通过，可以启动安装程序。",
                 installer_path=path, fallback_reason=reason), True)
    return True


def _finish_version_download(state, base: dict, mode: str, staging_dir,
                             result: dict, publish, download_installer_fallback,
                             installer: dict) -> None:
    """把暂存结果落进 state 或回退到完整安装器。"""
    if result.get("ok"):
        path = str(result.get("path") or staging_dir)
        with state._lock:
            state._update_staging_path = path
        publish(dict(base, state="ready_to_restart", payload_kind=mode,
                     text="更新目录已准备好，关闭程序后完成切换。",
                     staging_path=path), True)
        return
    if _try_installer_fallback(state, base, installer, publish,
                               download_installer_fallback, "apply_failed"):
        return
    # staging 的异常文本常带本机绝对路径，不能原样推给界面；细节只写运行记录。
    detail = str(result.get("detail") or "").strip()
    if detail:
        state._emit("log", "[X] 更新包应用失败：%s" % detail)
    publish(dict(base, state="failed", error_code="apply_failed",
                 text="更新包应用失败，已保留当前版本。"), True)


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
    cancel = lambda: state._update_cancelled or state.is_closing()  # noqa: E731
    mode, selected, full = select_version_payload(installer, current_version)
    got = download_version_asset(
        selected, mode, base=base, publish=publish, download=download,
        download_delta=download_delta, download_full=download_full, cancel=cancel)
    if (not got.get("ok") and mode == "delta"
            and got.get("error_code") != "cancelled"
            and full is not selected and full.get("url")):
        mode, selected = "full", full
        got = download_version_asset(
            selected, mode, base=base, publish=publish, download=download,
            download_delta=download_delta, download_full=download_full, cancel=cancel)
    if not got.get("ok"):
        code = str(got.get("error_code") or "unexpected_error")
        if code != "cancelled" and _try_installer_fallback(
                state, base, installer, publish, download_installer_fallback, "download_failed"):
            return
        publish(dict(base, state="available" if code == "cancelled" else "failed",
                     error_code=code, text=str(got.get("text") or "下载没能完成，请重试。")), True)
        return
    publish(dict(base, state="applying", payload_kind=mode, text="正在校验并准备更新目录…"), False)
    result = stage_and_cleanup(
        stage_update, base_dir, got, staging_dir, mode=mode,
        current_version=current_version, selected=selected,
        target_manifest=target_manifest, target_version=target_version,
        cleanup_download=cleanup_download)
    if not result.get("ok") and mode == "delta" and full is not selected and full.get("url"):
        mode, selected = "full", full
        got = download_version_asset(
            selected, mode, base=base, publish=publish, download=download,
            download_delta=download_delta, download_full=download_full, cancel=cancel)
        if not got.get("ok") and got.get("error_code") == "cancelled":
            # 增量应用失败后改下完整包，用户此时取消：口径与首段下载一致，回到可重新下载；
            # 不能落到 apply_failed，更不能再去拉完整安装器（用户明明已经喊停）。
            publish(dict(base, state="available", error_code="cancelled",
                         text="已取消下载，可重新下载。"), True)
            return
        if got.get("ok"):
            result = stage_and_cleanup(
                stage_update, base_dir, got, staging_dir, mode="full",
                current_version=current_version, selected=selected,
                target_manifest=target_manifest, target_version=target_version,
                cleanup_download=cleanup_download)
    _finish_version_download(state, base, mode, staging_dir, result, publish,
                             download_installer_fallback, installer)
