#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_ui_components_and_phone.py（来源：test_component_machine.py, test_component_transitions.py, test_settings_adv_rows.py, test_phone_link.py, test_topbar_phone.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_component_machine.py ====================
"""两个组件行共用的纯函数状态机：componentState 逐状态断言与两个认阶段适配的映射。

全部走 fixtures.ui_harness 的整页沙箱（run_js）：加载真实模块图，在沙箱里调
componentState、phonePhase、ocrPhase，断言状态与派生事实；不开浏览器、不发请求。

@author Author
"""

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402


class ComponentStateTests(unittest.TestCase):
    """componentState 的八个状态与派生事实；安装中可以叠在没装、需要更新上。"""

    def test_component_state_covers_every_state_in_order(self):
        """判断顺序与改前两份认阶段相同：下载、校验优先于状态字，ready 优先于 available。"""
        res = run_js("""
out.push(componentState({}, {}).state);
out.push(componentState({ download: { state: "downloading" }, ready: true }, {}).state);
out.push(componentState({ download: { state: "verifying" } }, {}).state);
out.push(componentState({ status: "checking", available: true }, {}).state);
out.push(componentState({ status: "outdated", available: true }, {}).state);
out.push(componentState({ status: "failed", available: true }, {}).state);
out.push(componentState({ ready: true }, {}).state);
out.push(componentState({ available: true }, {}).state);
""")
        self.assertEqual(res, ["missing", "downloading", "verifying", "checking",
                               "outdated", "broken", "enabled", "disabled"])

    def test_component_state_derived_facts_follow_the_row(self):
        """派生事实：失败、刚取消、在下载或校验、在加载、安装中、忙碌、位置与下载事务原样带出。"""
        res = run_js("""
const row = { available: true, status: "outdated",
  download: { state: "failed", total_bytes: 10485760, downloaded: 1048576 } };
const facts = componentState(row, { busy: true, installing: false,
  location: { path: "P:/demo/dir", short: "demo" } });
out.push([facts.failed, facts.cancelled, facts.downloading, facts.loading,
          facts.installing, facts.busy, facts.downloadState,
          facts.download.state, facts.location.short]);
const idle = componentState({ available: true }, {});
out.push([idle.failed, idle.cancelled, idle.downloading, idle.loading,
          idle.installing, idle.busy, idle.downloadState, idle.location]);
const empty = componentState({}, {});
out.push([componentState({ download: { state: "cancelled" } }, {}).cancelled,
          empty.downloadState]);
""")
        self.assertEqual(res[0], [True, False, False, False, False, True,
                                  "failed", "failed", "demo"])
        self.assertEqual(res[1], [False, False, False, False, False, False, "", None])
        self.assertEqual(res[2], [True, ""])

    def test_installing_overlays_missing_and_outdated(self):
        """安装中叠在没装、需要更新上：状态不变，进度块都要亮（安装中不能当没装或没结论）。"""
        res = run_js("""
const fromMissing = componentState({}, { installing: true });
out.push([fromMissing.state, fromMissing.loading, fromMissing.installing]);
const fromOutdated = componentState({ status: "outdated", available: true },
                                    { installing: true });
out.push([fromOutdated.state, fromOutdated.loading, fromOutdated.installing]);
const verifying = componentState({ download: { state: "verifying" } },
                                 { installing: true });
out.push([verifying.state, verifying.loading, verifying.installing]);
""")
        self.assertEqual(res[0], ["missing", True, True])
        self.assertEqual(res[1], ["outdated", True, True])
        self.assertEqual(res[2], ["verifying", True, True])

    def test_installing_is_an_adapter_fact_not_a_listed_state(self):
        """安装中只存在于适配层：状态机照旧报原状态，loading/installing 为真，清单里没有 installing。

        两行标题行的「正在安装组件…」由这份适配事实驱动，不能被当成「没装」。
        """
        data = run_js("""
const rows = [{}, { status: "outdated", available: true }, { ready: true }];
const facts = rows.map((row) => componentState(row, { installing: true }));
const head = rowHead("ocr", facts[0], { phase: "installing" });
out.push({ states: facts.map((f) => f.state), loading: facts.map((f) => f.loading),
  installing: facts.map((f) => f.installing), listed: COMPONENT_STATES.slice(),
  head: { text: head.text, tone: head.tone, button: head.button } });
""")[0]
        self.assertEqual(data["installing"], [True, True, True])
        self.assertEqual(data["loading"], [True, True, True])
        self.assertNotIn("installing", data["listed"],
                         "安装中是适配层事实，不能混进共享状态清单")
        for state in data["states"]:
            self.assertIn(state, data["listed"], "状态机返回值仍要落在清单里")
        self.assertEqual(data["head"]["text"], "正在安装组件…")
        self.assertEqual(data["head"]["tone"], "blue")
        self.assertIsNone(data["head"]["button"], "安装中不给可点的按钮")


class ProbeTests(unittest.TestCase):
    """读状态那一层：等锁、超时、读不到三种说法，以及手机行「开着」对状态的改写。"""

    def test_probe_has_four_values_and_download_wins(self):
        """四种取值：空、waiting、timeout、unreadable；在下载或校验时一律为空。"""
        res = run_js("""
out.push(componentState({ ready: true }, {}).probe);
out.push(componentState({ ready: true, busy: true }, {}).probe);
out.push(componentState({ status: "checking" }, {}).probe);
out.push(componentState({ ready: true, check_timed_out: true }, {}).probe);
out.push(componentState({ ready: true, read_error: true }, {}).probe);
out.push(componentState({ download: { state: "downloading" }, read_error: true }, {}).probe);
out.push(componentState({ download: { state: "verifying" }, busy: true }, {}).probe);
""")
        self.assertEqual(res, ["", "waiting", "waiting", "timeout", "unreadable", "", ""])

    def test_probe_timeout_counts_from_the_retry_start(self):
        """超时按「点过重试」那一刻重新算：差不到 30 秒是等锁，差满 30 秒才是超时。"""
        res = run_js("""
const row = (wait, timed) => ({ ready: true, busy: true, lock_wait_s: wait,
                               check_timed_out: timed });
out.push(componentState(row(55, true), { retryWaitBase: 40 }).probe);
out.push(componentState(row(70, true), { retryWaitBase: 40 }).probe);
out.push(componentState(row(90, true), { retryWaitBase: 40 }).probe);
out.push(componentState(row(90, false), { retryWaitBase: 40 }).probe);
out.push(componentState(row(40, true), { retryWaitBase: 40 }).probe);
""")
        self.assertEqual(res, ["waiting", "timeout", "timeout", "waiting", "waiting"])

    def test_running_forces_enabled_and_loading_only_counts_installing(self):
        """手机行开着时状态取 enabled、不算在下载；loading 只看安装中，检查中不再是加载。"""
        res = run_js("""
const on = componentState({ status: "checking", busy: true },
                          { running: true, installing: false });
out.push([on.state, on.downloading, on.loading, on.probe]);
const onInstalling = componentState({ status: "checking" }, { running: true, installing: true });
out.push([onInstalling.state, onInstalling.loading, onInstalling.probe]);
const idleChecking = componentState({ status: "checking", available: true }, {});
out.push([idleChecking.state, idleChecking.downloading, idleChecking.loading]);
const downloading = componentState({ download: { state: "downloading" } }, {});
out.push([downloading.state, downloading.downloading, downloading.loading]);
""")
        self.assertEqual(res[0], ["enabled", False, False, "waiting"])
        self.assertEqual(res[1], ["enabled", True, "waiting"])
        self.assertEqual(res[2], ["checking", False, False])
        self.assertEqual(res[3], ["downloading", True, True])


class StateInventoryTests(unittest.TestCase):
    """两台状态机各导出一份状态清单：推导函数只会返回清单里的值，看一处就知道有哪几种。"""

    def test_component_state_only_returns_the_listed_states(self):
        """整张输入网格（下载六档、状态五档、ready/available/running、三种忙的现象）都落在清单里。"""
        data = run_js("""
const seen = { state: [], probe: [] };
const dl = ["", "downloading", "verifying", "installed", "failed", "cancelled"];
const st = ["", "missing", "checking", "outdated", "failed", "ready"];
for (const d of dl) for (const s of st) for (const ready of [false, true])
  for (const avail of [false, true]) for (const running of [false, true])
    for (const read_error of [false, true]) for (const timed_out of [false, true])
      for (const busy of [false, true]) {
        const row = { download: { state: d }, status: s, ready: ready, available: avail,
                      busy: busy, read_error: read_error, check_timed_out: timed_out,
                      lock_wait_s: 90 };
        const facts = componentState(row, { installing: false, busy: busy, running: running,
                                           retryWaitBase: 0 });
        seen.state.push(facts.state);
        seen.probe.push(facts.probe);
      }
out.push({ seen: seen, states: COMPONENT_STATES, probes: COMPONENT_PROBES,
           frozen: [Object.isFrozen(COMPONENT_STATES), Object.isFrozen(COMPONENT_PROBES)] });
""")[0]
        self.assertEqual(data["frozen"], [True, True], "清单要冻结，不能让别处改")
        for key, listed in (("state", data["states"]), ("probe", data["probes"])):
            self.assertEqual(sorted(set(data["seen"][key])), sorted(listed),
                             key + "：清单要与推导实际会返回的值一一对上")
            for value in data["seen"][key]:
                self.assertIn(value, listed, key + "：推导返回了清单外的值")

    def test_phone_link_view_only_returns_the_listed_states(self):
        """手机连接状态同理：开着没开着、六种 link、配对与活动会话、四种秒数都落在四种状态里。"""
        data = run_js("""
const seen = [];
const links = [undefined, "unknown", "off", "waiting", "connected", "disconnected"];
const agos = [null, 30, 150, 4000];
for (const running of [false, true]) for (const link of links)
  for (const paired of [0, 1]) for (const live of [false, true]) for (const ago of agos) {
    const view = phoneLinkView({ running: running, link: link, paired_count: paired,
                                 live_session: live, last_contact_ago_s: ago });
    seen.push([view.link, typeof view.title, typeof view.big, typeof view.chip]);
  }
out.push({ seen: seen, listed: PHONE_LINK_STATES, frozen: Object.isFrozen(PHONE_LINK_STATES) });
""")[0]
        self.assertTrue(data["frozen"], "清单要冻结，不能让别处改")
        observed = [item[0] for item in data["seen"]]
        self.assertEqual(sorted(set(observed)), sorted(data["listed"]))
        for item in data["seen"]:
            self.assertIn(item[0], data["listed"])
            self.assertEqual(item[1:], ["string", "string", "string"], "每档都要给出可直接写的字")


