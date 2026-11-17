#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from __future__ import annotations

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
    api.stop_phone_access = rec
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


def _drive(testcase, row):
    """逐列跑一行：新 Api → 非列前置 → 装哨兵 → 摆列 → 调动作 → 断言。"""
    for column in _COLUMNS:
        with testcase.subTest(row=row, column=column):
            api = busy_states.build(testcase)
            prep = PREP.get(row)
            if prep is not None:
                prep(testcase, api)
            rec = SENTINELS[row](testcase, api)
            busy_states.put(api, column)
            result = ENTRIES[row](api)
            expect = GRID[row][column]
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


if __name__ == "__main__":
    unittest.main()
