#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_ui_layers.py（来源：test_ui_layers.py, test_ui_modules.py, test_webview_mime.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_ui_layers.py ====================
"""前端分层的契约：state/ 不引用 views/、controllers/ 与 app.js 的名字；views/ 不引用后两者的名字。

量法与审计参照表一致（按名字匹配、排除属性访问 / 对象字面量的键 / 注释与字符串 / 本文件同名局部声明），
由 tools/code_shape/ui_refs.mjs 清点；存量例外记在 tools/code_shape/ui_layer_allow.json，只减不增。
白名单按「文件 × 名字」计，不约束同一名字在同一文件里的引用次数。
没有 node 时两条清点用例跳过并说明，其余用例照常跑。
"""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL  # noqa: E402

ROOT = LOCAL.parent
UI_REFS = ROOT / "tools/code_shape/ui_refs.mjs"
ALLOW = ROOT / "tools/code_shape/ui_layer_allow.json"

# 批 3 已把 8 个纯判断函数搬回 state 层：它们不许以「上层名字」的身份回到白名单里。
MOVED_TO_STATE = ("verifiedSigned", "hmsDay", "submittingDetail", "effectiveRetryDeadline",
                  "selectionSignature", "numOrNull", "termsLocked", "clockPopOpenNow")


def _load_allow():
    return json.loads(ALLOW.read_text(encoding="utf-8"))


