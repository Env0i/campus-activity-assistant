# -*- coding: utf-8 -*-
"""界面契约：时钟模型、未知时钟与重试退避。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, run_js  # noqa: E402


class ClockModelReliabilityTests(unittest.TestCase):
    """CB04/CB06：采样后漂移只计一次、真实校准年龄、单调 TTL。"""

    def test_sampled_uncertainty_does_not_double_count_age(self):
        res = run_js(r"""
const t0 = 1700000000000;
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 10, state: "ready",
  epoch_s: t0 / 1000, tick_s: 0, sampled_tick_s: 0,
  uncertainty_s: 0.47, source: "ntp", age_s: 400, reason: "测试注入" }, { rttMs: 0 });
const first = clockReading();
const ui1 = clockUiState();
const now1 = businessNowMs();
__advanceMono(10000);
const second = clockReading();
const ui2 = clockUiState();
const now2 = businessNowMs();
__advanceMono(490001);        /* age = 900.001s：真正过期仍禁用 */
const ui3 = clockUiState();
const now3 = businessNowMs();
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 11, state: "ready",
  epoch_s: t0 / 1000 + 1000, tick_s: 0, sampled_tick_s: 0,
  uncertainty_s: 0.5001, source: "ntp", age_s: 0, reason: "测试注入" }, { rttMs: 0 });
const ui4 = clockUiState();
const now4 = businessNowMs();
out.push({ unc1: first.uncertaintyMs, unc2: second.uncertaintyMs,
  age1: first.ageMs, age2: second.ageMs, deltaNow: now2 - now1,
  ui1, ui2, ui3, now3, ui4, now4, now1 });
""")
        row = res[0]
        self.assertIn(row["ui1"], ("ready", "holdover"),
                      "采样 age=400s、unc=0.47s 时后端仍可用，UI 不得提前禁用")
        self.assertIsNotNone(row["now1"])
        self.assertAlmostEqual(row["unc1"], 470.0, delta=0.5)
        self.assertAlmostEqual(row["unc2"] - row["unc1"], 1.0, delta=0.2,
                               msg="10 秒只增加约 1ms 漂移，不得再加采样前 40ms")
        self.assertAlmostEqual(row["age1"], 400000.0, delta=1.0)
        self.assertAlmostEqual(row["age2"], 410000.0, delta=1.0)
        self.assertAlmostEqual(row["deltaNow"], 10000.0, delta=1.0)
        self.assertIn(row["ui2"], ("ready", "holdover"))
        self.assertEqual(row["ui3"], "unavailable", "超过 900 秒仍必须禁用")
        self.assertIsNone(row["now3"])
        self.assertEqual(row["ui4"], "unavailable", "总误差超过 0.5 秒仍必须禁用")
        self.assertIsNone(row["now4"])

    def test_f5_old_anchor_reports_real_calibration_age(self):
        res = run_js(r"""
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 10, state: "ready",
  epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 600,
  uncertainty_s: 0.05, source: "ntp", age_s: 600, reason: "测试注入" });
out.push({ last: clockLastSyncText(), ui: clockUiState(),
  usable: businessNowMs() !== null });
""")
        row = res[0]
        self.assertEqual(row["last"], "10 分钟前",
                         "F5 接入 600 秒旧锚点必须显示真实年龄，不能刷新成「刚刚」")
        self.assertEqual(row["ui"], "holdover")
        self.assertTrue(row["usable"])

    def test_open_clock_pop_repaints_on_settlement(self):
        """浮层打开时状态收口必须重画浮层（UI_SPEC §5.16.13：浮层与顶栏同源）。"""
        res = run_js(r"""
S.clockPopOpen = true;
renderClockPop();
const readyHtml = document.querySelector("#clock-pop").innerHTML;
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 20,
  state: "unavailable", epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0,
  uncertainty_s: 0, source: "qa", age_s: 0, reason: "测试注入" });
