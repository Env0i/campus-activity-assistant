#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把设置页那两处改回原样的验证（只在临时目录下的仓库副本里做，仓库本体不动）。

在副本里把 wireSettings 里验证码识别「下载并安装」「取消下载」两处绑定改回搬之前的
写法（「window.PhonePanel 在不在」的判断放回绑定之前），然后跑接线测试：识别行那
两条断言必须变红——普通脚本阶段模块还没执行，绑定之前判断为假，两颗按钮根本没绑上。
其余 33 例必须仍然全绿。

用法（仓库根执行，Python 一律带 -B）：
  python -B design/evidence/2026-11-14/phone-panel-move/scripts/revert_settings_check.py

@author Author
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

D6_BLOCK = '''  const ocrDownload = $("#btn-ocr-download");
  if (ocrDownload) {
    /* 手机面板已搬成模块：绑定发生在普通脚本阶段，模块那时还没执行，所以把
       「window.PhonePanel 在不在」的判断挪进点击处理里（写法同下面导入入口那处）。 */
    ocrDownload.addEventListener("click", () => {
      if (window.PhonePanel) void window.PhonePanel.downloadComponent("relogin_ocr");
    });
  }
  const ocrCancel = $("#btn-ocr-cancel");
  if (ocrCancel) {
    ocrCancel.addEventListener("click", () => {
      if (window.PhonePanel) void window.PhonePanel.cancelComponent("relogin_ocr");
    });
  }'''

ORIGINAL_BLOCK = '''  const ocrDownload = $("#btn-ocr-download");
  if (ocrDownload && window.PhonePanel) {
    ocrDownload.addEventListener("click", () => void window.PhonePanel.downloadComponent("relogin_ocr"));
  }
  const ocrCancel = $("#btn-ocr-cancel");
  if (ocrCancel && window.PhonePanel) {
    ocrCancel.addEventListener("click", () => void window.PhonePanel.cancelComponent("relogin_ocr"));
  }'''


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


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        getattr(stream, "reconfigure", lambda **_k: None)(encoding="utf-8", errors="replace")
    repo = Path(".").resolve()
    copy_root = Path(tempfile.mkdtemp(prefix="revert-settings-"))
    log("副本已建：%d 个文件" % copy_repo(repo, copy_root))
    settings = copy_root / "local" / "ui" / "views" / "settings.js"
    text = settings.read_text(encoding="utf-8")
    if text.count(D6_BLOCK) != 1:
        raise SystemExit("副本里找不到设置页那两处改动的原样文本，停下报告")
    settings.write_text(text.replace(D6_BLOCK, ORIGINAL_BLOCK), encoding="utf-8")
    reverted = settings.read_text(encoding="utf-8")
    if "if (ocrDownload && window.PhonePanel)" not in reverted:
        raise SystemExit("副本里改回原样没有生效，停下报告")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    # 探针：在副本的沙箱里看这两颗按钮到底有没有监听器
    probe = copy_root / "local" / "tests" / "test_zz_probe_revert.py"
    probe.write_text('''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import unittest
from pathlib import Path
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from fixtures.ui_harness import run_js


class Probe(unittest.TestCase):
    def test_probe_bindings(self):
        res = run_js("""
out.push({ phonePanel: typeof window.PhonePanel,
           dl: ($("#btn-ocr-download").listeners.click || []).length,
           cl: ($("#btn-ocr-cancel").listeners.click || []).length });
""")
        print("PROBE:", res[0])


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
    res2 = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                           "-s", "local/tests", "-p", "test_zz_probe_revert.py", "-v"],
                          cwd=copy_root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120, env=env)
    log("探针输出：%s" % ((res2.stdout or "") + (res2.stderr or "")))
    probe.unlink()
    node = shutil.which("node")
    if not node:
        raise SystemExit("本机没有 node")
    chk = subprocess.run([node, "--check", str(settings)], capture_output=True, text=True)
    if chk.returncode != 0:
        raise SystemExit("改回原样后语法不过，停下报告")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    res = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                          "-s", "local/tests", "-p", "test_ui_panel_wiring.py", "-v"],
                         cwd=copy_root, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=600, env=env)
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    red = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+) \(([^)]+)\)", out, re.M)))
    m = re.search(r"^Ran (\d+) tests? in", out, re.M)
    total = int(m.group(1)) if m else 0
    log("改回原样后：%d 例，红 %d 例" % (total, len(red)))
    for name, mod in red:
        log("  红：%s (%s)" % (name, mod))
    expect = {"test_wire_ocr_download_sends_the_ocr_download_request",
              "test_wire_ocr_cancel_sends_the_ocr_cancel_request"}
    got = {n.split(".")[-1] for n, _ in red}
    if total != 35 or got != expect:
        raise SystemExit("改回原样后的红例与预期不符：期望 %r，实际 %r" % (sorted(expect), sorted(got)))
    print("改回原样后识别行两条接线断言变红，其余 33 例仍绿（共 %d 例）" % total)
    shutil.rmtree(copy_root, ignore_errors=True)


if __name__ == "__main__":
    main()
