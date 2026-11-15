#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件行的状态转移：读状态这一层（等锁、超时、读不到）与坏了、取消、下载中各自长什么样。

一条转移一个用例，走 fixtures.ui_harness 的整页沙箱（run_js）：给后端快照、按需要点一下
「重试」或主按钮，只看用户看得到的结果（按钮在不在、能不能点、说明写的是哪句、有没有
再取一次快照），不对源码文本做断言。两行都适用的转移，两行都断言。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 公共桩：两行快照、可替换的下一次快照、记账的下载与取消请求、微任务推进
PRELUDE = r"""
window.__calls = [];
window.__snapshot = { ok: true, running: false };
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve(window.__snapshot),
  advanced_component_location: () => Promise.resolve({ ok: false }),
  download_advanced_feature: (name) => {
    window.__calls.push(["download_advanced_feature", name]); return Promise.resolve({ ok: true });
  },
  cancel_advanced_feature_download: (name) => {
    window.__calls.push(["cancel_advanced_feature_download", name]); return Promise.resolve({ ok: true });
  },
} };
const __flush = async (n = 12) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
const __rows = (phoneRow, ocrRow) => {
  PhonePanel.state.advanced = { features: { phone_control: phoneRow, relogin_ocr: ocrRow },
                                channels: { tailscale: { available: true } },
                                credential: { saved: false, staged: false } };
};
const __snap = (phoneRow, ocrRow) => {
  window.__snapshot = { ok: true, running: false, advanced: {
    features: { phone_control: phoneRow, relogin_ocr: ocrRow },
    channels: { tailscale: { available: true } }, credential: { saved: false, staged: false } } };
};
const __ui = () => ({
  phone: { install: [$("#btn-phone-component-install").hidden,
                     $("#btn-phone-component-install").textContent,
                     $("#btn-phone-component-install").disabled],
           cancel: [$("#btn-phone-component-cancel").hidden,
                    $("#btn-phone-component-cancel").disabled],
           missing: $("#phone-missing").hidden, loading: $("#phone-loading").hidden,
           probe: [$("#phone-probe").hidden, $("#phone-probe").textContent,
                   $("#phone-probe").dataset.probe],
           retry: [$("#btn-phone-component-retry").hidden, $("#btn-phone-component-retry").disabled],
           feature: $("#btn-phone-feature-install").hidden,
           chip: $("#phone-feature-status").hidden ? "" : $("#phone-feature-status").textContent,
           err: [$("#phone-component-error").hidden, $("#phone-component-error").textContent],
           imp: $("#phone-import-line").hidden },
  ocr: { install: [$("#btn-ocr-download").hidden, $("#btn-ocr-download").textContent,
                   $("#btn-ocr-download").disabled],
         cancel: [$("#btn-ocr-cancel").hidden, $("#btn-ocr-cancel").disabled],
         missing: $("#ocr-missing").hidden, loading: $("#ocr-loading").hidden,
         probe: [$("#ocr-probe").hidden, $("#ocr-probe").textContent, $("#ocr-probe").dataset.probe],
         retry: [$("#btn-ocr-retry").hidden, $("#btn-ocr-retry").disabled],
         enable: $("#btn-ocr-enable").hidden,
         chip: $("#ocr-feature-status").hidden ? "" : $("#ocr-feature-status").textContent,
         err: [$("#ocr-download-error").hidden, $("#ocr-download-error").textContent],
         imp: $("#ocr-import-line").hidden },
});
"""

WAITING = "正在确认组件状态…"
TIMEOUT = "另一个窗口正在安装或更新组件，已等 30 秒"
UNREADABLE = "暂时读不到组件状态"
BROKEN = "组件文件不完整。重新安装不会动你的账号和设置。"


