#!/usr/bin/env python3
"""在临时副本里跑一段界面片段，比较「未变异」与「这一条变异」的界面输出。

只用于判等价与补测试时的取证：同一段片段在两份副本上各跑一次，输出逐字比较。
用法（从仓库根执行）：
  python -B design/evidence/2026-11-17/plan-net/scripts/probe_plan.py M012 --snippet 片段.js
  python -B ... M012 --snippet 片段.js --json
片段里的约定与行为测试一致：out.push(...)，可用 setBusinessNow / $ / render。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import mutate_plan as mutate  # noqa: E402


def run_snippet(root: Path, snippet: Path) -> dict:
    script = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(%r) / 'local' / 'tests'))\n"
        "from fixtures.ui_harness import run_js\n"
        "snippet = Path(%r).read_text(encoding='utf-8')\n"
        "print('__OUT__' + json.dumps(run_js(snippet), ensure_ascii=False))\n"
    ) % (str(root), str(snippet))
    proc = subprocess.run([sys.executable, "-B", "-c", script], cwd=root,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise SystemExit("片段跑失败：\n" + proc.stderr[-2000:])
    marker = proc.stdout.rfind("__OUT__")
    return json.loads(proc.stdout[marker + len("__OUT__"):])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate")
    parser.add_argument("--snippet", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    candidates, _ = mutate.build_candidates()
    chosen = [item for item in candidates if item.cid == args.candidate]
    if not chosen:
        raise SystemExit(f"没有这个候选：{args.candidate}")
    candidate = chosen[0]
    snippet = Path(args.snippet)
    with tempfile.TemporaryDirectory(prefix="plan-probe-") as name:
        temp = Path(name)
        quiet = temp / "quiet"
        noisy = temp / "noisy"
        quiet.mkdir()
        mutate.copy_base(quiet)
        shutil.copytree(quiet, noisy)
        mutate.apply_candidate(noisy, candidate)
        before = run_snippet(quiet, snippet)
        after = run_snippet(noisy, snippet)
    same = before == after
    payload = {"candidate": candidate.as_dict(), "same": same, "before": before, "after": after}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print(f"候选 {candidate.cid} {candidate.kind} {candidate.function}: {candidate.line_text[:70]}")
        print(f"变异：{candidate.needle[:70]!r} -> {candidate.replacement[:40]!r}")
        print("输出一致" if same else "输出不同")
        for left, right in zip(before, after):
            if left != right:
                print("  未变异：" + json.dumps(left, ensure_ascii=False)[:600])
                print("  变异后：" + json.dumps(right, ensure_ascii=False)[:600])
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
