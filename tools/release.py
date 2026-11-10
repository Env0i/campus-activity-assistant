#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打一条 Release：本地资产准备与外部发布分离，publish 必须显式打开。

三个阶段（默认只做 check，零副作用；三阶段互斥）：

    python tools/release.py --check               # 只读检查：版本、资产命名、预期清单、发布门禁预演
    python tools/release.py --prepare             # 本地准备：构建 onefile EXE + 组装 EXE/ZIP 资产（不打 tag、不上传）
    python tools/release.py --publish [--yes]     # 外部发布：核验资产 → 干净 main 门禁 → 人工确认 → tag → 上传

副作用边界（各阶段）：
- check 只读零副作用；
- prepare 只写 dist/ 本地文件，可在 feature 分支跑（产物仅供预览，manifest 会如实记录
  来源 commit、分支与 source_dirty；脏构建不得作为正式候选发布）；
- publish 在任何 tag/上传**之前**逐项核验候选资产（版本/tag/完整 HEAD 来源/显式 source_dirty=false/
  EXE/ZIP/worker 齐全/大小与 SHA-256 一致/ZIP 白名单成员无多余），任何一项不符
  直接拒绝并提示显式 --prepare，绝不静默复用旧候选或现场补构建；人工确认**之后**再复核
  「同一干净 main/完整 HEAD/VERSION/资产指纹」——确认等待期间任何变化都中止；
  tag 显式绑定已核验提交、远端 tag（ls-remote 独立核验，peeled 优先）必须指向同一提交，
  缺失才创建/推送，绝不 force 改写；`gh release create --verify-tag` 禁止 gh 自动补 tag；
  已有 Release 默认不覆盖附件（要覆盖必须显式 --clobber）。

兼容输入：位置参数 tag 只作校验（必须与 VERSION 推导一致，否则拒绝），
**不再单独触发发布**——要发布必须显式 --publish。

本机正式资产 = 独立 EXE + 完整 ZIP + **安装版安装器** + 可选手机组件（+manifest 清单），前三者由
同一次 --prepare 里构建的**同一份冻结 EXE** 派生（安装器经 local/build/build_installer.py
从该 EXE 生成，独立 EXE 与 ZIP 内 EXE 字节一致；安装器自身不与 EXE 比字节——
它是自解压容器，可比性在安装后哈希核验，见 specs/versioning-and-release）。
绿色版/服务器版打包（build_portable / zip_portable / zip_server）保留为**另行授权的
兼容发行流程**，publish 不会隐式触发，也不会隐式同步 local/server 远端分发分支。

产物（版本号唯一来源是仓库根 VERSION，本工具不再自定版本）：

    dist/release-<tag>/campus-activity-watch-<tag>-win-x64.zip      完整 ZIP（EXE + 说明 + 协议）
    dist/release-<tag>/campus-activity-watch-<tag>-win-x64.exe      独立可用单文件（内置 grab-worker）
    dist/release-<tag>/campus-activity-watch-installer-<tag>-win-x64.exe  安装版（Inno Setup，中文向导）
    dist/release-<tag>/manifest.json                               版本/完整 HEAD/来源是否干净/每文件 SHA-256

@article 安装器产物本地名是中文（校园活动预报名工具-安装版-<版>.exe），上传 GitHub 时
统一改用 ASCII 资产名（GitHub 会规范化中文前缀，v1.1.0 已人工补救过一次）。
@author Author
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
# gh 的可执行文件不写死本机路径：优先 GH_EXE，其次 PATH 里的 gh，最后交给子进程自己找。
GH = Path(os.environ.get("GH_EXE") or shutil.which("gh") or "gh")
# 代理不写死：跑发布的人自己的环境里已经有 HTTPS_PROXY/系统代理就用，没有就直连。
# 写死某个端口只会让别人的机器上 publish 直接失败。

PRODUCT_NAME = "校园活动预报名工具"
VERSION_FILE = ROOT / "VERSION"

# 构建时注入的站点地址模块：只在构建机 prepare 期间存在（.gitignore 排除），
# 随 PyInstaller 进资源根；源码态找不到它就当没有（见 local/site_target.py）。
SITE_BUILD_MODULE = ROOT / "local" / "_site_build.py"
_SITE_ORIGIN_RE = re.compile(r"^https://[^/\s]+(/[^\s]*)?$")


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


def write_site_build(origin: str) -> None:
    """生成 local/_site_build.py（只含 BUILD_BASE 一个字符串常量）。"""
    SITE_BUILD_MODULE.write_text(
        "# 构建时由 tools/release.py 生成，含站点地址，绝不入库（见 .gitignore）。\n"
        "BUILD_BASE = %r\n" % origin,
        encoding="utf-8")


def _load_build_installer():
    """按文件路径加载 local/build/build_installer.py，不污染 sys.path。

    安装器构建入口必须 import 而非 subprocess：release.py 要把**同一份冻结 EXE**
    显式传给它（同源约束），命令行拼接做不到这个保证。模块导入无副作用。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "release_build_installer", ROOT / "local" / "build" / "build_installer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD_INSTALLER = _load_build_installer()

# 手机控制组件是第四个资产：缺它发布出去，「安装手机控制」这条路就不可用。
COMPONENT_FEATURE = "phone_control"
# 验证码识别组件是第五个资产：缺它，设置里验证码识别的「下载并安装」就不可用。
OCR_FEATURE = "relogin_ocr"
_COMPONENT_MODULES: dict = {}


def _load_local_module(name: str, *parts: str):
    """按文件路径加载 local/ 下的模块（不污染 sys.path）；文件不存在返回 None。"""
    import importlib.util
    path = ROOT.joinpath("local", *parts)
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def component_modules() -> dict:
    """组件包用到的两个模块：命名规则与装机校验各自只有一份实现。"""
    if not _COMPONENT_MODULES:
        _COMPONENT_MODULES["update_check"] = _load_local_module(
            "release_update_check", "update_check.py")
        _COMPONENT_MODULES["component_packages"] = _load_local_module(
            "release_component_packages", "infrastructure", "component_packages.py")
    return _COMPONENT_MODULES


def component_asset_name(version: str) -> str:
    """组件包的 ASCII 资产名：与下载侧（local/update_check.py）同一来源。"""
    module = component_modules()["update_check"]
    if module is None:
        raise SystemExit("[release] 找不到 local/update_check.py：组件包命名没有单一来源")
    return module.phone_control_asset_name(version)


def ocr_component_asset_name(version: str) -> str:
    """验证码识别组件包的资产名：同样只认 local/update_check.py 的命名规则。"""
    module = component_modules()["update_check"]
    if module is None:
        raise SystemExit("[release] 找不到 local/update_check.py：组件包命名没有单一来源")
    return module.component_asset_name(OCR_FEATURE, version)

# 服务器版打包时排除的东西：密钥、运行时数据、产物
SERVER_EXCLUDE = {"config.json", "data", "dist", "reports",
                  "__pycache__", "node_modules"}

# 服务器 ZIP 只允许这些顶层成员：任何 data/、config.json、缓存、日志都进不来。
# 与 SERVER_EXCLUDE（复制时忽略）是两道独立防线：先排除，再按成员白名单复核。
SERVER_ALLOWED_TOP = {"bot", "deploy", "docs", "scripts", "tests",
                      "README.md", "CHANGELOG.md", "LICENSE",
                      "requirements.txt", "config.example.json"}

# 完整便携 ZIP 的白名单：只放这四样，任何 data/config/log/缓存/外置 worker 都进不来
# （worker 已作为数据资源内置进主 EXE，单文件独立可用——五成员旧口径已被 2026-10-25 决定取代）
ZIP_MEMBERS = ("EXE", "README.md", "启动说明.txt", "LICENSE")

LAUNCH_NOTE = """{name} v{version}（Windows x64）

