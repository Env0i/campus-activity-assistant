#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计划栏新转移的行为测试：要你输验证码、停止没成功、快照对账与窗口恢复。

先断言用户看得到的（运行提示、按钮、说明、记录），再断言内部标记。
沙箱按 index.html 的加载顺序回放真实脚本；学校请求一律用本地桩。

@author Author
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import run_js  # noqa: E402
from test_prerefactor_fixes import run_ui  # noqa: E402

PRELUDE = r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.terms.version = "v1"; S.terms.acceptedVersion = "v1"; S.demo = false; S.online = true;
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
const running = (open) => {
  S.busy = true; S.stopping = false; S.editing = null; S.stopNote = null;
  S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
  S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", name: "活动甲",
    status: "waiting", attempts: 0, sign_start: open });
};
const warn = () => ({ text: $("#run-warn").textContent, html: $("#run-warn").innerHTML,
  hidden: $("#run-warn").hidden, tone: $("#run-warn").dataset.tone || "" });
const look = () => ({ warn: warn(), editing: S.editing || null, stopping: S.stopping,
  note: S.stopNote || null, logs: S.recentLogs.join("|"), stop: $("#btn-stop").textContent,
  plan: $("#btn-plan").textContent, board: $("#board-text").textContent,
  busy: S.busy, editNoteHidden: $("#edit-note").hidden });
const needHint = (mode) => {
  if (mode === "blocked") {
    window.onBackend.check({ ok: false, result: "expired", session_present: true,
      auto_state: "idle" });
    window.onBackend.login_auto({ auto_state: "blocked", auto_block: "ocr_missing" });
  } else {
    window.onBackend.check({ ok: false, result: "expired", session_present: true,
      auto_state: "handoff" });
  }
};
'''

TIMELY = "登录失效了，电脑认不出验证码。只要在 14:03:20 前输完验证码，计划照常继续；" \
         "否则 14:05:00 开放的那批会以“登录失效”结束。"


class RunWarnTransitionTests(unittest.TestCase):
    def test_needs_code_prompts_entering_captcha_when_time_allows(self):
        for mode in ("handoff", "blocked"):
            with self.subTest(mode=mode):
                data = run_js(PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:05:00"); needHint(%s); render();
out.push({ pill: $("#pill-text").textContent, warn: warn() });
''' % ('"' + mode + '"'))[0]
                self.assertEqual(data["pill"], "要你输验证码")
                self.assertIn(TIMELY, data["warn"]["text"])
                self.assertIn('data-act="login"', data["warn"]["html"])
                self.assertIn("输入验证码", data["warn"]["html"])

    def test_plain_expiry_keeps_the_original_relogin_sentence(self):
        data = run_js(PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:05:00");
window.onBackend.check({ ok: false, result: "expired", session_present: true,
  auto_state: "idle" }); render();
out.push(warn());
''')[0]
        self.assertIn("重新登录", data["text"])
        self.assertNotIn("电脑认不出验证码", data["text"])
        self.assertIn('data-act="login"', data["html"])

    def test_too_late_keeps_the_original_sentence_for_both_login_cases(self):
        for mode in ("handoff", "idle"):
            with self.subTest(mode=mode):
                data = run_js(PRELUDE + r'''
window.pywebview = { api: {} };
running("2026-11-06 14:00:30");
window.onBackend.check({ ok: false, result: "expired", session_present: true,
  auto_state: %s }); render();
out.push(warn());
''' % ('"handoff"' if mode == "handoff" else '"idle"'))[0]
                self.assertIn("来不及重新登录", data["text"])
                self.assertIn("这一批", data["text"])
                self.assertNotIn("data-act=", data["html"])


class StopFailureTransitionTests(unittest.TestCase):
    def test_stop_failure_while_editing_says_pausing_failed(self):
        data = run_js(PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); S.editing = { ids: [], doneN: 0 };
doStopPlan(); await flush(); render(); out.push(look());
''')[0]
        self.assertEqual(data["warn"]["text"], "没能暂停，计划照常进行。")
        self.assertEqual(data["warn"]["tone"], "warn")
        self.assertFalse(data["editing"])
        self.assertTrue(data["editNoteHidden"])
        self.assertIn("停止没成功，计划继续运行", data["logs"])
        self.assertEqual(data["note"], {"planId": "p1", "text": "没能暂停，计划照常进行。"})

    def test_plain_stop_failure_says_stopping_failed(self):
        data = run_js(PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush(); render(); out.push(look());
''')[0]
        self.assertEqual(data["warn"]["text"], "没能停止，计划照常进行。")
        self.assertEqual(data["warn"]["tone"], "warn")
        self.assertEqual(data["note"], {"planId": "p1", "text": "没能停止，计划照常进行。"})

    def test_login_hint_wins_over_a_stop_note(self):
        data = run_js(PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
needHint("handoff"); render(); out.push(look());
''')[0]
        self.assertIn(TIMELY.replace("14:03:20", "15:58:20")
                      .replace("14:05:00", "16:00:00"), data["warn"]["text"])
        self.assertIn("输入验证码", data["warn"]["html"])

    def test_another_stop_clears_the_previous_stop_note(self):
        data = run_js(PRELUDE + r'''
let first = true;
window.pywebview = { api: { stop_plan: () => first
  ? (first = false, Promise.reject(new Error("桥接断了"))) : new Promise(() => {}) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
const before = look();
doStopPlan(); render(); out.push({ before: before.note, after: look() });
''')[0]
        self.assertEqual(data["before"]["text"], "没能停止，计划照常进行。")
        self.assertIsNone(data["after"]["note"])
        self.assertTrue(data["after"]["warn"]["hidden"])

    def test_stop_note_from_an_earlier_plan_does_not_show_on_a_new_one(self):
        data = run_js(PRELUDE + r'''
window.pywebview = { api: { stop_plan: () => Promise.reject(new Error("桥接断了")) } };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
S.busy = true; S.stopping = false; S.editing = null;
S.plan = { id: "p2", status: "running", tasks: new Map(), source: "" };
S.plan.tasks.set("t2", { task_id: "t2", activity_id: "a2", name: "活动乙",
  status: "waiting", attempts: 0, sign_start: "2026-11-06 16:00:00" });
render(); out.push({ view: look(), planId: S.plan.id });
''')[0]
        self.assertNotIn("没能停止，计划照常进行。", data["view"]["warn"]["text"])
        self.assertTrue(data["view"]["busy"])
        self.assertEqual(data["view"]["note"]["planId"], "p1")
        self.assertNotEqual(data["view"]["note"]["planId"], data["planId"])


