# -*- coding: utf-8 -*-
"""手机受限 HTTP 适配器（标准库 http.server）。

只做传输层：路由、Host/Origin/CSRF/会话校验、请求体上限、安全响应头。
业务判定全在 application/phone_service 与 domain/phone_rules，这里不碰 Api。
绑定只允许回环或 Tailscale 专属 IPv4（由调用方先校验）；异常一律回可读
错误码，绝不回堆栈、不记 body/cookie/配对码。

@author Author
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from domain.phone_rules import (
    CSRF_HEADER, MAX_BODY_BYTES, hosts_allowed, origins_allowed,
    parse_json_body,
)

# 固定静态资源表：只认这几条路径，杜绝目录遍历/任意文件读取
PHONE_STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    # 品牌图标：head link rel="icon" 和 apple-touch-icon
    # 走同一个白名单映射，不新开路由、不放宽其他路径
    "/favicon.ico": ("favicon.ico", "image/x-icon"),
    "/apple-touch-icon.png": ("apple-touch-icon.png", "image/png"),
}
SECURITY_HEADERS = (
    # 页面只能用本地资源；验证码图用 data: 内联，不放开外域
    ("Content-Security-Policy",
     "default-src 'self'; script-src 'self'; style-src 'self'; "
     "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)


def _allowed_hosts(bind_host: str, public_host: str,
                   scheme: str = "http") -> tuple:
    """Host/Origin 白名单。

    隧道（https）只认那一个公网域名，旧的本机 Host 必须立刻失效；
    直连（http，Tailscale）除公网名外还要认绑定地址，手机上解析不到
    MagicDNS 时可以用 100.x 备用地址打开。
    """
    values = (public_host,) if str(scheme).lower() == "https" else (public_host, bind_host)
    hosts = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in hosts:
            hosts.append(text)
    return tuple(hosts)


class PhoneHttpServer:
    """ThreadingHTTPServer 的薄包装：start/stop/address，线程随进程收尾。"""

    def __init__(self, host: str, port: int, service, ui_dir: "Path | None" = None,
                 public_host: str = "", public_scheme: str = "http", log=None):
        self._host = str(host)
        self._public_host = str(public_host or host)
        self._public_scheme = "https" if str(public_scheme).lower() == "https" else "http"
        self._service = service
        self._ui_dir = Path(ui_dir) if ui_dir else Path(__file__).resolve().parents[1] / "ui" / "m"
        self._httpd = None
        self._thread = None
        self._want_port = int(port)
        self._log = log

    def start(self) -> None:
        handler = _make_handler(self._service, self._host, self._public_host,
                                self._public_scheme, self._ui_dir, self._log)
        httpd = ThreadingHTTPServer((self._host, self._want_port), handler)
        httpd.daemon_threads = True
        httpd.timeout = 5.0
        httpd._campus_public_host = self._public_host
        httpd._campus_hosts = _allowed_hosts(self._host, self._public_host,
                                           self._public_scheme)
        httpd._campus_public_scheme = self._public_scheme
        self._httpd = httpd
        self._thread = threading.Thread(target=httpd.serve_forever,
                                        name="phone-http", daemon=True)
        self._thread.start()

    def address(self) -> str:
        if self._httpd is None:
            return ""
        suffix = "" if self._public_scheme == "https" else ":%d" % self._httpd.server_address[1]
        return "%s://%s%s" % (self._public_scheme, self._public_host, suffix)

    def set_public_host(self, public_host: str, public_scheme: str = "http") -> None:
        """隧道拿到域名后更新 Host/Origin 白名单与桌面展示地址。"""
        value = str(public_host or "").strip()
        if not value:
            return
        self._public_host = value
        self._public_scheme = "https" if str(public_scheme).lower() == "https" else "http"
        if self._httpd is not None:
            self._httpd._campus_public_host = value
            self._httpd._campus_hosts = _allowed_hosts(self._host, value,
                                                     self._public_scheme)
            self._httpd._campus_public_scheme = self._public_scheme

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        if httpd is None:
            return
        try:
            httpd.shutdown()
        except Exception:  # noqa: BLE001 - 关闭尽力而为
            pass
        try:
            httpd.server_close()
        except Exception:  # noqa: BLE001
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def _make_handler(service, bind_host: str, public_host: str,
                  public_scheme: str, ui_dir: Path, log=None):
    """按服务实例生成处理器类：Host/Origin 用服务的字面 origin，不收外部配置。"""

    class Handler(BaseHTTPRequestHandler):
        server_version = "campus-phone"
        sys_version = ""
        # 慢速客户端也不能把线程挂死：连接级 socket 超时
        timeout = 10

        # BaseHTTPRequestHandler 默认把请求行打进 stderr；这里不落任何访问日志
        def log_message(self, fmt, *args):
            return

        # 非法方法一律拒绝：不给默认 501 页面，也不回服务器版本
        def do_PUT(self):  # noqa: N802
            self._deny("method_not_allowed", 405)

        def do_DELETE(self):  # noqa: N802
            self._deny("method_not_allowed", 405)

        def do_PATCH(self):  # noqa: N802
            self._deny("method_not_allowed", 405)

        def do_OPTIONS(self):  # noqa: N802
            self._deny("method_not_allowed", 405)

        def do_HEAD(self):  # noqa: N802
            self._deny("method_not_allowed", 405)

        # ---- 通用出口 ----
        def _send(self, status: int, body: bytes, content_type: str,
                  extra: "list | None" = None) -> None:
            self._campus_status = status
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                for key, value in SECURITY_HEADERS:
                    self.send_header(key, value)
                for key, value in (extra or []):
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)
            except Exception:  # noqa: BLE001 - 客户端断开等不外抛
                pass

        def _json(self, status: int, payload: dict, extra: "list | None" = None) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8", extra)

        def _deny(self, code: str, status: int = 403) -> None:
            # 只回错误码与一句话，不回堆栈、不回路径、不回请求内容
            self._campus_error = code
            # 先读掉未读的请求体：Windows 关闭留有未读数据的连接会发 RST，
            # 客户端可能读不到拒绝回包，只看到连接被中止（WinError 10053）
            self._discard_unread_body()
            self._json(status, {"ok": False, "error": code})

        def _log_access(self) -> None:
            """一行一条请求，只记「谁问的、结果如何」，不记 cookie 值、不记请求体。

            排查手机端问题全靠这行：Host/Origin 说明请求打的是哪个地址，
            cookies 里的名字说明浏览器到底带回了哪些凭证。
            """
            if log is None:
                return
            names = [part.split("=", 1)[0].strip()
                     for part in str(self.headers.get("Cookie") or "").split(";")
                     if "=" in part]
            try:
                log("http %s %s %d%s host=%s origin=%s cookies=[%s]" % (
                    self.command, self.path.split("?", 1)[0],
                    self._campus_status,
                    (" " + self._campus_error) if self._campus_error else "",
                    self.headers.get("Host") or "-",
                    self.headers.get("Origin") or "-",
                    ",".join(names)))
            except Exception:  # noqa: BLE001 - 记日志失败不影响响应
                pass

        def _expected_port(self) -> int:
            # 测试可用端口 0 换临时端口：校验必须认实际监听端口，不是写死 8765
            try:
                return int(self.server.server_address[1])
            except Exception:
                return 8765

        def _check_host(self) -> bool:
            hosts = getattr(self.server, "_campus_hosts",
                            (public_host, bind_host))
            return hosts_allowed(self.headers.get("Host"), hosts,
                                 self._expected_port())

        def _check_origin(self) -> bool:
            expected = getattr(self.server, "_campus_public_host", public_host)
            scheme = getattr(self.server, "_campus_public_scheme", public_scheme)
            if scheme == "https":
                # 隧道是 https 时只认那一个公网 origin
                return str(self.headers.get("Origin") or "").strip() == (
                    "https://%s" % expected)
            hosts = getattr(self.server, "_campus_hosts",
                            (public_host, bind_host))
            return origins_allowed(self.headers.get("Origin"), hosts,
                                   self._expected_port())

        def _read_body(self):
            raw_len = self.headers.get("Content-Length")
            if raw_len is None:
                return None, "empty_body"
            try:
                length = int(raw_len)
            except (TypeError, ValueError):
                return None, "bad_length"
            if length < 0 or length > MAX_BODY_BYTES:
                return None, "body_too_large"
            if length == 0:
                return None, "empty_body"
            body = self.rfile.read(length)
            self._campus_body_consumed = True
            return body, ""

        def _discard_unread_body(self):
            """拒绝前把未读的请求体读掉，客户端才能完整收到 403/405。

            只在 0 < Content-Length <= 上限时读；缺失、非法、超过上限都不读，照旧回包。
            读请求体受 Handler.timeout = 10 的连接超时约束，慢客户端挂不死线程。
            """
            if getattr(self, "_campus_body_consumed", False):
                return
            raw_len = self.headers.get("Content-Length")
            try:
                length = int(raw_len)
            except (TypeError, ValueError):
                return
            if length <= 0 or length > MAX_BODY_BYTES:
                return
            try:
                self.rfile.read(length)
            except Exception:  # noqa: BLE001 - 客户端断开等不外抛
                pass
            self._campus_body_consumed = True

        def _require_json_type(self) -> bool:
            ctype = str(self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            return ctype == "application/json"

        # ---- 路由 ----
        def do_GET(self):  # noqa: N802 - 基类命名
            self._campus_status = 0
            self._campus_error = ""
            try:
                self._route_get()
            except Exception:  # noqa: BLE001 - 任何异常都不回堆栈
                self._deny("internal", 500)
            finally:
                self._log_access()

        def do_POST(self):  # noqa: N802
            self._campus_status = 0
            self._campus_error = ""
            try:
                self._route_post()
            except Exception:  # noqa: BLE001
                self._deny("internal", 500)
            finally:
                self._log_access()

        def _route_get(self):
            if not self._check_host():
                return self._deny("bad_host")
            path = self.path.split("?", 1)[0]
            if path in ("/api/state",):
                return self._get_state()
            if path in PHONE_STATIC:
                return self._get_static(path)
            return self._deny("not_found", 404)

        def _route_post(self):
            if not self._check_host():
                return self._deny("bad_host")
            if not self._check_origin():
                return self._deny("bad_origin")
            if not self._require_json_type():
                return self._deny("bad_content_type")
            path = self.path.split("?", 1)[0]
            if path == "/pair":
                return self._post_pair()
            if path == "/api/action":
                return self._post_action()
            return self._deny("not_found", 404)

        # ---- 静态页 ----
        def _get_static(self, path):
            name, ctype = PHONE_STATIC[path]
            target = (ui_dir / name).resolve()
            # 固定映射之外的文件永远取不到：目录穿越无从谈起
            if not target.is_file():
                return self._deny("not_found", 404)
            try:
                body = target.read_bytes()
            except Exception:  # noqa: BLE001
                return self._deny("not_found", 404)
            self._send(200, body, ctype)

        # ---- 配对 ----
        def _post_pair(self):
            raw, error = self._read_body()
            if error:
                return self._deny(error, 400)
            data, error = parse_json_body(raw)
            if error:
                return self._deny(error, 400)
            result = service.pair(data.get("code"), ip=self.client_address[0])
            if not result.get("ok"):
                return self._json(403, result)
            cookies = [("Set-Cookie", result.get("cookie", "")),
                       ("Set-Cookie", result.get("csrf_cookie", ""))]
            # 只有固定地址通道会带回设备 cookie；Cloudflare 通道没有这一条
            if result.get("device_cookie"):
                cookies.append(("Set-Cookie", result["device_cookie"]))
            self._json(200, {"ok": True, "csrf_header": result.get("csrf_header", CSRF_HEADER),
                             "csrf": result.get("csrf", ""),
                             "expires_in": result.get("expires_in", 0)},
                       extra=cookies)

        # ---- 状态（只读本机缓存，绝不触发学校流量）----
        def _get_state(self):
            if not self._check_host():
                return self._deny("bad_host")
            cookie = self.headers.get("Cookie")
            # 浏览器把会话与设备 cookie 放在同一个 Cookie 头里：先认活动会话，
            # 没有会话才用设备信任换一条新的（只有 Tailscale 通道会走到这里）。
            session, headers = service.authenticate_or_restore(cookie, cookie)
            if session is None:
                return self._deny("need_pair", 401)
            cursor = None
            if "?" in self.path:
                for piece in self.path.split("?", 1)[1].split("&"):
                    key, _, value = piece.partition("=")
                    if key == "after":
                        cursor = value
            self._json(200, service.safe_state(cursor), extra=headers)

        # ---- 动作 ----
        def _post_action(self):
            session = service.authenticate(self.headers.get("Cookie"))
            if session is None:
                return self._deny("need_pair", 401)
            header = str(self.headers.get(CSRF_HEADER) or "")
            if not header or header != session.get("csrf"):
                return self._deny("bad_csrf")
            raw, error = self._read_body()
            if error:
                return self._deny(error, 400)
            data, error = parse_json_body(raw)
            if error:
                return self._deny(error, 400)
            self._json(200, service.dispatch(data.get("action"), data.get("args")))

    return Handler
