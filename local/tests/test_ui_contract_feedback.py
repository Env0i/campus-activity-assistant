# -*- coding: utf-8 -*-
"""界面契约：错误反馈与动作交错顺序。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import read, run_js  # noqa: E402


class ErrorFeedbackContractTests(unittest.TestCase):
    """错误说明唯一归属的静态契约：结果框/大屏/空态不再复读同一份错误说明。"""

    def test_apply_activities_failure_has_no_result_popup(self):
        """列表失败收尾不生成同义结果框：失败原话留给列表空态做唯一完整说明。"""
        js = read("ui/app.js")
        start = js.index("function applyActivities(")
        body = js[start:js.index("function render(", start)]
        self.assertNotIn("setResult(", body,
                         "列表失败收尾不得再弹同义结果框")
        self.assertIn("S.listError = res.text", body,
                      "失败原话必须记入 S.listError 供空态归因")

    def test_refresh_list_catch_has_no_result_popup(self):
        """refresh 的列表异常回调不再额外 setResult；只保留「未连接本机脚本」一处。"""
        js = read("ui/app.js")
        start = js.index("function refresh(")
        body = js[start:js.index("function applyActivities", start)]
        self.assertEqual(body.count("setResult("), 1,
                         "refresh 内只允许「未连接本机脚本」一处结果框")
        self.assertIn("还没有连接本机程序", body)
        self.assertIn("S.listError = msg(err)", body,
                      "桥接异常与 worker 失败同口径：原话归列表空态")

    def test_board_and_empty_no_longer_repeat_full_component_hint(self):
        """组件长说明与「重新检查」唯一归顶部横幅：大屏只留短状态、空态只留占位。"""
        js = read("ui/app.js")
        empty = js[js.index("function paintEmpty("):js.index("function paintCount(")]
        # 组件分支 = paintEmpty 里第一段；到「列表失败」分支为止（登录四态已抽成
        # loginEmptyState()，不再用 if (S.login.present) 当切片锚点）
        comp = empty[empty.index("if (S.runtime.error)"):
                     empty.index('if (S.listState === "error")')]
        self.assertNotIn("copy.hint", comp, "列表空态组件分支不得复读长说明")
        self.assertNotIn("重新检查", comp, "「重新检查」只能出现在顶部横幅")
        board = js[js.index("function paintSelected("):js.index("function setBoardTag(")]
        comp_board = board[board.index('S.runtime.error && S.listState !== "ready"'):
                           board.index('if (!S.busy && S.listState === "error"')]
        self.assertNotIn(".hint", comp_board, "大屏组件分支只留短状态")

    def test_list_error_copy_uses_real_failure_text(self):
        """空态归因用真实失败原话（S.listError），不再丢原话按空串猜。"""
        js = read("ui/app.js")
        empty = js[js.index("function paintEmpty("):js.index("function paintCount(")]
        self.assertIn('listErrorCopy(S.listError || "")', empty,
                      "空态归因必须用真实失败原话")


class ErrorFeedbackBehaviorTests(unittest.TestCase):
    """错误说明唯一归属的行为回归（node vm，不开浏览器、不调用学校）。"""

    def test_component_hint_only_in_banner_with_single_recheck(self):
        """组件错误：完整说明+重新检查只在顶部横幅；大屏/列表只留短状态与占位。"""
        res = run_js(r"""
setResult(null);   /* 桩里 #result 初始可见：先把结果框归零再进场景 */
S.runtime.error = "worker_missing";
S.listState = "error";
render();
const hint = RUNTIME_ERRORS.worker_missing.hint.slice(0, 10);
const banners = document.querySelector("#banners").innerHTML;
const board = document.querySelector("#board-text").textContent +
              document.querySelector("#selected").textContent;
const empty = document.querySelector("#empty-title").textContent +
              document.querySelector("#empty-text").textContent;
const action = document.querySelector("#empty-action");
const result = document.querySelector("#result");
/* 只数恢复入口（data-act="runtime-refresh" 按钮）：hint 文案本身含「重新检查」
 * 三个字，按字面量计数会把说明文本误当第二个入口 */
const recheck = (banners.match(/data-act="runtime-refresh"/g) || []).length +
  (action.hidden || action.textContent.indexOf("重新检查") < 0 ? 0 : 1);
