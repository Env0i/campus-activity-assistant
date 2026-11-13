# -*- coding: utf-8 -*-
"""界面契约：三态筛选、双模式、课表分组、空偏好与列表刷新。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read, run_js  # noqa: E402


class FilterControlTests(unittest.TestCase):
    """两个筛选控件：全部/需要/无需 三态都必须存在。"""

    def test_index_has_checkin_and_checkout_selects(self):
        html = read("ui/index.html")
        for key in ("checkin", "checkout"):
            self.assertIn('id="%s"' % key, html, "index.html 缺少 #%s 筛选控件" % key)
            self.assertIn('aria-label="%s要求"' % ("签到" if key == "checkin" else "签退"), html,
                          "#%s 需要 aria 名称，状态不能只靠位置表达" % key)
        for key in ("checkin", "checkout"):
            for value, label in (("all", "全部"), ("yes", "需要"), ("no", "无需")):
                self.assertIn('<option value="%s">%s</option>' % (value, label), html,
                              "#%s 缺少「%s」选项（%s）" % (key, label, value))

    def test_app_js_keeps_filter_prefs(self):
        js = read("ui/app.js")
        # 保存与恢复：filter 里的 checkin/checkout 必须进偏好
        self.assertIn('savePrefs({ filter: Object.assign({}, S.filter) })', js,
                      "筛选变化必须保存进偏好（savePrefs filter）")
        for key in ("checkin", "checkout"):
            self.assertIn('%s: ["all", "yes", "no"]' % key, js,
                          "applyPrefs 必须校验 %s 的三态取值" % key)


class TriStateContractTests(unittest.TestCase):
    """tri-state 字段名与 unknown 保留规则：null 不得降级成无需。"""

    def test_grab_normalizes_explicit_aliases_only(self):
        py = read("grab.py")
        self.assertIn("CHECKIN_FLAG_NAMES", py, "grab.py 缺少签到别名列")
        self.assertIn("CHECKOUT_FLAG_NAMES", py, "grab.py 缺少签退别名列")
        # 无法归一化的值必须保持 None，禁止猜成 False
        self.assertIn("return None", py, "_tri_state 对未知值必须返回 None")
        self.assertIn("not in (None, \"\")", py, "空值字段必须当作未知（跳过），不能当无需")
        # list --json 输出必须带两项 tri-state 字段
        self.assertIn('"checkin_required": act.get("checkin_required")', py,
                      "list --json 必须原样透传 checkin_required")
        self.assertIn('"checkout_required": act.get("checkout_required")', py,
                      "list --json 必须原样透传 checkout_required")

    def test_grab_tri_state_function_semantics(self):
        """_tri_state 的三态语义直接在 Python 里验证，不依赖浏览器。"""
        import sys
        sys.path.insert(0, str(LOCAL))
        try:
            import grab
        finally:
            sys.path.pop(0)
        self.assertIs(grab._tri_state(True), True)
        self.assertIs(grab._tri_state(1), True)
        self.assertIs(grab._tri_state("是"), True)
        self.assertIs(grab._tri_state(False), False)
        self.assertIs(grab._tri_state(0), False)
        self.assertIs(grab._tri_state("否"), False)
        # 未知字符串、缺失、空串、未确认数字都必须是 None
        for unknown in (None, "", "maybe", "2", "未知"):
            self.assertIsNone(grab._tri_state(unknown),
                              "未知值 %r 必须归一化为 None" % unknown)
        self.assertIsNone(grab._activity_flag({"qiandao": "随便"}, ("qiandao",)),
                          "未知别名取值必须保持 None")

    def test_app_js_filter_excludes_null_only_for_yes_no(self):
        js = read("ui/app.js")
        self.assertIn("function matchesFlag", js, "app.js 缺少筛选匹配函数 matchesFlag")
        # 需要和无需排除 null；全部保留 null —— 这条规则是文案级别的契约
        self.assertIn("if (value === null) return false;", js,
                      "matchesFlag 必须在需要/无需分支排除 null（未知不得误判）")
        self.assertIn('if (filter === "all") return true;', js,
                      "matchesFilter 的「全部」必须保留未知项")
        # 行内未知文案：详情未回/已回但没数据分开说，绝不写成「无需」
        self.assertIn("签到时间待确认", js, "行内必须显示「签到时间待确认」而不是留空")
        self.assertIn("签退时间待确认", js, "行内必须显示「签退时间待确认」而不是留空")
        self.assertIn("签到信息同步中", js, "详情未返回时必须显示「签到信息同步中」")

    def test_app_js_tri_state_normalize(self):
        js = read("ui/app.js")
        self.assertIn("item.checkin_required = triState(item.checkin_required)", js,
                      "列表数据必须经 triState 归一化 checkin_required")
        self.assertIn("item.checkout_required = triState(item.checkout_required)", js,
                      "列表数据必须经 triState 归一化 checkout_required")

    def test_demo_covers_tri_state_and_missing_time(self):
        """demo 样本必须能稳定复现筛选边界：true/false/null、已报名、活动时间缺失。"""
        import sys
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        finally:
            sys.path.pop(0)
        items = local_app.demo_items()
        flags = {(it["checkin_required"], it["checkout_required"]) for it in items}
        self.assertIn((True, False), flags, "demo 缺少「需要签到」样本")
        self.assertIn((False, True), flags, "demo 缺少「需要签退」样本")
        self.assertIn((None, None), flags, "demo 缺少「签到/签退未知」样本")
        self.assertIn((None, True), flags, "demo 缺少「签到未知但需签退」的混合样本")
        self.assertTrue(any(it["signed"] for it in items), "demo 缺少「已报名」样本")
        missing = [it for it in items if not it["act_start"] or not it["act_end"]]
        self.assertTrue(missing, "demo 缺少「活动时间缺失」样本")
        for it in items:
            self.assertIn("checkin_required", it)
            self.assertIn("checkout_required", it)
            self.assertIn(it["state"], ("已报名", "开放中", "未开放"),
                          "demo 的 state 必须用 list --json 同款中文口径")


class FilterIsolationTests(unittest.TestCase):
    """筛选只影响可见行：全局下一场、冲突校验、计划都基于全量数据。"""

    def test_next_open_uses_all_items(self):
        js = read("ui/app.js")
        self.assertIn("function nextOpen()", js)
        # nextOpen 内遍历的是 S.items（全量），不经过 filtered()
        start = js.index("function nextOpen()")
        body = js[start:js.index("function groupSelected")]
        self.assertIn("S.items.forEach", body, "nextOpen 必须基于全量 S.items，不受筛选影响")
        self.assertNotIn("filtered()", body, "nextOpen 不得使用 filtered() 的结果")

    def test_validation_uses_selected_items(self):
        js = read("ui/app.js")
        start = js.index("function validateSelection()")
        body = js[start:start + 1200]
        self.assertIn("selectedItems()", body, "冲突校验必须基于已选集合，而不是可见行")


class DualModeUiContractTests(unittest.TestCase):
    """双模式契约（静态）：模式文案、开放优先、已截止禁选、路线独立
    checkpoint、统一 deadline、startPlan 载荷与恢复合并不丢运行时字段。"""

    def test_mode_of_and_mode_texts(self):
        """modeOf 三分类与三种正式模式文案必须存在（预报名/立即报名/已截止）。"""
        js = read("ui/app.js")
        self.assertIn("function modeOf(", js, "缺少模式分类函数 modeOf")
        self.assertIn('pre_register: "预报名"', js, "缺少预报名文案")
        self.assertIn('instant_signup: "立即报名"', js, "缺少立即报名文案")
        self.assertIn('closed: "已截止"', js, "缺少已截止文案")
        # 模式只做展示与即时门禁：后端仍是最终权威
        self.assertIn("def classify_signup_mode", read("signup_plan.py"),
                      "后端必须有唯一模式分类口径 classify_signup_mode")

    def test_next_open_prefers_open_activity(self):
        """nextOpen 返回 openId/futureId；存在开放活动时 bestId 优先 openId。"""
        js = read("ui/app.js")
        start = js.index("function nextOpen()")
        body = js[start:js.index("function groupSelected", start)]
        for key in ("openId", "futureId", "bestId"):
            self.assertIn(key, body, "nextOpen 必须返回 %s（开放优先于未来场次）" % key)
        self.assertIn("isEligibleForPlan", body, "已截止活动不得参与下一场")

    def test_closed_activity_cannot_enter_plan(self):
        """已截止禁选：复选框禁用、整行点击拒绝、校验拒绝、统计排除。"""
        js = read("ui/app.js")
        self.assertIn("function isEligibleForPlan(", js,
                      "缺少统一可报名判据 isEligibleForPlan")
        # 复选框与整行点击共用同一份判据
        self.assertIn("check.disabled = S.busy || S.starting || termsLocked() || !isEligibleForPlan(item)", js,
                      "复选框必须同时受忙、启动中、条款门与已截止四道限制")
        start = js.index("function toggleSelection(")
        body = js[start:js.index("function clearSelection", start)]
        self.assertIn("!isEligibleForPlan(item)", body,
                      "整行点击路径也必须拒绝已截止活动")
        self.assertIn("isEligibleForPlan(item)", body, "复选框 change 路径必须过门禁")
        # validateSelection 明确拒绝已截止
        val_start = js.index("function validateSelection(")
        val_body = js[val_start:val_start + 1600]
        self.assertIn('modeOf(item) === "closed"', val_body,
                      "前端校验必须拒绝已截止活动")
        self.assertIn("报名已截止", val_body, "拒绝文案要说明报名已截止")
        # 统计口径排除已截止
        self.assertIn("S.items.filter(isEligibleForPlan)", js,
                      "可报名统计必须排除已截止")
        # 后端最终防线：拒绝策略在 domain.plan_rules，start_plan 仍走这条门禁
        rules = read("domain/plan_rules.py")
        self.assertIn("sign_end_passed", rules,
                      "start_plan 必须拒绝已截止活动（后端最终防线）")
        self.assertIn("报名已截止", rules, "拒绝时要返回具体说明")
        py = read("app.py")
        start_plan = py.index("def start_plan")
        plan_body = py[start_plan:py.index("def cancel_task", start_plan)]
        self.assertIn("closed_items_error", plan_body,
                      "start_plan 必须经 closed_items_error 过已截止门禁")

    def test_start_plan_payload_carries_sign_end_and_mode(self):
        """startPlan 显式传 sign_end 与 signup_mode，后端缺口数据也能拦截。"""
        js = read("ui/app.js")
        start = js.index("const items = selectedItems().map((item) => ({")
        body = js[start:js.index("}));", start)]
        self.assertIn("sign_end:", body, "start_plan 载荷必须带 sign_end")
        self.assertIn("signup_mode:", body, "start_plan 载荷必须带 signup_mode")

    def test_route_uses_independent_station_checkpoints(self):
        """路线图站点独立判断：真实 checkpoint 才 done，历史开放不抢占当前节点。"""
        js = read("ui/app.js")
        start = js.index("function paintRoute()")
        body = js[start:js.index("function routeDeadline", start)]
        for field in ("run_started_at", "page_opened_at", "watch_started_at"):
            self.assertIn(field, body, "路线站点必须用真实 checkpoint：%s" % field)
        self.assertIn("done: runStarted !== null", body,
                      "「本次启动」只有真实 checkpoint 才算 done")
        self.assertIn("done: openDone", body,
                      "原定开放是时间参考节点（历史开放标 done 但不抢占当前节点）")

    def test_unified_effective_retry_deadline(self):
        """路线/任务卡/LED 共用 effectiveRetryDeadline，不再固定回退 120 秒。"""
        js = read("ui/app.js")
        self.assertIn("function effectiveRetryDeadline(", js, "缺少统一截止函数")
        self.assertIn("function retryDeadline(task) {\n  return effectiveRetryDeadline(task);\n}",
                      js, "任务卡/LED 的旧入口必须并入统一推导")
        rd_start = js.index("function routeDeadline(")
        self.assertIn("effectiveRetryDeadline", js[rd_start:rd_start + 300],
                      "路线图截止必须走统一函数")
        # 推导口径：任务 retry_for_s 与 sign_end 截断，不是写死 120 秒
        ed_start = js.index("function effectiveRetryDeadline(")
        ed_body = js[ed_start:js.index("function retryDeadline", ed_start)]
        self.assertIn("task.retry_for_s", ed_body, "截止推导必须用任务携带的策略时长")
        self.assertIn("toTs(task.sign_end)", ed_body, "截止推导必须被 sign_end 截断")

    def test_plan_merge_keeps_runtime_fields(self):
        """晚到 plan 事件与页面重载恢复不得抹掉已收到的运行时字段。"""
        js = read("ui/app.js")
        self.assertIn("TASK_RUNTIME_FIELDS", js, "缺少运行时字段清单")
        self.assertIn("function mergeTask(", js, "缺少任务合并函数 mergeTask")
        for anchor in ("function handlePlan(", "function handleTask(",
                       "function ingestBootstrapPlan("):
            anchor_at = js.index(anchor)
            body = js[anchor_at:anchor_at + 900]
            self.assertIn("mergeTask(", body,
                          "%s 必须经 mergeTask 合并，不能整对象覆盖" % anchor.strip("function ("))

    def test_task_card_shows_signup_mode(self):
        """混合计划每个任务卡显示自己的模式。"""
        js = read("ui/app.js")
        start = js.index("function taskHtml(")
        body = js[start:js.index("function updateControls(", start)]
        self.assertIn("signup_mode", body, "任务卡必须读取任务的 signup_mode")
        self.assertIn("taskModePrefix(task)", body, "任务卡必须使用统一的模式文案")
        cards = run_js(r"""
