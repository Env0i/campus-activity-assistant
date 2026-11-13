# -*- coding: utf-8 -*-
"""界面契约：设置抽屉、引导、协助入口与书签复制。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read, help_dialog, HELP_TEST_VERSION, HELP_TEST_URL, load_backend_help, run_js, settings_drawer  # noqa: E402


class TourAndLifecycleContractTests(unittest.TestCase):
    """可重播引导（决策 009 修订：五步，登录成功且列表加载后才自动开始）+ 生命周期提示的静态契约。"""

    def test_index_has_six_tour_targets(self):
        """六个稳定高亮锚点：登录/列表/筛选/选择/开始/运行。"""
        html = read("ui/index.html")
        for key in ("login", "list", "filters", "select", "start", "run"):
            self.assertIn('data-tour-target="%s"' % key, html,
                          "缺少第 %s 步的高亮锚点 data-tour-target" % key)

    def test_index_has_tour_overlay_and_replay_entry(self):
        """引导遮罩结构 + 两处重播入口（「更多」与说明底部，共用一条路径）。"""
        html = read("ui/index.html")
        for needle in ('id="tour"', 'id="tour-card"', 'id="tour-spot"',
                       'id="tour-skip"', 'id="tour-prev"', 'id="tour-next"',
                       'id="tour-step"', 'id="tour-dots"'):
            self.assertIn(needle, html, "引导结构缺 %s" % needle)
        self.assertRegex(html, r'<h3 id="tour-title">[^<\s][^<]*</h3>',
                         "#tour-card 是 role=dialog 且 aria-labelledby=tour-title："
                         "标题静态不能为空，否则引导没开始前读屏只念「对话框」")
        self.assertIn('id="btn-help-tour"', html, "「更多」里必须有「重看引导」入口")
        self.assertIn('id="btn-help-tour"', html,
                      "说明底部必须有重播快捷入口（与更多共用同一条处理路径）")
        self.assertIn("重看引导", html, "重播入口要有可读文字，不能只靠图标")
        self.assertIn('id="help"', html, "必须有独立 dialog #help")
        self.assertIn("跳过引导", html, "必须有跳过按钮")

    def test_app_js_tour_definition_and_version(self):
        """TOUR_VERSION=3（新工作台五步）、五步定义与顺序、完成/跳过存储键与立即保存。

        取代旧的「版本 2、六步标题」：决策 009 修订把引导改成时刻表 → 勾选 → 核对 → 开始以后 → 顶部状态，
        内容实质变化，版本 +1，看过旧版的用户会再自动弹一次。"""
        js = read("ui/app.js")
        self.assertIn("const TOUR_VERSION = 3", js, "五步内容是实质变化，内容版本必须升到 3")
        steps = js[js.index("TOUR_STEPS = ["):js.index("const S = {")]
        self.assertEqual(steps.count("target: "), 5, "TOUR_STEPS 必须正好五步")
        for key in ("tour_version", "tour_completed_at", "tour_skipped_at"):
            self.assertIn(key, js, "引导状态键 %s 必须写入偏好" % key)
        self.assertIn("savePrefsNow", js, "完成/跳过必须立即落盘，不等防抖")
        titles = ("这是活动时刻表", "勾选想报的活动", "核对计划，再点开始", "开始以后看这里", "出问题先看顶部")
        at = [steps.index('title: "%s"' % title) for title in titles]
        self.assertEqual(at, sorted(at), "五步顺序固定：时刻表 → 勾选 → 核对 → 开始以后 → 顶部状态")
        targets = [steps.index('target: "%s"' % key) for key in ("list", "row", "select", "run", "login")]
        self.assertEqual(targets, sorted(targets), "五步高亮目标与顺序一一对应")
        # 只有勾选那一步可以真的点一行
        self.assertEqual(steps.count("interactive: true"), 1, "只有勾选那一步可操作")
        row = steps[steps.index('target: "row"'):steps.index('target: "select"')]
        self.assertIn("interactive: true", row, "可操作的必须是勾选那一步")

    def test_tour_steps_do_not_promise_selection_starts(self):
        """选择不等于开始：引导必须写清「勾选只是加入计划，不会开始报名」。

        旧断言逐句锁六步文案（「选择活动不会自动开始报名」「工具停止尝试」「整块大屏的结论……」），
        五步改写后由同义新句取代：勾选不开始、核对后再点开始、开始以后看进度、待核对去活动页确认。"""
        js = read("ui/app.js")
        steps = js[js.index("TOUR_STEPS = ["):js.index("const S = {")]
        self.assertNotIn("选中后马上执行", steps,
                         "引导不得暗示选中即执行")
        self.assertIn("勾选只是加入计划，不会开始报名", steps, "勾选那一步要写清选择不等于开始")
        self.assertIn("核对计划，再点开始", steps, "第 3 步要写清真正的开始动作在核对之后")
        self.assertIn("不要关闭工具或让电脑睡眠", steps, "开始以后那一步要讲清运行期间的前提")
        # 「待核对」→“待核对”：原型 tourSteps（Main:1260）用弯引号，c3-dialogs-gap TR07 照原型逐字
        self.assertIn("看到“待核对”时，到学校活动页确认", steps,
                      "开始以后那一步要讲清待核对的下一步（工具不自动重发）")
        # 原型 :631 原话是「停止不会取消已成功的报名」，旧断言多了「计划」二字
        self.assertIn("停止不会取消已成功的报名", read("ui/index.html"),
                      "停止确认要说明不撤销学校报名")

    def test_tour_steps_use_prototype_curly_quotes(self):
        """TR03/TR07/TR08：五步文案与原型 tourSteps（Main:1255-1263）同源，弯引号逐字。

        旧文案写直角引号「」，原型用弯引号“”；引号是文案的一部分，照原型逐字，
        直角写法不得回潮。"""
        js = read("ui/app.js")
        steps = js[js.index("TOUR_STEPS = ["):js.index("const S = {")]
        for phrase in ("“预报名”等开放后自动提交", "“立即报名”点开始后马上提交",
                       "看到“待核对”时，到学校活动页确认", "想再看一遍引导，点“帮助”"):
            self.assertIn(phrase, steps, "引导文案缺原型弯引号短语：%s" % phrase)
        for old in ("「预报名」", "「立即报名」", "「待核对」", "「帮助」"):
            self.assertNotIn(old, steps, "引导文案不得再出现直角引号：%s" % old)

    def test_tour_overlay_matches_prototype_frame(self):
        """TR01/TR03：卡宽 352px、遮罩色 rgba(17,29,38,.52)、卡头深色、spot 镂空挖洞；无 1/6 残留。

        原型 .t-pane 遮罩色与 .t-card 22rem（Main:507-510）；挖洞由 .tour-spot 的外扩
        box-shadow 呈现（原型四板挖洞的等价实现），不再有全遮 .tour-mask。
        「第 1/6 步」是六步时代的静态残留，步数由 views/tour.js 在 paintTour 里现填。"""
        css = read("ui/styles.css")
        tour_css = css[css.index(".tour {"):css.index("@keyframes pulse")]
        self.assertIn("width: 352px", tour_css, "引导卡宽必须照原型 22rem=352px")
        self.assertNotIn("340px", tour_css, "旧卡宽 340px 必须删掉，不留死样式")
        self.assertIn("rgba(17,29,38,.52)", tour_css, "遮罩色必须照原型 .t-pane（Main:507）")
        self.assertNotIn("rgba(17,24,20,.55)", tour_css, "旧遮罩色必须删掉，不留死样式")
        self.assertNotIn(".tour-mask", tour_css, "全遮板已由 spot 外扩阴影挖洞取代（TR01）")
        self.assertIn("var(--board)", tour_css, "卡头必须深色（照原型 .t-head，Main:509）")
        html = read("ui/index.html")
        self.assertNotIn("第 1/6 步", html, "六步时代的静态步数残留必须删掉")
        self.assertIn('id="tour-step"></span>', html, "步数 span 必须为空，由 views/tour.js 填写")

    def test_tour_row_pick_swaps_card_copy(self):
        """TR05（原型 Main:1302）：第 2 步勾选目标行后换卡文案，取消勾选换回；文案逐字。"""
        js = read("ui/views/tour.js")
        self.assertIn("加入计划了", js, "勾选后的卡片标题必须照原型")
        self.assertIn("右边的清单多了一场，报名还没有开始。想取消，再点一次这一行。", js,
                      "勾选后的卡片正文必须照原型")
        paint = js[js.index("function paintTour()")
                   :js.index("/* ---------------------------------------------------------------- 事件绑定 */")]
        self.assertIn("step.interactive", paint, "换卡只许发生在第 2 步（interactive）")

    def test_tour_never_triggers_backend_actions(self):
        """引导只做说明：开始/推进/跳过引导的代码不得调用任何桥接动作。"""
        js = read("ui/app.js")
        start = js.index("function tourShouldAutoStart()")
        end = js.index("/* ---------------------------------------------------------------- 事件绑定 */")
        body = js[start:end]
        for banned in ("api(\"login\"", "api(\"start_plan\"", "api(\"check\"",
                       "api(\"list_activities\"", "toggleSelection(", "startPlan()"):
            self.assertNotIn(banned, body,
                             "引导逻辑不得代替用户执行动作：%s" % banned)

    def test_tour_skip_pause_and_narrow_fallback(self):
        """跳过后同版不再自动弹；窄窗（≤980）与目标缺失退回底部说明条；运行中暂停。"""
        js = read("ui/app.js")
        self.assertIn("tourShouldAutoStart", js, "自动开始必须有判定函数")
        self.assertIn("seen >= TOUR_VERSION", js,
                      "自动开始只按已看过的内容版本判定（旧时间戳不得拦截新版）")
        self.assertIn("window.innerWidth > 980", js, "窄窗（≤980）必须退回底部说明条")
        self.assertIn('classList.toggle("is-bottom"', js, "回退态必须挂 is-bottom 类")
        self.assertIn('classList.toggle("no-target"', js, "没有目标时才挂 no-target 类")
        css = read("ui/styles.css")
        self.assertIn(".tour.no-target .tour-spot", css,
                      "隐藏高亮框只挂在「没有目标」上（R1）")
        self.assertNotIn(".tour.is-bottom .tour-spot", css,
                         "is-bottom 现在只表示卡片位置，不能再顺手藏高亮框")
        self.assertIn("tourPauseNow", js, "计划运行中必须暂停引导")
        self.assertIn("tourResumeNow", js, "计划结束后必须可恢复引导")
        # Esc 等同跳过
        esc_at = js.index('if (event.key === "Escape")')
        esc_body = js[esc_at:esc_at + 400]
        self.assertIn("tourSkip()", esc_body, "Esc 在引导打开时必须先走跳过")

    def test_chrome_login_window_text_only(self):
        """引导不讲登录窗口操作（登录成功后才自动开始），也不硬编码 Chrome；最后一步指向顶部状态。

        旧断言要求第 1 步讲「浏览器登录窗口是系统窗口」：决策 009 修订后引导在登录成功之后才开始，
        登录窗口那一步没有了，改为最后一步讲出问题先看顶部登录状态。"""
        js = read("ui/app.js")
        steps = js[js.index("TOUR_STEPS = ["):js.index("const S = {")]
        self.assertNotIn("Chrome", steps, "引导不得硬编码 Chrome")
        self.assertNotIn("登录窗口", steps, "引导在登录之后开始，不再讲登录窗口")
        last = steps[steps.index('target: "login"'):]
        self.assertIn("登录", last, "最后一步要指向顶部的登录状态")
        self.assertIn("帮助", last, "最后一步要说明去哪重看引导")

    def test_lifecycle_display_and_estimate_reminder(self):
        """生命周期提示：离线时长 abnormal 带「约」；登录估算同源且只是提醒；valid 不被估算压成失效。"""
        js = read("ui/app.js")
        self.assertIn("S.lifecycle = info.lifecycle || null", js,
                      "bootstrap 的 lifecycle 快照必须消费")
        # 旧断言「上次退出至本次启动」「以学校校验为准」「浮层剩余与胶囊同源」「估算到点单独分支」
        # 随登录剩余时间一起退场（架构方案 4.5：学校不公布有效期，工具不估算）；
        # 离线间隔留在时间浮层的「上次退出」一行，登录状态改由登录状态卡报上次校验时刻。
        self.assertIn("<dt>上次退出</dt>", js, "时间详情必须显示上一周期的离线间隔")
        self.assertIn("约 ", js, "abnormal 离线间隔必须带「约」")
        pop_body = js[js.index("function toggleClockPop("):js.index("function paintClockPopFeedback")]
        self.assertNotIn("life.login", pop_body, "时间浮层不得读冻结的生命周期登录快照")
        self.assertNotIn("S.login", pop_body, "时间浮层不再显示登录剩余（登录看登录状态卡）")
        self.assertNotIn("登录预计剩余", js, "任何地方都不得再出现登录预计剩余")
        self.assertNotIn("clock-pop-left", js, "登录剩余的走字单元格不得残留")
        paint = js[js.index("function paintLogin()"):js.index("function setBusy")]
        self.assertNotIn("loginHoursLeft", paint, "胶囊渲染不得再读剩余时间估算")
        # 估算不参与开始门禁：门禁仍只看 result === "valid"
        gate = js[js.index("function updateControls("):js.index("function paintBanners")]
        self.assertNotIn("estimated_expires_at", gate,
                         "生命周期估算不得进入开始按钮门禁")
        self.assertNotIn("lifecycle", gate, "生命周期字段不得参与门禁")

    def test_releases_latest_link_is_user_triggered(self):
        """GitHub releases/latest：只由用户点击打开，启动时不自动联网。"""
        html = read("ui/index.html")
        self.assertNotIn("<a ", help_dialog(html),
                         "发布页不得变成 WebView 内导航链接")
        js = read("ui/app.js")
        self.assertIn("const RELEASES_LATEST_URL =", js, "外链地址必须是固定常量")
        self.assertIn('api("open_latest_release")', js, "打开外链必须走后端动作（点击触发）")
        handler = js[js.index('$("#btn-help-latest").addEventListener'):
                     js.index('$("#btn-help-data").addEventListener')]
        self.assertIn("RELEASES_LATEST_URL", handler,
                      "打不开时要把固定地址摆成可选文本，让用户能自己复制")
        # 启动路径（boot/refresh）不得自动请求外链
        boot_body = js[js.index("async function boot()"):js.index("function applyPrefs")]
        self.assertNotIn("open_latest_release", boot_body, "启动时不得自动打开/请求 GitHub")


    def test_tour_does_not_gate_login_or_start(self):
        """引导未完成/进行中都不影响登录与 start_plan 门禁（门禁只看登录四态）。

        断言锁 S.tour 引导状态（而非 "tour" 子串——#btn-help-tour 的
        disabled 引用是设置功能，不是引导门禁）。
        """
        js = read("ui/app.js")
        gate = js[js.index("function updateControls("):js.index("function paintBanners")]
        self.assertNotIn("S.tour", gate,
                         "开始按钮门禁不得引用引导状态")
        # 旧断言「引导自动开始不读登录状态」被决策 009 修订取代：首次自动引导要等登录成功、
        # 列表加载、条款已同意（maybeStartTour）；版本判定本身仍不看登录，手动重看任何时候都行。
        version = js[js.index("function tourShouldAutoStart()"):js.index("function requestAutoTour")]
        self.assertNotIn("S.login", version, "内容版本判定不读登录状态")
        auto = js[js.index("function maybeStartTour()"):js.index("function tourRowTarget")]
        self.assertIn('S.login.result !== "valid"', auto, "首次自动引导要等学校确认登录有效")
        self.assertIn('S.listState !== "ready"', auto, "首次自动引导要等活动列表加载")
        self.assertIn("termsLocked()", auto, "没同意条款不自动引导")
        replay = js[js.index("function replayTourFrom("):js.index("function paintReplayButtons")]
        self.assertNotIn("S.login", replay, "手动重看引导不受登录状态限制：未登录也能看")
        # 引导也不改变登录按钮：paintLogin 的四态分支里没有引导概念
        paint = js[js.index("function paintLogin()"):js.index("function setBusy")]
        self.assertNotIn("tour", paint, "登录胶囊渲染与引导互不影响")

    def test_settings_dialog_shows_version(self):
        """「更多」显示后端版本（VERSION 唯一来源），帮助载荷带版本与外链；
        旧说明弹窗版本位 id 不得残留。"""
        js = read("ui/app.js")
        anchor = js.index('$("#help-version").textContent')
        self.assertIn("info.version", js[anchor:anchor + 160],
                      "版本必须来自 bootstrap.version（唯一来源）")
        self.assertIn('$("#help-version")', js, "版本必须填入更多弹窗唯一位置")
        html = read("ui/index.html")
        self.assertIn('id="help-version"', html, "设置弹窗必须有版本位")
        self.assertEqual(html.count('id="help-version"'), 1, "当前版本只出现一个真实节点")
        # 只锁字符串字面量：注释里提及历史候选号不算硬编码
        self.assertNotIn('"1.1.0"', js, "界面代码不得写死候选版本号字符串")
        self.assertNotIn("'1.1.0'", js, "界面代码不得写死候选版本号字符串")
        py = read("app.py")
        self.assertIn('"version": APP_VERSION', py, "bootstrap/help 用 APP_VERSION")
        self.assertIn('"latest_url": RELEASES_LATEST_URL', py,
                      "help 载荷要带最新版本入口信息")

    def test_unknown_attendance_copy_stays(self):
        """未知签到/签退必须说清「同步中/待确认」，且仍被需要/无需筛选排除。"""
        js = read("ui/app.js")
        html = read("ui/index.html")
        self.assertIn("签到信息同步中", js)
        self.assertIn("签到时间待确认", js)
        self.assertIn("无需签到", js, "明确无需必须有独立文案，不能与未知混用")
        self.assertNotIn("签到待说明", js, "旧「待说明」口径已细分，不得回退")
        for key in ("checkin", "checkout"):
            self.assertIn('id="%s"' % key, html)


class TourBehaviorTests(unittest.TestCase):
    """R5/R6：引导内容版本判定、焦点循环、背景快捷键隔离、暂停放行（node vm 行为）。"""

    def test_autostart_by_content_version_not_timestamps(self):
        """新用户自动弹；同版完成/跳过不弹；计划运行中不弹。"""
        res = run_js(r"""