out.push({ hintInBanner: banners.indexOf(hint) >= 0,
  hintInBoard: board.indexOf(hint) >= 0,
  hintInEmpty: empty.indexOf(hint) >= 0,
  resultVisible: !result.hidden,
  emptyActionHidden: action.hidden,
  recheck });
""")
        self.assertTrue(res[0]["hintInBanner"], "横幅必须承载完整组件说明")
        self.assertFalse(res[0]["hintInBoard"], "大屏不得复读长说明（只留短状态）")
        self.assertFalse(res[0]["hintInEmpty"], "列表空态只留未加载占位，不得复读长说明")
        self.assertFalse(res[0]["resultVisible"], "不得生成同义结果框")
        self.assertTrue(res[0]["emptyActionHidden"], "空态不得出现第二个「重新检查」")
        self.assertEqual(res[0]["recheck"], 1, "「重新检查」全页只能有一个")

    def test_list_failure_full_reason_only_in_empty_and_result_preserved(self):
        """普通列表失败：完整原因+重试只在列表空态；先放入的真实报名结果保留。"""
        res = run_js(r"""
setResult({ ok: true, title: "报名成功：校园夜跑", text: "建议去活动页确认一眼。" });
window.onBackend.activities({ ok: false, text: "学校接口 500 了", items: [] });
const result = document.querySelector("#result");
const action = document.querySelector("#empty-action");
out.push({
  resultKept: !result.hidden && result.innerHTML.indexOf("报名成功：校园夜跑") >= 0,
  resultText: result.innerHTML,
  emptyTitle: document.querySelector("#empty-title").textContent,
  emptyText: document.querySelector("#empty-text").textContent,
  retryText: action.hidden ? "" : action.textContent,
  board: document.querySelector("#board-text").textContent,
  banners: document.querySelector("#banners").innerHTML,
});
""")
        self.assertTrue(res[0]["resultKept"], "列表失败不得清掉真实报名结果")
        # 20261108-main-window LS12：失败空态的按钮照原型改名「刷新」，动作仍是重新拉列表，只改按钮名
        self.assertEqual(res[0]["retryText"], "刷新", "「刷新」只在列表空态")
        self.assertNotIn("报名成功", res[0]["emptyTitle"] + res[0]["emptyText"],
                         "空态说明与报名结果互不混写")
        self.assertNotIn("活动暂时没加载", res[0]["resultText"],
                         "结果框不得复读列表失败的完整说明")
        self.assertNotIn("脚本没跑通", res[0]["resultText"] + res[0]["board"],
                         "结果框与大屏都不得复读空态的完整原因")
        self.assertNotIn("程序组件", res[0]["banners"],
                         "普通列表失败不得冒充组件横幅")

    def test_component_recovery_restores_state(self):
        """组件故障恢复：本轮两分支都完成且无组件故障才撤横幅（轮次协议）。"""
        res = run_js(r"""
let resolveCheck, resolveList;
window.pywebview = { api: {
  check: () => new Promise((resolve) => { resolveCheck = resolve; }),
  list_activities: () => new Promise((resolve) => { resolveList = resolve; }),
}};
S.runtime.error = "worker_missing";
S.listState = "error";
render();
refresh(false);          /* 开启复查轮：两分支 pending，旧横幅保持到收口 */
await Promise.resolve();
resolveCheck({ ok: true, queued: true });
window.onBackend.check({ ok: true, result: "valid", hours_left: 10, session_present: true });
await Promise.resolve();
const bannerMidRound = document.querySelector("#banners").innerHTML.indexOf("程序组件缺失") >= 0;
resolveList({ ok: true, queued: true });
window.onBackend.activities({ ok: true, items: [] });
await Promise.resolve(); await Promise.resolve();
out.push({
  bannerMidRound,
  bannerGone: document.querySelector("#banners").innerHTML.indexOf("程序组件缺失") < 0,
  loginEnabled: !document.querySelector("#btn-login").disabled,
  runtimeCleared: !S.runtime.error,
});
""")
        self.assertTrue(res[0]["bannerMidRound"], "list 分支未完成时不得提前撤横幅")
        self.assertTrue(res[0]["runtimeCleared"], "本轮两分支完成且无故障后恢复")
        self.assertTrue(res[0]["bannerGone"], "恢复后横幅必须撤下")
        self.assertTrue(res[0]["loginEnabled"], "恢复后登录按钮必须解禁")


class ErrorFeedbackRoundtripTests(unittest.TestCase):
    """FB4 四入口组件码与刷新轮次恢复的行为回归（node vm + 受控 Promise 次序，不执行）。

    场景：A/B=check/list 两种到达顺序；C/D=login/start_plan 同步组件失败；
    E=同轮不互相撤、下一轮恢复、同步拒绝不悬挂 pending；F=真实业务结果保留与
    普通登录失败既有呈现。数 data-act 属性而非 hint 中的同名字样。
    """

    def test_check_valid_then_list_component_error_keeps_banner(self):
        """A：check valid 先到、list 组件故障后到——横幅恰一、控件禁用、无同义结果框。"""
        res = run_js(r"""
