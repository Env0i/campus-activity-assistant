#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据目录审计探针：矩阵测试是否还碰真实数据根，逐事件数出来。

在测试进程里装 sys.addaudithook，只统计 7 类事件（open / os.mkdir /
os.listdir / os.scandir / os.remove / os.rename / os.replace）里落在真实
数据根上的那部分。真实根取 runtime_paths.DATA_DIR 的模块级真值（测试夹具
只 patch app 模块属性，动不到它）。路径匹配认 Z 盘与 UNC 两种写法：先比
normcase(realpath(...)) 的字符串键，再沿事件路径的祖先链用 (st_dev, st_ino)
做一层 inode 身份兜底（stat 失败就跳过）。钩子内自己调 os.stat/realpath 前
用线程内重入标志防递归。输出只有事件类型、次数与去重后的文件名（basename），
绝不打印任何路径。零事件退出码 0，非零事件退出码 1。

用法（从仓库根，装齐依赖的解释器）：
python -B design/evidence/2026-11-17/api-guards/scripts/data_dir_probe.py

@author Author
"""
from __future__ import annotations

import os
import sys
import threading
import unittest
from pathlib import Path

TRACKED = ("open", "os.mkdir", "os.listdir", "os.scandir",
           "os.remove", "os.rename", "os.replace")

_REPO = Path(__file__).resolve().parents[5]


class _Probe:
    """审计钩子的载体：计数、匹配与报告，全程不输出路径。"""

    def __init__(self, real_root):
        self._key = os.path.normcase(os.path.realpath(str(real_root)))
        try:
            info = os.stat(str(real_root))
            self._ident = (info.st_dev, info.st_ino)
        except OSError:
            self._ident = None
        self.counts = {name: 0 for name in TRACKED}
        self.files = {name: set() for name in TRACKED}
        self._local = threading.local()

    # ---------- 匹配：字符串键在前，祖先链 inode 兜底在后 ----------

    def _hit(self, raw):
        """事件路径落在真实数据根内则返回其文件名（basename），否则 None。"""
        try:
            text = os.fspath(raw)
        except TypeError:
            return None
        if isinstance(text, bytes):
            try:
                text = os.fsdecode(text)
            except Exception:
                return None
        if getattr(self._local, "busy", False):
            return None
        self._local.busy = True
        try:
            try:
                probe = os.path.normcase(os.path.realpath(text))
            except OSError:
                probe = os.path.normcase(os.path.abspath(text))
            if probe == self._key or probe.startswith(self._key + os.sep):
                return os.path.basename(text.rstrip("/\\") or text)
            if self._ident is not None and self._chain_hits(text):
                return os.path.basename(text.rstrip("/\\") or text)
            return None
        finally:
            self._local.busy = False

    def _chain_hits(self, text):
        """事件路径本身或其祖先的 (st_dev, st_ino) 与真实根相同即算命中。"""
        cur = os.path.abspath(text)
        for _ in range(64):
            try:
                info = os.stat(cur)
            except OSError:
                return False
            if (info.st_dev, info.st_ino) == self._ident:
                return True
            parent = os.path.dirname(cur)
            if parent == cur:
                return False
            cur = parent
        return False

    # ---------- 钩子 ----------

    def hook(self, event, args):
        if event not in TRACKED:
            return
        if event in ("os.rename", "os.replace") and len(args) >= 2:
            paths = (args[0], args[1])
        else:
            paths = args[:1]
        for raw in paths:
            name = self._hit(raw)
            if name is not None:
                self.counts[event] += 1
                self.files[event].add(name)

    # ---------- 报告（只有次数与文件名） ----------

    def report(self):
        total = sum(self.counts.values())
        for event in TRACKED:
            if not self.counts[event]:
                continue
            names = "、".join(sorted(self.files[event]))
            print("%s: %d 次（文件：%s）" % (event, self.counts[event], names))
        print("真实数据根上的事件总数：%d" % total)
        return 0 if total == 0 else 1


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(_REPO / "local"))
    import runtime_paths  # 真实数据根的模块级真值：夹具 patch 不到它
    probe = _Probe(runtime_paths.DATA_DIR)
    sys.addaudithook(probe.hook)
    program = unittest.main(
        module=None, exit=False, verbosity=0,
        argv=[sys.argv[0], "discover", "-s", str(_REPO / "local" / "tests"),
              "-p", "test_busy_matrix.py"])
    result = program.result
    print("矩阵测试：%d 用例，失败 %d、错误 %d、跳过 %d"
          % (result.testsRun, len(result.failures), len(result.errors),
             len(result.skipped)))
    return probe.report()


if __name__ == "__main__":
    sys.exit(main())
