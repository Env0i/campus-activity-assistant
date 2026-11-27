#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""服务端验证码 OCR 模型解析与按需加载。

@author Author
"""
import os

CUSTOM_ONNX_NAME = "school_captcha.onnx"
CUSTOM_CHARSETS_NAME = "charsets.json"


def custom_model_paths(base_dir=None):
    """返回定制校园验证码模型的 (onnx, charsets) 路径；缺文件时返回 None。"""
    configured = (os.environ.get("CAMPUS_CUSTOM_OCR_DIR") or "").strip()
    root = configured or os.path.join(base_dir or os.path.dirname(os.path.abspath(__file__)), "models")
    onnx_path = os.path.join(root, CUSTOM_ONNX_NAME)
    charsets_path = os.path.join(root, CUSTOM_CHARSETS_NAME)
    if os.path.isfile(onnx_path) and os.path.isfile(charsets_path):
        return onnx_path, charsets_path
    return None


def load_engine(which, ddddocr_mod, base_dir=None):
    """按模型名实例化 ddddocr 引擎；custom 资产未部署时返回 None 交由后续模型兜底。"""
    if which == "custom":
        paths = custom_model_paths(base_dir)
        if paths is None:
            return None
        return ddddocr_mod.DdddOcr(
            show_ad=False, import_onnx_path=paths[0], charsets_path=paths[1]
        )
    # show_ad=False 关掉首次运行的横幅文字，免得混进日志
    return ddddocr_mod.DdddOcr(
        ocr=True, det=False, beta=(which == "beta"), show_ad=False
    )
