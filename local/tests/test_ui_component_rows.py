#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件与手机访问动手之前补的安全网·组件安装路径与验证码识别一组。

每个 test_ 守一张变异表里的一行，或守一个必有的界面场景，或把契约里只查
源码文字的一条改成跑 node 的行为用例：给后端状态、触发动作或重画、看用户
看得到的结果（进度区的字、状态字、按钮是否禁用、弹窗开不开），再断言内部值；
不对源码文本做断言。变异验证（未变异通过 / 对应变异变红、第一条失败断言是
用户看得到的那条）见 design/evidence/2026-11-14/components-net/。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 公共桩：手机访问快照（未开启、Tailscale 可用）、位置接口不返、
# 组件包自检通过（给一个固定版本号）、微任务推进
PRELUDE = r"""
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false,
    advanced: { channels: { tailscale: { available: true } } } }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
  inspect_advanced_component: () => Promise.resolve({ ok: true, version: "9.9" }),
} };
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
"""


class OcrPanelBusyReadTests(unittest.TestCase):
    """读进行中标志·验证码识别面板：忙碌时本节按钮要按住。"""

    def test_ocr_busy_read_disables_the_ocr_buttons(self):
        """验证码识别：识别面板自己的忙碌位亮着时，「启用」与「下载并安装」都要禁用。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: { available: true } } };
OcrPanel.busy = true;
paintOcrDownload();
out.push({ enableDisabled: $("#btn-ocr-enable").disabled,
           downloadDisabled: $("#btn-ocr-download").disabled,
           enableHidden: $("#btn-ocr-enable").hidden });
""")
        data = res[0]
        self.assertFalse(data["enableHidden"], "已装没启用时「启用」按钮要看得见")
        self.assertTrue(data["enableDisabled"], "面板忙碌时启用按钮要禁用")
        self.assertTrue(data["downloadDisabled"], "面板忙碌时下载按钮要禁用")

    def test_busy_guard_in_enable_ocr_sends_nothing(self):
        """验证码识别·启用：面板忙碌时再点「启用」，不发 enable_advanced_feature。"""
        res = run_js(PRELUDE + r"""
window.__ocrCalls = 0;
window.pywebview.api.enable_advanced_feature = () => {
  window.__ocrCalls += 1; return Promise.resolve({ ok: true }); };
OcrPanel.busy = true;
await enableOcr();
out.push({ ocrCalls: window.__ocrCalls });
""")
        self.assertEqual(res[0]["ocrCalls"], 0, "忙碌时再点启用不能再发请求")