const task = { task_id: "mode", name: "模式样本", status: "waiting",
  sign_start: "2099-01-01 09:00:00" };
out.push(taskHtml({ ...task, signup_mode: "pre_register" }));
out.push(taskHtml({ ...task, signup_mode: "instant_signup" }));
""")
        self.assertIn("预报名 · ", cards[0])
        self.assertIn("立即报名 · ", cards[1])

    def test_task_card_shows_submit_phase(self):
        """提交中任务卡照原型 card 的 submitting 支：只写次数、上限、最近原因和重试截止，不写阶段名。

        旧口径（UI_SPEC 5.8-6）显示「黄金风暴 / 常规全速 / 404 自适应」；原型 Main.dc.html 的 card 没有阶段名，
        计划 20261106-plan-panel 的 run-panel F 要求去掉。phase 字段仍可能随事件到达，任何取值都不得冒出阶段名。
        """
        cards = run_js(r"""
const task = { task_id: "phase", name: "阶段样本", status: "submitting",
  attempts: 1 };
out.push(taskHtml({ ...task, phase: "golden" }));
out.push(taskHtml({ ...task, phase: "full_speed" }));
out.push(taskHtml({ ...task, phase: "adaptive_backoff" }));
out.push(taskHtml({ ...task, phase: "unknown_kind" }));
out.push(taskHtml({ ...task }));
""")
        for card in cards:
            for label in ("黄金风暴", "常规全速", "404 自适应"):
                self.assertNotIn(label, card, "原型 card 不显示阶段名，任何 phase 都不编造文案")
            self.assertIn("已提交 1 次（不限次数）。", card, "提交中说明照原型 card：次数与上限")
            self.assertNotIn(" · 黄金", card)

    def test_starting_gates_selection_contract(self):
        """S.starting 期间锁定所有选择入口与可见控件：函数级门禁 + DOM disabled 一致。"""
        js = read("ui/app.js")
        # 函数级：toggleSelection 与 clearSelection 的第一道门禁必须同时拦 S.busy 与 S.starting
        self.assertIn("function toggleSelection(", js)
        start = js.index("function toggleSelection(")
        body = js[start:js.index("function clearSelection", start)]
        self.assertIn("if (S.busy || S.starting) return;", body,
                      "toggleSelection 必须在第一行同时拦截 busy 与 starting")
        clear_start = js.index("function clearSelection(")
        clear_body = js[clear_start:clear_start + 200]
        self.assertIn("if (S.busy || S.starting) return;", clear_body,
                      "clearSelection 必须在第一行同时拦截 busy 与 starting")
        # DOM 控件：清空按钮与 row-check disabled 必须包含 S.starting
        self.assertIn('$("#btn-clear-plan").disabled = S.busy || S.starting ||', js,
                      "清空按钮 disabled 必须包含 S.starting")
        self.assertIn("check.disabled = S.busy || S.starting ||", js,
                      "row-check disabled 必须包含 S.starting")


class TimetableGroupingBehaviorTests(unittest.TestCase):
    """M4/M5：groupTimetable 五场活动各归其位，不依赖本机时区。

    钉住 open.push / closed.push / signed.push 不串槽：改坏其中一个，这条用例必须变红。
    """

    def test_group_timetable_places_each_activity_in_its_correct_group(self):
        """五场活动：正在开放 / 等开放 / 报名时间待公布 / 已截止 / 已报名，各归其位。"""
        res = run_js(r"""
