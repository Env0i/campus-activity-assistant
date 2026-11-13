# -*- coding: utf-8 -*-
"""界面契约测试的公共夹具：读源文件、剥注释、JS 沙箱与原型注入片段。"""
from __future__ import annotations

import datetime as dt
import re
import unittest
from pathlib import Path


LOCAL = Path(__file__).resolve().parents[2]


# 学校时间按 UTC+8 解释：夹具写学校时间也要按北京时间生成，
# 否则执行机的时区设置不是 +08:00 时整批偏移（C5）
BEIJING_TZ = dt.timezone(dt.timedelta(hours=8))


def read(rel: str) -> str:
    path = LOCAL / rel
    self_msg = "契约文件缺失：%s" % path
    assert path.exists(), self_msg
    if rel == "ui/app.js":
        # 结构重构后界面脚本按层拆成多文件：契约断言读「前端脚本联合源码」，
        # 加载序取自 index.html（led.js 是独立字库渲染器，不含业务契约文本）。
        return read_ui_scripts()
    return path.read_text(encoding="utf-8")


def read_ui_scripts() -> str:
    """index.html 加载序的全部业务脚本拼接（led.js 除外）。"""
    html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
    parts = []
    for src in re.findall(r'<script src="([^"]+)"></script>', html):
        if src == "led.js":
            continue
        parts.append((LOCAL / "ui" / src).read_text(encoding="utf-8"))
    return "\n".join(parts)


def strip_ui_comments(text: str, suffix: str) -> str:
    """逐行剥注释、保留行号，供禁词扫描只看真实文案。

    原扫描按整行原文匹配，把注释里「为什么不照搬某个原型演示控件」「重登 sheet
    指哪张 sheet」之类的设计说明也当成了残留（20261108-phone-1to1 的手机页注释
    按计划规范必须写明这类取舍）；禁词查的是界面文案，注释不是文案。
    .js 剥行尾 // 与跨行块注释；.html 另剥跨行 <!-- -->；.css 只剥块注释。
    字符串里的 //（如链接）会被一并剥掉，但禁词都是中文词，不会藏在链接后面。"""
    out = []
    in_block = ""          # "" | "js" | "html"
    for line in text.splitlines():
        kept = []
        i, n = 0, len(line)
        while i < n:
            if in_block == "js":
                end = line.find("*/", i)
                if end < 0:
                    i = n
                else:
                    in_block = ""
                    i = end + 2
            elif in_block == "html":
                end = line.find("-->", i)
                if end < 0:
                    i = n
                else:
                    in_block = ""
                    i = end + 3
            elif suffix == ".js" and line.startswith("//", i):
                break
            elif suffix in (".js", ".css") and line.startswith("/*", i):
                in_block = "js"
                i += 2
            elif suffix == ".html" and line.startswith("<!--", i):
                in_block = "html"
                i += 4
            else:
                kept.append(line[i])
                i += 1
        out.append("".join(kept))
    return "\n".join(out)


def help_dialog(html: str) -> str:
    """截取更多 dialog 元素本体（不含其前注释），供禁词等逐字断言使用。"""
    start = html.index('<dialog class="dlg dlg-help"')
    end = html.index("</dialog>", start) + len("</dialog>")
    return html[start:end]


# 帮助载荷隔离求值用的注入常量：证明 help() 用的是外部版本来源，不是写死值
HELP_TEST_VERSION = "9.9.9-test"


HELP_TEST_URL = "https://example.invalid/releases/latest"


def load_backend_help() -> dict:
    """只取 app.py 里 Api.help 这一个方法，在隔离命名空间里求值后调用。

    不 import app.py：它的顶层会 import webview 并经 runtime_paths 触碰数据根，
    与本计划「不安装依赖、不读真实登录文件」的边界冲突。这里用 ast 抽出
    FunctionDef，单独编译并注入 APP_VERSION / RELEASES_LATEST_URL，
    因此拿到的是**真实方法的返回值**，不是源码子串的推测。
    """
    import ast

    tree = ast.parse(read("app.py"))
    node = next(item for item in ast.walk(tree)
                if isinstance(item, ast.FunctionDef) and item.name == "help"
                and [arg.arg for arg in item.args.args][:1] == ["self"])
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"APP_VERSION": HELP_TEST_VERSION, "RELEASES_LATEST_URL": HELP_TEST_URL}
    exec(compile(module, "<Api.help>", "exec"), namespace)  # noqa: S102 - 只编译受控片段
    return namespace["help"](None)


# --------------------------------------------------------------------- 行为测试装置
# 在 node vm 里加载生产 app.js + 最小 DOM 桩，执行代码片段并取回断言输出。
# 不开浏览器、不装依赖：node 是项目既有工具链（服务器机器人同用）。
# 桩的边界：querySelector 按选择器缓存同一元素；focus 记录到 focused；
# document 只捕获 keydown 监听（__dispatchKey 合成按键）；定时器只记录不调度。

