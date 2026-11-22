# -*- coding: utf-8 -*-
"""手机页连接复用对照测速服务：固定 no-store 缓存头，只切换连接关闭或复用。

复用 2026-11-12 的 serve_probe.py 与 redact.py，提供两种连接设置：
  - close：处理器使用 HTTP/1.0，每个请求回复后立即断开连接（与原测速服务及产品手机服务一致）
  - keepalive：处理器使用 HTTP/1.1，带准确 Content-Length 保持并复用同一条 TCP 连接

用法：
  python serve_keepalive.py --self-check
  python serve_keepalive.py --arm close --selfdrive
  python serve_keepalive.py --arm keepalive --selfdrive
  python serve_keepalive.py --channel tailscale --arm close --bind <Tailscale 地址> --public-host <MagicDNS 名> --port 8765
  python serve_keepalive.py --channel cloudflare --arm keepalive --cloudflared <cloudflared.exe 路径> --port 8765

@author Author
"""
from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBE_ROOT = HERE.parent
REPO_ROOT = PROBE_ROOT.parents[3]
ESM_VERIFY_ROOT = REPO_ROOT / "design" / "evidence" / "2026-11-12" / "esm-verify"
DEFAULT_WEB = ESM_VERIFY_ROOT / "web" / "generated"
DEFAULT_RESULTS = PROBE_ROOT / "results"
SELFCHECK_PATHS = (
    "/",
    "/common/base.js",
    "/common/runner.js",
    "/h9/legacy/index.html",
    "/h9/flat/index.html",
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载模块：%s" % path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


redact = _load_module("redact", ESM_VERIFY_ROOT / "tools" / "redact.py")
serve_probe = _load_module("serve_probe", ESM_VERIFY_ROOT / "phone" / "serve_probe.py")


class KeepaliveProbeState(serve_probe.ProbeState):
    """在 ProbeState 基础上增加组别标记与连接级请求日志。"""

    def __init__(self, web_root: Path, results: Path, channel: str, arm: str,
                 extra_names: list[str], log_path: Path, req_log_path: Path):
        super().__init__(web_root, results, channel, extra_names, log_path)
        if log_path.is_file():
            self._log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.arm = arm
        self.req_log_path = req_log_path
        self.conn_seq = 0
        self.request_records: list[dict] = []

    def next_name(self, label: str) -> str:
        with self.lock:
            idx = self.seq.get(label, 0) + 1
            while (self.results / ("phone-%s-%s-%s-%02d.json" % (
                self.channel, self.arm, label, idx
            ))).exists():
                idx += 1
            self.seq[label] = idx
            return "phone-%s-%s-%s-%02d.json" % (
                self.channel, self.arm, label, idx
            )

    def next_connection(self, client_port: int) -> int:
        with self.lock:
            self.conn_seq += 1
            return self.conn_seq

    def record_request(self, *, ts_ms: int, method: str, path: str,
                       status: int, num_bytes: int, conn_id: int,
                       client_port: int, conn_req_seq: int) -> None:
        entry = {
            "ts_ms": int(ts_ms),
            "channel": self.channel,
            "arm": self.arm,
            "method": str(method),
            "path": str(path),
            "status": int(status),
            "bytes": int(num_bytes),
            "conn_id": int(conn_id),
            "client_port": int(client_port),
            "conn_req_seq": int(conn_req_seq),
        }
        clean = redact.redact_obj(entry, self.extra_names)
        line = json.dumps(clean, ensure_ascii=False)
        residual = redact.find_residual(line, self.extra_names)
        if residual:
            self.log("请求日志脱敏自检发现残留，已停下不写盘：%s" % ", ".join(sorted(set(residual))[:5]))
            raise RuntimeError("redaction residual in request log")
        with self.lock:
            self.request_records.append(clean)
            with open(self.req_log_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(line + "\n")

    def save_report(self, payload: dict, host_header: str, ua: str) -> Path:
        label = serve_probe.browser_label(ua)
        name = self.next_name(label)
        with self.lock:
            req_count = len(self.request_records)
        record = {
            "channel": self.channel,
            "arm": self.arm,
            "received_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "server": {
                "bind_host": self.bind_host,
                "public_host": self.public_host,
                "host_header": host_header,
                "scheme": "https" if self.channel == "cloudflare" else "http",
                "request_log": self.req_log_path.name,
                "request_count_so_far": req_count,
            },
            "client": {"browser": label, "ua": ua},
            "payload": payload,
        }
        record = redact.redact_obj(record, self.extra_names)
        residual = redact.find_residual(json.dumps(record, ensure_ascii=False), self.extra_names)
        if residual:
            self.log("脱敏自检发现残留，已停下不写盘：%s" % ", ".join(sorted(set(residual))[:5]))
            raise RuntimeError("redaction residual")
        path = self.results / name
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        with self.lock:
            self.reports.append(record)
        self.log("收到上报 → %s（arm=%s page=%s form=%s run=%s）" % (
            name, self.arm, payload.get("page"), payload.get("form"), payload.get("run")))
        return path


def make_keepalive_handler(state: KeepaliveProbeState, arm: str):
    base_cls = serve_probe.make_handler(state)

    class KeepaliveHandler(base_cls):
        protocol_version = "HTTP/1.1" if arm == "keepalive" else "HTTP/1.0"

        def setup(self) -> None:
            super().setup()
            addr = getattr(self, "client_address", None)
            port = int(addr[1]) if isinstance(addr, tuple) and len(addr) > 1 else 0
            self._client_port = port
            self._conn_id = state.next_connection(port)
            self._conn_req_seq = 0

        def handle_one_request(self) -> None:
            self._req_ts_ms = int(time.time() * 1000)
            super().handle_one_request()

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            if code >= 400:
                self.close_connection = True
            self._conn_req_seq = getattr(self, "_conn_req_seq", 0) + 1
            ts_ms = getattr(self, "_req_ts_ms", None) or int(time.time() * 1000)
            super()._send(code, body, content_type)
            state.record_request(
                ts_ms=ts_ms,
                method=str(getattr(self, "command", "") or ""),
                path=str(getattr(self, "path", "") or ""),
                status=int(code),
                num_bytes=len(body),
                conn_id=getattr(self, "_conn_id", 0),
                client_port=getattr(self, "_client_port", 0),
                conn_req_seq=self._conn_req_seq,
            )

    return KeepaliveHandler


def _exercise_client_requests(port: int, arm: str) -> list[int]:
    local_ports: list[int] = []
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        for idx, path in enumerate(SELFCHECK_PATHS):
            if arm == "close" and idx > 0 and conn.sock is not None:
                raise AssertionError("close 组在第 %d 个请求前旧连接仍未关闭" % (idx + 1))
            conn.request("GET", path)
            if conn.sock is None:
                raise AssertionError("发送请求后 conn.sock 为空")
            local_ports.append(int(conn.sock.getsockname()[1]))
            resp = conn.getresponse()
            body = resp.read()
            raw_len = resp.getheader("Content-Length")
            if resp.status != 200 or raw_len is None or int(raw_len) != len(body) or len(body) <= 0:
                raise AssertionError("回复异常 path=%s status=%s len=%s/%d" % (
                    path, resp.status, raw_len, len(body)))
            if arm == "keepalive" and (resp.will_close or conn.sock is None):
                raise AssertionError("keepalive 组在第 %d 个请求后断开了连接" % (idx + 1))
            if arm == "close" and (not resp.will_close or conn.sock is not None):
                raise AssertionError("close 组在第 %d 个请求后未关闭连接" % (idx + 1))
    finally:
        conn.close()
    return local_ports


def _self_check_arm(web_root: Path, tmp_dir: Path, arm: str) -> dict:
    log_path = tmp_dir / ("selfcheck-%s.log" % arm)
    req_path = tmp_dir / ("requests-tailscale-%s-selfcheck.jsonl" % arm)
    state = KeepaliveProbeState(web_root, tmp_dir, "tailscale", arm, [], log_path, req_path)
    handler = make_keepalive_handler(state, arm)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = int(httpd.server_address[1])
    httpd.allowed_hosts = serve_probe.allowed_hosts("127.0.0.1", "127.0.0.1", "http")
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        local_ports = _exercise_client_requests(port, arm)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2.0)
    released = serve_probe.port_released("127.0.0.1", port)
    conn_ids = [r["conn_id"] for r in state.request_records]
    req_seqs = [r["conn_req_seq"] for r in state.request_records]
    if arm == "keepalive" and (
        conn_ids != [1, 1, 1, 1, 1]
        or req_seqs != [1, 2, 3, 4, 5]
        or len(set(local_ports)) != 1
    ):
        raise AssertionError("keepalive 组连接记录不符合预期：%s / %s" % (conn_ids, req_seqs))
    if arm == "close" and (
        conn_ids != [1, 2, 3, 4, 5]
        or req_seqs != [1, 1, 1, 1, 1]
        or len(set(local_ports)) < 2
    ):
        raise AssertionError("close 组连接记录不符合预期：%s / %s" % (conn_ids, req_seqs))
    if not released:
        raise AssertionError("%s 组关闭后端口未释放" % arm)
    return {
        "arm": arm,
        "requests": len(state.request_records),
        "distinct_connections": len(set(conn_ids)),
        "conn_ids": conn_ids,
        "conn_req_seqs": req_seqs,
        "content_length_verified": True,
        "port_released": released,
    }