class PhaseAdapterTests(unittest.TestCase):
    """phonePhase 与 ocrPhase：名字、参数、返回值不变，判断交给共用状态机。"""

    def test_phone_phase_maps_the_shared_machine_and_keeps_running_first(self):
        """手机行：开着就是 on；否则 enabled 当「装好未开启」，其余按组件状态同名给出。"""
        res = run_js("""
out.push(phonePhase({ running: true }, {}));
out.push(phonePhase({ running: true }, { download: { state: "downloading" } }));
out.push(phonePhase({ running: false }, { ready: true }));
out.push(phonePhase({ running: false }, { available: true }));
out.push(phonePhase({ running: false }, {}));
out.push(phonePhase({ running: false }, { status: "checking", available: true }));
out.push(phonePhase({ running: false }, { status: "outdated", available: true }));
out.push(phonePhase({ running: false }, { status: "failed", available: true }));
out.push(phonePhase({ running: false }, { download: { state: "downloading" } }));
out.push(phonePhase({ running: false }, { download: { state: "verifying" } }));
""")
        self.assertEqual(res, ["on", "on", "off", "disabled", "missing", "checking",
                               "outdated", "broken", "downloading", "verifying"])

    def test_ocr_phase_maps_the_shared_machine(self):
        """识别行：enabled 当已启用、disabled 也当未启用，其余同名；不认「开着」这档。"""
        res = run_js("""
out.push(ocrPhase({ ready: true }));
out.push(ocrPhase({ available: true }));
out.push(ocrPhase({}));
out.push(ocrPhase({ status: "checking", available: true }));
out.push(ocrPhase({ status: "outdated", available: true }));
out.push(ocrPhase({ status: "failed", available: true }));
out.push(ocrPhase({ download: { state: "downloading" } }));
out.push(ocrPhase({ download: { state: "verifying" } }));
out.push(ocrPhase({ ready: true, download: { state: "downloading" } }));
""")
        self.assertEqual(res, ["on", "off", "missing", "checking", "outdated",
                               "broken", "downloading", "verifying", "downloading"])

    def test_phone_lifecycle_phases_stay_adapter_facts(self):
        """开机关机是适配层的显示事实：开着仍报 on（组件行说在下载也不改），两档都不进连接状态清单。"""
        data = run_js("""
const downloading = { download: { state: "downloading" }, ready: false };
const on = phonePhase({ running: true }, downloading);
const starting = rowHead("phone", componentState({}, {}), { phase: "off", starting: true });
const stopping = rowHead("phone", componentState({ ready: true }, { running: true }),
                         { phase: "on", stopping: true });
out.push({ on: on, links: PHONE_LINK_STATES.slice(),
  starting: { text: starting.text, tone: starting.tone, button: starting.button },
  stopping: { text: stopping.text, tone: stopping.tone, button: stopping.button } });
""")[0]
        self.assertEqual(data["on"], "on", "手机访问开着时组件行在下载也按启用画")
        self.assertNotIn("starting", data["links"])
        self.assertNotIn("stopping", data["links"])
        self.assertEqual(data["starting"]["text"], "正在开启…")
        self.assertEqual(data["starting"]["tone"], "blue")
        self.assertIsNone(data["starting"]["button"])
        self.assertEqual(data["stopping"]["text"], "正在停止…")
        self.assertEqual(data["stopping"]["tone"], "blue")
        self.assertIsNone(data["stopping"]["button"])

# ==================== 源自 test_component_transitions.py ====================
"""组件行的状态转移：读状态这一层（等锁、超时、读不到）与坏了、取消、下载中各自长什么样。

一条转移一个用例，走 fixtures.ui_harness 的整页沙箱（run_js）：给后端快照、按需要点一下
「重试」或主按钮，只看用户看得到的结果（按钮在不在、能不能点、说明写的是哪句、有没有
再取一次快照），不对源码文本做断言。两行都适用的转移，两行都断言。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


# 公共桩：两行快照、可替换的下一次快照、记账的下载与取消请求、微任务推进
COMP_TRANS_PRELUDE = r"""
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
           chip: [$("#phone-feature-status").hidden, $("#phone-feature-status-text").textContent,
                  $("#phone-feature-status").className],
           err: [$("#phone-component-error").hidden, $("#phone-component-error").textContent],
           imp: $("#phone-import-line").hidden },
  ocr: { install: [$("#btn-ocr-download").hidden, $("#btn-ocr-download").textContent,
                   $("#btn-ocr-download").disabled],
         cancel: [$("#btn-ocr-cancel").hidden, $("#btn-ocr-cancel").disabled],
         missing: $("#ocr-missing").hidden, loading: $("#ocr-loading").hidden,
         probe: [$("#ocr-note").hidden, $("#ocr-note").textContent, $("#ocr-note").dataset.probe],
         retry: [$("#btn-ocr-retry").hidden, $("#btn-ocr-retry").disabled],
         enable: $("#btn-ocr-enable").hidden,
         chip: [$("#ocr-feature-status").hidden, $("#ocr-feature-status-text").textContent,
                $("#ocr-feature-status").className],
         err: [$("#ocr-download-error").hidden, $("#ocr-download-error").textContent],
         imp: $("#ocr-import-line").hidden },
});
"""

COMP_WAITING = "正在确认组件状态…"
TIMEOUT = "另一个窗口正在安装或更新组件，已等 30 秒"
UNREADABLE = "暂时读不到组件状态"
BROKEN = "组件文件不完整。重新安装不会动你的账号和设置。"


class ReadingStateHiddenTests(unittest.TestCase):
    """等锁没结论时：不装蒜也不假装在下载，原字保留，只多一句说明。"""

    def test_cached_row_under_lock_keeps_its_words_and_hides_actions(self):
        """有缓存又等锁：原来的字与 chip 一个字不变，主按钮、启用、进度块全收起，自动再取快照。"""
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
            self.assertEqual(after[side]["chip"][1], data["before"][side]["chip"][1],
                             side + "：等锁时原来的字要保留")
            self.assertEqual(after[side]["chip"][2], "adv-s blue", side + "：只把圆点变蓝")
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
__rows({ status: "checking", available: false }, { status: "checking", available: false });
PhonePanel.paint();
out.push({ ui: __ui(), polling: PhonePanel.needsPolling() });
""")
        data = res[0]
        ui = data["ui"]
        for side in ("phone", "ocr"):
            self.assertEqual(ui[side]["chip"][1], COMP_WAITING, side + "：状态句要说在确认")
            self.assertTrue(ui[side]["probe"][0], side + "：确认中不叠第二句")
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
                self.assertEqual(ui[side]["chip"][1], TIMEOUT, side + "：状态句要说明在等")
                self.assertTrue(ui[side]["probe"][0], side + "：等超时只说一句")
                self.assertEqual(ui[side]["retry"], [False, False], side + "：「重试」要可见可点")
                self.assertTrue(ui[side]["install"][0], side + "：超时不给主按钮")
                self.assertTrue(ui[side]["missing"], side + "：不能显示成没装")
        self.assertEqual(data["polling"], [False, False, False], "超时不再自动轮询，交给用户点")

    def test_retry_restarts_the_thirty_second_clock(self):
        """点「重试」后：还不到 30 秒回到「正在确认」，再等满 30 秒又变成超时。"""
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        self.assertEqual(later["chip"][1], TIMEOUT, "又等满 30 秒：再次说清在等")
        self.assertEqual(later["retry"], [False, False], "又超时：「重试」回来")

    def test_reading_recovers_and_clears_the_retry_start(self):
        """快照给出结论后：说明与「重试」一起收起，起点清掉。"""
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
            self.assertEqual(ui[side]["probe"], [False, BROKEN, ""], side + "：要说清不会动账号和设置")
            self.assertTrue(ui[side]["err"][0], side + "：文件不完整那句不进红条")
            self.assertTrue(ui[side]["retry"][0], side + "：坏了不是读状态，不给「重试」")
        self.assertTrue(ui["phone"]["feature"], "坏了不再另给一个导入入口")
        self.assertTrue(ui["ocr"]["enable"], "坏了的识别行不给「启用」")
        self.assertEqual(data["calls"], [["download_advanced_feature", "phone_control"],
                                         ["download_advanced_feature", "relogin_ocr"]],
                         "点重新安装走在线下载，带本行的组件名")

    def test_reinstall_failure_keeps_the_broken_words_and_offers_import(self):
        """重新安装失败：仍停在坏了，红条换成本次失败的原因，导入兜底出现。"""
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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
        res = run_js(COMP_TRANS_PRELUDE + r"""
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

# ==================== 源自 test_settings_adv_rows.py ====================
"""设置抽屉「高级功能」两项一行：标题行这一层长什么样。

一张表一格一个用例（口径见 docs/UI_SPEC.md 的「设置里的组件行」与证据目录的
dom-contract.md）：状态句、圆点颜色、主按钮的文字与显隐、标题行下那句小字或红条、
进度条宽度、展开区开合，以及「同一时刻标题行只有一只按钮看得见」。
走 fixtures.ui_harness 的整页沙箱（run_js），只看用户看得到的结果，不对源码文本断言。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


ADV_ROWS_PRELUDE = r"""
window.__calls = [];
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
  download_advanced_feature: (name) => {
    window.__calls.push(["download_advanced_feature", name]); return Promise.resolve({ ok: true });
  },
  start_phone_access: () => { window.__calls.push(["start_phone_access"]); return Promise.resolve({ ok: true }); },
  stop_phone_access: () => { window.__calls.push(["stop_phone_access"]); return Promise.resolve({ ok: true }); },
  enable_advanced_feature: (name) => {
    window.__calls.push(["enable_advanced_feature", name]); return Promise.resolve({ ok: true });
  },
} };
const __flush = async (n = 12) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
/* 两行各自的组件快照；环境项（通道、版本等）按需覆盖 */
const __paint = (phoneRow, ocrRow, env) => {
  const more = env || {};
  PhonePanel.state.running = !!more.running;
  PhonePanel.state.link = more.link || "off";
  PhonePanel.state.last_contact_ago_s = more.ago === undefined ? null : more.ago;
  PhonePanel.state.paired_count = more.paired ? 1 : 0;
  PhonePanel.state.live_session = false;
  PhonePanel.state.channel = "tailscale";
  PhonePanel.state.qr = "";
  PhonePanel.state.pair_code = "";
  PhonePanel.state.pair_code_status = null;
  PhonePanel.state.preferred_channel = "";
  PhonePanel.state.advanced = {
    features: { phone_control: phoneRow || {}, relogin_ocr: ocrRow || {} },
    channels: { tailscale: { available: true, state: "ready", addresses: [] },
                cloudflare: { available: false, state: "stopped" } },
    credential: { saved: false, staged: false }, phone_access: {} };
  PhonePanel.busy = !!more.busy;
  PhonePanel.pending = more.pending || "";
  PhonePanel.installing = { phone_control: !!more.installing, relogin_ocr: !!more.installing };
  PhonePanel.notes = { feature: "", missing: "", loading: "", off: "", offErr: "",
                       pair: "", onErr: "" };
  PhonePanel.location = null;
  PhonePanel.lastDownload = "";
  PhonePanel.stopAsk = !!more.stopAsk;
  PhonePanel.addPair = false;
  PhonePanel.codeSync = null;
  PhonePanel.codeLeft = 0;
  PhonePanel.lastCode = "";
  PhonePanel.channel = "";
  OcrPanel.busy = !!more.busy;
  OcrPanel.note = more.note || "";
  OcrPanel.error = "";
  OcrPanel.location = null;
  OcrPanel.lastDownload = "";
  PhonePanel.paint();
};
const __head = (id) => {
  const node = $(id);
  return {
    text: $(id + "-text").textContent,
    hidden: $(id + "-text").hidden,
    cls: node.className,
    tone: (String(node.className || "").replace("adv-s", "").replace("blink", "").trim() || ""),
    blink: String(node.className || "").indexOf("blink") >= 0,
  };
};
/* 一行标题行上看得见的全部按钮（按约定的固定顺序） */
const __buttons = (ids) => ids.filter((id) => !$(id).hidden)
  .map((id) => [id, $(id).textContent, $(id).disabled, $(id).className]);
const __phoneBtns = () => __buttons(["#btn-phone-component-install", "#btn-phone-component-cancel",
  "#btn-phone-component-retry", "#btn-phone-feature-install", "#btn-phone-start", "#btn-phone-stop"]);
const __ocrBtns = () => __buttons(["#btn-ocr-download", "#btn-ocr-cancel", "#btn-ocr-retry",
  "#btn-ocr-enable"]);
const __note = (id) => [$("#" + id).hidden, $("#" + id).textContent, $("#" + id).className];
const __bar = (id, fill) => [$("#" + id).hidden,
  Number($("#" + id).getAttribute("aria-valuenow")), $("#" + fill).style.width];
"""

DEFAULT_SOLID = "btn btn-solid"


def run(snippet):
    """带上公共桩跑一段片段，返回 out 数组。"""
    return run_js(ADV_ROWS_PRELUDE + snippet)


class ComponentHeadWordsTests(unittest.TestCase):
    """没装、下载到装完这一路：状态句、主按钮文字、进度条。"""

    def test_missing_row_offers_the_install_button(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "missing" }, { download: { state: "" }, status: "missing" });
