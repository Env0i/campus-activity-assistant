#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顶栏手机状态：原型画板与实际界面的并排截图（2026-11-15）。

用法（仓库根）：
  python -B design/evidence/2026-11-15/topbar-phone/scripts/shots.py
  python -B .../shots.py --only board,PhStartingTop,PhGoneTop   # 只出画板那两张
  python -B .../shots.py --only app,waiting-900 --sides app      # 只出界面侧窄档
  python -B .../shots.py --out %TEMP%/topbar-shots

两条服务都只绑 127.0.0.1、端口由系统分配：画板侧服务 design/prototype/workbench-2026-11/
（四个场景各有一张已经摆好状态的 .dc.html，直接打开那张，不再用 Main.dc.html 摆状态）；
界面侧服务 local/ui/，并在 app.js 之前插入 local/tests/fixtures/runtime_bridge.js。

界面侧流程：等 __modulesReady 与 PhonePanel.paint → 按场景表 Object.assign 写 PhonePanel.state
与 PhonePanel.pending → paint() → 要卡片时 openStatusCard("phone", true) → 截图。
**不打开设置抽屉**：这批图只看顶栏与详情卡，抽屉开着会把无关内容带进裁剪区。

拼图用「并集裁剪」：一个矩形覆盖顶栏 .status、手机标识、已展开的卡片与卡尖（存在时）的并集，
一次 clip 截出，四周留 8px。不选纵向拼接，因为拼接会藏掉卡片与顶栏的真实间距。

画板是固定 1280 宽画布，900 / 430 两档与「等手机连接」都没有画板：画板列写原因、打 [skip]，
不算失败。严格判失败的是 pageerror、console error、非 127.0.0.1 的请求、端口绑定失败、
无效 PNG，以及界面侧断言：关闭态标识收起；转圈只在 pending 时出现且 animation-name 非 none；
waiting 带 is-warn 与 blink、connected 带 is-ok 不带 is-warn、已断开都不带；#phone-badge-text
字色等于 --ok / --warn 且与叠出来的底色对比度不低于 4.5；aria-label 非空且提到状态；
#phone-pop-cap 是长期地址 / 临时地址、#phone-pop-note 非空、#phone-pop-rows 配对 4 组
dt/dd、没配对 3 组（只看结构不看数字）。

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
OUT_DEFAULT = ROOT / "design" / "evidence" / "2026-11-15" / "topbar-phone" / "shots"

# 界面侧统一用「正常可用」的桥场景：登录、列表照常回包，手机状态全由场景表注入
BRIDGE_SCENARIO = "valid"
SIDES = ("board", "app")
BOARD_SUFFIX = ".dc.html"
CLIP_PAD = 8
MIN_CONTRAST = 4.5
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

# 场景快照的公共部分：字段口径照后端 phone_access_state，只写顶栏与卡片读的那几项。
# address 用原型里的假地址（不认识的主机名 + 本机端口），页面不会去连它。
PHONE_FEATURE = {"status": "ready", "ready": True, "available": True, "download": {"state": ""}}
ADDRESS_TS = "http://my-pc.tailnet.ts.net:8765/"


def phone_state(**extra) -> dict:
    """一份完整的手机访问快照，extra 覆盖单项。"""
    state = dict(running=False, channel="tailscale", address=ADDRESS_TS, paired_count=0,
                  live_session=False, link="off", last_contact_ago_s=None,
                  pair_code_left_s=0, preferred_channel="tailscale",
                  advanced={"features": {"phone_control": dict(PHONE_FEATURE)}})
    state.update(extra)
    return state


def scene(sid, board, pending, card, tone, aria, cap, rows, board_why="", **state) -> dict:
    """一行场景：state 从 phone_state 起，转圈由 pending 推出来。id 也是 PNG 的文件名前缀。"""
    return {
        "id": sid, "board": board, "board_why": board_why, "viewport": (1280, 800),
        "pending": pending, "card": card, "state": phone_state(**state),
        "expect": {"spin": pending in ("starting", "stopping"), "tone": tone,
                   "aria": aria, "card": card, "cap": cap, "rows": rows},
    }


