#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件与手机访问动手之前补的安全网·手机访问与面板读取一组。

每个 test_ 守一张变异表里的一行：给后端状态、触发动作或重画、看用户看得到的
结果（按钮文字与是否禁用、状态字、有没有再发一次桥接请求），再断言内部值；
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

# 公共桩：手机访问快照（未开启、Tailscale 可用）、位置接口不返、微任务推进
PRELUDE = r"""
window.pywebview = { api: {
  phone_access_state: () => Promise.resolve({ ok: true, running: false,
    advanced: { channels: { tailscale: { available: true } } } }),
  advanced_component_location: () => Promise.resolve({ ok: false }),
} };
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
"""


class PhonePhaseRowTests(unittest.TestCase):
    """认阶段：手机访问一行的每个阶段，用户看到的按钮和状态字。"""

    def test_phone_phase_broken_offers_reinstall(self):
        """手机控制·加载失败：主按钮变「重新安装」，点它沿在线下载那条路再装一份；
        标题行那个「重新导入组件包」不再有，坏了的说明写在红条里。"""
        res = run_js(PRELUDE + r"""
globalThis.__calls = [];
window.pywebview.api.download_advanced_feature = (name) => {
  __calls.push(name); return Promise.resolve({ ok: true });
};
window.PhonePanel.state.advanced = { features: { phone_control: { status: "failed" } } };
window.PhonePanel.paint();
out.push({ btnText: $("#btn-phone-component-install").textContent,
           btnHidden: $("#btn-phone-component-install").hidden,
           btnDisabled: $("#btn-phone-component-install").disabled,
           featureBtnHidden: $("#btn-phone-feature-install").hidden,
           chip: $("#phone-feature-status").textContent,
           errorHidden: $("#phone-component-error").hidden,
           errorText: $("#phone-component-error").textContent });
$("#btn-phone-component-install").click();
await __flush();
out.push({ calls: __calls.slice() });
""")
        data, after = res[0], res[1]
        self.assertEqual(data["btnText"], "重新安装", "加载失败要给重新安装的入口")
        self.assertFalse(data["btnHidden"], "加载失败时主按钮要看得见")
        self.assertFalse(data["btnDisabled"], "不忙的时候主按钮要能点")
        self.assertTrue(data["featureBtnHidden"], "标题行不再另给一个重新导入的按钮")
        self.assertEqual(data["chip"], "加载失败", "状态字要说是加载失败")
        self.assertFalse(data["errorHidden"], "坏了要有一条说明")
        self.assertEqual(data["errorText"], "组件文件不完整。重新安装不会动你的账号和设置。")
        self.assertEqual(after["calls"], ["phone_control"], "点重新安装要走在线下载这条路")


class PaintBusyReadTests(unittest.TestCase):
    """读进行中标志·重画：忙碌时由重画把各块按钮按住，别让用户点到一半的动作。"""

    def test_busy_read_in_paint_relogin_disables_the_recovery_buttons(self):
        """登录恢复：面板忙碌时「填写账号密码/更换」与「清除已保存」两个按钮都要禁用。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ manageDisabled: $("#btn-credentials-manage").disabled,
           clearDisabled: $("#btn-credentials-clear").disabled });
""")
        data = res[0]
        self.assertTrue(data["manageDisabled"], "忙碌时登录恢复的入口按钮要禁用")
        self.assertTrue(data["clearDisabled"], "忙碌时清除账号按钮要禁用")

    def test_busy_read_in_paint_cred_form_disables_the_once_box(self):
        """登录恢复·表单：面板忙碌时「只在这次运行中使用」勾选项要禁用。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ onceDisabled: $("#credential-once").disabled });
""")
        data = res[0]
        self.assertTrue(data["onceDisabled"], "忙碌时勾选项要禁用")

    def test_busy_read_in_paint_cred_form_disables_save_with_a_filled_form(self):
        """登录恢复·表单：账号密码都填好、面板忙碌时「保存」按钮仍要禁用——
        不然保存请求会和进行中的动作叠在一起。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.busy = true;
$("#credential-user").value = "someone";
$("#credential-pass").value = "secret";
window.PhonePanel.paint();
out.push({ saveDisabled: $("#btn-credentials-save").disabled });
""")
        data = res[0]
        self.assertTrue(data["saveDisabled"], "忙碌时保存按钮要禁用")

    def test_busy_read_in_paint_phone_access_disables_start(self):
        """手机访问：面板忙碌时「开启手机访问」按钮要禁用（通道可用、没有其他禁用原因）。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.busy = true;
window.PhonePanel.state.advanced = { channels: { tailscale: { available: true } } };
window.PhonePanel.paint();
out.push({ startDisabled: $("#btn-phone-start").disabled,
           startHidden: $("#btn-phone-start").hidden });
""")
        data = res[0]
        self.assertFalse(data["startHidden"], "没开启时开启按钮要看得见")
        self.assertTrue(data["startDisabled"], "忙碌时开启按钮要禁用")