第一次使用：
1. 把整个 zip 解压到任意目录（路径别带中文和空格），双击「{exe_name}」。
2. 首次打开点右上角「登录」，在弹出的浏览器里完成一次登录；之后重开会自动复用，只有失效才需要重登。

必读：
- 想像正常软件那样用（开始菜单、控制面板卸载）：下载同版本安装版
  campus-activity-watch-installer-<版本>-win-x64.exe；本 zip 是免安装备用形态。
- 主 EXE 独立可用：程序组件（grab-worker）已内置，单独拷走 EXE 也能直接用。
- 需要 Windows 10/11 与 WebView2 运行时（一般自带），浏览器用电脑上的 Chrome 或 Edge。
- 登录态等数据存在本机 %LOCALAPPDATA%\\TianSoftActivityPreRegistration\\data，
  替换新版 EXE 不需要重新登录。

只给本人账号使用；请遵守学校关于活动的管理规定。
"""


def read_version() -> str:
    """版本唯一来源：仓库根 VERSION；格式非法直接失败，不产出版本对不上号的资产名。"""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SystemExit("[release] 读不到 VERSION（%s）：%s" % (VERSION_FILE, exc))
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise SystemExit("[release] VERSION 格式非法：%r（只允许 major.minor.patch）" % text)
    return text


def tag_of(version: str) -> str:
    return "v" + version


def exe_asset_name(version: str) -> str:
    """下载资产的唯一英文基名。

    GitHub 会把中文前缀规范化成别的形式（已发布 v1.1.0 就靠人工补救过一次），
    所以下载名只用 ASCII，中文产品名只出现在 Release 标题/说明里。
    manifest、prepare、verify、publish 共用这一个函数，不产生手工映射。
    """
    return "campus-activity-watch-v%s-win-x64.exe" % version


def zip_asset_name(version: str) -> str:
    return "campus-activity-watch-v%s-win-x64.zip" % version


def installer_asset_name(version: str) -> str:
    """安装版的 ASCII 资产名：本地 Inno 产物是中文名，上传前统一改名。"""
    return "campus-activity-watch-installer-v%s-win-x64.exe" % version


def payload_asset_name(version: str) -> str:
    """版本目录完整 payload 的 ASCII 资产名。"""
    return "campus-activity-watch-payload-v%s-win-x64.zip" % version


def delta_asset_name(base_version: str, target_version: str) -> str:
    """文件级增量包的 ASCII 资产名（明确记录基础版本与目标版本）。"""
    return "campus-activity-watch-delta-v%s-to-v%s-win-x64.zip" % (
        base_version, target_version)


SPLIT_ARTIFACTS = (
    "phone_control_runtime", "phone_control_cloudflared",
    "relogin_ocr_runtime", "relogin_ocr_model",
)


def artifact_asset_name(artifact_id: str, version: str) -> str:
    if artifact_id not in SPLIT_ARTIFACTS:
        raise ValueError("unknown artifact")
    return "campus-activity-watch-%s-v%s-win-x64.zip" % (
        artifact_id.replace("_", "-"), version)


def run(cmd: list[str], cwd: Path = ROOT, env: dict | None = None) -> str:
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, env=env,
                         encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise SystemExit("命令失败：%s\n%s\n%s"
                         % (" ".join(cmd), res.stdout[-1500:], res.stderr[-1500:]))
    return res.stdout


def git_state() -> dict:
    """只读采集当前分支 / 脏文件 / HEAD（短与完整），不做任何门禁判断。"""
    return {
        "branch": run(["git", "branch", "--show-current"]).strip(),
        "dirty": run(["git", "status", "--porcelain"]).strip(),
        "commit": run(["git", "rev-parse", "--short", "HEAD"]).strip(),
        "full": run(["git", "rev-parse", "HEAD"]).strip(),
    }


def source_commit() -> str:
    """外部发布门禁：Release 只能从干净 main 读取，避免把设计分支或半成品发布出去。

    返回**完整** HEAD：manifest 来源核验与 tag 指向核验都用它（短哈希可撞前缀）。
    """
    state = git_state()
    if state["branch"] != "main":
        raise SystemExit("外部发布必须从 main 运行，当前分支是 %s（准备阶段可在 feature 分支，"
                         "发布阶段不行——也不允许临时切 main 发布半成品）"
                         % (state["branch"] or "（分离 HEAD）"))
    if state["dirty"]:
        raise SystemExit("外部发布要求工作区干净，请先提交或清理改动：\n%s" % state["dirty"])
    return state["full"]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(stage_dir: Path, version: str, tag: str, files: list[Path],
                   build_state: dict | None = None,
                   component_included: bool | None = None,
                   site_configured: bool | None = None,
                   ocr_component_included: bool | None = None,
                   full_payload: Path | None = None,
                   deltas: list[dict] | None = None,
                   base_version: str | None = None,
                   target_manifest_sha256: str | None = None,
                   target_manifest: dict | None = None,
                   split_assets: dict | None = None) -> Path:
    """资产证据：版本、tag、来源分支、**完整 HEAD**、来源是否干净、每个文件的 SHA-256 与大小。

    source_dirty=true 的产物只能当预览：main 干净不等于资产来自干净提交，
    发布侧会拒绝脏候选，绝不把它说成来源于干净提交。
    component_included 显式记录这次候选有没有手机控制组件包：字段缺失的旧候选
    一律按「没有」处理，publish 会因此拒绝，而不是猜。
    site_configured 只记有没有把站点地址注入发布物，**不写地址本身**。
    """
    state = build_state or git_state()
    manifest = {
        "version": version,
        "tag": tag,
        "branch": state["branch"],
        "commit": state["full"],
        "commit_short": state["commit"],
        "source_dirty": bool(state["dirty"]),
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "files": {p.name: {"sha256": sha256_of(p), "bytes": p.stat().st_size}
                  for p in files},
    }
    if component_included is not None:
        manifest["component_included"] = bool(component_included)
    if ocr_component_included is not None:
        # 同样显式记账：字段缺失的旧候选按「没有验证码识别组件」处理，publish 拒绝
        manifest["ocr_component_included"] = bool(ocr_component_included)
    if site_configured is not None:
        manifest["site_configured"] = bool(site_configured)
    if full_payload is not None:
        full_payload = Path(full_payload)
        manifest["full_payload"] = {
            "name": full_payload.name,
            "bytes": full_payload.stat().st_size,
            "sha256": sha256_of(full_payload),
            "target_version": version,
            **({"target_manifest_sha256": target_manifest_sha256}
               if target_manifest_sha256 else {}),
            **({"target_manifest": target_manifest}
               if target_manifest is not None else {}),
        }
    if deltas is not None:
        manifest["deltas"] = [dict(item) for item in deltas]
    if base_version is not None:
        manifest["base_version"] = base_version
    if target_manifest_sha256 is not None:
        manifest["target_manifest_sha256"] = target_manifest_sha256
    if split_assets is not None:
        manifest["split_assets"] = {key: dict(value)
                                     for key, value in split_assets.items()}
    path = stage_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return path


def build_exe_onefile() -> Path:
    """调用 local/build/build_exe.py 构建 onefile 主 EXE（worker 已内置为数据资源，产物在 dist/campus-grab-exe）。"""
    print("[prepare] 构建 onefile EXE（内置 grab-worker）...")
    run([sys.executable, str(ROOT / "local" / "build" / "build_exe.py"), "--mode", "onefile"])
    out = DIST / "campus-grab-exe"
    main = out / "campus-activity-watch.exe"
    if not main.is_file():
        raise SystemExit("构建产物缺失：%s" % main)
    return out


def build_exe_onedir(version: str) -> Path:
    """构建版本隔离的 onedir 主程序，供完整 payload 与增量更新共用。"""
    print("[prepare] 构建 onedir payload（内置 grab-worker）...")
    run([sys.executable, str(ROOT / "local" / "build" / "build_exe.py"),
         "--mode", "onedir"])
    out = DIST / "campus-grab-exe-onedir" / version
    main = out / "campus-activity-watch.exe"
    if not main.is_file():
        raise SystemExit("构建产物缺失：%s" % main)
    return out


def _target_manifest(directory: Path, version: str) -> dict:
    """按更新器同一实现生成 onedir 目录清单，避免两边哈希口径漂移。"""
    module = _load_local_module("release_update_delta", "update_delta.py")
    if module is None:
        raise SystemExit("[prepare] 找不到 local/update_delta.py：payload 清单无法生成")
    try:
        return module.manifest_from_directory(directory, version=version)
    except Exception as exc:
        raise SystemExit("[prepare] onedir payload 清单生成失败：%s" % exc)


def stage_full_payload(version: str, stage_dir: Path, onedir_dir: Path) -> tuple[Path, str, dict]:
    """把 onedir 版本目录打成完整 payload，并返回资产路径、哈希与目标清单。"""
    target = stage_dir / payload_asset_name(version)
    manifest = _target_manifest(onedir_dir, version)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in manifest["files"]:
            relative = entry["path"]
            archive.write(onedir_dir / Path(*relative.split("/")), relative)
    return target, manifest["target_manifest_sha256"], manifest


def stage_delta_payload(base_version: str, target_version: str,
                        stage_dir: Path, base_dir: Path,
                        target_dir: Path) -> tuple[Path, dict]:
    """从显式历史 onedir 基线生成 delta 资产和发布清单条目。"""
    module = _load_local_module("release_update_delta", "update_delta.py")
    if module is None:
        raise SystemExit("[prepare] 找不到 local/update_delta.py：delta 无法生成")
    base_dir = Path(base_dir)
    target_dir = Path(target_dir)
    if not base_dir.is_dir() or not target_dir.is_dir():
        raise SystemExit("[prepare] delta 基线或目标目录不存在")
    target = stage_dir / delta_asset_name(base_version, target_version)
    try:
        delta = module.build_delta(base_dir, target_dir, base_version, target_version)
        module.write_delta_zip(delta, target, target_dir=target_dir)
    except Exception as exc:
        raise SystemExit("[prepare] delta 生成失败：%s" % exc)
    target_manifest = delta["target_manifest"]
    metadata = {
        "name": target.name,
        "bytes": target.stat().st_size,
        "sha256": sha256_of(target),
        "base_version": base_version,
        "target_version": target_version,
        "target_manifest_sha256": delta["target_manifest_sha256"],
        "target_manifest": target_manifest,
    }
    return target, metadata


def _default_cloudflared() -> Path:
    return ROOT / "local" / "bin" / "cloudflared.exe"


def build_phone_component(version: str, work_dir: Path,
                          cloudflared: Path | None = None) -> Path:
    """调 local/build/build_advanced.py 打组件包（PyInstaller，耗时几分钟）。

    只调脚本、不 import：打包必须在独立进程里跑，且「cloudflared 版本必须等于
    写死值」这条规则只允许有 build_advanced 一个实现，发布侧再核一遍清单即可。
    """
    binary = Path(cloudflared) if cloudflared else _default_cloudflared()
    if not binary.is_file():
        raise SystemExit("[prepare] 缺 cloudflared 二进制：%s\n"
                         "手机控制组件包必须内置固定版本；请把它放到 local/bin/，"
                         "或用 --cloudflared 指定" % binary)
    work_dir.mkdir(parents=True, exist_ok=True)
    print("[prepare] 构建手机控制组件包（内置 cloudflared）...")
    run([sys.executable, str(ROOT / "local" / "build" / "build_advanced.py"),
         "--feature", COMPONENT_FEATURE,
         "--output-dir", str(work_dir),
         "--cloudflared", str(binary)])
    produced = sorted(work_dir.glob("%s-*-windows-x64.zip" % COMPONENT_FEATURE))
    if len(produced) != 1:
        raise SystemExit("[prepare] 组件构建产物不唯一：%s" % (produced or "（没有产物）"))
    return produced[0]


def build_ocr_component(version: str, work_dir: Path) -> Path:
    """调 local/build/build_advanced.py 打验证码识别组件包（PyInstaller，需要 ddddocr 与 onnxruntime）。"""
    work_dir.mkdir(parents=True, exist_ok=True)
    print("[prepare] 构建验证码识别组件包 ...")
    run([sys.executable, str(ROOT / "local" / "build" / "build_advanced.py"),
         "--feature", OCR_FEATURE,
         "--output-dir", str(work_dir)])
    produced = sorted(work_dir.glob("%s-*-windows-x64.zip" % OCR_FEATURE))
    if len(produced) != 1:
        raise SystemExit("[prepare] 验证码识别组件构建产物不唯一：%s" % (produced or "（没有产物）"))
    return produced[0]


def build_split_artifact(artifact_id: str, version: str, work_dir: Path,
                         cloudflared: Path | str | None = None) -> Path:
    """构建单个 schema2 资产，旧 feature 构建入口不受影响。"""
    work_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(ROOT / "local" / "build" / "build_advanced.py"),
               "--artifact", artifact_id, "--output-dir", str(work_dir)]
    if artifact_id == "phone_control_cloudflared":
        binary = Path(cloudflared) if cloudflared else _default_cloudflared()
        if not binary.is_file():
            raise SystemExit("[prepare] 缺 cloudflared 二进制：%s" % binary)
        command += ["--cloudflared", str(binary)]
    run(command)
    produced = sorted(work_dir.glob("%s-*-windows-x64.zip" % artifact_id))
    if len(produced) != 1:
        raise SystemExit("[prepare] 拆分资产构建产物不唯一：%s" % (produced or "（没有产物）"))
    return produced[0]


# 可替换的构建入口：测试用假构建器验证装配契约，不跑 PyInstaller、不打包几十兆二进制
BUILD_COMPONENT = build_phone_component
BUILD_OCR_COMPONENT = build_ocr_component


def inspect_component(archive: Path, feature: str) -> dict:
    """用装机同一套清单校验组件包；不合规直接失败（发布不带「装不上」的包）。"""
    packages = component_modules()["component_packages"]
    if packages is None:
        raise SystemExit("[release] 找不到 local/infrastructure/component_packages.py")
    try:
        result = packages.inspect_archive(archive, feature)
    except Exception as exc:                       # 只读自检不该抛，抛了就当不合规
        raise SystemExit("[prepare] 组件包自检失败（%s）：%s" % (exc, archive))
    if not (isinstance(result, dict) and result.get("ok") is True):
        text = (result or {}).get("text") if isinstance(result, dict) else ""
        raise SystemExit("[prepare] 组件包不合规：%s（%s）" % (text or "未知原因", archive))
    return result


def inspect_phone_component(archive: Path) -> dict:
    """手机控制组件包自检（旧函数名）。"""
    return inspect_component(archive, COMPONENT_FEATURE)


def stage_phone_component(version: str, stage_dir: Path,
                          cloudflared: Path | None = None) -> Path:
    """构建组件包 → 改成发布资产名 → 按装机规则核验，返回资产路径。"""
    target = stage_dir / component_asset_name(version)
    # 组件脚本只接受系统临时目录下的独立工作区；发布目录只收最终资产。
    with tempfile.TemporaryDirectory(prefix="campus-phone-component-") as directory:
        work_dir = Path(directory)
        produced = BUILD_COMPONENT(version, work_dir, cloudflared)
        shutil.copy2(produced, target)
    inspect_phone_component(target)
    return target


def stage_ocr_component(version: str, stage_dir: Path) -> Path:
    """构建验证码识别组件包 → 改成发布资产名 → 按装机规则核验，返回资产路径。"""
    target = stage_dir / ocr_component_asset_name(version)
    with tempfile.TemporaryDirectory(prefix="campus-ocr-component-") as directory:
        produced = BUILD_OCR_COMPONENT(version, Path(directory))
        shutil.copy2(produced, target)
    inspect_component(target, OCR_FEATURE)
    return target


def stage_split_artifacts(version: str, stage_dir: Path,
                          cloudflared: Path | str | None = None) -> tuple[list[Path], dict]:
    """构建四种 schema2 资产并返回发布资产与 manifest 元数据。"""
    packages = component_modules()["component_packages"]
    assets = []
    metadata = {}
    for artifact_id in SPLIT_ARTIFACTS:
        with tempfile.TemporaryDirectory(prefix="campus-%s-" % artifact_id) as directory:
            produced = build_split_artifact(artifact_id, version, Path(directory), cloudflared)
            target = stage_dir / artifact_asset_name(artifact_id, version)
            shutil.copy2(produced, target)
        inspected = packages.inspect_artifact(target, artifact_id)
        if not inspected.get("ok"):
            raise SystemExit("[prepare] 拆分资产不合规：%s" % target.name)
        assets.append(target)
        metadata[artifact_id] = {
            "artifact_id": artifact_id,
            "name": target.name,
            "bytes": target.stat().st_size,
            "sha256": sha256_of(target),
            "target_version": version,
            "compatibility_id": "campus-activity-1",
            "role": inspected.get("role", ""),
        }
    return assets, metadata


def stage_local_assets(version: str, *, with_component: bool = True,
                       cloudflared: Path | str | None = None,
                       delta_base: Path | str | None = None,
                       delta_base_version: str | None = None,
                       split_components: bool = False) -> dict:
    """准备阶段：构建 + 组装完整 ZIP、单文件 EXE 与 onedir payload，写 manifest。

    只产生本地文件：不打 tag、不上传、不访问网络；OUT/data 里的旧登录态
    永远进不了 ZIP（白名单按文件名收集，data 目录不在清单里）。
    构建前后来源（HEAD/脏状态）必须一致：构建中途改代码的产物不能当候选。
    """
    tag = tag_of(version)
    pre = git_state()
    # 来源脏 = 预览构建：允许不注入站点地址；干净来源的正式候选必须注入，
    # 缺 SCHOOL_ORIGIN 或不是 https 时在构建**之前**直接失败（不产出任何资产）。
    preview = bool(pre["dirty"])
    site_origin = site_origin_for_build(preview)
    if site_origin:
        write_site_build(site_origin)
        print("[prepare] 已注入构建环境 SCHOOL_ORIGIN（值只进发布物，不进仓库）")
    try:
        out = build_exe_onefile()
        onedir_out = build_exe_onedir(version)
    finally:
        # 生成文件绝不留在工作区：构建成功/失败都删，避免真实地址落进源码树
        if site_origin:
            SITE_BUILD_MODULE.unlink(missing_ok=True)
    post = git_state()
    if (pre["full"], pre["dirty"]) != (post["full"], post["dirty"]):
        raise SystemExit("[prepare] 构建期间源码发生变化（%s%s → %s%s），本次产物不能当候选；"
                         "稳定后请重跑 --prepare"
                         % (pre["commit"], "*" if pre["dirty"] else "",
                            post["commit"], "*" if post["dirty"] else ""))
    stage_dir = DIST / ("release-" + tag)
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True)

    # 白名单暂存目录：成员名固定，绝不整目录拷贝（防止 data/config/log 混入）
    staging = stage_dir / ".zip-root"
    staging.mkdir()
    shutil.copy2(out / "campus-activity-watch.exe", staging / exe_asset_name(version))
    shutil.copy2(ROOT / "local" / "README.md", staging / "README.md")
    # 启动说明：输入先统一成 LF 再按 CRLF 输出——源文件若被 CRLF 检出
    # （fresh clone + autocrlf），字面量自带 \r\n，直接 newline 翻译会产生 CR CR LF
    (staging / "启动说明.txt").write_text(
        LAUNCH_NOTE.format(name=PRODUCT_NAME, version=version,
                           exe_name=exe_asset_name(version)).replace("\r\n", "\n"),
        encoding="utf-8", newline="\r\n")
    if not (ROOT / "LICENSE").is_file():
        raise SystemExit("缺少 LICENSE，发行包必须带协议")
    shutil.copy2(ROOT / "LICENSE", staging / "LICENSE")

    zip_path = stage_dir / zip_asset_name(version)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for member in ZIP_MEMBERS:
            name = exe_asset_name(version) if member == "EXE" else member
            zf.write(staging / name, name)

    exe_path = stage_dir / exe_asset_name(version)
    shutil.copy2(out / "campus-activity-watch.exe", exe_path)

    payload_path, target_manifest_sha256, target_manifest = stage_full_payload(
        version, stage_dir, onedir_out)
    delta_path = None
    delta_info = None
    if delta_base is not None or delta_base_version is not None:
        if delta_base is None or not delta_base_version:
            raise SystemExit("[prepare] 生成 delta 需要同时提供 --delta-base 和 --delta-base-version")
        delta_path, delta_info = stage_delta_payload(
            delta_base_version, version, stage_dir, Path(delta_base), onedir_out)
        print("[prepare] delta 资产：%s  %.1f MB（基线 %s）"
              % (delta_path.name, delta_path.stat().st_size / 1024 / 1024,
                 delta_base_version))

    # 安装版：从暂存区里**同一份冻结 EXE**（copy2 自 out，与独立 EXE 字节一致）
    # 派生安装器。喂暂存副本而不是 dist 原件：暂存目录是白名单净地，check_source
    # 的运行期残留检查不会误伤 build 目录里留给登录迁移的旧 data/。
    installer_build_dir = stage_dir / ".installer-build"
    installer_path = stage_dir / installer_asset_name(version)
    try:
        built = BUILD_INSTALLER.build(
            staging / exe_asset_name(version), installer_build_dir, version=version,
            payload_dir=onedir_out,
            updater=onedir_out / "update-launcher.exe")
        # 本地 Inno 产物是中文名；上传资产统一 ASCII（GitHub 会规范化中文前缀）
        shutil.copy2(built, installer_path)
    finally:
        shutil.rmtree(installer_build_dir, ignore_errors=True)
    shutil.rmtree(staging, ignore_errors=True)

    # 手机控制组件包：和安装器同属「派生资产」，但它必须内置固定版本的 cloudflared，
    # 所以单独构建、单独核验。--without-component 只在明确接受「组件不可用」时用。
    component_path = None
    ocr_component_path = None
    if with_component:
        component_path = stage_phone_component(version, stage_dir, cloudflared)
        ocr_component_path = stage_ocr_component(version, stage_dir)
    else:
        print("[prepare] 跳过两个组件包（--without-component）："
              "这次发布里手机控制和验证码识别的「下载并安装」都会不可用")

    split_paths = []
    split_info = None
    if split_components:
        split_paths, split_info = stage_split_artifacts(version, stage_dir, cloudflared)

    assets = [zip_path, exe_path, installer_path, payload_path]
    if delta_path is not None:
        assets.append(delta_path)
    if component_path is not None:
        assets.append(component_path)
    if ocr_component_path is not None:
        assets.append(ocr_component_path)
    assets.extend(split_paths)
    manifest = write_manifest(stage_dir, version, tag, assets,
                              build_state=post,
                              component_included=component_path is not None,
                              site_configured=bool(site_origin),
                              ocr_component_included=ocr_component_path is not None,
                              full_payload=payload_path,
                              deltas=[delta_info] if delta_info is not None else None,
                              base_version=delta_base_version,
                              target_manifest_sha256=target_manifest_sha256,
                              target_manifest=target_manifest,
                              split_assets=split_info)
    for path in assets:
        print("   %s  %.1f MB" % (path.name, path.stat().st_size / 1024 / 1024))
    print("[prepare] 资产就绪：%s" % stage_dir)
    print("[prepare] 清单：%s（版本/完整 HEAD/来源%s/SHA-256）"
          % (manifest, "脏（仅供预览，不得发布）" if post["dirty"] else "干净"))
    return {"zip": zip_path, "exe": exe_path, "installer": installer_path,
            "payload": payload_path,
            "delta": delta_path,
            "split_assets": split_paths,
            "component": component_path, "ocr_component": ocr_component_path,
            "manifest": manifest}


def check_only(version: str) -> None:
    """默认阶段：只读检查，输出资产命名、ZIP 白名单与发布门禁预演结果。"""
    tag = tag_of(version)
    print("[check] 版本（VERSION 唯一来源）：%s → tag %s" % (version, tag))
    print("[check] 资产命名：%s / %s / %s / %s / %s"
          % (zip_asset_name(version), exe_asset_name(version),
             installer_asset_name(version), component_asset_name(version),
             ocr_component_asset_name(version)))
    print("[check] 完整 ZIP 白名单成员：%s"
          % "、".join(exe_asset_name(version) if m == "EXE" else m for m in ZIP_MEMBERS))
    cloudflared = _default_cloudflared()
    print("[check] 手机控制组件包：%s（%s）"
          % (component_asset_name(version),
             "cloudflared 就绪：%s" % cloudflared if cloudflared.is_file()
             else "缺 cloudflared：%s —— prepare 前先放好或用 --cloudflared 指定" % cloudflared))
    missing = [str(p) for p in (ROOT / "local" / "build" / "build_exe.py",
                                ROOT / "local" / "build" / "build_installer.py",
                                ROOT / "local" / "installer" / "ChineseSimplified.isl",
                                ROOT / "local" / "README.md",
                                ROOT / "local" / "launchers" / "遇到问题先看我.txt",
                                ROOT / "LICENSE", VERSION_FILE) if not p.is_file()]
    if missing:
        raise SystemExit("[check] 缺少输入文件：%s" % "、".join(missing))
    state = git_state()
    gate_ok = state["branch"] == "main" and not state["dirty"]
    print("[check] 当前 %s@%s，工作区%s；外部发布门禁（main+干净）现在%s"
          % (state["branch"] or "（分离 HEAD）", state["commit"],
             "干净" if not state["dirty"] else "有未提交改动",
             "会通过" if gate_ok else "不会通过（prepare 不受影响，publish 前先合并回 main）"))
    stage_dir = DIST / ("release-" + tag)
    manifest = stage_dir / "manifest.json"
    if manifest.is_file():
        try:
            info = json.loads(manifest.read_text(encoding="utf-8"))
            print("[check] 已有候选：%s（来源 %s@%s，%s）——%s"
                  % (stage_dir, info.get("branch"), (info.get("commit") or "")[:12],
                     "脏构建，仅供预览" if info.get("source_dirty") else "来源干净",
                     "正式发布前必须在干净 main 重新 --prepare 并通过核验"
                     if info.get("source_dirty") or info.get("commit") != state["full"]
                     else "publish 会逐项核验后使用"))
        except (OSError, json.JSONDecodeError):
            print("[check] 已有候选 manifest 读不了：%s（publish 会拒绝）" % manifest)
    else:
        print("[check] 尚无 %s 候选：publish 只认显式 --prepare 的产物，不会现场补构建" % tag)
    print("[check] 本阶段零副作用：不构建、不打 tag、不上传")


def build_portable() -> None:
    """兼容发行流程（另行授权）：绿色版目录构建。publish 不会隐式调用。"""
    print("构建绿色版 ...")
    run([sys.executable, str(ROOT / "local" / "build" / "make_portable.py")])


def zip_portable(tag: str) -> Path:
    """兼容发行流程（另行授权）：绿色版压缩包。publish 不会隐式调用。"""
    src = DIST / "campus-grab-portable"
    if not src.is_dir():
        raise SystemExit("没找到 %s，先运行 local/build/make_portable.py" % src)
    out = DIST / ("campus-grab-portable-%s.zip" % tag)
    out.unlink(missing_ok=True)
    shutil.make_archive(str(out.with_suffix("")), "zip",
                        root_dir=str(DIST), base_dir="campus-grab-portable")
    return out


def server_manifest_path(tag: str) -> Path:
    """服务器 ZIP 的 provenance 边车：与 zip 同目录，解压前就能核验。"""
    return DIST / ("campus-server-%s.manifest.json" % tag)


def _zip_member_map(zip_path: Path) -> dict:
    """读出 zip 成员（去掉顶层目录名）→ {sha256, bytes}，越界成员直接拒绝。"""
    members: dict[str, dict] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            rel = name.split("/", 1)[1] if "/" in name else name
            top = rel.split("/", 1)[0]
            if top not in SERVER_ALLOWED_TOP:
                raise SystemExit(
                    "[server] ZIP 成员越界：%s（只允许 %s）"
                    % (rel, "、".join(sorted(SERVER_ALLOWED_TOP))))
            if rel == "config.json" or rel.startswith("data/"):
                raise SystemExit("[server] ZIP 混入运行时数据：%s" % rel)
            members[rel] = {
                "sha256": hashlib.sha256(zf.read(info)).hexdigest(),
                "bytes": info.file_size,
            }
    return members


def zip_server(tag: str) -> Path:
    """兼容发行流程（另行授权）：服务器版源码包 + manifest/SHA 边车。

    publish 不会隐式调用；生成的 manifest 记录版本、完整 HEAD、来源是否干净、
    ZIP 自身 SHA-256 与每个成员的 SHA-256/大小，可离线重算核验（P2-5）。
    """
    out = DIST / ("campus-server-%s.zip" % tag)
    out.unlink(missing_ok=True)
    staging = DIST / ("campus-server-" + tag)   # 解压后的顶层目录名，别带点（Windows 会当隐藏目录）
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(
        ROOT / "server", staging,
        ignore=shutil.ignore_patterns(*SERVER_EXCLUDE))
    # 服务器版单独带一份运维文档，克隆下来就能查
    shutil.copytree(ROOT / "docs", staging / "docs")
    shutil.copy2(ROOT / "README.md", staging / "README.md")
    shutil.copy2(ROOT / "CHANGELOG.md", staging / "CHANGELOG.md")
    # 协议跟着分发走：没有 LICENSE 的 zip 别人拿到只有"保留所有权利"的默认解释
    if (ROOT / "LICENSE").exists():
        shutil.copy2(ROOT / "LICENSE", staging / "LICENSE")
    shutil.make_archive(str(out.with_suffix("")), "zip",
                        root_dir=str(DIST), base_dir=staging.name)
    shutil.rmtree(staging, ignore_errors=True)

    members = _zip_member_map(out)
    state = git_state()
    manifest = {
        "schema": 1,
        "kind": "server",
        "version": VERSION_FILE.read_text(encoding="utf-8").strip(),
        "tag": tag,
        "branch": state["branch"],
        "commit": state["full"],
        "commit_short": state["commit"],
        "source_dirty": bool(state["dirty"]),
        "created": datetime.now().astimezone().isoformat(timespec="seconds"),
        "zip": {"name": out.name, "sha256": sha256_of(out),
                "bytes": out.stat().st_size},
        "files": members,
    }
    path = server_manifest_path(tag)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("[server] %s（%d 个成员，manifest：%s）" % (out.name, len(members), path.name))
    return out


def verify_server_zip(tag: str) -> dict:
    """重算成员哈希与 ZIP 哈希；任何不一致都拒绝，不用最低版本冒充 provenance。"""
    zip_path = DIST / ("campus-server-%s.zip" % tag)
    manifest_path = server_manifest_path(tag)
    if not zip_path.is_file():
        raise SystemExit("[server] 找不到 %s" % zip_path)
    if not manifest_path.is_file():
        raise SystemExit("[server] 缺 manifest：%s（先运行 zip_server）" % manifest_path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit("[server] manifest 读不了：%s" % exc)
    if manifest.get("zip", {}).get("sha256") != sha256_of(zip_path):
        raise SystemExit("[server] ZIP 哈希与 manifest 不一致：候选被改动过")
    members = _zip_member_map(zip_path)
    if members != manifest.get("files"):
        raise SystemExit("[server] ZIP 成员与 manifest 不一致：成员被增删或替换")
    if manifest.get("version") != VERSION_FILE.read_text(encoding="utf-8").strip():
        raise SystemExit("[server] manifest 版本与 VERSION 不一致")
    return {"manifest": manifest, "members": len(members)}


def verify_release_assets(version: str) -> dict:
    """发布前资产核验（独立函数，do_publish 在任何 tag/上传之前调用）。

    逐项核对：manifest 存在且 version/tag 一致、来源=当前完整 HEAD 且非脏构建、
    EXE/ZIP 齐全、大小与 SHA-256 与 manifest 一致、ZIP 成员恰为白名单（无 data 混入）。
    任何一项不符都直接拒绝并提示显式 --prepare——绝不静默复用旧候选、不现场补构建；
    「当前在干净 main」本身不构成绕过理由：main 干净不等于资产来自 main。
    """
    tag = tag_of(version)
    stage_dir = DIST / ("release-" + tag)
    manifest_path = stage_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit("[publish] %s 缺 manifest：没有可核验的 prepare 产物。"
                         "请先在目标来源上显式运行 --prepare；publish 不会现场补构建"
                         % stage_dir)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("[publish] manifest 读不了（%s）：候选不完整，请重新 --prepare" % exc)
    if not isinstance(manifest, dict):
        raise SystemExit("[publish] manifest 根不是对象：候选清单损坏，请重新 --prepare")
    if manifest.get("version") != version or manifest.get("tag") != tag:
        raise SystemExit("[publish] manifest 版本/tag（%s/%s）与当前候选（%s/%s）不一致："
                         "旧候选不得发布，请重新 --prepare"
                         % (manifest.get("version"), manifest.get("tag"), version, tag))
    # source_dirty 只认显式布尔 false：字段缺失/null/0/"false" 一律来源未知，不得发布
    dirty_flag = manifest.get("source_dirty")
    if dirty_flag is not False:
        raise SystemExit("[publish] manifest.source_dirty 缺失或不是布尔 false（%r）："
                         "来源未知不得发布；请在干净 main 上重新 --prepare" % (dirty_flag,))
    state = git_state()
    if manifest.get("commit") != state["full"]:
        raise SystemExit("[publish] 候选来源 %s ≠ 当前 HEAD %s：这份资产不是当前提交构建的，"
                         "不得发布；请在当前来源重新 --prepare"
                         % (manifest.get("commit"), state["full"]))
    exe_path = stage_dir / exe_asset_name(version)
    zip_path = stage_dir / zip_asset_name(version)
    installer_path = stage_dir / installer_asset_name(version)
    for path in (exe_path, zip_path, installer_path):
        if not path.is_file():
            raise SystemExit("[publish] 资产缺失：%s（请重新 --prepare，不要拼接旧产物）" % path)
        meta = (manifest.get("files") or {}).get(path.name)
        if not isinstance(meta, dict):
            raise SystemExit("[publish] manifest 里没有 %s 的清单记录" % path.name)
        if path.stat().st_size != meta.get("bytes"):
            raise SystemExit("[publish] %s 大小与 manifest 不符（%d ≠ %s）：文件被动过，拒绝发布"
                             % (path.name, path.stat().st_size, meta.get("bytes")))
        if sha256_of(path) != meta.get("sha256"):
            raise SystemExit("[publish] %s SHA-256 与 manifest 不符：文件被动过，拒绝发布" % path.name)
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        expected = {exe_asset_name(version) if m == "EXE" else m for m in ZIP_MEMBERS}
        if names != expected:
            extra = "、".join(sorted(names - expected)) or "（缺：%s）" % "、".join(sorted(expected - names))
            raise SystemExit("[publish] ZIP 成员与白名单不符（%s）：不得携带任何 data/config/log" % extra)
        # ZIP 内主 EXE 与单独资产 EXE 必须字节一致：同一份独立 EXE 的两种分发形态，
        # 不一致说明候选装配损坏（或混入了旧构建的 worker/入口）
        inner = zf.read(exe_asset_name(version))
        if hashlib.sha256(inner).hexdigest() != sha256_of(exe_path):
            raise SystemExit("[publish] ZIP 内主 EXE 与单独 EXE 不一致：候选装配损坏，"
                             "请重新 --prepare（不得手工拼包）")
    # 手机控制组件包：缺它就是通道里的「安装手机控制」不可用，不能当作发布完成
    if manifest.get("component_included") is not True:
        raise SystemExit("[publish] 候选没有手机控制组件包（manifest.component_included "
                         "不是布尔 true）：缺它「安装手机控制」不可用，不得发布；"
                         "请重新 --prepare（如确要发不带组件的版本，得显式接受这条降级）")
    component_path = _verified_component(stage_dir, manifest,
                                         component_asset_name(version), COMPONENT_FEATURE)
    # 验证码识别组件包：同样缺包就拒绝，不静默发出一个「下载并安装」点了没东西的版本
    if manifest.get("ocr_component_included") is not True:
        raise SystemExit("[publish] 候选没有验证码识别组件包（manifest.ocr_component_included "
                         "不是布尔 true）：缺它设置里验证码识别的「下载并安装」不可用，不得发布；"
                         "请重新 --prepare")
    ocr_component_path = _verified_component(stage_dir, manifest,
                                             ocr_component_asset_name(version), OCR_FEATURE)
    delta_paths = []
    for item in manifest.get("deltas", []) or []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SystemExit("[publish] delta 条目不合法")
        path = stage_dir / item["name"]
        meta = (manifest.get("files") or {}).get(path.name)
        if not path.is_file() or not isinstance(meta, dict):
            raise SystemExit("[publish] delta 资产缺失或没有 manifest 记录：%s" % path.name)
        if path.stat().st_size != meta.get("bytes") or sha256_of(path) != meta.get("sha256"):
            raise SystemExit("[publish] delta 资产哈希或大小不一致：%s" % path.name)
        delta_paths.append(path)
    split_paths = []
    for artifact_id, item in (manifest.get("split_assets") or {}).items():
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise SystemExit("[publish] 拆分资产条目不合法：%s" % artifact_id)
        path = stage_dir / item["name"]
        meta = (manifest.get("files") or {}).get(path.name)
        if not path.is_file() or not isinstance(meta, dict):
            raise SystemExit("[publish] 拆分资产缺失或没有 manifest 记录：%s" % path.name)
        if path.stat().st_size != meta.get("bytes") or sha256_of(path) != meta.get("sha256"):
            raise SystemExit("[publish] 拆分资产哈希或大小不一致：%s" % path.name)
        inspected = component_modules()["component_packages"].inspect_artifact(path, artifact_id)
        if not inspected.get("ok"):
            raise SystemExit("[publish] 拆分资产自检失败：%s" % path.name)
        split_paths.append(path)
    return {"stage": stage_dir, "exe": exe_path, "zip": zip_path,
            "installer": installer_path, "component": component_path,
            "ocr_component": ocr_component_path, "delta": delta_paths,
            "split_assets": split_paths, "manifest": manifest_path}


def _verified_component(stage_dir: Path, manifest: dict, name: str, feature: str) -> Path:
    """组件包资产逐项核：文件在、清单有记录、大小与哈希一致、按装机规则自检通过。"""
    component_path = stage_dir / name
    if not component_path.is_file():
        raise SystemExit("[publish] 组件包资产缺失：%s（请重新 --prepare）" % component_path)
    meta = (manifest.get("files") or {}).get(component_path.name)
    if not isinstance(meta, dict):
        raise SystemExit("[publish] manifest 里没有 %s 的清单记录" % component_path.name)
    if component_path.stat().st_size != meta.get("bytes"):
        raise SystemExit("[publish] %s 大小与 manifest 不符（%d ≠ %s）：文件被动过，拒绝发布"
                         % (component_path.name, component_path.stat().st_size, meta.get("bytes")))
    if sha256_of(component_path) != meta.get("sha256"):
        raise SystemExit("[publish] %s SHA-256 与 manifest 不符：文件被动过，拒绝发布"
                         % component_path.name)
    inspect_component(component_path, feature)
    return component_path


def remote_tag_commit(tag: str) -> str:
    """只读查询 origin 上同名 tag 的最终提交（peeled 优先，轻量 tag 取其值）。

    EXTRA-1：ls-remote 的 pattern 按完整引用名尾部匹配——只给精确 `<tag>` 一个
    pattern 时，附注 tag 的 `<tag>{}` peeled 行**不会**被返回，解析器只能拿到
    tag 对象 SHA，与提交 SHA 比对必然误报指向不符。所以同时请求
    `refs/tags/<tag>` 与 `<tag>^{}` 两个 pattern（peeled 行仍优先取用）。
    返回 "" 表示查询成功且 origin 上没有这个 tag；查询命令失败直接抛错拒绝，
    绝不把「查不到」和「查询失败」混为一谈——后者可能是网络/权限问题，
    当成不存在会绕过远端核验。
    """
    out = run(["git", "ls-remote", "--tags", "origin", tag, tag + "^{}"])
    peeled = ""
    lightweight = ""
    for line in out.strip().splitlines():
        sha, _, ref = line.partition("\t")
        ref = ref.strip()
        if ref == "refs/tags/%s^{}" % tag:       # 附注 tag 的 peeled 值（最终提交）优先
            peeled = sha.strip()
        elif ref == "refs/tags/%s" % tag:        # 轻量 tag 行（或附注 tag 对象本身）
            lightweight = sha.strip()
    return peeled or lightweight


def ensure_tag(tag: str, expect_commit: str) -> None:
    """让 origin 上的 tag 指向已核验的 expect_commit；任何不一致都在写入前拒绝，不 force。

    矩阵：远端已正确 → 复用；远端缺失且本地正确 → 显式 push 本地已核验 tag；
    两边都缺 → 创建显式绑定 expect_commit 的新附注 tag 再 push；本地或远端指向
    不一致 → 拒绝（不重写历史 tag）。push 完成后再查一次远端指向确认落地。
    """
    local_pointed = ""
    if run(["git", "tag", "-l", tag]).strip():
        local_pointed = run(["git", "rev-parse", tag + "^{}"]).strip()   # 解引用附注 tag 到提交
        if local_pointed != expect_commit:
            raise SystemExit("[publish] 本地 tag %s 指向 %s，与本次发布提交 %s 不一致。"
                             "不重写历史 tag：请核对该 tag 属于哪次发布，或修正 VERSION 后重来"
                             % (tag, local_pointed[:12], expect_commit[:12]))
    remote_pointed = remote_tag_commit(tag)
    if remote_pointed and remote_pointed != expect_commit:
        raise SystemExit("[publish] origin 上的 tag %s 指向 %s，与本次发布提交 %s 不一致："
                         "GitHub Release 会使用远端 tag，不得在错误指向上传。不 force 改写，"
                         "请人工核对该 tag 属于哪次发布" % (tag, remote_pointed[:12], expect_commit[:12]))
    if remote_pointed == expect_commit:
        print("   tag %s 已存在且远端指向本次提交，复用" % tag)
        return
    # 走到这里：远端缺失，且本地要么缺失要么已核对一致
    if not local_pointed:
        # 显式把新 tag 绑定到已核验提交——不靠「执行当时的 HEAD」默认值
        run(["git", "tag", "-a", tag, expect_commit, "-m", "%s %s" % (PRODUCT_NAME, tag)])
    run(["git", "push", "--quiet", "origin", tag])
    pushed = remote_tag_commit(tag)
    if pushed != expect_commit:
        raise SystemExit("[publish] push 后远端 tag %s 指向 %s ≠ %s：落地核验失败，"
                         "请人工检查远端状态后再试" % (tag, pushed[:12] or "（空）", expect_commit[:12]))
    print("   已创建并推送 tag %s → %s" % (tag, pushed[:12]))


def release_notes(tag: str) -> str:
    """取 CHANGELOG 里最新一节，并附上与资产名同源的下载行。

    下载名不再手写：GitHub 曾把中文前缀规范化，人工补救过一次（R16）。
    """
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    buf: list[str] = []
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if buf:
                break
            buf.append(line)
            continue
        if buf:
            buf.append(line)
    body = "\n".join(buf).strip()
    version = tag[1:] if tag.startswith("v") else tag
    download = ("**下载**：`%s`（安装版，推荐） · `%s`（单 EXE） · `%s`（完整 ZIP）\n\n"
                "**可选手机控制组件**：`%s`，也可在程序帮助中下载并安装。\n\n---\n\n"
                % (installer_asset_name(version), exe_asset_name(version),
                   zip_asset_name(version), component_asset_name(version)))
    return (body or tag) + "\n\n" + download


def publish(tag: str, assets: list[Path], clobber: bool = False) -> None:
    env = dict(os.environ)
    exists = subprocess.run([str(GH), "release", "view", tag],
                            capture_output=True, text=True, env=env,
                            encoding="utf-8", errors="replace")
    if exists.returncode == 0:
        if not clobber:
            raise SystemExit("[publish] Release %s 已存在：默认不覆盖已有附件。"
                             "确认要覆盖时显式加 --clobber（旧附件会被替换）" % tag)
        print("   Release %s 已存在，按 --clobber 覆盖附件" % tag)
        run([str(GH), "release", "upload", tag, *[str(a) for a in assets],
             "--clobber"], env=env)
        return
    notes_file = DIST / (".notes-" + tag + ".md")
    notes_file.write_text(release_notes(tag), encoding="utf-8")
    # --verify-tag：远端缺 tag 时让 gh 中止，禁止它从默认分支自动补一个
    # 未经我们核验的 tag（发布前 ensure_tag 已把远端 tag 对齐到已核验提交）
    run([str(GH), "release", "create", tag,
         "--verify-tag",
         "--title", "%s %s" % (PRODUCT_NAME, tag),
         "--notes-file", str(notes_file),
         *[str(a) for a in assets]], env=env)
    notes_file.unlink(missing_ok=True)


def confirm_publish(tag: str, assume_yes: bool) -> None:
    """外部发布的 user-gate：要么显式 --yes，要么人工输入 yes；其他输入一律中止。"""
    if assume_yes:
        print("[publish] 使用 --yes 跳过交互确认（仍然要求 main+干净工作区+资产核验通过）")
        return
    answer = input("即将创建 tag %s 并上传 GitHub Release（外部副作用）。输入 yes 继续："
                   % tag).strip().lower()
    if answer != "yes":
        raise SystemExit("未确认，已中止（没有创建 tag，也没有上传任何内容）")


def asset_digest(assets: dict) -> dict:
    """候选资产指纹：主程序、安装器、两个组件包和 manifest 全部纳入复核。

    组件必须一起算：少算一项时，那个组件 ZIP 在确认等待期被替换不会让指纹变化，
    发布前门禁就无法证明「用户拿到的组件包」还是核验过的那一份。
    """
    digest = {
        key: sha256_of(assets[key])
        for key in ("zip", "exe", "installer", "component", "ocr_component", "manifest")
    }
    if "delta" in assets:
        digest["delta"] = [sha256_of(path) for path in assets.get("delta", [])]
    if "split_assets" in assets:
        digest["split_assets"] = [sha256_of(path) for path in assets.get("split_assets", [])]
    return digest


def do_publish(tag: str, assume_yes: bool, version: str, clobber: bool = False) -> None:
    """外部发布：门禁 → 资产核验 → 人工确认 → 复核 → tag → 上传，副作用全部在核验之后。

    正式本机资产 = 独立 EXE + 完整 ZIP + 安装版安装器 + 手机控制组件 + 验证码识别组件 + manifest 六项；
    publish 不自动构建、
    不调用 make_portable/绿色版组包，也不隐式同步 local/server 分发分支
    （兼容发行流程另行授权）。
    人工确认可能等待很久：确认后、第一次 Git 写入前必须重验「同一干净 main、
    同一完整 HEAD、同一 VERSION、同一批资产」——期间任何变化都中止并要求
    重新核验确认，绝不静默改用新候选；上传前再比对一次资产指纹。
    """
    commit_before = source_commit()   # 门禁一：干净 main，返回完整 HEAD（确认前快照）
    derived = tag_of(version)
    if tag != derived:                # 门禁二：tag 只由 VERSION 推导
        raise SystemExit("[publish] tag %s 与 VERSION 推导的 %s 不一致："
                         "tag 只能由 VERSION 推导，不接受手写覆盖" % (tag, derived))
    verified = verify_release_assets(version)   # 门禁三：资产与来源逐项核验（任何副作用之前）
    digest_before = asset_digest(verified)
    confirm_publish(tag, assume_yes)            # 门禁四：人工确认（在 tag/上传之前）

    # FG1：确认可能等了很久——确认后、第一次 Git 写入前，重验来源与资产都没变
    commit = source_commit()
    if commit != commit_before:
        raise SystemExit("[publish] 确认期间 HEAD 从 %s 变成 %s（切分支/新提交？）："
                         "确认结论只对当时的来源有效，已中止；请重新核验后再确认发布"
                         % (commit_before[:12], commit[:12]))
    rechecked = verify_release_assets(version)   # VERSION/来源/资产任何一项变了都会在这里拒绝
    if asset_digest(rechecked) != digest_before:
        raise SystemExit("[publish] 确认期间候选资产被替换（哈希变化）：确认结论已失效，"
                         "已中止；请重新核验资产后再确认发布")
    assets = rechecked
    print("[publish] 来源：main@%s；目标 tag：%s" % (commit[:12], tag))

    print("[1/2] tag ...")
    ensure_tag(tag, commit)

    # 临近上传最后再比对一次资产指纹：tag 与上传之间也不该有替换窗口
    if asset_digest(verify_release_assets(version)) != digest_before:
        raise SystemExit("[publish] 上传前发现候选资产被替换（哈希变化）：已中止上传")
    print("[2/2] 上传 Release ...")
    upload_assets = [assets["zip"], assets["exe"], assets["installer"],
                     assets["component"], assets["ocr_component"]]
    upload_assets.extend(assets.get("delta", []))
    upload_assets.extend(assets.get("split_assets", []))
    upload_assets.append(assets["manifest"])
    publish(tag, upload_assets, clobber)

    print("\n完成：https://github.com/Env0i/campus-activity-assistant/releases/tag/%s" % tag)
    print("[提示] 绿色版/服务器版打包与 local/server 分发分支同步属兼容发行流程，需另行授权执行。")


def main() -> int:
    ap = argparse.ArgumentParser(description="打 Release（版本号读 VERSION，默认只做只读检查）")
    ap.add_argument("tag", nargs="?",
                    help="兼容校验输入：必须与 VERSION 推导一致；不再单独触发发布")
    ap.add_argument("--check", action="store_true", help="只读检查（默认行为，可省略）")
    ap.add_argument("--prepare", action="store_true",
                    help="本地准备 EXE/ZIP 资产（不打 tag、不上传、不要求 main）")
    ap.add_argument("--publish", action="store_true",
                    help="外部发布：核验资产 + 干净 main + 人工确认，才打 tag 并上传 GitHub")
    ap.add_argument("--yes", action="store_true", help="publish 的非交互确认（其余门禁照常）")
    ap.add_argument("--clobber", action="store_true",
                    help="允许覆盖已有 Release 的附件（默认拒绝覆盖，保护已发布产物）")
    ap.add_argument("--without-component", action="store_true",
                    help="prepare 时不打手机控制组件包（会让「安装手机控制」不可用）")
    ap.add_argument("--cloudflared",
                    help="prepare 打包组件时内置的 cloudflared.exe（默认 local/bin/cloudflared.exe）")
    ap.add_argument("--delta-base",
                    help="prepare 时使用历史 onedir 版本目录生成 delta 资产（默认不生成）")
    ap.add_argument("--delta-base-version",
                    help="--delta-base 对应的三段版本号")
    ap.add_argument("--split-components", action="store_true",
                    help="prepare 时同时构建 schema2 runtime/model/tool 资产")
    args = ap.parse_args()
    stages = [args.check, args.prepare, args.publish]
    if sum(1 for s in stages if s) > 1:
        raise SystemExit("[release] --check / --prepare / --publish 三阶段互斥，一次只选一个")
    version = read_version()
    derived = tag_of(version)
    if args.tag:
        given = args.tag if args.tag.startswith("v") else "v" + args.tag
        if given != derived:
            raise SystemExit("[release] 位置 tag %s 与 VERSION 推导的 %s 不一致："
                             "tag 只由 VERSION 推导" % (given, derived))
        if not any(stages):
            raise SystemExit("[release] 位置 tag 不再单独触发发布；请显式 --publish"
                             "（或 --check / --prepare）")

    if args.publish:
        do_publish(derived, args.yes, version, args.clobber)
        return 0
    if args.prepare:
        stage_local_assets(version,
                           with_component=not args.without_component,
                           cloudflared=args.cloudflared,
                           delta_base=args.delta_base,
                           delta_base_version=args.delta_base_version,
                           split_components=args.split_components)
        return 0
    check_only(version)   # 默认与 --check：零副作用
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
