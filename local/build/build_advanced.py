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

# 脚本在 local/build/：local/ 是上一级。脚本直接运行时 sys.path[0] 是 build/ 而不是 local/，
# infrastructure 包在 local/ 下，所以先把 local/ 补进导入路径再导入。
LOCAL = Path(__file__).resolve().parent.parent
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

from infrastructure import component_packages as cp  # noqa: E402


ARTIFACTS = {
    "phone_control_runtime": {
        "feature": "phone_control", "role": "runtime", "dependencies": ("segno",),
    },
    "phone_control_cloudflared": {
        "feature": "phone_control", "role": "tool", "dependencies": (),
    },
    "relogin_ocr_runtime": {
        "feature": "relogin_ocr", "role": "runtime",
        "dependencies": ("ddddocr", "onnxruntime"),
    },
    "relogin_ocr_model": {
        "feature": "relogin_ocr", "role": "model", "dependencies": (),
    },
}


def output_root(value):
    requested = Path(value)
    root = requested.resolve()
    temp = Path(tempfile.gettempdir()).resolve()
    if not requested.is_absolute() or root == temp or not root.is_relative_to(temp):
        raise ValueError("output-dir must be an absolute subdirectory of the system temp directory")
    return root


def _check_platform_and_dependencies(dependencies, *, require_pyinstaller=True):
    if not cp.supported():
        raise ValueError("Windows x64 is required")
    names = ("PyInstaller",) if require_pyinstaller else ()
    missing = [name for name in names + tuple(dependencies)
               if importlib.util.find_spec(name) is None]
    if missing:
        raise ValueError("Missing dependencies: " + ", ".join(missing))


def _pyinstaller_directory(feature, run_root, dependencies):
    wrapper = run_root / "entry.py"
    wrapper.write_text("from advanced_helper import main\nraise SystemExit(main(%r))\n" % feature,
                       encoding="utf-8")
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--console",
               "--name", "feature-helper", "--paths", str(LOCAL),
               "--distpath", str(run_root / "dist"), "--workpath", str(run_root / "work"),
               "--specpath", str(run_root)]
    for name in dependencies:
        command.extend(["--collect-all", name])
    if feature == "phone_control":
        command.extend(["--exclude-module", "ddddocr", "--exclude-module", "onnxruntime"])
    else:
        command.extend(["--exclude-module", "segno"])
    command.append(str(wrapper))
    subprocess.run(command, check=True)
    directory = run_root / "dist" / "feature-helper"
    if not directory.is_dir():
        raise ValueError("PyInstaller output missing: %s" % directory)
    return directory


def _remove_ocr_models(directory):
    """runtime 只带推理代码；common*.onnx 全部由 model artifact 提供。"""
    for path in directory.rglob("*.onnx"):
        if path.name.casefold().startswith("common"):
            path.unlink()


def _model_source_files():
    spec = importlib.util.find_spec("ddddocr")
    if spec is None or not spec.origin:
        raise ValueError("Missing dependency: ddddocr")
    package = Path(spec.origin).resolve().parent
    sources = {
        "common.onnx": package / "common.onnx",
        "common_old.onnx": package / "common_old.onnx",
    }
    if any(not path.is_file() for path in sources.values()):
        raise ValueError("ddddocr model files are missing")
    charsets = importlib.import_module("ddddocr.charsets")
    metadata = {
        "charsets-beta.json": {"charset": list(charsets.CHARSET_BETA), "word": False,
                               "image": [-1, 64], "channel": 1},
        "charsets-old.json": {"charset": list(charsets.CHARSET_OLD), "word": False,
                              "image": [-1, 64], "channel": 1},
    }
    return sources, metadata


def _artifact_manifest(artifact, files, *, entry=None, extra=None):
    spec = ARTIFACTS[artifact]
    data = {
        "schema": 2,
        "artifact": artifact,
        "artifact_id": artifact,
        "feature": spec["feature"],
        "role": spec["role"],
        "version": cp.version(),
        "asset_version": cp.version(),
        "app_version": cp.version(),
        "target": "win-x64",
        "platform": "windows-x64",
        "protocol": 1,
        "compatibility_id": "campus-activity-1",
        "entry": entry or "",
        "requires": ["relogin_ocr_model"] if artifact == "relogin_ocr_runtime" else [],
        "files": files,
    }
    if extra:
        data.update(extra)
    data["content_sha256"] = cp.artifact_content_sha256(data)
    return data


