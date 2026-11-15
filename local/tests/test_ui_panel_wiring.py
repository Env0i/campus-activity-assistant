#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板接线测试：手机面板 wire 与设置页验证码识别一节 wireSettings 的每处事件绑定。

每一处绑定一条用例：在整页沙箱（真实页面脚本清单）里触发控件的事件（点击、
change 或 input），先断言用户看得到的结果或发出的桥接请求（接口名和关键参数），
再断言内部值；不读源码文字。变异验证（未变异通过、把那一处绑定换成空语句后
红在它自己那句断言上）见 design/evidence/2026-11-14/phone-panel-move/wiring.md。
这份测试先于面板搬成模块编写，在还没搬的代码上全绿。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402

# 公共桩：桥接替身把每次请求记成 [接口名, ...参数]；微任务推进；按选择器触发事件。
# 验证码识别一节的两个绑定（下载、取消）在搬成模块后要靠点击时再查 window.PhonePanel，
# 这里全部走整页清单加载，绑没绑上只有点了才知道。
PRELUDE = r"""
window.__calls = [];
window.pywebview = { api: new Proxy({}, {
  get: (target, name) => (...args) => {
    window.__calls.push([String(name), ...args]);
    return Promise.resolve({ ok: true });
  },
}) };
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
const __fire = (sel, type) => {
  const el = $(sel);
  (el.listeners[type] || []).forEach((fn) => fn({ target: el, preventDefault() {} }));
};
"""


