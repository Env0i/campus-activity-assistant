#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""界面契约的静态测试：不开浏览器，直接用 UTF-8 读源文件核对。

覆盖签到/签退三态契约的关键约定，谁改丢了字段名、筛选语义或保存键，
这里的失败信息会直接指出缺哪一条，避免「界面悄悄退回两态」。

@author Author
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unittest
from pathlib import Path

LOCAL = Path(__file__).resolve().parents[1]
# 学校时间按 UTC+8 解释：夹具写学校时间也要按北京时间生成，
# 否则执行机的时区设置不是 +08:00 时整批偏移（C5）
BEIJING_TZ = dt.timezone(dt.timedelta(hours=8))


def read(rel: str) -> str:
    path = LOCAL / rel
    self_msg = "契约文件缺失：%s" % path
    assert path.exists(), self_msg
    if rel == "ui/app.js":
        # 结构重构后界面脚本按层拆成多文件：契约断言读「前端脚本联合源码」，
        # 加载序取自 index.html（led.js 是独立字库渲染器，不含业务契约文本）。
        return read_ui_scripts()
    return path.read_text(encoding="utf-8")


def read_ui_scripts() -> str:
    """index.html 加载序的全部业务脚本拼接（led.js 除外）。"""
    html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
    parts = []
    for src in re.findall(r'<script src="([^"]+)"></script>', html):
        if src == "led.js":
            continue
        parts.append((LOCAL / "ui" / src).read_text(encoding="utf-8"))
    return "\n".join(parts)


def strip_ui_comments(text: str, suffix: str) -> str:
    """逐行剥注释、保留行号，供禁词扫描只看真实文案。

    原扫描按整行原文匹配，把注释里「为什么不照搬某个原型演示控件」「重登 sheet
    指哪张 sheet」之类的设计说明也当成了残留（20261108-phone-1to1 的手机页注释
    按计划规范必须写明这类取舍）；禁词查的是界面文案，注释不是文案。
    .js 剥行尾 // 与跨行块注释；.html 另剥跨行 <!-- -->；.css 只剥块注释。
    字符串里的 //（如链接）会被一并剥掉，但禁词都是中文词，不会藏在链接后面。"""
    out = []
    in_block = ""          # "" | "js" | "html"
    for line in text.splitlines():
        kept = []
        i, n = 0, len(line)
        while i < n:
            if in_block == "js":
                end = line.find("*/", i)
                if end < 0:
                    i = n
                else:
                    in_block = ""
                    i = end + 2
            elif in_block == "html":
                end = line.find("-->", i)
                if end < 0:
                    i = n
                else:
                    in_block = ""
                    i = end + 3
            elif suffix == ".js" and line.startswith("//", i):
                break
            elif suffix in (".js", ".css") and line.startswith("/*", i):
                in_block = "js"
                i += 2
            elif suffix == ".html" and line.startswith("<!--", i):
                in_block = "html"
                i += 4
            else:
                kept.append(line[i])
                i += 1
        out.append("".join(kept))
    return "\n".join(out)


def help_dialog(html: str) -> str:
    """截取更多 dialog 元素本体（不含其前注释），供禁词等逐字断言使用。"""
    start = html.index('<dialog class="dlg dlg-help"')
    end = html.index("</dialog>", start) + len("</dialog>")
    return html[start:end]


# 帮助载荷隔离求值用的注入常量：证明 help() 用的是外部版本来源，不是写死值
HELP_TEST_VERSION = "9.9.9-test"
HELP_TEST_URL = "https://example.invalid/releases/latest"


def load_backend_help() -> dict:
    """只取 app.py 里 Api.help 这一个方法，在隔离命名空间里求值后调用。

    不 import app.py：它的顶层会 import webview 并经 runtime_paths 触碰数据根，
    与本计划「不安装依赖、不读真实登录文件」的边界冲突。这里用 ast 抽出
    FunctionDef，单独编译并注入 APP_VERSION / RELEASES_LATEST_URL，
    因此拿到的是**真实方法的返回值**，不是源码子串的推测。
    """
    import ast

    tree = ast.parse(read("app.py"))
    node = next(item for item in ast.walk(tree)
                if isinstance(item, ast.FunctionDef) and item.name == "help"
                and [arg.arg for arg in item.args.args][:1] == ["self"])
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"APP_VERSION": HELP_TEST_VERSION, "RELEASES_LATEST_URL": HELP_TEST_URL}
    exec(compile(module, "<Api.help>", "exec"), namespace)  # noqa: S102 - 只编译受控片段
    return namespace["help"](None)


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
        self.assertIn("refresh(true)", block,
                      "失败后必须静默复查登录态与列表（refresh(true)）")
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
        self.assertIn("check.disabled = S.busy || termsLocked() || !isEligibleForPlan(item)", js,
                      "复选框必须同时受忙、条款门与已截止三道限制")
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


# --------------------------------------------------------------------- 行为测试装置
# 在 node vm 里加载生产 app.js + 最小 DOM 桩，执行代码片段并取回断言输出。
# 不开浏览器、不装依赖：node 是项目既有工具链（服务器机器人同用）。
# 桩的边界：querySelector 按选择器缓存同一元素；focus 记录到 focused；
# document 只捕获 keydown 监听（__dispatchKey 合成按键）；定时器只记录不调度。

JS_HARNESS = r"""
"use strict";
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const uiDir = process.argv[2];
const snippetFile = process.argv[3];

const out = [];
const focused = [];
const els = new Map();
const keydownListeners = [];

function makeEl(sel) {
  const el = {
    __sel: sel, hidden: false, disabled: false, checked: false,
    value: "", textContent: "", title: "", returnValue: "",
    tagName: "DIV", open: false,
    dataset: {}, style: {}, _cls: new Set(),
    listeners: {},
  };
  /* innerHTML 与 textContent 按 DOM 语义联动：生产空态副行用带 nowrap span
   * 的 innerHTML 写文案（f541ba4 起就有），桩原来两者独立，读 textContent
   * 只能拿到空串。只联动赋值方向，读 innerHTML 仍返回原串。 */
  let _html = "";
  Object.defineProperty(el, "innerHTML", {
    get() { return _html; },
    set(v) { _html = String(v); el.textContent = _html.replace(/<[^>]*>/g, ""); },
  });
  el.classList = {
    toggle(c, on) {
      if (on === undefined) { if (el._cls.has(c)) el._cls.delete(c); else el._cls.add(c); }
      else if (on) el._cls.add(c); else el._cls.delete(c);
    },
    add(c) { el._cls.add(c); },
    remove(c) { el._cls.delete(c); },
    contains(c) { return el._cls.has(c); },
  };
  el.addEventListener = (type, fn) => { (el.listeners[type] = el.listeners[type] || []).push(fn); };
  el.removeEventListener = () => {};
  el.setAttribute = (k, v) => { el["attr_" + k] = v; };
  el.getAttribute = (k) => el["attr_" + k];
  el.focus = () => { sandbox.document.activeElement = el; focused.push(sel); };
  el.blur = () => { if (sandbox.document.activeElement === el) sandbox.document.activeElement = null; };
  el.select = () => {};
  el.click = () => (el.listeners.click || []).forEach((fn) => fn({ target: el, preventDefault() {} }));
  el.closest = () => null;
  el.contains = () => true;
  /* <dialog> 原生方法桩：设置/说明/停止确认的 open 状态靠它们翻转 */
  el.showModal = () => { el.open = true; };
  el.close = () => { el.open = false; };
  /* 子节点按真实语义记账：addLog 的「副作用有没有重复」需要数得出来 */
  el._children = [];
  el.appendChild = (child) => {
    el._children.push(child);
    el.childElementCount = el._children.length;
    return child;
  };
  el.removeChild = (child) => {
    const at = el._children.indexOf(child);
    if (at >= 0) el._children.splice(at, 1);
    el.childElementCount = el._children.length;
    return child;
  };
  el.insertBefore = (child) => { el._children.unshift(child); el.childElementCount = el._children.length; return child; };
  el.childElementCount = 0;
  el.childNodes = [];
  Object.defineProperty(el, "firstChild", {
    get() { return el._children[0] || null; },
  });
  el.getBoundingClientRect = () => ({ top: 100, left: 100, bottom: 140, right: 460, width: 360, height: 40 });
  el.getClientRects = () => [1];
  el.offsetWidth = 360;
  el.offsetHeight = 40;
  el.querySelector = (s) => el2(sel + " " + s);
  el.querySelectorAll = (s) => [el2(sel + " " + s)];
  return el;
}

function el2(sel) {
  if (!els.has(sel)) els.set(sel, makeEl(sel));
  return els.get(sel);
}

/* 单调钟独立于 Date：初值与 Date.now 同源（既有用例仍可用 Date.now 伪造
 * 「很久以前」的缓存时间），用例可再用 __advanceMono 单独推进经过时长，
 * 不会用 Date 假跳变同时推进 performance 导致红例失真。 */
const monoState = { base: Date.now(), offset: 0 };
const sandbox = {
  console, Date, Math, JSON, Promise, Object, Array, Number, String, Boolean, RegExp, Error,
  isNaN, parseInt, parseFloat,
  performance: { now: () => monoState.base + monoState.offset },
  __advanceMono: (ms) => { monoState.offset += Number(ms) || 0; },
  __monoValue: () => monoState.base + monoState.offset,
  innerWidth: 1120, innerHeight: 800,
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {},
  navigator: { onLine: true },
  /* window.addEventListener/removeEventListener：app.js 顶层注册 resize/online/offline 用 */
  addEventListener: () => {}, removeEventListener: () => {},
  out, focused, __els: els,
  requestAnimationFrame: () => 0,
  __dispatchKey: (ev) => {
    const e = Object.assign(
      { ctrlKey: false, shiftKey: false, altKey: false, defaultPrevented: false,
        target: { closest: () => null, tagName: "BODY", blur() {} } }, ev);
    e.preventDefault = () => { e.defaultPrevented = true; };
    keydownListeners.slice().forEach((fn) => fn(e));
    return e;
  },
  document: {
    hidden: false, activeElement: null,
    querySelector: (s) => el2(s),
    querySelectorAll: (s) => [el2(s)],
    createElement: (tag) => el2("<" + tag + ">"),
    createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
    addEventListener: (t, fn) => { if (t === "keydown") keydownListeners.push(fn); },
    removeEventListener: () => {},
  },
};
sandbox.window = sandbox;
sandbox.document.body = el2("body");
/* 停止确认弹层在 index.html 里默认 hidden；桩元素默认 hidden:false，不显式对齐的话
 * stopAskOpen() 在每个用例里都为真，键盘处理会被它截走 */
el2("#plan-stop-ask").hidden = true;
vm.createContext(sandbox);
/* 结构重构后界面按层拆成多脚本：按 index.html 的加载序喂进同一个沙箱，
 * 与真实 WebView 顺序一致。led.js 不进沙箱——字库渲染器只在真实 DOM 有
 * 意义，且历史行为就是 LED_UI 缺席时 ledSet 回退纯文本层。 */
const html = fs.readFileSync(path.join(uiDir, "index.html"), "utf8");
const scripts = Array.from(html.matchAll(/<script src="([^"]+)"><\/script>/g))
  .map((m) => m[1]).filter((src) => src !== "led.js");
for (const src of scripts) {
  vm.runInContext(fs.readFileSync(path.join(uiDir, src), "utf8"), sandbox, { filename: src });
}
/* 决策 012：node 桩显式注入可信假时钟（锚定 Date.now），不以 Date.now 作默认成功桩 */
vm.runInContext(
  "ingestBusinessClock({ schema: 1, owner_id: 'harness-clock', generation: 1," +
  " state: 'ready', epoch_s: Date.now() / 1000, tick_s: 0, sampled_tick_s: 0," +
  " uncertainty_s: 0, source: 'harness', age_s: 0, reason: '测试注入' });" +
  /* 用例把「业务现在」定到任意时刻：注入新一代快照，不再改 Date.now（墙钟不是权威） */
  "globalThis.setBusinessNow = (ms) => ingestBusinessClock({" +
  " schema: 1, owner_id: 'harness-clock'," +
  " generation: (S.businessClock.gen || 0) + 1, state: 'ready'," +
  " epoch_s: ms / 1000, tick_s: 0, sampled_tick_s: 0, uncertainty_s: 0," +
  " source: 'harness', age_s: 0, reason: '测试注入' });",
  sandbox, { filename: "clock-inject.js" });
/* 片段统一包成 async IIFE：顶层 await 可用（受控 Promise 次序），同步片段
 * 返回的 promise 立即完成，输出时序不变 */
const snippetSource = fs.readFileSync(snippetFile, "utf8");
const snippetResult = vm.runInContext(
  "(async () => {\n" + snippetSource + "\n})()",
  sandbox, { filename: "snippet.js" });
const finishHarness = () => process.stdout.write("__RESULT__" + JSON.stringify(out));
snippetResult.then(finishHarness, (err) => { process.stderr.write(String(err)); process.exit(1); });
"""


def run_js(snippet: str, env: dict | None = None):
    """在受控 JS 上下文里执行片段，返回 out 数组（list）。node 缺失时 skip。

    env 用于按用例注入 TZ（例如证明学校时间解析不随本机时区漂移）；
    默认不改进程环境。
    """
    import json
    import os
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("本机没有 node，无法运行 JS 行为测试")
    with tempfile.TemporaryDirectory() as name:
        harness = Path(name) / "harness.js"
        part = Path(name) / "snippet.js"
        harness.write_text(JS_HARNESS, encoding="utf-8")
        part.write_text(snippet, encoding="utf-8")
        child_env = dict(os.environ)
        child_env.update(env or {})
        res = subprocess.run([node, str(harness), str(LOCAL / "ui"), str(part)],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30, env=child_env)
        if res.returncode != 0:
            raise AssertionError("JS 行为测试崩溃：%s" % res.stderr[-800:])
        marker = res.stdout.rfind("__RESULT__")
        if marker < 0:
            raise AssertionError("JS 行为测试没有输出结果：%s" % res.stdout[-500:])
        return json.loads(res.stdout[marker + len("__RESULT__"):].strip() or "[]")


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




def settings_drawer(html):
    """设置抽屉（aside#settings）的完整片段。"""
    start = html.index('<aside class="draw" id="settings"')
    return html[start:html.index("</aside>", start)]


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


class TermsGateFailClosedTests(unittest.TestCase):
    """审阅返修：勾选门必须 fail-closed，三处口径不许各自漂移。"""

    def test_agree_checkbox_must_exist_in_html(self):
        """读不到复选框就按「没勾」处理，所以它一旦丢了必须红灯，不能静默放行。"""
        html = read("ui/index.html")
        self.assertIn('id="chk-terms-agree"', html, "条款勾选框被删了")
        self.assertIn('for="chk-terms-agree"', html, "勾选框的 label 也要指向它")
        self.assertIn("termsAgreeMissing()", read("ui/views/terms.js"),
                      "勾选门本身不能丢")

    def test_doc_meta_uses_the_same_terms_version(self):
        """文末元信息是第 4 份硬编码：必须与后端常量逐字一致，且落在 meta 片段里。"""
        version = re.search(r'^TERMS_VERSION\s*=\s*"([^"]+)"',
                            (LOCAL / "app.py").read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(version, "app.py 里找不到 TERMS_VERSION")
        html = read("ui/index.html")
        self.assertIn('id="terms-doc-meta"', html, "文末元信息块被删了")
        meta = html.split('id="terms-doc-meta"', 1)[1].split("</div>", 1)[0]
        self.assertIn(version.group(1), meta, "文末元信息里的版本号与后端常量不一致")

    def test_retry_options_match_store_choices(self):
        """index.html 的 option 集合必须等于 store.js 的 choices，避免第二套清单。"""
        html = read("ui/index.html")
        select = html.split('id="retry-for"', 1)[1].split("</select>", 1)[0]
        html_values = [int(v) for v in re.findall(r'<option value="(-?\d+)"', select)]
        store = read("ui/state/store.js")
        block = store.split("retryOptions:", 1)[1].split("choices:", 1)[1]
        block = block.split("]", 1)[0]
        store_values = [int(v) for v in re.findall(r"value:\s*(-?\d+)", block)]
        self.assertTrue(html_values, "没解析到 index.html 的尝试时长选项")
        self.assertEqual(sorted(html_values), sorted(store_values),
                         "下拉选项与权威 choices 分叉了，选中会被静默回滚")


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


class ManualUpdateUiBehaviorTests(unittest.TestCase):
    """更新通道独立于报名，覆盖请求时序、失败收尾与页面恢复。"""

    def test_late_snapshot_does_not_replace_newer_check(self):
        """接管旧请求后的快照可能晚到，不能覆盖用户随后新开的查询。"""
        res = run_js(r"""
let finishSnapshot, first = true;
window.pywebview = { api: {
  check_update: id => {
    if (first) { first = false; return Promise.resolve({ok:true,queued:true,skipped:true,request_id:"old"}); }
    return Promise.resolve({ok:true,queued:true,request_id:id});
  },
  bootstrap: () => new Promise(resolve => { finishSnapshot = resolve; }),
} };
checkUpdate();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
window.onBackend.update({request_id:"old",state:"current"});
checkUpdate();
const fresh = S.update.requestId;
finishSnapshot({update_check:{checking:false,request_id:"old",result:{request_id:"old",state:"current"}}});
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const pending = {preserved:S.update.requestId===fresh,state:S.update.state};
window.onBackend.update({request_id:fresh,state:"available",latest_version:"1.2.0"});
out.push({pending,state:S.update.state});
""")
        self.assertEqual(res[0], {"pending": {"preserved": True, "state": "checking"},
                                  "state": "available"})

    def test_result_timestamp_is_not_a_live_check(self):
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"current",checked_at:"2026-10-25T15:00:00Z"});
const known = {hidden:document.querySelector("#update-checked-at").hidden,
  text:document.querySelector("#update-checked-at").textContent};
window.onBackend.update({request_id:"request",state:"error",checked_at:"invalid"});
out.push({known,unknownHidden:document.querySelector("#update-checked-at").hidden});
""")
        self.assertFalse(res[0]["known"]["hidden"])
        self.assertIn("检查时间", res[0]["known"]["text"])
        self.assertTrue(res[0]["unknownHidden"])

    def test_open_help_never_queries_update(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: () => { calls += 1; } } };
document.querySelector("#btn-help").click();
document.querySelector("#btn-help").click();
out.push({ calls, open: document.querySelector("#help").open,
  state: document.querySelector("#update-status").textContent });
""")
        # 文案跟原型 Main.dc.html:1262 走：空闲态也要说清什么时候才联网
        self.assertEqual(res[0], {"calls": 0, "open": True, "state": "只有点“检查更新”时才联网，下载前还会再确认。"})

    def test_double_click_is_single_flight(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: id => { calls += 1; return Promise.resolve({ok:true,queued:true,request_id:id}); } } };
document.querySelector("#btn-update-check").click();
document.querySelector("#btn-update-check").click();
out.push({ calls, disabled: document.querySelector("#btn-update-check").disabled });
""")
        self.assertEqual(res[0], {"calls": 1, "disabled": True})

    def test_result_before_ack_does_not_reenter_checking(self):
        res = run_js(r"""
window.pywebview = { api: { check_update: id => {
  window.onBackend.update({request_id:id,state:"current"});
  return Promise.resolve({ok:true,queued:true,request_id:id});
} } };
document.querySelector("#btn-update-check").click();
await Promise.resolve(); await Promise.resolve();
out.push({state:S.update.state,disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "current", "disabled": False})

    def test_stale_event_cannot_replace_current_request(self):
        res = run_js(r"""
window.pywebview = { api: { check_update: id => Promise.resolve({ok:true,queued:true,request_id:id}) } };
checkUpdate();
const current = S.update.requestId;
window.onBackend.update({request_id:"old",state:"available",latest_version:"9.9.9"});
const stale = S.update.state;
window.onBackend.update({request_id:current,state:"preview",latest_version:"1.0.2"});
out.push({stale,state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["stale"], "checking")
        self.assertEqual(res[0]["state"], "preview")
        self.assertIn("1.0.2", res[0]["text"])

    def test_all_terminal_states_restore_button(self):
        res = run_js(r"""
for (const state of ["available","current","preview","unavailable","error"]) {
  S.update.requestId = "request"; S.update.state = "checking";
  window.onBackend.update({request_id:"request",state,latest_version:"1.2.0",text:"连接超时"});
  out.push({state,disabled:document.querySelector("#btn-update-check").disabled,
    text:document.querySelector("#update-status").textContent});
}
""")
        self.assertTrue(all(not item["disabled"] for item in res))
        self.assertIn("发现新版本", res[0]["text"])
        self.assertIn("最新正式版", res[1]["text"])
        self.assertIn("预览", res[2]["text"])
        self.assertEqual(res[3]["text"], "还没有正式发布的版本。")
        self.assertIn("暂时无法检查", res[4]["text"])

    def test_launching_shows_backend_text(self):
        """启动成功的二段文案由后端下发，前端固定「正在启动安装程序…」只是兜底。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"launching",
  text:"安装程序已启动。请先关闭本工具，再按向导完成安装。"});