def run_self_check(web_root: Path) -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="keepalive-selfcheck-") as tmp:
            tmp_dir = Path(tmp)
            close_res = _self_check_arm(web_root, tmp_dir, "close")
            keep_res = _self_check_arm(web_root, tmp_dir, "keepalive")
        summary = {"ok": True, "close": close_res, "keepalive": keep_res}
        serve_probe._say("SELF-CHECK PASS " + json.dumps(summary, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        serve_probe._say("SELF-CHECK FAIL %s: %s" % (type(exc).__name__, exc))
        return 1


def run_selfdrive(state: KeepaliveProbeState, httpd, args, stop: threading.Event,
                  shutdown) -> int:
    """本机 WebView2 跑一轮完整 H9 轮转（四种形态各 3 轮 = 12 份上报）。"""
    import webview

    start_url = "http://127.0.0.1:%d/h9/legacy/?run=1" % args.port
    window = webview.create_window("Keepalive probe 自测 (%s)" % args.arm,
                                   start_url, width=420, height=720)

    def driver() -> None:
        try:
            deadline = time.time() + 180.0
            ok = False
            while time.time() < deadline and not stop.is_set():
                with state.lock:
                    if len(state.reports) >= 12:
                        ok = True
                        break
                time.sleep(0.2)
            state.log("自测 /h9/legacy/?run=1（arm=%s）：%s（收到 %d 份上报，%d 条请求）" % (
                args.arm, "通过" if ok else "不齐",
                len(state.reports), len(state.request_records)))
            state.log("自测完成，汇总=%s" % json.dumps(state.summary(), ensure_ascii=False))
        finally:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception as exc:  # noqa: BLE001
                state.log("关闭服务时异常：%s" % type(exc).__name__)
            time.sleep(0.5)
            released = serve_probe.port_released(args.bind, args.port)
            state.log("端口已释放=%s（%s:%d）" % (released, args.bind, args.port))
            state.log("自测结束，硬退出")
            sys.stdout.flush()
            os._exit(0 if len(state.reports) >= 12 else 1)

    _ = window
    threading.Thread(target=driver, name="selfdrive", daemon=True).start()
    threading.Timer(300, lambda: os._exit(2)).start()
    try:
        webview.start(debug=False)
    except Exception as exc:  # noqa: BLE001
        state.log("WebView2 启动失败：%s" % type(exc).__name__)
        shutdown("自测失败")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["tailscale", "cloudflare"], default="tailscale")
    parser.add_argument("--arm", choices=["close", "keepalive"], default="")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-host", default="")
    parser.add_argument("--cloudflared", default="")
    parser.add_argument("--web", default=str(DEFAULT_WEB))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--duration", type=int, default=serve_probe.DEFAULT_DURATION)
    parser.add_argument("--selfdrive", action="store_true",
                        help="本机 WebView2 跑一轮四种形态各 3 轮")
    parser.add_argument("--self-check", action="store_true",
                        help="离线自检 close 与 keepalive 两组的连接行为与 Content-Length")
    return parser


def _wait_and_drain_tunnel(tunnel, state: KeepaliveProbeState) -> None:
    """等待 cloudflared 完成边缘连接注册并持续排空 stdout 管道，避免 1033 或管道阻塞。"""
    if tunnel is None or tunnel.stdout is None:
        return
    deadline = time.time() + 30.0
    registered = False
    while time.time() < deadline:
        line = tunnel.stdout.readline()
        if not line:
            if tunnel.poll() is not None:
                break
            time.sleep(0.1)
            continue
        if "Registered tunnel connection" in line:
            registered = True
            break
    state.log("隧道边缘连接注册=%s" % registered)

    def _drain() -> None:
        try:
            for _ in tunnel.stdout:
                pass
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_drain, name="cloudflared-drain", daemon=True).start()


