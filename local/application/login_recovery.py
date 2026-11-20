# -*- coding: utf-8 -*-
"""登录检查的单飞、补查与结果收尾；副作用由组合根注入。"""
from __future__ import annotations

import json
import threading
import time
import urllib.request

class LoginRecovery:
    def __init__(self, *, coordination, lock, ports):
        self._coordination = coordination
        self._lock = lock
        self._ports = ports
        self.last_check = {}
        self.check_again = False
        self.check_request_id = ""
        self.check_last = {"request_id": "", "payload": None}
        self.relay_proc_tree = None
        self.auto_relogin_started_at = None
        self.relay_creds_source = ""
        self.pending_save = None
        self.once_creds_rejected = False
        self.login_seen_valid = False
        self.expiry_pushed = False
        self.login_expired_logged = False

    def note_conclusion(self, conclusion):
        with self._lock:
            if conclusion == "valid":
                self.login_seen_valid = True
                self.expiry_pushed = False
                self.login_expired_logged = False
                return
            if conclusion != "expired":
                return
            push = bool(self.login_seen_valid and not self.expiry_pushed)
            if push:
                self.expiry_pushed = True
            first_expired = not self.login_expired_logged
            self.login_expired_logged = True
        if first_expired:
            try:
                silent, reason = self._ports["silent_state"]()
                self._ports["log_event"]("login_expired_detected",
                                         silent="true" if silent else "false", reason=reason or "none")
            except Exception:  # noqa: BLE001 - 日志不阻碍失效通知
                pass
        if push:
            self._ports["push_expired"]()

    def relay_finished(self):
        with self._lock:
            relay_tree = self.relay_proc_tree
            self.relay_proc_tree = None
            tree = None
            coord = self._coordination
            if relay_tree is not None and coord.proc_tree is relay_tree:
                tree = relay_tree
                coord.proc_tree = None
                if coord.proc is relay_tree.proc and coord.proc.poll() is not None:
                    coord.proc = None
            elif coord.proc is not None and coord.proc.poll() is not None:
                coord.proc = None
                tree = coord.proc_tree
                coord.proc_tree = None
            began = self.auto_relogin_started_at
        if tree is not None:
            tree.close()
        try:
            last = self._ports["relay_state"]()
        except Exception:
            last = {}
        state = str(last.get("state") or "")
        with self._lock:
            source = self.relay_creds_source
            if state != "success":
                self.pending_save = None
        if state == "failed" and last.get("safe_error") == "bad_password":
            self._bad_password(source)
        if last.get("origin") == "auto" and state in ("failed", "canceled"):
            self._ports["log_event"]("auto_relogin_failed", level="WARN",
                reason=str(last.get("safe_error") or state or "unknown"),
                failures=int(self._ports["auto_snapshot"]().get("failures") or 0),
                **({"elapsed_s": time.monotonic() - began} if began is not None else {}))
        elif last.get("origin") != "auto" and state in ("success", "failed", "canceled"):
            self._ports["log_event"]("relogin_manual_result", state=state,
                                     safe_error=str(last.get("safe_error") or ""))

    def _bad_password(self, source):
        if source == "saved":
            try:
                self._ports["mark_bad"]()
            except OSError:
                pass
            self._ports["emit"]("log", "保存的密码学校不认，自动登录已暂停；到设置里换成新密码。")
        else:
            self._ports["clear_staged"]()
            with self._lock:
                self.once_creds_rejected = True

    def push_expired(self, *, webhook, emit):
        """配了飞书机器人才推；消息只说失效和怎么办，不带账号。在后台线程里发，不拖界面。

        推送体放在这里，是因为「同一次失效只推一次」的判定本来就归本服务：
        note_conclusion 决定推不推，这里只负责怎么推。webhook 与 emit 由组合根注入。
        """
        if not webhook:
            return
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "orange",
                       "title": {"tag": "plain_text", "content": "登录已失效"}},
            "elements": [{"tag": "div", "text": {
                "tag": "lark_md", "content": "登录已失效，回电脑或手机上重新登录。"}}],
        }
        body = json.dumps({"msg_type": "interactive", "card": card},
                          ensure_ascii=False).encode("utf-8")

        def send() -> None:
            request = urllib.request.Request(webhook, data=body,
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    response.read(4096)
                emit("log", "登录失效已推送到飞书")
            except Exception as exc:  # noqa: BLE001 - 推送失败只记类别，不影响登录流程
                emit("log", "飞书推送失败：%s" % type(exc).__name__)

        threading.Thread(target=send, name="feishu-login-expired", daemon=True).start()

    def check(self, request_id=""):
        gate = self._ports["terms_gate"](request_id)
        if gate is not None:
            return dict(gate, queued=False)
        with self._lock:
            if self._coordination.closing:
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "程序正在关闭，已取消本次检查"}
            if self._coordination.cancelling:
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "正在取消报名，等它结束再刷新"}
            if self._coordination.checking:
                self.check_again = True
                answer = {"ok": True, "queued": True, "skipped": "已在检查登录态",
                          "request_id": self.check_request_id}
                if self.check_last.get("payload") and self.check_last.get("request_id") == self.check_request_id:
                    answer["result"] = self.check_last["payload"]
                return answer
            self._coordination.checking = True
            self.check_request_id = request_id or ""
        threading.Thread(target=self._ports["do_check"], daemon=True).start()
        return {"ok": True, "queued": True, "request_id": request_id}

    def do_check(self):
        try:
            self._ports["do_check_inner"]()
        except Exception as exc:  # noqa: BLE001 - 结论构造异常也必须收尾
            with self._lock:
                self.last_check = {"result": "unknown", "checked_at": time.time(), "runtime_error": ""}
            self._ports["emit"]("check", {"ok": False, "result": "unknown",
                                          "text": "检查登录态没跑完，请点「刷新」再试一次"})
            self._ports["emit"]("log", "[X] 检查收尾异常 %s: %s" % (type(exc).__name__, exc))
        finally:
            with self._lock:
                self._coordination.checking = False
                conclusion = self.last_check.get("result", "unknown")
                again = self.check_again and not self._coordination.closing
                self.check_again = False
                if again:
                    self._coordination.checking = True
            self._ports["observe_check"](conclusion)
            self._ports["note_conclusion"](conclusion)
            if conclusion == "expired" and self._ports["silent_state"]()[0]:
                self._ports["request_recover"]()
            if again:
                threading.Thread(target=self._ports["do_check"], daemon=True).start()

    def do_check_inner(self):
        if self._ports["demo"]():
            self.last_check = {"result": "demo", "checked_at": time.time(), "runtime_error": ""}
            self._ports["emit"]("check", {
                "ok": True, "result": "demo", "demo": True,
                "text": "演示模式：使用内存样例，不检查真实登录", "hours_left": None,
                "session_present": None, "session_expired": False, "saved_at": None,
                "estimated_expires_at": None, "reason": "", "hint": "",
                "clock": {"source": "http_date", "state": "unknown", "checked_at": None,
                          "offset_s": None, "uncertainty_s": None, "rtt_s": None,
                          "detail": "演示模式不做校时"}})
            return
        err_code = ""
        try:
            res = self._ports["run_check"]()
            code, out = res["code"], res["out"]
        except self._ports["closing_error"]:
            self._ports["emit"]("check", {"ok": False, "result": "unknown",
                                          "text": "程序正在关闭，本次检查已取消"})
            return
        except OSError as exc:
            err_code = self._ports["component_error"](exc)
            code = -1
            out = "[X] %s" % self._ports["worker_problem"](err_code)
            self._ports["emit"]("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
        except Exception as exc:
            code = -1
            out = "[X] 检查登录态没跑完，请点「刷新」再试一次"
            self._ports["emit"]("log", "[X] 检查登录态异常 %s: %s" % (type(exc).__name__, exc))
        state = self._ports["login_state"]()
        result, _clock, payload = self._ports["build_event"](state, code, out, err_code)
        payload["estimate_reason"] = state.get("estimate_reason")
        self.last_check = {"result": result, "checked_at": time.time(), "runtime_error": err_code}
        payload = dict(payload, **self._ports["last_check_fields"](self.last_check))
        if result == "expired":
            silent, block = self._ports["silent_state"]()
            payload["recovering"] = silent
            payload["recover_block"] = block
        payload.update(self._ports["auto_view"](result == "expired"))
        self._ports["emit"]("check", payload)


class LoginFields:
    @property
    def _relay_proc_tree(self): return self._login_recovery.relay_proc_tree
    @_relay_proc_tree.setter
    def _relay_proc_tree(self, value): self._login_recovery.relay_proc_tree = value
    @property
    def _auto_relogin_started_at(self): return self._login_recovery.auto_relogin_started_at
    @_auto_relogin_started_at.setter
    def _auto_relogin_started_at(self, value): self._login_recovery.auto_relogin_started_at = value
    @property
    def _relay_creds_source(self): return self._login_recovery.relay_creds_source
    @_relay_creds_source.setter
    def _relay_creds_source(self, value): self._login_recovery.relay_creds_source = value
    @property
    def _pending_save(self): return self._login_recovery.pending_save
    @_pending_save.setter
    def _pending_save(self, value): self._login_recovery.pending_save = value
    @property
    def _once_creds_rejected(self): return self._login_recovery.once_creds_rejected
    @_once_creds_rejected.setter
    def _once_creds_rejected(self, value): self._login_recovery.once_creds_rejected = value
    @property
    def _login_seen_valid(self): return self._login_recovery.login_seen_valid
    @_login_seen_valid.setter
    def _login_seen_valid(self, value): self._login_recovery.login_seen_valid = value
    @property
    def _expiry_pushed(self): return self._login_recovery.expiry_pushed
    @_expiry_pushed.setter
    def _expiry_pushed(self, value): self._login_recovery.expiry_pushed = value
    @property
    def _login_expired_logged(self): return self._login_recovery.login_expired_logged
    @_login_expired_logged.setter
    def _login_expired_logged(self, value): self._login_recovery.login_expired_logged = value
    @property
    def _last_check(self): return self._login_recovery.last_check
    @_last_check.setter
    def _last_check(self, value): self._login_recovery.last_check = value
    @_last_check.deleter
    def _last_check(self): del self._login_recovery.last_check
    @property
    def _check_again(self): return self._login_recovery.check_again
    @_check_again.setter
    def _check_again(self, value): self._login_recovery.check_again = value
    @_check_again.deleter
    def _check_again(self): del self._login_recovery.check_again
    @property
    def _check_request_id(self): return self._login_recovery.check_request_id
    @_check_request_id.setter
    def _check_request_id(self, value): self._login_recovery.check_request_id = value
    @_check_request_id.deleter
    def _check_request_id(self): del self._login_recovery.check_request_id
    @property
    def _check_last(self): return self._login_recovery.check_last
    @_check_last.setter
    def _check_last(self, value): self._login_recovery.check_last = value
    @_check_last.deleter
    def _check_last(self): del self._login_recovery.check_last