class StopResyncTransitionTests(unittest.TestCase):
    def test_no_such_plan_resyncs_from_bootstrap_instead_of_lying(self):
        data = run_js(PRELUDE + r'''
const calls = [];
window.pywebview = { api: {
  stop_plan: () => { calls.push("stop_plan"); return Promise.resolve({ ok: false,
    text: "当前没有这个计划" }); },
  bootstrap: () => { calls.push("bootstrap"); return Promise.resolve({ busy: false }); },
} };
running("2026-11-06 16:00:00"); doStopPlan(); await flush();
out.push({ calls: calls, view: look() });
''')[0]
        self.assertEqual(data["calls"], ["stop_plan", "bootstrap"])
        self.assertNotIn("正在停止", data["view"]["stop"])
        self.assertEqual(data["view"]["plan"], "开始报名计划")
        self.assertIn("可能还没公布报名时间", data["view"]["board"])
        self.assertFalse(data["view"]["busy"])
        self.assertFalse(data["view"]["stopping"])
        self.assertIsNone(data["view"]["note"])
        self.assertNotIn("照常进行", data["view"]["warn"]["text"])

    def test_window_return_drops_a_stale_stopping_flag(self):
        data = run_ui(r'''
setBusinessNow(Date.UTC(2026, 10, 6, 6, 0, 0));
S.busy = true; S.stopping = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
window.pywebview = { api: { bootstrap: () => Promise.resolve({ busy: false }),
  list_activities: () => Promise.resolve({ ok: true, items: [] }) } };
document.hidden = false;
window.__docListeners.visibilitychange.forEach((fn) => fn());
for (let i = 0; i < 8; i += 1) await Promise.resolve();
out.push({ stopping: S.stopping, stop: $("#btn-stop").textContent });
''')[0]
        self.assertFalse(data["stopping"])
        self.assertNotIn("正在停止", data["stop"])


if __name__ == "__main__":
    unittest.main()