def _start_server_and_tunnel(args, state: KeepaliveProbeState):
    if args.channel == "cloudflare":
        if not args.cloudflared:
            raise SystemExit("cloudflare 通道必须用 --cloudflared 传入 cloudflared.exe 路径")
        if args.public_host:
            raise SystemExit("cloudflare 通道的域名由隧道给出，不要传 --public-host")
    elif args.bind in ("0.0.0.0", "::"):
        state.log("注意：--bind 用了通配地址，样机仍只认白名单 Host")

    handler = make_keepalive_handler(state, args.arm)
    try:
        httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    except OSError as exc:
        raise SystemExit("绑定 %s:%d 失败：%s" % (args.bind, args.port, exc))
    httpd.daemon_threads = True
    httpd.timeout = 5.0
    tunnel = None
    public_host = args.public_host or args.bind
    if args.channel == "cloudflare":
        tunnel, public_host = serve_probe.start_cloudflared(args.cloudflared, args.port, state)
        _wait_and_drain_tunnel(tunnel, state)
        if public_host and public_host not in state.extra_names:
            state.extra_names.append(public_host)
        httpd.allowed_hosts = serve_probe.allowed_hosts(args.bind, public_host, "https")
        httpd.public_url = "https://%s/" % public_host
    else:
        httpd.allowed_hosts = serve_probe.allowed_hosts(args.bind, public_host, "http")
        httpd.public_url = "http://%s:%d/" % (public_host, args.port)
    state.bind_host = args.bind
    state.public_host = public_host
    return httpd, tunnel


