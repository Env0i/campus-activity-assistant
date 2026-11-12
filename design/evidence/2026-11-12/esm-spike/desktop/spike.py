#!/usr/bin/env python3
"""
ESM Feasibility Spike —— 桌面窗口加载、桥接与新旧混用
--------------------------------------------------------
两种运行模式：

  主控模式（无参数）
    顺序启动 A → B → C → D 四个子进程，每个子进程跑一个场景，
    stdout/stderr 重定向到 scene-{X}.log。最后汇总 comprehensive-result.json
    和 summary.txt。

  子进程模式（--scene A|B|C|D）
    创建一个 pywebview 窗口，按场景跑加载/桥接/互调检查，前端和 Python 互相
    收集数据，写入 result-{X}.json 后自动销毁窗口退出。

样机只回答 V1–V4 四个问题：
  V1 场景 A（file://）和 B（http_server）模块脚本能不能执行
  V2 场景 C 桥接调用是否双向畅通
  V3 场景 D 新旧脚本混用的执行顺序和互调
  V4 HTTP 服务监听地址、退出后端口释放、是否仅限本机

注：pywebview 6.2.1 内置 http_server 有 Bottle 签名不匹配的 bug
    （asset() missing 1 required positional argument: 'file'），
    所以 B/C/D 三个场景改用 Python 标准库 http.server，
    pywebview.create_window 传 http://localhost:{port}。
"""

import argparse
import functools
import http.server
import json
import os
import re
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

SPIKE_ROOT = Path(__file__).resolve().parent
WEB_DIR = SPIKE_ROOT / "web"

SCENES = {
    "A": {"name": "file:// 直接加载，无 http_server", "http_server": False},
    "B": {"name": "http_server=True，仅加载检查", "http_server": True},
    "C": {"name": "桥接测试（只在 http_server 下）", "http_server": True},
    "D": {"name": "新旧混用（http_server=True）", "http_server": True},
}


# =====================================================================
# 自己起的 HTTP server —— 绕开 pywebview 内置有 bug 的 Bottle
# =====================================================================