class WireComponentDialogTests(unittest.TestCase):
    """导入弹窗与组件下载这一组按钮的接线。"""

    def test_wire_comp_install_sends_the_phone_download_request(self):
        """没装时标题行「下载并安装」：点击发出手机控制的组件下载请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-phone-component-install").click();
await __flush();
out.push({ call: window.__calls[0] });
""")
        self.assertEqual(res[0]["call"][0], "download_advanced_feature", "点击要发出组件下载请求")
        self.assertEqual(res[0]["call"][1], "phone_control", "下载的必须是手机控制这一项")

    def test_wire_comp_cancel_sends_the_phone_cancel_request(self):
        """下载中标题行「取消下载」：点击发出手机控制的取消下载请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-phone-component-cancel").click();
await __flush();
out.push({ call: window.__calls[0] });
""")
        self.assertEqual(res[0]["call"][0], "cancel_advanced_feature_download",
                         "点击要发出取消下载请求")
        self.assertEqual(res[0]["call"][1], "phone_control", "取消的必须是手机控制这一项")

    def test_wire_feature_button_opens_the_import_dialog(self):
        """标题行缺组件包时的按钮（导入入口）：点击打开导入弹窗，不直接安装。"""
        res = run_js(PRELUDE + r"""
window.__installCalls = 0;
window.pywebview.api.install_advanced_feature = () => {
  window.__installCalls += 1; return Promise.resolve({ ok: true }); };
$("#btn-phone-feature-install").click();
await __flush();
out.push({ open: $("#dlg-components").open,
           title: $("#dlg-components-title").textContent,
           installCalls: window.__installCalls });
""")
        data = res[0]
        self.assertTrue(data["open"], "点击标题行导入入口要打开导入弹窗")
        self.assertEqual(data["title"], "导入手机控制组件", "弹窗要说清在导入哪个组件")
        self.assertEqual(data["installCalls"], 0, "入口只开弹窗，不能直接装")

    def test_wire_phone_import_link_opens_the_import_dialog(self):
        """下载失败后的「导入已下载的组件包」链接：点击打开手机控制的导入弹窗。"""
        res = run_js(PRELUDE + r"""
$("#btn-phone-import").click();
await __flush();
out.push({ open: $("#dlg-components").open,
           title: $("#dlg-components-title").textContent });
""")
        self.assertTrue(res[0]["open"], "点击导入链接要打开导入弹窗")
        self.assertEqual(res[0]["title"], "导入手机控制组件", "弹窗要说清在导入哪个组件")

    def test_wire_phone_pick_sends_the_pick_request(self):
        """弹窗里手机控制行的「选择文件」：点击发出选择文件请求，没选到时给一句话。"""
        res = run_js(PRELUDE + r"""
$("#btn-comp-phone-pick").click();
await __flush();
out.push({ call: window.__calls[0], note: $("#comp-phone-note").textContent });
""")
        self.assertEqual(res[0]["call"][0], "pick_advanced_component", "点击要发出选择文件请求")
        self.assertEqual(res[0]["call"][1], "phone_control", "选的是手机控制这一项")
        self.assertEqual(res[0]["note"], "还没有选择文件。", "没选到文件时结论行要说一声")

    def test_wire_ocr_pick_sends_the_pick_request(self):
        """弹窗里验证码识别行的「选择文件」：点击发出选择文件请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-comp-ocr-pick").click();
await __flush();
out.push({ call: window.__calls[0], note: $("#comp-ocr-note").textContent });
""")
        self.assertEqual(res[0]["call"][0], "pick_advanced_component", "点击要发出选择文件请求")
        self.assertEqual(res[0]["call"][1], "relogin_ocr", "选的是验证码识别这一项")
        self.assertEqual(res[0]["note"], "还没有选择文件。", "没选到文件时结论行要说一声")

    def test_wire_phone_file_install_asks_for_a_verified_file(self):
        """弹窗里手机控制行的「安装这份」：没自检通过时不可安装，结论行说先选文件。"""
        res = run_js(PRELUDE + r"""
$("#btn-comp-phone-install").click();
await __flush();
out.push({ note: $("#comp-phone-note").textContent,
           install: window.__calls.filter((c) => c[0] === "install_advanced_feature") });
""")
        self.assertEqual(res[0]["note"], "先选文件并自检通过，再安装。",
                         "没自检通过时结论行要说先选文件")
        self.assertEqual(res[0]["install"], [], "没自检通过时不能发安装请求")

    def test_wire_ocr_file_install_asks_for_a_verified_file(self):
        """弹窗里验证码识别行的「安装这份」：没自检通过时不可安装。"""
        res = run_js(PRELUDE + r"""
$("#btn-comp-ocr-install").click();
await __flush();
out.push({ note: $("#comp-ocr-note").textContent,
           install: window.__calls.filter((c) => c[0] === "install_advanced_feature") });
""")
        self.assertEqual(res[0]["note"], "先选文件并自检通过，再安装。",
                         "没自检通过时结论行要说先选文件")
        self.assertEqual(res[0]["install"], [], "没自检通过时不能发安装请求")

    def test_wire_comp_close_closes_the_dialog(self):
        """弹窗的「完成/关闭」按钮：点击后弹窗收起。"""
        res = run_js(PRELUDE + r"""
const dlg = $("#dlg-components");
dlg.hasAttribute = (k) => k === "open" && dlg.open === true;
dlg.removeAttribute = () => {};
window.PhonePanel.openComponents("phone_control");
$("#btn-comp-close").click();
await __flush();
out.push({ open: dlg.open });
""")
        self.assertFalse(res[0]["open"], "点击关闭按钮后弹窗要收起")

    def test_wire_tailscale_radio_sends_the_preference_request(self):
        """通道卡 Tailscale：选中即记偏好，请求带通道名。"""
        res = run_js(PRELUDE + r"""
$("#phone-chan-tailscale").checked = false;
__fire("#phone-chan-tailscale", "change");
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "set_phone_access_preferences"),
           checked: $("#phone-chan-tailscale").checked });
""")
        self.assertEqual(res[0]["call"], [["set_phone_access_preferences", "tailscale"]],
                         "选中通道要发出记偏好请求并带通道名")
        self.assertTrue(res[0]["checked"], "重画后这张卡要是选中态")

    def test_wire_cloudflare_radio_sends_the_preference_request(self):
        """通道卡 Cloudflare：选中即记偏好，请求带通道名。"""
        res = run_js(PRELUDE + r"""
$("#phone-chan-cloudflare").checked = false;
__fire("#phone-chan-cloudflare", "change");
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "set_phone_access_preferences"),
           checked: $("#phone-chan-cloudflare").checked });
""")
        self.assertEqual(res[0]["call"], [["set_phone_access_preferences", "cloudflare"]],
                         "选中通道要发出记偏好请求并带通道名")
        self.assertTrue(res[0]["checked"], "重画后这张卡要是选中态")