_WIDE = (
    scene("PhStartingTop", "PhStartingTop.dc.html", "starting", False, "", ("正在开启",), "", None),
    scene("PhStopping", "PhStopping.dc.html", "stopping", False, "", ("正在停止",), "", None,
          running=True, link="connected", paired_count=1, live_session=True),
    scene("PhGoneTop", "PhGoneTop.dc.html", "", True, "", ("已断开", "2 分钟前"), "长期地址", 4,
          running=True, link="disconnected", last_contact_ago_s=150, paired_count=1),
    scene("PopPhone", "PopPhone.dc.html", "", True, "ok", ("手机已连接",), "长期地址", 4,
          running=True, link="connected", last_contact_ago_s=8, paired_count=1, live_session=True),
    # 原型里没有「等手机连接」这一张，只有界面侧
    scene("waiting", "", "", True, "warn", ("等手机连接",), "长期地址", 4,
          "没有这张画板，只有界面侧", running=True, link="waiting", paired_count=1),
)

NARROW_SIDS = ("waiting", "PhGoneTop")
NARROW_WIDTHS = (900, 430)


def _narrow(row: dict, width: int) -> dict:
    """同一场景的窄档：只改视口；画板没有窄画布。"""
    return dict(row, id="%s-%d" % (row["id"], width), viewport=(width, 800),
                board="", board_why="画板只有 1280 宽固定画布，窄档只出界面侧")


SCENES = _WIDE + tuple(_narrow(row, width) for row in _WIDE
                       if row["id"] in NARROW_SIDS for width in NARROW_WIDTHS)

# 场景注入：先铺面板本体的兜底字段，再按场景表写快照。注入只写状态，不碰元素。
APPLY_JS = r"""
(cfg) => {
  const P = window.PhonePanel;
  P.notes = P.notes || { feature: "", missing: "", loading: "", off: "", offErr: "", pair: "", onErr: "" };
  P.installing = P.installing || { phone_control: false, relogin_ocr: false };
  if (!window.OcrPanel) window.OcrPanel = { note: "", error: "" };
  Object.assign(P.state, cfg.state || {});
  P.pending = cfg.pending || "";
  P.busy = !!cfg.busy;
  if (typeof P.paint === "function") P.paint();
  if (cfg.card && typeof openStatusCard === "function") openStatusCard("phone", true);
  return true;
}
"""

# 裁剪矩形：顶栏 .status ∪ 手机标识 ∪ 已展开的卡片 ∪ 卡尖。cfg 里带两边的选择器。
CLIP_JS = r"""
(cfg) => {
  const q = (sel) => (sel ? document.querySelector(sel) : null);
  const shown = (el) => !!el && !el.hidden && getComputedStyle(el).display !== "none"
    && getComputedStyle(el).visibility !== "hidden";
  const st = q(cfg.status);
  if (!st) return { error: "找不到顶栏：" + cfg.status };
  let pill = q(cfg.badge);
  if (!pill) {
    /* 画板没有 id：手机标识是 .status 里最后一个 .st-item 的 button.pill（时钟、登录在前） */
    const items = Array.from(st.querySelectorAll(".st-item"));
    const owner = items[items.length - 1];
    pill = owner ? owner.querySelector("button.pill") : null;
  }
  if (!pill) return { error: "找不到手机标识" };
  const card = q(cfg.card);
  const cardOn = shown(card);
  const rects = [];
  for (const el of [st, pill, cardOn ? card : null]) {
    if (!el) continue;
    const b = el.getBoundingClientRect();
    /* 收起（hidden）的元素量出来是 0×0，会把并集拉回原点，跳过 */
    if (b.width > 0 || b.height > 0) rects.push(b);
  }
  if (cardOn) {
    /* 卡尖：画板是 .st-item 里的 i.sc-caret；界面侧今天还没有这个元素，缺席不算失败 */
    const caret = (card.closest(".st-item") || document).querySelector(cfg.caret);
    if (shown(caret)) rects.push(caret.getBoundingClientRect());
  }
  const left = Math.min(...rects.map((b) => b.left));
  const top = Math.min(...rects.map((b) => b.top));
  const right = Math.max(...rects.map((b) => b.right));
  const bottom = Math.max(...rects.map((b) => b.bottom));
  const spin = q(cfg.spin);
  return {
    x: left, y: top, w: right - left, h: bottom - top,
    text: (pill.innerText || "").trim(),
    aria: String(pill.getAttribute("aria-label") || ""),
    cls: String(pill.className),
    card: cardOn,
    spin: shown(spin),
    spin_anim: spin ? getComputedStyle(spin).animationName : "",
  };
}
"""

