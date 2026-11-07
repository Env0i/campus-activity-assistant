# -*- coding: utf-8 -*-
"""手机受限访问用例门面：配对、会话、动作派发与有界事件缓冲。

Api、此刻、状态读取与服务启动端口全部由 app 注入；这里不碰 Windows API、
不碰具体路径、不起真实浏览器。会话与配对码只活在内存里：停服务即撤销，
重开工具必须回电脑重新配对。所有锁都是本模块自己的，绝不与 Api/协调器的
锁互相等待（_emit 投递走独立事件锁）。

@author Author
"""
from __future__ import annotations

import secrets
import threading
from urllib.parse import urlsplit

from domain.phone_rules import (
    COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER, DEVICE_COOKIE_NAME,
    EVENT_BUFFER_LIMIT, GLOBAL_FAIL_LIMIT, IP_FAIL_LIMIT, IP_LOCK_S, HTTP_PORT,
    PAIR_CODE_LEN, PAIR_TTL_S, SESSION_TTL_S, cookie_header_value,
    csrf_cookie_header_value, device_cookie_header_value, is_allowed_bind,
    lock_active, normalize_action, pair_code_fresh, project_state,
    select_events, session_alive, valid_pair_code,
)


class PhoneAccessService:
    """默认关闭的受限手机入口：只认配对过的会话，动作走严格白名单。"""

    def __init__(self, *, api, now, state_of, server_factory, log=None,
                 device_store=None):
        self._api = api
        self._now = now
        self._state_of = state_of
        self._server_factory = server_factory
        self._log = log or (lambda _msg: None)
        # 设备信任存储由 app 注入；为空就等于这个通道不支持免重配对
        self._device_store = device_store
        self._persistent_device = False
        # 配对/会话/限速同一把锁：比较与消费必须原子（一码一次，双兑换只有一赢）
        self._lock = threading.Lock()
        # 事件缓冲独立锁：_emit 投递不与 Api 锁互相等待，也不回调 HTTP 客户端
        self._event_lock = threading.Condition()
        self._events: list = []
        self._seq = 0
        self._pair_code = ""
        self._pair_created = 0.0
        self._pair_used = False
        # 每换一张配对码就 +1：桌面面板靠它判断「码变过」，不靠时间猜
        self._pair_seq = 0
        self._pair_reason = ""
        # 本次开启后成功兑换配对码的次数（settings-gap B1）：设置抽屉靠它判断「手机已连接」，
        # 不靠 pair_code_status 的瞬时 reason——换出来的那张码一过期，reason 就不再是 paired。
        self._paired_count = 0
        self._sessions: dict = {}
        self._fail_by_ip: dict = {}
        self._ip_lock_until: dict = {}
        self._global_fails = 0
        self._global_lock_until = 0.0
        self._server = None
        self._bind_host = ""
        self._public_host = ""
        self._public_scheme = "http"

    # ---------- 生命周期 ----------
    def is_running(self) -> bool:
        return self._server is not None

    def address(self) -> str:
        if self._server is None:
            return ""
        try:
            return str(self._server.address())
        except Exception:
            return ""

    def bind_supported(self, host: str = "127.0.0.1") -> bool:
        return is_allowed_bind(host)

    def pair_code_status(self) -> dict:
        """配对码 + 剩余有效秒数 + 换码序号，供桌面面板提示「码变了」。

        一码一次的语义不变：换出来的码同样只能兑换一次。码本身不进 URL、
        不落日志、不发给未配对手机；这里额外给出的只有剩余时间和换码原因。
        """
        # 时钟不可用时不能猜剩余时间，也不能让面板接口整轮失败：
        # 校时是外部依赖，面板刷新是高频路径，这里按「暂时不知道」降级。
        try:
            now = float(self._now())
        except Exception:
            return {"code": "", "expires_in": 0, "seq": self._pair_seq,
                    "reason": "clock_unavailable"}
        with self._lock:
            if self._server is not None and (
                    not self._pair_code or self._pair_used
                    or not pair_code_fresh(self._pair_created, now)):
                # 换码原因要保留：界面上「已配对换新」和「过期换新」的话术不同
                if self._pair_code and self._pair_used:
                    reason = "paired"
                elif self._pair_code:
                    reason = "expired"
                else:
                    reason = "new"
                self._pair_code = "".join(secrets.choice("0123456789")
                                          for _ in range(PAIR_CODE_LEN))
                self._pair_created = now
                self._pair_used = False
                self._pair_seq += 1
                self._pair_reason = reason
            if not self._pair_code or self._pair_used or not pair_code_fresh(
                    self._pair_created, now):
                return {"code": "", "expires_in": 0,
                        "seq": self._pair_seq, "reason": self._pair_reason}
            left = int(PAIR_TTL_S - (now - float(self._pair_created)))
            return {"code": self._pair_code, "expires_in": max(0, left),
                    "seq": self._pair_seq, "reason": self._pair_reason}

    def paired_count(self) -> int:
        """本次开启后成功兑换配对码的次数（只读；停止手机访问时清零）。"""
        with self._lock:
            return int(self._paired_count)

    def current_pair_code(self) -> str:
        """桌面面板显示一次性配对码；用过/过期就自动换一张新的。"""
        return str(self.pair_code_status().get("code") or "")

    def start(self, host: str = "127.0.0.1", port: int = HTTP_PORT,
              public_host: str = "", public_scheme: str = "http",
              persistent_device: bool = False) -> dict:
        """启动受限 HTTP 服务；默认关闭，只有显式开启才建 socket。

        persistent_device 只在地址固定的通道（Tailscale）为 True：只有它才签发
        设备信任 cookie，Cloudflare 每次都是新域名，恢复必然失败。
        """
        if not is_allowed_bind(host):
            return {"ok": False, "error": "bind_not_allowed",
                    "text": "只允许本机回环或 Tailscale 专属地址"}
        with self._lock:
            if self._server is not None:
                return {"ok": False, "error": "already_running",
                        "text": "手机访问已在运行"}
            self._pair_code = "".join(secrets.choice("0123456789")
                                      for _ in range(PAIR_CODE_LEN))
            self._pair_created = float(self._now())
            self._pair_used = False
            self._pair_seq += 1
            self._pair_reason = "started"
            self._paired_count = 0       # 每次重新开启都从零数起
            self._bind_host = str(host)
            self._public_host = str(public_host or host)
            self._public_scheme = "https" if str(public_scheme).lower() == "https" else "http"
        try:
            try:
                server = self._server_factory(host, port, self, self._public_host,
                                              self._public_scheme)
            except TypeError:
                # 兼容已有测试替身和旧的三参数工厂；真实 HTTP 适配器支持第四参数。
                server = self._server_factory(host, port, self)
            server.start()
        except Exception as exc:  # noqa: BLE001 - 端口占用等要给可读结论
            with self._lock:
                self._pair_code = ""
                self._pair_used = False
                self._public_host = ""
                self._public_scheme = "http"
            return {"ok": False, "error": "listen_failed",
                    "text": "手机服务没能监听：%s" % type(exc).__name__}
        with self._lock:
            self._server = server
            self._persistent_device = bool(persistent_device) and self._device_store is not None
        return {"ok": True, "address": self.address(),
                "pair_code": self.current_pair_code(),
                "persistent_device": self._persistent_device}

    def set_public_host(self, public_host: str, scheme: str = "http") -> dict:
        """为已监听的本地服务切换远程展示域名（Cloudflare 建隧道后调用）。"""
        value = str(public_host or "").strip()
        if not value:
            return {"ok": False, "error": "bad_public_host"}
        with self._lock:
            server = self._server
            self._public_host = value
            self._public_scheme = "https" if str(scheme).lower() == "https" else "http"
        setter = getattr(server, "set_public_host", None) if server else None
        if callable(setter):
            try:
                setter(value, self._public_scheme)
            except TypeError:
                setter(value)
        return {"ok": True, "address": self.address()}

    def set_public_url(self, public_url: str) -> dict:
        parsed = urlsplit(str(public_url or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return {"ok": False, "error": "bad_public_url"}
        return self.set_public_host(parsed.hostname, parsed.scheme)

    def stop(self, revoke_devices: bool = True) -> dict:
        """关闭 HTTP 并撤销全部会话：有界收尾，不等慢客户端。

        手动关闭默认连设备信任一起撤销（「关闭手机访问」就该断开这台手机）；
        进程退出的路径走 shutdown(preserve_devices=True) 保留它。
        """
        with self._lock:
            server = self._server
            self._server = None
            self._sessions.clear()
            self._pair_code = ""
            self._pair_used = False
            self._paired_count = 0       # 停止手机访问即清零（B1）
            self._public_host = ""
            self._public_scheme = "http"
            self._persistent_device = False
            self._fail_by_ip.clear()
            self._ip_lock_until.clear()
            self._global_fails = 0
            self._global_lock_until = 0.0
        if server is not None:
            try:
                server.stop()
            except Exception:  # noqa: BLE001 - 关闭尽力而为，异常不外抛
                pass
        if revoke_devices and self._device_store is not None:
            try:
                self._device_store.revoke_all()
            except Exception:  # noqa: BLE001 - 撤销失败不能挡住关服务
                pass
        return {"ok": True}

    def shutdown(self, preserve_devices: bool = True) -> dict:
        """程序退出用：默认保留设备信任，下次开工具还能直接连。"""
        return self.stop(revoke_devices=not preserve_devices)

    # ---------- 配对与会话 ----------
    def pair(self, code, ip: str = "") -> dict:
        """一次性兑换配对码 → 会话 cookie + CSRF 头值。比较/消费同一临界区。"""
        now = float(self._now())
        with self._lock:
            if self._locked(ip, now):
                self._note_pair(False, "尝试次数过多被限速")
                return {"ok": False, "error": "locked",
                        "text": "尝试次数过多，请稍后再试"}
            if not self._pair_code or self._pair_used or not pair_code_fresh(
                    self._pair_created, now):
                self._note_pair(False, "配对码不存在或已用过")
                return {"ok": False, "error": "no_code",
                        "text": "配对码不可用，请在电脑上重新开启"}
            if not valid_pair_code(code) or not secrets.compare_digest(
                    str(code), self._pair_code):
                self._record_failure(ip, now)
                self._note_pair(False, "配对码不对")
                return {"ok": False, "error": "bad_code",
                        "text": "配对码不对，请核对后重试"}
            self._pair_used = True
            self._paired_count += 1      # 只在兑换成功处加一；失败、限速都不算（B1）
            self._fail_by_ip.pop(ip, None)
            self._global_fails = 0
            token = secrets.token_hex(32)      # 256 位
            csrf = secrets.token_hex(32)
            self._sessions[token] = {"csrf": csrf, "created_at": now}
            # 设备信任只在固定地址通道签发：换域名就是换 origin，恢复了也没用
            device_token = (secrets.token_hex(32)
                            if self._persistent_device and self._device_store is not None
                            else "")
            if device_token:
                # 与 stop 的清会话同锁；配对落盘不得越过关闭时的撤销。
                try:
                    self._device_store.add_device(device_token, now)
                except Exception as exc:
                    self._log("设备信任落盘失败（%s），本次不签发设备 cookie"
                              % type(exc).__name__)
                    device_token = ""
        self._note_pair(True)
        return {"ok": True,
                "cookie_name": COOKIE_NAME,
                "cookie": cookie_header_value(token),
                "csrf_cookie": csrf_cookie_header_value(csrf),
                "csrf_header": CSRF_HEADER,
                "csrf": csrf,
                "device_cookie": (device_cookie_header_value(device_token)
                                  if device_token else ""),
                "expires_in": SESSION_TTL_S}

    def authenticate(self, cookie_header) -> "dict | None":
        """校验会话 cookie；过期即失效，且校验不刷新寿命。"""
        token = _cookie_value(cookie_header, COOKIE_NAME)
        if not token:
            return None
        now = float(self._now())
        with self._lock:
            session = self._sessions.get(token)
            if session is None or not session_alive(session, now):
                return None
            return {"token": token, "csrf": session.get("csrf", ""),
                    "created_at": session.get("created_at")}

    def has_live_session(self) -> bool:
        """还有没有未过期的手机会话。只回答「有没有」，绝不回传 token 或 cookie。

        关窗隐藏前要靠它判断「藏起来之后还叫得回来吗」：任务栏按钮消失以后，
        托盘或手机页是仅有的两条路。时间源坏掉时按「没人能唤回」处理——
        宁可拒绝隐藏，也不要把窗口藏成打不开的样子。
        """
        try:
            now = float(self._now())
        except Exception:  # noqa: BLE001 - 时钟不可用只影响这一次判断
            return False
        with self._lock:
            return any(session_alive(session, now)
                       for session in self._sessions.values())

    def authenticate_or_restore(self, cookie_header,
                                device_cookie_header="") -> "tuple":
        """读状态用：活动会话优先，没有会话才用设备信任换一条新会话。

        返回 (会话, 额外 Set-Cookie 列表)。浏览器把两种 cookie 放在同一个
        Cookie 头里，所以两个参数常常传同一个头，各自按键名取值。
        """
        session = self.authenticate(cookie_header)
        if session is not None:
            return session, []
        device_token = _cookie_value(device_cookie_header, DEVICE_COOKIE_NAME)
        if not device_token:
            self._log("信任恢复：请求里没有设备 cookie")
            return None, []
        with self._lock:
            # 校验、重建与 stop 清会话必须串行，避免停服务后迟到的校验重建权限。
            if not self._persistent_device or self._device_store is None:
                return None, []
            try:
                now = float(self._now())
                if not self._device_store.validate_device(device_token, now):
                    self._log("信任恢复：设备 cookie 不在信任列表（或已过期）")
                    return None, []
            except Exception as exc:
                self._log("信任恢复：设备信任存储不可用（%s）" % type(exc).__name__)
                return None, []
            self._log("信任恢复：设备 cookie 通过，重建会话")
            token = secrets.token_hex(32)
            csrf = secrets.token_hex(32)
            self._sessions[token] = {"csrf": csrf, "created_at": now}
        headers = [("Set-Cookie", cookie_header_value(token)),
                   ("Set-Cookie", csrf_cookie_header_value(csrf)),
                   ("Set-Cookie", device_cookie_header_value(device_token))]
        return ({"token": token, "csrf": csrf, "created_at": now, "restored": True},
                headers)

    def _note_pair(self, ok: bool, reason: str = "") -> None:
        """配对结果留一行给日志：只记成败与原因，绝不记配对码。"""
        if ok:
            self._log("配对成功：已签发会话%s" % (
                "，并登记了本机设备信任" if self._persistent_device else ""))
        else:
            self._log("配对失败：%s" % (reason or "未知原因"))

    def _locked(self, ip: str, now: float) -> bool:
        if lock_active(self._global_lock_until, now):
            return True
        return lock_active(self._ip_lock_until.get(ip or "", 0), now)

    def _record_failure(self, ip: str, now: float) -> None:
        key = str(ip or "")
        self._fail_by_ip[key] = self._fail_by_ip.get(key, 0) + 1
        self._global_fails += 1
        if self._fail_by_ip[key] >= IP_FAIL_LIMIT:
            self._ip_lock_until[key] = now + IP_LOCK_S
        if self._global_fails >= GLOBAL_FAIL_LIMIT:
            self._global_lock_until = now + IP_LOCK_S

    # ---------- 状态与事件 ----------
    def safe_state(self, cursor=None) -> dict:
        """手机可读快照：只读本机缓存，绝不在这里碰学校接口。"""
        with self._event_lock:
            events, reset = select_events([dict(event) for event in self._events], cursor)
            seq = self._seq
        return {"state": project_state(self._state_of()),
                "events": events, "reset": reset, "seq": seq}

    def record_event(self, kind, payload) -> None:
        """_emit 投递入口：窗口为空也可发布；锁外投递，不回调任何 HTTP 客户端。"""
        from domain.phone_rules import project_event
        safe = project_event(kind, payload)
        with self._event_lock:
            self._seq += 1
            self._events.append({"seq": self._seq, "kind": safe["kind"],
                                 "payload": safe["payload"]})
            if len(self._events) > EVENT_BUFFER_LIMIT:
                del self._events[:-EVENT_BUFFER_LIMIT]
            self._event_lock.notify_all()

    def _snapshot_events(self) -> list:
        with self._event_lock:
            return [dict(event) for event in self._events]

    # ---------- 动作派发 ----------
    def dispatch(self, action, args) -> dict:
        """严格白名单派发：只调白名单内方法与参数，绝不反射任意 Api。"""
        clean, error = normalize_action(action, args)
        if error:
            return {"ok": False, "error": error}
        name = str(action)
        if name == "save_retry_policy":
            # 手机只许改重试策略：terms/路径/任意键一律不进偏好
            return self._call("save_prefs",
                              {"prefs": {"retry_policy": clean.get("retry_policy", {})}})
        if name == "start_plan":
            # 计划来源由服务端补：手机请求体里带不进 source（白名单拒绝），这里写死 phone
            clean = dict(clean, source="phone")
        return self._call(name, clean)

    def _call(self, name: str, params: dict) -> dict:
        method = getattr(self._api, name, None)
        if method is None:
            return {"ok": False, "error": "not_available"}
        try:
            result = method(**params)
        except Exception as exc:  # noqa: BLE001 - 本机异常只回类型，不回堆栈
            return {"ok": False, "error": "internal",
                    "text": "本机执行失败：%s" % type(exc).__name__}
        return result if isinstance(result, dict) else {"ok": True}

    # ---------- 会话撤销（停服务/关闭时） ----------
    def revoke_all(self) -> None:
        with self._lock:
            self._sessions.clear()


def _cookie_value(header, name: str) -> str:
    """从 Cookie 头里取指定键的值；畸形输入一律当没有。"""
    text = str(header or "")
    for part in text.split(";"):
        key, _, value = part.strip().partition("=")
        if key == name:
            return value.strip()
    return ""
