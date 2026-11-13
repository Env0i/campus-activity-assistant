# -*- coding: utf-8 -*-
"""界面契约：桥接、分层边界、名称、图标、关窗与迁移横幅。"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read, strip_ui_comments, run_js, WB_STAMP_JS  # noqa: E402


class BridgeContractTests(unittest.TestCase):
    """桥接方法与事件名：界面和 app.py 的契约字面量。"""

    def test_app_js_calls_bridge_methods(self):
        js = read("ui/app.js")
        for method in ("bootstrap", "check", "list_activities", "login",
                       "start_plan", "cancel_task", "stop_plan",
                       "open_data", "save_prefs", "front_ready"):
            self.assertIn('"%s"' % method, js, "app.js 缺少桥接方法调用：%s" % method)

    def test_app_js_handles_backend_events(self):
        import re
        js = read("ui/app.js")
        self.assertIn("window.onBackend", js, "app.js 必须挂载 window.onBackend")
        for event in ("log", "check", "activities", "done", "plan", "task", "plan_done"):
            self.assertRegex(js, r"\b%s\s*:\s*\(" % event,
                             "window.onBackend 缺少事件处理：%s" % event)

    def test_no_mock_backend_in_production(self):
        """生产页面不得引用原型 mock-backend。"""
        html = read("ui/index.html")
        self.assertNotIn("mock-backend", html, "index.html 不得加载原型 mock-backend.js")
        self.assertNotIn("proto/", html, "index.html 不得引用 design/prototype 的资源")


class LayerBoundaryContractTests(unittest.TestCase):
    """分层结构契约：呈现归 views，controller 不直接读写 DOM；加载序即依赖序。"""

    VIEW_BEFORE_DEPENDENT = (
        ("views/terms.js", "controllers/terms.js"),
        ("views/update.js", "controllers/update.js"),
        ("views/update.js", "views/help.js"),
    )

    def test_script_load_order_puts_views_before_dependents(self):
        html = read("ui/index.html")
        scripts = re.findall(r'<script src="([^"]+)"></script>', html)
        for view, dependent in self.VIEW_BEFORE_DEPENDENT:
            self.assertIn(view, scripts, "缺少 %s" % view)
            self.assertIn(dependent, scripts, "缺少 %s" % dependent)
            self.assertLess(scripts.index(view), scripts.index(dependent),
                            "%s 必须先于 %s 加载（经典 script 顺序即依赖序）"
                            % (view, dependent))

    def test_terms_and_update_controllers_do_not_render_dom(self):
        """条款/更新 controller 只做状态编排与桥接效果，DOM 查询与呈现都在 views。"""
        banned = (
            "$(", "document.", "querySelector", ".textContent", ".innerHTML",
            ".dataset.", "showModal", ".hidden = ", ".disabled = ", ".focus(",
            "classList", "scrollTop", "setAttribute", ".close()", "createElement",
        )
        for rel in ("ui/controllers/terms.js", "ui/controllers/update.js"):
            js = read(rel)
            for token in banned:
                self.assertNotIn(token, js,
                                 "%s 不得直接呈现 DOM：%s" % (rel, token))


class NameContractTests(unittest.TestCase):
    """正式名称契约：校园活动预报名工具；「准点」只留在历史说明里。"""

    def test_formal_name_present_everywhere(self):
        for rel in ("../README.md", "README.md", "../docs/UI_SPEC.md",
                    "ui/index.html", "app.py"):
            self.assertIn("校园活动预报名工具", read(rel),
                          "%s 必须包含正式名称「校园活动预报名工具」" % rel)

    def test_window_title_uses_formal_name(self):
        py = read("app.py")
        self.assertIn('"title": "使用帮助"', py, "帮助标题描述用途，正式名称仍由窗口标题表达")
        self.assertIn("校园活动预报名工具\", str(UI)", py,
                      "webview.create_window 的窗口标题必须是正式名称")

    def test_runtime_no_zhundian_brand(self):
        """运行时文件里不得再出现「准点」品牌（历史原型称呼）。"""
        for rel in ("ui/index.html", "app.py", "ui/app.js"):
            self.assertNotIn("准点", read(rel),
                             "%s 不得再使用旧品牌「准点」" % rel)

    def test_short_label_for_narrow_window(self):
        html = read("ui/index.html")
        self.assertIn("校园预报名工具", html, "窄窗口短标签「校园预报名工具」必须存在")


class BrandIconContractTests(unittest.TestCase):
    """入场券标志契约：旧深色方块加圆点已替换，head link 与 brand 文件齐备。"""

    def test_old_brand_dot_group_gone(self):
        """旧标志：深色方块 + cy=9.5 r=2.6 和 cy=14 r=2.6 两个圆点。
        入场券版（UI-C）后这组坐标不得再出现在运行时页面。"""
        for rel in ("ui/index.html", "ui/m/index.html"):
            text = read(rel)
            self.assertNotIn('cy="9.5"', text,
                             "%s 不应再有旧标志圆点 cy=9.5" % rel)
            self.assertNotIn('cy="14" cy="18.5"', text,
                             "%s 不应再有旧标志两个圆点" % rel)

    def test_desktop_page_has_favicon_link(self):
        """桌面版 head 必须声明 brand/favicon.ico。"""
        html = read("ui/index.html")
        self.assertIn('rel="icon"', html, "必须有 favicon link")
        self.assertIn('brand/favicon.ico', html, "favicon 必须指向 brand/favicon.ico")

    def test_desktop_page_uses_new_logo_mark(self):
        """顶栏 brand-mark 的 SVG 必须是 64×64 入场券三条 path，
        不是原来的 28×28 深色方块。"""
        html = read("ui/index.html")
        self.assertIn('viewBox="0 0 64 64"', html,
                      "brand-mark 必须换入场券 64×64 viewBox")
        # 三条 path 的特征：琥珀色外圈 #B98319 + 浅琥珀内圈 + 深墨黑勾
        self.assertIn("#B98319", html, "入场券外圈琥珀色 #B98319 必须在 index.html")
        self.assertIn("#FFB020", html, "入场券内圈浅琥珀 #FFB020 必须在 index.html")

    def test_mobile_page_has_two_icon_links(self):
        """手机页 head 必须声明 favicon.ico 和 apple-touch-icon.png。"""
        html = read("ui/m/index.html")
        self.assertIn('rel="icon"', html, "手机页必须有 favicon link")
        self.assertIn('href="favicon.ico"', html, "favicon 必须指向 favicon.ico")
        self.assertIn('rel="apple-touch-icon"', html,
                      "手机页必须有 apple-touch-icon link")
        self.assertIn('apple-touch-icon.png', html,
                      "apple-touch-icon 必须指向 apple-touch-icon.png")

    def test_mobile_page_has_bar_logo(self):
        """手机页顶栏必须有入场券品牌 SVG（带 aria 标注）。

        原断言钉住旧顶栏的 bar-logo 类（照电脑端头部搬的类名）：G01（frame-theme）
        照原型 Phone.dc.html:236-241 重排手机页顶栏，同一张入场券图形改用 .mark，
        品牌语义在 role=img + aria-label 上；断言随之改读 .mark，并加验 aria 标注。"""
        html = read("ui/m/index.html")
        self.assertIn('class="mark"', html, "手机页顶栏必须有 .mark 品牌图")
        self.assertIn('aria-label="校园预报名"', html,
                      "品牌图必须带 aria 标注")
        self.assertIn('viewBox="0 0 64 64"', html,
                      "手机页入场券 logo 必须是 64×64 viewBox")


class WindowCloseChoiceContractTests(unittest.TestCase):
    """关窗三选：X 不再等于直接退出，最小化/退出/记住都要在界面上有对应物。"""

    def setUp(self):
        self.html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        self.css = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")
        self.controller = (LOCAL / "ui" / "controllers" / "window.js").read_text(encoding="utf-8")

    def test_dialog_offers_hide_minimize_exit_and_cancel(self):
        for needle in ('id="dlg-close"', 'id="dlg-close-body"', 'id="dlg-close-remember"',
                       'id="btn-close-hide"', 'id="btn-close-minimize"',
                       'id="btn-close-exit"', 'id="btn-close-cancel"'):
            self.assertIn(needle, self.html, "关窗对话框缺少 %s" % needle)
        # CW04：卡题照原型改（`隐藏到后台运行`→`隐藏到后台`、`直接退出`→`退出程序`）
        self.assertIn("隐藏到后台", self.html)
        self.assertIn("最小化到任务栏", self.html)
        self.assertIn("退出程序", self.html)
        # CW14：勾选框文案照原型 Main:820（旧句「以后都这样，别再问我」已换）
        self.assertIn("以后都这样，不再询问", self.html)
        self.assertNotIn("别再问我", self.html)
        self.assertIn('src="controllers/window.js"', self.html)
        self.assertIn(".dlg-check", self.css)

    def test_choices_are_stacked_rows_not_a_button_row(self):
        """三个出口并排看不清谁更安全：改成竖排可选行，每行带一句代价说明。"""
        # CW04：卡类名照原型 .cch/.cch.danger（Main:480-487），顺序「最小化→隐藏→退出」
        self.assertEqual(3, self.html.count('class="cch"')
                         + self.html.count('class="cch danger"'))
        self.assertIn('class="cch danger"', self.html)
        self.assertLess(self.html.index('id="btn-close-minimize"'),
                        self.html.index('id="btn-close-hide"'),
                        "CW04 卡序：最小化（推荐）在最前")
        self.assertLess(self.html.index('id="btn-close-hide"'),
                        self.html.index('id="btn-close-exit"'),
                        "CW04 卡序：隐藏居中，退出（红）在最后")
        for needle in (".cchoices", ".cch", ".cch.danger", ".stakes"):
            self.assertIn(needle, self.css)
        # 一行放不下三个「标题+说明」按钮，旧的窄弹窗宽度不该再被这个对话框引用
        self.assertIn('class="dlg dlg-close"', self.html)

    def test_close_frame_matches_the_prototype(self):
        """CW01/CW07（原型 Main:811-823）：深色点阵标题栏＋琥珀左线、无右上 ×；
        勾选居左、「先不关」线框钮居右；确认步脚部「返回」＋红色 btn-stop「停止计划并退出」。"""
        start = self.html.index('id="dlg-close"')
        block = self.html[start:self.html.index("</dialog>", start)]
        self.assertIn('aria-label="正在运行的事"', block, "CW03 利害清单 aria 照原型")
        self.assertNotIn("dlg-x", block, "CW01 关窗框无右上 ×")
        self.assertIn('id="btn-close-cancel"', block)
        self.assertIn("先不关", block)
        # CW07：确认步两钮沿用既有 id，主钮改红色实心 btn-stop，钮名照原型 Main:821
        self.assertIn('class="btn btn-stop" id="btn-close-exit-confirm"', block)
        self.assertIn("停止计划并退出", block)
        self.assertNotIn("仍然退出", block, "旧钮名「仍然退出」已按原型换成「停止计划并退出」")
        self.assertIn('id="btn-close-exit-back"', block)
        self.assertIn("返回", block)
        # CW01：勾选框挪进脚部（foot 区在 .dlg-foot 内），文案 CW14
        foot = block[block.index('class="dlg-foot"'):]
        self.assertIn('id="dlg-close-remember-row"', foot)
        self.assertIn("以后都这样，不再询问", foot)
        # 样式：宽度与深色标题栏照原型 .dlg.sm + .dlg-h（Main:811、266-269）
        self.assertIn(".dlg-close { width: min(480px, 100%); }", self.css)
        for needle in ('.dlg-close .dlg-head h2 { margin: 0; padding-left: 11px;'
                       ' border-left: 3px solid var(--amber);',
                       "radial-gradient(circle at 1.5px 1.5px, rgba(255,255,255,.045) 1px, transparent 1.4px) 0 0/6px 6px, var(--board)"):
            self.assertIn(needle, self.css)

    def test_close_copy_follows_the_prototype(self):
        """CW02/CW04/CW05/CW08/CW12：两套标题副题、三卡正文、隐藏禁用句、确认步正文都在源码里。"""
        # CW02/CW12：运行／空闲两套标题与副题（原型 Main:1724-1725），由 window.js 渲染
        for needle in ("报名计划还在运行", "最小化或隐藏都不影响计划，退出会停止它。",
                       "要关闭窗口吗？", "选一个关闭方式。Esc 先不关。",
                       "退出会停止报名计划", "确定要退出吗？"):
            self.assertIn(needle, self.controller)
        self.assertNotIn("要关闭这个窗口吗？", self.html,
                         "CW02 旧标题「要关闭这个窗口吗？」已按原型随状态切换")
        # CW04：三卡正文逐字照原型 Main:1715-1718（数字由 JS 按 BE1 载荷填；
        # 静态缺省写不带数字/手机在线的运行态，空闲态两卡在控制器里切换）
        for needle in ("窗口缩到任务栏，计划和手机访问都照常。",
                       "窗口不见了，工具在后台继续运行。从右下角托盘图标或手机页叫回来。",
                       "报名计划会停止，还没提交的场次不会再报名。手机也会断开。"):
            self.assertIn(needle, self.html)
        for needle in ("窗口缩到任务栏，点一下就回来。",
                       "登录状态会保留，下次打开不用重新登录。"):
            self.assertIn(needle, self.controller)
        # CW05：隐藏禁用原因照原型 Main:1715（禁用分支）
        self.assertIn("现在叫不回来：托盘图标没建起来，手机也没连着，所以不能隐藏。", self.html)
        # CW08：确认步正文照原型 Main:1722（数字段由 closeWaitPhrase 拼，缺字段退回「场次」）
        for needle in ("不会再报名。已经成功的报名不受影响。", "closeWaitPhrase"):
            self.assertIn(needle, self.controller)
        # CW03：利害清单两行结构的行文由 JS 拼，拼接式与回退句都在控制器里
        self.assertIn(" 场等开放，最近一批 ", self.controller)
        self.assertIn("手机已连接", self.controller)

    def test_controller_routes_the_four_outcomes(self):
        self.assertIn("request_window_close", self.controller)
        self.assertIn("remember_", self.controller)
        self.assertIn('submitWindowClose("hide")', self.controller)
        self.assertIn("window.close_action", (LOCAL / "app.py").read_text(encoding="utf-8"))
        # 隐藏走后端 window.hide()（pywebview 原生）；前端不自己调，也不引托盘库
        self.assertNotIn("pystray", self.controller)
        self.assertNotIn(".hide()", self.controller)

    def test_hide_runs_in_background_and_can_be_woken_from_the_phone(self):
        """隐藏＝进程继续跑，所以必须有唤回入口：托盘 + 手机页各一条。"""
        tray = (LOCAL / "infrastructure" / "tray_icon.py").read_text(encoding="utf-8")
        app_py = (LOCAL / "app.py").read_text(encoding="utf-8")
        self.assertIn("NotifyIcon", tray)
        self.assertIn("def start(self) -> bool", tray, "托盘建不起来要能优雅失败")
        # 消息循环不能挂在窗体上：Application.Run(form) 会把宿主窗体显示出来，
        # 用户点「隐藏到后台」时就会多出一个空白小窗。
        self.assertIn("ApplicationContext", tray)
        self.assertNotIn("Application.Run(form)", tray)
        self.assertIn("def hide_window(self) -> dict", app_py)
        self.assertIn("def show_window(self) -> dict", app_py)
        self.assertIn("def _ensure_tray(self) -> bool", app_py)
        self.assertIn('"show_window": set()',
                      (LOCAL / "domain" / "phone_rules.py").read_text(encoding="utf-8"))
        mobile = (LOCAL / "ui" / "m" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="btn-show-window"', mobile)
        self.assertIn("显示电脑窗口", mobile)

    def test_minimize_takes_focus_when_the_dialog_opens(self):
        """焦点落在「最小化」：三个出口里最轻、随时能回来的那一个。"""
        start = self.html.index('id="btn-close-minimize"')
        self.assertIn("autofocus", self.html[start:].split("</button>")[0],
                      "静态标记也要有：showModal 时内核先把焦点放到最小化")
        self.assertIn("focusSafestClose", self.controller)
        self.assertIn('getElementById("btn-close-minimize")', self.controller)
        # 元素或 focus 缺失时必须静默跳过：焦点问题不该把关窗流程卡住
        self.assertIn('typeof target.focus !== "function"', self.controller)
        self.assertIn("try {", self.controller)

    def test_hide_needs_a_live_way_back(self):
        """托盘和手机都没连着时拒绝隐藏：否则窗口一藏就再也叫不回来。"""
        app_py = (LOCAL / "app.py").read_text(encoding="utf-8")
        self.assertIn("has_live_session", app_py)
        self.assertIn("hide_unavailable", app_py)
        phone = (LOCAL / "application" / "phone_service.py").read_text(encoding="utf-8")
        self.assertIn("def has_live_session(self) -> bool:", phone)
        # 判断只读会话表，且「有没有」与 token/csrf 无关
        self.assertIn("session_alive(session, now)", phone)
        self.assertNotIn("has_live_session", self.controller,
                         "能不能唤回由后端判定，界面不自己猜")


class WorkbenchUiContractTests(unittest.TestCase):
    """新工作台的行为与静态契约：横幅、开始前提醒、运行中修改、空态、用词、更新、关窗、条款门、演示控件。"""

    def test_banner_shows_only_the_highest_priority_one(self):
        """横幅只留一条，优先级：组件缺失 > 条款未同意 > 断网 > 刚睡眠过 > 登录问题 > 北京时间问题。"""
        res = run_js(WB_STAMP_JS + r"""
