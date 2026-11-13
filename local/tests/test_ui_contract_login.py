# -*- coding: utf-8 -*-
"""界面契约：登录三态、启动闸门与重登后刷新。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read, run_js  # noqa: E402


class LoginStateContractTests(unittest.TestCase):
    """首次使用 / 登录失效 / 有效登录三态契约（防「首次使用被当成登录失效」回归）。

    「没有登录」= session.json 不存在、无法解析或缺少 token；
    仅有过期 token（present=true 且过期/校验失败）属于登录态失效；
    hours_left=0 不能单独代表首次未登录。
    """

    def test_backend_login_state_fields_in_payloads(self):
        py = read("app.py")
        self.assertIn("def login_state", py, "app.py 必须有三态快照函数 login_state")
        # check 事件载荷整理已下沉 application.login_service：三态字段随载荷迁移
        svc = read("application/login_service.py")
        for field in ("session_present", "session_expired"):
            self.assertIn('"%s"' % field, svc, "登录载荷缺字段 %s" % field)

    def test_login_state_semantics(self):
        import json
        import sys
        import tempfile
        from datetime import datetime, timedelta
        from unittest import mock

        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        tmp = Path(tempfile.mkdtemp())
        # login_state/token_hours_left 读的是模块级 SESSION_FILE（runtime_paths
        # 统一数据根），不是 HERE：patch 错目标会让隔离失效、摸到真实登录态
        session = tmp / "session.json"
        prefs = tmp / "ui.json"
        with mock.patch.object(local_app, "SESSION_FILE", session), \
             mock.patch.object(local_app, "PREFS", prefs):
            absent = local_app.login_state()
            self.assertFalse(absent["session_present"], "文件不存在=未登录")
            self.assertIsNone(absent["hours_left"])

            session.write_text("{坏掉的 json", encoding="utf-8")
            unparseable = local_app.login_state()
            self.assertFalse(unparseable["session_present"], "解析失败=未登录")

            fresh = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.write_text(json.dumps({"saved_at": fresh}), encoding="utf-8")
            no_token = local_app.login_state()
            self.assertFalse(no_token["session_present"],
                             "缺 token 不得按 saved_at 报成已登录")
            self.assertIsNone(no_token["hours_left"],
                              "空壳会话不得显示有效小时数")

            session.write_text(json.dumps({"token": "t", "saved_at": fresh}), encoding="utf-8")
            valid = local_app.login_state()
            self.assertTrue(valid["session_present"])
            self.assertFalse(valid["session_expired"])
            # 决策 012：无 v2 锚点不报数——旧 saved_at 不能冒充准确小时数
            self.assertIsNone(valid["hours_left"])

            stale = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
            session.write_text(json.dumps({"token": "t", "saved_at": stale}), encoding="utf-8")
            expired = local_app.login_state()
            self.assertTrue(expired["session_present"], "过期=登录过")
            # 旧墙钟文本不改判失效：有效性只由学校真实校验决定
            self.assertFalse(expired["session_expired"])
            self.assertIsNone(expired["hours_left"])

    def test_check_hint_success_beats_login_keyword(self):
        """code==0 的成功行常含「登录」字样（如「登录态还有 17 小时」），不得归类 login。"""
        import sys
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        self.assertEqual(local_app._check_hint("[OK] 登录态还有 17 小时", 0), "")
        self.assertEqual(local_app._check_hint("[X] 本机还没有登录过", 3), "login")

    def test_app_js_first_use_is_not_bad(self):
        js = read("ui/app.js")
        self.assertIn("S.login.present", js,
                      "paintLogin 必须用 session_present 区分首次使用")
        self.assertIn("S.login.present === false", js,
                      "present=false 必须走未登录分支，不显示登录态失效")
        self.assertIn("S.login.present !== false", js,
                      "bad 分支必须放过 present=false（hours_left=0 不代表首次未登录）")
        self.assertIn('state === "bad" || state === "warn" || state === "ok" ? "重新登录" : "登录"',
                      js, "按钮文案：只有登录过的状态才叫「重新登录」，首次使用叫「登录」")

    def test_app_js_reuse_login_copy_contract(self):
        """运行记录文案「已复用本机登录态」与 README 示例、UI_SPEC §5.9 同源，禁止回退。"""
        js = read("ui/app.js")
        self.assertIn("已复用本机登录态", js,
                      "运行记录必须是「已复用本机登录态」（local/README.md 示例同源）")
        self.assertNotIn("已复用本机登录状态", js,
                         "运行记录不得回退写「已复用本机登录状态」（文案同源契约）")


class StartGateContractTests(unittest.TestCase):
    """检查异常兜底与开始门禁：checking/unknown 不能启动真实计划，demo 可演示。"""

    def test_refresh_catch_leaves_checking(self):
        """check 调用失败（桥接/脚本异常）也必须离开「检查中」并落 unknown。"""
        js = read("ui/app.js")
        start = js.index("function refresh(")
        body = js[start:js.index("function applyActivities", start)]
        self.assertIn("S.login.checking = false", body,
                      "refresh 的 catch 必须清除「检查中」，不得永远停在检查态")
        self.assertIn('S.login.result = "unknown"', body,
                      "check 失败必须落 unknown 结论，给出「点刷新重试」的下一步")
        self.assertIn("S.login.ok = false", body,
                      "旧 ok 不清掉的话 unknown 分支接不住，顶栏会残留「登录有效」")

    def test_refresh_catch_failure_leaves_checking_and_sets_unknown(self):
        """行为测试：check 桥接抛错后，必须离开 checking、落 unknown、写日志。

        这条钉住 catch 分支真的在运行时清了三态，不是只有源码字符串断言。
        """
        res = run_js(r"""
