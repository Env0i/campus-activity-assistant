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
        """验证码识别已装未用、面板忙：这一行只给「启用」，忙时要禁用；
        「下载并安装」这一档此刻不在，不能因为忙没忙过来又亮一次。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: { available: true } } };
OcrPanel.busy = true;
paintOcrDownload();
out.push({ enableDisabled: $("#btn-ocr-enable").disabled,
           downloadHidden: $("#btn-ocr-download").hidden,
           enableHidden: $("#btn-ocr-enable").hidden });
""")
        data = res[0]
        self.assertFalse(data["enableHidden"], "装好没用时「启用」按钮要看得见")
        self.assertTrue(data["enableDisabled"], "面板忙碌时启用按钮要禁用")
        self.assertTrue(data["downloadHidden"], "这一档不给「下载并安装」")

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
        """验证码识别在下载：这次只给「取消」，忙时禁用、空闲时可点。"""
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
        self.assertTrue(busy["loadingShown"], "下载中进度条要显示")
        self.assertFalse(busy["cancelHidden"], "下载中标题行只给「取消」")
        self.assertEqual(busy["cancelText"], "取消")
        self.assertTrue(busy["disabledBusy"], "面板忙时取消按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一只按钮要可点")

    def test_installing_keeps_the_old_ocr_error_hidden(self):
        """验证码识别·安装中：之前留下的失败红条要收着，进度条也收着。
        装完标志清掉后，同一句红条才重新出现。"""
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
        self.assertTrue(data["loadingShown"] is False, "安装中进度条收着")
        self.assertEqual(data["errText"], "", "安装中不显示旧的失败红条")
        self.assertTrue(data["errHidden"], "安装中红条要收起")
        self.assertEqual(res[1]["errTextWhenFree"], "下载没有完成：连不上发布页，可以重试。",
                         "安装标志清掉后旧失败要重新可见")
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
        """手机控制在下、验证码识别在装：两行各写各的进度，互不串。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { download: { state: "downloading",
    downloaded: 5242880, total_bytes: 10485760 } },
  relogin_ocr: { ready: true } } };
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneText: $("#phone-feature-status-text").textContent,
           phoneLoadingHidden: $("#phone-loading").hidden,
           ocrText: $("#ocr-feature-status-text").textContent,
           ocrLoadingHidden: $("#ocr-loading").hidden });
""")
        data = res[0]
        self.assertIn("下载中", data["phoneText"], "手机控制行说自己在下")
        self.assertEqual(data["ocrText"], "正在安装组件…", "验证码识别行说自己在装")
        self.assertFalse(data["phoneLoadingHidden"], "手机控制的进度条要显示")
        self.assertTrue(data["ocrLoadingHidden"], "验证码识别的进度条要收着")

    def test_each_component_shows_its_own_installing_row(self):
        """两行都在装：各写各的「正在安装组件…」，谁也不跌回「没装」。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { ready: true }, relogin_ocr: { ready: true } } };
window.PhonePanel.installing.phone_control = true;
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneText: $("#phone-feature-status-text").textContent,
           ocrText: $("#ocr-feature-status-text").textContent,
           phoneMissingHidden: $("#phone-missing").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden });
""")
        data = res[0]
        self.assertEqual(data["phoneText"], "正在安装组件…", "手机控制行要说明在安装")
        self.assertEqual(data["ocrText"], "正在安装组件…", "验证码识别行要说明在安装")
        self.assertTrue(data["phoneMissingHidden"], "安装中不能显示成「没装」")
        self.assertTrue(data["ocrMissingHidden"], "安装中不能显示成「没装」")

    def test_each_component_installs_from_missing_without_showing_missing_blocks(self):
        """两行都在装、都没装过：没装块不能显示，标题行也只写状态——安装中按钮位不亮，
        免得用户在装到一半时再点一次。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: {}, relogin_ocr: {} } };
window.PhonePanel.installing.phone_control = true;
window.PhonePanel.installing.relogin_ocr = true;
window.PhonePanel.paint();
out.push({ phoneMissingHidden: $("#phone-missing").hidden,
           phoneInstallHidden: $("#btn-phone-component-install").hidden,
           phoneText: $("#phone-feature-status-text").textContent,
           phoneLoadingHidden: $("#phone-loading").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden,
           ocrDownloadHidden: $("#btn-ocr-download").hidden,
           ocrText: $("#ocr-feature-status-text").textContent,
           ocrLoadingHidden: $("#ocr-loading").hidden });
""")
        data = res[0]
        self.assertTrue(data["phoneMissingHidden"], "安装中的手机控制不能显示成「没装」")
        self.assertTrue(data["phoneInstallHidden"], "安装中标题行不给第二次「下载并安装」")
        self.assertEqual(data["phoneText"], "正在安装组件…", "手机控制要说明在安装")
        self.assertTrue(data["phoneLoadingHidden"], "安装中进度条收着")
        self.assertTrue(data["ocrMissingHidden"], "安装中的验证码识别不能显示成「没装」")
        self.assertTrue(data["ocrDownloadHidden"], "安装中标题行不给第二次「下载并安装」")
        self.assertEqual(data["ocrText"], "正在安装组件…", "验证码识别要说明在安装")
        self.assertTrue(data["ocrLoadingHidden"], "安装中进度条收着")

    def test_checking_state_is_not_missing_on_both_rows(self):
        """两行都在检查中：一行一行显示成「没装」或「装好了」都不对。
        检查中不假装下载、也不假装没装，状态句要写清正在确认；说明位留给别的结论，检查中空着。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: {
  phone_control: { status: "checking", available: true },
  relogin_ocr: { status: "checking", available: true } } };
window.PhonePanel.paint();
out.push({ phoneMissingHidden: $("#phone-missing").hidden,
           ocrMissingHidden: $("#ocr-missing").hidden,
           phoneLoadingHidden: $("#phone-loading").hidden,
           ocrLoadingHidden: $("#ocr-loading").hidden,
           phoneText: $("#phone-feature-status-text").textContent,
           ocrText: $("#ocr-feature-status-text").textContent,
           phoneProbeHidden: $("#phone-probe").hidden,
           ocrProbeHidden: $("#ocr-note").hidden,
           phoneProbeKind: $("#phone-probe").dataset.probe,
           ocrProbeKind: $("#ocr-note").dataset.probe,
           phoneRetryHidden: $("#btn-phone-component-retry").hidden,
           ocrRetryHidden: $("#btn-ocr-retry").hidden });
""")
        data = res[0]
        self.assertTrue(data["phoneMissingHidden"], "检查中的手机控制不能显示成「没装」")
        self.assertTrue(data["ocrMissingHidden"], "检查中的验证码识别不能显示成「没装」")
        self.assertTrue(data["phoneLoadingHidden"], "检查中不是下载，进度块要收着")
        self.assertTrue(data["ocrLoadingHidden"], "检查中不是下载，进度块要收着")
        self.assertEqual(data["phoneText"], "正在确认组件状态…", "手机控制要写清正在确认状态")
        self.assertEqual(data["ocrText"], "正在确认组件状态…", "验证码识别要写清正在确认状态")
        self.assertTrue(data["phoneProbeHidden"], "检查中说明位留空")
        self.assertTrue(data["ocrProbeHidden"], "检查中说明位留空")
        self.assertEqual(data["phoneProbeKind"], "waiting")
        self.assertEqual(data["ocrProbeKind"], "waiting")
        self.assertTrue(data["phoneRetryHidden"], "刚在检查中不给「重试」")
        self.assertTrue(data["ocrRetryHidden"], "刚在检查中不给「重试」")

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

    def test_package_button_opens_the_dialog_without_installing(self):
        """手机控制·缺组件包：展开区那只「安装/更换组件包」点了只开弹窗，不调安装接口。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = {
  features: { phone_control: { ready: true } },
  channels: { cloudflare: { error: "cloudflared_missing" } } };
window.__installCalls = 0;
window.pywebview.api.install_advanced_feature = () => {
  window.__installCalls += 1; return Promise.resolve({ ok: true }); };
wireComponentRetries();
window.PhonePanel.paint();
const btn = $("#btn-phone-package");
const shown = !btn.hidden;
btn.click();
out.push({ shown: shown, dlgOpen: $("#dlg-components").open,
           installCalls: window.__installCalls });
""")
        data = res[0]
        self.assertTrue(data["shown"], "缺组件包时展开区给补装入口")
        self.assertTrue(data["dlgOpen"], "点了要打开导入弹窗")
        self.assertEqual(data["installCalls"], 0, "入口只开弹窗，不能直接装")