const realClock = clockUiState;
const banner = () => {
  paintBanners();
  const h = document.querySelector("#banners").innerHTML;
  return { count: (h.match(/class="banner"/g) || []).length, text: h.replace(/<[^>]*>/g, "") };
};
S.runtime.error = "worker_missing";
S.terms.version = "v1"; S.terms.acceptedVersion = ""; S.terms.declined = true;
S.online = false;
S.sleepGap = 300000;
S.login.view = { state: "bad" };
clockUiState = () => "unavailable";
const seen = [banner()];
S.runtime.error = null; seen.push(banner());
S.terms.acceptedVersion = "v1"; seen.push(banner());
S.online = true; seen.push(banner());
S.sleepGap = 0; seen.push(banner());
S.login.view = { state: "unknown" }; seen.push(banner());
S.login.view = { state: "ok" }; seen.push(banner());
clockUiState = realClock; seen.push(banner());
out.push(seen);
""")
        seen = res[0]
        # 20261108-main-window LS21：睡眠横幅标题照原型改为「电脑刚才睡眠了约 N 分钟」，层级不变
        expected = ["程序组件缺失", "还没有同意使用条款", "网络断开了", "电脑刚才睡眠了约",
                    "登录已失效", "暂时无法确认登录状态", "北京时间还没校准"]
        for got, title in zip(seen, expected):
            self.assertEqual(got["count"], 1, "同一时刻只显示一条横幅（%s）" % title)
            self.assertIn(title, got["text"], "这一层应该显示「%s」" % title)
        self.assertEqual(seen[-1]["count"], 0, "都正常时不显示横幅")

    def test_five_pre_start_warnings_only_remind(self):
        """开始前提醒五条（断网 / 沿用上次校准 / 等 1 小时以上没开全自动登录 / 直到截止缺截止时间 / 24 小时以后），只提醒不拦。"""
        res = run_js(WB_STAMP_JS + r"""