S.busy = false;
S.prefs = {};
out.push({ fresh: tourShouldAutoStart() });
S.prefs = { tour_version: TOUR_VERSION, tour_completed_at: "2026-01-01T00:00:00Z" };
out.push({ sameDone: tourShouldAutoStart() });
S.prefs = { tour_version: TOUR_VERSION, tour_skipped_at: "2026-01-01T00:00:00Z" };
out.push({ sameSkipped: tourShouldAutoStart() });
S.prefs = { tour_version: 0, tour_completed_at: "2026-01-01T00:00:00Z" };
out.push({ oldVersionWithOldStamp: tourShouldAutoStart() });
S.busy = true;
out.push({ busyBlocks: !tourShouldAutoStart() });
S.busy = false;
""")
        self.assertTrue(res[0]["fresh"], "新用户必须自动弹")
        self.assertFalse(res[1]["sameDone"], "同版完成不重复弹")
        self.assertFalse(res[2]["sameSkipped"], "同版跳过不重复弹")
        self.assertTrue(res[3]["oldVersionWithOldStamp"],
                        "旧内容版本的时间戳不得挡住更新的内容版本（R5）")
        self.assertTrue(res[4]["busyBlocks"], "计划运行中不自动弹")

    def test_tab_cycles_inside_card_and_background_shortcuts_blocked(self):
        """Tab 在卡片按钮间循环；背景 Ctrl+F/`/`/Enter 不移焦点、不开始计划。"""
        res = run_js(r"""
