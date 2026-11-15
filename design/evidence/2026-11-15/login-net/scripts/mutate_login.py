# -*- coding: utf-8 -*-
"""登录块的变异量具：在仓库副本里逐行改一处，再跑登录相关的界面测试，看有没有用例变红。

定位口径是「文件 + 函数 + 那一行的文字」，不按行号：下一批要把这些文件搬成模块，行号会变，文字不会。
同一段文字在同一个函数里出现两次时，用 nth 指定第几处（从 1 数）。

两种改法：
- 认结论/认步骤（表甲）：把分支条件换成 false，让输入落到别的分支；兜底返回的字面量换成另一种写法。
- 读进行中标志（表乙）：把那一处读换成常量（或删掉那一小段条件），赋值不动。

副本从 git 的清单复制，不带 local/data、任何 config.json、local/bin 下的大文件。
所有写入都落在 tempfile.mkdtemp() 里，仓库本身一个字节都不改。

用法（从仓库根执行）：
  python -B design/evidence/<日期>/login-net/scripts/mutate_login.py --verify
  python -B design/evidence/<日期>/login-net/scripts/mutate_login.py --baseline
  python -B design/evidence/<日期>/login-net/scripts/mutate_login.py --ids J02,Y31
  python -B design/evidence/<日期>/login-net/scripts/mutate_login.py --shard-index 0 --shard-count 6 --out 结果目录/shard-0.json

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
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# 登录相关的界面测试全集：直接断言这三个文件的行为或文字的测试，加两个新文件。
TEST_FILES = [
    "test_ui_contract_login.py",
    "test_ui_exit_paths_login.py",
    "test_ui_reliability.py",
    "test_ui_contract_feedback.py",
    "test_ui_contract_plan.py",
    "test_ui_contract_settings.py",
    "test_ui_contract_shell.py",
    "test_prerefactor_fixes.py",
    "test_ui_login_capsule.py",
    "test_ui_relogin_dialog.py",
]

SKIP_COPY = (
    "local/data/",
    "server/data/",
    "local/config.json",
    "server/config.json",
    "local/_site_build.py",
    "local/bin/",
)

# 行：(id, 表, 文件, 函数, 定位串, 替换成, 第几处, 复用谁的结论, 这一行管什么)
ROWS = [
    # ---------------- 登录胶囊：认结论（views/login.js paintLogin）
    ("J01", "甲", "local/ui/views/login.js", "paintLogin",
     'const busyExpired = S.login.result === "expired" && S.login.present !== false;',
     'const busyExpired = false;', 1, None, "计划运行中仍要报失效的那条前提"),
    ("J02", "甲", "local/ui/views/login.js", "paintLogin",
     'if (S.busy && !S.login.loginPending && !busyExpired && !S.autoLogin) {',
     'if (false) {', 1, None, "忙碌时胶囊要说「已登录」而不是正在处理"),
    ("J03", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.demo) {', '} else if (false) {', 1, None, "演示模式自己说出来"),
    ("J04", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.autoLogin) {', '} else if (false) {', 1, None, "自动登录中…"),
    ("J05", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.login.loginPending) {', '} else if (false) {', 1, None, "登录中…（登录窗口还在等）"),
    ("J06", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.login.checking || (ok === null && S.login.present === true)) {',
     '} else if (false) {', 1, None, "检查登录…，本机有会话也不提前宣布已登录"),
    ("J07", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.login.present === false) {', '} else if (false) {', 1, None, "从没登录过：引导首次登录"),
    ("J08", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (S.login.result === "unknown" && ok === false) {', '} else if (false) {', 1, None, "登录待确认（网络原因）"),
    ("J09", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (ok === false && S.login.present !== false) {', '} else if (false) {', 1, None, "登录已失效"),
    ("J10", "甲", "local/ui/views/login.js", "paintLogin",
     '} else if (ok === true) {', '} else if (false) {', 1, None, "已登录"),
    ("J11", "甲", "local/ui/views/login.js", "paintLogin",
     'let text = "未登录";', 'let text = "已登录";', 1, None, "兜底的胶囊文字"),
    ("J12", "甲", "local/ui/views/login.js", "paintLogin",
     'if (termsLocked() && !S.demo && state !== "pending") {', 'if (false) {', 1, None, "等同意条款"),
    ("J13", "甲", "local/ui/views/login.js", "paintLogin",
     'state === "bad" || state === "warn" || state === "ok" ? "重新登录" : "登录"',
     'false ? "重新登录" : "登录"', 1, None, "登录按钮叫「重新登录」还是「登录」"),
    ("J14", "甲", "local/ui/views/login.js", "paintLogin",
     'const solid = state === "none" || state === "bad";', 'const solid = false;', 1, None,
     "登录按钮转实心还是描边"),

    # ---------------- 登录状态：认结论（state/login.js）
    ("J15", "甲", "local/ui/state/login.js", "reconcileAutoLogin",
     'if (!S.autoLogin) return;', 'if (false) return;', 1, None, "自动登录态收回的入口"),
    ("J16", "甲", "local/ui/state/login.js", "reconcileAutoLogin",
     'if (S.login.handoff || S.login.result === "valid") {', 'if (false) {', 1, None,
     "已转人工/学校确认有效时收回自动登录"),
    ("J17", "甲", "local/ui/state/login.js", "reconcileAutoLogin",
     'if (S.login.result === "expired") return;', 'if (false) return;', 1, None,
     "失效时留给 recovering 与中继事件"),
    ("J18", "甲", "local/ui/state/login.js", "reconcileAutoLogin",
     'if (typeof reloginAutoLive !== "function" || !reloginAutoLive())', 'if (false)', 1, None,
     "中继里没有这一场时收回自动登录"),
    ("J19", "甲", "local/ui/state/login.js", "setLogin",
     'if (S.login.result === "expired" && !S.login.handoff)',
     'if (false)', 1, None, "check 回来说失效且没转人工，才点亮自动登录中"),
    ("J20", "甲", "local/ui/state/login.js", "setLogin",
     'if (S.login.result === "valid") S.login.handoff = false;',
     'if (false) S.login.handoff = false;', 1, None, "结论为有效时清掉已转人工"),
    ("J21", "甲", "local/ui/state/login.js", "expiryText",
     'return at ? "约到 " + whenText(at) : "未知（以学校校验为准）";',
     'return "未知（以学校校验为准）";', 1, None, "预计有效的长句"),
    ("J22", "甲", "local/ui/state/login.js", "loginEstimateShort",
     'if (!at) return "";', 'if (false) return "";', 1, None, "没有锚点时不编预计时间"),
    ("J23", "甲", "local/ui/state/login.js", "loginEstimateShort",
     'if (now === null) return "约到 "', 'if (false) return "约到 "', 1, None,
     "未校准时写具体日期"),
    ("J24", "甲", "local/ui/state/login.js", "loginEstimateShort",
     'if (diff === 0) return "约到 " + time;', 'if (false) return "约到 " + time;', 1, None,
     "当天写「约到 时刻」"),
    ("J25", "甲", "local/ui/state/login.js", "loginEstimateShort",
     'if (diff === 1) return "约到明天 " + time;', 'if (false) return "约到明天 " + time;', 1, None,
     "明天写「约到明天 时刻」"),

    # ---------------- 重新登录对话框：认情况/认步骤（views/relogin.js）
    ("J26", "甲", "local/ui/views/relogin.js", "reloginCase",
     'if (cred.saved && cred.paused) return "bad";', 'if (false) return "bad";', 1, None,
     "保存的密码不对这一步"),
    ("J27", "甲", "local/ui/views/relogin.js", "reloginCase",
     'if (cred.saved) return "captcha";', 'if (false) return "captcha";', 1, None,
     "有保存账号直接进验证码步"),
    ("J28", "甲", "local/ui/views/relogin.js", "reloginCase",
     'return "login";', 'return "bad";', 1, None, "没账号时落登录表单"),
    ("J29", "甲", "local/ui/views/relogin.js", "reloginCapSub",
     'return mask ? "账号 " + mask + " 和密码由电脑自动填写" : "账号和密码由电脑自动填写";',
     'return "账号和密码由电脑自动填写";', 1, None, "验证码步副句带不带打码账号"),
    ("J30", "甲", "local/ui/views/relogin.js", "reloginFromLogin",
     'return !!(S.relogin && S.relogin.fromLogin);', 'return false;', 1, None,
     "这一场是不是从登录表单点进来的"),
    ("J31", "甲", "local/ui/views/relogin.js", "reloginHead",
     'if (step === "confirm") {', 'if (false) {', 1, None, "确认步的标题与副句"),
    ("J32", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (step === "login") {', '} else if (false) {', 1, None, "登录表单步的标题与副句"),
    ("J33", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (step === "bad") {', '} else if (false) {', 1, None, "密码不对步的标题与正文"),
    ("J34", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (step === "lgwait") {', '} else if (false) {', 1, None, "在学校登录页等待的标题"),
    ("J35", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (step === "cap") {', '} else if (false) {', 1, None, "验证码步的标题与副句"),
    ("J36", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (step === "wait") {', '} else if (false) {', 1, None, "等待步的标题与副句"),
    ("J37", "甲", "local/ui/views/relogin.js", "reloginHead",
     'if (/核对验证码/.test(busy)) {', 'if (false) {', 1, None, "核对验证码时标题仍是输入验证码"),
    ("J38", "甲", "local/ui/views/relogin.js", "reloginHead",
     '} else if (/自动/.test(busy)) {', '} else if (false) {', 1, None, "自动登录时标题是「正在自动登录」"),
    ("J39", "甲", "local/ui/views/relogin.js", "reloginHead",
     'title = "输入验证码";\n    sub = reloginFromLogin() && mask',
     'title = "输入验证码";\n    sub = false && mask', 1, None, "从登录表单进来时副句说密码已填好"),
    ("J40", "甲", "local/ui/views/relogin.js", "reloginActs",
     'if (step === "login") return RELOGIN_LOGIN_ACTS[reloginWay()] || RELOGIN_LOGIN_ACTS.here;',
     'if (false) return RELOGIN_LOGIN_ACTS[reloginWay()] || RELOGIN_LOGIN_ACTS.here;', 1, None,
     "登录步底栏按钮跟登录方式走"),
    ("J41", "甲", "local/ui/views/relogin.js", "reloginActs",
     'if (step === "cap" && reloginFromLogin()) return ["btn-lg-back", "btn-rl-cancel", "btn-rl-code"];',
     'if (false) return ["btn-lg-back", "btn-rl-cancel", "btn-rl-code"];', 1, None,
     "从登录表单进来的验证码步第一个按钮是「上一步」"),
    ("J42", "甲", "local/ui/views/relogin.js", "reloginActs",
     'return RELOGIN_ACTS[step] || [];', 'return [];', 1, None, "其余步骤的按钮表"),
    ("J43", "甲", "local/ui/views/relogin.js", "reloginWay",
     'return S.relogin && S.relogin.way === "browser" ? "browser" : "here";',
     'return "here";', 1, None, "登录方式默认听 S.relogin.way"),
    ("J44", "甲", "local/ui/views/relogin.js", "reloginStep",
     'if (box) box.hidden = name !== step;', 'if (box) box.hidden = false;', 1, None,
     "只显示当前步骤的块"),
    ("J45", "甲", "local/ui/views/relogin.js", "reloginStep",
     'if (dlg) dlg.classList.toggle("wide", step === "login");',
     'if (dlg) dlg.classList.toggle("wide", false);', 1, None, "登录那一屏宽一档"),
    ("J46", "甲", "local/ui/views/relogin.js", "reloginStep",
     'if (el) el.hidden = acts.indexOf(id) < 0;', 'if (el) el.hidden = false;', 1, None,
     "底栏按钮按步骤显隐"),
    ("J47", "甲", "local/ui/views/relogin.js", "reloginStep",
     'if (foot) foot.hidden = acts.length === 0;', 'if (foot) foot.hidden = false;', 1, None,
     "忙碌时整条底栏收起"),
    ("J48", "甲", "local/ui/views/relogin.js", "reloginNextReady",
     'if (btn) btn.disabled = !user || !pass;', 'if (btn) btn.disabled = false;', 1, None,
     "账号密码都填了才亮下一步"),
    ("J49", "甲", "local/ui/views/relogin.js", "reloginCodeReady",
     'if (btn) btn.disabled = !/^[0-9A-Za-z]{4}$/.test(code);', 'if (btn) btn.disabled = false;', 1, None,
     "验证码满 4 位才亮登录"),
    ("J50", "甲", "local/ui/views/relogin.js", "reloginError",
     'err.hidden = !text;', 'err.hidden = false;', 1, None, "红字有内容才出现"),
    ("J51", "甲", "local/ui/views/relogin.js", "openRelogin",
     'if (reloginRelay && reloginRelay.live) {', 'if (false) {', 1, None,
     "中继里有一场在跑就接上"),
    ("J52", "甲", "local/ui/views/relogin.js", "openRelogin",
     'if (reloginRelay.state === "waiting_code" && reloginRelay.mode !== "auto" && reloginRelay.image) {',
     'if (false) {', 1, None, "接上时已经有验证码图就直接画验证码步"),
    ("J53", "甲", "local/ui/views/relogin.js", "openRelogin",
     'reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");',
     'reloginStep("wait", "正在登录…");', 1, None, "接上时等待行的说法"),
    ("J54", "甲", "local/ui/views/relogin.js", "openRelogin",
     'if (kind === "bad") reloginStep("bad");', 'if (false) reloginStep("bad");', 1, None,
     "保存的密码不对就落那一步"),
    ("J55", "甲", "local/ui/views/relogin.js", "openRelogin",
     'else if (kind === "captcha") {', 'else if (false) {', 1, None, "有保存账号直接开验证码步"),
    ("J56", "甲", "local/ui/views/relogin.js", "openRelogin",
     'else reloginStep("login");', 'else reloginStep("bad");', 1, None, "没账号落登录表单"),
    ("J57", "甲", "local/ui/views/relogin.js", "loginEntry",
     'if (login.result === "expired" || login.handoff) {', 'if (false) {', 1, None,
     "登录过又失效才走重新登录"),
    ("J58", "甲", "local/ui/views/relogin.js", "closeRelogin",
     'const live = S.relogin && S.relogin.step && ["wait", "cap"].indexOf(S.relogin.step) >= 0;',
     'const live = false;', 1, None, "关掉时还活着的场次才要取消"),
    ("J59", "甲", "local/ui/views/relogin.js", "closeRelogin",
     'if (live && flowId && !reloginAutoLive(flowId)) return api("relogin_cancel", flowId).catch(() => {});',
     'if (false) return api("relogin_cancel", flowId).catch(() => {});', 1, None,
     "关掉时取消这一场"),
    ("J60", "甲", "local/ui/views/relogin.js", "reloginRefusal",
     'if (data.error === "plan_late") {', 'if (false) {', 1, None, "计划来不及时单独一句"),
    ("J61", "甲", "local/ui/views/relogin.js", "reloginRefusal",
     'return String(data.text || "这次没能开始登录，稍后再试。");',
     'return "这次没能开始登录，稍后再试。";', 1, None, "后端拒绝的兜底说法"),
    ("J62", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (handoff && !reloginHandoffSeen) {', 'if (false) {', 1, None, "转人工只提醒一次"),
    ("J63", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (!handoff) reloginHandoffSeen = false;', 'if (false) reloginHandoffSeen = false;', 1, None,
     "没转人工时清掉提醒过的标记"),
    ("J64", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (data.state === "success" || data.live === false) S.login.handoff = false;',
     'if (false) S.login.handoff = false;', 1, None, "一场走完就不再是等用户输码"),
    ("J65", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'else if (handoff) S.login.handoff = true;', 'else if (false) S.login.handoff = true;', 1, None,
     "转人工时记下已转人工"),
    ("J66", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'const auto = String(data.origin || "") === "auto" && !!data.live && !handoff',
     'const auto = false', 1, None, "顶栏「自动登录中…」的成立条件"),
    ("J67", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (auto !== !!S.autoLogin) {', 'if (false) {', 1, None, "自动登录态变了才重画胶囊与横幅"),
    ("J68", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (!S.relogin || !S.relogin.open) {', 'if (false) {', 1, None,
     "对话框没开时只记账不接管画面"),
    ("J69", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (data.state === "success") {', 'if (false) {', 1, None, "对话框没开时成功就刷新列表"),
    ("J70", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (state === "waiting_code" && data.mode !== "auto" && data.image) {', 'if (false) {', 1, None,
     "等到用户输码时画验证码步"),
    ("J71", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (state === "verifying" || state === "starting" || (state === "waiting_code" && data.mode === "auto")) {',
     'if (false) {', 1, None, "进行中画等待行"),
    ("J72", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (state === "success") {', 'if (false) {', 1, None, "对话框开着时成功画结果步"),
    ("J73", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (state === "failed" || state === "canceled") {', 'if (false) {', 1, None,
     "失败/取消画结果步"),
    ("J74", "甲", "local/ui/views/relogin.js", "receiveReloginState",
     'if (code === "bad_password") reloginStep("bad");', 'if (false) reloginStep("bad");', 1, None,
     "密码不对落「保存的密码不对」"),

    # ---------------- 读进行中标志（表乙）
    ("Y01", "乙", "local/ui/views/login.js", "paintLogin",
     'if (S.busy && !S.login.loginPending', 'if (false && !S.login.loginPending', 1, None,
     "paintLogin 读 S.busy"),
    ("Y02", "乙", "local/ui/views/login.js", "paintLogin",
     '&& !S.login.loginPending && !busyExpired', '&& true && !busyExpired', 1, None,
     "paintLogin 读 S.login.loginPending"),
    ("Y03", "乙", "local/ui/views/login.js", "paintLogin",
     '&& !busyExpired && !S.autoLogin) {', '&& !busyExpired && true) {', 1, None,
     "paintLogin 读 S.autoLogin"),
    ("Y04", "乙", "local/ui/views/login.js", "paintLogin", "", "", 1, "J04",
     "paintLogin 读 S.autoLogin（分支条件，与认结论同一处）"),
    ("Y05", "乙", "local/ui/views/login.js", "paintLogin", "", "", 1, "J05",
     "paintLogin 读 S.login.loginPending（分支条件，与认结论同一处）"),
    ("Y06", "乙", "local/ui/views/login.js", "paintLogin",
     '} else if (S.login.checking || (ok === null', '} else if (false || (ok === null', 1, None,
     "paintLogin 读 S.login.checking"),
    ("Y07", "乙", "local/ui/views/login.js", "setBusy",
     'if (S.busy && S.tour.open', 'if (false && S.tour.open', 1, None, "setBusy 读 S.busy 暂停引导"),
    ("Y08", "乙", "local/ui/views/login.js", "setBusy",
     'if (!S.busy && S.tour.paused) tourResumeNow();', 'if (S.tour.paused) tourResumeNow();', 1, None,
     "setBusy 读 S.busy 继续引导"),
    ("Y09", "乙", "local/ui/views/login.js", "setResult",
     'if (!S.busy) setResult(null);', 'if (true) setResult(null);', 1, None,
     "结果条自动收起前读 S.busy"),
    ("Y10", "乙", "local/ui/state/login.js", "reconcileAutoLogin", "", "", 1, "J15",
     "reconcileAutoLogin 读 S.autoLogin（与认结论同一处）"),
    ("Y11", "乙", "local/ui/state/login.js", "reconcileAutoLogin",
     '!reloginAutoLive()) S.autoLogin = false;', 'false) S.autoLogin = false;', 1, None,
     "reconcileAutoLogin 经 reloginAutoLive 读中继"),
    ("Y12", "乙", "local/ui/state/login.js", "setLogin",
     'if (S.login.result === "expired" && !S.login.handoff)',
     'if (S.login.result === "expired" && true)', 1, None, "setLogin 读 S.login.handoff"),
    ("Y13", "乙", "local/ui/views/relogin.js", "reloginAutoLive",
     'if (!relay || !relay.live ||', 'if (!relay || false ||', 1, None, "reloginAutoLive 读中继的 live"),
    ("Y14", "乙", "local/ui/views/relogin.js", "reloginAutoLive",
     'relay.handoff || String(relay.origin', 'false || String(relay.origin', 1, None,
     "reloginAutoLive 读中继的 handoff"),
    ("Y15", "乙", "local/ui/views/relogin.js", "reloginFromLogin", "", "", 1, "J30",
     "reloginFromLogin 读 S.relogin.fromLogin（与认结论同一处）"),
    ("Y16", "乙", "local/ui/views/relogin.js", "reloginWay", "", "", 1, "J43",
     "reloginWay 读 S.relogin.way（与认结论同一处）"),
    ("Y17", "乙", "local/ui/views/relogin.js", "watchBrowserLogin",
     'if (!S.relogin || !S.relogin.open) {', 'if (!S.relogin || false) {', 1, None,
     "轮询读 S.relogin.open"),
    ("Y18", "乙", "local/ui/views/relogin.js", "watchBrowserLogin",
     'if (login.result === "valid" || login.ok === true) {', 'if (false) {', 1, None,
     "轮询读 S.login 的结论"),
    ("Y19", "乙", "local/ui/views/relogin.js", "openRelogin",
     ' && reloginRelay.live) {', ') {', 1, None, "openRelogin 读中继的 live"),
    ("Y20", "乙", "local/ui/views/relogin.js", "openRelogin",
     'reloginRelay.state === "waiting_code" && ', '', 1, None, "openRelogin 读中继的 state"),
    ("Y21", "乙", "local/ui/views/relogin.js", "openRelogin",
     ' && reloginRelay.mode !== "auto"', '', 1, None, "openRelogin 读中继的 mode（是否自动）"),
    ("Y22", "乙", "local/ui/views/relogin.js", "openRelogin",
     ' && reloginRelay.image) {', ') {', 1, None, "openRelogin 读中继的 image"),
    ("Y23", "乙", "local/ui/views/relogin.js", "openRelogin",
     'reloginStep("wait", reloginRelay.mode === "auto" ? "电脑正在识别验证码…" : "正在登录…");',
     'reloginStep("wait", "正在登录…");', 1, None, "openRelogin 等待行读中继的 mode"),
    ("Y24", "乙", "local/ui/views/relogin.js", "reloginPickWay",
     'if (!S.relogin || !S.relogin.open) return;', 'if (!S.relogin) return;', 1, None,
     "reloginPickWay 读 S.relogin.open"),
    ("Y25", "乙", "local/ui/views/relogin.js", "closeRelogin", "", "", 1, "J58",
     "closeRelogin 读 S.relogin.step（与认结论同一处）"),
    ("Y26", "乙", "local/ui/views/relogin.js", "closeRelogin",
     'if (live && flowId && !reloginAutoLive(flowId))', 'if (live && flowId && false)', 1, None,
     "closeRelogin 经 reloginAutoLive 读中继"),
    ("Y27", "乙", "local/ui/views/relogin.js", "beginRelogin",
     'if (!S.relogin.open) return;', 'if (false) return;', 1, None, "beginRelogin 读 S.relogin.open"),
    ("Y28", "乙", "local/ui/views/relogin.js", "autoReloginOnce",
     'if (!S.relogin.open) return;', 'if (false) return;', 1, None,
     "autoReloginOnce 读 S.relogin.open"),
    ("Y29", "乙", "local/ui/views/relogin.js", "submitReloginCode",
     'if (S.relogin.open && result', 'if (result', 1, None, "提交验证码回来读 S.relogin.open"),
    ("Y30", "乙", "local/ui/views/relogin.js", "reloginSucceeded",
     'if (S.busy) return;', 'if (false) return;', 1, None, "登录成功后读 S.busy"),
    ("Y31", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     '!(S.login && S.login.result === "valid")', '!(false)', 1, None,
     "收进度时读 S.login 的结论"),
    ("Y32", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'if (auto !== !!S.autoLogin) {', 'if (auto !== false) {', 1, None,
     "收进度时读 S.autoLogin"),
    ("Y33", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'if (!S.relogin || !S.relogin.open) {', 'if (!S.relogin || false) {', 1, None,
     "收进度时读 S.relogin.open"),
    ("Y34", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'if (S.busy) addLog("重新登录成功，报名计划照常继续");',
     'if (false) addLog("重新登录成功，报名计划照常继续");', 1, None,
     "对话框没开时读 S.busy 写运行记录"),
    ("Y35", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'addLog(S.busy ? "重新登录成功，报名计划照常继续" : "重新登录成功");',
     'addLog("重新登录成功");', 1, None, "成功那一条运行记录读 S.busy"),
    ("Y36", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'reloginStep("msg", S.busy ? "重新登录成功，报名计划照常继续。" : "重新登录成功。");',
     'reloginStep("msg", "重新登录成功。");', 1, None, "成功结果步读 S.busy"),
    ("Y37", "乙", "local/ui/views/relogin.js", "receiveReloginState",
     'if (S.relogin.flowId && data.flow_id && String(data.flow_id) !== S.relogin.flowId) return;',
     'if (data.flow_id && false) return;', 1, None, "收进度时读 S.relogin.flowId"),
    ("Y38", "乙", "local/ui/views/status-cards.js", "renderLoginCard",
     'S.busy || !!S.login.checking', '!!S.login.checking', 1, None,
     "登录详情卡的检查按钮读 S.busy"),
    ("Y39", "乙", "local/ui/views/status-cards.js", "renderLoginCard",
     '!!S.login.checking || termsLocked()', 'false || termsLocked()', 1, None,
     "登录详情卡的检查按钮读 S.login.checking"),
    ("Y40", "乙", "local/ui/controllers/refresh.js", "scheduleSignedRefresh",
     'if (S.busy || S.starting || S.demo) return;', 'if (S.starting || S.demo) return;', 1, None,
     "计划运行时推迟刷新读 S.busy"),
    ("Y41", "乙", "local/ui/controllers/refresh.js", "checkRoundOpen",
     'return S.round.background ? !!S.runtime.checkPending : !!S.login.checking;',
     'return S.round.background ? !!S.runtime.checkPending : false;', 1, None,
     "前台轮是否在跑读 S.login.checking"),
    ("Y42", "乙", "local/ui/controllers/refresh.js", "autoRefreshDue",
     'if (S.login.result !== "valid") return false;', 'if (false) return false;', 1, None,
     "自动刷新读 S.login 的结论"),
    ("Y43", "乙", "local/ui/controllers/refresh.js", "autoRefreshDue",
     'if (S.login.loginPending) return false;', 'if (false) return false;', 1, None,
     "自动刷新读 S.login.loginPending"),
    ("Y44", "乙", "local/ui/controllers/refresh.js", "autoRefreshDue",
     'if (S.login.checking) return false;', 'if (false) return false;', 1, None,
     "自动刷新读 S.login.checking"),
]

FUNC_RE = r"(?m)^(?:async )?function %s\("
NEXT_FUNC_RE = r"(?m)^(?:async )?function "


def read_source(path: Path) -> str:
    """按字节读，不做换行翻译：共享盘上的文件可能是 CRLF，写回去要保持原样。"""
    return path.read_bytes().decode("utf-8")


def with_crlf(text: str, snippet: str) -> str:
    """定位串内部只写 \\n；文件是 CRLF 时换成 CRLF 再比对。"""
    return snippet.replace("\n", "\r\n") if "\r\n" in text else snippet


def region_of(text: str, fn: str) -> tuple[int, int]:
    m = re.search(FUNC_RE % re.escape(fn), text)
    if not m:
        raise KeyError("找不到函数 %s" % fn)
    start = m.start()
    nxt = re.search(NEXT_FUNC_RE, text[m.end():])
    end = m.end() + nxt.start() if nxt else len(text)
    return start, end


def apply_row(text: str, row: dict) -> str:
    """在函数体里把定位串换成替换串；命中次数不对就抛错（不猜）。"""
    if row["reuse"]:
        raise ValueError("复用行不该被应用")
    start, end = region_of(text, row["fn"])
    body = text[start:end]
    old = with_crlf(body, row["old"])
    new = with_crlf(body, row["new"])
    count = body.count(old)
    if count < row["nth"]:
        raise KeyError("%s %s 里找不到第 %d 处：%r（命中 %d）"
                       % (row["file"], row["fn"], row["nth"], old, count))
    idx = -1
    for _ in range(row["nth"]):
        idx = body.index(old, idx + 1)
    body = body[:idx] + new + body[idx + len(old):]
    return text[:start] + body + text[end:]


def git_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(root), capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def make_copy(dest: Path) -> None:
    for rel in git_files(REPO):
        if rel.startswith(SKIP_COPY) or rel.endswith("/__pycache__"):
            continue
        src = REPO / rel
        if not src.is_file():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


FAIL_RE = re.compile(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)")
MSG_RE = re.compile(r"^(AssertionError|KeyError|TypeError|NameError|ReferenceError|IndexError|AttributeError|ValueError)(.*)$")


def parse_failures(output: str) -> list[dict]:
    found = []
    current = None
    for line in output.splitlines():
        m = FAIL_RE.match(line.strip())
        if m:
            current = {"test": m.group(1), "case": m.group(2), "message": ""}
            found.append(current)
            continue
        if current is not None and not current["message"]:
            m2 = MSG_RE.match(line.strip())
            if m2:
                current["message"] = (m2.group(1) + m2.group(2)).strip()[:300]
    return found


def run_tests(root: Path, files: list[str] | None = None) -> dict:
    failures, ran, errors = [], 0, []
    for name in files or TEST_FILES:
        if not (root / "local" / "tests" / name).is_file():
            continue
        proc = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", name],
            cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        out = proc.stdout + proc.stderr
        m = re.search(r"^Ran (\d+) tests?", out, re.M)
        if m:
            ran += int(m.group(1))
        if proc.returncode != 0 and not FAIL_RE.search(out):
            errors.append({"file": name, "tail": out.strip().splitlines()[-6:]})
        for item in parse_failures(out):
            item["file"] = name
            failures.append(item)
    return {"ran": ran, "failures": failures, "errors": errors}


def row_dict(raw) -> dict:
    rid, table, file, fn, old, new, nth, reuse, what = raw
    return {"id": rid, "table": table, "file": file, "fn": fn, "old": old, "new": new,
            "nth": nth, "reuse": reuse, "what": what}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="只检查每条定位串能否在自己的函数里唯一找到")
    ap.add_argument("--baseline", action="store_true", help="在未变异的副本上跑一遍相关测试")
    ap.add_argument("--ids", default="", help="只跑这些行，逗号分隔")
    ap.add_argument("--legacy-only", action="store_true",
                    help="只跑补测前的测试文件（量「补测前」时用，后面两个新文件不参与）")
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    ap.add_argument("--out", default="", help="把结果 JSON 写到这个路径")
    args = ap.parse_args(argv)

    rows = [row_dict(r) for r in ROWS]
    test_files = TEST_FILES[:8] if args.legacy_only else TEST_FILES
    if args.ids:
        wanted = [x.strip() for x in args.ids.split(",") if x.strip()]
        by_id = {r["id"]: r for r in rows}
        rows = [by_id[i] for i in wanted]
    elif args.shard_count > 1 and not args.baseline and not args.verify:
        rows = [r for r in rows
                if zlib.crc32(("%s:%s" % (r["file"], r["old"] or r["reuse"])).encode("utf-8"))
                % args.shard_count == args.shard_index]

    if args.verify:
        bad = []
        for r in rows:
            if r["reuse"]:
                continue
            text = read_source(REPO / r["file"])
            start, end = region_of(text, r["fn"])
            n = text[start:end].count(with_crlf(text, r["old"]))
            status = "ok" if n >= r["nth"] else "MISS"
            if n != 1:
                status += "（命中 %d 处）" % n
            if status != "ok":
                bad.append((r["id"], r["file"], r["fn"], status))
            print("%-5s %-34s %-22s %s" % (r["id"], r["file"], r["fn"], status))
        print("\n定位不到或命中多处的行：%d" % len(bad))
        for item in bad:
            print("  ", item)
        return 1 if bad else 0

    workdir = Path(tempfile.mkdtemp(prefix="login-net-"))
    result = {"shard": args.shard_index, "shard_count": args.shard_count, "rows": []}
    try:
        if args.baseline:
            root = workdir / "baseline"
            make_copy(root)
            result["baseline"] = run_tests(root, test_files)
            print(json.dumps(result["baseline"], ensure_ascii=False)[:600])
        else:
            for r in rows:
                if r["reuse"]:
                    continue
                root = workdir / r["id"]
                make_copy(root)
                path = root / r["file"]
                original = read_source(path)
                try:
                    mutated = apply_row(original, r)
                except (KeyError, ValueError) as exc:
                    result["rows"].append({**r, "status": "invalid", "detail": str(exc)})
                    print("%-5s invalid %s" % (r["id"], exc))
                    continue
                if mutated == original:
                    result["rows"].append({**r, "status": "invalid", "detail": "替换后没有变化"})
                    print("%-5s invalid 替换后没有变化" % r["id"])
                    continue
                path.write_bytes(mutated.encode("utf-8"))
                outcome = run_tests(root, test_files)
                status = "killed" if outcome["failures"] else "survived"
                result["rows"].append({**r, "status": status, **outcome})
                print("%-5s %-9s 变红 %2d 条 %s" % (
                    r["id"], status, len(outcome["failures"]),
                    outcome["failures"][0]["test"] if outcome["failures"] else "(没红)"))
                shutil.rmtree(root, ignore_errors=True)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
