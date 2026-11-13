# -*- coding: utf-8 -*-
"""界面契约：计划栏的草稿、运行、结果与停止/重试。"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import BEIJING_TZ, read, run_js, PP_LOGIN_OK_JS, _pp_stats, WB_STAMP_JS  # noqa: E402


class LedAndStopContractTests(unittest.TestCase):
    """LED 点阵与停止二次确认的契约。"""

    def test_index_wires_led_and_stop_dialog(self):
        html = read("ui/index.html")
        self.assertIn('<script src="led.js"></script>', html, "必须在 app.js 之前引入 led.js")
        self.assertIn('id="led"', html, "缺少 LED 点阵容器 #led")
        # 原因：停止确认从原生 <dialog id="dlg-stop"> 改成计划栏内的遮罩弹层（决策 014 / 原型 P19），
        # 旧 id 与 form method=dialog 的 value=no/yes 通道随之取消，改钉新结构
        self.assertNotIn('id="dlg-stop"', html, "停止确认不再是原生 dialog：旧 #dlg-stop 必须删掉")
        start = html.index('id="plan-stop-ask"')
        ask = html[html.rindex("<div", 0, start):html.index("</aside>", start)]
        board = html[html.index('<aside class="board plan-panel" id="board"'):html.index("</aside>", start)]
        self.assertIn(ask, board, "停止确认弹层必须在 #board 内部，只盖计划栏")
        self.assertTrue(ask.startswith('<div class="scrim"'), "外层是原型的 .scrim 遮罩")
        for attr in ('role="dialog"', 'aria-modal="true"', 'aria-labelledby="plan-stop-title"', "hidden"):
            self.assertIn(attr, ask.split(">")[0], "遮罩缺 %s：读屏与默认隐藏靠它" % attr)
        self.assertIn('id="plan-stop-title">停止报名计划？<', ask, "标题逐字照原型")
        self.assertIn("工具会停止后续尝试。已经发出的提交仍可能成功，停止不会取消已成功的报名。", ask,
                      "说明逐字照原型")
        self.assertIn('class="btn btn-line" id="btn-stop-keep" type="button">继续计划<', ask,
                      "「继续计划」是 btn-line，且是弹层里的第一个按钮")
        self.assertIn('class="btn btn-stop" id="btn-stop-yes" type="button">停止计划<', ask,
                      "「停止计划」是 btn-stop（危险色），且排在「继续计划」之后")
        self.assertLess(ask.index("btn-stop-keep"), ask.index("btn-stop-yes"))
        self.assertIn('class="dlg sm"', ask, "弹层窄版 .dlg.sm 照原型")

    def test_led_js_is_pure_renderer(self):
        js = read("ui/led.js")
        self.assertIn("renderLed", js, "led.js 必须暴露 renderLed")
        self.assertIn("clearLed", js, "led.js 必须暴露 clearLed")
        self.assertIn("✓", js, "字库要含成功图标")
        self.assertIn("✕", js, "字库要含失败图标")
        for banned in ("fetch(", "XMLHttpRequest", "mock-backend", "pywebview", "onBackend"):
            self.assertNotIn(banned, js, "led.js 只负责渲染，不得含业务/网络逻辑：%s" % banned)

    def test_stop_only_after_confirmation(self):
        js = read("ui/app.js")
        start = js.index("function stopPlan()")
        body = js[start:js.index("function ", start + 10)]
        # 原因：确认弹窗换成 #plan-stop-ask 弹层，stopPlan 只负责打开它，不再 showModal
        self.assertIn("openStopAsk()", body, "stopPlan 必须先打开确认弹层")
        self.assertNotIn("showModal", body, "停止确认不再是原生 dialog")
        self.assertNotIn("stop_plan", body, "stopPlan 本体不得直接调用 stop_plan")
        do_start = js.index("function doStopPlan()")
        do_body = js[do_start:js.index("function ", do_start + 10)]
        self.assertIn('"stop_plan"', do_body, "真正的停止只在确认回调 doStopPlan 里")
        # 原因：原生 dialog 的 returnValue 通道取消；现在只有「停止计划」按钮（#btn-stop-yes）接到停止流程，
        # 「继续计划」与 Esc 只关弹层
        self.assertIn('$("#btn-stop-yes").addEventListener("click", confirmStopPlan)', js,
                      "只有「停止计划」按钮接到停止流程")
        self.assertIn('$("#btn-stop-keep").addEventListener("click", () => closeStopAsk(true))', js,
                      "「继续计划」只关弹层并还焦点")
        confirm = js[js.index("function confirmStopPlan()"):js.index("function ", js.index("function confirmStopPlan()") + 10)]
        self.assertIn("doStopPlan()", confirm, "「停止计划」走现有停止流程")
        self.assertNotIn("dlg-stop", js, "旧 #dlg-stop 的绑定必须删干净")
        self.assertNotIn("returnValue", js[js.index("function stopAskOpen()"):js.index("function modifyPlan()")],
                         "弹层不再借 dialog.returnValue 传结论")


class StopAskBehaviorTests(unittest.TestCase):
    """停止确认弹层（计划栏内遮罩，原型 P19）的焦点与键盘行为（node 桩，不连学校）。"""

    # 共用前置：计划运行中、桥接桩记录 stop_plan 调用
    SETUP = r"""
const calls = [];
window.pywebview = { api: { stop_plan: (id) => { calls.push(id); return Promise.resolve({ ok: true }); } } };
setBusy(true);
S.plan = { id: "p1", status: "running", tasks: new Map() };
updateControls();
const ask = document.querySelector("#plan-stop-ask");
const keep = document.querySelector("#btn-stop-keep");
const yes = document.querySelector("#btn-stop-yes");
const stopBtn = document.querySelector("#btn-stop");
"""

    def test_open_puts_focus_on_keep_going(self):
        """点「停止计划」只打开弹层，焦点落在「继续计划」；这时还没有发出 stop_plan。"""
        res = run_js(self.SETUP + r"""
const before = ask.hidden;
stopBtn.click();
out.push({ before, after: ask.hidden, active: document.activeElement.__sel, calls: calls.length,
  stopping: S.stopping });
""")
        self.assertTrue(res[0]["before"], "弹层默认隐藏")
        self.assertFalse(res[0]["after"], "点「停止计划」必须打开弹层")
        self.assertEqual(res[0]["active"], "#btn-stop-keep", "打开后焦点必须在「继续计划」，防止回车误停")
        self.assertEqual(res[0]["calls"], 0, "只是打开确认，不得已经停止")
        self.assertFalse(res[0]["stopping"], "只是打开确认，计划状态不变")

    def test_escape_closes_and_returns_focus_to_stop_button(self):
        """Esc 只关弹层，焦点回到 #btn-stop；不停止、不清空选择。"""
        res = run_js(self.SETUP + r"""
S.selected.add("a1");
stopBtn.click();
const ev = __dispatchKey({ key: "Escape" });
out.push({ hidden: ask.hidden, active: document.activeElement.__sel, calls: calls.length,
  prevented: ev.defaultPrevented, selKept: S.selected.has("a1") });
""")
        self.assertTrue(res[0]["hidden"], "Esc 必须关闭弹层")
        self.assertEqual(res[0]["active"], "#btn-stop", "关闭后焦点还给触发它的「停止计划」按钮")
        self.assertEqual(res[0]["calls"], 0, "Esc 不得停止计划")
        self.assertTrue(res[0]["prevented"], "Esc 由弹层接管，不再向下传")
        self.assertTrue(res[0]["selKept"], "Esc 不得顺手清空背景的选择")

    def test_keep_going_closes_without_stopping(self):
        """「继续计划」关闭弹层并还焦点，不停止。"""
        res = run_js(self.SETUP + r"""
stopBtn.click();
keep.click();
out.push({ hidden: ask.hidden, active: document.activeElement.__sel, calls: calls.length });
""")
        self.assertTrue(res[0]["hidden"], "「继续计划」必须关闭弹层")
        self.assertEqual(res[0]["active"], "#btn-stop", "关闭后焦点还给「停止计划」按钮")
        self.assertEqual(res[0]["calls"], 0, "「继续计划」不得停止计划")

    def test_confirm_runs_existing_stop_flow_once(self):
        """「停止计划」关弹层并走现有停止流程：恰好一次 stop_plan，界面进入「正在停止」。"""
        res = run_js(self.SETUP + r"""
stopBtn.click();
yes.click();
yes.click();   /* 弹层已关，重复点击不得再发第二次 */
out.push({ hidden: ask.hidden, calls: calls.slice(), stopping: S.stopping });
""")
        self.assertTrue(res[0]["hidden"], "确认后弹层关闭")
        self.assertEqual(res[0]["calls"], ["p1"], "必须只对当前计划发一次 stop_plan")
        self.assertTrue(res[0]["stopping"], "确认后进入「正在停止」")

    def test_confirm_after_plan_ended_does_not_call_backend(self):
        """弹层开着时计划恰好结束：「停止计划」只关弹层，不再给后端发 stop_plan。"""
        res = run_js(self.SETUP + r"""
stopBtn.click();
setBusy(false);
yes.click();
out.push({ hidden: ask.hidden, calls: calls.length });
""")
        self.assertTrue(res[0]["hidden"], "确认后弹层关闭")
        self.assertEqual(res[0]["calls"], 0, "计划已结束时不得再发 stop_plan")

    def test_tab_cycles_between_the_two_buttons_only(self):
        """弹层打开时 Tab / Shift+Tab 只在「继续计划」和「停止计划」之间循环。"""
        res = run_js(self.SETUP + r"""
stopBtn.click();
const seen = [document.activeElement.__sel];
const prevented = [];
for (let i = 0; i < 3; i += 1) {
  prevented.push(__dispatchKey({ key: "Tab" }).defaultPrevented);
  seen.push(document.activeElement.__sel);
}
const back = [];
for (let i = 0; i < 2; i += 1) {
  __dispatchKey({ key: "Tab", shiftKey: true });
  back.push(document.activeElement.__sel);
}
out.push({ seen, prevented, back });
""")
        self.assertEqual(res[0]["seen"], ["#btn-stop-keep", "#btn-stop-yes", "#btn-stop-keep", "#btn-stop-yes"],
                         "Tab 在两个按钮间循环，不跑到背景")
        self.assertTrue(all(res[0]["prevented"]), "Tab 由弹层接管（preventDefault）")
        self.assertEqual(res[0]["back"], ["#btn-stop-keep", "#btn-stop-yes"], "Shift+Tab 反向循环")

    def test_enter_and_search_keys_do_not_reach_background(self):
        """弹层打开时 Enter 不开始计划、Ctrl+F 与 / 不抢焦点去搜索框。"""
        res = run_js(self.SETUP + r"""
let started = 0;
startPlan = () => { started += 1; };
stopBtn.click();
__dispatchKey({ key: "Enter" });
const f = __dispatchKey({ key: "f", ctrlKey: true });
const slash = __dispatchKey({ key: "/" });
out.push({ started, active: document.activeElement.__sel, fPrevented: f.defaultPrevented,
  slashPrevented: slash.defaultPrevented, open: !ask.hidden });
""")
        self.assertEqual(res[0]["started"], 0, "Enter 不得穿透到背景开始计划")
        self.assertEqual(res[0]["active"], "#btn-stop-keep", "Ctrl+F 与 / 不得把焦点抢到搜索框")
        self.assertTrue(res[0]["fPrevented"] and res[0]["slashPrevented"], "背景快捷键被弹层吞掉")
        self.assertTrue(res[0]["open"], "这些键不关弹层")

    def test_no_plan_means_no_prompt(self):
        """没有进行中的计划时，stopPlan 不打开弹层。"""
        res = run_js(r"""
S.plan = { id: null, status: "idle", tasks: new Map() };
stopPlan();
out.push({ hidden: document.querySelector("#plan-stop-ask").hidden });
""")
        self.assertTrue(res[0]["hidden"], "没有计划就没有可停止的东西")

    def test_overlay_styles_follow_prototype(self):
        """样式照原型：遮罩绝对定位铺满计划栏、z-index 8；窄弹层 26rem；btn-stop 用危险色。"""
        css = read("ui/styles.css")
        self.assertRegex(css, r"\.board \{[^}]*position: relative", ".board 是遮罩的定位父级")
        scrim = css[css.index(".board .scrim {"):css.index("}", css.index(".board .scrim {"))]
        for want in ("position: absolute", "inset: 0", "z-index: 8", "rgba(17,29,38,.38)"):
            self.assertIn(want, scrim, "遮罩缺 %s（原型 .scrim）" % want)
        self.assertIn(".board .dlg.sm { width: min(26rem, 100%); }", css, "窄弹层宽度照原型 .dlg.sm")
        self.assertIn(".btn-stop { background: var(--bad); color: #fff; }", css, "「停止计划」用危险色（原型 .btn-stop）")
        self.assertNotIn("btn-stop-confirm", css + read("ui/index.html"), "旧的 btn-stop-confirm 样式随原生 dialog 一起删掉")