const pop = document.querySelector("#clock-pop");
const unavailableHtml = pop.innerHTML;
const topState = document.querySelector("#clock").dataset.state;
/* 手动重试进入 syncing（resyncClock 的浮层呈现），失败收口必须解按钮锁 */
S.businessClock.syncState = "syncing";
S.businessClock.syncRequestRound = 20;
renderClockPop();
const syncingHtml = pop.innerHTML;
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 21,
  state: "ready", epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0,
  uncertainty_s: 0.1, source: "qa", age_s: 0, sync_status: "failed",
  sync_round: 21, reason: "测试注入" });
const settledHtml = pop.innerHTML;
out.push({ topState,
  readyHtml, unavailableHtml, syncingHtml, settledHtml });
""")
        row = res[0]
        self.assertIn("已校准", row["readyHtml"], "前置：浮层应显示 ready 状态")
        self.assertEqual(row["topState"], "unavailable", "顶栏已收口为 unavailable")
        self.assertIn("时间校准失败", row["unavailableHtml"],
                      "unavailable 收口后浮层状态行必须与顶栏同源，不得停留旧状态")
        self.assertIn('type="button" disabled>正在校准…</button>', row["syncingHtml"],
                      "前置：重试中浮层按钮应为禁用")
        self.assertNotIn(" disabled", row["settledHtml"],
                         "失败收口后浮层「重新校准时间」按钮必须解禁，不得永久锁死")
        self.assertIn('type="button">重新校准时间</button>', row["settledHtml"])

    def test_round_cache_ttl_uses_monotonic_elapsed(self):
        res = run_js(r"""
const realNow = Date.now;
let wall = 1700000000000;
Date.now = () => wall;
try {
  cacheRoundPayload("check", "r1", { ok: true });
  wall += 8 * 3600e3;                 /* OS 前移 8 小时 */
  const kept = takeRoundPayload("check", "r1");
  cacheRoundPayload("check", "r2", { ok: true });
  __advanceMono(130001);              /* 真正经过 130 秒才过期 */
  const expired = takeRoundPayload("check", "r2");
  cacheRoundPayload("check", "r3", { ok: true });
  wall -= 30 * 86400e3;               /* OS 回拨 30 天 */
  const keptBack = takeRoundPayload("check", "r3");
  out.push({ kept, expired, keptBack });
} finally {
  Date.now = realNow;
}
""")
        row = res[0]
        self.assertIsNotNone(row["kept"], "OS 前移不得让刚暂存的终态立刻过期")
        self.assertIsNone(row["expired"], "真正单调超过 130 秒必须过期")
        self.assertIsNotNone(row["keptBack"], "OS 回拨不得延长缓存期限")

    def test_skipped_ack_replays_cached_terminal_across_wall_jumps(self):
        for offset in (8 * 3600e3, -30 * 86400e3):
            res = run_js(r"""
const realNow = Date.now;
let wall = 1700000000000;
Date.now = () => wall;
try {
  S.round.check = "owner-new";
  S.round.gen.check = 1;
  S.login.checking = true;
  S.login.result = null;
  window.onBackend.check({ request_id: "owner-old", ok: true, result: "valid",
    session_present: true, hours_left: 3 });
  wall += %d;
  settleSynchronous({ skipped: true, request_id: "owner-old" }, "check");
  out.push({ result: S.login.result, checkId: S.round.check,
    cacheLeft: S.round.cache.length });
} finally {
  Date.now = realNow;
}
""" % offset)
            row = res[0]
            self.assertEqual(row["result"], "valid",
                             "OS 跳变 %s 后 skipped ack 仍须立即重放暂存终态" % offset)
            self.assertEqual(row["checkId"], "owner-old")
            self.assertEqual(row["cacheLeft"], 0)

    def test_true_monotonic_expiry_drops_cached_terminal(self):
        res = run_js(r"""
S.round.check = "owner-new";
S.login.checking = true;
window.onBackend.check({ request_id: "owner-old", ok: true, result: "valid",
  session_present: true, hours_left: 3 });
__advanceMono(130001);
settleSynchronous({ skipped: true, request_id: "owner-old" }, "check");
out.push({ result: S.login.result, cacheLeft: S.round.cache.length });
""")
        row = res[0]
        self.assertIsNone(row["result"], "真正超过 130 秒后不得重放暂存终态")
        self.assertLessEqual(row["cacheLeft"], 1, "过期项不得被取用重放")

    def test_wait_for_bridge_uses_monotonic_bound(self):
        res = run_js(r"""
