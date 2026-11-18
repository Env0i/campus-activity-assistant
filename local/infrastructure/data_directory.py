# -*- coding: utf-8 -*-
"""数据根的路径计算：开发/绿色版与冻结 EXE 共用同一套口径。

只算路径：不建目录、不迁移、不读偏好——那些留在 runtime_paths。
runtime_paths 与 infrastructure.component_packages 都复用这里的计算，
后者因此不必反向 import 顶层模块（分层边界见 test_layer_boundaries）。

@author Author
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 统一数据根的应用目录名（%LOCALAPPDATA% 下）
APP_DIR_NAME = "TianSoftActivityPreRegistration"
_default_dir: Path | None = None


def base_dir() -> Path:
    """解析本进程的数据根（只算路径，不创建目录）。

    顺序：CAMPUS_DATA_DIR 覆盖 → 冻结态 %LOCALAPPDATA%/应用名/data → 源码态
    local/data。与 runtime_paths 拆分前的算法逐行一致。
    """
    override = os.environ.get("CAMPUS_DATA_DIR", "").strip()
    if override:
        # 相对路径锚定当前工作目录，避免冻结进程拿到一个随启动目录漂移的根
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA", "").strip()
        # LOCALAPPDATA 缺失（精简系统/服务账户）时回退 home/AppData/Local
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / APP_DIR_NAME / "data"
    return Path(__file__).resolve().parents[1] / "data"


def default_data_dir(*, initialize: bool = False) -> Path:
    """共享进程锚点；运行时初始化可重置，独立使用时首次解析即固定。"""
    global _default_dir
    if initialize or _default_dir is None:
        _default_dir = base_dir()
    return _default_dir
