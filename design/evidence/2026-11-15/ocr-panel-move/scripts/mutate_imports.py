#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""import 与挂回的变异：跨批 import 三条、挂回名字两个，各看哪些用例变红。

五条变异——
一、删 features/components/view-ocr.js 引 downloadFailText 的那一行 import；
二、删 features/components/actions.js 引 OcrPanel 的那一行 import；
三、删 features/phone-access/view.js 引 paintOcrDownload 的那一行 import；
四、过渡名单里去掉挂回的 OcrPanel（连同它的 import）；
五、过渡名单里去掉挂回的 paintOcrDownload（连同它的 import）。
每条都在 tempfile 下的仓库副本里做（副本按 git ls-files 复制，config.json 与两个
data 目录不进副本），仓库本体不动；改完先 node --check，再逐份跑相关测试文件，
记录变红的用例。预期：前三条拼接类测试不红、只有模块图守卫（与真加载第四条）
红——这正是拼接测试发现不了缺 import 的那类缺陷。

用法（仓库根执行，Python 一律带 -B）：
  python -B design/evidence/2026-11-15/ocr-panel-move/scripts/mutate_imports.py \
      [--json <文件>] [--out <markdown>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_FILES = (
    "test_phone_ui.py", "test_ui_component_rows.py", "test_ui_modules.py",
    "test_reason_maps.py", "test_ui_contract_components.py",
    "test_ui_contract_settings.py",
)
TEST_TIMEOUT_S = 900

# 每条：编号、说明、要删的行（去空白后逐字相等，每行必须恰好出现一次）
MUTATIONS = [
    ("m1-view-ocr-downloadfail", "view-ocr.js 引 downloadFailText 的 import",
     "features/components/view-ocr.js",
     ['import { downloadFailText } from "./state.js";']),
    ("m2-actions-ocrpanel", "components/actions.js 引 OcrPanel 的 import",
     "features/components/actions.js",
     ['import { OcrPanel } from "./state-ocr.js";']),
    ("m3-view-paintocrdownload", "phone-access/view.js 引 paintOcrDownload 的 import",
     "features/phone-access/view.js",
     ['import { paintOcrDownload } from "../components/view-ocr.js";']),
    ("m4-attach-ocrpanel", "过渡名单挂回 OcrPanel（连同 import）",
     "legacy-globals.js",
     ['import { OcrPanel } from "./features/components/state-ocr.js";',
      "window.OcrPanel = OcrPanel;"]),
    ("m5-attach-paintocrdownload", "过渡名单挂回 paintOcrDownload（连同 import）",
     "legacy-globals.js",
     ['import { paintOcrDownload } from "./features/components/view-ocr.js";',
      "window.paintOcrDownload = paintOcrDownload;"]),
]


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


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


def apply_mutation(copy_root: Path, rel: str, lines_to_remove: list[str]) -> None:
    path = copy_root / "local" / "ui" / rel
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    for want in lines_to_remove:
        hits = [i for i, l in enumerate(lines) if l.strip() == want]
        if len(hits) != 1:
            raise SystemExit("定位不到唯一一行 %r（%d 处），停下报告" % (want, len(hits)))
        del lines[hits[0]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def node_check(path: Path) -> bool:
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node，无法做语法检查")
    return subprocess.run([node, "--check", str(path)], capture_output=True,
                          text=True).returncode == 0


def run_one_test(copy_root: Path, pattern: str) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    cmd = [sys.executable, "-B", "-m", "unittest", "discover",
           "-s", "local/tests", "-p", pattern]
    res = subprocess.run(cmd, cwd=copy_root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=TEST_TIMEOUT_S, env=env)
    text = (res.stdout or "") + "\n" + (res.stderr or "")
    m = re.search(r"^Ran (\d+) tests? in", text, re.M)
    red = []
    for line in text.splitlines():
        mm = re.match(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)\s*$", line)
        if mm:
            red.append((mm.group(2) or mm.group(1)))
    sm = re.search(r"^FAILED \((.*)\)\s*$", text, re.M)
    stat = dict.fromkeys(("failures", "errors", "skipped"), 0)
    for key, val in (re.findall(r"(failures|errors|skipped)=(\d+)", sm.group(1)) if sm else []):
        stat[key] = int(val)
    return {"file": pattern, "total": int(m.group(1)) if m else 0,
            "ok": res.returncode == 0, "red": sorted(set(red)), **stat}


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    here = Path(__file__).resolve()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(here.parents[5]))
    ap.add_argument("--json", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()

    results = []
    for mid, desc, rel, lines_to_remove in MUTATIONS:
        copy_root = Path(tempfile.mkdtemp(prefix="ocr-import-mut-"))
        log("副本已建：%d 个文件" % copy_repo(repo, copy_root))
        apply_mutation(copy_root, rel, lines_to_remove)
        target = copy_root / "local" / "ui" / rel
        if not node_check(target):
            results.append({"id": mid, "desc": desc, "syntax_ok": False, "runs": []})
            log("[%s] 变异后语法不过" % mid)
            shutil.rmtree(copy_root, ignore_errors=True)
            continue
        runs = [run_one_test(copy_root, p) for p in TEST_FILES]
        red = sorted({r for run in runs for r in run["red"]})
        results.append({"id": mid, "desc": desc, "syntax_ok": True,
                        "where": rel, "runs": runs, "red": red})
        log("[%s] 红=%d" % (mid, len(red)))
        for run in runs:
            if run["red"]:
                log("    %s：%s" % (run["file"], "、".join(run["red"])))
            else:
                log("    %s：不红（%d 例）" % (run["file"], run["total"]))
        shutil.rmtree(copy_root, ignore_errors=True)

    payload = json.dumps(results, ensure_ascii=False, indent=1)
    print(payload)
    if args.json:
        Path(args.json).write_text(payload, encoding="utf-8")
    if args.out:
        lines = ["# import 与挂回的变异结论", "",
                 "- 五条变异都在临时目录下的仓库副本里做（仓库本体不动），改完先 node --check，"
                 "再逐份跑六份相关测试文件；未变异时这些文件在本仓库全绿。",
                 "",
                 "| 编号 | 变异 | 变红的用例 | 不红的文件（拼接类照常绿） |",
                 "|---|---|---|---|"]
        for item in results:
            reds = "、".join(item["red"]) if item["red"] else "（无）"
            quiet = "、".join(run["file"] for run in item["runs"] if not run["red"]) or "（无）"
            lines.append("| %s | %s | %s | %s |" % (item["id"], item["desc"], reds, quiet))
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
