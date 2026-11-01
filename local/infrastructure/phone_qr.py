# -*- coding: utf-8 -*-
"""手机访问二维码生成：依赖可选，未安装时返回明确状态。"""
from __future__ import annotations

import base64
import io
import sys
from urllib.parse import urlsplit


def png_data_uri(address: str, *, root=None, frozen=None) -> str:
    """地址 → PNG data URI；不把配对码放进二维码。"""
    text = str(address or "").strip()
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    if (not text or len(text) > 2048 or parsed.scheme not in {"http", "https"}
            or not parsed.hostname or parsed.query or parsed.fragment
            or parsed.username or parsed.password):
        return ""
    try:
        frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
        if frozen:
            from infrastructure import component_packages
            result = component_packages.invoke("phone_control", {"op": "qr", "url": text}, root=root)
            uri = str(result.get("qr") or "")
            return uri if uri.startswith("data:image/png;base64,") else ""
        import segno
        qr = segno.make(text, error="m")
        out = io.BytesIO()
        qr.save(out, kind="png", scale=5, border=4)
        return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
    except Exception:
        return ""


__all__ = ["png_data_uri"]