class PollingBusyReadTests(unittest.TestCase):
    """读进行中标志·轮询：动作在途时轮询不插进来重取快照。"""

    def test_busy_read_in_start_polling_skips_refresh_while_busy(self):
        """手机控制·轮询：面板忙碌时到点的轮询要跳过，不再发 phone_access_state；
        空闲时同一颗定时器照常重取（对照）。"""
        res = run_js(PRELUDE + r"""
globalThis.setInterval = (fn, ms) => { window.__poll = fn; return 1; };
window.__stateCalls = 0;
window.pywebview.api.phone_access_state = () => {
  window.__stateCalls += 1; return Promise.resolve({ ok: true, running: true }); };
window.PhonePanel.state.running = true;
window.PhonePanel.busy = true;
window.PhonePanel.startPolling();
window.__stateCalls = 0;
window.__poll();
out.push({ callsWhileBusy: window.__stateCalls });
window.PhonePanel.busy = false;
window.__poll();
await __flush();
out.push({ callsWhenFree: window.__stateCalls });
""")
        self.assertEqual(res[0]["callsWhileBusy"], 0, "忙碌时轮询不能再发快照请求")
        self.assertGreaterEqual(res[1]["callsWhenFree"], 1, "空闲时轮询要照常重取")


class GuardTests(unittest.TestCase):
    """读进行中标志·动作入口：忙碌或开启/关闭在途时再点，不再发一次桥接请求。"""

    def test_busy_guard_in_enable_feature_sends_nothing(self):
        """手机控制·启用：另一个动作在途时再点启用，不发 enable_advanced_feature。"""
        res = run_js(PRELUDE + r"""
window.__enableCalls = 0;
window.pywebview.api.enable_advanced_feature = () => {
  window.__enableCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = true;
await PhonePanel.enableFeature();
out.push({ enableCalls: window.__enableCalls });
""")
        self.assertEqual(res[0]["enableCalls"], 0, "忙碌时再点启用不能再发请求")

    def test_busy_guard_in_toggle_start_sends_nothing(self):
        """手机访问·开启：另一个动作在途时再点开启，不发 start_phone_access。"""
        res = run_js(PRELUDE + r"""
window.__startCalls = 0;
window.pywebview.api.start_phone_access = () => {
  window.__startCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = true;
window.PhonePanel.pending = "";
await PhonePanel.toggleStart();
out.push({ startCalls: window.__startCalls });
""")
        self.assertEqual(res[0]["startCalls"], 0, "忙碌时再点开启不能再发请求")

    def test_pending_guard_in_toggle_start_sends_nothing(self):
        """手机访问·开启：开启还在途（忙碌位已被更早回来的请求先清掉）时再点开启，
        不发第二次 start_phone_access。"""
        res = run_js(PRELUDE + r"""
window.__startCalls = 0;
window.pywebview.api.start_phone_access = () => {
  window.__startCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = false;
window.PhonePanel.pending = "starting";
await PhonePanel.toggleStart();
out.push({ startCalls: window.__startCalls });
""")
        self.assertEqual(res[0]["startCalls"], 0, "开启在途时再点不能再发请求")

    def test_busy_guard_in_toggle_stop_sends_nothing(self):
        """手机访问·关闭：另一个动作在途时再点关闭，不发 stop_phone_access。"""
        res = run_js(PRELUDE + r"""
window.__stopCalls = 0;
window.pywebview.api.stop_phone_access = () => {
  window.__stopCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = true;
window.PhonePanel.pending = "";
await PhonePanel.toggleStop();
out.push({ stopCalls: window.__stopCalls });
""")
        self.assertEqual(res[0]["stopCalls"], 0, "忙碌时再点关闭不能再发请求")

    def test_pending_guard_in_toggle_stop_sends_nothing(self):
        """手机访问·关闭：关闭还在途（忙碌位已被更早回来的请求先清掉）时再点关闭，
        不发第二次 stop_phone_access。"""
        res = run_js(PRELUDE + r"""
window.__stopCalls = 0;
window.pywebview.api.stop_phone_access = () => {
  window.__stopCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = false;
window.PhonePanel.pending = "stopping";
await PhonePanel.toggleStop();
out.push({ stopCalls: window.__stopCalls });
""")
        self.assertEqual(res[0]["stopCalls"], 0, "关闭在途时再点不能再发请求")

    def test_busy_guard_in_download_component_sends_nothing(self):
        """手机控制·下载：另一个动作在途时再点「下载并安装」，不发下载请求。"""
        res = run_js(PRELUDE + r"""
window.__downloadCalls = 0;
window.pywebview.api.download_advanced_feature = () => {
  window.__downloadCalls += 1; return Promise.resolve({ ok: true }); };
window.PhonePanel.busy = true;
await PhonePanel.downloadComponent("phone_control");
out.push({ downloadCalls: window.__downloadCalls });
""")
        self.assertEqual(res[0]["downloadCalls"], 0, "忙碌时再点下载不能再发请求")