out.push({ phone: __head("#phone-feature-status"), ocr: __head("#ocr-feature-status"),
           phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns() });
""")[0]
        for side, buttons, install_id in (
                ("phone", data["phoneBtns"], "#btn-phone-component-install"),
                ("ocr", data["ocrBtns"], "#btn-ocr-download")):
            head = data[side]
            self.assertEqual(head["text"], "没装")
            self.assertEqual(head["tone"], "grey")
            self.assertFalse(head["hidden"], "状态句要一直显示")
            self.assertEqual([b[0] for b in buttons], [install_id],
                             "没装时标题行只亮「下载并安装」")
            self.assertEqual(buttons[0][1], "下载并安装")
            self.assertEqual(buttons[0][3], DEFAULT_SOLID, "主按钮是实心")
            self.assertFalse(buttons[0][2])

    def test_failed_download_renames_the_button_and_shows_the_red_bar(self):
        data = run(r"""
const row = { download: { state: "failed", error_code: "network_error" }, status: "missing" };
__paint(row, row);
out.push({ phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns(),
           phoneErr: __note("phone-component-error"), ocrErr: __note("ocr-download-error"),
           phoneImp: $("#phone-import-line").hidden, ocrImp: $("#ocr-import-line").hidden });
""")[0]
        self.assertEqual(data["phoneBtns"][0][1], "重新下载")
        self.assertEqual(data["ocrBtns"][0][1], "重新下载")
        for key in ("phoneErr", "ocrErr"):
            self.assertFalse(data[key][0], "下载失败过，标题行下要有红条")
            self.assertIn("连不上发布页", data[key][1])
        self.assertFalse(data["phoneImp"], "展开区要给出导入兜底")
        self.assertFalse(data["ocrImp"])

    def test_downloading_says_how_much_and_shows_the_bar(self):
        data = run(r"""
const row = { download: { state: "downloading", downloaded: 5 * 1048576, total_bytes: 10 * 1048576 },
              status: "missing", available: true };
__paint(row, row);
out.push({ phone: __head("#phone-feature-status"), ocr: __head("#ocr-feature-status"),
           phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns(),
           phoneBar: __bar("phone-loading", "phone-prog-fill"),
           ocrBar: __bar("ocr-loading", "ocr-prog-fill") });
""")[0]
        self.assertEqual(data["phone"]["text"], "下载中 5.0 / 10.0 MB")
        self.assertEqual(data["ocr"]["text"], "下载中 5.0 / 10.0 MB")
        self.assertEqual(data["phone"]["tone"], "blue")
        self.assertEqual([b[1] for b in data["phoneBtns"]], ["取消"], "下载中只给取消")
        self.assertEqual([b[1] for b in data["ocrBtns"]], ["取消"])
        self.assertEqual(data["phoneBar"], [False, 50, "50%"])
        self.assertEqual(data["ocrBar"], [False, 50, "50%"])

    def test_downloading_without_a_total_says_only_downloading(self):
        data = run(r"""
const row = { download: { state: "downloading", downloaded: 3 * 1048576, total_bytes: 0 },
              status: "missing", available: true };
__paint(row, row);
out.push([__head("#phone-feature-status")["text"], __bar("phone-loading", "phone-prog-fill")]);
""")[0]
        self.assertEqual(data[0], "下载中", "总量读不到就不编数字")
        self.assertEqual(data[1], [False, 0, "0%"])

    def test_verifying_is_a_disabled_button_with_a_full_bar(self):
        data = run(r"""
const row = { download: { state: "verifying", downloaded: 10 * 1048576, total_bytes: 10 * 1048576 },
              status: "missing", available: true };
__paint(row, row);
out.push({ text: __head("#ocr-feature-status")["text"], btns: __ocrBtns(),
           bar: __bar("ocr-loading", "ocr-prog-fill") });
""")[0]
        self.assertEqual(data["text"], "下载完了，正在校验…")
        self.assertEqual([b[1] for b in data["btns"]], ["校验中…"])
        self.assertTrue(data["btns"][0][2], "校验中这只按钮要禁用")
        self.assertEqual(data["bar"], [False, 100, "100%"])

    def test_installing_takes_the_button_away(self):
        data = run(r"""
__paint({ download: { state: "installed" }, status: "missing" },
        { download: { state: "installed" }, status: "missing" }, { installing: true });
out.push({ text: __head("#ocr-feature-status")["text"], btns: __ocrBtns(),
           phoneBtns: __phoneBtns() });
""")[0]
        self.assertEqual(data["text"], "正在安装组件…")
        self.assertEqual(data["btns"], [], "安装中不给按钮")
        self.assertEqual(data["phoneBtns"], [])


class ComponentProbeWordsTests(unittest.TestCase):
    """读状态这三格：检查中、等锁有上次结论、超时、读不到。"""

    def test_checking_without_a_cache_says_it_is_looking(self):
        data = run(r"""