class _OwnHTTPServer:
    """用 Python 标准库 SimpleHTTPRequestHandler 起一个本机 HTTP server。"""

    def __init__(self, serve_dir, host="127.0.0.1", port=0):
        handler = functools.partial(
            http.server.SimpleHTTPRequestHandler,
            directory=str(serve_dir),
        )
        # TCPServer 基类；设置 allow_reuse_address 避免端口释放慢导致 bind 失败
        class _Reusable(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = _Reusable((host, port), handler)
        self.host, self.port = self._server.server_address
        # 后台线程跑 serve_forever，daemon=True 确保主线程退出自动终止
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()
        print(f"[httpd] serving {serve_dir} → http://{self.host}:{self.port}/",
              file=sys.stderr)

    def shutdown(self):
        """停止 HTTP server 并关闭 socket。"""
        try:
            self._server.shutdown()
            self._server.server_close()
        except Exception as e:
            print(f"[httpd] shutdown error: {e}", file=sys.stderr)


# =====================================================================
# BridgeApi —— 挂到 pywebview 的 js_api 对象上
# =====================================================================

_win_ref = None
_finalize_fired = [False]


class BridgeApi:
    """前端通过 window.pywebview.api 调这些方法。"""

    def __init__(self, scene_id):
        self.scene_id = scene_id
        self.ping_calls = []               # JS → Python
        self.ping_from_python = None       # Python → JS（场景 C）
        self.ping_from_python_error = None
        self.legacy_foo_result = None      # 场景 D
        self.legacy_foo_error = None
        self.module_call_legacy_result = None
        self.module_call_legacy_error = None
        self.http_host = None
        self.http_port = None
        self.final_snapshot = None
        self.errors_from_frontend = []
        self.pywebview_ready_fired = False

    # ---- 前端调用的 Python 方法 ----

    def ping(self, val):
        self.ping_calls.append({"val": val, "ts": time.time()})
        try:
            return val * 2
        except TypeError:
            return None

    def finalizeScene(self, data):
        """
        前端主动请求 finalize。Flask 线程里执行 destroy()，
        pywebview 内部用 PostMessage 投递，主线程消息循环处理。
        """
        global _finalize_fired
        if _finalize_fired[0]:
            return "already-finalized"
        _finalize_fired[0] = True

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {"raw": data}
        self.final_snapshot = data

        if _win_ref is not None:
            try:
                _win_ref.destroy()
            except Exception as e:
                print(f"[BridgeApi.finalizeScene] destroy: {e}", file=sys.stderr)
        return "ok"

    def reportError(self, info):
        self.errors_from_frontend.append(
            info if isinstance(info, dict) else {"raw": str(info)}
        )


# =====================================================================
# 主控：顺序跑四个子进程
# =====================================================================

def run_master():
    results = []
    for scene_id in ("A", "B", "C", "D"):
        print(f"\n====== 场景 {scene_id}: {SCENES[scene_id]['name']} ======",
              flush=True)
        r = run_child(scene_id)
        results.append(r)

    write_comprehensive(results)
    write_summary(results)


def run_child(scene_id):
    log_path = SPIKE_ROOT / f"scene-{scene_id}.log"
    cmd = [sys.executable, str(SPIKE_ROOT / "spike.py"), "--scene", scene_id]

    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT, cwd=str(SPIKE_ROOT),
        )
        try:
            proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            print(f"[master] 场景 {scene_id} 超时被 kill", flush=True)

    log_text = log_path.read_text(encoding="utf-8", errors="replace")

    result_path = SPIKE_ROOT / f"result-{scene_id}.json"
    if result_path.exists():
        data = json.loads(result_path.read_text(encoding="utf-8"))
    else:
        data = {"scene": scene_id, "error": "result json 未生成",
                "_log_tail": log_text[-2000:]}

    # 主控端额外验证（B/C/D）：端口释放 + 局域网 connect
    port = data.get("http_port")
    host = data.get("http_host")
    if scene_id in ("B", "C", "D") and port:
        data["socket_bind_test"] = _check_port_released(port)
        lan = _check_lan_connect(host, port)
        if lan is not None:
            data["lan_access"] = lan

    data.setdefault("_log_tail", log_text[-3000:])
    return data


def _check_port_released(port):
    time.sleep(1.5)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.close()
        return {"port_released": True}
    except OSError as e:
        return {"port_released": False, "error": str(e)}


def _get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def _check_lan_connect(host, port):
    if not host or not port:
        return None
    lan_ip = _get_lan_ip()
    if lan_ip and host != lan_ip:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            sock.connect((lan_ip, port))
            sock.close()
            return {"lan_connectable": True, "lan_ip": lan_ip}
        except (socket.timeout, OSError) as e:
            return {"lan_connectable": False, "lan_ip": lan_ip, "error": str(e)}
    return None


# =====================================================================
# 子进程：创建窗口，跑一个场景
# =====================================================================

