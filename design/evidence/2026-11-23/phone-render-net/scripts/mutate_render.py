#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手机页第二组（摄入与渲染）23 个函数的单点变异与行为测试判定。

用法（仓库根，Python 3.12）：
  python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py --list
  python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py --baseline
  python design/evidence/2026-11-23/phone-render-net/scripts/mutate_render.py --workers 4 --out design/evidence/2026-11-23/phone-render-net/before.md

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
TARGET_FILES = (
    "local/ui/m/ui-status.js",
    "local/ui/m/ui-list.js",
    "local/ui/m/ui-sync.js",
)
TEST_REL = Path("local/tests/test_phone_ui.py")
JSSCAN_MJS = REPO / "tools" / "code_shape" / "jsscan.mjs"
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy")

MUTATIONS: tuple[tuple[str, str, str, str, int, str, str], ...] = (
    ('M001', '甲', 'local/ui/m/ui-status.js', 'setBanner', 1, 'model.bannerKind = text ? String(kind || "info") : "";', 'void 0;'),
    ('M002', '乙', 'local/ui/m/ui-status.js', 'setBanner', 1, 'text ?', '!(text) ?'),
    ('M003', '丙', 'local/ui/m/ui-status.js', 'setBanner', 1, 'el.hidden = !text;', 'void 0;'),
    ('M004', '乙', 'local/ui/m/ui-status.js', 'clearStaleBanner', 1, 'if (model.bannerKind === "stale_action")', 'if (!(model.bannerKind === "stale_action"))'),
    ('M005', '乙', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'if (!stale)', 'if (!(!stale))'),
    ('M006', '丙', 'local/ui/m/ui-status.js', 'syncOffline', 1, '  if (!stale) {\n    note.hidden = true;', '  if (!stale) {\n    void 0;'),
    ('M007', '甲', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'model.offlineTries = 0;', 'void 0;'),
    ('M008', '乙', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'if (PhoneModel.connState(model, false).state !== "off")', 'if (!(PhoneModel.connState(model, false).state !== "off"))'),
    ('M009', '丙', 'local/ui/m/ui-status.js', 'syncOffline', 1, '  if (PhoneModel.connState(model, false).state !== "off") {\n    note.hidden = true;', '  if (PhoneModel.connState(model, false).state !== "off") {\n    void 0;'),
    ('M010', '乙', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'tries > 0 ?', '!(tries > 0) ?'),
    ('M011', '乙', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'model.flying ?', '!(model.flying) ?'),
    ('M012', '丙', 'local/ui/m/ui-status.js', 'syncOffline', 1, 'note.hidden = false;', 'void 0;'),
    ('M013', '丙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, '$("terms-alert").hidden = !(!off && terms);', 'void 0;'),
    ('M014', '丙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, '$("login-expired-banner").hidden = !(!off && !terms && expired);', 'void 0;'),
    ('M015', '丙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, '$("pclist-alert").hidden = !(!off && !terms && !expired && pcList);', 'void 0;'),
    ('M016', '乙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, 'if (!$("pclist-alert").hidden)', 'if (!(!$("pclist-alert").hidden))'),
    ('M017', '乙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, 'when\n      ?', '!(when)\n      ?'),
    ('M018', '丙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, '$("pcclock-alert").hidden = !(!off && !terms && !expired && !pcList && clockDown);', 'void 0;'),
    ('M019', '丙', 'local/ui/m/ui-status.js', 'renderAlerts', 1, '$("pair-ok-alert").hidden = !(!off && !terms && !expired && !pcList && !clockDown\n    && model.pairOkPending);', 'void 0;'),
    ('M020', '甲', 'local/ui/m/ui-status.js', 'canWrite', 1, 'model.nowMs = Date.now();', 'void 0;'),
    ('M021', '甲', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'model.nowMs = Date.now();', 'void 0;'),
    ('M022', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, '$("stale-note").hidden = !stale;', 'void 0;'),
    ('M023', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, '$("btn-stop").hidden = !model.busy;', 'void 0;'),
    ('M024', '乙', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'model.reloginSetup\n        ?', '!(model.reloginSetup)\n        ?'),
    ('M025', '乙', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'if (account)', 'if (!(account))'),
    ('M026', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'account.hidden = setup ? !PhoneModel.relNeedAcct(model.flow, setup) : true;', 'void 0;'),
    ('M027', '乙', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'setup ?', '!(setup) ?'),
    ('M028', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, '$("btn-cancel-start").hidden = !(model.pending && !model.pending.done);', 'void 0;'),
    ('M029', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, '$("review-policy").hidden = !hint;', 'void 0;'),
    ('M030', '乙', 'local/ui/m/ui-status.js', 'refreshControls', 1, 'if (model.sheetId)', 'if (!(model.sheetId))'),
    ('M031', '丙', 'local/ui/m/ui-status.js', 'refreshControls', 1, '$("btn-sheet-close").hidden = sheetBusy();', 'void 0;'),
    ('M032', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'bar.hidden = false;', 'void 0;'),
    ('M033', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'result ?', '!(result) ?'),
    ('M034', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("bar-info").hidden = !!result;', 'void 0;'),
    ('M035', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-reselect").hidden = !result || !result.canRetry;', 'void 0;'),
    ('M036', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-finish").hidden = !result;', 'void 0;'),
    ('M037', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'if (result)', 'if (!(result))'),
    ('M038', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-start").hidden = true;', 'void 0;'),
    ('M039', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-cancel-start").hidden = true;', 'void 0;'),
    ('M040', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'if (model.busy)', 'if (!(model.busy))'),
    ('M041', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'model.plan && String(model.plan.source || "") === "phone"\n      ?', '!(model.plan && String(model.plan.source || "") === "phone")\n      ?'),
    ('M042', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'if (model.pending && !model.pending.done)', 'if (!(model.pending && !model.pending.done))'),
    ('M043', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'PhoneModel.pendingLong(model.pending, Date.now())\n      ?', '!(PhoneModel.pendingLong(model.pending, Date.now()))\n      ?'),
    ('M044', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'if (model.pcListError)', 'if (!(model.pcListError))'),
    ('M045', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'bar.hidden = true;', 'void 0;'),
    ('M046', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-start").hidden = false;', 'void 0;'),
    ('M047', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'model.termsOk === false\n      ?', '!(model.termsOk === false)\n      ?'),
    ('M048', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'recoveringSub ?', '!(recoveringSub) ?'),
    ('M049', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'expiredSub ?', '!(expiredSub) ?'),
    ('M050', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'model.clockState === "unavailable"                   // EX06（Phone:865）\n                    ?', '!(model.clockState === "unavailable")                   // EX06（Phone:865）\n                    ?'),
    ('M051', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'PhoneModel.connState(model, model.flying).state === "off"  // UI-F3：离线不冒充「已选 N 场，可开始」\n                       ?', '!(PhoneModel.connState(model, model.flying).state === "off")  // UI-F3：离线不冒充「已选 N 场，可开始」\n                       ?'),
    ('M052', '乙', 'local/ui/m/ui-status.js', 'renderBar', 1, 'expired && !model.busy\n    && !(model.pending && !model.pending.done) ?', '!(expired && !model.busy\n    && !(model.pending && !model.pending.done)) ?'),
    ('M053', '丙', 'local/ui/m/ui-status.js', 'renderBar', 1, '$("btn-start").hidden = model.busy;', 'void 0;'),
    ('M054', '乙', 'local/ui/m/ui-status.js', 'renderRail', 1, 'if (!box)', 'if (!(!box))'),
    ('M055', '丙', 'local/ui/m/ui-status.js', 'renderRail', 1, 'box.hidden = !steps.length;', 'void 0;'),
    ('M056', '乙', 'local/ui/m/ui-status.js', 'renderRail', 1, 'if (step.state)', 'if (!(step.state))'),
    ('M057', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (!section)', 'if (!(!section))'),
    ('M058', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (model.busy)', 'if (!(model.busy))'),
    ('M059', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (pendingNow)', 'if (!(pendingNow))'),
    ('M060', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '    board = PhoneModel.pendingBoard(model.pending, Date.now());\n  } else if (result)', '    board = PhoneModel.pendingBoard(model.pending, Date.now());\n  } else if (!(result))'),
    ('M061', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (model.termsOk === false)', 'if (!(model.termsOk === false))'),
    ('M062', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'section.hidden = !board;', 'void 0;'),
    ('M063', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'result && result.boardCls ?', '!(result && result.boardCls) ?'),
    ('M064', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (!board)', 'if (!(!board))'),
    ('M065', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'board.tagTone ?', '!(board.tagTone) ?'),
    ('M066', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'nowLine.hidden = false;', 'void 0;'),
    ('M067', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'nowS !== null\n    ?', '!(nowS !== null)\n    ?'),
    ('M068', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '$("board-led-wrap").hidden = !!result;', 'void 0;'),
    ('M069', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '$("board-cap").hidden = !!result;', 'void 0;'),
    ('M070', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '$("board-stats").hidden = !result;', 'void 0;'),
    ('M071', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '  $("board-sub").textContent = board.sub;\n  if (result)', '  $("board-sub").textContent = board.sub;\n  if (!(result))'),
    ('M072', '甲', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'model.pickId = "";', 'void 0;'),
    ('M073', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '$("btn-pick-next").hidden = true;', 'void 0;'),
    ('M074', '乙', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'if (d.cls)', 'if (!(d.cls))'),
    ('M075', '甲', 'local/ui/m/ui-status.js', 'renderBoard', 1, 'model.pickId = board.pickId || "";', 'void 0;'),
    ('M076', '丙', 'local/ui/m/ui-status.js', 'renderBoard', 1, '$("btn-pick-next").hidden = !board.pickId;', 'void 0;'),
    ('M077', '乙', 'local/ui/m/ui-status.js', 'renderStats', 1, 'if (n.tone)', 'if (!(n.tone))'),
    ('M078', '丙', 'local/ui/m/ui-status.js', 'renderPlan', 1, 'tip.hidden = !model.busy;', 'void 0;'),
    ('M079', '乙', 'local/ui/m/ui-status.js', 'renderTasks', 1, 'if (!box)', 'if (!(!box))'),
    ('M080', '丙', 'local/ui/m/ui-status.js', 'renderTasks', 1, 'box.hidden = !(model.busy || PhoneModel.resultView(model.plan, model.busy)) || !tasks.length;', 'void 0;'),
    ('M081', '乙', 'local/ui/m/ui-status.js', 'renderTasks', 1, 'if (box.hidden)', 'if (!(box.hidden))'),
    ('M082', '乙', 'local/ui/m/ui-status.js', 'renderTasks', 1, 'card.tone ?', '!(card.tone) ?'),
    ('M083', '乙', 'local/ui/m/ui-status.js', 'renderTasks', 1, 'if (card.canCancel)', 'if (!(card.canCancel))'),
    ('M084', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'row.cls ?', '!(row.cls) ?'),
    ('M085', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'model.flashId === row.id ?', '!(model.flashId === row.id) ?'),
    ('M086', '甲', 'local/ui/m/ui-list.js', 'buildRow', 1, 'model.selected = res.selected;', 'void 0;'),
    ('M087', '甲', 'local/ui/m/ui-list.js', 'buildRow', 1, 'model.notice = res.notice;', 'void 0;'),
    ('M088', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.timeCls)', 'if (!(row.timeCls))'),
    ('M089', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.hasLeft)', 'if (!(row.hasLeft))'),
    ('M090', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.leftCls)', 'if (!(row.leftCls))'),
    ('M091', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'f.cls ?', '!(f.cls) ?'),
    ('M092', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, '  });\n  if (row.clash)', '  });\n  if (!(row.clash))'),
    ('M093', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.act)', 'if (!(row.act))'),
    ('M094', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.hasRf)', 'if (!(row.hasRf))'),
    ('M095', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'row.rfNo ?', '!(row.rfNo) ?'),
    ('M096', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.hasPlace)', 'if (!(row.hasPlace))'),
    ('M097', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.rw && row.rw.text)', 'if (!(row.rw && row.rw.text))'),
    ('M098', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.hasWarn)', 'if (!(row.hasWarn))'),
    ('M099', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (row.note)', 'if (!(row.note))'),
    ('M100', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, '  /* 重叠行：点按这一行展开 / 收起原因，一次只开一条（面板在行内占满整行宽） */\n  if (row.clash)', '  /* 重叠行：点按这一行展开 / 收起原因，一次只开一条（面板在行内占满整行宽） */\n  if (!(row.clash))'),
    ('M101', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (event && event.preventDefault)', 'if (!(event && event.preventDefault))'),
    ('M102', '乙', 'local/ui/m/ui-list.js', 'buildRow', 1, 'if (model.whyId === row.id)', 'if (!(model.whyId === row.id))'),
    ('M103', '乙', 'local/ui/m/ui-list.js', 'buildWhy', 1, 'if (view.hasGo)', 'if (!(view.hasGo))'),
    ('M104', '乙', 'local/ui/m/ui-list.js', 'buildWhy', 1, 'if (event && event.stopPropagation)', 'if (!(event && event.stopPropagation))'),
    ('M105', '甲', 'local/ui/m/ui-list.js', 'goSigned', 1, 'model.whyId = "";', 'void 0;'),
    ('M106', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if (!shown)', 'if (!(!shown))'),
    ('M107', '甲', 'local/ui/m/ui-list.js', 'goSigned', 1, 'model.filter = { q: "", status: "all", time: "all" };', 'void 0;'),
    ('M108', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if ($("q"))', 'if (!($("q")))'),
    ('M109', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if ($("search-q"))', 'if (!($("search-q")))'),
    ('M110', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'b.dataset.status === "all" ?', '!(b.dataset.status === "all") ?'),
    ('M111', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'b.dataset.time === "all" ?', '!(b.dataset.time === "all") ?'),
    ('M112', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if ($("signed-summary"))', 'if (!($("signed-summary")))'),
    ('M113', '甲', 'local/ui/m/ui-list.js', 'goSigned', 1, 'model.flashId = id;', 'void 0;'),
    ('M114', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if (row && row.scrollIntoView)', 'if (!(row && row.scrollIntoView))'),
    ('M115', '甲', 'local/ui/m/ui-list.js', 'goSigned', 1, 'model.flashId = "";', 'void 0;'),
    ('M116', '乙', 'local/ui/m/ui-list.js', 'goSigned', 1, 'if (row && row.classList)', 'if (!(row && row.classList))'),
    ('M117', '甲', 'local/ui/m/ui-list.js', 'renderItems', 1, 'model.nowMs = Date.now();', 'void 0;'),
    ('M118', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if (!box)', 'if (!(!box))'),
    ('M119', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if (!inListZone(zone, group.title))', 'if (!(!inListZone(zone, group.title)))'),
    ('M120', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if (group.nowBefore && group.now)', 'if (!(group.nowBefore && group.now))'),
    ('M121', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'group.cls ?', '!(group.cls) ?'),
    ('M122', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if ($("signed-count"))', 'if (!($("signed-count")))'),
    ('M123', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("fbar").hidden = !showList;', 'void 0;'),
    ('M124', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("search-view").hidden = !showList || !model.searchOpen;', 'void 0;'),
    ('M125', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'toggle.hidden = !(model.busy || result);', 'void 0;'),
    ('M126', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, '  toggle.hidden = !(model.busy || result);\n  toggle.setAttribute("aria-expanded", model.listOpen ?', '  toggle.hidden = !(model.busy || result);\n  toggle.setAttribute("aria-expanded", !(model.listOpen) ?'),
    ('M127', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, '  toggle.setAttribute("aria-expanded", model.listOpen ? "true" : "false");\n  toggle.textContent = model.listOpen ?', '  toggle.setAttribute("aria-expanded", model.listOpen ? "true" : "false");\n  toggle.textContent = !(model.listOpen) ?'),
    ('M128', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'tip.hidden = !showList || !noMatch;', 'void 0;'),
    ('M129', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("today-items").hidden = !showList || noMatch;', 'void 0;'),
    ('M130', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if ($("upcoming-zone"))', 'if (!($("upcoming-zone")))'),
    ('M131', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("upcoming-zone").hidden = !showList || noMatch;', 'void 0;'),
    ('M132', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if ($("signed-summary"))', 'if (!($("signed-summary")))'),
    ('M133', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("signed-summary").hidden = !showList || !result;', 'void 0;'),
    ('M134', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if (result)', 'if (!(result))'),
    ('M135', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("empty").hidden = !showList || noMatch || nowS === null || zoneCount[0] > 0;', 'void 0;'),
    ('M136', '乙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'if ($("upcoming-empty"))', 'if (!($("upcoming-empty")))'),
    ('M137', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, '$("upcoming-empty").hidden = !showList || noMatch || zoneCount[1] > 0;', 'void 0;'),
    ('M138', '丙', 'local/ui/m/ui-list.js', 'renderItems', 1, 'notice.hidden = !showList || !model.notice;', 'void 0;'),
    ('M139', '甲', 'local/ui/m/ui-list.js', 'toggleSearch', 1, 'model.searchOpen = !model.searchOpen;', 'void 0;'),
    ('M140', '丙', 'local/ui/m/ui-list.js', 'toggleSearch', 1, '$("search-view").hidden = !model.searchOpen;', 'void 0;'),
    ('M141', '乙', 'local/ui/m/ui-list.js', 'toggleSearch', 1, 'model.searchOpen ?', '!(model.searchOpen) ?'),
    ('M142', '甲', 'local/ui/m/ui-list.js', 'toggleSearch', 1, 'model.filter.q = "";', 'void 0;'),
    ('M143', '乙', 'local/ui/m/ui-list.js', 'toggleSearch', 1, 'if ($("q"))', 'if (!($("q")))'),
    ('M144', '乙', 'local/ui/m/ui-list.js', 'toggleSearch', 1, 'if (model.searchOpen && $("search-q").focus)', 'if (!(model.searchOpen && $("search-q").focus))'),
    ('M145', '乙', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, 'if (model.tickTimer)', 'if (!(model.tickTimer))'),
    ('M146', '甲', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, '  if (model.tickTimer) clearTimeout(model.tickTimer);\n  model.tickTimer = null;', '  if (model.tickTimer) clearTimeout(model.tickTimer);\n  void 0;'),
    ('M147', '乙', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, 'if (typeof document !== "undefined" && document.hidden)', 'if (!(typeof document !== "undefined" && document.hidden))'),
    ('M148', '乙', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, 'if (!model.paired)', 'if (!(!model.paired))'),
    ('M149', '甲', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, 'model.tickTimer = setTimeout(() => {\n    model.tickTimer = null;\n    tickClock();\n    scheduleTick();\n  }, PhoneModel.nextTickDelay(PhoneModel.businessNowS(model)));', 'void 0;'),
    ('M150', '甲', 'local/ui/m/ui-sync.js', 'scheduleTick', 1, '  model.tickTimer = setTimeout(() => {\n    model.tickTimer = null;', '  model.tickTimer = setTimeout(() => {\n    void 0;'),
    ('M151', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (typeof document !== "undefined" && document.hidden)', 'if (!(typeof document !== "undefined" && document.hidden))'),
    ('M152', '甲', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'model.tickMark = { wall: wallMs, mono: monoMs };', 'void 0;'),
    ('M153', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (slept && model.clock)', 'if (!(slept && model.clock))'),
    ('M154', '甲', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'model.clock = null;', 'void 0;'),
    ('M155', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (model.paired)', 'if (!(model.paired))'),
    ('M156', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, '  const clockText = nowS !== null\n    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准";\n  const nowEl = $("board-now-text");', '  const clockText = !(nowS !== null)\n    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)) : "待校准";\n  const nowEl = $("board-now-text");'),
    ('M157', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (nowEl && !$("board-now").hidden && nowEl.textContent !== clockText)', 'if (!(nowEl && !$("board-now").hidden && nowEl.textContent !== clockText))'),
    ('M158', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, '  const chipText = nowS !== null\n    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : "";\n  if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {', '  const chipText = !(nowS !== null)\n    ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(nowS)).slice(0, 5) : "";\n  if (typeof document !== "undefined" && typeof document.querySelectorAll === "function") {'),
    ('M159', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (typeof document !== "undefined" && typeof document.querySelectorAll === "function")', 'if (!(typeof document !== "undefined" && typeof document.querySelectorAll === "function"))'),
    ('M160', '乙', 'local/ui/m/ui-sync.js', 'tickClock', 1, 'if (chipText && el.textContent !== chipText)', 'if (!(chipText && el.textContent !== chipText))'),
    ('M161', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (!section || section.hidden)', 'if (!(!section || section.hidden))'),
    ('M162', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (result)', 'if (!(result))'),
    ('M163', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (model.busy)', 'if (!(model.busy))'),
    ('M164', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (pendingNow)', 'if (!(pendingNow))'),
    ('M165', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (model.termsOk === false)', 'if (!(model.termsOk === false))'),
    ('M166', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (!board || !board.led)', 'if (!(!board || !board.led))'),
    ('M167', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (!wrap || wrap.hidden)', 'if (!(!wrap || wrap.hidden))'),
    ('M168', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (wrap.getAttribute("aria-label") === board.led.aria)', 'if (!(wrap.getAttribute("aria-label") === board.led.aria))'),
    ('M169', '乙', 'local/ui/m/ui-sync.js', 'tickBoardLed', 1, 'if (d.cls)', 'if (!(d.cls))'),
    ('M170', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (typeof document === "undefined")', 'if (!(typeof document === "undefined"))'),
    ('M171', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (!box || typeof box.querySelectorAll !== "function")', 'if (!(!box || typeof box.querySelectorAll !== "function"))'),
    ('M172', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (el && el.dataset)', 'if (!(el && el.dataset))'),
    ('M173', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'el && el.querySelector ?', '!(el && el.querySelector) ?'),
    ('M174', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (!small || !row.hasLeft)', 'if (!(!small || !row.hasLeft))'),
    ('M175', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (row.st === "open" && small.textContent !== "已开放")', 'if (!(row.st === "open" && small.textContent !== "已开放"))'),
    ('M176', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (small.textContent !== row.left)', 'if (!(small.textContent !== row.left))'),
    ('M177', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (String(small.className || "") !== cls)', 'if (!(String(small.className || "") !== cls))'),
    ('M178', '乙', 'local/ui/m/ui-sync.js', 'tickRowLeft', 1, 'if (crossed && model.paired)', 'if (!(crossed && model.paired))'),
    ('M179', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (payload.reset)', 'if (!(payload.reset))'),
    ('M180', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seenEventSeq.clear();', 'void 0;'),
    ('M181', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seq = 0;', 'void 0;'),
    ('M182', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (logs)', 'if (!(logs))'),
    ('M183', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.login_relay && typeof state.login_relay === "object")', 'if (!(state.login_relay && typeof state.login_relay === "object"))'),
    ('M184', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (Array.isArray(state.activities))', 'if (!(Array.isArray(state.activities)))'),
    ('M185', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.items = state.activities;', 'void 0;'),
    ('M186', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.selected = before.filter((id) => {\n      const item = model.items.find((candidate) => candidate && candidate.id === id);\n      if (!item || !PhoneModel.actionable(item, model.items)) return false;\n      const status = PhoneModel.stOf(item, businessNow);\n      return status === "open" || status === "pre";\n    });', 'void 0;'),
    ('M187', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (!item || !PhoneModel.actionable(item, model.items))', 'if (!(!item || !PhoneModel.actionable(item, model.items)))'),
    ('M188', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (model.selected.length !== before.length)', 'if (!(model.selected.length !== before.length))'),
    ('M189', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.notice = "";', 'void 0;'),
    ('M190', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.plan && String(state.plan.plan_id || "") !== model.dismissedPlanId)', 'if (!(state.plan && String(state.plan.plan_id || "") !== model.dismissedPlanId))'),
    ('M191', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.plan = state.plan;', 'void 0;'),
    ('M192', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (typeof state.terms_ok === "boolean")', 'if (!(typeof state.terms_ok === "boolean"))'),
    ('M193', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.termsOk = state.terms_ok;', 'void 0;'),
    ('M194', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.relogin_setup && typeof state.relogin_setup === "object")', 'if (!(state.relogin_setup && typeof state.relogin_setup === "object"))'),
    ('M195', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.reloginSetup = state.relogin_setup;', 'void 0;'),
    ('M196', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.business_clock && typeof state.business_clock === "object")', 'if (!(state.business_clock && typeof state.business_clock === "object"))'),
    ('M197', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.clockState = String(state.business_clock.state || "");', 'void 0;'),
    ('M198', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.clock ?', '!(model.clock) ?'),
    ('M199', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.lastOkText = sampled !== null\n      ? PhoneModel.hhmmss(PhoneModel.beijingSecOf(sampled)) : "";', 'void 0;'),
    ('M200', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'sampled !== null\n      ?', '!(sampled !== null)\n      ?'),
    ('M201', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.pcListError = state.pc_list_error || null;', 'void 0;'),
    ('M202', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (typeof state.busy === "boolean")', 'if (!(typeof state.busy === "boolean"))'),
    ('M203', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.busy = state.busy;', 'void 0;'),
    ('M204', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.retry_policy && typeof state.retry_policy === "object"\n      && !model.retryHydrated && !model.retryDirty)', 'if (!(state.retry_policy && typeof state.retry_policy === "object"\n      && !model.retryHydrated && !model.retryDirty))'),
    ('M205', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.retry = {\n      retry_for_s: Number(state.retry_policy.retry_for_s),\n      max_attempts: Number(state.retry_policy.max_attempts || 0),\n    };', 'void 0;'),
    ('M206', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.retryHydrated = true;', 'void 0;'),
    ('M207', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.retry_options && Array.isArray(state.retry_options.choices))', 'if (!(state.retry_options && Array.isArray(state.retry_options.choices)))'),
    ('M208', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.retryOptions = state.retry_options;', 'void 0;'),
    ('M209', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seq = Math.max(model.seq, eventSeq);', 'void 0;'),
    ('M210', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (eventSeq > 0)', 'if (!(eventSeq > 0))'),
    ('M211', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (model.seenEventSeq.has(eventSeq))', 'if (!(model.seenEventSeq.has(eventSeq)))'),
    ('M212', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seenEventSeq.add(eventSeq);', 'void 0;'),
    ('M213', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seenEventSeq.delete(Math.min.apply(null, Array.from(model.seenEventSeq)));', 'void 0;'),
    ('M214', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (event.kind === "log")', 'if (!(event.kind === "log"))'),
    ('M215', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'typeof raw === "string" ?', '!(typeof raw === "string") ?'),
    ('M216', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (line)', 'if (!(line))'),
    ('M217', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (event.kind === "phone_relogin" && !state.login_relay)', 'if (!(event.kind === "phone_relogin" && !state.login_relay))'),
    ('M218', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (payload.seq)', 'if (!(payload.seq))'),
    ('M219', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.seq = Math.max(model.seq, Number(payload.seq));', 'void 0;'),
    ('M220', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (state.login && typeof state.login === "object")', 'if (!(state.login && typeof state.login === "object"))'),
    ('M221', '甲', 'local/ui/m/ui-sync.js', 'ingest', 1, 'model.login = state.login;', 'void 0;'),
    ('M222', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (syncLine)', 'if (!(syncLine))'),
    ('M223', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'syncNow !== null\n      ?', '!(syncNow !== null)\n      ?'),
    ('M224', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (model.sheetId === "review")', 'if (!(model.sheetId === "review"))'),
    ('M225', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (!model.selected.length)', 'if (!(!model.selected.length))'),
    ('M226', '乙', 'local/ui/m/ui-sync.js', 'ingest', 1, 'if (model.pending && !model.pending.done)', 'if (!(model.pending && !model.pending.done))'),
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
        direct_helpers: set[str] = set()
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("test_"):
                if any(
                    isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "run_phone_js"
                    for c in ast.walk(item)
                ):
                    direct_helpers.add(item.name)
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                uses_node = any(
                    isinstance(c, ast.Call) and (
                        (isinstance(c.func, ast.Name) and c.func.id == "run_phone_js")
                        or (isinstance(c.func, ast.Attribute)
                            and isinstance(c.func.value, ast.Name)
                            and c.func.value.id == "self"
                            and c.func.attr in direct_helpers)
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
    root = Path(tempfile.mkdtemp(prefix="phone_render_mut_"))
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
                "replace": repl, "status": "无效", "first_fail": "", "note": "未找到目标函数"}
    mutated = apply_in_func(orig_lf, rng[0], rng[1], locate, repl)
    if mutated is None:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无效", "first_fail": "", "note": "定位不唯一或未命中"}
    target.write_text(mutated, encoding="utf-8", newline="\n")
    try:
        node = shutil.which("node")
        chk = subprocess.run([node, "--check", str(target)], capture_output=True, text=True, check=False)
        if chk.returncode != 0:
            return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                    "replace": repl, "status": "无效", "first_fail": "", "note": "node --check 失败"}
        code, fails, _ = run_unittest(root)
    finally:
        target.write_text(orig_lf, encoding="utf-8", newline="\n")
    if code == 0:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "无人守", "first_fail": "", "note": ""}
    if not fails:
        return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
                "replace": repl, "status": "字面守", "first_fail": "(unknown)", "note": "非零退出但未解析出用例名"}
    behav = [f for f in fails if bmap.get(f, False)]
    status = "行为守" if behav else "字面守"
    return {"id": mid, "kind": kind, "file": rel, "func": fn, "occur": occur, "locate": locate,
            "replace": repl, "status": status, "first_fail": fails[0], "note": ""}


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
        print(f"{mid}\t{kind}\t{Path(rel).name}:{fn}\t#{occur}\t{'OK' if ok else 'MISS'}\t{loc_one} => {repl}")
    print(f"Total: {len(MUTATIONS)} (locate miss: {bad})")
    return 1 if bad else 0


def format_report(results: list[dict], phase: str, equiv: dict[str, str]) -> str:
    cats = ("行为守", "字面守", "无人守", "无效", "等价")
    counts = {k: 0 for k in cats}
    by_kind = {knd: {k: 0 for k in cats} for knd in ("甲", "乙", "丙")}
    lines = [
        f"# 第二组（摄入与渲染）变异结论（{phase}）",
        "",
        (
            f"- 范围：23 个函数（`ui-status.js` 13 个、`ui-list.js` 5 个、`ui-sync.js` 5 个），"
            f"甲类（`model.字段` 写换 `void 0`）{sum(1 for r in results if r['kind']=='甲')} 条、"
            f"乙类（条件 `C` 换 `!(C)`）{sum(1 for r in results if r['kind']=='乙')} 条、"
            f"丙类（`.hidden = X` 写换 `void 0`）{sum(1 for r in results if r['kind']=='丙')} 条，共 {len(results)} 条。"
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
            equiv_notes.append((r["id"], r["file"], r["func"], equiv[r["id"]]))
        counts[st] = counts.get(st, 0) + 1
        by_kind[r["kind"]][st] = by_kind[r["kind"]].get(st, 0) + 1
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
        "## 按变异口径单列统计（含显隐写入）",
        "",
        "| 变异口径 | 行为守 | 字面守 | 无人守 | 无效 | 等价 | 小计 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    kind_labels = {
        "甲": "甲类（`model.字段` 写换 `void 0`）",
        "乙": "乙类（条件 `C` 换 `!(C)`）",
        "丙": "丙类（`.hidden = X` 显隐写换 `void 0`）",
    }
    for knd in ("甲", "乙", "丙"):
        row_c = by_kind[knd]
        sub_total = sum(row_c.values())
        lines.append(
            f"| {kind_labels[knd]} | {row_c['行为守']} | {row_c['字面守']} | {row_c['无人守']} | "
            f"{row_c['无效']} | {row_c['等价']} | {sub_total} |"
        )
    if equiv_notes:
        lines.extend(["", "## 等价判定理由", ""])
        for mid, rel, fn, reason in equiv_notes:
            lines.append(f"- **{mid}**（`{Path(rel).name}:{fn}`）：{reason}")
    return "\n".join(lines) + "\n"


def run_parallel(selected: list[tuple], workers: int) -> list[dict]:
    orig_texts = {
        rel: (REPO / rel).read_text(encoding="utf-8").replace("\r\n", "\n")
        for rel in TARGET_FILES
    }
    ranges = func_ranges()
    bmap = test_behavior_map()
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_render_zip_"))
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
    tmp_zip_dir = Path(tempfile.mkdtemp(prefix="phone_render_base_"))
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
    ap = argparse.ArgumentParser(description="手机页第二组变异测试")
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