class WirePhoneAccessTests(unittest.TestCase):
    """手机访问开合这一组按钮的接线。"""

    def test_wire_start_sends_the_start_request_and_says_starting(self):
        """「开启手机访问」：点击先说「启动中…」，随后发出开启请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-phone-start").click();
out.push({ text: $("#btn-phone-start").textContent });
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "start_phone_access") });
""")
        self.assertEqual(res[0]["text"], "启动中…", "点击后按钮要说启动中")
        self.assertEqual(res[1]["call"], [["start_phone_access", "tailscale"]],
                         "要发出开启请求，默认通道是 Tailscale")

    def test_wire_stop_opens_the_confirm_row(self):
        """「关闭手机访问」：点击先展开确认行，不直接关闭。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.paint();
$("#phone-stop-confirm").hidden = true;
$("#btn-phone-stop").click();
out.push({ confirmShown: !$("#phone-stop-confirm").hidden,
           stopCalls: window.__calls.filter((c) => c[0] === "stop_phone_access") });
""")
        self.assertTrue(res[0]["confirmShown"], "点击关闭要先展开确认行")
        self.assertEqual(res[0]["stopCalls"], [], "只展开确认行，不发关闭请求")

    def test_wire_stop_cancel_collapses_the_confirm_row(self):
        """确认行的「先不关闭」：点击收起确认行，不发请求。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.paint();
$("#btn-phone-stop").click();
$("#btn-phone-stop-cancel").click();
out.push({ confirmHidden: $("#phone-stop-confirm").hidden,
           stopCalls: window.__calls.filter((c) => c[0] === "stop_phone_access") });
""")
        self.assertTrue(res[0]["confirmHidden"], "点「先不关闭」要收起确认行")
        self.assertEqual(res[0]["stopCalls"], [], "先不关闭不能发关闭请求")

    def test_wire_stop_confirm_sends_the_stop_request(self):
        """确认行的「确认关闭」：点击发出关闭请求。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.paint();
$("#btn-phone-stop-confirm").click();
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "stop_phone_access") });
""")
        self.assertEqual(res[0]["call"], [["stop_phone_access"]], "确认后要发出关闭请求")

    def test_wire_add_pair_shows_the_pair_block(self):
        """「再配对一台手机」：点击重新展开配对区。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.state.paired_count = 1;
window.PhonePanel.paint();
$("#btn-phone-add-pair").click();
out.push({ pairShown: !$("#phone-pair").hidden });
""")
        self.assertTrue(res[0]["pairShown"], "点击后配对区要重新展开")

    def test_wire_recheck_reports_the_result_inline(self):
        """「重新检测」：点击重取快照，连上了就地在提示行说结果。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = {
  features: { phone_control: { ready: true } },
  channels: { tailscale: { available: true } } };
$("#btn-tailscale-recheck").click();
await __flush();
out.push({ note: $("#phone-off-note").textContent,
           stateCalls: window.__calls.filter((c) => c[0] === "phone_access_state") });
""")
        self.assertEqual(res[0]["note"], "已重新检测：Tailscale 已连接。",
                         "重新检测的结论要就地说")
        self.assertEqual(len(res[0]["stateCalls"]), 1, "重新检测要重取一次快照")

    def test_wire_copy_marks_the_button_copied(self):
        """「复制」：点击后按钮短暂说「已复制」。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.address = "http://127.0.0.1:8765/";
document.execCommand = () => true;
$("#btn-phone-address-copy").click();
out.push({ text: $("#btn-phone-address-copy").textContent });
""")
        self.assertEqual(res[0]["text"], "已复制", "复制成功后按钮要说已复制")

    def test_wire_open_loc_sends_the_open_dir_request(self):
        """「打开所在文件夹」：点击发出打开目录请求，参数是手机控制。"""
        res = run_js(PRELUDE + r"""
$("#btn-phone-open-loc").click();
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "open_advanced_component_dir") });
""")
        self.assertEqual(res[0]["call"], [["open_advanced_component_dir", "phone_control"]],
                         "要发出打开目录请求并带组件名")

    def test_wire_cred_go_opens_the_credential_form(self):
        """「去保存」：点击打开设置的登录组并展开账号表单，聚焦账号框。"""
        res = run_js(PRELUDE + r"""
$("#credential-editor").hidden = true;
$("#btn-phone-cred-go").click();
out.push({ editorShown: !$("#credential-editor").hidden,
           focus: focused[focused.length - 1] });
""")
        self.assertTrue(res[0]["editorShown"], "点击去保存要展开账号表单")
        self.assertEqual(res[0]["focus"], "#credential-user", "焦点要落在账号框上")


