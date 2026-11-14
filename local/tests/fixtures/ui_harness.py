# -*- coding: utf-8 -*-
"""界面契约测试的公共夹具：读源文件、剥注释、JS 沙箱与原型注入片段。"""
from __future__ import annotations

import datetime as dt
import posixpath
import re
import unittest
from pathlib import Path


LOCAL = Path(__file__).resolve().parents[2]


# 学校时间按 UTC+8 解释：夹具写学校时间也要按北京时间生成，
# 否则执行机的时区设置不是 +08:00 时整批偏移（C5）
BEIJING_TZ = dt.timezone(dt.timedelta(hours=8))


# ---------------------------------------------------------------- 页面脚本清单（过渡期公共口径）
# 过渡期普通脚本先跑、模块后跑（ESM 地基批）：普通脚本按 index.html 的加载序在前，
# 模块入口的整张引用图随后、被引用的在前。契约拼接与 node 沙箱都按这份清单取源码：
# 普通脚本原样，模块去掉 import 语句与 export 关键字后拼在后面。
# mjs 侧同口径的实现是 tools/code_shape/ui_refs.mjs 的 pageFiles()（ui_modules.mjs 复用），
# 两边各有测试守着（test_ui_modules 与现有契约测试）。

LED_JS = "led.js"            # 独立字库渲染器：真实页面会加载，不含业务契约文本，不进清单与沙箱

_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>")
_SCRIPT_SRC_RE = re.compile(r"\bsrc=\"([^\"]+)\"")
_SCRIPT_MODULE_RE = re.compile(r"type\s*=\s*[\"']module[\"']")
_NAMED_IMPORT_RE = re.compile(r"^import\s*\{([^}]*)\}\s*from\s*\"(?P<src>[^\"]+)\"\s*;\s*$")
_IMPORT_KEYWORD_RE = re.compile(r"import\b")
_EXPORT_KEYWORD_RE = re.compile(r"export\b")
_EXPORT_DECL_RE = re.compile(r"^(\s*)export\s+(?=(?:function|const|let|var|class)\b)", re.MULTILINE)
_EXPORT_LIST_RE = re.compile(r"^\s*export\s*\{[^}]*\}\s*;\s*$")


def _read_ui(rel: str) -> str:
    path = LOCAL / "ui" / rel
    assert path.exists(), "界面脚本缺失：%s" % path
    return path.read_text(encoding="utf-8")


def _js_code_lines(src: str) -> list[str]:
    """剥掉 // 行注释与 /* */ 块注释后的逐行源码（保留行数），只用于认 import/export 行。

    不回写源码：字符串被行注释截断只影响这一行的判读，行首关键字的判断不受影响。"""
    out = []
    in_block = False
    for line in src.splitlines():
        kept = []
        i, n = 0, len(line)
        while i < n:
            if in_block:
                end = line.find("*/", i)
                if end < 0:
                    i = n
                else:
                    in_block = False
                    i = end + 2
            elif line.startswith("//", i):
                break
            elif line.startswith("/*", i):
                in_block = True
                i += 2
            else:
                kept.append(line[i])
                i += 1
        out.append("".join(kept))
    return out


def _module_deps(rel: str) -> list[str]:
    """模块的具名导入清单（模块只允许具名导入这一种写法，别的写法直接报错，不静默跳过）。"""
    deps = []
    for lineno, line in enumerate(_js_code_lines(_read_ui(rel)), start=1):
        code = line.strip()
        if not _IMPORT_KEYWORD_RE.match(code):
            continue
        m = _NAMED_IMPORT_RE.match(code)
        if not m:
            raise AssertionError(
                "%s:%d 的 import 不是「import { 名字 } from \"./相对路径\";」的单行具名导入，"
                "夹具只支持模块的具名导入写法：%s" % (rel, lineno, code))
        spec = m.group("src")
        if not (spec.startswith("./") or spec.startswith("../")):
            raise AssertionError(
                "%s:%d 的 import 路径必须是 ./ 或 ../ 开头的相对路径：%s" % (rel, lineno, spec))
        dep = posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec))
        if dep.startswith(".."):
            raise AssertionError("%s:%d 的 import 越出了 ui 目录：%s" % (rel, lineno, spec))
        deps.append(dep)
    return deps


