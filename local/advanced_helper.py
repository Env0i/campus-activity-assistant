# -*- coding: utf-8 -*-
"""可选组件的单次 JSON 入口；账号与会话不属于这个进程的协议。

@author Author
"""
from __future__ import annotations

import contextlib
import base64
import io
import json
import os
from pathlib import Path
import re
import sys

MAX_INPUT = 2 * 1024 * 1024 + 4096
_CAPTCHA_RE = re.compile(r"^[0-9A-Za-z]{4}$")


def _external_model_candidates():
    """返回外置 OCR 模型候选；源码/旧单体包没有目录时返回空。

    新版 runtime 与 model 资产并列放在 ``assets/`` 下。保留环境变量只是给
    测试和受控宿主使用，生产默认按 helper.exe 的目录推导，不依赖启动 cwd。
    """
    configured = (os.environ.get("CAMPUS_OCR_MODEL_ROOT") or "").strip()
    if configured:
        root = Path(configured)
    elif getattr(sys, "frozen", False):
        root = (Path(sys.executable).resolve().parent.parent /
                "relogin_ocr_model" / "models")
    else:
        return ()
    return (
        (root / "common.onnx", root / "charsets-beta.json", True),
        (root / "common_old.onnx", root / "charsets-old.json", False),
    )


def _classify_with_external_model(image, ddddocr):
    """用同级 model 资产识别；模型不全时返回 ``None`` 交给旧路径。"""
    try:
        raw = base64.b64decode(image[len("data:image/png;base64,"):], validate=True)
    except (ValueError, TypeError):
        return None
    for onnx_path, charsets_path, beta in _external_model_candidates():
        if not onnx_path.is_file() or not charsets_path.is_file():
            continue
        try:
            engine = ddddocr.DdddOcr(
                show_ad=False,
                beta=beta,
                import_onnx_path=str(onnx_path),
                charsets_path=str(charsets_path),
            )
            value = str(engine.classification(raw) or "").strip()
            if _CAPTCHA_RE.fullmatch(value):
                return value
        except Exception:
            # 外置模型损坏时继续尝试另一套；两套都不可用再走 legacy。
            continue
    return None


def run(feature, *, probe=False, stream=None):
    result = {"ok": False, "feature": feature, "protocol": 1}
    try:
        # 第三方库可能向 stdout 打印启动信息，协议输出必须保持单个 JSON。
        with contextlib.redirect_stdout(io.StringIO()):
            if feature == "phone_control":
                import segno
            elif feature == "relogin_ocr":
                import ddddocr
                import onnxruntime
            else:
                raise ValueError("unknown_feature")
            if probe:
                if feature == "relogin_ocr":
                    candidates = list(_external_model_candidates())
                    existing = [item for item in candidates
                                if item[0].is_file() or item[1].is_file()]
                    if existing:
                        if not any(item[0].is_file() and item[1].is_file()
                                   and _probe_external_model(item, ddddocr)
                                   for item in candidates):
                            raise ValueError("external_model_failed")
                result["ok"] = True
                return result
            raw = (stream or sys.stdin.buffer).read(MAX_INPUT + 1)
            if len(raw) > MAX_INPUT:
                raise ValueError("input_limit")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("bad_input")
            if feature == "phone_control" and set(payload) == {"op", "url"} and payload["op"] == "qr":
                from infrastructure.phone_qr import png_data_uri
                qr = png_data_uri(payload["url"], frozen=False)
                if not qr:
                    raise ValueError("qr_failed")
                result.update(ok=True, qr=qr)
            elif feature == "relogin_ocr" and set(payload) == {"op", "image"} and payload["op"] == "ocr":
                from infrastructure.advanced_features import classify_captcha
                image = payload["image"]
                code = _classify_with_external_model(image, ddddocr)
                if code is None:
                    # 旧单体包把模型放在 ddddocr 内部；没有同级外置模型时
                    # 保持原来的默认 beta→legacy fallback 行为。
                    code = classify_captcha(image, frozen=False)
                result.update(ok=True, code=code)
            else:
                raise ValueError("bad_operation")
    except Exception:
        result.update(ok=False, error="component_failed")
    return result


def _probe_external_model(candidate, ddddocr):
    onnx_path, charsets_path, beta = candidate
    try:
        ddddocr.DdddOcr(show_ad=False, beta=beta,
                        import_onnx_path=str(onnx_path),
                        charsets_path=str(charsets_path))
        return True
    except Exception:
        return False


def main(feature):
    result = run(feature, probe=sys.argv[1:] == ["--probe"])
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    sys.stdout.flush()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit("Use build_advanced.py to select a fixed component.")
