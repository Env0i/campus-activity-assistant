#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页第四组（重新登录）8 个函数的六类单点变异与行为测试判定。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py --list
  python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py --baseline
  python design/evidence/2026-11-23/phone-relogin-net/scripts/mutate_relogin.py --workers 4 --out design/evidence/2026-11-23/phone-relogin-net/before.md

@author Author
"""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
TARGET_FILES = ("local/ui/m/ui-relogin.js",)
ALL_FUNCTIONS = (
    "renderRelogin",
    "openRelogin",
    "endReloginControls",
    "ingestRelogin",
    "beginRelogin",
    "submitRelogin",
    "cancelRelogin",
    "refreshRelogin",
)
TEST_REL = Path("local/tests/test_phone_ui.py")
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

MUTATIONS: tuple[tuple[str, str, str, str, int, str, str], ...] = (
    # renderRelogin (24)
    ("M001", "乙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     'if (model.sheetId === "relogin")', 'if (!(model.sheetId === "relogin"))'),
    ("M002", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("sheet-title").textContent = PhoneModel.loginCopy(\n'
     '      model.relFirstLogin ? "never" : "expired", false).reloginEntry;',
     "void 0;"),
    ("M003", "乙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     "model.relFirstLogin ?", "!(model.relFirstLogin) ?"),
    ("M004", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-err").textContent = view.err;', "void 0;"),
    ("M005", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-err").hidden = !view.err;', "void 0;"),
    ("M006", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-spin").hidden = !view.spin;', "void 0;"),
    ("M007", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-busy-text").textContent = view.spin;', "void 0;"),
    ("M008", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-text").textContent = view.text;', "void 0;"),
    ("M009", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-text").hidden = !view.text;', "void 0;"),
    ("M010", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-form").hidden = !view.showForm;', "void 0;"),
    ("M011", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-lead").textContent = view.lead;', "void 0;"),
    ("M012", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-lead").hidden = !view.lead;', "void 0;"),
    ("M013", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("relogin-account").hidden = !view.needAcct;', "void 0;"),
    ("M014", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("relogin-captcha-group").hidden = !view.needCap;', "void 0;"),
    ("M015", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-auto").hidden = !view.autoCap;', "void 0;"),
    ("M016", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-save-gain").textContent = view.saveLine;', "void 0;"),
    ("M017", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-auto").hidden = view.mainKind !== "auto";', "void 0;"),
    ("M018", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin").hidden = view.mainKind !== "begin";', "void 0;"),
    ("M019", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-submit").hidden = view.mainKind !== "submit";', "void 0;"),
    ("M020", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("rel-second-row").hidden = !(view.refresh || view.cancel);', "void 0;"),
    ("M021", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-refresh").hidden = !view.refresh;', "void 0;"),
    ("M022", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-cancel").hidden = !view.cancel;', "void 0;"),
    ("M023", "丙", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-done").hidden = !view.done;', "void 0;"),
    ("M024", "己", "local/ui/m/ui-relogin.js", "renderRelogin", 1,
     '$("btn-relogin-done").textContent = view.done;', "void 0;"),
    # openRelogin (4)
    ("M025", "乙", "local/ui/m/ui-relogin.js", "openRelogin", 1,
     'if (model.sheetId === "relogin")', 'if (!(model.sheetId === "relogin"))'),
    ("M026", "乙", "local/ui/m/ui-relogin.js", "openRelogin", 1,
     "if (model.sheetId) closeSheet(true);", "if (!(model.sheetId)) closeSheet(true);"),
    ("M027", "甲", "local/ui/m/ui-relogin.js", "openRelogin", 1,
     'model.relFirstLogin = PhoneModel.loginState(model.login) === "never";', "void 0;"),
    ("M028", "甲", "local/ui/m/ui-relogin.js", "openRelogin", 1,
     "model.relConfirm = !liveFlow && !setup.paused && !!setup.saved && !!setup.ocr_ready;", "void 0;"),
    # endReloginControls (2)
    ("M029", "丙", "local/ui/m/ui-relogin.js", "endReloginControls", 1,
     '$("captcha").hidden = true;', "void 0;"),
    ("M030", "己", "local/ui/m/ui-relogin.js", "endReloginControls", 1,
     '$("captcha").removeAttribute("src");', "void 0;"),
    # ingestRelogin (42)
    ("M031", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "model.flow = info;", "void 0;"),
    ("M032", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'if (String(info.mode || "") === "auto"\n'
     '      && relayState !== "success" && relayState !== "failed" && relayState !== "canceled")',
     'if (!(String(info.mode || "") === "auto"\n'
     '      && relayState !== "success" && relayState !== "failed" && relayState !== "canceled"))'),
    ("M033", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "if (info.retrying)", "if (!(info.retrying))"),
    ("M034", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = "电脑正在自动登录" +\n'
     '        (rounds > 0 ? "（第 " + (rounds + 1) + " 次）" : "") + "…";',
     "void 0;"),
    ("M035", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "rounds > 0 ?", "!(rounds > 0) ?"),
    ("M036", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent =\n'
     '        "电脑会自动识别验证码；连续失败几次之后才会转到这里手动输入";',
     "void 0;"),
    ("M037", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;\n'
     '    model.reloginStarting = false;',
     '    void 0;\n'
     '    model.reloginSubmitting = false;\n'
     '    model.reloginStarting = false;'),
    ("M038", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;\n'
     '    model.reloginStarting = false;',
     '    model.challenge = null;\n'
     '    void 0;\n'
     '    model.reloginStarting = false;'),
    ("M039", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "model.reloginStarting = false;", "void 0;"),
    ("M040", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'if (relayState === "waiting_code" && info.challenge_id)',
     'if (!(relayState === "waiting_code" && info.challenge_id))'),
    ("M041", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "if (PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id))",
     "if (!(PhoneModel.matchesChallenge(model.challenge, info.flow_id, info.challenge_id)))"),
    ("M042", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "if (!info.submit_pending)", "if (!(!info.submit_pending))"),
    ("M043", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "if (!info.submit_pending) model.reloginSubmitting = false;",
     "if (!info.submit_pending) void 0;"),
    ("M044", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "model.challenge = {\n      flow_id: info.flow_id, challenge_id: info.challenge_id,\n    };",
     "void 0;"),
    ("M045", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.reloginSubmitting = false;\n    const img = $("captcha");',
     '    void 0;\n    const img = $("captcha");'),
    ("M046", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'if (String(info.image || "").indexOf("data:image/png;base64,") === 0)',
     'if (!(String(info.image || "").indexOf("data:image/png;base64,") === 0))'),
    ("M047", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "img.src = info.image;", "void 0;"),
    ("M048", "丙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "img.hidden = false;", "void 0;"),
    ("M049", "丙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "img.hidden = true;", "void 0;"),
    ("M050", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'img.removeAttribute("src");', "void 0;"),
    ("M051", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("code").value = "";', "void 0;"),
    ("M052", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'if (relayState === "verifying")', 'if (!(relayState === "verifying"))'),
    ("M053", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.reloginSubmitting = false;\n'
     '    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;',
     '    void 0;\n'
     '    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;'),
    ("M054", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;', "void 0;"),
    ("M055", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'else if (relayState === "starting")', 'else if (!(relayState === "starting"))'),
    ("M056", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.reloginSubmitting = false;\n'
     '    $("relogin-note").textContent = String(info.mode || "") === "auto"',
     '    void 0;\n'
     '    $("relogin-note").textContent = String(info.mode || "") === "auto"'),
    ("M057", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = String(info.mode || "") === "auto"\n'
     '      ? PhoneModel.RELOGIN_BUSY.prepare : PhoneModel.RELOGIN_BUSY.needCode;',
     "void 0;"),
    ("M058", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'String(info.mode || "") === "auto"\n      ?',
     '!(String(info.mode || "") === "auto")\n      ?'),
    ("M059", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'else if (relayState === "success")', 'else if (!(relayState === "success"))'),
    ("M060", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '  } else if (relayState === "success") {\n'
     '    model.challenge = null;',
     '  } else if (relayState === "success") {\n'
     '    void 0;'),
    ("M061", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '  } else if (relayState === "success") {\n'
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;',
     '  } else if (relayState === "success") {\n'
     '    model.challenge = null;\n'
     '    void 0;'),
    ("M062", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "if (info.live)", "if (!(info.live))"),
    ("M063", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = PhoneModel.loginDoneText(!!model.relFirstLogin, model.busy);',
     "void 0;"),
    ("M064", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = "上次重新登录已完成；需要时点「重新登录」再试";', "void 0;"),
    ("M065", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'else if (relayState === "failed" || relayState === "canceled")',
     'else if (!(relayState === "failed" || relayState === "canceled"))'),
    ("M066", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '  } else if (relayState === "failed" || relayState === "canceled") {\n'
     '    model.challenge = null;',
     '  } else if (relayState === "failed" || relayState === "canceled") {\n'
     '    void 0;'),
    ("M067", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '  } else if (relayState === "failed" || relayState === "canceled") {\n'
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;',
     '  } else if (relayState === "failed" || relayState === "canceled") {\n'
     '    model.challenge = null;\n'
     '    void 0;'),
    ("M068", "己", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '$("relogin-note").textContent = info.live\n'
     '      ? PhoneModel.reloginFailText(reason)\n'
     '      : PhoneModel.reloginFailText(reason, "上次重新登录未完成：");',
     "void 0;"),
    ("M069", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     "info.live\n      ?", "!(info.live)\n      ?"),
    ("M070", "乙", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     'else if (relayState && relayState !== "waiting_code")',
     'else if (!(relayState && relayState !== "waiting_code"))'),
    ("M071", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;\n'
     '    endReloginControls();\n'
     '  }',
     '    void 0;\n'
     '    model.reloginSubmitting = false;\n'
     '    endReloginControls();\n'
     '  }'),
    ("M072", "甲", "local/ui/m/ui-relogin.js", "ingestRelogin", 1,
     '    model.challenge = null;\n'
     '    model.reloginSubmitting = false;\n'
     '    endReloginControls();\n'
     '  }',
     '    model.challenge = null;\n'
     '    void 0;\n'
     '    endReloginControls();\n'
     '  }'),
    # beginRelogin (25)
    ("M073", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "if (model.reloginStarting)", "if (!(model.reloginStarting))"),
    ("M074", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "if (!canWrite())", "if (!(!canWrite()))"),
    ("M075", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.reloginStarting = true;", "void 0;"),
    ("M076", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.relConfirm = false;", "void 0;"),
    ("M077", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.relEnteredAcct = false;", "void 0;"),
    ("M078", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.relSavedChoice = false;", "void 0;"),
    ("M079", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "if (account && !account.hidden)", "if (!(account && !account.hidden))"),
    ("M080", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "if (!user || !pass)", "if (!(!user || !pass))"),
    ("M081", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '      model.reloginStarting = false;\n'
     '      $("relogin-note").textContent = "账号和密码都要填。";',
     '      void 0;\n'
     '      $("relogin-note").textContent = "账号和密码都要填。";'),
    ("M082", "己", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '$("relogin-note").textContent = "账号和密码都要填。";', "void 0;"),
    ("M083", "丁", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "args.username = user;", "void 0;"),
    ("M084", "丁", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "args.password = pass;", "void 0;"),
    ("M085", "丁", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     'args.save = !!($("relogin-save") || {}).checked;', "void 0;"),
    ("M086", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.relEnteredAcct = true;", "void 0;"),
    ("M087", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "model.relSavedChoice = args.save;", "void 0;"),
    ("M088", "己", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '$("relogin-pass").value = "";', "void 0;"),
    ("M089", "丁", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     'action: "phone_relogin_begin",', "action: undefined,"),
    ("M090", "丁", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     'action: "phone_relogin_begin", args: args',
     'action: "phone_relogin_begin", args: undefined'),
    ("M091", "甲", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '  model.reloginStarting = false;\n  if (!body || !body.ok)',
     '  void 0;\n  if (!body || !body.ok)'),
    ("M092", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     "if (!body || !body.ok)", "if (!(!body || !body.ok))"),
    ("M093", "己", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '$("relogin-note").textContent = body && body.error === "plan_late"\n'
     '      ? "现在来不及重新登录：" + String(body.text || "有场次正在提交，或者离开放不到 100 秒。")\n'
     '      : "还不能开始：" + String((body && body.text) || (body && body.error) || "请到电脑上准备账号");',
     "void 0;"),
    ("M094", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     'body && body.error === "plan_late"\n      ?',
     '!(body && body.error === "plan_late")\n      ?'),
    ("M095", "乙", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     'if (String(body.mode || "") === "auto")',
     'if (!(String(body.mode || "") === "auto"))'),
    ("M096", "己", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '$("relogin-note").textContent = "电脑正在自动登录，手机上不用再操作";', "void 0;"),
    ("M097", "己", "local/ui/m/ui-relogin.js", "beginRelogin", 1,
     '$("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.needCode;', "void 0;"),
    # submitRelogin (21)
    ("M098", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "if (!model.flow || !model.challenge)", "if (!(!model.flow || !model.challenge))"),
    ("M099", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "if (!PhoneModel.canSubmitRelogin(model, model.challenge))",
     "if (!(!PhoneModel.canSubmitRelogin(model, model.challenge)))"),
    ("M100", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "if (!PhoneModel.relCanSubmit({ needCap: true, code }))",
     "if (!(!PhoneModel.relCanSubmit({ needCap: true, code })))"),
    ("M101", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "if (!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id,\n"
     "                                   model.challenge.challenge_id))",
     "if (!(!PhoneModel.matchesChallenge(model.flow, model.challenge.flow_id,\n"
     "                                   model.challenge.challenge_id)))"),
    ("M102", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '$("relogin-note").textContent = "验证码已换代，请看新图";', "void 0;"),
    ("M103", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '    $("relogin-note").textContent = "验证码已换代，请看新图";\n    $("code").value = "";',
     '    $("relogin-note").textContent = "验证码已换代，请看新图";\n    void 0;'),
    ("M104", "甲", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "model.reloginSubmitting = true;", "void 0;"),
    ("M105", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     'method: "POST",', "method: undefined,"),
    ("M106", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     'body: { action: "phone_relogin_submit", args: {\n'
     '        flow_id: model.challenge.flow_id,\n'
     '        challenge_id: model.challenge.challenge_id, code } }',
     "body: undefined"),
    ("M107", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     'action: "phone_relogin_submit",', "action: undefined,"),
    ("M108", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "args: {\n"
     "        flow_id: model.challenge.flow_id,\n"
     "        challenge_id: model.challenge.challenge_id, code }",
     "args: undefined"),
    ("M109", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "flow_id: model.challenge.flow_id,", "flow_id: undefined,"),
    ("M110", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "challenge_id: model.challenge.challenge_id,", "challenge_id: undefined,"),
    ("M111", "丁", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "code } } });", "code: undefined } } });"),
    ("M112", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '  } catch (err) {\n'
     '    // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端\n'
     '    // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。\n'
     '    // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」\n'
     '    $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;',
     '  } catch (err) {\n'
     '    // 结果未知：既不能当成功也不能当失败。保持禁用，先对账问服务端\n'
     '    // 这张图到底有没有在途提交，等快照给结论再决定放行还是收口。\n'
     '    // RL02：旧句「提交结果未知，正在对账…」归并为「正在登录，请等结果」\n'
     '    void 0;'),
    ("M113", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "if (!result || result.status !== 200 || !result.body || !result.body.ok)",
     "if (!(!result || result.status !== 200 || !result.body || !result.body.ok))"),
    ("M114", "乙", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     'if (error === "duplicate_submit")', 'if (!(error === "duplicate_submit"))'),
    ("M115", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '    if (error === "duplicate_submit") {\n'
     '      // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行\n'
     '      // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」\n'
     '      $("relogin-note").textContent = PhoneModel.RELOGIN_BUSY.verify;',
     '    if (error === "duplicate_submit") {\n'
     '      // 服务端说同一张图还有在途提交：别解锁，等它的结论再放行\n'
     '      // RL02：旧句「验证码正在提交，请等待结果」同样归并进「正在登录，请等结果」\n'
     '      void 0;'),
    ("M116", "甲", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     "model.reloginSubmitting = false;", "void 0;"),
    ("M117", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '$("relogin-note").textContent = String(\n'
     '      (result && result.body && (result.body.text || result.body.error))\n'
     '        || "提交没有被接受");',
     "void 0;"),
    ("M118", "己", "local/ui/m/ui-relogin.js", "submitRelogin", 1,
     '  $("code").value = "";\n  void poll(true);',
     '  void 0;\n  void poll(true);'),
    # cancelRelogin (10)
    ("M119", "乙", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "if (!flowId || (flow && flow.live === false))",
     "if (!(!flowId || (flow && flow.live === false)))"),
    ("M120", "戊", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "if (!flowId || (flow && flow.live === false)) return true;",
     "if (!flowId || (flow && flow.live === false)) return false;"),
    ("M121", "丁", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     'action: "phone_relogin_cancel",', "action: undefined,"),
    ("M122", "丁", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "args: { flow_id: flowId }", "args: undefined"),
    ("M123", "丁", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "flow_id: flowId", "flow_id: undefined"),
    ("M124", "乙", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "if (body && body.error)", "if (!(body && body.error))"),
    ("M125", "戊", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "return false;", "return true;"),
    ("M126", "甲", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "model.challenge = null;", "void 0;"),
    ("M127", "丙", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     '$("captcha").hidden = true;', "void 0;"),
    ("M128", "戊", "local/ui/m/ui-relogin.js", "cancelRelogin", 1,
     "  return true;\n}", "  return false;\n}"),
    # refreshRelogin (1)
    ("M129", "乙", "local/ui/m/ui-relogin.js", "refreshRelogin", 1,
     "if (canceled === false)", "if (!(canceled === false))"),
)


def clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for k in PROXY_VARS:
        env.pop(k, None)
    return env


def func_ranges() -> dict[tuple[str, str], tuple[int, int]]:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node 不可用")
    code = (
        'import { readFileSync } from "node:fs";\n'
        'import { pathToFileURL } from "node:url";\n'
        'const [scan, ...files] = process.argv.slice(2);\n'
        'const { findFunctions } = await import(pathToFileURL(scan).href);\n'
        'const out = {};\n'
        'for (const fpath of files) {\n'
        '  const { funcs } = findFunctions(readFileSync(fpath, "utf8"));\n'
        '  const m = {};\n'
        '  for (const f of funcs) if (f.depth === 0 && f.kind === "function" && f.name) m[f.name] = [f.start, f.end];\n'
        '  out[fpath] = m;\n'
        '}\n'
        'process.stdout.write(JSON.stringify(out));\n'
    )
    abs_files = [str(REPO / rel) for rel in TARGET_FILES]
    res = subprocess.run(
        [node, "--input-type=module", "-", str(JSSCAN_MJS), *abs_files],
        input=code, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    raw = json.loads(res.stdout)
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for rel, abs_path in zip(TARGET_FILES, abs_files):
        for fn, rng in raw.get(abs_path, {}).items():
            out[(rel, fn)] = (int(rng[0]), int(rng[1]))
    return out


def test_behavior_map() -> dict[str, bool]:
    tree = ast.parse((REPO / TEST_REL).read_text(encoding="utf-8"))
    out: dict[str, bool] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        helpers: dict[str, ast.FunctionDef] = {
            item.name: item
            for item in node.body
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("test_")
        }
        behav_helpers: set[str] = {
            name for name, item in helpers.items()
            if any(
                isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "run_phone_js"
                for c in ast.walk(item)
            )
        }
        changed = True
        while changed:
            changed = False
            for name, item in helpers.items():
                if name in behav_helpers:
                    continue
                if any(
                    isinstance(c, ast.Call)
                    and isinstance(c.func, ast.Attribute)
                    and isinstance(c.func.value, ast.Name)
                    and c.func.value.id == "self"
                    and c.func.attr in behav_helpers
                    for c in ast.walk(item)
                ):
                    behav_helpers.add(name)
                    changed = True
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                uses_node = any(
                    isinstance(c, ast.Call) and (
                        (isinstance(c.func, ast.Name) and c.func.id == "run_phone_js")
                        or (isinstance(c.func, ast.Attribute)
                            and isinstance(c.func.value, ast.Name)
                            and c.func.value.id == "self"
                            and c.func.attr in behav_helpers)
                    )
                    for c in ast.walk(item)
                )
                out[f"{node.name}.{item.name}"] = uses_node
    return out


def apply_in_func(text: str, start: int, end: int, locate: str, repl: str) -> str | None:
    lines = text.splitlines(keepends=False)
    head = "\n".join(lines[:start - 1])
    body = "\n".join(lines[start - 1:end])
    tail = "\n".join(lines[end:])
    if locate.startswith("^"):
        pat = re.compile(locate, re.M)
        hits = list(pat.finditer(body))
        if len(hits) != 1:
            return None
        new_body = pat.sub(lambda _m: repl, body, count=1)
    else:
        if body.count(locate) != 1:
            return None
        new_body = body.replace(locate, repl, 1)
    parts = [p for p in (head, new_body, tail) if p]
    return "\n".join(parts) + ("\n" if text.endswith("\n") else "")


def create_archive_zip(zip_path: Path) -> None:
    subprocess.run(
        ["git", "archive", "--format=zip", "--output", str(zip_path), "HEAD"],
        cwd=REPO, check=True, capture_output=True,
    )


def open_replica(zip_path: Path) -> Path:
    root = Path(tempfile.mkdtemp(prefix="phone_relogin_mut_"))
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(root)
    dst_test = root / TEST_REL
    dst_test.parent.mkdir(parents=True, exist_ok=True)
    dst_test.write_bytes((REPO / TEST_REL).read_bytes())
    return root


def _parse_running_test(out_text: str) -> list[str]:
    m = re.findall(r"^([A-Za-z0-9_]+)\s+\(([^)]+)\)\s+\.\.\.", out_text, flags=re.M)
    if not m:
        return []
    meth, qual = m[-1]
    parts = qual.split(".")
    cls = parts[-2] if len(parts) >= 2 else ""
    return [f"{cls}.{meth}" if cls else meth]


def run_unittest(root: Path) -> tuple[int, list[str], int]:
    try:
        res = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests", "-p", "test_phone_ui.py", "-v"],
            cwd=root, env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )
    except subprocess.TimeoutExpired as exc:
        out_text = (exc.stdout or b"" if isinstance(exc.stdout, bytes) else exc.stdout or "")
        err_text = (exc.stderr or b"" if isinstance(exc.stderr, bytes) else exc.stderr or "")
        if isinstance(out_text, bytes):
            out_text = out_text.decode("utf-8", "replace")
        if isinstance(err_text, bytes):
            err_text = err_text.decode("utf-8", "replace")
        return 124, _parse_running_test(out_text + "\n" + err_text), 0
    out_text = (res.stdout or "") + "\n" + (res.stderr or "")
    fails = re.findall(r"^(?:FAIL|ERROR):\s+([A-Za-z0-9_]+)\s+\(([^)]+)\)", out_text, flags=re.M)
    names = []
    for meth, qual in fails:
        parts = qual.split(".")
        cls = parts[-2] if len(parts) >= 2 else ""
        names.append(f"{cls}.{meth}" if cls else meth)
    skipped = 0
    m = re.search(r"skipped=(\d+)", out_text)
    if m:
        skipped = int(m.group(1))
    return res.returncode, names, skipped


def run_one_in_replica(
    root: Path, orig_texts: dict[str, str], ranges: dict[tuple[str, str], tuple[int, int]],
    bmap: dict[str, bool], mut: tuple,
) -> dict:
    mid, kind, rel, fn, occur, locate, repl = mut
    target = root / rel
    orig_lf = orig_texts[rel]
    rng = ranges.get((rel, fn))
    if not rng:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "未找到目标函数", "timeout": False}
    mutated = apply_in_func(orig_lf, rng[0], rng[1], locate, repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "定位不唯一或未命中", "timeout": False}
    target.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        node = shutil.which("node")
        chk = subprocess.run([node, "--check", str(target)], capture_output=True, text=True, check=False)
        if chk.returncode != 0:
            return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                    "replace": repl, "status": "无效", "first_fail": "", "note": "node --check 失败", "timeout": False}
        code, fails, _ = run_unittest(root)
    finally:
        target.write_text(orig_lf, encoding="utf-8", newline="\n")
    if code == 0:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无人守", "first_fail": "", "note": "", "timeout": False}
    if code == 124:
        first = fails[0] if fails else "(timeout)"
        behav = [f for f in fails if bmap.get(f, False)]
        status = "行为守" if (behav or not fails) else "字面守"
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": status, "first_fail": f"{first}（超时）", "note": "超时", "timeout": True}
    if not fails:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "字面守", "first_fail": "(unknown)", "note": "非零退出但未解析出用例名", "timeout": False}
    behav = [f for f in fails if bmap.get(f, False)]
    status = "行为守" if behav else "字面守"
    return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
            "replace": repl, "status": status, "first_fail": fails[0], "note": "", "timeout": False}


def worker_chunk(
    zip_path: Path, orig_texts: dict[str, str], ranges: dict[tuple[str, str], tuple[int, int]],
    bmap: dict[str, bool], chunk: list[tuple],
) -> list[dict]:
    root = open_replica(zip_path)
    results = []
    try:
        for mut in chunk:
            results.append(run_one_in_replica(root, orig_texts, ranges, bmap, mut))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return results


def list_mutations(ranges: dict[tuple[str, str], tuple[int, int]], orig_texts: dict[str, str]) -> int:
    bad = 0
    for mid, kind, rel, fn, occur, locate, repl in MUTATIONS:
        rng = ranges.get((rel, fn))
        ok = bool(rng and apply_in_func(orig_texts[rel], rng[0], rng[1], locate, repl) is not None)
        if not ok:
            bad += 1
        loc_one = locate.replace("\n", "\\n")
        rep_one = repl.replace("\n", "\\n")
        print(f"{mid}\t{kind}\t{Path(rel).name}:{fn}\t#{occur}\t{'OK' if ok else 'MISS'}\t{loc_one} => {rep_one}")
    print(f"Total: {len(MUTATIONS)} (locate miss: {bad})")
    return 1 if bad else 0


def format_report(results: list[dict], phase: str, equiv: dict) -> str:
    cats = ("行为守", "字面守", "无人守", "无效", "等价")
    kinds = ("甲", "乙", "丙", "丁", "戊", "己")
    counts = {k: 0 for k in cats}
    by_kind = {knd: {k: 0 for k in cats} for knd in kinds}
    by_func = {fn: {"kinds": {knd: 0 for knd in kinds}, "cats": {k: 0 for k in cats}, "total": 0} for fn in ALL_FUNCTIONS}
    lines = [
        f"# 第四组（重新登录）变异结论（{phase}）",
        "",
        (
            f"- 范围：`local/ui/m/ui-relogin.js` 的 8 个顶层函数（共 {len(results)} 条）："
            f"甲类（`model.字段` 写换 `void 0`）{sum(1 for r in results if r['kind']=='甲')} 条、"
            f"乙类（条件 `C` 换 `!(C)`）{sum(1 for r in results if r['kind']=='乙')} 条、"
            f"丙类（`.hidden = X` 写换 `void 0`）{sum(1 for r in results if r['kind']=='丙')} 条、"
            f"丁类（请求载荷属性与 `args.*` 写入变异）{sum(1 for r in results if r['kind']=='丁')} 条、"
            f"戊类（`return true`/`false` 互换）{sum(1 for r in results if r['kind']=='戊')} 条、"
            f"己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`）{sum(1 for r in results if r['kind']=='己')} 条。"
        ),
        "",
        "| 编号 | 类 | 文件 | 函数 | 定位原文 | 替换后原文 | 结论 | 第一条失败用例 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    equiv_notes = []
    for r in results:
        st = r["status"]
        if st == "无人守" and r["id"] in equiv:
            st = "等价"
            info = equiv[r["id"]]
            reason = info.get("reason", "") if isinstance(info, dict) else str(info)
            callers = info.get("callers", "") if isinstance(info, dict) else ""
            equiv_notes.append((r["id"], r["file"], r["func"], reason, callers))
        counts[st] = counts.get(st, 0) + 1
        by_kind[r["kind"]][st] = by_kind[r["kind"]].get(st, 0) + 1
        fn_stat = by_func[r["func"]]
        fn_stat["total"] += 1
        fn_stat["kinds"][r["kind"]] += 1
        fn_stat["cats"][st] += 1
        loc = r["locate"].replace("\n", " ↵ ").replace("|", "\\|")
        rep = r["replace"].replace("\n", " ↵ ").replace("|", "\\|")
        ff = f"`{r['first_fail']}`" if r["first_fail"] else "—"
        f_short = Path(r["file"]).name
        lines.append(f"| {r['id']} | {r['kind']} | `{f_short}` | `{r['func']}` | `{loc}` | `{rep}` | {st} | {ff} |")
    lines.extend(["", "## 各类合计", ""])
    for k in cats:
        lines.append(f"- {k}：{counts[k]}")
    lines.append(f"- 总计：{len(results)}")
    lines.extend([
        "",
        "## 按变异口径统计",
        "",
        "| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    kind_labels = {
        "甲": "甲类（`model.字段` 写换 `void 0`）",
        "乙": "乙类（条件 `C` 换 `!(C)`）",
        "丙": "丙类（`.hidden = X` 写换 `void 0`）",
        "丁": "丁类（请求载荷属性与 `args.*` 写入变异）",
        "戊": "戊类（`return true`/`false` 互换）",
        "己": "己类（`.textContent`/`.value`/`.src`/`removeAttribute` 写换 `void 0`）",
    }
    for knd in kinds:
        row_c = by_kind[knd]
        sub_total = sum(row_c.values())
        lines.append(
            f"| {kind_labels[knd]} | {row_c['行为守']} | {row_c['字面守']} | {row_c['无人守']} | "
            f"{row_c['无效']} | {row_c['等价']} | {sub_total} |"
        )
    lines.extend([
        "",
        "## 按函数统计",
        "",
        "| 函数 | 口径（甲 / 乙 / 丙 / 丁 / 戊 / 己） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ])
    for fn in ALL_FUNCTIONS:
        fs = by_func[fn]
        ks = " / ".join(str(fs["kinds"][knd]) for knd in kinds)
        cs = fs["cats"]
        lines.append(
            f"| `{fn}` | {ks} | {cs['行为守']} | {cs['字面守']} | {cs['无人守']} | "
            f"{cs['无效']} | {cs['等价']} | {fs['total']} |"
        )
    if equiv_notes:
        lines.extend(["", "## 等价判定理由与调用方证明", ""])
        for mid, rel, fn, reason, callers in equiv_notes:
            tail = f" 调用方证明：{callers}" if callers else ""
            lines.append(f"- **{mid}**（`{Path(rel).name}:{fn}`）：{reason}{tail}")
    return "\n".join(lines) + "\n"


def run_parallel(selected: list[tuple], workers: int) -> list[dict]:
    orig_texts = {
        rel: (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        for rel in TARGET_FILES
    }
    ranges = func_ranges()
    bmap = test_behavior_map()
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_relogin_zip_"))
    zip_path = tmp_zip_dir / "repo.zip"
    try:
        create_archive_zip(zip_path)
        w = max(1, min(4, workers, len(selected)))
        chunks = [selected[i::w] for i in range(w)]
        merged = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=w) as ex:
            futs = [ex.submit(worker_chunk, zip_path, orig_texts, ranges, bmap, ch) for ch in chunks if ch]
            for fut in concurrent.futures.as_completed(futs):
                merged.extend(fut.result())
        order = {m[0]: idx for idx, m in enumerate(MUTATIONS)}
        merged.sort(key=lambda r: order[r["id"]])
        return merged
    finally:
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def run_baseline() -> int:
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_relogin_base_"))
    zip_path = tmp_zip_dir / "repo.zip"
    root = None
    try:
        create_archive_zip(zip_path)
        root = open_replica(zip_path)
        code, fails, skipped = run_unittest(root)
        print(f"Baseline: exit={code}, fails={len(fails)}, skipped={skipped}")
        return 0 if (code == 0 and skipped == 0) else 1
    finally:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(tmp_zip_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="手机页第四组变异测试")
    ap.add_argument("--list", action="store_true", help="只列清单并核对定位")
    ap.add_argument("--baseline", action="store_true", help="跑未变异副本基线")
    ap.add_argument("--ids", default="", help="只跑指定编号（逗号分隔）")
    ap.add_argument("--workers", type=int, default=4, help="并行副本数（最大 4）")
    ap.add_argument("--phase", default="补测之前", help="报告阶段标题")
    ap.add_argument("--equiv-json", default="", help="等价判定 JSON 文件路径")
    ap.add_argument("--out", default="", help="输出 Markdown 路径")
    args = ap.parse_args(argv)
    orig_texts = {
        rel: (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        for rel in TARGET_FILES
    }
    if args.list:
        return list_mutations(func_ranges(), orig_texts)
    if args.baseline:
        return run_baseline()
    wanted = {s.strip() for s in args.ids.split(",") if s.strip()}
    selected = [m for m in MUTATIONS if not wanted or m[0] in wanted]
    if not selected:
        print("没有匹配的编号", file=sys.stderr)
        return 1
    equiv = json.loads(Path(args.equiv_json).read_text(encoding="utf-8")) if args.equiv_json else {}
    results = run_parallel(selected, args.workers)
    md = format_report(results, args.phase, equiv)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8", newline="\n")
        print(f"Wrote {args.out} ({len(results)} mutations)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
