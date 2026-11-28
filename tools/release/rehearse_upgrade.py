#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发版前升级演练：让某一版客户端用自己的更新代码，在与真实默认安装位置
等长的目录里应用增量包，并量出实际触碰到的最长路径。

为什么要演练：1.3.3 实机从 1.3.2 升级时增量包应用失败，根因是旧客户端把
staging 名与工作目录名层层叠拼，路径顶到 Windows 默认上限；而
LongPathsEnabled=1 的机器上超长路径并不报错，所以判定必须由程序量路径，
不能依赖系统报错。做法：按 --client-ref 取该版本的 updater.py 与
update_delta.py（git 引用用只读的 git show，或 worktree 用当前工作区），
摆成包结构放进临时目录；复制基线版本目录到一个绝对路径长度等于
C:\\Users\\<用户名>\\AppData\\Local\\Programs\\CampusActivityWatch\\versions
的演练版本根，staging 用固定 32 字符名；起 ``python -I`` 子进程装审计钩子，
调用该版本客户端的 stage_update，回传一行 JSON；父进程按
「返回 ok + mode=delta + 最长路径≤259」判定并给退出码。

用法（只动临时目录，不联网、不碰真实安装目录与数据目录）：

    python tools/release/rehearse_upgrade.py --client-ref v1.3.3 --base-dir <基线版本目录> --base-version 1.3.2 --delta <增量 zip> --target-dir <目标版本目录> --target-version 1.3.3

边界：git 只用 show 只读；演练版本根与客户端代码临时目录结束即删；
目标清单由父进程用当前工作区的 update_delta 计算，经 JSON 传给子进程，
子进程不再 import 工作区代码。

@author Author
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 真实默认安装版本根 C:\Users\<用户名>\AppData\Local\Programs\CampusActivityWatch\versions
# 里用户名之外的固定段共 61 字符：C:\Users\ 9 + \AppData 8 + \Local 6 +
# \Programs 9 + \CampusActivityWatch 20 + \versions 9。
TARGET_ROOT_BASE = 61
DEFAULT_USERNAME_LENGTH = 20
# Windows 默认 MAX_PATH=260 含结尾空字符，能写进普通 API 的路径最长 259。
PATH_LIMIT = 259
SUBPROCESS_TIMEOUT_S = 300
_VERSION_RE = r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
# staging 固定名 32 字符，与前端请求号最长形态等长：前端 update/actions.js
# 生成 dl- + 13 位时间戳（Date.now）+ - + 6 位随机，加 .staging- 前缀恰 32。
# 时间戳用固定样本，保证同一台机器重复演练的路径长度可复现。
STAGING_NAME = ".staging-dl-1764300000000-abcdef"
CLIENT_MODULES = (
    "local/infrastructure/update/updater.py",
    "local/infrastructure/update/update_delta.py",
)