def _run_refs():
    """跑一次 ui_refs.mjs，返回 {层: {(文件, 名字)}}。"""
    out = subprocess.run(
        ["node", str(UI_REFS)], cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8", check=True)
    data = json.loads(out.stdout)
    result = {}
    for group in ("state", "views"):
        result[group] = {(r["file"], r["name"]) for r in data[group]}
    return result


@unittest.skipUnless(shutil.which("node"), "本机没有 node，前端跨层清点跳过")
class UiLayerRefsTests(unittest.TestCase):
    def _compare(self, group):
        allow = {(file, name) for file, names in _load_allow()[group].items() for name in names}
        actual = _run_refs()[group]
        extra = sorted(actual - allow)
        missing = sorted(allow - actual)
        self.assertEqual([], extra,
                         "%s/ 出现新的跨层引用（文件, 名字），要么把定义搬到正确的层，"
                         "要么加进 ui_layer_allow.json：%r" % (group, extra))
        self.assertEqual([], missing,
                         "ui_layer_allow.json 里的这些 %s/ 项在代码里已经没有了，"
                         "请删掉：%r" % (group, missing))

    def test_state_does_not_reference_upper_layers(self):
        self._compare("state")

    def test_views_do_not_reference_controllers_or_app(self):
        self._compare("views")


class UiLayerAllowListTests(unittest.TestCase):
    """不依赖 node：白名单本身的结构与内容。"""

    def test_moved_names_do_not_come_back_as_upper_layer_definitions(self):
        state_names = {name for names in _load_allow()["state"].values() for name in names}
        back = sorted(set(MOVED_TO_STATE) & state_names)
        self.assertEqual([], back,
                         "这些名字已经在 state 层定义，不该再作为上层名字出现在白名单：%r" % (back,))

    def test_allow_list_stays_empty(self):
        self.assertEqual(_load_allow(), {"state": {}, "views": {}})


# ==================== 源自 test_ui_modules.py ====================
"""模块图守卫：tools/code_shape/ui_modules.mjs 的报告与期望值逐项比对。

期望值 tools/code_shape/ui_modules_expect.json 由 ui_modules.mjs --expect 生成，不手写；
五类问题（顶层循环、缺 import、普通脚本引用了没挂回的模块名字、违反层规则、挂出去没人用）
必须为空，「模块用到的普通脚本全局名字」与「挂回 window 的名字」两份清单逐项相等，
多一项少一项都红。没有 node 时跳过并说明。"""


TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_boot_guard, run_native_smoke  # noqa: E402

ROOT = LOCAL.parent
UI_MODULES = ROOT / "tools" / "code_shape" / "ui_modules.mjs"
EXPECT = ROOT / "tools" / "code_shape" / "ui_modules_expect.json"

PROBLEM_KEYS = ("cycles", "missing_imports", "unattached_module_names",
                "layer_violations", "unused_legacy_globals")
LIST_KEYS = ("plain_globals_used", "legacy_globals_attached")


def _run_ui_modules() -> dict:
    out = subprocess.run(["node", str(UI_MODULES)], cwd=str(ROOT),
                         capture_output=True, text=True, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def _expect() -> dict:
    return json.loads(EXPECT.read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("node"), "本机没有 node，模块图守卫跳过")
class UiModulesReportTests(unittest.TestCase):
    """五类问题段必须为空；两份清单必须与期望值逐项相等。"""

    def test_problem_sections_are_empty(self):
        report = _run_ui_modules()
        for key in PROBLEM_KEYS:
            self.assertEqual(report[key], [],
                             "ui_modules.mjs 的 %s 不为空：%r" % (key, report[key]))

    def test_lists_match_expectation(self):
        report = _run_ui_modules()
        expect = _expect()
        for key in LIST_KEYS:
            self.assertEqual(report[key], expect[key],
                             "ui_modules.mjs 的 %s 与期望值不一致：实际 %r，期望 %r"
                             % (key, report[key], expect[key]))

    def test_expect_file_covers_exactly_the_guarded_keys(self):
        expect = _expect()
        self.assertEqual(sorted(expect), sorted(PROBLEM_KEYS + LIST_KEYS),
                         "ui_modules_expect.json 的键必须是五类问题加两份清单：%r" % (sorted(expect),))


@unittest.skipUnless(shutil.which("node"), "本机没有 node，模块过渡行为测试跳过")
class BootGuardBehaviorTests(unittest.TestCase):
    """后端早到的事件排队重放一条不丢；兜底提示只在模块没就绪时出现。"""

    def test_early_events_replay_in_order_and_nothing_is_lost(self):
        """早到的三条事件按原顺序重放且一条不丢；就绪之后直接透传，不再排队。"""
        res = run_boot_guard(r"""
/* 模块没就绪：三条早到事件全进队列，一条都没到处理器 */
window.onBackend.log("一");
window.onBackend.check({ id: 1 });
window.onBackend.done({ ok: true });
out.push({ before: __calls.length });
/* main.js 的两个动作：置就绪、放排队 */
window.__modulesReady = true;
window.__replayBackendQueue();
out.push({ kinds: __calls.map((c) => c[0]), args: __calls.map((c) => c[1]) });
/* 之后直接透传 */
window.onBackend.log("就绪后直达");
out.push({ total: __calls.length, last: __calls[__calls.length - 1][0] });
""")
        self.assertEqual(res[0]["before"], 0, "模块没就绪时事件不得直接到处理器")
        self.assertEqual(res[1]["kinds"], ["log", "check", "done"], "重放必须按原顺序")
        self.assertEqual(res[1]["args"][0], "一", "重放的参数要原样")
        self.assertEqual(res[1]["args"][1], {"id": 1}, "重放的参数要原样")
        self.assertEqual(res[1]["args"][2], {"ok": True}, "重放的参数要原样")
        self.assertEqual(res[2]["total"], 4, "重放之后透传，不再排队")
        self.assertEqual(res[2]["last"], "log", "透传的那条就是最后一条")

    def test_fallback_banner_shows_only_while_modules_not_ready(self):
        """没就绪时 10 秒提示出现在页面最顶上（内联样式）；就绪后到点不再出现。"""
        res = run_boot_guard(r"""
out.push({ ms: __timers[0].ms });
__timers[0].fn();
const banner = document.body._children[0];
out.push({ text: banner.textContent,
  inlineStyle: typeof banner.attrs.style === "string" && banner.attrs.style.length > 0,
  atTop: document.body.firstChild === banner });
window.__modulesReady = true;
__timers[0].fn();
out.push({ children: document.body._children.length });
""")
        self.assertEqual(res[0]["ms"], 10000, "兜底提示的等待是 10 秒")
        self.assertEqual(res[1]["text"], "界面没有加载完整。请关闭工具后重新打开；还是这样就重新安装。",
                         "提示文字与产品里逐字一致（用户看真窗口时可改）")
        self.assertTrue(res[1]["inlineStyle"], "提示只用内联样式，不依赖样式表")
        self.assertTrue(res[1]["atTop"], "提示插在页面最顶上")
        self.assertEqual(res[2]["children"], 1, "就绪后到点不再出现第二条")

    def test_replay_survives_a_failing_handler(self):
        """放出排队事件时某条的处理函数抛错：报出、跳过、后面的继续送，一条不丢。"""
        res = run_boot_guard(r"""
/* 第二条（check）的处理函数在放出时抛错 */
__explode = "check";
window.onBackend.log("一");
window.onBackend.check({ id: 2 });
window.onBackend.done({ ok: true });
out.push({ queued: __calls.length });
window.__modulesReady = true;
window.__replayBackendQueue();
out.push({ kinds: __calls.map((c) => c[0]), errors: __consoleErrors });
/* 再放一次：已放出的不重送 */
window.__replayBackendQueue();
out.push({ total: __calls.length });
""")
        self.assertEqual(res[0]["queued"], 0, "未就绪时三条都排队，没有直接到处理器")
        self.assertEqual(res[1]["kinds"], ["log", "done"],
                         "第二条抛错后第三条仍然送到，送到的顺序是第一条和第三条")
        self.assertEqual(len(res[1]["errors"]), 1, "抛错要用 console.error 报出一次")
        self.assertIn("check", res[1]["errors"][0], "报错要说清是哪条处理函数出的错")
        self.assertEqual(res[2]["total"], 2, "再调一次放出函数不会重复送")


@unittest.skipUnless(shutil.which("node"), "本机没有 node，原生加载冒烟跳过")
class NativeLoadSmokeTests(unittest.TestCase):
    """拼起来能跑 ≠ 真加载能跑——main.js 用真实的动态 import 加载，不走夹具拼接，
    也不从仓库目录直接加载（仓库在网络共享盘上时 node 沿上层找 package.json 会出错）。"""

    # 手机面板搬成模块之前 PhonePanel 的全部成员名（顶层字段加方法，从面板搬走前
    # 的原文件里取出写成字面量）；搬完装配回同一个对象，成员一个不多、一个不少。
    PANEL_MEMBERS = [
        "state", "busy", "pending", "pollTimer", "pollTicks", "tickTimer", "lastCode",
        "channel", "notes", "stopAsk", "addPair", "addPairAt", "copied", "copyTimer",
        "location", "lastDownload", "codeLeft", "codeSync", "picked", "verified",
        "clearConfirm", "credForm", "credNote", "credNoteTone", "importKey", "installing",
        "refresh", "loadLocation", "downloadActive", "needsPolling", "startPolling",
        "stopPolling", "startTick", "stopTick", "feature", "selectedChannel", "paint",
        "paintRelogin", "paintCredForm", "paintPhoneAccess", "paintCountdown",
        "openComponents", "paintComponents", "pickComponent", "inspectComponent",
        "showComponentNote", "installComponent", "closeComponents", "featureAction",
        "enableFeature", "toggleStart", "toggleStop", "askStop", "cancelStop",
        "confirmStop", "addPairing", "goSaveCredentials", "openComponentDir",
        "copyByTextarea", "copyAddress", "downloadComponent", "cancelComponent",
        "changeChannel", "recheckTailscale", "saveCredentials", "openCredForm",
        "cancelCredForm", "askClearCredentials", "cancelClearCredentials",
        "confirmClearCredentials", "clearCredentials", "wire",
    ]

    def test_real_load_filter_toggle_saves_each_choice_once(self):
        """真实模块按钮控制筛选面板，每次点击只保存一次。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: { save_prefs: (patch) => {
  window.__calls.push(patch); return Promise.resolve({ ok: true });
} } };
const snapshot = () => ({ hidden: $("#more-filters").hidden,
  expanded: $("#btn-more").getAttribute("aria-expanded") });
$("#btn-more").click();
await flushPrefs();
const opened = snapshot();
$("#btn-more").click();
await flushPrefs();
out.push({ opened, closed: snapshot(), saves: window.__calls });
""")
        self.assertTrue(result["modulesReady"])
        self.assertEqual(result["after"][0]["opened"], {"hidden": False, "expanded": "true"})
        self.assertEqual(result["after"][0]["closed"], {"hidden": True, "expanded": "false"})
        self.assertEqual(result["after"][0]["saves"], [{"filter_open": True}, {"filter_open": False}])

    def test_real_load_clock_sync_delegates_after_redraw(self):
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: { sync_clock: () => {
  window.__calls.push("sync_clock"); return new Promise(() => {});
} } };
const pop = $("#clock-pop");
const dispatch = (target) => pop.listeners.click.forEach((fn) => fn({ target }));
const other = { closest: () => null };
const disabled = { disabled: true };
dispatch(other);
dispatch({ closest: () => disabled });
S.clockPopOpen = true;
renderClockPop();
renderClockPop();
const button = { disabled: false };
dispatch({ closest: (selector) => selector === "#clock-pop-sync" ? button : null });
out.push({ calls: window.__calls, listeners: pop.listeners.click.length });
""")
        self.assertTrue(result["modulesReady"])
        self.assertEqual(result["after"][0], {"calls": ["sync_clock"], "listeners": 1})

    def test_real_load_log_toggle_saves_each_choice_once(self):
        """模块真加载后展开、收起，显示状态和每次保存请求一致。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: { save_prefs: (patch) => {
  window.__calls.push(patch); return Promise.resolve({ ok: true });
} } };
const snapshot = () => ({ open: document.querySelector(".log-card").dataset.open,
  label: $("#btn-log-toggle").textContent,
  expanded: $("#btn-log-toggle").getAttribute("aria-expanded") });