class ChannelCardTests(unittest.TestCase):
    """两张通道卡的结论：长期地址与临时地址要说得清差别和代价。"""

    def test_channel_cards_say_long_lived_versus_temporary(self):
        """手机访问·通道卡：Tailscale 可用说地址固定、重启不用重新配对；Cloudflare
        可用说组件里已带好、但每次开启地址都会变、要重新扫码和配对。"""
        res = run_js(PRELUDE + r"""
const cards = channelCards({ tailscale: { available: true },
  cloudflare: { available: true } });
out.push({ tsStatus: cards.tailscale.status, tsText: cards.tailscale.text,
           cfStatus: cards.cloudflare.status, cfText: cards.cloudflare.text });
""")
        data = res[0]
        self.assertEqual(data["tsStatus"], "已连接", "Tailscale 可用要说已连接")
        self.assertIn("地址固定", data["tsText"], "长期地址要说重启后不用重新配对")
        self.assertIn("同一个账号", data["tsText"], "长期地址要说电脑和手机登录同一账号")
        self.assertEqual(data["cfStatus"], "可用", "Cloudflare 可用要说可用")
        self.assertIn("组件里已带好", data["cfText"], "临时地址要说不用另外装")
        self.assertIn("要重新扫码和配对", data["cfText"], "临时地址要说代价")


class CheckEventLinkTests(unittest.TestCase):
    """重新登录的校验事件回到界面后，手机访问面板要重取自己的快照。"""

    def test_check_event_refreshes_the_phone_panel(self):
        """登录校验通过的事件到达后，面板重新取一次手机访问快照（再发一次桥接请求）。"""
        res = run_js(PRELUDE + r"""
window.__stateCalls = 0;
window.pywebview.api.phone_access_state = () => {
  window.__stateCalls += 1; return Promise.resolve({ ok: true, running: false }); };
window.onBackend.check({ ok: true, result: "valid" });
await __flush();
out.push({ stateCalls: window.__stateCalls });
""")
        self.assertGreaterEqual(res[0]["stateCalls"], 1, "check 事件后面板要重取快照")


