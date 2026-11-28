#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 PyInstaller 构建本机版 EXE；脚本只构建，不自动安装 PyInstaller。

构建产物支持两种形态：
- onedir（版本目录）：主程序排除重依赖，grab-worker 以目录形态（--contents-directory .）
  放在 <版本目录>/_internal/w/ 并清理 playwright/driver/package/lib/tools/skills 文档，
  同时生成 update-launcher.exe 及其输入指纹，并校验版本目录内相对路径长度上限。
- onefile（独立单 EXE）：先构建单文件 grab-worker，再把它作为普通数据资源与 VERSION
  一起打进主程序资源根，使单 EXE 拷到任何空目录都能自足，不依赖 EXE 旁外置 worker。
资源落点两种模式同源：onedir 在 <exe>/_internal/（PyInstaller 6.x 的 _MEIPASS），
onefile 在运行期解包根；主程序内执行的是完整既有 worker，不重新分析其依赖。

版本号来自仓库根的 VERSION（唯一来源），并随 --add-data 打进冻结资源根，
运行时 app.py 按 RESOURCE_ROOT/VERSION 读到同一个值。

@author Author
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# 脚本在 local/build/：local/（运行模块、ui/、README）是上一级，仓库根再上一级
LOCAL = Path(__file__).resolve().parent.parent
PROJECT = LOCAL.parent
OUT = PROJECT / "dist" / "campus-grab-exe"
OUT_ONEDIR = PROJECT / "dist" / "campus-grab-exe-onedir"
WORK = PROJECT / "dist" / ".pyinstaller-work"
VERSION_FILE = PROJECT / "VERSION"
# component_packages._load_sibling 用 importlib 动态加载同级模块，PyInstaller
# 静态分析看不到这些 import；不显式 hidden-import，冻结后启动即 ModuleNotFoundError。
COMPONENT_SIBLING_MODULES = (
    "infrastructure.components.component_manifest",
    "infrastructure.components.component_storage",
    "infrastructure.components.component_transactions",
    "infrastructure.components.component_artifacts",
    "infrastructure.components.component_cloudflared",
)
# 以下模块仅给独立高级组件 helper 使用，主程序冻结态不直接加载；
# 若不排除，PyInstaller 会顺着源码态分支把百余 MB 的识别库打包进主程序。
MAIN_EXCLUDED_MODULES = ("ddddocr", "onnxruntime", "cv2", "numpy", "segno")
# onedir 装配后复核 _internal 下不得残留上述重依赖目录。
_FORBIDDEN_ONEDIR_DIRS = ("cv2", "onnxruntime", "numpy", "numpy.libs", "ddddocr")
# Windows 默认 260 字符路径上限：按 20 字符用户名 + 每用户安装 + 旧版客户端暂存工作目录
# （C:\Users\<20 字符>\AppData\Local\Programs\CampusActivityWatch\versions\.staging-<请求号>.part-<32 位十六进制>\）
# 固定占用 153 字符，留给版本目录内相对路径的安全空间收口在 100 字符以内。
MAX_VERSION_DIR_RELATIVE_PATH = 100
# 改启动器打包参数时加一
LAUNCHER_BUILD_REVISION = 1
LAUNCHER_FINGERPRINT_FILE = "update-launcher.fingerprint"
_WORKER_SKILLS_REL = Path("playwright") / "driver" / "package" / "lib" / "tools" / "skills"


def read_version() -> str:
    """构建前读 VERSION 并校验格式：版本不合法就不构建，不产出版本对不上号的包。"""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit("[exe] 读不到 VERSION（%s）：%s" % (VERSION_FILE, exc))
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise SystemExit("[exe] VERSION 格式非法：%r（只允许 major.minor.patch）" % text)
    return text


def fail_if_missing() -> None:
    if importlib.util.find_spec("PyInstaller") is None:
        raise SystemExit(
            "未找到 PyInstaller；先在当前 Python 环境执行："
            "python -m pip install pyinstaller"
        )