window.pywebview = { api: {
  check: () => {
    return Promise.reject(new Error("bridge down"));
  },
  list_activities: () => new Promise(() => {}),  // 永不完成
} };
// 条款已同意：S.terms.acceptedVersion 与 S.terms.version 相等
S.terms = { version: "v1", acceptedVersion: "v1", acceptedAt: "2026-11-05 10:00" };
S.online = true;
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
refresh(false);
// 让 catch 分支跑完（async 调度）
await Promise.resolve();
await Promise.resolve();
out.push({
  checking: S.login.checking,
  ok: S.login.ok,
  result: S.login.result,
  logs: S.recentLogs.slice(),
});
""")
        row = res[0]
        self.assertFalse(row["checking"],
                         "桥接失败后 checking 必须清掉，不能永远停在「检查中」")
        self.assertFalse(row["ok"],
                         "桥接失败后 ok 必须清掉，否则 unknown 分支接不住")
        self.assertEqual(row["result"], "unknown",
                         "桥接失败后 result 必须是 unknown，不是 valid/none/expired")
        log_text = "\n".join(row["logs"])
        self.assertIn("检查登录状态失败", log_text,
                      "运行记录里要有失败说明")

    def test_start_button_requires_valid_or_demo(self):
        """开始按钮门禁：只有登录校验 valid 且不在检查中，或 demo 模式放行。"""
        js = read("ui/app.js")
        start = js.index("function updateControls(")
        body = js[start:js.index("function paintBanners", start)]
        self.assertIn('S.login.result === "valid"', body,
                      "开始按钮必须要求登录校验 valid（unknown/none/expired 禁用）")
        self.assertIn("!S.login.checking", body,
                      "checking 必须显式禁用开始：新一轮检查不清旧 valid，不排除会放行未确认期")
        self.assertIn("S.demo", body, "demo 模式必须能绕过登录门禁继续视觉演示")

    def test_bootstrap_carries_demo_flag(self):
        py = read("app.py")
        start = py.index("def bootstrap")
        body = py[start:py.index("def help(", start)]
        self.assertIn('"demo"', body, "bootstrap 载荷必须带 demo 标记，前端门禁才能放行演示")

    def test_backend_start_plan_rejects_unconfirmed_login(self):
        """后端最终防线：非 demo 且最近 check 结论不是 valid 时拒绝。"""
        py = read("app.py")
        start = py.index("def start_plan")
        body = py[start:py.index("def cancel_task", start)]
        self.assertIn('result == "valid"', body,
                      "start_plan 必须以「最近 check 结论 valid」为唯一放行形态")
        self.assertIn("DEMO", body, "demo 模式继续可运行演示计划")
        for state in ("checking", "none", "expired"):
            self.assertIn(state, body, "start_plan 门禁必须覆盖 %s" % state)


class StateGapsContractTests(unittest.TestCase):
    """登录到期检查、时钟偏差、断网/睡眠、断点与错误行动按钮的静态契约。"""

    def test_login_expiry_check_present(self):
        """开始前不拿登录估算比报名窗口；改为按最晚一场要等多久 + 自动登录开没开全来提醒。

        旧断言要求检查条写「预计可覆盖本次窗口」并用 earliestSelectedExecutionEnd 比较：
        学校不公布有效期、工具不估算（架构方案 4.5）后，这条比较没有依据，函数一并删除；
        由开始前提醒第 3 条取代（设计第 5 节，开放前 100 秒内失效的那场直接结束）。"""
        js = read("ui/app.js")
        self.assertIn("function paintChecks", js, "缺少检查条 paintChecks")
        # 计划栏 1:1（draft-panel F）：检查条照原型 checks 只列未满足的登录结论，判断移进 planCheckList，
        # 读的是 paintLogin 写好的 S.login.view.state（ok 只在学校确认有效时出现）
        checks = js[js.index("function planCheckList("):js.index("function autoLoginCredential")]
        self.assertIn('(S.login.view || {}).state', checks, "检查条只报学校的登录结论")
        self.assertIn('login !== "ok"', checks, "登录不是学校确认有效就列为未满足")
        for banned in ("预计", "expireAt", "loginHoursLeft"):
            self.assertNotIn(banned, checks, "检查条不得再拿登录估算说事（%s）" % banned)
        self.assertNotIn("earliestSelectedExecutionEnd", js, "登录估算比较窗口的函数不得残留")
        self.assertNotIn("预计可覆盖本次窗口", js, "不得再给登录覆盖窗口的估算结论")
        self.assertNotIn("登录撑得到这次报名窗口", js,
                         "不得再用保证式结论：登录有效性只由学校校验决定")
        warns = js[js.index("function preStartWarnings("):js.index("function paintPrewarn")]
        self.assertIn("latest - now > 3600", warns, "按最晚一场要等 1 小时以上来提醒")
        # 计划栏 1:1（draft-panel G）：句子照原型 loginWarn
        self.assertIn("开放前 100 秒内失效，那场就结束。", warns, "要讲清来不及重新登录的后果")

    def test_clock_skew_structured_and_not_text_scraped(self):
        """R08：学校 HTTP 粗测只认结构化载荷，逐轮替换，不再从文本猜。"""
        js = read("ui/app.js")
        self.assertIn("function applyClock", js, "必须有一个结构化学校时间入口")
        self.assertIn("S.clock = {", js, "学校粗测必须按状态（ok/warn/unknown）整份替换")
        self.assertIn("clock-pop", js, "必须有时钟详情浮层 #clock-pop")
        self.assertIn("粗测", js, "必须明确这是粗测、仅作诊断")
        self.assertNotIn("#clock-skew", js, "顶栏不再放长状态徽章")
        self.assertNotIn("本机时钟与服务器相差", js,
                         "不得再从人读文本解析偏差：失败文本不能变成确定结论")
        self.assertNotIn("S.clock.checked =", js, "旧的 checked 布尔已被状态机取代")

    def test_online_offline_banners(self):
        js = read("ui/app.js")
        self.assertIn('addEventListener("online"', js, "必须监听 online 恢复")
        self.assertIn('addEventListener("offline"', js, "必须监听 offline 断网")
        self.assertIn("网络断开", js, "断网横幅必须有文字说明")

    def test_sleep_gap_uses_real_interval(self):
        js = read("ui/app.js")
        self.assertIn("SLEEP_GAP_MS", js, "睡眠检测必须有明确阈值常量")
        self.assertIn("lastBeat", js, "必须基于真实心跳间隔（lastBeat 差值）判定睡眠")
        self.assertNotIn("simulateSleep", js, "不得提供模拟睡眠成功的钩子")

    def test_responsive_breakpoints(self):
        css = read("ui/styles.css")
        for width in ("1060px", "900px", "860px"):
            self.assertIn("max-width: %s" % width, css, "缺少 %s 宽度断点" % width)
        self.assertIn("max-height: 720px", css, "缺少 720px 高度断点（矮窗口档）")
        self.assertIn(".c-place, .colhead .h-place { display: none; }", css,
                      "860 断点必须收起地点列")
        self.assertIn(".name-short { display: inline; }", css,
                      "860 断点必须切换为短品牌名")

    def test_error_result_has_action(self):
        js = read("ui/app.js")
        self.assertIn("result-action", js, "失败结论必须带行动按钮（刷新列表/再试一次）")

    def test_check_event_carries_hint(self):
        # check 事件载荷整理已下沉 application.login_service
        svc = read("application/login_service.py")
        self.assertIn('"hint": check_hint', svc, "check 事件必须带可区分的 hint 分类字段")
        py = read("app.py")
        self.assertIn("def _check_hint", py, "缺少 hint 分类函数")


class LoginEstimateBehaviorTests(unittest.TestCase):
    """R4：登录剩余同一来源、绝对时刻计时、刷新不续期（node vm 行为，不调用学校）。"""

    def test_relogin_swaps_anchor_without_reload(self):
        """启动旧估算 → 窗口内重新登录 → check 事件带新锚点：不重载窗口也同步换新。"""
        res = run_js(r"""