out.push({state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["state"], "launching")
        self.assertEqual(res[0]["text"], "安装程序已启动。请先关闭本工具，再按向导完成安装。")

    def test_no_installer_shows_backend_reason(self):
        """no_installer 的三类原因由后端区分下发（update_check.py），前端不得一律说「没有可校验的安装包」。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"no_installer",latest_version:"1.2.0",
  text:"发现新版本 1.2.0，但安装包大小与校验信息不一致，请前往下载页手动下载。"});
out.push({state:S.update.state,text:document.querySelector("#update-status").textContent});
""")
        self.assertEqual(res[0]["state"], "no_installer")
        self.assertEqual(res[0]["text"], "发现新版本 1.2.0，但安装包大小与校验信息不一致，请前往下载页手动下载。")

    def test_bridge_reject_is_local_and_recoverable(self):
        res = run_js(r"""
S.runtime.error = "worker_missing"; S.busy = true;
const oldResult = document.querySelector("#result").textContent;
window.pywebview = { api: { check_update: () => Promise.reject(new Error("桥接失败")) } };
checkUpdate();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({state:S.update.state,runtime:S.runtime.error,busy:S.busy,
  result:document.querySelector("#result").textContent===oldResult,
  disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "error", "runtime": "worker_missing", "busy": True,
                                  "result": True, "disabled": False})

    def test_bootstrap_restores_without_network_query(self):
        res = run_js(r"""
let calls = 0;
window.pywebview = { api: { check_update: () => { calls += 1; } } };
restoreUpdate({checking:true,request_id:"inflight",result:null});
const pending = S.update.state;
restoreUpdate({checking:false,request_id:"inflight",result:{request_id:"inflight",state:"current"}});
out.push({calls,pending,state:S.update.state});
""")
        self.assertEqual(res[0], {"calls": 0, "pending": "checking", "state": "current"})

    def test_lost_event_has_finite_wait(self):
        res = run_js(r"""
const original = setTimeout; let timeout;
setTimeout = fn => { timeout = fn; return 1; };
window.pywebview = { api: { check_update: id => Promise.resolve({ok:true,queued:true,request_id:id}) } };
checkUpdate(); timeout(); setTimeout = original;
out.push({state:S.update.state,disabled:document.querySelector("#btn-update-check").disabled});
""")
        self.assertEqual(res[0], {"state": "error", "disabled": False})


class UpdateBoardPaintTests(unittest.TestCase):
    """更新组画板 UP01-UP12（c3-dialogs-gap 二）：每个状态只露一枚主钮、检查时间连字符、
    确认问句带真实体积、哈希失败专句、进度条 aria、黄警示独立块、底注句内链接钮。

    原型基准：Main.dc.html:771-786（markup）、1426-1451（状态行与钮槽）、1456/1459（错误框/进度块）。
    示意值（1.3.0、92.4 MB、11-03 14:20）不写死：全部由用例注入假数据、实现读真实回包。"""

    INSTALLER = {"url": "https://example.invalid/x.exe", "bytes": 96927744}  # 92.4375 MiB -> fmtBytes 92.4 MB

    def test_one_primary_action_per_state(self):
        """UP01 钮显隐矩阵（原型 Main.dc.html:1446-1451）：每态只露该态唯一的主动作钮；
        confirm 是中间态，确认下载与取消两枚同显；校验中禁用；error 走重试检查（原型 :1448）。"""
        res = run_js(r"""
const q = (id) => document.querySelector(id);
const flow = { install: q("#btn-update-install"), confirm: q("#btn-update-confirm"),
  launch: q("#btn-update-launch"), cancel: q("#btn-update-cancel"), close: q("#btn-update-close") };
const installer = { url: "https://example.invalid/x.exe", bytes: 96927744 };
function paint(state, result) {
  S.update.state = state;
  S.update.result = result || null;
  S.update.paintedState = null;
  S.update.guardUntil = 0;
  paintUpdate();
}
paint("idle");
out.push({ state: "idle", check: [!q("#btn-update-check").hidden, q("#btn-update-check").textContent],
  flowHidden: q("#update-flow").hidden });
paint("available", { latest_version: "9.9.9", installer: installer });
out.push({ state: "available", install: [!flow.install.hidden, flow.install.textContent],
  checkHidden: q("#btn-update-check").hidden, confirmHidden: flow.confirm.hidden,
  cancelHidden: flow.cancel.hidden, launchHidden: flow.launch.hidden, closeHidden: flow.close.hidden });
paint("confirm", { latest_version: "9.9.9", installer: installer });
out.push({ state: "confirm", confirm: [!flow.confirm.hidden, flow.confirm.textContent],
  cancel: [!flow.cancel.hidden, flow.cancel.textContent],
  installHidden: flow.install.hidden, checkHidden: q("#btn-update-check").hidden });
paint("downloading", { downloaded: 39845888, total_bytes: 96927744 });
out.push({ state: "downloading", cancel: [!flow.cancel.hidden, flow.cancel.textContent],
  checkHidden: q("#btn-update-check").hidden });
paint("verifying");
out.push({ state: "verifying", cancel: [!flow.cancel.hidden, flow.cancel.textContent, flow.cancel.disabled],
  checkHidden: q("#btn-update-check").hidden });
paint("ready_to_install");
out.push({ state: "ready", launch: [!flow.launch.hidden, flow.launch.textContent] });
S.busy = true;
paint("ready_to_install");
out.push({ state: "ready-busy", launch: [!flow.launch.hidden, flow.launch.textContent] });
S.busy = false;
paint("launching", { text: "正在启动安装程序…" });
out.push({ state: "launching", close: [!flow.close.hidden, flow.close.textContent, flow.close.disabled],
  launchHidden: flow.launch.hidden });
/* 二段启动与真实时序一致：第一段先画过（paintedState 已是 launching），二段不再重置防误触 */
S.update.guardUntil = Date.now() - 1;
S.update.result = { text: "安装程序已启动。请先关闭本工具，再按向导完成安装。" };
paintUpdate();
out.push({ state: "launched", close: [!flow.close.hidden, flow.close.textContent, flow.close.disabled] });
paint("failed", { error_code: "hash_mismatch", installer: installer });
out.push({ state: "failed", install: [!flow.install.hidden, flow.install.textContent],
  checkHidden: q("#btn-update-check").hidden });
paint("error", { text: "连接超时" });
out.push({ state: "error", check: [!q("#btn-update-check").hidden, q("#btn-update-check").textContent],
  flowHidden: q("#update-flow").hidden });
""")
        r = {row["state"]: row for row in res}
        self.assertEqual(r["idle"]["check"], [True, "检查更新"])
        self.assertTrue(r["idle"]["flowHidden"])
        self.assertEqual(r["available"]["install"], [True, "下载并安装"])
        self.assertTrue(r["available"]["checkHidden"])
        self.assertTrue(all(r["available"][k] for k in ("confirmHidden", "cancelHidden", "launchHidden", "closeHidden")))
        self.assertEqual(r["confirm"]["confirm"], [True, "确认下载"])
        self.assertEqual(r["confirm"]["cancel"], [True, "取消"])
        self.assertTrue(r["confirm"]["installHidden"] and r["confirm"]["checkHidden"])
        self.assertEqual(r["downloading"]["cancel"], [True, "取消下载"])
        self.assertTrue(r["downloading"]["checkHidden"])
        self.assertEqual(r["verifying"]["cancel"], [True, "校验中…", True], "校验中禁用（原型 :1449）")
        self.assertTrue(r["verifying"]["checkHidden"])
        self.assertEqual(r["ready"]["launch"], [True, "启动安装程序"])
        self.assertEqual(r["ready-busy"]["launch"], [True, "仍然启动安装程序"], "计划运行中要明说会中断（UP12）")
        self.assertEqual(r["launching"]["close"], [True, "启动中…", True], "启动段禁用（UP01）")
        self.assertTrue(r["launching"]["launchHidden"])
        self.assertEqual(r["launched"]["close"], [True, "关闭本工具…", False], "启动成功才交回关窗（UP10）")
        self.assertEqual(r["failed"]["install"], [True, "重新下载"], "哈希失败或普通失败都叫重新下载（UP08）")
        self.assertTrue(r["failed"]["checkHidden"])
        self.assertEqual(r["error"]["check"], [True, "重试检查"], "检查失败没有安装包可重下，走重试（原型 :1448）")
        self.assertTrue(r["error"]["flowHidden"])

    def test_checked_at_is_hyphen_padded_format(self):
        """UP03 检查时间自拼 MM-DD HH:mm（连字符、pad2），不靠 toLocaleString（Chromium 出斜杠）。"""
        res = run_js(r"""
out.push(formatCheckedAt(new Date(2026, 10, 3, 14, 20).getTime()));
out.push(formatCheckedAt(new Date(2026, 0, 5, 8, 5).getTime()));
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"current",checked_at:"2026-11-03T06:20:00Z"});
const at = document.querySelector("#update-checked-at");
out.push({ hidden: at.hidden, tail: at.textContent.slice(5),
  pattern: /^\d{2}-\d{2} \d{2}:\d{2}$/.test(at.textContent.slice(5)) });
""")
        self.assertEqual(res[0], "11-03 14:20")
        self.assertEqual(res[1], "01-05 08:05")
        self.assertTrue(res[2]["pattern"], "回包时间也要落成连字符格式：%s" % res[2]["tail"])
        self.assertFalse(res[2]["hidden"])

    def test_confirm_question_carries_real_size(self):
        """UP04 确认问句带真实体积（X=版本、Y=installer.bytes 换算）；无体积时去括号段。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"confirm",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe", bytes:96927744}});
const withSize = document.querySelector("#update-confirm-question").textContent;
window.onBackend.update({request_id:"request",state:"confirm",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe"}});
const withoutSize = document.querySelector("#update-confirm-question").textContent;
out.push({ withSize, withoutSize, boxShown: !document.querySelector("#update-confirm-box").hidden });
""")
        self.assertEqual(res[0]["withSize"],
                         "下载 9.9.9 安装包（92.4 MB）？只写临时目录，不动现在的程序和你的数据。"
                         "校验通过后，什么时候安装由你决定。")
        self.assertEqual(res[0]["withoutSize"],
                         "下载 9.9.9 安装包？只写临时目录，不动现在的程序和你的数据。"
                         "校验通过后，什么时候安装由你决定。")
        self.assertTrue(res[0]["boxShown"])

    def test_available_shows_version_block_with_real_size(self):
        """UP04 新版本块：大版本数字＋体积句；后端没带 bytes 时不显示体积句。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"available",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe", bytes:96927744}});
const box = document.querySelector("#update-version-box");
const sized = { shown: !box.hidden, num: document.querySelector("#update-version-num").textContent,
  note: document.querySelector("#update-version-note").textContent };
window.onBackend.update({request_id:"request",state:"available",latest_version:"9.9.9",
  installer:{url:"https://example.invalid/x.exe"}});
const bare = { shown: !box.hidden, num: document.querySelector("#update-version-num").textContent,
  note: document.querySelector("#update-version-note").textContent };
out.push({ sized, bare });
""")
        # 句中「安」「装」之间插了不可见的 U+2060，防止窄屏下末行只剩「装」一个字
        self.assertEqual(res[0]["sized"], {"shown": True, "num": "9.9.9",
                                           "note": "完整安装包 92.4 MB，下载后先校验，再由你决定什么时候安⁠装"})
        self.assertEqual(res[0]["bare"], {"shown": True, "num": "9.9.9", "note": ""})

    def test_hash_mismatch_gets_dedicated_sentence(self):
        """UP08 哈希专句只按 error_code=hash_mismatch 显示；其余 error_code 照旧显示后端 text。"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"failed",error_code:"hash_mismatch",
  text:"下载内容哈希校验未通过，已放弃并清理。"});
const box = document.querySelector("#update-error-box");
const hash = { hidden: box.hidden, text: box.textContent,
  status: document.querySelector("#update-status").textContent };
window.onBackend.update({request_id:"request",state:"failed",error_code:"size_mismatch",
  text:"下载大小与校验信息不一致（96927744 / 96927744 字节），已放弃。"});
const other = { hidden: box.hidden, text: box.textContent };
window.onBackend.update({request_id:"request",state:"error",text:"暂时无法连接GitHub，请检查网络后重试。"});
const checkErr = { hidden: box.hidden, text: box.textContent };
out.push({ hash, other, checkErr });
""")
        self.assertEqual(res[0]["hash"], {
            "hidden": False, "text": "下载内容的哈希校验没通过，已放弃并删掉临时文件。旧版本和你的数据都没动。",
            "status": "更新没有完成。"})
        self.assertEqual(res[0]["other"]["text"], "下载大小与校验信息不一致（96927744 / 96927744 字节），已放弃。")
        self.assertNotIn("哈希校验没通过", res[0]["other"]["text"])
        self.assertEqual(res[0]["checkErr"]["text"], "暂时无法连接GitHub，请检查网络后重试。")
        self.assertFalse(res[0]["checkErr"]["hidden"])

    def test_progress_block_carries_aria_and_percent(self):
        """UP06 进度块：aria-valuenow 随真实进度走，右侧「A / B MB（P%）」；
        校验中左句换「下载完成，正在校验」、右侧数字让位。
        （role/aria-label/aria-valuemax 是静态骨架，在 test_update_board_markup_follows_prototype 钉。）"""
        res = run_js(r"""
S.update.requestId = "request";
window.onBackend.update({request_id:"request",state:"downloading",downloaded:39845888,total_bytes:96927744});
const bar = document.querySelector("#update-progress-bar");
const box = document.querySelector("#update-progress-box");
const down = { shown: !box.hidden, label: document.querySelector("#update-progress-label").textContent,
  num: document.querySelector("#update-progress-num").textContent,
  now: bar.getAttribute("aria-valuenow"),
  noteShown: !document.querySelector("#update-download-note").hidden };
window.onBackend.update({request_id:"request",state:"verifying"});
const verify = { shown: !box.hidden, label: document.querySelector("#update-progress-label").textContent,
  num: document.querySelector("#update-progress-num").textContent,
  now: bar.getAttribute("aria-valuenow"),
  noteShown: !document.querySelector("#update-download-note").hidden };
out.push({ down, verify });
""")
        self.assertEqual(res[0]["down"], {"shown": True, "label": "已下载", "num": "38.0 / 92.4 MB（41%）",
                                          "now": "41", "noteShown": True})
        # 校验中的 aria-valuenow 沿用合并结果里最后一次下载进度（真实链路末包 done==total → 100）
        self.assertEqual(res[0]["verify"], {"shown": True, "label": "下载完成，正在校验", "num": "",
                                            "now": "41", "noteShown": True})

    def test_ready_warn_block_is_independent(self):
        """UP11/UP12 黄警示独立成块（不再拼进进度行）：busy 才显示，向导句常驻就绪块。"""
        res = run_js(r"""
S.update.requestId = "request";
S.busy = true;
window.onBackend.update({request_id:"request",state:"ready_to_install"});
const busy = { boxShown: !document.querySelector("#update-ready-box").hidden,
  warnShown: !document.querySelector("#update-plan-warn").hidden,
  progressGone: document.querySelector("#update-progress-box").hidden,
  status: document.querySelector("#update-status").textContent };
S.busy = false;
paintUpdate();
const idle = { warnShown: !document.querySelector("#update-plan-warn").hidden,
  status: document.querySelector("#update-status").textContent };