class ReadingStateHiddenTests(unittest.TestCase):
    """等锁没结论时：不装蒜也不假装在下载，原字保留，只多一句说明。"""

    def test_cached_row_under_lock_keeps_its_words_and_hides_actions(self):
        """有缓存又等锁：原来的字与 chip 一个字不变，主按钮、启用、进度块全收起，自动再取快照。"""
        res = run_js(PRELUDE + r"""
const plain = { ready: true };
__rows(plain, plain);
PhonePanel.paint();
const before = __ui();
__rows({ ready: true, busy: true, lock_wait_s: 5 },
       { ready: true, busy: true, lock_wait_s: 5 });
PhonePanel.paint();
out.push({ before: before, after: __ui(), polling: PhonePanel.needsPolling() });
""")
        data = res[0]
        after = data["after"]
        for side in ("phone", "ocr"):
            self.assertEqual(after[side]["chip"], data["before"][side]["chip"],
                             side + "：等锁时原来的字要保留")
            self.assertTrue(after[side]["probe"][0], side + "：有结论就不用再说一句")
            self.assertTrue(after[side]["retry"][0], side + "：没到 30 秒不给「重试」")
            self.assertTrue(after[side]["install"][0], side + "：还没结论不给主按钮")
            self.assertTrue(after[side]["missing"], side + "：不能显示成没装")
            self.assertTrue(after[side]["loading"], side + "：不是在下载，进度块收起")
        self.assertTrue(after["phone"]["feature"], "有缓存时标题行不给「启用」")
        self.assertTrue(after["ocr"]["enable"], "有缓存时识别行不给「启用」")
        self.assertTrue(data["polling"], "等锁时要自动再取快照")

    def test_lock_hides_the_row_enable_buttons_that_would_otherwise_show(self):
        """装好没启用的两行（手机「启用手机控制」、识别「启用」）一等锁就收起，没等锁时照常给。"""
        res = run_js(PRELUDE + r"""
const plain = { available: true };
__rows(plain, plain);
PhonePanel.paint();
const before = __ui();
__rows({ available: true, busy: true, lock_wait_s: 5 },
       { available: true, busy: true, lock_wait_s: 5 });
PhonePanel.paint();
out.push({ before: before, after: __ui() });
""")
        data = res[0]
        self.assertFalse(data["before"]["phone"]["feature"], "没在等锁时手机行要给「启用手机控制」")
        self.assertFalse(data["before"]["ocr"]["enable"], "没在等锁时识别行要给「启用」")
        self.assertTrue(data["after"]["phone"]["feature"], "等锁时不给「启用手机控制」")
        self.assertTrue(data["after"]["ocr"]["enable"], "等锁时不给「启用」")

    def test_row_without_cache_says_it_is_still_looking(self):
        """没缓存又等锁：不给任何按钮，写一句「正在确认组件状态…」，并自动再取快照。"""
        res = run_js(PRELUDE + r"""
__rows({ status: "checking", available: false }, { status: "checking", available: false });
PhonePanel.paint();
out.push({ ui: __ui(), polling: PhonePanel.needsPolling() });
""")
        data = res[0]
        ui = data["ui"]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["probe"], [False, WAITING, "waiting"], side + "：要说在确认")
            self.assertTrue(ui[side]["retry"][0], side + "：还没到 30 秒不给「重试」")
            self.assertTrue(ui[side]["install"][0], side + "：没结论不给主按钮")
            self.assertTrue(ui[side]["cancel"][0], side + "：不是在下载")
            self.assertTrue(ui[side]["missing"], side + "：不能显示成没装")
            self.assertTrue(ui[side]["loading"], side + "：不是在下载，进度块收起")
        self.assertTrue(ui["phone"]["feature"])
        self.assertTrue(ui["ocr"]["enable"])
        self.assertTrue(data["polling"])