class StopLifecycleContractTests(unittest.TestCase):
    """停止生命周期的静态契约：进程树终止、「正在停止」反馈、重试窗口硬截止。"""

    def test_app_py_kills_process_tree(self):
        # 树终止 helper 已下沉 infrastructure.process_tree；任务监督的
        # 取消收尾契约在 application.plan_service（app.py 保留 stop_plan 入口）
        tree_src = read("infrastructure/process_tree.py")
        self.assertIn("def kill_tree", tree_src, "必须有进程树终止 helper")
        self.assertIn("taskkill", tree_src, "Windows 下必须按 taskkill /F /T 终止整棵进程树")
        plan_src = read("application/plan_service.py")
        self.assertIn("canceled or reader_done.is_set()",
                      plan_src, "取消路径的退出条件不得依赖管道 EOF（孙进程可能握着管道）")
        py = read("app.py")
        self.assertIn("_terminate_plan_procs", py, "stop_plan 必须主动终止活着的 worker")

    def test_grab_retry_window_is_hard_deadline(self):
        """所有阻塞必须压在同一个单调预算上（R03/R06）。

        旧实现按墙钟 deadline 逐个钳制，墙钟回拨就会把窗口拉长；现在
        reload/click/expect_response/goto 的超时都必须来自 RetryBudget，
        由单调截止与绝对截止取更紧者。行为证据在 test_worker_boundaries。
        """
        import ast
        source = read("grab.py")
        self.assertNotIn("def clamp_wait_ms", source, "旧的墙钟钳制 helper 必须移除")
        self.assertIn("RetryBudget(", source, "重试窗口必须用单调预算")
        tree = ast.parse(source)
        cmd = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "cmd_grab")
        offenders = []
        for node in ast.walk(cmd):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"reload", "click", "expect_response", "goto"}:
                continue
            timeout = next((kw.value for kw in node.keywords if kw.arg == "timeout"), None)
            text = ast.unparse(timeout) if timeout is not None else "<none>"
            if "budget.timeout_ms" not in text:
                offenders.append((node.func.attr, text))
        self.assertFalse(offenders, "阻塞调用必须用预算超时：%r" % offenders)

    def test_grab_finally_never_returns(self):
        """cmd_grab 的 finally 只收尾浏览器：return 会掩盖真实退出码（成功0/登录失败3/报名失败2）。"""
        import ast
        tree = ast.parse(read("grab.py"))
        cmd = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "cmd_grab")
        offenders = []
        for node in ast.walk(cmd):
            if isinstance(node, ast.Try) and node.finalbody:
                for stmt in node.finalbody:
                    offenders.extend(sub for sub in ast.walk(stmt)
                                     if isinstance(sub, ast.Return))
        self.assertFalse(offenders, "cmd_grab 的 finally 里不得 return：%r" % offenders)

    def test_app_js_stopping_feedback(self):
        js = read("ui/app.js")
        self.assertIn("S.stopping", js, "停止后必须有「正在停止」的即时反馈状态")
        self.assertIn('"正在停止…"', js, "停止按钮要切换为「正在停止…」")
        self.assertIn("S.stopping = false", js, "plan_done 后必须解除正在停止状态")
        self.assertIn("S.login.present === false ? \"未登录\" : \"已登录\"", js,
                      "忙碌胶囊只表达登录状态，不替换成处理中")


class RetryPolicyUiContractTests(unittest.TestCase):
    """重试策略的界面契约：控件、偏好、telemetry 展示与旧桥接不丢。"""

    def test_index_has_policy_controls(self):
        html = read("ui/index.html")
        self.assertIn('id="retry-for"', html, "缺少重试时长下拉 #retry-for")
        self.assertIn('id="max-attempts"', html, "缺少最大提交次数输入 #max-attempts")
        for label in ("2 分钟", "10 分钟", "30 分钟", "1 小时", "直到报名截止"):
            self.assertIn(label, html, "重试时长缺少「%s」档位" % label)
        self.assertIn('value="0"', html, "次数输入必须能表达 0=不限")

    def test_app_js_saves_and_sends_policy(self):
        js = read("ui/app.js")
        self.assertIn("retryPolicy", js, "缺少策略状态 S.retryPolicy")
        self.assertIn("retry_policy", js, "策略必须随偏好保存/恢复（prefs.retry_policy）")
        self.assertIn("setRetryPolicy", js, "缺少策略写入函数 setRetryPolicy")
        # startPlan 必须把策略传给后端
        start = js.index("api(\"start_plan\"")
        call = js[start:start + 200]
        self.assertIn("retry_for_s", call, "start_plan 载荷必须带 retry_for_s")
        self.assertIn("max_attempts", call, "start_plan 载荷必须带 max_attempts")

    def test_app_js_renders_attempts_and_stop_reason(self):
        js = read("ui/app.js")
        # R13：有限次数必须写出上限；0=不限要明说，不能只写「第 N 次」。
        # 计划栏 1:1（run-panel F）：写法照原型 card「已提交 N 次（上限 M 次）」，不再是「N/M 次」
        self.assertIn('"已提交 " + attempts + " 次（"', js, "任务卡必须显示已提交次数")
        self.assertIn('"上限 " + cap + " 次"', js, "任务卡必须显示上限（telemetry）")
        self.assertIn('"不限次数"', js, "不限次数必须明说，不能只给一个孤立数字")
        self.assertIn("last_reason", js, "任务卡必须显示最近原因")
        self.assertIn("stopReasonText", js, "缺少停止条件人话函数")
        for word in ("达到最大提交次数", "重试时长到了", "报名已截止", "登录失效"):
            self.assertIn(word, js, "终态文案缺「%s」" % word)
        # 路线图不再用固定 sign_start+120 冒充截止
        self.assertIn("telemetryDeadline", js, "重试截止必须优先用 telemetry")

    def test_plan_failure_keeps_silent_recheck(self):
        """失败终态路径必须保留 400ms 去重的静默复查：掉了登录要翻到胶囊上。"""
        js = read("ui/controllers/plan-events.js")
        self.assertIn("S.recheckPending = true", js,
                      "静默复查必须有去重标志（S.recheckPending）")
        recheck = js.index("S.recheckPending = true")
        block = js[recheck:recheck + 160]
        # 原断言钉住字面 refresh(true)（前台轮）；该处是程序自己发起的复查，
        # 前台轮会画骨架、失败时清空列表与勾选（U2/U3，计划 20261113-prerefactor-fixes），改走后台轮
        self.assertIn("refresh(true, { background: true })", block,
                      "失败后必须静默复查登录态与列表（后台轮 refresh(true, { background: true })）")
        self.assertIn("}, 400);", block, "复查必须挂在 400ms 去重窗口里（setTimeout 400）")

    def test_backend_contract_strings(self):
        # worker 命令行已随任务监督下沉 application.plan_service
        plan_src = read("application/plan_service.py")
        self.assertIn("--sign-end", plan_src, "worker 命令必须传报名截止")
        self.assertIn("--retry-for", plan_src, "worker 命令必须传重试时长")
        self.assertIn("--max-attempts", plan_src, "worker 命令必须传最大提交次数")
        py = read("app.py")
        self.assertIn("def _parse_retry_line", py, "必须解析 [retry] 结构化行")
        grab = read("grab.py")
        self.assertIn("def compute_retry_window", grab, "缺少窗口纯函数")
        self.assertIn("def attempts_allowed", grab, "缺少次数上限判断")
        self.assertIn("sign_end", read("signup_plan.py"), "TaskSpec 必须携带 sign_end")


