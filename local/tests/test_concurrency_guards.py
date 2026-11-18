#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_concurrency_guards.py（来源：test_busy_matrix.py, test_lock_order.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_busy_matrix.py ====================
"""忙碌矩阵逐格钉住：14 个动作 × 10 种「正在进行」= 140 格。

what：把「谁挡谁」矩阵一格一格钉死（block / pass / merge），因为下一批重构要把
忙碌字段从 Api 搬进协调对象，今天没有任何用例逐格守矩阵——搬错一个条件不会有
任何红。

how：只有 fixtures/busy_states.py 碰 Api 的状态字段（忙碌私有字段与 _activities/
_last_check 这类业务前置都经它摆）；本文件只负责「选动作、装哨兵、摆列状态、
断言结果」。每格用一个全新的 Api（夹具造，数据根隔离在临时目录），因此格与格
之间没有残留状态。

期望网格的来源：design/evidence/2026-11-17/api-coordination/busy.md 第二节
（手工逐函数读出来的矩阵），另见 G1–G14 判断表。凡与源码实测不一致的格子，以
源码实测为准并在该格写清 busy.md 的原值。busy.md 的「计划在跑」一列把
`_plan.published_status()` 与 `_plan_procs`（计划任务进程登记表）混在一起，
这里拆成 plan 与 plan_procs 两列分别钉。

@author Author
"""

import sys
import threading
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
LOCAL = TESTS_DIR.parent
for _path in (str(LOCAL), str(TESTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
# fixtures 目录不能单独进 sys.path：里面的 business_clock.py 会遮住 local/business_clock.py

from fixtures import busy_states  # noqa: E402

BLOCK, PASS, MERGE = "block", "pass", "merge"

# 列顺序与 busy.md 的矩阵表头一致（「计划在跑」拆成 plan 与 plan_procs 两列）：
# 关闭中 | 取消报名在途 | check 在途 | list 在途 | 单 worker 在跑 |
# 计划在跑（_plan.published_status） | 计划任务进程在跑（_plan_procs） |
# 组件事务在途 | 隧道启动中 | 更新在途
_COLUMNS = busy_states.COLUMNS

# 期望网格（busy.md 第二节，逐格按源码实测核对）：
# block = 门禁拒绝且没走到下一步；pass = 走到下一步；merge = 合并在途、不另起。
# plan_procs 列的依据：_is_busy_locked（local/app.py 4297）、
# _cancel_busy_reason_locked（2399）、_relogin_blocked_locked（1890）读它；
# check/list 自己的门、组件移除（1735）、开手机访问（G8）、_spawn_relay_worker、
# UpdateService（G12）不读它。
GRID = {
    # check：关闭/取消中拒；check 在途合并（置 _check_again）；其余放行。
    # plan_procs：check 的门（~2110）只读 _closing/_cancelling/_checking
    "check": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, MERGE, PASS, PASS, PASS, PASS, PASS, PASS, PASS))),
    # list_activities：关闭/取消中拒；list 在途合并；其余放行
    "list_activities": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, PASS, MERGE, PASS, PASS, PASS, PASS, PASS, PASS))),
    # login：关闭（G11）/取消中/_spawn 的 G1（worker/plan_procs）/计划在跑（G11）拒。
    # plan_procs：login 自身只看 _closing 与 _plan（2627-2637），随后 _spawn →
    # _is_busy_locked（4390）读 _plan_procs（4297）
    "login": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, PASS, PASS, BLOCK, BLOCK, BLOCK, PASS, PASS, PASS))),
    # grab：只有 _spawn 的 G1 门（含关闭）。
    # plan_procs：grab → _spawn → _is_busy_locked 读 _plan_procs
    "grab": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, PASS, PASS, BLOCK, BLOCK, BLOCK, PASS, PASS, PASS))),
    # start_plan：关闭/取消中（G1）/check 在途（G6）/worker/计划在跑拒。
    # plan_procs：_start_plan_inner（2884）直接调 _is_busy_locked 读 _plan_procs
    "start_plan": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, BLOCK, PASS, BLOCK, BLOCK, BLOCK, PASS, PASS, PASS))),
    # cancel_signup：G2 读关闭、取消、计划、plan_procs、worker、check/list/组件。
    # plan_procs：_cancel_busy_reason_locked（2399-2400）读 _plan_procs
    "cancel_signup": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, PASS, PASS))),
    # 组件下载：G7（关闭/组件在途）+ G1（取消/worker/计划/plan_procs）。
    # plan_procs：download_advanced_feature 走 _is_busy_locked（1435）
    "component_download": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, PASS, PASS, BLOCK, BLOCK, BLOCK, BLOCK, PASS, PASS))),
    # 组件安装：与下载同一组门（G7 + G1）。代表入口取 install_advanced_feature：
    # busy.md 的「组件安装」格读的是 _advanced_busy；enable_advanced_feature 只看
    # 关闭，属另一条设置路径，不覆盖这张矩阵。
    # plan_procs：install_advanced_feature 的门（1656）走 _is_busy_locked
    "component_install": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, PASS, PASS, BLOCK, BLOCK, BLOCK, BLOCK, PASS, PASS))),
    # 组件移除：只看关闭与 _advanced_busy，不读 G1（与技术不对称，busy.md 已记）。
    # plan_procs：移除门（1735）不读 _plan_procs
    "component_remove": dict(zip(_COLUMNS, (
        BLOCK, PASS, PASS, PASS, PASS, PASS, PASS, BLOCK, PASS, PASS))),
    # 开启手机访问：G8 = 关闭/组件在途 + 隧道启动中（只挡 cloudflare 通道）。
    # plan_procs：G8 只读 _closing/_advanced_busy/_cloudflare_starting
    "start_phone_access": dict(zip(_COLUMNS, (
        BLOCK, PASS, PASS, PASS, PASS, PASS, PASS, BLOCK, BLOCK, PASS))),
    # 停止手机访问：没有忙碌门，任何在途状态都照停。
    # plan_procs：同前，无门可读
    "stop_phone_access": dict(zip(_COLUMNS, (
        PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS))),
    # 自动重登：G3（关闭/组件/check/list/取消/worker/plan_procs）。计划在跑：
    # busy.md 第二节写 G3（login_wait 时放行）= 挡；实测 _relogin_blocked_locked
    # 只读 _login_wait_pending / _proc / _plan_procs，不读 _plan，
    # 所以空任务的计划在跑时放行（见 local/app.py 的 _relogin_blocked_locked）。
    # plan_procs：_relogin_blocked_locked（1890）读 _plan_procs → 挡
    "auto_relogin": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, PASS, BLOCK, BLOCK, PASS, PASS))),
    # 手工/手机重登：G9（关闭）+ G10（取消/check/list/worker）；计划在跑放行。
    # plan_procs：_spawn_relay_worker（4126-4128）不看 _plan_procs，
    # 计划在跑设计如此放行（busy.md 已记）
    "manual_relogin": dict(zip(_COLUMNS, (
        BLOCK, BLOCK, BLOCK, BLOCK, BLOCK, PASS, PASS, PASS, PASS, PASS))),
    # 更新检查与下载：G12 单飞；关闭拒，已在更新则合并。检查与下载共用
    # UpdateService 的同一个单飞槽位（start_check/start_download 都先过 _refuse），
    # 所以用 check_update 代表这一行；下载路径见 update_download 的同一入口。
    # plan_procs：G12 只看 UpdateService 自己的槽位与 is_closing
    "update": dict(zip(_COLUMNS, (
        BLOCK, PASS, PASS, PASS, PASS, PASS, PASS, PASS, PASS, MERGE))),
}


class _Recorder:
    """哨兵：记下「走到了忙碌门之后的下一步」，并可被别的线程唤醒。"""

    def __init__(self, result=None):
        self.result = result
        self.calls = []
        self._event = threading.Event()

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self._event.set()
        return self.result

    @property
    def called(self):
        return self._event.is_set()

    def wait(self, timeout=2.0):
        return self._event.wait(timeout)

    def reset(self):
        self.calls.clear()
        self._event.clear()


def _app():
    try:
        import app as local_app
    except Exception as exc:  # pragma: no cover - 仅在缺依赖的环境触发
        raise unittest.SkipTest("local/app.py 无法导入：%s" % exc)
    return local_app


def _patch(testcase, target, name, new, **kwargs):
    patcher = mock.patch.object(target, name, new, **kwargs)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return patcher


# ---------- 每行的入口（Api 上的真实动作；busy.md 的行） ----------

def _entry_check(api):
    return api.check(request_id="rid-check")


def _entry_list(api):
    return api.list_activities(request_id="rid-list")