const H = 3600e3;
const now = Date.now();
/* bootstrap：旧凭证还剩 1 小时，随后第一次校验回来（ok=true，与真实启动时序一致） */
setLogin(1, null, true, { session_present: true, saved_at: "s-old", estimated_expires_at: (now + 1 * H) / 1000 });
window.onBackend.check({ ok: true, result: "valid", hours_left: 1,
  session_present: true, estimated_expires_at: (now + 1 * H) / 1000, saved_at: "s-old" });
const before = S.login.expireAt;
/* 重新登录成功：旧锚点立即作废（未知，等 check 带新锚点） */
window.onBackend.done({ kind: "login", ok: true });
const cleared = S.login.expireAt;
/* check 回来：新锚点 = 新 saved_at + 17.5h */
window.onBackend.check({ ok: true, result: "valid", hours_left: 17.5,
  session_present: true, estimated_expires_at: (now + 17.5 * H) / 1000, saved_at: "s-new" });
out.push({ before, cleared, after: S.login.expireAt,
  pillText: document.querySelector("#pill-text").textContent,
  pillSub: document.querySelector("#pill-sub").textContent });
""")
        self.assertEqual(res[0]["cleared"], None, "重登成功后旧锚点必须作废")
        self.assertGreater(res[0]["after"], res[0]["before"] + 8 * 3600e3,
                           "check 事件必须换上重登后的新锚点")
        self.assertEqual(res[0]["pillText"], "已登录")

    def test_pill_shows_last_check_not_remaining_time(self):
        """胶囊写上次向学校校验的时刻，不写剩余时间；时钟推进两小时，这句话不跟着走字。

        取代旧的「锚点随时钟倒数」：学校不公布有效期，工具不估算（架构方案 4.5），
        锚点仍按绝对时刻保存（loginHoursLeft 仍减两小时），只是不再显示给用户。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