const realNow = Date.now;
const realTimeout = setTimeout;
let wall = 1700000000000;
Date.now = () => wall;
setTimeout = (fn) => { __advanceMono(50); wall += 3600e3; fn(); return 1; };
const start = __monoValue();
try {
  const ok = await waitForBridge(15000);
  out.push({ ok: ok, elapsed: __monoValue() - start });
} finally {
  Date.now = realNow;
  setTimeout = realTimeout;
}
""")
        row = res[0]
        self.assertFalse(row["ok"])
        self.assertGreaterEqual(row["elapsed"], 14950,
                                "15 秒承诺必须按单调经过时长，不能被 OS 前移提前结束")


class UnknownClockDisplayTests(unittest.TestCase):
    """CB05：校时失败不得冒充「学校还没公布报名时间」。"""

    ITEMS = r"""
const items = [
  { id: "a", name: "已知开放时间", sign_start: "2026-10-27 09:00:00",
    sign_end: "2026-10-27 18:00:00", act_start: "2026-10-28 09:00:00",
    act_end: "2026-10-28 11:00:00", place: "A", signed: false },
  { id: "b", name: "已报名活动", sign_start: "2026-10-27 10:00:00",
    sign_end: "2026-10-27 18:00:00", act_start: "2026-10-28 09:00:00",
    act_end: "2026-10-28 11:00:00", place: "B", signed: true, state: "已报名" },
  { id: "c", name: "时间未公布", sign_start: "",
    sign_end: "", act_start: "2026-10-29 09:00:00",
    act_end: "2026-10-29 11:00:00", place: "C", signed: false }
];
applyActivities({ ok: true, items: items }, true);
"""

    def test_known_start_without_trusted_now_is_pending_calibration(self):
        res = run_js(self.ITEMS + r"""
S.selected.clear();
markClockUnavailable("校时失败");
render();
const rows = $("#rows").innerHTML;
out.push({ rows, board: $("#selected").textContent,
  boardText: $("#board-text").innerHTML,
  metric: $("#metric-free").textContent });
""")
        row = res[0]
        rows = row["rows"]
        # A 有已知开放时间：保留绝对时间并标「待校准」，不得进「报名时间待公布」
        row_a = rows.split('data-id="a"', 1)[1].split('data-id="b"', 1)[0]
        self.assertIn("待校准", row_a)
        self.assertIn("09:00", row_a, "已知绝对时间必须保留")
        # C 真正缺 sign_start：仍然是「待公布」
        row_c = rows.split('data-id="c"', 1)[1]
        self.assertIn("待公布", row_c)
        self.assertRegex(rows, r"报名时间待公布.*?count\">1 场",
                         "待公布组只能包含真正缺开放时间的活动")
        # B 已报名事实保留
        row_b = rows.split('data-id="b"', 1)[1].split('data-id="c"', 1)[0]
        self.assertIn("已报名", row_b)
        # 大屏：不得断言没有可报名场次，只给时间待校准与单一恢复入口
        self.assertEqual(row["board"], "时间待校准")
        self.assertNotIn("没有可报名的场次", row["board"] + row["boardText"])
        self.assertIn("校准北京时间", row["boardText"])
        self.assertEqual(row["boardText"].count("data-open-clock"), 1,
                         "恢复入口必须唯一")
        self.assertEqual(row["metric"], "待确认", "未知计数不得伪造 0 或 6")

    def test_recovery_recomputes_groups_counts_and_keeps_selection(self):
        res = run_js(self.ITEMS + r"""
S.selected.clear();
S.selected.add("a");
S.retryPolicy = { retry_for_s: 600, max_attempts: 2 };
markClockUnavailable("校时失败");
render();
const beforeMetric = $("#metric-free").textContent;
const beforeCountdown = $("#countdown").textContent;
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 30,
  state: "ready", epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0,
  uncertainty_s: 0.05, source: "harness", age_s: 0, reason: "恢复" });