// 北京时间 2026-11-06 10:00:00（UTC+8）
const nowMs = new Date(Date.UTC(2026, 10, 6, 2, 0, 0)).getTime();
setBusinessNow(nowMs);

const openAct = {
  id: "open-1", name: "正在开放活动",
  sign_start: "2026-11-06 09:00:00", sign_end: "2026-11-06 11:00:00",
  act_start: "2026-11-07 09:00:00", act_end: "2026-11-07 11:00:00",
  signed: false, place: "地点 A"
};
const waitingAct = {
  id: "wait-1", name: "等开放活动",
  sign_start: "2026-11-07 09:00:00", sign_end: "2026-11-07 11:00:00",
  act_start: "2026-11-08 09:00:00", act_end: "2026-11-08 11:00:00",
  signed: false, place: "地点 B"
};
const unknownAct = {
  id: "unk-1", name: "时间待公布活动",
  sign_start: "", sign_end: "",
  act_start: "", act_end: "",
  signed: false, place: "地点 C"
};
const closedAct = {
  id: "closed-1", name: "已截止活动",
  sign_start: "2026-11-05 09:00:00", sign_end: "2026-11-05 11:00:00",
  act_start: "2026-11-06 09:00:00", act_end: "2026-11-06 11:00:00",
  signed: false, place: "地点 D"
};
const signedAct = {
  id: "signed-1", name: "已报名活动",
  sign_start: "2026-11-06 08:00:00", sign_end: "2026-11-06 10:00:00",
  act_start: "2026-11-07 08:00:00", act_end: "2026-11-07 10:00:00",
  signed: true, place: "地点 E"
};

const rows = [openAct, waitingAct, unknownAct, closedAct, signedAct];
const html = groupTimetable(rows);

// 提取每组内容做断言：每个活动名恰好出现在一个组里
function sectionContent(label) {
  const idx = html.indexOf("<b>" + label + "</b>");
  if (idx < 0) return "";
  // 找下一个 section.gsec 或结尾
  const nextSec = html.indexOf('<section class="gsec"', idx + 1);
  const end = nextSec >= 0 ? nextSec : html.length;
  return html.substring(idx, end);
}

const openHtml = sectionContent("正在开放");
const unknownHtml = sectionContent("报名时间待公布");
const closedHtml = sectionContent("已截止");
const signedHtml = sectionContent("已报名");