class TimeoutAndRetryTests(unittest.TestCase):
    """等锁超过 30 秒：明说在等，并给「重试」；重试从点下去那一刻重新算 30 秒。"""

    def test_timeout_says_so_and_offers_a_retry(self):
        """超时（有缓存、没缓存各一）：写「已等 30 秒」，「重试」可见可点，主按钮收起，不自动轮询。"""
        res = run_js(PRELUDE + r"""
__rows({ ready: true, busy: true, lock_wait_s: 40, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 40, check_timed_out: true });
PhonePanel.paint();
const cached = __ui();
const cachedPolling = PhonePanel.needsPolling();
__rows({ status: "checking", available: true, busy: true, lock_wait_s: 40, check_timed_out: true },
       { status: "checking", available: true, busy: true, lock_wait_s: 40, check_timed_out: true });
PhonePanel.paint();
const fresh = __ui();
const freshPolling = PhonePanel.needsPolling();
// 没点过重试、后端已经报超时：哪怕等锁秒数还没到 30 秒，也按超时算
__rows({ ready: true, busy: true, lock_wait_s: 10, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 10, check_timed_out: true });
PhonePanel.paint();
out.push({ cached: cached, fresh: fresh, backendSaysTimedOut: __ui(),
           polling: [cachedPolling, freshPolling, PhonePanel.needsPolling()] });
""")
        data = res[0]
        for name in ("cached", "fresh", "backendSaysTimedOut"):
            ui = data[name]
            for side in ("phone", "ocr"):
                self.assertEqual(ui[side]["probe"], [False, TIMEOUT, "timeout"], side + "：要说明在等")
                self.assertEqual(ui[side]["retry"], [False, False], side + "：「重试」要可见可点")
                self.assertTrue(ui[side]["install"][0], side + "：超时不给主按钮")
                self.assertTrue(ui[side]["missing"], side + "：不能显示成没装")
        self.assertEqual(data["polling"], [False, False, False], "超时不再自动轮询，交给用户点")

    def test_retry_restarts_the_thirty_second_clock(self):
        """点「重试」后：还不到 30 秒回到「正在确认」，再等满 30 秒又变成超时。"""
        res = run_js(PRELUDE + r"""
__rows({ ready: true, busy: true, lock_wait_s: 40, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 40, check_timed_out: true });
PhonePanel.paint();
$("#btn-phone-component-retry").click();
await __flush();
__snap({ ready: true, busy: true, lock_wait_s: 55, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 55, check_timed_out: true });
await PhonePanel.refresh();
out.push({ afterClick: __ui().phone, base: retryWaitBase("phone_control") });
__snap({ ready: true, busy: true, lock_wait_s: 65, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 65, check_timed_out: true });
await PhonePanel.refresh();
out.push({ mid: __ui().phone });
__snap({ ready: true, busy: true, lock_wait_s: 85, check_timed_out: true },
       { ready: true, busy: true, lock_wait_s: 85, check_timed_out: true });
await PhonePanel.refresh();
out.push({ later: __ui().phone });
""")
        first, clicked, mid, later = res[0], res[0]["afterClick"], res[1]["mid"], res[2]["later"]
        self.assertEqual(first["base"], 40, "起点记的是点下去那一刻的等锁秒数")
        self.assertTrue(clicked["probe"][0], "还不到 30 秒：说明收起，回到只是等结论")
        self.assertTrue(clicked["retry"][0], "还不到 30 秒：不显示「重试」")
        self.assertTrue(mid["probe"][0], "差 25 秒还在窗口里：说明仍然收起")
        self.assertTrue(mid["retry"][0], "差 25 秒不给「重试」")
        self.assertEqual(later["probe"], [False, TIMEOUT, "timeout"], "又等满 30 秒：再次说清在等")
        self.assertEqual(later["retry"], [False, False], "又超时：「重试」回来")

    def test_reading_recovers_and_clears_the_retry_start(self):
        """快照给出结论后：说明与「重试」一起收起，起点清掉。"""
        res = run_js(PRELUDE + r"""
__rows({ ready: true, read_error: true }, { ready: true, read_error: true });
PhonePanel.paint();
const broken = __ui();
__snap({ ready: true }, { ready: true });
$("#btn-ocr-retry").click();
await __flush();
out.push({ broken: broken, base: retryWaitBase("relogin_ocr"), after: __ui(),
           baseAfter: retryWaitBase("relogin_ocr") });
""")
        data = res[0]
        for side in ("phone", "ocr"):
            self.assertEqual(data["broken"][side]["probe"], [False, UNREADABLE, "unreadable"],
                             side + "：读不到要说清楚")
            self.assertEqual(data["broken"][side]["retry"], [False, False], side + "：读不到给「重试」")
        self.assertTrue(data["after"]["ocr"]["probe"][0], "快照恢复后说明收起")
        self.assertTrue(data["after"]["ocr"]["retry"][0], "快照恢复后「重试」收起")
        self.assertIsNone(data["baseAfter"], "读到结论后起点不留着")

    def test_retry_is_disabled_while_the_panel_is_busy(self):
        """面板正忙时「重试」看得见但点不动，等这一轮做完再点。"""
        res = run_js(PRELUDE + r"""
__rows({ ready: true, busy: true, lock_wait_s: 40, check_timed_out: true },
       { ready: true });
await __flush();
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push(__ui().phone.retry);
""")
        self.assertEqual(res[0], [False, True], "看得见、但禁用")

    def test_unreadable_without_cache_also_offers_a_retry(self):
        """没缓存又读不到：一样说「暂时读不到组件状态」并给「重试」，不显示成没装。"""
        res = run_js(PRELUDE + r"""
__rows({ read_error: true }, { read_error: true });
PhonePanel.paint();
out.push(__ui());
""")
        ui = res[0]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["probe"], [False, UNREADABLE, "unreadable"], side)
            self.assertEqual(ui[side]["retry"], [False, False], side)
            self.assertTrue(ui[side]["install"][0], side + "：读不到不给主按钮")