def run_pyinstaller(name: str, source: Path, mode: str, add_ui: bool,
                    extra_data: "list[tuple[Path, str]] | None" = None) -> Path:
    stage = WORK / name
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    # EXE 图标：PyInstaller --icon 只对 windowed 程序有效，
    # 文件不存在就直接报错退出——绝不静默退回系统默认图标，
    # 免得发出去的包看起来像漏了品牌资源
    icon_path = LOCAL / "ui" / "brand" / "app.ico"
    if name != "grab-worker":
        if not icon_path.is_file():
            raise SystemExit(
                "[exe] 品牌图标不存在：%s\n"
                "      先把 design/brand/ico/app.ico 复制到 local/ui/brand/，"
                "或确认是否漏了 UI-C 计划" % icon_path)
    args = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", name, "--distpath", str(stage / "dist"),
        "--workpath", str(stage / "build"), "--specpath", str(stage),
        "--onefile" if mode == "onefile" else "--onedir",
        "--console" if name == "grab-worker" else "--windowed",
    ]
    if name != "grab-worker":
        args += ["--icon", str(icon_path)]
    elif mode == "onedir":
        # onedir 报名进程与主程序共享 _internal/w/，避免自身再套一层 _internal 拉长相对路径
        args += ["--contents-directory", "."]
    if name == "campus-activity-watch":
        args += ["--hidden-import", "signup_plan", "--collect-all", "webview"]
        for module in COMPONENT_SIBLING_MODULES:
            args += ["--hidden-import", module]
        for module in MAIN_EXCLUDED_MODULES:
            args += ["--exclude-module", module]
        if add_ui:
            args += ["--add-data", str(LOCAL / "ui") + os.pathsep + "ui"]
        # 版本单一来源：同一份根 VERSION 放进冻结资源根，app.py 用 RESOURCE_ROOT 读
        for src, dest in (extra_data or []):
            args += ["--add-data", str(src) + os.pathsep + dest]
    args.append(str(source))
    print("[exe] $ " + " ".join(str(part) for part in args), flush=True)
    result = subprocess.run(args, cwd=str(LOCAL), text=True)
    if result.returncode != 0:
        raise SystemExit("PyInstaller 构建失败，退出码 %d" % result.returncode)
    if mode == "onefile":
        return stage / "dist" / (name + ".exe")
    return stage / "dist" / name / (name + ".exe")


def prune_output(out: Path, *, preserve_data: bool = True) -> None:
    """清掉旧构建产物；onefile 可保留 out/data，onedir 不保留运行时目录。

    data 里可能有上一版 EXE 留下的 session.json / storage_state.json，
    重建后由 runtime_paths 首次启动迁移到统一数据根——onefile 先删数据等于
    替用户注销登录。构建失败/文件锁定时同样不会碰保留中的 data（删除按条目
    进行，出错直接抛，不吞）。
    """
    if not out.exists():
        return
    for child in out.iterdir():
        if child.name == "data":
            if preserve_data:
                continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _verify_onedir_exclusions(out: Path) -> None:
    """确认主程序 onedir 产物的 _internal 下未混入被排除的重依赖目录。"""
    internal = out / "_internal"
    if not internal.is_dir():
        return
    for name in _FORBIDDEN_ONEDIR_DIRS:
        if (internal / name).exists():
            raise SystemExit("[exe] onedir 产物 _internal 下存在不应打包的目录：%s" % name)


def _install_onedir_worker(worker_exe: Path, out: Path) -> Path:
    """将目录形态报名进程拷贝到版本目录的 _internal/w/ 下。"""
    target = out / "_internal" / "w"
    shutil.copytree(worker_exe.parent, target, dirs_exist_ok=True)
    return target


def _prune_worker_docs(worker_dir: Path) -> None:
    """删掉驱动里仅作说明、运行时不读取且占 98 字符长路径的 skills 文档目录。"""
    skills_dir = worker_dir / _WORKER_SKILLS_REL
    if skills_dir.exists():
        shutil.rmtree(skills_dir)


def _verify_version_dir_paths(out: Path) -> None:
    """确保版本目录内任一文件相对路径不超过 100 字符，给旧版暂存工作目录留足余量。"""
    longest_rel = ""
    for item in out.rglob("*"):
        if item.is_file():
            rel = item.relative_to(out).as_posix()
            if len(rel) > len(longest_rel):
                longest_rel = rel
    if len(longest_rel) > MAX_VERSION_DIR_RELATIVE_PATH:
        raise SystemExit(
            "[exe] 版本目录相对路径超过 %d 字符上限（%d 字符）：%s"
            % (MAX_VERSION_DIR_RELATIVE_PATH, len(longest_rel), longest_rel))


def _pyinstaller_version() -> str:
    try:
        return importlib.metadata.version("pyinstaller")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _compute_launcher_fingerprint(
    launcher_src: "Path | None" = None,
    icon_path: "Path | None" = None,
    *,
    py_version: "str | None" = None,
    pyinstaller_version: "str | None" = None,
    revision: "int | None" = None,
) -> str:
    """按固定顺序拼接启动器源码、图标、Python 与 PyInstaller 版本及修订号算 SHA-256。"""
    src_bytes = Path(launcher_src or (LOCAL / "update_launcher.py")).read_bytes()
    ico_bytes = Path(icon_path or (LOCAL / "ui" / "brand" / "app.ico")).read_bytes()
    py_ver = sys.version if py_version is None else py_version
    pi_ver = _pyinstaller_version() if pyinstaller_version is None else pyinstaller_version
    rev = LAUNCHER_BUILD_REVISION if revision is None else revision
    digest = hashlib.sha256()
    for part in (src_bytes, ico_bytes, py_ver.encode("utf-8"),
                 pi_ver.encode("utf-8"), str(rev).encode("utf-8")):
        digest.update(part)
        digest.update(b"\x00")
    return digest.hexdigest()