S.busy = false;
startTour(0);
const qFocused = () => focused.indexOf("#q") >= 0;
/* startTour 已聚焦 #tour-next（buttons=[skip,prev,next] 的第 3 个）：
 * Tab 从 next 前进绕回 skip，Shift+Tab 再回到 next——首尾相接 */
__dispatchKey({ key: "Tab" });
__dispatchKey({ key: "Tab", shiftKey: true });
const tabInCard = focused.slice(-2);
/* 背景快捷键：焦点不得进搜索框 */
__dispatchKey({ key: "f", ctrlKey: true });
const ctrlF = qFocused();
__dispatchKey({ key: "/" });
const slash = qFocused();
/* 背景 Enter：必须拦截（不得开始计划） */
const ev = __dispatchKey({ key: "Enter" });
out.push({ tabInCard, ctrlF, slash, enterBlocked: ev.defaultPrevented,
  tourOpen: S.tour.open });
tourSkip();
""")
        self.assertEqual(res[0]["tabInCard"], ["#tour-skip", "#tour-next"],
                         "Tab 必须在卡片按钮间首尾循环（next → skip → next）")
        self.assertFalse(res[0]["ctrlF"], "引导可见时 Ctrl+F 不得把焦点送进背景搜索框")
        self.assertFalse(res[0]["slash"], "引导可见时 `/` 不得移动焦点")
        self.assertTrue(res[0]["enterBlocked"], "背景 Enter 必须被拦截，不得开始计划")
        self.assertTrue(res[0]["tourOpen"], "以上按键都不得顺手关掉引导")

    def test_esc_skips_once_and_restores_focus(self):
        """Esc=跳过且只落一次偏好；关闭后焦点还给引导开始前的元素。"""
        res = run_js(r"""
const saved = [];
savePrefsNow = (patch) => saved.push(patch);
const target = document.querySelector("#btn-refresh");
target.focus();
startTour(2);
const enteredTour = focused.indexOf("#tour-next") >= 0;
__dispatchKey({ key: "Escape" });
__dispatchKey({ key: "Escape" });   /* 第二次 Esc：引导已关，不得再落一次跳过记录 */
out.push({ savedCount: saved.length, savedKeys: Object.keys(saved[0] || {}),
  tourOpen: S.tour.open, restored: focused.slice(-1)[0], enteredTour });