def run_scene_child(scene_id):
    global _win_ref, _finalize_fired
    _win_ref = None
    _finalize_fired = [False]

    scene = SCENES[scene_id]
    need_httpd = scene["http_server"]

    import webview

    api = BridgeApi(scene_id)
    own_httpd = None

    if need_httpd:
        # 自己起 HTTP server，绕开 pywebview 内置 Bottle 的 bug
        own_httpd = _OwnHTTPServer(WEB_DIR)
        api.http_host = own_httpd.host
        api.http_port = own_httpd.port
        url = f"http://{own_httpd.host}:{own_httpd.port}/"
    else:
        url = str(WEB_DIR / "index.html")

    try:
        win = webview.create_window(
            f"ESM Spike {scene_id}",
            url,
            js_api=api,
            width=720, height=480,
        )
        _win_ref = win

        # ---- 注册 loaded 回调（pywebview 6.2.1 公开事件里只有 loaded） ----
        def on_ready():
            api.pywebview_ready_fired = True

            if scene_id == "C":
                try:
                    api.ping_from_python = win.evaluate_js(
                        'window.apiBridgeMain.pongFromPython("hello-from-python")'
                    )
                except Exception as e:
                    api.ping_from_python_error = str(e)

            if scene_id == "D":
                try:
                    api.legacy_foo_result = win.evaluate_js(
                        'window.legacyGlobal.foo()'
                    )
                except Exception as e:
                    api.legacy_foo_error = str(e)
                try:
                    api.module_call_legacy_result = win.evaluate_js(
                        'window.apiBridgeMain.callLegacyFoo()'
                    )
                except Exception as e:
                    api.module_call_legacy_error = str(e)

        try:
            event = win.events.loaded
            event += on_ready
            print(f"[scene-{scene_id}] on_ready → events.loaded", file=sys.stderr)
        except Exception as e:
            print(f"[scene-{scene_id}] 注册事件失败: {e}", file=sys.stderr)

        # ---- 4 秒定时器兜底 finalize ----
        def timer_fallback():
            global _finalize_fired
            if _finalize_fired[0]:
                return
            _finalize_fired[0] = True
            print(f"[scene-{scene_id}] 定时器兜底 finalize（前端没调？）",
                  file=sys.stderr)
            try:
                snap_js = """
                    JSON.stringify({
                        runOrder: window.runOrder || [],
                        bridgeResults: window._bridgeResults || {},
                        errors: window._spikeErrors || [],
                        legacyGlobalExists: !!(window.legacyGlobal),
                        apiBridgeMainExists: !!(window.apiBridgeMain),
                        apiBridgeChainExists: !!(window.apiBridgeChain),
                        apiBridgeLeafExists: !!(window.apiBridgeLeaf)
                    })
                """
                api.final_snapshot = json.loads(win.evaluate_js(snap_js))
            except Exception as e:
                api.final_snapshot = {"error": str(e)}
            if _win_ref is not None:
                try:
                    _win_ref.destroy()
                except Exception as e:
                    print(f"[scene-{scene_id}] timer destroy: {e}",
                          file=sys.stderr)

        threading.Timer(4.0, timer_fallback).start()

        # ---- 阻塞直到窗口被 destroy ----
        try:
            webview.start(debug=False)
        except SystemExit:
            pass
    finally:
        if own_httpd:
            own_httpd.shutdown()

    _write_scene_result(scene_id, api, need_httpd)


def _write_scene_result(scene_id, api, http_server):
    result = {
        "scene": scene_id,
        "scene_name": SCENES[scene_id]["name"],
        "http_server": http_server,
        "http_host": api.http_host,
        "http_port": api.http_port,
        "pywebview_ready_fired": api.pywebview_ready_fired,
        "final_snapshot": api.final_snapshot,
        "js_to_python_ping_calls": api.ping_calls,
        "python_to_js_pongFromPython": {
            "result": api.ping_from_python,
            "error": api.ping_from_python_error,
        },
        "legacy_call_foo": {
            "result": api.legacy_foo_result,
            "error": api.legacy_foo_error,
        },
        "module_call_legacyFoo": {
            "result": api.module_call_legacy_result,
            "error": api.module_call_legacy_error,
        },
        "errors_from_frontend": api.errors_from_frontend,
    }
    out_path = SPIKE_ROOT / f"result-{scene_id}.json"
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[scene-{scene_id}] → {out_path}", file=sys.stderr)


# =====================================================================
# 汇总输出
# =====================================================================

def write_comprehensive(results):
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "scenes": results}
    out_path = SPIKE_ROOT / "comprehensive-result.json"
    out_path.write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\n[master] comprehensive → {out_path}", flush=True)


