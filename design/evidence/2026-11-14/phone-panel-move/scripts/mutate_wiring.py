#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接线变异：把每一处事件绑定的「动作行」换成空语句，跑接线测试，记下变红的用例
与第一条失败断言。仓库本体永不改动：读写在 tempfile 下的仓库副本里进行，副本按
git ls-files 复制，config.json 与 local/data、server/data 下的文件不进副本。

行按「文件、函数、那一行的文字」定位（不按行号——面板要搬成模块，行号会变，
文字不会；验证码识别的下载与取消两处，设置页把「window.PhonePanel 在不在」的
判断挪进点击处理里之后那一行也变了，所以每行带搬之前/搬之后两份文字与文件，
用 --stage 选）。定位不到就整体停下报告，不猜。每条变异先 node --check 再跑
local/tests/test_ui_panel_wiring.py（只跑这一份），变红的用例里第一条失败断言
应当是那一处绑定自己那句（用户看得到的结果或发出的桥接请求）。

同一行绑两个控件的（通道卡两张、账号密码两个输入框、识别一节的导入入口两颗），
变异后两颗各自那句断言都红，先红的是先跑的那颗自己那句，表里照实记。

用法（仓库根执行，Python 一律带 -B）：
  --verify 只定位核对；--baseline 未变异基线；--stage 搬之前|搬之后（默认搬之前）；
  --ids 只跑指定编号；--out 写 markdown 结论表；--json 写机器可读结果。
不联网、不构建、不起真实窗口。