def _entry_login(api):
    return api.login()


def _entry_grab(api):
    return api.grab("act-open", "矩阵测试场次")


def _entry_start_plan(api):
    return api.start_plan([{"id": "act-plan"}])


def _entry_cancel(api):
    return api.cancel_signup("act-signed")


def _entry_download(api):
    return api.download_advanced_feature("phone_control")


def _entry_install(api):
    return api.install_advanced_feature("phone_control")


def _entry_remove(api):
    return api.remove_advanced_feature("phone_control")


def _entry_start_phone(api):
    # 用 cloudflare 通道：隧道启动中的门只在这一条通道上生效
    return api.start_phone_access("cloudflare")


def _entry_stop_phone(api):
    return api.stop_phone_access()


def _entry_auto_relogin(api):
    # 走 G3（_auto_relogin_eligible）→ 预备凭据 → _relay.begin
    return api._begin_auto_relogin_once()


def _entry_manual_relogin(api):
    # 手输账号密码：G9 → 预备 → _relay.begin → G10（_spawn_relay_worker）
    return api.relogin_begin("tester", "secret")


def _entry_update(api):
    return api.check_update("rid-update")


ENTRIES = {
    "check": _entry_check,
    "list_activities": _entry_list,
    "login": _entry_login,
    "grab": _entry_grab,
    "start_plan": _entry_start_plan,
    "cancel_signup": _entry_cancel,
    "component_download": _entry_download,
    "component_install": _entry_install,
    "component_remove": _entry_remove,
    "start_phone_access": _entry_start_phone,
    "stop_phone_access": _entry_stop_phone,
    "auto_relogin": _entry_auto_relogin,
    "manual_relogin": _entry_manual_relogin,
    "update": _entry_update,
}


# ---------- 非列前置：让「没有列状态」时这一行动作本来能过忙碌门 ----------
# （_activities / _last_check 的摆法收在 fixtures/busy_states.py 的 stage_* 函数里）


def _prep_plan(testcase, api):
    busy_states.stage_plan_activity(api)
    # 真实计划只认「学校接口确认有效」这一种登录结论
    busy_states.stage_valid_check(api)


def _prep_cancel(testcase, api):
    busy_states.stage_signed_activity(api)


def _prep_download(testcase, api):
    # 源码版对组件包直接回 source_build：这一行要考的是忙碌门，不是发布形态
    _patch(testcase, _app().sys, "frozen", True, create=True)


PREP = {
    "start_plan": _prep_plan,
    "cancel_signup": _prep_cancel,
    "component_download": _prep_download,
}


# ---------- 每行的哨兵：装在忙碌门之后的那一步 ----------

def _sentinel_check(testcase, api):
    rec = _Recorder()
    api._do_check = rec              # check 过了门才起线程跑它
    return rec


def _sentinel_list(testcase, api):
    rec = _Recorder()
    api._do_list = rec               # list 过了门才起线程跑它
    return rec


def _sentinel_spawn_worker(testcase, api):
    """login / grab / 手工重登共用：真正起 worker 的 spawn_owned。

    login/grab 经 Api._spawn，手工重登经 Api._spawn_relay_worker；两者的忙碌门都在
    spawn_owned 之前。替身记录后抛 OSError，让调用方按「本机没能启动」收口，
    不产生任何真进程。
    """
    rec = _Recorder()

    def stub(*args, **kwargs):
        rec()
        raise OSError("sentinel: 忙碌门已放行，这里不该真起 worker")

    _patch(testcase, _app(), "spawn_owned", stub)
    return rec


def _sentinel_plan_start(testcase, api):
    rec = _Recorder()
    # 最终接纳与最终 busy 重检之后才 coordinator.start()
    _patch(testcase, _app().PlanCoordinator, "start", rec)
    return rec


def _sentinel_cancel(testcase, api):
    rec = _Recorder({"ok": True, "kind": "cancelled"})
    api._cancel_signup_run = rec     # 过了 G2 才真正取消
    return rec


def _sentinel_download(testcase, api):
    rec = _Recorder({"ok": True})
    api._component_service.start = rec
    return rec


def _sentinel_install(testcase, api):
    rec = _Recorder({"ok": True})
    api._install_selected_feature = rec
    return rec


def _sentinel_remove(testcase, api):
    rec = _Recorder({"ok": True})
    # 移除过了门先停手机访问，再动文件：这里就是门后的第一步
    api._stop_phone_for_component_locked = rec
    return rec


def _sentinel_start_phone(testcase, api):
    rec = _Recorder({"ok": False, "error": "sentinel"})
    api._phone.start = rec
    return rec


def _sentinel_stop_phone(testcase, api):
    rec = _Recorder({"ok": True})
    api._phone.stop = rec
    return rec


def _sentinel_auto_relogin(testcase, api):
    rec = _Recorder({"ok": True, "flow_id": "stub"})
    api._relay.begin = rec
    return rec


def _sentinel_update(testcase, api):
    rec = _Recorder({"ok": True, "queued": True, "request_id": "rid-update"})
    # UpdateService.start_check/start_download 过了 _refuse 才 _spawn 线程
    api._updates._spawn = rec
    return rec


SENTINELS = {
    "check": _sentinel_check,
    "list_activities": _sentinel_list,
    "login": _sentinel_spawn_worker,
    "grab": _sentinel_spawn_worker,
    "start_plan": _sentinel_plan_start,
    "cancel_signup": _sentinel_cancel,
    "component_download": _sentinel_download,
    "component_install": _sentinel_install,
    "component_remove": _sentinel_remove,
    "start_phone_access": _sentinel_start_phone,
    "stop_phone_access": _sentinel_stop_phone,
    "auto_relogin": _sentinel_auto_relogin,
    "manual_relogin": _sentinel_spawn_worker,
    "update": _sentinel_update,
}


# ---------- 合并格的附加断言：合并的痕迹要真的留下 ----------

def _merge_check_again(testcase, api, result):
    testcase.assertTrue(api._check_again, "check 在途必须记下「本轮收尾再补查一次」")


def _merge_list_skipped(testcase, api, result):
    testcase.assertEqual(result.get("skipped"), "已经在拉活动列表")
    testcase.assertTrue(api._listing, "合并不清在途标记，等原来那轮收尾")


def _merge_update_singleflight(testcase, api, result):
    testcase.assertTrue(result.get("skipped"), result)
    testcase.assertTrue(api._updates._updating, "合并不释放更新单飞槽位")


MERGE_CHECKS = {
    "check": _merge_check_again,
    "list_activities": _merge_list_skipped,
    "update": _merge_update_singleflight,
}


def _assert_cell(testcase, expect, rec, result):
    """按 block / pass / merge 断言一格。"""
    if expect == BLOCK:
        testcase.assertFalse(rec.called, "门禁该拒却走到了下一步：%r" % (result,))
        testcase.assertFalse(result.get("ok"), "拒绝必须是 ok=False：%r" % (result,))
        return
    if expect == PASS:
        testcase.assertTrue(rec.wait(), "门禁该放行却没走到下一步：%r" % (result,))
        return
    # merge：不另起一轮，原在途那一轮继续
    testcase.assertFalse(rec.called, "该合并在途却被当成新动作放行：%r" % (result,))
    testcase.assertTrue(result.get("ok"), "合并回执必须 ok=True：%r" % (result,))
    testcase.assertTrue(result.get("skipped"), "合并回执要带 skipped：%r" % (result,))


def _reset_busy_columns(api):
    """复位 10 列忙碌状态与合并副产物，使同一行的 BLOCK/MERGE 格可复用同一个 Api 实例。"""
    api._closing = False
    api._cancelling = False
    api._checking = False
    api._check_again = False
    api._check_request_id = ""
    api._listing = False
    api._list_request_id = ""
    api._proc = None
    api._plan = None
    api._plan_procs = {}
    api._advanced_busy = False
    api._cloudflare_starting = False
    api._updates._updating = False
    api._updates._update_request_id = ""


def _drive(testcase, row):
    """逐列跑一行：BLOCK/MERGE 格复用同一行 Api 并复位列状态；PASS 格会产生动作副作用，单独构造。"""
    shared_api = busy_states.build(testcase)
    prep = PREP.get(row)
    if prep is not None:
        prep(testcase, shared_api)
    shared_rec = SENTINELS[row](testcase, shared_api)
    for column in _COLUMNS:
        expect = GRID[row][column]
        with testcase.subTest(row=row, column=column):
            if expect == PASS:
                api = busy_states.build(testcase)
                if prep is not None:
                    prep(testcase, api)
                rec = SENTINELS[row](testcase, api)
            else:
                api = shared_api
                rec = shared_rec
                rec.reset()
                _reset_busy_columns(api)
            busy_states.put(api, column)
            result = ENTRIES[row](api)
            _assert_cell(testcase, expect, rec, result)
            if expect == MERGE:
                MERGE_CHECKS[row](testcase, api, result)


