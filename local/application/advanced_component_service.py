# -*- coding: utf-8 -*-
"""用户主动触发的组件包下载与安装事务（手机控制、验证码识别各一份实例）。

状态机（每个组件一份，互不影响）：

    available → downloading → verifying → installed
    available/downloading → cancelled（不改动现有组件）
    任意阶段 → failed（清理暂存，旧组件保持可用）
    installed → removing → missing

字节级下载与 Release 元数据解析都由 composition root（`local/app.py`）注入：
下载复用 `updater.download_installer`（HTTPS、大小上限、`.part` 半成品、实时
SHA-256、取消即清理都在那儿），元数据解析用 `update_check`。本模块不直接
import 任何网络/进程模块（分层边界契约），只做它之上的编排：
取元数据 → 下载 → 用装机同一套规则校验 → 原子安装 → 失败回滚。

规矩：下载只能由用户动作触发，不后台下载、不自动升级；不新增任何代理配置。
@author Author
"""
from __future__ import annotations

import json
import socket
import threading
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError

from infrastructure import component_packages as _packages

FEATURE = "phone_control"
# 校验失败时说「这是别的组件的包，不是 XX」用的名字
_TITLES = {"phone_control": "手机控制", "relogin_ocr": "验证码识别"}
# 每 1 MiB 至少发一次进度：界面靠这个数字动，不是靠每块都重画
PROGRESS_STEP_BYTES = 1024 * 1024

_STATE_TEXT = {
    "available": "可以下载组件包（约 %s）。",
    "downloading": "正在下载组件包…",
    "verifying": "正在校验组件包…",
    "installed": "组件包已安装（版本 %s）。",
    "cancelled": "已取消下载，现有组件没有被改动。",
    "failed": "下载或安装没有成功。",
    "removing": "正在移除组件包…",
    "missing": "组件包未安装。",
}