const realClock = clockUiState;
seed([
  { id: "a1", name: "半小时后", sign_start: stamp(now + 1800), sign_end: stamp(now + 7200) },
  { id: "a2", name: "两小时后没截止", sign_start: stamp(now + 7200) },
  { id: "a3", name: "两天后", sign_start: stamp(now + 2 * 86400), sign_end: stamp(now + 2 * 86400 + 3600) },
]);
const texts = () => preStartWarnings().map((w) => w.text);
/* 原型 loginWarn 只在登录有效时提醒（draft-panel G）：先记下没登录时的样子，再把登录置为有效 */
S.selected = new Set(["a2"]);
const waitNoLogin = preStartWarnings();
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
paintLogin();
S.online = true;
S.retryPolicy = { retry_for_s: 120, max_attempts: 0 };
S.selected = new Set(["a1"]);
const quiet = texts();
S.online = false; const offline = texts(); S.online = true;
clockUiState = () => "holdover"; const hold = texts(); clockUiState = realClock;
S.selected = new Set(["a2"]);
const wait = preStartWarnings();
S.retryPolicy.retry_for_s = 0; const noEnd = texts(); S.retryPolicy.retry_for_s = 120;
S.selected = new Set(["a1", "a3"]); const day = texts();
const cred = { credential: { saved: true, ocr_ready: true, paused: false } };
S.advanced = cred;
if (window.PhonePanel && PhonePanel.state) PhonePanel.state.advanced = cred;
S.selected = new Set(["a2"]); const fullAuto = texts();
/* 有提醒时主按钮改叫「仍然开始报名计划」 */
S.advanced = {}; if (window.PhonePanel && PhonePanel.state) PhonePanel.state.advanced = {};
paintChecks(); updateControls();
const label = document.querySelector("#btn-plan").textContent;
S.selected = new Set(["a1"]); paintChecks(); updateControls();
const quietLabel = document.querySelector("#btn-plan").textContent;
out.push({ quiet, offline, hold, wait, noEnd, day, fullAuto, label, quietLabel, waitNoLogin });
""")
        r = res[0]
        self.assertEqual(r["quiet"], [], "半小时内开放、有截止、在线：不提醒")
        # 计划栏 1:1（draft-panel G）：五条逐字照原型 preWarn / loginWarn
        self.assertIn("现在连不上网。到开放时间还没恢复，就提交不出去。", r["offline"], "第 1 条：断网")
        self.assertTrue(any(t.startswith("北京时间在用上次的校准结果") and t.endswith("工具正在自动重试校准。")
                            for t in r["hold"]), "第 2 条：沿用上次校准")
        wait = [w for w in r["wait"] if "中途登录失效" in w["text"]]
        self.assertEqual(len(wait), 1, "第 3 条：等 1 小时以上又没开全自动登录")
        self.assertIn("自动登录没开", wait[0]["text"])
        self.assertIn("开放前 100 秒内失效，那场就结束。", wait[0]["text"])
        self.assertTrue(wait[0]["text"].startswith("要等到"), wait[0]["text"])
        self.assertEqual(wait[0]["act"], "go-cred", "没保存账号就带「去保存」")
        self.assertFalse(any("中途登录失效" in w["text"] for w in r["waitNoLogin"]),
                         "原型 loginWarn：登录不是有效时不提第 3 条（由「还差一步」说）")
        self.assertTrue(any("“直到报名截止”对它只会尝试 2 分钟。" in t for t in r["noEnd"]),
                        "第 4 条：直到截止但缺截止时间")
        self.assertTrue(any(t.startswith("「两小时后没截止」没给报名截止时间") for t in r["noEnd"]))
        # 计划 20261108 fe-plan：原型这句在窄档会把「这段时间」拆成两行，原型用 U+2060 把「时」「间」连住，
        # 界面同句照抄；这里只是断言里补上同一个不可见连接符，句子本身没变。
        self.assertIn("有场次在 24 小时以后才开放，计划要一直运行到那时。这段时⁠间电⁠脑不能关机或睡眠。", r["day"],
                      "第 5 条：最晚一场 24 小时以后（按最晚一场算）")
        self.assertFalse(any("中途登录失效" in t for t in r["fullAuto"]), "自动登录开全了就不提第 3 条")
        self.assertEqual(r["label"], "仍然开始报名计划", "有提醒时按钮改名，但不禁用")
        self.assertEqual(r["quietLabel"], "开始报名计划")

    def test_modify_plan_disabled_inside_the_100_second_window(self):
        """运行中「修改计划」：有场次在提交或离开放不到 100 秒（含 100 秒）就禁用并写原因；正在停止也禁用。"""
        res = run_js(WB_STAMP_JS + r"""