setLogin(5, null, true, { estimated_expires_at: t0 / 1000 + 5 * 3600 });
window.onBackend.check({ ok: true, result: "valid", hours_left: 5,
  session_present: true, estimated_expires_at: t0 / 1000 + 5 * 3600,
  last_check_at: "2026-11-03 14:20:03", last_check_state: "valid" });
const h1 = loginHoursLeft();
const sub1 = document.querySelector("#pill-sub").textContent;
setBusinessNow(t0 + 2 * H);
paintLogin();
const h2 = loginHoursLeft();
const sub2 = document.querySelector("#pill-sub").textContent;
out.push({ h1, h2, sub1, sub2, note: document.querySelector("#status-detail").textContent });
""")
        r = res[0]
        self.assertAlmostEqual(r["h1"], 5.0, delta=0.01)
        self.assertAlmostEqual(r["h2"], 3.0, delta=0.01, msg="锚点仍按绝对时刻保存，不随刷新续期")
        self.assertEqual(r["sub1"], "14:20 校验", "已登录时胶囊旁只写上次校验时刻")
        self.assertEqual(r["sub2"], r["sub1"], "时钟推进不改这句话：它是事实，不是倒计时")
        for banned in ("约剩", "小时", "过期"):
            self.assertNotIn(banned, r["sub1"], "胶囊不得显示剩余时间（%s）" % banned)
        self.assertIn("预计", r["note"], "有估算时说明里要给「预计…以学校为准」")
        self.assertIn("以学校为准", r["note"], "估算必须写明以学校校验为准")
        self.assertNotIn("学校不公布", r["note"], "E2 起改为按锚点给预计提示")

    def test_login_estimate_five_writings(self):
        """E2：预计有效的五种写法各就各位，且只作提示（不参与失效判定）。"""
        res = run_js(r"""
const H = 3600;
const t0 = 1700000000000;
setBusinessNow(t0);
function cardOf(anchor, result) {
  setLogin(null, result || "valid", true, anchor || {});
  S.login.result = result || "valid";
  renderLoginCard();
  return document.querySelector("#login-pop-rows").textContent;
}
out.push({
  ok: cardOf({ estimated_expires_at: t0 / 1000 + H, estimate_reason: "ok" }),
  tomorrow: cardOf({ estimated_expires_at: t0 / 1000 + 20 * H, estimate_reason: "ok" }),
  passed: cardOf({ estimated_expires_at: t0 / 1000 - 60, estimate_reason: "ok" }),
  noAnchor: cardOf({ estimate_reason: "no_anchor" }),
  noClock: cardOf({ estimate_reason: "clock_unavailable" }),
});
""")
        r = res[0]
        self.assertIn("预计有效", r["ok"], "详情卡行名改为「预计有效」")
        self.assertRegex(r["ok"], r"约到 \d{2}:\d{2}（按登录后 10 小时估，以学校为准）")
        self.assertIn("约到明天", r["tomorrow"], "跨天的估算写「明天」")
        self.assertIn("已过预计时间，学校仍确认有效", r["passed"],
                      "估算过点但学校仍有效：如实说明，不改登录结论")
        self.assertIn("不知道（这次登录不是在本工具里完成的）", r["noAnchor"])
        self.assertIn("北京时间校准后再估", r["noClock"])

    def test_repeated_check_does_not_renew_anchor(self):
        """刷新同一凭证：锚点是绝对时刻，不会按「本次刷新时刻 + hours」续期。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
const anchor = t0 / 1000 + 4 * 3600;
setLogin(4, null, true, { estimated_expires_at: anchor });
window.onBackend.check({ ok: true, result: "valid", hours_left: 4,
  session_present: true, estimated_expires_at: anchor });
const a1 = S.login.expireAt;
/* 两小时后再次 check：后端 hours 按绝对时刻递减（4→2），锚点必须仍是同一绝对时刻 */
setBusinessNow(t0 + 2 * H);
window.onBackend.check({ ok: true, result: "valid", hours_left: 2,
  session_present: true, estimated_expires_at: anchor });