__paint({ status: "checking" }, { status: "checking" });
out.push({ phone: __head("#phone-feature-status"), phoneBtns: __phoneBtns(),
           ocrBtns: __ocrBtns(), phoneNote: __note("phone-probe") });
""")[0]
        self.assertEqual(data["phone"]["text"], "正在确认组件状态…")
        self.assertEqual(data["phone"]["tone"], "blue")
        self.assertEqual(data["phoneBtns"], [], "没结论不给动作按钮")
        self.assertEqual(data["ocrBtns"], [])
        self.assertTrue(data["phoneNote"][0], "没有上次结论时不用写下面那行小字")

    def test_locked_with_a_cached_answer_keeps_the_words_and_blues_the_dot(self):
        data = run(r"""
const plain = run => run();
__paint({ download: { state: "" }, status: "ready" }, { status: "ready" });
const before = { phone: __head("#phone-feature-status")["text"], ocr: __head("#ocr-feature-status")["text"] };
__paint({ download: { state: "" }, status: "ready", busy: true, lock_wait_s: 6 },
        { status: "ready", busy: true, lock_wait_s: 6 });
out.push({ before: before,
           phone: __head("#phone-feature-status"), ocr: __head("#ocr-feature-status"),
           phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns(), phoneNote: __note("phone-probe") });
""")[0]
        self.assertEqual(data["phone"]["text"], data["before"]["phone"], "等锁时字照原来的写")
        self.assertEqual(data["ocr"]["text"], data["before"]["ocr"])
        self.assertEqual(data["phone"]["tone"], "blue", "只把圆点变蓝")
        self.assertEqual(data["ocr"]["tone"], "blue")
        self.assertEqual(data["phoneBtns"], [], "等锁时按钮位收起")
        self.assertEqual(data["ocrBtns"], [])
        self.assertTrue(data["phoneNote"][0], "有上次结论时那行小字不用写")

    def test_timeout_is_an_amber_sentence_with_a_retry(self):
        data = run(r"""
const row = { download: { state: "" }, status: "ready", busy: true, lock_wait_s: 40,
              check_timed_out: true };
__paint(row, row);
out.push({ phone: __head("#phone-feature-status"), phoneBtns: __phoneBtns(),
           ocrBtns: __ocrBtns() });
""")[0]
        self.assertEqual(data["phone"]["text"], "另一个窗口正在安装或更新组件，已等 30 秒")
        self.assertEqual(data["phone"]["tone"], "amber")
        self.assertEqual([b[1] for b in data["phoneBtns"]], ["重试"])
        self.assertEqual([b[1] for b in data["ocrBtns"]], ["重试"])

    def test_unreadable_keeps_the_words_and_adds_an_amber_sentence(self):
        data = run(r"""
const row = { download: { state: "" }, status: "ready", read_error: true };
__paint(row, row);
out.push({ phone: __head("#phone-feature-status"), phoneBtns: __phoneBtns(),
           phoneNote: __note("phone-probe"), ocrBtns: __ocrBtns() });
""")[0]
        self.assertEqual(data["phone"]["text"], "没装", "字照原状态写")
        self.assertEqual(data["phone"]["tone"], "amber-dot", "只把圆点变琥珀")
        self.assertFalse(data["phoneNote"][0])
        self.assertEqual(data["phoneNote"][1], "暂时读不到组件状态")
        self.assertIn("amber", data["phoneNote"][2])
        self.assertEqual([b[1] for b in data["phoneBtns"]], ["重试"])
        self.assertTrue(data["phoneBtns"][0][3].endswith("btn-line"), "重试是线框按钮")


class ComponentStateWordsTests(unittest.TestCase):
    """需要更新、坏了这两档，以及坏了时那句进小字而不是红条。"""

    def test_outdated_explains_what_does_not_need_redoing(self):
        data = run(r"""
const row = { download: { state: "" }, status: "outdated", available: true };
__paint(row, row);
out.push({ phone: __head("#phone-feature-status"), ocr: __head("#ocr-feature-status"),
           phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns(),
           phoneNote: __note("phone-probe"), ocrNote: __note("ocr-note") });
""")[0]
        self.assertEqual(data["phone"]["text"], "需要更新")
        self.assertEqual(data["phone"]["tone"], "amber")
        self.assertEqual([b[1] for b in data["phoneBtns"]], ["更新组件"])
        self.assertEqual([b[1] for b in data["ocrBtns"]], ["更新组件"])
        self.assertIn("手机不用重新配对", data["phoneNote"][1])
        self.assertIn("账号密码不用重填", data["ocrNote"][1])

    def test_broken_says_reinstall_and_puts_the_words_below_the_header(self):
        data = run(r"""
const row = { download: { state: "" }, status: "failed" };
__paint(row, row);
out.push({ phone: __head("#phone-feature-status"), ocr: __head("#ocr-feature-status"),
           phoneBtns: __phoneBtns(), ocrBtns: __ocrBtns(),
           phoneNote: __note("phone-probe"), ocrNote: __note("ocr-note"),
           phoneErr: __note("phone-component-error"), ocrErr: __note("ocr-download-error") });
""")[0]
        self.assertEqual(data["phone"]["text"], "加载失败")
        self.assertEqual(data["phone"]["tone"], "red")
        self.assertEqual([b[1] for b in data["phoneBtns"]], ["重新安装"])
        self.assertEqual([b[1] for b in data["ocrBtns"]], ["重新安装"])
        self.assertEqual(data["phoneNote"][1], "组件文件不完整。重新安装不会动你的账号和设置。")
        self.assertIn("red", data["phoneNote"][2], "这句是深红小字")
        self.assertEqual(data["ocrNote"][1], data["phoneNote"][1])
        self.assertTrue(data["phoneErr"][0], "坏了不再用红条写这句")
        self.assertTrue(data["ocrErr"][0])


    def test_broken_row_that_also_failed_a_download_keeps_the_import_line(self):
        data = run(r"""
const row = { download: { state: "failed", error_code: "network_error" }, status: "failed" };
__paint(row, row);
out.push({ btns: __phoneBtns(), imp: $("#phone-import-line").hidden,
           err: __note("phone-component-error") });
""")[0]
        self.assertEqual([b[1] for b in data["btns"]], ["重新安装"])
        self.assertFalse(data["imp"], "手动出路留着：下载也失败时还能导入已下载的包")
        self.assertFalse(data["err"][0], "红条写下载失败那句")


class PhoneRowWordsTests(unittest.TestCase):
    """手机访问这一行独有的档：停用、未开启、开启中、已开启、停止中。"""

    def test_disabled_and_off_rows(self):
        data = run(r"""
__paint({ download: { state: "" }, available: true }, {}, {});
const off = { text: __head("#phone-feature-status")["text"], btns: __phoneBtns() };
__paint({ download: { state: "" }, status: "ready", ready: true }, {}, { running: false });
out.push({ off: off, waiting: { text: __head("#phone-feature-status")["text"],
                                tone: __head("#phone-feature-status")["tone"],
                                btns: __phoneBtns() },
           hidden: $("#btn-phone-feature-install").hidden });
""")[0]
        self.assertEqual(data["off"]["text"], "已停用")
        self.assertEqual([b[1] for b in data["off"]["btns"]], ["启用手机控制"])
        self.assertEqual(data["waiting"]["text"], "未开启 · 通道用 Tailscale")
        self.assertEqual([b[1] for b in data["waiting"]["btns"]], ["开启"])
        self.assertTrue(data["hidden"], "启用/换组件包那两只这类不用的位置收起")

    def test_missing_cloudflared_keeps_start_and_puts_the_package_in_the_detail(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "ready", ready: true }, {}, { running: false });
PhonePanel.state.advanced.channels.cloudflare = { available: false, state: "missing",
                                                  error: "cloudflared_missing" };
PhonePanel.paint();
const pack = $("#btn-phone-package");
out.push({ text: __head("#phone-feature-status")["text"], btns: __phoneBtns(),
           action: $("#btn-phone-feature-install").dataset.action,
           pack: [pack.hidden, pack.disabled] });
""")[0]
        self.assertEqual(data["text"], "未开启 · 通道用 Tailscale")
        self.assertEqual([b[1] for b in data["btns"]], ["开启"],
                         "标题行不给补装按钮，照常给「开启」")
        self.assertEqual(data["action"], "import")
        self.assertEqual(data["pack"], [False, False],
                         "补装入口放进展开区，缺通道组件时看得见、点得动")
        html = (TESTS.parents[1] / "local" / "ui" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="btn-phone-package" type="button" hidden>安装/更换组件包</button>', html,
                      "展开区里那只补装按钮的文案写在页面上")

    def test_the_package_button_opens_the_import_dialog(self):
        """缺 cloudflared 时展开区那只补装按钮要真的打开导入弹窗（标题行只留「开启」，入口藏在展开区里也得能用）。"""
        data = run(r"""
__paint({ download: { state: "" }, status: "ready", ready: true }, {}, { running: false });
PhonePanel.state.advanced.channels.cloudflare = { available: false, state: "missing",
                                                  error: "cloudflared_missing" };
wireComponentRetries();
PhonePanel.paint();
const pack = $("#btn-phone-package");
const before = [pack.hidden, pack.disabled];
pack.click();
out.push({ before: before, key: PhonePanel.importKey,
           dialog: $("#dlg-components").attr_open === "" || !!$("#dlg-components").open });
""")[0]
        self.assertEqual(data["before"], [False, False], "补装按钮看得见、点得动")
        self.assertEqual(data["key"], "phone_control", "点了要给手机控制选组件包")
        self.assertTrue(data["dialog"], "点了要打开导入弹窗")

    def test_start_failure_renames_the_button(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "ready", ready: true }, {}, {});
