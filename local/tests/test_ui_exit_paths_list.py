#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 1 出口行为测试·列表一组（计划 20261113-refactor-step1-exit-tests）。

每个 test_ 守 D2 变异表里的一个出口（编号见用例名）：在 node 沙箱里按
index.html 的加载序跑真实界面脚本、触发动作、看用户看得到的结果（列表骨架、
空态、运行记录），再断言状态值；不对源码文本做断言。
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

# 定时器桩：记下所有 setTimeout，用 __fire(ms) 精确触发 130 秒兜底；__flush 推进微任务
TIMERS = r"""
const __timers = [];
let __seq = 1;
setTimeout = (fn, ms) => { __timers.push({ id: __seq, fn: fn, ms: ms }); return __seq++; };
clearTimeout = (id) => {
  const at = __timers.findIndex((t) => t.id === id);
  if (at >= 0) __timers.splice(at, 1);
};
const __fire = (ms) => {
  const hit = __timers.find((t) => t.ms === ms);
  if (hit) { clearTimeout(hit.id); hit.fn(); }
  return !!hit;
};
const __flush = async (n = 8) => { for (let i = 0; i < n; i += 1) await Promise.resolve(); };
"""

# 业务现在 = 北京时间 2026-11-06 14:00；条款已同意、在线、非演示；运行记录逐行记账
PRELUDE = TIMERS + r"""
S.terms.version = "v1";
S.terms.acceptedVersion = "v1";
S.online = true;
S.demo = false;
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
const appended = [];
const logBox = $("#log");
const origAppend = logBox.appendChild;
logBox.appendChild = (child) => {
  appended.push(String(child.textContent).replace(/^\d\d:\d\d:\d\d\s+/, ""));
  return origAppend(child);
};
"""


class ListRoundExitTests(unittest.TestCase):
    """列表·加载中（S.listState）接续超时、条款回绝与没能开始三条出口。"""

    def test_R03_list_error_when_the_adopted_old_round_times_out(self):
        """列表·加载中：接续旧请求（skipped）后 130 秒仍没回包——骨架换成错误空态，
        运行记录写一句失败说明。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => new Promise(() => {}),
  list_activities: () => Promise.resolve({ skipped: true, request_id: "list-old-1" }),
} };
refresh(false);
await __flush();
const adopted = S.round.list;
const during = { state: S.listState };
__fire(130000);
await __flush();
out.push({ adopted, during, after: { state: S.listState, emptyHidden: $("#empty").hidden,
                                     lines: appended.slice() } });
""")
        data = res[0]
        self.assertEqual(data["adopted"], "list-old-1", "前提：请求号已接续回旧 owner")
        self.assertEqual(data["during"]["state"], "loading", "前提：接续后仍在加载中")
        self.assertEqual(data["after"]["state"], "error", "接续后的超时也要落错误空态")
        self.assertFalse(data["after"]["emptyHidden"], "用户要在空态里看到失败原因")
        self.assertTrue(any("活动列表没加载" in line for line in data["after"]["lines"]),
                        data["after"]["lines"])

    def test_R04_list_rejected_by_terms_lands_the_error_state_and_terms_gate(self):
        """列表·加载中：后端条款回绝——列表落错误空态，条款门禁重新弹到用户面前。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => new Promise(() => {}),
  list_activities: () => Promise.resolve({ ok: false, error: "terms_required",
                                           text: "请先同意使用条款" }),
} };
refresh(false);
await __flush();
out.push({ state: S.listState, emptyHidden: $("#empty").hidden,
           termsOpen: $("#dlg-terms").open === true });
""")
        data = res[0]
        self.assertEqual(data["state"], "error", "条款回绝不能让列表停在骨架")
        self.assertFalse(data["emptyHidden"])
        self.assertTrue(data["termsOpen"], "条款回绝要把条款面弹出来")

    def test_R05_list_could_not_start_lands_the_error_state_with_the_reason(self):
        """列表·加载中：后端说这次加载没能开始——列表落错误空态，运行记录写明原因。"""
        res = run_js(PRELUDE + r"""
window.pywebview = { api: {
  check: () => new Promise(() => {}),
  list_activities: () => Promise.resolve({ ok: false, text: "正在关闭，稍后再试" }),
} };
refresh(false);
await __flush();
out.push({ state: S.listState, emptyHidden: $("#empty").hidden,
           error: S.listError, lines: appended.slice() });
""")
        data = res[0]
        self.assertEqual(data["state"], "error")
        self.assertFalse(data["emptyHidden"])
        self.assertIn("正在关闭，稍后再试", data["error"])
        self.assertTrue(any("活动列表没加载" in line for line in data["lines"]), data["lines"])


if __name__ == "__main__":
    unittest.main()
