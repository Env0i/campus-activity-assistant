# -*- coding: utf-8 -*-
"""高级组件操作：编排由组合根提供的组件、手机和登录端口。"""
from __future__ import annotations

from pathlib import Path
import threading
import time
from application.components import component_projection


class ComponentActions:
    def __init__(self, *, allowed, phone_key, inspect_executable, inspect_archive,
                 selected_dir, package_error, open_directory, credential_lock,
                 coordination, coordination_lock, load_prefs, feature_state, save_prefs, ocr_key,
                 reset_login, window, select_file, phone_lock, service_for,
                 frozen, busy, finished, emit, title, phone, login, component,
                 failure_reasons, log, demo, auto_update, download, wait_idle):
        self._allowed = allowed
        self._phone_key = phone_key
        self._inspect_executable = inspect_executable
        self._inspect_archive = inspect_archive
        self._selected_dir = selected_dir
        self._package_error = package_error
        self._open_directory = open_directory
        self._credential_lock = credential_lock
        self._coordination = coordination
        self._lock = coordination_lock
        self._load_prefs = load_prefs
        self._feature_state = feature_state
        self._save_prefs = save_prefs
        self._ocr_key = ocr_key
        self._reset_login = reset_login
        self._window = window
        self._select_file = select_file
        self._phone_lock = phone_lock
        self._service_for = service_for
        self._frozen = frozen
        self._busy = busy
        self._finished = finished
        self._emit = emit
        self._title = title
        self._phone = phone
        self._login = login
        self._component = component
        self._failure_reasons = failure_reasons
        self._log = log
        self._demo = demo
        self._auto_update = auto_update
        self._download = download
        self._wait_idle = wait_idle

    def schedule_auto_update(self, window) -> None:
        if self._demo() or not self._frozen():
            return

        def run() -> None:
            try:
                event = getattr(getattr(window, "events", None), "loaded", None)
                if event is not None:
                    event.wait(15)
            except Exception:
                pass
            try:
                self._auto_update(frozen=self._frozen(), demo=self._demo(), prefs=self._load_prefs(),
                                  state_of=self._component["frozen_feature_state"], download=self._download,
                                  wait_idle=self._wait_idle, log=lambda text: self._emit("log", text))
            except Exception as exc:
                self._emit("log", "组件自动更新没有完成：%s" % type(exc).__name__)

        threading.Thread(target=run, name="component-auto-update", daemon=True).start()

    def wait_settled(self, key: str, *, timeout: float = 1800.0) -> str:
        service = self._service_for(str(key))
        if service is None:
            return ""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._coordination.closing:
                    return ""
            try:
                state = str(service.snapshot().get("state") or "")
            except Exception:
                return ""
            if state not in ("downloading", "verifying", "removing"):
                return state
            time.sleep(0.5)
        return ""

    def replace_downloaded(self, key, payload, *, root=None, group=False):
        with self._credential_lock:
            with self._phone_lock:
                with self._lock:
                    if self._coordination.closing:
                        raise RuntimeError("application_closing")
                if not self._phone["stop_tunnel"]():
                    raise self._package_error("component_in_use")
                self._phone["shutdown"]()
                self._phone["clear_channel"]()
                action = self._component["commit"] if group else self._component["install"]
                return action(payload, key, root=root) if not group else action(key, payload, root=root)

    def replace_downloaded_ocr(self, key, payload, *, root=None, group=False):
        with self._credential_lock:
            with self._lock:
                if self._coordination.closing:
                    raise RuntimeError("application_closing")
            self._login["cancel_auto"]()
            self._reset_login()
            action = self._component["commit"] if group else self._component["install"]
            return action(payload, key, root=root) if not group else action(key, payload, root=root)

    def finished(self, key: str = "") -> None:
        with self._lock:
            self._coordination.advanced_busy = False
        if not key:
            return
        service = self._service_for(key)
        try:
            snap = service.snapshot()
        except Exception:
            return
        if str(snap.get("state")) != "failed":
            return
        text = self._failure_reasons.get(str(snap.get("error_code") or ""))
        text = text or str(snap.get("text") or "")
        if text:
            self._emit("log", "下载没有完成：" + text + ("" if text[-1] in "。！？" else "。"))

    def installed(self, key: str, version: str) -> None:
        enabled = dict(self._load_prefs().get("advanced_features") or {})
        enabled[key] = True
        if not self._save_prefs({"advanced_features": enabled}):
            self._log(("验证码识别组件" if key == self._ocr_key else "组件") + "已安装，但启用状态没有保存成功")
        if key == self._phone_key:
            self._phone["refresh_executable"]()
        self._emit("log", "%s组件已安装（%s）。" % ("验证码识别" if key == self._ocr_key else "手机控制", version or "版本未知"))

    def snapshot(self) -> dict:
        prefs = self._load_prefs()
        downloads = {}
        for key in (self._phone_key, self._ocr_key):
            service = self._service_for(key)
            try:
                downloads[key] = service.snapshot() if service is not None else {}
            except Exception:
                downloads[key] = {}
        cloudflare_status, cloudflare_exit = self._phone["status"]()
        saved = self._login["has_credentials"]()
        username = ""
        if saved:
            try:
                username = self._login["username"]()
            except Exception:
                saved = False
        return component_projection.advanced_features_state(
            features=self._feature_state(prefs), advanced_busy=self._coordination.advanced_busy,
            downloads=downloads, tailscale=self._phone["tailscale"](),
            cloudflare_status=cloudflare_status, cloudflare_exit=cloudflare_exit,
            cloudflare_executable=self._phone["executable"](),
            phone_access=self._phone["preferences"](prefs),
            credential={"store_available": self._login["available"](), "saved": saved,
                        "username": username, "ocr_ready": self._login["ocr_ready"](prefs),
                        "automatic": self._login["automatic"](),
                        "staged": self._login["staged"](), "staged_hint": self._login["staged_hint"](),
                        "last_origin": self._login["last_origin"](),
                        "paused": saved and self._login["is_bad"]()})

    def download(self, key: str = "") -> dict:
        chosen = str(key or self._phone_key)
        service = self._service_for(chosen)
        if service is None:
            return {"ok": False, "error": "bad_feature", "text": "这个功能没有可在线下载的组件包。"}
        if not self._frozen():
            return {"ok": False, "error": "source_build",
                    "text": "源码版用的是已装好的 Python 依赖，不需要组件包。"}
        with self._phone_lock:
            with self._lock:
                if self._coordination.closing or self._coordination.advanced_busy or self._busy():
                    return {"ok": False, "error": "busy", "text": "请等待当前操作结束。"}
                self._coordination.advanced_busy = True
            try:
                result = service.start()
            except Exception:
                self._finished()
                raise
            if not result.get("ok"):
                self._finished()
        if result.get("ok"):
            self._emit("log", "开始下载%s组件包。" % self._title(chosen))
        return result

    def cancel_download(self, key: str = "") -> dict:
        service = self._service_for(str(key or self._phone_key))
        if service is None:
            return {"ok": False, "error": "bad_feature", "text": "未知高级功能"}
        return service.cancel()

    def service_for(self, key: str):
        if key == self._phone_key:
            return self._component["phone_service"]()
        if key == self._ocr_key:
            return self._component["ocr_service"]()
        return None

    def install(self, key: str = "", path: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "text": "未知高级功能"}
        chosen = str(path or "").strip().strip('"')
        if chosen:
            inspected = self._component["inspect"](key, chosen)
            if not inspected.get("ok"):
                return {"ok": False, "error": str(inspected.get("kind") or "inspect_failed"),
                        "text": str(inspected.get("text") or "这个文件不能用。")}
        with self._lock:
            if self._coordination.closing or self._coordination.advanced_busy or self._busy():
                return {"ok": False, "text": "请等待当前操作结束后再安装。"}
            self._coordination.advanced_busy = True
        try:
            if chosen and str(inspected.get("kind")) == "cloudflared":
                return self._install_cloudflared(key, chosen)
            return self._component["install_selected"](key, chosen)
        finally:
            with self._lock:
                self._coordination.advanced_busy = False

    def _install_cloudflared(self, key: str, chosen: str) -> dict:
        with self._credential_lock, self._phone_lock:
            if key == self._phone_key and self._phone["running"]():
                self._phone["stop_locked"]()
            try:
                result = self._component["install_cloudflared"](chosen)
            except self._package_error as exc:
                code = str(exc.args[0] if exc.args else "install_failed")
                return {"ok": False, "error": code, "text": "这份 cloudflared 没有通过校验：%s" % code}
            enabled = dict(self._load_prefs().get("advanced_features") or {})
            enabled[str(key)] = True
            if not self._save_prefs({"advanced_features": enabled}):
                return {"ok": False, "error": "prefs_busy",
                        "text": "cloudflared 已收好，但启用状态暂未保存；重新打开帮助再试。"}
            self._phone["refresh_executable"]()
            return result

    def install_selected(self, key: str, chosen: str = "") -> dict:
        frozen = self._frozen()
        archive = chosen or None
        if archive is None and frozen:
            if self._window() is None:
                return {"ok": False, "text": "请在电脑窗口中导入组件。"}
            selected = self._select_file(("组件包 (*.zip)",))
            if not selected:
                return {"ok": True, "canceled": True, "text": "已取消导入。"}
            archive = str(selected[0])
        if archive and not frozen:
            return {"ok": False, "error": "source_build",
                    "text": "源码版用的是已装好的 Python 依赖，组件包对它不起作用；"
                            "手机访问用的 cloudflared 源码版也不会从 PATH 里找，请改用发布版导入组件包。"}
        with self._credential_lock, self._phone_lock:
            with self._lock:
                if self._coordination.closing:
                    return {"ok": False, "text": "程序正在关闭。"}
            if key == self._phone_key and self._phone["running"]():
                self._phone["stop_locked"]()
            if key == self._ocr_key:
                self._login["cancel_auto"]()
                self._reset_login()
            result = self._component["install_feature"](key, frozen, archive)
            if not result.get("ok"):
                return result
            enabled = dict(self._load_prefs().get("advanced_features") or {})
            enabled[str(key)] = True
            if not self._save_prefs({"advanced_features": enabled}):
                return {"ok": False, "error": "prefs_busy",
                        "text": "组件已安装，但启用状态暂未保存；重新打开帮助再试。"}
            self._phone["refresh_executable"]()
            return result

    def remove(self, key: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "text": "未知高级功能"}
        with self._credential_lock, self._phone_lock:
            with self._lock:
                if self._coordination.closing or self._coordination.advanced_busy:
                    return {"ok": False, "text": "请等待当前操作结束。"}
                self._coordination.advanced_busy = True
            try:
                if key == self._phone_key:
                    self._phone["stop_locked"]()
                else:
                    self._login["cancel_auto"]()
                    self._login["clear_staged"]()
                    self._reset_login()
                enabled = dict(self._load_prefs().get("advanced_features") or {})
                enabled[key] = False
                if not self._save_prefs({"advanced_features": enabled}):
                    return {"ok": False, "text": "停用状态未保存，请重试。"}
                if self._frozen():
                    if key == self._phone_key:
                        removed = self._service_for(key).remove()
                        if not removed.get("ok"):
                            return {"ok": False, "text": str(removed.get("text") or "组件文件未能移除，请关闭后重试。")}
                    else:
                        self._component["remove"](key)
                self._phone["refresh_executable"]()
                return {"ok": True, "text": "功能已移除；已保存的账号可另行清除。"}
            except (OSError, ValueError):
                return {"ok": False, "text": "功能已停用，组件文件未能移除，请关闭后重试。"}
            finally:
                with self._lock:
                    self._coordination.advanced_busy = False

    def pick(self, key: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "text": "未知高级功能"}
        if self._window() is None:
            return {"ok": False, "text": "请在电脑窗口里选择文件。"}
        try:
            selected = self._select_file(("组件包 (*.zip)",))
        except Exception:  # noqa: BLE001 - 系统对话框不可用时保留界面
            return {"ok": False, "error": "dialog_unavailable",
                    "text": "打不开系统的文件选择框。请关掉设置后重新打开再试；仍不行，就到发布页下载组件包，再点「导入已下载的组件包」。"}
        if not selected:
            return {"ok": True, "canceled": True, "text": "已取消选择。"}
        return {"ok": True, "path": str(selected[0])}

    def enable(self, key: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "reason": "bad_feature", "error": "bad_feature",
                    "text": "未知高级功能"}
        with self._credential_lock:
            with self._lock:
                if self._coordination.closing:
                    return {"ok": False, "reason": "closing", "error": "closing",
                            "text": "程序正在关闭。"}
            prefs = self._load_prefs()
            if not self._feature_state(prefs).get(key, {}).get("available"):
                return {"ok": False, "reason": "not_available", "error": "not_available",
                        "text": "这个组件还没装好，不能启用。"}
            enabled = dict(prefs.get("advanced_features") or {})
            enabled[str(key)] = True
            if not self._save_prefs({"advanced_features": enabled}):
                return {"ok": False, "reason": "prefs_busy", "error": "prefs_busy",
                        "text": "启用状态没有保存，请重试。"}
            if key == self._ocr_key:
                self._reset_login()
            return {"ok": True, "feature": str(key), "enabled": True}

    def inspect(self, key: str = "", path: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "kind": "unknown_feature", "text": "未知高级功能"}
        chosen = str(path or "").strip().strip('"')
        if not chosen:
            return {"ok": False, "kind": "empty", "text": "还没有选择文件。"}
        if Path(chosen).suffix.lower() == ".exe":
            if key != self._phone_key:
                return {"ok": False, "kind": "not_zip", "text": "这里需要组件包 ZIP，不是可执行文件。"}
            return self._inspect_executable(chosen)
        return self._inspect_archive(chosen, key)

    def location(self, key: str = "") -> dict:
        if not self._allowed(key):
            return {"ok": False, "error": "bad_feature", "text": "未知高级功能"}
        try:
            directory = self._selected_dir(key)
        except (self._package_error, OSError, ValueError):
            return {"ok": False, "error": "location_unavailable", "text": "读不到组件的安装位置。"}
        parts = directory.parts
        short = "…\\" + "\\".join(parts[-2:]) if len(parts) > 2 else str(directory)
        return {"ok": True, "path": str(directory), "short": short,
                "exists": directory.is_dir()}

    def open_location(self, key: str = "") -> dict:
        located = self.location(key)
        if not located.get("ok"):
            return located
        directory = Path(located["path"])
        target = directory if directory.is_dir() else directory.parent
        if not target.is_dir():
            return {"ok": False, "error": "not_found", "text": "组件文件夹还不存在。"}
        try:
            self._open_directory(str(target))
        except OSError as exc:
            return {"ok": False, "error": "open_failed",
                    "text": "没能打开文件夹（%s）。" % type(exc).__name__}
        return {"ok": True, "opened": "component" if target == directory else "parent"}