class BusyMatrixTests(unittest.TestCase):
    """14 行 × 10 列，一格一个 subTest。每行的期望见 GRID 上方注释。"""

    def test_grid_is_14_rows_by_10_columns(self):
        """矩阵形状必须正好 14×10=140 格，少一格就等于漏钉。"""
        self.assertEqual(len(GRID), 14, "行数必须是 14")
        cells = 0
        for row, columns in GRID.items():
            self.assertEqual(tuple(columns), tuple(_COLUMNS), "%s 的列不齐" % row)
            self.assertTrue(set(columns.values()) <= {BLOCK, PASS, MERGE},
                            "%s 出现未知结论：%s" % (row, set(columns.values())))
            cells += len(columns)
        self.assertEqual(cells, 140, "格子总数必须是 140")

    def test_row_check(self):
        _drive(self, "check")

    def test_row_list_activities(self):
        _drive(self, "list_activities")

    def test_row_login(self):
        _drive(self, "login")

    def test_row_grab(self):
        _drive(self, "grab")

    def test_row_start_plan(self):
        _drive(self, "start_plan")

    def test_row_cancel_signup(self):
        _drive(self, "cancel_signup")

    def test_row_component_download(self):
        _drive(self, "component_download")

    def test_row_component_install(self):
        _drive(self, "component_install")

    def test_row_component_remove(self):
        _drive(self, "component_remove")

    def test_row_start_phone_access(self):
        _drive(self, "start_phone_access")

    def test_row_stop_phone_access(self):
        _drive(self, "stop_phone_access")

    def test_row_auto_relogin(self):
        _drive(self, "auto_relogin")

    def test_row_manual_relogin(self):
        _drive(self, "manual_relogin")

    def test_row_update(self):
        _drive(self, "update")

# ==================== 源自 test_lock_order.py ====================
"""锁序守卫：本仓库的锁只许按固定等级「由外层向里层」升序获取。

拆分 Api 时最大的风险是锁悄悄换了位置：把某段临界区搬进服务后，外层锁与内层锁的
先后关系一反转，现有用例照样全绿——因为死锁只在真并发下出现，而且往往几百次里才
撞上一次。本文件只读源码（ast 解析，绝不 import 产品代码），守三条不变量：

1. 等级只升：持等级 N 的锁时，只能再拿等级 > N 的锁（嵌套越深，号只会变大）。
   Api 与各服务类内部都查：每个 `with` 块的直接嵌套、以及块内经同类方法往下追
   ≤6 层拿到的锁都要升序；同号重入只允许冻结表里的 RLock 既有重入。
2. 协调锁不碰服务：持 `Api._lock` 期间只许调 `self._plan.published_status()`——
   它读的是锁外发布的不可变状态。别的服务调用一律不许进来，否则「Api 锁 → 服务锁」
   会和服务里「服务锁 → 回调 Api」的那条边成环。
3. 服务锁不碰注入端口：服务拿着自己的锁（或叶子锁）时不许调构造注入的端口——
   端口是界面层塞进来的回调，一旦它在里面反手取 Api 锁，环就成立。只有逐条核对
   过「它自己不取跨层锁」的叶子端口才在白名单里；唯一例外是发布端口 emit——
   已逐条核对过「持发布锁调它只会再取更高等级的锁」，记在 ORDERED_PORTS。

等级表（2026-11-23 发布锁定级返修：`_publish` 持发布锁调 emit 端口，端口接到
app.py:2958 的闭包会拿 Api._lock 与服务/事件锁，故发布锁必须在协调锁之外；
Api._lock 的取证见 design/evidence/2026-11-17/api-coordination/locks.md）：

    1  Api._credential_lock          凭据锁 Lock
    2  Api._phone_access_lock        手机访问锁 Lock
    3  PlanCoordinator._emit_lock    发布锁 Lock（_publish 持它调 emit 端口，
                                    端口实际会拿 Api._lock 与服务/事件锁）
    4  Api._lock                     协调锁 Lock（证据计 96 处 with / 64 个方法；
                                    嵌套 def 的获取处在证据里被重复归属，本扫描器
                                    按唯一获取处计 93 处）。第一批拆分后实体在
                                    application/coordination.py 的 Coordinator._lock，
                                    Api._lock 指向同一对象（属性别名）
    5  服务锁：LoginRelayService / AutoReloginMonitor / PhoneAccessService /
       AdvancedComponentService / UpdateService / PlanCoordinator 的 `_lock`
    6  叶子锁：PhoneAccessService._event_lock、模块级 _PHONE_LOG_LOCK 与
       _LIFECYCLE_LOCK

开工 HEAD 上就存在、但不在这一批修的存量违例记在冻结表里：实际必须**恰好**等于
冻结表——多一条说明这一批改坏了，少一条说明存量已经消失，要把对应条目删掉。

扫描口径（写清楚才守得住）：规则一同时看 Api 与 SERVICE_FILES 里的每个服务类——
直接嵌套的 `with` 与「经同类方法链 ≤6 层」拿到的锁都算；update_service 的模块级
函数（run_check/run_download/run_version_download）里 `state.X` 沿既有约定当
`self.X` 对待。嵌套 def 里的调用不算外层块的调用（闭包定义时不持锁）。规则二只看
Api；规则三进服务类，其中「持 _emit_lock 调 emit」单独记进 ORDERED_PORTS。另有
一道独立断言钉住 P2-1：PlanCoordinator 对 `self._publish` 的调用（直接、或经同类
方法链 ≤6 层追到的）一律不许出现在 `with self._lock:` 块内——状态写入在锁内、
事件发布在锁外；谁把发布挪进锁内，这道断言与规则一（_lock(5)→_emit_lock(3)
降级）两道都抓。

@author Author
"""

import ast

TESTS_DIR = Path(__file__).resolve().parent
LOCAL_DIR = TESTS_DIR.parent
APP_FILE = LOCAL_DIR / "app.py"

# 服务模块：锁等级 5/6 的持有者（相对 local/ 的路径即源码里的模块键）
SERVICE_FILES = (
    "application/coordination.py",
    "application/component_actions.py",
    "application/login_recovery.py",
    "application/activity_list_service.py",
    "application/plan_admission.py",
    "application/signup_cancellation.py",
    "application/worker_service.py",
    "application/desktop_lifecycle.py",
    "application/clock_service.py",
    "application/login_relay_service.py",
    "application/auto_relogin.py",
    "application/phone_access_session.py",
    "application/phone_service.py",
    "application/advanced_component_service.py",
    "application/update_service.py",
    "application/plan_service.py",
    "signup_plan.py",
)

# 等级表：键是「类名.属性名」，模块级锁直接用名字
LEVELS: dict[str, int] = {
    "Api._credential_lock": 1,
    "Api._phone_access_lock": 2,
    "PlanCoordinator._emit_lock": 3,
    "Api._lock": 4,
    # 第一批拆分后协调锁的实体在 Coordinator；Api._lock 是同一对象的属性别名
    # （`self._lock = self._coord.lock`），两者同号同锁，升序判定按同一等级比较。
    "Coordinator._lock": 4,
    "LoginRelayService._lock": 5,
    "AutoReloginMonitor._lock": 5,
    "PhoneAccessService._lock": 5,
    "AdvancedComponentService._lock": 5,
    "UpdateService._lock": 5,
    "PlanCoordinator._lock": 5,
    "PhoneAccessService._event_lock": 6,
    "_PHONE_LOG_LOCK": 6,
    "_LIFECYCLE_LOCK": 6,
}

SERVICE_CLASSES = (
    "Coordinator", "ComponentActions", "PhoneAccessController", "LoginRecovery", "ActivityListService", "LoginRelayService", "AutoReloginMonitor", "PhoneAccessService",
    "AdvancedComponentService", "UpdateService", "PlanCoordinator", "PlanAdmission", "SignupCancellation",
    "WorkerService", "DesktopLifecycle", "ClockService",
)

# 三条旧重入已改为持锁调用不再取锁的停机入口；后续不得新增同号重入。
FROZEN_REENTRY: tuple[tuple[str, str, str], ...] = ()