out.push({
  openHasOpen: openHtml.includes("正在开放活动"),
  openHasNotWaiting: !openHtml.includes("等开放活动"),
  openHasNotUnknown: !openHtml.includes("时间待公布活动"),
  openHasNotClosed: !openHtml.includes("已截止活动"),
  openHasNotSigned: !openHtml.includes("已报名活动"),

  unknownHasUnknown: unknownHtml.includes("时间待公布活动"),
  closedHasClosed: closedHtml.includes("已截止活动"),
  signedHasSigned: signedHtml.includes("已报名活动"),

  unknownOnly: unknownHtml.includes("时间待公布活动") && !unknownHtml.includes("正在开放活动") && !unknownHtml.includes("等开放活动") && !unknownHtml.includes("已截止活动") && !unknownHtml.includes("已报名活动"),
  closedOnly: closedHtml.includes("已截止活动") && !closedHtml.includes("正在开放活动") && !closedHtml.includes("等开放活动") && !closedHtml.includes("时间待公布活动") && !closedHtml.includes("已报名活动"),
  signedOnly: signedHtml.includes("已报名活动") && !signedHtml.includes("正在开放活动") && !signedHtml.includes("等开放活动") && !signedHtml.includes("时间待公布活动") && !signedHtml.includes("已截止活动"),

  // 等开放活动应该在日期分组里（不在以上四个固定组）
  waitingInDayGroup: html.includes("等开放活动") && !openHtml.includes("等开放活动")
    && !unknownHtml.includes("等开放活动") && !closedHtml.includes("等开放活动")
    && !signedHtml.includes("等开放活动"),

  groupCount: (html.match(/<section class="gsec"/g) || []).length,
});
""")
        row = res[0]
        self.assertTrue(row["openHasOpen"],
                        "「正在开放」组应含 open 活动")
        self.assertTrue(row["openHasNotWaiting"],
                        "「正在开放」组不得含 waiting 活动")
        self.assertTrue(row["openHasNotUnknown"],
                        "「正在开放」组不得含 unknown 活动")
        self.assertTrue(row["openHasNotClosed"],
                        "「正在开放」组不得含 closed 活动")
        self.assertTrue(row["openHasNotSigned"],
                        "「正在开放」组不得含 signed 活动")
        self.assertTrue(row["unknownHasUnknown"],
                        "「报名时间待公布」组应含 unknown 活动")
        self.assertTrue(row["closedHasClosed"],
                        "「已截止」组应含 closed 活动")
        self.assertTrue(row["signedHasSigned"],
                        "「已报名」组应含 signed 活动")
        self.assertTrue(row["unknownOnly"],
                        "「报名时间待公布」组只能含 unknown 那一场")
        self.assertTrue(row["closedOnly"],
                        "「已截止」组只能含 closed 那一场")
        self.assertTrue(row["signedOnly"],
                        "「已报名」组只能含 signed 那一场")
        self.assertTrue(row["waitingInDayGroup"],
                        "waiting 活动应在日期分组里，不在四个固定组")
        self.assertEqual(row["groupCount"], 5,
                         "恰好五个分组：正在开放、一个日期组、待公布、已报名、已截止（LS01 起已报名在已截止前）")


class EmptyPreferenceBehaviorTests(unittest.TestCase):
    """UX-01/03 + 清筛选：空态按真实原因给下一步，清筛选不重置用户策略。"""

    def test_known_zero_has_no_login_nudge(self):
        """登录有效 + 成功返回 0 场：指标写 0，空态不再诱导登录，大屏不重复原因。"""
        res = run_js(r"""
S.items = [];
S.byId = new Map();
S.listState = "ready";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.selected = new Set();
render();
out.push({ title: document.querySelector("#empty-title").textContent,
  text: document.querySelector("#empty-text").textContent,
  total: document.querySelector("#metric-total").textContent,
  free: document.querySelector("#metric-free").textContent,
  action: document.querySelector("#empty-action").textContent,
  boardTitle: document.querySelector("#selected").textContent,
  boardText: document.querySelector("#board-text").textContent });
""")
        case = res[0]
        self.assertEqual(case["title"], "学校当前没有返回活动")
        self.assertNotIn("重新登录", case["text"])
        self.assertNotIn("点右上角", case["text"], "登录有效时不得再给登录下一步")
        self.assertEqual(case["total"], "0", "已知零条必须写 0，不是破折号")
        self.assertEqual(case["free"], "0")
        # 原型 Main.dc.html:2096 的按钮就叫「刷新」：刷新本身已是统一入口，
        # 「重新加载」是自造词（计划 desktop-copy 的 W8）。
        self.assertEqual(case["action"], "刷新")
        # 计划栏 1:1（draft-panel A）：原型 draft 段 0 场时标题「学校当前没有活动」、副行「稍后刷新再看。」
        self.assertEqual(case["boardTitle"], "学校当前没有活动")
        self.assertEqual(case["boardText"], "稍后刷新再看。")
        self.assertNotIn("还没公布", case["boardText"], "大屏不得把已知零说成还没公布")

    def test_list_empty_subline_uses_current_wording(self):
        """学校返回 0 场：副行先说「这不是登录问题」，再给刷新（设计第 6 节四种空态）。

        取代旧的「副行说学校当前没有返回可报名活动」：标题已经是这句，副行不再重复，
        改为排除登录原因并给下一步；仍不得残留「学校这次」变体，也不再用「登录是有效的」开头。"""
        list_src = read("ui/views/list.js")
        self.assertIn("这不是登录问题。", list_src)
        self.assertIn("学校发布新活动后会出现在这里", list_src)
        self.assertNotIn("学校这次", list_src)
        self.assertNotIn("登录是有效的，学校当前没有返回", list_src)

    def test_board_and_list_share_one_empty_sentence(self):
        """学校返回 0 场：计划栏与列表空态各用原型那一句，两处都钉住，防止再分叉成第三种说法。

        旧口径是两处一字不差；现在的原型两处本来就不同：计划栏 draft 段写「学校当前没有活动」/「稍后刷新再看。」，
        列表 empty 写「学校当前没有返回活动」（计划 20261106-plan-panel 的 draft-panel A，见 plan_amendments）。
        """
        panel = read("ui/views/plan-panel.js")
        self.assertIn('"学校当前没有活动"', panel)
        self.assertIn('"稍后刷新再看。"', panel)
        self.assertNotIn("学校当前没有返回活动", panel, "计划栏照原型 draft 段，不用列表那一句")
        self.assertIn("学校当前没有返回活动", read("ui/views/list.js"))

    def test_login_states_get_their_own_next_step(self):
        """none→登录、expired→重新登录、unknown→刷新（且不得说成过期）。"""
        res = run_js(r"""
function snapshot() {
  render();
  return { title: document.querySelector("#empty-title").textContent,
    text: document.querySelector("#empty-text").textContent,
    action: document.querySelector("#empty-action").textContent };
}
S.items = []; S.byId = new Map(); S.listState = "ready";
S.login.present = false; S.login.result = "none"; S.login.checking = false;
const none = snapshot();
S.login.present = true; S.login.result = "expired"; S.login.ok = false;
const expired = snapshot();
S.login.result = "unknown"; S.login.ok = false;
const unknown = snapshot();
out.push({ none, expired, unknown });
""")
        case = res[0]
        self.assertEqual(case["none"]["title"], "登录后查看活动")
        self.assertIn("「登录」", case["none"]["text"])
        self.assertIn("重新登录", case["expired"]["title"])
        self.assertIn("「重新登录」", case["expired"]["text"])
        self.assertEqual(case["unknown"]["title"], "暂时无法确认登录状态")
        for banned in ("过期", "重新登录"):
            self.assertNotIn(banned, case["unknown"]["text"],
                             "unknown 一律不得说成过期或要求重登")
        self.assertEqual(case["unknown"]["action"], "刷新")

    def test_error_and_idle_are_not_known_zero(self):
        """还没拉到 / 拉失败都不是「学校零活动」：指标未知，原因各归其位。"""
        res = run_js(r"""