class WireCredentialsTests(unittest.TestCase):
    """保存的账号与登录恢复这一组按钮的接线。"""

    def test_wire_manage_opens_the_credential_form(self):
        """「填写账号密码/更换」：点击展开账号表单。"""
        res = run_js(PRELUDE + r"""
$("#credential-editor").hidden = true;
$("#btn-credentials-manage").click();
out.push({ editorShown: !$("#credential-editor").hidden });
""")
        self.assertTrue(res[0]["editorShown"], "点击入口按钮要展开账号表单")

    def test_wire_cred_cancel_collapses_the_credential_form(self):
        """表单的「取消」：点击收起表单。"""
        res = run_js(PRELUDE + r"""
$("#btn-credentials-manage").click();
$("#btn-credentials-cancel").click();
out.push({ editorHidden: $("#credential-editor").hidden });
""")
        self.assertTrue(res[0]["editorHidden"], "点取消要收起表单")

    def test_wire_user_input_reenables_the_save_button(self):
        """账号框输入：两个输入框都有内容后保存按钮可点。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#credential-user").value = "abc";
$("#credential-pass").value = "def";
__fire("#credential-user", "input");
out.push({ saveDisabled: $("#btn-credentials-save").disabled });
""")
        self.assertFalse(res[0]["saveDisabled"], "输入齐全后保存按钮要可点")

    def test_wire_pass_input_reenables_the_save_button(self):
        """密码框输入：两个输入框都有内容后保存按钮可点。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#credential-user").value = "abc";
$("#credential-pass").value = "def";
__fire("#credential-pass", "input");
out.push({ saveDisabled: $("#btn-credentials-save").disabled });
""")
        self.assertFalse(res[0]["saveDisabled"], "输入齐全后保存按钮要可点")

    def test_wire_once_change_renames_the_save_button(self):
        """勾选「只在这次运行中用」：保存按钮改名。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#credential-once").checked = true;
__fire("#credential-once", "change");
out.push({ text: $("#btn-credentials-save").textContent });
""")
        self.assertEqual(res[0]["text"], "只用这一次", "勾选后保存按钮要说只用这一次")

    def test_wire_save_sends_the_prepare_request_when_once_checked(self):
        """「只用这一次」下点保存：发出暂存请求，表单收起并就地说明。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#credential-user").value = "abc";
$("#credential-pass").value = "def";
$("#credential-once").checked = true;
$("#btn-credentials-save").click();
await __flush();
out.push({ call: window.__calls.filter((c) =>
             c[0] === "prepare_phone_relogin" || c[0] === "save_relogin_credentials"),
           editorHidden: $("#credential-editor").hidden,
           note: $("#credential-note").textContent });
""")
        self.assertEqual(res[0]["call"], [["prepare_phone_relogin", "abc", "def"]],
                         "勾了只用这一次要发暂存请求")
        self.assertTrue(res[0]["editorHidden"], "保存成功要收起表单")
        self.assertEqual(res[0]["note"], "已准备好，只在这次运行中使用。",
                         "保存成功要就地说一句")

    def test_wire_clear_opens_the_clear_confirm_row(self):
        """「清除已保存」：点击先展开确认行，不直接清。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#relogin-clear-confirm").hidden = true;
$("#btn-credentials-clear").click();
out.push({ confirmShown: !$("#relogin-clear-confirm").hidden,
           clearCalls: window.__calls.filter((c) => c[0] === "clear_relogin_credentials") });
""")
        self.assertTrue(res[0]["confirmShown"], "点击清除要先展开确认行")
        self.assertEqual(res[0]["clearCalls"], [], "只展开确认行，不发清除请求")

    def test_wire_clear_cancel_collapses_the_clear_confirm_row(self):
        """清除确认行的「先不清除」：点击收起确认行。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#btn-credentials-clear").click();
$("#btn-relogin-clear-cancel").click();
out.push({ confirmHidden: $("#relogin-clear-confirm").hidden });
""")
        self.assertTrue(res[0]["confirmHidden"], "点「先不清除」要收起确认行")

    def test_wire_clear_confirm_sends_the_clear_request(self):
        """清除确认行的「确认清除」：点击发出清除请求并就地说结果。"""
        res = run_js(PRELUDE + r"""
await __flush();
$("#btn-credentials-clear").click();
$("#btn-relogin-clear-confirm").click();
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "clear_relogin_credentials"),
           note: $("#credential-note").textContent });
""")
        self.assertEqual(res[0]["call"], [["clear_relogin_credentials"]], "确认后要发出清除请求")
        self.assertEqual(res[0]["note"], "已清除本机保存的账号密码。", "清除成功要就地说一句")


