#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 1 出口行为测试·组件一组（计划 20261113-refactor-step1-exit-tests）。

每个 test_ 守 D2 变异表里的一个出口（编号见用例名）：在 node 沙箱里按
index.html 的加载序跑真实界面脚本、触发动作、看用户看得到的结果（按钮恢复可点、
就地提示句），再断言状态值；不对源码文本做断言。
变异验证（未变异通过 / 对应变异变红）见 design/evidence/2026-11-13/exit-path-tests/。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 公共桩：组件状态快照（未开启、Tailscale 可用）、位置接口不返、微任务推进
PRELUDE = r"""
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false,
    advanced: { channels: { tailscale: { available: true } } } }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
} };
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
"""


class PanelBusyExitTests(unittest.TestCase):
    """组件·面板请求在途（PhonePanel.busy）的四条出口：动作结束后按钮要恢复可点。"""

    def test_C01_enable_feature_releases_the_busy_lock(self):
        """组件·面板请求在途：启用手机控制的请求回来——标题行按钮恢复可点，
        并就地说明「已启用」。"""
        res = run_js(PRELUDE + r"""
PhonePanel.state.feature = { ready: false, available: true };
window.pywebview.api.enable_advanced_feature = () => Promise.resolve({ ok: true });
await PhonePanel.enableFeature();
out.push({ busy: PhonePanel.busy, btnDisabled: $("#btn-phone-feature-install").disabled,
           note: PhonePanel.notes.off });
""")
        data = res[0]
        self.assertFalse(data["btnDisabled"], "请求回来后按钮要恢复可点")
        self.assertEqual(data["note"], "手机控制已启用，选一条通道就能开启。")
        self.assertFalse(data["busy"], "忙碌位要清掉")

    def test_C02_toggle_start_releases_the_busy_lock(self):
        """组件·面板请求在途：开启手机访问的请求回来——「开启手机访问」按钮恢复可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
    channels: { tailscale: { available: true } } };
window.PhonePanel.paint();
window.pywebview.api.start_phone_access = () => Promise.resolve({ ok: true });
await PhonePanel.toggleStart();
out.push({ busy: PhonePanel.busy,
           startDisabled: $("#btn-phone-start").hidden ? "hidden" : $("#btn-phone-start").disabled,
           startText: $("#btn-phone-start").textContent });
""")
        data = res[0]
        self.assertFalse(data["busy"], "忙碌位要清掉")
        self.assertEqual(data["startText"], "开启")
        self.assertFalse(data["busy"])

    def test_C03_toggle_stop_releases_the_busy_lock(self):
        """组件·面板请求在途：关闭手机访问的请求回来——「关闭手机访问」按钮恢复可点。"""
        res = run_js(PRELUDE + r"""
PhonePanel.state.running = true;
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
    channels: { tailscale: { available: true } } };
window.PhonePanel.paint();
window.pywebview.api.stop_phone_access = () => Promise.resolve({ ok: true });
await PhonePanel.toggleStop();
out.push({ busy: PhonePanel.busy,
           stopDisabled: $("#btn-phone-stop").hidden ? "hidden" : $("#btn-phone-stop").disabled,
           stopText: $("#btn-phone-stop").textContent });
""")
        data = res[0]
        self.assertFalse(data["busy"], "忙碌位要清掉")
        self.assertEqual(data["stopText"], "关闭手机访问")
        self.assertFalse(data["busy"])

    def test_C04_download_component_releases_the_busy_lock(self):
        """组件·面板请求在途：下载组件的请求回来（无论成败）——标题行按钮恢复可点。"""
        res = run_js(PRELUDE + r"""
window.pywebview.api.download_advanced_feature = () => Promise.resolve({ ok: true });
await PhonePanel.downloadComponent("phone_control");
out.push({ busy: PhonePanel.busy,
           btnDisabled: $("#btn-phone-feature-install").disabled });
""")
        data = res[0]
        self.assertFalse(data["btnDisabled"], "下载请求回来后按钮要恢复可点")
        self.assertFalse(data["busy"])


class PendingExitTests(unittest.TestCase):
    """组件·手机访问开启中或停止中（PhonePanel.pending）的两条出口。"""

    def test_C06_toggle_start_clears_the_starting_pending(self):
        """组件·手机访问开启中：开启请求回来——标题行离开「正在开启…」回到「未开启」那一档。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
    channels: { tailscale: { available: true } } };
window.PhonePanel.paint();
window.pywebview.api.phone_access_state = () => Promise.resolve({ ok: true, running: false,
    advanced: { features: { phone_control: { ready: true } },
      channels: { tailscale: { available: true } } } });
window.pywebview.api.start_phone_access = () => Promise.resolve({ ok: true });
await PhonePanel.toggleStart();
out.push({ pending: PhonePanel.pending,
           startHidden: $("#btn-phone-start").hidden,
           startText: $("#btn-phone-start").textContent,
           chip: $("#phone-feature-status-text").textContent });
""")
        data = res[0]
        self.assertEqual(data["pending"], "", "开启中标记要清掉")
        self.assertFalse(data["startHidden"], "请求回来后按钮位要重新亮起来")
        self.assertEqual(data["startText"], "开启", "按钮不能停在启动中")
        self.assertNotEqual(data["chip"], "正在开启…", "状态句不能停在正在开启")

    def test_C07_toggle_stop_clears_the_stopping_pending(self):
        """组件·手机访问停止中：关闭请求回来——标题行离开「正在停止…」回到已连接那一档。"""
        res = run_js(PRELUDE + r"""
PhonePanel.state.running = true;
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
    channels: { tailscale: { available: true } } };
window.PhonePanel.paint();
window.pywebview.api.phone_access_state = () => Promise.resolve({ ok: true, running: false,
    advanced: { features: { phone_control: { ready: true } },
      channels: { tailscale: { available: true } } } });
window.pywebview.api.stop_phone_access = () => Promise.resolve({ ok: true });
await PhonePanel.toggleStop();
out.push({ pending: PhonePanel.pending,
           startHidden: $("#btn-phone-start").hidden,
           startText: $("#btn-phone-start").textContent,
           chip: $("#phone-feature-status-text").textContent });
""")
        data = res[0]
        self.assertEqual(data["pending"], "", "停止中标记要清掉")
        self.assertFalse(data["startHidden"], "关闭之后按钮位换回「开启」")
        self.assertEqual(data["startText"], "开启")
        self.assertNotEqual(data["chip"], "正在停止…", "状态句不能停在正在停止")


class OcrBusyExitTests(unittest.TestCase):
    """组件·验证码识别面板请求在途（OcrPanel.busy）的出口。"""

    def test_C09_enable_ocr_releases_the_busy_lock(self):
        """组件·验证码识别面板请求在途：启用请求回来——「启用」按钮恢复可点，
        并就地说明「已启用」。"""
        res = run_js(PRELUDE + r"""
PhonePanel.state.advanced = { features: { relogin_ocr: { ready: true } },
  channels: { tailscale: { available: true } } };
window.pywebview.api.enable_advanced_feature = () => Promise.resolve({ ok: true });
await enableOcr();
paintSettings();
out.push({ busy: OcrPanel.busy, enableDisabled: $("#btn-ocr-enable").disabled,
           note: OcrPanel.note });
""")
        data = res[0]
        self.assertFalse(data["enableDisabled"], "启用请求回来后按钮要恢复可点")
        self.assertEqual(data["note"], "验证码识别已启用。")
        self.assertFalse(data["busy"], "忙碌位要清掉")


if __name__ == "__main__":
    unittest.main()