setResult(null);   /* 桩里 #result 初始可见：先归零再进场景 */
let resolveCheck, resolveList;
window.pywebview = { api: {
  check: () => new Promise((resolve) => { resolveCheck = resolve; }),
  list_activities: () => new Promise((resolve) => { resolveList = resolve; }),
}};
refresh(false);
await Promise.resolve();
resolveCheck({ ok: true, queued: true });
window.onBackend.check({ ok: true, result: "valid", hours_left: 10,
  session_present: true, estimated_expires_at: Date.now() / 1000 + 15 * 3600 });
await Promise.resolve();
resolveList({ ok: true, queued: true });
window.onBackend.activities({ ok: false, text: "程序组件缺失，请重新下载完整版本",
  items: [], runtime_error: "worker_missing" });
await Promise.resolve(); await Promise.resolve();
const banners = document.querySelector("#banners").innerHTML;
out.push({
  bannerHint: (banners.match(/无法找到所需程序组件/g) || []).length,
  recheck: (banners.match(/data-act="runtime-refresh"/g) || []).length,
  loginDisabled: document.querySelector("#btn-login").disabled,
  startDisabled: document.querySelector("#btn-plan").disabled,
  resultVisible: !document.querySelector("#result").hidden,
  runtime: S.runtime.error,
});
""")
        self.assertEqual(res[0]["bannerHint"], 1, "组件完整说明全页恰一次")
        self.assertEqual(res[0]["recheck"], 1, "恢复入口恰一个")
        self.assertTrue(res[0]["loginDisabled"], "缺组件时登录必须禁用")
        self.assertTrue(res[0]["startDisabled"], "缺组件时开始必须禁用")
        self.assertFalse(res[0]["resultVisible"], "不得生成同义结果框")
        self.assertEqual(res[0]["runtime"], "worker_missing")

    def test_list_component_error_then_check_valid_keeps_banner(self):
        """B：activities 组件故障先到、check valid 后到——横幅不得被同轮另一分支撤掉。"""
        res = run_js(r"""
let resolveCheck, resolveList;
window.pywebview = { api: {
  check: () => new Promise((resolve) => { resolveCheck = resolve; }),
  list_activities: () => new Promise((resolve) => { resolveList = resolve; }),
}};
refresh(false);
await Promise.resolve();
resolveList({ ok: true, queued: true });
window.onBackend.activities({ ok: false, text: "程序组件缺失，请重新下载完整版本",
  items: [], runtime_error: "worker_missing" });
await Promise.resolve();
const bannerAfterList = (document.querySelector("#banners").innerHTML
  .match(/无法找到所需程序组件/g) || []).length;
resolveCheck({ ok: true, queued: true });
window.onBackend.check({ ok: true, result: "valid", hours_left: 10, session_present: true });
await Promise.resolve(); await Promise.resolve();
const banners = document.querySelector("#banners").innerHTML;
out.push({
  bannerAfterList,
  bannerAfterCheck: (banners.match(/无法找到所需程序组件/g) || []).length,
  recheck: (banners.match(/data-act="runtime-refresh"/g) || []).length,
  runtime: S.runtime.error,
});
""")
        self.assertEqual(res[0]["bannerAfterList"], 1)
        self.assertEqual(res[0]["bannerAfterCheck"], 1, "同轮 check valid 后到不得撤组件横幅")
        self.assertEqual(res[0]["recheck"], 1)
        self.assertEqual(res[0]["runtime"], "worker_missing")

    def test_login_component_failure_banner_only(self):
        """C：login 同步组件失败只挂横幅，不再生成「登录没能开始」同义结果框。"""
        res = run_js(r"""