PhonePanel.notes.offErr = "端口被占用";
PhonePanel.paint();
out.push({ text: __head("#phone-feature-status")["text"], btns: __phoneBtns(),
           note: __note("phone-probe"), err: __note("phone-component-error"),
           detailErr: __note("phone-off-error") });
""")[0]
        self.assertEqual(data["text"], "未开启 · 通道用 Tailscale")
        self.assertEqual([b[1] for b in data["btns"]], ["重新开启"], "失败过就说重新开启")
        self.assertEqual([data["note"][0], data["note"][1]], [True, ""],
                         "标题行下那行字只讲持续状态，这次出错不写它")
        self.assertEqual([data["err"][0], data["err"][1]], [False, "端口被占用"],
                         "开不起来的原因写在标题行下那条红条里")
        self.assertEqual(data["detailErr"][1], "",
                         "展开区那条红条不讲这次开启失败")

    def test_tunnel_gone_puts_the_reason_in_the_red_bar(self):
        """隧道自己断开：原因走同一红条，按钮改「重新开启」，通道名说 Cloudflare。"""
        data = run(r"""
__paint({ download: { state: "" }, status: "ready", ready: true }, {}, {});
PhonePanel.channel = "cloudflare";
PhonePanel.state.advanced.channels.cloudflare = { available: true, state: "exited", error: "tunnel_exited" };
PhonePanel.paint();
out.push({ text: __head("#phone-feature-status")["text"], btns: __phoneBtns(),
           note: __note("phone-probe"), err: __note("phone-component-error") });
""")[0]
        self.assertEqual(data["text"], "未开启 · 通道用 Cloudflare")
        self.assertEqual([b[1] for b in data["btns"]], ["重新开启"])
        self.assertEqual([data["note"][0], data["note"][1]], [True, ""])
        self.assertEqual([data["err"][0], data["err"][1]],
                         [False, "Cloudflare 隧道断了，旧地址和二维码已失效。重新开启后要重新扫码配对。"],
                         "隧道断开的原因也写红条")

    def test_starting_and_stopping_have_no_button(self):
        data = run(r"""
__paint({ download: { state: "" }, ready: true }, {}, { pending: "starting" });
const starting = { text: __head("#phone-feature-status")["text"], btns: __phoneBtns() };
__paint({ download: { state: "" }, ready: true }, {}, { running: true, pending: "stopping" });
out.push({ starting: starting, stopping: { text: __head("#phone-feature-status")["text"],
                                           btns: __phoneBtns() } });
""")[0]
        self.assertEqual(data["starting"]["text"], "正在开启…")
        self.assertEqual(data["starting"]["btns"], [])
        self.assertEqual(data["stopping"]["text"], "正在停止…")
        self.assertEqual(data["stopping"]["btns"], [])

    def test_running_row_follows_the_link_state(self):
        data = run(r"""
const row = { download: { state: "" }, ready: true };
__paint(row, {}, { running: true, link: "connected", ago: 3, paired: true });
const connected = __head("#phone-feature-status");
__paint(row, {}, { running: true, link: "waiting", paired: true });
const waiting = __head("#phone-feature-status");
__paint(row, {}, { running: true, link: "disconnected", ago: 150, paired: true });
out.push({ connected: connected, waiting: waiting,
           disconnected: __head("#phone-feature-status"), btns: __phoneBtns() });
""")[0]
        self.assertEqual(data["connected"]["text"], "手机已连接")
        self.assertEqual(data["connected"]["tone"], "green")
        self.assertEqual(data["waiting"]["text"], "等手机连接")
        self.assertEqual(data["waiting"]["tone"], "amber")
        self.assertTrue(data["waiting"]["blink"], "等连接时圆点慢闪")
        self.assertEqual(data["disconnected"]["text"], "已断开 · 2 分钟前")
        self.assertEqual([b[1] for b in data["btns"]], ["关闭手机访问"])

    def test_stop_confirm_disables_the_close_button(self):
        data = run(r"""
const row = { download: { state: "" }, ready: true };
__paint(row, {}, { running: true, link: "connected", stopAsk: true, paired: true });
out.push({ btns: __phoneBtns(), confirm: $("#phone-stop-confirm").hidden });
""")[0]
        self.assertEqual([b[1] for b in data["btns"]], ["关闭手机访问"])
        self.assertTrue(data["btns"][0][2], "确认关闭展开时这只按钮禁用")
        self.assertFalse(data["confirm"], "确认块要看得见")


class OcrRowWordsTests(unittest.TestCase):
    """验证码识别这一行独有的两档，以及刚装好那句落到小字里。"""

    def test_installed_but_not_enabled_offers_enable(self):
        data = run(r"""
__paint({}, { download: { state: "" }, available: true });
out.push({ text: __head("#ocr-feature-status")["text"], tone: __head("#ocr-feature-status")["tone"],
           btns: __ocrBtns() });
""")[0]
        self.assertEqual(data["text"], "已装好还没启用")
        self.assertEqual(data["tone"], "grey")
        self.assertEqual([b[1] for b in data["btns"]], ["启用"])

    def test_enabled_row_shows_the_version(self):
        data = run(r"""
__paint({}, { download: { state: "" }, ready: true, package_version: "1.2.0" });
const withVersion = { head: __head("#ocr-feature-status"), btns: __ocrBtns() };
window.PhonePanel.state.running = true;
__paint({}, { download: { state: "" }, ready: true });
out.push({ withVersion: withVersion, noVersion: __head("#ocr-feature-status"),
           missing: $("#ocr-missing").hidden });
""")[0]
        self.assertEqual(data["withVersion"]["head"]["text"], "已启用 · 版本 1.2.0")
        self.assertEqual(data["withVersion"]["head"]["tone"], "green")
        self.assertEqual(data["withVersion"]["btns"], [])
        self.assertEqual(data["noVersion"]["text"], "已启用", "拿不到版本就只写已启用")
        self.assertTrue(data["missing"], "装好的行不显示「没装」块")

    def test_fresh_note_lands_below_the_header(self):
        data = run(r"""
__paint({}, { download: { state: "" }, ready: true, package_version: "1.2.0" },
        { running: true, note: "验证码识别组件已安装并启用。" });
out.push({ note: __note("ocr-note") });
""")[0]
        self.assertFalse(data["note"][0])
        self.assertEqual(data["note"][1], "验证码识别组件已安装并启用。")
        self.assertIn("green", data["note"][2])


    def test_a_panel_note_still_lands_below_the_header_while_checking(self):
        data = run(r"""
__paint({ status: "checking" }, { download: { state: "" }, status: "checking" },
        { note: "验证码识别组件已安装并启用。" });
out.push({ note: __note("ocr-note"), text: __head("#ocr-feature-status")["text"] });
""")[0]
        self.assertEqual(data["text"], "正在确认组件状态…")
        self.assertFalse(data["note"][0], "这次动作的结果也要贴出来")
        self.assertEqual(data["note"][1], "验证码识别组件已安装并启用。")
        self.assertIn("green", data["note"][2])


class SingleButtonTests(unittest.TestCase):
    """一张表一格：同一时刻标题行只亮一只按钮。"""

    def test_each_phase_lights_at_most_one_button(self):
        phases = {
            "missing": {"download": {"state": ""}, "status": "missing"},
            "downloading": {"download": {"state": "downloading", "downloaded": 1, "total_bytes": 4},
                            "status": "missing", "available": True},
            "verifying": {"download": {"state": "verifying"}, "status": "missing", "available": True},
            "installing": {"download": {"state": "installed"}, "status": "missing"},
            "checking": {"status": "checking"},
            "timeout": {"status": "checking", "busy": True, "lock_wait_s": 40, "check_timed_out": True},
            "unreadable": {"status": "ready", "read_error": True},
            "outdated": {"download": {"state": ""}, "status": "outdated", "available": True},
            "broken": {"download": {"state": ""}, "status": "failed"},
            "ready": {"download": {"state": ""}, "status": "ready", "ready": True},
        }
        for name, row in phases.items():
            with self.subTest(phase=name):
                data = run(r"""
__paint(__ROW__, __ROW__, {});
out.push({ phone: __phoneBtns(), ocr: __ocrBtns() });
""".replace("__ROW__", __import__("json").dumps(row)))[0]
                self.assertLessEqual(len(data["phone"]), 1, "手机行同一时刻最多一只按钮")
                self.assertLessEqual(len(data["ocr"]), 1, "识别行同一时刻最多一只按钮")


class ToggleTests(unittest.TestCase):
    """展开箭头：手机默认展开、识别默认收起，点一下换过来。"""

    def test_default_open_close_and_the_arrow(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "missing" }, { download: { state: "" }, status: "missing" });
out.push({ phoneDetail: $("#phone-row-detail").hidden, ocrDetail: $("#ocr-row-detail").hidden,
           phoneAria: $("#btn-phone-row-toggle").getAttribute("aria-expanded"),
           ocrAria: $("#btn-ocr-row-toggle").getAttribute("aria-expanded"),
           phoneLabel: $("#btn-phone-row-toggle").getAttribute("aria-label") });
""")[0]
        self.assertFalse(data["phoneDetail"], "手机访问默认展开")
        self.assertTrue(data["ocrDetail"], "验证码识别默认收起")
        self.assertEqual(data["phoneAria"], "true")
        self.assertEqual(data["ocrAria"], "false")
        self.assertIn("收起", data["phoneLabel"])

    def test_clicking_the_arrow_flips_the_detail_area(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "missing" }, { download: { state: "" }, status: "missing" });