# 子进程脚本：装审计钩子量最长路径，调该版本客户端的 stage_update。
# 审计事件名与路径参数位置对照 Python 3.12 官方审计事件表：open(path, mode,
# flags)；os.rename(src, dst, src_dir_fd, dst_dir_fd)——os.replace 也走这个
# 事件名，两个路径都量；os.remove(path, dir_fd)——os.unlink 同名；
# os.rmdir(path, dir_fd)；os.mkdir(path, mode, dir_fd)；os.scandir(path)。
# shutil.copyfile(src, dst) 只有 copy/copyfile 走；Windows 上 copy2 直接走
# CopyFile2 快路径不经过它，所以要再收 copystat/copymode 才能量到逐文件
# 复制落点。os.stat 不在审计表里。
RUNNER_SOURCE = '''\
# -*- coding: utf-8 -*-
"""演练子进程：装审计钩子量最长路径，调该版本客户端的 stage_update，
向 stdout 打一行 JSON（唯一协议，ensure_ascii 保证任何控制台都能读）。"""
import json
import os
import sys

# 审计事件名 -> 需要测长的路径参数下标，只收官方审计事件表里带路径的条目。
PATH_ARGS = {
    "open": (0,),
    "os.chdir": (0,),
    "os.chmod": (0,),
    "os.chown": (0,),
    "os.link": (0, 1),
    "os.listdir": (0,),
    "os.mkdir": (0,),
    "os.rename": (0, 1),
    "os.remove": (0,),
    "os.rmdir": (0,),
    "os.scandir": (0,),
    "os.symlink": (0, 1),
    "os.utime": (0,),
    "os.walk": (0,),
    "shutil.copyfile": (0, 1),
    "shutil.copymode": (0, 1),
    "shutil.copystat": (0, 1),
    "shutil.copytree": (0, 1),
    "shutil.move": (0, 1),
    "shutil.rmtree": (0,),
    "tempfile.mkdtemp": (0,),
    "tempfile.mkstemp": (0,),
}

measured = {"max": ""}
seen_events = set()


def as_text(value):
    """审计参数可能是 str/bytes/Path/fd：能当路径的转成文本，其余不算。"""
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return os.fsdecode(value)
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    return None


def record(event, args):
    """钩子本体：绝不抛异常，否则被审计的操作本身会被打断。"""
    spec = PATH_ARGS.get(event)
    if spec is None:
        return
    seen_events.add(event)
    for index in spec:
        try:
            if index >= len(args):
                continue
            text = as_text(args[index])
            if not text:
                continue
            if not os.path.isabs(text):
                text = os.path.abspath(text)
            if len(text) > len(measured["max"]):
                measured["max"] = text
        except Exception:
            return


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        params = json.load(handle)
    sys.path.insert(0, params["client_dir"])
    import infrastructure.update.updater as updater

    error = None
    result = {}
    # 钩子装在模块导入之后、调用之前：只量 stage_update 实际触碰的路径。
    sys.addaudithook(record)
    try:
        result = updater.stage_update(
            params["base_dir"], params["delta"], params["staging"],
            mode="delta", base_version=params["base_version"],
            target_manifest=params["target_manifest"],
            target_version=params["target_version"])
    except Exception as exc:  # 把异常作为结果带回父进程，不崩协议
        error = "%s: %s" % (type(exc).__name__, exc)
    report = {
        "result": result,
        "max_len": len(measured["max"]),
        "max_path": measured["max"],
        "events": sorted(seen_events),
        "error": error,
    }
    sys.stdout.write(json.dumps(report, ensure_ascii=True) + "\\n")


main()
'''


def read_client_bytes(client_ref, rel_path):
    """按 git 引用（只读 git show）或 worktree 读出该版客户端模块的字节。"""
    if client_ref == "worktree":
        path = ROOT / rel_path
        if not path.is_file():
            raise SystemExit("工作区缺少客户端模块：%s" % path)
        return path.read_bytes()
    result = subprocess.run(
        ["git", "show", "%s:%s" % (client_ref, rel_path)],
        cwd=str(ROOT), capture_output=True)
    if result.returncode != 0:
        raise SystemExit(
            "git show 取不到 %s 的 %s（引用不存在？）：%s"
            % (client_ref, rel_path,
               result.stderr.decode("utf-8", "replace").strip()))
    return result.stdout


def load_client_modules(client_ref, client_dir):
    """把该版客户端模块按包结构摆放，相对导入（from .update_delta）也能用。"""
    package = client_dir / "infrastructure" / "update"
    package.mkdir(parents=True)
    (client_dir / "infrastructure" / "__init__.py").write_bytes(b"")
    (package / "__init__.py").write_bytes(b"")
    for rel in CLIENT_MODULES:
        (package / Path(rel).name).write_bytes(read_client_bytes(client_ref, rel))