class PreopenRouteContractTests(unittest.TestCase):
    """预报名提前准备与真实 checkpoint 的静态契约（反修门禁）。"""

    def test_paint_route_has_no_fake_time_fallbacks(self):
        """paintRoute 不得用 armedAt/open-100/open-5 编造事件时间；缺失显示待发生文案。"""
        js = read("ui/app.js")
        start = js.index("function paintRoute()")
        body = js[start:js.index("function routeDeadline", start)]
        for banned in ("armedAt", "open - 100", "open - 5"):
            self.assertNotIn(banned, body,
                             "路线图站点不得用 %s 生成估算时间冒充事件时间" % banned)
        for needed in ("待启动", "待打开", "待开始"):
            self.assertIn(needed, body, "缺 checkpoint 的站点必须显示「%s」" % needed)
        # 真实 checkpoint 仍是三个执行站点唯一的时间来源
        for field in ("run_started_at", "page_opened_at", "watch_started_at"):
            self.assertIn(field, body, "路线站点必须消费真实字段 %s" % field)

    def test_worker_payload_carries_lead(self):
        """worker 载荷显式携带与 TaskSpec 一致的 --lead；快照携带 lead_s。"""
        # worker 命令行已随任务监督下沉 application.plan_service
        plan_src = read("application/plan_service.py")
        self.assertIn('"--lead", str(max(0, int(spec.lead_s or 0)))', plan_src,
                      "_run_plan_task 必须显式传 --lead（预报名提前准备窗口）")
        sp = read("signup_plan.py")
        self.assertIn("lead_s: int = 100", sp, "TaskSpec 快照必须携带 lead_s（默认 100）")
        self.assertIn('"lead_s": self.lead_s', sp, "as_dict 必须输出 lead_s，页面重载不丢")

    def test_scheduler_prepare_semantics(self):
        """调度器按准备时刻调度：instant 立即、pre_register 提前、批次间不 join。"""
        sp = read("signup_plan.py")
        self.assertIn("def _prepare_ts", sp, "缺少按准备时刻调度的纯函数")
        start = sp.index("def _run(self)")
        body = sp[start:sp.index("def _prepare_ts", start)]
        self.assertIn("_prepare_ts", body, "调度循环必须按 _prepare_ts 排序与分批")
        # 批次循环内不得 join 整批（否则重试会阻塞后续场次按准备时刻启动）
        batch_zone = body[:body.index("for thread in threads")]
        self.assertNotIn("thread.join()", batch_zone,
                         "批次循环内不得 join：重试中的场次不得阻塞后续调度")
        self.assertIn('== "instant_signup"', sp,
                      "已开放场次必须立即启动，不等历史 sign_start")