# 界面侧读数：标识的显隐/语气/字色/对比度、转圈的显隐与动画、卡片的标题行与行数。
APP_AUDIT_JS = r"""
() => {
  const q = (sel) => document.querySelector(sel);
  const text = (sel) => { const el = q(sel); return el ? (el.textContent || "").trim() : null; };
  const nums = (s) => { const m = String(s).match(/[0-9.]+/g); return m ? m.map(Number) : null; };
  const rgba = (s) => {
    const v = nums(s);
    return v && v.length >= 3 ? { rgb: v.slice(0, 3), a: v.length > 3 ? v[3] : 1 } : null;
  };
  const parse = (s) => {
    const m = String(s || "").trim().match(/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
    if (!m) return rgba(s);
    const h = m[1];
    const parts = h.length === 3 ? h.split("").map((c) => c + c)
                                 : [h.slice(0, 2), h.slice(2, 4), h.slice(4, 6)];
    return { rgb: parts.map((c) => parseInt(c, 16)), a: 1 };
  };
  const blend = (fg, under) => fg.rgb.map((v, i) => Math.round(v * fg.a + under[i] * (1 - fg.a)));
  const solid = (c, under) => (!c ? [0, 0, 0] : (c.a >= 1 ? c.rgb : blend(c, under)));
  /* 半透明底色要按 alpha 一层层叠到不透明为止，否则 tint 被当成纯白，对比度会算高 */
  const bgOf = (el) => {
    const layers = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const c = rgba(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
      node = node.parentElement;
    }
    let bg = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i -= 1) bg = blend(layers[i], bg);
    return bg;
  };
  const lum = (c) => {
    const f = (v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => (Math.max(lum(a), lum(b)) + 0.05) / (Math.min(lum(a), lum(b)) + 0.05);
  const shown = (el) => !!el && !el.hidden && getComputedStyle(el).display !== "none"
    && getComputedStyle(el).visibility !== "hidden";
  const badge = q("#phone-badge");
  const label = q("#phone-badge-text") || badge;
  const glyph = badge ? badge.querySelector("svg") : null;
  const spin = q("#phone-badge-spin");
  const card = q("#phone-pop");
  const rows = q("#phone-pop-rows");
  const bg = badge ? bgOf(badge) : [255, 255, 255];
  const out = {
    badge_found: !!badge,
    badge_shown: shown(badge),
    badge_cls: badge ? String(badge.className) : "",
    badge_aria: badge ? String(badge.getAttribute("aria-label") || "") : "",
    text_color: label ? getComputedStyle(label).color : "",
    same_as_ok: false,
    same_as_warn: false,
    bg: "rgb(" + bg.join(", ") + ")",
    contrast: 0,
    spin_found: !!spin,
    spin_shown: shown(spin),
    spin_anim: spin ? getComputedStyle(spin).animationName : "",
    glyph_found: !!glyph,
    blink_anim: glyph ? getComputedStyle(glyph).animationName : "",
    card_found: !!card,
    card_shown: shown(card),
    cap: text("#phone-pop-cap"),
    note: text("#phone-pop-note"),
    dts: rows ? rows.querySelectorAll("dt").length : -1,
    dds: rows ? rows.querySelectorAll("dd").length : -1,
  };
  if (label && badge) {
    const fg = solid(parse(getComputedStyle(label).color), bg);
    out.contrast = Math.round(ratio(fg, bg) * 100) / 100;
    const ok = parse(getComputedStyle(badge).getPropertyValue("--ok"));
    const warn = parse(getComputedStyle(badge).getPropertyValue("--warn"));
    out.same_as_ok = !!ok && fg.join(",") === solid(ok, bg).join(",");
    out.same_as_warn = !!warn && fg.join(",") === solid(warn, bg).join(",");
  }
  return out;
}
"""


