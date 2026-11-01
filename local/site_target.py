"""目标站点根地址的唯一来源。

真实域名不进仓库：公开树里只有占位值 `https://portal.school.example.edu`，
本机运行时从 `local/config.json` 的 `site.base`（已被 .gitignore 排除）读取。

解析优先级：
  1. 环境变量 SCHOOL_ORIGIN（与 server/scripts 那边同名同义，方便统一注入）
  2. config.json 的 site.base（开发/绿色版放在程序旁）
  3. 占位域名

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


def _configured_base() -> str:
    for candidate in (os.environ.get("SCHOOL_ORIGIN", "").strip(), _from_config()):
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