class RuntimeDisplayBehaviorTests(unittest.TestCase):
    """UX-04/05：当前目标只跟真实任务走，单场结果不抢写整屏（node vm 行为）。

    全部经生产函数 render()/handleTask()/handlePlanDone() 进入；
    零学校、零 worker、零浏览器。本任务只定义，不运行。
    """

    def test_canceled_task_leaves_batch_count(self):
        """A 取消、C 仍等待：批次由 2 变 1，已取消的场次不再当目标。"""
        res = run_js(r"""
const start = "2099-01-01 09:00:00";
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "活动A",
  status: "canceled", sign_start: start, signup_mode: "pre_register" });
S.plan.tasks.set("C", { task_id: "C", activity_id: "C", name: "活动C",
  status: "waiting", sign_start: start, signup_mode: "pre_register" });
/* 原勾选集合没被清理：修复前倒计时读的就是它，会继续说「同时提交 2 场」 */
S.selected = new Set(["A", "C"]);
render();
const view = executionView();
out.push({ phase: view.phase, taskId: view.task.task_id, count: view.count,
  countdown: document.querySelector("#countdown").textContent,
  title: document.querySelector("#selected").textContent });
""")
        case = res[0]
        self.assertEqual(case["phase"], "waiting")
        self.assertEqual(case["taskId"], "C", "当前目标必须是还没结束的 C")
        self.assertEqual(case["count"], 1, "取消 A 后同批只剩 1 场")
        self.assertIn("同时开放 1 场", case["countdown"])
        self.assertNotIn("2 场", case["countdown"], "已取消的场次不得继续计入批次")
        self.assertEqual(case["title"], "活动C", "标题必须跟着当前执行目标")

    def test_success_leaves_target_on_future_activity(self):
        """立即场成功后目标回到仍等待的未来场；LED 标注用真实开放时刻，不重拼。"""
        res = run_js(r"""
const start = "2099-01-01 09:00:00";
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("B", { task_id: "B", activity_id: "B", name: "活动B",
  status: "success", sign_start: "2020-01-01 09:00:00", signup_mode: "instant_signup" });
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "活动A",
  status: "waiting", sign_start: start, signup_mode: "pre_register" });
render();
out.push({ taskId: executionView().task.task_id,
  countdown: document.querySelector("#countdown").textContent,
  label: document.querySelector("#led-label b").textContent,
  expected: hmsDay(toTs(start)), clock: fmtClock(toTs(start)) });
""")
        case = res[0]
        self.assertEqual(case["taskId"], "A", "立即场成功后目标必须落到未来场")
        self.assertIn("同时开放 1 场", case["countdown"])
        self.assertNotIn("00:00:00", case["countdown"], "未来场不得显示成全开放")
        # 计划栏 1:1（run-panel C）：原型 led 说明用 hms(cur.open)，跨天加「N 天后」，所以期望走 hmsDay
        self.assertEqual(case["label"], case["expected"],
                         "LED 标注必须直接格式化开放时刻（now+left 会差 1 秒）")
        self.assertTrue(case["label"].endswith(case["clock"]))

    def test_preview_open_label_uses_absolute_time(self):
        """未选择与选择预览也必须直接显示开放时刻，不能从取整倒计时反推。"""
        res = run_js(r"""
const start = "2099-01-01 09:00:00";
setBusinessNow((toTs(start) - 60) * 1000 + 250);
const item = { id: "preview", name: "预览场", sign_start: start,
  sign_end: "2099-01-01 10:00:00", act_start: "2099-01-02 10:00:00",
  act_end: "2099-01-02 11:00:00", signed: false };
S.busy = false; S.items = [item]; S.byId = new Map([[item.id, item]]);
S.selected = new Set(); S.plan = { id: null, status: "idle", tasks: new Map() };
/* 计划栏 1:1（draft-panel I）：原型 draft 段 led 在列表没加载时只写「活动未加载」，样本要先标列表已加载 */
S.listState = "ready";
paintLed();
const idle = document.querySelector("#led-label b").textContent;
S.selected.add(item.id);
paintLed();
const selected = document.querySelector("#led-label b").textContent;
out.push({ idle, selected, expected: fmtClock(toTs(start)) });
""")
        self.assertEqual(res[0]["idle"], res[0]["expected"])
        self.assertEqual(res[0]["selected"], res[0]["expected"])

    def test_submitting_wins_over_waiting(self):
        """真实提交优先于未来预热；批次数只数真正提交过且仍活跃的任务。

        样本必须是生产可能出现的形状：已开放（sign_start 在过去）+ 真实
        run_started_at + attempts>0。未来 2099 + attempts 缺失的样本只能
        证明「raw submitting 也算提交」，正是本轮要修掉的错口径。
        """
        res = run_js(r"""
const open = "2026-10-25 19:00:00";
const openTs = toTs(open);
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
/* 未来预热场：raw submitting，但还没开放、一次都没提交 */
S.plan.tasks.set("W", { task_id: "W", activity_id: "W", name: "预热场",
  status: "submitting", sign_start: "2099-01-01 09:00:00", page_opened_at: openTs,
  signup_mode: "pre_register" });
/* 两场已开放、各提交过一次（并列：应保持快照顺序取 S1） */
S.plan.tasks.set("S1", { task_id: "S1", activity_id: "S1", name: "提交场1",
  status: "submitting", attempts: 1, sign_start: open, run_started_at: openTs,
  retry_for_s: 600, signup_mode: "instant_signup" });
S.plan.tasks.set("S2", { task_id: "S2", activity_id: "S2", name: "提交场2",
  status: "submitting", attempts: 2, sign_start: open, run_started_at: openTs,
  retry_for_s: 600, signup_mode: "instant_signup" });
S.plan.tasks.set("D", { task_id: "D", activity_id: "D", name: "已完成",
  status: "success", attempts: 1, sign_start: open, signup_mode: "instant_signup" });
render();
const view = executionView();
out.push({ phase: view.phase, taskId: view.task.task_id, count: view.count,
  countdown: document.querySelector("#countdown").textContent,
  label: document.querySelector("#led-label b").textContent,
  expected: fmtClock(view.retryUntil),
  warmups: Array.from(S.plan.tasks.values())
    .map((task) => task.task_id + ":" + taskDisplayPhase(task)).join(",") });
""")
        case = res[0]
        self.assertEqual(case["phase"], "submitting")
        self.assertEqual(case["taskId"], "S1", "并列时保持快照顺序")
        self.assertEqual(case["count"], 2, "只数真正提交过且仍活跃的两场，不含未来预热")
        self.assertIn("正在提交 2 场", case["countdown"])
        self.assertEqual(case["label"], case["expected"], "LED 标注必须是当前场的重试截止")
        self.assertIn("W:preopen", case["warmups"], "未来预热不是提交阶段")
        self.assertIn("S1:retrying", case["warmups"])

    def test_all_terminal_waits_for_plan_done(self):
        """全终态但 plan_done 未到：汇总中；没有任务：准备中，都不提前报成功。"""
        res = run_js(r"""
setResult(null);        /* 结果桩归零：桩默认 hidden=false，真实首屏是隐藏的 */
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "活动A",
  status: "success", sign_start: "2099-01-01 09:00:00", signup_mode: "instant_signup" });
render();
const settling = { phase: executionView().phase,
  countdown: document.querySelector("#countdown").textContent,
  tag: document.querySelector("#board-tag-text").textContent,
  text: document.querySelector("#board-text").textContent,
  resultHidden: document.querySelector("#result").hidden,
  board: document.querySelector("#board").dataset.planState };
S.plan.tasks = new Map();
render();
const preparing = { phase: executionView().phase,
  countdown: document.querySelector("#countdown").textContent,
  tag: document.querySelector("#board-tag-text").textContent };
out.push({ settling, preparing });
""")
        case = res[0]
        self.assertEqual(case["settling"]["phase"], "settling")
        self.assertEqual(case["settling"]["countdown"], "正在汇总结果")
        self.assertEqual(case["settling"]["tag"], "汇总中")
        self.assertTrue(case["settling"]["resultHidden"],
                        "计划级结论没到，结果框不得先写成功")
        self.assertEqual(case["settling"]["board"], "running", "汇总中仍是运行色")
        self.assertEqual(case["preparing"]["phase"], "preparing")
        self.assertEqual(case["preparing"]["countdown"], "正在准备")
        self.assertEqual(case["preparing"]["tag"], "准备中")

    def test_snapshot_restore_without_selection_or_list_item(self):
        """快照重载且选择为空、列表项不在：仍从任务快照得到同一目标，不回退到别的场。"""
        res = run_js(r"""
S.selected = new Set();
S.items = [];
S.byId = new Map();
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "活动A",
  status: "waiting", sign_start: "2099-01-01 09:00:00", signup_mode: "pre_register" });
render();
const restored = { taskId: executionView().task.task_id,
  itemName: executionView().item.name,
  title: document.querySelector("#selected").textContent,
  route: !!routeTarget(),
  countdown: document.querySelector("#countdown").textContent };
/* 连 sign_start 都没有：显示「待公布」，不拿另一场或当前时间凑 */
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "活动A", status: "waiting" });
render();
const unknown = { openAt: executionView().openAt,
  countdown: document.querySelector("#countdown").textContent,
  label: document.querySelector("#led-label b").textContent,
  title: document.querySelector("#selected").textContent };
out.push({ restored, unknown });
""")
        case = res[0]
        self.assertEqual(case["restored"]["taskId"], "A")
        self.assertEqual(case["restored"]["itemName"], "活动A", "列表项缺失时用任务字段现构")
        self.assertEqual(case["restored"]["title"], "活动A")
        self.assertTrue(case["restored"]["route"], "路线目标必须仍能从任务快照得到")
        self.assertIn("同时开放 1 场", case["restored"]["countdown"])
        self.assertIsNone(case["unknown"]["openAt"])
        self.assertIn("时间待公布", case["unknown"]["countdown"])
        self.assertEqual(case["unknown"]["label"], "待公布")
        self.assertEqual(case["unknown"]["title"], "活动A", "缺字段也不得换成另一场")

    def test_single_failure_does_not_paint_plan(self):
        """单场失败只更新任务反馈；整屏色彩等计划级终态，且各终态各有其色。"""
        res = run_js(r"""
setResult(null);        /* 结果桩归零：桩默认 hidden=false，真实首屏是隐藏的 */
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
handleTask({ plan_id: "p1", task_id: "A", activity_id: "A", name: "活动A",
  status: "failed", reason: "名额已满", stop_reason: "max_attempts",
  sign_start: "2099-01-01 09:00:00", sign_end: "2099-01-02 09:00:00" });
const running = { board: document.querySelector("#board").dataset.planState,
  resultHidden: document.querySelector("#result").hidden,
  tasksHtml: document.querySelector("#plan-tasks").innerHTML };
handlePlanDone({ plan_id: "p1", status: "failed",
  summary: { counts: { failed: 1 } } });
const failed = { board: document.querySelector("#board").dataset.planState,
  resultVisible: !document.querySelector("#result").hidden,
  resultHtml: document.querySelector("#result").innerHTML,
  title: document.querySelector("#selected").textContent };
/* 结果页外框按原型 res 段由各场结论决定（result-panel D），不再只看计划 status：每种终态配上对应的场次 */
const colors = {};
const sets = {
  partial: [{ task_id: "A", activity_id: "A", status: "success" },
            { task_id: "B", activity_id: "B", status: "failed", stop_reason: "max_attempts" }],
  completed: [{ task_id: "A", activity_id: "A", status: "success" }],
  stopped: [{ task_id: "A", activity_id: "A", status: "canceled", stop_reason: "user_stopped" }],
};
Object.keys(sets).forEach((status) => {
  S.plan.status = status;
  S.plan.tasks = new Map(sets[status].map((t) => [t.task_id, t]));
  openResultPage();
  render();
  colors[status] = document.querySelector("#board").dataset.planState;
});
S.selected.add("zzz");
render();
colors.afterChange = document.querySelector("#board").dataset.planState;
out.push({ running, failed, colors });
""")
        case = res[0]
        self.assertEqual(case["running"]["board"], "running",
                         "单场失败不得把整屏染成计划失败")
        self.assertTrue(case["running"]["resultHidden"],
                        "运行中的单场失败不得抢写结果框")
        self.assertIn("task-state is-bad", case["running"]["tasksHtml"],
                      "任务卡要照实显示这一场失败")
        self.assertIn("报名未成功", case["running"]["tasksHtml"])
        self.assertIn("达到最大提交次数", case["running"]["tasksHtml"],
                      "任务卡要写出到达的停止条件")
        self.assertEqual(case["failed"]["board"], "failed")
        # 计划栏 1:1（result-panel D / plan-events setResult，P8）：结论改由计划栏标题承担，#result 条不再写计划结论
        self.assertEqual(case["failed"]["title"], "报名计划没有成功")
        self.assertFalse(case["failed"]["resultVisible"], "计划结束不再往 #result 条写结论")
        self.assertNotIn("报名计划没有成功", case["failed"]["resultHtml"])
        self.assertEqual(case["colors"]["partial"], "partial")
        self.assertEqual(case["colors"]["completed"], "completed")
        self.assertEqual(case["colors"]["stopped"], "stopped")
        self.assertEqual(case["colors"]["afterChange"], "idle",
                         "选择集合变了就回到常态，不继续挂着上一轮终态")