window.pywebview = { api: {
  login: () => Promise.resolve({ ok: false,
    text: "程序组件无法读取，请重新下载完整版本", error: "worker_permission" }),
}};
doLogin();
await Promise.resolve(); await Promise.resolve();
const banners = document.querySelector("#banners").innerHTML;
const result = document.querySelector("#result");
out.push({
  bannerHint: (banners.match(/被系统拦住或没有权限/g) || []).length,
  recheck: (banners.match(/data-act="runtime-refresh"/g) || []).length,
  resultVisible: !result.hidden,
  resultText: result.hidden ? "" : result.innerHTML.slice(0, 40),
  loginDisabled: document.querySelector("#btn-login").disabled,
  runtime: S.runtime.error,
});
""")
        self.assertEqual(res[0]["bannerHint"], 1, "组件说明只在横幅")
        self.assertEqual(res[0]["recheck"], 1)
        self.assertFalse(res[0]["resultVisible"], "组件失败不得再弹同义结果框")
        self.assertEqual(res[0]["runtime"], "worker_permission")
        self.assertTrue(res[0]["loginDisabled"], "组件横幅挂出后登录禁用")

    def test_start_plan_component_failure_banner_only(self):
        """D：start_plan 同步组件失败只挂横幅；提交中标志释放、按钮恢复可点文案。"""
        res = run_js(r"""
const item = { id: "a1", name: "活动", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, seconds_to_open: 1,
  state: "未开放", place: "", checkin_required: null, checkout_required: null };
S.items = [item];
S.byId = new Map([["a1", item]]);
S.listState = "ready";
S.login.result = "valid";
S.login.checking = false;
S.selected.add("a1");
S.demo = false;
window.pywebview = { api: {
  start_plan: () => Promise.resolve({ ok: false,
    text: "程序组件启动失败，请重新下载完整版本", error: "spawn_failed" }),
}};
startPlan();
await Promise.resolve(); await Promise.resolve();
const banners = document.querySelector("#banners").innerHTML;
out.push({
  bannerHint: (banners.match(/组件在但没能启动/g) || []).length,
  recheck: (banners.match(/data-act="runtime-refresh"/g) || []).length,
  resultVisible: !document.querySelector("#result").hidden,
  starting: S.starting,
  planText: document.querySelector("#btn-plan").textContent,
  runtime: S.runtime.error,
});
""")
        self.assertEqual(res[0]["bannerHint"], 1)
        self.assertEqual(res[0]["recheck"], 1)
        self.assertFalse(res[0]["resultVisible"], "组件失败不得生成同义失败结果框")
        self.assertFalse(res[0]["starting"], "提交中标志必须释放")
        self.assertEqual(res[0]["planText"], "开始报名计划", "拒绝后按钮恢复")
        self.assertEqual(res[0]["runtime"], "spawn_failed")

    def test_next_round_recovery_and_no_permanent_pending(self):
        """E：同轮不互相撤、下一轮两分支完成才恢复；同步拒绝不把 pending 卡死。"""
        res = run_js(r"""
let resolveCheck, resolveList;
window.pywebview = { api: {
  check: () => new Promise((resolve) => { resolveCheck = resolve; }),
  list_activities: () => new Promise((resolve) => { resolveList = resolve; }),
}};
refresh(false);
await Promise.resolve();
resolveList({ ok: true, queued: true });
window.onBackend.activities({ ok: false, text: "程序组件缺失，请重新下载完整版本",
  items: [], runtime_error: "worker_missing" });
await Promise.resolve();
resolveCheck({ ok: true, queued: true });
window.onBackend.check({ ok: false, result: "unknown", hours_left: null, session_present: true });
await Promise.resolve(); await Promise.resolve();
const bannerRound1 = document.querySelector("#banners").innerHTML
  .match(/无法找到所需程序组件/g).length;
/* 下一轮：check valid 先完成（list 未完成）→ 不得提前撤 */
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: true, queued: true }),
  list_activities: () => Promise.resolve({ ok: true, queued: true }),
}};
refresh(false);
await Promise.resolve();
window.onBackend.check({ ok: true, result: "valid", hours_left: 10, session_present: true });
await Promise.resolve();
const bannerMidRound = document.querySelector("#banners").innerHTML
  .match(/无法找到所需程序组件/g).length;
window.onBackend.activities({ ok: true, items: [] });
await Promise.resolve(); await Promise.resolve();
const bannerGone = document.querySelector("#banners").innerHTML
  .indexOf("程序组件缺失") < 0;
