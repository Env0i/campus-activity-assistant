#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两个组件行共用的纯函数状态机：componentState 逐状态断言与两个认阶段适配的映射。

全部走 fixtures.ui_harness 的整页沙箱（run_js）：加载真实模块图，在沙箱里调
componentState、phonePhase、ocrPhase，断言状态与派生事实；不开浏览器、不发请求。

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


if __name__ == "__main__":
    unittest.main()