class RetryDeadlineBoundaryTests(unittest.TestCase):
    """BC-01：界面回退截止的锚点不能随墙钟跨过开放时刻而切换。

    样本按生产形状写：预报名提前 100 秒开页（run_started_at = 开放 - 100），
    运行期间还没有 retry_deadline 遥测。worker 的 retry_anchor 在开页前就钉死，
    界面若在开放那一秒改用启动点，会让截止倒退 100 秒。
    """

    def test_anchor_is_stable_across_open(self):
        """open-1 秒 / 开放瞬间 / open+1 秒：推导出的截止必须是同一时刻。"""
        res = run_js(r"""
const openTs = toTs("2026-10-25 20:00:00");
const task = { task_id: "A", status: "submitting", attempts: 1,
  sign_start: "2026-10-25 20:00:00", sign_end: "", retry_for_s: 120,
  run_started_at: openTs - 100 };
out.push({ before: effectiveRetryDeadline(task, openTs - 1),
  atOpen: effectiveRetryDeadline(task, openTs),
  after: effectiveRetryDeadline(task, openTs + 1),
  expected: openTs + 120 });
""")
        case = res[0]
        self.assertEqual(case["before"], case["expected"],
                         "开放前按 max(开放, 启动) 推导")
        self.assertEqual(case["atOpen"], case["expected"], "开放瞬间不得换锚")
        self.assertEqual(case["after"], case["expected"], "开放后不得倒退回启动点 + 时长")

    def test_truncation_fallback_and_telemetry(self):
        """sign_end 截断、迟到启动、时长 0 回退、遥测优先、未知返回 null。"""
        res = run_js(r"""
const openTs = toTs("2026-10-25 20:00:00");
const base = { task_id: "A", status: "submitting", attempts: 1,
  sign_start: "2026-10-25 20:00:00", retry_for_s: 120, run_started_at: openTs - 100 };
const truncated = effectiveRetryDeadline(
  Object.assign({}, base, { sign_end: "2026-10-25 20:01:00" }), openTs);
/* 迟到启动：开放后才拉起 worker（已开放场次按启动时刻起算） */
const late = effectiveRetryDeadline(
  Object.assign({}, base, { run_started_at: openTs + 30 }), openTs + 40);
/* 时长 0 且没有 sign_end：回退默认 120 秒 */
const zeroNoEnd = effectiveRetryDeadline(
  Object.assign({}, base, { retry_for_s: 0, sign_end: "" }), openTs);
/* 时长 0 且有 sign_end：直接截到报名截止 */
const zeroWithEnd = effectiveRetryDeadline(
  Object.assign({}, base, { retry_for_s: 0, sign_end: "2026-10-25 20:30:00" }), openTs);
/* 遥测优先：即便本机推导不同，也以 worker 的结构化截止为准 */
const telemetry = effectiveRetryDeadline(
  Object.assign({}, base, { retry_deadline: openTs + 300 }), openTs);
/* 已开放、又没有任何启动参考点：未知（不得拿 now 冒充 0 秒） */
const unknown = effectiveRetryDeadline(
  { task_id: "B", status: "submitting", sign_start: "2026-10-25 20:00:00",
    sign_end: "", retry_for_s: 120 }, openTs + 5);
/* 未来场且还没启动：原定开放作计划参考 */
const planned = effectiveRetryDeadline(
  { task_id: "C", status: "waiting", sign_start: "2026-10-25 21:00:00",
    sign_end: "", retry_for_s: 120 }, openTs);
out.push({ truncated, late, zeroNoEnd, zeroWithEnd, telemetry, unknown, planned,
  openTs });
""")
        case = res[0]
        self.assertEqual(case["truncated"], case["openTs"] + 60, "sign_end 必须硬截断")
        self.assertEqual(case["late"], case["openTs"] + 30 + 120,
                         "迟到启动从启动点起算，不再借用原定开放")
        self.assertEqual(case["zeroNoEnd"], case["openTs"] + 120,
                         "时长 0 且无截止时回退 120 秒")
        self.assertEqual(case["zeroWithEnd"], case["openTs"] + 1800,
                         "时长 0 且有截止时直接到截止")
        self.assertEqual(case["telemetry"], case["openTs"] + 300, "遥测必须优先")
        self.assertIsNone(case["unknown"], "没有时间参考时必须是未知，不是当前时刻")
        self.assertEqual(case["planned"], case["openTs"] + 3600 + 120,
                         "未来场未启动时用原定开放作计划参考")


    def test_absolute_deadline_needs_no_anchor(self):
        """ED-01：「直到报名截止」+ 已知 sign_end 时，截止与起点无关。

        排队中或快照字段还没齐时，正会出现「有绝对截止、没有启动/开放参考点」；
        这时不能判未知。有限时长仍需要起点，缺 sign_end 的 0 时长仍回退 120 秒。
        """
        res = run_js(r"""
const now = toTs("2026-10-25 21:00:00");
out.push({
  /* 已开放、没有 run_started_at / submitSeen / 遥测 */
  openPast: effectiveRetryDeadline({ status: "queued",
    sign_start: "2026-10-25 20:00:00", sign_end: "2026-10-25 22:00:00",
    retry_for_s: 0 }, now),
  /* 连开放时间都还没有，但有绝对截止 */
  noOpen: effectiveRetryDeadline({ status: "queued",
    sign_start: "", sign_end: "2026-10-25 22:00:00", retry_for_s: 0 }, now),
  /* 0 时长且没有 sign_end、也没有起点：确实未知 */
  noEnd: effectiveRetryDeadline({ status: "queued",
    sign_start: "2026-10-25 20:00:00", sign_end: "", retry_for_s: 0 }, now),
  /* 有限时长 + 无起点：仍未知（不能拿 now 起算） */
  finiteNoStart: effectiveRetryDeadline({ status: "queued",
    sign_start: "2026-10-25 20:00:00", sign_end: "2026-10-25 22:00:00",
    retry_for_s: 120 }, now),
  /* 0 时长 + 绝对截止 + 遥测：遥测优先 */
  telemetry: effectiveRetryDeadline({ status: "queued",
    sign_start: "", sign_end: "2026-10-25 22:00:00", retry_for_s: 0,
    retry_deadline: toTs("2026-10-25 21:30:00") }, now),
  deadline: toTs("2026-10-25 22:00:00"),
  telemetry_expected: toTs("2026-10-25 21:30:00"),
});
""")
        case = res[0]
        self.assertEqual(case["openPast"], case["deadline"],
                         "已开放无起点时，0 时长应直接取 sign_end")
        self.assertEqual(case["noOpen"], case["deadline"],
                         "连开放时间都没有，也不影响绝对截止")
        self.assertIsNone(case["noEnd"], "没有 sign_end 又无起点，只能未知")
        self.assertIsNone(case["finiteNoStart"], "有限时长缺起点仍未知，不拿 now 起算")
        self.assertEqual(case["telemetry"], case["telemetry_expected"],
                         "有遥测时以 worker 的结构化截止为准")
        self.assertLess(case["telemetry"], case["deadline"], "遥测优先于 sign_end")


class DisplayPhaseBoundaryTests(unittest.TestCase):
    """BC-02：raw submitting 只表示 worker 已接管，预热不等于已提交。"""

    def test_activity_row_tracks_phase_and_open_time(self):
        """活动行与任务卡共用阶段，缓存的未开放文本不能阻止跨开放时刻换组。"""
        res = run_js(r"""
const open = toTs("2099-01-01 09:00:00");
const item = { id: "A", sign_start: "2099-01-01 09:00:00",
  sign_end: "2099-01-01 10:00:00", state: "未开放" };
const task = { ...item, task_id: "A", status: "submitting", attempts: 0 };
setBusinessNow((open - 10) * 1000);
const waiting = stateCellHtml(item, stateOf(item), "10 秒", task);
setBusinessNow((open + 1) * 1000);
const preparing = stateCellHtml(item, stateOf(item), "已开放", task);
const rowState = stateOf(item);
task.attempts = 1;
const retrying = stateCellHtml(item, rowState, "已开放", task);
out.push({ waiting, preparing, retrying, rowState });
""")
        self.assertIn("等待开放", res[0]["waiting"])
        self.assertIn("准备报名", res[0]["preparing"])
        self.assertIn("提交中", res[0]["retrying"])
        self.assertEqual(res[0]["rowState"], "open")

    def test_future_prewarm_is_not_reported_as_submitting(self):
        """未来场 raw submitting（提前开页）：标题/LED/任务卡都必须是等待开放。

        再把时钟推过开放一秒并跑 tick：必须变成「准备报名」且不被旧文案盖回。
        """
        res = run_js(r"""
const openStr = "2099-01-01 09:00:00";
const openTs = toTs(openStr);
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map() };
S.plan.tasks.set("A", { task_id: "A", activity_id: "A", name: "未来场",
  status: "submitting", sign_start: openStr, page_opened_at: openTs - 100,
  signup_mode: "pre_register" });
render();
const before = { phase: executionView().phase, display: executionView().display,
  countdown: document.querySelector("#countdown").textContent,
  tag: document.querySelector("#board-tag-text").textContent,
  led: document.querySelector("#led-label b").textContent,
  html: document.querySelector("#plan-tasks").innerHTML,
  openHms: hmsDay(openTs) };   /* 同一业务时刻下算期望（下面会把时钟推到开放后） */
const openTs0 = openTs;
setBusinessNow((openTs0 + 1) * 1000);
tick();
const after = { phase: executionView().phase,
  countdown: document.querySelector("#countdown").textContent,
  tag: document.querySelector("#board-tag-text").textContent,
  detail: document.querySelector('.task-row[data-task-id="A"] .task-detail').textContent,
  label: document.querySelector('.task-row[data-task-id="A"] .task-state').textContent };
out.push({ before, after, openClock: fmtClock(openTs) });
""")
        case = res[0]
        self.assertEqual(case["before"]["phase"], "waiting", "未来预热不是提交阶段")
        self.assertEqual(case["before"]["display"], "preopen")
        self.assertIn("同时开放 1 场", case["before"]["countdown"])
        self.assertEqual(case["before"]["tag"], "等开放")
        # 计划栏 1:1（run-panel C）：原型 ex 段 led 的说明是 hms(cur.open)，跨天时前面加「明天 / 后天 / N 天后」；
        # 样本开在 2099 年，所以按 hmsDay 比，时刻部分仍必须是原定开放的 HH:MM:SS
        self.assertEqual(case["before"]["led"], case["before"]["openHms"],
                         "LED 必须走到原定开放，不是重试窗口")
        self.assertTrue(case["before"]["led"].endswith(case["openClock"]),
                        "LED 说明的时刻部分必须是原定开放")
        self.assertIn("提前准备", case["before"]["html"])
        self.assertNotIn("正在提交", case["before"]["html"],
                         "任务卡不得把预热说成已提交")
        self.assertIn("等待开放", case["before"]["html"])
        self.assertEqual(case["after"]["phase"], "arming", "开放后进入准备报名")
        self.assertIn("已开放", case["after"]["countdown"])
        self.assertEqual(case["after"]["tag"], "准备报名")
        self.assertNotIn("等开放", case["after"]["tag"], "已开放就不能还说等开放")
        self.assertIn("已开放，正在准备提交", case["after"]["detail"])
        self.assertEqual(case["after"]["label"], "准备报名",
                         "标签也要跟着 tick 更新，不能退回原始 submitting 文案")

    def test_missing_attempts_is_not_a_submission(self):
        """attempts 缺失或非法一律不算已提交（NaN/负数/字符串都不算）。"""
        res = run_js(r"""
const openTs = toTs("2026-10-25 19:00:00");
const phases = [
  taskDisplayPhase({ status: "submitting", sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "submitting", attempts: 0, sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "submitting", attempts: "abc", sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "submitting", attempts: -2, sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "submitting", attempts: 1, sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "queued", sign_start: "2026-10-25 19:00:00" }, openTs + 1),
  taskDisplayPhase({ status: "success", attempts: 3, sign_start: "2026-10-25 19:00:00" }, openTs + 1),
];
out.push({ phases });
""")
        phases = res[0]["phases"]
        self.assertEqual(phases[:4], ["preparing"] * 4, "没有真实提交就不能进 retrying")
        self.assertEqual(phases[4], "retrying")
        self.assertEqual(phases[5], "preparing", "已开放的排队任务是准备报名，不是等开放")
        self.assertEqual(phases[6], "terminal")