class TitleRowButtonUsePointTests(unittest.TestCase):
    """使用点·标题行三颗按钮：面板忙时按钮要按住，空闲时同一颗要可点。"""

    def test_busy_read_disables_the_component_install_button(self):
        """手机控制·没装：标题行「下载并安装」看得见，面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: {} } };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ missingShown: !$("#phone-missing").hidden,
           btnHidden: $("#btn-phone-component-install").hidden,
           btnText: $("#btn-phone-component-install").textContent,
           disabledBusy: $("#btn-phone-component-install").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-component-install").disabled });
""")
        busy, free = res
        self.assertTrue(busy["missingShown"], "没装时「没装」块要看得见")
        self.assertFalse(busy["btnHidden"], "没装时标题行「下载并安装」要看得见")
        self.assertEqual(busy["btnText"], "下载并安装")
        self.assertTrue(busy["disabledBusy"], "面板忙时下载按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_busy_read_disables_the_component_cancel_button(self):
        """手机控制·下载中：标题行「取消下载」看得见，面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: {
  download: { state: "downloading", downloaded: 5242880, total_bytes: 10485760 } } } };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ loadingShown: !$("#phone-loading").hidden,
           cancelHidden: $("#btn-phone-component-cancel").hidden,
           cancelText: $("#btn-phone-component-cancel").textContent,
           disabledBusy: $("#btn-phone-component-cancel").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-component-cancel").disabled });
""")
        busy, free = res
        self.assertTrue(busy["loadingShown"], "下载中进度块要显示")
        self.assertFalse(busy["cancelHidden"], "下载中标题行「取消下载」要看得见")
        self.assertEqual(busy["cancelText"], "取消下载")
        self.assertTrue(busy["disabledBusy"], "面板忙时取消按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_busy_read_disables_the_title_action_button_on_missing_cloudflared(self):
        """手机控制·已装未开启但 Cloudflare 缺组件包：标题行「安装/更换组件包」看得见，
        面板忙时要禁用，空闲时可点——缺包的补装入口不能被忙碌位关死。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
  channels: { tailscale: { available: true },
              cloudflare: { error: "cloudflared_missing" } } };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ btnHidden: $("#btn-phone-feature-install").hidden,
           btnText: $("#btn-phone-feature-install").textContent,
           disabledBusy: $("#btn-phone-feature-install").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-feature-install").disabled });
""")
        busy, free = res
        self.assertFalse(busy["btnHidden"], "缺组件包时标题行按钮要看得见")
        self.assertEqual(busy["btnText"], "安装/更换组件包")
        self.assertTrue(busy["disabledBusy"], "面板忙时标题行按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")


class PhoneAccessUsePointTests(unittest.TestCase):
    """使用点·手机访问各按钮与两行位置、错误信息：忙时要按住，空闲时可点。"""

    def test_busy_read_disables_the_open_location_button(self):
        """手机控制·已装未开启：知道组件装在哪时「打开所在文件夹」看得见，
        面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } } };
window.PhonePanel.location = { path: "组件目录", short: "组件目录" };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ locShown: !$("#phone-loc-after").hidden,
           btnHidden: $("#btn-phone-open-loc").hidden,
           disabledBusy: $("#btn-phone-open-loc").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-open-loc").disabled });
""")
        busy, free = res
        self.assertTrue(busy["locShown"], "「装在」那一行要看得见")
        self.assertFalse(busy["btnHidden"], "「打开所在文件夹」要看得见")
        self.assertTrue(busy["disabledBusy"], "面板忙时打开位置按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_loading_hides_the_installed_location_row(self):
        """手机控制·下载中：「装在」那一行要收起（还没装，不该说「装在」）；
        装好未开启时同一行要显示。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.location = { path: "组件目录", short: "组件目录" };
window.PhonePanel.state.advanced = { features: { phone_control: {
  download: { state: "downloading", downloaded: 1048576, total_bytes: 10485760 } } } };
window.PhonePanel.paint();
out.push({ locAfterHiddenWhileLoading: $("#phone-loc-after").hidden,
           loadingShown: !$("#phone-loading").hidden });
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } } };
window.PhonePanel.paint();
out.push({ locAfterShownWhenOff: !$("#phone-loc-after").hidden });
""")
        data = res[0]
        self.assertTrue(data["locAfterHiddenWhileLoading"], "下载中「装在」行要收起")
        self.assertTrue(data["loadingShown"], "下载中进度块要显示")
        self.assertTrue(res[1]["locAfterShownWhenOff"], "装好未开启时「装在」行要显示")

    def test_busy_disables_the_recheck_button_and_starting_hides_it(self):
        """手机访问·Tailscale 没连上：「重新检测」看得见，面板忙时要禁用、空闲时可点；
        启动过程中它要收起（开了再检测也来不及），空闲时同一颗要显示。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
  channels: { tailscale: { available: false, state: "not_logged_in" } } };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ recheckHidden: $("#btn-tailscale-recheck").hidden,
           hint: $("#phone-channel-hint").textContent,
           disabledBusy: $("#btn-tailscale-recheck").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-tailscale-recheck").disabled });
window.PhonePanel.pending = "starting";
window.PhonePanel.paint();
out.push({ recheckHiddenWhileStarting: $("#btn-tailscale-recheck").hidden });
window.PhonePanel.pending = "";
window.PhonePanel.paint();
out.push({ recheckShownWhenFree: !$("#btn-tailscale-recheck").hidden });
""")
        busy, free, starting, shown = res
        self.assertFalse(busy["recheckHidden"], "Tailscale 没连上时「重新检测」要看得见")
        self.assertIn("还差一步", busy["hint"], "没登录要说差哪一步")
        self.assertTrue(busy["disabledBusy"], "面板忙时重新检测按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")
        self.assertTrue(starting["recheckHiddenWhileStarting"], "启动中「重新检测」要收起")
        self.assertTrue(shown["recheckShownWhenFree"], "空闲时「重新检测」要显示")

    def test_busy_read_disables_the_copy_button_while_running(self):
        """手机访问·已开启：「复制」按钮看得见，面板忙时要禁用，空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ onShown: !$("#phone-on").hidden,
           copyHidden: $("#btn-phone-address-copy").hidden,
           disabledBusy: $("#btn-phone-address-copy").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-address-copy").disabled });
""")
        busy, free = res
        self.assertTrue(busy["onShown"], "已开启时「已开启」那块要看得见")
        self.assertFalse(busy["copyHidden"], "已开启时「复制」要看得见")
        self.assertTrue(busy["disabledBusy"], "面板忙时复制按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_busy_read_disables_the_add_pair_button(self):
        """手机访问·已开启且手机已连接：「再配对一台手机」看得见，面板忙时要禁用，
        空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.state.paired_count = 1;
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ onShown: !$("#phone-on").hidden,
           addPairHidden: $("#btn-phone-add-pair").hidden,
           disabledBusy: $("#btn-phone-add-pair").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-add-pair").disabled });
""")
        busy, free = res
        self.assertTrue(busy["onShown"], "已连接时「已开启」那块要看得见")
        self.assertFalse(busy["addPairHidden"], "已连接时「再配对一台手机」要看得见")
        self.assertTrue(busy["disabledBusy"], "面板忙时再配对按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时同一颗按钮要可点")

    def test_cancel_failure_note_shows_in_the_progress_area(self):
        """手机控制·下载中且取消没生效：进度块下面那行要说「取消没有生效」，
        不让用户以为取消已经成功了；取消生效时这行要空。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: {
  download: { state: "downloading", downloaded: 1048576, total_bytes: 10485760 } } } };
window.PhonePanel.notes.loading = "取消没有生效，请稍后重试。";
window.PhonePanel.paint();
out.push({ loadingShown: !$("#phone-loading").hidden,
           errText: $("#phone-loading-error").textContent,
           errHidden: $("#phone-loading-error").hidden });
window.PhonePanel.notes.loading = "";
window.PhonePanel.paint();
out.push({ errTextAfterClear: $("#phone-loading-error").textContent });
""")
        data = res[0]
        self.assertTrue(data["loadingShown"], "下载中进度块要显示")
        self.assertEqual(data["errText"], "取消没有生效，请稍后重试。", "进度区要说明取消没生效")
        self.assertFalse(data["errHidden"], "这句说明要看得见")
        self.assertEqual(res[1]["errTextAfterClear"], "", "取消生效后这行要空")