/* 第三轮：后端同步拒绝（无终态事件）不得把 pending 卡死 */
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: false, queued: false, text: "程序正在关闭，已取消本次检查" }),
  list_activities: () => Promise.resolve({ ok: false, queued: false }),
}};
refresh(false);
await Promise.resolve(); await Promise.resolve();
out.push({
  bannerRound1, bannerMidRound, bannerGone,
  loginEnabled: !document.querySelector("#btn-login").disabled,
  runtimeCleared: !S.runtime.error,
  pendingAfterRefusal: S.runtime.checkPending || S.runtime.listPending,
});
""")
        self.assertEqual(res[0]["bannerRound1"], 1)
        self.assertEqual(res[0]["bannerMidRound"], 1, "下一轮 list 未完成不得提前撤")
        self.assertTrue(res[0]["bannerGone"], "两分支都完成且无故障后撤横幅")
        self.assertTrue(res[0]["loginEnabled"])
        self.assertTrue(res[0]["runtimeCleared"])
        self.assertFalse(res[0]["pendingAfterRefusal"], "同步拒绝也必须有轮次终态")

    def test_business_results_survive_component_rounds(self):
        """F：真实报名结果在组件错误出现与恢复期间保留；普通登录失败仍按既有结果呈现。"""
        res = run_js(r"""
setResult({ ok: true, title: "报名成功：校园夜跑", text: "建议去活动页确认一眼。" });
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: true, queued: true }),
  list_activities: () => Promise.resolve({ ok: true, queued: true }),
}};
refresh(false);
await Promise.resolve();
window.onBackend.activities({ ok: false, text: "程序组件缺失，请重新下载完整版本",
  items: [], runtime_error: "worker_missing" });
await Promise.resolve(); await Promise.resolve();
const result = document.querySelector("#result");
const keptDuring = !result.hidden && result.innerHTML.indexOf("报名成功：校园夜跑") >= 0;
window.onBackend.activities({ ok: true, items: [] });
await Promise.resolve(); await Promise.resolve();
const keptAfter = !result.hidden && result.innerHTML.indexOf("报名成功：校园夜跑") >= 0;
/* 普通登录失败（非组件码）：既有「登录没能开始」结果框语义不变 */
window.pywebview = { api: {
  login: () => Promise.resolve({ ok: false, text: "[X] 窗口被关掉了" }),
}};
doLogin();
await Promise.resolve(); await Promise.resolve();
const loginResult = document.querySelector("#result");
out.push({
  keptDuring, keptAfter,
  bannerUp: document.querySelector("#banners").innerHTML
    .indexOf("无法找到所需程序组件") >= 0,
  normalLoginResultShown: !loginResult.hidden &&
    loginResult.innerHTML.indexOf("登录没能开始") >= 0,
});
""")
        self.assertTrue(res[0]["keptDuring"], "组件错误出现不得抹掉真实报名结果")
        self.assertTrue(res[0]["keptAfter"], "组件恢复也不得抹掉真实报名结果")
        self.assertTrue(res[0]["bannerUp"], "组件横幅与业务结果并存")
        self.assertTrue(res[0]["normalLoginResultShown"], "普通登录失败保持既有结果框语义")


class _ActionInterleaveMixin:
    """FB4-R1 交错场景的共享装置：受控 check/list/动作 Promise，全走生产动作路径。"""

    _CHECK_OK_EVENT = r"""
resolveCheck({ ok: true, queued: true });
window.onBackend.check({ ok: true, result: "valid", hours_left: 10, session_present: true });
await Promise.resolve();
"""
    _LIST_OK_EVENT = r"""
resolveList({ ok: true, queued: true });
window.onBackend.activities({ ok: true, items: [] });
await Promise.resolve();
"""

    @staticmethod
    def _interleave_snippet(action_key, prepare, body):
        template = r"""