""")
        self.assertTrue(res[0]["enteredTour"], "开始引导时焦点必须进卡片")
        self.assertEqual(res[0]["savedCount"], 1, "Esc 跳过只持久化一次")
        self.assertIn("tour_version", res[0]["savedKeys"])
        self.assertFalse(res[0]["tourOpen"])
        self.assertEqual(res[0]["restored"], "#btn-refresh", "关闭后焦点还给引导前的元素")

    def test_busy_pause_releases_constraints_and_resume(self):
        """计划运行暂停引导：键盘约束放行（背景快捷键正常工作）、不挡停止；结束后回原步骤。"""
        res = run_js(r"""
startTour(3);
setBusy(true);          /* 暂停：遮罩隐藏 */
const pausedVisible = tourVisible();
/* 暂停期间背景快捷键照常工作：Ctrl+F 正常跳搜索框（约束已解除） */
__dispatchKey({ key: "f", ctrlKey: true });
const qReachable = focused.indexOf("#q") >= 0;
const stillOpen = S.tour.open;
setBusy(false);         /* 恢复 */
out.push({ pausedVisible, qReachable,
  stillOpen, resumedVisible: tourVisible(), step: S.tour.step,
  boxHidden: document.querySelector("#tour").hidden });
tourSkip();
""")
        self.assertFalse(res[0]["pausedVisible"], "暂停期间引导不可见（不挡运行界面）")
        self.assertTrue(res[0]["qReachable"], "暂停时背景快捷键放行（停止/搜索操作不受影响）")
        self.assertTrue(res[0]["stillOpen"], "暂停只是隐藏，引导状态保留")
        self.assertTrue(res[0]["resumedVisible"], "计划结束恢复引导显示")
        self.assertEqual(res[0]["step"], 3, "恢复后回到原步骤")
        self.assertFalse(res[0]["boxHidden"])

    def test_render_repositions_open_tour(self):
        """列表重画挪动目标后：重新定位现有高亮，不重开、不假点击。"""
        res = run_js(r"""
startTour(1);
const spot = document.querySelector("#tour-spot");
spot.style.top = "0px";
render();               /* 活动重画（空列表也走 render） */
out.push({ step: S.tour.step, open: S.tour.open,
  repositioned: String(spot.style.top) !== "0px" });
tourSkip();
""")
        self.assertEqual(res[0]["step"], 1, "重定位不得改变当前步骤")
        self.assertTrue(res[0]["open"], "render 不得重开或关闭引导")
        self.assertTrue(res[0]["repositioned"], "render 后必须重新定位高亮框")

    def test_row_pick_swaps_card_copy_and_back(self):
        """TR05（原型 Main:1302）：第 2 步勾选高亮行→卡换「加入计划了」，取消→换回。

        步数、主钮、圆点不随换卡变；第 2 步之外（第 1 步）勾选不得换卡。"""
        res = run_js(r"""
const row = document.querySelector("#rows .row");
const check = document.querySelector("#rows .row .row-check");
tourRowTarget = () => row;   /* 桩没有行结构：直接指定引导高亮的行 */
startTour(1);
const snap = () => ({
  title: document.querySelector("#tour-title").textContent,
  text: document.querySelector("#tour-text").textContent,
  step: document.querySelector("#tour-step").textContent,
  next: document.querySelector("#tour-next").textContent,
  dots: document.querySelector("#tour-dots").innerHTML,
});
const base = snap();
check.checked = true;
paintTour();
const picked = snap();
check.checked = false;
paintTour();
const restored = snap();
/* 第 2 步之外不受影响：第 1 步即使复选框为勾也不换卡 */
check.checked = true;
startTour(0);
const otherStep = snap();
tourSkip();
out.push({ base, picked, restored, otherStep });
""")
        row = res[0]
        self.assertEqual(row["base"]["title"], "勾选想报的活动", "未勾选时保持第 2 步原文案")
        self.assertIn("勾选只是加入计划", row["base"]["text"], "未勾选时保持第 2 步原正文")
        self.assertEqual(row["picked"]["title"], "加入计划了", "勾选后卡片标题必须照原型换句")
        self.assertIn("右边的清单多了一场", row["picked"]["text"], "勾选后正文必须照原型换句")
        self.assertEqual(row["restored"]["title"], "勾选想报的活动", "取消勾选换回原标题")
        self.assertIn("点这一行试试", row["restored"]["text"], "取消勾选换回原正文")
        self.assertEqual(row["picked"]["step"], row["base"]["step"], "步数不随换卡变")
        self.assertEqual(row["picked"]["next"], row["base"]["next"], "主钮文案不随换卡变")
        self.assertEqual(row["picked"]["dots"], row["base"]["dots"], "圆点不随换卡变")
        self.assertEqual(row["otherStep"]["title"], "这是活动时刻表", "第 2 步之外不受勾选影响")

    def test_spot_stays_visible_when_card_falls_to_bottom(self):
        """卡片放不下改放底部时目标框仍在；只有目标缺失/不可见才藏（R1）。"""
        res = run_js(r"""
startTour(0);
const box = document.querySelector("#tour");
const spot = document.querySelector("#tour-spot");
const target = document.querySelector('[data-tour-target="list"]');
window.innerHeight = 200;        /* 卡片下方放不下，回退到底部 */
document.querySelector("#tour-card").offsetHeight = 400;
target.offsetWidth = 360;
paintTour();
const fallback = { isBottom: box.classList.contains("is-bottom"),
  noTarget: box.classList.contains("no-target"), spotTop: String(spot.style.top) };
target.offsetWidth = 0;          /* 目标不可见：这时才隐藏框 */
paintTour();
const missing = { isBottom: box.classList.contains("is-bottom"),
  noTarget: box.classList.contains("no-target"), spotTop: String(spot.style.top) };