def compute_target_manifest(target_dir, target_version):
    """用当前工作区 update_delta 算目标清单：父进程算好经 JSON 传给子进程。"""
    module_path = ROOT / "local" / "infrastructure" / "update" / "update_delta.py"
    spec = importlib.util.spec_from_file_location(
        "campus_rehearse_target_update_delta", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.manifest_from_directory(target_dir, version=target_version)


def build_equal_length_root(work_parent, username_length):
    """在 work_parent 下建一个绝对路径与真实默认版本根完全等长的演练版本根。

    填充目录名用重复字母 p 加数字尾凑长度；父目录太短都放不下最短合法
    目录名时只能换更短的父目录，这里报错退出，不悄悄降级成不等长的根。
    """
    target_len = TARGET_ROOT_BASE + username_length
    parent = Path(work_parent).resolve()
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit("--work-parent 无法创建：%s（%s）" % (parent, exc))
    pad_len = target_len - len(str(parent)) - len(os.sep)
    if pad_len < 1:
        raise SystemExit(
            "--work-parent 太长：%s（%d 字符）下建不出 %d 字符的等长版本根，"
            "请换一个更短的父目录。" % (parent, len(str(parent)), target_len))
    for attempt in range(100):
        suffix = "" if attempt == 0 else "-%02d" % attempt
        pad_name = "p" * (pad_len - len(suffix)) + suffix
        root = parent / pad_name
        try:
            root.mkdir()
        except FileExistsError:
            continue
        return root
    raise SystemExit("--work-parent 下 %d 字符的填充目录名都被占用：%s" % (pad_len, parent))


def _stderr_tail(completed):
    text = completed.stderr.decode("utf-8", "replace").strip()
    return text[-400:] if text else ""


def _empty_report(error):
    return {"error": error, "result": {}, "max_len": None,
            "max_path": "", "events": []}


def parse_child_report(completed):
    """子进程约定 stdout 最后一行是演练 JSON；解析不到就把 stderr 尾部带回。"""
    lines = [line.strip() for line in
             completed.stdout.decode("utf-8", "replace").splitlines()
             if line.strip()]
    if lines:
        try:
            report = json.loads(lines[-1])
        except ValueError:
            report = None
        if isinstance(report, dict) and {"result", "max_len", "events"} <= set(report):
            return report
        error = "子进程最后一行不是演练 JSON：%r" % lines[-1][:200]
    else:
        error = "子进程没有输出（exit=%d）" % completed.returncode
    return _empty_report("%s；stderr：%s" % (error, _stderr_tail(completed)))


def run_client_stage(client_dir, params):
    """把演练参数写给子进程，跑该版本客户端的 stage_update 并解析回传。"""
    params_file = client_dir / "rehearse-params.json"
    params_file.write_text(json.dumps(params, ensure_ascii=False),
                           encoding="utf-8")
    runner = client_dir / "_rehearse_runner.py"
    runner.write_text(RUNNER_SOURCE, encoding="utf-8")
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(runner), str(params_file)],
            capture_output=True, timeout=SUBPROCESS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return _empty_report("子进程超过 %d 秒没结束" % SUBPROCESS_TIMEOUT_S)
    except OSError as exc:
        return _empty_report("子进程无法启动：%s" % exc)
    return parse_child_report(completed)


def judge(report):
    """三条判定：stage_update ok、mode=delta、最长路径不超上限；返回不满足项。"""
    reasons = []
    result = report.get("result") or {}
    if report.get("error"):
        reasons.append("子进程没有完成演练：%s" % report["error"])
    if not result.get("ok"):
        reasons.append("stage_update 未成功：%s"
                       % json.dumps(result, ensure_ascii=True, sort_keys=True))
    if result.get("mode") != "delta":
        reasons.append("mode 不是 delta：%r" % result.get("mode"))
    max_len = report.get("max_len")
    if max_len is None:
        reasons.append("没有量到任何带路径参数的审计事件")
    elif max_len > PATH_LIMIT:
        reasons.append("最长路径 %d 超过上限 %d：%s"
                       % (max_len, PATH_LIMIT, report.get("max_path")))
    return reasons