const calls = [];
window.pywebview = { api: { stop_plan: () => { calls.push("stop_plan"); return Promise.resolve({ ok: true }); } } };
S.busy = true;
S.plan = { id: "p1", status: "running", tasks: new Map(), source: "" };
const put = (status, openIn) => {
  S.plan.tasks.clear();
  S.plan.tasks.set("t1", { task_id: "t1", activity_id: "a1", status: status, sign_start: stamp(now + openIn) });
};
const look = () => { paintRunPanel(); return { disabled: document.querySelector("#btn-modify").disabled,
  why: document.querySelector("#modify-why").textContent }; };
put("waiting", 101); const edge = look();
put("waiting", 100); const at100 = look();
put("submitting", 900); const submitting = look();
put("waiting", 900); S.stopping = true; const stopping = look(); S.stopping = false;
put("waiting", 90); modifyPlan(); const lateCalls = calls.slice();
put("waiting", 900); const far = look(); modifyPlan();
out.push({ edge, at100, submitting, stopping, far, lateCalls, calls, editing: S.editing });
""")
        r = res[0]
        self.assertFalse(r["edge"]["disabled"], "离开放 101 秒还来得及改")
        self.assertTrue(r["at100"]["disabled"], "离开放 100 秒（含）就不能改")
        # 计划栏 1:1（run-panel E）：原因逐字照原型 modifyInfo
        self.assertEqual(r["at100"]["why"], "有场次 100 秒内开放，工具已在准备，现在不能修改。", "禁用要写原因")
        self.assertEqual(r["submitting"]["why"], "有场次正在提交，现在不能修改。")
        self.assertTrue(r["submitting"]["disabled"], "有场次在提交不能改")
        self.assertTrue(r["stopping"]["disabled"], "正在停止不能改")
        self.assertEqual(r["lateCalls"], [], "来不及时点修改也不停计划")
        self.assertEqual(r["far"]["why"], "还没提交的场次可以放回草稿，改完要重新开始。", "能改时说清楚修改会先停下")
        self.assertEqual(r["calls"], ["stop_plan"], "修改＝先停下计划")
        # 计划栏 1:1（draft-panel C）：进入修改时记下已结束的场次数（原型 modifyS 的 doneN），这里没有已结束的
        self.assertEqual(r["editing"], {"ids": ["a1"], "doneN": 0}, "还没提交的场次带回草稿")

    def test_late_window_is_the_same_100_seconds_front_and_back(self):
        """运行中重新登录的「来不及」窗口：前端 planLate 与后端 login_rules 同一个 100 秒。"""
        backend = (LOCAL / "domain" / "login_rules.py").read_text(encoding="utf-8")
        front = read("ui/views/plan-panel.js")
        import re
        back_value = re.search(r"^LATE_WINDOW_S = (\d+)$", backend, re.M)
        front_value = re.search(r"^const LATE_WINDOW_S = (\d+);$", front, re.M)
        self.assertIsNotNone(back_value, "后端要有 LATE_WINDOW_S 常量")
        self.assertIsNotNone(front_value, "前端要有 LATE_WINDOW_S 常量")
        self.assertEqual(back_value.group(1), "100")
        self.assertEqual(front_value.group(1), back_value.group(1), "前后端来不及窗口必须同一个数")
        late = front[front.index("function planLate("):front.index("function earliestWaitingOpen")]
        self.assertIn("open - now <= LATE_WINDOW_S", late, "含 100 秒整（与后端 <= 一致）")
        self.assertIn('st === "submitting"', late, "有场次在提交也算来不及")

    def test_full_is_counted_apart_and_never_reselected(self):
        """结果页：名额已满单列、中性色，不放回「重新选择未成功的场次」；其他未成功的放回。"""
        res = run_js(WB_STAMP_JS + r"""