out.push({ fallback, missing });
tourSkip();
""")
        row = res[0]
        self.assertTrue(row["fallback"]["isBottom"], "卡片放不下要落到底部")
        self.assertFalse(row["fallback"]["noTarget"], "目标还在，不能挂 no-target")
        self.assertNotEqual(row["fallback"]["spotTop"], "", "目标在就必须看得见高亮框")
        self.assertTrue(row["missing"]["noTarget"], "目标不可见时才挂 no-target")
        self.assertEqual(row["missing"]["spotTop"], "", "没有目标时不画高亮框")


class SettingsEntryContractTests(unittest.TestCase):
    """设置与帮助分成两个入口（设计第 8 节）：设置抽屉分高级功能 / 登录 / 程序三组，帮助只留快速说明。

    取代旧的「单帮助入口、版本更新与本机数据都在帮助里、不得有 #btn-settings / #settings」：
    新工作台把会改东西的项（手机访问、验证码识别、保存账号、关闭窗口时、更新、数据、条款撤回）
    收进设置抽屉，帮助只讲怎么用；两处都不得保留第二套旧节点。"""

    def test_index_has_settings_entry_and_groups(self):
        """顶栏有「设置」「帮助」两个入口；设置抽屉三组，版本更新与本机数据在「程序」组。"""
        html = read("ui/index.html")
        for btn, name, label in (("btn-settings", "设置：高级功能、登录、程序", "设置"),
                                 ("btn-help", "帮助：使用说明、快捷键、重看引导", "帮助")):
            at = html.index('id="%s"' % btn)
            tag = html[at:html.index("</button>", at)]
            self.assertIn('aria-label="%s"' % name, tag, "入口必须有可读的无障碍名（不能只靠图标）")
            self.assertIn('<span class="lbl">%s</span>' % label, tag, "顶栏按钮的文字必须是「%s」" % label)
            self.assertIn("<svg", tag, "顶栏入口必须带内联 SVG 图标")
        self.assertEqual(html.count('id="settings"'), 1, "只有一个设置抽屉")
        drawer = settings_drawer(html)
        self.assertIn('role="dialog"', drawer)
        for sec, title in (("adv", "高级功能"), ("login", "登录"), ("prog", "程序")):
            self.assertIn('data-sec="%s">%s<' % (sec, title), drawer, "设置导航缺「%s」" % title)
            self.assertIn('id="set-%s"' % sec, drawer, "设置抽屉缺分组 #set-%s" % sec)
        prog = drawer[drawer.index('id="set-prog"'):]
        for needle in ("close-pref", "help-version", "btn-update-check", "update-status",
                       "btn-help-latest", "btn-help-data", "btn-terms-withdraw", "help-status"):
            self.assertIn('id="%s"' % needle, prog, "「设置 → 程序」缺组件 #%s" % needle)
        # 「前往下载页」按 UP10 照原型改成底注句内链接钮「打开发布页」（原型 Main.dc.html:784）
        for text in ("关闭窗口时", "版本与更新", "本机数据", "打开数据目录", "打开发布页", "撤回同意"):
            self.assertIn(text, prog, "「设置 → 程序」缺「%s」" % text)
        adv = drawer[drawer.index('id="set-adv"'):drawer.index('id="set-login"')]
        for needle in ("btn-phone-feature-install", "btn-ocr-download"):
            self.assertIn('id="%s"' % needle, adv, "「设置 → 高级功能」缺 #%s" % needle)
        login = drawer[drawer.index('id="set-login"'):drawer.index('id="set-prog"')]
        self.assertIn('id="relogin-card"', login, "「设置 → 登录」缺保存账号卡片")
        dialog = help_dialog(html)
        self.assertNotIn("set-group", dialog + drawer, "不再用三张同形分组卡")
        self.assertNotIn('id="settings"', dialog, "帮助里不嵌第二个设置")
        for banned in ("清空凭证", "重置", "自动更新", "自动检查更新"):
            self.assertNotIn(banned, dialog + drawer, "设置和帮助都不得出现未确认功能「%s」" % banned)

    def test_help_dialog_keeps_quick_help_only(self):
        """帮助只留三步说明、快捷键、重看引导与「知道了」；版本更新、数据目录与条款不在帮助里。

        原型 Main.dc.html:744-746 是 1:1 基准：帮助里没有条款入口，条款只在「设置 → 条款与隐私」。"""
        html = read("ui/index.html")
        help_body = help_dialog(html)
        for component in ("help-version", "btn-update-check", "update-status", "btn-help-data",
                          "btn-terms-withdraw", "phone-feature-status"):
            self.assertNotIn('id="%s"' % component, help_body,
                             "#%s 属于「设置」，帮助里不得保留第二份" % component)
        for text in ("三步使用说明", "键盘快捷键", "重看引导", "知道了"):
            self.assertIn(text, help_body, "帮助缺「%s」" % text)
        self.assertNotIn('id="btn-help-terms-view"', help_body,
                         "帮助里不再有条款入口（原型 :744-746）")
        self.assertNotIn("使用条款与隐私", help_body, "条款入口只留在设置里")
        self.assertIn("关闭", help_body, "帮助弹窗保留关闭按钮")
        self.assertIn('id="btn-help-tour"', help_body,
                      "说明底部保留重播快捷入口（学习入口就近可重播）")
        self.assertIn('id="help-steps"', help_body, "说明弹窗保留三步快速帮助容器")
        js = read("ui/app.js")
        for step_title in ("确认登录", "选活动并开始", "看结果"):
            self.assertIn(step_title, js, "三步快速帮助必须保留（%s）" % step_title)
        self.assertIn("再点“开始报名计划”", js,
                      "三步说明必须写出真正的开始动作（HK02：引号照原型弯引号）")

    def test_app_js_wires_settings_actions(self):
        """两处重播共用 replayTourFrom；版本/目录仍走既有接口；忙时禁用有可见原因。"""
        js = read("ui/app.js")
        for anchor in ('$("#btn-help")', '$("#btn-help-tour")', '$("#btn-settings")',
                       '$("#btn-help-latest")', '$("#btn-help-data")', '$("#btn-settings-close")'):
            self.assertIn(anchor, js, "app.js 缺入口绑定：%s" % anchor)
        # #btn-settings 从「旧引用」改为必须绑定：新工作台把设置做回独立抽屉（views/settings.js）
        for stale in ('$("#btn-latest")', '$("#settings-version")'):
            self.assertNotIn(stale, js, "app.js 残留旧引用 %s（元素已删除会直接抛错）" % stale)
        self.assertIn("function openSettings(", js, "设置抽屉必须有打开函数")
        self.assertIn("function openSettingsSection(", js, "提醒里的「去保存/去安装」要能直达分组")
        self.assertIn('replayTourFrom("#help", "#btn-help")', js,
                      "更多里的重播必须走共用处理函数")
        self.assertIn('replayTourFrom("#help", "#btn-help")', js,
                      "说明里的重播必须走同一个处理函数")
        body = js[js.index("function replayTourFrom("):js.index("function paintReplayButtons")]
        self.assertIn("S.busy", body, "重播必须先确认非忙")
        self.assertIn("dialog.close()", body, "重播前必须关掉当前弹窗，不叠模态")
        self.assertIn("opener.focus()", body, "重播前把焦点还给对应顶栏入口")
        self.assertIn("startTour(0)", body, "重播最终从第 1 步开始")
        self.assertIn('api("open_latest_release")', js, "查看发布页仍走既有后端外链")
        self.assertIn('api("open_data")', js, "打开数据目录复用既有后端接口")
        replay = js[js.index("function paintReplayButtons("):js.index("function savePrefs(")]
        self.assertIn("btn.disabled = !!S.busy", replay, "忙时必须禁用重播")
        self.assertIn('"计划结束后可重看引导"', replay, "禁用原因必须可见，不只靠 title")

    def test_dialog_keys_do_not_penetrate(self):
        """任意 dialog 打开时 Enter/Esc 不穿透（不开始计划、不清空选择）。"""
        js = read("ui/app.js")
        key_at = js.index('document.addEventListener("keydown"')
        body = js[key_at:key_at + 2400]
        self.assertIn('"#help"', body,
                      "弹窗键盘隔离必须覆盖更多弹窗")
        # 原因：停止确认不再是 <dialog>（没有 .open），键盘隔离改成「弹层可见」判断并由 stopAskKey 接管
        self.assertIn("stopAskOpen()", body, "停止确认弹层可见时键盘归弹层")
        self.assertIn("stopAskKey(event)", body, "弹层可见时 Esc/Tab/Enter 交给 stopAskKey")
        self.assertNotIn("#dlg-stop", body, "旧 #dlg-stop 不再参与键盘隔离")


class SettingsDialogBehaviorTests(unittest.TestCase):
    """设置入口行为回归（node vm 行为，不开浏览器、不调用学校）。"""

    def test_top_entry_opens_and_replay_chain(self):
        """顶栏入口打开设置；重看引导先关设置再进引导。"""
        res = run_js(r"""
