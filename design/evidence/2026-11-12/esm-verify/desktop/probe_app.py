# -*- coding: utf-8 -*-
"""桌面样机：按产品同样的写法建窗口，跑 H2/H3/H4/H5/H11 的探针并写脱敏 JSON。

场景（--scenario）：
  product        传给 create_window 的是不带协议前缀的绝对路径，start() 不传 http_server
                 （与 local/app.py:4829-4832 的写法一致）——H2 主场景、H5 早推
  file-url       显式传 file:// 地址
  file-url-allow 显式传 file://，并设 webview.settings['ALLOW_FILE_URLS']=True
  file-url-noallow  显式传 file://，并设 webview.settings['ALLOW_FILE_URLS']=False
                 （E1 对照组：pywebview 6.2.1 默认 True，见 webview/__init__.py:121）
  http-server    start(http_server=True)，用来坐实上一轮「Bottle 报错」的说法
  h11            入口模块 404，只看 5 秒兜底
  cycle          顶层互相引用的循环，记录报错原文
  h9-legacy / h9-flat / h9-chain / h9-preload   40 个脚本/模块的加载计时（auto=0）

取数方式：窗口起来后由本进程用 evaluate_js 读页面里的探针对象，读到就 os._exit(0)。
不走 js_api、也不从线程里关窗——pywebview 关窗在部分环境会卡住 GUI 线程，
样机只需要数据，不值得为优雅退出冒卡死的风险。

冻结态（PyInstaller）从 sys._MEIPASS/web/generated 取资源，与发版写法一致。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC_ROOT = HERE.parent
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    # onefile/onedir：资源在 sys._MEIPASS，结果写在 exe 旁边，别落进临时解包目录
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS"))
    SAMPLE_ROOT = Path(sys.executable).resolve().parent
else:
    RESOURCE_ROOT = SRC_ROOT
    SAMPLE_ROOT = SRC_ROOT
WEB = RESOURCE_ROOT / "web" / "generated"
RESULTS = SAMPLE_ROOT / "results"

sys.path.insert(0, str(RESOURCE_ROOT / "tools"))
from redact import redact_obj  # noqa: E402


# F1（返修）：控制台打印可能因编码抛异常（stdout 被重定向且不是 UTF-8 时）。
# 打印失败只能降级，不能抛出，否则 os._exit 走不到，GUI 线程不退，进程挂住。
def _say(message: str) -> None:
    try:
        print(message, flush=True)
    except Exception:  # noqa: BLE001 - 打印失败只降级
        try:
            sys.stdout.write(message.encode("ascii", "replace").decode("ascii") + "\n")
            sys.stdout.flush()
        except Exception:  # noqa: BLE001
            pass

PAGES = {
    "product": ("h2/page.html", "", 4.0),
    "file-url": ("h2/page.html", "", 4.0),
    "file-url-allow": ("h2/page.html", "", 4.0),
    "file-url-noallow": ("h2/page.html", "", 4.0),  # E1 新增：显式关闭 ALLOW_FILE_URLS
    "http-server": ("h2/page.html", "", 4.0),
    "h11": ("h11/index.html", "", 7.5),
    "cycle": ("h3/cycle/index.html", "", 2.5),
    "h9-legacy": ("h9/legacy/index.html", "?auto=0", 2.5),
    "h9-flat": ("h9/flat/index.html", "?auto=0", 2.5),
    "h9-chain": ("h9/chain/index.html", "?auto=0", 2.5),
    "h9-preload": ("h9/preload-chain/index.html", "?auto=0", 2.5),
}

PROBE_DELAYS = (0, 50, 100, 200, 500)

# E1：pywebview 6.2.1 的 ALLOW_FILE_URLS 默认值（webview/__init__.py:121）。
# 结果里用它判断「这次的取值是不是默认值」，换版本后默认值变了会在结果里看得出来。
PYWEBVIEW_DEFAULT_ALLOW_FILE_URLS = True
# 启动时读到的取值与本场景是否显式改过，供 main() 的异常分支也能落盘
ALLOW_STATE: dict = {"at_start": None, "set_by_probe": None}


def allow_fields(webview_module) -> dict:
    """E1：每个场景的结果都写明 ALLOW_FILE_URLS 的取值与是否为 pywebview 默认值。"""
    if webview_module is None:
        return {"allow_file_urls": "unknown（webview 未导入）"}
    final = bool(webview_module.settings.get("ALLOW_FILE_URLS"))
    return {
        "allow_file_urls": final,
        "allow_file_urls_at_start": ALLOW_STATE["at_start"],
        "allow_file_urls_set_by_probe": ALLOW_STATE["set_by_probe"],
        "pywebview_default_allow_file_urls": PYWEBVIEW_DEFAULT_ALLOW_FILE_URLS,
        "allow_file_urls_is_pywebview_default": final == PYWEBVIEW_DEFAULT_ALLOW_FILE_URLS,
    }


def send_probe(window, records: list, lock: threading.Lock,
               n: int, phase: str, loaded: bool) -> None:
    expression = "window.onBackend && window.onBackend.probe(%d)" % n
    item = {"n": n, "phase": phase, "loaded_at_send": loaded,
            "returned": None, "error": None, "duration_ms": None}
    started = time.perf_counter()
    try:
        item["returned"] = window.evaluate_js(expression)
    except Exception as exc:  # noqa: BLE001 - 记录原文即可
        item["error"] = "%s: %s" % (type(exc).__name__, exc)
    item["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    with lock:
        records.append(item)


def run(args, out_path: Path) -> None:
    import webview

    rel, query, collect_after = PAGES[args.scenario]
    page = WEB / rel
    if not page.is_file():
        raise SystemExit("页面不存在：%s（先跑 web/gen_modules.py）" % rel)

    if args.scenario in ("file-url", "file-url-allow", "file-url-noallow"):
        url = page.as_uri() + query
    else:
        url = str(page) + query
    # E1：只有 file-url-allow / file-url-noallow 显式改这个设置，其余场景保持 pywebview 默认值
    ALLOW_STATE["at_start"] = bool(webview.settings.get("ALLOW_FILE_URLS"))
    if args.scenario == "file-url-allow":
        webview.settings["ALLOW_FILE_URLS"] = True
        ALLOW_STATE["set_by_probe"] = True
    elif args.scenario == "file-url-noallow":
        webview.settings["ALLOW_FILE_URLS"] = False
        ALLOW_STATE["set_by_probe"] = False

    window = webview.create_window("ESM verify probe", url, width=760, height=560)
    loaded = {"flag": False, "at": None}
    records: list = []
    lock = threading.Lock()
    emitted = threading.Event()
    started_at = time.perf_counter()

    def collect_and_exit() -> None:
        snapshot = None
        error = None
        try:
            raw = window.evaluate_js("JSON.stringify(window.__collect())")
            snapshot = json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            error = "%s: %s" % (type(exc).__name__, exc)
        if emitted.is_set():
            os._exit(0)
        received = []
        for item in ((snapshot or {}).get("backend_events") or []):
            try:
                received.append(int(item.get("n")))
            except (TypeError, ValueError):
                continue
        for item in records:
            item["received_by_page"] = item["n"] in received
        result = {
            "scenario": args.scenario,
            "page": rel,
            "url_kind": "unchanged-absolute-path" if args.scenario not in
                        ("file-url", "file-url-allow", "file-url-noallow") else "file-uri",
            **allow_fields(webview),
            "loaded_event": {"fired": loaded["flag"]},
            "env": {
                "frozen": bool(getattr(sys, "frozen", False)),
                "resource_root": str(RESOURCE_ROOT),
                "python": platform.python_version(),
                "system": platform.platform(),
                "pywebview": _version("pywebview"),
            },
            "backend_push": records,
            "snapshot": snapshot,
            "collect_error": error,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 1),
        }
        names = [socket.gethostname(), os.environ.get("COMPUTERNAME", "")]
        # 加固（不在 E 清单内）：页面自己报的 location.host 是 file:// 的主机段（共享盘服务器名），
        # 也当主机名脱敏；否则 file:// 场景的结果里会留下一个机器名
        # X2（返修）：回环地址与空串由 redact.usable_names 统一过滤，这里不再手工区分
        loc = (snapshot or {}).get("location") or {}
        names += [str(loc.get("host") or ""), str(loc.get("hostname") or "")]
        try:
            out_path.write_text(
                json.dumps(redact_obj(result, names), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n")
            emitted.set()
            _say("[desktop] %s -> %s" % (args.scenario, out_path))
        except Exception as exc:  # noqa: BLE001 - 写盘失败也要退出，不能挂住窗口
            _say("[desktop] %s 写盘失败：%s" % (args.scenario, type(exc).__name__))
        finally:
            # F1：无论写盘与打印是否成功，都必须走到 os._exit
            os._exit(0)

    def on_loaded():
        loaded["flag"] = True
        loaded["at"] = time.perf_counter()
        if args.scenario == "product":
            for n, delay in enumerate(PROBE_DELAYS, start=1):
                threading.Timer(delay / 1000.0, send_probe,
                                args=(window, records, lock, n,
                                      "after_loaded", True)).start()
        threading.Timer(collect_after, collect_and_exit).start()

    window.events.loaded += on_loaded

    def gui_start():
        # H5：GUI 刚起来、loaded 事件之前推一次（模块还没执行）
        if args.scenario == "product":
            send_probe(window, records, lock, -1, "gui_start", loaded["flag"])

    try:
        if args.scenario == "http-server":
            webview.start(gui_start, None, http_server=True, debug=False)
        else:
            webview.start(gui_start, None, debug=False)
    except Exception as exc:  # noqa: BLE001 - http_server 的报错要原样留下
        payload = {
            "scenario": args.scenario,
            "page": rel,
            **allow_fields(sys.modules.get("webview")),
            "start_error": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback_tail": traceback.format_exc().splitlines()[-6:],
            },
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 1),
        }
        names = [socket.gethostname(), os.environ.get("COMPUTERNAME", "")]
        try:
            out_path.write_text(
                json.dumps(redact_obj(payload, names), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8", newline="\n")
            _say("[desktop] %s -> %s（start 抛错）" % (args.scenario, out_path))
        except Exception as exc:  # noqa: BLE001
            _say("[desktop] %s 写盘失败：%s" % (args.scenario, type(exc).__name__))
        finally:
            os._exit(0)


def _version(name: str) -> str:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    # F1（返修）：stdout 被重定向且不是 UTF-8 时改为 replace，打印不再抛编码错误
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:  # noqa: BLE001 - 旧解释器或非 TextIOWrapper 时跳过
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=sorted(PAGES))
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESULTS / ("desktop-%s.json" % args.scenario)

    try:
        run(args, out)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - 任何异常都要落盘可查
        names = [socket.gethostname(), os.environ.get("COMPUTERNAME", "")]
        payload = {"scenario": args.scenario, **allow_fields(sys.modules.get("webview")), "fatal": {
            "type": type(exc).__name__, "message": str(exc),
            "traceback_tail": traceback.format_exc().splitlines()[-8:],
        }}
        out.write_text(json.dumps(redact_obj(payload, names), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
        _say("[desktop] %s -> %s（异常）" % (args.scenario, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