function snapshot() {
  render();
  return { title: document.querySelector("#empty-title").textContent,
    text: document.querySelector("#empty-text").textContent,
    total: document.querySelector("#metric-total").textContent };
}
S.items = []; S.byId = new Map(); S.listState = "idle";
S.login.result = "valid"; S.login.present = true;
const idle = snapshot();
S.listState = "error"; S.listError = "连不上学校站点";
const error = snapshot();
out.push({ idle, error });
""")
        case = res[0]
        self.assertEqual(case["idle"]["title"], "还没有加载活动列表")
        self.assertEqual(case["idle"]["total"], "—", "没拉到之前是未知，不是 0")
        self.assertNotIn("学校当前没有返回活动", case["error"]["title"],
                         "网络失败不得伪装成学校零活动")
        self.assertEqual(case["error"]["total"], "—")

    def test_component_banner_keeps_single_owner(self):
        """组件问题仍只有横幅一个归属：空态不复读说明、不重复恢复按钮。"""
        res = run_js(r"""
S.items = []; S.byId = new Map(); S.listState = "error"; S.listError = "程序组件缺失";
S.runtime.error = "worker_missing";
S.login.result = "valid"; S.login.present = true;
render();
const html = document.querySelector("#banners").innerHTML;
out.push({ title: document.querySelector("#empty-title").textContent,
  text: document.querySelector("#empty-text").textContent,
  actionHidden: document.querySelector("#empty-action").hidden,
  rechecks: (html.match(/data-act="runtime-refresh"/g) || []).length,
  hints: (html.match(/无法找到所需程序组件/g) || []).length });
""")
        case = res[0]
        # 20261108-main-window LS16：缺组件空态标题照原型 broken 画板改为「活动列表没加载」
        self.assertEqual(case["title"], "活动列表没加载")
        self.assertNotIn("登录", case["text"], "缺组件不许显示成「登录后查看活动」")
        self.assertTrue(case["actionHidden"], "空态不重复恢复按钮")
        self.assertEqual(case["rechecks"], 1, "横幅只有一个恢复入口")
        self.assertEqual(case["hints"], 1, "完整原因只出现一次")

    def test_clear_filter_keeps_retry_policy_and_other_prefs(self):
        """清筛选只重置 6 个筛选键：600/3、浏览器开关、日志、引导版本全部保留。"""
        res = run_js(r"""
const item = { id: "a1", name: "活动A", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, state: "未开放" };
S.items = [normalize(item)];
S.byId = new Map([["a1", S.items[0]]]);
S.listState = "ready";
S.prefs = { retry_policy: { retry_for_s: 600, max_attempts: 3 }, headed: true,
  log_open: true, tour_version: 2, tour_completed_at: "2026-01-01T00:00:00Z",
  legacy_unknown: "keep" };
S.retryPolicy = { retry_for_s: 600, max_attempts: 3 };
S.logOpen = true;
S.filter = { q: "zzz", status: "free", time: "today", sort: "name",
  checkin: "yes", checkout: "no" };
/* 控件此刻显示用户设的 600 / 3：修复前 applyPrefs 会把它们打回 120 / 0 */
document.querySelector("#retry-for").value = "600";
document.querySelector("#max-attempts").value = "3";
const saved = [];
savePrefs = (patch) => { saved.push(patch); Object.assign(S.prefs, patch); };
render();
const emptyTitle = document.querySelector("#empty-title").textContent;
document.querySelector("#empty-action").click();
const payload = saved[saved.length - 1] || {};
out.push({ emptyTitle,
  filter: Object.assign({}, S.filter),
  retryFor: S.retryPolicy.retry_for_s, maxAttempts: S.retryPolicy.max_attempts,
  retrySelect: document.querySelector("#retry-for").value,
  maxInput: document.querySelector("#max-attempts").value,
  policy: S.prefs.retry_policy, headed: S.prefs.headed, logOpen: S.logOpen,
  tourVersion: S.prefs.tour_version, tourStamp: S.prefs.tour_completed_at,
  legacy: S.prefs.legacy_unknown,
  payloadKeys: Object.keys(payload), payloadFilter: payload.filter,
  q: document.querySelector("#q").value });
""")
        case = res[0]
        self.assertEqual(case["emptyTitle"], "没有符合筛选的活动")
        self.assertEqual(case["retryFor"], 600, "清筛选不得把重试时长打回默认")
        self.assertEqual(case["maxAttempts"], 3)
        self.assertEqual(case["retrySelect"], "600", "控件值必须还是用户设的 10 分钟")
        self.assertEqual(case["maxInput"], "3", "控件值必须还是用户设的 3 次")
        self.assertEqual(case["policy"]["retry_for_s"], 600, "偏好里的策略必须原样保留")
        self.assertTrue(case["headed"], "浏览器开关偏好必须保留")
        self.assertTrue(case["logOpen"], "运行记录展开状态必须保留")
        self.assertEqual(case["tourVersion"], 2, "引导内容版本必须保留")
        self.assertEqual(case["tourStamp"], "2026-01-01T00:00:00Z")
        self.assertEqual(case["legacy"], "keep", "未识别的偏好键不得被清掉")
        self.assertEqual(case["payloadKeys"], ["filter"], "save_prefs 只写过滤器差量")
        self.assertEqual(case["payloadFilter"]["q"], "")
        self.assertEqual(case["payloadFilter"]["status"], "all")
        self.assertEqual(case["filter"]["sort"], "open", "排序也要回到默认")
        self.assertEqual(case["q"], "", "搜索框跟着清空")

    def test_start_plan_payload_keeps_policy_after_clear(self):
        """清筛选后再开始：start_plan 载荷里的策略仍是 600/3。"""
        res = run_js(r"""
let sent = null;
window.pywebview = { api: {
  start_plan: (items, headed, policy) => {
    sent = { items, headed, policy };
    return Promise.resolve({ ok: true, plan_id: "p1" });
  },
} };
const item = { id: "a1", name: "活动A", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, state: "未开放" };
S.items = [normalize(item)];
S.byId = new Map([["a1", S.items[0]]]);
S.listState = "ready";
S.prefs = { retry_policy: { retry_for_s: 600, max_attempts: 3 } };
S.retryPolicy = { retry_for_s: 600, max_attempts: 3 };
S.filter = { q: "zzz", status: "free", time: "today", sort: "name",
  checkin: "yes", checkout: "no" };
savePrefs = () => {};
render();
document.querySelector("#empty-action").click();   /* 先清筛选，不动策略 */
S.selected.add("a1");
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.demo = false;
render();
startPlan();
await Promise.resolve(); await Promise.resolve();
out.push({ policy: sent && sent.policy, itemCount: sent && sent.items.length,
  selected: S.selected.size });
