#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模块图守卫：tools/code_shape/ui_modules.mjs 的报告与期望值逐项比对。

期望值 tools/code_shape/ui_modules_expect.json 由 ui_modules.mjs --expect 生成，不手写；
五类问题（顶层循环、缺 import、普通脚本引用了没挂回的模块名字、违反层规则、挂出去没人用）
必须为空，「模块用到的普通脚本全局名字」与「挂回 window 的名字」两份清单逐项相等，
多一项少一项都红。没有 node 时跳过并说明。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, run_boot_guard, run_native_smoke  # noqa: E402

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
        """真加载下识别行下载失败（原因是连不上发布页），调挂回的绘制后红条要看得见、
        文字是「下载没有完成：连不上发布页，可以重试。」。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"], after=r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: {
  download: { state: "failed", error_code: "network_error" } } } };
window.paintOcrDownload();
const bar = $("#ocr-download-error");
out.push({ barShown: !bar.hidden, text: bar.textContent });
""")
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        self.assertTrue(result["after"][0]["barShown"], "下载失败后识别行红条要看得见")
        self.assertEqual(result["after"][0]["text"], "下载没有完成：连不上发布页，可以重试。",
                         "红条文字要按失败原因拼出可重试那句")


if __name__ == "__main__":
    unittest.main()
