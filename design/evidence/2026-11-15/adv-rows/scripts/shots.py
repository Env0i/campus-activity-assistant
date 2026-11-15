#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""原型画板与本地界面并排截图：一张画板对一张实际界面。

用法（仓库根）：
  python -B design/evidence/2026-11-15/adv-rows/scripts/shots.py
  python -B .../shots.py --only board,AdvCheck,PhGone        # 只出画板那一边
  python -B .../shots.py --only AdvCheck --only PhGone --sides board
  python -B .../shots.py --out %TEMP%/adv-rows-shots

两条本地服务都只绑 127.0.0.1，端口交给系统分配（0），跑完关闭：
  - 画板侧：design/prototype/workbench-2026-11/ 原样静态服务，页面就是画板自己；
  - 界面侧：local/ui/ 静态服务，并在 app.js 之前插入 local/tests/fixtures/runtime_bridge.js
    （测试用的 pywebview 替身），再按下面的场景表把 PhonePanel 摆成画板对应的状态。

界面侧的固定流程：等 window.__modulesReady 与 PhonePanel.paint 可用 → openSettings(<section>)
→ 等 500ms（openSettings 自己会 refresh，必须等它写完再注入）→ 按场景写 PhonePanel.state /
PhonePanel.busy / PhonePanel.pending / OcrPanel.note 等 → PhonePanel.paint() → 按 #settings 的
元素 rect 截图。注入只写状态字段，不依赖任何「一项一行」的新元素，旧排版（标题行在
#phone-feature-status / #ocr-feature-status 那一带）同样适用。

严格判失败（任一即非 0 退出）：pageerror、console 里 type 为 error、任何不是
127.0.0.1/localhost 的请求、端口绑定失败、PNG 不是有效图片。输出与 pairs.md 不写主机路径。

@author Author
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[5]
PROTO = ROOT / "design" / "prototype" / "workbench-2026-11"
UI = ROOT / "local" / "ui"
BRIDGE = ROOT / "local" / "tests" / "fixtures" / "runtime_bridge.js"
OUT_DEFAULT = ROOT / "design" / "evidence" / "2026-11-15" / "adv-rows"

# 界面侧统一的 pywebview 替身场景：登录/列表/条款都按「正常可用」回包，
# 高级功能的差异全部由场景表的注入片段摆，不靠桥的场景名。
BRIDGE_SCENARIO = "valid"

SIDES = ("board", "app")
SIDE_WORDS = {"board", "app"}
BOARD_SUFFIX = ".dc.html"

