#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板搬成模块之后，安全网三组变异加检查中探针加组件 9 个出口在新位置的行清单
（只放数据，不放逻辑；定位与执行复用 design/evidence/2026-11-14/components-net/
scripts/mutate_reads.py，由同目录 run_after_move.py 换上这份清单再跑）。

前 83 行与 mutate_rows.py 的 ROWS 逐条对应：编号、一行是什么、函数名、该行原文、
方式与换法一个字不改，只有「文件相对 local/ui/」换成面板搬走后的新位置——
phonePhase 在 features/phone-access/state.js；paint 与 paintPhoneAccess 在
features/phone-access/view.js；paintRelogin 与 paintCredForm 在
features/login/view-recovery.js；startPolling、enableFeature、toggleStart、
toggleStop 在 features/phone-access/actions.js；downloadComponent 在
features/components/actions.js；views/settings.js 的行不变。
后 9 行是出口那一批里组件这一块的 9 个出口（C01–C09），变异方式与
mutate_exits.py 相同——把那一行的状态赋值整行换成空语句；文件路径同样换成
新位置，函数名与该行原文一个字不改。

行按「文件、函数、那一行的文字」定位，不按行号；定位不到就整体停下报告。

@author Author
"""
from __future__ import annotations

import sys
from pathlib import Path

_OLD_SCRIPTS = Path(__file__).resolve().parents[2] / "components-net" / "scripts"
sys.path.insert(0, str(_OLD_SCRIPTS))
from mutate_rows import ROWS as _OLD_ROWS  # noqa: E402

# 旧清单里 views/phone.js 的行，按函数名换到新位置
_NEW_PATH_BY_FUNC = {
    "phonePhase": "features/phone-access/state.js",
    "paint": "features/phone-access/view.js",
    "paintPhoneAccess": "features/phone-access/view.js",
    "paintRelogin": "features/login/view-recovery.js",
    "paintCredForm": "features/login/view-recovery.js",
    "startPolling": "features/phone-access/actions.js",
    "enableFeature": "features/phone-access/actions.js",
    "toggleStart": "features/phone-access/actions.js",
    "toggleStop": "features/phone-access/actions.js",
    "downloadComponent": "features/components/actions.js",
}

# 出口那一批里组件这一块的 9 个出口（C01–C09）：文件换到新位置，
# 函数名与那一行的原文一个字不改；变异方式=blank（整行换成空语句）
_EXIT_ROWS = [
    ("C01", "组件·面板请求在途", "features/phone-access/actions.js", "enableFeature",
     "PhonePanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C02", "组件·面板请求在途", "features/phone-access/actions.js", "toggleStart",
     "PhonePanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C03", "组件·面板请求在途", "features/phone-access/actions.js", "toggleStop",
     "PhonePanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C04", "组件·面板请求在途", "features/components/actions.js", "downloadComponent",
     "PhonePanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C05", "组件·面板请求在途", "features/login/actions-recovery.js", "saveCredentials",
     "PhonePanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C06", "组件·手机访问开启中或停止中", "features/phone-access/actions.js", "toggleStart",
     'PhonePanel.pending = "";', "blank", "（整行）", "（空语句）", "组件出口"),
    ("C07", "组件·手机访问开启中或停止中", "features/phone-access/actions.js", "toggleStop",
     'PhonePanel.pending = "";', "blank", "（整行）", "（空语句）", "组件出口"),
    ("C08", "组件·导入安装中", "features/components/actions.js", "installComponent",
     "PhonePanel.installing[key] = false;", "blank", "（整行）", "（空语句）", "组件出口"),
    ("C09", "组件·验证码识别面板请求在途", "views/settings.js", "enableOcr",
     "OcrPanel.busy = false;", "blank", "（整行）", "（空语句）", "组件出口"),
]


def _remap(rows):
    out = []
    for row in rows:
        rid, desc, rel, func = row[0], row[1], row[2], row[3]
        if rel == "views/phone.js":
            rel = _NEW_PATH_BY_FUNC[func]
        out.append((rid, desc, rel, func) + tuple(row[4:]))
    return out


ROWS = _remap(_OLD_ROWS) + _EXIT_ROWS