def _module_graph(entry: str | None) -> list[str]:
    """模块入口的引用图，被引用的在前（后序）；顶层循环引用直接报错——
    那会让整张模块图起不来（esm-verify H3），报告由 tools/code_shape/ui_modules.mjs 出。"""
    order: list[str] = []
    visiting: set[str] = set()

    def visit(rel: str, path: list[str]) -> None:
        if rel in order:
            return
        if rel in visiting:
            raise AssertionError("模块顶层循环引用，整张图起不来：%s -> %s" % (" -> ".join(path), rel))
        visiting.add(rel)
        for dep in _module_deps(rel):
            visit(dep, path + [rel])
        visiting.remove(rel)
        order.append(rel)

    if entry:
        visit(entry, [])
    return order


def _script_srcs(html: str) -> list[tuple[str, bool]]:
    """index.html 里带 src 的 <script> 标签按出现顺序给 (src, 是否模块入口)。

    旧正则只认 <script src="…"></script> 一种写法，这里放宽到同时认 type="module" 的入口。"""
    out = []
    for tag in _SCRIPT_TAG_RE.findall(html):
        src = _SCRIPT_SRC_RE.search(tag)
        if src:
            out.append((src.group(1), _SCRIPT_MODULE_RE.search(tag) is not None))
    return out


def page_scripts() -> list[dict]:
    """页面脚本清单（公共口径的夹具函数）：普通脚本按 index.html 的加载序在前，之后是模块
    入口的整张引用图（被引用的在前）；led.js 不进清单。read_ui_scripts 与 node 沙箱
    （run_js）都按这份清单取源码。"""
    html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
    plain, entries = [], []
    for src, is_module in _script_srcs(html):
        if is_module:
            entries.append(src)
        elif src != LED_JS:
            plain.append(src)
    if len(entries) > 1:
        raise AssertionError("index.html 有多个模块入口，夹具只支持一个：%r" % entries)
    return ([{"rel": rel, "module": False} for rel in plain]
            + [{"rel": rel, "module": True} for rel in _module_graph(entries[0] if entries else None)])


def _module_sandbox_src(rel: str) -> str:
    """模块源码 → 沙箱可执行的等价源码：去掉 import 行与 export 关键字。

    只支持具名导入与 export 声明 / export { 列表 }；默认导出等别的写法报错，不静默吞掉。
    import 语句的形状已由 _module_deps 在建图时校验过，这里只做剥壳。"""
    src = _read_ui(rel)
    for lineno, line in enumerate(_js_code_lines(src), start=1):
        code = line.strip()
        if _EXPORT_KEYWORD_RE.match(code) and not _EXPORT_DECL_RE.match(code) \
                and not _EXPORT_LIST_RE.match(code):
            raise AssertionError(
                "%s:%d 的 export 写法夹具不支持（只许 export 声明与 export { 列表 }；默认导出不用）：%s"
                % (rel, lineno, code))
    src = re.sub(r"(?m)^\s*import\s*\{[^}]*\}\s*from\s*\"[^\"]+\"\s*;\s*$", "", src)
    src = _EXPORT_DECL_RE.sub(r"\1", src)
    src = re.sub(r"(?m)^\s*export\s*\{[^}]*\}\s*;\s*$", "", src)
    return src


def read(rel: str) -> str:
    path = LOCAL / rel
    self_msg = "契约文件缺失：%s" % path
    assert path.exists(), self_msg
    if rel == "ui/app.js":
        # 结构重构后界面脚本按层拆成多文件：契约断言读「前端脚本联合源码」，
        # 加载序取自 index.html（led.js 是独立字库渲染器，不含业务契约文本）。
        return read_ui_scripts()
    return path.read_text(encoding="utf-8")


def module_group_sandbox_src(entry: str) -> str:
    """模块入口的整张引用图（被引用的在前），剥掉 import 与 export 后的拼接源码。

    与 read_ui_scripts 的模块段同一口径，只取这一个入口的那组模块。"""
    return "\n".join(_module_sandbox_src(rel) for rel in _module_graph(entry))


def module_group_raw_src(entry: str) -> str:
    """模块入口的整张引用图的原文拼接（不剥壳），给读源码的字面断言用。"""
    return "\n".join(_read_ui(rel) for rel in _module_graph(entry))


