# -*- coding: utf-8 -*-
"""可选组件的单次 JSON 入口；账号与会话不属于这个进程的协议。

@author Author
"""
from __future__ import annotations

import contextlib
import io
import json
import sys

MAX_INPUT = 2 * 1024 * 1024 + 4096


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
                result.update(ok=True, code=classify_captcha(payload["image"], frozen=False))
            else:
                raise ValueError("bad_operation")
    except Exception:
        result.update(ok=False, error="component_failed")
    return result


def main(feature):
    result = run(feature, probe=sys.argv[1:] == ["--probe"])
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    sys.stdout.flush()
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit("Use build_advanced.py to select a fixed component.")