@author Author
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 每行一个 9 元组：
#   (编号, 控件与事件, 应有的结果, 文件·搬之前, 文件·搬之后, 函数,
#    该行去空白后的原文·搬之前, 该行去空白后的原文·搬之后, 组名)
# 换法只有一种：整行换成空语句「;」。
ROWS = [
    ("w-comp-install", "标题行「下载并安装」点击", "发出手机控制的组件下载请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (compInstall) compInstall.addEventListener("click", () => void PhonePanel.downloadComponent("phone_control"));',
     'if (compInstall) compInstall.addEventListener("click", () => void PhonePanel.downloadComponent("phone_control"));',
     "wire·组件下载"),
    ("w-comp-cancel", "标题行「取消下载」点击", "发出手机控制的取消下载请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (compCancel) compCancel.addEventListener("click", () => void PhonePanel.cancelComponent("phone_control"));',
     'if (compCancel) compCancel.addEventListener("click", () => void PhonePanel.cancelComponent("phone_control"));',
     "wire·组件下载"),
    ("w-feature", "标题行导入入口点击", "打开手机控制的导入弹窗，不直接安装",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (featureBtn) featureBtn.addEventListener("click", () => PhonePanel.featureAction());',
     'if (featureBtn) featureBtn.addEventListener("click", () => PhonePanel.featureAction());',
     "wire·导入弹窗"),
    ("w-import-phone", "「导入已下载的组件包」链接点击", "打开手机控制的导入弹窗",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (importPhone) importPhone.addEventListener("click", () => PhonePanel.openComponents("phone_control"));',
     'if (importPhone) importPhone.addEventListener("click", () => PhonePanel.openComponents("phone_control"));',
     "wire·导入弹窗"),
    ("w-pick-phone", "弹窗手机控制行「选择文件」点击", "发出选择文件请求，没选到给一句话",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (pickPhone) pickPhone.addEventListener("click", () => void PhonePanel.pickComponent("phone_control"));',
     'if (pickPhone) pickPhone.addEventListener("click", () => void PhonePanel.pickComponent("phone_control"));',
     "wire·导入弹窗"),
    ("w-pick-ocr", "弹窗验证码识别行「选择文件」点击", "发出选择文件请求，没选到给一句话",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (pickOcr) pickOcr.addEventListener("click", () => void PhonePanel.pickComponent("relogin_ocr"));',
     'if (pickOcr) pickOcr.addEventListener("click", () => void PhonePanel.pickComponent("relogin_ocr"));',
     "wire·导入弹窗"),
    ("w-install-phone", "弹窗手机控制行「安装这份」点击", "没自检通过时说先选文件，不发安装请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (installPhoneFile) installPhoneFile.addEventListener("click", () => void PhonePanel.installComponent("phone_control"));',
     'if (installPhoneFile) installPhoneFile.addEventListener("click", () => void PhonePanel.installComponent("phone_control"));',
     "wire·导入弹窗"),
    ("w-install-ocr", "弹窗验证码识别行「安装这份」点击", "没自检通过时说先选文件，不发安装请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (installOcrFile) installOcrFile.addEventListener("click", () => void PhonePanel.installComponent("relogin_ocr"));',
     'if (installOcrFile) installOcrFile.addEventListener("click", () => void PhonePanel.installComponent("relogin_ocr"));',
     "wire·导入弹窗"),
    ("w-close", "弹窗关闭按钮点击", "弹窗收起",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (closeComponents) closeComponents.addEventListener("click", () => PhonePanel.closeComponents());',
     'if (closeComponents) closeComponents.addEventListener("click", () => PhonePanel.closeComponents());',
     "wire·导入弹窗"),
    ("w-chan-tailscale", "通道卡 Tailscale change", "发出记偏好请求带通道名，卡变选中态",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));',
     'if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));',
     "wire·通道卡（同行两颗）"),
    ("w-chan-cloudflare", "通道卡 Cloudflare change", "发出记偏好请求带通道名，卡变选中态",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));',
     'if (radio) radio.addEventListener("change", () => void PhonePanel.changeChannel(key));',
     "wire·通道卡（同行两颗）"),
    ("w-start", "「开启手机访问」点击", "先说「启动中…」，随后发出开启请求（默认 Tailscale）",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (start) start.addEventListener("click", () => void PhonePanel.toggleStart());',
     'if (start) start.addEventListener("click", () => void PhonePanel.toggleStart());',
     "wire·手机访问开合"),
    ("w-stop", "「关闭手机访问」点击", "先展开确认行，不发请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (stop) stop.addEventListener("click", () => PhonePanel.askStop());',
     'if (stop) stop.addEventListener("click", () => PhonePanel.askStop());',
     "wire·手机访问开合"),
    ("w-stop-cancel", "确认行「先不关闭」点击", "收起确认行，不发请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (stopCancel) stopCancel.addEventListener("click", () => PhonePanel.cancelStop());',
     'if (stopCancel) stopCancel.addEventListener("click", () => PhonePanel.cancelStop());',
     "wire·手机访问开合"),
    ("w-stop-confirm", "确认行「确认关闭」点击", "发出关闭请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (stopConfirm) stopConfirm.addEventListener("click", () => void PhonePanel.confirmStop());',
     'if (stopConfirm) stopConfirm.addEventListener("click", () => void PhonePanel.confirmStop());',
     "wire·手机访问开合"),
    ("w-add-pair", "「再配对一台手机」点击", "重新展开配对区",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (addPair) addPair.addEventListener("click", () => PhonePanel.addPairing());',
     'if (addPair) addPair.addEventListener("click", () => PhonePanel.addPairing());',
     "wire·手机访问开合"),
    ("w-recheck", "「重新检测」点击", "重取快照，连上了就地说结果",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (recheck) recheck.addEventListener("click", () => void PhonePanel.recheckTailscale());',
     'if (recheck) recheck.addEventListener("click", () => void PhonePanel.recheckTailscale());',
     "wire·手机访问开合"),
    ("w-copy", "「复制」点击", "复制成功后按钮说「已复制」",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (copy) copy.addEventListener("click", () => void PhonePanel.copyAddress());',
     'if (copy) copy.addEventListener("click", () => void PhonePanel.copyAddress());',
     "wire·手机访问开合"),
    ("w-open-loc", "「打开所在文件夹」点击", "发出打开目录请求带组件名",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (openLoc) openLoc.addEventListener("click", () => void PhonePanel.openComponentDir());',
     'if (openLoc) openLoc.addEventListener("click", () => void PhonePanel.openComponentDir());',
     "wire·组件位置"),
    ("w-cred-go", "「去保存」点击", "展开账号表单并聚焦账号框",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (credGo) credGo.addEventListener("click", () => PhonePanel.goSaveCredentials());',
     'if (credGo) credGo.addEventListener("click", () => PhonePanel.goSaveCredentials());',
     "wire·登录恢复"),
    ("w-manage", "「填写账号密码/更换」点击", "展开账号表单",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (manage) manage.addEventListener("click", () => PhonePanel.openCredForm());',
     'if (manage) manage.addEventListener("click", () => PhonePanel.openCredForm());',
     "wire·登录恢复"),
    ("w-cred-cancel", "表单「取消」点击", "收起表单",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (credCancel) credCancel.addEventListener("click", () => PhonePanel.cancelCredForm());',
     'if (credCancel) credCancel.addEventListener("click", () => PhonePanel.cancelCredForm());',
     "wire·登录恢复"),
    ("w-cred-user", "账号框 input", "输入齐全后保存按钮可点",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());',
     'if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());',
     "wire·登录恢复（同行两框）"),
    ("w-cred-pass", "密码框 input", "输入齐全后保存按钮可点",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());',
     'if (field) field.addEventListener("input", () => PhonePanel.paintCredForm());',
     "wire·登录恢复（同行两框）"),
    ("w-once", "「只在这次运行中用」change", "保存按钮改名「只用这一次」",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (onceBox) onceBox.addEventListener("change", () => PhonePanel.paintCredForm());',
     'if (onceBox) onceBox.addEventListener("change", () => PhonePanel.paintCredForm());',
     "wire·登录恢复"),
    ("w-save", "保存按钮点击", "勾选时发暂存请求，收起表单并就地说一句",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (save) save.addEventListener("click", () => void PhonePanel.saveCredentials());',
     'if (save) save.addEventListener("click", () => void PhonePanel.saveCredentials());',
     "wire·登录恢复"),
    ("w-clear", "「清除已保存」点击", "先展开确认行，不发请求",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (clear) clear.addEventListener("click", () => PhonePanel.askClearCredentials());',
     'if (clear) clear.addEventListener("click", () => PhonePanel.askClearCredentials());',
     "wire·登录恢复"),
    ("w-clear-cancel", "清除确认行「先不清除」点击", "收起确认行",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (clearCancel) clearCancel.addEventListener("click", () => PhonePanel.cancelClearCredentials());',
     'if (clearCancel) clearCancel.addEventListener("click", () => PhonePanel.cancelClearCredentials());',
     "wire·登录恢复"),
    ("w-clear-confirm", "清除确认行「确认清除」点击", "发出清除请求并就地说结果",
     "views/phone.js", "features/phone-access/actions-panel.js", "wire",
     'if (clearConfirm) clearConfirm.addEventListener("click", () => void PhonePanel.confirmClearCredentials());',
     'if (clearConfirm) clearConfirm.addEventListener("click", () => void PhonePanel.confirmClearCredentials());',
     "wire·登录恢复"),
    ("s-ocr-download", "识别一节「下载并安装」点击", "发出验证码识别的下载请求",
     "views/settings.js", "views/settings.js", "wireSettings",
     'ocrDownload.addEventListener("click", () => void window.PhonePanel.downloadComponent("relogin_ocr"));',
     'if (window.PhonePanel) void window.PhonePanel.downloadComponent("relogin_ocr");',
     "wireSettings·验证码识别"),
    ("s-ocr-cancel", "识别一节「取消下载」点击", "发出验证码识别的取消下载请求",
     "views/settings.js", "views/settings.js", "wireSettings",
     'ocrCancel.addEventListener("click", () => void window.PhonePanel.cancelComponent("relogin_ocr"));',
     'if (window.PhonePanel) void window.PhonePanel.cancelComponent("relogin_ocr");',
     "wireSettings·验证码识别"),
    ("s-ocr-enable", "识别一节「启用」点击", "发出启用请求并就地说结果",
     "views/settings.js", "views/settings.js", "wireSettings",
     'if (ocrEnable) ocrEnable.addEventListener("click", () => void enableOcr());',
     'if (ocrEnable) ocrEnable.addEventListener("click", () => void enableOcr());',
     "wireSettings·验证码识别"),
    ("s-ocr-import", "识别一节「导入已下载的组件包」点击", "打开验证码识别的导入弹窗",
     "views/settings.js", "views/settings.js", "wireSettings",
     'if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");',
     'if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");',
     "wireSettings·验证码识别（同行两颗）"),
    ("s-ocr-reimport", "识别一节标题行「重新导入组件包」点击", "打开验证码识别的导入弹窗",
     "views/settings.js", "views/settings.js", "wireSettings",
     'if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");',
     'if (window.PhonePanel) window.PhonePanel.openComponents("relogin_ocr");',
     "wireSettings·验证码识别（同行两颗）"),
    ("s-ocr-open-loc", "识别一节「打开所在文件夹」点击", "发出打开目录请求带组件名",
     "views/settings.js", "views/settings.js", "wireSettings",
     'if (ocrOpenLoc) ocrOpenLoc.addEventListener("click", () => void openOcrDir());',
     'if (ocrOpenLoc) ocrOpenLoc.addEventListener("click", () => void openOcrDir());',
     "wireSettings·验证码识别"),
]

