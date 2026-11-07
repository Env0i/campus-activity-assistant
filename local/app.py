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
from business_clock import BusinessClock, ClockUnavailable
from time_contract import school_epoch, school_time_text, configure_time_source
from update_check import check_latest_release
import update_check as _update_check
from urllib.error import HTTPError, URLError
import updater

# 登录态/偏好统一数据根：开发用 local/data，冻结 EXE 用 %LOCALAPPDATA%
# （CAMPUS_DATA_DIR 可覆盖），与 grab-worker 解析出同一份登录文件
from runtime_paths import DATA_DIR, LOG_FILE, SESSION_FILE, UI_STATE_FILE, ensure_data_dir

# 分层依赖（只准向下）：app（interface 外观）→ application → domain 纯规则；
# 外部副作用统一走 infrastructure 适配器。旧模块级名字保留为兼容包装/再导出，
# 测试与调用方按原名注入、patch 的语义不变。
from domain import demo_data as _demo_data
from domain import lifecycle_rules as _lifecycle_rules
from domain import log_events as _log_events
from domain import login_rules as _login_rules
from domain import plan_rules as _plan_rules
from domain import retry_rules as _retry_rules
from domain import time_text as _time_text
from domain import worker_lines as _worker_lines
from domain.errors import ClosingError as _ClosingError
from infrastructure import lifecycle_store as _lifecycle_store
from infrastructure import prefs_store as _prefs_store
from infrastructure import process_tree as _process_tree
from infrastructure import phone_http as _phone_http
from infrastructure import advanced_features as _advanced_features
from infrastructure import component_packages as _component_packages
from infrastructure import credential_store as _credential_store
from infrastructure import phone_session_store as _phone_session_store
from infrastructure import phone_qr as _phone_qr
from infrastructure import tunnel_manager as _tunnel_manager
from application import login_service as _login_service
from application import login_relay_service as _login_relay_service
from application.auto_relogin import AutoReloginMonitor
from application import phone_service as _phone_service
from application import advanced_component_service as _advanced_component
from application import plan_service as _plan_service
from application import update_service as _update_service

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", HERE))
# 和报名进程同一份配置：界面只读其中的 feishu_webhook 一个键
CONFIG_FILE = HERE / "config.json"
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
TERMS_VERSION = "2026-11-07-r5"


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
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    hook = str(data.get("feishu_webhook") or "").strip()
    return hook if hook.startswith("https://") else ""


def _component_title(feature: str) -> str:
    """组件的中文名：下载日志与「没有发布组件包」提示用，和 update_check 同一份。"""
    return _update_check.COMPONENT_TITLES.get(str(feature), str(feature))


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
             "label": "自动延长（最多25分钟）"},
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

    实现已下沉 domain.login_rules（纯分类）；此处保留旧名字兼容包装。
    """
    return _login_rules.component_error(exc)


# 关闭屏障语义类型在 domain.errors；旧名字保留为再导出（同 class 对象）。
# 调用方必须把它与组件异常分开处理——关闭拒绝不得归类为 worker_* 组件码，
# 也不得冒充报名失败向上抛。

# --demo：用假数据起界面，方便调样式、截图，不需要登录
DEMO = False


def demo_items() -> list[dict]:
    """演示样例集：纯数据模型在 domain.demo_data，时间与格式化在此注入。"""
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


# 偏好存储原语已下沉 infrastructure.prefs_store；旧名字保留为再导出，
# 测试与调用方继续用 app.load_prefs_from / app._atomic_write_prefs 等注入。
load_prefs_from = _prefs_store.load_from
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
    """本机内部凭证摘要（纯规则在 domain.login_rules）：只用于把 v2 锚点和具体凭证绑定。"""
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
# 锁与事务原语在 infrastructure.prefs_store；这里保留旧常量名供注入/patch。
_PREFS_LOCK = _prefs_store.PREFS_LOCK
_PREFS_LOCK_TIMEOUT_S = _prefs_store.LOCK_TIMEOUT_S   # 生命周期元数据：拿不到就放弃本次写入
_PREFS_SAVE_TIMEOUT_S = _prefs_store.SAVE_TIMEOUT_S   # 用户偏好：给正在收尾的另一个进程留出时间


def update_prefs(patch: dict) -> bool:
    """统一的原子读-合并-写（Api.save_prefs 与生命周期心跳共用同一把锁）。

    拿不到跨进程锁就返回失败：绕过文件锁写入会覆盖另一个实例刚保存的周期。
    调用方可重试用户偏好；可选登录估算落盘失败也不影响真实登录成功。
    """
    try:
        with _prefs_transaction(PREFS, timeout_s=_PREFS_SAVE_TIMEOUT_S):
            prefs = load_prefs()
            prefs.update(patch or {})
            _atomic_write_prefs(PREFS, prefs)
        return True
    except _PrefsLockTimeout:
        return False


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
    分类规则在 domain.login_rules（纯函数）；这里只负责读 session.json 并
    保持旧名兼容（测试按 app.SESSION_FILE 注入）。
    """
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        token = str(data.get("token") or "").strip()
        saved_text = str(data.get("saved_at") or "").strip()
    except Exception:
        return _login_rules.build_session_state("", "", None, None)
    if not token:
        return _login_rules.build_session_state("", "", None, None)
    # 不再按写死寿命倒推剩余时间（S3）：hours_left 恒为 None，
    # 界面改读 bootstrap 里的 last_check_at / last_check_state。
    # 旧字段先保留为 null，待 UI 计划移除。
    return _login_rules.build_session_state(token, saved_text, None, None)


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


# 时间文本换算已下沉 domain.time_text；旧名字保留为兼容包装（学校时间换算
# 在此注入 time_contract.school_epoch，domain/application 不直连混合模块；
# 墙钟读取也留在此界面层，domain 只做纯格式化）。
_parse_local_time = _time_text.parse_local_time
_latest_moment = _time_text.latest_moment


def _now_text() -> str:
    """本地墙钟文本（兼容名；实现在 domain.time_text.format_local_text，取时在此）。"""
    return _time_text.format_local_text(datetime.now())


def _seconds_until(ts: str | None, now: "float | None") -> "int | None":
    """学校时间文本距现在多少秒（实现在 domain.time_text，换算函数在此注入）。"""
    return _time_text.seconds_until(ts, now, school_epoch)


def _task_deadline(spec) -> "float | None":
    """父层视角的本场绝对截止（实现在 domain.time_text，换算函数在此注入）。"""
    return _time_text.task_deadline(spec, school_epoch)

# 生命周期纯记账已下沉 domain.lifecycle_rules；旧名字保留为再导出。
compute_lifecycle = _lifecycle_rules.compute_lifecycle
compute_lifecycle_v2 = _lifecycle_rules.compute_lifecycle_v2


# 生命周期持久化已下沉 infrastructure.lifecycle_store；旧名字保留为再导出。
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
    """relay worker 的最小进程句柄：收尾走既有树终止，不另起第二套收尸。"""

    def __init__(self, proc: subprocess.Popen):
        self.proc = proc

    def terminate(self) -> None:
        _kill_tree(self.proc)


