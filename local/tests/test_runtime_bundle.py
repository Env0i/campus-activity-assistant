#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行时组件与资源解析的契约测试（临时目录 + mock 进程，零学校调用、零真实登录态）。

覆盖：worker 路径解析（源码 grab.py / 冻结资源根，绝不借 EXE 旁旧文件）、
组件失败（缺失/权限/启动异常）时 check/list/login 的恰一次终态收尾、
正常关闭只终止本 Api 登记的进程、--runtime-check 离线探针的 JSON/退出码契约、
构建脚本把 worker 作为内置资源打进主程序（mock 定义）。

边界：这里的 mock 用例**不能**替代真实冻结验收——「仅含单 EXE 的空目录实际由
主程序启动内置 worker --help 且退出 0」必须在授权后用真实冻结包执行（见决策 010）。

运行方式（需用户授权后）：PYTHONPATH=. python -m unittest local.tests.test_runtime_bundle

@author Author
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
ROOT = LOCAL.parent
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
from fixtures.business_clock import TestWallClock  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402
from time_contract import configure_time_source  # noqa: E402
configure_time_source(time.time)   # 旧用例显式注入本机时钟；新用例改注 FakeBusinessClock


def _app():
    """导入 local/app.py（webview/pyinstaller 缺失时跳过，不装依赖）。"""
    sys.path.insert(0, str(LOCAL))
    try:
        import app as local_app
    except Exception as exc:
        raise unittest.SkipTest("无法导入 local/app.py：%s" % exc)
    finally:
        sys.path.pop(0)
    return local_app


def read(rel: str) -> str:
    path = ROOT / rel
    assert path.exists(), "契约文件缺失：%s" % path
    return path.read_text(encoding="utf-8")


def _owned_tree(proc):
    """把既有假进程包成 _run 使用的受管树替身。"""
    tree = mock.Mock()
    tree.proc = proc
    return tree


# ---- 条款同意夹具（计划 repair-terms-test-fixtures）----
# check、list、login、start_plan 与协调器生命周期都先过 app._terms_gate，而门禁
# 只读 app.PREFS：不把偏好钉到临时文件，这些用例就会去读开发者真实的 ui.json，
# 门禁结论随机器上是否点过同意而漂移。同意状态只写在本轮临时 ui.json 的
# terms_version / terms_accepted_at 两个键上，模块跑完即删；专门验证 terms_required
# 未同意状态的用例在 test_terms_consent.py 里照旧构造，不受这里影响。
_PREFS_PATCHER = None
_PREFS_TMP = None


def setUpModule():
    """把本模块的偏好文件钉到临时 ui.json，并写入当前版本的条款同意。"""
    global _PREFS_PATCHER, _PREFS_TMP
    try:
        local_app = _app()
    except unittest.SkipTest:
        # 导入失败时由各用例自己 skipTest，保持原有跳过行为，不替它们下结论
        return
    _PREFS_TMP = tempfile.TemporaryDirectory(prefix="campus-terms-prefs-")
    _PREFS_PATCHER = mock.patch.object(local_app, "PREFS",
                                       Path(_PREFS_TMP.name) / "ui.json")
    _PREFS_PATCHER.start()
    if not local_app.update_prefs({"terms_version": local_app.TERMS_VERSION,
                                   "terms_accepted_at": "2026-10-27 12:00:00"}):
        tearDownModule()
        raise RuntimeError("条款同意偏好夹具写入失败")


def tearDownModule():
    """还原真实的 app.PREFS，并删除本轮临时偏好目录。"""
    global _PREFS_PATCHER, _PREFS_TMP
    if _PREFS_PATCHER is not None:
        _PREFS_PATCHER.stop()
        _PREFS_PATCHER = None
    if _PREFS_TMP is not None:
        _PREFS_TMP.cleanup()
        _PREFS_TMP = None


class WorkerResolutionTests(unittest.TestCase):
    """worker 唯一来源：源码态 grab.py，冻结态资源根 grab-worker.exe。"""

    def setUp(self):
        self.app = _app()

    def test_source_mode_resolves_grab_py(self):
        """开发/源码形态：worker 就是 local/grab.py，随仓库存在。"""
        self.assertEqual(self.app.GRAB, LOCAL / "grab.py")
        self.assertTrue(self.app.GRAB.is_file(), "源码形态必须能找到 grab.py")

    def test_frozen_mode_uses_resource_root_never_exe_sidecar(self):
        """冻结解析只看资源根：EXE 旁即使躺着一个旧 worker 也不借，也不看 cwd。"""
        here = Path("D:/only-exe-dir")
        resource_root = Path("D:/res-root")
        frozen = self.app.resolve_worker_path(True, here, resource_root)
        self.assertEqual(frozen, resource_root / "grab-worker.exe",
                         "冻结态 worker 必须来自打包资源根")
        self.assertNotEqual(frozen, here / "grab-worker.exe",
                            "不得静默借用 EXE 旁旧 worker（旧包混用会掩盖组件缺失）")
        self.assertEqual(self.app.resolve_worker_path(False, here, resource_root),
                         here / "grab.py", "源码态与资源根无关")

    def test_worker_problem_codes(self):
        """组件自检三码：worker_missing / worker_permission / 空串=齐备。"""
        app = self.app
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            with mock.patch.object(app, "GRAB", tmp / "nope.py"):
                self.assertEqual(app.worker_problem(), "worker_missing")
            readable = tmp / "grab.py"
            readable.write_text("# source", encoding="utf-8")
            with mock.patch.object(app, "GRAB", readable):
                self.assertEqual(app.worker_problem(), "", "可读即齐备（源码态）")
                with mock.patch("os.access", lambda p, m: False):
                    self.assertEqual(app.worker_problem(), "worker_permission")
            exe = tmp / "grab-worker.exe"
            exe.write_bytes(b"MZ")
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(app, "GRAB", exe), \
                    mock.patch("os.access", lambda p, m: True):
                self.assertEqual(app.worker_problem(), "", "冻结态存在且可访问即齐备")
            with mock.patch.object(sys, "frozen", True, create=True), \
                    mock.patch.object(app, "GRAB", tmp / "gone.exe"):
                self.assertEqual(app.worker_problem(), "worker_missing")

    def test_component_error_mapping(self):
        """Popen/run 异常 → 结构化错误码：FileNotFound→missing / Permission→permission / 其余→spawn。"""
        app = self.app
        self.assertEqual(app._component_error(FileNotFoundError()), "worker_missing")
        self.assertEqual(app._component_error(PermissionError()), "worker_permission")
        self.assertEqual(app._component_error(OSError("boom")), "spawn_failed")