# 服务类内部的同号重入（均为 RLock 的既有重入）：实际必须恰好等于这张表。
# 键是「类.方法」——服务类之间方法重名（如 snapshot），裸方法名分不清归属。
FROZEN_SERVICE_REENTRY: tuple[tuple[str, str, str], ...] = (
    # signup_plan.py cancel_task:380 —— 持 _lock 调 _set_state_locked，它在
    # signup_plan.py:537 自己再进一次 _lock（RLock 重入；锁内只改状态不回调）
    ("PlanCoordinator.cancel_task", "PlanCoordinator._lock", "PlanCoordinator._lock"),
    # signup_plan.py stop:395 —— 停止路径在锁内把未启动场次落终态，同上调
    # _set_state_locked:537 再进一次 _lock
    ("PlanCoordinator.stop", "PlanCoordinator._lock", "PlanCoordinator._lock"),
)

# 持协调锁时唯一放行的服务调用：published_status 只读锁外发布的不可变字符串，
# 以及协调对象自己的两个 _locked 判定（第一批拆分后的薄转发：判定体在
# Coordinator 里，不带 `with`，调用方持锁的约定沿用原名）。
FROZEN_COORD_CALLS: tuple[tuple[str, str], ...] = (
    ("_published_plan_state", "self._plan.published_status"),
    # app.py _cancel_busy_reason_locked：旧名转发 Coordinator.cancel_busy_reason_locked
    ("cancel", "self._coord.cancel_busy_reason_locked"),
    ("_busy_gate_locked", "self._coord.is_busy_locked"),
    # app.py _is_busy_locked：旧名转发 Coordinator.is_busy_locked（busy 判定只读已发布状态，P2-1）
    ("_is_busy_locked", "self._coord.is_busy_locked"),
    # app.py login（持 _lock 复核计划是否在跑）
    ("login", "self._plan.published_status"),
)

# 叶子端口白名单：逐条核对过「它自己不取跨层锁」的注入端口。
# 键是（类, 端口属性）；注释写清真实接线与为什么不构成环。
LEAF_PORTS: tuple[tuple[str, str], ...] = (
    # 接线 app.py:960 now=time.monotonic：只读单调钟，不取任何锁
    ("LoginRelayService", "_now"),
    # 接线 app.py:973 now=time.monotonic：同上
    ("AutoReloginMonitor", "_now"),
    # 接线 app.py:900 now=self._clock_now → business_clock.BusinessClock.now:307，
    # 只可重入自己的 RLock（叶子，持锁期间不外调），5→叶子 是升序
    ("PhoneAccessService", "_now"),
    # 接线 app.py:975 log=self._log_event:1949：只拿 grab.log 的跨进程文件锁（叶子）
    ("AutoReloginMonitor", "_log"),
    # 接线 app.py:902 log=phone_log:151：只拿 _PHONE_LOG_LOCK（等级 6 叶子）
    ("PhoneAccessService", "_log"),
    # 接线 app.py:883 is_closing=self._update_is_closing:2055：只读一个布尔，不取锁
    ("UpdateService", "_is_closing"),
    # 接线 AdvancedComponentService 未注入 version → component_packages.version:88，
    # 只读 VERSION 文件，无锁
    ("AdvancedComponentService", "_version"),
)

# 已核对过取锁顺序的发布端口（键：(模块, 方法, 端口)）：持 _emit_lock（等级 3）
# 调它们时，端口接到的代码只会再取更高等级的锁，顺序成立不成环。这张表必须与
# 扫描器实际发现的「持 _emit_lock 调端口」恰好相等；存量消失时条目只许删。
ORDERED_PORTS: tuple[tuple[str, str, str], ...] = (
    # signup_plan.py _publish:353 持 _emit_lock 调 emit 端口。端口接到 app.py:2958
    # _start_plan_inner 里定义的闭包：非 plan_done 事件先在 with self._lock
    # （app.py:2968，等级 4）里对账，再调 Api._emit（app.py:1094）；plan_done
    # 路径在 app.py:2983 再进 with self._lock。Api._emit 又会碰
    # LoginRelayService 的状态投影（relay._lock，等级 5）与
    # PhoneAccessService.record_event（_event_lock，等级 6）。这些锁全都高于
    # 持有的 _emit_lock（3），等级只升、不成环——这正是发布锁必须排在协调锁
    # 之外的原因。
    ("signup_plan.py", "_publish", "emit"),
)

# 服务锁期间调端口的冻结老账：(模块, 方法, 端口)。每条都是既存事实，不在这一批修。
# 原第四条（signup_plan.py _publish 持 _emit_lock 调 emit）经取锁顺序核对后
# 挪进上面的 ORDERED_PORTS——它是发布锁定级的依据，不是待修存量。
FROZEN_PORTS: tuple[tuple[str, str, str], ...] = (
    # advanced_component_service.py snapshot:138 → _refresh_idle_state:112 取 _status，
    # 而 _status 实际是 component_packages.feature_status → status:701 会取 _LOCK
    ("application/advanced_component_service.py", "snapshot", "_status"),
    # phone_service.py pair:280 持 _lock 写设备信任，PhoneSessionStore.add_device:62
    # 取自己的 RLock（等级表外的底层锁）
    ("application/phone_access_session.py", "pair", "_device_store"),
    # phone_service.py authenticate_or_restore:369 同上，validate_device:82 取同一把锁
    ("application/phone_access_session.py", "authenticate_or_restore", "_device_store"),
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _dotted(node: ast.AST) -> str:
    """`self._relay.cancel` 这类属性链拼成点号串；拼不出来返回空串。"""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return ""
    parts.append(node.id)
    return ".".join(reversed(parts))


def _last_name(node: ast.AST) -> str:
    """表达式链尾的名字：`_update_service.UpdateService` → `UpdateService`。"""
    dotted = _dotted(node)
    return dotted.rsplit(".", 1)[-1] if dotted else ""


def _lock_id(expr: ast.AST, owner: str | None, module: str) -> str | None:
    """`with` 目标表达式 → 等级表里的锁名字；认不出返回 None。

    - `self.<attr>`：归属当前类（Api 或某个服务类）；
    - 模块级 `_XXX_LOCK`：名字本身；
    - update_service 里的 `state._lock`：那个 `state` 就是 UpdateService 实例；
    - plan_service.run_plan_task 的 `lock` 形参：唯一调用方传的是 Api._lock
      （app.py:4313），因此按 Api._lock 计获取处；它不参与规则一的嵌套分析。
    """
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        base, attr = expr.value.id, expr.attr
        if base == "self" and owner == "ComponentActions":
            aliases = {"_credential_lock": "Api._credential_lock",
                       "_phone_lock": "Api._phone_access_lock", "_lock": "Api._lock"}
            if attr in aliases:
                return aliases[attr]
        if base == "self" and owner == "PhoneAccessController":
            aliases = {"_lock": "Api._phone_access_lock", "_coord_lock": "Api._lock"}
            if attr in aliases:
                return aliases[attr]
        if base == "self" and owner in ("LoginRecovery", "ActivityListService", "PlanAdmission", "SignupCancellation",
                                         "WorkerService", "DesktopLifecycle", "ClockService") and attr == "_lock":
            return "Api._lock"
        if base == "owner" and owner == "PlanEvents" and attr == "_lock":
            return "Api._lock"
        lock = ""
        if base == "self" and owner:
            lock = "%s.%s" % (owner, attr)
        elif base == "state" and module == "application/update_service.py":
            lock = "UpdateService.%s" % attr
        return lock if lock in LEVELS else None
    if isinstance(expr, ast.Name):
        if expr.id == "lock" and module == "application/plan_service.py":
            return "Api._lock"
        return expr.id if expr.id in LEVELS else None
    return None


def _iter_withs(fn: ast.AST, owner: str | None, module: str):
    """函数体里每个 `with`：产出 (节点, 外层锁元组, 本块锁元组)。

    嵌套 def 里的 `with` 也计入（它确实在同一个实例上取同一把锁），但外层锁从零
    算起——闭包是定义时创建、调用时才执行，定义它的那一刻并不持锁。

    `with A, B:` 按书写顺序当作「先 A 后 B」依次获取：本仓库的多项目写法只有
    「凭据锁 → 手机访问锁」（1→2，升序）与「Api 锁 → 服务锁」，所以按顺序比较
    既符合实际也可能被破坏。`with (...)` 的换行写法由 ast 归一，同样适用。
    """
    found: list[tuple[ast.With, tuple[str, ...], tuple[str, ...]]] = []

    def visit(node: ast.AST, outer: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, ())
                continue
            if isinstance(child, ast.Lambda):
                continue
            if isinstance(child, ast.With):
                ids = tuple(lock for lock in (_lock_id(item.context_expr, owner, module)
                                              for item in child.items) if lock)
                found.append((child, outer, ids))
                visit(child, outer + ids)
            else:
                visit(child, outer)

    visit(fn, ())
    return found


def _calls_in(node: ast.AST):
    """块内（语句级包含）的 Call 节点；嵌套 def/类的函数体不算——定义时不执行。"""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                              ast.Lambda)):
            continue
        if isinstance(child, ast.Call):
            yield child
        yield from _calls_in(child)