def _write_manifest(directory, manifest):
    (directory / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_artifact_directory(directory, artifact):
    manifest = cp.validate_artifact_directory(directory, artifact)
    if manifest.get("content_sha256") != cp.artifact_content_sha256(manifest):
        raise ValueError("artifact content hash mismatch")
    return manifest


def _zip_directory(directory, archive):
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                package.write(path, path.relative_to(directory).as_posix())


def _finish_artifact(artifact, output, run_root, directory, manifest):
    _write_manifest(directory, manifest)
    _validate_artifact_directory(directory, artifact)
    entry = manifest.get("entry")
    if entry and manifest["role"] == "runtime":
        cp._helper(directory / entry, feature=manifest["feature"], probe=True)
    archive = output / ("%s-%s-windows-x64.zip" % (artifact, cp.version()))
    _zip_directory(directory, archive)
    total = sum(p.stat().st_size for p in directory.rglob("*") if p.is_file())
    if archive.stat().st_size > cp.MAX_ARCHIVE:
        raise ValueError("Archive exceeds import size limit")
    report = {"archive": str(archive), "sha256": cp.sha256(archive),
              "compressed_bytes": archive.stat().st_size, "extracted_bytes": total,
              "files": len(manifest["files"]) + 1, "version": cp.version(),
              "feature": manifest["feature"], "artifact": artifact,
              "role": manifest["role"]}
    (run_root / "build-result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


def _build_legacy(feature, output_dir, cloudflared=None):
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


def _build_artifact(artifact, output_dir, cloudflared=None):
    spec = ARTIFACTS.get(artifact)
    if spec is None:
        raise ValueError("unknown_artifact")
    _check_platform_and_dependencies(
        spec["dependencies"], require_pyinstaller=spec["role"] == "runtime")
    output = output_root(output_dir)
    run_root = output / artifact
    run_root.mkdir(parents=True, exist_ok=False)
    directory = run_root / "dist" / artifact
    directory.mkdir(parents=True)
    extra = {}
    entry = None
    if spec["role"] == "runtime":
        directory.rmdir()
        directory = _pyinstaller_directory(spec["feature"], run_root, spec["dependencies"])
        if artifact == "relogin_ocr_runtime":
            _remove_ocr_models(directory)
        entry = "feature-helper.exe"
    elif artifact == "phone_control_cloudflared":
        if not cloudflared:
            raise ValueError("cloudflared_required：独立 phone_control tool artifact 需要 --cloudflared")
        binary = Path(cloudflared).resolve(strict=True)
        info = subprocess.run([str(binary), "--version"], check=True, capture_output=True,
                              text=True, encoding="utf-8", timeout=10,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        found = cp.parse_cloudflared_version((info.stdout or "") + " " + (info.stderr or ""))
        if found != cp.CLOUDFLARED_VERSION:
            raise ValueError("cloudflared %s required, got %s" %
                             (cp.CLOUDFLARED_VERSION, found or (info.stdout or "").strip()[:60]))
        target = directory / cp.CLOUDFLARED_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(binary, target)
        extra["tool"] = {"name": "cloudflared", "version": found}
        entry = cp.CLOUDFLARED_NAME
    elif artifact == "relogin_ocr_model":
        sources, metadata = _model_source_files()
        models = directory / "models"
        models.mkdir(parents=True)
        for name, source in sources.items():
            shutil.copy2(source, models / name)
        for name, value in metadata.items():
            (models / name).write_text(json.dumps(value, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    files = {p.relative_to(directory).as_posix(): cp.sha256(p)
             for p in sorted(directory.rglob("*")) if p.is_file()}
    manifest = _artifact_manifest(artifact, files, entry=entry, extra=extra)
    if spec["role"] == "tool":
        manifest["tool"]["sha256"] = files[entry]
        manifest["content_sha256"] = cp.artifact_content_sha256(manifest)
    return _finish_artifact(artifact, output, run_root, directory, manifest)


def build(feature, output_dir, cloudflared=None, *, artifact=None):
    """兼容旧的 feature 调用，并接受四种 artifact 名称。"""
    selected = artifact or feature
    if selected in ARTIFACTS:
        return _build_artifact(selected, output_dir, cloudflared)
    return _build_legacy(selected, output_dir, cloudflared)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--feature", choices=sorted(cp.FEATURES),
                       help="兼容入口：构建 schema=1 单体组件 ZIP")
    group.add_argument("--artifact", choices=sorted(ARTIFACTS),
                       help="构建 schema=2 可复用 artifact ZIP")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cloudflared")
    args = parser.parse_args()
    try:
        build(args.feature or args.artifact, args.output_dir, args.cloudflared)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, "Build failed: %s\n" % exc)


if __name__ == "__main__":
    main()