$("#btn-log-toggle").click();
await flushPrefs();
const opened = snapshot();
$("#btn-log-toggle").click();
await flushPrefs();
out.push({ opened, closed: snapshot(), saves: window.__calls });
""")
        self.assertTrue(result["modulesReady"])
        self.assertEqual(result["after"][0]["opened"],
                         {"open": "true", "label": "收起", "expanded": "true"})
        self.assertEqual(result["after"][0]["closed"],
                         {"open": "false", "label": "展开", "expanded": "false"})
        self.assertEqual(result["after"][0]["saves"], [{"log_open": True}, {"log_open": False}])

    def test_real_load_restores_log_pref_without_saving(self):
        """应用已有偏好只同步面板，不能再发一次保存请求。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: { save_prefs: (patch) => {
  window.__calls.push(patch); return Promise.resolve({ ok: true });
} } };
applyPrefs({ log_open: true });
await flushPrefs();
out.push({ open: document.querySelector(".log-card").dataset.open,
           label: $("#btn-log-toggle").textContent,
           expanded: $("#btn-log-toggle").getAttribute("aria-expanded"),
           saves: window.__calls });
""")
        self.assertTrue(result["modulesReady"])
        self.assertEqual(result["after"][0],
                         {"open": "true", "label": "收起", "expanded": "true", "saves": []})

    def test_real_module_load_attaches_every_reported_name(self):
        """真加载后，模块图报告里挂回的每个名字在 window 上都得有定义（函数或对象
        都算，PhonePanel 是对象），缺一个点名。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"])
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        missing = [entry["name"] for entry in result["names"] if not entry["isDefined"]]
        self.assertEqual([], missing,
                         "真加载下 window 没挂回这些名字（拼接沙箱里模块名恰好是全局的，"
                         "这类缺陷拼接测试发现不了，真窗口里普通脚本一调用就是 "
                         "ReferenceError）：%r" % (missing,))

    def test_real_load_phone_panel_has_exactly_the_same_members(self):
        """真加载装配后的 PhonePanel：成员名排序后与搬之前逐个相等，一个不多一个不少。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
out.push({ members: Object.keys(window.PhonePanel).sort() });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertEqual(sorted(result["after"][0]["members"]), sorted(self.PANEL_MEMBERS),
                         "真加载装配后的 PhonePanel 成员与搬之前不一致")

    def test_real_load_ocr_download_and_cancel_send_their_requests(self):
        """真加载下点识别行的「下载并安装」与「取消下载」：各发出一次对应请求。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