document.querySelector("#btn-help").click();
const opened = document.querySelector("#help").open;
document.querySelector("#btn-help-tour").click();
out.push({ opened,
  settingsClosed: !document.querySelector("#help").open,
  tourOpen: S.tour.open, step: S.tour.step });
tourSkip();
""")
        self.assertTrue(res[0]["opened"], "点顶栏「设置」必须打开设置弹窗")
        self.assertTrue(res[0]["settingsClosed"], "重播前必须先关闭设置弹窗")
        self.assertTrue(res[0]["tourOpen"], "重播必须进入六步引导")
        self.assertEqual(res[0]["step"], 0, "重播从第 1 步开始")

    def test_running_can_open_settings_but_not_replay(self):
        """计划运行中：设置可打开、重看引导禁用且不重播；结束后可重播。"""
        res = run_js(r"""
setBusy(true);
document.querySelector("#btn-help").click();
const openedWhileBusy = document.querySelector("#help").open;
const replayDisabled = document.querySelector("#btn-help-tour").disabled;
document.querySelector("#btn-help-tour").click();
const tourNotOpened = !S.tour.open;
setBusy(false);
document.querySelector("#btn-help-tour").click();
const tourOpenedAfterEnd = S.tour.open;
out.push({ openedWhileBusy, replayDisabled, tourNotOpened, tourOpenedAfterEnd });
tourSkip();
""")
        self.assertTrue(res[0]["openedWhileBusy"], "计划运行中也必须能打开设置")
        self.assertTrue(res[0]["replayDisabled"], "运行中「重看引导」必须禁用")
        self.assertTrue(res[0]["tourNotOpened"], "运行中不得重播引导打断计划")
        self.assertTrue(res[0]["tourOpenedAfterEnd"], "计划结束后可以重播")

    def test_dialog_open_blocks_enter_and_escape_penetration(self):
        """设置弹窗打开时：Enter 不开始计划、Esc 不清空选择、不误跳引导。"""
        res = run_js(r"""
S.selected.add("a1");
let startCalled = 0;
const realStart = startPlan;
startPlan = () => { startCalled += 1; };
const dlg = document.querySelector("#help");
dlg.open = true;
__dispatchKey({ key: "Enter" });
__dispatchKey({ key: "Escape" });
dlg.open = false;
startPlan = realStart;
out.push({ startCalled, selKept: S.selected.has("a1"), tourOpen: S.tour.open });
""")
        self.assertEqual(res[0]["startCalled"], 0, "弹窗打开时 Enter 不得穿透开始计划")
        self.assertTrue(res[0]["selKept"], "弹窗打开时 Esc 不得清空选择")
        self.assertFalse(res[0]["tourOpen"], "弹窗打开时 Esc 不得误触引导")

    def test_latest_and_data_actions_called_once_per_click(self):
        """「GitHub 最新版本」与「打开数据目录」各走一次既有后端接口。"""
        res = run_js(r"""
window.pywebview = { api: {
  open_latest_release: () => { out.latest = (out.latest || 0) + 1; return Promise.resolve({ ok: true }); },
  open_data: () => { out.data = (out.data || 0) + 1; return Promise.resolve({ ok: true }); },
} };
document.querySelector("#btn-help-latest").click();
document.querySelector("#btn-help-data").click();
out.push({ latest: out.latest, data: out.data });
""")
        self.assertEqual(res[0]["latest"], 1, "外链每次点击恰调用一次")
        self.assertEqual(res[0]["data"], 1, "数据目录每次点击恰调用一次")


class AssistanceBehaviorTests(unittest.TestCase):
    """说明/更多/重播：文案同源、全状态可开、焦点归还、外链与目录一次一点击。"""

    # 已确认的文案基线：两端一起漂移时，这一份仍然能挡住
    # 原型 Main.dc.html:745 是 1:1 基准：副标题与三步逐字照抄，也不再带适用范围 note
    # （那两句在首次使用的条款摘要里，原型 :750）。
    _EXPECTED_COPY = {
        "title": "使用帮助",
        "subtitle": "三步完成一次报名",
        "steps": [
            (1, "确认登录",
             "顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。"),
            (2, "选活动并开始",
             "在时刻表勾选活动，核对右边的计划，再点“开始报名计划”。勾选不会自动开始。"),
            (3, "看结果",
             "每场结果单独显示。看到“待核对”时，到学校活动页确认。"),
        ],
    }

    def test_backend_help_payload_matches_default_help(self):
        """Api.help() 的真实载荷与 DEFAULT_HELP 逐字段一致（结构 + 顺序 + 文案）。

        后端：ast 只编译 Api.help，注入版本/地址常量后调用 help(None)；
        前端：node 里把生产 DEFAULT_HELP 取出来。两边深比较，不用源码子串。
        """
        backend = load_backend_help()
        frontend = run_js("out.push(JSON.parse(JSON.stringify(DEFAULT_HELP)));")[0]
        expected = self._EXPECTED_COPY

        # 后端载荷结构：字段齐全、步骤编号有序、版本/外链来自注入常量
        self.assertEqual(sorted(backend),
                         ["latest_url", "steps", "subtitle", "title", "version"],
                         "help 载荷字段发生变化（原型帮助没有 note）")
        self.assertEqual(backend["version"], HELP_TEST_VERSION,
                         "版本必须来自 APP_VERSION，不能写死")
        self.assertEqual(backend["latest_url"], HELP_TEST_URL,
                         "发布页地址必须来自 RELEASES_LATEST_URL")
        self.assertEqual([step["no"] for step in backend["steps"]], [1, 2, 3],
                         "三步顺序必须是 1/2/3")
        for step in backend["steps"]:
            self.assertEqual(sorted(step), ["no", "text", "title"],
                             "步骤字段结构变化")

        # 前端对象不带第二套版本来源
        self.assertEqual(sorted(frontend), ["steps", "subtitle", "title"],
                         "DEFAULT_HELP 不得自带版本/地址字段，也不再带 note")

        # 逐字段深比较（含中文全角标点）
        self.assertEqual(frontend["title"], backend["title"])
        self.assertEqual(frontend["subtitle"], backend["subtitle"])
        self.assertEqual(len(frontend["steps"]), len(backend["steps"]))
        for got, want in zip(frontend["steps"], backend["steps"]):
            self.assertEqual((got["no"], got["title"], got["text"]),
                             (want["no"], want["title"], want["text"]),
                             "第 %s 步两处必须一字不差" % want["no"])

        # 与已确认文案独立比对：防止前后端一起漂移而深比较仍然通过
        self.assertEqual(backend["title"], expected["title"])
        self.assertEqual(backend["subtitle"], expected["subtitle"])
        self.assertEqual([(step["no"], step["title"], step["text"])
                          for step in backend["steps"]], expected["steps"])

    def test_more_opens_in_every_state(self):
        """未登录 / 组件报错 / 计划运行中都开得出来；说明与更多不叠模态。"""
        res = run_js(r"""
