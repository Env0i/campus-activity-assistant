# -*- coding: utf-8 -*-
"""零执行函数名在测试里出现的次数（计划 plan-20261114-refactor-endpoint-evidence-fix 的 decisions D6）。

量什么：读本目录上一级 online.md 里 local/app.py 与 local/grab.py 的两份「一行都没执行到的函数」
清单（46 + 18 = 64 个），对每个函数取限定名里第一个点号之前的部分，数它作为完整单词
（左右两侧都不是字母、数字或下划线）在 local/tests 下全部 .py 文件文本里出现的次数。
只做文本统计，注释与字符串里的出现也计入（D6 字面口径：作为完整单词出现）。
清单从 online.md 原文解析，行格式为 `- `限定名`（起止行，N 行）`，所在文件取自最近的
「## local/…」标题；两份清单共 64 条，条数不是 64 时原样报出。
参照数：计划 decisions D6 写明指挥会话的参照是「64 个函数里 37 个大于 0」；
本脚本只把它打印出来对照，不参与任何计算。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/zero_exec_in_tests.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root():
    """先按「脚本位置上推四级」定位仓库根；脚本被复制到别处时改问 git。"""
    cand = HERE.parents[4] if len(HERE.parents) > 4 else None
    if cand is not None and (cand / ".git").exists():
        return cand
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         cwd=os.getcwd(), capture_output=True)
    if out.returncode == 0:
        return Path(out.stdout.decode("utf-8", "replace").strip())
    raise SystemExit("定位不到仓库根：请从仓库根运行本脚本")


REPO = _repo_root()
ONLINE = HERE.parent / "online.md"
TESTS = REPO / "local" / "tests"
# 参照数（出处：本计划 decisions D6；只用于打印对照，不参与计算）
REF_TOTAL = 64
REF_GT0 = 37

LIST_ITEM = re.compile(r"^- `(.+?)`（(\d+)-(\d+)，(\d+) 行）$")


def parse_online():
    """从 online.md 解析两份零执行清单：(文件, 限定名, 行数) 的列表。"""
    cur = None
    in_list = False
    items = []
    text = ONLINE.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    for ln in text.splitlines():
        if ln.startswith("## local/"):
            cur = ln[len("## "):].strip()
            in_list = False
        elif ln.startswith("一行都没执行到的函数"):
            in_list = True
        elif in_list:
            m = LIST_ITEM.match(ln)
            if m:
                items.append((cur, m.group(1), int(m.group(4))))
            elif ln.strip():
                in_list = False
    return items


def count_word(name, blob):
    """完整单词计数：左右两侧都不是字母、数字或下划线。"""
    pat = re.compile("(?<![A-Za-z0-9_])" + re.escape(name) + "(?![A-Za-z0-9_])")
    return len(pat.findall(blob))


def main():
    items = parse_online()
    blob = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted(TESTS.rglob("*.py")))
    counts = []
    for f, qual, nlines in items:
        base = qual.split(".")[0]
        counts.append((f, qual, nlines, count_word(base, blob)))
    gt0 = sum(1 for c in counts if c[3] > 0)
    print("## 零执行函数名在测试里出现的次数（H3 补充，本计划 decisions D6）")
    print()
    print("量什么：online.md 里 local/app.py 与 local/grab.py 的两份「一行都没执行到的函数」清单"
          f"（共 {len(items)} 个），对每个函数取限定名里第一个点号之前的部分，数它作为完整单词"
          "（左右两侧都不是字母、数字或下划线）在 local/tests 下全部 .py 文件文本里出现的次数；"
          "只做文本统计，注释与字符串里的出现也计入。清单从 online.md 原文解析。")
    print()
    print("| 文件 | 函数 | 行数 | 在测试里出现的次数 |")
    print("|---|---|---|---|")
    for f, qual, nlines, n in counts:
        print(f"| `{f}` | `{qual}` | {nlines} | {n} |")
    print()
    print(f"出现次数大于 0 的：{gt0} 个（共 {len(items)} 个）。")
    ref_ok = (len(items) == REF_TOTAL and gt0 == REF_GT0)
    print(f"对照：计划 decisions D6 的参照数是「{REF_TOTAL} 个函数里 {REF_GT0} 个大于 0」，"
          f"本次 {len(items)} 个里 {gt0} 个大于 0 -> {'一致' if ref_ok else '不一致，差在哪见口径疑点'}")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/zero_exec_in_tests.py`")


if __name__ == "__main__":
    main()