seed([
  { id: "f1", name: "满了", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
  { id: "x1", name: "没成功", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
  { id: "ok1", name: "报上了", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) },
]);
S.busy = false;
S.plan = { id: "p1", status: "completed", tasks: new Map([
  ["t1", { task_id: "t1", activity_id: "f1", status: "failed", stop_reason: "full" }],
  ["t2", { task_id: "t2", activity_id: "x1", status: "failed", stop_reason: "unknown_reply" }],
  ["t3", { task_id: "t3", activity_id: "ok1", status: "success" }],
]) };
const ids = reselectableIds();
const counts = resultCounts();
reselectFailed();
out.push({ ids, counts, selected: Array.from(S.selected) });
""")
        r = res[0]
        self.assertEqual(r["ids"], ["x1"], "名额已满、已成功都不放回")
        # 计划栏 1:1（result-panel C）：大数字五类，多了「已取消」一格
        # 计划 20261108 fe-plan（LS22 / PB15）：计数对象多了「错过了」一类 missed；这里没有睡眠窗口，恒为 0，其余数不变
        self.assertEqual(r["counts"], {"ok": 1, "full": 1, "pending": 0, "bad": 1, "missed": 0, "canceled": 0},
                         "名额已满单列，不算未成功")
        self.assertEqual(r["selected"], ["x1"])
        labels = read("ui/state/labels.js")
        self.assertIn('if (stop === "full") return "is-neutral";', labels, "名额已满用中性色，不是失败红")

    def test_four_empty_states_do_not_mix(self):
        """空态四种：筛选后为空 / 学校返回 0 场 / 列表没加载（写原因）/ 组件缺失（不放第二个按钮）。"""
        res = run_js(WB_STAMP_JS + r"""
const snap = () => { render(); const a = document.querySelector("#empty-action");
  return { title: document.querySelector("#empty-title").textContent,
    text: document.querySelector("#empty-text").textContent,
    label: a.textContent, act: a.dataset.action, hidden: a.hidden }; };
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 3600) }]);
S.listState = "ready";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.filter.q = "不会命中的关键词";
const filtered = snap();
S.filter.q = "";
seed([]);
const zero = snap();
S.listState = "idle";
S.terms.version = "v1"; S.terms.acceptedVersion = ""; S.terms.declined = true;
const terms = snap();
S.terms.acceptedVersion = "v1";
S.runtime.error = "worker_missing";
const comp = snap();
out.push({ filtered, zero, terms, comp });
""")
        r = res[0]
        self.assertEqual(r["filtered"]["title"], "没有符合筛选的活动")
        self.assertEqual(r["filtered"]["act"], "clear-filters", "只有筛选为空给「清除筛选」")
        self.assertEqual(r["zero"]["title"], "学校当前没有返回活动")
        self.assertIn("这不是登录问题", r["zero"]["text"])
        self.assertEqual(r["zero"]["act"], "refresh")
        self.assertIn("同意使用条款", r["terms"]["text"], "没加载要写原因")
        self.assertEqual(r["terms"]["act"], "terms-open", "原因对应的那一个动作")
        # 20261108-main-window LS16：标题照原型改为「活动列表没加载」
        self.assertEqual(r["comp"]["title"], "活动列表没加载")
        self.assertTrue(r["comp"]["hidden"], "组件缺失不放第二个按钮，看顶部横幅")
        titles = {r[k]["title"] for k in ("filtered", "zero", "terms", "comp")}
        self.assertEqual(len(titles), 4, "四种空态标题各不相同，不能混用")

    def test_vocabulary_table_outside_terms_text(self):
        """用词表：local/ui 不出现「重登」「刷新状态」「直发」「约剩」（条款正文除外，它须与 docs 一字不差）。"""
        ui = LOCAL / "ui"
        hits = []
        for path in sorted(ui.rglob("*")):
            if path.suffix not in (".js", ".html", ".css") or "led" in path.name:
                continue
            # 原断言按整行原文扫描：手机页注释（解释「重登 sheet」指哪张 sheet 等）
            # 被当成用词残留；注释不是界面文案，扫描改在剥注释后的文本上做，
            # 行号按原行保留，对真实文案的检查强度不变
            stripped = strip_ui_comments(path.read_text(encoding="utf-8"), path.suffix)
            for no, line in enumerate(stripped.splitlines(), 1):
                if '<div class="terms-section">' in line:
                    continue   # 内嵌条款正文归条款文档管，用词以 docs 为准
                for word in ("重登", "刷新状态", "直发", "约剩"):
                    if word in line:
                        hits.append("%s:%d %s" % (path.relative_to(ui), no, word))
        self.assertEqual(hits, [], "界面用词表有残留")

    def test_update_buttons_sit_in_the_title_row_with_a_guard(self):
        """更新按钮在「版本与更新」标题行右侧；新出现的推进按钮先停 0.8 秒防误点。"""
        html = read("ui/index.html")
        row = html[html.index('<div class="help-tool-row set-update">'):]
        row = row[:row.index('<div class="help-tool-row">')]
        self.assertIn("版本与更新", row)
        actions = row[row.index('class="help-actions update-actions"'):]
        for needle in ("btn-update-install", "btn-update-confirm", "btn-update-launch",
                       "btn-update-check", "btn-update-close"):
            self.assertIn('id="%s"' % needle, actions, "#%s 要在标题行右侧的按钮区" % needle)
        self.assertIn("const UPDATE_GUARD_MS = 800;", read("ui/views/update.js"))
        res = run_js(r"""
S.update.state = "available";
S.update.result = { latest_version: "9.9.9", installer: { url: "https://example.invalid/x.exe" } };
paintUpdate();
const fresh = document.querySelector("#btn-update-install").disabled;
const checkHidden = document.querySelector("#btn-update-check").hidden;
S.update.guardUntil = Date.now() - 1;
paintUpdate();
const later = document.querySelector("#btn-update-install").disabled;
S.busy = true; S.update.state = "ready_to_install"; paintUpdate();
out.push({ fresh, later, checkHidden, launch: document.querySelector("#btn-update-launch").textContent });
""")
        r = res[0]
        self.assertTrue(r["fresh"], "刚出现的「下载并安装」先停 0.8 秒")
        self.assertFalse(r["later"], "过了 0.8 秒就能点")
        self.assertTrue(r["checkHidden"], "每步只留一个推进动作：流程按钮出现时收起「检查更新」")
        self.assertEqual(r["launch"], "仍然启动安装程序", "计划运行中安装要明说会中断")

    def test_close_dialog_three_exits(self):
        """关窗三出口（CW02–CW08、CW12）：利害清单两行、最小化默认焦点、计划运行时标推荐、
        退出要再确认（确认步换标题正文与脚部两钮）、Esc 回选择步且不出全局链、
        托盘不可用且手机没连时不能隐藏并写原因。"""
        res = run_js(r"""