def scrubbed(value) -> str:
    """打印前抹掉主机路径：出错信息里可能带仓库根或临时目录。"""
    text = str(value)
    for raw, token in ((str(ROOT), "<repo>"), (str(Path.cwd()), "<cwd>"),
                       (str(Path.home()), "~"), (tempfile.gettempdir(), "<temp>")):
        text = text.replace(raw, token).replace(raw.replace("\\", "/"), token)
    return text


def build_test_page(root: Path) -> str:
    """生产 index.html 原样保留，只在 app.js 之前插入测试桥。"""
    html = (root / "index.html").read_text(encoding="utf-8")
    marker = '<script src="app.js"></script>'
    if marker not in html:
        raise RuntimeError("index.html 结构变了：找不到 app.js 脚本标签")
    return html.replace(marker, '<script src="/qa/runtime_bridge.js"></script>\n  ' + marker, 1)


class _Handler(BaseHTTPRequestHandler):
    """按后缀给 Content-Type，只服务 root 里的普通文件；异常回固定串，不把路径交给页面。"""

    server_version = "topbar-phone-shots/1.0"
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
        handler = type("TopbarHandler", (_Handler,),
                       {"root": Path(root).resolve(), "inject_bridge": inject_bridge})
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="topbar-http", daemon=True)

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

    def problems(self) -> list:
        found = []
        if self.page_errors:
            found.append("pageerror：" + " | ".join(self.page_errors))
        if self.console:
            found.append("console error：" + " | ".join(self.console))
        if self.external:
            found.append("外部请求：" + " | ".join(self.external))
        return found


def png_size(target: Path):
    """校验 PNG 魔数并取宽高：读 IHDR，不装依赖。"""
    data = target.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) <= 512:
        raise ValueError("不是有效的 PNG（%d 字节）" % len(data))
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big"), len(data)


def open_page(browser, base: str, viewport, init_script=None):
    context = browser.new_context(viewport={"width": viewport[0], "height": viewport[1]})
    page = context.new_page()
    if init_script:
        page.add_init_script(init_script)
    return context, page, PageWatch(page, base)


def clip_cfg(side: str) -> dict:
    """两边的选择器：画板没有 id，界面侧用 id。卡尖界面侧还没有，选中什么算什么。"""
    if side == "board":
        return {"status": ".status", "badge": "",
                "card": 'div.sc[role="dialog"][aria-label="手机访问详情"]',
                "caret": "i.sc-caret", "spin": ".status .pill-spin"}
    return {"status": ".status", "badge": "#phone-badge", "card": "#phone-pop",
            "caret": "#phone-pop .sc-caret, #phone-pop-caret", "spin": "#phone-badge-spin"}


def shoot_region(page, side: str, viewport, target: Path):
    """算并集矩形再截一次；返回读数与 (宽, 高, 字节)。"""
    page.evaluate("window.scrollTo(0, 0)")
    info = page.evaluate(CLIP_JS, clip_cfg(side))
    if info.get("error"):
        raise RuntimeError(info["error"])
    x = max(0, int(info["x"]) - CLIP_PAD)
    y = max(0, int(info["y"]) - CLIP_PAD)
    w = min(int(info["w"]) + CLIP_PAD * 2, viewport[0] - x)
    h = min(int(info["h"]) + CLIP_PAD * 2, viewport[1] - y)
    if w <= 0 or h <= 0:
        raise RuntimeError("裁剪矩形为空：%dx%d" % (w, h))
    page.screenshot(path=str(target), clip={"x": x, "y": y, "width": w, "height": h})
    return info, png_size(target)


def audit_board(info: dict, row: dict) -> list:
    """画板侧只核对「截到的是这张画板」：文字提到该状态，卡片/转圈是否展开与场景一致。"""
    exp = row["expect"]
    problems = []
    if not info["text"]:
        problems.append("画板上手机标识没有文字")
    for word in exp["aria"]:
        if word not in info["aria"] and word not in info["text"]:
            problems.append("画板标识里没提到「%s」（实际：%s / %s）" % (word, info["text"], info["aria"]))
    if info["card"] != exp["card"]:
        problems.append("画板卡片展开状态不符：期望 %s，实际 %s" % (exp["card"], info["card"]))
    if info["spin"] != exp["spin"]:
        problems.append("画板转圈状态不符：期望 %s，实际 %s" % (exp["spin"], info["spin"]))
    return problems


