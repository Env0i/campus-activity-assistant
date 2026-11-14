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

    def test_real_module_load_attaches_every_reported_name(self):
        """真加载后，模块图报告里挂回的每个名字在 window 上都得是函数，缺一个点名。"""
        report = _run_ui_modules()
        result = run_native_smoke(report["legacy_globals_attached"])
        self.assertTrue(result["modulesReady"], "真加载后 main.js 必须置 __modulesReady")
        missing = [entry["name"] for entry in result["names"] if not entry["isFunction"]]
        self.assertEqual([], missing,
                         "真加载下 window 没挂回这些名字（拼接沙箱里模块名恰好是全局的，"
                         "这类缺陷拼接测试发现不了，真窗口里普通脚本一调用就是 "
                         "ReferenceError）：%r" % (missing,))


if __name__ == "__main__":
    unittest.main()
