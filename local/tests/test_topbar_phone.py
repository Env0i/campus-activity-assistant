#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""顶栏的手机标识与手机详情卡：五种样子各一条，卡里的行与小标各一条。

走 fixtures.ui_harness 的整页沙箱（run_js）：摆一份 phone_access_state 快照与
PhonePanel.pending，画一遍，只看用户看得到的结果——标识写哪句字、什么颜色档、
转圈出不出来、读屏念什么，详情卡的小 chip、大字、副句、底部提醒与每一行。
样式表不在沙箱里，颜色与慢闪的最终样子由 design/evidence 里的截图脚本在 Edge 里核对。

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

# 公共桩：手机组件固定装好已启用（这批只看连接状态与过程），一套快照、一次整页重画
PRELUDE = r"""
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
    return run_js(PRELUDE + snippet)


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


if __name__ == "__main__":
    unittest.main()
