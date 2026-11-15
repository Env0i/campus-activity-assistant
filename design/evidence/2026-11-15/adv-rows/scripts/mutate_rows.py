#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本批「一项一行」排版的变异测试：一处一处把新写的推导与绘制改坏，看是不是有用户看得到的东西变红。

每条变异都只改一处源码（在临时副本里改，仓库本身不动），然后跑与它对应的用例：
改坏之后必须有断言失败，且失败要落在「圆点什么色、状态句哪一句、按钮在不在、小字写不写」这类
用户看得到的结果上。不红的变异要么是真的等价（写理由），要么说明这一档没有被守住（那就补用例）。

用法（仓库根）：
    python -B design/evidence/2026-11-15/adv-rows/scripts/mutate_rows.py

@author Author
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
ROW = "local/ui/features/components/state-row.js"
VIEW_PHONE = "local/ui/features/phone-access/view.js"
ACTIONS = "local/ui/features/components/actions.js"
VIEW = "local/ui/features/components/view-row.js"
PHONE_VIEW = "local/ui/features/phone-access/view.js"

# 名字, 文件, 原文, 改坏, 用例文件, 可选 -k 片段, 等价理由
MUTATIONS = [
    # ---- rowHead：每一格的文字、颜色、按钮、小字、进度条 ----
    ("没装那一档说成「未安装」", ROW,
     '    head.text = "没装";\n',
     '    head.text = "未安装";\n',
     "test_settings_adv_rows.py", "test_missing_row_offers_the_install_button", ""),
    ("没装时的主按钮改成线框", ROW,
     'head.button = button(installLabel("missing", facts.failed), "btn-solid", "install");',
     'head.button = button(installLabel("missing", facts.failed), "btn-line", "install");',
     "test_settings_adv_rows.py", "test_missing_row_offers_the_install_button", ""),
    ("需要更新时还说下载并安装", ROW,
     '  if (state === "outdated") return "更新组件";\n',
     "",
     "test_settings_adv_rows.py", "test_outdated_explains_what_does_not_need_redoing", ""),
    ("坏了时还说重新下载", ROW,
     '  if (state === "broken") return "重新安装";\n',
     "",
     "test_settings_adv_rows.py", "test_broken_says_reinstall_and_puts_the_words_below_the_header", ""),
    ("下载中不写已下与总量", ROW,
     '  return total && done ? "下载中 " + done + " / " + total + " MB" : "下载中";\n',
     '  return "下载中";\n',
     "test_settings_adv_rows.py", "test_downloading_says_how_much_and_shows_the_bar", ""),
    ("下载中不给进度条数字", ROW,
     "  if (total <= 0) return 0;\n  return Math.max(0, Math.min(100, Math.round((done / total) * 100)));",
     "  if (total <= 0) return 0;\n  return 0;",
     "test_settings_adv_rows.py", "test_downloading_says_how_much_and_shows_the_bar", ""),
    ("校验中的进度条不写满", ROW,
     '    head.text = "下载完了，正在校验…";\n    head.tone = "blue";\n    head.bar = 100;\n',
     '    head.text = "下载完了，正在校验…";\n    head.tone = "blue";\n    head.bar = 40;\n',
     "test_settings_adv_rows.py", "test_verifying_is_a_disabled_button_with_a_full_bar", ""),
    ("校验中把「校验中…」按钮收掉", ROW,
     '    head.button = button(VERIFY_CANCEL_TEXT, "btn-line", "cancel");\n',
     "",
     "test_settings_adv_rows.py", "test_verifying_is_a_disabled_button_with_a_full_bar", ""),
    ("安装中不给「正在安装组件…」这句", ROW,
     '    head.text = "正在安装组件…";\n',
     '    head.text = "";\n',
     "test_settings_adv_rows.py", "test_installing_takes_the_button_away", ""),
    ("检查中仍说旧文案", ROW,
     'const CHECKING_TEXT = "正在确认组件状态…";',
     'const CHECKING_TEXT = "正在检查组件…";',
     "test_settings_adv_rows.py", "test_checking_without_a_cache_says_it_is_looking", ""),
    ("等锁时不把圆点变蓝", ROW,
     '    head.tone = "blue";\n    head.button = null;\n',
     '    head.tone = "grey";\n    head.button = null;\n',
     "test_settings_adv_rows.py", "test_locked_with_a_cached_answer_keeps_the_words_and_blues_the_dot", ""),
    ("超时那句说成正常等锁", ROW,
     '    head.text = WAIT_TEXT;\n',
     '    head.text = CHECKING_TEXT;\n',
     "test_settings_adv_rows.py", "test_timeout_is_an_amber_sentence_with_a_retry", ""),
    ("超时不给「重试」", ROW,
     '    head.button = button(RETRY_TEXT, "btn-line", "retry");\n    return;\n  }\n  if (probe === "unreadable") {',
     '    return;\n  }\n  if (probe === "unreadable") {',
     "test_settings_adv_rows.py", "test_timeout_is_an_amber_sentence_with_a_retry", ""),
    ("读不到时不换圆点颜色", ROW,
     '    head.tone = "amber-dot";\n',
     '    head.tone = "grey";\n',
     "test_settings_adv_rows.py", "test_unreadable_keeps_the_words_and_adds_an_amber_sentence", ""),
    ("读不到时不写小字", ROW,
     '    head.note = { text: UNREADABLE_TEXT, tone: "amber" };\n',
     "",
     "test_settings_adv_rows.py", "test_unreadable_keeps_the_words_and_adds_an_amber_sentence", ""),
    ("需要更新时不解释哪件事不用重做", ROW,
     '    head.note = { text: kind === "phone" ? OUTDATED_NOTE_PHONE : OUTDATED_NOTE_OCR, tone: "" };\n',
     "",
     "test_settings_adv_rows.py", "test_outdated_explains_what_does_not_need_redoing", ""),
    ("坏了时那句不写在小字里", ROW,
     '    head.note = { text: BROKEN_NOTE, tone: "red" };\n',
     "",
     "test_settings_adv_rows.py", "test_broken_says_reinstall_and_puts_the_words_below_the_header", ""),
    ("坏了时圆点不变红", ROW,
     '    head.text = "加载失败";\n    head.tone = "red";\n',
     '    head.text = "加载失败";\n    head.tone = "grey";\n',
     "test_settings_adv_rows.py", "test_broken_says_reinstall_and_puts_the_words_below_the_header", ""),
    ("等手机连接时圆点不慢闪", ROW,
     '  head.blink = link.link === "waiting";\n',
     '  head.blink = false;\n',
     "test_settings_adv_rows.py", "test_running_row_follows_the_link_state", ""),
    ("已断开时写成灰字却不换字", ROW,
     '  head.text = String(link.title || "等手机连接");\n',
     '  head.text = "等手机连接";\n',
     "test_settings_adv_rows.py", "test_running_row_follows_the_link_state", ""),
    ("关闭中不给「正在停止…」这句", ROW,
     '    head.text = "正在停止…";\n',
     '    head.text = "";\n',
     "test_settings_adv_rows.py", "test_starting_and_stopping_have_no_button", ""),
    ("确认关闭时按钮还能点", ROW,
     '  head.button = button("关闭手机访问", "btn-line", "stop", env.stopAsk);',
     '  head.button = button("关闭手机访问", "btn-line", "stop", false);',
     "test_settings_adv_rows.py", "test_stop_confirm_disables_the_close_button", ""),
    ("组件停用时不告诉用户去启用", ROW,
     '    head.button = button("启用手机控制", "btn-line", "enable", env.busy);\n',
     "",
     "test_settings_adv_rows.py", "test_disabled_and_off_rows", ""),
    ("没开时不说用哪条通道", ROW,
     '  head.text = "未开启 · 通道用 " + (env.channelName || "Tailscale");\n',
     '  head.text = "未开启";\n',
     "test_settings_adv_rows.py", "test_disabled_and_off_rows", ""),
    ("开不起来时还当它能开", VIEW_PHONE,
     '      startFailed: !!(notes.offErr || tunnelGone),\n',
     '      startFailed: false,\n',
     "test_settings_adv_rows.py", "test_start_failure_renames_the_button", ""),
    ("开启失败后不改口「重新开启」", ROW,
     '  head.button = button(env.startFailed ? "重新开启" : "开启", "btn-solid", "start", env.startDisabled);\n',
     '  head.button = button("开启", "btn-solid", "start", env.startDisabled);\n',
     "test_settings_adv_rows.py", "test_start_failure_renames_the_button", ""),
    ("补装入口不再看缺包", VIEW_PHONE,
     '    const packageBtn = phoneShow("#btn-phone-package", phase === "off" && componentMissing && !starting);\n',
     '    const packageBtn = phoneShow("#btn-phone-package", false);\n',
     "test_settings_adv_rows.py", "test_missing_cloudflared_keeps_start_and_puts_the_package_in_the_detail", ""),
    ("原因又挤回红条", VIEW_PHONE,
     '    phoneText("#phone-off-error", phase === "off" && failed ? downloadFailText(download) : "");\n',
     '    phoneText("#phone-off-error", phase === "off" ? (notes.offErr || startErrorText()) : "");\n',
     "test_settings_adv_rows.py", "test_start_failure_renames_the_button", ""),
    ("补装那只按钮没人接", ACTIONS,
     '  if (pack) pack.addEventListener("click", () => PhonePanel.openComponents("phone_control"));\n',
     '',
     "test_settings_adv_rows.py", "test_the_package_button_opens_the_import_dialog", ""),
    ("刚装好那句不再落到小字里", ROW,
     "  if (!head.note && env.note) head.note = { text: String(env.note), tone: \"green\" };\n",
     "",
     "test_settings_adv_rows.py", "test_a_panel_note_still_lands_below_the_header_while_checking", ""),
    ("装好了但没启用时还说已启用", ROW,
     '      head.text = "已装好还没启用";\n',
     '      head.text = "已启用";\n',
     "test_settings_adv_rows.py", "test_installed_but_not_enabled_offers_enable", ""),
    ("已启用时不写版本号", ROW,
     '      head.text = version ? "已启用 · 版本 " + version : "已启用";\n',
     '      head.text = "已启用";\n',
     "test_settings_adv_rows.py", "test_enabled_row_shows_the_version", ""),
    ("手机行默认收起、识别行默认展开", ROW,
     "const ROW_OPEN = { phone: true, ocr: false };",
     "const ROW_OPEN = { phone: false, ocr: true };",
     "test_settings_adv_rows.py", "test_default_open_close_and_the_arrow", ""),

    # ---- view-row：落 DOM 的每一处 ----
    ("按钮位不先收起别的按钮", VIEW,
     "  Object.keys(buttons).forEach((action) => rowShow(buttons[action], false));\n",
     "",
     "test_settings_adv_rows.py", "test_each_phase_lights_at_most_one_button", ""),
    ("小字不看有没有内容都写出来", VIEW,
     "    note.hidden = !head.note;\n",
     "    note.hidden = false;\n",
     "test_settings_adv_rows.py", "test_checking_without_a_cache_says_it_is_looking", ""),
    ("圆点不带颜色档", VIEW,
     '    chip.className = "adv-s " + head.tone + (head.blink ? " blink" : "");\n',
     '    chip.className = "adv-s";\n',
     "test_settings_adv_rows.py", "test_locked_with_a_cached_answer_keeps_the_words_and_blues_the_dot", ""),
    ("进度条永远收着", VIEW,
     "  const bar = rowShow(spec.barId, typeof head.bar === \"number\");\n",
     "  const bar = rowShow(spec.barId, false);\n",
     "test_settings_adv_rows.py", "test_downloading_says_how_much_and_shows_the_bar", ""),
    ("箭头 aria 不跟着开合走", VIEW,
     '    toggle.setAttribute("aria-expanded", open ? "true" : "false");\n',
     '    toggle.setAttribute("aria-expanded", "true");\n',
     "test_settings_adv_rows.py", "test_clicking_the_arrow_flips_the_detail_area", ""),
    ("展开区不跟着开合收起", VIEW,
     "  rowShow(spec.detailId, open);\n",
     "  rowShow(spec.detailId, true);\n",
     "test_settings_adv_rows.py", "test_clicking_the_arrow_flips_the_detail_area", ""),
    ("坏了不给导入兜底", VIEW,
     "  rowShow(spec.importLineId, (facts.state === \"missing\" || facts.state === \"outdated\"\n"
     "    || facts.state === \"broken\") && facts.failed && !facts.installing);\n",
     "  rowShow(spec.importLineId, (facts.state === \"missing\" || facts.state === \"outdated\")\n"
     "    && facts.failed && !facts.installing);\n",
     "test_settings_adv_rows.py", "test_broken_row_that_also_failed_a_download_keeps_the_import_line", ""),
    ("没装块不看状态", VIEW,
     '  rowShow(spec.missingId, facts.state === "missing" && !facts.installing);\n',
     "  rowShow(spec.missingId, true);\n",
     "test_settings_adv_rows.py", "test_enabled_row_shows_the_version", ""),

    # ---- 开启失败与隧道断开：原因落在标题行下那条红条里，不回到小字 ----
    ("开不起来的原因不写进红条", PHONE_VIEW,
     '    const componentErr = phase === "off" ? startError\n',
     '    const componentErr = phase === "off" ? ""\n',
     "test_settings_adv_rows.py", "test_start_failure_renames_the_button", ""),
    ("开不起来的原因又写回标题行下那行小字", PHONE_VIEW,
     '      componentError: componentErr,\n',
     '      componentError: componentErr,\n      note: startError,\n',
     "test_settings_adv_rows.py", "test_start_failure_renames_the_button", ""),
    ("未开启时红条的条件写成开着才讲原因", PHONE_VIEW,
     '    const componentErr = phase === "off" ? startError\n',
     '    const componentErr = phase === "on" ? startError\n',
     "test_settings_adv_rows.py", "test_tunnel_gone_puts_the_reason_in_the_red_bar", ""),

    # ---- 手机一行：点「关闭手机访问」时自动展开 ----
    ("确认块不自动展开", PHONE_VIEW,
     '    if (PhonePanel.stopAsk) setRowOpen("phone", true);\n',
     "",
     "test_settings_adv_rows.py", "test_asking_to_close_opens_the_confirmation_area", ""),
]

