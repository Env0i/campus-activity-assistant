#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本机 UI 的离线浏览器验收：原样加载 local/ui，只注入测试桥。

用法（只在获得运行授权后执行）：

    python -X utf8 tools/qa_runtime_reliability.py \\
        --host 127.0.0.1 --port 8388 \\
        --evidence-root %TEMP%/campus-qa/browser --run

覆盖面（决策 012 返修后的全量场景）：
- 顶栏唯一时间入口与独立北京时间：boot 前 / 运行中注入 ±8 小时 / ±30 天的
  系统墙钟错时，直接读 #clock-time、等待 LED、任务卡、现在线与登录详情，
  对照测试桥的固定权威 epoch（window.__QA_CLOCK_NOW），不硬编码具体日期；
- 真正执行 page.reload 模拟 F5：同代旧采样不回退、旧代次不覆盖、
  同代不可用不抹锚点、更高代次才更新、F5 后按权威快照恢复；
- holdover 300/900 秒边界、首校时延迟、真实指针点击重新校时、
  失败反馈只落在时间详情，不触发 login/start_plan；
- 全界面文案行为证据：四态登录与未知小时数、首次登录绿色结论不重复、
  忙时胶囊保持登录结论、已报名移出计划不调用学校取消；
- 五视口 980/1120/1280/746/680：正式名称单行、唯一入口、焦点归还、
  详情不越界、未知状态不挤掉帮助与登录操作；
- 新工作台（决策 014）五视口 1280×800 / 1120×800 / 980×720 / 746×512 / 680×480：
  草稿、计划栏打开、计划运行、设置抽屉打开四个时刻都无横向滚动，刷新、设置、帮助、
  开始 / 停止都在视口内且中心点真的点得到；登录按钮在登录状态卡里，浏览器登录走
  重新登录对话框的「改用浏览器登录」；胶囊只写上次校验时刻，不写剩余时间；
- pageerror / console 错误 / 外部请求一律 0，违例直接判失败。

约束：
- 只绑定 127.0.0.1；端口占用直接报错退出，不杀占用者；
- 生产四文件原样读取，测试页只在 app.js 之前插入 runtime_bridge.js；
- 外部请求全部拦截并记录（页面不允许访问学校 / GitHub）；
- 使用已安装的 Edge（channel=msedge）；装不了就标 blocked，禁止安装依赖；
- 每个场景保存 DOM 断言、viewport、截图绝对路径与失败原因。

@author Author
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "local" / "ui"
BRIDGE = ROOT / "local" / "tests" / "fixtures" / "runtime_bridge.js"
# 静态资源按后缀决定 Content-Type。旧写法是列举 4 个文件的 SCREENSHOT_FILES，
# UI 拆成 state/controllers/views 多目录后其余 28 个模块全部 404，页面直接
# `S is not defined`——工具自己在腐烂，却只报成「场景断言失败」，还因为
# 截图断言看体积而留下假绿。改成服务 UI 目录内任意文件，后缀不在表里才 404。
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
# 与 local/app.py 的 TERMS_VERSION 必须同值，契约测试 test_qa_bridge_contract 会核对
TERMS_VERSION = "2026-11-03-r4"


def _ui_root() -> Path:
    """当前服务的 UI 目录；指定 --ui-root 时指向复现用的临时副本。

    副本只用于证明「修复前的缺陷确实会被断言抓住」，正式场景永远读生产 UI。
    """
    override = getattr(QaHandler, "ui_root", None)
    return Path(override) if override else UI


def build_test_page() -> str:
    """生产 index.html 原样保留，只在 led.js 之前插入测试桥。"""
    html = (_ui_root() / "index.html").read_text(encoding="utf-8")
    marker = '<script src="led.js"></script>'
    if marker not in html:
        raise RuntimeError("index.html 结构变了：找不到 led.js 脚本标签")
    return html.replace(marker, '<script src="/qa/runtime_bridge.js"></script>\n  ' + marker, 1)


class QaHandler(BaseHTTPRequestHandler):
    server_version = "campus-qa/1.0"

    def log_message(self, fmt, *args):  # noqa: A003 - 保持静默，证据走报告
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
            if path in ("/", "/index.html", "/qa.html"):
                self._send(200, "text/html; charset=utf-8", build_test_page().encode("utf-8"))
                return
            if path == "/qa/runtime_bridge.js":
                self._send(200, "application/javascript; charset=utf-8",
                           BRIDGE.read_bytes())
                return
            name = path.lstrip("/")
            target = (_ui_root() / name).resolve()
            root = _ui_root().resolve()
            ctype = CTYPES.get(target.suffix.lower())
            # is_relative_to 一并挡住 .. 与绝对路径；隐藏文件不对外暴露
            inside = (ctype is not None and target.is_file()
                      and target.is_relative_to(root)
                      and not any(part.startswith(".")
                                  for part in target.relative_to(root).parts))
            if inside:
                self._send(200, ctype, target.read_bytes())
                return
            self._send(404, "text/plain; charset=utf-8", b"not found")
        except Exception as exc:  # noqa: BLE001 - 500 只回固定串，不把内部绝对路径交给页面
            traceback.print_exception(exc)  # 真实原因打在本机控制台
            self._send(500, "text/plain; charset=utf-8", "静态文件读取失败".encode("utf-8"))


class QaServer:
    def __init__(self, host: str, port: int, ui_root=None):
        QaHandler.ui_root = str(ui_root) if ui_root else None
        self.httpd = ThreadingHTTPServer((host, port), QaHandler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="qa-http", daemon=True)
        self.host = host
        self.port = self.httpd.server_address[1]

    @property
    def base(self) -> str:
        return "http://%s:%d" % (self.host, self.port)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class Session:
    """一个场景的页面会话：收集断言、截图、控制台与外部请求。"""

    def __init__(self, browser, base: str, evidence: Path, scenario: dict):
        self.browser = browser
        self.base = base
        self.evidence = evidence
        self.scenario = scenario
        self.assertions = []
        self.actions = []
        self.screenshots = []
        self.console = []
        self.page_errors = []
        self.external = []
        width, height = scenario["viewport"]
        context_args = {"viewport": {"width": width, "height": height}}
        if scenario.get("timezone"):
            context_args["timezone_id"] = scenario["timezone"]
        self.context = browser.new_context(**context_args)
        self.page = self.context.new_page()
        self.page.add_init_script(
            "window.__QA_SCENARIO = %s;" % json.dumps(scenario["bridge"]))
        self.page.on("console", self._on_console)
        self.page.on("pageerror", self._on_page_error)
        self.page.route("**/*", self._route)
        self.page.goto(base + "/", wait_until="domcontentloaded")
        self.page.wait_for_function(
            "window.pywebview && window.__QA_CALLS && document.querySelector('#pill')",
            timeout=15000)

    # ---- 采集 -------------------------------------------------------
    def _on_console(self, message):
        if message.type in ("error", "warning"):
            self.console.append({"type": message.type, "text": message.text})

    def _on_page_error(self, error):
        self.page_errors.append(str(error))

    def _route(self, route):
        url = route.request.url
        if url.startswith(self.base) or url.startswith("data:") or url.startswith("about:"):
            route.continue_()
            return
        self.external.append(url)
        route.abort()

    # ---- 断言 -------------------------------------------------------
    def check(self, label: str, ok: bool, detail: str = "") -> None:
        self.assertions.append({"check": label, "ok": bool(ok), "detail": str(detail)})

    def check_contains(self, selector: str, needle: str) -> None:
        text = self.text(selector)
        self.check("%s 含「%s」" % (selector, needle), needle in text, text[:120])

    def check_not_contains(self, selector: str, needle: str) -> None:
        text = self.text(selector)
        self.check("%s 不含「%s」" % (selector, needle), needle not in text, text[:120])

    def shot(self, name: str) -> str:
        path = self.evidence / ("%s-%s.png" % (self.scenario["id"], name))
        self.page.screenshot(path=str(path), full_page=False)
        # 截图是证据不是断言：旧写法按 size>2000 判「过」，失败现场的大截图
        # 反而必然通过，等于给失败场景发绿灯。这里只校验文件真的是 PNG：
        # 只看非空等于恒真（playwright 写不出 0 字节），魔数才是能被写坏的证据。
        size = path.stat().st_size if path.exists() else 0
        head = path.open("rb").read(8) if path.exists() else b""
        self.check("截图 %s 是有效 PNG" % path.name,
                   head == b"\x89PNG\r\n\x1a\n" and size > 512,
                   "head=%r bytes=%d" % (head, size))
        self.screenshots.append(str(path.resolve()))
        return str(path)

    # ---- 交互 -------------------------------------------------------
    def text(self, selector: str) -> str:
        return self.page.locator(selector).first.inner_text()

    def count(self, selector: str) -> int:
        return self.page.locator(selector).count()

    def attr(self, selector: str, name: str):
        return self.page.locator(selector).first.get_attribute(name)

    def js(self, expression, arg=None):
        return self.page.evaluate(expression, arg) if arg is not None \
            else self.page.evaluate(expression)

    def wait(self, expression: str, timeout: int = 8000) -> None:
        self.page.wait_for_function(expression, timeout=timeout)

    def set_state(self, **values) -> None:
        self.js("(s) => Object.assign(window.__QA_STATE, s)", values)

    def emit(self, kind: str, payload: dict) -> None:
        self.js("([k, p]) => window.__QA_EMIT(k, p)", [kind, payload])

    def click(self, selector: str) -> None:
        self.page.locator(selector).first.click()

    def pick(self, activity_id: str) -> None:
        """真实 DOM 点击复选框：列表会整块重绘，避免 Playwright 的
        「点击后再校验同一元素」被重绘打断；仍然走生产 change 处理器。"""
        selector = "input.row-check[data-id=%s]" % json.dumps(activity_id)
        self.js("(sel) => document.querySelector(sel).click()", selector)
        self.wait("S.selected.has(%s)" % json.dumps(activity_id))

    def pointer(self, selector: str, label: str) -> dict:
        """用真实 Playwright 指针点一次，并记录几何与命中目标。

        这是 FR07 的核心证据：`is_visible()` 只证明元素在 DOM 里有尺寸，
        不证明它落在滚动容器的可视交集里、也不证明那个坐标真的点得到它。
        """
        locator = self.page.locator(selector).first
        locator.scroll_into_view_if_needed()
        box = locator.bounding_box() or {}
        center = [box.get("x", 0) + box.get("width", 0) / 2,
                  box.get("y", 0) + box.get("height", 0) / 2]
        # 命中目标解析：点到图标/文字子节点也算命中按钮，取最近的带 id 祖先
        hit = self.js(
            "([x, y]) => { const el = document.elementFromPoint(x, y);"
            " if (!el) return { tag: '', id: '', dataId: '' };"
            " const owner = el.closest ? el.closest('[id]') : null;"
            " return { tag: el.tagName, id: owner ? owner.id : '',"
            "          dataId: el.getAttribute('data-id') || '' }; }",
            center)
        record = {"action": label, "selector": selector,
                  "box": {k: round(v, 1) for k, v in box.items()},
                  "center": [round(v, 1) for v in center], "hit": hit}
        locator.click()          # 真实指针，不是 JS 调用处理器
        record["clicked"] = True
        self.actions.append(record)
        return record

    def pointer_pick(self, activity_id: str) -> dict:
        """真实指针勾选：滚到行内再点，最后校验选择真的变了。"""
        selector = "input.row-check[data-id=%s]" % json.dumps(activity_id)
        record = self.pointer(selector, "pick:%s" % activity_id)
        self.wait("S.selected.has(%s)" % json.dumps(activity_id))
        record["selected"] = True
        return record

    def inject(self, script: str) -> None:
        """在页面脚本之前注入数据准备代码（跨 reload 生效）。

        只用于提供「后端本来就会给的数据」，不替换任何生产函数。
        """
        self.page.add_init_script(script)

    def settle(self, timeout: int = 8000) -> None:
        """等首屏 check/list 都落定：空态与指标必须基于真实结论断言。"""
        self.page.wait_for_function(
            "S.listState === 'ready' || S.listState === 'error'", timeout=timeout)
        self.page.wait_for_function("S.login.checking === false", timeout=timeout)

    def close(self) -> None:
        try:
            self.context.close()
        except Exception:
            pass

    # ---- 独立北京时间断言（对照测试桥的固定权威 epoch，不硬编码日期）----
    def qa_now(self) -> float:
        """测试桥的权威业务时刻（秒）。"""
        return float(self.js("window.__QA_CLOCK_NOW()"))

    def wait_business_ready(self, timeout: int = 12000) -> None:
        """等锚点建立且顶栏显示真实时分秒。"""
        self.wait("(S.businessClock.state === 'ready' || S.businessClock.state === 'holdover') "
                  "&& document.querySelector('#clock-time').textContent.includes(':')",
                  timeout)

    def check_clock_text(self, label: str) -> None:
        """顶栏 #clock-time 必须等于权威北京时间（±1 秒进位容差）。"""
        data = self.js("""() => {
          const fmt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
          const nowS = window.__QA_CLOCK_NOW();
          const at = (d) => fmt.format(new Date((nowS + d) * 1000));
          return { text: document.querySelector('#clock-time').textContent.trim(),
                   candidates: [at(-1), at(0), at(1)],
                   ui: document.querySelector('#clock').dataset.state };
        }""")
        self.check(label, data["text"] in data["candidates"], data)

    def check_unique_clock(self) -> None:
        """顶栏只允许一个时间入口（按钮 + 详情浮层各一个）。"""
        data = self.js("() => ({ clock: document.querySelectorAll('#clock').length,"
                       " pop: document.querySelectorAll('#clock-pop').length,"
                       " kind: document.querySelectorAll('button.clock').length })")
        self.check("顶栏只有一个时间入口",
                   data == {"clock": 1, "pop": 1, "kind": 1}, data)

    def check_topbar_layout(self, tag: str) -> None:
        """正式名称与时钟标签单行，帮助/登录/时钟都可达且无横向滚动。"""
        data = self.js("""() => {
          const brand = document.querySelector('.brand-name');
          const shown = Array.from(brand.children)
            .find((c) => getComputedStyle(c).display !== 'none');
          const fs = parseFloat(getComputedStyle(shown).fontSize) || 13;
          const label = document.querySelector('#clock-label');
          const rect = (sel) => {
            const el = document.querySelector(sel);
            return el ? el.getBoundingClientRect() : { width: 0, right: 0, left: 0 };
          };
          const help = rect('#btn-help');
          /* 新工作台：登录按钮收进登录状态卡，顶栏的登录入口是状态胶囊 #pill */
          const login = rect('#pill');
          const settings = rect('#btn-settings');
          const refresh = rect('#btn-refresh');
          const clock = rect('#clock');
          return {
            brandLines: Math.round(shown.getBoundingClientRect().height / (fs * 1.35)),
            clockLabelLines: label ? Math.round(label.getBoundingClientRect().height /
              ((parseFloat(getComputedStyle(label).fontSize) || 12) * 1.35)) : 0,
            clockText: document.querySelector('#clock-time').textContent.trim(),
            helpReachable: help.width > 0 && help.right <= window.innerWidth + 1,
            settingsReachable: settings.width > 0 && settings.right <= window.innerWidth + 1,
            refreshReachable: refresh.width > 0 && refresh.right <= window.innerWidth + 1,
            loginReachable: login.width > 0 && login.left < window.innerWidth,
            clockReachable: clock.width > 0 && clock.right <= window.innerWidth + 1,
            noHScroll: document.documentElement.scrollWidth
              <= document.documentElement.clientWidth + 1,
          };
        }""")
        self.check("%s：正式名称单行" % tag, data["brandLines"] <= 1, data)
        self.check("%s：时钟标签单行" % tag, data["clockLabelLines"] <= 1, data)
        self.check("%s：帮助仍可达" % tag, data["helpReachable"], data)
        self.check("%s：设置仍可达" % tag, data["settingsReachable"], data)
        self.check("%s：刷新仍可达" % tag, data["refreshReachable"], data)
        self.check("%s：登录状态胶囊仍可达" % tag, data["loginReachable"], data)
        self.check("%s：时钟仍可达" % tag, data["clockReachable"], data)
        self.check("%s：无横向滚动" % tag, data["noHScroll"], data)
        return data

    def check_last_check_pill(self) -> None:
        """已登录时胶囊旁只写上次向学校校验的时刻（架构方案 4.5），不写剩余时间。

        取代旧的「#pill-sub 含约剩」：学校不公布有效期，工具不估算；桥在 check 事件里
        带 last_check_at（与 app._last_check_fields 同形），胶囊显示成「HH:MM 校验」。"""
        sub = self.text("#pill-sub").strip()
        self.check("#pill-sub 写上次校验时刻", sub.endswith(" 校验") and len(sub) == len("14:20 校验"), sub)
        self.check("#pill-sub 不写剩余时间", "约剩" not in sub and "小时" not in sub, sub)

    def browser_login(self, label: str = "login") -> dict:
        """新工作台的浏览器登录路径：点胶囊固定登录卡 → 「登录 / 重新登录」→ 对话框里「改用浏览器登录」。

        登录按钮不在顶栏了，在登录状态卡里；点了先开重新登录对话框（设计 9.3 四种情况）。
        QA 不输账号密码，只走浏览器登录这条路，后端收到的仍是一次 login 调用。"""
        self.pointer("#pill", label + ":open-card")
        self.wait("!document.querySelector('#login-pop').hidden", 4000)
        rec = self.pointer("#btn-login", label)
        self.wait("document.querySelector('#dlg-relogin').open === true", 4000)
        self.pointer("#btn-rl-browser", label + ":browser")
        return rec

    def emit_clock(self, bump: bool = True, **patch) -> None:
        """改桥注入并按生产语义重发权威快照；generation 不前进会被 UI 拒收。"""
        if patch:
            self.set_state(**patch)
        if bump:
            self.js("() => { window.__QA_STATE.clockGen ="
                    " (Number(window.__QA_STATE.clockGen) || 1) + 1; }")
        self.js("() => window.__QA_EMIT('business_clock', window.__QA_CLOCK_STATE())")

    def inject_state(self, **values) -> None:
        """页面脚本前注入桥状态（跨 reload 生效）；用于 boot 前的错时/失效。"""
        self.inject("window.__QA_STATE = Object.assign(window.__QA_STATE || {}, %s);"
                    % json.dumps(values, ensure_ascii=False))

    def inject_wall_skew(self, offset_ms: int) -> None:
        """在页面脚本前把 Date.now 整体偏移（不改系统时间/时区，只影响沙箱）。"""
        self.inject("const __qaRealNow = Date.now.bind(Date);"
                    "Date.now = () => __qaRealNow() + %d;" % offset_ms)

    def skew_wall_now(self, offset_ms: int) -> None:
        """运行中把 Date.now 偏移（不 reload）；performance 单调外推不受影响。"""
        self.js("(off) => { const r = Date.now.bind(Date);"
                "Date.now = () => r() + off; }", offset_ms)

    def check_nowline(self, label: str) -> None:
        """「现在」线必须按北京时间显示（±1 分钟容差）。"""
        data = self.js("""() => {
          const chip = document.querySelector('[data-now]');
          if (!chip) return null;
          const fmt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai',
            hour: '2-digit', minute: '2-digit', hour12: false });
          const nowS = window.__QA_CLOCK_NOW();
          return { text: chip.textContent.trim(),
                   candidates: [fmt.format(new Date((nowS - 60) * 1000)),
                                fmt.format(new Date(nowS * 1000)),
                                fmt.format(new Date((nowS + 60) * 1000))] };
        }""")
        self.check(label, bool(data) and data["text"] in data["candidates"],
                   data or "页面上没有现在线")

    def calls_count(self, name: str) -> int:
        return int(self.js("window.__QA_CALLS.filter((c) => c.name === '%s').length" % name))

    def hit_in(self, record: dict, selector: str) -> bool:
        """命中坐标必须落在 selector（或其后代）上；子元素 id 不同也算命中。"""
        center = record.get("center") or []
        if len(center) != 2:
            return False
        return bool(self.js(
            "([x, y]) => { const el = document.elementFromPoint(x, y);"
            " return !!el && !!el.closest(%s); }" % json.dumps(selector), center))


def _task(task_id, activity_id, name, status, stop=None, attempts=0, reason="", **extra):
    payload = {"plan_id": "qa-plan", "task_id": task_id, "activity_id": activity_id,
               "name": name, "sign_start": "", "sign_end": "", "status": status,
               "attempts": attempts, "reason": reason}
    if stop:
        payload["stop_reason"] = stop
    payload.update(extra)
    return payload


SCENARIOS = []


def scenario(sid, title, viewport, bridge="valid", settle=True, timezone=None):
    def deco(fn):
        SCENARIOS.append({"id": sid, "title": title, "viewport": viewport,
                          "bridge": bridge, "settle": settle, "timezone": timezone, "run": fn})
        return fn
    return deco