class BrokenRowTests(unittest.TestCase):
    """坏了：主按钮改「重新安装」，走同一条在线下载；红条说明不会动账号和设置。"""

    def test_broken_row_offers_reinstall_on_the_main_button(self):
        """两行主按钮都写「重新安装」，点下去发出本行组件的下载请求，标题行不给入口。"""
        res = run_js(PRELUDE + r"""
__rows({ status: "failed" }, { status: "failed" });
PhonePanel.paint();
const ui = __ui();
$("#btn-phone-component-install").click();
await __flush();
$("#btn-ocr-download").click();
await __flush();
out.push({ ui: ui, calls: window.__calls.slice() });
""")
        data = res[0]
        ui = data["ui"]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["install"], [False, "重新安装", False], side + "：主按钮改重新安装")
            self.assertEqual(ui[side]["err"], [False, BROKEN], side + "：要说清不会动账号和设置")
            self.assertTrue(ui[side]["retry"][0], side + "：坏了不是读状态，不给「重试」")
        self.assertTrue(ui["phone"]["feature"], "坏了不再另给一个导入入口")
        self.assertTrue(ui["ocr"]["enable"], "坏了的识别行不给「启用」")
        self.assertEqual(data["calls"], [["download_advanced_feature", "phone_control"],
                                         ["download_advanced_feature", "relogin_ocr"]],
                         "点重新安装走在线下载，带本行的组件名")

    def test_reinstall_failure_keeps_the_broken_words_and_offers_import(self):
        """重新安装失败：仍停在坏了，红条换成本次失败的原因，导入兜底出现。"""
        res = run_js(PRELUDE + r"""
const failed = { state: "failed", error_code: "network_error", text: "后端原话" };
__rows({ status: "failed", download: failed }, { status: "failed", download: failed });
PhonePanel.paint();
out.push(__ui());
""")
        ui = res[0]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["install"], [False, "重新安装", False], side + "：主按钮仍是重新安装")
            self.assertEqual(ui[side]["err"],
                             [False, "下载没有完成：连不上发布页，可以重试。"], side + "：红条说这次失败")
            self.assertFalse(ui[side]["imp"], side + "：失败后给手动导入的兜底")


class QuietTransitionsTests(unittest.TestCase):
    """不吵人的两条：取消下载不留痕；下载中同时等锁也不打扰。"""

    def test_cancelling_a_download_leaves_no_trace(self):
        """取消后两行都回到「下载并安装」：没装块显示，任何一句取消话都不出现。"""
        res = run_js(PRELUDE + r"""
__rows({ download: { state: "cancelled" } }, { download: { state: "cancelled" } });
PhonePanel.paint();
out.push({ ui: __ui(), note: [$("#ocr-note").hidden, $("#ocr-note").textContent],
           offNote: $("#phone-off-note").hidden });
""")
        data = res[0]
        for side in ("phone", "ocr"):
            self.assertEqual(data["ui"][side]["install"], [False, "下载并安装", False], side)
            self.assertFalse(data["ui"][side]["missing"], side + "：取消后就是没装，块要显示")
            self.assertTrue(data["ui"][side]["probe"][0], side + "：取消不是读状态")
            self.assertTrue(data["ui"][side]["retry"][0], side)
            self.assertTrue(data["ui"][side]["imp"], side + "：取消不是失败，不露导入")
        self.assertEqual(data["note"], [True, ""], "识别行的说明位不写取消话")
        self.assertTrue(data["offNote"])

    def test_failed_download_on_an_empty_row_offers_download_again(self):
        """没装又下载失败过：主按钮说「重新下载」，导入兜底这时才出现。"""
        res = run_js(PRELUDE + r"""
__rows({ download: { state: "failed", error_code: "network_error" } },
       { download: { state: "failed", error_code: "network_error" } });
await __flush();
out.push(__ui());
""")
        for row in ("phone", "ocr"):
            self.assertEqual(res[0][row]["install"], [False, "重新下载", False], row)
            self.assertEqual(res[0][row]["probe"], [True, "", ""], row)
            self.assertFalse(res[0][row]["imp"], row + "：下载失败过要留导入兜底")

    def test_downloading_row_stays_quiet_even_when_the_backend_is_busy(self):
        """下载中同时等锁：进度块照常显示、「取消下载」照常能点，不插一句读状态的话。"""
        res = run_js(PRELUDE + r"""
const row = { ready: true, busy: true, lock_wait_s: 40, check_timed_out: true,
              download: { state: "downloading", downloaded: 5, total_bytes: 10 } };
__rows(row, row);
PhonePanel.paint();
out.push(__ui());
""")
        ui = res[0]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["cancel"], [False, False], side + "：取消下载要能点")
            self.assertFalse(ui[side]["loading"], side + "：进度块要显示")
            self.assertTrue(ui[side]["probe"][0], side + "：下载中不插读状态的话")
            self.assertTrue(ui[side]["retry"][0], side)
            self.assertTrue(ui[side]["install"][0], side + "：下载中不给主按钮")


if __name__ == "__main__":
    unittest.main()
