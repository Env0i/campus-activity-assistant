"""手机通道的生命周期与桌面入口。副作用通过组合根注入。"""
from __future__ import annotations

import threading

from application.phone_access_session import PhoneAccessService as PhoneAccessService
from domain import retry_rules



class PhoneAccessController:
    def __init__(self, *, lock, coordination, coordination_lock, service, ports):
        self._lock = lock
        self._coordination = coordination
        self._coord_lock = coordination_lock
        self._service = service
        self._ports = ports
        self.channel = ""
        self.exit_notice = None
        self.starting = False

    def raw_state(self):
        with self._coord_lock:
            activities = [dict(item) for item in self._ports["activities"]().values()]
            plan = self._ports["plan"]()
            last_plan = self._ports["last_plan"]()
            busy = self._ports["busy"]()
            error = self._ports["list_error"]()
            pc_list_error = dict(error) if error else None
        snapshot = None
        if plan is not None:
            try:
                snapshot = plan.snapshot()
            except Exception:
                snapshot = None
        if snapshot is None:
            snapshot = last_plan
        if isinstance(snapshot, dict):
            snapshot = dict(snapshot)
            snapshot.setdefault("source", self._ports["plan_source"](snapshot.get("plan_id")))
        login = self._ports["login_state"]()
        with self._coord_lock:
            last_check = dict(self._ports["last_check"]())
        login.update(self._ports["last_check_fields"](last_check))
        if login.get("last_check_state") == "expired":
            try:
                login["recovering"] = bool(self._ports["relogin_state"]()[0])
            except Exception:  # noqa: BLE001 - 恢复状态不可用时如实保留失效提示
                login["recovering"] = False
        prefs = self._ports["load_prefs"]()
        retry_pref = prefs.get("retry_policy") if isinstance(prefs, dict) else None
        retry_pref = retry_pref if isinstance(retry_pref, dict) else {}
        retry_policy = {
            "retry_for_s": retry_rules.policy_int(retry_pref.get("retry_for_s"), 120,
                                                   minimum=retry_rules.ADAPTIVE_RETRY),
            "max_attempts": retry_rules.policy_int(retry_pref.get("max_attempts"), 0),
        }
        return {"activities": activities, "login": login, "plan": snapshot, "busy": busy,
                "business_clock": self._ports["clock_payload"](),
                "retry_options": self._ports["retry_options"](), "retry_policy": retry_policy,
                "terms": self._ports["terms"](self._ports["load_prefs"]()),
                "terms_ok": self._ports["terms_gate"]() is None,
                "relogin_setup": self._ports["relogin_setup"](),
                "login_relay": self._ports["relay_view"](), "pc_list_error": pc_list_error}

    def relogin_setup(self):
        saved = self._ports["credentials_saved"]()
        hint = ""
        if saved:
            try:
                hint = self._ports["mask_account"](self._ports["stored_username"]())
            except Exception:
                saved = False
        try:
            ocr = bool(self._ports["ocr_ready"]())
        except Exception:
            ocr = False
        return {"saved": saved, "account_hint": hint, "ocr_ready": ocr,
                "paused": bool(saved and self._ports["credentials_bad"]())}

    def status_snapshot(self):
        status = self._ports["tunnel"]().status()
        if status.get("state") == "exited":
            self.exit_notice = dict(status)
        return status, dict(self.exit_notice or {})

    def reconcile(self):
        _, notice = self._ports["status_snapshot"]()
        if not notice:
            return {}
        with self._lock:
            if self.channel != "cloudflare":
                return {}
            if self._service().is_running():
                self._ports["stop_locked"]()
            self.channel = ""
            self._ports["log"]("Cloudflare 隧道已退出：手机访问随之停止，手机需要重新开启并重新配对")
            self._ports["emit"]("log", "Cloudflare 临时通道已失效，请重新开启手机访问")
        return dict(notice)

    def snapshot(self):
        self._ports["reconcile"]()
        service = self._service()
        prefs = self._ports["load_prefs"]()
        feature = self._ports["feature_state"](prefs)
        address = service.address()
        prefs_info = self._ports["phone_prefs"](prefs)
        code_info = service.pair_code_status()
        advanced = self._ports["advanced"]()
        return {"ok": True, "feature": feature, "features": {"phone_control": dict(feature)},
                "channels": dict(advanced.get("channels") or {}), "active_channel": self.channel,
                "running": service.is_running(), "channel": self.channel, "address": address,
                "qr": self._ports["qr"](address), "pair_code": code_info["code"],
                "pair_code_status": code_info, "paired_count": service.paired_count(),
                "live_session": bool(service.is_running() and service.has_live_session()),
                **service.link_status(), "supported": bool(feature.get("ready")),
                "preferred_channel": prefs_info["preferred_channel"],
                "tailscale_autostart": prefs_info["tailscale_autostart"],
                "advanced": self._ports["advanced"]()}

    def start(self, channel="tailscale"):
        with self._lock:
            return self._ports["start_locked"](channel)

    def start_locked(self, channel):
        prefs = self._ports["load_prefs"]()
        if not self._ports["feature_ready"](prefs):
            return {"ok": False, "error": "feature_required", "text": "请先在帮助里的高级功能安装手机控制。"}
        selected = str(channel or "tailscale").strip().lower()
        if selected in {"127.0.0.1", "localhost"}:
            selected = "local"
        if selected not in {"tailscale", "cloudflare", "local"}:
            return {"ok": False, "error": "bad_channel", "text": "请选择远程通道"}
        with self._coord_lock:
            if self._coordination.closing or self._coordination.advanced_busy:
                return {"ok": False, "text": "程序正在关闭，手机访问没有开启"}
        service = self._service()
        if service.is_running() and self.channel and selected != self.channel:
            return {"ok": False, "error": "other_channel_running", "text": "现在开着的是另一条通道，请先关闭再切换。"}
        if selected == "cloudflare" and self.starting:
            return {"ok": False, "error": "cloudflare_starting", "text": "Cloudflare 隧道正在启动，请稍等几秒。"}
        target = public_host = "127.0.0.1"
        if selected == "tailscale":
            endpoint = self._ports["tailscale"]()
            if not endpoint.get("available"):
                return {"ok": False, "error": endpoint.get("error", "tailscale_unavailable"),
                        "text": endpoint.get("text", "请先登录 Tailscale")}
            target = str(endpoint.get("bind_host") or "")
            public_host = str(endpoint.get("public_host") or target)
        if selected == "cloudflare":
            verified = self._ports["resolve_tunnel"]()
            self._ports["tunnel"]().executable = verified
            if not verified:
                return {"ok": False, "error": "cloudflared_missing",
                        "text": "没有找到通过校验的 cloudflared，Cloudflare 通道暂时不可用。"}
        return self._start_service(service, selected, target, public_host)

    def _start_service(self, service, selected, target, public_host):
        result = service.start(target, public_host=public_host, persistent_device=(selected == "tailscale"))
        if not result.get("ok"):
            return result
        self.channel = selected
        if selected == "cloudflare":
            self.starting = True
            try:
                tunnel = self._ports["tunnel"]().start(service.address())
            finally:
                self.starting = False
            if not tunnel.get("ok"):
                service.stop()
                self.channel = ""
                return tunnel
            public_url = str(tunnel.get("url") or "")
            public_host = public_url.split("//", 1)[-1].split("/", 1)[0]
            service.set_public_url(public_url)
            self.exit_notice = None
        self._ports["log"]("开启手机访问：通道=%s 监听=%s 公网=%s 设备信任=%s" % (
            selected, target, public_host, "开" if result.get("persistent_device") else "关"))
        self._ports["emit"]("log", "手机访问已开启：%s" % result.get("address", ""))
        self._ports["remember"](selected)
        return dict(result, channel=selected, address=service.address())

    def remember(self, channel):
        block = {"preferred_channel": str(channel), "tailscale_autostart": str(channel) == "tailscale"}
        if not self._ports["save_phone_prefs"](block):
            self._ports["emit"]("log", "通道选择没有写进偏好；本次照常可用，下次需要重新选。")

    def forget_autostart(self):
        current = self._ports["phone_prefs"](self._ports["load_prefs"]())
        self._ports["save_phone_prefs"]({"preferred_channel": current["preferred_channel"],
                                         "tailscale_autostart": False})

    def set_preferences(self, preferred_channel=""):
        channel = str(preferred_channel or "").strip().lower()
        if channel and channel not in {"tailscale", "cloudflare"}:
            return {"ok": False, "error": "bad_channel", "text": "请选择远程通道"}
        current = self._ports["phone_prefs"](self._ports["load_prefs"]())
        chosen = channel or current["preferred_channel"]
        block = {"preferred_channel": chosen, "tailscale_autostart": chosen == "tailscale"}
        if not self._ports["save_phone_prefs"](block):
            return {"ok": False, "error": "prefs_busy", "text": "通道选择没有保存，请重试。"}
        return {"ok": True, **block}

    def restore(self):
        current = self._ports["phone_prefs"](self._ports["load_prefs"]())
        if current["preferred_channel"] != "tailscale" or not current["tailscale_autostart"]:
            return {"ok": False, "error": "not_configured",
                    "text": "上次没有用 Tailscale 开启手机访问，本次不自动恢复。"}
        with self._coord_lock:
            if self._coordination.closing:
                return {"ok": False, "text": "程序正在关闭，手机访问没有恢复"}
        service = self._service()
        if service.is_running():
            return {"ok": True, "running": True, "channel": self.channel, "address": service.address()}
        endpoint = self._ports["tailscale"]()
        if not endpoint.get("available"):
            return {"ok": False, "error": endpoint.get("error", "tailscale_unavailable"),
                    "state": endpoint.get("state", ""), "text": endpoint.get("text", "Tailscale 现在不可用")}
        return dict(self._ports["start"]("tailscale"), restored=True)

    def schedule_restore(self, window):
        def run():
            try:
                event = getattr(getattr(window, "events", None), "loaded", None)
                if event is not None:
                    event.wait(15)
            except Exception:
                pass
            try:
                result = self._ports["restore"]()
            except Exception as exc:
                self._ports["emit"]("log", "手机访问没有恢复：%s" % type(exc).__name__)
                return
            if result.get("ok") and result.get("address"):
                self._ports["emit"]("log", "已恢复手机访问：%s" % result["address"])
        threading.Thread(target=run, name="phone-restore", daemon=True).start()
        self._ports["component_auto_update"](window)

    def stop(self):
        with self._lock:
            result = self._ports["stop_locked"]()
        self.exit_notice = None
        return result

    def stop_locked(self):
        self._ports["cancel_relogin"]()
        tunnel_stopped = self._ports["stop_tunnel"]()
        result = self._service().stop(revoke_devices=True)
        self._ports["log"]("关闭手机访问：通道=%s，已撤销会话与设备信任" % (self.channel or "-"))
        self.channel = ""
        self._ports["forget"]()
        if not tunnel_stopped:
            text = "手机入口已停止，但 Cloudflare 隧道没能关闭，请重试关闭。"
            self._ports["emit"]("log", text)
            return {"ok": False, "error": "tunnel_stop_failed", "text": text}
        self._ports["emit"]("log", "手机访问已关闭")
        return result


class PhoneFields:
    @property
    def _phone_channel(self): return self._phone_controller.channel
    @_phone_channel.setter
    def _phone_channel(self, value): self._phone_controller.channel = value
    @property
    def _cloudflare_exit_notice(self): return self._phone_controller.exit_notice
    @_cloudflare_exit_notice.setter
    def _cloudflare_exit_notice(self, value): self._phone_controller.exit_notice = value
    @property
    def _cloudflare_starting(self): return self._phone_controller.starting
    @_cloudflare_starting.setter
    def _cloudflare_starting(self, value): self._phone_controller.starting = value