def audit_app(info: dict, row: dict) -> list:
    """界面侧断言：显隐、语气类、字色与对比度、aria、卡片结构。"""
    exp = row["expect"]
    if not info["badge_found"]:
        return ["缺少 #phone-badge（界面侧还没落地？）"]
    problems = []
    if not info["badge_shown"]:
        problems.append("#phone-badge 应该显示，实际是收起的")
    cls = info["badge_cls"].split()
    # 转圈：只有 starting/stopping 该出现，出现时必须真的在动
    if exp["spin"]:
        if not info["spin_found"]:
            problems.append("缺少 #phone-badge-spin（开启/停止中的转圈元素）")
        elif not info["spin_shown"]:
            problems.append("#phone-badge-spin 应该显示，实际是收起的")
        elif info["spin_anim"] == "none":
            problems.append("#phone-badge-spin 的 animation-name 是 none，看不到转圈")
    elif info["spin_found"] and info["spin_shown"]:
        problems.append("#phone-badge-spin 只在 pending 时显示，现在不该出现")
    # 语气：connected 带 is-ok，waiting 带 is-warn + blink，已断开两个都不带
    tone = exp["tone"]
    if tone == "ok":
        if "is-ok" not in cls:
            problems.append("手机已连接时 class 缺 is-ok（实际：%s）" % info["badge_cls"])
        if "is-warn" in cls:
            problems.append("手机已连接时不该带 is-warn")
        if not info["same_as_ok"]:
            problems.append("#phone-badge-text 的字色 %s 不等于 --ok" % info["text_color"])
    elif tone == "warn":
        for word in ("is-warn", "blink"):
            if word not in cls:
                problems.append("等手机连接时 class 缺 %s（实际：%s）" % (word, info["badge_cls"]))
        if not info["glyph_found"]:
            problems.append("#phone-badge 里找不到 svg，看不到慢闪")
        elif info["blink_anim"] == "none":
            problems.append("等手机连接时 svg 的 animation-name 是 none，看不到慢闪")
        if not info["same_as_warn"]:
            problems.append("#phone-badge-text 的字色 %s 不等于 --warn" % info["text_color"])
    else:
        for word in ("is-ok", "is-warn"):
            if word in cls:
                problems.append("这个状态不该带 %s（实际：%s）" % (word, info["badge_cls"]))
    if info["contrast"] < MIN_CONTRAST:
        problems.append("#phone-badge-text 与底色 %s 的对比度 %.2f，低于 %.1f" % (info["bg"], info["contrast"], MIN_CONTRAST))
    # aria：非空且提到当前状态
    if not info["badge_aria"]:
        problems.append("#phone-badge 的 aria-label 是空的")
    else:
        for word in exp["aria"]:
            if word not in info["badge_aria"]:
                problems.append("aria-label 里没提到「%s」（实际：%s）" % (word, info["badge_aria"]))
    # 卡片：标题行、备注、dt/dd 组数
    if not exp["card"]:
        if info["card_found"] and info["card_shown"]:
            problems.append("#phone-pop 不该展开，实际开着")
        return problems
    if not info["card_found"] or not info["card_shown"]:
        problems.append("#phone-pop 应该展开，实际没开")
        return problems
    if info["cap"] != exp["cap"]:
        problems.append("#phone-pop-cap 是 %r，期望 %r" % (info["cap"], exp["cap"]))
    if not info["note"]:
        problems.append("#phone-pop-note 是空的")
    if info["dts"] != info["dds"]:
        problems.append("#phone-pop-rows 的 dt/dd 数量不等：%d/%d" % (info["dts"], info["dds"]))
    if exp["rows"] is not None and info["dts"] != exp["rows"]:
        problems.append("#phone-pop-rows 是 %d 组 dt/dd，期望 %d 组" % (info["dts"], exp["rows"]))
    return problems