/* 替身没有 getElementById，window.js 加载时会跳过接线：补上垫片后手动接一次（真实 DOM 加载时自动接） */
document.getElementById = (id) => document.querySelector("#" + id);
wireWindowClose();
const sent = [];
window.pywebview = { api: { request_window_close: (a) => { sent.push(a); return Promise.resolve({ ok: true }); } } };
const dlg = document.querySelector("#dlg-close");
const escKeys = dlg.listeners.keydown;
openWindowCloseDialog({ plan_running: true, phone_running: true, phone_live: false, tray_ok: false,
                        waiting_count: 2, next_batch_at: "14:30:00" });
const running = {
  title: document.querySelector("#dlg-close-title").textContent,
  sub: document.querySelector("#dlg-close-body").textContent,
  stakes: document.querySelector("#dlg-close-running").textContent,
  stakeRows: (document.querySelector("#dlg-close-running").innerHTML.match(/<li/g) || []).length,
  stakesHidden: document.querySelector("#dlg-close-running").hidden,
  hideDisabled: document.querySelector("#btn-close-hide").disabled,
  why: document.querySelector("#close-hide-why").textContent,
  rec: document.querySelector("#close-rec").hidden,
  minText: document.querySelector("#close-min-text").textContent,
  exitText: document.querySelector("#close-exit-text").textContent,
  focus: document.activeElement && document.activeElement.__sel,
};
document.querySelector("#btn-close-exit").click();
const confirmStep = {
  title: document.querySelector("#dlg-close-title").textContent,
  sub: document.querySelector("#dlg-close-body").textContent,
  body: document.querySelector("#dlg-close-confirm").textContent,
  confirmVisible: !document.querySelector("#dlg-close-confirm").hidden,
  choicesHidden: document.querySelector("#dlg-close-choices").hidden,
  rememberHidden: document.querySelector("#dlg-close-remember-row").hidden,
  cancelHidden: document.querySelector("#btn-close-cancel").hidden,
  backVisible: !document.querySelector("#btn-close-exit-back").hidden,
  yesVisible: !document.querySelector("#btn-close-exit-confirm").hidden,
  focus: document.activeElement && document.activeElement.__sel,
  sent: sent.slice(),
};
/* 确认步 Esc：回选择步、不发动作（CW06，原型 Main:2446） */
const escEvent = { key: "Escape", stopped: false, prevented: false,
                   stopPropagation() { this.stopped = true; }, preventDefault() { this.prevented = true; } };
escKeys[0](escEvent);
const backToPick = {
  stopped: escEvent.stopped, prevented: escEvent.prevented,
  title: document.querySelector("#dlg-close-title").textContent,
  confirmVisible: !document.querySelector("#dlg-close-confirm").hidden,
  choicesHidden: document.querySelector("#dlg-close-choices").hidden,
  focus: document.activeElement && document.activeElement.__sel,
  sent: sent.slice(),
};
/* 选择步 Esc：只隔离全局链（stopPropagation），关闭交给原生 cancel，等价「先不关」 */
const escEvent2 = { key: "Escape", stopped: false, prevented: false,
                    stopPropagation() { this.stopped = true; }, preventDefault() { this.prevented = true; } };
escKeys[0](escEvent2);
const pickEsc = { stopped: escEvent2.stopped, prevented: escEvent2.prevented, sent: sent.slice() };
/* 确认后真的退出：重新进确认步再点「停止计划并退出」 */
document.querySelector("#btn-close-exit").click();
document.querySelector("#btn-close-exit-confirm").click();
const afterYes = { sent: sent.slice() };
/* 空闲：手机连着就能隐藏；无利害清单、无推荐；卡文换 CW12 那套 */
openWindowCloseDialog({ plan_running: false, phone_running: true, phone_live: true, tray_ok: false });
const idle = {
  title: document.querySelector("#dlg-close-title").textContent,
  stakesHidden: document.querySelector("#dlg-close-running").hidden,
  hideDisabled: document.querySelector("#btn-close-hide").disabled,
  rec: document.querySelector("#close-rec").hidden,
  minText: document.querySelector("#close-min-text").textContent,
  exitText: document.querySelector("#close-exit-text").textContent,
};
/* BE1 载荷缺字段（旧后端）：利害行整行退回「报名计划正在运行」，卡文与确认段不带数字 */
openWindowCloseDialog({ plan_running: true, phone_running: true, phone_live: true, tray_ok: true });
const legacy = {
  stakes: document.querySelector("#dlg-close-running").textContent,
  exitText: document.querySelector("#close-exit-text").textContent,
  hideText: document.querySelector("#close-hide-text").textContent,
};
out.push({ running, confirmStep, backToPick, pickEsc, afterYes, idle, legacy });
""")
        r = res[0]
        running = r["running"]
        self.assertEqual(running["title"], "报名计划还在运行", "CW02 运行态标题")
        self.assertEqual(running["sub"], "最小化或隐藏都不影响计划，退出会停止它。")
        self.assertIn("2 场等开放，最近一批 14:30:00", running["stakes"],
                      "CW03 利害行写 BE1 的真实数字与时刻")
        self.assertIn("手机访问开着", running["stakes"])
        self.assertEqual(running["stakeRows"], 2, "CW03 利害清单两行（计划＋手机）")
        self.assertFalse(running["stakesHidden"])
        self.assertTrue(running["hideDisabled"], "托盘不可用且手机没连：不能隐藏")
        self.assertIn("叫不回来", running["why"], "不能隐藏要写原因（CW05）")
        self.assertFalse(running["rec"], "计划运行时标「推荐」")
        self.assertEqual(running["minText"], "窗口缩到任务栏，计划和手机访问都照常。")
        self.assertEqual(running["exitText"],
                         "报名计划会停止，还没提交的 2 场不会再报名。手机也会断开。")
        self.assertEqual(running["focus"], "#btn-close-minimize", "最小化默认获得焦点")
        confirm = r["confirmStep"]
        self.assertEqual(confirm["title"], "退出会停止报名计划", "确认步标题照原型 Main:1724")
        self.assertEqual(confirm["sub"], "确定要退出吗？")
        self.assertEqual(confirm["body"],
                         "还没提交的 2 场不会再报名。已经成功的报名不受影响。", "CW08 确认正文")
        self.assertTrue(confirm["confirmVisible"])
        self.assertTrue(confirm["choicesHidden"])
        self.assertTrue(confirm["rememberHidden"], "CW07 确认步收起勾选行")
        self.assertTrue(confirm["cancelHidden"])
        self.assertTrue(confirm["backVisible"])
        self.assertTrue(confirm["yesVisible"])
        self.assertEqual(confirm["focus"], "#btn-close-exit-back", "确认步焦点落「返回」")
        self.assertEqual(confirm["sent"], [], "确认之前不发退出")
        back = r["backToPick"]
        self.assertTrue(back["stopped"], "Esc 在 dialog 层 stopPropagation，不落全局链（CW06）")
        self.assertTrue(back["prevented"], "确认步 Esc 拦下原生关闭，改回选择步")
        self.assertEqual(back["title"], "报名计划还在运行", "Esc 回选择步后标题还原")
        self.assertFalse(back["confirmVisible"])
        self.assertFalse(back["choicesHidden"])
        self.assertEqual(back["focus"], "#btn-close-minimize")
        self.assertEqual(back["sent"], [], "Esc 回选择步不发动作")
        self.assertTrue(r["pickEsc"]["stopped"])
        self.assertFalse(r["pickEsc"]["prevented"],
                         "选择步 Esc 交给 <dialog> 原生 cancel 静默关闭（等价「先不关」）")
        self.assertEqual(r["pickEsc"]["sent"], [])
        self.assertEqual(r["afterYes"]["sent"], ["exit"], "确认后才真的退出")
        idle = r["idle"]
        self.assertEqual(idle["title"], "要关闭窗口吗？", "CW12 空闲标题")
        self.assertTrue(idle["stakesHidden"], "空闲不渲染利害清单（CW11 保持）")
        self.assertFalse(idle["hideDisabled"], "手机连着就能隐藏（能从手机叫回来）")
        self.assertTrue(idle["rec"], "没有计划时不标推荐")
        self.assertEqual(idle["minText"], "窗口缩到任务栏，点一下就回来。")
        self.assertEqual(idle["exitText"], "登录状态会保留，下次打开不用重新登录。")
        legacy = r["legacy"]
        self.assertIn("报名计划正在运行", legacy["stakes"], "BE1 字段缺失整行退回现有文案")
        self.assertNotIn("等开放", legacy["stakes"])
        self.assertEqual(legacy["exitText"],
                         "报名计划会停止，还没提交的场次不会再报名。手机也会断开。",
                         "waiting_count 缺失时去掉数字")
        self.assertEqual(legacy["hideText"],
                         "窗口不见了，工具在后台继续运行。从右下角托盘图标或手机页叫回来。")

    def test_terms_unaccepted_disables_the_school_actions(self):
        """条款未同意停用清单：登录、登录检查、刷新、勾选、开始、重新登录对话框、自动引导；列表只读并标可能过时。"""
        res = run_js(WB_STAMP_JS + r"""