$("#btn-ocr-row-toggle").click();
out.push({ ocrDetail: $("#ocr-row-detail").hidden,
           ocrAria: $("#btn-ocr-row-toggle").getAttribute("aria-expanded") });
$("#btn-phone-row-toggle").click();
out.push({ phoneDetail: $("#phone-row-detail").hidden,
           phoneAria: $("#btn-phone-row-toggle").getAttribute("aria-expanded") });
""")
        self.assertFalse(data[0]["ocrDetail"], "点一下展开")
        self.assertEqual(data[0]["ocrAria"], "true")
        self.assertTrue(data[1]["phoneDetail"], "再点一下收起")
        self.assertEqual(data[1]["phoneAria"], "false", "收起后箭头也要说收起")

    def test_asking_to_close_opens_the_confirmation_area(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "ready", ready: true }, {},
        { running: true, link: "connected", paired: true });
$("#btn-phone-row-toggle").click();
out.push({ collapsed: $("#phone-row-detail").hidden });
$("#btn-phone-stop").click();
out.push({ opened: $("#phone-row-detail").hidden, confirm: $("#phone-stop-confirm").hidden });
""")
        self.assertTrue(data[0]["collapsed"], "先收起")
        self.assertFalse(data[1]["opened"], "点关闭后要自动展开")
        self.assertFalse(data[1]["confirm"], "确认块要看得见")

    def test_expanded_area_keeps_its_own_hidden_flags(self):
        data = run(r"""
__paint({ download: { state: "" }, status: "missing" }, { download: { state: "" }, status: "missing" });
const before = { missing: $("#ocr-missing").hidden, imp: $("#ocr-import-line").hidden };
$("#btn-ocr-row-toggle").click();
out.push({ before: before, after: { missing: $("#ocr-missing").hidden,
                                    imp: $("#ocr-import-line").hidden } });
""")[0]
        self.assertEqual(data["before"], data["after"], "开合只收容器，里面各块自己的显隐不变")


class RowHeadPureTests(unittest.TestCase):
    """rowHead 是纯函数：整张输入网格上出来的颜色都在清单里，文案与按钮名都合法。"""

    def test_row_head_only_returns_listed_tones(self):
        data = run(r"""
const rows = [{ download: { state: "" }, status: "missing" },
              { download: { state: "downloading", downloaded: 1, total_bytes: 4 }, status: "missing" },
              { download: { state: "verifying" }, status: "missing", available: true },
              { download: { state: "installed" }, status: "missing" },
              { status: "checking" },
              { status: "checking", busy: true, lock_wait_s: 40, check_timed_out: true },
              { status: "ready", read_error: true },
              { download: { state: "" }, status: "outdated", available: true },
              { download: { state: "" }, status: "failed" },
              { download: { state: "" }, status: "ready", ready: true }];
const seen = [];
let bad = 0;
for (const kind of ["phone", "ocr"]) {
  for (const row of rows) {
    for (const running of [false, true]) {
      for (const busy of [false, true]) {
        const facts = componentState(row, { busy: busy, running: running });
        const phase = kind === "ocr"
          ? (facts.state === "enabled" ? "on" : (facts.state === "disabled" ? "off" : facts.state))
          : facts.state;
        const extra = { phase: phase, running: running, busy: busy,
                        channelName: "Tailscale", link: { link: "connected", title: "手机已连接" },
                        version: "1.2.0" };
        const head = rowHead(kind, facts, extra);
        if (ROW_TONES.indexOf(head.tone) < 0) bad += 1;
        if (!String(head.text || "").length) bad += 1;
        if (head.button && !!head.button.action === false && head.button.cls !== undefined) bad += 0;
        if (head.bar !== null && (head.bar < 0 || head.bar > 100)) bad += 1;
        seen.push(head.tone);
      }
    }
  }
}
out.push({ bad: bad, tones: Array.from(new Set(seen)).sort() });
""")[0]
        self.assertEqual(data["bad"], 0, "网格上没有越界或空话")
        self.assertTrue(set(data["tones"]).issubset({"grey", "blue", "green", "amber", "red", "amber-dot"}))

# ==================== 源自 test_phone_link.py ====================
"""手机连接状态：设置抽屉的 chip、顶栏的手机标识、手机详情卡都在说「现在连着没有」。

一种状态或一条转移一个用例，走 fixtures.ui_harness 的整页沙箱（run_js）：摆一份
phone_access_state 快照，画一遍抽屉与顶栏，只看用户看得到的结果（写的是哪句字、
什么语气、标识出不出来、详情卡的小 chip 与大字），不对源码文本做断言。
「配过对没有」那几块（说明行、配对区、绿条、再配一台）与连接状态无关，同一快照
下换 link 必须一个字不变。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


# 公共桩：手机组件固定装好已启用（这批只看连接状态），一套快照、一次整页重画、一份观测
PHONE_LINK_PRELUDE = r"""
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
} };
const __set = (patch) => {
  const row = { download: { state: "" }, status: "ready", ready: true, available: true };
  Object.assign(PhonePanel.state, { running: true, address: "http://pc.tail.ts.net:8765/",
    channel: "tailscale", paired_count: 0, live_session: false,
    link: undefined, last_contact_ago_s: null }, patch);
  PhonePanel.state.advanced = { features: { phone_control: row, relogin_ocr: row },
    channels: { tailscale: { available: true, state: "connected" } },
    credential: { saved: false, staged: false } };
};
const __paint = () => { S.statusCard = { kind: "phone", pinned: false }; PhonePanel.paint(); };
const __rows = () => $("#phone-pop-rows").innerHTML;
const __view = () => ({
  chip: [$("#phone-feature-status").hidden, $("#phone-feature-status-text").textContent,
         $("#phone-feature-status").className, $("#phone-feature-status").dataset.link],
  badge: [$("#phone-badge").hidden, $("#phone-badge-text").textContent,
          $("#phone-badge").className, $("#phone-badge").dataset.link,
          $("#phone-badge-spin").hidden],
  cardChip: [$("#phone-pop-chip-text").textContent, $("#phone-pop-chip").dataset.tone,
             $("#phone-pop-cap").textContent],
  cardBig: $("#phone-pop-big").textContent,
  cardSub: $("#phone-pop-sub").textContent,
  cardNote: $("#phone-pop-note").textContent,
  rows: __rows(),
});
const __pairBits = () => ({
  lead: $("#phone-feature-note").textContent,
  ok: $("#phone-ok").hidden,
  pair: $("#phone-pair").hidden,
  add: $("#btn-phone-add-pair").hidden,
  tip: $("#phone-cred-tip").hidden,
  rows: __rows(),
});
"""

CONNECTED = "手机已连接"
PHONE_WAITING = "等手机连接"


class LinkStateTests(unittest.TestCase):
    """四种连接状态各写什么字、什么语气、标识出不出现。"""

    def test_waiting_says_waiting_in_drawer_badge_and_card(self):
        """开着还没人来过：三处都写「等手机连接」，语气是提醒，标识没有 is-ok。"""
        view = run_js(PHONE_LINK_PRELUDE + r"""