out.push({ a1, a2: S.login.expireAt });
""")
        self.assertEqual(res[0]["a1"], res[0]["a2"], "同一凭证的锚点不得随刷新漂移")

    def test_valid_at_zero_estimate_stays_valid(self):
        """估算到点但学校 valid：仍「登录有效」，不显示成过期（放行只看学校结论）。"""
        res = run_js(r"""
window.onBackend.check({ ok: true, result: "valid", hours_left: 0,
  session_present: true, estimated_expires_at: Date.now() / 1000 - 60 });
out.push({ state: document.querySelector("#pill").dataset.state,
  text: document.querySelector("#pill-text").textContent,
  sub: document.querySelector("#pill-sub").textContent });
""")
        self.assertEqual(res[0]["state"], "ok")
        self.assertEqual(res[0]["text"], "已登录")
        # 旧断言「胶囊写以学校校验为准」随剩余时间一起去掉：胶囊不再出现任何到期估算
        for banned in ("约剩", "过期", "小时"):
            self.assertNotIn(banned, res[0]["sub"], "估算到点也不得在胶囊上露出到期说法")

    def test_no_anchor_shows_unknown_not_fabricated(self):
        """没有锚点：不编 17 小时；unknown 结论也不显示成过期。"""
        res = run_js(r"""
setLogin(null, true, true, { session_present: true, saved_at: null, estimated_expires_at: null });
S.login.result = "unknown"; S.login.ok = false;
paintLogin();
out.push({ text: document.querySelector("#pill-text").textContent,
  expiry: expiryText() });
""")
        self.assertEqual(res[0]["text"], "登录待确认")
        self.assertNotIn("17", res[0]["expiry"], "没有锚点不得编造 17 小时")
        self.assertIn("未知", res[0]["expiry"])


class LoginSequenceBehaviorTests(unittest.TestCase):
    """P1：取消/失败/超时的重新登录必须整份回滚，成功换锚点，且同一轮统一收口。

    用状态机序列断言（登录字段 + 胶囊 + 剩余时间 + 按钮），而不是只比一句文案：
    用户看到的一致性是「所有 surface 在同一结论下同步」，单点文案断言抓不到
    「胶囊已登录、剩余时间消失」这类混合态。
    """

    def test_cancelled_relogin_restores_full_prior_login_state(self):
        """已登录点重登 → 取消：胶囊、剩余时间、锚点、按钮全部回到登录前，只多一条失败说明。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
const anchor = t0 / 1000 + 4 * 3600;
setLogin(4, null, true, { session_present: true, estimated_expires_at: anchor, saved_at: "s-old" });
window.onBackend.check({ ok: true, result: "valid", hours_left: 4, session_present: true,
  estimated_expires_at: anchor, saved_at: "s-old" });
const before = {
  hours: S.login.hours, ok: S.login.ok, present: S.login.present, expireAt: S.login.expireAt,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state,
  sub: document.querySelector("#pill-sub").textContent,
  btn: document.querySelector("#btn-login").textContent,
};
let pending = null;
let loginCalls = 0;
window.pywebview = { api: {
  login: () => { loginCalls += 1; return new Promise((r) => { pending = r; }); },
  check: () => Promise.resolve({ ok: true }),
} };
doLogin();
const snapDuring = !!S.login.preLoginSnapshot;
pending({ ok: true });
await Promise.resolve(); await Promise.resolve();
window.onBackend.done({ kind: "login", ok: false, reason: "窗口被关掉" });
out.push({
  snapDuring, snapCleared: S.login.preLoginSnapshot === null, loginCalls,
  loginPending: S.login.loginPending,
  hours: S.login.hours, present: S.login.present, expireAt: S.login.expireAt,
  text: document.querySelector("#pill-text").textContent,
  state: document.querySelector("#pill").dataset.state,
  sub: document.querySelector("#pill-sub").textContent,
  btn: document.querySelector("#btn-login").textContent,
  before,
});
""")
        r = res[0]
        self.assertTrue(r["snapDuring"], "点登录时必须先存下完整登录结论快照")
        self.assertTrue(r["snapCleared"], "取消落地后快照必须清掉，不能留着下次误回滚")
        self.assertEqual(r["loginCalls"], 1)
        self.assertFalse(r["loginPending"])
        self.assertEqual(r["expireAt"], r["before"]["expireAt"], "取消不得动旧锚点")
        self.assertEqual(r["present"], r["before"]["present"])
        self.assertEqual(r["state"], "ok", "仍有效的旧会话不得画成失效")
        self.assertEqual(r["text"], "已登录")
        self.assertEqual(r["sub"], r["before"]["sub"], "剩余时间必须原样保留，不能显示成失效/未知")
        self.assertEqual(r["btn"], r["before"]["btn"], "按钮文字不得因取消而变化")

    def test_login_pending_never_paints_run_board(self):
        """点登录期间大屏必须说「登录中」，不能借 S.busy 说成「正在准备报名」。"""
        res = run_js(r"""
