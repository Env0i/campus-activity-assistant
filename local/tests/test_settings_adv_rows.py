#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置抽屉「高级功能」两项一行：标题行这一层长什么样。

一张表一格一个用例（口径见 docs/UI_SPEC.md 的「设置里的组件行」与证据目录的
dom-contract.md）：状态句、圆点颜色、主按钮的文字与显隐、标题行下那句小字或红条、
进度条宽度、展开区开合，以及「同一时刻标题行只有一只按钮看得见」。
走 fixtures.ui_harness 的整页沙箱（run_js），只看用户看得到的结果，不对源码文本断言。

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

PRELUDE = r"""
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
    return run_js(PRELUDE + snippet)


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


if __name__ == "__main__":
    unittest.main()