const calls = [];
window.pywebview = { api: new Proxy({}, { get: (t, name) => (...args) => { calls.push(String(name)); return new Promise(() => {}); } }) };
seed([{ id: "a1", name: "甲活动", sign_start: stamp(now + 3600), sign_end: stamp(now + 7200) }]);
S.listState = "ready"; S.listAtMono = performance.now();
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
S.terms.version = "v1"; S.terms.acceptedVersion = ""; S.terms.declined = true;
S.selected = new Set(["a1"]);
render(); paintLogin(); updateControls(); renderLoginCard();
S.tour.autoPending = true; maybeStartTour();
openRelogin(); doLogin(); startPlan(); refresh(false);
out.push({
  login: document.querySelector("#btn-login").disabled,
  refresh: document.querySelector("#btn-refresh").disabled,
  plan: document.querySelector("#btn-plan").disabled,
  check: document.querySelector("#btn-login-check").disabled,
  row: document.querySelector(".row-check").disabled,
  pill: document.querySelector("#pill-text").textContent,
  fresh: document.querySelector("#fresh").textContent,
  relogin: document.querySelector("#dlg-relogin").open,
  tour: S.tour.open,
  calls,
});
""")
        r = res[0]
        for key in ("login", "refresh", "plan", "check", "row"):
            self.assertTrue(r[key], "条款未同意时 %s 必须停用" % key)
        self.assertEqual(r["pill"], "等同意条款", "胶囊明说在等条款，不报旧结论")
        self.assertIn("可能过时", r["fresh"], "列表只读停在上次结果，要标可能过时")
        self.assertFalse(r["relogin"], "重新登录对话框不开")
        self.assertFalse(r["tour"], "不自动引导")
        self.assertEqual(r["calls"], [], "不发任何后端动作（后端也会拦）")

    def test_prototype_demo_controls_are_not_shipped(self):
        """原型里只为演示存在的控件（状态对照表「实现时删除」一节）不进产品，也不变成隐藏功能。"""
        ui = LOCAL / "ui"
        banned = ("原型演示", "演示：", "时间快进", "演示时间已复位", "模拟学校", "模拟系统",
                  "模拟连不上电脑", "ph-demo", "下一次检查结果")
        hits = []
        for path in sorted(ui.rglob("*")):
            if path.suffix not in (".js", ".html", ".css"):
                continue
            # 原断言对整文件原文匹配：手机页注释里「原型 demo-tip 的「演示：」行不进产品」
            # 这类解释为什么不搬演示控件的说明被当成演示控件本身；注释不是控件，
            # 扫描改在剥注释后的文本上做，对真实控件与文案的检查强度不变
            text = strip_ui_comments(path.read_text(encoding="utf-8"), path.suffix)
            hits.extend("%s：%s" % (path.relative_to(ui), word) for word in banned if word in text)
        self.assertEqual(hits, [], "演示控件不得进产品")


class MigrationBannerTests(unittest.TestCase):
    """MG01/MG02（原型 Main:2146/2147、1182/1183）：旧数据迁移横幅与运行记录。

    bootstrap.migration = {moved, login_failed} 或 null；成功与失败互斥，
    横幅只显示最高一条：组件缺失/条款/登录失效等既有横幅都优先于迁移横幅。
    """

    def test_banner_copy_and_mutual_exclusion(self):
        """MG01 成功照原型 .banner.note；MG02 失败走警示档；两态互斥。"""
        res = run_js(r"""
const banner = () => {
  paintBanners();
  const h = document.querySelector("#banners").innerHTML;
  return { html: h, text: h.replace(/<[^>]*>/g, "") };
};
S.migration = { moved: 3, login_failed: false };
const ok = banner();
S.migration = { moved: 0, login_failed: true };
const fail = banner();
out.push({ ok, fail });
""")
        ok, fail = res[0]["ok"], res[0]["fail"]
        self.assertIn('data-tone="note"', ok["html"], "MG01 照原型 .banner.note")
        self.assertIn("已把旧版本的数据搬到新位置。", ok["text"])
        self.assertIn("登录、设置和运行记录都在，不用重新登录。位置在设置的“本机数据”里。",
                      ok["text"], "MG01 正文逐字照原型（含全角引号）")
        self.assertIn('data-act="migrated-ok"', ok["html"])
        self.assertIn("知道了", ok["text"])
        self.assertNotIn("旧版本的登录信息没能搬过来", ok["text"], "成功时不出失败横幅")
        self.assertIn('data-tone="warn"', fail["html"], "MG02 是警示横幅")
        self.assertIn("旧版本的登录信息没能搬过来。", fail["text"])
        self.assertIn("设置和运行记录已经搬好；重新登录一次就行，旧文件还留在原来的位置。",
                      fail["text"], "MG02 正文逐字照原型")
        self.assertIn('data-act="login"', fail["html"])
        self.assertIn("登录", fail["text"])
        self.assertNotIn("已把旧版本的数据搬到新位置", fail["text"], "失败时不出成功横幅")

    def test_banner_copy_for_both_and_other_failures(self):
        """迁移横幅另两种结果：登录和其他都失败；只有其他失败（登录已搬好）。"""
        res = run_js(r"""
