#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校园活动自动报名 · 本机版（WebView2 外壳）。

界面在 ui/ 下用 HTML/CSS 写，这里只做三件事：

1. 起窗口、加载 ui/index.html；
2. 把 grab.py 的能力暴露成页面可调的方法（window.pywebview.api.*）；
3. 把子进程输出实时推给页面（window.onBackend.log / .state / .done）。

业务逻辑一律留在 grab.py：换界面不用碰它，界面出问题也能直接命令行复现。

@author Author
"""
from __future__ import annotations

import atexit
import contextlib
import ctypes
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid

# 演示模式的数据根隔离必须在导入 runtime_paths 之前完成：
# DATA_DIR 是导入期常量，晚一步就已经指向真实 %LOCALAPPDATA%，bootstrap 会读真实凭证。
# 只认显式 --demo；不覆盖用户自己指定的 CAMPUS_DATA_DIR。
if "--demo" in sys.argv and not os.environ.get("CAMPUS_DATA_DIR", "").strip():
    _demo_root = tempfile.mkdtemp(prefix="campus-demo-")
    os.environ["CAMPUS_DATA_DIR"] = _demo_root
    atexit.register(shutil.rmtree, _demo_root, True)
from datetime import datetime, timedelta
from pathlib import Path

import webview

from signup_plan import PlanCoordinator, TaskSpec, classify_signup_mode, validate_plan
from infrastructure.clock.business_clock import BusinessClock, ClockUnavailable
from infrastructure.clock.time_contract import school_epoch, school_time_text, configure_time_source
from infrastructure.update.update_check import check_latest_release
from infrastructure.update import update_check as _update_check
from urllib.error import HTTPError, URLError
from infrastructure.update import updater

# 登录态/偏好统一数据根：开发用 local/data，冻结 EXE 用 %LOCALAPPDATA%
# （CAMPUS_DATA_DIR 可覆盖），与 grab-worker 解析出同一份登录文件
from infrastructure.stores.runtime_paths import (DATA_DIR, LOG_FILE, LOG_LOCK_FILE, SESSION_FILE,
                           UI_STATE_FILE, ensure_data_dir, migration_record, config_file_path, legacy_config_candidates)

# 分层依赖（只准向下）：app（interface 外观）→ application → domain 纯规则；
# 外部副作用统一走 infrastructure 适配器。旧模块级名字保留为兼容包装/再导出，
# 测试与调用方按原名注入、patch 的语义不变。
from domain.signup import cancel_rules as _cancel_rules
from domain.common import demo_data as _demo_data
from domain.desktop import lifecycle_rules as _lifecycle_rules
from domain.worker import log_events as _log_events
from domain.login import login_rules as _login_rules
from domain.plan import plan_rules as _plan_rules
from domain.signup import retry_rules as _retry_rules
from domain.common import time_text as _time_text
from domain.worker import worker_lines as _worker_lines
from domain.common.errors import ClosingError as _ClosingError
from infrastructure.stores import lifecycle_store as _lifecycle_store
from infrastructure.stores import prefs_store as _prefs_store
from infrastructure.desktop import process_tree as _process_tree
from infrastructure.phone import phone_http as _phone_http
from infrastructure.components import advanced_features as _advanced_features
from infrastructure.components import component_packages as _component_packages
from infrastructure.stores import credential_store as _credential_store
from infrastructure.notify import feishu_webhook as _feishu_webhook_post
from infrastructure.stores import phone_session_store as _phone_session_store
from infrastructure.phone import phone_qr as _phone_qr
from infrastructure.phone import tunnel_manager as _tunnel_manager
from infrastructure.desktop import single_instance as _single_instance
from application import coordination as _coordination
from application.login import login_service as _login_service
from application.login import login_recovery as _login_recovery
from application.activity import activity_list_service as _activity_list_service
from application.login import login_relay_service as _login_relay_service
from application.login import relogin_entry as _relogin_entry
from application.login.auto_relogin import AutoReloginMonitor
from application.phone import phone_service as _phone_service
from application.components import advanced_component_service as _advanced_component
from application.components import component_projection as _component_projection
from application.components import component_actions as _component_actions
from application.plan import plan_service as _plan_service
from application.signup import signup_cancellation as _signup_cancellation
from application.worker import worker_service as _worker_service
from application.desktop import desktop_lifecycle as _desktop_lifecycle
from application.desktop import desktop_window as _desktop_window
from application.desktop import clock_service as _clock_service
from application.desktop import update_service as _update_service
from application.settings import feishu_settings as _feishu_settings

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", HERE))
# 和报名进程同一份配置：界面只读其中的 feishu_webhook 一个键
CONFIG_FILE = config_file_path(frozen=getattr(sys, "frozen", False), here=HERE, data_dir=DATA_DIR)
UI = RESOURCE_ROOT / "ui" / "index.html"


def resolve_worker_path(frozen: bool, here: Path, resource_root: Path) -> Path:
    """worker 唯一来源（纯函数，供契约测试）：源码态跑 here/grab.py；
    冻结态只用打包进资源根的 grab-worker.exe——绝不退回 EXE 旁的旧文件，
    也不依赖启动 cwd：独立单 EXE 被拷到任何空目录都必须自足。"""
    if frozen:
        return resource_root / "grab-worker.exe"
    return here / "grab.py"


GRAB = resolve_worker_path(getattr(sys, "frozen", False), HERE, RESOURCE_ROOT)
PREFS = UI_STATE_FILE
# 登录剩余时间不再按写死的寿命常数推算：真实界面只显示「剩余时间未知」，
# 也没观测到 token 自然过期（2026-11-03 架构修订 S3）。界面改为读上次校验时刻。
# GitHub 最新版本页：用户点「GitHub 最新版本」时由系统默认浏览器打开，
# 启动时不自动联网检查，也不在 WebView 里跳转
RELEASES_LATEST_URL = "https://github.com/Env0i/campus-activity-assistant/releases/latest"
CREDENTIAL_FILE = DATA_DIR / "relogin-credentials.dpapi.json"
_CREDENTIAL_STORE_OK = None
# 电脑自己识别验证码连续失败这么多次，才把图交给手机上的人来打。
# 只改这一个数字就能调整「多信任 OCR」的程度。
_MANUAL_RELOGIN_AFTER = 3
# G2：组件下载失败写进运行记录的说法，与界面红条（ui/features/components/state.js 的 PHONE_DOWNLOAD_REASON）同源
_DOWNLOAD_FAIL_REASONS = {
    "network_error": "连不上发布页",
    "http_error": "GitHub 暂时无法响应，请稍后重试",
    "rate_limited": "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载后导入",
    "timeout": "连接超时",
    "not_published": "发布页上还没有这个版本的组件包，可以稍后再试，或手动下载后导入",
}
# 报名进程确认登录失效后等界面自动登录的秒数（决策 015）：本机自动登录要开浏览器、
# 认验证码，留够时间；只有电脑能自己登录时才传给 worker，否则传 0、照旧直接结束
RELOGIN_WAIT_S = 45.0


def _credential_store_available() -> bool:
    """本机加密存储（DPAPI）是否可用：首次探测后缓存，结果只用于界面与门禁。

    探测失败一律当「不可用」，绝不退化成明文保存。
    """
    global _CREDENTIAL_STORE_OK
    if _CREDENTIAL_STORE_OK is None:
        probe = getattr(_credential_store, "_protect", None)
        try:
            _CREDENTIAL_STORE_OK = bool(probe and probe(b"probe"))
        except Exception:
            _CREDENTIAL_STORE_OK = False
    return _CREDENTIAL_STORE_OK
# 手机设备信任：只存 token 的 SHA-256，仍由 DPAPI 封在外层，明文 token 只活在手机浏览器里
DEVICE_FILE = DATA_DIR / "phone-devices.dpapi.json"
PHONE_LOG = DATA_DIR / "phone.log"
_PHONE_LOG_LOCK = threading.Lock()
_PHONE_LOG_MAX_BYTES = 512 * 1024


def phone_log(message: str) -> None:
    """手机访问专用日志：一行一条，落 DATA_DIR/phone.log，超过 512KB 轮转一次。

    只记事实（方法/路径/状态码/主机名/带了哪些 cookie 名），
    绝不记配对码、cookie 值、账号密码与验证码——这文件会被随手贴出去。
    """
    if DEMO:
        # 演示/测试模式不落真实日志：否则替身数据会混进用户排障用的文件
        return
    try:
        with _PHONE_LOG_LOCK:
            try:
                if PHONE_LOG.stat().st_size > _PHONE_LOG_MAX_BYTES:
                    PHONE_LOG.replace(PHONE_LOG.with_name("phone.log.1"))
            except OSError:
                pass
            with PHONE_LOG.open("a", encoding="utf-8", newline=chr(10)) as fp:
                fp.write("%s %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    message))
                fp.write(chr(10))
    except Exception:  # noqa: BLE001 - 日志写不进去也不能影响业务
        pass


def read_version() -> str:
    """读唯一的版本源 VERSION：源码从项目根、绿色版从脚本旁、冻结程序从打包资源根。

    版本格式只认 major.minor.patch；文件缺失或格式非法直接启动失败并给开发者
    可读错误——把版本读取失败静默成旧版本，会发布出 GUI、文件名、tag 对不上号的包。
    不能依赖启动 cwd：三种形态各有一个固定候选路径，按序取第一个存在的。
    """
    candidates = [
        RESOURCE_ROOT / "VERSION",   # 冻结程序：build_exe --add-data 打进资源根
        HERE / "VERSION",            # 绿色版：make_portable 复制到 app.py 旁
        HERE.parent / "VERSION",     # 源码：仓库根
    ]
    for path in candidates:
        if path.is_file():
            text = path.read_text(encoding="utf-8").strip()
            if re.fullmatch(r"\d+\.\d+\.\d+", text):
                return text
            raise SystemExit("[X] VERSION 内容不是 major.minor.patch：%r（%s）"
                             % (text, path))
    raise SystemExit("[X] 找不到 VERSION 文件（尝试过 %s）；版本号只有一个来源，不回退写死值"
                     % "、".join(str(p) for p in candidates))


def license_candidates(resource_root: Path, here: Path) -> tuple:
    """随包 LICENSE 的唯一候选链（纯函数，供契约测试）：冻结资源根 → 脚本旁 → 仓库根。

    与上面 VERSION 的三形态同构；只找 LICENSE 这一个名字，
    绝不指向任何登录态/凭据文件。
    """
    return (resource_root / "LICENSE", here / "LICENSE", here.parent / "LICENSE")


APP_VERSION = read_version()


def update_version_paths(*, here=HERE, version=APP_VERSION):
    """返回版本目录更新端口；程序版本与数据目录保持两个根。"""
    configured = os.environ.get("CAMPUS_VERSION_ROOT", "").strip()
    base = Path(here)
    if configured:
        root = Path(configured)
    elif base.name == str(version) and base.parent.name == "versions":
        # 版本启动器进入 versions/<版本>/ 主程序后，更新根仍是安装根下的
        # versions，而不是当前版本目录里的第二层 versions。
        root = base.parent
    else:
        root = base / "versions"
    return {"root": root, "current_file": root.parent / "current.json",
            "base_dir": root / version}

# 条款的当前版本：与 docs/USER_AGREEMENT.md、docs/PRIVACY_POLICY.md 顶部的版本字段
# 是同一份（契约测试会核对两处一致）。条款内容更新时同步改这两处，
# 界面据此判断是否需要重新弹出条款确认。
#
# 版本形如「日期」或「日期-rN」：本轮修订修正了许可边界、通信披露和
# 「版本变化必须再次点击同意」的接受语义，旧版本（2026-10-27）的同意
# 记录不能静默覆盖新内容，所以提升到 -r1 而不是沿用同一天。
# 2026-11-03 升到 r4：披露报名默认直发、运行时密钥只在内存、自动登录代勾
# 学校《隐私协议》，以及用本工具登录会顶掉同一账号在其他地方的登录。
# 2026-11-07 升到 r5：只改说法——直发改称直接提交、条款入口改到设置、生效日期改为版本日、条款要点补适用范围句。
# 2026-11-09 升到 r6：只补披露——隐私第 3 节补手机访问两种通道与 GitHub 下载，第 1 节补手机配对记录，对外通信由三类改为四类。
TERMS_VERSION = "2026-11-09-r6"


def terms_unknown_payload() -> dict:
    """条款状态不可知时的统一拒绝载荷（界面据此提示重试，不猜）。"""
    return {"ok": False, "error": "terms_required",
            "text": "还没确认当前版本的使用条款；点「查看条款」阅读后再继续。"}


def terms_state(prefs: dict) -> dict:
    """条款同意快照（纯函数，供契约测试隔离求值）。

    只读 ui.json 偏好里的 terms_version / terms_accepted_at 两个键：不碰
    任何登录文件，也不把同意状态写进运行日志。bootstrap 把这份快照
    带给界面，界面按「已同意版本 != 当前版本」判定门禁。
    """
    return {
        "version": TERMS_VERSION,
        "accepted_version": str((prefs or {}).get("terms_version") or ""),
        "accepted_at": str((prefs or {}).get("terms_accepted_at") or ""),
    }


def _feishu_webhook() -> str:
    """只取 config.json 里的 feishu_webhook；没配、读不出或不是 https 都当没配。"""
    return _feishu_settings.configured_hook(CONFIG_FILE, read=_read_config_text)


def _read_config_text(path) -> str:
    """读配置文件全文：缺失抛 FileNotFoundError，其余读失败原样抛，由调用方拒绝保存。"""
    return Path(path).read_text(encoding="utf-8")


def _component_title(feature: str) -> str:
    """组件的中文名：下载日志与「没有发布组件包」提示用，和 update_check 同一份。"""
    return _update_check.COMPONENT_TITLES.get(str(feature), str(feature))


# 主程序升级后自动补装组件：先验证码识别（决定登录失效能不能自己恢复），
# 再手机控制（远程入口最后才恢复）。
AUTO_UPDATE_FEATURES = (_advanced_features.RELOGIN_OCR, _advanced_features.PHONE_CONTROL)


def auto_update_outdated_components(*, frozen, demo, prefs, state_of, download,
                                    wait_idle=None, log=None) -> list:
    """把「用户启用过、只差版本」的组件换新，每项只试一次，不重试。

    只处理 status == outdated：没启用过的不动（尊重用户当初的选择），
    其它错误（文件损坏、平台不支持）也不在这里偷偷重装——那会把真实故障
    盖掉。download 返回 busy 或失败时只写一句运行记录，留给设置里一键更新。
    返回尝试过的键，方便测试和运行记录核对顺序。
    """
    attempted = []
    if not frozen or demo:
        return attempted
    rows = state_of(prefs) or {}
    for key in AUTO_UPDATE_FEATURES:
        row = rows.get(key) or {}
        if not row.get("enabled") or row.get("status") != "outdated":
            continue
        title = _component_title(key)
        attempted.append(key)
        if log:
            log("%s组件需要随主程序更新，开始自动更新。" % title)
        try:
            result = download(key) or {}
        except Exception as exc:
            result = {"ok": False, "error": type(exc).__name__}
        if not result.get("ok"):
            error = str(result.get("error") or "")
            if log:
                log("%s组件没有自动更新%s，可以在设置里点「更新组件」。" % (
                    title, "（%s）" % error if error else ""))
            continue
        # 必须等这一项真正落定再开下一项：同一个下载事务不能并发
        outcome = wait_idle(key) if wait_idle else "installed"
        if outcome == "installed":
            if log:
                log("%s组件已更新。" % title)
        elif log:
            log("%s组件还没有更新完，可以在设置里点「更新组件」。" % title)
    return attempted


def _retry_options_payload() -> dict:
    """三种重试模式的权威选项与默认值：桌面/手机共用这一份口径。

    缺截止的 0 模式回退秒数也在这里声明，不各维护第二套清单。
    """
    return {
        "default": int(_retry_rules.DEFAULT_RETRY_SECONDS),
        "fallback_seconds": int(_retry_rules.DEFAULT_RETRY_SECONDS),
        "adaptive_cap_seconds": int(_retry_rules.ADAPTIVE_SECONDS),
        "choices": [
            {"value": 120, "label": "2 分钟"},
            {"value": 600, "label": "10 分钟"},
            {"value": 1800, "label": "30 分钟"},
            {"value": 3600, "label": "1 小时"},
            {"value": int(_retry_rules.ADAPTIVE_RETRY),
             "label": "自动延长（最多 25 分钟）"},
            {"value": 0, "label": "直到报名截止"},
        ],
    }


CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# 组件诊断：结构化错误码 → 人话主文案。技术细节只进运行记录（日志），
# 主提示保持一句话——用户要的是「该做什么」，不是 WinError 2。
WORKER_PROBLEM_TEXT = {
    "worker_missing": "程序组件缺失，请重新下载完整版本",
    "worker_permission": "程序组件无法读取，请重新下载完整版本",
    "spawn_failed": "程序组件启动失败，请重新下载完整版本",
}
# 离线自检（--runtime-check）给内置 worker --help 的时限
RUNTIME_CHECK_TIMEOUT_S = 60


def worker_problem() -> str:
    """启动 worker 前的组件自检：返回结构化错误码，组件齐备返回空串。

    源码态要求 grab.py 可读；冻结态要求资源根里的 grab-worker.exe 存在且可执行。
    只看文件事实，不发起任何进程/网络动作——调用方据此决定拒绝还是放行。
    """
    if getattr(sys, "frozen", False):
        if not GRAB.is_file():
            return "worker_missing"
        if not os.access(GRAB, os.R_OK | os.X_OK):
            return "worker_permission"
        return ""
    if not GRAB.is_file():
        return "worker_missing"
    if not os.access(GRAB, os.R_OK):
        return "worker_permission"
    return ""


def _component_error(exc: Exception) -> str:
    """把**进程创建**抛出的异常归类为结构化组件错误码（check/list/login 收尾共用）。

    实现已下沉 domain.login.login_rules（纯分类）；此处保留旧名字兼容包装。
    """
    return _login_rules.component_error(exc)


# 关闭屏障语义类型在 domain.common.errors；旧名字保留为再导出（同 class 对象）。
# 调用方必须把它与组件异常分开处理——关闭拒绝不得归类为 worker_* 组件码，
# 也不得冒充报名失败向上抛。

# --demo：用假数据起界面，方便调样式、截图，不需要登录
DEMO = False


def demo_items() -> list[dict]:
    """演示样例集：纯数据模型在 domain.common.demo_data，时间与格式化在此注入。"""
    return _demo_data.demo_items(time.time(), school_time_text)


# main 建立 BusinessClock 后登记快照路径与 owner（_env 给 worker 用）
_CLOCK_ENV = {"path": "", "owner": ""}


def _env() -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # 把主程序解析好的数据根传给 worker：即使 worker 所在目录不同，
    # 两侧也会读写同一份 session/storage_state
    env["CAMPUS_DATA_DIR"] = str(DATA_DIR)
    # 同实例时钟快照：worker 复用父进程校时结果，不各自另选源（决策 012）
    if _CLOCK_ENV.get("path"):
        env["CAMPUS_CLOCK_SNAPSHOT"] = _CLOCK_ENV["path"]
        env["CAMPUS_CLOCK_OWNER"] = _CLOCK_ENV["owner"]
    return env


def worker_command(*args: str) -> list[str]:
    """普通 Python 调 grab.py；冻结主程序改调资源根里内置的 worker exe。"""
    if getattr(sys, "frozen", False):
        return [str(GRAB)] + list(args)
    return [sys.executable, str(GRAB)] + list(args)


def resolve_update_launcher_path(frozen: bool, here: Path, resource_root: Path) -> Path:
    """更新启动器只来自固定 payload 入口，不接受界面传入的任意路径。"""
    if frozen:
        return here / "update-launcher.exe"
    return here / "update_launcher.py"


def update_launcher_command(mode: str, *, staging: str = "", version_root: Path | str = "",
                            target_version: str = "", parent_pid: int | None = None,
                            current_file: Path | str = "") -> list[str]:
    """构造启动器命令；路径由版本端口计算，调用方只传已校验的 staging。"""
    launcher = resolve_update_launcher_path(getattr(sys, "frozen", False), HERE, RESOURCE_ROOT)
    command = ([str(launcher)] if getattr(sys, "frozen", False)
               else [sys.executable, str(launcher)])
    command += [("--start" if mode == "start" else "--apply"),
                "--version-root", str(version_root)]
    if current_file:
        command += ["--current-file", str(current_file)]
    if mode == "apply":
        command += ["--staging", str(staging), "--target-version", str(target_version),
                    "--parent-pid", str(parent_pid if parent_pid is not None else os.getpid())]
    return command


def version_sweep_target(*, frozen, here, version):
    """冻结且正从 versions/<当前版本>/ 运行时返回 (版本根, current.json, 运行目录)，否则 None。

    独立 EXE、源码态没有版本目录，什么都不清理：不能把别人的 versions 当成自己的。
    """
    if not frozen:
        return None
    base = Path(here)
    if base.name != str(version) or base.parent.name != "versions":
        return None
    return base.parent, base.parent.parent / "current.json", base


def sweep_versions_in_background(*, frozen=None, here=None, version=None,
                                 sweep=None, log=None):
    """启动后在后台线程清理一次版本目录；不满足条件返回 None。

    清理的是更新残留和超出 current/previous 的旧版本（updater.sweep_version_root），
    当前进程所在目录始终保留，数据目录不在版本根下。任何异常只经 log 回调记录
    （log(failed=数量) 或 log(error=异常类型名)，不带路径），绝不影响主程序启动。
    """
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if frozen:  # 先迁旧地址：下面的清理会删掉更早的版本目录，旧位置的地址随之消失
        try:
            _feishu_settings.migrate_legacy(config_file_path(frozen=True, here=HERE if here is None else here, data_dir=DATA_DIR),
                                            legacy_config_candidates(HERE if here is None else here), read=_read_config_text, write=_prefs_store.atomic_write)
        except Exception as exc:  # noqa: BLE001 - 迁移失败不挡启动
            if log:
                log(error=type(exc).__name__)
    target = version_sweep_target(frozen=frozen, here=HERE if here is None else here,
                                  version=APP_VERSION if version is None else version)
    if target is None:
        return None
    root, current_file, running = target
    run_sweep = sweep or updater.sweep_version_root

    def _run() -> None:
        try:
            result = run_sweep(root, current_file=current_file, keep_dir=running)
            failed = result.get("failed") if isinstance(result, dict) else None
            if failed and log:
                log(failed=len(failed))   # 只报数量，不带目录名
        except Exception as exc:  # noqa: BLE001 - 清理失败不能影响启动
            if log:
                log(error=type(exc).__name__)

    thread = threading.Thread(target=_run, name="version-sweep", daemon=True)
    thread.start()
    return thread


def version_switch_available(*, frozen=None, here=None, version=None, launcher=None) -> bool:
    """能不能走版本目录切换：冻结态、update-launcher.exe 存在、当前进程正从 versions/<当前版本>/ 运行。

    三者缺一就走完整安装器：独立 EXE、源码态都没有版本目录可切换，下载版本目录包
    只会让用户在 update_launch 被拒绝后走进死胡同。参数只给测试注入，生产全部取默认。
    """
    frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not frozen:
        return False
    here = HERE if here is None else Path(here)
    version = APP_VERSION if version is None else version
    if version_sweep_target(frozen=True, here=here, version=version) is None:
        return False
    path = launcher if launcher is not None else resolve_update_launcher_path(
        True, here, RESOURCE_ROOT)
    return Path(path).is_file()


# 偏好存储原语已下沉 infrastructure.stores.prefs_store；旧名字保留为再导出，
# 测试与调用方继续用 app.load_prefs_from / app._atomic_write_prefs 等注入。
load_prefs_from = _prefs_store.load_from
_load_prefs_for_update = _prefs_store.load_for_update
_atomic_write_prefs = _prefs_store.atomic_write
_PrefsLockTimeout = _prefs_store.PrefsLockTimeout
_acquire_prefs_file_lock = _prefs_store.acquire_file_lock
_release_prefs_file_lock = _prefs_store.release_file_lock
_prefs_transaction = _prefs_store.prefs_transaction


def load_prefs() -> dict:
    return load_prefs_from(PREFS)


# ---- 手机访问通道偏好 ------------------------------------------------------
# 只记两件事：上次用的是哪个通道、要不要在下次启动时自动恢复 Tailscale。
# 不记地址、不记设备、不记配对码：地址由探测现算，设备信任有自己的存储。
_PHONE_PREF_NAMESPACE = "phone_access"
_PHONE_CHANNELS = ("tailscale", "cloudflare", "local")


def _phone_access_prefs(prefs: dict) -> dict:
    """读通道偏好；形状非法一律当「没配过」，不猜用户的意图。"""
    block = prefs.get(_PHONE_PREF_NAMESPACE) if isinstance(prefs, dict) else None
    if not isinstance(block, dict):
        block = {}
    channel = str(block.get("preferred_channel") or "").strip().lower()
    if channel not in _PHONE_CHANNELS:
        channel = ""
    return {"preferred_channel": channel,
            "tailscale_autostart": bool(block.get("tailscale_autostart"))}


# 帮助面板会定时来问状态，二维码按地址缓存一份：地址不变就不重复画 PNG
_QR_CACHE: dict = {}


def _phone_qr_data(address: str) -> str:
    """按地址缓存二维码 data URI；地址变了才重画，失败按「没有二维码」处理。"""
    if not address:
        return ""
    cached = _QR_CACHE.get(address)
    if cached is not None:
        return cached
    try:
        data = _phone_qr.png_data_uri(address, root=DATA_DIR)
    except Exception:  # noqa: BLE001 - 画不出二维码不该让整个状态接口失败
        return ""
    _QR_CACHE.clear()          # 旧地址的图再没人要，只留当前这一份
    _QR_CACHE[address] = data
    return data


# ---- 独立北京时间（决策 012）-----------------------------------------------
# 生产 main 恒注入 BusinessClock；未注入时这里是显式不可用，绝不回退本机墙钟。
# 测试需要可读时钟时必须显式注入 Fake（见 local/tests/fixtures/business_clock.py）。
class _UnavailableClock:
    """未配置时钟：所有业务读数显式失败，不提供任何墙钟替身。"""

    owner_id = ""
    generation = 0

    def now(self) -> float:
        raise ClockUnavailable("业务时钟未配置")

    def bounds(self):
        raise ClockUnavailable("业务时钟未配置")

    def elapsed_s(self) -> float:
        return time.monotonic()      # 仅用于本地监督，不当作业务时刻

    def state(self) -> str:
        return "unavailable"

    @property
    def reason(self) -> str:
        return "业务时钟未配置"

    def request_resync(self) -> None:
        pass

    def snapshot(self) -> dict:
        raise ClockUnavailable("业务时钟未配置")


def _credential_id(token: str) -> str:
    """本机内部凭证摘要（纯规则在 domain.login.login_rules）：只用于把 v2 锚点和具体凭证绑定。"""
    return _login_rules.credential_id(token)


def save_session_timing_anchor(token: str, epoch: float, uncertainty_s: float = 0.0) -> None:
    """新登录成功且有可信北京时间时建立 v2 锚点；换凭证必须换新锚点。"""
    if not token:
        return
    update_prefs({"session_timing_v2": {
        "credential_id": _credential_id(token),
        "saved_epoch": float(epoch),
        "time_source": "ntp",
        "uncertainty_s": round(float(uncertainty_s), 3)}})


# 界面偏好与生命周期心跳共用的持久化锁：读-合并-写必须串行，
# 否则心跳的整份快照会覆盖用户刚存的筛选/引导状态（反之亦然）。
# 锁与事务原语在 infrastructure.stores.prefs_store；这里保留旧常量名供注入/patch。
_PREFS_LOCK = _prefs_store.PREFS_LOCK
_PREFS_LOCK_TIMEOUT_S = _prefs_store.LOCK_TIMEOUT_S   # 生命周期元数据：拿不到就放弃本次写入
_PREFS_SAVE_TIMEOUT_S = _prefs_store.SAVE_TIMEOUT_S   # 用户偏好：给正在收尾的另一个进程留出时间


def update_prefs(patch: dict) -> bool:
    """统一的原子读-合并-写（Api.save_prefs 与生命周期心跳共用同一把锁）。

    实现已下沉 prefs_store.update：这里把 app 模块上**当前**的读、写、事务原语
    传进去，按 app._load_prefs_for_update / app._atomic_write_prefs /
    app._prefs_transaction 打的补丁照样生效。读用严格读：读不到当前偏好就放弃
    整次事务（返回 False、一个字节都不写），免得拿空字典合并再写回、把用户的
    条款同意与筛选一次冲掉；宽松的 app.load_prefs 只给界面与 bootstrap 的无锁
    读用。任何失败（锁拿不到、读不到当前偏好、写不进去）都返回 False，绝不把
    异常抛给界面。调用方可重试用户偏好；可选登录估算落盘失败也不影响真实登录。
    """
    return _prefs_store.update(PREFS, patch, load=lambda: _load_prefs_for_update(PREFS),
                               write=_atomic_write_prefs,
                               transaction=_prefs_transaction)


CLOSE_ACTIONS = ("ask", "hide", "minimize", "exit")


def defer_close_action(callback, delay: float = 0.25) -> None:
    """把「和界面打交道」的关窗动作挪到工作线程去跑。

    closing 事件回调在 UI 主线程里执行，回调里直接 evaluate_js / 弹自家对话框
    会在主线程抢 pywebview 的内部锁，窗口直接变「未响应」（pywebview#1699）。
    所以先取消这次关闭，再从工作线程把要问的话推给界面。
    """

    def _run() -> None:
        try:
            callback()
        except Exception:
            pass

    timer = threading.Timer(max(0.0, float(delay)), _run)
    timer.daemon = True
    timer.start()


def make_tray_icon(*, on_show, on_exit):
    """托盘图标的唯一创建点（纯装配，供 application.desktop_window 注入）。

    import 留在组合根：只有真要建托盘时才加载 pystray 依赖，启动路径不受影响；
    application 层因此不必也不许直接 import infrastructure。
    """
    from infrastructure.desktop import tray_icon as _tray_icon

    return _tray_icon.TrayIcon(on_show=on_show, on_exit=on_exit)


def handle_window_close(api, window, *, defer=None) -> bool:
    """closing 回调的全部判定：返回 True 放行关闭，False 取消。

    与界面交互的部分（弹三选、最小化）一律经 defer 挪走，绝不在主线程直接调用。
    """
    defer = defer or defer_close_action
    if getattr(api, "_close_approved", False):
        return True
    action = resolve_close_action(load_prefs(), api.plan_active_for_close())
    if action == "exit":
        api._close_approved = True
        return True
    if action == "hide":
        defer(api.hide_window)
        return False
    if action == "minimize":
        defer(window.minimize)
        return False
    defer(api.ask_window_close)
    return False


def resolve_close_action(prefs, plan_running: bool) -> str:
    """点右上角 X 之后该做什么：ask（弹三选）/ hide（藏到后台）/ minimize / exit。

    计划在跑或已就绪时一律先问——这时候隐藏、最小化或退出都意味着手机那边可能
    正要打开报名，不能让一次误点静默地把计划带走。
    """
    if plan_running:
        return "ask"
    try:
        window = (prefs or {}).get("window") or {}
        value = str(window.get("close_action") or "")
    except Exception:
        value = ""
    return value if value in CLOSE_ACTIONS else "ask"


def login_state(clock=None) -> dict:
    """登录三态快照：界面靠它区分「从没登录过」和「登录过期」。

    「没有登录」= session.json 不存在、无法解析或缺少 token；只有 token 还在但
    已过期才叫登录态失效。缺 token 时 hours_left 必须是 None——按 saved_at 报
    一个假的小时数会把空壳会话显示成有效。登录有效性永远以学校真实校验为准，
    这些字段绝不参与放行或拦截（S3 起不再输出剩余小时数）。

    E1（计划 20261109，决策 006 修订 2026-11-09）：预计有效按本机 v2 锚点
    （session_timing_v2）+ 可信业务时钟估；估算只作提示，session_expired 恒由
    学校校验决定，估算到点也不算失效。分类规则在 domain.login.login_rules。
    """
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        token = str(data.get("token") or "").strip()
        saved_text = str(data.get("saved_at") or "").strip()
    except Exception:
        return _login_rules.build_session_state("", "", None, None)
    if not token:
        return _login_rules.build_session_state("", "", None, None)
    timing = None
    try:
        timing = (load_prefs() or {}).get("session_timing_v2")
    except Exception:
        timing = None
    now = None
    if clock is not None:
        try:
            now = clock.now()
        except Exception:
            now = None
    return _login_rules.build_session_state(token, saved_text, None, now, timing=timing)


def _last_check_fields(last: dict) -> dict:
    """上次登录校验的时刻与结论（北京时间文本 + valid/expired/unknown）。

    S3：界面显示「上次校验」而不是按写死的寿命倒推剩余小时数。
    只有学校明确给出「有效」或「过期」才原样上报；none / checking / demo /
    认不出的结论一律归 unknown，避免把未确认当成失效或有效。
    """
    result = str((last or {}).get("result") or "unknown")
    state = result if result in ("valid", "expired") else "unknown"
    checked_at = (last or {}).get("checked_at")
    text = None
    if isinstance(checked_at, (int, float)) and checked_at > 0:
        try:
            text = school_time_text(float(checked_at))
        except Exception:
            text = None
    return {"last_check_at": text, "last_check_state": state}


# 时间文本换算已下沉 domain.common.time_text；旧名字保留为兼容包装（学校时间换算
# 在此注入 infrastructure.clock.time_contract.school_epoch，domain/application 不直连混合模块；
# 墙钟读取也留在此界面层，domain 只做纯格式化）。
_parse_local_time = _time_text.parse_local_time
_latest_moment = _time_text.latest_moment


def _now_text() -> str:
    """本地墙钟文本（兼容名；实现在 domain.common.time_text.format_local_text，取时在此）。"""
    return _time_text.format_local_text(datetime.now())


def _seconds_until(ts: str | None, now: "float | None") -> "int | None":
    """学校时间文本距现在多少秒（实现在 domain.common.time_text，换算函数在此注入）。"""
    return _time_text.seconds_until(ts, now, school_epoch)


def _task_deadline(spec) -> "float | None":
    """父层视角的本场绝对截止（实现在 domain.common.time_text，换算函数在此注入）。"""
    return _time_text.task_deadline(spec, school_epoch)

# 生命周期纯记账已下沉 domain.desktop.lifecycle_rules；旧名字保留为再导出。
compute_lifecycle = _lifecycle_rules.compute_lifecycle
compute_lifecycle_v2 = _lifecycle_rules.compute_lifecycle_v2


# 生命周期持久化已下沉 infrastructure.stores.lifecycle_store；旧名字保留为再导出。
AppLifecycle = _lifecycle_store.AppLifecycle





_LIFECYCLE: "AppLifecycle | None" = None
_LIFECYCLE_LOCK = threading.Lock()


def get_lifecycle(now_fn=None) -> AppLifecycle:
    """进程级单例（懒创建）：main() 启动时先建，bootstrap 重复取同一实例。"""
    global _LIFECYCLE
    with _LIFECYCLE_LOCK:
        if _LIFECYCLE is None:
            # 偏好路径从 app 外观注入：测试 patch app.PREFS 后单例仍写隔离文件
            _LIFECYCLE = AppLifecycle(prefs_file=PREFS, now_fn=now_fn)
        return _LIFECYCLE


class _RelayTree:
    """relay worker 的受管句柄：终止走 Job Object，没有所有权时才回退到 Popen。"""

    def __init__(self, tree):
        self.proc = tree.proc
        self._tree = tree

    def terminate(self) -> None:
        try:
            if not self._tree.terminate():
                _kill_tree(self.proc)
        finally:
            self._tree.close()


# L1：拉活动列表前最多等约 8 秒北京时间；等不到照常拉，由 worker 用学校
# 回包的 HTTP Date 头兜底筛选（L2）。测试可 patch 这两个常量。
LIST_CLOCK_WAIT_S = 8.0
LIST_CLOCK_POLL_S = 0.25


class Api(_coordination.CoordinatorFields, _phone_service.PhoneFields,
          _login_recovery.LoginFields, _activity_list_service.ActivityListFields,
          _plan_service.PlanFields, _clock_service.ClockFields,
          _relogin_entry.ReloginEntryFields, _desktop_window.DesktopWindowFields):
    def _published_plan_state(self):
        return self._plan.published_status() if self._plan else ""

    def _make_login_recovery(self):
        return _login_recovery.LoginRecovery(
            coordination=self._coord, lock=self._lock,
            ports={"terms_gate": lambda request_id: self._terms_gate(request_id),
                   "do_check": lambda: self._do_check(),
                   "do_check_inner": lambda: self._do_check_inner(),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "observe_check": lambda result: self._auto_relogin.observe_check(result),
                   "note_conclusion": lambda result: self._note_login_conclusion(result),
                   "silent_state": lambda: self._silent_relogin_state(),
                   "request_recover": lambda: self._auto_relogin.request_recover(),
                   "demo": lambda: DEMO,
                   "run_check": lambda: self._run(worker_command("check"), timeout=90),
                   "closing_error": _ClosingError,
                   "component_error": lambda exc: _component_error(exc),
                   "worker_problem": lambda code: WORKER_PROBLEM_TEXT.get(
                       code, "程序组件启动失败，请重新下载完整版本"),
                   "login_state": lambda: login_state(self._clock),
                   "build_event": lambda *args: _login_service.build_check_event(*args),
                   "last_check_fields": lambda state: _last_check_fields(state),
                   "auto_view": lambda expired: self._auto_relogin.view(expired=expired),
                   "log_event": lambda *args, **kwargs: self._log_event(*args, **kwargs),
                   "push_expired": lambda: self._push_login_expired(),
                   "post_json": lambda url, body: _feishu_webhook_post.post_json(url, body),
                   "relay_state": lambda: self._relay.state(),
                   "mark_bad": lambda: _credential_store.mark_bad(CREDENTIAL_FILE),
                   "clear_staged": lambda: self._relay.clear_staged(),
                   "auto_snapshot": lambda: self._auto_relogin.snapshot()})

    def _make_activity_list(self):
        return _activity_list_service.ActivityListService(
            coordination=self._coord, lock=self._lock, sync_window=lambda: self.SIGNED_SYNC_WINDOW_S,
            ports={"terms_gate": lambda request_id: self._terms_gate(request_id),
                   "do_list": lambda: self._do_list(),
                   "do_list_inner": lambda: self._do_list_inner(),
                   "clock_text": lambda: self._pc_clock_text(),
                   "school_time_text": lambda: school_time_text(now_fn=self._clock_now),
                   "note_error": lambda reason: self._note_pc_list_error(reason),
                   "closing_error": _ClosingError,
                   "component_error": lambda exc: _component_error(exc),
                   "worker_problem": lambda code: WORKER_PROBLEM_TEXT.get(code, "活动列表没能加载"),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "clock_now": lambda: self._clock_now(),
                   "demo": lambda: DEMO, "demo_items": lambda: demo_items(),
                   "wait_clock": lambda: self._wait_for_list_clock(),
                   "run_list": lambda: self._run(worker_command("list", "--json"), timeout=120),
                   "merge": lambda items: self._merge_list_activities(items),
                   "merge_rules": lambda *args: _plan_rules.merge_list_activities(*args),
                   "seconds_until": lambda value, now: _seconds_until(value, now)})

    def _make_signup_cancellation(self):
        return _signup_cancellation.SignupCancellation(
            lock=self._lock, coordination=self._coord, activity_list=self._activity_list,
            busy_text=self.CANCEL_BUSY_TEXT,
            ports={"terms_gate": lambda: self._terms_gate(),
                   "run": lambda aid: self._cancel_signup_run(aid),
                   "after": lambda aid: self._after_cancelled(aid),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "demo": lambda: DEMO, "worker_problem": lambda: worker_problem(),
                   "diagnose_problem": lambda problem: self._emit(
                       "log", "[X] 组件诊断 %s：组件路径 %s" % (problem, GRAB)),
                   "diagnose_error": lambda exc: self._emit(
                       "log", "[X] 组件诊断 %s：%s" % (_component_error(exc), type(exc).__name__)),
                   "worker": lambda aid: self._run(
                       worker_command("cancel", "--id", aid, "--json"),
                       timeout=self.CANCEL_WORKER_TIMEOUT_S),
                   "closing_error": _ClosingError})

    def _make_plan_manager(self):
        return _plan_service.PlanAdmission(
            lock=self._lock, coordination=self._coord,
            activity_list=self._activity_list, login=self._login_recovery,
            ports={"terms_gate": lambda: self._terms_gate(),
                   "start_inner": lambda *args: self._start_plan_inner(*args),
                   "demo": lambda: DEMO, "clock_ready": lambda: self._clock_ready(),
                   "clock_now": lambda: self._clock_now(),
                   "worker_problem": lambda: worker_problem(),
                   "worker_problem_text": lambda problem: WORKER_PROBLEM_TEXT[problem],
                   "classify": lambda *args: classify_signup_mode(*args),
                   "validate": lambda *args, **kwargs: validate_plan(*args, **kwargs),
                   "task_spec": lambda *args, **kwargs: TaskSpec.from_activity(*args, **kwargs),
                   "coordinator": lambda *args, **kwargs: PlanCoordinator(*args, **kwargs),
                   "run_task": lambda *args: self._run_plan_task(*args),
                   "spawn_failure": _SpawnFailure, "closing_error": _ClosingError,
                   "confirm_signed": lambda *args: self._confirm_signed(*args),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "notify_done": lambda snapshot: self._notify_plan_done(snapshot)})

    def _make_worker_service(self):
        return _worker_service.WorkerService(
            lock=self._lock, coordination=self._coord, login=self._login_recovery,
            ports={"spawn": lambda args, **kwargs: spawn_owned(args, cwd=str(HERE), env=_env(), **kwargs),
                   "kill_tree": lambda proc: _kill_tree(proc),
                   "worker_problem": lambda: worker_problem(),
                   "problem_text": lambda problem: WORKER_PROBLEM_TEXT[problem],
                   "busy": lambda: self._is_busy_locked(),
                   "diagnose_problem": lambda problem: self._emit(
                       "log", "[X] 组件诊断 %s：组件路径 %s" % (problem, GRAB)),
                   "component_error": lambda exc: _component_error(exc),
                   "spawn_failure": _SpawnFailure, "closing_error": _ClosingError,
                   "relay_tree": lambda tree: _RelayTree(tree),
                   "pump": lambda *args: self._pump(*args),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "observe_relay": lambda line: self._relay.observe_line(line),
                   "done_result": lambda *args: _login_service.done_result(*args),
                   "anchor_login": lambda: self._anchor_login_success()})

    def _make_desktop_lifecycle(self):
        return _desktop_lifecycle.DesktopLifecycle(
            lock=self._lock, coordination=self._coord, plan_manager=self._plan_manager,
            ports={"stop_tray": lambda: self._stop_tray(),
                   "components": lambda: (getattr(self, "_component_service", None),
                                           getattr(self, "_ocr_component_service", None)),
                   "stop_auto_relogin": lambda: self._auto_relogin.stop(),
                   "shutdown_relay": lambda: self._relay.shutdown(),
                   "stop_tunnel": lambda: self._stop_cloudflare_checked(),
                   "shutdown_phone": lambda: self._phone.shutdown(preserve_devices=True),
                   "clear_phone_channel": lambda: setattr(self, "_phone_channel", ""),
                   "kill_tree": lambda proc: _kill_tree(proc)})

    def _make_clock_service(self, clock):
        return _clock_service.ClockService(
            clock=clock if clock is not None else _UnavailableClock(),
            lock=self._lock, coordination=self._coord, plan_manager=self._plan_manager,
            ports={"demo": lambda: DEMO, "ready": lambda: self._clock_ready(),
                   "now": lambda: self._clock_now(), "snapshot": lambda: self.clock_snapshot(),
                   "payload": lambda: self._clock_payload(),
                   "list_wait": lambda: LIST_CLOCK_WAIT_S, "list_poll": lambda: LIST_CLOCK_POLL_S,
                   "emit": lambda kind, payload: self._emit(kind, payload)})

    def _make_desktop_window(self):
        return _desktop_window.DesktopWindow(
            lock=self._lock, coordination=self._coord,
            ports={"plan": lambda: self._plan,
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "log": lambda message: phone_log(message),
                   "load_prefs": lambda: load_prefs(),
                   "update_prefs": lambda patch: update_prefs(patch),
                   "resolve_close_action": lambda prefs, running: resolve_close_action(
                       prefs, running),
                   "ensure_tray": lambda: self._ensure_tray(),
                   "phone_running": lambda: self._phone.is_running(),
                   "phone_live": lambda: self._phone.has_live_session(),
                   "clock_now": lambda: self._clock_now(),
                   "clock_ready": lambda: self._clock_ready(),
                   "epoch_of": lambda text: school_epoch(text),
                   "time_text_of": lambda epoch: school_time_text(epoch),
                   "plan_done_notice": lambda tasks: _plan_service.plan_done_notice(tasks),
                   "tray_factory": lambda **kwargs: make_tray_icon(**kwargs)})

    def _make_relogin_entry(self):
        return _relogin_entry.ReloginEntry(
            coordination=self._coord, lock=self._lock,
            login_recovery=self._login_recovery, credential_lock=self._credential_lock,
            ports={"terms_gate": lambda: self._terms_gate(),
                   "emit": lambda kind, payload: self._emit(kind, payload),
                   "log_event": lambda *args, **kwargs: self._log_event(*args, **kwargs),
                   "relay": lambda: self._relay,
                   "monitor": lambda: self._auto_relogin,
                   "plan": lambda: self._plan,
                   "demo": lambda: DEMO,
                   "load_prefs": lambda: load_prefs(),
                   "ocr_ready": lambda prefs: _advanced_features.feature_ready(
                       prefs, _advanced_features.RELOGIN_OCR, root=DATA_DIR),
                   "has_credentials": lambda: _credential_store.has_credentials(
                       CREDENTIAL_FILE),
                   "load_credentials": lambda: _credential_store.load(CREDENTIAL_FILE),
                   "save_credentials": lambda user, secret: _credential_store.save(
                       CREDENTIAL_FILE, user, secret),
                   "clear_credentials": lambda: _credential_store.clear(CREDENTIAL_FILE),
                   "credentials_bad": lambda: _credential_store.is_bad(CREDENTIAL_FILE),
                   "store_available": lambda: _credential_store_available(),
                   "worker_command": lambda *args: worker_command(*args),
                   "clock_now": lambda: self._clock_now(),
                   "epoch_of": lambda text: school_epoch(text),
                   "clock_bounds": lambda: self._clock.bounds(),
                   "session_token": lambda: str(json.loads(
                       SESSION_FILE.read_text(encoding="utf-8")).get("token") or "").strip(),
                   "save_anchor": lambda token, epoch, uncertainty: (
                       save_session_timing_anchor(token, epoch, uncertainty)),
                   "note_origin": lambda origin: setattr(self, "_last_login_origin", origin),
                   "refresh_check": lambda: threading.Thread(
                       target=self.check, daemon=True).start(),
                   "wait_s": lambda: RELOGIN_WAIT_S,
                   "manual_after": lambda: _MANUAL_RELOGIN_AFTER})

    def _phone_actions(self):
        return {
            "list_activities": lambda **kw: self.list_activities(**kw),
            "check": lambda **kw: self.check(**kw),
            "start_plan": lambda **kw: self.start_plan(**kw),
            "start_request_state": lambda **kw: self.start_request_state(**kw),
            "cancel_start_request": lambda **kw: self.cancel_start_request(**kw),
            "stop_plan": lambda **kw: self.stop_plan(**kw),
            "cancel_task": lambda **kw: self.cancel_task(**kw),
            "save_retry_policy": lambda retry_policy=None: self.save_prefs(prefs={"retry_policy": retry_policy or {}}),
            "show_window": lambda **kw: self.show_window(**kw),
            "phone_relogin_begin": lambda **kw: self.phone_relogin_begin(**kw),
            "phone_relogin_submit": lambda **kw: self.phone_relogin_submit(**kw),
            "phone_relogin_cancel": lambda **kw: self.phone_relogin_cancel(**kw),
        }

    def _make_phone_controller(self):
        return _phone_service.PhoneAccessController(
            lock=self._phone_access_lock, coordination=self._coord,
            coordination_lock=self._lock, service=lambda: self._phone,
            ports={
                "tunnel": lambda: self._cloudflare,
                "status_snapshot": lambda: self._cloudflare_status_snapshot(),
                "reconcile": lambda: self._reconcile_cloudflare_lifecycle(),
                "stop_locked": lambda: self._stop_phone_access(),
                "start_locked": lambda channel: self._start_phone_access(channel),
                "start": lambda channel: self.start_phone_access(channel),
                "restore": lambda: self.restore_phone_access(),
                "remember": lambda channel: self._remember_phone_channel(channel),
                "forget": lambda: self._forget_phone_autostart(),
                "log": lambda message: phone_log(message),
                "emit": lambda kind, payload: self._emit(kind, payload),
                "load_prefs": lambda: load_prefs(),
                "save_phone_prefs": lambda block: update_prefs({_PHONE_PREF_NAMESPACE: block}),
                "phone_prefs": lambda prefs: _phone_access_prefs(prefs),
                "feature_state": lambda prefs: _advanced_features.feature_state(
                    prefs, root=DATA_DIR, frozen=bool(getattr(sys, "frozen", False))).get(
                        _advanced_features.PHONE_CONTROL, {}),
                "feature_ready": lambda prefs: _advanced_features.feature_ready(
                    prefs, _advanced_features.PHONE_CONTROL, root=DATA_DIR),
                "advanced": lambda: self.advanced_features_state(),
                "qr": lambda address: _phone_qr_data(address),
                "tailscale": lambda: _tunnel_manager.tailscale_endpoint(),
                "resolve_tunnel": lambda: _tunnel_manager.resolve_cloudflared(
                    resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR),
                "cancel_relogin": lambda: self._relay.cancel(origin="phone"),
                "stop_tunnel": lambda: self._stop_cloudflare_checked(),
                "component_auto_update": lambda window: self.schedule_component_auto_update(window),
                "activities": lambda: self._activity_list.snapshot_locked(),
                "plan": lambda: self._plan,
                "last_plan": lambda: self._last_plan,
                "busy": lambda: self._is_busy_locked(),
                "list_error": lambda: self._pc_list_error,
                "plan_source": lambda plan_id: self._plan_source_of(plan_id),
                "login_state": lambda: login_state(self._clock),
                "last_check": lambda: self._last_check,
                "last_check_fields": lambda value: _last_check_fields(value),
                "relogin_state": lambda: self._silent_relogin_state(),
                "clock_payload": lambda: self._clock_payload(),
                "retry_options": lambda: _retry_options_payload(),
                "terms": lambda prefs: terms_state(prefs),
                "terms_gate": lambda: self._terms_gate(),
                "relogin_setup": lambda: self._phone_relogin_setup(),
                "relay_view": lambda: self._phone_relay_view(),
                "credentials_saved": lambda: _credential_store.has_credentials(CREDENTIAL_FILE),
                "stored_username": lambda: _credential_store.stored_username(CREDENTIAL_FILE),
                "mask_account": lambda account: _login_rules.mask_account(account),
                "ocr_ready": lambda: self._relogin_ocr_ready(),
                "credentials_bad": lambda: _credential_store.is_bad(CREDENTIAL_FILE),
                "school_epoch": school_epoch,
            })

    def _stop_phone_for_component_locked(self):
        result = self._stop_phone_access()
        self._cloudflare_exit_notice = None
        return result

    def _component_login_ports(self):
        return {"has_credentials": lambda: _credential_store.has_credentials(CREDENTIAL_FILE),
                "username": lambda: _credential_store.stored_username(CREDENTIAL_FILE),
                "available": lambda: _credential_store_available(),
                "ocr_ready": lambda prefs: _advanced_features.feature_ready(
                    prefs, _advanced_features.RELOGIN_OCR, root=DATA_DIR),
                "automatic": lambda: self._auto_relogin.snapshot(),
                "staged": lambda: self._relay.has_staged(),
                "staged_hint": lambda: self._relay.staged_hint(),
                "last_origin": lambda: self._last_login_origin,
                "is_bad": lambda: _credential_store.is_bad(CREDENTIAL_FILE),
                "cancel_auto": lambda: self._relay.cancel(origin="auto"),
                "clear_staged": lambda: self._relay.clear_staged()}

    def _make_component_actions(self):
        return _component_actions.ComponentActions(
            allowed=lambda key: _advanced_features.allowed_feature(key),
            phone_key=_advanced_features.PHONE_CONTROL,
            inspect_executable=lambda path: _component_packages.inspect_cloudflared(path),
            inspect_archive=lambda path, key: _component_packages.inspect_archive(path, key),
            selected_dir=lambda key: _component_packages.selected_install_dir(key, root=DATA_DIR),
            package_error=_component_packages.PackageError,
            open_directory=lambda path: os.startfile(path),
            credential_lock=self._credential_lock, coordination=self._coord,
            coordination_lock=self._lock,
            load_prefs=lambda: load_prefs(),
            feature_state=lambda prefs: _advanced_features.feature_state(
                prefs, root=DATA_DIR, frozen=bool(getattr(sys, "frozen", False))),
            save_prefs=lambda values: update_prefs(values),
            ocr_key=_advanced_features.RELOGIN_OCR,
            reset_login=lambda: self._auto_relogin.reset(),
            window=lambda: self._window,
            select_file=lambda types: self._window.create_file_dialog(
                webview.FileDialog.OPEN, allow_multiple=False, file_types=types),
            phone_lock=self._phone_access_lock,
            service_for=lambda key: self._component_service_for(key),
            frozen=lambda: bool(getattr(sys, "frozen", False)),
            busy=lambda: self._is_busy_locked(), finished=lambda: self._component_finished(),
            emit=lambda kind, value: self._emit(kind, value), title=_component_title,
            phone={"status": lambda: self._cloudflare_status_snapshot(),
                   "tailscale": lambda: _tunnel_manager.tailscale_endpoint(),
                   "executable": lambda: self._cloudflare.executable,
                   "refresh_executable": lambda: setattr(self._cloudflare, "executable",
                       _tunnel_manager.resolve_cloudflared(resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)),
                   "stop_tunnel": lambda: self._stop_cloudflare_checked(),
                   "shutdown": lambda: self._phone.shutdown(preserve_devices=True),
                   "clear_channel": lambda: setattr(self, "_phone_channel", ""),
                   "running": lambda: self._phone.is_running(),
                   "stop_locked": lambda: self._stop_phone_for_component_locked(),
                   "preferences": lambda prefs: _phone_access_prefs(prefs)},
            login=self._component_login_ports(),
            component={"install": lambda *args, **kwargs: _component_packages.install(*args, **kwargs),
                       "phone_service": lambda: self._component_service,
                       "ocr_service": lambda: self._ocr_component_service,
                       "commit": lambda *args, **kwargs: _component_packages.commit_artifact_group(*args, **kwargs),
                       "inspect": lambda key, path: self.inspect_advanced_component(key, path),
                       "install_selected": lambda key, path: self._install_selected_feature(key, path),
                       "install_cloudflared": lambda path: _component_packages.install_cloudflared(path, root=DATA_DIR),
                       "install_feature": lambda key, frozen, archive: _advanced_features.install_feature(
                           key, frozen=frozen, root=DATA_DIR, archive=archive),
                       "frozen_feature_state": lambda prefs: _advanced_features.feature_state(
                           prefs, root=DATA_DIR, frozen=True),
                       "remove": lambda key: _component_packages.remove(key, root=DATA_DIR)},
            failure_reasons=_DOWNLOAD_FAIL_REASONS, log=lambda text: phone_log(text),
            demo=lambda: DEMO, auto_update=lambda **kwargs: auto_update_outdated_components(**kwargs),
            download=lambda key: self.download_advanced_feature(key),
            wait_idle=lambda key: self._wait_component_settled(key))

    def __init__(self, clock=None) -> None:
        # 协调对象（第一层）：唯一那把锁、关闭屏障、在途槽位与四张进程登记表
        # 都由它持有；_lock 只是同一对象的本地别名，旧字段名见下方 property。
        self._coord = _coordination.Coordinator(plan_state=self._published_plan_state)
        self._lock = self._coord.lock
        self._login_recovery = self._make_login_recovery()
        self._activity_list = self._make_activity_list()
        self._signup_cancellation = self._make_signup_cancellation()
        self._plan_manager = self._make_plan_manager()
        self._worker_service = self._make_worker_service()
        self._desktop_lifecycle = self._make_desktop_lifecycle()
        # 独立北京时间（决策 012）：生产 main 注入 BusinessClock；
        # 未注入时显式不可用，绝不回退本机时间。测试必须显式注入 Fake。
        self._clock_service = self._make_clock_service(clock)
        self._relay_proc_tree = None
        # 窗口对象由 main() 在 create_window 之后经 _window 代理赋进来
        self._desktop_window = self._make_desktop_window()
        self._activities: dict[str, dict] = {}
        # EX05/BE2：电脑侧最近一次拉活动列表失败（安全原因短语 + 北京 HH:MM）。
        # 只进手机快照（_phone_raw_state），不写日志；成功刷新即清空（None）。
        # R-P3-4：另记最后一次成功刷新的时刻——pc_list_error.at 优先用它，
        # 因为文案说的是「手机现在这份列表」的更新时刻，不是失败时刻
        self._pc_list_error: dict | None = None
        self._pc_list_ok_at: str = ""
        self._credential_lock = threading.Lock()
        self._phone_access_lock = threading.Lock()
        self._component_actions = self._make_component_actions()
        # 去重期间又被要求刷新的标记：本轮收尾时补查一次，重登成功后的刷新
        # 不能被「已在检查」静默丢掉（只补一次，不排循环）
        self._check_again = False
        # 在途请求 ID：去重跳过时界面才能对上账（R11）
        self._check_request_id = ""
        self._list_request_id = ""
        self._check_last = {"request_id": "", "payload": None}
        self._list_last = {"request_id": "", "payload": None}
        # 最近一次 check 的四态结论：start_plan 的放行/拒绝只信它
        self._last_check: dict = {}
        # 最近一次自动登录发起时刻（单调钟）：成功/失败落盘日志时算整轮耗时
        self._auto_relogin_started_at = None
        # 更新检查独立于登录/报名，只由帮助按钮触发；页面重载复用内存中的在途请求。
        # 状态与单飞槽位在 application.desktop.update_service.UpdateService：_updating 表示
        # 「任一更新动作在途」（检查或下载），_update_installer 是检查阶段选好的安装器
        # 资产（URL/大小/哈希），下载只信它、不收界面传来的地址；_update_installer_path
        # 是校验通过后的本地产物。这里只留转发与端口注入；请求号格式只在服务里检查，Api 不再重复。
        self._updates = _update_service.UpdateService(
            emit=lambda kind, payload: self._emit(kind, payload),
            is_closing=self._update_is_closing)
        # 手机受限访问（默认关闭）：配对/会话只活在内存里，事件走有界缓冲。
        # 这里不建 socket——只有显式 start_phone_access 才监听。
        self._phone = _phone_service.PhoneAccessService(
            actions=self._phone_actions(), now=self._clock_now, state_of=self._phone_raw_state,
            device_store=_phone_session_store.PhoneSessionStore(DEVICE_FILE),
            log=phone_log,
            server_factory=lambda host, port, svc, public_host="", public_scheme="http": _phone_http.PhoneHttpServer(
                host, port, svc, public_host=public_host, public_scheme=public_scheme,
                log=phone_log))
        self._phone_controller = self._make_phone_controller()
        self._phone_channel = ""
        # 组件包下载：手机控制、验证码识别各一条事务。只有用户点「下载并安装」才动网络；
        # 失败不影响已有组件
        self._component_service = _advanced_component.AdvancedComponentService(
            feature=_advanced_features.PHONE_CONTROL,
            root=DATA_DIR,
            download=updater.download_installer,
            asset_resolver=self._resolve_component_asset,
            install=self._install_downloaded_component,
            inspect_artifact=_component_packages.inspect_artifact,
            commit_artifact_group=self._commit_downloaded_component_group,
            version=_component_packages.version,
            inspect=_component_packages.inspect_archive,
            status=_component_packages.feature_status,
            remover=_component_packages.remove,
            find_cached_artifact=_component_packages.find_cached_artifact,
            cache_artifact=_component_packages.cache_artifact,
            artifacts=_component_packages.ARTIFACTS,
            cloudflared_version=_component_packages.CLOUDFLARED_VERSION,
            on_installed=self._component_installed,
            on_finished=lambda: self._component_finished(_advanced_features.PHONE_CONTROL),
            log=phone_log)
        self._ocr_component_service = _advanced_component.AdvancedComponentService(
            feature=_advanced_features.RELOGIN_OCR,
            root=DATA_DIR,
            download=updater.download_installer,
            asset_resolver=lambda version: self._resolve_component_asset(
                version, _advanced_features.RELOGIN_OCR),
            install=self._install_downloaded_ocr,
            inspect_artifact=_component_packages.inspect_artifact,
            commit_artifact_group=self._commit_downloaded_ocr_group,
            version=_component_packages.version,
            inspect=_component_packages.inspect_archive,
            status=_component_packages.feature_status,
            remover=_component_packages.remove,
            find_cached_artifact=_component_packages.find_cached_artifact,
            cache_artifact=_component_packages.cache_artifact,
            artifacts=_component_packages.ARTIFACTS,
            cloudflared_version=_component_packages.CLOUDFLARED_VERSION,
            on_installed=self._ocr_component_installed,
            on_finished=lambda: self._component_finished(_advanced_features.RELOGIN_OCR),
            log=phone_log)
        # 上一次登录真实成功后由谁完成（auto_ocr / phone_manual）：只用于说明文案
        self._last_login_origin = ""
        # 登录失效推飞书：本次运行里校验过有效，之后变成失效才推；同一次失效只推一次
        self._login_seen_valid = False
        self._expiry_pushed = False
        # 同一段失效只落一次 login_expired_detected：检查每 60 秒一轮，不重复刷日志
        self._login_expired_logged = False
        self._cloudflare = _tunnel_manager.CloudflareTunnel(
            _tunnel_manager.resolve_cloudflared(resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR),
            popen=_tunnel_manager.spawn_cloudflared,
            # 每次真正拉起隧道前再核一遍组件：缓存路径可能已被替换或删除
            verify=lambda path: _tunnel_manager.verify_managed_cloudflared(path, root=DATA_DIR),
            usage=lambda path: _component_packages.cloudflared_usage(path, root=DATA_DIR))
        # 隧道异常退出只报一次 exited，之后 status() 读到的就是 stopped：
        # 退出提示必须自己存住，否则同一次状态组装里的第二次读取会把它降级成「可用」。
        # None 表示「没有未收起的退出提示」，用户手动 stop 或成功 start 后清空。
        self._cloudflare_exit_notice: dict | None = None
        # Cloudflare 拉起隧道是一段有网络等待的同步过程：期间再点一次「开启」，
        # 必须明确回「正在启动」，而不是排队后又叠一条隧道。
        self._cloudflare_starting = False
        # 手机重登中继：凭据只在进程内存，singleflight，成功才建时钟锚点
        self._relogin_entry = self._make_relogin_entry()
        self._relay = _login_relay_service.LoginRelayService(
            spawn=self._spawn_relay_worker, now=time.monotonic,
            emit=self._emit, log=self._log_event,
            on_success=self._anchor_login_success,
            on_finish=self._relay_finished,
            classify_captcha=self._classify_captcha, manual_after=_MANUAL_RELOGIN_AFTER)
        # 调度器的端口写成 lambda：它读的是 Api 上那几个旧名字，替身改哪个名字都立刻生效
        self._auto_relogin = AutoReloginMonitor(
            now=time.monotonic, check=self.check,
            start=lambda: self._begin_auto_relogin(),
            eligible=lambda: self._auto_relogin_eligible(),
            state=lambda: self._relay.state(),
            paused=lambda: self._auto_relogin_paused(),
            log=lambda *args, **kwargs: self._log_event(*args, **kwargs),
            ready=lambda: self._silent_relogin_ready(),
            on_change=lambda view: self._emit("login_auto", view))
        if not DEMO:
            self._auto_relogin.start()

    # ---------- 协调对象字段的兼容代理 ----------
    # 忙碌状态、进程登记表与关停 Event 已归 application.coordination.Coordinator；
    # 旧字段名的显式 property + setter 由 CoordinatorFields 继承进来（含整表替换
    # `api._plan_procs = {...}`），动作代码与夹具一行不用改。

    # ---------- 独立北京时间 ----------
    def _clock_now(self) -> float:
        return self._clock_service.now()

    def _clock_ready(self) -> bool:
        return self._clock_service.ready()

    def _wait_for_list_clock(self) -> float:
        return self._clock_service.wait_for_list()

    def _clock_payload(self) -> dict:
        return self._clock_service.payload()

    def clock_snapshot(self) -> dict:
        return self._clock_service.snapshot()

    def sync_clock(self) -> dict:
        return self._clock_service.sync()

    def _start_clock_monitor(self) -> None:
        return self._clock_service.start_monitor()

    # ---------- 事件推送 ----------
    def _emit(self, kind: str, payload) -> None:
        # check/activities 统一带上本轮请求 ID：界面按 ID 丢弃迟到的旧轮事件，
        # 不靠「最后一次谁先到」猜（R11）
        if isinstance(payload, dict) and "request_id" not in payload:
            if kind == "check":
                payload = dict(payload, request_id=self._check_request_id)
            elif kind == "activities":
                payload = dict(payload, request_id=self._list_request_id)
        # 手机事件缓冲：窗口为空也可发布（有界 400 条、脱敏、独立锁、锁外投递）；
        # 只入内存缓冲，绝不回调任何 HTTP 客户端，也不在这里碰 Api/协调器锁
        phone_payload = self._phone_relay_view() if kind == "phone_relogin" else payload
        self._phone.record_event(kind, phone_payload)
        if not self._window:
            return
        # 终态快照留档：去重跳过时若原操作已经结束，直接把结果交回去，
        # 不让界面等一个永远不会再发的旧 ID 事件（C06）
        if isinstance(payload, dict) and kind == "check":
            self._check_last = {"request_id": str(payload.get("request_id") or ""),
                                "payload": dict(payload)}
        elif isinstance(payload, dict) and kind == "activities":
            self._list_last = {"request_id": str(payload.get("request_id") or ""),
                               "payload": dict(payload)}
        js = "window.onBackend && window.onBackend.%s(%s)" % (
            kind, json.dumps(payload, ensure_ascii=False))
        try:
            self._window.evaluate_js(js)
        except Exception:
            pass

    # ---------- 条款授权（学校动作的最终防线） ----------
    def _terms_gate(self, request_id: str = "") -> "dict | None":
        """学校联网动作的统一条款门禁；返回 None 才放行。

        界面按钮只是第一道：脚本、快捷键、事件重放都能绕过按钮，所以真实
        判定放在后端。只读 ui.json 的 terms_version / terms_accepted_at，
        不读登录文件、不写运行日志；演示模式（DEMO）完全离线，不受此限。

        未同意、版本不匹配、偏好读不出（load_prefs 兜底返回空）都按
        **未授权**处理：不启动线程、worker、学校请求或计划协调器。
        """
        if DEMO:
            return None
        state = terms_state(load_prefs())
        if state["accepted_version"] == TERMS_VERSION:
            return None
        payload = dict(terms_unknown_payload(), terms=state)
        if request_id:
            # 带上原 request_id：界面按 ID 对账，不把拒绝当成新一轮在途
            payload["request_id"] = request_id
        return payload

    # ---------- 读数据 ----------
    def bootstrap(self) -> dict:
        prefs = load_prefs()
        if DEMO:
            # 演示模式不读 session/storage_state，也不碰真实生命周期文件（C07）
            login_info = {"hours_left": None, "session_present": None,
                          "estimated_expires_at": None, "saved_at": None,
                          "last_check_at": None, "last_check_state": "unknown",
                          "demo": True}
            lifecycle_info = {"close_quality": "unknown", "closed_for_s": None,
                              "last_heartbeat_at": None, "demo": True}
        else:
            login_info = login_state(self._clock)
            # 上次校验时刻/结论：界面据此显示「上次校验」，不再倒推剩余时间（S3）
            with self._lock:
                last_check = dict(self._last_check)
            login_info.update(_last_check_fields(last_check))
            login_info.update(self._auto_relogin.view(expired=last_check.get("result") == "expired"))
            lifecycle_info = get_lifecycle().snapshot()
        payload = {
            "version": APP_VERSION,
            "prefs": prefs,
            # 条款同意快照：界面据此决定是否弹条款、是否放行学校网络动作；同意状态本身只存 ui.json（terms_version / terms_accepted_at）
            "terms": terms_state(prefs),
            "business_clock": self._clock_payload(),
            "help": self.help(),
            "advanced_features": self.advanced_features_state(),
            "login": login_info,
            # 生命周期元数据（上一周期关闭时长/质量 + 登录估算）：只作提示，
            # 不参与任何放行/拦截；F5 重载重复调用拿到的是同一份进程级快照
            "lifecycle": lifecycle_info,
            # MG01/MG02（BE3，原型 Main:2146/2147）：本次进程启动时旧数据迁移的
            # 结果，{moved, login_failed} 或 None（没发生迁移）。只给桌面横幅与
            # 运行记录，不进手机快照。
            "migration": migration_record(),
            # demo 标记：界面据此放行演示计划（真实模式仍要求登录校验 valid）
            "demo": DEMO,
            "feishu_webhook": _feishu_webhook(),   # 设置里回显；没配或不是 https 为空串
            # 三种重试模式的权威选项与默认值：桌面/手机共用这一份口径
            "retry_options": _retry_options_payload(),
        }
        # busy 与计划快照必须在同一「判定点」取：先取协调器快照（锁外），
        # 再回 Api 锁内确认这份快照仍属于当前计划并重新计算 busy。这样既不会
        # 出现「busy=true 但 plan 是上一份终态快照」，也不在持 Api 锁时取
        # 协调器锁（P2-1 锁序）。
        snapshot, busy = self._bootstrap_plan_snapshot()
        with self._lock:
            payload["busy"] = busy
            generation = self._plan_generation
        # 更新状态读服务自己那把锁：四个键与值不变，只是不再由 Api 的锁护着。
        # 它与 busy 本来就没有规则上的联动（busy 来自计划快照，update_check 来自更新链路），
        # 搬家前后都不存在「两个字段必须同一瞬间」的读法。
        payload["update_check"] = self._updates.snapshot()
        if snapshot is not None:
            # 页面重载会丢掉 plan/task 事件：把计划快照一并交给 bootstrap，界面
            # 才能恢复任务列表和「停止」按钮；复制一份再补归属，不改写共享快照。
            boot_plan = dict(snapshot)
            boot_plan["plan_generation"] = generation
            boot_plan.setdefault("source", self._plan_source_of(boot_plan.get("plan_id")))
            boot_plan.setdefault("request_id",
                                 self._find_request_id(boot_plan.get("plan_id")))
            payload["plan"] = boot_plan
        return payload

    def _find_request_id(self, plan_id) -> str:
        """按 plan_id 反查开始请求 ID（只读，不加锁时调用者需保证一致性）。"""
        target = str(plan_id or "")
        if not target:
            return ""
        with self._lock:
            return next((key for key, value in self._start_requests.items()
                         if value.get("plan_id") == target), "")

    def _bootstrap_plan_snapshot(self) -> tuple["dict | None", bool]:
        """锁外取计划快照，再锁内确认归属；返回 (快照, busy)。

        取快照期间计划可能被替换或结束：重读最多三次，最终以 Api 锁内的
        当前计划/终态快照为准，不返回已过期计划。
        """
        for _ in range(3):
            with self._lock:
                plan = self._plan
            if plan is None:
                with self._lock:
                    return self._last_plan, self._is_busy_locked()
            try:
                snapshot = plan.snapshot()
            except Exception:
                snapshot = None
            with self._lock:
                # 只有「这份快照仍属于当前计划」时才连 busy 一起返回：
                # 否则重新读，避免把旧计划的运行态配上新计划的忙态
                if self._plan is plan:
                    return snapshot, self._is_busy_locked()
        with self._lock:
            return self._last_plan, self._is_busy_locked()

    def help(self) -> dict:
        return {
            "title": "使用帮助",
            "subtitle": "三步完成一次报名",
            # 版本与最新版本入口：界面据此显示「版本 1.1.0」和 GitHub 外链按钮
            # （APP_VERSION 恒来自 read_version()，这里只是示例注释，不写死实现）
            "version": APP_VERSION,
            "latest_url": RELEASES_LATEST_URL,
            # 三步只讲「怎么操作」：选中不等于开始，开始按钮必须点，结果逐场看。
            # 与 DEFAULT_HELP 逐字一致（test_ui_contract 比对两端），照抄原型 :745。
            "steps": [
                {"no": 1, "title": "确认登录",
                 "text": "顶部显示“已登录”就行；提示失效再重新登录。"},
                {"no": 2, "title": "选活动并开始",
                 "text": "勾选活动、核对右侧计划，再点“开始报名计划”。勾选不会自动开始。"},
                {"no": 3, "title": "看结果",
                 "text": "每场单独出结果；看到“待核对”，到学校活动页确认。"},
            ],
        }

    # ---------- 可选高级功能与本机凭据 ------------------------------------
    def _resolve_component_asset(self, version: str,
                                 feature: str = _advanced_features.PHONE_CONTROL) -> dict:
        """解析 Release 里的组件资产（网络只在用户点下载时用）。

        `application` 层不允许直接 import `update_check`（分层契约），所以这层
        网络与错误分类留在 composition root：拿不到、清单不对、限速必须分开说。
        """
        try:
            _update_check.parse_version(version)
            # G1：按标签拼清单直链，不请求 api.github.com（未登录接口按出口 IP 限流）
            raw_manifest = _update_check._fetch_bytes(
                _update_check.tag_manifest_url(version), _update_check.MAX_MANIFEST_BYTES,
                "TianSoftActivityPreRegistration-component-manifest")
            payload = _update_check.payload_from_manifest(raw_manifest, version)
            split_verdict = _update_check.resolve_component_assets(
                payload, version, raw_manifest, feature)
            verdict = _update_check.resolve_component_asset(
                payload, version, raw_manifest, feature)
            if split_verdict.get("state") == "available":
                return {"ok": True, "assets": split_verdict["assets"],
                        "asset": verdict.get("asset") if verdict.get("state") == "available" else None}
        except HTTPError as exc:
            if exc.code in (403, 429):
                return {"ok": False, "error": "rate_limited",
                        "text": "GitHub 暂时限制了查询次数，过一会再试，或到发布页手动下载。"}
            if exc.code == 404:
                return {"ok": False, "error": "no_component",
                        "text": "这个版本没有发布%s组件包。" % _component_title(feature)}
            return {"ok": False, "error": "http_error",
                    "text": "GitHub 暂时无法响应，请稍后重试。"}
        except (TimeoutError, socket.timeout):
            return {"ok": False, "error": "timeout", "text": "查询组件包信息超时，请重试。"}
        except URLError as exc:
            code = ("timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout))
                    else "network_error")
            return {"ok": False, "error": code, "text": "暂时连不上 GitHub，请检查网络后重试。"}
        except (ValueError, UnicodeError, TypeError):
            return {"ok": False, "error": "manifest_invalid",
                    "text": "组件包清单不可用，已停止下载。"}
        except OSError:
            return {"ok": False, "error": "network_error",
                    "text": "暂时连不上 GitHub，请检查网络后重试。"}
        if verdict.get("state") != "available":
            return {"ok": False,
                    "error": str(verdict.get("error_code") or verdict.get("state") or "no_component"),
                    "text": str(verdict.get("text") or "组件包不可用。")}
        return {"ok": True, "asset": verdict["asset"]}

    def _stop_cloudflare_checked(self) -> bool:
        """停 Cloudflare 隧道并看返回值：没停下写一条运行记录并返回 False（H1）。

        tunnel_manager.stop() 在进程没停下时返回 ok=False（tunnel_stop_failed）；此前四处调用
        都不看，界面照写「手机访问已关闭」，隧道其实还在。只有显式 ok=False 才算失败。
        """
        result = self._cloudflare.stop()
        if isinstance(result, dict) and result.get("ok") is False:
            self._emit("log", "Cloudflare 隧道没能关闭，请重试")
            return False
        return True

    def _install_downloaded_component(self, archive, key, *, root=None):
        return self._component_actions.replace_downloaded(key, archive, root=root)

    def _commit_downloaded_component_group(self, feature, artifacts, *, root=None):
        return self._component_actions.replace_downloaded(feature, artifacts, root=root, group=True)

    def _component_finished(self, feature: str='') -> None:
        return self._component_actions.finished(feature)

    def _component_installed(self, version: str) -> None:
        return self._component_actions.installed(_advanced_features.PHONE_CONTROL, version)

    def _install_downloaded_ocr(self, archive, key, *, root=None):
        return self._component_actions.replace_downloaded_ocr(key, archive, root=root)

    def _commit_downloaded_ocr_group(self, feature, artifacts, *, root=None):
        return self._component_actions.replace_downloaded_ocr(feature, artifacts, root=root, group=True)

    def _ocr_component_installed(self, version: str) -> None:
        return self._component_actions.installed(_advanced_features.RELOGIN_OCR, version)

    def _component_service_for(self, key: str):
        return self._component_actions.service_for(key)

    def download_advanced_feature(self, key: str='') -> dict:
        return self._component_actions.download(key)

    def cancel_advanced_feature_download(self, key: str='') -> dict:
        return self._component_actions.cancel_download(key)

    def enable_advanced_feature(self, key: str='') -> dict:
        return self._component_actions.enable(key)

    def advanced_component_location(self, key: str='') -> dict:
        return self._component_actions.location(key)

    def open_advanced_component_dir(self, key: str='') -> dict:
        return self._component_actions.open_location(key)

    def advanced_features_state(self) -> dict:
        return self._component_actions.snapshot()

    def inspect_advanced_component(self, key: str='', path: str='') -> dict:
        return self._component_actions.inspect(key, path)

    def pick_advanced_component(self, key: str='') -> dict:
        return self._component_actions.pick(key)

    def install_advanced_feature(self, key: str='', path: str='') -> dict:
        return self._component_actions.install(key, path)

    def _install_selected_feature(self, key: str, chosen: str='') -> dict:
        return self._component_actions.install_selected(key, chosen)

    def remove_advanced_feature(self, key: str='') -> dict:
        return self._component_actions.remove(key)

    # ---------- 重登入口与自动重登门（实现在 application.login.relogin_entry） ----------
    # 这些名字是 AutoReloginMonitor、手机动作表与谁挡谁矩阵的接线点，这里只保留
    # 三行以内的转发；状态归属与逐条判断见该服务与 domain/login/login_rules 的纯函数。
    def save_relogin_credentials(self, username: str = "", password: str = "") -> dict:
        return self._relogin_entry.save_relogin_credentials(username, password)

    def clear_relogin_credentials(self) -> dict:
        return self._relogin_entry.clear_relogin_credentials()

    def _silent_relogin_ready(self) -> tuple[bool, str]:
        return self._relogin_entry._silent_relogin_ready()

    def _silent_relogin_state(self) -> tuple[bool, str]:
        return self._relogin_entry._silent_relogin_state()

    def _auto_relogin_eligible(self) -> bool:
        return self._relogin_entry._auto_relogin_eligible()

    def _once_credentials_staged(self) -> bool:
        return self._relogin_entry._once_credentials_staged()

    def _auto_relogin_paused(self) -> bool:
        return self._relogin_entry._auto_relogin_paused()

    def _request_auto_relogin(self) -> None:
        return self._relogin_entry._request_auto_relogin()

    def _relogin_wait_s(self) -> float:
        return self._relogin_entry._relogin_wait_s()

    def _relogin_ocr_ready(self) -> bool:
        return self._relogin_entry._relogin_ocr_ready()

    def _manual_relogin_wanted(self, relay=None) -> bool:
        return self._relogin_entry._manual_relogin_wanted(relay)

    def _phone_relay_view(self) -> dict:
        return self._relogin_entry._phone_relay_view()

    def _log_event(self, event: str, level: str = "INFO", **fields) -> None:
        """自动登录的关键动作落盘到 grab.log（行格式与 worker 同源，见 domain.worker.log_events）。

        界面进程不 import grab（冻结主程序里没有它），所以这里自己追加一行；
        字段先过黑名单（不带账号、密码、验证码）。追加前要先拿 grab.log.lock：
        worker 的轮转也在同一把锁里，否则轮转会把刚写的行挪走。写失败至少打到
        stderr，绝不影响登录流程本身。演示模式完全离线，不写。
        """
        if DEMO:
            return
        try:
            stamp = school_time_text(now_fn=self._clock_now)
        except Exception:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "%s %s" % (stamp, _log_events.format_event_line(
            event, "auto_relogin", level=level, fields=fields))
        lock_handle = None
        locked = False
        try:
            ensure_data_dir()
            lock_handle = open(LOG_LOCK_FILE, "a+b")
            _acquire_prefs_file_lock(lock_handle, 2.0)
            locked = True
            with open(LOG_FILE, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception as exc:  # noqa: BLE001 - 日志写不进去不能拖垮登录
            if sys.stderr is not None:
                try:
                    print("[log] 写日志文件失败（%s）：%s" % (type(exc).__name__, line),
                          file=sys.stderr, flush=True)
                except Exception:
                    pass
        finally:
            if locked:
                _release_prefs_file_lock(lock_handle)
            if lock_handle is not None:
                lock_handle.close()

    def _begin_auto_relogin(self) -> dict:
        return self._relogin_entry._begin_auto_relogin()

    def _begin_auto_relogin_once(self) -> dict:
        return self._relogin_entry._begin_auto_relogin_once()

    def _classify_captcha(self, image: str) -> str:
        prefs = load_prefs()
        if not _advanced_features.feature_ready(prefs, _advanced_features.RELOGIN_OCR, root=DATA_DIR):
            return ""
        return _advanced_features.classify_captcha(image, root=DATA_DIR)

    def front_ready(self) -> dict:
        # 仅排障：前端 boot 完成时打一声招呼，确认桥接真的通了
        self._trace("front_ready")
        return {"ok": True}

    # ---------- 更新（状态与用例在 application.desktop.update_service） ----------
    def _update_is_closing(self) -> bool:
        """读一个布尔值在 CPython 里是原子的；这里不拿 Api 锁，是为了不让「服务锁 → Api 锁」嵌套。"""
        return bool(self._closing)

    def check_update(self, request_id: str) -> dict:
        """只登记轻量后台查询，不在桥接线程等待网络，也不改变报名门禁。"""
        return self._updates.start_check(
            request_id, thread_factory=threading.Thread, job=self._do_check_update,
            cleanup_staging=updater.cleanup_staging,
            update_version_paths=update_version_paths, current_version=APP_VERSION)

    def _do_check_update(self, request_id: str) -> None:
        # 线程目标：fetch 端口在这里取，测试按 app.check_latest_release 替换的补丁才生效
        _update_service.run_check(self._updates, request_id, fetch=check_latest_release,
                                  current_version=APP_VERSION,
                                  latest_url=RELEASES_LATEST_URL, switch_available=version_switch_available)

    def update_download(self, request_id: str) -> dict:
        """用户确认后启动安装器下载：单飞后台流式下载并校验，事件回推进度与结论。"""
        return self._updates.start_download(request_id, thread_factory=threading.Thread,
                                            job=self._do_update_download)

    def _do_update_download(self, request_id: str, installer: dict) -> None:
        # 线程目标：版本路径与下载/落盘端口都在这里取（updater 模块属性即替身缝）
        self._updates.download_job(
            request_id, installer, version_switch_available=version_switch_available,
            update_version_paths=update_version_paths, stage_update=updater.stage_update,
            download_payload=updater.download_payload,
            download_installer=updater.download_installer,
            cleanup_download=updater.cleanup_download,
            current_version=APP_VERSION, latest_url=RELEASES_LATEST_URL)

    def update_cancel(self) -> dict:
        """用户取消下载：只置取消标记，下载线程在下一块之间停下并清理半成品。"""
        return self._updates.cancel()

    def update_launch(self, request_id: str) -> dict:
        """用户确认后启动已校验的安装器；启动前先回推 launching 状态。

        安装器路径：关闭主程序由调用方控制，这里不退出、不自动重启。
        版本目录切换路径：启动器拉起后主程序约 1 秒自己走「退出」关窗，切换才能继续。
        两条路径失败都不改会话和偏好。
        """
        return self._updates.launch(request_id, _update_service.LaunchPorts(
            version_switch_available=version_switch_available,
            update_version_paths=update_version_paths,
            launcher_command=update_launcher_command,
            spawn=subprocess.Popen,
            cwd=str(HERE),
            env_factory=_env,
            creationflags=CREATE_NO_WINDOW,
            parent_pid=os.getpid(),
            defer_close=defer_close_action,
            request_close=lambda: self.request_window_close("exit"),
            launch_installer=updater.launch_installer))

    def check(self, request_id: str='') -> dict:
        return self._login_recovery.check(request_id)

    def list_activities(self, request_id: str='') -> dict:
        return self._activity_list.list_activities(request_id)

    def _do_check(self) -> None:
        return self._login_recovery.do_check()

    def _note_login_conclusion(self, conclusion: str) -> None:
        return self._login_recovery.note_conclusion(conclusion)

    def _push_login_expired(self) -> None:
        """配了飞书机器人才推；推送体在 LoginRecovery——「推不推」的判定也在那里。"""
        return self._login_recovery.push_expired(webhook=_feishu_webhook(),
                                                 emit=self._emit)

    def _do_check_inner(self) -> None:
        return self._login_recovery.do_check_inner()

    def _pc_clock_text(self) -> str:
        return self._activity_list.clock_text()

    def _note_pc_list_error(self, reason: str) -> None:
        return self._activity_list.note_error(reason)

    def _do_list(self) -> None:
        return self._activity_list.do_list()

    # ---------- 取消报名（计划 20261107-conflict-cancel，X1–X4） ----------
    # 取消不可撤回：只收当前列表缓存里 signed 为真的单个 id；联网动作在一次性 worker 里做
    # （grab.py cancel），前置条件由 worker 重核；成败只信 worker 的复查结论。
    # 只在电脑端提供：phone_rules.ACTION_PARAMS 不含 cancel_signup（X1）。
    CANCEL_WORKER_TIMEOUT_S = 90

    # 忙碌原因 → 界面可直接显示的一句话（原型 PhStopAsk 同口径的初稿）
    CANCEL_BUSY_TEXT = {
        "plan_running": "计划在运行，先停下来再取消",
        "refreshing": "正在刷新，等它结束再取消",
        "task_running": "有任务在运行（登录或报名），等它结束再取消",
        "cancelling": "正在取消另一场",
        "closing": "程序正在关闭，已取消本次操作",
    }

    def _cancel_busy_reason_locked(self) -> str:
        """取消能不能开始：返回占用原因，空串表示空闲。调用方持 self._lock。

        判定已归 application.coordination.Coordinator（G2），这里只作旧名转发。
        """
        return self._coord.cancel_busy_reason_locked()

    def _cancel_refusal(self, kind: str, reason: str) -> dict:
        return self._signup_cancellation.refusal(kind, reason)

    def cancel_signup(self, activity_id: str = "") -> dict:
        return self._signup_cancellation.cancel(activity_id)

    def _cancel_signup_run(self, aid: str) -> dict:
        return self._signup_cancellation.run(aid)

    def _after_cancelled(self, aid: str) -> None:
        return self._signup_cancellation.after_cancelled(aid)

    # ---------- 报名结果回写 ----------
    # 学校列表短暂滞后是常态：报名成功后立即刷新仍可能拿到 signed=false。
    # 已确认成功在这段窗口内不被撤销；超过窗口仍为 false 时以学校列表为最终权威
    # （本地不能长期伪造已报名，否则会挡住用户真正需要重报的场次）。
    SIGNED_SYNC_WINDOW_S = 120.0

    def _confirm_signed(self, activity_id: str, status: str) -> bool:
        """worker 终态为 success/already_signed 时原子回写活动缓存。

        unconfirmed/failed/canceled/auth_unavailable 一律不写：未知结果不能被
        猜成成功，也不能因为本地停止就撤销学校已确认的事实。
        """
        aid = str(activity_id or "")
        if not aid or status not in {"success", "already_signed"}:
            return False
        try:
            confirmed_at = float(self._clock_now())
        except Exception:
            # 校时不可用时也保留事实，只是同步窗口改由「无截止」处理（见合并）
            confirmed_at = 0.0
        with self._lock:
            item = self._activities.get(aid)
            if not item:
                return False
            item = dict(item)
            item["signed"] = True
            item["signed_source"] = ("plan_success" if status == "success"
                                     else "plan_already_signed")
            item["signed_confirmed_at"] = confirmed_at
            item["sync_pending"] = False
            self._activities[aid] = item
            return True

    def _merge_list_activities(self, items: list[dict]) -> list[dict]:
        return self._activity_list.merge(items)

    def _do_list_inner(self) -> None:
        return self._activity_list.do_list_inner()

    # ---------- 动作 ----------
    def login(self) -> dict:
        if DEMO:
            # 演示模式不打开学校登录页、不写 session（R20）
            return {"ok": False, "demo": True,
                    "text": "演示模式不联网：这里不会打开学校登录页。"
                            "要看真实登录，请不带 --demo 启动。"}
        with self._lock:
            if self._closing:
                # 不带 error 码：前端不得把关闭取消当成组件问题挂横幅
                return {"ok": False, "text": "程序正在关闭，已取消本次登录"}
            if self._plan and self._plan.published_status() in {"running", "ready"}:
                return {"ok": False, "text": "报名计划正在运行，先停止计划再登录"}
        # 条款门禁：登录要打开学校登录页并写回会话，未获授权不起 worker
        gate = self._terms_gate()
        if gate is not None:
            return gate
        return self._spawn(worker_command("login"), "登录", kind="login")

    def grab(self, activity_id: str, name: str, at: str = "",
             headed: bool = False) -> dict:
        if DEMO:
            # 演示模式绝不起真实 worker：grab 是学校动作，demo 只给离线结论
            # （与计划协调器里的 demo runner 同一口径，不绕过条款门禁）
            return {"ok": False, "demo": True,
                    "text": "演示模式不联网：这里不会真正提交报名。"}
        # 条款门禁：单场报名直接打学校接口，未获授权不起 worker
        gate = self._terms_gate()
        if gate is not None:
            return gate
        args = worker_command("grab", "--activity-id", activity_id, "--name", name)
        if at:
            args += ["--at", at]
        if headed:
            args.append("--headed")
        return self._spawn(args, "等待并抢报名：%s" % name, kind="grab")

    START_KEEP = 32

    # 已完成计划的留档上限：重复终态幂等只看这段窗口，足够覆盖迟到回调
    FINISHED_PLAN_KEEP = 32

    def _prune_finished_plans_locked(self) -> None:
        return self._plan_manager.prune_finished_plans_locked()

    def _protect_start(self, request_id: str) -> bool:
        return self._plan_manager.protect_start(request_id)

    def _remember_start(self, request_id: str, state: str, **extra) -> None:
        return self._plan_manager.remember_start(request_id, state, **extra)

    def _start_replay(self, record: dict, request_id: str) -> dict:
        return self._plan_manager.start_replay(record, request_id)

    def start_request_state(self, request_id: str) -> dict:
        return self._plan_manager.start_request_state(request_id)

    def cancel_start_request(self, request_id: str) -> dict:
        return self._plan_manager.cancel_start_request(request_id)

    def start_plan(self, items: list[dict], headed: bool = False,
                   retry_policy: dict | None = None, request_id: str = "",
                   source: str = "desktop") -> dict:
        return self._plan_manager.start_plan(items, headed, retry_policy, request_id, source)

    def _start_plan_inner(self, items: list[dict], headed: bool,
                          retry_policy: dict | None, request_id: str = "") -> dict:
        return self._plan_manager.start_plan_inner(items, headed, retry_policy, request_id)

    def cancel_task(self, plan_id: str, task_id: str) -> dict:
        with self._lock:
            plan = self._plan
        if not plan or plan.plan_id != str(plan_id):
            return {"ok": False, "text": "计划已经结束"}
        ok = plan.cancel_task(str(task_id))
        return {"ok": ok, "text": "已请求取消这一场" if ok else "这一场已经结束"}

    def stop_plan(self, plan_id: str) -> dict:
        with self._lock:
            plan = self._plan
        if not plan or plan.plan_id != str(plan_id):
            return {"ok": False, "text": "当前没有这个计划"}
        # 幂等：重复停止同一个计划也返回 ok。顺序必须是「先置停协调器，
        # 再杀还活着的 worker」——反过来杀，等待中的批次可能在杀完之后
        # 又被拉起来。树终止不等 Playwright 自然超时，确认后立即生效。
        plan.stop()
        self._terminate_plan_procs()
        return {"ok": True, "text": "已停止计划"}

    def _terminate_plan_procs(self) -> None:
        return self._worker_service.terminate_plan_procs()

    # ---------- 窗口外壳（实现在 application.desktop_window） ----------
    # 签名与方法名是界面契约与 main() 的接线点，这里只保留转发；
    # 窗口、托盘与三个标志的归属见该服务，旧字段名由 DesktopWindowFields 代理。
    def plan_active_for_close(self) -> bool:
        return self._desktop_window.plan_active_for_close()

    def _close_plan_burden(self) -> dict:
        return self._desktop_window._close_plan_burden()

    def ask_window_close(self) -> dict:
        return self._desktop_window.ask_window_close()

    def request_window_close(self, action: str = "") -> dict:
        return self._desktop_window.request_window_close(action)

    def _remember_close_action(self, action: str) -> bool:
        return self._desktop_window._remember_close_action(action)

    def hide_window(self) -> dict:
        return self._desktop_window.hide_window()

    def _notify_window_hidden(self) -> None:
        return self._desktop_window._notify_window_hidden()

    def show_window(self) -> dict:
        return self._desktop_window.show_window()

    def window_visibility(self) -> dict:
        return self._desktop_window.window_visibility()

    def _on_window_minimized(self) -> None:
        return self._desktop_window._on_window_minimized()

    def _on_window_restored(self) -> None:
        return self._desktop_window._on_window_restored()

    def _on_second_open(self) -> None:
        return self._desktop_window._on_second_open()

    def _plan_source_of(self, plan_id) -> str:
        with self._lock:
            return self._plan_sources.get(str(plan_id or ""), "desktop")

    def _notify_plan_done(self, snapshot) -> None:
        return self._desktop_window._notify_plan_done(snapshot)

    def _ensure_tray(self) -> bool:
        return self._desktop_window._ensure_tray()

    def _stop_tray(self) -> None:
        return self._desktop_window._stop_tray()

    def shutdown(self) -> None:
        return self._desktop_lifecycle.shutdown()

    def stop(self) -> dict:
        with self._lock:
            plan = self._plan
        if plan:
            return self.stop_plan(plan.plan_id)
        with self._lock:
            proc = self._proc
            tree = self._proc_tree
        if tree is not None and tree.proc.poll() is None:
            tree.terminate()
            self._emit("log", "已请求停止")
            return {"ok": True}
        if tree is not None:
            # 受管树对应的进程早已退出（例如中继刚收尾）：不再回「已请求停止」。
            # 清掉旧树引用，并顺手收走可能残留的后代（Job 句柄关闭即整树结束）。
            with self._lock:
                if self._proc_tree is tree:
                    self._proc_tree = None
                if self._proc is tree.proc:
                    self._proc = None
                if self._relay_proc_tree is tree:
                    self._relay_proc_tree = None
            tree.terminate()
            tree.close()
            return {"ok": False, "text": "当前没有在跑的任务"}
        if proc and proc.poll() is None:
            _kill_tree(proc)
            self._emit("log", "已请求停止")
            return {"ok": True}
        return {"ok": False, "text": "当前没有在跑的任务"}

    # ---------- 手机受限访问（默认关闭） ----------
    def _phone_raw_state(self) -> dict:
        return self._phone_controller.raw_state()

    def _phone_relogin_setup(self) -> dict:
        return self._phone_controller.relogin_setup()

    def _cloudflare_status_snapshot(self) -> tuple[dict, dict]:
        return self._phone_controller.status_snapshot()

    def _reconcile_cloudflare_lifecycle(self) -> dict:
        return self._phone_controller.reconcile()

    def phone_access_state(self) -> dict:
        return self._phone_controller.snapshot()

    def start_phone_access(self, channel: str='tailscale') -> dict:
        return self._phone_controller.start(channel)

    def _start_phone_access(self, channel: str) -> dict:
        return self._phone_controller.start_locked(channel)

    def _remember_phone_channel(self, channel: str) -> None:
        return self._phone_controller.remember(channel)

    def _forget_phone_autostart(self) -> None:
        return self._phone_controller.forget_autostart()

    def set_phone_access_preferences(self, preferred_channel: str='') -> dict:
        return self._phone_controller.set_preferences(preferred_channel)

    def restore_phone_access(self) -> dict:
        return self._phone_controller.restore()

    def schedule_phone_restore(self, window) -> None:
        return self._phone_controller.schedule_restore(window)

    def schedule_component_auto_update(self, window) -> None:
        return self._component_actions.schedule_auto_update(window)

    def _wait_component_settled(self, key: str, *, timeout: float=1800.0) -> str:
        return self._component_actions.wait_settled(key, timeout=timeout)

    def stop_phone_access(self) -> dict:
        return self._phone_controller.stop()

    def _stop_phone_access(self) -> dict:
        return self._phone_controller.stop_locked()

    # ---------- 手机重登中继（凭据只在进程内存；入口在 application.login.relogin_entry） ----------
    def prepare_phone_relogin(self, username: str = "", password: str = "",
                              save: bool = False) -> dict:
        return self._relogin_entry.prepare_phone_relogin(username, password, save)

    def _commit_pending_save(self) -> None:
        return self._relogin_entry._commit_pending_save()

    def _relogin_late_answer(self) -> "dict | None":
        return self._relogin_entry._relogin_late_answer()

    def _relogin_entry_gate(self) -> "dict | None":
        return self._relogin_entry._relogin_entry_gate()

    def _relogin_manual_case(self) -> str:
        return self._relogin_entry._relogin_manual_case()

    def _begin_typed_relogin(self, username: str, password: str, save: bool,
                             origin: str) -> dict:
        return self._relogin_entry._begin_typed_relogin(username, password, save, origin)

    # ---------- 电脑上的重新登录（与手机共用一场登录流程） ----------
    def relogin_begin(self, username: str = "", password: str = "", save: bool = False) -> dict:
        return self._relogin_entry.relogin_begin(username, password, save)

    def relogin_submit(self, flow_id: str = "", challenge_id: str = "", code: str = "") -> dict:
        """电脑上输的验证码。"""
        return self._relay.submit(flow_id, challenge_id, code, origin="desktop")

    def relogin_cancel(self, flow_id: str = "") -> dict:
        return self._relogin_entry.relogin_cancel(flow_id)

    def relogin_auto_once(self) -> dict:
        return self._relogin_entry.relogin_auto_once()

    def phone_relogin_begin(self, username: str = "", password: str = "",
                            save: bool = False) -> dict:
        return self._relogin_entry.phone_relogin_begin(username, password, save)

    def phone_relogin_submit(self, flow_id: str = "", challenge_id: str = "",
                             code: str = "") -> dict:
        return self._relay.submit(flow_id, challenge_id, code)

    def phone_relogin_cancel(self, flow_id: str = "") -> dict:
        return self._relogin_entry.phone_relogin_cancel(flow_id)

    def _spawn_relay_worker(self, args: list[str]):
        return self._worker_service.spawn_relay(args)

    def _relay_finished(self) -> None:
        return self._login_recovery.relay_finished()

    def open_data(self) -> dict:
        """打开数据目录，并把**真实路径**回给界面。

        只回 {"ok": true} 是不够的：用户最常问的就是「数据到底在哪」，
        窗口一关就又不知道了。路径必须能被看见、能被复制，所以原样回传
        实际解析出来的目录（CAMPUS_DATA_DIR 覆盖过的话也如实反映）。
        """
        path = ensure_data_dir()
        os.startfile(str(path))            # noqa: S606 - Windows 桌面工具
        return {"ok": True, "path": str(path)}

    def open_latest_release(self) -> dict:
        """用户点「GitHub 最新版本」时用系统默认浏览器打开固定的 releases/latest 页。

        只打开常量地址：不收任意 URL、不在 WebView 内替换工具页面、
        启动时也不自动访问 GitHub——版本检查是人的事，不是工具的网络行为。
        """
        try:
            os.startfile(RELEASES_LATEST_URL)   # noqa: S606 - 系统默认浏览器
            return {"ok": True, "url": RELEASES_LATEST_URL}
        except Exception as exc:  # noqa: BLE001 - 打不开也要给界面一个可读结论
            return {"ok": False, "text": "没能打开浏览器（%s）" % type(exc).__name__,
                    "url": RELEASES_LATEST_URL}

    def get_license_text(self) -> dict:
        """全文弹窗「MIT 许可证」页签的随包 LICENSE 原文（UTF-8 读入，原样回传）。

        生产 UI 由 pywebview 直接加载本地 index.html、没有 HTTP 服务，许可证文本
        只能走桥。候选链见 license_candidates：冻结资源根 → 脚本旁 → 仓库根，
        拿第一个存在的；三个位置都没有（残缺包）或读取失败时给人话，让界面
        在页签内就地重试，而不是把异常抛给页面。只读 LICENSE，不碰任何凭据文件。
        """
        for path in license_candidates(RESOURCE_ROOT, HERE):
            try:
                if path.is_file():
                    text = path.read_text(encoding="utf-8")
                    return {"ok": True, "text": text, "path": str(path)}
            except OSError:
                continue  # 换下一个候选；三处都读不到就走统一的人话失败
        return {"ok": False,
                "text": "没有找到随包的 LICENSE 文件（安装目录、程序目录与仓库根都没有）。"
                        "请重新下载完整版本，或到仓库首页查看 MIT 许可证全文。"}

    def save_prefs(self, prefs: dict) -> dict:
        # 与生命周期心跳共用同一把锁的原子读-合并-写（update_prefs）
        if not update_prefs(prefs or {}):
            return {"ok": False, "error": "prefs_busy",
                    "text": "设置暂未保存，另一个窗口正在保存数据。"}
        return {"ok": True}

    def save_feishu_webhook(self, url: str = "") -> dict:
        """飞书提醒地址：校验与合并写回在 application 层，这里只薄转发读写端口。"""
        return _feishu_settings.save(CONFIG_FILE, url, read=_read_config_text,
                                     write=_prefs_store.atomic_write)

    def test_feishu_webhook(self, url: str = "") -> dict:
        """发一条测试消息：走现有 webhook 适配器，结果交给设置里就地显示。"""
        return _feishu_settings.test_message(url, post=_feishu_webhook_post.post_json)

    def accept_terms(self, document_version: str = "") -> dict:
        """同意使用条款：先核验界面实际读到的文档版本，再经 ui.json 原子偏好事务落盘。

        同意必须绑定「用户读到的那份全文」：document_version 为空、旧版、
        未知新版或类型非法，都说明界面副本与程序要求不同源（混合资源或旧
        HTML），此时零写入直接拒绝——否则界面提示不匹配却已留下当前版同意，
        刷新后会放行。只写 terms_version / terms_accepted_at 两个键——不读写
        任何登录文件，不把同意状态写进运行日志；拿不到跨进程锁时如实返回
        失败，让界面留在条款弹窗里重试。
        """
        # 版本判定必须在 time.strftime 与 update_prefs 之前：拒绝路径零副作用
        if not (isinstance(document_version, str)
                and document_version == TERMS_VERSION):
            return {
                "ok": False,
                "error": "terms_version_mismatch",
                "text": "界面显示的条款版本与程序要求的版本不一致，请重新下载完整版本后再确认。",
                "terms": terms_state(load_prefs()),
            }
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if not update_prefs({"terms_version": TERMS_VERSION,
                             "terms_accepted_at": stamp}):
            return {"ok": False, "error": "prefs_busy",
                    "text": "条款同意状态暂未保存，另一个窗口正在保存数据；请再点一次。"}
        return {"ok": True, "terms": terms_state(load_prefs())}

    def withdraw_terms(self) -> dict:
        """撤回条款同意：清空已同意版本、记下撤回时刻，学校动作随即回到条款门之后。

        计划在跑或已就绪时拒绝：撤回会让后面的场次登录和提交全被拦住，等于悄悄停掉计划，
        必须先由用户自己停止。只写 ui.json 的三个条款键——保存的账号密码、登录信息一概
        不动，重新同意后照常可用；不起线程、不写运行日志。
        """
        if self.plan_active_for_close():
            return {"ok": False, "error": "plan_running",
                    "text": "计划运行中不能撤回，先停止计划。"}
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        if not update_prefs({"terms_version": "", "terms_accepted_at": "",
                             "terms_withdrawn_at": stamp}):
            return {"ok": False, "error": "prefs_busy",
                    "text": "撤回没有保存，另一个窗口正在保存数据；请再点一次。"}
        # 撤回时刻只随这次回执给界面显示；terms_state 仍只回报三个键（条款契约不变）
        return {"ok": True, "terms": dict(terms_state(load_prefs()), withdrawn_at=stamp)}

    # ---------- 内部 ----------
    def _is_busy_locked(self) -> bool:
        """G1 忙碌判定；调用方持 self._lock。判定已归 Coordinator，这里只转发。

        只读协调器已发布的不可变状态：持 Api 锁时绝不取协调器锁（P2-1）。
        反向路径（协调器 → Api）同样已改为锁外发布，两条边不再成环。
        """
        return self._coord.is_busy_locked()

    def _is_busy(self) -> bool:
        with self._lock:
            return self._is_busy_locked()

    def _run_plan_task(self, spec: TaskSpec, cancel_event: threading.Event,
                       status: callable) -> dict:
        """运行一个单活动脚本；取消只终止对应进程，不影响同批其他任务。

        用例实现在 application.plan.plan_service；worker 命令、环境、进程树创建、
        监督余量、学校时间换算与时钟异常类型都从这里以端口注入（裸名解析
        保持测试按 app.X 替换的语义）。
        """
        return _plan_service.run_plan_task(
            spec, cancel_event, status,
            emit=self._emit, lock=self._lock, plan_procs=self._plan_procs,
            plan_trees=self._plan_trees,
            clock_now=self._clock_now, is_closing=lambda: self._closing,
            worker_command=worker_command, env=_env, spawn=spawn_owned_worker,
            cwd=str(HERE), grace_s=SUPERVISE_GRACE_S,
            epoch_of=school_epoch, time_text_of=school_time_text,
            clock_unavailable=ClockUnavailable,
            relogin_wait_s=self._relogin_wait_s(),
            on_login_wait=self._request_auto_relogin)

    def _trace(self, msg: str) -> None:
        """调试用：只有设了 CAMPUS_TRACE 才落盘，平时零副作用。"""
        path = os.environ.get("CAMPUS_TRACE")
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(str(msg) + "\n")
        except Exception:
            pass

    def _run(self, args: list[str], timeout: int) -> dict:
        return self._worker_service.run(args, timeout)

    def _spawn(self, args: list[str], label: str, kind: str = "grab") -> dict:
        return self._worker_service.spawn(args, label, kind)

    def _anchor_login_success(self, origin: str = "") -> None:
        return self._relogin_entry._anchor_login_success(origin)

    def _pump(self, proc, label: str, kind: str = "grab") -> None:
        return self._worker_service.pump(proc, label, kind)


# ---- 兼容包装：已下沉 domain / infrastructure 的纯规则与进程树适配器 ----
# 实现见 domain.common.time_text / domain.signup.retry_rules / domain.login.login_rules /
# domain.worker.worker_lines / infrastructure.desktop.process_tree；旧名字保留供测试与
# 内部调用按原名注入、patch。
_task_deadline = _time_text.task_deadline
_kill_tree = _process_tree.kill_tree
_SpawnFailure = _process_tree.SpawnFailure
_ProcessTree = _process_tree.ProcessTree
spawn_owned_worker = _process_tree.spawn_owned_worker
spawn_owned = _process_tree.spawn_owned
_win_kernel32 = _process_tree.win_kernel32
_parse_checkpoint_line = _worker_lines.parse_checkpoint_line
_parse_clock_line = _worker_lines.parse_clock_line
_attempts_of = _retry_rules.attempts_of
_with_attempts = _retry_rules.with_attempts
_retry_payload = _retry_rules.retry_payload
_ATTEMPT_RE = _retry_rules.ATTEMPT_RE


def _parse_retry_line(line: str) -> "dict | None":
    """解析 worker 的 [retry] 结构化终态行（实现在 domain.signup.retry_rules）。"""
    return _retry_rules.parse_retry_line(line)


def _check_reason_line(out: str) -> tuple[str, str]:
    """从 check 的完整输出提取 (来源行, 末行)（实现在 domain.login.login_rules）。"""
    return _login_rules.check_reason_line(out)


def _check_result(state: dict, code: int, text: str) -> str:
    """check 的四态结论（实现在 domain.login.login_rules）。"""
    return _login_rules.check_result(state, code, text)


def _check_hint(text: str, code: int) -> str:
    """把 check 的来源行粗分类：network / login / error（实现在 domain.login.login_rules）。"""
    return _login_rules.check_hint(text, code)








SUPERVISE_GRACE_S = 5.0








def _runtime_check_main(argv: list[str]) -> int:
    """离线自检 CLI（--runtime-check --report <绝对JSON路径>）。

    在 GUI/数据根/生命周期**之前**分发：只验证「冻结程序能按真实解析路径启动
    内置 worker --help 并正常退出」，不访问学校、不读凭证、不初始化统一数据根。
    缺 CAMPUS_DATA_DIR 直接拒绝——worker 自身启动会建数据根，验收必须显式指定
    临时目录，绝不摸到真实登录态。窗口版没有控制台：结论只经 JSON 文件与
    进程退出码表达（成功 0 / 失败 1 / 报告写不出去 2）。
    """
    report = ""
    for i, part in enumerate(argv):
        if part == "--report" and i + 1 < len(argv):
            report = argv[i + 1]
    result = {
        "version": APP_VERSION,
        "frozen": bool(getattr(sys, "frozen", False)),
        "worker": str(GRAB),
        "ok": False,
        "exit_code": None,
    }
    if not report:
        print("[X] runtime-check 缺少 --report <绝对JSON路径>", file=sys.stderr)
        return 2
    try:
        report_path = Path(report)
        if not report_path.is_absolute():
            raise ValueError("--report 需要绝对路径（窗口版没有可依赖的 cwd）")
        if not os.environ.get("CAMPUS_DATA_DIR", "").strip():
            raise ValueError("缺少 CAMPUS_DATA_DIR：离线自检必须显式指定临时数据根，"
                             "拒绝触碰真实登录态")
        problem = worker_problem()
        if problem:
            result["component"] = problem
            raise RuntimeError(WORKER_PROBLEM_TEXT[problem])
        proc = subprocess.Popen(
            worker_command("--help"), cwd=str(HERE),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            env=_env(), creationflags=CREATE_NO_WINDOW)
        try:
            proc.communicate(timeout=RUNTIME_CHECK_TIMEOUT_S)
            result["exit_code"] = proc.returncode
            result["ok"] = proc.returncode == 0
            if not result["ok"]:
                result["error"] = "worker --help 退出码 %s" % proc.returncode
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            result["error"] = "worker --help 超时（%d 秒）" % RUNTIME_CHECK_TIMEOUT_S
    except Exception as exc:  # noqa: BLE001 - 结论一律落 JSON，不向上抛
        result.setdefault("error", str(exc))
    try:
        rp = Path(report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        tmp = rp.with_name(rp.name + ".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, rp)
    except Exception as exc:
        print("[X] runtime-check 报告写不出去：%s" % exc, file=sys.stderr)
        return 2
    return 0 if result["ok"] else 1


def _screen_size():
    """主屏分辨率 (宽, 高)；取不到（QA/无显示环境）返回 None，不抛错。"""
    try:
        screen = webview.screens[0]
        return int(screen.width), int(screen.height)
    except Exception:
        return None


def _window_geometry(screen=None) -> tuple[int, int, int, int]:
    """窗口出厂几何 (width, height, min_w, min_h)。

    目标 1280×820（内容密度按 ≥1280 设计），最小 1024×680；screen 为
    主屏分辨率时，宽度按原值、高度先扣 80px 任务栏余量再收敛到目标，
    并托底到最小尺寸（屏过小时宁可略超也不塌缩）。screen 不可用则直接
    返回出厂值。
    """
    width, height, min_w, min_h = 1280, 820, 1024, 680
    if screen:
        try:
            screen_w, screen_h = int(screen[0]), int(screen[1])
        except (TypeError, ValueError, IndexError):
            return width, height, min_w, min_h
        width = min(width, screen_w)
        height = min(height, screen_h - 80)
        width = max(width, min_w)
        height = max(height, min_h)
    return width, height, min_w, min_h


def main() -> int:
    # --runtime-check 先于一切副作用分发：不建数据根、不起生命周期、不开窗口
    if "--runtime-check" in sys.argv:
        return _runtime_check_main(sys.argv)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    # 启动即确保统一数据根可用；冻结进程首次启动会顺带迁移旧 EXE 旁数据
    ensure_data_dir()
    global DEMO
    if "--demo" in sys.argv:
        DEMO = True
    if not UI.exists():
        print("找不到界面文件：%s" % UI, file=sys.stderr)
        return 1
    # 防止开两份（GL01）：只守图形界面启动，worker 子命令是别的进程、不经过这里。
    # 第二份唤回第一份后直接退出（退出码 0），不建时钟、不建 Api、不起窗口。
    # --demo 不接入：假数据、不碰学校，提交不了报名；演示数据根又是临时目录，
    # 端口文件对不上，接入了反而会让演示和正式版互相挡住。
    # 守卫出任何意外都放行（fail-open）：绝不能让唯一的那一份打不开。
    instance_guard = None
    instance_role = None
    if not DEMO:
        try:
            instance_guard = _single_instance.SingleInstance(DATA_DIR)
            instance_role = instance_guard.acquire()
        except Exception as exc:  # noqa: BLE001
            print("[!] 单实例守卫出错，照常启动：%s" % type(exc).__name__, file=sys.stderr)
            instance_guard = None
    if instance_guard is not None and instance_role == _single_instance.SECOND:
        # 判定为第二份就一定在这里退出；hand_over 自己吞掉一切异常，恒返回 0
        return instance_guard.hand_over()
    if instance_guard is not None:
        # 崩溃或异常退出时也尽量删掉自己的端口文件；互斥量由系统随进程收回
        atexit.register(instance_guard.close)
    # 进程级生命周期：冻结上一运行周期并开始心跳（F5 重载不重置；
    # 懒创建兜底——bootstrap 先被调用时也能拿到同一实例）
    # 独立北京时间（决策 012）：主程序唯一 BusinessClock 生命周期；
    # 后台同步不阻塞 UI，Api import 时不联网；demo 完全离线（标「演示时间」）
    clock = BusinessClock(background=not DEMO)
    configure_time_source(clock.now)
    try:
        snap = clock.snapshot()
        if snap.get("owner_id"):
            _CLOCK_ENV["path"] = clock._snapshot_path()
            _CLOCK_ENV["owner"] = str(snap.get("owner_id"))
    except Exception:
        pass
    lifecycle = get_lifecycle(now_fn=clock.now)
    api = Api(clock=clock)
    api._start_clock_monitor()
    if not DEMO:
        # 清理线程早于窗口创建，界面事件会丢；经 grab.log 落盘（只含数量或异常类型名）
        sweep_versions_in_background(
            log=lambda **fields: api._log_event("version_sweep", level="WARN", **fields))
    width, height, min_w, min_h = _window_geometry(_screen_size())
    window = webview.create_window(
        "校园活动预报名工具", str(UI),
        js_api=api, width=width, height=height, min_size=(min_w, min_h),
        background_color="#E9EEF6",
    )
    api._window = window
    api.schedule_phone_restore(window)
    if instance_guard is not None:
        # 窗口对象有了再开唤回监听：show()/evaluate_js 会等窗口真正显示、加载完
        instance_guard.start_listener(api._on_second_open)

    def _closing() -> bool:
        """返回 False 取消关闭。默认 ask：弹出三选，绝不静默带走正在跑的计划。"""
        return handle_window_close(api, window)

    try:
        window.events.closing += _closing
    except AttributeError:
        # 老版本 pywebview 没有可取消的 closing：退化成「直接关」，
        # 行为与升级前一致，不假装能拦
        pass
    try:
        # 最小化/还原：计划在后台结束时据此决定要不要发系统通知
        window.events.minimized += api._on_window_minimized
        window.events.restored += api._on_window_restored
    except AttributeError:
        pass
    webview.start(debug=False)
    if instance_guard is not None:
        # 窗口没了就先停监听：收尾期间再开的那份连不上，弹「工具已经开着」，
        # 互斥量留到收尾完，免得新的一份在旧 worker 还没收干净时就开跑计划
        instance_guard.stop_listener()
    # 窗口已关（正常路径）：先收本实例登记的 worker（计划/登录/单活动/check/list）——
    # onefile 退出后运行期资源根即消失，绝不能留下还握着它的孤儿进程；
    # 再停心跳并落关闭时刻，clean/abnormal 的分界不变
    api.shutdown()
    lifecycle.finalize()
    clock.close()
    if instance_guard is not None:
        instance_guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
