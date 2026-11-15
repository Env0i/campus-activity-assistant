#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本批转移的变异测试：一处一处把新加的判断改坏，看是不是有用户看得到的东西变红。

每条变异都只改一处源码（在临时副本里改，仓库本身不动），然后跑与它对应的用例：
改坏之后必须有断言失败，且失败要落在「按钮在不在、文字是哪句」这类用户看得到的结果上。
不红的变异要么是真的等价（写理由），要么说明这一档没有被守住（那就补用例，不许放过）。

用法（仓库根）：
    python -B design/evidence/2026-11-15/component-transitions/scripts/mutate_transitions.py

@author Author
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# name, path, 原文, 改坏, 用哪个用例文件, 可选 -k 片段, 等价理由
MUTATIONS = [
    ("在下载中也不放过读状态", "local/ui/features/components/state-machine.js",
     '  if (downloading) probe = "";\n',
     '  if (downloading) probe = "waiting";\n',
     "test_component_machine.py", "", ""),
    ("等锁排在超时之后（有缓存就被等锁吃掉）", "local/ui/features/components/state-machine.js",
     '  else if (overWait) probe = "timeout";\n'
     '  else if (source.busy || String(source.status || "") === "checking") probe = "waiting";\n',
     '  else if (source.busy || String(source.status || "") === "checking") probe = "waiting";\n'
     '  else if (overWait) probe = "timeout";\n',
     "test_component_transitions.py", "", ""),
    ("没有重试起点时不算超时", "local/ui/features/components/state-machine.js",
     "    && (!hasBase || waited - Number(env.retryWaitBase) >= PROBE_TIMEOUT_S);\n",
     "    && (waited - Number(env.retryWaitBase) >= PROBE_TIMEOUT_S);\n",
     "test_component_transitions.py", "", ""),
    ("超时窗口从 30 秒缩短成 20 秒", "local/ui/features/components/state-machine.js",
     "const PROBE_TIMEOUT_S = 30;\n",
     "const PROBE_TIMEOUT_S = 20;\n",
     "test_component_transitions.py", "", ""),
    ("手机行开着时不再强制按装好画", "local/ui/features/components/state-machine.js",
     '  if (env.running) state = "enabled";\n',
     '  if (env.running) state = state || "enabled";\n',
     "test_component_machine.py", "", ""),
    ("loading 又把检查中算成加载", "local/ui/features/components/state-machine.js",
     "    loading: downloading || installing,\n",
     '    loading: downloading || installing || state === "checking",\n',
     "test_component_transitions.py", "", ""),
    ("读不到这一档不算了", "local/ui/features/components/state-machine.js",
     '  else if (source.read_error) probe = "unreadable";\n',
     '  else if (false) probe = "unreadable";\n',
     "test_component_transitions.py", "", ""),
    ("没结论时还把主按钮摆出来", "local/ui/features/components/view-row.js",
     "      || !!probe;\n",
     "      || false;\n",
     "test_component_transitions.py", "", ""),
    ("需要更新时说成下载并安装", "local/ui/features/components/view-row.js",
     "  if (state === \"outdated\") return INSTALL_TEXT_OUTDATED;\n",
     "  if (state === \"outdated\") return INSTALL_TEXT_DEFAULT;\n",
     "test_phone_ui.py", "test_outdated_shows_update_button_instead_of_broken", ""),
    ("坏了时主按钮不说重新安装", "local/ui/features/components/view-row.js",
     '  if (state === "broken") return INSTALL_TEXT_BROKEN;\n',
     '  if (state === "broken") return INSTALL_TEXT_DEFAULT;\n',
     "test_component_transitions.py", "", ""),
    ("下载失败过也还说下载并安装", "local/ui/features/components/view-row.js",
     "  return failed ? INSTALL_TEXT_FAILED : INSTALL_TEXT_DEFAULT;\n",
     "  return INSTALL_TEXT_DEFAULT;\n",
     "test_component_transitions.py", "", ""),
    ("坏了时不给导入兜底", "local/ui/features/components/view-row.js",
     '  rowShow(spec.importLineId, (state === "missing" || state === "outdated" || state === "broken")\n',
     '  rowShow(spec.importLineId, (state === "missing" || state === "outdated")\n',
     "test_component_transitions.py", "", ""),
    ("读不到时说成正在确认", "local/ui/features/components/view-row.js",
     '  if (probe === "unreadable") return PROBE_TEXT_UNREADABLE;\n',
     '  if (probe === "unreadable") return PROBE_TEXT_CHECKING;\n',
     "test_component_transitions.py", "", ""),
    ("超时那句说成正在确认", "local/ui/features/components/view-row.js",
     '  if (probe === "timeout") return PROBE_TEXT_TIMEOUT;\n',
     '  if (probe === "timeout") return PROBE_TEXT_CHECKING;\n',
     "test_component_transitions.py", "", ""),
    ("有缓存也多说一句正在确认", "local/ui/features/components/view-row.js",
     '  if (probe === "waiting" && state === "checking") return PROBE_TEXT_CHECKING;\n',
     '  if (probe === "waiting") return PROBE_TEXT_CHECKING;\n',
     "test_component_transitions.py", "", ""),
    ("说明行不带读状态标记", "local/ui/features/components/view-row.js",
     "  if (note) note.dataset.probe = probe;\n",
     '  if (note) note.dataset.probe = "";\n',
     "test_component_transitions.py", "", ""),
    ("等锁时也给「重试」", "local/ui/features/components/view-row.js",
     '  const retry = rowShow(spec.retryId, probe === "timeout" || probe === "unreadable");\n',
     "  const retry = rowShow(spec.retryId, !!probe);\n",
     "test_component_transitions.py", "", ""),
    ("面板忙时「重试」还能点", "local/ui/features/components/view-row.js",
     "    retry.disabled = facts.busy;\n",
     "    retry.disabled = false;\n",
     "test_component_transitions.py", "", ""),
    ("手机行坏了不写那句说明", "local/ui/features/phone-access/view.js",
     ': (phase === "broken" ? BROKEN_NOTE : ""))) : "";\n',
     ': (phase === "broken" ? "组件有问题" : ""))) : "";\n',
     "test_component_transitions.py", "", ""),
    ("手机行坏了还给标题行那个入口", "local/ui/features/phone-access/view.js",
     "      featureBtn.hidden = !featureAction || !!facts.probe;\n",
     "      featureBtn.hidden = false;\n",
     "test_component_transitions.py", "", ""),
    ("手机行不把重试起点交下去", "local/ui/features/phone-access/view.js",
     '      running: !!st.running, retryWaitBase: retryWaitBase("phone_control"),\n',
     "      running: !!st.running, retryWaitBase: null,\n",
     "test_component_transitions.py", "", ""),
    ("识别行坏了不写那句说明", "local/ui/features/components/view-ocr.js",
     '  const brokenText = phase === "broken" && !installing ? BROKEN_NOTE : "";\n',
     '  const brokenText = "";\n',
     "test_component_transitions.py", "", ""),
    ("识别行又把取消句写回去", "local/ui/features/components/view-ocr.js",
     '  ocrText("#ocr-note", OcrPanel.note);\n',
     '  ocrText("#ocr-note", OcrPanel.note || "下载已取消，没有装任何东西。");\n',
     "test_component_transitions.py", "", ""),
    ("点「重试」不记这一刻的等锁秒数", "local/ui/features/components/actions.js",
     "  setRetryWaitBase(feature, PhonePanel.feature(feature).lock_wait_s);\n",
     "  setRetryWaitBase(feature, null);\n",
     "test_component_transitions.py", "", ""),
    ("手机行「重试」没接上", "local/ui/features/components/actions.js",
     '    phoneRetry.addEventListener("click", () => retryComponent("phone_control"));\n',
     "    void phoneRetry;\n",
     "test_component_transitions.py", "", ""),
    ("识别行「重试」没接上", "local/ui/features/components/actions.js",
     '    ocrRetry.addEventListener("click", () => retryComponent("relogin_ocr"));\n',
     "    void ocrRetry;\n",
     "test_component_transitions.py", "", ""),
    ("等锁时不再自动再取快照", "local/ui/features/phone-access/state.js",
     "    return !!PhonePanel.state.running || PhonePanel.downloadActive() || probing();\n",
     "    return !!PhonePanel.state.running || PhonePanel.downloadActive();\n",
     "test_component_transitions.py", "", ""),
    ("新快照到了不清重试起点", "local/ui/features/phone-access/actions.js",
     "    clearSettledRetryBase();\n",
     "    void clearSettledRetryBase;\n",
     "test_component_transitions.py", "", ""),
    ("面板启动时不接「重试」", "local/ui/features/phone-access/actions-panel.js",
     "  wireComponentRetries();\n",
     "  void wireComponentRetries;\n",
     "test_component_transitions.py", "", ""),
]

# 这些失败说明改坏的是语法或导入，不是用户看得到的结果
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
                         encoding="utf-8", errors="replace", timeout=600)
    return res.returncode == 0, (res.stdout or "") + (res.stderr or "")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mutate-transitions-"))
    try:
        copy_tree(work)
        ok, log = run_tests(work, "test_component_transitions.py", "")
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