const t0 = 1700000000000;
setBusinessNow(t0);
const anchor = t0 / 1000 + 4 * 3600;
setLogin(4, null, true, { session_present: true, estimated_expires_at: anchor });
window.onBackend.check({ ok: true, result: "valid", hours_left: 4, session_present: true,
  estimated_expires_at: anchor });
const boardBefore = document.querySelector("#selected").textContent;
let pending = null;
window.pywebview = { api: {
  login: () => new Promise((r) => { pending = r; }),
  check: () => Promise.resolve({ ok: true }),
} };
doLogin();
const during = {
  tag: document.querySelector("#board-tag-text").textContent,
  title: document.querySelector("#selected").textContent,
  text: document.querySelector("#board-text").textContent,
  busy: S.busy,
  loginPending: S.login.loginPending,
};
pending({ ok: true });
await Promise.resolve(); await Promise.resolve();
window.onBackend.done({ kind: "login", ok: false, reason: "窗口被关掉" });
out.push({
  boardBefore, during,
  after: {
    tag: document.querySelector("#board-tag-text").textContent,
    title: document.querySelector("#selected").textContent,
  },
  loginPending: S.login.loginPending,
  busy: S.busy,
});
""")
        r = res[0]
        self.assertTrue(r["during"]["loginPending"], "点登录后必须处于登录尝试态")
        self.assertTrue(r["during"]["busy"], "登录尝试期间 S.busy 为真（等待 worker）")
        self.assertEqual(r["during"]["tag"], "登录中", "登录尝试不得露出报名计划的「准备中」状态")
        self.assertIn("登录窗口", r["during"]["title"])
        self.assertNotIn("正在准备报名", r["during"]["title"],
                         "点登录不能把大屏说成正在准备报名")
        self.assertFalse(r["loginPending"])
        self.assertFalse(r["busy"])
        self.assertNotEqual(r["after"]["tag"], "登录中", "取消落地后大屏要回到非登录态")
        self.assertEqual(r["after"]["title"], r["boardBefore"], "取消后大屏必须回到登录前的内容")

    def test_logged_in_without_last_check_says_never_checked(self):
        """有会话但还没向学校校验过：胶囊不编时刻，状态卡明说「还没有向学校校验过」。

        取代旧的「锚点对不上时胶囊写未知、建议重新登录」：现在胶囊不报剩余时间，
        没有估算可恢复，所以也不再拿「重新登录」当补救；缺的是校验时刻，就照实说。"""
        res = run_js(r"""
setBusinessNow(1700000000000);
setLogin(null, true, true);
renderLoginCard();
out.push({
  text: document.querySelector("#pill-text").textContent,
  sub: document.querySelector("#pill-sub").textContent,
  note: document.querySelector("#status-detail").textContent,
  card: document.querySelector("#login-pop-sub").textContent,
  state: document.querySelector("#pill").dataset.state,
  hours: loginHoursLeft(),
});
""")
        r = res[0]
        self.assertIsNone(r["hours"], "没有匹配锚点时不得报出小时数")
        self.assertEqual(r["text"], "已登录")
        self.assertEqual(r["state"], "ok")
        self.assertEqual(r["sub"], "", "没校验过就不编时刻")
        self.assertNotIn("小时", r["sub"], "不得编造剩余小时数")
        self.assertIn("还没有向学校校验过", r["card"], "状态卡要明说还没校验过，不能空着")
        self.assertIn("登录有效", r["note"], "说明文字要告诉用户登录本身是有效的")
        self.assertEqual(r["note"], "学校确认登录有效",
                         "没有估算锚点时只报学校确认事实，不编有效期")

    def test_failed_relogin_keeps_countdown_instead_of_invalid(self):
        """超时/登录失败：保留旧有效期与「已登录」，只显示这次失败的说明。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
const anchor = t0 / 1000 + 6 * 3600;
setLogin(6, null, true, { session_present: true, estimated_expires_at: anchor });
window.onBackend.check({ ok: true, result: "valid", hours_left: 6, session_present: true,
  estimated_expires_at: anchor, last_check_at: "2026-11-03 09:00:12", last_check_state: "valid" });
window.pywebview = { api: { login: () => Promise.resolve({ ok: true }), check: () => Promise.resolve({ ok: true }) } };
doLogin();
window.onBackend.done({ kind: "login", ok: false, reason: "仍未检测到登录成功" });
out.push({
  expireAt: S.login.expireAt,
  state: document.querySelector("#pill").dataset.state,
  text: document.querySelector("#pill-text").textContent,
  sub: document.querySelector("#pill-sub").textContent,
  hours: loginHoursLeft(),
});
""")
        r = res[0]
        self.assertEqual(r["expireAt"], 1700000000000 + 6 * 3600e3)
        self.assertEqual(r["state"], "ok")
        self.assertEqual(r["text"], "已登录")
        # 旧断言「胶囊仍写 6 小时」改为：失败重登保留原来的上次校验时刻（胶囊不再报剩余时间）
        self.assertEqual(r["sub"], "09:00 校验", "失败重登不能吞掉原来的校验时刻")
        self.assertAlmostEqual(r["hours"], 6.0, delta=0.01)

    def test_cancelled_relogin_without_any_session_stays_logged_out(self):
        """本来就没有会话：取消重登后仍是未登录，不能因为点过登录就显示已登录。"""
        res = run_js(r"""
