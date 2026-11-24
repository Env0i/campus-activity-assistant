#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发版守卫：tools/release/release.py 的 --prepare / --publish 动手前把工程守卫整个跑一遍。

挡的是「发出去的东西没过工程底线」：大小名单、三道分层/形状守卫测试、ruff、本机版全量。
依次执行，有一步失败立即停——返回值点名失败的那一步，后面的步骤不再跑，没有跳过开关。
每一步用子进程跑（超时按步给上限），子进程输出攒齐后原样转发，守卫不改写任何输出。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# 每步的超时秒数：全量在共享盘上要跑几分钟，上限放宽到一小时防挂死。
TIMEOUT_SHAPE = 600
TIMEOUT_GUARD_TESTS = 900
TIMEOUT_RUFF = 600
TIMEOUT_FULL = 3600

# 构建前的站点地址检查：正式构建缺 SCHOOL_ORIGIN 或不是 https 直接失败。
# 从 tools/release/release.py 搬来（函数体不改），release.py 经模块属性继续用旧名字。
_SITE_ORIGIN_RE = re.compile(r"^https://[^/\s]+(/[^\s]*)?$")


def run_command(command: list[str], timeout: int, cwd: Path) -> tuple[int, str]:
    """跑一步子进程，返回 (退出码, 合并输出)；超时按失败计（退出码 124）。

    模块级名字：测试用替身替换它，不真跑子进程（tools/release/tests/test_release_guards.py）。
    """
    try:
        done = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        pieces = [piece for piece in (exc.stdout, exc.stderr) if piece]
        pieces.append("[守卫] 超过 %d 秒未结束，按失败处理" % timeout)
        return 124, "\n".join(str(piece) for piece in pieces)
    return done.returncode, "\n".join(piece for piece in (done.stdout, done.stderr) if piece)


class _Step:
    """守卫的一步：显示名 + 命令 + 超时。run 负责转发输出并按退出码定输赢。"""

    def __init__(self, name: str, command: list[str], timeout: int, cwd: Path) -> None:
        self.name = name
        self.command = command
        self.timeout = timeout
        self.cwd = cwd

    def run(self) -> bool:
        code, output = run_command(self.command, self.timeout, self.cwd)
        if output.strip():
            print(output, end="" if output.endswith("\n") else "\n", flush=True)
        if code == 0:
            return True
        if "No module named ruff" in output:
            print("[守卫] ruff 没装：先 python -m pip install -r requirements-dev.txt",
                  flush=True)
        return False


def site_origin_for_build(preview: bool) -> str:
    """读取构建环境 SCHOOL_ORIGIN 并校验；正式构建缺值或不是 https 直接失败。

    地址只来自构建环境变量，绝不写进仓库任何文件；值本身也不进 manifest。
    预览构建（来源脏）允许缺席，产物仅供人工验收，manifest 记 site_configured=false。
    """
    origin = (os.environ.get("SCHOOL_ORIGIN") or "").strip()
    if not origin:
        if preview:
            print("[prepare] 预览构建：未设 SCHOOL_ORIGIN，发布物不含内置站点地址")
            return ""
        raise SystemExit("[prepare] 正式构建缺 SCHOOL_ORIGIN：站点地址必须在构建环境注入，"
                         "不写进仓库；本次不产出任何资产")
    if not _SITE_ORIGIN_RE.match(origin):
        if preview:
            print("[prepare] 预览构建：SCHOOL_ORIGIN 不是 https 地址，按未注入处理")
            return ""
        raise SystemExit("[prepare] SCHOOL_ORIGIN 必须是 https 站点根地址（不带查询或空白）；"
                         "本次不产出任何资产")
    return origin.rstrip("/")


def guard_steps(root: Path) -> list[_Step]:
    """守卫步骤表，顺序即口径：形状 → 三道守卫测试 → ruff → 本机版全量。

    命令与 AGENTS.md「命令」一节同款；解释器用当前进程的 python，工作目录是仓库根
    （测试按 local.xxx 导入，必须从仓库根跑）。单文件守卫测试沿用 discover 指定文件名的写法。
    """
    root = Path(root)
    tests = str(root / "local" / "tests")
    discover = ("-m", "unittest", "discover", "-s", tests)
    return [
        _Step("代码形状大小比对", [sys.executable, "-B", "-X", "utf8",
                                  str(root / "tools" / "code_shape" / "check.py")],
              TIMEOUT_SHAPE, root),
        _Step("守卫测试 test_code_shape", [sys.executable, "-B", *discover,
                                           "-p", "test_code_shape.py", "-v"],
              TIMEOUT_GUARD_TESTS, root),
        _Step("守卫测试 test_layer_boundaries", [sys.executable, "-B", *discover,
                                                 "-p", "test_layer_boundaries.py", "-v"],
              TIMEOUT_GUARD_TESTS, root),
        _Step("守卫测试 test_ui_layers", [sys.executable, "-B", *discover,
                                          "-p", "test_ui_layers.py", "-v"],
              TIMEOUT_GUARD_TESTS, root),
        _Step("ruff 静态检查", [sys.executable, "-m", "ruff", "check",
                                "local", "server", "tools"], TIMEOUT_RUFF, root),
        _Step("本机版全量", [sys.executable, "-B", *discover, "-p", "test_*.py", "-v"],
              TIMEOUT_FULL, root),
    ]


def run_guards(root: Path) -> tuple[bool, str | None]:
    """依次跑守卫：全过返回 (True, None)；有一步失败返回 (False, 那一步的名字) 并停。

    失败即停：发版要的是全绿，半绿说明底线已经破了，把剩下的跑完没有意义。
    """
    for step in guard_steps(root):
        print("[守卫] %s ..." % step.name, flush=True)
        if step.run():
            print("[守卫] 通过：%s" % step.name, flush=True)
            continue
        print("[守卫] 没过：%s（后面的步骤不再跑）" % step.name, flush=True)
        return False, step.name
    return True, None