class WireSettingsOcrTests(unittest.TestCase):
    """设置页 wireSettings 里验证码识别一节的六处接线。

    下载与取消这两处在搬成模块后改成点击时再查 window.PhonePanel（模块那时才执行）；
    接线测试不管绑定发生在加载期还是点击期，只管点了有没有反应。"""

    def test_wire_ocr_download_sends_the_ocr_download_request(self):
        """识别一节「下载并安装」：点击发出验证码识别的下载请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-ocr-download").click();
await __flush();
out.push({ call: window.__calls[0] });
""")
        self.assertEqual(res[0]["call"][0], "download_advanced_feature", "点击要发出组件下载请求")
        self.assertEqual(res[0]["call"][1], "relogin_ocr", "下载的必须是验证码识别这一项")

    def test_wire_ocr_cancel_sends_the_ocr_cancel_request(self):
        """识别一节「取消下载」：点击发出验证码识别的取消下载请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-ocr-cancel").click();
await __flush();
out.push({ call: window.__calls[0] });
""")
        self.assertEqual(res[0]["call"][0], "cancel_advanced_feature_download",
                         "点击要发出取消下载请求")
        self.assertEqual(res[0]["call"][1], "relogin_ocr", "取消的必须是验证码识别这一项")

    def test_wire_ocr_enable_sends_the_enable_request(self):
        """识别一节「启用」：点击发出启用请求并就地说结果。"""
        res = run_js(PRELUDE + r"""
$("#btn-ocr-enable").click();
await __flush();
out.push({ note: $("#ocr-note").textContent,
           call: window.__calls.filter((c) => c[0] === "enable_advanced_feature") });
""")
        self.assertEqual(res[0]["note"], "验证码识别已启用。", "启用成功要就地说一句")
        self.assertEqual(res[0]["call"], [["enable_advanced_feature", "relogin_ocr"]],
                         "要发出启用请求并带组件名")

    def test_wire_ocr_import_opens_the_ocr_dialog(self):
        """识别一节「导入已下载的组件包」：点击打开验证码识别的导入弹窗。"""
        res = run_js(PRELUDE + r"""
$("#btn-ocr-import").click();
out.push({ open: $("#dlg-components").open,
           title: $("#dlg-components-title").textContent });
""")
        self.assertTrue(res[0]["open"], "点击导入链接要打开导入弹窗")
        self.assertEqual(res[0]["title"], "导入验证码识别组件", "弹窗要说清在导入哪个组件")

    def test_wire_ocr_reinstall_sends_the_ocr_download(self):
        """识别一节坏了点「重新安装」：走在线下载那条路再装一份，不再开导入弹窗。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { relogin_ocr: { status: "failed" } } };
PhonePanel.paint();
$("#btn-ocr-download").click();
await __flush();
out.push({ open: $("#dlg-components").open,
           call: window.__calls.filter((c) => c[0] === "download_advanced_feature") });
""")
        self.assertEqual(res[0]["call"], [["download_advanced_feature", "relogin_ocr"]],
                         "点了重新安装要发出组件下载请求并带组件名")
        self.assertFalse(res[0]["open"], "重新安装不再走导入弹窗")

    def test_wire_ocr_open_loc_sends_the_open_dir_request(self):
        """识别一节「打开所在文件夹」：点击发出打开目录请求。"""
        res = run_js(PRELUDE + r"""
$("#btn-ocr-open-loc").click();
await __flush();
out.push({ call: window.__calls.filter((c) => c[0] === "open_advanced_component_dir") });
""")
        self.assertEqual(res[0]["call"], [["open_advanced_component_dir", "relogin_ocr"]],
                         "要发出打开目录请求并带组件名")


if __name__ == "__main__":
    unittest.main()