S.businessClock.attempted = true;
render();
const rows = $("#rows").innerHTML;
out.push({ beforeMetric, beforeCountdown,
  metric: $("#metric-free").textContent,
  countdown: $("#countdown").textContent,
  selected: Array.from(S.selected), policy: S.retryPolicy,
  rowA: rows.split('data-id="a"')[1].split('data-id="b"')[0] });
""")
        row = res[0]
        self.assertEqual(row["beforeMetric"], "待确认")
        self.assertIn("待校准", row["beforeCountdown"])
        self.assertRegex(row["metric"], r"^\d+$",
                         "恢复后计数必须回到真实数字")
        self.assertNotIn("待校准", row["countdown"],
                         "恢复后倒计时必须原地重算")
        self.assertEqual(row["selected"], ["a"], "恢复不得丢掉选择")
        self.assertEqual(row["policy"], {"retry_for_s": 600, "max_attempts": 2},
                         "恢复不得重置重试策略")
        self.assertNotIn("待校准", row["rowA"])
        self.assertNotIn("待公布", row["rowA"])

    def test_runtime_component_copy_points_to_redownload_and_recheck(self):
        res = run_js(r"""
out.push({ hint: RUNTIME_ERRORS.worker_missing.hint,
  title: RUNTIME_ERRORS.worker_missing.title });
""")
        row = res[0]
        self.assertIn("无法找到所需程序组件", row["hint"])
        self.assertIn("重新下载完整版本", row["hint"])
        self.assertIn("重新检查", row["hint"])
        self.assertNotIn("没跟着程序", row["hint"])


class ClockRetryBackoffDisplayTests(unittest.TestCase):
    """R1：首轮校时失败后自动退避重试，界面要说清「什么时候再试」与失败原因。"""

    def test_retrying_state_exposes_countdown_and_whitelisted_reason(self):
        res = run_js(r"""
ingestBusinessClock({ schema: 1, owner_id: "harness-clock", generation: 12,
  state: "unavailable", epoch_s: null, tick_s: null, sampled_tick_s: null,
  uncertainty_s: null, source: "", age_s: null, reason: "本轮没有可用的时间源响应",
  sync_status: "failed", sync_round: 3, retry_attempt: 2, retry_in_s: 9.4,
  last_failure_source: "ntp.aliyun.com", last_failure_reason: "timeout" }, { rttMs: 0 });
S.businessClock.attempted = true;
out.push({ ui: clockUiState(), hint: clockRetryText(), due: clockRetryDueText(),
  source: clockFailureSourceText(), reason: clockFailureReasonText(),
  now: businessNowMs() });
""")
        row = res[0]
        self.assertEqual(row["ui"], "retrying", "排了退避就要显示「正在重试」而不是直接失败")
        self.assertIn("正在重试", row["hint"])
        self.assertEqual(row["due"], "10 秒后", "剩余秒数向上取整，避免显示 0 秒后")
        self.assertEqual(row["source"], "ntp.aliyun.com")
        self.assertEqual(row["reason"], "网络超时", "白名单原因要翻成人话")
        self.assertIsNone(row["now"], "校时失败时不得回退系统时间")

    def test_backoff_fields_and_copy_are_wired_through_ui(self):
        state_js = (LOCAL / "ui" / "state" / "clock.js").read_text(encoding="utf-8")
        pop_js = (LOCAL / "ui" / "views" / "clock-pop.js").read_text(encoding="utf-8")
        top_js = (LOCAL / "ui" / "views" / "clock.js").read_text(encoding="utf-8")
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        styles = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")
        for field in ("retry_attempt", "retry_in_s", "last_failure_source",
                      "last_failure_reason"):
            self.assertIn(field, state_js, "快照字段必须逐个读出，不能靠缺键猜")
        self.assertIn("正在重试", state_js)
        self.assertIn("重试校准", pop_js, "失败态的按钮要说清点它会发生什么")
        for label in ("下一次重试", "最近失败来源", "最近失败原因"):
            self.assertIn(label, pop_js)
        self.assertIn("clock-retry-hint", html)
        self.assertIn("clock-retry-hint", top_js)
        self.assertIn('[data-state="retrying"]', styles)


if __name__ == "__main__":
    unittest.main()