def _write_launcher_fingerprint(out: Path) -> Path:
    path = out / LAUNCHER_FINGERPRINT_FILE
    path.write_text(_compute_launcher_fingerprint() + "\n", encoding="utf-8")
    return path


def _copy_release_docs(out: Path) -> None:
    shutil.copy2(LOCAL / "README.md", out / "README.md")
    shutil.copy2(PROJECT / "CHANGELOG.md", out / "CHANGELOG.md")
    if (LOCAL / "gui-preview.png").is_file():
        shutil.copy2(LOCAL / "gui-preview.png", out / "gui-preview.png")
    if (PROJECT / "LICENSE").is_file():
        shutil.copy2(PROJECT / "LICENSE", out / "LICENSE")


def assemble(mode: str) -> Path:
    # onefile 沿用既有目录；onedir 按版本隔离，避免覆盖其他候选产物。
    out = OUT if mode == "onefile" else OUT_ONEDIR / read_version()
    prune_output(out, preserve_data=(mode == "onefile"))
    out.mkdir(parents=True, exist_ok=True)
    # 先构建 worker（onefile 模式打成单文件并随 VERSION 进资源根，onedir 模式打成目录放 _internal/w/）；
    # 不用 --add-binary（会重分析依赖），onefile 与 onedir 都只从资源根解析 worker。
    worker = run_pyinstaller("grab-worker", LOCAL / "grab.py", mode, False)
    if mode == "onefile":
        # --add-data 对文件源按「dest/源文件名」归档：dest 必须是 "."，
        # 让 worker 以 basename（恰为 grab-worker.exe）落在资源根；
        # 写成 dest="grab-worker.exe" 会解包成同名目录，冻结态解析直接 worker_missing
        app = run_pyinstaller("campus-activity-watch", LOCAL / "app.py", mode, True,
                              extra_data=[(worker, "."), (VERSION_FILE, ".")])
    else:
        app = run_pyinstaller("campus-activity-watch", LOCAL / "app.py", mode, True,
                              extra_data=[(VERSION_FILE, ".")])
    # onedir 版本目录需要一个独立入口：主程序退出后它才有权限切换 staging，
    # 再按 current.json 启动固定版本 EXE。onefile 仍沿用旧的完整安装器路径，
    # 不额外生成旁路启动器，避免改变既有单文件资产形态。
    launcher = (run_pyinstaller("update-launcher", LOCAL / "update_launcher.py", "onefile", False)
                if mode == "onedir" else None)
    if mode == "onefile":
        shutil.copy2(app, out / app.name)
    else:
        shutil.copytree(app.parent, out, dirs_exist_ok=True)
        _prune_worker_docs(_install_onedir_worker(worker, out))
        shutil.copy2(launcher, out / "update-launcher.exe")
        _verify_onedir_exclusions(out)
        _write_launcher_fingerprint(out)
    # worker 已落进资源根（onefile 内置，onedir 放 _internal/w/）：OUT 不再放置外置 grab-worker.exe，
    # 构建失败会在这里之前直接退出，绝不退回「外置 worker 入口」假称独立
    # 发行说明 / 预览 / 协议：与 Release ZIP 的清单保持同一套来源
    _copy_release_docs(out)
    # data 只是占位目录：已有（旧版数据）原样保留，全新构建维持旧布局
    if mode == "onefile":
        (out / "data").mkdir(exist_ok=True)
    else:
        _verify_version_dir_paths(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="构建校园活动预报名工具 EXE")
    parser.add_argument("--mode", choices=("onedir", "onefile"), default="onedir",
                        help="默认 onedir；onefile 仅在需要单文件入口时使用")
    args = parser.parse_args()
    version = read_version()
    print("[exe] 版本（VERSION 唯一来源）：%s" % version, flush=True)
    fail_if_missing()
    output = assemble(args.mode)
    print("[exe] 构建完成：%s" % output, flush=True)
    print("[exe] 主 EXE 已内置 grab-worker：单文件可独立运行（无需外置 worker）。",
          flush=True)
    print("[exe] 首次运行前确认 Windows WebView2、Chrome/Edge 可用。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
