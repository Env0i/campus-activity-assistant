# -*- coding: utf-8 -*-
"""界面契约：渠道安装、高级组件弹窗与文档同步。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))

from fixtures.ui_harness import LOCAL, read  # noqa: E402


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

    def test_import_fallback_sits_outside_missing_blocks(self):
        """导入兜底不能挂在「没装」块里：更新失败停在 outdated 时整块收着，挂进去就看不见。"""
        for line_id, block_id in (("phone-import-line", "phone-missing"),
                                  ("ocr-import-line", "ocr-missing")):
            self.assertLess(self.html.index('id="' + line_id + '"'),
                            self.html.index('id="' + block_id + '"'),
                            line_id + " 必须在 " + block_id + " 之前")

    def test_no_path_box_or_raw_binary_picker_for_normal_users(self):
        for forbidden in ('id="phone-cloudflared-path"',
                          'id="btn-phone-cloudflared-inspect"',
                          "cloudflared.exe 路径"):
            self.assertNotIn(forbidden, self.html, forbidden)


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


if __name__ == "__main__":
    unittest.main()
