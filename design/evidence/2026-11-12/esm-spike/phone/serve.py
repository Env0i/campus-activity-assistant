# -*- coding: utf-8 -*-
"""phone spike —— 手机页安全头下的 ES Modules 加载验证。

起一个和 local/infrastructure/phone_http.py 安全头一致的标准库 HTTP server，
用 pywebview 加载含 ES Modules 的页面，收集证据。

前置 desktop-spike 的关键发现（已承接）：
  - pywebview 6.2.1 内置 http_server 有 Bottle bug，必须自己起标准库 server
  - pywebview 6.x js_api 返回 Promise，Python 端能正常收到 JS 传来的参数
  - pywebview.start() 必须在主线程调用，不能放子线程

只在 design/evidence/2026-11-12/esm-spike/phone/ 目录下产生文件，
不碰 local/、server/ 下任何文件。
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import webview

# ============================================================
# 安全头（从 local/infrastructure/phone_http.py 原样抄）
# ============================================================
SECURITY_HEADERS = (
    ("Content-Security-Policy",
     "default-src 'self'; script-src 'self'; style-src 'self'; "
     "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
RESULT_JSON = HERE / "phone-result.json"
SUMMARY_TXT = HERE / "summary.txt"
RUN_LOG = HERE / "run.log"


# ============================================================
# Handler —— SimpleHTTPRequestHandler + 安全头 + .mjs MIME
# ============================================================
class _PhoneSpikeHandler(SimpleHTTPRequestHandler):
    """文件根 = WEB_DIR，响应带 phone_http.py 的全部安全头。"""

    server_version = "phone-spike"
    sys_version = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt, *args):  # noqa: D401
        return

    def end_headers(self):  # noqa: N802 - 基类命名
        for key, value in SECURITY_HEADERS:
            self.send_header(key, value)
        super().end_headers()

    def guess_type(self, path):  # noqa: N802 - 基类命名
        if path.endswith(".mjs"):
            return "text/javascript; charset=utf-8"
        return super().guess_type(path)


# ============================================================
# js_api —— Python 端回调桥
# ============================================================
_win_ref = None
_finalize_fired = [False]


class _SpikeApi:
    """JS 端通过 window.pywebview.api 调 finalize(snapshot)。"""

    def __init__(self):
        self.snapshot = None
        self.pywebview_ready_fired = False

    def finalize(self, data):
        """JS 端主动请求 finalize；destroy() 触发主线程退出 webview.start()。"""
        global _finalize_fired
        if _finalize_fired[0]:
            return "already-finalized"
        _finalize_fired[0] = True

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {"raw": data}
        self.snapshot = data

        if _win_ref is not None:
            try:
                _win_ref.destroy()
            except Exception as e:
                print(f"[js_api.finalize] destroy: {e}", file=sys.stderr)
        return "ok"


# ============================================================
# LAN 连通性 / 端口释放 —— 独立函数
# ============================================================
def _find_lan_ip() -> str:
    """找一个不是 127.* 的本机 IP。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            name = socket.gethostname()
            try:
                ips = socket.gethostbyname_ex(name)[2] or []
            except Exception:
                ips = []
            for ip in ips:
                if not ip.startswith("127."):
                    return ip
            return ""
    finally:
        try:
            s.close()
        except Exception:
            pass


def _lan_connect_test(lan_ip: str, port: int) -> int:
    """socket.connect_ex 尝试连本机局域网 IP:port；0=通，非 0=不通。"""
    if not lan_ip:
        return -1
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        rc = s.connect_ex((lan_ip, port))
        s.close()
        return rc
    except Exception:
        return -1


