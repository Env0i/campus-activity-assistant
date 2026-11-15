#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重新登录对话框的接线变异：把每一处事件绑定的动作换成空语句，看它自己那条用例会不会红。

做法与 design/evidence 里手机面板那一批一样：把仓库的 local/ 目录整个复制到
tempfile.mkdtemp() 下（不带 local/data 与任何 config.json），在副本里按「文件 + 那一行的
原文」替换成空动作，跑对应用例，再还原字节；仓库里的文件绝不改动。

搬文件那一批前后文件路径不同，用 --phase pre|post 选路径表：pre 指向 views/relogin.js，
post 指向 features/login/actions-relogin.js。行清单与用例名两阶段完全一样。

只读仓库、只写临时目录；输出只有「哪一处、跑哪条用例、红没红、第一条失败断言」。

@author Author
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]

# 逻辑文件 → 两阶段各自的真实路径
PHASE_PATHS = {
    "pre": {
        "relogin": "local/ui/views/relogin.js",
        "app": "local/ui/app.js",
    },
    "post": {
        "relogin": "local/ui/features/login/actions-relogin.js",
        "app": "local/ui/main.js",
    },
}

# 登录按钮那一处搬到了 main.js，原文与替换串跟着换（同一句接线的两种写法）
PHASE_BINDINGS = {
    "post": {
        "btn-login": (
            '$("#btn-login").addEventListener("click", loginEntry);',
            '$("#btn-login").addEventListener("click", () => {});',
        ),
    },
}

# 每一处绑定：它自己那条用例、要替换的那一行原文、换成什么
BINDINGS = [
    ("btn-rl-auto", "relogin",
     '  on("btn-rl-auto", () => { void autoReloginOnce(); });',
     '  on("btn-rl-auto", () => {});',
     "test_auto_login_button_asks_the_backend_once"),
    ("btn-lg-next", "relogin",
     '  on("btn-lg-next", submitReloginForm);',
     '  on("btn-lg-next", () => {});',
     "test_next_button_starts_relogin_with_the_typed_account"),
    ("btn-rl-code", "relogin",
     '  on("btn-rl-code", () => { void submitReloginCode(); });',
     '  on("btn-rl-code", () => {});',
     "test_code_button_submits_the_typed_code"),
    ("btn-rl-browser", "relogin",
     '  on("btn-rl-browser", () => { closeRelogin().then(() => doLogin()); });',
     '  on("btn-rl-browser", () => {});',
     "test_browser_button_closes_then_opens_the_school_page"),
    ("btn-bad-browser", "relogin",
     '  on("btn-bad-browser", () => { closeRelogin().then(() => doLogin()); });',
     '  on("btn-bad-browser", () => {});',
     "test_bad_password_browser_button_also_opens_the_school_page"),
    ("btn-bad-update", "relogin",
     '  on("btn-bad-update", () => { if (S.relogin) S.relogin.fromLogin = false; reloginPickWay("here"); });',
     '  on("btn-bad-update", () => {});',
     "test_update_password_button_returns_to_the_form"),
    ("btn-lg-back", "relogin",
     '  on("btn-lg-back", () => { if (S.relogin) S.relogin.fromLogin = false; reloginStep("login"); });',
     '  on("btn-lg-back", () => {});',
     "test_back_button_returns_from_the_captcha_step"),
    ("btn-lg-webopen", "relogin",
     '  on("btn-lg-webopen", reloginOpenSchoolPage);',
     '  on("btn-lg-webopen", () => {});',
     "test_school_page_button_waits_for_the_browser"),
    ("btn-rl-cancel", "relogin",
     '  on("btn-rl-cancel", closeRelogin);',
     '  on("btn-rl-cancel", () => {});',
     "test_cancel_closes_the_dialog_and_cancels_the_flow"),
    ("btn-rl-done", "relogin",
     '  on("btn-rl-done", closeRelogin);',
     '  on("btn-rl-done", () => {});',
     "test_done_closes_the_dialog_without_touching_the_backend"),
    ("lg-here", "relogin",
     '  on("lg-here", () => reloginPickWay("here"));',
     '  on("lg-here", () => {});',
     "test_way_card_here_shows_the_form_again"),
    ("lg-web", "relogin",
     '  on("lg-web", () => reloginPickWay("browser"));',
     '  on("lg-web", () => {});',
     "test_way_card_browser_hides_the_form"),
    ("lg-eye", "relogin",
     '  on("lg-eye", reloginTogglePass);',
     '  on("lg-eye", () => {});',
     "test_eye_button_shows_the_password_as_plain_text"),
    ("rl-user input", "relogin",
     '  if (userInput && userInput.addEventListener) userInput.addEventListener("input", reloginNextReady);',
     '  if (userInput && userInput.addEventListener) userInput.addEventListener("input", () => {});',
     "test_typing_the_account_enables_next"),
    ("rl-pass input", "relogin",
     '    passInput.addEventListener("input", reloginNextReady);',
     '    passInput.addEventListener("input", () => {});',
     "test_typing_the_password_enables_next"),
    ("rl-pass Enter", "relogin",
     '      if (event.key === "Enter" && reloginWay() === "here") { event.preventDefault(); submitReloginForm(); }',
     '      if (event.key === "Enter" && reloginWay() === "here") { event.preventDefault(); }',
     "test_enter_in_the_password_field_submits_the_form"),
    ("rl-save change", "relogin",
     '  if (saveBox && saveBox.addEventListener) saveBox.addEventListener("change", reloginPaintWay);',
     '  if (saveBox && saveBox.addEventListener) saveBox.addEventListener("change", () => {});',
     "test_ticking_save_rewrites_the_explanation"),
    ("rl-code input", "relogin",
     '    codeInput.addEventListener("input", reloginCodeReady);',
     '    codeInput.addEventListener("input", () => {});',
     "test_four_digit_code_enables_the_login_button"),
    ("rl-code Enter", "relogin",
     '      if (event.key === "Enter") { event.preventDefault(); void submitReloginCode(); }',
     '      if (event.key === "Enter") { event.preventDefault(); }',
     "test_enter_in_the_code_field_submits_it"),
    ("dlg-relogin cancel", "relogin",
     '    dlg.addEventListener("cancel", (event) => { event.preventDefault(); closeRelogin(); });',
     '    dlg.addEventListener("cancel", (event) => { event.preventDefault(); });',
     "test_escape_on_the_dialog_closes_it"),
    ("btn-login", "app",
     '$("#btn-login").addEventListener("click", loginEntry);',
     '$("#btn-login").addEventListener("click", () => {});',
     "test_expired_login_button_opens_the_relogin_dialog"),
]