class AdvancedComponentService:
    """单个组件包的下载/校验/安装事务（单飞，可取消，可重试）。"""

    def __init__(self, *, download, asset_resolver, root=None, version=None,
                 inspect=None, install=None, status=None,
                  remover=None, inspect_artifact=None, find_cached_artifact=None,
                  cache_artifact=None, commit_artifact_group=None,
                  on_installed=None, on_finished=None, log=None,
                 feature=FEATURE):
        if feature not in _TITLES:
            raise ValueError("unknown component feature")
        self._feature = feature
        self._root = root
        self._version = version or _packages.version
        self._asset_resolver = asset_resolver
        self._download = download
        self._inspect = inspect or _packages.inspect_archive
        self._install = install or _packages.install
        self._inspect_artifact = inspect_artifact or _packages.inspect_artifact
        self._find_cached_artifact = find_cached_artifact or _packages.find_cached_artifact
        self._cache_artifact = cache_artifact or _packages.cache_artifact
        self._commit_artifact_group = commit_artifact_group or _packages.commit_artifact_group
        self._status = status or _packages.feature_status
        self._remover = remover or _packages.remove
        self._on_installed = on_installed
        self._on_finished = on_finished
        self._log = log
        self._lock = threading.RLock()
        self._thread = None
        self._active = False
        self._installing = False
        self._closed = False
        self._cancel_flag = False
        self._installed = False
        self._version_text = ""
        self._state = "missing"
        self._error_code = ""
        self._text = ""
        self._downloaded = 0
        self._total = 0
        self._request_id = ""
        self._refresh_idle_state()

    # ---------- 快照与状态 ------------------------------------------------
    def _refresh_idle_state(self) -> None:
        """空闲态直接从装机目录读：装没装以磁盘为准，不靠内存记忆。"""
        try:
            info = self._status(self._feature, root=self._root) or {}
        except Exception:
            info = {}
        available = bool(info.get("available"))
        self._installed = available
        if available:
            self._state = "installed"
            self._version_text = str(info.get("version") or self._version() or "")
        elif self._state not in ("downloading", "verifying", "removing"):
            self._state = "available"

    def _set(self, **fields) -> None:
        with self._lock:
            for name, value in fields.items():
                setattr(self, "_" + name, value)

    def snapshot(self) -> dict:
        with self._lock:
            if not self._active and self._state in ("available", "installed", "missing"):
                self._refresh_idle_state()
            state = self._state
            return {
                "state": state,
                "request_id": self._request_id,
                "text": self._render_text(state),
                "downloaded": self._downloaded,
                "total_bytes": self._total,
                "error_code": self._error_code,
                "version": self._version_text,
            }

    def _render_text(self, state: str) -> str:
        template = _STATE_TEXT.get(state, "")
        if state == "available":
            total = int(self._total or 0)
            return template % ("%.1f MB" % (total / 1024.0 / 1024.0)) if total else (
                "可以下载组件包。")
        if state == "installed":
            return template % (self._version_text or "未知") if self._version_text else (
                "组件包已安装。")
        if state in ("downloading", "failed"):
            if self._text:
                return self._text
            if state == "downloading" and self._total:
                percent = min(99, int(self._downloaded * 100 / self._total))
                return "%s %d%%" % (template, percent)
        return template

    # ---------- 用户动作 --------------------------------------------------
    def start(self) -> dict:
        """开始下载（单飞）。再次点击在下载期间一律返回 busy。"""
        with self._lock:
            if self._closed or self._active:
                return {"ok": False, "error": "busy",
                        "text": "已经在下载组件包了，请等它结束。"}
            self._state = "downloading"
            self._error_code = ""
            self._text = ""
            self._downloaded = 0
            self._total = 0
            self._cancel_flag = False
            self._active = True
            self._installing = False
            self._request_id = uuid.uuid4().hex[:12]
            thread = threading.Thread(target=self._run, name="advanced-component",
                                      daemon=True)
            self._thread = thread
            request_id = self._request_id
            try:
                thread.start()
            except Exception:
                self._active = False
                self._thread = None
                raise
        return {"ok": True, "state": "downloading", "request_id": request_id}

    def cancel(self) -> dict:
        """取消：只置标记，真正的半成品清理在下载循环的 finally 里。"""
        with self._lock:
            if self._installing:
                return {"ok": False, "error": "install_committing",
                        "text": "组件正在安装，请等待安装结束。"}
            running = self._active and self._state != "removing"
            self._cancel_flag = True
            if not running:
                return {"ok": True, "state": self._state, "text": "当前没有正在进行的下载。"}
        return {"ok": True, "state": "cancelled", "text": "正在取消下载…"}

    def shutdown(self) -> None:
        """关闭前取消尚未提交的安装，并等已进入替换阶段的事务收尾。"""
        with self._lock:
            self._closed = True
            self._cancel_flag = True
            thread = self._thread
            installing = self._installing
        if thread is not None and thread is not threading.current_thread():
            # 网络阶段只操作暂存且已被禁止进入安装；慢网不能拖住其他退出收尾。
            # 提交阶段只做本地校验/换位，必须等回滚或安装完成后才能退出。
            thread.join(timeout=None if installing else 2)

    def remove(self) -> dict:
        """移除已安装组件（调用方负责先把手机访问停掉）。"""
        with self._lock:
            if self._closed or self._active:
                return {"ok": False, "error": "busy",
                        "text": "正在下载，结束后再移除。"}
            self._state = "removing"
            self._active = True
            self._error_code = ""
            self._text = ""
        try:
            self._remover(self._feature, root=self._root)
        except Exception as exc:
            with self._lock:
                self._state = "installed" if self._installed else "failed"
                self._error_code = "remove_failed"
                self._text = "组件文件没有移除干净（%s），请关闭程序后重试。" % type(exc).__name__
            return {"ok": False, "error": "remove_failed", "text": self._text}
        finally:
            with self._lock:
                if not self._error_code:
                    self._installed = False
                    self._version_text = ""
                    self._state = "missing"
                    self._text = ""
                self._active = False
        return {"ok": True, "state": "missing", "text": "组件包已移除。"}

    # ---------- 下载 → 校验 → 安装 ---------------------------------------
    def _run(self) -> None:
        archive = ""
        try:
            resolved = self._resolve_asset()
            if self._cancelled():
                return
            if not resolved.get("ok"):
                self._fail(str(resolved.get("error") or "no_component"),
                           str(resolved.get("text") or "这个版本没有发布组件包。"))
                return
            if isinstance(resolved.get("assets"), list):
                try:
                    if self._run_split_assets(resolved["assets"]):
                        return
                except Exception as exc:
                    self._fail("artifact_install_failed",
                               "拆分组件准备失败（%s），当前组件仍保留。" % type(exc).__name__)
                if self._cancelled() or not isinstance(resolved.get("asset"), dict):
                    return
                # 拆分组尚未提交，旧组继续可用；完整单体包仍须单独校验再安装。
                self._set(state="downloading", text="", error_code="")
            asset = resolved["asset"]
            self._set(total=int(asset.get("bytes") or 0))
            last_progress = [0]

            def progress(done, total):
                if done - last_progress[0] < PROGRESS_STEP_BYTES and done < total:
                    return
                last_progress[0] = done
                self._set(downloaded=int(done), total=int(total or 0))

            got = self._download(
                asset["url"], name=asset["name"], expect_bytes=asset["bytes"],
                expect_sha256=asset["sha256"], root=self._root,
                progress=progress, cancel=lambda: self._cancel_flag)
            if not got.get("ok"):
                code = str(got.get("error_code") or "download_failed")
                if code == "cancelled":
                    self._set(state="cancelled", text="", error_code="")
                else:
                    self._fail(code, str(got.get("text") or "下载失败。"))
                return
            archive = str(got.get("path") or "")
            if self._cancelled():
                return
            self._set(state="verifying", text="正在校验组件包…")
            problem = self._verify(archive)
            if problem:
                self._fail(problem[0], problem[1])
                return
            info = self._inspect(archive, self._feature)
            # 与 cancel 共用锁确定提交点：此前取消不动旧包，此后明确拒绝取消。
            with self._lock:
                if self._cancel_flag:
                    self._state = "cancelled"
                    self._text = ""
                    return
                self._installing = True
            self._install(archive, self._feature, root=self._root)
            version = str((info or {}).get("version") or "")
            with self._lock:
                self._state = "installed"
                self._installed = True
                self._version_text = version
                self._error_code = ""
                self._text = ""
            if self._on_installed is not None:
                try:
                    self._on_installed(version)
                except Exception as exc:      # 偏好没写成不影响「已装好」这件事
                    self._note("组件已安装，但启用状态没保存：%s" % type(exc).__name__)
        except Exception as exc:
            self._fail("unexpected", "下载或安装出现意外（%s），请重试。" % type(exc).__name__)
        finally:
            if archive:
                self._cleanup(archive)
            if self._on_finished is not None:
                try:
                    self._on_finished()
                except Exception:
                    pass
            with self._lock:
                self._installing = False
                self._active = False

    def _run_split_assets(self, assets) -> bool:
        """先复用或准备全部不可变资产，最后一次切换完整功能组。"""
        required = {key for key, spec in _packages.ARTIFACTS.items()
                    if spec["feature"] == self._feature}
        if (not assets or any(not isinstance(asset, dict) for asset in assets)
                or {asset.get("artifact_id") for asset in assets} != required
                or len(assets) != len(required)):
            self._fail("bad_artifact", "拆分组件资产组不完整。")
            return False
        prepared = {}
        missing = []
        for asset in assets:
            cached = self._find_cached_artifact(asset, root=self._root)
            if cached is None:
                missing.append(asset)
            else:
                prepared[asset["artifact_id"]] = cached
        total = sum(int(asset.get("bytes") or 0) for asset in missing)
        self._set(total=total, downloaded=0)
        offset = 0
        for asset in missing:
            if self._cancelled():
                return False
            artifact_id = asset["artifact_id"]
            self._set(total=total, state="downloading", text="")
            last_progress = [offset]
            def progress(done, _expect):
                current = offset + int(done or 0)
                if current - last_progress[0] < PROGRESS_STEP_BYTES and current < offset + int(asset.get("bytes") or 0):
                    return
                last_progress[0] = current
                self._set(downloaded=current, total=total)
            got = self._download(
                asset["url"], name=asset["name"], expect_bytes=asset["bytes"],
                expect_sha256=asset["sha256"], root=self._root,
                progress=progress, cancel=lambda: self._cancel_flag)
            if not got.get("ok"):
                code = str(got.get("error_code") or "download_failed")
                if code == "cancelled":
                    self._set(state="cancelled", text="", error_code="")
                else:
                    self._fail(code, str(got.get("text") or "下载失败。"))
                return False
            archive = str(got.get("path") or "")
            try:
                self._set(state="verifying", text="正在校验组件资产…")
                info = self._inspect_artifact(archive, artifact_id)
                if not (isinstance(info, dict) and info.get("ok") is True):
                    self._fail(str((info or {}).get("kind") or "bad_artifact"),
                               str((info or {}).get("text") or "拆分组件资产不合规。"))
                    return False
                with self._lock:
                    if self._cancel_flag:
                        self._state = "cancelled"
                        self._text = ""
                        return False
                prepared[artifact_id] = self._cache_artifact(
                    archive, artifact_id, root=self._root,
                    expect_content_sha256=asset.get("content_sha256"))
            finally:
                self._cleanup(archive)
            offset += int(asset.get("bytes") or 0)
        # 与取消/关闭共用锁确定唯一提交点，网络阶段始终允许取消。
        with self._lock:
            if self._cancel_flag or self._closed:
                self._state = "cancelled"
                self._text = ""
                self._error_code = ""
                return False
            self._state = "verifying"
            self._installing = True
        try:
            committed = self._commit_artifact_group(
                self._feature, [prepared[asset["artifact_id"]] for asset in assets],
                root=self._root)
            if not committed.get("ok"):
                with self._lock:
                    self._installing = False
                self._fail("artifact_install_failed", "组件组未能切换，当前组件仍保留。")
                return False
        except Exception:
            with self._lock:
                self._installing = False
            raise
        runtime = prepared[self._feature + "_runtime"]
        with self._lock:
            self._state = "installed"
            self._installed = True
            self._version_text = str(runtime.get("version") or "")
            self._error_code = ""
            self._text = ""
        if self._on_installed is not None:
            try:
                self._on_installed(self._version_text)
            except Exception as exc:
                self._note("拆分组件已安装，但启用状态没保存：%s" % type(exc).__name__)
        return True

    def _cancelled(self) -> bool:
        with self._lock:
            if not self._cancel_flag:
                return False
            self._state = "cancelled"
            self._text = ""
            self._error_code = ""
            return True

    def _resolve_asset(self) -> dict:
        if self._asset_resolver is None:
            return {"ok": False, "error": "no_component",
                    "text": "这个版本没有发布组件包。"}
        return self._asset_resolver(self._version()) or {}

    def _verify(self, archive: str):
        """用装机同一套规则再核一遍；返回 (错误码, 文案) 或 None。"""
        if not archive:
            return ("download_failed", "没有拿到下载文件。")
        try:
            info = self._inspect(archive, self._feature)
        except Exception as exc:
            return ("bad_component", "组件包打不开（%s）。" % type(exc).__name__)
        if not (isinstance(info, dict) and info.get("ok") is True):
            text = (info or {}).get("text") if isinstance(info, dict) else ""
            return (str((info or {}).get("kind") or "bad_component"),
                    str(text or "组件包不合规。"))
        if str(info.get("feature") or "") != self._feature:
            return ("wrong_feature", "这是别的组件的包，不是%s。" % _TITLES[self._feature])
        declared = str(info.get("cloudflared") or "")
        # 只有手机控制内置 cloudflared；验证码识别包里出现这个字段同样按清单核一遍
        if declared and declared != _packages.CLOUDFLARED_VERSION:
            return ("cloudflared_version",
                    "组件包内置的 cloudflared 版本不对（%s），请重新下载。" % declared)
        return None

    def _fail(self, code: str, text: str) -> None:
        with self._lock:
            # 失败只改「这次事务」的结论：已装好的旧组件保持 installed 语义
            self._state = "failed"
            self._error_code = code
            self._text = text
        self._note("组件下载失败：%s" % code)

    def _cleanup(self, archive: str) -> None:
        try:
            path = Path(archive)
            if path.is_file():
                path.unlink()
            parent = path.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass

    def _note(self, message: str) -> None:
        if self._log is not None:
            try:
                self._log(message)
            except Exception:
                pass