WIRING_TEST = "test_ui_panel_wiring.py"
TEST_TIMEOUT_S = 600
_DEF_RE = r"^\s*(?:async\s+)?(?:function\s+)?%s\s*\([^)]*\)\s*\{"
_CODE_LINE_RE = re.compile(
    r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`|//[^\n]*|/\*.*?\*/', re.S)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def copy_repo(repo: Path, dest: Path) -> int:
    """按 git ls-files（已跟踪 + 未跟踪未忽略）复制；config.json 与两个 data 目录不进副本。"""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                         cwd=repo, capture_output=True, check=True)
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    count = 0
    for rel in names:
        if "config.json" in rel or rel.startswith(("local/data/", "server/data/")):
            continue
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            count += 1
    return count


def _strip_strings_and_comments(line: str) -> str:
    return _CODE_LINE_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), line)


def locate_function(text: str, name: str) -> tuple[int, int]:
    """函数名 -> (起始行号, 结束行号)，闭区间、1 起始。找不到或括号不闭合就报错。"""
    lines = text.splitlines()
    pat = re.compile(_DEF_RE % re.escape(name), re.M)
    start = None
    open_line = None
    depth = 0
    for idx, line in enumerate(lines):
        if start is None:
            m = pat.match(line)
            if m:
                start = open_line = idx
                stripped = _strip_strings_and_comments(line)
                depth = stripped.count("{") - stripped.count("}")
                if depth <= 0 and "{" in stripped:
                    return (idx + 1, idx + 1)
                if depth > 0:
                    continue
                continue
        else:
            stripped = _strip_strings_and_comments(line)
            depth += stripped.count("{") - stripped.count("}")
            if depth <= 0:
                return (open_line + 1, idx + 1)
    raise SystemExit("定位不到函数 %r（或括号不闭合），停下报告" % name)


def locate_row(root: Path, row, stage_file: str, stage_text: str) -> tuple[Path, int]:
    """按「文件、函数、那一行的文字」定位，返回（文件路径, 行下标 0 起始）。定位不到就停下。"""
    func = row[5]
    path = root / "local" / "ui" / stage_file
    text = path.read_text(encoding="utf-8")
    start, end = locate_function(text, func)
    lines = text.splitlines()
    hits = [i for i in range(start - 1, end)
            if i < len(lines) and lines[i].strip() == stage_text]
    if len(hits) != 1:
        got = "；".join(lines[i].strip() for i in hits[:3]) or "<没有这一行>"
        raise SystemExit("定位不到唯一一行：函数 %s（第 %d–%d 行）里与 %r 逐字相等的行有 %d 处（%s），停下报告"
                         % (func, start, end, stage_text, len(hits), got))
    return path, hits[0]


def node_check(path: Path) -> bool:
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node，无法做语法检查")
    return subprocess.run([node, "--check", str(path)], capture_output=True,
                          text=True).returncode == 0


def first_failure_detail(text: str, first_red_id: str) -> dict:
    """第一个变红用例的第一条失败断言：断言源码行与 AssertionError 原文。"""
    pat = re.compile(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", re.M)
    for m in pat.finditer(text):
        if first_red_id not in (m.group(1), m.group(2)):
            continue
        rest = text[m.end():]
        nxt = pat.search(rest)
        lines = (rest[:nxt.start()] if nxt else rest).splitlines()
        assert_src = ""
        assert_msg = ""
        for i, line in enumerate(lines):
            if "AssertionError" in line or ("Error" in line and ":" in line
                                            and re.match(r"^\w+(Error|Exception)", line.strip())):
                assert_msg = line.strip()
                for back in range(i - 1, max(i - 5, -1), -1):
                    cand = lines[back].strip()
                    if cand.startswith(("self.assert", "assert ")):
                        assert_src = cand
                        break
                break
        return {"test": first_red_id, "assert_src": assert_src, "assert_msg": assert_msg}
    return {"test": first_red_id, "assert_src": "", "assert_msg": ""}


def run_wiring_tests(copy_root: Path) -> dict:
    """只跑接线测试文件，返回 {total, failures, errors, ok, red, first_fail}。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-B", "-m", "unittest", "discover",
           "-s", "local/tests", "-p", WIRING_TEST, "-v"]
    res = subprocess.run(cmd, cwd=copy_root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=TEST_TIMEOUT_S, env=env)
    text = (res.stdout or "") + "\n" + (res.stderr or "")
    m = re.search(r"^Ran (\d+) tests? in", text, re.M)
    total = int(m.group(1)) if m else 0
    red = []
    for line in text.splitlines():
        mm = re.match(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", line)
        if mm:
            red.append(mm.group(2) or mm.group(1))
    first = first_failure_detail(text, red[0]) if red else None
    sm = re.search(r"^FAILED \((.*)\)\s*$", text, re.M)
    stat = dict.fromkeys(("failures", "errors", "skipped"), 0)
    for key, val in (re.findall(r"(failures|errors|skipped)=(\d+)", sm.group(1)) if sm else []):
        stat[key] = int(val)
    return {"total": total, "ok": res.returncode == 0, "red": sorted(set(red)),
            "first_fail": first, **stat}


def conclusions_for(rows, copy_root: Path, stage: str) -> list:
    results = []
    originals: dict = {}
    located: dict = {}
    for row in rows:
        stage_file = row[3] if stage == "搬之前" else row[4]
        stage_text = row[6] if stage == "搬之前" else row[7]
        path, idx = locate_row(copy_root, row, stage_file, stage_text)
        located[row[0]] = (path, idx)
        originals.setdefault(str(path), path.read_text(encoding="utf-8"))
    for row in rows:
        rid = row[0]
        stage_file = row[3] if stage == "搬之前" else row[4]
        path, idx = located[rid]
        original = originals[str(path)]
        lines = original.splitlines(keepends=True)
        mutated = list(lines)
        mutated[idx] = ";" + lines[idx][len(lines[idx].rstrip("\r\n")):]
        path.write_text("".join(mutated), encoding="utf-8")
        syntax_ok = node_check(path)
        if not syntax_ok:
            path.write_text(original, encoding="utf-8")
            results.append({"id": rid, "desc": row[1], "expect": row[2], "group": row[8],
                            "where": "%s %s" % (stage_file, row[5]), "conclusion": "运行异常",
                            "red": [], "first_fail": None})
            log("[%s] 变异后语法不过，记运行异常" % rid)
            continue
        run = run_wiring_tests(copy_root)
        conclusion = "没人守" if not run["red"] else "红在绑定自己的断言"
        ff = run["first_fail"] or {}
        results.append({"id": rid, "desc": row[1], "expect": row[2], "group": row[8],
                        "where": "%s %s" % (stage_file, row[5]), "conclusion": conclusion,
                        "red": run["red"], "first_fail": ff, "total": run["total"],
                        "failures": run["failures"], "errors": run["errors"]})
        log("[%s] %s 红=%d 先红=%s 断言=%s" %
            (rid, conclusion, len(run["red"]), ff.get("test", ""), ff.get("assert_msg", "")))
        path.write_text(original, encoding="utf-8")
    return results


def write_markdown(out_path: Path, results, stage: str, total_rows: int) -> None:
    counts: dict = {}
    for item in results:
        counts[item["conclusion"]] = counts.get(item["conclusion"], 0) + 1
    lines = [
        "# 接线变异结论（%s）" % stage,
        "",
        "- 变异做法：把那一处绑定的动作行整行换成空语句「;」（定位按「文件、函数、那一行的文字」，"
        "清单在 scripts/mutate_wiring.py），只在临时目录下的仓库副本里做，仓库本体不动；每条变异"
        "先 node --check，再跑 local/tests/test_ui_panel_wiring.py（只跑这一份）。",
        "- 结论口径：变红且第一条失败断言是那一处绑定自己那句（用户看得到的结果或发出的桥接请求）"
        "即「红在绑定自己的断言」；没有用例变红即「没人守」。同一行绑两个控件的（通道卡两张、"
        "账号密码两个输入框、识别一节的导入入口两颗），变异后两颗各自那句都红，表里记先红的那颗。",
        "",
        "| 编号 | 控件与事件 | 应有的结果 | 变异位置 | 结论 | 变红的用例（最多三条） | 先红用例的第一条失败断言 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in results:
        reds = item["red"][:3] if item["red"] else ["（无）"]
        ff = item.get("first_fail") or {}
        src = ff.get("assert_src", "")
        detail = ("`%s` → %s" % (src, ff.get("assert_msg", ""))) if src else (
            ff.get("assert_msg", "") or "（无）")
        lines.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            item["id"], item["desc"], item["expect"], item["where"],
            item["conclusion"], "、".join(reds), detail))
    lines.append("")
    summary = "、".join("%s %d" % (k, counts[k]) for k in sorted(counts))
    lines.append("汇总：%s（本节 %d 行；表共 %d 处绑定）" % (summary, len(results), total_rows))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_rows(repo: Path, rows, stage: str) -> None:
    for row in rows:
        stage_file = row[3] if stage == "搬之前" else row[4]
        stage_text = row[6] if stage == "搬之前" else row[7]
        path, idx = locate_row(repo, row, stage_file, stage_text)
        line = path.read_text(encoding="utf-8").splitlines()[idx]
        log("定位 %s（%s）→ %s:%d %s" % (row[0], stage, row[3] if stage == "搬之前" else row[4],
                                        idx + 1, line.strip()))


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(here.parents[5]))
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--stage", default="搬之前", choices=["搬之前", "搬之后"])
    ap.add_argument("--out", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    rows = ROWS
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        rows = [r for r in ROWS if r[0] in wanted]
        if len(rows) != len(wanted):
            raise SystemExit("编号对不上表，停下报告：缺 %s"
                             % sorted(wanted - {r[0] for r in rows}))
    if args.shards > 1:
        rows = [r for i, r in enumerate(ROWS) if i % args.shards == args.shard]
    if args.verify:
        verify_rows(repo, rows, args.stage)
        return
    copy_root = Path(tempfile.mkdtemp(prefix="wire-mut-"))
    log("副本已建：%d 个文件" % copy_repo(repo, copy_root))
    if args.baseline:
        run = run_wiring_tests(copy_root)
        log("基线：%d 例，失败 %d，报错 %d，ok=%s" % (run["total"], run["failures"],
                                                  run["errors"], run["ok"]))
        print(json.dumps({k: v for k, v in run.items() if k != "first_fail"},
                         ensure_ascii=False))
        shutil.rmtree(copy_root, ignore_errors=True)
        return
    verify_rows(repo, rows, args.stage)
    results = conclusions_for(rows, copy_root, args.stage)
    if args.out:
        write_markdown(Path(args.out), results, args.stage, len(ROWS))
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    log("完成 %d 条" % len(results))
    shutil.rmtree(copy_root, ignore_errors=True)


if __name__ == "__main__":
    main()