$("#btn-ocr-download").click();
await __flush();
$("#btn-ocr-cancel").click();
await __flush();
out.push({ download: window.__calls.filter((c) => c[0] === "download_advanced_feature"),
           cancel: window.__calls.filter((c) => c[0] === "cancel_advanced_feature_download") });
""")
        self.assertEqual(result["after"][0]["download"],
                         [["download_advanced_feature", "relogin_ocr"]],
                         "真加载下点识别行「下载并安装」要发出验证码识别的下载请求")
        self.assertEqual(result["after"][0]["cancel"],
                         [["cancel_advanced_feature_download", "relogin_ocr"]],
                         "真加载下点识别行「取消下载」要发出验证码识别的取消请求")

    def test_real_load_help_opens_and_saves_seen(self):
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
$("#help-status").hidden = false;
$("#help-status").textContent = "旧反馈";
$("#btn-help").click();
await flushPrefs();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
out.push({ open: $("#help").open, hidden: $("#help-status").hidden,
  text: $("#help-status").textContent, calls: window.__calls });
""")
        state = result["after"][0]
        self.assertTrue(result["modulesReady"])
        self.assertTrue(state["open"])
        self.assertTrue(state["hidden"])
        self.assertEqual(state["text"], "")
        self.assertEqual([c for c in state["calls"] if c[0] == "save_prefs"],
                         [["save_prefs", {"welcome_seen": True}]])
        self.assertFalse([c for c in state["calls"] if c[0] in
                          ("open_latest_release", "open_data", "open_advanced_component_dir")])

    def test_real_load_start_sends_the_start_request(self):
        """真加载下点手机行的「开启手机访问」：发出开启请求。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
$("#btn-phone-start").click();
out.push({ start: window.__calls.filter((c) => c[0] === "start_phone_access") });
""")
        self.assertEqual(result["after"][0]["start"], [["start_phone_access", "tailscale"]],
                         "真加载下点手机行「开启手机访问」要发出开启请求")

    def test_real_load_tour_exit_saves_once_and_restores_focus(self):
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.__calls = [];
window.pywebview = { api: { save_prefs: (patch) => {
  window.__calls.push(patch); return Promise.resolve({ ok: true });
} } };
$("#btn-settings").focus();
startTour(0);
$("#tour-skip").click();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
const skipped = { calls: window.__calls.slice(), focus: document.activeElement === $("#btn-settings"),
  closed: !S.tour.open && $("#tour").hidden };