CTYPES = {
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

# 界面侧等「模块图起来、面板可画」：main.js 置 __modulesReady，legacy-globals 挂回 PhonePanel
APP_READY = ('window.__modulesReady === true && !!window.PhonePanel '
             '&& typeof window.PhonePanel.paint === "function"')

# 每个场景片段之前先铺这几件：面板本体、识别面板、两行共用的构造器与通道快照
APP_PRELUDE = """
  const P = window.PhonePanel;
  const C = window.OcrPanel || (window.OcrPanel = { note: "", error: "" });
  const st = P.state;
  P.notes = P.notes || { feature: "", missing: "", loading: "", off: "", offErr: "", pair: "", onErr: "" };
  P.installing = P.installing || { phone_control: false, relogin_ocr: false };
  const CHANNELS = { tailscale: { available: true, state: "ok" }, cloudflare: { available: true } };
  /* 组件行：字段口径照 features/components/state-machine.js 的 componentState
   * （status 取 missing/checking/outdated/failed/ready 那一套，download.state 取 ""/downloading/
   * verifying/installed/failed，busy+lock_wait_s+check_timed_out 造等锁与超时，read_error 造读不到） */
  const comp = (extra) => Object.assign(
    { status: "missing", ready: false, available: false, download: { state: "" } }, extra || {});
  /* 写两行组件快照；extra 里的键（通道、账号、偏好）并进 st.advanced */
  const feat = (phone, ocr, extra) => {
    st.advanced = Object.assign({}, st.advanced, extra || {},
      { features: { phone_control: phone || comp(), relogin_ocr: ocr || comp() } });
  };
  /* 假二维码：只用页面内 SVG data URL，不发请求。画板那边是点阵码，这里只求看起来是一张码 */
  const qrArt = () => {
    const cell = 6;
    const n = 25;
    let rects = "";
    for (let y = 0; y < n; y += 1) {
      for (let x = 0; x < n; x += 1) {
        const on = ((x * 7 + y * 13) % 5 < 2) || (x < 3 && y < 3) || (x >= n - 3 && y < 3);
        if (on) rects += "<rect x='" + (x * cell) + "' y='" + (y * cell) + "' width='" + cell + "' height='" + cell + "'/>";
      }
    }
    const svg = "<svg xmlns='http://www.w3.org/2000/svg' width='" + (n * cell) + "' height='" + (n * cell)
      + "'><rect width='100%' height='100%' fill='#fff'/><g fill='#111'>" + rects + "</g></svg>";
    return "data:image/svg+xml;utf8," + encodeURIComponent(svg);
  };
"""

# 片段之后统一重画：paint() 是两节共用绘制，paintComponents() 只有一项一行那版才有
APP_EPILOGUE = """
  if (typeof P.paint === "function") P.paint();
  if (typeof P.paintComponents === "function") P.paintComponents();
  return true;
"""

# 场景表：board 是画板文件名；scene 是实际界面要摆成的状态名（也是 --only 的名字、pairs.md 的一列）；
# section 是 openSettings 跳到的分组（空串 = 抽屉顶部总览）；viewport 是浏览器视口。
# js 里的名字来自 APP_PRELUDE：P、C、st、comp、feat、CHANNELS、qrArt。
SCENES = (
    {
        "board": "Settings.dc.html", "scene": "settings", "section": "",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp());
  st.running = false;
  st.link = "off";
""",
    },
    {
        "board": "PhoneSetup.dc.html", "scene": "phonesetup", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ download: { state: "downloading", downloaded: 18400000, total_bytes: 31600000 } }),
       comp());
  st.running = false;
  st.link = "off";
""",
    },
    {
        "board": "PhoneWait.dc.html", "scene": "phonewait", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true }), { channels: CHANNELS });
  st.running = true;
  st.link = "waiting";
  st.channel = "tailscale";
  st.pair_code = "482913";
  st.pair_code_status = { state: "pending", reason: "" };
  st.codeLeft = 272;
  st.qr = qrArt();
""",
    },
    {
        "board": "PhoneLinked.dc.html", "scene": "phonelinked", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true }), { channels: CHANNELS });
  st.running = true;
  st.link = "connected";
  st.channel = "tailscale";
  st.pair_code = "";
  st.paired_count = 1;
  st.live_session = true;
  st.codeLeft = 0;
  st.qr = qrArt();
""",
    },
    {
        "board": "CompOk.dc.html", "scene": "compok", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }),
       comp({ download: { state: "downloading", downloaded: 15580000, total_bytes: 38000000 } }));
  st.running = false;
""",
    },
    {
        "board": "CompFail.dc.html", "scene": "compfail", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }),
       comp({ download: { state: "failed", error_code: "network_error", text: "" } }));
  st.running = false;
""",
    },
    {
        "board": "CompAfter.dc.html", "scene": "compafter", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true }));
  st.running = false;
""",
    },
    {
        "board": "PhFail.dc.html", "scene": "phfail", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ download: { state: "failed", error_code: "network_error", text: "" } }),
       comp({ ready: true, available: true }));
  st.running = false;
""",
    },
    {
        "board": "AdvCheck.dc.html", "scene": "advcheck", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true, status: "checking", busy: true, lock_wait_s: 4 }),
       comp({ ready: true, package_version: "1.2.0" }));
  P.busy = true;
  st.running = false;