def _bind_test(host: str, port: int) -> bool:
    """测试 shutdown + server_close 后端口能不能重新 bind。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.close()
        return True
    except OSError:
        return False


# ============================================================
# main
# ============================================================
def main():
    log_lines = []

    def log(msg: str) -> None:
        line = msg
        print(line, flush=True)
        log_lines.append(line)

    log(f"[phone-spike] web_dir = {WEB_DIR}")
    log(f"[phone-spike] web_dir exists = {WEB_DIR.is_dir()}")

    # ---- Phase 1: 起标准库 HTTP server ----
    server = ThreadingHTTPServer(("127.0.0.1", 0), _PhoneSpikeHandler)
    server.daemon_threads = True
    bind_host, bind_port = server.server_address
    httpd_thread = threading.Thread(target=server.serve_forever, name="phone-spike-httpd",
                                   daemon=True)
    httpd_thread.start()
    log(f"[phone-spike] httpd listening on {bind_host}:{bind_port}")

    # ---- Phase 2: urllib 先 GET 一次抓实际返回头 ----
    http_headers_actual = {}
    try:
        url = f"http://127.0.0.1:{bind_port}/main.mjs"
        req = urllib.request.Request(url, headers={"User-Agent": "phone-spike"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            status = resp.status
            http_headers_actual = {k: v for k, v in resp.headers.items()}
            log(f"[phone-spike] urllib GET /main.mjs → {status}")
            for k, v in http_headers_actual.items():
                log(f"[phone-spike]   header: {k}: {v}")
    except Exception as e:
        log(f"[phone-spike] urllib GET failed: {e}")

    csp_present = any(
        k.lower() == "content-security-policy" for k in http_headers_actual
    )
    nosniff_present = any(
        k.lower() == "x-content-type-options"
        and http_headers_actual[k].lower() == "nosniff"
        for k in http_headers_actual
    )
    log(f"[phone-spike] CSP present in headers = {csp_present}")
    log(f"[phone-spike] X-Content-Type-Options: nosniff = {nosniff_present}")

    # ---- Phase 3: pywebview 加载（主线程） ----
    global _win_ref, _finalize_fired
    _finalize_fired[0] = False
    api = _SpikeApi()

    def _run_pywebview():
        global _win_ref
        url = f"http://127.0.0.1:{bind_port}/"
        log(f"[phone-spike] pywebview opening {url}")
        win = webview.create_window(
            "ESM Phone Spike",
            url=url,
            js_api=api,
            width=400,
            height=600,
            resizable=False,
        )
        _win_ref = win

        def on_loaded():
            api.pywebview_ready_fired = True
            log("[phone-spike] pywebview window loaded")

        win.events.loaded += on_loaded

        # 4 秒定时器兜底 finalize —— 前端没主动调 finalize 的话
        def timer_fallback():
            global _finalize_fired
            if _finalize_fired[0]:
                return
            _finalize_fired[0] = True
            log("[phone-spike] python-side finalize timeout fired")
            try:
                snap_js = (
                    'JSON.stringify({'
                    'runOrder: window.runOrder || [],'
                    'errors: window._spikeErrors || []'
                    '})'
                )
                api.snapshot = json.loads(win.evaluate_js(snap_js))
            except Exception as e:
                api.snapshot = {"timer_error": str(e)}
            if _win_ref is not None:
                try:
                    _win_ref.destroy()
                except Exception as e:
                    log(f"[phone-spike] timer destroy error: {e}")

        threading.Timer(4.0, timer_fallback).start()

        # 阻塞直到 destroy() 被 js_api.finalize 或 timer_fallback 触发
        try:
            webview.start(debug=False)
        except SystemExit:
            pass

    # 主线程直接调 pywebview.start() —— desktop-spike 证明这是必须的
    try:
        _run_pywebview()
    finally:
        log("[phone-spike] webview.start() returned")

    # ---- Phase 4: 收集快照 ----
    js_snapshot = api.snapshot or {}
    run_order = js_snapshot.get("runOrder", [])
    log(f"[phone-spike] pywebview_ready_fired = {api.pywebview_ready_fired}")
    log(f"[phone-spike] runOrder = {run_order}")
    log(f"[phone-spike] legacy-top in runOrder = {'legacy-top' in run_order}")
    log(f"[phone-spike] leaf-top in runOrder   = {'leaf-top' in run_order}")
    log(f"[phone-spike] chain-top in runOrder  = {'chain-top' in run_order}")
    log(f"[phone-spike] main-top in runOrder   = {'main-top' in run_order}")

    # ---- Phase 5: 关 server、测端口释放 ----
    log("[phone-spike] shutting down HTTP server")
    try:
        server.shutdown()
    except Exception as e:
        log(f"[phone-spike] server.shutdown() exception: {e}")
    time.sleep(1.0)
    try:
        server.server_close()
    except Exception as e:
        log(f"[phone-spike] server.server_close() exception: {e}")

    time.sleep(1.0)
    port_released = _bind_test(bind_host, bind_port)
    log(f"[phone-spike] port {bind_host}:{bind_port} re-bind test = {port_released}")

    # ---- Phase 6: LAN 连通性 ----
    lan_ip = _find_lan_ip()
    log(f"[phone-spike] LAN IP = {lan_ip or '(none)'}")
    lan_rc = _lan_connect_test(lan_ip, bind_port)
    log(f"[phone-spike] LAN connect test rc = {lan_rc} (0=通, 非0=不通)")

    # ---- Phase 7: 组装结果 ----
    modules_executed = run_order
    run_order_set = set(run_order) if isinstance(run_order, list) else set()
    leaf_ok = "leaf-top" in run_order_set
    chain_ok = "chain-top" in run_order_set
    main_ok = "main-top" in run_order_set
    legacy_ok = "legacy-top" in run_order_set
    all_modules_ran = leaf_ok and chain_ok and main_ok

    phone_result = {
        "http_headers_actual": http_headers_actual,
        "csp_present": csp_present,
        "nosniff_present": nosniff_present,
        "modules_executed": modules_executed,
        "module_error": js_snapshot.get("errors") or None,
        "legacy_executed": legacy_ok,
        "all_modules_executed": all_modules_ran,
        "leaf_executed": leaf_ok,
        "chain_executed": chain_ok,
        "main_executed": main_ok,
        "lan_connect_result": lan_rc,
        "lan_ip": lan_ip,
        "port_released": port_released,
        "server_bind_host": bind_host,
        "server_bind_port": bind_port,
        "pywebview_ready_fired": api.pywebview_ready_fired,
        "js_snapshot": js_snapshot,
    }

    RESULT_JSON.write_text(
        json.dumps(phone_result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    log(f"[phone-spike] wrote {RESULT_JSON}")

    RUN_LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    log(f"[phone-spike] wrote {RUN_LOG}")

    # ---- Phase 8: 写 summary.txt ----
    if csp_present and nosniff_present and all_modules_ran and legacy_ok:
        v5_conclusion = "可行（CSP script-src 'self' + nosniff 下 ES Modules 完整加载）"
    elif csp_present and nosniff_present and not all_modules_ran:
        v5_conclusion = "不可行（安全头已下发但 ES Modules 未完整加载）"
    elif not csp_present or not nosniff_present:
        v5_conclusion = "有条件可行（安全头未正确下发，需先修复 server）"
    else:
        v5_conclusion = "未知（pywebview bridge 未就绪，无法判断）"

    L = []
    L.append("=" * 60)
    L.append("ESM Phone Spike —— 手机页安全头下的模块加载结论")
    L.append("日期：2026-11-12")
    L.append("只回答 V5：phone_http.py 安全头 + ES Modules")
    L.append("=" * 60)
    L.append("")
    L.append(f"V5 结论: {v5_conclusion}")
    L.append("")
    L.append("关键证据:")
    L.append(f"  - server: {bind_host}:{bind_port}（自己起的标准库 http.server）")
    L.append(f"  - CSP 实际下发: {csp_present}")
    L.append(f"  - X-Content-Type-Options: nosniff 实际下发: {nosniff_present}")
    if http_headers_actual:
        L.append(f"  - CSP 值: {http_headers_actual.get('Content-Security-Policy', '(missing)')}")
    L.append(f"  - pywebview window loaded: {api.pywebview_ready_fired}")
    L.append(f"  - legacy.js 顶层执行: {legacy_ok}")
    L.append(f"  - leaf.mjs 顶层执行: {leaf_ok}")
    L.append(f"  - chain.mjs 顶层执行: {chain_ok}")
    L.append(f"  - main.mjs 顶层执行: {main_ok}")
    L.append(f"  - runOrder = {run_order}")
    L.append(f"  - LAN IP = {lan_ip or '(none)'}")
    L.append(f"  - LAN connect rc = {lan_rc} (0=通, 非0=不通)")
    L.append(f"  - 端口释放 = {port_released}")
    if js_snapshot.get("errors"):
        L.append(f"  - 前端错误 = {js_snapshot['errors']}")

    L.append("")
    L.append("=" * 60)
    L.append("PHONE_STATIC 白名单扩展方案")
    L.append("=" * 60)
    L.append("")
    L.append("现状：phone_http.py 的 PHONE_STATIC 是手工登记的路径白名单：")
    L.append("  /, /index.html, /styles.css, /app.js, /favicon.ico,")
    L.append("  /apple-touch-icon.png")
    L.append("")
    L.append("如果前端改用 ES Modules（import 链 main.mjs → chain.mjs → leaf.mjs），")
    L.append("PHONE_STATIC 需要新增的静态资源路径：")
    L.append("")
    L.append("  方式一：手工登记（当前方案的自然延伸）")
    L.append("    /main.mjs → main.mjs, text/javascript; charset=utf-8")
    L.append("    /chain.mjs → chain.mjs, text/javascript; charset=utf-8")
    L.append("    /leaf.mjs → leaf.mjs, text/javascript; charset=utf-8")
    L.append("    后续每新增 .mjs 文件（含共享工具模块如 /utils.mjs, /state.mjs 等）都")
    L.append("    要在 PHONE_STATIC 加一条映射。")
    L.append("")
    L.append("  方式二：按扩展名放行（更灵活但放弃部分严格性）")
    L.append("    在 do_GET 里加一个 if path.endswith('.mjs') 分支，")
    L.append("    直接从 ui_dir 读文件（需额外防止路径穿越——仍然只允许 .mjs 后缀，")
    L.append("    且必须 resolve() 后确认在 ui_dir 内）。")
    L.append("    类似地，.js 文件（旧普通脚本）也可以走同一分支。")
    L.append("")
    L.append("  方式三：混合（推荐）")
    L.append("    保留 PHONE_STATIC 映射用于 index.html / favicon 这种精确路径；")
    L.append("    新增一个 if path.endswith(('.mjs', '.js', '.css', '.svg')) 分支")
    L.append("    放行前端资产目录内的文件（resolve() + 路径边界校验）。")
    L.append("    好处：import 链里出现任何新 .mjs 都能被自动发现，不用改 Python。")
    L.append("    风险：如果前端打包产物里混入敏感文件（极不可能），需要额外检查。")
    L.append("")
    L.append("自动发现的边界条件：")
    L.append("  - import 语句里的模块路径是相对于当前 .mjs 文件的，浏览器会自动发起")
    L.append("    HTTP GET；server 只要允许 .mjs 后缀的文件就够了，不需要 Python 去解析")
    L.append("    ES import 语句——浏览器自己负责。")
    L.append("  - 路径穿越防护仍然不能松：resolve() 后必须确认在 ui_dir.resolve() 下。")

    SUMMARY_TXT.write_text("\n".join(L) + "\n", encoding="utf-8")
    log(f"[phone-spike] wrote {SUMMARY_TXT}")
    log("[phone-spike] done")

    sys.exit(0)


if __name__ == "__main__":
    main()
