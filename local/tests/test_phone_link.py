#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机连接状态：设置抽屉的 chip、顶栏的手机标识、手机详情卡都在说「现在连着没有」。

一种状态或一条转移一个用例，走 fixtures.ui_harness 的整页沙箱（run_js）：摆一份
phone_access_state 快照，画一遍抽屉与顶栏，只看用户看得到的结果（写的是哪句字、
什么语气、标识出不出来、详情卡的小 chip 与大字），不对源码文本做断言。
「配过对没有」那几块（说明行、配对区、绿条、再配一台）与连接状态无关，同一快照
下换 link 必须一个字不变。

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

# 公共桩：手机组件固定装好已启用（这批只看连接状态），一套快照、一次整页重画、一份观测
PRELUDE = r"""
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
const __view = () => ({
  chip: [$("#phone-feature-status").hidden, $("#phone-feature-status").textContent,
         $("#phone-feature-status").className, $("#phone-feature-status").dataset.link],
  badge: [$("#phone-badge").hidden, $("#phone-badge-text").textContent,
          $("#phone-badge").className, $("#phone-badge").dataset.link],
  cardChip: [$("#phone-pop-chip-text").textContent, $("#phone-pop-chip").dataset.tone],
  cardBig: $("#phone-pop-big").textContent,
  pairRows: $("#phone-pop-rows").textContent,
});
const __pairBits = () => ({
  lead: $("#phone-feature-note").textContent,
  ok: $("#phone-ok").hidden,
  pair: $("#phone-pair").hidden,
  add: $("#btn-phone-add-pair").hidden,
  tip: $("#phone-cred-tip").hidden,
  rows: $("#phone-pop-rows").textContent,
});
"""

CONNECTED = "手机已连接"
WAITING = "等手机连接"


