#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页第四组收尾（「外壳与接线」）7 个函数的六类单点变异与行为测试判定。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py --list
  python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py --baseline
  python design/evidence/2026-11-23/phone-shell-net/scripts/mutate_shell.py --workers 4 --out design/evidence/2026-11-23/phone-shell-net/before.md

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
TARGET_FILES = ("local/ui/m/ui-shell.js",)
ALL_FUNCTIONS = (
    "sheetBusy",
    "openSheet",
    "closeSheet",
    "showSheetError",
    "askConfirm",
    "onConfirmYes",
    "wire",
)
TEST_REL = Path("local/tests/test_phone_ui.py")
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

MUTATIONS: tuple[tuple[str, str, str, str, int, str, str], ...] = (
    # sheetBusy (1)
    ("M001", "乙", "local/ui/m/ui-shell.js", "sheetBusy", 1,
     'if (flow && String(flow.mode || "") === "auto")',
     'if (!(flow && String(flow.mode || "") === "auto"))'),
    # openSheet (17)
    ("M002", "乙", "local/ui/m/ui-shell.js", "openSheet", 1,
     "if (!root || !SHEET_TITLES[id] || model.sheetId)",
     "if (!(!root || !SHEET_TITLES[id] || model.sheetId))"),
    ("M003", "甲", "local/ui/m/ui-shell.js", "openSheet", 1,
     "model.sheetOpener = document.activeElement || null;", "void 0;"),
    ("M004", "甲", "local/ui/m/ui-shell.js", "openSheet", 1,
     "model.sheetId = id;", "void 0;"),
    ("M005", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("sheet-err").hidden = true;', "void 0;"),
    ("M006", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("more-panel").hidden = id !== "more";', "void 0;"),
    ("M007", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("review-panel").hidden = id !== "review";', "void 0;"),
    ("M008", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("confirm-panel").hidden = id !== "confirm";', "void 0;"),
    ("M009", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("relogin-panel").hidden = id !== "relogin";', "void 0;"),
    ("M010", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("review-foot").hidden = id !== "review";', "void 0;"),
    ("M011", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("relogin-foot").hidden = id !== "relogin";', "void 0;"),
    ("M012", "己", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("sheet-title").textContent = id === "relogin"\n'
     '    ? PhoneModel.loginCopy(model.relFirstLogin ? "never" : "expired", false).reloginEntry\n'
     '    : SHEET_TITLES[id];',
     "void 0;"),
    ("M013", "乙", "local/ui/m/ui-shell.js", "openSheet", 1,
     'id === "relogin"\n    ?', '!(id === "relogin")\n    ?'),
    ("M014", "乙", "local/ui/m/ui-shell.js", "openSheet", 1,
     "model.relFirstLogin ?", "!(model.relFirstLogin) ?"),
    ("M015", "乙", "local/ui/m/ui-shell.js", "openSheet", 1,
     'if (id === "more")', 'if (!(id === "more"))'),
    ("M016", "己", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("btn-relogin-open").textContent = PhoneModel.loginCopy(PhoneModel.loginState(model.login), false).reloginEntry;',
     "void 0;"),
    ("M017", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     '$("btn-sheet-close").hidden = sheetBusy();', "void 0;"),
    ("M018", "丙", "local/ui/m/ui-shell.js", "openSheet", 1,
     "root.hidden = false;", "void 0;"),
    # closeSheet (18)
    ("M019", "乙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "if (!root || !model.sheetId)", "if (!(!root || !model.sheetId))"),
    ("M020", "乙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "if (!force && sheetBusy())", "if (!(!force && sheetBusy()))"),
    ("M021", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("btn-sheet-close").hidden = true;', "void 0;"),
    ("M022", "甲", "local/ui/m/ui-shell.js", "closeSheet", 1,
     'model.sheetId = "";', "void 0;"),
    ("M023", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "root.hidden = true;", "void 0;"),
    ("M024", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("more-panel").hidden = true;', "void 0;"),
    ("M025", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("review-panel").hidden = true;', "void 0;"),
    ("M026", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("confirm-panel").hidden = true;', "void 0;"),
    ("M027", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("relogin-panel").hidden = true;', "void 0;"),
    ("M028", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("review-foot").hidden = true;', "void 0;"),
    ("M029", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("relogin-foot").hidden = true;', "void 0;"),
    ("M030", "丙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     '$("sheet-err").hidden = true;', "void 0;"),
    ("M031", "乙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     'if (el) el.value = "";', 'if (!(el)) el.value = "";'),
    ("M032", "己", "local/ui/m/ui-shell.js", "closeSheet", 1,
     'if (el) el.value = "";', "if (el) void 0;"),
    ("M033", "甲", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "model.confirm = null;", "void 0;"),
    ("M034", "甲", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "model.relConfirm = false;", "void 0;"),
    ("M035", "甲", "local/ui/m/ui-shell.js", "closeSheet", 1,
     "model.sheetOpener = null;", "void 0;"),
    ("M036", "乙", "local/ui/m/ui-shell.js", "closeSheet", 1,
     'if (opener && typeof opener.focus === "function")',
     'if (!(opener && typeof opener.focus === "function"))'),
    # showSheetError (3)
    ("M037", "乙", "local/ui/m/ui-shell.js", "showSheetError", 1,
     "if (!model.sheetId)", "if (!(!model.sheetId))"),
    ("M038", "己", "local/ui/m/ui-shell.js", "showSheetError", 1,
     'el.textContent = String(text || "");', "void 0;"),
    ("M039", "丙", "local/ui/m/ui-shell.js", "showSheetError", 1,
     "el.hidden = !text;", "void 0;"),
    # askConfirm (8)
    ("M040", "乙", "local/ui/m/ui-shell.js", "askConfirm", 1,
     "if (!view || model.sheetId)", "if (!(!view || model.sheetId))"),
    ("M041", "甲", "local/ui/m/ui-shell.js", "askConfirm", 1,
     "model.confirm = { kind: kind, taskId: taskId };", "void 0;"),
    ("M042", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("sheet-title").textContent = view.title;', "void 0;"),
    ("M043", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("confirm-text").textContent = view.text;', "void 0;"),
    ("M044", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("btn-confirm-no").textContent = view.no;', "void 0;"),
    ("M045", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("btn-confirm-yes").textContent = view.yes;', "void 0;"),
    ("M046", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("btn-confirm-no").disabled = false;', "void 0;"),
    ("M047", "己", "local/ui/m/ui-shell.js", "askConfirm", 1,
     '$("btn-confirm-yes").disabled = false;', "void 0;"),
    # onConfirmYes (9)
    ("M048", "乙", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     'kind === "cancelstart" ?', '!(kind === "cancelstart") ?'),
    ("M049", "乙", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     'kind === "stop" ?', '!(kind === "stop") ?'),
    ("M050", "乙", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     'kind === "cancelTask" ?', '!(kind === "cancelTask") ?'),
    ("M051", "乙", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     "if (!run)", "if (!(!run))"),
    ("M052", "己", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     '$("btn-confirm-yes").disabled = true;', "void 0;"),
    ("M053", "己", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     '$("btn-confirm-no").disabled = true;', "void 0;"),
    ("M054", "乙", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     "if (ok !== false)", "if (!(ok !== false))"),
    ("M055", "己", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     '$("btn-confirm-yes").disabled = false;', "void 0;"),
    ("M056", "己", "local/ui/m/ui-shell.js", "onConfirmYes", 1,
     '$("btn-confirm-no").disabled = false;', "void 0;"),
    # wire (85)
    ("M057", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-pair").addEventListener("click", () => void pair());', "void 0;"),
    ("M058", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("pair-code").addEventListener("input", () => {\n'
     '    const el = $("pair-code");\n'
     '    const digits = String(el.value || "").replace(/\\D/g, "").slice(0, 6);\n'
     '    if (el.value !== digits) el.value = digits;\n'
     '    model.pairErr = "";\n'
     '    renderPair();\n'
     '  });',
     "void 0;"),
    ("M059", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (el.value !== digits) el.value = digits;",
     "if (!(el.value !== digits)) el.value = digits;"),
    ("M060", "己", "local/ui/m/ui-shell.js", "wire", 1,
     "if (el.value !== digits) el.value = digits;",
     "if (el.value !== digits) void 0;"),
    ("M061", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     'model.pairErr = "";', "void 0;"),
    ("M062", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("pair-code").addEventListener("keydown", (event) => {\n'
     '    if (event && event.key === "Enter") void pair();\n'
     '  });',
     "void 0;"),
    ("M063", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if (event && event.key === "Enter")',
     'if (!(event && event.key === "Enter"))'),
    ("M064", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-refresh").addEventListener("click", () => void poll(true));', "void 0;"),
    ("M065", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-offline-retry").addEventListener("click", () => void poll(true));', "void 0;"),
    ("M066", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-pair-ok").addEventListener("click", () => {\n'
     '    model.pairOkPending = false;\n'
     '    renderAlerts(PhoneModel.isStale(model.lastOkAt, model.nowMs));\n'
     '  });',
     "void 0;"),
    ("M067", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.pairOkPending = false;", "void 0;"),
    ("M068", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-more").addEventListener("click", () => openSheet("more"));', "void 0;"),
    ("M069", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-sheet-close").addEventListener("click", () => closeSheet());', "void 0;"),
    ("M070", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("sheet-root").addEventListener("click", (event) => {\n'
     '    if (event && event.target === event.currentTarget) closeSheet();\n'
     '  });',
     "void 0;"),
    ("M071", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (event && event.target === event.currentTarget)",
     "if (!(event && event.target === event.currentTarget))"),
    ("M072", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'document.addEventListener("keydown", (event) => {\n'
     '    if (event && event.key === "Escape") closeSheet();\n'
     '  });',
     "void 0;"),
    ("M073", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if (event && event.key === "Escape")',
     'if (!(event && event.key === "Escape"))'),
    ("M074", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-start").addEventListener("click", () => {\n'
     '    if (PhoneModel.loginExpired(model.login) && !model.busy\n'
     '        && !(model.pending && !model.pending.done)) openRelogin();\n'
     '    else openReview();\n'
     '  });',
     "void 0;"),
    ("M075", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (PhoneModel.loginExpired(model.login) && !model.busy\n"
     "        && !(model.pending && !model.pending.done))",
     "if (!(PhoneModel.loginExpired(model.login) && !model.busy\n"
     "        && !(model.pending && !model.pending.done)))"),
    ("M076", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-banner-relogin").addEventListener("click", () => openRelogin());', "void 0;"),
    ("M077", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-review-start").addEventListener("click", () => { closeSheet(true); void startPlan(); });', "void 0;"),
    ("M078", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-review-back").addEventListener("click", () => closeSheet());', "void 0;"),
    ("M079", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("review-items").addEventListener("click", (event) => {\n'
     '    const id = event && event.target && event.target.dataset\n'
     '      ? String(event.target.dataset.id || "") : "";\n'
     '    if (id) removeFromReview(id);\n'
     '  });',
     "void 0;"),
    ("M080", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "event && event.target && event.target.dataset\n      ?",
     "!(event && event.target && event.target.dataset)\n      ?"),
    ("M081", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (id) removeFromReview(id);", "if (!(id)) removeFromReview(id);"),
    ("M082", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-stop").addEventListener("click", () => askConfirm("stop"));', "void 0;"),
    ("M083", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-cancel-start").addEventListener("click", () => askConfirm("cancelstart"));', "void 0;"),
    ("M084", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-confirm-no").addEventListener("click", () => closeSheet());', "void 0;"),
    ("M085", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-confirm-yes").addEventListener("click", () => onConfirmYes());', "void 0;"),
    ("M086", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-reselect").addEventListener("click", () => reselectFailed());', "void 0;"),
    ("M087", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-finish").addEventListener("click", () => finishPlanView());', "void 0;"),
    ("M088", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-toggle-list").addEventListener("click", () => {\n'
     '    model.listOpen = !model.listOpen;\n'
     '    renderItems();\n'
     '  });',
     "void 0;"),
    ("M089", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.listOpen = !model.listOpen;", "void 0;"),
    ("M090", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if ($("btn-show-window"))', 'if (!($("btn-show-window")))'),
    ("M091", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-show-window").addEventListener("click", () => void showComputerWindow());', "void 0;"),
    ("M092", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-open").addEventListener("click", () => openRelogin());', "void 0;"),
    ("M093", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin").addEventListener("click", () => void beginRelogin());', "void 0;"),
    ("M094", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-auto").addEventListener("click", () => void beginRelogin());', "void 0;"),
    ("M095", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-submit").addEventListener("click", () => void submitRelogin());', "void 0;"),
    ("M096", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-cancel").addEventListener("click", async () => {\n'
     '    model.relConfirm = false;\n'
     '    /* 取消成立（或本来就没有在途流程）才收 sheet；撤不掉就留着重试 */\n'
     '    const ok = await cancelRelogin();\n'
     '    if (ok !== false) closeSheet(true);\n'
     '  });',
     "void 0;"),
    ("M097", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.relConfirm = false;", "void 0;"),
    ("M098", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (ok !== false) closeSheet(true);", "if (!(ok !== false)) closeSheet(true);"),
    ("M099", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-refresh").addEventListener("click", () => void refreshRelogin());', "void 0;"),
    ("M100", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-relogin-done").addEventListener("click", () => closeSheet());', "void 0;"),
    ("M101", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$(id).addEventListener("input", () => refreshControls());', "void 0;"),
    ("M102", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("q").addEventListener("input", () => {\n'
     '    model.filter.q = $("q").value;\n'
     '    if ($("search-q")) $("search-q").value = $("q").value;\n'
     '    renderItems();\n'
     '  });',
     "void 0;"),
    ("M103", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     'model.filter.q = $("q").value;', "void 0;"),
    ("M104", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if ($("search-q")) $("search-q").value = $("q").value;',
     'if (!($("search-q"))) $("search-q").value = $("q").value;'),
    ("M105", "己", "local/ui/m/ui-shell.js", "wire", 1,
     'if ($("search-q")) $("search-q").value = $("q").value;',
     'if ($("search-q")) void 0;'),
    ("M106", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-search").addEventListener("click", () => toggleSearch());', "void 0;"),
    ("M107", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("search-q").addEventListener("input", () => {\n'
     '    model.filter.q = $("search-q").value;\n'
     '    if ($("q")) $("q").value = $("search-q").value;\n'
     '    renderItems();\n'
     '  });',
     "void 0;"),
    ("M108", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     'model.filter.q = $("search-q").value;', "void 0;"),
    ("M109", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if ($("q")) $("q").value = $("search-q").value;',
     'if (!($("q"))) $("q").value = $("search-q").value;'),
    ("M110", "己", "local/ui/m/ui-shell.js", "wire", 1,
     'if ($("q")) $("q").value = $("search-q").value;',
     'if ($("q")) void 0;'),
    ("M111", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("btn-pick-next").addEventListener("click", () => {\n'
     '    if (!model.pickId) return;\n'
     '    const res = PhoneModel.pickItem(model.selected, model.items, model.pickId, true);\n'
     '    model.selected = res.selected;\n'
     '    model.notice = res.notice;\n'
     '    renderItems();\n'
     '  });',
     "void 0;"),
    ("M112", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (!model.pickId) return;", "if (!(!model.pickId)) return;"),
    ("M113", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.selected = res.selected;", "void 0;"),
    ("M114", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.notice = res.notice;", "void 0;"),
    ("M115", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'btn.addEventListener("click", () => {\n'
     '      model.filter.status = btn.dataset.status;\n'
     '      document.querySelectorAll("[data-status]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));\n'
     '      renderItems();\n'
     '    });',
     "void 0;"),
    ("M116", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.filter.status = btn.dataset.status;", "void 0;"),
    ("M117", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'document.querySelectorAll("[data-status]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));',
     'document.querySelectorAll("[data-status]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", !(other === btn) ? "true" : "false"));'),
    ("M118", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'btn.addEventListener("click", () => {\n'
     '      model.filter.time = btn.dataset.time;\n'
     '      document.querySelectorAll("[data-time]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));\n'
     '      renderItems();\n'
     '    });',
     "void 0;"),
    ("M119", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "model.filter.time = btn.dataset.time;", "void 0;"),
    ("M120", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'document.querySelectorAll("[data-time]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", other === btn ? "true" : "false"));',
     'document.querySelectorAll("[data-time]").forEach((other) =>\n'
     '        other.setAttribute("aria-pressed", !(other === btn) ? "true" : "false"));'),
    ("M121", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("retry-for").addEventListener("change", () => {\n'
     '    model.retry.retry_for_s = Number($("retry-for").value);\n'
     '    model.retryDirty = true;\n'
     '    void saveRetry();\n'
     '    refreshControls();\n'
     '  });',
     "void 0;"),
    ("M122", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     'model.retry.retry_for_s = Number($("retry-for").value);', "void 0;"),
    ("M123", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     '    model.retry.retry_for_s = Number($("retry-for").value);\n'
     '    model.retryDirty = true;',
     '    model.retry.retry_for_s = Number($("retry-for").value);\n'
     '    void 0;'),
    ("M124", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     '$("max-attempts").addEventListener("change", () => {\n'
     '    model.retry.max_attempts = Number($("max-attempts").value || 0);\n'
     '    model.retryDirty = true;\n'
     '    void saveRetry();\n'
     '  });',
     "void 0;"),
    ("M125", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     'model.retry.max_attempts = Number($("max-attempts").value || 0);', "void 0;"),
    ("M126", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     '    model.retry.max_attempts = Number($("max-attempts").value || 0);\n'
     '    model.retryDirty = true;',
     '    model.retry.max_attempts = Number($("max-attempts").value || 0);\n'
     '    void 0;'),
    ("M127", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'document.addEventListener("visibilitychange", () => {\n'
     '    if (document.hidden) {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      model.pollTimer = null;\n'
     '      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表\n'
     '      model.tickTimer = null;\n'
     '    } else if (model.paired) {\n'
     '      void poll(false);       // 回前台立刻补一次，仍按事件游标补齐\n'
     '    }\n'
     '  });',
     "void 0;"),
    ("M128", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (document.hidden)", "if (!(document.hidden))"),
    ("M129", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     '  document.addEventListener("visibilitychange", () => {\n'
     '    if (document.hidden) {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);',
     '  document.addEventListener("visibilitychange", () => {\n'
     '    if (document.hidden) {\n'
     '      if (!(model.pollTimer)) clearTimeout(model.pollTimer);'),
    ("M130", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      model.pollTimer = null;\n'
     '      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表',
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      void 0;\n'
     '      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表'),
    ("M131", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表",
     "if (!(model.tickTimer)) clearTimeout(model.tickTimer);   // P1：后台停表"),
    ("M132", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     "      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表\n"
     "      model.tickTimer = null;",
     "      if (model.tickTimer) clearTimeout(model.tickTimer);   // P1：后台停表\n"
     "      void 0;"),
    ("M133", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "else if (model.paired)", "else if (!(model.paired))"),
    ("M134", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     'if (typeof window !== "undefined" && typeof window.addEventListener === "function")',
     'if (!(typeof window !== "undefined" && typeof window.addEventListener === "function"))'),
    ("M135", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'window.addEventListener("pagehide", () => {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      model.pollTimer = null;\n'
     '      if (model.tickTimer) clearTimeout(model.tickTimer);\n'
     '      model.tickTimer = null;\n'
     '    });',
     "void 0;"),
    ("M136", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     '    window.addEventListener("pagehide", () => {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);',
     '    window.addEventListener("pagehide", () => {\n'
     '      if (!(model.pollTimer)) clearTimeout(model.pollTimer);'),
    ("M137", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     '    window.addEventListener("pagehide", () => {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      model.pollTimer = null;',
     '    window.addEventListener("pagehide", () => {\n'
     '      if (model.pollTimer) clearTimeout(model.pollTimer);\n'
     '      void 0;'),
    ("M138", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     '      if (model.tickTimer) clearTimeout(model.tickTimer);\n'
     '      model.tickTimer = null;\n'
     '    });',
     '      if (!(model.tickTimer)) clearTimeout(model.tickTimer);\n'
     '      model.tickTimer = null;\n'
     '    });'),
    ("M139", "甲", "local/ui/m/ui-shell.js", "wire", 1,
     '      if (model.tickTimer) clearTimeout(model.tickTimer);\n'
     '      model.tickTimer = null;\n'
     '    });',
     '      if (model.tickTimer) clearTimeout(model.tickTimer);\n'
     '      void 0;\n'
     '    });'),
    ("M140", "庚", "local/ui/m/ui-shell.js", "wire", 1,
     'window.addEventListener("pageshow", () => {\n'
     '      if (!document.hidden && model.paired) void poll(false); // bfcache 恢复后按游标补齐\n'
     '    });',
     "void 0;"),
    ("M141", "乙", "local/ui/m/ui-shell.js", "wire", 1,
     "if (!document.hidden && model.paired)",
     "if (!(!document.hidden && model.paired))"),
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
    root = Path(tempfile.mkdtemp(prefix="phone_shell_mut_"))
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
    kinds = ("甲", "乙", "丙", "戊", "己", "庚")
    counts = {k: 0 for k in cats}
    by_kind = {knd: {k: 0 for k in cats} for knd in kinds}
    by_func = {fn: {"kinds": {knd: 0 for knd in kinds}, "cats": {k: 0 for k in cats}, "total": 0} for fn in ALL_FUNCTIONS}
    lines = [
        f"# 第五组（外壳与接线）变异结论（{phase}）",
        "",
        (
            f"- 范围：`local/ui/m/ui-shell.js` 的 7 个顶层函数（共 {len(results)} 条）："
            f"甲类（`model.字段` 写换 `void 0`）{sum(1 for r in results if r['kind']=='甲')} 条、"
            f"乙类（条件 `C` 换 `!(C)`）{sum(1 for r in results if r['kind']=='乙')} 条、"
            f"丙类（`.hidden = X` 写换 `void 0`）{sum(1 for r in results if r['kind']=='丙')} 条、"
            f"戊类（`return true`/`false` 互换）{sum(1 for r in results if r['kind']=='戊')} 条、"
            f"己类（`.textContent`/`.value`/`.disabled` 写换 `void 0`）{sum(1 for r in results if r['kind']=='己')} 条、"
            f"庚类（`addEventListener` 绑定整条换 `void 0`）{sum(1 for r in results if r['kind']=='庚')} 条。"
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
        "戊": "戊类（`return true`/`false` 互换）",
        "己": "己类（`.textContent`/`.value`/`.disabled` 写换 `void 0`）",
        "庚": "庚类（`addEventListener` 绑定整条换 `void 0`）",
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
        "| 函数 | 口径（甲 / 乙 / 丙 / 戊 / 己 / 庚） | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
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
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_shell_zip_"))
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
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_shell_base_"))
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
    ap = argparse.ArgumentParser(description="手机页外壳与接线组变异测试")
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