class _LockGraph:
    """一次扫描的索引：类、方法、服务属性、锁获取处，以及同类的调用闭包。"""

    def __init__(self, trees: dict[str, ast.Module]):
        self.trees = trees
        self.classes: dict[tuple[str, str], ast.ClassDef] = {}
        self.functions: dict[tuple[str, str], ast.AST] = {}
        for module, tree in trees.items():
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    self.classes[(module, node.name)] = node
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.functions[(module, node.name)] = node
        self.api_key = ("app.py", "Api")
        self._methods: dict[tuple[str, str], dict[str, ast.AST]] = {}
        self._attrs: dict[str, tuple[str, str]] | None = None

    def methods(self, key: tuple[str, str]) -> dict[str, ast.AST]:
        if key not in self._methods:
            cls = self.classes.get(key)
            self._methods[key] = {} if cls is None else {
                node.name: node for node in cls.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        return self._methods[key]

    def _ctor(self, value: ast.AST, fn: ast.AST) -> tuple[str, str] | None:
        """构造调用 → (模块, 类名)：认服务类名，也认先把实例存局部变量再赋值的写法。"""
        if isinstance(value, ast.Call):
            if _dotted(value.func) == "self._make_component_actions":
                return self._known("ComponentActions")
            if _dotted(value.func) == "self._make_phone_controller":
                return self._known("PhoneAccessController")
            if _dotted(value.func) == "self._make_login_recovery":
                return self._known("LoginRecovery")
            if _dotted(value.func) == "self._make_activity_list":
                return self._known("ActivityListService")
            if _dotted(value.func) == "self._make_plan_manager":
                return self._known("PlanAdmission")
            if _dotted(value.func) == "self._make_signup_cancellation":
                return self._known("SignupCancellation")
            if _dotted(value.func) == "self._make_worker_service":
                return self._known("WorkerService")
            if _dotted(value.func) == "self._make_desktop_lifecycle":
                return self._known("DesktopLifecycle")
            if _dotted(value.func) == "self._make_clock_service":
                return self._known("ClockService")
            return self._known(_last_name(value.func))
        if isinstance(value, ast.Name):
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                    continue
                if any(isinstance(t, ast.Name) and t.id == value.id for t in node.targets):
                    return self._known(_last_name(node.value.func))
        return None

    def _known(self, name: str) -> tuple[str, str] | None:
        for key in self.classes:
            if key[1] == name and name in SERVICE_CLASSES:
                return key
        return None

    def service_attrs(self) -> dict[str, tuple[str, str]]:
        """Api 的 `self.<属性>` → 服务类。来源是 Api 各方法里的 `self.x = 构造()`。"""
        if self._attrs is not None:
            return self._attrs
        mapping: dict[str, tuple[str, str]] = {}
        for fn in self.methods(self.api_key).values():
            for node in ast.walk(fn):
                if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                    continue
                target = node.targets[0]
                if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                        and target.value.id == "self"):
                    continue
                key = self._ctor(node.value, fn)
                if key is not None:
                    mapping[target.attr] = key
        if "_plan_manager" in mapping and ("application/plan_admission.py", "PlanFields") in self.classes:
            mapping["_plan"] = self._known("PlanCoordinator")
        self._attrs = mapping
        return mapping

    def service_keys(self) -> list[tuple[str, str]]:
        return [key for key in self.classes if key[1] in SERVICE_CLASSES or key == ("application/plan_admission.py", "PlanEvents")]

    def closure_locks(self, key: tuple[str, str], method: str, depth: int = 0,
                      seen: frozenset[str] = frozenset()) -> set[str]:
        """方法（含同类方法调用，6 层）可能获取的锁；认不出就是空集。"""
        fn = self.methods(key).get(method)
        if fn is None or depth > 6 or method in seen:
            return set()
        out = {lock for _, _, ids in _iter_withs(fn, key[1], key[0]) for lock in ids}
        for call in _calls_in(fn):
            parts = _dotted(call.func).split(".")
            if len(parts) == 2 and parts[0] == "self" and parts[1] in self.methods(key):
                out |= self.closure_locks(key, parts[1], depth + 1, seen | {method})
            elif key == self.api_key and len(parts) == 3 and parts[0] == "self":
                target = self.service_attrs().get(parts[1])
                if target is not None:
                    out |= self.closure_locks(target, parts[2], depth + 1)
        return out

    def callee_locks(self, call: ast.Call) -> set[str]:
        """块内一次调用可能获取的锁：Api 方法链（≤6 层）或一层进服务类。"""
        parts = _dotted(call.func).split(".")
        if len(parts) == 2 and parts[0] == "self":
            return self.closure_locks(self.api_key, parts[1])
        if len(parts) == 3 and parts[0] == "self":
            key = self.service_attrs().get(parts[1])
            if key is not None:
                return self.closure_locks(key, parts[2])
        return set()

    def ports(self, key: tuple[str, str]) -> dict[str, str]:
        """构造注入的端口：`__init__` 形参被赋到哪个 self 属性上。

        认 `self._x = param`、`self._x = param or 默认`、`self.x = param if ... else ...`；
        `self._next = now() + 1` 这种「用形参算出的值」不算端口（它不可调用）。
        """
        fn = self.methods(key).get("__init__")
        if fn is None:
            return {}
        params = {arg.arg for arg in list(fn.args.args) + list(fn.args.kwonlyargs)}
        params.discard("self")
        found: dict[str, str] = {}
        for node in ast.walk(fn):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            attr = next((t.attr for t in targets if isinstance(t, ast.Attribute)
                         and isinstance(t.value, ast.Name) and t.value.id == "self"), "")
            param = _port_param(node.value, params)
            if attr and param:
                found[attr] = param
        return found

    def acquisitions(self) -> dict[str, int]:
        """每把锁的获取处（`with` 里的一项算一处，多项目按书写顺序各算一处）。"""
        counts: dict[str, int] = {}
        for (module, _name), fn in self.functions.items():
            for _, _, ids in _iter_withs(fn, None, module):
                for lock in ids:
                    counts[lock] = counts.get(lock, 0) + 1
        for key in self.classes:
            for fn in self.methods(key).values():
                for _, _, ids in _iter_withs(fn, key[1], key[0]):
                    for lock in ids:
                        counts[lock] = counts.get(lock, 0) + 1
        return counts

    def blocks(self):
        """全部 `with`：产出 (模块, 归属方法名, 节点, 外层锁, 本块锁)。"""
        for (module, name), fn in self.functions.items():
            for node, outer, ids in _iter_withs(fn, None, module):
                yield module, name, node, outer, ids
        for key in self.classes:
            for name, fn in self.methods(key).items():
                for node, outer, ids in _iter_withs(fn, key[1], key[0]):
                    yield key[0], name, node, outer, ids


def _port_param(value: ast.AST, params: set[str]) -> str:
    """赋值右侧是不是「就是这个形参」：Name / `param or 默认` / `param if .. else ..`。"""
    if isinstance(value, ast.Name):
        return value.id if value.id in params else ""
    if isinstance(value, ast.BoolOp) and isinstance(value.values[0], ast.Name):
        return value.values[0].id if value.values[0].id in params else ""
    if isinstance(value, ast.IfExp) and isinstance(value.body, ast.Name):
        return value.body.id if value.body.id in params else ""
    return ""


def _deepest(holding) -> str | None:
    """当前最深的那把锁（等级最高者）——后拿的锁只需比它大。"""
    locks = list(holding)
    return max(locks, key=lambda lock: LEVELS[lock]) if locks else None


def _judge(record: dict, method: str, line: int, holding, inner: str) -> None:
    base = _deepest(holding)
    if base is None:
        return
    if LEVELS[inner] < LEVELS[base]:
        record["down"].append((method, line, base, inner))
    elif LEVELS[inner] == LEVELS[base]:
        record["equal"].append((method, line, base, inner))


def _rule_one(graph: _LockGraph) -> dict[str, list[tuple]]:
    """持等级 N 时只许拿等级 > N：直接嵌套 + Api 方法链 + 一层进服务类。"""
    record: dict[str, list[tuple]] = {"down": [], "equal": []}
    for name, fn in graph.methods(graph.api_key).items():
        for node, outer, ids in _iter_withs(fn, "Api", "app.py"):
            holding = list(outer)
            for inner in ids:
                _judge(record, name, node.lineno, holding, inner)
                holding.append(inner)      # `with A, B:` 按书写顺序当作依次获取
            for call in _calls_in(node):
                for lock in graph.callee_locks(call):
                    _judge(record, name, call.lineno, holding, lock)
    return {kind: sorted(set(items)) for kind, items in record.items()}