function openCase(prepare) {
  prepare();
  const dlg = document.querySelector("#help");
  if (dlg.open) dlg.close();
  document.querySelector("#btn-help").click();
  const opened = dlg.open;
  dlg.close();
  return opened;
}
const fresh = openCase(() => { S.busy = false; S.runtime.error = null; });
const errored = openCase(() => { S.runtime.error = "worker_missing"; });
const busy = openCase(() => { S.busy = true; });
S.busy = false;
document.querySelector("#btn-help").click();
const helpOpen = document.querySelector("#help").open;
document.querySelector("#btn-help").click();
const stacked = { more: document.querySelector("#help").open,
  tour: S.tour.open };
out.push({ fresh, errored, busy, helpOpen, stacked });
""")
        case = res[0]
        self.assertTrue(case["fresh"], "常态必须能打开更多")
        self.assertTrue(case["errored"], "组件报错时更多仍要能打开")
        self.assertTrue(case["busy"], "计划运行中也要能打开更多")
        self.assertTrue(case["helpOpen"])
        self.assertTrue(case["stacked"]["more"])
        self.assertFalse(case["stacked"]["tour"], "重复打开帮助不能自行启动引导")

    def test_both_replay_entries_close_dialog_and_return_focus(self):
        """两处重播都先关弹窗、从第 1 步开始，退出后焦点回到各自顶栏入口。"""
        res = run_js(r"""
const more = document.querySelector("#help");
const help = document.querySelector("#help");
document.querySelector("#btn-help").click();
document.querySelector("#btn-help-tour").click();
const fromMore = { closed: !more.open, tour: S.tour.open, step: S.tour.step,
  opener: S.tour.restoreFocus && S.tour.restoreFocus.__sel };
tourSkip();
const afterMore = focused.slice(-1)[0];
document.querySelector("#btn-help").click();
document.querySelector("#btn-help-tour").click();
const fromHelp = { closed: !help.open, tour: S.tour.open, step: S.tour.step,
  opener: S.tour.restoreFocus && S.tour.restoreFocus.__sel };
tourSkip();
const afterHelp = focused.slice(-1)[0];
out.push({ fromMore, afterMore, fromHelp, afterHelp,
  otherStillOpen: more.open, helpStillOpen: help.open });
""")
        case = res[0]
        self.assertTrue(case["fromMore"]["closed"], "重播前必须先关掉更多")
        self.assertTrue(case["fromMore"]["tour"])
        self.assertEqual(case["fromMore"]["step"], 0)
        self.assertEqual(case["fromMore"]["opener"], "#btn-help",
                         "开始前的焦点必须是「更多」入口")
        self.assertEqual(case["afterMore"], "#btn-help", "退出引导把焦点还回更多入口")
        self.assertTrue(case["fromHelp"]["closed"], "重播前必须先关掉说明")
        self.assertEqual(case["fromHelp"]["opener"], "#btn-help")
        self.assertEqual(case["afterHelp"], "#btn-help")
        self.assertFalse(case["otherStillOpen"])
        self.assertFalse(case["helpStillOpen"])

    def test_busy_disables_replay_but_keeps_version_visible(self):
        """运行中两处重播都禁用并写明原因；版本仍可查，点击也不进引导。"""
        res = run_js(r"""
document.querySelector("#help-version").textContent = "9.9.9";
setBusy(true);
document.querySelector("#btn-help").click();
const opened = document.querySelector("#help").open;
const tourBtn = document.querySelector("#btn-help-tour");
const helpBtn = document.querySelector("#btn-help-tour");
const disabled = { tour: tourBtn.disabled, help: helpBtn.disabled };
const label = tourBtn.textContent;
/* 桩不按 disabled 拦截点击：这里同时验证代码自己的忙判定 */
document.querySelector("#btn-help-tour").click();
const noTour = !S.tour.open;
const version = document.querySelector("#help-version").textContent;
setBusy(false);
out.push({ opened, disabled, label, noTour, version,
  restored: { disabled: tourBtn.disabled, label: tourBtn.textContent } });
""")
        case = res[0]
        self.assertTrue(case["opened"], "运行中也要能打开更多查版本")
        self.assertTrue(case["disabled"]["tour"], "运行中「更多」里的重播必须禁用")
        self.assertTrue(case["disabled"]["help"], "运行中说明里的重播也必须禁用")
        self.assertEqual(case["label"], "计划结束后可重看引导",
                         "禁用原因必须直接写在按钮上，不只靠 title")
        self.assertTrue(case["noTour"], "禁用期间点击不得进引导")
        self.assertEqual(case["version"], "9.9.9", "版本仍必须可见")
        self.assertFalse(case["restored"]["disabled"], "计划结束后重播恢复可用")
        self.assertEqual(case["restored"]["label"], "重看引导")

    def test_external_actions_fire_once_and_not_on_open(self):
        """打开弹窗不联网、不开目录；每次点击恰调用一次既有接口。"""
        res = run_js(r"""
let latest = 0, data = 0;
window.pywebview = { api: {
  open_latest_release: () => { latest += 1; return Promise.resolve({ ok: true }); },
  open_data: () => { data += 1; return Promise.resolve({ ok: true }); },
} };
document.querySelector("#btn-help").click();
const atOpen = { latest, data };
document.querySelector("#btn-help-latest").click();
document.querySelector("#btn-help-data").click();
await Promise.resolve();
out.push({ atOpen, latest, data,
  statusHidden: document.querySelector("#help-status").hidden });
""")
        case = res[0]
        self.assertEqual(case["atOpen"], {"latest": 0, "data": 0},
                         "打开弹窗不得自动联网或打开目录")
        self.assertEqual(case["latest"], 1, "外链每次点击恰调用一次")
        self.assertEqual(case["data"], 1, "数据目录每次点击恰调用一次")
        self.assertTrue(case["statusHidden"], "成功时不显示局部错误")

    def test_failures_show_local_status_with_fixed_url(self):
        """失败只在这个弹窗里说下一步；发布页失败要给出可复制的固定地址。"""
        res = run_js(r"""
window.pywebview = { api: {
  open_latest_release: () => Promise.resolve({ ok: false }),
  open_data: () => Promise.reject(new Error("没有权限")),
} };
document.querySelector("#btn-help").click();
document.querySelector("#btn-help-latest").click();
await Promise.resolve(); await Promise.resolve();
const latest = { hidden: document.querySelector("#help-status").hidden,
  text: document.querySelector("#help-status").textContent,
  tone: document.querySelector("#help-status").dataset.tone };
document.querySelector("#btn-help-data").click();
await Promise.resolve(); await Promise.resolve();
const data = { hidden: document.querySelector("#help-status").hidden,
  text: document.querySelector("#help-status").textContent,
  tone: document.querySelector("#help-status").dataset.tone };
out.push({ latest, data, url: RELEASES_LATEST_URL });
""")
        case = res[0]
        self.assertFalse(case["latest"]["hidden"], "失败必须在弹窗里可见")
        self.assertIn("发布页没能打开", case["latest"]["text"])
        self.assertIn(case["url"], case["latest"]["text"], "要把固定地址摆出来供复制")
        self.assertEqual(case["latest"]["tone"], "warn")
        self.assertFalse(case["data"]["hidden"])
        self.assertIn("打不开数据目录", case["data"]["text"])
        self.assertIn("没有权限", case["data"]["text"])
        self.assertEqual(case["data"]["tone"], "bad")

    def test_open_data_success_writes_real_path_into_help_text(self):
        """成功打开数据目录：真实路径进正文说明行，错误位保持隐藏。"""
        res = run_js(r"""
