# -*- coding: utf-8 -*-
"""自动恢复调度的假时钟与接线回归；不读取本机凭据。

@author Author
"""
import sys
import threading
import json
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.auto_relogin import AutoReloginMonitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.allowed = True
        self.checks = []
        self.starts = []
        self.flow = {"state": "idle"}
        self.monitor = AutoReloginMonitor(
            now=lambda: self.now, check=lambda: self.checks.append(self.now),
            start=self.begin, eligible=lambda: self.allowed, state=lambda: self.flow)
        self.addCleanup(self.monitor.stop)

    def begin(self):
        self.starts.append(self.now)
        self.flow = {"state": "starting", "flow_id": str(len(self.starts))}
        return {"ok": True, "flow_id": self.flow["flow_id"]}

    def test_worker_request_starts_relogin_right_away_even_in_backoff(self):
        # 决策 015：报名进程发来 login_wait，下一拍就自动登录，不等退避
        self.monitor.observe_check("expired")
        self.flow = {"state": "idle"}
        self.monitor._failures = 2
        self.monitor._retry_at = self.now + 900
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_worker_request_does_not_double_start_while_inflight(self):
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        self.monitor.request_recover()   # 第一轮还在跑
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_worker_request_respects_eligibility_gate(self):
        self.allowed = False
        self.monitor.request_recover()
        self.monitor.tick()
        self.assertEqual(self.starts, [])

    def test_initial_wait_period_and_disabled_gate(self):
        self.monitor.tick()
        self.assertEqual(self.checks, [])
        self.now = 60
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.now = 120
        self.allowed = False
        self.monitor.tick()
        self.assertEqual(self.checks, [60])
        self.allowed = True
        self.monitor.tick()
        self.assertEqual(self.checks, [60, 120])

    def test_only_expired_starts_and_waiting_code_stays_inflight(self):
        for result in ("unknown", "network", "bad_clock", "none", "valid"):
            self.monitor.observe_check(result)
            self.monitor.tick()
        self.assertEqual(self.starts, [])
        self.monitor.observe_check("expired")
        self.monitor.tick()
        for phase in ("starting", "waiting_code", "verifying"):
            self.flow["state"] = phase
            self.now += 1000
            self.monitor.tick()
        self.assertEqual(len(self.starts), 1)

    def test_a_takeover_by_another_source_is_not_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 手机端另开一场人工重登：中继换成了一条新的、还在跑的流程
        self.flow = {"state": "waiting_code", "flow_id": "phone-1", "live": True}
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["failures"], 0,
                         "人主动接手不是自动重登失败，不能累加失败次数")
        self.assertFalse(snapshot["inflight"], "槽位要放回去，别一直占着")

    def test_our_own_flow_vanishing_still_counts_as_a_failure(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(len(self.starts), 1)
        # 中继里什么都没有了：这一轮确实没跑成
        self.flow = {"state": "idle", "flow_id": "", "live": False}
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 1)

    def test_backoff_cap_success_reset_and_clear_suppress(self):
        self.monitor.observe_check("expired")
        for wait in (60, 120, 300, 900, 900):
            self.monitor.tick()
            self.flow["state"] = "failed"
            self.monitor.tick()
            started = len(self.starts)
            self.now += wait - 1
            self.monitor.tick()
            self.assertEqual(len(self.starts), started)
            self.now += 1
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        self.assertEqual(self.monitor.snapshot()["failures"], 0)
        started = len(self.starts)
        self.monitor.observe_check("expired")
        self.monitor.reset()
        self.allowed = False
        self.now += 5000
        self.monitor.tick()
        self.assertEqual(len(self.starts), started)

    def test_success_records_recent_use_without_sensitive_fields(self):
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.flow["state"] = "success"
        self.monitor.tick()
        snapshot = self.monitor.snapshot()
        self.assertEqual(snapshot["last_used_method"], "auto_ocr")
        self.assertEqual(snapshot["last_used_ago_s"], 0)
        text = json.dumps(snapshot, ensure_ascii=False)
        for leaked in ("secret", "password", "token", "code"):
            self.assertNotIn(leaked, text)
        # 历史事实不被 reset 擦掉：界面要能解释「上次是谁完成的」
        self.now += 125
        self.monitor.reset()
        later = self.monitor.snapshot()
        self.assertEqual(later["last_used_method"], "auto_ocr")
        self.assertEqual(later["last_used_ago_s"], 125)

    def test_callbacks_can_reenter_and_concurrent_tick_is_singleflight(self):
        entered, release = threading.Event(), threading.Event()
        def begin():
            self.monitor.snapshot()
            entered.set()
            release.wait(2)
            return self.begin()
        self.monitor._start_relogin = begin
        self.monitor.observe_check("expired")
        thread = threading.Thread(target=self.monitor.tick)
        thread.start()
        self.assertTrue(entered.wait(1))
        self.monitor.tick()
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.starts), 1)

    def test_stop_wakes_wait_and_prevents_more_work(self):
        self.monitor.start()
        self.monitor.stop()
        self.assertFalse(self.monitor._thread.is_alive())
        self.now = 1000
        self.monitor.observe_check("expired")
        self.monitor.tick()
        self.assertEqual(self.starts + self.checks, [])


