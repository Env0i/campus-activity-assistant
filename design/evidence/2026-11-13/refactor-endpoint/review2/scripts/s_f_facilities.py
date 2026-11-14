# -*- coding: utf-8 -*-
"""review2 表 F 独立复算：工程设施盘点（计划 D8 口径：只查有没有）。

从仓库根运行：python -B design/evidence/2026-11-13/refactor-endpoint/review2/scripts/s_f_facilities.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
cand = HERE.parents[5] if len(HERE.parents) > 5 else None
if cand and (cand / ".git").exists():
    REPO = cand
else:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    REPO = Path(out.stdout.decode().strip())

ROOT_FILES = ["pyproject.toml", "setup.cfg", "package.json", ".editorconfig",
              ".pre-commit-config.yaml", "mypy.ini", ".mypy.ini", ".coveragerc",
              ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
              "eslint.config.js", "eslint.config.mjs", ".prettierrc",
              ".prettierrc.json", ".prettierrc.toml", "prettier.config.js"]
HOOK_DIRS = [".githooks", ".github/workflows"]


def tracked():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPO), capture_output=True, check=True)
    exts = (".py", ".js", ".mjs", ".md", ".toml", ".cfg", ".ini", ".txt",
            ".yaml", ".yml", ".json", ".bat", ".ps1", ".sh", ".html")
    return sorted(n for n in out.stdout.decode("utf-8").split("\0")
                  if n and n.endswith(exts))


def main():
    print("## review2 表 F 独立复算")
    print()
    print("### 存在性")
    print()
    print("| 项目 | 结果 |")
    print("|---|---|")
    for n in ROOT_FILES:
        print(f"| {n} | {'存在' if (REPO / n).exists() else '无'} |")
    for d in HOOK_DIRS:
        p = REPO / d
        if p.exists():
            names = "、".join(sorted(x.name for x in p.iterdir()))
            print(f"| {d}/ | {names} |")
        else:
            print(f"| {d}/ | 无 |")
    print()
    print("### requirements 文件（总行 / 非注释非空 / 未锁 == 行数）")
    print()
    reqs = []
    for dirpath, dirnames, filenames in REPO.walk():
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "dist", "data")]
        for f in filenames:
            if f.startswith("requirements") and f.endswith(".txt"):
                reqs.append((dirpath / f).relative_to(REPO).as_posix())
    for rel in sorted(reqs):
        lines = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        specs = [x.strip() for x in lines if x.strip() and not x.strip().startswith("#")]
        unlocked = [x for x in specs if "==" not in x.split(";")[0].split(" ")[0]]
        print(f"- `{rel}`：{len(lines)} / {len(specs)} / {len(unlocked)}"
              + (f"；未锁：{'；'.join(unlocked)}" if unlocked else ""))
    print()
    print("### tools/release.py 单元测试调用与 --prepare 行")
    print()
    rel_text = (REPO / "tools/release.py").read_text(encoding="utf-8", errors="replace")
    hits = [(i, x.strip()) for i, x in enumerate(rel_text.splitlines(), 1)
            if re.search(r"\bunittest\b|\bpytest\b|compileall", x)]
    print(f"- 含 unittest/pytest/compileall 的行：{'无' if not hits else ''}")
    for i, _ in hits:
        print(f"  - tools/release.py:{i}")
    preps = [i for i, x in enumerate(rel_text.splitlines(), 1) if "--prepare" in x]
    print(f"- 含 --prepare 的行数：{len(preps)}（tools/release.py:{min(preps) if preps else '-'} 起）")
    print()
    print(f"- tools/code_shape/check.py 存在：{(REPO / 'tools/code_shape/check.py').exists()}")
    print()
    rows = []
    for name in tracked():
        try:
            for i, x in enumerate((REPO / name).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if re.search("ruff", x, re.I):
                    rows.append(f"{name}:{i}")
        except OSError:
            pass
    print(f"### ruff 字符串查找（git 跟踪文本文件，共 {len(rows)} 行）")
    print()
    for r in rows:
        print(f"- {r}")


if __name__ == "__main__":
    main()