const realPath = "C:\\Users\\demo\\AppData\\Local\\TianSoftActivityPreRegistration\\data";
window.pywebview = { api: {
  open_data: () => Promise.resolve({ ok: true, path: realPath }),
} };
document.querySelector("#btn-help").click();
document.querySelector("#btn-help-data").click();
await Promise.resolve(); await Promise.resolve();
const line = document.querySelector("#help-data-path");
const status = document.querySelector("#help-status");
out.push({ lineText: line.textContent, statusHidden: status.hidden,
  statusText: status.textContent });
""")
        case = res[0]
        self.assertIn("C:\\Users\\demo", case["lineText"],
                      "用户最常问的就是数据在哪，真实路径必须写在正文里")
        self.assertTrue(case["statusHidden"], "成功不是错误，不得点亮错误位")
        self.assertEqual(case["statusText"], "", "错误位不得混入成功路径")

    def test_open_data_failure_keeps_help_text_and_shows_reason(self):
        """失败时正文说明行不被清空或污染，错误只进错误位。"""
        res = run_js(r"""
window.pywebview = { api: {
  open_data: () => Promise.reject(new Error("目录被占用")),
} };
document.querySelector("#btn-help").click();
const line = document.querySelector("#help-data-path");
const before = line.textContent;
document.querySelector("#btn-help-data").click();
await Promise.resolve(); await Promise.resolve();
const status = document.querySelector("#help-status");
out.push({ before, after: line.textContent, statusHidden: status.hidden,
  statusText: status.textContent });
""")
        case = res[0]
        self.assertEqual(case["after"], case["before"],
                         "失败不改写正文说明，重试语义由错误位承载")
        self.assertNotIn("目录被占用", case["after"], "错误原因不得污染正文行")
        self.assertFalse(case["statusHidden"])
        self.assertIn("打不开数据目录", case["statusText"])
        self.assertIn("目录被占用", case["statusText"])


class OpenDataContractTests(unittest.TestCase):
    """后端 open_data 契约：只回 ok + 目录路径，绝不回传登录文件内容。"""

    def test_api_open_data_returns_only_ok_and_path(self):
        """用 ast 隔离求值 Api.open_data：返回字典只允许 ok/path 两个键。"""
        import ast
        import os
        import tempfile

        tree = ast.parse(read("app.py"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "open_data"
                    and [arg.arg for arg in item.args.args][:1] == ["self"])
        module = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(module)
        with tempfile.TemporaryDirectory() as name:
            # os.startfile 只在真打开目录时有副作用；用假实现替掉，断言不执行
            namespace = {"os": type("FakeOS", (), {"startfile": staticmethod(
                lambda p: launched.append(p))})(),
                         "ensure_data_dir": lambda: Path(name)}
            launched = []
            exec(compile(module, "<Api.open_data>", "exec"), namespace)  # noqa: S102 - 只编译受控片段
            result = namespace["open_data"](None)
        self.assertTrue(result.get("ok"))
        self.assertEqual(sorted(result.keys()), ["ok", "path"],
                         "回传键固定为 ok/path：多一个字段就是把不该给的塞给界面")
        self.assertEqual(result["path"], str(Path(name)))
        self.assertEqual(launched, [str(Path(name))],
                         "打开目录的副作用必须仍然发生（os.startfile 恰一次）")

    def test_success_handler_does_not_touch_login_files(self):
        """前端成功分支只引用 res.path；登录文件名不得出现在处理块里。"""
        js = read("ui/app.js")
        start = js.index('$("#btn-help-data").addEventListener')
        end = js.index("window.addEventListener(\"resize\"", start)
        block = js[start:end]
        for banned in ("session.json", "storage_state", "token"):
            self.assertNotIn(banned, block,
                             "打开数据目录的成功反馈不得引用登录文件：%s" % banned)
        self.assertIn("help-data-path", block, "成功路径必须写回正文说明行")
        then_branch = block[block.index(".then"):block.index(".catch")]
        self.assertNotIn("helpStatus", then_branch,
                         "成功反馈不得写错误位（进入 then 前的 helpStatus("") 只是清场复位）")


class DialogCloseButtonRuleTests(unittest.TestCase):
    """规则：只有阅读型面板保留 ×，帮助与重新登录靠底部按钮和 Esc 关闭（用户 2026-11-08 定）。"""

    @staticmethod
    def _dialog_block(html, opener):
        start = html.index(opener)
        end = html.index("</dialog>", start) + len("</dialog>")
        return html[start:end]

    def test_help_dialog_has_no_x_and_uses_bottom_button(self):
        html = read("ui/index.html")
        block = self._dialog_block(html, '<dialog class="dlg dlg-help" id="help"')
        self.assertNotIn("dlg-x", block, "帮助弹窗不得有 × 关闭按钮")
        self.assertIn('<form method="dialog"><button class="btn btn-solid" type="submit">知道了</button></form>',
                      block, "帮助弹窗底部必须有「知道了」关闭按钮")

    def test_relogin_dialog_has_no_x(self):
        html = read("ui/index.html")
        block = self._dialog_block(html, '<dialog class="dlg dlg-relogin" id="dlg-relogin"')
        self.assertNotIn("dlg-x", block, "重新登录弹窗不得有 × 关闭按钮")

    def test_first_use_and_terms_update_dialogs_have_no_x(self):
        """FU01/TM08（原型 Main:800/878；UI_SPEC §5.13）：两个条款小框都是
        「做决定的弹窗」，不放右上角 ×——退出只走「暂不使用／暂不同意」与 Esc。"""
        html = read("ui/index.html")
        intro = self._dialog_block(html, '<dialog class="dlg dlg-terms-intro" id="dlg-terms-intro"')
        update = self._dialog_block(html, '<dialog class="dlg dlg-tu" id="dlg-terms-update"')
        self.assertNotIn("dlg-x", intro, "首次说明框不得有 × 关闭按钮")
        self.assertNotIn("dlg-x", update, "条款更新框不得有 × 关闭按钮")

    def test_settings_drawer_keeps_close_button(self):
        html = read("ui/index.html")
        self.assertIn('id="btn-settings-close"', html, "设置抽屉（阅读型面板）必须保留 × 关闭按钮")


class BookmarkCopyContractTests(unittest.TestCase):
    """桌面帮助页与手机页必须给同一句话：扫码只当首次引导，长期入口是书签。"""

    COPY = "打开后建议加入手机书签，方便下次访问。"

    def _read(self, *parts):
        return (LOCAL.joinpath(*parts)).read_text(encoding="utf-8")

    def test_desktop_and_mobile_share_the_same_hint(self):
        desktop = self._read("ui", "index.html")
        mobile = self._read("ui", "m", "index.html")
        view = self._read("ui", "views", "phone.js")
        # fe-phone 同步：桌面抽屉照原型删了两处旧书签句（PH22），只在开启 Tailscale 后留一句
        # 「地址固定，建议在手机上存成书签，下次直接打开。」（PH27）。手机页不在本计划范围（local/ui/m/** 禁改），
        # 仍是旧句；两页措辞不再逐字相同，这一处列进 result 给用户定
        self.assertIn(self.COPY, mobile, "手机页要提示存书签")
        self.assertNotIn(self.COPY, desktop, "桌面旧书签句按 PH22 删除")
        desktop_copy = "地址固定，建议在手机上存成书签，下次直接打开。"
        self.assertIn(desktop_copy, desktop, "桌面固定地址要提示存书签")
        self.assertIn(desktop_copy, view)


if __name__ == "__main__":
    unittest.main()