class StartStopToggleUsePointTests(unittest.TestCase):
    """使用点·开启与关闭一组：启动中/关闭中/安装中，按钮和通道卡都要按住。"""

    def test_busy_and_pending_disable_the_channel_radios(self):
        """手机访问·已装未开启：两张通道单选卡看得见；面板忙或启动中都要禁用，
        空闲时可点——启动到一半换通道，拿到的地址会和界面对不上。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } } };
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ offShown: !$("#phone-off").hidden,
           tsDisabledBusy: $("#phone-chan-tailscale").disabled,
           cfDisabledBusy: $("#phone-chan-cloudflare").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ tsDisabledFree: $("#phone-chan-tailscale").disabled,
           cfDisabledFree: $("#phone-chan-cloudflare").disabled });
window.PhonePanel.pending = "starting";
window.PhonePanel.paint();
out.push({ tsDisabledPending: $("#phone-chan-tailscale").disabled,
           cfDisabledPending: $("#phone-chan-cloudflare").disabled });
window.PhonePanel.pending = "";
window.PhonePanel.paint();
out.push({ tsFreeAgain: $("#phone-chan-tailscale").disabled });
""")
        busy, free, pending, again = res
        self.assertTrue(busy["offShown"], "已装未开启时「未开启」块要看得见")
        self.assertTrue(busy["tsDisabledBusy"], "面板忙时 Tailscale 单选要禁用")
        self.assertTrue(busy["cfDisabledBusy"], "面板忙时 Cloudflare 单选要禁用")
        self.assertFalse(free["tsDisabledFree"], "面板空闲时单选要可点")
        self.assertFalse(free["cfDisabledFree"], "面板空闲时单选要可点")
        self.assertTrue(pending["tsDisabledPending"], "启动中 Tailscale 单选要禁用")
        self.assertTrue(pending["cfDisabledPending"], "启动中 Cloudflare 单选要禁用")
        self.assertFalse(again["tsFreeAgain"], "空闲时单选要可点")

    def test_pending_and_installing_disable_the_start_button(self):
        """手机访问·已装未开启：启动中「开启手机访问」说「启动中…」并禁用、lead 说正在
        开启，空闲时可点；安装中（进度块显示时）同一颗也要禁用，装完空闲时可点。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.advanced = { features: { phone_control: { ready: true } },
  channels: { tailscale: { available: true } } };
window.PhonePanel.pending = "starting";
window.PhonePanel.paint();
out.push({ offShown: !$("#phone-off").hidden,
           startHidden: $("#btn-phone-start").hidden,
           startText: $("#btn-phone-start").textContent,
           lead: $("#phone-feature-note").textContent,
           disabledPending: $("#btn-phone-start").disabled });
window.PhonePanel.pending = "";
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-start").disabled,
           freeText: $("#btn-phone-start").textContent });
window.PhonePanel.installing.phone_control = true;
window.PhonePanel.paint();
out.push({ loadingShown: !$("#phone-loading").hidden,
           disabledInstalling: $("#btn-phone-start").disabled });
window.PhonePanel.installing.phone_control = false;
window.PhonePanel.paint();
out.push({ disabledAfterInstallFlag: $("#btn-phone-start").disabled });
""")
        pending, free, installing, after = res
        self.assertTrue(pending["offShown"], "已装未开启时「未开启」块要看得见")
        self.assertFalse(pending["startHidden"], "启动中开启按钮要看得见")
        self.assertEqual(pending["startText"], "启动中…", "启动中按钮要说明自己在启动")
        self.assertEqual(pending["lead"], "正在开启，先不要切换通道。", "lead 要说正在开启")
        self.assertTrue(pending["disabledPending"], "启动中开启按钮要禁用")
        self.assertFalse(free["disabledFree"], "空闲时开启按钮要可点")
        self.assertEqual(free["freeText"], "开启手机访问")
        self.assertTrue(installing["loadingShown"], "安装中进度块要显示")
        self.assertTrue(installing["disabledInstalling"], "安装中开启按钮要禁用")
        self.assertFalse(after["disabledAfterInstallFlag"], "装完空闲时开启按钮要可点")

    def test_busy_and_pending_disable_the_stop_button(self):
        """手机访问·已开启：「关闭手机访问」看得见；面板忙时要禁用、空闲时可点；
        关闭进行中说「关闭中…」并禁用，空闲时按钮字回到「关闭手机访问」。"""
        res = run_js(PRELUDE + r"""
window.PhonePanel.state.running = true;
window.PhonePanel.busy = true;
window.PhonePanel.paint();
out.push({ onShown: !$("#phone-on").hidden,
           stopHidden: $("#btn-phone-stop").hidden,
           disabledBusy: $("#btn-phone-stop").disabled });
window.PhonePanel.busy = false;
window.PhonePanel.paint();
out.push({ disabledFree: $("#btn-phone-stop").disabled });
window.PhonePanel.pending = "stopping";
window.PhonePanel.paint();
out.push({ disabledPending: $("#btn-phone-stop").disabled,
           stopText: $("#btn-phone-stop").textContent });
window.PhonePanel.pending = "";
window.PhonePanel.paint();
out.push({ freeText: $("#btn-phone-stop").textContent });
""")
        busy, free, pending, again = res
        self.assertTrue(busy["onShown"], "已开启时「已开启」那块要看得见")
        self.assertFalse(busy["stopHidden"], "已开启时「关闭手机访问」要看得见")
        self.assertTrue(busy["disabledBusy"], "面板忙时关闭按钮要禁用")
        self.assertFalse(free["disabledFree"], "面板空闲时关闭按钮要可点")
        self.assertTrue(pending["disabledPending"], "关闭进行中按钮要禁用")
        self.assertEqual(pending["stopText"], "关闭中…", "关闭进行中按钮要说明自己在关闭")
        self.assertEqual(again["freeText"], "关闭手机访问")


if __name__ == "__main__":
    unittest.main()
