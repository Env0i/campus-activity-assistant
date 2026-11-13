# -*- coding: utf-8 -*-
"""手机样机服务：按 manifest 显式登记的文件提供页面，收集上报并脱敏写盘。

安全头与 Host 校验照 local/infrastructure/phone_http.py:24-60 的写法
（SECURITY_HEADERS 与 _allowed_hosts 的语义），只服务本计划登记过的文件。

  python serve_probe.py --channel tailscale --bind <Tailscale 地址> \
      --public-host <MagicDNS 名> --port 8765
  python serve_probe.py --channel cloudflare --cloudflared <cloudflared.exe 路径>
  python serve_probe.py --selfdrive          # 本机源码态试跑（WebView2 当手机浏览器）

退出条件：--duration 秒后自动退出（默认 900 秒 = 15 分钟），或 Ctrl+C。
退出前确认端口已释放，并在日志里写一行。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_WEB = HERE.parent / "web" / "generated"
DEFAULT_RESULTS = HERE.parent / "results"
MAX_BODY = 64 * 1024
DEFAULT_DURATION = 15 * 60
SERVER_NAME = "esm-verify-probe"

sys.path.insert(0, str(HERE.parent / "tools"))
from redact import find_residual, redact_obj, redact_text  # noqa: E402


# F1（返修）：控制台打印可能因编码抛异常。日志函数在 selfdrive 的 finally 里也会调用，
# 若在这里抛出，os._exit 走不到，WebView2 窗口不退，进程挂住，所以打印失败只降级。
def _say(message: str) -> None:
    try:
        print(message, flush=True)
    except Exception:  # noqa: BLE001 - 打印失败只降级
        try:
            sys.stdout.write(message.encode("ascii", "replace").decode("ascii") + "\n")
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass

# 与 local/infrastructure/phone_http.py:34-42 完全一致
SECURITY_HEADERS = (
    ("Content-Security-Policy",
     "default-src 'self'; script-src 'self'; style-src 'self'; "
     "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)


# ---------------------------------------------------------------- 工具函数
def browser_label(ua: str) -> str:
    """把 User-Agent 压成一个稳定的短标签，用于结果文件名。"""
    text = str(ua or "")
    low = text.lower()
    wechat = "micromessenger" in low
    lark = "lark" in low or "feishu" in low
    iphone = "iphone" in low or "ipad" in low or "ios" in low
    android = "android" in low
    if wechat:
        return "ios-wechat" if iphone else ("android-wechat" if android else "wechat")
    if lark:
        return "ios-lark" if iphone else ("android-lark" if android else "lark")
    if iphone:
        return "ios-safari"
    if android:
        return "android-chrome"
    if "edg/" in low or "chrome/" in low:
        return "desktop-webview2"
    return "unknown"


def hostname_of(value: str) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("["):
        return text.split("]")[0].lstrip("[")
    return text.split(":", 1)[0]


def allowed_hosts(bind_host: str, public_host: str, scheme: str) -> tuple:
    """照 phone_http.py:45-59：https 只认隧道域名，http 还认绑定地址。"""
    values = (public_host,) if scheme == "https" else (public_host, bind_host)
    hosts = []
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in hosts:
            hosts.append(text)
    return tuple(hosts)


def port_released(host: str, port: int) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.close()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- 服务主体
class ProbeState:
    def __init__(self, web_root: Path, results: Path, channel: str,
                 extra_names: list[str], log_path: Path):
        self.web_root = web_root
        self.results = results
        self.channel = channel
        self.extra_names = extra_names
        self.log_path = log_path
        self.manifest = self._load_manifest()
        self.reports: list[dict] = []
        self.seq: dict[str, int] = {}
        self.lock = threading.Lock()
        self.bind_host = ""
        self.public_host = ""
        self._log_lines: list[str] = []

    def _load_manifest(self) -> dict:
        path = self.web_root / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        files = {}
        for url_path, meta in data.get("files", {}).items():
            files[url_path] = (meta["file"], meta["type"])
        return files

    def log(self, message: str) -> None:
        line = redact_text("[%s] %s" % (time.strftime("%H:%M:%S"), message),
                           self.extra_names)
        self._log_lines.append(line)
        _say(line)
        try:
            self.log_path.write_text("\n".join(self._log_lines) + "\n", encoding="utf-8")
        except OSError:
            pass

    def next_name(self, label: str) -> str:
        key = label
        with self.lock:
            self.seq[key] = self.seq.get(key, 0) + 1
            return "phone-%s-%s-%02d.json" % (self.channel, label, self.seq[key])

    def save_report(self, payload: dict, host_header: str, ua: str) -> Path:
        label = browser_label(ua)
        name = self.next_name(label)
        record = {
            "channel": self.channel,
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "server": {
                "bind_host": self.bind_host,
                "public_host": self.public_host,
                "host_header": host_header,
                "scheme": "https" if self.channel == "cloudflare" else "http",
            },
            "client": {
                "browser": label,
                "ua": ua,
            },
            "payload": payload,
        }
        record = redact_obj(record, self.extra_names)
        residual = find_residual(json.dumps(record, ensure_ascii=False), self.extra_names)
        if residual:
            self.log("脱敏自检发现残留，已停下不写盘：%s" % ", ".join(sorted(set(residual))[:5]))
            raise RuntimeError("redaction residual")
        path = self.results / name
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        with self.lock:
            self.reports.append(record)
        self.log("收到上报 → %s（page=%s form=%s run=%s）" % (
            name, payload.get("page"), payload.get("form"), payload.get("run")))
        return path

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        failures = []
        with self.lock:
            for item in self.reports:
                payload = item.get("payload") or {}
                key = "%s" % (payload.get("page") or "unknown")
                if payload.get("form"):
                    key += ":" + str(payload.get("form"))
                counts[key] = counts.get(key, 0) + 1
                if payload.get("page") == "h9":
                    expected = payload.get("expected_count") or 0
                    if expected and payload.get("module_count") != expected:
                        failures.append("%s run%s 模块数 %s != %s" % (
                            payload.get("form"), payload.get("run"),
                            payload.get("module_count"), expected))
                if payload.get("fallback", {}).get("shown") \
                        and payload.get("page") != "h11":
                    failures.append("%s 出现兜底提示" % key)
                if payload.get("missing_module", {}).get("element_error") is None \
                        and payload.get("page") == "h11":
                    failures.append("h11 没有记录到 404 的 error 事件")
            return {"total": len(self.reports), "counts": counts,
                    "failures": failures}


def make_handler(state: ProbeState):
    class ProbeHandler(BaseHTTPRequestHandler):
        server_version = SERVER_NAME
        sys_version = ""

        def log_message(self, fmt, *args):  # noqa: D401 - 静默访问日志
            return

        # ---- 公共 ----
        def _host_ok(self) -> bool:
            host = hostname_of(self.headers.get("Host", ""))
            return host in self.server.allowed_hosts

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for key, value in SECURITY_HEADERS:
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _send_json(self, code: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(code, body, "application/json; charset=utf-8")

        def _bad_host(self) -> None:
            # E6：被拒的 Host 可能含 tailnet 名，先脱敏再写日志（log() 内还会再脱敏一次）
            state.log("拒绝 Host=%s" % redact_text(self.headers.get("Host", ""), state.extra_names))
            self._send(403, b"host not allowed", "text/plain; charset=utf-8")

        # ---- GET ----
        def do_GET(self) -> None:  # noqa: N802 - 基类命名
            if not self._host_ok():
                self._bad_host()
                return
            path = urllib.parse.urlsplit(self.path).path
            if path == "/__summary":
                self._send_json(200, state.summary())
                return
            if path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
                return
            entry = state.manifest.get(path)
            if entry is None:
                entry = state.manifest.get(path + "index.html")
            if entry is None:
                self._send(404, b"not registered", "text/plain; charset=utf-8")
                return
            rel, mime = entry
            target = (state.web_root / rel).resolve()
            try:
                target.relative_to(state.web_root.resolve())
            except ValueError:
                self._send(404, b"bad path", "text/plain; charset=utf-8")
                return
            if not target.is_file():
                self._send(404, b"missing file", "text/plain; charset=utf-8")
                return
            self._send(200, target.read_bytes(), mime)

        # ---- POST ----
        def do_POST(self) -> None:  # noqa: N802 - 基类命名
            if not self._host_ok():
                self._bad_host()
                return
            path = urllib.parse.urlsplit(self.path).path
            if path != "/__report":
                self._send(404, b"not registered", "text/plain; charset=utf-8")
                return
            origin = self.headers.get("Origin", "")
            if origin:
                parsed = urllib.parse.urlsplit(origin)
                if hostname_of(parsed.netloc) not in self.server.allowed_hosts:
                    self._send(403, b"origin not allowed", "text/plain; charset=utf-8")
                    return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send(411, b"length required", "text/plain; charset=utf-8")
                return
            if length > MAX_BODY:
                self._send(413, b"too large", "text/plain; charset=utf-8")
                return
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self._send(400, b"bad json", "text/plain; charset=utf-8")
                return
            if not isinstance(payload, dict):
                self._send(400, b"bad payload", "text/plain; charset=utf-8")
                return
            ua = self.headers.get("User-Agent", "")
            if not payload.get("ua"):
                payload["ua"] = ua
            path_written = state.save_report(payload, self.headers.get("Host", ""), ua)
            self._send_json(200, {"ok": True, "file": path_written.name})

    return ProbeHandler


# ---------------------------------------------------------------- Cloudflare 隧道
def start_cloudflared(exe: str, port: int, state: ProbeState):
    """起临时隧道并解析出 trycloudflare.com 域名；返回 (进程, 域名)。"""
    state.log("启动 cloudflared 临时隧道（只连本机 %d 端口）" % port)
    proc = subprocess.Popen(
        [exe, "tunnel", "--url", "http://127.0.0.1:%d" % port, "--no-autoupdate"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
    )
    deadline = time.time() + 90
    public = ""
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.2)
            continue
        if "trycloudflare.com" in line:
            for token in line.replace("|", " ").split():
                if token.startswith("https://") and "trycloudflare.com" in token:
                    public = token.rstrip(".,;")
                    break
        if public:
            break
    if not public:
        raise SystemExit("cloudflared 90 秒内没有给出 trycloudflare.com 地址")
    host = urllib.parse.urlsplit(public).hostname or ""
    state.log("隧道就绪（域名已脱敏）")
    return proc, host  # type: ignore[return-value]


# ---------------------------------------------------------------- main
def main() -> int:
    # F1（返修）：stdout 被重定向且不是 UTF-8 时改为 replace
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["tailscale", "cloudflare"], default="tailscale")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-host", default="")
    parser.add_argument("--cloudflared", default="")
    parser.add_argument("--web", default=str(DEFAULT_WEB))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION)
    parser.add_argument("--selfdrive", action="store_true",
                        help="本机源码态试跑：用 WebView2 当手机浏览器依次加载探针")
    args = parser.parse_args()

    web_root = Path(args.web).resolve()
    results = Path(args.results).resolve()
    results.mkdir(parents=True, exist_ok=True)
    if not (web_root / "manifest.json").is_file():
        raise SystemExit("找不到 manifest.json，先跑 web/gen_modules.py")

    scheme = "https" if args.channel == "cloudflare" else "http"
    public_host = args.public_host or args.bind
    extra_names = [socket.gethostname(), os.environ.get("COMPUTERNAME", ""),
                   args.bind, public_host]
    log_path = results / ("phone-%s-server.log" % args.channel)
    state = ProbeState(web_root, results, args.channel, extra_names, log_path)

    httpd = None
    tunnel = None
    if args.channel == "cloudflare":
        if not args.cloudflared:
            raise SystemExit("cloudflare 通道必须用 --cloudflared 传入 cloudflared.exe 路径")
        if args.public_host:
            raise SystemExit("cloudflare 通道的域名由隧道给出，不要传 --public-host")
    else:
        if args.bind in ("0.0.0.0", "::"):
            state.log("注意：--bind 用了通配地址，样机仍只认白名单 Host")

    handler = make_handler(state)
    try:
        httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    except OSError as exc:
        raise SystemExit("绑定 %s:%d 失败：%s" % (args.bind, args.port, exc))
    httpd.daemon_threads = True
    httpd.timeout = 5.0

    if args.channel == "cloudflare":
        tunnel_proc, tunnel_host = start_cloudflared(args.cloudflared, args.port, state)
        tunnel = tunnel_proc
        public_host = tunnel_host
        httpd.allowed_hosts = allowed_hosts(args.bind, public_host, "https")
        httpd.public_url = "https://%s/" % public_host
    else:
        httpd.allowed_hosts = allowed_hosts(args.bind, public_host, "http")
        httpd.public_url = "http://%s:%d/" % (public_host, args.port)
    state.bind_host = args.bind
    state.public_host = public_host

    thread = threading.Thread(target=httpd.serve_forever, name="probe-http", daemon=True)
    thread.start()
    state.log("样机服务已启动，通道=%s，端口=%d，允许的 Host 数量=%d" % (
        args.channel, args.port, len(httpd.allowed_hosts)))
    # 控制台给出可直接照抄的地址；日志文件里保留脱敏版本
    _say("手机打开：%s" % httpd.public_url)
    state.log("手机打开（日志已脱敏）：%s" % httpd.public_url)
    state.log("预计 %d 秒后自动退出" % args.duration)

    stop = threading.Event()

    def shutdown(reason: str) -> None:
        if stop.is_set():
            return
        stop.set()
        state.log("停止：%s" % reason)
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception as exc:  # noqa: BLE001 - 关闭尽力而为
            state.log("关闭服务时异常：%s" % type(exc).__name__)
        if tunnel is not None:
            try:
                tunnel.terminate()
            except Exception:  # noqa: BLE001
                pass
        time.sleep(0.5)
        # 15 分钟内可能会重复 bind，这里只报结果，不再占端口
        released = port_released(args.bind, args.port)
        state.log("端口已释放=%s（%s:%d）" % (released, args.bind, args.port))

    threading.Timer(max(5, args.duration), shutdown, args=("到时自动退出",)).start()

    if args.selfdrive:
        return selfdrive(state, httpd, args, stop, shutdown)

    try:
        while not stop.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown("用户中止")
    return 0


def selfdrive(state: ProbeState, httpd, args, stop: threading.Event, shutdown) -> int:
    """本机源码态试跑：WebView2 当手机浏览器，依次加载探针并等上报。

    结束时直接 os._exit：pywebview 在部分环境从线程里关窗会卡住 GUI 线程，
    样机只需要数据，硬退出比优雅退出可靠。
    """
    import webview

    base = "http://127.0.0.1:%d" % args.port
    steps = [
        {"url": "/h2/page.html", "need": 1},
        {"url": "/h11/", "need": 0, "collect": True},
        {"url": "/h9/legacy/?run=1", "need": 12},
    ]
    window = webview.create_window("ESM verify 自测", base + steps[0]["url"],
                                   width=420, height=720)

    def wait_reports(baseline: int, need: int, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline and not stop.is_set():
            with state.lock:
                got = len(state.reports) - baseline
            if got >= need:
                return True
            time.sleep(0.2)
        return False

    def driver() -> None:
        try:
            time.sleep(3.0)
            for idx, step in enumerate(steps):
                with state.lock:
                    baseline = len(state.reports)
                if idx > 0:
                    window.load_url(base + step["url"])
                if step.get("collect"):
                    # H11 在本机 WebView2 里走不了 POST（window.pywebview 存在，
                    # 兜底分支会跳过上报），所以由驱动方读快照并写盘
                    time.sleep(7.5)
                    payload = json.loads(
                        window.evaluate_js("JSON.stringify(window.__collect())"))
                    payload["page"] = "h11"
                    state.save_report(payload, "127.0.0.1:%d" % args.port,
                                      payload.get("ua") or "")
                    ok = bool((payload.get("fallback") or {}).get("shown"))
                else:
                    ok = wait_reports(baseline, step["need"],
                                      60 if idx < 2 else 180)
                state.log("自测 %s：%s" % (step["url"], "通过" if ok else "不齐"))
            state.log("自测完成，汇总=%s" % json.dumps(state.summary(),
                                                      ensure_ascii=False))
        finally:
            # E7：退出前关服务，用 port_released() 写「端口已释放=True/False」，不再留给人工确认
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception as exc:  # noqa: BLE001 - 关闭尽力而为
                state.log("关闭服务时异常：%s" % type(exc).__name__)
            time.sleep(0.5)
            released = port_released(args.bind, args.port)
            state.log("端口已释放=%s（%s:%d）" % (released, args.bind, args.port))
            state.log("自测结束，硬退出")
            sys.stdout.flush()
            os._exit(0)

    threading.Thread(target=driver, name="selfdrive", daemon=True).start()
    threading.Timer(300, lambda: os._exit(2)).start()
    try:
        webview.start(debug=False)
    except Exception as exc:  # noqa: BLE001
        state.log("WebView2 启动失败：%s" % type(exc).__name__)
        shutdown("自测失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