class ComponentRowLeftoverTests(unittest.TestCase):
    """审计补的两处老缺口：手机开着时残留的下载事务、识别行有错误没备注时的取消句。"""

    def test_running_phone_hides_component_progress_even_with_a_stale_download(self):
        """手机访问开着：快照里组件还留着下载中的事务，组件那一行也不能亮进度块和「取消下载」。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true, available: true, download: { state: "downloading", downloaded: 3145728, total_bytes: 9437184 } } } };
window.PhonePanel.paint();
out.push({ loadingHidden: $("#phone-loading").hidden, cancelHidden: $("#btn-phone-component-cancel").hidden });
""")
        data = res[0]
        self.assertTrue(data["loadingHidden"], "手机开着时进度块要收起")
        self.assertTrue(data["cancelHidden"], "手机开着时取消下载按钮要收起")

    def test_ocr_error_without_note_suppresses_the_cancel_sentence(self):
        """验证码识别·取消后回到没装：面板留着错误、没有备注时，红条说错误，不再说「下载已取消」那句。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: { download: { state: "cancelled" } } } };
OcrPanel.note = "";
OcrPanel.error = "面板错误";
window.PhonePanel.paint();
out.push({ errorText: $("#ocr-download-error").textContent, noteText: $("#ocr-note").textContent, noteHidden: $("#ocr-note").hidden });
""")
        data = res[0]
        self.assertEqual(data["errorText"], "面板错误", "红条要说面板上的错误")
        self.assertEqual(data["noteText"], "", "没有备注时不能再说取消句")
        self.assertTrue(data["noteHidden"], "没有备注时备注行要收起")


if __name__ == "__main__":
    unittest.main()