JS_HARNESS = r"""
"use strict";
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const uiDir = process.argv[2];
const snippetFile = process.argv[3];

const out = [];
const focused = [];
const els = new Map();
const keydownListeners = [];

function makeEl(sel) {
  const el = {
    __sel: sel, hidden: false, disabled: false, checked: false,
    value: "", textContent: "", title: "", returnValue: "",
    tagName: "DIV", open: false,
    dataset: {}, style: {}, _cls: new Set(),
    listeners: {},
  };
  /* innerHTML 与 textContent 按 DOM 语义联动：生产空态副行用带 nowrap span
   * 的 innerHTML 写文案（f541ba4 起就有），桩原来两者独立，读 textContent
   * 只能拿到空串。只联动赋值方向，读 innerHTML 仍返回原串。 */
  let _html = "";
  Object.defineProperty(el, "innerHTML", {
    get() { return _html; },
    set(v) { _html = String(v); el.textContent = _html.replace(/<[^>]*>/g, ""); },
  });
  el.classList = {
    toggle(c, on) {
      if (on === undefined) { if (el._cls.has(c)) el._cls.delete(c); else el._cls.add(c); }
      else if (on) el._cls.add(c); else el._cls.delete(c);
    },
    add(c) { el._cls.add(c); },
    remove(c) { el._cls.delete(c); },
    contains(c) { return el._cls.has(c); },
  };
  el.addEventListener = (type, fn) => { (el.listeners[type] = el.listeners[type] || []).push(fn); };
  el.removeEventListener = () => {};
  el.setAttribute = (k, v) => { el["attr_" + k] = v; };
  el.getAttribute = (k) => el["attr_" + k];
  el.focus = () => { sandbox.document.activeElement = el; focused.push(sel); };
  el.blur = () => { if (sandbox.document.activeElement === el) sandbox.document.activeElement = null; };
  el.select = () => {};
  el.click = () => (el.listeners.click || []).forEach((fn) => fn({ target: el, preventDefault() {} }));
  el.closest = () => null;
  el.contains = () => true;
  /* <dialog> 原生方法桩：设置/说明/停止确认的 open 状态靠它们翻转 */
  el.showModal = () => { el.open = true; };
  el.close = () => { el.open = false; };
  /* 子节点按真实语义记账：addLog 的「副作用有没有重复」需要数得出来 */
  el._children = [];
  el.appendChild = (child) => {
    el._children.push(child);
    el.childElementCount = el._children.length;
    return child;
  };
  el.removeChild = (child) => {
    const at = el._children.indexOf(child);
    if (at >= 0) el._children.splice(at, 1);
    el.childElementCount = el._children.length;
    return child;
  };
  el.insertBefore = (child) => { el._children.unshift(child); el.childElementCount = el._children.length; return child; };
  el.childElementCount = 0;
  el.childNodes = [];
  Object.defineProperty(el, "firstChild", {
    get() { return el._children[0] || null; },
  });
  el.getBoundingClientRect = () => ({ top: 100, left: 100, bottom: 140, right: 460, width: 360, height: 40 });
  el.getClientRects = () => [1];
  el.offsetWidth = 360;
  el.offsetHeight = 40;
  el.querySelector = (s) => el2(sel + " " + s);
  el.querySelectorAll = (s) => [el2(sel + " " + s)];
  return el;
}

function el2(sel) {
  if (!els.has(sel)) els.set(sel, makeEl(sel));
  return els.get(sel);
}

/* 单调钟独立于 Date：初值与 Date.now 同源（既有用例仍可用 Date.now 伪造
 * 「很久以前」的缓存时间），用例可再用 __advanceMono 单独推进经过时长，
 * 不会用 Date 假跳变同时推进 performance 导致红例失真。 */
const monoState = { base: Date.now(), offset: 0 };
const sandbox = {
  console, Date, Math, JSON, Promise, Object, Array, Number, String, Boolean, RegExp, Error,
  isNaN, parseInt, parseFloat,
  performance: { now: () => monoState.base + monoState.offset },
  __advanceMono: (ms) => { monoState.offset += Number(ms) || 0; },
  __monoValue: () => monoState.base + monoState.offset,
  innerWidth: 1120, innerHeight: 800,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  navigator: { onLine: true },
  /* window.addEventListener/removeEventListener：app.js 顶层注册 resize/online/offline 用 */
  addEventListener: () => {}, removeEventListener: () => {},
  out, focused, __els: els,
  requestAnimationFrame: () => 0,
  __dispatchKey: (ev) => {
    const e = Object.assign(
      { ctrlKey: false, shiftKey: false, altKey: false, defaultPrevented: false,
        target: { closest: () => null, tagName: "BODY", blur() {} } }, ev);
    e.preventDefault = () => { e.defaultPrevented = true; };
    keydownListeners.slice().forEach((fn) => fn(e));
    return e;
  },
  document: {
    hidden: false, activeElement: null,
    querySelector: (s) => el2(s),
    querySelectorAll: (s) => [el2(s)],
    createElement: (tag) => el2("<" + tag + ">"),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
    addEventListener: (t, fn) => { if (t === "keydown") keydownListeners.push(fn); },
    removeEventListener: () => {},
  },
};
sandbox.window = sandbox;
sandbox.document.body = el2("body");
/* 停止确认弹层在 index.html 里默认 hidden；桩元素默认 hidden:false，不显式对齐的话
 * stopAskOpen() 在每个用例里都为真，键盘处理会被它截走 */
el2("#plan-stop-ask").hidden = true;
vm.createContext(sandbox);
/* 结构重构后界面按层拆成多脚本：按 index.html 的加载序喂进同一个沙箱，
 * 与真实 WebView 顺序一致。led.js 不进沙箱——字库渲染器只在真实 DOM 有
 * 意义，且历史行为就是 LED_UI 缺席时 ledSet 回退纯文本层。 */
const html = fs.readFileSync(path.join(uiDir, "index.html"), "utf8");
const scripts = Array.from(html.matchAll(/<script src="([^"]+)"><\/script>/g))
  .map((m) => m[1]).filter((src) => src !== "led.js");
for (const src of scripts) {
  vm.runInContext(fs.readFileSync(path.join(uiDir, src), "utf8"), sandbox, { filename: src });
}
/* 决策 012：node 桩显式注入可信假时钟（锚定 Date.now），不以 Date.now 作默认成功桩 */
vm.runInContext(
  "ingestBusinessClock({ schema: 1, owner_id: 'harness-clock', generation: 1," +
  " state: 'ready', epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0," +
  " uncertainty_s: 0, source: 'harness', age_s: 0, reason: '测试注入' });" +
  /* 用例把「业务现在」定到任意时刻：注入新一代快照，不再改 Date.now（墙钟不是权威） */
  "globalThis.setBusinessNow = (ms) => ingestBusinessClock({" +
  " schema: 1, owner_id: 'harness-clock'," +
  " generation: (S.businessClock.gen || 0) + 1, state: 'ready'," +
  " epoch_s: ms / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0," +
  " source: 'harness', age_s: 0, reason: '测试注入' });",
  sandbox, { filename: "clock-inject.js" });
/* 片段统一包成 async IIFE：顶层 await 可用（受控 Promise 次序），同步片段
 * 返回的 promise 立即完成，输出时序不变 */
const snippetSource = fs.readFileSync(snippetFile, "utf8");
const snippetResult = vm.runInContext(
  "(async () => {\n" + snippetSource + "\n})()",
  sandbox, { filename: "snippet.js" });
const finishHarness = () => process.stdout.write("__RESULT__" + JSON.stringify(out));
snippetResult.then(finishHarness, (err) => { process.stderr.write(String(err)); process.exit(1); });
"""