def audit_invariants(page) -> list:
    """三条与场景无关的不变量，截完图后再摆：关掉收起、开着不转圈、没配对三行。"""
    problems = []

    def apply(state: dict, card: bool = False) -> dict:
        page.evaluate(APPLY_JS, {"state": state, "pending": "", "card": card})
        return page.evaluate(APP_AUDIT_JS)

    info = apply({"running": False, "link": "off", "paired_count": 0, "live_session": False})
    if not info["badge_found"]:
        problems.append("不变量：缺少 #phone-badge")
    elif info["badge_shown"]:
        problems.append("不变量：running=false、pending 空、link=off 时 #phone-badge 应收起")
    info = apply({"running": True, "link": "connected", "paired_count": 1,
                  "live_session": True}, True)
    if info["badge_found"] and not info["badge_shown"]:
        problems.append("不变量：手机已连接时 #phone-badge 应显示")
    if info["spin_shown"]:
        problems.append("不变量：pending 为空时 #phone-badge-spin 应收起")
    if "is-ok" not in info["badge_cls"].split():
        problems.append("不变量：已连接时 #phone-badge 的 class 应含 is-ok")
    info = apply({"paired_count": 0, "live_session": False}, True)
    if info["dts"] != 3 or info["dds"] != 3:
        problems.append("不变量：没配对时 #phone-pop-rows 应是 3 组 dt/dd，实际 %d/%d"
                        % (info["dts"], info["dds"]))
    return problems