class ComponentFailureCloseoutTests(unittest.TestCase):
    """check/list/login 的组件失败收尾：恰一次终态、busy 清位、零学校调用、会话不变。"""

    def setUp(self):
        self.app = _app()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.session = self.tmp / "session.json"
        for patch in (mock.patch.object(self.app, "SESSION_FILE", self.session),
                      mock.patch.object(self.app, "DEMO", False)):
            patch.start()
            self.addCleanup(patch.stop)

    def _api_with_events(self):
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload=None: events.append((kind, payload))
        return api, events

    def _missing_worker(self) -> Path:
        return self.tmp / "no-such-worker.exe"

    def test_check_worker_missing_emits_unknown_once(self):
        """check 遇缺组件：恰一次 check 终态（unknown + runtime_error），检查位清零。"""
        api, events = self._api_with_events()
        cmd = mock.Mock(side_effect=lambda *a: [str(self._missing_worker())])
        with mock.patch.object(self.app, "worker_command", cmd):
            api._do_check()
        checks = [payload for kind, payload in events if kind == "check"]
        self.assertEqual(len(checks), 1, "check 必须恰发一次终态事件")
        payload = checks[0]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["result"], "unknown",
                         "组件失败不得冒充登录四态里的 expired/none")
        self.assertEqual(payload["runtime_error"], "worker_missing")
        self.assertEqual(api._last_check["result"], "unknown")
        self.assertEqual(api._last_check["runtime_error"], "worker_missing")
        self.assertFalse(api._checking, "finally 必须清「检查中」标记")
        self.assertEqual(cmd.call_args_list, [mock.call("check")],
                         "只允许分发 check，不得顺势调 list/login（零学校调用）")
        self.assertFalse(self.session.exists(), "组件失败路径不得创建/改写会话文件")

    def test_check_worker_missing_logs_technical_detail(self):
        """技术细节只进运行记录（log 事件），主文案保持人话。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "worker_command",
                               lambda *a: [str(self._missing_worker())]):
            api._do_check()
        logs = [payload for kind, payload in events if kind == "log"]
        self.assertTrue(logs, "组件诊断的技术细节必须落日志")
        self.assertIn("worker_missing", logs[0])
        check = next(p for kind, p in events if kind == "check")
        self.assertNotIn("FileNotFoundError", check["text"], "主文案不得含技术词")

    def test_list_worker_missing_emits_failure_once(self):
        """list 遇缺组件：恰一次 activities 失败终态——骨架必须能结束（WinError 2 缺口）。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "worker_command",
                               lambda *a: [str(self._missing_worker())]):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1, "list 必须恰发一次终态事件")
        payload = acts[0]
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["runtime_error"], "worker_missing")
        self.assertIn("程序组件缺失", payload["text"])
        self.assertFalse(api._listing, "finally 必须清「拉列表」标记")

    def test_list_spawn_exception_maps_to_spawn_failed(self):
        """非文件缺失类异常（权限/占用）同样给终态并归 spawn_failed。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(side_effect=OSError("boom"))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["runtime_error"], "spawn_failed")

    def test_list_permission_error_maps_to_worker_permission(self):
        """权限类进程创建异常归 worker_permission（组件码只来自进程创建 OSError）。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(side_effect=PermissionError("denied"))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["runtime_error"], "worker_permission")

    def test_list_data_exception_is_plain_failure_not_component(self):
        """数据异常（TypeError 等）：恰一次失败终态、无 runtime_error、
        不冒充组件损坏（不诱导重新下载）；检查位解除、凭证零接触。"""
        api, events = self._api_with_events()
        fake = mock.Mock()
        fake.returncode = 0
        fake.communicate.return_value = ('[{"id": "a1", "name": "活动"}]', "")
        fake.poll.return_value = 0
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(return_value=_owned_tree(fake))), \
                mock.patch.object(self.app, "_seconds_until",
                                  mock.Mock(side_effect=TypeError("bad data shape"))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1, "数据异常也必须恰一次终态")
        payload = acts[0]
        self.assertFalse(payload["ok"])
        self.assertNotIn("runtime_error", payload, "数据异常不得带组件码")
        self.assertNotIn("程序组件", payload["text"], "数据异常不得冒充组件损坏")
        self.assertEqual(payload["text"], "活动列表没能加载")
        self.assertFalse(api._listing, "finally 必须清「拉列表」标记")
        self.assertFalse(self.session.exists(), "数据异常路径不得创建/改写会话文件")

    def test_list_with_sign_start_item_keeps_seconds_to_open(self):
        """回归（M5）：列表里有一场带 sign_start 的活动时，整理函数不抛 TypeError。

        app.py 末尾的兼容别名 `_seconds_until = _time_text.seconds_until` 会覆盖
        575 行的两参数包装，真活动列表一进来就 missing argument；删掉别名后
        1785 行的两参数调用必须仍能算出整数秒。
        """
        api, events = self._api_with_events()
        fake = mock.Mock()
        fake.returncode = 0
        fake.communicate.return_value = (json.dumps(
            [{"id": "a1", "name": "活动", "sign_start": "2099-01-01 00:00:00"}],
            ensure_ascii=False), "")
        fake.poll.return_value = 0
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(return_value=_owned_tree(fake))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1, "成功路径也只发一次列表终态")
        payload = acts[0]
        self.assertTrue(payload["ok"], "有真实活动时列表不得因整理函数崩溃")
        item = payload["items"][0]
        self.assertIsInstance(item["seconds_to_open"], int,
                              "未来 sign_start 必须算出整数秒，而不是崩掉或 None")

    def test_list_parses_stdout_only_and_logs_timing(self):
        """列表 JSON 只来自 stdout：stderr 的辅助日志不再污染解析，
        [timing] 行转成一条「活动列表用时」运行记录（联网段按 total_s）。"""
        api, events = self._api_with_events()
        fake = mock.Mock()
        fake.returncode = 0
        fake.communicate.return_value = (
            '[{"id": "a1", "name": "活动", "sign_start": "", "sign_end": ""}]',
            "[i] 一行辅助日志\n[timing] list token_s=0.40 pages=7 pages_s=2.80 "
            "details=3 details_s=1.20 total_s=4.50\n")
        fake.poll.return_value = 0
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(return_value=_owned_tree(fake))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertTrue(acts[0]["ok"], "stderr 混有辅助日志时列表必须照常可解析")
        self.assertEqual([item["id"] for item in acts[0]["items"]], ["a1"])
        logs = [payload for kind, payload in events if kind == "log"]
        timing_logs = [item for item in logs
                       if str(item).startswith("活动列表用时")]
        self.assertEqual(len(timing_logs), 1, "用时应恰好写一条运行记录")
        self.assertIn("联网约 4.5 秒", str(timing_logs[0]))
        self.assertIn("补详情 3 场", str(timing_logs[0]))

    def test_list_without_timing_line_still_loads(self):
        """旧 worker 没有 [timing] 行：列表照常加载，运行记录用简短用时一句。"""
        api, events = self._api_with_events()
        fake = mock.Mock()
        fake.returncode = 0
        fake.communicate.return_value = (
            '[{"id": "a1", "name": "活动", "sign_start": "", "sign_end": ""}]',
            "[i] 只有一行杂音，没有用时分段\n")
        fake.poll.return_value = 0
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(return_value=_owned_tree(fake))):
            api._do_list()
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertTrue(acts[0]["ok"], "没有 [timing] 行时列表必须照常加载")
        logs = [payload for kind, payload in events if kind == "log"]
        timing_logs = [item for item in logs
                       if str(item).startswith("活动列表用时")]
        self.assertEqual(len(timing_logs), 1)
        self.assertNotIn("联网约", str(timing_logs[0]),
                         "拿不到分段时只写简短用时，不得编造联网耗时")

    def test_check_data_exception_is_plain_failure_not_component(self):
        """check 数据异常：恰一次检查失败终态、无 runtime_error、技术细节只进日志。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app.Api, "_run",
                               mock.Mock(side_effect=AttributeError("bad check data"))):
            api._do_check()
        checks = [payload for kind, payload in events if kind == "check"]
        self.assertEqual(len(checks), 1)
        payload = checks[0]
        self.assertFalse(payload["ok"])
        self.assertNotIn("runtime_error", payload, "数据异常不得带组件码")
        self.assertIn("检查登录态没跑完", payload["text"])
        self.assertEqual(api._last_check["runtime_error"], "")
        self.assertFalse(api._checking, "finally 必须清「检查中」标记")
        logs = [payload for kind, payload in events if kind == "log"]
        self.assertTrue(any("AttributeError" in str(item) for item in logs),
                        "技术细节必须落日志")

    def test_list_unknown_exception_closes_out_once(self):
        """未知类型异常：恰一次终态收尾，不因空错误码取字典二次抛错。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "spawn_owned",
                               mock.Mock(side_effect=RuntimeError("weird"))):
            api._do_list()   # 不向上抛即通过：兜底分支不得让异常冲出收尾
        acts = [payload for kind, payload in events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertNotIn("runtime_error", acts[0])
        self.assertEqual(acts[0]["text"], "活动列表没能加载")

    def test_check_outer_fallback_revokes_stale_valid(self):
        """FB3：结论构造阶段异常命中外层兜底——后端旧 valid 同步撤销为 unknown。"""
        app = self.app
        api, events = self._api_with_events()
        api._last_check = {"result": "valid", "checked_at": 0.0, "runtime_error": ""}
        api._checking = True
        made = []

        def fake_coord(*args, **kwargs):
            made.append(args)
            return mock.Mock()

        ok_run = mock.Mock(return_value={"code": 0, "out": "[OK] 登录态还有 15 小时"})
        item = {"id": "a1", "name": "活动", "sign_start": "2026-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}
        # R05：先登记权威缓存再开始；这里验证的是关闭/校验交错，不是陈旧快照门禁
        api._activities = {item["id"]: dict(item)}
        # 结论构造已下沉 application.login_service：外层兜底的注入缝随实现迁移
        from application import login_service
        with mock.patch.object(app.Api, "_run", ok_run), \
                mock.patch.object(login_service, "check_reason_line",
                                  mock.Mock(side_effect=TypeError("结论构造炸了"))), \
                mock.patch.object(app, "PlanCoordinator", fake_coord):
            api._do_check()
            res = api.start_plan([dict(item)])
        checks = [payload for kind, payload in events if kind == "check"]
        self.assertEqual(len(checks), 1, "外层兜底仍恰一次终态")
        self.assertEqual(checks[0]["result"], "unknown")
        self.assertNotIn("runtime_error", checks[0], "外层兜底不是组件错误")
        self.assertEqual(api._last_check["result"], "unknown", "后端判定必须同步撤销")
        self.assertEqual(api._last_check["runtime_error"], "")
        self.assertFalse(api._checking)
        self.assertFalse(res.get("ok"), "旧 valid 不得继续放行 start_plan")
        self.assertEqual(made, [], "拒绝路径不得构造协调器")
        # 随后正常校验恢复 valid：按既有规则重新接纳
        with mock.patch.object(app.Api, "_run", ok_run), \
                mock.patch.object(app, "PlanCoordinator", fake_coord):
            api._do_check()
            res2 = api.start_plan([dict(item)])
        self.assertEqual(api._last_check["result"], "valid")
        self.assertTrue(res2.get("ok"), "正常校验恢复 valid 后按既有规则接纳")

    def test_login_worker_missing_returns_structured_no_busy(self):
        """login 同步组件失败：ok=false + error 码，不留 busy/子进程占位。"""
        api, events = self._api_with_events()
        with mock.patch.object(self.app, "worker_command",
                               lambda *a: [str(self._missing_worker())]):
            res = api.login()
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "worker_missing")
        self.assertIn("程序组件缺失", res["text"])
        self.assertIn("重新下载完整版本", res["text"])
        self.assertIsNone(api._proc, "失败路径不得留下子进程占位")
        self.assertFalse(api._is_busy_locked())
        self.assertNotIn("done", [kind for kind, _ in events], "没启动就没有 done 事件")

    def test_demo_check_is_fully_offline(self):
        """R20：--demo 的 check/list/login 只用内存样例，零 worker、零学校。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload=None: events.append((kind, payload))
        with mock.patch.object(app, "DEMO", True), \
                mock.patch.object(app.Api, "_run",
                                  side_effect=AssertionError("演示模式不得起 worker")), \
                mock.patch.object(app.Api, "_spawn",
                                  side_effect=AssertionError("演示模式不得起进程")):
            api._do_check()
            api._do_list()
            login = api.login()
        checks = [payload for kind, payload in events if kind == "check"]
        self.assertEqual(len(checks), 1, "check 恰一次终态")
        self.assertEqual(checks[0]["result"], "demo", "必须标明演示模式，不伪装登录有效")
        self.assertTrue(checks[0].get("demo"))
        self.assertFalse(api._checking)
        self.assertFalse(api._is_busy_locked())
        self.assertEqual(api._last_check["result"], "demo")
        self.assertFalse(login["ok"], "演示模式不打开学校登录页")
        self.assertTrue(login.get("demo"))
        lists = [payload for kind, payload in events if kind == "activities"]
        self.assertTrue(lists and lists[0]["ok"] and lists[0]["items"],
                        "演示列表必须来自内存样例")

    def test_demo_bootstrap_reads_no_credentials(self):
        """C07：demo 的 bootstrap 不得读 session/生命周期，也不得迁移真实数据。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        with mock.patch.object(app, "DEMO", True), \
                mock.patch.object(app, "login_state",
                                  side_effect=AssertionError("demo 不得读真实登录态")), \
                mock.patch.object(app, "get_lifecycle",
                                  side_effect=AssertionError("demo 不得读真实生命周期")):
            info = api.bootstrap()
        self.assertTrue(info["demo"])
        self.assertTrue(info["login"]["demo"])
        self.assertIsNone(info["login"]["session_present"], "演示没有真实会话，不能伪造成 false")
        self.assertEqual(info["lifecycle"]["close_quality"], "unknown")

    def test_start_plan_rejects_missing_component_but_demo_skips(self):
        """start_plan 保留组件门禁（真实模式）；demo 不起 worker，跳过组件检查。"""
        item = {"id": "a", "name": "活动", "sign_start": "2099-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        with mock.patch.object(self.app, "worker_problem", lambda: "worker_missing"):
            res = api.start_plan([dict(item)])
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"], "worker_missing")
        self.assertIn("程序组件缺失", res["text"])
        self.assertIsNone(api._plan, "拒绝路径不得创建计划")
        # demo：不起 worker，组件门禁放行（落到计划校验层；缺举办时间的样本直接被拒）
        with mock.patch.object(self.app, "DEMO", True):
            api2 = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
            res2 = api2.start_plan([{"id": "b", "name": "缺时间",
                                     "sign_start": "2099-01-01 09:00:00",
                                     "signed": False}])
            self.assertFalse(res2["ok"])
            self.assertNotEqual(res2.get("error"), "worker_missing",
                                "demo 模式不得被组件门禁拦截")


class ListClockWaitTests(unittest.TestCase):
    """L1：拉列表前最多等约 8 秒北京时间；等不到也照常拉，用时行写明等待与来源。"""

    def setUp(self):
        self.app = _app()
        for patch in (mock.patch.object(self.app, "DEMO", False),):
            patch.start()
            self.addCleanup(patch.stop)

    def _api(self):
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload=None: events.append((kind, payload))
        return api, events

    def _run_reply(self, stderr=""):
        return {"code": 0, "out": "[]", "stdout": "[]", "stderr": stderr}

    def test_waits_until_clock_ready_then_starts_worker(self):
        api, events = self._api()
        checks = []

        def ready():
            checks.append(time.monotonic())
            return len(checks) > 2          # 第三次轮询时校时已好

        with mock.patch.object(self.app, "LIST_CLOCK_WAIT_S", 1.0), \
                mock.patch.object(self.app, "LIST_CLOCK_POLL_S", 0.05), \
                mock.patch.object(api, "_clock_ready", ready), \
                mock.patch.object(api, "_run", lambda *a, **k: self._run_reply()):
            elapsed = self._timed(api._do_list)
        self.assertGreaterEqual(elapsed, 0.09, "校时没好时要先等，不立刻拉列表")
        logs = [p for k, p in events if k == "log"]
        self.assertIn("北京时间校准中，稍后加载活动", logs)
        acts = [p for k, p in events if k == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertTrue(acts[0]["ok"], "等到了就照常加载")

    def test_timeout_still_loads_the_list(self):
        api, events = self._api()
        with mock.patch.object(self.app, "LIST_CLOCK_WAIT_S", 0.2), \
                mock.patch.object(self.app, "LIST_CLOCK_POLL_S", 0.05), \
                mock.patch.object(api, "_clock_ready", lambda: False), \
                mock.patch.object(api, "_run", lambda *a, **k: self._run_reply()):
            elapsed = self._timed(api._do_list)
        self.assertGreaterEqual(elapsed, 0.15, "等不到也要等满上限")
        acts = [p for k, p in events if k == "activities"]
        self.assertEqual(len(acts), 1, "超时不得跳过列表")
        self.assertTrue(acts[0]["ok"])

    def test_ready_clock_does_not_wait_or_warn(self):
        api, events = self._api()
        with mock.patch.object(self.app, "LIST_CLOCK_WAIT_S", 5.0), \
                mock.patch.object(api, "_clock_ready", lambda: True), \
                mock.patch.object(api, "_run", lambda *a, **k: self._run_reply()):
            elapsed = self._timed(api._do_list)
        self.assertLess(elapsed, 0.5, "时钟已就绪：立即拉列表")
        logs = [p for k, p in events if k == "log"]
        self.assertNotIn("北京时间校准中，稍后加载活动", logs)

    def test_close_interrupts_the_wait(self):
        api, _events = self._api()
        api._closing = True
        with mock.patch.object(self.app, "LIST_CLOCK_WAIT_S", 5.0), \
                mock.patch.object(api, "_clock_ready", lambda: False), \
                mock.patch.object(api, "_run", lambda *a, **k: self._run_reply()):
            elapsed = self._timed(api._do_list)
        self.assertLess(elapsed, 0.5, "关闭中不得把退出拖到 8 秒")

    def test_timing_line_reports_wait_and_filter_source(self):
        api, events = self._api()
        checks = []

        def ready():
            checks.append(1)
            return len(checks) > 1
        stderr = ("[timing] list token_s=0.10 pages=1 pages_s=0.10 details=1 "
                  "details_s=0.10 total_s=0.20 filter_time_source=school_date\n")
        with mock.patch.object(self.app, "LIST_CLOCK_WAIT_S", 1.0), \
                mock.patch.object(self.app, "LIST_CLOCK_POLL_S", 0.2), \
                mock.patch.object(api, "_clock_ready", ready), \
                mock.patch.object(api, "_run",
                                  lambda *a, **k: self._run_reply(stderr)):
            api._do_list()
        timing = [str(p) for k, p in events
                  if k == "log" and str(p).startswith("活动列表用时")]
        self.assertEqual(len(timing), 1)
        self.assertIn("等北京时间约 0.2 秒", timing[0])
        self.assertIn("按学校服务器时间筛选", timing[0])

    @staticmethod
    def _timed(fn):
        started = time.monotonic()
        fn()
        return time.monotonic() - started


class ShutdownLifecycleTests(unittest.TestCase):
    """正常关闭收尾：先停协调器，再按树终止**仅本 Api 登记**的进程。"""

    def setUp(self):
        self.app = _app()

    def _sleeper(self, seconds: int = 30) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(%d)" % seconds],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def _force_kill(proc: subprocess.Popen) -> None:
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait(5)
        except Exception:
            pass

    def test_shutdown_kills_only_registered_procs(self):
        """登记过的登录/计划/辅助进程全部终止；未登记的外部进程原样存活。"""
        p_login = self._sleeper()
        p_plan = self._sleeper()
        p_aux = self._sleeper()
        p_foreign = self._sleeper()
        self.addCleanup(self._force_kill, p_foreign)
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._proc = p_login
        api._plan_procs["task-01"] = p_plan
        api._aux_procs.add(p_aux)
        api.shutdown()
        deadline = time.time() + 5
        for proc in (p_login, p_plan, p_aux):
            while proc.poll() is None and time.time() < deadline:
                time.sleep(0.05)
            self.assertIsNotNone(proc.poll(), "登记过的进程必须在关闭收尾中被终止")
        self.assertIsNone(p_foreign.poll(), "未登记的外部进程不得被扫杀")
        self._force_kill(p_foreign)

    def test_shutdown_stops_coordinator_once(self):
        """有计划时先置停协调器（等待/排队任务标 canceled），再走进程收尾。"""
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        plan = mock.Mock()
        plan.plan_id = "p1"
        api._plan = plan
        api.shutdown()
        plan.stop.assert_called_once_with()

    def test_spawn_registers_proc_inside_lock(self):
        """受管创建与 _proc 登记在同一把锁内：关闭与异步启动竞态不留孤儿（结构锁死）。"""
        src = read("local/app.py")
        spawn = src[src.index("\n    def _spawn(self"):
                    src.index("\n    def _anchor_login_success")]
        self.assertIn("with self._lock:", spawn)
        self.assertLess(spawn.index("with self._lock:"),
                        spawn.index("spawn_owned("),
                        "受管创建必须在锁内（所有权与登记原子，关闭快照才能看到它）")
        self.assertIn("self._proc = tree.proc", spawn)
        self.assertIn("self._proc_tree = tree", spawn)
        self.assertNotIn("subprocess.Popen", spawn, "_spawn 不得绕开受管进程树")

    def test_relay_worker_uses_managed_spawn_with_stdin(self):
        """relay 的 stdin/stdout 也要走受管入口，不能再用裸 Popen。"""
        src = read("local/app.py")
        relay = src[src.index("\n    def _spawn_relay_worker"):
                    src.index("\n    def _relay_finished")]
        self.assertIn("spawn_owned(", relay)
        self.assertIn("stdin=subprocess.PIPE", relay)
        self.assertIn("self._proc_tree = tree", relay)
        self.assertNotIn("subprocess.Popen", relay)

    def test_plan_stop_prefers_managed_tree(self):
        """停计划先走 Job 端口；对已退出的 Popen 调 kill_tree 只能当兜底。"""
        src = read("local/app.py")
        term = src[src.index("def _terminate_plan_procs"):
                   src.index("def plan_active_for_close")]
        self.assertIn("self._plan_trees", term)
        self.assertIn("tree.terminate()", term)
        self.assertIn("_kill_tree(proc)", term, "旧 Popen 只作兼容回退")
        self.assertIn("plan_trees=self._plan_trees", src)

    def test_aux_run_uses_owned_tree_and_closes_it_after_success(self):
        """check/list worker 成功收尾：受管树登记、stdio 分离、句柄关闭。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        proc = mock.Mock()
        proc.returncode = 0
        proc.communicate.return_value = ("[]", "[i] aux\n")
        tree = mock.Mock()
        tree.proc = proc
        with mock.patch.object(app, "spawn_owned", return_value=tree) as spawn:
            result = api._run(["worker", "list", "--json"], timeout=3)
        self.assertEqual(result["stdout"], "[]")
        self.assertEqual(result["stderr"], "[i] aux\n")
        self.assertEqual(api._aux_trees, {}, "正常收尾后不得残留 aux tree 登记")
        self.assertEqual(api._aux_procs, set(), "兼容进程表也必须清理")
        tree.close.assert_called_once_with()
        spawn.assert_called_once()
        self.assertIs(spawn.call_args.kwargs["stdout"], app.subprocess.PIPE)
        self.assertIs(spawn.call_args.kwargs["stderr"], app.subprocess.PIPE)

    def test_aux_run_timeout_terminates_tree_before_legacy_fallback(self):
        """check/list 超时优先终止受管树，旧 kill_tree 不再成为主路径。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        proc = mock.Mock()
        proc.communicate.side_effect = [subprocess.TimeoutExpired("worker", 1), ("", "")]
        proc.returncode = -9
        tree = mock.Mock()
        tree.proc = proc
        with mock.patch.object(app, "spawn_owned", return_value=tree), \
                mock.patch.object(app, "_kill_tree") as legacy_kill:
            result = api._run(["worker", "check"], timeout=1)
        self.assertEqual(result["code"], -1)
        tree.terminate.assert_called_once_with()
        tree.close.assert_called_once_with()
        legacy_kill.assert_not_called()
        self.assertEqual(api._aux_trees, {})

    def test_aux_run_contract_keeps_tree_registration_and_stdio_split(self):
        """_run 的关键收口顺序固定在组合根，避免回到裸 Popen。"""
        src = read("local/app.py")
        run = src[src.index("    def _run("):src.index("    def _spawn(")]
        self.assertIn("spawn_owned(", run)
        self.assertIn("self._aux_trees[proc] = tree", run)
        self.assertIn("tree.terminate()", run)
        self.assertIn("tree.close()", run)
        self.assertIn("stdout=subprocess.PIPE", run)
        self.assertIn("stderr=subprocess.PIPE", run)

    def test_shutdown_terminates_aux_trees_before_legacy_processes(self):
        """关闭收尾先用 aux tree，只有无树或树失败的旧登记才走 kill_tree。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        p_owned, p_failed, p_legacy = (_FakeProc(31), _FakeProc(32), _FakeProc(33))
        owned = mock.Mock()
        owned.proc = p_owned
        owned.terminate.return_value = True
        failed = mock.Mock()
        failed.proc = p_failed
        failed.terminate.return_value = False
        api._aux_trees = {p_owned: owned, p_failed: failed}
        api._aux_procs = {p_owned, p_failed, p_legacy}
        with mock.patch.object(app, "_kill_tree") as kill:
            api.shutdown()
        self.assertEqual({id(call.args[0]) for call in kill.call_args_list},
                         {id(p_failed), id(p_legacy)})
        self.assertEqual(kill.call_count, 2)
        owned.terminate.assert_called_once_with()
        failed.terminate.assert_called_once_with()
        owned.close.assert_called_once_with()
        failed.close.assert_called_once_with()

    def test_kill_tree_is_pid_only(self):
        """树终止只按 PID：不得出现按映像名扫杀（用户可能开着别的实例）。

        树终止实现已下沉 infrastructure.process_tree，契约随实现迁移。
        """
        src = read("local/infrastructure/process_tree.py")
        self.assertIn('["taskkill", "/F", "/T", "/PID", str(proc.pid)]', src,
                      "树终止命令必须按 PID")
        self.assertNotIn('"/IM"', src, "不得按映像名扫杀")
        self.assertNotIn('"/IM"', read("local/app.py"), "不得按映像名扫杀")


class _FakeProc:
    """内存假进程：poll 恒为 None（活得好好的一段内存），kill 只翻标记。"""

    def __init__(self, pid: int = 1000):
        self.pid = pid
        self.killed = False

    def poll(self):
        return None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


class _GatePopen:
    """可控 Popen 替身：构造（=Popen 调用）内等 release 才返回，communicate 内等 finish 才返回。

    创建与登记在同一临界区里：构造内阻塞让创建线程停在「已进锁、尚未登记」
    的中段（shutdown 必须等在锁外）；communicate 内阻塞让进程停在
    「已登记、还活着」——此时 shutdown 取快照必须收走它。行为全部内存化
    （零真实子进程）。
    """

    def __init__(self, entered: threading.Event, release: threading.Event,
                 finish: threading.Event, args, **kwargs):
        self.args = args
        self.pid = 4711
        self.returncode = 0
        self.killed = False
        self._finish = finish
        entered.set()
        release.wait(5)

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode

    def communicate(self, timeout=None):
        self._finish.wait(5)
        return ("[]", "")


class _AuxTreeGate:
    def __init__(self, proc, terminated):
        self.proc = proc
        self.terminated = terminated
        self.closed = False

    def terminate(self):
        self.proc.killed = True
        self.terminated.append(self.proc)
        return True

    def close(self):
        self.closed = True


class ShutdownBarrierTests(unittest.TestCase):
    """关闭屏障的行为回归（事件/屏障驱动，不靠 sleep 碰竞态、不只断言源码含锁）。

    覆盖四类交错：关闭先置位时四类公开入口均不 Popen；创建已开始时 shutdown
    等待登记完成且收走不漏；排队 check/list 与计划任务在关闭后到达创建点被拒；
    并发两次 shutdown 只收尾一次且无死锁。除既有真实进程用例外，这里全部用
    内存假进程 + 打点替身（零真实子进程、零学校调用），外部未登记 fixture
    必须存活仍由 ShutdownLifecycleTests.test_shutdown_kills_only_registered_procs
    以真实无害进程守护。本轮只定义，不运行（待授权轮统一执行）。
    """

    def setUp(self):
        self.app = _app()

    def _plan_item(self) -> dict:
        return {"id": "a1", "name": "活动", "sign_start": "2099-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}

    def test_closing_refuses_all_public_starters_without_popen(self):
        """关闭先置位：check/list/login/start_plan 四类入口都拒绝且零 Popen。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        popen_calls = []

        def counting_popen(args, **kwargs):
            popen_calls.append(args)
            raise AssertionError("关闭后不得创建任何进程")

        with mock.patch.object(app, "worker_command", lambda *a: ["fake-worker"]), \
                mock.patch.object(app, "worker_problem", lambda: ""), \
                mock.patch.object(app, "spawn_owned", counting_popen):
            api.shutdown()
            r_check = api.check()
            r_list = api.list_activities()
            r_login = api.login()
            r_plan = api.start_plan([self._plan_item()])
        for name, res in (("check", r_check), ("list", r_list),
                          ("login", r_login), ("start_plan", r_plan)):
            self.assertFalse(res.get("ok"), "%s 关闭后必须拒绝" % name)
            self.assertIn("关闭", res.get("text", ""), "%s 拒绝话术要说明正在关闭" % name)
            self.assertNotIn("error", res, "%s 拒绝不是组件码，不得带 error 字段" % name)
        self.assertEqual(popen_calls, [], "四类入口都不得走到 Popen")
        self.assertFalse(api._checking)
        self.assertFalse(api._listing)
        self.assertIsNone(api._plan, "关闭后不得创建计划")

    def test_shutdown_waits_for_inflight_creation_and_reaps_it(self):
        """创建先开始：shutdown 等在锁外；登记完成、进程仍活着时必被收走（不漏登记）。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        entered, release, finish = (threading.Event(), threading.Event(),
                                    threading.Event())
        made = []

        def gate_spawn(args, **kwargs):
            proc = _GatePopen(entered, release, finish, args, **kwargs)
            made.append(proc)
            return _AuxTreeGate(proc, kills)

        kills = []

        done = threading.Event()

        def closer():
            api.shutdown()
            done.set()

        with mock.patch.object(app, "spawn_owned", gate_spawn), \
                mock.patch.object(app, "worker_command", lambda *a: ["fake-worker"]):
            worker = threading.Thread(target=api._do_list, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), "创建线程必须到达 Popen 边界（锁内）")
            closer_t = threading.Thread(target=closer, daemon=True)
            closer_t.start()
            self.assertFalse(done.wait(0.2),
                             "创建未登记完成前 shutdown 必须等在锁外，不得提前收尾")
            release.set()
            self.assertTrue(done.wait(5), "登记完成后 shutdown 必须完成收尾")
            finish.set()            # 收尾完成后再放进程走完 communicate
            worker.join(5)
            closer_t.join(5)
        self.assertEqual(kills, made, "shutdown 快照必须接住已登记的活进程并收走")

    def _queued_refusal(self, do_request, event_kind):
        """排队请求在关闭后到达创建点：拒绝创建、恰一次取消终态、无组件码。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        entered, proceed = threading.Event(), threading.Event()

        def gate_cmd(*a):
            entered.set()
            proceed.wait(5)
            return ["fake-worker"]

        popen_calls = []

        def counting_popen(args, **kwargs):
            popen_calls.append(args)
            raise AssertionError("关闭后不得创建进程")

        events = []
        api._emit = lambda kind, payload=None: events.append((kind, payload))
        with mock.patch.object(app, "worker_command", gate_cmd), \
                mock.patch.object(app, "spawn_owned", counting_popen):
            worker = threading.Thread(target=do_request, args=(api,), daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), "排队线程必须先到达创建点之前")
            api.shutdown()          # 创建者还没进锁：shutdown 零等待完成
            proceed.set()
            worker.join(5)
        self.assertEqual(popen_calls, [], "关闭后排队请求不得创建任何进程")
        finals = [payload for kind, payload in events if kind == event_kind]
        self.assertEqual(len(finals), 1, "%s 请求必须恰一次终态" % event_kind)
        self.assertNotIn("runtime_error", finals[0], "关闭取消不是组件错误")
        return api

    def test_queued_check_refuses_creation_after_closing(self):
        """已排队的 check 在关闭后到达创建点：拒绝创建、恰一次取消终态。"""
        api = self._queued_refusal(lambda api: api._do_check(), "check")
        self.assertFalse(api._checking, "finally 必须清「检查中」标记")

    def test_queued_list_refuses_creation_after_closing(self):
        """已排队的 list 在关闭后到达创建点：拒绝创建、恰一次取消终态。"""
        api = self._queued_refusal(lambda api: api._do_list(), "activities")
        self.assertFalse(api._listing, "finally 必须清「拉列表」标记")

    def test_plan_task_refuses_creation_after_closing(self):
        """计划任务在关闭后到达创建点：_run_plan_task 抛关闭拒绝（取消语义）。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        spec = SimpleNamespace(task_id="task-01-a1", activity_id="a1", name="活动",
                               sign_start="2099-01-01 09:00:00",
                               sign_end="2099-01-02 09:00:00",
                               lead_s=100, retry_for_s=120, max_attempts=0,
                               headed=False)
        entered, proceed = threading.Event(), threading.Event()

        def gate_cmd(*a):
            entered.set()
            proceed.wait(5)
            return ["fake-worker"]

        popen_calls = []

        def counting_popen(args, **kwargs):
            popen_calls.append(args)
            raise AssertionError("关闭后不得创建进程")

        errors = []

        def work():
            try:
                api._run_plan_task(spec, threading.Event(), None)
            except Exception as exc:  # noqa: BLE001 - 断言的就是这个异常
                errors.append(exc)

        with mock.patch.object(app, "worker_command", gate_cmd), \
                mock.patch.object(app.subprocess, "Popen", counting_popen):
            worker = threading.Thread(target=work, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5))
            api.shutdown()
            proceed.set()
            worker.join(5)
        self.assertEqual(popen_calls, [], "关闭后计划任务不得创建进程")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], app._ClosingError,
                              "计划任务的关闭拒绝必须是取消语义异常，不是组件错误")

    def test_runner_converts_closing_refusal_to_canceled(self):
        """计划运行中关闭：runner 把关闭拒绝转成 canceled，协调器照常收出唯一 plan_done。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        # 已开放场次（instant_signup）：协调器立即启动任务线程——
        # 未来场次是 pre_register，真实调度会等到准备时刻，测试里永远到不了创建点
        item = {"id": "a1", "name": "活动", "sign_start": "2026-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}
        # R05：先登记权威缓存再开始；这里验证的是关闭/校验交错，不是陈旧快照门禁
        api._activities = {item["id"]: dict(item)}
        entered, proceed = threading.Event(), threading.Event()
        events = []
        plan_done = threading.Event()

        def fake_task(api_self, spec, cancel_event, status):
            # 挂在类上的普通函数经实例访问会绑定 self：首参是 Api 实例
            entered.set()
            proceed.wait(5)
            raise app._ClosingError("程序正在关闭，本场次未启动")

        def capture(kind, payload=None):
            events.append((kind, payload))
            if kind == "plan_done":
                plan_done.set()

        api._emit = capture
        with mock.patch.object(app.Api, "_run_plan_task", fake_task):
            # 整段编排必须在补丁存活期内：start_plan 返回≠任务线程已到创建点，
            # 补丁提前撤销会让线程拿回真方法、真实拉起 worker
            res = api.start_plan([dict(item)])
            self.assertTrue(res.get("ok"), "计划本身应能启动（拒绝发生在任务创建点）")
            self.assertTrue(entered.wait(5), "任务线程必须到达关闭拒绝边界")
            api.shutdown()          # 先停协调器（排队任务标 canceled），再放行拒绝
            proceed.set()
            self.assertTrue(plan_done.wait(5), "计划必须收出唯一一次 plan_done")
        plan_dones = [payload for kind, payload in events if kind == "plan_done"]
        self.assertEqual(len(plan_dones), 1, "plan_done 恰一次")
        self.assertEqual(api._plan, None, "计划收尾后 Api 不得再持有协调器")
        tasks = [payload for kind, payload in events if kind == "task"]
        self.assertTrue(tasks, "任务终态事件必须存在")
        self.assertNotIn("failed", [payload.get("status") for payload in tasks],
                         "关闭拒绝不得冒充报名失败")
        self.assertEqual(tasks[-1].get("status"), "canceled",
                         "任务最后一个事件必须是 canceled 终态")
        self.assertEqual(plan_dones[0]["summary"]["counts"].get("canceled"), 1,
                         "计划汇总必须计 1 场 canceled")

    def test_concurrent_shutdowns_close_out_once_without_deadlock(self):
        """并发两次 shutdown：只真正收尾一次（stop 恰一次、每进程恰收一次）、无死锁。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        plan = mock.Mock()
        api._plan = plan
        p_login, p_plan = _FakeProc(pid=1001), _FakeProc(pid=1002)
        api._proc = p_login
        api._plan_procs["task-01"] = p_plan
        kills = []
        barrier = threading.Barrier(2)

        def closer():
            barrier.wait(5)
            api.shutdown()

        with mock.patch.object(app, "_kill_tree", lambda proc: kills.append(proc)):
            threads = [threading.Thread(target=closer, daemon=True) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(5)
            self.assertFalse(any(thread.is_alive() for thread in threads),
                             "并发 shutdown 必须都能完成（无死锁）")
        plan.stop.assert_called_once_with()
        self.assertEqual(len(kills), 2, "每个登记进程恰被收走一次（重复 shutdown 不重复收尾）")
        self.assertEqual({id(proc) for proc in kills}, {id(p_login), id(p_plan)})


class ShutdownAcceptTests(unittest.TestCase):
    """FB1 计划接纳原子化与 FB2 关闭完成信号的行为回归（事件/屏障驱动，全内存替身）。

    协调器一律 mock（不真实 start）、树终止 patch 为打点替身：补丁作用域覆盖
    线程创建至 join，零真实 Popen、零学校访问、无 sleep 猜次序。本轮只定义不运行。
    """

    def setUp(self):
        self.app = _app()

    @staticmethod
    def _instant_item():
        # 已开放场次（instant_signup）：请求合法且协调器无需等待即可调度
        return {"id": "a1", "name": "活动", "sign_start": "2026-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}

    def test_concurrent_start_plans_accept_exactly_one(self):
        """两请求都越过开头 busy 检查后在最终接纳点串行：恰一个接纳、一个拒绝、一个协调器启动。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        item = self._instant_item()
        # 计划接纳改为以本进程缓存为权威（R05）：先登记同源快照再开始。
        # 这里验证的是接纳/关闭交错，不是陈旧快照门禁（后者有专门用例）
        api._activities = {item["id"]: dict(item)}
        barrier = threading.Barrier(2)
        real_validate = app.validate_plan

        def gate_validate(normalized, now=None, signed_activities=None):
            barrier.wait(5)          # 两请求都越过开头 busy 检查后才放行
            return real_validate(normalized, now=now,
                                 signed_activities=signed_activities)

        instances = []

        def fake_coord(plan_id, specs, runner, emit, now=None):
            inst = mock.Mock()
            inst.plan_id = plan_id
            # 真实协调器登记后任务全 queued → snapshot 为 running（busy 判据）；
            # 替身必须还原这一语义，否则最终接纳点的 busy 重检判不出
            inst.snapshot = mock.Mock(return_value={"status": "running"})
            # Api 的 busy 判定改读已发布状态（P2-1），替身必须还原同一语义
            inst.published_status = mock.Mock(return_value="running")
            instances.append(inst)
            return inst

        with mock.patch.object(app, "validate_plan", gate_validate), \
                mock.patch.object(app, "PlanCoordinator", fake_coord):
            results = [None, None]

            def starter(index):
                results[index] = api.start_plan([dict(item)])

            threads = [threading.Thread(target=starter, args=(i,), daemon=True)
                       for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(5)
            self.assertFalse(any(thread.is_alive() for thread in threads),
                             "并发接纳不得死锁")
        self.assertEqual(len(instances), 2, "两请求各自构建协调器（接纳点前无法共享）")
        started = [inst for inst in instances if inst.start.call_count == 1]
        self.assertEqual(len(started), 1, "恰一个协调器被启动")
        self.assertIs(api._plan, started[0], "_plan 不得被后到请求覆盖")
        oks = [r for r in results if r and r.get("ok")]
        refused = [r for r in results if r and not r.get("ok")]
        self.assertEqual(len(oks), 1, "恰一个请求接纳")
        self.assertEqual(len(refused), 1, "另一请求被拒")
        self.assertIn("先停止", refused[0]["text"], "拒绝话术沿用既有 busy 口径")

    def test_request_paused_before_reservation_refused_after_shutdown(self):
        """请求停在校验后、最终预留前，shutdown 先完成：放行后被拒、零启动、无新计划。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        item = self._instant_item()
        # 计划接纳改为以本进程缓存为权威（R05）：先登记同源快照再开始。
        # 这里验证的是接纳/关闭交错，不是陈旧快照门禁（后者有专门用例）
        api._activities = {item["id"]: dict(item)}
        entered, release = threading.Event(), threading.Event()
        made = []

        def gate_coord(plan_id, specs, runner, emit, now=None):
            entered.set()            # 已过开头检查，停在校验后、最终预留前
            release.wait(5)
            inst = mock.Mock()
            inst.plan_id = plan_id
            made.append(inst)
            return inst

        holder = {}

        def starter():
            holder["res"] = api.start_plan([dict(item)])

        with mock.patch.object(app, "PlanCoordinator", gate_coord):
            worker = threading.Thread(target=starter, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), "请求必须先到达预留边界之前")
            api.shutdown()           # 关闭先完成：快照看不到未预留的请求
            release.set()
            worker.join(5)
        self.assertFalse(holder["res"].get("ok"), "最终接纳点必须核到关闭已开始")
        self.assertIn("关闭", holder["res"]["text"])
        self.assertEqual(made and made[0].start.call_count, 0, "未接纳请求零 start")
        self.assertIsNone(api._plan, "未接纳的请求不得留下计划")

    def test_shutdown_stops_reserved_coordinator(self):
        """已预留的协调器必须被 shutdown 快照看见并置停（预留与快照同锁）。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        item = self._instant_item()
        # 计划接纳改为以本进程缓存为权威（R05）：先登记同源快照再开始。
        # 这里验证的是接纳/关闭交错，不是陈旧快照门禁（后者有专门用例）
        api._activities = {item["id"]: dict(item)}
        inst = mock.Mock()
        inst.plan_id = "p1"
        with mock.patch.object(app, "PlanCoordinator", lambda *a, **k: inst):
            res = api.start_plan([dict(item)])
        self.assertTrue(res.get("ok"))
        self.assertIs(api._plan, inst)
        api.shutdown()
        inst.stop.assert_called_once_with()   # 预留后关闭必须置停协调器

    def test_start_failure_releases_own_reservation_only(self):
        """coordinator.start 抛错：释放本人预留、下一次正常请求可开始、不清别的计划。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        item = self._instant_item()
        # 计划接纳改为以本进程缓存为权威（R05）：先登记同源快照再开始。
        # 这里验证的是接纳/关闭交错，不是陈旧快照门禁（后者有专门用例）
        api._activities = {item["id"]: dict(item)}
        boom = mock.Mock()
        boom.start.side_effect = RuntimeError("计划已经在运行")
        boom.snapshot = mock.Mock(return_value={"status": "running"})
        boom.published_status = mock.Mock(return_value="running")
        ok_inst = mock.Mock()
        ok_inst.plan_id = "p2"
        ok_inst.snapshot = mock.Mock(return_value={"status": "running"})
        ok_inst.published_status = mock.Mock(return_value="running")
        made = []

        def factory(plan_id, specs, runner, emit, now=None):
            inst = ok_inst if made else boom
            made.append(inst)
            return inst

        with mock.patch.object(app, "PlanCoordinator", factory):
            res1 = api.start_plan([dict(item)])
            self.assertFalse(res1.get("ok"))
            self.assertIn("计划没能开始", res1["text"], "启动失败返回可读结论")
            self.assertIsNone(api._plan, "失败必须撤销本请求的预留")
            res2 = api.start_plan([dict(item)])
            self.assertTrue(res2.get("ok"), "释放后下一次正常请求可开始")
            res3 = api.start_plan([dict(item)])
            self.assertFalse(res3.get("ok"), "已有计划时新请求被拒")
            self.assertIs(api._plan, ok_inst, "拒绝路径不得清掉已接纳的计划")

    def test_second_shutdown_waits_for_closeout_completion(self):
        """后到 shutdown 等首次收尾的完成信号：释放前都不返回、锁外等待、每 PID 恰收一次。"""
        app = self.app
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        plan = mock.Mock()
        api._plan = plan
        p_login, p_plan = _FakeProc(pid=2001), _FakeProc(pid=2002)
        api._proc = p_login
        api._plan_procs["task-01"] = p_plan
        kills = []
        entered, release = threading.Event(), threading.Event()

        def gate_kill(proc):
            kills.append(proc)
            entered.set()            # 首次收尾停在树终止中段
            release.wait(5)

        d1, d2 = threading.Event(), threading.Event()

        def closer(flag):
            api.shutdown()
            flag.set()

        with mock.patch.object(app, "_kill_tree", gate_kill):
            s1 = threading.Thread(target=closer, args=(d1,), daemon=True)
            s1.start()
            self.assertTrue(entered.wait(5), "首次收尾必须到达树终止边界")
            s2 = threading.Thread(target=closer, args=(d2,), daemon=True)
            s2.start()
            self.assertFalse(d1.wait(0.1), "收尾未完成时首次调用不得返回")
            self.assertFalse(d2.wait(0.1), "后到调用必须等待完成信号，不得提前返回")
            self.assertTrue(api._lock.acquire(timeout=1),
                            "等待完成信号不得持有 Api 锁（锁内等待会死锁）")
            api._lock.release()
            release.set()
            s1.join(5)
            s2.join(5)
            self.assertTrue(d1.is_set() and d2.is_set(), "释放后两个调用都必须退出")
        plan.stop.assert_called_once_with()
        self.assertEqual(kills, [p_plan, p_login], "每个登记 PID 恰收一次")
        self.assertTrue(api._shutdown_done_event.is_set(), "完成信号由收尾 finally 发出")


class RuntimeCheckTests(unittest.TestCase):
    """--runtime-check 离线探针：前置早返回、临时数据根必填、JSON/退出码契约。

    worker 一律 mock 成无害本地命令（零学校调用）；mock 通过≠真实冻结验收——
    「仅含单 EXE 的空目录实际启动内置 worker --help」仍须授权后实包执行。
    """

    def setUp(self):
        self.app = _app()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.session = self.tmp / "session.json"
        for patch in (mock.patch.object(self.app, "SESSION_FILE", self.session),
                      mock.patch.object(self.app, "PREFS", self.tmp / "ui.json")):
            patch.start()
            self.addCleanup(patch.stop)

    def _report(self) -> Path:
        return self.tmp / "report.json"

    def _argv(self, report: Path) -> list:
        return ["app.py", "--runtime-check", "--report", str(report)]

    def test_missing_report_arg_returns_2_without_json(self):
        """前置早返回：缺 --report 直接退出码 2，什么都不写。"""
        rc = self.app._runtime_check_main(["app.py", "--runtime-check"])
        self.assertEqual(rc, 2)
        self.assertFalse(self.tmp.joinpath("report.json").exists())

    def test_missing_data_dir_refused_and_reported(self):
        """临时数据根必填：缺 CAMPUS_DATA_DIR 拒绝运行，结论落 JSON、退出码 1。"""
        report = self._report()
        env = {k: v for k, v in os.environ.items() if k != "CAMPUS_DATA_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            rc = self.app._runtime_check_main(self._argv(report))
        self.assertEqual(rc, 1)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(data["ok"])
        self.assertIn("CAMPUS_DATA_DIR", data["error"], "拒绝原因要指明缺什么")

    def test_worker_help_success_writes_clean_json(self):
        """worker --help 成功：JSON ok=true + 退出码 0，进程退出码 0；载荷脱敏。"""
        report = self._report()
        with mock.patch.dict(os.environ, {"CAMPUS_DATA_DIR": str(self.tmp / "data")}), \
                mock.patch.object(self.app, "worker_command",
                                  lambda *a: [sys.executable, "-c", "import sys; sys.exit(0)"]):
            rc = self.app._runtime_check_main(self._argv(report))
        self.assertEqual(rc, 0)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(data["exit_code"], 0)
        for key in ("version", "frozen", "worker"):
            self.assertIn(key, data, "报告必须带 %s（版本/frozen/组件来源）" % key)
        self.assertNotIn("token", report.read_text(encoding="utf-8").lower(),
                         "报告必须脱敏")
        self.assertFalse(self.session.exists(), "探针不得触碰真实登录态文件")

    def test_worker_help_timeout_kills_and_reports(self):
        """worker --help 超时：树终止挂着的进程，JSON ok=false + 超时说明、退出码 1。"""
        report = self._report()
        with mock.patch.dict(os.environ, {"CAMPUS_DATA_DIR": str(self.tmp / "data")}), \
                mock.patch.object(self.app, "worker_command",
                                  lambda *a: [sys.executable, "-c", "import time; time.sleep(30)"]), \
                mock.patch.object(self.app, "RUNTIME_CHECK_TIMEOUT_S", 0.3):
            rc = self.app._runtime_check_main(self._argv(report))
        self.assertEqual(rc, 1)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(data["ok"])
        self.assertIn("超时", data["error"])

    def test_worker_missing_reported(self):
        """组件缺失：JSON component=worker_missing + 人话错误、退出码 1，零子进程。"""
        report = self._report()
        with mock.patch.dict(os.environ, {"CAMPUS_DATA_DIR": str(self.tmp / "data")}), \
                mock.patch.object(self.app, "GRAB", self.tmp / "gone.exe"):
            rc = self.app._runtime_check_main(self._argv(report))
        self.assertEqual(rc, 1)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(data["ok"])
        self.assertEqual(data["component"], "worker_missing")
        self.assertIn("程序组件缺失", data["error"])

    def test_dispatch_precedes_gui_and_data_dir(self):
        """分发顺序锁死：runtime-check 先于数据根初始化、生命周期与窗口创建。"""
        src = read("local/app.py")
        main_src = src[src.index("def main("):]
        probe_at = main_src.index("--runtime-check")
        self.assertLess(probe_at, main_src.index("ensure_data_dir()"),
                        "runtime-check 必须先于数据根初始化分发")
        self.assertLess(probe_at, main_src.index("webview.create_window"),
                        "runtime-check 必须先于窗口创建分发")
        # 正常关闭：先收 worker（shutdown），再写关闭时刻（finalize）
        self.assertLess(main_src.index("api.shutdown()"),
                        main_src.index("lifecycle.finalize()"),
                        "关闭必须先收本实例 worker，再 finalize 生命周期")


class WindowGeometryTests(unittest.TestCase):
    """窗口出厂几何：目标 1280×820、最小 1024×680，小屏收敛且托底不塌缩。"""

    def setUp(self):
        self.app = _app()

    def test_geometry_none_returns_defaults(self):
        """QA/无显示环境：拿不到屏幕信息就直接用出厂几何，不抛错。"""
        self.assertEqual(self.app._window_geometry(None), (1280, 820, 1024, 680))

    def test_geometry_large_screen_keeps_target(self):
        """大屏：宽高都充足，完整使用目标尺寸。"""
        self.assertEqual(self.app._window_geometry((1920, 1000)),
                         (1280, 820, 1024, 680))

    def test_geometry_short_screen_height_floors_to_min(self):
        """1366×768 档：可用高度不够放 820，高度收敛后托底到 min_h。"""
        self.assertEqual(self.app._window_geometry((1366, 688)),
                         (1280, 680, 1024, 680))

    def test_geometry_tiny_screen_both_floored(self):
        """1000×600 档：宽高都低于最小值，双托底（宁可略超不塌缩）。"""
        self.assertEqual(self.app._window_geometry((1000, 600)),
                         (1024, 680, 1024, 680))

    def test_create_window_keeps_min_size(self):
        """源码契约：create_window 必须绑定 min_size=(min_w, min_h)，防最小尺寸被删。"""
        src = read("local/app.py")
        main_src = src[src.index("def main("):]
        self.assertIn("min_size=(min_w, min_h)", main_src,
                      "create_window 必须带上最小尺寸")


class PlanDoneCommitOrderTests(unittest.TestCase):
    """FR05：plan_done 发布之前，可观察的完成状态必须已经提交。

    Api._lock 是普通 Lock（非可重入）——回调里再取锁会当场死锁，
    所以「在回调里立即读状态」同时验证了顺序与解锁两件事。
    """

    def setUp(self):
        self.app = _app()

    @staticmethod
    def _item():
        return {"id": "a1", "name": "活动", "sign_start": "2026-01-01 09:00:00",
                "sign_end": "2099-01-02 09:00:00",
                "act_start": "2099-01-03 09:00:00", "act_end": "2099-01-03 11:00:00",
                "signed": False}

    def _api(self):
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        item = self._item()
        api._activities = {item["id"]: dict(item)}
        return api, item

    def test_callback_sees_committed_terminal_state(self):
        app = self.app
        api, item = self._api()
        seen = {}
        done = threading.Event()
        real_emit = api._emit

        def recorder(kind, payload):
            if kind == "plan_done":
                # 同步读取：不睡、不等线程，就在发布的那一刻
                seen["plan"] = api._plan
                seen["last"] = api._last_plan
                seen["request"] = api.start_request_state("rid-order")
                done.set()
            real_emit(kind, payload)

        api._emit = recorder

        def fake_coord(plan_id, specs, runner, emit, now=None):
            inst = mock.Mock()
            inst.plan_id = plan_id
            inst.snapshot = mock.Mock(return_value={"status": "completed", "tasks": []})

            def start():
                emit("plan_done", {"plan_id": plan_id, "status": "completed",
                                   "summary": {"total": 0, "counts": {}}})

            inst.start = start
            return inst

        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            res = api.start_plan([item], request_id="rid-order")
        self.assertTrue(res["ok"], res)
        self.assertTrue(done.wait(5), "plan_done 必须发出来")
        self.assertIsNone(seen["plan"], "plan_done 回调里 _plan 必须已是 None")
        self.assertIsNotNone(seen["last"], "终态快照必须在发布前写好")
        self.assertEqual(seen["last"].get("status"), "completed")
        self.assertEqual(seen["request"]["state"], "accepted")
        self.assertTrue(seen["request"].get("finished"), "对账记录必须已标完成")
        self.assertFalse(api._is_busy())

    def test_late_plan_done_cannot_overwrite_newer_plan(self):
        app = self.app
        api, item = self._api()
        captured = {}
        old_done = threading.Event()

        def fake_coord(plan_id, specs, runner, emit, now=None):
            inst = mock.Mock()
            inst.plan_id = plan_id
            captured.setdefault("emit", emit)
            captured.setdefault("ids", []).append(plan_id)
            # 第一个计划一直「运行中」；第二个计划也保持运行，方便观察归属
            inst.snapshot = mock.Mock(return_value={"status": "running", "tasks": []})
            return inst

        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-1")
            self.assertTrue(first["ok"], first)
            old_emit = captured["emit"]
            # 让旧计划先结束一次，把 _last_plan 填上
            old_emit("plan_done", {"plan_id": first["plan_id"], "status": "completed",
                                   "summary": {"total": 0, "counts": {}}})
            old_done.set()
            self.assertIsNotNone(api._last_plan, "旧计划结束后应有终态快照")
            self.assertIsNone(api._plan, "旧计划结束后 _plan 应为 None")

            second = api.start_plan([item], request_id="rid-2")
            self.assertTrue(second["ok"], second)
            self.assertIsNotNone(api._plan, "新计划应占用当前槽")
            # 旧计划迟到的完成事件：不得覆盖新计划，也不得改写终态快照
            old_emit("plan_done", {"plan_id": first["plan_id"], "status": "failed",
                                   "summary": {"total": 0, "counts": {}}})
        self.assertEqual(api._plan.plan_id, second["plan_id"],
                         "旧计划迟到的 plan_done 不得清空后来计划")
        self.assertIsNone(api._last_plan,
                          "新计划在运行时不该被旧计划的终态快照覆盖")

    def test_live_accepted_request_survives_rejection_flood(self):
        """运行中的已接纳请求不能被大量拒绝请求挤出留档，否则对账只剩 unknown。"""
        app = self.app
        api, item = self._api()
        emitted = {}

        def fake_coord(plan_id, specs, runner, emit, now=None):
            inst = mock.Mock()
            inst.plan_id = plan_id
            inst.snapshot = mock.Mock(return_value={"status": "running", "tasks": []})
            emitted["emit"] = emit
            return inst

        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-live")
            self.assertTrue(first["ok"], first)
            for index in range(40):
                with api._lock:
                    api._remember_start("rid-flood-%d" % index, "rejected",
                                        result={"ok": False, "text": "busy"})
            live = api.start_request_state("rid-live")
            self.assertEqual(live["state"], "accepted",
                             "运行中的已接纳请求不得被拒绝请求挤出留档")
            self.assertEqual(live["plan_id"], first["plan_id"])
            # plan_done 写入终态后保护才解除，之后允许按上限淘汰
            emitted["emit"]("plan_done", {"plan_id": first["plan_id"],
                                          "status": "completed",
                                          "summary": {"total": 0, "counts": {}}})
            for index in range(40, 80):
                with api._lock:
                    api._remember_start("rid-flood-%d" % index, "rejected",
                                        result={"ok": False, "text": "busy"})
        self.assertEqual(api.start_request_state("rid-live")["state"], "unknown",
                         "plan_done 之后应按留档上限正常淘汰")

    # ---------- P1：旧计划事件隔离与终态快照归属 ----------

    def _dual_plan_api(self):
        """两个 mock 协调器的 Api：emissions[plan_id] 可直接发事件。"""
        api, item = self._api()
        emissions = {}
        snapshots = {}

        def fake_coord(plan_id, specs, runner, emit, now=None):
            inst = mock.Mock()
            inst.plan_id = plan_id
            snapshots[plan_id] = {"plan_id": plan_id, "status": "stopped", "tasks": []}
            # 每次取快照返回新副本：终态提交写进 Api 的是独立对象，不是共享引用
            inst.snapshot = mock.Mock(side_effect=lambda: dict(snapshots[plan_id]))
            emissions[plan_id] = emit
            return inst

        return api, item, emissions, snapshots, fake_coord

    def test_late_done_not_forwarded_after_newer_plan_accepted(self):
        """A 完成后 B 接纳：A 迟到的 plan_done 不得再广播到界面（P1）。"""
        app = self.app
        api, item, emissions, _, fake_coord = self._dual_plan_api()
        forwarded = []
        real_emit = api._emit

        def recorder(kind, payload):
            if isinstance(payload, dict):
                forwarded.append((kind, str(payload.get("plan_id") or "")))
            real_emit(kind, payload)

        api._emit = recorder
        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-a")
            self.assertTrue(first["ok"], first)
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "stopped", "summary": {}})
            forwarded.clear()
            second = api.start_plan([item], request_id="rid-b")
            self.assertTrue(second["ok"], second)
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "failed", "summary": {}})
        self.assertEqual(api._plan.plan_id, second["plan_id"])
        stale = [kind for kind, pid in forwarded if pid == first["plan_id"]]
        self.assertEqual(stale, [],
                         "旧计划迟到的 plan_done 不得转发给当前界面")

    def test_late_progress_events_not_forwarded(self):
        """B 运行中：旧 A 的 plan/task 进度事件同样不得广播（P1）。"""
        app = self.app
        api, item, emissions, _, fake_coord = self._dual_plan_api()
        forwarded = []
        real_emit = api._emit

        def recorder(kind, payload):
            if isinstance(payload, dict):
                forwarded.append((kind, str(payload.get("plan_id") or "")))
            real_emit(kind, payload)

        api._emit = recorder
        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-a")
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "stopped", "summary": {}})
            forwarded.clear()
            second = api.start_plan([item], request_id="rid-b")
            self.assertTrue(second["ok"], second)
            emissions[first["plan_id"]]("plan", {
                "plan_id": first["plan_id"], "status": "running", "tasks": []})
            emissions[first["plan_id"]]("task", {
                "plan_id": first["plan_id"], "task_id": "t1", "status": "running"})
        stale = [kind for kind, pid in forwarded if pid == first["plan_id"]]
        self.assertEqual(stale, [],
                         "旧计划迟到的 plan/task 事件不得广播到当前界面")

    def test_late_done_cannot_overwrite_snapshot_after_newer_plan_finished(self):
        """B 已结束（_plan=None、_last_plan=B）：A 迟到完成不得覆盖快照（P1）。"""
        app = self.app
        api, item, emissions, snapshots, fake_coord = self._dual_plan_api()
        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-a")
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "completed", "summary": {}})
            second = api.start_plan([item], request_id="rid-b")
            self.assertTrue(second["ok"], second)
            snapshots[second["plan_id"]]["status"] = "stopped"
            emissions[second["plan_id"]]("plan_done", {
                "plan_id": second["plan_id"], "status": "stopped", "summary": {}})
            self.assertIsNone(api._plan, "B 已结束：槽应为空")
            self.assertEqual(api._last_plan.get("plan_id"), second["plan_id"])
            # 旧 A 的迟到完成：槽为空≠归属最新计划
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "failed", "summary": {}})
        self.assertEqual(api._last_plan.get("plan_id"), second["plan_id"],
                         "较新计划已结束后，旧计划的迟到完成不得覆盖终态快照")
        self.assertEqual(api._last_plan.get("status"), "stopped")

    def test_duplicate_done_keeps_first_conclusion(self):
        """同一计划重复终态：结论与留档以第一次为准，不被重复包改写（P1）。"""
        app = self.app
        api, item, emissions, _, fake_coord = self._dual_plan_api()
        with mock.patch.object(app, "PlanCoordinator", fake_coord):
            first = api.start_plan([item], request_id="rid-a")
            self.assertTrue(first["ok"], first)
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "stopped", "summary": {}})
            first_last = dict(api._last_plan or {})
            emissions[first["plan_id"]]("plan_done", {
                "plan_id": first["plan_id"], "status": "failed", "summary": {}})
        self.assertEqual((api._last_plan or {}).get("status"),
                         first_last.get("status"),
                         "重复终态不得把已定结论改成另一状态")
        record = api.start_request_state("rid-a")
        self.assertEqual(record.get("state"), "accepted")
        self.assertEqual((record.get("snapshot") or {}).get("status"), "stopped",
                         "重复终态不得把 request_id 留档结论改成另一状态")

    def test_events_and_bootstrap_carry_generation_and_request_id(self):
        """内部事件与 bootstrap 快照携带 plan_id/plan_generation/request_id（P1）。"""
        app = self.app
        api, item, emissions, snapshots, fake_coord = self._dual_plan_api()
        seen = []
        real_emit = api._emit

        def recorder(kind, payload):
            if isinstance(payload, dict):
                seen.append((kind, dict(payload)))
            real_emit(kind, payload)

        api._emit = recorder

        def coord_with_plan_event(plan_id, specs, runner, emit, now=None):
            inst = fake_coord(plan_id, specs, runner, emit)

            def start():
                emit("plan", {"plan_id": plan_id, "status": "ready", "tasks": []})
                emit("plan_done", {"plan_id": plan_id, "status": "stopped",
                                   "summary": {}})

            inst.start = start
            return inst

        with mock.patch.object(app, "PlanCoordinator", coord_with_plan_event):
            res = api.start_plan([item], request_id="rid-gen")
            self.assertTrue(res["ok"], res)
            boot = api.bootstrap()
        kinds = {kind: payload for kind, payload in seen}
        plan_event = kinds.get("plan") or {}
        done_event = kinds.get("plan_done") or {}
        self.assertGreaterEqual(int(plan_event.get("plan_generation", 0)), 1,
                                "plan 事件必须携带接纳代次")
        self.assertEqual(plan_event.get("request_id"), "rid-gen")
        self.assertGreaterEqual(int(done_event.get("plan_generation", 0)), 1,
                                "plan_done 事件必须携带接纳代次")
        self.assertEqual(done_event.get("request_id"), "rid-gen")
        boot_plan = boot.get("plan") or {}
        self.assertEqual(int(boot_plan.get("plan_generation", 0)),
                         int(plan_event.get("plan_generation")),
                         "bootstrap 快照的代次必须与接纳代次一致")
        self.assertEqual(boot_plan.get("request_id"), "rid-gen")


class BuildEmbedsWorkerTests(unittest.TestCase):
    """构建脚本把 worker 作为数据资源打进主程序（mock 定义，不运行 PyInstaller）。"""

    def setUp(self):
        sys.path.insert(0, str(LOCAL / "build"))   # 打包脚本在 local/build/
        try:
            import build_exe
        except Exception as exc:
            raise unittest.SkipTest("无法导入 build_exe：%s" % exc)
        finally:
            sys.path.pop(0)
        self.be = build_exe

    def test_worker_built_before_main_and_embedded_as_data(self):
        """先构建 worker 再构建主程序；worker 以数据资源进资源根，不用 --add-binary。"""
        src = read("local/build/build_exe.py")
        assemble = src[src.index("def assemble"):src.index("def main(")]
        self.assertLess(assemble.index('run_pyinstaller("grab-worker"'),
                        assemble.index('run_pyinstaller("campus-activity-watch"'),
                        "必须先构建 worker，再作为资源构建主程序")
        self.assertIn('extra_data=[(worker, "."), (VERSION_FILE, ".")]',
                      assemble,
                      "实际构建出的 worker 与 VERSION 以 dest=\".\" 进资源根"
                      "（--add-data 对文件源按 dest/源文件名归档，写 dest=文件名会变成同名目录）")
        self.assertNotIn('"--add-binary"', src,
                         "不得把 --add-binary 参数传给 PyInstaller 重新分析 worker 依赖")
        self.assertNotIn('OUT / "grab-worker.exe"', assemble,
                         "OUT 根目录不再放置外置 worker（独立 EXE 定位）")
        self.assertIn("prune_output(out,", assemble, "重建清理通路保留")
        self.assertIn('if child.name == "data":', src, "prune_output 仍跳过 data")

    def test_assemble_embeds_worker_and_skips_sidecar(self):
        """mock 构建行为：记录 run_pyinstaller 调用序与 extra_data 指向实际 worker/VERSION。"""
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            out = tmp / "out"
            fake_worker = tmp / "stage-worker" / "dist" / "grab-worker.exe"
            fake_worker.parent.mkdir(parents=True)
            fake_worker.write_bytes(b"worker")
            fake_app = tmp / "stage-app" / "dist" / "campus-activity-watch.exe"
            fake_app.parent.mkdir(parents=True)
            fake_app.write_bytes(b"app")
            calls = []

            def fake_run(name_, source, mode, add_ui, extra_data=None):
                calls.append((name_, list(extra_data or [])))
                return fake_worker if name_ == "grab-worker" else fake_app

            with mock.patch.object(self.be, "OUT", out), \
                    mock.patch.object(self.be, "run_pyinstaller", fake_run):
                result = self.be.assemble("onefile")
            self.assertEqual(result, out, "onefile 输出路径保持既有 dist/campus-grab-exe")
            self.assertEqual([c[0] for c in calls],
                             ["grab-worker", "campus-activity-watch"],
                             "构建顺序：worker 先于主程序")
            embed = {Path(src_).name: dest for src_, dest in calls[1][1]}
            # --add-data 对文件源按 dest/basename 归档：dest="." 时 basename
            # （恰为 grab-worker.exe）就是资源根的最终落点
            self.assertEqual(embed.get("grab-worker.exe"), ".",
                             "extra_data 必须指向实际构建出的 worker，dest=\".\" 落资源根")
            self.assertEqual(embed.get("VERSION"), ".", "VERSION 同批进资源根")
            self.assertTrue((out / "campus-activity-watch.exe").is_file())
            self.assertFalse((out / "grab-worker.exe").exists(),
                             "OUT 根目录不再有外置 worker")
            self.assertTrue((out / "data").is_dir(), "data 占位目录维持旧布局")

    def test_assemble_onedir_uses_versioned_output_without_runtime_dirs(self):
        """onedir 输出隔离到版本目录，发行目录不预建运行时 data/config/log。"""
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            onefile_out = tmp / "onefile"
            onedir_root = tmp / "campus-grab-exe-onedir"
            stale_output = onedir_root / "1.2.2"
            for runtime_name in ("data", "config", "log"):
                (stale_output / runtime_name).mkdir(parents=True)
            fake_worker = tmp / "stage-worker" / "dist" / "grab-worker.exe"
            fake_worker.parent.mkdir(parents=True)
            fake_worker.write_bytes(b"worker")
            fake_app = (tmp / "stage-app" / "dist" / "campus-activity-watch"
                        / "campus-activity-watch.exe")
            fake_app.parent.mkdir(parents=True)
            fake_app.write_bytes(b"app")
            calls = []

            def fake_run(name_, source, mode, add_ui, extra_data=None):
                calls.append((name_, mode, list(extra_data or [])))
                return fake_worker if name_ == "grab-worker" else fake_app

            with mock.patch.object(self.be, "OUT", onefile_out), \
                    mock.patch.object(self.be, "OUT_ONEDIR", onedir_root,
                                      create=True), \
                    mock.patch.object(self.be, "read_version",
                                      return_value="1.2.2"), \
                    mock.patch.object(self.be, "run_pyinstaller", fake_run):
                result = self.be.assemble("onedir")

            expected = onedir_root / "1.2.2"
            self.assertEqual(result, expected)
            self.assertTrue((expected / "campus-activity-watch.exe").is_file())
            for runtime_name in ("data", "config", "log"):
                self.assertFalse((expected / runtime_name).exists(),
                                 "onedir 发行目录不得预建运行时目录：%s" % runtime_name)
            self.assertFalse(onefile_out.exists(), "onedir 构建不得触碰 onefile 输出根")

    def test_resource_locations_match_app_resolution(self):
        """两模式资源位置与 app.py 解析同源：onedir 在 _internal，onefile 在运行期 _MEIPASS。"""
        app_src = read("local/app.py")
        self.assertIn('resource_root / "grab-worker.exe"', app_src,
                      "app.py 冻结解析 = 资源根/grab-worker.exe")
        self.assertIn("RESOURCE_ROOT = Path(getattr(sys, \"_MEIPASS\", HERE))", app_src,
                      "资源根两种模式都经 _MEIPASS（onedir 6.x 即 _internal）")
        be_src = read("local/build/build_exe.py")
        self.assertIn('extra_data=[(worker, "."), (VERSION_FILE, ".")]', be_src,
                      "--add-data 落点与 app.py 解析是同一个资源根（dest=\".\" + basename）")

    def test_onedir_builds_fixed_update_launcher_payload(self):
        """onedir 版本目录必须携带固定名称的更新启动器；onefile 不新增旁路入口。"""
        src = read("local/build/build_exe.py")
        assemble = src[src.index("def assemble"):src.index("def main(")]
        self.assertIn('run_pyinstaller("update-launcher"', assemble,
                      "onedir 必须从 update_launcher.py 构建独立入口")
        self.assertIn('LOCAL / "update_launcher.py"', assemble,
                      "更新入口源码必须来自 local/update_launcher.py")
        self.assertIn('shutil.copy2(launcher, out / "update-launcher.exe")', assemble,
                      "启动器必须放进版本 payload 根目录")

    def test_version_paths_from_version_dir_keep_shared_root(self):
        """从版本目录启动时，更新仍写安装根的 current.json。"""
        app = _app()
        paths = app.update_version_paths(
            here=Path("D:/program/versions/1.2.2"), version="1.2.2")
        self.assertEqual(paths["root"], Path("D:/program/versions"))
        self.assertEqual(paths["current_file"], Path("D:/program/current.json"))
        self.assertEqual(paths["base_dir"], Path("D:/program/versions/1.2.2"))

    def test_ready_to_restart_launches_apply_launcher_with_checked_paths(self):
        """ready_to_restart 启动 apply，并把 staging/版本根/目标版本/父 PID 一起传给入口。"""
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._update_result = {"state": "ready_to_restart", "latest_version": "1.2.2",
                              "request_id": "rid-update"}
        api._update_staging_path = "D:/versions/.staging-rid-update"
        launched = []
        with tempfile.TemporaryDirectory() as name:
            launcher = Path(name) / "update-launcher.exe"
            launcher.write_bytes(b"launcher")
            with mock.patch.object(app.sys, "frozen", True, create=True), \
                    mock.patch.object(app, "version_switch_available", return_value=True), \
                    mock.patch.object(app, "resolve_update_launcher_path",
                                      return_value=launcher):
                with mock.patch.object(app, "update_version_paths", return_value={
                        "root": Path("D:/versions"), "current_file": Path("D:/current.json"),
                        "base_dir": Path("D:/versions/1.2.1")}):
                    with mock.patch.object(app.subprocess, "Popen",
                                           side_effect=lambda args, **kwargs: launched.append((args, kwargs))):
                        result = api.update_launch("rid-update")
        self.assertTrue(result["ok"], result)
        self.assertEqual(len(launched), 1)
        args, kwargs = launched[0]
        self.assertIn("--apply", args)
        self.assertIn("--staging", args)
        self.assertIn("D:/versions/.staging-rid-update", args)
        self.assertIn("--version-root", args)
        self.assertTrue(any(str(item).replace("\\", "/") == "D:/versions" for item in args))
        self.assertIn("--target-version", args)
        self.assertIn("1.2.2", args)
        self.assertIn("--parent-pid", args)
        self.assertIn(str(os.getpid()), args)
        self.assertEqual(kwargs.get("cwd"), str(app.HERE))

    def test_ready_to_restart_stays_ready_in_development(self):
        """开发态没有旁路启动器时不切换目录，保留 ready_to_restart。"""
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._update_result = {"state": "ready_to_restart", "latest_version": "1.2.2"}
        api._update_staging_path = "D:/versions/.staging-rid-update"
        with mock.patch.object(app.sys, "frozen", False, create=True), \
                mock.patch.object(app.subprocess, "Popen") as popen:
            result = api.update_launch("rid-update")
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "ready_to_restart")
        self.assertEqual(api._update_result["state"], "ready_to_restart")
        popen.assert_not_called()

    def test_ready_to_restart_stays_ready_when_frozen_launcher_is_missing(self):
        """冻结 onefile 或残缺 onedir 没有旁路入口时不得误切换。"""
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._update_result = {"state": "ready_to_restart", "latest_version": "1.2.2"}
        api._update_staging_path = "D:/versions/.staging-rid-update"
        with mock.patch.object(app.sys, "frozen", True, create=True), \
                mock.patch.object(app, "resolve_update_launcher_path",
                                  return_value=Path("D:/missing/update-launcher.exe")), \
                mock.patch.object(app.subprocess, "Popen") as popen:
            result = api.update_launch("rid-update")
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "ready_to_restart")
        popen.assert_not_called()

    def test_ready_to_restart_refused_when_version_switch_is_unavailable(self):
        """update_launch 与下载用同一判据：不在 versions/<当前版本>/ 下运行时不起启动器。"""
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        api._update_result = {"state": "ready_to_restart", "latest_version": "1.2.2",
                              "request_id": "rid-update"}
        api._update_staging_path = "D:/versions/.staging-rid-update"
        with tempfile.TemporaryDirectory() as name:
            launcher = Path(name) / "update-launcher.exe"
            launcher.write_bytes(b"launcher")
            with mock.patch.object(app.sys, "frozen", True, create=True), \
                    mock.patch.object(app, "version_switch_available", return_value=False), \
                    mock.patch.object(app, "resolve_update_launcher_path",
                                      return_value=launcher), \
                    mock.patch.object(app.subprocess, "Popen") as popen:
                result = api.update_launch("rid-update")
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "ready_to_restart")
        popen.assert_not_called()


class BusyLockOrderContractTests(unittest.TestCase):
    """P2-1：持 Api 锁时的 busy 判定只读协调器已发布状态，绝不取协调器锁。"""

    def test_busy_check_uses_published_status_only(self):
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        plan = mock.Mock()
        plan.published_status.return_value = "running"
        plan.snapshot.side_effect = AssertionError("持 Api 锁时不得取协调器锁")
        api._plan = plan
        with api._lock:
            self.assertTrue(api._is_busy_locked())
        plan.snapshot.assert_not_called()

    def test_busy_false_for_terminal_plan(self):
        app = _app()
        api = stop_auto_relogin_on_cleanup(self, app.Api(clock=TestWallClock()))
        plan = mock.Mock()
        plan.published_status.return_value = "completed"
        api._plan = plan
        self.assertFalse(api._is_busy_locked())
        plan.snapshot.assert_not_called()


class MigrationOncePerProcessTests(unittest.TestCase):
    """G1/G3：旧数据迁移每个进程只做一次；等锁超时不是迁移结论。

    只给 runtime_paths 的模块属性打补丁（不 reload），数据根、迁移锁、旧目录全落在
    tempfile.gettempdir() 下的临时目录，不碰真实 data。
    """

    def setUp(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import runtime_paths
        finally:
            sys.path.pop(0)
        self.rp = runtime_paths
        tmp = tempfile.TemporaryDirectory(dir=tempfile.gettempdir(), prefix="campus-migrate-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.target = root / "target"
        self.target.mkdir()
        legacy = root / "old-exe"
        (legacy / "data").mkdir(parents=True)
        (legacy / "data" / "session.json").write_text('{"legacy": 1}', encoding="utf-8")
        self.legacy_data = legacy / "data"
        patchers = (
            mock.patch.object(runtime_paths, "DATA_DIR", self.target),
            mock.patch.object(runtime_paths, "MIGRATION_LOCK_FILE", self.target / "migration.lock"),
            mock.patch.object(runtime_paths, "_legacy_data_dir", lambda: self.legacy_data),
            mock.patch.object(runtime_paths, "_MIGRATION_RECORD", None),
            # create=True：基线上还没有这个标记，补丁照样能装上，失败落在断言而不是装补丁
            mock.patch.object(runtime_paths, "_MIGRATION_DONE", False, create=True),
            mock.patch.object(sys, "frozen", True, create=True),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_second_ensure_data_dir_does_not_migrate_again(self):
        """G1：冻结态下连续多次 ensure_data_dir，迁移只跑一次、迁移锁只拿一次。"""
        rp = self.rp
        real_migrate = rp._migrate_legacy_data
        with mock.patch.object(rp, "_migrate_legacy_data", wraps=real_migrate) as migrate, \
                mock.patch.object(rp, "acquire_file_lock", wraps=rp.acquire_file_lock) as acquire:
            rp.ensure_data_dir()
            rp.ensure_data_dir()
            rp.ensure_data_dir()
        self.assertEqual(migrate.call_count, 1, "完整迁移过一次后不得再迁移（每行日志都会调它）")
        self.assertEqual(acquire.call_count, 1, "不得每次都重新去抢迁移锁")
        self.assertTrue((self.target / "session.json").is_file(), "第一次照常把旧文件搬过来")

    def test_nothing_to_migrate_is_also_remembered(self):
        """G1：旧目录里什么都没有也算完整跑完一次，之后不再重复。"""
        rp = self.rp
        (self.legacy_data / "session.json").unlink()
        with mock.patch.object(rp, "_migrate_legacy_data", wraps=rp._migrate_legacy_data) as migrate:
            rp.ensure_data_dir()
            rp.ensure_data_dir()
        self.assertEqual(migrate.call_count, 1)
        self.assertIsNone(rp.migration_record(), "没搬任何文件就没有迁移记录")

    def test_lock_timeout_leaves_no_conclusion_and_is_retried(self):
        """G3：等锁超时（另一个实例在迁移）不写迁移记录，也不置位，下次拿到锁照常迁移。"""
        rp = self.rp
        holder = open(str(rp.MIGRATION_LOCK_FILE), "a+b")
        rp.acquire_file_lock(holder, 1.0)
        try:
            with mock.patch.object(rp, "MIGRATION_LOCK_TIMEOUT_S", 0.2), \
                    mock.patch.object(sys, "stderr", new=io.StringIO()):
                rp.ensure_data_dir()
            self.assertIsNone(rp.migration_record(),
                              "超时只说明对方在搬，本次没有结论；不能让界面报「旧登录信息没搬过来」")
            self.assertFalse((self.target / "session.json").exists(), "对方迁移中，不得并行复制")
        finally:
            rp.release_file_lock(holder)
            holder.close()
        # 锁释放后下一次 ensure_data_dir 必须真的再迁移一次（超时不置位）
        rp.ensure_data_dir()
        self.assertTrue((self.target / "session.json").is_file())
        self.assertEqual(rp.migration_record()["moved"], 1)
        self.assertFalse(rp.migration_record()["login_failed"])


class SpawnFailureClassificationTests(unittest.TestCase):
    """G2：SpawnFailure 是「worker 根本没启动」，取消报名/检查/拉列表都按进程没起来处理。"""

    def setUp(self):
        self.app = _app()
        for patch in (mock.patch.object(self.app, "DEMO", False),
                      mock.patch.object(self.app, "worker_problem", lambda: ""),
                      mock.patch.object(self.app, "worker_command", lambda *a: ["W"] + list(a))):
            patch.start()
            self.addCleanup(patch.stop)
        self.api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        self.events = []
        self.api._emit = lambda kind, payload=None: self.events.append((kind, payload))
        self.failure = self.app._SpawnFailure("worker 没能加入进程树（Job 创建或归属失败）")

    def test_spawn_failure_is_an_oserror_with_a_component_code(self):
        """类型关系：SpawnFailure 要被各调用点的 except OSError 接住，并拿到已有组件码。"""
        self.assertIsInstance(self.failure, OSError)
        self.assertEqual(self.app._component_error(self.failure), "spawn_failed")

    def test_cancel_with_spawn_failure_is_a_precheck_failure_not_unknown(self):
        """取消报名遇到 SpawnFailure：说前置失败，不能说「结果未知，可能已经发出」。"""
        self.api._activities = {"a1": {"id": "a1", "name": "活动", "signed": True}}
        with mock.patch.object(self.app, "spawn_owned", mock.Mock(side_effect=self.failure)):
            got = self.api._cancel_signup_run("a1")
        self.assertEqual(got, {"ok": False, "kind": "precheck_failed",
                               "reason": "worker_unavailable"})
        logs = [payload for kind, payload in self.events if kind == "log"]
        self.assertTrue(any("spawn_failed" in str(text) for text in logs), "组件诊断写进运行记录")

    def test_check_with_spawn_failure_carries_the_component_code(self):
        with mock.patch.object(self.app, "spawn_owned", mock.Mock(side_effect=self.failure)):
            self.api._do_check()
        checks = [payload for kind, payload in self.events if kind == "check"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["result"], "unknown")
        self.assertEqual(checks[0]["runtime_error"], "spawn_failed")

    def test_list_with_spawn_failure_carries_the_component_code(self):
        with mock.patch.object(self.app, "spawn_owned", mock.Mock(side_effect=self.failure)):
            self.api._do_list()
        acts = [payload for kind, payload in self.events if kind == "activities"]
        self.assertEqual(len(acts), 1)
        self.assertFalse(acts[0]["ok"])
        self.assertEqual(acts[0]["runtime_error"], "spawn_failed")


if __name__ == "__main__":
    unittest.main()
