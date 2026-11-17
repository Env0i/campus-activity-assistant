#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试夹具：把 Api 摆进十种「正在进行」状态，并造一个不碰真实数据根的测试 Api。

what：`put(api, column)` 逐列摆状态，`build(testcase)` 造一个只属于本次用例的
Api——两者合起来是「谁挡谁」矩阵逐格钉住（test_busy_matrix.py）的唯一状态入口。

how（数据根隔离）：构造 Api 前用 `tempfile.mkdtemp()` 建一个临时数据根，把 app
模块上按数据根派生的名字（DATA_DIR，以及构造路径与各动作会读的
CREDENTIAL_FILE / DEVICE_FILE / PHONE_LOG / PREFS / SESSION_FILE / LOG_FILE /
LOG_LOCK_FILE / ensure_data_dir）全部 patch 到临时根，用例结束删掉临时根。
组件服务（AdvancedComponentService(root=DATA_DIR)）、隧道、凭据因此只碰临时
目录，测试绝不 mkdir/open 真实数据根——由
design/evidence/2026-11-17/api-guards/data-dir-probe.txt 的审计钩子逐事件核对
为零。其余会碰真实数据的端口（偏好、凭证、日志、隧道解析）照旧换成内存替身。

how（忙碌字段）：本模块是**唯一**写 Api 忙碌私有字段的地方（_closing /
_cancelling / _checking / _listing / _proc / _plan / _plan_procs /
_advanced_busy / _cloudflare_starting，以及 UpdateService 自己的 _updating）。
`_plan` 与 `_plan_procs` 分成两列：busy.md 手工矩阵的「计划在跑」一列把
`_plan.published_status()`（协调器已发布状态）与 `_plan_procs`（计划任务进程
登记表）混在一起，这里拆开逐格钉。非忙碌的业务前置（_activities/_last_check）
也经本模块的 stage_* 具名函数摆，测试文件不直接写 Api 的状态字段。

下一批重构会把忙碌字段从 Api 搬进协调对象（交接单见
design/evidence/2026-11-17/api-coordination/busy.md）；到时行/列断言
（block / pass / merge）一格不用动，本模块跟着搬。矩阵测试里的哨兵仍留在
测试文件：其中 `_do_check`、`_do_list`、`_cancel_signup_run`、
`_install_selected_feature`、`api._phone.start/stop`、`api._relay.begin`、
`api._updates._spawn`、`spawn_owned`、`PlanCoordinator.start` 装在后续批次
会挪走的私有方法/端口上——拆到哪批、哪批把对应哨兵一起挪。

环境缺 pywebview 时按仓库惯例整批跳过（同 test_application_services 的写法）：
跳过不冒充通过，装齐依赖的解释器上这些用例会真跑。