class RelayRaceTests(unittest.TestCase):
    def test_spawn_reservation_and_old_finish_cannot_replace_new_flow(self):
        from application.login_relay_service import LoginRelayService
        from test_login_relay import FakeWorker
        entered, release = threading.Event(), threading.Event()
        workers = []
        def spawn(_args):
            worker = FakeWorker()
            workers.append(worker)
            entered.set()
            release.wait(2)
            return worker
        service = LoginRelayService(spawn=spawn, now=lambda: 0)
        self.addCleanup(service.shutdown)
        service.prepare("fictional", "fictional")
        answers = []
        thread = threading.Thread(target=lambda: answers.append(
            service.begin(worker_command=["fake"], origin="auto")))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(service.begin(worker_command=["fake"])["error"], "busy")
        finally:
            release.set()
            thread.join(3)
        old = service._flow
        self.assertEqual(service.cancel(origin="phone").get("skipped"), "foreign_origin")
        service.cancel()
        service.begin(worker_command=["fake"])
        current = service.state()["flow_id"]
        service._finish(old)
        service._handle_line(old, '[login] {"kind":"success","flow_id":"%s"}' % old["flow_id"])
        self.assertEqual(service.state()["flow_id"], current)


class PausedMonitorTests(unittest.TestCase):
    """保存的密码被学校拒绝过：自动登录暂停，不再拿同一份密码去试。"""

    def test_paused_monitor_never_starts(self):
        starts = []
        paused = {"value": True}
        monitor = AutoReloginMonitor(
            now=lambda: 0, check=lambda: None,
            start=lambda: starts.append(1) or {"ok": True, "flow_id": "f"},
            eligible=lambda: True, state=lambda: {"state": "idle"},
            paused=lambda: paused["value"])
        monitor.observe_check("expired")
        monitor.request_recover()
        monitor.tick()
        self.assertEqual(starts, [], "暂停时报名进程请求自动登录也不发起")
        self.assertEqual(monitor.snapshot()["state"], "paused")
        paused["value"] = False
        monitor.tick()
        self.assertEqual(starts, [1], "写入新密码解除暂停后恢复")


class LateWindowRuleTests(unittest.TestCase):
    """计划运行中「来不及重新登录」：提交中，或离开放不到 100 秒。"""

    def setUp(self):
        from domain import login_rules
        self.rules = login_rules
        self.opens = {"a": 1000.0, "b": 2000.0}

    def _late(self, tasks, now):
        return self.rules.relogin_too_late(tasks, now, lambda t: self.opens.get(t.get("id")))

    def test_window_is_100_seconds(self):
        self.assertEqual(self.rules.LATE_WINDOW_S, 100)
        waiting = [{"id": "a", "status": "waiting"}]
        self.assertFalse(self._late(waiting, 899), "离开放 101 秒还来得及")
        self.assertTrue(self._late(waiting, 900), "离开放正好 100 秒就来不及")
        self.assertTrue(self._late(waiting, 1005), "过了开放还在排队也来不及")

    def test_submitting_is_always_late(self):
        self.assertTrue(self._late([{"id": "b", "status": "submitting"}], 0))

    def test_finished_and_unknown_open_do_not_block(self):
        self.assertFalse(self._late([{"id": "a", "status": "success"},
                                     {"id": "x", "status": "waiting"}], 999))

    def test_mask_account_keeps_two_and_two(self):
        self.assertEqual(self.rules.mask_account("stu20990001"), "st****01")
        self.assertEqual(self.rules.mask_account("ab"), "a****")
        self.assertEqual(self.rules.mask_account(""), "")


if __name__ == "__main__":
    unittest.main()