""")
        case = res[0]
        self.assertEqual(case["itemCount"], 1)
        self.assertEqual(case["policy"], {"retry_for_s": 600, "max_attempts": 3},
                         "开始计划必须用用户设的 600/3，不能被清筛选重置")

    def test_start_plan_payload_carries_headed_switch(self):
        """headed 复选框勾选/取消两种状态下开始：start_plan 第 2 参必须实时跟随。"""
        res = run_js(r"""
const headedArgs = [];
window.pywebview = { api: {
  start_plan: (items, headed, policy) => {
    headedArgs.push(headed);
    return Promise.resolve({ ok: true, plan_id: "p1" });
  },
} };
const item = { id: "a1", name: "活动A", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, state: "未开放" };
S.items = [normalize(item)];
S.byId = new Map([["a1", S.items[0]]]);
S.listState = "ready";
S.prefs = { retry_policy: { retry_for_s: 600, max_attempts: 3 } };
S.retryPolicy = { retry_for_s: 600, max_attempts: 3 };
savePrefs = () => {};
S.selected.add("a1");
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.demo = false;
render();
document.querySelector("#headed").checked = true;
startPlan();
await Promise.resolve(); await Promise.resolve();
S.busy = false;                       /* 解开成功路径的置忙，允许第二次驱动 */
document.querySelector("#headed").checked = false;
startPlan();
await Promise.resolve(); await Promise.resolve();
out.push({ headedArgs });
""")
        case = res[0]
        self.assertEqual(case["headedArgs"], [True, False],
                         "start_plan 第 2 参必须实时读 #headed 勾选态（选中=True，取消=False）")

    def test_ready_nonempty_without_target_keeps_data(self):
        """BC-03：有活动但没有可执行目标，不等于学校没返回。"""
        res = run_js(r"""
function snap() {
  render();
  return { title: document.querySelector("#selected").textContent,
    text: document.querySelector("#board-text").textContent,
    count: document.querySelector("#count").textContent };
}
S.listState = "ready"; S.login.result = "valid"; S.login.present = true;
S.selected = new Set();
const signed = normalize({ id: "s1", name: "已报名场", signed: true,
  sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00",
  act_start: "2099-01-03 09:00:00", act_end: "2099-01-03 11:00:00" });
const closed = normalize({ id: "c1", name: "已截止场",
  sign_start: "2020-01-01 09:00:00", sign_end: "2020-01-01 10:00:00",
  act_start: "2020-01-02 09:00:00", act_end: "2020-01-02 11:00:00" });
const unknown = normalize({ id: "u1", name: "待公布场",
  sign_start: "", sign_end: "", act_start: "2099-05-01 09:00:00",
  act_end: "2099-05-01 11:00:00" });
S.items = [signed]; S.byId = new Map([["s1", signed]]);
const onlySigned = snap();
S.items = [closed]; S.byId = new Map([["c1", closed]]);
const onlyClosed = snap();
S.items = [unknown]; S.byId = new Map([["u1", unknown]]);
const onlyUnknown = snap();
S.items = []; S.byId = new Map();
const reallyEmpty = snap();
out.push({ onlySigned, onlyClosed, onlyUnknown, reallyEmpty });
""")
        case = res[0]
        for name in ("onlySigned", "onlyClosed", "onlyUnknown"):
            self.assertEqual(case[name]["title"], "没有可报名的场次",
                             "%s：有活动但无目标，不能说学校没返回" % name)
            self.assertEqual(case[name]["count"], "1 / 1 场",
                             "%s：列表数据必须原样保留" % name)
        self.assertNotIn("学校当前没有返回活动", case["onlySigned"]["title"])
        self.assertNotIn("学校当前没有活动", case["onlySigned"]["title"])
        # 计划栏 1:1（draft-panel A）：原型 draft 段 0 场的标题是「学校当前没有活动」
        self.assertEqual(case["reallyEmpty"]["title"], "学校当前没有活动",
                         "真正零条才归咎学校空列表")

    def test_check_arrival_updates_empty_state(self):
        """BC-04：检查中不说有效；后到的 check 结论自己把空态改过来。

        全程经 window.onBackend.check 进入，不在结论之后手动 render。
        """
        res = run_js(r"""
function snap() {
  return { title: document.querySelector("#empty-title").textContent,
    text: document.querySelector("#empty-text").textContent };
}
S.items = []; S.byId = new Map(); S.listState = "ready";
/* 刷新保留旧 result 并进入 checking：这正是提前写「登录是有效的」的窗口 */
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = true;
render();
const whileChecking = snap();
window.onBackend.check({ ok: false, result: "expired", hours_left: 0, session_present: true });
const afterExpired = snap();
/* 再来一轮 unknown：只能说不确定，不说过期、不逼重登 */
S.login.checking = true;
render();
const checkingAgain = snap();
window.onBackend.check({ ok: false, result: "unknown", hours_left: null, session_present: true });
const afterUnknown = snap();
/* 相反次序：check 先到、list 后到 */
S.login.checking = false;
window.onBackend.check({ ok: true, result: "valid", hours_left: 6, session_present: true });
window.onBackend.activities({ ok: true, items: [] });
const checkThenList = snap();
out.push({ whileChecking, afterExpired, checkingAgain, afterUnknown, checkThenList });
""")
        case = res[0]
        self.assertEqual(case["whileChecking"]["title"], "正在检查登录状态",
                         "检查没结束时不得提前宣布「登录是有效的」")
        self.assertIn("重新登录", case["afterExpired"]["title"],
                      "后到的 expired 必须自己刷新空态，不靠手动 render")
        self.assertEqual(case["checkingAgain"]["title"], "正在检查登录状态")
        self.assertEqual(case["afterUnknown"]["title"], "暂时无法确认登录状态")
        self.assertNotIn("过期", case["afterUnknown"]["text"], "unknown 不说过期")
        self.assertEqual(case["checkThenList"]["title"], "学校当前没有返回活动",
                         "check 先到、list 后到也要收敛到真实状态")

    def test_empty_action_dispatches_by_intent(self):
        """BC-05：「重试」必须真的重发请求；只有筛选空态才清筛选。"""
        res = run_js(r"""
const item = { id: "a1", name: "活动A", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-02 09:00:00", act_start: "2099-01-03 09:00:00",
  act_end: "2099-01-03 11:00:00", signed: false, state: "未开放" };
S.items = [normalize(item)];
S.byId = new Map([["a1", S.items[0]]]);
S.filter = { q: "zzz", status: "free", time: "today", sort: "name",
  checkin: "yes", checkout: "no" };
