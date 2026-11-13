#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电脑端奖励徽标（实践分 · 虚拟工资）：宽档侧边两枚标签、窄档 .sub 内联块、演示数据形态。

脚本按 index.html 加载序在 node 沙箱里回放；原型真源是 Main.dc.html 的 rwOf / .rw* 规则。
断行与像素以 Edge/WebView2 截图为准，这里只测文本、类名与 CSS 规则是否存在。

@author Author
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, run_js  # noqa: E402

SETUP = r"""
const mk = (extra) => Object.assign({ id: "r1", name: "测试活动", place: "教室", signed: false,
  checkin_required: false, checkout_required: false,
  sign_start: "2026-11-07 10:00:00", sign_end: "2026-11-08 10:00:00",
  act_start: "2026-11-09 08:00:00", act_end: "2026-11-09 17:00:00" }, extra);
const both = (item) => ({ side: rewardChips(item), inline: rewardInline(item) });
"""


class RewardTextTests(unittest.TestCase):
    def test_pending_ready_zero_and_missing(self):
        out = run_js(SETUP + r"""
out.push({
  pending: both(mk({ reward_state: "pending", points: null, wage: null })),
  absent: both(mk({})),
  full: both(mk({ reward_state: "ready", points: 2, wage: 20 })),
  half: both(mk({ reward_state: "ready", points: 0.5, wage: "5" })),
  zero: both(mk({ reward_state: "ready", points: 0, wage: 0 })),
  zeroWage: both(mk({ reward_state: "ready", points: 1, wage: 0 })),
  noPts: both(mk({ reward_state: "ready", points: null, wage: 20 })),
  noWage: both(mk({ reward_state: "ready", points: 3, wage: "" })),
  none: both(mk({ reward_state: "ready", points: null, wage: undefined })),
  pendingWithValues: both(mk({ reward_state: "pending", points: 9, wage: 9 })),
  evil: both(mk({ reward_state: "ready", points: "<b>x</b>", wage: 1 })),
  nothing: rewardChips(null),
});
""")[0]
        # 详情没回来：只写同步中，侧边带 title，内联用 .rw-i.p
        for key in ("pending", "absent", "pendingWithValues"):
            self.assertIn('<span class="rw-p">奖励同步中</span>', out[key]["side"], key)
            self.assertIn('title="奖励信息同步中"', out[key]["side"], key)
            self.assertNotIn("rw-c", out[key]["side"], key)
            self.assertIn('class="rw-i p"', out[key]["inline"], key)
            self.assertIn(">奖励同步中</span>", out[key]["inline"], key)
        self.assertNotIn("9", out["pendingWithValues"]["side"], "pending 时不显示可能残留的数值")
        # 有值
        side = out["full"]["side"]
        self.assertIn('<span class="rw-c pt"><b>2</b>分</span>', side)
        self.assertIn('<span class="rw-c wg">工资<b>20</b></span>', side)
        self.assertIn('title="实践分 2，虚拟工资 20"', side)
        self.assertIn('<span class="rw-i" title="实践分 2，虚拟工资 20">2 分 · 工资 20</span>', out["full"]["inline"])
        self.assertIn("0.5</b>分", out["half"]["side"])
        self.assertIn(">0.5 分 · 工资 5<", out["half"]["inline"])
        # 0 是真实回答，照实写
        self.assertIn("<b>0</b>分", out["zero"]["side"])
        self.assertIn("工资<b>0</b>", out["zero"]["side"])
        self.assertNotIn("未公布", out["zero"]["side"])
        self.assertIn(">0 分 · 工资 0<", out["zero"]["inline"])
        self.assertIn(">1 分 · 工资 0<", out["zeroWage"]["inline"])
        # 缺失：ready 才写未公布，类名带 na
        self.assertIn('<span class="rw-c pt na">分未公布</span>', out["noPts"]["side"])
        self.assertIn('<span class="rw-c wg">', out["noPts"]["side"])
        self.assertIn(">分未公布 · 工资 20<", out["noPts"]["inline"])
        self.assertIn('<span class="rw-c wg na">工资未公布</span>', out["noWage"]["side"])
        self.assertIn(">3 分 · 工资未公布<", out["noWage"]["inline"])
        self.assertIn('title="实践分 未公布，虚拟工资 未公布"', out["none"]["side"])
        self.assertIn(">分未公布 · 工资未公布<", out["none"]["inline"])
        self.assertNotIn("<b></b>", out["none"]["side"], "没有数值时不画空的 <b>")
        self.assertNotIn('class="rw-i p"', out["none"]["inline"], "ready 的缺失不是同步中")
        # 转义
        self.assertNotIn("<b>x</b>", out["evil"]["side"] + out["evil"]["inline"])
        self.assertEqual(out["nothing"], "")

    def test_row_outputs_both_variants_and_inline_sits_between_refund_and_requirements(self):
        out = run_js(SETUP + r"""
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const item = mk({ reward_state: "ready", points: 2, wage: 20, cancel_allowed: true });
window.onBackend.activities({ ok: true, items: [item] });
out.push(rowHtml(findItem("r1")));
""")[0]
        self.assertEqual(out.count('class="rw" '), 1, "侧边块带 title，类名后面还有属性")
        self.assertEqual(out.count('class="rw-i"'), 1)
        self.assertLess(out.index('class="rw" '), out.index('class="sub"'), "侧边标签在名字行")
        self.assertGreater(out.index('class="rw-i"'), out.index('class="sub"'), "内联块在 .sub 行")
        self.assertGreater(out.index('class="rw-i"'), out.index('class="rf"'), "在报后可退之后")
        self.assertGreater(out.index("无需签到"), out.index('class="rw-i"'), "在签到说明之前")