TEST_FILE = "test_ui_relogin_wiring.py"
NOT_VISIBLE = ("SyntaxError", "IndentationError", "ImportError", "ModuleNotFoundError")


def tree_files(root: Path) -> list[str]:
    """导出树（不是 git 仓库）里的 local/ 清单，跳过 data 与配置文件。"""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root / "local"):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git", "data", "bin")]
        for name in filenames:
            rel = Path(dirpath, name).relative_to(root).as_posix()
            if rel.endswith("config.json") or rel.endswith("_site_build.py"):
                continue
            out.append(rel)
    return out


def copy_repo(dest: Path, source: Path | None = None) -> None:
    """按 git ls-files 的清单复制，只带 local/（不带 data 与配置文件）。

    给了 source（开工 HEAD 的导出树）就按那棵树复制，用来量「搬之前」。
    """
    if source is not None:
        names = tree_files(source)
        for name in names:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / name, target)
        return
    names = []
    for extra in ([], ["--others", "--exclude-standard"]):
        raw = subprocess.run(["git", "ls-files", "-z", *extra, "local/"], cwd=str(REPO),
                             capture_output=True, check=True).stdout
        names.extend(part.decode("utf-8") for part in raw.split(b"\0") if part)
    for name in names:
        if name.startswith("local/data/"):
            continue
        source = REPO / name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def read_text(path: Path) -> str:
    """读成 LF 归一后的文本，并记住原来是 CRLF 还是 LF。"""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), ("\r\n" in raw)


def write_text(path: Path, text: str, crlf: bool) -> None:
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def child_env() -> dict:
    """子进程要继承 PATH，否则找不到 node，界面用例会被整体跳过。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_case(root: Path, case: str) -> tuple[bool, str]:
    """跑一条用例；返回（是否有用例变红、第一条失败断言的说明）。"""
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover",
         "-s", "local/tests", "-p", TEST_FILE, "-k", case],
        cwd=str(root), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=child_env())
    output = (proc.stdout or "") + (proc.stderr or "")
    failed = re.findall(r"^(?:FAIL|ERROR): (\S+)", output, re.M)
    if any(marker in output for marker in NOT_VISIBLE):
        return True, "红在了别的错误上（语法或导入），不算守住"
    if not failed:
        return False, ""
    assertion = ""
    for line in output.splitlines():
        if "AssertionError" in line:
            assertion = line.strip()
            break
    return True, assertion or failed[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="重新登录对话框接线变异")
    parser.add_argument("--phase", choices=("pre", "post"), default="pre")
    parser.add_argument("--only", action="append", default=[], help="只跑这几处（名字片段）")
    parser.add_argument("--tree", default="", help="用开工 HEAD 的导出树量「搬之前」")
    args = parser.parse_args()

    paths = PHASE_PATHS[args.phase]
    picked = [b for b in BINDINGS if not args.only or any(k in b[0] for k in args.only)]
    root = Path(tempfile.mkdtemp(prefix="mutate-relogin-wiring-"))
    copy_repo(root, Path(args.tree) if args.tree else None)
    if args.tree:
        # 接线测试是本批新加的，开工 HEAD 的树上没有：从工作区补进来
        source_test = REPO / "local/tests" / TEST_FILE
        (root / "local/tests").mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_test, root / "local/tests" / TEST_FILE)

    killed = survived = 0
    for name, key, old, new, case in picked:
        old, new = PHASE_BINDINGS.get(args.phase, {}).get(name, (old, new))
        target = root / paths[key]
        text, crlf = read_text(target)
        if text.count(old) != 1:
            print("[bad] %-20s 原文出现 %d 次，无法定位" % (name, text.count(old)))
            survived += 1
            continue
        write_text(target, text.replace(old, new), crlf)
        try:
            red, note = run_case(root, case)
        finally:
            write_text(target, text, crlf)
        if red:
            killed += 1
            print("[red] %-20s %s -> %s" % (name, case, note[:110]))
        else:
            survived += 1
            print("[alive] %-20s %s 没有变红" % (name, case))

    print("变异条数：%d；存活：%d" % (len(picked), survived))
    shutil.rmtree(root, ignore_errors=True)
    return 0 if survived == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