@author Author
"""
from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# 列 = 「正在进行的事」。busy.md 第二节的「计划在跑」一列在此拆成两列：
# plan = 协调器已发布状态（_plan.published_status）；
# plan_procs = 计划任务进程登记表（_plan_procs 里 poll() 为 None 的进程）。
COLUMNS = ("closing", "cancelling", "checking", "listing", "worker",
           "plan", "plan_procs", "advanced", "tunnel", "updating")

BEIJING_TZ = timezone(timedelta(hours=8))


class _AliveProc:
    """进程替身：poll() 恒为 None，读起来就是「单 worker 还在跑」。"""

    returncode = None
    stdout = None
    stdin = None

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None

    def kill(self):
        return None


class _RunningPlan:
    """计划协调器替身：只回答已发布状态与任务快照。"""

    plan_id = "busy-plan"

    def published_status(self):
        return "running"

    def snapshot(self):
        # 手工重登入口的「来得及吗」判据读它：空任务 = 还来得及
        return {"tasks": []}


def put(api, column):
    """把 api 摆进 column 对应的「正在进行」状态，返回 api。

    每一列只设置门禁真正读到的那个字段；不改别的忙碌位，保证一格只考一个条件。
    """
    if column == "closing":
        api._closing = True
    elif column == "cancelling":
        api._cancelling = True
    elif column == "checking":
        api._checking = True
        api._check_request_id = "rid-busy"
    elif column == "listing":
        api._listing = True
        api._list_request_id = "rid-busy"
    elif column == "worker":
        api._proc = _AliveProc()
    elif column == "plan":
        api._plan = _RunningPlan()
    elif column == "plan_procs":
        # 只摆计划任务进程登记表，不碰 _plan（构造后本来就是 None）：
        # login/grab 走 _spawn 的 G1、start_plan/cancel/组件下载安装/自动重登
        # 各自的门读 _plan_procs；check/list/移除/手机/手工重登/更新不读它
        api._plan_procs = {"task-1": _AliveProc()}
    elif column == "advanced":
        api._advanced_busy = True
    elif column == "tunnel":
        # app.py 里「Cloudflare 拉起隧道中」的字段名
        api._cloudflare_starting = True
    elif column == "updating":
        # UpdateService 的单飞槽位：与服务自己 start_check/start_download 置位同名
        api._updates._updating = True
        api._updates._update_request_id = "rid-busy"
    else:
        raise ValueError("未知列: %s" % column)
    return api


# ---------- 非忙碌的业务前置：把 Api 的业务状态摆成「动作本来能过忙碌门」 ----------

def _plan_activity():
    """一场正在开放、报名未截止、举办时段完整且未报名的活动。"""
    now = datetime.now(BEIJING_TZ).replace(tzinfo=None)
    fmt = (lambda moment: moment.strftime("%Y-%m-%d %H:%M:%S"))
    return {"id": "act-plan", "name": "矩阵测试场次", "signed": False,
            "sign_start": fmt(now - timedelta(seconds=60)),
            "sign_end": fmt(now + timedelta(hours=1)),
            "act_start": fmt(now + timedelta(hours=2)),
            "act_end": fmt(now + timedelta(hours=3))}


def stage_plan_activity(api):
    """start_plan 的前置：活动表里有一场可报名的场次。"""
    row = _plan_activity()
    api._activities = {row["id"]: dict(row)}
    return api


def stage_valid_check(api):
    """start_plan 的前置：最近一次 check 的结论是「学校接口确认有效」。"""
    api._last_check = {"result": "valid", "checked_at": 0.0}
    return api


def stage_signed_activity(api):
    """cancel_signup 的前置：活动表里有一场已报名的场次。"""
    api._activities = {"act-signed": {"id": "act-signed", "name": "已报名场次",
                                      "signed": True}}
    return api


def _patch(testcase, target, name, new, **kwargs):
    """在 target 上打一个补丁，用例结束自动撤回。"""
    patcher = mock.patch.object(target, name, new, **kwargs)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return patcher


def _isolate_data_root(testcase, local_app):
    """把 app 模块上按数据根派生的名字全部指到临时目录，返回临时根。

    构造路径实际会读的名字以 local/app.py 的 Api.__init__ 为准：
    PhoneSessionStore(DEVICE_FILE)、两个 AdvancedComponentService(root=DATA_DIR)、
    CloudflareTunnel(root=DATA_DIR)；动作路径还会读 PREFS/CREDENTIAL_FILE/
    SESSION_FILE/LOG_FILE/LOG_LOCK_FILE 与 ensure_data_dir。
    """
    tmp_root = Path(tempfile.mkdtemp(prefix="busy-matrix-data-"))
    testcase.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)
    _patch(testcase, local_app, "DATA_DIR", tmp_root)
    _patch(testcase, local_app, "CREDENTIAL_FILE",
           tmp_root / "relogin-credentials.dpapi.json")
    _patch(testcase, local_app, "DEVICE_FILE",
           tmp_root / "phone-devices.dpapi.json")
    _patch(testcase, local_app, "PHONE_LOG", tmp_root / "phone.log")
    _patch(testcase, local_app, "PREFS", tmp_root / "ui.json")
    _patch(testcase, local_app, "SESSION_FILE", tmp_root / "session.json")
    _patch(testcase, local_app, "LOG_FILE", tmp_root / "grab.log")
    _patch(testcase, local_app, "LOG_LOCK_FILE", tmp_root / "grab.log.lock")
    _patch(testcase, local_app, "ensure_data_dir", lambda: tmp_root)
    return tmp_root


def build(testcase):
    """造一个测试用 Api：时钟可控、DEMO 关、条款放行、数据根隔离、组件自检为空。

    构造前先把数据根 patch 到临时目录（_isolate_data_root），再把会碰真实数据的
    端口（偏好、凭证、日志、隧道解析）换成内存替身；构造后立刻停掉 Api 自带的
    自动重登线程（它在 __init__ 里启动），避免后台每拍去读凭证/偏好。

    环境缺 pywebview 时按仓库惯例整批跳过（同 test_application_services 的写法）：
    跳过不冒充通过，装齐依赖的解释器上这些用例会真跑。
    """
    try:
        import app as local_app
    except Exception as exc:  # pragma: no cover - 环境缺 pywebview 时跳过
        testcase.skipTest("无法导入 local/app.py：%s" % exc)
    from fixtures.api_threads import stop_auto_relogin_on_cleanup
    from fixtures.business_clock import TestWallClock

    _isolate_data_root(testcase, local_app)
    _patch(testcase, local_app, "DEMO", False)
    _patch(testcase, local_app, "worker_problem", lambda: "")
    _patch(testcase, local_app, "load_prefs", lambda: {})
    _patch(testcase, local_app, "update_prefs", lambda patch: True)
    _patch(testcase, local_app, "phone_log", lambda message: None)
    _patch(testcase, local_app._credential_store, "has_credentials",
           lambda path: True)
    _patch(testcase, local_app._credential_store, "is_bad", lambda path: False)
    _patch(testcase, local_app._credential_store, "load",
           lambda path: {"username": "tester", "password": "secret"})
    _patch(testcase, local_app._advanced_features, "feature_ready",
           lambda *args, **kwargs: True)
    # 构造 Api 时 CloudflareTunnel 会解析组件路径：钉成固定值，不扫真实数据根
    _patch(testcase, local_app._tunnel_manager, "resolve_cloudflared",
           lambda *args, **kwargs: "stub-cloudflared.exe")
    _patch(testcase, local_app._tunnel_manager, "tailscale_endpoint",
           lambda *args, **kwargs: {"available": True, "bind_host": "127.0.0.1",
                                    "public_host": "127.0.0.1"})

    api = stop_auto_relogin_on_cleanup(testcase,
                                       local_app.Api(clock=TestWallClock()))
    monitor = getattr(api, "_auto_relogin", None)
    if monitor is not None:
        monitor.stop()
    api._emit = mock.Mock()
    api._log_event = lambda *args, **kwargs: None
    api._terms_gate = lambda *args, **kwargs: None
    return api
