#!/usr/bin/env python3
"""在临时副本里逐条破坏本批样子，确认样式测试会变红。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "design/evidence/2026-11-16/login-machine/scripts"))
from capsule_grid import copy_current  # noqa: E402


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise AssertionError(f"mutation target count: {path.name} {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="")


def mutate_rechecking(root: Path) -> None:
    replace_once(root / "local/ui/features/login/view.js",
                 'className: "is-ok is-spin",', 'className: "is-ok",')


def mutate_auto(root: Path) -> None:
    replace_once(root / "local/ui/features/login/view.js",
                 'className: "is-busy is-spin",', 'className: "is-busy",')


def mutate_unknown(root: Path) -> None:
    replace_once(root / "local/ui/features/login/view.js",
                 '  unknown: {\n    /* 学校接口没应答/网络异常：不能误报成「重新登录」，会话原样保留 */\n    className: "is-warn",',
                 '  unknown: {\n    /* 学校接口没应答/网络异常：不能误报成「重新登录」，会话原样保留 */\n    className: "is-none",')


def mutate_spin_animation(root: Path) -> None:
    replace_once(root / "local/ui/styles.css",
                 'animation: advspin .9s linear infinite; }\n.btn {',
                 '}\n.btn {')


def mutate_spin_order(root: Path) -> None:
    path = root / "local/ui/styles.css"
    old = '''.pill.is-busy i { background: var(--blue); animation: pulse 1.4s ease-in-out infinite; }
/* 转圈只换圆点，不新增元素；沿用 advspin 动画让减少动画规则仍可停住。 */
.pill.is-spin i { background: transparent; border: 2px solid currentColor; border-right-color: transparent; box-sizing: border-box; animation: advspin .9s linear infinite; }
'''
    new = '''/* 转圈只换圆点，不新增元素；沿用 advspin 动画让减少动画规则仍可停住。 */
.pill.is-spin i { background: transparent; border: 2px solid currentColor; border-right-color: transparent; box-sizing: border-box; animation: advspin .9s linear infinite; }
.pill.is-busy i { background: var(--blue); animation: pulse 1.4s ease-in-out infinite; }
'''
    replace_once(path, old, new)


def mutate_card_rechecking(root: Path) -> None:
    replace_once(root / "local/ui/views/status-cards.js",
                 '  rechecking: { tone: "ok", big: "登录有效" },\n', '')


def mutate_card_needs_code(root: Path) -> None:
    replace_once(root / "local/ui/views/status-cards.js",
                 '  needs_code: { tone: "warn", big: "要你输验证码" },\n', '')


def mutate_card_tone(root: Path) -> None:
    replace_once(root / "local/ui/views/status-cards.js",
                 '{ tone: "warn", big: "要你输验证码" }',
                 '{ tone: "bad", big: "要你输验证码" }')


def mutate_banner_condition(root: Path) -> None:
    replace_once(root / "local/ui/features/login/view.js",
                 '+ (busy ? "报名计划还在等，开放前 100 秒以前输完就照常继续。"',
                 '+ (!busy ? "报名计划还在等，开放前 100 秒以前输完就照常继续。"')


def mutate_banner_copy(root: Path) -> None:
    replace_once(root / "local/ui/features/login/view.js",
                 '+ (busy ? "报名计划还在等，开放前 100 秒以前输完就照常继续。"\n'
                 '        : "电脑需要你输入验证码才能继续登录。")',
                 '+ (busy ? "电脑需要你输入验证码才能继续登录。"\n'
                 '        : "报名计划还在等，开放前 100 秒以前输完就照常继续。")')


MUTATIONS = [
    ("rechecking-spin", mutate_rechecking),
    ("auto-spin", mutate_auto),
    ("unknown-amber", mutate_unknown),
    ("spin-no-animation", mutate_spin_animation),
    ("spin-before-busy", mutate_spin_order),
    ("card-no-rechecking-override", mutate_card_rechecking),
    ("card-no-needs-code-override", mutate_card_needs_code),
    ("card-wrong-needs-code-tone", mutate_card_tone),
    ("banner-inverted-busy", mutate_banner_condition),
    ("banner-swapped-copy", mutate_banner_copy),
]


def run_tests(root: Path) -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "local/tests",
         "-p", "test_login_looks.py"],
        cwd=root, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    output = proc.stdout + proc.stderr
    failed = re.search(r"^(?:FAIL|ERROR):\s+([^\r\n]+)", output, re.MULTILINE)
    return {"exit_code": proc.returncode, "first_failure": failed.group(1) if failed else ""}


def main() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="login-looks-mutate-") as temp:
        base = Path(temp) / "repo"
        base.mkdir()
        copy_current(base)
        source_test = ROOT / "local/tests/test_login_looks.py"
        target_test = base / "local/tests/test_login_looks.py"
        target_test.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_test, target_test)
        for name, mutation in MUTATIONS:
            case = Path(temp) / name
            shutil.copytree(base, case)
            mutation(case)
            outcome = run_tests(case)
            results.append({"name": name, **outcome, "red": outcome["exit_code"] != 0})
    print(json.dumps({"mutations": results,
                      "all_red": all(item["red"] for item in results)},
                     ensure_ascii=False, sort_keys=True))
    return 0 if all(item["red"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