S.prefs = { retry_policy: { retry_for_s: 600, max_attempts: 3 } };
S.retryPolicy = { retry_for_s: 600, max_attempts: 3 };
savePrefs = () => {};
let checks = 0, lists = 0;
window.pywebview = { api: {
  check: () => { checks += 1; return Promise.reject(new Error("桥接断了")); },
  list_activities: () => { lists += 1; return Promise.reject(new Error("桥接断了")); },
} };
/* 有缓存 + 列表请求失败：空态显示「重试」 */
S.listState = "error"; S.listError = "连不上学校站点";
render();
const errorState = { action: document.querySelector("#empty-action").textContent,
  intent: document.querySelector("#empty-action").dataset.action };
document.querySelector("#empty-action").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const afterRetry = { checks, lists, q: S.filter.q };
/* 回到正常筛选空态：这里才该清筛选，且不再发请求 */
S.listState = "ready";
render();
const filterState = { action: document.querySelector("#empty-action").textContent,
  intent: document.querySelector("#empty-action").dataset.action };
document.querySelector("#empty-action").click();
out.push({ errorState, afterRetry, filterState,
  afterClear: { checks, lists, q: S.filter.q, sort: S.filter.sort },
  retry: S.retryPolicy.retry_for_s, max: S.retryPolicy.max_attempts });
""")
        case = res[0]
        # 20261108-main-window LS12：按钮改名「刷新」，意图仍是 refresh（下一行钉住）
        self.assertEqual(case["errorState"]["action"], "刷新")
        self.assertEqual(case["errorState"]["intent"], "refresh",
                         "失败空态的动作意图必须是刷新，不是清筛选")
        self.assertEqual(case["afterRetry"]["checks"], 1, "「重试」必须真的再查登录态")
        self.assertEqual(case["afterRetry"]["lists"], 1, "「重试」必须真的再拉列表")
        self.assertEqual(case["afterRetry"]["q"], "zzz",
                         "点重试不得顺手清筛选把错误藏掉")
        self.assertEqual(case["filterState"]["intent"], "clear-filters")
        self.assertEqual(case["afterClear"]["q"], "", "筛选空态才清筛选")
        self.assertEqual(case["afterClear"]["sort"], "open")
        self.assertEqual(case["afterClear"]["checks"], 1, "清筛选不得发请求")
        self.assertEqual(case["afterClear"]["lists"], 1)
        self.assertEqual(case["retry"], 600, "清筛选仍不得动策略")
        self.assertEqual(case["max"], 3)


class AttendanceDetailUiTests(unittest.TestCase):
    """真实详情字段：时间段、无需、同步中、待确认四种展示与三态筛选。"""

    def _row(self, **extra):
        row = {"id": "a1", "name": "活动", "sign_start": "2026-10-26 09:00:00",
               "sign_end": "2026-10-26 23:00:00", "act_start": "2026-10-27 19:00:00",
               "act_end": "2026-10-27 21:00:00", "signed": False}
        row.update(extra)
        return row

    def test_required_checkin_shows_real_time_range(self):
        res = run_js(r"""
window.onBackend.activities({ ok: true, items: [{
  id: "a1", name: "活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
  act_end: "2026-10-27 21:00:00", signed: false,
  checkin_required: true, checkin_start: "2026-10-27 19:00:00",
  checkin_end: "2026-10-27 19:40:00", checkout_required: false,
  checkout_start: "", checkout_end: "", attendance_state: "ready" }] });
out.push({ html: rowHtml(findItem("a1")) });
""")
        html = res[0]["html"]
        self.assertIn("签到 19:00–19:40", html)
        self.assertIn("无需签退", html)

    def test_pending_detail_is_not_unknown_no_need(self):
        res = run_js(r"""
window.onBackend.activities({ ok: true, items: [{
  id: "a1", name: "活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
  act_end: "2026-10-27 21:00:00", signed: false,
  checkin_required: null, checkout_required: null, attendance_state: "pending" }] });
const pending = rowHtml(findItem("a1"));
window.onBackend.activities({ ok: true, items: [{
  id: "a1", name: "活动", sign_start: "2026-10-26 09:00:00",
  sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
  act_end: "2026-10-27 21:00:00", signed: false,
  checkin_required: null, checkout_required: null, attendance_state: "unknown" }] });
const unknown = rowHtml(findItem("a1"));
out.push({ pending: pending, unknown: unknown });
""")
        self.assertIn("签到信息同步中", res[0]["pending"])
        self.assertNotIn("无需", res[0]["pending"])
        self.assertIn("签到时间待确认", res[0]["unknown"])

    def test_precise_filters_exclude_unknown_and_all_keeps_it(self):
        res = run_js(r"""
const rows = [
  { id: "yes", name: "需要签到", sign_start: "2026-10-26 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
    act_end: "2026-10-27 21:00:00", signed: false, checkin_required: true,
    checkout_required: true, attendance_state: "ready" },
  { id: "no", name: "无需签到", sign_start: "2026-10-26 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
    act_end: "2026-10-27 21:00:00", signed: false, checkin_required: false,
    checkout_required: false, attendance_state: "ready" },
  { id: "unknown", name: "待确认", sign_start: "2026-10-26 09:00:00",
    sign_end: "2026-10-26 23:00:00", act_start: "2026-10-27 19:00:00",
    act_end: "2026-10-27 21:00:00", signed: false, checkin_required: null,
    checkout_required: null, attendance_state: "pending" }
];
S.items = rows.map(normalize);
S.byId = new Map(S.items.map((item) => [item.id, item]));
const ids = (f) => { S.filter.checkin = f; return filtered().map((item) => item.id); };
out.push({ yes: ids("yes"), no: ids("no"), all: ids("all") });
""")
        data = res[0]
        self.assertEqual(data["yes"], ["yes"])
        self.assertEqual(data["no"], ["no"])
        self.assertEqual(sorted(data["all"]), ["no", "unknown", "yes"])


class AriaAndPlaceTests(unittest.TestCase):
    """D-10/D-11：chips 用 aria-pressed；地点可聚焦、Enter/Space 展开且不改选择。"""

    def test_chips_use_aria_pressed_not_selected(self):
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        app = read("ui/app.js")   # 前端脚本联合源码（chips 渲染已随分层拆分）
        self.assertIn('aria-pressed="true"', html)
        self.assertNotIn('aria-selected="false">可报名', html,
                         "button 上的 aria-selected 非法，必须用 aria-pressed")
        self.assertIn('chip.setAttribute("aria-pressed"', app)
        self.assertNotIn('chip.setAttribute("aria-selected"', app)

    def test_place_has_role_and_expanded_state(self):
        res = run_js(r"""
window.onBackend.activities({ ok: true, items: [{
  id: "a1", name: "活动", place: "实训楼 C305 三楼最里面那间",
  sign_start: "2026-10-26 09:00:00", sign_end: "2026-10-26 23:00:00",
  act_start: "2026-10-27 09:00:00", act_end: "2026-10-27 11:00:00",
  signed: false }] });