class OcrButtonUsePointTests(unittest.TestCase):
    """使用点·验证码识别一节的三处按钮与红条：忙时要按住，安装中不翻旧账。"""

    def test_busy_read_disables_the_ocr_cancel_button(self):
        """验证码识别·下载中：标题行「取消下载」看得见，面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: {
  download: { state: "downloading", downloaded: 3145728, total_bytes: 9437184 } } } };
OcrPanel.busy = true;
window.PhonePanel.paint();
out.push({ loadingShown: !$("#ocr-loading").hidden,
           cancelHidden: $("#btn-ocr-cancel").hidden,
           cancelText: $("#btn-ocr-cancel").textContent,
           disabledBusy: $("#btn-ocr-cancel").disabled });
OcrPanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-ocr-cancel").disabled });
""")
        busy, free = res
        self.assertTrue(busy["loadingShown"], "下载中进度块要显示")
        self.assertFalse(busy["cancelHidden"], "下载中标题行「取消下载」要看得见")
        self.assertEqual(busy["cancelText"], "取消下载")
        self.assertTrue(busy["disabledBusy"], "面板忙时取消按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_installing_keeps_the_old_ocr_error_hidden(self):
        """验证码识别·安装中：之前留下的失败红条要收着，进度块照常显示；
        安装标志放下后同一条红条才出现——不能让旧失败吓住正在进行的安装。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: {} } };
OcrPanel.error = "下载没有完成：连不上发布页，可以重试。";
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ loadingShown: !$("#ocr-loading").hidden,
           errText: $("#ocr-download-error").textContent,
           errHidden: $("#ocr-download-error").hidden });
window.PhonePanel.installing.relogin_ocr = false;
window.PhonePanel.paint();
out.push({ errTextWhenFree: $("#ocr-download-error").textContent,
           errHiddenWhenFree: $("#ocr-download-error").hidden });
""")
        data = res[0]
        self.assertTrue(data["loadingShown"], "安装中进度块要显示")
        self.assertEqual(data["errText"], "", "安装中不显示旧的失败红条")
        self.assertTrue(data["errHidden"], "安装中红条要收起")
        self.assertEqual(res[1]["errTextWhenFree"], "下载没有完成：连不上发布页，可以重试。",
                         "安装标志放下后旧失败要重新可见")
        self.assertFalse(res[1]["errHiddenWhenFree"])

    def test_busy_read_disables_the_ocr_open_location_button(self):
        """验证码识别·已装未启用：「打开所在文件夹」看得见，面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: { available: true } } };
OcrPanel.location = { path: "组件目录", short: "组件目录" };
OcrPanel.busy = true;
window.PhonePanel.paint();
out.push({ locShown: !$("#ocr-loc-after").hidden,
           btnHidden: $("#btn-ocr-open-loc").hidden,
           disabledBusy: $("#btn-ocr-open-loc").disabled });
OcrPanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-ocr-open-loc").disabled });
""")
        busy, free = res
        self.assertTrue(busy["locShown"], "「装在」那一行要看得见")
        self.assertFalse(busy["btnHidden"], "「打开所在文件夹」要看得见")
        self.assertTrue(busy["disabledBusy"], "面板忙时打开位置按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_loading_hides_the_ocr_installed_location_row(self):
        """验证码识别·下载中：「装在」那一行要收起（还没装，不该说「装在」）；
        已装未启用时同一行要显示。"""
        res = run_js(PRELUDE + r"""
OcrPanel.location = { path: "组件目录", short: "组件目录" };
window.PhonePanel.state.advanced = { features: { relogin_ocr: {
  download: { state: "downloading", downloaded: 1048576, total_bytes: 10485760 } } } };
window.PhonePanel.paint();
out.push({ locAfterHiddenWhileLoading: $("#ocr-loc-after").hidden,
           loadingShown: !$("#ocr-loading").hidden });
window.PhonePanel.state.advanced = { features: { relogin_ocr: { available: true } } };
window.PhonePanel.paint();
out.push({ locAfterShownWhenOff: !$("#ocr-loc-after").hidden });
""")
        data = res[0]
        self.assertTrue(data["locAfterHiddenWhileLoading"], "下载中「装在」行要收起")
        self.assertTrue(data["loadingShown"], "下载中进度块要显示")
        self.assertTrue(res[1]["locAfterShownWhenOff"], "已装未启用时「装在」行要显示")


class InstallingRowTests(unittest.TestCase):
    """读进行中标志·安装路径与三个必有的界面场景。"""

    def test_phone_downloads_while_ocr_installs_rows_do_not_mix(self):
        """两个组件：手机控制在下载、验证码识别在安装——两行各显示各的进度字，互不串。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { download: { state: "downloading",
    downloaded: 5242880, total_bytes: 10485760 } },
  relogin_ocr: { ready: true } } };
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneProg: $("#phone-prog-text").textContent,
           phoneLoadingHidden: $("#phone-loading").hidden,
           ocrProg: $("#ocr-prog-text").textContent,
           ocrLoadingHidden: $("#ocr-loading").hidden });
""")
        data = res[0]
        self.assertEqual(data["phoneProg"], "正在下载手机控制组件", "手机控制行说自己在下载")
        self.assertEqual(data["ocrProg"], "正在安装组件…", "验证码识别行说自己在安装")
        self.assertFalse(data["phoneLoadingHidden"], "手机控制的进度块要显示")
        self.assertFalse(data["ocrLoadingHidden"], "验证码识别的进度块要显示")

    def test_each_component_shows_its_own_installing_row(self):
        """两个组件各自「正在安装」：两行的进度区都说「正在安装组件…」，不再当没装。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { ready: true }, relogin_ocr: { ready: true } } };
window.PhonePanel.installing.phone_control = true;
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneProg: $("#phone-prog-text").textContent,
           ocrProg: $("#ocr-prog-text").textContent,
           phoneMissingHidden: $("#phone-missing").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden });
""")
        data = res[0]
        self.assertEqual(data["phoneProg"], "正在安装组件…", "手机控制行要说正在安装")
        self.assertEqual(data["ocrProg"], "正在安装组件…", "验证码识别行要说正在安装")
        self.assertTrue(data["phoneMissingHidden"], "安装中不能显示成没装")
        self.assertTrue(data["ocrMissingHidden"], "安装中不能显示成没装")

    def test_each_component_installs_from_missing_without_showing_missing_blocks(self):
        """两个组件·从「没装」出发的安装中：「没装」块都不显示（安装中不能当没装），
        进度区都说「正在安装组件…」并显示，标题行主按钮禁用。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: {}, relogin_ocr: {} } };
window.PhonePanel.installing.phone_control = true;
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneMissingHidden: $("#phone-missing").hidden,
           phoneInstallHidden: $("#btn-phone-component-install").hidden,
           phoneInstallDisabled: $("#btn-phone-component-install").disabled,
           phoneProg: $("#phone-prog-text").textContent,
           phoneLoadingShown: !$("#phone-loading").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden,
           ocrDownloadHidden: $("#btn-ocr-download").hidden,
           ocrDownloadDisabled: $("#btn-ocr-download").disabled,
           ocrProg: $("#ocr-prog-text").textContent,
           ocrLoadingShown: !$("#ocr-loading").hidden });
""")
        data = res[0]
        self.assertTrue(data["phoneMissingHidden"], "安装中的手机控制不能显示成没装")
        self.assertFalse(data["phoneInstallHidden"], "没装时标题行主按钮要看得见")
        self.assertTrue(data["phoneInstallDisabled"], "安装中主按钮要禁用")
        self.assertEqual(data["phoneProg"], "正在安装组件…", "手机控制行要说正在安装")
        self.assertTrue(data["phoneLoadingShown"], "手机控制的进度块要显示")
        self.assertTrue(data["ocrMissingHidden"], "安装中的验证码识别不能显示成没装")
        self.assertFalse(data["ocrDownloadHidden"], "没装时「下载并安装」要看得见")
        self.assertTrue(data["ocrDownloadDisabled"], "安装中「下载并安装」要禁用")
        self.assertEqual(data["ocrProg"], "正在安装组件…", "验证码识别行要说正在安装")
        self.assertTrue(data["ocrLoadingShown"], "验证码识别的进度块要显示")

    def test_checking_state_is_not_missing_on_both_rows(self):
        """后端给「检查中」（组件事务锁被占）时，两行都不显示成「没装」，
        进度区都说「正在检查组件…」且进度块要显示——检查中不是空闲，块不能收起。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { status: "checking", available: true },
  relogin_ocr: { status: "checking", available: true } } };
window.PhonePanel.paint();
out.push({ phoneMissingHidden: $("#phone-missing").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden,
           phoneLoadingHidden: $("#phone-loading").hidden,
           ocrLoadingHidden: $("#ocr-loading").hidden,
           phoneProg: $("#phone-prog-text").textContent,
           ocrProg: $("#ocr-prog-text").textContent });
""")
        data = res[0]
        self.assertTrue(data["phoneMissingHidden"], "检查中的手机控制不能显示成没装")
        self.assertTrue(data["ocrMissingHidden"], "检查中的验证码识别不能显示成没装")
        self.assertFalse(data["phoneLoadingHidden"], "检查中的手机控制进度块要显示")
        self.assertFalse(data["ocrLoadingHidden"], "检查中的验证码识别进度块要显示")
        self.assertEqual(data["phoneProg"], "正在检查组件…", "手机控制行要说正在检查")
        self.assertEqual(data["ocrProg"], "正在检查组件…", "验证码识别行要说正在检查")


