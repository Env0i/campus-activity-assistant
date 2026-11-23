#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""核对冻结 EXE 包内的手机页资源与工作区源码逐字节一致。

只看 PyInstaller 归档里的 ui/m 成员，不启动 EXE、不读真实配置与数据目录。
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[5]
EXE = ROOT / "dist" / "campus-grab-exe" / "campus-activity-watch.exe"
SRC = ROOT / "local" / "ui" / "m"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    if not EXE.is_file():
        print("[exe-assets] 找不到 EXE：%s" % EXE)
        return 1
    reader = CArchiveReader(str(EXE))
    members = {}
    for name in reader.toc:
        norm = str(name).replace("\\", "/")
        if norm.startswith("ui/m/") and not norm.endswith("/"):
            members[norm.split("/")[-1]] = reader.extract(name)
    expected = {p.name: p for p in SRC.iterdir() if p.is_file()}
    missing = sorted(set(expected) - set(members))
    extra = sorted(set(members) - set(expected))
    mismatch = []
    for name, path in sorted(expected.items()):
        if name in members and sha(members[name]) != sha(path.read_bytes()):
            mismatch.append(name)
    print("[exe-assets] 包内 ui/m 成员 %d 个，工作区源码 %d 个" % (len(members), len(expected)))
    if missing:
        print("[exe-assets] 包内缺少：%s" % ", ".join(missing))
    if extra:
        print("[exe-assets] 包内多出：%s" % ", ".join(extra))
    if mismatch:
        print("[exe-assets] 内容不一致：%s" % ", ".join(mismatch))
    ok = not (missing or extra or mismatch)
    print("[exe-assets] 结论：%s" % ("一致" if ok else "不一致"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