def _rule_one_services(graph: _LockGraph) -> dict[str, list[tuple]]:
    """规则一的服务类部分：SERVICE_FILES 每个服务类内部等级只许升。

    与 Api 同口径：每个 `with` 块的直接嵌套、以及块内经同类方法（≤6 层）拿到的
    锁都要升序。记录的归属名是「类.方法」（服务类之间方法重名，裸名分不清）。
    update_service 的模块级函数（run_check/run_download/run_version_download）
    里 `state._lock` 就是那个 UpdateService 实例的锁、`state.X()` 就是它的方法
    （既有约定，见 _lock_id 的注释），按同类规则查。
    """
    record: dict[str, list[tuple]] = {"down": [], "equal": []}

    def scan(fn: ast.AST, key: tuple[str, str], label: str, base: str) -> None:
        for node, outer, ids in _iter_withs(fn, key[1], key[0]):
            holding = list(outer)
            for inner in ids:
                _judge(record, label, node.lineno, holding, inner)
                holding.append(inner)
            for call in _calls_in(node):
                parts = _dotted(call.func).split(".")
                if len(parts) == 2 and parts[0] == base and parts[1] in graph.methods(key):
                    for lock in graph.closure_locks(key, parts[1]):
                        _judge(record, label, call.lineno, holding, lock)
                if key == ("application/component_actions.py", "ComponentActions"):
                    for lock in _component_port_locks(graph, call):
                        _judge(record, label, call.lineno, holding, lock)
                if key == ("application/phone_service.py", "PhoneAccessController"):
                    for lock in _component_port_locks(graph, call, "_make_phone_controller", "PhoneAccessController"):
                        _judge(record, label, call.lineno, holding, lock)
                if key == ("application/worker_service.py", "WorkerService"):
                    for lock in _component_port_locks(graph, call, "_make_worker_service", "WorkerService"):
                        _judge(record, label, call.lineno, holding, lock)

    for key in graph.service_keys():
        for name, fn in graph.methods(key).items():
            scan(fn, key, "%s.%s" % (key[1], name), "self")
    state_key = ("application/update_service.py", "UpdateService")
    for (module, name), fn in graph.functions.items():
        if module == state_key[0]:
            scan(fn, state_key, name, "state")
    return {kind: sorted(set(items)) for kind, items in record.items()}


def _component_port_locks(graph: _LockGraph, call: ast.Call,
                          factory_name="_make_component_actions", class_name="ComponentActions") -> set[str]:
    """沿组合根注入的组件回调追踪锁，保留调用方已持有的物理锁。"""
    func = call.func
    group = ""
    if isinstance(func, ast.Subscript) and isinstance(func.slice, ast.Constant):
        group, name = _dotted(func.value).removeprefix("self._"), func.slice.value
    else:
        dotted = _dotted(func)
        if not dotted.startswith("self._"):
            return set()
        name = dotted.removeprefix("self._")
    factory = graph.methods(graph.api_key).get(factory_name)
    if factory is None:
        return set()
    result = set()
    for constructor in _calls_in(factory):
        if _last_name(constructor.func) != class_name:
            continue
        for keyword in constructor.keywords:
            value = keyword.value
            if group and keyword.arg == group and isinstance(value, ast.Call):
                method = _dotted(value.func).removeprefix("self.")
                helper = graph.methods(graph.api_key).get(method)
                value = next((n.value for n in helper.body if isinstance(n, ast.Return)), None) if helper else None
            if keyword.arg == group and isinstance(value, ast.Dict):
                value = next((v for k, v in zip(value.keys, value.values)
                              if isinstance(k, ast.Constant) and k.value == name), None)
            elif group or keyword.arg != name:
                continue
            if not isinstance(value, ast.Lambda):
                continue
            for target in _calls_in(value):
                parts = _dotted(target.func).split(".")
                if len(parts) == 2 and parts[0] == "self":
                    result |= graph.closure_locks(graph.api_key, parts[1])
                elif len(parts) == 3 and parts[0] == "self":
                    key = graph.service_attrs().get(parts[1])
                    if key:
                        result |= graph.closure_locks(key, parts[2])
    return result


