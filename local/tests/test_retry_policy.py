#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""合并测试模块：test_retry_policy.py（来源：test_retry_events.py, test_retry_policy.py, test_retry_phone_policy.py, test_retry_phone_integration.py）。

@author Author
"""
from __future__ import annotations

# ==================== 源自 test_retry_events.py ====================
"""报名进程进度事件 → 任务快照字段（决策 015）：路径、等自动登录。"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.retry_rules import parse_retry_line, progress_event_status  # noqa: E402


def _phone_test_actions(api):
    from domain.phone_rules import ACTION_PARAMS
    actions = {name: (lambda _name=name, **kw: getattr(api, _name)(**kw))
               for name in ACTION_PARAMS if hasattr(api, name)}
    if hasattr(api, "save_prefs"):
        actions["save_retry_policy"] = lambda retry_policy=None: api.save_prefs(
            {"retry_policy": retry_policy or {}})
    return actions


class ProgressEventStatusTests(unittest.TestCase):
    def test_path_event_keeps_reason_with_spaces(self):
        # worker 把原因里的空格换成不换行空格，整行才不会被按空格切碎
        reason = "取不到运行时密钥（返回里没有可用密钥（code=1 x））".replace(" ", " ")
        parsed = parse_retry_line("[retry] kind=path path=click path_reason=" + reason)
        self.assertEqual(progress_event_status(parsed),
                         {"path": "click",
                          "path_reason": "取不到运行时密钥（返回里没有可用密钥（code=1 x））"})

    def test_login_wait_and_resume(self):
        wait = progress_event_status(parse_retry_line("[retry] kind=login_wait wait_s=45"), 1000.0)
        self.assertEqual(wait, {"login_wait": "waiting", "login_wait_until": 1045})
        no_clock = progress_event_status(parse_retry_line("[retry] kind=login_wait wait_s=45"), None)
        self.assertEqual(no_clock["login_wait_until"], "")
        done = progress_event_status(parse_retry_line("[retry] kind=login_resumed"), 1000.0)
        self.assertEqual(done, {"login_wait": "", "login_wait_until": ""})

    def test_other_events_add_nothing(self):
        for line in ("[retry] kind=submit attempts=1 request_id=req-1 phase=full_speed",
                     "[retry] kind=window retry_deadline=1 sign_end=0"):
            self.assertEqual(progress_event_status(parse_retry_line(line), 1.0), {})
        self.assertEqual(progress_event_status(None, 1.0), {})

# ==================== 源自 test_retry_policy.py ====================
"""重试策略契约测试：窗口计算、次数上限、结构化解析与 fake worker 全链路。

时间用例对应 <tmp>/campus-retry-policy-20261024/timeline-cases.json；
fake worker 场景不连学校站点，只验证 worker 输出 → task 事件的载荷链路。

@author Author
"""

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

LOCAL = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
# grab.py / signup_plan.py 内部是裸导入（from runtime_paths import ...）：
# 先把 local/ 加进 sys.path，按包路径导入时裸导入才不会断
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from time_contract import configure_time_source  # noqa: E402
configure_time_source(time.time)   # 旧用例显式注入本机时钟；新用例改注 FakeBusinessClock

from grab import attempts_allowed, compute_retry_window, retry_anchor
from signup_plan import TaskSpec
from fixtures.business_clock import TestWallClock  # noqa: E402
from fixtures.api_threads import stop_auto_relogin_on_cleanup  # noqa: E402

NOW = 1000.0
# 学校时间是北京时间：造 at/sign_end 必须用同一时区，否则换时区就错位
BEIJING_TZ = timezone(timedelta(hours=8))


def activity(aid, sign, start, end, sign_end=""):
    return {"id": aid, "name": aid, "sign_start": sign, "sign_end": sign_end,
            "act_start": start, "act_end": end, "signed": False}


# ---- 条款同意夹具（计划 repair-terms-test-fixtures）----
# start_plan、login、check、list 都先过 app._terms_gate，而门禁只读 app.PREFS：
# 不把偏好钉到临时文件，这些用例就会去读开发者真实的 ui.json，门禁结论随机器上
# 是否点过同意而漂移。同意状态只写在本轮临时 ui.json 的 terms_version /
# terms_accepted_at 两个键上，模块跑完即删；未同意状态、旧版本拒绝与 demo 豁免
# 的专测在 test_terms_consent.py 里照旧构造，不受这里影响。
_PREFS_PATCHER = None
_PREFS_TMP = None


def setUpModule():
    """把本模块的偏好文件钉到临时 ui.json，并写入当前版本的条款同意。"""
    global _PREFS_PATCHER, _PREFS_TMP
    sys.path.insert(0, str(LOCAL))
    try:
        import app as local_app
    except Exception:
        # 导入失败时由各用例自己 skipTest，保持原有跳过行为，不替它们下结论
        return
    finally:
        sys.path.pop(0)
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


class RetryWindowTests(unittest.TestCase):
    """compute_retry_window：三种起算点与 sign_end 硬上限。"""

    def test_timeline_cases_table_driven(self):
        """用例与 timeline-cases.json 一一对应：未来/已开放/直到截止/缺截止回退/截止截断。"""
        cases = [
            # (at_ts, sign_end_ts, retry_for_s, 期望 start/deadline/binding)
            (4600.0, 8200.0, 600, (4600.0, 5200.0, "duration")),      # 未来活动从 sign_start 起算
            (900.0, 8200.0, 600, (NOW, NOW + 600, "duration")),        # 已开放从启动起算
            (900.0, 8200.0, 0, (NOW, 8200.0, "sign_end")),             # 直到报名截止
            (900.0, None, 0, (NOW, NOW + 120, "fallback")),            # 缺 sign_end 回退 120 秒
            (1100.0, 1300.0, 3600, (1100.0, 1300.0, "sign_end")),      # 截止更早：sign_end 截断
            (1100.0, 9999.0, 3600, (1100.0, 4700.0, "duration")),      # 时长更早：duration
        ]
        for at, sign_end, retry_for, want in cases:
            with self.subTest(at=at, sign_end=sign_end, retry_for=retry_for):
                start, deadline, binding = compute_retry_window(at, sign_end, retry_for, now=NOW)
                self.assertEqual((start, deadline, binding), want)

    def test_deadline_never_passes_sign_end(self):
        """任何策略下有效截止都不得晚于 sign_end。"""
        for retry_for in (0, 1, 600, 86400, 10 ** 6):
            _, deadline, _ = compute_retry_window(4600.0, 5000.0, retry_for, now=NOW)
            self.assertLessEqual(deadline, 5000.0,
                                 "retry_for=%r 时截止越过了 sign_end" % retry_for)

    def test_fallback_never_runs_forever(self):
        """「直到截止」但缺 sign_end：必须回退到有限窗口。"""
        _, deadline, binding = compute_retry_window(900.0, None, 0, now=NOW)
        self.assertEqual(binding, "fallback")
        self.assertLessEqual(deadline, NOW + 120.001)


class AttemptsCountingTests(unittest.TestCase):
    """attempts_allowed：0 表示不限；否则等于上限时不得再点。"""

    def test_max_attempts_semantics(self):
        self.assertTrue(attempts_allowed(0, 0))
        self.assertTrue(attempts_allowed(99, 0), "0=不限")
        self.assertTrue(attempts_allowed(2, 3))
        self.assertFalse(attempts_allowed(3, 3), "第 4 次点击前必须拦下")
        self.assertFalse(attempts_allowed(9, 3))