__PREPARE__
setResult(null);   /* 结果桩初始可见：场景起点归零（生产动作自身也会清） */
let resolveCheck, resolveList, resolveAction;
window.pywebview = { api: {
  check: () => new Promise((resolve) => { resolveCheck = resolve; }),
  list_activities: () => new Promise((resolve) => { resolveList = resolve; }),
  __ACTION__: () => new Promise((resolve) => { resolveAction = resolve; }),
}};
__BODY__
const kept = {
  error: S.runtime.error,
  roundError: S.runtime.roundError,
  bannerHint: (document.querySelector("#banners").innerHTML
    .match(/无法找到所需程序组件|被系统拦住或没有权限|组件在但没能启动/g) || []).length,
  recheck: (document.querySelector("#banners").innerHTML
    .match(/data-act="runtime-refresh"/g) || []).length,
  resultVisible: !document.querySelector("#result").hidden,
  loginDisabled: document.querySelector("#btn-login").disabled,
  startDisabled: document.querySelector("#btn-plan").disabled,
  planText: document.querySelector("#btn-plan").textContent,
  starting: S.starting,
};
/* 下一轮完整复查：只有一分支完成时旧横幅还在；两分支无组件故障后恢复 */
window.pywebview = { api: {
  check: () => Promise.resolve({ ok: true, queued: true }),
  list_activities: () => Promise.resolve({ ok: true, queued: true }),
}};
refresh(false);
await Promise.resolve();
window.onBackend.check({ ok: true, result: "valid", hours_left: 10, session_present: true });
await Promise.resolve(); await Promise.resolve();
const midRound = (document.querySelector("#banners").innerHTML
  .match(/data-act="runtime-refresh"/g) || []).length;
window.onBackend.activities({ ok: true, items: [] });
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ kept, midRound,
  bannerGone: (document.querySelector("#banners").innerHTML
    .match(/data-act="runtime-refresh"/g) || []).length === 0,
  runtimeCleared: !S.runtime.error,
  roundCleared: !S.runtime.roundError,
  loginEnabled: !document.querySelector("#btn-login").disabled,
});
"""
        return (template.replace("__PREPARE__", prepare)
                .replace("__ACTION__", action_key)
                .replace("__BODY__", body))

    @staticmethod
    def _phase_orders():
        """动作失败前无分支成功 / check 先成功 / list 先成功 三种交错。"""
        return {
            "before-none": ("", _ActionInterleaveMixin._CHECK_OK_EVENT
                            + _ActionInterleaveMixin._LIST_OK_EVENT),
            "check-first": (_ActionInterleaveMixin._CHECK_OK_EVENT,
                            _ActionInterleaveMixin._LIST_OK_EVENT),
            "list-first": (_ActionInterleaveMixin._LIST_OK_EVENT,
                           _ActionInterleaveMixin._CHECK_OK_EVENT),
        }


class ActionInterleaveBehaviorTests(_ActionInterleaveMixin, unittest.TestCase):
    """FB4-R1：刷新未收尾时的登录/开始组件失败必须进入本轮累计（迟到成功不得撤）。

    每组经生产 doLogin()/startPlan() 进入（受控 Promise），覆盖三种交错顺序与
    下一轮恢复；零学校/浏览器/进程。本任务仅定义，不运行。
    """

    _START_PREPARE = r"""
const item = { id: "a1", name: "活动", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, seconds_to_open: 1,
  state: "未开放", place: "", checkin_required: null, checkout_required: null };