const banner = () => {
  paintBanners();
  const h = document.querySelector("#banners").innerHTML;
  return { html: h, text: h.replace(/<[^>]*>/g, "") };
};
S.migration = { moved: 0, login_failed: true, other_failed: true };
const both = banner();
S.migration = { moved: 2, login_failed: false, other_failed: true };
const other = banner();
S.migration = { moved: 0, login_failed: true, other_failed: false };
const loginOnly = banner();
out.push({ both, other, loginOnly });
""")
        both, other, login_only = res[0]["both"], res[0]["other"], res[0]["loginOnly"]
        wj = "\u2060"
        self.assertIn('data-tone="warn"', both["html"])
        self.assertIn("旧版本的数据没能搬过来。", both["text"])
        # 「调」「一下」之间有 U+2060，防止「下」单字掉行
        self.assertIn("旧文件还留在原来的位置；重新登录一次就行，设置要重新调" + wj + "一下。", both["text"])
        self.assertIn('data-act="login"', both["html"])
        self.assertNotIn("已经搬好", both["text"], "全失败时不能说搬好了")
        self.assertIn('data-tone="note"', other["html"])
        self.assertIn("旧版本的设置或运行记录没能搬过来。", other["text"])
        self.assertIn("登录信息已经搬好，不用重新登录；旧文件还留在原来的位置。", other["text"])
        self.assertIn('data-act="migrated-ok"', other["html"])
        self.assertNotIn('data-act="login"', other["html"], "登录已搬好，不再催登录")
        self.assertIn("设置和运行记录已经搬好", login_only["text"], "只登录失败保持原 MG02")

    def test_migration_banner_loses_to_login_and_runtime_banners(self):
        """迁移横幅低于组件缺失与登录失效：同一时刻仍只显示最高一条。"""
        res = run_js(r"""
const banner = () => { paintBanners(); return document.querySelector("#banners").innerHTML.replace(/<[^>]*>/g, ""); };
S.migration = { moved: 3, login_failed: false };
S.login.view = { state: "bad" };
const loginBad = banner();
S.runtime.error = "worker_missing";
const runtimeBad = banner();
S.runtime.error = null;
S.login.view = { state: "ok" };
const alone = banner();
out.push({ loginBad, runtimeBad, alone });
""")
        self.assertIn("登录已失效。", res[0]["loginBad"])
        self.assertNotIn("已把旧版本的数据搬到新位置", res[0]["loginBad"])
        self.assertIn("程序组件缺失", res[0]["runtimeBad"])
        self.assertNotIn("已把旧版本的数据搬到新位置", res[0]["runtimeBad"])
        self.assertIn("已把旧版本的数据搬到新位置", res[0]["alone"])

    def test_ack_hides_migration_banner_for_this_run_only(self):
        """MG01「知道了」只收起本次运行内的横幅：S 置位，不调落盘接口。"""
        res = run_js(r"""
const saved = [];
window.pywebview = { api: { save_prefs: (p) => { saved.push(p); return Promise.resolve({ ok: true }); } } };
S.migration = { moved: 3, login_failed: false };
paintBanners();
const before = document.querySelector("#banners").innerHTML;
document.querySelector("#banners").listeners.click.forEach((fn) => fn({
  target: { closest: (sel) => (sel === '[data-act="migrated-ok"]' ? {} : null) },
}));
const after = document.querySelector("#banners").innerHTML;
out.push({ before, after, dismissed: S.migrationDismissed, saved: saved.length });
""")
        case = res[0]
        self.assertIn("已把旧版本的数据搬到新位置", case["before"])
        self.assertEqual(case["after"], "", "知道了 只收起横幅")
        self.assertTrue(case["dismissed"], "收起状态进 S")
        self.assertEqual(case["saved"], 0, "收起状态不落盘")

    def test_failed_banner_login_button_opens_the_login_entry(self):
        """MG02「登录」复用登录失效横幅的同一入口（data-act=login → openLogin）。"""
        res = run_js(r"""
window.pywebview = { api: { login: () => new Promise(() => {}) } };
S.migration = { moved: 0, login_failed: true };
paintBanners();
document.querySelector("#banners").listeners.click.forEach((fn) => fn({
  target: { closest: (sel) => (sel === '[data-act="login"]' ? {} : null) },
}));
out.push({ open: !!(S.relogin && S.relogin.open),
           dialog: document.querySelector("#dlg-relogin").open });
""")
        self.assertTrue(res[0]["open"], "点「登录」必须进入登录流程")
        self.assertTrue(res[0]["dialog"], "登录对话框打开")

    def test_boot_writes_the_migration_run_log(self):
        """启动按 bootstrap.migration 写一条运行记录（原型 Main:1182/1183）；null 不写。"""
        res = run_js(r"""
const bootOnce = async (migration) => {
  window.pywebview = { api: {
    bootstrap: () => Promise.resolve({ demo: false,
      prefs: { welcome_seen: true, tour_version: 9999 },
      terms: { version: "2026-10-27", accepted_version: "2026-10-27",
               accepted_at: "2026-10-27 12:00:00" },
      migration }),
    save_prefs: () => Promise.resolve({ ok: true }),
    front_ready: () => Promise.resolve({ ok: true }),
    clock_snapshot: () => new Promise(() => {}),
    check: () => new Promise(() => {}),
    list_activities: () => new Promise(() => {}),
  } };
  S.recentLogs.length = 0;
  await boot();
  return { logs: S.recentLogs.slice(), migration: S.migration };
};
const success = await bootOnce({ moved: 3, login_failed: false });
const failed = await bootOnce({ moved: 0, login_failed: true });
const bothFailed = await bootOnce({ moved: 0, login_failed: true, other_failed: true });
const otherFailed = await bootOnce({ moved: 2, login_failed: false, other_failed: true });
const none = await bootOnce(null);
out.push({ success, failed, bothFailed, otherFailed, none });
""")
        success, failed, none = res[0]["success"], res[0]["failed"], res[0]["none"]
        self.assertIn("已把 3 个旧数据文件搬到新的数据目录", "\n".join(success["logs"]),
                      "成功日志用真实的 moved")
        self.assertIn("[!] 旧版本的登录信息没能搬过来，其他数据已搬好",
                      "\n".join(failed["logs"]), "失败日志逐字照原型")
        self.assertIn("[!] 旧版本的数据没能搬过来，旧文件还在原来的位置",
                      "\n".join(res[0]["bothFailed"]["logs"]))
        self.assertIn("[!] 旧版本的设置或运行记录没能搬过来，登录信息已搬好",
                      "\n".join(res[0]["otherFailed"]["logs"]))
        none_logs = "\n".join(none["logs"])
        self.assertNotIn("旧数据文件", none_logs, "migration 为 null 不写成功记录")
        self.assertNotIn("旧版本的登录信息", none_logs, "migration 为 null 不写失败记录")
        self.assertIsNone(none["migration"])


if __name__ == "__main__":
    unittest.main()