def _require_dir(value, label):
    path = Path(value).resolve()
    if not path.is_dir():
        raise SystemExit("%s 不是目录：%s" % (label, path))
    return path


def run_rehearsal(*, client_ref, base_dir, base_version, delta, target_dir,
                  target_version, username_length=DEFAULT_USERNAME_LENGTH,
                  work_parent=None):
    """跑完整演练，返回报告；等长版本根与客户端代码临时目录用完即删。"""
    if not isinstance(client_ref, str) or not client_ref:
        raise SystemExit("--client-ref 必须是 git 引用或 worktree")
    try:
        user_len = int(username_length)
    except (TypeError, ValueError):
        raise SystemExit("--username-length 必须是整数：%r" % username_length) from None
    if not 0 <= user_len <= 64:
        raise SystemExit("--username-length 必须在 0..64：%r" % username_length)
    if not _version_ok(base_version):
        raise SystemExit("--base-version 必须是 x.y.z：%r" % base_version)
    if not _version_ok(target_version):
        raise SystemExit("--target-version 必须是 x.y.z：%r" % target_version)
    base_dir = _require_dir(base_dir, "--base-dir")
    target_dir = _require_dir(target_dir, "--target-dir")
    delta = Path(delta).resolve()
    if not delta.is_file():
        raise SystemExit("--delta 不存在：%s" % delta)
    client_dir = Path(tempfile.mkdtemp(prefix="campus-rehearse-client-"))
    root = None
    try:
        load_client_modules(client_ref, client_dir)
        manifest = compute_target_manifest(target_dir, target_version)
        root = build_equal_length_root(work_parent or tempfile.gettempdir(),
                                       user_len)
        base_copy = root / base_version
        shutil.copytree(base_dir, base_copy)
        params = {
            "client_dir": str(client_dir),
            "base_dir": str(base_copy),
            "delta": str(delta),
            "staging": str(root / STAGING_NAME),
            "base_version": base_version,
            "target_version": target_version,
            "target_manifest": manifest,
        }
        report = run_client_stage(client_dir, params)
        report["reasons"] = judge(report)
        report["ok"] = not report["reasons"]
        report["client_ref"] = client_ref
        report["rehearsal_root"] = str(root)
        return report
    finally:
        if root is not None:
            shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(client_dir, ignore_errors=True)


def _version_ok(version):
    return bool(isinstance(version, str) and re.fullmatch(_VERSION_RE, version))


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="发版前升级演练：用某版客户端自己的更新代码在等长版本根里"
                    "应用增量包，并量出实际触碰到的最长路径")
    parser.add_argument("--client-ref", required=True,
                        help="git 引用（如 v1.3.3）或字面量 worktree")
    parser.add_argument("--base-dir", required=True, help="基线版本目录")
    parser.add_argument("--base-version", required=True, help="基线版本号")
    parser.add_argument("--delta", required=True, help="增量 zip")
    parser.add_argument("--target-dir", required=True,
                        help="目标版本目录，用来算目标清单")
    parser.add_argument("--target-version", required=True, help="目标版本号")
    parser.add_argument("--username-length", type=int,
                        default=DEFAULT_USERNAME_LENGTH,
                        help="等长根按 C:\\Users\\<N 个字符> 凑齐（默认 20）")
    parser.add_argument("--work-parent", default=None,
                        help="放演练目录的父目录（默认系统临时目录）")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    report = run_rehearsal(
        client_ref=args.client_ref, base_dir=args.base_dir,
        base_version=args.base_version, delta=args.delta,
        target_dir=args.target_dir, target_version=args.target_version,
        username_length=args.username_length, work_parent=args.work_parent)
    for reason in report["reasons"]:
        print("不满足：%s" % reason)
    print("演练结论：%s；最长路径 %s 字符（上限 %d）：%s"
          % ("通过" if report["ok"] else "不通过", report.get("max_len"),
             PATH_LIMIT, report.get("max_path")))
    print("实际量到的审计事件：%s" % ", ".join(report.get("events") or []))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