class RewardCssTests(unittest.TestCase):
    css = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")

    def rule(self, selector: str) -> str:
        m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_chip_rules_follow_the_prototype(self):
        self.assertIn("min-width: 3.125rem", self.rule(".c-main .rw-c.pt"))
        self.assertIn("min-width: 3.75rem", self.rule(".c-main .rw-c.wg"))
        self.assertIn("text-align: center", self.rule(".c-main .rw-c.pt"))
        self.assertIn("box-shadow: none", self.rule(".c-main .rw-c.na"))
        self.assertIn("margin-left: 0", self.rule(".c-main .rw-c b:first-child"))
        self.assertIn("display: none", self.rule(".c-main .rw-c b:empty"))

    def test_narrow_tier_swaps_side_chips_for_the_inline_block(self):
        self.assertIn("display: none", self.rule(".c-main .rw-i"), "宽档不显示内联块")
        m = re.search(r"@media \(max-width: 719px\)\s*\{\s*\.c-main \.rw \{ display: none; \}\s*"
                      r"\.c-main \.rw-i \{ display: inline; \}\s*\}", self.css)
        self.assertIsNotNone(m, "窄档（< 720px）隐藏侧边、显示内联")
        self.assertIn("color: var(--warn)", self.rule(".c-main .rw-i.p"))

    def test_selected_and_dim_rows(self):
        self.assertIn(".row.is-selected .rw-c, .row.is-selected .rw-i:not(.p)", self.css)
        self.assertIn(".row.is-signed .rw-c, .row.is-closed .rw-c", self.css)


class DemoRewardTests(unittest.TestCase):
    def test_every_demo_row_carries_reward_keys(self):
        sys.path.insert(0, str(LOCAL))
        try:
            from domain import demo_data
        finally:
            sys.path.pop(0)
        rows = demo_data.demo_items(1_700_000_000.0, lambda epoch=None: "T%s" % epoch)
        for row in rows:
            for key in ("points", "wage", "reward_state"):
                self.assertIn(key, row, row["id"])
            self.assertIn(row["reward_state"], ("ready", "pending"), row["id"])
            for key in ("points", "wage"):
                self.assertTrue(row[key] is None or isinstance(row[key], (int, float)), row["id"])
            if row["reward_state"] == "pending":
                self.assertIsNone(row["points"], row["id"])
                self.assertIsNone(row["wage"], row["id"])
        states = {r["id"]: r for r in rows}
        self.assertEqual(states["demo-volunteer"]["reward_state"], "pending")
        self.assertTrue(any(r["reward_state"] == "ready" and r["points"] is None and r["wage"] is None for r in rows))
        self.assertTrue(any(r["reward_state"] == "ready" and r["wage"] == 0 for r in rows))
        self.assertTrue(any(r["points"] == 0.5 for r in rows))


if __name__ == "__main__":
    unittest.main()