""",
    },
    {
        "board": "AdvTimeout.dc.html", "scene": "advtimeout", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true, check_timed_out: true, lock_wait_s: 42 }),
       comp({ ready: true, read_error: true }));
  P.busy = false;
  st.running = false;
""",
    },
    {
        "board": "AdvBroken.dc.html", "scene": "advbroken", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ status: "outdated", ready: true, package_version: "1.2.0" }),
       comp({ status: "failed", ready: true, package_version: "1.2.0" }));
  st.running = false;
""",
    },
    {
        "board": "AdvReFail.dc.html", "scene": "advrefail", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ available: true }),
       comp({ status: "failed", download: { state: "failed", error_code: "network_error" } }));
  C.error = "下载没有完成：连不上发布页，可以重试。";
  st.running = false;
""",
    },
    {
        "board": "AdvUpdFail.dc.html", "scene": "advupdfail", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ status: "outdated", ready: true,
              download: { state: "failed", error_code: "network_error" } }),
       comp({ ready: true, status: "checking", busy: true, read_error: true }));
  st.running = false;
""",
    },
    {
        "board": "AdvVerify.dc.html", "scene": "advverify", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ download: { state: "verifying", downloaded: 38000000, total_bytes: 38000000 } }), comp());
  P.installing.relogin_ocr = true;
  P.busy = true;
  st.running = false;
""",
    },
    {
        "board": "PhDownload.dc.html", "scene": "phdownload", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ download: { state: "downloading", downloaded: 7000000, total_bytes: 18400000 } }),
       comp({ ready: true, available: true }));
  st.running = false;
""",
    },
    {
        "board": "PhStartFail.dc.html", "scene": "phstartfail", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }),
       { channels: { tailscale: { available: false, state: "missing" }, cloudflare: { available: true } } });
  st.running = false;
  st.channel = "cloudflare";
  P.notes.onErr = "Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。";
""",
    },
    {
        "board": "PhStarting.dc.html", "scene": "phstarting", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }));
  st.running = false;
  P.pending = "starting";
  P.busy = true;
""",
    },
    {
        "board": "PhStopping.dc.html", "scene": "phstopping", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }), { channels: CHANNELS });
  st.running = true;
  st.link = "connected";
  st.paired_count = 1;
  st.live_session = true;
  P.pending = "stopping";
  P.busy = true;
""",
    },
    {
        "board": "PhGone.dc.html", "scene": "phgone", "section": "adv",
        "viewport": (1280, 800),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }), { channels: CHANNELS });
  st.running = true;
  st.link = "disconnected";
  st.last_contact_ago_s = 150;
  st.paired_count = 1;
  st.live_session = false;
  st.pair_code = "482913";
  st.codeLeft = 271;
  st.qr = qrArt();
""",
    },
    {
        "board": "NarrowSettings.dc.html", "scene": "narrow-settings", "section": "",
        "viewport": (430, 820),
        "js": """
  feat();
  st.running = false;
  st.link = "off";
""",
    },
    # 以下是本批补的四张 + 一张 900 宽中档：画板那侧没有对应的一对，
    # 所以只出界面一侧（sides 收窄），结论写进 pairs.md。
    {
        "board": "", "scene": "startfail-port", "section": "adv",
        "viewport": (1280, 800), "sides": ("app",),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }), { channels: CHANNELS });
  st.running = false;
  st.link = "off";
  PhonePanel.notes.offErr = "端口 8765 被别的程序占着，换一条通道或关掉那个程序再试。";
""",
    },
    {
        "board": "", "scene": "startfail-tunnel", "section": "adv",
        "viewport": (1280, 800), "sides": ("app",),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }),
       { channels: { tailscale: CHANNELS.tailscale,
                     cloudflare: { available: true, state: "exited", error: "tunnel_exited",
                                   addresses: [] } } });
  st.running = false;
  st.link = "off";
  /* 画板 PhStartFail 选中的是 Cloudflare：通道名要说 Cloudflare，别拿 Tailscale 对图 */
  st.channel = "cloudflare";
  P.channel = "cloudflare";
