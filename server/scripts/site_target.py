"""目标学校站点根地址的唯一来源（服务器版）。

解析优先级：环境变量 SCHOOL_ORIGIN → server/config.json 的 site.base → 占位值。
真实地址只存在部署机配置，不写进公开执行代码。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PLACEHOLDER = "https://portal.school.example.edu"
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


def _config_origin() -> str:
    try:
        raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    site = (raw or {}).get("site") or {}
    return str(site.get("base") or "").strip()


def _configured_base() -> str:
    for candidate in (os.environ.get("SCHOOL_ORIGIN", "").strip(),
                      _config_origin()):
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
CONFIG_MESSAGE = ("未配置目标学校站点，请在 server/config.json 的 site.base 填写目标学校根地址，"
                  "或注入 SCHOOL_ORIGIN。")
