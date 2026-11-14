#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""面板搬成模块之后，在新位置重跑安全网的执行器入口：把 2026-11-14 那份
mutate_reads.py 的行清单换成 rows_after_move.py 的 92 行（83 行安全网 + 9 个组件
出口），其余逻辑（副本、定位、变异、跑相关测试、结论分类、出表）全部复用，
不改旧目录的任何文件。

用法与 mutate_reads.py 相同（仓库根执行，Python 一律带 -B）：
  --verify 只定位核对；--baseline 未变异基线；--ids 指定编号；
  --shard i --shards n 分片；--out 写 markdown；--json 写机器可读结果；
  --merge s0.json … 合成分片。

@author Author
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "components-net" / "scripts"))

import mutate_reads  # noqa: E402
from rows_after_move import ROWS  # noqa: E402

mutate_reads.ROWS = ROWS
# 新位置是模块：函数声明行前面多了一个 export 关键字，定位正则相应放宽
# （旧目录的文件一个字不改，这里只在运行时换这个常量）
mutate_reads._DEF_RE = r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s+)?%s\s*\([^)]*\)\s*\{"
mutate_reads.main()