@scenario("demo-mode", "演示模式可开始且策略可见", (1120, 800), "demo")
def _(s: Session):
    s.check_contains("#pill-text", "演示模式")
    s.check_unique_clock()
    s.check_topbar_layout("演示模式 1120")
    s.check("顶栏时钟标注演示时间", s.attr("#clock", "data-state") == "demo"
            and s.text("#clock-label").strip() == "演示时间",
            [s.attr("#clock", "data-state"), s.text("#clock-label")])
    s.check("演示时间入口可访问名称同步", "演示时间" in (s.attr("#clock", "aria-label") or ""),
            s.attr("#clock", "aria-label"))
    s.wait("S.listState === 'ready'")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.check("#演示模式策略控件可见", s.page.locator("#retry-for").is_visible())
    s.check("#演示模式开始按钮可见", s.page.locator("#btn-plan").is_visible())
    s.shot("demo-ready")


# ------------------------------------------------------------ 条款门场景
# 这些场景补的是「浏览器里 0 覆盖」的四条拒绝路径：状态未知、未同意、
# 已拒绝、版本不匹配。它们断言的是 HEAD 的拆分版前端；v1.1.1 实包的同名
# 行为仍要走 B01 手工切片（包内是单体 app.js，行号不同）。

def _gate_disabled(s: Session) -> list:
    """条款门禁的三入口状态：[登录, 刷新, 开始]。"""
    return s.js("() => ['#btn-login', '#btn-refresh', '#btn-plan']"
                ".map((q) => document.querySelector(q).disabled)")


def _dialog_open(s: Session) -> bool:
    return bool(s.js("() => document.querySelector('#dlg-terms').open"))


@scenario("terms-unknown-gate", "后端没给条款状态：未知态横幅 + 三入口停用 + 不自动弹窗",
          (1120, 800), "terms_absent", settle=False)
def _(s: Session):
    s.wait("S.terms.unknown === true")
    s.check_contains("#banners", "条款状态没能确认")
    disabled = _gate_disabled(s)
    s.check("条款未知时登录/刷新/开始全部停用", disabled == [True, True, True], disabled)
    s.check("未知态不自动弹条款（要用户自己点开才可确认）", not _dialog_open(s))
    s.shot("unknown")