window.pywebview = { api: { login: () => Promise.resolve({ ok: true }), check: () => Promise.resolve({ ok: true }) } };
setLogin(null, false, false);
doLogin();
window.onBackend.done({ kind: "login", ok: false, reason: "打不开登录页" });
out.push({
  present: S.login.present, expireAt: S.login.expireAt,
  state: document.querySelector("#pill").dataset.state,
  text: document.querySelector("#pill-text").textContent,
});
""")
        r = res[0]
        self.assertFalse(r["present"])
        self.assertIsNone(r["expireAt"])
        self.assertEqual(r["state"], "none")
        self.assertEqual(r["text"], "未登录")

    def test_successful_relogin_clears_old_anchor_then_adopts_new(self):
        """成功重登：尝试前快照作废，旧锚点立刻清零，随后 check 带回新锚点。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
const oldAnchor = t0 / 1000 + 1 * 3600;
setLogin(1, null, true, { session_present: true, estimated_expires_at: oldAnchor, saved_at: "s-old" });
window.onBackend.check({ ok: true, result: "valid", hours_left: 1, session_present: true,
  estimated_expires_at: oldAnchor, saved_at: "s-old" });
window.pywebview = { api: { login: () => Promise.resolve({ ok: true }), check: () => Promise.resolve({ ok: true }) } };
doLogin();
window.onBackend.done({ kind: "login", ok: true });
const cleared = { expireAt: S.login.expireAt, snap: S.login.preLoginSnapshot };
const newAnchor = t0 / 1000 + 17.5 * 3600;
window.onBackend.check({ ok: true, result: "valid", hours_left: 17.5, session_present: true,
  estimated_expires_at: newAnchor, saved_at: "s-new",
  last_check_at: "2026-11-03 10:05:40", last_check_state: "valid" });
out.push({ cleared, after: S.login.expireAt, sub: document.querySelector("#pill-sub").textContent,
  state: document.querySelector("#pill").dataset.state });
""")
        r = res[0]
        self.assertIsNone(r["cleared"]["expireAt"], "成功后旧锚点必须立即作废")
        self.assertIsNone(r["cleared"]["snap"], "成功后尝试前快照必须作废")
        self.assertAlmostEqual(r["after"], 1700000000000 + 17.5 * 3600e3, delta=1000)
        self.assertEqual(r["state"], "ok")
        # 旧断言「胶囊报约剩」改为：新一轮校验回来后胶囊换成这次的校验时刻，仍不报剩余时间
        self.assertEqual(r["sub"], "10:05 校验", "重登成功后的校验时刻要换上")
        self.assertNotIn("约剩", r["sub"], "胶囊不得显示剩余时间")

    def test_old_round_check_cannot_override_restored_state(self):
        """取消落地后，旧轮 check 迟到：不得改写回滚后的登录结论。"""
        res = run_js(r"""
const H = 3600e3;
const t0 = 1700000000000;
setBusinessNow(t0);
const anchor = t0 / 1000 + 4 * 3600;
setLogin(4, null, true, { session_present: true, estimated_expires_at: anchor });
window.onBackend.check({ ok: true, result: "valid", hours_left: 4, session_present: true,
  estimated_expires_at: anchor });
window.pywebview = { api: { login: () => Promise.resolve({ ok: true }), check: () => Promise.resolve({ ok: true }) } };
doLogin();
window.onBackend.done({ kind: "login", ok: false, reason: "窗口被关掉" });
const kept = { expireAt: S.login.expireAt, state: document.querySelector("#pill").dataset.state };
/* 回滚后新一轮刷新已经开始（S.round.check 是新 id）；此时上一轮的 check 才迟到 */
S.round.check = "round-new";
S.round.checkTimer = 0;
window.onBackend.check({ request_id: "round-from-before", ok: false, result: "none", hours_left: null });
out.push({ kept, after: { expireAt: S.login.expireAt, state: document.querySelector("#pill").dataset.state } });
""")
        r = res[0]
        self.assertEqual(r["after"], r["kept"], "旧轮迟到结论不得覆盖回滚后的状态")

    def test_sync_login_dependent_view_repaints_every_surface(self):
        """统一收口函数必须同时重画胶囊/时钟/空态/大屏/路线/列表，不只改胶囊。"""
        res = run_js(r"""