NOT_VISIBLE = ("SyntaxError", "ImportError", "ModuleNotFoundError", "IndentationError")


def copy_tree(work: Path) -> None:
    shutil.copytree(REPO / "local", work / "local",
                    ignore=shutil.ignore_patterns("data", "__pycache__", "*.pyc"))


def run_tests(work: Path, pattern: str, keyword: str) -> tuple[bool, str]:
    cmd = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
           "-p", pattern]
    if keyword:
        cmd += ["-k", keyword]
    res = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=900)
    return res.returncode == 0, (res.stdout or "") + (res.stderr or "")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mutate-rows-"))
    try:
        copy_tree(work)
        ok, log = run_tests(work, "test_settings_adv_rows.py", "")
        if not ok:
            print("原始副本就不绿，先修测试：\n" + log[-2000:])
            return 1
        print("原始副本：用例全绿")
        survived = []
        for index, (name, rel, old, new, pattern, keyword, reason) in enumerate(MUTATIONS, 1):
            path = work / rel
            raw = path.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            text = raw.replace("\r\n", "\n")
            if old not in text:
                print("%2d. 跳过（找不到原文）：%s" % (index, name))
                survived.append((name, "找不到原文"))
                continue
            path.write_bytes(text.replace(old, new, 1).replace("\n", "\r\n" if crlf else "\n")
                             .encode("utf-8"))
            try:
                ok, log = run_tests(work, pattern, keyword)
            finally:
                path.write_bytes(raw.encode("utf-8"))
            if ok:
                survived.append((name, reason or "没有用例守住"))
                print("%2d. 存活：%s" % (index, name))
                continue
            if any(mark in log for mark in NOT_VISIBLE):
                survived.append((name, "红在语法/导入，不是用户看得到的结果"))
                print("%2d. 红错了地方：%s" % (index, name))
                continue
            print("%2d. 红：%s" % (index, name))
        print("\n变异条数：%d；存活：%d" % (len(MUTATIONS), len(survived)))
        for name, why in survived:
            print("  - %s（%s）" % (name, why))
        return 1 if survived else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