class AcceptanceDefectRegressionTests(unittest.TestCase):
    """验收时实测出来的三个真缺陷，各留一条能复现的回归。"""

    LOCKED = ('S.terms = { version: "2026-11-09-r6", acceptedVersion: "", acceptedAt: "",'
              ' declined: false, prompted: true, unknown: false }; \n')

    def test_retry_for_accepts_adaptive_choice(self):
        """-1 自动延长是官方模式（docs/RETRY_POLICY_GUIDE.md:230），不能被白名单回滚。"""
        res = run_js(r"""
S.retryPolicy = { retry_for_s: 120, max_attempts: 0 };
const pick = (value) => {
  const el = $("#retry-for");
  el.value = value;
  (el.listeners.change || []).forEach((fn) => fn({ target: el }));
  return { policy: S.retryPolicy.retry_for_s, shown: el.value };
};
out.push({ adaptive: pick("-1"), legal: pick("600"), illegal: pick("999") });
""")
        case = res[0]
        self.assertEqual(case["adaptive"]["policy"], -1,
                         "选自动延长必须落到 -1，而不是被回滚成原值")
        self.assertEqual(case["adaptive"]["shown"], "-1", "下拉不得被回写成旧值")
        self.assertEqual(case["legal"]["policy"], 600)
        self.assertEqual(case["illegal"]["policy"], 600, "非法值必须保持原状")
        self.assertEqual(case["illegal"]["shown"], "600",
                         "非法值要把下拉回写成当前生效值")

    def test_list_rows_disabled_while_terms_locked(self):
        """条款没同意时列表复选框必须禁用：不能只拦登录/刷新/开始，漏掉勾选。

        判据必须只由条款门决定，否则用例会恒真：夹具的签到窗口按调用时刻相对
        生成（stub 的业务时钟锚在真实墙钟上），这样活动永远「可报名」，复选框
        是否禁用就只剩 termsLocked() 一个自变量。再补一条正向对照，防止改成
        「行恒禁用」也能骗过断言。
        """
        now = dt.datetime.now(BEIJING_TZ)
        def stamp(hours):
            return (now + dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        fixture = (
            '{ id: "a", name: "可报名活动", sign_start: "%s", sign_end: "%s",'
            ' act_start: "%s", act_end: "%s", place: "A", signed: false }'
            % (stamp(-2), stamp(2), stamp(3), stamp(5))
        )
        res = run_js(self.LOCKED + r"""
const fixture = [%s];
const rowBox = (state) => {
  if (state === "accepted") { S.terms.acceptedVersion = S.terms.version; }
  applyActivities({ ok: true, items: fixture }, true);
  S.listState = "ready";
  render();
  const m = $("#rows").innerHTML.match(/<input class="row-check"[^>]*data-id="a"[^>]*>/);
  return { locked: termsLocked(), eligible: isEligibleForPlan(S.byId.get("a")),
           box: m ? m[0] : "" };
};
out.push({ locked: rowBox("locked"), accepted: rowBox("accepted") });
""" % fixture)
        case = res[0]
        locked, accepted = case["locked"], case["accepted"]
        self.assertTrue(locked["eligible"], "夹具必须落在报名窗口内，否则用例会变成恒真")
        self.assertTrue(locked["locked"], "前置没成立：条款必须先处于未同意")
        self.assertTrue(locked["box"], "没找到活动行的复选框，选择器口径变了")
        self.assertIn("disabled", locked["box"],
                      "条款未同意时可报名活动的复选框也必须禁用")
        self.assertNotIn("disabled", accepted["box"],
                         "正向对照：条款已同意时同一行必须可勾选")

    def test_quick_pick_blocked_by_terms_gate(self):
        """「选这一场」是大屏的快捷选择，走的也是 toggleSelection，同样要被条款门拦住。"""
        now = dt.datetime.now(BEIJING_TZ)
        def stamp(hours):
            return (now + dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        res = run_js(self.LOCKED + r"""
applyActivities({ ok: true, items: [
  { id: "a", name: "可报名活动", sign_start: "%s", sign_end: "%s",
    act_start: "%s", act_end: "%s", place: "A", signed: false }] }, true);
S.listState = "ready";
S.selected = new Set();
toggleSelection("a", true);
const lockedPicked = S.selected.size;
S.terms.acceptedVersion = S.terms.version;
toggleSelection("a", true);
out.push({ lockedPicked: lockedPicked, acceptedPicked: S.selected.size });
""" % (stamp(-2), stamp(2), stamp(3), stamp(5)))
        case = res[0]
        self.assertEqual(case["lockedPicked"], 0,
                         "条款未同意时「选这一场」不能把活动放进选择集合")
        self.assertEqual(case["acceptedPicked"], 1,
                         "正向对照：同意后同一条路径必须能选中")

    def test_empty_state_does_not_point_to_disabled_refresh(self):
        """未同意时「刷新」是禁用的，空态不能还让人点刷新。"""
        res = run_js(self.LOCKED + r"""
S.items = [];
S.byId = new Map();
S.listState = "idle";
S.selected = new Set();
render();
out.push({ text: document.querySelector("#empty-text").textContent,
  action: document.querySelector("#empty-action").textContent,
  intent: document.querySelector("#empty-action").dataset.action,
  refreshDisabled: $("#btn-refresh").disabled });
""")
        case = res[0]
        self.assertTrue(case["refreshDisabled"], "前置没成立：未同意时刷新必须禁用")
        self.assertNotIn("点「刷新」", case["text"], "禁用状态下不得再提示点刷新")
        self.assertIn("条款", case["text"], "空态要给条款这条真正的出路")
        self.assertEqual(case["action"], "查看条款",
                         "按钮也不能指向被禁用的刷新，否则只是把死路从文案挪到按钮")
        self.assertEqual(case["intent"], "terms-open", "按钮要真的能打开条款")


class PlanPanelPrototypeTests(unittest.TestCase):
    """计划栏向原型 1:1（计划 20261106-plan-panel）：草稿、运行、结果三段按原型 Main.dc.html 视图模型的新行为。

    草稿：draft / checks / blockers / editNote；运行：ex / head / runWarnV / card；结果：res 段与结果页标记。
    """

    # ---------------- draft-panel
    def test_draft_one_selected_title_and_checks(self):
        """选 1 场：标题「已选 1 场」、副行一句汇总；检查条照原型 checks 只列未满足的，全满足无提醒只留一条 ✓。"""
        res = run_js(WB_STAMP_JS + PP_LOGIN_OK_JS + r"""
seed([{ id: "a1", name: "甲活动", place: "一号楼", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200),
        act_start: stamp(now + 86400), act_end: stamp(now + 90000) }]);
S.selected = new Set(["a1"]);
render();
const ok = { title: document.querySelector("#selected").textContent,
  sub: document.querySelector("#board-text").textContent,
  meta: document.querySelector("#selected-meta").innerHTML,
  checks: document.querySelector("#plan-checks").innerHTML,
  tag: document.querySelector("#board-tag-text").textContent };
S.login.result = "expired"; S.login.ok = false;
paintLogin();   /* 生产里登录结论由 check 事件经 paintLogin 写进 S.login.view，检查条读它 */
render();
const expired = { checks: document.querySelector("#plan-checks").innerHTML,
  why: document.querySelector("#plan-why").innerHTML };
S.selected = new Set();
S.login.result = "valid"; S.login.ok = true;
paintLogin();
render();
const none = { checks: document.querySelector("#plan-checks").innerHTML };
out.push({ ok, expired, none });
""")
        r = res[0]
        self.assertEqual(r["ok"]["title"], "已选 1 场", "原型 draft.title：一律「已选 N 场」")
        self.assertEqual(r["ok"]["sub"], "1 场预报名等开放", "原型 summary：为 0 的一半不写")
        self.assertEqual(r["ok"]["meta"], "", "选了活动不再复读地点时间（票里有）")
        self.assertEqual(r["ok"]["checks"].count('class="chk"'), 1, "全满足且无提醒只留一条")
        self.assertIn("登录、北京时间和举办时间都没问题", r["ok"]["checks"])
        self.assertIn('data-tone="ok"><i aria-hidden="true">✓</i>', r["ok"]["checks"])
        self.assertEqual(r["expired"]["checks"].count('class="chk"'), 1, "只列未满足的那一条")
        self.assertIn('data-tone="no"><i aria-hidden="true">!</i>登录已失效', r["expired"]["checks"])
        self.assertIn("还差一步：登录已失效", r["expired"]["why"])
        self.assertIn('data-act="login">重新登录</button>', r["expired"]["why"])
        self.assertIn("登录和北京时间都没问题", r["none"]["checks"], "没选活动时的那一句")

    def test_draft_clock_blocker_resyncs_directly(self):
        """「还差一步：北京时间还没校准」的按钮叫「重新校准」，直接触发校准（原型 blockers 的 syncClock）。"""
        res = run_js(WB_STAMP_JS + PP_LOGIN_OK_JS + r"""
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) }]);
S.selected = new Set(["a1"]);
businessNowMs = () => null;
updateControls();
out.push({ why: document.querySelector("#plan-why").innerHTML,
  hidden: document.querySelector("#plan-why").hidden,
  board: typeof resyncClock });
""")
        r = res[0]
        self.assertFalse(r["hidden"])
        self.assertIn("还差一步：北京时间还没校准", r["why"])
        self.assertIn('data-act="clock-sync">重新校准</button>', r["why"])
        self.assertEqual(r["board"], "function")
        app = read("ui/app.js")
        self.assertIn('else if (act === "clock-sync") resyncClock();', app, "按钮直接触发重新校准")

    def test_draft_edit_note_counts_down_inside_300_seconds(self):
        """修改中：#edit-note 三句拼成，离最近一场开放不到 300 秒时报剩余时间；主按钮叫「重新开始计划」。"""
        res = run_js(WB_STAMP_JS + PP_LOGIN_OK_JS + r"""
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 200), sign_end: stamp(now + 7200) }]);
S.selected = new Set(["a1"]);
S.busy = false;
S.editing = { ids: ["a1"], doneN: 1 };
render();
const near = { note: document.querySelector("#edit-note").textContent,
  hidden: document.querySelector("#edit-note").hidden,
  tag: document.querySelector("#board-tag-text").textContent,
  start: document.querySelector("#btn-plan").textContent };
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 900), sign_end: stamp(now + 7200) }]);
S.editing = { ids: ["a1"], doneN: 0 };
render();
const far = { note: document.querySelector("#edit-note").textContent };
out.push({ near, far });
""")
        r = res[0]
        self.assertFalse(r["near"]["hidden"])
        self.assertTrue(r["near"]["note"].startswith("计划已暂停，重新开始前不会自动报名。"), r["near"]["note"])
        self.assertIn("已结束的 1 场不受影响。", r["near"]["note"])
        self.assertIn("离最近一场开放只剩", r["near"]["note"])
        self.assertEqual(r["near"]["tag"], "修改中")
        self.assertEqual(r["near"]["start"], "重新开始计划")
        self.assertEqual(r["far"]["note"], "计划已暂停，重新开始前不会自动报名。", "超过 300 秒、没有已结束的就只有第一句")

    # ---------------- run-panel
    def _run_one(self, extra, task):
        return run_js(WB_STAMP_JS + PP_LOGIN_OK_JS + r"""
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) }]);
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
/* LED 下方说明的前半句：桩里文本节点不进 textContent，按调用记下来 */
const __caps = [];
const __realCap = paintLedLabel;
paintLedLabel = (prefix, value) => { __caps.push(String(prefix)); return __realCap(prefix, value); };
""" + extra + r"""
const put = (patch) => { S.plan.tasks.clear();
  S.plan.tasks.set("t1", Object.assign({ task_id: "t1", activity_id: "a1", name: "甲活动",
    signup_mode: "pre_register" }, patch)); };
const look = () => { paintLogin(); render(); return {
  tag: document.querySelector("#board-tag-text").textContent,
  cap: document.querySelector("#board-text").textContent,
  meta: document.querySelector("#selected-meta").innerHTML,
  warn: document.querySelector("#run-warn").innerHTML,
  warnHidden: document.querySelector("#run-warn").hidden,
  led: __caps[__caps.length - 1] || "",
  ledB: document.querySelector("#led-label b").textContent,
  tasks: document.querySelector("#plan-tasks").innerHTML,
  pill: document.querySelector("#pill-text").textContent,
  banners: document.querySelector("#banners").innerHTML }; };
""" + task)

    def test_run_tag_turns_soon_inside_five_seconds(self):
        """等开放：离开放大于 5 秒「等开放」，5 秒以内「即将开放」（原型 ex 段 head，P18）。"""
        res = self._run_one("", r"""
put({ status: "waiting", sign_start: stamp(now + 4) }); const four = look();
put({ status: "waiting", sign_start: stamp(now + 5) }); const five = look();
put({ status: "waiting", sign_start: stamp(now + 6) }); const six = look();
out.push({ four, five, six, open6: hmsDay(now + 6) });
""")
        r = res[0]
        self.assertEqual(r["four"]["tag"], "即将开放")
        self.assertEqual(r["five"]["tag"], "即将开放", "5 秒（含）以内")
        self.assertEqual(r["six"]["tag"], "等开放")
        self.assertEqual(r["six"]["cap"], "这一场等开放，到点自动开始。")
        self.assertEqual(r["six"]["meta"], "", "运行态不写地点时间（原型运行态没有）")
        self.assertEqual(r["six"]["led"], "开放时间")
        self.assertEqual(r["six"]["ledB"], r["open6"])

    def test_run_submitting_single_caption_and_cancel_label(self):
        """提交中、只有 1 场：「已提交 N 次，最近：<原因>」；等开放的任务卡取消按钮叫「取消这一场」。"""
        res = self._run_one("", r"""
put({ status: "submitting", sign_start: stamp(now - 5), attempts: 3, last_reason: "还没开放",
      retry_deadline: now + 115 });
const sub = look();
put({ status: "waiting", sign_start: stamp(now + 900) }); const wait = look();
put({ status: "queued", sign_start: stamp(now + 900) }); const queued = look();
out.push({ sub, wait, queued, until: hmsDay(now + 115) });
""")
        r = res[0]
        self.assertTrue(r["sub"]["cap"].startswith("已提交 3 次，最近："), r["sub"]["cap"])
        self.assertEqual(r["sub"]["cap"], "已提交 3 次，最近：还没开放")
        self.assertEqual(r["sub"]["tag"], "正在提交")
        self.assertEqual(r["sub"]["led"], "本次尝试到", "原型 ex 段 led：本次尝试到 HH:MM:SS")
        self.assertEqual(r["sub"]["ledB"], r["until"])
        self.assertIn("已提交 3 次（不限次数）。最近：还没开放，重试到 ", r["sub"]["tasks"])
        self.assertIn(">取消这一场</button>", r["wait"]["tasks"])
        self.assertIn(">取消这一场</button>", r["queued"]["tasks"], "queued 也是还没提交，照样能取消")
        self.assertNotIn(">取消</button>", r["wait"]["tasks"])

    def test_run_warn_relogin_window_and_too_late(self):
        """运行中登录失效：离开放 300 秒给「只要在 … 前重新登录」和按钮；60 秒说来不及、不给按钮（原型 runWarnV）。"""
        res = self._run_one(r"""
S.login.result = "expired"; S.login.ok = false;
""", r"""
put({ status: "waiting", sign_start: stamp(now + 300) }); const far = look();
put({ status: "waiting", sign_start: stamp(now + 60) }); const near = look();
out.push({ far, near, expect: hmsDay(now + 200) });
""")
        r = res[0]
        self.assertFalse(r["far"]["warnHidden"])
        self.assertIn("只要在 " + r["expect"] + " 前重新登录，计划照常继续", r["far"]["warn"])
        self.assertIn('data-act="login">重新登录</button>', r["far"]["warn"])
        self.assertIn("来不及重新登录", r["near"]["warn"])
        self.assertIn("这一批会以“登录失效”结束。", r["near"]["warn"])
        self.assertNotIn("<button", r["near"]["warn"], "来不及时不给重新登录按钮")

    def test_busy_pill_shows_expired_but_keeps_unknown(self):
        """运行中学校明确说登录失效：胶囊「登录已失效」、横幅「报名计划还在等」；网络原因的 unknown 仍是「已登录」。"""
        res = self._run_one(r"""
S.login.result = "expired"; S.login.ok = false;
""", r"""
put({ status: "waiting", sign_start: stamp(now + 900) }); const expired = look();
S.login.result = "unknown"; S.login.ok = false;
const unknown = look();
out.push({ expired, unknown });
""")
        r = res[0]
        self.assertEqual(r["expired"]["pill"], "登录已失效", "决策 014 第 8 条：运行中失效要说出来")
        self.assertIn("报名计划还在等", r["expired"]["banners"])
        self.assertEqual(r["unknown"]["pill"], "已登录", "网络原因的暂时无法确认不打扰运行中的计划")

    # ---------------- result-panel
    def _result(self, tasks, status, after="", via="task"):
        body = WB_STAMP_JS + PP_LOGIN_OK_JS + r"""
seed([
  { id: "a1", name: "甲", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
  { id: "a2", name: "乙", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
  { id: "a3", name: "丙", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
]);
S.selected = new Set(["a1", "a2", "a3"]);
window.onBackend.plan({ plan_id: "p1", status: "running", tasks: [] });
"""
        if via == "plan":
            # 场次结论随计划快照一起到（plan 事件带 tasks，不逐场发 task 事件）：成功场次到 plan_done
            # 才被移出选择集合——P1 里结果页就是在这一步退回草稿的
            body += "window.onBackend.plan(%s);\n" % json.dumps(
                {"plan_id": "p1", "status": "running", "tasks": tasks}, ensure_ascii=False)
        else:
            for task in tasks:
                body += "window.onBackend.task(%s);\n" % json.dumps(dict(task, plan_id="p1"), ensure_ascii=False)
        body += "const beforeDone = Array.from(S.selected).sort();\n"
        body += "window.onBackend.plan_done({ plan_id: \"p1\", status: %s, summary: {} });\n" % json.dumps(status)
        body += r"""
const view = () => ({
  tag: document.querySelector("#board-tag-text").textContent,
  title: document.querySelector("#selected").textContent,
  sub: document.querySelector("#board-text").textContent,
  meta: document.querySelector("#selected-meta").innerHTML,
  stats: document.querySelector("#plan-stats").innerHTML,
  statsHidden: document.querySelector("#plan-stats").hidden,
  reselectHidden: document.querySelector("#btn-reselect").hidden,
  resultActionsHidden: document.querySelector("#result-actions").hidden,
  draftActionsHidden: document.querySelector("#route-actions").hidden,
  tickets: document.querySelector("#plan-tickets").innerHTML,
  policyHidden: document.querySelector("#policy-line").hidden,
  ledHidden: document.querySelector("#led-box").hidden,
  resultHidden: document.querySelector("#result").hidden,
  tasks: document.querySelector("#plan-tasks").innerHTML,
  frame: document.querySelector("#board").dataset.planState,
  selected: Array.from(S.selected).sort(), beforeDone: beforeDone });
const done = view();
""" + after + r"""
out.push({ done, later: typeof later === "undefined" ? null : later });
"""
        return run_js(body)[0]

    def test_result_partial_with_pending_and_no_fallback(self):
        """两场成功一场待核对：大数字「已报名 2」「待核对 1」，标题副行照原型 res；成功场次被移出选择后也不回落。"""
        tasks = [
            {"task_id": "t1", "activity_id": "a1", "name": "甲", "status": "success", "stop_reason": "success", "attempts": 1},
            {"task_id": "t2", "activity_id": "a2", "name": "乙", "status": "success", "stop_reason": "success", "attempts": 1},
            {"task_id": "t3", "activity_id": "a3", "name": "丙", "status": "failed", "stop_reason": "unconfirmed", "attempts": 2},
        ]
        r = self._result(tasks, "partial", r"""
/* 刷新取回学校列表：两场成功的显示已报名，被自动移出选择（controllers/refresh.js）——不是用户改勾选 */
window.onBackend.activities({ ok: true, request_id: "l1", items: [
  { id: "a1", name: "甲", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200), signed: true },
  { id: "a2", name: "乙", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200), signed: true },
  { id: "a3", name: "丙", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200), signed: false } ] });
noteSignedTasks(Array.from(S.plan.tasks.values()));
render();
const refreshed = view();
/* 用户自己在时刻表改勾选：结果页到此关闭 */
toggleSelection("a3", false);
const changed = view();
const later = { refreshed, changed };
""", via="plan")
        done = r["done"]
        self.assertEqual(done["beforeDone"], ["a1", "a2", "a3"], "对照：plan_done 之前成功场次还在选择里")
        self.assertEqual(done["selected"], ["a3"], "成功场次已移出选择集合")
        self.assertEqual(_pp_stats(done["stats"]), {"已报名": 2, "待核对": 1})
        self.assertFalse(done["statsHidden"])
        self.assertEqual(done["tag"], "部分完成")
        self.assertEqual(done["title"], "报名计划部分完成", "成功场次被移出选择也不回落成「下一场」")
        self.assertEqual(done["sub"], "有 1 场需要到活动页核对，结果以学校为准。")
        self.assertEqual(done["meta"], "", "结果页不写地点时间")
        self.assertEqual(done["tickets"], "", "结果页不摆草稿的票")
        self.assertTrue(done["policyHidden"], "结果页不显示尝试设置")
        self.assertTrue(done["draftActionsHidden"], "结果页不显示检查条、提醒、还差一步")
        self.assertFalse(done["resultActionsHidden"])
        self.assertTrue(done["ledHidden"], "部分完成不显示 LED（原型 res.hasLed）")
        self.assertTrue(done["resultHidden"], "结论不再写进 #result 条（P8）")
        self.assertEqual(done["frame"], "partial")
        self.assertIn(">刷新核对</button>", done["tasks"], "待核对场次只给「刷新核对」")
        self.assertNotIn("打开活动页", done["tasks"])
        self.assertIn("没拿到确定回应；结束时向学校核对也没查到结果。", done["tasks"])
        later = r["later"]
        self.assertEqual(later["refreshed"]["title"], "报名计划部分完成", "刷新移出成功场次也不关结果页")
        self.assertNotEqual(later["changed"]["title"], "报名计划部分完成", "用户改了勾选就离开结果页")
        self.assertTrue(later["changed"]["statsHidden"])

    def test_result_only_full_has_no_reselect(self):
        """只有名额已满：标题「这次没报上：名额满了」，不放「重新选择未成功的场次」（原型 res.canRetry）。"""
        r = self._result([
            {"task_id": "t1", "activity_id": "a1", "name": "甲", "status": "failed", "stop_reason": "full", "attempts": 4},
        ], "failed")
        done = r["done"]
        self.assertEqual(done["title"], "这次没报上：名额满了")
        self.assertEqual(done["tag"], "名额已满")
        self.assertEqual(done["sub"], "学校的名额在开放后被报满了，不是工具出错。")
        self.assertEqual(_pp_stats(done["stats"]), {"名额已满": 1})
        self.assertTrue(done["reselectHidden"], "名额已满不放回重新选择")
        self.assertFalse(done["resultActionsHidden"], "「完成，回到活动列表」还在")
        self.assertIn("学校说报名人数已满，这一场到此结束，不再提交。不是工具出错。已提交 4 次", done["tasks"])

    def test_result_stopped_counts_canceled(self):
        """用户停止：「已取消」计数出现，标题「报名计划已停止」，没提交的场次写「计划已停止，这一场没有提交」。"""
        r = self._result([
            {"task_id": "t1", "activity_id": "a1", "name": "甲", "status": "success", "stop_reason": "success", "attempts": 1,
             "last_reason": "报名成功！"},
            {"task_id": "t2", "activity_id": "a2", "name": "乙", "status": "canceled", "stop_reason": "user_stopped"},
        ], "stopped")
        done = r["done"]
        self.assertEqual(_pp_stats(done["stats"]), {"已报名": 1, "已取消": 1})
        self.assertEqual(done["title"], "报名计划已停止")
        self.assertEqual(done["tag"], "已停止")
        self.assertEqual(done["sub"], "已提交的场次保留原状态，还没提交的场次已取消。")
        self.assertIn("计划已停止，这一场没有提交", done["tasks"])
        self.assertIn("学校回“报名成功”，结束时向学校核对过：已报名", done["tasks"])
        self.assertFalse(done["reselectHidden"], "已取消的可以重新选")

    def test_result_all_success_shows_mini_led(self):
        """全部报上：标签「报名成功」、标题「报名计划完成」，只这时（和全失败）显示缩小的 LED。"""
        r = self._result([
            {"task_id": "t1", "activity_id": "a1", "name": "甲", "status": "success", "stop_reason": "success", "attempts": 1},
        ], "completed")
        done = r["done"]
        self.assertEqual(done["tag"], "报名成功")
        self.assertEqual(done["title"], "报名计划完成")
        self.assertEqual(done["sub"], "每场结束时都向学校核对过。")
        self.assertFalse(done["ledHidden"])
        self.assertEqual(done["frame"], "completed")
        self.assertTrue(done["reselectHidden"], "没有可重选的场次")

    def test_result_not_complete_while_a_task_is_still_waiting(self):
        """计划结束时还有一场停在 waiting：不能说「报名计划完成」，走「部分完成」。"""
        r = self._result([
            {"task_id": "t1", "activity_id": "a1", "name": "甲", "status": "success", "stop_reason": "success", "attempts": 1},
            {"task_id": "t2", "activity_id": "a2", "name": "乙", "status": "waiting", "stop_reason": "", "attempts": 0},
        ], "partial")
        done = r["done"]
        self.assertEqual(done["title"], "报名计划部分完成")
        self.assertEqual(done["tag"], "部分完成")
        self.assertNotEqual(done["title"], "报名计划完成")

    def test_stop_ask_closes_when_plan_ends(self):
        """停止确认弹层开着时计划结束：弹层收起，焦点不留在隐藏元素上（原型 finishState 的 stopAsk:false）。"""
        res = run_js(StopAskBehaviorTests.SETUP + r"""
stopBtn.click();
const opened = !ask.hidden;
const focusedBefore = document.activeElement.__sel;
setBusy(false);
S.plan = { id: "p1", status: "completed", tasks: new Map() };
updateControls();
const act = document.activeElement;
out.push({ opened, focusedBefore, hidden: ask.hidden, active: act && act.__sel,
  activeHidden: !!(act && (act.id === "btn-stop-keep" || act.id === "btn-stop-yes")) });
""")
        self.assertTrue(res[0]["opened"])
        self.assertEqual(res[0]["focusedBefore"], "#btn-stop-keep")
        self.assertTrue(res[0]["hidden"], "计划结束后弹层必须收起")
        self.assertFalse(res[0]["activeHidden"], "焦点不能留在已隐藏的弹层按钮上")

    def test_task_prepared_uses_checkpoint_time(self):
        """等待开放：准备好了「已准备好，HH:MM:SS 开放时提交」，还没准备好「提前准备，等到 HH:MM:SS 开放」（原型 card）。"""
        res = self._run_one("", r"""
put({ status: "waiting", sign_start: stamp(now + 900) }); const plain = look();
put({ status: "waiting", sign_start: stamp(now + 900), watch_started_at: now - 3 }); const ready = look();
out.push({ plain, ready, open: hmsDay(now + 900) });
""")
        r = res[0]
        self.assertIn("提前准备，等到 " + r["open"] + " 开放", r["plain"]["tasks"])
        self.assertIn("已准备好，" + r["open"] + " 开放时提交", r["ready"]["tasks"])


if __name__ == "__main__":
    unittest.main()
