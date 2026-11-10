# -*- coding: utf-8 -*-
"""两个可选高级组件的状态与按需安装原语。

启动时只读探测，不自动联网、不自动装依赖。用户在帮助弹窗明确点击安装后，
调用方才可以执行 pip；冻结程序不把自身 EXE 当作 Python 解释器。

@author Author
"""
from __future__ import annotations

import importlib.util
import base64
import re
import subprocess
import sys
import threading
import zipfile
from dataclasses import dataclass
from typing import Callable

from infrastructure import component_packages


PHONE_CONTROL = "phone_control"
RELOGIN_OCR = "relogin_ocr"


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    title: str
    package: str
    module: str
    description: str


FEATURES = {
    PHONE_CONTROL: FeatureSpec(
        PHONE_CONTROL, "手机控制", "segno", "segno",
        "二维码、远程通道和手机控制台。",
    ),
    RELOGIN_OCR: FeatureSpec(
        RELOGIN_OCR, "验证码识别", "ddddocr", "ddddocr",
        "保存本机凭据并自动识别验证码；未安装时仍可人工输入。",
    ),
}

_CAPTCHA_RE = re.compile(r"^[0-9A-Za-z]{4}$")
_OCR_LOCK = threading.Lock()
_OCR_ENGINES = {}


def _enabled(prefs: dict | None, key: str) -> bool:
    values = (prefs or {}).get("advanced_features") or {}
    return bool(values.get(key, False))


def module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        return False


def feature_ready(prefs: dict | None, key: str, *, root=None, frozen=None) -> bool:
    """只有用户启用且依赖可导入时，组件才可被业务调用。"""
    state = feature_state(prefs, root=root, frozen=frozen)
    return bool(state.get(str(key), {}).get("ready"))


def feature_state(prefs: dict | None = None, *, root=None, frozen=None) -> dict:
    """返回可直接给桌面 UI 的状态，不暴露安装路径或凭据。"""
    result = {}
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    for key, spec in FEATURES.items():
        package = component_packages.feature_status(key, root=root) if frozen else {
            "available": module_available(spec.module), "source": "source", "error": "",
            "version": ""}
        available = package["available"]
        error = package["error"]
        result[key] = {
            "key": key,
            "title": spec.title,
            "description": spec.description,
            "enabled": _enabled(prefs, key),
            "available": available,
            "ready": bool(_enabled(prefs, key) and available),
            "installable": error != "unsupported_platform",
            "package": spec.package,
            "source": package["source"],
            # 装的是哪个版本的组件：界面要说得出来，下载服务也拿它判断是否最新
            "package_version": str(package.get("version") or ""),
            "error": error,
            "status": ("unsupported" if error == "unsupported_platform" else
                       "failed" if error else "ready" if available else "missing"),
            "install_mode": "import" if frozen else "pip",
        }
    return result


def install_feature(
    key: str,
    *,
    python_executable: str | None = None,
    frozen=None,
    root=None,
    archive=None,
    runner: Callable[..., object] = subprocess.run,
) -> dict:
    """按用户点击安装一个组件；不接受任意包名，避免变成通用 pip 入口。"""
    spec = FEATURES.get(str(key))
    if spec is None:
        return {"ok": False, "error": "unknown_feature", "text": "未知高级功能"}
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if frozen:
        if archive is None:
            return {"ok": False, "error": "package_required",
                    "text": "请选择与当前版本相同、来源可信的组件 ZIP。"}
        try:
            return component_packages.install(archive, key, root=root)
        except (component_packages.PackageError, OSError, ValueError, zipfile.BadZipFile):
            return {"ok": False, "error": "component_import_failed",
                    "text": "组件未导入。请检查来源、版本及完整性，原有组件仍保留。"}
    if module_available(spec.module):
        # 源码环境已装好依赖时只启用；冻结态始终走独立组件。
        return {"ok": True, "feature": key, "text": "%s已启用" % spec.title}
    exe = str(python_executable or sys.executable)
    try:
        completed = runner(
            [exe, "-m", "pip", "install", spec.package],
            check=False, capture_output=True, text=True, timeout=300,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "install_failed",
                "text": "安装失败：%s" % type(exc).__name__}
    code = int(getattr(completed, "returncode", 1) or 0)
    if code != 0:
        return {"ok": False, "error": "install_failed",
                "text": "安装失败，请检查网络或 Python 环境。"}
    importlib.invalidate_caches()
    if not module_available(spec.module):
        return {"ok": False, "error": "install_unavailable",
                "text": "安装命令已结束，但组件仍不可用，请重启程序后再试。"}
    return {"ok": True, "feature": key, "text": "%s已安装" % spec.title}


def classify_captcha(image_data_uri: str, *, root=None, frozen=None) -> str:
    """可选 ddddocr 识别入口；缺组件、坏图片或非四位结果都返回空串。

    识别只在调用方已经通过 feature_ready 门禁后发生，模块导入保持延迟，
    基础安装启动时不会加载大模型。
    """
    text = str(image_data_uri or "")
    prefix = "data:image/png;base64,"
    if not text.startswith(prefix) or len(text) > 2 * 1024 * 1024:
        return ""
    try:
        raw = base64.b64decode(text[len(prefix):], validate=True)
        if not raw:
            return ""          # 空图不进识别引擎，直接回退人工
        frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
        if frozen:
            result = component_packages.invoke(RELOGIN_OCR, {"op": "ocr", "image": text}, root=root)
            value = str(result.get("code") or "").strip()
        else:
            import ddddocr
            # 模型初始化昂贵；每个解释器缓存，beta 不可用才回退默认模型。
            with _OCR_LOCK:
                for beta in (True, False):
                    try:
                        cache_key = (ddddocr.DdddOcr, beta)
                        engine = _OCR_ENGINES.get(cache_key)
                        if engine is None:
                            engine = ddddocr.DdddOcr(show_ad=False, beta=beta)
                            _OCR_ENGINES[cache_key] = engine
                        value = str(engine.classification(raw) or "").strip()
                        if _CAPTCHA_RE.fullmatch(value):
                            return value
                    except Exception:
                        continue
                return ""
    except Exception:  # noqa: BLE001 - 引擎任何故障都必须回退人工输入
        return ""
    return value if _CAPTCHA_RE.fullmatch(value) else ""


def allowed_feature(key: str) -> bool:
    return str(key) in FEATURES


__all__ = [
    "FEATURES", "PHONE_CONTROL", "RELOGIN_OCR", "allowed_feature",
    "feature_state", "feature_ready", "install_feature", "module_available",
    "classify_captcha",
]