out.push({ html: rowHtml(findItem("a1")) });
""")
        html = res[0]["html"]
        self.assertIn('role="button"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('tabindex="0"', html)

    def test_enter_expands_place_without_selection(self):
        res = run_js(r"""
const place = document.createElement("div");
const handler = document.querySelector("#rows").listeners.keydown[0];
const event = { target: { closest: (sel) => (sel === ".c-place" ? place : null) },
                key: "Enter", defaultPrevented: false,
                preventDefault() { this.defaultPrevented = true; } };
handler(event);
const opened = place.getAttribute("aria-expanded");
handler(event);
const closed = place.getAttribute("aria-expanded");
const keyA = { target: { closest: (sel) => (sel === ".c-place" ? place : null) },
               key: "a", preventDefault() { this.defaultPrevented = true; } };
handler(keyA);
out.push({ opened: opened, closed: closed, prevented: event.defaultPrevented,
           selected: S.selected.size, afterA: place.getAttribute("aria-expanded") });
""")
        data = res[0]
        self.assertEqual(data["opened"], "true")
        self.assertEqual(data["closed"], "false")
        self.assertTrue(data["prevented"], "Enter 必须阻止默认滚动/提交")
        self.assertEqual(data["selected"], 0, "展开地点不得勾选活动")
        self.assertEqual(data["afterA"], "false", "其他按键不改变展开状态")


class RefreshFeedbackTests(unittest.TestCase):
    """N2：点刷新立刻看得见加载，失败落原型失败态，断网时不发请求并给「重新检测」。"""

    def test_loading_replaces_old_rows_with_skeleton(self):
        """有旧列表时点刷新同样立刻进加载态：列表骨架、计划栏与点阵屏都改口。

        取代「只有空列表才显示骨架」：请求挂着不回来时，旧行原样留着看起来就是没反应
        （原型 Main.dc.html:2138 / :2006 / :1993）。"""
        res = run_js(r"""
S.items = [{ id: "a1", name: "旧活动", sign_start: "2026-11-05 10:00:00",
  sign_end: "2026-11-05 12:00:00", act_start: "2026-11-06 10:00:00",
  act_end: "2026-11-06 12:00:00" }];
S.byId = new Map(S.items.map((it) => [String(it.id), it]));
S.listState = "loading";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.selected = new Set();
render();
out.push({
  rows: document.querySelector("#rows").innerHTML,
  planTitle: document.querySelector("#selected").textContent,
  planText: document.querySelector("#board-text").textContent,
  /* 桩的 textContent 不聚合子节点：paintLedLabel 把前缀写进文本节点，
   * 读 firstChild 才拿得到「正在加载」，等价于真实 DOM 的 label.textContent。 */
  led: (document.querySelector("#led-label").firstChild || {}).textContent || "",
  loading: document.querySelector("#list").classList.contains("is-loading"),
});
""")
        row = res[0]
        self.assertIn("skel-row", row["rows"], "加载态必须换成骨架行，旧行不能继续显示")
        self.assertNotIn("旧活动", row["rows"], "旧行在加载期间先收起，避免看起来没反应")
        self.assertTrue(row["loading"], "列表容器要带 is-loading，样式才进加载态")
        self.assertEqual(row["planTitle"], "活动列表正在加载")
        self.assertEqual(row["planText"], "先等这一次加载结束。")
        self.assertIn("正在加载", row["led"], "点阵屏同步报「正在加载」（原型 :1993）")

    def test_list_failure_uses_prototype_copy(self):
        """已登录仍拉不到列表：空态与计划栏用原型失败态原话，并给「重试」。"""
        res = run_js(r"""
S.items = [];
S.byId = new Map();
S.selected = new Set();
S.listState = "error";
S.listError = "活动列表超过 130 秒没有回应";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
render();
out.push({
  title: document.querySelector("#empty-title").textContent,
  text: document.querySelector("#empty-text").textContent,
  action: document.querySelector("#empty-action").textContent,
  planTitle: document.querySelector("#selected").textContent,
  planText: document.querySelector("#board-text").textContent,
});
""")
        row = res[0]
        self.assertEqual(row["title"], "活动暂时没加载")
        # 20261108-main-window LS12：正文语序与按钮名照原型 listerr 画板
        # 评审修正：原型在这句里把「刷」「新」用 U+2060 连住，免得按钮名在 Edge 里被断成两行；句子本身没变。
        self.assertEqual(row["text"], "连不上学校站点，已保存的登录不受影响。检查网络后点“刷⁠新”。")
        self.assertEqual(row["action"], "刷新")
        self.assertEqual(row["planTitle"], "活动暂时没加载")
        self.assertEqual(row["planText"], "具体原因看左边列表的提示。")

    def test_offline_refresh_sends_nothing_and_keeps_the_banner(self):
        """已知断网：refresh 不发 check/list，反馈就是横幅本身（原型 :1849）。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: {
  check: () => { calls.push("check"); return Promise.resolve({ ok: true }); },
  list_activities: () => { calls.push("list"); return Promise.resolve({ ok: true, items: [] }); },
} };
S.online = false;
refresh(false);
out.push({ calls: calls.slice(),
  banner: document.querySelector("#banners").innerHTML,
  hidden: document.querySelector("#banners").hidden });
""")
        row = res[0]
        self.assertEqual(row["calls"], [], "断网时不发学校请求，避免请求一直挂着")
        self.assertFalse(row["hidden"], "断网横幅要一直挂着")
        self.assertIn("网络断开了。", row["banner"])
        self.assertIn("恢复以后点“刷新”。", row["banner"])
        self.assertIn("重新检测", row["banner"])

    def test_net_recheck_restores_banner_without_refreshing(self):
        """「重新检测」只重读网络状态：恢复后收起横幅、写「网络已恢复」，不自动刷新。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: {
  check: () => { calls.push("check"); return Promise.resolve({ ok: true }); },
  list_activities: () => { calls.push("list"); return Promise.resolve({ ok: true, items: [] }); },
} };
S.online = false;
paintBanners();
const evt = { target: { closest: (sel) => (sel === '[data-act="net-recheck"]' ? {} : null) },
  preventDefault() {} };
__els.get("#banners").listeners.click.forEach((fn) => fn(evt));
out.push({ online: S.online, banner: document.querySelector("#banners").innerHTML,
  calls: calls.slice(), logs: S.recentLogs.slice() });
""")
        row = res[0]
        self.assertTrue(row["online"], "重新检测到联网后要把状态改回来")
        self.assertEqual(row["banner"], "", "网络恢复后横幅内容清空（容器本身不设 hidden）")
        self.assertEqual(row["calls"], [], "原型让用户自己点刷新，重新检测不自动加载")
        self.assertIn("[OK] 网络已恢复", row["logs"])


if __name__ == "__main__":
    unittest.main()
