"""目标站点根地址的唯一来源。

真实域名不进仓库：公开树里只有占位值 `https://portal.school.example.edu`。
三种来源按优先级解析：
  1. 环境变量 SCHOOL_ORIGIN（与 server/scripts 那边同名同义，方便统一注入）
  2. config.json 的 site.base（开发/绿色版放在程序旁）
  3. 打包内置的 `_site_build.BUILD_BASE`（发布版在构建时由 tools/release.py 从
     构建环境的 SCHOOL_ORIGIN 生成并打进资源根；该文件绝不入库，源码态没有就跳过）

都缺失时回落到占位域名，`CONFIGURED=False`（学校动作会被拒绝，不会拿占位地址发请求）。
端点路由（/dr/api、/stu/）是站点自身的路径，不属于可替换变量，不在这里。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PLACEHOLDER = "https://portal.school.example.edu"


def _here() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _from_config() -> str:
    path = _here() / "config.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    site = (raw or {}).get("site") or {}
    return str(site.get("base") or "").strip()


def _from_build() -> str:
    """打包内置的构建时地址：`local/_site_build.py` 只在正式构建期间存在。

    源码态、开发机与公开仓库都没有这个模块（.gitignore 排除），导入失败就当没有；
    发布版由 tools/release.py 在 prepare 阶段生成并随 PyInstaller 打进资源根。
    """
    try:
        from _site_build import BUILD_BASE  # 构建时生成，绝不入库
    except ImportError:
        return ""
    return str(BUILD_BASE or "").strip()


def _configured_base() -> str:
    for candidate in (os.environ.get("SCHOOL_ORIGIN", "").strip(),
                      _from_config(), _from_build()):
        if candidate:
            return candidate.rstrip("/")
    return ""


def resolve_base() -> str:
    configured = _configured_base()
    if configured:
        return configured
    return PLACEHOLDER


BASE_URL = resolve_base()
CONFIGURED = bool(_configured_base())
CONFIG_MESSAGE = ("未配置目标学校站点，请复制 local/config.example.json 为 "
                  "local/config.json 并填写 site.base。")
