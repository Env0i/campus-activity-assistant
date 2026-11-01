# -*- coding: utf-8 -*-
"""在显式临时目录构建两个独立组件，不安装依赖，不改基础程序。

@author Author
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
import sys
import zipfile
from pathlib import Path

from infrastructure import component_packages as cp

LOCAL = Path(__file__).resolve().parent


def output_root(value):
    requested = Path(value)
    root = requested.resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if not requested.is_absolute() or root == temp or not root.is_relative_to(temp):
        raise ValueError("output-dir must be an absolute subdirectory of the system temp directory")
    return root


def build(feature, output_dir, cloudflared=None):
    cp._key(feature)
    if not cp.supported():
        raise ValueError("Windows x64 is required")
    output = output_root(output_dir)
    dependencies = ("segno",) if feature == "phone_control" else ("ddddocr", "onnxruntime")
    missing = [name for name in ("PyInstaller",) + dependencies if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError("Missing dependencies: " + ", ".join(missing))
    if feature == "phone_control" and not cloudflared:
        # 没有内置 cloudflared 的 phone 组件没有远程通道；宁可构建失败也不产半个包
        raise ValueError(
            "cloudflared_required：phone_control 组件必须内置 cloudflared，请用 --cloudflared 指定"
            "与 component_packages.CLOUDFLARED_VERSION 一致的二进制；不再回退到 PATH。")
    run_root = output / feature
    # 每次构建占独立目录；既有结果不删除、不复用旧 dist。
    run_root.mkdir(parents=True, exist_ok=False)
    wrapper = run_root / "entry.py"
    wrapper.write_text("from advanced_helper import main\nraise SystemExit(main(%r))\n" % feature,
                       encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--console",
               "--name", "feature-helper", "--paths", str(LOCAL),
               "--distpath", str(run_root / "dist"), "--workpath", str(run_root / "work"),
               "--specpath", str(run_root)]
    for name in dependencies:
        command.extend(["--collect-all", name])
    # 避免 phone 的静态分析把可选 OCR 打进同一个组件。
    if feature == "phone_control":
        command.extend(["--exclude-module", "ddddocr", "--exclude-module", "onnxruntime"])
    else:
        command.extend(["--exclude-module", "segno"])
    command.append(str(wrapper))
    subprocess.run(command, check=True)
    directory = run_root / "dist" / "feature-helper"
    cloudflare = None
    if feature == "phone_control":
        binary = Path(cloudflared).resolve(strict=True)
        info = subprocess.run([str(binary), "--version"], check=True, capture_output=True,
                              text=True, encoding="utf-8", timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        found = cp.parse_cloudflared_version(info.stdout or "")
        if found != cp.CLOUDFLARED_VERSION:
            raise ValueError(
                "cloudflared %s required, got %s；组件包的版本是写死的，"
                "换版本要先改 component_packages.CLOUDFLARED_VERSION"
                % (cp.CLOUDFLARED_VERSION, found or info.stdout.strip()[:60]))
        target = directory / cp.CLOUDFLARED_NAME
        target.parent.mkdir()
        shutil.copyfile(binary, target)
        cloudflare = {"version": found, "sha256": cp.sha256(target)}
    files = {p.relative_to(directory).as_posix(): cp.sha256(p)
             for p in sorted(directory.rglob("*")) if p.is_file()}
    # target/app_version 是给下载与安装流程看的：前者说明架构，后者说明这个组件包
    # 与哪个版本的主程序配套。platform/version 仍保留，装机校验靠它们。
    manifest = {"schema": 1, "feature": feature, "version": cp.version(),
                "app_version": cp.version(), "target": "win-x64",
                "platform": "windows-x64", "entry": "feature-helper.exe", "files": files}
    if cloudflare:
        manifest["cloudflared"] = cloudflare
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    cp.validate_directory(directory, feature)
    cp._helper(directory / "feature-helper.exe", feature=feature, probe=True)
    archive = output / ("%s-%s-windows-x64.zip" % (feature, cp.version()))
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(directory).as_posix())
    total = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
    if archive.stat().st_size > cp.MAX_ARCHIVE:
        raise ValueError("Archive exceeds import size limit")
    report = {"archive": str(archive), "sha256": cp.sha256(archive),
              "compressed_bytes": archive.stat().st_size, "extracted_bytes": total,
              "files": len(files) + 1, "version": cp.version(), "feature": feature}
    (run_root / "build-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True, choices=sorted(cp.FEATURES))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cloudflared")
    args = parser.parse_args()
    try:
        build(args.feature, args.output_dir, args.cloudflared)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, "Build failed: %s\n" % exc)


if __name__ == "__main__":
    main()