out.push({ busy, idle });
""")
        self.assertEqual(res[0]["busy"], {"boxShown": True, "warnShown": True, "progressGone": True,
                                          "status": "安装包已通过大小和 SHA-256 校验。"})
        self.assertFalse(res[0]["idle"]["warnShown"], "计划没跑就不该吓唬人")
        self.assertEqual(res[0]["idle"]["status"], "安装包已通过大小和 SHA-256 校验。")

    def test_update_board_markup_follows_prototype(self):
        """UP01/UP04/UP06/UP08/UP10/UP11 静态骨架：状态行、错误框、新版本块、确认/就绪盒、
        进度条 aria、黄警示独立块、底注句内链接钮，全部照原型 Main.dc.html:771-786 落位。"""
        html = read("ui/index.html")
        row = html[html.index('<div class="help-tool-row set-update">'):]
        row = row[:row.index('<div class="help-tool-row">')]
        for needle in ("help-version", "update-status", "update-checked-at", "update-error-box",
                       "update-version-box", "update-confirm-box", "update-progress-box",
                       "update-progress-bar", "update-progress-fill",
                       "update-plan-warn", "update-ready-box", "update-download-note",
                       "btn-update-install", "btn-update-confirm", "btn-update-launch",
                       "btn-update-cancel", "btn-update-close", "btn-update-check", "btn-help-latest"):
            self.assertIn('id="%s"' % needle, row, "「版本与更新」缺 #%s" % needle)
        self.assertIn('role="progressbar"', row)
        self.assertIn('aria-label="安装包下载进度"', row)
        self.assertIn('aria-valuemax="100"', row)
        self.assertIn("启动后按安装向导操作。工具不会自己退出或重启。", row, "就绪块的向导句（UP12，原型 :781）")
        # 「建」「议」之间插了不可见的 U+2060，防止「建议」被拆到两行
        self.assertIn("报名计划还在运行。安装时要先关闭本工具，计划会停止，建⁠议等这次计划结束再装。", row,
                      "黄警示独立成块（UP11，原型 :781）")
        note = row[row.index('<p class="ph-note">'):]
        self.assertIn('<button class="ph-link" id="btn-help-latest" type="button">打开发布页</button>', note,
                      "底注句内链接钮（UP10，原型 :784）")
        self.assertIn("，看更新说明，或者手动下载完整包。", note)
        self.assertNotIn("前往下载页", row, "独立「前往下载页」钮撤底（UP10）")
        css = read("ui/styles.css")
        for rule in (".up-v {", ".upbox {", ".help-tool-row p.ph-err", ".help-tool-row p.ph-warn"):
            self.assertIn(rule, css, "样式缺 %s（UP04/UP08/UP11）" % rule)
        for state in ('[data-state="available"]', '[data-state="ready_to_install"]'):
            self.assertIn("#update-status%s" % state, css, "状态行配色缺 %s（UP03/UP12）" % state)


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


class TermsConsentContractTests(unittest.TestCase):
    """决策 013 / 条款同意门：后端快照、ui.json 落盘与版本同源契约。"""

    # 版本形如 2026-10-27 或 2026-11-03-r4：修订版必须能被解析，否则
    # 「已同意版本 != 当前版本」的判定会被旧同意记录静默绕过
    DOCS_VERSION_RE = r"版本：\*\*(\d{4}-\d{2}-\d{2}(?:-r\d+)?)\*\*"

    TERMS_DOC_PATHS = ("docs/USER_AGREEMENT.md", "docs/PRIVACY_POLICY.md")

    def _docs_terms_version(self) -> str:
        """两份文档各自带版本字段，且必须同值：拆开后不能出现两套版本号。"""
        versions = []
        for path in self.TERMS_DOC_PATHS:
            text = (LOCAL.parent / path).read_text(encoding="utf-8")
            match = re.search(self.DOCS_VERSION_RE, text)
            self.assertIsNotNone(match, path + " 必须带 版本：**YYYY-MM-DD** 字段")
            versions.append(match.group(1))
        self.assertEqual(len(set(versions)), 1,
                         "两份条款文档版本号必须一致，收到 %r" % (versions,))
        return versions[0]

    def _app_terms_version(self) -> str:
        import ast

        tree = ast.parse(read("app.py"))
        node = next(item for item in tree.body
                    if isinstance(item, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "TERMS_VERSION"
                            for target in item.targets))
        return ast.literal_eval(node.value)

    def test_terms_version_matches_docs_file(self):
        """程序内条款版本与两份 docs 是同一份（决策 013）。"""
        self.assertEqual(self._app_terms_version(), self._docs_terms_version(),
                         "TERMS_VERSION 与条款文件版本字段漂移了；两处必须一起改")

    def test_terms_state_reads_only_declared_prefs_keys(self):
        """terms_state 只读 ui.json 的 terms_version / terms_accepted_at。"""
        import ast

        tree = ast.parse(read("app.py"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "terms_state"
                    and [arg.arg for arg in item.args.args][:1] == ["prefs"])
        module = ast.Module(body=[node], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {"TERMS_VERSION": "9.9.9-test"}
        exec(compile(module, "<terms_state>", "exec"), namespace)  # noqa: S102
        terms_state = namespace["terms_state"]

        self.assertEqual(terms_state({}),
                         {"version": "9.9.9-test", "accepted_version": "", "accepted_at": ""})
        self.assertEqual(
            terms_state({"terms_version": "1.0.0", "terms_accepted_at": "2026-10-27 09:00:00"}),
            {"version": "9.9.9-test", "accepted_version": "1.0.0",
             "accepted_at": "2026-10-27 09:00:00"})
        self.assertEqual(terms_state(None)["accepted_version"], "", "None 偏好必须回退为未同意")

        # 只碰声明的两个键：不读 session/storage，也不写日志
        source = ast.unparse(node)
        self.assertIn("terms_version", source)
        self.assertIn("terms_accepted_at", source)
        for banned in ("SESSION_FILE", "STORAGE_STATE", "storage_state", "grab.log", "log"):
            self.assertNotIn(banned, source, "terms_state 不得触碰登录文件或日志")

    def test_bootstrap_carries_terms_snapshot(self):
        """bootstrap 载荷必须带 terms 快照（terms_state(prefs)），界面据此判定门禁。"""
        import ast

        tree = ast.parse(read("app.py"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "bootstrap"
                    and [arg.arg for arg in item.args.args][:1] == ["self"])
        source = ast.unparse(node)
        self.assertIn("'terms': terms_state(prefs)", source,
                      "bootstrap 必须把 terms_state(prefs) 放进载荷")

    def test_accept_terms_writes_prefs_transaction_only(self):
        """accept_terms：经 update_prefs 原子事务写两个键；不碰登录文件与日志。"""
        import ast

        tree = ast.parse(read("app.py"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "accept_terms"
                    and [arg.arg for arg in item.args.args][:1] == ["self"])
        # accept_terms 的返回载荷复用 terms_state：一起编译，保持与真实实现同源
        state_node = next(item for item in ast.walk(tree)
                          if isinstance(item, ast.FunctionDef) and item.name == "terms_state"
                          and [arg.arg for arg in item.args.args][:1] == ["prefs"])
        module = ast.Module(body=[node, state_node], type_ignores=[])
        ast.fix_missing_locations(module)

        source = ast.unparse(node)
        self.assertIn("update_prefs", source, "必须走 ui.json 原子偏好事务")
        for banned in ("SESSION_FILE", "STORAGE_STATE", "storage_state",
                       "read_text", "_trace", "addLog"):
            self.assertNotIn(banned, source, "同意状态不得读写登录文件或写日志")

        stamp = "2026-10-27 12:00:00"

        class FakeTime:
            @staticmethod
            def strftime(fmt, value):
                return stamp

            @staticmethod
            def localtime():
                return ()

        written = []

        def fake_update(patch):
            written.append(dict(patch))
            return True

        namespace = {"time": FakeTime, "TERMS_VERSION": "9.9.9-test",
                     "update_prefs": fake_update,
                     "load_prefs": lambda: {"terms_version": "9.9.9-test",
                                            "terms_accepted_at": stamp}}
        exec(compile(module, "<accept_terms>", "exec"), namespace)  # noqa: S102
        accept_terms = namespace["accept_terms"]

        # AST 抽出的真实签名是 accept_terms(self, document_version="")：首参
        # 会绑定 self，document_version 必须用关键字（或第二实参）传入；单传
        # 一个字符串会把版本绑进 self、让 document_version 退回默认空串，
        # 在写前被版本校验拒绝——那测不到成功事务本身。
        got = accept_terms(None, document_version="9.9.9-test")
        self.assertEqual(got["ok"], True)
        self.assertEqual(got["terms"], {"version": "9.9.9-test",
                                        "accepted_version": "9.9.9-test",
                                        "accepted_at": stamp})
        self.assertEqual(written, [{"terms_version": "9.9.9-test",
                                    "terms_accepted_at": stamp}])

        # 拿不到跨进程锁：如实失败，不落盘也不谎报成功。
        # 「尝试过写入」与「真正持久化」必须用两个容器区分：busy_attempts 记录
        # 每次尝试的 patch（期望恰为正确两键一次），written 只记真正落盘的键
        # （忙锁分支必须仍为空）——不能用一个从未被写入的列表冒充"未持久化"。
        written.clear()  # 先清空成功持久化容器：本分支只观察忙锁轮次
        busy_attempts = []

        def busy_update(patch):
            busy_attempts.append(dict(patch))
            return False

        namespace["update_prefs"] = busy_update
        busy = accept_terms(None, document_version="9.9.9-test")
        self.assertEqual(busy["ok"], False)
        self.assertEqual(busy["error"], "prefs_busy")
        self.assertEqual(busy_attempts,
                         [{"terms_version": "9.9.9-test",
                           "terms_accepted_at": stamp}],
                         "忙锁分支仍必须恰好尝试一次正确的两键")
        self.assertEqual(written, [], "成功持久化容器在忙锁分支保持为空")

    def test_accept_terms_rejects_mismatched_version_before_write(self):
        """版本不匹配（缺参/旧版/非法类型）必须在写前拒绝：零 update_prefs。"""
        import ast
        import time

        tree = ast.parse(read("app.py"))
        node = next(item for item in ast.walk(tree)
                    if isinstance(item, ast.FunctionDef) and item.name == "accept_terms"
                    and [arg.arg for arg in item.args.args][:1] == ["self"])
        source = ast.unparse(node)
        # 判定必须先于任何写入与时间戳生成（顺序即证据）
        self.assertLess(source.index("document_version == TERMS_VERSION"),
                        source.index("update_prefs"),
                        "版本判定必须位于原子写之前")
        self.assertLess(source.index("document_version == TERMS_VERSION"),
                        source.index("strftime"),
                        "版本判定必须位于时间戳生成之前")

        state_node = next(item for item in ast.walk(tree)
                          if isinstance(item, ast.FunctionDef) and item.name == "terms_state"
                          and [arg.arg for arg in item.args.args][:1] == ["prefs"])
        module = ast.Module(body=[node, state_node], type_ignores=[])
        ast.fix_missing_locations(module)

        written = []
        store = {"terms_version": "9.9.9-test", "terms_accepted_at": "2026-10-27 12:00:00"}
        namespace = {"time": time, "TERMS_VERSION": "9.9.9-test",
                     "update_prefs": lambda patch: (written.append(dict(patch)), True)[1],
                     "load_prefs": lambda: dict(store)}
        exec(compile(module, "<accept_terms>", "exec"), namespace)  # noqa: S102
        accept_terms = namespace["accept_terms"]

        # 非法 document_version 全集逐项拒绝（subTest 便于定位到具体输入）；
        # self 传 None 只是给首参占位——被检对象始终是 document_version。
        for bad in ("", "9.9.8-old", "9.9.10-new", None, 999, {"v": "9.9.9-test"}):
            with self.subTest(document_version=bad):
                got = accept_terms(None, document_version=bad)
                self.assertEqual(got["ok"], False, "非法输入 %r 必须拒绝" % (bad,))
                self.assertEqual(got["error"], "terms_version_mismatch")
                self.assertIn("terms", got, "拒绝时可带只读 terms 快照供界面比对")
        # 缺 document_version 是独立场景：签名默认空串，不能拿空串冒充缺参表达
        got_missing = accept_terms(None)
        self.assertEqual(got_missing["ok"], False, "缺 document_version 必须拒绝")
        self.assertEqual(got_missing["error"], "terms_version_mismatch")
        self.assertIn("terms", got_missing)
        self.assertEqual(written, [], "任何被拒输入都不得触发 update_prefs")
        self.assertEqual(store, {"terms_version": "9.9.9-test",
                                 "terms_accepted_at": "2026-10-27 12:00:00"},
                         "被拒后内存偏好与原同意时间必须原样不变")

    def test_terms_copy_avoids_over_promises(self):
        """负向断言：不写 MIT 之外的禁令、不写「继续使用视为同意」、不夸通信范围。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        pairs = [(path, (LOCAL.parent / path).read_text(encoding="utf-8"))
                 for path in self.TERMS_DOC_PATHS]
        pairs.append(("ui/index.html", html))
        for label, text in pairs:
            self.assertNotIn("个人非商业使用", text,
                             "%s：不得用条款收窄 MIT 已授予的权利" % label)
            self.assertNotIn("禁止商业销售", text,
                             "%s：不得新增 LICENSE 之外的分发禁止" % label)
            self.assertNotIn("去除本条款后分发", text,
                             "%s：去除补充文档不该写成许可限制" % label)
            self.assertNotIn("继续使用视为接受新版本", text,
                             "%s：版本变化必须显式重新同意，不能默认延续" % label)
            self.assertNotIn("仅在你主动操作时向学校系统发起访问", text,
                             "%s：同意后有周期刷新，不能写成只在手动时通信" % label)
        # 责任限制仍需保留法律不可排除的部分
        agreement = (LOCAL.parent / "docs" / "USER_AGREEMENT.md").read_text(encoding="utf-8")
        self.assertIn("不适用于法律不允许排除的情形", agreement)

    def test_terms_version_is_shared_by_docs_html_and_backend(self):
        """2026-11-09-r6 必须在文档、内嵌全文与后端常量里同时出现。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        version = self._app_terms_version()
        for pane, rel, _count in self.TERMS_DOCS:
            docs = (LOCAL.parent / rel).read_text(encoding="utf-8")
            self.assertIn(version, docs, "%s：文档版本字段与后端常量漂移" % rel)
        self.assertIn(version, html,
                      "内嵌全文必须写明同一版本：冻结程序没有 docs 目录可对照")
        agreement = (LOCAL.parent / "docs" / "USER_AGREEMENT.md").read_text(encoding="utf-8")
        self.assertIn("条款变更与终止", agreement)
        self.assertIn("再次点击同意", agreement,
                      "版本变化必须要求显式重新同意")
        # 内嵌全文不另立版本常量：版本由后端 bootstrap 带进来
        self.assertNotIn("TERMS_VERSION", html)

    def test_disclosure_covers_campus_data_dir_migration_and_uninstall_scope(self):
        """§6.1 披露四件事：CAMPUS_DATA_DIR 覆盖、迁移源副本保留、卸载只删
        默认数据目录、同意后的周期学校刷新；两处误导性旧表述必须绝迹。"""
        docs = (LOCAL.parent / "docs" / "PRIVACY_POLICY.md").read_text(encoding="utf-8")
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        readme = (LOCAL / "README.md").read_text(encoding="utf-8")
        tips = (LOCAL / "launchers" / "遇到问题先看我.txt").read_text(encoding="utf-8")
        for label, text in (("docs", docs), ("内嵌全文", html)):
            self.assertIn("CAMPUS_DATA_DIR", text,
                          "%s：必须写明 CAMPUS_DATA_DIR 对数据目录的覆盖" % label)
            self.assertIn("源文件保留在原处", text,
                          "%s：迁移是复制，源文件必须写明保留" % label)
            self.assertIn("只针对默认数据目录", text,
                          "%s：卸载可选删除必须限定在默认数据目录" % label)
            self.assertIn("按界面操作与周期刷新发生", text,
                          "%s：同意后的周期学校刷新必须写明" % label)
            self.assertNotIn("仅在你主动操作时以你的账号访问学校系统", text,
                             "%s：同意后有周期刷新，不能写成只在手动时访问学校" % label)
            self.assertNotIn("彻底删除所有数据", text,
                             "%s：删一个目录只删该处，不能声称一次清光所有副本" % label)
        self.assertIn("CAMPUS_DATA_DIR", readme,
                      "README 必须在 CAMPUS_DATA_DIR 说明附近补迁移与卸载范围")
        self.assertIn("原文件保留在旧位置", readme, "README：迁移必须写明保留原文件")
        self.assertIn("只针对默认的", readme, "README：卸载可选删除只针对默认数据目录")
        # 排障说明是固定宽度折行文本，先去掉全部空白再断言，避免跨行断词误报
        tips_compact = "".join(tips.split())
        self.assertIn("CAMPUS_DATA_DIR", tips, "排障说明必须区分自定义覆盖目录")
        self.assertIn("迁移过来的原文件也还留在原处", tips_compact,
                      "排障说明必须写明旧 EXE 旁迁移源副本仍在")
        self.assertIn("不等于所有副本都没了", tips_compact,
                      "排障说明必须写明删一个目录不等于清光全部副本")

    def test_docs_and_embedded_text_share_same_sections(self):
        """两份文档与内嵌全文的节标题、编号、顺序必须逐份一致（冻结 EXE 无 docs/ 也可读）。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        head = html.index('id="doc-terms-agreement"')
        mid = html.index('id="doc-terms-privacy"')
        panes = {"agreement": html[head:mid], "privacy": html[mid:]}
        for pane, path, count in self.TERMS_DOCS:
            docs = (LOCAL.parent / path).read_text(encoding="utf-8")
            doc_titles = re.findall(r"^## (\d+)\. (.+)$", docs, flags=re.M)
            html_titles = re.findall(r"<h3>(\d+)\. (.+?)</h3>", panes[pane])
            self.assertEqual([t[0] for t in doc_titles],
                             [str(i) for i in range(1, count + 1)],
                             path + " 必须是 1..%d 节" % count)
            self.assertEqual([t[0] for t in html_titles],
                             [str(i) for i in range(1, count + 1)],
                             pane + " 内嵌全文必须是 1..%d 节" % count)
            for (no, title), (hno, htitle) in zip(doc_titles, html_titles):
                self.assertEqual((no, title), (hno, htitle),
                                 "%s 第 %s 节标题两处必须一字不差" % (pane, no))

    def test_index_html_has_terms_dialog_contract(self):
        """条款契约：全文阅读器、两个小框、同意、暂不使用与帮助内入口。
        （20261108-c3-dialogs decisions 第 1 条：#dlg-terms 只做全文阅读器，
        要点/全文切换钮删除；首次同意入口是首次说明框、版本更新入口是条款更新框，
        「查看完整条款」由「现在就看」（首次说明框）与「看完整条款」（更新框）取代。）"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        for required in ('id="dlg-terms"', 'id="btn-terms-accept"',
                         'id="btn-terms-decline"', 'id="dlg-terms-version"',
                         'id="dlg-terms-full-text"', 'id="btn-help-terms"',
                         'id="dlg-terms-status"',
                         'id="dlg-terms-intro"', 'id="dlg-terms-update"'):
            self.assertIn(required, html, "条款弹窗缺少 %s" % required)
        self.assertIn("我已阅读并同意", html)
        self.assertIn("暂不使用", html)
        self.assertIn("看完整条款", html, "条款更新框的完整条款入口")
        # 「现在就看」由 views/terms.js 从 store 的 FIRST_USE_POINTS 第六条渲染（原型 Main:806）
        self.assertIn("现在就看", read("ui/state/store.js"),
                      "首次说明框的完整条款入口句在六条要点数据里")
        self.assertNotIn('id="btn-terms-full"', html, "要点/全文切换钮已随要点视图删除")
        # 完整条款必须覆盖两份文档各自全部节（拆开后各自从 1 编号）
        head = html.index('id="doc-terms-agreement"')
        mid = html.index('id="doc-terms-privacy"')
        panes = {"agreement": html[head:mid], "privacy": html[mid:]}
        for pane, count in (("agreement", 10), ("privacy", 8)):
            for index in range(1, count + 1):
                self.assertIn("%d. " % index, panes[pane],
                              "%s 缺第 %d 节" % (pane, index))
        # 不出现任何报名成功承诺
        for banned in ("包成功", "保证报名成功", "必定成功"):
            self.assertNotIn(banned, html)

    def test_terms_reader_shell_matches_prototype(self):
        """TM01-TM05（c3-dialogs-gap，原型 Main:386-387/886-895）：全文阅读器壳层——
        tdoc 外框、× 只等于关闭、标题与页签、脚部两态、TOC 宽档常显与徽章样式。"""
        html = read("ui/index.html")
        start = html.index('id="dlg-terms"')
        block = html[start:html.index("</dialog>", start)]
        # TM01：壳层类名映射原型 .dlg.tdoc；× 走原生关闭，aria 只说「关闭条款」
        self.assertIn('class="dlg dlg-terms tdoc"', html)
        self.assertIn('method="dialog"', block)
        self.assertIn('aria-label="关闭条款"', block)
        self.assertNotIn("暂不使用并关闭条款", block, "× 不再等于拒绝")
        # TM02：标题照原型（Main:887）
        self.assertIn(">使用条款与隐私</h2>", block)
        self.assertNotIn("使用条款与隐私告知", block)
        # TM03：第三页签照原型叫「开源许可」，右侧注逐字弯引号（Main:888）
        self.assertIn(">开源许可</button>", block)
        self.assertNotIn(">MIT 许可证</button>", block,
                         "页签名照原型改；正文与 MIT 相关字样不受影响")
        self.assertIn("标着“本版新增”的是这次的改动", block)
        # TM02：元信息行 = 版本句 + 本份副本版本节点 + JS 状态段
        self.assertIn('id="dlg-terms-version"', block)
        self.assertIn('id="dlg-terms-document-version"', block)
        self.assertIn('id="terms-sub-state"', block)
        # TM04/TM05：脚部两态——勾选行连接词「和」、主钮「同意并继续」、只读「关闭」
        # （「与→和」只按任务规格改勾选行；副行的连接词不在此列）
        foot = block[block.index('class="dlg-foot terms-foot"'):]
        self.assertIn("我已阅读并同意<button", foot)
        self.assertIn('《用户协议》</button>和<button type="button" class="doc-link" data-doc="privacy"',
                      foot, "勾选行连接词照原型用「和」")
        self.assertNotIn("《用户协议》</button>与<button", foot)
        self.assertIn(">同意并继续</button>", block)
        self.assertNotIn(">我已阅读并同意</button>", block)
        self.assertIn(">关闭</button>", block)
        self.assertIn(">Esc 关闭</span>", block)
        self.assertNotIn("Esc 暂不使用", block)
        # TM01：章节导航宽档常显——HTML 不写 hidden，显隐交给样式（≤719px 收起）
        self.assertNotRegex(html, r'<nav class="terms-toc"[^>]*hidden')
        css = read("ui/styles.css")
        self.assertIn("grid-template-columns: 11rem minmax(0, 1fr)", css,
                      "宽档左栏 11rem（原型 Main:394）")
        self.assertIn("@media (max-width: 719px) { .terms-toc { display: none; } }", css)
        self.assertNotIn("has-toc", css, "旧「只在全文视图显示」的开关删干净")
        self.assertNotIn("has-toc", read("ui/views/terms.js"))
        # TM03：「本版新增」徽章样式挂在 data-new 节标上（正文文字不动）
        self.assertIn('h3[data-new]::after { content: "本版新增"', css)
        # NEEDS-HUMAN 7：死引用清零，焦点归还改指设置里的查看条款入口
        self.assertNotIn("btn-help-terms-view", read("ui/views/terms.js"))

    # ---- 内嵌全文 ↔ 规范真源逐字契约（计划 20261028-terms-embedded-exact-sync）----

    # 两份文档各自成篇，维护说明句里的「完整条款/完整协议」措辞不同，
    # 这里只锚定不随文档切换变化的半句。
    MAINTENANCE_NOTE = "本文件是随源码分发的可审阅规范来源"
    DISCLAIMER = "本文件是产品使用说明，不是法律意见；有具体法律疑问请咨询执业律师。"
    OFFLINE_NOTE = "本份条款可离线阅读：全文就在本窗口内，不依赖网络或仓库文档。"

    @staticmethod
    def _norm_canonical(text: str, *, strip_ordered: bool) -> str:
        # HTMLParser 已去标签；HTML 中的 Markdown 字符就是可见文字，必须参与比较。
        if not strip_ordered:
            return re.sub(r"\s+", "", text)
        text = text.replace("**", "").replace("`", "")
        text = re.sub(r"(?m)^\s*>\s?", "", text)
        text = re.sub(r"(?m)^\s*-\s+", "", text)
        text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)
        text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _first_diff(a: str, b: str) -> int:
        for index, (left, right) in enumerate(zip(a, b)):
            if left != right:
                return index
        return min(len(a), len(b))

    # 条款已拆两份：各自独立成篇，节数与文件路径都不一样
    TERMS_DOCS = (("agreement", "docs/USER_AGREEMENT.md", 10),
                  ("privacy", "docs/PRIVACY_POLICY.md", 8))

    def _docs_canonical_texts(self, path="docs/USER_AGREEMENT.md", count=10):
        """只读解析条款文档 →（前言规范化文本, {1..N: 规范化文本}）。
        前言剔除已知排除项「规范来源维护说明句」（计划 task4 clarify 记录），剔除前先断言
        该句仍在 docs，避免排除项在规范演化后失效。"""
        docs = (LOCAL.parent / path).read_text(encoding="utf-8")
        start = re.search(r"(?m)^## 1\. ", docs)
        self.assertIsNotNone(start, "文档必须从 ## 1. 起进入分节结构")
        preamble_raw = docs[:start.start()]
        title = re.search(r"(?m)^# (.+)$", preamble_raw)
        self.assertIsNotNone(title, "docs 必须带 # 一级标题")
        quote = "\n".join(re.findall(r"(?m)^\s*>\s?(.*)$", preamble_raw))
        quote_n = self._norm_canonical(quote, strip_ordered=True)
        maint_n = re.sub(r"\s+", "", self.MAINTENANCE_NOTE)
        self.assertIn(maint_n, quote_n, "维护说明句必须仍在 docs 前言，否则该排除项失去依据")
        # 两份文档措辞略有不同（完整条款/完整协议），整句按锚点起、句号止剥掉
        quote_n = re.sub(re.escape(maint_n) + r".*?里读到。", "", quote_n)
        preamble = self._norm_canonical(title.group(1), strip_ordered=True) + quote_n
        sections = {}
        for part in re.split(r"(?m)^(?=## \d+\. )", docs):
            match = re.match(r"## (\d+)\. ", part)
            if match:
                sections[int(match.group(1))] = self._norm_canonical(part, strip_ordered=True)
        self.assertEqual(sorted(sections), list(range(1, count + 1)),
                         "%s 必须是 1..%d 节" % (path, count))
        return preamble, sections

    def _embedded_canonical_texts(self, html=None, count=11):
        """标准库 HTMLParser 从 #dlg-terms-full-text 抽取用户可见规范文本 →
        （前言, {1..11}, 容器内全部文本）。html 为 None 时才读真实 index.html，
        传入字符串时只解析内存样例（task3 突变用例）。采集范围不越过该 section：
        不误收要点、版本副标题、工具栏、帮助 UI 或离线说明。"""
        from html.parser import HTMLParser

        class _TermsFullTextParser(HTMLParser):
            """按 terms-section 分桶收集可见文本：terms-preamble 归前言，
            其余按 h3 的节号归节；all_text 记录容器内全部文本供全量比较与排除断言。
            section/div 两个深度界定桶起止、识别不支持的嵌套；其他标签不计深度。"""

            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.in_full = False
                self.full_roots = 0      # 全文根 section 出现次数（必须恰好 1）
                self.section_depth = 0   # 根闭合后必须归 0
                self.div_depth = 0        # 容器内 div 深度（根 section 自身不计）
                self.bucket = None       # {"preamble", "num", "parts"} | None
                self.bucket_depth = None # 建桶时的 div_depth，只在同深度闭合封桶
                self.h3_parts = None
                self.preamble = []
                self.sections = {}
                self.section_order = []  # 封桶先后（章序断言）
                self.all_text = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if not self.in_full:
                    if tag == "section" and attrs.get("id") == "dlg-terms-full-text":
                        self.full_roots += 1
                        self.in_full = True
                        self.section_depth = 1
                    return
                if tag == "section":
                    raise AssertionError("全文容器内出现嵌套 section：结构不受支持")
                if tag == "div":
                    self.div_depth += 1
                    classes = (attrs.get("class") or "").split()
                    if "terms-section" in classes:
                        if self.bucket is not None:
                            raise AssertionError("terms-section 嵌套在另一节内：结构不受支持")
                        self.bucket = {"preamble": "terms-preamble" in classes,
                                       "num": None, "parts": []}
                        self.bucket_depth = self.div_depth
                elif tag == "h3" and self.bucket is not None:
                    self.h3_parts = []

            def handle_endtag(self, tag):
                if not self.in_full:
                    return
                if tag == "section":
                    self.in_full = False
                    self.section_depth = 0
                    return
                if tag == "h3" and self.bucket is not None:
                    head = re.match(r"(\d+)\.", "".join(self.h3_parts or []).strip())
                    if head and not self.bucket["preamble"]:
                        self.bucket["num"] = int(head.group(1))
                    self.h3_parts = None
                elif tag == "div":
                    # 只在建桶时的深度封桶：桶内纯结构嵌套 div 不提前截断
                    if self.bucket is not None and self.div_depth == self.bucket_depth:
                        text = "".join(self.bucket["parts"])
                        if self.bucket["preamble"]:
                            self.preamble.append(text)
                        else:
                            if self.bucket["num"] is None:
                                raise AssertionError("非前言桶没有可解析章号：结构不受支持")
                            self.sections.setdefault(self.bucket["num"], []).append(text)
                            self.section_order.append(self.bucket["num"])
                        self.bucket = None
                        self.bucket_depth = None
                    self.div_depth -= 1

            def handle_data(self, data):
                if not self.in_full:
                    return
                if self.h3_parts is not None:
                    self.h3_parts.append(data)
                if self.bucket is not None:
                    self.bucket["parts"].append(data)
                self.all_text.append(data)

        if html is None:
            html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        parser = _TermsFullTextParser()
        parser.feed(html)
        parser.close()
        self.assertFalse(parser.in_full, "#dlg-terms-full-text 必须闭合")
        self.assertEqual(parser.full_roots, 1, "全文根 section 必须恰好出现一次")
        self.assertEqual(parser.section_depth, 0, "根闭合后 section 深度必须归 0")
        self.assertIsNone(parser.bucket, "根闭合后不得残留未封的桶")
        self.assertEqual(parser.div_depth, 0, "容器内 div 必须全部闭合")
        self.assertEqual(sorted(parser.sections), list(range(1, count + 1)),
                         "内嵌必须是 1..%d 节" % count)
        self.assertTrue(all(len(texts) == 1 for texts in parser.sections.values()),
                        "每章必须恰好一个桶")
        self.assertEqual(parser.section_order, list(range(1, count + 1)),
                         "章序必须是 1..%d" % count)
        self.assertEqual(len(parser.preamble), 1, "内嵌前言块必须恰好一个")
        return parser

    @staticmethod
    def _pane_fragment(html, pane):
        """截出某一份文档的容器（div 深度配平），再包一层全文根让解析器复用。
        拆成两份后 #dlg-terms-full-text 里有两个 .terms-doc，逐份比较时各自成篇。"""
        start = html.index('<div class="terms-doc" id="doc-terms-%s"' % pane)
        depth = 0
        pos = start
        while True:
            open_at = html.find("<div", pos)
            close_at = html.find("</div>", pos)
            if close_at == -1:
                raise AssertionError("terms-doc 容器没有闭合：" + pane)
            if open_at != -1 and open_at < close_at:
                depth += 1
                pos = open_at + 4
            else:
                depth -= 1
                pos = close_at + len("</div>")
                if depth == 0:
                    return ('<section id="dlg-terms-full-text" hidden '
                            'aria-label="完整条款">' + html[start:pos] + "</section>")

    def _assert_embedded_matches_docs(self, html=None):
        """两道精确比较：前言 + 逐节（保留原首差诊断），最后加全文容器全量相等。
        桶外额外正文只能进 all_text，会被第三道断言抓住；两个既定排除项
        （离线提示、规范来源维护说明句）仍只按各自原位置排除，不设白名单。"""
        for pane, path, count in self.TERMS_DOCS:
            self._assert_pane_matches_docs(pane, path, count, html)

    @staticmethod
    def _li_parent_violations(html):
        """列表项必须挂在 <ul>/<ol> 下：裸 <li> 浏览器会当没有标记的文本。"""
        from html.parser import HTMLParser

        stack, bad = [], []

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == "li":
                    bad.append(stack[-1] if stack else "")
                stack.append(tag)

            def handle_endtag(self, tag):
                if tag in stack:
                    while stack and stack.pop() != tag:
                        pass

        P().feed(html)
        return [t for t in bad if t not in ("ul", "ol")]

    def test_terms_panes_wrap_list_items_in_ul_or_ol(self):
        """结构退化（<li> 直接挂在 <div> 下）逐字比较看不出来，必须单独断言。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        for pane, path, _count in self.TERMS_DOCS:
            frag = self._pane_fragment(html, pane)
            # 片段顶部补回被切掉的外层 section，否则解析栈起点不一致
            bad = self._li_parent_violations(frag)
            self.assertEqual(bad, [], "%s：这些 <li> 的父节点不是 ul/ol：%r" % (path, bad))
            docs = (LOCAL.parent / path).read_text(encoding="utf-8")
            tops = len(re.findall(r"^- \S", docs, re.M))
            # 嵌套项：有序编号与缩进的 - 子项都是源文档的列表项（条款升 r6 起隐私第 3 节
            # 出现了缩进的 - 子项，只数有序编号会把它们漏成「多出」）
            nested = len(re.findall(r"^[ \t]+(?:\d+\.|-)[ \t]+\S", docs, re.M))
            self.assertEqual(frag.count("<li>"), tops + nested,
                             "%s：li 数与源文档的列表项数对不上（漏项或多出）" % path)

    def _assert_pane_matches_docs(self, pane, path, count, html=None):
        """同一份文档自比：前言逐字、逐节逐字、全文容器全量相等。"""
        if html is None:
            html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        docs_preamble, docs_sections = self._docs_canonical_texts(path, count)
        parser = self._embedded_canonical_texts(self._pane_fragment(html, pane), count)
        html_preamble = self._norm_canonical("".join(parser.preamble), strip_ordered=False)
        gap = self._first_diff(html_preamble, docs_preamble)
        self.assertEqual(
            html_preamble, docs_preamble,
            "前言与规范真源不逐字一致（首差 @%d）：\n  docs: …%s…\n  html: …%s…"
            % (gap, docs_preamble[max(0, gap - 30): gap + 60],
               html_preamble[max(0, gap - 30): gap + 60]))
        self.assertEqual(list(parser.sections), list(range(1, count + 1)),
                         "章节顺序必须是 1..%d" % count)
        for number in range(1, count + 1):
            docs_text = docs_sections[number]
            html_text = self._norm_canonical("".join(parser.sections[number]),
                                             strip_ordered=False)
            gap = self._first_diff(html_text, docs_text)
            self.assertEqual(
                html_text, docs_text,
                "第 %d 节与 %s 不逐字一致（首差 @%d）：\n"
                "  docs: …%s…\n  html: …%s…"
                % (number, path, gap, docs_text[max(0, gap - 30): gap + 60],
                   html_text[max(0, gap - 30): gap + 60]))
        expected_full = docs_preamble + "".join(docs_sections[n]
                                              for n in range(1, count + 1))
        actual_full = self._norm_canonical("".join(parser.all_text), strip_ordered=False)
        gap = self._first_diff(actual_full, expected_full)
        self.assertEqual(actual_full, expected_full,
                         "全文容器有未纳入章节的正文或文本次序漂移（首差 @%d）" % gap)

    def test_embedded_full_text_is_verbatim_identical_to_docs(self):
        """内嵌全文与只读规范真源逐字一致：唯一允许差异为结构标签与折叠空白。"""
        self._assert_embedded_matches_docs()

    def test_disclaimer_sits_in_preamble_not_user_agreement_section(self):
        """免责声明只在前言；用户协议第 9 节以「人民法院提起诉讼。」结束。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        parser = self._embedded_canonical_texts(
            self._pane_fragment(html, "agreement"), 10)
        preamble = self._norm_canonical("".join(parser.preamble), strip_ordered=False)
        law = self._norm_canonical("".join(parser.sections[9]), strip_ordered=False)
        self.assertIn(self.DISCLAIMER, preamble, "免责声明必须出现在前言")
        self.assertNotIn("不是法律意见", law, "第 9 节正文不得出现免责声明")
        self.assertTrue(law.endswith("人民法院提起诉讼。"),
                        "第 9 节必须以规范原文「人民法院提起诉讼。」结束")

    def test_offline_note_lives_outside_canonical_comparison_flow(self):
        """「本份条款可离线阅读」是独立 UI 包装：规范正文与真源文件里都没有它。
        （20261108-c3-dialogs decisions 第 1 条：要点视图连同这句离线提示一起删除，
        阅读器只呈现全文——界面包装里也不再出现。）"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        for pane, _, count in self.TERMS_DOCS:
            parser = self._embedded_canonical_texts(
                self._pane_fragment(html, pane), count)
            self.assertNotIn(self.OFFLINE_NOTE, "".join(parser.all_text),
                             "离线提示不得进入规范正文比较流：" + pane)
        self.assertNotIn(self.OFFLINE_NOTE, html,
                         "要点视图删除后，离线提示不再出现在界面包装里")
        for path in self.TERMS_DOC_PATHS:
            docs = (LOCAL.parent / path).read_text(encoding="utf-8")
            self.assertNotIn(self.OFFLINE_NOTE, docs,
                             "界面提示不得写入规范真源：" + path)

    def test_preamble_maintenance_sentence_is_known_exclusion(self):
        """已知排除项：规范来源维护说明句只在 docs 前言，内嵌前言按计划不呈现。"""
        maint = re.sub(r"\s+", "", self.MAINTENANCE_NOTE)
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        docs = "".join((LOCAL.parent / path).read_text(encoding="utf-8")
                       for path in self.TERMS_DOC_PATHS)
        # docs 侧必须做结构规范化再比较（剥 Markdown 标记、行首有序标记、标题符
        # 并折叠空白）：该句在 docs 里位于 blockquote 中，裸折叠空白会留下 `>`
        # 块引用符导致误报不一致。前言取 `^## 1\.` 之前，先断言分界存在；不能
        # 复用 _docs_canonical_texts 的前言——它已剔除本排除项。
        boundary = re.search(r"^## 1\.", docs, flags=re.M)
        self.assertIsNotNone(boundary, "docs 必须存在 `## 1.` 章节分界")
        preamble_raw = docs[:boundary.start()]
        self.assertIn(maint, self._norm_canonical(preamble_raw, strip_ordered=True),
                      "docs 前言必须保留规范来源说明")
        for pane, _, count in self.TERMS_DOCS:
            parser = self._embedded_canonical_texts(
                self._pane_fragment(html, pane), count)
            self.assertNotIn(maint, self._norm_canonical("".join(parser.preamble),
                                                         strip_ordered=False),
                             "内嵌前言按计划排除规范来源说明句：" + pane)

    def test_parity_rejects_text_outside_section_buckets(self):
        """桶外额外正文必须被全文容器比较抓住：只比章节桶不算一致。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        anchor = '<div class="terms-section terms-preamble">'
        self.assertEqual(html.count(anchor), len(self.TERMS_DOCS))
        changed = html.replace(anchor, '<p>额外条款句。</p>' + anchor, 1)
        with self.assertRaises(AssertionError):
            self._assert_embedded_matches_docs(changed)

    def test_parity_keeps_literal_markdown_characters_in_html(self):
        """HTML 里的 **、`、# 是可见文字，不得被规范化当 Markdown 抹掉。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        anchor = "本条款适用中华人民共和国法律。"
        self.assertEqual(html.count(anchor), 1)
        for marker in ("**", "`", "# "):
            with self.subTest(marker=marker):
                changed = html.replace(anchor, "\n" + marker + anchor, 1)
                with self.assertRaises(AssertionError):
                    self._assert_embedded_matches_docs(changed)

    def test_parity_accepts_text_preserving_html_wrapper(self):
        """仅标签包装不改变可见文字：只折叠空白仍判相等。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        anchor = "本条款适用中华人民共和国法律。"
        self.assertEqual(html.count(anchor), 1)
        changed = html.replace(anchor, "<span>" + anchor + "</span>", 1)
        self._assert_embedded_matches_docs(changed)

    def test_parity_accepts_pure_structural_nested_div(self):
        """纯结构嵌套 div 不提前封桶：字符顺序不变时仍相等（深度边界正向样例）。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        # 取用户协议 pane 的第 1 节做样例：它后面必然还有下一节，
        # 用最后一节会因为「下一个 terms-section」落到另一份文档而切歪。
        pane_head = html.index('id="doc-terms-agreement"')
        start = html.index('<div class="terms-section">', pane_head)
        self.assertNotEqual(start, -1, "第 1 节开标签必须存在")
        end = html.index('<div class="terms-section">', start + 1)
        open_tag = '<div class="terms-section">'
        block = html[start:end]
        self.assertEqual(len(re.findall(re.escape(block), html)), 1, "第 1 节块必须唯一")
        content = block[len(open_tag):block.rfind("</div>")]
        wrapped_block = open_tag + "<div>" + content + "</div></div>"
        changed = html[:start] + wrapped_block + html[end:]
        self._assert_embedded_matches_docs(changed)

    def test_terms_dialog_structure_contract(self):
        """三层布局结构契约（HTMLParser 只查父子归属与 ID 唯一性）：
        head/body/foot 都是同一 dialog 的直接子级、正文控件全部在唯一
        terms-body 血统内、底栏三动作相对顺序不变、全文默认 hidden 且
        aria-controls 关联正确。不声称能证明 CSS 滚动或按钮可见——
        那些必须由后续授权的浏览器测量负责。"""
        from html.parser import HTMLParser

        class _LayoutParser(HTMLParser):
            VOID = {"br", "img", "input", "meta", "link", "hr",
                    "area", "base", "col", "embed", "source", "track", "wbr"}
            # 结构类名按优先级取首个作为规范标记，避免 dlg-foot/terms-foot
            # 这种双类名容器被记成 .dlg-foot 导致归属断言落空
            # （terms-toolbar/terms-summary 已随要点视图删除，decisions 第 1 条）
            STRUCT = ("terms-head", "terms-body", "terms-feedback", "terms-foot",
                      "help-esc")

            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.stack = []   # [(tag, attrs_dict)]
                self.ids = {}     # id -> 出现次数
                self.info = {}    # 关键标记 -> {parent, ancestors, attrs, order}
                self._seq = 0

            @classmethod
            def _marker(cls, tag, attrs):
                if attrs.get("id"):
                    return "#" + attrs["id"]
                tokens = (attrs.get("class") or "").split()
                for struct in cls.STRUCT:
                    if struct in tokens:
                        return "." + struct
                if tokens:
                    return "." + tokens[0]
                return "<" + tag + ">"

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                parent = (self._marker(*self.stack[-1]) if self.stack else None)
                ancestors = [self._marker(t, a) for t, a in self.stack]
                interest = []
                if attrs.get("id"):
                    self.ids[attrs["id"]] = self.ids.get(attrs["id"], 0) + 1
                    interest.append("#" + attrs["id"])
                tokens = set((attrs.get("class") or "").split())
                for struct in self.STRUCT:
                    if struct in tokens:
                        interest.append("." + struct)
                if tag == "form" and attrs.get("method") == "dialog":
                    interest.append("<form#dialog>")
                # 只记录条款 dialog 内部的元素（帮助弹窗也有自己的 help-esc）
                if interest and ("#dlg-terms" in ancestors or "#dlg-terms" in interest):
                    self._seq += 1
                    for key in interest:
                        self.info.setdefault(key, {
                            "parent": parent,
                            "ancestors": ancestors,
                            "attrs": attrs,
                            "order": self._seq,
                        })
                if tag not in self.VOID:
                    self.stack.append((tag, attrs))

            def handle_endtag(self, tag):
                for i in range(len(self.stack) - 1, -1, -1):
                    if self.stack[i][0] == tag:
                        del self.stack[i:]
                        break

        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        parser = _LayoutParser()
        parser.feed(html)
        parser.close()

        self.assertIsNotNone(parser.info.get("#dlg-terms"), "条款 dialog 必须存在")
        # head/body/foot 均为 dialog 直接子级：放错层级会改变滚动归属
        for key in (".terms-head", ".terms-body", ".terms-foot"):
            el = parser.info.get(key)
            self.assertIsNotNone(el, "缺失结构区：" + key)
            self.assertEqual(el["parent"], "#dlg-terms",
                             key + " 必须是 dialog 的直接子级，不许塞进 body")
        # 阅读区是唯一滚动区：以下控件必须位于 terms-body 血统内
        # （terms-toolbar/terms-summary 已删，阅读器只呈现全文）
        for key in ("#dlg-terms-sub",
                    "#dlg-terms-full-text", "#dlg-terms-status",
                    "#btn-terms-recheck", ".terms-feedback", ".help-esc"):
            el = parser.info.get(key)
            self.assertIsNotNone(el, "阅读区内缺失：" + key)
            self.assertIn(".terms-body", el["ancestors"],
                          key + " 必须位于唯一阅读区 terms-body 内")
        # 标题与 X 关闭都在 head
        self.assertIn(".terms-head",
                      parser.info["#dlg-terms-title"]["ancestors"],
                      "标题必须在 terms-head 内")
        x_form = parser.info.get("<form#dialog>")
        self.assertIsNotNone(x_form, "右上角 X 必须走 method=dialog 原生关闭")
        self.assertIn(".terms-head", x_form["ancestors"],
                      "X 关闭表单必须在 terms-head 内")
        # 底栏三动作都在 foot，且相对顺序不变
        for key in ("#btn-terms-close", "#btn-terms-decline", "#btn-terms-accept"):
            el = parser.info.get(key)
            self.assertIsNotNone(el, "底栏缺失：" + key)
            self.assertEqual(el["parent"], ".terms-foot",
                             key + " 必须是 terms-foot 的直接子级")
        orders = [parser.info[k]["order"] for k in
                  ("#btn-terms-close", "#btn-terms-decline", "#btn-terms-accept")]
        self.assertEqual(orders, sorted(orders),
                         "底栏动作相对顺序必须保持 close→decline→accept")
        # 全文默认隐藏；阅读器只呈现全文（要点视图已删，无切换钮可断言）
        full = parser.info["#dlg-terms-full-text"]
        self.assertIn("hidden", full["attrs"], "全文区默认必须 hidden")
        # 关键 ID 全文唯一（结构契约的前提）
        for dom_id in ("dlg-terms", "dlg-terms-title", "dlg-terms-sub",
                       "dlg-terms-full-text",
                       "dlg-terms-status", "btn-terms-recheck",
                       "btn-terms-close", "btn-terms-decline",
                       "btn-terms-accept", "dlg-terms-document-version",
                       "dlg-terms-version"):
            self.assertEqual(parser.ids.get(dom_id), 1, "ID 必须唯一：" + dom_id)
        # FU01/TM08：两个小框的 ID 也必须唯一（不与阅读器共用节点）
        for dom_id in ("dlg-terms-intro", "dlg-terms-intro-title",
                       "dlg-terms-intro-sub", "chk-terms-intro-agree",
                       "btn-terms-intro-decline", "btn-terms-intro-accept",
                       "dlg-terms-update", "dlg-terms-update-title",
                       "terms-update-version", "terms-update-from",
                       "terms-update-list", "btn-tu-decline", "btn-tu-accept"):
            self.assertEqual(parser.ids.get(dom_id), 1, "ID 必须唯一：" + dom_id)

    def test_intro_title_keeps_focus_target_but_draws_no_focus_ring(self):
        """首次说明框打开时焦点落在标题（tabindex=-1，读屏照读），但不画蓝色焦点框（原型没有）。"""
        html = read("ui/index.html")
        self.assertIn('<h2 id="dlg-terms-intro-title" tabindex="-1">', html, "焦点落点不变")
        css = read("ui/styles.css")
        self.assertRegex(
            css,
            r"\.dlg-terms-intro \.dlg-head h2:focus,\s*\.dlg-terms-intro \.dlg-head h2:focus-visible\s*\{\s*outline:\s*none;")


class TermsConsentBehaviorTests(unittest.TestCase):
    """决策 013 / 条款同意门：首弹、拒绝不重弹、同意持久化解锁、版本变更再提示。"""

    TERMS = {"version": "2026-10-27", "accepted_version": "", "accepted_at": ""}

    def test_first_boot_opens_terms_and_blocks_network_actions(self):
        """首次未同意：弹一次条款；登录/列表/报名计划都不发起学校网络动作。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  login: () => { calls.push("login"); return new Promise(() => {}); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
/* decisions 第 1 条：首启自动弹的是首次说明框，不再直接开全文阅读器 */
const opened = document.querySelector("#dlg-terms-intro").open;
const readerOpen = document.querySelector("#dlg-terms").open;
refresh(false);
doLogin();
startPlan();
await Promise.resolve(); await Promise.resolve();
out.push({ opened, readerOpen, calls,
  loginDisabled: document.querySelector("#btn-login").disabled,
  refreshDisabled: document.querySelector("#btn-refresh").disabled,
  planDisabled: document.querySelector("#btn-plan").disabled,
  banner: document.querySelector("#banners").innerHTML });
""")
        case = res[0]
        self.assertTrue(case["opened"], "首次未同意必须弹首次说明框（FU01）")
        self.assertFalse(case["readerOpen"], "首启不再直接开全文阅读器（decisions 第 1 条）")
        self.assertEqual(case["calls"], [], "未同意时不得发起任何学校网络动作")
        self.assertTrue(case["loginDisabled"], "登录按钮必须禁用")
        self.assertTrue(case["refreshDisabled"], "刷新按钮必须禁用")
        self.assertTrue(case["planDisabled"], "开始按钮必须禁用")
        self.assertIn("使用条款", case["banner"], "必须挂条款横幅提供再同意入口")

    def test_terms_banner_splits_update_from_never_agreed(self):
        """TM06（原型 Main:2138）：有旧版同意记录 → 「使用条款更新了，还没有同意新版。」；
        从没同意或拒绝过 → 保留现有「还没有同意使用条款。」与各自分支正文。"""
        res = run_js(WB_STAMP_JS + r"""
const banner = () => { paintBanners(); return document.querySelector("#banners").innerHTML.replace(/<[^>]*>/g, ""); };
S.terms.version = "v2"; S.terms.acceptedVersion = "v1"; S.terms.declined = false;
const updated = banner();
S.terms.acceptedVersion = ""; S.terms.declined = true;
const never = banner();
S.terms.acceptedVersion = ""; S.terms.declined = false;
const fresh = banner();
out.push({ updated, never, fresh });
""")
        r = res[0]
        self.assertIn("使用条款更新了，还没有同意新版。", r["updated"])
        self.assertIn("同意后才能登录、查看活动和开始报名计划。", r["updated"],
                      "更新分支正文照原型")
        self.assertNotIn("使用条款更新了", r["never"])
        self.assertIn("还没有同意使用条款。", r["never"])
        self.assertIn("登录、活动列表和报名计划保持停用。", r["never"], "拒绝过保留现有分支正文")
        self.assertIn("还没有同意使用条款。", r["fresh"])
        self.assertIn("同意后才能登录、查看活动列表与开始报名计划。", r["fresh"],
                      "从没同意保留现有分支正文")

    def test_terms_unknown_banner_two_sentences_and_log_once(self):
        """TM07（原型 Main:2138/1180）：未知态横幅拆两句；运行记录只写一次，
        标志位在重复触发与 addLog 去重窗口之外仍然成立，读到版本后复位。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false;
S.prefs = {};
markTermsUnknown();
const banner = document.querySelector("#banners").innerHTML.replace(/<[^>]*>/g, "");
const logText = document.querySelector("#log")._children.map((row) => row.textContent).join("\n");
const rows1 = document.querySelector("#log")._children.length;
S.recentLogs.length = 0;   /* 绕开 addLog 的同句去重，证明「只写一次」靠标志位 */
markTermsUnknown();
const rows2 = document.querySelector("#log")._children.length;
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
S.recentLogs.length = 0;
markTermsUnknown();
const rows3 = document.querySelector("#log")._children.length;
out.push({ banner, logText, rows1, rows2, rows3 });
""")
        r = res[0]
        self.assertIn("条款状态没能确认。", r["banner"])
        self.assertIn("读不到你同意过哪一版。", r["banner"], "TM07：正文第一句照原型")
        self.assertIn("登录、活动列表和报名计划暂时停用，打开条款重新确认后恢复。", r["banner"])
        self.assertIn("[!] 没读到条款同意记录，学校相关操作已暂停", r["logText"])
        self.assertEqual(r["rows1"], 1, "未知态写一条运行记录")
        self.assertEqual(r["rows2"], 1, "重复触发不刷屏（标志位，不靠 addLog 去重）")
        self.assertEqual(r["rows3"], 2, "读到版本后标志位复位，下一次未知再写")

    def test_terms_meta_line_follows_real_state(self):
        """TM02（原型 Main:1571 句式）：版本句恒在（unknown 写「尚未确认」），
        状态段按真实状态拼——旧版没同意 / 还没同意 / 已同意当前版（不留旧版段）。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false;
S.prefs = {};
S.terms.prompted = true;   /* 不自动弹窗，只看元信息行 */
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
const fresh = { ver: document.querySelector("#dlg-terms-version").textContent,
                state: document.querySelector("#terms-sub-state").innerHTML };
ingestTerms({ version: "2026-10-28", accepted_version: "2026-10-27", accepted_at: "" });
const updated = document.querySelector("#terms-sub-state").innerHTML;
S.terms.unknown = true; S.terms.version = ""; S.terms.acceptedVersion = "";
paintTerms();
const unknown = { ver: document.querySelector("#dlg-terms-version").textContent,
                  state: document.querySelector("#terms-sub-state").innerHTML };
S.terms.unknown = false; S.terms.version = "2026-10-28"; S.terms.acceptedVersion = "2026-10-28";
paintTerms();
const agreed = document.querySelector("#terms-sub-state").innerHTML;
out.push({ fresh, updated, unknown, agreed });
""")
        r = res[0]
        self.assertEqual(r["fresh"], {"ver": "2026-10-27", "state": "你还没有同意。"})
        self.assertEqual(r["updated"], "你之前同意的是 <b>2026-10-27</b>，新版还没同意。")
        self.assertEqual(r["unknown"], {"ver": "尚未确认", "state": ""},
                         "unknown 不声称任何同意状态")
        self.assertEqual(r["agreed"], "", "已同意当前版不显示旧版段")

    def test_terms_close_intent_mode_bit(self):
        """TM01 × 三语义（FU01/TM08 已接线）：未知态直开的阅读器 ×＝「关闭」；
        从首启说明框打开的 ×＝「回到原来的小框」，关掉全文小框被唤回；
        横幅入口（未同意）按路由先进首次说明框。"""
        res = run_js(r"""
window.pywebview = { api: {} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTerms("banner");   /* 从没同意过：横幅入口路由进首次说明框（FU01） */
const routedToIntro = document.querySelector("#dlg-terms-intro").open;
const readerWhileIntro = document.querySelector("#dlg-terms").open;
openTermsReader("intro");   /* 「现在就看」同款入口（app.js 委托同路径） */
const fromIntro = termsCloseIntent();
const backTarget = S.terms.box;
const dlg = document.querySelector("#dlg-terms");
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
const backReopened = document.querySelector("#dlg-terms-intro").open;
const readerAfterBack = dlg.open;
/* 未知态：直接开全文阅读器，×＝关闭 */
markTermsUnknown();
openTerms();
const fromUnknown = termsCloseIntent();
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
out.push({ routedToIntro, readerWhileIntro, fromIntro, backTarget,
  backReopened, readerAfterBack, fromUnknown });
""")
        r = res[0]
        self.assertTrue(r["routedToIntro"], "未同意的横幅入口路由进首次说明框")
        self.assertFalse(r["readerWhileIntro"], "小框在场时阅读器没被同时打开")
        self.assertEqual(r["fromIntro"], "back", "从说明框打开的全文 ×＝回小框")
        self.assertEqual(r["backTarget"], "intro", "等待返回的小框登记为 intro")
        self.assertTrue(r["backReopened"], "全文关掉后首次说明框被唤回")
        self.assertFalse(r["readerAfterBack"], "回小框后阅读器关闭")
        self.assertEqual(r["fromUnknown"], "close", "未知态直开的全文 × 只等于关闭")

    def test_accept_persists_unlocks_and_reloads(self):
        """同意：走后端 accept_terms 落盘，解锁网络动作并补上首轮加载。"""
        res = run_js(r"""
let calls = [], saved = [], accepted = 0, sentDocVersion = [];
window.pywebview = { api: {
  accept_terms: (documentVersion) => {
    accepted += 1;
    sentDocVersion.push(documentVersion);
    return Promise.resolve({ ok: true, terms: { version: "2026-10-27",
      accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } });
  },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
/* 内嵌全文版本字段（生产取自 index.html）；harness 的 DOM 桩不解析 HTML，
 * 这里按真实页面写入同版，才能验证「回执版本 == 用户读到的版本」的校验 */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ accepted, calls, saved, sentDocVersion,
  docNode: document.querySelector("#dlg-terms-document-version").textContent,
  dialogOpen: document.querySelector("#dlg-terms").open,
  introOpen: document.querySelector("#dlg-terms-intro").open,
  loginDisabled: document.querySelector("#btn-login").disabled,
  refreshDisabled: document.querySelector("#btn-refresh").disabled,
  banner: document.querySelector("#banners").innerHTML });
""")
        case = res[0]
        self.assertEqual(case["accepted"], 1, "同意必须恰好调用一次后端接口")
        self.assertEqual(case["sentDocVersion"], [case["docNode"]],
                         "提交的 documentVersion 必须等于可见内嵌版本节点")
        self.assertEqual(case["calls"], ["check", "list"],
                         "同意后要补上被拦下的首轮加载")
        self.assertIn({"terms_declined_version": ""}, case["saved"],
                      "同意后要清掉拒绝版本标记")
        self.assertFalse(case["dialogOpen"], "同意成功必须关掉条款弹窗")
        self.assertFalse(case["introOpen"], "全文里同意＝小框里同意：首次说明框一并关闭")
        self.assertFalse(case["loginDisabled"], "同意后登录必须解锁")
        self.assertNotIn("使用条款", case["banner"], "同意后必须撤掉条款横幅")

    def test_accept_requires_agree_checkbox(self):
        """方案 A：没勾「我已阅读以上全部条款」时同意无效——零请求、留提示、门禁不动。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1; return Promise.resolve({ ok: true }); },
  check: () => new Promise(() => {}),
  list_activities: () => new Promise(() => {}),
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
/* 复选框保持未勾选：点同意必须什么都不做 */
document.querySelector("#chk-terms-agree").checked = false;
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve();
out.push({ accepted,
  status: document.querySelector("#dlg-terms-status").textContent,
  dialogOpen: document.querySelector("#dlg-terms").open,
  loginDisabled: document.querySelector("#btn-login").disabled });
""")
        case = res[0]
        self.assertEqual(case["accepted"], 0, "未勾选时不得调用任何写入")
        self.assertIn("勾选", case["status"], "必须说明为什么没解锁")
        self.assertTrue(case["dialogOpen"], "门禁未解除时弹窗必须留在原地")
        self.assertTrue(case["loginDisabled"], "未勾选时登录保持禁用")

    def test_accept_failure_keeps_dialog_open_with_reason(self):
        """保存失败（prefs_busy）：留在弹窗里给重试说明，门禁保持。"""
        res = run_js(r"""
window.pywebview = { api: {
  accept_terms: () => Promise.resolve({ ok: false, text: "条款同意状态暂未保存，另一个窗口正在保存数据；请再点一次。" }),
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve();
out.push({ open: document.querySelector("#dlg-terms").open,
  statusHidden: document.querySelector("#dlg-terms-status").hidden,
  statusText: document.querySelector("#dlg-terms-status").textContent,
  locked: termsLocked() });
""")
        case = res[0]
        self.assertTrue(case["open"], "保存失败必须留在条款弹窗里")
        self.assertFalse(case["statusHidden"])
        self.assertIn("再点一次", case["statusText"], "失败说明要给出重试指引")
        self.assertTrue(case["locked"], "失败时门禁不得放行")

    def test_unknown_terms_accept_with_matching_receipt_unlocks_once(self):
        """未知态：只有回执字段齐全且版本与内嵌全文同版，才清 unknown、
        关弹窗，并且只补一次被拦下的首轮加载。"""
        res = run_js(r"""
let calls = [], saved = [], accepted = 0;
window.pywebview = { api: {
  accept_terms: () => {
    accepted += 1;
    return Promise.resolve({ ok: true, terms: { version: "2026-11-09-r6",
      accepted_version: "2026-11-09-r6", accepted_at: "2026-10-27 12:00:00" } });
  },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  login: () => { calls.push("login"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
markTermsUnknown();
const lockedBefore = termsLocked();
const autoOpenBefore = document.querySelector("#dlg-terms").open;
const bannerBefore = document.querySelector("#banners").innerHTML;
openTerms();
/* 内嵌全文版本（生产取自 index.html）：harness 的 DOM 桩不解析 HTML */
document.querySelector("#dlg-terms-document-version").textContent = "2026-11-09-r6";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const after = { unknown: S.terms.unknown, locked: termsLocked(),
  version: S.terms.version, acceptedVersion: S.terms.acceptedVersion,
  acceptedAt: S.terms.acceptedAt, prompted: S.terms.prompted,
  dialogOpen: document.querySelector("#dlg-terms").open,
  loginDisabled: document.querySelector("#btn-login").disabled,
  banner: document.querySelector("#banners").innerHTML,
  calls: calls.slice(), saved: saved.slice(), accepted };
out.push({ lockedBefore, autoOpenBefore, bannerBefore, after });
""")
        case = res[0]
        self.assertTrue(case["lockedBefore"], "未知态本身必须是锁住的")
        self.assertFalse(case["autoOpenBefore"], "未知态不自动弹窗，用户点开的才可确认")
        self.assertIn("条款状态没能确认", case["bannerBefore"])
        after = case["after"]
        self.assertFalse(after["unknown"], "回执校验通过后才允许清 unknown")
        self.assertFalse(after["locked"], "确认成功必须解锁门禁")
        self.assertEqual(after["version"], "2026-11-09-r6", "要写入回执里的条款版本")
        self.assertEqual(after["acceptedVersion"], "2026-11-09-r6")
        self.assertEqual(after["acceptedAt"], "2026-10-27 12:00:00")
        self.assertTrue(after["prompted"])
        self.assertFalse(after["dialogOpen"], "确认成功必须关掉条款弹窗")
        self.assertFalse(after["loginDisabled"])
        self.assertNotIn("条款状态没能确认", after["banner"], "确认成功后撤掉未知横幅")
        self.assertEqual(after["accepted"], 1, "同意必须恰好调用一次后端接口")
        self.assertEqual(after["calls"], ["check", "list"],
                         "只补一次首轮加载（check+list 各一次），不得重复触发")
        self.assertIn({"terms_declined_version": ""}, after["saved"],
                      "确认成功要清掉拒绝版本标记")

    def test_unknown_terms_accept_rejects_bad_receipts(self):
        """未知态的残缺/矛盾/错版回执与桥接异常：一律留在弹窗、不清 unknown、
        不落盘，并继续阻止任何学校动作（fail closed，不做本地乐观更新）。"""
        res = run_js(r"""
let calls = [], saved = [], mode = "missing_at";
window.pywebview = { api: {
  accept_terms: () => {
    if (mode === "reject") return Promise.reject(new Error("桥接断了"));
    if (mode === "prefs_busy") return Promise.resolve({ ok: false, text: "条款同意状态暂未保存，另一个窗口正在保存数据；请再点一次。" });
    if (mode === "missing_at") return Promise.resolve({ ok: true, terms: { version: "2026-11-09-r6", accepted_version: "2026-11-09-r6" } });
    if (mode === "version_mismatch") return Promise.resolve({ ok: true, terms: { version: "2026-11-09-r6", accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } });
    if (mode === "doc_mismatch") return Promise.resolve({ ok: true, terms: { version: "2026-11-05-r1", accepted_version: "2026-11-05-r1", accepted_at: "2026-11-05 09:00:00" } });
  },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  login: () => { calls.push("login"); return new Promise(() => {}); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
async function probe(m, docVersion) {
  mode = m;
  markTermsUnknown();
  openTerms();
  /* 内嵌全文版本（生产取自 index.html）：doc_mismatch 用一份过期副本 */
  document.querySelector("#dlg-terms-document-version").textContent = docVersion;
  document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
  document.querySelector("#btn-terms-accept").click();
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
  const state = { open: document.querySelector("#dlg-terms").open,
    unknown: S.terms.unknown, locked: termsLocked(),
    version: S.terms.version, acceptedVersion: S.terms.acceptedVersion,
    status: document.querySelector("#dlg-terms-status").textContent };
  refresh(false);
  doLogin();
  startPlan();
  return state;
}
const missingAt = await probe("missing_at", "2026-11-09-r6");
const versionMismatch = await probe("version_mismatch", "2026-11-09-r6");
const docMismatch = await probe("doc_mismatch", "2026-11-09-r6");
const prefsBusy = await probe("prefs_busy", "2026-11-09-r6");
const bridgeReject = await probe("reject", "2026-11-09-r6");
out.push({ missingAt, versionMismatch, docMismatch, prefsBusy, bridgeReject,
  calls, saved });
""")
        data = res[0]
        expect = {
            "missingAt": "缺字段",
            "versionMismatch": "自相矛盾",
            "docMismatch": "当前条款副本不匹配",
            "prefsBusy": "再点一次",
            "bridgeReject": "再点一次",
        }
        for name, hint in expect.items():
            case = data[name]
            self.assertTrue(case["open"], "%s：失败必须留在条款弹窗里" % name)
            self.assertTrue(case["unknown"], "%s：失败不得清 unknown" % name)
            self.assertTrue(case["locked"], "%s：失败时门禁不得放行" % name)
            self.assertEqual(case["version"], "", "%s：不得写入任何条款版本" % name)
            self.assertEqual(case["acceptedVersion"], "",
                             "%s：不得本地乐观标记为已同意" % name)
            self.assertIn(hint, case["status"], "%s：失败说明要讲清原因" % name)
        self.assertEqual(data["calls"], [],
                         "所有失败路径都不得发起任何学校动作")
        self.assertEqual(data["saved"], [], "失败时不得落盘任何同意标记")

    def test_decline_does_not_reprompt_and_keeps_help_available(self):
        """拒绝：不退出、不再强弹；帮助与条款入口仍可用，网络动作保持禁用。"""
        res = run_js(r"""
let calls = [], saved = [];
window.pywebview = { api: {
  login: () => { calls.push("login"); return new Promise(() => {}); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
/* decisions 第 1 条：首启强弹的是首次说明框，「暂不使用」是它的拒绝钮 */
const firstOpen = document.querySelector("#dlg-terms-intro").open;
const readerAtBoot = document.querySelector("#dlg-terms").open;
document.querySelector("#btn-terms-intro-decline").click();
await Promise.resolve(); await Promise.resolve();
const afterDecline = { open: document.querySelector("#dlg-terms-intro").open,
  readerOpen: document.querySelector("#dlg-terms").open,
  declined: S.terms.declined };
refresh(false);
doLogin();
startPlan();
const reopened = document.querySelector("#dlg-terms-intro").open;
document.querySelector("#btn-help").click();
const helpOpen = document.querySelector("#help").open;
document.querySelector("#btn-help-terms").click();
/* 帮助/设置里的条款入口按同一时机路由：未同意 → 首次说明框 */
const termsFromHelp = document.querySelector("#dlg-terms-intro").open;
/* 重复拒绝回归：从帮助重开同版条款后再点暂不使用，必须仍关闭弹窗 */
document.querySelector("#btn-terms-intro-decline").click();
await Promise.resolve(); await Promise.resolve();
const afterRepeat = { open: document.querySelector("#dlg-terms-intro").open,
  declined: S.terms.declined,
  declinedWrites: saved.filter((p) => p.terms_declined_version !== undefined).length };
out.push({ firstOpen, readerAtBoot, afterDecline, reopened, helpOpen, termsFromHelp, afterRepeat,
  calls, saved,
  loginDisabled: document.querySelector("#btn-login").disabled,
  refreshDisabled: document.querySelector("#btn-refresh").disabled,
  planDisabled: document.querySelector("#btn-plan").disabled });
""")
        case = res[0]
        self.assertTrue(case["firstOpen"], "拒绝前首次说明框在场（FU01）")
        self.assertFalse(case["readerAtBoot"], "拒绝路径不再经过全文阅读器")
        self.assertFalse(case["afterDecline"]["open"], "拒绝后必须关掉说明框")
        self.assertFalse(case["afterDecline"]["readerOpen"], "拒绝后阅读器也不在场")
        self.assertTrue(case["afterDecline"]["declined"])
        self.assertFalse(case["reopened"], "拒绝后不得再强弹条款")
        self.assertEqual(case["calls"], [], "拒绝后网络动作仍全部被拦")
        self.assertTrue(case["helpOpen"], "帮助必须继续可用")
        self.assertTrue(case["termsFromHelp"], "帮助里的条款入口必须能重新打开条款说明框")
        self.assertIn({"terms_declined_version": "2026-10-27"}, case["saved"],
                      "拒绝版本必须落盘（跨重启不再强弹）")
        self.assertTrue(case["loginDisabled"])
        self.assertTrue(case["refreshDisabled"])
        self.assertTrue(case["planDisabled"])
        self.assertFalse(case["afterRepeat"]["open"], "重复拒绝必须仍关闭说明框")
        self.assertTrue(case["afterRepeat"]["declined"], "重复拒绝后 declined 仍为 true")
        self.assertEqual(case["afterRepeat"]["declinedWrites"], 1, "拒绝版本只写一次")
        self.assertEqual(case["calls"], [], "重复拒绝后网络动作仍全部被拦")

    def test_declined_version_persists_and_version_change_reprompts(self):
        """重启后同一版本不重弹；条款版本变化时重新提示（更新框，FU01/TM08 路由）。"""
        res = run_js(r"""
let saved = [];
window.pywebview = { api: {
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
document.querySelector("#btn-terms-intro-decline").click();
await Promise.resolve(); await Promise.resolve();
/* 模拟重启：全新会话，prefs 带回上次拒绝过的版本 */
S.terms = { version: "", acceptedVersion: "", acceptedAt: "", declined: false, prompted: false };
ingestTerms({ version: "2026-10-27", accepted_version: "" });
const sameVersion = document.querySelector("#dlg-terms-intro").open;
document.querySelector("#dlg-terms-intro").close();
/* 条款版本变化：重新提示（同意过旧版 → 条款更新框） */
S.terms = { version: "", acceptedVersion: "", acceptedAt: "", declined: false, prompted: false };
ingestTerms({ version: "2026-11-01", accepted_version: "2026-10-27" });
const newVersionUpdateBox = document.querySelector("#dlg-terms-update").open;
const newVersionReader = document.querySelector("#dlg-terms").open;
out.push({ saved, sameVersion, newVersionUpdateBox, newVersionReader });
""")
        case = res[0]
        self.assertIn({"terms_declined_version": "2026-10-27"}, case["saved"])
        self.assertFalse(case["sameVersion"], "重启后同一版本不得再强弹")
        self.assertTrue(case["newVersionUpdateBox"], "条款版本变化必须重新提示（条款更新框）")
        self.assertFalse(case["newVersionReader"], "版本变化不再直接开全文阅读器")

    def test_restart_restores_declined_and_blocks_autoload_chain(self):
        """重启后刷新、F5 和可见性恢复都不再强弹，也不发学校动作（返修缺陷 1）。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  login: () => { calls.push("login"); return new Promise(() => {}); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-11-09-r6", accepted_version: "", accepted_at: "" });
document.querySelector("#btn-terms-intro-decline").click();
await Promise.resolve(); await Promise.resolve();
/* 模拟重启：全新会话状态 + prefs 带回上次拒绝过的版本 */
S.terms = { version: "", acceptedVersion: "", acceptedAt: "", declined: false,
            prompted: false, unknown: false };
ingestTerms({ version: "2026-11-09-r6", accepted_version: "" });
const afterRestart = { open: document.querySelector("#dlg-terms-intro").open,
  readerOpen: document.querySelector("#dlg-terms").open,
  declined: S.terms.declined };
refresh(false);
__dispatchKey({ key: "F5" });
doLogin();
startPlan();
out.push({ afterRestart, calls,
  open: document.querySelector("#dlg-terms").open,
  introOpen: document.querySelector("#dlg-terms-intro").open });
""")
        case = res[0]
        self.assertFalse(case["afterRestart"]["open"], "重启后同一版本不得再强弹")
        self.assertFalse(case["afterRestart"]["readerOpen"], "重启后也不开阅读器")
        self.assertTrue(case["afterRestart"]["declined"],
                        "重启后必须把拒绝态恢复成会话状态，否则刷新会重复弹窗")
        self.assertEqual(case["calls"], [], "F5/刷新/可见性恢复都不得发学校动作")
        self.assertFalse(case["open"], "整条自动链路都不许再弹条款阅读器")
        self.assertFalse(case["introOpen"], "整条自动链路都不许再弹首次说明框")

    def test_unknown_terms_state_fails_closed_and_keeps_help_open(self):
        """bootstrap 失败、返回 null、缺 terms、空版本或结构非法：一律拦住。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  login: () => { calls.push("login"); return new Promise(() => {}); },
  check: (id) => { calls.push("check"); return new Promise(() => {}); },
  list_activities: (id) => { calls.push("list"); return new Promise(() => {}); },
  start_plan: () => { calls.push("start"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
function probe(payload) {
  S.terms = { version: "", acceptedVersion: "", acceptedAt: "", declined: false,
              prompted: false, unknown: false };
  document.querySelector("#dlg-terms").close();
  ingestTerms(payload);
  const locked = termsLocked();
  refresh(false);
  doLogin();
  startPlan();
  const autoOpen = document.querySelector("#dlg-terms").open;
  const banner = document.querySelector("#banners").innerHTML;
  document.querySelector("#btn-help").click();
  const helpOpen = document.querySelector("#help").open;
  document.querySelector("#btn-help-terms").click();
  const manualOpen = document.querySelector("#dlg-terms").open;
  document.querySelector("#dlg-terms").close();
  return { locked, unknown: S.terms.unknown, autoOpen, manualOpen, helpOpen, banner };
}
const nullPayload = probe(null);
const missing = probe({ version: "", accepted_version: "" });
const emptyObject = probe({});
const badType = probe("不是对象");
out.push({ nullPayload, missing, emptyObject, badType, calls });
""")
        data = res[0]
        for name in ("nullPayload", "missing", "emptyObject", "badType"):
            case = data[name]
            self.assertTrue(case["locked"], "%s：条款状态未知必须拦住学校动作" % name)
            self.assertTrue(case["unknown"], "%s：必须标记为未知态" % name)
            self.assertFalse(case["autoOpen"], "%s：未知态不自动弹窗" % name)
            self.assertTrue(case["manualOpen"], "%s：帮助里的条款入口仍可显式打开" % name)
            self.assertTrue(case["helpOpen"], "%s：帮助必须始终可用" % name)
            self.assertIn("条款状态没能确认", case["banner"], "%s：必须挂可重试横幅" % name)
        self.assertEqual(data["calls"], [], "未知态不得发起任何学校动作")

    def test_version_change_prompts_only_once(self):
        """条款版本变化只强弹一次：同版本重复 ingest 不再弹。"""
        res = run_js(r"""
S.demo = false;
S.prefs = { terms_declined_version: "2026-10-27" };
ingestTerms({ version: "2026-11-09-r6", accepted_version: "" });
/* 版本变化的强弹现在落在首次说明框（从没同意过 → FU01 路由） */
const firstOpen = document.querySelector("#dlg-terms-intro").open;
const firstReaderOpen = document.querySelector("#dlg-terms").open;
document.querySelector("#dlg-terms-intro").close();
ingestTerms({ version: "2026-11-09-r6", accepted_version: "" });
const againOpen = document.querySelector("#dlg-terms-intro").open;
document.querySelector("#dlg-terms-intro").close();
/* 已拒绝过当前版本：不再弹 */
S.prefs.terms_declined_version = "2026-11-09-r6";
S.terms = { version: "", acceptedVersion: "", acceptedAt: "", declined: false,
            prompted: false, unknown: false };
ingestTerms({ version: "2026-11-09-r6", accepted_version: "" });
const declinedOpen = document.querySelector("#dlg-terms-intro").open;
out.push({ firstOpen, firstReaderOpen, againOpen, declinedOpen });
""")
        case = res[0]
        self.assertTrue(case["firstOpen"], "版本变化必须重新提示一次（首次说明框）")
        self.assertFalse(case["firstReaderOpen"], "强弹不再直接开全文阅读器")
        self.assertFalse(case["declinedOpen"], "本版本已拒绝过就不该再弹")

    def test_demo_mode_is_not_gated(self):
        """离线演示（demo）不做学校网络动作：条款门禁不拦演示形态。"""
        res = run_js(r"""
S.demo = true;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
out.push({ opened: document.querySelector("#dlg-terms").open,
  locked: termsLocked(),
  loginDisabled: document.querySelector("#btn-login").disabled,
  banner: document.querySelector("#banners").innerHTML });
""")
        case = res[0]
        self.assertFalse(case["opened"], "演示模式不弹条款")
        self.assertFalse(case["locked"])
        self.assertFalse(case["loginDisabled"], "演示模式登录入口不受条款门禁")
        self.assertNotIn("使用条款", case["banner"])


class TermsInteractionLoopTests(unittest.TestCase):
    """close-terms-interaction-loop：在途保存、10 秒超时未确认、重新确认、
    只读查看、关闭收口、来源焦点、引导延后与条款弹窗键盘隔离的行为契约。
    DOM 桩只复用既有能力（focus/activeElement、listeners、计时器替换），
    不把 showModal/hidden 桩当排版证据。"""

    def test_double_click_saves_once_and_locks_footer(self):
        """连续点击只登记一次在途：一次请求、保存态三控件禁用、文案「正在保存…」。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1; return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
const accept = document.querySelector("#btn-terms-accept");
const decline = document.querySelector("#btn-terms-decline");
const dlg = document.querySelector("#dlg-terms");
out.push({ accepted,
  acceptDisabled: accept.disabled, acceptText: accept.textContent,
  declineDisabled: decline.disabled, xDisabled: dlg.querySelector(".dlg-x").disabled,
  escText: dlg.querySelector(".help-esc").textContent, locked: termsLocked() });
""")
        case = res[0]
        self.assertEqual(case["accepted"], 1, "保存中重复点击只能发出一次 accept_terms")
        self.assertTrue(case["acceptDisabled"])
        self.assertEqual(case["acceptText"], "正在保存…")
        self.assertTrue(case["declineDisabled"])
        self.assertTrue(case["xDisabled"])
        self.assertEqual(case["escText"], "正在保存…")
        self.assertTrue(case["locked"], "在途保存期间门禁保持")

    def test_accept_failure_restores_buttons_and_keeps_dialog(self):
        """明确失败：留在弹窗、给出原因、三控件恢复可点，不假称未确认。"""
        res = run_js(r"""
window.pywebview = { api: {
  accept_terms: () => Promise.resolve({ ok: false,
    text: "设置保存失败（设置可能正在被占用），请稍后再试。" }),
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const accept = document.querySelector("#btn-terms-accept");
const dlg = document.querySelector("#dlg-terms");
out.push({ open: dlg.open,
  acceptDisabled: accept.disabled, acceptText: accept.textContent,
  declineDisabled: document.querySelector("#btn-terms-decline").disabled,
  xDisabled: dlg.querySelector(".dlg-x").disabled,
  escText: dlg.querySelector(".help-esc").textContent, locked: termsLocked(),
  status: document.querySelector("#dlg-terms-status").textContent });
""")
        case = res[0]
        self.assertTrue(case["open"], "失败必须留在弹窗里")
        self.assertFalse(case["acceptDisabled"])
        # TM04（原型 Main:894）：同意钮名照原型改「同意并继续」
        self.assertEqual(case["acceptText"], "同意并继续")
        self.assertFalse(case["declineDisabled"])
        self.assertFalse(case["xDisabled"])
        # TM01（decisions 014 修订）：× 语义改为关闭、拒绝只走「暂不使用」钮，
        # 保存失败留在弹窗时 Esc 也只是「关闭」提示
        self.assertEqual(case["escText"], "Esc 关闭")
        self.assertTrue(case["locked"])
        self.assertIn("设置保存失败", case["status"])
        self.assertNotIn("未确认", case["status"], "明确失败不能说成未确认")

    def test_accept_success_refreshes_exactly_once_and_closes(self):
        """完整成功：关窗解锁、首轮学校加载只补一次、延后的引导只消费一次。"""
        res = run_js(r"""
let calls = [], saved = [];
window.pywebview = { api: {
  accept_terms: () => Promise.resolve({ ok: true, terms: { version: "2026-10-27",
      accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } }),
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  check: () => { calls.push("check"); return new Promise(() => {}); },
  list_activities: () => { calls.push("list"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
S.terms.deferredIntro = { tour: false, welcome: true };
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
await Promise.resolve(); await Promise.resolve();
out.push({ open: document.querySelector("#dlg-terms").open,
  locked: termsLocked(), calls, deferred: S.terms.deferredIntro,
  declinedCleared: saved.some((p) => "terms_declined_version" in p),
  focus: document.activeElement && document.activeElement.__sel });
""")
        case = res[0]
        self.assertFalse(case["open"], "成功才关弹窗")
        self.assertFalse(case["locked"])
        self.assertEqual(case["calls"], ["check", "list"], "完整成功最多补加载一次")
        self.assertIsNone(case["deferred"], "延后的引导只继续一次（消费即清空）")
        self.assertTrue(case["declinedCleared"])
        self.assertEqual(case["focus"], "#btn-help", "同意成功焦点回 #btn-help")

    def test_save_timeout_keeps_gate_reopens_close_and_drops_late_receipt(self):
        """10 秒未获可确认结果：不假称失败/取消，门禁保持、关闭权限恢复、
        禁止直接再次写同意；迟到回执不关窗、不覆盖、不重复刷新。"""
        res = run_js(r"""
let timers = [], accepted = 0, calls = [], resolveAccept = null;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1;
    return new Promise((resolve) => { resolveAccept = resolve; }); },
  check: () => { calls.push("check"); return new Promise(() => {}); },
  list_activities: () => { calls.push("list"); return new Promise(() => {}); },
} };
setTimeout = (fn) => { timers.push(fn); return timers.length; };
clearTimeout = () => {};
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
const dlg = document.querySelector("#dlg-terms");
const cancelEv = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
(dlg.listeners.cancel || []).forEach((fn) => fn(cancelEv));
const savingState = { prevented: cancelEv.defaultPrevented,
  acceptDisabled: document.querySelector("#btn-terms-accept").disabled };
timers[0](); /* 10 秒超时 → 未确认 */
const statusAfterTimeout = document.querySelector("#dlg-terms-status").textContent;
const accept = document.querySelector("#btn-terms-accept");
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click(); /* 未确认期间再点：不得再发请求 */
const afterRetryClick = accepted;
resolveAccept({ ok: true, terms: { version: "2026-10-27",
  accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } });
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const recheck = document.querySelector("#btn-terms-recheck");
out.push({ savingState, statusAfterTimeout, accepted, afterRetryClick,
  open: dlg.open, locked: termsLocked(),
  acceptDisabled: accept.disabled,
  declineDisabled: document.querySelector("#btn-terms-decline").disabled,
  xDisabled: dlg.querySelector(".dlg-x").disabled,
  recheckHidden: recheck.hidden, recheckDisabled: recheck.disabled,
  escText: dlg.querySelector(".help-esc").textContent,
  statusFinal: document.querySelector("#dlg-terms-status").textContent,
  calls });
""")
        case = res[0]
        self.assertTrue(case["savingState"]["prevented"], "保存中的 Esc 必须被 cancel 拦下")
        self.assertTrue(case["savingState"]["acceptDisabled"])
        self.assertIn("未确认", case["statusAfterTimeout"])
        self.assertNotIn("没有保存成功", case["statusAfterTimeout"], "超时不能假称失败")
        self.assertNotIn("已拒绝", case["statusAfterTimeout"], "超时不能假称取消")
        self.assertEqual(case["afterRetryClick"], 1, "未确认期间禁止直接再次写同意")
        self.assertTrue(case["open"], "迟到回执不许关窗")
        self.assertTrue(case["locked"], "迟到回执不许解锁")
        self.assertTrue(case["acceptDisabled"], "未确认期间同意按钮保持禁用")
        self.assertTrue(case["declineDisabled"])
        self.assertFalse(case["xDisabled"], "关闭权限恢复")
        self.assertFalse(case["recheckHidden"], "亮出重新确认状态")
        self.assertFalse(case["recheckDisabled"])
        self.assertEqual(case["escText"], "Esc 关闭")
        self.assertEqual(case["calls"], [], "迟到回执不许重复刷新")
        self.assertEqual(case["statusFinal"], case["statusAfterTimeout"],
                         "迟到回执不许覆盖未确认状态")
        self.assertEqual(case["accepted"], 1)

    def test_recheck_confirmed_acceptance_closes_without_new_write(self):
        """重新确认读到「已同意同版+有时间+匹配本份」：按成功收口，零新写请求。"""
        res = run_js(r"""
let timers = [], accepted = 0, calls = [], saved = [];
window.pywebview = { api: {
  accept_terms: () => { accepted += 1; return new Promise(() => {}); },
  bootstrap: () => { calls.push("bootstrap");
    return Promise.resolve({ terms: { version: "2026-10-27",
      accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } }); },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  check: () => { calls.push("check"); return new Promise(() => {}); },
  list_activities: () => { calls.push("list"); return new Promise(() => {}); },
} };
setTimeout = (fn) => { timers.push(fn); return timers.length; };
clearTimeout = () => {};
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
S.terms.deferredIntro = { tour: false, welcome: false };
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
timers[0](); /* 超时 → 未确认 */
document.querySelector("#btn-terms-recheck").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
await Promise.resolve(); await Promise.resolve();
out.push({ open: document.querySelector("#dlg-terms").open,
  locked: termsLocked(), accepted, calls, saved,
  deferred: S.terms.deferredIntro,
  focus: document.activeElement && document.activeElement.__sel });
""")
        case = res[0]
        self.assertFalse(case["open"])
        self.assertFalse(case["locked"])
        self.assertEqual(case["accepted"], 1, "重新确认不得再发同意写请求")
        self.assertEqual(case["calls"], ["bootstrap", "check", "list"],
                         "只读一次 bootstrap，成功收口补一次加载")
        self.assertTrue(any("terms_declined_version" in p for p in case["saved"]))
        self.assertIsNone(case["deferred"], "成功收口把延后引导消费掉")
        self.assertEqual(case["focus"], "#btn-help")

    def test_recheck_explicitly_not_accepted_restores_accept_button(self):
        """重新确认读到明确未同意：恢复同意按钮与关闭语义，可再点一次。"""
        res = run_js(r"""
let timers = [], accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1; return new Promise(() => {}); },
  bootstrap: () => Promise.resolve({ terms: { version: "2026-10-27",
    accepted_version: "", accepted_at: "" } }),
} };
setTimeout = (fn) => { timers.push(fn); return timers.length; };
clearTimeout = () => {};
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
timers[0]();
document.querySelector("#btn-terms-recheck").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const recheck = document.querySelector("#btn-terms-recheck");
out.push({ open: document.querySelector("#dlg-terms").open,
  locked: termsLocked(), accepted,
  acceptDisabled: document.querySelector("#btn-terms-accept").disabled,
  recheckHidden: recheck.hidden,
  escText: document.querySelector("#dlg-terms .help-esc").textContent,
  status: document.querySelector("#dlg-terms-status").textContent });
""")
        case = res[0]
        self.assertTrue(case["open"])
        self.assertTrue(case["locked"], "明确未同意门禁保持")
        self.assertFalse(case["acceptDisabled"], "恢复同意按钮供重试")
        self.assertTrue(case["recheckHidden"], "未确认态收口后收起重新确认")
        # TM01（decisions 014 修订）：Esc 只等于关闭，不再有「Esc 暂不使用」
        self.assertEqual(case["escText"], "Esc 关闭")
        self.assertIn("尚未记录同意", case["status"])
        self.assertEqual(case["accepted"], 1)

    def test_recheck_read_failure_keeps_unconfirmed(self):
        """重新确认读取失败：仍按未确认处理，按钮恢复可点，门禁保持。"""
        res = run_js(r"""
let timers = [], accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1; return new Promise(() => {}); },
  bootstrap: () => Promise.reject(new Error("桥接断了")),
} };
setTimeout = (fn) => { timers.push(fn); return timers.length; };
clearTimeout = () => {};
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
timers[0]();
document.querySelector("#btn-terms-recheck").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const recheck = document.querySelector("#btn-terms-recheck");
out.push({ open: document.querySelector("#dlg-terms").open,
  locked: termsLocked(), accepted,
  acceptDisabled: document.querySelector("#btn-terms-accept").disabled,
  recheckHidden: recheck.hidden, recheckDisabled: recheck.disabled,
  recheckText: recheck.textContent,
  status: document.querySelector("#dlg-terms-status").textContent });
""")
        case = res[0]
        self.assertTrue(case["open"])
        self.assertTrue(case["locked"])
        self.assertTrue(case["acceptDisabled"], "读取失败不恢复同意按钮")
        self.assertFalse(case["recheckHidden"])
        self.assertFalse(case["recheckDisabled"], "重新确认恢复可点")
        self.assertEqual(case["recheckText"], "重新确认状态")
        self.assertIn("没能读到", case["status"])
        self.assertIn("未确认", case["status"])
        self.assertEqual(case["accepted"], 1)

    def test_readonly_view_makes_no_writes_and_restores_settings_focus(self):
        """已同意查看：只读（只显示关闭），关闭零 accept/save/学校调用；
        关闭后不把帮助弹出来，焦点回设置里的「查看条款」入口。

        帮助里的条款入口已按原型 :744-746 删除，条款只剩「设置 → 条款与隐私」；
        terms.js 里 source=help 的归还分支保留为兜底（入口找不到时落到 #btn-help）。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  accept_terms: () => { calls.push("accept"); return Promise.resolve({ ok: true }); },
  save_prefs: () => { calls.push("save"); return Promise.resolve({ ok: true }); },
  check: () => { calls.push("check"); return new Promise(() => {}); },
  list_activities: () => { calls.push("list"); return new Promise(() => {}); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "2026-10-27",
  accepted_at: "2026-10-27 12:00:00" });
const help = document.querySelector("#help");
const dlg = document.querySelector("#dlg-terms");
const accept = document.querySelector("#btn-terms-accept");
const decline = document.querySelector("#btn-terms-decline");
/* 设置抽屉里的入口：打开后先取只读态底部的 Esc 文案，再关闭验证焦点归还 */
document.querySelector("#btn-help-terms").click();
const escBefore = dlg.querySelector(".help-esc").textContent;
dlg.close();
(dlg.listeners.close || []).forEach((fn) => fn());
const fromSettings = { helpOpen: help.open, focus: document.activeElement && document.activeElement.__sel };
out.push({ calls, declined: S.terms.declined,
  acceptHidden: accept.hidden, declineHidden: decline.hidden,
  closeHidden: document.querySelector("#btn-terms-close").hidden,
  recheckHidden: document.querySelector("#btn-terms-recheck").hidden,
  xDisabled: dlg.querySelector(".dlg-x").disabled, escBefore,
  fromSettings, lockedAfter: termsLocked() });
""")
        case = res[0]
        self.assertEqual(case["calls"], [], "只读查看零 accept/save/学校调用")
        self.assertFalse(case["declined"], "只读关闭不记拒绝")
        self.assertTrue(case["acceptHidden"])
        self.assertTrue(case["declineHidden"])
        self.assertFalse(case["closeHidden"], "只读只显示关闭")
        self.assertTrue(case["recheckHidden"])
        self.assertFalse(case["xDisabled"])
        self.assertEqual(case["escBefore"], "Esc 关闭")
        self.assertFalse(case["fromSettings"]["helpOpen"], "从设置打开的，关闭后不把帮助弹出来")
        self.assertEqual(case["fromSettings"]["focus"], "#btn-help-terms", "焦点回设置里的「查看条款」")
        self.assertFalse(case["lockedAfter"])

    def test_viewonly_status_merges_consent_into_one_line(self):
        """只读查看（已同意同版）：状态行合并为一行好消息（用户拍板的合并
        精简，20261031）——两处书名号仍是 doc-link 蓝链、版本用 <b>、时间
        「月-日 时:分」当年内省略年份；整行不再出现「程序要求版本」版本句，
        #dlg-terms-sub 在只读态收起。未同意首跑与版本不一致分支不走这里，
        文案不动（另路径，各有用例钉住）。vm 假元素只忠实 textContent/hidden，
        data-tone/computed color/按钮结构由浏览器场景 terms-status-viewonly 钉。"""
        res = run_js(r"""
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-11-09-r6", accepted_version: "2026-11-09-r6",
  accepted_at: "2026-10-27 12:00:00" });
document.querySelector("#btn-help-terms").click();
const sub = document.querySelector("#dlg-terms-sub");
out.push({
  subHidden: sub.hidden,
  /* vm 假元素不聚合 innerHTML：合并行文案用纯函数 builder 直接断言，
     渲染态（data-tone/computed color/按钮可点）由浏览器场景钉 */
  line: termsViewOnlyLineHtml("2026-11-09-r6", "2026-10-27 12:00:00"),
});
""")
        case = res[0]
        self.assertTrue(case["subHidden"], "只读态收起副行，版本句不再重复显示")
        line = case["line"]
        text = re.sub(r"<[^>]+>", "", line)   # 渲染后的纯文本口径
        self.assertIn("已同意", text)
        self.assertIn("《用户协议》与《隐私政策》", text, "书名号整句进状态行")
        self.assertEqual(line.count('class="doc-link" data-doc='), 2,
                         "两处书名号仍是可点的 doc-link 蓝链")
        self.assertIn("<b>2026-11-09-r6</b>", line, "版本号用 <b> 保留")
        self.assertIn("（10-27 12:00 同意）", text,
                      "当年内时间省略年份：月-日 时:分")
        self.assertIn("更新后会再次展示并要求重新同意", text)
        self.assertNotIn("程序要求版本", text, "版本句合并进一行，不再复读")
        self.assertNotIn("同意后才能", text)

    def test_consent_time_text_omits_year_only_within_same_year(self):
        """consentTimeText：当年「月-日 时:分」；跨年保留完整年份；
        原文不合法原样返回（不编造日期）。"""
        res = run_js(r"""
setBusinessNow(new Date(Date.UTC(2026, 9, 31, 2, 13, 0)).getTime());
const sameYear = consentTimeText("2026-10-27 12:00:00");
setBusinessNow(new Date(Date.UTC(2027, 0, 2, 2, 0, 0)).getTime());
const crossYear = consentTimeText("2026-10-27 12:00:00");
const unparsable = consentTimeText("同意时间未记录");
out.push({ sameYear, crossYear, unparsable });
""")
        case = res[0]
        self.assertEqual(case["sameYear"], "10-27 12:00")
        self.assertEqual(case["crossYear"], "2026-10-27 12:00", "跨年保留完整年份")
        self.assertEqual(case["unparsable"], "同意时间未记录", "不合法原文原样返回")

    def test_reader_shows_full_text_only_and_never_saves(self):
        """阅读器只呈现全文（decisions 第 1 条：要点视图与切换钮已删）——
        打开即全文可见、阅读区滚回顶部、零保存零学校调用。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  save_prefs: () => { calls.push("save"); return Promise.resolve({ ok: true }); },
  accept_terms: () => { calls.push("accept"); return Promise.resolve({ ok: true }); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
/* 静态 HTML 里全文区默认 hidden（结构契约钉住默认态）：打开路径必须自己取消隐藏，
 * 否则页签/目录正常而正文空白（visual-verify 2026-11-08 截到的缺陷）。 */
document.querySelector("#dlg-terms-full-text").hidden = true;
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
const full = document.querySelector("#dlg-terms-full-text");
const body = document.querySelector(".terms-body");
body.scrollTop = 40;
resetTermsReaderView(); /* 每次打开前的复位路径（openTermsReader 内调用同一函数） */
out.push({ fullVisible: !full.hidden, scrollTop: body.scrollTop,
  toggleGone: !__els.has("#btn-terms-full"),
  summaryGone: !__els.has("#dlg-terms-summary"),
  calls, open: document.querySelector("#dlg-terms").open });
""")
        case = res[0]
        self.assertTrue(case["fullVisible"], "阅读器打开即全文，无要点视图")
        self.assertEqual(case["scrollTop"], 0, "复位把阅读区滚回顶部")
        self.assertTrue(case["toggleGone"], "要点/全文切换钮已删")
        self.assertTrue(case["summaryGone"], "要点视图容器已删")
        self.assertEqual(case["calls"], [], "打开阅读器绝不保存")
        self.assertTrue(case["open"])

    def test_close_without_acceptance_only_closes_and_never_declines(self):
        """TM01（decisions 014 修订）＋FU01/TM08（decisions 第 1 条）：全文里
        未同意时 Esc/X 只等于「关闭」——不落盘、不记拒绝，并且回到等在后面的
        首次说明框（不等于拒绝，拒绝只走「暂不使用」钮）；门禁保持、横幅还在。"""
        res = run_js(r"""
let saved = [];
window.pywebview = { api: {
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
} };
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 从首启说明框进来：× 模式位＝back */
const dlg = document.querySelector("#dlg-terms");
const cancelEv = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
(dlg.listeners.cancel || []).forEach((fn) => fn(cancelEv));
dlg.close();
(dlg.listeners.close || []).forEach((fn) => fn());
out.push({ prevented: cancelEv.defaultPrevented, declined: S.terms.declined,
  saved, locked: termsLocked(), readerOpen: dlg.open,
  introReopened: document.querySelector("#dlg-terms-intro").open,
  banner: document.querySelector("#banners").innerHTML,
  focus: document.activeElement && document.activeElement.__sel });
""")
        case = res[0]
        self.assertFalse(case["prevented"], "未保存时 Esc 放行原生关闭")
        self.assertFalse(case["declined"], "×/Esc 只等于关闭，不记拒绝")
        self.assertEqual(case["saved"], [], "关闭不得写任何偏好（拒绝版本只由暂不使用钮落盘）")
        self.assertTrue(case["locked"], "未同意关闭后门禁保持")
        self.assertFalse(case["readerOpen"], "全文已关闭")
        self.assertTrue(case["introReopened"], "关全文回到等在后面的首次说明框（FU01）")
        self.assertIn("使用条款", case["banner"], "未同意时条款横幅仍在")
        self.assertEqual(case["focus"], "#dlg-terms-intro-title", "焦点回到说明框标题")

    def test_close_restores_banner_focus_without_stacking_dialogs(self):
        """来源是横幅：说明框登记横幅来源；重入是守卫空操作；全文关掉回说明框；
        在说明框里拒绝才把焦点还给被点的横幅按钮（decisions 第 1 条的三件套链路）。"""
        res = run_js(r"""
window.pywebview = { api: {
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false;
S.prefs = {};
S.terms.prompted = true; // 同会话已提示过：防止 ingestTerms 自动首弹抢先
                         // 登记来源，让横幅打开成为真实来源
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
const dlg = document.querySelector("#dlg-terms");
const back = document.querySelector("#btn-plan");
const beforeBannerOpen = dlg.open;
openTerms("banner", back);   /* 未同意：路由进首次说明框 */
const introBox = document.querySelector("#dlg-terms-intro");
const bannerOpen = introBox.open;
const bannerSource = S.terms.source;
const bannerBackIsPlan = S.terms.focusBack === back;
const seqAfterBanner = S.terms.requestSeq;
openTerms("auto"); // 守卫：任一条款面已开时不重置任何登记（保护首来源）
const guardSource = S.terms.source;
const guardBackIsPlan = S.terms.focusBack === back;
const guardSeq = S.terms.requestSeq;
openTermsReader("intro");   /* 说明框里的「现在就看」：收小框、开全文 */
const readerOpen = dlg.open;
const introHiddenWhileReader = !introBox.open;
dlg.close();
(dlg.listeners.close || []).forEach((fn) => fn());
const afterFullClose = { readerOpen: dlg.open, introBack: introBox.open,
  focus: document.activeElement && document.activeElement.__sel };
document.querySelector("#btn-terms-intro-decline").click();  /* 在小框里拒绝 */
const afterDecline = { introOpen: introBox.open, readerOpen: dlg.open,
  focus: document.activeElement && document.activeElement.__sel };
out.push({ beforeBannerOpen, bannerOpen, bannerSource, bannerBackIsPlan,
  seqAfterBanner, guardSource, guardBackIsPlan, guardSeq,
  readerOpen, introHiddenWhileReader, afterFullClose, afterDecline,
  declined: S.terms.declined,
  helpOpen: document.querySelector("#help").open });
""")
        case = res[0]
        self.assertFalse(case["beforeBannerOpen"], "prompted 已置：ingestTerms 不得自动首弹")
        self.assertTrue(case["bannerOpen"], "横幅打开必须真实打开说明框（FU01）")
        self.assertEqual(case["bannerSource"], "banner", "打开时必须登记横幅来源")
        self.assertTrue(case["bannerBackIsPlan"], "打开时必须登记被点按钮为焦点返回点")
        self.assertEqual(case["guardSource"], "banner", "守卫不得覆盖首来源登记")
        self.assertTrue(case["guardBackIsPlan"], "守卫不得清空焦点返回点")
        self.assertEqual(case["guardSeq"], case["seqAfterBanner"],
                         "守卫空操作：不得再次作废请求代号")
        self.assertTrue(case["readerOpen"], "「现在就看」必须打开全文")
        self.assertTrue(case["introHiddenWhileReader"], "开全文前先收起说明框（两框不叠层）")
        self.assertFalse(case["afterFullClose"]["readerOpen"], "× 关全文")
        self.assertTrue(case["afterFullClose"]["introBack"], "关全文回说明框")
        self.assertEqual(case["afterFullClose"]["focus"], "#dlg-terms-intro-title")
        self.assertFalse(case["afterDecline"]["introOpen"])
        self.assertFalse(case["afterDecline"]["readerOpen"])
        self.assertEqual(case["afterDecline"]["focus"], "#btn-plan",
                         "横幅来源的拒绝把焦点还给被点的按钮")
        # TM01（decisions 014 修订）：关闭只等于关闭，拒绝只走暂不使用钮
        self.assertTrue(case["declined"])
        self.assertFalse(case["helpOpen"], "帮助没被误开（不叠弹窗）")

    def test_boot_defers_intro_until_terms_accepted(self):
        """真实 boot 首次 prefs 空且未同意：只弹条款、首轮学校加载被拦、
        欢迎与引导都延后；同意后引导只继续一次，绝不伪造 tour_version。"""
        res = run_js(r"""
let calls = [], saved = [];
window.pywebview = { api: {
  bootstrap: () => { calls.push("bootstrap");
    return Promise.resolve({ demo: false, prefs: {},
      terms: { version: "2026-10-27", accepted_version: "", accepted_at: "" } }); },
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  front_ready: () => { calls.push("front_ready"); return Promise.resolve({ ok: true }); },
  clock_snapshot: () => new Promise(() => {}),
  check: () => { calls.push("check"); return new Promise(() => {}); },
  list_activities: () => { calls.push("list"); return new Promise(() => {}); },
  accept_terms: (v) => { calls.push("accept:" + v);
    return Promise.resolve({ ok: true, terms: { version: "2026-10-27",
      accepted_version: "2026-10-27", accepted_at: "2026-10-27 12:00:00" } }); },
} };
await boot();
const schoolCalls = () => calls.filter((c) => c === "check" || c === "list");
const atBoot = { termsOpen: document.querySelector("#dlg-terms-intro").open,
  readerOpen: document.querySelector("#dlg-terms").open,
  helpOpen: document.querySelector("#help").open, tourOpen: S.tour.open,
  deferred: JSON.parse(JSON.stringify(S.terms.deferredIntro || null)),
  schoolCalls: schoolCalls() };
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
document.querySelector("#dlg-terms-document-version").textContent = "2026-10-27";
document.querySelector("#chk-terms-agree").checked = true; /* 方案 A：先勾选再点同意 */
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
const afterAccept = { tourOpen: S.tour.open, pending: !!S.tour.autoPending,
  helpOpen: document.querySelector("#help").open,
  readerOpen: document.querySelector("#dlg-terms").open,
  introOpen: document.querySelector("#dlg-terms-intro").open,
  deferred: S.terms.deferredIntro, schoolCalls: schoolCalls(),
  tourVersionWritten: saved.some((p) => "tour_version" in p),
  welcomeWritten: saved.some((p) => "welcome_seen" in p),
  locked: termsLocked() };
/* 学校确认登录有效：列表还没到，引导继续等 */
window.onBackend.check({ ok: true, result: "valid", hours_left: null, session_present: true });
const afterCheck = { tourOpen: S.tour.open, pending: !!S.tour.autoPending };
/* 列表到了：这时才开始，而且只开始一次 */
window.onBackend.activities({ ok: true, items: [] });
const afterList = { tourOpen: S.tour.open, pending: !!S.tour.autoPending, step: S.tour.step };
out.push({ atBoot, afterAccept, afterCheck, afterList });
""")
        at_boot, after = res[0]["atBoot"], res[0]["afterAccept"]
        self.assertTrue(at_boot["termsOpen"], "首次未同意只弹首次说明框（FU01）")
        self.assertFalse(at_boot["readerOpen"], "boot 不再直接弹全文阅读器")
        self.assertFalse(at_boot["helpOpen"], "欢迎延后")
        self.assertFalse(at_boot["tourOpen"], "引导延后")
        self.assertEqual(at_boot["deferred"], {"tour": True, "welcome": False})
        self.assertEqual(at_boot["schoolCalls"], [], "首轮学校加载被条款拦下")
        # 旧断言「同意后引导立刻继续」改为：同意后登记一次，等登录确认有效、列表加载后才开始（决策 009 修订）
        self.assertFalse(after["tourOpen"], "同意后还没登录确认和列表，引导先不弹")
        self.assertFalse(after["readerOpen"], "同意成功先关全文")
        self.assertFalse(after["introOpen"], "同意成功再关首次说明框（两框都关）")
        self.assertTrue(after["pending"], "同意后引导登记为等着开始")
        self.assertFalse(res[0]["afterCheck"]["tourOpen"], "只有登录确认、列表没到：还不弹")
        self.assertTrue(res[0]["afterList"]["tourOpen"], "登录有效且列表到了：引导开始")
        self.assertFalse(res[0]["afterList"]["pending"], "开始后登记清掉（只继续一次）")
        self.assertEqual(res[0]["afterList"]["step"], 0, "从第 1 步开始")
        self.assertFalse(after["helpOpen"], "本例引导适用，不再叠欢迎")
        self.assertIsNone(after["deferred"], "延后项消费后清空（只继续一次）")
        self.assertEqual(after["schoolCalls"], ["check", "list"], "同意后补一次加载")
        self.assertFalse(after["tourVersionWritten"], "绝不伪造 tour_version")
        self.assertTrue(after["welcomeWritten"], "首次欢迎标记仍按原语义落盘")
        self.assertFalse(after["locked"])

    def test_decline_after_deferred_boot_does_not_fake_tour_completion(self):
        """延后状态下点「暂不使用」（TM01：拒绝只走这个钮；FU01 起它长在
        首次说明框上）：本会话不自动开引导、不写 tour_version，引导完成状态
        保持未写；拒绝收口（焦点/引导让位）由 declineTerms 自己完成。"""
        res = run_js(r"""
let saved = [];
window.pywebview = { api: {
  bootstrap: () => Promise.resolve({ demo: false, prefs: {},
    terms: { version: "2026-10-27", accepted_version: "", accepted_at: "" } }),
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  front_ready: () => Promise.resolve({ ok: true }),
  clock_snapshot: () => new Promise(() => {}),
} };
await boot();
document.querySelector("#btn-terms-intro-decline").click();
await Promise.resolve(); await Promise.resolve();
out.push({ declined: S.terms.declined, tourOpen: S.tour.open,
  introOpen: document.querySelector("#dlg-terms-intro").open,
  helpOpen: document.querySelector("#help").open,
  tourVersionWritten: saved.some((p) => "tour_version" in p),
  tourStillEligible: tourShouldAutoStart(),
  declinedSaved: saved.some((p) => p.terms_declined_version === "2026-10-27"),
  focus: document.activeElement && document.activeElement.__sel });
""")
        case = res[0]
        self.assertTrue(case["declined"])
        self.assertFalse(case["introOpen"], "拒绝后说明框关闭")
        self.assertFalse(case["tourOpen"], "拒绝后本会话不自动开引导")
        self.assertFalse(case["helpOpen"])
        self.assertFalse(case["tourVersionWritten"], "拒绝不伪造引导完成")
        self.assertTrue(case["tourStillEligible"], "引导完成状态保持未写")
        self.assertTrue(case["declinedSaved"])
        self.assertEqual(case["focus"], "#btn-help")

    def test_terms_dialog_keyboard_does_not_penetrate_background(self):
        """打开的条款弹窗独占键盘：Enter/斜杠/Ctrl+F/F5 不穿透（不 preventDefault、
        不抢搜索、不刷新），引导可见时 Esc 也不跳过引导。"""
        res = run_js(r"""
S.demo = false;
S.prefs = {};
ingestTerms({ version: "2026-10-27", accepted_version: "", accepted_at: "" });
openTermsReader("intro"); /* 首启说明框里的「现在就看」入口（decisions 第 1 条） */
const eEnter = __dispatchKey({ key: "Enter" });
const eSlash = __dispatchKey({ key: "/" });
const eCtrlF = __dispatchKey({ key: "f", ctrlKey: true });
const eF5 = __dispatchKey({ key: "F5" });
const focusAfterSearch = document.activeElement && document.activeElement.__sel;
/* 引导强行可见：Esc 不许跳过引导、不许写 tour_version */
S.tour.open = true;
S.tour.paused = false;
S.terms.tourYield = false;
const eEsc = __dispatchKey({ key: "Escape" });
out.push({ enterPrevented: eEnter.defaultPrevented,
  slashPrevented: eSlash.defaultPrevented,
  ctrlFPrevented: eCtrlF.defaultPrevented,
  f5Prevented: eF5.defaultPrevented, escPrevented: eEsc.defaultPrevented,
  focusAfterSearch, tourOpen: S.tour.open,
  tourVersionWritten: "tour_version" in S.prefs,
  termsOpen: document.querySelector("#dlg-terms").open });
""")
        case = res[0]
        self.assertFalse(case["enterPrevented"], "Enter 保留原生语义，不触发开始计划")
        self.assertFalse(case["slashPrevented"], "斜杠不抢搜索框")
        self.assertFalse(case["ctrlFPrevented"], "Ctrl+F 不抢搜索框")
        self.assertFalse(case["f5Prevented"], "保存外的重载保留原生（不强拦）")
        self.assertFalse(case["escPrevented"], "条款打开时 Esc 不穿透到引导")
        self.assertEqual(case["focusAfterSearch"], "#dlg-terms-title",
                         "焦点停在条款标题，没被搜索抢走")
        self.assertTrue(case["tourOpen"], "引导没被条款内的 Esc 跳过")
        self.assertFalse(case["tourVersionWritten"])
        self.assertTrue(case["termsOpen"])

    def test_terms_dialog_static_contract_native_close_and_anchors(self):
        """静态守护：X 走原生 method=dialog 关闭（由 close 监听统一收口）、
        阅读区/反馈/底栏结构与版本节点齐备。"""
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        start = html.index('id="dlg-terms"')
        block = html[start:html.index("</dialog>", start)]
        self.assertIn('method="dialog"', block, "右上角 X 必须走原生关闭")
        self.assertEqual(block.count('id="dlg-terms-document-version"'), 1)
        self.assertEqual(block.count('id="dlg-terms-status"'), 1)
        # 要点视图与工具行已删（decisions 第 1 条）：阅读器只呈现全文
        for anchor in ("terms-head", "terms-body",
                       "terms-feedback", "terms-foot", "terms-section"):
            self.assertIn(anchor, block, "设计稿结构区缺失：" + anchor)
        self.assertIn('id="btn-terms-recheck"', block)
        self.assertIn('id="btn-terms-close"', block)
        self.assertNotIn('id="btn-terms-full"', block)
        self.assertNotIn("terms-toolbar", block)
        self.assertNotIn("terms-summary", block)
        self.assertNotIn("terms-update-list", block, "内嵌更新区块已删，清单挪进条款更新框")

    def test_first_use_and_update_modals_static_contract(self):
        """FU01/TM08（c3-dialogs-gap，原型 Main:798-807/878-881/1828/2484）：
        两个小框的骨架、无 × 规则、脚部钮排布与注句、副题版本节点。"""
        html = read("ui/index.html")
        # FU01：标题与副题逐字照原型（Main:800）
        self.assertIn("开始前先了解这些", html)
        self.assertIn("同意后才能登录、查看活动和开始报名计划", html)
        # TM08：副题句式照原型 Main:879（X/Y 由 views 填真实版本）
        self.assertIn("，你之前同意的是", html)
        self.assertIn("。同意新版后才能继续登录和报名。", html)
        # TM08：注句逐字照原型 Main:880
        self.assertIn("不同意也可以继续用帮助和设置，但登录、自动登录、活动列表和报名计划会停用。"
                      "已保存的账号密码和登录信息不会删除。", html)
        intro = self._dialog_block(html, "dlg-terms-intro")
        update = self._dialog_block(html, "dlg-terms-update")
        # × 规则（UI_SPEC §5.13：做决定的弹窗不放 ×）——两个小框都没有 dlg-x
        for name, block in (("首次说明框", intro), ("条款更新框", update)):
            self.assertNotIn("dlg-x", block, name + "不放右上角 ×")
            self.assertNotIn('method="dialog"', block, name + "没有 × 关闭表单")
        # FU01 脚部（Main:807）：勾选居左＋暂不使用｜同意并继续（勾选前禁用）
        self.assertIn('id="chk-terms-intro-agree"', intro)
        self.assertIn(">暂不使用</button>", intro)
        self.assertIn("disabled", intro)
        self.assertIn(">同意并继续</button>", intro)
        # TM08 脚部（Main:881）：看完整条款｜暂不同意｜同意新版条款
        self.assertIn(">看完整条款</button>", update)
        self.assertIn(">暂不同意</button>", update)
        self.assertIn(">同意新版条款</button>", update)
        # TM08（Main:880）：变更清单容器与「这次主要改了：」引导句在框内
        self.assertIn("这次主要改了：", update)
        self.assertIn('id="terms-update-list"', update)
        # 验证 grep 口径：两个标题串都只落在 index.html 的对话块里
        self.assertEqual(html.count("开始前先了解这些"), 1)
        self.assertGreaterEqual(html.count("同意新版条款"), 1)

    @staticmethod
    def _dialog_block(html: str, dom_id: str) -> str:
        """截取指定 dialog 元素本体（含结尾标签），供小框的逐块断言使用。"""
        start = html.index('id="' + dom_id + '"')
        start = html.rindex("<dialog", 0, start)
        end = html.index("</dialog>", start) + len("</dialog>")
        return html[start:end]

    def test_terms_status_feedback_resets_reading_scroll_zero_side_effects(self):
        """termsStatus 反馈与阅读区滚动（只定义、待授权运行）：
        非空消息把唯一阅读区 scrollTop 归零且文本/tone/hidden 正确；
        清空分支提前 return，只隐藏状态、不动滚动；
        焦点、全文展开态、条款请求代号全部不变，且反馈路径零桥调用。"""
        res = run_js(r"""
          // 本用例只验证 termsStatus 反馈，不走真实桥接：harness 不预置 pywebview，
          // 先给五个键本地 no-op Promise 桩让包装器可挂接；任何意外调用都会被记录。
          window.pywebview = { api: {
            accept_terms: () => Promise.resolve({ ok: true }),
            save_prefs: () => Promise.resolve({ ok: true }),
            bootstrap: () => Promise.resolve({}),
            check: () => Promise.resolve({ ok: true }),
            list_activities: () => Promise.resolve({ ok: true, items: [] }),
          } };
          const body = $(".terms-body");
          const status = $("#dlg-terms-status");
          const full = $("#dlg-terms-full-text");
          const bridge = window.pywebview.api;
          const bridgeCalls = [];
          ["accept_terms", "save_prefs", "bootstrap", "check", "list_activities"].forEach((key) => {
            const fn = bridge[key];
            bridge[key] = (...args) => { bridgeCalls.push(key); return fn.apply(bridge, args); };
          });
          body.scrollTop = 200;
          const focusBefore = document.activeElement;
          const seqBefore = S.terms.requestSeq;
          const fullHiddenBefore = full.hidden;
          termsStatus("保存结果未确认：请点「重新确认状态」核对本机记录。", "warn");
          out.push({
            scrollTop: body.scrollTop,
            text: status.textContent,
            tone: status.dataset.tone,
            hidden: status.hidden,
            focusUnchanged: document.activeElement === focusBefore,
            seqUnchanged: S.terms.requestSeq === seqBefore,
            fullHiddenUnchanged: full.hidden === fullHiddenBefore
          });
          body.scrollTop = 100;
          termsStatus("", "warn");
          out.push({
            scrollTop: body.scrollTop,
            hidden: status.hidden,
            text: status.textContent
          });
          out.push({ bridgeCalls: bridgeCalls });
        """)
        shown, cleared, calls = res[0], res[1], res[2]
        self.assertEqual(shown["scrollTop"], 0, "非空反馈必须把阅读区滚回顶部")
        self.assertIn("保存结果未确认", shown["text"], "状态文本必须如实展示反馈消息")
        self.assertEqual(shown["tone"], "warn", "tone 必须按传入值展示")
        self.assertFalse(shown["hidden"], "非空反馈必须可见")
        self.assertTrue(shown["focusUnchanged"], "反馈不许碰焦点")
        self.assertTrue(shown["seqUnchanged"], "反馈不许改条款请求代号")
        self.assertTrue(shown["fullHiddenUnchanged"], "反馈不许动全文展开态")
        self.assertEqual(cleared["scrollTop"], 100,
                         "清空分支必须提前 return，不能归零滚动")
        self.assertTrue(cleared["hidden"], "清空后状态必须隐藏")
        self.assertEqual(cleared["text"], "", "清空后状态文本必须置空")
        self.assertEqual(calls["bridgeCalls"], [], "反馈路径必须零桥调用")


class FirstUseAndUpdateModalsTests(unittest.TestCase):
    """FU01/FU02/TM08/TM09（plan 20261108-c3-dialogs decisions 第 1/2 条）：
    首次说明框与条款更新框的打开时机、小框⇄全文往返、勾选门、拒绝路径与数据。"""

    # views/terms.js 的 TERMS_CHANGES 条数（r6 变更记录归纳 3 条，TM09 用其真实内容；条款升 r6 后由 4 条改为 3 条）
    TERMS_CHANGES_COUNT = 3

    def test_routing_three_terms_states(self):
        """三种条款状态各开哪个框：从没同意→首次说明框；同意过旧版→条款更新框；
        状态未知→直接开全文阅读器（同意态）。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false;
S.prefs = {};
S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const neverBox = document.querySelector("#dlg-terms-intro").open;
const neverReader = document.querySelector("#dlg-terms").open;
document.querySelector("#dlg-terms-intro").close();
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
const updateBox = document.querySelector("#dlg-terms-update").open;
const updateReader = document.querySelector("#dlg-terms").open;
document.querySelector("#dlg-terms-update").close();
markTermsUnknown();
openTerms("banner");
const unknownReader = document.querySelector("#dlg-terms").open;
const unknownIntro = document.querySelector("#dlg-terms-intro").open;
out.push({ neverBox, neverReader, updateBox, updateReader, unknownReader, unknownIntro });
""")
        r = res[0]
        self.assertTrue(r["neverBox"], "从没同意过 → 首次说明框（FU01）")
        self.assertFalse(r["neverReader"], "从没同意过不开全文阅读器")
        self.assertTrue(r["updateBox"], "同意过旧版 → 条款更新框（TM08）")
        self.assertFalse(r["updateReader"], "同意过旧版不开全文阅读器")
        self.assertTrue(r["unknownReader"], "状态未知 → 直接开全文阅读器（同意态）")
        self.assertFalse(r["unknownIntro"], "状态未知不弹小框")

    def test_update_box_paints_versions_changes_and_focus(self):
        """TM08/TM09：副题版本读真实值（示意值不进产品）、变更清单 4 条带
        「新增」徽章（r5 真实内容，原型 Main:880 版式）、打开时焦点落同意钮
        （Main:1828）。"""
        res = run_js(r"""
window.pywebview = { api: {} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "2026-11-09-r6", accepted_version: "2026-10-27-r3", accepted_at: "" });
openTerms("banner");
const box = document.querySelector("#dlg-terms-update");
out.push({
  open: box.open,
  version: document.querySelector("#terms-update-version").textContent,
  from: document.querySelector("#terms-update-from").textContent,
  items: document.querySelector("#terms-update-list").innerHTML.split("<li>").length - 1,
  badges: document.querySelector("#terms-update-list").innerHTML.split("tu-new").length - 1,
  focus: document.activeElement && document.activeElement.__sel,
  lead: document.querySelector("#dlg-terms-update-lead").textContent,
});
""")
        r = res[0]
        self.assertTrue(r["open"])
        self.assertEqual(r["version"], "2026-11-09-r6", "副题新版号读 S.terms.version")
        self.assertEqual(r["from"], "2026-10-27-r3", "副题旧版号读已同意版本")
        self.assertEqual(r["items"], self.TERMS_CHANGES_COUNT, "变更清单条数＝TERMS_CHANGES")
        self.assertEqual(r["badges"], self.TERMS_CHANGES_COUNT, "每条一个「新增」徽章")
        self.assertEqual(r["focus"], "#btn-tu-accept", "打开时焦点落「同意新版条款」（Main:1828）")

    def test_full_text_roundtrip_from_boxes_via_x_and_esc(self):
        """小框→全文→关全文回小框：× 与 Esc 两种关法都回到原来的小框，
        不记拒绝、不落盘（decisions 第 1 条）。"""
        res = run_js(r"""
window.pywebview = { api: { save_prefs: () => Promise.resolve({ ok: true }) } };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
const dlg = document.querySelector("#dlg-terms");
const tu = document.querySelector("#dlg-terms-update");
/* × 关法：close + 手动收口 close 监听（桩不模拟原生 close 事件） */
openTermsReader("update");
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
const viaX = { readerOpen: dlg.open, tuBack: tu.open, declined: S.terms.declined };
/* Esc 关法：cancel 放行 + close 收口 */
openTermsReader("update");
const cancelEv = { defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
(dlg.listeners.cancel || []).forEach((fn) => fn(cancelEv));
dlg.close(); (dlg.listeners.close || []).forEach((fn) => fn());
const viaEsc = { readerOpen: dlg.open, tuBack: tu.open, declined: S.terms.declined,
  escPrevented: cancelEv.defaultPrevented };
out.push({ viaX, viaEsc });
""")
        r = res[0]
        self.assertFalse(r["viaX"]["readerOpen"])
        self.assertTrue(r["viaX"]["tuBack"], "× 关全文回条款更新框")
        self.assertFalse(r["viaX"]["declined"], "关全文不等于拒绝")
        self.assertFalse(r["viaEsc"]["escPrevented"], "未保存时 Esc 放行原生关闭")
        self.assertTrue(r["viaEsc"]["tuBack"], "Esc 关全文回条款更新框")
        self.assertFalse(r["viaEsc"]["declined"])

    def test_agree_in_full_text_closes_update_box_too(self):
        """从条款更新框进全文、在全文里同意：两框都关（先关全文再关更新框）。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1;
    return Promise.resolve({ ok: true, terms: { version: "v2",
      accepted_version: "v2", accepted_at: "2026-11-08 12:00:00" } }); },
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");   /* 同意过旧版：先进条款更新框（TM08） */
openTermsReader("update"); /* 「看完整条款」入口 */
document.querySelector("#dlg-terms-document-version").textContent = "v2";
document.querySelector("#chk-terms-agree").checked = true;
document.querySelector("#btn-terms-accept").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ accepted, readerOpen: document.querySelector("#dlg-terms").open,
  tuOpen: document.querySelector("#dlg-terms-update").open,
  locked: termsLocked() });
""")
        r = res[0]
        self.assertEqual(r["accepted"], 1)
        self.assertFalse(r["readerOpen"], "全文关闭")
        self.assertFalse(r["tuOpen"], "条款更新框一并关闭")
        self.assertFalse(r["locked"])

    def test_intro_accept_gated_by_checkbox(self):
        """FU01（Main:2484）：勾选前「同意并继续」禁用，点不动、零请求；
        勾选后解锁，同意成功关闭说明框。"""
        res = run_js(r"""
let accepted = 0;
window.pywebview = { api: {
  accept_terms: () => { accepted += 1;
    return Promise.resolve({ ok: true, terms: { version: "v2",
      accepted_version: "v2", accepted_at: "2026-11-08 12:00:00" } }); },
  save_prefs: () => Promise.resolve({ ok: true }),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
/* accept_terms 的回执契约按内嵌全文版本校验（同阅读器路径） */
document.querySelector("#dlg-terms-document-version").textContent = "v2";
const intro = document.querySelector("#dlg-terms-intro");
const accept = document.querySelector("#btn-terms-intro-accept");
const agree = document.querySelector("#chk-terms-intro-agree");
const disabledBefore = accept.disabled;
accept.click();   /* 勾选前点击：桩不模拟 disabled，控制器里的勾选门必须拦 */
const acceptedBefore = accepted;
agree.checked = true;
(agree.listeners.change || []).forEach((fn) => fn({ target: agree }));
const enabledAfter = !accept.disabled;
accept.click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ disabledBefore, acceptedBefore, enabledAfter, accepted,
  introOpen: intro.open, readerOpen: document.querySelector("#dlg-terms").open,
  focus: document.activeElement && document.activeElement.__sel });
""")
        r = res[0]
        self.assertTrue(r["disabledBefore"], "勾选前同意钮禁用（Main:2484）")
        self.assertEqual(r["acceptedBefore"], 0, "勾选门前点击零请求")
        self.assertTrue(r["enabledAfter"], "勾选后同意钮解锁")
        self.assertEqual(r["accepted"], 1)
        self.assertFalse(r["introOpen"], "同意成功关闭说明框")
        self.assertFalse(r["readerOpen"])
        self.assertEqual(r["focus"], "#btn-help")

    def test_esc_on_small_boxes_is_decline_and_saving_is_blocked(self):
        """FU01/TM08：小框 Esc＝暂不使用／暂不同意（拒绝路径落盘）；保存中
        Esc 被 cancel 拦下不关闭；未确认＝离开待确认界面不记拒绝。"""
        res = run_js(r"""
let saved = [];
window.pywebview = { api: {
  save_prefs: (patch) => { saved.push(JSON.parse(JSON.stringify(patch))); return Promise.resolve({ ok: true }); },
  accept_terms: () => new Promise(() => {}),
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
const intro = document.querySelector("#dlg-terms-intro");
const tu = document.querySelector("#dlg-terms-update");
const mkCancel = () => ({ defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });
/* 更新框：保存中 Esc 拦下（在途） */
ingestTerms({ version: "v2", accepted_version: "v1", accepted_at: "" });
openTerms("banner");
S.terms.saving = true;
let ev = mkCancel();
(tu.listeners.cancel || []).forEach((fn) => fn(ev));
const savingBlocked = ev.defaultPrevented && tu.open;
S.terms.saving = false;
S.terms.unconfirmed = true;
ev = mkCancel();
(tu.listeners.cancel || []).forEach((fn) => fn(ev));
const unconfirmedLeave = !tu.open;
S.terms.unconfirmed = false;
/* 首启说明框：Esc＝暂不使用，落盘拒绝版本 */
document.querySelector("#dlg-terms-update").close();
S.terms.declined = false;
S.terms.acceptedVersion = "";
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
ev = mkCancel();
(intro.listeners.cancel || []).forEach((fn) => fn(ev));
out.push({ savingBlocked, unconfirmedLeave, declined: S.terms.declined,
  introOpen: intro.open, tuOpen: tu.open,
  declinedSaved: saved.some((p) => p.terms_declined_version === "v2"),
  readerOpen: document.querySelector("#dlg-terms").open });
""")
        r = res[0]
        self.assertTrue(r["savingBlocked"], "保存中 Esc 必须 preventDefault 且不关闭")
        self.assertTrue(r["unconfirmedLeave"], "未确认时 Esc＝离开待确认界面（不记拒绝）")
        self.assertTrue(r["declined"], "Esc 在小框上等于拒绝（拒绝路径）")
        self.assertFalse(r["introOpen"])
        self.assertTrue(r["declinedSaved"], "拒绝版本落盘（现有拒绝路径不变）")
        self.assertFalse(r["readerOpen"])

    def test_first_use_points_data_and_rendering(self):
        """FU02：六条要点在 store（数据）与渲染（6 条 li、第六条带「现在就看」
        链接钮），关键句与 r5 正文一致（decisions 第 2 条）。"""
        store = read("ui/state/store.js")
        # 抽两条钉关键词：第 1 条的目标学校限定、第 5 条的对外通信三类口径
        self.assertIn("只适用于一所目标学校", store)
        self.assertIn("访问 GitHub", store, "对外通信按 r6 隐私第 3 节四类口径（GitHub 下载）")
        self.assertIn("运行时密钥", store, "密钥叫法按 r5 用户协议第 1/3 节")
        self.assertIn("不提供多账号、批量占位或代他人报名", store,
                      "义务表述按 r5 用户协议第 5 节")
        res = run_js(r"""
window.pywebview = { api: {} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const list = document.querySelector("#dlg-terms-intro-points");
out.push({
  items: list.innerHTML.split("<li>").length - 1,
  html: list.innerHTML,
  open: document.querySelector("#dlg-terms-intro").open,
  agree: document.querySelector("#chk-terms-intro-agree").checked,
});
""")
        r = res[0]
        self.assertTrue(r["open"])
        self.assertEqual(r["items"], 6, "六条要点")
        self.assertFalse(r["agree"], "每次打开回到未勾选")
        # 桩不解析 HTML：标题等静态文案由 test_first_use_and_update_modals_static_contract 覆盖
        self.assertEqual(r["html"].count('id="btn-terms-intro-fulltext"'), 1,
                         "第六条「完整条款」只有一个入口链接钮")
        self.assertIn("现在就看", r["html"])

    def test_small_boxes_block_background_shortcuts(self):
        """UI_SPEC §5.13 第 2 条：小框开着时 F5/Ctrl+F//、Enter 不落到背景
        （不刷新、不抢搜索、不开始计划）。"""
        res = run_js(r"""
let calls = [];
window.pywebview = { api: {
  start_plan: () => { calls.push("start"); return Promise.resolve({ ok: true }); },
} };
S.demo = false; S.prefs = {}; S.terms.prompted = true;
ingestTerms({ version: "v2", accepted_version: "", accepted_at: "" });
openTerms("banner");
const eF5 = __dispatchKey({ key: "F5" });
const eEnter = __dispatchKey({ key: "Enter" });
const eCtrlF = __dispatchKey({ key: "f", ctrlKey: true });
const eSlash = __dispatchKey({ key: "/" });
out.push({ f5: eF5.defaultPrevented, enter: eEnter.defaultPrevented,
  ctrlF: eCtrlF.defaultPrevented, slash: eSlash.defaultPrevented,
  calls, introOpen: document.querySelector("#dlg-terms-intro").open });
""")
        r = res[0]
        self.assertTrue(r["introOpen"])
        self.assertEqual(r["calls"], [], "背景 Enter 不开始计划")
        self.assertFalse(r["f5"], "F5 保留原生语义（背景刷新按钮不响应）")
        self.assertFalse(r["enter"], "Enter 保留原生语义")
        self.assertFalse(r["ctrlF"], "Ctrl+F 不抢搜索框")
        self.assertFalse(r["slash"], "斜杠不抢搜索框")


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



class ChannelInstallContractTests(unittest.TestCase):
    """手机控制安装区：能力状态在前、一键装组件、长期/临时说得清。"""

    def setUp(self):
        self.html = read("ui/index.html")
        self.css = read("ui/styles.css")
        self.view = read("ui/views/phone.js")

    def test_component_download_elements_exist(self):
        for marker in ('id="phone-component-state"',
                       'id="phone-component-progress"',
                       'id="phone-component-error"',
                       'id="btn-phone-component-install"',
                       'id="btn-phone-component-cancel"'):
            self.assertIn(marker, self.html, marker)

    def test_component_state_is_announced(self):
        self.assertIn('id="phone-component-state" aria-live="polite"', self.html)
        self.assertIn('id="phone-status" role="status"', self.html,
                      "结果提示同样要能被读屏念出来")

    def test_progress_and_error_have_styles(self):
        self.assertIn(".phone-component-progress", self.css)
        self.assertIn(".phone-component-error", self.css)
        self.assertIn("var(--bad-tint)", self.css)
        block = self.css.split("/* ---- 帮助里的跨设备访问")[-1]
        self.assertNotIn("gradient", block.split("/* ---- 独立北京时间")[0],
                         "新增的组件区不引入渐变")
        # fe-phone（PH14）：进度条墨色、不用蓝色，验证码识别共用 .ph-bar
        self.assertIn(".ph-bar i { display: block; width: 0; height: 100%; background: var(--ink);", self.css)
        self.assertNotIn(".phone-component-progress { width: 100%; height: 8px; margin: 4px 0; "
                         "accent-color: var(--blue); }", self.css)

    def test_channels_say_long_lived_versus_temporary(self):
        # fe-phone 同步：通道卡名照原型改成逗号「Tailscale，长期地址」「Cloudflare，临时地址」（PH17），
        # 卡名写在 index.html 的单选卡里
        self.assertIn("Tailscale，长期地址", self.html)
        self.assertIn("Cloudflare，临时地址", self.html)
        self.assertIn("重新扫码", self.html)
        self.assertIn("要重新扫码和配对", self.view)

    def test_no_path_box_or_raw_binary_picker_for_normal_users(self):
        for forbidden in ('id="phone-cloudflared-path"',
                          'id="btn-phone-cloudflared-inspect"',
                          "cloudflared.exe 路径"):
            self.assertNotIn(forbidden, self.html, forbidden)
class LicenseDocContractTests(unittest.TestCase):
    """蓝链 + MIT 第三页签（20261031 验收第 3 条）：
    正文/勾选行/第 3 条的内联文档链接、随包 LICENSE 经桥读取、懒加载与缓存、
    失败就地重试。QA 行为断言在 tools/qa_runtime_reliability.py 的
    terms-links-license 场景；这里锁静态契约与后端读文件语义。"""

    # ---- 后端：候选链纯函数 + Api.get_license_text（ast 隔离求值，不 import app.py）----

    @staticmethod
    def _load_license_funcs():
        import ast

        tree = ast.parse(read("app.py"))
        funcs = {}
        for item in ast.walk(tree):
            if (isinstance(item, ast.FunctionDef)
                    and item.name in ("license_candidates", "get_license_text")):
                funcs[item.name] = item
        missing = {"license_candidates", "get_license_text"} - set(funcs)
        assert not missing, "app.py 缺少函数：%s" % sorted(missing)
        module = ast.Module(body=[funcs["license_candidates"], funcs["get_license_text"]],
                            type_ignores=[])
        ast.fix_missing_locations(module)
        ns = {"Path": Path}
        exec(compile(module, "<Api.get_license_text>", "exec"), ns)  # noqa: S102
        return ns

    def test_license_candidates_order(self):
        """候选链：冻结资源根 → 脚本旁 → 仓库根（here.parent），别无他处。"""
        ns = self._load_license_funcs()
        cands = ns["license_candidates"](Path("/pkg/_internal"), Path("/pkg/local"))
        self.assertEqual([c.name for c in cands], ["LICENSE"] * 3)
        self.assertEqual([str(c.parent) for c in cands],
                         [str(Path("/pkg/_internal")), str(Path("/pkg/local")),
                          str(Path("/pkg"))])
        for cand in cands:
            lowered = str(cand).lower()
            for banned in ("session", "storage_state", "credential", "token"):
                self.assertNotIn(banned, lowered,
                                 "LICENSE 候选链不得指向凭据类文件：%s" % cand)

    def test_api_get_license_text_reads_package_order_and_fails_plain(self):
        """有 LICENSE：按候选顺序取第一个存在的；没有：ok=False + 人话，不抛异常。"""
        import tempfile

        ns = self._load_license_funcs()
        get = ns["get_license_text"]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            here = root / "local"
            here.mkdir()
            ns["RESOURCE_ROOT"], ns["HERE"] = root / "_internal", here
            missing = get(None)
            self.assertFalse(missing.get("ok"), missing)
            self.assertTrue(isinstance(missing.get("text"), str) and missing["text"],
                            "失败必须给人话：%r" % missing)
            self.assertNotIn("Traceback", missing["text"])
            # 仓库根（here.parent）有：读得到
            (root / "LICENSE").write_text("MIT root", encoding="utf-8")
            got = get(None)
            self.assertTrue(got["ok"], got)
            self.assertEqual(got["text"], "MIT root")
            # 脚本旁优先于仓库根
            (here / "LICENSE").write_text("MIT here", encoding="utf-8")
            self.assertEqual(get(None)["text"], "MIT here")
            # 冻结资源根最优先
            (root / "_internal").mkdir()
            (root / "_internal" / "LICENSE").write_text("MIT frozen", encoding="utf-8")
            self.assertEqual(get(None)["text"], "MIT frozen")

    # ---- 前端 DOM/CSS/脚本 ----

    def test_index_has_inline_doc_links_and_license_tab(self):
        html = read("ui/index.html")
        sub_start = html.index('id="dlg-terms-sub"')
        sub = html[sub_start:html.index("</p>", sub_start)]
        for doc in ("agreement", "privacy"):
            self.assertIn('<button type="button" class="doc-link" data-doc="%s">' % doc,
                          sub, "副行缺 %s 内联链接" % doc)
        label_start = html.index('class="terms-agree"')
        label = html[label_start:html.index("</label>", label_start)]
        for doc in ("agreement", "privacy"):
            self.assertIn('class="doc-link" data-doc="%s"' % doc,
                          label, "同意勾选行缺 %s 内联链接" % doc)
        self.assertIn('id="tab-terms-license"', html, "缺 MIT 许可证页签")
        self.assertIn('id="doc-terms-license"', html, "缺 MIT 许可证内容容器")
        # 第 3 条「见随包 LICENSE」也要有链接（在协议 pane 内）
        agree_start = html.index('id="doc-terms-agreement"')
        agree = html[agree_start:html.index('id="doc-terms-privacy"')]
        self.assertIn('data-doc="license"', agree, "第 3 条缺「随包 LICENSE」链接")
        # license 容器不得用 <h3>N. 编号：privacy 切片延伸到文件尾，会污染逐节契约
        lic_start = html.index('id="doc-terms-license"')
        license_pane = html[lic_start:html.index("</section>", lic_start)]
        self.assertNotRegex(license_pane, r"<h3>\d+\. ")

    def test_styles_paint_links_blue_and_pre_monospace(self):
        css = read("ui/styles.css")
        doc_link_rules = [line for line in css.splitlines() if ".doc-link" in line]
        self.assertTrue(doc_link_rules, "缺内联链接样式")
        self.assertTrue(any("var(--blue)" in line and "underline" in line
                            for line in doc_link_rules),
                        "doc-link 必须蓝色加下划线：%r" % doc_link_rules)
        pre_rules = [line for line in css.splitlines() if ".license-pre" in line]
        self.assertTrue(any("monospace" in line for line in pre_rules),
                        "license-pre 必须等宽：%r" % pre_rules)
        self.assertTrue(any("pre" in line and "overflow" in line for line in pre_rules),
                        "license-pre 必须可滚动：%r" % pre_rules)

    def test_scripts_wire_lazy_license_load_and_cache(self):
        scripts = read("ui/app.js")
        self.assertIn('"get_license_text"', scripts, "前端必须经桥调 get_license_text")
        self.assertIn("S.licenseText", scripts, "必须用 S.licenseText 缓存")
        self.assertIn("#tab-terms-license", scripts, "MIT 页签必须接切换事件")
        self.assertIn("ensureLicenseText", scripts, "缺懒加载控制器")
        self.assertIn("paintLicenseDoc", scripts, "缺许可文档渲染器")
        self.assertIn("doc-link", scripts, "内联链接必须有委托点击处理")

    def test_bridge_fixture_mirrors_license_capability(self):
        fixture = (LOCAL / "tests" / "fixtures" / "runtime_bridge.js").read_text(
            encoding="utf-8")
        self.assertIn("get_license_text:", fixture, "桥替身缺 get_license_text 方法")
        self.assertIn("licenseFail", fixture, "桥替身缺失败注入钩子（QA ④ 断言依赖）")
        self.assertIn("MIT License", fixture, "桥替身必须内嵌真实 MIT 全文")


PP_LOGIN_OK_JS = r"""
S.listState = "ready";
S.login.present = true; S.login.result = "valid"; S.login.ok = true; S.login.checking = false;
paintLogin();
"""


def _pp_stats(html):
    """结果页大数字 → {标签: 数}（只含显示出来的格子）。"""
    return {label: int(n) for n, label in
            re.findall(r"<strong>(\d+)</strong><span>([^<]+)</span>", html)}


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


if __name__ == "__main__":
    unittest.main()


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


class AdvancedComponentDialogContractTests(unittest.TestCase):
    """「安装/更换」打开的是逐项自检的对话框，不是点一下就装、也不是代下载。"""

    def setUp(self):
        self.html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        self.css = (LOCAL / "ui" / "styles.css").read_text(encoding="utf-8")
        self.phone = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")

    def test_the_dialog_lists_one_row_per_component(self):
        # fe-ocr-login 同步（IM01）：弹窗改成「每次导入一个组件」——两行各自带路径、选择文件、结论、需要说明，
        # 状态标签（comp-*-status）和单独的「自检」按钮按原型去掉；Tailscale 行见下一个用例
        for needle in ('id="dlg-components"', 'id="comp-phone"', 'id="comp-ocr"',
                       'id="dlg-components-title"', 'id="btn-comp-close"'):
            self.assertIn(needle, self.html, "组件对话框缺少 %s" % needle)
        for prefix in ("comp-phone", "comp-ocr"):
            for suffix in ("need", "path", "note"):
                self.assertIn('id="%s-%s"' % (prefix, suffix), self.html)
            for action in ("pick", "install"):
                self.assertIn('id="btn-%s-%s"' % (prefix, action), self.html)
            self.assertNotIn('id="btn-%s-inspect"' % prefix, self.html, "自检随选文件自动做（IM01）")
            self.assertNotIn('id="%s-status"' % prefix, self.html)
        self.assertIn("选一个已经下好的组件包 ZIP。选完会立刻自检，选错了会当场说清是什么。", self.html)
        self.assertIn("需要 relogin_ocr-版本号.zip，在发布页和程序一起发布，版本要和程序一致。", self.html)
        self.assertIn("需要 phone_control-版本号.zip，里面已经带好 cloudflared，不用另外安装。", self.html)

    def test_nothing_is_installed_before_a_file_passes_the_check(self):
        """安装按钮默认不可点：必须先选文件、且自检通过。"""
        start = self.html.index('id="btn-comp-phone-install"')
        stop = self.html.index(">", start)
        self.assertIn("disabled", self.html[start:stop])
        start = self.html.index('id="btn-comp-ocr-install"')
        stop = self.html.index(">", start)
        self.assertIn("disabled", self.html[start:stop])
        # fe-ocr-login 同步：安装按钮的禁用判断随 paintComponents 改写成按当前导入的组件逐个算
        self.assertIn("installEl.disabled = !verified", self.phone)
        self.assertIn("inspect_advanced_component", self.phone)
        self.assertIn("install_advanced_feature", self.phone)

    def test_the_install_buttons_only_open_the_dialog(self):
        """帮助页那两个「安装」按钮改成打开对话框，不再直接调安装接口。"""
        self.assertNotIn('PhonePanel.install("phone_control"', self.phone)
        self.assertNotIn('PhonePanel.install("relogin_ocr"', self.phone)
        # fe-ocr-login 同步：弹窗一次只导入一个组件，打开时必须说清是哪个，所以入口都改成带组件键的写法
        # （原先不带参数的 PhonePanel.openComponents() 在 phone.js 里 3 处，计数没法再用）。
        # phone.js 剩 2 处，都是手机控制：下载失败后的「导入已下载的组件包」链接（PH10），
        # 以及原型没画、保留现状的「重新导入组件包 / 安装/更换组件包」（PH14b）；
        # 验证码识别的导入入口搬到 settings.js（OC12 的句内链接，和 OC14 保留的「重新导入组件包」按钮共用一处绑定）
        settings = (LOCAL / "ui" / "views" / "settings.js").read_text(encoding="utf-8")
        self.assertEqual(0, self.phone.count("PhonePanel.openComponents()"))
        self.assertEqual(2, self.phone.count('PhonePanel.openComponents("phone_control")'))
        self.assertEqual(1, settings.count('PhonePanel.openComponents("relogin_ocr")'))

    def test_tailscale_and_bare_cloudflared_are_not_imported_here(self):
        """Tailscale 是系统装的软件，不是组件包；裸 cloudflared.exe 的入口随弹窗改版去掉（IM01，后端接口不动）。
        fe-ocr-login 同步：原用例要求弹窗里有一行只检测不收文件的 Tailscale，原型的导入弹窗没有这一行，
        遇到 Tailscale 安装程序由自检结论当场说清（IM03），所以改成断言这一行已经不在。"""
        self.assertNotIn('id="comp-tailscale"', self.html)
        self.assertNotIn("btn-comp-tailscale-pick", self.html)
        self.assertNotIn("cloudflared.exe", self.html)
        self.assertNotIn(".comp-row-plain", self.css)
        self.assertNotIn("comp-tailscale-status", self.phone)


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


class WithdrawReasonTests(unittest.TestCase):
    """计划运行中撤回按钮禁用，原因要写在按钮下方（原型 Main.dc.html:738）。"""

    def test_reason_shows_only_while_a_plan_is_running(self):
        res = run_js(r"""
S.terms = { version: "v1", acceptedVersion: "v1", acceptedAt: "2026-11-04 10:00" };
S.busy = true;
paintTermsRow();
const why = document.querySelector("#terms-withdraw-why");
const busy = { hidden: why.hidden, text: why.textContent,
  disabled: document.querySelector("#btn-terms-withdraw").disabled };
S.busy = false;
paintTermsRow();
const idle = { hidden: why.hidden,
  disabled: document.querySelector("#btn-terms-withdraw").disabled };
out.push({ busy, idle });
""")
        row = res[0]
        self.assertFalse(row["busy"]["hidden"], "忙时原因必须可见，不能只放在悬停提示里")
        # 桩不解析静态 HTML：文案另用 index.html 契约钉住，这里只管显隐
        self.assertIn("报名计划运行中不能撤回同意，先停止计划。", read("ui/index.html"),
                      "撤回原因必须是原型 :738 原话")
        self.assertTrue(row["busy"]["disabled"], "忙时撤回按钮仍禁用")
        self.assertTrue(row["idle"]["hidden"], "不忙时原因收起")
        self.assertFalse(row["idle"]["disabled"], "不忙时撤回按钮可用")


class WithdrawRowPrototypeTests(unittest.TestCase):
    """设置里的撤回同意照原型重排（TM10/TM11，原型 Main:788-790/2490/2492/340）：
    条款行换句式并改句内链接钮；确认条换红色 .ph-confirm、确认钮换红色实心 btn-stop；
    行为不变——点「撤回同意」只展开确认条，点「确认撤回」才调 withdraw_terms。"""

    CONFIRM_COPY = ("撤回后，登录、自动登录、活动列表和报名计划会停用。"
                    "已保存的账号密码和登录信息不会删除。"
                    "要删除账号密码，在“登录恢复”里清除。")

    def confirm_bar(self):
        """确认条整块（单行 markup，含 id="terms-withdraw-confirm" 的那一行）。"""
        html = read("ui/index.html")
        return next(line for line in html.splitlines()
                    if 'id="terms-withdraw-confirm"' in line)

    def test_confirm_bar_copy_is_verbatim_with_red_stop_button(self):
        """TM11：确认条三句逐字照抄原型 Main:789（含全角引号“登录恢复”），脚部
        「先不撤回」线框｜「确认撤回」红色实心 btn-stop（复用关窗任务样式）。"""
        bar = self.confirm_bar()
        self.assertIn(self.CONFIRM_COPY, bar, "确认条文案必须与原型逐字一致")
        self.assertIn('class="ph-confirm"', bar, "确认条用红色确认条样式（原型 .ph-confirm bad-tint，Main:340）")
        self.assertIn('role="alert"', bar, "撤回是破坏性动作，确认条要有警示语义")
        self.assertIn('class="btn btn-line"', bar, "「先不撤回」保留线框钮")
        self.assertIn('class="btn btn-stop"', bar, "「确认撤回」必须是红色实心钮（原型 btn-stop）")
        self.assertIn("先不撤回", bar)
        self.assertIn("确认撤回", bar)

    def test_withdraw_is_inline_link_inside_terms_sentence(self):
        """TM10：「撤回同意」从独立线框钮改成条款句内的链接钮（原型 Main:2492 句内
        ph-link），与状态句同段、初始隐藏；动作区只留「查看条款」。"""
        html = read("ui/index.html")
        p_at = html.index('id="settings-terms-state"')
        para = html[html.rindex("<p>", 0, p_at):html.index("</p>", p_at)]
        self.assertIn('id="btn-terms-withdraw"', para, "「撤回同意」必须在条款句同一段里")
        btn_at = para.index('id="btn-terms-withdraw"')
        tag = para[para.rindex("<button", 0, btn_at):para.index(">", btn_at) + 1]
        self.assertIn('class="ph-link"', tag, "句内撤回入口是链接钮形态（原型 Main:2492）")
        self.assertIn("hidden", tag, "链接钮初始隐藏：显隐由 paintTermsRow 按同意状态接管")
        actions_at = html.index('id="btn-help-terms"')
        actions = html[html.rindex('<div class="help-actions"', 0, actions_at):
                       html.index("</div>", actions_at)]
        self.assertNotIn("btn-terms-withdraw", actions, "动作区不再保留独立的撤回线框钮")
        self.assertIn("查看条款", actions, "「查看条款」入口不动（terms-reader 任务已接好路由）")

    def test_old_row_and_confirm_copy_are_retired(self):
        """TM10/TM11：旧句式随原型重排退役——「同意了这一版」行文案、黄底旧确认块
        （含「重新同意就能继续用」）不得残留在设置抽屉；未同意句保留不计入。"""
        drawer = settings_drawer(read("ui/index.html"))
        self.assertNotIn("同意了这一版", drawer, "旧行文案已换成原型句式（TM10）")
        self.assertNotIn("重新同意就能继续用", drawer, "旧确认块文案已换成原型三句（TM11）")
        self.assertNotIn('class="terms-withdraw-confirm"', drawer,
                         "黄底旧确认条类名已换 .ph-confirm，样式规则一并删除")

    def test_row_sentence_uses_real_version_and_hyphen_time(self):
        """TM10：已同意句照原型 Main:2490——时间 MM-DD HH:mm（连字符，秒丢弃）、
        版本读真实数据；未同意句保留现有文案，链接钮未同意时隐藏。"""
        res = run_js(r"""
S.terms = { version: "r9", acceptedVersion: "r9", acceptedAt: "2026-11-08 09:12:33" };
paintTermsRow();
const line = document.querySelector("#settings-terms-state");
const acceptedText = line.textContent;
const linkShown = !document.querySelector("#btn-terms-withdraw").hidden;
S.terms.acceptedVersion = "";
paintTermsRow();
out.push({ acceptedText, linkShown,
  deniedText: line.textContent,
  linkHidden: document.querySelector("#btn-terms-withdraw").hidden });
""")
        row = res[0]
        self.assertEqual(row["acceptedText"],
                         "你在 11-08 09:12 同意了 r9 版。用户协议、隐私政策和开源许可的全文都可以在这里查看。",
                         "已同意句必须是原型句式：连字符时间＋真实版本（原型示意值 11-03 09:12 不写死）")
        self.assertTrue(row["linkShown"], "已同意且确认条未展开时显示句内「撤回同意」")
        self.assertEqual(row["deniedText"],
                         "还没有同意这一版：登录、登录检查、自动登录、刷新活动和开始计划都已停用。",
                         "未同意句保留现有文案不动")
        self.assertTrue(row["linkHidden"], "未同意时不显示撤回入口")

    def test_link_only_expands_and_confirm_calls_api(self):
        """TM10/TM11 行为不变（硬要求）：点「撤回同意」只展开确认条并藏起链接钮
        （原型 canWithdraw 含 !termsWAsk），点「先不撤回」收起复原，点「确认撤回」
        才 api("withdraw_terms") 且只调一次。"""
        res = run_js(r"""
const calls = [];
window.pywebview = { api: { withdraw_terms: () => { calls.push("withdraw_terms");
  return Promise.resolve({ ok: true, terms: { version: "r9", accepted_version: "", accepted_at: "" } }); } } };
S.terms = { version: "r9", acceptedVersion: "r9", acceptedAt: "2026-11-08 09:12:33" };
paintTermsRow();
const link = document.querySelector("#btn-terms-withdraw");
const box = document.querySelector("#terms-withdraw-confirm");
box.hidden = true; /* 桩不解析静态 hidden 属性：按 index.html 初始态补上 */
const before = { boxHidden: box.hidden, linkShown: !link.hidden };
link.click();
const afterAsk = { boxHidden: box.hidden, linkHidden: link.hidden, calls: calls.length };
document.querySelector("#btn-terms-withdraw-cancel").click();
const afterNo = { boxHidden: box.hidden, linkShown: !link.hidden, calls: calls.length };
link.click();
document.querySelector("#btn-terms-withdraw-confirm").click();
await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
out.push({ before, afterAsk, afterNo,
  afterConfirm: { boxHidden: box.hidden, calls: calls.length,
    linkHidden: link.hidden } });
""")
        row = res[0]
        self.assertTrue(row["before"]["boxHidden"] and row["before"]["linkShown"],
                        "初始：确认条收起、已同意显示链接钮")
        self.assertFalse(row["afterAsk"]["boxHidden"], "点「撤回同意」展开确认条")
        self.assertTrue(row["afterAsk"]["linkHidden"], "确认条展开时链接钮隐藏（原型 Main:2492）")
        self.assertEqual(row["afterAsk"]["calls"], 0, "展开确认条不得已经发出 withdraw_terms")
        self.assertTrue(row["afterNo"]["boxHidden"], "「先不撤回」收起确认条")
        self.assertTrue(row["afterNo"]["linkShown"], "收起后链接钮恢复")
        self.assertEqual(row["afterNo"]["calls"], 0, "「先不撤回」不发 withdraw_terms")
        self.assertTrue(row["afterConfirm"]["boxHidden"], "「确认撤回」后确认条收起")
        self.assertEqual(row["afterConfirm"]["calls"], 1, "只有「确认撤回」才调用 withdraw_terms")
        self.assertTrue(row["afterConfirm"]["linkHidden"], "撤回成功后回到未同意态，链接钮隐藏")

    def test_closing_drawer_collapses_confirm_bar(self):
        """TM10/TM11 既有行为保持：关抽屉强制收起确认条，重开抽屉时链接钮按状态恢复。"""
        res = run_js(r"""
S.terms = { version: "r9", acceptedVersion: "r9", acceptedAt: "2026-11-08 09:12:33" };
paintTermsRow();
const link = document.querySelector("#btn-terms-withdraw");
const box = document.querySelector("#terms-withdraw-confirm");
box.hidden = true; /* 桩不解析静态 hidden 属性：按 index.html 初始态补上 */
link.click();
const open = !box.hidden;
S.settingsOpen = true;
closeSettings(false);
const collapsed = box.hidden;
paintTermsRow();
out.push({ open, collapsed, linkShownAfterRepaint: !link.hidden });
""")
        row = res[0]
        self.assertTrue(row["open"], "前置：确认条已展开")
        self.assertTrue(row["collapsed"], "关抽屉必须强制收起确认条（既有行为不变）")
        self.assertTrue(row["linkShownAfterRepaint"], "收起后链接钮显隐恢复由 paintTermsRow 接管")


class DocAndCopySyncTests(unittest.TestCase):
    """文档和提示文案必须跟真实能力对得上：cloudflared 只从组件包来。"""

    def setUp(self):
        self.doc = (LOCAL.parent / "docs" / "PHONE_ACCESS.md").read_text(encoding="utf-8")
        self.readme = (LOCAL / "README.md").read_text(encoding="utf-8")
        self.html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        self.phone_view = (LOCAL / "ui" / "views" / "phone.js").read_text(encoding="utf-8")

    def test_docs_point_at_the_component_package_not_the_path(self):
        """task-1 之后 PATH 回退没了：文档再教人自备 cloudflared 就是骗人。"""
        for name, text in (("PHONE_ACCESS.md", self.doc), ("local/README.md", self.readme)):
            self.assertNotIn("需要用户自行准备", text, "%s 还在教用户自备 cloudflared" % name)
            self.assertNotIn("PATH 或安装包 bin", text, "%s 还在把 PATH 当合法来源" % name)
            self.assertIn("组件包", text, "%s 没写清 cloudflared 从组件包来" % name)
        # 版本、安装方式与校验口径要能被用户读到，不能只活在代码里
        self.assertIn("2026.10.7", self.doc)
        self.assertIn("SHA-256", self.doc)
        # task-4 起组件可以一键装：文档要写清这条路和两条通道的长期/临时差别
        self.assertIn("下载并安装组件包", self.doc)
        self.assertIn("长期通道", self.doc)
        self.assertIn("不会自动升级", self.doc)

    def test_ui_copy_matches_the_bundled_binary(self):
        self.assertIn("组件包", self.html)
        # fe-phone 同步：「不用另装」那段 Cloudflare 警告按 PH21 删除，同一意思收进 Cloudflare 卡片（PH17）
        self.assertIn("组件里已带好", self.phone_view)
        self.assertIn("组件包", self.phone_view)

    def test_hide_choice_says_how_it_comes_back(self):
        """「隐藏到后台」必须交代两条唤回路，否则用户不知道窗口去哪了。"""
        start = self.html.index('id="btn-close-hide"')
        block = self.html[start:].split("</button>")[0]
        self.assertIn("托盘", block)
        self.assertIn("手机页", block)
        # CW05：禁用原因句照原型 Main:1715 禁用分支改写（旧句「…两者都没有时工具不会隐藏」随卡文重写退役）
        self.assertIn("叫不回来", block)
        self.assertIn("不能隐藏", block)

    def test_the_install_entry_survives_a_missing_component_package(self):
        """源码版模块可用不代表组件包在：通道报缺失时入口必须还看得见。

        以前是 `phoneInstall.hidden = phoneReady`，源码版 segno 一导入就 ready，
        按钮被藏起来，Cloudflare 却因为没组件包而不可用 —— 用户无处可补装。
        """
        self.assertIn("cloudflared_missing", self.phone_view)
        self.assertIn("componentMissing", self.phone_view)
        self.assertIn("安装/更换组件包", self.phone_view)
        self.assertNotIn("phoneInstall.hidden = phoneReady;", self.phone_view)

    def test_a_check_event_refreshes_the_desktop_relogin_card(self):
        """重登成功后顶栏会变，右侧「电脑续登录」卡片也得跟着刷新。"""
        app_js = (LOCAL / "ui" / "app.js").read_text(encoding="utf-8")
        self.assertIn("window.PhonePanel", app_js)
        self.assertIn("PhonePanel.refresh", app_js)
        # 顶层 const 不会挂到 window 上：必须显式暴露，否则上面的调用永远是空
        self.assertIn("window.PhonePanel = PhonePanel;", self.phone_view)


# 新工作台（决策 014 / 设计 2026-11-02）专属断言：计划 test-ui-contract 要求的新增覆盖。
# 学校时刻文本按 SCHOOL_OFFSET_S 现算，片段里不写死日期，免得夹具随日历过期。
WB_STAMP_JS = r"""
const stamp = (sec) => {
  const d = new Date((sec + SCHOOL_OFFSET_S) * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return d.getUTCFullYear() + "-" + p(d.getUTCMonth() + 1) + "-" + p(d.getUTCDate()) + " "
    + p(d.getUTCHours()) + ":" + p(d.getUTCMinutes()) + ":" + p(d.getUTCSeconds());
};
const t0 = 1700000000000;
setBusinessNow(t0);
const now = t0 / 1000;
const seed = (list) => { S.items = list.map(normalize); S.byId = new Map(S.items.map((i) => [String(i.id), i])); };
"""


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