""",
    },
    {
        "board": "", "scene": "stopping", "section": "adv",
        "viewport": (1280, 800), "sides": ("app",),
        "js": """
  feat(comp({ ready: true }), comp({ ready: true, available: true }));
  st.running = true;
  st.link = "connected";
  st.last_contact_ago_s = 5;
  st.paired_count = 1;
  st.live_session = true;
  PhonePanel.pending = "stopping";
  PhonePanel.busy = true;
""",
    },
    {
        "board": "", "scene": "advcheck-900", "section": "adv",
        "viewport": (900, 800), "sides": ("app",),
        "js": """
  feat(comp({ status: "checking", ready: true, busy: true, lock_wait_s: 4 }), comp());
  st.running = false;
  st.link = "off";
""",
    },
)


def board_stem(scene: dict) -> str:
    """画板文件名去掉 .dc.html：AdvCheck.dc.html → AdvCheck。"""
    board = str(scene.get("board") or "")
    if not board:
        return str(scene["scene"])
    return board[:-len(BOARD_SUFFIX)] if board.endswith(BOARD_SUFFIX) else Path(board).stem


def scrubbed(text) -> str:
    """打印前抹掉主机路径：出错信息里可能带仓库根或临时目录。"""
    value = str(text)
    for raw, token in ((str(ROOT), "<repo>"), (str(Path.cwd()), "<cwd>"),
                       (str(Path.home()), "~"), (tempfile.gettempdir(), "<temp>")):
        if not raw:
            continue
        value = value.replace(raw, token).replace(raw.replace("\\", "/"), token)
    return value


def build_test_page(root: Path) -> str:
    """生产 index.html 原样保留，只在 app.js 之前插入测试桥。"""
    html = (root / "index.html").read_text(encoding="utf-8")
    marker = '<script src="app.js"></script>'
    if marker not in html:
        raise RuntimeError("index.html 结构变了：找不到 app.js 脚本标签")
    return html.replace(marker, '<script src="/qa/runtime_bridge.js"></script>\n  ' + marker, 1)


class _Handler(BaseHTTPRequestHandler):
    """按后缀给 Content-Type，只服务 root 里的普通文件；异常回固定串，不把路径交给页面。"""

    server_version = "adv-rows-shots/1.0"
    root: Path
    inject_bridge = False

    def log_message(self, fmt, *args):  # noqa: A003 - 保持静默，证据走终端
        return

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 约定
        path = urlparse(self.path).path
        try:
            if self.inject_bridge and path in ("", "/", "/index.html"):
                self._send(200, "text/html; charset=utf-8",
                           build_test_page(self.root).encode("utf-8"))
                return
            if self.inject_bridge and path == "/qa/runtime_bridge.js":
                self._send(200, "application/javascript; charset=utf-8", BRIDGE.read_bytes())
                return
            name = path.lstrip("/") or "index.html"
            target = (self.root / name).resolve()
            ctype = CTYPES.get(target.suffix.lower())
            # is_relative_to 一并挡住 .. 与绝对路径；隐藏文件不对外暴露
            inside = (ctype is not None and target.is_file() and target.is_relative_to(self.root)
                      and not any(part.startswith(".")
                                  for part in target.relative_to(self.root).parts))
            if inside:
                self._send(200, ctype, target.read_bytes())
                return
            self._send(404, "text/plain; charset=utf-8", b"not found")
        except Exception as exc:  # noqa: BLE001 - 500 只回固定串，真实原因打在本机终端
            traceback.print_exception(exc)
            self._send(500, "text/plain; charset=utf-8", "静态文件读取失败".encode("utf-8"))


class StaticServer:
    """只绑 127.0.0.1；端口传 0 由系统分配，用完 stop()。"""

    def __init__(self, root: Path, inject_bridge: bool = False, host: str = "127.0.0.1",
                 port: int = 0):
        handler = type("AdvHandler", (_Handler,),
                       {"root": Path(root).resolve(), "inject_bridge": inject_bridge})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="shots-http", daemon=True)

    @property
    def base(self) -> str:
        return "http://%s:%d" % (self.host, self.port)

    def start(self) -> "StaticServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class PageWatch:
    """一页的观察器：控制台错误、pageerror、外部请求（只放行本服务与 data:/about:/blob:）。"""

    def __init__(self, page, base: str):
        self.base = base
        self.console: list[str] = []
        self.page_errors: list[str] = []
        self.external: list[str] = []
        page.on("console", self._on_console)
        page.on("pageerror", self._on_pageerror)
        page.route("**/*", self._route)

    def _on_console(self, message) -> None:
        if message.type == "error":
            self.console.append(message.text)

    def _on_pageerror(self, error) -> None:
        self.page_errors.append(str(error))

    def _route(self, route) -> None:
        url = route.request.url
        if url.startswith(self.base) or url.startswith(("data:", "about:", "blob:")):
            route.continue_()
            return
        self.external.append(url)
        route.abort()

    def problems(self) -> list[str]:
        found = []
        if self.page_errors:
            found.append("pageerror：" + " | ".join(self.page_errors))
        if self.console:
            found.append("console error：" + " | ".join(self.console))
        if self.external:
            found.append("外部请求：" + " | ".join(self.external))
        return found


def png_size(target: Path) -> tuple[int, int, int]:
    """校验 PNG 魔数并取宽高：读 IHDR，不装依赖。"""
    data = target.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) <= 512:
        raise ValueError("不是有效的 PNG（%d 字节）" % len(data))
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"), len(data)


def open_page(browser, base: str, viewport, init_script: str | None = None):
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    page = context.new_page()
    if init_script:
        page.add_init_script(init_script)
    return context, page, PageWatch(page, base)


# 每条状态句与小字在原型里的字色（Main.dc.html 的 --ok / --warn / --bad / --ink-2）。
# 圆点另有亮色，这里只看字：字必须用这四个深色，否则在浅底上对比度不到 4.5。
COLOR_WANT_STATUS = {
    "green": "#146c43", "amber": "#8f5600", "red": "#b63227",
    "blue": "#4e5964", "amber-dot": "#4e5964", "": "#4e5964",
}
# 小字（.adv-n）：原型的红比状态句更深一档，绿与琥珀复用同一组变量。
COLOR_WANT_NOTE = {
    "green": "#146c43", "amber": "#8f5600", "red": "#8a2a20",
    "blue": "#4e5964", "amber-dot": "#4e5964", "": "#4e5964",
}
MIN_CONTRAST = 4.5

COLOR_AUDIT_JS = r"""
() => {
  const TONES = ["green", "amber", "red", "blue", "amber-dot"];
  const num = (s) => {
    const m = String(s).match(/[\d.]+/g);
    if (!m) return null;
    if (m.length >= 4 && Number(m[3]) === 0) return null;
    return m.slice(0, 3).map(Number);
  };
  const hex = (c) => "#" + c.map((v) => (v < 16 ? "0" : "") + v.toString(16)).join("");
  const lum = (c) => {
    const f = (v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => {
    const l1 = lum(a), l2 = lum(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  };
  const bgOf = (el) => {
    let node = el;
    while (node && node.nodeType === 1) {
      const c = num(getComputedStyle(node).backgroundColor);
      if (c) return c;
      node = node.parentElement;
    }
    return [255, 255, 255];
  };
  const rows = [];
  const targets = [["phone-status", "#phone-feature-status"],
                   ["ocr-status", "#ocr-feature-status"],
                   ["phone-note", "#phone-probe"],
                   ["ocr-note", "#ocr-note"]];
  for (const [key, sel] of targets) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const style = getComputedStyle(el);
    const color = num(style.color);
    rows.push({
      key: key,
      tone: TONES.filter((tone) => el.classList.contains(tone)).join(" "),
      text: (el.textContent || "").trim(),
      hidden: !!el.hidden || style.display === "none",
      color: color ? hex(color) : "",
      contrast: color ? Math.round(ratio(color, bgOf(el)) * 100) / 100 : 0,
    });
  }
  return rows;
}
"""


def audit_colors(page) -> list:
    """在真实浏览器里读每张卡的状态句与小字：字色要等于原型的深色，对比度不低于 4.5。"""
    problems = []
    for row in page.evaluate(COLOR_AUDIT_JS):
        if row["hidden"] or not row["text"]:
            continue
        table = COLOR_WANT_STATUS if row["key"].endswith("-status") else COLOR_WANT_NOTE
        want = table.get(row["tone"], None)
        if want is None:
            problems.append("字色检查：%s 的色调类 %r 不认识" % (row["key"], row["tone"]))
            continue
        if row["color"] != want:
            problems.append("字色检查：%s（%s）是 %s，原型规定 %s"
                            % (row["key"], row["tone"] or "无色调", row["color"], want))
        if row["contrast"] < MIN_CONTRAST:
            problems.append("字色检查：%s 对比度 %.2f，低于 %.1f"
                            % (row["key"], row["contrast"], MIN_CONTRAST))
    return problems


def shoot_board(browser, base: str, scene: dict, target: Path):
    """画板侧：整页截（画板是固定 1280×800 或 430×820 的画布）。"""
    context, page, watch = open_page(browser, base, scene["viewport"])
    try:
        page.goto(base + "/" + scene["board"], wait_until="domcontentloaded", timeout=30000)
        # 画布运行时（support.js）先把内容画出来，再等网络静默与 600ms 收尾动画
        page.wait_for_function("!!document.body && document.body.innerText.trim().length > 80",
                               timeout=20000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(600)
        page.screenshot(path=str(target), full_page=True)
    finally:
        context.close()
    return watch.problems(), png_size(target)


def shoot_app(browser, base: str, scene: dict, target: Path):
    """界面侧：起桥 → 等模块图 → 开抽屉 → 等 refresh 写完 → 注入状态 → 重画 → 截 #settings。"""
    context, page, watch = open_page(
        browser, base, scene["viewport"],
        "window.__QA_SCENARIO = %s;" % json.dumps(BRIDGE_SCENARIO))
    try:
        page.goto(base + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function(APP_READY, timeout=20000)
        page.evaluate("openSettings(%s)" % json.dumps(scene.get("section") or ""))
        page.wait_for_timeout(500)
        page.evaluate("() => {%s%s%s}" % (APP_PRELUDE, scene["js"], APP_EPILOGUE))
        page.wait_for_timeout(200)
        page.locator("#settings").screenshot(path=str(target))
        problems = watch.problems() + audit_colors(page)
    finally:
        context.close()
    return problems, png_size(target)


def write_pairs(out_dir: Path, scenes) -> None:
    """pairs.md 骨架：每个场景一行，看过图再填结论。"""
    lines = [
        "# 画板与本地界面对照",
        "",
        "每个画板一行：画板名、界面侧场景名、结论。结论看完图再写，保留 `待看图填写` 表示还没看。",
        "",
        "| 画板 | 场景 | 结论 |",
        "| --- | --- | --- |",
    ]
    for scene in scenes:
        lines.append("| %s | %s | 待看图填写 |" % (board_stem(scene), scene["scene"]))
    (out_dir / "pairs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def select_scenes(tokens, sides: str):
    """--only 里 board/app 选边，其余按画板名或场景名过滤（大小写不敏感）。"""
    chosen = {"board", "app"} if sides == "both" else {sides}
    names: list[str] = []
    for chunk in tokens:
        for item in str(chunk).replace("，", ",").split(","):
            item = item.strip()
            if not item:
                continue
            low = item.lower()
            if low in SIDE_WORDS:
                chosen &= {low}
            else:
                names.append(low)
    if names:
        scenes = [scene for scene in SCENES
                  if board_stem(scene).lower() in names or str(scene["scene"]).lower() in names]
        if not scenes:
            known = "、".join(board_stem(scene) for scene in SCENES)
            raise SystemExit("--only 没匹配到画板：%s\n可用：%s" % ("、".join(tokens), known))
    else:
        scenes = list(SCENES)
    return scenes, [side for side in SIDES if side in chosen]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="原型画板与本地界面并排截图")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="输出目录，默认 design/evidence/2026-11-15/adv-rows")
    parser.add_argument("--only", action="append", default=[], metavar="名字",
                        help="只跑这些画板/场景；可重复或逗号分隔。board / app 表示只跑某一侧")
    parser.add_argument("--sides", choices=("both", "board", "app"), default="both",
                        help="跑哪一侧，默认两边都跑")
    return parser.parse_args(argv)


def start_server(root: Path, inject_bridge: bool, servers: list) -> str:
    try:
        server = StaticServer(root, inject_bridge).start()
    except OSError as exc:
        print("端口绑定失败（可能被占用）：" + scrubbed(exc))
        raise SystemExit(2)
    servers.append(server)
    return server.base


def run_shots(browser, bases: dict, scenes, sides, out_dir: Path):
    failures: list[str] = []
    bad_images = 0
    for scene in scenes:
        stem = board_stem(scene)
        for side in (scene.get("sides") or sides):
            target = out_dir / ("%s-%s.png" % (stem, side))
            try:
                shoot = shoot_board if side == "board" else shoot_app
                problems, size = shoot(browser, bases[side], scene, target)
            except Exception as exc:  # noqa: BLE001 - 单格失败不打断整轮，最后统一非 0
                problems, size = ["截图失败：" + (str(exc) or exc.__class__.__name__)], None
            if size:
                print("[%s] %s %s %dx%d %.1f KB" % ("ok" if not problems else "fail",
                                                    stem, side, size[0], size[1], size[2] / 1024.0))
            else:
                print("[fail] %s %s 没有生成图片" % (stem, side))
            if problems:
                bad_images += 1
            for problem in problems:
                print("       " + scrubbed(problem))
                failures.append("%s %s: %s" % (stem, side, scrubbed(problem)))
    return failures, bad_images


def check_inputs(scenes, sides) -> None:
    if "board" in sides:
        # 没有画板的场景（这批补的「开启失败」两种来源、中档宽度）只出界面一侧
        missing = [scene["board"] for scene in scenes
                   if scene.get("board") and not (PROTO / scene["board"]).is_file()]
        if missing:
            raise SystemExit("缺少画板文件：" + "、".join(missing))
    if "app" in sides:
        for path in (UI / "index.html", BRIDGE):
            if not path.is_file():
                raise SystemExit("缺少界面文件：" + str(path.relative_to(ROOT)))


def main(argv=None) -> int:
    args = parse_args(argv)
    scenes, sides = select_scenes(args.only, args.sides)
    check_inputs(scenes, sides)
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_pairs(out_dir, scenes)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("没有装 playwright，跑不了截图")
        return 2

    servers: list = []
    failures: list[str] = []
    try:
        bases = {}
        if "board" in sides:
            bases["board"] = start_server(PROTO, False, servers)
        if "app" in sides:
            bases["app"] = start_server(UI, True, servers)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="msedge", headless=True)
            try:
                failures, bad_images = run_shots(browser, bases, scenes, sides, out_dir)
            finally:
                browser.close()
    finally:
        for server in servers:
            server.stop()

    shots = len(scenes) * len(sides)
    if failures:
        print("失败 %d 条 / 共 %d 张图，其中 %d 张有问题" % (len(failures), shots, bad_images))
        return 1
    print("全部 %d 张图通过：没有 pageerror、console error、外部请求与字色问题" % shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