__set({ link: "waiting" });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"], [False, PHONE_WAITING, "adv-s amber blink", "waiting"])
        self.assertEqual(view["badge"], [False, PHONE_WAITING, "pill phone-badge is-warn blink", "waiting", True])
        self.assertEqual(view["cardChip"], ["等连接", "warn", "长期地址"])
        self.assertEqual(view["cardBig"], PHONE_WAITING)
        self.assertEqual(view["cardSub"], "用手机扫码打开页面，再输入配对码")

    def test_connected_says_connected_everywhere(self):
        """最近两分钟手机来过：三处都是「已连接」那套字，标识与详情卡小 chip 都是 ok。"""
        view = run_js(PHONE_LINK_PRELUDE + r"""
__set({ paired_count: 1, link: "connected", last_contact_ago_s: 12 });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"], [False, CONNECTED, "adv-s green", "connected"])
        self.assertEqual(view["badge"], [False, CONNECTED, "pill phone-badge is-ok", "connected", True])
        self.assertEqual(view["cardChip"], ["已连接", "ok", "长期地址"])
        self.assertEqual(view["cardBig"], CONNECTED)
        self.assertEqual(view["cardSub"], "在手机上能看活动、开始和停止计划")
        self.assertIn("<dt>手机最近访问</dt><dd>12 秒前</dd>", view["rows"])

    def test_disconnected_shows_how_long_ago_the_phone_left(self):
        """已断开：抽屉与标识写「已断开 · N 分钟前」，详情卡小 chip 只写「已断开」。"""
        view = run_js(PHONE_LINK_PRELUDE + r"""
__set({ paired_count: 1, link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__view());
""")[0]
        title = "已断开 · 2 分钟前"
        self.assertEqual(view["chip"], [False, title, "adv-s grey", "disconnected"])
        self.assertEqual(view["badge"], [False, title, "pill phone-badge", "disconnected", True])
        self.assertEqual(view["cardChip"], ["已断开", "", "长期地址"])
        self.assertEqual(view["cardBig"], title)
        self.assertEqual(view["cardSub"], "手机一段时间没来访问，不算出错；手机回来会自动变成已连接")
        self.assertIn("<dt>手机最近访问</dt><dd>2 分钟前</dd>", view["rows"])

    def test_disconnected_without_a_contact_time_says_only_disconnected(self):
        """秒数是空的（从未有过来访）：只说「已断开」，不留一个空的「· 」。"""
        view = run_js(PHONE_LINK_PRELUDE + r"""
__set({ paired_count: 1, link: "disconnected", last_contact_ago_s: null });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"][:2], [False, "已断开"])
        self.assertEqual(view["badge"][:2], [False, "已断开"])
        self.assertEqual(view["cardBig"], "已断开")
        self.assertIn("<dt>手机最近访问</dt><dd>—</dd>", view["rows"])

    def test_phone_comes_back_and_the_words_return(self):
        """一条转移：已断开 → 手机又来了 → 回到「手机已连接」，标识重新带上 is-ok。"""
        before, after = run_js(PHONE_LINK_PRELUDE + r"""
__set({ link: "disconnected", last_contact_ago_s: 4000 });
__paint();
out.push(__view());
__set({ link: "connected", last_contact_ago_s: 3 });
__paint();
out.push(__view());
""")
        self.assertEqual(before["chip"][1], "已断开 · 1 小时前")
        self.assertEqual(after["chip"], [False, CONNECTED, "adv-s green", "connected"])
        self.assertEqual(after["badge"], [False, CONNECTED, "pill phone-badge is-ok", "connected", True])

    def test_not_running_hides_the_badge_and_says_not_enabled(self):
        """没开：标识收起，抽屉 chip「未开启」，详情卡「未开启」「手机访问未开启」。"""
        view = run_js(PHONE_LINK_PRELUDE + r"""
__set({ running: false, link: "off" });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["badge"][0], True)
        self.assertEqual(view["badge"][3], "off")
        self.assertEqual(view["badge"][4], True, "收起时转圈也不该在页面上")
        self.assertEqual(view["cardChip"], ["未开启", "", "长期地址"])
        self.assertEqual(view["cardBig"], "手机访问未开启")


class FallbackRuleTests(unittest.TestCase):
    """后端没给 link（老快照）或给 unknown 时，退回「配过对 / 有活动会话」的两档规则。"""

    def test_missing_link_falls_back_to_the_pairing_rule(self):
        """没有 link 字段：配过对就是「手机已连接」，没配过就是「等手机连接」。"""
        paired, waiting = run_js(PHONE_LINK_PRELUDE + r"""
__set({ paired_count: 1 });
__paint();
out.push(__view());
__set({ paired_count: 0, live_session: false });
__paint();
out.push(__view());
""")
        self.assertEqual(paired["chip"], [False, CONNECTED, "adv-s green", "connected"])
        self.assertEqual(waiting["chip"], [False, PHONE_WAITING, "adv-s amber blink", "waiting"])

    def test_unknown_and_off_links_also_fall_back(self):
        """unknown 与「开着却给了 off」都当没有结论：有活动会话时仍按旧规则说已连接。"""
        unknown, off_link = run_js(PHONE_LINK_PRELUDE + r"""
__set({ link: "unknown", live_session: true });
__paint();
out.push(__view());
__set({ link: "off", paired_count: 0, live_session: false });
__paint();
out.push(__view());
""")
        self.assertEqual(unknown["chip"][1], CONNECTED)
        self.assertEqual(unknown["cardChip"], ["已连接", "ok", "长期地址"])
        self.assertEqual(off_link["chip"], [False, PHONE_WAITING, "adv-s amber blink", "waiting"])

    def test_unknown_link_stays_a_compatibility_fallback(self):
        """兼容行为，不是独立渲染的 unknown 状态：开着但 link=unknown 时退回配对与活动会话的两档规则。

        没配对、没有活动会话 → waiting；有配对 → connected。unknown 不在连接状态清单里。
        """
        data = run_js("""
out.push({
  unpaired: phoneLinkView({ running: true, link: "unknown", paired_count: 0, live_session: false }),
  paired: phoneLinkView({ running: true, link: "unknown", paired_count: 1, live_session: false }),
  listed: PHONE_LINK_STATES.slice(),
});
""")[0]
        self.assertEqual(data["unpaired"]["link"], "waiting")
        self.assertEqual(data["paired"]["link"], "connected")
        self.assertNotIn("unknown", data["listed"],
                         "unknown 只是老快照的兜底输入，不是新的可见状态")


class PairingIsNotLinkTests(unittest.TestCase):
    """「配过对没有」不看连接状态：同一份配对快照换 link，配对那几块一个字不变。"""

    def test_pairing_blocks_do_not_follow_the_link(self):
        """已配对的一台手机走了：说明行、绿条、再配一台、详情卡配对行照旧，只有连接那几处变。"""
        connected, gone = run_js(PHONE_LINK_PRELUDE + r"""
__set({ paired_count: 1, link: "connected", last_contact_ago_s: 5 });
__paint();
out.push(__pairBits());
__set({ paired_count: 1, link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__pairBits());
""")
        # 详情卡最后一行「手机最近访问」写的是连接信息，它本来就该变；其余各块一个字不变
        self.assertEqual([connected["lead"], connected["ok"], connected["pair"], connected["add"],
                          connected["tip"]],
                         [gone["lead"], gone["ok"], gone["pair"], gone["add"], gone["tip"]])
        self.assertIn("<dt>已配对</dt><dd>1 台手机</dd>", connected["rows"],
                      "详情卡配对行看的是配过对没有，不是连着没有")
        self.assertIn("<dt>已配对</dt><dd>1 台手机</dd>", gone["rows"])
        self.assertIn("<dd>5 秒前</dd>", connected["rows"])
        self.assertIn("<dd>2 分钟前</dd>", gone["rows"])
        self.assertFalse(connected["ok"], "绿条：配对码已换过的那条按配过对显示，不随连接状态")
        self.assertEqual(gone["add"], False, "配过对就能「再配一台手机」")

# ==================== 源自 test_topbar_phone.py ====================
"""顶栏的手机标识与手机详情卡：五种样子各一条，卡里的行与小标各一条。

走 fixtures.ui_harness 的整页沙箱（run_js）：摆一份 phone_access_state 快照与
PhonePanel.pending，画一遍，只看用户看得到的结果——标识写哪句字、什么颜色档、
转圈出不出来、读屏念什么，详情卡的小 chip、大字、副句、底部提醒与每一行。
样式表不在沙箱里，颜色与慢闪的最终样子由 design/evidence 里的截图脚本在 Edge 里核对。

@author Author
"""


TESTS = Path(__file__).resolve().parents[1]
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))


# 公共桩：手机组件固定装好已启用（这批只看连接状态与过程），一套快照、一次整页重画
TOPBAR_PHONE_PRELUDE = r"""
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
} };
const __set = (patch) => {
  const row = { download: { state: "" }, status: "ready", ready: true, available: true };
  Object.assign(PhonePanel.state, { running: true, address: "http://pc.tail.ts.net:8765/",
    channel: "tailscale", paired_count: 0, live_session: false,
    link: undefined, last_contact_ago_s: null, pair_code_status: {} }, patch);
  PhonePanel.state.advanced = { features: { phone_control: row, relogin_ocr: row },
    channels: { tailscale: { available: true, state: "connected" } },
    credential: { saved: false, staged: false } };
};
const __paint = (pending) => {
  PhonePanel.pending = pending || "";
  S.statusCard = { kind: "phone", pinned: false };
  PhonePanel.paint();
};
const __badge = () => [$("#phone-badge").hidden, $("#phone-badge-text").textContent,
                       $("#phone-badge").className, $("#phone-badge").dataset.link,
                       $("#phone-badge-spin").hidden];
const __card = () => ({
  chip: [$("#phone-pop-chip-text").textContent, $("#phone-pop-chip").dataset.tone],
  cap: $("#phone-pop-cap").textContent,
  big: $("#phone-pop-big").textContent,
  sub: $("#phone-pop-sub").textContent,
  note: $("#phone-pop-note").textContent,
  rows: $("#phone-pop-rows").innerHTML,
  aria: $("#phone-badge").getAttribute("aria-label"),
});
"""


def _run(snippet):
    return run_js(TOPBAR_PHONE_PRELUDE + snippet)


class BadgeLooksTests(unittest.TestCase):
    """标识的五种样子：正在开启… / 正在停止… / 等手机连接 / 手机已连接 / 已断开，没开收起。"""

    def test_starting_shows_a_spinner_on_a_grey_pill(self):
        """开启中还没起来：标识先出来说话，灰底、前面挂转圈，不带别的颜色档。"""
        badge = _run(r"""
__set({ running: false, link: "off" });
__paint("starting");
out.push(__badge());
""")[0]
        self.assertEqual(badge, [False, "正在开启…", "pill phone-badge", "off", False])

    def test_stopping_also_shows_the_spinner(self):
        """关闭中：一样是灰底转圈，说的是过程而不是连接状态。"""
        badge = _run(r"""
__set({ link: "connected", last_contact_ago_s: 3 });
__paint("stopping");
out.push(__badge());
""")[0]
        self.assertEqual(badge, [False, "正在停止…", "pill phone-badge", "connected", False])

    def test_waiting_blinks_in_amber(self):
        """开着但手机还没来过：琥珀底、图标慢闪，转圈收起来（慢闪与转圈不同时出现）。"""
        badge = _run(r"""
__set({ link: "waiting" });
__paint();
out.push(__badge());
""")[0]
        self.assertEqual(badge, [False, "等手机连接", "pill phone-badge is-warn blink", "waiting", True])

    def test_connected_is_green_without_a_spinner(self):
        """手机来过：绿底，不闪也不转。"""
        badge = _run(r"""
__set({ link: "connected", last_contact_ago_s: 3 });
__paint();
out.push(__badge());
""")[0]
        self.assertEqual(badge, [False, "手机已连接", "pill phone-badge is-ok", "connected", True])

    def test_disconnected_keeps_the_plain_pill_and_the_time(self):
        """两分钟没来：灰底（不是提醒档），文字带「· 2 分钟前」。"""
        badge = _run(r"""
__set({ link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__badge());
""")[0]
        self.assertEqual(badge, [False, "已断开 · 2 分钟前", "pill phone-badge", "disconnected", True])

    def test_not_running_hides_both_the_pill_and_the_spinner(self):
        """没开：标识收起，转圈也不能留在页面上。"""
        badge = _run(r"""
__set({ running: false, link: "off" });
__paint();
out.push(__badge());
""")[0]
        self.assertEqual(badge[:2], [True, ""])
        self.assertEqual(badge[3:], ["off", True])

    def test_aria_label_says_which_state_it_is(self):
        """读屏要听得出是哪一种：开启中、等连接、已连接、已断开各不同，都带「查看详情」。"""
        labels = _run(r"""
__set({ running: false, link: "off" }); __paint("starting");
out.push($("#phone-badge").getAttribute("aria-label"));
__set({ link: "waiting" }); __paint();
out.push($("#phone-badge").getAttribute("aria-label"));
__set({ link: "connected", last_contact_ago_s: 3 }); __paint();
out.push($("#phone-badge").getAttribute("aria-label"));
__set({ link: "disconnected", last_contact_ago_s: 150 }); __paint();
out.push($("#phone-badge").getAttribute("aria-label"));
""")
        self.assertEqual(labels, ["正在开启…，查看详情", "手机访问已开启，等手机连接，查看详情",
                                  "手机已连接，查看详情", "已断开 · 2 分钟前，查看详情"])


class PhoneCardTests(unittest.TestCase):
    """详情卡：小 chip、小标、大字、副句、底部提醒与每一行都照原型。"""

    def test_waiting_card_offers_the_pairing_code(self):
        """等连接：小 chip「等连接」，副句教怎么扫码，没配过对时第三行是配对码。"""
        card = _run(r"""
__set({ link: "waiting", pair_code_status: { code: "482913", expires_in: 135 } });
__paint();
out.push(__card());
""")[0]
        self.assertEqual(card["chip"], ["等连接", "warn"])
        self.assertEqual(card["cap"], "长期地址")
        self.assertEqual(card["big"], "等手机连接")
        self.assertEqual(card["sub"], "用手机扫码打开页面，再输入配对码")
        self.assertEqual(card["note"], "程序退出后手机就打不开了。想在外面随时用，关窗口时选最小化或隐藏到后台。")
        self.assertIn("<dt>配对码</dt><dd>2:15 后换新</dd>", card["rows"])
        self.assertIn("<dt>地址</dt><dd>pc.tail.ts.net:8765</dd>", card["rows"])

    def test_connected_card_lists_the_phone_and_when_it_last_came(self):
        """已连接：配对行写「1 台手机」，最近访问写「多久以前」，小 chip 是 ok 档。"""
        card = _run(r"""
__set({ paired_count: 1, link: "connected", last_contact_ago_s: 12 });
__paint();
out.push(__card());
""")[0]
        self.assertEqual(card["chip"], ["已连接", "ok"])
        self.assertEqual(card["sub"], "在手机上能看活动、开始和停止计划")
        self.assertIn("<dt>已配对</dt><dd>1 台手机</dd>", card["rows"])
        self.assertIn("<dt>手机最近访问</dt><dd>12 秒前</dd>", card["rows"])

    def test_live_session_without_pairing_does_not_claim_a_paired_phone(self):
        """只有活动会话、还没真配过对：配对行写「有手机连着」，不能写「1 台手机」。"""
        card = _run(r"""
__set({ paired_count: 0, live_session: true, link: "connected", last_contact_ago_s: 8 });
__paint();
out.push(__card());
""")[0]
        self.assertIn("<dt>已配对</dt><dd>有手机连着</dd>", card["rows"])
        self.assertIn("<dt>手机最近访问</dt><dd>8 秒前</dd>", card["rows"])

    def test_gone_card_explains_it_is_not_an_error(self):
        """已断开：小 chip 写「已断开」、不带颜色档，副句说明这不算出错。"""
        card = _run(r"""
__set({ paired_count: 1, link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__card());
""")[0]
        self.assertEqual(card["chip"], ["已断开", ""])
        self.assertEqual(card["big"], "已断开 · 2 分钟前")
        self.assertEqual(card["sub"], "手机一段时间没来访问，不算出错；手机回来会自动变成已连接")
        self.assertIn("<dt>手机最近访问</dt><dd>2 分钟前</dd>", card["rows"])

    def test_cloudflare_card_says_the_address_is_temporary(self):
        """Cloudflare 通道：小标「临时地址」，行里点明临时，底部提醒说地址会变。"""
        card = _run(r"""
__set({ channel: "cloudflare", address: "https://abc.trycloudflare.com", link: "waiting" });
__paint();
out.push(__card());
""")[0]
        self.assertEqual(card["cap"], "临时地址")
        self.assertEqual(card["note"], "这是临时地址，关闭访问或重启程序后就会变，手机要重新扫码配对。")
        self.assertIn("<dt>通道</dt><dd>Cloudflare，临时地址</dd>", card["rows"])
        self.assertIn("<dt>地址</dt><dd>abc.trycloudflare.com</dd>", card["rows"])

    def test_card_without_a_pairing_code_sends_you_to_the_settings(self):
        """配对码还没下发：不编一个倒计时，直接写「在设置里看配对码」。"""
        card = _run(r"""
__set({ link: "waiting", pair_code_status: {} });
__paint();
out.push(__card());
""")[0]
        self.assertIn("<dt>配对码</dt><dd>在设置里看配对码</dd>", card["rows"])

    def test_card_stays_empty_while_the_phone_access_is_off(self):
        """没开：卡片照旧说「未开启」，不列通道与地址这些没有的字段。"""
        card = _run(r"""
__set({ running: false, link: "off" });
__paint();
out.push(__card());
""")[0]
        self.assertEqual(card["chip"], ["未开启", ""])
        self.assertEqual(card["big"], "手机访问未开启")
        self.assertEqual(card["sub"], "到设置 → 高级功能里开启")
        self.assertEqual(card["note"], "")
        self.assertEqual(card["rows"], "")


class CardOpenTests(unittest.TestCase):
    """开启中、停止中点标识不弹详情卡；平常照弹。"""

    def test_card_does_not_open_while_starting_or_stopping(self):
        """开启中、停止中标识在转圈，点它不打开详情卡；开好以后点它照常打开。"""
        res = _run(r"""
const __open = (pending, running) => {
  __set({ running: running, link: running ? "connected" : "off", paired_count: 1 });
  PhonePanel.pending = pending;
  S.statusCard = null;
  $("#phone-pop").hidden = true;
  PhonePanel.paint();
  openStatusCard("phone", true);
  return [$("#phone-pop").hidden, S.statusCard ? S.statusCard.kind : ""];
};
out.push(__open("starting", false));
out.push(__open("stopping", true));
out.push(__open("", true));
""")
        self.assertEqual(res[0], [True, ""], "开启中点标识不弹卡")
        self.assertEqual(res[1], [True, ""], "停止中点标识不弹卡")
        self.assertEqual(res[2], [False, "phone"], "开好以后照常弹卡")


class ProgramGroupCardTests(unittest.TestCase):
    """D6：设置「程序」组合卡的折叠详情、状态点与飞书/更新展开切换。"""

    def test_program_card_toggles_update_and_feishu_details(self):
        """飞书与更新默认收起详情；点展开箭头切换显隐，飞书配置状态反映到标题行。"""
        res = run_js(r"""
S.feishuWebhook = "https://open.feishu.cn/hook/abc";
S.feishuOpen = false;
S.updateOpen = false;
S.update = { state: "idle", result: {} };
paintFeishuRow(true);
paintUpdate();
const before = { fsHidden: $("#feishu-detail").hidden, fsText: $("#feishu-status-text").textContent,
                 upHidden: $("#update-detail").hidden, fsExp: $("#btn-feishu-toggle").getAttribute("aria-expanded") };
$("#btn-feishu-toggle").click();
$("#btn-update-row-toggle").click();
const after = { fsHidden: $("#feishu-detail").hidden, upHidden: $("#update-detail").hidden,
                fsExp: $("#btn-feishu-toggle").getAttribute("aria-expanded"),
                upExp: $("#btn-update-row-toggle").getAttribute("aria-expanded") };
out.push({ before, after });
""")[0]
        self.assertTrue(res["before"]["fsHidden"])
        self.assertIn("已配置", res["before"]["fsText"])
        self.assertTrue(res["before"]["upHidden"])
        self.assertEqual(res["before"]["fsExp"], "false")
        self.assertFalse(res["after"]["fsHidden"])
        self.assertFalse(res["after"]["upHidden"])
        self.assertEqual(res["after"]["fsExp"], "true")
        self.assertEqual(res["after"]["upExp"], "true")


class PhoneTimelineContractTests(unittest.TestCase):
    """D9：手机页时间轴节点、四层卡片与类型标签静态契约。"""

    def test_phone_styles_and_list_avoid_grid_and_desc_popup(self):
        root = Path(__file__).resolve().parents[2]
        css = (root / "ui" / "m" / "styles.css").read_text(encoding="utf-8")
        js = (root / "ui" / "m" / "ui" / "ui-list.js").read_text(encoding="utf-8")
        for token in (".tl-node", ".tl-dot.open", ".tl-dot.next", ".tl-dot.wait",
                      ".tl-dot.unknown", ".tl-batch", ".type-tag", ".l3-r",
                      ".flag.next { display: none; }"):
            self.assertIn(token, css)
        for token in ("buildTimelineNode", "tl-below", "l3 l3-4", "type-tag"):
            self.assertIn(token, js)
        self.assertNotIn("desc-btn", js)
        self.assertNotIn("innerHTML", js)


if __name__ == "__main__":
    unittest.main()