def shoot_board(browser, base: str, row: dict, target: Path):
    """画板侧：直接打开那张已经摆好状态的画板，等运行时画完再截顶栏与卡片的并集。"""
    context, page, watch = open_page(browser, base, row["viewport"])
    try:
        page.goto(base + "/" + row["board"], wait_until="domcontentloaded", timeout=30000)
        # 画布运行时先把内容画出来；顶栏出现即说明场景已经摆好
        page.wait_for_function("!!document.querySelector('.status button.pill')", timeout=20000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.wait_for_timeout(600)
        info, size = shoot_region(page, "board", row["viewport"], target)
        problems = watch.problems() + audit_board(info, row)
    finally:
        context.close()
    return problems, size


def shoot_app(browser, base: str, row: dict, target: Path):
    """界面侧：起桥 → 等模块图 → 写快照 → 重画 → 要卡片就展开 → 截并集 → 跑断言。"""
    context, page, watch = open_page(browser, base, row["viewport"],
                                     "window.__QA_SCENARIO = %s;" % json.dumps(BRIDGE_SCENARIO))
    try:
        page.goto(base + "/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_function(APP_READY, timeout=20000)
        page.evaluate(APPLY_JS, {"state": row["state"], "pending": row["pending"],
                                 "card": row["card"], "busy": False})
        page.wait_for_timeout(200)
        info, size = shoot_region(page, "app", row["viewport"], target)
        audit = page.evaluate(APP_AUDIT_JS)
        problems = watch.problems() + audit_app(audit, row) + audit_invariants(page)
    finally:
        context.close()
    return problems, size


def write_pairs(out_dir: Path, scenes) -> None:
    """pairs.md 骨架：每个场景一行，画板缺失写原因，结论看完图再填。"""
    lines = [
        "# 顶栏手机状态：画板与本地界面对照",
        "",
        "每个场景一行。宽度是浏览器视口宽（1280 为原型画布宽度）。画板列写画板文件与产物，"
        "没有画板的场景写原因——那是已知情况，不当失败。结论看完图再写，"
        "保留 `待看图填写` 表示还没看。",
        "",
        "| 场景 | 宽度 | 画板 | 界面 | 结论 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in scenes:
        board = ("`%s` → `%s-board.png`" % (row["board"], row["id"]) if row["board"]
                 else "（%s）" % row["board_why"])
        lines.append("| %s | %d | %s | `%s-app.png` | 待看图填写 |" % (row["id"], row["viewport"][0], board, row["id"]))
    (out_dir / "pairs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def scene_names(row: dict) -> tuple:
    """--only 认的名字：场景 id，以及画板文件名去后缀。"""
    board = str(row["board"] or "")
    names = [str(row["id"]).lower()]
    if board:
        names.append((board[:-len(BOARD_SUFFIX)] if board.endswith(BOARD_SUFFIX)
                      else Path(board).stem).lower())  # PhGoneTop.dc.html → phgonetop
    return tuple(names)


def select_scenes(tokens, sides: str):
    """--only 里 board/app 选边，其余按场景 id 或画板名过滤（大小写不敏感）。"""
    chosen = set(SIDES) if sides == "both" else {sides}
    names: list[str] = []
    for chunk in tokens:
        for item in str(chunk).replace("，", ",").split(","):
            item = item.strip()
            if item and item.lower() in SIDES:
                chosen &= {item.lower()}
            elif item:
                names.append(item.lower())
    scenes = [row for row in SCENES if not names or any(name in scene_names(row) for name in names)]
    if not scenes:
        raise SystemExit("--only 没匹配到场景：%s\n可用：%s"
                         % ("、".join(tokens), "、".join(row["id"] for row in SCENES)))
    return scenes, [side for side in SIDES if side in chosen]


def start_server(root: Path, inject_bridge: bool, servers: list) -> str:
    try:
        server = StaticServer(root, inject_bridge).start()
    except OSError as exc:
        print("端口绑定失败（可能被占用）：" + scrubbed(exc))
        raise SystemExit(2)
    servers.append(server)
    return server.base


def run_shots(browser, bases: dict, scenes, sides, out_dir: Path):
    """逐格截图与断言；单格失败不打断整轮，最后统一汇总。"""
    failures: list[str] = []
    bad_images = 0
    shots = 0
    for row in scenes:
        for side in sides:
            if side == "board" and not row["board"]:
                print("[skip] %s board %s" % (row["id"], row["board_why"]))
                continue
            shots += 1
            target = out_dir / ("%s-%s.png" % (row["id"], side))
            shoot = shoot_board if side == "board" else shoot_app
            try:
                problems, size = shoot(browser, bases[side], row, target)
            except Exception as exc:  # noqa: BLE001 - 单格失败不打断整轮
                problems, size = ["截图失败：" + (str(exc) or exc.__class__.__name__)], None
            if size:
                print("[%s] %s %s %dx%d %.1f KB"
                      % ("ok" if not problems else "fail", row["id"], side,
                         size[0], size[1], size[2] / 1024.0))
            else:
                print("[fail] %s %s 没有生成图片" % (row["id"], side))
            if problems:
                bad_images += 1
            for problem in problems:
                print("       " + scrubbed(problem))
                failures.append("%s %s: %s" % (row["id"], side, scrubbed(problem)))
    return failures, bad_images, shots


def check_inputs(scenes, sides) -> None:
    if "board" in sides:
        missing = [row["board"] for row in scenes if row["board"] and not (PROTO / row["board"]).is_file()]
        if missing:
            raise SystemExit("缺少画板文件：" + "、".join(missing))
    if "app" in sides:
        for path in (UI / "index.html", BRIDGE):
            if not path.is_file():
                raise SystemExit("缺少界面文件：" + str(path.relative_to(ROOT)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="顶栏手机状态的画板与界面并排截图")
    parser.add_argument("--out", default=str(OUT_DEFAULT),
                        help="输出目录，默认 design/evidence/2026-11-15/topbar-phone/shots")
    parser.add_argument("--only", action="append", default=[], metavar="名字",
                        help="只跑这些场景/画板，可重复或逗号分隔；board / app 表示只跑某一侧")
    parser.add_argument("--sides", choices=("both", "board", "app"), default="both",
                        help="跑哪一侧，默认两边都跑")
    args = parser.parse_args(argv)
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
                failures, bad_images, shots = run_shots(browser, bases, scenes, sides, out_dir)
            finally:
                browser.close()
    finally:
        for server in servers:
            server.stop()

    if failures:
        print("失败 %d 条 / 共 %d 张图，其中 %d 张有问题"
              % (len(failures), shots, bad_images))
        return 1
    print("全部 %d 张图通过：没有 pageerror、console error、外部请求与顶栏断言问题" % shots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
