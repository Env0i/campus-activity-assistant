#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本批「顶栏手机标识与详情卡」的变异测试：一处一处改坏，看有没有用户看得到的东西变红。

每条变异只改一处源码（在临时副本里改，仓库本身不动），再跑与它对应的用例。
改坏之后必须有断言失败，而且失败要落在「标识写哪句话、什么颜色档、转圈在不在、
读屏念什么、卡片第几行写什么」这类用户看得到的结果上。
不红的变异要么真的等价（写理由），要么说明这一档没被守住（补用例）。

样式表不在测试环境里（沙箱没有 CSS），颜色与慢闪由 design/evidence/2026-11-15/topbar-phone/
scripts/shots.py 在 Edge 里读真实计算值核对；把 `.pill.blink svg` 那条规则删掉会让
`[fail] waiting app ... 等手机连接时 svg 的 animation-name 是 none` 变红（本批跑过）。

用法（仓库根）：
    python -B design/evidence/2026-11-15/topbar-phone/scripts/mutate_topbar.py

@author Author
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
CARDS = "local/ui/views/status-cards.js"
LINK = "local/ui/features/phone-access/state-link.js"
PHONE_LINK = "test_phone_link.py"
TOPBAR = "test_topbar_phone.py"

# 名字, 文件, 原文, 改坏, 用例文件, 可选 -k 片段, 等价理由
MUTATIONS = [
    # ---- 标识的五种样子 ----
    ("开启中不算忙（只认停止中）", CARDS,
     'const busy = pending === "starting" || pending === "stopping";',
     'const busy = pending === "stopping";',
     TOPBAR, "test_starting_shows_a_spinner", ""),
    ("停止中不算忙（只认开启中）", CARDS,
     'const busy = pending === "starting" || pending === "stopping";',
     'const busy = pending === "starting";',
     TOPBAR, "test_stopping_also_shows_the_spinner", ""),
    ("开启中也说正在停止", CARDS,
     'const text = pending === "starting" ? "正在开启…" : "正在停止…";',
     'const text = "正在停止…";',
     TOPBAR, "test_starting_shows_a_spinner", ""),
    ("等连接不给提醒档", CARDS,
     'const tone = look.tone === "ok" ? " is-ok" : (look.tone === "warn" ? " is-warn blink" : "");',
     'const tone = look.tone === "ok" ? " is-ok" : "";',
     TOPBAR, "test_waiting_blinks_in_amber", ""),
    ("等连接不慢闪", CARDS,
     'const tone = look.tone === "ok" ? " is-ok" : (look.tone === "warn" ? " is-warn blink" : "");',
     'const tone = look.tone === "ok" ? " is-ok" : (look.tone === "warn" ? " is-warn" : "");',
     TOPBAR, "test_waiting_blinks_in_amber", ""),
    ("已连接不给绿档", CARDS,
     'const tone = look.tone === "ok" ? " is-ok" : (look.tone === "warn" ? " is-warn blink" : "");',
     'const tone = look.tone === "warn" ? " is-warn blink" : "";',
     TOPBAR, "test_connected_is_green", ""),
    ("转圈一直在", CARDS,
     "  if (spin) spin.hidden = !look.busy;",
     "  if (spin) spin.hidden = false;",
     TOPBAR, "test_connected_is_green", ""),
    ("转圈永远收着", CARDS,
     "  if (spin) spin.hidden = !look.busy;",
     "  if (spin) spin.hidden = true;",
     TOPBAR, "test_starting_shows_a_spinner", ""),
    ("没开也把标识显示出来", CARDS,
     'return { show: view.link !== "off", link: view.link, text: view.title, tone: view.tone, busy: false };',
     'return { show: true, link: view.link, text: view.title, tone: view.tone, busy: false };',
     TOPBAR, "test_not_running_hides_both", ""),
    ("读屏不写「查看详情」", CARDS,
     'badge.setAttribute("aria-label", spoken + "，查看详情");',
     'badge.setAttribute("aria-label", spoken);',
     TOPBAR, "test_aria_label_says_which_state_it_is", ""),
    ("等连接的读屏不写全", CARDS,
     'const spoken = look.busy ? look.text : (look.link === "waiting" ? "手机访问已开启，等手机连接" : look.text);',
     'const spoken = look.text;',
     TOPBAR, "test_aria_label_says_which_state_it_is", ""),
    # ---- 详情卡 ----
    ("卡片小标永远是长期地址", CARDS,
     '  if (cap) cap.textContent = state.channel === "cloudflare" ? "临时地址" : "长期地址";',
     '  if (cap) cap.textContent = "长期地址";',
     TOPBAR, "test_cloudflare_card_says_the_address_is_temporary", ""),
    ("卡片底部提醒写反", CARDS,
     '      ? (state.channel === "cloudflare" ? PHONE_CARD_NOTE.cloudflare : PHONE_CARD_NOTE.tailscale)',
     '      ? (state.channel === "cloudflare" ? PHONE_CARD_NOTE.tailscale : PHONE_CARD_NOTE.cloudflare)',
     TOPBAR, "test_cloudflare_card_says_the_address_is_temporary", ""),
    ("副句不分连接状态", CARDS,
     '  $("#phone-pop-sub").textContent = state.running ? (PHONE_CARD_SUB[view.link] || "") : "到设置 → 高级功能里开启";',
     '  $("#phone-pop-sub").textContent = state.running ? PHONE_CARD_SUB.waiting : "到设置 → 高级功能里开启";',
     TOPBAR, "test_gone_card_explains", ""),
    ("最近访问永远写占位符", CARDS,
     '    rows.push(["手机最近访问", view.ago || "—"]);',
     '    rows.push(["手机最近访问", "—"]);',
     TOPBAR, "test_connected_card_lists_the_phone", ""),
    ("只有活动会话也说 1 台手机", CARDS,
     '    rows.push(["已配对", count > 1 ? count + " 台手机" : (count === 1 ? "1 台手机" : "有手机连着")]);',
     '    rows.push(["已配对", count > 1 ? count + " 台手机" : "1 台手机"]);',
     TOPBAR, "test_live_session_without_pairing", ""),
    ("地址不去掉协议头", CARDS,
     '    ["地址", String(state.address || "—").replace(/^https?:\\/\\//, "").replace(/\\/$/, "")],',
     '    ["地址", String(state.address || "—")],',
     TOPBAR, "test_waiting_card_offers_the_pairing_code", ""),
    ("配对码不写倒计时", CARDS,
     '  rows.push(["配对码", info.code ? countdown(info.expires_in) + " 后换新" : "在设置里看配对码"]);',
     '  rows.push(["配对码", "在设置里看配对码"]);',
     TOPBAR, "test_waiting_card_offers_the_pairing_code", ""),
    ("没开也列通道与地址", CARDS,
     "  if (!state.running) return [];\n",
     "",
     TOPBAR, "test_card_stays_empty_while_the_phone_access_is_off", ""),
    # ---- 连接状态的推导 ----
    ("卡片小 chip 把「等连接」写全", LINK,
     '  waiting: { title: "等手机连接", big: "等手机连接", chip: "等连接", tone: "warn" },',
     '  waiting: { title: "等手机连接", big: "等手机连接", chip: "等手机连接", tone: "warn" },',
     TOPBAR, "test_waiting_card_offers_the_pairing_code", ""),
    ("已断开的标题不带多久以前", LINK,
     '  if (link === "disconnected") return withAgo(link, ago, ago);',
     '  if (link === "disconnected") return withAgo(link, "", ago);',
     PHONE_LINK, "test_disconnected_shows_how_long_ago", ""),
    ("多久以前不带给详情卡", LINK,
     '           chip: base.chip, tone: base.tone, ago: ago || "" };',
     '           chip: base.chip, tone: base.tone, ago: "" };',
     TOPBAR, "test_connected_card_lists_the_phone", ""),
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
    work = Path(tempfile.mkdtemp(prefix="mutate-topbar-"))
    try:
        copy_tree(work)
        for pattern in (TOPBAR, PHONE_LINK):
            ok, log = run_tests(work, pattern, "")
            if not ok:
                print("原始副本就不绿（%s），先修测试：\n%s" % (pattern, log[-2000:]))
                return 1
        print("原始副本：两个文件全绿")
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
