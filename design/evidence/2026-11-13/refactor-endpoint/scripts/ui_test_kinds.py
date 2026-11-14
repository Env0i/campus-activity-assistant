# -*- coding: utf-8 -*-
"""表 E2：界面测试函数分类（计划 plan-20261114-refactor-endpoint-evidence-fix 的 decisions D7）。

量什么：表 E 的同一批 17 个文件（local/tests 下文件名以 test_ui_ 开头的测试文件，加
test_phone_ui.py；文件清单与 ui_assertions.py 同一条规则）。先用 ast 找「运行函数」：
函数体里调用了 run_js（调用名为 run_js 的 Name 或 Attribute），或函数源码段里同时出现
subprocess 和 node 两个词；再把调用了运行函数的函数也算作运行函数，反复到不再增加为止
（调用按名字匹配，只看同一文件里定义的函数名）。然后对每个 test_ 开头的函数分两类：
它是运行函数的记「跑 node」，其余记「不跑 node」。每个文件一行，列为 测试函数数、
跑 node、不跑 node；表尾合计。函数收集用 ast.walk（含类方法与嵌套函数），
test_ 函数也按同一收集方式取。
参照数：计划 decisions D7 写明指挥会话的参照是合计 748、552、196，其中 test_phone_ui.py
210、195、15、test_ui_contract_components.py 15、0、15；本脚本只把它打印出来对照，
不参与任何计算。

从仓库根运行：
    python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_test_kinds.py
"""
import ast
import os
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
TESTS = REPO / "local" / "tests"
# 参照数（出处：本计划 decisions D7；只用于打印对照，不参与计算）
REF_TOTAL = (748, 552, 196)
REF_PHONE = (210, 195, 15)
REF_COMPONENTS = (15, 0, 15)


def iter_files():
    """表 E 的同一批文件：test_ui_*.py 排序后加 test_phone_ui.py。"""
    names = sorted(TESTS.glob("test_ui_*.py"))
    phone = TESTS / "test_phone_ui.py"
    if phone.exists():
        names.append(phone)
    return names


def call_names(node):
    """函数节点子树（含嵌套 def）里全部调用的名字：Name.id 或 Attribute.attr。"""
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def src_segment(src, node):
    seg = ast.get_source_segment(src, node)
    if seg is not None:
        return seg
    lines = src.replace("\r\n", "\n").splitlines()
    return "\n".join(lines[node.lineno - 1: node.end_lineno])


def is_seed_runner(f, src):
    """种子运行函数：函数体（含嵌套 def）调用了 run_js，或函数源码段同时含 subprocess 与 node。"""
    if "run_js" in call_names(f):
        return True
    seg = src_segment(src, f)
    return "subprocess" in seg and "node" in seg


def classify_file(p):
    src = p.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    names = {f.name for f in funcs}
    runners = {f.name for f in funcs if is_seed_runner(f, src)}
    changed = True
    while changed:  # 传播：调用了运行函数的也算运行函数，反复到不再增加
        changed = False
        for f in funcs:
            if f.name in runners:
                continue
            if call_names(f) & runners:
                runners.add(f.name)
                changed = True
    tfuncs = [f for f in funcs if f.name.startswith("test_")]
    n_run = sum(1 for f in tfuncs if f.name in runners)
    return len(tfuncs), n_run, len(tfuncs) - n_run


def main():
    rows = []
    for p in iter_files():
        rel = p.relative_to(REPO).as_posix()
        total, run, not_run = classify_file(p)
        rows.append((rel, total, run, not_run))
    total_all = sum(r[1] for r in rows)
    run_all = sum(r[2] for r in rows)
    not_all = total_all - run_all
    print("## 表 E2：界面测试函数分类（本计划 decisions D7）")
    print()
    print("量什么：表 E 的同一批 17 个文件（test_ui_*.py 加 test_phone_ui.py，清单与 ui_assertions.py "
          "同一条规则）。ast 找「运行函数」：函数体（含嵌套 def）调用了 run_js，或函数源码段里同时出现 "
          "subprocess 和 node；再把调用了运行函数的函数也算作运行函数，反复到不再增加（按名字匹配，"
          "只看同一文件里定义的函数名）。每个 test_ 开头的函数：是运行函数记「跑 node」，其余记"
          "「不跑 node」。函数收集用 ast.walk（含类方法）。")
    print()
    print("| 文件 | 测试函数数 | 跑 node | 不跑 node |")
    print("|---|---|---|---|")
    for rel, total, run, not_run in rows:
        print(f"| `{rel}` | {total} | {run} | {not_run} |")
    print(f"| 合计 | {total_all} | {run_all} | {not_all} |")
    print()
    ok = run_all + not_all == total_all
    print(f"自校：跑 node + 不跑 node = 测试函数数（{run_all} + {not_all} = {total_all}）-> "
          f"{'成立' if ok else '不成立'}")
    ref_ok = ((total_all, run_all, not_all) == REF_TOTAL)
    phone_row = next(r for r in rows if r[0].endswith("test_phone_ui.py"))
    comp_row = next(r for r in rows if r[0].endswith("test_ui_contract_components.py"))
    ref_ok = ref_ok and (phone_row[1:] == REF_PHONE) and (comp_row[1:] == REF_COMPONENTS)
    print(f"对照：计划 decisions D7 参照数 合计 {REF_TOTAL[0]}、{REF_TOTAL[1]}、{REF_TOTAL[2]}，"
          f"test_phone_ui.py {REF_PHONE[0]}、{REF_PHONE[1]}、{REF_PHONE[2]}，"
          f"test_ui_contract_components.py {REF_COMPONENTS[0]}、{REF_COMPONENTS[1]}、"
          f"{REF_COMPONENTS[2]}；本次 合计 {total_all}、{run_all}、{not_all}，"
          f"test_phone_ui.py {phone_row[1]}、{phone_row[2]}、{phone_row[3]}，"
          f"test_ui_contract_components.py {comp_row[1]}、{comp_row[2]}、{comp_row[3]} -> "
          f"{'逐项一致' if ref_ok else '不一致，差在哪见口径疑点'}")
    print()
    print("复跑命令：`python -B design/evidence/2026-11-13/refactor-endpoint/scripts/ui_test_kinds.py`")


if __name__ == "__main__":
    main()