class RetryLineParsingTests(unittest.TestCase):
    """[retry] 结构化行与 telemetry 载荷。"""

    def _app(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        return local_app

    def test_parse_retry_line_keeps_reason_with_spaces(self):
        app = self._app()
        parsed = app._parse_retry_line(
            "[retry] attempts=3 stop_reason=max_attempts retry_deadline=1792900000 "
            "sign_end=1792810000 last_reason=code:0 报名人数已满")
        self.assertEqual(parsed["attempts"], "3")
        self.assertEqual(parsed["stop_reason"], "max_attempts")
        self.assertEqual(parsed["retry_deadline"], "1792900000")
        self.assertEqual(parsed["last_reason"], "code:0 报名人数已满")

    def test_parse_done_line_real_shape_tail_fields_independent(self):
        """真实形状：done 行 last_reason 在行末，尾字段各自独立成键。

        发射端（grab.py）与解析端（retry_rules.py）的契约：last_reason 恒为
        最后一个字段、可含空格；pending / streak_404 / phase 不得粘进原话。
        发射端回退（last_reason 挪回行中）必须让本用例变红。
        """
        app = self._app()
        parsed = app._parse_retry_line(
            "[retry] kind=done attempts=3 stop_reason=max_attempts "
            "retry_deadline=1792900000 sign_end=1792810000 "
            "pending=2 streak_404=3 phase=full_speed "
            "last_reason=code:0 报名人数已满")
        self.assertEqual(parsed["last_reason"], "code:0 报名人数已满")
        self.assertEqual(parsed["pending"], "2")
        self.assertEqual(parsed["streak_404"], "3")
        self.assertEqual(parsed["phase"], "full_speed")
        # 发射端契约守护：signup_outcome.py 的 done 行格式串必须以 last_reason 收尾
        source = (LOCAL / "application" / "signup_outcome.py").read_text(encoding="utf-8")
        match = re.search(r'log\("\[retry\] kind=done[^"]*"(?:\s*\n\s*"[^"]*")*', source)
        self.assertIsNotNone(match, "done 行格式串找不到：发射端形状变了，先对齐本契约")
        format_text = "".join(re.findall(r'"([^"]*)"', match.group(0)))
        self.assertTrue(format_text.endswith("last_reason=%s"),
                        "done 行 last_reason 必须在行末，否则尾字段会粘进原话")

    def test_parse_retry_line_rejects_plain_lines(self):
        app = self._app()
        self.assertIsNone(app._parse_retry_line("[i] 第 3 次提交：code:0 名额已满"))
        self.assertIsNone(app._parse_retry_line(""))

    def test_retry_payload_defaults_and_blank_epochs(self):
        app = self._app()
        spec = TaskSpec("t", "a", "a", "2026-10-25 10:00:00", "2026-10-25 12:00:00",
                        "2026-10-25 13:00:00", sign_end="2026-10-26 10:00:00")
        payload = app._retry_payload({}, spec, stop_reason="process_error")
        self.assertEqual(payload["stop_reason"], "process_error")
        self.assertEqual(payload["attempts"], 0)
        self.assertEqual(payload["retry_deadline"], "")
        self.assertEqual(payload["sign_end"], "2026-10-26 10:00:00", "结构化行缺失时用活动自身 sign_end")
        payload2 = app._retry_payload(
            {"attempts": "5", "stop_reason": "sign_end", "retry_deadline": "0",
             "sign_end": "1792810000", "last_reason": "x"}, spec, stop_reason="fallback")
        self.assertEqual(payload2["attempts"], 5)
        self.assertEqual(payload2["retry_deadline"], "", "epoch=0 表示没有，落空串")
        self.assertEqual(payload2["sign_end"], "1792810000")


class WorkerTelemetryFlowTests(unittest.TestCase):
    """fake worker：[i] 第 N 次提交 / [retry] 行 → task 事件与终态载荷。"""

    def _api(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        self._app_module = local_app
        return stop_auto_relogin_on_cleanup(self, local_app.Api(clock=TestWallClock()))

    def _run_worker(self, api, source, policy=None, sign_end=""):
        """启动单任务计划等到 plan_done，返回 (事件, plan_id, task_id, worker 参数)。"""
        import tempfile
        from unittest import mock

        local_app = self._app_module
        fake = Path(tempfile.mkdtemp()).resolve() / "fake_worker.py"
        fake.write_text(source, encoding="utf-8")
        captured = {}
        events = []
        api._emit = lambda kind, payload: events.append((kind, payload))
        # 本类只验证重试策略链路：先给一个 valid 的登录结论，越过登录门禁
        api._last_check = {"result": "valid", "checked_at": 0.0}

        original = local_app.worker_command

        def capture(*args):
            # 模拟真实 worker_command：返回 base+args 的新列表；
            # _run_plan_task 随后的 += 会落在这张表上，captured 因此能看到完整命令
            cmd = [sys.executable, str(fake)] + list(args)
            captured["args"] = cmd
            return cmd

        at = (datetime.now(BEIJING_TZ).replace(tzinfo=None) - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
        row = activity("a", at, "2026-10-23 12:00:00", "2026-10-23 13:00:00", sign_end=sign_end)
        # 计划接纳以本进程缓存为权威（R05）：本类验证遥测链路，先把同源快照
        # 登记进缓存再开始；接纳门禁本身由 test_signup_plan 的专门用例覆盖
        api._activities = {str(row["id"]): dict(row)}
        patcher = mock.patch.object(local_app, "worker_command", capture)
        with patcher:
            res = api.start_plan([row], False, policy)
            self.assertTrue(res["ok"], res)
            budget = time.time() + 10
            while time.time() < budget and not any(k == "plan_done" for k, _ in events):
                time.sleep(0.05)
        return events, res["plan_id"], captured.get("args")

    def test_max_attempts_full_is_retryable_then_stops(self):
        """人数已满可重试：第 N 次提交行推 telemetry，次数到达给 max_attempts 终态。"""
        api = self._api()
        source = (
            "import sys, time\n"
            "time.sleep(0.1)\n"
            "print('[i] 第 1 次提交：code:0 报名人数已满', flush=True)\n"
            "print('[i] 第 2 次提交：code:0 报名人数已满', flush=True)\n"
            "print('[i] 第 3 次提交：code:0 报名人数已满', flush=True)\n"
            "print('[X] 已提交 3 次仍没成功：code:0 报名人数已满', flush=True)\n"
            "print('[retry] attempts=3 stop_reason=max_attempts retry_deadline=1792900000 "
            "sign_end=1792810000 last_reason=code:0 报名人数已满', flush=True)\n"
            "sys.exit(2)\n"
        )
        sign_end = (datetime.now(BEIJING_TZ).replace(tzinfo=None) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        events, plan_id, worker_args = self._run_worker(
            api, source, policy={"retry_for_s": 600, "max_attempts": 3}, sign_end=sign_end)

        task_events = [p for kind, p in events if kind == "task"]
        submitting = [p for p in task_events
                      if p.get("status") == "submitting" and "attempts" in p]
        # task 事件是自包含快照（重试截止到达等后续推送也会重报当前次数）；
        # 计数契约看「值只在真正 signUp 的行上递增」，不看事件条数
        pushes = [p["attempts"] for p in submitting]
        increments = [b for a, b in zip([0] + pushes, pushes) if b != a]
        self.assertEqual(increments, [1, 2, 3],
                         "attempts 只在真正 signUp 的行上递增（刷新/查询/截止推送不计）")
        self.assertEqual(pushes[-1], 3)
        self.assertTrue(all("报名人数已满" in p["last_reason"] for p in submitting))
        final = task_events[-1]
        self.assertEqual(final["status"], "failed")
        self.assertEqual(final["code"], 2)
        self.assertEqual(final["stop_reason"], "max_attempts")
        self.assertEqual(final["attempts"], 3)
        self.assertEqual(final["retry_deadline"], "1792900000")
        done = [p for kind, p in events if kind == "plan_done"][-1]
        self.assertEqual(done["status"], "failed")
        # worker 参数链路：策略与截止必须传到命令行
        self.assertIn("--retry-for", worker_args)
        self.assertEqual(worker_args[worker_args.index("--retry-for") + 1], "600")
        self.assertEqual(worker_args[worker_args.index("--max-attempts") + 1], "3")
        self.assertEqual(worker_args[worker_args.index("--sign-end") + 1], sign_end)

    def test_success_and_login_invalid_terminal_payloads(self):
        """成功带 attempts；登录失效（退出码 3）带 login_invalid 终态。"""
        api = self._api()
        ok_source = (
            "import sys, time\n"
            "time.sleep(0.1)\n"
            "print('[i] 第 2 次提交：code:1 成功', flush=True)\n"
            "print('[OK] 报名成功（尝试 2 次）', flush=True)\n"
            "print('[retry] attempts=2 stop_reason=success retry_deadline=1792900000 sign_end=0 last_reason=', flush=True)\n"
            "sys.exit(0)\n"
        )
        events, _, _ = self._run_worker(api, ok_source)
        final = [p for kind, p in events if kind == "task"][-1]
        self.assertEqual(final["status"], "success")
        self.assertEqual(final["stop_reason"], "success")
        self.assertEqual(final["attempts"], 2)

        login_source = (
            "import sys, time\n"
            "time.sleep(0.1)\n"
            "print('[X] 登录失效：学校要求重新登录', flush=True)\n"
            "print('[retry] attempts=1 stop_reason=login_invalid retry_deadline=1792900000 sign_end=0 last_reason=code:4001 登录失效', flush=True)\n"
            "sys.exit(3)\n"
        )
        events2, _, _ = self._run_worker(api, login_source)
        final2 = [p for kind, p in events2 if kind == "task"][-1]
        self.assertEqual(final2["status"], "failed")
        self.assertEqual(final2["code"], 3)
        self.assertEqual(final2["stop_reason"], "login_invalid")

    def test_invalid_policy_falls_back_to_defaults(self):
        """脏策略值回落默认 120 秒 / 不限，不得把 worker 挂成异常形态。"""
        api = self._api()
        source = ("import sys, time\n"
                  "time.sleep(0.1)\n"
                  "print('[X] 没抢到：名额已满', flush=True)\n"
                  "print('[retry] attempts=1 stop_reason=retry_duration retry_deadline=1792900000 sign_end=0 last_reason=名额已满', flush=True)\n"
                  "sys.exit(2)\n")
        events, _, worker_args = self._run_worker(
            api, source, policy={"retry_for_s": -5, "max_attempts": "abc"})
        self.assertEqual(worker_args[worker_args.index("--retry-for") + 1], "120")
        self.assertEqual(worker_args[worker_args.index("--max-attempts") + 1], "0")
        self.assertNotIn("--sign-end", worker_args, "活动没有 sign_end 就不传")

    def test_checkpoint_uses_source_time_not_receipt(self):
        """R10：节点时间来自子进程记录的发生时刻，父层转发慢 2 秒也不漂。"""
        api = self._api()
        source = (
            "import json, sys, time\n"
            "at = 1792000000.0\n"
            "print('[checkpoint] ' + json.dumps({'kind': 'worker_started', 'at': at}), flush=True)\n"
            "time.sleep(1.2)\n"
            "print('[checkpoint] ' + json.dumps({'kind': 'page_opened', 'at': at + 0.5}), flush=True)\n"
            "time.sleep(0.3)\n"
            "print('[i] 详情页已加载', flush=True)\n"
            "print('[retry] kind=done attempts=0 stop_reason=retry_duration "
            "retry_deadline=0 sign_end=0 last_reason=', flush=True)\n"
            "print('[X] 没抢到：名额已满', flush=True)\n"
            "sys.exit(2)\n"
        )
        events, _, _ = self._run_worker(api, source)
        task_events = [p for kind, p in events if kind == "task"]
        opened = [p["page_opened_at"] for p in task_events if "page_opened_at" in p]
        self.assertTrue(opened, "结构化 checkpoint 必须变成任务节点")
        self.assertEqual(opened[0], 1792000000.5,
                         "节点时间必须是源事件时间，不是读到日志的接收时刻")
        self.assertEqual(task_events[-1].get("run_started_at"), 1792000000.0)

    def test_progress_retry_line_does_not_fake_terminal(self):
        """进度 [retry] 行（无 stop_reason）不得被当成终态。"""
        api = self._api()
        source = (
            "import sys, time\n"
            "print('[retry] kind=window retry_deadline=1792900300 sign_end=1792900000', flush=True)\n"
            "print('[i] 第 1 次提交：已发起', flush=True)\n"
            "time.sleep(0.1)\n"
            "print('[X] 没抢到：名额已满', flush=True)\n"
            "print('[retry] kind=done attempts=1 stop_reason=retry_duration "
            "retry_deadline=1792900300 sign_end=1792900000 last_reason=名额已满', flush=True)\n"
            "sys.exit(2)\n"
        )
        events, _, _ = self._run_worker(api, source)
        task_events = [p for kind, p in events if kind == "task"]
        final = task_events[-1]
        self.assertEqual(final["stop_reason"], "retry_duration")
        self.assertEqual(final["attempts"], 1)
        # 进度行在启动阶段就把截止推上去了，不必等终态
        early = [p for p in task_events
                 if p.get("status") == "submitting" and p.get("retry_deadline") == "1792900300"]
        self.assertTrue(early, "窗口确定的进度行必须让截止尽早上屏")

    def test_phase_forwarded_from_progress_and_done_lines(self):
        """进度行 phase 实时上屏，终态行 phase 独立成键后原样进终态载荷。

        done 行按 grab.py 新形状构造（last_reason 在行末）；转发链
        plan_service 进度 → retry_payload 终态任一处丢 phase 都会让本用例红。
        """
        api = self._api()
        source = (
            "import sys, time\n"
            "print('[retry] kind=window retry_deadline=1792900300', flush=True)\n"
            "print('[retry] kind=submit attempts=1 request_id=r1 phase=golden', flush=True)\n"
            "time.sleep(0.1)\n"
            "print('[X] 没抢到：名额已满', flush=True)\n"
            "print('[retry] kind=done attempts=1 stop_reason=retry_duration "
            "retry_deadline=1792900300 sign_end=1792900000 "
            "pending=0 streak_404=0 phase=full_speed last_reason=名额已满', flush=True)\n"
            "sys.exit(2)\n"
        )
        events, _, _ = self._run_worker(api, source)
        task_events = [p for kind, p in events if kind == "task"]
        progress = [p for p in task_events if p.get("phase")]
        self.assertEqual(progress[0]["phase"], "golden", "进度行 phase 必须实时转发")
        final = task_events[-1]
        self.assertEqual(final["phase"], "full_speed", "终态行 phase 必须进终态载荷")
        self.assertEqual(final["last_reason"], "名额已满", "last_reason 不得粘尾字段")

    def test_plan_snapshot_carries_policy(self):
        """计划快照保留策略：页面重载后策略不丢。"""
        api = self._api()
        sign_end = (datetime.now(BEIJING_TZ).replace(tzinfo=None) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        source = ("import time\n"
                  "print('[i] worker started', flush=True)\n"
                  "time.sleep(300)\n")
        threading.Timer(0.3, lambda: api.stop_plan(api._plan.plan_id)).start()
        events, plan_id, _ = self._run_worker(
            api, source, policy={"retry_for_s": 1800, "max_attempts": 5}, sign_end=sign_end)
        snapshots = [p for kind, p in events if kind == "plan"]
        task = snapshots[0]["tasks"][0]
        self.assertEqual(task["retry_for_s"], 1800)
        self.assertEqual(task["max_attempts"], 5)
        self.assertEqual(task["sign_end"], sign_end)


class InstantModeRetryWindowTests(unittest.TestCase):
    """已开放场次（立即报名/抢名额）的重试窗口：从本次启动计时，sign_end 硬截断。

    时间全部注入 now，不依赖真实时钟；三种策略（2 分钟/1 小时/直到截止）
    与路线、任务卡、LED 共用同一套 deadline 口径。
    """

    NOW = 1792000000.0

    def test_open_activity_starts_from_launch_not_history(self):
        """已开放场次从本次启动（now）起算：历史 sign_start 不再充当重试起点。"""
        at_ts = self.NOW - 3 * 86400      # 三天前开放的场次
        sign_end_ts = self.NOW + 86400
        retry_start, deadline, binding = compute_retry_window(
            at_ts, sign_end_ts, 3600, now=self.NOW)
        self.assertEqual(retry_start, self.NOW, "重试起点必须是本次启动时刻")
        self.assertEqual(deadline, self.NOW + 3600)
        self.assertEqual(binding, "duration")

    def test_long_policy_truncated_by_sign_end(self):
        """1 小时策略撞上更早的报名截止：deadline=sign_end，binding=sign_end。"""
        at_ts = self.NOW - 600
        sign_end_ts = self.NOW + 1200
        retry_start, deadline, binding = compute_retry_window(
            at_ts, sign_end_ts, 3600, now=self.NOW)
        self.assertEqual(retry_start, self.NOW)
        self.assertEqual(deadline, sign_end_ts)
        self.assertEqual(binding, "sign_end")

    def test_until_sign_end_policy_uses_sign_end(self):
        """直到截止（0）：deadline=sign_end；缺 sign_end 回退 120 秒，绝不无限运行。"""
        at_ts = self.NOW - 600
        sign_end_ts = self.NOW + 5400
        _, deadline, binding = compute_retry_window(at_ts, sign_end_ts, 0, now=self.NOW)
        self.assertEqual((deadline, binding), (sign_end_ts, "sign_end"))
        _, fallback_deadline, fallback_binding = compute_retry_window(
            at_ts, None, 0, now=self.NOW)
        self.assertEqual((fallback_deadline, fallback_binding),
                         (self.NOW + 120, "fallback"))

    def test_future_activity_still_waits_for_sign_start(self):
        """预报名场次保持原口径：从 sign_start 起算，已开放口径不得外溢。"""
        future_at = self.NOW + 1800
        sign_end_ts = self.NOW + 86400
        retry_start, deadline, binding = compute_retry_window(
            future_at, sign_end_ts, 600, now=self.NOW)
        self.assertEqual(retry_start, future_at)
        self.assertEqual(deadline, future_at + 600)
        self.assertEqual(binding, "duration")


class RetryAnchorTests(unittest.TestCase):
    """重试起算点锚定（retry_anchor）：页面加载延迟不得后移 deadline。

    时间全部注入，不依赖真实时钟；对照旧行为（加载完成后才取 now）证明修复。
    """

    NOW = 1792000000.0

    def test_open_activity_deadline_pinned_to_launch(self):
        """已开放场次：anchor=worker 启动时刻；慢 20 秒的页面不改 deadline。"""
        past_at = self.NOW - 600
        sign_end_ts = self.NOW + 86400
        anchor = retry_anchor(past_at, now=self.NOW)
        self.assertEqual(anchor, self.NOW, "已开放场次的起算点固定为 worker 启动时刻")
        # 旧口径（页面加载完成后才取 now）：deadline 被慢页面整体后移 20 秒
        _, late_deadline, _ = compute_retry_window(past_at, sign_end_ts, 600, now=self.NOW + 20)
        self.assertEqual(late_deadline, self.NOW + 620)
        # 新口径（anchor 在 page.goto 前固定）：deadline 钉在启动时刻
        _, deadline, binding = compute_retry_window(anchor, sign_end_ts, 600, now=anchor)
        self.assertEqual((deadline, binding), (self.NOW + 600, "duration"))

    def test_future_activity_anchor_is_sign_start(self):
        """未来场次：anchor 归一到原定 sign_start，deadline 从开放起算。"""
        future_at = self.NOW + 1800
        sign_end_ts = self.NOW + 86400
        anchor = retry_anchor(future_at, now=self.NOW)
        self.assertEqual(anchor, future_at, "未来场次的起算点仍是原定开放时刻")
        _, deadline, binding = compute_retry_window(anchor, sign_end_ts, 600, now=anchor)
        self.assertEqual((deadline, binding), (future_at + 600, "duration"))

    def test_sign_end_truncation_and_fallback_unchanged(self):
        """anchor 口径下 sign_end 截断与缺截止回退 120 秒保持不变。"""
        anchor = self.NOW
        sign_end_ts = self.NOW + 1200
        _, deadline, binding = compute_retry_window(anchor, sign_end_ts, 3600, now=anchor)
        self.assertEqual((deadline, binding), (sign_end_ts, "sign_end"))
        _, fallback_deadline, fallback_binding = compute_retry_window(anchor, None, 0, now=anchor)
        self.assertEqual((fallback_deadline, fallback_binding),
                         (self.NOW + 120, "fallback"))


WORKER_FIXTURE = r'''
import os
import subprocess
import sys
import time

scenario = sys.argv[1] if len(sys.argv) > 1 else "silent"
pid_file = os.environ.get("CAMPUS_LIFECYCLE_PIDS", "")

if scenario == "silent":
    time.sleep(60)
elif scenario == "slow_output":
    for i in range(2000):
        print("[i] tick %d" % i, flush=True)
        time.sleep(0.02)
elif scenario == "parent_exit":
    # 孙进程继承 stdout：父进程立刻退出，管道仍被握着，EOF 永远不会来
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    if pid_file:
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(child.pid))
    print("[i] parent exiting, grandchild holds stdout", flush=True)
    sys.exit(0)
elif scenario == "structured_only":
    # 只有结构化提交行、没有人话行：次数不能因此归零
    print("[retry] kind=submit attempts=3", flush=True)
    time.sleep(60)
elif scenario == "job_marker":
    # 主体第一条指令就问「我现在属于某个 Job 吗」：
    # 若归属发生在进程已经跑起来之后，这里只会看到 0。
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.IsProcessInJob.restype = ctypes.c_int
    k.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                 ctypes.POINTER(ctypes.c_int)]
    inside = ctypes.c_int(0)
    ok = k.IsProcessInJob(ctypes.c_void_p(-1), None, ctypes.byref(inside))
    marker = os.environ.get("CAMPUS_LIFECYCLE_MARK", "")
    if marker:
        with open(marker, "w", encoding="utf-8") as f:
            # 第三个字段是主体第一条指令的时刻，用来和父层「归属成功」的时刻比先后
            f.write("%d %d %.6f" % (1 if ok else 0, inside.value, time.time()))
    time.sleep(60)
elif scenario == "submitted_then_wait":
    # 已发起 3 次提交、没有终态：随后被用户停止
    print("[i] 第 3 次提交：已发起", flush=True)
    print("[retry] kind=submit attempts=3", flush=True)
    time.sleep(60)
elif scenario == "success_then_wait":
    # 成功终态已到，但进程还没退出：此时停止不得把成功改写成取消
    print("[i] 第 1 次提交：code:1 成功", flush=True)
    print("[OK] 报名成功（尝试 1 次）", flush=True)
    print("[retry] kind=done attempts=1 stop_reason=success retry_deadline=0 "
          "sign_end=0 last_reason=", flush=True)
    time.sleep(60)
elif scenario == "already_then_wait":
    print("[i] 你已经报过这个活动", flush=True)
    print("[retry] kind=done attempts=0 stop_reason=already_signed "
          "retry_deadline=0 sign_end=0 last_reason=", flush=True)
    time.sleep(60)
elif scenario == "definite_fail_then_wait":
    # 学校明确失败：停止晚到时按这个确定结论记，不降级成「待核对」
    print("[i] 第 2 次提交：报名人数已满", flush=True)
    print("[retry] kind=done attempts=2 stop_reason=max_attempts "
          "retry_deadline=0 sign_end=0 last_reason=报名人数已满", flush=True)
    time.sleep(60)
elif scenario == "terminal":
    print("[i] 第 2 次提交：code:1 成功", flush=True)
    print("[OK] 报名成功（尝试 2 次）", flush=True)
    print("[retry] kind=done attempts=2 stop_reason=success retry_deadline=0 "
          "sign_end=0 last_reason=", flush=True)
    sys.exit(0)
else:
    raise SystemExit("unknown scenario: %s" % scenario)
'''


def _pid_alive(pid: int) -> bool:
    """进程是否还活着；Windows 用 tasklist 避免 os.kill 的终止语义。"""
    if os.name == "nt":
        # tasklist 输出是控制台代码页（GBK），不能让 reader 线程按 UTF-8 解码
        done = subprocess.run(["tasklist", "/FI", "PID eq %d" % int(pid), "/NH"],
                              capture_output=True, timeout=5)
        out = (done.stdout or b"").decode("mbcs", "replace")
        return str(int(pid)) in out
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


class _WorkerCase(unittest.TestCase):
    """真实临时 worker 的公共装置（脚本生成在临时根，零真实 worker/浏览器）。

    短测试把 SUPERVISE_GRACE_S 换成 0.4 秒并在 cleanup 恢复；子类只写用例。
    """

    GRACE = 0.4

    def setUp(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        self.app = local_app
        self.root = Path(tempfile.mkdtemp(prefix="campus-lifecycle-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.root), True)
        self._old_grace = local_app.SUPERVISE_GRACE_S
        local_app.SUPERVISE_GRACE_S = self.GRACE
        self.addCleanup(setattr, local_app, "SUPERVISE_GRACE_S", self._old_grace)
        self.script = self.root / "worker_fixture.py"
        self.script.write_text(WORKER_FIXTURE, encoding="utf-8")

    def _spec(self, retry_for: int, *, deadline_past: bool = True):
        # retry_for_s 是整数字段。默认把起点再往前推 0.5 秒，让有效截止略早于现在，
        # 监督延迟就固定为 GRACE，不依赖用例执行速度；取消类用例要一个「远未到点」
        # 的窗口，否则监督会先于取消收尾，测到的就不是取消语义了。
        offset = (retry_for + 0.5) if deadline_past else 1.0
        return TaskSpec(task_id="t1", activity_id="a1", name="生命周期实验",
                        sign_start="2026-10-26 09:00:00", act_start="", act_end="",
                        sign_end="", retry_for_s=retry_for, max_attempts=0,
                        signup_mode="instant_signup", lead_s=0,
                        retry_started_at=time.time() - offset)

    def _run_task(self, scenario: str, *, retry_for: int = 5,
                  cancel_after: float | None = None, cancel_on_attempts: int | None = None,
                  cancel_on_log: str | None = None,
                  expect_spawn_failure: bool = False, deadline_past: bool = True):
        """跑一场 fake worker，返回 (api, result, events, elapsed, pid_file, mark_file, seen)。

        cancel_after 是墙钟延时：机器慢时它可能早于终态行到达，测到的就不是「晚到」；
        需要「父进程已读到终态行之后再停止」的用例改用 cancel_on_log。
        """
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        cancel = threading.Event()

        def emit(kind, payload):
            events.append((kind, payload))
            # feed 对每一行输出都会 emit("log", ...)：此刻父进程已读到并记下该行
            if cancel_on_log and kind == "log" and cancel_on_log in str(payload):
                cancel.set()

        api._emit = emit
        pid_file = self.root / ("pid-%d.txt" % time.monotonic_ns())
        mark_file = self.root / ("mark-%d.txt" % time.monotonic_ns())
        seen = {"attempts": 0, "spawned_at": []}

        def status(state, detail):
            """生产 status 回调的替身：只记录，不改行为。

            「父确认已消费该行再取消」靠它证明——收到 attempts>=N 的那次回调
            一定发生在 feed() 已经解析完该行之后。
            """
            if state != "submitting" or not isinstance(detail, dict):
                return
            if "worker_spawned_at" in detail:
                seen["spawned_at"].append(detail["worker_spawned_at"])
            if "attempts" in detail:
                seen["attempts"] = max(seen["attempts"], int(detail["attempts"]))
                if cancel_on_attempts and seen["attempts"] >= cancel_on_attempts:
                    cancel.set()

        def fake_command(*args):
            return [sys.executable, str(self.script), scenario]

        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_LIFECYCLE_PIDS"] = str(pid_file)
            env["CAMPUS_LIFECYCLE_MARK"] = str(mark_file)
            return env

        timer = None
        started = time.time()
        result = None
        error = None
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            if cancel_after is not None:
                timer = threading.Timer(cancel_after, cancel.set)
                timer.start()
            try:
                result = api._run_plan_task(
                    self._spec(retry_for, deadline_past=deadline_past), cancel, status)
            except self.app._SpawnFailure as exc:
                error = exc
            finally:
                if timer is not None:
                    timer.cancel()
        if expect_spawn_failure:
            self.assertIsNotNone(error, "归属失败必须以 _SpawnFailure 结束这一场")
        elif error is not None:
            raise error
        return api, result, events, time.time() - started, pid_file, mark_file, seen


class WorkerLifecycleTests(_WorkerCase):
    """F03：父先退出、孙持管道时，监督仍能在有界时间内结束并清干净。"""

    def test_silent_worker_is_supervised(self):
        api, result, _, elapsed, _, _, _ = self._run_task("silent", retry_for=1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stop_reason"], "retry_duration")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0,
                             "静默不退出的 worker 必须被监督收走")
        self.assertEqual(api._plan_procs, {})

    def test_slow_output_does_not_block_supervision(self):
        api, result, events, elapsed, _, _, _ = self._run_task("slow_output", retry_for=1)
        self.assertEqual(result["status"], "failed")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0)
        self.assertTrue(any("tick" in str(payload) for kind, payload in events),
                        "慢输出仍要被读线程消费，不能卡住监督")
        self.assertEqual(api._plan_procs, {})

    def test_parent_exit_with_grandchild_holding_pipe_ends_bounded(self):
        api, result, _, elapsed, pid_file, _, _ = self._run_task("parent_exit", retry_for=1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["stop_reason"], "retry_duration",
                         "父已退出且无终态、也没有提交过：按重试时长收尾")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0,
                             "孙进程持管道不得把监控拖到永久等待")
        self.assertEqual(api._plan_procs, {}, "进程表必须清空，否则 busy 永远不释放")
        self.assertTrue(pid_file.exists(), "装置应记录孙进程 PID")
        grandchild = int(pid_file.read_text(encoding="utf-8").strip())
        deadline = time.time() + 2.0
        while time.time() < deadline and _pid_alive(grandchild):
            time.sleep(0.05)
        self.assertFalse(_pid_alive(grandchild), "孙进程必须被本场所有权收走")

    def test_structured_attempts_survive_supervision(self):
        _, result, _, elapsed, _, _, _ = self._run_task("structured_only", retry_for=1)
        self.assertEqual(result["attempts"], 3,
                         "只有结构化提交行时次数也不能归零")
        self.assertEqual(result["stop_reason"], "unconfirmed",
                         "发过请求但没有终态：必须说结果待核对")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0)

    def test_normal_terminal_cancels_watchdog(self):
        api, result, _, elapsed, _, _, _ = self._run_task("terminal", retry_for=30)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["attempts"], 2)
        self.assertLess(elapsed, 3.0, "正常完成必须立刻撤销监督，不等 30 秒截止")
        self.assertEqual(api._plan_procs, {})

    def test_cancel_and_deadline_together_return_once(self):
        api, result, _, elapsed, _, _, _ = self._run_task(
            "silent", retry_for=1, cancel_after=0.5)
        self.assertIn(result["status"], {"canceled", "failed"},
                      "取消与截止同时到达只能有一个终态")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0)
        self.assertEqual(api._plan_procs, {})

    def test_plan_done_once_and_busy_released(self):
        """整计划跑一遍：监督收走后 plan_done 恰一次、busy 解除。"""
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload: events.append((kind, payload))
        api._last_check = {"result": "valid", "checked_at": 0.0}
        at = (datetime.now(BEIJING_TZ).replace(tzinfo=None) - timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S")
        sign_end = (datetime.now(BEIJING_TZ).replace(tzinfo=None) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        row = activity("a1", at, "2026-10-23 12:00:00", "2026-10-23 13:00:00",
                       sign_end=sign_end)
        api._activities = {"a1": dict(row)}

        def fake_command(*args):
            return [sys.executable, str(self.script), "parent_exit"]

        with mock.patch.object(self.app, "worker_command", fake_command):
            res = api.start_plan([row], False, {"retry_for_s": 1, "max_attempts": 0})
            self.assertTrue(res["ok"], res)
            deadline = time.time() + 1 + self.GRACE + 2.0
            while time.time() < deadline and not any(k == "plan_done" for k, _ in events):
                time.sleep(0.05)
        done = [p for kind, p in events if kind == "plan_done"]
        self.assertEqual(len(done), 1, "plan_done 必须恰一次")
        terminals = [p for kind, p in events
                     if kind == "task" and p.get("status") in
                     {"success", "already_signed", "failed", "canceled"}]
        self.assertEqual(len(terminals), 1, "本场终态必须恰一次")
        self.assertFalse(api._is_busy(), "监督收走后 busy 必须解除")
        self.assertEqual(api._plan_procs, {})
        # F5/bootstrap 要能恢复最后一个计划的结论：另存一份终态快照
        self.assertIsNone(api._plan, "当前计划仍按旧契约清空")
        self.assertIsNotNone(api._last_plan, "plan_done 后必须留下终态快照")
        self.assertIn(api._last_plan.get("status"), {"failed", "partial", "completed"})


class WorkerOwnershipTests(_WorkerCase):
    """FR02：所有权必须在 worker 主体执行之前建立，失败不得静默降级。

    全部使用真实临时子进程；Job 侧失败用「只替换 Windows API 返回值」的方式
    制造（那是外部 I/O 边界，不是被测的生产函数）。
    """

    def setUp(self):
        if os.name != "nt":
            self.skipTest("Job Object 归属只在 Windows 上成立")
        super().setUp()

    def _patch_kernel(self, **overrides):
        """只改 Windows API 的返回值，保留其余真实实现。

        kernel32 替身注入在 infrastructure.process_tree（进程树适配器的
        替换接口）：_run_plan_task 经 app 的 spawn_owned_worker 再导出走
        到该模块，这里替的就是那一层。
        """
        from infrastructure import process_tree
        real = process_tree.win_kernel32()
        saved = process_tree._KERNEL32

        class Wrap:
            def __getattr__(self, name):
                if name in overrides:
                    return overrides[name]
                return getattr(real, name)

        process_tree._KERNEL32 = Wrap()
        self.addCleanup(setattr, process_tree, "_KERNEL32", saved)

    def test_worker_body_starts_only_after_job_ownership(self):
        """归属成功的时刻必须早于 worker 主体的第一条指令。

        不能只看 IsProcessInJob：测试进程自己也可能在某个 Job 里，
        子进程会继承它，那样「是否在 Job 里」永远为真。这里比的是时刻——
        挂起创建的意义就是主体在归属成功之前一步都跑不了。
        """
        app = self.app
        real = app._win_kernel32()
        stamp = {}

        def recording_assign(job, handle):
            ok = real.AssignProcessToJobObject(job, handle)
            if ok:
                stamp["at"] = time.time()
            return ok

        self._patch_kernel(AssignProcessToJobObject=recording_assign)
        _, result, _, _, _, mark, _ = self._run_task("job_marker", retry_for=1)
        self.assertTrue(mark.exists(), "装置应写出归属探测结果")
        ok, inside, first_instruction = mark.read_text(encoding="utf-8").split()
        self.assertEqual(ok, "1", "IsProcessInJob 调用失败")
        self.assertIn("at", stamp, "装置应记录归属成功时刻")
        self.assertGreaterEqual(
            float(first_instruction), stamp["at"] - 0.02,
            "worker 主体在归属成功之前就跑了：创建与归属之间存在未受控窗口")
        self.assertEqual(inside, "1")
        self.assertEqual(result["stop_reason"], "retry_duration")

    def test_spawn_reports_ownership_failure_and_runs_no_body(self):
        """归属失败必须报错、零主体动作、零进程残留。"""
        for name, override in (
                ("创建 Job 失败", {"CreateJobObjectW": lambda *a: None}),
                ("设置 Job 失败", {"SetInformationJobObject": lambda *a: 0}),
                ("归属 Job 失败", {"AssignProcessToJobObject": lambda *a: 0}),
                ("恢复线程失败", {"ResumeThread": lambda *h: 0xFFFFFFFF}),
                ("找不到主线程", {"OpenThread": lambda *a: None}),
        ):
            with self.subTest(阶段=name):
                self._patch_kernel(**override)
                api, _result, _events, _elapsed, _pid, mark, _seen = self._run_task(
                    "job_marker", retry_for=1, expect_spawn_failure=True)
                self.assertFalse(mark.exists(),
                                 "归属失败时 worker 主体不得执行（%s）" % name)
                self.assertEqual(api._plan_procs, {}, "失败后进程表必须为空")
                self.assertFalse(api._is_busy(), "失败后不得留下忙状态")

    def test_cancel_before_spawn_completes_returns_single_terminal(self):
        """取消碰到挂起创建：仍只有一个终态、进程表清空。"""
        api, result, events, elapsed, _, _, _ = self._run_task(
            "silent", retry_for=1, cancel_after=0.0)
        self.assertIn(result["status"], {"canceled", "failed"})
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 3.0)
        self.assertEqual(api._plan_procs, {})
        self.assertEqual(result["attempts"], 0, "没有提交过就不能记次数")

    def test_deadline_already_passed_supervises_immediately(self):
        """截止已过：看门狗与主循环同一上限，只收一次、不死锁。"""
        api, result, _, elapsed, _, _, _ = self._run_task("silent", retry_for=1)
        self.assertEqual(result["stop_reason"], "retry_duration")
        self.assertLessEqual(elapsed, 0.5 + self.GRACE + 2.0)
        self.assertEqual(api._plan_procs, {})


class StopPreservesFactsTests(_WorkerCase):
    """FR03：停止只终止本地执行，不覆盖次数与已确认结果。"""

    def test_cancel_after_submissions_keeps_attempts_and_marks_unconfirmed(self):
        _, result, _, _, _, _, seen = self._run_task(
            "submitted_then_wait", retry_for=30, deadline_past=False, cancel_on_attempts=3)
        self.assertGreaterEqual(seen["attempts"], 3, "父层必须已消费该提交行")
        self.assertEqual(result["attempts"], 3, "停止不得把已提交次数清零")
        self.assertEqual(result["stop_reason"], "unconfirmed",
                         "已发出请求又没确定回应：结果待核对，不是普通取消")
        self.assertTrue(result.get("locally_stopped"))
        self.assertEqual(result["status"], "failed")

    def test_cancel_after_confirmed_success_keeps_success(self):
        _, result, _, _, _, _, _ = self._run_task(
            "success_then_wait", retry_for=30, deadline_past=False, cancel_on_log="kind=done")
        self.assertEqual(result["status"], "success",
                         "停止晚到不得把已确认成功改写为取消")
        self.assertEqual(result["attempts"], 1)

    def test_cancel_after_already_signed_keeps_already(self):
        _, result, _, _, _, _, _ = self._run_task(
            "already_then_wait", retry_for=30, deadline_past=False, cancel_on_log="kind=done")
        self.assertEqual(result["status"], "already_signed")

    def test_cancel_after_definite_failure_keeps_reason(self):
        _, result, _, _, _, _, _ = self._run_task(
            "definite_fail_then_wait", retry_for=30, deadline_past=False,
            cancel_on_log="kind=done")
        self.assertEqual(result["stop_reason"], "max_attempts",
                         "确定失败晚于停止时不能被改写成「待核对」")
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["status"], "failed")

    def test_cancel_without_submission_is_plain_canceled(self):
        _, result, _, _, _, _, _ = self._run_task(
            "silent", retry_for=30, deadline_past=False, cancel_after=0.5)
        self.assertEqual(result["status"], "canceled",
                         "一次都没提交时仍是普通取消")
        self.assertEqual(result["attempts"], 0)


class SubmitBackoffTests(unittest.TestCase):
    """RC-05：人数已满时提交间隔 2 秒起、1.5 倍退避、8 秒封顶且受截止钳制。"""

    def test_backoff_sequence_is_bounded(self):
        from grab import (SUBMIT_BACKOFF_MAX_S, SUBMIT_BACKOFF_START_S,
                          next_submit_gap)
        gaps = []
        gap = SUBMIT_BACKOFF_START_S
        for _ in range(8):
            gaps.append(round(gap, 3))
            gap = next_submit_gap(gap)
        self.assertEqual(gaps[:5], [2.0, 3.0, 4.5, 6.75, 8.0])
        self.assertEqual(set(gaps[4:]), {SUBMIT_BACKOFF_MAX_S},
                         "退避必须封顶在 8 秒，不能无限放大")

    def test_backoff_never_exceeds_remaining_window(self):
        from grab import wait_before_next_submit
        sleeps = []

        class _Budget:
            def remaining_s(self):
                return 5.0

            def sleep(self, seconds):
                sleeps.append(round(seconds, 3))

        next_gap = wait_before_next_submit(_Budget(), 8.0)
        self.assertEqual(sleeps, [5.0], "窗口只剩 5 秒时最多等 5 秒")
        self.assertEqual(next_gap, 8.0)

    def test_invalid_gap_restarts_from_two_seconds(self):
        from grab import next_submit_gap
        self.assertEqual(next_submit_gap(None), 3.0)
        self.assertEqual(next_submit_gap(0), 3.0)
        self.assertEqual(next_submit_gap(-10), 3.0)

# ==================== 源自 test_retry_phone_policy.py ====================
"""重试三模式与手机受限链路的具名契约测试（离线）。

覆盖决策 1/2 的行为边界：显式时长不扩窗、自动延长（-1）初始 120 与
cap 1500、父监督按「候选 − 已接纳」增量平移单调截止、伪造/重复/非法/过界
事件 0 增量、取消立即唤醒看门狗、三种模式 worker/父/桌面投影同值、
0 缺截止 2 分钟兜底。全部离线：fake worker 脚本、假时钟、127.0.0.1 不开，
真实学校/浏览器/凭据一律不用。

@author Author
"""


LOCAL = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

configure_time_source(time.time)

from domain.retry_window import (  # noqa: E402
    ADAPTIVE_RETRY, ADAPTIVE_SECONDS, DEFAULT_RETRY_SECONDS,
    extension_cap, extension_delta, initial_deadline,
)
from domain.time_text import task_deadline  # noqa: E402
from grab import BurstPolicy  # noqa: E402


# ---- 学校时间文本换算（与 ui/state/time.js 的 toTs 同一公式）------------
def school_text(epoch: float) -> str:
    """epoch 秒 → 学校时间文本；toTs 是它的逆变换。"""
    dt = datetime.fromtimestamp(float(epoch) + 8 * 3600, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def school_epoch(text) -> "float | None":
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$",
                     str(text or ""))
    if not match:
        return None
    y, mo, d, h, mi, s = (int(part) for part in match.groups())
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc).timestamp() - 8 * 3600


# ---- fake worker 脚本（临时根落地，零真实 worker/浏览器）----------------
PHONE_WORKER_FIXTURE = r'''
import os
import sys
import time

scenario = sys.argv[1] if len(sys.argv) > 1 else "silent"
deadline = os.environ.get("CAMPUS_TEST_DEADLINE", "0")

if scenario == "silent":
    time.sleep(60)
elif scenario == "quick":
    # 只为拿 worker 命令行：立刻正常退出，不占监督窗口
    print("[i] quick", flush=True)
    sys.exit(0)
elif scenario == "extend_then_wait":
    # 先宣布一次扩窗再挂住：父层必须按新截止收树，旧截止不得杀树
    print("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline, flush=True)
    time.sleep(60)
elif scenario == "extend_then_done":
    print("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline, flush=True)
    print("[retry] kind=done attempts=1 stop_reason=success retry_deadline=%s "
          "sign_end=0 last_reason=" % deadline, flush=True)
    sys.exit(0)
elif scenario == "terminal_then_extend":
    # 终态之后的扩窗必须被忽略：旧截止照常收树
    print("[retry] kind=done attempts=1 stop_reason=success retry_deadline=0 "
          "sign_end=0 last_reason=", flush=True)
    print("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline, flush=True)
    time.sleep(60)
elif scenario == "double_extend":
    # 同一候选重复宣布一次：只有第一次有增量
    print("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline, flush=True)
    print("[retry] kind=window_extended retry_deadline=%s sign_end=0" % deadline, flush=True)
    time.sleep(60)
else:
    raise SystemExit("unknown scenario: %s" % scenario)
'''


class _ServiceCase(unittest.TestCase):
    """api._run_plan_task 的公共装置：假 worker 脚本 + 短监督余量。"""

    GRACE = 0.4

    def setUp(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        self.app = local_app
        self.root = Path(tempfile.mkdtemp(prefix="campus-retry-phone-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.root), True)
        self._old_grace = local_app.SUPERVISE_GRACE_S
        local_app.SUPERVISE_GRACE_S = self.GRACE
        self.addCleanup(setattr, local_app, "SUPERVISE_GRACE_S", self._old_grace)
        self.script = self.root / "worker_fixture.py"
        self.script.write_text(PHONE_WORKER_FIXTURE, encoding="utf-8")

    def _spec(self, retry_for, *, anchor_offset: float = 1.0,
              sign_end: str = "") -> TaskSpec:
        """anchor_offset 是「当前时刻 − 冻结起点」：越大，初始截止越近。"""
        return TaskSpec(task_id="t1", activity_id="a1", name="重试模式实验",
                        sign_start="2026-10-30 09:00:00", act_start="", act_end="",
                        sign_end=sign_end, retry_for_s=retry_for, max_attempts=0,
                        signup_mode="instant_signup", lead_s=0,
                        retry_started_at=time.time() - anchor_offset)

    def _run(self, scenario: str, *, retry_for, anchor_offset: float = 1.0,
             sign_end: str = "", cancel_after: float | None = None,
             announce_deadline: "float | None" = None, clock_spy=None):
        """跑一场 fake worker；返回 (result, elapsed, events, captured_args)。"""
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        events = []
        api._emit = lambda kind, payload: events.append((kind, payload))
        cancel = threading.Event()
        captured = []
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            if announce_deadline is not None:
                env["CAMPUS_TEST_DEADLINE"] = "%.3f" % float(announce_deadline)
            return env

        def fake_command(*args):
            # worker_command 返回的 argv 会被 plan_service 用 += 追加
            # --window/--retry-for/--sign-end 等：记下最终 argv 才是证据
            cmd = [sys.executable, str(self.script), scenario]
            captured.append(cmd)
            return cmd

        timer = None
        started = time.time()
        result = None
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            if clock_spy is not None:
                with mock.patch.object(api, "_clock_now", clock_spy):
                    if cancel_after is not None:
                        timer = threading.Timer(cancel_after, cancel.set)
                        timer.start()
                    try:
                        result = api._run_plan_task(
                            self._spec(retry_for, anchor_offset=anchor_offset,
                                       sign_end=sign_end), cancel, lambda *a: None)
                    finally:
                        if timer is not None:
                            timer.cancel()
            else:
                if cancel_after is not None:
                    timer = threading.Timer(cancel_after, cancel.set)
                    timer.start()
                try:
                    result = api._run_plan_task(
                        self._spec(retry_for, anchor_offset=anchor_offset,
                                   sign_end=sign_end), cancel, lambda *a: None)
                finally:
                    if timer is not None:
                        timer.cancel()
        return result, time.time() - started, events, captured


def _watchdog_leaks() -> list:
    return [t for t in threading.enumerate()
            if t.name == "signup-watchdog" and t.is_alive()]


# ===================================================================== 公式层
class InitialDeadlineTests(unittest.TestCase):
    """-1 初始 120、cap 1500 且 sign_end 硬截；三种模式同一公式。"""

    def test_auto_mode_initial_deadline_is_120_not_sign_end(self):
        anchor = 1792000000.0
        sign_end = anchor + 4000.0
        self.assertEqual(initial_deadline(anchor, ADAPTIVE_RETRY, sign_end),
                         anchor + DEFAULT_RETRY_SECONDS)
        self.assertEqual(initial_deadline(anchor, ADAPTIVE_RETRY, None),
                         anchor + DEFAULT_RETRY_SECONDS)

    def test_auto_mode_cap_is_anchor_plus_1500_cut_by_sign_end(self):
        anchor = 1792000000.0
        self.assertEqual(extension_cap(anchor, None), anchor + ADAPTIVE_SECONDS)
        self.assertEqual(extension_cap(anchor, anchor + 300.0), anchor + 300.0)
        self.assertEqual(extension_cap(anchor, anchor + 99999.0),
                         anchor + ADAPTIVE_SECONDS)

    def test_fixed_and_until_deadline_keep_existing_contract(self):
        anchor = 1792000000.0
        sign_end = anchor + 30.0
        # 正数硬时长：sign_end 更早时被截断
        self.assertEqual(initial_deadline(anchor, 600, sign_end), sign_end)
        self.assertEqual(initial_deadline(anchor, 600, anchor + 900.0), anchor + 600)
        # 0：有截止直达，缺截止回退 120
        self.assertEqual(initial_deadline(anchor, 0, anchor + 5000.0), anchor + 5000.0)
        self.assertEqual(initial_deadline(anchor, 0, None), anchor + DEFAULT_RETRY_SECONDS)

    def test_zero_without_sign_end_falls_back_to_two_minutes(self):
        """0 缺截止明确兜底 2 分钟，绝不无限运行。"""
        anchor = 1792000000.0
        deadline, binding = compute_retry_window(anchor, None, 0, now=anchor)[1:]
        self.assertEqual(deadline, anchor + DEFAULT_RETRY_SECONDS)
        self.assertEqual(binding, "fallback")
        self.assertEqual(initial_deadline(anchor, 0, None), anchor + 120.0)

    def test_worker_and_parent_formula_agree_for_three_modes(self):
        anchor = 1792000000.0
        sign_end = anchor + 4000.0
        cases = ((120, anchor + 120.0), (ADAPTIVE_RETRY, anchor + 120.0),
                 (0, sign_end))
        for mode, want in cases:
            with self.subTest(mode=mode):
                _, worker_deadline, _ = compute_retry_window(
                    anchor, sign_end, mode, now=anchor)
                spec = TaskSpec(task_id="t1", activity_id="a1", name="对照",
                                sign_start="", act_start="", act_end="",
                                sign_end=school_text(sign_end),
                                retry_for_s=mode, max_attempts=0,
                                signup_mode="instant_signup", lead_s=0,
                                retry_started_at=anchor)
                parent_deadline = task_deadline(spec, school_epoch)
                self.assertEqual(worker_deadline, want)
                self.assertEqual(parent_deadline, want)


class ExtensionDeltaTests(unittest.TestCase):
    """伪造/重复/非法/过界事件 0 增量；合法扩窗只给严格增长的差值。"""

    CAP = 2500.0

    def test_valid_extension_returns_strict_growth_delta(self):
        self.assertEqual(extension_delta(1000.0, 1380.0, self.CAP, True), 380.0)

    def test_fixed_mode_and_disabled_never_extend(self):
        self.assertEqual(extension_delta(1000.0, 1380.0, self.CAP, False), 0.0)
        self.assertEqual(extension_delta(1000.0, 1380.0, None, True), 0.0)

    def test_duplicate_shrink_out_of_bounds_are_zero(self):
        self.assertEqual(extension_delta(1000.0, 1000.0, self.CAP, True), 0.0)
        self.assertEqual(extension_delta(1000.0, 900.0, self.CAP, True), 0.0)
        self.assertEqual(extension_delta(1000.0, self.CAP + 1.0, self.CAP, True), 0.0)
        self.assertEqual(extension_delta(1000.0, self.CAP, self.CAP, True),
                         self.CAP - 1000.0)

    def test_illegal_values_are_zero(self):
        for candidate in ("abc", None, "", float("nan"), float("inf"), [1]):
            with self.subTest(candidate=candidate):
                self.assertEqual(extension_delta(1000.0, candidate, self.CAP, True), 0.0)

    def test_delta_does_not_depend_on_wall_clock(self):
        """同一对数值的增量恒定：时钟跳变不影响 extension_delta 的结果。"""
        before = extension_delta(1000.0, 1380.0, self.CAP, True)
        time.sleep(0.05)
        self.assertEqual(extension_delta(1000.0, 1380.0, self.CAP, True), before)


class _FakeClock:
    """BurstPolicy 的最小业务时钟替身：wall 是业务 epoch，mono 是单调秒。"""

    def __init__(self, wall, mono=1000.0):
        self.wall = float(wall)
        self.mono = float(mono)

    def time(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def elapsed_s(self):
        return self.mono

    def now(self):
        return self.wall

    def sleep(self, seconds):
        step = max(0.0, float(seconds))
        self.wall += step
        self.mono += step


class WorkerExtensionPolicyTests(unittest.TestCase):
    """worker 侧扩窗：固定 120 连 404 不扩；自动模式扩到 cap 且 sign_end 硬截。"""

    START = 1792000000.0

    def _policy(self, *, allow_extend, base_deadline=None, sign_end_ts=None):
        clock = _FakeClock(wall=self.START, mono=1000.0)
        policy = BurstPolicy(
            open_ts=self.START,
            base_deadline=self.START + 120.0 if base_deadline is None else base_deadline,
            sign_end_ts=sign_end_ts, max_attempts=0,
            clock=clock, retry_start=self.START,
            allow_extend=allow_extend)
        return policy, clock

    def test_fixed_120_with_consecutive_404_does_not_extend(self):
        """固定 120（显式 --retry-for）连 404 不扩窗：用户给的秒数是硬承诺。"""
        policy, clock = self._policy(allow_extend=False)
        clock.wall = self.START + 5.0
        for _ in range(10):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.effective_deadline, self.START + 120.0)
        self.assertGreater(policy.streak_404, 3, "连击照常计数，只是不拉窗口")

    def test_auto_mode_extends_to_cap_and_sign_end_stays_hard(self):
        """自动延长（allow_extend）连 404 扩到起点+1500；sign_end 更早时被硬截。"""
        policy, clock = self._policy(allow_extend=True, base_deadline=self.START + 120.0)
        clock.wall = self.START + 5.0
        for _ in range(10):
            policy.settle(policy.register_request(), "404")
        self.assertEqual(policy.effective_deadline, self.START + ADAPTIVE_SECONDS)

        cut, clock2 = self._policy(allow_extend=True, base_deadline=self.START + 120.0,
                                   sign_end_ts=self.START + 300.0)
        clock2.wall = self.START + 5.0
        for _ in range(10):
            cut.settle(cut.register_request(), "404")
        self.assertEqual(cut.effective_deadline, self.START + 300.0,
                         "sign_end 永远硬截止，扩窗不得越过")


class PlanServiceModeTests(_ServiceCase):
    """父层：自动模式 worker 参数、扩窗平移单调截止、取消立即唤醒。"""

    def test_auto_mode_worker_arguments_use_window_without_retry_for(self):
        """自动延长（-1）发 --window 120 且不传 --retry-for；正数/0 仍显式。"""
        _, _, _, captured = self._run("quick", retry_for=ADAPTIVE_RETRY)
        args = captured[0]
        self.assertIn("--window", args)
        self.assertEqual(args[args.index("--window") + 1], "120")
        self.assertNotIn("--retry-for", args)

        _, _, _, captured = self._run("quick", retry_for=120)
        args = captured[0]
        self.assertIn("--retry-for", args)
        self.assertEqual(args[args.index("--retry-for") + 1], "120")
        self.assertNotIn("--window", args)

        _, _, _, captured = self._run("quick", retry_for=0)
        args = captured[0]
        self.assertEqual(args[args.index("--retry-for") + 1], "0")

    def test_extension_moves_hard_stop_and_old_deadline_does_not_kill(self):
        """延期后旧截止不杀树、新截止会收树（关键算式按增量平移）。"""
        now = time.time()
        anchor = now - (DEFAULT_RETRY_SECONDS - 1.0)   # 初始截止 ≈ 1 秒后
        candidate = anchor + DEFAULT_RETRY_SECONDS + 4.0
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._emit = lambda kind, payload: None
        cancel = threading.Event()
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_TEST_DEADLINE"] = "%.3f" % candidate
            return env

        def fake_command(*args):
            return [sys.executable, str(self.script), "extend_then_wait"]

        started = time.time()
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            result = api._run_plan_task(
                self._spec(ADAPTIVE_RETRY, anchor_offset=DEFAULT_RETRY_SECONDS - 1.0),
                cancel, lambda *a: None)
        elapsed = time.time() - started
        self.assertEqual(result["stop_reason"], "retry_duration")
        self.assertGreaterEqual(elapsed, 2.5,
                                "旧截止（约 %.1f 秒）不得杀树" % (0.5 + self.GRACE))
        self.assertLessEqual(elapsed, 4.0 + self.GRACE + 2.0,
                             "新截止必须把树收走，不能挂住不退")
        self.assertEqual(_watchdog_leaks(), [])

    def test_fixed_mode_ignores_window_extended_events(self):
        """固定模式的扩窗事件一律 0 增量：旧截止照常收树。"""
        now = time.time()
        anchor = now - (DEFAULT_RETRY_SECONDS - 1.0)
        candidate = anchor + DEFAULT_RETRY_SECONDS + 8.0
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._emit = lambda kind, payload: None
        cancel = threading.Event()
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_TEST_DEADLINE"] = "%.3f" % candidate
            return env

        def fake_command(*args):
            return [sys.executable, str(self.script), "extend_then_wait"]

        started = time.time()
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            result = api._run_plan_task(
                self._spec(120, anchor_offset=DEFAULT_RETRY_SECONDS - 1.0),
                cancel, lambda *a: None)
        elapsed = time.time() - started
        self.assertEqual(result["stop_reason"], "retry_duration")
        self.assertLess(elapsed, 3.0, "固定 120 不得被 window_extended 拉长")
        self.assertEqual(_watchdog_leaks(), [])

    def test_terminal_then_extend_is_ignored(self):
        """终态之后的扩窗事件忽略：仍按旧截止收树，不延期。"""
        now = time.time()
        anchor = now - (DEFAULT_RETRY_SECONDS - 1.0)
        candidate = anchor + DEFAULT_RETRY_SECONDS + 8.0
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._emit = lambda kind, payload: None
        cancel = threading.Event()
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_TEST_DEADLINE"] = "%.3f" % candidate
            return env

        def fake_command(*args):
            return [sys.executable, str(self.script), "terminal_then_extend"]

        started = time.time()
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            result = api._run_plan_task(
                self._spec(ADAPTIVE_RETRY, anchor_offset=DEFAULT_RETRY_SECONDS - 1.0),
                cancel, lambda *a: None)
        elapsed = time.time() - started
        self.assertLess(elapsed, 3.0, "终态后的扩窗不得延期")
        self.assertEqual(result["status"], "success")

    def test_duplicate_extension_event_adds_only_once(self):
        """同一候选重复宣布：只有第一次有增量。"""
        now = time.time()
        anchor = now - (DEFAULT_RETRY_SECONDS - 1.0)
        candidate = anchor + DEFAULT_RETRY_SECONDS + 4.0
        api = stop_auto_relogin_on_cleanup(self, self.app.Api(clock=TestWallClock()))
        api._emit = lambda kind, payload: None
        cancel = threading.Event()
        original_env = self.app._env

        def fake_env():
            env = dict(original_env())
            env["CAMPUS_TEST_DEADLINE"] = "%.3f" % candidate
            return env

        def fake_command(*args):
            return [sys.executable, str(self.script), "double_extend"]

        started = time.time()
        with mock.patch.object(self.app, "worker_command", fake_command), \
                mock.patch.object(self.app, "_env", fake_env):
            result = api._run_plan_task(
                self._spec(ADAPTIVE_RETRY, anchor_offset=DEFAULT_RETRY_SECONDS - 1.0),
                cancel, lambda *a: None)
        elapsed = time.time() - started
        self.assertEqual(result["stop_reason"], "retry_duration")
        # 只扩一次：new = old + (candidate - accepted)；重复事件不得再加一份
        self.assertLess(elapsed, 7.5, "重复扩窗事件不得叠加第二次增量")
        self.assertEqual(_watchdog_leaks(), [])

    def test_cancel_wakes_watchdog_immediately(self):
        """取消立即唤醒看门狗线程退出：不许睡到远截止才放手。"""
        result, _, _, _ = self._run("silent", retry_for=3600, cancel_after=0.3)
        self.assertIn(result["status"], {"canceled", "failed"})
        self.assertEqual(_watchdog_leaks(), [],
                         "取消后 signup-watchdog 线程必须已被唤醒退出")

    def test_backward_clock_recalibration_cannot_extend_monotonic_duration(self):
        """扩窗不重新读业务时钟：clock_now 只在入口取一次。"""
        now = time.time()
        anchor = now - (DEFAULT_RETRY_SECONDS - 1.0)
        candidate = anchor + DEFAULT_RETRY_SECONDS + 3.0
        calls = {"n": 0}

        def spy():
            calls["n"] += 1
            return now

        result, _, _, _ = self._run(
            "extend_then_done", retry_for=ADAPTIVE_RETRY,
            anchor_offset=DEFAULT_RETRY_SECONDS - 1.0,
            announce_deadline=candidate, clock_spy=spy)
        self.assertEqual(result["status"], "success")
        self.assertEqual(calls["n"], 1,
                         "扩窗路径不得重新读业务时钟（重校向后修正不得延期）")


# ===================================================================== 投影对照
def _run_js(snippet: str):
    """node vm 执行真实 UI 脚本（复用项目既有行为测试装置）；无 node 时 skip。"""
    try:
        from fixtures.ui_harness import run_js
    except Exception as exc:                       # pragma: no cover - 装置缺失
        raise unittest.SkipTest("UI 行为装置不可用：%s" % exc)
    return run_js(snippet)


class DesktopProjectionTests(unittest.TestCase):
    """三种模式 worker / 父监督 / 桌面投影同值对照（node vm 跑真实 UI 脚本，原 board.js）。"""

    ANCHOR = 1792000000.0
    SIGN_END = ANCHOR + 4000.0

    def _desktop(self, retry_for, sign_end_text, fallback_now=None,
                 with_deadline=None):
        import json as _json
        task = {"retry_for_s": retry_for, "retry_started_at": self.ANCHOR,
                "sign_end": sign_end_text}
        if with_deadline is not None:
            task["retry_deadline"] = with_deadline
        now = self.ANCHOR if fallback_now is None else fallback_now
        snippet = ("const task = %s;\n"
                   "out.push(effectiveRetryDeadline(task, %s));\n"
                   % (_json.dumps(task), repr(float(now))))
        values = _run_js(snippet)
        self.assertTrue(values, "桌面投影没有输出")
        return values[0]

    def _worker_parent(self, mode, sign_end_epoch):
        _, worker_deadline, _ = compute_retry_window(
            self.ANCHOR, sign_end_epoch, mode, now=self.ANCHOR)
        spec = TaskSpec(task_id="t1", activity_id="a1", name="投影对照",
                        sign_start="", act_start="", act_end="",
                        sign_end=school_text(sign_end_epoch) if sign_end_epoch else "",
                        retry_for_s=mode, max_attempts=0,
                        signup_mode="instant_signup", lead_s=0,
                        retry_started_at=self.ANCHOR)
        return worker_deadline, task_deadline(spec, school_epoch)

    def test_three_modes_projection_same_value_across_layers(self):
        """固定 120 / 自动 -1 / 直到截止 0：三层推导同值（含 0 缺截止兜底）。"""
        cases = (
            (120, self.SIGN_END, self.ANCHOR + 120.0),
            (ADAPTIVE_RETRY, self.SIGN_END, self.ANCHOR + 120.0),
            (0, self.SIGN_END, self.SIGN_END),
            (0, None, self.ANCHOR + DEFAULT_RETRY_SECONDS),
            (120, self.ANCHOR + 30.0, self.ANCHOR + 30.0),
        )
        for mode, sign_end_epoch, want in cases:
            with self.subTest(mode=mode, sign_end=sign_end_epoch):
                worker_deadline, parent_deadline = self._worker_parent(
                    mode, sign_end_epoch)
                desktop = self._desktop(
                    mode, school_text(sign_end_epoch) if sign_end_epoch else "")
                self.assertEqual(worker_deadline, want)
                self.assertEqual(parent_deadline, want)
                self.assertEqual(float(desktop), want)

    def test_auto_mode_matches_explicit_120_worker_formula(self):
        """自动模式的 worker 参数是 --window 120：两条公式初始截止必须同值。"""
        _, via_auto, _ = compute_retry_window(
            self.ANCHOR, self.SIGN_END, ADAPTIVE_RETRY, now=self.ANCHOR)
        _, via_window, _ = compute_retry_window(
            self.ANCHOR, self.SIGN_END, DEFAULT_RETRY_SECONDS, now=self.ANCHOR)
        self.assertEqual(via_auto, via_window)

    def test_desktop_prefers_backend_accepted_deadline(self):
        """倒计时优先后端已接纳 deadline（合法扩窗后的权威截止同此入口）。"""
        desktop = self._desktop(ADAPTIVE_RETRY, school_text(self.SIGN_END),
                                with_deadline=self.ANCHOR + 777.0)
        self.assertEqual(float(desktop), self.ANCHOR + 777.0)

    def test_desktop_zero_without_sign_end_shows_two_minute_fallback(self):
        desktop = self._desktop(0, "")
        self.assertEqual(float(desktop), self.ANCHOR + DEFAULT_RETRY_SECONDS)


class CanonicalOptionsTests(unittest.TestCase):
    """bootstrap 的权威选项与桌面 select / store.js 兜底副本保持一致。"""

    def _bootstrap_retry_options(self):
        sys.path.insert(0, str(LOCAL))
        try:
            import app as local_app
        except Exception as exc:
            self.skipTest("无法导入 local/app.py：%s" % exc)
        finally:
            sys.path.pop(0)
        tmp = tempfile.mkdtemp(prefix="campus-retry-opts-")
        self.addCleanup(shutil.rmtree, tmp, True)
        with mock.patch.object(local_app, "PREFS", Path(tmp) / "ui.json"), \
                mock.patch.object(local_app, "DEMO", True):
            payload = stop_auto_relogin_on_cleanup(
                self, local_app.Api(clock=TestWallClock())).bootstrap()
        return payload["retry_options"]

    def test_desktop_select_options_match_bootstrap_canonical_choices(self):
        options = self._bootstrap_retry_options()
        html = (LOCAL / "ui" / "index.html").read_text(encoding="utf-8")
        match = re.search(r'id="retry-for".*?</select>', html, re.S)
        self.assertIsNotNone(match, "找不到 #retry-for 下拉框")
        values = re.findall(r'<option value="(-?\d+)">', match.group(0))
        self.assertEqual(values, [str(item["value"]) for item in options["choices"]],
                         "桌面选项必须与 bootstrap 权威清单同序同值")
        self.assertEqual(options["default"], 120)

    def test_store_default_choices_match_bootstrap_canonical(self):
        options = self._bootstrap_retry_options()
        snippet = "out.push(JSON.parse(JSON.stringify(S.retryOptions)));\n"
        values = _run_js(snippet)
        self.assertTrue(values, "store.js 没有导出 retryOptions")
        self.assertEqual(values[0]["choices"], options["choices"])
        self.assertEqual(values[0]["default"], options["default"])

# ==================== 源自 test_retry_phone_integration.py ====================
"""B 轮离线集成：pair → 读活动 → 自动模式 start → 合法扩窗 → 截止一致 → 停止
→ relay 挑战 → 匹配码 → 假校验成功 → 读新登录结论。

临时数据根 + fake worker/clock/Api + loopback HTTP；不读真实账号、不连学校。

@author Author
"""

import json
import urllib.error
import urllib.request

LOCAL = Path(__file__).resolve().parents[1]
TESTS_DIR = Path(__file__).resolve().parent
if str(LOCAL) not in sys.path:
    sys.path.insert(0, str(LOCAL))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from application.phone_service import PhoneAccessService  # noqa: E402

# 合法的一像素 PNG（1×1 透明）：投影层只放行真 PNG 魔数的图，
# 'AAAA' 这类假图会被丢成空串，用它测正常链路等于测一个不可能发生的事件。
CAPTCHA_PNG = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
               "AAAAC0lEQVR42mNgAAIAAAUAAen63NgAAAAASUVORK5CYII=")
from infrastructure.phone_http import PhoneHttpServer  # noqa: E402

PHONE_DIR = LOCAL / "ui" / "m"
ANCHOR = 1792000000.0


class ScriptedApi:
    """替身 Api：只按脚本回话，任何学校/进程动作都不会真发生。"""

    def __init__(self, service_holder):
        self.calls = []
        self.service_holder = service_holder
        self.login = {"hours_left": 3, "session_present": True}
        self.plan = None
        self.ack_lost = False

    # ---- 读 ----
    def list_activities(self, request_id=""):
        self.calls.append(("list_activities", request_id))
        return {"ok": True, "request_id": request_id, "items": [
            {"id": "a1", "name": "篮球赛", "sign_start": "2026-11-01 09:00:00",
             "sign_end": "2026-11-02 09:00:00", "signed": False}]}

    def check(self, request_id=""):
        self.calls.append(("check", request_id))
        return {"ok": True, "result": "valid", "request_id": request_id}

    # ---- 写 ----
    def start_plan(self, items, headed=False, retry_policy=None, request_id="", source="desktop"):
        # source 由手机服务端补成 phone（客户端带不进来），替身照收
        self.calls.append(("start_plan", items, request_id))
        self.last_source = source
        policy = retry_policy or {}
        task = {"task_id": "t1", "name": "篮球赛", "status": "submitting",
                "retry_for_s": int(policy.get("retry_for_s", 120)),
                "max_attempts": int(policy.get("max_attempts", 0)),
                "retry_started_at": ANCHOR,
                "retry_deadline": initial_deadline(
                    ANCHOR, policy.get("retry_for_s", 120), ANCHOR + 4000.0),
                "sign_end_ts": ANCHOR + 4000.0}
        self.plan = {"plan_id": "p1", "tasks": [task]}
        if self.ack_lost:
            return {"ok": False, "error": "busy"}   # 应答丢失：调用方以为没收到
        return {"ok": True, "plan_id": "p1", "request_id": request_id}

    def start_request_state(self, request_id=""):
        self.calls.append(("start_request_state", request_id))
        return {"ok": True, "state": "accepted", "plan_id": "p1",
                "request_id": request_id}

    def stop_plan(self, plan_id):
        self.calls.append(("stop_plan", plan_id))
        if self.plan:
            self.plan["tasks"][0]["status"] = "failed"
        return {"ok": True}

    def cancel_task(self, plan_id, task_id):
        self.calls.append(("cancel_task", plan_id, task_id))
        return {"ok": True}

    def save_prefs(self, prefs):
        self.calls.append(("save_prefs", prefs))
        return {"ok": True}

    # ---- relay ----
    def phone_relogin_begin(self):
        self.calls.append(("phone_relogin_begin",))
        return {"ok": True, "flow_id": "flow-1"}

    def phone_relogin_submit(self, flow_id="", challenge_id="", code=""):
        self.calls.append(("phone_relogin_submit", flow_id, challenge_id, code))
        if code == "Ab12":
            self.login = {"hours_left": 17, "session_present": True}
            return {"ok": True, "verified": True}
        return {"ok": False, "error": "bad_code"}

    def phone_relogin_cancel(self, flow_id=""):
        self.calls.append(("phone_relogin_cancel", flow_id))
        return {"ok": True}


class IntegrationBase(unittest.TestCase):
    def setUp(self):
        self.holder = {}
        self.api = ScriptedApi(self.holder)
        self.ui_dir = Path(tempfile.mkdtemp(prefix="campus-int-ui-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.ui_dir), True)
        scripts = re.findall(
            r'<script\s+src="([^"]+)"\s*></script>',
            (PHONE_DIR / "index.html").read_text(encoding="utf-8"),
        )
        for name in ("index.html", "styles.css", *scripts):
            (self.ui_dir / name).write_text(
                (PHONE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
        self.raw = {
            "activities": [{"id": "a1", "name": "篮球赛", "signed": False}],
            "login": dict(self.api.login),
            "plan": None, "busy": False,
            "terms": {"accepted_version": "1"},
            "retry_options": {"default": 120, "fallback_seconds": 120,
                              "adaptive_cap_seconds": ADAPTIVE_SECONDS,
                              "choices": [{"value": 120, "label": "2 分钟"},
                                          {"value": ADAPTIVE_RETRY,
                                           # 标签与 app.py 同步补空格（GL06）；仅文案，取值不变
                                           "label": "自动延长（最多 25 分钟）"},
                                          {"value": 0, "label": "直到报名截止"}]},
        }
        self.service = PhoneAccessService(
            actions=_phone_test_actions(self.api), now=lambda: 0.0,
            state_of=self._raw_state,
            server_factory=lambda host, port, svc: PhoneHttpServer(
                host, port, svc, ui_dir=self.ui_dir))
        self.holder["service"] = self.service
        started = self.service.start("127.0.0.1", 0)
        self.assertTrue(started["ok"], started)
        self.base = started["address"].rstrip("/")
        self.origin = self.base
        self.code = started["pair_code"]
        self.addCleanup(self.service.stop)

    def _raw_state(self):
        self.raw["login"] = dict(self.api.login)
        self.raw["plan"] = self.api.plan
        return self.raw

    def _req(self, method, path, body=None, headers=None, cookie=None):
        data = None
        merged = {"Host": self.base.split("//", 1)[1]}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            merged["Content-Type"] = "application/json"
        merged.update(headers or {})
        if cookie:
            merged["Cookie"] = cookie
        req = urllib.request.Request(self.base + path, data=data, method=method)
        for key, value in merged.items():
            req.add_header(key, value)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers), exc.read()

    def _pair(self, code=None):
        status, headers, body = self._req(
            "POST", "/pair", body={"code": code or self.code},
            headers={"Origin": self.origin})
        payload = json.loads(body)
        cookie = ""
        for key, value in headers.items():
            if key.lower() == "set-cookie" and value.startswith("campus_phone_sid="):
                cookie = value.split(";", 1)[0]
        return status, payload, cookie

    def _action(self, action, args, cookie, csrf):
        status, _, body = self._req(
            "POST", "/api/action", body={"action": action, "args": args},
            headers={"Origin": self.origin, "X-Campus-Csrf": csrf}, cookie=cookie)
        return status, json.loads(body)

    def _state(self, cookie, cursor=0):
        status, _, body = self._req("GET", "/api/state?after=%d" % cursor,
                                    cookie=cookie)
        self.assertEqual(status, 200)
        return json.loads(body)


class FullChainTests(IntegrationBase):
    def test_pair_read_start_extend_stop_relogin_chain(self):
        """计划要求的完整链路（每一步都用真 HTTP + 替身 Api）。"""
        # 1) 配对
        status, payload, cookie = self._pair()
        self.assertEqual(status, 200)
        self.assertTrue(cookie)

        # 2) 读活动（只读本机缓存）
        state = self._state(cookie)
        self.assertEqual(state["state"]["activities"][0]["id"], "a1")
        self.assertEqual(self.api.calls, [], "读状态不得触发学校流量")

        # 3) 自动模式 start
        status, result = self._action("start_plan", {
            "items": [{"id": "a1"}],
            "retry_policy": {"retry_for_s": ADAPTIVE_RETRY, "max_attempts": 0},
            "request_id": "req-1"}, cookie, payload["csrf"])
        self.assertTrue(result["ok"])
        self.assertEqual(self.api.calls[-1][0], "start_plan")
        self.assertEqual(self.api.calls[-1][1], [{"id": "a1"}])
        task = self.api.plan["tasks"][0]
        self.assertEqual(task["retry_for_s"], ADAPTIVE_RETRY)
        want_initial = initial_deadline(ANCHOR, ADAPTIVE_RETRY, ANCHOR + 4000.0)
        self.assertEqual(task["retry_deadline"], want_initial,
                         "自动模式初始截止必须是 120 秒口径")

        # 4) 合法扩窗：worker 事件进缓冲，权威截止前移
        candidate = ANCHOR + DEFAULT_RETRY_SECONDS + 300.0
        self.assertLessEqual(candidate,
                             extension_cap(ANCHOR, ANCHOR + 4000.0))
        self.service.record_event("log", {"kind": "window_extended",
                                          "retry_deadline": candidate})
        task["retry_deadline"] = candidate
        state = self._state(cookie)
        shown = state["state"]["plan"]["tasks"][0]
        self.assertEqual(shown["retry_deadline"], candidate,
                         "快照 deadline 必须与后端接纳值一致")

        # 5) 停止（显式）
        status, result = self._action("stop_plan", {"plan_id": "p1"},
                                      cookie, payload["csrf"])
        self.assertTrue(result["ok"])
        self.assertEqual(self.api.calls[-1], ("stop_plan", "p1"))

        # 6) relay 挑战 → 7) 匹配码 → 8) 假校验成功
        status, result = self._action("phone_relogin_begin", {}, cookie,
                                      payload["csrf"])
        self.assertTrue(result["ok"])
        self.service.record_event("phone_relogin", {
            "ready": True, "state": "waiting_code", "flow_id": "flow-1",
            "challenge_id": "chg-1", "image": CAPTCHA_PNG,
            "expires_in": 60, "attempts": 0, "max_attempts": 3, "safe_error": ""})
        state = self._state(cookie)
        relay = state["events"][-1]["payload"]
        self.assertEqual(relay["challenge_id"], "chg-1")
        self.assertTrue(relay["image"].startswith("data:image/png;base64,"))

        status, result = self._action("phone_relogin_submit", {
            "flow_id": "flow-1", "challenge_id": "chg-1", "code": "Ab12"},
            cookie, payload["csrf"])
        self.assertTrue(result["ok"])

        # 9) 读新登录结论
        state = self._state(cookie)
        self.assertEqual(state["state"]["login"]["hours_left"], 17,
                         "新登录结论必须反映假校验成功后的会话")

    def test_lost_ack_reconciles_exactly_once(self):
        """丢 ack：同 request_id 只读对账只接纳一次，绝不重复开计划。"""
        self.api.ack_lost = True
        status, payload, cookie = self._pair()
        status, result = self._action("start_plan", {
            "items": [{"id": "a1"}], "request_id": "req-9"},
            cookie, payload["csrf"])
        self.assertFalse(result["ok"], "应答丢失时调用方看不到成功")
        started = [c for c in self.api.calls if c[0] == "start_plan"]
        self.assertEqual(len(started), 1, "对账不得再开一场计划")
        status, result = self._action("start_request_state",
                                      {"request_id": "req-9"}, cookie,
                                      payload["csrf"])
        self.assertEqual(result["state"], "accepted")
        status, result = self._action("start_request_state",
                                      {"request_id": "req-9"}, cookie,
                                      payload["csrf"])
        self.assertEqual(result["state"], "accepted")
        started = [c for c in self.api.calls if c[0] == "start_plan"]
        self.assertEqual(len(started), 1, "对账多少次都只接纳一次")

    def test_repair_after_401_does_not_replay_writes(self):
        """401 后重新配对：不得自动重放任何写动作。"""
        status, payload, cookie = self._pair()
        self._action("start_plan", {"items": [{"id": "a1"}], "request_id": "r1"},
                     cookie, payload["csrf"])
        writes_before = [c for c in self.api.calls if c[0] != "list_activities"]
        # 会话失效（撤销 cookie）→ 401
        self.service.revoke_all()
        status, _, _ = self._req("GET", "/api/state", cookie=cookie)
        self.assertIn(status, (401, 403))
        # 重新配对（新的一码一次）后只读状态，不重放写操作
        fresh = self.service.current_pair_code()
        status, payload2, cookie2 = self._pair(fresh)
        self.assertEqual(status, 200, "新的一码一次必须能重新配对")
        state = self._state(cookie2)
        self.assertEqual(state["state"]["activities"][0]["id"], "a1")
        writes_after = [c for c in self.api.calls if c[0] != "list_activities"]
        self.assertEqual(writes_after, writes_before + [],
                         "重新配对后不得自动重放写操作")

    def test_unknown_result_does_not_auto_restart(self):
        """结果未知（pending）不自动重启计划，也不重发未确认任务。"""
        status, payload, cookie = self._pair()
        self._action("start_plan", {"items": [{"id": "a1"}], "request_id": "r1"},
                     cookie, payload["csrf"])
        self.api.plan["tasks"][0]["status"] = "failed"
        self.api.plan["tasks"][0]["stop_reason"] = "unconfirmed"
        state = self._state(cookie)
        task = state["state"]["plan"]["tasks"][0]
        self.assertEqual(task["stop_reason"], "unconfirmed")
        started = [c for c in self.api.calls if c[0] == "start_plan"]
        self.assertEqual(len(started), 1,
                         "未知结果不得自动重启/重发（决策 6）")

    def test_deadline_matches_across_worker_parent_desktop(self):
        """三种模式下 worker 公式 / 父截止 / 手机投影同值（离线对照）。"""
        from domain.time_text import task_deadline
        from grab import compute_retry_window
        for mode, want in ((120, ANCHOR + 120.0),
                           (ADAPTIVE_RETRY, ANCHOR + DEFAULT_RETRY_SECONDS),
                           (0, ANCHOR + 4000.0)):
            _, worker_deadline, _ = compute_retry_window(
                ANCHOR, ANCHOR + 4000.0, mode, now=ANCHOR)

            class Spec:
                retry_started_at = ANCHOR
                sign_end = "2026-11-02 09:00:00"
                retry_for_s = mode

            parent = task_deadline(Spec(), lambda _t: ANCHOR + 4000.0)
            self.assertEqual(worker_deadline, want)
            self.assertEqual(parent, want)
            self.assertEqual(
                initial_deadline(ANCHOR, mode, ANCHOR + 4000.0), want)

if __name__ == "__main__":
    unittest.main()