class LinkStateTests(unittest.TestCase):
    """四种连接状态各写什么字、什么语气、标识出不出现。"""

    def test_waiting_says_waiting_in_drawer_badge_and_card(self):
        """开着还没人来过：三处都写「等手机连接」，语气是提醒，标识没有 is-ok。"""
        view = run_js(PRELUDE + r"""
__set({ link: "waiting" });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"], [False, WAITING, "ph-st warn", "waiting"])
        self.assertEqual(view["badge"], [False, WAITING, "pill phone-badge", "waiting"])
        self.assertEqual(view["cardChip"], [WAITING, "warn"])
        self.assertEqual(view["cardBig"], WAITING)

    def test_connected_says_connected_everywhere(self):
        """最近两分钟手机来过：三处都是「已连接」那套字，标识与详情卡小 chip 都是 ok。"""
        view = run_js(PRELUDE + r"""
__set({ link: "connected", last_contact_ago_s: 12 });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"], [False, CONNECTED, "ph-st ok", "connected"])
        self.assertEqual(view["badge"], [False, CONNECTED, "pill phone-badge is-ok", "connected"])
        self.assertEqual(view["cardChip"], ["已连接", "ok"])
        self.assertEqual(view["cardBig"], CONNECTED)

    def test_disconnected_shows_how_long_ago_the_phone_left(self):
        """已断开：抽屉与标识写「已断开 · N 分钟前」，详情卡小 chip 只写「已断开」。"""
        view = run_js(PRELUDE + r"""
__set({ link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__view());
""")[0]
        title = "已断开 · 2 分钟前"
        self.assertEqual(view["chip"], [False, title, "ph-st", "disconnected"])
        self.assertEqual(view["badge"], [False, title, "pill phone-badge", "disconnected"])
        self.assertEqual(view["cardChip"], ["已断开", ""])
        self.assertEqual(view["cardBig"], title)

    def test_disconnected_without_a_contact_time_says_only_disconnected(self):
        """秒数是空的（从未有过来访）：只说「已断开」，不留一个空的「· 」。"""
        view = run_js(PRELUDE + r"""
__set({ link: "disconnected", last_contact_ago_s: null });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["chip"][:2], [False, "已断开"])
        self.assertEqual(view["badge"][:2], [False, "已断开"])
        self.assertEqual(view["cardBig"], "已断开")

    def test_phone_comes_back_and_the_words_return(self):
        """一条转移：已断开 → 手机又来了 → 回到「手机已连接」，标识重新带上 is-ok。"""
        before, after = run_js(PRELUDE + r"""
__set({ link: "disconnected", last_contact_ago_s: 4000 });
__paint();
out.push(__view());
__set({ link: "connected", last_contact_ago_s: 3 });
__paint();
out.push(__view());
""")
        self.assertEqual(before["chip"][1], "已断开 · 1 小时前")
        self.assertEqual(after["chip"], [False, CONNECTED, "ph-st ok", "connected"])
        self.assertEqual(after["badge"], [False, CONNECTED, "pill phone-badge is-ok", "connected"])

    def test_not_running_hides_the_badge_and_says_not_enabled(self):
        """没开：标识收起，抽屉 chip「未开启」，详情卡「未开启」「手机访问未开启」。"""
        view = run_js(PRELUDE + r"""
__set({ running: false, link: "off" });
__paint();
out.push(__view());
""")[0]
        self.assertEqual(view["badge"][0], True)
        self.assertEqual(view["badge"][3], "off")
        self.assertEqual(view["cardChip"], ["未开启", ""])
        self.assertEqual(view["cardBig"], "手机访问未开启")


class FallbackRuleTests(unittest.TestCase):
    """后端没给 link（老快照）或给 unknown 时，退回「配过对 / 有活动会话」的两档规则。"""

    def test_missing_link_falls_back_to_the_pairing_rule(self):
        """没有 link 字段：配过对就是「手机已连接」，没配过就是「等手机连接」。"""
        paired, waiting = run_js(PRELUDE + r"""
__set({ paired_count: 1 });
__paint();
out.push(__view());
__set({ paired_count: 0, live_session: false });
__paint();
out.push(__view());
""")
        self.assertEqual(paired["chip"], [False, CONNECTED, "ph-st ok", "connected"])
        self.assertEqual(waiting["chip"], [False, WAITING, "ph-st warn", "waiting"])

    def test_unknown_and_off_links_also_fall_back(self):
        """unknown 与「开着却给了 off」都当没有结论：有活动会话时仍按旧规则说已连接。"""
        unknown, off_link = run_js(PRELUDE + r"""
__set({ link: "unknown", live_session: true });
__paint();
out.push(__view());
__set({ link: "off", paired_count: 0, live_session: false });
__paint();
out.push(__view());
""")
        self.assertEqual(unknown["chip"][1], CONNECTED)
        self.assertEqual(unknown["cardChip"], ["已连接", "ok"])
        self.assertEqual(off_link["chip"], [False, WAITING, "ph-st warn", "waiting"])


class PairingIsNotLinkTests(unittest.TestCase):
    """「配过对没有」不看连接状态：同一份配对快照换 link，配对那几块一个字不变。"""

    def test_pairing_blocks_do_not_follow_the_link(self):
        """已配对的一台手机走了：说明行、绿条、再配一台、详情卡配对行照旧，只有连接那几处变。"""
        connected, gone = run_js(PRELUDE + r"""
__set({ paired_count: 1, link: "connected", last_contact_ago_s: 5 });
__paint();
out.push(__pairBits());
__set({ paired_count: 1, link: "disconnected", last_contact_ago_s: 150 });
__paint();
out.push(__pairBits());
""")
        self.assertEqual(gone, connected, "配过对的事实不受连接状态影响")
        self.assertIn("已配对，配对码已收起", connected["rows"],
                      "详情卡配对行看的是配过对没有，不是连着没有")
        self.assertFalse(connected["ok"], "绿条：配对码已换过的那条按配过对显示，不随连接状态")
        self.assertEqual(gone["add"], False, "配过对就能「再配一台手机」")


if __name__ == "__main__":
    unittest.main()
