# -*- coding: utf-8 -*-
"""界面契约：协议闸门、同意回环、许可文档与撤回原因。"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read, run_js, settings_drawer, WB_STAMP_JS  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
