"""构建版本目录文件级增量 ZIP 和旁路 JSON 清单（离线工具）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "local"
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))

import update_delta  # noqa: E402


def build_outputs(base_dir: Path, target_dir: Path, base_version: str,
                  target_version: str, output: Path) -> tuple[Path, Path]:
    delta = update_delta.build_delta(base_dir, target_dir, base_version, target_version)
    if output.suffix.lower() == ".zip":
        archive = output
        manifest_path = output.with_suffix(".json")
    else:
        output.mkdir(parents=True, exist_ok=True)
        stem = "delta-%s-to-%s" % (base_version, target_version)
        archive = output / (stem + ".zip")
        manifest_path = output / (stem + ".json")
    update_delta.write_delta_zip(delta, archive, target_dir=target_dir)
    public = {key: value for key, value in delta.items() if not key.startswith("_")}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_part = manifest_path.with_name(manifest_path.name + ".part")
    try:
        manifest_part.write_text(json.dumps(public, ensure_ascii=False, sort_keys=True,
                                            indent=2) + "\n", encoding="utf-8")
        manifest_part.replace(manifest_path)
    except Exception:
        manifest_part.unlink(missing_ok=True)
        raise
    return archive, manifest_path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成 onedir 文件级增量 ZIP")
    parser.add_argument("base_dir", nargs="?")
    parser.add_argument("target_dir", nargs="?")
    parser.add_argument("base_version", nargs="?")
    parser.add_argument("target_version", nargs="?")
    parser.add_argument("--base-dir", dest="base_dir_opt")
    parser.add_argument("--target-dir", dest="target_dir_opt")
    parser.add_argument("--base-version", dest="base_version_opt")
    parser.add_argument("--target-version", dest="target_version_opt")
    parser.add_argument("-o", "--output", required=True,
                        help="输出 ZIP 路径或输出目录")
    args = parser.parse_args(argv)
    values = {
        "base_dir": args.base_dir_opt or args.base_dir,
        "target_dir": args.target_dir_opt or args.target_dir,
        "base_version": args.base_version_opt or args.base_version,
        "target_version": args.target_version_opt or args.target_version,
    }
    if any(value is None for value in values.values()):
        parser.error("需要 base_dir、target_dir、base_version、target_version")
    archive, manifest = build_outputs(Path(values["base_dir"]), Path(values["target_dir"]),
                                      values["base_version"], values["target_version"],
                                      Path(args.output))
    print(json.dumps({"zip": str(archive), "manifest": str(manifest)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
