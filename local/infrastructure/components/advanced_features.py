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
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from domain.components.component_rules import check_timed_out
from infrastructure.components import component_packages
from infrastructure.stores.prefs_store import PrefsLockTimeout


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
# 组件状态的上一次成功结果，只存进程内存：组件事务锁被别的进程占着时，
# 界面状态查询拿它顶一下，不能让一次锁等待超时变成「组件装坏了」。
_PACKAGE_CACHE = {}
_PACKAGE_CACHE_LOCK = threading.Lock()
# 这一轮连续等锁的起点，按 (root, key) 记，与缓存共用一把锁：等锁是「已经连续
# 等了多久」，要用单调时钟累计（改系统时间不能让它跳），读成功或读错即清零。
# 用单调时钟是因为这是「等了多久」，不是业务时刻。
_LOCK_WAIT_START = {}


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


def _frozen_package(key: str, root, clock) -> dict:
    """冻结态的组件状态；拿事务锁超时（PrefsLockTimeout）时不向界面抛异常。

    有上一次成功的结果就返回它的副本并标 busy；一次都没成功过就返回 checking，
    不报 failed，也不报 missing：此刻并不知道组件是什么状态。等锁时按 (root,
    key) 记「这一轮连续等锁的起点」，给出等了多少秒、是否到 30 秒，界面据此画
    「检查超时」；读状态出错也不冒异常，退回上一次成功的结果（或检查中）并标
    read_error，让界面说「暂时读不到组件状态」。
    """
    cache_key = (str(root) if root is not None else "", key)
    try:
        package = component_packages.feature_status(key, root=root)
    except PrefsLockTimeout:
        with _PACKAGE_CACHE_LOCK:
            cached = _PACKAGE_CACHE.get(cache_key)
            started = _LOCK_WAIT_START.get(cache_key)
            if started is None:
                started = clock()
                _LOCK_WAIT_START[cache_key] = started
            lock_wait_s = max(0, int(clock() - started))
        # 等锁的两个字段有缓存、没缓存两种包都要带：界面在「检查中」与「缓存顶住」
        # 两种显示下都要能数出「已经等了多少秒、到没到 30 秒」
        if cached is not None:
            payload = dict(cached, busy=True, lock_wait_s=lock_wait_s,
                           check_timed_out=check_timed_out(lock_wait_s))
            return payload
        return {"available": False, "source": "imported", "error": "", "version": "",
                "busy": True, "checking": True,
                "lock_wait_s": lock_wait_s,
                "check_timed_out": check_timed_out(lock_wait_s)}
    except (component_packages.PackageError, OSError, ValueError):
        # 读错不同于等锁：状态真的读不出来。退回上一次成功的结果；没有就按
        # 检查中（不说没装），两者都标 read_error。等锁起点一并清掉。
        with _PACKAGE_CACHE_LOCK:
            cached = _PACKAGE_CACHE.get(cache_key)
            _LOCK_WAIT_START.pop(cache_key, None)
        if cached is not None:
            return dict(cached, read_error=True)
        return {"available": False, "source": "imported", "error": "", "version": "",
                "busy": True, "checking": True, "read_error": True}
    slim = {"available": package["available"], "source": package["source"],
            "error": package["error"], "version": str(package.get("version") or "")}
    with _PACKAGE_CACHE_LOCK:
        _PACKAGE_CACHE[cache_key] = slim
        _LOCK_WAIT_START.pop(cache_key, None)
    return package


def feature_state(prefs: dict | None = None, *, root=None, frozen=None,
                  clock=time.monotonic) -> dict:
    """返回可直接给桌面 UI 的状态，不暴露安装路径或凭据。"""
    result = {}
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    for key, spec in FEATURES.items():
        package = _frozen_package(key, root, clock) if frozen else {
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
                       "checking" if package.get("checking") else
                       "outdated" if error == "component_outdated" else
                       "failed" if error else "ready" if available else "missing"),
            "install_mode": "import" if frozen else "pip",
        }
        if package.get("busy"):
            result[key]["busy"] = True
        # 等锁与读错是「这一次查询的事实」，原样抄到那一行；没在等锁、没读错
        # 时不出现，前端按缺字段判断
        if "lock_wait_s" in package:
            result[key]["lock_wait_s"] = package["lock_wait_s"]
            result[key]["check_timed_out"] = package["check_timed_out"]
        if "read_error" in package:
            result[key]["read_error"] = package["read_error"]
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


def _custom_ocr_paths():
    """返回随源码或旧单体包附带的定制校园验证码模型路径；缺失时返回 ``None``。"""
    roots = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS) / "ocr_models")
    roots.append(Path(__file__).resolve().parents[3] / "server" / "deploy" / "login" / "models")
    for base in roots:
        onnx_path = base / "school_captcha.onnx"
        charsets_path = base / "charsets.json"
        if onnx_path.is_file() and charsets_path.is_file():
            return str(onnx_path), str(charsets_path)
    return None


def _classify_local(ddddocr_mod, raw: bytes) -> str:
    """按 定制校园模型 → beta → 默认模型 的顺序尝试识别，全部命中缓存。"""
    custom = _custom_ocr_paths()
    specs = []
    if custom is not None:
        specs.append(("custom", custom))
    specs.extend(("builtin", beta) for beta in (True, False))
    with _OCR_LOCK:
        for kind, arg in specs:
            try:
                cache_key = (ddddocr_mod.DdddOcr, kind, arg)
                engine = _OCR_ENGINES.get(cache_key)
                if engine is None:
                    if kind == "custom":
                        engine = ddddocr_mod.DdddOcr(
                            show_ad=False, import_onnx_path=arg[0], charsets_path=arg[1])
                    else:
                        engine = ddddocr_mod.DdddOcr(show_ad=False, beta=arg)
                    _OCR_ENGINES[cache_key] = engine
                value = str(engine.classification(raw) or "").strip()
                if _CAPTCHA_RE.fullmatch(value):
                    return value
            except Exception:
                continue
        return ""


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
            # 模型初始化昂贵；每个解释器缓存，定制模型或 beta 不可用才回退后续模型。
            return _classify_local(ddddocr, raw)
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
