#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机连接状态的变异测试：把推导里的一条判断、一句文字、一处取字改坏，看有没有用户看得到的东西变红。

每条变异只改一处源码（在临时副本里改，仓库本身不动），然后跑与它对应的用例，或者跑
模块图守卫。改坏之后必须有断言失败，且失败要落在「哪句字、什么语气、标识出不出来」
这类用户看得到的结果上。挂回那一行由模块图守卫守（unattached 不为空即红），其余每条
都必须红在一条界面断言上；不红的要么是真等价（写理由），要么补用例再变异到红。

用法（仓库根）：
    python -B design/evidence/2026-11-15/phone-link/scripts/mutate_link.py

@author Author
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LINK = "local/ui/features/phone-access/state-link.js"
VIEW = "local/ui/features/phone-access/view.js"
CARDS = "local/ui/views/status-cards.js"
GLOBALS = "local/ui/legacy-globals.js"
MACHINE = "local/ui/features/components/state-machine.js"

LINK_TEST = "test_phone_link.py"
MACHINE_TEST = "test_component_machine.py"

# 每条：名字、文件、原文、改坏、守它的用例文件（空表示用模块图守卫）、-k 片段、等价理由
MUTATIONS = [
    ("没开也说成等手机连接", LINK,
     '  if (!state.running) return withAgo("off", "");\n',
     '  if (!state.running && !state.address) return withAgo("off", "");\n',
     LINK_TEST, "", ""),
    ("先把 waiting 当成已连接", LINK,
     '  if (link === "waiting" || link === "connected") return withAgo(link, "");\n',
     '  if (link === "waiting" || link === "connected") return withAgo("connected", "");\n',
     LINK_TEST, "", ""),
    ("把 connected 当成等手机连接", LINK,
     '  if (link === "waiting" || link === "connected") return withAgo(link, "");\n',
     '  if (link === "waiting" || link === "connected") return withAgo("waiting", "");\n',
     LINK_TEST, "", ""),
    ("已断开时不写多久没来", LINK,
     '  if (link === "disconnected") return withAgo(link, contactAgo(state.last_contact_ago_s));\n',
     '  if (link === "disconnected") return withAgo(link, "");\n',
     LINK_TEST, "", ""),
    ("秒数为空也拼一句「0 秒前」", LINK,
     '  if (ago === null || ago === undefined || ago === "") return "";\n',
     '  if (ago === undefined || ago === "") return "";\n',
     LINK_TEST, "", ""),
    ("退回规则永远说等手机连接", LINK,
     '  return withAgo(phoneLinkedNow(state) ? "connected" : "waiting", "");\n',
     '  return withAgo("waiting", "");\n',
     LINK_TEST, "", ""),
    ("退回规则把两档对调", LINK,
     '  return withAgo(phoneLinkedNow(state) ? "connected" : "waiting", "");\n',
     '  return withAgo(phoneLinkedNow(state) ? "waiting" : "connected", "");\n',
     LINK_TEST, "", ""),
    ("等同连接那句换成别的字", LINK,
     '  waiting: { title: "等手机连接", big: "等手机连接", chip: "等手机连接", tone: "warn" },\n',
     '  waiting: { title: "等手机来", big: "等手机连接", chip: "等手机连接", tone: "warn" },\n',
     LINK_TEST, "", ""),
    ("已连接的小 chip 换成别的字", LINK,
     '  connected: { title: "手机已连接", big: "手机已连接", chip: "已连接", tone: "ok" },\n',
     '  connected: { title: "手机已连接", big: "手机已连接", chip: "已连上", tone: "ok" },\n',
     LINK_TEST, "", ""),
    ("已断开的标题行换成别的字", LINK,
     '  disconnected: { title: "已断开", big: "已断开", chip: "已断开", tone: "" },\n',
     '  disconnected: { title: "断开了", big: "已断开", chip: "已断开", tone: "" },\n',
     LINK_TEST, "", ""),
    ("已连接不再给 ok 语气", LINK,
     '  connected: { title: "手机已连接", big: "手机已连接", chip: "已连接", tone: "ok" },\n',
     '  connected: { title: "手机已连接", big: "手机已连接", chip: "已连接", tone: "" },\n',
     LINK_TEST, "", ""),
    ("等手机连接不再给提醒语气", LINK,
     '  waiting: { title: "等手机连接", big: "等手机连接", chip: "等手机连接", tone: "warn" },\n',
     '  waiting: { title: "等手机连接", big: "等手机连接", chip: "等手机连接", tone: "" },\n',
     LINK_TEST, "", ""),
    ("没开的详情卡小 chip 换成别的字", LINK,
     '  off: { title: "", big: "手机访问未开启", chip: "未开启", tone: "" },\n',
     '  off: { title: "", big: "手机访问未开启", chip: "未开", tone: "" },\n',
     LINK_TEST, "", ""),
    ("抽屉 chip 不写连接那句字", VIEW,
     '      else if (phase === "on") { const view = phoneLinkView(st); text = view.title;'
     ' tone = view.tone; link = view.link; }\n',
     '      else if (phase === "on") { const view = phoneLinkView(st); text = "";'
     ' tone = view.tone; link = view.link; }\n',
     LINK_TEST, "", ""),
    ("抽屉 chip 不写语气", VIEW,
     '      else if (phase === "on") { const view = phoneLinkView(st); text = view.title;'
     ' tone = view.tone; link = view.link; }\n',
     '      else if (phase === "on") { const view = phoneLinkView(st); text = view.title;'
     ' tone = ""; link = view.link; }\n',
     LINK_TEST, "", ""),
    ("抽屉 chip 不写 data-link", VIEW,
     '      chip.dataset.link = link;\n',
     '      chip.dataset.link = "";\n',
     LINK_TEST, "", ""),
    ("顶栏标识没开也显示", CARDS,
     '  badge.hidden = view.link === "off";\n',
     '  badge.hidden = false;\n',
     LINK_TEST, "", ""),
    ("顶栏标识一直带 is-ok", CARDS,
     '  badge.className = "pill phone-badge" + (view.tone === "ok" ? " is-ok" : "");\n',
     '  badge.className = "pill phone-badge is-ok";\n',
     LINK_TEST, "", ""),
    ("顶栏标识的字不写", CARDS,
     '  $("#phone-badge-text").textContent = view.title;\n',
     '  $("#phone-badge-text").textContent = "";\n',
     LINK_TEST, "", ""),
    ("顶栏标识不写 data-link", CARDS,
     '  badge.dataset.link = view.link;\n',
     '  badge.dataset.link = "";\n',
     LINK_TEST, "", ""),
    ("详情卡小 chip 写了大字那句", CARDS,
     '  $("#phone-pop-chip-text").textContent = view.chip;\n',
     '  $("#phone-pop-chip-text").textContent = view.big;\n',
     LINK_TEST, "", ""),
    ("详情卡大字写了小 chip 那句", CARDS,
     '  $("#phone-pop-big").textContent = view.big;\n',
     '  $("#phone-pop-big").textContent = view.chip;\n',
     LINK_TEST, "", ""),
    ("详情卡小 chip 不写语气", CARDS,
     '  if (chip) chip.dataset.tone = view.tone;\n',
     '  if (chip) chip.dataset.tone = "";\n',
     LINK_TEST, "", ""),
    ("详情卡配对行改成看活动会话", CARDS,
     '  const paired = phoneLinkedNow(state);\n',
     '  const paired = !!state.live_session;\n',
     LINK_TEST, "test_pairing_blocks_do_not_follow_the_link", ""),
    ("漏挂 phoneLinkView 到 window", GLOBALS,
     '  window.phoneLinkView = phoneLinkView;\n',
     '', "", "", "由模块图守卫守：普通脚本用了模块里的名字却没挂回"),
    ("组件状态清单里混进一个不存在的状态", MACHINE,
     '  "disabled", "missing",\n',
     '  "disabled", "missing", "unknown",\n',
     MACHINE_TEST, "", ""),
    ("组件读状态清单少了「读不到」", MACHINE,
     'export const COMPONENT_PROBES = Object.freeze(["", "waiting", "timeout", "unreadable"]);\n',
     'export const COMPONENT_PROBES = Object.freeze(["", "waiting", "timeout"]);\n',
     MACHINE_TEST, "", ""),
    ("手机连接状态清单少了「已断开」", LINK,
     'export const PHONE_LINK_STATES = Object.freeze(["off", "waiting", "connected", "disconnected"]);\n',
     'export const PHONE_LINK_STATES = Object.freeze(["off", "waiting", "connected"]);\n',
     MACHINE_TEST, "", ""),
]