class Api:
    def __init__(self, clock=None) -> None:
        # 独立北京时间（决策 012）：生产 main 注入 BusinessClock；
        # 未注入时显式不可用，绝不回退本机时间。测试必须显式注入 Fake。
        self._clock = clock if clock is not None else _UnavailableClock()
        self._clock_syncing = False
        self._window: webview.Window | None = None
        self._proc: subprocess.Popen | None = None
        self._plan: PlanCoordinator | None = None
        self._plan_procs: dict[str, subprocess.Popen] = {}
        # 最近一个已结束计划的快照（只读展示用；_plan 只表示当前计划）
        self._last_plan: dict | None = None
        # check/list 这类短命 worker 的登记表：正常关闭时一并树终止，不留孤儿
        self._aux_procs: set = set()
        self._activities: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._credential_lock = threading.RLock()
        self._advanced_busy = False
        self._phone_access_lock = threading.RLock()
        # 关闭屏障：shutdown 在同一把 _lock 内置位 _closing，而一切 worker 创建
        # （Popen）与登记也都在这把锁里先核它——关闭先发生则零创建；创建已开始
        # 则 shutdown 必等登记完成才能取快照，收走的进程不会漏。
        # _closing 表达「关闭已开始」；「收尾已完成」用 Event 表达（FB2）：后到
        # 的 shutdown 在锁外等待同一个 Event，返回即代表收尾真正完成。
        self._closing = False
        # 关窗弹窗里点过「退出」才放行：closing 事件返回 False 会取消关闭
        self._close_approved = False
        # 托盘图标：只在窗口藏起来以后才建，建不起来也不影响主程序
        self._tray = None
        self._shutdown_done_event = threading.Event()
        # 刷新去重：连点「刷新」不该堆起多个 check/list 子进程
        self._checking = False
        # 去重期间又被要求刷新的标记：本轮收尾时补查一次，重登成功后的刷新
        # 不能被「已在检查」静默丢掉（只补一次，不排循环）
        self._check_again = False
        self._listing = False
        # 在途请求 ID：去重跳过时界面才能对上账（R11）
        self._check_request_id = ""
        self._list_request_id = ""
        self._check_last = {"request_id": "", "payload": None}
        self._list_last = {"request_id": "", "payload": None}
        # 最近一次 check 的四态结论：start_plan 的放行/拒绝只信它
        self._last_check: dict = {}
        # 报名进程发来 login_wait（决策 015）：允许这一次在计划运行中自动登录
        self._login_wait_pending = False
        # 最近一次自动登录发起时刻（单调钟）：成功/失败落盘日志时算整轮耗时
        self._auto_relogin_started_at = None
        # 更新检查独立于登录/报名，只由帮助按钮触发；页面重载复用内存中的在途请求。
        # _updating 表示「任一更新动作在途」（检查或下载），单飞共用一个槽位；
        # _update_installer 是检查阶段选好的安装器资产（URL/大小/哈希），
        # 下载只信它，不收界面传来的地址；_update_installer_path 是校验通过后的本地产物。
        self._updating = False
        self._update_request_id = ""
        self._update_result: dict | None = None
        self._update_installer: dict | None = None
        self._update_installer_path = ""
        self._update_cancelled = False
        # 开始请求登记（R11）：request_id → {state, plan_id, result}。
        # 只留最近有限条，活跃请求不驱逐；不存凭证、不写外部数据。
        self._start_requests: dict[str, dict] = {}
        self._start_order: list[str] = []
        # 取消保护跨过普通 32 条历史的淘汰；进程内保留，上限满时拒绝新取消。
        self._canceled_start_ids: set[str] = set()
        # 计划接纳代次与最近接纳计划（P1）：plan/task/plan_done 事件与终态快照
        # 只归属「最近接纳的计划」。槽为空（_plan=None）不代表迟到回调属于最新
        # 计划——较新的计划可能已经结束；归属以接纳代次为准，不随 _plan 清空遗失。
        self._plan_generation = 0
        self._latest_plan_id = ""
        # 已提交过终态的计划（重复 plan_done 幂等：已定结论不被重复包改写）
        self._finished_plan_ids: dict[str, bool] = {}
        # 手机受限访问（默认关闭）：配对/会话只活在内存里，事件走有界缓冲。
        # 这里不建 socket——只有显式 start_phone_access 才监听。
        self._phone = _phone_service.PhoneAccessService(
            api=self, now=self._clock_now, state_of=self._phone_raw_state,
            device_store=_phone_session_store.PhoneSessionStore(DEVICE_FILE),
            log=phone_log,
            server_factory=lambda host, port, svc, public_host="", public_scheme="http": _phone_http.PhoneHttpServer(
                host, port, svc, public_host=public_host, public_scheme=public_scheme,
                log=phone_log))
        self._phone_channel = ""
        # 组件包下载：手机控制、验证码识别各一条事务。只有用户点「下载并安装」才动网络；
        # 失败不影响已有组件
        self._component_service = _advanced_component.AdvancedComponentService(
            feature=_advanced_features.PHONE_CONTROL,
            root=DATA_DIR,
            download=updater.download_installer,
            asset_resolver=self._resolve_component_asset,
            install=self._install_downloaded_component,
            on_installed=self._component_installed,
            on_finished=self._component_finished,
            log=phone_log)
        self._ocr_component_service = _advanced_component.AdvancedComponentService(
            feature=_advanced_features.RELOGIN_OCR,
            root=DATA_DIR,
            download=updater.download_installer,
            asset_resolver=lambda version: self._resolve_component_asset(
                version, _advanced_features.RELOGIN_OCR),
            install=self._install_downloaded_ocr,
            on_installed=self._ocr_component_installed,
            on_finished=self._component_finished,
            log=phone_log)
        # 上一次登录真实成功后由谁完成（auto_ocr / phone_manual）：只用于说明文案
        self._last_login_origin = ""
        # 登录失效推飞书：本次运行里校验过有效，之后变成失效才推；同一次失效只推一次
        self._login_seen_valid = False
        self._expiry_pushed = False
        # 窗口不在眼前（最小化或隐藏到后台）时，计划结束要发系统通知
        self._window_hidden = False
        self._window_minimized = False
        # 计划来源（desktop / phone）：start_plan 调用前登记，随计划事件和快照带出去
        self._next_plan_source = "desktop"
        self._plan_sources: dict[str, str] = {}
        self._cloudflare = _tunnel_manager.CloudflareTunnel(
            _tunnel_manager.resolve_cloudflared(resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR),
            # 每次真正拉起隧道前再核一遍组件：缓存路径可能已被替换或删除
            verify=lambda path: _tunnel_manager.verify_managed_cloudflared(path, root=DATA_DIR))
        # 隧道异常退出只报一次 exited，之后 status() 读到的就是 stopped：
        # 退出提示必须自己存住，否则同一次状态组装里的第二次读取会把它降级成「可用」。
        # None 表示「没有未收起的退出提示」，用户手动 stop 或成功 start 后清空。
        self._cloudflare_exit_notice: dict | None = None
        # Cloudflare 拉起隧道是一段有网络等待的同步过程：期间再点一次「开启」，
        # 必须明确回「正在启动」，而不是排队后又叠一条隧道。
        self._cloudflare_starting = False
        # 手机重登中继：凭据只在进程内存，singleflight，成功才建时钟锚点
        self._relay = _login_relay_service.LoginRelayService(
            spawn=self._spawn_relay_worker, now=time.monotonic,
            emit=self._emit, log=lambda _msg: None,
            on_success=self._anchor_login_success,
            on_finish=self._relay_finished,
            classify_captcha=self._classify_captcha, manual_after=_MANUAL_RELOGIN_AFTER)
        # 这一场登录用的是谁的账号密码：saved=电脑上保存的，typed=这次手输的
        # （只在内存里，勾了保存才在成功后写盘）。决定失败时要不要暂停自动登录。
        self._relay_creds_source = ""
        self._pending_save: dict | None = None
        self._auto_relogin = AutoReloginMonitor(
            now=time.monotonic, check=self.check, start=self._begin_auto_relogin,
            eligible=self._auto_relogin_eligible, state=self._relay.state,
            paused=lambda: _credential_store.is_bad(CREDENTIAL_FILE))
        if not DEMO:
            self._auto_relogin.start()

    # ---------- 独立北京时间 ----------
    def _clock_now(self) -> float:
        if DEMO:
            # 演示离线：与 bootstrap 的「演示时间」快照同源（OS 时刻，仅演示）
            return time.time()
        return self._clock.now()

    def _clock_ready(self) -> bool:
        """开始门禁只认 ready/holdover 且 bounds 可读：syncing/未知不放行。"""
        try:
            if self._clock.state() not in ("ready", "holdover"):
                return False
            lower, upper = self._clock.bounds()
        except Exception:
            return False
        return bool(upper >= lower)

    def _clock_payload(self) -> dict:
        """bootstrap 的时钟载荷：demo 离线给显式标注的「演示时间」快照，
        不冒充真实授时；正常模式返回当前业务时钟快照。"""
        if DEMO:
            return {"schema": 1, "owner_id": "demo-clock", "generation": 1,
                    "state": "ready", "epoch_s": time.time(), "tick_s": 0,
                    "sampled_tick_s": 0, "uncertainty_s": None,
                    "source": "演示时间（离线，非真实授时）", "age_s": 0,
                    "sync_status": "succeeded", "sync_round": 1,
                    "retry_attempt": 0, "retry_in_s": 0,
                    "last_failure_source": "", "last_failure_reason": "",
                    "reason": "演示模式不联网：顶栏时间仅供演示"}
        return self.clock_snapshot()

    def clock_snapshot(self) -> dict:
        """当前业务时钟快照（无凭证）：bootstrap 与「重新校时」共用。"""
        try:
            return self._clock.snapshot()
        except Exception as exc:
            # 兜底也要带齐退避字段：界面按「有字段但为空」渲染，不靠缺键猜测
            return {"schema": 1, "state": "unavailable", "reason": str(exc),
                    "retry_attempt": 0, "retry_in_s": 0,
                    "last_failure_source": "", "last_failure_reason": ""}

    def sync_clock(self) -> dict:
        """界面「重新校时」：去重后台重校，完成后推 business_clock 事件。"""
        with self._lock:
            if self._clock_syncing:
                return {"ok": True, "queued": True, "dedup": True}
            self._clock_syncing = True

        def run():
            try:
                # demo 完全离线：不发起 NTP，直接确认「演示时间」快照
                state = "ready" if DEMO else self._clock.sync()
            except Exception:
                state = "unavailable"
            with self._lock:
                self._clock_syncing = False
            self._emit("business_clock",
                       self._clock_payload() if DEMO else self.clock_snapshot())
            return state

        threading.Thread(target=run, name="clock-resync", daemon=True).start()
        return {"ok": True, "queued": True}

    def _start_clock_monitor(self) -> None:
        """有未来任务时在最早准备点前 20 秒请求一次后台重校（尊重源冷却）。"""
        if getattr(self, "_clock_monitor_started", False):
            return
        self._clock_monitor_started = True

        def monitor():
            requested_for = None
            while True:
                time.sleep(5)
                try:
                    with self._lock:
                        plan = self._plan
                    if plan is None:
                        requested_for = None
                        continue
                    nxt = plan.next_prepare_epoch()
                    if nxt is None:
                        continue
                    left = nxt - self._clock_now()
                    if 0 < left <= 20 and requested_for != plan.plan_id:
                        self._clock.request_resync()
                        requested_for = plan.plan_id
                except Exception:
                    continue

        threading.Thread(target=monitor, name="clock-monitor", daemon=True).start()

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
            lifecycle_info = get_lifecycle().snapshot()
        payload = {
            "version": APP_VERSION,
            "prefs": prefs,
            # 条款同意快照：界面据此决定是否弹条款、是否放行学校网络动作；
            # 同意状态本身只存 ui.json（terms_version / terms_accepted_at）
            "terms": terms_state(prefs),
            "business_clock": self._clock_payload(),
            "help": self.help(),
            "advanced_features": self.advanced_features_state(),
            "login": login_info,
            # 生命周期元数据（上一周期关闭时长/质量 + 登录估算）：只作提示，
            # 不参与任何放行/拦截；F5 重载重复调用拿到的是同一份进程级快照
            "lifecycle": lifecycle_info,
            # demo 标记：界面据此放行演示计划（真实模式仍要求登录校验 valid）
            "demo": DEMO,
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
            payload["update_check"] = {"checking": self._updating,
                                       "request_id": self._update_request_id,
                                       "result": self._update_result,
                                       "installer_path": self._update_installer_path}
            generation = self._plan_generation
        if snapshot is not None:
            # 页面重载会丢掉 plan/task 事件：把计划快照一并交给 bootstrap，
            # 界面才能恢复任务列表和「停止」按钮；计划本身不会重复提交。
            # 复制一份再补归属字段，不改写共享的 _last_plan。
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
                 "text": "顶部显示“已登录”就可以继续。只有提示失效时才需要重新登录。"},
                {"no": 2, "title": "选活动并开始",
                 "text": "在时刻表勾选活动，核对右边的计划，再点「开始报名计划」。勾选不会自动开始。"},
                {"no": 3, "title": "看结果",
                 "text": "每场结果单独显示。看到“待核对”时，到学校活动页确认。"},
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
            release_api = _update_check.LATEST_API.rsplit("/", 1)[0] + "/tags/v" + version
            payload = json.loads(
                _update_check._fetch_bytes(
                    release_api, _update_check.MAX_BYTES,
                    "TianSoftActivityPreRegistration/component").decode("utf-8"))
            picked = _update_check.select_release_assets(payload, version)
            raw_manifest = b""
            if picked["manifest_url"]:
                raw_manifest = _update_check._fetch_bytes(
                    picked["manifest_url"], _update_check.MAX_MANIFEST_BYTES,
                    "TianSoftActivityPreRegistration-component-manifest")
            verdict = _update_check.resolve_component_asset(
                payload, version, raw_manifest, feature)
        except HTTPError as exc:
            if exc.code in (403, 429):
                return {"ok": False, "error": "rate_limited",
                        "text": "GitHub 暂时限制查询，请稍后重试或查看发布页。"}
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
            return {"ok": False, "error": "invalid_response",
                    "text": "组件包信息无法识别，请查看发布页。"}
        except OSError:
            return {"ok": False, "error": "network_error",
                    "text": "暂时连不上 GitHub，请检查网络后重试。"}
        if verdict.get("state") != "available":
            return {"ok": False,
                    "error": str(verdict.get("error_code") or verdict.get("state") or "no_component"),
                    "text": str(verdict.get("text") or "组件包不可用。")}
        return {"ok": True, "asset": verdict["asset"]}

    def _install_downloaded_component(self, archive, key, *, root=None):
        """下载与手动导入共用通道锁，换包前先释放正在使用的组件进程。"""
        with self._credential_lock, self._phone_access_lock:
            with self._lock:
                if self._closing:
                    raise RuntimeError("application_closing")
            self._cloudflare.stop()
            self._phone.shutdown(preserve_devices=True)
            self._phone_channel = ""
            return _component_packages.install(archive, key, root=root)

    def _component_finished(self) -> None:
        with self._lock:
            self._advanced_busy = False

    def _component_installed(self, version: str) -> None:
        """组件装好后的收尾（在工作线程里被调用）：写启用状态、刷新 cloudflared。"""
        enabled = dict(load_prefs().get("advanced_features") or {})
        enabled[_advanced_features.PHONE_CONTROL] = True
        if not update_prefs({"advanced_features": enabled}):
            phone_log("组件已安装，但启用状态没有保存成功")
        self._cloudflare.executable = _tunnel_manager.resolve_cloudflared(
            resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)
        self._emit("log", "手机控制组件已安装（%s）。" % (version or "版本未知"))

    def _install_downloaded_ocr(self, archive, key, *, root=None):
        """验证码识别包换位前先停掉正在跑的自动登录：识别引擎可能正被它占着。"""
        with self._credential_lock:
            with self._lock:
                if self._closing:
                    raise RuntimeError("application_closing")
            self._relay.cancel(origin="auto")
            self._auto_relogin.reset()
            return _component_packages.install(archive, key, root=root)

    def _ocr_component_installed(self, version: str) -> None:
        """验证码识别装好后写启用状态（在工作线程里被调用）。"""
        enabled = dict(load_prefs().get("advanced_features") or {})
        enabled[_advanced_features.RELOGIN_OCR] = True
        if not update_prefs({"advanced_features": enabled}):
            phone_log("验证码识别组件已安装，但启用状态没有保存成功")
        self._emit("log", "验证码识别组件已安装（%s）。" % (version or "版本未知"))

    def _component_service_for(self, key: str):
        """功能键 → 对应的下载事务；不认识的键返回 None。"""
        mapping = {_advanced_features.PHONE_CONTROL: "_component_service",
                   _advanced_features.RELOGIN_OCR: "_ocr_component_service"}
        name = mapping.get(key)
        # 按 key 惰性取属性：字典急切求值会在查 phone_control 时也碰
        # _ocr_component_service，属性缺失就炸（与 shutdown 收口的
        # getattr(self, name, None) 防御风格对齐）。
        return getattr(self, name) if name else None

    def download_advanced_feature(self, key: str = "") -> dict:
        """用户主动下载组件包（手机控制或验证码识别）：单飞，重复点击直接回 busy。"""
        chosen = str(key or _advanced_features.PHONE_CONTROL)
        service = self._component_service_for(chosen)
        if service is None:
            return {"ok": False, "error": "bad_feature",
                    "text": "这个功能没有可在线下载的组件包。"}
        if not bool(getattr(sys, "frozen", False)):
            # 源码版跑的是仓库里的 Python 依赖，组件包对它没有作用
            return {"ok": False, "error": "source_build",
                    "text": "源码版用的是已装好的 Python 依赖，不需要组件包。"}
        with self._phone_access_lock:
            with self._lock:
                if self._closing or self._advanced_busy or self._is_busy_locked():
                    return {"ok": False, "error": "busy", "text": "请等待当前操作结束。"}
                self._advanced_busy = True
            try:
                result = service.start()
            except Exception:
                self._component_finished()
                raise
            if not result.get("ok"):
                self._component_finished()
        if result.get("ok"):
            self._emit("log", "开始下载%s组件包。" % _component_title(chosen))
        return result

    def cancel_advanced_feature_download(self, key: str = "") -> dict:
        """取消正在进行的组件下载；未在下载时如实说没有任务。"""
        service = self._component_service_for(str(key or _advanced_features.PHONE_CONTROL))
        if service is None:
            return {"ok": False, "error": "bad_feature", "text": "未知高级功能"}
        return service.cancel()

    def enable_advanced_feature(self, key: str = "") -> dict:
        """启用一个已装好但没开启的组件（settings-gap B2，OC08「启用」按钮）。

        只认 phone_control / relogin_ocr；组件没装好（available 为假）时什么都不改。
        与安装完成的收尾一致：验证码识别启用后要重置自动登录的暂停状态。
        """
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "reason": "bad_feature", "error": "bad_feature",
                    "text": "未知高级功能"}
        with self._credential_lock:
            with self._lock:
                if self._closing:
                    return {"ok": False, "reason": "closing", "error": "closing",
                            "text": "程序正在关闭。"}
            prefs = load_prefs()
            feature = _advanced_features.feature_state(
                prefs, root=DATA_DIR, frozen=bool(getattr(sys, "frozen", False))).get(key, {})
            if not feature.get("available"):
                return {"ok": False, "reason": "not_available", "error": "not_available",
                        "text": "这个组件还没装好，不能启用。"}
            enabled = dict(prefs.get("advanced_features") or {})
            enabled[str(key)] = True
            if not update_prefs({"advanced_features": enabled}):
                return {"ok": False, "reason": "prefs_busy", "error": "prefs_busy",
                        "text": "启用状态没有保存，请重试。"}
            if key == _advanced_features.RELOGIN_OCR:
                self._auto_relogin.reset()
            return {"ok": True, "feature": str(key), "enabled": True}

    def advanced_component_location(self, key: str = "") -> dict:
        """组件在本机的安装位置（settings-gap B3，只给电脑端设置抽屉用）。

        路径只经这个接口给 pywebview 的 js_api；绝不放进 advanced_features_state，
        也不进手机快照，手机动作白名单（domain.phone_rules.ACTION_PARAMS）里没有它。
        short 是界面用的省略形式：前面用省略号，只留 advanced 与组件键两段。
        """
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "error": "bad_feature", "text": "未知高级功能"}
        try:
            directory = _component_packages.install_dir(key, root=DATA_DIR)
        except (_component_packages.PackageError, OSError, ValueError):
            return {"ok": False, "error": "location_unavailable", "text": "读不到组件的安装位置。"}
        parts = directory.parts
        short = "…\\" + "\\".join(parts[-2:]) if len(parts) > 2 else str(directory)
        return {"ok": True, "path": str(directory), "short": short,
                "exists": directory.is_dir()}

    def open_advanced_component_dir(self, key: str = "") -> dict:
        """用资源管理器打开组件所在文件夹（B3，只给电脑端）。

        组件目录还不存在就打开它的上一级（advanced），两级都不存在则如实说明。
        """
        located = self.advanced_component_location(key)
        if not located.get("ok"):
            return located
        directory = Path(located["path"])
        target = directory if directory.is_dir() else directory.parent
        if not target.is_dir():
            return {"ok": False, "error": "not_found", "text": "组件文件夹还不存在。"}
        try:
            os.startfile(str(target))        # noqa: S606 - Windows 桌面工具，与 open_data 同
        except OSError as exc:
            return {"ok": False, "error": "open_failed",
                    "text": "没能打开文件夹（%s）。" % type(exc).__name__}
        return {"ok": True, "opened": "component" if target == directory else "parent"}

    def advanced_features_state(self) -> dict:
        """帮助弹窗使用的高级功能快照；不返回密码、密文或安装路径。"""
        prefs = load_prefs()
        features = _advanced_features.feature_state(
            prefs, root=DATA_DIR, frozen=bool(getattr(sys, "frozen", False)))
        if self._advanced_busy:
            for feature in features.values():
                feature["busy"] = True
        # 组件下载事务的快照挂在各自那一行：界面据此显示下载中、失败、可取消
        for key in (_advanced_features.PHONE_CONTROL, _advanced_features.RELOGIN_OCR):
            service = self._component_service_for(key)
            try:
                download = service.snapshot() if service is not None else {}
            except Exception:
                download = {}
            if key in features:
                features[key]["download"] = download
        tailscale = _tunnel_manager.tailscale_endpoint()
        cloudflare_status, cloudflare_exit = self._cloudflare_status_snapshot()
        if cloudflare_exit:
            # 进程已经退出：这次刷新就要报「退出」，不能因为读到的第二次状态是
            # stopped 就把通道重新说成可用——用户会照着旧地址去扫码。
            cf_state = "exited"
            cf_text = str(cloudflare_exit.get("text")
                          or "Cloudflare 隧道已退出，重新开启会得到新地址。")
            cf_error = "tunnel_exited"
        elif self._cloudflare.executable:
            # 快速隧道地址每次开启都变，所以状态只有「可用/在运行」两档，
            # 且必须把「重启后要重新扫码」写进快照，界面照抄，不再自行判断
            cf_state = "running" if cloudflare_status.get("running") else "available"
            cf_text = ("Cloudflare 临时地址正在提供访问。" if cf_state == "running"
                       else "可用时由 Cloudflare 临时地址提供远程访问。")
            cf_error = ""
        else:
            cf_state = "missing"
            cf_text = "没有找到 cloudflared，Cloudflare 通道目前不可用。"
            cf_error = "cloudflared_missing"
        saved = _credential_store.has_credentials(CREDENTIAL_FILE)
        username = ""
        if saved:
            try:
                username = _credential_store.stored_username(CREDENTIAL_FILE)
            except Exception:
                saved = False
        return {
            "ok": True,
            "features": features,
            "channels": {
                "tailscale": dict(tailscale,
                                  temporary=False,
                                  restart_requires_pairing=False,
                                  restart_note="地址固定：重启程序后手机仍可直接打开。"),
                "cloudflare": {
                    "available": bool(self._cloudflare.executable),
                    "error": cf_error,
                    "state": cf_state,
                    "text": cf_text,
                    "temporary": True,
                    "restart_requires_pairing": True,
                    "restart_note": "临时地址：重启或重新开启后地址会变，手机需要重新扫码配对。",
                },
            },
            "phone_access": _phone_access_prefs(prefs),
            "credential": {
                # 保存账号只看本机加密存储；ddddocr 是否就绪单列，界面分开显示
                "available": _credential_store_available(),
                "store_available": _credential_store_available(),
                "saved": saved,
                "username": username,
                "ocr_ready": _advanced_features.feature_ready(
                    prefs, _advanced_features.RELOGIN_OCR, root=DATA_DIR),
                "automatic": self._auto_relogin.snapshot(),
                # B4：这次运行内存里有没有「只用这一次」的账号；只给打码账号，绝无密码
                "staged": self._relay.has_staged(),
                "staged_hint": self._relay.staged_hint(),
                "last_origin": self._last_login_origin,
                # 学校说保存的密码不对：自动登录已暂停，写入新密码后解除
                "paused": saved and _credential_store.is_bad(CREDENTIAL_FILE),
            },
        }

    def inspect_advanced_component(self, key: str = "", path: str = "") -> dict:
        """只读自检：用户选的这份文件到底是不是这里要装的东西。

        对话框每选一次文件就调一次，把「这是别的组件的包」「这是 Tailscale 的 exe」
        这类结论直接顶到界面上，而不是等他点了保存才看到一个错误码。不落盘、不安装。
        """
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "kind": "unknown_feature", "text": "未知高级功能"}
        chosen = str(path or "").strip().strip('"')
        if not chosen:
            return {"ok": False, "kind": "empty", "text": "还没有选择文件。"}
        if Path(chosen).suffix.lower() == ".exe":
            if key != _advanced_features.PHONE_CONTROL:
                return {"ok": False, "kind": "not_zip",
                        "text": "这里需要组件包 ZIP，不是可执行文件。"}
            return _component_packages.inspect_cloudflared(chosen)
        return _component_packages.inspect_archive(chosen, key)

    def pick_advanced_component(self, key: str = "") -> dict:
        """弹系统文件选择框，把用户选中的路径交回给对话框。

        路径只用于这一次自检与安装，不写进偏好、不进日志。
        """
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "text": "未知高级功能"}
        if self._window is None:
            return {"ok": False, "text": "请在电脑窗口里选择文件。"}
        if key == _advanced_features.PHONE_CONTROL:
            types = ("cloudflared (*.exe)", "组件包 (*.zip)")
        else:
            types = ("组件包 (*.zip)",)
        try:
            selected = self._window.create_file_dialog(
                webview.FileDialog.OPEN, allow_multiple=False, file_types=types)
        except Exception:  # noqa: BLE001 - 原生对话框不可用不该让整个页面崩掉
            return {"ok": False, "error": "dialog_unavailable",
                    "text": "打不开系统的文件选择框，请改用手动填写路径。"}
        if not selected:
            return {"ok": True, "canceled": True, "text": "已取消选择。"}
        return {"ok": True, "path": str(selected[0])}

    def install_advanced_feature(self, key: str = "", path: str = "") -> dict:
        """只响应帮助弹窗明确点击的固定组件，不接受任意 pip 包名。

        path 非空时按「用户亲自选的文件」处理：先自检，再决定走组件包导入还是
        收编一份单独校验过的 cloudflared；自检不过就原样把原因交回界面。
        """
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "text": "未知高级功能"}
        chosen = str(path or "").strip().strip('"')
        if chosen:
            inspected = self.inspect_advanced_component(key, chosen)
            if not inspected.get("ok"):
                return {"ok": False, "error": str(inspected.get("kind") or "inspect_failed"),
                        "text": str(inspected.get("text") or "这个文件不能用。")}
        with self._lock:
            if self._closing or self._advanced_busy or self._is_busy_locked():
                return {"ok": False, "text": "请等待当前操作结束后再安装。"}
            self._advanced_busy = True
        try:
            if chosen and str(inspected.get("kind")) == "cloudflared":
                # 单独一份 cloudflared：不进组件包体系，但同样要核版本与哈希
                with self._credential_lock, self._phone_access_lock:
                    if key == _advanced_features.PHONE_CONTROL and self._phone.is_running():
                        self.stop_phone_access()
                    try:
                        result = _component_packages.install_cloudflared(chosen)
                    except _component_packages.PackageError as exc:
                        code = str(exc.args[0] if exc.args else "install_failed")
                        return {"ok": False, "error": code,
                                "text": "这份 cloudflared 没有通过校验：%s" % code}
                    prefs = load_prefs()
                    enabled = dict(prefs.get("advanced_features") or {})
                    enabled[str(key)] = True
                    if not update_prefs({"advanced_features": enabled}):
                        return {"ok": False, "error": "prefs_busy",
                                "text": "cloudflared 已收好，但启用状态暂未保存；重新打开帮助再试。"}
                    self._cloudflare.executable = _tunnel_manager.resolve_cloudflared(
                        resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)
                    return result
            return self._install_selected_feature(key, chosen)
        finally:
            with self._lock:
                self._advanced_busy = False

    def _install_selected_feature(self, key: str, chosen: str = "") -> dict:
        """在已占住 _advanced_busy 的前提下真正安装。

        带 path 表示用户已经在对话框里选好文件；不带 path 是旧入口（打包版现场弹框）。
        """
        frozen = bool(getattr(sys, "frozen", False))
        archive = chosen or None
        if archive is None and frozen:
            if self._window is None:
                return {"ok": False, "text": "请在电脑窗口中导入组件。"}
            selected = self._window.create_file_dialog(
                webview.FileDialog.OPEN, allow_multiple=False,
                file_types=("组件包 (*.zip)",))
            if not selected:
                return {"ok": True, "canceled": True, "text": "已取消导入。"}
            archive = str(selected[0])
        if archive and not frozen:
            # 源码版跑的是仓库里的 Python 代码，组件包对它没有作用：
            # 与其「装完没变化」，不如直接说清该走哪条路
            return {"ok": False, "error": "source_build",
                    "text": "源码版用的是已装好的 Python 依赖，组件包对它不起作用；"
                            "Cloudflare 通道请改为选择 cloudflared.exe。"}
        with self._credential_lock, self._phone_access_lock:
            with self._lock:
                if self._closing:
                    return {"ok": False, "text": "程序正在关闭。"}
            if key == _advanced_features.PHONE_CONTROL and self._phone.is_running():
                self.stop_phone_access()
            if key == _advanced_features.RELOGIN_OCR:
                self._relay.cancel(origin="auto")
                self._auto_relogin.reset()
            result = _advanced_features.install_feature(
                key, frozen=frozen, root=DATA_DIR, archive=archive)
            if not result.get("ok"):
                return result
            prefs = load_prefs()
            enabled = dict(prefs.get("advanced_features") or {})
            enabled[str(key)] = True
            if not update_prefs({"advanced_features": enabled}):
                return {"ok": False, "error": "prefs_busy",
                        "text": "组件已安装，但启用状态暂未保存；重新打开帮助再试。"}
            self._cloudflare.executable = _tunnel_manager.resolve_cloudflared(
                resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)
            return result

    def remove_advanced_feature(self, key: str = "") -> dict:
        if not _advanced_features.allowed_feature(key):
            return {"ok": False, "text": "未知高级功能"}
        with self._credential_lock, self._phone_access_lock:
            with self._lock:
                if self._closing or self._advanced_busy:
                    return {"ok": False, "text": "请等待当前操作结束。"}
                self._advanced_busy = True
            try:
                if key == _advanced_features.PHONE_CONTROL:
                    self.stop_phone_access()
                else:
                    self._relay.cancel(origin="auto")
                    self._relay.clear_staged()
                    self._auto_relogin.reset()
                enabled = dict(load_prefs().get("advanced_features") or {})
                enabled[key] = False
                if not update_prefs({"advanced_features": enabled}):
                    return {"ok": False, "text": "停用状态未保存，请重试。"}
                if getattr(sys, "frozen", False):
                    if key == _advanced_features.PHONE_CONTROL:
                        # 走下载服务移除：它同时收拾 .part 残渣与「已安装」状态位
                        removed = self._component_service.remove()
                        if not removed.get("ok"):
                            return {"ok": False,
                                    "text": str(removed.get("text") or "组件文件未能移除，请关闭后重试。")}
                    else:
                        _component_packages.remove(key, root=DATA_DIR)
                self._cloudflare.executable = _tunnel_manager.resolve_cloudflared(
                    resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)
                return {"ok": True, "text": "功能已移除；已保存的账号可另行清除。"}
            except (OSError, ValueError):
                return {"ok": False, "text": "功能已停用，组件文件未能移除，请关闭后重试。"}
            finally:
                with self._lock:
                    self._advanced_busy = False

    def save_relogin_credentials(self, username: str = "", password: str = "") -> dict:
        """保存续登录用的账号密码（DPAPI 加密落盘）。

        只依赖「本机加密存储可用」：ddddocr 只决定能不能自动识别验证码，
        手机端人工输码的重登同样需要这份账号——两件事不再互相绑死。
        """
        user = str(username or "").strip()
        secret = str(password or "")
        if not user or not secret:
            return {"ok": False, "error": "needs_local_setup",
                    "text": "请输入账号和密码。"}
        if not _credential_store_available():
            return {"ok": False, "error": "store_unavailable",
                    "text": "本机加密存储不可用，暂时无法保存账号密码。"}
        try:
            with self._credential_lock:
                _credential_store.save(CREDENTIAL_FILE, user, secret)
                self._auto_relogin.reset()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": "credential_save_failed",
                    "text": "账号密码暂时没有保存：%s" % type(exc).__name__}
        return {"ok": True, "saved": True, "username": user}

    def clear_relogin_credentials(self) -> dict:
        with self._credential_lock:
            _credential_store.clear(CREDENTIAL_FILE)
            self._relay.clear_staged()
            self._relay.cancel(origin="auto")
            self._auto_relogin.reset()
        return {"ok": True, "saved": False}

    def _auto_relogin_eligible(self) -> bool:
        if DEMO or self._terms_gate() is not None:
            return False
        with self._lock:
            if (self._closing or self._advanced_busy or self._checking or self._listing
                    or self._relogin_blocked_locked()):
                return False
        return bool(_advanced_features.feature_ready(
            load_prefs(), _advanced_features.RELOGIN_OCR, root=DATA_DIR)
            and _credential_store.has_credentials(CREDENTIAL_FILE))

    def _relogin_blocked_locked(self) -> bool:
        """计划运行中什么时候不该自动登录（决策 015）。调用方持 self._lock。

        计划在等开放、报名进程还没起来：可以原地自动登录。报名进程在跑：只有它确认
        登录失效、发来 login_wait 时才登录，免得开抢中途把它手里的登录态顶掉。
        """
        if self._login_wait_pending:
            return False
        if self._proc and self._proc.poll() is None:
            return True
        return any(proc.poll() is None for proc in self._plan_procs.values())

    def _request_auto_relogin(self) -> None:
        """报名进程发来 login_wait：放行这一次计划运行中的自动登录，并让调度立即动手。"""
        with self._lock:
            self._login_wait_pending = True
        self._auto_relogin.request_recover()

    def _relogin_wait_s(self) -> float:
        """worker 确认登录失效后能等多久：电脑能自己登录（有账号密码、验证码识别已装）才等。"""
        if DEMO:
            return 0.0
        try:
            # 保存的密码被学校拒绝过：自动登录已暂停，报名进程等了也白等
            ready = bool(_advanced_features.feature_ready(
                load_prefs(), _advanced_features.RELOGIN_OCR, root=DATA_DIR)
                and _credential_store.has_credentials(CREDENTIAL_FILE)
                and not _credential_store.is_bad(CREDENTIAL_FILE))
        except Exception:
            return 0.0
        return RELOGIN_WAIT_S if ready else 0.0

    def _relogin_ocr_ready(self) -> bool:
        """电脑这边有没有「自己认验证码」的能力。"""
        return bool(_advanced_features.feature_ready(
            load_prefs(), _advanced_features.RELOGIN_OCR, root=DATA_DIR))

    def _manual_relogin_wanted(self, relay=None) -> bool:
        """验证码该不该交给手机上的人来打。

        电脑装了 OCR 就让它自己认：手机只看到「重试中」，两个人抢同一张图只会
        互相把对方顶掉。同一场连认 _MANUAL_RELOGIN_AFTER 次都不对、或整轮自动
        重登连续失败同样次数，说明机器解决不了，这时才把图推给手机。
        """
        if not self._relogin_ocr_ready():
            return True
        relay = self._relay.state() if relay is None else relay
        if relay.get("live") and relay.get("mode") in ("auto", "manual"):
            return relay["mode"] == "manual"
        # 只有这一场还在跑，attempts 才说明「电脑认了几次都没认对」；
        # 历史快照里的 attempts 是上一场残留，拿它判定会把手机永久锁进人工模式
        if relay.get("live") and int(relay.get("attempts") or 0) >= _MANUAL_RELOGIN_AFTER:
            return True
        failures = int(self._auto_relogin.snapshot().get("failures") or 0)
        return failures >= _MANUAL_RELOGIN_AFTER

    def _phone_relay_view(self) -> dict:
        """手机 /api/state 里的重登投影。

        机器还在认的时候，图和挑战号都不下发：手机看不到验证码就不会去提交，
        也就不会和电脑抢同一张图。mode/retrying/retry_in 让手机能显示「重试中」，
        而不是把「还没有图」误当成「重登已经结束」。
        """
        relay = dict(self._relay.state())
        auto = self._auto_relogin.snapshot()
        manual = self._manual_relogin_wanted(relay)
        state = str(relay.get("state") or "")
        retrying = bool(auto.get("inflight")) or state in ("starting", "verifying")
        if not manual:
            relay["image"] = ""
            relay["challenge_id"] = ""
        relay["mode"] = "manual" if manual else "auto"
        relay["retrying"] = retrying
        relay["retry_in"] = max(0, int(auto.get("retry_in") or 0))
        relay["auto_failures"] = max(0, int(auto.get("failures") or 0))
        # live 原样透传：手机端只有在本场真的还在跑时才播报「重登成功」
        relay["live"] = bool(relay.get("live"))
        return relay

    def _log_event(self, event: str, level: str = "INFO", **fields) -> None:
        """自动登录的关键动作落盘到 grab.log（行格式与 worker 同源，见 domain.log_events）。

        界面进程不 import grab（冻结主程序里没有它），所以这里自己追加一行；
        字段先过黑名单（不带账号、密码、验证码）。写失败至少打到 stderr，
        绝不影响登录流程本身。演示模式完全离线，不写。
        """
        if DEMO:
            return
        try:
            stamp = school_time_text(now_fn=self._clock_now)
        except Exception:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = "%s %s" % (stamp, _log_events.format_event_line(
            event, "auto_relogin", level=level, fields=fields))
        try:
            ensure_data_dir()
            with open(LOG_FILE, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception as exc:  # noqa: BLE001 - 日志写不进去不能拖垮登录
            if sys.stderr is not None:
                try:
                    print("[log] 写日志文件失败（%s）：%s" % (type(exc).__name__, line),
                          file=sys.stderr, flush=True)
                except Exception:
                    pass

    def _begin_auto_relogin(self) -> dict:
        """发起一轮自动登录，并把发起结果写进 grab.log（带耗时和失败分类，不带账号）。

        busy 是「现在不该登」（正在检查、计划在跑等），什么都没尝试，不落盘。
        """
        began = time.monotonic()
        result = self._begin_auto_relogin_once()
        if result.get("ok"):
            self._auto_relogin_started_at = began
            self._log_event("auto_relogin_started", elapsed_s=time.monotonic() - began)
        elif result.get("error") != "busy":
            self._log_event("auto_relogin_start_failed", level="WARN",
                            reason=str(result.get("error") or "unknown"),
                            elapsed_s=time.monotonic() - began)
        return result

    def _begin_auto_relogin_once(self) -> dict:
        with self._credential_lock:
            if _credential_store.is_bad(CREDENTIAL_FILE):
                return {"ok": False, "error": "bad_password"}
            if not self._auto_relogin_eligible():
                return {"ok": False, "error": "busy"}
            stored = {}
            try:
                stored = _credential_store.load(CREDENTIAL_FILE)
                result = self._relay.prepare(stored["username"], stored["password"])
                if not result.get("ok"):
                    return result
                with self._lock:
                    self._relay_creds_source = "saved"
                    self._pending_save = None
                manual = int(self._auto_relogin.snapshot().get("failures") or 0) >= _MANUAL_RELOGIN_AFTER
                return self._relay.begin(origin="auto", worker_command=worker_command("login"),
                                         manual=manual)
            except Exception:
                return {"ok": False, "error": "needs_local_setup"}
            finally:
                stored.clear()
                # 一次 login_wait 只放行一轮自动登录：发起过就收回（成败都一样）
                with self._lock:
                    self._login_wait_pending = False

    def _classify_captcha(self, image: str) -> str:
        prefs = load_prefs()
        if not _advanced_features.feature_ready(prefs, _advanced_features.RELOGIN_OCR, root=DATA_DIR):
            return ""
        return _advanced_features.classify_captcha(image, root=DATA_DIR)

    def front_ready(self) -> dict:
        # 仅排障：前端 boot 完成时打一声招呼，确认桥接真的通了
        self._trace("front_ready")
        return {"ok": True}

    def check_update(self, request_id: str) -> dict:
        """只登记轻量后台查询，不在桥接线程等待网络，也不改变报名门禁。"""
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
            return {"ok": False, "queued": False, "text": "更新请求无效，请重试。"}
        with self._lock:
            if self._closing:
                return {"ok": False, "queued": False, "text": "程序正在关闭。"}
            if self._updating:
                return {"ok": True, "queued": True, "skipped": True,
                        "request_id": self._update_request_id}
            self._updating = True
            self._update_request_id = request_id
        try:
            threading.Thread(target=self._do_check_update, args=(request_id,), daemon=True).start()
        except Exception:
            with self._lock:
                self._updating = False
            return {"ok": False, "queued": False, "text": "检查没能启动，请重试。"}
        return {"ok": True, "queued": True, "request_id": request_id}

    def _do_check_update(self, request_id: str) -> None:
        # 用例在 application.update_service；fetch 端口在此注入（测试按
        # app.check_latest_release 替换）。状态字段留在 Api 供界面重载对账。
        _update_service.run_check(self, request_id, fetch=check_latest_release,
                                  current_version=APP_VERSION,
                                  latest_url=RELEASES_LATEST_URL)

    def _publish_update(self, payload: dict, finished: bool) -> None:
        """把更新状态推给界面并留档；finished 才释放单飞槽位。"""
        with self._lock:
            self._update_result = payload
            if finished:
                self._updating = False
            closing = self._closing
        if not closing:
            self._emit("update", payload)

    def update_download(self, request_id: str) -> dict:
        """用户确认后启动安装器下载：单飞后台流式下载并校验，事件回推进度与结论。"""
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
            return {"ok": False, "queued": False, "text": "更新请求无效，请重试。"}
        with self._lock:
            if self._closing:
                return {"ok": False, "queued": False, "text": "程序正在关闭。"}
            if self._updating:
                return {"ok": True, "queued": True, "skipped": True,
                        "request_id": self._update_request_id}
            installer = self._update_installer
            if not isinstance(installer, dict) or not installer.get("url"):
                return {"ok": False, "queued": False,
                        "text": "当前没有可下载的安装包，请前往下载页。"}
            self._updating = True
            self._update_request_id = request_id
            self._update_cancelled = False
        try:
            threading.Thread(target=self._do_update_download,
                             args=(request_id, installer), daemon=True).start()
        except Exception:
            with self._lock:
                self._updating = False
            return {"ok": False, "queued": False, "text": "下载没能启动，请重试。"}
        return {"ok": True, "queued": True, "request_id": request_id}

    def _do_update_download(self, request_id: str, installer: dict) -> None:
        # 用例在 application.update_service；download/publish 端口在此注入
        # （updater 模块属性即替身缝）。进度/结论都经 _publish_update 推给界面。
        _update_service.run_download(
            self, request_id, installer,
            download=updater.download_installer, publish=self._publish_update,
            current_version=APP_VERSION, latest_url=RELEASES_LATEST_URL)

    def update_cancel(self) -> dict:
        """用户取消下载：只置取消标记，下载线程在下一块之间停下并清理半成品。"""
        with self._lock:
            self._update_cancelled = True
        return {"ok": True}

    def update_launch(self, request_id: str) -> dict:
        """用户确认后启动已校验的安装器；启动前先回推 launching 状态。

        关闭主程序由调用方控制：这里不退出、不自动重启，失败不改会话和偏好。
        """
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
            return {"ok": False, "text": "更新请求无效，请重试。"}
        with self._lock:
            if self._closing:
                return {"ok": False, "text": "程序正在关闭。"}
            path = self._update_installer_path
            base = dict(self._update_result or {})
        if not path:
            return {"ok": False, "text": "还没有已校验的安装包，请先下载。"}
        # 安装器启动前先回推状态：界面能看到「正在启动安装程序…」
        self._publish_update(dict(base, request_id=request_id, state="launching",
                                  text="正在启动安装程序…", installer_path=path,
                                  error_code=""), False)
        got = updater.launch_installer(path)
        if got.get("ok"):
            text = "安装程序已启动。请先关闭本工具，再按向导完成安装。"
            self._publish_update(dict(base, request_id=request_id, state="launching",
                                      text=text, installer_path=path, error_code=""), False)
            return {"ok": True, "path": path, "text": text}
        text = str(got.get("text") or "安装程序没能启动，请重试。")
        self._publish_update(dict(base, request_id=request_id, state="failed",
                                  text=text, installer_path=path,
                                  error_code=str(got.get("error_code") or "launch_failed")), False)
        return {"ok": False, "text": text}


    def check(self, request_id: str = "") -> dict:
        # js_api 的处理跑在 UI 线程上：一旦在这里跑 subprocess，
        # 窗口会直接"未响应"。所以只负责起线程，结果用事件推回去。
        # 条款门禁：登录态校验要访问学校接口，未获授权就不起线程（后端最终防线）
        gate = self._terms_gate(request_id)
        if gate is not None:
            return dict(gate, queued=False)
        with self._lock:
            if self._closing:
                # 关闭拒绝是取消语义：不给组件码，不再起线程
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "程序正在关闭，已取消本次检查"}
            if self._checking:
                # 去重必须带上在途请求 ID：界面按 ID 对账，不能把旧轮当新轮
                # 但这一轮的真实意图不能丢：记下来，等本轮收尾再补查一次
                self._check_again = True
                answer = {"ok": True, "queued": True, "skipped": "已在检查登录态",
                          "request_id": self._check_request_id}
                last = self._check_last
                if last.get("payload") and last.get("request_id") == self._check_request_id:
                    # 原操作刚好已经结束：把终态直接带回去，界面不用干等
                    answer["result"] = last["payload"]
                return answer
            self._checking = True
            self._check_request_id = request_id or ""
        threading.Thread(target=self._do_check, daemon=True).start()
        return {"ok": True, "queued": True, "request_id": request_id}

    def list_activities(self, request_id: str = "") -> dict:
        # 条款门禁同上：活动列表来自学校接口，未获授权不拉列表
        gate = self._terms_gate(request_id)
        if gate is not None:
            return dict(gate, queued=False)
        with self._lock:
            if self._closing:
                return {"ok": False, "queued": False, "request_id": request_id,
                        "text": "程序正在关闭，已取消拉取活动列表"}
            if self._listing:
                answer = {"ok": True, "queued": True, "skipped": "已经在拉活动列表",
                          "request_id": self._list_request_id}
                last = self._list_last
                if last.get("payload") and last.get("request_id") == self._list_request_id:
                    answer["result"] = last["payload"]
                return answer
            self._listing = True
            self._list_request_id = request_id or ""
        threading.Thread(target=self._do_list, daemon=True).start()
        return {"ok": True, "queued": True, "request_id": request_id}

    def _do_check(self) -> None:
        try:
            self._do_check_inner()
        except Exception as exc:  # noqa: BLE001 - 兜底：结论构造中的意外也必须收尾
            # FB3：任何 check 终态必须先同步后端判定——结论构造阶段的意外不能
            # 让旧 valid 留作 start_plan 放行依据。先在锁内写 unknown/当前时刻
            # 并清旧组件结论，再锁外发唯一终态（状态写入先于事件）
            with self._lock:
                self._last_check = {"result": "unknown", "checked_at": time.time(),
                                    "runtime_error": ""}
            self._emit("check", {"ok": False, "result": "unknown",
                                 "text": "检查登录态没跑完，请点「刷新」再试一次"})
            self._emit("log", "[X] 检查收尾异常 %s: %s" % (type(exc).__name__, exc))
        finally:
            with self._lock:
                self._checking = False
                conclusion = self._last_check.get("result", "unknown")
                # 去重期间有人要求过再查：只补这一次，且立刻重新占住去重槽位，
                # 避免补查的线程还没起来就被第三次点击当成「空闲」再起一个
                again = self._check_again and not self._closing
                self._check_again = False
                if again:
                    self._checking = True
            self._auto_relogin.observe_check(conclusion)
            self._note_login_conclusion(conclusion)
            if again:
                threading.Thread(target=self._do_check, daemon=True).start()

    def _note_login_conclusion(self, conclusion: str) -> None:
        """记下登录结论的变化：本次运行里有效过、之后变成失效，推一次飞书。"""
        with self._lock:
            if conclusion == "valid":
                self._login_seen_valid = True
                self._expiry_pushed = False
                return
            if conclusion != "expired" or not self._login_seen_valid or self._expiry_pushed:
                return
            self._expiry_pushed = True
        self._push_login_expired()

    def _push_login_expired(self) -> None:
        """配了飞书机器人才推；消息只说失效和怎么办，不带账号。在后台线程里发，不拖界面。"""
        if DEMO:
            return
        hook = _feishu_webhook()
        if not hook:
            return
        card = {
            "config": {"wide_screen_mode": True},
            "header": {"template": "orange",
                       "title": {"tag": "plain_text", "content": "登录已失效"}},
            "elements": [{"tag": "div", "text": {
                "tag": "lark_md", "content": "登录已失效，回电脑或手机上重新登录。"}}],
        }
        body = json.dumps({"msg_type": "interactive", "card": card},
                          ensure_ascii=False).encode("utf-8")

        def send() -> None:
            import urllib.request

            request = urllib.request.Request(hook, data=body,
                                             headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    response.read(4096)
                self._emit("log", "登录失效已推送到飞书")
            except Exception as exc:  # noqa: BLE001 - 推送失败只记类别，不影响登录流程
                self._emit("log", "飞书推送失败：%s" % type(exc).__name__)

        threading.Thread(target=send, name="feishu-login-expired", daemon=True).start()

    def _do_check_inner(self) -> None:
        if DEMO:
            # 演示模式完全离线：不读 session.json/storage_state、不起 worker、
            # 不碰学校。状态明确写「演示模式」，绝不伪装成真实登录有效（R20）
            self._last_check = {"result": "demo", "checked_at": time.time(),
                                "runtime_error": ""}
            self._emit("check", {
                "ok": True, "result": "demo", "demo": True,
                "text": "演示模式：使用内存样例，不检查真实登录",
                "hours_left": None, "session_present": None,
                "session_expired": False, "saved_at": None,
                "estimated_expires_at": None, "reason": "", "hint": "",
                "clock": {"source": "http_date", "state": "unknown",
                          "checked_at": None, "offset_s": None,
                          "uncertainty_s": None, "rtt_s": None,
                          "detail": "演示模式不做校时"},
            })
            return
        err_code = ""
        try:
            res = self._run(worker_command("check"), timeout=90)
            code, out = res["code"], res["out"]
        except _ClosingError:
            # 关闭取消：仍给恰一次终态，但属取消语义——不归类组件码、
            # 不触碰登录四态字段，技术细节没有需要落日志的内容
            self._emit("check", {"ok": False, "result": "unknown",
                                 "text": "程序正在关闭，本次检查已取消"})
            return
        except OSError as exc:
            # 进程创建失败（缺文件/权限/其他 OS 层）才归组件码：与登录四态分离，
            # 一律 unknown + runtime_error 附加字段——不清会话、不指导重登
            err_code = _component_error(exc)
            code = -1
            out = "[X] %s" % WORKER_PROBLEM_TEXT.get(err_code, "程序组件启动失败，请重新下载完整版本")
            # 技术细节只进运行记录（日志），主文案保持人话
            self._emit("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
        except Exception as exc:
            # 数据/解析等普通异常：仍是检查失败终态，但不设 runtime_error、
            # 不诱导重新下载——数据坏了不是组件坏了
            code = -1
            out = "[X] 检查登录态没跑完，请点「刷新」再试一次"
            self._emit("log", "[X] 检查登录态异常 %s: %s" % (type(exc).__name__, exc))
        # 事件载荷整理在 application.login_service（分类纯规则在 domain）：
        # 归因只信第一条 [X] 来源行；三态字段跟结果一起发，粗校时逐轮替换（R08）。
        state = login_state(self._clock)
        result, clock, payload = _login_service.build_check_event(
            state, code, out, err_code)
        self._last_check = {"result": result, "checked_at": time.time(),
                            "runtime_error": err_code}
        # 上次校验时刻随 check 事件一起给界面（与 bootstrap.login 同一口径），胶囊和登录卡据此显示
        payload = dict(payload, **_last_check_fields(self._last_check))
        self._emit("check", payload)

    def _do_list(self) -> None:
        try:
            self._do_list_inner()
        except _ClosingError:
            # 关闭取消：恰一次失败终态收尾（骨架必能结束），但属取消语义，
            # 不归类组件码、不诱导重下/重检
            self._emit("activities", {"ok": False,
                                      "text": "程序正在关闭，活动列表加载已取消",
                                      "items": []})
        except OSError as exc:
            # 进程创建失败（缺文件/权限/其他 OS 层）才归组件码——此前任意
            # Exception 都会被归成 spawn_failed，数据异常被误报成「重新下载」
            err_code = _component_error(exc)
            self._emit("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
            self._emit("activities", {"ok": False,
                                      "text": WORKER_PROBLEM_TEXT.get(err_code, "活动列表没能加载"),
                                      "items": [], "runtime_error": err_code})
        except Exception as exc:
            # 数据/解析等普通异常：仍必给恰一次失败终态（此前 FileNotFoundError
            # 从这里泄出导致骨架永远加载），但不是组件问题——不设 runtime_error、
            # 不诱导重新下载或重新登录
            self._emit("log", "[X] 列表请求异常 %s: %s" % (type(exc).__name__, exc))
            self._emit("activities", {"ok": False, "text": "活动列表没能加载", "items": []})
        finally:
            with self._lock:
                self._listing = False

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
        """列表刷新结果与本地已确认成功合并（纯策略在 domain.plan_rules）。

        学校说已报名 → 权威；本地已确认成功但学校还没同步 → 窗口内保留
        signed=true 并标 sync_pending，让界面继续把这场留在「已报名」而不可再选。
        """
        try:
            now = float(self._clock_now())
        except Exception:
            now = None            # 没有可信现在：保留本地确认，不按系统时间算窗口
        return _plan_rules.merge_list_activities(
            items, self._activities, now, self.SIGNED_SYNC_WINDOW_S)

    def _do_list_inner(self) -> None:
        if DEMO:
            items = demo_items()
            self._activities = {str(it["id"]): it for it in items}
            self._emit("activities", {"ok": True, "items": items})
            return
        started = time.monotonic()   # 总用时含 worker 启动；联网段由 [timing] 单独给
        res = self._run(worker_command("list", "--json"), timeout=120)
        elapsed = time.monotonic() - started
        if res["code"] != 0:
            self._emit("activities", {"ok": False,
                                      "text": res["out"].strip(), "items": []})
            return
        try:
            # stderr 可能混有辅助日志，列表 JSON 只认 stdout；
            # 测试里伪造的 _run 没有 stdout 键时退回旧的 out，行为不变
            raw = res.get("stdout", res["out"])
            items = json.loads(raw.strip() or "[]")
        except json.JSONDecodeError:
            self._emit("activities", {"ok": False,
                                      "text": "活动列表解析失败", "items": []})
            return
        # 用时只进运行记录，不进 activities 载荷：stderr 里只认 [timing] 那一行
        timing_text = "活动列表用时 %.1f 秒" % elapsed
        try:
            for line in (res.get("stderr") or "").splitlines():
                if not line.startswith("[timing] list "):
                    continue
                fields = {}
                for part in line[len("[timing] list "):].split():
                    if "=" in part:
                        key, value = part.split("=", 1)
                        fields[key] = value
                total_s = float(fields["total_s"])
                timing_text = (
                    "活动列表用时 %.1f 秒：程序启动约 %.1f 秒，联网约 %.1f 秒"
                    "（列表约 %d 页，补详情 %d 场）"
                    % (elapsed, max(0.0, elapsed - total_s), total_s,
                       int(fields.get("pages", 0)),
                       int(fields.get("details", 0))))
                break
        except Exception:
            timing_text = "活动列表用时 %.1f 秒" % elapsed
        self._emit("log", timing_text)
        now = None
        try:
            now = self._clock_now()      # 列表「距开放」按业务北京时间
        except Exception:
            now = None                   # 校时不可用：显示未知，不用系统时间补
        # 报名成功后学校列表可能短暂滞后：合并本地已确认成功，再下发界面和缓存。
        # 合并只读本地缓存、不联网，也不改写学校返回的其它字段。
        items = self._merge_list_activities(items)
        for it in items:
            it["seconds_to_open"] = _seconds_until(it.get("sign_start"), now)
        with self._lock:
            self._activities = {str(it.get("id")): dict(it) for it in items if it.get("id")}
        # 详情补充是逐活动异步完成的：把「还在同步/已失败」如实交给界面，
        # 不让整张列表因为某一场详情查不到而失败。
        pending = sum(1 for it in items if it.get("attendance_state") == "pending")
        failed = sum(1 for it in items if it.get("attendance_state") == "unknown")
        self._emit("activities", {"ok": True, "items": items,
                                  "attendance": {"pending": pending, "unknown": failed}})

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
        """已完成计划登记只留最近有限条（调用方持锁）。"""
        if len(self._finished_plan_ids) <= self.FINISHED_PLAN_KEEP:
            return
        for plan_id in list(self._finished_plan_ids)[:-self.FINISHED_PLAN_KEEP]:
            self._finished_plan_ids.pop(plan_id, None)

    def _remember_start(self, request_id: str, state: str, **extra) -> None:
        """登记开始请求的结论（调用方持锁）。只保留最近 32 条，pending 不驱逐。"""
        record = dict(self._start_requests.get(request_id) or {})
        record.update({"state": state, "at": record.get("at") or time.time()})
        record.update(extra)
        self._start_requests[request_id] = record
        if request_id in self._start_order:
            self._start_order.remove(request_id)
        self._start_order.append(request_id)
        while len(self._start_order) > self.START_KEEP:
            victim = next((rid for rid in self._start_order
                           if self._start_requests.get(rid, {}).get("state") != "pending"), None)
            if victim is None:
                break
            self._start_order.remove(victim)
            self._start_requests.pop(victim, None)

    def _start_replay(self, record: dict, request_id: str) -> dict:
        """同一 request_id 重放：返回原结论，绝不另建计划。"""
        state = record.get("state")
        if state in {"accepted", "rejected"}:
            return dict(record.get("result") or {}, request_id=request_id, duplicate=True)
        if state == "canceled":
            return {"ok": False, "text": "这次开始已取消，可以重新发起。",
                    "request_id": request_id, "canceled": True}
        return {"ok": True, "queued": True, "pending": True, "request_id": request_id,
                "text": "正在确认是否启动，请稍候"}

    def start_request_state(self, request_id: str) -> dict:
        """只读对账：这次开始到底是 pending / accepted / rejected / canceled。"""
        rid = str(request_id or "")
        with self._lock:
            record = self._start_requests.get(rid)
            if record is None and rid in getattr(self, "_canceled_start_ids", set()):
                record = {"state": "canceled"}
            plan = self._plan
            # 代次只在该请求的计划仍是最近接纳计划时给出：对旧请求对账不得
            # 伪造成最新接纳代次（P1）
            generation = (self._plan_generation
                          if str(record.get("plan_id") or "") == self._latest_plan_id
                          else 0) if record else 0
        if not record:
            return {"ok": True, "state": "unknown", "request_id": rid,
                    "text": "没有这次开始的记录，可能程序重启过"}
        state = str(record.get("state") or "unknown")
        plan_id = str(record.get("plan_id") or "")
        payload = {"ok": True, "state": state, "plan_id": plan_id, "request_id": rid,
                   "plan_generation": generation}
        if state == "accepted":
            if plan is not None and plan.plan_id == plan_id:
                snapshot = plan.snapshot()
                payload["running"] = snapshot.get("status") in {"ready", "running"}
                payload["snapshot"] = snapshot
            else:
                # 计划已经收尾：返回这次请求自己的终态快照，不借别的较新计划
                payload["running"] = False
                payload["finished"] = True
                payload["snapshot"] = record.get("snapshot") or {
                    "status": record.get("final_status") or "unknown",
                    "summary": {}, "tasks": []}
            payload["status"] = (payload.get("snapshot") or {}).get("status")
        else:
            payload["text"] = str((record.get("result") or {}).get("text") or "")
        return payload

    def cancel_start_request(self, request_id: str) -> dict:
        """放弃待确认的开始；未知 ID 先登记取消，拦住网络中迟到的原请求。"""
        rid = str(request_id or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            return {"ok": False, "text": "开始请求标识无效，请重试。"}
        with self._lock:
            record = self._start_requests.get(rid)
            canceled_ids = self.__dict__.setdefault("_canceled_start_ids", set())
            if rid in canceled_ids:
                return {"ok": True, "state": "canceled", "request_id": rid}
            if (not record or record.get("state") == "pending") and len(canceled_ids) >= 1024:
                return {"ok": False, "error": "cancel_capacity",
                        "text": "取消记录已满，请等待本次对账结果。"}
            if not record:
                canceled_ids.add(rid)
                self._remember_start(rid, "canceled")
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "canceled":
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "pending":
                canceled_ids.add(rid)
                record["state"] = "canceled"
                return {"ok": True, "state": "canceled", "request_id": rid}
            if record.get("state") == "accepted":
                # 已被接纳就不能再答复「取消成功」：给出真实 plan_id 让界面去停止
                return {"ok": False, "state": "accepted",
                        "plan_id": str(record.get("plan_id") or ""),
                        "request_id": rid,
                        "text": "这次开始已经被接纳，请用「停止计划」结束"}
            return {"ok": False, "state": record.get("state"),
                    "text": "这次开始已经有结论，不能再取消"}

    def start_plan(self, items: list[dict], headed: bool = False,
                   retry_policy: dict | None = None, request_id: str = "",
                   source: str = "desktop") -> dict:
        """校验并启动计划；带 request_id 时按进程内登记实现幂等（R11）。

        UI 的超时不能靠「清掉正在提交」来放行第二次开始——那可能真的重复报名。
        这里按 request_id 记住接纳/拒绝结论：同 ID 再来返回原结论，
        另提供只读对账与取消接纳，让界面能问清楚「到底启没启」。
        """
        rid = request_id if isinstance(request_id, str) else ""
        if rid and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", rid):
            return {"ok": False, "text": "开始请求标识无效，请重试。"}
        if rid:
            # 查重与占位必须在同一临界区：分成两段锁会让两个同 ID 请求
            # 都读到「不存在」，然后各自去建计划（C04）
            with self._lock:
                known = self._start_requests.get(rid)
                if rid in getattr(self, "_canceled_start_ids", set()):
                    known = {"state": "canceled"}
                if known is not None:
                    replay = self._start_replay(known, rid)
                else:
                    self._remember_start(rid, "pending")
                    replay = None
            if replay is not None:
                return replay
        # 条款门禁放在「幂等重放之后、真正建计划之前」：已接纳/已拒绝的
        # 结论照旧重放，新的请求未获授权则立即把本次登记收成 rejected，
        # 既不留下悬空 pending，也不启动计划协调器与任何 worker。
        gate = self._terms_gate()
        if gate is not None:
            rejected = dict(gate)
            if rid:
                rejected["request_id"] = rid
                with self._lock:
                    record = self._start_requests.get(rid) or {}
                    if record.get("state") == "pending":
                        self._remember_start(rid, "rejected", result=rejected)
            return rejected
        # 来源只认两个值：手机端由 phone_service 在服务端补上，界面传别的一律当电脑
        with self._lock:
            self._next_plan_source = "phone" if source == "phone" else "desktop"
        try:
            result = self._start_plan_inner(items, headed, retry_policy, rid)
        except Exception as exc:  # noqa: BLE001 - 本机异常也要留下真实结论
            with self._lock:
                record = self._start_requests.get(rid) or {}
                if rid and record.get("state") not in {"accepted", "canceled"}:
                    self._remember_start(rid, "rejected",
                                         result={"ok": False,
                                                 "text": "开始计划时本机异常：%s"
                                                         % type(exc).__name__})
            return {"ok": False, "text": "开始计划时本机异常：%s" % type(exc).__name__,
                    "request_id": rid}
        if rid:
            with self._lock:
                record = self._start_requests.get(rid) or {}
                state = record.get("state")
                if state == "canceled":
                    # 取消先赢：如实返回取消，不把结论覆盖成 accepted/rejected
                    result = {"ok": False, "text": "这次开始已取消，可以重新发起。",
                              "canceled": True}
                elif state == "accepted":
                    # inner 已在线性化点写过接纳结论，外层不得覆盖
                    result = dict(record.get("result") or result)
                else:
                    self._remember_start(
                        rid, "accepted" if result.get("ok") else "rejected",
                        plan_id=str(result.get("plan_id") or ""), result=dict(result))
        return dict(result, request_id=rid) if rid else result

    def _start_plan_inner(self, items: list[dict], headed: bool,
                          retry_policy: dict | None, request_id: str = "") -> dict:
        with self._lock:
            plan_source = getattr(self, "_next_plan_source", "desktop")
            self._next_plan_source = "desktop"
        if not isinstance(items, list) or not items:
            return {"ok": False, "text": "先至少选择一场活动"}
        # 北京时间门禁（决策 012）：时钟不可用时不新启自动报名（demo 离线豁免）；
        # 计划接纳时刻只取一次业务 now——开始后的校时/鉴权/开页不后移 instant 窗口
        if not DEMO and not self._clock_ready():
            return {"ok": False,
                    "text": "北京时间还没有校准，暂不能开始自动报名；稍后点「重新校时」再试。"}
        accepted_at = self._clock_now()
        with self._lock:
            if self._closing:
                return {"ok": False, "text": "程序正在关闭，已取消开始计划"}
            if not DEMO and not self._clock_ready():
                return {"ok": False,
                        "text": "北京时间在开始前失去校准，这次没有启动；稍后重试。"}
            if self._is_busy_locked():
                return {"ok": False, "text": "已有登录、报名或计划在运行，先停止后再开始"}
        # 真实计划只在学校接口确认登录有效后开始（最终防线，界面按钮门禁之外）：
        # checking / unknown / none / expired 一律拒绝并给出下一步；demo 没有真实
        # 登录态，继续走演示流程不受此限。
        if not DEMO:
            problem = worker_problem()
            if problem:
                # 组件不齐的计划必然全场失败：这里就拒绝，不让用户等到点才发现；
                # demo 模式不起 worker，不做此检查
                return {"ok": False,
                        "text": "%s；计划没法开始" % WORKER_PROBLEM_TEXT[problem],
                        "error": problem}
            with self._lock:
                checking = self._checking
                last = dict(self._last_check)
            if checking:
                return {"ok": False, "text": "正在检查登录态，等这次检查完成再开始"}
            result = last.get("result") or "unknown"
            if result == "valid":
                pass                     # 学校接口确认有效：唯一放行形态
            elif result == "none":
                return {"ok": False, "text": "还没有登录：打开顶栏的登录状态，点「登录」先登录一次"}
            elif result == "expired":
                return {"ok": False, "text": "登录态已失效：打开顶栏的登录状态，点「重新登录」后再开始"}
            else:
                return {"ok": False,
                        "text": "暂时无法确认登录态：点「刷新」重试，确认登录有效后再开始"}

        policy = retry_policy if isinstance(retry_policy, dict) else {}
        # 三种模式：正数=硬时长，0=直到截止，-1=自动延长（最多25分钟）；
        # 其他负值/非法值回 120，不猜用户意图
        retry_for_s = _retry_rules.policy_int(policy.get("retry_for_s"), 120,
                                              minimum=_retry_rules.ADAPTIVE_RETRY)
        max_attempts = _retry_rules.policy_int(policy.get("max_attempts"), 0)

        # 计划项归一化/门禁的纯策略在 domain.plan_rules：前端只提交「选了哪
        # 一场」，资格与时间一律以本进程缓存为准（R05）；不合格整单拒绝。
        normalized, error = _plan_rules.normalize_plan_items(
            items, self._activities, accepted_at)
        if error is not None:
            return error
        # 模式分类/冲突校验的纯函数在此注入 signup_plan（domain 不直连）
        error = _plan_rules.closed_items_error(
            normalized, accepted_at, classify_signup_mode)
        if error is not None:
            return error
        # 已报名活动占用的举办时段也是冲突基线：学校列表 signed=true 的全量活动
        # 与本次选择按 act_start/act_end 比较。缓存读取加锁：worker 线程可能正在
        # 回写报名结果（dict 迭代中变更会抛 RuntimeError）。
        with self._lock:
            signed_baseline = [dict(item) for item in self._activities.values()
                               if item.get("signed")]
        checked = _plan_rules.check_conflicts(
            normalized, accepted_at, signed_baseline, validate_plan)
        if not checked["ok"]:
            return checked

        plan_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._plan_sources[plan_id] = plan_source
            # 只留最近几份：页面重载、手机快照只会问到最近的计划
            for stale in list(self._plan_sources)[:-16]:
                self._plan_sources.pop(stale, None)
        specs = [TaskSpec.from_activity(item, "task-%02d-%s" % (i + 1, item["id"]), headed,
                                        retry_for_s=retry_for_s, max_attempts=max_attempts,
                                        now=accepted_at)
                 for i, item in enumerate(normalized)]

        # 接纳代次在下方最终接纳的同一临界区赋值；emit 闭包捕获自己的代次，
        # 事件与终态快照的归属都按代次判定，不以 _plan 槽为空推断（P1）
        accepted_generation = [0]

        def annotated(payload: dict) -> dict:
            """内部桥接事件统一携带 plan_id/plan_generation/request_id（P1）。"""
            data = dict(payload) if isinstance(payload, dict) else {}
            data.setdefault("plan_id", plan_id)
            data["plan_generation"] = accepted_generation[0]
            data["source"] = plan_source
            if "request_id" not in data:
                rid = next((key for key, value in self._start_requests.items()
                            if value.get("plan_id") == plan_id), "")
                if rid:
                    data["request_id"] = rid
            return data

        def emit(kind: str, payload: dict) -> None:
            # 报名结果先回写活动缓存，再转发事件：界面收到 task/plan_done 时，
            # 后端立场（下一次开始会不会重新接纳这场）已经同步更新。
            if kind == "task" and isinstance(payload, dict):
                status = str(payload.get("status") or "")
                if status in {"success", "already_signed"}:
                    self._confirm_signed(str(payload.get("activity_id") or ""), status)
            if kind != "plan_done":
                # 旧计划迟到的进度事件不得广播到当前界面：事件只属于最近
                # 接纳的计划；历史计划的进度仍可按 request_id 只读对账（P1）
                with self._lock:
                    is_latest = self._latest_plan_id == plan_id
                    forward = annotated(payload) if is_latest else None
                if is_latest:
                    self._emit(kind, forward)
                return
            # 完成状态先提交、再发布：收到 plan_done 的同步回调（测试、未完成的
            # bootstrap、开始对账）必须当场就看到 _plan 已清空、终态快照与
            # request_id 记录已可读；先发事件再改状态会留下可观察的中间态（FR05）。
            # 快照在 Api 锁外取：协调器锁只在它自己内部持有，反向边不再成环（P2-1）。
            # plan_done 发出时所有任务已终态，这里的快照就是终态快照。
            try:
                snapshot = coordinator.snapshot()
            except Exception:
                snapshot = None
            with self._lock:
                owns_slot = self._plan is coordinator
                if owns_slot:
                    self._plan = None
                elif (self._plan is None
                      and self._latest_plan_id == plan_id):
                    # 关闭/停止已把当前计划清空：只有「这就是最近接纳的计划」
                    # 时才算它的收尾。槽为空≠归属——较新计划已结束后，旧计划
                    # 的迟到完成不得覆盖它的终态快照（P1）
                    owns_slot = True
                first_done = not self._finished_plan_ids.get(plan_id)
                if owns_slot and first_done:
                    # 终态快照只写一次：重复终态不得把已定结论改成另一状态；
                    # 旧计划迟到的 plan_done 不得覆盖后来计划或它的终态快照
                    self._finished_plan_ids[plan_id] = True
                    self._prune_finished_plans_locked()
                    self._last_plan = snapshot
                if first_done:
                    # 终态快照按 request_id 留档：ack 丢了也要能核实「已经结束」（C05）
                    rid = next((key for key, value in self._start_requests.items()
                                if value.get("plan_id") == plan_id), "")
                    if rid:
                        final_status = str(payload.get("status")
                                           or (snapshot or {}).get("status") or "")
                        self._remember_start(
                            rid, "accepted", plan_id=plan_id, finished=True,
                            final_status=final_status,
                            snapshot={"status": final_status,
                                      "summary": payload.get("summary") or {},
                                      "tasks": (snapshot or {}).get("tasks") or []})
                forward_done = self._latest_plan_id == plan_id
                forward_payload = annotated(payload) if forward_done else None
            # 先提交后发布（顺序保留，FR05）；旧计划的完成事件不广播（P1）
            if forward_done:
                self._emit("plan_done", forward_payload)
                self._notify_plan_done(snapshot)

        def runner(spec: TaskSpec, cancel_event: threading.Event,
                   status: callable) -> dict:
            if DEMO:
                # demo 只演示任务状态，不创建 grab.py 子进程，也不访问学校站点。
                status("submitting", {"detail": "演示：正在提交"})
                for _ in range(4):
                    if cancel_event.is_set():
                        return {"status": "canceled", "reason": "用户取消了这一场"}
                    time.sleep(0.05)
                if spec.activity_id.endswith("career"):
                    return {"status": "failed", "code": 2, "reason": "演示：名额已满"}
                return {"status": "success", "code": 0, "reason": "演示：报名成功"}
            try:
                return self._run_plan_task(spec, cancel_event, status)
            except _SpawnFailure as exc:
                # 没拿到进程树所有权就不会有网络或浏览器动作：这一场如实记成
                # 「本机没能启动」，既不冒充学校拒绝，也不静默降级成无主进程。
                return {"status": "failed", "code": None,
                        "reason": "本场没能启动：%s" % exc,
                        "stop_reason": "spawn_failed", "attempts": 0}
            except _ClosingError:
                # 关闭拒绝落到协调器里就是取消：不冒充报名失败，也不让异常
                # 冲出 runner 污染任务状态（协调器业务不改）
                return {"status": "canceled", "code": None,
                        "reason": "程序正在关闭，本场次未启动"}

        coordinator = PlanCoordinator(plan_id, specs, runner, emit,
                                      now=self._clock_now)
        with self._lock:
            # FB1 最终接纳点：从开头的 busy 检查到这里隔着校验与构建，期间
            # 可能已有别的请求预留计划、或关闭已开始——同一临界区内重检并
            # 只允许一个请求预留唯一协调器，未接纳的请求不启动、不覆盖
            if self._closing:
                return {"ok": False, "text": "程序正在关闭，已取消开始计划"}
            if not DEMO and not self._clock_ready():
                return {"ok": False,
                        "text": "北京时间在开始前失去校准，这次没有启动；稍后重试。"}
            if self._is_busy_locked():
                return {"ok": False, "text": "已有登录、报名或计划在运行，先停止后再开始"}
            # 取消接纳与最终预留同一临界区：pending 期间点了取消，
            # 这里必须拒绝，绝不能先占位再补一个「已取消」的计划
            if request_id and self._start_requests.get(request_id, {}).get("state") == "canceled":
                return {"ok": False, "text": "这次开始已取消，可以重新发起。",
                        "canceled": True}
            self._plan = coordinator
            self._last_plan = None
            # 接纳代次与最近接纳计划在同一临界区赋值：此后所有事件/快照的
            # 归属判定都以这一线性化点为基准（P1）
            self._plan_generation += 1
            accepted_generation[0] = self._plan_generation
            self._latest_plan_id = plan_id
            if request_id:
                # 接纳与预留同一线性化点：此后取消只能回报真实 plan_id（C04）
                self._remember_start(request_id, "accepted", plan_id=plan_id,
                                     result={"ok": True, "queued": True,
                                             "plan_id": plan_id})
        try:
            # start 在 Api 锁外：协调器启动会 emit 回调（plan 事件要拿 _lock），
            # 锁内调用会双向等死
            coordinator.start()
        except Exception:
            # 启动失败只撤销本请求仍持有的预留，不碰别的计划，不残留 busy
            with self._lock:
                if self._plan is coordinator:
                    self._plan = None
                if request_id:
                    self._remember_start(request_id, "rejected", plan_id="",
                                         result={"ok": False,
                                                 "text": "计划没能开始，请再试一次"})
            return {"ok": False, "text": "计划没能开始，请再试一次"}
        return {"ok": True, "queued": True, "plan_id": plan_id,
                "plan_generation": accepted_generation[0]}

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
        """立刻按进程树终止计划里所有活着的 worker。"""
        with self._lock:
            procs = list(self._plan_procs.values())
        for proc in procs:
            _kill_tree(proc)

    def plan_active_for_close(self) -> bool:
        """计划在跑或已就绪：关窗必须先问，不能静默最小化/退出。"""
        plan = getattr(self, "_plan", None)
        if plan is None:
            return False
        try:
            return plan.published_status() in {"running", "ready"}
        except Exception:
            return False

    def ask_window_close(self) -> dict:
        """把「要关了，你想怎样」推给界面去选；返回本次判定依据。

        tray_ok / phone_running / phone_live 让对话框先列出正在运行的东西，并说清
        「隐藏到后台」能不能用：托盘建不起来、手机又没连时隐藏就叫不回来（与 hide_window 同一道门）。
        """
        plan_running = self.plan_active_for_close()
        action = resolve_close_action(load_prefs(), plan_running)
        try:
            tray_ok = bool(self._ensure_tray())
        except Exception:
            tray_ok = False
        try:
            phone_running = bool(self._phone.is_running())
            phone_live = bool(self._phone.has_live_session())
        except Exception:
            phone_running = phone_live = False
        payload = {"plan_running": plan_running, "default_action": action,
                   "tray_ok": tray_ok, "phone_running": phone_running, "phone_live": phone_live}
        self._emit("window_close_ask", payload)
        return dict(payload, ok=True)

    def request_window_close(self, action: str = "") -> dict:
        """界面四选的结果：hide 藏到后台 / minimize / exit / 先不关，remember_ 表示「以后都这样」。

        只认这几个词；记住的选择写进 ui.json 的 window.close_action，
        下次点 X 直接照做（计划在跑时仍会先问）。

        hide 是唯一「先做再记」的选项：这条出口有门禁（托盘或手机访问必须至少
        通一条），门禁没过就不能把「以后都隐藏」写进偏好——否则下次点 X 会直接
        走到一条走不通的路上，而用户根本没成功隐藏过。
        """
        action = str(action or "")
        allowed = ("hide", "minimize", "exit",
                   "remember_hide", "remember_minimize", "remember_exit")
        if action not in allowed:
            return {"ok": False, "error": "bad_action", "text": "未知的关闭方式。"}
        remember = action.startswith("remember_")
        chosen = action[len("remember_"):] if remember else action
        if chosen == "hide":
            result = self.hide_window()
            result["remembered"] = False
            if not result.get("ok"):
                # 门禁没通过：原样返回失败原因，用户原来的偏好一个字都不动
                return result
            if remember:
                if self._remember_close_action("hide"):
                    result["remembered"] = True
                else:
                    # 已经藏起来了就别再翻回来，只是这次没记住
                    result["text"] = "窗口已隐藏，但偏好没有保存成功，这次先不记住。"
            return result
        if remember and not self._remember_close_action(chosen):
            return {"ok": False, "error": "prefs_busy",
                    "text": "偏好没有保存成功，这次先不记住。"}
        if chosen == "minimize":
            try:
                self._window.minimize()
            except Exception:
                return {"ok": False, "error": "no_window", "text": "窗口不可用，没能最小化。"}
            self._window_minimized = True
            return {"ok": True, "action": "minimize", "remembered": remember}
        self._close_approved = True
        try:
            self._window.destroy()
        except Exception:
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能退出。"}
        return {"ok": True, "action": "exit", "remembered": remember}

    def _remember_close_action(self, action: str) -> bool:
        """把「以后都这样」写进 ui.json 的 window.close_action，返回是否写成功。"""
        prefs = load_prefs()
        window = dict(prefs.get("window") or {}) if isinstance(prefs.get("window"), dict) else {}
        window["close_action"] = action
        return bool(update_prefs({"window": window}))

    # ---------- 隐藏到后台（窗口消失、进程继续跑） ----------
    def hide_window(self) -> dict:
        """把窗口藏起来：手机访问、报名计划、校时全都继续跑。

        藏起来以后任务栏上就没有按钮了，所以必须先有一条能把界面叫回来的路：
        托盘图标，或者至少还有一条未过期的手机会话。两样都没有就拒绝隐藏——
        把窗口藏成再也打不开的样子，比不让它隐藏糟糕得多。
        """
        tray = self._ensure_tray()
        if not tray:
            if not self._phone.has_live_session():
                return {"ok": False, "error": "hide_unavailable",
                        "text": "托盘图标和手机访问都不可用：现在隐藏就没法把窗口叫回来，"
                                "这次先不隐藏。"}
            phone_log("托盘图标没有建起来：隐藏后请用手机页的「显示电脑窗口」叫回界面。")
        try:
            self._window.hide()
        except Exception:
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能隐藏。"}
        phone_log("窗口已隐藏到后台；进程继续运行，托盘或手机页可以唤回")
        self._window_hidden = True
        return {"ok": True, "action": "hide", "hidden": True, "tray": self._tray is not None}

    def show_window(self) -> dict:
        """把藏起来的窗口叫回来（托盘菜单、手机页都用这一个入口）。"""
        try:
            self._window.show()
        except Exception:
            return {"ok": False, "error": "no_window", "text": "窗口不可用，没能显示。"}
        try:
            # 从最小化里叫回来也走这里：隐藏和最小化一起清掉
            self._window.restore()
        except Exception:
            pass
        self._window_hidden = False
        self._window_minimized = False
        phone_log("窗口已从后台显示出来")
        return {"ok": True, "hidden": False, "tray": self._tray is not None}

    def _on_window_minimized(self) -> None:
        self._window_minimized = True

    def _on_window_restored(self) -> None:
        self._window_minimized = False

    def _plan_source_of(self, plan_id) -> str:
        with self._lock:
            return self._plan_sources.get(str(plan_id or ""), "desktop")

    def _notify_plan_done(self, snapshot) -> None:
        """窗口最小化或藏在后台时计划结束：托盘弹一条系统通知，点通知回到窗口。

        窗口就在眼前时不打扰；托盘建不起来就不发，结果仍在窗口里。
        """
        if not (self._window_hidden or self._window_minimized):
            return
        title, text = _plan_service.plan_done_notice((snapshot or {}).get("tasks") or [])
        try:
            if self._ensure_tray() and self._tray is not None:
                self._tray.notify(title, text)
        except Exception:
            pass

    def _ensure_tray(self) -> bool:
        """懒建托盘图标；已经建过就直接复用。任何异常都只当作「没有托盘」。"""
        if self._tray is not None:
            return True
        try:
            from infrastructure import tray_icon as _tray_icon

            tray = _tray_icon.TrayIcon(on_show=self.show_window,
                                       on_exit=lambda: self.request_window_close("exit"))
            if tray.start():
                self._tray = tray
                return True
        except Exception:
            self._tray = None
        return False

    def _stop_tray(self) -> None:
        tray = self._tray
        self._tray = None
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass

    def shutdown(self) -> None:
        """窗口正常关闭的进程收尾：先同锁置关闭屏障并取快照，再停协调器、树终止**仅本 Api 登记**的 worker。

        关闭屏障：_closing 与一切 worker 创建/登记共用 _lock——快照取到时，
        任何「已开始创建」的进程必然已登记完成（创建若还没进锁，随后会被
        _closing 拒绝），因此快照是完备的，收走不会漏；锁外调用 plan.stop 与
        树终止：协调器回调与任务线程的登记/清理都需要 _lock，锁内等待会互相
        等死。重复/并发 shutdown：后到调用在锁外等待首次收尾的完成 Event，
        返回即代表收尾真正完成——入口置位不算 done，主正常退出不会先于收尾
        完成继续 finalize。
        覆盖登录/单活动（_proc）、计划任务（_plan_procs）与 check/list（_aux_procs）；
        onefile 主程序退出后运行期资源根即消失，留下还握着它的孤儿 worker 只会
        拿着旧资源继续跑——必须先收干净再 finalize 生命周期。
        绝不按进程名扫杀：用户可能同时开着别的实例或别的程序，只动自己登记的进程。
        """
        # 托盘图标先撤：窗口都收尾了还挂着一个图标，用户点它只会点出幽灵窗口
        self._stop_tray()
        with self._lock:
            if self._closing:
                # 已有收尾在进行：后到调用不重取快照、不重复 stop/kill，
                # 在锁外等同一个完成 Event——返回即代表收尾真正完成（FB2）
                done_event = self._shutdown_done_event
            else:
                done_event = None
                self._closing = True
                plan = self._plan
                plan_procs = list(self._plan_procs.values())
                aux_procs = list(self._aux_procs)
                proc = self._proc
        if done_event is not None:
            done_event.wait()
            return
        try:
            # 等组件目录替换提交/回滚完毕，再让主进程和 onefile 资源退出。
            for name in ("_component_service", "_ocr_component_service"):
                component_service = getattr(self, name, None)
                if component_service is not None:
                    component_service.shutdown()
            self._auto_relogin.stop()
            # 手机入口先收：有界取消中继、关 HTTP、撤销会话，再走进程收尾
            try:
                self._relay.shutdown()
            except Exception:
                pass
            try:
                self._cloudflare.stop()
                # 正常退出只是关程序：保留设备信任，下次恢复入口不用重新配对；
                # 用户在界面里手动关闭才走 stop(revoke_devices=True)。
                self._phone.shutdown(preserve_devices=True)
                self._phone_channel = ""
            except Exception:
                pass
            if plan:
                try:
                    plan.stop()
                except Exception:
                    pass   # 窗口已在关闭，收尾尽力而为，不让异常挡住生命周期写入
            for orphan in plan_procs + aux_procs:
                _kill_tree(orphan)
            if proc and proc.poll() is None:
                _kill_tree(proc)
        finally:
            # 完成信号在收尾 finally 发出：提前置位会让后到调用先于真正收尾返回
            self._shutdown_done_event.set()

    def stop(self) -> dict:
        with self._lock:
            plan = self._plan
        if plan:
            return self.stop_plan(plan.plan_id)
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            _kill_tree(proc)
            self._emit("log", "已请求停止")
            return {"ok": True}
        return {"ok": False, "text": "当前没有在跑的任务"}

    # ---------- 手机受限访问（默认关闭） ----------
    def _phone_raw_state(self) -> dict:
        """手机状态投影的原料：只读本机缓存，绝不因此触发学校流量。"""
        with self._lock:
            activities = [dict(item) for item in self._activities.values()]
            plan = self._plan
            last_plan = self._last_plan
            busy = self._is_busy_locked()
        snapshot = None
        if plan is not None:
            try:
                snapshot = plan.snapshot()
            except Exception:
                snapshot = None
        if snapshot is None:
            snapshot = last_plan
        if isinstance(snapshot, dict):
            snapshot = dict(snapshot)
            snapshot.setdefault("source", self._plan_source_of(snapshot.get("plan_id")))
        login = login_state(self._clock)
        # 手机页也写上次校验时刻（与 bootstrap.login 同一口径，ui-amendment-002）
        with self._lock:
            last_check = dict(self._last_check)
        login.update(_last_check_fields(last_check))
        return {
            "activities": activities,
            "login": login,
            "plan": snapshot,
            "busy": busy,
            "business_clock": self._clock_payload(),
            "retry_options": _retry_options_payload(),
            "terms": terms_state(load_prefs()),
            # 手机端条款门和电脑同源：没同意当前版本时手机停在缓存，不能开始计划或重新登录
            "terms_ok": self._terms_gate() is None,
            # 手机重新登录要知道电脑有没有账号、有没有验证码识别；账号只给打码后的样子
            "relogin_setup": self._phone_relogin_setup(),
            # relay 公开状态只含阶段/挑战图，不含账号密码、token 或 DPAPI 密文；
            # 电脑自己认图时投影层会把验证码抹掉，手机只看到「重试中」
            "login_relay": self._phone_relay_view(),
        }

    def _phone_relogin_setup(self) -> dict:
        """手机重新登录表单需要的四件事：有没有保存账号、账号打码、识别装没装、是否暂停。"""
        saved = _credential_store.has_credentials(CREDENTIAL_FILE)
        hint = ""
        if saved:
            try:
                hint = _login_rules.mask_account(_credential_store.stored_username(CREDENTIAL_FILE))
            except Exception:
                saved = False
        try:
            ocr = bool(self._relogin_ocr_ready())
        except Exception:
            ocr = False
        return {"saved": saved, "account_hint": hint, "ocr_ready": ocr,
                "paused": bool(saved and _credential_store.is_bad(CREDENTIAL_FILE))}

    def _cloudflare_status_snapshot(self) -> tuple[dict, dict]:
        """读一次隧道状态，顺手把「异常退出」收成可复用的退出提示。

        CloudflareTunnel.status() 只报一次 exited，读完就把子进程句柄与地址清掉，
        下一次读到的只会是 stopped。一次响应里要读好几处状态，所以退出结论必须
        在这里留住；返回 (本次状态, 仍然有效的退出提示)，提示为空 dict 表示没有。
        """
        status = self._cloudflare.status()
        if status.get("state") == "exited":
            self._cloudflare_exit_notice = dict(status)
        return status, dict(self._cloudflare_exit_notice or {})

    def _reconcile_cloudflare_lifecycle(self) -> dict:
        """Cloudflare 临时通道的生命周期对账：隧道没了就把这条通道彻底收口。

        进程异常退出等于这条临时通道已经失效：手机服务没有公网入口了，旧地址和
        二维码也注定打不开，所以立刻停服务、撤销会话、清空通道与地址，让界面拿到
        running=false、address=''、qr=''。必须幂等——状态刷新会被反复调用，手机已经
        停下、通道已经清空时再来一次什么都不做。
        """
        _, notice = self._cloudflare_status_snapshot()
        if not notice:
            return {}
        with self._phone_access_lock:
            if self._phone_channel != "cloudflare":
                return {}
            if self._phone.is_running():
                self._stop_phone_access()
            self._phone_channel = ""
            phone_log("Cloudflare 隧道已退出：手机访问随之停止，手机需要重新开启并重新配对")
            self._emit("log", "Cloudflare 临时通道已失效，请重新开启手机访问")
        return dict(notice)

    def phone_access_state(self) -> dict:
        """帮助弹窗：监听状态、远程通道、地址、二维码与一次性配对码。

        配对码只在这里给桌面面板显示，不进 URL、不落日志、不发给未配对手机。
        """
        # 先对账再读：同一次响应不得把已经失效的旧地址或旧二维码带回界面
        self._reconcile_cloudflare_lifecycle()
        service = self._phone
        prefs = load_prefs()
        feature = _advanced_features.feature_state(
            prefs, root=DATA_DIR, frozen=bool(getattr(sys, "frozen", False))).get(
                _advanced_features.PHONE_CONTROL, {})
        address = service.address()
        prefs_info = _phone_access_prefs(prefs)
        # 一次取全：配对码、剩余有效秒数、换码序号（界面靠 seq/reason 提示码已换新）
        code_info = service.pair_code_status()
        # 三份状态各归各：能力（组件装没装）、通道（网络入口通不通）、当前跑的是哪条。
        # 前端不允许用单个 ready 推导全部状态——那正是「ddddocr 没装却说手机控制
        # 不可用」那类串台的老毛病。
        advanced = self.advanced_features_state()
        channels = dict(advanced.get("channels") or {})
        return {"ok": True,
                "feature": feature,
                "features": {"phone_control": dict(feature)},
                "channels": channels,
                "active_channel": self._phone_channel,
                "running": service.is_running(),
                "channel": self._phone_channel,
                "address": address,
                "qr": _phone_qr_data(address),
                "pair_code": code_info["code"],
                "pair_code_status": code_info,
                # B1：本次开启后成功兑换配对码的次数，停止手机访问时清零；
                # 「手机已连接」靠它判断，不靠 pair_code_status 的瞬时 reason
                "paired_count": service.paired_count(),
                # fe-phone（审核决定 A4）：重启后手机靠设备信任 cookie 恢复会话时 paired_count 为 0，
                # 「手机已连接」= paired_count > 0 或 live_session。只给布尔，绝不回传 token 或 cookie；
                # stop() 本就清会话，这里仍与 is_running 取与，停着时一定为假
                "live_session": bool(service.is_running() and service.has_live_session()),
                "supported": bool(feature.get("ready")),
                # 通道选择的单一真源：界面只显示，不自己推断该恢复哪一个
                "preferred_channel": prefs_info["preferred_channel"],
                "tailscale_autostart": prefs_info["tailscale_autostart"],
                "advanced": self.advanced_features_state()}

    def start_phone_access(self, channel: str = "tailscale") -> dict:
        with self._phone_access_lock:
            return self._start_phone_access(channel)

    def _start_phone_access(self, channel: str) -> dict:
        """开启远程手机入口：Tailscale 或 Cloudflare，局域网不作为产品入口。"""
        prefs = load_prefs()
        if not _advanced_features.feature_ready(prefs, _advanced_features.PHONE_CONTROL, root=DATA_DIR):
            return {"ok": False, "error": "feature_required",
                    "text": "请先在帮助里的高级功能安装手机控制。"}
        selected = str(channel or "tailscale").strip().lower()
        # 保留旧测试/开发调用的回环入口；帮助界面只提供两个远程通道。
        if selected in {"127.0.0.1", "localhost"}:
            selected = "local"
        if selected not in {"tailscale", "cloudflare", "local"}:
            return {"ok": False, "error": "bad_channel", "text": "请选择远程通道"}
        with self._lock:
            if self._closing or self._advanced_busy:
                return {"ok": False, "text": "程序正在关闭，手机访问没有开启"}
        # 同一时间只跑一条通道：换通道必须先关掉现在这条，绝不自动切换
        if self._phone.is_running() and self._phone_channel and selected != self._phone_channel:
            return {"ok": False, "error": "other_channel_running",
                    "text": "现在开着的是另一条通道，请先关闭再切换。"}
        if selected == "cloudflare" and self._cloudflare_starting:
            return {"ok": False, "error": "cloudflare_starting",
                    "text": "Cloudflare 隧道正在启动，请稍等几秒。"}
        target = "127.0.0.1"
        public_host = "127.0.0.1"
        if selected == "tailscale":
            endpoint = _tunnel_manager.tailscale_endpoint()
            if not endpoint.get("available"):
                return {"ok": False, "error": endpoint.get("error", "tailscale_unavailable"),
                        "text": endpoint.get("text", "请先登录 Tailscale")}
            target = str(endpoint.get("bind_host") or "")
            public_host = str(endpoint.get("public_host") or target)
        if selected == "cloudflare":
            # 组件可能在程序启动之后被替换或删除：每次真正启动前都重新解析校验，
            # 校验不过就先清掉初始化时缓存的旧路径，绝不再拿它去执行
            verified = _tunnel_manager.resolve_cloudflared(
                resource_root=RESOURCE_ROOT, here=HERE, root=DATA_DIR)
            self._cloudflare.executable = verified
            if not verified:
                return {"ok": False, "error": "cloudflared_missing",
                        "text": "没有找到通过校验的 cloudflared，Cloudflare 通道暂时不可用。"}
        result = self._phone.start(target, public_host=public_host,
                                   persistent_device=(selected == "tailscale"))
        if result.get("ok"):
            self._phone_channel = selected
            if selected == "cloudflare":
                self._cloudflare_starting = True
                try:
                    tunnel = self._cloudflare.start(self._phone.address())
                finally:
                    self._cloudflare_starting = False
                if not tunnel.get("ok"):
                    self._phone.stop()
                    self._phone_channel = ""
                    return tunnel
                public_url = str(tunnel.get("url") or "")
                public_host = public_url.split("//", 1)[-1].split("/", 1)[0]
                self._phone.set_public_url(public_url)
                # 重新开启成功：上一次的「隧道已退出」提示到此为止
                self._cloudflare_exit_notice = None
            phone_log("开启手机访问：通道=%s 监听=%s 公网=%s 设备信任=%s" % (
                selected, target, public_host,
                "开" if result.get("persistent_device") else "关"))
            self._emit("log", "手机访问已开启：%s" % result.get("address", ""))
            self._remember_phone_channel(selected)
            result = dict(result, channel=selected, address=self._phone.address())
        return result

    def _remember_phone_channel(self, channel: str) -> None:
        """开启成功后记下通道；只有地址固定的 Tailscale 才允许下次自动恢复。"""
        block = {"preferred_channel": str(channel),
                 "tailscale_autostart": str(channel) == "tailscale"}
        if not update_prefs({_PHONE_PREF_NAMESPACE: block}):
            self._emit("log", "通道选择没有写进偏好；本次照常可用，下次需要重新选。")

    def _forget_phone_autostart(self) -> None:
        """手动关闭手机访问：不再自动恢复（设备信任由服务自己撤销）。"""
        current = _phone_access_prefs(load_prefs())
        update_prefs({_PHONE_PREF_NAMESPACE: {
            "preferred_channel": current["preferred_channel"],
            "tailscale_autostart": False}})

    def set_phone_access_preferences(self, preferred_channel: str = "") -> dict:
        """记住用户选的通道；只影响下次启动是否自动恢复，不动当前监听。"""
        channel = str(preferred_channel or "").strip().lower()
        if channel and channel not in _PHONE_CHANNELS:
            return {"ok": False, "error": "bad_channel", "text": "请选择远程通道"}
        current = _phone_access_prefs(load_prefs())
        chosen = channel or current["preferred_channel"]
        block = {"preferred_channel": chosen,
                 # 明确选了 Tailscale 才开启下次自动恢复；换成 Cloudflare 等于放弃
                 "tailscale_autostart": chosen == "tailscale"}
        if not update_prefs({_PHONE_PREF_NAMESPACE: block}):
            return {"ok": False, "error": "prefs_busy",
                    "text": "通道选择没有保存，请重试。"}
        return {"ok": True, "preferred_channel": chosen,
                "tailscale_autostart": block["tailscale_autostart"]}

    def restore_phone_access(self) -> dict:
        """窗口就绪后按上次的通道恢复入口：只恢复 Tailscale，绝不自动恢复 Cloudflare。

        只做「已经装好并登录」的恢复：不安装外部程序、不启动守护进程、不弹提示。
        """
        current = _phone_access_prefs(load_prefs())
        if current["preferred_channel"] != "tailscale" or not current["tailscale_autostart"]:
            return {"ok": False, "error": "not_configured",
                    "text": "上次没有用 Tailscale 开启手机访问，本次不自动恢复。"}
        with self._lock:
            if self._closing:
                return {"ok": False, "text": "程序正在关闭，手机访问没有恢复"}
        if self._phone.is_running():
            return {"ok": True, "running": True, "channel": self._phone_channel,
                    "address": self._phone.address()}
        endpoint = _tunnel_manager.tailscale_endpoint()
        if not endpoint.get("available"):
            return {"ok": False,
                    "error": endpoint.get("error", "tailscale_unavailable"),
                    "state": endpoint.get("state", ""),
                    "text": endpoint.get("text", "Tailscale 现在不可用")}
        result = self.start_phone_access("tailscale")
        return dict(result, restored=True)

    def schedule_phone_restore(self, window) -> None:
        """窗口加载完再恢复手机入口：此时界面能收到日志，HTTP 桥也已就绪。

        只恢复上次用 Tailscale 开启的固定入口；没配过就什么都不做，不弹提示——
        「首次不装也不影响后续」靠的就是这条静默路径。
        """
        def run() -> None:
            try:
                event = getattr(getattr(window, "events", None), "loaded", None)
                if event is not None:
                    event.wait(15)
            except Exception:
                pass
            try:
                result = self.restore_phone_access()
            except Exception as exc:
                self._emit("log", "手机访问没有恢复：%s" % type(exc).__name__)
                return
            if result.get("ok") and result.get("address"):
                self._emit("log", "已恢复手机访问：%s" % result["address"])

        threading.Thread(target=run, name="phone-restore", daemon=True).start()

    def stop_phone_access(self) -> dict:
        with self._phone_access_lock:
            result = self._stop_phone_access()
        # 用户自己关掉通道＝他已经知道那条隧道废了，退出提示可以收起来
        self._cloudflare_exit_notice = None
        return result

    def _stop_phone_access(self) -> dict:
        """关闭手机入口并撤销全部会话：有界收尾，不留后台监听。"""
        self._relay.cancel(origin="phone")
        self._cloudflare.stop()
        result = self._phone.stop(revoke_devices=True)
        phone_log("关闭手机访问：通道=%s，已撤销会话与设备信任" % (self._phone_channel or "-"))
        self._phone_channel = ""
        self._forget_phone_autostart()
        self._emit("log", "手机访问已关闭")
        return result

    # ---------- 手机重登中继（凭据只在进程内存） ----------
    def prepare_phone_relogin(self, username: str = "", password: str = "",
                              save: bool = False) -> dict:
        """桌面「准备手机重登」：账号密码只进当前进程内存，响应只回 ready 布尔。

        绝不写 prefs/文件/命令行/env/日志；手机 HTTP 白名单也读不到这份数据。
        save=True 时，登录成功后才把这份账号密码写进电脑（默认不保存）。
        """
        user = str(username or "").strip()
        secret = str(password or "")
        typed = bool(user and secret)
        if not typed:
            if _credential_store_available():
                try:
                    stored = _credential_store.load(CREDENTIAL_FILE)
                    user, secret = stored["username"], stored["password"]
                except Exception:
                    user, secret = "", ""
        result = self._relay.prepare(user, secret)
        if result.get("ok"):
            with self._lock:
                self._relay_creds_source = "typed" if typed else "saved"
                self._pending_save = ({"username": user, "password": secret}
                                      if typed and save else None)
        user = ""
        secret = ""
        if result.get("ok"):
            self._emit("log", "已为手机重新登录准备好账号（只在本工具内存里）")
        return result

    def _commit_pending_save(self) -> None:
        """登录成功后才落盘这次手输、又勾了保存的账号密码；没有就什么都不做。"""
        with self._lock:
            pending = self._pending_save
            self._pending_save = None
        if not pending:
            return
        try:
            with self._credential_lock:
                _credential_store.save(CREDENTIAL_FILE, pending["username"], pending["password"])
                self._auto_relogin.reset()
            self._emit("log", "账号密码已保存到这台电脑（加密存储）")
        except Exception as exc:  # noqa: BLE001 - 保存失败不影响「已经登录成功」
            self._emit("log", "账号密码没有保存成功：%s" % type(exc).__name__)
        finally:
            pending.clear()

    def _relogin_late_answer(self) -> "dict | None":
        """计划运行中还来不来得及重新登录（架构方案 4.3）；来得及返回 None。

        有场次在提交，或离开放不到 100 秒，就只剩电脑自己的自动登录。业务时钟读不出来时
        按来不及处理：宁可让用户等电脑自动登录，也不在开抢前抢走登录态。
        """
        with self._lock:
            plan = self._plan
        if plan is None:
            return None
        try:
            tasks = (plan.snapshot() or {}).get("tasks") or []
            late = _login_rules.relogin_too_late(
                tasks, self._clock_now(),
                lambda task: school_epoch(str(task.get("sign_start") or "")))
        except Exception:
            late = True
        if not late:
            return None
        return {"ok": False, "error": "plan_late",
                "text": "有场次正在提交，或者离开放不到 100 秒。这时只有电脑能自动登录。"}

    def _relogin_entry_gate(self) -> "dict | None":
        """电脑和手机重新登录共同的前置门：演示、条款、关闭、来不及。"""
        if DEMO:
            return {"ok": False, "error": "demo", "text": "演示模式不联网，不会启动重新登录。"}
        gate = self._terms_gate()
        if gate is not None:
            return {"ok": False, "error": "terms_required", "text": "请先在电脑上同意使用条款"}
        with self._lock:
            if self._closing:
                return {"ok": False, "text": "程序正在关闭，已取消本次重新登录"}
        return self._relogin_late_answer()

    def _begin_typed_relogin(self, username: str, password: str, save: bool,
                             origin: str) -> dict:
        """用这次手输的账号密码登录：只进内存，save=True 才在成功后写进电脑。"""
        prepared = self.prepare_phone_relogin(username, password, save=save)
        if not prepared.get("ok"):
            return dict(prepared, text="请输入账号和密码。")
        manual = not self._relogin_ocr_ready()
        extra = {} if origin == "phone" else {"origin": origin}
        result = self._relay.begin(plan_active=False, worker_command=worker_command("login"),
                                   manual=manual, **extra)
        if not result.get("ok"):
            with self._lock:
                self._pending_save = None
        return dict(result, mode="manual" if manual else "auto")

    # ---------- 电脑上的重新登录（与手机共用一场登录流程） ----------
    def relogin_begin(self, username: str = "", password: str = "", save: bool = False) -> dict:
        """电脑上点「重新登录」。四种情况（设计 9.3）：

        - 填了账号密码：用这次输入的（默认只在内存里，save=True 成功后才保存）；
        - 没填：用电脑上保存的；保存的密码被学校拒绝过就停下，让用户输新密码；
        - 装了验证码识别：电脑自己认，连续认错 3 次转人工；没装：等用户输验证码。
        和手机共用同一场流程，同一时间只有一场；计划来不及时返回 plan_late。
        """
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if str(username or "").strip() and str(password or ""):
            return self._begin_typed_relogin(username, password, bool(save), origin="desktop")
        if not _credential_store.has_credentials(CREDENTIAL_FILE):
            return {"ok": False, "error": "needs_local_setup", "text": "请输入账号和密码。"}
        if _credential_store.is_bad(CREDENTIAL_FILE):
            return {"ok": False, "error": "bad_password",
                    "text": "保存的密码学校不认，自动登录已暂停。请输入新的账号密码。"}
        prepared = self.prepare_phone_relogin()
        if not prepared.get("ok"):
            return {"ok": False, "error": "needs_local_setup", "text": "请输入账号和密码。"}
        manual = not self._relogin_ocr_ready()
        result = self._relay.begin(plan_active=False, worker_command=worker_command("login"),
                                   manual=manual, origin="desktop")
        return dict(result, mode="manual" if manual else "auto")

    def relogin_submit(self, flow_id: str = "", challenge_id: str = "", code: str = "") -> dict:
        """电脑上输的验证码。"""
        return self._relay.submit(flow_id, challenge_id, code, origin="desktop")

    def relogin_cancel(self, flow_id: str = "") -> dict:
        """取消电脑上发起或接手的这一场登录；旧场的 flow_id 不取消新场。"""
        state = self._relay.state()
        if (flow_id and state.get("live") and state.get("flow_id")
                and flow_id != state.get("flow_id")):
            return {"ok": False, "error": "stale_flow", "text": "这次重新登录已经结束"}
        return self._relay.cancel()

    def relogin_auto_once(self) -> dict:
        """有保存的账号又装了验证码识别：用户确认后让电脑自动登录一次。"""
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if _credential_store.is_bad(CREDENTIAL_FILE):
            return {"ok": False, "error": "bad_password",
                    "text": "保存的密码学校不认，自动登录已暂停。请输入新的账号密码。"}
        current = self._relay.state()
        if current.get("live"):
            return {"ok": True, "mode": "auto", "flow_id": str(current.get("flow_id") or ""),
                    "text": "已经在登录了，等它结束。"}
        result = self._begin_auto_relogin()
        if not result.get("ok") and result.get("error") == "busy":
            return dict(result, text="电脑正在检查登录或加载活动，稍后再试。")
        return dict(result, mode="auto")

    def phone_relogin_begin(self, username: str = "", password: str = "",
                            save: bool = False) -> dict:
        if not DEMO and self._terms_gate() is not None:
            return {"ok": False, "error": "terms_required",
                    "text": "请先在电脑上同意使用条款"}
        # 演示、关闭中、计划来不及（有场次在提交或离开放不到 100 秒）都在这一道门里
        gate = self._relogin_entry_gate()
        if gate is not None:
            return gate
        if str(username or "").strip() and str(password or ""):
            # 手机上输的账号密码：默认只在电脑内存里，勾了「保存到这台电脑」才在成功后写盘
            return self._begin_typed_relogin(username, password, bool(save), origin="phone")
        if not self._manual_relogin_wanted():
            # 电脑自己会认图：手机别另开一场人工重登，只回报进度。
            # 已经有一场在跑就什么都不做——重复点按钮不该变成第二个 worker。
            current = self._relay.state()
            state = str(current.get("state") or "")
            # 只有真的还在跑的流程才算忙：历史快照里剩下的 waiting_code/verifying
            # 不代表「现在别再开一场」，否则一次残留会让手机永远点不动
            busy = bool(current.get("live")) and state not in (
                "idle", "success", "failed", "canceled")
            if not busy:
                started = self._begin_auto_relogin()
                if not started.get("ok") and started.get("error") != "busy":
                    return started
            return {"ok": True, "mode": "auto",
                    "text": "电脑正在自动登录，手机上不用再操作"}
        if not self._relay.prepared():
            self.prepare_phone_relogin()
        # 能走到这里说明计划来得及（_relogin_entry_gate 已判过 100 秒窗口）
        return self._relay.begin(plan_active=False,
                                 worker_command=worker_command("login"), manual=True)

    def phone_relogin_submit(self, flow_id: str = "", challenge_id: str = "",
                             code: str = "") -> dict:
        return self._relay.submit(flow_id, challenge_id, code)

    def phone_relogin_cancel(self, flow_id: str = "") -> dict:
        state = self._relay.state()
        # 历史快照的 flow_id 不属于现在这一场：拿它挡取消只会让用户点了没反应
        if (flow_id and state.get("live") and state.get("flow_id")
                and flow_id != state.get("flow_id")):
            return {"ok": False, "error": "stale_flow",
                    "text": "这次重新登录已经结束"}
        return self._relay.cancel(origin=None if state.get("mode") == "manual" else "phone")

    def _spawn_relay_worker(self, args: list[str]):
        """relay worker 创建：与 _spawn 同锁关闭屏障与 busy 预留，登记后才允许输入。"""
        problem = worker_problem()
        if problem:
            raise RuntimeError(problem)
        with self._lock:
            if self._closing:
                raise RuntimeError("closing")
            # 计划在跑不再一律拦：什么时候能登录由调用方先判断（手动看 100 秒窗口，
            # 自动看 _relogin_blocked_locked）。这里只防和另一个单独进程、检查、拉列表撞车。
            single = self._proc is not None and self._proc.poll() is None
            if single or self._checking or self._listing:
                raise RuntimeError("busy")
            proc = subprocess.Popen(
                args, cwd=str(HERE), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=_env(), creationflags=CREATE_NO_WINDOW)
            self._proc = proc       # 占住 busy 位：原有 login/计划不能同跑
        return _RelayTree(proc)

    def _relay_finished(self) -> None:
        with self._lock:
            if self._proc is not None and self._proc.poll() is not None:
                self._proc = None
            began = self._auto_relogin_started_at
        # 自动登录这一轮没成：落盘失败分类（中继给的安全错误码，不含账号和验证码）
        try:
            last = self._relay.state()
        except Exception:
            last = {}
        state = str(last.get("state") or "")
        with self._lock:
            source = self._relay_creds_source
            if state != "success":
                # 没登录成功：这次手输的账号密码不保存
                self._pending_save = None
        if state == "failed" and last.get("safe_error") == "bad_password":
            if source == "saved":
                # 学校明确说保存的密码不对：暂停自动登录，直到写入新密码
                try:
                    _credential_store.mark_bad(CREDENTIAL_FILE)
                except OSError:
                    pass
                self._emit("log", "保存的密码学校不认，自动登录已暂停；到设置里换成新密码。")
            else:
                # 手输的密码不对：内存里这份作废，下次要重新输
                self._relay.clear_staged()
        if last.get("origin") == "auto" and last.get("state") in ("failed", "canceled"):
            self._log_event("auto_relogin_failed", level="WARN",
                            reason=str(last.get("safe_error") or last.get("state") or "unknown"),
                            **({"elapsed_s": time.monotonic() - began}
                               if began is not None else {}))

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
        # 只读协调器已发布的不可变状态：持 Api 锁时绝不取协调器锁（P2-1）。
        # 反向路径（协调器 → Api）同样已改为锁外发布，两条边不再成环。
        if self._proc and self._proc.poll() is None:
            return True
        if self._plan:
            if self._plan.published_status() in {"ready", "running"}:
                return True
        return any(proc.poll() is None for proc in self._plan_procs.values())

    def _is_busy(self) -> bool:
        with self._lock:
            return self._is_busy_locked()

    def _run_plan_task(self, spec: TaskSpec, cancel_event: threading.Event,
                       status: callable) -> dict:
        """运行一个单活动脚本；取消只终止对应进程，不影响同批其他任务。

        用例实现在 application.plan_service；worker 命令、环境、进程树创建、
        监督余量、学校时间换算与时钟异常类型都从这里以端口注入（裸名解析
        保持测试按 app.X 替换的语义）。
        """
        return _plan_service.run_plan_task(
            spec, cancel_event, status,
            emit=self._emit, lock=self._lock, plan_procs=self._plan_procs,
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
        """同步跑一个短命 worker（check/list）：创建、登记与关闭屏障同锁。

        Popen 在锁内：关闭先发生则拒绝创建（_ClosingError，取消语义）；
        创建已开始则 shutdown 必等登记完成才能取快照，不会留下未登记孤儿。
        OSError（缺文件/权限）原样抛给调用方归类成结构化组件错误。
        """
        with self._lock:
            if self._closing:
                raise _ClosingError("程序正在关闭，已取消本次 worker 调用")
            proc = subprocess.Popen(
                args, cwd=str(HERE), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                env=_env(), creationflags=CREATE_NO_WINDOW)
            self._aux_procs.add(proc)
        try:
            try:
                out, err = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                # 超时同样按进程树终止：onefile 引导进程死后真实 worker 可能还活着
                _kill_tree(proc)
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                return {"code": -1, "out": "[X] 执行超时（%d 秒）" % timeout,
                        "stdout": "", "stderr": ""}
        finally:
            with self._lock:
                self._aux_procs.discard(proc)
        return {"code": proc.returncode, "out": (out or "") + (err or ""),
                # stdout/stderr 分开交：列表 JSON 只认 stdout，stderr 混着辅助
                # 日志，不能整段拿去 json.loads（旧键 out 保留原行为不动）
                "stdout": out or "", "stderr": err or ""}

    def _spawn(self, args: list[str], label: str, kind: str = "grab") -> dict:
        problem = worker_problem()
        if problem:
            # 组件不齐：同步给结构化失败——不占 busy 位、不写 _proc 占位
            self._emit("log", "[X] 组件诊断 %s：组件路径 %s" % (problem, GRAB))
            return {"ok": False, "text": WORKER_PROBLEM_TEXT[problem], "error": problem}
        try:
            with self._lock:
                if self._closing:
                    # 关闭拒绝不带 error 码：不是组件损坏，前端不得挂横幅
                    return {"ok": False, "text": "程序正在关闭，已取消本次「%s」" % label}
                if self._is_busy_locked():
                    return {"ok": False, "text": "已经有一个任务在跑，先等它结束"}
                self._proc = subprocess.Popen(
                    args, cwd=str(HERE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    env=_env(), creationflags=CREATE_NO_WINDOW)
                proc = self._proc
        except OSError as exc:
            # Popen 竞态失败（文件在自检后被删/被锁）：同样给结构化结论，不冒充成功
            err_code = _component_error(exc)
            self._emit("log", "[X] 组件诊断 %s：%s: %s" % (err_code, type(exc).__name__, exc))
            return {"ok": False, "text": WORKER_PROBLEM_TEXT[err_code], "error": err_code}

        threading.Thread(target=self._pump, args=(proc, label, kind),
                         daemon=True).start()
        return {"ok": True}

    def _anchor_login_success(self, origin: str = "") -> None:
        """新登录真实成功后建立 v2 锚点；没有可信时钟就不写（不拿系统时间冒充）。

        只在本次 login worker 成功路径调用：check/refresh/bootstrap 都不续期，
        也不改 session/storage_state 结构，旧有效凭证不要求重登。
        origin 由中继给出（auto_ocr=无人值守、phone_manual=手机人工），
        只用于「上一次是怎么完成的」这一行说明，不参与判断。
        """
        self._commit_pending_save()
        if origin in ("auto_ocr", "phone_manual"):
            with self._lock:
                self._last_login_origin = origin
                began = self._auto_relogin_started_at
            if origin == "auto_ocr":
                self._log_event("auto_relogin_ok",
                                **({"elapsed_s": time.monotonic() - began}
                                   if began is not None else {}))
            # 重登成功时桌面还停在「登录已过期」：补一次正常的登录检查，
            # 让顶栏状态、活动列表和时间锚点跟着刷新。check 自带忙碌去重，
            # 手动重登、自动重登走的是同一条路。
            threading.Thread(target=self.check, daemon=True).start()
        try:
            lower, upper = self._clock.bounds()
            token = str(json.loads(SESSION_FILE.read_text(encoding="utf-8"))
                        .get("token") or "").strip()
        except Exception:
            return
        if not token or not (upper >= lower):
            return
        save_session_timing_anchor(token, (lower + upper) / 2.0,
                                   (upper - lower) / 2.0)

    def _pump(self, proc: subprocess.Popen, label: str, kind: str = "grab") -> None:
        self._emit("log", "▶ " + label)
        tail: list[str] = []
        for line in proc.stdout or []:
            line = line.rstrip("\r\n")
            if not line:
                continue
            tail.append(line)
            del tail[:-40]
            if line.startswith("[login] "):
                # [login] 结构行交专属 relay flow；原日志/桌面 done 行为保持
                self._relay.observe_line(line)
            self._emit("log", line)
        proc.wait()
        # done 结论整理在 application.login_service：login 只看退出码，
        # grab 还要求见过「报名成功」行；失败原因取第一条 [X] 来源行。
        ok, reason = _login_service.done_result(kind, proc.returncode, tail)
        if kind == "login" and ok:
            # 只有本次登录真实成功才建立 v2 锚点：check/refresh 不续期，
            # 失败/取消路径根本不走这里，旧锚点与旧会话原样保留。
            # 锚点写入失败（偏好锁超时/磁盘只读）不能吞掉登录结论：
            # 否则 done 永远不来，界面就永远停在「登录中」。
            try:
                self._anchor_login_success()
            except Exception as exc:  # noqa: BLE001 - 兜底上报，不中断收口
                self._emit("log", "[!] 登录成功，但会话时间锚点没有写成：%s" % exc)
        self._emit("done", {"ok": ok, "code": proc.returncode,
                            "reason": reason, "label": label, "kind": kind})
        with self._lock:
            if self._proc is proc:
                self._proc = None


# ---- 兼容包装：已下沉 domain / infrastructure 的纯规则与进程树适配器 ----
# 实现见 domain.time_text / domain.retry_rules / domain.login_rules /
# domain.worker_lines / infrastructure.process_tree；旧名字保留供测试与
# 内部调用按原名注入、patch。
_task_deadline = _time_text.task_deadline
_kill_tree = _process_tree.kill_tree
_SpawnFailure = _process_tree.SpawnFailure
_ProcessTree = _process_tree.ProcessTree
spawn_owned_worker = _process_tree.spawn_owned_worker
_win_kernel32 = _process_tree.win_kernel32
_parse_checkpoint_line = _worker_lines.parse_checkpoint_line
_parse_clock_line = _worker_lines.parse_clock_line
_attempts_of = _retry_rules.attempts_of
_with_attempts = _retry_rules.with_attempts
_retry_payload = _retry_rules.retry_payload
_ATTEMPT_RE = _retry_rules.ATTEMPT_RE


def _parse_retry_line(line: str) -> "dict | None":
    """解析 worker 的 [retry] 结构化终态行（实现在 domain.retry_rules）。"""
    return _retry_rules.parse_retry_line(line)


def _check_reason_line(out: str) -> tuple[str, str]:
    """从 check 的完整输出提取 (来源行, 末行)（实现在 domain.login_rules）。"""
    return _login_rules.check_reason_line(out)


def _check_result(state: dict, code: int, text: str) -> str:
    """check 的四态结论（实现在 domain.login_rules）。"""
    return _login_rules.check_result(state, code, text)


def _check_hint(text: str, code: int) -> str:
    """把 check 的来源行粗分类：network / login / error（实现在 domain.login_rules）。"""
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
    width, height, min_w, min_h = _window_geometry(_screen_size())
    window = webview.create_window(
        "校园活动预报名工具", str(UI),
        js_api=api, width=width, height=height, min_size=(min_w, min_h),
        background_color="#E9EEF6",
    )
    api._window = window
    api.schedule_phone_restore(window)

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
    # 窗口已关（正常路径）：先收本实例登记的 worker（计划/登录/单活动/check/list）——
    # onefile 退出后运行期资源根即消失，绝不能留下还握着它的孤儿进程；
    # 再停心跳并落关闭时刻，clean/abnormal 的分界不变
    api.shutdown()
    lifecycle.finalize()
    clock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
