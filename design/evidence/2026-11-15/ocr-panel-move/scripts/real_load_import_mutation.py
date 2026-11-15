#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真加载第四条的变异验证：在仓库副本里删掉 view-ocr.js 引 downloadFailText 的
那一行 import，然后——
一、跑模块图守卫（node tools/code_shape/ui_modules.mjs），「用了别的模块定义的名字
    却没有 import」一类必须非空；
二、只跑真加载第四条用例（识别行下载失败后红条的文字），必须变红。
两段输出都打印到标准输出，供 real-load-output.md 收录。仓库本体不动。

用法（仓库根执行，Python 一律带 -B）：
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/real_load_import_mutation.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MUTATED_FILE = "local/ui/features/components/view-ocr.js"
REMOVE_LINE = 'import { downloadFailText } from "./state.js";'
GUARD_TEST = "test_real_load_ocr_failed_download_paints_the_retry_bar"


def log(msg: str) -> None:
    print(msg, flush=True)


def copy_repo(repo: Path, dest: Path) -> int:
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                         cwd=repo, capture_output=True, check=True)
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    count = 0
    for rel in names:
        if "config.json" in rel or rel.startswith(("local/data/", "server/data/")):
            continue
        src = repo / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            count += 1
    return count


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    repo = Path(".").resolve()
    copy_root = Path(tempfile.mkdtemp(prefix="ocr-realload-mut-"))
    log("副本已建：%d 个文件（路径只在终端显示，不进任何产物）" % copy_repo(repo, copy_root))
    target = copy_root / MUTATED_FILE
    lines = target.read_text(encoding="utf-8").splitlines()
    hits = [i for i, l in enumerate(lines) if l.strip() == REMOVE_LINE]
    if len(hits) != 1:
        raise SystemExit("定位不到唯一一行 %r（%d 处）" % (REMOVE_LINE, len(hits)))
    del lines[hits[0]]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    log("")
    log("== 一、模块图守卫（副本里跑）缺 import 一类 ==")
    res = subprocess.run(["node", "tools/code_shape/ui_modules.mjs"], cwd=copy_root,
                         capture_output=True, text=True, encoding="utf-8", env=env, check=True)
    report = json.loads(res.stdout)
    log("missing_imports = " + json.dumps(report["missing_imports"], ensure_ascii=False, indent=1))
    log("missing_imports 条数：%d（非空即守卫抓到）" % len(report["missing_imports"]))

    log("")
    log("== 二、真加载第四条用例（副本里跑）==")
    res = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
         "-p", "test_ui_modules.py", "-v", "-k", GUARD_TEST],
        cwd=copy_root, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=600, env=env)
    text = (res.stdout or "") + "\n" + (res.stderr or "")
    tail = [l for l in text.splitlines() if l.strip()][-14:]
    for l in tail:
        log(l)
    log("")
    log("退出码 %d（非零即这条用例真的变红）" % res.returncode)
    shutil.rmtree(copy_root, ignore_errors=True)
    if res.returncode == 0 or not report["missing_imports"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