class DialogContractBehaviorTests(unittest.TestCase):
    """导入弹窗：安装按钮先过自检才可点；标题行的导入入口只开弹窗不安装。"""

    def test_dialog_install_button_stays_disabled_until_a_file_passes(self):
        """导入弹窗·手机控制：没选文件时「安装这份」不可点；自检通过后才可点，
        结论行说识别出了什么。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.openComponents("phone_control");
out.push({ title: $("#dlg-components-title").textContent,
           disabled: $("#btn-comp-phone-install").disabled });
await PhonePanel.inspectComponent("phone_control", "phone_control-9.9.zip");
out.push({ disabledAfter: $("#btn-comp-phone-install").disabled,
           note: $("#comp-phone-note").textContent });
""")
        first, second = res
        self.assertEqual(first["title"], "导入手机控制组件", "弹窗要说清在导入哪个组件")
        self.assertTrue(first["disabled"], "没选文件时安装按钮要禁用")
        self.assertFalse(second["disabledAfter"], "自检通过后安装按钮要可点")
        self.assertEqual(second["note"], "已识别为「手机控制」组件包，版本 9.9。",
                         "结论行要说识别出了什么")

    def test_feature_action_import_opens_the_dialog_without_installing(self):
        """手机控制·缺组件包：标题行「安装/更换组件包」点了只开弹窗，不调安装接口。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = {
  features: { phone_control: { ready: true } },
  channels: { cloudflare: { error: "cloudflared_missing" } } };
window.__installCalls = 0;
window.pywebview.api.install_advanced_feature = () => {
  window.__installCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.paint();
const btn = $("#btn-phone-feature-install");
btn.click();
out.push({ btnText: btn.textContent, dlgOpen: $("#dlg-components").open,
           installCalls: window.__installCalls });
""")
        data = res[0]
        self.assertEqual(data["btnText"], "安装/更换组件包", "缺组件包时标题行给导入入口")
        self.assertTrue(data["dlgOpen"], "点了要打开导入弹窗")
        self.assertEqual(data["installCalls"], 0, "入口只开弹窗，不能直接装")


if __name__ == "__main__":
    unittest.main()