def _make_shutdown(state: KeepaliveProbeState, httpd, tunnel, args,
                   stop: threading.Event):
    def shutdown(reason: str) -> None:
        if stop.is_set():
            return
        stop.set()
        state.log("停止：%s" % reason)
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception as exc:  # noqa: BLE001
            state.log("关闭服务时异常：%s" % type(exc).__name__)
        if tunnel is not None:
            try:
                tunnel.terminate()
            except Exception:  # noqa: BLE001
                pass
        time.sleep(0.5)
        released = serve_probe.port_released(args.bind, args.port)
        state.log("端口已释放=%s（%s:%d）" % (released, args.bind, args.port))

    return shutdown


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001
        pass
    args = _build_parser().parse_args()
    web_root = Path(args.web).resolve()
    if not (web_root / "manifest.json").is_file():
        raise SystemExit("找不到 manifest.json：%s" % (web_root / "manifest.json"))
    if args.self_check:
        return run_self_check(web_root)
    if args.arm not in ("close", "keepalive"):
        raise SystemExit("必须通过 --arm 指定 close 或 keepalive")

    results = Path(args.results).resolve()
    results.mkdir(parents=True, exist_ok=True)
    started_tag = time.strftime("%Y%m%d-%H%M%S")
    public_host = args.public_host or args.bind
    extra_names = [socket.gethostname(), os.environ.get("COMPUTERNAME", ""),
                   args.bind, public_host]
    log_path = results / ("phone-%s-%s-server.log" % (args.channel, args.arm))
    req_log_path = results / ("requests-%s-%s-%s.jsonl" % (
        args.channel, args.arm, started_tag))
    state = KeepaliveProbeState(web_root, results, args.channel, args.arm,
                                extra_names, log_path, req_log_path)
    httpd, tunnel = _start_server_and_tunnel(args, state)
    threading.Thread(target=httpd.serve_forever, name="probe-http", daemon=True).start()
    state.log("服务已启动，通道=%s，组别=%s，端口=%d，请求日志=%s" % (
        args.channel, args.arm, args.port, req_log_path.name))
    serve_probe._say("手机打开：%s" % httpd.public_url)
    serve_probe._say("直接进四形态轮转：%sh9/legacy/?run=1" % httpd.public_url)
    state.log("手机打开（日志已脱敏）：%s" % httpd.public_url)

    stop = threading.Event()
    shutdown = _make_shutdown(state, httpd, tunnel, args, stop)
    threading.Timer(max(5, args.duration), shutdown, args=("到时自动退出",)).start()
    if args.selfdrive:
        return run_selfdrive(state, httpd, args, stop, shutdown)
    try:
        while not stop.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown("用户中止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
