#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线手机页 HTTP 探针：起 dev_phone_preview，核对首页与关键静态脚本可读，然后停服。

只连 127.0.0.1；不连学校，不读真实配置与数据目录。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PROXY_VARS = ("http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY", "all_proxy", "ALL_PROXY")
BANNER = re.compile(r"地址=(http://127\.0\.0\.1:\d+)/\s+配对码=(\d{6})")


def fetch(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8", "replace")


def main() -> int:
    for key in PROXY_VARS:
        os.environ.pop(key, None)
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "local" / "dev_phone_preview.py"),
         "--state", "valid", "--port", "0", "--no-browser"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", env=env, cwd=str(ROOT),
    )
    watchdog = threading.Timer(60, proc.terminate)
    watchdog.start()
    try:
        base = ""
        code = ""
        assert proc.stdout is not None
        for line in proc.stdout:
            match = BANNER.search(line)
            if match:
                base, code = match.group(1), match.group(2)
                print("[probe] %s" % line.strip())
                break
        if not base:
            print("[probe] 没有等到预览服务启动")
            return 1
        checks = [
            ("/", "校园活动", "首页"),
            ("/styles.css", "--", "样式"),
            ("/ui-shell.js", "PhoneUI", "外壳脚本"),
            ("/model.js", "PhoneModel", "模型脚本"),
        ]
        for path, marker, label in checks:
            status, text = fetch(base + path)
            if status != 200 or marker not in text:
                print("[probe] %s 失败：status=%s" % (label, status))
                return 1
            print("[probe] %s 通过：%s %d 字节" % (label, path, len(text.encode("utf-8"))))
        print("[probe] 配对码格式：%s" % ("6 位数字" if code.isdigit() and len(code) == 6 else "异常"))
        print("[probe] 结论：离线手机页与关键脚本均可读")
        return 0
    finally:
        watchdog.cancel()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