window.onBackend.check({ ok: true, result: "valid", hours_left: 3, session_present: true,
  estimated_expires_at: Date.now() / 1000 + 3 * 3600 });
const seen = [];
for (const name of ["paintList", "paintRoute", "paintSelected", "paintClockStatus", "refreshLoginEmptyState"]) {
  const real = window[name] || eval(name);
  const spy = function () { seen.push(name); return real.apply(null, arguments); };
  if (name in window) window[name] = spy; else eval(name + " = spy");
}
syncLoginDependentView();
out.push({ seen, state: document.querySelector("#pill").dataset.state });
""")
        r = res[0]
        self.assertEqual(r["state"], "ok")
        for name in ("paintList", "paintRoute", "paintSelected", "paintClockStatus", "refreshLoginEmptyState"):
            self.assertIn(name, r["seen"], "统一收口必须重画 %s" % name)


class OtherLoginWordingTests(unittest.TestCase):
    """登录详情卡「别处登录」一行：别处登录不一定让本机下线，只说「可能」，以实际登录状态为准（用户 2026-11-09 定）。"""

    def test_other_login_row_is_hedged(self):
        js = read("ui/views/status-cards.js")
        self.assertIn("可能让这里失效，比如手机上的学校页面；以实际登录状态为准", js)
        self.assertNotIn("会让这里失效", js, "不能断言别处登录一定让本机失效")


class ReloginRefreshTests(unittest.TestCase):
    """N1：重新登录成功后自动加载活动列表（与浏览器登录成功同一条路）。"""

    def test_success_fires_one_refresh_and_replays_do_not(self):
        """空闲时收到 success → 走一次 check + list；同一 flow 的重放不再刷；
        计划运行中不刷新（后端照常继续计划）。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: {
  check: () => { calls.push("check"); return Promise.resolve({ ok: true }); },
  list_activities: () => { calls.push("list"); return Promise.resolve({ ok: true, items: [] }); },
} };
receiveReloginState({ state: "success", flow_id: "f1" });
const once = calls.slice();
receiveReloginState({ state: "success", flow_id: "f1" });
const replay = calls.slice();
S.busy = true;
receiveReloginState({ state: "success", flow_id: "f2" });
const busy = calls.slice();
out.push({ once, replay, busy });
""")
        row = res[0]
        self.assertEqual(row["once"].count("list"), 1,
                         "登录成功要立刻拉一次活动列表，用户不必再手点「刷新」")
        self.assertGreaterEqual(row["once"].count("check"), 1,
                                "与浏览器登录成功同一条路：先查一次登录状态")
        self.assertEqual(row["replay"], row["once"],
                         "中继会重放快照：同一 flow 的 success 只能刷新一次")
        self.assertEqual(row["busy"], row["replay"],
                         "计划运行中不刷新：界面只说明「计划照常继续」")

    def test_open_dialog_success_also_loads_the_list(self):
        """对话框开着时登录成功同样立刻加载：走完「登录成功」提示再刷新。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: {
  check: () => { calls.push("check"); return Promise.resolve({ ok: true }); },
  list_activities: () => { calls.push("list"); return Promise.resolve({ ok: true, items: [] }); },
} };
S.relogin = { open: true, step: "wait", flowId: "f1", challengeId: "" };
receiveReloginState({ state: "success", flow_id: "f1" });
out.push({ calls: calls.slice(), step: S.relogin.step, flowId: S.relogin.flowId,
  msg: document.querySelector("#rl-msg-text").textContent });
""")
        row = res[0]
        self.assertEqual(row["calls"].count("list"), 1, "对话框确认成功后也要加载列表")
        self.assertEqual(row["step"], "msg", "仍然停在「重新登录成功」这一屏")
        self.assertEqual(row["flowId"], "", "本场 flow 收口后清空")
        self.assertEqual(row["msg"], "重新登录成功。", "空闲时的成功提示保持原话")

    def test_relogin_success_without_flow_id_refreshes_only_once(self):
        """无 flow_id 的 success 快照视为同一事件只放行一次：中继重放不再打回加载态。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: {
  check: () => { calls.push("check"); return Promise.resolve({ ok: true }); },
  list_activities: () => { calls.push("list"); return Promise.resolve({ ok: true, items: [] }); },
} };
receiveReloginState({ state: "success", flow_id: "" });
const first = calls.slice();
receiveReloginState({ state: "success", flow_id: "" });
const replay = calls.slice();
out.push({ first, replay });
""")
        row = res[0]
        self.assertEqual(row["first"].count("list"), 1,
                         "无 flow_id 的成功快照同样要立刻拉一次活动列表")
        self.assertGreaterEqual(row["first"].count("check"), 1,
                                "与浏览器登录成功同一条路：先查一次登录状态")
        self.assertEqual(row["replay"], row["first"],
                         "空 flow_id 的重放视为同一事件：不得再次 doCheck + refresh 打回加载态")


if __name__ == "__main__":
    unittest.main()