@scenario("terms-first-run-decline", "首启强弹条款；拒绝后落盘 declined_version 且保持停用",
          (1120, 800), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.wait("S.terms.unknown === false")
    s.check("程序版本与内嵌全文同版",
            s.text("#dlg-terms-version").strip() == TERMS_VERSION
            and s.text("#dlg-terms-document-version").strip() == TERMS_VERSION,
            [s.text("#dlg-terms-version"), s.text("#dlg-terms-document-version")])
    disabled = _gate_disabled(s)
    s.check("未同意时三入口停用", disabled == [True, True, True], disabled)
    s.shot("dialog")
    s.click("#btn-terms-decline")
    s.wait("!document.querySelector('#dlg-terms').open")
    s.check_contains("#banners", "还没有同意使用条款")
    s.check("会话进入 declined 语义", s.js("() => S.terms.declined") is True)
    # 落盘是异步的：等 IPC 回写真的到，别拿「弹窗已关」当「设置已存」
    s.wait("(window.__QA_STATE.savedPrefs || {}).terms_declined_version === '%s'" % TERMS_VERSION)
    s.check("拒绝写入本版 declined_version",
            s.js("() => (window.__QA_STATE.savedPrefs || {}).terms_declined_version")
            == TERMS_VERSION,
            s.js("() => (window.__QA_STATE.savedPrefs || {}).terms_declined_version"))
    disabled = _gate_disabled(s)
    s.check("拒绝后三入口仍停用（拒绝不是放行）", disabled == [True, True, True], disabled)
    s.shot("declined")


@scenario("terms-accept-unlocks", "同意条款后清空 declined 落盘并解锁首轮加载",
          (1120, 800), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    # 方案 A（条款文档化）：同意按钮先禁用，必须先勾选再点，勾选是纯前端态
    s.check("未勾选时同意按钮禁用",
            s.js("() => document.querySelector('#btn-terms-accept').disabled") is True)
    s.click("#chk-terms-agree")
    s.check("勾选后同意按钮解锁",
            s.js("() => document.querySelector('#btn-terms-accept').disabled") is False)
    s.click("#btn-terms-accept")
    s.wait("!document.querySelector('#dlg-terms').open")
    s.wait("S.terms.acceptedVersion === '%s'" % TERMS_VERSION)
    s.check("同意回执带 accepted_at", bool(s.js("() => S.terms.acceptedAt")))
    s.check("同意后落盘空的 declined_version",
            s.js("() => (window.__QA_STATE.savedPrefs || {}).terms_declined_version") == "",
            s.js("() => (window.__QA_STATE.savedPrefs || {}).terms_declined_version"))
    s.check("同意后未确认标记被清掉", s.js("() => S.terms.unknown") is False)
    s.check_not_contains("#banners", "还没有同意使用条款")
    s.wait("S.listState === 'ready' || S.listState === 'error'")
    s.check("登录与刷新恢复可点",
            s.js("() => !document.querySelector('#btn-login').disabled"
                 " && !document.querySelector('#btn-refresh').disabled"),
            _gate_disabled(s))
    s.shot("accepted")


@scenario("terms-short-window", "420 高的窄窗：底栏三个动作仍在视口内、阅读区自己滚",
          (746, 420), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    geo = s.js("""() => {
      const vh = window.innerHeight;
      const pick = (sel) => { const el = document.querySelector(sel); if (!el) return null;
        const r = el.getBoundingClientRect();
        return { sel: sel, bottom: Math.round(r.bottom), top: Math.round(r.top),
                 w: Math.round(r.width), h: Math.round(r.height) }; };
      const body = document.querySelector('.terms-body');
      return { vh: vh, btns: ['#btn-terms-decline', '#btn-terms-accept'].map(pick).filter(Boolean),
               bodyScrolls: body.scrollHeight > body.clientHeight + 1 };
    }""")
    out = [b["sel"] for b in geo["btns"] if b["bottom"] > geo["vh"] + 1 or b["h"] < 20]
    s.check("420 高时两个动作仍在视口内且没被压没", out == [], out)
    s.check("420 高时阅读区自己滚（不是整窗溢出）", geo["bodyScrolls"] is True, geo["bodyScrolls"])
    s.shot("short-window")
    s.click("#btn-terms-full")
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    s.click("#tab-terms-privacy")
    s.check("短窗里 tab 照样能切",
            s.js("() => document.querySelector('#doc-terms-privacy').hidden === false") is True)
    s.shot("short-window-fulltext")


@scenario("terms-fulltext-tabs", "两份文档用 tab 切换：切过去就只看到那一份",
          (1120, 800), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.click("#btn-terms-full")
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    s.check("默认停在用户协议",
            s.js("() => document.querySelector('#doc-terms-agreement').hidden === false"
                 " && document.querySelector('#doc-terms-privacy').hidden === true") is True)
    s.click("#tab-terms-privacy")
    s.check("切到隐私政策后两份互斥",
            s.js("() => document.querySelector('#doc-terms-agreement').hidden === true && document.querySelector('#doc-terms-privacy').hidden === false") is True)
    s.check("tab 的 aria-pressed 跟着走（button 不用 aria-selected）",
            s.js("() => document.querySelector('#tab-terms-privacy').getAttribute('aria-pressed') === 'true' && document.querySelector('#tab-terms-agreement').getAttribute('aria-pressed') === 'false'") is True)
    s.check("没有残留的 tab 语义",
            s.js("() => !document.querySelector('#tab-terms-agreement').hasAttribute('role') && !document.querySelector('#tab-terms-agreement').hasAttribute('aria-selected')") is True)
    s.check("切到的那份内容确实是隐私政策",
            s.text("#doc-terms-privacy h4").strip() == "隐私政策")
    s.shot("privacy-pane")
    s.click("#tab-terms-agreement")
    s.check("切回来",
            s.js("() => document.querySelector('#doc-terms-agreement').hidden === false && document.querySelector('#doc-terms-privacy').hidden === true") is True)


_LICENSE_CALLS_JS = "() => window.__QA_CALLS.filter((c) => c.name === 'get_license_text').length"


@scenario("terms-links-license", "正文/勾选行内联蓝链开全文切页签；MIT 页签经桥懒加载、缓存与就地重试",
          (1120, 800), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    # ① 副行两处内联链接：存在、蓝色下划线、点击打开全文并切对应页签
    links = s.js("""() => [...document.querySelectorAll('#dlg-terms-sub button.doc-link')]
      .map((b) => ({ doc: b.getAttribute('data-doc'), text: b.textContent.trim(),
                     color: getComputedStyle(b).color,
                     underline: getComputedStyle(b).textDecorationLine }))""")
    s.check("副行恰有两个 doc-link（协议/隐私）且蓝色下划线",
            [l["doc"] for l in links] == ["agreement", "privacy"]
            and all(l["color"] == "rgb(30, 90, 140)" and l["underline"] == "underline"
                    for l in links), links)
    s.click('#dlg-terms-sub button.doc-link[data-doc="agreement"]')
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    s.check("点《用户协议》打开全文并停在协议页签",
            s.js("() => document.querySelector('#tab-terms-agreement').classList.contains('is-on')"
                 " && document.querySelector('#doc-terms-agreement').hidden === false") is True)
    s.check("点副行链接没有翻转勾选框",
            s.js("() => document.querySelector('#chk-terms-agree').checked") is False)
    s.click('#dlg-terms-sub button.doc-link[data-doc="privacy"]')
    s.check("点《隐私政策》切到隐私页签",
            s.js("() => document.querySelector('#tab-terms-privacy').classList.contains('is-on')"
                 " && document.querySelector('#doc-terms-privacy').hidden === false") is True)
    s.shot("links")
    s.click("#tab-terms-agreement")
    s.wait("document.querySelector('#doc-terms-agreement').hidden === false")
    # ④ 失败路径先行（注入桥返回 ok:false）：错误只在页签内就地提示，无全局弹窗
    s.js("() => { window.__QA_STATE.licenseFail = true; }")
    s.click('#doc-terms-agreement button.doc-link[data-doc="license"]')
    s.wait("document.querySelector('#doc-terms-license').hidden === false")
    s.wait("document.querySelector('#license-status').hidden === false")
    s.check("MIT 页签激活且协议/隐私互斥收起",
            s.js("() => document.querySelector('#tab-terms-license').classList.contains('is-on')"
                 " && document.querySelector('#doc-terms-agreement').hidden === true"
                 " && document.querySelector('#doc-terms-privacy').hidden === true") is True)
    s.check("失败就地提示人话，不弹全局弹窗",
            s.js("() => document.querySelector('#license-status').textContent.includes('LICENSE')"
                 " && document.querySelectorAll('dialog[open]').length === 1") is True)
    s.check("失败态亮出「重新读取」且首次激活恰调一次桥",
            s.js("() => document.querySelector('#btn-license-retry').hidden === false") is True
            and s.js(_LICENSE_CALLS_JS) == 1, s.js(_LICENSE_CALLS_JS))
    s.shot("license-error")
    # ③ 成功路径：重试读到内嵌 MIT 全文；再次切换走缓存，桥不再被调
    s.js("() => { window.__QA_STATE.licenseFail = false; }")
    s.click("#btn-license-retry")
    s.wait("document.querySelector('#license-pre').hidden === false")
    s.check("pre 内是 MIT License 全文且状态收起",
            s.js("() => document.querySelector('#license-pre').textContent.includes('MIT License')"
                 " && document.querySelector('#license-status').hidden === true") is True)
    s.check("重试后桥共被调两次（失败一次+重试一次）", s.js(_LICENSE_CALLS_JS) == 2,
            s.js(_LICENSE_CALLS_JS))
    s.shot("license-ok")
    s.click("#tab-terms-privacy")
    s.click("#tab-terms-license")
    s.wait("document.querySelector('#license-pre').hidden === false")
    s.check("再次切回 MIT 走缓存（桥调用次数不变）", s.js(_LICENSE_CALLS_JS) == 2,
            s.js(_LICENSE_CALLS_JS))
    # ② 同意勾选行：点链接外的文字正常 toggle，点链接不改变勾选状态
    pt = s.js("""() => {
      const w = document.createTreeWalker(document.querySelector('.terms-agree'),
                                          NodeFilter.SHOW_TEXT, null);
      let n;
      while ((n = w.nextNode())) {
        if (n.textContent.includes('我已阅读并同意')) {
          const r = document.createRange();
          r.selectNodeContents(n);
          const rect = r.getBoundingClientRect();
          return { x: rect.left + 4, y: (rect.top + rect.bottom) / 2 };
        }
      }
      return null;
    }""")
    s.check("勾选行里找得到链接外的文字用于对照点击", bool(pt), pt)
    if pt:
        s.page.mouse.click(pt["x"], pt["y"])
        s.wait("document.querySelector('#chk-terms-agree').checked === true")
        s.click('.terms-agree button.doc-link[data-doc="privacy"]')
        s.check("点勾选行里的链接不改变勾选状态（preventDefault 生效）且切到隐私页签",
                s.js("() => document.querySelector('#chk-terms-agree').checked === true"
                     " && document.querySelector('#tab-terms-privacy').classList.contains('is-on')") is True)
    s.check("全场景结束桥恰好被调两次", s.js(_LICENSE_CALLS_JS) == 2, s.js(_LICENSE_CALLS_JS))
    s.shot("agree-label")


@scenario("terms-fulltext-document", "方案 A：全文视图按文档体排版（限宽、左边界齐、文末元信息）",
          (1120, 800), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.click("#btn-terms-full")
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    s.check("全文视图显示文末元信息",
            s.js("() => document.querySelector('#terms-doc-meta').hidden") is False)
    # 左边界一致：副行、工具行标题、要点正文、全文段落应共用同一条文档列左边
    lefts = s.js("""() => {
      // 只量当前可见的块：进全文视图后要点区是隐藏的，宽度 0 的块不参与比对。
      const q = (sel) => { const el = document.querySelector(sel);
        if (!el) return null; const r = el.getBoundingClientRect();
        return r.width > 0 ? Math.round(r.left) : null; };
      return { sub: q('#dlg-terms-sub'), toolbar: q('.terms-toolbar'),
               summary: q('#dlg-terms-summary'), doc: q('#dlg-terms-full-text'),
               meta: q('#terms-doc-meta') };
    }""")
    vals = [v for v in lefts.values() if v is not None]
    s.check("文档列左边界一致（容差 2px）", max(vals) - min(vals) <= 2, lefts)
    s.shot("fulltext-1120")
    # 滚到文末：版本/生效日期/许可要真的落在文档列里，而不是悬在别处
    s.js("() => { const b = document.querySelector('.terms-body'); b.scrollTop = b.scrollHeight; }")
    s.wait("() => { const b = document.querySelector('.terms-body'); return b.scrollTop + b.clientHeight >= b.scrollHeight - 2; }")
    end = s.js("""() => { const m = document.querySelector('#terms-doc-meta');
      const d = document.querySelector('#dlg-terms-full-text');
      const r = m.getBoundingClientRect(); const dr = d.getBoundingClientRect();
      return { visible: !m.hidden && r.height > 0, aligned: Math.abs(r.left - dr.left) <= 2,
               lastIn: Math.round(r.bottom) <= Math.round(document.querySelector('.terms-body').getBoundingClientRect().bottom) + 1 }; }""")
    s.check("文末元信息可见且与正文左对齐", end["visible"] and end["aligned"], end)
    s.shot("fulltext-end")


@scenario("terms-fulltext-narrow", "方案 A：窄窗（746）全文视图仍单列、按钮不撑出",
          (746, 900), "terms_unaccepted", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.click("#btn-terms-full")
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    foot = s.js("""() => {
      const foot = document.querySelector('.terms-foot');
      const fr = foot.getBoundingClientRect();
      const btns = ['#btn-terms-close', '#btn-terms-decline', '#btn-terms-accept']
        .map((sel) => { const el = document.querySelector(sel); if (!el) return null;
          const r = el.getBoundingClientRect();
          return { sel: sel, bottom: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height) }; })
        .filter((b) => b && b.w > 0);
      return { footBottom: Math.round(fr.bottom), btns: btns };
    }""")
    overflow = [b["sel"] for b in foot["btns"] if b["bottom"] > foot["footBottom"] + 1]
    s.check("窄窗下按钮没被挤出底栏", overflow == [], overflow)
    tiny = [b["sel"] for b in foot["btns"] if b["h"] < 20 or b["w"] < 40]
    s.check("窄窗下每个按钮仍可点（尺寸不为零）", tiny == [], tiny)
    s.check("窄窗下底栏不横向溢出",
            s.js("() => document.querySelector('.terms-foot').scrollWidth"
                 " <= document.querySelector('.terms-foot').clientWidth + 1") is True)
    s.shot("fulltext-746")

@scenario("terms-version-mismatch-locked", "后端版本与内嵌全文不一致：发请求前本地拒绝",
          (1120, 800), "terms_mismatch", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    # 方案 A：先过勾选门，才能测到「版本不一致」这条本地拒绝路径
    s.click("#chk-terms-agree")
    s.click("#btn-terms-accept")
    s.wait("document.querySelector('#dlg-terms-status').textContent.includes('不一致')")
    s.check("本地拒绝后弹窗不关（门禁保持）", _dialog_open(s))
    s.check("零 accept_terms 请求：不同源副本不得替后端确认", s.calls_count("accept_terms") == 0,
            s.calls_count("accept_terms"))
    disabled = _gate_disabled(s)
    s.check("三入口仍停用", disabled == [True, True, True], disabled)
    s.shot("mismatch")


@scenario("terms-declined-no-reopen", "拒绝过的本版重启后不再强弹，横幅保持停用",
          (1120, 800), "terms_declined", settle=False)
def _(s: Session):
    s.wait("S.terms.declined === true")
    s.check("不自动弹窗", not _dialog_open(s))
    s.check_contains("#banners", "还没有同意使用条款")
    s.check("横幅说明保持停用",
            s.js("() => document.querySelector('#banners').textContent.includes('保持停用')"))
    disabled = _gate_disabled(s)
    s.check("三入口停用", disabled == [True, True, True], disabled)
    s.shot("declined-restart")


@scenario("terms-declined-old-version-regate", "拒绝的是旧版：条款更新后重新门禁",
          (1120, 800), "terms_declined_old", settle=False)
def _(s: Session):
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.check("旧版拒绝不恢复 declined（必须重新同意）", s.js("() => S.terms.declined") is False)
    s.check("弹窗显示的是程序当前版本",
            s.text("#dlg-terms-version").strip() == TERMS_VERSION,
            s.text("#dlg-terms-version"))
    disabled = _gate_disabled(s)
    s.check("三入口停用", disabled == [True, True, True], disabled)
    s.shot("regate")


@scenario("terms-status-viewonly", "1104×790：只读条款状态行合并为一行好消息，info 色不是错误红",
          (1104, 790), "valid")
def _(s: Session):
    """用户图2 反馈「已同意本版」好消息渲染成错误红 + 两行冗余。HEAD 实测
    （centering-diagnosis.txt）：#dlg-terms-status 在 .terms-feedback 内，
    info 色已是 --ink-2，红色未复现（疑出自 v1.1.1 实包旧单体 UI）——颜色
    断言按行为级「≠ var(--bad) rgb」作守护；两行合并（用户拍板）是真改动，
    断言整行不再出现「程序要求版本」版本句。"""
    s.settle()
    # 新工作台：帮助里的「查看条款」是 #btn-help-terms-view（#btn-help-terms 在「设置 → 程序」）
    s.click("#btn-help")
    s.wait("document.querySelector('#help').open === true")
    s.click("#btn-help-terms-view")
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.wait("document.querySelector('#dlg-terms-status').hidden === false")
    d = s.js("""() => {
      const box = document.querySelector('#dlg-terms-status');
      const sub = document.querySelector('#dlg-terms-sub');
      return {
        tone: box.getAttribute('data-tone'),
        text: box.textContent.trim(),
        color: getComputedStyle(box).color,
        badRgb: 'rgb(182, 50, 39)',
        docLinks: box.querySelectorAll('button.doc-link').length,
        boldVersion: box.querySelector('b') ? box.querySelector('b').textContent : '',
        subHidden: sub.hidden,
        /* 用户读到的「整行」= 状态行 + 仍可见的副行；合并后副行收起只剩状态行 */
        topText: box.textContent.trim() + " " + (sub.hidden ? "" : sub.textContent.trim()),
      };
    }""")
    s.check("状态行 data-tone=info", d["tone"] == "info", d["tone"])
    s.check("好消息不是错误红：computed color ≠ var(--bad) 的 rgb",
            d["color"] != d["badRgb"], "实际 %s（--bad=%s）" % (d["color"], d["badRgb"]))
    s.check_contains("#dlg-terms-status", "已同意《用户协议》与《隐私政策》")
    s.check_contains("#dlg-terms-status", "（10-30 09:00 同意）")
    s.check("状态行两处书名号仍是 doc-link 蓝链", d["docLinks"] == 2, d["docLinks"])
    s.check("版本号用 <b> 保留且是内嵌全文版本", d["boldVersion"] == TERMS_VERSION,
            d["boldVersion"])
    s.check("整行（状态行+可见副行）不含「程序要求版本」版本句",
            "程序要求版本" not in d["topText"], d["topText"][:160])
    s.check("副行 #dlg-terms-sub 只读态收起", d["subHidden"], d["subHidden"])
    s.shot("status-merged")
    # 蓝链可点：点状态行《用户协议》开全文并切对应页签（委托处理覆盖动态按钮）
    s.click('#dlg-terms-status button.doc-link[data-doc="agreement"]')
    s.wait("document.querySelector('#dlg-terms-full-text').hidden === false")
    s.check("点状态行蓝链打开全文并切到协议页签", s.js(
        "() => document.querySelector('#dlg-terms-full-text').hidden === false &&"
        " document.querySelector('#tab-terms-agreement').getAttribute('aria-pressed') === 'true'"))
    s.shot("status-link-opens-full")


_TERMS_LINE_AUDIT_JS = r"""() => {
  /* 副行逐行审计：对 #dlg-terms-sub 内每个文本节点建 Range，取 getClientRects()
   * 按行归并，逐行核对「完整落在 .terms-body 可视矩形内」并点名每行中点/
   * 底缘的实际命中元素（找盖住者）。这是 20261031 用户图1（副行第二行只见
   * 上半截字形）的机械判据与诊断数据源。 */
  const sub = document.querySelector("#dlg-terms-sub");
  const body = document.querySelector(".terms-body");
  const toolbar = document.querySelector(".terms-toolbar");
  if (!sub || !body) return { missing: true };
  const bodyRect = body.getBoundingClientRect();
  const subRect = sub.getBoundingClientRect();
  const nameOf = (el) => !el ? "null"
    : el.tagName + (el.id ? "#" + el.id : "")
      + (el.classList && el.classList.length ? "." + [...el.classList].join(".") : "");
  const walker = document.createTreeWalker(sub, NodeFilter.SHOW_TEXT, null);
  const frags = [];
  let node;
  while ((node = walker.nextNode())) {
    const range = document.createRange();
    range.selectNodeContents(node);
    const list = range.getClientRects();
    for (let i = 0; i < list.length; i++) {
      const r = list[i];
      if (r.width <= 0 && r.height <= 0) continue;
      frags.push({ top: r.top, bottom: r.bottom, left: r.left, right: r.right });
    }
  }
  frags.sort((a, b) => a.top - b.top || a.left - b.left);
  const lines = [];
  for (const f of frags) {
    const last = lines[lines.length - 1];
    if (last && Math.abs(f.top - last.top) <= 3) {
      last.top = Math.min(last.top, f.top);
      last.bottom = Math.max(last.bottom, f.bottom);
      last.left = Math.min(last.left, f.left);
      last.right = Math.max(last.right, f.right);
    } else {
      lines.push({ top: f.top, bottom: f.bottom, left: f.left, right: f.right });
    }
  }
  const EPS = 2;
  for (const l of lines) {
    l.h = Math.round((l.bottom - l.top) * 10) / 10;
    const cx = Math.min(Math.max((l.left + l.right) / 2, l.left + 2), l.right - 2);
    const midEl = document.elementFromPoint(cx, (l.top + l.bottom) / 2);
    const lowEl = document.elementFromPoint(cx, l.bottom - 2);
    l.coverMid = nameOf(midEl);
    l.coverLow = nameOf(lowEl);
    l.covered = midEl ? !midEl.closest("#dlg-terms-sub") : true;
  }
  const offenders = lines
    .map((l, i) => ({ i, ...l }))
    .filter((l) => l.top < bodyRect.top - EPS || l.bottom > bodyRect.bottom + EPS);
  const toolbarRect = toolbar ? toolbar.getBoundingClientRect() : null;
  /* 工具行向上的同色投影带：box-shadow 纵向负偏移会在工具行**未吸顶**时
   * 盖住它上方 20px 内的正文（20261031 图1 副行末行下半截被裁的机制）。
   * 这里按计算样式解析投影，还原它实际涂抹的矩形，供断言逐行求交。 */
  let band = null;
  if (toolbar && toolbarRect) {
    const shadow = getComputedStyle(toolbar).boxShadow;
    const m = /(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px\s+(-?[\d.]+)px/.exec(shadow || "");
    if (shadow && shadow !== "none" && m) {
      const oy = parseFloat(m[2]), blur = parseFloat(m[3]), spread = parseFloat(m[4]);
      if (oy < 0) {
        band = { top: toolbarRect.top + oy - spread - blur,
                 bottom: toolbarRect.top,
                 left: toolbarRect.left, right: toolbarRect.right,
                 shadow };
      }
    }
  }
  const shadowLines = !band ? []
    : lines.filter((l) => l.bottom > band.top + 2 && l.top < band.bottom - 2
                         && l.right > band.left + 2 && l.left < band.right - 2)
        .map((l, i) => ({ i, top: l.top, bottom: l.bottom }));
  const cs = getComputedStyle(sub);
  const bold = sub.querySelector("b");
  const csB = bold ? getComputedStyle(bold) : null;
  return {
    dpr: window.devicePixelRatio,
    innerW: window.innerWidth, innerH: window.innerHeight,
    body: { top: bodyRect.top, bottom: bodyRect.bottom, clientH: body.clientHeight,
            scrollH: body.scrollHeight, scrollTop: body.scrollTop },
    sub: { top: subRect.top, bottom: subRect.bottom, fontSize: cs.fontSize,
           lineHeight: cs.lineHeight, fontFamily: cs.fontFamily.slice(0, 90) },
    bFont: csB ? { fontFamily: csB.fontFamily.slice(0, 90), fontSize: csB.fontSize,
                   lineHeight: csB.lineHeight } : null,
    toolbar: toolbarRect ? { top: toolbarRect.top, bottom: toolbarRect.bottom,
                             left: toolbarRect.left, right: toolbarRect.right } : null,
    shadowBand: band, shadowLines,
    lines, offenders,
  };
}"""


@scenario("terms-dialog-no-clip", "1104×790：条款副行逐行完整落在阅读区内、行高一致、无元素遮盖",
          (1104, 790), "terms_absent", settle=False)
def _(s: Session):
    s.wait("S.terms.unknown === true")
    s.click('[data-act="terms-open"]')
    s.wait("document.querySelector('#dlg-terms').open === true")
    s.shot("dialog-open")
    audit = s.js(_TERMS_LINE_AUDIT_JS)
    s.check("副行审计取到行数据", bool(audit) and not audit.get("missing")
            and len(audit.get("lines", [])) >= 1,
            str(audit)[:300])
    if not audit or audit.get("missing") or not audit.get("lines"):
        return
    s.check("副行每一行完整落在阅读区可视矩形内（±2px）",
            audit["offenders"] == [], audit["offenders"] or audit["lines"])
    heights = [l["h"] for l in audit["lines"]]
    s.check("行数≥2 时每行高度一致（±2px）",
            len(heights) < 2 or max(heights) - min(heights) <= 2, heights)
    s.check("副行没有一行被别的元素盖住（行中点命中仍是副行自身/其后代）",
            not any(l["covered"] for l in audit["lines"]),
            [[l["coverMid"], l["coverLow"]] for l in audit["lines"]])
    s.check("工具行不再向上涂抹同色投影带盖住副行（吸顶补条带不得盖未吸顶正文）",
            not audit.get("shadowLines"), audit.get("shadowBand"))
    s.shot("dialog-audited")


@scenario("first-run-unlogged", "首次未登录空态", (980, 760), "unlogged")
def _(s: Session):
    s.wait("document.querySelector('#pill-text').textContent.includes('未登录')")
    s.check_contains("#pill-text", "未登录")
    s.check("#首次使用按钮叫「登录」", s.text("#btn-login-text").strip() == "登录")
    s.check_contains("#empty-title", "登录后查看活动")
    s.check_contains("#empty-text", "点右上角「登录」")
    s.check_unique_clock()
    s.check_topbar_layout("980 首次未登录")
    s.wait_business_ready()
    s.check_clock_text("未登录同样只显独立北京时间")
    s.shot("empty")


_TOPBAR_FIT_JS = r"""() => {
  /* 顶栏最右元素 vs 窗口右缘：枚举 header.top 全部后代取最大 right。
   * 用户真机 1104 宽截图「登录」被右缘裁掉（20261031 图2）；QA Chromium 在
   * 861–1152 各宽度、未登录/拒绝条款/最长右簇四种形状下均未复现
   * （loginRight 恒 = innerW−12..16），本场景按用户裁定作回归守护。 */
  let worst = null;
  for (const el of document.querySelectorAll(".top *")) {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 && r.height <= 0) continue;
    if (!worst || r.right > worst.right) {
      worst = { sel: el.tagName + (el.id ? "#" + el.id : ""),
                right: Math.round(r.right * 100) / 100 };
    }
  }
  return { innerW: window.innerWidth, worst,
           hScroll: document.documentElement.scrollWidth
                    > document.documentElement.clientWidth + 1 };
}"""


@scenario("topbar-fits-width", "1024–1152 每 16px：顶栏最右元素不越过窗口右缘（图2 回归守护）",
          (1104, 790), "unlogged_declined", settle=False)
def _(s: Session):
    s.wait("S.terms.declined === true")
    s.wait("(document.querySelector('#pill-text').textContent || '').includes('未登录')")
    s.shot("w1104-declined")
    widths = list(range(1024, 1153, 16))

    def sweep():
        rows, bad = [], []
        for w in widths:
            s.page.set_viewport_size({"width": w, "height": 790})
            s.page.wait_for_timeout(60)
            d = s.js(_TOPBAR_FIT_JS)
            rows.append({"w": w, **d})
            if d["worst"] is None or d["worst"]["right"] > d["innerW"] + 1 or d["hScroll"]:
                bad.append({"w": w, **d})
        return rows, bad

    # 判据有效性对照：右簇临时注入假按钮，判据必须报出溢出，否则判据无效。
    # 对照注入只活在这一步，拔掉后复测必须干净（不放宽、也不跳过）。
    # 宽度取 500px 而不是口头说的 200px：brand（desc+name 可缩/可换行）能吸收
    # 约 430px 余量，200px 在 1024–1152 任何一档都打不红，对照会假绿。
    s.js("""() => {
      const fake = document.createElement('button');
      fake.id = 'qa-topbar-fake';
      fake.type = 'button';
      fake.textContent = '对照';
      fake.style.flex = 'none';
      fake.style.width = '500px';
      document.querySelector('.top-right').appendChild(fake);
    }""")
    _, contrast_bad = sweep()
    s.check("判据有效性对照：注入 500px 假按钮后判据报出溢出（能红才算数）",
            len(contrast_bad) >= 1, contrast_bad)
    s.js("() => { const f = document.getElementById('qa-topbar-fake'); if (f) f.remove(); }")
    rows, bad = sweep()
    s.check("1024–1152 每 16px 共 %d 档：顶栏最右元素 right ≤ innerWidth+1 且无横向滚动"
            % len(widths), bad == [], bad)
    s.page.set_viewport_size({"width": 1104, "height": 790})
    s.page.wait_for_timeout(60)
    s.shot("w1104-guard")


@scenario("checking", "正在检查登录态", (1120, 800), "checking", settle=False)
def _(s: Session):
    s.check_contains("#pill-text", "检查登录")
    s.check_contains("#status-detail", "正在检查登录状态")
    s.shot("checking")
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')", 12000)
    s.check("#pill 已离开检查中", "检查" not in s.text("#pill-text"))
    s.check_last_check_pill()


@scenario("unknown-network", "网络未知不诱导重登", (1120, 800), "unknown")
def _(s: Session):
    s.wait("document.querySelector('#pill-text').textContent.includes('登录待确认')")
    s.check_contains("#pill-text", "登录待确认")
    s.check_not_contains("#pill-text", "登录已失效")
    # 列表本轮也失败：空态写真实原因与恢复动作，不复读、不诱导重登
    s.check_contains("#empty-title", "暂时无法加载")
    s.check_contains("#empty-text", "恢复网络后点「刷新」重试")
    s.check_not_contains("#empty-text", "重新登录")
    # 下一轮列表成功返回 0 场：登录未知仍有专属空态，未知小时数不编造
    s.set_state(list="empty")
    s.click("#btn-refresh")
    s.wait("document.querySelector('#empty-title').textContent.includes('暂时无法确认登录状态')",
           8000)
    s.check_contains("#empty-title", "暂时无法确认登录状态")
    s.check_contains("#empty-text", "检查网络")
    s.check("未知状态按钮仍叫「登录」", s.text("#btn-login-text").strip() == "登录")
    s.check("未知小时数不编造", s.text("#pill-sub").strip() == "", s.text("#pill-sub"))
    s.shot("unknown")


@scenario("valid-empty", "登录有效但学校零活动", (1280, 900), "empty")
def _(s: Session):
    s.wait("document.querySelector('#empty-title').textContent.includes('学校当前没有返回活动')")
    s.check_contains("#empty-title", "学校当前没有返回活动")
    s.check_contains("#empty-text", "登录是有效的")
    # 第 3 条：副行与标题「当前」口径一致（vm 假元素不聚合 innerHTML，渲染层归这里钉）
    s.check_contains("#empty-text", "学校当前没有返回可报名活动")
    s.check_not_contains("#empty-text", "学校这次")
    s.check("#metric-total", s.text("#metric-total").strip() == "0")
    s.shot("empty")


@scenario("empty-state-layout-copy",
          "空态布局与文案：拆行、同句、垂直居中、按钮更名、底部空白测量", (1280, 900), "empty")
def _(s: Session):
    s.wait("document.querySelector('#empty-title').textContent.includes('学校当前没有返回活动')")
    # 第 2 条：大屏与列表空态是同一状态，两处标题必须同句，不得各写一套措辞
    board, title = s.text("#selected").strip(), s.text("#empty-title").strip()
    s.check("大屏与空态标题同句", board == title,
            "大屏#selected=%r 空态#empty-title=%r" % (board, title))
    # 第 1 条：副行书名号里的「刷新」不得被中文任意断行拆到两行。
    # 判据说明：本 Chromium 的 innerText 按规范不把软折行写成 \n（探针证实：
    # 段落 lineRects=2 时 innerText 仍无 \n），原判据「innerText 不含 刷\n新」
    # 无判别力；改用 Range 顶坐标——刷/新 两字渲染行不同行即算拆行。
    wrap = s.js("""() => {
      const root = document.querySelector("#empty-text");
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let n, spots = [];
      while ((n = walker.nextNode())) {
        const i = n.data.indexOf("刷新");
        if (i >= 0) spots.push([n, i]);
      }
      if (spots.length !== 1)
        return { ok: false, reason: "「刷新」文本节点不唯一：" + spots.length };
      const [node, off] = spots[0];
      const topOf = (o) => {
        const r = document.createRange();
        r.setStart(node, o); r.setEnd(node, o + 1);
        const rect = r.getClientRects()[0];
        return rect ? Math.round(rect.top * 10) / 10 : null;
      };
      return { ok: true, shuaTop: topOf(off), xinTop: topOf(off + 1),
               innerTextJson: JSON.stringify(root.innerText) };
    }""")
    same_line = bool(wrap.get("ok")) and wrap.get("shuaTop") is not None \
        and wrap.get("shuaTop") == wrap.get("xinTop")
    s.check("空态副行「刷新」两字渲染在同一行", same_line, str(wrap))
    # 副行第二行孤行判据已随 f538cc9 回退删除（revert 4ad23ca）：span 恢复只包
    # 「刷新」二字，84px「「」开头孤行回到 main 口径，不再守护。
    # 第 5 条：空态按钮改叫「重新加载」与顶栏「刷新」区分；只改文案，dataset.action 仍 refresh
    empty_btn, top_btn = s.text("#empty-action").strip(), s.text("#btn-refresh").strip()
    s.check("空态按钮文案是「重新加载」", empty_btn == "重新加载", empty_btn)
    s.check("空态按钮与顶栏「刷新」不同文", empty_btn != top_btn,
            "空态=%r 顶栏=%r" % (empty_btn, top_btn))
    # 第 4 条：底部空白只测量不设断言——数值链原样进 qa-report，归因交主代理/用户拍板
    geo = s.js("""() => {
      const rectOf = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { top: Math.round(r.top * 10) / 10,
                 height: Math.round(r.height * 10) / 10,
                 bottom: Math.round(r.bottom * 10) / 10 };
      };
      /* 内容块并集（同 empty-centered 的四元素）：顶对齐判据用 */
      const blocks = [".empty-art", "#empty-title", "#empty-text", "#empty-action"]
        .map((q) => document.querySelector(q))
        .filter((el) => el && !el.hidden && el.getBoundingClientRect().width > 0)
        .map((el) => el.getBoundingClientRect());
      return { innerHeight: window.innerHeight,
               html: rectOf("html"), body: rectOf("body"), zd: rectOf("#zd"),
               table: rectOf(".table"), list: rectOf("#list"), logbar: rectOf("#logbar"),
               empty: rectOf("#empty"), emptyArt: rectOf("#empty .empty-art"),
               blockTop: blocks.length ? +(Math.min(...blocks.map((b) => b.top))).toFixed(1) : null,
               blockBottom: blocks.length ? +(Math.max(...blocks.map((b) => b.bottom))).toFixed(1) : null };
    }""")
    s.actions.append({"action": "bottom-gap-geometry", **geo})
    # 第 3 条（第二次换向，撤销 dd440ad）：顶对齐经用户真机验证否决——默认与
    # 拉大拉小都不正确，与窗口尺寸无关；恢复 19:03 认可态的垂直居中口径：
    # 内容块（art/title/text/action 并集）垂直中心与 .list 垂直中心差 ≤ 6px。
    # 换向链：ebd8d03 垂直中心 → af32672 顶边差 ≤40px → 本次回垂直中心；
    # 此后该断言锁定为垂直居中口径，除非用户带截图再次要求。
    listMid = round((geo["list"]["top"] + geo["list"]["bottom"]) / 2, 1)
    blockMid = round((geo["blockTop"] + geo["blockBottom"]) / 2, 1)
    voff = round(blockMid - listMid, 1)
    s.check("空态内容块垂直中心与 .list 垂直中心差 ≤ 6px", abs(voff) <= 6,
            "blockMid=%.1f listMid=%.1f 实际差=%.1f blockTop=%.1f blockBottom=%.1f" % (
                blockMid, listMid, voff, geo["blockTop"], geo["blockBottom"]))
    s.shot("empty")


@scenario("empty-short-height",
          "短高窗口空态仍把剩余高度交给列表区（用户 1316x824 截图回归）",
          (1316, 824), "empty")
def _(s: Session):
    s.wait("document.querySelector('#empty-title').textContent.includes('学校当前没有返回活动')")
    geo = s.js("""() => {
      const rect = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { top: r.top, height: r.height, bottom: r.bottom };
      };
      const parts = [".empty-art", "#empty-title", "#empty-text", "#empty-action"]
        .map((q) => document.querySelector(q))
        .filter((el) => el && !el.hidden && el.getBoundingClientRect().width > 0)
        .map((el) => el.getBoundingClientRect());
      const list = rect("#list");
      const blockTop = Math.min(...parts.map((r) => r.top));
      const blockBottom = Math.max(...parts.map((r) => r.bottom));
      return { innerHeight: window.innerHeight, zd: rect("#zd"),
               table: rect(".table"), list,
               blockMid: (blockTop + blockBottom) / 2,
               listMid: (list.top + list.bottom) / 2 };
    }""")
    s.check("短高窗口主列仍撑满视口", geo["zd"]["height"] >= geo["innerHeight"] - 2, geo)
    s.check("短高窗口列表区没有塌缩", geo["list"]["height"] >= 300, geo)
    s.check("短高窗口空态仍在列表区垂直居中",
            abs(geo["blockMid"] - geo["listMid"]) <= 6, geo)
    s.shot("empty-short-height")


_EMPTY_CENTER_JS = r"""() => {
  /* 空态块水平居中测量：内容块（art/title/text/action 的并集包围盒）中心
   * vs .list 两个参照中心——矩形（可视卡片，用户视觉参照）与内容盒
   * （clientWidth，列头/行同轴）。inset:0 是否真覆盖 = empty.right 与
   * list.right 之差（scrollbar-gutter 预留槽不在 abspos 包含块内时 >0）。 */
  const rect = (el) => el.getBoundingClientRect();
  const list = document.querySelector("#list");
  const empty = document.querySelector("#empty");
  const parts = [".empty-art", "#empty-title", "#empty-text", "#empty-action"]
    .map((sel) => document.querySelector(sel))
    .filter((el) => el && !el.hidden && rect(el).width > 0);
  const union = parts.reduce((acc, el) => {
    const b = rect(el);
    return { left: Math.min(acc.left, b.left), right: Math.max(acc.right, b.right) };
  }, { left: Infinity, right: -Infinity });
  const lb = rect(list), eb = rect(empty);
  const cxOf = (b) => (b.left + b.right) / 2;
  return {
    innerWidth: window.innerWidth,
    title: document.querySelector("#empty-title").textContent.trim(),
    blockCx: +(cxOf(union)).toFixed(1),
    listRectCx: +(cxOf(lb)).toFixed(1),
    listContentCx: +(lb.left + list.clientWidth / 2).toFixed(1),
    listClientW: list.clientWidth, listOffsetW: list.offsetWidth,
    emptyW: +eb.width.toFixed(1),
    emptyCx: +(cxOf(eb)).toFixed(1),
    coverGap: +(lb.right - eb.right).toFixed(1),
    partsCx: parts.map((el) => ({
      sel: el.id ? "#" + el.id
           : el.tagName + "." + String(el.className.baseVal ?? el.className).split(" ")[0],
      cx: +(cxOf(rect(el))).toFixed(1) })),
  };
}"""

_EMPTY_WORD_JS = r"""(words) => {
  /* 判据③量法：把 #empty-text 的文本节点按序拼成全文并记录 (node, offset)，
   * 对每个受保护词的每次出现构造覆盖 Range，getClientRects() 的所有矩形
   * top 差 ≤1px 视为同一行，换行即红。innerText 按规范不把软折行写成 \n
   * （f541ba4 探针证实），禁止用它判行。 */
  const root = document.querySelector("#empty-text");
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes = [];
  let full = "", n;
  while ((n = walker.nextNode())) {
    nodes.push({ node: n, base: full.length });
    full += n.data;
  }
  const loc = (i) => {
    for (let k = nodes.length - 1; k >= 0; k--) {
      if (i >= nodes[k].base) return [nodes[k].node, i - nodes[k].base];
    }
    return null;
  };
  const out = { text: full, words: {} };
  for (const w of words) {
    const occ = [];
    let hit = full.indexOf(w);
    while (hit >= 0) {
      const a = loc(hit), b = loc(hit + w.length);
      if (a && b) {
        const r = document.createRange();
        r.setStart(a[0], a[1]);
        r.setEnd(b[0], b[1]);
        const tops = [...r.getClientRects()]
          .filter((x) => x.width > 0 || x.height > 0)
          .map((x) => Math.round(x.top * 10) / 10);
        occ.push(tops.length
          ? { n: tops.length, topMin: Math.min(...tops), topMax: Math.max(...tops),
              split: Math.max(...tops) - Math.min(...tops) > 1 }
          : { n: 0, topMin: null, topMax: null, split: true });
      } else {
        occ.push({ n: 0, topMin: null, topMax: null, split: true });
      }
      hit = full.indexOf(w, hit + w.length);
    }
    out.words[w] = { found: occ.length, occ };
  }
  return out;
}"""


@scenario("empty-centered",
          "空态块水平居中与副行防拆词：1024/1067/1104/1280@790 + 1067×831 × 五状态，"
          "块中心对 .list 可视盒中心 ≤4px",
          (1104, 790), "empty")
def _(s: Session):
    """用户实测空态块偏左 20-35px（两份截图，改顶对齐前也有）——是 .empty
    居中参照的旧问题不是回归。判据：内容块中心 vs .list 矩形（可视卡片）
    中心 ≤4px；与内容盒（clientWidth）中心的差值一并打印进 detail 不隐藏
    （列头/行与内容盒同轴，两个参照的差 = 滚动槽/2，诊断归因用）。

    方案 B 增补两守护：
    - 判据①：art/title/text/action 四元素各自中心 X 对 #empty 卡片中心
      ≤2px，每元素一条、五状态×五档位聚合（ebd8d03 删掉的同轴守护按更强
      形式补回，锚点从四元素极差改为卡片中心）；
    - 判据③：各态副行受保护词逐词 Range 单行，档位含复现档 1067×831——
      #empty-text 盒宽被 max-width:330 钳住、与视口基本无关，拆词是
      「有没有 nowrap span」决定的，多档位扫描防回归漏网；
    - terms-locked 态经 unlogged_declined 预设重启进页：条款锁定时 refresh
      安静返回（controllers/refresh.js），listState 停在 idle，空态走
      「还没有加载活动列表」锁定副行；R11 失联兜底 100/130s，hang 态足够
      撑完本轮量测。"""
    row_sizes = [(1024, 790), (1067, 790), (1104, 790), (1280, 790), (1067, 831)]
    states = (
        # (名称, 等待元素, 等待特征, 进入方式, 本态副行受保护词)
        ("valid-empty", "#empty-title", "学校当前没有返回活动", None, ("刷新",)),
        ("expired", "#empty-title", "登录状态失效",
         ("set", {"check": "expired"}), ("重新登录", "刷新")),
        ("unlogged", "#empty-title", "登录后查看活动",
         ("set", {"check": "none"}), ("「登录」", "刷新")),
        ("checking", "#empty-title", "正在检查登录状态",
         ("set", {"check": "hang"}), ("重新登录",)),
        ("terms-locked", "#empty-text", "同意使用条款",
         ("preset", "unlogged_declined"), ("查看条款", "可以")),
    )
    rows = []
    word_rows = []   # (state, 视口标签, 词量测 JSON)
    for name, sel, needle, switch, words in states:
        if switch and switch[0] == "set":
            s.set_state(**switch[1])
            s.js("() => refresh(false)")
        elif switch and switch[0] == "preset":
            s.inject("window.__QA_SCENARIO = %s;" % json.dumps(switch[1]))
            s.page.reload(wait_until="domcontentloaded")
        s.wait("document.querySelector('%s').textContent.includes(%s)"
               % (sel, json.dumps(needle)), 12000)
        for (w, h) in row_sizes:
            s.page.set_viewport_size({"width": w, "height": h})
            s.page.wait_for_timeout(60)
            d = s.js(_EMPTY_CENTER_JS)
            d["state"] = name
            d["vh"] = h
            rows.append(d)
            word_rows.append((name, "%dx%d" % (w, h),
                              s.js(_EMPTY_WORD_JS, list(words))))
            if (w, h) == (1104, 790):
                s.shot("w1104-" + name)
            if (w, h) == (1067, 831):
                s.shot("w1067h831-" + name)
        if switch and switch[0] == "set":
            # 换态后回 valid-empty 基线，下一态不受上一态残留影响
            s.set_state(check="valid", list="empty")
            s.js("() => refresh(false)")
            s.wait("document.querySelector('#empty-title')"
                   ".textContent.includes('学校当前没有返回活动')", 8000)
    if any(d["state"] == "terms-locked" for d in rows):
        # terms-locked 走过预设重启：恢复 empty 预设，别把改过的 init 脚本带出本场景
        s.inject("window.__QA_SCENARIO = 'empty';")
        s.page.reload(wait_until="domcontentloaded")
        s.settle()
        s.wait("document.querySelector('#empty-title')"
               ".textContent.includes('学校当前没有返回活动')", 8000)
    for d in rows:
        off_rect = round(d["listRectCx"] - d["blockCx"], 1)
        off_content = round(d["listContentCx"] - d["blockCx"], 1)
        s.check("空态块中心与 .list 可视盒中心差 ≤4px（%s @%dx%d）"
                % (d["state"], d["innerWidth"], d["vh"]),
                abs(off_rect) <= 4,
                "blockCx=%.1f listRectCx=%.1f 差=%.1f | 内容盒参照差=%.1f "
                "listClientW=%d listOffsetW=%d emptyW=%.1f coverGap=%.1f parts=%s"
                % (d["blockCx"], d["listRectCx"], off_rect, off_content,
                   d["listClientW"], d["listOffsetW"], d["emptyW"],
                   d["coverGap"], json.dumps(d["partsCx"], ensure_ascii=False)))
        # 四元素中心 X 极差 ≤0.5px（原 D-1 判据②，ebd8d03 保留）：按钮满宽
        # 拉伸时中心仍应同轴，判据继续成立；按钮宽判据随 4ad23ca 删除不再守护
        cxs = [p["cx"] for p in d["partsCx"]]
        spread = round(max(cxs) - min(cxs), 2)
        s.check("空态四元素中心X极差 ≤0.5px（%s @%dx%d）"
                % (d["state"], d["innerWidth"], d["vh"]),
                spread <= 0.5,
                "spread=%.2f parts=%s" % (spread, json.dumps(d["partsCx"], ensure_ascii=False)))
    # 判据①（方案 B）：每元素中心 X 对 #empty 卡片中心 ≤2px，五状态×五档位聚合
    part_names = (".empty-art", "#empty-title", "#empty-text", "#empty-action")
    for idx, pname in enumerate(part_names):
        worst, worst_at, missing = 0.0, "", 0
        for d in rows:
            if len(d["partsCx"]) <= idx:
                missing += 1
                continue
            diff = abs(round(d["partsCx"][idx]["cx"] - d["emptyCx"], 1))
            if diff > worst:
                worst = diff
                worst_at = "%s @%dx%d" % (d["state"], d["innerWidth"], d["vh"])
        s.check("空态%s中心X对卡片中心差 ≤2px（五状态×五档位聚合）" % pname,
                worst <= 2 and missing == 0,
                "最差=%.1fpx（%s） 元素缺失行=%d" % (worst, worst_at, missing))
    # 判据③（方案 B）：受保护词逐词 Range 单行；每状态每词一条，跨档位聚合。
    # not-ready/unlocked 与 unknown 两分支副行 ≤300/144px < 330 max-width，
    # 数学上不可折行且其词已在别态覆盖，不为形式覆盖引入非生产形态的状态注入。
    by_state = {}
    for name, vw, wc in word_rows:
        by_state.setdefault(name, []).append((vw, wc))
    for name, samples in by_state.items():
        for w in sorted({w for _, wc in samples for w in wc["words"]}):
            found, bad = 0, []
            for vw, wc in samples:
                data = wc["words"].get(w)
                if not data:
                    bad.append("%s:词量测缺失" % vw)
                    continue
                found += data["found"]
                if data["found"] == 0:
                    bad.append("%s:副行未命中" % vw)
                for o in data["occ"]:
                    if o["split"]:
                        bad.append("%s:%s" % (vw, json.dumps(o, ensure_ascii=False)))
            s.check("空态副行「%s」不拆词（%s，五档位聚合）" % (w, name),
                    found > 0 and not bad,
                    "命中=%d 违例=%s 全文=%r"
                    % (found, json.dumps(bad, ensure_ascii=False),
                       samples[0][1]["text"]))
    covers = [d for d in rows if d["innerWidth"] == 1104 and d["vh"] == 790]
    s.check("inset:0 真覆盖：#empty right 与 .list right 之差 ≤1px（五状态 @1104）",
            all(d["coverGap"] <= 1 for d in covers),
            "coverGap=%s" % [d["coverGap"] for d in covers])


@scenario("long-place", "超长地点两行与大屏展开", (1280, 900), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.page.locator('input.row-check[data-id="a-open"]').check()
    s.wait("document.querySelector('#selected-meta .b-place')")
    s.shot("collapsed")
    metrics = s.js("""() => {
      const place = document.querySelector('#selected-meta .b-place');
      const text = place.querySelector('.b-place-text');
      const rect = place.getBoundingClientRect();
      const next = document.querySelector('#board-text').getBoundingClientRect();
      return { lines: Math.round(text.getBoundingClientRect().height / (13 * 1.35)),
               contained: rect.width <= place.parentElement.getBoundingClientRect().width + 1,
               no_overlap: rect.bottom <= next.top + 1 };
    }""")
    s.check("大屏地点默认不超过两行", metrics["lines"] <= 2, metrics)
    s.check("大屏地点不横向溢出", metrics["contained"], metrics)
    s.check("展开前不覆盖下一条", metrics["no_overlap"], metrics)
    s.page.locator("#selected-meta .b-place").focus()
    s.page.keyboard.press("Enter")
    s.wait("document.querySelector('#selected-meta .b-place').getAttribute('aria-expanded') === 'true'")
    expanded = s.js("""() => {
      const place = document.querySelector('#selected-meta .b-place');
      const text = place.querySelector('.b-place-text');
      const next = document.querySelector('#board-text').getBoundingClientRect();
      return { expanded: place.getAttribute('aria-expanded'),
               full: text.scrollHeight <= text.clientHeight + 1,
               no_overlap: place.getBoundingClientRect().bottom <= next.top + 1 };
    }""")
    s.check("Enter 展开后 aria-expanded=true", expanded["expanded"] == "true", expanded)
    s.check("展开后全文可见", expanded["full"], expanded)
    s.check("展开后仍不覆盖下一条", expanded["no_overlap"], expanded)
    s.shot("expanded")
    # 表格地点：聚焦即可展开（与键盘同一路径）
    s.js("document.querySelector('#rows .row .c-place').focus()")
    table = s.js("""() => {
      const cell = document.querySelector('#rows .row .c-place');
      return { focused: document.activeElement === cell,
               expanded: getComputedStyle(cell).webkitLineClamp === 'none' };
    }""")
    s.check("表格地点可聚焦", table["focused"], table)
    s.check("表格地点聚焦后展开全文", table["expanded"], table)
    s.shot("table-place")


@scenario("filters-clear-preserves-policy", "筛选清空保留重试策略", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.wait("!document.querySelector('#retry-for').closest('.policy-select').hidden")
    s.page.select_option("#retry-for", "600")
    s.page.fill("#max-attempts", "3")
    s.page.fill("#q", "绝对不存在的活动")
    s.wait("document.querySelector('#empty-title').textContent.includes('没有符合筛选')")
    s.check_contains("#empty-title", "没有符合筛选")
    s.check("#empty-action 是清除筛选", s.text("#empty-action").strip() == "清除筛选")
    s.shot("filtered-empty")
    s.click("#empty-action")
    s.check("#q 已清空", s.page.input_value("#q") == "")
    s.check("#retry-for 保持 600", s.page.input_value("#retry-for") == "600")
    s.check("#max-attempts 保持 3", s.page.input_value("#max-attempts") == "3")
    s.check("#rows 恢复", s.count("#rows .row") >= 5)
    s.shot("cleared")


@scenario("filter-persist-reload", "筛选保存跨重载恢复（save_prefs→bootstrap 整环）", (1120, 800), "valid")
def _(s: Session):
    """F5 不许弄丢用户设的筛选：save_prefs 带出 filter，bootstrap 原样回放。"""
    s.wait("document.querySelectorAll('#rows .row').length >= 8")
    s.check("未筛选时 a-open 在列", s.count("input.row-check[data-id=a-open]") == 1)
    s.page.select_option("#checkin", "yes")
    s.wait("S.filter.checkin === 'yes'")
    # savePrefs 有 250ms 防抖：等真正落盘（桥记录到调用）再继续，否则
    # 后面采集 savedPrefs 会拿到空对象
    s.wait("window.__QA_CALLS.some((c) => c.name === 'save_prefs'"
           " && c.args[0] && c.args[0].filter && c.args[0].filter.checkin === 'yes')", 4000)
    s.check("save_prefs 已带 filter.checkin=yes", s.js(
        "window.__QA_CALLS.some((c) => c.name === 'save_prefs'"
        " && c.args[0] && c.args[0].filter && c.args[0].filter.checkin === 'yes')"),
        s.js("JSON.stringify(window.__QA_CALLS.filter((c) => c.name === 'save_prefs'))"))
    s.check("保存后立即按签到过滤", s.count("#rows .row") == 7
            and s.count("input.row-check[data-id=a-open]") == 0,
            [s.count("#rows .row"), s.count("input.row-check[data-id=a-open]")])
    s.shot("filtered-yes")
    # 重载：生产语义是后端进程不重启、偏好从 ui.json 回放——桥把 savedPrefs
    # 重新喂给 state（init 脚本先于桥装载），等价于后端已落盘这一事实
    saved = s.js("window.__QA_STATE.savedPrefs")
    s.inject("window.__QA_STATE = Object.assign(window.__QA_STATE || {}, { savedPrefs: %s });"
             % json.dumps(saved, ensure_ascii=False))
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.check("重载后下拉恢复签到=需要", s.page.input_value("#checkin") == "yes",
            s.page.input_value("#checkin"))
    s.check("重载后 S.filter 恢复", s.js("S.filter.checkin") == "yes",
            s.js("JSON.stringify(S.filter)"))
    s.check("重载后可见行仍按签到过滤", s.count("#rows .row") == 7
            and s.count("input.row-check[data-id=a-open]") == 0,
            [s.count("#rows .row"), s.count("input.row-check[data-id=a-open]")])
    s.shot("filter-restored")


@scenario("list-fail-login-states", "没登录/失效 + 列表失败：空态标题各归各", (1120, 800),
          "list_fail_unlogged")
def _(s: Session):
    """列表失败叠加登录四态时，空态标题必须按真实登录结论归因，不得互串。"""
    s.settle()
    s.wait("document.querySelector('#empty-title').textContent.includes('还没登录')", 8000)
    s.check_contains("#pill-text", "未登录")
    s.check("未登录变体不含过期关键词",
            "登录已过期" not in s.text("#empty-title")
            and "登录已失效" not in s.text("#empty-title"),
            s.text("#empty-title"))
    s.check("未登录重试入口存在", s.text("#empty-action").strip() == "重试",
            s.text("#empty-action"))
    s.shot("list-fail-unlogged")
    # 同一场景切到「登录失效 + 列表失败」：标题走 expired 分支，不借未登录话术
    s.set_state(check="expired")
    s.js("() => refresh(false)")
    s.wait("S.listState === 'error' && document.querySelector('#empty-title')"
           ".textContent.includes('登录已过期')", 8000)
    s.check_contains("#pill-text", "登录已失效")
    s.check("过期变体不含未登录关键词", "还没登录" not in s.text("#empty-title"),
            s.text("#empty-title"))
    s.check("过期重试入口存在", s.text("#empty-action").strip() == "重试",
            s.text("#empty-action"))
    s.shot("list-fail-expired")


@scenario("preopen-and-instant", "预报名与立即报名同批", (1280, 900), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    # a-open 与 a-long 举办时间不冲突：一立即、一预报名，才是真实的混合批次
    s.pick("a-open")
    s.pick("a-long")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("window.__QA_CALLS.some((c) => c.name === 'start_plan')")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-long", "创新创业训练计划宣讲", "waiting",
                         signup_mode="pre_register", sign_start="2026-10-27 20:00:00"))
    s.emit("task", _task("t2", "a-open", "校园歌手大赛决赛", "submitting",
                         signup_mode="instant_signup", attempts=1, last_reason="已发起"))
    s.wait("document.querySelectorAll('#plan-tasks .task-row').length === 2")
    s.check_contains("#plan-tasks", "预报名")
    s.check_contains("#plan-tasks", "立即报名")
    s.check("#开始按钮锁定", s.page.locator("#btn-plan").is_disabled())
    s.shot("running")


@scenario("conflict-selection", "冲突选择端到端（G-01）", (1120, 800), "valid")
def _(s: Session):
    """真实指针勾选：时段重叠的第二场被拒绝，原选择保留，提示说的是举办时间。"""
    s.wait("S.listState === 'ready'")
    s.emit("activities", {"ok": True, "items": [
        {"id": "qa-a", "name": "冲突活动甲", "place": "实训楼 A301",
         "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-28 23:00:00",
         "act_start": "2026-10-28 19:00:00", "act_end": "2026-10-28 20:00:00",
         "signed": False, "checkin_required": True,
         "checkin_start": "2026-10-28 19:00:00", "checkin_end": "2026-10-28 19:20:00",
         "checkout_required": False, "attendance_state": "ready"},
        {"id": "qa-b", "name": "冲突活动乙", "place": "实训楼 A302",
         "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-28 23:00:00",
         "act_start": "2026-10-28 19:30:00", "act_end": "2026-10-28 21:00:00",
         "signed": False, "checkin_required": None, "checkout_required": None,
         "attendance_state": "pending"},
        {"id": "qa-c", "name": "不冲突活动", "place": "实训楼 B204",
         "sign_start": "2026-10-26 09:00:00", "sign_end": "2026-10-28 23:00:00",
         "act_start": "2026-10-29 09:00:00", "act_end": "2026-10-29 11:00:00",
         "signed": False, "checkin_required": False, "checkout_required": False,
         "attendance_state": "ready"},
    ]})
    s.wait("S.items.length === 3")
    s.pointer_pick("qa-a")
    s.check("首场可开始", not s.page.locator("#btn-plan").is_disabled())
    s.pointer("input.row-check[data-id=\"qa-b\"]", "pick:qa-b")
    s.check("冲突场次未被选中", not s.js("S.selected.has('qa-b')"))
    s.check("原选择保留", s.js("S.selected.has('qa-a')"))
    s.check_contains("#plan-conflicts", "活动时间重叠")
    s.check_contains("#plan-conflicts", "已保留原选择")
    s.check_not_contains("#plan-conflicts", "报名开放")
    s.shot("conflict-rejected")
    s.pointer_pick("qa-c")
    s.check("不冲突场次可选", s.js("S.selected.has('qa-c')"))
    s.check("两场都在计划里", s.js("S.selected.size === 2"))
    s.check("不冲突时开始可用", not s.page.locator("#btn-plan").is_disabled())
    s.shot("conflict-resolved")


@scenario("update-five-states", "更新检查五态端到端（G-02）", (1120, 800), "valid")
def _(s: Session):
    """检查更新走真实按钮与真实事件：current/available/preview/unavailable/error。

    新工作台：版本与更新在「设置 → 程序」，从设置抽屉进，不再从帮助进。"""
    s.click("#btn-settings")
    s.wait("document.querySelector('#settings').hidden === false")
    s.click("#btn-update-check")
    s.wait("S.update.state === 'current'")
    s.check_contains("#update-status", "当前为最新正式版")
    # 桥替身的版本号必须走生产 _result 键（update_check.py:109 的
    # current_version/latest_version）：旧名 current/latest 恰好不被
    # current 态文案消费，漂移不会自己爆红，这里必须显式守住。
    s.check("版本号来自生产契约字段 current_version/latest_version", s.js(
        "(() => { const r = S.update.result || {};"
        " return r.current_version === '1.1.1' && r.latest_version === '1.1.1'; })()"))
    s.check("检查后按钮回到可点", not s.page.locator("#btn-update-check").is_disabled())
    # 桥回执的 checked_at 必须是前端能解析的时间：替身若发 epoch 秒，
    # Date.parse 得 NaN，「检查时间」行被隐藏（B11 失真，此处必须红）。
    s.check("检查时间行可见且内容可解析", s.js(
        "(() => { const el = document.querySelector('#update-checked-at');"
        " return !el.hidden && el.textContent.trim() !== ''"
        " && Number.isFinite(Date.parse(S.update.result.checked_at)); })()"))
    request_id = s.js("S.update.requestId")
    s.shot("update-current")
    cases = [
        ("available", "发现新版本 1.1.2", "1.1.2", "检查更新"),
        ("preview", "当前为预览版本，最新正式版 1.1.2", "1.1.2", "检查更新"),
        ("unavailable", "暂无正式发布", "", "检查更新"),
        ("error", "暂时无法检查更新", "", "重试检查"),
    ]
    for state, needle, latest, button in cases:
        s.emit("update", {"request_id": request_id, "state": state,
                          "latest_version": latest, "url": "",
                          "text": "网络没通" if state == "error" else "",
                          "checked_at": "2026-10-27T09:00:00+08:00"})
        s.wait("S.update.state === %s" % json.dumps(state))
        s.check_contains("#update-status", needle)
        s.check("五态按钮文案 %s" % state, s.text("#btn-update-check").strip() == button)
        s.check("#检查时间五态可见 %s" % state,
                not s.page.locator("#update-checked-at").is_hidden())
        s.shot("update-" + state)


@scenario("mixed-success-waiting", "单场成功不抢整屏结论", (1280, 900), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-open")
    s.pick("a-long")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("window.__QA_CALLS.some((c) => c.name === 'start_plan')")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-long", "创新创业训练计划宣讲", "success",
                         stop="success", attempts=1, reason="报名成功"))
    s.emit("task", _task("t2", "a-open", "校园歌手大赛决赛", "waiting",
                         signup_mode="instant_signup"))
    s.wait("document.querySelectorAll('#plan-tasks .task-row').length === 2")
    s.check("#运行中不弹整屏成功", s.page.locator("#result").is_hidden())
    s.shot("single-success")
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "partial",
                         "summary": {"total": 2, "counts": {"success": 1, "waiting": 1}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#result", "部分完成")
    s.shot("partial-done")


@scenario("unknown-outcomes", "未确认与鉴权未知贯穿界面", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-open")
    s.pick("a-long")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("window.__QA_CALLS.some((c) => c.name === 'start_plan')")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-long", "创新创业训练计划宣讲", "failed",
                         stop="unconfirmed", attempts=3, reason="响应丢失"))
    s.emit("task", _task("t2", "a-open", "校园歌手大赛决赛", "failed",
                         stop="auth_unavailable", attempts=0, reason="接口异常：URLError"))
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "failed",
                         "summary": {"total": 2, "counts": {"failed": 2}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#result", "需确认")
    s.check_not_contains("#result", "都没抢到")
    s.check_not_contains("#result", "登录失效")
    s.check_contains("#plan-tasks", "待核对")
    s.check_contains("#plan-tasks", "本场没有提交")
    s.check("#LED 不亮失败叉", s.attr("#led", "data-tone") != "red")
    # FR06：待核对与未提交必须分列，不能拿 unknown 总数当「待核对」
    s.check_contains("#result", "待核对 1 场")
    s.check_contains("#result", "未提交 1 场")
    s.check_not_contains("#result", "待核对 2 场")
    shadow = s.js("getComputedStyle(document.querySelector('#board')).boxShadow")
    s.actions.append({"action": "board-shadow", "value": shadow})
    s.check("#大屏不画确定失败红框", "255, 91, 72" not in shadow, shadow)
    s.check("#大屏框是中性琥珀", "185, 131, 25" in shadow, shadow)
    s.check("#大屏状态为 attention", s.js(
        "document.querySelector('#board').dataset.planState") == "attention",
        s.js("document.querySelector('#board').dataset.planState"))
    s.shot("unknown-summary")


@scenario("reconcile-hang", "对账永不返回的 5 秒出口", (1120, 800), "reconcile_hang")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("window.__QA_CALLS.some((c) => c.name === 'start_plan')")
    # 触发生产对账入口（真实按钮要在 15 秒后才走这里，QA 直接驱动同一函数）
    s.js("""() => {
      S.startRequest = { id: 'qa-hang', state: 'submitting', timer: null,
                         queryTimer: null, reconcile: 0, gen: 0 };
      S.starting = true;
      reconcileStart('qa-hang');
    }""")
    s.shot("reconciling")
    s.wait("document.querySelector('#result').textContent.includes('结果未确认')", 9000)
    s.check_contains("#result", "5 秒")
    s.check("#开始仍锁定", s.page.locator("#btn-plan").is_disabled())
    calls = s.js("window.__QA_CALLS.filter((c) => c.name === 'start_request_state').length")
    s.click("#result-action")
    s.wait("window.__QA_CALLS.filter((c) => c.name === 'start_request_state').length > %d" % calls)
    s.check("#重新确认只读", s.js(
        "window.__QA_CALLS.filter((c) => c.name === 'start_plan').length") == 1)
    s.shot("reconfirm")


@scenario("skipped-terminal-first", "终态先于 skipped ack", (1120, 800), "skipped")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.js("""() => {
      window.__QA_STATE.nextCheckSkipped = true;
      refresh(false);                    // 新一轮 ID 先发
      window.__QA_EMIT('check', { request_id: 'qa-old-check', ok: true,
        result: 'valid', session_present: true, hours_left: 6 });
    }""")
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')", 5000)
    s.check("#旧终态被接续重放", "检查" not in s.text("#pill-text"))
    s.check("#未干等 100 秒", s.js("S.login.checking === false"))
    s.shot("replayed")


@scenario("component-banner", "组件横幅与下一轮恢复", (1120, 800), "component")
def _(s: Session):
    s.wait("document.querySelector('#banners').textContent.includes('程序组件缺失')")
    s.check_contains("#banners", "程序组件缺失")
    s.check_contains("#empty-title", "活动列表未加载")
    s.shot("banner")
    s.set_state(list="ok", check="valid")
    s.click("#btn-refresh")
    s.wait("!document.querySelector('#banners').textContent.includes('程序组件缺失')")
    s.check("#横幅已撤销", "程序组件缺失" not in s.text("#banners"))
    s.check("#列表恢复", s.count("#rows .row") >= 5)
    s.shot("recovered")


@scenario("keyboard-dialogs", "键盘、弹窗与引导", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.page.keyboard.press("Control+f")
    s.check("#Ctrl+F 聚焦搜索", s.js("document.activeElement && document.activeElement.id === 'q'"))
    s.page.keyboard.press("Escape")
    s.check("时钟入口可访问名称同步状态", "北京时间" in (s.attr("#clock", "aria-label") or "")
            and "详情" in (s.attr("#clock", "aria-label") or ""),
            s.attr("#clock", "aria-label"))
    s.click("#clock")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    esc_state = s.js("() => ({ hidden: document.querySelector('#clock-pop').hidden,"
                     " open: S.clockPopOpen,"
                     " active: document.activeElement ? document.activeElement.id : '' })")
    s.page.keyboard.press("Escape")
    esc_after = s.js("() => ({ hidden: document.querySelector('#clock-pop').hidden,"
                     " open: S.clockPopOpen,"
                     " active: document.activeElement ? document.activeElement.id : '' })")
    s.check("Esc 关闭时间详情且焦点归还", esc_after["hidden"] is True
            and esc_after["active"] == "clock", [esc_state, esc_after])
    s.click("#btn-help")
    s.wait("document.querySelector('#help').open === true")
    s.shot("help")
    s.page.keyboard.press("Escape")
    s.wait("document.querySelector('#help').open === false")
    s.check("#Esc 关闭后焦点回入口", s.js(
        "document.activeElement && document.activeElement.id === 'btn-help'"))
    s.click("#btn-help")
    s.wait("document.querySelector('#help').open === true")
    s.click("#btn-help-tour")
    s.wait("document.querySelector('#tour').hidden === false")
    s.check_contains("#tour-card", "第 1/5 步")
    s.shot("tour")
    s.click("#tour-skip")
    s.wait("document.querySelector('#tour').hidden === true")
    s.check("#重看引导按设计关闭帮助面板", s.js("document.querySelector('#help').open === false"))
    s.check("#跳过引导后焦点回入口", s.js(
        "document.activeElement && document.activeElement.id === 'btn-help'"))


@scenario("owner-reuse-cross-round", "同 owner 结果收口新刷新轮次", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    # roundA：真发一轮 check，但后端卡住不回（owner 就是这一轮自己发的 ID）
    s.set_state(check="hang")
    s.js("() => refresh(false)")
    owner = s.js("S.round.check")
    s.check("#owner 是本轮自己发出的 ID", str(owner).startswith("check-"), owner)
    # 终态先到（后端 _do_check 还没走到 finally，在途标记仍在）
    s.js("""(rid) => window.onBackend.check({ request_id: rid, ok: true,
      result: 'valid', session_present: true, hours_left: 6,
      clock: { source: 'http_date', state: 'ok', offset_s: 0,
               uncertainty_s: 1, rtt_s: 0.2, checked_at: 1 } })""", owner)
    s.wait("S.login.checking === false && S.login.result === 'valid'")
    count_js = ("(needle) => Array.from(document.querySelectorAll('#log .lg'))"
                ".filter((el) => el.textContent.indexOf(needle) >= 0).length")
    before = s.js(count_js, "已复用本机登录态")
    s.actions.append({"action": "log-before", "count": before})
    s.check("#复用日志在本轮 valid 校验后输出过一次", before >= 1, before)

    # roundB：新一轮先置「检查中」，后端回 skipped + 同一 owner 的既有终态
    s.set_state(check="valid", nextCheckSkipped=True, skipCheckId=owner,
                skipCheckResult={"request_id": owner, "ok": True, "result": "valid",
                                 "session_present": True, "hours_left": 6})
    s.js("() => refresh(false)")
    s.wait("S.login.checking === false", 6000)
    s.check("#新轮次不再干等 100 秒", s.js("S.login.checking === false"))
    s.check("#新轮次接续原 owner", s.js("S.round.check") == owner, s.js("S.round.check"))
    s.check("#登录结论保留", s.js("S.login.result") == "valid", s.js("S.login.result"))
    s.check("#新轮 pending 已收口", s.js("S.runtime.checkPending === false"))
    after = s.js(count_js, "已复用本机登录态")
    s.actions.append({"action": "log-after", "count": after})
    s.check("#同一句日志不重复", after == before, [before, after])

    # 旧轮迟到 ack 不得收口后来那一轮：C 的 ack 慢回，D 一直挂着
    s.js("""() => {
      window.__QA_STATE.delayCheckMs = 900;
      refresh(false);                        // roundC
      window.__QA_STATE.check = 'hang';      // roundD 永不回
      refresh(false);                        // roundD
    }""")
    s.page.wait_for_timeout(1500)
    s.check("#旧 ack 不清新轮 pending", s.js("S.runtime.checkPending === true"),
            s.js("[S.runtime.checkPending, S.runtime.listPending, S.round.gen.check]"))
    s.check("#新一轮仍是检查中", s.js("S.login.checking === true"))
    s.shot("owner-reuse")


@scenario("stopped-unconfirmed", "停止保留已提交与待核对", (1280, 900), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-open")
    s.pick("a-long")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("window.__QA_CALLS.some((c) => c.name === 'start_plan')")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-long", "创新创业训练计划宣讲", "success",
                         stop="success", attempts=1, reason="报名成功"))
    s.emit("task", _task("t2", "a-open", "校园歌手大赛决赛", "failed",
                         stop="unconfirmed", attempts=3,
                         reason="已按你的要求停止；最后一次提交没有拿到确定回应",
                         locally_stopped=True))
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "stopped",
                         "summary": {"total": 2, "counts": {"success": 1, "failed": 1}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#result strong", "已停止")
    s.check_contains("#result", "待核对")
    s.check_contains("#result", "已报名 1 场")
    s.check_contains("#plan-tasks", "已提交 3 次")
    s.check_not_contains("#result", "都没抢到")
    shadow = s.js("getComputedStyle(document.querySelector('#board')).boxShadow")
    s.check("#停止带未知不画红框", "255, 91, 72" not in shadow, shadow)
    s.check("#LED 不亮失败叉", s.attr("#led", "data-tone") != "red")
    s.shot("stopped-unconfirmed")


@scenario("f5-terminal-restore", "F5 恢复完整终态", (1120, 800), "valid")
def _(s: Session):
    s.inject("window.__QA_PLAN = " + json.dumps({
        "plan_id": "qa-f5",
        "status": "failed",
        "summary": {"total": 2, "counts": {"failed": 2}},
        "tasks": [
            {"task_id": "t1", "activity_id": "a-long", "name": "创新创业训练计划宣讲",
             "status": "failed", "stop_reason": "unconfirmed", "attempts": 4,
             "reason": "响应丢失"},
            {"task_id": "t2", "activity_id": "a-open", "name": "校园歌手大赛决赛",
             "status": "failed", "stop_reason": "auth_unavailable", "attempts": 0,
             "reason": "接口异常：URLError"},
        ],
    }, ensure_ascii=False))
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("S.plan.id === 'qa-f5'")
    s.wait("!document.querySelector('#result').hidden")
    s.check("#F5 后不是忙碌态", s.js("S.busy === false"))
    s.check("#F5 后结论框在", s.js("document.querySelector('#result').hidden === false"))
    s.check_contains("#result", "待核对 1 场")
    s.check_contains("#result", "未提交 1 场")
    s.check_contains("#plan-tasks", "已提交 4 次")
    s.check("#F5 后 LED 不亮失败叉", s.attr("#led", "data-tone") != "red")
    shadow = s.js("getComputedStyle(document.querySelector('#board')).boxShadow")
    s.check("#F5 后整屏中性", "255, 91, 72" not in shadow, shadow)
    s.check("#F5 后 doneSelection 已设", s.js(
        "S.plan.doneSelection === selectionSignature()"))
    s.check("#F5 不重发 start_plan", s.js(
        "window.__QA_CALLS.filter((c) => c.name === 'start_plan').length") == 0)
    s.shot("f5-restored")
    # 用户真的改变选择后才回预览
    s.pointer_pick("a-future")
    s.check("#改变选择后回预览", s.js(
        "document.querySelector('#board').dataset.planState === 'idle'"),
        s.js("document.querySelector('#board').dataset.planState"))
    s.shot("f5-after-select")


@scenario("stale-plan-events", "旧计划事件不劫持运行中的计划", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-open")
    s.wait("!document.querySelector('#btn-plan').disabled")
    # 真实点击「开始报名计划」：B（qa-plan，代次 2）经生产 startPlan 路径接纳
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("task", _task("t1", "a-open", "校园歌手大赛决赛", "submitting", attempts=2))
    # 注入旧 A（qa-plan-old，代次 1）迟到的 plan/task/plan_done 三类事件
    s.js("() => window.__QA_EMIT_STALE()")
    s.page.wait_for_timeout(200)
    s.check("#旧事件不改当前计划 ID", s.js("S.plan.id") == "qa-plan", s.js("S.plan.id"))
    s.check("#B 仍运行、忙态未被解除", s.js("S.busy === true && S.plan.status === 'running'"),
            s.js("[S.busy, S.plan.status]"))
    s.check("#旧任务不得混入 B 的任务表", s.js("S.plan.tasks.has('t-old')") is False,
            list(s.js("Array.from(S.plan.tasks.keys())")))
    s.check("#B 的任务次数保留", s.js("(S.plan.tasks.get('t1')||{}).attempts") == 2,
            s.js("(S.plan.tasks.get('t1')||{}).attempts"))
    s.check("#旧事件不弹终态结果框", s.js("document.querySelector('#result').hidden"),
            s.text("#result")[:80])
    # 真实指针点击停止并确认：stop_plan 实参必须是 B 的 plan_id（P1）
    record = s.pointer("#btn-stop", "stop")
    s.check("#停止按钮真实命中", _hit_id(record, "btn-stop"), record.get("hit"))
    s.wait("document.querySelector('#dlg-stop').open === true")
    s.pointer("#dlg-stop button[value='yes']", "stop-confirm")
    s.wait("S.busy === false", 8000)
    stops = s.js("window.__QA_CALLS.filter((c) => c.name === 'stop_plan')"
                 ".map((c) => String(c.args[0]))")
    s.check("#停止调用指向 B", stops == ["qa-plan"], stops)
    s.check_contains("#result strong", "已停止")
    s.check("#旧计划 ID 不得出现在屏上", s.js("S.plan.id") == "qa-plan", s.js("S.plan.id"))
    s.shot("stale-plan-events")


@scenario("stale-after-done", "旧计划事件不改已完成结论", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "failed",
                         stop="unconfirmed", attempts=3, reason="响应丢失"))
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "failed",
                         "summary": {"total": 1, "counts": {"failed": 1}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#result", "待核对 1 场")
    before_html = s.js("document.querySelector('#result').innerHTML")
    before_led = s.attr("#led", "data-tone")
    # B 已结束后注入旧 A 的完成与进度事件：结论/LED/边框/忙态保持 B
    s.js("() => window.__QA_EMIT_STALE()")
    s.page.wait_for_timeout(200)
    s.check("#已完成结论不被旧完成事件改写",
            s.js("document.querySelector('#result').innerHTML") == before_html,
            s.js("document.querySelector('#result').innerHTML")[:120])
    s.check("#LED 保持 B 的结论", s.attr("#led", "data-tone") == before_led,
            [before_led, s.attr("#led", "data-tone")])
    s.check("#已完成计划不得被旧进度复活", s.js("S.busy === false"), s.js("S.busy"))
    s.check("#屏上计划仍是 B", s.js("S.plan.id") == "qa-plan", s.js("S.plan.id"))
    s.check("#旧任务的卡不得混进来", s.js("S.plan.tasks.has('t-old')") is False,
            list(s.js("Array.from(S.plan.tasks.keys())")))
    # F5 后同样成立：权威快照（带接纳代次）建立归属，旧事件不再覆盖
    s.inject("window.__QA_PLAN = " + json.dumps({
        "plan_id": "qa-plan", "plan_generation": 2, "status": "failed",
        "summary": {"total": 1, "counts": {"failed": 1}},
        "tasks": [{"task_id": "t1", "activity_id": "a-future",
                   "name": "人工智能前沿讲座", "status": "failed",
                   "stop_reason": "unconfirmed", "attempts": 3, "reason": "响应丢失"}],
    }, ensure_ascii=False))
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("S.plan.id === 'qa-plan' && S.busy === false")
    s.js("() => window.__QA_EMIT_STALE()")
    s.page.wait_for_timeout(200)
    s.check("#F5 后旧事件不改结论", s.js("S.busy === false && S.plan.id === 'qa-plan'"),
            s.js("[S.plan.id, S.busy, S.plan.status]"))
    s.check_contains("#result", "待核对 1 场")
    s.shot("stale-after-done")


@scenario("early-events-before-ack", "新计划事件早于 ack 且 ack 不抹次数", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    # ack 延迟 600ms 回：B 的 plan/task 事件先于 ack 到达（生产真实时序）
    s.set_state(earlyEventsBeforeAck=True, earlyAckDelayMs=600)
    s.click("#btn-plan")
    s.wait("S.plan.id === 'qa-plan' && S.plan.tasks.has('t1')", 8000)
    s.check("#早于 ack 的事件已接纳新计划", s.js("S.plan.id") == "qa-plan",
            s.js("S.plan.id"))
    s.check("#早到的事件已建任务表", s.js("S.plan.tasks.size") == 1,
            s.js("S.plan.tasks.size"))
    s.wait("S.startRequest.state === 'settled' && S.busy === true", 8000)
    s.check("#ack 后忙态成立", s.js("S.busy === true"), s.js("S.busy"))
    s.check("#ack 不清已收任务", s.js("S.plan.tasks.size") == 1,
            s.js("S.plan.tasks.size"))
    s.check("#ack 不抹已收到的提交次数",
            s.js("(S.plan.tasks.get('t1')||{}).attempts") == 2,
            s.js("(S.plan.tasks.get('t1')||{}).attempts"))
    s.shot("early-events-before-ack")


@scenario("early-terminal-before-ack", "终态早于开始 ack：ack 不复活已结束计划", (1120, 800), "valid")
def _(s: Session):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    # ack 延迟 600ms；30ms 后先推 plan/task/plan_done(completed)
    s.set_state(earlyTerminalBeforeAck=True, earlyAckDelayMs=600)
    s.click("#btn-plan")
    s.wait("S.plan.status === 'completed' && S.busy === false", 8000)
    s.check_contains("#result", "已报名 1 场")
    s.wait("S.startRequest.state === 'settled'", 8000)
    s.page.wait_for_timeout(300)
    s.check("#迟到的 ack 不复活忙态", s.js("S.busy === false"), s.js("S.busy"))
    s.check("#开始标志已释放", s.js("S.starting === false"), s.js("S.starting"))
    s.check("#终态结论保持", s.js("S.plan.status") == "completed",
            s.js("S.plan.status"))
    s.check("#次数保留", s.js("(S.plan.tasks.get('t1')||{}).attempts") == 1,
            s.js("(S.plan.tasks.get('t1')||{}).attempts"))
    s.check("#不重发开始", s.js(
        "window.__QA_CALLS.filter((c) => c.name === 'start_plan').length") == 1,
        s.js("window.__QA_CALLS.filter((c) => c.name === 'start_plan').length"))
    s.check("#LED 保持成功结论", s.attr("#led", "data-tone") != "red",
            s.attr("#led", "data-tone"))
    s.shot("early-terminal-before-ack")


@scenario("clock-skew-boot-8h", "开机前本机错 +8 小时仍显北京时间", (1120, 800), "valid")
def _(s: Session):
    s.inject_wall_skew(8 * 3600 * 1000)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait_business_ready()
    s.check_clock_text("顶栏时间不随本机 +8 小时漂移")
    s.check_unique_clock()
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.check_nowline("现在线 = 权威北京时间（本机 +8h）")
    s.check_last_check_pill()
    # 等待 LED 与任务卡：等待倒计时按业务时钟推进，不因错时显示待校准
    s.pick("a-future")
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "waiting",
                         signup_mode="pre_register",
                         sign_start=s.js("S.byId.get('a-future').sign_start")))
    s.wait("document.querySelector('#btn-stop').disabled === false")
    metric = s.js("() => document.querySelector('#countdown').textContent")
    s.check("倒计时按北京时间推进（非待校准）",
            "待校准" not in metric and "同时开放" in metric, metric)
    s.check_contains("#led-label", "同时开放 1 场，开放")
    s.check("LED 倒计时是数字不是占位", s.js(
        "() => { const t = document.querySelector('#led-label').textContent;"
        " return t.indexOf('--:--') < 0 && t.indexOf('待校准') < 0; }"), s.text("#led-label"))
    s.shot("skew-boot-8h")


@scenario("clock-skew-boot-30d", "开机前本机错 -30 天仍显北京时间", (1120, 800), "valid")
def _(s: Session):
    s.inject_wall_skew(-30 * 86400 * 1000)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait_business_ready()
    s.check_clock_text("顶栏时间不随本机 -30 天漂移")
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.check("#错日期下列表仍有可报名行",
            s.js("S.items.some((i) => modeOf(i) !== 'closed' && !i.signed)"),
            s.js("S.items.map((i) => modeOf(i))"))
    s.check_nowline("现在线 = 权威北京时间（本机 -30d）")
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled", 6000)
    s.check("开始按钮未被错日期禁死", s.js("!document.querySelector('#btn-plan').disabled"),
            s.text("#btn-plan"))
    s.shot("skew-boot-30d")


@scenario("wall-jump-during-plan", "运行中系统墙钟跳 30 天不影响业务时钟", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    before = s.js("""() => {
      const fmt = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai',
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
      return { text: document.querySelector('#clock-time').textContent.trim(),
               expect: fmt.format(new Date(window.__QA_CLOCK_NOW() * 1000)) };
    }""")
    s.check("注入前顶栏已显北京时间", before["text"] == before["expect"], before)
    # 运行中注入 +30 天：不 reload，等 1 秒 tick 重绘后顶栏仍为北京时间
    s.skew_wall_now(30 * 86400 * 1000)
    s.page.wait_for_timeout(1400)
    s.check_clock_text("运行中 +30 天后顶栏仍为北京时间")
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-future")
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "waiting",
                         signup_mode="pre_register",
                         sign_start=s.js("S.byId.get('a-future').sign_start")))
    s.wait("document.querySelector('#btn-stop').disabled === false")
    metric = s.js("() => document.querySelector('#countdown').textContent")
    s.check("错日期下倒计时仍按北京时间", "待校准" not in metric and "同时开放" in metric, metric)
    s.check_nowline("运行中错时后现在线仍为北京时间")
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "failed",
                         stop="unconfirmed", attempts=1, reason="响应丢失"))
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "failed",
                         "summary": {"total": 1, "counts": {"failed": 1}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#result", "待核对 1 场")
    s.shot("wall-jump-during-plan")


@scenario("clock-skew-runtime-minus8h", "运行中系统墙钟回拨 8 小时不回显旧时刻", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    s.pick("a-future")
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "waiting",
                         signup_mode="pre_register",
                         sign_start=s.js("S.byId.get('a-future').sign_start")))
    s.wait("document.querySelector('#btn-stop').disabled === false")
    s.skew_wall_now(-8 * 3600 * 1000)
    s.page.wait_for_timeout(1400)
    s.check_clock_text("运行中 -8 小时后顶栏仍为北京时间")
    metric = s.js("() => document.querySelector('#countdown').textContent")
    s.check("回拨后等待倒计时不凭空变长（按北京时间）",
            "待校准" not in metric and "同时开放" in metric, metric)
    s.check_contains("#led-label", "同时开放 1 场，开放")
    s.check("回拨后忙时胶囊保持登录结论", s.text("#pill-text").strip() == "已登录",
            s.text("#pill-text"))
    s.shot("skew-runtime-minus8h")


@scenario("clock-unavailable-start", "校时不可用：开始禁用单一原因、恢复即解禁", (1120, 800), "valid")
def _(s: Session):
    s.inject_state(clockUnavailable=True)
    s.inject_wall_skew(30 * 86400 * 1000)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.check("顶栏时间显示待校准", s.text("#clock-time").strip() == "待校准",
            s.text("#clock-time"))
    s.check_unique_clock()
    s.pick("a-future")
    s.check("#时钟不可用时开始禁用", s.page.locator("#btn-plan").is_disabled())
    s.check("#禁用原因单一可见", s.text("#btn-plan").strip() == "北京时间未校准",
            s.text("#btn-plan"))
    s.check("#登录校验与时钟正交（仍有效）", s.js("S.login.result") == "valid",
            s.js("S.login.result"))
    s.check_contains("#pill-text", "已登录")
    # 恢复：真实指针点开时间详情并点击「重新校准时间」
    rec = s.pointer("#clock", "open-clock-pop")
    s.check("#时钟入口真实命中", s.hit_in(rec, "#clock"), rec.get("hit"))
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    s.set_state(clockUnavailable=False)
    rec2 = s.pointer("#clock-pop-sync", "resync")
    s.check("#重新校准按钮真实命中", s.hit_in(rec2, "#clock-pop-sync"), rec2.get("hit"))
    s.wait("document.querySelector('#clock').dataset.state === 'ready'", 12000)
    s.wait_business_ready()
    s.check_clock_text("恢复后顶栏为权威北京时间")
    s.check("#恢复校时后开始解禁", s.js("!document.querySelector('#btn-plan').disabled"))
    s.check("#恢复过程不触发登录", s.calls_count("login") == 0, s.calls_count("login"))
    s.check("#恢复过程不触发开始计划", s.calls_count("start_plan") == 0,
            s.calls_count("start_plan"))
    s.shot("clock-unavailable-start")


@scenario("clock-sync-failure-feedback", "重新校时失败：反馈只在时间详情", (1120, 800), "valid")
def _(s: Session):
    s.inject_state(clockUnavailable=True)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.pointer("#clock", "open-clock-pop")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    s.check_contains("#clock-pop-status", "时间校准失败")
    s.check("详情说明不可用原因", "暂时无法获取北京时间" in s.text("#clock-pop-feedback"),
            s.text("#clock-pop-feedback"))
    s.check("失败态按钮叫重试校准", s.text("#clock-pop-sync").strip() == "重试校准",
            s.text("#clock-pop-sync"))
    s.pointer("#clock-pop-sync", "resync-fail")
    s.wait("S.businessClock.syncState === 'idle' && document.querySelector('#clock-pop-feedback')"
           ".textContent.includes('本次校准未成功')", 8000)
    s.check("#失败反馈只在详情（不占结果框）", s.js("document.querySelector('#result').hidden"),
            s.text("#result")[:80])
    s.check("#失败后开始仍禁用", s.page.locator("#btn-plan").is_disabled())
    s.check("#失败不触发登录", s.calls_count("login") == 0, s.calls_count("login"))
    s.check("#失败不触发开始计划", s.calls_count("start_plan") == 0,
            s.calls_count("start_plan"))
    s.shot("clock-sync-failure")


@scenario("clock-holdover-expiry", "holdover 仍可用、过期转待校准并可恢复", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    s.check_clock_text("holdover 前顶栏为权威北京时间")
    # 注入 420 秒授时年龄：超过 300 秒 → holdover，仍可显示
    s.emit_clock(clockAgeS=420)
    s.wait("document.querySelector('#clock').dataset.state === 'holdover'", 8000)
    s.check("holdover 仍显示时间", ":" in s.text("#clock-time"), s.text("#clock-time"))
    s.check("holdover 顶栏标题说明沿用上次校准",
            "使用上次校准结果" in (s.attr("#clock", "title") or ""), s.attr("#clock", "title"))
    s.pointer("#clock", "open-pop-holdover")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    s.check_contains("#clock-pop-status", "使用上次校准结果")
    s.check("holdover 详情给出解释", len(s.text(".pop-explain").strip()) > 0,
            s.text(".pop-explain"))
    s.page.keyboard.press("Escape")
    s.wait("document.querySelector('#clock-pop').hidden === true", 4000)
    s.check("Esc 关详情后焦点回时钟入口",
            s.js("document.activeElement && document.activeElement.id === 'clock'"),
            s.js("document.activeElement && document.activeElement.id"))
    # 过期：905 秒年龄 → unavailable，显示待校准并禁用开始
    s.emit_clock(clockAgeS=905)
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.check("过期后显示待校准", s.text("#clock-time").strip() == "待校准",
            s.text("#clock-time"))
    s.pick("a-future")
    s.check("过期后开始禁用", s.page.locator("#btn-plan").is_disabled())
    s.check("过期禁用原因单一", s.text("#btn-plan").strip() == "北京时间未校准",
            s.text("#btn-plan"))
    # 恢复：年龄归零 + 更高代次 → 重新可读
    s.emit_clock(clockAgeS=0)
    s.wait("document.querySelector('#clock').dataset.state === 'ready'", 10000)
    s.wait_business_ready()
    s.check_clock_text("恢复后顶栏为权威北京时间")
    s.check("恢复后开始解禁", s.js("!document.querySelector('#btn-plan').disabled"))
    s.shot("clock-holdover-expiry")


@scenario("clock-first-sync-delay", "首校时延迟期间不误导且完成后自动恢复", (1120, 800), "valid")
def _(s: Session):
    s.inject_state(clockInitialUnavailable=True)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'syncing'", 8000)
    s.check("首校时未完成显示校准中", s.text("#clock-time").strip() == "校准中…",
            s.text("#clock-time"))
    s.pick("a-future")
    s.check("首校时期间开始禁用", s.page.locator("#btn-plan").is_disabled())
    s.check("禁用原因单一可见", s.text("#btn-plan").strip() == "北京时间未校准",
            s.text("#btn-plan"))
    s.check("等待期不触发登录", s.calls_count("login") == 0, s.calls_count("login"))
    s.check("等待期不触发开始计划", s.calls_count("start_plan") == 0,
            s.calls_count("start_plan"))
    # 后台首校时完成：生产语义 = business_clock 事件 + 更高代次
    s.set_state(clockInitialUnavailable=False)
    s.emit_clock()
    s.wait("document.querySelector('#clock').dataset.state === 'ready'", 10000)
    s.wait_business_ready()
    s.check_clock_text("首校时完成后显示北京时间")
    s.check("首校时完成后开始解禁", s.js("!document.querySelector('#btn-plan').disabled"))
    s.shot("clock-first-sync-delay")


@scenario("clock-status-after-reload", "F5 后锚点恢复且旧代次/旧采样/同代误报不倒退", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    s.check_clock_text("F5 前顶栏时间 = 权威北京时间")
    anchor0 = s.js("S.businessClock.anchorEpochMs")
    # 同代旧采样（锚点早 100 秒）：不得把显示时间拖回去
    s.js("""() => {
      const nowS = window.__QA_CLOCK_NOW();
      window.onBackend.business_clock({ schema: 1, owner_id: 'qa-clock',
        generation: S.businessClock.gen, state: 'ready',
        epoch_s: nowS - 100, tick_s: 0, sampled_tick_s: 0,
        uncertainty_s: 0.2, source: 'qa-ntp', age_s: 0, reason: '旧采样' });
    }""")
    s.page.wait_for_timeout(300)
    s.check("同代旧采样不回退锚点",
            s.js("S.businessClock.anchorEpochMs") >= anchor0 - 2000,
            [anchor0, s.js("S.businessClock.anchorEpochMs")])
    s.check_clock_text("旧采样后顶栏仍为权威北京时间")
    # 更低代次：不得覆盖
    s.js("""() => window.onBackend.business_clock({ schema: 1, owner_id: 'qa-clock',
      generation: 0, state: 'ready', epoch_s: 1000, tick_s: 0,
      sampled_tick_s: 0, uncertainty_s: 0.2, source: 'old', age_s: 0, reason: 'old' })""")
    s.page.wait_for_timeout(200)
    s.check("旧代次不回写锚点",
            s.js("S.businessClock.anchorEpochMs") >= anchor0 - 2000,
            [anchor0, s.js("S.businessClock.anchorEpochMs")])
    # 同代 unavailable 误报：不得抹掉已建立的可读锚点
    s.js("""() => window.onBackend.business_clock({ schema: 1, owner_id: 'qa-clock',
      generation: S.businessClock.gen, state: 'unavailable', epoch_s: null,
      tick_s: null, sampled_tick_s: null, uncertainty_s: 0, source: 'qa-ntp',
      age_s: null, reason: '暂时无法获取北京时间（同代误报）' })""")
    s.page.wait_for_timeout(200)
    s.check("同代误报不抹锚点",
            s.js("S.businessClock.state") in ("ready", "holdover")
            and s.js("S.businessClock.anchorEpochMs") >= anchor0 - 2000,
            s.js("S.businessClock.state"))
    s.check_clock_text("同代误报后仍显示北京时间")
    # 更高代次 holdover：接受并更新
    s.emit_clock(clockAgeS=420)
    s.wait("document.querySelector('#clock').dataset.state === 'holdover'", 8000)
    s.check("更高代次更新为沿用上次校准", True)
    s.check("代次单调不减", s.js("S.businessClock.gen") >= 2, s.js("S.businessClock.gen"))
    # F5：bootstrap 权威快照重建锚点，旧代次事件不得污染
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait_business_ready()
    s.check_clock_text("F5 后锚点按权威快照恢复")
    s.check("F5 后时钟可读", s.js("S.businessClock.state") in ("ready", "holdover"),
            s.js("S.businessClock.state"))
    s.shot("clock-status-after-reload")


@scenario("clock-sampled-age-uncertainty", "采样误差与年龄分离：age400/unc0.47 仍可用", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.emit_clock(clockAgeS=400, clockUncertaintyS=0.47)
    s.wait("document.querySelector('#clock').dataset.state === 'holdover'", 8000)
    s.check("400 秒旧锚点仍显示时间", ":" in s.text("#clock-time"), s.text("#clock-time"))
    s.pick("a-future")
    s.check("可用快照不提前禁用开始", s.js("!document.querySelector('#btn-plan').disabled"))
    s.check("业务时刻仍可读", s.js("businessNowMs() !== null"))
    s.pointer("#clock", "open-age400")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    pop = s.js("""() => {
      const pop = document.querySelector('#clock-pop');
      return { state: pop.dataset.state,
               text: pop.textContent,
               rows: Array.from(pop.querySelectorAll('.facts div')).map((d) => d.textContent) };
    }""")
    s.check("浮层状态为沿用上次校准", pop["state"] == "holdover", pop["state"])
    s.check("详情误差约 0.47 秒（不叠加采样前漂移）",
            any("0.47" in row for row in pop["rows"]), pop["rows"])
    s.check("详情不显示成 0.51 秒", "0.51" not in pop["text"], pop["text"][-200:])
    s.shot("age400-unc047")


@scenario("clock-f5-old-calibration-age", "F5 接入旧锚点不刷新最近校准", (1120, 800), "valid")
def _(s: Session):
    s.inject_state(clockAgeS=600)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'holdover'", 8000)
    s.pointer("#clock", "open-f5-age")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    text = s.text("#clock-pop")
    s.check("F5 后显示真实校准年龄", "10 分钟前" in text, text[:400])
    s.check("F5 不把旧锚点说成刚刚", "刚刚" not in text, text[:400])
    s.check("权威 age 保持 600 秒",
            abs(s.js("S.businessClock.sampleAgeMs") - 600000) < 1,
            s.js("S.businessClock.sampleAgeMs"))
    s.shot("f5-old-age")


@scenario("clock-unknown-known-open-time", "校时失败不把已知开放时间说成待公布", (1120, 800), "valid")
def _(s: Session):
    s.inject_state(clockUnavailable=True)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    data = s.js("""() => {
      const row = (id) => document.querySelector('.row[data-id="' + id + '"]');
      const unknown = document.querySelector('.gsec[data-g="unknown"]');
      return {
        futureState: row('a-future').querySelector('.c-state').textContent.trim(),
        futureTime: row('a-future').querySelector('.c-time').textContent.trim(),
        futureInUnknown: unknown
          ? unknown.textContent.includes('人工智能前沿讲座') : false,
        noSignInUnknown: unknown
          ? unknown.textContent.includes('开放时间未公布') : false,
        signedState: row('a-signed').querySelector('.c-state').textContent.trim(),
        board: document.querySelector('#selected').textContent.trim(),
        boardText: document.querySelector('#board-text').textContent,
        boardButtons: document.querySelectorAll('#board-text [data-open-clock]').length,
        metricFree: document.querySelector('#metric-free').textContent.trim(),
        metricTotal: document.querySelector('#metric-total').textContent.trim(),
      };
    }""")
    s.check("已知开放时间保留", ":" in data["futureTime"], data["futureTime"])
    s.check("已知开放时间标待校准", "待校准" in data["futureState"], data["futureState"])
    s.check("不把已知开放时间塞进待公布组", not data["futureInUnknown"], data)
    s.check("真正缺开放时间的仍在待公布组", data["noSignInUnknown"], data)
    s.check("已报名事实保留", "已报名" in data["signedState"], data["signedState"])
    s.check("大屏只报时间待校准", data["board"] == "时间待校准", data["board"])
    s.check("大屏不断言没有可报名场次",
            "没有可报名的场次" not in data["boardText"], data["boardText"])
    s.check("大屏恢复入口唯一", data["boardButtons"] == 1, data["boardButtons"])
    s.check("可报名计数不伪造", data["metricFree"] == "待确认", data["metricFree"])
    s.check("列表总数仍真实", data["metricTotal"].isdigit(), data["metricTotal"])
    s.shot("unknown-clock-known-time")
    # 恢复：选中一项并改策略，校时恢复后原地重算且不丢选择/策略
    s.pick("a-future")
    s.js("() => { S.retryPolicy = { retry_for_s: 600, max_attempts: 2 }; }")
    s.set_state(clockUnavailable=False)
    s.emit_clock(clockAgeS=0, clockUncertaintyS=0.2)
    s.wait("document.querySelector('#clock').dataset.state === 'ready'", 10000)
    s.wait_business_ready()
    after = s.js("""() => ({
      metricFree: document.querySelector('#metric-free').textContent.trim(),
      countdown: document.querySelector('#countdown').textContent.trim(),
      selected: Array.from(S.selected), policy: S.retryPolicy,
      futureState: document.querySelector('.row[data-id="a-future"] .c-state')
        .textContent.trim(),
    })""")
    s.check("恢复后计数真实", after["metricFree"].isdigit(), after["metricFree"])
    s.check("恢复后倒计时重算", "待校准" not in after["countdown"], after["countdown"])
    s.check("恢复后不丢选择", after["selected"] == ["a-future"], after["selected"])
    s.check("恢复后不丢重试策略",
            after["policy"] == {"retry_for_s": 600, "max_attempts": 2}, after["policy"])
    s.check("恢复后行状态重算", "待校准" not in after["futureState"], after["futureState"])
    s.shot("recovered")


@scenario("clock-failure-icon-color", "校时失败状态图形与顶栏同为警告色", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    s.pointer("#clock", "open-normal")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    probe = """() => ({
      color: getComputedStyle(
        document.querySelector('#clock-pop-status .state-icon')).color,
      state: document.querySelector('#clock-pop').dataset.state,
      label: document.querySelector('#clock-pop-status').textContent.trim() })"""
    ready = s.js(probe)
    s.check("正常态浮层图形成功色", ready["state"] == "ready", ready)
    s.page.keyboard.press("Escape")
    s.set_state(clockUnavailable=True)
    s.emit_clock(clockAgeS=0, clockUncertaintyS=0.2)
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.pointer("#clock", "open-failure")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    failed = s.js(probe)
    s.check("失败态浮层图形警告色", failed["state"] == "unavailable", failed)
    s.check("失败与正常状态图形颜色不同", failed["color"] != ready["color"],
            [ready, failed])
    s.check("失败态标签为时间校准失败", "时间校准失败" in failed["label"], failed["label"])
    s.shot("failure-icon-color")


@scenario("clock-five-states", "时钟状态渲染：校准中/失败/holdover/ready", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait_business_ready()
    s.shot("ready")
    # 从真实 bootstrap 接入首轮进行中的后端快照，不直接改生产 S 状态。
    s.inject_state(clockInitialUnavailable=True)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'syncing'", 4000)
    s.check("校准中顶栏文案", s.text("#clock-time").strip() == "校准中…",
            s.text("#clock-time"))
    s.pointer("#clock", "open-syncing")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    s.check_contains("#clock-pop-status", "正在校准")
    s.shot("syncing")
    s.page.keyboard.press("Escape")
    s.emit_clock(clockInitialUnavailable=False, clockAgeS=400, clockUncertaintyS=0.3)
    s.wait("document.querySelector('#clock').dataset.state === 'holdover'", 8000)
    s.shot("holdover")
    s.set_state(clockUnavailable=True)
    s.emit_clock(clockAgeS=0, clockUncertaintyS=0.2)
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'", 8000)
    s.shot("failure")


@scenario("clock-state-demo", "演示时间浮层中性色", (1120, 800), "demo")
def _(s: Session):
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'demo'", 8000)
    s.pointer("#clock", "open-demo")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    demo = s.js("""() => ({
      state: document.querySelector('#clock-pop').dataset.state,
      label: document.querySelector('#clock-pop-status').textContent.trim() })""")
    s.check("演示浮层状态为 demo", demo["state"] == "demo", demo)
    s.check("演示标签", "演示时间" in demo["label"], demo["label"])
    s.shot("demo")


def _cached_terminal_wall_jump(s: Session, offset_ms: int, tag: str) -> None:
    """终态先暂存 → OS 墙钟跳变 → skipped ack 到达：必须仍立即重放。"""
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.js("""(off) => {
      window.__QA_STATE.nextCheckSkipped = true;
      S.login.checking = true;
      S.login.result = null;
      refresh(false);
      window.__QA_EMIT('check', { request_id: 'qa-old-check', ok: true,
        result: 'valid', session_present: true, hours_left: 6 });
      const real = Date.now.bind(Date);
      Date.now = () => real() + off;
    }""", offset_ms)
    s.wait("S.login.result === 'valid'", 5000)
    s.check("墙钟%s后终态仍立即重放" % tag, s.js("S.login.checking === false"))
    s.check("重放后暂存清空", s.js("S.round.cache.length") == 0,
            s.js("S.round.cache.length"))
    s.check("重放不重复发起检查",
            s.js("window.__QA_CALLS.filter((c) => c.name === 'check').length") <= 2)
    s.shot("wall-jump-%s" % tag)


@scenario("clock-cached-terminal-wall-forward", "暂存终态跨 OS 前移 8 小时仍重放", (1120, 800), "skipped")
def _(s: Session):
    _cached_terminal_wall_jump(s, 8 * 3600 * 1000, "forward")


@scenario("clock-cached-terminal-wall-back", "暂存终态跨 OS 回拨 30 天仍重放", (1120, 800), "skipped")
def _(s: Session):
    _cached_terminal_wall_jump(s, -30 * 86400 * 1000, "back")


@scenario("legacy-session-valid-no-estimate", "旧会话有效但不编造估算小时数", (1120, 800), "legacy_session")
def _(s: Session):
    s.settle()
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')", 10000)
    s.check_contains("#pill-text", "已登录")
    # 旧断言「剩余时间明说未知、建议重新登录恢复估算」随剩余时间一起退场（架构方案 4.5）：
    # 现在胶囊只写上次校验时刻，说明里讲清有效期学校不公布、工具不估算。
    s.check_last_check_pill()
    s.check_not_contains("#status-detail", "约剩")
    note = s.text("#status-detail")
    s.check("详情说明登录本身有效", "登录有效" in note, note)
    s.check("详情说明有效期不估算", "学校不公布" in note, note)
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    # 时间详情不再有登录剩余那一行（登录看登录状态卡），旧 saved_at 更不会被拿来冒充。
    s.pointer("#clock", "open-pop-legacy")
    s.wait("!document.querySelector('#clock-pop').hidden", 4000)
    pop_state = s.js(
        "() => ({ hidden: document.querySelector('#clock-pop').hidden,"
        " left: document.querySelector('#clock-pop-left') ? 'HAS-NODE' : 'NO-NODE',"
        " text: document.querySelector('#clock-pop').textContent })")
    s.check("时间详情不显示登录剩余", pop_state["left"] == "NO-NODE"
            and "登录预计剩余" not in pop_state["text"], pop_state)
    s.page.keyboard.press("Escape")
    s.wait("document.querySelector('#clock-pop').hidden === true", 4000)
    s.shot("legacy-session")


@scenario("login-flow-first-success", "首次登录成功只报一次绿色结论", (1120, 800), "unlogged")
def _(s: Session):
    s.settle()
    s.check_contains("#pill-text", "未登录")
    s.set_state(loginDone=True, loginOk=True, check="valid")
    rec = s.browser_login("login")
    s.check("#登录按钮真实命中", s.hit_in(rec, "#btn-login"), rec.get("hit"))
    s.wait("document.querySelector('#result').textContent.includes('登录成功')", 8000)
    s.check_contains("#result strong", "登录成功")
    s.check("#成功结论不染红", "is-bad" not in (s.attr("#result", "class") or ""),
            s.attr("#result", "class"))
    s.wait("S.login.checking === false", 12000)
    s.check_contains("#pill-text", "已登录")
    s.check_last_check_pill()
    s.check("#只发起一次登录", s.calls_count("login") == 1, s.calls_count("login"))
    s.check("#登录后排队校验登录态", s.calls_count("check") >= 1, s.calls_count("check"))
    red_lines = s.js("""() => Array.from(document.querySelectorAll('#log .lg'))
      .filter((el) => el.textContent.indexOf('登录没完成') >= 0
                   || el.textContent.indexOf('登录没能开始') >= 0
                   || el.textContent.indexOf('报名未成功') >= 0).length""")
    s.check("#首次登录没有红色失败复读", red_lines == 0, red_lines)
    s.shot("login-success")


@scenario("login-four-states", "四态登录与未知小时数准确（含已选择×四态门禁）", (1120, 800), "valid")
def _(s: Session):
    def _matrix(tag: str) -> None:
        """已选择 × 当前登录态的按钮矩阵：开始禁用、登录/刷新不被连坐、选择不丢。
        读 DOM 的 disabled 属性本身，不用 is_disabled 的观感判定（B04 门禁）。"""
        s.check("%s：#btn-plan 禁用" % tag,
                s.js("document.querySelector('#btn-plan').disabled === true"),
                s.js("document.querySelector('#btn-plan').disabled"))
        s.check("%s：#btn-refresh 保持可用" % tag,
                s.js("document.querySelector('#btn-refresh').disabled === false"),
                s.js("document.querySelector('#btn-refresh').disabled"))
        s.check("%s：#btn-login 保持可用" % tag,
                s.js("document.querySelector('#btn-login').disabled === false"),
                s.js("document.querySelector('#btn-login').disabled"))
        s.check("%s：已选择不丢" % tag, s.js("S.selected.has('a-future')"),
                s.js("Array.from(S.selected).join(',') || '（空）'"))

    s.settle()
    # 1) 有效：已登录 + 估算小时数
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')")
    s.check_last_check_pill()
    s.check("有效时按钮叫重新登录", s.text("#btn-login-text").strip() == "重新登录")
    # 已选择 × 四态矩阵：真实勾选一场可报名活动，checking/unknown/none/expired
    # 下开始一律禁用（plan-panel.js loginReady），登录/刷新保持可用，选择不丢；
    # 回到 valid 恢复可用。
    s.pick("a-future")
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.check("valid+已选择：#btn-plan 可用",
            s.js("!document.querySelector('#btn-plan').disabled"),
            s.js("document.querySelector('#btn-plan').disabled"))
    # checking：check 分支放慢 1200ms、list 分支先落定——检查期不得放行开始
    s.set_state(check="slow")
    s.click("#btn-refresh")
    s.wait("S.listState === 'ready' && S.login.checking === true", 8000)
    _matrix("checking")
    s.wait("S.login.checking === false", 8000)
    # 2) 失效：明确叫重新登录
    s.set_state(check="expired")
    s.click("#btn-refresh")
    s.wait("document.querySelector('#pill-text').textContent.includes('登录已失效')", 8000)
    s.check("失效按钮叫重新登录", s.text("#btn-login-text").strip() == "重新登录")
    s.check("失效说明给动作", "重新登录" in s.text("#status-detail"), s.text("#status-detail"))
    _matrix("expired")
    # 3) 未知：不诱导重登、不编小时数
    s.set_state(check="unknown")
    s.click("#btn-refresh")
    s.wait("document.querySelector('#pill-text').textContent.includes('登录待确认')", 8000)
    s.check_contains("#pill-text", "登录待确认")
    s.check_not_contains("#pill-text", "登录已失效")
    s.check("未知说明给恢复动作", "刷新" in s.text("#status-detail")
            and "先不用重新登录" in s.text("#status-detail"), s.text("#status-detail"))
    s.check("未知小时数留空", s.text("#pill-sub").strip() == "", s.text("#pill-sub"))
    _matrix("unknown")
    # 4) 未登录：引导首次登录
    s.set_state(check="none")
    s.click("#btn-refresh")
    s.wait("document.querySelector('#pill-text').textContent.includes('未登录')", 8000)
    s.check("未登录按钮叫登录", s.text("#btn-login-text").strip() == "登录")
    _matrix("none")
    # 回到有效：开始恢复可用，选择仍在
    s.set_state(check="valid")
    s.click("#btn-refresh")
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')", 8000)
    s.wait("!document.querySelector('#btn-plan').disabled")
    s.check("回到 valid：#btn-plan 恢复可用",
            s.js("!document.querySelector('#btn-plan').disabled"),
            s.js("document.querySelector('#btn-plan').disabled"))
    s.check("回到 valid：已选择不丢", s.js("S.selected.has('a-future')"),
            s.js("Array.from(S.selected).join(',') || '（空）'"))
    s.shot("login-four-states")


@scenario("relogin-cancel-fail-keeps-session", "重登取消/失败整份回滚登录快照", (1120, 800), "valid")
def _(s: Session):
    """浏览器级复刻 B02 契约：取消/超时/失败都整份回滚到尝试前，旧会话仍有效。"""
    s.settle()
    s.wait("document.querySelector('#pill-text').textContent.includes('已登录')")
    s.check_last_check_pill()
    before = s.js("""() => ({
        pill: document.querySelector('#pill-text').textContent.trim(),
        sub: document.querySelector('#pill-sub').textContent.trim(),
        btn: document.querySelector('#btn-login-text').textContent.trim(),
        expireAt: S.login.expireAt, savedAt: S.login.savedAt })""")

    def _rollback(tag: str, title_needle: str) -> None:
        s.check("%s：胶囊仍已登录" % tag,
                s.js("document.querySelector('#pill-text').textContent.includes('已登录')"),
                s.js("document.querySelector('#pill-text').textContent"))
        s.check("%s：不画登录已失效" % tag,
                s.js("!document.querySelector('#pill-text').textContent.includes('登录已失效')"),
                s.js("document.querySelector('#pill-text').textContent"))
        s.check("%s：上次校验时刻不变" % tag,
                s.js("document.querySelector('#pill-sub').textContent.trim() === %s"
                     % json.dumps(before["sub"])),
                s.js("document.querySelector('#pill-sub').textContent.trim()"))
        s.check("%s：按钮文字复原" % tag,
                s.js("document.querySelector('#btn-login-text').textContent.trim() === %s"
                     % json.dumps(before["btn"])),
                s.js("document.querySelector('#btn-login-text').textContent.trim()"))
        s.check("%s：零锚点写入" % tag,
                s.js("S.login.expireAt === %s && S.login.savedAt === %s"
                     % (json.dumps(before["expireAt"]), json.dumps(before["savedAt"]))),
                [s.js("S.login.expireAt"), s.js("S.login.savedAt")])
        s.check("%s：尝试前快照已清" % tag, s.js("S.login.preLoginSnapshot === null"),
                s.js("S.login.preLoginSnapshot"))
        s.check("%s：大屏回到非登录态" % tag,
                s.js("document.querySelector('#board-tag-text').textContent") != "登录中",
                s.js("document.querySelector('#board-tag-text').textContent"))
        s.check("%s：结果框只报这次失败" % tag, title_needle in s.text("#result"),
                s.text("#result")[:120])

    # (a) 失败路径：worker 等满 10 分钟没检测到登录——挂起期先证明「登录中」，
    # 不得提前报失败；终态后整份回滚
    s.set_state(loginDone=True, loginOk=False,
                loginReason="仍未检测到登录成功", loginDelayMs=1500)
    s.browser_login("relogin-fail")
    s.wait("S.login.loginPending === true && S.busy === true", 8000)
    s.check("挂起期大屏进入登录中",
            s.js("document.querySelector('#board-tag-text').textContent") == "登录中",
            s.js("document.querySelector('#board-tag-text').textContent"))
    s.check("挂起期不提前报失败", s.js("document.querySelector('#result').hidden"),
            s.text("#result")[:120])
    s.wait("S.login.loginPending === false", 12000)
    _rollback("失败终态", "还没登录成功")
    s.check("失败登录按钮恢复可用", s.js("!document.querySelector('#btn-login').disabled"))
    s.shot("relogin-fail-rollback")

    # (b) 取消路径：登录窗口被关掉——同样整份回滚，且零锚点写入
    s.wait("!document.querySelector('#btn-login').disabled")
    s.set_state(loginOk=False, loginReason="窗口被关掉", loginDelayMs=300)
    s.browser_login("relogin-cancel")
    s.wait("S.login.loginPending === false", 12000)
    _rollback("取消终态", "登录窗口被关掉了")
    s.shot("relogin-cancel-rollback")


@scenario("busy-pill-login-state", "忙时胶囊保持登录结论且操作禁用", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.pick("a-future")
    s.click("#btn-plan")
    s.wait("S.busy === true")
    s.check_contains("#pill-text", "已登录")
    s.check("#忙时登录按钮禁用", s.page.locator("#btn-login").is_disabled())
    s.check("#忙时刷新保持可用（恢复路径不封死）",
            s.js("!document.querySelector('#btn-refresh').disabled"))
    s.check("#忙时不拿「正在处理」顶替登录结论",
            "正在" not in s.text("#pill-text"), s.text("#pill-text"))
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "waiting",
                         signup_mode="pre_register",
                         sign_start=s.js("S.byId.get('a-future').sign_start")))
    s.wait("document.querySelector('#btn-stop').disabled === false")
    s.check_contains("#pill-text", "已登录")
    s.shot("busy-pill")
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "stopped",
                         "summary": {"total": 1, "counts": {"canceled": 1}}})
    s.wait("S.busy === false", 8000)
    s.check_contains("#pill-text", "已登录")
    s.check("#停止后登录按钮恢复可用", s.js("!document.querySelector('#btn-login').disabled"))


@scenario("signed-clear-no-cancel", "已报名移出计划不调用学校取消、不自动重开", (1120, 800), "valid")
def _(s: Session):
    s.settle()
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.pick("a-open")
    s.click("#btn-plan")
    s.wait("S.busy === true && S.plan.id === 'qa-plan'")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-open", "校园歌手大赛决赛", "success",
                         stop="success", attempts=1, reason="报名成功"))
    s.emit("plan_done", {"plan_id": "qa-plan", "status": "completed",
                         "summary": {"total": 1, "counts": {"success": 1}}})
    s.wait("!document.querySelector('#result').hidden")
    s.check_contains("#plan-tasks", "报名成功")
    clears_before = s.calls_count("cancel_task")
    s.check("#清空按钮已恢复可用", s.js("!document.querySelector('#btn-clear-plan').disabled"))
    s.click("#btn-clear-plan")
    s.wait("S.busy === false && S.plan.status === 'idle'", 6000)
    s.check("移出计划不调用学校取消", s.calls_count("cancel_task") == clears_before == 0,
            [clears_before, s.calls_count("cancel_task")])
    s.check("移出计划不重发开始", s.calls_count("start_plan") == 1, s.calls_count("start_plan"))
    s.check("移出后大屏回预览",
            s.js("document.querySelector('#board').dataset.planState") == "idle",
            s.js("document.querySelector('#board').dataset.planState"))
    s.check("移出后不再显示已报名任务卡", s.count("#plan-tasks .task-row") == 0,
            s.count("#plan-tasks .task-row"))
    s.shot("signed-clear")


def _topbar_matrix(s: Session, tag: str) -> None:
    """登录三态 × 时钟两态组合：名称单行、操作可达、未知态不挤掉入口。"""
    s.settle()
    for check_mode, clock_bad, pill_needle in (
            ("valid", False, "已登录"), ("unknown", False, "登录待确认"),
            ("none", True, "未登录")):
        s.set_state(check=check_mode, clockUnavailable=clock_bad)
        s.js("() => refresh(false)")
        s.wait("document.querySelector('#pill-text').textContent.includes('%s')" % pill_needle,
               10000)
        s.emit_clock()
        s.wait("document.querySelector('#clock').dataset.state === '%s'"
               % ("unavailable" if clock_bad else "ready"), 8000)
        g = s.check_topbar_layout("%s %s×%s" % (tag, pill_needle,
                                                "时钟不可用" if clock_bad else "时钟正常"))
        if clock_bad:
            s.check("%s：未知时钟显示待校准" % tag, g["clockText"] == "待校准", g["clockText"])
            s.check("%s：不可用时开始禁用" % tag, s.page.locator("#btn-plan").is_disabled())
        else:
            s.check("%s：正常时钟显示真实时刻" % tag, ":" in g["clockText"], g["clockText"])
    s.shot("topbar-matrix-%s" % tag)


@scenario("topbar-matrix-1120", "顶栏登录×时钟组合（1120）", (1120, 800), "valid")
def _(s: Session):
    _topbar_matrix(s, "1120")


@scenario("topbar-matrix-980", "顶栏登录×时钟组合（980）", (980, 760), "valid")
def _(s: Session):
    _topbar_matrix(s, "980")


@scenario("topbar-matrix-1280", "顶栏登录×时钟组合（1280）", (1280, 900), "valid")
def _(s: Session):
    _topbar_matrix(s, "1280")


def _hit_id(record: dict, expect: str) -> bool:
    """命中目标校验：那个坐标真的落在预期元素（或它的子节点）上，没被遮挡。"""
    hit = record.get("hit") or {}
    return str(hit.get("id") or "") == str(expect)


def _narrow(s: Session, width: int, height: int):
    s.wait("document.querySelectorAll('#rows .row').length >= 5")
    s.check_unique_clock()
    s.check_topbar_layout("窄窗 %d" % width)
    s.wait_business_ready()
    s.check_clock_text("窄窗顶栏仍显独立北京时间")
    s.check("#无横向滚动", s.js("document.documentElement.scrollWidth <= "
                                "document.documentElement.clientWidth + 1"),
            s.js("[document.documentElement.scrollWidth, document.documentElement.clientWidth]"))

    # FR07：活动区必须有真实可操作高度，不能只剩表头
    geo = s.js("""() => {
      const list = document.querySelector('#rows');
      const table = document.querySelector('.table');
      const lr = list.getBoundingClientRect();
      const tr = table.getBoundingClientRect();
      const rows = Array.from(document.querySelectorAll('#rows .row'));
      const first = rows[0] ? rows[0].getBoundingClientRect() : null;
      /* 可见带 = 列表矩形 ∩ 表格矩形 ∩ 视口：list 自己的 height 可能是被
         父级 overflow:hidden 裁掉之前的值，不能当作「用户看得到多少」。 */
      const top = Math.max(lr.top, tr.top, 0);
      const bottom = Math.min(lr.bottom, tr.bottom, window.innerHeight);
      const visibleH = Math.max(0, bottom - top);
      const overlap = first
        ? Math.max(0, Math.min(bottom, first.bottom) - Math.max(top, first.top)) : 0;
      return { listH: Math.round(lr.height), tableH: Math.round(tr.height),
               visibleH: Math.round(visibleH), rows: rows.length,
               scrollH: Math.round(list.scrollHeight),
               firstRowOverlap: Math.round(overlap),
               pageScrollable: document.documentElement.scrollHeight
                 > document.documentElement.clientHeight + 1 };
    }""")
    s.actions.append({"action": "list-geometry", **geo})
    # 短窗允许整页纵向滚动：要求「现在就看得见」或「滚一下就能看见」，
    # 两者都不成立才是把列表挤没了（修复前 visibleH=11 且不可滚动）。
    s.check("#列表有可操作高度", geo["listH"] >= 120, geo)
    s.check("#列表可达（视口内或页面可滚动）",
            geo["visibleH"] >= 120 or geo["pageScrollable"], geo)
    s.check("#首行可达", geo["firstRowOverlap"] >= 20 or geo["pageScrollable"], geo)

    # 真实指针：两行各自滚到可见处再点，命中目标必须是本行复选框
    first = s.pointer_pick("a-future")
    s.check("#指针命中第一行", (first["hit"] or {}).get("dataId") == "a-future", first["hit"])
    s.check("#第一行选择已改变", s.js("S.selected.has('a-future')"), list(s.js("Array.from(S.selected)")))
    second = s.pointer_pick("a-long")
    s.check("#滚动后仍可选中第二行", s.js("S.selected.has('a-long')"),
            list(s.js("Array.from(S.selected)")))
    s.shot("narrow-%d" % width)

    # 开始 → 停止：两个关键操作在短窗里也必须真的点得到
    planning = s.pointer("#btn-plan", "start")     # pointer() 自己就点击
    s.check("#开始按钮命中", _hit_id(planning, "btn-plan"), planning["hit"])
    s.wait("S.busy === true")
    # 只有计划事件到了才有路线与停止入口：先补真实形状的 plan/task 载荷
    sign_start = s.js("S.byId.get('a-future').sign_start")
    s.emit("plan", {"plan_id": "qa-plan", "status": "running", "tasks": []})
    s.emit("task", _task("t1", "a-future", "人工智能前沿讲座", "waiting",
                         signup_mode="pre_register", sign_start=sign_start))
    s.wait("document.querySelector('#btn-stop').disabled === false")
    s.wait("document.querySelector('#route-line').hidden === false")
    stop = s.pointer("#btn-stop", "stop")
    s.check("#停止按钮命中", _hit_id(stop, "btn-stop"), stop["hit"])
    s.wait("document.querySelector('#dlg-stop').open === true")
    s.check("#停止确认框可打开", True)
    s.page.locator("#dlg-stop button[value='no']").first.click()
    s.wait("document.querySelector('#dlg-stop').open === false")
    s.shot("narrow-%d-running" % width)

    # 帮助入口同样要能到达并关闭
    help_rec = s.pointer("#btn-help", "help")
    s.check("#帮助按钮命中", _hit_id(help_rec, "btn-help"), help_rec["hit"])
    s.wait("document.querySelector('#help').open === true")
    s.page.keyboard.press("Escape")
    s.wait("document.querySelector('#help').open === false")
    s.shot("narrow-%d-help-closed" % width)


@scenario("narrow-746", "压力视口 746x512", (746, 512), "valid")
def _(s: Session):
    _narrow(s, 746, 512)


@scenario("narrow-680", "压力视口 680x480", (680, 480), "valid")
def _(s: Session):
    _narrow(s, 680, 480)


def run_scenarios(base: str, evidence: Path, only: str | None) -> dict:
    from playwright.sync_api import sync_playwright

    report = {"ok": False, "base": base, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "scenarios": [], "failures": []}
    selected = [item for item in SCENARIOS if not only or item["id"] == only]
    if only and not selected:
        raise SystemExit("没有这个场景：%s" % only)

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(channel="msedge", headless=True)
        except Exception as exc:  # noqa: BLE001 - 环境缺失按 blocked 处理
            report["blocked"] = "无法启动 Edge/Playwright：%s" % exc
            return report
        try:
            for item in selected:
                scenario_report = {"id": item["id"], "title": item["title"],
                                   "viewport": item["viewport"], "assertions": [],
                                   "actions": [], "screenshots": [], "console": [],
                                   "page_errors": [], "external_requests": []}
                session = None
                print("[i] 场景 %s …（%dx%d）" % (item["id"], item["viewport"][0],
                                                  item["viewport"][1]))
                try:
                    session = Session(browser, base, evidence, item)
                    if item.get("settle", True):
                        session.settle()
                    item["run"](session)
                    scenario_report["assertions"] = session.assertions
                    scenario_report["actions"] = session.actions
                    scenario_report["screenshots"] = session.screenshots
                    scenario_report["console"] = session.console
                    scenario_report["page_errors"] = session.page_errors
                    scenario_report["external_requests"] = session.external
                    failed = [a for a in session.assertions if not a["ok"]]
                    scenario_report["ok"] = (not failed
                                             and not session.page_errors
                                             and not session.console
                                             and not session.external)
                    if failed:
                        report["failures"].extend(
                            "%s: %s" % (item["id"], a["check"]) for a in failed)
                    if session.page_errors:
                        report["failures"].append("%s: pageerror %s"
                                                  % (item["id"], session.page_errors[0]))
                    if session.external:
                        report["failures"].append("%s: 外部请求 %s"
                                                  % (item["id"], session.external[0]))
                except Exception as exc:  # noqa: BLE001 - 场景失败要写进报告
                    scenario_report["ok"] = False
                    scenario_report["error"] = "%s: %s" % (type(exc).__name__, exc)
                    report["failures"].append("%s: %s" % (item["id"], exc))
                    if session is not None:
                        try:
                            session.shot("failure")
                        except Exception:
                            pass
                        scenario_report["screenshots"] = session.screenshots
                        scenario_report["assertions"] = session.assertions
                        scenario_report["actions"] = session.actions
                        scenario_report["console"] = session.console
                        scenario_report["page_errors"] = session.page_errors
                        scenario_report["external_requests"] = session.external
                finally:
                    if session is not None:
                        session.close()
                report["scenarios"].append(scenario_report)
                print("[%s] %s（断言 %d）" % ("OK" if scenario_report["ok"] else "X",
                                              item["id"], len(scenario_report["assertions"])))
        finally:
            browser.close()
    report["ok"] = not report["failures"]
    report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return report


@scenario("cold-clock-progress-failure-recovery", "真实boot校准中、失败与点击恢复", (1120, 800))
def _(s: Session):
    s.inject_state(clockInitialUnavailable=True)
    s.page.reload(wait_until="domcontentloaded")
    s.settle()
    s.wait("document.querySelector('#clock').dataset.state === 'syncing'")
    s.check("真实bootstrap显示校准中", s.text("#clock-time").strip() == "校准中…")
    s.check("未知LED不误标待公布", "待公布" not in s.text("#led-label"), s.text("#led-label"))
    s.pointer("#clock", "open-first-sync")
    s.check_contains("#clock-pop-status", "正在校准")
    s.shot("real-boot-syncing")
    s.emit_clock(clockInitialUnavailable=False, clockUnavailable=True)
    s.wait("document.querySelector('#clock').dataset.state === 'unavailable'")
    s.check_contains("#clock-pop-status", "时间校准失败")
    s.shot("first-attempt-failed")
    s.set_state(clockUnavailable=False)
    before = s.calls_count("sync_clock")
    s.pointer("#clock-pop-sync", "retry-first-clock")
    s.wait("document.querySelector('#clock').dataset.state === 'ready'")
    s.check("真实点击发起一次校准", s.calls_count("sync_clock") == before + 1)
    s.check_clock_text("恢复后显示北京时间")
    s.shot("retry-recovered")


@scenario("log-business-time", "日志只使用业务时间或worker源时间", (1120, 800))
def _(s: Session):
    s.wait_business_ready()
    data = s.js("""() => {
      const RealDate=Date;
      globalThis.Date=class extends RealDate {
        constructor(...args){super(...(args.length?args:[0]));} static now(){return 0;}
      };
      const before=clockParts(businessNowMs()).time;
      addLog('[i] 日志业务时刻验证');
      const row=document.querySelector('#log').lastElementChild.textContent;
      const after=clockParts(businessNowMs()).time;
      const source='2026-10-26 19:59:00 [i] worker源事件';
      addLog(source);
      return {before,after,row,source,worker:document.querySelector('#log').lastElementChild.textContent};
    }""")
    s.check("日志时间不使用错误OS", any(data["row"].startswith(t + "  ")
                                       for t in [data["before"], data["after"]]), data)
    s.check("worker源时间不被重新盖章", data["worker"] == data["source"], data)
    s.emit_clock(clockUnavailable=True)
    unknown = s.js("""() => { addLog('[i] 未校准日志');
      return document.querySelector('#log').lastElementChild.textContent; }""")
    s.check("缺时钟日志明确待校准", unknown.startswith("待校准  "), unknown)
    s.shot("log-time-dom")


@scenario("preferences-busy-recovery", "设置保存超时有界重试与恢复", (1120, 800))
def _(s: Session):
    s.pick("a-future")       # 与实际使用一致：选择活动后才展示计划设置控件
    s.set_state(prefsBusy=True)
    before = s.calls_count("save_prefs")
    s.pointer("label:has(#headed)", "change-setting-while-locked")
    s.wait("S.saveFailures === 2", 6000)
    s.check("最多一次自动重试", s.calls_count("save_prefs") == before + 2)
    s.check("失败只提示一次", s.js("Array.from(document.querySelectorAll('#log .lg')).filter(x=>x.textContent.includes('设置暂未保存')).length") == 1)
    s.check("会话设置与待保存值保留", s.js("S.prefs.headed === true && S.savePending.headed === true"))
    s.shot("save-busy")
    s.set_state(prefsBusy=False)
    s.pointer("label:has(#headed)", "change-after-lock-release")
    s.wait("window.__QA_STATE.savedPrefs && window.__QA_STATE.savedPrefs.headed === false")
    s.wait("Object.keys(S.savePending).length === 0 && !S.saveBusy")
    s.check("恢复时较新值优先", s.js("S.prefs.headed === false"))
    s.shot("save-recovered")


def _today_in_os_timezone(s: Session):
    s.emit_clock(clockEpochS=1792947600, clockAgeS=0)  # 北京2026-10-26 01:00
    s.js("""() => {
      const items=[{id:'today',name:'北京时间今天',sign_start:'2026-10-26 22:00:00',
        act_start:'2026-10-28 10:00:00',act_end:'2026-10-28 11:00:00'},
        {id:'tomorrow',name:'北京时间明天',sign_start:'2026-10-27 01:00:00',
        act_start:'2026-10-29 10:00:00',act_end:'2026-10-29 11:00:00'}];
      bumpRoundGeneration('list'); S.round.list='qa-timezone';
      window.__QA_EMIT('activities',{request_id:'qa-timezone',ok:true,items});
    }""")
    s.page.locator("#time").select_option("today")
    s.wait("document.querySelectorAll('#rows .row').length === 1")
    s.check("今天按北京日期过滤", s.page.locator("#rows .row").first.get_attribute("data-id") == "today")
    s.check_clock_text("非北京OS时区仍显示北京时间")
    s.shot("today-filter")


scenario("today-filter-utc", "UTC系统时区下的北京今天", (1120, 800), timezone="UTC")(_today_in_os_timezone)
scenario("today-filter-los-angeles", "洛杉矶系统时区下的北京今天", (1120, 800), timezone="America/Los_Angeles")(_today_in_os_timezone)


@scenario("manual-clock-failure-same-generation", "校准失败及时收尾并保留可用旧时间", (1120, 800))
def _(s: Session):
    s.wait_business_ready()
    s.pointer("#clock", "open-clock-before-retry")
    old_gen = s.js("S.businessClock.gen")
    old_round = s.js("S.businessClock.syncRound")
    s.set_state(clockSyncFails=True)
    s.pointer("#clock-pop-sync", "retry-with-valid-anchor")
    s.wait("S.businessClock.syncState === 'idle' && S.businessClock.syncError.includes('未成功')", 4000)
    s.check("失败不伪造授时代次", s.js("S.businessClock.gen") == old_gen)
    s.check("失败仍有本次尝试编号", s.js("S.businessClock.syncRound") == old_round + 1)
    s.check_contains("#clock-pop-feedback", "仍使用上次校准结果")
    s.check("仍可读取有效旧时间", s.js("businessNowMs() !== null"))
    s.check("不占用报名结论", s.js("document.querySelector('#result').hidden"))
    s.page.wait_for_timeout(250)   # 覆盖结果早于 sync_clock ack：迟到ack不重启等待
    s.check("迟到回执不复活校准等待", s.js("S.businessClock.syncState === 'idle'"))
    s.shot("same-generation-failure")
    s.set_state(clockSyncFails=False)
    s.pointer("#clock-pop-sync", "retry-after-failure")
    s.wait("S.businessClock.gen > %d && S.businessClock.syncState === 'idle'" % old_gen)
    s.check("新成功清除旧错误", s.js("S.businessClock.syncError === ''"))
    s.check_clock_text("恢复成功后北京时间准确")
    s.shot("retry-success")


# ------------------------------------------------------------ 新工作台五视口
# 计划 test-ui-contract：五视口（含 746×512、680×480）都无横向滚动，刷新、设置、帮助、
# 开始 / 停止可见可点。分档与 CSS 同一套阈值：宽 ≥1040、中 720–1039、窄 <720、矮 高 <660。
WORKBENCH_VIEWPORTS = [(1280, 800), (1120, 800), (980, 720), (746, 512), (680, 480)]


def _no_hscroll(s: Session, tag: str) -> None:
    data = s.js("() => ({ sw: document.documentElement.scrollWidth,"
                " cw: document.documentElement.clientWidth })")
    s.check("%s：无横向滚动" % tag, data["sw"] <= data["cw"] + 1, data)


def _reachable(s: Session, selector: str, tag: str) -> dict:
    """可见、整块落在视口里、没被禁用，而且中心点 elementFromPoint 命中它自己或子节点。

    只看 is_visible() 不够：被计划条、抽屉或滚动容器盖住的按钮同样「可见」。"""
    data = s.js("""(sel) => {
      const el = document.querySelector(sel);
      if (!el) return { ok: false, why: 'missing' };
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      const shown = r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
      const inside = r.left >= -1 && r.top >= -1
        && r.right <= window.innerWidth + 1 && r.bottom <= window.innerHeight + 1;
      return { ok: shown && inside && !!hit && (hit === el || el.contains(hit)),
               disabled: !!el.disabled, hit: hit ? (hit.id || hit.tagName) : '',
               box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] };
    }""", selector)
    s.check("%s：%s 可见可点" % (tag, selector), bool(data.get("ok")) and not data.get("disabled"), data)
    return data


def _open_plan_panel(s: Session, tag: str) -> None:
    """中、窄档计划栏和时刻表二选一：经计划条「查看计划」打开（宽档本来就在）。"""
    if s.js("S.band") == "wide":
        return
    _reachable(s, "#btn-dock-open", tag + " 计划条")
    s.pointer("#btn-dock-open", "open-plan:" + tag)
    s.wait("S.planOpen === true", 4000)


def _register_workbench_viewport(width: int, height: int) -> None:
    tag = "%d×%d" % (width, height)

    @scenario("workbench-%dx%d" % (width, height),
              "新工作台 %s：无横向滚动，刷新/设置/帮助/开始/停止可见可点" % tag,
              (width, height), "valid")
    def _(s: Session):
        s.settle()
        s.wait_business_ready()
        s.wait("document.querySelectorAll('#rows .row').length >= 5")
        band = s.js("({ band: S.band, short: S.short })")
        expect = "wide" if width >= 1040 else ("medium" if width >= 720 else "narrow")
        s.check("%s：分档 %s" % (tag, expect), band.get("band") == expect
                and bool(band.get("short")) == (height < 660), band)
        _no_hscroll(s, tag + " 草稿")
        for selector in ("#btn-refresh", "#btn-settings", "#btn-help"):
            _reachable(s, selector, tag + " 顶栏")
        s.shot("draft")
        s.pick("a-future")
        _open_plan_panel(s, tag)
        s.wait("!document.querySelector('#btn-plan').disabled", 8000)
        _no_hscroll(s, tag + " 计划栏")
        _reachable(s, "#btn-plan", tag + " 开始")
        s.shot("plan")
        rec = s.pointer("#btn-plan", "start:" + tag)
        s.check("%s：开始按钮真实命中" % tag, s.hit_in(rec, "#btn-plan"), rec.get("hit"))
        s.wait("S.busy === true && S.plan.id === 'qa-plan'", 8000)
        if s.js("S.band") != "wide" and not s.js("S.planOpen"):
            _open_plan_panel(s, tag + " 运行中")
        _no_hscroll(s, tag + " 运行中")
        _reachable(s, "#btn-stop", tag + " 停止")
        for selector in ("#btn-refresh", "#btn-settings", "#btn-help"):
            _reachable(s, selector, tag + " 运行中顶栏")
        s.shot("running")
        s.pointer("#btn-settings", "settings:" + tag)
        s.wait("document.querySelector('#settings').hidden === false", 4000)
        _no_hscroll(s, tag + " 设置抽屉")
        _reachable(s, "#btn-settings-close", tag + " 设置抽屉")
        s.shot("settings")
        s.page.keyboard.press("Escape")
        s.wait("document.querySelector('#settings').hidden === true", 4000)


for _w, _h in WORKBENCH_VIEWPORTS:
    _register_workbench_viewport(_w, _h)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="本机 UI 离线验收")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--ui-root", default=None,
                        help="复现/对照用的 UI 目录（默认读生产 local/ui）")
    parser.add_argument("--port", type=int, default=8382)
    parser.add_argument("--evidence-root", default="")
    parser.add_argument("--run", action="store_true", help="真正启动浏览器执行")
    parser.add_argument("--scenario", default="", help="只跑一个场景")
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "localhost"):
        print("[X] 只允许绑定回环地址，收到 %r" % args.host)
        return 2
    if not (UI / "index.html").exists() or not BRIDGE.exists():
        print("[X] 缺少 UI 文件或测试桥：%s" % BRIDGE)
        return 2
    evidence = Path(args.evidence_root or (ROOT / "dist" / "qa-evidence"))
    evidence.mkdir(parents=True, exist_ok=True)

    try:
        server = QaServer(args.host, args.port, ui_root=args.ui_root)
    except OSError as exc:
        print("[X] 端口 %d 无法绑定（可能被占用）：%s" % (args.port, exc))
        return 2
    server.start()
    print("[i] QA 服务：%s（证据目录 %s）" % (server.base, evidence))
    try:
        if not args.run:
            print("[i] 未传 --run：只校验服务与资源，不启动浏览器。")
            return 0
        try:
            report = run_scenarios(server.base, evidence, args.scenario or None)
        except ImportError as exc:
            print("[blocked] 没有 Playwright：%s" % exc)
            return 3
        report_path = evidence / "qa-report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        print("[i] 报告：%s" % report_path.resolve())
        if report.get("blocked"):
            print("[blocked] %s" % report["blocked"])
            return 3
        passed = [item for item in report["scenarios"] if item.get("ok")]
        print("[i] 场景 %d/%d 通过，截图 %d 张"
              % (len(passed), len(report["scenarios"]),
                 sum(len(item["screenshots"]) for item in report["scenarios"])))
        if report["failures"]:
            for line in report["failures"]:
                print("[X] %s" % line)
            return 1
        print("[OK] 全部场景通过")
        return 0
    finally:
        server.stop()


if __name__ == "__main__":
    sys.exit(main())