NOT_VISIBLE = ("SyntaxError", "ImportError", "ModuleNotFoundError", "IndentationError")


def copy_tree(work: Path) -> None:
    shutil.copytree(REPO / "local", work / "local",
                    ignore=shutil.ignore_patterns("data", "__pycache__", "*.pyc"))
    shutil.copytree(REPO / "tools" / "code_shape", work / "tools" / "code_shape",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def run_tests(work: Path, pattern: str, keyword: str) -> tuple[bool, str, str]:
    cmd = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", pattern]
    if keyword:
        cmd += ["-k", keyword]
    res = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=600)
    return res.returncode == 0, (res.stdout or "") + (res.stderr or ""), ""


def run_guard(work: Path) -> tuple[bool, str, str]:
    """模块图守卫：挂回漏了会让 unattached_module_names 不为空，这里把它当成红。

    返回（守卫是否干净、一句话说明、红在别的错误上的理由）。
    """
    res = subprocess.run(["node", "tools/code_shape/ui_modules.mjs"], cwd=str(work),
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=120)
    try:
        report = json.loads(res.stdout or "")
    except ValueError:
        return False, "", "守卫没给出报告：" + ((res.stderr or res.stdout or "")[:200])
    attached = report.get("unattached_module_names") or []
    unused = report.get("unused_legacy_globals") or []
    clean = res.returncode == 0 and attached == [] and unused == []
    return clean, "unattached_module_names = %s" % (attached,), ""


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mutate-link-"))
    try:
        copy_tree(work)
        for pattern in (LINK_TEST, MACHINE_TEST):
            ok, log, _ = run_tests(work, pattern, "")
            if not ok:
                print("原始副本就不绿（%s），先修测试：\n%s" % (pattern, log[-2000:]))
                return 1
        print("原始副本：两个用例文件全绿")
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
                if pattern:
                    ok, log, bad = run_tests(work, pattern, keyword)
                else:
                    ok, log, bad = run_guard(work)
            finally:
                path.write_bytes(raw.encode("utf-8"))
            if ok:
                survived.append((name, reason or "没有用例守住"))
                print("%2d. 存活：%s" % (index, name))
                continue
            if bad:
                survived.append((name, bad))
                print("%2d. 红错了地方：%s（%s）" % (index, name, bad))
                continue
            if pattern and any(mark in log for mark in NOT_VISIBLE):
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