def read_ui_scripts() -> str:
    """index.html 加载序的全部业务脚本拼接（led.js 除外）。

    过渡期：普通脚本原样在前，模块去掉 import 与 export 后拼在后面，
    顺序即 page_scripts() 的清单；模块里的名字经 legacy-globals.js 挂回 window。"""
    return "\n".join(
        _module_sandbox_src(item["rel"]) if item["module"] else _read_ui(item["rel"])
        for item in page_scripts())


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
/* 结构重构后界面按层拆成多脚本：沙箱自带「页面脚本清单」的同口径一份——
 * 普通脚本按 index.html 的加载序在前，模块入口的整张引用图随后、被引用的在前；
 * 模块去掉 import 语句与 export 关键字后执行。与 Python 夹具的 page_scripts() /
 * read_ui_scripts() 同一口径，两边各有测试守着。led.js 不进清单——字库渲染器
 * 只在真实 DOM 有意义，且历史行为就是 LED_UI 缺席时 ledSet 回退纯文本层。 */
const html = fs.readFileSync(path.join(uiDir, "index.html"), "utf8");
const _SRC_TAG_RE = /\bsrc="([^"]+)"/;
const _MODULE_TAG_RE = /type\s*=\s*["']module["']/;
const plainList = [];
const moduleEntries = [];
for (const m of html.matchAll(/<script\b([^>]*)>/g)) {
  const src = _SRC_TAG_RE.exec(m[1]);
  if (!src) continue;
  if (_MODULE_TAG_RE.test(m[1])) moduleEntries.push(src[1]);
  else if (src[1] !== "led.js") plainList.push(src[1]);
}
if (moduleEntries.length > 1) throw new Error("index.html 有多个模块入口：" + moduleEntries.join(", "));
/* 模块只允许这些写法：单行具名导入、export 声明与 export { 列表 }；别的直接报错 */
const IMPORT_RE = /^import\s*\{([^}]*)\}\s*from\s*"([^"]+)"\s*;\s*$/;
const IMPORT_KEYWORD_RE = /^import\b/;
const EXPORT_DECL_RE = /^(\s*)export\s+(?=(?:function|const|let|var|class)\b)/;
/* 剥壳用多行版（g 会给 test() 带上 lastIndex 状态，所以校验与替换分成两个正则） */
const EXPORT_DECL_STRIP_RE = /^(\s*)export\s+(?=(?:function|const|let|var|class)\b)/mg;
const EXPORT_LIST_RE = /^\s*export\s*\{[^}]*\}\s*;\s*$/;
const EXPORT_KEYWORD_RE = /^export\b/;
const codeLines = (src) => {
  const lines = [];
  let inBlock = false;
  for (const line of src.split("\n")) {
    let kept = "";
    for (let i = 0; i < line.length; ) {
      if (inBlock) {
        const e = line.indexOf("*/", i);
        if (e < 0) { i = line.length; } else { inBlock = false; i = e + 2; }
      } else if (line.startsWith("//", i)) break;
      else if (line.startsWith("/*", i)) { inBlock = true; i += 2; }
      else { kept += line[i]; i += 1; }
    }
    lines.push(kept);
  }
  return lines;
};
const moduleImportsOf = (rel) => {
  const out = [];
  for (const line of codeLines(fs.readFileSync(path.join(uiDir, rel), "utf8"))) {
    const t = line.trim();
    if (!IMPORT_KEYWORD_RE.test(t)) continue;
    const m = IMPORT_RE.exec(t);
    if (!m) throw new Error(rel + " 的 import 不是「import { 名字 } from ./相对路径」的单行具名导入：" + t);
    if (!/^\.{1,2}\//.test(m[2])) throw new Error(rel + " 的 import 路径必须是 ./ 或 ../ 开头的相对路径：" + m[2]);
    out.push(path.posix.normalize(path.posix.join(path.posix.dirname(rel), m[2])));
  }
  return out;
};
const moduleGraph = (entry) => {
  const order = [];
  const visiting = new Set();
  const visit = (rel, chain) => {
    if (order.includes(rel)) return;
    if (visiting.has(rel)) throw new Error("模块顶层循环引用：" + chain.concat(rel).join(" -> "));
    visiting.add(rel);
    for (const dep of moduleImportsOf(rel)) visit(dep, chain.concat(rel));
    visiting.delete(rel);
    order.push(rel);
  };
  if (entry) visit(entry, []);
  return order;
};
const moduleSandboxSrc = (rel) => {
  const src = fs.readFileSync(path.join(uiDir, rel), "utf8");
  for (const line of codeLines(src)) {
    const t = line.trim();
    if (EXPORT_KEYWORD_RE.test(t) && !EXPORT_DECL_RE.test(t) && !EXPORT_LIST_RE.test(t)) {
      throw new Error(rel + " 的 export 写法沙箱不支持（只许 export 声明与 export { 列表 }）：" + t);
    }
  }
  return src
    .replace(/^\s*import\s*\{[^}]*\}\s*from\s*"[^"]+"\s*;\s*$/gm, "")
    .replace(EXPORT_DECL_STRIP_RE, "$1")
    .replace(/^\s*export\s*\{[^}]*\}\s*;\s*$/gm, "");
};
const scripts = plainList.map((rel) => ({ rel, code: fs.readFileSync(path.join(uiDir, rel), "utf8") }));
for (const rel of moduleGraph(moduleEntries[0] || null)) {
  scripts.push({ rel, code: moduleSandboxSrc(rel) });
}
for (const item of scripts) {
  vm.runInContext(item.code, sandbox, { filename: item.rel });
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

    沙箱按自己那份「页面脚本清单」同口径加载，本函数只给 ui 目录与片段。
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


# ---------------------------------------------------------------- 过渡期模块的行为装置
# boot-guard 的最小沙箱：只装它需要的东西——onBackend 的三个处理器、可手动触发的
# 定时器、能记账的 document。真实页面里 app.js 先定义 onBackend，boot-guard 再包一层，
# 这里照同序摆好；模块没就绪时（__modulesReady 不为真）包装层把事件存进队列。
BOOT_GUARD_HARNESS = r"""
"use strict";
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const uiDir = process.argv[2];
const snippetFile = process.argv[3];
const out = [];
const calls = [];
const timers = [];
const errors = [];
const sandbox = {
  /* 处理函数出错时 boot-guard 会经 console.error 报出：沙箱的 console 换成记账桩，
   * 用例能断言「报了错、说了是哪条」。__explode 指到哪个名字，那个处理函数记账后就抛。 */
  console: { error: (...a) => errors.push(a.map((x) => String(x)).join(" ")) },
  out, __calls: calls, __timers: timers, __consoleErrors: errors, __explode: null,
  setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; },
  clearTimeout: () => {},
  document: {
    createElement: (tag) => ({ tagName: tag, attrs: {}, textContent: "",
      setAttribute(k, v) { this.attrs[k] = v; } }),
    body: { _children: [], firstChild: null,
      insertBefore(child) { this._children.unshift(child); this.firstChild = child; return child; } },
  },
};
sandbox.window = sandbox;
const maybeThrow = (name) => {
  if (sandbox.__explode === name) throw new Error("处理器抛错：" + name);
};
sandbox.window.onBackend = {
  log: (line) => { maybeThrow("log"); calls.push(["log", line]); },
  check: (payload) => { maybeThrow("check"); calls.push(["check", payload]); },
  done: (payload) => { maybeThrow("done"); calls.push(["done", payload]); },
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(uiDir, "boot-guard.js"), "utf8"),
                sandbox, { filename: "boot-guard.js" });
const result = vm.runInContext(
  "(async () => {\n" + fs.readFileSync(snippetFile, "utf8") + "\n})()",
  sandbox, { filename: "snippet.js" });
result.then(() => process.stdout.write("__RESULT__" + JSON.stringify(out)),
            (err) => { process.stderr.write(String(err)); process.exit(1); });
"""


def run_boot_guard(snippet: str):
    """在最小沙箱里跑 boot-guard 行为片段，返回 out 数组（list）。node 缺失时 skip。"""
    import json
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，boot-guard 行为测试跳过")
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "bootguard-harness.js"
        part = Path(name) / "snippet.js"
        harness.write_text(BOOT_GUARD_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        res = subprocess.run([node, str(harness), str(LOCAL / "ui"), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30)
        if res.returncode != 0:
            raise AssertionError("boot-guard 行为测试崩溃：%s" % res.stderr[-800:])
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise AssertionError("boot-guard 行为测试没有输出结果：%s" % res.stdout[-500:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


# 原生加载冒烟沙箱：复用 JS_HARNESS 的同一套 DOM 桩（从「const out = [];」切到
# vm.createContext 之前），但不进 vm 上下文——桩挂到真实全局，普通脚本按夹具清单
# runInThisContext（与浏览器的多脚本共享全局词法环境同语义），main.js 用真实的
# 动态 import 加载，不走拼接。它守的是「拼起来能跑、真加载却缺挂回」这一类缺陷：
# 拼接以后模块里的名字恰好是全局的，只有真加载才暴露普通脚本拿不到模块名字的问题。
# 加载目录是 tempfile 下的临时副本（_copy_ui_tree 复制 .js 并放一个声明 type 为
# module 的 package.json），不从仓库目录直接加载：仓库在网络共享盘上时 node 沿
# 上层目录找 package.json 会出错，仓库里也不许建 package.json。
_SMOKE_STUBS = JS_HARNESS[JS_HARNESS.index("const out = [];"):JS_HARNESS.index("vm.createContext(sandbox);")]

SMOKE_HARNESS = (
    '"use strict";\n'
    'const vm = require("vm");\n'
    'const fs = require("fs");\n'
    'const path = require("path");\n'
    'const { pathToFileURL } = require("url");\n'
    'const uiDir = process.argv[2];\n'
    'const listFile = process.argv[3];\n'
    'const namesFile = process.argv[4];\n'
    'const afterFile = process.argv[5] || "";\n'
    + _SMOKE_STUBS
    + 'for (const [k, v] of Object.entries(sandbox)) {\n'
    '  try { Object.defineProperty(globalThis, k, { value: v, writable: true, configurable: true }); }\n'
    '  catch (err) { /* navigator 这类只读内建保持原样，桩的差异不影响冒烟断言 */ }\n'
    '}\n'
    'globalThis.window = globalThis;\n'
    'const attached = JSON.parse(fs.readFileSync(namesFile, "utf8"));\n'
    'const list = JSON.parse(fs.readFileSync(listFile, "utf8"));\n'
    'for (const rel of list) {\n'
    '  vm.runInThisContext(fs.readFileSync(path.join(uiDir, rel), "utf8"), { filename: rel });\n'
    '}\n'
    'import(pathToFileURL(path.join(uiDir, "main.js")).href).then(async () => {\n'
    '  if (afterFile) {\n'
    '    await vm.runInThisContext("(async () => {\\n" + fs.readFileSync(afterFile, "utf8") + "\\n})()",\n'
    '      { filename: "after-snippet.js" });\n'
    '  }\n'
    '  process.stdout.write("__RESULT__" + JSON.stringify([{\n'
    '    modulesReady: window.__modulesReady === true,\n'
    '    names: attached.map((name) => ({ name: name, isDefined: typeof window[name] !== "undefined" })),\n'
    '    after: out,\n'
    '  }]));\n'
    '}, (err) => { process.stderr.write(String(err)); process.exit(1); });\n'
)


def _copy_ui_tree(dest: Path) -> None:
    """把 local/ui 下的 .js 按原目录结构复制进临时目录（不含手机页 m/），并放一个
    只声明 type 为 module 的 package.json：模块加载不依赖 node 的语法探测（旧一些的
    node 没有这个能力），也不受仓库上层目录影响。package.json 只在临时目录里，
    仓库里不建。"""
    import shutil
    for src in (LOCAL / "ui").rglob("*.js"):
        rel = src.relative_to(LOCAL / "ui")
        if rel.parts[0] == "m":
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    (dest / "package.json").write_text('{"type": "module"}', encoding="utf-8")


def run_native_smoke(names: list, after: str | None = None) -> dict:
    """真实的动态 import 加载 main.js，返回挂回名字的逐个核对结果。node 缺失时 skip。

    names 是模块图报告里挂回 window 的名字清单：真加载完成后逐个断言 window 上
    对应的名字有定义（函数或对象都算）。普通脚本与 main.js 都从临时副本目录读，
    模块的 import 由 node 的真实加载器按副本里的 package.json（type: module）解析。
    after 是可选片段：真加载完成之后在同一个全局环境里执行并把 out 带回来，供
    「真加载下再点控件」一类的断言用；不给时行为与原来一致。"""
    import json
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，原生加载冒烟跳过")
    plain = [item["rel"] for item in page_scripts() if not item["module"]]
    with tempfile.TemporaryDirectory() as name:
        dest = Path(name) / "ui"
        _copy_ui_tree(dest)
        harness = Path(name) / "smoke-harness.js"
        part = Path(name) / "list.json"
        namesfile = Path(name) / "names.json"
        afterfile = Path(name) / "after.js"
        harness.write_text(SMOKE_HARNESS, encoding="utf-8")
        part.write_text(json.dumps(plain), encoding="utf-8")
        namesfile.write_text(json.dumps(list(names)), encoding="utf-8")
        cmd = [node, str(harness), str(dest), str(part), str(namesfile)]
        if after:
            afterfile.write_text(after, encoding="utf-8")
            cmd.append(str(afterfile))
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        if res.returncode != 0:
            raise AssertionError("原生加载冒烟崩溃：%s" % res.stderr[-800:])
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise AssertionError("原生加载冒烟没有输出结果：%s" % res.stdout[-500:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")[0]


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