window.__calls = [];
$("#btn-settings").focus();
startTour(TOUR_STEPS.length - 1);
$("#tour-next").click();
for (let i = 0; i < 12; i += 1) await Promise.resolve();
out.push({ skipped, completed: { calls: window.__calls.slice(),
  focus: document.activeElement === $("#btn-settings"), closed: !S.tour.open && $("#tour").hidden },
  version: TOUR_VERSION });
""")
        state = result["after"][0]
        self.assertTrue(result["modulesReady"])
        for key, stamp in (("skipped", "tour_skipped_at"), ("completed", "tour_completed_at")):
            exit_state = state[key]
            self.assertTrue(exit_state["closed"])
            self.assertTrue(exit_state["focus"])
            self.assertEqual(len(exit_state["calls"]), 1)
            self.assertEqual(exit_state["calls"][0]["tour_version"], state["version"])
            self.assertTrue(exit_state["calls"][0][stamp])

    def test_real_load_settings_drawer_asks_the_ocr_component_location(self):
        """真加载下点设置按钮打开抽屉：发出一次验证码识别的组件位置请求。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
$("#btn-settings").click();
await __flush();
out.push({ loc: window.__calls.filter(
  (c) => c[0] === "advanced_component_location" && c[1] === "relogin_ocr") });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertEqual(result["after"][0]["loc"],
                         [["advanced_component_location", "relogin_ocr"]],
                         "真加载下打开设置抽屉要发出一次验证码识别的组件位置请求")

    def test_real_load_at_medium_and_narrow_widths_keeps_the_tail_bindings(self):
        """按窗口宽度真加载两次（900 中档、430 窄档）。

        app.js 顶层那句 applyBand() 会在普通脚本阶段就按宽度选分支一路往下跑，走到
        paintDock -> startBlocker -> termsLocked() 时模块名还没挂回 window（挂回在
        main.js 里），整页报 ReferenceError，其后那 40 余处绑定一处都装不上。所以
        这里既要不崩，也要证明末尾那条「打开数据目录」的绑定确实点得动。
        """
        report = _run_ui_modules()
        for width, height in ((900, 700), (430, 820)):
            with self.subTest(width=width):
                result = run_native_smoke(report["legacy_globals_attached"],
                                          size=(width, height),
                                          before='document.querySelector("#btn-plan").disabled = true;',
                                          after=r'''
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
$("#btn-log-folder").click();
await __flush();
out.push({ opened: window.__calls.filter((c) => c[0] === "open_data") });
''')
                self.assertTrue(result["modulesReady"],
                                "%d 宽真加载后 main.js 必须置 __modulesReady" % width)
                self.assertEqual(result["after"][0]["opened"], [["open_data"]],
                                 "%d 宽真加载下点「打开数据目录」要发出一次 open_data"
                                 "（app.js 末尾那批绑定没装上就点不动）" % width)

    def test_real_load_ocr_enable_says_enabled_in_the_row(self):
        """真加载下点识别行的「启用」：发出启用请求，识别行说明里出现启用成功那句。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
const __flush = async (n = 12) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
$("#btn-ocr-enable").click();
await __flush();
out.push({ note: $("#ocr-note").textContent,
           noteShown: !$("#ocr-note").hidden,
           enable: window.__calls.filter((c) => c[0] === "enable_advanced_feature") });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertTrue(result["after"][0]["noteShown"], "启用成功后识别行说明要看得见")
        self.assertEqual(result["after"][0]["note"], "验证码识别已启用。",
                         "真加载下点「启用」后说明里要有启用成功那句（经面板字段与下载区绘制）")
        self.assertEqual(result["after"][0]["enable"],
                         [["enable_advanced_feature", "relogin_ocr"]],
                         "真加载下点「启用」要发出启用请求")

    def test_real_load_ocr_open_dir_sends_the_open_dir_request(self):
        """真加载下点识别行「打开所在文件夹」：发出打开目录请求。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