S.items = [item];
S.byId = new Map([["a1", item]]);
S.listState = "ready";
S.login.result = "valid";
S.login.checking = false;
S.selected.add("a1");
S.demo = false;
"""

    @staticmethod
    def _assert_kept_and_recovered(case, expected_code, expect_starting_released=False):
        kept = case["kept"]
        assert kept["error"] == expected_code, kept
        assert kept["roundError"] == expected_code, kept
        assert kept["bannerHint"] == 1, kept
        assert kept["recheck"] == 1, kept
        assert kept["resultVisible"] is False, kept
        assert kept["loginDisabled"] is True, kept
        assert kept["startDisabled"] is True, kept
        if expect_starting_released:
            assert kept["starting"] is False, kept
            assert kept["planText"] == "开始报名计划", kept
        assert case["midRound"] == 1, case
        assert case["bannerGone"] is True, case
        assert case["runtimeCleared"] is True, case
        assert case["roundCleared"] is True, case
        assert case["loginEnabled"] is True, case

    def test_login_component_failure_survives_late_refresh_success(self):
        """登录组：刷新未收尾时登录组件失败——迟到成功不得撤新横幅。"""
        payload = ('{ ok: false, error: "worker_permission", '
                   'text: "程序组件无法读取，请重新下载完整版本" }')
        for name, (before, after) in self._phase_orders().items():
            with self.subTest(order=name):
                body = ("refresh(false);\nawait Promise.resolve();\n" + before
                        + "\ndoLogin();\nawait Promise.resolve(); await Promise.resolve();\n"
                        + "resolveAction(" + payload + ");\n"
                        + "await Promise.resolve(); await Promise.resolve();"
                        + " await Promise.resolve();\n" + after)
                res = run_js(self._interleave_snippet("login", "", body))
                self.assertEqual(res[0]["kept"]["error"], "worker_permission")
                self._assert_kept_and_recovered(res[0], "worker_permission")

    def test_start_plan_component_failure_survives_late_refresh_success(self):
        """开始组：先点开始、刷新未收尾时动作失败——迟到成功不得撤新横幅。"""
        payload = ('{ ok: false, error: "worker_missing", '
                   'text: "程序组件缺失，请重新下载完整版本" }')
        for name, (before, after) in self._phase_orders().items():
            with self.subTest(order=name):
                body = ("startPlan();\nawait Promise.resolve();\n"
                        + "refresh(false);\nawait Promise.resolve();\n" + before
                        + "\nresolveAction(" + payload + ");\n"
                        + "await Promise.resolve(); await Promise.resolve();"
                        + " await Promise.resolve();\n" + after)
                res = run_js(self._interleave_snippet("start_plan",
                                                      self._START_PREPARE, body))
                self.assertEqual(res[0]["kept"]["error"], "worker_missing")
                self._assert_kept_and_recovered(res[0], "worker_missing",
                                                expect_starting_released=True)


class ErrorFeedbackRoundtripContractTests(unittest.TestCase):
    """FB4 接线的静态契约：四入口消费、轮次协议、提交中标志。"""

    def test_apply_activities_consumes_runtime_error(self):
        js = read("ui/app.js")
        body = js[js.index("function applyActivities("):js.index("function render(")]
        self.assertIn("noteRoundError(res.runtime_error)", body,
                      "列表失败必须先消费后端组件归类再渲染")
        self.assertIn('settleRefreshBranch("list")', body,
                      "activities 事件必须收口本轮 list 分支")

    def test_check_event_uses_round_protocol(self):
        js = read("ui/app.js")
        handler = js[js.index("window.onBackend"):]
        self.assertNotIn("S.runtime.error = data.runtime_error || null", handler,
                         "check 事件不得无条件覆盖组件结论（会抹掉同轮另一分支故障）")
        self.assertIn("S.runtime.roundError", handler, "check 终态必须进轮次故障累计")

    def test_login_and_start_plan_consume_component_codes(self):
        js = read("ui/app.js")
        login_body = js[js.index("function doLogin()"):
                        js.index("/* ---------------------------------------------------------------- 事件 */")]
        self.assertIn("RUNTIME_ERRORS[res.error]", login_body,
                      "登录同步失败必须只认可知组件码并走横幅")
        start_body = js[js.index("function startPlan()"):
                        js.index("function cancelTask(")]
        self.assertIn("RUNTIME_ERRORS[res.error]", start_body,
                      "开始计划的同步失败必须只认可知组件码并走横幅")
        self.assertIn("S.starting = true", start_body, "提交中标志必须置位")

    def test_action_failures_enter_round_accumulator(self):
        """FB4-R1：两个动作分支必须复用 noteRoundError（写 error+roundError），
        不得只写 S.runtime.error——否则刷新未收尾时迟到成功会撤掉新横幅。"""
        js = read("ui/app.js")
        login_body = js[js.index("function doLogin()"):
                        js.index("/* ---------------------------------------------------------------- 事件 */")]
        start_body = js[js.index("function startPlan()"):
                        js.index("function cancelTask(")]
        for label, body in (("doLogin", login_body), ("startPlan", start_body)):
            self.assertIn("noteRoundError(res.error)", body,
                          "%s 的组件失败必须进入本轮故障累计" % label)
            self.assertNotIn("S.runtime.error = res.error", body,
                             "%s 不得绕过累计函数只写显示态" % label)
        note = js[js.index("function noteRoundError("):
                  js.index("function settleRefreshBranch(")]
        self.assertIn("S.runtime.roundError = code", note)
        self.assertIn("S.runtime.error = code", note)
        gate = js[js.index("function updateControls("):
                  js.index("/* ---------------------------------------------------------------- 横幅 */")]
        self.assertIn("S.starting", gate, "提交中标志必须进入开始按钮门禁")


if __name__ == "__main__":
    unittest.main()
