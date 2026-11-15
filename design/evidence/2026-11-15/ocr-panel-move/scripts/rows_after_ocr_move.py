#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证码识别一节搬成模块之后，安全网行清单在新位置的版本（只放数据，不放逻辑）。

从上一批（手机面板搬家）的行清单 design/evidence/2026-11-14/phone-panel-move/
scripts/rows_after_move.py 取全部 92 行（83 行安全网 + 9 个组件出口），把其中
文件是 views/settings.js、函数是 ocrPhase 或 paintOcrDownload 的行换到新位置——
ocrPhase 到 features/components/state-ocr.js、paintOcrDownload 到
features/components/view-ocr.js；函数名与那一行的原文一个字不改，别的行不变
（busy-enableOcr 与出口 C09 的 enableOcr 留在 views/settings.js，那批函数本批不搬）。
定位与执行复用 design/evidence/2026-11-14/components-net/scripts/mutate_reads.py，
由同目录 run_after_ocr_move.py 换上这份清单再跑。

行按「文件、函数、那一行的文字」定位，不按行号；定位不到就整体停下报告。

@author Author
"""
from __future__ import annotations

import sys
from pathlib import Path

_OLD_SCRIPTS = (Path(__file__).resolve().parents[3] / "2026-11-14"
                / "phone-panel-move" / "scripts")
sys.path.insert(0, str(_OLD_SCRIPTS))
from rows_after_move import ROWS as _OLD_ROWS  # noqa: E402

# 旧清单里 views/settings.js 的行，按函数名换到新位置
_NEW_PATH_BY_FUNC = {
    "ocrPhase": "features/components/state-ocr.js",
    "paintOcrDownload": "features/components/view-ocr.js",
}


def _remap(rows):
    out = []
    for row in rows:
        rid, desc, rel, func = row[0], row[1], row[2], row[3]
        if rel == "views/settings.js" and func in _NEW_PATH_BY_FUNC:
            rel = _NEW_PATH_BY_FUNC[func]
        out.append((rid, desc, rel, func) + tuple(row[4:]))
    return out


ROWS = _remap(_OLD_ROWS)