window.__calls = [];
$("#btn-ocr-open-loc").click();
out.push({ openDir: window.__calls.filter((c) => c[0] === "open_advanced_component_dir") });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertEqual(result["after"][0]["openDir"],
                         [["open_advanced_component_dir", "relogin_ocr"]],
                         "真加载下点「打开所在文件夹」要发出打开目录请求")

    def test_real_load_ocr_failed_download_paints_the_retry_bar(self):
        """真加载下识别行下载失败（原因是连不上发布页），打开设置后红条要看得见、
        文字是「下载没有完成：连不上发布页，可以重试。」。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: {
  download: { state: "failed", error_code: "network_error" } } } };
$("#btn-settings").click();
const bar = $("#ocr-download-error");
out.push({ barShown: !bar.hidden, text: bar.textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertTrue(result["after"][0]["barShown"], "下载失败后识别行红条要看得见")
        self.assertEqual(result["after"][0]["text"], "下载没有完成：连不上发布页，可以重试。",
                         "红条文字要按失败原因拼出可重试那句")

# ==================== 源自 test_webview_mime.py ====================
"""脚本类型头登记的守卫：pywebview 本地服务的脚本类型头来自标准库 mimetypes，而
mimetypes 在 Windows 上会读注册表——有的电脑把 .js 记成 text/plain（装过某些软件之后
会出现）。普通脚本不在乎类型头，模块脚本严格要求 JavaScript 类型，类型不对时整张
模块图都不加载，界面停在兜底提示上，重装也没用；宿主机的注册表是正常的，验不出这个
问题，只能靠这里的模拟加断言守住。三条用例都用 add_type 把 .js 模拟成 text/plain，
断言登记函数（与 infrastructure 包导入时的登记）把它压回 text/javascript；
每条用例收尾在 addCleanup 里把 mimetypes 重新初始化，模拟不外溢。"""

import importlib
import mimetypes

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))


SIMULATED = ("text/plain", None)
REGISTERED = ("text/javascript", None)


def _restore_mimetypes():
    """把 mimetypes 的映射恢复到本进程初始状态，模拟不带到别的测试。"""
    mimetypes.init()


class WebViewMimeTests(unittest.TestCase):
    """模拟注册表把 .js 记成 text/plain 之后，登记给出的仍是 text/javascript。"""

    def setUp(self):
        self.addCleanup(_restore_mimetypes)

    def test_register_script_types_overrides_simulated_registry(self):
        """模拟注册表生效后，register_script_types() 把 .js 压回 text/javascript。"""
        from local.infrastructure.webview_mime import register_script_types
        mimetypes.add_type("text/plain", ".js")
        self.assertEqual(mimetypes.guess_type("main.js"), SIMULATED,
                         "模拟没有生效（guess_type 仍是原值），这条测试没有牙")
        register_script_types()
        self.assertEqual(mimetypes.guess_type("main.js"), REGISTERED,
                         "登记之后 .js 必须是 text/javascript")

    def test_package_import_registers_script_types(self):
        """infrastructure 包导入时的那次登记同样压得过模拟的注册表。"""
        mimetypes.add_type("text/plain", ".js")
        import local.infrastructure as infra
        importlib.reload(infra)          # 重新执行包初始化，导入处的登记再跑一遍
        self.assertEqual(mimetypes.guess_type("main.js"), REGISTERED,
                         "infrastructure 包导入时必须登记 .js 的脚本类型")

    def test_bottle_static_file_serves_javascript_type(self):
        """pywebview 自带服务用 bottle.static_file 供脚本：模拟注册表后类型头仍以
        text/javascript 开头。没装 bottle 时跳过并说明，其余两条照常跑。"""
        try:
            import bottle
        except ImportError:
            self.skipTest("本机没装 bottle：静态文件类型头这条跳过，其余两条照常跑")
        mimetypes.add_type("text/plain", ".js")
        from local.infrastructure.webview_mime import register_script_types
        register_script_types()
        response = bottle.static_file("main.js", root=str(LOCAL / "ui"))
        content_type = response.headers.get("Content-Type") or response.content_type
        self.assertTrue(content_type.startswith("text/javascript"),
                        "bottle.static_file 给 main.js 的类型头必须以 text/javascript 开头，"
                        "实际是 %r" % (content_type,))

if __name__ == "__main__":
    unittest.main()