def write_summary(results):
    """中文 summary.txt：逐个场景列结论 + 关键证据。"""
    L = []
    L.append("=" * 60)
    L.append("ESM Feasibility Spike —— 桌面样机结论")
    L.append("日期：2026-11-12")
    L.append("样机只回答 V1–V4，不涉及产品代码迁移")
    L.append("=" * 60)

    for r in results:
        sid = r.get("scene", "?")
        snap = r.get("final_snapshot") or {}
        run_order = snap.get("runOrder") or []

        L.append("")
        L.append(f"——— 场景 {sid}: {SCENES.get(sid, {}).get('name', '?')} ———")
        L.append(f"  http_server = {r.get('http_server')}")
        if r.get("http_host"):
            L.append(f"  HTTP server = {r['http_host']}:{r['http_port']}（自己起的标准库 server）")

        L.append(f"  runOrder = {run_order}")

        legacy_ok = "legacy-top" in run_order
        main_ok = "main-top" in run_order
        chain_ok = "chain-top" in run_order
        leaf_ok = "leaf-top" in run_order
        L.append(f"  legacy.js 顶层执行       : {legacy_ok}")
        L.append(f"  main.mjs  顶层执行       : {main_ok}")
        L.append(f"  chain.mjs 顶层执行       : {chain_ok}")
        L.append(f"  leaf.mjs  顶层执行       : {leaf_ok}")
        if chain_ok and leaf_ok:
            L.append("  → import 链 main→chain→leaf 完整走通")
        elif main_ok:
            L.append("  → import 链在 chain/leaf 处中断")
        elif not main_ok:
            L.append("  → main.mjs 没执行（WebView2 拦截 / HTTP 没起来 / 网络错误）")

        if "pywebviewready-fired" in run_order:
            L.append("  pywebviewready 事件      : 已触发")
        elif "dom-load-fired" in run_order:
            L.append("  DOM load 兜底            : 已触发（pywebviewready 没出）")
        else:
            L.append("  前端就绪事件             : 都没触发")

        if r.get("js_to_python_ping_calls"):
            c = r["js_to_python_ping_calls"][0]
            L.append(f"  JS→Python ping({c['val']}) → 返回 {c['val'] * 2}: OK")
        else:
            L.append("  JS→Python ping            : 未调用")

        p2j = r.get("python_to_js_pongFromPython") or {}
        if p2j.get("result") is not None:
            L.append(f"  Python→JS pongFromPython : {p2j['result']}")
        elif p2j.get("error"):
            L.append(f"  Python→JS pongFromPython : 失败 — {p2j['error']}")

        if legacy_ok and main_ok:
            li = run_order.index("legacy-top")
            mi = run_order.index("main-top")
            L.append(f"  执行顺序                 : legacy({li}) < main({mi}) {'OK' if li < mi else '异常'}")

        l2m = r.get("legacy_call_foo") or {}
        if l2m.get("result") is not None:
            L.append(f"  legacyGlobal.foo()       : {l2m['result']}")
        m2l = r.get("module_call_legacyFoo") or {}
        if m2l.get("result") is not None:
            L.append(f"  module→legacy 互调       : {m2l['result']}")

        sb = r.get("socket_bind_test")
        if sb:
            L.append(f"  端口释放                 : {sb.get('port_released')}")
        lan = r.get("lan_access")
        if lan:
            L.append(f"  局域网可访问             : {lan.get('lan_connectable')}（本机 {lan.get('lan_ip')}）")

        errs = (r.get("errors_from_frontend") or []) + (snap.get("errors") or [])
        if errs:
            L.append(f"  WebView2 错误            : {errs}")

    L.append("")
    L.append("=" * 60)
    L.append("总体判断（运行完人工填或 report 任务汇总）")

    summary_path = SPIKE_ROOT / "summary.txt"
    summary_path.write_text("\n".join(L), encoding="utf-8")
    print(f"[master] summary → {summary_path}", flush=True)


# =====================================================================
# main
# =====================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", choices=["A", "B", "C", "D"])
    args = parser.parse_args()

    if args.scene:
        run_scene_child(args.scene)
    else:
        run_master()


if __name__ == "__main__":
    main()