def run_js(snippet: str, env: dict | None = None):
    """在受控 JS 上下文里执行片段，返回 out 数组（list）。node 缺失时 skip。

    env 用于按用例注入 TZ（例如证明学校时间解析不随本机时区漂移）；
    默认不改进程环境。
    """
    import json
    import os
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，无法运行 JS 行为测试")
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "harness.js"
        part = Path(name) / "snippet.js"
        harness.write_text(JS_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        child_env = dict(os.environ)
        child_env.update(env or {})
        res = subprocess.run([node, str(harness), str(LOCAL / "ui"), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30, env=child_env)
        if res.returncode != 0:
            raise AssertionError("JS 行为测试崩溃：%s" % res.stderr[-800:])
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise AssertionError("JS 行为测试没有输出结果：%s" % res.stdout[-500:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


def settings_drawer(html):
    """设置抽屉（aside#settings）的完整片段。"""
    start = html.index('<aside class="draw" id="settings"')
    return html[start:html.index("</aside>", start)]


PP_LOGIN_OK_JS = r"""
S.listState = "ready";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
paintLogin();
"""


def _pp_stats(html):
    """结果页大数字 → {标签: 数}（只含显示出来的格子）。"""
    return {label: int(n) for n, label in
            re.findall(r"<strong>(\d+)</strong><span>([^<]+)</span>", html)}


# 新工作台（决策 014 / 设计 2026-11-02）专属断言：计划 test-ui-contract 要求的新增覆盖。
# 学校时刻文本按 SCHOOL_OFFSET_S 现算，片段里不写死日期，免得夹具随日历过期。
WB_STAMP_JS = r"""
const stamp = (sec) => {
  const d = new Date((sec + SCHOOL_OFFSET_S) * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return d.getUTCFullYear() + "-" + p(d.getUTCMonth() + 1) + "-" + p(d.getUTCDate()) + " "
    + p(d.getUTCHours()) + ":" + p(d.getUTCMinutes()) + ":" + p(d.getUTCSeconds());
};
const t0 = 1700000000000;
setBusinessNow(t0);
const now = t0 / 1000;
const seed = (list) => { S.items = list.map(normalize); S.byId = new Map(S.items.map((i) => [String(i.id), i])); };
"""