def _service_calls(graph: _LockGraph, node: ast.AST, attrs, owner: str,
                   depth: int = 0, seen: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    """块内对 `self.<服务>.<方法>()` 的调用；经 Api 方法最多追 6 层。

    owner 是这条调用**写在哪个方法里**（追进去以后就换成被调方法），这样冻结表
    记的是真实源码位置，而不是从哪个入口一路持锁下来的。
    """
    out: list[tuple[str, str]] = []
    for call in _calls_in(node):
        dotted = _dotted(call.func)
        parts = dotted.split(".")
        if len(parts) == 3 and parts[0] == "self" and parts[1] in attrs:
            out.append((owner, dotted))
        elif len(parts) == 2 and parts[0] == "self" and parts[1] in graph.methods(graph.api_key):
            if depth < 6 and parts[1] not in seen:
                callee = graph.methods(graph.api_key)[parts[1]]
                out += _service_calls(graph, callee, attrs, parts[1],
                                      depth + 1, seen | {parts[1]})
    return out


def _rule_two(graph: _LockGraph) -> list[tuple[str, str]]:
    """持 Api._lock 时只许调 self._plan.published_status()。

    只认 `self.<服务属性>.<方法>()` 这种写法：`plan = self._plan` 的局部别名
    （app.py 里 7 处 snapshot/start）不追。开工 HEAD 上这 7 处全部落在 with 之外
    （逐个核过外层 with 栈为空）；将来若有人在持锁块里用别名调服务，规则二看不见
    ——真要这么改，先把别名解析补进这里。
    """
    attrs = graph.service_attrs()
    hits: list[tuple[str, str]] = []
    for name, fn in graph.methods(graph.api_key).items():
        for node, _outer, ids in _iter_withs(fn, "Api", "app.py"):
            if "Api._lock" in ids:
                hits.extend(_service_calls(graph, node, attrs, name))
    # 计划与取消服务持有的 _lock 就是同一协调锁；追踪其同类方法，
    # 避免迁移后只扫描 Api 而漏掉真实临界区。
    def service_calls(key, node, owner, seen=frozenset()):
        found = []
        for call in _calls_in(node):
            dotted = _dotted(call.func)
            if dotted.startswith("self._coord.") and len(dotted.split(".")) == 3:
                found.append((owner, dotted))
            parts = dotted.split(".")
            if len(parts) == 2 and parts[0] == "self" and parts[1] not in seen:
                target = graph.methods(key).get(parts[1])
                if target:
                    found.extend(service_calls(key, target, parts[1], seen | {parts[1]}))
        return found

    for class_name in ("PlanAdmission", "SignupCancellation", "WorkerService", "DesktopLifecycle", "ClockService"):
        key = graph._known(class_name)
        if key is None:
            continue
        for name, fn in graph.methods(key).items():
            for node, _outer, ids in _iter_withs(fn, class_name, key[0]):
                if "Api._lock" in ids:
                    hits.extend(service_calls(key, node, name, frozenset({name})))
    # Coordinator 的两个判定由调用者持同一把锁；追踪注入的计划状态端口。
    key = attrs.get("_coord")
    init = graph.methods(graph.api_key).get("__init__")
    if key and init:
        for call in _calls_in(init):
            if _last_name(call.func) != "Coordinator":
                continue
            for keyword in call.keywords:
                if keyword.arg == "plan_state" and _dotted(keyword.value).startswith("self."):
                    port = _dotted(keyword.value).split(".")[-1]
                    for method in ("is_busy_locked", "cancel_busy_reason_locked"):
                        fn = graph.methods(key).get(method)
                        if fn and any(_dotted(c.func) == "self._plan_state" for c in _calls_in(fn)):
                            target = graph.methods(graph.api_key).get(port)
                            if target:
                                hits.extend(_service_calls(graph, target, attrs, port))
    return sorted(set(hits))


def _port_calls(graph: _LockGraph, key: tuple[str, str], node: ast.AST, ports,
                depth: int = 0, seen: frozenset[str] = frozenset()) -> list[tuple[int, str]]:
    """块内对注入端口的调用（含同类方法递归 6 层，端口按属性名归一）。"""
    out: list[tuple[int, str]] = []
    for call in _calls_in(node):
        parts = _dotted(call.func).split(".")
        if len(parts) < 2 or parts[0] not in ("self", "state"):
            continue
        attr = parts[1]
        if attr in ports:
            out.append((call.lineno, attr))
        elif depth < 6 and parts[1] in graph.methods(key) and parts[1] not in seen:
            callee = graph.methods(key)[parts[1]]
            out += _port_calls(graph, key, callee, ports, depth + 1, seen | {parts[1]})
    return out


def _rule_three(graph: _LockGraph) -> set[tuple[str, str, str, str]]:
    """服务持自己的锁（或叶子锁）时调了哪些注入端口：(模块, 类, 方法, 端口)。"""
    found: set[tuple[str, str, str, str]] = set()
    for key in graph.service_keys():
        ports = graph.ports(key)
        for name, fn in graph.methods(key).items():
            for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
                if not any(lock.startswith(key[1] + ".") for lock in ids):
                    continue
                for _line, port in _port_calls(graph, key, node, ports):
                    found.add((key[0], key[1], name, port))
    # update_service 的 run_check/run_download 是模块级函数，`state._lock` 就是
    # 那个 UpdateService 实例的锁：按同类规则查（模块级函数里没有 self）。
    key = ("application/update_service.py", "UpdateService")
    ports = graph.ports(key)
    for (module, name), fn in graph.functions.items():
        if module != key[0]:
            continue
        for node, _outer, ids in _iter_withs(fn, key[1], module):
            if not any(lock.startswith(key[1] + ".") for lock in ids):
                continue
            for _line, port in _port_calls(graph, key, node, ports):
                found.add((module, key[1], name, port))
    return found


def _ordered_ports(graph: _LockGraph) -> set[tuple[str, str, str]]:
    """持 PlanCoordinator._emit_lock 期间调到的注入端口：(模块, 方法, 端口)。

    发布锁（等级 3）持锁调 emit 是本仓库唯一「持锁调端口、端口会再取更高等级锁」
    的有意设计（P2-1 的锁外发布 + 串行化）；这些位置必须与 ORDERED_PORTS 恰好
    相等——多一条是新的未核对端口，少一条说明存量已消失，要删表。
    """
    found: set[tuple[str, str, str]] = set()
    key = ("signup_plan.py", "PlanCoordinator")
    ports = graph.ports(key)
    for name, fn in graph.methods(key).items():
        for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
            if "PlanCoordinator._emit_lock" not in ids:
                continue
            for _line, port in _port_calls(graph, key, node, ports):
                found.add((key[0], name, port))
    return found


def _publish_inside_coord_lock(graph: _LockGraph) -> list[tuple[str, int]]:
    """持 PlanCoordinator._lock 期间（直接或经同类方法链 ≤6 层）调到 _publish 的位置。

    P2-1：状态写入在 _lock 内、事件发布一律在锁外（今天调用处是 start:368、
    cancel_task:383、stop:402、_run:484、_set_state:532，全在锁外）。谁把发布
    挪进锁内，这里就红；那时 _lock(5)→_emit_lock(3) 同时也是规则一的降级，
    两道都抓。
    """
    key = ("signup_plan.py", "PlanCoordinator")
    hits: list[tuple[str, int]] = []

    def reach(node: ast.AST, depth: int, seen: frozenset[str]) -> None:
        for call in _calls_in(node):
            parts = _dotted(call.func).split(".")
            if len(parts) != 2 or parts[0] != "self":
                continue
            if parts[1] == "_publish":
                hits.append((key[1], call.lineno))
            elif depth < 6 and parts[1] in graph.methods(key) and parts[1] not in seen:
                reach(graph.methods(key)[parts[1]], depth + 1, seen | {parts[1]})

    for name, fn in graph.methods(key).items():
        for node, _outer, ids in _iter_withs(fn, key[1], key[0]):
            if "PlanCoordinator._lock" in ids:
                reach(node, 0, frozenset({name}))
    return sorted(set(hits))


def _unknown_locks(graph: _LockGraph) -> list[tuple[str, str, int, str]]:
    """名字里带 lock 却不在等级表里的 `with` 目标：新锁必须先上等级表。"""
    found: list[tuple[str, str, int, str]] = []
    for module, method, node, _outer, _ids in graph.blocks():
        for item in node.items:
            shown = _dotted(item.context_expr)
            if not shown:
                continue
            tail = shown.rsplit(".", 1)[-1]
            if "lock" not in tail.lower():
                continue
            owner = _owner_class(graph, module, method)
            if _lock_id(item.context_expr, owner, module) is None:
                found.append((module, method, node.lineno, shown))
    return found


def _owner_class(graph: _LockGraph, module: str, method: str) -> str | None:
    for key in graph.classes:
        if key[0] == module and method in graph.methods(key):
            return key[1]
    return None


def _load_graph() -> _LockGraph:
    trees = {"app.py": _parse(APP_FILE)}
    for rel in SERVICE_FILES:
        trees[rel] = _parse(LOCAL_DIR / rel)
    return _LockGraph(trees)


def scan_all() -> dict[str, object]:
    """一次扫描的全部结论（测试与排障共用；排障时直接打印这个字典）。"""
    graph = _load_graph()
    rule_one = _rule_one(graph)
    rule_one_services = _rule_one_services(graph)
    return {
        "counts": graph.acquisitions(),
        "down": rule_one["down"],
        "equal": rule_one["equal"],
        "service_down": rule_one_services["down"],
        "service_equal": rule_one_services["equal"],
        "coord_calls": _rule_two(graph),
        "ports": _rule_three(graph),
        "ordered_ports": _ordered_ports(graph),
        "publish_in_lock": _publish_inside_coord_lock(graph),
        "unknown": _unknown_locks(graph),
        "service_attrs": {attr: key[1] for attr, key in graph.service_attrs().items()},
    }


class LockOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = scan_all()

    def test_scanner_recognizes_the_inventoried_acquisitions(self):
        """扫描器必须看得见证据里数过的锁：认少了说明守卫是空的。"""
        counts = self.report["counts"]
        self.assertGreaterEqual(counts.get("Api._lock", 0), 90,
                                "Api._lock 获取处：%s" % (counts.get("Api._lock"),))
        # 四个下载替换入口合并为两条实现，物理获取点随之减少两处。
        self.assertGreaterEqual(counts.get("Api._credential_lock", 0), 10,
                                "凭据锁获取处：%s" % (counts.get("Api._credential_lock"),))
        self.assertGreaterEqual(counts.get("Api._phone_access_lock", 0), 8,
                                "手机访问锁获取处：%s" % (counts.get("Api._phone_access_lock"),))
        self.assertEqual(sorted(set(self.report["service_attrs"].values())),
                         sorted(SERVICE_CLASSES), "Api 里认不全服务属性")
        graph = _load_graph()
        key = ("application/component_actions.py", "ComponentActions")
        for name in ("replace_downloaded", "replace_downloaded_ocr"):
            locks = {lock for _, _, ids in _iter_withs(graph.methods(key)[name], key[1], key[0]) for lock in ids}
            self.assertIn("Api._credential_lock", locks)
            self.assertIn("Api._lock", locks)
        self.assertIn("Api._phone_access_lock", {
            lock for _, _, ids in _iter_withs(graph.methods(key)["replace_downloaded"], key[1], key[0]) for lock in ids})

    def test_new_locks_must_be_leveled(self):
        """新出现的 *_lock 必须先写进等级表，不能就这么用了。"""
        self.assertEqual(self.report["unknown"], [],
                         "这些锁不在等级表里：%s" % (self.report["unknown"],))

    def test_lock_level_only_rises(self):
        """持一把锁时只许拿更高等级的锁：Api 内降级一律不许。"""
        self.assertEqual(self.report["down"], [],
                         "Api 锁序降级的获取处：%s" % (self.report["down"],))

    def test_reentry_equals_the_frozen_legacy_list(self):
        """同号重入必须恰好等于冻结表，当前不允许重入。"""
        actual = sorted({(method, outer, inner)
                         for method, _line, outer, inner in self.report["equal"]})
        self.assertEqual(actual, sorted(set(FROZEN_REENTRY)))

    def test_service_lock_level_only_rises(self):
        """服务类内部同样只许升序：降级一条都不许有（开工清点时无存量）。"""
        self.assertEqual(self.report["service_down"], [],
                         "服务类锁序降级的获取处：%s" % (self.report["service_down"],))

    def test_service_reentry_equals_the_frozen_legacy_list(self):
        """服务类内部的同号重入必须恰好是冻结的两条（RLock 既有重入）。"""
        actual = sorted({(method, outer, inner)
                         for method, _line, outer, inner in self.report["service_equal"]})
        self.assertEqual(actual, sorted(set(FROZEN_SERVICE_REENTRY)))

    def test_coordination_lock_calls_only_published_status(self):
        """持协调锁时只许读锁外发布的计划状态。"""
        self.assertEqual(sorted(set(self.report["coord_calls"])),
                         sorted(set(FROZEN_COORD_CALLS)))
        self.assertEqual(_published_status_body(),
                         "return str(self._status_cache)",
                         "published_status 变复杂了，规则二的放行理由要重核")

    def test_service_locks_avoid_injected_ports(self):
        """服务持锁时不碰注入端口；白名单/有序端口/冻结表必须恰好覆盖全部实际情况。"""
        frozen = set(FROZEN_PORTS)
        allowed = set(LEAF_PORTS)
        ordered = set(ORDERED_PORTS)
        actual = self.report["ports"]
        extra = sorted(item for item in actual
                       if (item[0], item[2], item[3]) not in frozen
                       and (item[0], item[2], item[3]) not in ordered
                       and (item[1], item[3]) not in allowed)
        self.assertEqual(extra, [], "服务持锁期间调了新的注入端口：%s" % (extra,))
        seen = {(module, method, port) for module, _cls, method, port in actual}
        self.assertEqual(sorted(frozen - seen), [],
                         "冻结表里这些已经不再违规，请删掉（清单只许变短）")
        used = {(cls, port) for _module, cls, _method, port in actual}
        self.assertEqual(sorted(allowed - used), [],
                         "白名单里这些端口当前没被持锁调用，核对记录已过期")

    def test_ordered_ports_match_the_scanner(self):
        """持发布锁调端口的位置必须恰好等于 ORDERED_PORTS（只许因存量消失变短）。"""
        self.assertEqual(sorted(self.report["ordered_ports"]),
                         sorted(set(ORDERED_PORTS)),
                         "持 _emit_lock 调端口的位置与 ORDERED_PORTS 不符：%s"
                         % (sorted(self.report["ordered_ports"]),))

    def test_publish_stays_outside_the_coordinator_lock(self):
        """P2-1：协调器的事件发布一律在状态锁外（锁内只写状态，不碰回调）。"""
        self.assertEqual(self.report["publish_in_lock"], [],
                         "持 PlanCoordinator._lock 期间调到了 _publish：%s"
                         % (self.report["publish_in_lock"],))


def _published_status_body() -> str:
    """PlanCoordinator.published_status 的函数体源码（锁外可读的最后一环）。

    规则二完全依赖「它不取协调器锁、也不调任何端口」：signup_plan.py:347-349
    的实现只有一行 `return str(self._status_cache)`，缓存写在 _lock 内、读在锁外。
    """
    tree = _parse(LOCAL_DIR / "signup_plan.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "PlanCoordinator":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "published_status":
                    return ast.unparse(item).split("\n")[-1].strip()
    return ""


class ScannerSelfTests(unittest.TestCase):
    """守卫自己也要被守住：合成一段写得出的违规，每类都必须被抓到。"""

    @classmethod
    def setUpClass(cls):
        cls.graph = _LockGraph({
            "app.py": _parse_text("""
class Api:
    def __init__(self):
        self._lock = object()
        self._credential_lock = object()
        self._phone = PhoneAccessService()
        self._relay = LoginRelayService()

    def down(self):
        with self._lock:
            with self._credential_lock:
                pass

    def new_lock(self):
        with self._x_lock:
            pass

    def service_call(self):
        with self._lock:
            self._relay.cancel()

    def api_chain(self):
        with self._lock:
            self._helper()

    def _helper(self):
        self._phone.pair()
"""),
            "application/login_relay_service.py": _parse_text("""
class LoginRelayService:
    def __init__(self, *, now):
        self._now = now
        self._lock = object()

    def cancel(self):
        with self._lock:
            self._now()
"""),
            "application/phone_service.py": _parse_text("""
class PhoneAccessService:
    def __init__(self, *, api):
        self._api = api
        self._lock = object()
        self._event_lock = object()

    def pair(self):
        with self._lock:
            self._api.start_plan()

    def service_down(self):
        with self._event_lock:
            with self._lock:
                pass
"""),
        })

    def test_flags_a_level_down_acquisition(self):
        self.assertEqual(_rule_one(self.graph)["down"],
                         [("down", 10, "Api._lock", "Api._credential_lock")])

    def test_coordinator_reentry_is_seen_from_caller(self):
        graph = _load_graph()
        fn = graph.methods(("application/coordination.py", "Coordinator"))["is_busy_locked"]
        fn.body = [ast.With(items=[ast.withitem(context_expr=ast.parse("self._lock", mode="eval").body)],
                            body=[ast.Pass(lineno=fn.lineno)], lineno=fn.lineno)]
        self.assertTrue(any(inner == "Coordinator._lock" for _, _, _, inner in _rule_one(graph)["equal"]))

    def test_plan_state_port_rejects_locked_snapshot(self):
        graph = _load_graph()
        fn = graph.methods(graph.api_key)["_published_plan_state"]
        for call in _calls_in(fn):
            if _dotted(call.func) == "self._plan.published_status":
                call.func.attr = "snapshot"
        self.assertIn(("_published_plan_state", "self._plan.snapshot"), _rule_two(graph))

    def test_component_stop_callback_detects_phone_lock_reentry(self):
        graph = _load_graph()
        fn = graph.methods(graph.api_key)["_stop_phone_for_component_locked"]
        fn.body = [ast.With(items=[ast.withitem(context_expr=ast.parse("self._phone_access_lock", mode="eval").body)],
                            body=[ast.Pass(lineno=fn.lineno)], lineno=fn.lineno)]
        self.assertTrue(any(outer == inner == "Api._phone_access_lock"
                            for _, _, outer, inner in _rule_one_services(graph)["equal"]))

    def test_flags_an_unleveled_new_lock(self):
        self.assertEqual(_unknown_locks(self.graph),
                         [("app.py", "new_lock", 14, "self._x_lock")])

    def test_flags_a_service_port_under_a_service_lock(self):
        self.assertEqual(_rule_three(self.graph),
                         {("application/login_relay_service.py", "LoginRelayService",
                           "cancel", "_now"),
                          ("application/phone_service.py", "PhoneAccessService",
                           "pair", "_api")})

    def test_flags_a_service_call_under_the_coordination_lock(self):
        self.assertEqual(_rule_two(self.graph),
                         [("_helper", "self._phone.pair"),
                          ("service_call", "self._relay.cancel")])

    def test_flags_a_service_level_down_acquisition(self):
        """服务类内部的降级嵌套也必须被抓到：持事件锁（6）再拿服务锁（5）不行。"""
        self.assertEqual(_rule_one_services(self.graph)["down"],
                         [("PhoneAccessService.service_down", 13,
                           "PhoneAccessService._event_lock",
                           "PhoneAccessService._lock")])
        self.assertEqual(_rule_one_services(self.graph)["equal"], [])

    def test_flags_publish_inside_the_coordinator_lock(self):
        """把 _publish 挪进协调器锁内：锁外发布断言与规则一降级两道都抓。"""
        graph = _LockGraph({"signup_plan.py": _parse_text("""
class PlanCoordinator:
    def __init__(self, *, runner, emit):
        self.runner = runner
        self.emit = emit
        self._lock = object()
        self._emit_lock = object()

    def evil(self):
        with self._lock:
            self._publish("task", {})

    def _publish(self, kind, payload):
        with self._emit_lock:
            self.emit(kind, payload)
""")})
        self.assertEqual(_publish_inside_coord_lock(graph),
                         [("PlanCoordinator", 10)])
        self.assertEqual(_rule_one_services(graph)["down"],
                         [("PlanCoordinator.evil", 10, "PlanCoordinator._lock",
                           "PlanCoordinator._emit_lock")])
        self.assertEqual(_ordered_ports(graph),
                         {("signup_plan.py", "_publish", "emit")})

    def test_does_not_descend_into_nested_definitions(self):
        """`with` 里的闭包是定义不是调用：闭包体内取锁不算在外层块里。"""
        graph = _LockGraph({"app.py": _parse_text("""
class Api:
    def build(self):
        with self._lock:
            def later():
                with self._credential_lock:
                    pass
            return later
""")})
        self.assertEqual(_rule_one(graph)["down"], [])
        self.assertEqual(_rule_one(graph)["equal"], [])


def _parse_text(source: str) -> ast.Module:
    return ast.parse(source.lstrip("\n"))

if __name__ == "__main__":
    unittest.main()
